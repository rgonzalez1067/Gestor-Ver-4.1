"""API Pública para recepción de Contactos Iniciales desde fuentes externas.

Este módulo expone endpoints que NO requieren autenticación de usuario,
protegidos únicamente por API Key. Permite a widgets web, aliados comerciales
y sistemas externos enviar leads directamente a MegaNexus.
"""
from fastapi import APIRouter, HTTPException, Header, Request
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid
import logging
import os

from config import db

router = APIRouter()

# API Key para autenticación de fuentes externas
EXTERNAL_API_KEY = os.environ.get("EXTERNAL_API_KEY", "mnx-ext-2026-key")

# Rate limiting simple en memoria
_rate_limits = {}  # ip -> (count, window_start)
RATE_LIMIT_MAX = 30  # max requests
RATE_LIMIT_WINDOW = 3600  # per hour


class ExternalContactPayload(BaseModel):
    """Payload que reciben los endpoints públicos."""
    contact_name: str = Field(..., min_length=2, max_length=150, description="Nombre completo de la persona")
    phone: str = Field(..., min_length=7, max_length=20, description="Teléfono con código de país")
    email: str = Field(..., description="Correo electrónico")
    legal_name: str = Field(..., min_length=2, max_length=200, description="Razón social o nombre de la empresa")
    interest_notes: Optional[str] = Field("", max_length=500, description="Productos o servicios de interés")
    referred_by: Optional[str] = Field("", max_length=150, description="Origen del referido (aliado, campaña, widget, etc.)")


def _check_rate_limit(client_ip: str) -> bool:
    """Verifica rate limiting por IP. Retorna True si está permitido."""
    now = datetime.now(timezone.utc).timestamp()
    if client_ip in _rate_limits:
        count, window_start = _rate_limits[client_ip]
        if now - window_start > RATE_LIMIT_WINDOW:
            _rate_limits[client_ip] = (1, now)
            return True
        if count >= RATE_LIMIT_MAX:
            return False
        _rate_limits[client_ip] = (count + 1, window_start)
        return True
    _rate_limits[client_ip] = (1, now)
    return True


@router.post("/external/contacts")
async def create_external_contact(
    data: ExternalContactPayload,
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """
    Endpoint público para recibir contactos desde fuentes externas.
    
    **Autenticación**: Header `X-API-Key` con la clave proporcionada por MegaNexus.
    
    **Rate Limit**: 30 peticiones por hora por IP.
    """
    # Validar API Key
    if not x_api_key or x_api_key != EXTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida o no proporcionada")
    
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Límite de peticiones excedido. Intente en 1 hora.")
    
    # Validar email básico
    if "@" not in data.email or "." not in data.email:
        raise HTTPException(status_code=422, detail="Email inválido")
    
    # Verificar duplicado por email o teléfono (últimas 24h)
    yesterday = (datetime.now(timezone.utc).timestamp() - 86400)
    existing = await db.initial_contacts.find_one({
        "$or": [
            {"email": data.email.strip().lower()},
            {"phone": data.phone.strip()}
        ],
        "source": "external_api"
    })
    if existing:
        return {
            "status": "duplicate",
            "message": "Este contacto ya fue registrado previamente.",
            "contact_id": existing.get("contact_id")
        }
    
    # Crear contacto
    contact_id = f"ic_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    # Buscar usuario por defecto para asignación (primer admin o gerente)
    default_user = await db.users.find_one(
        {"role": "admin", "is_active": {"$ne": False}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
    )
    assigned_name = "Sin asignar"
    assigned_user_id = None
    if default_user:
        assigned_name = f"{default_user.get('first_name', '')} {default_user.get('last_name', '')}".strip()
        assigned_user_id = default_user["user_id"]
    
    referred = (data.referred_by or "").strip() or "API Externa"
    
    contact = {
        "contact_id": contact_id,
        "contact_name": data.contact_name.strip(),
        "phone": data.phone.strip(),
        "email": data.email.strip().lower(),
        "legal_name": data.legal_name.strip(),
        "interest_notes": (data.interest_notes or "").strip()[:500],
        "referred_by": referred,
        "assigned_to_user_id": assigned_user_id,
        "assigned_to_name": assigned_name,
        "due_date": None,
        "created_by_user_id": None,
        "created_by_name": f"API Externa ({referred})",
        "sede": "PYME",
        "is_converted": False,
        "converted_client_id": None,
        "source": "external_api",
        "source_ip": client_ip,
        "created_at": now,
        "updated_at": now,
        "bitacora": [
            {
                "entry_id": f"be_{uuid.uuid4().hex[:8]}",
                "action": "created",
                "description": f"Contacto recibido vía API Externa. Referido por: {referred}",
                "user_name": "Sistema (API)",
                "timestamp": now
            }
        ]
    }
    
    await db.initial_contacts.insert_one(contact)
    del contact["_id"]
    
    logging.info(f"Contacto externo creado: {contact_id} | {data.contact_name} | Referido: {referred} | IP: {client_ip}")
    
    return {
        "status": "created",
        "message": "Contacto registrado exitosamente en MegaNexus.",
        "contact_id": contact_id,
        "assigned_to": assigned_name,
    }


@router.get("/external/health")
async def external_health():
    """Health check para verificar disponibilidad de la API externa."""
    return {"status": "ok", "service": "MegaNexus External API", "version": "1.0"}
