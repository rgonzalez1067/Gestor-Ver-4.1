"""Route module: projects.py - Módulo de Proyectos (Post-Venta)"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form, Query
from fastapi.responses import Response, FileResponse, StreamingResponse
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
from services.email_service import send_email, resolve_sender_for_area
from services.assignment_notifications import notify_project_assigned
from services.project_template_vars import resolve_project_template_vars
from services.object_storage import init_storage, put_object, get_object
from services.pdf_storage import save_pdf_dual

router = APIRouter()
logger = logging.getLogger(__name__)

IMPLEMENTATION_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]
STORE_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]  # Sin "Notificado" para tiendas
PROJECT_PRIORITIES = ["Alta", "Media", "Normal"]


class ProjectAssign(BaseModel):
    assigned_to_user_id: str
    estimated_delivery_date: Optional[str] = None
    reassignment_comment: Optional[str] = None
    reassignment_date: Optional[str] = None


class TicketNumberUpdate(BaseModel):
    ticket_number: str
    confirm_duplicate: bool = False


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


# ==================== MASTER OVERRIDE (Super-Admin) ====================
class BankProductsOverride(BaseModel):
    bank_name: str
    products: List[str] = []


class StoreProductsOverride(BaseModel):
    store_id: str
    banks_products: List[BankProductsOverride] = []


class MasterOverridePayload(BaseModel):
    # Campos escalares (texto libre)
    project_number: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    client_rif: Optional[str] = None
    client_sede: Optional[str] = None
    total_usd: Optional[float] = None
    total_bs: Optional[float] = None
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_model: Optional[str] = None
    server_name: Optional[str] = None
    ticket_number: Optional[str] = None
    # Dropdowns
    status: Optional[str] = None
    quote_type: Optional[str] = None
    sponsoring_bank_id: Optional[str] = None
    sponsoring_bank_name: Optional[str] = None
    sponsoring_processor_name: Optional[str] = None
    # Generador del Proyecto (usuario que originó la cotización). Se setea
    # manualmente por Admin para corregir/cargar proyectos antiguos o importados.
    generador_user_id: Optional[str] = None
    # Estructura relacional
    banks_products: Optional[List[BankProductsOverride]] = None  # proyectos single
    stores_products: Optional[List[StoreProductsOverride]] = None  # multitienda
    hardware: Optional[List[dict]] = None


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


def _compose_ticket_subject(ticket, subject: str) -> str:
    """Devuelve el asunto tal como lo definió el usuario, limpiando solo las
    variables fantasma '{...}' que no se resolvieron.

    NOTA: NO se agrega ningún prefijo automático (ej. '[Ticket N]'); el asunto
    imprime únicamente las variables que el usuario seleccionó en la plantilla.
    El parámetro `ticket` se mantiene por compatibilidad de firma."""
    subject = (subject or "").strip()
    subject = re.sub(r"\{[^{}]{0,60}\}", "", subject)
    subject = re.sub(r"\s{2,}", " ", subject).strip()
    return subject

NOTIFICATION_SUBJECTS = {
    "Primer Envío": "Notificación de Implementación",
    "Primer Recordatorio": "1er Recordatorio — Implementación",
    "Segundo Recordatorio": "2do Recordatorio — Implementación",
    "Tercer Recordatorio": "3er Recordatorio (Urgente) — Implementación",
}


# ==================== PROJECT ENDPOINTS ====================

async def _build_project_visibility_query(user: dict) -> dict:
    """Construye el filtro de visibilidad de la bandeja de Proyectos según rol/área.

    Reglas (Feb 2026):
      - Admin: todos.
      - Ejecutivo de Ventas Pyme (departamento='Ventas Pyme'): proyectos generados
        por el ÁREA Pyme (creados por cualquier usuario del departamento Ventas Pyme).
      - Ejecutivo de Ventas Corporativas (departamento='Ventas Corporativas'):
        proyectos propios (created_by_user_id) MÁS los de su sede CORP (client_segment).
      - Implementador (cargo='Implementador'): solo los proyectos donde figura como
        Implementador Asignado.
      - Resto (Coordinador/Gerente de Implementación, Directores, Operaciones,
        Administración, etc.): todos (comportamiento nativo sin alteración).
    """
    if user.get("role") == "admin":
        return {}
    cargo = (user.get("cargo") or "").strip()
    dept = (user.get("departamento") or "").strip()
    uid = user.get("user_id")

    if cargo == "Ejecutivo" and dept == "Ventas Pyme":
        pyme_users = await db.users.find(
            {"departamento": "Ventas Pyme"}, {"_id": 0, "user_id": 1}
        ).to_list(2000)
        pyme_ids = [u["user_id"] for u in pyme_users if u.get("user_id")]
        return {"created_by_user_id": {"$in": pyme_ids}}

    # Ventas Corporativas: visibilidad COLECTIVA del equipo. Cualquier miembro del
    # departamento "Ventas Corporativas" (tolerante a variantes) ve TODOS los
    # proyectos creados por cualquier integrante de su mismo equipo.
    if "ventas corporativ" in dept.lower():
        corp_users = await db.users.find(
            {"departamento": {"$regex": "ventas corporativ", "$options": "i"}},
            {"_id": 0, "user_id": 1}
        ).to_list(2000)
        corp_ids = [u["user_id"] for u in corp_users if u.get("user_id")]
        if uid and uid not in corp_ids:
            corp_ids.append(uid)
        return {"created_by_user_id": {"$in": corp_ids}}

    if cargo == "Implementador":
        return {"assigned_to_user_id": uid}

    # Resto de roles: sin restricción (gobernanza de Implementación intacta).
    return {}


@router.get("/projects")
async def get_projects(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    query = await _build_project_visibility_query(user)
    # PERFORMANCE: la grilla NO usa los arrays pesados (bitacora,
    # notification_history, status_history) — solo el detalle del proyecto
    # (GET /projects/{id}, que sí trae el doc completo). Excluirlos aquí reduce
    # el payload ~70% y evita que el listado se degrade a medida que crece la
    # bitácora. El enriquecimiento (PVV/métricas/SLA) no depende de estos campos.
    _list_projection = {"_id": 0, "bitacora": 0, "notification_history": 0, "status_history": 0}
    projects = await db.projects.find(query, _list_projection).sort("created_at", -1).to_list(1000)
    # Iter39: inyectar pvv_count para que la lista pueda mostrarlo / ordenarlo
    # sin un GET adicional por proyecto.
    from services.project_pvv import compute_project_pvv, compute_project_metrics
    from services.business_calendar import get_holiday_sets, business_days_between
    from services.project_sla_engine import sla_reference_date
    specific, recurring = await get_holiday_sets()
    today = datetime.now(timezone.utc).date()
    # Enriquecer con Nombre Jurídico y Grupo Económico del cliente para que el
    # filtro de "Cliente" del panel pueda buscar por RIF, Razón Social o Grupo.
    client_ids = list({p.get("client_id") for p in projects if p.get("client_id")})
    clients_map = {}
    if client_ids:
        async for c in db.clients.find(
            {"client_id": {"$in": client_ids}},
            {"_id": 0, "client_id": 1, "legal_name": 1, "fantasy_name": 1, "grupo_economico": 1, "rif": 1},
        ):
            clients_map[c["client_id"]] = c
    for p in projects:
        cl = clients_map.get(p.get("client_id")) or {}
        p["client_legal_name"] = cl.get("legal_name") or p.get("client_name") or ""
        p["client_economic_group"] = cl.get("grupo_economico") or ""
        p["pvv_count"] = compute_project_pvv(p)
        # Iter: métricas del Mini Tablero de Avance Operativo (físico + PVV).
        p["operational_metrics"] = compute_project_metrics(p)
        # Días HÁBILES desde la referencia SLA. En 'En Gestión' la referencia se
        # reinicia solo con acciones de interacción válidas (correo/avance matriz).
        entered = sla_reference_date(p)
        p["business_days_in_state"] = business_days_between(entered.date(), today, specific, recurring) if entered else 0
        # Cuenta regresiva (días HÁBILES) hasta la fecha estimada de entrada en
        # producción comprometida por el cliente. El panel muestra el aviso solo
        # cuando faltan <= 5 días hábiles (lo decide el frontend con este valor).
        # -1 = la fecha ya transcurrió; None = sin fecha registrada.
        p["production_days_left"] = None
        prod = (p.get("fecha_estimada_produccion") or "").strip()
        if prod:
            try:
                prod_date = datetime.fromisoformat(prod[:10]).date()
                if prod_date >= today:
                    p["production_days_left"] = business_days_between(today, prod_date, specific, recurring)
                else:
                    p["production_days_left"] = -1
            except Exception:
                pass
    return projects


def _user_sales_team(user: dict) -> Optional[str]:
    """Equipo comercial del usuario según su departamento: 'CORP', 'PYME' o None."""
    dept = (user.get("departamento") or "").strip().lower()
    if "ventas corporativ" in dept:
        return "CORP"
    if dept.startswith("ventas pyme") or "ventas pyme" in dept:
        return "PYME"
    return None


class CobroRecurrenteToggle(BaseModel):
    status: Optional[bool] = None  # si None → alterna el estado actual


@router.put("/projects/{project_id}/cobro-recurrente")
async def toggle_cobro_recurrente(project_id: str, body: CobroRecurrenteToggle, authorization: Optional[str] = Header(None)):
    """Indicador de Cobro Recurrente ($). Solo puede alternarlo un ADMIN, o un
    usuario del área de Ventas cuyo equipo (CORP/PyME) coincida con el equipo
    comercial origen del proyecto (client_segment). Persiste estado + usuario +
    timestamp (UTC)."""
    user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    project_team = (project.get("client_segment") or "PYME").strip().upper()
    if project_team not in ("CORP", "PYME"):
        project_team = "PYME"
    is_admin = (user.get("role") == "admin")
    user_team = _user_sales_team(user)
    allowed = is_admin or (user_team is not None and user_team == project_team)
    if not allowed:
        raise HTTPException(status_code=403, detail="Acción exclusiva para el equipo comercial asignado al proyecto")

    current = bool(project.get("cobro_recurrente_status", False))
    new_status = bool(body.status) if body and body.status is not None else (not current)
    full_name = (f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                 or user.get("name") or user.get("email") or "")
    updates = {
        "cobro_recurrente_status": new_status,
        "cobro_recurrente_by": user.get("user_id"),
        "cobro_recurrente_by_name": full_name,
        "cobro_recurrente_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    return {"status": "ok", **updates}


@router.get("/projects/stats")
async def get_project_stats(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    # Stats coherentes con la grilla: aplican el mismo filtro de visibilidad.
    base = await _build_project_visibility_query(user)

    def _q(extra: dict) -> dict:
        return {"$and": [base, extra]} if base else extra

    total = await db.projects.count_documents(base)
    pending = await db.projects.count_documents(_q({"status": "Por asignar"}))
    in_progress = await db.projects.count_documents(_q({"status": {"$in": ["Asignado", "En Gestión", "Implementado parcial"]}}))
    blocked = await db.projects.count_documents(_q({"status": "Suspendido"}))
    frozen = await db.projects.count_documents(_q({"status": "Congelado"}))
    completed = await db.projects.count_documents(_q({"status": "Culminado"}))
    irregular = await db.projects.count_documents(_q({"is_irregular": True}))
    return {"total": total, "pending": pending, "in_progress": in_progress, "blocked": blocked, "frozen": frozen, "completed": completed, "irregular": irregular}


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
    user = await get_current_user(authorization)
    # Aislamiento de datos (P0): el acceso por URL directa debe respetar la misma
    # regla de visibilidad que la grilla. Un Implementador solo puede abrir los
    # proyectos donde figura como técnico asignado; un Ejecutivo solo los de su
    # área/sede. Resto de roles (Coordinador/Gerente/Operaciones/Admin): sin límite.
    vis = await _build_project_visibility_query(user)
    match = {"$and": [vis, {"project_id": project_id}]} if vis else {"project_id": project_id}
    project = await db.projects.find_one(match, {"_id": 0})
    if not project:
        exists = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "project_id": 1})
        if exists:
            raise HTTPException(status_code=403, detail="No tiene acceso a este proyecto")
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    # Iter39: incluir pvv_count (Nro de PVV) — métrica oficial homologada con
    # "Total de Terminales Virtuales" del Resumen Ejecutivo.
    from services.project_pvv import compute_project_pvv
    project["pvv_count"] = compute_project_pvv(project)
    # MultiRIF: enriquecer cada RIF con Razón Social (legal_name) y Nombre de
    # Fantasía (fantasy_name) del cliente VALIDADO (vía client_id). Si el RIF no
    # fue validado (sin client_id) se dejan vacíos para que la UI muestre
    # "No Validado". Aplica por igual a matrices originadas en Cotización o en
    # Proyecto Directo, ya que ambos canales persisten client_id en cada RIF.
    rifs = project.get("rifs") or []
    if rifs:
        rif_client_ids = list({r.get("client_id") for r in rifs if r.get("client_id")})
        rif_clients = {}
        if rif_client_ids:
            async for c in db.clients.find(
                {"client_id": {"$in": rif_client_ids}},
                {"_id": 0, "client_id": 1, "legal_name": 1, "fantasy_name": 1},
            ):
                rif_clients[c["client_id"]] = c
        for r in rifs:
            c = rif_clients.get(r.get("client_id")) or {}
            r["legal_name"] = c.get("legal_name") or ""
            r["fantasy_name"] = c.get("fantasy_name") or ""
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

    # Gatillo de Asignación: al asignar un Implementador el estado pasa a "Asignado".
    # Regla de negocio: si el proyecto YA tiene Nro de Ticket cargado (estaba "En
    # Gestión"), una reasignación NO retrocede el estado — se mantiene "En Gestión".
    has_ticket = bool((project.get("ticket_number") or "").strip())
    new_status = "En Gestión" if has_ticket else "Asignado"

    update_data = {
        "assigned_to_user_id": assignment.assigned_to_user_id,
        "assigned_to_name": implementer_name,
        "assigned_by_user_id": current_user.get("user_id"),
        "assigned_by_name": assigner_name,
        "assigned_at": now,
        "fecha_asignacion": now,
        "status": new_status,
        "status_changed_at": now,
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

    # Notificar al implementador con la nueva plantilla MegaNexus (asíncrono,
    # no bloquea la respuesta HTTP)
    try:
        # Refrescamos el proyecto con los datos de asignación recién aplicados
        # para que la plantilla muestre fecha_asignacion correcta.
        project_for_email = {**project, **update_data}
        await notify_project_assigned(
            project=project_for_email,
            target_user=implementer,
            assigner_name=assigner_name,
        )
    except Exception as e:
        logger.warning(f"[email] notify_project_assigned failed: {e}")

    # Push notification (evento #7 Proyecto asignado a mí)
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="project_assigned_to_me",
            title=f"Proyecto {project.get('project_number','')} asignado a ti",
            message=f"Cliente {project.get('client_name','')}",
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
async def update_project_status(
    project_id: str,
    new_status: str = Form(...),
    note: Optional[str] = Form(None),
    change_date: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
):
    current_user = await get_current_user(authorization)
    if new_status not in PROJECT_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Válidos: {PROJECT_STATUSES}")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Regla: "Configurado en espera del Cliente" solo puede asignarse desde "En Gestión".
    if new_status == "Configurado en espera del Cliente" and project.get("status") != "En Gestión":
        raise HTTPException(status_code=400, detail="El estado 'Configurado en espera del Cliente' solo puede asignarse desde 'En Gestión'.")

    current_status = project.get("status")
    is_freeze = new_status == "Congelado"
    is_unfreeze = current_status == "Congelado" and new_status != "Congelado"

    # Regla de negocio (Congelado): solo se congela DESDE "En Gestión" y solo se
    # descongela HACIA "En Gestión".
    if is_freeze and current_status != "En Gestión":
        raise HTTPException(status_code=400, detail="Solo se puede Congelar un proyecto que esté 'En Gestión'.")
    if is_freeze and not (note or "").strip():
        raise HTTPException(status_code=400, detail="La justificación es obligatoria para Congelar el proyecto.")
    if is_unfreeze and new_status != "En Gestión":
        raise HTTPException(status_code=400, detail="Un proyecto Congelado solo puede volver a 'En Gestión' (Descongelar).")

    now = datetime.now(timezone.utc).isoformat()
    update_data = {"status": new_status, "status_changed_at": now, "updated_at": now}
    if new_status == "Culminado":
        update_data["completed_at"] = now

    if is_freeze:
        # Congelar: pausa el semáforo/retardo. Guardamos los días de retardo
        # acumulados para reanudarlos EXACTOS al descongelar. El motor SLA ignora
        # el estado "Congelado" (no suma retardo ni dispara alertas).
        update_data["is_frozen"] = True
        update_data["frozen_at"] = now
        update_data["freeze_reason"] = (note or "").strip()
        update_data["sla_days_at_freeze"] = int(project.get("sla_days") or 0)
        update_data["last_frozen_alert_at"] = None
    elif is_unfreeze:
        # Descongelar: reanuda el retardo desde donde quedó (pausa real). Se
        # corre la fecha de referencia del semáforo hacia atrás lo justo para que
        # el conteo de días hábiles retome en `sla_days_at_freeze`.
        n_days = int(project.get("sla_days_at_freeze") or project.get("sla_days") or 0)
        from services.business_calendar import get_holiday_sets, business_days_ago
        specific, recurring = await get_holiday_sets()
        ref_date = business_days_ago(datetime.now(timezone.utc).date(), n_days, specific, recurring)
        ref_iso = datetime(ref_date.year, ref_date.month, ref_date.day, tzinfo=timezone.utc).isoformat()
        update_data["status_changed_at"] = ref_iso
        update_data["last_qualified_activity_at"] = ref_iso
        update_data["is_frozen"] = False
        update_data["frozen_at"] = None
        update_data["unfrozen_at"] = now


    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Guardar adjunto opcional de la justificación
    attachment = None
    if file and file.filename:
        upload_dir = f"/app/backend/uploads/status_changes/{project_id}"
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
        file_path = os.path.join(upload_dir, safe_name)
        content = await file.read()
        save_pdf_dual(file_path, content, f"status_changes/{project_id}/{safe_name}")
        attachment = {
            "filename": file.filename,
            "url": f"/uploads/status_changes/{project_id}/{safe_name}",
            "size": len(content),
            "content_type": file.content_type,
        }

    # Nota corta (compatibilidad con historial existente)
    note_text = f"Estado cambiado a '{new_status}'"
    if change_date:
        note_text += f" (Fecha: {change_date})"
    if note:
        note_text += f" — {note}"
    pnote = {"note_id": f"pn_{uuid.uuid4().hex[:8]}", "text": note_text, "created_by": current_user.get("user_id", ""), "created_by_name": user_name, "created_at": now}

    # Entrada de bitácora (auditoría de cierre/suspensión/reactivación)
    bitacora_text = f"[Cambio de Estado] {new_status}"
    if note:
        bitacora_text += f" — {note}"
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": bitacora_text,
        "execution_date": change_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "status_change",
        "new_status": new_status,
        "attachments": [attachment] if attachment else [],
    }

    # Persistir el MOTIVO/justificación del último cambio de estado como campos
    # del proyecto → quedan disponibles como variables de plantilla ({Motivo_Cambio_Estatus})
    # en TODAS las grillas de variables (proyectos, otras acciones, SLA).
    update_data["last_status_note"] = (note or "").strip()
    update_data["last_status_new"] = new_status
    update_data["last_status_from"] = current_status
    update_data["last_status_at"] = now
    update_data["last_status_actor"] = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    update_data["last_status_change_date"] = change_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_data, "$push": {"notes": pnote, "bitacora": bitacora_entry}},
    )

    # Disparo asíncrono (no bloqueante) de la notificación de cambio de estado.
    if new_status in _PROJECT_STATUS_ACTION_MAP:
        import asyncio
        asyncio.create_task(_dispatch_project_status_action(project_id, new_status, note, current_user))

    return {"message": f"Estado actualizado a '{new_status}'", "new_status": new_status, "bitacora_entry_id": bitacora_entry["entry_id"]}


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


# ==================== MASTER OVERRIDE (Super-Admin) ====================

def _build_override_matrix(banks_products, existing_matrix):
    """Reconstruye {banco: {producto: phase_data}} preservando los datos de fase
    existentes cuando el par banco/producto no cambia (evita perder avance)."""
    m = {}
    existing_matrix = existing_matrix or {}
    for bp in banks_products:
        bn = (bp.bank_name or "").strip()
        if not bn:
            continue
        m.setdefault(bn, {})
        for prod in bp.products:
            prod = (prod or "").strip()
            if not prod:
                continue
            m[bn][prod] = (existing_matrix.get(bn, {}) or {}).get(prod, {})
    return m


def _build_override_services(banks_products, existing_services, box_count):
    """Reconstruye los items 'additional' (medios de pago por banco) desde el
    override, preservando precios de los items que coinciden y descartando los
    eliminados. Los items que no son 'additional' se conservan intactos."""
    existing_services = existing_services or []
    kept = [s for s in existing_services if s.get("item_type") != "additional"]
    existing_add = {
        ((s.get("bank_name") or "").strip(), (s.get("item_name") or "").strip()): s
        for s in existing_services if s.get("item_type") == "additional"
    }
    qty = box_count or 1
    for bp in banks_products:
        bn = (bp.bank_name or "").strip()
        if not bn:
            continue
        for prod in bp.products:
            prod = (prod or "").strip()
            if not prod:
                continue
            match = existing_add.get((bn, prod))
            if match:
                kept.append(match)
            else:
                kept.append({
                    "item_type": "additional",
                    "item_id": None,
                    "item_name": prod,
                    "bank_name": bn,
                    "quantity": qty,
                    "cantidad_cajas": qty,
                    "cantidad_bancos": 1,
                    "unit_price_usd": 0,
                    "total_usd": 0,
                })
    return kept


def _summarize_matrix(matrix):
    """Convierte {banco: {producto: {...}}} en un texto legible 'Banco: p1, p2'."""
    if not matrix:
        return "—"
    parts = []
    for bn, prods in matrix.items():
        prod_list = ", ".join(sorted((prods or {}).keys())) or "(sin productos)"
        parts.append(f"{bn}: {prod_list}")
    return " | ".join(parts)


def _master_diff(old_project, update, is_multistore):
    """Calcula el diff de auditoría (campo, etiqueta, anterior, nuevo) entre el
    proyecto previo y el override aplicado. Devuelve lista de cambios."""
    labels = {
        "project_number": "Nro de Proyecto", "client_name": "Cliente", "client_rif": "RIF",
        "client_sede": "Sede", "total_usd": "Total USD", "total_bs": "Total Bs",
        "integrator_name": "Integrador", "integrator_app_name": "App Integrador",
        "pinpad_model": "Modelo Pinpad", "server_name": "Servidor", "ticket_number": "Nro de Ticket",
        "status": "Estado", "quote_type": "Tipo de Proyecto", "sponsoring_bank_name": "Banco Patrocinador",
        "created_by_name": "Generador",
    }
    changes = []
    for field, label in labels.items():
        if field not in update:
            continue
        old_val = old_project.get(field)
        new_val = update.get(field)
        if (old_val or "") != (new_val or "") and not (old_val in (None, "") and new_val in (None, "")):
            changes.append({"field": field, "label": label, "old": old_val, "new": new_val})

    if "hardware" in update:
        old_hw = ", ".join(sorted([h.get("name", "") for h in (old_project.get("hardware") or [])])) or "—"
        new_hw = ", ".join(sorted([h.get("name", "") for h in (update.get("hardware") or [])])) or "—"
        if old_hw != new_hw:
            changes.append({"field": "hardware", "label": "Hardware", "old": old_hw, "new": new_hw})

    if "implementation_matrix" in update:
        old_sum = _summarize_matrix(old_project.get("implementation_matrix"))
        new_sum = _summarize_matrix(update.get("implementation_matrix"))
        if old_sum != new_sum:
            changes.append({"field": "implementation_matrix", "label": "Bancos/Productos", "old": old_sum, "new": new_sum})

    if is_multistore and "stores" in update:
        old_stores = {s.get("store_id"): s for s in (old_project.get("stores") or [])}
        for st in update.get("stores") or []:
            sid = st.get("store_id")
            o_sum = _summarize_matrix((old_stores.get(sid) or {}).get("implementation_matrix"))
            n_sum = _summarize_matrix(st.get("implementation_matrix"))
            if o_sum != n_sum:
                changes.append({
                    "field": f"store:{sid}",
                    "label": f"Tienda «{st.get('name', sid)}»",
                    "old": o_sum, "new": n_sum,
                })
    return changes


@router.put("/projects/{project_id}/master-override")
async def master_override_project(project_id: str, payload: MasterOverridePayload, authorization: Optional[str] = Header(None)):
    """Edición Maestra (Super-Admin Override). Sobrescribe de forma directa y sin
    restricciones los datos del proyecto, reconstruyendo de forma consistente las
    estructuras relacionales (banks[], services[], implementation_matrix y, en
    multitienda, las matrices por tienda). EXCLUSIVO para rol Administrador."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: la Edición Maestra es exclusiva para Administradores.")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    update = {"updated_at": now, "updated_by": current_user.get("email", "")}

    # --- Campos escalares de texto ---
    for f in ("project_number", "client_id", "client_name", "client_rif", "client_sede",
              "integrator_id", "integrator_name", "integrator_app_name", "pinpad_model", "server_name"):
        val = getattr(payload, f)
        if val is not None:
            update[f] = val
    if payload.total_usd is not None:
        update["total_usd"] = payload.total_usd
    if payload.total_bs is not None:
        update["total_bs"] = payload.total_bs
    if payload.ticket_number is not None:
        update["ticket_number"] = payload.ticket_number.strip()

    # --- Dropdowns ---
    if payload.status is not None:
        if payload.status not in PROJECT_STATUSES:
            raise HTTPException(status_code=400, detail=f"Estado inválido. Válidos: {PROJECT_STATUSES}")
        update["status"] = payload.status
        update["status_changed_at"] = now
        if payload.status == "Culminado":
            update["completed_at"] = now
    if payload.quote_type is not None:
        update["quote_type"] = (payload.quote_type or "").upper()

    # --- Generador del Proyecto (created_by) ---
    if payload.generador_user_id is not None:
        gid = (payload.generador_user_id or "").strip()
        if gid and gid != "__none__":
            gu = await db.users.find_one(
                {"user_id": gid}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}
            )
            if not gu:
                raise HTTPException(status_code=400, detail="Usuario Generador no encontrado.")
            gname = f"{gu.get('first_name', '')} {gu.get('last_name', '')}".strip() or gu.get("email", "")
            update["created_by_user_id"] = gid
            update["created_by_name"] = gname
        else:
            update["created_by_user_id"] = None
            update["created_by_name"] = "—"

    # --- Banco Patrocinador ---
    if payload.sponsoring_bank_name is not None:
        bank_name = (payload.sponsoring_bank_name or "").strip()
        proc = (payload.sponsoring_processor_name or "").strip()
        update["sponsoring_bank_name"] = bank_name or None
        update["sponsoring_bank_id"] = payload.sponsoring_bank_id or None
        update["sponsoring_processor_name"] = proc or None
        update["sponsored_implementation"] = bool(bank_name)
        update["patrocinador_label"] = (f"{proc} — {bank_name}" if proc and bank_name else (bank_name or None))

    # --- Hardware ---
    if payload.hardware is not None:
        update["hardware"] = payload.hardware

    # --- Estructura relacional (Banco ↔ Productos) ---
    is_multistore = project.get("project_type") == "multistore"
    if is_multistore and payload.stores_products is not None:
        sp_map = {s.store_id: s.banks_products for s in payload.stores_products}
        union = {}  # banco -> set(productos)
        new_stores = []
        for st in project.get("stores", []):
            sid = st.get("store_id")
            if sid in sp_map:
                bps = sp_map[sid]
                st["implementation_matrix"] = _build_override_matrix(bps, st.get("implementation_matrix", {}))
                for bp in bps:
                    union.setdefault((bp.bank_name or "").strip(), set()).update(
                        [(p or "").strip() for p in bp.products if (p or "").strip()]
                    )
            else:
                for bn, prods in (st.get("implementation_matrix") or {}).items():
                    union.setdefault(bn, set()).update(prods.keys())
            new_stores.append(st)
        update["stores"] = new_stores
        # La matriz principal de multitienda es la unión de las tiendas
        principal = [BankProductsOverride(bank_name=bn, products=sorted(prods)) for bn, prods in union.items() if bn]
        update["implementation_matrix"] = _build_override_matrix(principal, project.get("implementation_matrix", {}))
        update["banks"] = [{"bank_name": bn} for bn in union.keys() if bn]
        update["services"] = _build_override_services(principal, project.get("services", []), project.get("box_count"))
    elif payload.banks_products is not None:
        bps = payload.banks_products
        update["implementation_matrix"] = _build_override_matrix(bps, project.get("implementation_matrix", {}))
        update["banks"] = [{"bank_name": (bp.bank_name or "").strip()} for bp in bps if (bp.bank_name or "").strip()]
        update["services"] = _build_override_services(bps, project.get("services", []), project.get("box_count"))

    # --- Auditoría con diff (campo: anterior → nuevo) ---
    changes = _master_diff(project, update, is_multistore)

    def _fmt(v):
        if v in (None, ""):
            return "—"
        return str(v)

    if changes:
        diff_lines = "; ".join(f"{c['label']}: '{_fmt(c['old'])}' → '{_fmt(c['new'])}'" for c in changes)
        summary_text = f"[Edición Maestra] {len(changes)} campo(s) modificado(s) por {user_name}: {diff_lines}"
    else:
        summary_text = f"[Edición Maestra] {user_name} guardó sin cambios efectivos."

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": summary_text,
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": summary_text,
        "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "master_override",
        "changes": changes,
    }
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update, "$push": {"notes": note, "bitacora": bitacora_entry}},
    )

    # Disparo asíncrono de la notificación de cambio de estado (Edición Maestra),
    # solo cuando el estado cambió efectivamente a un estado con trigger.
    new_status_mo = update.get("status")
    if new_status_mo in _PROJECT_STATUS_ACTION_MAP and new_status_mo != project.get("status"):
        import asyncio
        asyncio.create_task(_dispatch_project_status_action(project_id, new_status_mo, None, current_user))

    return {"message": "Proyecto actualizado (Edición Maestra)", "project_id": project_id, "changes_count": len(changes)}


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


