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

logger = logging.getLogger("other_actions_engine")


async def get_config(action_id: str) -> Optional[dict]:
    return await db.other_action_configs.find_one({"action_id": action_id}, {"_id": 0})


async def dispatch_other_action(
    action_id: str,
    template_vars: dict,
    current_user: Optional[dict] = None,
    fallback_subject: str = "",
) -> dict:
    """Despacha la acción según la config dinámica. Ver reglas en el docstring
    del módulo."""
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
        if row.get("type") != "user":
            skipped.append({"row_id": row.get("row_id"), "reason": f"tipo no soportado: {row.get('type')}"})
            continue
        resolved = await _resolve_user_email(row.get("user_id", ""))
        if not resolved:
            skipped.append({"row_id": row.get("row_id"), "reason": "Usuario no encontrado o inactivo"})
            continue
        rcpt_email, rcpt_name = resolved

        tpl = await _load_template(row.get("template_id"))
        if not tpl:
            skipped.append({"row_id": row.get("row_id"), "reason": "Plantilla no encontrada"})
            continue

        subject = _render(tpl.get("subject", ""), template_vars) or fallback_subject
        body = _render(tpl.get("body_html", "") or tpl.get("body", ""), template_vars)

        channel = (row.get("delivery_channel") or "email").lower()
        try:
            if channel == "inbox":
                await deliver_to_inbox(
                    user_id=row.get("user_id"),
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
            "skipped": skipped,
            "executed_by": (current_user or {}).get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    logger.info(f"[other-actions] {action_id} dispatched: sent={sent_count}, skipped={len(skipped)}")
    return {"dispatched": True, "disabled": False, "sent_count": sent_count, "recipients": sent_to, "skipped": skipped}
