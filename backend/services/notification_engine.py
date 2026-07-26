"""Notification Engine — Motor Dinámico de Notificaciones (Fase 2).

Lee `action_notification_configs` y envía correos según la matriz configurada por
el admin. Si no hay config para una acción, devuelve False y el caller debe usar
el motor legacy como fallback (cero riesgo de regresión).

Función principal:
    `await try_dispatch(action_id, quote, current_user, **ctx)` → bool
    Retorna True si despachó usando configs dinámicas; False si no había config
    (caller debe ejecutar lógica legacy).
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Optional

from config import db
from services.email_service import send_email
from services.inbox_service import deliver_to_inbox

logger = logging.getLogger("notification_engine")


def _quote_to_biz_sub(quote: dict) -> tuple[Optional[str], Optional[str]]:
    """Mapea una cotización a (business_type, product_subcategory).

    Reglas:
      - quote_category == 'equipment' → ('equipos', None)
      - quote_category == 'repair' → ('reparaciones', None)
      - quote_category == 'implementation' →
          biz = implementacion_pyme | implementacion_corp (según sede/segment)
          sub = vpos | mpos_tablet | mpos_imple_pos | payment_gateway
                (según quote_type / sub-tipo)
      - Otros → (None, None) → no aplica config dinámico, fallback legacy.
    """
    cat = (quote.get("quote_category") or "").lower()
    if cat == "direct_project":
        # Proyectos creados desde el módulo "Proyectos Directos" — sin sub-categoría.
        return "proyectos_directos", None
    if cat == "equipment":
        # Iter50: equipos ahora se subcategoriza por segmento del cliente.
        sede = (quote.get("sede") or quote.get("client_segment") or "PYME").upper()
        sub = "clientes_corp" if sede == "CORP" else "clientes_pyme"
        return "equipos", sub
    if cat == "repair":
        return "reparaciones", None
    # MPOS Imple+POS (Fast Track) usa el bucket de Implementación en el catálogo:
    # el admin lo configura bajo "Implementaciones Pyme/Corp · MPOS Imple+POS".
    if cat == "fast_track":
        sede = (quote.get("sede") or quote.get("client_segment") or "PYME").upper()
        biz = "implementacion_corp" if sede == "CORP" else "implementacion_pyme"
        return biz, "mpos_imple_pos"
    if cat != "implementation":
        return None, None

    sede = (quote.get("sede") or quote.get("client_segment") or "PYME").upper()
    biz = "implementacion_corp" if sede == "CORP" else "implementacion_pyme"

    qtype = (quote.get("quote_type") or "").upper()
    sub_quote_type = (quote.get("sub_quote_type") or "").upper()
    if qtype in ("LINK_PAGO", "LINK"):
        sub = "link_pago"
    elif qtype == "GATEWAY" or "GATEWAY" in qtype:
        sub = "payment_gateway"
    elif qtype == "VPOS":
        sub = "vpos"
    elif qtype == "MPOS":
        # Distinguir MPOS Tablet vs MPOS Imple+POS por sub_quote_type
        if "IMPLE" in sub_quote_type or "POS" in sub_quote_type:
            sub = "mpos_imple_pos"
        else:
            sub = "mpos_tablet"
    else:
        sub = None
    return biz, sub


async def _load_template(template_id: str) -> Optional[dict]:
    if not template_id:
        return None
    return await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})


async def _resolve_user_email(user_id: str) -> Optional[tuple[str, str]]:
    if not user_id:
        return None
    u = await db.users.find_one({"user_id": user_id, "is_active": True}, {
        "_id": 0, "email": 1, "first_name": 1, "last_name": 1,
    })
    if not u or not u.get("email"):
        return None
    name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u["email"]
    return u["email"], name


async def _build_template_vars(quote: dict) -> dict:
    """Resuelve variables comunes desde la cotización + cliente.

    HOMOLOGADO con el motor legacy (`services.workflow_notifications.py`):
    expone tanto los nombres en snake_case (legacy: `client_name`,
    `quote_number`, `total_usd`, etc.) como los CamelCase
    (`Nombre_Cliente`, `Cotizacion_Nro`, ...) y minúsculas
    (`nombre_cliente`, `nro_cotizacion`) para máxima compatibilidad con
    plantillas existentes y futuras.
    """
    creator_name, creator_email = "", ""
    if quote.get("created_by_user_id"):
        creator = await db.users.find_one(
            {"user_id": quote["created_by_user_id"]},
            {"_id": 0, "first_name": 1, "last_name": 1, "email": 1},
        )
        if creator:
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            creator_email = creator.get("email", "")

    legal_name = quote.get("client_name", "")
    rif = quote.get("client_rif", "")
    address = ""
    contact_name = quote.get("client_contact", "") or ""
    contact_email = quote.get("client_email", "") or ""
    contact_phone = quote.get("client_phone", "") or ""
    client_fantasy = ""
    if quote.get("client_id"):
        c = await db.clients.find_one(
            {"client_id": quote["client_id"]},
            {"_id": 0, "fantasy_name": 1, "legal_name": 1, "rif": 1,
             "address": 1, "contacts": 1, "contact1": 1},
        )
        if c:
            # Reglas de mapeo de variables dinámicas (Feb 2026):
            # - {client_name} / {Nombre_Cliente} → SIEMPRE Razón Social
            #   (legal_name). Antes se priorizaba fantasy_name, lo que generaba
            #   confusión legal en emails y documentos institucionales.
            legal_name = c.get("legal_name") or c.get("fantasy_name") or legal_name
            client_fantasy = c.get("fantasy_name") or ""
            rif = rif or c.get("rif", "")
            address = c.get("address") or ""
            contacts = c.get("contacts") or []
            primary = contacts[0] if contacts else (c.get("contact1") or {})
            if isinstance(primary, dict):
                contact_name = contact_name or primary.get("full_name") or primary.get("name") or (
                    f"{primary.get('first_name', '')} {primary.get('last_name', '')}".strip()
                )
                contact_email = contact_email or primary.get("email") or ""
                contact_phone = contact_phone or primary.get("phone") or primary.get("telefono") or ""

    # Normalización fiscal: RIF a 9 dígitos con padding de ceros a la izquierda.
    # Feb 2026 — Requerimiento de integridad de datos: previene casos como
    # `V12345` que en realidad es `V-000012345`.
    from services.rif_formatter import format_rif
    rif = format_rif(rif)

    raw_segment = quote.get("sede", quote.get("client_segment", "PYME"))
    norm_segment = (
        "PYME" if raw_segment in ("TBP", "PYME", "Pymes", "pyme")
        else "CORP" if raw_segment in ("CORP", "Corp", "Corporativo")
        else raw_segment
    )
    quote_number = quote.get("quote_number", "")
    invoice_number = quote.get("invoice_number", "") or ""

    # === {Estado_Proyecto} — estado actual del proyecto derivado ===
    # Disponible también en plantillas de Cotizaciones: si el registro base es un
    # proyecto trae su status; si es una cotización, se busca el proyecto asociado.
    estado_proyecto = quote.get("status") or ""
    if not estado_proyecto and quote.get("quote_id"):
        _proj = await db.projects.find_one({"quote_id": quote["quote_id"]}, {"_id": 0, "status": 1})
        if _proj:
            estado_proyecto = _proj.get("status") or ""

    approved_at = quote.get("approved_at") or quote.get("collected_at") or ""
    approved_date = ""
    if approved_at:
        try:
            from datetime import datetime
            approved_date = datetime.fromisoformat(approved_at.replace("Z", "+00:00")).strftime("%d/%m/%Y")
        except Exception:
            approved_date = approved_at[:10] if isinstance(approved_at, str) else ""

    # ============================================================
    # Variables computadas (HTML tables / listas) — antes solo
    # existían en motores legacy específicos. Ahora se construyen
    # universalmente para que CUALQUIER plantilla las reciba sin
    # importar qué acción invoque al motor.
    # ============================================================
    # 1) items_table — Despacho/Equipos: tabla HTML compacta
    items_table_html = ""
    equipment_items = quote.get("equipment_items") or []
    ft_items = quote.get("ft_equipment_items") or []
    all_eq = equipment_items + ft_items
    if all_eq:
        rows = ["<tr><th style='padding:6px;border:1px solid #cbd5e1;background:#f1f5f9;text-align:left'>Modelo</th><th style='padding:6px;border:1px solid #cbd5e1;background:#f1f5f9;text-align:right'>Cant.</th></tr>"]
        for it in all_eq:
            name = it.get("name") or it.get("hardware_name") or it.get("model_name") or it.get("modelo") or "Equipo"
            qty = it.get("quantity", 1) or 1
            rows.append(f"<tr><td style='padding:6px;border:1px solid #e2e8f0'>{name}</td><td style='padding:6px;border:1px solid #e2e8f0;text-align:right'>{qty}</td></tr>")
        items_table_html = f"<table style='border-collapse:collapse;width:100%;margin:8px 0;font-size:13px'>{''.join(rows)}</table>"

    # 2) Modelo_Equipo / Cantidad — Fast Track (primer item de ft_equipment_items)
    modelo_equipo = ""
    cantidad_str = ""
    if ft_items:
        primary = ft_items[0]
        modelo_equipo = primary.get("name") or primary.get("model_name") or primary.get("modelo") or ""
        cantidad_total = sum(int(it.get("quantity", 1) or 1) for it in ft_items)
        cantidad_str = str(cantidad_total)
    elif equipment_items:
        primary = equipment_items[0]
        modelo_equipo = primary.get("name") or primary.get("hardware_name") or ""
        cantidad_total = sum(int(it.get("quantity", 1) or 1) for it in equipment_items)
        cantidad_str = str(cantidad_total)

    # 3) lista_modelos_seriales / lista_equipos_seriales — Reparaciones
    lista_modelos_seriales_html = ""
    lista_equipos_seriales_html = ""
    repaired_models = quote.get("repair_models") or quote.get("repaired_models") or []
    for rm in repaired_models:
        mn = rm.get("model_name", "N/A")
        serials = rm.get("serials") or []
        line = f"<p style='margin:4px 0'><strong>{mn}</strong>: {', '.join(serials) if serials else 'sin seriales'}</p>"
        lista_modelos_seriales_html += line
        lista_equipos_seriales_html += line
    # Fallback con preassigned_serials para fast_track
    if not lista_modelos_seriales_html:
        preassigned = quote.get("preassigned_serials") or []
        if preassigned:
            primary_model = modelo_equipo or "Equipo"
            block = f"<p style='margin:4px 0'><strong>{primary_model}</strong>: {', '.join(preassigned)}</p>"
            lista_modelos_seriales_html = block
            lista_equipos_seriales_html = block

    # 4) modelos_resumen — lista plana de modelos (para subjects y previews)
    modelos_resumen = ""
    if repaired_models:
        modelos_resumen = ", ".join([rm.get("model_name", "N/A") for rm in repaired_models])
    elif all_eq:
        modelos_resumen = ", ".join([
            (it.get("name") or it.get("hardware_name") or it.get("model_name") or "Equipo")
            for it in all_eq
        ])

    # 5) almacen_custodia — nombre de la sede como almacén custodio
    sede_names = {"PYME": "Almacen Torre Banco Plaza (Pymes)", "CORP": "Almacen Corporativo"}
    almacen_custodia = sede_names.get(norm_segment, norm_segment)

    # 6) Direccion_Entrega — del cliente; si no existe usar address legal
    direccion_entrega = address or ""

    # 7) abreviaturas_medios_pago — token dinámico que concatena las
    # abreviaturas de los medios de pago seleccionados en la cotización
    # separadas por "/". Si la cotización no tiene medios de pago, queda "".
    try:
        from services.medios_pago_abrev import compute_abreviaturas_medios_pago
        abreviaturas_medios_pago = await compute_abreviaturas_medios_pago(quote)
    except Exception:
        abreviaturas_medios_pago = quote.get("abreviaturas_medios_pago", "") or ""

    # 8) Variables específicas del flujo de Implementación / técnicas de la
    # cotización. Antes solo se exponía `integrator_name` y `pinpad_model`,
    # dejando huérfanos los aliases en español documentados al usuario.
    # Feb 2026: agregamos Cantidad_Cajas (el usuario reportó que esta variable
    # NO se cargaba en la acción "Enviar a Implementación") + resto de aliases.
    cantidad_cajas_val = quote.get("cantidad_cajas")
    if cantidad_cajas_val is None or cantidad_cajas_val == "":
        cantidad_cajas_str = ""
    else:
        try:
            cantidad_cajas_str = str(int(cantidad_cajas_val))
        except (TypeError, ValueError):
            cantidad_cajas_str = str(cantidad_cajas_val)
    integrator_name_val = quote.get("integrator_name", "") or ""
    integrator_app_name_val = quote.get("integrator_app_name", "") or ""
    pinpad_model_val = quote.get("pinpad_model", "") or ""
    sponsor_bank_name_val = quote.get("sponsor_bank_name", "") or ""

    # 9) Variables dinámicas a nivel de cotización (Matriz de Bancos/Productos,
    # Matriz de Sucursales y Patrocinador). Antes NO se resolvían en este motor,
    # por lo que tokens como {Matriz_Bancos_Productos} llegaban vacíos al cliente.
    try:
        from services.quote_template_vars import build_quote_dynamic_vars
        quote_dynamic_vars = build_quote_dynamic_vars(
            quote, client_fantasy=client_fantasy, client_legal=legal_name
        )
    except Exception:
        quote_dynamic_vars = {}

    base_vars = {
        # ----- Cotización -----
        "quote_number": quote_number,
        "Cotizacion_Nro": quote_number,
        "nro_cotizacion": quote_number,
        "quote_type": quote.get("quote_type", "N/A"),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Monto_Total": f"{quote.get('total_usd', 0):.2f}",
        "invoice_number": invoice_number,
        "approved_date": approved_date,
        "Estado_Proyecto": estado_proyecto,
        # ----- Medios de Pago: abreviaturas concatenadas con "/" -----
        "abreviaturas_medios_pago": abreviaturas_medios_pago,
        "Abreviaturas_Medios_Pago": abreviaturas_medios_pago,
        "medios_pago_abreviaturas": abreviaturas_medios_pago,
        # ----- Cliente -----
        "client_name": legal_name,
        "Nombre_Cliente": legal_name,
        "nombre_cliente": legal_name,
        "Nombre_Fantasia": client_fantasy or legal_name,
        "client_rif": rif,
        "Rif_Cliente": rif,
        "client_address": address,
        "Direccion_Cliente": address,
        # ----- Contacto -----
        "Contacto_Principal": contact_name,
        "contacto_cliente": contact_name,
        "Datos_Contacto": contact_name,
        "Email_Contacto": contact_email,
        "Email_Cliente": contact_email,
        "Telefono_Contacto": contact_phone,
        "Telefono_Cliente": contact_phone,
        # ----- Ejecutivo -----
        "Nombre_Ejecutivo": creator_name,
        "Email_Ejecutivo": creator_email,
        # ----- Empresa / Integración -----
        "company_name": quote.get("company_name", "Merchant Server"),
        "integrator_name": integrator_name_val,
        "Integrador": integrator_name_val,
        "integrator_app_name": integrator_app_name_val,
        "Aplicativo_Integracion": integrator_app_name_val,
        "Aplicativo": integrator_app_name_val,
        "pinpad_model": pinpad_model_val,
        "Modelo_Pinpad": pinpad_model_val,
        "Pinpad": pinpad_model_val,
        "sponsor_bank_name": sponsor_bank_name_val,
        "Banco_Patrocinador": sponsor_bank_name_val,
        # ----- Volumen / Cantidades -----
        # Variable usada por la plantilla de "Enviar a Implementación":
        # antes no se exponía y aparecía vacía al renderizar.
        "cantidad_cajas": cantidad_cajas_str,
        "Cantidad_Cajas": cantidad_cajas_str,
        "cajas": cantidad_cajas_str,
        # ----- Sede -----
        "sede_name": norm_segment,
        "Nombre_Sucursal": quote.get("sede", quote.get("client_segment", "PYME")),
        # ----- Variables computadas (despacho/reparación/fast track) -----
        "items_table": items_table_html,
        "Modelo_Equipo": modelo_equipo,
        "modelo_equipo": modelo_equipo,
        "Cantidad": cantidad_str,
        "cantidad": cantidad_str,
        "lista_modelos_seriales": lista_modelos_seriales_html,
        "lista_equipos_seriales": lista_equipos_seriales_html,
        "Lista_Seriales": lista_modelos_seriales_html,
        "modelos_resumen": modelos_resumen,
        "almacen_custodia": almacen_custodia,
        "Direccion_Entrega": direccion_entrega,
        "direccion_entrega": direccion_entrega,
    }
    base_vars.update(quote_dynamic_vars)
    # V6: Matriz de Contactos de Facturación (Grupo + Principal + Sucursal).
    try:
        from services.billing_contacts import build_billing_matrix_var
        base_vars["Matriz_Contactos_Facturacion"] = await build_billing_matrix_var(quote)
    except Exception:
        base_vars["Matriz_Contactos_Facturacion"] = ""
    return base_vars


def _render(text: str, vars_: dict) -> str:
    if not text:
        return ""
    out = text
    for k, v in vars_.items():
        # Soporta {var} y {{var}}
        out = out.replace("{{" + k + "}}", str(v or ""))
        out = out.replace("{" + k + "}", str(v or ""))
    return out


async def _collect_pdf_attachments(action_id: str, quote: dict, ctx: dict) -> list[dict]:
    """Devuelve lista de attachments en formato Resend (filename + content base64).

    El caller pasa en `ctx` los PDFs ya generados (ej: 'billing_pdf_bytes',
    'implementation_pdf_bytes'). Este helper también puede leer URLs persistidas.
    """
    out = []
    # PDFs pasados por el caller (binarios listos)
    for key, default_name in [
        ("billing_pdf_bytes", f"Calculos_Definitivos_{quote.get('quote_number', 'cot')}.pdf"),
        ("implementation_pdf_bytes", f"Ficha_Tecnica_{quote.get('quote_number', 'cot')}.pdf"),
        ("quote_pdf_bytes", f"Cotizacion_{quote.get('quote_number', 'cot')}.pdf"),
        ("invoice_pdf_bytes", f"Factura_{quote.get('quote_number', 'cot')}.pdf"),
        ("delivery_note_pdf_bytes", f"NotaEntrega_{quote.get('quote_number', 'cot')}.pdf"),
    ]:
        if ctx.get(key):
            out.append({
                "filename": default_name,
                "content": base64.b64encode(ctx[key]).decode("utf-8"),
            })
    return out


def _insert_before_footer(body: str, block: str) -> str:
    """Inserta `block` ANTES del footer/firma del cuerpo HTML.

    Estrategia (en orden de prioridad):
    1. Si hay un cierre clásico de despedida (`Atentamente`, `Saludos`,
       `Cordialmente`, `Gracias por`) → insertar antes del bloque que lo
       contiene (es la regla principal: el "footer" de la mayoría de
       plantillas es esa firma).
    2. Si no hay despedida pero existe `</body>` → insertar justo antes.
    3. Fallback: append al final del body.
    """
    if not body:
        return block
    if not block:
        return body
    import re
    lower = body.lower()
    for needle in ("atentamente", "saludos cordiales", "cordialmente", "saludos,", "gracias por"):
        idx = lower.find(needle)
        if idx == -1:
            continue
        # Buscar el inicio del último <p|div|table|hr> antes del needle (incluye sus tags abiertos)
        candidates = [body.rfind(t, 0, idx) for t in ("<p", "<div", "<table", "<hr")]
        anchor = max(candidates) if any(c != -1 for c in candidates) else -1
        if anchor != -1:
            return body[:anchor] + block + body[anchor:]
        return body[:idx] + block + body[idx:]
    m = re.search(r"</body\s*>", body, flags=re.IGNORECASE)
    if m:
        return body[:m.start()] + block + body[m.start():]
    return body + block


async def try_dispatch(
    action_id: str,
    quote: dict,
    current_user: dict,
    custom_message: Optional[str] = None,
    cc_emails: Optional[list[str]] = None,
    extra_template_vars: Optional[dict] = None,
    extra_attachments: Optional[list[dict]] = None,
    **ctx: Any,
) -> bool:
    """Despacha notificaciones según la config dinámica para esta acción.

    Retorna True si encontró config y envió correos. Retorna False si NO había
    config para `(biz_type, sub_cat, action_id)` — el caller debe ejecutar el
    motor legacy (fallback).

    Si la fila tiene `type=client_field` pero la cotización no tiene email del
    cliente: salta esa fila con warning en logs (no bloquea las demás filas).

    `extra_attachments`: lista [{filename, content (base64)}] de archivos
    adicionales (ej. comprobantes de pago anticipado, soportes del modal de
    personalización). Se adjuntan SIEMPRE al correo (no dependen del flag
    send_pdf_attachments — son responsabilidad del caller).
    """
    biz, sub = _quote_to_biz_sub(quote)
    if not biz:
        return False

    config_key = f"{biz}|{sub or '_'}|{action_id}"
    cfg = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0})
    if not cfg or not cfg.get("recipients"):
        return False

    # Construir variables de plantilla
    tpl_vars = await _build_template_vars(quote)
    if extra_template_vars:
        tpl_vars.update(extra_template_vars)
    # Firma institucional global (resuelve datos del usuario que detona)
    from services.signature import build_signature_html
    tpl_vars["Firma_Notificacion_Global"] = await build_signature_html(current_user)

    # Email del cliente (resolver una vez)
    client_email = tpl_vars.get("Email_Contacto") or quote.get("client_email") or ""

    pdf_attachments = await _collect_pdf_attachments(action_id, quote, ctx)
    custom_block = ""
    if custom_message:
        raw = custom_message
        try:
            from urllib.parse import unquote
            raw = unquote(raw)
        except Exception:
            pass
        safe = (raw or "").strip()[:1500]
        # Bloque visual de "Mensaje del Ejecutivo" — se anexa al FINAL del cuerpo
        # (igual que el motor legacy).
        custom_block = (
            "<hr style='border:none;border-top:1px solid #e2e8f0;margin:24px 0 16px'/>"
            "<div style='border-left:4px solid #2563eb;padding:10px 14px;"
            "background:#eff6ff;margin:10px 0;border-radius:4px'>"
            "<p style='margin:0 0 6px;font-size:12px;color:#1e3a8a;font-weight:600;text-transform:uppercase;letter-spacing:.5px'>Mensaje del Ejecutivo</p>"
            f"<p style='margin:0;color:#334155;line-height:1.5;white-space:pre-wrap'>{safe}</p></div>"
        )

    sent_count = 0
    skipped = []
    # Política de CC del modal: los user_cc_emails se anexan UNA sola vez como
    # CC efectivo del primer envío exitoso (no como copias de cortesía con body
    # genérico). Así llegan como destinatarios visibles del mensaje real,
    # ven los adjuntos y aparecen en el encabezado Cc del receptor.
    user_cc_list = [c for c in (cc_emails or []) if c and "@" in c]
    cc_already_attached = False
    for row in cfg["recipients"]:
        # Resolver destinatario
        rcpt_email, rcpt_name, rcpt_user_id = "", "", None
        if row.get("type") == "client_field":
            if not client_email:
                skipped.append({"row_id": row.get("row_id"), "reason": "Cliente sin email"})
                continue
            rcpt_email = client_email
            rcpt_name = tpl_vars.get("Datos_Contacto", "") or "Cliente"
        elif row.get("type") == "user":
            resolved = await _resolve_user_email(row.get("user_id", ""))
            if not resolved:
                skipped.append({"row_id": row.get("row_id"), "reason": "Usuario no encontrado o inactivo"})
                continue
            rcpt_email, rcpt_name = resolved
            rcpt_user_id = row.get("user_id")
        elif row.get("type") == "session_user":
            # "Usuario generador": el usuario web activo que dispara la acción.
            se = (current_user or {}).get("email")
            if not se:
                skipped.append({"row_id": row.get("row_id"), "reason": "Sin usuario de sesión (Usuario generador)"})
                continue
            rcpt_email = se
            rcpt_name = (
                f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
                or se
            )
            rcpt_user_id = current_user.get("user_id")
        elif row.get("type") == "session_executive":
            # "Ejecutivo generador": el ejecutivo que creó la cotización.
            resolved = await _resolve_user_email(quote.get("created_by_user_id", ""))
            if resolved:
                rcpt_email, rcpt_name = resolved
                rcpt_user_id = quote.get("created_by_user_id")
            else:
                ee = tpl_vars.get("Email_Ejecutivo") or ""
                if not ee or "@" not in ee:
                    skipped.append({"row_id": row.get("row_id"), "reason": "Ejecutivo generador no encontrado"})
                    continue
                rcpt_email = ee
                rcpt_name = tpl_vars.get("Nombre_Ejecutivo") or ee
        else:
            skipped.append({"row_id": row.get("row_id"), "reason": f"tipo desconocido: {row.get('type')}"})
            continue

        # Plantilla
        tpl = await _load_template(row.get("template_id"))
        if not tpl:
            skipped.append({"row_id": row.get("row_id"), "reason": "Plantilla no encontrada"})
            continue

        # Render subject + body con variables resueltas
        subject = _render(tpl.get("subject", ""), tpl_vars)
        body = _render(tpl.get("body_html", "") or tpl.get("body", ""), tpl_vars)
        # Falla A — Garantía de seriales en el correo de Cotización de Reparación al
        # cliente: si el cuerpo renderizado NO incluye ya el listado de seriales, se
        # inyecta el bloque (paridad total con el PDF). Solo aplica al envío al cliente
        # de cotizaciones de reparación con seriales persistidos en `repair_models`.
        if action_id == "send_to_client" and quote.get("quote_category") == "repair":
            _all_serials = [
                s for rm in (quote.get("repair_models") or [])
                for s in (rm.get("serials") or [])
            ]
            _serials_html = tpl_vars.get("Lista_Seriales") or tpl_vars.get("lista_modelos_seriales") or ""
            if _all_serials and _serials_html and not any(str(s) in body for s in _all_serials):
                _serials_block = (
                    "<div style='margin:16px 0'>"
                    "<p style='margin:0 0 6px;font-weight:bold;color:#2c3e50'>Detalle de Seriales de los Equipos:</p>"
                    f"<div style='border:1px solid #e0e0e0;border-radius:6px;padding:10px 14px;background:#f8f9fa'>{_serials_html}</div>"
                    "</div>"
                )
                body = _insert_before_footer(body, _serials_block)
        # Mensaje personalizado se inserta ANTES del footer/firma de la
        # plantilla (no al final absoluto, ni al inicio).
        if custom_block:
            body = _insert_before_footer(body, custom_block)
        # Bloque HTML inyectado por el caller (ej: Matriz Financiera Consolidada
        # de aprobación Corporativa) — se inserta antes del footer.
        _injected_block = ctx.get("injected_html_block")
        if _injected_block:
            body = _insert_before_footer(body, _injected_block)

        # Anexos: PDFs auto-generados (sujetos al flag) + extra_attachments (siempre).
        attachments = []
        if row.get("send_pdf_attachments", True) and pdf_attachments:
            attachments.extend(pdf_attachments)
        if extra_attachments:
            attachments.extend(extra_attachments)
        attachments = attachments or None

        # Adjuntar CCs al primer destinatario solamente (evita N copias)
        cc_for_this_send = None
        if user_cc_list and not cc_already_attached:
            # Excluir el propio destinatario para no duplicar
            cc_for_this_send = [c for c in user_cc_list if c.lower() != rcpt_email.lower()]
            if cc_for_this_send:
                cc_already_attached = True

        # Determinar canal: inbox sólo aplica a usuarios internos. Para
        # `client_field` se fuerza `email` (no podemos mostrar bandeja a
        # un cliente externo).
        channel = (row.get("delivery_channel") or "email").lower()
        # El canal "inbox" sólo es válido para destinatarios internos (con user_id).
        # Cliente externo o destinatarios sin user_id → se fuerza email.
        if not rcpt_user_id:
            channel = "email"

        try:
            if channel == "inbox":
                await deliver_to_inbox(
                    user_id=rcpt_user_id,
                    recipient_email=rcpt_email,
                    recipient_name=rcpt_name,
                    subject=subject or f"Notificación · {quote.get('quote_number', '')}",
                    html=body,
                    action_id=action_id,
                    quote_id=quote.get("quote_id"),
                    quote_number=quote.get("quote_number"),
                    attachments=attachments,
                )
                # Si había CCs asignados a este envío, los enviamos por correo
                # (los CCs son externos al motor de inbox).
                if cc_for_this_send:
                    await send_email(
                        to=cc_for_this_send,
                        subject=subject or f"Notificación · {quote.get('quote_number', '')}",
                        html=body,
                        action=f"{action_id}_dynamic_cc",
                        quote_id=quote.get("quote_id"),
                        quote_number=quote.get("quote_number"),
                        attachments=attachments,
                    )
            else:
                await send_email(
                    to=[rcpt_email],
                    subject=subject or f"Notificación · {quote.get('quote_number', '')}",
                    html=body,
                    action=f"{action_id}_dynamic",
                    quote_id=quote.get("quote_id"),
                    quote_number=quote.get("quote_number"),
                    attachments=attachments,
                    cc=cc_for_this_send,
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"[engine] Error enviando a {rcpt_email} (channel={channel}): {e}")
            skipped.append({"row_id": row.get("row_id"), "reason": str(e)})

    # Fallback: si no se logró adjuntar los CCs (porque ningún destinatario
    # principal fue válido), enviar un correo separado a los CCs con el ÚLTIMO
    # subject/body renderizado, para no perderlos.
    if user_cc_list and not cc_already_attached and sent_count == 0:
        logger.warning(f"[engine] CCs {user_cc_list} no pudieron adjuntarse — sin destinatarios principales válidos")

    # Bitácora del despacho dinámico
    await db.bitacora.insert_one({
        "action": "notification_engine_dispatch",
        "action_id": action_id,
        "config_key": config_key,
        "quote_id": quote.get("quote_id"),
        "quote_number": quote.get("quote_number"),
        "sent_count": sent_count,
        "skipped": skipped,
        "executed_by": (current_user or {}).get("email"),
        "executed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    })
    logger.info(f"[engine] {action_id} dispatched: sent={sent_count}, skipped={len(skipped)}")
    return True


async def has_config(action_id: str, quote: dict) -> bool:
    """Útil para validación previa: ¿hay configuración dinámica para esta acción?"""
    biz, sub = _quote_to_biz_sub(quote)
    if not biz:
        return False
    config_key = f"{biz}|{sub or '_'}|{action_id}"
    cfg = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0, "recipients": 1})
    return bool(cfg and cfg.get("recipients"))


async def validate_client_email_required(action_id: str, quote: dict) -> Optional[str]:
    """Pre-check: si la config tiene una fila tipo `client_field` pero el cliente
    no tiene email registrado, retorna mensaje de advertencia (caller decide si
    abortar). None si no hay problema.
    """
    biz, sub = _quote_to_biz_sub(quote)
    if not biz:
        return None
    config_key = f"{biz}|{sub or '_'}|{action_id}"
    cfg = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0, "recipients": 1})
    if not cfg:
        return None
    needs_client = any(r.get("type") == "client_field" for r in (cfg.get("recipients") or []))
    if not needs_client:
        return None

    client_email = quote.get("client_email")
    if not client_email and quote.get("client_id"):
        c = await db.clients.find_one(
            {"client_id": quote["client_id"]},
            {"_id": 0, "contacts": 1, "contact1": 1},
        )
        if c:
            primary = (c.get("contacts") or [c.get("contact1") or {}])[0] if (c.get("contacts") or c.get("contact1")) else {}
            if isinstance(primary, dict):
                client_email = primary.get("email")
    if not client_email:
        return (
            "La configuración de esta acción requiere notificar al Cliente, pero la ficha "
            "del cliente no tiene email registrado. Cárgalo en la ficha o ajusta la "
            "configuración de la acción antes de continuar."
        )
    return None
