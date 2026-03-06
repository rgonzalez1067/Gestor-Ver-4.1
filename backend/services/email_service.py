"""
Servicio de correo electrónico con modo simulado.
Si Resend está configurado, envía correos reales.
Si no, registra correos simulados en la BD.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from config import db, RESEND_AVAILABLE, SENDER_EMAIL, get_resend_api_key

logger = logging.getLogger(__name__)

try:
    import resend
except ImportError:
    pass


async def send_email(
    to: List[str],
    subject: str,
    html: str,
    action: str = "general",
    quote_id: str = None,
    quote_number: str = None,
    attachments: list = None,
    sender: str = None,
) -> dict:
    """
    Envía un email real o simulado.
    Retorna dict con status ('sent', 'simulated', 'error'), message, y email_log_id.
    """
    sender = sender or SENDER_EMAIL
    email_log = {
        "email_log_id": f"eml_{uuid.uuid4().hex[:12]}",
        "action": action,
        "quote_id": quote_id,
        "quote_number": quote_number,
        "from": sender,
        "to": to,
        "subject": subject,
        "html_preview": html[:500],
        "has_attachment": bool(attachments),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Intentar envío real
    if RESEND_AVAILABLE:
        try:
            api_key = await get_resend_api_key()
            if api_key:
                resend.api_key = api_key
                params = {
                    "from": sender,
                    "to": to,
                    "subject": subject,
                    "html": html,
                }
                if attachments:
                    params["attachments"] = attachments

                import asyncio
                result = await asyncio.to_thread(resend.Emails.send, params)

                email_log["status"] = "sent"
                email_log["resend_id"] = result.get("id") if isinstance(result, dict) else str(result)
                log_copy = {k: v for k, v in email_log.items() if k != "_id"}
                await db.email_logs.insert_one(log_copy)

                return {
                    "status": "sent",
                    "message": f"Email enviado a {', '.join(to)}",
                    "email_log_id": email_log["email_log_id"],
                }
        except Exception as e:
            logger.error(f"Error enviando email real: {e}")
            email_log["status"] = "error"
            email_log["error"] = str(e)
            log_copy = {k: v for k, v in email_log.items() if k != "_id"}
            await db.email_logs.insert_one(log_copy)
            # Fall through to simulation

    # Modo simulado
    email_log["status"] = "simulated"
    log_copy = {k: v for k, v in email_log.items() if k != "_id"}
    await db.email_logs.insert_one(log_copy)
    logger.info(f"[EMAIL SIMULADO] To: {to} | Subject: {subject} | Action: {action}")

    return {
        "status": "simulated",
        "message": f"Email simulado a {', '.join(to)}",
        "email_log_id": email_log["email_log_id"],
        "simulated": True,
    }
