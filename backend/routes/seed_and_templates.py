"""Route module: seed_and_templates.py"""
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
    template_id: str
    name: str
    subject: str
    body_html: str
    description: Optional[str] = None
    is_active: bool = True
    context: Optional[str] = None  # "COTIZACIONES" | "IMPLEMENTACION" | "ADMINISTRACION" | "CLIENTES"
    is_custom: bool = False  # True si fue creada manualmente por un usuario admin (no parte del catálogo legacy)
    group: Optional[str] = None  # "Pyme" | "Corp" | "Implementación" | "General" — categoría visible en el Motor de Notificaciones
    sede: Optional[str] = None   # "PYME" | "CORP" — para alinear con plantillas legacy por sede
    is_project_template: Optional[bool] = None

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
    },
    "repair_invoice": {
        "name": "Facturación de Reparaciones",
        "description": "Se envía a Ventas cuando Administración genera y carga la factura de una cotización de reparación",
        "subject": "[FACTURADA] Reparación - Cotización #{quote_number} - {client_name} - Sede {sede_name}",
        "body_html": """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facturación de Reparación</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f7f9; color: #333333;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f4f7f9;">
        <tr>
            <td align="center" style="padding: 20px 0;">

                <table border="0" cellpadding="0" cellspacing="0" width="95%" style="max-width: 900px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">

                    <tr>
                        <td align="left" style="padding: 25px 40px; background-color: #003366;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 20px; letter-spacing: 1px; text-transform: uppercase; font-weight: bold;">
                                Factura de Reparación Generada y Cargada
                            </h1>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 40px;">
                            <p style="font-size: 16px; margin-bottom: 25px;">Estimado <strong>Equipo de Ventas</strong>,</p>

                            <p style="font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                                Les informamos que la factura asociada a la reparación de equipos aprobada recientemente ya ha sido <strong>generada y cargada exitosamente</strong> en el sistema.
                            </p>

                            <div style="background-color: #f8fafc; border: 1px solid #cbd5e0; border-radius: 6px; padding: 20px; margin-bottom: 30px;">
                                <h3 style="color: #003366; margin-top: 0; font-size: 16px; border-bottom: 1px solid #cbd5e0; padding-bottom: 10px;">Referencia de la Operación:</h3>
                                <ul style="list-style: none; padding: 0; margin: 15px 0 0 0; font-size: 16px;">
                                    <li style="margin-bottom: 10px;"><strong>Cotización Nro:</strong> <span style="color: #2b6cb0;">{quote_number}</span></li>
                                    <li><strong>Cliente:</strong> {client_name}</li>
                                </ul>
                            </div>

                            <p style="font-size: 16px; font-weight: bold; color: #2d3748; margin-bottom: 30px;">
                                A partir de este momento, pueden proceder con la <strong>Gestión de Cobranza</strong> correspondiente para la reparación.
                            </p>

                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #fffaf0; border: 1px solid #feebc8; border-left: 5px solid #ed8936; border-radius: 4px;">
                                <tr>
                                    <td style="padding: 20px;">
                                        <h4 style="margin: 0 0 10px 0; color: #9c4221; font-size: 16px;">Acción Requerida:</h4>
                                        <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #7b341e;">
                                            Una vez obtenido el o los comprobantes de pago, favor cargarlos en el <strong>Gestor de Cotizaciones</strong>. Este paso es fundamental para autorizar la <strong>entrega de los equipos reparados</strong> al cliente.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 0 40px 40px 40px;">
                            <p style="font-size: 15px; margin-bottom: 5px; color: #718096;">Atentamente,</p>
                            <p style="font-size: 16px; font-weight: bold; color: #003366; margin: 0;">Equipo de Administración</p>
                            <p style="font-size: 14px; color: #a0aec0; margin-top: 5px;">Aplicación Gestor | MegaNexus</p>
                        </td>
                    </tr>

                    <tr>
                        <td align="center" style="padding: 15px; background-color: #edf2f7; font-size: 12px; color: #a0aec0;">
                            Este es un mensaje automático generado por el sistema de gestión.
                        </td>
                    </tr>
                </table>

            </td>
        </tr>
    </table>
</body>
</html>
"""
    },
    "repair_quote_sent": {
        "name": "Envío Cotización de Reparación",
        "description": "Se envía al cliente cuando se genera una cotización de reparación de equipos",
        "subject": "Presupuesto de Reparación - Cotización Nro. {nro_cotizacion} - {nombre_cliente}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; width: 95%; max-width: 900px; margin: 0 auto;">
<div style="background: #2c3e50; padding: 20px 24px; border-radius: 8px 8px 0 0;">
  <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Presupuesto de Reparación</h2>
</div>
<div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
  <p>Estimado(a) <strong>{contacto_cliente}</strong>,</p>
  <p>Reciba un cordial saludo de parte de <strong>Mega Soft</strong>.</p>
  <p>Hemos finalizado la evaluación técnica de sus equipos. Adjunto a este correo encontrará el detalle de los costos, repuestos y tiempos estimados para la reparación de sus terminales:</p>

  <table style="border-collapse: collapse; margin: 16px 0; width: 100%;">
    <tr><td style="padding: 10px 12px; border: 1px solid #ddd; background: #f8f9fa; width: 40%;"><strong>Equipos en revisión:</strong></td><td style="padding: 10px 12px; border: 1px solid #ddd;">{modelos_resumen}</td></tr>
    <tr><td style="padding: 10px 12px; border: 1px solid #ddd; background: #f8f9fa;"><strong>Nro. de Control:</strong></td><td style="padding: 10px 12px; border: 1px solid #ddd;">{nro_cotizacion}</td></tr>
  </table>

  <p>Para proceder con el servicio, agradecemos su revisión y aprobación formal a través de nuestra plataforma.</p>

  <div style="text-align: center; margin: 24px 0;">
    <a href="#" style="display: inline-block; background: #f39c12; color: #ffffff; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 15px;">Ver y Aprobar Cotización</a>
  </div>

  <p>Quedamos atentos a cualquier duda técnica que pueda surgir. Puede escribirnos al correo <a href="mailto:{Email_Ejecutivo}" style="color: #2c3e50;">{Email_Ejecutivo}</a> de <strong>{Nombre_Ejecutivo}</strong>.</p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">Mega Soft — Servicio Técnico de Terminales de Pago</p>
</div>
</body>
</html>
"""
    },
    "repair_approved": {
        "name": "Aprobación Cotización de Reparación",
        "description": "Confirmación automática que recibe el cliente al aprobar una cotización de reparación",
        "subject": "Confirmación de Aprobación - Cotización Nro. {nro_cotizacion}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; width: 95%; max-width: 900px; margin: 0 auto;">
<div style="background: #2c3e50; padding: 20px 24px; border-radius: 8px 8px 0 0;">
  <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Aprobación Confirmada</h2>
</div>
<div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
  <p>Hola, <strong>{contacto_cliente}</strong>.</p>
  <p>Confirmamos que hemos recibido la aprobación de la cotización <strong>{nro_cotizacion}</strong>.</p>

  <div style="background: #eafaf1; border-left: 4px solid #27ae60; padding: 14px 16px; border-radius: 4px; margin: 16px 0;">
    <p style="margin: 0 0 8px; font-weight: bold; color: #27ae60;">¿Qué sigue ahora?</p>
    <p style="margin: 0; font-size: 14px;">Sus equipos han sido ingresados formalmente a nuestro taller técnico para iniciar el proceso de reparación. Le notificaremos de forma automática en cuanto los equipos estén listos para ser retirados o despachados.</p>
  </div>

  <p>Puede consultar el estatus de su solicitud en cualquier momento comunicándose con su ejecutivo.</p>
  <p>Gracias por confiar en el soporte técnico de <strong>Mega Soft</strong>.</p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">Mega Soft — Servicio Técnico de Terminales de Pago</p>
</div>
</body>
</html>
"""
    },
    "repair_complete_client": {
        "name": "Notificación de Reparación Finalizada",
        "description": "Se envía al cliente cuando el técnico marca la reparación como completada",
        "subject": "Sus equipos ya han sido reparados - {nro_cotizacion}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; width: 95%; max-width: 900px; margin: 0 auto;">
<div style="background: #2c3e50; padding: 20px 24px; border-radius: 8px 8px 0 0;">
  <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Reparación Finalizada</h2>
</div>
<div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
  <p>Estimado(a) <strong>{contacto_cliente}</strong>,</p>
  <p>Nos complace informarle que el proceso técnico de reparación para sus equipos bajo la cotización <strong>{nro_cotizacion}</strong> ha finalizado exitosamente.</p>

  <div style="background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin: 16px 0;">
    <p style="margin: 0 0 8px; font-weight: bold; color: #2c3e50;">Detalle de equipos listos:</p>
    <div style="font-size: 14px;">{lista_modelos_seriales}</div>
  </div>

  <p>Actualmente, su solicitud ha pasado al departamento de <strong>Administración</strong> para la emisión de la Factura / Proforma correspondiente. Una vez gestionado el pago, procederemos con la entrega física de los activos.</p>

  <p>Gracias por su paciencia y confianza en <strong>Mega Soft</strong>.</p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">Mega Soft — Servicio Técnico de Terminales de Pago</p>
</div>
</body>
</html>
"""
    },
    "repair_delivery": {
        "name": "Orden de Entrega de Equipos Reparados",
        "description": "Se envía al cliente cuando se genera la Nota de Entrega de equipos reparados",
        "subject": "Entrega de Equipos Reparados - Nota de Entrega Nro. {nro_nota_entrega}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; width: 95%; max-width: 900px; margin: 0 auto;">
<div style="background: #2c3e50; padding: 20px 24px; border-radius: 8px 8px 0 0;">
  <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Entrega de Equipos Reparados</h2>
</div>
<div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
  <p>Estimado(a) <strong>{contacto_cliente}</strong>,</p>
  <p>Se ha generado una nueva <strong>{tipo_nota_entrega}</strong> relacionada con sus equipos en servicio técnico.</p>

  <table style="border-collapse: collapse; margin: 16px 0; width: 100%;">
    <tr><td style="padding: 10px 12px; border: 1px solid #ddd; background: #f8f9fa; width: 45%;"><strong>Nota de Entrega Nro:</strong></td><td style="padding: 10px 12px; border: 1px solid #ddd;">{nro_nota_entrega}</td></tr>
    <tr><td style="padding: 10px 12px; border: 1px solid #ddd; background: #f8f9fa;"><strong>Equipos entregados:</strong></td><td style="padding: 10px 12px; border: 1px solid #ddd;">{cantidad_entregada} unidades</td></tr>
    <tr><td style="padding: 10px 12px; border: 1px solid #ddd; background: #f8f9fa;"><strong>Estatus del Proyecto:</strong></td><td style="padding: 10px 12px; border: 1px solid #ddd;">{estatus_entrega}</td></tr>
  </table>

  <p>Adjunto encontrará el documento PDF con el detalle de los seriales entregados para su control de inventario.</p>

  <div style="text-align: center; margin: 24px 0;">
    <a href="#" style="display: inline-block; background: #f39c12; color: #ffffff; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 15px;">Descargar Nota de Entrega</a>
  </div>

  <p>Favor confirmar la recepción de los equipos a la brevedad posible.</p>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">Mega Soft — Servicio Técnico de Terminales de Pago</p>
</div>
</body>
</html>
"""
    },
    "repair_collect_warehouse": {
        "name": "Pago de Reparación Recibido (Orden de Despacho)",
        "description": "Se envía al Almacén cuando se confirma el pago de una reparación para autorizar la salida de equipos en custodia",
        "subject": "ORDEN DE DESPACHO: Pago Confirmado - Cotización #{nro_cotizacion} - {nombre_cliente}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; width: 95%; max-width: 900px; margin: 0 auto;">
<div style="background: #2c3e50; padding: 20px 24px; border-radius: 8px 8px 0 0;">
  <h2 style="color: #ffffff; margin: 0; font-size: 20px;">Orden de Despacho — Equipos Reparados</h2>
</div>
<div style="padding: 24px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
  <p>Hola Equipo de Almacén,</p>
  <p>El departamento de <strong>Administración</strong> ha confirmado la recepción del pago correspondiente a la reparación de equipos del cliente: <strong>{nombre_cliente}</strong>.</p>
  <p>Por lo tanto, se autoriza la <strong>salida inmediata</strong> de los activos bajo custodia.</p>

  <div style="background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin: 16px 0;">
    <p style="margin: 0 0 10px; font-weight: bold; color: #2c3e50;">Detalles para el Despacho:</p>
    <table style="border-collapse: collapse; width: 100%;">
      <tr><td style="padding: 8px 12px; border: 1px solid #ddd; background: #f0f0f0; width: 40%;"><strong>Nro. de Cotización:</strong></td><td style="padding: 8px 12px; border: 1px solid #ddd;">{nro_cotizacion}</td></tr>
      <tr><td style="padding: 8px 12px; border: 1px solid #ddd; background: #f0f0f0;"><strong>Ubicación de Origen:</strong></td><td style="padding: 8px 12px; border: 1px solid #ddd;">{almacen_custodia}</td></tr>
    </table>
  </div>

  <div style="background: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin: 16px 0;">
    <p style="margin: 0 0 8px; font-weight: bold; color: #2c3e50;">Equipos a Entregar:</p>
    <div style="font-size: 14px;">{lista_equipos_seriales}</div>
  </div>

  <div style="background: #fff8e1; border-left: 4px solid #f39c12; padding: 14px 16px; border-radius: 4px; margin: 16px 0;">
    <p style="margin: 0 0 8px; font-weight: bold; color: #e67e22;">Instrucciones Operativas:</p>
    <ol style="margin: 0; padding-left: 20px; font-size: 14px; color: #555;">
      <li style="margin-bottom: 6px;">Localizar los equipos físicamente en el área de <strong>"Equipos Reparados"</strong>.</li>
      <li style="margin-bottom: 6px;">Ingresar a la Cotización en MegaNexus y ejecutar la acción <strong>"Marcar como Entregada"</strong>.</li>
      <li style="margin-bottom: 6px;">Generar la <strong>Nota de Entrega</strong> (asegurarse de que el sistema indique si es Parcial o Final según la cantidad entregada).</li>
      <li>Adjuntar la Nota de Entrega al paquete antes de la salida.</li>
    </ol>
  </div>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 12px; color: #999;">Mega Soft — Servicio Técnico de Terminales de Pago</p>
</div>
</body>
</html>
"""
    }
}

# Plantillas globales de Proyecto (no se dividen por sede)
PROJECT_EMAIL_TEMPLATES = {
    "new_integration_project": {
        "template_id": "new_integration_project",
        "name": "Nuevo Proyecto de Integracion",
        "description": "Se envia al Gerente de Implementacion al crear un nuevo proyecto de integracion",
        "subject": "Nuevo Proyecto de Integracion — {nombre_integrador} ({tipo_integracion})",
        "body_html": """<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;">
<h2 style="color:#2c3e50;">Nuevo Proyecto de Integracion</h2>
<p>Se ha registrado un nuevo proyecto en la plataforma. A continuacion, los detalles tecnicos para su gestion:</p>

<h3 style="color:#34495e;margin-top:20px;">Datos del Proyecto</h3>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;width:100%;">
<tr style="background:#f8f9fa;"><td style="padding:8px 12px;color:#666;border:1px solid #eee;width:220px;">Integrador:</td><td style="padding:8px 12px;font-weight:600;border:1px solid #eee;">{nombre_integrador}</td></tr>
<tr><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Tipo de Integracion:</td><td style="padding:8px 12px;border:1px solid #eee;">{tipo_integracion}</td></tr>
<tr style="background:#f8f9fa;"><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Nombre Aplicativo:</td><td style="padding:8px 12px;border:1px solid #eee;">{nombre_aplicativo}</td></tr>
<tr><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Productos a Certificar:</td><td style="padding:8px 12px;border:1px solid #eee;">{Productos_Certificar_Integrador}</td></tr>
<tr style="background:#f8f9fa;"><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Nombre Responsable Tecnico:</td><td style="padding:8px 12px;border:1px solid #eee;">{nombre_responsable}</td></tr>
<tr><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Email Responsable Tecnico:</td><td style="padding:8px 12px;border:1px solid #eee;">{email_responsable}</td></tr>
<tr style="background:#f8f9fa;"><td style="padding:8px 12px;color:#666;border:1px solid #eee;">Telefono Responsable Tecnico:</td><td style="padding:8px 12px;border:1px solid #eee;">{telefono_responsable}</td></tr>
</table>

{comentarios_personalizados}

<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#666;font-size:12px;">Generado por: <strong>{usuario_creador}</strong></p>
<p style="color:#666;font-size:12px;">Fecha de Creacion: {fecha_sistema}</p>
<p style="color:#999;font-size:11px;">Correo automatico de MegaNexus Gestor.</p></div>""",
        "is_active": True,
        "is_project_template": True,
    },
    "project_notify_client": {
        "template_id": "project_notify_client",
        "name": "Notificación de Proyecto — Cliente",
        "description": "Comunicaciones secuenciales al cliente durante implementación",
        "subject": "Implementación Proyecto {project_number} — {Nombre_Cliente}",
        "body_html": """<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;">
<h2 style="color:#2c3e50;">{notification_subject}</h2>
<p><strong>Ticket:</strong> {ticket_number}</p>
<p>Estimado/a <strong>{Contacto_Principal}</strong>,</p>
<p>Le informamos sobre el estado de su proyecto de implementación <strong>{project_number}</strong>.</p>
<p><strong>Nivel:</strong> {notification_level}</p>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;">
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cliente:</td><td style="padding:4px 0;font-weight:600;">{Nombre_Cliente}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cotización:</td><td style="padding:4px 0;">{quote_number}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Integrador:</td><td style="padding:4px 0;">{Integrador}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Sucursal:</td><td style="padding:4px 0;">{Nombre_Sucursal}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cajas:</td><td style="padding:4px 0;">{Cantidad_Cajas}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Implementador:</td><td style="padding:4px 0;">{Nombre_Implementador}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Contacto Impl.:</td><td style="padding:4px 0;">{Correo_Implementador} | {Telefono_Implementador}</td></tr>
</table>
<h3 style="color:#2c3e50;margin-top:20px;">Bancos y Productos</h3>
{Matriz_Bancos_Productos}
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#999;font-size:12px;">Correo automático de MegaNexus Gestor.</p></div>""",
        "is_active": True,
        "is_project_template": True,
    },
    "project_notify_bank": {
        "template_id": "project_notify_bank",
        "name": "Notificación de Proyecto — Banco",
        "description": "Comunicaciones secuenciales a bancos durante implementación",
        "subject": "Implementación {bank_name} — Proyecto {project_number}",
        "body_html": """<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;">
<h2 style="color:#2c3e50;">{notification_subject} — {bank_name}</h2>
<p><strong>Ticket:</strong> {ticket_number}</p>
<p>Estimados contactos de <strong>{bank_name}</strong>,</p>
<p>Proyecto <strong>{project_number}</strong> para <strong>{Nombre_Cliente}</strong>.</p>
<p><strong>Nivel:</strong> {notification_level}</p>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;">
<tr><td style="padding:4px 12px 4px 0;color:#666;">Contacto Principal:</td><td style="padding:4px 0;">{Contacto_Principal}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Integrador:</td><td style="padding:4px 0;">{Integrador}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Aplicativo:</td><td style="padding:4px 0;">{Aplicativo_Integracion}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Sucursal:</td><td style="padding:4px 0;">{Nombre_Sucursal}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cajas:</td><td style="padding:4px 0;">{Cantidad_Cajas}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Implementador:</td><td style="padding:4px 0;">{Nombre_Implementador}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Contacto Impl.:</td><td style="padding:4px 0;">{Correo_Implementador} | {Telefono_Implementador}</td></tr>
</table>
<h3 style="color:#2c3e50;">Productos</h3>
<p>{bank_products}</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#999;font-size:12px;">Correo automático de MegaNexus Gestor.</p></div>""",
        "is_active": True,
        "is_project_template": True,
    },
    "project_notify_bank_client": {
        "template_id": "project_notify_bank_client",
        "name": "Notificación de Proyecto Banco y Cliente",
        "description": "Notifica simultáneamente al Banco y al Cliente cuando el proyecto tiene un solo banco",
        "subject": "Implementación {bank_name} — {Nombre_Cliente} — Proyecto {project_number}",
        "body_html": """<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;">
<h2 style="color:#2c3e50;">{notification_subject}</h2>
<p style="font-size:14px;color:#555;">Proyecto <strong>{project_number}</strong> | Ticket: <strong>{ticket_number}</strong></p>
<hr style="border:none;border-top:2px solid #3498db;margin:16px 0;">

<h3 style="color:#2c3e50;margin-top:20px;">Datos del Cliente</h3>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;width:100%;">
<tr><td style="padding:6px 12px 6px 0;color:#666;width:180px;">Razón Social:</td><td style="padding:6px 0;font-weight:bold;">{Nombre_Cliente}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">RIF:</td><td style="padding:6px 0;">{client_rif}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Contacto Principal:</td><td style="padding:6px 0;">{Contacto_Principal}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Sucursal(es):</td><td style="padding:6px 0;">{Nombre_Sucursal}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Cantidad de Cajas:</td><td style="padding:6px 0;font-weight:bold;">{Cantidad_Cajas}</td></tr>
</table>

<h3 style="color:#2c3e50;margin-top:20px;">Datos del Banco</h3>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;width:100%;">
<tr><td style="padding:6px 12px 6px 0;color:#666;width:180px;">Banco:</td><td style="padding:6px 0;font-weight:bold;">{bank_name}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Productos:</td><td style="padding:6px 0;">{bank_products}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Tipo de Cotización:</td><td style="padding:6px 0;">{quote_type}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Modelo Pinpad:</td><td style="padding:6px 0;">{pinpad_model}</td></tr>
</table>

<h3 style="color:#2c3e50;margin-top:20px;">Datos de Implementación</h3>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;width:100%;">
<tr><td style="padding:6px 12px 6px 0;color:#666;width:180px;">Integrador:</td><td style="padding:6px 0;font-weight:bold;">{Integrador}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Aplicativo:</td><td style="padding:6px 0;">{Aplicativo_Integracion}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Implementador:</td><td style="padding:6px 0;">{Nombre_Implementador}</td></tr>
<tr><td style="padding:6px 12px 6px 0;color:#666;">Contacto Implementador:</td><td style="padding:6px 0;">{Correo_Implementador} | {Telefono_Implementador}</td></tr>
</table>

<div style="margin-top:20px;">
<h3 style="color:#2c3e50;">Matriz de Implementación</h3>
{Matriz_Bancos_Productos}
</div>

<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<p style="color:#999;font-size:11px;">Correo automático generado por MegaNexus Gestor. Nivel: {notification_level}</p></div>""",
        "is_active": True,
        "is_project_template": True,
    },
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
async def get_email_templates(context: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Obtiene plantillas de correo, opcionalmente filtradas por contexto (COTIZACIONES|IMPLEMENTACION|ADMINISTRACION)"""
    await get_current_user(authorization)

    query = {}
    if context:
        query["context"] = context.upper()

    templates = await db.email_templates.find(query, {"_id": 0}).to_list(200)

    # Lápidas: plantillas por defecto que el usuario eliminó (no reaparecen).
    tombstoned = {
        d["template_id"]
        async for d in db.deleted_default_templates.find({}, {"_id": 0, "template_id": 1})
    }

    # Para el módulo de Implementación (Plantillas de Proyectos), incluir las
    # plantillas de Proyecto por defecto (Texto Enriquecido) que aún no estén
    # persistidas, para que el dropdown del modal de notificaciones las liste.
    if context and context.upper() == "IMPLEMENTACION":
        existing_ids = {t["template_id"] for t in templates}
        for template_id, default_template in PROJECT_EMAIL_TEMPLATES.items():
            if template_id not in existing_ids and template_id not in tombstoned:
                templates.append(default_template)

    # Si no hay filtro de contexto, incluir plantillas predeterminadas que falten
    if not context:
        template_ids = [t["template_id"] for t in templates]
        for template_id, default_template in EMAIL_TEMPLATES_BY_SEDE.items():
            if template_id not in template_ids and template_id not in tombstoned:
                templates.append(default_template)
        for template_id, default_template in PROJECT_EMAIL_TEMPLATES.items():
            if template_id not in template_ids and template_id not in tombstoned:
                templates.append(default_template)
        for template_id, default_template in DEFAULT_EMAIL_TEMPLATES.items():
            if template_id not in template_ids and template_id not in tombstoned:
                sede_version_exists = any(t["template_id"].startswith(template_id + "_") for t in templates)
                if not sede_version_exists:
                    templates.append(default_template)

    return templates

SIGNATURE_TOKEN = "{Firma_Notificacion_Global}"


def _inject_signature_block(body_html: str) -> str:
    """Inserta el bloque de firma global al pie del cuerpo HTML.
    Lo coloca antes de </body> (o </html>) si existen; si no, lo agrega al final."""
    block = f'\n<p style="margin-top:16px;">{SIGNATURE_TOKEN}</p>\n'
    body = body_html or ""
    low = body.lower()
    for tag in ("</body>", "</html>"):
        idx = low.rfind(tag)
        if idx != -1:
            return body[:idx] + block + body[idx:]
    return body + block


@router.post("/email-templates/append-signature")
async def append_signature_to_all_templates(authorization: Optional[str] = Header(None)):
    """Homologa la plataforma: agrega la variable {Firma_Notificacion_Global} al pie
    de TODAS las plantillas de correo (persistidas + predeterminadas que falten) que
    aún no la incluyan. Idempotente: las que ya la tienen se omiten. Solo admin."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden homologar las plantillas")

    # Reunir el universo completo de plantillas (misma lógica que GET /email-templates sin contexto)
    templates = await db.email_templates.find({}, {"_id": 0}).to_list(500)
    tombstoned = {
        d["template_id"]
        async for d in db.deleted_default_templates.find({}, {"_id": 0, "template_id": 1})
    }
    template_ids = {t["template_id"] for t in templates}
    for source in (EMAIL_TEMPLATES_BY_SEDE, PROJECT_EMAIL_TEMPLATES, DEFAULT_EMAIL_TEMPLATES):
        for template_id, default_template in source.items():
            if template_id in template_ids or template_id in tombstoned:
                continue
            if source is DEFAULT_EMAIL_TEMPLATES and any(t["template_id"].startswith(template_id + "_") for t in templates):
                continue
            templates.append(default_template)
            template_ids.add(template_id)

    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    skipped = 0
    for t in templates:
        body = t.get("body_html") or ""
        if SIGNATURE_TOKEN in body:
            skipped += 1
            continue
        new_body = _inject_signature_block(body)
        data = {k: v for k, v in t.items() if k != "_id"}
        data["body_html"] = new_body
        data["updated_at"] = now
        await db.email_templates.update_one(
            {"template_id": t["template_id"]},
            {"$set": data},
            upsert=True,
        )
        updated += 1

    return {
        "updated": updated,
        "skipped": skipped,
        "total": len(templates),
        "message": f"Firma agregada a {updated} plantilla(s). {skipped} ya la tenían.",
    }



