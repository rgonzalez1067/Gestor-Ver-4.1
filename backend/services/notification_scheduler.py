"""Notification scheduler — jobs programados para eventos basados en tiempo.

Corre 1 vez al día a las 08:00 America/Caracas (UTC-4).
Eventos programados:
  #12 taller_equipo_over_15_days — equipos en taller > 15 días
  #14 project_assigned_not_started — proyectos asignados pero no iniciados (>2 días)
  #15 project_stalled_5_days — proyectos iniciados sin avance en los últimos 5 días
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import db
from services.notification_service import notify

logger = logging.getLogger(__name__)

scheduler: AsyncIOScheduler | None = None


# ==================== Jobs ====================

async def job_taller_over_15_days() -> None:
    """Notifica por cada equipo en taller 'En reparación' con > 15 días desde fecha_ingreso."""
    now = datetime.now(timezone.utc)
    count = 0
    cursor = db.taller_equipos.find(
        {"estatus": "En reparación"},
        {"_id": 0},
    )
    async for eq in cursor:
        fecha_str = eq.get("fecha_ingreso", "")
        if not fecha_str:
            continue
        try:
            fi = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            if fi.tzinfo is None:
                fi = fi.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        days = (now - fi).days
        if days < 15:
            continue

        # Evitar spam: una notificación cada 5 días por equipo
        last = eq.get("last_taller_alert_at")
        if last:
            try:
                lf = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if lf.tzinfo is None:
                    lf = lf.replace(tzinfo=timezone.utc)
                if (now - lf).days < 5:
                    continue
            except Exception:
                pass

        await notify(
            event_type="taller_equipo_over_15_days",
            title=f"Equipo en taller {days} días",
            message=f"Serial {eq.get('serial', 's/n')} · Modelo {eq.get('modelo', '')} · Cliente {eq.get('client_name', '')}",
            context={"sede": None},
            link="/taller-equipos",
            quote_id=eq.get("quote_id"),
        )
        await db.taller_equipos.update_one(
            {"taller_equipo_id": eq["taller_equipo_id"]},
            {"$set": {"last_taller_alert_at": now.isoformat()}},
        )
        count += 1

    logger.info(f"[scheduler] taller_over_15_days → {count} equipo(s) notificado(s)")


async def job_project_assigned_not_started() -> None:
    """Proyectos con status != 'En Implementación' y con assignee definido por >2 días."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=2)
    count = 0
    cursor = db.projects.find(
        {
            "status": {"$nin": ["En Implementación", "Completado", "Cancelado"]},
            "assigned_to_user_id": {"$exists": True, "$ne": None},
        },
        {"_id": 0},
    )
    async for p in cursor:
        assigned_at_str = p.get("assigned_at")
        if not assigned_at_str:
            continue
        try:
            aa = datetime.fromisoformat(assigned_at_str.replace("Z", "+00:00"))
            if aa.tzinfo is None:
                aa = aa.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if aa > threshold:
            continue

        # Cool-down 3 días
        last = p.get("last_not_started_alert_at")
        if last:
            try:
                lf = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if lf.tzinfo is None:
                    lf = lf.replace(tzinfo=timezone.utc)
                if (now - lf).days < 3:
                    continue
            except Exception:
                pass

        days = (now - aa).days
        await notify(
            event_type="project_assigned_not_started",
            title=f"Proyecto asignado sin iniciar ({days} días)",
            message=f"Proyecto {p.get('project_number', '')} · Cliente {p.get('client_name', '')}",
            context={
                "sede": p.get("client_sede"),
                "assignee_user_id": p.get("assigned_to_user_id"),
            },
            link=f"/projects/{p.get('project_id')}",
            project_id=p.get("project_id"),
        )
        await db.projects.update_one(
            {"project_id": p["project_id"]},
            {"$set": {"last_not_started_alert_at": now.isoformat()}},
        )
        count += 1
    logger.info(f"[scheduler] project_assigned_not_started → {count} proyecto(s)")


async def job_project_stalled_5_days() -> None:
    """Proyectos 'En Implementación' sin cambios de status ni eventos en bitácora últimos 5 días."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=5)
    count = 0
    cursor = db.projects.find(
        {"status": "En Implementación"},
        {"_id": 0},
    )
    async for p in cursor:
        last_activity_str = p.get("last_activity_at") or p.get("updated_at") or p.get("created_at")
        if not last_activity_str:
            continue
        try:
            la = datetime.fromisoformat(last_activity_str.replace("Z", "+00:00"))
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if la > threshold:
            continue

        last_alert = p.get("last_stalled_alert_at")
        if last_alert:
            try:
                lf = datetime.fromisoformat(last_alert.replace("Z", "+00:00"))
                if lf.tzinfo is None:
                    lf = lf.replace(tzinfo=timezone.utc)
                if (now - lf).days < 3:
                    continue
            except Exception:
                pass

        days = (now - la).days
        await notify(
            event_type="project_stalled_5_days",
            title=f"Proyecto sin avance ({days} días)",
            message=f"Proyecto {p.get('project_number', '')} · Cliente {p.get('client_name', '')}",
            context={
                "sede": p.get("client_sede"),
                "assignee_user_id": p.get("assigned_to_user_id"),
            },
            link=f"/projects/{p.get('project_id')}",
            project_id=p.get("project_id"),
        )
        await db.projects.update_one(
            {"project_id": p["project_id"]},
            {"$set": {"last_stalled_alert_at": now.isoformat()}},
        )
        count += 1
    logger.info(f"[scheduler] project_stalled_5_days → {count} proyecto(s)")


# ==================== Scheduler lifecycle ====================

def start_scheduler() -> None:
    """Arranca APScheduler con los 3 jobs. Llamado desde server.py startup."""
    global scheduler
    if scheduler and scheduler.running:
        return
    scheduler = AsyncIOScheduler(timezone="America/Caracas")
    # Todos los días a las 8:00 AM Caracas
    scheduler.add_job(job_taller_over_15_days, CronTrigger(hour=8, minute=0), id="taller_15d", replace_existing=True)
    scheduler.add_job(job_project_assigned_not_started, CronTrigger(hour=8, minute=5), id="proj_not_started", replace_existing=True)
    scheduler.add_job(job_project_stalled_5_days, CronTrigger(hour=8, minute=10), id="proj_stalled", replace_existing=True)
    scheduler.start()
    logger.info("[scheduler] started with 3 jobs at 08:00/08:05/08:10 America/Caracas")


def stop_scheduler() -> None:
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")
