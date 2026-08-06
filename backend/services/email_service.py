"""
Servicio de correo electrónico con motor SMTP propio.
Prioridad: SMTP propio > Resend (fallback) > Simulado.
"""
import logging
import os
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


def normalize_email_html(html: str) -> str:
    """Homologa el espaciado del correo con la Vista Previa de la app.

    Los clientes de correo (Gmail) aplican márgenes grandes por defecto a los
    párrafos <p>, por lo que el correo recibido se ve con más espacio entre
    líneas que la Vista Previa (que usa CSS compacto). Aquí inyectamos estilos
    en línea compactos en cada <p> y envolvemos el cuerpo con la tipografía
    base, replicando exactamente la clase .email-render del frontend.
    """
    import re
    if not html or "<" not in html:
        return html

    def style_p(m):
        attrs = m.group(1) or ""
        if "margin" in attrs.lower():
            return m.group(0)
        if re.search(r'style\s*=\s*["\']', attrs, re.IGNORECASE):
            new_attrs = re.sub(
                r'(style\s*=\s*["\'])',
                r'\1margin:0 0 10px 0;line-height:1.5;',
                attrs, count=1, flags=re.IGNORECASE,
            )
            return f"<p{new_attrs}>"
        return f'<p{attrs} style="margin:0 0 10px 0;line-height:1.5;">'

    body = re.sub(r"<p([^>]*)>", style_p, html, flags=re.IGNORECASE)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        'line-height:1.5;color:#1f2937;">' + body + "</div>"
    )


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
    bcc: List[str] = None,
    reply_to: str = None,
) -> dict:
    """Envío síncrono vía SMTP (se ejecuta en thread aparte)."""
    msg = MIMEMultipart("mixed")
    msg["From"] = sender
    msg["To"] = ", ".join(to) if to else sender
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    if cc:
        msg["Cc"] = ", ".join(cc)

    # Cuerpo HTML + imágenes inline (CID) dentro de un contenedor multipart/related.
    inline_atts = [a for a in (attachments or []) if a.get("content_id")]
    regular_atts = [a for a in (attachments or []) if not a.get("content_id")]
    if inline_atts:
        from email.mime.image import MIMEImage
        related = MIMEMultipart("related")
        related.attach(MIMEText(html, "html", "utf-8"))
        for att in inline_atts:
            content = att.get("content", b"")
            if isinstance(content, str):
                import base64
                try:
                    content = base64.b64decode(content)
                except Exception:
                    content = content.encode("utf-8")
            _subtype = (att.get("content_type", "") or "image/png").split("/")[-1] or "png"
            try:
                img = MIMEImage(content, _subtype=_subtype)
            except Exception:
                img = MIMEImage(content, _subtype="png")
            img.add_header("Content-ID", f"<{att['content_id']}>")
            img.add_header("Content-Disposition", "inline", filename=att.get("filename", "logo"))
            related.attach(img)
        msg.attach(related)
    else:
        msg.attach(MIMEText(html, "html", "utf-8"))

    # Adjuntos (compatible con formato Resend: {filename, content})
    # content puede ser: base64 string (de Resend) o bytes crudos
    if regular_atts:
        for att in regular_atts:
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

    # All recipients for sendmail (TO + CC + BCC). El Bcc NO se agrega como cabecera
    # para preservar la privacidad: los destinatarios en copia oculta no se ven entre sí.
    all_recipients = list(to) + (cc or []) + (bcc or [])

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(sender, all_recipients, msg.as_string())

    return {"status": "sent", "method": "smtp"}


def _is_mail_hosted_img(url: str) -> bool:
    """Detecta imágenes alojadas en un buzón de correo (requieren sesión y NO se
    pueden descargar/incrustar): Gmail, Outlook/OWA, googleusercontent fimg."""
    u = (url or "").lower()
    return (
        "mail.google.com" in u
        or ("googleusercontent.com" in u and ("view=fimg" in u or "attid=" in u))
        or "outlook.live.com" in u
        or "outlook.office" in u
        or "/owa/" in u
    )



