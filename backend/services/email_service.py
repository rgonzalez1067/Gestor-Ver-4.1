"""
Servicio de correo electrónico con motor SMTP propio.
Prioridad: SMTP propio > Resend (fallback) > Simulado.
"""
import logging
import uuid
import smtplib
import asyncio
import time
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


# ==================== FOOTER GLOBAL (cache ligero) ====================

_FOOTER_CACHE = {"body_html": None, "fetched_at": 0.0}
_FOOTER_TTL_SECONDS = 60


def invalidate_footer_cache() -> None:
    """Limpia el caché en memoria del footer global (llamado al guardar)."""
    _FOOTER_CACHE["body_html"] = None
    _FOOTER_CACHE["fetched_at"] = 0.0


async def _get_global_footer_html() -> str:
    """Devuelve el footer global (con variables resueltas) listo para anexar al correo.

    Caché en memoria (~60s) para evitar golpear Mongo en cada envío.
    """
    now = time.time()
    cached = _FOOTER_CACHE["body_html"]
    if cached is not None and (now - _FOOTER_CACHE["fetched_at"]) < _FOOTER_TTL_SECONDS:
        return cached

    try:
        doc = await db.config.find_one({"type": "email_footer"}, {"_id": 0, "body_html": 1})
    except Exception as e:
        logger.warning(f"[Footer] Error leyendo footer global: {e}")
        doc = None

    body = (doc or {}).get("body_html", "") or ""
    if body:
        year = datetime.now(timezone.utc).strftime("%Y")
        body = (
            body.replace("{{año_actual}}", year)
            .replace("{{ano_actual}}", year)
            .replace("{{razon_social}}", "Mega Soft Computación, C.A.")
        )

    _FOOTER_CACHE["body_html"] = body
    _FOOTER_CACHE["fetched_at"] = now
    return body


# ==================== REMITENTES POR ÁREA (multi-sender) ====================

_SENDERS_CACHE = {"doc": None, "fetched_at": 0.0}
_SENDERS_TTL_SECONDS = 60


def invalidate_senders_cache() -> None:
    """Limpia el caché en memoria de la config de remitentes (al guardar)."""
    _SENDERS_CACHE["doc"] = None
    _SENDERS_CACHE["fetched_at"] = 0.0


async def _get_email_senders_config() -> dict:
    """Lee la config de remitentes (db.config type=email_senders) con caché ~60s."""
    now = time.time()
    cached = _SENDERS_CACHE["doc"]
    if cached is not None and (now - _SENDERS_CACHE["fetched_at"]) < _SENDERS_TTL_SECONDS:
        return cached
    try:
        doc = await db.config.find_one({"type": "email_senders"}, {"_id": 0}) or {}
    except Exception as e:
        logger.warning(f"[Senders] Error leyendo remitentes: {e}")
        doc = {}
    _SENDERS_CACHE["doc"] = doc
    _SENDERS_CACHE["fetched_at"] = now
    return doc


async def resolve_sender_for_area(area: str) -> str:
    """Devuelve el correo remitente configurado para un área (p.ej. 'proyectos',
    'integradores'). Si no hay asignación válida/activa, retorna el remitente
    institucional por defecto (SENDER_EMAIL)."""
    try:
        doc = await _get_email_senders_config()
        active_emails = {
            (s.get("email") or "").strip().lower()
            for s in doc.get("senders", [])
            if s.get("active", True) and s.get("email")
        }
        assigned = ((doc.get("assignments") or {}).get(area) or "").strip()
        if assigned and assigned.lower() in active_emails:
            return assigned
    except Exception as e:
        logger.warning(f"[Senders] No se pudo resolver remitente para '{area}': {e}")
    return SENDER_EMAIL


async def resolve_sender_for_quote(quote: dict) -> str:
    """Remitente para correos del módulo de Cotizaciones, según el segmento del
    cliente: Corporativo → área 'cotizaciones_corp'; PYME → 'cotizaciones_pyme'."""
    segment = ""
    if isinstance(quote, dict):
        segment = (quote.get("client_segment") or "").strip().upper()
    area = "cotizaciones_corp" if segment == "CORP" else "cotizaciones_pyme"
    return await resolve_sender_for_area(area)


def _append_footer_to_html(html: str, footer_html: str) -> str:
    """Anexa el footer global al final del cuerpo HTML, manteniendo integridad visual."""
    if not footer_html:
        return html
    wrapper = (
        '<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;'
        'font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#64748b;line-height:1.5;">'
        f'{footer_html}'
        '</div>'
    )
    # Insertar antes de </body> si existe, sino al final
    if "</body>" in html.lower():
        import re
        return re.sub(r"</body>", wrapper + "</body>", html, count=1, flags=re.IGNORECASE)
    return html + wrapper


def _send_smtp(
    to: List[str],
    subject: str,
    html: str,
    sender: str,
    attachments: list = None,
    cc: List[str] = None,
) -> dict:
    """Envío síncrono vía SMTP (se ejecuta en thread aparte)."""
    msg = MIMEMultipart("mixed")
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)

    # Cuerpo HTML
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Adjuntos (compatible con formato Resend: {filename, content})
    # content puede ser: base64 string (de Resend) o bytes crudos
    if attachments:
        for att in attachments:
            part = MIMEBase("application", "octet-stream")
            content = att.get("content", b"")
            if isinstance(content, str):
                # Viene como base64 string (formato Resend) → decodificar a bytes
                import base64
                try:
                    content = base64.b64decode(content)
                except Exception:
                    content = content.encode("utf-8")
            part.set_payload(content)
            encoders.encode_base64(part)
            # Usar keyword arg para filename (maneja caracteres especiales/unicode correctamente)
            fname = att.get("filename", "adjunto")
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)

    # All recipients for sendmail (TO + CC)
    all_recipients = list(to) + (cc or [])

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(sender, all_recipients, msg.as_string())

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
    cc: List[str] = None,
) -> dict:
    """
    Envía un email con soporte para CC.
    Prioridad: 1) SMTP propio  2) Resend  3) Simulado.
    """
    sender = sender or SENDER_EMAIL
    # Filter empty emails
    to = [e for e in to if e and e.strip() and '@' in e]
    cc = [e for e in (cc or []) if e and e.strip() and '@' in e]

    # Anexar footer global institucional al final del HTML (si hay configurado)
    try:
        footer_html = await _get_global_footer_html()
        if footer_html:
            html = _append_footer_to_html(html, footer_html)
    except Exception as e:
        logger.warning(f"[Footer] No se pudo anexar footer global: {e}")

    email_log = {
        "email_log_id": f"eml_{uuid.uuid4().hex[:12]}",
        "action": action,
        "quote_id": quote_id,
        "quote_number": quote_number,
        "from": sender,
        "to": to,
        "cc": cc,
        "subject": subject,
        "html_preview": html[:500],
        "has_attachment": bool(attachments),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # ---- 1) Motor SMTP propio (prioridad) ----
    if SMTP_AVAILABLE:
        try:
            result = await asyncio.to_thread(
                _send_smtp, to, subject, html, sender, attachments, cc
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
