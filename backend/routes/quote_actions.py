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
from services.hoja_ruta_pdf import generate_nota_entrega_pdf

router = APIRouter()
logger = logging.getLogger(__name__)


class QuoteStatusUpdate(BaseModel):
    new_status: str

class EmailSendRequest(BaseModel):
    quote_id: str
    recipient_email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None

# Flujo regular: Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Entregada/Implementación
REGULAR_FLOW = {
    'approve': 'Enviada',
    'invoice': 'Aprobada',
    'collect': 'Facturada',
    'deliver': 'Pagada',
    'send_implementation': 'Pagada',
}

STATUS_ORDER = ['Borrador', 'Enviada', 'Aprobada', 'Facturada', 'Pagada', 'Entregada', 'En Implementación']

def get_status_index(status):
    """Obtiene el índice de un estado en el flujo normal."""
    if status in STATUS_ORDER:
        return STATUS_ORDER.index(status)
    return -1

def is_regularization(current_status, action):
    """Determina si la acción es una regularización (el estado actual ya superó el paso)."""
    action_result = {'approve': 'Aprobada', 'invoice': 'Facturada', 'collect': 'Pagada'}
    result_status = action_result.get(action)
    if not result_status:
        return False
    return get_status_index(current_status) > get_status_index(result_status)

async def check_irregular_flow(quote, action, current_user):
    """Verifica si la acción es irregular y registra en audit log si aplica."""
    expected_status = REGULAR_FLOW.get(action)
    current_status = quote.get("quote_status", "Borrador")
    if expected_status and current_status != expected_status:
        return True
    return False

async def log_audit_exception(quote_id, quote_number, action, expected_status, actual_status, reason, regularization_date, user):
    """Registra excepción de flujo en la colección de auditoría."""
    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    entry = {
        "audit_id": f"aud_{uuid.uuid4().hex[:8]}",
        "quote_id": quote_id,
        "quote_number": quote_number,
        "action": action,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "exception_reason": reason,
        "regularization_date": regularization_date,
        "user_id": user.get("user_id", ""),
        "user_name": user_name,
        "created_at": now
    }
    await db.audit_exceptions.insert_one(entry)
    entry.pop("_id", None)
    return entry