# Estados de proyecto considerados "cerrados" (no vigentes) para el resumen de carga.
_CLOSED_STATUSES = {"culminado", "anulado"}


@router.get("/projects/implementers/{user_id}/workload-summary")
async def implementer_workload_summary(
    user_id: str,
    name: Optional[str] = Query(None, description="Nombre del implementador (fallback cuando no hay user_id o es legacy/huérfano)."),
    authorization: Optional[str] = Header(None),
):
    """Resumen rápido de carga de un implementador (para el tooltip del Panel de Proyectos).
    Estrategia A (carga bajo demanda). Calcula sobre el MISMO universo que el "Reporte de Carga"
    (TODOS los proyectos asignados, sin filtrar por estado) para que los números coincidan
    exactamente con el reporte:
      - projects_count = Nro de Proyectos del reporte.
      - cajas_asignadas = Σ cajas de tipos VPOS/MPOS/VPOS_MULTIRIF (= Nro de Cajas del reporte);
        cajas_pendientes = asignadas − configuradas (configuradas solo si Culminado/Implementado parcial).
      - pvv_asignados = Σ compute_project_pvv de TODOS los proyectos (= Total PVV del reporte);
        pvv_pendientes = asignados − configurados (procesados en fase 'En Producción').
      - avance_global = promedio del % de avance.
    Resiliente: si el user_id es vacío/placeholder o no devuelve proyectos pero llega `name`,
    se reintenta por `assigned_to_name`. Sin proyectos → todo en 0.
    """
    await get_current_user(authorization)

    from services.project_pvv import compute_project_metrics, compute_project_pvv

    _proj = {
        "_id": 0, "status": 1, "quote_type": 1,
        "cantidad_cajas": 1, "box_count": 1, "rifs": 1,
        "implementation_matrix": 1, "stores": 1, "assigned_to_name": 1,
    }

    projs = []
    has_uid = bool(user_id) and user_id.strip().lower() not in ("_", "none", "null", "undefined")
    if has_uid:
        projs = await db.projects.find({"assigned_to_user_id": user_id}, _proj).to_list(5000)
    # Fallback por nombre (legacy / user_id huérfano)
    if not projs and name:
        projs = await db.projects.find({"assigned_to_name": name}, _proj).to_list(5000)

    # Universo idéntico al "Reporte de Carga": TODOS los proyectos asignados
    # (sin filtrar por estado), para que projects_count / cajas / PVV coincidan
    # exactamente con el reporte (Nro de Proyectos / Nro de Cajas / Total PVV).
    _CONFIGURED = {"culminado", "implementado parcial"}
    cajas_asignadas = 0
    cajas_configuradas = 0
    pvv_asignados = 0
    pvv_configurados = 0
    prog_sum = 0.0
    for p in projs:
        qt = (p.get("quote_type") or "").upper()
        # PVV: suma de compute_project_pvv para TODOS los tipos (igual que el reporte "Total PVV").
        pvv_asignados += compute_project_pvv(p)
        pvv_configurados += compute_project_metrics(p)["pvv_configurados"]
        # Cajas: solo tipos que cuentan cajas (VPOS/MPOS/VPOS_MULTIRIF), igual que el reporte "Nro de Cajas".
        if _counts_cajas(qt):
            cajas = _project_total_cajas(p)
            cajas_asignadas += cajas
            if (p.get("status") or "").strip().lower() in _CONFIGURED:
                cajas_configuradas += cajas
        prog = _calculate_rollup_progress(p) if p.get("stores") else _calculate_single_progress(p)
        prog_sum += prog.get("global_progress", 0) or 0

    n = len(projs)
    cajas_pendientes = max(0, cajas_asignadas - cajas_configuradas)
    pvv_pendientes = max(0, pvv_asignados - pvv_configurados)
    avance_global = int(round(prog_sum / n)) if n else 0
    resolved_name = (projs[0].get("assigned_to_name") if projs else "") or (name or "")

    return {
        "user_id": user_id,
        "implementer_name": resolved_name,
        "projects_count": n,
        "cajas_asignadas": cajas_asignadas,
        "cajas_pendientes": cajas_pendientes,
        "pvv_asignados": pvv_asignados,
        "pvv_pendientes": pvv_pendientes,
        "avance_global": avance_global,
    }


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
    template_id: Optional[str] = None  # Plantilla de Proyecto seleccionada en el modal (override del default)


