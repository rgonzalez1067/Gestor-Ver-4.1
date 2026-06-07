# ruff: noqa
"""Test job_implementer_alerts_due — recordatorios de Mis Alertas por email.

Cubre 3 branches + cool-down. Usa asyncio.run en un test síncrono para
evitar la dependencia de pytest-asyncio.
"""
import asyncio
import os
import sys
from datetime import date

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')

PROJECT_ID = "prj_bba45a09cd00"


async def _run():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    today = date.today().isoformat()
    alerts = [
        {"alert_id": "alt_t", "message": "hoy", "deadline": today, "completed": False,
         "created_by_user_id": "user_a8e3874291c8", "created_by_name": "Jhonatan Rojas", "created_at": today},
        {"alert_id": "alt_p", "message": "pasado", "deadline": "2026-01-01", "completed": False,
         "created_by_user_id": "user_a8e3874291c8", "created_by_name": "Jhonatan Rojas", "created_at": "2026-01-01"},
        {"alert_id": "alt_f", "message": "futuro", "deadline": "2099-12-31", "completed": False,
         "created_by_user_id": "user_a8e3874291c8", "created_by_name": "Jhonatan Rojas", "created_at": today},
    ]
    await db.projects.update_one({"project_id": PROJECT_ID}, {"$set": {"implementer_alerts": alerts}})
    await db.email_logs.delete_many({"action": "implementer_alert_reminder"})

    from services.notification_scheduler import job_implementer_alerts_due
    await job_implementer_alerts_due()
    count = await db.email_logs.count_documents({"action": "implementer_alert_reminder"})
    assert count == 2, f"expected 2 emails (today + past), got {count}"
    p = await db.projects.find_one({"project_id": PROJECT_ID}, {"_id": 0, "implementer_alerts": 1})
    by_id = {a["alert_id"]: a for a in p["implementer_alerts"]}
    assert by_id["alt_t"].get("last_reminder_at")
    assert by_id["alt_p"].get("last_reminder_at")
    assert not by_id["alt_f"].get("last_reminder_at")

    # Cool-down
    await job_implementer_alerts_due()
    count2 = await db.email_logs.count_documents({"action": "implementer_alert_reminder"})
    assert count2 == 2, f"cool-down failed: got {count2}"

    # Cleanup
    await db.projects.update_one({"project_id": PROJECT_ID}, {"$set": {"implementer_alerts": []}})
    await db.email_logs.delete_many({"action": "implementer_alert_reminder"})


def test_implementer_alert_reminder_job():
    asyncio.run(_run())
