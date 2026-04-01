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
    },
    "repair_quote_sent": {
        "name": "Envío Cotización de Reparación",
        "description": "Se envía al cliente cuando se genera una cotización de reparación de equipos",
        "subject": "Presupuesto de Reparación - Cotización Nro. {nro_cotizacion} - {nombre_cliente}",
        "body_html": """
<html>
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
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
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
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
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
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
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
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
<body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
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
    "project_notify_client": {
        "template_id": "project_notify_client",
        "name": "Notificación de Proyecto — Cliente",
        "description": "Comunicaciones secuenciales al cliente durante implementación",
        "subject": "Implementación Proyecto {project_number} — {Nombre_Cliente}",
        "body_html": """<div style="font-family:Arial,sans-serif;max-width:600px;">
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
        "body_html": """<div style="font-family:Arial,sans-serif;max-width:600px;">
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
    """Obtiene todas las plantillas de correo (por sede + plantillas de proyecto globales)"""
    await get_current_user(authorization)
    
    templates = await db.email_templates.find({}, {"_id": 0}).to_list(200)
    
    # Si no hay plantillas, devolver las predeterminadas por sede + proyecto
    if not templates:
        return list(EMAIL_TEMPLATES_BY_SEDE.values()) + list(PROJECT_EMAIL_TEMPLATES.values())
    
    # Asegurar que todas las plantillas por sede existan
    template_ids = [t["template_id"] for t in templates]
    for template_id, default_template in EMAIL_TEMPLATES_BY_SEDE.items():
        if template_id not in template_ids:
            templates.append(default_template)
    
    # Asegurar que plantillas de proyecto existan
    for template_id, default_template in PROJECT_EMAIL_TEMPLATES.items():
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
    
    await db.email_templates.insert_one(template_data)
    
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


