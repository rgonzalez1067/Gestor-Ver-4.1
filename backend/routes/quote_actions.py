"""Route module: quote_actions.py"""
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

# ==================== QUOTE ACTIONS ENDPOINTS ====================

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

@router.post("/quotes/{quote_id}/approve")
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
    quote_sede = quote.get("sede", "TBP")
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or config.get("admin_email") if config else None
    sales_email = sede_emails.get("sales") if sede_emails else None
    
    email_sent = False
    sales_notified = False
    if RESEND_AVAILABLE:
        try:
            api_key = await get_resend_api_key()
            if api_key:
                resend.api_key = api_key
                
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
                
                # Notificar a administración de la sede
                if admin_email:
                    resend.emails.send({
                        "from": SENDER_EMAIL,
                        "to": [admin_email],
                        "subject": subject,
                        "html": html_content
                    })
                    email_sent = True
                
                # Notificar a ventas de la sede
                if sales_email:
                    resend.emails.send({
                        "from": SENDER_EMAIL,
                        "to": [sales_email],
                        "subject": f"[VENTAS] {subject}",
                        "html": html_content
                    })
                    sales_notified = True
        except Exception as e:
            print(f"Error enviando email a administración/ventas: {e}")
    
    return {
        "message": "Cotización aprobada exitosamente",
        "quote_id": quote_id,
        "new_status": "Aprobada",
        "admin_notified": email_sent,
        "sales_notified": sales_notified,
        "admin_email": admin_email if email_sent else None
    }

@router.post("/quotes/{quote_id}/send-to-client")
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

@router.post("/quotes/{quote_id}/send-to-implementation")
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

@router.post("/quotes/{quote_id}/invoice")
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
    
    # Enviar notificación a administración y ventas usando plantilla por sede
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "TBP")
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or config.get("admin_email") if config else None
    sales_email = sede_emails.get("sales") if sede_emails else None
    
    if RESEND_AVAILABLE and RESEND_API_KEY:
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        
        template = await db.email_templates.find_one({"template_id": "invoice"}, {"_id": 0})
        if not template:
            template = DEFAULT_EMAIL_TEMPLATES["invoice"]
        
        template_vars = {
            "quote_number": quote.get('quote_number', ''),
            "client_name": client_name,
            "client_rif": client.get('rif', 'N/A') if client else 'N/A',
            "invoice_number": invoice_number or 'No especificado',
            "total_usd": f"{quote.get('total_usd', 0):.2f}"
        }
        
        subject = render_email_template(template["subject"], template_vars)
        html_content = render_email_template(template["body_html"], template_vars)
        
        # Notificar a administración de la sede
        if admin_email:
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [admin_email],
                    "subject": subject,
                    "html": html_content
                }
                await asyncio.to_thread(resend.Emails.send, params)
            except Exception as e:
                logger.error(f"Error enviando notificación de factura a admin: {str(e)}")
        
        # Notificar a ventas de la sede
        if sales_email:
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [sales_email],
                    "subject": f"[VENTAS] {subject}",
                    "html": html_content
                }
                await asyncio.to_thread(resend.Emails.send, params)
            except Exception as e:
                logger.error(f"Error enviando notificación de factura a ventas: {str(e)}")
    
    return {
        "message": "Cotización facturada exitosamente",
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }

@router.post("/quotes/{quote_id}/collect")
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
        quote_sede = quote.get("sede", "TBP")
        emails_by_sede = config.get("emails_by_sede", {}) if config else {}
        sede_emails = emails_by_sede.get(quote_sede, {})
        warehouse_email = sede_emails.get("warehouse") or config.get("warehouse_email") if config else None
        
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

@router.post("/quotes/{quote_id}/deliver")
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

@router.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Crea una nueva versión de la cotización (Modificar)"""
    await get_current_user(authorization)
    
    # Obtener cotización original
    original_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not original_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Generar nuevo número de cotización con nomenclatura de sede
    quote_sede = original_quote.get("sede", "TBP")
    new_quote_number = await generate_quote_number(quote_sede)
    
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