@router.get("/email-templates/{template_id}")
async def get_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene una plantilla de correo específica"""
    await get_current_user(authorization)
    
    template = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    
    if not template:
        # Buscar primero en plantillas de proyecto
        if template_id in PROJECT_EMAIL_TEMPLATES:
            return PROJECT_EMAIL_TEMPLATES[template_id]
        # Luego en plantillas por sede
        if template_id in EMAIL_TEMPLATES_BY_SEDE:
            return EMAIL_TEMPLATES_BY_SEDE[template_id]
        # Luego en plantillas legacy
        if template_id in DEFAULT_EMAIL_TEMPLATES:
            return DEFAULT_EMAIL_TEMPLATES[template_id]
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    
    return template

@router.post("/email-templates")
async def create_email_template(template: EmailTemplate, authorization: Optional[str] = Header(None)):
    """Crea una nueva plantilla de correo"""
    await get_current_user(authorization)
    
    existing = await db.email_templates.find_one({"template_id": template.template_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una plantilla con ese ID")
    
    template_data = template.model_dump()
    template_data["created_at"] = datetime.now(timezone.utc).isoformat()
    template_data["updated_at"] = template_data["created_at"]
    template_data["is_custom"] = True  # Marcar siempre las creadas vía POST como personalizadas

    await db.email_templates.insert_one(template_data)
    # Si era una plantilla por defecto previamente eliminada, quitar la lápida.
    await db.deleted_default_templates.delete_one({"template_id": template.template_id})
    
    return {"message": "Plantilla creada exitosamente", "template_id": template.template_id}

@router.put("/email-templates/{template_id}")
async def update_email_template(template_id: str, template: EmailTemplate, authorization: Optional[str] = Header(None)):
    """Actualiza o crea una plantilla de correo"""
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
    await db.deleted_default_templates.delete_one({"template_id": template_id})
    
    return {"message": "Plantilla actualizada exitosamente", "template_id": template_id}

@router.post("/email-templates/reset/{template_id}")
async def reset_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Restablece una plantilla a su valor predeterminado"""
    await get_current_user(authorization)
    
    # Buscar primero en plantillas por sede, luego en Proyecto (Implementación), luego legacy
    default_template = None
    if template_id in EMAIL_TEMPLATES_BY_SEDE:
        default_template = EMAIL_TEMPLATES_BY_SEDE[template_id].copy()
    elif template_id in PROJECT_EMAIL_TEMPLATES:
        default_template = PROJECT_EMAIL_TEMPLATES[template_id].copy()
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
    await db.deleted_default_templates.delete_one({"template_id": template_id})
    
    return {"message": "Plantilla restablecida a valores predeterminados", "template": default_template}


