"""Route module: projects.py - Módulo de Proyectos (Post-Venta)"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form, Query
from fastapi.responses import Response
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging
import os
import json
import base64
import re

from config import db, get_current_user
from models import PROJECT_STATUSES
from services.email_service import send_email
from services.project_template_vars import resolve_project_template_vars
from services.object_storage import init_storage, put_object, get_object

router = APIRouter()
logger = logging.getLogger(__name__)

IMPLEMENTATION_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]
STORE_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]  # Sin "Notificado" para tiendas
PROJECT_PRIORITIES = ["Alta", "Media", "Normal"]


class ProjectStatusUpdate(BaseModel):
    new_status: str
    note: Optional[str] = None
    change_date: Optional[str] = None


class ProjectAssign(BaseModel):
    assigned_to_user_id: str
    estimated_delivery_date: Optional[str] = None
    reassignment_comment: Optional[str] = None
    reassignment_date: Optional[str] = None


class TicketNumberUpdate(BaseModel):
    ticket_number: str


class VTIDGenerateRequest(BaseModel):
    prefix: str
    start_number: int = 1
    store_id: Optional[str] = None


class PhaseUpdate(BaseModel):
    bank_name: str
    product_name: str
    phase: str
    completed: bool
    expected: Optional[int] = None
    processed: Optional[int] = None


class BitacoraEntry(BaseModel):
    text: str
    execution_date: str


class PriorityUpdate(BaseModel):
    priority: str


class BankNotifyRequest(BaseModel):
    bank_name: str


class AdhocEmailRequest(BaseModel):
    recipients: List[str]
    subject: str
    message: str
    image_urls: Optional[List[str]] = None


NOTIFICATION_PREFIXES = [
    "Primer Envío",
    "Primer Recordatorio",
    "Segundo Recordatorio",
    "Tercer Recordatorio",
]

# Legacy mapping for backwards compatibility
NOTIFICATION_LEVELS = NOTIFICATION_PREFIXES

NOTIFICATION_SUBJECTS = {
    "Primer Envío": "Notificación de Implementación",
    "Primer Recordatorio": "1er Recordatorio — Implementación",
    "Segundo Recordatorio": "2do Recordatorio — Implementación",
    "Tercer Recordatorio": "3er Recordatorio (Urgente) — Implementación",
}


# ==================== PROJECT ENDPOINTS ====================

@router.get("/projects")
async def get_projects(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    projects = await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return projects


@router.get("/projects/stats")
async def get_project_stats(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    total = await db.projects.count_documents({})
    pending = await db.projects.count_documents({"status": "Pendiente por Asignar"})
    in_progress = await db.projects.count_documents({"status": "Asignado / En Proceso"})
    blocked = await db.projects.count_documents({"status": {"$in": ["Suspendido por Cliente", "Suspendido por Banco"]}})
    completed = await db.projects.count_documents({"status": "Finalizado / Producción"})
    irregular = await db.projects.count_documents({"is_irregular": True})
    return {"total": total, "pending": pending, "in_progress": in_progress, "blocked": blocked, "completed": completed, "irregular": irregular}


@router.get("/projects/implementers/list")
async def get_implementers(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    impl_cargos = ["Implementador", "Coordinador de Implementación", "Gerente de Implementación", "Técnico de Infraestructura"]
    users = await db.users.find(
        {"cargo": {"$in": impl_cargos}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
    ).to_list(100)
    if not users:
        users = await db.users.find({}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}).to_list(100)
    return users


@router.get("/projects/{project_id}")
async def get_project(project_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.put("/projects/{project_id}/assign")
async def assign_project(project_id: str, assignment: ProjectAssign, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    implementer = await db.users.find_one({"user_id": assignment.assigned_to_user_id}, {"_id": 0})
    if not implementer:
        raise HTTPException(status_code=404, detail="Implementador no encontrado")

    implementer_name = f"{implementer.get('first_name', '')} {implementer.get('last_name', '')}".strip()
    assigner_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    now = datetime.now(timezone.utc).isoformat()

    update_data = {
        "assigned_to_user_id": assignment.assigned_to_user_id,
        "assigned_to_name": implementer_name,
        "assigned_by_user_id": current_user.get("user_id"),
        "assigned_by_name": assigner_name,
        "assigned_at": now,
        "fecha_asignacion": now,
        "status": "Asignado / En Proceso",
        "updated_at": now,
    }
    if assignment.estimated_delivery_date:
        update_data["estimated_delivery_date"] = assignment.estimated_delivery_date

    previous_assignee = project.get("assigned_to_name", "")
    is_reassignment = bool(previous_assignee)

    note_text = f"Proyecto {'reasignado' if is_reassignment else 'asignado'} a {implementer_name}."
    if is_reassignment and previous_assignee:
        note_text += f" (Anterior: {previous_assignee})"
    if assignment.reassignment_date:
        note_text += f" Fecha: {assignment.reassignment_date}."
    if assignment.reassignment_comment:
        note_text += f" Motivo: {assignment.reassignment_comment}"
    if assignment.estimated_delivery_date:
        note_text += f" Fecha estimada: {assignment.estimated_delivery_date}"

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": note_text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": assigner_name,
        "created_at": now,
    }

    await db.projects.update_one({"project_id": project_id}, {"$set": update_data, "$push": {"notes": note}})

    # Notificar al implementador
    impl_email = implementer.get("email")
    if impl_email:
        try:
            await send_email(
                to=[impl_email],
                subject=f"Proyecto Asignado: {project.get('project_number', project_id)}",
                html=f"<h2>Nuevo proyecto asignado</h2><p><strong>Proyecto:</strong> {project.get('project_number')}</p><p><strong>Cliente:</strong> {project.get('client_name')} ({project.get('client_rif')})</p><p><strong>Asignado por:</strong> {assigner_name}</p>",
                action="assign_project",
                quote_id=project.get("quote_id")
            )
        except Exception as e:
            logger.warning(f"Error notificando implementador: {e}")

    # Push notification (evento #7 Proyecto asignado a mí)
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="project_assigned_to_me",
            title=f"Proyecto {project.get('project_number','')} asignado a ti",
            message=f"Cliente {project.get('client_name','')} · Total USD ${project.get('total_usd',0):,.2f}",
            context={
                "assignee_user_id": assignment.assigned_to_user_id,
                "sede": project.get("client_sede"),
            },
            link=f"/projects/{project_id}",
            project_id=project_id,
        )
        # Actualizar assigned_at para que el cron de 'asignado sin iniciar' pueda medir
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"assigned_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.warning(f"[notify] project_assigned_to_me failed: {e}")

    return {"message": "Proyecto asignado exitosamente", "assigned_to": implementer_name}


@router.put("/projects/{project_id}/status")
async def update_project_status(project_id: str, status_update: ProjectStatusUpdate, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    if status_update.new_status not in PROJECT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Válidos: {PROJECT_STATUSES}")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    update_data = {"status": status_update.new_status, "updated_at": now}
    if status_update.new_status == "Finalizado / Producción":
        update_data["completed_at"] = now

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    note_text = f"Estado cambiado a '{status_update.new_status}'"
    if status_update.change_date:
        note_text += f" (Fecha: {status_update.change_date})"
    if status_update.note:
        note_text += f" — {status_update.note}"

    note = {"note_id": f"pn_{uuid.uuid4().hex[:8]}", "text": note_text, "created_by": current_user.get("user_id", ""), "created_by_name": user_name, "created_at": now}
    await db.projects.update_one({"project_id": project_id}, {"$set": update_data, "$push": {"notes": note}})
    return {"message": f"Estado actualizado a '{status_update.new_status}'", "new_status": status_update.new_status}


@router.put("/projects/{project_id}/priority")
async def update_project_priority(project_id: str, body: PriorityUpdate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    if body.priority not in PROJECT_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Prioridad inválida. Válidas: {PROJECT_PRIORITIES}")
    result = await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"priority": body.priority, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return {"message": f"Prioridad actualizada a '{body.priority}'"}


# ==================== NOTIFICATION ENDPOINTS ====================

def _calculate_single_progress(project: dict) -> dict:
    """Calcula el avance de un proyecto single basado en su implementación matrix."""
    matrix = project.get("implementation_matrix", {})
    bank_progress = {}
    for bank_name, products in matrix.items():
        bank_progress[bank_name] = {}
        for product_name, phases in products.items():
            completed = sum(1 for p in IMPLEMENTATION_PHASES if phases.get(p, {}).get("completed", False))
            pct = round((completed / len(IMPLEMENTATION_PHASES)) * 100, 1) if IMPLEMENTATION_PHASES else 0
            bank_progress[bank_name][product_name] = pct
    all_pcts = [pct for bank in bank_progress.values() for pct in bank.values()]
    global_progress = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0
    return {"global_progress": global_progress, "bank_progress": bank_progress}


def _calculate_rollup_progress(project: dict) -> dict:
    """Calcula el avance promedio de la matriz principal basado en las matrices de las tiendas.
    Retorna dict con progreso por banco/producto y progreso global."""
    stores = project.get("stores", [])
    if not stores:
        return {"global_progress": 0, "bank_progress": {}}

    main_matrix = project.get("implementation_matrix", {})
    bank_progress = {}

    for bank_name in main_matrix:
        products = main_matrix[bank_name]
        bank_progress[bank_name] = {}
        for product_name in products:
            # Para cada producto, calcular el promedio de avance de las tiendas
            store_progresses = []
            for store in stores:
                store_matrix = store.get("implementation_matrix", {})
                store_phases = store_matrix.get(bank_name, {}).get(product_name, {})
                completed = sum(1 for p in STORE_PHASES if store_phases.get(p, {}).get("completed", False))
                pct = (completed / len(STORE_PHASES)) * 100 if STORE_PHASES else 0
                store_progresses.append(pct)
            avg = sum(store_progresses) / len(store_progresses) if store_progresses else 0
            bank_progress[bank_name][product_name] = round(avg, 1)

    # Progreso global
    all_pcts = [pct for bank in bank_progress.values() for pct in bank.values()]
    global_progress = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0

    return {"global_progress": global_progress, "bank_progress": bank_progress}


@router.post("/projects/{project_id}/notify-client")
async def notify_client(project_id: str, authorization: Optional[str] = Header(None)):
    """Primera Comunicación al cliente. Desbloquea la matriz."""
    return await _send_sequential_notification(project_id, "client", None, authorization)


@router.post("/projects/{project_id}/notify-bank")
async def notify_bank(project_id: str, body: BankNotifyRequest, authorization: Optional[str] = Header(None)):
    """Primera Comunicación a un banco."""
    return await _send_sequential_notification(project_id, "bank", body.bank_name, authorization)


class SequentialNotifyRequest(BaseModel):
    target: str  # "client", "bank", or "bank_client"
    bank_name: Optional[str] = None
    additional_recipients: Optional[List[str]] = None  # CC emails
    to_override: Optional[List[str]] = None  # Si se envía, reemplaza el TO auto-resuelto desde DB
    custom_html: Optional[str] = None  # Editable preview override
    custom_subject: Optional[str] = None  # Editable subject override


@router.post("/projects/{project_id}/send-notification")
async def send_sequential_notification(project_id: str, body: SequentialNotifyRequest, authorization: Optional[str] = Header(None)):
    """Enviar notificación al cliente o banco. El prefijo se calcula automáticamente por conteo."""
    return await _send_sequential_notification(
        project_id, body.target, body.bank_name, authorization,
        additional_recipients=body.additional_recipients,
        custom_html=body.custom_html,
        custom_subject=body.custom_subject,
        to_override=body.to_override,
    )


def _render_vars(template_str: str, variables: dict) -> str:
    """Renderiza variables {key} y {{key}} en una plantilla.
    También maneja el caso donde el editor HTML inyecta tags dentro de las llaves.
    """
    result = template_str

    # Paso 1: Limpiar HTML tags dentro de llaves (ej: <span>{</span>Nombre<span>}</span>)
    result = _clean_html_in_braces(result)

    # Paso 2: Reemplazo estándar
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value or ""))
        result = result.replace(f"{{{key}}}", str(value or ""))
    return result


def _clean_html_in_braces(html: str) -> str:
    """Limpia etiquetas HTML que el editor rico pueda insertar dentro de variables {Variable}.
    Ej: <span>{</span><b>Nombre_Cliente</b><span>}</span> → {Nombre_Cliente}
    """
    # Pattern: find sequences that look like a variable with HTML tags mixed in
    # This handles: {<span>Nombre_Cliente</span>}, <b>{</b>Nombre<b>}</b>, etc.
    html_tag = r'(?:<[^>]*>)*'
    pattern = re.compile(
        r'(' + html_tag + r'\{' + html_tag + r')'  # Opening brace with possible tags
        r'([A-Za-z_][A-Za-z0-9_]*)'                 # Variable name (clean)
        r'(' + html_tag + r'\}' + html_tag + r')',   # Closing brace with possible tags
    )

    def replacer(m):
        var_name = m.group(2)
        return '{' + var_name + '}'

    # Also handle cases where the variable name itself has HTML tags in it
    # e.g., {<span>Nombre</span>_<span>Cliente</span>}
    inner_tag_pattern = re.compile(r'\{([^}]*<[^>]*>[^}]*)\}')

    def clean_inner(m):
        inner = re.sub(r'<[^>]*>', '', m.group(1))
        return '{' + inner.strip() + '}'

    result = inner_tag_pattern.sub(clean_inner, html)
    result = pattern.sub(replacer, result)
    return result


async def _resolve_notification_email(project: dict, target: str, bank_name: Optional[str], send_count: int, template_vars: dict) -> dict:
    """Resuelve destinatarios, asunto y HTML de una notificación de proyecto.
    El asunto se prefija automáticamente según el conteo de envíos.
    Returns: {to_list, subject, html, entity_label, prefix}
    """
    # Determinar prefijo según conteo de envíos
    prefix_idx = min(send_count, len(NOTIFICATION_PREFIXES) - 1)
    prefix_label = NOTIFICATION_PREFIXES[prefix_idx]

    ticket = project.get("ticket_number", "")

    # Add notification-specific vars
    template_vars["notification_level"] = prefix_label
    template_vars["notification_subject"] = prefix_label

    if target == "client":
        client = None
        client_id = project.get("client_id")
        if client_id:
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        client_name = project.get("client_name", "Cliente")

        # === DATA BINDING CORRECTO: extraer emails de contacts[] ===
        to_list = []
        if client:
            contacts = client.get("contacts", [])
            # Contacto principal = primer contacto
            if contacts:
                primary_email = contacts[0].get("email", "")
                if primary_email and "@" in primary_email:
                    to_list.append(primary_email)
            # Contactos secundarios notificables
            for c in contacts[1:]:
                c_email = c.get("email", "")
                if c_email and "@" in c_email and c_email not in to_list:
                    to_list.append(c_email)
            # Fallback al email top-level del cliente
            if not to_list:
                top_email = client.get("email", "")
                if top_email and "@" in top_email:
                    to_list.append(top_email)

        if not to_list:
            to_list = []  # Sin destinatarios → el frontend avisará

        entity_label = f"Cliente ({client_name})"

        # Siempre usar plantilla del DB
        template = await db.email_templates.find_one({"template_id": "project_notify_client"}, {"_id": 0})
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "Implementación: {project_number}"), template_vars)
            subject = f"[{prefix_label}] {raw_subject}"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            subject = f"[{prefix_label}] Implementación: {project.get('project_number', '')}"
            html = f"""<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;margin:0 auto;">
