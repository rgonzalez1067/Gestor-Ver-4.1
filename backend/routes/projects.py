"""Route module: projects.py - Módulo de Proyectos (Post-Venta)"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging

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
                to=impl_email,
                subject=f"Proyecto Asignado: {project.get('project_number', project_id)}",
                html_content=f"<h2>Nuevo proyecto asignado</h2><p><strong>Proyecto:</strong> {project.get('project_number')}</p><p><strong>Cliente:</strong> {project.get('client_name')} ({project.get('client_rif')})</p><p><strong>Asignado por:</strong> {assigner_name}</p>",
                quote_id=project.get("quote_id")
            )
        except Exception as e:
            logger.warning(f"Error notificando implementador: {e}")

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
    """Notificar al cliente (Hito 1 - Fase Cero). Desbloquea la matriz."""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if project.get("client_notified"):
        raise HTTPException(status_code=400, detail="El cliente ya fue notificado para este proyecto")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Buscar email del cliente
    client = None
    client_id = project.get("client_id")
    if client_id:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})

    client_email = client.get("email", "") if client else ""
    client_name = project.get("client_name", "Cliente")

    # Construir email (placeholder para plantilla HTML futura)
    subject = f"MegaNexus — Notificación de Implementación: {project.get('project_number', '')}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2>Notificación de Implementación</h2>
        <p>Estimado/a <strong>{client_name}</strong>,</p>
        <p>Le informamos que su proyecto de implementación <strong>{project.get('project_number', '')}</strong>
        ha sido iniciado.</p>
        <p>Detalles del proyecto:</p>
        <ul>
            <li>Cotización: {project.get('quote_number', '')}</li>
            <li>Tipo: {project.get('quote_type', '')}</li>
            <li>Modelo Pinpad: {project.get('pinpad_model', '—')}</li>
        </ul>
        <!-- PLACEHOLDER: Contenido HTML de plantilla aprobada -->
        <hr>
        <p style="color: #999; font-size: 12px;">Este es un correo automático de MegaNexus.</p>
    </div>
    """

    to_list = [client_email] if client_email else ["cliente@ejemplo.com"]
    email_result = await send_email(
        to=to_list,
        subject=subject,
        html=html,
        action="notify_client_implementation",
        quote_id=project.get("quote_id"),
        quote_number=project.get("quote_number"),
    )

    # Registrar notificación en el proyecto
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {
            "client_notified": True,
            "client_notified_at": now,
            "client_notified_by": user_name,
            "updated_at": now,
        }}
    )

    return {
        "message": f"Cliente notificado exitosamente ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "client_email": to_list[0],
        "client_notified": True,
    }


@router.post("/projects/{project_id}/notify-bank")
async def notify_bank(project_id: str, body: BankNotifyRequest, authorization: Optional[str] = Header(None)):
    """Notificación consolidada a un banco (Hito 2). Un email por banco con todos sus productos."""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Verificar hard stop: cliente debe estar notificado primero
    if not project.get("client_notified"):
        raise HTTPException(status_code=400, detail="Debe notificar al cliente primero (Hito 1)")

    bank_name = body.bank_name
    matrix = project.get("implementation_matrix", {})
    if bank_name not in matrix:
        raise HTTPException(status_code=404, detail=f"Banco '{bank_name}' no encontrado en la matriz")

    # Verificar si ya fue notificado
    bank_notifications = project.get("bank_notifications", {})
    if bank_name in bank_notifications:
        raise HTTPException(status_code=400, detail=f"El banco '{bank_name}' ya fue notificado")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Agregar productos del banco
    products = list(matrix[bank_name].keys())

    # Buscar contactos del banco
    bank = await db.banks.find_one({"bank_name": bank_name}, {"_id": 0})
    bank_email = ""
    if bank:
        contacts = bank.get("contacts", [])
        if contacts:
            bank_email = contacts[0].get("email", "")

    # Construir email consolidado (placeholder para plantilla HTML futura)
    products_html = "".join(f"<li>{p}</li>" for p in products)
    subject = f"MegaNexus — Notificación de Implementación: {bank_name} — {project.get('project_number', '')}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px;">
        <h2>Notificación de Implementación — {bank_name}</h2>
        <p>Estimados contactos de <strong>{bank_name}</strong>,</p>
        <p>Se ha iniciado la implementación del proyecto <strong>{project.get('project_number', '')}</strong>
        para el cliente <strong>{project.get('client_name', '')}</strong>.</p>
        <p><strong>Productos asociados a {bank_name}:</strong></p>
        <ul>{products_html}</ul>
        <p><strong>Datos técnicos:</strong></p>
        <ul>
            <li>Cotización: {project.get('quote_number', '')}</li>
            <li>Integrador: {project.get('integrator_name', '—')}</li>
            <li>Aplicativo: {project.get('integrator_app_name', '—')}</li>
            <li>Modelo Pinpad: {project.get('pinpad_model', '—')}</li>
        </ul>
        <!-- PLACEHOLDER: Contenido HTML de plantilla aprobada para bancos -->
        <hr>
        <p style="color: #999; font-size: 12px;">Este es un correo automático de MegaNexus.</p>
    </div>
    """

    to_list = [bank_email] if bank_email else [f"contacto@{bank_name.lower().replace(' ', '')}.com"]
    email_result = await send_email(
        to=to_list,
        subject=subject,
        html=html,
        action="notify_bank_implementation",
        quote_id=project.get("quote_id"),
        quote_number=project.get("quote_number"),
    )

    # Registrar notificación del banco
    bank_notifications[bank_name] = {
        "notified_at": now,
        "notified_by": user_name,
        "products": products,
        "email_status": email_result.get("status"),
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {
            "bank_notifications": bank_notifications,
            "updated_at": now,
        }}
    )

    return {
        "message": f"Banco '{bank_name}' notificado con {len(products)} producto(s) ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "bank_name": bank_name,
        "products_notified": products,
    }


@router.get("/projects/{project_id}/rollup")
async def get_project_rollup(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener el avance roll-up de un proyecto multitienda."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if project.get("project_type") != "multistore":
        raise HTTPException(status_code=400, detail="Solo aplicable a proyectos multitienda")
    return _calculate_rollup_progress(project)


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