@router.post("/projects/{project_id}/send-notification")
async def send_sequential_notification(
    project_id: str,
    target: str = Form(...),
    bank_name: str = Form(default=""),
    additional_recipients: str = Form(default="[]"),
    to_override: str = Form(default="[]"),
    custom_html: str = Form(default=""),
    custom_subject: str = Form(default=""),
    template_id: str = Form(default=""),
    attach_matrix: str = Form(default="false"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None),
):
    """Enviar notificación al cliente o banco (multipart: soporta adjuntos + matriz).
    El prefijo se calcula automáticamente por conteo."""
    def _parse_list(raw):
        try:
            v = json.loads(raw) if raw else []
            return [e for e in v if e] if isinstance(v, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    cc = _parse_list(additional_recipients)
    to_ov = _parse_list(to_override)
    extra_attachments = []
    for f in files:
        if f.filename:
            content = await f.read()
            extra_attachments.append({"filename": f.filename, "content": content, "content_type": f.content_type})

    return await _send_sequential_notification(
        project_id, target, (bank_name or None), authorization,
        additional_recipients=(cc or None),
        custom_html=(custom_html or None),
        custom_subject=(custom_subject or None),
        to_override=(to_ov or None),
        template_id=(template_id or None),
        extra_attachments=extra_attachments,
        attach_matrix=(str(attach_matrix).lower() == "true"),
    )


# ==================== PLANTILLA PREFERIDA (Preferencias de Notificación) ====================
# Mapeo destino → template_id preferido para precargar en el modal de notificaciones.
# Se almacena en db.config (type='project_notification_preferences').
NOTIF_PREF_DOC = {"type": "project_notification_preferences"}
VALID_NOTIF_DESTINATIONS = ("client", "bank", "bank_client", "client_avance", "bank_avance")


async def _get_notification_template(template_id: Optional[str]) -> Optional[dict]:
    """Obtiene una plantilla por id desde la BD; si no está persistida, recurre a los
    defaults de Plantillas de Proyecto / por sede / legacy (Texto Enriquecido)."""
    if not template_id:
        return None
    tpl = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    if tpl:
        return tpl
    from routes.seed_and_templates import (
        PROJECT_EMAIL_TEMPLATES, EMAIL_TEMPLATES_BY_SEDE, DEFAULT_EMAIL_TEMPLATES,
    )
    for d in (PROJECT_EMAIL_TEMPLATES, EMAIL_TEMPLATES_BY_SEDE, DEFAULT_EMAIL_TEMPLATES):
        if template_id in d:
            return d[template_id]
    return None


@router.get("/project-notification-preferences")
async def get_notification_preferences(authorization: Optional[str] = Header(None)):
    """Devuelve el template_id preferido por destino: {client, bank, bank_client}."""
    await get_current_user(authorization)
    doc = await db.config.find_one(NOTIF_PREF_DOC, {"_id": 0})
    doc = doc or {}
    return {
        "client": doc.get("client") or "project_notify_client",
        "bank": doc.get("bank") or "project_notify_bank",
        "bank_client": doc.get("bank_client") or "project_notify_bank_client",
        # Notificación de Avance (consolidado al cliente / técnica por banco).
        # Por defecto reutilizan la plantilla preferida base de client/bank.
        "client_avance": doc.get("client_avance") or doc.get("client") or "project_notify_client",
        "bank_avance": doc.get("bank_avance") or doc.get("bank") or "project_notify_bank",
    }


class NotificationPreferenceUpdate(BaseModel):
    destination: str  # "client" | "bank" | "bank_client"
    template_id: str


@router.put("/project-notification-preferences")
async def set_notification_preference(body: NotificationPreferenceUpdate, authorization: Optional[str] = Header(None)):
    """Marca una plantilla como Preferida para un destino concreto (solo una por destino)."""
    await get_current_user(authorization)
    if body.destination not in VALID_NOTIF_DESTINATIONS:
        raise HTTPException(status_code=400, detail="Destino inválido")
    tpl = await _get_notification_template(body.template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    await db.config.update_one(
        NOTIF_PREF_DOC,
        {"$set": {body.destination: body.template_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"message": "Plantilla preferida actualizada", "destination": body.destination, "template_id": body.template_id}


@router.get("/projects/{project_id}/attachments/{attachment_id}/download")
async def download_project_attachment(project_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Descarga un anexo del proyecto (los cargados en Proyectos Directos antes
    del envío a Implementación). Sirve desde FS local primero, luego Object
    Storage como fallback. Acceso: cualquier usuario con acceso al módulo
    Proyectos (RBAC global cubre /api/projects)."""
    import io as _io
    from config import UPLOADS_DIR
    from services.pdf_storage import get_pdf_from_storage

    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "attachments": 1})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    att = next((a for a in (project.get("attachments") or []) if a.get("attachment_id") == attachment_id), None)
    if not att:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")

    key = (att.get("storage_key") or (att.get("url") or "").replace("/uploads/", "")).lstrip("/")
    ctype = att.get("content_type", "application/octet-stream")
    filename = att.get("filename", attachment_id)

    file_path = UPLOADS_DIR / key
    if file_path.exists():
        return FileResponse(path=str(file_path), filename=filename, media_type=ctype)

    obj = get_pdf_from_storage(key)
    if obj:
        content, stored_ctype = obj
        return StreamingResponse(
            _io.BytesIO(content),
            media_type=stored_ctype or ctype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")


@router.get("/projects/{project_id}/ficha-tecnica")
async def download_ficha_tecnica(project_id: str, authorization: Optional[str] = Header(None)):
    """Genera y descarga al vuelo la Ficha Técnica de Implementación (Sección A + B)
    de un proyecto, reutilizando el generador de PDF. Construye un dict tipo-cotización
    desde el proyecto (y complementa desde la cotización origen si existe)."""
    await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    from services.implementation_pdf import generate_implementation_pdf

    def pick(*vals):
        for v in vals:
            if v not in (None, ""):
                return v
        return ""

    # Base: cotización origen si existe; luego se sobreescribe con datos del proyecto
    quote_like = {}
    if project.get("quote_id"):
        q = await db.quotes.find_one({"quote_id": project["quote_id"]}, {"_id": 0})
        if q:
            quote_like = dict(q)

    client = {}
    if project.get("client_id"):
        client = await db.clients.find_one({"client_id": project["client_id"]}, {"_id": 0}) or {}

    quote_like.update({
        "quote_number": pick(project.get("quote_number"), quote_like.get("quote_number"), project.get("project_number")),
        "quote_type": pick(project.get("quote_type"), quote_like.get("quote_type")),
        # Bancos/Productos del Resumen Ejecutivo: el proyecto es la fuente de verdad
        # (la implementation_matrix se arma desde estos `services`). Para Proyectos
        # Directos el quote_id es ficticio y no existe en `quotes`, por lo que sin
        # esto la tabla salía vacía. Fallback a la cotización origen si el proyecto
        # no los tuviera persistidos.
        "services": project.get("services") or quote_like.get("services") or [],
        "pg_setup_items": project.get("pg_setup_items") or quote_like.get("pg_setup_items") or [],
        "cantidad_cajas": project.get("box_count") or quote_like.get("cantidad_cajas") or 0,
        "economic_group": pick(project.get("economic_group"), quote_like.get("economic_group")),
        "fantasy_name": pick(project.get("fantasy_name"), quote_like.get("fantasy_name"), client.get("fantasy_name"), project.get("client_name")),
        "integrator_name": pick(project.get("integrator_name"), quote_like.get("integrator_name")),
        "integrator_app_name": pick(project.get("integrator_app_name"), quote_like.get("integrator_app_name")),
        "pinpad_model": pick(project.get("pinpad_model"), quote_like.get("pinpad_model")),
        "server_name": pick(project.get("server_name"), quote_like.get("server_name")),
        "communication_type": pick(project.get("communication_type"), quote_like.get("communication_type")),
        "sponsor_bank_name": pick(project.get("sponsor_bank_name"), quote_like.get("sponsor_bank_name")),
        "sponsor_processor_name": pick(project.get("sponsor_processor_name"), quote_like.get("sponsor_processor_name")),
        "sponsored_implementation": project.get("sponsored_implementation", quote_like.get("sponsored_implementation")),
        "sponsoring_bank_name": pick(project.get("sponsoring_bank_name"), quote_like.get("sponsoring_bank_name")),
        "sponsoring_processor_name": pick(project.get("sponsoring_processor_name"), quote_like.get("sponsoring_processor_name")),
        "pinpad_serials": project.get("pinpad_serials") or quote_like.get("pinpad_serials") or [],
        "equipments": project.get("equipments") or quote_like.get("equipments") or [],
        "serials_provider_note": pick(project.get("serials_provider_note"), quote_like.get("serials_provider_note")),
        "fiscal_printer_model": pick(project.get("fiscal_printer_model"), quote_like.get("fiscal_printer_model")),
        "client_segment": pick(project.get("client_segment"), quote_like.get("client_segment"), "PYME"),
        "client_name": pick(project.get("client_name"), quote_like.get("client_name")),
        "client_rif": pick(project.get("client_rif"), quote_like.get("client_rif")),
        # Componentes adicionales (Ficha Técnica sección C): fuente de verdad el proyecto
        "additional_components": project.get("additional_components") or quote_like.get("additional_components"),
        # Instrucciones/observaciones para el implementador: el PROYECTO es la
        # fuente de verdad al regenerar la ficha (la cotización origen puede haber
        # sido archivada/eliminada, y en Proyectos Directos el quote_id es ficticio).
        "implementation_instructions": pick(project.get("implementation_instructions"), quote_like.get("implementation_instructions")),
    })

    contacts = client.get("contacts", []) if client else []
    branches = quote_like.get("branch_details") or project.get("branch_details") or []
    if not branches and project.get("stores"):
        branches = [
            {"store_name": s.get("name", ""), "quantity": s.get("box_count", 0)}
            for s in project.get("stores", [])
        ]

    # VPOS Multi-RIF: construir la distribución jerárquica (Cliente/RIF ->
    # Sucursales -> Cajas) desde rifs + stores del proyecto, para que la Ficha
    # Técnica imprima el "Detalle de Tiendas y Sucursales" jerárquico.
    is_multirif_project = (project.get("project_type") or "").lower() == "multirif" or bool(project.get("rifs"))
    if is_multirif_project:
        stores_all = project.get("stores") or []
        mr_dist = []
        for rif in (project.get("rifs") or []):
            rid = rif.get("rif_id")
            rif_stores = [s for s in stores_all if s.get("rif_id") == rid]
            mr_dist.append({
                "client_name": rif.get("client_name") or "Cliente",
                "rif": rif.get("rif") or "",
                "boxes": int(rif.get("box_count") or 0),
                "stores": [
                    {"name": s.get("name", ""), "boxes": int(s.get("box_count") or 0)}
                    for s in rif_stores
                ],
            })
        if mr_dist:
            quote_like["multirif_distribution"] = mr_dist
            quote_like["is_multirif"] = True

    pdf_bytes = generate_implementation_pdf(quote_like, client, contacts, branches)
    safe_num = str(quote_like.get("quote_number") or project_id).replace("/", "_").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ficha_tecnica_{safe_num}.pdf"'},
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


def _html_to_plaintext(html: str) -> str:
    """Convierte el HTML de un correo a texto simple legible para la bitácora.
    Preserva saltos de línea de bloques (<br>, <p>, <div>, <tr>, <li>, <h*>) y
    representa filas de tabla con separadores para que la matriz siga siendo legible.
    """
    if not html or not str(html).strip():
        return ""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(str(html), "html.parser")
        for tag in soup(["style", "script"]):
            tag.decompose()
        # Separadores de celdas -> tabuladores; filas -> saltos de línea
        for td in soup.find_all(["td", "th"]):
            td.insert_after(" | ")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for block in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table"]):
            block.append("\n")
        text = soup.get_text()
    except Exception:
        text = re.sub(r"<br\s*/?>", "\n", str(html), flags=re.I)
        text = re.sub(r"</(p|div|tr|li|h[1-6]|table)>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        import html as _htmlmod
        text = _htmlmod.unescape(text)
    # Normalizar: quitar " | " colgantes, espacios y líneas en blanco excesivas
    lines = []
    for ln in text.splitlines():
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        ln = re.sub(r"(\s*\|\s*)+$", "", ln).strip()
        lines.append(ln)
    out, blank = [], 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 1:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip()



def _style_email_tables(html: str) -> str:
    """Aplica estilos email-safe (bordes/padding) a tablas sin estilo.

    El editor enriquecido (TipTap) puede serializar la Matriz de Bancos/Productos
    sin sus estilos inline; este post-procesado garantiza que el destinatario
    reciba una tabla legible con bordes. No altera tablas que ya traen `style`.
    """
    if not html or '<table' not in html:
        return html

    def _style_table(m):
        tag = m.group(0)
        if 'style=' in tag.lower():
            return tag
        return tag[:-1] + ' style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;margin:8px 0;">'

    def _style_cell(m):
        tag = m.group(0)
        name = m.group(1)
        attrs = m.group(2) or ''
        if 'style=' in attrs.lower():
            return tag
        is_header = name.lower() == 'th'
        base = 'padding:8px 12px;border:1px solid #e9ecef;'
        if is_header:
            base = 'padding:10px 12px;border:1px solid #ddd;text-align:left;background:#2c3e50;color:#ffffff;'
        return f'<{name}{attrs} style="{base}">'

    html = re.sub(r'<table[^>]*>', _style_table, html)
    html = re.sub(r'<(td|th)([^>]*)>', _style_cell, html)
    return html


def _adhoc_message_to_html(message: str) -> str:
    """Cuerpo del correo ad-hoc → HTML.

    Si el mensaje ya viene como HTML (editor de Texto Enriquecido), se respeta tal
    cual y se estilizan sus tablas. Si es texto plano (legacy), se aplica nl2br
    dentro de un párrafo. Evita envolver HTML de bloque dentro de un <p> inválido.
    """
    msg = message or ""
    if re.search(r'<[a-zA-Z][^>]*>', msg):
        return _style_email_tables(msg)
    return f"<p>{msg.replace(chr(10), '<br>')}</p>"


def _clean_html_in_braces(html: str) -> str:
    """Limpia etiquetas HTML que el editor rico pueda insertar DENTRO de variables {Variable}.
    Ej: {<span>Nombre</span>_Cliente} → {Nombre_Cliente}

    Solo opera sobre el contenido encerrado entre llaves (sin anidar). NO consume
    etiquetas adyacentes fuera de las llaves, evitando corromper estructuras como
    tablas que sigan inmediatamente a una variable (ej. {Patrocinador}<table>...).
    """
    def replacer(m):
        inner = re.sub(r'<[^>]*>', '', m.group(1)).strip()
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', inner):
            return '{' + inner + '}'
        return m.group(0)  # no parece una variable → dejar intacto

    # Captura {...} sin llaves anidadas
    return re.sub(r'\{([^{}]*)\}', replacer, html)


async def _resolve_notification_email(project: dict, target: str, bank_name: Optional[str], send_count: int, template_vars: dict, override_template_id: Optional[str] = None) -> dict:
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

        # Plantilla del DB (preferida/seleccionada o default de Texto Enriquecido)
        template = await _get_notification_template(override_template_id or "project_notify_client")
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "Implementación: {project_number}"), template_vars)
            # 2.3: limpiar variables NO parametrizadas que quedaron sin resolver en el asunto
            # (evita imprimir nombres técnicos como {Nombre_Variable} que el operador no insertó).
            raw_subject = re.sub(r"\{\{?\s*[A-Za-z0-9_áéíóúÁÉÍÓÚñÑ]+\s*\}?\}", "", raw_subject)
            raw_subject = re.sub(r"\s{2,}", " ", raw_subject).strip()
            subject = f"{raw_subject} [{prefix_label}]"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            subject = f"Implementación: {project.get('project_number', '')} [{prefix_label}]"
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
        # Matriz de Seguimiento Evolutiva: filtrada al banco destinatario (confidencialidad).
        from services.project_template_vars import _build_seguimiento_evolutiva_html, _build_matrix_html
        template_vars["Matriz_Seguimiento_Evolutiva"] = _build_seguimiento_evolutiva_html(project, bank_filter=bank_name)
        # Matriz de Bancos y Productos: filtrada automáticamente al banco destinatario.
        template_vars["Matriz_Bancos_Productos"] = _build_matrix_html(
            project.get("implementation_matrix", {}), services=project.get("services", []) or [], bank_filter=bank_name)
        if client:
            template_vars["client_rif"] = client.get("rif", client.get("tax_id", ""))

        template = await _get_notification_template(override_template_id or "project_notify_bank_client")
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "{bank_name} — {Nombre_Cliente} — {project_number}"), template_vars)
            subject = f"{raw_subject} [{prefix_label}]"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            # Fallback: combina datos del cliente y banco
            products_html = "".join(f"<li>{p}</li>" for p in bank_products)
            subject = f"{bank_name} — {client_name} — {project.get('project_number', '')} [{prefix_label}]"
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
        # Matriz de Seguimiento Evolutiva: filtrada al banco destinatario (confidencialidad).
        from services.project_template_vars import _build_seguimiento_evolutiva_html, _build_matrix_html
        template_vars["Matriz_Seguimiento_Evolutiva"] = _build_seguimiento_evolutiva_html(project, bank_filter=bank_name)
        # Matriz de Bancos y Productos: filtrada automáticamente al banco destinatario.
        template_vars["Matriz_Bancos_Productos"] = _build_matrix_html(
            project.get("implementation_matrix", {}), services=project.get("services", []) or [], bank_filter=bank_name)

        # Siempre usar plantilla del DB (preferida/seleccionada o default)
        template = await _get_notification_template(override_template_id or "project_notify_bank")
        if template and template.get("body_html"):
            raw_subject = _render_vars(template.get("subject", "{bank_name} — {project_number}"), template_vars)
            subject = f"{raw_subject} [{prefix_label}]"
            html = _render_vars(template.get("body_html", ""), template_vars)
        else:
            products_html = "".join(f"<li>{p}</li>" for p in bank_products)
            subject = f"{bank_name} — {project.get('project_number', '')} [{prefix_label}]"
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


async def _send_sequential_notification(project_id: str, target: str, bank_name: Optional[str], authorization: str, level: str = None, additional_recipients: Optional[List[str]] = None, custom_html: Optional[str] = None, custom_subject: Optional[str] = None, to_override: Optional[List[str]] = None, template_id: Optional[str] = None, extra_attachments: Optional[List[dict]] = None, attach_matrix: bool = False):
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

    # Resolver variables del proyecto (firma = usuario que detona, si lo hay)
    _actor = await get_current_user(authorization) if authorization else None
    template_vars = await resolve_project_template_vars(project, actor_user=_actor)

    # Construir email con plantilla + prefijo dinámico
    email_data = await _resolve_notification_email(project, target, bank_name, send_count, template_vars, override_template_id=template_id)
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
        # Re-aplicar estilos a tablas (la matriz editada en el editor puede perder estilos inline)
        html = _style_email_tables(html)
    if custom_subject:
        subject = _render_vars(subject, template_vars)

    # Adjuntar tabla de la matriz de distribución al cuerpo si se solicitó (botón "Adjuntar Matriz")
    if attach_matrix:
        _matrix = template_vars.get("Matriz_Bancos_Productos", "")
        if _matrix:
            html = f"{html}<hr>{_style_email_tables(_matrix)}"

    # Process base64 images → upload to storage for email compatibility
    html = await _replace_base64_images(html, current_user.get("user_id", "system"))

    # Preparar adjuntos (Cargar Archivos / Imágenes): se guardan en disco (registro) y
    # se adjuntan al correo saliente.
    saved_files = []
    email_attachments = None
    if extra_attachments:
        email_attachments = []
        upload_dir = f"/app/backend/uploads/notif_emails/{project_id}"
        os.makedirs(upload_dir, exist_ok=True)
        for att in extra_attachments:
            content = att.get("content", b"")
            fname = att.get("filename", "adjunto")
            safe_name = f"{uuid.uuid4().hex[:8]}_{fname}"
            file_path = os.path.join(upload_dir, safe_name)
            try:
                save_pdf_dual(file_path, content, f"notif_emails/{project_id}/{safe_name}")
            except Exception:
                pass
            saved_files.append({"filename": fname, "url": f"/uploads/notif_emails/{project_id}/{safe_name}", "size": len(content), "content_type": att.get("content_type")})
            email_attachments.append({"filename": fname, "content": content})

    email_result = await send_email(
        to=to_list, subject=subject, html=html,
        action=f"notification_{target}_{prefix_label.replace(' ', '_').lower()}",
        quote_id=project.get("quote_id"), quote_number=project.get("quote_number"),
        cc=additional_recipients,
        attachments=email_attachments,
        sender=await resolve_sender_for_area("proyectos"),
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
        "attachments_count": len(saved_files),
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

    update_set = {"notification_history": notification_history, "updated_at": now, "last_contact_at": now, "last_contact_by": user_name, "last_contact_target": target,
                  "last_followup_at": now, "last_followup_by": user_name}

    # Disparador de semáforo (En Gestión): un correo EXITOSO a Cliente o Banco es
    # una acción de interacción válida → reinicia el contador de inactividad a Verde.
    if target in ("client", "bank", "bank_client") and email_result.get("status") in ("sent", "simulated"):
        update_set["last_qualified_activity_at"] = now

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
            "message": _html_to_plaintext(html),
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
    # Título legible según destinatario (evita mostrar "Banco None" cuando el
    # envío fue al cliente, que se veía como un error).
    if target == "bank_client" and bank_name:
        _notif_title = f"Cliente + Banco {bank_name} notificado"
    elif target == "bank" and bank_name:
        _notif_title = f"Banco {bank_name} notificado"
    else:
        _notif_title = "Cliente notificado"
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="bank_notified_in_project",
            title=_notif_title,
            message=f"Proyecto {project.get('project_number','')} · Nivel {prefix_label}",
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
    template_id: Optional[str] = None  # Plantilla seleccionada en el modal
    custom_html: Optional[str] = None  # Cuerpo editado en el editor enriquecido
    custom_subject: Optional[str] = None  # Asunto editado (opcional)


@router.post("/projects/{project_id}/preview-notification")
async def preview_notification(project_id: str, body: PreviewNotificationRequest, authorization: Optional[str] = Header(None)):
    """Vista previa de la próxima notificación de proyecto (prefijo automático por conteo)."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Calcular conteo de envíos anteriores
    notification_history = project.get("notification_history", {})
    history_key = "client" if body.target == "client" else f"bank_{body.bank_name}"
    entity_history = notification_history.get(history_key, [])
    send_count = len(entity_history)

    # Resolver variables del proyecto (firma = usuario en sesión)
    template_vars = await resolve_project_template_vars(project, actor_user=current_user)

    # Construir email (sin enviar) con prefijo basado en conteo y plantilla seleccionada
    email_data = await _resolve_notification_email(project, body.target, body.bank_name, send_count, template_vars, override_template_id=body.template_id)

    # Overrides editables del modal (cuerpo / asunto). Se re-renderizan las variables.
    subject = email_data["subject"]
    html = email_data["html"]
    if body.custom_html:
        html = _render_vars(body.custom_html, template_vars)
        html = _style_email_tables(html)
    if body.custom_subject:
        prefix_label = NOTIFICATION_PREFIXES[min(send_count, len(NOTIFICATION_PREFIXES) - 1)]
        raw = _render_vars(body.custom_subject, template_vars)
        subject = raw if raw.strip().startswith("[") else f"[{prefix_label}] {raw}"

    # Si hay destinatarios manuales, sustituir el TO en la respuesta
    to_list = email_data["to_list"]
    if body.to_override:
        valid_to = [e.strip() for e in body.to_override if e and '@' in e]
        if valid_to:
            to_list = valid_to

    # Determinar próximo prefijo
    prefix_idx = min(send_count, len(NOTIFICATION_PREFIXES) - 1)

    return {
        "subject": subject,
        "html": html,
        "recipients": to_list,
        "entity_label": email_data["entity_label"],
        "prefix": NOTIFICATION_PREFIXES[prefix_idx],
        "send_number": send_count + 1,
        "variables": {k: v for k, v in template_vars.items() if k not in ("Matriz_Bancos_Productos", "Matriz_Sucursales", "Matriz_Avance_Proyecto", "Matriz_Avance_Proyecto_Con_Fecha", "Matriz_Seguimiento_Evolutiva")},
        "matrix_html": template_vars.get("Matriz_Bancos_Productos", ""),
    }


class PreviewAdhocRequest(BaseModel):
    subject: str
    message: str
    include_matrix: bool = False


@router.post("/projects/{project_id}/preview-adhoc-email")
async def preview_adhoc_email(project_id: str, body: PreviewAdhocRequest, authorization: Optional[str] = Header(None)):
    """Vista previa de un correo ad-hoc con variables del proyecto resueltas."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Resolver variables del proyecto (firma = usuario que envía)
    template_vars = await resolve_project_template_vars(project, actor_user=current_user)

    # Renderizar asunto y mensaje con variables
    rendered_subject = _render_vars(body.subject, template_vars)
    rendered_message = _render_vars(body.message, template_vars)

    ticket = project.get("ticket_number", "")
    ticket_label = f"[Ticket {ticket}] " if ticket else ""

    message_html = _adhoc_message_to_html(rendered_message)
    matrix_section = ""
    if body.include_matrix:
        matrix_section = f"<hr>{template_vars.get('Matriz_Bancos_Productos', '')}"

    html = f"""<div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        {message_html}
        {matrix_section}
        <hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | {f'Ticket: {ticket} | ' if ticket else ''}Cliente: {template_vars.get('Nombre_Cliente', project.get("client_name", ""))}</p>
    </div>"""

    # No duplicar el prefijo [Ticket N] si el asunto ya lo incluye.
    final_subject = _compose_ticket_subject(ticket, rendered_subject)

    return {
        "subject": final_subject,
        "html": html,
        "variables": {k: v for k, v in template_vars.items() if k not in ("Matriz_Bancos_Productos", "Matriz_Sucursales", "Matriz_Avance_Proyecto", "Matriz_Avance_Proyecto_Con_Fecha", "Matriz_Seguimiento_Evolutiva")},
    }


@router.get("/projects/{project_id}/template-variables")
async def get_project_template_variables(project_id: str, bank: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Obtener las variables resueltas de un proyecto (para mostrar en el editor).

    `bank` (opcional): si se especifica, la `matrix_html` ({Matriz_Bancos_Productos})
    se devuelve ya filtrada a ese banco — para que el editor de una notificación a
    Banco reciba la matriz automáticamente depurada (sin borrado manual)."""
    current_user = await get_current_user(authorization)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    template_vars = await resolve_project_template_vars(project, actor_user=current_user)
    matrix_html = template_vars.get("Matriz_Bancos_Productos", "")
    if bank and (bank or "").strip():
        from services.project_template_vars import _build_matrix_html
        matrix_html = _build_matrix_html(
            project.get("implementation_matrix", {}), services=project.get("services", []) or [], bank_filter=bank.strip())
    return {
        "variables": {k: v for k, v in template_vars.items() if k not in ("Matriz_Bancos_Productos", "Matriz_Sucursales", "Matriz_Avance_Proyecto", "Matriz_Avance_Proyecto_Con_Fecha", "Matriz_Seguimiento_Evolutiva")},
        "matrix_html": matrix_html,
        "available_tags": [
            {"key": "Nombre_Cliente", "label": "Nombre del Cliente", "source": "Clientes.razon_social"},
            {"key": "Contacto_Principal", "label": "Contacto Principal", "source": "Contactos.nombre_apellido"},
            {"key": "Datos_Contacto", "label": "Datos del Contacto (nombre, tel, email)", "source": "Contactos.full_info"},
            {"key": "Nombre_Sucursal", "label": "Nombre de Sucursal", "source": "Sucursales.nombre"},
            {"key": "Cantidad_Cajas", "label": "Cantidad de Cajas", "source": "Sucursales.nro_cajas"},
            {"key": "Matriz_Sucursales", "label": "Tabla de Sucursales (Sucursal / Cantidad de Cajas)", "source": "Proyecto.stores"},
            {"key": "Integrador", "label": "Integrador", "source": "Proyecto.integrador"},
            {"key": "Matriz_Bancos_Productos", "label": "Tabla Bancos/Productos (HTML)", "source": "Proyecto.implementation_matrix"},
            {"key": "Matriz_MultiRif_Distribucion", "label": "Tabla Multi-RIF: Distribución (Cliente/RIF → Sucursales → Cajas)", "source": "Proyecto.rifs"},
            {"key": "Matriz_MultiRif_Avance", "label": "Tabla Multi-RIF: Distribución + Avance % (3 niveles)", "source": "Proyecto.rifs"},
            {"key": "Matriz_Avance_Proyecto", "label": "Matriz de Avance del Proyecto (Banco→Producto→Fases · % por fase · KPI Global)", "source": "Proyecto.implementation_matrix / stores"},
            {"key": "Matriz_Avance_Proyecto_Con_Fecha", "label": "Matriz de Avance del Proyecto CON FECHA (% por fase + fecha en que se alcanzó · KPI Global)", "source": "Proyecto.implementation_matrix / stores"},
            {"key": "Matriz_Seguimiento_Evolutiva", "label": "Matriz de Seguimiento Evolutiva (RIF/Tienda/Cajas × Banco→Producto→Fases · modular por banco)", "source": "Proyecto.rifs / stores / implementation_matrix"},
            {"key": "project_number", "label": "Nro. Proyecto", "source": "Proyecto.project_number"},
            {"key": "quote_number", "label": "Nro. Cotización", "source": "Proyecto.quote_number"},
            {"key": "ticket_number", "label": "Nro. Ticket", "source": "Proyecto.ticket_number"},
            {"key": "client_rif", "label": "RIF del Cliente", "source": "Clientes.rif"},
            {"key": "quote_type", "label": "Tipo de Cotización", "source": "Proyecto.quote_type"},
            {"key": "integrator_app_name", "label": "Aplicativo", "source": "Proyecto.integrator_app_name"},
            {"key": "pinpad_model", "label": "Modelo Pinpad", "source": "Proyecto.pinpad_model"},
            {"key": "assigned_to", "label": "Asignado a", "source": "Proyecto.assigned_to_name"},
            {"key": "Estado_Proyecto", "label": "Estado actual del proyecto", "source": "Proyecto.status"},
            {"key": "Motivo_Cambio_Estatus", "label": "Motivo / Justificación del último cambio de estado", "source": "Proyecto.last_status_note"},
            {"key": "Estatus_Anterior", "label": "Estado anterior (antes del último cambio)", "source": "Proyecto.last_status_from"},
            {"key": "Fecha_Cambio_Estatus", "label": "Fecha del último cambio de estado", "source": "Proyecto.last_status_change_date"},
            {"key": "Usuario_Cambio_Estatus", "label": "Usuario que hizo el último cambio de estado", "source": "Proyecto.last_status_actor"},
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

    # Permisos: Admin, implementador asignado, su supervisor, o equipo de Implementación
    user_role = current_user.get("role", "")
    user_id = current_user.get("user_id", "")
    assigned_to = project.get("assigned_to_user_id", "")
    if user_role != "admin":
        cargo = (current_user.get("cargo") or "").lower()
        depto = (current_user.get("departamento") or "").lower()
        is_impl_profile = ("implement" in depto) or ("implement" in cargo) or ("infraestructura" in cargo)
        # Check if user is the assigned implementer
        is_implementer = bool(user_id) and user_id == assigned_to
        # Check if user is the supervisor of the assigned implementer
        is_supervisor = False
        if assigned_to:
            assigned_user = await db.users.find_one({"user_id": assigned_to}, {"_id": 0, "supervisor_id": 1})
            if assigned_user and assigned_user.get("supervisor_id") == user_id:
                is_supervisor = True
        if not (is_implementer or is_supervisor or is_impl_profile):
            raise HTTPException(status_code=403, detail="Solo el equipo de Implementación, el implementador asignado o su supervisor pueden editar la matriz")

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
        {"$set": {"implementation_matrix": matrix, "updated_at": now, "last_qualified_activity_at": now}}
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
    if project.get("project_type") not in ("multistore", "multirif"):
        raise HTTPException(status_code=400, detail="Este proyecto no es multitienda ni Multi-RIF")

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
            "updated_at": now,
            "last_qualified_activity_at": now
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
    rollup = None
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        rollup = _calculate_rollup_progress(updated_project)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"rollup_progress": rollup, "updated_at": now}}
        )

    # Devolvemos expected/processed/completed calculados + rollup para que el
    # frontend aplique una actualización LOCAL (optimista) sin recargar todo el
    # proyecto (clave para la latencia en Multi-RIF con muchas tiendas).
    return {
        "message": "Fase de tienda actualizada", "store_id": store_id, "bank": bank_key,
        "product": phase_update.product_name, "phase": phase_update.phase,
        "completed": is_completed, "expected": expected, "processed": processed,
        "rollup_progress": rollup,
    }


class BatchMatrixUpdate(BaseModel):
    # --- Multi-selección (nuevo) ---
    phases: Optional[list] = None          # varias fases a marcar al 100%
    bank_products: Optional[dict] = None   # {banco: [medios de pago]} — cruce multi-banco
    # --- Legacy (compatibilidad) ---
    phase: Optional[str] = None            # una sola fase
    bank_name: Optional[str] = None        # un solo banco
    product_name: Optional[str] = None     # un solo producto
    product_names: Optional[list] = None   # varios productos de un solo banco
    # Comunes
    store_ids: Optional[list] = None       # opcional; no requerido en proyectos NO multitienda
    reason: Optional[str] = ""


@router.post("/projects/{project_id}/matrix/batch-update")
async def batch_update_multistore_matrix(project_id: str, body: BatchMatrixUpdate, authorization: Optional[str] = Header(None)):
    """Actualización masiva CRUZADA: marca al 100% una o varias FASES para uno o
    varios BANCOS (cada uno con su lista de medios de pago). Disponible para TODOS
    los proyectos de integración: en multitienda/Multi-RIF aplica a las tiendas
    seleccionadas; en proyectos NO multitienda aplica directamente a la matriz del
    proyecto. Registra UNA entrada en bitácora con todo el detalle."""
    current_user = await get_current_user(authorization)

    # --- Normalizar FASES (multi con fallback legacy) ---
    phases = body.phases if body.phases else ([body.phase] if body.phase else [])
    phases = [p for p in phases if p]
    if not phases:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos una fase")
    invalid = [p for p in phases if p not in STORE_PHASES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Fase(s) inválida(s): {invalid}. Válidas: {STORE_PHASES}")

    # --- Normalizar BANCOS + MEDIOS DE PAGO (dict {banco: [productos]}) ---
    bank_products = {}
    if body.bank_products:
        for bank, prods in body.bank_products.items():
            clean = [p for p in (prods or []) if p]
            if bank and clean:
                bank_products[bank] = clean
    elif body.bank_name:
        legacy_prods = body.product_names if body.product_names else ([body.product_name] if body.product_name else [])
        legacy_prods = [p for p in legacy_prods if p]
        if legacy_prods:
            bank_products[body.bank_name] = legacy_prods
    if not bank_products:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un banco/ente con al menos un medio de pago")

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not project.get("client_notified"):
        raise HTTPException(status_code=400, detail="Debe notificar al cliente primero antes de actualizar la matriz")

    is_multistore = project.get("project_type") in ("multistore", "multirif") and bool(project.get("stores"))

    # Validar banco/medio de pago contra el CATÁLOGO real del proyecto (evita
    # contaminar la matriz con nombres inexistentes por typos del cliente).
    catalog = project.get("implementation_matrix", {}) or {}
    for bank, prods in bank_products.items():
        if bank not in catalog:
            raise HTTPException(status_code=400, detail=f"El banco/ente '{bank}' no existe en la matriz del proyecto")
        bank_catalog = catalog.get(bank) or {}
        for p in prods:
            if p not in bank_catalog:
                raise HTTPException(status_code=400, detail=f"El medio de pago '{p}' no existe para '{bank}'")

    # Permisología: admin, implementador asignado o supervisor.
    # El implementador asignado se guarda en `assigned_to_user_id` (campo canónico).
    user_id = current_user.get("user_id", "")
    user_role = current_user.get("role", "")
    cargo = current_user.get("cargo", "")
    is_admin = user_role == "admin"
    is_assigned = bool(user_id) and user_id in (
        project.get("assigned_to_user_id"),
        project.get("implementer_user_id"),  # compat. legacy
        project.get("implementer_id"),       # compat. legacy
    )
    is_supervisor = cargo in ("Gerente", "Director", "Supervisor")
    if not (is_admin or is_assigned or is_supervisor):
        raise HTTPException(status_code=403, detail="Solo el implementador asignado o su supervisor puede ejecutar actualización masiva")

    stores = project.get("stores", [])
    stores_by_id = {s.get("store_id"): s for s in stores}
    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")

    all_products = sorted({p for prods in bank_products.values() for p in prods})
    banks_list = list(bank_products.keys())

    def _apply_to_matrix(matrix, default_expected):
        """Marca al 100% cada (banco→producto→fase) del cruce sobre una matriz."""
        total = 0
        for bank, prods in bank_products.items():
            if bank not in matrix:
                matrix[bank] = {}
            for product_name in prods:
                if product_name not in matrix[bank]:
                    matrix[bank][product_name] = {}
                for phase in phases:
                    old_data = matrix[bank][product_name].get(phase, {})
                    expected = old_data.get("expected") or default_expected
                    matrix[bank][product_name][phase] = {
                        "completed": True,
                        "expected": expected,
                        "processed": expected,
                        "updated_at": now,
                        "updated_by": user_name,
                        "batch_updated": True,
                    }
                    total += expected
        return total

    processed_stores = []
    scope_label = ""

    if is_multistore:
        target_ids = body.store_ids or []
        if not target_ids:
            raise HTTPException(status_code=400, detail="Debe seleccionar al menos una tienda")
        for sid in target_ids:
            store = stores_by_id.get(sid)
            if not store:
                continue
            matrix = store.get("implementation_matrix", {})
            store_expected_total = _apply_to_matrix(matrix, store.get("box_count", 0) or 0)
            await db.projects.update_one(
                {"project_id": project_id, "stores.store_id": sid},
                {"$set": {"stores.$.implementation_matrix": matrix, "updated_at": now, "last_qualified_activity_at": now}}
            )
            processed_stores.append({"store_id": sid, "name": store.get("name", sid), "expected": store_expected_total})
        if not processed_stores:
            raise HTTPException(status_code=404, detail="Ninguna de las tiendas seleccionadas existe en el proyecto")
        scope_label = f"{len(processed_stores)} tienda(s)"
    else:
        # Proyecto NO multitienda: aplicar directamente a la matriz del proyecto.
        matrix = project.get("implementation_matrix", {}) or {}
        default_expected = project.get("cantidad_cajas") or project.get("box_count") or 0
        _apply_to_matrix(matrix, default_expected)
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"implementation_matrix": matrix, "updated_at": now, "last_qualified_activity_at": now}}
        )
        scope_label = "matriz del proyecto"

    # Recalcular rollup
    updated_project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if updated_project:
        rollup = _calculate_rollup_progress(updated_project)
        await db.projects.update_one({"project_id": project_id}, {"$set": {"rollup_progress": rollup, "updated_at": now}})

    # Bitácora única con detalle completo
    reason = (body.reason or "Recepción de información masiva por parte del Banco/Cliente").strip()
    bp_lines = "\n".join([f"  · {b}: {', '.join(prods)}" for b, prods in bank_products.items()])
    store_names = [s["name"] for s in processed_stores]
    bitacora_text = (
        f"[ACTUALIZACIÓN MASIVA DE ESTATUS]\n"
        f"Fase(s) actualizada(s) ({len(phases)}): {', '.join(phases)}\n"
        f"Bancos/Entes ({len(banks_list)}) y medios de pago:\n{bp_lines}\n"
        + (f"Tiendas procesadas ({len(processed_stores)}): {', '.join(store_names)}\n" if is_multistore else "Alcance: matriz del proyecto (No Multitienda)\n")
        + f"Motivo: {reason}\n"
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
            "phases": phases,
            "bank_products": bank_products,
            "reason": reason,
            "stores": processed_stores,
            "total_stores": len(processed_stores),
            "is_multistore": is_multistore,
        },
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"bitacora": bitacora_entry}})

    return {
        "message": f"Actualización masiva aplicada ({len(phases)} fase(s), {len(banks_list)} banco(s)) a {scope_label}",
        "stores_processed": processed_stores,
        "phases": phases,
        "banks": banks_list,
        "is_multistore": is_multistore,
        "bitacora_entry_id": bitacora_entry["entry_id"],
    }


