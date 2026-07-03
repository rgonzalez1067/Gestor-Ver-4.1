"""Route module: settings.py"""
# ruff: noqa: F403, F405
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template
from models import *
import shutil

router = APIRouter()

# ==================== CONFIGURATION ENDPOINTS ====================

class SedeEmails(BaseModel):
    admin: Optional[EmailStr] = None
    warehouse: Optional[EmailStr] = None
    sales: Optional[EmailStr] = None

class EmailsBySede(BaseModel):
    PYME: Optional[SedeEmails] = None
    CORP: Optional[SedeEmails] = None

class AppSettings(BaseModel):
    implementation_email: Optional[EmailStr] = None
    implementation_manager_email: Optional[EmailStr] = None  # Correo Gerente de Implementación
    admin_email: Optional[EmailStr] = None  # LEGACY
    warehouse_email: Optional[EmailStr] = None  # LEGACY
    emails_by_sede: Optional[dict] = None
    resend_api_key: Optional[str] = None

@router.get("/config/settings")
async def get_app_settings(authorization: Optional[str] = Header(None)):
    """Obtiene la configuración general de la aplicación"""
    await get_current_user(authorization)
    
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    if not config:
        return {
            "implementation_email": None, 
            "admin_email": None, 
            "warehouse_email": None,
            "emails_by_sede": {
                "PYME": {"admin": "", "warehouse": "", "sales": ""},
                "CORP": {"admin": "", "warehouse": "", "sales": ""}
            },
            "resend_api_key_configured": False
        }
    
    # No devolver la API key completa por seguridad, solo indicar si está configurada
    resend_key = config.get("resend_api_key")
    resend_key_masked = None
    if resend_key:
        resend_key_masked = f"{'*' * (len(resend_key) - 4)}{resend_key[-4:]}" if len(resend_key) > 4 else "****"
    
    # Normalizar emails_by_sede para incluir siempre los campos esperados por la UI.
    # `operations` (solo PYME) es el buzón usado por flujos de logística como
    # Preasignación de Seriales. Si se omite, el frontend lo muestra vacío y el
    # admin pierde el valor al re-guardar otras secciones.
    raw_ebs = config.get("emails_by_sede", {})
    emails_by_sede = {}
    for sede_id in ["PYME", "CORP"]:
        sede_data = raw_ebs.get(sede_id, {})
        emails_by_sede[sede_id] = {
            "admin": sede_data.get("admin", config.get("admin_email", "") if sede_id == "PYME" else ""),
            "warehouse": sede_data.get("warehouse", config.get("warehouse_email", "") if sede_id == "PYME" else ""),
            "sales": sede_data.get("sales", ""),
            "operations": sede_data.get("operations", config.get("operations_email", "") if sede_id == "PYME" else ""),
        }
    
    return {
        "implementation_email": config.get("implementation_email"),
        "implementation_manager_email": config.get("implementation_manager_email"),
        "admin_email": config.get("admin_email"),
        "warehouse_email": config.get("warehouse_email"),
        "emails_by_sede": emails_by_sede,
        "resend_api_key_configured": bool(resend_key),
        "resend_api_key_masked": resend_key_masked
    }

