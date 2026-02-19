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
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
import io
import shutil
import csv
import base64

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

app = FastAPI(title="Cotizador Merchant Server API")

# Create uploads directory for logo
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
api_router = APIRouter(prefix="/api")

# ==================== MODELS ====================

class Contact(BaseModel):
    name: str
    phone: str
    email: EmailStr

class ClientCreate(BaseModel):
    rif: str
    legal_name: str
    fantasy_name: str
    segment: Literal["Pymes", "Corporativo", "Mixto"]
    address: Optional[str] = None  # Dirección fiscal
    contact1: Contact
    contact2: Contact

class Client(BaseModel):
    client_id: str = Field(default_factory=lambda: f"cli_{uuid.uuid4().hex[:12]}")
    rif: str
    legal_name: str
    fantasy_name: str
    segment: Literal["Pymes", "Corporativo", "Mixto"]
    address: Optional[str] = None  # Dirección fiscal
    contact1: Contact
    contact2: Contact
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

# Modelo para items de cotización de equipos
class EquipmentQuoteItem(BaseModel):
    hardware_id: str
    name: str
    hardware_type: str  # "Dispositivo" o "Accesorio"
    quantity: int = 1
    unit_price_usd: float = 0
    total_usd: float = 0

# Tipos de cotización
QUOTE_CATEGORIES = ["implementation", "equipment"]  # Implementación o Equipos/Accesorios
EQUIPMENT_TYPES = ["Dispositivo", "Accesorio"]

class QuoteCreate(BaseModel):
    client_id: str
    quote_category: str = "implementation"  # "implementation" o "equipment"
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
    }
}

class Quote(BaseModel):
    quote_id: str = Field(default_factory=lambda: f"quo_{uuid.uuid4().hex[:12]}")
    quote_number: str
    client_id: str
    quote_category: str = "implementation"  # "implementation" o "equipment"
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
    # Campos de seguimiento - timestamps
    sent_to_client_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    invoiced_at: Optional[datetime] = None  # NUEVO: Cuando se factura
    paid_at: Optional[datetime] = None  # NUEVO: Cuando se cobra
    delivered_at: Optional[datetime] = None  # NUEVO: Cuando se entrega (equipos)
    sent_to_implementation_at: Optional[datetime] = None
    # Campos de factura
    invoice_pdf_url: Optional[str] = None  # NUEVO: URL del PDF de la factura
    invoice_number: Optional[str] = None  # NUEVO: Número de factura
    # Versionamiento
    version: int = 1  # NUEVO: Versión de la cotización
    parent_quote_id: Optional[str] = None  # NUEVO: ID de la cotización original (si es una modificación)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None

