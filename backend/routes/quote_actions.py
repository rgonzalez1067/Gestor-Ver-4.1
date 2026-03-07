"""Route module: quote_actions.py - Acciones del flujo de cotizaciones"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr
import uuid
import logging
import io
import os
import base64

from config import db, get_current_user, UPLOADS_DIR, SENDER_EMAIL, generate_quote_number, render_email_template
from models import *
from services.email_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)


class QuoteStatusUpdate(BaseModel):
    new_status: str

class EmailSendRequest(BaseModel):
    quote_id: str
    recipient_email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None


@router.put("/quotes/{quote_id}/status")
async def update_quote_status(quote_id: str, status_update: QuoteStatusUpdate, authorization: Optional[str] = Header(None)):
    """Actualiza el estatus de una cotización validando transiciones permitidas"""
    await get_current_user(authorization)
    
    if status_update.new_status not in QUOTE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Estados válidos: {QUOTE_STATUSES}")
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    quote_category = quote.get("quote_category", "implementation")
    
    transitions = QUOTE_TRANSITIONS.get(quote_category, QUOTE_TRANSITIONS["implementation"])
    allowed_next_states = transitions.get(current_status, [])
    
    if status_update.new_status not in allowed_next_states:
        raise HTTPException(
            status_code=400,
            detail=f"Transición no permitida: '{current_status}' → '{status_update.new_status}'. Transiciones válidas: {allowed_next_states}"
        )
    
    # Timestamp según el nuevo estado
    timestamp_map = {
        "Enviada": "sent_to_client_at",
        "Aprobada": "approved_at",
        "Facturada": "invoiced_at",
        "Pagada": "paid_at",
        "Entregada": "delivered_at",
        "Enviada a Imple": "sent_to_implementation_at",
    }
    update_fields = {"quote_status": status_update.new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if status_update.new_status in timestamp_map:
        update_fields[timestamp_map[status_update.new_status]] = datetime.now(timezone.utc).isoformat()

    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": update_fields}
    )

    # === TRIGGER: Crear Proyecto al enviar a Implementación ===
    if status_update.new_status == "Enviada a Imple":
        try:
            await _create_project_from_quote(quote, quote_id)
        except Exception as e:
            logger.error(f"Error creando proyecto desde cotización {quote_id}: {e}")
    
    return {"message": f"Estado actualizado a '{status_update.new_status}'", "previous_status": current_status, "new_status": status_update.new_status}


@router.post("/quotes/{quote_id}/approve")
async def approve_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Aprobar una cotización - Requiere anexo de Orden de Compra"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Enviada":
        raise HTTPException(status_code=400, detail=f"Solo se pueden aprobar cotizaciones en estado 'Enviada'. Estado actual: {current_status}")
    
    # Validar Orden de Compra
    attachments = quote.get("attachments", [])
    has_oc = any(a.get("category") == "Orden de Compra" for a in attachments)
    if not has_oc:
        raise HTTPException(status_code=422, detail="Debe cargar la Orden de Compra antes de aprobar la cotización")
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Actualizar estado
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {"quote_status": "Aprobada", "approved_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Preparar email
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "TBP")
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or (config.get("admin_email") if config else None)
    sales_email = sede_emails.get("sales") if sede_emails else None

    template = await db.email_templates.find_one({"template_id": "quote_approved"}, {"_id": 0})
    if not template:
        template = {
            "subject": "Cotización {{quote_number}} Aprobada - Lista para Facturar",
            "body_html": "<h2>Cotización Aprobada</h2><p>La cotización <strong>{{quote_number}}</strong> ha sido aprobada.</p><p><strong>Cliente:</strong> {{client_name}}</p><p><strong>Total USD:</strong> ${{total_usd}}</p>"
        }
    
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "quote_type": quote.get('quote_type', 'N/A'),
        "total_usd": f"{quote.get('total_usd', 0):.2f}"
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    email_results = []
    # Notificar a admin
    if admin_email:
        r = await send_email(to=[admin_email], subject=subject, html=html_content, action="approve_admin", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
    # Notificar a ventas
    if sales_email:
        r = await send_email(to=[sales_email], subject=f"[VENTAS] {subject}", html=html_content, action="approve_sales", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
    # Si no hay destinatarios configurados, log simulado genérico
    if not admin_email and not sales_email:
        r = await send_email(to=["admin@sede.local"], subject=subject, html=html_content, action="approve_no_config", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)

    return {
        "message": "Cotización aprobada exitosamente",
        "quote_id": quote_id,
        "new_status": "Aprobada",
        "emails": email_results
    }


@router.post("/quotes/{quote_id}/send-to-client")
async def send_quote_to_client(quote_id: str, authorization: Optional[str] = Header(None)):
    """Envía la cotización por email al cliente con el PDF adjunto"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Obtener email del contacto (si no tiene, usar simulado)
    contacts = client.get('contacts', [])
    client_email = None
    if contacts:
        client_email = contacts[0].get('email')
    if not client_email:
        client_email = client.get('contact1', {}).get('email')
    if not client_email or client_email == 'sin@email.com':
        client_email = f"cliente_{client.get('rif', 'unknown')}@simulado.local"
    
    # Preparar plantilla
    template = await db.email_templates.find_one({"template_id": "quote_sent"}, {"_id": 0})
    if not template:
        template = {
            "subject": "Cotización {{quote_number}} - {{company_name}}",
            "body_html": "<h2>Estimado {{client_name}}</h2><p>Adjunto encontrará la cotización <strong>{{quote_number}}</strong>.</p><p>Total: ${{total_usd}} USD</p>"
        }
    
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "client_rif": client.get('rif', 'N/A'),
        "quote_type": quote.get('quote_type', 'N/A'),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "company_name": "Merchant Server"
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    # Preparar attachment PDF si existe
    pdf_attachments = None
    pdf_url = quote.get("quote_pdf_url")
    if pdf_url:
        pdf_path = UPLOADS_DIR / pdf_url.replace("/uploads/", "")
        if pdf_path.exists():
            with open(pdf_path, 'rb') as f:
                pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
            pdf_attachments = [{"filename": f"cotizacion_{quote.get('quote_number', 'quote')}.pdf", "content": pdf_base64}]

    # Enviar (real o simulado)
    email_result = await send_email(
        to=[client_email], subject=subject, html=html_content,
        action="send_to_client", quote_id=quote_id, quote_number=quote.get('quote_number'),
        attachments=pdf_attachments
    )
    
    # Actualizar estado
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {"sent_to_client_at": datetime.now(timezone.utc).isoformat(), "quote_status": "Enviada"}}
    )
    
    return {
        "message": f"Cotización enviada a {client_email}",
        "recipient": client_email,
        "new_status": "Enviada",
        **email_result
    }