@router.put("/projects/{project_id}/implementation-fields")
async def update_implementation_fields(project_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar campos de Integrador y Aplicativo en el proyecto."""
    await get_current_user(authorization)
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
    if "fecha_estimada_produccion" in body:
        update_set["fecha_estimada_produccion"] = body["fecha_estimada_produccion"] or None
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
    await get_current_user(authorization)
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
        {"$push": {"bitacora": bitacora_entry},
         "$set": {"last_followup_at": bitacora_entry["created_at"], "last_followup_by": user_name, "updated_at": bitacora_entry["created_at"]}}
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
    additional_recipients: str = Form(default="[]"),
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

    # Parse CC (destinatarios adicionales) — homologado con send-notification
    try:
        cc_raw = json.loads(additional_recipients) if additional_recipients else []
        cc_list = [e for e in cc_raw if e and isinstance(e, str) and '@' in e] if isinstance(cc_raw, list) else []
    except (json.JSONDecodeError, ValueError, TypeError):
        cc_list = []

    if not subject.strip():
        raise HTTPException(status_code=400, detail="El asunto es obligatorio")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    ticket = project.get("ticket_number", "")
    ticket_label = f"[Ticket {ticket}] " if ticket else ""

    # Guardar adjuntos
    saved_files = []
    email_attachments = []  # {filename, content} para adjuntar al correo
    upload_dir = f"/app/backend/uploads/adhoc_emails/{project_id}"
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            save_pdf_dual(file_path, content, f"adhoc_emails/{project_id}/{safe_name}")
            saved_files.append({
                "filename": f.filename,
                "url": f"/uploads/adhoc_emails/{project_id}/{safe_name}",
                "size": len(content),
                "content_type": f.content_type,
            })
            email_attachments.append({"filename": f.filename, "content": content})

    # Construir email HTML
    message_html = _adhoc_message_to_html(message)
    full_subject = subject  # se renderiza y se prefija el ticket más abajo (sin duplicar)
    # Incluir matrix_html si fue enviada (separada del conteo de caracteres)
    matrix_section = f"<hr>{matrix_html}" if matrix_html.strip() else ""
    html = f"""
    <div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        {message_html}
        {matrix_section}
        {f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Ticket: {ticket} | Cliente: {project.get("client_name", "")}</p>' if ticket else f'<hr><p style="color: #666; font-size: 11px;">Proyecto: {project.get("project_number", "")} | Cliente: {project.get("client_name", "")}</p>'}
    </div>
    """

    # Resolve variables in adhoc emails too (firma = usuario que envía)
    template_vars = await resolve_project_template_vars(project, actor_user=current_user)
    html = _render_vars(html, template_vars)
    html = _style_email_tables(html)
    full_subject = _render_vars(full_subject, template_vars)
    # No duplicar el prefijo [Ticket N] si el asunto del usuario ya lo incluye.
    full_subject = _compose_ticket_subject(ticket, full_subject)

    # Process base64 images → upload to storage
    html = await _replace_base64_images(html, current_user.get("user_id", "system"))

    email_result = await send_email(
        to=to_list,
        cc=(cc_list or None),
        subject=full_subject,
        html=html,
        action="adhoc_project_email",
        quote_id=project.get("quote_id"),
        quote_number=project.get("quote_number"),
        sender=await resolve_sender_for_area("proyectos"),
        attachments=(email_attachments or None),
    )

    # Auto-registrar en bitácora con contenido completo
    attachments_text = f" ({len(saved_files)} adjunto(s))" if saved_files else ""
    matrix_tag = " [+Matriz]" if matrix_html.strip() else ""
    cc_tag = f" | CC: {', '.join(cc_list)}" if cc_list else ""
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:8]}",
        "text": f"[Otras Notificaciones] {subject}{attachments_text}{matrix_tag} → {', '.join(to_list)}{cc_tag}",
        "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
        "type": "adhoc_email",
        "email_detail": {
            "subject": full_subject,
            "recipients": to_list,
            "cc": cc_list,
            "message": _html_to_plaintext(html),
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

    # Automatización "Fecha de Último Contacto" + "Último Seguimiento" + semáforo:
    # una "Otra Notificación" al cliente actualiza Último Contacto y Último
    # Seguimiento, y reinicia el semáforo SLA a verde (last_qualified_activity_at)
    # igual que las notificaciones formales cliente/banco.
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"last_contact_at": now, "last_contact_by": user_name, "last_contact_target": "client",
                  "last_followup_at": now, "last_followup_by": user_name,
                  "last_qualified_activity_at": now, "updated_at": now}},
    )

    total_recipients = len(to_list) + len(cc_list)
    return {
        "message": f"Correo enviado a {total_recipients} destinatario(s) ({email_result.get('status', 'unknown')})",
        "status": email_result.get("status"),
        "recipients": to_list,
        "cc": cc_list,
        "subject": full_subject,
        "attachments_count": len(saved_files),
        "bitacora_entry_id": bitacora_entry["entry_id"],
    }


# ==================== SUGGESTED CONTACTS ====================

# Emails/nombres placeholder heredados de importaciones masivas que NO deben
# mostrarse como destinatarios reales (no existen en las fichas).
PLACEHOLDER_CONTACT_EMAILS = {"na@na.com", "sin@email.com", "n/a", "noemail@noemail.com"}
PLACEHOLDER_CONTACT_NAMES = {"n/a", "na", "sin nombre"}


def _is_placeholder_contact(email: str, name: str = "") -> bool:
    em = (email or "").strip().lower()
    nm = (name or "").strip().lower()
    if em in PLACEHOLDER_CONTACT_EMAILS:
        return True
    if "@" not in em:
        return True  # email inválido → no es un destinatario utilizable
    if nm in PLACEHOLDER_CONTACT_NAMES and em in PLACEHOLDER_CONTACT_EMAILS:
        return True
    return False


def _is_placeholder_for_deletion(email: str, name: str = "") -> bool:
    """Más conservador que _is_placeholder_contact: usado para borrado FÍSICO.
    Solo elimina el patrón placeholder real (email basura conocido o nombre N/A
    sin email válido). NO borra contactos legítimos que simplemente no tengan
    correo (pueden tener nombre/teléfono útiles en la ficha)."""
    em = (email or "").strip().lower()
    nm = (name or "").strip().lower()
    if em in PLACEHOLDER_CONTACT_EMAILS:
        return True
    if nm in PLACEHOLDER_CONTACT_NAMES and ("@" not in em or em in PLACEHOLDER_CONTACT_EMAILS):
        return True
    return False


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
            # Consolidar: Principal (globales) + sucursal seleccionada (locales)
            client_docs = []
            principal = client
            if client.get("is_branch") and client.get("parent_client_id"):
                p = await db.clients.find_one({"client_id": client["parent_client_id"]}, {"_id": 0})
                if p:
                    principal = p
                    client_docs.append((p, "Principal"))
                    client_docs.append((client, client.get("sucursal") or "Sucursal"))
                else:
                    client_docs.append((client, "Principal"))
            else:
                client_docs.append((client, "Principal"))

            for cdoc, scope_label in client_docs:
                # Email principal del cliente (si existe) — solo del Principal
                if cdoc.get("email") and scope_label == "Principal":
                    contacts.append({
                        "email": cdoc["email"],
                        "label": client_label,
                        "name": client_label,
                        "contact_type": "Principal",
                        "source": "client",
                        "scope": scope_label,
                    })
                # Contactos CRM (array contacts)
                for c in cdoc.get("contacts", []):
                    if c.get("email"):
                        name = c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or "Contacto"
                        role = c.get("role") or c.get("contact_type") or "Otro"
                        contacts.append({
                            "email": c["email"],
                            "label": f"{name} · {scope_label}" if scope_label != "Principal" else name,
                            "name": name,
                            "contact_type": role,
                            "source": "client",
                            "scope": scope_label,
                            "purposes": c.get("purposes") or [],
                        })
                # Contactos legacy (contact1, contact2) — solo del Principal
                if scope_label == "Principal":
                    for key in ["contact1", "contact2"]:
                        legacy = cdoc.get(key)
                        if legacy and isinstance(legacy, dict) and legacy.get("email"):
                            legacy_name = legacy.get('name', key)
                            contacts.append({
                                "email": legacy["email"],
                                "label": legacy_name,
                                "name": legacy_name,
                                "contact_type": legacy.get("role") or "Contacto",
                                "source": "client",
                                "scope": scope_label,
                            })

            # Nivel 1 (herencia): contactos del Grupo Económico del Principal
            gid = principal.get("grupo_economico_id")
            if gid:
                grp = await db.economic_groups.find_one(
                    {"group_id": gid}, {"_id": 0, "name": 1, "contacts": 1}
                )
                if grp:
                    for c in (grp.get("contacts") or []):
                        if not (c.get("email") or "").strip():
                            continue
                        name = c.get("full_name") or "Contacto"
                        contacts.append({
                            "email": c["email"],
                            "label": f"{name} · Grupo Económico",
                            "name": name,
                            "contact_type": c.get("role") or "Otro",
                            "source": "client",
                            "scope": "grupo",
                            "grupo_economico_name": grp.get("name"),
                            "purposes": c.get("purposes") or [],
                        })

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
                        # Label compacto: solo nombre + tipo (sin repetir banco que ya va en bank_name)
                        label = f"{full} · {ctype}"
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
                        "label": f"{contact_name} · Principal",
                        "source": "bank",
                        "bank_name": bank_name,
                        "contact_type": "Principal",
                        "name": contact_name,
                    })

    # Deduplicar permitiendo el mismo email en distintas fuentes (cliente vs banco)
    # y en distintos bancos. Ej: si Manuel Suarez (Banco Mercantil) tiene el mismo
    # email que el contacto Cliente, ambos deben aparecer.
    seen_keys = set()
    unique_contacts = []
    for c in contacts:
        # Excluir contactos placeholder heredados (na@na.com, sin@email.com, N/A, etc.)
        if _is_placeholder_contact(c.get("email", ""), c.get("name") or c.get("label", "")):
            continue
        key = (c.get("email", "").lower(), c.get("source"), c.get("bank_name") or "")
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_contacts.append(c)

    return unique_contacts


@router.post("/admin/clean-placeholder-contacts")
async def clean_placeholder_contacts(authorization: Optional[str] = Header(None)):
    """[ADMIN] Purga física de contactos placeholder heredados de importaciones
    masivas (legacy contact1/contact2 con N/A · na@na.com · sin@email.com, y
    entradas inválidas en arrays contacts[] de clientes/bancos).

    Idempotente: puede ejecutarse varias veces sin efectos secundarios.
    Pensado para correrse una vez en producción tras el despliegue.
    """
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar esta acción")

    legacy_unset = 0
    clients_arr_cleaned = 0
    banks_arr_cleaned = 0

    # 1) Clientes: legacy contact1/contact2 placeholder -> $unset + filtrar contacts[]
    async for cl in db.clients.find({}, {"_id": 0, "client_id": 1, "contact1": 1, "contact2": 1, "contacts": 1}):
        unset = {}
        for k in ("contact1", "contact2"):
            lg = cl.get(k)
            if isinstance(lg, dict) and _is_placeholder_for_deletion(lg.get("email", ""), lg.get("name", "")):
                unset[k] = ""
        arr = cl.get("contacts") or []
        new_arr = [c for c in arr if not _is_placeholder_for_deletion(
            c.get("email", ""),
            c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}",
        )]
        arr_changed = len(new_arr) != len(arr)

        update = {}
        if unset:
            update["$unset"] = unset
            legacy_unset += len(unset)
        if arr_changed:
            update.setdefault("$set", {})["contacts"] = new_arr
            clients_arr_cleaned += (len(arr) - len(new_arr))
        if update:
            await db.clients.update_one({"client_id": cl["client_id"]}, update)

    # 2) Bancos: filtrar contacts[] (defensivo)
    async for bk in db.banks.find({}, {"_id": 0, "bank_id": 1, "name": 1, "contacts": 1}):
        arr = bk.get("contacts") or []
        new_arr = [c for c in arr if not _is_placeholder_for_deletion(
            c.get("email", ""),
            c.get("full_name") or f"{c.get('first_name', '')} {c.get('last_name', '')}",
        )]
        if len(new_arr) != len(arr):
            banks_arr_cleaned += (len(arr) - len(new_arr))
            await db.banks.update_one({"bank_id": bk.get("bank_id"), "name": bk.get("name")}, {"$set": {"contacts": new_arr}})

    total = legacy_unset + clients_arr_cleaned + banks_arr_cleaned
    return {
        "message": f"Limpieza completada. {total} contacto(s) placeholder eliminado(s).",
        "legacy_contacts_removed": legacy_unset,
        "client_array_contacts_removed": clients_arr_cleaned,
        "bank_array_contacts_removed": banks_arr_cleaned,
    }



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

async def _dispatch_implementer_response(project_id: str, ticket: str, current_user: dict):
    """Background: despacha la acción dinámica 'Respuesta del Implementador' al
    registrarse el Nro de Ticket de un proyecto. Si el admin no configuró la
    acción (o está desactivada), `dispatch_other_action` simplemente no envía nada."""
    try:
        from services.other_actions_engine import dispatch_other_action
        from services.project_template_vars import resolve_project_template_vars
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        if not project:
            return
        tvars = await resolve_project_template_vars(project, actor_user=current_user)
        tvars["ticket_number"] = ticket
        tvars["Nro_Ticket"] = ticket
        tvars["usuario_ejecutor"] = (
            f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            or current_user.get("email", "")
        )
        tvars["fecha_sistema"] = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        await dispatch_other_action(
            action_id="implementer_response",
            template_vars=tvars,
            current_user=current_user,
            fallback_subject=f"Respuesta del Implementador — Ticket {ticket}",
            executive_user_id=project.get("created_by_user_id"),
        )
    except Exception as e:
        logger.warning(f"[ticket] dispatch implementer_response failed: {e}")


# Estado del proyecto → action_id de "Otras Acciones" (notificaciones de estado).
_PROJECT_STATUS_ACTION_MAP = {
    "Congelado": "project_status_congelado",
    "Suspendido": "project_status_suspendido",
    "Implementado parcial": "project_status_implementado_parcial",
    "Culminado": "project_status_culminado",
}


async def _dispatch_project_status_action(project_id: str, new_status: str, note: Optional[str], current_user: dict):
    """Background: despacha la acción dinámica de cambio de estado del Proyecto
    (Suspendido / Implementado parcial / Culminado) configurada en "Otras
    Acciones". Se llama DESPUÉS de persistir el cambio (y el comentario/anexo del
    modal de justificación). Si el admin no configuró la acción o está
    desactivada, `dispatch_other_action` no envía nada (cero regresión)."""
    action_id = _PROJECT_STATUS_ACTION_MAP.get(new_status)
    if not action_id:
        return
    try:
        from services.other_actions_engine import dispatch_other_action
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
        if not project:
            return
        tvars = await resolve_project_template_vars(project, actor_user=current_user)
        comentario = (note or "").strip()
        tvars["Comentario_Estado"] = comentario
        tvars["Comentario_Cierre"] = comentario
        tvars["Motivo_Cambio_Estatus"] = comentario
        tvars["Estado_Proyecto"] = new_status
        # Congelamiento: variables propias (motivo y días acumulados congelado).
        if new_status == "Congelado":
            tvars["Motivo_Congelamiento"] = comentario
            frozen_at = project.get("frozen_at")
            dias = 0
            if frozen_at:
                try:
                    fa = datetime.fromisoformat(str(frozen_at).replace("Z", "+00:00"))
                    if fa.tzinfo is None:
                        fa = fa.replace(tzinfo=timezone.utc)
                    dias = max(0, (datetime.now(timezone.utc) - fa).days)
                except Exception:
                    dias = 0
            tvars["Dias_Congelado"] = str(dias)
        tvars["usuario_ejecutor"] = (
            f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            or current_user.get("email", "")
        )
        tvars["fecha_sistema"] = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        await dispatch_other_action(
            action_id=action_id,
            template_vars=tvars,
            current_user=current_user,
            fallback_subject=f"Proyecto {project.get('project_number', '')} — {new_status}",
            executive_user_id=project.get("created_by_user_id"),
            project=project,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[project-status] dispatch '{new_status}' failed: {e}")




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

    # Valor anterior: detecta la transición vacío → valor para disparar la
    # acción dinámica "Respuesta del Implementador".
    prev_ticket = (project.get("ticket_number") or "").strip()

    # Verificar unicidad del ticket — FLEXIBLE: si el ticket ya existe en otro
    # proyecto y el usuario NO ha confirmado, devolvemos una advertencia (409)
    # con el Nombre de Fantasía del cliente del otro proyecto para que el
    # usuario decida si desea continuar (hay casos de negocio donde un mismo
    # ticket aplica a varios proyectos).
    existing = await db.projects.find_one(
        {"ticket_number": ticket, "project_id": {"$ne": project_id}},
        {"_id": 0, "project_id": 1, "project_number": 1, "client_id": 1, "client_name": 1},
    )
    if existing and not body.confirm_duplicate:
        fantasy = ""
        if existing.get("client_id"):
            cdoc = await db.clients.find_one(
                {"client_id": existing["client_id"]},
                {"_id": 0, "fantasy_name": 1, "legal_name": 1},
            )
            if cdoc:
                fantasy = cdoc.get("fantasy_name") or cdoc.get("legal_name") or ""
        if not fantasy:
            fantasy = existing.get("client_name") or "otro cliente"
        existing_pnum = existing.get("project_number", "") or ""
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ticket_duplicate",
                "existing_client_fantasy": fantasy,
                "existing_project_number": existing_pnum,
                "message": (
                    f"El Número de Ticket '{ticket}' ya está asociado al cliente "
                    f"\"{fantasy}\""
                    + (f" (proyecto {existing_pnum})" if existing_pnum else "")
                    + ". ¿Desea continuar y asignarlo también a este proyecto?"
                ),
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    note = {
        "note_id": f"pn_{uuid.uuid4().hex[:8]}",
        "text": f"Ticket registrado: {ticket} (por {user_name})",
        "created_by": current_user.get("user_id", ""),
        "created_by_name": user_name,
        "created_at": now,
    }

    update_set = {"ticket_number": ticket, "unblocked_at": now, "updated_at": now}

    # Gatillo de Activación Operativa: al guardar el Nro de Ticket el estado pasa
    # automáticamente a "En Gestión", salvo que el proyecto ya esté en un estado
    # manual (Suspendido / Implementado parcial / Culminado), que se respeta.
    from models import PROJECT_MANUAL_STATUSES
    if (project.get("status") or "") not in PROJECT_MANUAL_STATUSES:
        update_set["status"] = "En Gestión"
        update_set["status_changed_at"] = now

    # Proyectos Directos: el Nro. de Ticket es condición suficiente para desbloquear
    # la ejecución (matriz incluida). El envío de notificaciones por correo es
    # OPCIONAL para este tipo de proyectos (nacen fuera del cotizador comercial),
    # por lo que marcamos la matriz como desbloqueada sin exigir la "Primera
    # Comunicación". Para proyectos estándar el flujo de notificación no cambia.
    if project.get("direct_project") and not project.get("client_notified"):
        update_set["client_notified"] = True
        update_set["client_notified_at"] = now
        update_set["client_notified_by"] = user_name
        note["text"] = (
            f"Ticket registrado: {ticket} (por {user_name}) — Proyecto Directo "
            f"desbloqueado sin envío de notificación (notificación opcional)."
        )

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": update_set, "$push": {"notes": note}}
    )

    # Disparar "Respuesta del Implementador" en background SOLO cuando el ticket
    # pasa de vacío → valor y el ejecutor es Implementador (admin permitido para QA).
    cargo_l = (current_user.get("cargo") or "").lower()
    is_impl = ("implementador" in cargo_l) or (current_user.get("role") == "admin")
    if not prev_ticket and ticket and is_impl:
        import asyncio
        asyncio.create_task(_dispatch_implementer_response(project_id, ticket, current_user))

    return {"message": f"Ticket '{ticket}' registrado exitosamente", "ticket_number": ticket, "direct_unlock": bool(project.get("direct_project"))}


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


def _compress_image(data: bytes, ext: str):
    """Compresión ligera para imágenes pegadas: reescala a máx 1600px y recomprime,
    reduciendo el peso de los correos. GIF (posible animación) se deja intacto.
    Retorna (bytes, ext, content_type). Si algo falla, devuelve el original."""
    ext = (ext or "png").lower()
    if ext == "gif":
        return data, ext, MIME_TYPES.get(ext, "image/gif")
    try:
        from io import BytesIO
        from PIL import Image as PILImage

        img = PILImage.open(BytesIO(data))
        max_dim = 1600
        if max(img.size) > max_dim:
            ratio = max_dim / float(max(img.size))
            img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), PILImage.LANCZOS)

        out = BytesIO()
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        if ext in ("jpg", "jpeg") and not has_alpha:
            img.convert("RGB").save(out, format="JPEG", quality=82, optimize=True)
            return out.getvalue(), "jpg", "image/jpeg"
        if ext == "webp":
            img.save(out, format="WEBP", quality=82, method=4)
            return out.getvalue(), "webp", "image/webp"
        # PNG (o JPG con transparencia → se preserva como PNG)
        img.save(out, format="PNG", optimize=True)
        return out.getvalue(), "png", "image/png"
    except Exception as e:
        logger.warning(f"[upload_image] compresión omitida: {e}")
        return data, ext, MIME_TYPES.get(ext, "application/octet-stream")


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

    # Compresión ligera (reescala + recomprime) para aligerar los correos.
    data, ext, content_type = _compress_image(data, ext)

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


# =====================================================================
# REPORTE: Carga y Estatus agrupado por Implementador (PDF)
# =====================================================================

_TYPE_LABEL = {"VPOS": "VPOS", "MPOS": "MPOS", "GATEWAY": "Payment", "LINK": "Link de Pago", "VPOS_MULTIRIF": "VPOS-MR"}
# Etiqueta completa para encabezados de sección/resumen (no se trunca como el badge).
_TYPE_FULL_LABEL = {"VPOS": "VPOS", "MPOS": "MPOS", "GATEWAY": "Payment Gateway", "LINK": "Link de Pago", "VPOS_MULTIRIF": "VPOS Multi-RIF"}
_TYPE_BADGE_CSS = {
    "VPOS":          ("#dbeafe", "#1e40af", "#bfdbfe"),
    "MPOS":          ("#d1fae5", "#065f46", "#a7f3d0"),
    "GATEWAY":       ("#ede9fe", "#5b21b6", "#ddd6fe"),
    "LINK":          ("#f1f5f9", "#334155", "#e2e8f0"),
    "VPOS_MULTIRIF": ("#cffafe", "#155e75", "#a5f3fc"),
}

# Tipos de proyecto que aportan "Cajas" (PDVs). VPOS Multi-RIF también las cuenta
# (su total se distribuye entre RIFs/sucursales pero suma a la carga del implementador).
_CAJAS_TYPES = {"VPOS", "MPOS", "VPOS_MULTIRIF"}


def _counts_cajas(qt: Optional[str]) -> bool:
    return (qt or "").upper() in _CAJAS_TYPES


def _project_total_cajas(p: dict) -> int:
    """Total de cajas de un proyecto. En Multi-RIF las cajas viven en rifs/stores,
    por lo que `cantidad_cajas` puede venir vacío: se cae a `box_count` y, en último
    término, a la suma de `box_count` de los RIFs."""
    try:
        c = int(p.get("cantidad_cajas") or p.get("box_count") or 0)
    except (TypeError, ValueError):
        c = 0
    if c <= 0 and p.get("rifs"):
        c = sum(int(r.get("box_count") or 0) for r in (p.get("rifs") or []))
    return c


def _norm_type(qt: Optional[str]) -> str:
    """Normaliza el quote_type a las categorías canónicas (VPOS/MPOS/GATEWAY/LINK/VPOS_MULTIRIF)."""
    t = (qt or "").upper()
    if t in ("LINK_PAGO", "LINK"):
        return "LINK"
    if t == "FAST_TRACK":
        return "MPOS"
    return t


def _format_es_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        return iso[:10] if len(iso) >= 10 else iso


async def _workload_dataset(
    assigned_to: Optional[List[str]],
    original_implementer: Optional[List[str]],
    status: Optional[List[str]],
    client: Optional[str],
    quote_type: Optional[List[str]],
    date_from: Optional[str],
    date_to: Optional[str],
    generator: Optional[List[str]] = None,
) -> list:
    """Consulta, enriquece (cajas, PVV, días hábiles, % avance) y filtra los
    proyectos para el Reporte de Carga. Compartido por las salidas PDF y Excel
    para garantizar consistencia total de datos y filtros entre ambos formatos.
    """
    # Normalizar el rango de Periodo de Asignación (YYYY-MM-DD). Solo la porción
    # de fecha; assigned_at se guarda como ISO string, comparable lexicográficamente.
    _df = (date_from or "").strip()[:10] or None
    _dt = (date_to or "").strip()[:10] or None

    projects = await db.projects.find(
        {},
        {
            "_id": 0,
            "project_id": 1, "client_name": 1, "client_rif": 1,
            "quote_type": 1, "status": 1, "cantidad_cajas": 1, "box_count": 1,
            "assigned_to_name": 1, "assigned_at": 1,
            "created_by_name": 1, "created_by_user_id": 1,
            "last_contact_at": 1, "last_contact_by": 1,
            "reassigned_from_name": 1, "reassignment_history": 1,
            "fantasy_name": 1,
            "implementation_matrix": 1,
            "project_type": 1, "rifs": 1,
            "status_changed_at": 1, "sent_to_implementation_at": 1,
            "created_at": 1, "unblocked_at": 1,
            "stores": 1, "is_multistore": 1,
        },
    ).to_list(5000)

    def _avance_cell_html(pct: int) -> str:
        color = "#16a34a" if pct >= 100 else "#d97706" if pct > 0 else "#94a3b8"
        return f'<span style="font-weight:700;color:{color};">{pct}%</span>'

    from services.project_pvv import compute_project_pvv
    from services.business_calendar import get_holiday_sets, business_days_between
    from services.project_sla_engine import stage_entered_at
    _specific, _recurring = await get_holiday_sets()
    _today = datetime.now(timezone.utc).date()
    for _p in projects:
        _p["_cajas"] = _project_total_cajas(_p)
        _p["box_count"] = _p["_cajas"]
        _p["_pvv"] = compute_project_pvv(_p)
        _entered = stage_entered_at(_p)
        _p["_bdays"] = business_days_between(_entered.date(), _today, _specific, _recurring) if _entered else 0
        if _p.get("stores"):
            _prog = _calculate_rollup_progress(_p)
        else:
            _prog = _calculate_single_progress(_p)
        _p["_avance"] = int(round(_prog.get("global_progress", 0) or 0))
        _p["_avance_html"] = _avance_cell_html(_p["_avance"])

    def _matches(p: dict) -> bool:
        if assigned_to:
            impl_now = p.get("assigned_to_name") or "Sin asignar"
            if impl_now not in assigned_to:
                return False
        if original_implementer:
            orig = p.get("reassigned_from_name") or ""
            if orig not in original_implementer:
                return False
        if status:
            if (p.get("status") or "") not in status:
                return False
        if client:
            q = client.strip().lower()
            haystack = " ".join([
                str(p.get("client_name") or ""),
                str(p.get("fantasy_name") or ""),
                str(p.get("client_rif") or ""),
            ]).lower()
            if q not in haystack:
                return False
        if quote_type:
            qt = _norm_type(p.get("quote_type"))
            wanted = [_norm_type(t) for t in quote_type]
            if qt not in wanted:
                return False
        if generator:
            if (p.get("created_by_name") or "Sin generador") not in generator:
                return False
        if _df or _dt:
            a = p.get("assigned_at")
            if not a:
                return False
            day = str(a)[:10]
            if _df and day < _df:
                return False
            if _dt and day > _dt:
                return False
        return True

    return [p for p in projects if _matches(p)]


@router.get("/projects/reports/workload-pdf")
async def projects_workload_pdf(
    authorization: Optional[str] = Header(None),
    assigned_to: Optional[List[str]] = Query(None, description="Filtrar por Implementador Actual (nombre). Multi-select."),
    original_implementer: Optional[List[str]] = Query(None, description="Filtrar por Implementador Original (reasignados). Multi-select."),
    status: Optional[List[str]] = Query(None, description="Filtrar por Estatus. Multi-select."),
    client: Optional[str] = Query(None, description="Búsqueda parcial por Razón Social o Nombre de Fantasía del cliente."),
    quote_type: Optional[List[str]] = Query(None, description="Filtrar por Tipo de Proyecto (VPOS, MPOS, GATEWAY, LINK). Multi-select."),
    date_from: Optional[str] = Query(None, description="Periodo de Asignación — Desde (YYYY-MM-DD). Filtra por Fecha de Asignación (assigned_at)."),
    date_to: Optional[str] = Query(None, description="Periodo de Asignación — Hasta (YYYY-MM-DD, inclusive). Filtra por Fecha de Asignación (assigned_at)."),
    generator: Optional[List[str]] = Query(None, description="Filtrar por Generador del Proyecto (created_by_name). Multi-select."),
    group_by: str = Query("implementer", description="Modo de agrupación del reporte: 'implementer' (por implementador, default) o 'type' (por Tipo de Proyecto)."),
):
    """PDF: carga de proyectos agrupados por implementador.
    Columnas: Cliente, Generador, Tipo (badge), Cajas (solo VPOS/MPOS), Implementador
    Original (si reasignado), Fecha asignación, Último contacto.
    Acceso: usuarios con permiso `proyectos`. Accesible para admin, coordinadores y gerentes.
    Soporta filtros multi-selección (parámetros repetibles en query).
    """
    import weasyprint

    user = await get_current_user(authorization)

    # Normalizar rango para el chip del PDF (el filtrado real vive en el helper).
    _df = (date_from or "").strip()[:10] or None
    _dt = (date_to or "").strip()[:10] or None

    projects = await _workload_dataset(
        assigned_to, original_implementer, status, client, quote_type, date_from, date_to, generator,
    )

    # Agrupar por implementador asignado
    groups: dict = {}
    cajas_by_impl: dict = {}
    pvv_by_impl: dict = {}  # Iter39: sumatoria PVV por implementador
    for p in projects:
        impl = p.get("assigned_to_name") or "Sin asignar"
        groups.setdefault(impl, []).append(p)
        # Sumar cajas solo de VPOS/MPOS/VPOS-MR (igual criterio que la columna "Cajas" del PDF)
        qt = (p.get("quote_type") or "").upper()
        if _counts_cajas(qt):
            cajas_by_impl[impl] = cajas_by_impl.get(impl, 0) + int(p.get("_cajas") or 0)
        else:
            cajas_by_impl.setdefault(impl, 0)
        # PVV se acumula SIEMPRE (todos los tipos de proyecto generan terminales virtuales).
        pvv_by_impl[impl] = pvv_by_impl.get(impl, 0) + int(p.get("_pvv") or 0)

    # Iter39: orden de implementadores por PVV total descendente (en lugar de cantidad de proyectos).
    # "Sin asignar" siempre al final independientemente de su volumen.
    ordered = sorted(
        groups.keys(),
        key=lambda k: (k == "Sin asignar", -pvv_by_impl.get(k, 0), -len(groups[k]), k),
    )

    # HTML
    section_html_parts = []
    for impl in ordered:
        items = groups[impl]
        rows_html = ""
        for p in items:
            qt = (p.get("quote_type") or "").upper()
            label = _TYPE_LABEL.get(qt, "—")
            bg, fg, br = _TYPE_BADGE_CSS.get(qt, ("#f8fafc", "#475569", "#e2e8f0"))
            type_badge = (
                f'<span style="display:inline-block; padding:2px 6px; font-size:9px; font-weight:600; '
                f'border-radius:4px; background:{bg}; color:{fg}; border:1px solid {br};">{label}</span>'
                if label != "—" else '<span class="muted">—</span>'
            )
            # Cajas para VPOS/MPOS/VPOS-MR (Multi-RIF suma su total distribuido)
            cajas = ""
            if _counts_cajas(qt):
                c = p.get("_cajas") or 0
                cajas = str(c) if c else "—"
            else:
                cajas = "—"
            # Iter39: PVV por proyecto (se aplica a todos los tipos de proyecto).
            pvv_val = int(p.get("_pvv") or 0)
            pvv_cell = str(pvv_val) if pvv_val > 0 else "—"
            # Implementador original (solo si reasignado)
            orig = p.get("reassigned_from_name") or ""
            is_reassigned = bool(orig)
            orig_html = f'<span class="orig">{orig}</span>' if (is_reassigned and orig) else '<span class="muted">—</span>'
            rows_html += f"""
            <tr>
              <td>{p.get('client_name') or '—'}<div class="rif">{p.get('client_rif') or ''}</div></td>
              <td class="gen">{p.get('created_by_name') or '—'}</td>
              <td>{type_badge}</td>
              <td class="num">{cajas}</td>
              <td class="num pvv">{pvv_cell}</td>
              <td class="state">{p.get('status') or '—'}</td>
              <td class="num avance">{p.get('_avance_html', '—')}</td>
              <td class="num bdays">{p.get('_bdays', 0)}</td>
              <td>{orig_html}</td>
              <td class="date">{_format_es_date(p.get('assigned_at'))}</td>
              <td class="date">{_format_es_date(p.get('last_contact_at'))}</td>
            </tr>
            """
        section_html_parts.append(f"""
        <div class="group">
          <div class="group-head">
            <span class="impl">{impl}</span>
            <span class="count">Nro de Proyectos {len(items)} &nbsp;·&nbsp; Nro de Cajas {cajas_by_impl.get(impl, 0)} &nbsp;·&nbsp; <strong>Total PVV {pvv_by_impl.get(impl, 0)}</strong></span>
          </div>
          <table class="rep">
            <colgroup>
              <col class="c-cliente" />
              <col class="c-gen" />
              <col class="c-tipo" />
              <col class="c-cajas" />
              <col class="c-pvv" />
              <col class="c-estado" />
              <col class="c-avance" />
              <col class="c-bdays" />
              <col class="c-orig" />
              <col class="c-fasign" />
              <col class="c-ultcont" />
            </colgroup>
            <thead>
              <tr>
                <th>Cliente</th><th>Generador</th><th>Tipo</th><th>Cajas</th><th>PVV</th>
                <th>Estado</th><th>% Avance</th><th>Días háb.</th><th>Implementador Original</th>
                <th>Fecha Asignación</th><th>Último Contacto</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
        """)

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    exec_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get('email','')
    total = sum(len(v) for v in groups.values())
    total_cajas = sum(cajas_by_impl.values())
    total_pvv = sum(pvv_by_impl.values())  # Iter39

    # --- Ranking visual: TODOS los implementadores ordenados por PVV (Iter39).
    # Excluye "Sin asignar" para no comparar un grupo huérfano contra personas reales.
    ranking_items = [
        (impl, pvv_by_impl.get(impl, 0), len(groups.get(impl, [])), cajas_by_impl.get(impl, 0))
        for impl in groups.keys()
        if impl != "Sin asignar"
    ]
    # Orden estricto descendente por PVV; desempate por #proyectos desc, luego cajas desc, luego nombre.
    ranking_items.sort(key=lambda x: (-x[1], -x[2], -x[3], x[0]))
    ranking_html = ""
    if ranking_items:
        max_pvv = max((p for _, p, _, _ in ranking_items), default=0) or 1
        medals = {0: "#FFD700", 1: "#C0C0C0", 2: "#CD7F32"}  # oro, plata, bronce
        cards = []
        for idx, (impl, pvv, n_proj, cajas) in enumerate(ranking_items):
            bar_pct = int(round((pvv / max_pvv) * 100)) if max_pvv else 0
            medal_color = medals.get(idx, "#475569")
            text_color = "#0f172a" if idx < 3 else "#e2e8f0"
            position_label = f"{idx + 1}°"
            cards.append(f"""
            <div class="rank-card">
              <div class="rank-pos" style="background:{medal_color}; color:{text_color};">{position_label}</div>
              <div class="rank-body">
                <div class="rank-impl">{impl}</div>
                <div class="rank-bar-bg"><div class="rank-bar" style="width:{bar_pct}%;"></div></div>
                <div class="rank-stats"><strong>{pvv}</strong> PVV · {n_proj} proyecto(s) · {cajas} caja(s)</div>
              </div>
            </div>
            """)
        ranking_html = f"""
        <div class="ranking">
          <div class="ranking-title">Ranking de Carga — Implementadores por PVV</div>
          <div class="ranking-grid">
            {''.join(cards)}
          </div>
        </div>
        """

    group_label = "Implementador"

    # ── Modo de agrupación alterno: por Tipo de Proyecto (group_by=type) ──
    # Reconstruye las secciones agrupando por tipo y reemplaza el ranking de
    # implementadores por un resumen del mix comercial. Los totales globales
    # (total / total_cajas / total_pvv) son independientes de la agrupación.
    if group_by == "type":
        group_label = "Tipo de Proyecto"
        type_groups: dict = {}
        for p in projects:
            type_groups.setdefault(_norm_type(p.get("quote_type")) or "SIN", []).append(p)
        type_order = ["VPOS", "VPOS_MULTIRIF", "MPOS", "GATEWAY", "LINK"]
        ordered_types = [t for t in type_order if t in type_groups] + [k for k in type_groups if k not in type_order]
        section_html_parts = []
        type_summary_data = []
        for tkey in ordered_types:
            items = type_groups[tkey]
            tlabel = _TYPE_FULL_LABEL.get(tkey, "Sin Tipo")
            n_t = len(items)
            cajas_t = 0
            pvv_t = 0
            rows_html = ""
            for p in items:
                qtn = _norm_type(p.get("quote_type"))
                label = _TYPE_LABEL.get(qtn, "—")
                bg, fg, br = _TYPE_BADGE_CSS.get(qtn, ("#f8fafc", "#475569", "#e2e8f0"))
                type_badge = (
                    f'<span style="display:inline-block; padding:2px 6px; font-size:9px; font-weight:600; '
                    f'border-radius:4px; background:{bg}; color:{fg}; border:1px solid {br};">{label}</span>'
                    if label != "—" else '<span class="muted">—</span>'
                )
                if _counts_cajas(qtn):
                    c = int(p.get("_cajas") or 0)
                    cajas_t += c
                    cajas = str(c) if c else "—"
                else:
                    cajas = "—"
                pvv_val = int(p.get("_pvv") or 0)
                pvv_t += pvv_val
                pvv_cell = str(pvv_val) if pvv_val > 0 else "—"
                if p.get("assigned_to_name"):
                    impl_html = f'<span style="color:#4338ca; font-weight:500;">{p.get("assigned_to_name")}</span>'
                else:
                    impl_html = '<span class="muted">Sin asignar</span>'
                rows_html += f"""
                <tr>
                  <td>{p.get('client_name') or '—'}<div class="rif">{p.get('client_rif') or ''}</div></td>
                  <td class="gen">{p.get('created_by_name') or '—'}</td>
                  <td>{type_badge}</td>
                  <td class="num">{cajas}</td>
                  <td class="num pvv">{pvv_cell}</td>
                  <td class="state">{p.get('status') or '—'}</td>
                  <td class="num avance">{p.get('_avance_html', '—')}</td>
                  <td class="num bdays">{p.get('_bdays', 0)}</td>
                  <td>{impl_html}</td>
                  <td class="date">{_format_es_date(p.get('assigned_at'))}</td>
                  <td class="date">{_format_es_date(p.get('last_contact_at'))}</td>
                </tr>
                """
            section_html_parts.append(f"""
            <div class="group">
              <div class="group-head" style="background:#f5f3ff; border-left-color:#7c3aed;">
                <span class="impl" style="color:#6d28d9;">{tlabel}</span>
                <span class="count" style="color:#7c3aed;">Nro de Proyectos {n_t} &nbsp;·&nbsp; Nro de Cajas {cajas_t} &nbsp;·&nbsp; <strong>Total PVV {pvv_t}</strong></span>
              </div>
              <table class="rep">
                <colgroup>
                  <col class="c-cliente" /><col class="c-gen" /><col class="c-tipo" /><col class="c-cajas" /><col class="c-pvv" />
                  <col class="c-estado" /><col class="c-avance" /><col class="c-bdays" /><col class="c-orig" /><col class="c-fasign" /><col class="c-ultcont" />
                </colgroup>
                <thead>
                  <tr>
                    <th>Cliente</th><th>Generador</th><th>Tipo</th><th>Cajas</th><th>PVV</th>
                    <th>Estado</th><th>% Avance</th><th>Días háb.</th><th>Implementador</th>
                    <th>Fecha Asignación</th><th>Último Contacto</th>
                  </tr>
                </thead>
                <tbody>{rows_html}</tbody>
              </table>
            </div>
            """)
            type_summary_data.append((tlabel, n_t, cajas_t, pvv_t))

        max_n = max((d[1] for d in type_summary_data), default=0) or 1
        cards = []
        for tlabel, n_t, cajas_t, pvv_t in type_summary_data:
            bar_pct = int(round((n_t / max_n) * 100)) if max_n else 0
            pct_total = int(round((n_t / total) * 100)) if total else 0
            cards.append(f"""
            <div style="background:#1e293b; border:1px solid #334155; border-radius:6px; padding:10px;">
              <div style="font-size:11px; font-weight:700; color:#f1f5f9; margin-bottom:6px;">{tlabel}</div>
              <div style="height:4px; background:#334155; border-radius:2px; overflow:hidden; margin-bottom:6px;">
                <div style="height:100%; width:{bar_pct}%; background:linear-gradient(90deg,#7c3aed,#a78bfa);"></div>
              </div>
              <div style="font-size:9px; color:#cbd5e1;"><strong style="color:#a78bfa; font-size:13px;">{n_t}</strong> proyecto(s) · {pct_total}% · {cajas_t} caja(s) · {pvv_t} PVV</div>
            </div>
            """)
        ranking_html = f"""
        <div class="ranking" style="background:#0f172a;">
          <div class="ranking-title" style="color:#a78bfa;">Resumen del Mix por Tipo de Proyecto</div>
          <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px;">
            {''.join(cards) if cards else '<span style="color:#cbd5e1; font-size:10px;">Sin proyectos.</span>'}
          </div>
        </div>
        """

    # Construir resumen de filtros aplicados (si los hay)
    filters_chips: list[str] = []
    if assigned_to:
        filters_chips.append(f"Implementador Actual: {', '.join(assigned_to)}")
    if original_implementer:
        filters_chips.append(f"Implementador Original: {', '.join(original_implementer)}")
    if status:
        filters_chips.append(f"Estatus: {', '.join(status)}")
    if client:
        filters_chips.append(f"Cliente: {client}")
    if quote_type:
        filters_chips.append(f"Tipo: {', '.join(_TYPE_FULL_LABEL.get(t.upper(), t.upper()) for t in quote_type)}")
    if generator:
        filters_chips.append(f"Generador: {', '.join(generator)}")
    if _df or _dt:
        _periodo = f"Desde {_format_es_date(_df) if _df else '—'} — Hasta {_format_es_date(_dt) if _dt else '—'}"
        filters_chips.append(f"Periodo de Asignación: {_periodo}")
    filters_html = ""
    if filters_chips:
        chips = "".join(
            f'<span style="display:inline-block; background:#eef2ff; color:#3730a3; border:1px solid #c7d2fe; padding:2px 8px; border-radius:10px; font-size:9px; margin:2px 4px 2px 0;">{c}</span>'
            for c in filters_chips
        )
        filters_html = f'<div class="filters"><strong>Filtros aplicados:</strong> {chips}</div>'

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
    <meta charset="utf-8" />
    <style>
      @page {{ size: A4 landscape; margin: 1.5cm 1.2cm; }}
      body {{ font-family: 'Helvetica', Arial, sans-serif; color: #1e293b; font-size: 10px; }}
      h1 {{ font-size: 18px; margin: 0 0 4px; color: #0f172a; }}
      .sub {{ color: #64748b; font-size: 10px; margin-bottom: 14px; }}
      .filters {{
        background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
        padding: 6px 10px; margin-bottom: 14px; font-size: 10px; color: #475569;
      }}
      .filters strong {{ color: #312e81; margin-right: 4px; }}
      .group {{ margin-bottom: 18px; }}
      .group-head {{
        display: flex; justify-content: space-between; align-items: baseline;
        background: #eef2ff; border-left: 4px solid #4f46e5; padding: 6px 10px; border-radius: 4px;
        break-after: avoid;
      }}
      .group-head .impl {{ font-weight: 700; font-size: 13px; color: #312e81; }}
      .group-head .count {{ font-size: 10px; color: #4338ca; font-weight: 600; }}
      table.rep {{ width: 100%; border-collapse: collapse; margin-top: 6px; table-layout: fixed; }}
      /* Anchos fijos por columna para que TODAS las tablas (por implementador) queden alineadas */
      table.rep col.c-cliente  {{ width: 15%; }}
      table.rep col.c-gen      {{ width: 11%; }}
      table.rep col.c-tipo     {{ width: 5%; }}
      table.rep col.c-cajas    {{ width: 4%; }}
      table.rep col.c-pvv      {{ width: 4%; }}
      table.rep col.c-estado   {{ width: 10%; }}
      table.rep col.c-avance   {{ width: 6%; }}
      table.rep col.c-bdays    {{ width: 5%; }}
      table.rep col.c-orig     {{ width: 12%; }}
      table.rep col.c-fasign   {{ width: 14%; }}
      table.rep col.c-ultcont  {{ width: 14%; }}
      table.rep td.gen {{ font-size: 9px; color: #475569; }}
      table.rep td.pvv {{ font-weight: 700; color: #4f46e5; }}
      table.rep td.bdays {{ font-weight: 700; color: #0f766e; }}
      table.rep th {{
        background: #f8fafc; color: #475569; text-transform: uppercase; font-size: 8px;
        padding: 5px 6px; border-bottom: 1px solid #e2e8f0; text-align: left;
      }}
      table.rep td {{
        padding: 6px; border-bottom: 1px solid #f1f5f9; font-size: 10px; vertical-align: top;
        word-wrap: break-word; overflow-wrap: break-word;
      }}
      table.rep td.num {{ text-align: center; font-variant-numeric: tabular-nums; }}
      table.rep td.date {{ font-variant-numeric: tabular-nums; color: #334155; }}
      table.rep td.state {{ color: #0f172a; font-weight: 500; }}
      .rif {{ color: #94a3b8; font-size: 9px; font-family: monospace; }}
      .orig {{ color: #b45309; font-weight: 500; }}
      .muted {{ color: #cbd5e1; }}
      .footer {{
        margin-top: 20px; padding-top: 8px; border-top: 1px solid #e2e8f0;
        color: #94a3b8; font-size: 9px; display: flex; justify-content: space-between;
      }}
      /* Mini ranking */
      .ranking {{
        margin-top: 22px; padding: 12px 14px; background: #0f172a; border-radius: 8px;
        color: #f8fafc; break-inside: avoid;
      }}
      .ranking-title {{
        font-size: 11px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.5px; color: #fbbf24; margin-bottom: 10px;
      }}
      .ranking-grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
      }}
      .rank-card {{
        flex: 1; background: #1e293b; border: 1px solid #334155; border-radius: 6px;
        padding: 8px 10px; display: flex; gap: 8px; align-items: stretch;
      }}
      .rank-pos {{
        flex: 0 0 28px; width: 28px; height: 28px; border-radius: 50%;
        font-weight: 800; font-size: 11px; color: #0f172a;
        display: flex; align-items: center; justify-content: center;
        align-self: center;
      }}
      .rank-body {{ flex: 1; min-width: 0; }}
      .rank-impl {{
        font-size: 11px; font-weight: 700; color: #f1f5f9;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px;
      }}
      .rank-bar-bg {{
        height: 4px; background: #334155; border-radius: 2px; overflow: hidden; margin-bottom: 4px;
      }}
      .rank-bar {{
        height: 100%; background: linear-gradient(90deg, #4f46e5, #6366f1);
      }}
      .rank-stats {{ font-size: 9px; color: #cbd5e1; }}
      .rank-stats strong {{ color: #fbbf24; font-size: 11px; }}
    </style>
    </head>
    <body>
      <h1>Reporte de Carga y Estatus de Proyectos</h1>
      <div class="sub">Agrupado por {group_label} · Total: {total} proyecto(s) · {total_cajas} caja(s) · <strong>{total_pvv} PVV</strong> · Generado: {now_str} · Por: {exec_name}</div>
      {filters_html}
      {''.join(section_html_parts) if section_html_parts else '<p style="color:#64748b;font-style:italic">No hay proyectos registrados.</p>'}
      {ranking_html}
      <div class="footer">
        <span>MegaNexus · Departamento de Implementación</span>
        <span>{now_str}</span>
      </div>
    </body>
    </html>
    """

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"carga_implementadores_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/reports/workload-xlsx")
async def projects_workload_xlsx(
    authorization: Optional[str] = Header(None),
    assigned_to: Optional[List[str]] = Query(None),
    original_implementer: Optional[List[str]] = Query(None),
    status: Optional[List[str]] = Query(None),
    client: Optional[str] = Query(None),
    quote_type: Optional[List[str]] = Query(None),
    date_from: Optional[str] = Query(None, description="Periodo de Asignación — Desde (YYYY-MM-DD)."),
    date_to: Optional[str] = Query(None, description="Periodo de Asignación — Hasta (YYYY-MM-DD, inclusive)."),
    generator: Optional[List[str]] = Query(None, description="Filtrar por Generador del Proyecto (created_by_name). Multi-select."),
    group_by: str = Query("implementer", description="'implementer' o 'type'."),
):
    """Excel (.xlsx) del Reporte de Carga. Mismos filtros y datos que el PDF
    (comparten `_workload_dataset`). Una hoja con encabezado, resumen de filtros,
    tabla con autofiltro y fila de totales.
    """
    import io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    await get_current_user(authorization)

    _df = (date_from or "").strip()[:10] or None
    _dt = (date_to or "").strip()[:10] or None

    projects = await _workload_dataset(
        assigned_to, original_implementer, status, client, quote_type, date_from, date_to, generator,
    )

    # Orden: por dimensión de agrupación (implementador o tipo), luego cliente.
    def _grp_key(p):
        if group_by == "type":
            return (_TYPE_FULL_LABEL.get(_norm_type(p.get("quote_type")), "Sin Tipo"), p.get("client_name") or "")
        impl = p.get("assigned_to_name") or "Sin asignar"
        return (impl == "Sin asignar", impl, p.get("client_name") or "")
    projects_sorted = sorted(projects, key=_grp_key)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte de Carga"

    # Estilos
    title_font = Font(size=14, bold=True, color="1E1B4B")
    sub_font = Font(size=9, color="64748B")
    header_font = Font(size=9, bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4F46E5")
    total_font = Font(size=9, bold=True, color="0F172A")
    total_fill = PatternFill("solid", fgColor="EEF2FF")
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style="thin", color="E2E8F0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        "Implementador", "Cliente", "Generador", "RIF", "Tipo", "Cajas", "PVV",
        "Estado", "% Avance", "Días háb.", "Impl. Original",
        "Fecha Asignación", "Último Contacto",
    ]

    # Título
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value="Reporte de Carga y Estatus").font = title_font

    # Subtítulo: fecha de generación + filtros aplicados
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    chips = []
    if assigned_to: chips.append(f"Implementador Actual: {', '.join(assigned_to)}")
    if original_implementer: chips.append(f"Implementador Original: {', '.join(original_implementer)}")
    if status: chips.append(f"Estatus: {', '.join(status)}")
    if client: chips.append(f"Cliente: {client}")
    if quote_type: chips.append(f"Tipo: {', '.join(_TYPE_FULL_LABEL.get(t.upper(), t.upper()) for t in quote_type)}")
    if generator: chips.append(f"Generador: {', '.join(generator)}")
    if _df or _dt:
        chips.append(f"Periodo de Asignación: Desde {_format_es_date(_df) if _df else '—'} — Hasta {_format_es_date(_dt) if _dt else '—'}")
    sub_txt = f"Generado: {now_str}  ·  Agrupado por: {'Tipo de Proyecto' if group_by == 'type' else 'Implementador'}  ·  Proyectos: {len(projects_sorted)}"
    if chips:
        sub_txt += "  ·  Filtros → " + "  |  ".join(chips)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    ws.cell(row=2, column=1, value=sub_txt).font = sub_font

    # Encabezados (fila 4)
    header_row = 4
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=col, value=h)
        c.font = header_font
        c.fill = header_fill
        c.alignment = center
        c.border = border

    # Datos
    r = header_row + 1
    tot_cajas = tot_pvv = 0
    for p in projects_sorted:
        qtn = _norm_type(p.get("quote_type"))
        cajas_val = int(p.get("_cajas") or 0) if _counts_cajas((p.get("quote_type") or "").upper()) else None
        pvv_val = int(p.get("_pvv") or 0)
        if cajas_val:
            tot_cajas += cajas_val
        tot_pvv += pvv_val
        row_vals = [
            p.get("assigned_to_name") or "Sin asignar",
            p.get("client_name") or "—",
            p.get("created_by_name") or "—",
            p.get("client_rif") or "",
            _TYPE_FULL_LABEL.get(qtn, "—"),
            cajas_val if cajas_val else "—",
            pvv_val if pvv_val > 0 else "—",
            p.get("status") or "—",
            f"{int(p.get('_avance') or 0)}%",
            int(p.get("_bdays") or 0),
            p.get("reassigned_from_name") or "—",
            _format_es_date(p.get("assigned_at")),
            _format_es_date(p.get("last_contact_at")),
        ]
        for col, v in enumerate(row_vals, start=1):
            c = ws.cell(row=r, column=col, value=v)
            c.border = border
            if col in (6, 7, 9, 10):
                c.alignment = center
        r += 1

    # Fila de totales
    if projects_sorted:
        for col in range(1, len(headers) + 1):
            c = ws.cell(row=r, column=col)
            c.fill = total_fill
            c.border = border
        ws.cell(row=r, column=1, value=f"TOTAL ({len(projects_sorted)} proyectos)").font = total_font
        tc = ws.cell(row=r, column=6, value=tot_cajas); tc.font = total_font; tc.alignment = center
        tp = ws.cell(row=r, column=7, value=tot_pvv); tp.font = total_font; tp.alignment = center

    # Anchos de columna
    widths = [22, 30, 22, 16, 16, 8, 8, 16, 10, 10, 22, 16, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # Autofiltro + congelar encabezado
    last_col = openpyxl.utils.get_column_letter(len(headers))
    ws.auto_filter.ref = f"A{header_row}:{last_col}{max(header_row, r - 1)}"
    ws.freeze_panes = f"A{header_row + 1}"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"carga_implementadores_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )





# =====================================================================
# REASIGNACIÓN MASIVA (Sección 3)
# =====================================================================

class BulkReassignBody(BaseModel):
    from_user_id: Optional[str] = None  # opcional (puede ser "sin_asignar")
    to_user_id: str
    project_ids: List[str]


def _is_coordinator_or_admin(user: dict) -> bool:
    """Coord/Gerente/Admin para acciones gerenciales (reasignación masiva, compromisos)."""
    if (user.get("role") or "").lower() == "admin":
        return True
    cargo = (user.get("cargo") or "").lower()
    return cargo in ("coordinador", "gerente")


@router.post("/projects/bulk-reassign")
async def bulk_reassign_projects(body: BulkReassignBody, authorization: Optional[str] = Header(None)):
    """Reasignación masiva de proyectos. Solo Coord/Gerente/Admin.
    - Registra al implementador anterior en `reassignment_history[]`.
    - Marca `assigned_to_*` al nuevo implementador.
    - Cambia status a 'En proceso/reasignado'.
    """
    user = await get_current_user(authorization)
    if not _is_coordinator_or_admin(user):
        raise HTTPException(status_code=403, detail="Solo Coordinadores, Gerentes o Admin pueden reasignar en masa")

    if not body.project_ids:
        raise HTTPException(status_code=400, detail="No se seleccionaron proyectos")

    to_user = await db.users.find_one({"user_id": body.to_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1})
    if not to_user:
        raise HTTPException(status_code=404, detail="Implementador destino no encontrado")
    if (to_user.get("cargo") or "").lower() != "implementador":
        raise HTTPException(status_code=400, detail="El usuario destino no tiene cargo 'Implementador'")
    to_name = f"{to_user.get('first_name','')} {to_user.get('last_name','')}".strip()
    now_iso = datetime.now(timezone.utc).isoformat()
    exec_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")

    reassigned = 0
    skipped = []
    for pid in body.project_ids:
        p = await db.projects.find_one({"project_id": pid}, {
            "_id": 0, "project_id": 1, "assigned_to_user_id": 1, "assigned_to_name": 1, "assigned_at": 1,
            "ticket_number": 1, "status": 1,
        })
        if not p:
            skipped.append({"project_id": pid, "reason": "not_found"})
            continue
        if p.get("assigned_to_user_id") == body.to_user_id:
            skipped.append({"project_id": pid, "reason": "already_assigned"})
            continue

        # Regla de negocio: una reasignación mantiene "En Gestión" si el proyecto
        # ya tiene Nro de Ticket; si no, queda "Asignado".
        reassign_status = "En Gestión" if (p.get("ticket_number") or "").strip() else "Asignado"

        history_entry = {
            "from_user_id": p.get("assigned_to_user_id"),
            "from_name": p.get("assigned_to_name"),
            "to_user_id": body.to_user_id,
            "to_name": to_name,
            "reassigned_at": now_iso,
            "reassigned_by_name": exec_name,
        }
        await db.projects.update_one(
            {"project_id": pid},
            {
                "$set": {
                    "assigned_to_user_id": body.to_user_id,
                    "assigned_to_name": to_name,
                    "assigned_at": now_iso,
                    "status": reassign_status,
                    "reassigned_from_name": p.get("assigned_to_name"),
                    "reassigned_from_user_id": p.get("assigned_to_user_id"),
                    "updated_at": now_iso,
                },
                "$push": {"reassignment_history": history_entry},
            },
        )
        reassigned += 1

    return {
        "reassigned": reassigned,
        "skipped": skipped,
        "to_user_id": body.to_user_id,
        "to_name": to_name,
        "message": f"{reassigned} proyecto(s) reasignado(s) a {to_name}",
    }


# =====================================================================
# COMPROMISOS GERENCIALES (Sección 4)
# =====================================================================

class CommitmentCreate(BaseModel):
    message: str
    deadline: Optional[str] = None


@router.get("/projects/{project_id}/commitments")
async def list_commitments(project_id: str, authorization: Optional[str] = Header(None)):
    """Cualquier usuario con acceso al proyecto puede ver los compromisos."""
    await get_current_user(authorization)
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "commitments": 1, "project_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return p.get("commitments") or []


@router.post("/projects/{project_id}/commitments")
async def create_commitment(project_id: str, body: CommitmentCreate, authorization: Optional[str] = Header(None)):
    """Crear compromiso. Solo Coord/Gerente/Admin."""
    user = await get_current_user(authorization)
    if not _is_coordinator_or_admin(user):
        raise HTTPException(status_code=403, detail="Solo Coordinadores, Gerentes o Admin pueden crear compromisos")
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "project_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    role = "Admin" if (user.get("role") or "").lower() == "admin" else (user.get("cargo") or "Gerente").capitalize()
    import uuid as _uuid
    commitment = {
        "commitment_id": f"cmt_{_uuid.uuid4().hex[:12]}",
        "message": (body.message or "").strip(),
        "deadline": body.deadline or None,
        "created_by_user_id": user.get("user_id"),
        "created_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", ""),
        "created_by_role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed": False,
    }
    if not commitment["message"]:
        raise HTTPException(status_code=400, detail="El mensaje del compromiso no puede estar vacío")

    await db.projects.update_one({"project_id": project_id}, {"$push": {"commitments": commitment}})
    return {"message": "Compromiso registrado", "commitment": commitment}


