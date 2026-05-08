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
    if cat == "equipment":
        return "equipos", None
    if cat == "repair":
        return "reparaciones", None
    if cat != "implementation":
        return None, None

    sede = (quote.get("sede") or quote.get("client_segment") or "PYME").upper()
    biz = "implementacion_corp" if sede == "CORP" else "implementacion_pyme"

    qtype = (quote.get("quote_type") or "").upper()
    sub_quote_type = (quote.get("sub_quote_type") or "").upper()
    if qtype == "GATEWAY" or "GATEWAY" in qtype:
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
    if quote.get("client_id"):
        c = await db.clients.find_one(
            {"client_id": quote["client_id"]},
            {"_id": 0, "fantasy_name": 1, "legal_name": 1, "rif": 1,
             "address": 1, "contacts": 1, "contact1": 1},
        )
        if c:
            legal_name = c.get("fantasy_name") or c.get("legal_name") or legal_name
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

    raw_segment = quote.get("sede", quote.get("client_segment", "PYME"))
    norm_segment = (
        "PYME" if raw_segment in ("TBP", "PYME", "Pymes", "pyme")
        else "CORP" if raw_segment in ("CORP", "Corp", "Corporativo")
        else raw_segment
    )
    quote_number = quote.get("quote_number", "")
    invoice_number = quote.get("invoice_number", "") or ""
    approved_at = quote.get("approved_at") or quote.get("collected_at") or ""
    approved_date = ""
    if approved_at:
        try:
            from datetime import datetime
            approved_date = datetime.fromisoformat(approved_at.replace("Z", "+00:00")).strftime("%d/%m/%Y")
        except Exception:
            approved_date = approved_at[:10] if isinstance(approved_at, str) else ""

    return {
        # ----- Cotización -----
        "quote_number": quote_number,
        "Cotizacion_Nro": quote_number,
        "nro_cotizacion": quote_number,
        "quote_type": quote.get("quote_type", "N/A"),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Monto_Total": f"{quote.get('total_usd', 0):.2f}",
        "invoice_number": invoice_number,
        "approved_date": approved_date,
        # ----- Cliente -----
        "client_name": legal_name,
        "Nombre_Cliente": legal_name,
        "nombre_cliente": legal_name,
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
        "integrator_name": quote.get("integrator_name", ""),
        "pinpad_model": quote.get("pinpad_model", ""),
        # ----- Sede -----
        "sede_name": norm_segment,
        "Nombre_Sucursal": quote.get("sede", quote.get("client_segment", "PYME")),
    }


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


async def try_dispatch(
    action_id: str,
    quote: dict,
    current_user: dict,
    custom_message: Optional[str] = None,
    cc_emails: Optional[list[str]] = None,
    extra_template_vars: Optional[dict] = None,
    **ctx: Any,
) -> bool:
    """Despacha notificaciones según la config dinámica para esta acción.

    Retorna True si encontró config y envió correos. Retorna False si NO había
    config para `(biz_type, sub_cat, action_id)` — el caller debe ejecutar el
    motor legacy (fallback).

    Si la fila tiene `type=client_field` pero la cotización no tiene email del
    cliente: salta esa fila con warning en logs (no bloquea las demás filas).
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

    # Email del cliente (resolver una vez)
    client_email = tpl_vars.get("Email_Contacto") or quote.get("client_email") or ""

    pdf_attachments = await _collect_pdf_attachments(action_id, quote, ctx)
    custom_block = ""
    if custom_message:
        safe = (custom_message or "").strip()[:300]
        custom_block = (
            "<div style='border-left:4px solid #2563eb;padding:8px 12px;"
            "background:#eff6ff;margin:10px 0'>"
            f"<p style='margin:0;color:#334155'>{safe}</p></div>"
        )

    sent_count = 0
    skipped = []
    for row in cfg["recipients"]:
        # Resolver destinatario
        rcpt_email, rcpt_name = "", ""
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
        if custom_block:
            body = custom_block + body

        attachments = pdf_attachments if row.get("send_pdf_attachments", True) else None

        try:
            await send_email(
                to=[rcpt_email],
                subject=subject or f"Notificación · {quote.get('quote_number', '')}",
                html=body,
                action=f"{action_id}_dynamic",
                quote_id=quote.get("quote_id"),
                quote_number=quote.get("quote_number"),
                attachments=attachments,
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"[engine] Error enviando a {rcpt_email}: {e}")
            skipped.append({"row_id": row.get("row_id"), "reason": str(e)})

    # Cc adicionales (sin attachments por privacidad — siguen política legacy)
    for cc in (cc_emails or []):
        if cc and "@" in cc:
            try:
                await send_email(
                    to=[cc],
                    subject=f"[CC] Notificación · {quote.get('quote_number', '')}",
                    html=f"<p>Copia de cortesía de la acción <b>{action_id}</b>.</p>",
                    action=f"{action_id}_dynamic_cc",
                    quote_id=quote.get("quote_id"),
                    quote_number=quote.get("quote_number"),
                )
            except Exception as e:
                logger.warning(f"[engine] Error CC {cc}: {e}")

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
