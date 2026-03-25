"""
Servicio de correo electrónico con motor SMTP propio.
Prioridad: SMTP propio > Resend (fallback) > Simulado.
"""
import logging
import uuid
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from typing import Optional, List

from config import (
    db, SENDER_EMAIL,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_AVAILABLE,
    RESEND_AVAILABLE, get_resend_api_key,
)

logger = logging.getLogger(__name__)

try:
    import resend
except ImportError:
    pass


def _send_smtp(
    to: List[str],
    subject: str,
    html: str,
    sender: str,
    attachments: list = None,
) -> dict:
    """Envío síncrono vía SMTP (se ejecuta en thread aparte)."""
    msg = MIMEMultipart("mixed")
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject

    # Cuerpo HTML
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Adjuntos (compatible con formato Resend: {filename, content})
    if attachments:
        for att in attachments:
            part = MIMEBase("application", "octet-stream")
            content = att.get("content", b"")
            if isinstance(content, str):
                content = content.encode("utf-8")
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{att.get("filename", "adjunto")}"')
            msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(sender, to, msg.as_string())

    return {"status": "sent", "method": "smtp"}


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
    Envía un email.
    Prioridad: 1) SMTP propio  2) Resend  3) Simulado.
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

    # ---- 1) Motor SMTP propio (prioridad) ----
    if SMTP_AVAILABLE:
        try:
            result = await asyncio.to_thread(
                _send_smtp, to, subject, html, sender, attachments
            )
            email_log["status"] = "sent"
            email_log["method"] = "smtp"
            log_copy = {k: v for k, v in email_log.items() if k != "_id"}
            await db.email_logs.insert_one(log_copy)
            logger.info(f"[SMTP] Email enviado a {to} | Subject: {subject}")
            return {
                "status": "sent",
                "message": f"Email enviado a {', '.join(to)}",
                "email_log_id": email_log["email_log_id"],
                "method": "smtp",
            }
        except Exception as e:
            logger.error(f"[SMTP] Error: {e}")
            email_log["smtp_error"] = str(e)
            # Fall through to Resend

    # ---- 2) Resend (fallback) ----
    if RESEND_AVAILABLE:
        try:
            api_key = await get_resend_api_key()
            if api_key:
                resend.api_key = api_key
                params = {"from": sender, "to": to, "subject": subject, "html": html}
                if attachments:
                    params["attachments"] = attachments
                result = await asyncio.to_thread(resend.Emails.send, params)
                email_log["status"] = "sent"
                email_log["method"] = "resend"
                email_log["resend_id"] = result.get("id") if isinstance(result, dict) else str(result)
                log_copy = {k: v for k, v in email_log.items() if k != "_id"}
                await db.email_logs.insert_one(log_copy)
                return {
                    "status": "sent",
                    "message": f"Email enviado a {', '.join(to)}",
                    "email_log_id": email_log["email_log_id"],
                    "method": "resend",
                }
        except Exception as e:
            logger.error(f"[Resend] Error: {e}")
            email_log["resend_error"] = str(e)

    # ---- 3) Modo simulado ----
    email_log["status"] = "simulated"
    email_log["method"] = "simulated"
    log_copy = {k: v for k, v in email_log.items() if k != "_id"}
    await db.email_logs.insert_one(log_copy)
    logger.info(f"[EMAIL SIMULADO] To: {to} | Subject: {subject} | Action: {action}")

    return {
        "status": "simulated",
        "message": f"Email simulado a {', '.join(to)}",
        "email_log_id": email_log["email_log_id"],
        "simulated": True,
    }
