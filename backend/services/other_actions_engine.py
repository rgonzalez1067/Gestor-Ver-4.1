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


async def get_config(action_id: str) -> Optional[dict]:
    return await db.other_action_configs.find_one({"action_id": action_id}, {"_id": 0})


async def dispatch_other_action(
    action_id: str,
    template_vars: dict,
    current_user: Optional[dict] = None,
    fallback_subject: str = "",
    executive_user_id: Optional[str] = None,
    extra_cc: Optional[list] = None,
    project: Optional[dict] = None,
) -> dict:
    """Despacha la acción según la config dinámica. Ver reglas en el docstring
    del módulo.

    `extra_cc`: lista opcional de correos a incluir en COPIA (CC) en CADA envío
    por email (p.ej. el "Correo Adicional Eventual" de un Proyecto de Integración).
    No altera los destinatarios configurados; solo se añade en copia.

    `project`: documento del proyecto que detona el evento. Necesario para resolver
    el destinatario dinámico "Usuario Implementador" (type='project_implementer').
    """
    extra_cc = [e for e in (extra_cc or []) if e and isinstance(e, str) and '@' in e]
    cfg = await get_config(action_id)
    if not cfg:
        return {"dispatched": False, "reason": "no_config"}

    # Toggle global de la acción: si está desactivada, no sale ningún correo.
    if not cfg.get("enabled", True):
        logger.info(f"[other-actions] '{action_id}' desactivada — no se envía nada")
        return {"dispatched": True, "disabled": True, "sent_count": 0}

    recipients = cfg.get("recipients") or []
    if not recipients:
        # Config existe pero sin filas: tratar como "no configurado" → fallback.
        return {"dispatched": False, "reason": "no_recipients"}

    sent_count = 0
    sent_to: list[str] = []
    skipped: list[dict] = []

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
        else:
            skipped.append({"row_id": row.get("row_id"), "reason": f"tipo no soportado: {rtype}"})
            continue

        tpl = await _load_template(row.get("template_id"))
        if not tpl:
            skipped.append({"row_id": row.get("row_id"), "reason": "Plantilla no encontrada"})
            continue

        if "Firma_Notificacion_Global" not in template_vars:
            from services.signature import build_signature_html
            template_vars["Firma_Notificacion_Global"] = await build_signature_html(current_user)

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
                )
            else:
                await send_email(
                    to=[rcpt_email],
                    subject=subject or fallback_subject or "Notificación",
                    html=body,
                    action=f"{action_id}_other",
                    cc=extra_cc or None,
                )
            sent_count += 1
            sent_to.append(rcpt_email)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[other-actions] Error enviando a {rcpt_email} (channel={channel}): {e}")
            skipped.append({"row_id": row.get("row_id"), "reason": str(e)})

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