<h2 style="color:#2c3e50;">[{prefix_label}] Implementación</h2>
{f'<p><strong>Ticket:</strong> {ticket}</p>' if ticket else ''}
<p>Estimado/a <strong>{template_vars.get('Contacto_Principal', client_name)}</strong>,</p>
<p>Le informamos sobre el estado de su proyecto de implementación <strong>{project.get('project_number','')}</strong>.</p>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;">
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cliente:</td><td style="padding:4px 0;font-weight:600;">{template_vars.get('Nombre_Cliente', client_name)}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cotización:</td><td style="padding:4px 0;">{project.get('quote_number','')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Integrador:</td><td style="padding:4px 0;">{template_vars.get('Integrador', '—')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Sucursal:</td><td style="padding:4px 0;">{template_vars.get('Nombre_Sucursal', '—')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cajas:</td><td style="padding:4px 0;">{template_vars.get('Cantidad_Cajas', '—')}</td></tr>
</table>
<h3 style="color:#2c3e50;margin-top:20px;">Bancos y Productos</h3>
{template_vars.get('Matriz_Bancos_Productos', '')}
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#999;font-size:12px;">Correo automático de MegaNexus Gestor.</p></div>"""
    elif target == "bank_client":
        # === Notificación Única (Cliente + Banco) para proyectos Single de un solo banco ===
        client = None
        client_id = project.get("client_id")
        if client_id:
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        client_name = project.get("client_name", "Cliente")

        to_list = []
        # Emails del cliente
        if client:
            contacts = client.get("contacts", [])
            if contacts:
                primary_email = contacts[0].get("email", "")
                if primary_email and "@" in primary_email:
                    to_list.append(primary_email)
            for c in contacts[1:]:
                c_email = c.get("email", "")
                if c_email and "@" in c_email and c_email not in to_list:
                    to_list.append(c_email)
            if not to_list:
                top_email = client.get("email", "")
                if top_email and "@" in top_email:
                    to_list.append(top_email)

        # Emails del banco
        bank = await db.banks.find_one({"name": bank_name}, {"_id": 0})
        if not bank:
            bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
        if bank:
            main_email = bank.get("contact_email", "")
            if main_email and "@" in main_email and main_email not in to_list:
                to_list.append(main_email)
            for c in bank.get("contacts", []):
                c_email = c.get("email", "")
                if c_email and "@" in c_email and c_email not in to_list:
                    to_list.append(c_email)

        entity_label = f"Cliente + Banco ({client_name} / {bank_name})"

        # Bank-specific products + client RIF para la plantilla combinada
        bank_products = list(project.get("implementation_matrix", {}).get(bank_name, {}).keys())
        template_vars["bank_name"] = bank_name
        template_vars["bank_products"] = ", ".join(bank_products)
        if client:
            template_vars["client_rif"] = client.get("rif", client.get("tax_id", ""))

        template = await db.email_templates.find_one({"template_id": "project_notify_bank_client"}, {"_id": 0})
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "{bank_name} — {Nombre_Cliente} — {project_number}"), template_vars)
            subject = f"[{prefix_label}] {raw_subject}"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            # Fallback: combina datos del cliente y banco
            products_html = "".join(f"<li>{p}</li>" for p in bank_products)
            subject = f"[{prefix_label}] {bank_name} — {client_name} — {project.get('project_number', '')}"
            html = f"""<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;margin:0 auto;">
<h2 style="color:#2c3e50;">[{prefix_label}] Implementación {bank_name} — {client_name}</h2>
{f'<p><strong>Ticket:</strong> {ticket}</p>' if ticket else ''}
<p>Proyecto <strong>{project.get('project_number','')}</strong></p>
<h3 style="color:#2c3e50;">Productos del Banco</h3>
<ul>{products_html}</ul>
{template_vars.get('Matriz_Bancos_Productos', '')}
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#999;font-size:12px;">Correo automático de MegaNexus Gestor.</p></div>"""
    else:
        # === DATA BINDING CORRECTO: extraer emails del banco ===
        bank = await db.banks.find_one({"name": bank_name}, {"_id": 0})
        if not bank:
            bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
        to_list = []
        if bank:
            # Email principal del banco
            main_email = bank.get("contact_email", "")
            if main_email and "@" in main_email:
                to_list.append(main_email)
            # Contactos del banco
            contacts = bank.get("contacts", [])
            for c in contacts:
                c_email = c.get("email", "")
                if c_email and "@" in c_email and c_email not in to_list:
                    to_list.append(c_email)

        if not to_list:
            to_list = []  # Sin destinatarios → frontend avisará

        entity_label = f"Banco ({bank_name})"

        # Bank-specific products for the matrix
        bank_products = list(project.get("implementation_matrix", {}).get(bank_name, {}).keys())
        template_vars["bank_name"] = bank_name
        template_vars["bank_products"] = ", ".join(bank_products)

        # Siempre usar plantilla del DB
        template = await db.email_templates.find_one({"template_id": "project_notify_bank"}, {"_id": 0})
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "{bank_name} — {project_number}"), template_vars)
            subject = f"[{prefix_label}] {raw_subject}"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            products_html = "".join(f"<li>{p}</li>" for p in bank_products)
            subject = f"[{prefix_label}] {bank_name} — {project.get('project_number', '')}"
            html = f"""<div style="font-family:Arial,sans-serif;width:95%;max-width:900px;margin:0 auto;">
<h2 style="color:#2c3e50;">[{prefix_label}] {bank_name}</h2>
{f'<p><strong>Ticket:</strong> {ticket}</p>' if ticket else ''}
<p>Estimados contactos de <strong>{bank_name}</strong>,</p>
<p>Proyecto <strong>{project.get('project_number','')}</strong> para <strong>{template_vars.get('Nombre_Cliente', project.get('client_name',''))}</strong>.</p>
<table style="border-collapse:collapse;margin:12px 0;font-size:13px;font-family:Arial,sans-serif;">
<tr><td style="padding:4px 12px 4px 0;color:#666;">Contacto Principal:</td><td style="padding:4px 0;">{template_vars.get('Contacto_Principal', '—')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Integrador:</td><td style="padding:4px 0;">{template_vars.get('Integrador', '—')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Sucursal:</td><td style="padding:4px 0;">{template_vars.get('Nombre_Sucursal', '—')}</td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#666;">Cajas:</td><td style="padding:4px 0;">{template_vars.get('Cantidad_Cajas', '—')}</td></tr>
</table>
<h3 style="color:#2c3e50;">Productos del Banco</h3>
<ul>{products_html}</ul>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
<p style="color:#999;font-size:12px;">Correo automático de MegaNexus Gestor.</p></div>"""

    return {"to_list": to_list, "subject": subject, "html": html, "entity_label": entity_label, "prefix": prefix_label}


