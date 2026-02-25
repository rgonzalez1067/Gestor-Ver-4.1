from fastapi import FastAPI, APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate, BaseDocTemplate, PageBreak
from reportlab.lib.units import inch, cm, mm
from reportlab.pdfgen import canvas
import io
import shutil
import csv
import base64
import hashlib
import secrets

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

# Helper function para obtener API key de Resend (BD o env)
async def get_resend_api_key():
    """Obtiene la API key de Resend de la BD o de las variables de entorno"""
    global RESEND_API_KEY
    
    # Primero intentar de la BD
    config = await db.config.find_one({"type": "app_settings"})
    if config and config.get("resend_api_key"):
        api_key = config["resend_api_key"]
        if RESEND_AVAILABLE:
            resend.api_key = api_key
        return api_key
    
    # Fallback a variable de entorno
    return RESEND_API_KEY

app = FastAPI(title="Cotizador Merchant Server API")

# Create uploads directory for logo
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
api_router = APIRouter(prefix="/api")

async def generate_quote_number(sede: str) -> str:
    """Genera un número de cotización con formato COT-AAAA-MM-NNN-SEDE.
    Usa un contador atómico por sede y mes en la colección 'counters'.
    """
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    sede_code = sede.upper() if sede in ("TBP", "LCH") else "TBP"
    counter_key = f"quote_{sede_code}_{year}_{month}"
    
    result = await db.counters.find_one_and_update(
        {"_id": counter_key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True  # motor: True = AFTER
    )
    seq = result["seq"]
    return f"COT-{year}-{month}-{seq:03d}-{sede_code}"

# ==================== MODELS ====================

class Contact(BaseModel):
    name: str
    phone: str
    email: EmailStr

class ContactCRM(BaseModel):
    contact_id: str = Field(default_factory=lambda: f"cnt_{uuid.uuid4().hex[:8]}")
    first_name: str
    last_name: str
    phone: str = ""
    email: str = ""
    role: Literal["Administrativo", "Financiero", "Técnico", "Cuentas por Pagar", "Operativo"] = "Administrativo"

class ClientCreate(BaseModel):
    rif: str
    legal_name: str
    fantasy_name: str
    segment: Literal["Pymes", "Corporativo", "Mixto"]
    address: Optional[str] = None
    sucursal: str = "Principal"
    contacts: List[ContactCRM] = []
    # Legacy support
    contact1: Optional[Contact] = None
    contact2: Optional[Contact] = None

class Client(BaseModel):
    client_id: str = Field(default_factory=lambda: f"cli_{uuid.uuid4().hex[:12]}")
    rif: str
    legal_name: str
    fantasy_name: str
    segment: Literal["Pymes", "Corporativo", "Mixto"]
    address: Optional[str] = None
    sucursal: str = "Principal"
    contacts: List[ContactCRM] = []
    contact1: Optional[Contact] = None
    contact2: Optional[Contact] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ClientLogCreate(BaseModel):
    client_id: str
    contact_date: Optional[str] = None
    detail: str
    action: str = ""
    follow_up_date: Optional[str] = None

class BankProduct(BaseModel):
    product_name: str
    description: Optional[str] = None
    vpos_available: bool = False
    gateway_available: bool = False
    mpos_available: bool = False
    link_available: bool = False

class BankCreate(BaseModel):
    name: str
    type: str
    country: str
    products: List[BankProduct] = []

class Bank(BaseModel):
    bank_id: str = Field(default_factory=lambda: f"bnk_{uuid.uuid4().hex[:12]}")
    name: str
    type: str
    country: str
    products: List[BankProduct] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComponentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ComponentType(BaseModel):
    component_id: str = Field(default_factory=lambda: f"cmp_{uuid.uuid4().hex[:12]}")
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class HardwareCreate(BaseModel):
    name: str
    type: str
    price_usd: float
    price_bs_usd: float
    description: Optional[str] = None

class Hardware(BaseModel):
    hardware_id: str = Field(default_factory=lambda: f"hwr_{uuid.uuid4().hex[:12]}")
    name: str
    type: str
    price_usd: float
    price_bs_usd: float
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ServiceCreate(BaseModel):
    category: str
    name: str
    application_type: Literal["setup", "recurring", "both"] = "both"
    vpos_enabled: bool = True
    gateway_enabled: bool = True
    mpos_enabled: bool = True
    link_enabled: bool = True
    setup_cost_conventional: float = 0
    monthly_cost_conventional: float = 0
    setup_cost_outsourcing: float = 0
    monthly_cost_outsourcing: float = 0
    description: Optional[str] = None
    linked_recurring_service_id: Optional[str] = None  # ID del servicio recurrente vinculado (solo para tipo setup/both)

class Service(BaseModel):
    service_id: str = Field(default_factory=lambda: f"srv_{uuid.uuid4().hex[:12]}")
    category: str
    name: str
    application_type: str = "both"
    vpos_enabled: bool = True
    gateway_enabled: bool = True
    mpos_enabled: bool = True
    link_enabled: bool = True
    setup_cost_conventional: float = 0
    monthly_cost_conventional: float = 0
    setup_cost_outsourcing: float = 0
    monthly_cost_outsourcing: float = 0
    description: Optional[str] = None
    linked_recurring_service_id: Optional[str] = None  # ID del servicio recurrente vinculado
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== INTEGRATOR MODELS ====================
INTEGRATOR_TYPES = ["Integrador", "Comercio"]
INTEGRATION_MODALITIES = ["Bridge PG", "MPOS", "PG Universal", "PG No universal", "REST", "Stand Alone"]
INTEGRATOR_STATUSES = ["Certificado", "En proceso", "Suspendido"]

# ==================== IMPORT RESPONSE MODELS ====================
class ImportError(BaseModel):
    row: int
    column: str
    value: Optional[str] = None
    error_type: str  # 'missing', 'invalid', 'format', 'duplicate'
    message: str
    suggested_action: str

class ImportValidationResult(BaseModel):
    is_valid: bool
    file_format: str
    total_rows: int
    columns_found: List[str]
    columns_missing: List[str]
    columns_extra: List[str]
    message: str

class ImportResult(BaseModel):
    status: str  # 'success', 'partial', 'error'
    total_processed: int
    success_count: int
    error_count: int
    skipped_count: int
    errors: List[ImportError]
    message: str

class IntegratorCreate(BaseModel):
    name: str
    integrator_type: Literal["Integrador", "Comercio"]
    app_name: str
    integration_modality: Literal["Bridge PG", "MPOS", "PG Universal", "PG No universal", "REST", "Stand Alone"]
    integrator_status: Literal["Certificado", "En proceso", "Suspendido"] = "En proceso"

class Integrator(BaseModel):
    integrator_id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:12]}")
    name: str
    integrator_type: str
    app_name: str
    integration_modality: str
    integrator_status: str = "En proceso"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QuoteItem(BaseModel):
    item_type: str
    item_id: Optional[str] = None  # Opcional para items generados dinámicamente
    item_name: str
    quantity: int
    unit_price_usd: float
    total_usd: float
    # Campos adicionales para preservar datos de edición
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Campos específicos para items adicionales (medios de pago)
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None
    tarifa_setup: Optional[float] = None
    tarifa_recurrente: Optional[float] = None

# Modelo para items de cotización de equipos
class EquipmentQuoteItem(BaseModel):
    hardware_id: str
    name: str
    hardware_type: str  # "Dispositivo" o "Accesorio"
    quantity: int = 1
    unit_price_usd: float = 0
    total_usd: float = 0

# Tipos de cotización - ACTUALIZADO con nueva estructura jerárquica
QUOTE_CATEGORIES = ["implementation", "equipment", "repair"]  # Implementación, Equipos/Accesorios o Reparaciones
EQUIPMENT_TYPES = ["Dispositivo", "Accesorio"]

# Categorías para filtros (según anexo del usuario)
QUOTE_FILTER_CATEGORIES = [
    {"id": "Implementaciones", "description": "Servicios de instalación, configuración o puesta en marcha"},
    {"id": "Equipos", "description": "Venta de hardware principal (Laptops, Servidores, etc.)"},
    {"id": "Accesorios", "description": "Periféricos y complementos (Mouses, cables, teclados)"},
    {"id": "Reparaciones", "description": "Mano de obra técnica y servicios de mantenimiento correctivo"}
]

class QuoteCreate(BaseModel):
    client_id: str
    quote_category: str = "implementation"  # "implementation", "equipment" o "repair"
    quote_type: Optional[str] = "VPOS"  # Para implementaciones
    equipment_type: Optional[str] = None  # "Dispositivo" o "Accesorio" para equipos
    pricing_model: Optional[str] = "conventional"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    equipment_items: List[EquipmentQuoteItem] = []  # Items para cotización de equipos
    notes: Optional[str] = None
    # Nuevos campos de integración y hardware
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    # Campos de cantidades a nivel de cotización
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Campos específicos para REPARACIONES
    repair_description: Optional[str] = None  # Descripción de la falla
    equipment_serial_number: Optional[str] = None  # Número de serie del equipo a reparar
    estimated_delivery_date: Optional[str] = None  # Fecha estimada de entrega

# Estados del ciclo de vida de cotizaciones - Flujo actualizado
QUOTE_STATUSES = ["Borrador", "Enviada", "Aprobada", "Facturada", "Pagada", "Entregada", "Enviada a Imple"]

# Flujo de transiciones permitidas por categoría
QUOTE_TRANSITIONS = {
    "equipment": {
        "Borrador": ["Enviada"],
        "Enviada": ["Aprobada"],
        "Aprobada": ["Facturada"],
        "Facturada": ["Pagada"],
        "Pagada": ["Entregada"],
        "Entregada": []  # Estado final
    },
    "implementation": {
        "Borrador": ["Enviada"],
        "Enviada": ["Aprobada"],
        "Aprobada": ["Facturada"],
        "Facturada": ["Pagada"],
        "Pagada": ["Enviada a Imple"],
        "Enviada a Imple": []  # Estado final
    },
    "repair": {
        "Borrador": ["Enviada"],
        "Enviada": ["Aprobada"],
        "Aprobada": ["Facturada"],
        "Facturada": ["Pagada"],
        "Pagada": ["Entregada"],
        "Entregada": []  # Estado final - Equipo reparado entregado
    }
}

class Quote(BaseModel):
    quote_id: str = Field(default_factory=lambda: f"quo_{uuid.uuid4().hex[:12]}")
    quote_number: str
    client_id: str
    quote_category: str = "implementation"  # "implementation", "equipment" o "repair"
    quote_type: str = "VPOS"  # Para implementaciones
    equipment_type: Optional[str] = None  # "Dispositivo" o "Accesorio" para equipos
    pricing_model: str = "conventional"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    equipment_items: List[EquipmentQuoteItem] = []  # Items para cotización de equipos
    subtotal_usd: float
    total_usd: float
    exchange_rate: float
    total_bs: float
    notes: Optional[str] = None
    quote_status: str = "Borrador"  # Estados: Borrador, Enviada, Aprobada, Facturada, Pagada, Entregada, Enviada a Imple
    # Campos de integración y hardware
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    # Campos de cantidades a nivel de cotización
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Campos específicos para REPARACIONES
    repair_description: Optional[str] = None  # Descripción de la falla
    equipment_serial_number: Optional[str] = None  # Número de serie del equipo a reparar
    estimated_delivery_date: Optional[str] = None  # Fecha estimada de entrega
    # Sede del usuario que crea la cotización
    sede: str = "TBP"  # "TBP" (Torre Banco Plaza) o "LCH" (Los Chaguaramos)
    created_by_user_id: Optional[str] = None  # ID del usuario que creó la cotización
    # Campos de seguimiento - timestamps
    sent_to_client_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    invoiced_at: Optional[datetime] = None  # NUEVO: Cuando se factura
    paid_at: Optional[datetime] = None  # NUEVO: Cuando se cobra
    delivered_at: Optional[datetime] = None  # NUEVO: Cuando se entrega (equipos)
    sent_to_implementation_at: Optional[datetime] = None
    # Campos de PDF y factura
    quote_pdf_url: Optional[str] = None  # URL del PDF de la cotización
    invoice_pdf_url: Optional[str] = None  # URL del PDF de la factura
    invoice_number: Optional[str] = None  # Número de factura
    # Versionamiento
    version: int = 1  # Versión de la cotización
    parent_quote_id: Optional[str] = None  # ID de la cotización original (si es una modificación)
    attachments: List[dict] = []  # Lista de anexos: {attachment_id, category, filename, url, uploaded_by, uploaded_at}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Categorías de anexos
ATTACHMENT_CATEGORIES = [
    "Cotización",
    "Orden de Compra",
    "Factura",
    "Pagos",
    "Otros"
]

# Reglas de workflow: qué categoría de anexo es obligatoria para cada transición de estado
WORKFLOW_ATTACHMENT_RULES = {
    "Aprobada": {"category": "Orden de Compra", "max_files": 1, "label": "Orden de Compra Aprobada"},
    "Facturada": {"category": "Factura", "max_files": 1, "label": "Documento Fiscal (Factura)"},
    "Pagada": {"category": "Pagos", "max_files": 0, "label": "Comprobante(s) de Pago"},  # 0 = múltiple
}

class ExchangeRate(BaseModel):
    rate: float
    date: datetime
    source: str = "BCV"

# Modelo para generar PDF desde frontend
class QuotePDFItem(BaseModel):
    concepto: str
    cantidad_cajas: int = 1
    cantidad_bancos: int = 1
    tarifa: float = 0
    total: float = 0
    bank_name: Optional[str] = None  # Para la matriz de distribución

class QuotePDFRequest(BaseModel):
    cliente_nombre: str
    cliente_rif: str = ""
    cliente_address: str = ""  # Dirección fiscal
    quote_type: str = "VPOS"
    pricing_model: str = "conventional"
    cantidad_cajas: int = 1  # Total de cajas cotizadas
    # Nuevos campos de integración y hardware
    integrator_name: str = ""
    integrator_app_name: str = ""
    pinpad_model: str = ""
    sponsor_bank_name: str = ""
    setup_items: List[QuotePDFItem] = []
    recurring_basic_items: List[QuotePDFItem] = []
    recurring_other_items: List[QuotePDFItem] = []
    descuento: float = 0
    notes: str = ""

# ==================== AUTH MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None

class UserRegister(BaseModel):
    """Modelo para registro de usuario"""
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    cedula: str = Field(..., min_length=6, max_length=15)  # Cédula de identidad
    email: EmailStr
    password: str = Field(..., min_length=8)  # Mínimo 8 caracteres
    phone: Optional[str] = None  # Teléfono
    cargo: Optional[str] = None  # Cargo/Función
    departamento: Optional[str] = None  # Departamento
    sede: str = Field(default="TBP", description="Sede del usuario: TBP o LCH")

# Departamentos disponibles
DEPARTAMENTOS = ["Administración", "Almacén", "Ventas", "TI", "Implementación", "Gerencia"]

class UserLogin(BaseModel):
    """Modelo para login de usuario"""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Modelo de respuesta de usuario (sin password)"""
    user_id: str
    email: str
    first_name: str
    last_name: str
    cedula: str
    phone: Optional[str] = None
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    role: str = "user"  # "admin" o "user"
    sede: str = "TBP"  # "TBP" (Torre Banco Plaza) o "LCH" (Los Chaguaramos)
    is_active: bool = True
    is_verified: bool = False
    permissions: dict = {}
    created_at: Optional[str] = None

class UserUpdate(BaseModel):
    """Modelo para actualizar usuario (admin)"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    cedula: Optional[str] = None
    phone: Optional[str] = None
    cargo: Optional[str] = None
    departamento: Optional[str] = None
    sede: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserPermissions(BaseModel):
    """Modelo para actualizar permisos de usuario"""
    user_id: str
    permissions: dict  # {"cotizaciones": "edit", "clientes": "read", ...}

