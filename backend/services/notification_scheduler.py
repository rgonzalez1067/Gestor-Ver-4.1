"""Notification scheduler — jobs programados para eventos basados en tiempo.

Corre 1 vez al día a las 08:00 America/Caracas (UTC-4).
Eventos programados:
  #12 taller_equipo_over_15_days — equipos en taller > 15 días
  #14 project_assigned_not_started — proyectos asignados pero no iniciados (>2 días)
  #15 project_stalled_5_days — proyectos iniciados sin avance en los últimos 5 días
  #16 implementer_alert_due — alertas personales del implementador que vencen hoy o están vencidas
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta, date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import db
from services.notification_service import notify, manager
from services.email_service import send_email

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
    """Proyectos en estado 'Asignado' (asignados sin iniciar gestión) por >2 días."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=2)
    count = 0
    cursor = db.projects.find(
        {
            "status": "Asignado",
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
    """Proyectos 'En Gestión' sin cambios de status ni eventos en bitácora últimos 5 días."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=5)
    count = 0
    cursor = db.projects.find(
        {"status": "En Gestión"},
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

async def job_implementer_alerts_due() -> None:
    """Recordatorios de "Mis Alertas" del Implementador.

    Para cada alerta activa (completed=false) con `deadline`:
      - Hoy es el día del deadline → email "Vence hoy".
      - El deadline ya pasó → email "Vencida (hace N días)".
    Cool-down: no re-notifica la misma alerta en las últimas 24h.
    """
    now = datetime.now(timezone.utc)
    today = date.today()
    count = 0

    cursor = db.projects.find(
        {"implementer_alerts": {"$exists": True, "$not": {"$size": 0}}},
        {
            "_id": 0,
            "project_id": 1, "project_number": 1, "client_name": 1,
            "assigned_to_user_id": 1, "assigned_to_name": 1,
            "implementer_alerts": 1,
        },
    )
    async for p in cursor:
        impl_user_id = p.get("assigned_to_user_id")
        if not impl_user_id:
            continue
        alerts = p.get("implementer_alerts") or []
        active = [a for a in alerts if not a.get("completed") and a.get("deadline")]
        if not active:
            continue

        # Resolver email del implementador (una sola lectura por proyecto)
        impl_user = await db.users.find_one(
            {"user_id": impl_user_id, "is_active": True},
            {"_id": 0, "email": 1, "first_name": 1, "last_name": 1},
        )
        if not impl_user or not impl_user.get("email"):
            continue

        for a in active:
            try:
                dl = datetime.fromisoformat(str(a["deadline"])[:10]).date()
            except Exception:
                continue
            delta_days = (today - dl).days
            # Solo notificamos cuando vence hoy (delta=0) o cuando ya pasó (delta>0).
            if delta_days < 0:
                continue

            # Cool-down 24h
            last = a.get("last_reminder_at")
            if last:
                try:
                    lf = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                    if lf.tzinfo is None:
                        lf = lf.replace(tzinfo=timezone.utc)
                    if (now - lf) < timedelta(hours=24):
                        continue
                except Exception:
                    pass

            # Construir correo
            vence_label = "vence hoy" if delta_days == 0 else f"está vencida hace {delta_days} día(s)"
            subject = f"Mi Alerta — {vence_label} · Proyecto {p.get('project_number', '')}"
            html = f"""
            <div style="font-family:Arial,sans-serif;color:#1e293b;">
              <div style="background:#f59e0b;color:#fff;padding:12px 16px;border-radius:6px 6px 0 0;">
                <h2 style="margin:0;font-size:18px;">🔔 Tu alerta personal {vence_label}</h2>
              </div>
              <div style="border:1px solid #fde68a;border-top:none;padding:16px;border-radius:0 0 6px 6px;background:#fffbeb;">
                <p style="margin:0 0 8px;"><strong>Proyecto:</strong> {p.get('project_number', '')} — {p.get('client_name', '')}</p>
                <p style="margin:0 0 8px;"><strong>Mensaje:</strong> {a.get('message', '')}</p>
                <p style="margin:0 0 8px;"><strong>Fecha objetivo:</strong> {dl.strftime('%d/%m/%Y')}</p>
                <p style="margin:12px 0 0;color:#92400e;font-size:13px;">
                  Ingresa al proyecto y gestiona tu alerta desde el botón <strong>"Mis Alertas"</strong>.
                </p>
              </div>
              <p style="color:#94a3b8;font-size:11px;margin-top:16px;">
                Recordatorio automático diario. Este correo se envía a {impl_user.get('email')} como implementador asignado.
              </p>
            </div>
            """
            try:
                await send_email(
                    to=[impl_user["email"]],
                    subject=subject,
                    html=html,
                    action="implementer_alert_reminder",
                )
            except Exception as e:
                logger.warning(f"[scheduler] implementer_alert_reminder email failed: {e}")
                continue

            # Marcar last_reminder_at en la alerta ($ positional)
            await db.projects.update_one(
                {"project_id": p["project_id"], "implementer_alerts.alert_id": a["alert_id"]},
                {"$set": {"implementer_alerts.$.last_reminder_at": now.isoformat()}},
            )

            # Push notification in-app (opcional, reaprovecha pipeline existente)
            try:
                await notify(
                    event_type="implementer_alert_due",
                    title=f"Alerta personal {vence_label}",
                    message=f"{p.get('project_number', '')} · {a.get('message', '')[:80]}",
                    context={"assignee_user_id": impl_user_id},
                    link=f"/projects/{p['project_id']}",
                    project_id=p["project_id"],
                )
            except Exception:
                pass

            count += 1

    logger.info(f"[scheduler] implementer_alerts_due → {count} recordatorio(s) enviado(s)")


async def job_inbox_reminders_due() -> None:
    """Centro de Mensajes — "Recuérdame".

    Corre cada minuto. Por cada notificación del sistema con `remind_at` vencido
    y aún no disparada (`remind_fired != True`), empuja una alerta en vivo por
    WebSocket (toast intenso) al usuario dueño y la marca como disparada para
    no repetir. La alerta visual persistente (badge "Vencido") la calcula el
    listado `/inbox/me` (campo `remind_due`).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    count = 0
    cursor = db.inbox_messages.find(
        {
            "deleted_at": None,
            "is_user_message": {"$ne": True},
            "remind_at": {"$ne": None, "$lte": now_iso},
            "remind_fired": {"$ne": True},
        },
        {"_id": 0, "message_id": 1, "user_id": 1, "subject": 1, "quote_number": 1},
    )
    async for m in cursor:
        try:
            await manager.send_to_user(m["user_id"], {
                "type": "reminder_due",
                "payload": {
                    "message_id": m.get("message_id"),
                    "subject": m.get("subject") or "Recordatorio",
                    "quote_number": m.get("quote_number") or "",
                    "link": "/dashboard",
                },
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[scheduler] reminder push failed msg={m.get('message_id')}: {e}")
            continue
        await db.inbox_messages.update_one(
            {"message_id": m["message_id"], "user_id": m["user_id"]},
            {"$set": {"remind_fired": True, "remind_fired_at": now_iso}},
        )
        count += 1
    if count:
        logger.info(f"[scheduler] inbox_reminders_due → {count} recordatorio(s) disparado(s)")


def start_scheduler() -> None:
    """Arranca APScheduler con los 4 jobs. Llamado desde server.py startup."""
    global scheduler
    if scheduler and scheduler.running:
        return
    scheduler = AsyncIOScheduler(timezone="America/Caracas")
    # Todos los días a las 8:00 AM Caracas
    scheduler.add_job(job_taller_over_15_days, CronTrigger(hour=8, minute=0), id="taller_15d", replace_existing=True)
    scheduler.add_job(job_project_assigned_not_started, CronTrigger(hour=8, minute=5), id="proj_not_started", replace_existing=True)
    scheduler.add_job(job_project_stalled_5_days, CronTrigger(hour=8, minute=10), id="proj_stalled", replace_existing=True)
    scheduler.add_job(job_implementer_alerts_due, CronTrigger(hour=8, minute=15), id="impl_alerts_due", replace_existing=True)
    # Recuérdame: chequeo frecuente (cada minuto) de vencimientos del Centro de Mensajes.
    scheduler.add_job(job_inbox_reminders_due, IntervalTrigger(minutes=1), id="inbox_reminders", replace_existing=True)
    scheduler.start()
    logger.info("[scheduler] started with 5 jobs (4 daily + inbox_reminders cada 1 min)")


def stop_scheduler() -> None:
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")