@router.put("/config/settings")
async def update_app_settings(settings: AppSettings, authorization: Optional[str] = Header(None)):
    """Actualiza la configuración general de la aplicación"""
    global RESEND_API_KEY
    await get_current_user(authorization)
    
    update_data = {
        "type": "app_settings",
        "implementation_email": settings.implementation_email,
        "implementation_manager_email": settings.implementation_manager_email,
        "emails_by_sede": settings.emails_by_sede or {},
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Mantener compatibilidad con campos legacy
    if settings.admin_email:
        update_data["admin_email"] = settings.admin_email
    if settings.warehouse_email:
        update_data["warehouse_email"] = settings.warehouse_email
    
    # Solo actualizar resend_api_key si se proporciona un valor
    if settings.resend_api_key:
        update_data["resend_api_key"] = settings.resend_api_key
        RESEND_API_KEY = settings.resend_api_key
        if RESEND_AVAILABLE:
            resend.api_key = settings.resend_api_key
    
    await db.config.update_one(
        {"type": "app_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    return {
        "message": "Configuración actualizada",
        "implementation_email": settings.implementation_email,
        "emails_by_sede": settings.emails_by_sede,
        "resend_api_key_configured": bool(settings.resend_api_key)
    }


# ==================== EMAIL FOOTER GLOBAL ====================

class EmailFooterPayload(BaseModel):
    body_html: str = ""


def _resolve_footer_variables(body_html: str) -> str:
    """Reemplaza variables dinámicas soportadas en el footer global."""
    if not body_html:
        return ""
    year = datetime.now(timezone.utc).strftime("%Y")
    return (
        body_html
        .replace("{{año_actual}}", year)
        .replace("{{ano_actual}}", year)
        .replace("{{razon_social}}", "Mega Soft Computación, C.A.")
    )


@router.get("/config/email-footer")
async def get_email_footer(authorization: Optional[str] = Header(None)):
    """Obtiene el footer global que se adjunta automáticamente a todos los correos."""
    await get_current_user(authorization)
    doc = await db.config.find_one({"type": "email_footer"}, {"_id": 0})
    if not doc:
        return {"body_html": "", "updated_at": None, "updated_by": None}
    return {
        "body_html": doc.get("body_html", ""),
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


@router.put("/config/email-footer")
async def update_email_footer(
    payload: EmailFooterPayload,
    authorization: Optional[str] = Header(None),
):
    """Actualiza el footer global. Solo administradores."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar el footer global")

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    update_doc = {
        "type": "email_footer",
        "body_html": payload.body_html or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user_name,
    }
    await db.config.update_one(
        {"type": "email_footer"},
        {"$set": update_doc},
        upsert=True,
    )
    # Invalidar caché del servicio de correo
    try:
        from services.email_service import invalidate_footer_cache
        invalidate_footer_cache()
    except Exception:
        pass

    return {
        "message": "Footer global actualizado",
        "body_html": update_doc["body_html"],
        "updated_at": update_doc["updated_at"],
        "updated_by": update_doc["updated_by"],
    }


@router.post("/config/email-footer/preview")
async def preview_email_footer(
    payload: EmailFooterPayload,
    authorization: Optional[str] = Header(None),
):
    """Devuelve el footer con variables resueltas para vista previa."""
    await get_current_user(authorization)
    return {"html": _resolve_footer_variables(payload.body_html or "")}


# ==================== REMITENTES DE CORREO POR ÁREA (multi-sender) ====================

ALLOWED_SENDER_DOMAIN = SENDER_EMAIL.split("@")[-1] if "@" in SENDER_EMAIL else ""

# Áreas donde el remitente se fija automáticamente.
EMAIL_SENDER_AREAS = [
    {"key": "proyectos", "label": "Proyectos (notificaciones a Clientes/Bancos y Otras Notificaciones)"},
    {"key": "integradores", "label": "Integradores (comunicaciones a integradores)"},
    {"key": "cotizaciones_pyme", "label": "Cotizaciones PYME"},
    {"key": "cotizaciones_corp", "label": "Cotizaciones Corporativas"},
    {"key": "comunicaciones_clientes", "label": "Comunicaciones a Clientes"},
    {"key": "contactos_iniciales", "label": "Contactos Iniciales"},
    {"key": "nuevos_productos", "label": "Nuevos Productos"},
    {"key": "inventarios", "label": "Inventarios"},
]


class SenderItem(BaseModel):
    id: Optional[str] = None
    label: Optional[str] = None
    email: str
    active: bool = True


class EmailSendersPayload(BaseModel):
    senders: List[SenderItem] = []
    assignments: dict = {}


@router.get("/config/email-senders")
async def get_email_senders(authorization: Optional[str] = Header(None)):
    """Lista de remitentes disponibles + asignación por área. Default = SENDER_EMAIL."""
    await get_current_user(authorization)
    doc = await db.config.find_one({"type": "email_senders"}, {"_id": 0}) or {}
    return {
        "senders": doc.get("senders", []),
        "assignments": doc.get("assignments", {}),
        "default_sender": SENDER_EMAIL,
        "allowed_domain": ALLOWED_SENDER_DOMAIN,
        "areas": EMAIL_SENDER_AREAS,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


@router.put("/config/email-senders")
async def update_email_senders(payload: EmailSendersPayload, authorization: Optional[str] = Header(None)):
    """Guarda los remitentes y su asignación por área. Solo administradores.
    Restricción: todos los correos deben pertenecer al dominio institucional
    (mismo dominio que SENDER_EMAIL) para evitar rechazo por SPF/anti-spoofing."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden configurar los remitentes")

    cleaned = []
    seen = set()
    for s in payload.senders:
        email = (s.email or "").strip().lower()
        label = (s.label or "").strip()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail=f"Correo inválido: '{s.email}'")
        if ALLOWED_SENDER_DOMAIN and not email.endswith("@" + ALLOWED_SENDER_DOMAIN):
            raise HTTPException(status_code=400, detail=f"Solo se permiten correos del dominio @{ALLOWED_SENDER_DOMAIN}")
        if email in seen:
            continue
        seen.add(email)
        cleaned.append({
            "id": s.id or f"snd_{uuid.uuid4().hex[:8]}",
            "label": label or email,
            "email": email,
            "active": bool(s.active),
        })

    valid_emails = {c["email"] for c in cleaned if c["active"]}
    assignments = {}
    for area in EMAIL_SENDER_AREAS:
        k = area["key"]
        v = ((payload.assignments or {}).get(k) or "").strip().lower()
        if v and v in valid_emails:
            assignments[k] = v

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    update_doc = {
        "type": "email_senders",
        "senders": cleaned,
        "assignments": assignments,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": user_name,
    }
    await db.config.update_one({"type": "email_senders"}, {"$set": update_doc}, upsert=True)

    try:
        from services.email_service import invalidate_senders_cache
        invalidate_senders_cache()
    except Exception:
        pass

    return {
        "message": "Remitentes actualizados",
        "senders": cleaned,
        "assignments": assignments,
        "updated_at": update_doc["updated_at"],
        "updated_by": update_doc["updated_by"],
    }


# Endpoint para obtener plantillas de documentos por sede
@router.get("/config/document-templates")
async def get_document_templates(authorization: Optional[str] = Header(None)):
    """Obtiene el estado de las plantillas de documentos por sede"""
    await get_current_user(authorization)
    
    # Por ahora retornar estructura vacía - las plantillas se configurarán más adelante
    templates = {}
    template_types = ['despacho_equipos', 'cotizacion_aprobada', 'facturacion_control']
    sedes = ['PYME', 'CORP']
    
    for sede in sedes:
        for template_type in template_types:
            key = f"{template_type}_{sede}"
            templates[key] = {"exists": False, "configured_at": None}
    
    return templates

@router.post("/config/logo")
async def upload_logo(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'png'
    logo_path = UPLOADS_DIR / f"logo.{file_extension}"
    
    # Remove existing logo if exists
    for existing_logo in UPLOADS_DIR.glob("logo.*"):
        existing_logo.unlink()
    
    with open(logo_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"message": "Logo subido exitosamente", "filename": f"logo.{file_extension}"}

@router.get("/config/logo")
async def get_logo():
    for logo_file in UPLOADS_DIR.glob("logo.*"):
        return FileResponse(logo_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="No hay logo configurado")

@router.delete("/config/logo")
async def delete_logo(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    for existing_logo in UPLOADS_DIR.glob("logo.*"):
        existing_logo.unlink()
        return {"message": "Logo eliminado exitosamente"}
    
    raise HTTPException(status_code=404, detail="No hay logo para eliminar")


# ==================== LOGO DE PIE DE NOTIFICACIONES (FIRMA) ====================

@router.post("/config/notification-logo")
async def upload_notification_logo(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Sube el 'Logotipo para Pie de Notificaciones' usado en la firma global."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden cargar el logo de notificaciones")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen (.png o .jpg)")

    file_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
    if file_extension not in ("png", "jpg", "jpeg"):
        raise HTTPException(status_code=400, detail="Formato no permitido. Use .png o .jpg")

    for existing in UPLOADS_DIR.glob("notif_logo.*"):
        existing.unlink()
    logo_path = UPLOADS_DIR / f"notif_logo.{file_extension}"
    with open(logo_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    await db.config.update_one(
        {"type": "notification_footer_logo"},
        {"$set": {"type": "notification_footer_logo", "filename": f"notif_logo.{file_extension}",
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    try:
        from services.signature import invalidate_signature_logo_cache
        invalidate_signature_logo_cache()
    except Exception:
        pass
    return {"message": "Logo de notificaciones subido exitosamente", "filename": f"notif_logo.{file_extension}"}


@router.get("/config/notification-logo")
async def get_notification_logo():
    for logo_file in UPLOADS_DIR.glob("notif_logo.*"):
        return FileResponse(logo_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="No hay logo de notificaciones configurado")


@router.delete("/config/notification-logo")
async def delete_notification_logo(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    removed = False
    for existing in UPLOADS_DIR.glob("notif_logo.*"):
        existing.unlink()
        removed = True
    await db.config.delete_one({"type": "notification_footer_logo"})
    try:
        from services.signature import invalidate_signature_logo_cache
        invalidate_signature_logo_cache()
    except Exception:
        pass
    if removed:
        return {"message": "Logo de notificaciones eliminado"}
    raise HTTPException(status_code=404, detail="No hay logo para eliminar")

# ==================== QUOTE TEMPLATES (PDFs) ====================

TEMPLATE_TYPES = [
    "vpos_pyme",
    "vpos_corporativo", 
    "payment_gateway",
    "mpos",
    "dispositivos",
    "accesorios"
]

@router.post("/config/templates/{template_type}")
async def upload_template(template_type: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Subir plantilla PDF para un tipo de cotización"""
    await get_current_user(authorization)
    
    if template_type not in TEMPLATE_TYPES:
        raise HTTPException(status_code=400, detail=f"Tipo de plantilla inválido. Tipos válidos: {', '.join(TEMPLATE_TYPES)}")
    
    if not file.content_type == 'application/pdf':
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
    
    templates_dir = UPLOADS_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    template_path = templates_dir / f"{template_type}.pdf"
    
    # Remove existing template if exists
    if template_path.exists():
        template_path.unlink()
    
    with open(template_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"message": f"Plantilla {template_type} subida exitosamente", "filename": f"{template_type}.pdf"}

@router.get("/config/templates/{template_type}")
async def get_template(template_type: str, authorization: Optional[str] = Header(None)):
    """Obtener plantilla PDF de un tipo de cotización"""
    await get_current_user(authorization)
    
    if template_type not in TEMPLATE_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de plantilla inválido")
    
    templates_dir = UPLOADS_DIR / "templates"
    template_path = templates_dir / f"{template_type}.pdf"
    
    if not template_path.exists():
        raise HTTPException(status_code=404, detail=f"No hay plantilla configurada para {template_type}")
    
    return FileResponse(template_path, media_type="application/pdf", filename=f"plantilla_{template_type}.pdf")

@router.delete("/config/templates/{template_type}")
async def delete_template(template_type: str, authorization: Optional[str] = Header(None)):
    """Eliminar plantilla PDF de un tipo de cotización"""
    await get_current_user(authorization)
    
    if template_type not in TEMPLATE_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de plantilla inválido")
    
    templates_dir = UPLOADS_DIR / "templates"
    template_path = templates_dir / f"{template_type}.pdf"
    
    if template_path.exists():
        template_path.unlink()
        return {"message": f"Plantilla {template_type} eliminada exitosamente"}
    
    raise HTTPException(status_code=404, detail="No hay plantilla para eliminar")

@router.get("/config/templates")
async def list_templates(authorization: Optional[str] = Header(None)):
    """Listar estado de todas las plantillas"""
    await get_current_user(authorization)
    
    templates_dir = UPLOADS_DIR / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    template_status = {}
    for template_type in TEMPLATE_TYPES:
        template_path = templates_dir / f"{template_type}.pdf"
        template_status[template_type] = {
            "exists": template_path.exists(),
            "filename": f"{template_type}.pdf" if template_path.exists() else None
        }
    
    return template_status



# ==================== GESTOR DE ANEXOS CORPORATIVOS (TARIFAS PDF) ====================
# Permite subir/actualizar desde Configuración los anexos de tarifas que el motor
# de PDF intercala en las cotizaciones Link de Pago / Tokenizador, sin depender de
# un redeploy. Se persisten en Mongo (base64) y se materializan en disco; al arrancar
# el servidor se restauran a disco (restore_corporate_anexos) para sobrevivir redeploys.
from pathlib import Path as _Path
import base64 as _base64
from config import STATIC_PDFS_DIR as _STATIC_PDFS_DIR

ANEXOS_STATIC_DIR = _Path(__file__).resolve().parent.parent / "static" / "anexos"
_ANEXO_DIRS = {"anexos": ANEXOS_STATIC_DIR, "static_pdfs": _Path(str(_STATIC_PDFS_DIR))}

CORPORATE_ANEXOS = {
    # --- Tarifas (motor Link de Pago / Tokenizador) ---
    "link_pago": {"label": "Tarifas Link de Pago", "filename": "link_pago_anexo.pdf", "dir": "anexos",
                  "category": "Tarifas", "description": "Página de tarifas insertada en cotizaciones Link de Pago (pág. 5)."},
    "tokenizador": {"label": "Tarifas Tokenizador", "filename": "tokenizador_anexo.pdf", "dir": "anexos",
                    "category": "Tarifas", "description": "Página de tarifas del Tokenizador (rutas Tokenizador y Ambos)."},
    # --- Términos y Condiciones (PyME) ---
    "terminos_pg": {"label": "Términos PG / Link de Pago (PyME)", "filename": "anexo_pg.pdf", "dir": "static_pdfs",
                    "category": "Términos y Condiciones (PyME)", "description": "Condiciones legales para Payment Gateway y Link de Pago segmento PyME."},
    "terminos_vpos": {"label": "Términos VPOS (PyME)", "filename": "anexo_vpos.pdf", "dir": "static_pdfs",
                      "category": "Términos y Condiciones (PyME)", "description": "Condiciones legales para VPOS segmento PyME."},
    # --- Términos y Condiciones (Corporativo) ---
    "terminos_gateway_corp": {"label": "Términos Payment Gateway (Corporativo)", "filename": "anexo_gateway_corp.pdf", "dir": "static_pdfs",
                              "category": "Términos y Condiciones (Corporativo)", "description": "Anexo corporativo que reemplaza los términos en cotizaciones PG corporativas."},
    "terminos_link_corp": {"label": "Términos Link de Pago (Corporativo)", "filename": "anexo_link_corp.pdf", "dir": "static_pdfs",
                           "category": "Términos y Condiciones (Corporativo)", "description": "Anexo corporativo que reemplaza los términos en cotizaciones Link de Pago corporativas."},
    "terminos_vpos_corp": {"label": "Términos VPOS (Corporativo)", "filename": "anexo_corporativa.pdf", "dir": "static_pdfs",
                           "category": "Términos y Condiciones (Corporativo)", "description": "Anexo corporativo para cotizaciones VPOS corporativas."},
    # --- Condiciones de Equipos / Servicios ---
    "cond_verifone_tbp": {"label": "Condiciones Verifone (PyME / TBP)", "filename": "condiciones_verifone_tbp.pdf", "dir": "static_pdfs",
                          "category": "Condiciones de Equipos", "description": "Condiciones legales para equipos Verifone segmento PyME (TBP)."},
    "cond_verifone": {"label": "Condiciones Verifone (Corporativo / LCH)", "filename": "condiciones_verifone.pdf", "dir": "static_pdfs",
                      "category": "Condiciones de Equipos", "description": "Condiciones legales para equipos Verifone segmento Corporativo (LCH)."},
    "cond_morefun": {"label": "Condiciones Morefun", "filename": "condiciones_morefun.pdf", "dir": "static_pdfs",
                     "category": "Condiciones de Equipos", "description": "Condiciones legales para equipos Morefun."},
    "cond_accesorios": {"label": "Condiciones Accesorios", "filename": "condiciones_accesorios.pdf", "dir": "static_pdfs",
                        "category": "Condiciones de Equipos", "description": "Condiciones legales para cotizaciones de accesorios."},
    "cond_reparaciones": {"label": "Condiciones Reparaciones", "filename": "condiciones_reparaciones.pdf", "dir": "static_pdfs",
                          "category": "Condiciones de Equipos", "description": "Condiciones legales para cotizaciones de reparaciones."},
}


def _anexo_path(key: str) -> _Path:
    cfg = CORPORATE_ANEXOS[key]
    return _ANEXO_DIRS[cfg.get("dir", "anexos")] / cfg["filename"]


async def restore_corporate_anexos():
    """Restaura los anexos corporativos almacenados en Mongo hacia el disco.
    Se invoca en el arranque del servidor para que las cargas hechas desde la UI
    persistan tras un redeploy (el FS del contenedor es efímero)."""
    try:
        async for doc in db.corporate_anexos.find({}):
            key = doc.get("key")
            content_b64 = doc.get("content_b64")
            if key in CORPORATE_ANEXOS and content_b64:
                try:
                    p = _anexo_path(key)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(_base64.b64decode(content_b64))
                except Exception as e:
                    logging.warning(f"[anexos] restore {key} failed: {e}")
    except Exception as e:
        logging.warning(f"[anexos] restore_corporate_anexos failed: {e}")


def _anexo_metadata(key: str) -> dict:
    cfg = CORPORATE_ANEXOS[key]
    path = _anexo_path(key)
    meta = {"key": key, "label": cfg["label"], "description": cfg["description"],
            "category": cfg.get("category", "General"),
            "filename": cfg["filename"], "exists": path.exists(), "size": None, "pages": None}
    if path.exists():
        try:
            meta["size"] = path.stat().st_size
            from PyPDF2 import PdfReader
            meta["pages"] = len(PdfReader(str(path)).pages)
        except Exception:
            pass
    return meta


@router.get("/config/anexos")
async def list_corporate_anexos(authorization: Optional[str] = Header(None)):
    """Lista los anexos corporativos gestionables y sus metadatos (incluye la fecha
    de última actualización almacenada en Mongo)."""
    await get_current_user(authorization)
    items = []
    for key in CORPORATE_ANEXOS:
        meta = _anexo_metadata(key)
        doc = await db.corporate_anexos.find_one({"key": key}, {"_id": 0, "updated_at": 1, "updated_by": 1})
        meta["updated_at"] = (doc or {}).get("updated_at")
        meta["updated_by"] = (doc or {}).get("updated_by")
        items.append(meta)
    return {"anexos": items}


@router.post("/config/anexos/{key}")
async def upload_corporate_anexo(key: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Sube/reemplaza un anexo corporativo (solo PDF). Persiste en Mongo y en disco."""
    user = await get_current_user(authorization)
    if key not in CORPORATE_ANEXOS:
        raise HTTPException(status_code=404, detail="Anexo no reconocido")
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf") and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    # Validar que sea un PDF legible
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        num_pages = len(reader.pages)
        if num_pages < 1:
            raise ValueError("PDF sin páginas")
    except Exception:
        raise HTTPException(status_code=400, detail="El PDF no es válido o está dañado")

    # Persistir en disco
    _anexo_path(key).parent.mkdir(parents=True, exist_ok=True)
    _anexo_path(key).write_bytes(content)

    # Persistir en Mongo (para sobrevivir redeploys)
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.corporate_anexos.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "filename": CORPORATE_ANEXOS[key]["filename"],
            "content_b64": _base64.b64encode(content).decode("ascii"),
            "size": len(content),
            "pages": num_pages,
            "updated_at": now_iso,
            "updated_by": user.get("full_name") or user.get("email") or user.get("user_id"),
        }},
        upsert=True,
    )
    return {"success": True, "key": key, "pages": num_pages, "size": len(content), "updated_at": now_iso}


@router.get("/config/anexos/{key}/download")
async def download_corporate_anexo(key: str, authorization: Optional[str] = Header(None)):
    """Descarga el anexo corporativo actual."""
    await get_current_user(authorization)
    if key not in CORPORATE_ANEXOS:
        raise HTTPException(status_code=404, detail="Anexo no reconocido")
    path = _anexo_path(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Anexo no disponible")
    return FileResponse(str(path), media_type="application/pdf", filename=CORPORATE_ANEXOS[key]["filename"])