async def _send_sequential_notification(project_id: str, target: str, bank_name: Optional[str], authorization: str, level: str = None, additional_recipients: Optional[List[str]] = None, custom_html: Optional[str] = None, custom_subject: Optional[str] = None, to_override: Optional[List[str]] = None):
    """Lógica de notificaciones con prefijos dinámicos por conteo de envíos.
    
    El cuerpo del correo siempre viene de la plantilla configurada.
    El asunto se prefija automáticamente:
      Envío 1: [Primer Envío]
      Envío 2: [Primer Recordatorio]
      Envío 3: [Segundo Recordatorio]
      Envío 4+: [Tercer Recordatorio]
    """
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    notification_history = project.get("notification_history", {})

    # Determinar clave de historial
    if target == "client":
        history_key = "client"
    elif target == "bank_client":
        # Para notificación única, el conteo se basa en el historial del banco
        history_key = f"bank_{bank_name}"
    else:
        history_key = f"bank_{bank_name}"

    # Obtener historial para esta entidad
    entity_history = notification_history.get(history_key, [])
    send_count = len(entity_history)  # Cuántas veces se ha enviado antes

    # Para bancos: verificar que cliente tenga al menos un envío
    if target == "bank":
        client_history = notification_history.get("client", [])
        if not client_history:
            raise HTTPException(status_code=400, detail="Debe notificar al cliente primero")
        matrix = project.get("implementation_matrix", {})
        if bank_name not in matrix:
            raise HTTPException(status_code=404, detail=f"Banco '{bank_name}' no encontrado en la matriz")

    # Para bank_client: validar que el banco exista en la matriz
    if target == "bank_client":
        matrix = project.get("implementation_matrix", {})
        if bank_name not in matrix:
            raise HTTPException(status_code=404, detail=f"Banco '{bank_name}' no encontrado en la matriz")

    # Determinar el prefijo basado en conteo
    prefix_idx = min(send_count, len(NOTIFICATION_PREFIXES) - 1)
    prefix_label = NOTIFICATION_PREFIXES[prefix_idx]

    # Resolver variables del proyecto
    template_vars = await resolve_project_template_vars(project)

    # Construir email con plantilla + prefijo dinámico
    email_data = await _resolve_notification_email(project, target, bank_name, send_count, template_vars)
    # Si el usuario seleccionó destinatarios manualmente desde el panel, sustituir TO
    if to_override:
        valid_to = [e.strip() for e in to_override if e and '@' in e]
        if valid_to:
            to_list = valid_to
        else:
            to_list = email_data["to_list"]
    else:
        to_list = email_data["to_list"]
    subject = custom_subject if custom_subject else email_data["subject"]
    html = custom_html if custom_html else email_data["html"]
    entity_label = email_data["entity_label"]

    # CRITICAL: Re-apply variable replacement on custom_html (user may have inserted variables in editor)
    if custom_html:
        html = _render_vars(html, template_vars)
    if custom_subject:
        subject = _render_vars(subject, template_vars)

    # Process base64 images → upload to storage for email compatibility
    html = await _replace_base64_images(html, current_user.get("user_id", "system"))

    email_result = await send_email(
        to=to_list, subject=subject, html=html,
        action=f"notification_{target}_{prefix_label.replace(' ', '_').lower()}",
        quote_id=project.get("quote_id"), quote_number=project.get("quote_number"),
        cc=additional_recipients,
    )

    # CC list for logging
    cc_list = [e for e in (additional_recipients or []) if e and e.strip() and '@' in e]

    # Registrar en historial
    entry = {
        "level": prefix_label,
        "send_number": send_count + 1,
        "sent_at": now,
        "sent_by": user_name,
        "recipients": to_list,
        "cc": cc_list,
        "subject": subject,
        "email_status": email_result.get("status"),
    }
    entity_history.append(entry)
    notification_history[history_key] = entity_history

    # Para bank_client: registrar el envío también en el historial del cliente
    if target == "bank_client":
        client_history_copy = notification_history.get("client", [])
        client_entry = {**entry, "combined_with_bank": bank_name}
        client_history_copy.append(client_entry)
        notification_history["client"] = client_history_copy

    update_set = {"notification_history": notification_history, "updated_at": now}

    # Primer envío al cliente desbloquea la matriz
    if target == "client" and send_count == 0:
        update_set["client_notified"] = True
        update_set["client_notified_at"] = now
        update_set["client_notified_by"] = user_name

    # Notificación Única (Cliente + Banco) también desbloquea la matriz
    if target == "bank_client":
        if not project.get("client_notified"):
            update_set["client_notified"] = True
            update_set["client_notified_at"] = now
            update_set["client_notified_by"] = user_name
        # Registrar en bank_notifications (compat)
        if send_count == 0:
            bank_notifications = project.get("bank_notifications", {})
            bank_notifications[bank_name] = {"notified_at": now, "notified_by": user_name, "products": list(project.get("implementation_matrix", {}).get(bank_name, {}).keys()), "email_status": email_result.get("status")}
            update_set["bank_notifications"] = bank_notifications

    # Primer envío al banco registra en bank_notifications (compat)
    if target == "bank" and send_count == 0:
        bank_notifications = project.get("bank_notifications", {})
        bank_notifications[bank_name] = {"notified_at": now, "notified_by": user_name, "products": list(project.get("implementation_matrix", {}).get(bank_name, {}).keys()), "email_status": email_result.get("status")}
        update_set["bank_notifications"] = bank_notifications

    await db.projects.update_one({"project_id": project_id}, {"$set": update_set})

    # Auto-registrar en bitácora
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": f"[{prefix_label}] {entity_label} — {subject}",
        "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "notification",
        "email_detail": {
            "subject": subject,
            "recipients": to_list,
            "html_content": html,
            "level": prefix_label,
            "send_number": send_count + 1,
            "target": target,
            "bank_name": bank_name,
            "sent_at": now,
        }
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    # Push notification (evento #8 Banco notificado en proyecto)
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="bank_notified_in_project",
            title=f"Banco {bank_name} notificado",
            message=f"Proyecto {project.get('project_number','')} · Nivel {prefix_label} · Target: {target}",
            context={
                "assignee_user_id": project.get("assigned_to_user_id"),
                "sede": project.get("client_sede"),
            },
            link=f"/projects/{project_id}",
            project_id=project_id,
        )
    except Exception as e:
        logger.warning(f"[notify] bank_notified failed: {e}")

    return {
        "message": f"[{prefix_label}] enviada a {entity_label} ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "level": prefix_label,
        "send_number": send_count + 1,
        "target": target,
        "bank_name": bank_name,
        "recipients": to_list,
    }



