"""Other Actions Engine — Motor Dinámico para "Otras Acciones".

Hermano de `notification_engine.py`, pero para acciones que NO están atadas a
una cotización (cambio de fase de Nuevos Productos, creación de Proyecto de
Integración). Lee `other_action_configs` (keyed por `action_id`) y despacha a
los destinatarios internos configurados por el admin, con la plantilla y canal
(Correo / Centro de Mensajes) elegidos.

Reglas de comportamiento (acordadas con el usuario):
  - Si NO existe config para la acción → retorna {"dispatched": False} y el
    caller ejecuta su lógica legacy (cero regresión en Producción).
  - Si la config existe pero `enabled` es False → NO se envía nada y se retorna
    {"dispatched": True, "disabled": True}. El caller NO debe hacer fallback.
  - Si la config existe, está activa y tiene destinatarios → despacha y retorna
    {"dispatched": True, "sent_count": N, ...}.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from config import db
from services.email_service import send_email
from services.inbox_service import deliver_to_inbox
from services.notification_engine import _load_template, _render, _resolve_user_email
from services.dynamic_recipients import resolve_project_implementer

logger = logging.getLogger("other_actions_engine")


def _resolve_client_email(client: Optional[dict], template_vars: dict) -> tuple:
    """Resuelve (email, nombre) del cliente externo para el destinatario 'client_field'.
    Prioriza el documento `client`; si no, usa variables de plantilla comunes."""
    if client:
        e = (client.get("email") or "").strip()
        cname = (client.get("fantasy_name") or client.get("legal_name")
                 or client.get("commercial_name") or "").strip()
        if e and "@" in e:
            return e, (cname or e)
        for c in (client.get("contacts") or []):
            ce = (c.get("email") or "").strip()
            if ce and "@" in ce:
                return ce, (cname or c.get("name") or ce)
    for k in ("Email_Cliente", "Email_Contacto", "Correo_Cliente", "correo_cliente", "client_email"):
        v = template_vars.get(k)
        if isinstance(v, str) and v.strip() and "@" in v:
            nombre = template_vars.get("Nombre_Cliente") or template_vars.get("Cliente") or v.strip()
            return v.strip(), nombre
    return "", ""


async def get_config(action_id: str) -> Optional[dict]:
    return await db.other_action_configs.find_one({"action_id": action_id}, {"_id": 0})


async def _dispatch_guaranteed_only(
    action_id: str,
    template_vars: dict,
    current_user: Optional[dict],
    fallback_subject: str,
    guaranteed_to: list,
    extra_attachments: Optional[list],
    prepend_signature_html: Optional[str],
) -> dict:
    """Envío mínimo garantizado cuando la acción no tiene config: notifica igual
    al Integrador y a los correos adicionales con un cuerpo genérico + firma."""
    from services.signature import build_signature_html
    if "Firma_Notificacion_Global" not in template_vars:
        sig_html = await build_signature_html(current_user) if current_user else await build_signature_html(None)
        if prepend_signature_html:
            sig_html = prepend_signature_html + sig_html
        template_vars["Firma_Notificacion_Global"] = sig_html
    tpl = {
        "subject": fallback_subject or "Notificación",
        "body_html": (
            f"<p>{fallback_subject or 'Notificación del sistema'}.</p>"
            "<p>{Firma_Notificacion_Global}</p>"
        ),
    }
    subject = _render(tpl["subject"], template_vars) or fallback_subject or "Notificación"
    body = _render(tpl["body_html"], template_vars)
    sent_to: list[str] = []
    for g_email in guaranteed_to:
        try:
            await send_email(to=[g_email], subject=subject, html=body,
                             action=f"{action_id}_other", attachments=(extra_attachments or None))
            sent_to.append(g_email)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[other-actions] Error (garantizado/no_config) enviando a {g_email}: {e}")
    return {"dispatched": True, "disabled": False, "sent_count": len(sent_to),
            "recipients": sent_to, "reason": "guaranteed_only"}


async def dispatch_other_action(
    action_id: str,
    template_vars: dict,
    current_user: Optional[dict] = None,
    fallback_subject: str = "",
    executive_user_id: Optional[str] = None,
    extra_cc: Optional[list] = None,
    project: Optional[dict] = None,
    prepend_signature_html: Optional[str] = None,
    integrator: Optional[dict] = None,
    extra_attachments: Optional[list] = None,
    client: Optional[dict] = None,
    guaranteed_to: Optional[list] = None,
) -> dict:
    """Despacha la acción según la config dinámica. Ver reglas en el docstring
    del módulo.

    `extra_cc`: lista opcional de correos a incluir en COPIA (CC) en CADA envío
    por email (p.ej. el "Correo Adicional Eventual" de un Proyecto de Integración).
    No altera los destinatarios configurados; solo se añade en copia.

    `project`: documento del proyecto que detona el evento. Necesario para resolver
    el destinatario dinámico "Usuario Implementador" (type='project_implementer').

    `prepend_signature_html`: bloque HTML opcional que se inserta INMEDIATAMENTE
    encima de la firma institucional ({Firma_Notificacion_Global}). Útil para
    garantizar que un mensaje personalizado quede justo antes de la firma,
    independientemente de si la plantilla referencia o no su variable propia.
    """
    extra_cc = [e for e in (extra_cc or []) if e and isinstance(e, str) and '@' in e]
    # `guaranteed_to`: destinatarios que SIEMPRE deben recibir el correo (To),
    # independientemente de las filas de destinatarios configuradas. Se usa para
    # garantizar la notificación de Cierre de Proyecto al Integrador y a los
    # correos adicionales del operador. Dedup case-insensitive.
    _seen_g = set()
    guaranteed_to = [
        e.strip() for e in (guaranteed_to or [])
        if e and isinstance(e, str) and '@' in e
        and not (e.strip().lower() in _seen_g or _seen_g.add(e.strip().lower()))
    ]
    cfg = await get_config(action_id)
    if not cfg:
        if guaranteed_to:
            return await _dispatch_guaranteed_only(
                action_id, template_vars, current_user, fallback_subject,
                guaranteed_to, extra_attachments, prepend_signature_html,
            )
        return {"dispatched": False, "reason": "no_config"}

    # Toggle global de la acción: si está desactivada, no sale ningún correo.
    if not cfg.get("enabled", True):
        logger.info(f"[other-actions] '{action_id}' desactivada — no se envía nada")
        return {"dispatched": True, "disabled": True, "sent_count": 0}

    recipients = cfg.get("recipients") or []
    if not recipients and not guaranteed_to:
        # Config existe pero sin filas: tratar como "no configurado" → fallback.
        return {"dispatched": False, "reason": "no_recipients"}

    sent_count = 0
    sent_to: list[str] = []
    skipped: list[dict] = []
    delivered: set = set()  # emails ya notificados (To + CC), para evitar duplicados

    for row in recipients:
        rtype = row.get("type", "user")
        rcpt_email, rcpt_name, rcpt_user_id = "", "", None
        if rtype == "user":
            resolved = await _resolve_user_email(row.get("user_id", ""))
            if not resolved:
                skipped.append({"row_id": row.get("row_id"), "reason": "Usuario no encontrado o inactivo"})
                continue
            rcpt_email, rcpt_name = resolved
            rcpt_user_id = row.get("user_id")
        elif rtype == "session_user":
            # "Usuario generador": el usuario web activo que dispara la acción.
            se = (current_user or {}).get("email")
            if not se:
                skipped.append({"row_id": row.get("row_id"), "reason": "Sin usuario de sesión (Usuario generador)"})
                continue
            rcpt_email = se
            rcpt_name = (
                f"{(current_user or {}).get('first_name', '')} {(current_user or {}).get('last_name', '')}".strip()
                or se
            )
            rcpt_user_id = (current_user or {}).get("user_id")
        elif rtype == "session_executive":
            # "Ejecutivo generador": el ejecutivo que originó el registro (cotización/proyecto).
            resolved = await _resolve_user_email(executive_user_id or "")
            if not resolved:
                skipped.append({"row_id": row.get("row_id"), "reason": "Ejecutivo generador no encontrado"})
                continue
            rcpt_email, rcpt_name = resolved
            rcpt_user_id = executive_user_id
        elif rtype == "project_implementer":
            # "Usuario Implementador": el técnico asignado al proyecto que detona
            # el evento. Con contingencia a Coordinador/Administrador.
            rcpt_email, rcpt_name, rcpt_user_id, fb_note = await resolve_project_implementer(project)
            if not rcpt_email:
                skipped.append({"row_id": row.get("row_id"), "reason": fb_note or "Implementador no resoluble"})
                continue
            if fb_note:
                logger.warning(
                    f"[other-actions] {action_id} · Usuario Implementador (fallback): {fb_note} "
                    f"(proyecto {(project or {}).get('project_number', 's/n')}) → {rcpt_email}"
                )
        elif rtype == "integrator_user":
            # "Usuario Integrador": el "Responsable por parte del Integrador".
            # Su correo puede vivir en `principal_contact_email` (ficha completa)
            # o en `contacts[0].email` (wizard de creación). Cascada robusta.
            email = ((integrator or {}).get("principal_contact_email") or "").strip()
            iname = (integrator or {}).get("principal_contact_name") or ""
            if not email or '@' not in email:
                for _c in ((integrator or {}).get("contacts") or []):
                    _ce = (_c.get("email") or "").strip()
                    if _ce and '@' in _ce:
                        email = _ce
                        iname = iname or (_c.get("name") or "")
                        break
            if not email or '@' not in email:
                skipped.append({"row_id": row.get("row_id"), "reason": "Integrador sin correo de Responsable (Usuario Integrador)"})
                continue
            rcpt_email = email
            rcpt_name = iname or (integrator or {}).get("name") or email
            rcpt_user_id = None
        elif rtype == "client_field":
            # "Correo del Cliente": correo del cliente externo asociado al evento.
            # Se resuelve desde el documento `client` (si se pasa) o desde variables
            # de plantilla (Email_Cliente / Email_Contacto / Correo_Cliente / client_email).
            ce, cname = _resolve_client_email(client, template_vars)
            if not ce:
                skipped.append({"row_id": row.get("row_id"), "reason": "Cliente sin correo (Correo del Cliente)"})
                continue
            rcpt_email = ce
            rcpt_name = cname
            rcpt_user_id = None
        else:
            skipped.append({"row_id": row.get("row_id"), "reason": f"Tipo de destinatario no soportado: {rtype}"})
            continue

        tpl = await _load_template(row.get("template_id"))
        if not tpl:
            # Sin plantilla seleccionada → cuerpo genérico por defecto. Evita el
            # no-envío silencioso y garantiza que los adjuntos automáticos (p.ej.
            # el Certificado de Integración) igual se despachen.
            tpl = {
                "subject": fallback_subject or "Notificación",
                "body_html": (
                    f"<p>{fallback_subject or 'Notificación del sistema'}.</p>"
                    "<p>{Firma_Notificacion_Global}</p>"
                ),
            }

        # Firma institucional global: SIEMPRE refleja al usuario que ejecuta la
        # acción manual. Los template_vars de proyecto traen un baseline
        # "CRM - Gestor" (resolve_project_template_vars), que aquí se sobreescribe
        # con los datos reales del operador en sesión.
        from services.signature import build_signature_html
        if current_user:
            sig_html = await build_signature_html(current_user)
        elif "Firma_Notificacion_Global" not in template_vars:
            sig_html = await build_signature_html(None)
        else:
            sig_html = template_vars["Firma_Notificacion_Global"]
        # Inserta el bloque (p.ej. "Información adicional") justo encima de la firma.
        if prepend_signature_html:
            sig_html = prepend_signature_html + sig_html
        template_vars["Firma_Notificacion_Global"] = sig_html

        subject = _render(tpl.get("subject", ""), template_vars) or fallback_subject
        body = _render(tpl.get("body_html", "") or tpl.get("body", ""), template_vars)

        channel = (row.get("delivery_channel") or "email").lower()
        # El canal "inbox" requiere un usuario interno (user_id).
        if not rcpt_user_id:
            channel = "email"
        try:
            if channel == "inbox":
                await deliver_to_inbox(
                    user_id=rcpt_user_id,
                    recipient_email=rcpt_email,
                    recipient_name=rcpt_name,
                    subject=subject or fallback_subject or "Notificación",
                    html=body,
                    action_id=action_id,
                    project_id=(project or {}).get("project_id") if project else None,
                    attachments=extra_attachments,
                )
            else:
                cc_list = [e for e in (extra_cc or []) if e != rcpt_email] or None
                await send_email(
                    to=[rcpt_email],
                    subject=subject or fallback_subject or "Notificación",
                    html=body,
                    action=f"{action_id}_other",
                    cc=cc_list,
                    attachments=(extra_attachments or None),
                )
                delivered.add(rcpt_email.lower())
                for _cc in (cc_list or []):
                    delivered.add(_cc.lower())
            sent_count += 1
            sent_to.append(rcpt_email)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[other-actions] Error enviando a {rcpt_email} (channel={channel}): {e}")
            skipped.append({"row_id": row.get("row_id"), "reason": str(e)})

    # ---------- Envío GARANTIZADO (To) a Integrador + adicionales ----------
    # Cada correo en `guaranteed_to` que aún no haya sido notificado (ni como To ni
    # como CC en las filas configuradas) recibe el mensaje directamente.
    if guaranteed_to:
        # Selección de plantilla: primera fila con template_id; si no, genérica.
        g_tpl = None
        for row in recipients:
            if row.get("template_id"):
                g_tpl = await _load_template(row.get("template_id"))
                if g_tpl:
                    break
        if not g_tpl:
            g_tpl = {
                "subject": fallback_subject or "Notificación",
                "body_html": (
                    f"<p>{fallback_subject or 'Notificación del sistema'}.</p>"
                    "<p>{Firma_Notificacion_Global}</p>"
                ),
            }
        # Firma institucional (si aún no se estableció en el bucle).
        if "Firma_Notificacion_Global" not in template_vars:
            from services.signature import build_signature_html
            sig_html = await build_signature_html(current_user) if current_user else await build_signature_html(None)
            if prepend_signature_html:
                sig_html = prepend_signature_html + sig_html
            template_vars["Firma_Notificacion_Global"] = sig_html
        g_subject = _render(g_tpl.get("subject", ""), template_vars) or fallback_subject or "Notificación"
        g_body = _render(g_tpl.get("body_html", "") or g_tpl.get("body", ""), template_vars)
        for g_email in guaranteed_to:
            if g_email.lower() in delivered:
                continue
            try:
                await send_email(
                    to=[g_email],
                    subject=g_subject,
                    html=g_body,
                    action=f"{action_id}_other",
                    attachments=(extra_attachments or None),
                )
                delivered.add(g_email.lower())
                sent_count += 1
                sent_to.append(g_email)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[other-actions] Error (garantizado) enviando a {g_email}: {e}")
                skipped.append({"row_id": "guaranteed", "reason": str(e)})

    # Bitácora del despacho
    try:
        await db.bitacora.insert_one({
            "action": "other_action_dispatch",
            "action_id": action_id,
            "sent_count": sent_count,
            "sent_to": sent_to,
            "cc": extra_cc,
            "skipped": skipped,
            "executed_by": (current_user or {}).get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    logger.info(f"[other-actions] {action_id} dispatched: sent={sent_count}, skipped={len(skipped)}")
    return {"dispatched": True, "disabled": False, "sent_count": sent_count, "recipients": sent_to, "cc": extra_cc, "skipped": skipped}