@router.post("/quotes/{quote_id}/send-to-implementation")
async def send_quote_to_implementation(quote_id: str, authorization: Optional[str] = Header(None)):
    """Envía la cotización al equipo de implementación"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Pagada":
        raise HTTPException(status_code=400, detail=f"Solo se pueden enviar a implementación cotizaciones en estado 'Pagada'. Estado actual: {current_status}")
    
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Obtener email de implementación
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    implementation_email = config.get('implementation_email') if config else None
    if not implementation_email:
        implementation_email = "implementacion@simulado.local"
    
    # Preparar template
    services = quote.get('services', [])
    services_html = "<table style='border-collapse:collapse;width:100%'><thead><tr style='background:#f3f4f6'><th style='padding:8px;border:1px solid #ddd;text-align:left'>Servicio</th><th style='padding:8px;border:1px solid #ddd;text-align:center'>Categoría</th></tr></thead><tbody>"
    for svc in services:
        services_html += f"<tr><td style='padding:8px;border:1px solid #ddd'>{svc.get('name','N/A')}</td><td style='padding:8px;border:1px solid #ddd;text-align:center'>{svc.get('category','N/A')}</td></tr>"
    services_html += "</tbody></table>"
    
    template = await db.email_templates.find_one({"template_id": "implementation"}, {"_id": 0})
    if not template:
        template = {
            "subject": "Nueva Implementación: {{quote_number}} - {{client_name}}",
            "body_html": "<h2>Nueva implementación asignada</h2><p><strong>Cotización:</strong> {{quote_number}}</p><p><strong>Cliente:</strong> {{client_name}} ({{client_rif}})</p><p><strong>Integrador:</strong> {{integrator_name}}</p>{{services_table}}"
        }
    
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "client_rif": client.get('rif', 'N/A') if client else 'N/A',
        "quote_type": quote.get('quote_type', 'N/A'),
        "integrator_name": f"{quote.get('integrator_name', 'N/A')} ({quote.get('integrator_app_name', '')})",
        "pinpad_model": quote.get('pinpad_model', 'N/A'),
        "services_table": services_html
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    # Preparar PDF attachment
    pdf_attachments = None
    pdf_url = quote.get("quote_pdf_url")
    if pdf_url:
        pdf_path = UPLOADS_DIR / pdf_url.replace("/uploads/", "")
        if pdf_path.exists():
            with open(pdf_path, 'rb') as f:
                pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
            pdf_attachments = [{"filename": f"implementacion_{quote.get('quote_number', 'quote')}.pdf", "content": pdf_base64}]

    email_result = await send_email(
        to=[implementation_email], subject=subject, html=html_content,
        action="send_to_implementation", quote_id=quote_id, quote_number=quote.get('quote_number'),
        attachments=pdf_attachments
    )
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {"sent_to_implementation_at": datetime.now(timezone.utc).isoformat(), "quote_status": "Enviada a Imple"}}
    )

    # TRIGGER: Crear Proyecto y eliminar cotización
    try:
        # Re-leer la cotización antes de eliminarla para tener todos los datos
        quote_for_project = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if quote_for_project:
            await _create_project_from_quote(quote_for_project, quote_id)
    except Exception as e:
        logger.error(f"Error creando proyecto desde cotización {quote_id}: {e}")

    return {"message": f"Enviado a implementación: {implementation_email}", "new_status": "Enviada a Imple", **email_result}


# ==================== FLUJO DE FACTURACIÓN Y COBRO ====================

@router.post("/quotes/{quote_id}/invoice")
async def invoice_quote(quote_id: str, invoice_number: str = Form(None), authorization: Optional[str] = Header(None)):
    """Facturar cotización - Requiere anexo de 'Factura'"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    if quote.get("quote_status") != "Aprobada":
        raise HTTPException(status_code=400, detail="Solo se pueden facturar cotizaciones en estado 'Aprobada'")
    
    attachments = quote.get("attachments", [])
    factura_attachments = [a for a in attachments if a.get("category") == "Factura"]
    if not factura_attachments:
        raise HTTPException(status_code=422, detail="Debe cargar el documento de Factura antes de facturar la cotización")
    
    invoice_url = factura_attachments[-1].get("url", "")
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "quote_status": "Facturada",
        "invoiced_at": datetime.now(timezone.utc).isoformat(),
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }})
    
    # Enviar notificación
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "TBP")
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or (config.get("admin_email") if config else None)
    sales_email = sede_emails.get("sales") if sede_emails else None

    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    template = await db.email_templates.find_one({"template_id": "invoice"}, {"_id": 0})
    if not template:
        template = {
            "subject": "Cotización {{quote_number}} Facturada",
            "body_html": "<h2>Cotización Facturada</h2><p>La cotización <strong>{{quote_number}}</strong> ha sido facturada.</p><p><strong>Cliente:</strong> {{client_name}}</p><p><strong>Factura:</strong> {{invoice_number}}</p><p><strong>Total USD:</strong> ${{total_usd}}</p>"
        }
    
    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "client_name": client_name,
        "client_rif": client.get('rif', 'N/A') if client else 'N/A',
        "invoice_number": invoice_number or 'No especificado',
        "total_usd": f"{quote.get('total_usd', 0):.2f}"
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    email_results = []
    recipients = [(admin_email, "invoice_admin"), (sales_email, "invoice_sales")]
    if not admin_email and not sales_email:
        recipients = [("admin@sede.local", "invoice_no_config")]
    
    for email, action in recipients:
        if email:
            prefix = "[VENTAS] " if "sales" in action else ""
            r = await send_email(to=[email], subject=f"{prefix}{subject}", html=html_content, action=action, quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)

    return {"message": "Cotización facturada exitosamente", "invoice_pdf_url": invoice_url, "invoice_number": invoice_number, "emails": email_results}