# ==================== PREVIEW ENDPOINTS ====================

class PreviewNotificationRequest(BaseModel):
    target: str  # "client" or "bank"
    bank_name: Optional[str] = None
    to_override: Optional[List[str]] = None  # destinatarios manuales seleccionados


@router.post("/projects/{project_id}/preview-notification")
async def preview_notification(project_id: str, body: PreviewNotificationRequest, authorization: Optional[str] = Header(None)):
    """Vista previa de la próxima notificación de proyecto (prefijo automático por conteo)."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Calcular conteo de envíos anteriores
    notification_history = project.get("notification_history", {})
    history_key = "client" if body.target == "client" else f"bank_{body.bank_name}"
    entity_history = notification_history.get(history_key, [])
    send_count = len(entity_history)

    # Resolver variables del proyecto
    template_vars = await resolve_project_template_vars(project)

    # Construir email (sin enviar) con prefijo basado en conteo
    email_data = await _resolve_notification_email(project, body.target, body.bank_name, send_count, template_vars)

    # Si hay destinatarios manuales, sustituir el TO en la respuesta
    to_list = email_data["to_list"]
    if body.to_override:
        valid_to = [e.strip() for e in body.to_override if e and '@' in e]
        if valid_to:
            to_list = valid_to

    # Determinar próximo prefijo
    prefix_idx = min(send_count, len(NOTIFICATION_PREFIXES) - 1)

    return {
        "subject": email_data["subject"],
        "html": email_data["html"],
        "recipients": to_list,
        "entity_label": email_data["entity_label"],
        "prefix": NOTIFICATION_PREFIXES[prefix_idx],
        "send_number": send_count + 1,
        "variables": {k: v for k, v in template_vars.items() if k != "Matriz_Bancos_Productos"},
        "matrix_html": template_vars.get("Matriz_Bancos_Productos", ""),
    }


class PreviewAdhocRequest(BaseModel):
    subject: str
    message: str
    include_matrix: bool = False


@router.post("/projects/{project_id}/preview-adhoc-email")
async def preview_adhoc_email(project_id: str, body: PreviewAdhocRequest, authorization: Optional[str] = Header(None)):
    """Vista previa de un correo ad-hoc con variables del proyecto resueltas."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Resolver variables del proyecto
    template_vars = await resolve_project_template_vars(project)

    # Renderizar asunto y mensaje con variables
    rendered_subject = _render_vars(body.subject, template_vars)
    rendered_message = _render_vars(body.message, template_vars)

    ticket = project.get("ticket_number", "")
    ticket_label = f"[Ticket {ticket}] " if ticket else ""

    message_html = rendered_message.replace("\n", "<br>")
    matrix_section = ""
    if body.include_matrix:
        matrix_section = f"<hr>{template_vars.get('Matriz_Bancos_Productos', '')}"

    html = f"""<div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        <p>{message_html}</p>
        {matrix_section}
        <hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | {f'Ticket: {ticket} | ' if ticket else ''}Cliente: {template_vars.get('Nombre_Cliente', project.get("client_name", ""))}</p>
    </div>"""

    return {
        "subject": f"{ticket_label}{rendered_subject}",
        "html": html,
        "variables": {k: v for k, v in template_vars.items() if k != "Matriz_Bancos_Productos"},
    }


