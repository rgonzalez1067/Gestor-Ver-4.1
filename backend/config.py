"""
Configuración central de la aplicación.
Contiene la conexión a MongoDB, directorios, y helpers compartidos.
"""
from fastapi import Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import os
import logging
import io
import hashlib
import secrets

from dotenv import load_dotenv

# PyPDF2 para manipulación de plantillas PDF
try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

# Resend para envío de emails (legacy/fallback)
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Configuración SMTP propio
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
SMTP_AVAILABLE = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)

# Configuración de Resend (fallback)
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'gestor@megasoft.com.ve')
if RESEND_AVAILABLE and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

STATIC_PDFS_DIR = ROOT_DIR / "static_pdfs"


# ==================== PASSWORD HELPERS ====================

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{pwd_hash}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, pwd_hash = stored_hash.split(":")
        check_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return check_hash == pwd_hash
    except Exception:
        return False


# ==================== AUTH HELPERS ====================

async def get_resend_api_key():
    global RESEND_API_KEY
    config = await db.config.find_one({"type": "app_settings"})
    if config and config.get("resend_api_key"):
        api_key = config["resend_api_key"]
        if RESEND_AVAILABLE:
            resend.api_key = api_key
        return api_key
    return RESEND_API_KEY


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    session_token = None
    
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.replace("Bearer ", "")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
    
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user_doc


async def require_permission(authorization: Optional[str], module: str, level: str = "read"):
    """Middleware de permisos RBAC.
    Valida que el usuario tenga el nivel de permiso requerido para el módulo.
    level: 'read' (GET) o 'edit' (POST/PUT/PATCH/DELETE)
    Lanza 403 si el permiso es insuficiente.
    """
    user = await get_current_user(authorization)
    # Admins siempre tienen acceso completo
    if user.get("role") == "admin":
        return user
    
    permissions = user.get("permissions", {})
    user_level = permissions.get(module, "none")
    
    if user_level == "none":
        raise HTTPException(status_code=403, detail=f"No tiene acceso al módulo '{module}'")
    
    if level == "edit" and user_level == "read":
        raise HTTPException(status_code=403, detail=f"No tiene permisos de escritura en el módulo '{module}'")
    
    return user


