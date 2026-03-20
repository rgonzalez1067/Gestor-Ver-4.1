"""Route module: projects.py - Módulo de Proyectos (Post-Venta)"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging
import os
import json

from config import db, get_current_user
from models import PROJECT_STATUSES
from services.email_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)

IMPLEMENTATION_PHASES = ["Notificado", "Recibido", "Configurado", "Testeado", "En Producción"]
STORE_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]  # Sin "Notificado" para tiendas
PROJECT_PRIORITIES = ["Alta", "Media", "Normal"]


class ProjectStatusUpdate(BaseModel):
    new_status: str
    note: Optional[str] = None
    change_date: Optional[str] = None


class ProjectAssign(BaseModel):
    assigned_to_user_id: str
    ticket_number: str
    estimated_delivery_date: Optional[str] = None
    reassignment_comment: Optional[str] = None
    reassignment_date: Optional[str] = None


class PhaseUpdate(BaseModel):
    bank_name: str
    product_name: str
    phase: str
    completed: bool


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


NOTIFICATION_LEVELS = [
    "Primera Comunicación",
    "Primer Recordatorio",
    "Segundo Recordatorio",
    "Tercer Recordatorio",
]

NOTIFICATION_SUBJECTS = {
    "Primera Comunicación": "Notificación de Implementación",
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
    blocked = await db.projects.count_documents({"status": "Detenido por Cliente/Banco"})
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

    # Validar ticket_number obligatorio
    ticket = assignment.ticket_number.strip()
    if not ticket:
        raise HTTPException(status_code=400, detail="El Número de Ticket es obligatorio")

    # Verificar unicidad del ticket (excepto si es el mismo proyecto reasignado)
    existing = await db.projects.find_one({"ticket_number": ticket, "project_id": {"$ne": project_id}}, {"_id": 0, "project_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"El Número de Ticket '{ticket}' ya está asignado a otro proyecto")

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
        "ticket_number": ticket,
        "status": "Asignado / En Proceso",
        "updated_at": now,
    }
    if assignment.estimated_delivery_date:
        update_data["estimated_delivery_date"] = assignment.estimated_delivery_date

    previous_assignee = project.get("assigned_to_name", "")
    is_reassignment = bool(previous_assignee)
    
    note_text = f"Proyecto {'reasignado' if is_reassignment else 'asignado'} a {implementer_name}. Ticket: {ticket}."
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

    # Notificar al implementador (con ticket en asunto)
    impl_email = implementer.get("email")
    if impl_email:
        try:
            await send_email(
                to=[impl_email],
                subject=f"[Ticket {ticket}] Proyecto Asignado: {project.get('project_number', project_id)}",
                html=f"<h2>Nuevo proyecto asignado</h2><p><strong>Ticket:</strong> {ticket}</p><p><strong>Proyecto:</strong> {project.get('project_number')}</p><p><strong>Cliente:</strong> {project.get('client_name')} ({project.get('client_rif')})</p><p><strong>Asignado por:</strong> {assigner_name}</p>",
                action="assign_project",
                quote_id=project.get("quote_id")
            )
        except Exception as e:
            logger.warning(f"Error notificando implementador: {e}")

    return {"message": "Proyecto asignado exitosamente", "assigned_to": implementer_name, "ticket_number": ticket}


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
    target: str  # "client" or "bank"
    bank_name: Optional[str] = None
    level: str  # one of NOTIFICATION_LEVELS


@router.post("/projects/{project_id}/send-notification")
async def send_sequential_notification(project_id: str, body: SequentialNotifyRequest, authorization: Optional[str] = Header(None)):
    """Enviar notificación secuencial (cualquier nivel) a cliente o banco."""
    return await _send_sequential_notification(project_id, body.target, body.bank_name, authorization, body.level)


async def _send_sequential_notification(project_id: str, target: str, bank_name: Optional[str], authorization: str, level: str = None):
    """Lógica unificada de notificaciones secuenciales."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    ticket = project.get("ticket_number", "")
    ticket_label = f"[Ticket {ticket}] " if ticket else ""
    notification_history = project.get("notification_history", {})

    # Determinar clave de historial
    history_key = "client" if target == "client" else f"bank_{bank_name}"

    # Obtener historial para esta entidad
    entity_history = notification_history.get(history_key, [])
    executed_levels = [h["level"] for h in entity_history]

    # Determinar nivel actual
    if level is None:
        # Auto-detectar: primer nivel no ejecutado
        level = None
        for lvl in NOTIFICATION_LEVELS:
            if lvl not in executed_levels:
                level = lvl
                break
        if level is None:
            raise HTTPException(status_code=400, detail="Todos los niveles de notificación ya fueron enviados")
    else:
        if level not in NOTIFICATION_LEVELS:
            raise HTTPException(status_code=400, detail=f"Nivel inválido. Válidos: {NOTIFICATION_LEVELS}")

    # Validar secuencialidad
    level_idx = NOTIFICATION_LEVELS.index(level)
    for i in range(level_idx):
        if NOTIFICATION_LEVELS[i] not in executed_levels:
            raise HTTPException(status_code=400, detail=f"Debe ejecutar '{NOTIFICATION_LEVELS[i]}' antes de '{level}'")

    if level in executed_levels:
        raise HTTPException(status_code=400, detail=f"'{level}' ya fue enviada")

    # Para bancos: verificar que cliente tenga al menos la Primera Comunicación
    if target == "bank":
        client_history = notification_history.get("client", [])
        if not client_history:
            raise HTTPException(status_code=400, detail="Debe notificar al cliente primero")
        matrix = project.get("implementation_matrix", {})
        if bank_name not in matrix:
            raise HTTPException(status_code=404, detail=f"Banco '{bank_name}' no encontrado en la matriz")

    # Construir email según target
    subject_suffix = NOTIFICATION_SUBJECTS.get(level, level)

    if target == "client":
        client = None
        client_id = project.get("client_id")
        if client_id:
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        client_email = client.get("email", "") if client else ""
        client_name = project.get("client_name", "Cliente")
        to_list = [client_email] if client_email else ["cliente@ejemplo.com"]

        subject = f"{ticket_label}{subject_suffix}: {project.get('project_number', '')}"
        html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;">