@router.get("/projects/{project_id}/template-variables")
async def get_project_template_variables(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener las variables resueltas de un proyecto (para mostrar en el editor)."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    template_vars = await resolve_project_template_vars(project)
    return {
        "variables": {k: v for k, v in template_vars.items() if k != "Matriz_Bancos_Productos"},
        "matrix_html": template_vars.get("Matriz_Bancos_Productos", ""),
        "available_tags": [
            {"key": "Nombre_Cliente", "label": "Nombre del Cliente", "source": "Clientes.razon_social"},
            {"key": "Contacto_Principal", "label": "Contacto Principal", "source": "Contactos.nombre_apellido"},
            {"key": "Datos_Contacto", "label": "Datos del Contacto (nombre, tel, email)", "source": "Contactos.full_info"},
            {"key": "Nombre_Sucursal", "label": "Nombre de Sucursal", "source": "Sucursales.nombre"},
            {"key": "Cantidad_Cajas", "label": "Cantidad de Cajas", "source": "Sucursales.nro_cajas"},
            {"key": "Integrador", "label": "Integrador", "source": "Proyecto.integrador"},
            {"key": "Matriz_Bancos_Productos", "label": "Tabla Bancos/Productos (HTML)", "source": "Proyecto.implementation_matrix"},
            {"key": "project_number", "label": "Nro. Proyecto", "source": "Proyecto.project_number"},
            {"key": "quote_number", "label": "Nro. Cotización", "source": "Proyecto.quote_number"},
            {"key": "ticket_number", "label": "Nro. Ticket", "source": "Proyecto.ticket_number"},
            {"key": "client_rif", "label": "RIF del Cliente", "source": "Clientes.rif"},
            {"key": "quote_type", "label": "Tipo de Cotización", "source": "Proyecto.quote_type"},
            {"key": "integrator_app_name", "label": "Aplicativo", "source": "Proyecto.integrator_app_name"},
            {"key": "pinpad_model", "label": "Modelo Pinpad", "source": "Proyecto.pinpad_model"},
            {"key": "assigned_to", "label": "Asignado a", "source": "Proyecto.assigned_to_name"},
            {"key": "Aplicativo_Integracion", "label": "Aplicativo de Integración", "source": "Proyecto.integrator_app_name"},
            {"key": "Nombre_Implementador", "label": "Nombre del Implementador", "source": "Usuarios.nombre (asignado)"},
            {"key": "Correo_Implementador", "label": "Correo del Implementador", "source": "Usuarios.email (asignado)"},
            {"key": "Telefono_Implementador", "label": "Teléfono del Implementador", "source": "Usuarios.phone (asignado)"},
            {"key": "Lista_VTID", "label": "Lista de Terminales Virtuales (HTML)", "source": "Proyecto.vtids"},
            {"key": "Modelo_Seriales_Equipos", "label": "Tabla de Modelo y Seriales de Equipos", "source": "Proyecto.equipments"},
            {"key": "Datos_Contacto", "label": "Datos completos del Contacto Principal", "source": "Clientes.contacts[0]"},
        ],
    }



@router.get("/projects/{project_id}/notification-history")
async def get_notification_history(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener historial de notificaciones secuenciales."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "notification_history": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project.get("notification_history", {})


@router.get("/projects/{project_id}/rollup")
async def get_project_rollup(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener el avance de un proyecto (single o multitienda)."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if project.get("project_type") == "multistore":
        return _calculate_rollup_progress(project)
    return _calculate_single_progress(project)


# ==================== IMPLEMENTATION MATRIX ====================

@router.put("/projects/{project_id}/matrix/phase")
async def update_matrix_phase(project_id: str, phase_update: PhaseUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar una fase de la matriz de implementación (solo proyectos single)"""
    current_user = await get_current_user(authorization)
    if phase_update.phase not in IMPLEMENTATION_PHASES:
        raise HTTPException(status_code=400, detail=f"Fase inválida. Válidas: {IMPLEMENTATION_PHASES}")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Permisos: Solo implementador asignado, su supervisor, o admin
    user_role = current_user.get("role", "")
    user_id = current_user.get("user_id", "")
    assigned_to = project.get("assigned_to", "")
    if user_role != "admin":
        user_supervisor_id = current_user.get("supervisor_id", "")
        # Check if user is the assigned implementer
        is_implementer = user_id == assigned_to
        # Check if user is the supervisor of the assigned implementer
        is_supervisor = False
        if assigned_to:
            assigned_user = await db.users.find_one({"user_id": assigned_to}, {"_id": 0, "supervisor_id": 1})
            if assigned_user and assigned_user.get("supervisor_id") == user_id:
                is_supervisor = True
        if not is_implementer and not is_supervisor:
            raise HTTPException(status_code=403, detail="Solo el implementador asignado o su supervisor pueden editar la matriz")

    # Bloquear edición manual en multitienda
    if project.get("project_type") == "multistore":
        raise HTTPException(status_code=400, detail="La matriz principal de un proyecto multitienda es de solo lectura.")

    if not project.get("client_notified"):
        raise HTTPException(status_code=400, detail="Debe notificar al cliente primero antes de actualizar la matriz")

    matrix = project.get("implementation_matrix", {})
    bank_key = phase_update.bank_name
    if bank_key not in matrix:
        matrix[bank_key] = {}
    if phase_update.product_name not in matrix[bank_key]:
        matrix[bank_key][phase_update.product_name] = {}

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Obtener estado anterior para bitácora
    old_data = matrix[bank_key][phase_update.product_name].get(phase_update.phase, {})
    old_processed = old_data.get("processed", 0)

    # Determinar cantidades
    expected = phase_update.expected if phase_update.expected is not None else old_data.get("expected", 0)
    processed = phase_update.processed if phase_update.processed is not None else old_data.get("processed", 0)
    is_completed = processed >= expected and expected > 0

    matrix[bank_key][phase_update.product_name][phase_update.phase] = {
        "completed": is_completed,
        "expected": expected,
        "processed": processed,
        "updated_at": now,
        "updated_by": user_name
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"implementation_matrix": matrix, "updated_at": now}}
    )

    # Bitácora automática si cambió la cantidad procesada
    if processed != old_processed:
        pct = round((processed / expected * 100)) if expected > 0 else 0
        bitacora_text = f"[Matriz] {phase_update.phase} — {bank_key}/{phase_update.product_name}: {processed}/{expected} ({pct}%). Actualizado por {user_name}."
        bitacora_entry = {
            "entry_id": f"log_{uuid.uuid4().hex[:8]}",
            "text": bitacora_text,
            "execution_date": now[:10],
            "created_at": now,
            "created_by": user_name,
            "auto_generated": True,
        }
        await db.projects.update_one(
            {"project_id": project_id},
            {"$push": {"bitacora": bitacora_entry}}
        )

    # Recalcular progreso
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        progress = _calculate_single_progress(updated_project)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"rollup_progress": progress}}
        )

    # Push notification (evento #9 Fase de matriz completada) solo si completed=True
    if is_completed:
        try:
            from services.notification_service import notify as _push_notify
            await _push_notify(
                event_type="matrix_phase_completed",
                title=f"Fase completada: {phase_update.phase}",
                message=f"Proyecto {updated_project.get('project_number','') if updated_project else ''} · Banco {bank_key} · Producto {phase_update.product_name}",
                context={
                    "assignee_user_id": (updated_project or {}).get("assigned_to_user_id"),
                    "sede": (updated_project or {}).get("client_sede"),
                },
                link=f"/projects/{project_id}",
                project_id=project_id,
            )
        except Exception as e:
            logger.warning(f"[notify] matrix_phase_completed failed: {e}")

    return {
        "message": "Fase actualizada",
        "bank": bank_key,
        "product": phase_update.product_name,
        "phase": phase_update.phase,
        "expected": expected,
        "processed": processed,
        "completed": is_completed
    }


@router.put("/projects/{project_id}/stores/{store_id}/matrix/phase")
async def update_store_matrix_phase(project_id: str, store_id: str, phase_update: PhaseUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar una fase de la matriz de implementación de una tienda específica"""
    current_user = await get_current_user(authorization)
    if phase_update.phase not in STORE_PHASES:
        raise HTTPException(status_code=400, detail=f"Fase inválida para tienda. Válidas: {STORE_PHASES}")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if project.get("project_type") != "multistore":
        raise HTTPException(status_code=400, detail="Este proyecto no es multitienda")

    # Hard stop: verificar que el cliente fue notificado
    if not project.get("client_notified"):
        raise HTTPException(status_code=400, detail="Debe notificar al cliente primero antes de actualizar la matriz")

    stores = project.get("stores", [])
    store_idx = next((i for i, s in enumerate(stores) if s.get("store_id") == store_id), None)
    if store_idx is None:
        raise HTTPException(status_code=404, detail="Tienda no encontrada en el proyecto")

    store = stores[store_idx]
    matrix = store.get("implementation_matrix", {})
    bank_key = phase_update.bank_name
    if bank_key not in matrix:
        matrix[bank_key] = {}
    if phase_update.product_name not in matrix[bank_key]:
        matrix[bank_key][phase_update.product_name] = {}

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Obtener estado anterior
    old_data = matrix[bank_key][phase_update.product_name].get(phase_update.phase, {})
    old_processed = old_data.get("processed", 0)

    expected = phase_update.expected if phase_update.expected is not None else old_data.get("expected", store.get("box_count", 0))
    processed = phase_update.processed if phase_update.processed is not None else old_data.get("processed", 0)
    is_completed = processed >= expected and expected > 0

    matrix[bank_key][phase_update.product_name][phase_update.phase] = {
        "completed": is_completed,
        "expected": expected,
        "processed": processed,
        "updated_at": now,
        "updated_by": user_name
    }

    # Actualizar la tienda dentro del array de stores
    await db.projects.update_one(
        {"project_id": project_id, "stores.store_id": store_id},
        {"$set": {
            "stores.$.implementation_matrix": matrix,
            "updated_at": now
        }}
    )

    # Bitácora automática si cambió la cantidad procesada
    if processed != old_processed:
        pct = round((processed / expected * 100)) if expected > 0 else 0
        store_name = store.get("name", store_id)
        bitacora_text = f"[Matriz Tienda {store_name}] {phase_update.phase} — {bank_key}/{phase_update.product_name}: {processed}/{expected} ({pct}%). Por {user_name}."
        bitacora_entry = {
            "entry_id": f"log_{uuid.uuid4().hex[:8]}",
            "text": bitacora_text,
            "execution_date": now[:10],
            "created_at": now,
            "created_by": user_name,
            "auto_generated": True,
        }
        await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    # Recalcular roll-up de la matriz principal
    # Re-leer el proyecto con la tienda actualizada
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        rollup = _calculate_rollup_progress(updated_project)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"rollup_progress": rollup, "updated_at": now}}
        )

    return {"message": "Fase de tienda actualizada", "store_id": store_id, "bank": bank_key, "product": phase_update.product_name, "phase": phase_update.phase, "completed": phase_update.completed}


class BatchMatrixUpdate(BaseModel):
    phase: str
    bank_name: str
    product_name: str
    store_ids: list
    reason: Optional[str] = ""


@router.post("/projects/{project_id}/matrix/batch-update")
async def batch_update_multistore_matrix(project_id: str, body: BatchMatrixUpdate, authorization: Optional[str] = Header(None)):
    """Actualización masiva: para cada tienda seleccionada marca processed=expected en (fase+banco+producto).
    Solo proyectos multitienda. Registra UNA entrada en bitácora con todo el detalle."""
    current_user = await get_current_user(authorization)
    if body.phase not in STORE_PHASES:
        raise HTTPException(status_code=400, detail=f"Fase inválida. Válidas: {STORE_PHASES}")
    if not body.store_ids:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos una tienda")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if project.get("project_type") != "multistore":
        raise HTTPException(status_code=400, detail="Solo proyectos multitienda")
    if not project.get("client_notified"):
        raise HTTPException(status_code=400, detail="Debe notificar al cliente primero antes de actualizar la matriz")

    # Permisología: admin, implementador asignado o supervisor
    user_id = current_user.get("user_id", "")
    user_role = current_user.get("role", "")
    cargo = current_user.get("cargo", "")
    is_admin = user_role == "admin"
    is_assigned = user_id == project.get("implementer_user_id") or user_id == project.get("implementer_id")
    is_supervisor = cargo in ("Gerente", "Director", "Supervisor")
    if not (is_admin or is_assigned or is_supervisor):
        raise HTTPException(status_code=403, detail="Solo el implementador asignado o su supervisor puede ejecutar actualización masiva")

    stores = project.get("stores", [])
    stores_by_id = {s.get("store_id"): s for s in stores}
    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")

    processed_stores = []
    for sid in body.store_ids:
        store = stores_by_id.get(sid)
        if not store:
            continue
        matrix = store.get("implementation_matrix", {})
        if body.bank_name not in matrix:
            matrix[body.bank_name] = {}
        if body.product_name not in matrix[body.bank_name]:
            matrix[body.bank_name][body.product_name] = {}

        old_data = matrix[body.bank_name][body.product_name].get(body.phase, {})
        expected = old_data.get("expected", store.get("box_count", 0)) or store.get("box_count", 0)
        matrix[body.bank_name][body.product_name][body.phase] = {
            "completed": expected > 0,
            "expected": expected,
            "processed": expected,
            "updated_at": now,
            "updated_by": user_name,
            "batch_updated": True,
        }
        await db.projects.update_one(
            {"project_id": project_id, "stores.store_id": sid},
            {"$set": {"stores.$.implementation_matrix": matrix, "updated_at": now}}
        )
        processed_stores.append({"store_id": sid, "name": store.get("name", sid), "expected": expected})

    if not processed_stores:
        raise HTTPException(status_code=404, detail="Ninguna de las tiendas seleccionadas existe en el proyecto")

    # Recalcular rollup
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        rollup = _calculate_rollup_progress(updated_project)
        await db.projects.update_one({"project_id": project_id}, {"$set": {"rollup_progress": rollup, "updated_at": now}})

    # Bitácora única con detalle completo
    reason = (body.reason or "Recepción de información masiva por parte del Banco/Cliente").strip()
    store_names = [s["name"] for s in processed_stores]
    total_procesado = sum(s["expected"] for s in processed_stores)
    bitacora_text = (
        f"[ACTUALIZACIÓN MASIVA DE ESTATUS]\n"
        f"Fase actualizada: {body.phase}\n"
        f"Producto: {body.product_name}\n"
        f"Ente bancario: {body.bank_name}\n"
        f"Tiendas procesadas ({len(processed_stores)}): {', '.join(store_names)}\n"
        f"Total de unidades completadas: {total_procesado}\n"
        f"Motivo: {reason}\n"
        f"Usuario responsable: {user_name}"
    )
    bitacora_entry = {
        "entry_id": f"batch_{uuid.uuid4().hex[:10]}",
        "text": bitacora_text,
        "execution_date": now[:10],
        "created_at": now,
        "created_by": user_name,
        "auto_generated": True,
        "entry_type": "batch_matrix_update",
        "batch_meta": {
            "phase": body.phase,
            "bank_name": body.bank_name,
            "product_name": body.product_name,
            "reason": reason,
            "stores": processed_stores,
            "total_stores": len(processed_stores),
        },
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    return {
        "message": f"Actualización masiva aplicada a {len(processed_stores)} tienda(s)",
        "stores_processed": processed_stores,
        "bitacora_entry_id": bitacora_entry["entry_id"],
    }


@router.put("/projects/{project_id}/implementation-fields")
async def update_implementation_fields(project_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar campos de Integrador y Aplicativo en el proyecto."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    update_set = {}
    if "integrator_name" in body:
        update_set["integrator_name"] = body["integrator_name"]
    if "application_name" in body:
        update_set["integrator_app_name"] = body["application_name"]
    if "integrator_app_name" in body:
        update_set["integrator_app_name"] = body["integrator_app_name"]
    if "box_count" in body:
        update_set["box_count"] = body["box_count"]
    if update_set:
        update_set["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.projects.update_one({"project_id": project_id}, {"$set": update_set})
    return {"message": "Campos actualizados", **update_set}


@router.post("/projects/{project_id}/implementation-serials")
async def add_implementation_serials(project_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Agregar seriales de hardware en la vista de implementación."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    serials = body.get("serials", [])
    if not serials:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos un serial")

    existing = project.get("implementation_serials", [])
    new_serials = [s.strip() for s in serials if s.strip() and s.strip() not in existing]
    all_serials = existing + new_serials

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"implementation_serials": all_serials, "updated_at": now}}
    )

    # Bitácora automática
    if new_serials:
        bitacora_entry = {
            "entry_id": f"log_{uuid.uuid4().hex[:8]}",
            "text": f"[Seriales] Se cargaron {len(new_serials)} serial(es) en implementación: {', '.join(new_serials[:5])}{'...' if len(new_serials) > 5 else ''}. Por {user_name}.",
            "execution_date": now[:10],
            "created_at": now,
            "created_by": user_name,
            "auto_generated": True,
        }
        await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    return {"message": f"{len(new_serials)} serial(es) agregados", "total_serials": len(all_serials), "serials": all_serials}


@router.post("/projects/{project_id}/implementation-serials/upload")
async def upload_serials_file(project_id: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Cargar seriales desde archivo Excel (.xlsx/.csv/.txt)."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    content = await file.read()
    serials = []
    fname = (file.filename or "").lower()

    if fname.endswith('.xlsx') or fname.endswith('.xls'):
        import openpyxl
        import io
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is not None:
                    val = str(cell).strip()
                    if val and len(val) >= 3 and len(val) <= 60:
                        serials.append(val)
                    break  # Solo primera columna
        wb.close()
    else:
        text = content.decode('utf-8', errors='replace')
        for line in text.split('\n'):
            val = line.split(',')[0].split(';')[0].split('\t')[0].strip()
            if val and len(val) >= 3 and len(val) <= 60:
                serials.append(val)

    # Filtrar headers
    if serials and serials[0].lower() in ('serial', 'seriales', 'numero', 'terminal', 'nro'):
        serials = serials[1:]

    if not serials:
        raise HTTPException(status_code=400, detail="No se encontraron seriales válidos en el archivo")

    existing = project.get("implementation_serials", [])
    new_serials = [s for s in serials if s not in existing]
    all_serials = existing + new_serials

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"implementation_serials": all_serials, "updated_at": now}}
    )

    if new_serials:
        bitacora_entry = {
            "entry_id": f"log_{uuid.uuid4().hex[:8]}",
            "text": f"[Seriales Excel] Se cargaron {len(new_serials)} serial(es): {', '.join(new_serials[:5])}{'...' if len(new_serials) > 5 else ''}. Por {user_name}.",
            "execution_date": now[:10],
            "created_at": now,
            "created_by": user_name,
            "auto_generated": True,
        }
        await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    return {"message": f"{len(new_serials)} serial(es) cargados desde archivo", "total_serials": len(all_serials), "serials": all_serials}