async def _download_img_bytes(url: str, ctype_default: str, fname_default: str):
    """Descarga los bytes de una imagen remota. Devuelve (content, ctype, fname)
    o (None, ctype, fname) si falla (p.ej. requiere autenticación: mail.google.com)."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as _cli:
            r = await _cli.get(url)
        if r.status_code == 200 and r.content and (r.headers.get("content-type", "")).lower().startswith("image"):
            ctype = (r.headers.get("content-type") or ctype_default).split(";")[0].strip() or ctype_default
            fname = (url.rsplit("/", 1)[-1].split("?", 1)[0]) or fname_default
            return r.content, ctype, fname
        logger.warning(f"[BodyImg] descarga no-imagen/{r.status_code}: {url[:80]}")
    except Exception as e:
        logger.warning(f"[BodyImg] descarga falló {url[:80]}: {e}")
    return None, ctype_default, fname_default


async def _embed_body_images(html: str, attachments: list) -> tuple:
    """Convierte las imágenes del cuerpo (URLs servidas por nuestro backend o data URIs)
    en adjuntos inline CID, para que se visualicen en cualquier cliente de correo
    (Outlook/Gmail bloquean las imágenes remotas o no las cargan)."""
    import re
    import base64
    if not html or "<img" not in html.lower():
        return html, attachments
    atts = list(attachments) if attachments else []
    pattern = re.compile(r'<img\b[^>]*?\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
    base_url = (os.environ.get("REACT_APP_BACKEND_URL", "") or "").rstrip("/")
    replacements = {}
    remove_srcs = []  # imágenes remotas no incrustables (auth-gated) → se eliminan
    for m in pattern.finditer(html):
        src = m.group(1)
        if src.startswith("cid:") or src in replacements or src in remove_srcs:
            continue
        content = None
        ctype = "image/png"
        fname = "imagen.png"
        # Decodifica entidades HTML del src (&amp; → &) para poder descargar/leer.
        dec_src = src.replace("&amp;", "&").replace("&#38;", "&")
        # Normaliza rutas RELATIVAS a absolutas (Conversión Forzosa): el editor o
        # una plantilla legacy pueden guardar src="/api/projects/images/..." o
        # "/media/...". Los clientes de correo no resuelven rutas sin dominio.
        abs_src = dec_src
        if dec_src.startswith("/") and not dec_src.startswith("//"):
            abs_src = f"{base_url}{dec_src}" if base_url else dec_src
        if dec_src.startswith("data:image/"):
            try:
                header, b64 = dec_src.split(",", 1)
                ctype = header.split(":", 1)[1].split(";", 1)[0]
                content = base64.b64decode(b64)
                fname = f"imagen.{ctype.split('/')[-1]}"
            except Exception:
                continue
        elif "/api/projects/images/" in dec_src:
            # Imagen hospedada por nuestro backend (relativa o absoluta, cualquier
            # dominio) → leer bytes directo de object storage por su image_id.
            try:
                tail = dec_src.split("/api/projects/images/", 1)[1].split("?", 1)[0]
                file_id = tail.split(".", 1)[0]
                rec = await db.uploaded_images.find_one({"image_id": file_id}, {"_id": 0})
                if rec:
                    from services.object_storage import get_object
                    content, ct = await asyncio.to_thread(get_object, rec["storage_path"])
                    ctype = rec.get("content_type") or ct or "image/png"
                    fname = rec.get("original_filename") or tail
            except Exception as e:
                logger.warning(f"[BodyImg] storage lookup falló {src}: {e}")
            if content is None and (abs_src.startswith("http://") or abs_src.startswith("https://")):
                content, ctype, fname = await _download_img_bytes(abs_src, ctype, fname)
            if content is None:
                continue
        elif abs_src.startswith("http://") or abs_src.startswith("https://"):
            # Imágenes autenticadas de correo (Gmail/Outlook): no se pueden obtener
            # (requieren sesión). Marcar para eliminar el <img> sin intentar descargar.
            if _is_mail_hosted_img(abs_src):
                remove_srcs.append(src)
                continue
            # Cualquier otro origen (incluye relativas ya absolutizadas) → descargar.
            content, ctype, fname = await _download_img_bytes(abs_src, ctype, fname)
            if content is None:
                continue
        else:
            continue
        if not content:
            continue
        cid = f"bodyimg_{uuid.uuid4().hex[:10]}"
        replacements[src] = cid
        atts.append({
            "filename": fname,
            "content": content,
            "content_id": cid,
            "inline": True,
            "content_type": ctype,
        })
    for src, cid in replacements.items():
        # Reemplazo acotado por comillas para evitar colisiones de substring
        # (una ruta relativa puede ser substring de una URL absoluta equivalente).
        html = html.replace(f'"{src}"', f'"cid:{cid}"').replace(f"'{src}'", f"'cid:{cid}'")
    # Eliminar las etiquetas <img> de imágenes de correo no incrustables.
    for bad in remove_srcs:
        html = re.sub(r'<img\b[^>]*?\bsrc=["\']' + re.escape(bad) + r'["\'][^>]*>', '', html, flags=re.IGNORECASE)
    return html, atts


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
    bcc: List[str] = None,
    reply_to: str = None,
) -> dict:
    """
    Envía un email con soporte para CC y BCC (copia oculta).
    Prioridad: 1) SMTP propio  2) Resend  3) Simulado.
    """
    sender = sender or SENDER_EMAIL
    # Reply-To: por defecto igual al remitente (From), para que las respuestas
    # del destinatario lleguen a la cuenta configurada por área.
    reply_to = reply_to or sender
    # Filter empty emails
    to = [e for e in to if e and e.strip() and '@' in e]
    cc = [e for e in (cc or []) if e and e.strip() and '@' in e]
    bcc = [e for e in (bcc or []) if e and e.strip() and '@' in e]

    # Homologar el espaciado del cuerpo con la Vista Previa (márgenes compactos
    # en <p>) antes de anexar el footer y enviar.
    try:
        html = normalize_email_html(html)
    except Exception as e:
        logger.warning(f"[Normalize] No se pudo normalizar el HTML del correo: {e}")

    # Anexar footer global institucional al final del HTML (si hay configurado)
    try:
        footer_html = await _get_global_footer_html()
        if footer_html:
            html = _append_footer_to_html(html, footer_html)
    except Exception as e:
        logger.warning(f"[Footer] No se pudo anexar footer global: {e}")

    # Logo de firma incrustado (CID): si el HTML referencia cid:firma_logo, adjuntar el
    # archivo del logo como imagen inline para que se vea en cualquier cliente de correo.
    try:
        if "cid:firma_logo" in (html or ""):
            from services.signature import get_footer_logo_file
            logo_file = get_footer_logo_file()
            if logo_file:
                import mimetypes
                inline_logo = {
                    "filename": logo_file.name,
                    "content": logo_file.read_bytes(),
                    "content_id": "firma_logo",
                    "inline": True,
                    "content_type": mimetypes.guess_type(str(logo_file))[0] or "image/png",
                }
                attachments = ([inline_logo] + list(attachments)) if attachments else [inline_logo]
    except Exception as e:
        logger.warning(f"[Firma] No se pudo adjuntar el logo inline (CID): {e}")

    # Imágenes del cuerpo (pegadas en plantillas) → incrustar como CID inline para que
    # se visualicen en el correo (Outlook/Gmail bloquean o no cargan imágenes remotas).
    try:
        html, attachments = await _embed_body_images(html, attachments)
    except Exception as e:
        logger.warning(f"[BodyImg] No se pudieron incrustar las imágenes del cuerpo: {e}")

    email_log = {
        "email_log_id": f"eml_{uuid.uuid4().hex[:12]}",
        "action": action,
        "quote_id": quote_id,
        "quote_number": quote_number,
        "from": sender,
        "reply_to": reply_to,
        "to": to,
        "cc": cc,
        "bcc_count": len(bcc),
        "subject": subject,
        "html_preview": html[:500],
        "has_attachment": bool(attachments),
        "attachment_count": len(attachments or []),
        "attachment_names": [a.get("filename") for a in (attachments or [])],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # ---- 1) Motor SMTP propio (prioridad) ----
    if SMTP_AVAILABLE:
        try:
            result = await asyncio.to_thread(
                _send_smtp, to, subject, html, sender, attachments, cc, bcc, reply_to
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
                params = {"from": sender, "to": to or [sender], "subject": subject, "html": html}
                if reply_to:
                    params["reply_to"] = reply_to
                if bcc:
                    params["bcc"] = bcc
                if attachments:
                    import base64 as _b64
                    rs_atts = []
                    for att in attachments:
                        content = att.get("content", b"")
                        if isinstance(content, (bytes, bytearray)):
                            content = _b64.b64encode(content).decode("ascii")
                        item = {"filename": att.get("filename", "adjunto"), "content": content}
                        if att.get("content_id"):
                            item["content_id"] = att["content_id"]
                            item["content_type"] = att.get("content_type", "image/png")
                            item["disposition"] = "inline"
                        rs_atts.append(item)
                    params["attachments"] = rs_atts
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
