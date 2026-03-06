"""Route module: projects.py - Módulo de Proyectos (Post-Venta)"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import logging

from config import db, get_current_user
from models import PROJECT_STATUSES, CARGOS
from services.email_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)


class ProjectAssign(BaseModel):
    assigned_to_user_id: str
    estimated_delivery_date: Optional[str] = None


class ProjectStatusUpdate(BaseModel):
    new_status: str
    note: Optional[str] = None


class ProjectNoteCreate(BaseModel):
    text: str


# ==================== PROJECT ENDPOINTS ====================

@router.get("/projects")
async def get_projects(authorization: Optional[str] = Header(None)):
    """Obtener todos los proyectos"""
    await get_current_user(authorization)
    projects = await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return projects


@router.get("/projects/stats")
async def get_project_stats(authorization: Optional[str] = Header(None)):
    """Estadísticas de proyectos para el dashboard"""
    await get_current_user(authorization)
    total = await db.projects.count_documents({})
    pending = await db.projects.count_documents({"status": "Pendiente por Asignar"})
    in_progress = await db.projects.count_documents({"status": "Asignado / En Proceso"})
    blocked = await db.projects.count_documents({"status": "Detenido por Cliente/Banco"})
    completed = await db.projects.count_documents({"status": "Finalizado / Producción"})
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "blocked": blocked,
        "completed": completed
    }


@router.get("/projects/{project_id}")
async def get_project(project_id: str, authorization: Optional[str] = Header(None)):
    """Obtener un proyecto por ID"""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.put("/projects/{project_id}/assign")
async def assign_project(project_id: str, assignment: ProjectAssign, authorization: Optional[str] = Header(None)):
    """Asignar un proyecto a un implementador"""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Buscar implementador
    implementer = await db.users.find_one({"user_id": assignment.assigned_to_user_id}, {"_id": 0})
    if not implementer:
        raise HTTPException(status_code=404, detail="Implementador no encontrado")

    implementer_name = f"{implementer.get('first_name', '')} {implementer.get('last_name', '')}".strip()
    now = datetime.now(timezone.utc).isoformat()

    update_data = {
        "assigned_to_user_id": assignment.assigned_to_user_id,
        "assigned_to_name": implementer_name,
        "assigned_by_user_id": current_user.get("user_id"),
        "assigned_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "assigned_at": now,
        "status": "Asignado / En Proceso",
        "updated_at": now,
    }
    if assignment.estimated_delivery_date:
        update_data["estimated_delivery_date"] = assignment.estimated_delivery_date

    # Agregar nota automática
    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": f"Proyecto asignado a {implementer_name}." + (f" Fecha estimada: {assignment.estimated_delivery_date}" if assignment.estimated_delivery_date else ""),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": update_data["assigned_by_name"],
        "created_at": now,
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_data, "$push": {"notes": note}}
    )

    # Notificar al implementador por email
    implementer_email = implementer.get("email")
    if implementer_email:
        try:
            subject = f"Nuevo Proyecto Asignado: {project.get('project_number', project_id)}"
            body = f"""
            <h2>Se le ha asignado un nuevo proyecto</h2>
            <p><strong>Proyecto:</strong> {project.get('project_number', project_id)}</p>
            <p><strong>Cliente:</strong> {project.get('client_name', '')} ({project.get('client_rif', '')})</p>
            <p><strong>Sede:</strong> {project.get('client_sede', '')}</p>
            <p><strong>Cotización de referencia:</strong> {project.get('quote_number', '')}</p>
            <p><strong>Asignado por:</strong> {update_data['assigned_by_name']}</p>
            {f"<p><strong>Fecha estimada de entrega:</strong> {assignment.estimated_delivery_date}</p>" if assignment.estimated_delivery_date else ""}
            """
            await send_email(to=implementer_email, subject=subject, html_content=body, quote_id=project.get("quote_id"))
        except Exception as e:
            logger.warning(f"Error enviando notificación al implementador: {e}")

    return {"message": "Proyecto asignado exitosamente", "assigned_to": implementer_name}


@router.put("/projects/{project_id}/status")
async def update_project_status(project_id: str, status_update: ProjectStatusUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar el estado de un proyecto"""
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

    # Nota automática
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    note_text = f"Estado cambiado a '{status_update.new_status}'"
    if status_update.note:
        note_text += f": {status_update.note}"
    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": note_text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_data, "$push": {"notes": note}}
    )

    return {"message": f"Estado actualizado a '{status_update.new_status}'", "new_status": status_update.new_status}


@router.post("/projects/{project_id}/notes")
async def add_project_note(project_id: str, note_data: ProjectNoteCreate, authorization: Optional[str] = Header(None)):
    """Agregar una nota a un proyecto"""
    current_user = await get_current_user(authorization)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": note_data.text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.projects.update_one(
        {"project_id": project_id},
        {"$push": {"notes": note}}
    )

    return note


@router.put("/projects/{project_id}/priority")
async def update_project_priority(project_id: str, priority: str, authorization: Optional[str] = Header(None)):
    """Actualizar la prioridad de un proyecto"""
    await get_current_user(authorization)

    if priority not in ["Baja", "Normal", "Alta", "Urgente"]:
        raise HTTPException(status_code=400, detail="Prioridad inválida")

    result = await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"priority": priority, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    return {"message": f"Prioridad actualizada a '{priority}'"}


@router.get("/projects/implementers/list")
async def get_implementers(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios que pueden ser asignados como implementadores"""
    await get_current_user(authorization)
    impl_cargos = ["Implementador", "Coordinador de Implementación", "Gerente de Implementación", "Técnico de Infraestructura"]
    users = await db.users.find(
        {"cargo": {"$in": impl_cargos}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
    ).to_list(100)
    # If no users with those cargos, return all users as fallback
    if not users:
        users = await db.users.find(
            {},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
        ).to_list(100)
    return users