@router.delete("/email-templates/{template_id}")
async def delete_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Elimina una plantilla de correo.

    Las plantillas predeterminadas (semilla) no existen en la BD: se listan desde
    el código. Para poder 'eliminarlas' se registra una lápida (tombstone) en
    `deleted_default_templates` para que `get_email_templates` deje de incluirlas.
    """
    await get_current_user(authorization)
    result = await db.email_templates.delete_one({"template_id": template_id})
    if result.deleted_count > 0:
        return {"message": "Plantilla eliminada exitosamente", "template_id": template_id}

    # No estaba en BD: ¿es una plantilla por defecto conocida?
    is_default = (
        template_id in PROJECT_EMAIL_TEMPLATES
        or template_id in EMAIL_TEMPLATES_BY_SEDE
        or template_id in DEFAULT_EMAIL_TEMPLATES
    )
    if is_default:
        await db.deleted_default_templates.update_one(
            {"template_id": template_id},
            {"$set": {"template_id": template_id, "deleted_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"message": "Plantilla eliminada exitosamente", "template_id": template_id}

    raise HTTPException(status_code=404, detail="Plantilla no encontrada")


# Función auxiliar para renderizar plantillas con variables


# ==================== SEED: Plantilla Comprobante de Pago ====================
SEED_TEMPLATE_COMPROBANTE = {
    "template_id": "comprobante_pago",
    "name": "Envio de Comprobante de Pago",
    "subject": "Confirmacion de Recepcion de Pago - {Nombre_Cliente} - {Cotizacion_Nro}",
    "body_html": """<div style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#00447C;border-radius:6px 6px 0 0">