class SessionData(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    session_token: str

# Módulos disponibles para permisos
AVAILABLE_MODULES = [
    "cotizaciones",
    "clientes", 
    "bancos",
    "medios_pago",
    "dispositivos",
    "integradores",
    "configuracion"
]

# Niveles de permiso
PERMISSION_LEVELS = ["none", "read", "edit"]

# ==================== PASSWORD HELPERS ====================

def hash_password(password: str) -> str:
    """Hash de contraseña usando SHA-256 + salt"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{pwd_hash}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica contraseña contra hash almacenado"""
    try:
        salt, pwd_hash = stored_hash.split(":")
        check_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return check_hash == pwd_hash
    except:
        return False

# ==================== AUTH HELPERS ====================

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

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/session")
async def create_session(x_session_id: str = Header(...)):
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": x_session_id}
            )
            response.raise_for_status()
            session_data = response.json()
        
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"email": session_data["email"]}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": session_data["name"],
                    "picture": session_data.get("picture")
                }}
            )
        else:
            user_doc = {
                "user_id": user_id,
                "email": session_data["email"],
                "name": session_data["name"],
                "picture": session_data.get("picture"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(user_doc)
        
        session_token = session_data["session_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        
        return {
            "session_token": session_token,
            "user": user
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@api_router.get("/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    # Retornar usuario sin password_hash
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "first_name": user.get("first_name", user.get("name", "").split()[0] if user.get("name") else ""),
        "last_name": user.get("last_name", " ".join(user.get("name", "").split()[1:]) if user.get("name") else ""),
        "name": user.get("name", f"{user.get('first_name', '')} {user.get('last_name', '')}"),
        "cedula": user.get("cedula", ""),
        "role": user.get("role", "user"),
        "sede": user.get("sede", "TBP"),  # Sede del usuario
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
        "permissions": user.get("permissions", {}),
        "picture": user.get("picture")
    }

@api_router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.replace("Bearer ", "")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    return {"message": "Logged out successfully"}

# ==================== NEW AUTH ENDPOINTS (Email/Password) ====================

@api_router.post("/auth/register")
async def register_user(user_data: UserRegister):
    """Registrar nuevo usuario con email y contraseña"""
    
    # Verificar si el email ya existe
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
    
    # Verificar si la cédula ya existe
    existing_cedula = await db.users.find_one({"cedula": user_data.cedula}, {"_id": 0})
    if existing_cedula:
        raise HTTPException(status_code=400, detail="La cédula ya está registrada")
    
    # Crear usuario
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(user_data.password)
    
    # Validar sede
    valid_sedes = ["TBP", "LCH"]
    sede = user_data.sede.upper() if user_data.sede else "TBP"
    if sede not in valid_sedes:
        raise HTTPException(status_code=400, detail="Sede inválida. Debe ser 'TBP' o 'LCH'")
    
    # Verificar si es el primer usuario (será admin)
    user_count = await db.users.count_documents({})
    is_first_user = user_count == 0
    
    # Permisos por defecto (admin tiene todo, usuario tiene lectura)
    default_permissions = {}
    for module in AVAILABLE_MODULES:
        default_permissions[module] = "edit" if is_first_user else "read"
    
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "password_hash": password_hash,
        "role": "admin" if is_first_user else "user",
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions,
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Crear sesión automáticamente
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Retornar usuario sin password
    user_response = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "role": user_doc["role"],
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions
    }
    
    return {
        "message": "Usuario registrado exitosamente",
        "session_token": session_token,
        "user": user_response
    }

@api_router.post("/auth/login")
async def login_user(credentials: UserLogin):
    """Login con email y contraseña"""
    
    # Buscar usuario
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Verificar si es un usuario de Google OAuth (sin password_hash)
    if "password_hash" not in user:
        raise HTTPException(
            status_code=400, 
            detail="Esta cuenta fue creada con Google. Por favor, use el inicio de sesión con Google."
        )
    
    # Verificar contraseña
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Verificar si la cuenta está activa
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada. Contacte al administrador.")
    
    # Crear nueva sesión
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Retornar usuario sin password
    user_response = {
        "user_id": user["user_id"],
        "email": user["email"],
        "first_name": user.get("first_name", user.get("name", "").split()[0] if user.get("name") else ""),
        "last_name": user.get("last_name", " ".join(user.get("name", "").split()[1:]) if user.get("name") else ""),
        "name": user.get("name", f"{user.get('first_name', '')} {user.get('last_name', '')}"),
        "cedula": user.get("cedula", ""),
        "role": user.get("role", "user"),
        "sede": user.get("sede", "TBP"),  # Sede del usuario
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
        "permissions": user.get("permissions", {}),
        "picture": user.get("picture")
    }
    
    return {
        "message": "Login exitoso",
        "session_token": session_token,
        "user": user_response
    }

# ==================== ADMIN ENDPOINTS ====================

@api_router.get("/admin/users")
async def get_all_users(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver la lista de usuarios")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users

@api_router.put("/admin/users/{user_id}/permissions")
async def update_user_permissions(user_id: str, permissions: dict, authorization: Optional[str] = Header(None)):
    """Actualizar permisos de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar permisos")
    
    # Verificar que el usuario existe
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar permisos
    valid_permissions = {}
    for module in AVAILABLE_MODULES:
        if module in permissions:
            level = permissions[module]
            if level in PERMISSION_LEVELS:
                valid_permissions[module] = level
            else:
                valid_permissions[module] = "read"
        else:
            valid_permissions[module] = user.get("permissions", {}).get(module, "read")
    
    # Actualizar permisos
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"permissions": valid_permissions}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Permisos actualizados", "user": updated_user}

@api_router.put("/admin/users/{user_id}/role")
async def update_user_role(user_id: str, role: str, authorization: Optional[str] = Header(None)):
    """Actualizar rol de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar roles")
    
    # No permitir que el admin se quite el rol a sí mismo
    if current_user["user_id"] == user_id and role != "admin":
        raise HTTPException(status_code=400, detail="No puede quitarse el rol de administrador a sí mismo")
    
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Use 'admin' o 'user'")
    
    # Verificar que el usuario existe
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"role": role}}
    )
    
    return {"message": f"Rol actualizado a '{role}'"}

@api_router.put("/admin/users/{user_id}/status")
async def update_user_status(user_id: str, is_active: bool, authorization: Optional[str] = Header(None)):
    """Activar/desactivar un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar el estado de usuarios")
    
    # No permitir que el admin se desactive a sí mismo
    if current_user["user_id"] == user_id and not is_active:
        raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_active": is_active}}
    )
    
    # Si se desactiva, eliminar todas sus sesiones
    if not is_active:
        await db.user_sessions.delete_many({"user_id": user_id})
    
    return {"message": f"Usuario {'activado' if is_active else 'desactivado'}"}

@api_router.put("/admin/users/{user_id}")
async def update_user(user_id: str, user_data: UserUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar datos de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar usuarios")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Construir datos de actualización
    update_data = {}
    if user_data.first_name is not None:
        update_data["first_name"] = user_data.first_name
    if user_data.last_name is not None:
        update_data["last_name"] = user_data.last_name
    if user_data.first_name or user_data.last_name:
        fn = user_data.first_name or user.get("first_name", "")
        ln = user_data.last_name or user.get("last_name", "")
        update_data["name"] = f"{fn} {ln}"
    if user_data.cedula is not None:
        # Verificar que no exista otro usuario con esa cédula
        existing = await db.users.find_one({"cedula": user_data.cedula, "user_id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cédula")
        update_data["cedula"] = user_data.cedula
    if user_data.phone is not None:
        update_data["phone"] = user_data.phone
    if user_data.cargo is not None:
        update_data["cargo"] = user_data.cargo
    if user_data.departamento is not None:
        if user_data.departamento not in DEPARTAMENTOS and user_data.departamento != "":
            raise HTTPException(status_code=400, detail=f"Departamento inválido. Opciones: {DEPARTAMENTOS}")
        update_data["departamento"] = user_data.departamento
    if user_data.sede is not None:
        if user_data.sede not in ["TBP", "LCH"]:
            raise HTTPException(status_code=400, detail="Sede inválida. Use 'TBP' o 'LCH'")
        update_data["sede"] = user_data.sede
    if user_data.role is not None:
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Rol inválido. Use 'admin' o 'user'")
        # No permitir quitarse rol de admin a sí mismo
        if current_user["user_id"] == user_id and user_data.role != "admin":
            raise HTTPException(status_code=400, detail="No puede quitarse el rol de administrador")
        update_data["role"] = user_data.role
    if user_data.is_active is not None:
        if current_user["user_id"] == user_id and not user_data.is_active:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta")
        update_data["is_active"] = user_data.is_active
        if not user_data.is_active:
            await db.user_sessions.delete_many({"user_id": user_id})
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["user_id"]
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    # Registrar auditoría
    audit_log = {
        "action": "user_updated",
        "user_id": user_id,
        "changes": list(update_data.keys()),
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Usuario actualizado", "user": updated_user}

@api_router.post("/admin/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, authorization: Optional[str] = Header(None)):
    """Enviar token de restablecimiento de contraseña (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden restablecer contraseñas")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Generar token de un solo uso
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Guardar token en la base de datos
    await db.password_reset_tokens.delete_many({"user_id": user_id})  # Eliminar tokens anteriores
    await db.password_reset_tokens.insert_one({
        "user_id": user_id,
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["user_id"]
    })
    
    # Registrar auditoría
    audit_log = {
        "action": "password_reset_requested",
        "user_id": user_id,
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    # TODO: Enviar email con el token cuando Resend esté configurado
    # Por ahora, devolver el token para pruebas
    return {
        "message": "Token de restablecimiento generado",
        "email": user.get("email"),
        "reset_token": reset_token,  # En producción, esto NO se devuelve
        "expires_at": expires_at.isoformat(),
        "note": "El token debe ser enviado por correo electrónico al usuario"
    }

@api_router.post("/admin/users/create")
async def admin_create_user(user_data: UserRegister, authorization: Optional[str] = Header(None)):
    """Crear un nuevo usuario desde el panel de administración"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear usuarios")
    
    # Verificar si el email ya existe
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo electrónico")
    
    # Verificar si la cédula ya existe
    existing_cedula = await db.users.find_one({"cedula": user_data.cedula}, {"_id": 0})
    if existing_cedula:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cédula")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(user_data.password)
    
    valid_sedes = ["TBP", "LCH"]
    sede = user_data.sede.upper() if user_data.sede else "TBP"
    if sede not in valid_sedes:
        raise HTTPException(status_code=400, detail="Sede inválida")
    
    default_permissions = {}
    for module in AVAILABLE_MODULES:
        default_permissions[module] = "read"
    
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "password_hash": password_hash,
        "role": "user",
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions,
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["user_id"]
    }
    
    await db.users.insert_one(user_doc)
    
    # Registrar auditoría
    audit_log = {
        "action": "user_created",
        "user_id": user_id,
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    # Respuesta sin password
    user_response = {k: v for k, v in user_doc.items() if k != "password_hash"}
    return {"message": "Usuario creado exitosamente", "user": user_response}

@api_router.get("/admin/users/{user_id}/audit")
async def get_user_audit_log(user_id: str, authorization: Optional[str] = Header(None)):
    """Obtener historial de auditoría de un usuario"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver auditorías")
    
    logs = await db.audit_logs.find(
        {"user_id": user_id}, 
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    
    return logs

@api_router.get("/admin/departamentos")
async def get_departamentos(authorization: Optional[str] = Header(None)):
    """Obtener lista de departamentos disponibles"""
    await get_current_user(authorization)
    return DEPARTAMENTOS

# ==================== CLIENTS ENDPOINTS ====================

@api_router.post("/clients")
async def create_client(client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    # Validar unicidad RIF + Sucursal
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal"},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    # Generate contacts IDs if not present
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    client = Client(**data)
    doc = client.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.get("/clients")
async def get_clients(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    clients = await db.clients.find({}, {"_id": 0}).to_list(1000)
    return clients

@api_router.get("/clients/template")
async def get_clients_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación para clientes"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    data = {
        'RIF': ['J-12345678-9', 'J-98765432-1', 'J-11223344-5'],
        'Sucursal': ['Principal', 'Sede Norte', 'Principal'],
        'Nombre Jurídico': ['Empresa Demo CA', 'Empresa Demo CA', 'Otra Empresa SRL'],
        'Nombre Fantasía': ['DemoCorp', 'DemoCorp Norte', 'OtraCorp'],
        'Segmento': ['Corporativo', 'Corporativo', 'Pymes'],
        'Dirección': ['Av. Libertador, Edif. Torre X, Caracas', 'CC San Ignacio, Valencia', ''],
        'Contacto Nombre': ['Carlos', 'Ana', 'Pedro'],
        'Contacto Apellido': ['Pérez', 'Ruiz', 'Gómez'],
        'Contacto Teléfono': ['0412-1234567', '0416-9876543', '0414-1112233'],
        'Contacto Email': ['carlos@demo.com', 'ana@demo.com', 'pedro@otra.com'],
        'Contacto Rol': ['Administrativo', 'Técnico', 'Financiero']
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        info_data = {
            'Campo': ['RIF *', 'Sucursal', 'Nombre Jurídico *', 'Nombre Fantasía', 'Segmento',
                       'Dirección', 'Contacto Nombre', 'Contacto Apellido', 'Contacto Teléfono',
                       'Contacto Email', 'Contacto Rol'],
            'Descripción': [
                'RIF del cliente (obligatorio)', 'Nombre de la sucursal (def: Principal)',
                'Razón social (obligatorio)', 'Nombre comercial',
                'Pymes, Corporativo o Mixto (def: Pymes)',
                'Dirección fiscal', 'Nombre del contacto principal',
                'Apellido del contacto', 'Teléfono del contacto',
                'Email del contacto', 'Administrativo, Financiero, Técnico, Cuentas por Pagar, Operativo'
            ],
            'Obligatorio': ['Sí', 'No', 'Sí', 'No', 'No', 'No', 'No', 'No', 'No', 'No', 'No'],
            'Ejemplo': ['J-12345678-9', 'Principal', 'Empresa Demo CA', 'DemoCorp', 'Corporativo',
                        'Av. Libertador...', 'Carlos', 'Pérez', '0412-1234567', 'carlos@demo.com', 'Administrativo']
        }
        pd.DataFrame(info_data).to_excel(writer, index=False, sheet_name='Instrucciones')
        
        roles_data = {
            'Roles Válidos': ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo'],
            'Segmentos Válidos': ['Pymes', 'Corporativo', 'Mixto', '', ''],
            'Nota': [
                'RIF + Sucursal deben ser únicos',
                'Se permite el mismo RIF con diferente Sucursal',
                'Los campos marcados con * son obligatorios',
                'Si no indica segmento, se asigna "Pymes"',
                'Si no indica rol, se asigna "Administrativo"'
            ]
        }
        pd.DataFrame(roles_data).to_excel(writer, index=False, sheet_name='Valores Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_clientes.xlsx"}
    )

@api_router.get("/clients/{client_id}")
async def get_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@api_router.put("/clients/{client_id}")
async def update_client(client_id: str, client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    # Validar unicidad RIF + Sucursal (excluyendo el propio registro)
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal", "client_id": {"$ne": client_id}},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe otro cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    result = await db.clients.update_one(
        {"client_id": client_id},
        {"$set": data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_client(client_id, authorization)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones vinculadas
    quotes_count = await db.quotes.count_documents({"client_id": client_id})
    if quotes_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el cliente porque tiene {quotes_count} cotización(es) vinculada(s). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.clients.delete_one({"client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    # También eliminar los logs de bitácora del cliente
    await db.client_logs.delete_many({"client_id": client_id})
    return {"message": "Cliente eliminado exitosamente"}

# ==================== BITÁCORA DE CLIENTES ====================

@api_router.get("/clients/{client_id}/logs")
async def get_client_logs(client_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene la bitácora de eventos de un cliente (ordenada por fecha desc)"""
    await get_current_user(authorization)
    logs = await db.client_logs.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return logs

@api_router.post("/clients/{client_id}/logs")
async def create_client_log(client_id: str, log_data: ClientLogCreate, authorization: Optional[str] = Header(None)):
    """Crea una entrada en la bitácora de un cliente (no editable)"""
    current_user = await get_current_user(authorization)
    
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    log_entry = {
        "log_id": f"log_{uuid.uuid4().hex[:12]}",
        "client_id": client_id,
        "contact_date": log_data.contact_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "detail": log_data.detail,
        "action": log_data.action,
        "follow_up_date": log_data.follow_up_date,
        "is_completed": False,
        "created_by": current_user.get("email", "unknown"),
        "created_by_name": current_user.get("full_name", current_user.get("email", "")),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.client_logs.insert_one(log_entry)
    log_entry.pop("_id", None)
    return log_entry

@api_router.patch("/clients/logs/{log_id}/complete")
async def toggle_log_complete(log_id: str, authorization: Optional[str] = Header(None)):
    """Marca/desmarca un log como completado"""
    await get_current_user(authorization)
    log = await db.client_logs.find_one({"log_id": log_id}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Entrada de bitácora no encontrada")
    new_status = not log.get("is_completed", False)
    await db.client_logs.update_one({"log_id": log_id}, {"$set": {"is_completed": new_status}})
    return {"log_id": log_id, "is_completed": new_status}

# ==================== DASHBOARD ALERTS ====================

@api_router.get("/dashboard/alerts")
async def get_dashboard_alerts(authorization: Optional[str] = Header(None)):
    """Obtiene alertas de seguimiento para el dashboard"""
    await get_current_user(authorization)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_later = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Obtener logs con fecha de seguimiento pendiente (no completados)
    logs = await db.client_logs.find(
        {"follow_up_date": {"$ne": None}, "is_completed": {"$ne": True}},
        {"_id": 0}
    ).sort("follow_up_date", 1).to_list(200)
    
    # Clasificar por semáforo
    overdue = []  # Rojo
    today_list = []  # Amarillo
    upcoming = []  # Verde
    
    # Obtener info de clientes para enriquecer las alertas
    client_ids = list(set(log["client_id"] for log in logs))
    clients_map = {}
    if client_ids:
        clients = await db.clients.find({"client_id": {"$in": client_ids}}, {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1, "sucursal": 1}).to_list(200)
        clients_map = {c["client_id"]: c for c in clients}
    
    for log in logs:
        fd = log.get("follow_up_date", "")
        if not fd:
            continue
        client_info = clients_map.get(log["client_id"], {})
        enriched = {
            **log,
            "client_name": client_info.get("fantasy_name") or client_info.get("legal_name", "—"),
            "client_rif": client_info.get("rif", ""),
            "client_sucursal": client_info.get("sucursal", "")
        }
        if fd < today:
            enriched["priority"] = "overdue"
            overdue.append(enriched)
        elif fd == today:
            enriched["priority"] = "today"
            today_list.append(enriched)
        elif fd <= week_later:
            enriched["priority"] = "upcoming"
            upcoming.append(enriched)
    
    return {
        "overdue": overdue,
        "today": today_list,
        "upcoming": upcoming,
        "total": len(overdue) + len(today_list) + len(upcoming)
    }

@api_router.post("/clients/import")
async def import_clients(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                message='Formato de archivo no soportado', suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        column_mapping = {
            'nombre_jurídico': 'legal_name', 'nombre_juridico': 'legal_name',
            'nombre_fantasía': 'fantasy_name', 'nombre_fantasia': 'fantasy_name',
            'segmento': 'segment', 'dirección': 'address', 'direccion': 'address',
            'contacto_nombre': 'contact_name', 'contacto_apellido': 'contact_lastname',
            'contacto_teléfono': 'contact_phone', 'contacto_telefono': 'contact_phone',
            'contacto_email': 'contact_email', 'contacto_rol': 'contact_role',
            # Legacy support
            'contacto1_nombre': 'contact_name', 'contacto1_teléfono': 'contact_phone',
            'contacto1_telefono': 'contact_phone', 'contacto1_email': 'contact_email'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        required_columns = ['rif', 'legal_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None, error_type='missing',
                    message='Columnas requeridas no encontradas',
                    suggested_action='Descargue la plantilla y use las columnas: RIF, Nombre Jurídico')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        valid_segments = ['Pymes', 'Corporativo', 'Mixto']
        valid_roles = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo']
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                rif = str(row.get('rif', '')).strip() if pd.notna(row.get('rif')) else ''
                legal_name = str(row.get('legal_name', '')).strip() if pd.notna(row.get('legal_name')) else ''
                fantasy_name = str(row.get('fantasy_name', '')).strip() if pd.notna(row.get('fantasy_name')) else ''
                segment = str(row.get('segment', 'Pymes')).strip() if pd.notna(row.get('segment')) else 'Pymes'
                sucursal = str(row.get('sucursal', 'Principal')).strip() if pd.notna(row.get('sucursal')) else 'Principal'
                address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else ''
                
                row_errors = []
                
                if not rif:
                    row_errors.append(ImportError(row=row_num, column='RIF', value='(vacío)',
                        error_type='missing', message='El RIF es obligatorio',
                        suggested_action='Ingrese un RIF válido'))
                
                if not legal_name:
                    row_errors.append(ImportError(row=row_num, column='Nombre Jurídico', value='(vacío)',
                        error_type='missing', message='El nombre jurídico es obligatorio',
                        suggested_action='Ingrese el nombre jurídico del cliente'))
                
                if segment not in valid_segments:
                    segment = 'Pymes'
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados con llave compuesta RIF + Sucursal
                existing = await db.clients.find_one({"rif": rif, "sucursal": sucursal})
                if existing:
                    errors.append(ImportError(row=row_num, column='RIF + Sucursal', value=f'{rif} / {sucursal}',
                        error_type='duplicate', message=f'Ya existe un cliente con RIF {rif} y sucursal "{sucursal}"',
                        suggested_action='Cambie la sucursal o verifique si desea actualizar el registro'))
                    skipped_count += 1
                    continue
                
                # Construir contactos CRM
                contacts_crm = []
                contact_name = str(row.get('contact_name', '')).strip() if pd.notna(row.get('contact_name')) else ''
                contact_lastname = str(row.get('contact_lastname', '')).strip() if pd.notna(row.get('contact_lastname')) else ''
                contact_phone = str(row.get('contact_phone', '')).strip() if pd.notna(row.get('contact_phone')) else ''
                contact_email = str(row.get('contact_email', '')).strip() if pd.notna(row.get('contact_email')) else ''
                contact_role = str(row.get('contact_role', 'Administrativo')).strip() if pd.notna(row.get('contact_role')) else 'Administrativo'
                if contact_role not in valid_roles:
                    contact_role = 'Administrativo'
                
                if contact_name:
                    contacts_crm.append({
                        "contact_id": f"cnt_{uuid.uuid4().hex[:8]}",
                        "first_name": contact_name,
                        "last_name": contact_lastname,
                        "phone": contact_phone,
                        "email": contact_email,
                        "role": contact_role
                    })
                
                client = Client(
                    rif=rif,
                    legal_name=legal_name,
                    fantasy_name=fantasy_name,
                    segment=segment,
                    sucursal=sucursal,
                    address=address,
                    contacts=contacts_crm,
                    contact1=Contact(name=f'{contact_name} {contact_lastname}'.strip() or 'N/A', phone=contact_phone or 'N/A', email=contact_email or 'sin@email.com'),
                    contact2=Contact(name='N/A', phone='N/A', email='sin@email.com')
                )
                
                doc = client.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.clients.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} clientes importados correctamente.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors, message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=None, error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté corrupto')],
            message=f'Error: {str(e)}'
        )


@api_router.get("/clients/export/pdf")
async def export_clients_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    clients = await db.clients.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Clientes - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['RIF', 'Nombre Jurídico', 'Nombre Fantasía', 'Segmento', 'Contacto']]
    for c in clients:
        contact_name = c.get('contact1', {}).get('name', 'N/A') if isinstance(c.get('contact1'), dict) else 'N/A'
        data.append([
            c['rif'][:15],
            c['legal_name'][:25],
            c['fantasy_name'][:20],
            c.get('segment', 'N/A'),
            contact_name[:20]
        ])
    
    table = Table(data, colWidths=[1.2*inch, 2*inch, 1.5*inch, 1*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=clientes.pdf"}
    )

# ==================== BANKS ENDPOINTS ====================

@api_router.post("/banks", response_model=Bank)
async def create_bank(bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    bank = Bank(**bank_data.model_dump())
    doc = bank.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.banks.insert_one(doc)
    return bank

@api_router.get("/banks", response_model=List[Bank])
async def get_banks(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    banks = await db.banks.find({}, {"_id": 0}).to_list(1000)
    for bank in banks:
        if isinstance(bank['created_at'], str):
            bank['created_at'] = datetime.fromisoformat(bank['created_at'])
    return banks

@api_router.put("/banks/{bank_id}", response_model=Bank)
async def update_bank(bank_id: str, bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.banks.update_one(
        {"bank_id": bank_id},
        {"$set": bank_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if isinstance(bank['created_at'], str):
        bank['created_at'] = datetime.fromisoformat(bank['created_at'])
    return bank

@api_router.delete("/banks/{bank_id}")
async def delete_bank(bank_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este banco
    quotes_with_bank = await db.quotes.count_documents({
        "$or": [
            {"sponsor_bank_id": bank_id},
            {"services.bank_id": bank_id}
        ]
    })
    if quotes_with_bank > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el banco porque está asociado a {quotes_with_bank} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.banks.delete_one({"bank_id": bank_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    return {"message": "Banco eliminado exitosamente"}

@api_router.post("/banks/import", response_model=ImportResult)
async def import_banks(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Validar formato de archivo
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Leer archivo
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Mapeo de columnas
        column_mapping = {
            'nombre': 'name', 'tipo': 'type', 'país': 'country', 'pais': 'country'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columnas requeridas
        if 'name' not in df.columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='name', value=None, error_type='missing',
                    message='Columna "Nombre" no encontrada',
                    suggested_action='Asegúrese de que el archivo tenga la columna: Nombre')],
                message='Error: Falta columna requerida (Nombre)'
            )
        
        valid_types = ['Banco', 'Fintech']
        valid_countries = ['Venezuela', 'Estados Unidos']
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                bank_type = str(row.get('type', 'Banco')).strip() if pd.notna(row.get('type')) else 'Banco'
                country = str(row.get('country', 'Venezuela')).strip() if pd.notna(row.get('country')) else 'Venezuela'
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del banco es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Validar tipo (usar default si no es válido)
                if bank_type not in valid_types:
                    bank_type = 'Banco'
                
                # Validar país (usar default si no es válido)
                if country not in valid_countries:
                    country = 'Venezuela'
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.banks.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un banco con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear banco
                bank = Bank(name=name, type=bank_type, country=country, products=[])
                doc = bank.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.banks.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        # Determinar estado final
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} bancos importados correctamente.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors, message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=None, error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté corrupto')],
            message=f'Error: {str(e)}'
        )

@api_router.get("/banks/export/pdf")
async def export_banks_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    banks = await db.banks.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Bancos y Entidades - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Banco', 'Tipo', 'País', 'Productos']]
    for b in banks:
        products_str = ', '.join([p['product_name'] for p in b.get('products', [])][:3])
        if len(b.get('products', [])) > 3:
            products_str += f" (+{len(b['products']) - 3} más)"
        data.append([
            b['name'][:30],
            b['type'],
            b['country'],
            products_str[:40] if products_str else 'Sin productos'
        ])
    
    table = Table(data, colWidths=[2*inch, 1*inch, 1.2*inch, 2.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B7D4E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bancos.pdf"}
    )

# ==================== COMPONENT TYPES ENDPOINTS ====================

@api_router.post("/component-types", response_model=ComponentType)
async def create_component_type(component_data: ComponentTypeCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    component = ComponentType(**component_data.model_dump())
    doc = component.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.component_types.insert_one(doc)
    return component

@api_router.get("/component-types", response_model=List[ComponentType])
async def get_component_types(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    components = await db.component_types.find({}, {"_id": 0}).to_list(1000)
    for comp in components:
        if isinstance(comp['created_at'], str):
            comp['created_at'] = datetime.fromisoformat(comp['created_at'])
    return components

@api_router.delete("/component-types/{component_id}")
async def delete_component_type(component_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.component_types.delete_one({"component_id": component_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Component type not found")
    return {"message": "Component type deleted successfully"}

# ==================== HARDWARE ENDPOINTS ====================

@api_router.post("/hardware", response_model=Hardware)
async def create_hardware(hardware_data: HardwareCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    hardware = Hardware(**hardware_data.model_dump())
    doc = hardware.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.hardware.insert_one(doc)
    return hardware

@api_router.get("/hardware", response_model=List[Hardware])
async def get_hardware(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    for hw in hardware_list:
        if isinstance(hw['created_at'], str):
            hw['created_at'] = datetime.fromisoformat(hw['created_at'])
    return hardware_list

@api_router.put("/hardware/{hardware_id}", response_model=Hardware)
async def update_hardware(hardware_id: str, hardware_data: HardwareCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.hardware.update_one(
        {"hardware_id": hardware_id},
        {"$set": hardware_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Hardware not found")
    hardware = await db.hardware.find_one({"hardware_id": hardware_id}, {"_id": 0})
    if isinstance(hardware['created_at'], str):
        hardware['created_at'] = datetime.fromisoformat(hardware['created_at'])
    return hardware

@api_router.delete("/hardware/{hardware_id}")
async def delete_hardware(hardware_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este dispositivo
    quotes_with_hardware = await db.quotes.count_documents({
        "$or": [
            {"pinpad_id": hardware_id},
            {"hardware.hardware_id": hardware_id}
        ]
    })
    if quotes_with_hardware > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el dispositivo porque está asociado a {quotes_with_hardware} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.hardware.delete_one({"hardware_id": hardware_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Hardware not found")
    return {"message": "Dispositivo eliminado exitosamente"}

# ==================== HARDWARE IMPORT/EXPORT ====================

@api_router.post("/hardware/import", response_model=ImportResult)
async def import_hardware(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Importar bienes y servicios desde archivo Excel/CSV"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Validar formato de archivo
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Leer archivo
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Mapeo de columnas
        column_mapping = {
            'nombre': 'name', 'tipo': 'type', 'categoría': 'category', 'categoria': 'category',
            'precio_usd': 'price_usd', 'precio_efectivo': 'price_usd',
            'precio_bs_usd': 'price_bs_usd', 'precio_transferencia': 'price_bs_usd',
            'descripción': 'description', 'descripcion': 'description'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columna requerida
        if 'name' not in df.columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='name', value=None, error_type='missing',
                    message='Columna "Nombre" no encontrada',
                    suggested_action='Asegúrese de que el archivo tenga la columna: Nombre')],
                message='Error: Falta columna requerida (Nombre)'
            )
        
        # Tipos válidos
        valid_types = ['Pinpad', 'POS', 'Cable', 'Base', 'Accesorio', 'Mantenimiento', 'Licencia', 'Consultoria', 'Componente', 'Pieza']
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                hw_type = str(row.get('type', 'Accesorio')).strip() if pd.notna(row.get('type')) else 'Accesorio'
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Validar tipo (usar default si no es válido)
                if hw_type not in valid_types:
                    hw_type = 'Accesorio'
                
                # Parsear precios
                try:
                    price_usd = float(row.get('price_usd', 0)) if pd.notna(row.get('price_usd')) else 0.0
                except (ValueError, TypeError):
                    price_usd = 0.0
                
                try:
                    price_bs_usd = float(row.get('price_bs_usd', 0)) if pd.notna(row.get('price_bs_usd')) else 0.0
                except (ValueError, TypeError):
                    price_bs_usd = 0.0
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.hardware.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un registro con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear hardware
                hardware = Hardware(
                    name=name, 
                    type=hw_type, 
                    price_usd=price_usd, 
                    price_bs_usd=price_bs_usd,
                    description=description
                )
                doc = hardware.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.hardware.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        # Determinar estado final
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} registros importados correctamente.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors, message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=None, error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté corrupto')],
            message=f'Error: {str(e)}'
        )

@api_router.get("/hardware/export/excel")
async def export_hardware_excel(authorization: Optional[str] = Header(None)):
    """Exportar bienes y servicios a Excel"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    
    # Crear DataFrame
    data = []
    for h in hardware_list:
        data.append({
            'Nombre': h.get('name', ''),
            'Tipo': h.get('type', ''),
            'Precio Efectivo (USD)': h.get('price_usd', 0),
            'Precio Bs/USD': h.get('price_bs_usd', 0),
            'Descripción': h.get('description', '')
        })
    
    df = pd.DataFrame(data)
    
    # Crear archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Bienes y Servicios')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bienes_servicios.xlsx"}
    )

@api_router.get("/hardware/export/pdf")
async def export_hardware_pdf(authorization: Optional[str] = Header(None)):
    """Exportar bienes y servicios a PDF"""
    await get_current_user(authorization)
    
    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Bienes y Servicios - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Nombre', 'Tipo', 'Precio USD', 'Precio Bs/USD', 'Descripción']]
    for h in hardware_list:
        data.append([
            h.get('name', '')[:30],
            h.get('type', ''),
            f"${h.get('price_usd', 0):.2f}",
            f"${h.get('price_bs_usd', 0):.2f}",
            (h.get('description', '') or '')[:25]
        ])
    
    table = Table(data, colWidths=[2*inch, 1*inch, 1*inch, 1*inch, 1.7*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bienes_servicios.pdf"}
    )

@api_router.get("/hardware/template")
async def get_hardware_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación para bienes y servicios"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    # Crear plantilla con datos de ejemplo
    data = {
        'Nombre': ['Pinpad V240m', 'Cable USB', 'Servicio Mantenimiento'],
        'Tipo': ['Pinpad', 'Cable', 'Mantenimiento'],
        'Precio Efectivo (USD)': [150.00, 5.00, 50.00],
        'Precio Bs/USD': [165.00, 5.50, 55.00],
        'Descripción': ['Terminal de pago Verifone', 'Cable USB tipo A-B', 'Mantenimiento preventivo mensual']
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        # Añadir hoja con tipos válidos
        tipos_data = {
            'Tipos Válidos': ['Pinpad', 'POS', 'Cable', 'Base', 'Accesorio', 'Mantenimiento', 'Licencia', 'Consultoria', 'Componente', 'Pieza'],
            'Descripción': [
                'Dispositivos Pinpad',
                'Terminales POS',
                'Cables de conexión',
                'Bases y soportes',
                'Accesorios varios',
                'Servicios de mantenimiento',
                'Licencias de software',
                'Servicios de consultoría',
                'Componentes electrónicos',
                'Piezas mecánicas'
            ]
        }
        pd.DataFrame(tipos_data).to_excel(writer, index=False, sheet_name='Tipos Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_bienes_servicios.xlsx"}
    )

# ==================== SERVICES ENDPOINTS ====================

@api_router.post("/services", response_model=Service)
async def create_service(service_data: ServiceCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    service = Service(**service_data.model_dump())
    doc = service.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.services.insert_one(doc)
    return service

@api_router.get("/services", response_model=List[Service])
async def get_services(
    authorization: Optional[str] = Header(None),
    compatibility: Optional[str] = None,
    application_type: Optional[str] = None
):
    await get_current_user(authorization)
    
    query = {}
    if compatibility:
        compatibility_lower = compatibility.lower()
        if compatibility_lower == 'vpos':
            query['vpos_enabled'] = True
        elif compatibility_lower == 'gateway':
            query['gateway_enabled'] = True
        elif compatibility_lower == 'mpos':
            query['mpos_enabled'] = True
        elif compatibility_lower == 'link':
            query['link_enabled'] = True
    
    # Filtrar por tipo de aplicación (setup, recurring, both)
    if application_type:
        if application_type == 'recurring_available':
            # Servicios que pueden ser recurrentes (recurring o both)
            query['application_type'] = {'$in': ['recurring', 'both']}
        else:
            query['application_type'] = application_type
    
    services = await db.services.find(query, {"_id": 0}).to_list(1000)
    for srv in services:
        if isinstance(srv['created_at'], str):
            srv['created_at'] = datetime.fromisoformat(srv['created_at'])
    return services

@api_router.put("/services/{service_id}", response_model=Service)
async def update_service(service_id: str, service_data: ServiceCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.services.update_one(
        {"service_id": service_id},
        {"$set": service_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    service = await db.services.find_one({"service_id": service_id}, {"_id": 0})
    if isinstance(service['created_at'], str):
        service['created_at'] = datetime.fromisoformat(service['created_at'])
    return service

@api_router.delete("/services/{service_id}")
async def delete_service(service_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este servicio
    quotes_with_service = await db.quotes.count_documents({
        "services.item_id": service_id
    })
    if quotes_with_service > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el medio de pago porque está asociado a {quotes_with_service} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    # Verificar si está vinculado a algún banco
    banks_with_service = await db.banks.count_documents({
        "products.service_id": service_id
    })
    if banks_with_service > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el medio de pago porque está configurado en {banks_with_service} banco(s). Elimine primero la asociación con los bancos."
        )
    
    result = await db.services.delete_one({"service_id": service_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Medio de pago eliminado exitosamente"}

@api_router.post("/services/import", response_model=ImportResult)
async def import_services(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Validar formato de archivo
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Leer archivo
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Mapeo de columnas
        column_mapping = {
            'nombre': 'name', 'categoría': 'category', 'categoria': 'category',
            'descripción': 'description', 'descripcion': 'description',
            'setup_convencional': 'setup_cost_conventional',
            'mensual_convencional': 'monthly_cost_conventional',
            'setup_outsourcing': 'setup_cost_outsourcing',
            'mensual_outsourcing': 'monthly_cost_outsourcing'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columna requerida
        if 'name' not in df.columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='name', value=None, error_type='missing',
                    message='Columna "Nombre" no encontrada',
                    suggested_action='Asegúrese de que el archivo tenga la columna: Nombre')],
                message='Error: Falta columna requerida (Nombre)'
            )
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                category = str(row.get('category', 'General')).strip() if pd.notna(row.get('category')) else 'General'
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del servicio es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Parsear costos con validación
                def parse_cost(value, field_name):
                    if pd.isna(value) or value == '':
                        return 0.0
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        row_errors.append(ImportError(row=row_num, column=field_name, value=str(value),
                            error_type='format', message='Valor numérico inválido',
                            suggested_action='Ingrese un número válido (ej: 100.50)'))
                        return 0.0
                
                setup_conv = parse_cost(row.get('setup_cost_conventional'), 'Setup Convencional')
                monthly_conv = parse_cost(row.get('monthly_cost_conventional'), 'Mensual Convencional')
                setup_outs = parse_cost(row.get('setup_cost_outsourcing'), 'Setup Outsourcing')
                monthly_outs = parse_cost(row.get('monthly_cost_outsourcing'), 'Mensual Outsourcing')
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.services.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un servicio con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear servicio
                service = Service(
                    category=category, name=name, description=description,
                    setup_cost_conventional=setup_conv, monthly_cost_conventional=monthly_conv,
                    setup_cost_outsourcing=setup_outs, monthly_cost_outsourcing=monthly_outs
                )
                doc = service.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.services.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        # Determinar estado final
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} servicios importados correctamente.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors, message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=None, error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté corrupto')],
            message=f'Error: {str(e)}'
        )

@api_router.get("/services/export/pdf")
async def export_services_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    services = await db.services.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Catálogo de Servicios - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Servicio', 'Setup Conv.', 'Mensual Conv.', 'Setup Out.', 'Mensual Out.']]
    for s in services:
        data.append([
            s['name'][:40],
            f"${s.get('setup_cost_conventional', 0):.2f}",
            f"${s.get('monthly_cost_conventional', 0):.2f}",
            f"${s.get('setup_cost_outsourcing', 0):.2f}",
            f"${s.get('monthly_cost_outsourcing', 0):.2f}"
        ])
    
    table = Table(data, colWidths=[2.5*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=servicios.pdf"}
    )

# ==================== EXCHANGE RATE ENDPOINTS ====================

@api_router.get("/exchange-rate/current")
async def get_current_exchange_rate(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    latest_rate = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
    
    if latest_rate:
        if isinstance(latest_rate['date'], str):
            latest_rate['date'] = datetime.fromisoformat(latest_rate['date'])
        
        rate_age = datetime.now(timezone.utc) - latest_rate['date'].replace(tzinfo=timezone.utc)
        if rate_age.total_seconds() < 86400:
            return latest_rate
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get("https://pydolarve.org/api/v1/dollar?page=bcv")
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                bcv_rate = float(data[0].get("price", 0))
                
                new_rate = {
                    "rate": bcv_rate,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source": "BCV"
                }
                
                await db.exchange_rates.insert_one(new_rate)
                
                new_rate['date'] = datetime.fromisoformat(new_rate['date'])
                return new_rate
    except Exception as e:
        if latest_rate:
            return latest_rate
        raise HTTPException(status_code=503, detail=f"Unable to fetch exchange rate: {str(e)}")

@api_router.post("/exchange-rate/update")
async def update_exchange_rate(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get("https://pydolarve.org/api/v1/dollar?page=bcv")
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                bcv_rate = float(data[0].get("price", 0))
                
                new_rate = {
                    "rate": bcv_rate,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source": "BCV"
                }
                
                await db.exchange_rates.insert_one(new_rate)
                new_rate['date'] = datetime.fromisoformat(new_rate['date'])
                
                return new_rate
            else:
                raise HTTPException(status_code=503, detail="No data received from BCV API")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch exchange rate: {str(e)}")

# ==================== QUOTES ENDPOINTS ====================

@api_router.post("/quotes", response_model=Quote)
async def create_quote(quote_data: QuoteCreate, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    
    exchange_rate_doc = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
    
    # Si no hay tasa de cambio, usar valor por defecto
    if not exchange_rate_doc:
        exchange_rate = 40.0  # Valor por defecto
    else:
        exchange_rate = exchange_rate_doc["rate"]
    
    # Calcular totales según el tipo de cotización
    if quote_data.quote_category == "equipment":
        # Cotización de equipos/accesorios
        subtotal_usd = sum(item.total_usd for item in quote_data.equipment_items)
        total_usd = subtotal_usd
    else:
        # Cotización de implementación (flujo original)
        subtotal_usd = sum(item.total_usd for item in quote_data.services) + sum(item.total_usd for item in quote_data.hardware)
        total_usd = subtotal_usd
    
    total_bs = total_usd * exchange_rate
    
    # Obtener la sede del usuario actual
    user_sede = current_user.get("sede", "TBP")
    
    quote_number = await generate_quote_number(user_sede)
    
    quote = Quote(
        quote_number=quote_number,
        client_id=quote_data.client_id,
        quote_category=quote_data.quote_category or "implementation",
        quote_type=quote_data.quote_type or "VPOS",
        equipment_type=quote_data.equipment_type,
        pricing_model=quote_data.pricing_model or "conventional",
        services=quote_data.services,
        hardware=quote_data.hardware,
        equipment_items=quote_data.equipment_items,
        subtotal_usd=subtotal_usd,
        total_usd=total_usd,
        exchange_rate=exchange_rate,
        total_bs=total_bs,
        notes=quote_data.notes,
        integrator_id=quote_data.integrator_id,
        integrator_name=quote_data.integrator_name,
        integrator_app_name=quote_data.integrator_app_name,
        pinpad_id=quote_data.pinpad_id,
        pinpad_model=quote_data.pinpad_model,
        sponsor_bank_id=quote_data.sponsor_bank_id,
        sponsor_bank_name=quote_data.sponsor_bank_name,
        cantidad_cajas=quote_data.cantidad_cajas,
        cantidad_bancos=quote_data.cantidad_bancos,
        sede=user_sede,  # Sede del usuario
        created_by_user_id=current_user.get("user_id")  # ID del usuario que crea
    )
    
    doc = quote.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.quotes.insert_one(doc)
    
    return quote

# Modelo para crear cotización con PDF
class QuoteCreateWithPDF(BaseModel):
    """Modelo combinado para crear cotización y generar PDF"""
    # Datos básicos de la cotización
    client_id: str
    quote_category: str = "implementation"
    quote_type: str = "VPOS"
    equipment_type: Optional[str] = None
    pricing_model: str = "conventional"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    equipment_items: List[EquipmentQuoteItem] = []
    notes: Optional[str] = None
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Datos para el PDF (diccionario flexible)
    pdf_data: Optional[dict] = None

@api_router.post("/quotes/create-with-pdf")
async def create_quote_with_pdf(data: QuoteCreateWithPDF, authorization: Optional[str] = Header(None)):
    """
    Crea una cotización y genera el PDF automáticamente.
    El PDF se almacena en el servidor y se guarda la URL en la cotización.
    """
    current_user = await get_current_user(authorization)
    
    try:
        exchange_rate_doc = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
        
        if not exchange_rate_doc:
            exchange_rate = 40.0
        else:
            exchange_rate = exchange_rate_doc["rate"]
        
        # Calcular totales
        if data.quote_category == "equipment":
            subtotal_usd = sum(item.total_usd for item in data.equipment_items)
            total_usd = subtotal_usd
        else:
            subtotal_usd = sum(item.total_usd for item in data.services) + sum(item.total_usd for item in data.hardware)
            total_usd = subtotal_usd
        
        total_bs = total_usd * exchange_rate
        
        # Obtener la sede del usuario actual
        user_sede = current_user.get("sede", "TBP")
        
        count = await db.quotes.count_documents({})
        quote_number = f"COT-{datetime.now().year}-{count + 1:03d}"
        quote_id = f"quo_{uuid.uuid4().hex[:12]}"
        
        # Generar PDF si se proporcionaron los datos
        quote_pdf_url = None
        if data.pdf_data:
            try:
                # Convertir dict a TemplateQuotePDFRequest
                pdf_request = TemplateQuotePDFRequest(**data.pdf_data)
                pdf_request.quote_number = quote_number
                
                # Obtener logo si existe
                logo_path = None
                logo_file = UPLOADS_DIR / "logo.png"
                if logo_file.exists():
                    logo_path = str(logo_file)
                
                # Crear generador
                generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
                
                # Generar PDF
                pdf_buffer = generator.generate()
                
                # Guardar PDF en el servidor
                pdf_filename = f"quote_{quote_id}_{quote_number.replace('-', '_')}.pdf"
                pdf_path = UPLOADS_DIR / pdf_filename
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_buffer.getvalue())
                
                quote_pdf_url = f"/uploads/{pdf_filename}"
                logging.info(f"PDF generado y almacenado: {quote_pdf_url}")
                
            except Exception as e:
                logging.error(f"Error generando PDF: {str(e)}")
                # Continuar sin PDF si falla la generación
        
        # Crear anexo automático para el PDF generado
        initial_attachments = []
        if quote_pdf_url:
            initial_attachments.append({
                "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
                "category": "Cotización",
                "filename": pdf_filename,
                "url": quote_pdf_url,
                "uploaded_by": current_user.get("email", "system"),
                "uploaded_by_name": current_user.get("full_name", "Sistema"),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": len(pdf_buffer.getvalue()) if pdf_buffer else 0,
                "content_type": "application/pdf"
            })
        
        # Crear la cotización
        quote = Quote(
            quote_id=quote_id,
            quote_number=quote_number,
            client_id=data.client_id,
            quote_category=data.quote_category or "implementation",
            quote_type=data.quote_type or "VPOS",
            equipment_type=data.equipment_type,
            pricing_model=data.pricing_model or "conventional",
            services=data.services,
            hardware=data.hardware,
            equipment_items=data.equipment_items,
            subtotal_usd=subtotal_usd,
            total_usd=total_usd,
            exchange_rate=exchange_rate,
            total_bs=total_bs,
            notes=data.notes,
            integrator_id=data.integrator_id,
            integrator_name=data.integrator_name,
            integrator_app_name=data.integrator_app_name,
            pinpad_id=data.pinpad_id,
            pinpad_model=data.pinpad_model,
            sponsor_bank_id=data.sponsor_bank_id,
            sponsor_bank_name=data.sponsor_bank_name,
            cantidad_cajas=data.cantidad_cajas,
            cantidad_bancos=data.cantidad_bancos,
            sede=user_sede,
            created_by_user_id=current_user.get("user_id"),
            quote_pdf_url=quote_pdf_url,
            attachments=initial_attachments
        )
        
        doc = quote.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.quotes.insert_one(doc)
        
        return {
            "quote": quote,
            "pdf_url": quote_pdf_url,
            "message": "Cotización creada exitosamente" + (" con PDF" if quote_pdf_url else "")
        }
        
    except Exception as e:
        logging.error(f"Error creando cotización con PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear cotización: {str(e)}")

@api_router.get("/quotes", response_model=List[Quote])
async def get_quotes(authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    
    # Filtrar por sede del usuario (admin puede ver todas)
    query = {}
    if current_user.get("role") != "admin":
        user_sede = current_user.get("sede", "TBP")
        query["sede"] = user_sede
    
    quotes = await db.quotes.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for quote in quotes:
        if isinstance(quote['created_at'], str):
            quote['created_at'] = datetime.fromisoformat(quote['created_at'])
        # Asegurar que cotizaciones antiguas sin sede tengan valor por defecto
        if 'sede' not in quote:
            quote['sede'] = 'TBP'
    return quotes

@api_router.get("/quotes/{quote_id}", response_model=Quote)
async def get_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if isinstance(quote['created_at'], str):
        quote['created_at'] = datetime.fromisoformat(quote['created_at'])
    return quote

@api_router.get("/quotes/{quote_id}/pdf")
async def generate_quote_pdf(quote_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("<b>COTIZACIÓN</b>", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    info_data = [
        ["Cotización #:", quote["quote_number"]],
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", client["legal_name"]],
        ["RIF:", client["rif"]],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    if quote["services"]:
        elements.append(Paragraph("<b>Servicios</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        service_data = [["Descripción", "Cantidad", "Precio Unit.", "Total"]]
        for item in quote["services"]:
            service_data.append([
                item["item_name"],
                str(item["quantity"]),
                f"${item['unit_price_usd']:.2f}",
                f"${item['total_usd']:.2f}"
            ])
        
        service_table = Table(service_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
        service_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(service_table)
        elements.append(Spacer(1, 0.3*inch))
    
    if quote["hardware"]:
        elements.append(Paragraph("<b>Hardware</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        hardware_data = [["Descripción", "Cantidad", "Precio Unit.", "Total"]]
        for item in quote["hardware"]:
            hardware_data.append([
                item["item_name"],
                str(item["quantity"]),
                f"${item['unit_price_usd']:.2f}",
                f"${item['total_usd']:.2f}"
            ])
        
        hardware_table = Table(hardware_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
        hardware_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(hardware_table)
        elements.append(Spacer(1, 0.3*inch))
    
    totals_data = [
        ["Subtotal (USD):", f"${quote['subtotal_usd']:.2f}"],
        ["Total (USD):", f"${quote['total_usd']:.2f}"],
        ["Tasa de Cambio:", f"{quote['exchange_rate']:.2f} Bs/USD"],
        ["Total (Bs):", f"{quote['total_bs']:.2f} Bs"]
    ]
    totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.black),
    ]))
    elements.append(totals_table)
    
    if quote.get("notes"):
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Notas:</b>", styles['Heading3']))
        elements.append(Paragraph(quote["notes"], styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=quote_{quote['quote_number']}.pdf"}
    )

class QuoteUpdate(BaseModel):
    """Modelo para actualizar cotización existente"""
    quote_type: Optional[str] = None
    client_id: Optional[str] = None
    pricing_model: Optional[str] = None
    services: Optional[List[QuoteItem]] = None
    hardware: Optional[List[QuoteItem]] = None
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    subtotal_usd: Optional[float] = None
    total_usd: Optional[float] = None
    descuento: Optional[float] = None
    exchange_rate: Optional[float] = None
    total_bs: Optional[float] = None
    notes: Optional[str] = None
    # Campos de cantidades a nivel de cotización
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None

@api_router.put("/quotes/{quote_id}")
async def update_quote(quote_id: str, quote_update: QuoteUpdate, authorization: Optional[str] = Header(None)):
    """Actualiza una cotización existente (solo en estado Borrador)"""
    await get_current_user(authorization)
    
    # Verificar que la cotización existe
    existing_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Solo permitir actualizar cotizaciones en estado Borrador
    if existing_quote.get("quote_status", "Borrador") != "Borrador":
        raise HTTPException(status_code=400, detail="Solo se pueden modificar cotizaciones en estado Borrador")
    
    # Preparar datos de actualización (solo campos proporcionados)
    update_data = {}
    update_fields = quote_update.model_dump(exclude_unset=True)
    
    for field, value in update_fields.items():
        if value is not None:
            update_data[field] = value
    
    # Calcular total_bs si se actualizó total_usd
    if "total_usd" in update_data:
        exchange_rate = update_data.get("exchange_rate", existing_quote.get("exchange_rate", 36.5))
        update_data["total_bs"] = update_data["total_usd"] * exchange_rate
    
    if update_data:
        result = await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Retornar cotización actualizada
    updated_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    return updated_quote

@api_router.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Elimina una cotización (función de mantenimiento - disponible en cualquier estado)"""
    print(f"[DELETE QUOTE] Recibida solicitud para eliminar quote_id: {quote_id}")
    
    await get_current_user(authorization)
    print("[DELETE QUOTE] Usuario autenticado correctamente")
    
    # Verificar que la cotización existe
    existing_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing_quote:
        print(f"[DELETE QUOTE] ERROR: Cotización no encontrada: {quote_id}")
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    quote_number = existing_quote.get("quote_number", quote_id)
    print(f"[DELETE QUOTE] Cotización encontrada: {quote_number}, procediendo a eliminar...")
    
    # Eliminar la cotización (sin restricción de estado - función de mantenimiento)
    result = await db.quotes.delete_one({"quote_id": quote_id})
    print(f"[DELETE QUOTE] Resultado de delete_one: deleted_count={result.deleted_count}")
    
    if result.deleted_count == 0:
        print("[DELETE QUOTE] ERROR: delete_one retornó 0")
        raise HTTPException(status_code=404, detail="Error al eliminar la cotización")
    
    print(f"[DELETE QUOTE] ÉXITO: Cotización {quote_number} eliminada")
    return {"message": f"Cotización {quote_number} eliminada exitosamente", "quote_id": quote_id}

@api_router.post("/quotes/generate-pdf")
async def generate_quote_pdf_from_data(data: QuotePDFRequest, authorization: Optional[str] = Header(None)):
    """Genera un PDF de cotización desde los datos del frontend sin guardar en BD"""
    await get_current_user(authorization)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = styles['Title']
    title_style.fontSize = 16
    elements.append(Paragraph("<b>COTIZACIÓN - Merchant Server</b>", title_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Información del cliente
    quote_type_names = {
        'VPOS': 'Cajas Registradoras (VPOS)',
        'GATEWAY': 'Ecommerce (Payment Gateway)',
        'MPOS': 'Tablet o Android (MPOS)',
        'LINK': 'Link de Pago'
    }
    pricing_model_names = {
        'conventional': 'Modelo Convencional',
        'outsourcing': 'Modelo Outsourcing'
    }
    
    info_data = [
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", data.cliente_nombre],
        ["RIF:", data.cliente_rif or "N/A"],
        ["Tipo de Servicio:", quote_type_names.get(data.quote_type, data.quote_type)],
        ["Modelo de Precios:", pricing_model_names.get(data.pricing_model, data.pricing_model)],
    ]
    
    # Agregar información de integración y hardware si está disponible
    if data.integrator_name:
        info_data.append(["Integrador:", f"{data.integrator_name} ({data.integrator_app_name})"])
    if data.pinpad_model:
        info_data.append(["Modelo de Pinpad:", data.pinpad_model])
    if data.sponsor_bank_name:
        info_data.append(["Entidad Patrocinadora:", data.sponsor_bank_name])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Función para crear tabla de items
    def create_items_table(items, header_color, title):
        if not items:
            return None
        
        elements.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.05*inch))
        
        table_data = [["N°", "Concepto", "Cajas", "Bancos", "Tarifa USD", "Total USD"]]
        subtotal = 0
        for i, item in enumerate(items, 1):
            total = item.cantidad_cajas * item.cantidad_bancos * item.tarifa
            subtotal += total
            table_data.append([
                str(i),
                item.concepto,
                str(item.cantidad_cajas),
                str(item.cantidad_bancos),
                f"${item.tarifa:.2f}",
                f"${total:.2f}"
            ])
        
        # Fila de subtotal
        table_data.append(["", "", "", "", "Subtotal:", f"${subtotal:.2f}"])
        
        item_table = Table(table_data, colWidths=[0.4*inch, 3*inch, 0.6*inch, 0.6*inch, 0.9*inch, 0.9*inch])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            # Estilo del subtotal
            ('FONTNAME', (4, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (4, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 0.15*inch))
        return subtotal
    
    # Sección SETUP (azul)
    subtotal_setup = create_items_table(data.setup_items, colors.Color(0.1, 0.4, 0.7), "INVERSIÓN INICIAL (SETUP)")
    if subtotal_setup is None:
        subtotal_setup = 0
    
    # Sección RECURRENTES BÁSICOS (verde)
    subtotal_rec_basic = create_items_table(data.recurring_basic_items, colors.Color(0.2, 0.6, 0.3), "COSTOS RECURRENTES - BÁSICOS")
    if subtotal_rec_basic is None:
        subtotal_rec_basic = 0
    
    # Sección OTROS RECURRENTES (teal)
    subtotal_rec_other = create_items_table(data.recurring_other_items, colors.Color(0.1, 0.5, 0.5), "OTROS RECURRENTES")
    if subtotal_rec_other is None:
        subtotal_rec_other = 0
    
    # Calcular totales
    subtotal_recurrente = subtotal_rec_basic + subtotal_rec_other
    descuento_setup = subtotal_setup * (data.descuento / 100)
    descuento_recurrente = subtotal_recurrente * (data.descuento / 100)
    total_setup = subtotal_setup - descuento_setup
    total_recurrente = subtotal_recurrente - descuento_recurrente
    total_general = total_setup + total_recurrente
    
    # Tabla de resumen final
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("<b>RESUMEN DE LA COTIZACIÓN</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.05*inch))
    
    summary_data = [
        ["Concepto", "Subtotal", "Descuento", "Total Neto"],
        ["Inversión Inicial (Setup)", f"${subtotal_setup:.2f}", f"-${descuento_setup:.2f}", f"${total_setup:.2f}"],
        ["Costos Recurrentes (Mensual)", f"${subtotal_recurrente:.2f}", f"-${descuento_recurrente:.2f}", f"${total_recurrente:.2f}"],
        ["", "", "TOTAL GENERAL:", f"${total_general:.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.3*inch, 1.3*inch, 1.3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        # Total general
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -1), (-1, -1), 11),
        ('BACKGROUND', (2, -1), (-1, -1), colors.Color(0.1, 0.4, 0.7)),
        ('TEXTCOLOR', (2, -1), (-1, -1), colors.whitesmoke),
    ]))
    elements.append(summary_table)
    
    # ==================== RESUMEN EJECUTIVO ====================
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("<b>RESUMEN EJECUTIVO</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Colores para la matriz
    color_amarillo = colors.Color(0.98, 0.75, 0.18)  # Amber/Amarillo
    color_azul = colors.Color(0.74, 0.85, 0.95)      # Azul claro
    color_verde = colors.Color(0.74, 0.93, 0.74)    # Verde claro
    
    # Cabecera del Resumen (Cliente, Cajas, Dirección)
    header_data = [
        ["Cliente", data.cliente_nombre],
        ["Cantidad de Cajas", str(data.cantidad_cajas)],
        ["Dirección Fiscal", data.cliente_address or "No especificada"],
    ]
    
    header_table = Table(header_data, colWidths=[1.5*inch, 5*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), color_amarillo),
        ('BACKGROUND', (0, 1), (0, 1), color_azul),
        ('BACKGROUND', (0, 2), (0, 2), color_verde),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.15*inch))
    
    # Matriz de Distribución (Bancos, Productos, Cajas)
    # Consolidar solo items con banco asociado (excluir conceptos base)
    bank_product_map = {}
    all_items = data.setup_items + data.recurring_basic_items + data.recurring_other_items
    
    for item in all_items:
        # Solo incluir items que tienen banco asociado (excluir conceptos base)
        if not item.bank_name:
            continue
            
        bank_name = item.bank_name
        product_name = item.concepto
        key = f"{bank_name}-{product_name}"
        
        if key not in bank_product_map:
            bank_product_map[key] = {
                "banco": bank_name,
                "producto": product_name,
                "cajas": 0
            }
        bank_product_map[key]["cajas"] += item.cantidad_cajas
    
    # Crear tabla de matriz
    matriz_data = [["Bancos", "Productos", "Cantidad de Cajas"]]
    total_terminales = 0
    
    for row in bank_product_map.values():
        matriz_data.append([row["banco"], row["producto"], str(row["cajas"])])
        total_terminales += row["cajas"]
    
    # Si no hay items, mostrar mensaje
    if len(matriz_data) == 1:
        matriz_data.append(["Sin medios de pago", "", "0"])
    
    matriz_table = Table(matriz_data, colWidths=[2.5*inch, 2.5*inch, 1.5*inch])
    matriz_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (0, 0), color_verde),
        ('BACKGROUND', (1, 0), (1, 0), color_azul),
        ('BACKGROUND', (2, 0), (2, 0), color_amarillo),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(matriz_table)
    
    # Total de Terminales Virtuales
    elements.append(Spacer(1, 0.05*inch))
    total_data = [["Total de Terminales Virtuales", str(total_terminales or data.cantidad_cajas)]]
    total_table = Table(total_data, colWidths=[5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(total_table)
    
    # Notas
    if data.notes:
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<b>Notas:</b>", styles['Heading3']))
        elements.append(Paragraph(data.notes, styles['Normal']))
    
    # Pie de página
    elements.append(Spacer(1, 0.3*inch))
    footer_style = styles['Normal']
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    elements.append(Paragraph("Este documento es una cotización y no representa un compromiso contractual.", footer_style))
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - Cotizador Merchant Server", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"cotizacion_{data.cliente_nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==================== GENERADOR DE PDF CON PLANTILLA ====================

class TemplateQuotePDFRequest(BaseModel):
    """Modelo para generar PDF usando plantilla configurada"""
    template_type: str = "vpos_pyme"  # Tipo de plantilla a usar
    # Datos del cliente (campos amarillos Página 1 y 2)
    cliente_nombre: str
    cliente_rif: str = ""
    cliente_contacto: str = ""  # Persona de contacto
    cliente_address: str = ""
    # Datos de la solicitud (campos amarillos)
    integrator_name: str = ""
    integrator_app_name: str = ""  # Nombre del Aplicativo de Caja
    pinpad_model: str = ""
    sponsor_bank_name: str = ""  # Patrocinador
    cantidad_cajas: int = 1
    # Número de cotización
    quote_number: str = ""
    # Items de cotización
    setup_items: List[QuotePDFItem] = []
    recurring_basic_items: List[QuotePDFItem] = []
    recurring_other_items: List[QuotePDFItem] = []
    additional_items: List[QuotePDFItem] = []  # Items de sesión setup (medios de pago con banco)
    descuento: float = 0
    notes: str = ""
    # Datos adicionales
    quote_type: str = "VPOS"
    pricing_model: str = "conventional"


# ==================== CLASE PARA PDF CON FLUJO DINÁMICO ====================

class DynamicQuotePDFGenerator:
    """Generador de PDF con flujo dinámico y salto de página automático"""
    
    # Colores corporativos
    COLOR_AZUL = colors.HexColor("#00447C")
    COLOR_VERDE = colors.HexColor("#28A745") 
    COLOR_VERDE_CLARO = colors.HexColor("#E8F5E9")
    COLOR_AZUL_CLARO = colors.HexColor("#E3F2FD")
    COLOR_GRIS = colors.HexColor("#F5F5F5")
    COLOR_TEXTO = colors.HexColor("#333333")
    
    def __init__(self, data: TemplateQuotePDFRequest, logo_path: Optional[str] = None):
        self.data = data
        self.logo_path = logo_path
        self.buffer = io.BytesIO()
        self.page_width, self.page_height = letter
        self.margin = 50
        self.styles = self._create_styles()
        
    def _create_styles(self):
        """Crear estilos personalizados para el documento"""
        styles = getSampleStyleSheet()
        
        # Título principal
        styles.add(ParagraphStyle(
            name='TituloPortada',
            fontName='Helvetica-Bold',
            fontSize=28,
            textColor=self.COLOR_AZUL,
            alignment=1,  # Centro
            spaceAfter=15
        ))
        
        # Subtítulo (más grande pero menor que el título)
        styles.add(ParagraphStyle(
            name='Subtitulo',
            fontName='Helvetica-Bold',
            fontSize=18,  # Aumentado de 14 a 18
            textColor=self.COLOR_AZUL,
            alignment=1,
            spaceAfter=10
        ))
        
        # Encabezado de sección
        styles.add(ParagraphStyle(
            name='SeccionHeader',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=self.COLOR_AZUL,
            spaceBefore=15,
            spaceAfter=8
        ))
        
        # Texto normal
        styles.add(ParagraphStyle(
            name='TextoNormal',
            fontName='Helvetica',
            fontSize=10,
            textColor=self.COLOR_TEXTO,
            leading=14,
            spaceAfter=6
        ))
        
        # Campo etiqueta
        styles.add(ParagraphStyle(
            name='CampoEtiqueta',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=self.COLOR_AZUL
        ))
        
        # Campo valor
        styles.add(ParagraphStyle(
            name='CampoValor',
            fontName='Helvetica',
            fontSize=10,
            textColor=self.COLOR_TEXTO
        ))
        
        # Pie de página
        styles.add(ParagraphStyle(
            name='PiePagina',
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.gray,
            alignment=1
        ))
        
        return styles
    
    def _header_footer(self, canvas, doc):
        """Añadir encabezado y pie de página a cada página"""
        canvas.saveState()
        
        # Encabezado - Logo y título
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                canvas.drawImage(self.logo_path, self.margin, self.page_height - 70, 
                               width=120, height=50, preserveAspectRatio=True)
            except:
                pass
        
        # Línea de encabezado
        canvas.setStrokeColor(self.COLOR_AZUL)
        canvas.setLineWidth(2)
        canvas.line(self.margin, self.page_height - 80, 
                   self.page_width - self.margin, self.page_height - 80)
        
        # Número de cotización en encabezado (derecha)
        if self.data.quote_number:
            canvas.setFont('Helvetica-Bold', 10)
            canvas.setFillColor(self.COLOR_AZUL)
            canvas.drawRightString(self.page_width - self.margin, self.page_height - 65, 
                                  f"Cotización: {self.data.quote_number}")
        
        # Pie de página
        canvas.setStrokeColor(self.COLOR_GRIS)
        canvas.setLineWidth(1)
        canvas.line(self.margin, 40, self.page_width - self.margin, 40)
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        canvas.drawCentredString(self.page_width / 2, 25, 
                                f"Cotizador Merchant Server - {datetime.now().strftime('%d/%m/%Y')}")
        canvas.drawRightString(self.page_width - self.margin, 25, f"Página {doc.page}")
        
        canvas.restoreState()
    
    def _create_info_table(self, data_pairs, col_widths=None):
        """Crear tabla de información con etiquetas y valores"""
        if col_widths is None:
            col_widths = [150, 300]
        
        table_data = []
        for label, value in data_pairs:
            table_data.append([
                Paragraph(f"<b>{label}:</b>", self.styles['CampoEtiqueta']),
                Paragraph(str(value) if value else "—", self.styles['CampoValor'])
            ])
        
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return table
    
    def _create_items_table(self, items, title, header_color, show_tax=True):
        """Crear tabla de items de cotización con desglose fiscal"""
        elements = []
        
        # Título de la sección
        elements.append(Paragraph(title, self.styles['SeccionHeader']))
        
        if not items:
            elements.append(Paragraph("No hay items en esta sección.", self.styles['TextoNormal']))
            return elements, 0
        
        # Preparar datos de la tabla
        table_data = [['N°', 'Concepto', 'Cajas', 'Bancos', 'Tarifa', 'Total']]
        
        subtotal = 0
        for i, item in enumerate(items, 1):
            total_item = item.cantidad_cajas * item.cantidad_bancos * item.tarifa
            subtotal += total_item
            
            table_data.append([
                str(i),
                item.concepto[:45] + ('...' if len(item.concepto) > 45 else ''),
                str(item.cantidad_cajas),
                str(item.cantidad_bancos),
                f"${item.tarifa:.2f}",
                f"${total_item:.2f}"
            ])
        
        # Crear tabla de items
        col_widths = [25, 230, 45, 45, 65, 75]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilos de la tabla
        style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            
            # Cuerpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # N°
            ('ALIGN', (2, 1), (5, -1), 'CENTER'),  # Números
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ])
        
        # Alternar colores de filas
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)
        
        table.setStyle(style)
        elements.append(table)
        
        # Tabla de totales fiscales (si show_tax es True)
        if show_tax:
            iva = subtotal * 0.16
            total_con_iva = subtotal + iva
            
            totals_data = [
                ['Subtotal:', f"${subtotal:.2f}"],
                ['IVA (16%):', f"${iva:.2f}"],
                ['Total:', f"${total_con_iva:.2f}"]
            ]
            
            totals_table = Table(totals_data, colWidths=[405, 75])
            totals_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LINEABOVE', (0, 0), (-1, 0), 1, header_color),
                ('BACKGROUND', (0, -1), (-1, -1), header_color),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ]))
            elements.append(totals_table)
        
        elements.append(Spacer(1, 10))
        
        return elements, subtotal
    
    def _create_bank_products_table(self):
        """Crear tabla de Bancos/Productos/Cajas para el resumen (estilo igual al frontend)
        IMPORTANTE: Usa SOLO additional_items (items de Sesion Setup con bank_name)"""
        elements = []
        
        # Colores para las celdas (igual que el frontend)
        COLOR_AMARILLO = colors.HexColor("#FBBF24")  # bg-amber-400
        COLOR_AZUL_CLARO = colors.HexColor("#BFDBFE")  # bg-blue-200
        COLOR_VERDE_CLARO = colors.HexColor("#BBF7D0")  # bg-green-200
        
        # ===== FILA 1: Cliente y Cantidad de Cajas en la misma fila (2 columnas) =====
        row1_data = [[
            # Celda 1: Cliente
            Table(
                [[Paragraph("<b>Cliente</b>", self.styles['CampoEtiqueta']), self.data.cliente_nombre]],
                colWidths=[90, 150]
            ),
            # Celda 2: Cantidad de Cajas
            Table(
                [[Paragraph("<b>Cantidad de Cajas</b>", self.styles['CampoEtiqueta']), str(self.data.cantidad_cajas)]],
                colWidths=[110, 120]
            )
        ]]
        
        # Crear tabla externa para la fila 1
        row1_table = Table(row1_data, colWidths=[245, 235])
        row1_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        # Estilizar las subtablas internas
        cliente_table = row1_data[0][0]
        cliente_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_AMARILLO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        cajas_table = row1_data[0][1]
        cajas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_AZUL_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(row1_table)
        elements.append(Spacer(1, 5))
        
        # ===== FILA 2: Dirección Fiscal (puede ser de 2 líneas si es muy larga) =====
        direccion = self.data.cliente_address or "No especificada"
        # Si la dirección es muy larga (más de 60 caracteres), permitir que fluya en múltiples líneas
        direccion_style = ParagraphStyle(
            'DireccionStyle',
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            wordWrap='LTR'
        )
        
        direccion_data = [[
            Paragraph("<b>Dirección Fiscal</b>", self.styles['CampoEtiqueta']),
            Paragraph(direccion, direccion_style)
        ]]
        
        direccion_table = Table(direccion_data, colWidths=[100, 380])
        direccion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(direccion_table)
        elements.append(Spacer(1, 12))
        
        # ===== TABLA DE BANCOS/PRODUCTOS/CAJAS =====
        # Usar SOLO additional_items (items de Sesion Setup con banco)
        bank_product_map = {}
        total_cajas = 0
        
        for item in self.data.additional_items:
            if item.bank_name:  # Solo items con banco asociado
                bank_name = item.bank_name
                # Usar el concepto completo como nombre del producto
                producto = item.concepto
                key = f"{bank_name}-{producto}"
                
                if key not in bank_product_map:
                    bank_product_map[key] = {
                        'bank': bank_name,
                        'product': producto,
                        'cajas': 0
                    }
                bank_product_map[key]['cajas'] += item.cantidad_cajas or 1
        
        # Calcular total de cajas
        for data in bank_product_map.values():
            total_cajas += data['cajas']
        
        # Si no hay items con banco, mostrar mensaje
        if not bank_product_map:
            elements.append(Paragraph("No hay medios de pago seleccionados", self.styles['TextoNormal']))
            elements.append(Spacer(1, 15))
            return elements
        
        # Crear tabla de Bancos/Productos/Cajas con colores de encabezado
        table_data = [['Bancos', 'Productos', 'Cantidad de Cajas']]
        
        for data in bank_product_map.values():
            table_data.append([data['bank'], data['product'], str(data['cajas'])])
        
        table = Table(table_data, colWidths=[160, 230, 90])
        table.setStyle(TableStyle([
            # Encabezados con colores
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_CLARO),  # Bancos - verde
            ('BACKGROUND', (1, 0), (1, 0), COLOR_AZUL_CLARO),   # Productos - azul
            ('BACKGROUND', (2, 0), (2, 0), COLOR_AMARILLO),     # Cantidad - amarillo
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        # Alternar colores de filas
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)]))
        
        elements.append(table)
        
        # Total de terminales virtuales
        total_display = total_cajas if total_cajas > 0 else self.data.cantidad_cajas
        total_data = [['Total de Terminales Virtuales:', str(total_display)]]
        total_table = Table(total_data, colWidths=[390, 90])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),  # bg-slate-100
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor("#94A3B8")),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def generate(self):
        """Generar el PDF completo con flujo dinámico"""
        
        # Meses en español
        MESES_ES = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        # Crear documento con flujo automático
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=100,  # Espacio para encabezado
            bottomMargin=60  # Espacio para pie de página
        )
        
        elements = []
        
        # Fecha actual en español
        now = datetime.now()
        fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"
        
        # ==================== PÁGINA 1: PORTADA ====================
        elements.append(Spacer(1, 80))
        elements.append(Paragraph("COTIZACIÓN DE SERVICIOS", self.styles['TituloPortada']))
        elements.append(Spacer(1, 10))  # Salto de línea entre título y subtítulo
        elements.append(Paragraph("Merchant Server - Plataforma de Pagos", self.styles['Subtitulo']))
        elements.append(Spacer(1, 40))
        
        # Información del proyecto
        info_portada = [
            ("Cliente", self.data.cliente_nombre),
            ("RIF", self.data.cliente_rif),
            ("Cantidad de Cajas", str(self.data.cantidad_cajas)),
            ("Integrador", self.data.integrator_name),
            ("Aplicativo de Caja", self.data.integrator_app_name),
            ("Modelo Pinpad", self.data.pinpad_model),
            ("Banco Patrocinador", self.data.sponsor_bank_name),
        ]
        elements.append(self._create_info_table(info_portada))
        elements.append(Spacer(1, 30))
        
        # Número de cotización (autogenerado) y fecha en español
        elements.append(Paragraph(
            f"<b>Número de Cotización:</b> {self.data.quote_number}", 
            self.styles['TextoNormal']
        ))
        elements.append(Paragraph(f"<b>Fecha:</b> {fecha_actual}", self.styles['TextoNormal']))
        
        # Salto de página
        elements.append(PageBreak())
        
        # ==================== PÁGINA 2: CUERPO DEL DOCUMENTO ====================
        # Carta de presentación
        carta_header = f"""
        <b>Señores:</b> {self.data.cliente_nombre}<br/>
        <b>RIF:</b> {self.data.cliente_rif}<br/>
        <b>Att:</b> {self.data.cliente_contacto or 'Departamento de Compras'}<br/><br/>
        """
        elements.append(Paragraph(carta_header, self.styles['TextoNormal']))
        
        # Texto corregido según solicitud del usuario
        carta_body = f"""
        Por medio de la presente, nos complace presentarle nuestra propuesta comercial para la implementación 
        de terminales virtuales de pago en sus puntos de venta. La solución propuesta se implementa con la 
        integración del Merchant Server con el aplicativo <b>{self.data.integrator_app_name}</b> desarrollado 
        por <b>{self.data.integrator_name}</b>, garantizando una experiencia de cobro segura y eficiente.
        """
        elements.append(Paragraph(carta_body, self.styles['TextoNormal']))
        elements.append(Spacer(1, 15))
        
        # RESUMEN EJECUTIVO (inmediatamente después del párrafo)
        elements.append(Paragraph("RESUMEN EJECUTIVO", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 8))
        
        # Tabla de resumen con estilo igual al frontend (Cliente/Cajas/Dirección + Bancos/Productos)
        elements.extend(self._create_bank_products_table())
        
        # Salto de página
        elements.append(PageBreak())
        
        # ==================== PÁGINA 3: COSTOS ====================
        # Costos de Setup con desglose fiscal
        setup_elements, subtotal_setup = self._create_items_table(
            self.data.setup_items, 
            "COSTOS DE IMPLEMENTACIÓN (SETUP)", 
            self.COLOR_AZUL,
            show_tax=True
        )
        elements.extend(setup_elements)
        
        # Costos Recurrentes con desglose fiscal
        all_recurring = self.data.recurring_basic_items + self.data.recurring_other_items
        recurring_elements, subtotal_recurrente = self._create_items_table(
            all_recurring, 
            "COSTOS RECURRENTES MENSUALES", 
            self.COLOR_VERDE,
            show_tax=True
        )
        elements.extend(recurring_elements)
        
        # Notas (si existen) - van en esta página
        if self.data.notes:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(f"<b>Notas:</b> {self.data.notes}", self.styles['TextoNormal']))
        
        # Salto de página para el Resumen de Inversión
        elements.append(PageBreak())
        
        # ==================== PÁGINA 4: RESUMEN DE LA INVERSIÓN ====================
        elements.append(Paragraph("RESUMEN DE LA INVERSIÓN", self.styles['TituloPortada']))
        elements.append(Spacer(1, 20))
        
        # Calcular totales con IVA
        iva_setup = subtotal_setup * 0.16
        iva_recurrente = subtotal_recurrente * 0.16
        
        # Manejar descuento (se resta del subtotal ANTES del IVA)
        descuento = self.data.descuento or 0
        subtotal_setup_con_descuento = subtotal_setup - descuento
        iva_setup_con_descuento = subtotal_setup_con_descuento * 0.16
        total_setup_final = subtotal_setup_con_descuento + iva_setup_con_descuento
        
        total_recurrente_final = subtotal_recurrente + iva_recurrente
        
        # Construir tabla de resumen
        resumen_data = [['Concepto', 'Monto (USD)']]
        
        # Setup
        resumen_data.append(['Subtotal Setup', f"${subtotal_setup:.2f}"])
        if descuento > 0:
            resumen_data.append(['Descuento', f"-${descuento:.2f}"])
            resumen_data.append(['Subtotal con Descuento', f"${subtotal_setup_con_descuento:.2f}"])
            resumen_data.append(['IVA Setup (16%)', f"${iva_setup_con_descuento:.2f}"])
        else:
            resumen_data.append(['IVA Setup (16%)', f"${iva_setup:.2f}"])
        resumen_data.append(['TOTAL SETUP (Pago Único)', f"${total_setup_final:.2f}"])
        
        # Recurrentes
        resumen_data.append(['', ''])  # Fila vacía separadora
        resumen_data.append(['Subtotal Recurrente', f"${subtotal_recurrente:.2f}"])
        resumen_data.append(['IVA Recurrente (16%)', f"${iva_recurrente:.2f}"])
        resumen_data.append(['TOTAL MENSUAL', f"${total_recurrente_final:.2f}"])
        
        # Gran total
        resumen_data.append(['', ''])
        resumen_data.append(['INVERSIÓN INICIAL (Setup)', f"${total_setup_final:.2f}"])
        resumen_data.append(['COSTO MENSUAL RECURRENTE', f"${total_recurrente_final:.2f}"])
        
        resumen_table = Table(resumen_data, colWidths=[360, 120])
        
        # Determinar índices de filas importantes
        idx_total_setup = 5 if descuento <= 0 else 6
        idx_total_mensual = idx_total_setup + 5
        
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            # Destacar total setup
            ('BACKGROUND', (0, idx_total_setup), (-1, idx_total_setup), self.COLOR_AZUL_CLARO),
            ('FONTNAME', (0, idx_total_setup), (-1, idx_total_setup), 'Helvetica-Bold'),
            # Destacar total mensual
            ('BACKGROUND', (0, -3), (-1, -3), self.COLOR_VERDE_CLARO),
            ('FONTNAME', (0, -3), (-1, -3), 'Helvetica-Bold'),
            # Destacar filas finales
            ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor("#1E293B")),  # slate-800
            ('TEXTCOLOR', (0, -2), (-1, -1), colors.white),
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(resumen_table)
        
        # Salto de página para Términos
        elements.append(PageBreak())
        
        # ==================== PÁGINA 5: TÉRMINOS Y CONDICIONES ====================
        elements.append(Paragraph("TÉRMINOS Y CONDICIONES", self.styles['TituloPortada']))
        elements.append(Spacer(1, 20))
        
        # Fecha de vigencia en español
        vigencia_date = now + timedelta(days=5)
        vigencia_fecha = f"{vigencia_date.day} de {MESES_ES[vigencia_date.month]} de {vigencia_date.year}"
        
        terminos = f"""
        <b>1. Vigencia de la Propuesta</b><br/>
        La presente oferta económica tiene una vigencia de <b>5 días hábiles</b> a partir de su emisión.
        Fecha de vencimiento: <b>{vigencia_fecha}</b><br/><br/>
        
        <b>2. Tiempo de Implementación</b><br/>
        El tiempo estimado de implementación queda sujeto a la prontitud con la que las entidades 
        bancarias remitan la información técnica de afiliados y terminales de los productos seleccionados.<br/><br/>
        
        <b>3. Forma de Pago</b><br/>
        - Costos de Setup: 100% al momento de la instalación<br/>
        - Costos Recurrentes: Facturación mensual vencida<br/><br/>
        
        <b>4. Soporte Técnico</b><br/>
        Se incluye soporte técnico 24/7 para incidencias relacionadas con la plataforma de pagos.<br/><br/>
        
        <b>5. Confidencialidad</b><br/>
        Toda la información contenida en este documento es confidencial y de uso exclusivo
        del destinatario.
        """
        elements.append(Paragraph(terminos, self.styles['TextoNormal']))
        
        # Construir documento con encabezado y pie de página
        doc.build(elements, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        
        self.buffer.seek(0)
        return self.buffer


def create_overlay_pdf(data: TemplateQuotePDFRequest, page_width: float, page_height: float, page_num: int):
    """[LEGACY] Crea un PDF overlay para el modo de plantilla base - Solo para compatibilidad"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    c.save()
    buffer.seek(0)
    return buffer


@api_router.post("/quotes/generate-pdf-with-template")
async def generate_quote_pdf_with_template(data: TemplateQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """
    Genera un PDF de cotización profesional con flujo dinámico.
    Ya no depende de plantilla base - genera el documento completo desde cero con diseño profesional.
    Características:
    - Flujo dinámico con salto de página automático
    - Sin placeholders amarillos
    - Posicionamiento exacto
    - Diseño profesional
    """
    await get_current_user(authorization)
    
    try:
        # Obtener logo si existe
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)
        
        # Crear generador
        generator = DynamicQuotePDFGenerator(data, logo_path)
        
        # Generar PDF
        pdf_buffer = generator.generate()
        
        # Nombre del archivo
        filename = f"cotizacion_{data.cliente_nombre.replace(' ', '_').replace('.', '')}_{data.quote_number or datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Generation-Method": "dynamic-flow"
            }
        )
        
    except Exception as e:
        logging.error(f"Error generando PDF dinámico: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")


@api_router.post("/quotes/preview-pdf-with-template")
async def preview_quote_pdf_with_template(data: TemplateQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """
    Genera una previsualización del PDF con flujo dinámico.
    Retorna el PDF inline para visualización en el navegador.
    """
    await get_current_user(authorization)
    
    try:
        # Obtener logo si existe
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)
        
        # Crear generador
        generator = DynamicQuotePDFGenerator(data, logo_path)
        
        # Generar PDF
        pdf_buffer = generator.generate()
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}  # Inline para preview
        )
        
    except Exception as e:
        logging.error(f"Error en preview PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@api_router.get("/quotes/check-template/{template_type}")
async def check_template_availability(template_type: str, authorization: Optional[str] = Header(None)):
    """Verifica si existe una plantilla configurada para el tipo especificado"""
    await get_current_user(authorization)
    
    templates_dir = UPLOADS_DIR / "templates"
    template_path = templates_dir / f"{template_type}.pdf"
    
    return {
        "template_type": template_type,
        "available": template_path.exists(),
        "message": "Plantilla disponible" if template_path.exists() else "No hay plantilla configurada"
    }

# Modelo para PDF de cotización de equipos
class EquipmentPDFItem(BaseModel):
    hardware_id: str
    name: str
    hardware_type: str
    quantity: int = 1
    unit_price_usd: float = 0
    total_usd: float = 0

class EquipmentQuotePDFRequest(BaseModel):
    cliente_nombre: str
    cliente_rif: str = ""
    cliente_address: str = ""
    equipment_type: str = "Dispositivo"  # "Dispositivo" o "Accesorio"
    items: List[EquipmentPDFItem] = []
    notes: str = ""

@api_router.post("/quotes/generate-equipment-pdf")
async def generate_equipment_quote_pdf(data: EquipmentQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """Genera un PDF para cotización de Equipos y Accesorios"""
    await get_current_user(authorization)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = styles['Title']
    title_style.fontSize = 18
    title_style.textColor = colors.Color(0.1, 0.3, 0.5)
    
    type_title = "DISPOSITIVOS" if data.equipment_type == "Dispositivo" else "ACCESORIOS"
    elements.append(Paragraph(f"<b>COTIZACIÓN DE {type_title}</b>", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Información del cliente
    elements.append(Paragraph("<b>Información del Cliente</b>", styles['Heading2']))
    
    info_data = [
        ["Cliente:", data.cliente_nombre],
        ["RIF:", data.cliente_rif or "N/A"],
        ["Dirección:", data.cliente_address or "No especificada"],
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
    ]
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.9, 0.9, 0.9)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Tabla de items
    elements.append(Paragraph(f"<b>Detalle de {type_title.title()}</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Header de la tabla
    items_data = [["#", "Producto", "Cantidad", "Precio Unit.", "Total USD"]]
    
    subtotal = 0
    for idx, item in enumerate(data.items, 1):
        total_line = item.quantity * item.unit_price_usd
        items_data.append([
            str(idx),
            item.name,
            str(item.quantity),
            f"${item.unit_price_usd:.2f}",
            f"${total_line:.2f}"
        ])
        subtotal += total_line
    
    # Fila de subtotal
    items_data.append(["", "", "", "Subtotal:", f"${subtotal:.2f}"])
    items_data.append(["", "", "", "TOTAL:", f"${subtotal:.2f}"])
    
    items_table = Table(items_data, colWidths=[0.4*inch, 3.5*inch, 0.8*inch, 0.9*inch, 0.9*inch])
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.4, 0.6)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -3), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -3), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        # Subtotal y Total
        ('FONTNAME', (3, -2), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (3, -2), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (3, -2), (-1, -2), 1, colors.black),
        ('BACKGROUND', (3, -1), (-1, -1), colors.Color(0.1, 0.4, 0.6)),
        ('TEXTCOLOR', (3, -1), (-1, -1), colors.whitesmoke),
        ('FONTSIZE', (3, -1), (-1, -1), 11),
    ]))
    elements.append(items_table)
    
    # Notas
    if data.notes:
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Observaciones:</b>", styles['Heading3']))
        elements.append(Paragraph(data.notes, styles['Normal']))
    
    # Footer
    elements.append(Spacer(1, 0.4*inch))
    footer_style = styles['Normal']
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    elements.append(Paragraph("Esta cotización tiene una validez de 15 días.", footer_style))
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - Cotizador Merchant Server", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"cotizacion_{type_title.lower()}_{data.cliente_nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==================== QUOTE ACTIONS ENDPOINTS ====================

class QuoteStatusUpdate(BaseModel):
    new_status: str

class EmailSendRequest(BaseModel):
    quote_id: str
    recipient_email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None

@api_router.put("/quotes/{quote_id}/status")
async def update_quote_status(quote_id: str, status_update: QuoteStatusUpdate, authorization: Optional[str] = Header(None)):
    """Actualiza el estatus de una cotización validando transiciones permitidas"""
    await get_current_user(authorization)
    
    if status_update.new_status not in QUOTE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Estados válidos: {QUOTE_STATUSES}")
    
    # Obtener cotización actual
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    quote_category = quote.get("quote_category", "implementation")
    
    # Validar transición permitida
    transitions = QUOTE_TRANSITIONS.get(quote_category, QUOTE_TRANSITIONS["implementation"])
    allowed_next_states = transitions.get(current_status, [])
    
    if status_update.new_status not in allowed_next_states:
        raise HTTPException(
            status_code=400, 
            detail=f"Transición no permitida de '{current_status}' a '{status_update.new_status}'. Estados siguientes permitidos: {allowed_next_states}"
        )
    
    # Actualizar campos de seguimiento según el nuevo estado
    update_data = {"quote_status": status_update.new_status}
    
    if status_update.new_status == "Enviada":
        update_data["sent_to_client_at"] = datetime.now(timezone.utc).isoformat()
    elif status_update.new_status == "Aprobada":
        update_data["approved_at"] = datetime.now(timezone.utc).isoformat()
    elif status_update.new_status == "Facturada":
        update_data["invoiced_at"] = datetime.now(timezone.utc).isoformat()
    elif status_update.new_status == "Pagada":
        update_data["paid_at"] = datetime.now(timezone.utc).isoformat()
    elif status_update.new_status == "Entregada":
        update_data["delivered_at"] = datetime.now(timezone.utc).isoformat()
    elif status_update.new_status == "Enviada a Imple":
        update_data["sent_to_implementation_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    return {"message": f"Cotización actualizada a estado: {status_update.new_status}"}

@api_router.post("/quotes/{quote_id}/approve")
async def approve_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Aprobar cotización - Requiere que exista un anexo de 'Orden de Compra'"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar que está en estado Enviada
    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Enviada":
        raise HTTPException(status_code=400, detail=f"Solo se pueden aprobar cotizaciones en estado 'Enviada'. Estado actual: {current_status}")
    
    # Validar que tiene anexo de Orden de Compra
    attachments = quote.get("attachments", [])
    has_oc = any(a.get("category") == "Orden de Compra" for a in attachments)
    if not has_oc:
        raise HTTPException(status_code=422, detail="Debe cargar la Orden de Compra antes de aprobar la cotización")
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Actualizar estado a Aprobada
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {
            "quote_status": "Aprobada",
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Obtener configuración de correos
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    admin_email = config.get("admin_email") if config else None
    
    email_sent = False
    if admin_email and RESEND_AVAILABLE:
        try:
            # Obtener API key de BD o env
            api_key = await get_resend_api_key()
            if api_key:
                resend.api_key = api_key
                
                # Obtener plantilla de correo
                template = await db.email_templates.find_one({"template_id": "quote_approved"}, {"_id": 0})
                if not template:
                    template = {
                        "subject": "Cotización {{quote_number}} Aprobada - Lista para Facturar",
                        "body_html": """
                        <h2>Cotización Aprobada</h2>
                        <p>La cotización <strong>{{quote_number}}</strong> ha sido aprobada y está lista para ser facturada.</p>
                        <p><strong>Cliente:</strong> {{client_name}}</p>
                        <p><strong>Tipo:</strong> {{quote_type}}</p>
                        <p><strong>Total USD:</strong> ${{total_usd}}</p>
                        <p>Por favor proceda con la facturación.</p>
                        """
                    }
                
                template_vars = {
                    "quote_number": quote.get('quote_number', ''),
                    "client_name": client_name,
                    "quote_type": quote.get('quote_type', 'N/A'),
                    "total_usd": f"{quote.get('total_usd', 0):.2f}"
                }
                
                subject = render_email_template(template["subject"], template_vars)
                html_content = render_email_template(template["body_html"], template_vars)
                
                resend.emails.send({
                    "from": SENDER_EMAIL,
                    "to": [admin_email],
                    "subject": subject,
                    "html": html_content
                })
                email_sent = True
        except Exception as e:
            print(f"Error enviando email a administración: {e}")
    
    return {
        "message": "Cotización aprobada exitosamente",
        "quote_id": quote_id,
        "new_status": "Aprobada",
        "admin_notified": email_sent,
        "admin_email": admin_email if email_sent else None
    }

@api_router.post("/quotes/{quote_id}/send-to-client")
async def send_quote_to_client(quote_id: str, authorization: Optional[str] = Header(None)):
    """Envía la cotización por email al cliente con el PDF adjunto"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Obtener email del contacto
    client_email = client.get('contact1', {}).get('email')
    if not client_email or client_email == 'sin@email.com':
        raise HTTPException(status_code=400, detail="El cliente no tiene un email de contacto válido")
    
    # Obtener plantilla de correo
    template = await db.email_templates.find_one({"template_id": "quote_sent"}, {"_id": 0})
    if not template:
        template = DEFAULT_EMAIL_TEMPLATES["quote_sent"]
    
    # Preparar variables para la plantilla
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "client_rif": client.get('rif', 'N/A'),
        "quote_type": quote.get('quote_type', 'N/A'),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "company_name": "Merchant Server"
    }
    
    # Renderizar plantilla
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)
    
    # Verificar configuración de Resend
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        # Simular envío si no hay API key
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "sent_to_client_at": datetime.now(timezone.utc).isoformat(),
                "quote_status": "Enviada"
            }}
        )
        return {
            "status": "simulated",
            "message": f"Email simulado a {client_email} (Configure RESEND_API_KEY para envío real)",
            "recipient": client_email
        }
    
    # Generar PDF en memoria
    pdf_buffer = await generate_quote_pdf_buffer(quote, client)
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [client_email],
            "subject": subject,
            "html": html_content,
            "attachments": [{
                "filename": f"cotizacion_{quote.get('quote_number', 'quote')}.pdf",
                "content": pdf_base64
            }]
        }
        
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        
        # Actualizar cotización
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "sent_to_client_at": datetime.now(timezone.utc).isoformat(),
                "quote_status": "Enviada"
            }}
        )
        
        return {
            "status": "success",
            "message": f"Cotización enviada exitosamente a {client_email}",
            "email_id": email_result.get("id")
        }
    except Exception as e:
        logger.error(f"Error enviando email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")

@api_router.post("/quotes/{quote_id}/send-to-implementation")
async def send_quote_to_implementation(quote_id: str, authorization: Optional[str] = Header(None)):
    """Envía la cotización al equipo de implementación"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar que esté en estado Pagada
    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Pagada":
        raise HTTPException(status_code=400, detail=f"Solo se pueden enviar a implementación cotizaciones en estado 'Pagada'. Estado actual: {current_status}")
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Obtener email de implementación desde configuración
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    implementation_email = config.get('implementation_email') if config else None
    
    if not implementation_email:
        raise HTTPException(status_code=400, detail="Email de implementación no configurado. Vaya a Configuración para establecerlo.")
    
    # Verificar configuración de Resend
    if not RESEND_AVAILABLE or not RESEND_API_KEY:
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "sent_to_implementation_at": datetime.now(timezone.utc).isoformat(),
                "quote_status": "Enviada a Imple"
            }}
        )
        return {
            "status": "simulated",
            "message": f"Email simulado a {implementation_email} (Configure RESEND_API_KEY para envío real)"
        }
    
    # Generar PDF
    pdf_buffer = await generate_quote_pdf_buffer(quote, client)
    pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
    
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'
    
    # Preparar tabla de servicios
    services = quote.get('services', [])
    services_html = """<table style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr style="background: #f3f4f6;">
                <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Servicio</th>
                <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Categoría</th>
            </tr>
        </thead>
        <tbody>"""
    for service in services:
        services_html += f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{service.get('name', 'N/A')}</td><td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{service.get('category', 'N/A')}</td></tr>"
    services_html += "</tbody></table>"
    
    # Obtener plantilla
    template = await db.email_templates.find_one({"template_id": "implementation"}, {"_id": 0})
    if not template:
        template = DEFAULT_EMAIL_TEMPLATES["implementation"]
    
    # Preparar variables
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "client_rif": client.get('rif', 'N/A'),
        "quote_type": quote.get('quote_type', 'N/A'),
        "integrator_name": f"{quote.get('integrator_name', 'N/A')} ({quote.get('integrator_app_name', '')})",
        "pinpad_model": quote.get('pinpad_model', 'N/A'),
        "services_table": services_html
    }
    
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)
    
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [implementation_email],
            "subject": subject,
            "html": html_content,
            "attachments": [{
                "filename": f"implementacion_{quote.get('quote_number', 'quote')}.pdf",
                "content": pdf_base64
            }]
        }
        
        email_result = await asyncio.to_thread(resend.Emails.send, params)
        
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "sent_to_implementation_at": datetime.now(timezone.utc).isoformat(),
                "quote_status": "Enviada a Imple"
            }}
        )
        
        return {
            "status": "success",
            "message": f"Enviado a implementación: {implementation_email}",
            "email_id": email_result.get("id")
        }
    except Exception as e:
        logger.error(f"Error enviando a implementación: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al enviar email: {str(e)}")

# ==================== NUEVOS ENDPOINTS DEL FLUJO DE ESTADOS ====================

class InvoiceUpload(BaseModel):
    invoice_number: Optional[str] = None

@api_router.post("/quotes/{quote_id}/invoice")
async def invoice_quote(
    quote_id: str, 
    invoice_number: str = Form(None),
    authorization: Optional[str] = Header(None)
):
    """Facturar una cotización - Requiere que exista un anexo de 'Factura'"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar estado actual
    if quote.get("quote_status") != "Aprobada":
        raise HTTPException(status_code=400, detail="Solo se pueden facturar cotizaciones en estado 'Aprobada'")
    
    # Validar que tiene anexo de Factura
    attachments = quote.get("attachments", [])
    factura_attachments = [a for a in attachments if a.get("category") == "Factura"]
    if not factura_attachments:
        raise HTTPException(status_code=422, detail="Debe cargar el documento de Factura antes de facturar la cotización")
    
    # Obtener la URL del último anexo de factura
    invoice_url = factura_attachments[-1].get("url", "")
    
    # Actualizar cotización: estado
    update_data = {
        "quote_status": "Facturada",
        "invoiced_at": datetime.now(timezone.utc).isoformat(),
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_data})
    
    # Enviar notificación a administración usando plantilla
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    admin_email = config.get('admin_email') if config else None
    
    if admin_email and RESEND_AVAILABLE and RESEND_API_KEY:
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        
        # Obtener plantilla
        template = await db.email_templates.find_one({"template_id": "invoice"}, {"_id": 0})
        if not template:
            template = DEFAULT_EMAIL_TEMPLATES["invoice"]
        
        # Preparar variables
        template_vars = {
            "quote_number": quote.get('quote_number', ''),
            "client_name": client_name,
            "client_rif": client.get('rif', 'N/A') if client else 'N/A',
            "invoice_number": invoice_number or 'No especificado',
            "total_usd": f"{quote.get('total_usd', 0):.2f}"
        }
        
        subject = render_email_template(template["subject"], template_vars)
        html_content = render_email_template(template["body_html"], template_vars)
        
        try:
            params = {
                "from": SENDER_EMAIL,
                "to": [admin_email],
                "subject": subject,
                "html": html_content
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            logger.error(f"Error enviando notificación de factura: {str(e)}")
    
    return {
        "message": "Cotización facturada exitosamente",
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }

@api_router.post("/quotes/{quote_id}/collect")
async def collect_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Marcar cotización como Pagada - Requiere que existan anexos en categoría 'Pagos'"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar estado actual
    if quote.get("quote_status") != "Facturada":
        raise HTTPException(status_code=400, detail="Solo se pueden cobrar cotizaciones en estado 'Facturada'")
    
    # Validar que tiene al menos un comprobante de pago
    attachments = quote.get("attachments", [])
    payment_proofs = [a for a in attachments if a.get("category") == "Pagos"]
    if not payment_proofs:
        raise HTTPException(status_code=422, detail="Debe cargar al menos un comprobante de pago antes de registrar el cobro")
    
    # Actualizar cotización
    update_data = {
        "quote_status": "Pagada",
        "paid_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_data})
    
    # Si es categoría equipos, enviar notificación a almacén
    quote_category = quote.get("quote_category", "implementation")
    
    if quote_category == "equipment":
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        warehouse_email = config.get('warehouse_email') if config else None
        
        if warehouse_email and RESEND_AVAILABLE and RESEND_API_KEY:
            client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
            client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
            
            # Preparar lista de items como tabla HTML
            equipment_items = quote.get('equipment_items', [])
            items_html = """<table style="border-collapse: collapse; width: 100%; max-width: 400px;">
                <thead>
                    <tr style="background: #f3f4f6;">
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Producto</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Cantidad</th>
                    </tr>
                </thead>
                <tbody>"""
            for item in equipment_items:
                items_html += f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{item.get('name', 'N/A')}</td><td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{item.get('quantity', 1)}</td></tr>"
            items_html += "</tbody></table>"
            
            # Obtener plantilla
            template = await db.email_templates.find_one({"template_id": "warehouse"}, {"_id": 0})
            if not template:
                template = DEFAULT_EMAIL_TEMPLATES["warehouse"]
            
            # Preparar variables
            template_vars = {
                "quote_number": quote.get('quote_number', ''),
                "client_name": client_name,
                "client_rif": client.get('rif', 'N/A') if client else 'N/A',
                "client_address": client.get('address', 'N/A') if client else 'N/A',
                "items_table": items_html
            }
            
            subject = render_email_template(template["subject"], template_vars)
            html_content = render_email_template(template["body_html"], template_vars)
            
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [warehouse_email],
                    "subject": subject,
                    "html": html_content
                }
                await asyncio.to_thread(resend.Emails.send, params)
            except Exception as e:
                logger.error(f"Error enviando notificación a almacén: {str(e)}")
    
    return {"message": "Cotización marcada como Pagada", "notified_warehouse": quote_category == "equipment"}

@api_router.post("/quotes/{quote_id}/deliver")
async def deliver_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Marcar cotización de equipos como Entregada"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar categoría
    if quote.get("quote_category") != "equipment":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de equipos")
    
    # Validar estado actual
    if quote.get("quote_status") != "Pagada":
        raise HTTPException(status_code=400, detail="Solo se pueden entregar cotizaciones en estado 'Pagada'")
    
    # Actualizar cotización
    update_data = {
        "quote_status": "Entregada",
        "delivered_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_data})
    
    return {"message": "Cotización marcada como Entregada"}

@api_router.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Crea una nueva versión de la cotización (Modificar)"""
    await get_current_user(authorization)
    
    # Obtener cotización original
    original_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not original_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Generar nuevo número de cotización
    count = await db.quotes.count_documents({})
    new_quote_number = f"COT-{datetime.now().year}-{str(count + 1).zfill(3)}"
    
    # Determinar versión
    original_version = original_quote.get("version", 1)
    parent_id = original_quote.get("parent_quote_id") or quote_id
    
    # Crear nueva cotización basada en la original
    new_quote = {
        **original_quote,
        "quote_id": f"quo_{uuid.uuid4().hex[:12]}",
        "quote_number": new_quote_number,
        "quote_status": "Borrador",
        "version": original_version + 1,
        "parent_quote_id": parent_id,
        # Limpiar timestamps
        "sent_to_client_at": None,
        "approved_at": None,
        "invoiced_at": None,
        "paid_at": None,
        "delivered_at": None,
        "sent_to_implementation_at": None,
        "invoice_pdf_url": None,
        "invoice_number": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.quotes.insert_one(new_quote)
    
    return {
        "message": "Nueva versión creada exitosamente",
        "new_quote_id": new_quote["quote_id"],
        "new_quote_number": new_quote_number,
        "version": new_quote["version"],
        "parent_quote_id": parent_id
    }

# ==================== ANEXOS (ATTACHMENTS) ENDPOINTS ====================

@api_router.get("/quotes/{quote_id}/attachments")
async def get_quote_attachments(quote_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene todos los anexos de una cotización"""
    await get_current_user(authorization)
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0, "attachments": 1, "quote_number": 1})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return {
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "attachments": quote.get("attachments", [])
    }

@api_router.post("/quotes/{quote_id}/attachments")
async def upload_quote_attachment(
    quote_id: str,
    file: UploadFile = File(...),
    category: str = Form(...),
    authorization: Optional[str] = Header(None)
):
    """Sube un anexo a una cotización"""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoría inválida. Opciones: {', '.join(ATTACHMENT_CATEGORIES)}")
    
    # Crear directorio de anexos si no existe
    attachments_dir = UPLOADS_DIR / "attachments" / quote_id
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre único para el archivo
    attachment_id = f"att_{uuid.uuid4().hex[:12]}"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    safe_filename = f"{attachment_id}{file_ext}"
    file_path = attachments_dir / safe_filename
    
    # Guardar archivo
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    attachment = {
        "attachment_id": attachment_id,
        "category": category,
        "filename": file.filename or safe_filename,
        "url": f"/uploads/attachments/{quote_id}/{safe_filename}",
        "uploaded_by": current_user.get("email", "unknown"),
        "uploaded_by_name": current_user.get("full_name", current_user.get("email", "unknown")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream"
    }
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$push": {"attachments": attachment}}
    )
    
    return {"message": "Anexo subido exitosamente", "attachment": attachment}

@api_router.delete("/quotes/{quote_id}/attachments/{attachment_id}")
async def delete_quote_attachment(quote_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un anexo de una cotización"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Buscar el anexo
    attachment = next((a for a in quote.get("attachments", []) if a["attachment_id"] == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")
    
    # Eliminar archivo físico
    url_path = attachment["url"].replace("/uploads/", "")
    file_path = UPLOADS_DIR / url_path
    if file_path.exists():
        file_path.unlink()
    
    # Eliminar de la BD
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$pull": {"attachments": {"attachment_id": attachment_id}}}
    )
    
    return {"message": "Anexo eliminado exitosamente"}

@api_router.get("/quotes/{quote_id}/attachments/{attachment_id}/download")
async def download_quote_attachment(quote_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Descarga un anexo de una cotización"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    attachment = next((a for a in quote.get("attachments", []) if a["attachment_id"] == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")
    
    # Construir path del archivo
    url_path = attachment["url"].replace("/uploads/", "")
    file_path = UPLOADS_DIR / url_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")
    
    return FileResponse(
        path=str(file_path),
        filename=attachment["filename"],
        media_type=attachment.get("content_type", "application/octet-stream")
    )

async def generate_quote_pdf_buffer(quote: dict, client: dict) -> io.BytesIO:
    """Genera un PDF de cotización y lo retorna como buffer"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = styles['Title']
    title_style.fontSize = 16
    elements.append(Paragraph("<b>COTIZACIÓN - Merchant Server</b>", title_style))
    elements.append(Spacer(1, 0.15*inch))
    
    quote_type_names = {
        'VPOS': 'Cajas Registradoras (VPOS)',
        'GATEWAY': 'Ecommerce (Payment Gateway)',
        'MPOS': 'Tablet o Android (MPOS)',
        'LINK': 'Link de Pago'
    }
    
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'
    
    info_data = [
        ["Cotización #:", quote.get('quote_number', 'N/A')],
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", client_name],
        ["RIF:", client.get('rif', 'N/A')],
        ["Tipo de Servicio:", quote_type_names.get(quote.get('quote_type'), quote.get('quote_type', 'N/A'))],
    ]
    
    if quote.get('integrator_name'):
        info_data.append(["Integrador:", f"{quote.get('integrator_name')} ({quote.get('integrator_app_name', '')})"])
    if quote.get('pinpad_model'):
        info_data.append(["Modelo Pinpad:", quote.get('pinpad_model')])
    if quote.get('sponsor_bank_name'):
        info_data.append(["Patrocinador:", quote.get('sponsor_bank_name')])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Servicios
    if quote.get('services'):
        elements.append(Paragraph("<b>Servicios</b>", styles['Heading2']))
        svc_data = [["Concepto", "Cantidad", "Precio USD", "Total USD"]]
        for svc in quote['services']:
            total = svc.get('quantity', 1) * svc.get('price_usd', 0)
            svc_data.append([
                svc.get('item_name', ''),
                str(svc.get('quantity', 1)),
                f"${svc.get('price_usd', 0):.2f}",
                f"${total:.2f}"
            ])
        svc_table = Table(svc_data, colWidths=[3.5*inch, 1*inch, 1*inch, 1*inch])
        svc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.4, 0.7)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(svc_table)
        elements.append(Spacer(1, 0.15*inch))
    
    # Total
    elements.append(Spacer(1, 0.2*inch))
    total_data = [
        ["Total USD:", f"${quote.get('total_usd', 0):.2f}"]
    ]
    total_table = Table(total_data, colWidths=[5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
    ]))
    elements.append(total_table)
    
    # Footer
    elements.append(Spacer(1, 0.3*inch))
    footer_style = styles['Normal']
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ==================== INTEGRATORS ENDPOINTS ====================

@api_router.get("/integrators", response_model=List[Integrator])
async def get_integrators(
    authorization: Optional[str] = Header(None),
    integrator_status: Optional[str] = None,
    integrator_type: Optional[str] = None
):
    await get_current_user(authorization)
    
    query = {}
    if integrator_status:
        query['integrator_status'] = integrator_status
    if integrator_type:
        query['integrator_type'] = integrator_type
    
    integrators = await db.integrators.find(query, {"_id": 0}).to_list(1000)
    for intg in integrators:
        if isinstance(intg.get('created_at'), str):
            intg['created_at'] = datetime.fromisoformat(intg['created_at'])
    return integrators

@api_router.post("/integrators", response_model=Integrator)
async def create_integrator(integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    new_integrator = Integrator(**integrator.model_dump())
    doc = new_integrator.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.integrators.insert_one(doc)
    return new_integrator

@api_router.get("/integrators/{integrator_id}", response_model=Integrator)
async def get_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return integrator

@api_router.put("/integrators/{integrator_id}", response_model=Integrator)
async def update_integrator(integrator_id: str, integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    
    update_data = integrator.model_dump()
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": update_data}
    )
    
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return updated

@api_router.delete("/integrators/{integrator_id}")
async def delete_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este integrador
    quotes_with_integrator = await db.quotes.count_documents({
        "integrator_id": integrator_id
    })
    if quotes_with_integrator > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el integrador porque está asociado a {quotes_with_integrator} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.integrators.delete_one({"integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return {"message": "Integrador eliminado exitosamente"}

# Export integrators to Excel
@api_router.get("/integrators/export/excel")
async def export_integrators_excel(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    import pandas as pd
    
    df = pd.DataFrame(integrators)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Reorder columns
    columns_order = ['integrator_id', 'name', 'integrator_type', 'app_name', 'integration_modality', 'integrator_status', 'created_at']
    df = df[[c for c in columns_order if c in df.columns]]
    
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Integradores')
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=integradores.xlsx"}
    )

# Export integrators to PDF
@api_router.get("/integrators/export/pdf")
async def export_integrators_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("<b>Listado de Integradores</b>", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Table data
    table_data = [["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus"]]
    for intg in integrators:
        table_data.append([
            intg.get('name', ''),
            intg.get('integrator_type', ''),
            intg.get('app_name', ''),
            intg.get('integration_modality', ''),
            intg.get('integrator_status', '')
        ])
    
    table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1.3*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.3, 0.5)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=integradores.pdf"}
    )

# Import integrators from Excel/CSV with detailed validation
@api_router.post("/integrators/import", response_model=ImportResult)
async def import_integrators(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Determine file format
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error',
            total_processed=0,
            success_count=0,
            error_count=1,
            skipped_count=0,
            errors=[ImportError(
                row=0,
                column='archivo',
                value=file.filename,
                error_type='format',
                message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv'
            )],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Read file
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error',
                total_processed=0,
                success_count=0,
                error_count=1,
                skipped_count=0,
                errors=[ImportError(
                    row=0,
                    column='archivo',
                    value=file.filename,
                    error_type='format',
                    message='El archivo está vacío',
                    suggested_action='Agregue registros al archivo antes de importar'
                )],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Map common column names
        column_mapping = {
            'nombre': 'name',
            'nombre_del_integrador': 'name',
            'tipo': 'integrator_type',
            'tipo_de_integrador': 'integrator_type',
            'aplicativo': 'app_name',
            'nombre_del_aplicativo': 'app_name',
            'modalidad': 'integration_modality',
            'modalidad_de_integración': 'integration_modality',
            'modalidad_de_integracion': 'integration_modality',
            'estatus': 'integrator_status',
            'estado': 'integrator_status'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Required columns check
        required_columns = ['name', 'integrator_type', 'app_name', 'integration_modality']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error',
                total_processed=0,
                success_count=0,
                error_count=1,
                skipped_count=0,
                errors=[ImportError(
                    row=0,
                    column=', '.join(missing_columns),
                    value=None,
                    error_type='missing',
                    message=f'Columnas requeridas no encontradas: {", ".join(missing_columns)}',
                    suggested_action='Asegúrese de que el archivo tenga las columnas: Nombre, Tipo, Aplicativo, Modalidad'
                )],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (header is row 1)
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                integrator_type = str(row.get('integrator_type', '')).strip() if pd.notna(row.get('integrator_type')) else ''
                app_name = str(row.get('app_name', '')).strip() if pd.notna(row.get('app_name')) else ''
                integration_modality = str(row.get('integration_modality', '')).strip() if pd.notna(row.get('integration_modality')) else ''
                integrator_status = str(row.get('integrator_status', 'En proceso')).strip() if pd.notna(row.get('integrator_status')) else 'En proceso'
                
                row_errors = []
                
                # Validate required fields
                if not name:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Nombre',
                        value='(vacío)',
                        error_type='missing',
                        message='El nombre del integrador es obligatorio',
                        suggested_action='Ingrese un nombre válido para el integrador'
                    ))
                
                if not app_name:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Aplicativo',
                        value='(vacío)',
                        error_type='missing',
                        message='El nombre del aplicativo es obligatorio',
                        suggested_action='Ingrese el nombre del aplicativo'
                    ))
                
                # Validate integrator_type
                if integrator_type not in INTEGRATOR_TYPES:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Tipo',
                        value=integrator_type or '(vacío)',
                        error_type='invalid',
                        message='Tipo de integrador no válido',
                        suggested_action=f'Use uno de: {", ".join(INTEGRATOR_TYPES)}'
                    ))
                
                # Validate integration_modality
                if integration_modality not in INTEGRATION_MODALITIES:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Modalidad',
                        value=integration_modality or '(vacío)',
                        error_type='invalid',
                        message='Modalidad de integración no válida',
                        suggested_action=f'Use una de: {", ".join(INTEGRATION_MODALITIES)}'
                    ))
                
                # Validate status (non-blocking, use default)
                if integrator_status not in INTEGRATOR_STATUSES:
                    integrator_status = "En proceso"
                
                # If there are errors, skip this row
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Check for duplicates
                existing = await db.integrators.find_one({
                    "name": name,
                    "app_name": app_name
                })
                
                if existing:
                    errors.append(ImportError(
                        row=row_num,
                        column='Nombre/Aplicativo',
                        value=f'{name} / {app_name}',
                        error_type='duplicate',
                        message='Ya existe un integrador con este nombre y aplicativo',
                        suggested_action='Verifique si desea actualizar el registro existente'
                    ))
                    skipped_count += 1
                    continue
                
                # Create integrator
                new_integrator = Integrator(
                    name=name,
                    integrator_type=integrator_type,
                    app_name=app_name,
                    integration_modality=integration_modality,
                    integrator_status=integrator_status
                )
                
                doc = new_integrator.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.integrators.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(
                    row=row_num,
                    column='General',
                    value=None,
                    error_type='format',
                    message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos en esta fila'
                ))
                skipped_count += 1
        
        # Determine status
        if success_count == total_rows:
            result_status = 'success'
            message = f'Importación exitosa: {success_count} registros procesados correctamente'
        elif success_count > 0:
            result_status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} con errores'
        else:
            result_status = 'error'
            message = f'Importación fallida: {skipped_count} registros con errores'
        
        return ImportResult(
            status=result_status,
            total_processed=total_rows,
            success_count=success_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors[:50],  # Limit to first 50 errors
            message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error',
            total_processed=0,
            success_count=0,
            error_count=1,
            skipped_count=0,
            errors=[ImportError(
                row=0,
                column='archivo',
                value=file.filename,
                error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté dañado y tenga el formato correcto'
            )],
            message='Error crítico: No se pudo procesar el archivo'
        )

# ==================== CONFIGURATION ENDPOINTS ====================

class SedeEmails(BaseModel):
    admin: Optional[EmailStr] = None
    warehouse: Optional[EmailStr] = None

class EmailsBySede(BaseModel):
    TBP: Optional[SedeEmails] = None
    LCH: Optional[SedeEmails] = None

class AppSettings(BaseModel):
    implementation_email: Optional[EmailStr] = None
    admin_email: Optional[EmailStr] = None  # LEGACY: Mantener para compatibilidad
    warehouse_email: Optional[EmailStr] = None  # LEGACY: Mantener para compatibilidad
    emails_by_sede: Optional[dict] = None  # NUEVO: Correos por sede {TBP: {admin, warehouse}, LCH: {admin, warehouse}}
    resend_api_key: Optional[str] = None

@api_router.get("/config/settings")
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
                "TBP": {"admin": "", "warehouse": ""},
                "LCH": {"admin": "", "warehouse": ""}
            },
            "resend_api_key_configured": False
        }
    
    # No devolver la API key completa por seguridad, solo indicar si está configurada
    resend_key = config.get("resend_api_key")
    resend_key_masked = None
    if resend_key:
        resend_key_masked = f"{'*' * (len(resend_key) - 4)}{resend_key[-4:]}" if len(resend_key) > 4 else "****"
    
    return {
        "implementation_email": config.get("implementation_email"),
        "admin_email": config.get("admin_email"),
        "warehouse_email": config.get("warehouse_email"),
        "emails_by_sede": config.get("emails_by_sede", {
            "TBP": {"admin": config.get("admin_email", ""), "warehouse": config.get("warehouse_email", "")},
            "LCH": {"admin": "", "warehouse": ""}
        }),
        "resend_api_key_configured": bool(resend_key),
        "resend_api_key_masked": resend_key_masked
    }

@api_router.put("/config/settings")
async def update_app_settings(settings: AppSettings, authorization: Optional[str] = Header(None)):
    """Actualiza la configuración general de la aplicación"""
    global RESEND_API_KEY
    await get_current_user(authorization)
    
    update_data = {
        "type": "app_settings",
        "implementation_email": settings.implementation_email,
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

# Endpoint para obtener plantillas de documentos por sede
@api_router.get("/config/document-templates")
async def get_document_templates(authorization: Optional[str] = Header(None)):
    """Obtiene el estado de las plantillas de documentos por sede"""
    await get_current_user(authorization)
    
    # Por ahora retornar estructura vacía - las plantillas se configurarán más adelante
    templates = {}
    template_types = ['despacho_equipos', 'cotizacion_aprobada', 'facturacion_control']
    sedes = ['TBP', 'LCH']
    
    for sede in sedes:
        for template_type in template_types:
            key = f"{template_type}_{sede}"
            templates[key] = {"exists": False, "configured_at": None}
    
    return templates

@api_router.post("/config/logo")
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

@api_router.get("/config/logo")
async def get_logo():
    for logo_file in UPLOADS_DIR.glob("logo.*"):
        return FileResponse(logo_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="No hay logo configurado")

@api_router.delete("/config/logo")
async def delete_logo(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    for existing_logo in UPLOADS_DIR.glob("logo.*"):
        existing_logo.unlink()
        return {"message": "Logo eliminado exitosamente"}
    
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

@api_router.post("/config/templates/{template_type}")
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

@api_router.get("/config/templates/{template_type}")
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

@api_router.delete("/config/templates/{template_type}")
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

@api_router.get("/config/templates")
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

# ==================== SEED BANKS ENDPOINT ====================

@api_router.post("/banks/seed")
async def seed_banks(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Lista de bancos de Venezuela
    venezuela_banks = [
        "Banco de Venezuela",
        "Banco Mercantil",
        "Banesco Banco Universal",
        "BBVA Provincial",
        "Banco Exterior",
        "Banco Nacional de Crédito (BNC)",
        "Banco del Tesoro",
        "Banco Bicentenario",
        "Banco Occidental de Descuento (BOD)",
        "Banco Sofitasa",
        "Banco Plaza",
        "Banco Activo",
        "Banco del Caribe",
        "Banco Fondo Común (BFC)",
        "Banco Agrícola de Venezuela",
        "Bancrecer",
        "Banplus",
        "100% Banco",
        "Bancamiga",
        "Mi Banco",
        "Bancaribe"
    ]
    
    # Lista de bancos de Estados Unidos
    usa_banks = [
        "Bank of America",
        "Banesco USA",
        "Wells Fargo",
        "Citi Bank",
        "US Bank",
        "Chase",
        "Amerant"
    ]
    
    # Fintechs
    fintechs = [
        {"name": "Cashea", "country": "Venezuela"},
        {"name": "Lysto", "country": "Venezuela"},
        {"name": "Crixto", "country": "Venezuela"}
    ]
    
    inserted_count = 0
    
    # Insert Venezuela banks
    for bank_name in venezuela_banks:
        existing = await db.banks.find_one({"name": bank_name})
        if not existing:
            bank = Bank(name=bank_name, type="Banco", country="Venezuela", products=[])
            doc = bank.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.banks.insert_one(doc)
            inserted_count += 1
    
    # Insert USA banks
    for bank_name in usa_banks:
        existing = await db.banks.find_one({"name": bank_name})
        if not existing:
            bank = Bank(name=bank_name, type="Banco", country="Estados Unidos", products=[])
            doc = bank.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.banks.insert_one(doc)
            inserted_count += 1
    
    # Insert Fintechs
    for fintech in fintechs:
        existing = await db.banks.find_one({"name": fintech["name"]})
        if not existing:
            bank = Bank(name=fintech["name"], type="Fintech", country=fintech["country"], products=[])
            doc = bank.model_dump()
            doc['created_at'] = doc['created_at'].isoformat()
            await db.banks.insert_one(doc)
            inserted_count += 1
    
    return {"message": f"Base de datos poblada exitosamente. {inserted_count} bancos agregados."}

# ==================== PLANTILLAS DE CORREO ====================

class EmailTemplate(BaseModel):
    """Modelo para plantillas de correo"""
    template_id: str  # 'quote_sent', 'invoice', 'warehouse', 'implementation'
    name: str
    subject: str
    body_html: str  # Cuerpo del correo en HTML
    description: Optional[str] = None
    is_active: bool = True

# Plantillas predeterminadas
DEFAULT_EMAIL_TEMPLATES = {
    "quote_approved": {
        "template_id": "quote_approved",
        "name": "Cotización Aprobada",
        "description": "Se envía a Administración cuando una cotización es aprobada y está lista para facturar",
        "subject": "[APROBADA] Cotización #{quote_number} - Lista para Facturar",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #059669;">Cotización Aprobada - Lista para Facturar</h2>
<p>La siguiente cotización ha sido <strong>APROBADA</strong> y requiere facturación:</p>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tipo:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_type}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${total_usd} USD</td></tr>
</table>
<p><strong>Acción Requerida:</strong> Por favor proceda con la facturación desde el módulo de Cotizaciones.</p>
</body>
</html>
""",
        "is_active": True
    },
    "quote_sent": {
        "template_id": "quote_sent",
        "name": "Envío de Cotización",
        "description": "Se envía al cliente cuando se genera una cotización",
        "subject": "Cotización #{quote_number} - {company_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #2563eb;">Cotización #{quote_number}</h2>
<p>Estimado/a <strong>{client_name}</strong>,</p>
<p>Adjunto encontrará la cotización solicitada con los detalles de nuestra propuesta comercial.</p>
<p><strong>Resumen:</strong></p>
<ul>
<li>Número de Cotización: {quote_number}</li>
<li>Tipo: {quote_type}</li>
<li>Total: ${total_usd} USD</li>
</ul>
<p>Quedamos atentos a sus comentarios.</p>
<p>Saludos cordiales,<br><strong>{company_name}</strong></p>
</body>
</html>
""",
        "is_active": True
    },
    "invoice": {
        "template_id": "invoice",
        "name": "Facturación y Control Contable",
        "description": "Se envía a Administración cuando se factura una cotización",
        "subject": "[FACTURADA] Cotización #{quote_number} - {client_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #7c3aed;">Notificación de Facturación</h2>
<p>Se ha registrado la facturación de la siguiente cotización:</p>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>RIF:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_rif}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Número de Factura:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{invoice_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${total_usd} USD</td></tr>
</table>
<p>Este correo es para control contable y seguimiento.</p>
</body>
</html>
""",
        "is_active": True
    },
    "warehouse": {
        "template_id": "warehouse",
        "name": "Despacho de Equipos",
        "description": "Se envía a Almacén cuando una cotización de equipos es pagada",
        "subject": "[ALMACÉN] Pedido Listo - Cotización #{quote_number} - {client_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #f59e0b;">Solicitud de Despacho de Equipos</h2>
<p>El siguiente pedido ha sido <strong>PAGADO</strong> y está listo para preparar:</p>

<h3>Datos del Cliente:</h3>
<ul>
<li><strong>Cliente:</strong> {client_name}</li>
<li><strong>RIF:</strong> {client_rif}</li>
<li><strong>Dirección:</strong> {client_address}</li>
</ul>

<h3>Productos a Despachar:</h3>
{items_table}

<p style="background: #fef3c7; padding: 10px; border-radius: 5px;">
<strong>Nota:</strong> Por favor coordinar la entrega con el cliente.
</p>
</body>
</html>
""",
        "is_active": True
    },
    "implementation": {
        "template_id": "implementation",
        "name": "Inicio de Obra",
        "description": "Se envía a Implementación con los detalles técnicos del proyecto",
        "subject": "[IMPLEMENTACIÓN] Proyecto Aprobado - {client_name} - {quote_type}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #059669;">Nuevo Proyecto para Implementación</h2>
<p>El siguiente proyecto ha sido aprobado y está listo para iniciar:</p>

<h3>Datos del Proyecto:</h3>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>RIF:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_rif}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tipo:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_type}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Integrador:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{integrator_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Modelo Pinpad:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{pinpad_model}</td></tr>
</table>

<h3>Servicios Contratados:</h3>
{services_table}

<p>Por favor coordinar con el cliente para iniciar la implementación.</p>
</body>
</html>
""",
        "is_active": True
    }
}

# Sedes disponibles
SEDES = [
    {"id": "TBP", "name": "Torre Banco Plaza"},
    {"id": "LCH", "name": "Los Chaguaramos"}
]

# Base templates para generar por sede
BASE_EMAIL_TEMPLATES = {
    "quote_sent": {
        "name": "Envío de Cotización a Cliente",
        "description": "Se envía al cliente cuando se genera una cotización",
        "subject": "Cotización #{quote_number} - {company_name} - Sede {sede_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #2563eb;">Cotización #{quote_number}</h2>
<p>Estimado/a <strong>{client_name}</strong>,</p>
<p>Adjunto encontrará la cotización solicitada con los detalles de nuestra propuesta comercial.</p>
<p><strong>Resumen:</strong></p>
<ul>
<li>Número de Cotización: {quote_number}</li>
<li>Tipo: {quote_type}</li>
<li>Total: ${total_usd} USD</li>
<li>Sede: {sede_name}</li>
</ul>
<p>Quedamos atentos a sus comentarios.</p>
<p>Saludos cordiales,<br><strong>{company_name}</strong></p>
</body>
</html>
"""
    },
    "quote_approved": {
        "name": "Cotización Aprobada",
        "description": "Se envía a Administración cuando una cotización es aprobada",
        "subject": "[APROBADA] Cotización #{quote_number} - Lista para Facturar - Sede {sede_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #059669;">Cotización Aprobada - Lista para Facturar</h2>
<p>La siguiente cotización ha sido <strong>APROBADA</strong> y requiere facturación:</p>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tipo:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_type}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${total_usd} USD</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Sede:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{sede_name}</td></tr>
</table>
<p><strong>Acción Requerida:</strong> Por favor proceda con la facturación desde el módulo de Cotizaciones.</p>
</body>
</html>
"""
    },
    "invoice": {
        "name": "Facturación y Control Contable",
        "description": "Se envía a Administración cuando se factura una cotización",
        "subject": "[FACTURADA] Cotización #{quote_number} - {client_name} - Sede {sede_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #7c3aed;">Notificación de Facturación</h2>
<p>Se ha registrado la facturación de la siguiente cotización:</p>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>RIF:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_rif}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Número de Factura:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{invoice_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${total_usd} USD</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Sede:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{sede_name}</td></tr>
</table>
<p>Este correo es para control contable y seguimiento.</p>
</body>
</html>
"""
    },
    "warehouse": {
        "name": "Despacho de Equipos",
        "description": "Se envía a Almacén cuando una cotización de equipos es pagada",
        "subject": "[ALMACÉN] Pedido Listo - Cotización #{quote_number} - Sede {sede_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #f59e0b;">Solicitud de Despacho de Equipos - Sede {sede_name}</h2>
<p>El siguiente pedido ha sido <strong>PAGADO</strong> y está listo para preparar:</p>

<h3>Datos del Cliente:</h3>
<ul>
<li><strong>Cliente:</strong> {client_name}</li>
<li><strong>RIF:</strong> {client_rif}</li>
<li><strong>Dirección:</strong> {client_address}</li>
</ul>

<h3>Productos a Despachar:</h3>
{items_table}

<p style="background: #fef3c7; padding: 10px; border-radius: 5px;">
<strong>Nota:</strong> Por favor coordinar la entrega con el cliente.
</p>
</body>
</html>
"""
    },
    "implementation": {
        "name": "Envío a Implementación",
        "description": "Se envía a Implementación con los detalles técnicos del proyecto",
        "subject": "[IMPLEMENTACIÓN] Proyecto Aprobado - {client_name} - Sede {sede_name}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
<h2 style="color: #059669;">Nuevo Proyecto para Implementación - Sede {sede_name}</h2>
<p>El siguiente proyecto ha sido aprobado y está listo para iniciar:</p>

<h3>Datos del Proyecto:</h3>
<table style="border-collapse: collapse; margin: 20px 0;">
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cotización:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_number}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Cliente:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>RIF:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{client_rif}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Tipo:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{quote_type}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Integrador:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{integrator_name}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Modelo Pinpad:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{pinpad_model}</td></tr>
<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Sede:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{sede_name}</td></tr>
</table>

<h3>Servicios Contratados:</h3>
{services_table}

<p>Por favor coordinar con el cliente para iniciar la implementación.</p>
</body>
</html>
"""
    }
}

# Generar todas las plantillas por sede
def generate_email_templates_by_sede():
    templates = {}
    for sede in SEDES:
        for base_id, base_template in BASE_EMAIL_TEMPLATES.items():
            template_id = f"{base_id}_{sede['id']}"
            templates[template_id] = {
                "template_id": template_id,
                "name": f"{base_template['name']} (Sede {sede['id']})",
                "description": f"{base_template['description']} - Sede {sede['name']}",
                "subject": base_template['subject'],
                "body_html": base_template['body_html'],
                "sede": sede['id'],
                "sede_name": sede['name'],
                "is_active": True
            }
    return templates

# Plantillas generadas por sede
EMAIL_TEMPLATES_BY_SEDE = generate_email_templates_by_sede()

@api_router.get("/email-templates")
async def get_email_templates(authorization: Optional[str] = Header(None)):
    """Obtiene todas las plantillas de correo (por sede)"""
    await get_current_user(authorization)
    
    templates = await db.email_templates.find({}, {"_id": 0}).to_list(100)
    
    # Si no hay plantillas, devolver las predeterminadas por sede
    if not templates:
        return list(EMAIL_TEMPLATES_BY_SEDE.values())
    
    # Asegurar que todas las plantillas por sede existan
    template_ids = [t["template_id"] for t in templates]
    for template_id, default_template in EMAIL_TEMPLATES_BY_SEDE.items():
        if template_id not in template_ids:
            templates.append(default_template)
    
    # También incluir plantillas legacy si existen
    for template_id, default_template in DEFAULT_EMAIL_TEMPLATES.items():
        if template_id not in template_ids:
            # Solo agregar si no hay versión por sede
            sede_version_exists = any(t["template_id"].startswith(template_id + "_") for t in templates)
            if not sede_version_exists:
                templates.append(default_template)
    
    return templates

@api_router.get("/email-templates/{template_id}")
async def get_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene una plantilla de correo específica"""
    await get_current_user(authorization)
    
    template = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    
    if not template:
        # Buscar primero en plantillas por sede
        if template_id in EMAIL_TEMPLATES_BY_SEDE:
            return EMAIL_TEMPLATES_BY_SEDE[template_id]
        # Luego buscar en plantillas legacy
        if template_id in DEFAULT_EMAIL_TEMPLATES:
            return DEFAULT_EMAIL_TEMPLATES[template_id]
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    return template

@api_router.put("/email-templates/{template_id}")
async def update_email_template(template_id: str, template: EmailTemplate, authorization: Optional[str] = Header(None)):
    """Actualiza una plantilla de correo"""
    await get_current_user(authorization)
    
    # Validar que el template_id coincida
    if template.template_id != template_id:
        raise HTTPException(status_code=400, detail="El ID de la plantilla no coincide")
    
    template_data = template.model_dump()
    template_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.email_templates.update_one(
        {"template_id": template_id},
        {"$set": template_data},
        upsert=True
    )
    
    return {"message": "Plantilla actualizada exitosamente", "template_id": template_id}

@api_router.post("/email-templates/reset/{template_id}")
async def reset_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Restablece una plantilla a su valor predeterminado"""
    await get_current_user(authorization)
    
    # Buscar primero en plantillas por sede, luego en legacy
    default_template = None
    if template_id in EMAIL_TEMPLATES_BY_SEDE:
        default_template = EMAIL_TEMPLATES_BY_SEDE[template_id].copy()
    elif template_id in DEFAULT_EMAIL_TEMPLATES:
        default_template = DEFAULT_EMAIL_TEMPLATES[template_id].copy()
    
    if not default_template:
        raise HTTPException(status_code=404, detail="Plantilla predeterminada no encontrada")
    
    default_template["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.email_templates.update_one(
        {"template_id": template_id},
        {"$set": default_template},
        upsert=True
    )
    
    return {"message": "Plantilla restablecida a valores predeterminados", "template": default_template}

# Función auxiliar para renderizar plantillas con variables
def render_email_template(template_body: str, variables: dict) -> str:
    """Reemplaza las variables en la plantilla con valores reales"""
    result = template_body
    for key, value in variables.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(value) if value else "N/A")
    return result

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