@router.delete("/projects/{project_id}/implementation-serials/{serial}")
async def remove_implementation_serial(project_id: str, serial: str, authorization: Optional[str] = Header(None)):
    """Eliminar un serial de implementación."""
    current_user = await get_current_user(authorization)
    await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"implementation_serials": serial}}
    )
    return {"message": f"Serial {serial} eliminado"}




# ==================== BITÁCORA ====================

@router.post("/projects/{project_id}/bitacora")
async def add_bitacora_entry(project_id: str, entry: BitacoraEntry, authorization: Optional[str] = Header(None)):
    """Agregar entrada a la bitácora del proyecto"""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": entry.text,
        "execution_date": entry.execution_date,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$push": {"bitacora": bitacora_entry}}
    )

    return bitacora_entry


@router.get("/projects/{project_id}/bitacora")
async def get_bitacora(project_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "bitacora": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project.get("bitacora", [])


# ==================== ADHOC EMAIL ====================

@router.post("/projects/{project_id}/send-adhoc-email")
async def send_adhoc_email(
    project_id: str,
    recipients: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    matrix_html: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None)
):
    """Enviar email ad-hoc desde un proyecto. Auto-registra en bitácora."""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Parse recipients
    try:
        to_list = json.loads(recipients)
        if not isinstance(to_list, list) or not to_list:
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Destinatarios inválidos. Envíe un array JSON de emails.")

    if not subject.strip():
        raise HTTPException(status_code=400, detail="El asunto es obligatorio")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    ticket = project.get("ticket_number", "")
    ticket_label = f"[Ticket {ticket}] " if ticket else ""

    # Guardar adjuntos
    saved_files = []
    upload_dir = f"/app/backend/uploads/adhoc_emails/{project_id}"
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            with open(file_path, "wb") as fp:
                fp.write(content)
            saved_files.append({
                "filename": f.filename,
                "url": f"/uploads/adhoc_emails/{project_id}/{safe_name}",
                "size": len(content),
                "content_type": f.content_type,
            })

    # Construir email HTML
    message_html = message.replace("\n", "<br>")
    full_subject = f"{ticket_label}{subject}"
    # Incluir matrix_html si fue enviada (separada del conteo de caracteres)
    matrix_section = f"<hr>{matrix_html}" if matrix_html.strip() else ""
    html = f"""
    <div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        <p>{message_html}</p>
        {matrix_section}
        {f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Ticket: {ticket} | Cliente: {project.get("client_name", "")}</p>' if ticket else f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Cliente: {project.get("client_name", "")}</p>'}
    </div>
    """

    # Resolve variables in adhoc emails too
    template_vars = await resolve_project_template_vars(project)
    html = _render_vars(html, template_vars)
    full_subject = _render_vars(full_subject, template_vars)

    # Process base64 images → upload to storage
    html = await _replace_base64_images(html, current_user.get("user_id", "system"))

    email_result = await send_email(
        to=to_list,
        subject=full_subject,
        html=html,
        action="adhoc_project_email",
        quote_id=project.get("quote_id"),
        quote_number=project.get("quote_number"),
    )

    # Auto-registrar en bitácora con contenido completo
    attachments_text = f" ({len(saved_files)} adjunto(s))" if saved_files else ""
    matrix_tag = " [+Matriz]" if matrix_html.strip() else ""
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": f"[Otras Notificaciones] {subject}{attachments_text}{matrix_tag} → {', '.join(to_list)}",
        "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "adhoc_email",
        "email_detail": {
            "subject": full_subject,
            "recipients": to_list,
            "message": message,
            "html_content": html,
            "attachments": saved_files,
            "has_matrix": bool(matrix_html.strip()),
            "sent_at": now,
        }
    }
    await db.projects.update_one(
        {"project_id": project_id},
        {"$push": {"bitacora": bitacora_entry}}
    )

    return {
        "message": f"Correo enviado a {len(to_list)} destinatario(s) ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "recipients": to_list,
        "subject": full_subject,
        "attachments_count": len(saved_files),
        "bitacora_entry_id": bitacora_entry["entry_id"],
    }


