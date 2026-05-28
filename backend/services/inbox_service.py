"""Centro de Mensajes — bandeja interna del usuario.

Análogo a `email_service.send_email()` pero persiste el mensaje en la
colección `inbox_messages` para que el usuario lo vea en su Dashboard,
sin pasar por SMTP/Resend.

Se respeta el footer global institucional (parida visual con correo).

Documento canónico:
{
  message_id: str,
  user_id: str,            # destinatario
  recipient_email: str,    # email histórico (snapshot, NO se usa para envío)
  recipient_name: str,
  subject: str,
  body_html: str,          # HTML completo con footer ya anexado
  action_id: str | None,
  quote_id: str | None,
  quote_number: str | None,
  project_id: str | None,
  created_at: str (ISO),
  read_at: str | None,     # ISO cuando el usuario abre/expande
  deleted_at: str | None,  # soft delete; se filtra en GET
  attachments_meta: [      # solo metadatos (filename, size). No guardamos blobs.
    {filename, size_bytes}
  ]
}
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import db
from services.email_service import _get_global_footer_html, _append_footer_to_html

logger = logging.getLogger(__name__)


async def deliver_to_inbox(
    *,
    user_id: str,
    recipient_email: str,
    recipient_name: str,
    subject: str,
    html: str,
    action_id: Optional[str] = None,
    quote_id: Optional[str] = None,
    quote_number: Optional[str] = None,
    project_id: Optional[str] = None,
    attachments: Optional[list[dict]] = None,
) -> dict:
    """Inserta un mensaje en la bandeja interna del usuario.

    Devuelve `{status, message_id}`. Aplica el footer global para mantener
    paridad visual con los correos. Los adjuntos NO se guardan como blobs
    (se conserva sólo metadatos `filename` + `size_bytes` para mostrar al
    usuario que la acción originalmente llevaba adjuntos).
    """
    if not user_id:
        logger.warning("[Inbox] user_id vacío, no se inserta mensaje")
        return {"status": "skipped", "reason": "no_user_id"}

    # Anexar footer global (mismo HTML que el correo)
    try:
        footer_html = await _get_global_footer_html()
        if footer_html:
            html = _append_footer_to_html(html, footer_html)
    except Exception as e:
        logger.warning(f"[Inbox] Footer no anexado: {e}")

    attachments_meta = []
    for att in (attachments or []):
        content = att.get("content")
        size = 0
        if isinstance(content, (bytes, bytearray)):
            size = len(content)
        elif isinstance(content, str):
            # base64 string aprox bytes
            size = int(len(content) * 3 / 4)
        attachments_meta.append({
            "filename": att.get("filename", "adjunto"),
            "size_bytes": size,
        })

    msg = {
        "message_id": f"inbox_{uuid.uuid4().hex[:14]}",
        "user_id": user_id,
        "recipient_email": recipient_email or "",
        "recipient_name": recipient_name or "",
        "subject": subject or "(sin asunto)",
        "body_html": html or "",
        "action_id": action_id,
        "quote_id": quote_id,
        "quote_number": quote_number,
        "project_id": project_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_at": None,
        "deleted_at": None,
        "attachments_meta": attachments_meta,
    }
    await db.inbox_messages.insert_one(msg)
    logger.info(
        f"[Inbox] msg {msg['message_id']} → user={user_id} subject='{subject[:60]}' action={action_id}"
    )
    return {
        "status": "delivered",
        "method": "inbox",
        "message_id": msg["message_id"],
    }
