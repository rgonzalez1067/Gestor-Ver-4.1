"""
Modelos Pydantic y constantes de la aplicación.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid

# ==================== MODELS ====================

class Contact(BaseModel):
    name: str
    phone: str
    email: EmailStr

class ContactCRM(BaseModel):
    contact_id: str = Field(default_factory=lambda: f"cnt_{uuid.uuid4().hex[:8]}")
    full_name: str = ""
    first_name: Optional[str] = None  # Legacy
    last_name: Optional[str] = None   # Legacy
    phone: str = ""
    email: str = ""
    role: Literal["Administrativo", "Financiero", "Técnico", "Cuentas por Pagar", "Operativo"] = "Administrativo"

# Categorías Comerciales disponibles
CATEGORIAS_COMERCIALES = [
    "Supermercados", "Abastos", "Restaurantes", "Panaderías", "Bares", "Discotecas",
    "Comida Rápida", "Cafeterías", "Tiendas de Ropa", "Boutique", "Salón de Belleza",
    "Barbería", "Spa/Salud", "Gimnasios", "Cosmética", "Tiendas de Calzados",
    "Mueblerías", "Ferretería", "Tiendas de Electrodomésticos", "Jardinería",
    "Joyerías", "Tienda de Electrónica", "Venta de Software", "Jugueterías",
    "Librerías", "Tiendas por Departamento", "Colegios", "Universidades",
    "Inmobiliarias", "Clínicas",
]

class ClientCreate(BaseModel):
    rif: str
    legal_name: str
    fantasy_name: str
    segment: str = "Pymes"
    condicion: str = "Prospecto"
    referidor: Optional[str] = None
    address: Optional[str] = None
    branch_address: Optional[str] = None
    categoria_comercial: Optional[str] = None
    sucursal: str = "Principal"
    grupo_economico: Optional[str] = None
    ejecutivo_propietario: Optional[str] = None
    ejecutivo_user_id: Optional[str] = None
    cantidad_tiendas: Optional[int] = None
    cantidad_cajas: Optional[int] = None
    fecha_primer_contacto: Optional[str] = None
    tipo_contacto: Optional[str] = None
    tipo_servicio: List[str] = []
    integrador_id: Optional[str] = None
    integrador_name: Optional[str] = None
    aplicativo: Optional[str] = None
    contacts: List[ContactCRM] = []
    contact1: Optional[Contact] = None
    contact2: Optional[Contact] = None

class Client(BaseModel):
    client_id: str = Field(default_factory=lambda: f"cli_{uuid.uuid4().hex[:12]}")
    rif: str
    legal_name: str
    fantasy_name: str
    segment: str = "Pymes"
    condicion: str = "Prospecto"
    referidor: Optional[str] = None
    address: Optional[str] = None
    branch_address: Optional[str] = None
    categoria_comercial: Optional[str] = None
    sucursal: str = "Principal"
    grupo_economico: Optional[str] = None
    ejecutivo_propietario: Optional[str] = None
    ejecutivo_user_id: Optional[str] = None
    cantidad_tiendas: Optional[int] = None
    cantidad_cajas: Optional[int] = None
    fecha_primer_contacto: Optional[str] = None
    tipo_contacto: Optional[str] = None
    tipo_servicio: List[str] = []
    integrador_id: Optional[str] = None
    integrador_name: Optional[str] = None
    aplicativo: Optional[str] = None
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
    contacted_person: Optional[str] = None

class BankProduct(BaseModel):
    product_name: str
    description: Optional[str] = None
    vpos_available: bool = False
    gateway_available: bool = False
    mpos_available: bool = False
    link_available: bool = False
    pg_setup_cost: float = 0  # Costo de setup para Payment Gateway

class BankIntegration(BaseModel):
    """Integración en curso con un banco"""
    integration_id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:8]}")
    service_name: str
    component_type: str  # "VPOS/MPOS" o "PG/Link"
    tipo_corp: str = ""
    status: Literal["PreProd", "Primer Prod", "Masificación"] = "PreProd"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BankCreate(BaseModel):
    name: str
    type: str
    country: str
    rif: Optional[str] = None
    bank_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    bank_logo_url: Optional[str] = None
    products: List[BankProduct] = []
    integrations: List[BankIntegration] = []

class Bank(BaseModel):
    bank_id: str = Field(default_factory=lambda: f"bnk_{uuid.uuid4().hex[:12]}")
    name: str
    type: str
    country: str
    rif: Optional[str] = None
    bank_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    bank_logo_url: Optional[str] = None
    products: List[BankProduct] = []
    integrations: List[BankIntegration] = []
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
    asset_type: Literal["Bien", "Servicio"] = "Bien"
    price_usd: float
    price_bs_usd: float
    description: Optional[str] = None

class Hardware(BaseModel):
    hardware_id: str = Field(default_factory=lambda: f"hwr_{uuid.uuid4().hex[:12]}")
    name: str
    type: str
    asset_type: str = "Bien"
    price_usd: float
    price_bs_usd: float
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ServiceCreate(BaseModel):
    category: str
    name: str
    service_type: Literal["Producto", "Servicio"] = "Servicio"
    tipo_corp: Literal["Derecho de Uso", "Apoyo Técnico", "Soporte y Monitoreo"]
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
    service_type: str = "Servicio"
    tipo_corp: str = ""
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
INTEGRATION_MODALITIES = ["Bridge PG", "MPOS", "PG Universal", "PG No universal", "REST", "Stand Alone", "TKN No Universal", "TKN Universal", "Web Link de Pago Modalidad No Universal", "Web Link de Pago Modalidad Universal", "Wrapper"]
INTEGRATOR_STATUSES = ["Certificado", "En proceso", "Suspendido"]
INTEGRATION_PHASES = ["Negociación", "Desarrollo", "QA", "SQA", "Producción"]

class TechnicalContact(BaseModel):
    contact_id: str = Field(default_factory=lambda: f"ctc_{uuid.uuid4().hex[:8]}")
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

class BitacoraEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: f"bit_{uuid.uuid4().hex[:8]}")
    integrator_id: str
    description: str
    contact_id: Optional[str] = None
    contact_name: Optional[str] = None
    date: str  # ISO date
    commitment: Optional[str] = None
    commitment_deadline: Optional[str] = None  # ISO date
    commitment_completed: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EvolutionEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: f"evo_{uuid.uuid4().hex[:8]}")
    integrator_id: str
    comment: str
    phase: str = ""  # Deprecated but kept for backwards compatibility
    contact_person: str = ""  # Persona de contacto (nombre libre o del CRM)
    date: str  # ISO date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

class ProductEvolutionEntry(BaseModel):
    """Entrada de bitácora de evolución para una integración de producto bancario."""
    entry_id: str = Field(default_factory=lambda: f"pev_{uuid.uuid4().hex[:8]}")
    bank_id: str
    integration_id: str
    comment: str
    phase: str  # PreProd, Primer Prod, Masificación
    date: str  # ISO date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

# ==================== NEW PRODUCTS (R&D Pipeline) ====================

class NewProduct(BaseModel):
    """Producto nuevo en pipeline de I+D antes de despliegue oficial."""
    product_id: str = Field(default_factory=lambda: f"npd_{uuid.uuid4().hex[:8]}")
    service_id: str  # Referencia al catálogo maestro de servicios
    service_name: str
    component_type: str  # "VPOS/MPOS" o "PG/Link"
    tipo_corp: str = ""
    bank_id: str  # Banco patrocinador/socio
    bank_name: str = ""
    status: Literal["Negociación", "DESA", "SQA", "IMPLE", "Promovido"] = "Negociación"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class NewProductCreate(BaseModel):
    service_id: str  # ID del servicio del catálogo maestro
    component_type: str
    bank_id: str
    notes: Optional[str] = None

class NewProductEvolutionEntry(BaseModel):
    """Entrada de bitácora de evolución para un producto nuevo en pipeline I+D."""
    entry_id: str = Field(default_factory=lambda: f"npe_{uuid.uuid4().hex[:8]}")
    product_id: str
    comment: str
    phase: str  # Negociación, DESA, SQA, IMPLE
    date: str  # ISO date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

class StatusTransitionLog(BaseModel):
    """Log de auditoría para transiciones de estado en pipeline I+D."""
    transition_id: str = Field(default_factory=lambda: f"stl_{uuid.uuid4().hex[:8]}")
    product_id: str
    old_status: str
    new_status: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str
    user_name: str
    days_in_previous_phase: Optional[int] = None

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
    updated_count: int = 0
    cert_updates_count: int = 0
    error_count: int
    skipped_count: int
    errors: List[ImportError]
    message: str

class IntegratorCreate(BaseModel):
    name: str
    integrator_type: Literal["Integrador", "Comercio"]
    integration_type: Optional[str] = None
    app_name: str
    integration_modality: Optional[str] = None
    integrator_status: Literal["Certificado", "En proceso", "Suspendido"] = "En proceso"
    gestor: Optional[str] = None
    categoria: Optional[str] = None
    certifications: Optional[dict] = None
    last_contact_date: Optional[str] = None
    contacts: Optional[List[TechnicalContact]] = None
    integration_phase: Optional[str] = "Negociación"

class Integrator(BaseModel):
    integrator_id: str = Field(default_factory=lambda: f"int_{uuid.uuid4().hex[:12]}")
    name: str
    integrator_type: str
    integration_type: Optional[str] = None
    app_name: str
    integration_modality: Optional[str] = None
    integrator_status: str = "En proceso"
    gestor: Optional[str] = None
    gestor_user_id: Optional[str] = None
    categoria: Optional[str] = None
    implementador: Optional[str] = None
    implementador_user_id: Optional[str] = None
    certifications: Optional[dict] = None
    last_contact_date: Optional[str] = None
    contacts: Optional[List[TechnicalContact]] = None
    integration_phase: Optional[str] = "Negociación"
    has_overdue_commitments: Optional[bool] = None
    assigned_at: Optional[str] = None
    assigned_by: Optional[str] = None
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
    # Metadatos de comportamiento (para restaurar correctamente al editar)
    lockBancos: Optional[bool] = None
    autoBancos: Optional[bool] = None
    bancosOverride: Optional[int] = None
    totalOverride: Optional[float] = None
    isAutoLinked: Optional[bool] = None

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

# ==================== TABLA DE COSTOS RECURRENTES PAYMENT GATEWAY ====================
PG_RECURRING_COSTS_TABLE = {
    "ranges": [
        {"rango": 1, "min": 0, "max": 200, "label": "0 - 200"},
        {"rango": 2, "min": 201, "max": 400, "label": "201 - 400"},
        {"rango": 3, "min": 401, "max": 600, "label": "401 - 600"},
        {"rango": 4, "min": 601, "max": 800, "label": "601 - 800"},
        {"rango": 5, "min": 801, "max": 1000, "label": "801 - 1,000"},
        {"rango": 6, "min": 1001, "max": 2000, "label": "1,001 - 2,000"},
        {"rango": 7, "min": 2001, "max": 3000, "label": "2,001 - 3,000"},
        {"rango": 8, "min": 3001, "max": 4000, "label": "3,001 - 4,000"},
        {"rango": 9, "min": 4001, "max": 5000, "label": "4,001 - 5,000"},
        {"rango": 10, "min": 5001, "max": 6000, "label": "5,001 - 6,000"},
        {"rango": 11, "min": 6001, "max": 7000, "label": "6,001 - 7,000"},
        {"rango": 12, "min": 7001, "max": 8000, "label": "7,001 - 8,000"},
        {"rango": 13, "min": 8001, "max": 9000, "label": "8,001 - 9,000"},
        {"rango": 14, "min": 9001, "max": 10000, "label": "9,001 - 10,000"},
        {"rango": 15, "min": 10001, "max": 1000000, "label": "10,001+"}
    ],
    "product_counts": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "data": [
        {"rango": 1, "1": {"base": 30.0, "tope": 0.15}, "2": {"base": 36.0, "tope": 0.18}, "3": {"base": 42.0, "tope": 0.21}, "4": {"base": 48.0, "tope": 0.24}, "5": {"base": 54.0, "tope": 0.27}, "6": {"base": 60.0, "tope": 0.3}, "7": {"base": 66.0, "tope": 0.33}, "8": {"base": 72.0, "tope": 0.36}, "9": {"base": 78.0, "tope": 0.39}, "10": {"base": 84.0, "tope": 0.42}, "11": {"base": 90.0, "tope": 0.45}},
        {"rango": 2, "1": {"base": 31.25, "tope": 0.078125}, "2": {"base": 37.5, "tope": 0.09375}, "3": {"base": 43.75, "tope": 0.109375}, "4": {"base": 50.0, "tope": 0.125}, "5": {"base": 56.25, "tope": 0.140625}, "6": {"base": 62.5, "tope": 0.15625}, "7": {"base": 68.75, "tope": 0.171875}, "8": {"base": 75.0, "tope": 0.1875}, "9": {"base": 81.25, "tope": 0.203125}, "10": {"base": 87.5, "tope": 0.21875}, "11": {"base": 93.75, "tope": 0.234375}},
        {"rango": 3, "1": {"base": 33.5, "tope": 0.055833}, "2": {"base": 40.2, "tope": 0.067}, "3": {"base": 46.9, "tope": 0.078167}, "4": {"base": 53.6, "tope": 0.089333}, "5": {"base": 60.3, "tope": 0.1005}, "6": {"base": 67.0, "tope": 0.111667}, "7": {"base": 73.7, "tope": 0.122833}, "8": {"base": 80.4, "tope": 0.134}, "9": {"base": 87.1, "tope": 0.145167}, "10": {"base": 93.8, "tope": 0.156333}, "11": {"base": 100.5, "tope": 0.1675}},
        {"rango": 4, "1": {"base": 36.0, "tope": 0.045}, "2": {"base": 43.2, "tope": 0.054}, "3": {"base": 50.4, "tope": 0.063}, "4": {"base": 57.6, "tope": 0.072}, "5": {"base": 64.8, "tope": 0.081}, "6": {"base": 72.0, "tope": 0.09}, "7": {"base": 79.2, "tope": 0.099}, "8": {"base": 86.4, "tope": 0.108}, "9": {"base": 93.6, "tope": 0.117}, "10": {"base": 100.8, "tope": 0.126}, "11": {"base": 108.0, "tope": 0.135}},
        {"rango": 5, "1": {"base": 38.4, "tope": 0.0384}, "2": {"base": 46.1, "tope": 0.0461}, "3": {"base": 53.8, "tope": 0.0538}, "4": {"base": 61.5, "tope": 0.0615}, "5": {"base": 69.2, "tope": 0.0692}, "6": {"base": 76.9, "tope": 0.0769}, "7": {"base": 84.6, "tope": 0.0846}, "8": {"base": 92.3, "tope": 0.0923}, "9": {"base": 100.0, "tope": 0.1}, "10": {"base": 107.7, "tope": 0.1077}, "11": {"base": 115.4, "tope": 0.1154}},
        {"rango": 6, "1": {"base": 48.0, "tope": 0.024}, "2": {"base": 57.6, "tope": 0.0288}, "3": {"base": 67.2, "tope": 0.0336}, "4": {"base": 76.8, "tope": 0.0384}, "5": {"base": 86.4, "tope": 0.0432}, "6": {"base": 96.0, "tope": 0.048}, "7": {"base": 105.6, "tope": 0.0528}, "8": {"base": 115.2, "tope": 0.0576}, "9": {"base": 124.8, "tope": 0.0624}, "10": {"base": 134.4, "tope": 0.0672}, "11": {"base": 144.0, "tope": 0.072}},
        {"rango": 7, "1": {"base": 55.2, "tope": 0.0184}, "2": {"base": 66.25, "tope": 0.022083}, "3": {"base": 77.3, "tope": 0.025767}, "4": {"base": 88.35, "tope": 0.02945}, "5": {"base": 99.4, "tope": 0.033133}, "6": {"base": 110.45, "tope": 0.036817}, "7": {"base": 121.5, "tope": 0.0405}, "8": {"base": 132.55, "tope": 0.044183}, "9": {"base": 143.6, "tope": 0.047867}, "10": {"base": 154.65, "tope": 0.05155}, "11": {"base": 165.7, "tope": 0.055233}},
        {"rango": 8, "1": {"base": 61.2, "tope": 0.0153}, "2": {"base": 73.45, "tope": 0.018363}, "3": {"base": 85.7, "tope": 0.021425}, "4": {"base": 97.95, "tope": 0.024488}, "5": {"base": 110.2, "tope": 0.02755}, "6": {"base": 122.45, "tope": 0.030613}, "7": {"base": 134.7, "tope": 0.033675}, "8": {"base": 146.95, "tope": 0.036737}, "9": {"base": 159.2, "tope": 0.0398}, "10": {"base": 171.45, "tope": 0.042862}, "11": {"base": 183.7, "tope": 0.045925}},
        {"rango": 9, "1": {"base": 69.7, "tope": 0.01394}, "2": {"base": 83.7, "tope": 0.01674}, "3": {"base": 97.7, "tope": 0.01954}, "4": {"base": 111.7, "tope": 0.02234}, "5": {"base": 125.7, "tope": 0.02514}, "6": {"base": 139.7, "tope": 0.02794}, "7": {"base": 153.7, "tope": 0.03074}, "8": {"base": 167.7, "tope": 0.03354}, "9": {"base": 181.7, "tope": 0.03634}, "10": {"base": 195.7, "tope": 0.03914}, "11": {"base": 209.7, "tope": 0.04194}},
        {"rango": 10, "1": {"base": 74.3, "tope": 0.012383}, "2": {"base": 89.1, "tope": 0.01485}, "3": {"base": 103.9, "tope": 0.017317}, "4": {"base": 118.7, "tope": 0.019783}, "5": {"base": 133.5, "tope": 0.02225}, "6": {"base": 148.3, "tope": 0.024717}, "7": {"base": 163.1, "tope": 0.027183}, "8": {"base": 177.9, "tope": 0.02965}, "9": {"base": 192.7, "tope": 0.032117}, "10": {"base": 207.5, "tope": 0.034583}, "11": {"base": 222.3, "tope": 0.03705}},
        {"rango": 11, "1": {"base": 82.85, "tope": 0.011836}, "2": {"base": 99.45, "tope": 0.014207}, "3": {"base": 116.05, "tope": 0.016579}, "4": {"base": 132.65, "tope": 0.01895}, "5": {"base": 149.25, "tope": 0.021321}, "6": {"base": 165.85, "tope": 0.023693}, "7": {"base": 182.45, "tope": 0.026064}, "8": {"base": 199.05, "tope": 0.028436}, "9": {"base": 215.65, "tope": 0.030807}, "10": {"base": 232.25, "tope": 0.033179}, "11": {"base": 248.85, "tope": 0.03555}},
        {"rango": 12, "1": {"base": 87.7, "tope": 0.010962}, "2": {"base": 105.3, "tope": 0.013162}, "3": {"base": 122.9, "tope": 0.015362}, "4": {"base": 140.5, "tope": 0.017562}, "5": {"base": 158.1, "tope": 0.019762}, "6": {"base": 175.7, "tope": 0.021962}, "7": {"base": 193.3, "tope": 0.024162}, "8": {"base": 210.9, "tope": 0.026362}, "9": {"base": 228.5, "tope": 0.028562}, "10": {"base": 246.1, "tope": 0.030762}, "11": {"base": 263.7, "tope": 0.032962}},
        {"rango": 13, "1": {"base": 91.25, "tope": 0.010139}, "2": {"base": 109.5, "tope": 0.012167}, "3": {"base": 127.75, "tope": 0.014194}, "4": {"base": 146.0, "tope": 0.016222}, "5": {"base": 164.25, "tope": 0.01825}, "6": {"base": 182.5, "tope": 0.020278}, "7": {"base": 200.75, "tope": 0.022306}, "8": {"base": 219.0, "tope": 0.024333}, "9": {"base": 237.25, "tope": 0.026361}, "10": {"base": 255.5, "tope": 0.028389}, "11": {"base": 273.75, "tope": 0.030417}},
        {"rango": 14, "1": {"base": 96.0, "tope": 0.0096}, "2": {"base": 115.2, "tope": 0.01152}, "3": {"base": 134.4, "tope": 0.01344}, "4": {"base": 153.6, "tope": 0.01536}, "5": {"base": 172.8, "tope": 0.01728}, "6": {"base": 192.0, "tope": 0.0192}, "7": {"base": 211.2, "tope": 0.02112}, "8": {"base": 230.4, "tope": 0.02304}, "9": {"base": 249.6, "tope": 0.02496}, "10": {"base": 268.8, "tope": 0.02688}, "11": {"base": 288.0, "tope": 0.0288}},
        {"rango": 15, "1": {"base": None, "tope": 0.00924}, "2": {"base": None, "tope": 0.00948}, "3": {"base": None, "tope": 0.00972}, "4": {"base": None, "tope": 0.00996}, "5": {"base": None, "tope": 0.0102}, "6": {"base": None, "tope": 0.01044}, "7": {"base": None, "tope": 0.01068}, "8": {"base": None, "tope": 0.01092}, "9": {"base": None, "tope": 0.01116}, "10": {"base": None, "tope": 0.0114}, "11": {"base": None, "tope": 0.01164}}
    ]
}

# Modelo para items de Setup de Payment Gateway
class PGSetupItem(BaseModel):
    concepto: str
    costo: float = 0
    banco: str = "N/A"
    observacion: str = ""

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
    # Campos específicos para Payment Gateway
    pg_setup_items: List[dict] = []
    pg_recurring_cost: Optional[dict] = None
    pg_transaction_range: Optional[int] = None
    # Descuentos independientes
    descuento_setup: float = 0
    descuento_recurrente: float = 0
    # Parámetros dinámicos VPOS
    requires_pinpad_config: bool = True
    requires_vpn: bool = True
    # Cliente en producción
    is_production_client: bool = False
    production_items: List[dict] = []
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
    client_name: Optional[str] = None  # Nombre del cliente para visualización rápida
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
    sede: str = "PYME"  # "PYME" o "CORP"
    # Segmento de cliente (seleccionado en el wizard)
    client_segment: str = "PYME"  # "PYME" o "CORP" — tagging de segmento
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
    # Campos específicos para Payment Gateway
    pg_setup_items: List[dict] = []  # Items de setup PG: {concepto, costo, banco, observacion}
    pg_recurring_cost: Optional[dict] = None  # {rango_index, num_products, base, tope, rango_label}
    pg_transaction_range: Optional[int] = None  # Índice del rango de transacciones seleccionado
    # Descuentos independientes
    descuento: float = 0
    descuento_setup: float = 0
    descuento_recurrente: float = 0
    # Parámetros dinámicos VPOS
    requires_pinpad_config: bool = True
    requires_vpn: bool = True
    # Cliente en producción
    is_production_client: bool = False
    production_items: List[dict] = []
    attachments: List[dict] = []  # Lista de anexos: {attachment_id, category, filename, url, uploaded_by, uploaded_at}
    # Flujo Irregular
    is_irregular: Optional[bool] = None  # True si tiene excepciones de flujo
    irregular_exceptions: Optional[List[dict]] = None  # Lista de excepciones registradas
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

# ==================== PROJECT MODELS ====================

PROJECT_STATUSES = ["Pendiente por Asignar", "Asignado / En Proceso", "Detenido por Cliente/Banco", "Finalizado / Producción"]

class ProjectNote(BaseModel):
    note_id: str = Field(default_factory=lambda: f"pn_{uuid.uuid4().hex[:8]}")
    text: str
    created_by: str = ""
    created_by_name: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: f"prj_{uuid.uuid4().hex[:12]}")
    project_number: str = ""
    # Relación con cotización
    quote_id: str
    quote_number: str = ""
    quote_pdf_url: Optional[str] = None
    # Datos heredados del cliente
    client_id: str
    client_name: str = ""
    client_rif: str = ""
    client_sede: str = ""
    # Datos heredados de la cotización
    quote_category: str = "implementation"
    quote_type: str = "VPOS"
    services: List[dict] = []
    hardware: List[dict] = []
    equipment_items: List[dict] = []
    pg_setup_items: List[dict] = []
    banks: List[dict] = []
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    total_usd: float = 0
    total_bs: float = 0
    # Estado y asignación
    status: str = "Pendiente por Asignar"
    assigned_to_user_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_by_user_id: Optional[str] = None
    assigned_by_name: Optional[str] = None
    assigned_at: Optional[str] = None
    estimated_delivery_date: Optional[str] = None
    priority: str = "Normal"  # Baja, Normal, Alta, Urgente
    # Notas e historial
    notes: List[ProjectNote] = []
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

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
    quote_type: str = "VPOS"  # "VPOS", "MPOS", "GATEWAY", "LINK"
    pricing_model: str = "conventional"  # MPOS siempre usa "outsourcing"
    cantidad_cajas: int = 1  # Total de cajas cotizadas
    # Nuevos campos de integración y hardware
    integrator_name: str = ""
    integrator_app_name: str = ""
    pinpad_model: str = ""
    sponsor_bank_name: str = ""
    setup_items: List[QuotePDFItem] = []
    recurring_basic_items: List[QuotePDFItem] = []
    recurring_other_items: List[QuotePDFItem] = []
    production_items: List[QuotePDFItem] = []  # Items de cliente en producción
    descuento: float = 0
    descuento_setup: float = 0
    descuento_recurrente: float = 0
    notes: str = ""
    pg_setup_items: List[dict] = []  # Items de setup PG para PDF
    pg_recurring_cost: Optional[dict] = None  # Recurring cost data for PG
    is_production_client: bool = False

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None

class UserRegister(BaseModel):
    """Modelo para registro de usuario"""
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    cedula: Optional[str] = Field(default=None, min_length=6, max_length=15)  # Cédula de identidad (opcional)
    email: EmailStr
    password: str = Field(..., min_length=8)  # Mínimo 8 caracteres
    phone: Optional[str] = None  # Teléfono
    cargo: Optional[str] = None  # Cargo/Función
    departamento: Optional[str] = None  # Departamento
    sede: str = Field(default="PYME", description="Sede del usuario: PYME o CORP")

# Departamentos disponibles
DEPARTAMENTOS = ["Implementación", "Infraestructura", "Ventas Pyme", "Ventas Corporativas", "Administración", "Dirección"]

# Cargos disponibles
CARGOS = [
    "Gerente de Ventas Pyme",
    "Gerente de Ventas Corporativas",
    "Ejecutivo de Ventas Pyme",
    "Ejecutivo de Ventas Corporativas",
    "Gerente de Administración",
    "Coordinador de Administración",
    "Asistente Administrativo (Almacén)",
    "Técnico de Infraestructura",
    "Gerente de Implementación",
    "Coordinador de Implementación",
    "Implementador",
    "Director",
    "Gerente de Infraestructura",
]

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
    sede: str = "PYME"  # "PYME" o "CORP"
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


# ==================== INVENTORY MODULE ====================

class Warehouse(BaseModel):
    """Almacén físico para control de inventario."""
    warehouse_id: str = Field(default_factory=lambda: f"whs_{uuid.uuid4().hex[:8]}")
    name: str
    location: str = ""
    notes: str = ""
    responsible_user_id: str = ""   # FK a usuario responsable
    responsible_name: str = ""       # Nombre para display rápido
    responsible_email: str = ""      # Email para alertas
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WarehouseCreate(BaseModel):
    name: str
    location: str = ""
    notes: str = ""
    responsible_user_id: str = ""

MOVEMENT_TYPES = ["entrada", "salida", "transferencia_entrada", "transferencia_salida"]

class InventoryMovement(BaseModel):
    """Movimiento de inventario (entrada, salida, transferencia)."""
    movement_id: str = Field(default_factory=lambda: f"mov_{uuid.uuid4().hex[:8]}")
    warehouse_id: str
    item_id: str          # hardware_id de la tabla Bienes y Servicios
    item_name: str
    item_type: str        # tipo del hardware (POS, Pinpad, Cable, etc.)
    movement_type: str    # entrada, salida, transferencia_entrada, transferencia_salida
    quantity: int
    unit_cost: float = 0
    serials: List[str] = []  # Solo para hardware crítico (POS/Pinpad)
    reference: str = ""      # Ej: "COT-2026-03-001" o "Transferencia desde Almacén X"
    client_name: str = ""    # Para salidas por venta
    client_id: str = ""      # FK opcional a clientes
    quote_id: str = ""       # FK opcional a cotizaciones
    quote_number: str = ""   # Nro de cotización para referencia rápida
    notes: str = ""
    transfer_id: str = ""    # ID que vincula salida+entrada en transferencias
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

SERIALIZED_TYPES = ["pos", "pinpad", "mpos"]