<h2>{subject_suffix}</h2>
{f'<p><strong>Ticket:</strong> {ticket}</p>' if ticket else ''}
<p>Estimado/a <strong>{client_name}</strong>,</p>
<p>Le informamos sobre el estado de su proyecto de implementación <strong>{project.get('project_number','')}</strong>.</p>
<p><strong>Nivel:</strong> {level}</p>
<ul><li>Cotización: {project.get('quote_number','')}</li><li>Tipo: {project.get('quote_type','')}</li><li>Pinpad: {project.get('pinpad_model','—')}</li></ul>
<!-- PLACEHOLDER: Plantilla HTML aprobada -->
<hr><p style="color:#999;font-size:12px;">Correo automático de MegaNexus.</p></div>"""
        entity_label = f"Cliente ({client_name})"
    else:
        bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
        bank_email = ""
        if bank:
            contacts = bank.get("contacts", [])
            if contacts:
                bank_email = contacts[0].get("email", "")
        to_list = [bank_email] if bank_email else [f"contacto@{bank_name.lower().replace(' ', '')}.com"]

        products = list(project.get("implementation_matrix", {}).get(bank_name, {}).keys())
        products_html = "".join(f"<li>{p}</li>" for p in products)
        subject = f"{ticket_label}{subject_suffix}: {bank_name} — {project.get('project_number', '')}"
        html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;">
<h2>{subject_suffix} — {bank_name}</h2>
{f'<p><strong>Ticket:</strong> {ticket}</p>' if ticket else ''}
<p>Estimados contactos de <strong>{bank_name}</strong>,</p>
<p>Proyecto <strong>{project.get('project_number','')}</strong> para <strong>{project.get('client_name','')}</strong>.</p>
<p><strong>Nivel:</strong> {level}</p>
<p><strong>Productos:</strong></p><ul>{products_html}</ul>
<ul><li>Integrador: {project.get('integrator_name','—')}</li><li>Aplicativo: {project.get('integrator_app_name','—')}</li><li>Pinpad: {project.get('pinpad_model','—')}</li></ul>
<!-- PLACEHOLDER: Plantilla HTML aprobada para bancos -->
<hr><p style="color:#999;font-size:12px;">Correo automático de MegaNexus.</p></div>"""
        entity_label = f"Banco ({bank_name})"

    email_result = await send_email(
        to=to_list, subject=subject, html=html,
        action=f"notification_{target}_{level.replace(' ', '_').lower()}",
        quote_id=project.get("quote_id"), quote_number=project.get("quote_number"),
    )

    # Registrar en historial
    entry = {"level": level, "sent_at": now, "sent_by": user_name, "recipients": to_list, "subject": subject, "email_status": email_result.get("status")}
    entity_history.append(entry)
    notification_history[history_key] = entity_history

    update_set = {"notification_history": notification_history, "updated_at": now}

    # Primera Comunicación al cliente desbloquea la matriz
    if target == "client" and level == "Primera Comunicación":
        update_set["client_notified"] = True
        update_set["client_notified_at"] = now
        update_set["client_notified_by"] = user_name

    # Primera Comunicación al banco registra en bank_notifications (compat)
    if target == "bank" and level == "Primera Comunicación":
        bank_notifications = project.get("bank_notifications", {})
        bank_notifications[bank_name] = {"notified_at": now, "notified_by": user_name, "products": list(project.get("implementation_matrix", {}).get(bank_name, {}).keys()), "email_status": email_result.get("status")}
        update_set["bank_notifications"] = bank_notifications

    await db.projects.update_one({"project_id": project_id}, {"$set": update_set})

    # Auto-registrar en bitácora con contenido completo
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": f"[{level}] {entity_label} — {subject}",
        "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "notification",
        "email_detail": {
            "subject": subject,
            "recipients": to_list,
            "html_content": html,
            "level": level,
            "target": target,
            "bank_name": bank_name,
            "sent_at": now,
        }
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    return {
        "message": f"{level} enviada a {entity_label} ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "level": level,
        "target": target,
        "bank_name": bank_name,
        "recipients": to_list,
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

    # Bloquear edición manual en multitienda
    if project.get("project_type") == "multistore":
        raise HTTPException(status_code=400, detail="La matriz principal de un proyecto multitienda es de solo lectura. Actualice las matrices de las tiendas.")

    # Hard stop: verificar que el cliente fue notificado
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

    matrix[bank_key][phase_update.product_name][phase_update.phase] = {
        "completed": phase_update.completed,
        "updated_at": now,
        "updated_by": user_name
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"implementation_matrix": matrix, "updated_at": now}}
    )

    # Recalcular progreso para proyecto single
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        progress = _calculate_single_progress(updated_project)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"rollup_progress": progress}}
        )

    return {"message": "Fase actualizada", "bank": bank_key, "product": phase_update.product_name, "phase": phase_update.phase, "completed": phase_update.completed}


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

    matrix[bank_key][phase_update.product_name][phase_update.phase] = {
        "completed": phase_update.completed,
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
    if len(message) > 1000:
        raise HTTPException(status_code=400, detail="El mensaje no puede exceder 1000 caracteres")

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
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <p>{message_html}</p>
        {f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Ticket: {ticket} | Cliente: {project.get("client_name", "")}</p>' if ticket else f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Cliente: {project.get("client_name", "")}</p>'}
    </div>
    """

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
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": f"[Otras Notificaciones] {subject}{attachments_text} → {', '.join(to_list)}",
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

    # Contacto del cliente
    client_id = project.get("client_id")
    if client_id:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if client:
            if client.get("email"):
                contacts.append({"email": client["email"], "label": f"Cliente: {project.get('client_name', '')}", "source": "client"})
            for c in client.get("contacts", []):
                if c.get("email"):
                    contacts.append({"email": c["email"], "label": f"Cliente ({c.get('name', '')})", "source": "client"})

    # Contactos de bancos del proyecto
    matrix = project.get("implementation_matrix", {})
    for bank_name in matrix:
        bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
        if bank:
            for c in bank.get("contacts", []):
                if c.get("email"):
                    contacts.append({"email": c["email"], "label": f"Banco {bank_name} ({c.get('name', '')})", "source": "bank"})

    return contacts


# ==================== EMAIL TEMPLATES (CRUD) ====================

@router.get("/email-templates")
async def list_email_templates(authorization: Optional[str] = Header(None)):
    """Listar todas las plantillas de email."""
    await get_current_user(authorization)
    templates = await db.email_templates.find({}, {"_id": 0}).to_list(None)
    return templates


@router.post("/email-templates")
async def create_email_template(authorization: Optional[str] = Header(None), name: str = Form(...), subject: str = Form(...), body: str = Form(...)):
    """Crear plantilla de email (solo admin)."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar plantillas")

    now = datetime.now(timezone.utc).isoformat()
    template = {
        "template_id": f"tpl_{uuid.uuid4().hex[:8]}",
        "name": name.strip(),
        "subject": subject.strip(),
        "body": body,
        "created_by": current_user.get("user_id"),
        "created_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "created_at": now,
        "updated_at": now,
    }
    await db.email_templates.insert_one(template)
    template.pop("_id", None)
    return template


@router.put("/email-templates/{template_id}")
async def update_email_template(template_id: str, authorization: Optional[str] = Header(None), name: str = Form(...), subject: str = Form(...), body_content: str = Form(...)):
    """Actualizar plantilla de email (solo admin)."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar plantillas")

    result = await db.email_templates.update_one(
        {"template_id": template_id},
        {"$set": {"name": name.strip(), "subject": subject.strip(), "body": body_content, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return {"message": "Plantilla actualizada"}


@router.delete("/email-templates/{template_id}")
async def delete_email_template(template_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar plantilla de email (solo admin)."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar plantillas")

    result = await db.email_templates.delete_one({"template_id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return {"message": "Plantilla eliminada"}



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
