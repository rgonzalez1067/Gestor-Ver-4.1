from fastapi import FastAPI, APIRouter, HTTPException, Header, Response, status, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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
    contact1: Contact
    contact2: Contact

class Client(BaseModel):
    client_id: str = Field(default_factory=lambda: f"cli_{uuid.uuid4().hex[:12]}")
    rif: str
    legal_name: str
    fantasy_name: str
    segment: Literal["Pymes", "Corporativo", "Mixto"]
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

class IntegratorCreate(BaseModel):
    name: str
    integrator_type: Literal["Integrador", "Comercio"]
    app_name: str
    integration_modality: Literal["Bridge PG", "MPOS", "PG Universal", "PG No universal", "REST", "Stand Alone"]
    status: Literal["Certificado", "En proceso", "Suspendido"] = "En proceso"

class Integrator(BaseModel):
    integrator_id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:12]}")
    name: str
    integrator_type: str
    app_name: str
    integration_modality: str
    status: str = "En proceso"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class QuoteItem(BaseModel):
    item_type: str
    item_id: Optional[str] = None  # Opcional para items generados dinámicamente
    item_name: str
    quantity: int
    unit_price_usd: float
    total_usd: float

class QuoteCreate(BaseModel):
    client_id: str
    quote_type: Optional[str] = "VPOS"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    notes: Optional[str] = None

class Quote(BaseModel):
    quote_id: str = Field(default_factory=lambda: f"quo_{uuid.uuid4().hex[:12]}")
    quote_number: str
    client_id: str
    quote_type: str = "VPOS"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    subtotal_usd: float
    total_usd: float
    exchange_rate: float
    total_bs: float
    notes: Optional[str] = None
    quote_status: str = "draft"
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

class QuotePDFRequest(BaseModel):
    cliente_nombre: str
    cliente_rif: str = ""
    quote_type: str = "VPOS"
    pricing_model: str = "conventional"
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

@api_router.post("/clients/import")
async def import_clients(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use CSV o Excel.")
    
    content = await file.read()
    imported_count = 0
    
    try:
        if file.filename.endswith('.csv'):
            decoded = content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            
            for row in reader:
                client = Client(
                    rif=row.get('RIF', row.get('rif', '')).strip(),
                    legal_name=row.get('Nombre Jurídico', row.get('legal_name', '')).strip(),
                    fantasy_name=row.get('Nombre Fantasía', row.get('fantasy_name', '')).strip(),
                    segment=row.get('Segmento', row.get('segment', 'Pymes')).strip() or 'Pymes',
                    contact1=Contact(
                        name=row.get('Contacto1 Nombre', '').strip(),
                        phone=row.get('Contacto1 Teléfono', '').strip(),
                        email=row.get('Contacto1 Email', '').strip()
                    ),
                    contact2=Contact(name='', phone='', email='')
                )
                if client.rif and client.legal_name:
                    doc = client.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.clients.insert_one(doc)
                    imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="Para archivos Excel, por favor convierta a CSV primero")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar archivo: {str(e)}")
    
    return {"message": f"{imported_count} clientes importados exitosamente"}

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

@api_router.post("/banks/import")
async def import_banks(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use CSV o Excel.")
    
    content = await file.read()
    imported_count = 0
    
    try:
        if file.filename.endswith('.csv'):
            decoded = content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            
            for row in reader:
                bank = Bank(
                    name=row.get('Nombre', row.get('nombre', row.get('name', ''))).strip(),
                    type=row.get('Tipo', row.get('tipo', row.get('type', 'Banco'))).strip(),
                    country=row.get('País', row.get('pais', row.get('country', 'Venezuela'))).strip(),
                    products=[]
                )
                if bank.name:
                    doc = bank.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.banks.insert_one(doc)
                    imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="Para archivos Excel, por favor convierta a CSV primero")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar archivo: {str(e)}")
    
    return {"message": f"{imported_count} bancos importados exitosamente"}

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

@api_router.post("/services/import")
async def import_services(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Use CSV o Excel.")
    
    content = await file.read()
    imported_count = 0
    
    try:
        if file.filename.endswith('.csv'):
            decoded = content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            
            for row in reader:
                service = Service(
                    category='General',
                    name=row.get('Nombre', row.get('nombre', row.get('name', ''))).strip(),
                    setup_cost_conventional=float(row.get('Setup Convencional', row.get('setup_cost_conventional', 0)) or 0),
                    monthly_cost_conventional=float(row.get('Mensual Convencional', row.get('monthly_cost_conventional', 0)) or 0),
                    setup_cost_outsourcing=float(row.get('Setup Outsourcing', row.get('setup_cost_outsourcing', 0)) or 0),
                    monthly_cost_outsourcing=float(row.get('Mensual Outsourcing', row.get('monthly_cost_outsourcing', 0)) or 0),
                    description=row.get('Descripción', row.get('descripcion', row.get('description', ''))).strip()
                )
                if service.name:
                    doc = service.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.services.insert_one(doc)
                    imported_count += 1
        else:
            raise HTTPException(status_code=400, detail="Para archivos Excel, por favor convierta a CSV primero")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar archivo: {str(e)}")
    
    return {"message": f"{imported_count} servicios importados exitosamente"}

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
    
    subtotal_usd = sum(item.total_usd for item in quote_data.services) + sum(item.total_usd for item in quote_data.hardware)
    total_usd = subtotal_usd
    total_bs = total_usd * exchange_rate
    
    count = await db.quotes.count_documents({})
    quote_number = f"QUO-{count + 1:05d}"
    
    quote = Quote(
        quote_number=quote_number,
        client_id=quote_data.client_id,
        quote_type=quote_data.quote_type or "VPOS",
        services=quote_data.services,
        hardware=quote_data.hardware,
        subtotal_usd=subtotal_usd,
        total_usd=total_usd,
        exchange_rate=exchange_rate,
        total_bs=total_bs,
        notes=quote_data.notes
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

# ==================== CONFIGURATION ENDPOINTS ====================

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
