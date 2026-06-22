"""Firma Institucional Global para correos/notificaciones.

Compila la variable dinámica {Firma_Notificacion_Global}: un bloque HTML de pie
de firma que combina constantes institucionales (Mega Soft Computación, C.A.),
el logo cargado en Configuración ("Logotipo para Pie de Notificaciones") y los
datos del usuario que detona la acción (nombre, email, teléfono), resueltos en
tiempo de ejecución.
"""
import os
import time
import logging

from config import db, UPLOADS_DIR

logger = logging.getLogger(__name__)

# Content-ID usado para incrustar el logo inline en el correo (independiente del entorno).
CID_FIRMA_LOGO = "firma_logo"

# Constantes institucionales (Texto fijo)
_RAZON_SOCIAL = "Mega Soft Computación, C.A."
_RIF = "J-00343075-7"
_CIUDAD = "Caracas - Venezuela"
_WEB_LABEL = "www.megasoft.com.ve"
_WEB_URL = "https://www.megasoft.com.ve"

# Nombre por defecto cuando NO hay un humano que detona (ej. SLAs automáticos)
DEFAULT_ACTOR_NAME = "CRM - Gestor"

_LOGO_CACHE = {"url": None, "fetched_at": 0.0}
_LOGO_TTL = 60.0


def invalidate_signature_logo_cache():
    _LOGO_CACHE["url"] = None
    _LOGO_CACHE["fetched_at"] = 0.0


def get_footer_logo_file():
    """Path del archivo de logo de pie cargado en Configuración (o None).
    Se lee directamente de disco para no depender de URLs/variables de entorno."""
    try:
        for f in UPLOADS_DIR.glob("notif_logo.*"):
            return f
    except Exception as e:
        logger.warning(f"[Firma] Error localizando logo: {e}")
    return None


async def _get_footer_logo_url() -> str:
    """URL pública del logo de pie de notificaciones (o '' si no hay)."""
    now = time.time()
    if _LOGO_CACHE["url"] is not None and (now - _LOGO_CACHE["fetched_at"]) < _LOGO_TTL:
        return _LOGO_CACHE["url"]
    url = ""
    try:
        doc = await db.config.find_one({"type": "notification_footer_logo"}, {"_id": 0, "filename": 1})
        if doc and doc.get("filename"):
            base = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
            if base:
                url = f"{base}/api/config/notification-logo"
    except Exception as e:
        logger.warning(f"[Firma] Error leyendo logo de firma: {e}")
    _LOGO_CACHE["url"] = url
    _LOGO_CACHE["fetched_at"] = now
    return url


async def build_signature_html(user: dict = None) -> str:
    """Construye el bloque HTML de la firma institucional.

    `user`: dict del usuario que detona (con first_name/last_name/email/phone).
    Si es None (flujos automáticos), usa DEFAULT_ACTOR_NAME y omite email/teléfono.
    """
    name = DEFAULT_ACTOR_NAME
    email = ""
    phone = ""
    if user:
        nm = f"{user.get('first_name', '') or ''} {user.get('last_name', '') or ''}".strip()
        name = nm or user.get("name") or DEFAULT_ACTOR_NAME
        email = (user.get("email") or "").strip()
        phone = (user.get("phone") or "").strip()

    # Logo incrustado vía CID (cid:firma_logo) -> visible en Gmail/Outlook sin depender
    # de URLs públicas/variables de entorno. El adjunto inline lo agrega send_email().
    logo_html = (
        f'<img src="cid:{CID_FIRMA_LOGO}" alt="Mega Soft Computación" '
        f'style="max-height:52px;width:auto;margin-bottom:10px;display:block;" />'
        if get_footer_logo_file() else ""
    )

    rows = [f'<div style="font-weight:700;color:#111827;font-size:14px;">{name}</div>']
    rows.append(f'<div style="color:#374151;font-weight:600;">{_RAZON_SOCIAL}</div>')
    rows.append(f'<div style="color:#6b7280;">Rif: {_RIF}</div>')
    rows.append(f'<div style="color:#6b7280;">{_CIUDAD}</div>')
    if email:
        rows.append(f'<div style="color:#6b7280;">Email: {email}</div>')
    if phone:
        rows.append(f'<div style="color:#6b7280;">Telf: {phone}</div>')
    rows.append(
        f'<div style="color:#6b7280;">Web Site: '
        f'<a href="{_WEB_URL}" style="color:#2563eb;text-decoration:none;">{_WEB_LABEL}</a></div>'
    )

    return (
        '<div style="margin-top:20px;padding-top:12px;border-top:1px solid #e5e7eb;'
        'font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.6;">'
        f'{logo_html}{"".join(rows)}</div>'
    )