@router.post("/quotes/{quote_id}/collect")
async def collect_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Marcar cotización como Pagada - Requiere anexos en categoría 'Pagos'"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    if quote.get("quote_status") != "Facturada":
        raise HTTPException(status_code=400, detail="Solo se pueden cobrar cotizaciones en estado 'Facturada'")
    
    attachments = quote.get("attachments", [])
    payment_proofs = [a for a in attachments if a.get("category") == "Pagos"]
    if not payment_proofs:
        raise HTTPException(status_code=422, detail="Debe cargar al menos un comprobante de pago antes de registrar el cobro")
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "quote_status": "Pagada",
        "paid_at": datetime.now(timezone.utc).isoformat()
    }})
    
    email_results = []
    quote_category = quote.get("quote_category", "implementation")
    
    if quote_category == "equipment":
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        quote_sede = quote.get("sede", "TBP")
        emails_by_sede = config.get("emails_by_sede", {}) if config else {}
        sede_emails = emails_by_sede.get(quote_sede, {})
        warehouse_email = sede_emails.get("warehouse") or (config.get("warehouse_email") if config else None)
        if not warehouse_email:
            warehouse_email = "almacen@simulado.local"
        
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        
        equipment_items = quote.get('equipment_items', [])
        items_html = "<table style='border-collapse:collapse;width:100%;max-width:400px'><thead><tr style='background:#f3f4f6'><th style='padding:8px;border:1px solid #ddd;text-align:left'>Producto</th><th style='padding:8px;border:1px solid #ddd;text-align:center'>Cantidad</th></tr></thead><tbody>"
        for item in equipment_items:
            items_html += f"<tr><td style='padding:8px;border:1px solid #ddd'>{item.get('name','N/A')}</td><td style='padding:8px;border:1px solid #ddd;text-align:center'>{item.get('quantity',1)}</td></tr>"
        items_html += "</tbody></table>"
        
        template = await db.email_templates.find_one({"template_id": "warehouse"}, {"_id": 0})
        if not template:
            template = {
                "subject": "Despacho Pendiente: {{quote_number}} - {{client_name}}",
                "body_html": "<h2>Nuevo despacho pendiente</h2><p><strong>Cotización:</strong> {{quote_number}}</p><p><strong>Cliente:</strong> {{client_name}} ({{client_rif}})</p><p><strong>Dirección:</strong> {{client_address}}</p>{{items_table}}"
            }
        
        template_vars = {
            "quote_number": quote.get('quote_number', ''),
            "client_name": client_name,
            "client_rif": client.get('rif', 'N/A') if client else 'N/A',
            "client_address": client.get('address', 'N/A') if client else 'N/A',
            "items_table": items_html
        }
        subject = render_email_template(template["subject"], template_vars)
        html_content = render_email_template(template["body_html"], template_vars)
        
        r = await send_email(to=[warehouse_email], subject=subject, html=html_content, action="collect_warehouse", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
    
    return {"message": "Cotización marcada como Pagada", "emails": email_results}


@router.post("/quotes/{quote_id}/deliver")
async def deliver_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Marcar cotización de equipos como Entregada"""
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    if quote.get("quote_category") != "equipment":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de equipos")
    
    if quote.get("quote_status") != "Pagada":
        raise HTTPException(status_code=400, detail="Solo se pueden entregar cotizaciones en estado 'Pagada'")
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "quote_status": "Entregada",
        "delivered_at": datetime.now(timezone.utc).isoformat()
    }})
    
    return {"message": "Cotización marcada como Entregada"}


@router.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Crea una nueva versión de la cotización (Modificar)"""
    await get_current_user(authorization)
    
    original_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not original_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    quote_sede = original_quote.get("sede", "TBP")
    new_quote_number = await generate_quote_number(quote_sede)
    
    original_version = original_quote.get("version", 1)
    parent_id = original_quote.get("parent_quote_id") or quote_id
    
    new_quote = {
        **original_quote,
        "quote_id": f"quo_{uuid.uuid4().hex[:12]}",
        "quote_number": new_quote_number,
        "quote_status": "Borrador",
        "version": original_version + 1,
        "parent_quote_id": parent_id,
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


# ==================== EMAIL LOG ====================

@router.get("/email-logs")
async def get_email_logs(limit: int = 50, authorization: Optional[str] = Header(None)):
    """Retorna el historial de correos enviados/simulados"""
    await get_current_user(authorization)
    logs = await db.email_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"email_logs": logs, "count": len(logs)}


# ==================== PROJECT TRIGGER ====================

async def _create_project_from_quote(quote: dict, quote_id: str):
    """Crea un proyecto a partir de una cotización enviada a implementación"""
    existing = await db.projects.find_one({"quote_id": quote_id})
    if existing:
        logger.info(f"Proyecto ya existe para cotización {quote_id}")
        return

    # Obtener datos del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = client.get("legal_name", "") if client else quote.get("client_name", "")
    client_rif = client.get("rif", "") if client else ""
    client_sede = client.get("sucursal", "Principal") if client else "Principal"

    # Código de sede para nomenclatura
    sede_code = client_sede[:3].upper() if client_sede else "PRI"
    now = datetime.now(timezone.utc)
    year = now.strftime('%Y')
    month = now.strftime('%m')

    # Consecutivo mensual
    month_prefix = f"PRY-{year}-{month}-"
    last_project = await db.projects.find_one(
        {"project_number": {"$regex": f"^{month_prefix}"}},
        sort=[("project_number", -1)]
    )
    if last_project:
        try:
            last_num = int(last_project["project_number"].split("-")[3])
            next_num = last_num + 1
        except (IndexError, ValueError):
            next_num = 1
    else:
        next_num = 1

    project_number = f"PRY-{year}-{month}-{str(next_num).zfill(3)}-{sede_code}"

    # Extraer bancos de la cotización
    banks = []
    for item in quote.get("services", []):
        bn = item.get("bank_name")
        if bn and bn not in [b.get("bank_name") for b in banks]:
            banks.append({"bank_name": bn})
    if quote.get("sponsor_bank_name"):
        if quote["sponsor_bank_name"] not in [b.get("bank_name") for b in banks]:
            banks.append({"bank_name": quote["sponsor_bank_name"]})

    # Construir matriz de implementación desde los items 'additional'
    # Los items 'additional' son los medios de pago que el usuario seleccionó
    # explícitamente para cada banco (ej: "TDD/TDC Suscripción" para "Banco Mercantil").
    # NO usar recurring_basic/recurring_other ya que incluyen tarifas base y costos
    # de infraestructura que NO representan implementaciones por banco.
    implementation_matrix = {}
    for item in quote.get("services", []):
        if item.get("item_type") != "additional":
            continue
        bn = item.get("bank_name", "")
        name = item.get("item_name", "")
        if not bn or not name:
            continue
        if bn not in implementation_matrix:
            implementation_matrix[bn] = {}
        if name not in implementation_matrix[bn]:
            implementation_matrix[bn][name] = {}

    # Heredar anexos de la cotización
    attachments = []
    for att in quote.get("attachments", []):
        attachments.append({
            "attachment_id": att.get("attachment_id", f"att_{uuid.uuid4().hex[:12]}"),
            "filename": att.get("filename", ""),
            "url": att.get("url", ""),
            "category": att.get("category", "Cotización"),
            "uploaded_by": att.get("uploaded_by", "system"),
            "uploaded_by_name": att.get("uploaded_by_name", "Sistema"),
            "uploaded_at": att.get("uploaded_at", now.isoformat()),
            "inherited_from": "cotización",
        })

    project = {
        "project_id": f"prj_{uuid.uuid4().hex[:12]}",
        "project_number": project_number,
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "quote_pdf_url": quote.get("quote_pdf_url"),
        "client_id": quote.get("client_id", ""),
        "client_name": client_name,
        "client_rif": client_rif,
        "client_sede": client_sede,
        "quote_category": quote.get("quote_category", "implementation"),
        "quote_type": quote.get("quote_type", "VPOS"),
        "services": quote.get("services", []),
        "hardware": quote.get("hardware", []),
        "equipment_items": quote.get("equipment_items", []),
        "pg_setup_items": quote.get("pg_setup_items", []),
        "banks": banks,
        "integrator_name": quote.get("integrator_name"),
        "integrator_app_name": quote.get("integrator_app_name"),
        "pinpad_model": quote.get("pinpad_model"),
        "sponsor_bank_name": quote.get("sponsor_bank_name"),
        "total_usd": quote.get("total_usd", 0),
        "total_bs": quote.get("total_bs", 0),
        "status": "Pendiente por Asignar",
        "priority": "Normal",
        "implementation_matrix": implementation_matrix,
        "attachments": attachments,
        "bitacora": [],
        "notes": [{
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Proyecto creado desde cotización {quote.get('quote_number', quote_id)}",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        }],
        "created_at": now.isoformat(),
    }

    await db.projects.insert_one(project)
    logger.info(f"Proyecto {project_number} creado desde cotización {quote_id}")

    # Eliminar la cotización origen
    await db.quotes.delete_one({"quote_id": quote_id})
    logger.info(f"Cotización {quote_id} eliminada tras conversión a proyecto {project_number}")

    # Notificar al Gerente de Implementación
    try:
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        impl_manager_email = config.get("implementation_manager_email") if config else None
        if impl_manager_email:
            subject = f"Nuevo Proyecto: {project_number} - {client_name}"
            body = f"""
            <h2>Nuevo Proyecto Pendiente de Asignación</h2>
            <p><strong>Proyecto:</strong> {project_number}</p>
            <p><strong>Cliente:</strong> {client_name} ({client_rif})</p>
            <p><strong>Sede:</strong> {client_sede}</p>
            <p><strong>Cotización origen:</strong> {quote.get('quote_number', '')}</p>
            <p><strong>Tipo:</strong> {quote.get('quote_type', 'VPOS')}</p>
            <p><strong>Total USD:</strong> ${quote.get('total_usd', 0):,.2f}</p>
            <hr>
            <p>Ingrese al sistema para asignar este proyecto a un implementador.</p>
            """
            await send_email(to=impl_manager_email, subject=subject, html_content=body, quote_id=quote_id)
    except Exception as e:
        logger.warning(f"Error notificando gerente de implementación: {e}")