# ==================== SUGGESTED CONTACTS ====================

@router.get("/projects/{project_id}/suggested-contacts")
async def get_suggested_contacts(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener contactos sugeridos del Cliente y Bancos del proyecto."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    contacts = []

    # Contactos del cliente
    client_id = project.get("client_id")
    if client_id:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if client:
            client_label = project.get("client_name", client.get("fantasy_name", "Cliente"))
            # Email principal del cliente (si existe)
            if client.get("email"):
                contacts.append({"email": client["email"], "label": f"Cliente: {client_label}", "source": "client"})
            # Contactos CRM del cliente (array contacts)
            for c in client.get("contacts", []):
                if c.get("email"):
                    name = c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Contacto"
                    contacts.append({"email": c["email"], "label": f"Cliente ({name})", "source": "client"})
            # Contactos legacy (contact1, contact2)
            for key in ["contact1", "contact2"]:
                legacy = client.get(key)
                if legacy and isinstance(legacy, dict) and legacy.get("email"):
                    contacts.append({"email": legacy["email"], "label": f"Cliente ({legacy.get('name', key)})", "source": "client"})

    # Contactos de bancos del proyecto
    matrix = project.get("implementation_matrix", {})
    for bank_name in matrix:
        bank = await db.banks.find_one({"name": bank_name}, {"_id": 0})
        if not bank:
            bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
        if bank:
            # Array contacts (nuevo modelo multi-contacto) - prioridad
            bank_contacts_arr = bank.get("contacts") or []
            if bank_contacts_arr:
                for c in bank_contacts_arr:
                    if c.get("email"):
                        full = c.get("full_name") or f"{c.get('first_name','')} {c.get('last_name','')}".strip() or "Contacto"
                        ctype = c.get("contact_type") or "Otro"
                        position = c.get("position") or ""
                        label = f"Banco {bank_name} ({full}{' · ' + position if position else ''} · {ctype})"
                        contacts.append({
                            "email": c["email"],
                            "label": label,
                            "source": "bank",
                            "bank_name": bank_name,
                            "contact_type": ctype,
                            "name": full,
                        })
            else:
                # Fallback legacy contact_email
                if bank.get("contact_email"):
                    contact_name = bank.get("contact_name") or "Contacto"
                    contacts.append({
                        "email": bank["contact_email"],
                        "label": f"Banco {bank_name} ({contact_name})",
                        "source": "bank",
                        "bank_name": bank_name,
                        "contact_type": "Principal",
                        "name": contact_name,
                    })

    # Deduplicar por email
    seen_emails = set()
    unique_contacts = []
    for c in contacts:
        if c["email"] not in seen_emails:
            seen_emails.add(c["email"])
            unique_contacts.append(c)

    return unique_contacts


# ==================== EMAIL TEMPLATES (CRUD) ====================

## Email template routes removed — handled by seed_and_templates.py



@router.post("/projects/migrate-matrix")
async def migrate_project_matrices(authorization: Optional[str] = Header(None)):
    """Reconstruye las matrices de implementación de todos los proyectos
    usando solo los items 'additional' (medios de pago seleccionados por banco)."""
    await get_current_user(authorization)
    
    projects = await db.projects.find({}, {"_id": 0}).to_list(None)
    updated = 0
    
    for p in projects:
        services = p.get("services", [])
        new_matrix = {}
        for item in services:
            if item.get("item_type") != "additional":
                continue
            bn = item.get("bank_name", "")
            name = item.get("item_name", "")
            if not bn or not name:
                continue
            if bn not in new_matrix:
                new_matrix[bn] = {}
            if name not in new_matrix[bn]:
                new_matrix[bn][name] = {}
        
        if new_matrix != p.get("implementation_matrix", {}):
            await db.projects.update_one(
                {"project_id": p["project_id"]},
                {"$set": {"implementation_matrix": new_matrix}}
            )
            updated += 1
    
    return {"message": f"Matrices actualizadas: {updated} proyectos"}


# ==================== TICKET NUMBER (SECURITY LOCK) ====================

@router.put("/projects/{project_id}/ticket")
async def update_ticket_number(project_id: str, body: TicketNumberUpdate, authorization: Optional[str] = Header(None)):
    """Permite al implementador registrar el Número de Ticket para desbloquear la ejecución del proyecto."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    ticket = body.ticket_number.strip()
    if not ticket:
        raise HTTPException(status_code=400, detail="El Número de Ticket es obligatorio")

    # Verificar unicidad del ticket
    existing = await db.projects.find_one({"ticket_number": ticket, "project_id": {"$ne": project_id}}, {"_id": 0, "project_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"El Número de Ticket '{ticket}' ya está asignado a otro proyecto")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": f"Ticket registrado: {ticket} (por {user_name})",
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"ticket_number": ticket, "unblocked_at": now, "updated_at": now}, "$push": {"notes": note}}
    )

    return {"message": f"Ticket '{ticket}' registrado exitosamente", "ticket_number": ticket}


# ==================== VTID GENERATOR (PER-STORE) ====================

@router.post("/projects/{project_id}/vtids/generate")
async def generate_vtids(project_id: str, body: VTIDGenerateRequest, authorization: Optional[str] = Header(None)):
    """Genera VTIDs secuenciales. Si store_id se provee, genera para esa sucursal."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    prefix = body.prefix.strip().upper()
    if not prefix:
        raise HTTPException(status_code=400, detail="El prefijo es obligatorio")
    if len(prefix) > 10:
        raise HTTPException(status_code=400, detail="El prefijo no puede superar 10 caracteres")

    stores = project.get("stores", [])
    is_multistore = project.get("project_type") == "multistore" and len(stores) > 0

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    start = max(body.start_number, 1)

    if is_multistore:
        # MULTITIENDA: generar VTIDs por sucursal
        if not body.store_id:
            raise HTTPException(status_code=400, detail="Para proyectos multitienda, debe especificar la sucursal (store_id)")
        store = next((s for s in stores if s.get("store_id") == body.store_id), None)
        if not store:
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        total_boxes = store.get("box_count", 0)
        if total_boxes <= 0:
            raise HTTPException(status_code=400, detail=f"La sucursal '{store.get('name', '')}' no tiene cajas registradas.")

        vtids = []
        for i in range(total_boxes):
            num = start + i
            vtids.append({
                "vtid_id": f"vtid_{uuid.uuid4().hex[:8]}",
                "code": f"{prefix}{str(num).zfill(3)}",
                "sequence": num,
            })

        # Update store's vtids within the stores array
        await db.projects.update_one(
            {"project_id": project_id, "stores.store_id": body.store_id},
            {"$set": {
                "stores.$.vtids": vtids,
                "stores.$.vtid_prefix": prefix,
                "stores.$.vtid_generated_at": now,
                "stores.$.vtid_generated_by": user_name,
                "updated_at": now,
            }}
        )
        store_name = store.get("name", body.store_id)
        note_text = f"VTIDs generados para {store_name} ({len(vtids)}): {prefix}{str(start).zfill(3)} → {prefix}{str(start + total_boxes - 1).zfill(3)} (por {user_name})"
    else:
        # TIENDA ÚNICA: generar a nivel de proyecto
        services = project.get("services", [])
        total_boxes = max((s.get("cantidad_cajas", 0) for s in services), default=0) if services else 0
        if total_boxes <= 0:
            raise HTTPException(status_code=400, detail="El proyecto no tiene cajas registradas.")

        vtids = []
        for i in range(total_boxes):
            num = start + i
            vtids.append({
                "vtid_id": f"vtid_{uuid.uuid4().hex[:8]}",
                "code": f"{prefix}{str(num).zfill(3)}",
                "sequence": num,
            })

        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {
                "vtids": vtids,
                "vtid_prefix": prefix,
                "vtid_generated_at": now,
                "vtid_generated_by": user_name,
                "updated_at": now,
            }}
        )
        note_text = f"VTIDs generados ({len(vtids)}): {prefix}{str(start).zfill(3)} → {prefix}{str(start + total_boxes - 1).zfill(3)} (por {user_name})"

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": note_text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"notes": note}})

    return {
        "message": f"{len(vtids)} VTIDs generados exitosamente",
        "vtids": vtids,
        "total": len(vtids),
        "prefix": prefix,
        "store_id": body.store_id,
    }