async def mark_quote_irregular(quote_id, action, reason, regularization_date):
    """Marca la cotización como irregular y agrega la excepción."""
    exception_entry = {
        "action": action,
        "reason": reason,
        "regularization_date": regularization_date,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # Ensure irregular_exceptions is an array (handles null or missing field)
    await db.quotes.update_one(
        {"quote_id": quote_id, "$or": [{"irregular_exceptions": None}, {"irregular_exceptions": {"$exists": False}}]},
        {"$set": {"irregular_exceptions": []}}
    )
    await db.quotes.update_one({"quote_id": quote_id}, {
        "$set": {"is_irregular": True},
        "$push": {"irregular_exceptions": exception_entry}
    })

@router.get("/quotes/irregular/count")
async def get_irregular_count(authorization: Optional[str] = Header(None)):
    """Devuelve el conteo de cotizaciones en estado irregular."""
    await get_current_user(authorization)
    count = await db.quotes.count_documents({"is_irregular": True})
    return {"count": count}

@router.get("/quotes/audit-log")
async def get_audit_log(authorization: Optional[str] = Header(None)):
    """Devuelve el log de auditoría de excepciones de flujo."""
    await get_current_user(authorization)
    entries = await db.audit_exceptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return entries

@router.get("/quotes/{quote_id}/audit-log")
async def get_quote_audit_log(quote_id: str, authorization: Optional[str] = Header(None)):
    """Devuelve el log de auditoría de excepciones para una cotización específica."""
    await get_current_user(authorization)
    entries = await db.audit_exceptions.find({"quote_id": quote_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries


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
        "Reparada": "repaired_at",
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
async def approve_quote(quote_id: str, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients")):
    """Aprobar una cotización - Requiere anexo de Orden de Compra. Soporta flujo irregular y mensaje personalizado."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Enviada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para aprobar sin haber enviado al cliente")
        await mark_quote_irregular(quote_id, "approve", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "approve", "Enviada", current_status, exception_reason, regularization_date, current_user)
    
    # Validar Orden de Compra
    attachments = quote.get("attachments", [])
    has_oc = any(a.get("category") == "Orden de Compra" for a in attachments)
    if not has_oc:
        raise HTTPException(status_code=422, detail="Debe cargar la Orden de Compra antes de aprobar la cotización")
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Actualizar estado (solo si NO es regularización retroactiva)
    is_regul = is_regularization(current_status, "approve")
    update_fields = {"approved_at": datetime.now(timezone.utc).isoformat()}
    if not is_regul:
        update_fields["quote_status"] = "Aprobada"
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": update_fields}
    )

    # TRIGGER: Si es reparación, insertar seriales en taller_equipos
    is_repair = quote.get("quote_category") == "repair"
    if is_repair and not is_regul:
        repair_models = quote.get("repair_models", [])
        now_iso = datetime.now(timezone.utc).isoformat()
        taller_docs = []
        for rm in repair_models:
            model_name = rm.get("model_name", "")
            model_id = rm.get("model_id", "")
            for serial in rm.get("serials", []):
                taller_docs.append({
                    "taller_equipo_id": f"te_{uuid.uuid4().hex[:12]}",
                    "serial": serial,
                    "modelo": model_name,
                    "modelo_id": model_id,
                    "client_id": quote.get("client_id", ""),
                    "client_name": client_name,
                    "quote_id": quote_id,
                    "quote_number": quote.get("quote_number", ""),
                    "estatus": "En reparación",
                    "fecha_ingreso": now_iso,
                    "fecha_entrega": None,
                })
        if taller_docs:
            await db.taller_equipos.insert_many(taller_docs)
            logger.info(f"Taller: {len(taller_docs)} equipo(s) ingresados para cotización {quote.get('quote_number')}")
    
    # Preparar email
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "PYME")
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
    
    # Agregar mensaje personalizado si existe
    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content += f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px"><p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p><p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:200]}</p></div>'

    # Parsear destinatarios adicionales
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    email_results = []
    # Para reparaciones, NO enviar email a admin en aprobación (se envía al completar reparación)
    is_repair = quote.get("quote_category") == "repair"
    
    if not is_repair:
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
        # Enviar a destinatarios adicionales (CC)
        for cc in cc_emails:
            r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="approve_cc", quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)

    return {
        "message": "Cotización aprobada exitosamente" + (" — Pendiente de Reparación" if is_repair else ""),
        "quote_id": quote_id,
        "new_status": "Aprobada",
        "emails": email_results,
        "is_repair": is_repair
    }


@router.post("/quotes/{quote_id}/repair-complete")
async def repair_complete(quote_id: str, authorization: Optional[str] = Header(None), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients")):
    """Marcar reparación como completada y notificar a Administración para facturar."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Aprobada":
        raise HTTPException(status_code=400, detail=f"Solo se puede marcar como reparada desde estado 'Aprobada'. Estado actual: '{current_status}'")

    # Cambiar estado a "Reparada"
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {
            "quote_status": "Reparada",
            "repaired_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Notificar a Administración (misma lógica que approve para no-reparaciones)
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "PYME")
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or (config.get("admin_email") if config else None)
    sales_email = sede_emails.get("sales") if sede_emails else None

    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    client_name = client.get("fantasy_name") or client.get("legal_name") if client else "Cliente"

    template = await db.email_templates.find_one({"template_id": "repair_complete"}, {"_id": 0})
    if not template:
        template = {
            "subject": "Reparación Completada: {{quote_number}} - Lista para Facturar",
            "body_html": "<h2>Reparación Completada</h2><p>La cotización de reparación <strong>{{quote_number}}</strong> ha sido completada por el taller y está lista para facturar.</p><p><strong>Cliente:</strong> {{client_name}}</p><p><strong>Total USD:</strong> ${{total_usd}}</p>"
        }

    template_vars = {
        "quote_number": quote.get("quote_number", ""),
        "client_name": client_name,
        "total_usd": f"{quote.get('total_usd', 0):.2f}"
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content += f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px"><p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p><p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:200]}</p></div>'

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    email_results = []
    if admin_email:
        r = await send_email(to=[admin_email], subject=subject, html=html_content, action="repair_complete_admin", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)
    if sales_email:
        r = await send_email(to=[sales_email], subject=f"[VENTAS] {subject}", html=html_content, action="repair_complete_sales", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)
    if not admin_email and not sales_email:
        r = await send_email(to=["admin@sede.local"], subject=subject, html=html_content, action="repair_complete_no_config", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="repair_complete_cc", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)

    return {
        "message": "Reparación marcada como completada. Notificación enviada a Administración.",
        "quote_id": quote_id,
        "new_status": "Reparada",
        "emails": email_results
    }


@router.post("/quotes/{quote_id}/send-to-client")
async def send_quote_to_client(quote_id: str, authorization: Optional[str] = Header(None), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients")):
    """Envía la cotización por email al cliente con el PDF adjunto"""
    current_user = await get_current_user(authorization)
    
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
        contact1 = client.get('contact1') or {}
        client_email = contact1.get('email') if isinstance(contact1, dict) else None
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

    # Agregar mensaje personalizado
    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content += f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px"><p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p><p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:200]}</p></div>'

    # Parsear destinatarios adicionales
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

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
    
    # Enviar a destinatarios adicionales (CC)
    cc_results = []
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="send_to_client_cc", quote_id=quote_id, quote_number=quote.get('quote_number'), attachments=pdf_attachments)
        cc_results.append(r)
    
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


class SendToImplementationRequest(BaseModel):
    is_multistore: Optional[bool] = False
    stores: Optional[list] = None

@router.post("/quotes/{quote_id}/send-to-implementation")
async def send_quote_to_implementation(quote_id: str, body: Optional[SendToImplementationRequest] = None, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date")):
    """Envía la cotización al equipo de implementación. Soporta flujo irregular."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Pagada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para enviar a implementación sin pago registrado")
        await mark_quote_irregular(quote_id, "send-to-implementation", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "send-to-implementation", "Pagada", current_status, exception_reason, regularization_date, current_user)
    
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
            multistore_data = None
            if body and body.is_multistore and body.stores:
                multistore_data = {"is_multistore": True, "stores": body.stores}
            await _create_project_from_quote(quote_for_project, quote_id, multistore_data)
    except Exception as e:
        logger.error(f"Error creando proyecto desde cotización {quote_id}: {e}")

    return {"message": f"Enviado a implementación: {implementation_email}", "new_status": "Enviada a Imple", **email_result}


# ==================== FLUJO DE FACTURACIÓN Y COBRO ====================

@router.post("/quotes/{quote_id}/invoice")
async def invoice_quote(quote_id: str, invoice_number: str = Form(None), exception_reason: str = Form(None), regularization_date: str = Form(None), authorization: Optional[str] = Header(None), x_exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), x_regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients")):
    """Facturar cotización - Requiere anexo de 'Factura'. Soporta flujo irregular y mensaje personalizado."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    quote_category = quote.get("quote_category", "implementation")
    expected_invoice_status = "Reparada" if quote_category == "repair" else "Aprobada"
    is_irregular = current_status != expected_invoice_status
    
    exc_reason = exception_reason or x_exception_reason
    exc_date = regularization_date or x_regularization_date
    
    if is_irregular:
        if not exc_reason:
            raise HTTPException(status_code=422, detail=f"IRREGULAR:Debe proporcionar un motivo para facturar sin estado '{expected_invoice_status}'")
        await mark_quote_irregular(quote_id, "invoice", exc_reason, exc_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "invoice", expected_invoice_status, current_status, exc_reason, exc_date, current_user)
    
    attachments = quote.get("attachments", [])
    factura_attachments = [a for a in attachments if a.get("category") == "Factura"]
    if not factura_attachments:
        raise HTTPException(status_code=422, detail="Debe cargar el documento de Factura antes de facturar la cotización")
    
    invoice_url = factura_attachments[-1].get("url", "")
    
    is_regul = is_regularization(current_status, "invoice")
    update_set = {
        "invoiced_at": datetime.now(timezone.utc).isoformat(),
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }
    if not is_regul:
        update_set["quote_status"] = "Facturada"
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_set})
    
    # Enviar notificación
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "PYME")
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

    # Agregar mensaje personalizado
    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content += f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px"><p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p><p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:200]}</p></div>'

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    email_results = []
    recipients = [(admin_email, "invoice_admin"), (sales_email, "invoice_sales")]
    if not admin_email and not sales_email:
        recipients = [("admin@sede.local", "invoice_no_config")]
    
    for email, action in recipients:
        if email:
            prefix = "[VENTAS] " if "sales" in action else ""
            r = await send_email(to=[email], subject=f"{prefix}{subject}", html=html_content, action=action, quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)
    
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="invoice_cc", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)

    return {"message": "Cotización facturada exitosamente", "invoice_pdf_url": invoice_url, "invoice_number": invoice_number, "emails": email_results}


@router.post("/quotes/{quote_id}/collect")
async def collect_quote(quote_id: str, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients")):
    """Marcar cotización como Pagada - Requiere anexos en categoría 'Pagos'. Soporta flujo irregular y mensaje personalizado."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Facturada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para cobrar sin facturar previamente")
        await mark_quote_irregular(quote_id, "collect", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "collect", "Facturada", current_status, exception_reason, regularization_date, current_user)
    
    attachments = quote.get("attachments", [])
    payment_proofs = [a for a in attachments if a.get("category") == "Pagos"]
    if not payment_proofs:
        raise HTTPException(status_code=422, detail="Debe cargar al menos un comprobante de pago antes de registrar el cobro")
    
    is_regul = is_regularization(current_status, "collect")
    update_set = {"paid_at": datetime.now(timezone.utc).isoformat()}
    if not is_regul:
        update_set["quote_status"] = "Pagada"
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_set})
    
    email_results = []
    quote_category = quote.get("quote_category", "implementation")
    
    # Parsear CC y mensaje personalizado
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]
    
    if quote_category == "equipment":
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        quote_sede = quote.get("sede", "PYME")
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
        
        if custom_message and custom_message.strip():
            user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            html_content += f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px"><p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p><p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:200]}</p></div>'
        
        r = await send_email(to=[warehouse_email], subject=subject, html=html_content, action="collect_warehouse", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
    
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] Cobro registrado - {quote.get('quote_number', '')}", html=f"<p>Se ha registrado el cobro de la cotización {quote.get('quote_number', '')}.</p>", action="collect_cc", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
    
    return {"message": "Cotización marcada como Pagada", "emails": email_results}


@router.get("/quotes/{quote_id}/delivery-prep")
async def delivery_preparation(quote_id: str, warehouse_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Devuelve los datos de preparación para entrega: items de la cotización y stock disponible."""
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if quote.get("quote_category") != "equipment":
        raise HTTPException(status_code=400, detail="Solo cotizaciones de equipos soportan entrega")

    equipment_items = quote.get("equipment_items", [])

    # Almacenes disponibles
    warehouses = await db.warehouses.find({}, {"_id": 0}).sort("name", 1).to_list(100)

    # Stock por almacén si se especifica
    stock_by_item = {}
    if warehouse_id:
        movements = await db.inventory_movements.find(
            {"warehouse_id": warehouse_id}, {"_id": 0}
        ).to_list(10000)
        stock = {}
        for m in movements:
            iid = m["item_id"]
            if iid not in stock:
                stock[iid] = {"quantity": 0, "serials": [], "item_type": m.get("item_type", "")}
            sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
            stock[iid]["quantity"] += sign * m["quantity"]
            if m.get("serials"):
                if sign > 0:
                    stock[iid]["serials"].extend(m["serials"])
                else:
                    for s in m["serials"]:
                        if s in stock[iid]["serials"]:
                            stock[iid]["serials"].remove(s)
        stock_by_item = stock

    # Enrich items with stock info
    items_with_stock = []
    for item in equipment_items:
        hw_id = item.get("hardware_id", "")
        st = stock_by_item.get(hw_id, {})
        items_with_stock.append({
            "hardware_id": hw_id,
            "name": item.get("name", ""),
            "hardware_type": item.get("hardware_type", ""),
            "quantity_quoted": item.get("quantity", 1),
            "stock_available": st.get("quantity", 0),
            "serials_available": st.get("serials", []),
            "requires_serial": (st.get("item_type", "") or item.get("hardware_type", "")).lower() in SERIALIZED_TYPES,
        })

    return {
        "quote_number": quote.get("quote_number", ""),
        "client_id": quote.get("client_id", ""),
        "client_name": quote.get("client_name", ""),
        "warehouses": warehouses,
        "items": items_with_stock,
    }


@router.post("/quotes/{quote_id}/deliver")
async def deliver_quote(quote_id: str, body: dict = {}, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date")):
    """Marcar cotización de equipos o reparaciones como Entregada, con deducción automática de inventario y generación de Hoja de Ruta."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    quote_category = quote.get("quote_category", "implementation")
    if quote_category not in ["equipment", "repair"]:
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de equipos o reparaciones")

    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Pagada"

    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para entregar sin pago registrado")
        await mark_quote_irregular(quote_id, "deliver", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "deliver", "Pagada", current_status, exception_reason, regularization_date, current_user)

    warehouse_id = body.get("warehouse_id")
    delivery_items = body.get("delivery_items", [])
    delivery_notes = body.get("notes", "")
    # Logistics fields
    delivery_method = body.get("delivery_method", "personalizada")
    receiver_name = body.get("receiver_name", "")
    receiver_cedula = body.get("receiver_cedula", "")
    receiver_phone = body.get("receiver_phone", "")
    courier_name = body.get("courier_name", "")
    courier_office = body.get("courier_office", "")
    # Legacy compatibility
    transportista = courier_name if delivery_method == "courier" else receiver_name
    guia_placa = courier_office if delivery_method == "courier" else ""
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Get client info
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name", "") or "") if client else (quote.get("client_name") or "")
    client_rif = (client.get("rif") or "") if client else ""
    client_address = (client.get("address") or "") if client else ""

    hoja_ruta_url = None
    delivered_pdf_items = []

    # Process inventory exits if warehouse and items provided
    if warehouse_id and delivery_items:
        wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
        if not wh:
            raise HTTPException(status_code=404, detail="Almacén no encontrado")

        warehouse_name = wh.get("name", "")

        for d_item in delivery_items:
            hw_id = d_item.get("hardware_id", "")
            qty = d_item.get("quantity", 0)
            serials = d_item.get("serials", [])
            if not hw_id or qty <= 0:
                continue

            # Get hardware info
            hw = await db.hardware.find_one({"hardware_id": hw_id}, {"_id": 0})
            if not hw:
                raise HTTPException(status_code=404, detail=f"Producto {hw_id} no encontrado en catálogo")

            hw_type = hw.get("type", "General")
            requires_serial = hw_type.lower() in SERIALIZED_TYPES

            # Calculate current stock
            movements = await db.inventory_movements.find(
                {"warehouse_id": warehouse_id, "item_id": hw_id}, {"_id": 0}
            ).to_list(10000)
            stock_qty = 0
            stock_serials = []
            cost_total = 0
            for m in movements:
                sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
                stock_qty += sign * m["quantity"]
                cost_total += sign * m["quantity"] * m.get("unit_cost", 0)
                if m.get("serials"):
                    if sign > 0:
                        stock_serials.extend(m["serials"])
                    else:
                        for s in m["serials"]:
                            if s in stock_serials:
                                stock_serials.remove(s)
            avg_cost = round(cost_total / stock_qty, 2) if stock_qty > 0 else 0

            if stock_qty < qty:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente de '{hw['name']}'. Disponible: {stock_qty}, Solicitado: {qty}")

            if requires_serial:
                if len(serials) != qty:
                    raise HTTPException(status_code=400, detail=f"Debe seleccionar {qty} serial(es) para '{hw['name']}'")
                for s in serials:
                    if s not in stock_serials:
                        raise HTTPException(status_code=400, detail=f"Serial '{s}' no disponible en almacén")

            # Create exit movement
            exit_mov = InventoryMovement(
                warehouse_id=warehouse_id,
                item_id=hw_id,
                item_name=hw["name"],
                item_type=hw_type,
                movement_type="salida",
                quantity=qty,
                unit_cost=avg_cost,
                serials=serials if requires_serial else [],
                reference=f"Entrega COT {quote.get('quote_number', '')}",
                client_name=client_name,
                client_id=quote.get("client_id", ""),
                quote_id=quote_id,
                quote_number=quote.get("quote_number", ""),
                notes=f"Salida automática por entrega de cotización {quote.get('quote_number', '')}",
                created_by=user_name,
            )
            doc = exit_mov.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            await db.inventory_movements.insert_one(doc)
            doc.pop("_id", None)

            # Trigger CheckStock alert
            from routes.inventory import check_stock_alert
            await check_stock_alert(warehouse_id, hw_id, hw["name"])

            delivered_pdf_items.append({
                "name": hw["name"],
                "type": hw_type,
                "quantity": qty,
                "serials": serials if requires_serial else [],
            })

        # Generate Nota de Entrega PDF
        try:
            logo_path = None
            logo_file = UPLOADS_DIR / "logo.png"
            if logo_file.exists():
                logo_path = str(logo_file)

            # Generate correlativo NE-YYYY-XXXX
            year = datetime.now(timezone.utc).strftime("%Y")
            last_ne = await db.nota_entrega_counter.find_one_and_update(
                {"year": year},
                {"$inc": {"counter": 1}},
                upsert=True,
                return_document=True,
            )
            if last_ne and "_id" in last_ne:
                del last_ne["_id"]
            ne_num = last_ne.get("counter", 1) if last_ne else 1
            correlativo = f"NE-{year}-{ne_num:04d}"

            # Get project info if exists
            project = await db.projects.find_one({"quote_id": quote_id}, {"_id": 0})
            project_number = project.get("project_number", "") if project else ""

            # Get client contact info
            contact_name = ""
            contact_phone = ""
            if client:
                contact1 = client.get("contact1") or {}
                contacts_crm = client.get("contacts", [])
                if contact1 and contact1.get("name"):
                    contact_name = contact1.get("name", "")
                    contact_phone = contact1.get("phone", "")
                elif contacts_crm:
                    contact_name = contacts_crm[0].get("full_name", "")
                    contact_phone = contacts_crm[0].get("phone", "")

            # Classify items (Equipo vs Consumible)
            SERIALIZED = ["pos", "pinpad", "mpos"]
            for pdi in delivered_pdf_items:
                pdi["category"] = "Equipo" if pdi.get("type", "").lower() in SERIALIZED else "Consumible"

            pdf_buffer = generate_nota_entrega_pdf(
                correlativo=correlativo,
                quote_number=quote.get("quote_number", ""),
                project_number=project_number,
                client_name=client_name,
                client_rif=client_rif,
                client_address=client_address,
                client_contact_name=contact_name,
                client_contact_phone=contact_phone,
                warehouse_name=warehouse_name,
                delivered_items=delivered_pdf_items,
                delivered_by=user_name,
                transportista=transportista,
                guia_placa=guia_placa,
                notes=delivery_notes,
                logo_path=logo_path,
                delivery_method=delivery_method,
                receiver_name=receiver_name,
                receiver_cedula=receiver_cedula,
                receiver_phone=receiver_phone,
                courier_name=courier_name,
                courier_office=courier_office,
            )
            pdf_filename = f"NotaEntrega_{correlativo}.pdf"
            pdf_path = UPLOADS_DIR / pdf_filename
            with open(pdf_path, "wb") as f:
                f.write(pdf_buffer.getvalue())
            hoja_ruta_url = f"/uploads/{pdf_filename}"

            # Attach to quote
            attachment = {
                "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
                "category": "Otros",
                "filename": pdf_filename,
                "url": hoja_ruta_url,
                "uploaded_by": current_user.get("email", "system"),
                "uploaded_by_name": user_name,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "content_type": "application/pdf",
            }
            await db.quotes.update_one(
                {"quote_id": quote_id},
                {"$push": {"attachments": attachment}}
            )

            # Also attach to client annexes
            if client:
                client_attachment = {**attachment, "attachment_id": f"att_{uuid.uuid4().hex[:12]}", "category": "Otros"}
                await db.clients.update_one(
                    {"client_id": quote.get("client_id")},
                    {"$push": {"attachments": client_attachment}}
                )

            logger.info(f"Nota de Entrega generada: {hoja_ruta_url}")
        except Exception as e:
            logger.error(f"Error generando Nota de Entrega: {e}")
            import traceback
            traceback.print_exc()

    # Update quote status
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "quote_status": "Entregada",
        "delivered_at": datetime.now(timezone.utc).isoformat()
    }})

    return {
        "message": "Cotización marcada como Entregada",
        "inventory_processed": len(delivered_pdf_items) > 0,
        "items_delivered": len(delivered_pdf_items),
        "hoja_ruta_url": hoja_ruta_url,
    }


# ===================== ENTREGA DE REPARACIONES =====================

@router.get("/quotes/{quote_id}/repair-delivery-prep")
async def repair_delivery_prep(quote_id: str, authorization: Optional[str] = Header(None)):
    """Obtener equipos en reparación del cliente para selección de entrega."""
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    client_id = quote.get("client_id", "")

    # Obtener equipos en reparación del cliente
    equipos_cursor = db.taller_equipos.find(
        {"client_id": client_id, "estatus": "En reparación"},
        {"_id": 0}
    )
    equipos = await equipos_cursor.to_list(5000)

    # Agrupar por modelo
    modelos_map = {}
    for eq in equipos:
        modelo = eq.get("modelo", "Sin modelo")
        if modelo not in modelos_map:
            modelos_map[modelo] = {
                "modelo": modelo,
                "modelo_id": eq.get("modelo_id", ""),
                "serials": [],
            }
        modelos_map[modelo]["serials"].append({
            "taller_equipo_id": eq.get("taller_equipo_id"),
            "serial": eq.get("serial", ""),
            "quote_number": eq.get("quote_number", ""),
            "fecha_ingreso": eq.get("fecha_ingreso", ""),
        })

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name", "")) if client else ""

    return {
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "quote_status": quote.get("quote_status", ""),
        "client_id": client_id,
        "client_name": client_name,
        "client_rif": (client.get("rif", "") if client else ""),
        "client_address": (client.get("address", "") if client else ""),
        "modelos": list(modelos_map.values()),
        "total_equipos": len(equipos),
    }


@router.post("/quotes/{quote_id}/repair-deliver")
async def repair_deliver(quote_id: str, body: dict = {}, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date")):
    """Entregar equipos reparados: actualiza taller_equipos, genera Nota de Entrega, cambia estado."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Pagada"

    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para entregar sin pago registrado")
        await mark_quote_irregular(quote_id, "repair-deliver", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "repair-deliver", "Pagada", current_status, exception_reason, regularization_date, current_user)

    selected_serials = body.get("selected_serials", [])  # Lista de taller_equipo_id
    delivery_method = body.get("delivery_method", "personalizada")
    receiver_name = body.get("receiver_name", "")
    receiver_cedula = body.get("receiver_cedula", "")
    receiver_phone = body.get("receiver_phone", "")
    courier_name = body.get("courier_name", "")
    courier_office = body.get("courier_office", "")
    delivery_notes = body.get("notes", "")

    if not selected_serials:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un equipo para entregar")

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Obtener info del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name", "")) if client else (quote.get("client_name") or "")
    client_rif = (client.get("rif", "") if client else "")
    client_address = (client.get("address", "") if client else "")

    # Obtener los equipos seleccionados de taller_equipos
    equipos_to_deliver = await db.taller_equipos.find(
        {"taller_equipo_id": {"$in": selected_serials}, "estatus": "En reparación"},
        {"_id": 0}
    ).to_list(5000)

    if not equipos_to_deliver:
        raise HTTPException(status_code=400, detail="No se encontraron equipos válidos para entregar")

    # Agrupar por modelo para el PDF
    modelos_pdf = {}
    for eq in equipos_to_deliver:
        modelo = eq.get("modelo", "Sin modelo")
        if modelo not in modelos_pdf:
            modelos_pdf[modelo] = {"name": modelo, "type": "Equipo", "quantity": 0, "serials": [], "category": "Equipo"}
        modelos_pdf[modelo]["quantity"] += 1
        modelos_pdf[modelo]["serials"].append(eq.get("serial", ""))

    delivered_pdf_items = list(modelos_pdf.values())

    # Generar Nota de Entrega PDF
    hoja_ruta_url = None
    try:
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)

        year = datetime.now(timezone.utc).strftime("%Y")
        last_ne = await db.nota_entrega_counter.find_one_and_update(
            {"year": year},
            {"$inc": {"counter": 1}},
            upsert=True,
            return_document=True,
        )
        if last_ne and "_id" in last_ne:
            del last_ne["_id"]
        ne_num = last_ne.get("counter", 1) if last_ne else 1
        correlativo = f"NE-{year}-{ne_num:04d}"

        contact_name = ""
        contact_phone = ""
        if client:
            contact1 = client.get("contact1") or {}
            if isinstance(contact1, dict) and contact1.get("name"):
                contact_name = contact1.get("name", "")
                contact_phone = contact1.get("phone", "")

        transportista = courier_name if delivery_method == "courier" else receiver_name
        guia_placa = courier_office if delivery_method == "courier" else ""

        pdf_buffer = generate_nota_entrega_pdf(
            correlativo=correlativo,
            quote_number=quote.get("quote_number", ""),
            project_number="",
            client_name=client_name,
            client_rif=client_rif,
            client_address=client_address,
            client_contact_name=contact_name,
            client_contact_phone=contact_phone,
            warehouse_name="Taller de Reparación",
            delivered_items=delivered_pdf_items,
            delivered_by=user_name,
            transportista=transportista,
            guia_placa=guia_placa,
            notes=delivery_notes,
            logo_path=logo_path,
            delivery_method=delivery_method,
            receiver_name=receiver_name,
            receiver_cedula=receiver_cedula,
            receiver_phone=receiver_phone,
            courier_name=courier_name,
            courier_office=courier_office,
        )
        pdf_filename = f"NotaEntrega_Reparacion_{correlativo}.pdf"
        pdf_path = UPLOADS_DIR / pdf_filename
        with open(pdf_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        hoja_ruta_url = f"/uploads/{pdf_filename}"

        # Adjuntar a la cotización
        attachment = {
            "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
            "category": "Nota de Entrega",
            "filename": pdf_filename,
            "url": hoja_ruta_url,
            "uploaded_by": current_user.get("email", "system"),
            "uploaded_by_name": user_name,
            "uploaded_at": now_iso,
            "content_type": "application/pdf",
        }
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$push": {"attachments": attachment}}
        )

        if client:
            client_att = {**attachment, "attachment_id": f"att_{uuid.uuid4().hex[:12]}"}
            await db.clients.update_one(
                {"client_id": quote.get("client_id")},
                {"$push": {"attachments": client_att}}
            )

        logger.info(f"Nota de Entrega Reparación generada: {hoja_ruta_url}")
    except Exception as e:
        logger.error(f"Error generando Nota de Entrega Reparación: {e}")
        import traceback
        traceback.print_exc()

    # UPDATE masivo: cambiar estatus a "Entregado" con fecha_entrega
    await db.taller_equipos.update_many(
        {"taller_equipo_id": {"$in": selected_serials}},
        {"$set": {"estatus": "Entregado", "fecha_entrega": now_iso}}
    )

    # Actualizar estado de la cotización a "Entregada"
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "quote_status": "Entregada",
        "delivered_at": now_iso,
    }})

    return {
        "message": f"Entrega registrada: {len(equipos_to_deliver)} equipo(s) entregados",
        "equipos_entregados": len(equipos_to_deliver),
        "hoja_ruta_url": hoja_ruta_url,
    }