<tr><td style="padding:20px 30px;color:#fff;font-size:22px;font-weight:bold">Confirmacion de Recepcion de Pago</td></tr>
</table>
<div style="border:1px solid #E0E0E0;border-top:none;padding:25px 30px;background:#fff">
<p style="font-size:15px;color:#333">Estimado/a <strong>{Nombre_Cliente}</strong>,</p>
<p style="font-size:14px;color:#555">Por medio de la presente, confirmamos la recepcion del comprobante de pago correspondiente a la cotizacion <strong>{Cotizacion_Nro}</strong>.</p>
<table width="100%" cellpadding="8" cellspacing="0" style="border:1px solid #E0E0E0;border-radius:4px;margin:15px 0">
<tr style="background:#E3F2FD"><td style="font-weight:bold;font-size:13px;color:#00447C;width:200px">Cliente</td><td style="font-size:13px">{Nombre_Cliente}</td></tr>
<tr><td style="font-weight:bold;font-size:13px;color:#00447C">RIF</td><td style="font-size:13px">{Rif_Cliente}</td></tr>
<tr style="background:#E3F2FD"><td style="font-weight:bold;font-size:13px;color:#00447C">Cotizacion</td><td style="font-size:13px">{Cotizacion_Nro}</td></tr>
<tr><td style="font-weight:bold;font-size:13px;color:#00447C">Contacto</td><td style="font-size:13px">{Contacto_Principal}</td></tr>
</table>
<p style="font-size:14px;color:#555">Nuestro equipo procedera a validar el pago y actualizar el estatus de su cotizacion. Si tiene alguna consulta, no dude en comunicarse con nosotros.</p>
<p style="font-size:14px;color:#333;margin-top:20px">Atentamente,<br><strong>Equipo de Ventas MegaNexus</strong></p>
</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;border:1px solid #E0E0E0;border-top:none;border-radius:0 0 6px 6px">
<tr><td style="padding:12px 30px;font-size:11px;color:#999;text-align:center">Este correo fue generado automaticamente por el Gestor MegaNexus.</td></tr>
</table>
</div>""",
    "description": "Plantilla para confirmar la recepcion de comprobante de pago al cliente",
    "is_active": True,
    "context": "COTIZACIONES",
}