@router.get("/projects/{project_id}/vtids")
async def get_vtids(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene todos los VTIDs del proyecto (globales + por sucursal)."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    stores = project.get("stores", [])
    store_vtids = []
    for s in stores:
        if s.get("vtids"):
            store_vtids.append({
                "store_id": s.get("store_id"),
                "store_name": s.get("name", ""),
                "box_count": s.get("box_count", 0),
                "vtids": s.get("vtids", []),
                "prefix": s.get("vtid_prefix", ""),
                "generated_at": s.get("vtid_generated_at"),
                "generated_by": s.get("vtid_generated_by"),
            })

    return {
        "vtids": project.get("vtids", []),
        "prefix": project.get("vtid_prefix", ""),
        "generated_at": project.get("vtid_generated_at"),
        "generated_by": project.get("vtid_generated_by"),
        "store_vtids": store_vtids,
    }


@router.delete("/projects/{project_id}/vtids")
async def delete_vtids(project_id: str, store_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Elimina VTIDs. Si store_id se provee, solo elimina los de esa sucursal."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    if store_id:
        store = next((s for s in project.get("stores", []) if s.get("store_id") == store_id), None)
        store_name = store.get("name", store_id) if store else store_id
        await db.projects.update_one(
            {"project_id": project_id, "stores.store_id": store_id},
            {"$unset": {
                "stores.$.vtids": "",
                "stores.$.vtid_prefix": "",
                "stores.$.vtid_generated_at": "",
                "stores.$.vtid_generated_by": "",
            }, "$set": {"updated_at": now}}
        )
        note_text = f"VTIDs de {store_name} eliminados (por {user_name})"
    else:
        await db.projects.update_one(
            {"project_id": project_id},
            {
                "$set": {"updated_at": now},
                "$unset": {"vtids": "", "vtid_prefix": "", "vtid_generated_at": "", "vtid_generated_by": ""},
            }
        )
        note_text = f"VTIDs eliminados (por {user_name})"

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": note_text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"notes": note}})

    return {"message": "VTIDs eliminados exitosamente"}


# ==================== IMAGE UPLOAD & SERVING ====================

MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp",
}


@router.post("/projects/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Upload image to object storage and return public URL."""
    current_user = await get_current_user(authorization)
    user_id = current_user.get("user_id", "unknown")

    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "png"
    if ext not in MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Formato no soportado. Use: {', '.join(MIME_TYPES.keys())}")

    content_type = MIME_TYPES.get(ext, "application/octet-stream")
    data = await file.read()

    if len(data) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="La imagen excede el tamaño máximo de 10MB")

    file_id = uuid.uuid4().hex[:12]
    storage_path = f"{os.environ.get('APP_NAME', 'meganexus')}/email-images/{user_id}/{file_id}.{ext}"

    try:
        result = put_object(storage_path, data, content_type)
    except Exception as e:
        logger.error(f"Image upload failed: {e}")
        raise HTTPException(status_code=500, detail="Error al subir imagen al servidor")

    # Store reference
    await db.uploaded_images.insert_one({
        "image_id": file_id,
        "storage_path": result.get("path", storage_path),
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Return the serving URL (goes through our backend)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    public_url = f"{base_url}/api/projects/images/{file_id}.{ext}"

    return {"url": public_url, "image_id": file_id, "filename": file.filename}


@router.get("/projects/images/{filename}")
async def serve_image(filename: str):
    """Serve uploaded image without auth (for email rendering)."""
    file_id = filename.split(".")[0] if "." in filename else filename
    record = await db.uploaded_images.find_one({"image_id": file_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    try:
        data, ct = get_object(record["storage_path"])
    except Exception as e:
        logger.error(f"Image download failed: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener imagen")

    return Response(content=data, media_type=record.get("content_type", ct))


@router.post("/projects/process-email-images")
async def process_email_images(authorization: Optional[str] = Header(None)):
    """Process HTML content: replace base64 images with uploaded URLs."""
    await get_current_user(authorization)
    return {"message": "Use send endpoints - base64 images are processed automatically"}


async def _replace_base64_images(html: str, user_id: str) -> str:
    """Replace all base64 image data URIs in HTML with uploaded URLs."""
    base64_pattern = re.compile(r'src="data:image/(jpeg|jpg|png|gif|webp);base64,([^"]+)"')
    matches = list(base64_pattern.finditer(html))

    if not matches:
        return html

    base_url = os.environ.get("REACT_APP_BACKEND_URL", "")

    for match in matches:
        ext = match.group(1)
        if ext == "jpeg":
            ext = "jpg"
        b64_data = match.group(2)

        try:
            img_data = base64.b64decode(b64_data)
        except Exception:
            continue

        file_id = uuid.uuid4().hex[:12]
        storage_path = f"{os.environ.get('APP_NAME', 'meganexus')}/email-images/{user_id}/{file_id}.{ext}"
        content_type = MIME_TYPES.get(ext, "image/png")

        try:
            result = put_object(storage_path, img_data, content_type)
            await db.uploaded_images.insert_one({
                "image_id": file_id,
                "storage_path": result.get("path", storage_path),
                "original_filename": f"pasted_{file_id}.{ext}",
                "content_type": content_type,
                "size": result.get("size", len(img_data)),
                "uploaded_by": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            public_url = f"{base_url}/api/projects/images/{file_id}.{ext}"
            html = html.replace(match.group(0), f'src="{public_url}"')
        except Exception as e:
            logger.warning(f"Failed to upload base64 image: {e}")

    return html


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar un proyecto. Solo administradores."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar proyectos")
    
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "project_id": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    
    await db.projects.delete_one({"project_id": project_id})
    logging.info(f"Proyecto {project_id} eliminado por {current_user.get('email')}")
    return {"message": "Proyecto eliminado exitosamente"}