@router.get("/taller-equipos")
async def get_taller_equipos(authorization: Optional[str] = Header(None), client_id: Optional[str] = None, estatus: Optional[str] = None):
    """Consultar equipos en taller (para futura vista de trazabilidad)."""
    await get_current_user(authorization)
    query = {}
    if client_id:
        query["client_id"] = client_id
    if estatus:
        query["estatus"] = estatus
    equipos = await db.taller_equipos.find(query, {"_id": 0}).to_list(10000)
    return {"equipos": equipos, "total": len(equipos)}


@router.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Crea una nueva versión de la cotización (Modificar)"""
    await get_current_user(authorization)
    
    original_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not original_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    quote_sede = original_quote.get("sede", "PYME")
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

async def _create_project_from_quote(quote: dict, quote_id: str, multistore_data: dict = None):
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
        "client_segment": quote.get("client_segment", "PYME"),
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
        "is_irregular": quote.get("is_irregular", False),
        "irregular_exceptions": quote.get("irregular_exceptions", []) or [],
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
        "project_type": "single",
        "client_notified": False,
        "client_notified_at": None,
        "client_notified_by": None,
        "bank_notifications": {},
        "rollup_progress": None,
    }

    # Soporte Multitienda
    if multistore_data and multistore_data.get("is_multistore"):
        stores_raw = multistore_data.get("stores", [])
        project["project_type"] = "multistore"
        project["stores"] = []
        for store in stores_raw:
            store_entry = {
                "store_id": f"st_{uuid.uuid4().hex[:8]}",
                "name": store.get("name", ""),
                "box_count": store.get("box_count", 0),
                "implementation_matrix": dict(implementation_matrix),
                "status": "Pendiente",
                "notes": [],
            }
            project["stores"].append(store_entry)
        # Nota especial para multitienda
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Proyecto Multitienda con {len(stores_raw)} tienda(s): {', '.join(s.get('name', '') for s in stores_raw)}",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

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