@router.put("/projects/{project_id}/commitments/{commitment_id}/complete")
async def complete_commitment(project_id: str, commitment_id: str, authorization: Optional[str] = Header(None)):
    """Marcar compromiso como cumplido. Solo Coord/Gerente/Admin."""
    user = await get_current_user(authorization)
    if not _is_coordinator_or_admin(user):
        raise HTTPException(status_code=403, detail="Solo Coordinadores, Gerentes o Admin pueden completar compromisos")
    now_iso = datetime.now(timezone.utc).isoformat()
    name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")
    res = await db.projects.update_one(
        {"project_id": project_id, "commitments.commitment_id": commitment_id},
        {"$set": {
            "commitments.$.completed": True,
            "commitments.$.completed_at": now_iso,
            "commitments.$.completed_by_name": name,
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado")
    return {"message": "Compromiso marcado como cumplido"}


@router.delete("/projects/{project_id}/commitments/{commitment_id}")
async def delete_commitment(project_id: str, commitment_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar compromiso. Solo Coord/Gerente/Admin."""
    user = await get_current_user(authorization)
    if not _is_coordinator_or_admin(user):
        raise HTTPException(status_code=403, detail="Solo Coordinadores, Gerentes o Admin pueden eliminar compromisos")
    res = await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"commitments": {"commitment_id": commitment_id}}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado")
    return {"message": "Compromiso eliminado"}



# =====================================================================
# MIS ALERTAS DE IMPLEMENTADOR (Sección 3 — Autogestión)
# =====================================================================

class ImplementerAlertCreate(BaseModel):
    message: str
    deadline: Optional[str] = None


def _is_assigned_implementer(user: dict, project: dict) -> bool:
    """True si el usuario es el implementador asignado actualmente al proyecto."""
    uid = user.get("user_id")
    return bool(uid) and uid == project.get("assigned_to_user_id")


@router.get("/projects/{project_id}/implementer-alerts")
async def list_implementer_alerts(project_id: str, authorization: Optional[str] = Header(None)):
    """Lista alertas del implementador asignado.
    Visibilidad: Implementador asignado + Coord/Gerente/Admin (lectura para supervisión).
    """
    user = await get_current_user(authorization)
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "implementer_alerts": 1, "assigned_to_user_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not (_is_assigned_implementer(user, p) or _is_coordinator_or_admin(user)):
        raise HTTPException(status_code=403, detail="No tiene acceso a las alertas de este proyecto")
    return p.get("implementer_alerts") or []


@router.post("/projects/{project_id}/implementer-alerts")
async def create_implementer_alert(project_id: str, body: ImplementerAlertCreate, authorization: Optional[str] = Header(None)):
    """Crear alerta personal. Solo el implementador asignado al proyecto."""
    user = await get_current_user(authorization)
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "assigned_to_user_id": 1, "project_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _is_assigned_implementer(user, p):
        raise HTTPException(status_code=403, detail="Solo el implementador asignado puede crear sus alertas")

    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="El mensaje de la alerta no puede estar vacío")

    import uuid as _uuid
    alert = {
        "alert_id": f"alt_{_uuid.uuid4().hex[:12]}",
        "message": message,
        "deadline": body.deadline or None,
        "created_by_user_id": user.get("user_id"),
        "created_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed": False,
    }
    await db.projects.update_one({"project_id": project_id}, {"$push": {"implementer_alerts": alert}})
    return {"message": "Alerta registrada", "alert": alert}


@router.put("/projects/{project_id}/implementer-alerts/{alert_id}/complete")
async def complete_implementer_alert(project_id: str, alert_id: str, authorization: Optional[str] = Header(None)):
    """Marcar alerta como cumplida. Solo el implementador asignado."""
    user = await get_current_user(authorization)
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "assigned_to_user_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _is_assigned_implementer(user, p):
        raise HTTPException(status_code=403, detail="Solo el implementador asignado puede completar sus alertas")
    now_iso = datetime.now(timezone.utc).isoformat()
    name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")
    res = await db.projects.update_one(
        {"project_id": project_id, "implementer_alerts.alert_id": alert_id},
        {"$set": {
            "implementer_alerts.$.completed": True,
            "implementer_alerts.$.completed_at": now_iso,
            "implementer_alerts.$.completed_by_name": name,
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"message": "Alerta marcada como cumplida"}


@router.delete("/projects/{project_id}/implementer-alerts/{alert_id}")
async def delete_implementer_alert(project_id: str, alert_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar alerta personal. Solo el implementador asignado."""
    user = await get_current_user(authorization)
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "assigned_to_user_id": 1})
    if not p:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not _is_assigned_implementer(user, p):
        raise HTTPException(status_code=403, detail="Solo el implementador asignado puede eliminar sus alertas")
    res = await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"implementer_alerts": {"alert_id": alert_id}}},
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    return {"message": "Alerta eliminada"}



