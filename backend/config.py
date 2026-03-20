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

# Resend para envío de emails
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

# Configuración de Resend
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'onboarding@resend.dev')
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
    except:
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