class SessionData(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    session_token: str

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
    
    expires_at = session_doc["expires_at"]
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
    return user

@api_router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.replace("Bearer ", "")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    return {"message": "Logged out successfully"}

# ==================== CLIENTS ENDPOINTS ====================

@api_router.post("/clients", response_model=Client)
async def create_client(client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    client = Client(**client_data.model_dump())
    doc = client.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.clients.insert_one(doc)
    return client

@api_router.get("/clients", response_model=List[Client])
async def get_clients(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    clients = await db.clients.find({}, {"_id": 0}).to_list(1000)
    for client in clients:
        if isinstance(client['created_at'], str):
            client['created_at'] = datetime.fromisoformat(client['created_at'])
    return clients

@api_router.get("/clients/{client_id}", response_model=Client)
async def get_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if isinstance(client['created_at'], str):
        client['created_at'] = datetime.fromisoformat(client['created_at'])
    return client

@api_router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.clients.update_one(
        {"client_id": client_id},
        {"$set": client_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_client(client_id, authorization)

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.clients.delete_one({"client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

@api_router.post("/clients/import", response_model=ImportResult)
async def import_clients(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
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
            status='error',
            total_processed=0,
            success_count=0,
            error_count=1,
            skipped_count=0,
            errors=[ImportError(
                row=0, column='archivo', value=file.filename,
                error_type='format',
                message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv'
            )],
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
        
        # Mapeo de columnas comunes
        column_mapping = {
            'nombre_jurídico': 'legal_name', 'nombre_juridico': 'legal_name',
            'nombre_fantasía': 'fantasy_name', 'nombre_fantasia': 'fantasy_name',
            'segmento': 'segment',
            'contacto1_nombre': 'contact1_name', 'contacto1_teléfono': 'contact1_phone',
            'contacto1_telefono': 'contact1_phone', 'contacto1_email': 'contact1_email'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columnas requeridas
        required_columns = ['rif', 'legal_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None, error_type='missing',
                    message='Columnas requeridas no encontradas', 
                    suggested_action='Asegúrese de que el archivo tenga las columnas: RIF, Nombre Jurídico')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        valid_segments = ['Pymes', 'Corporativo', 'Mixto']
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2  # Número de fila en Excel
            
            try:
                rif = str(row.get('rif', '')).strip() if pd.notna(row.get('rif')) else ''
                legal_name = str(row.get('legal_name', '')).strip() if pd.notna(row.get('legal_name')) else ''
                fantasy_name = str(row.get('fantasy_name', '')).strip() if pd.notna(row.get('fantasy_name')) else ''
                segment = str(row.get('segment', 'Pymes')).strip() if pd.notna(row.get('segment')) else 'Pymes'
                
                row_errors = []
                
                # Validar campos requeridos
                if not rif:
                    row_errors.append(ImportError(row=row_num, column='RIF', value='(vacío)',
                        error_type='missing', message='El RIF es obligatorio',
                        suggested_action='Ingrese un RIF válido'))
                
                if not legal_name:
                    row_errors.append(ImportError(row=row_num, column='Nombre Jurídico', value='(vacío)',
                        error_type='missing', message='El nombre jurídico es obligatorio',
                        suggested_action='Ingrese el nombre jurídico del cliente'))
                
                # Validar segmento
                if segment not in valid_segments:
                    segment = 'Pymes'  # Usar valor por defecto si no es válido
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.clients.find_one({"rif": rif})
                if existing:
                    errors.append(ImportError(row=row_num, column='RIF', value=rif,
                        error_type='duplicate', message='Ya existe un cliente con este RIF',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Obtener datos de contacto
                contact1_name = str(row.get('contact1_name', '')).strip() if pd.notna(row.get('contact1_name')) else ''
                contact1_phone = str(row.get('contact1_phone', '')).strip() if pd.notna(row.get('contact1_phone')) else ''
                contact1_email = str(row.get('contact1_email', '')).strip() if pd.notna(row.get('contact1_email')) else ''
                
                # Crear cliente
                client = Client(
                    rif=rif,
                    legal_name=legal_name,
                    fantasy_name=fantasy_name,
                    segment=segment,
                    contact1=Contact(name=contact1_name, phone=contact1_phone, email=contact1_email or 'sin@email.com'),
                    contact2=Contact(name='', phone='', email='sin@email.com')
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
        
        # Determinar estado final
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
            status=status,
            total_processed=total_rows,
            success_count=success_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors,
            message=message
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
    result = await db.banks.delete_one({"bank_id": bank_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    return {"message": "Bank deleted successfully"}

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
    result = await db.hardware.delete_one({"hardware_id": hardware_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Hardware not found")
    return {"message": "Hardware deleted successfully"}

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
    result = await db.services.delete_one({"service_id": service_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service deleted successfully"}

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
    await get_current_user(authorization)
    
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
    
    count = await db.quotes.count_documents({})
    quote_number = f"COT-{datetime.now().year}-{count + 1:03d}"
    
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
        sponsor_bank_name=quote_data.sponsor_bank_name
    )
    
    doc = quote.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.quotes.insert_one(doc)
    
    return quote

@api_router.get("/quotes", response_model=List[Quote])
async def get_quotes(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    quotes = await db.quotes.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    for quote in quotes:
        if isinstance(quote['created_at'], str):
            quote['created_at'] = datetime.fromisoformat(quote['created_at'])
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
    subject = f"[IMPLEMENTACIÓN] Cotización #{quote.get('quote_number', '')} - {client_name}"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #059669;">Nueva Implementación Aprobada</h2>
        <p>Se ha aprobado la siguiente cotización y está lista para implementación:</p>
        
        <table style="margin: 20px 0; border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr style="background: #f3f4f6;"><td style="padding: 10px; font-weight: bold;">Cotización #</td><td style="padding: 10px;">{quote.get('quote_number', 'N/A')}</td></tr>
            <tr><td style="padding: 10px; font-weight: bold;">Cliente</td><td style="padding: 10px;">{client_name}</td></tr>
            <tr style="background: #f3f4f6;"><td style="padding: 10px; font-weight: bold;">RIF</td><td style="padding: 10px;">{client.get('rif', 'N/A')}</td></tr>
            <tr><td style="padding: 10px; font-weight: bold;">Tipo de Servicio</td><td style="padding: 10px;">{quote.get('quote_type', 'N/A')}</td></tr>
            <tr style="background: #f3f4f6;"><td style="padding: 10px; font-weight: bold;">Integrador</td><td style="padding: 10px;">{quote.get('integrator_name', 'N/A')} ({quote.get('integrator_app_name', '')})</td></tr>
            <tr><td style="padding: 10px; font-weight: bold;">Modelo Pinpad</td><td style="padding: 10px;">{quote.get('pinpad_model', 'N/A')}</td></tr>
            <tr style="background: #f3f4f6;"><td style="padding: 10px; font-weight: bold;">Patrocinador</td><td style="padding: 10px;">{quote.get('sponsor_bank_name', 'N/A')}</td></tr>
            <tr><td style="padding: 10px; font-weight: bold;">Total USD</td><td style="padding: 10px;"><strong>${quote.get('total_usd', 0):.2f}</strong></td></tr>
        </table>
        
        <p>Por favor revisar el PDF adjunto para los detalles completos.</p>
        <p style="margin-top: 30px; color: #6b7280; font-size: 12px;">Este es un mensaje automático del sistema de cotizaciones.</p>
    </body>
    </html>
    """
    
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
    invoice_file: UploadFile = File(...),
    invoice_number: str = Form(None),
    authorization: Optional[str] = Header(None)
):
    """Facturar una cotización - Requiere subir el PDF de la factura"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar estado actual
    if quote.get("quote_status") != "Aprobada":
        raise HTTPException(status_code=400, detail="Solo se pueden facturar cotizaciones en estado 'Aprobada'")
    
    # Validar que sea un PDF
    if not invoice_file.content_type == 'application/pdf':
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
    
    # Guardar el archivo de factura
    file_extension = "pdf"
    invoice_filename = f"invoice_{quote_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
    invoice_path = UPLOADS_DIR / invoice_filename
    
    content = await invoice_file.read()
    with open(invoice_path, "wb") as f:
        f.write(content)
    
    # Actualizar cotización
    update_data = {
        "quote_status": "Facturada",
        "invoiced_at": datetime.now(timezone.utc).isoformat(),
        "invoice_pdf_url": f"/uploads/{invoice_filename}",
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
                "html": html_content,
                "attachments": [{
                    "filename": f"factura_{invoice_number or quote_id}.pdf",
                    "content": base64.b64encode(content).decode('utf-8')
                }]
            }
            await asyncio.to_thread(resend.Emails.send, params)
        except Exception as e:
            logger.error(f"Error enviando notificación de factura: {str(e)}")
    
    return {
        "message": "Cotización facturada exitosamente",
        "invoice_pdf_url": f"/uploads/{invoice_filename}",
        "invoice_number": invoice_number
    }

@api_router.post("/quotes/{quote_id}/collect")
async def collect_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Marcar cotización como Pagada (Cobrar)"""
    await get_current_user(authorization)
    
    # Obtener cotización
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Validar estado actual
    if quote.get("quote_status") != "Facturada":
        raise HTTPException(status_code=400, detail="Solo se pueden cobrar cotizaciones en estado 'Facturada'")
    
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
            
            # Preparar lista de items
            equipment_items = quote.get('equipment_items', [])
            items_html = ""
            for item in equipment_items:
                items_html += f"<tr><td style='padding: 8px; border: 1px solid #ddd;'>{item.get('name', 'N/A')}</td><td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{item.get('quantity', 1)}</td></tr>"
            
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [warehouse_email],
                    "subject": f"[ALMACÉN] Pedido Pagado - Cotización #{quote.get('quote_number', '')} - {client_name}",
                    "html": f"""
                    <html><body style="font-family: Arial, sans-serif;">
                        <h2 style="color: #f59e0b;">Pedido Listo para Preparar</h2>
                        <p>La cotización <strong>#{quote.get('quote_number', '')}</strong> ha sido pagada y está lista para preparar.</p>
                        
                        <h3>Datos del Cliente:</h3>
                        <p><strong>Cliente:</strong> {client_name}</p>
                        <p><strong>RIF:</strong> {client.get('rif', 'N/A') if client else 'N/A'}</p>
                        <p><strong>Dirección:</strong> {client.get('address', 'N/A') if client else 'N/A'}</p>
                        
                        <h3>Items a Despachar:</h3>
                        <table style="border-collapse: collapse; width: 100%; max-width: 400px;">
                            <thead>
                                <tr style="background: #f3f4f6;">
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Producto</th>
                                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Cantidad</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items_html}
                            </tbody>
                        </table>
                        
                        <p style="margin-top: 20px; color: #6b7280; font-size: 12px;">Este es un mensaje automático del sistema de cotizaciones.</p>
                    </body></html>
                    """
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
    
    result = await db.integrators.delete_one({"integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return {"message": "Integrator deleted successfully"}

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

class AppSettings(BaseModel):
    implementation_email: Optional[EmailStr] = None
    admin_email: Optional[EmailStr] = None  # NUEVO: Correo de Administración
    warehouse_email: Optional[EmailStr] = None  # NUEVO: Correo de Almacén

@api_router.get("/config/settings")
async def get_app_settings(authorization: Optional[str] = Header(None)):
    """Obtiene la configuración general de la aplicación"""
    await get_current_user(authorization)
    
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    if not config:
        return {"implementation_email": None, "admin_email": None, "warehouse_email": None}
    return {
        "implementation_email": config.get("implementation_email"),
        "admin_email": config.get("admin_email"),
        "warehouse_email": config.get("warehouse_email")
    }

@api_router.put("/config/settings")
async def update_app_settings(settings: AppSettings, authorization: Optional[str] = Header(None)):
    """Actualiza la configuración general de la aplicación"""
    await get_current_user(authorization)
    
    await db.config.update_one(
        {"type": "app_settings"},
        {"$set": {
            "type": "app_settings",
            "implementation_email": settings.implementation_email,
            "admin_email": settings.admin_email,
            "warehouse_email": settings.warehouse_email,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }},
        upsert=True
    )
    
    return {
        "message": "Configuración actualizada",
        "implementation_email": settings.implementation_email,
        "admin_email": settings.admin_email,
        "warehouse_email": settings.warehouse_email
    }

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

@api_router.get("/email-templates")
async def get_email_templates(authorization: Optional[str] = Header(None)):
    """Obtiene todas las plantillas de correo"""
    await get_current_user(authorization)
    
    templates = await db.email_templates.find({}, {"_id": 0}).to_list(100)
    
    # Si no hay plantillas, devolver las predeterminadas
    if not templates:
        return list(DEFAULT_EMAIL_TEMPLATES.values())
    
    # Asegurar que todas las plantillas predeterminadas existan
    template_ids = [t["template_id"] for t in templates]
    for template_id, default_template in DEFAULT_EMAIL_TEMPLATES.items():
        if template_id not in template_ids:
            templates.append(default_template)
    
    return templates

@api_router.get("/email-templates/{template_id}")
async def get_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene una plantilla de correo específica"""
    await get_current_user(authorization)
    
    template = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    
    if not template:
        # Devolver plantilla predeterminada si existe
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
    
    result = await db.email_templates.update_one(
        {"template_id": template_id},
        {"$set": template_data},
        upsert=True
    )
    
    return {"message": "Plantilla actualizada exitosamente", "template_id": template_id}

@api_router.post("/email-templates/reset/{template_id}")
async def reset_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Restablece una plantilla a su valor predeterminado"""
    await get_current_user(authorization)
    
    if template_id not in DEFAULT_EMAIL_TEMPLATES:
        raise HTTPException(status_code=404, detail="Plantilla predeterminada no encontrada")
    
    default_template = DEFAULT_EMAIL_TEMPLATES[template_id]
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