@router.post("/projects/bitacora/backfill-plaintext")
async def backfill_bitacora_plaintext(authorization: Optional[str] = Header(None)):
    """Genera la versión en texto simple (email_detail.message) para las entradas
    de bitácora existentes que solo tienen html_content, para que sean legibles.
    SOLO administradores. Idempotente: no sobreescribe mensajes ya existentes.
    """
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar este proceso")

    projects_scanned = 0
    entries_converted = 0
    projects_updated = 0

    cursor = db.projects.find(
        {"bitacora.email_detail.html_content": {"$exists": True}},
        {"project_id": 1, "bitacora": 1},
    )
    async for proj in cursor:
        projects_scanned += 1
        bitacora = proj.get("bitacora", []) or []
        changed = False
        for entry in bitacora:
            det = entry.get("email_detail")
            if not isinstance(det, dict):
                continue
            html = det.get("html_content")
            msg = det.get("message")
            has_msg = isinstance(msg, str) and msg.strip()
            # Reconvertir también cuando el `message` guardado contiene HTML crudo
            # (caso de "Otras Notificaciones"/adhoc_email antiguas que almacenaban
            # el HTML en `message`), no solo cuando falta.
            msg_is_html = has_msg and bool(re.search(r"<[a-zA-Z/][^>]*>", msg))
            if html and (not has_msg or msg_is_html):
                det["message"] = _html_to_plaintext(html)
                entries_converted += 1
                changed = True
            elif msg_is_html:
                det["message"] = _html_to_plaintext(msg)
                entries_converted += 1
                changed = True
        if changed:
            await db.projects.update_one(
                {"project_id": proj["project_id"]},
                {"$set": {"bitacora": bitacora}},
            )
            projects_updated += 1

    logging.info(f"[backfill-plaintext] proyectos={projects_scanned} actualizados={projects_updated} entradas={entries_converted}")
    return {
        "success": True,
        "projects_scanned": projects_scanned,
        "projects_updated": projects_updated,
        "entries_converted": entries_converted,
    }