async def generate_quote_number(sede: str) -> str:
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    sede_code = sede.upper() if sede in ("PYME", "CORP") else "PYME"
    counter_key = f"quote_{sede_code}_{year}_{month}"
    
    result = await db.counters.find_one_and_update(
        {"_id": counter_key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = result["seq"]
    return f"COT-{year}-{month}-{seq:03d}-{sede_code}"


def stamp_header_footer_on_all_pages(pdf_buffer, quote_number="", logo_path=None):
    """Aplica encabezado y pie de página como overlay en TODAS las páginas del PDF final.
    Esto asegura que las páginas inyectadas (anexos, condiciones) también tengan el branding."""
    if not PYPDF2_AVAILABLE:
        return pdf_buffer
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as rl_canvas
    
    pdf_buffer.seek(0) if isinstance(pdf_buffer, io.BytesIO) else None
    reader = PdfReader(pdf_buffer if isinstance(pdf_buffer, io.BytesIO) else io.BytesIO(pdf_buffer))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return pdf_buffer
    
    page_width, page_height = letter
    margin = 50
    writer = PdfWriter()
    
    for page_num, page in enumerate(reader.pages, start=1):
        # Crear overlay para esta página
        overlay_buf = io.BytesIO()
        c = rl_canvas.Canvas(overlay_buf, pagesize=letter)
        
        # Encabezado - Logo
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(logo_path, margin, page_height - 70, width=120, height=50, preserveAspectRatio=True)
            except Exception:
                pass
        
        # Línea de encabezado
        c.setStrokeColor(colors.HexColor("#00447C"))
        c.setLineWidth(2)
        c.line(margin, page_height - 80, page_width - margin, page_height - 80)
        
        # Número de cotización + fecha
        if quote_number:
            c.setFont('Helvetica-Bold', 10)
            c.setFillColor(colors.HexColor("#00447C"))
            c.drawRightString(page_width - margin, page_height - 55, f"Cotizacion: {quote_number}")
            c.setFont('Helvetica', 8)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawRightString(page_width - margin, page_height - 68, 
                             f"Fecha: {datetime.now(timezone.utc).strftime('%d/%m/%Y')}")
        
        # Pie de página
        c.setStrokeColor(colors.HexColor("#EEEEEE"))
        c.setLineWidth(1)
        c.line(margin, 40, page_width - margin, 40)
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(margin, 25, "Documento Confidencial - Propiedad de Mega Soft Computacion C.A.")
        c.drawRightString(page_width - margin, 25, f"Pagina {page_num} de {total_pages}")
        
        c.save()
        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        overlay_page = overlay_reader.pages[0]
        
        # Merge: overlay encima de la página original
        page.merge_page(overlay_page)
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def append_vpos_static_pages(pdf_buffer: io.BytesIO) -> io.BytesIO:
    if not PYPDF2_AVAILABLE:
        return pdf_buffer
    
    anexo_path = STATIC_PDFS_DIR / "anexo_vpos.pdf"
    if not anexo_path.exists():
        return pdf_buffer
    
    writer = PdfWriter()
    pdf_buffer.seek(0)
    reader = PdfReader(pdf_buffer)
    for page in reader.pages:
        writer.add_page(page)
    
    anexo_reader = PdfReader(str(anexo_path))
    for page in anexo_reader.pages:
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def append_pg_static_pages(pdf_buffer: io.BytesIO) -> io.BytesIO:
    if not PYPDF2_AVAILABLE:
        return pdf_buffer
    
    anexo_path = STATIC_PDFS_DIR / "anexo_pg.pdf"
    if not anexo_path.exists():
        return pdf_buffer
    
    writer = PdfWriter()
    pdf_buffer.seek(0)
    reader = PdfReader(pdf_buffer)
    for page in reader.pages:
        writer.add_page(page)
    
    anexo_reader = PdfReader(str(anexo_path))
    for page in anexo_reader.pages:
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def append_corporate_static_pages(pdf_buffer: io.BytesIO) -> io.BytesIO:
    """Anexa el PDF 'Anexo Cotización Corporativa' al PDF generado para clientes corporativos.
    Reemplaza las páginas estándar de términos y condiciones (páginas 6-9)."""
    if not PYPDF2_AVAILABLE:
        return pdf_buffer
    
    anexo_path = STATIC_PDFS_DIR / "anexo_corporativa.pdf"
    if not anexo_path.exists():
        return pdf_buffer
    
    writer = PdfWriter()
    pdf_buffer.seek(0)
    reader = PdfReader(pdf_buffer)
    for page in reader.pages:
        writer.add_page(page)
    
    anexo_reader = PdfReader(str(anexo_path))
    for page in anexo_reader.pages:
        writer.add_page(page)
    
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output


def append_equipment_conditions(pdf_bytes: bytes, equipment_type: str, sede: str = "") -> bytes:
    """Anexa el PDF de condiciones legales correspondiente al tipo de equipo y sede."""
    if not PYPDF2_AVAILABLE:
        return pdf_bytes

    # Para Verifone, diferenciar por sede: PYME→TBP, CORP→LCH
    if equipment_type == "Verifone":
        filename = "condiciones_verifone_tbp.pdf" if sede == "PYME" else "condiciones_verifone.pdf"
    else:
        conditions_map = {
            "Morefun": "condiciones_morefun.pdf",
            "Accesorio": "condiciones_accesorios.pdf",
            "Reparación": "condiciones_reparaciones.pdf",
        }
        filename = conditions_map.get(equipment_type)

    if not filename:
        return pdf_bytes

    conditions_path = STATIC_PDFS_DIR / filename
    if not conditions_path.exists():
        return pdf_bytes

    writer = PdfWriter()
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        writer.add_page(page)

    conditions_reader = PdfReader(str(conditions_path))
    for page in conditions_reader.pages:
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def render_email_template(template_body: str, variables: dict) -> str:
    result = template_body
    for key, value in variables.items():
        # Soportar {{key}}, {key}, y #{key}
        result = result.replace(f"{{{{{key}}}}}", str(value))
        result = result.replace(f"#{{{key}}}", str(value))
        result = result.replace(f"{{{key}}}", str(value))
    return result


def build_custom_message_block(custom_message: str, user_name: str = "", max_chars: int = 1000) -> str:
    """Construye el bloque HTML del mensaje personalizado del operador.

    Si custom_message es vacío, retorna string vacío.
    """
    if not custom_message or not str(custom_message).strip():
        return ""
    safe_msg = str(custom_message).strip()
    if max_chars and len(safe_msg) > max_chars:
        safe_msg = safe_msg[:max_chars]
    label = f"Mensaje de {user_name}".strip() if user_name else "Mensaje del remitente"
    return (
        '<div style="margin:16px 0;padding:12px;background:#f0f9ff;'
        'border-left:4px solid #3b82f6;border-radius:4px;">'
        f'<p style="font-size:13px;color:#1e40af;margin:0;"><strong>{label}:</strong></p>'
        f'<p style="font-size:13px;color:#334155;margin:6px 0 0;white-space:pre-wrap;">{safe_msg}</p>'
        '</div>'
    )


def inject_custom_message(html: str, custom_message: str, user_name: str = "", max_chars: int = 1000) -> str:
    """Inserta el bloque del mensaje personalizado en el HTML del correo.

    Orden buscado:
      1. Marcador `{{Mensaje_Personalizado}}` o `{Mensaje_Personalizado}` en la plantilla → reemplaza (control fino).
      2. Antes de patrones típicos de cierre/firma ("Atentamente", "Saludos cordiales", "Equipo Mega Soft", "Equipo MegaNexus", etc.) → inserta ANTES.
      3. Antes de </body> si existe.
      4. Append al final como último recurso.

    El footer institucional global se anexa después en `send_email()`, por lo que
    el resultado final queda: Cuerpo → Mensaje Personalizado → Firma plantilla → Footer global.
    """
    block = build_custom_message_block(custom_message, user_name, max_chars=max_chars)
    if not html:
        return block
    if not block:
        # Limpiar marcadores residuales si los hay
        cleaned = html
        for marker in ("{{Mensaje_Personalizado}}", "{Mensaje_Personalizado}", "#{Mensaje_Personalizado}"):
            cleaned = cleaned.replace(marker, "")
        return cleaned

    # 1) Reemplazo por marcador explícito
    for marker in ("{{Mensaje_Personalizado}}", "{Mensaje_Personalizado}", "#{Mensaje_Personalizado}"):
        if marker in html:
            return html.replace(marker, block)

    # 2) Insertar antes de patrones de cierre (case-insensitive)
    import re
    closing_patterns = [
        r"atentamente[,.\s]",
        r"saludos\s+cordiales",
        r"cordialmente",
        r"equipo\s+mega\s*soft",
        r"equipo\s+mega\s*nexus",
        r"quedamos\s+a\s+su\s+disposici",
    ]
    for pat in closing_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            # Buscar el inicio del tag/bloque que contiene este texto (último <p, <div o <br antes)
            cut_search = re.search(r"<(p|div|br|hr|table)[^>]*>(?=[^<]*" + pat + ")", html, re.IGNORECASE)
            insert_at = cut_search.start() if cut_search else m.start()
            return html[:insert_at] + block + html[insert_at:]

    # 3) Antes de </body>
    if "</body>" in html.lower():
        return re.sub(r"</body>", block + "</body>", html, count=1, flags=re.IGNORECASE)

    # 4) Append al final
    return html + block

