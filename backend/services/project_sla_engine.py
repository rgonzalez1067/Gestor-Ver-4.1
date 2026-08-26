"""Project SLA Engine — Semáforo de Tiempos + Motor de Acciones Automatizadas.

Calcula el color del semáforo (Verde → Amarillo → Rojo) de cada proyecto activo
según una matriz configurable de días por etapa del ciclo de vida, y dispara
acciones (Correo / Centro de Mensajes) cuando un proyecto cambia de color.

Etapas (filas de la matriz), mapeadas al estado del proyecto:
  - por_asignar  → status "Por asignar"  (Sin asignar)
  - asignado     → status "Asignado"     (Asignado sin desbloquear)
  - en_gestion   → status "En Gestión"   (Desbloqueado / En gestión)

Columnas de la matriz:
  - warning_days : días para pasar de Verde a Amarillo (Alerta Preventiva)
  - delay_days   : días para pasar de Amarillo a Rojo (Alerta Crítica / Vencimiento)

El conteo de días se hace desde que el proyecto ENTRÓ al estado actual.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from config import db
from services.email_service import send_email
from services.inbox_service import deliver_to_inbox
from services.notification_engine import _load_template, _render, _resolve_user_email
from services.dynamic_recipients import resolve_project_implementer
from services.project_template_vars import resolve_project_template_vars

logger = logging.getLogger("project_sla_engine")

# ---------- Catálogo de etapas y acciones ----------
STAGE_DEFS = [
    {"key": "por_asignar", "label": "Sin asignar", "status": "Por asignar"},
    {"key": "asignado", "label": "Asignado sin desbloquear", "status": "Asignado"},
    {"key": "en_gestion", "label": "Desbloqueado / En Gestión", "status": "En Gestión"},
]
STAGE_KEYS = [s["key"] for s in STAGE_DEFS]
STATUS_TO_STAGE = {s["status"]: s["key"] for s in STAGE_DEFS}
ACTIVE_STATUSES = list(STATUS_TO_STAGE.keys())

DEFAULT_THRESHOLDS = {k: {"warning_days": 2, "delay_days": 4} for k in STAGE_KEYS}

SLA_CONFIG_ID = "default"


def _build_action_catalog() -> list[dict]:
    """6 acciones: 3 de advertencia (V→A) y 3 de retraso (A→R), una por etapa."""
    actions = []
    for s in STAGE_DEFS:
        actions.append({
            "id": f"sla_warning_{s['key']}",
            "stage": s["key"],
            "transition": "warning",
            "label": f"Advertencia (Verde → Amarillo) · {s['label']}",
            "description": f"Se dispara cuando un proyecto en estado '{s['status']}' alcanza los días de advertencia y su semáforo pasa a Amarillo.",
        })
    for s in STAGE_DEFS:
        actions.append({
            "id": f"sla_delay_{s['key']}",
            "stage": s["key"],
            "transition": "delay",
            "label": f"Retraso (Amarillo → Rojo) · {s['label']}",
            "description": f"Se dispara cuando un proyecto en estado '{s['status']}' alcanza los días de vencimiento y su semáforo pasa a Rojo.",
        })
    return actions


SLA_ACTIONS = _build_action_catalog()
SLA_ACTION_IDS = {a["id"] for a in SLA_ACTIONS}

# Variables disponibles para las plantillas de estas acciones.
SLA_TEMPLATE_VARIABLES = [
    "Nro_Proyecto", "project_number", "Nombre_Cliente", "client_name",
    "Email_Contacto", "Contacto_Principal", "Nombre_Implementador",
    "estado_proyecto", "etapa_sla", "dias_en_estado", "color_semaforo",
    "Estado_Proyecto", "Motivo_Cambio_Estatus", "Estatus_Anterior",
    "Fecha_Cambio_Estatus", "Usuario_Cambio_Estatus",
    "fecha_sistema",
]


# ---------- Config (matriz) ----------
async def get_sla_config() -> dict:
    cfg = await db.project_sla_config.find_one({"config_id": SLA_CONFIG_ID}, {"_id": 0})
    if not cfg:
        return {
            "config_id": SLA_CONFIG_ID,
            "stages": {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()},
            "frozen_notify_frequency_days": 7,
        }
    # Completar etapas faltantes con default
    stages = cfg.get("stages") or {}
    for k in STAGE_KEYS:
        if k not in stages:
            stages[k] = dict(DEFAULT_THRESHOLDS[k])
    cfg["stages"] = stages
    if not cfg.get("frozen_notify_frequency_days"):
        cfg["frozen_notify_frequency_days"] = 7
    return cfg


# ---------- Cálculo del semáforo ----------
def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def stage_entered_at(project: dict) -> Optional[datetime]:
    """Fecha en que el proyecto entró a su estado actual (con fallbacks robustos)."""
    status = project.get("status")
    # status_changed_at es la fuente más precisa cuando existe.
    primary = _parse_dt(project.get("status_changed_at"))
    if status == "Por asignar":
        return primary or _parse_dt(project.get("sent_to_implementation_at")) or _parse_dt(project.get("created_at"))
    if status == "Asignado":
        return primary or _parse_dt(project.get("assigned_at")) or _parse_dt(project.get("created_at"))
    if status == "En Gestión":
        return (primary or _parse_dt(project.get("unblocked_at"))
                or _parse_dt(project.get("assigned_at")) or _parse_dt(project.get("created_at")))
    return primary or _parse_dt(project.get("created_at"))


def sla_reference_date(project: dict) -> Optional[datetime]:
    """Fecha de referencia para el semáforo SLA.

    - Fases iniciales (Por asignar / Asignado): se refresca con el cambio de estado
      (usa stage_entered_at).
    - 'En Gestión': el contador solo se reinicia con una ACCIÓN DE INTERACCIÓN VÁLIDA
      (correo a Cliente/Banco o avance en la matriz de adquirencia), registrada en
      `last_qualified_activity_at`. La bitácora NO reinicia el semáforo.
    """
    entered = stage_entered_at(project)
    if project.get("status") == "En Gestión":
        qualified = _parse_dt(project.get("last_qualified_activity_at"))
        if qualified and (entered is None or qualified > entered):
            return qualified
    return entered


def compute_color(days: int, thresholds: dict) -> str:
    warning = int(thresholds.get("warning_days", 2))
    delay = int(thresholds.get("delay_days", 4))
    if days >= delay:
        return "red"
    if days >= warning:
        return "yellow"
    return "green"


async def evaluate_project(project: dict, config: dict, now: Optional[datetime] = None, holiday_sets: Optional[tuple] = None) -> Optional[dict]:
    """Devuelve {stage, days, color, thresholds} o None si el proyecto no aplica
    (estados terminales/pausados no llevan semáforo de tiempos).

    `days` se cuenta en DÍAS HÁBILES (excluye fines de semana y festivos)."""
    now = now or datetime.now(timezone.utc)
    status = project.get("status")
    stage = STATUS_TO_STAGE.get(status)
    if not stage:
        return None
    entered = sla_reference_date(project)
    if not entered:
        return None
    if holiday_sets is None:
        from services.business_calendar import get_holiday_sets
        holiday_sets = await get_holiday_sets()
    specific, recurring = holiday_sets
    from services.business_calendar import business_days_between
    days = business_days_between(entered.date(), now.date(), specific, recurring)
    thresholds = (config.get("stages") or {}).get(stage, DEFAULT_THRESHOLDS[stage])
    color = compute_color(days, thresholds)
    return {"stage": stage, "days": days, "color": color, "thresholds": thresholds}


# ---------- Dispatch de acciones ----------
async def _resolve_external_email(project: dict, tvars: dict) -> tuple[str, str]:
    email = (tvars.get("Email_Contacto") or "").strip()
    name = (tvars.get("Contacto_Principal") or project.get("client_name") or "Cliente").strip()
    return email, name


async def dispatch_sla_action(action_id: str, project: dict) -> dict:
    cfg = await db.project_sla_action_configs.find_one({"action_id": action_id}, {"_id": 0})
    if not cfg:
        return {"dispatched": False, "reason": "no_config"}
    if not cfg.get("enabled", True):
        return {"dispatched": True, "disabled": True, "sent_count": 0}
    recipients = cfg.get("recipients") or []
    if not recipients:
        return {"dispatched": False, "reason": "no_recipients"}

    tvars = await resolve_project_template_vars(project)
    # Firma institucional global. SLA es automático (sin humano) → CRM - Gestor.
    from services.signature import build_signature_html
    tvars["Firma_Notificacion_Global"] = await build_signature_html(None)
    # Variables extra propias del SLA
    tvars.update({
        "estado_proyecto": project.get("status", ""),
        "color_semaforo": project.get("sla_color", ""),
        "dias_en_estado": str(project.get("sla_days", "")),
        "fecha_sistema": datetime.now(timezone.utc).strftime("%d/%m/%Y"),
    })

    sent_count, sent_to, skipped = 0, [], []
    for row in recipients:
        rtype = row.get("type", "owner")
        rcpt_email, rcpt_name, rcpt_user_id = "", "", None
        if rtype == "owner":
            owner_uid = project.get("created_by_user_id") or project.get("created_by")
            resolved = await _resolve_user_email(owner_uid or "")
            if not resolved:
                skipped.append({"row_id": row.get("row_id"), "reason": "Generador del proyecto no encontrado"})
                continue
            rcpt_email, rcpt_name = resolved
            rcpt_user_id = owner_uid
        elif rtype == "external_client":
            rcpt_email, rcpt_name = await _resolve_external_email(project, tvars)
            if not rcpt_email:
                skipped.append({"row_id": row.get("row_id"), "reason": "Cliente sin correo de contacto"})
                continue
        elif rtype == "user":
            resolved = await _resolve_user_email(row.get("user_id", ""))
            if not resolved:
                skipped.append({"row_id": row.get("row_id"), "reason": "Usuario interno no encontrado"})
                continue
            rcpt_email, rcpt_name = resolved
            rcpt_user_id = row.get("user_id")
        elif rtype == "project_implementer":
            # "Usuario Implementador": técnico asignado al proyecto, con
            # contingencia a Coordinador/Administrador.
            rcpt_email, rcpt_name, rcpt_user_id, fb_note = await resolve_project_implementer(project)
            if not rcpt_email:
                skipped.append({"row_id": row.get("row_id"), "reason": fb_note or "Implementador no resoluble"})
                continue
            if fb_note:
                logger.warning(
                    f"[sla] {action_id} · Usuario Implementador (fallback): {fb_note} "
                    f"(proyecto {project.get('project_number', 's/n')}) → {rcpt_email}"
                )
        else:
            skipped.append({"row_id": row.get("row_id"), "reason": f"tipo no soportado: {rtype}"})
            continue

        tpl = await _load_template(row.get("template_id"))
        if not tpl:
            skipped.append({"row_id": row.get("row_id"), "reason": "Plantilla no encontrada"})
            continue

        subject = _render(tpl.get("subject", ""), tvars) or f"Alerta de tiempo · Proyecto {project.get('project_number', '')}"
        body = _render(tpl.get("body_html", "") or tpl.get("body", ""), tvars)

        channel = (row.get("delivery_channel") or "email").lower()
        if not rcpt_user_id:  # inbox requiere usuario interno
            channel = "email"
        try:
            if channel == "inbox":
                await deliver_to_inbox(
                    user_id=rcpt_user_id, recipient_email=rcpt_email, recipient_name=rcpt_name,
                    subject=subject, html=body, action_id=action_id, project_id=project.get("project_id"),
                )
            else:
                await send_email(to=[rcpt_email], subject=subject, html=body, action=f"{action_id}_sla")
            sent_count += 1
            sent_to.append(rcpt_email)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[sla] Error enviando a {rcpt_email} (channel={channel}): {e}")
            skipped.append({"row_id": row.get("row_id"), "reason": str(e)})

    logger.info(f"[sla] {action_id} → sent={sent_count}, skipped={len(skipped)} (proyecto {project.get('project_number')})")
    return {"dispatched": True, "sent_count": sent_count, "recipients": sent_to, "skipped": skipped}


# ---------- Job / evaluación masiva ----------
async def run_sla_evaluation(force_dispatch: bool = False) -> dict:
    """Evalúa todos los proyectos activos, persiste su color y dispara acciones
    en las transiciones Verde→Amarillo y Amarillo→Rojo."""
    now = datetime.now(timezone.utc)
    config = await get_sla_config()
    from services.business_calendar import get_holiday_sets
    holiday_sets = await get_holiday_sets()
    evaluated, transitions, dispatched = 0, 0, 0

    cursor = db.projects.find({"status": {"$in": ACTIVE_STATUSES}}, {"_id": 0})
    async for project in cursor:
        res = await evaluate_project(project, config, now, holiday_sets)
        if not res:
            continue
        evaluated += 1
        new_color = res["color"]
        prev_color = project.get("sla_color")

        await db.projects.update_one(
            {"project_id": project["project_id"]},
            {"$set": {
                "sla_color": new_color, "sla_days": res["days"],
                "sla_stage": res["stage"], "sla_evaluated_at": now.isoformat(),
            }},
        )

        if new_color == prev_color:
            continue
        transitions += 1
        await db.projects.update_one(
            {"project_id": project["project_id"]},
            {"$set": {"sla_color_changed_at": now.isoformat()}},
        )
        # Mantener una copia fresca con el color recién persistido para las vars.
        project["sla_color"] = new_color
        project["sla_days"] = res["days"]

        action_id = None
        if new_color == "yellow" and prev_color != "yellow":
            action_id = f"sla_warning_{res['stage']}"
        elif new_color == "red" and prev_color != "red":
            action_id = f"sla_delay_{res['stage']}"

        if action_id:
            out = await dispatch_sla_action(action_id, project)
            if out.get("sent_count"):
                dispatched += out["sent_count"]

    logger.info(f"[sla] evaluación: {evaluated} proyectos, {transitions} transiciones, {dispatched} envíos")
    return {"evaluated": evaluated, "transitions": transitions, "dispatched": dispatched}


async def job_project_sla_transitions() -> None:
    try:
        await run_sla_evaluation()
    except Exception as e:  # noqa: BLE001
        logger.error(f"[sla] job error: {e}")
