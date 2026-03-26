"""Route module: seed_and_templates.py"""
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
try:
    import resend
except ImportError:
    pass

router = APIRouter()

# ==================== SEED BANKS ENDPOINT ====================

@router.post("/banks/seed")
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
<p>Si desea realizar algún ajuste en ella, escriba al correo <a href="mailto:{Email_Ejecutivo}">{Email_Ejecutivo}</a> de <strong>{Nombre_Ejecutivo}</strong>, Ejecutivo de Ventas de nuestro Equipo que lo atendió.</p>
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
    {"id": "PYME", "name": "PYME"},
    {"id": "CORP", "name": "CORP"}
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
<p>Si desea realizar algún ajuste en ella, escriba al correo <a href="mailto:{Email_Ejecutivo}">{Email_Ejecutivo}</a> de <strong>{Nombre_Ejecutivo}</strong>, Ejecutivo de Ventas de nuestro Equipo que lo atendió.</p>
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

@router.get("/email-templates")
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

@router.get("/email-templates/{template_id}")
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

@router.put("/email-templates/{template_id}")
async def update_email_template_legacy(template_id: str, template: EmailTemplate, authorization: Optional[str] = Header(None)):
    """Actualiza una plantilla de correo - LEGACY: Use /api/email-templates/{id} with FormData instead"""
    # This route is deprecated - the new CRUD routes are in projects.py
    # Keeping for backward compatibility but recommending FormData version
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

@router.post("/email-templates/reset/{template_id}")
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


