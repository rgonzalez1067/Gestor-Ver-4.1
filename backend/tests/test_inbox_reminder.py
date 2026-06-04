"""
Centro de Mensajes — Función "Recuérdame" (P0).

Valida end-to-end:
  - PATCH /api/inbox/{id}/remind fija el recordatorio en una notificación del sistema.
  - GET /api/inbox/me devuelve remind_at + remind_due=True cuando ya venció.
  - El job del scheduler (job_inbox_reminders_due) dispara la alerta (encola en
    ws_outbox) y marca remind_fired=True (no repite).
  - PATCH sobre un mensaje user-to-user devuelve 400 (solo notificaciones del sistema).
  - PATCH con remind_at=None limpia el recordatorio.

Crea registros temporales con prefijo TESTREM_ y los elimina por ID al final.
"""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/app/backend")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BASE = "http://localhost:8001/api"
TAG = "TESTREM_"


async def run():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    uid = TAG + uuid.uuid4().hex[:8]
    user = {
        "user_id": uid,
        "email": f"{uid}@testrem.local",
        "first_name": "Rem",
        "last_name": "Test",
        "role": "user",
        "sede": "PYME",
        "is_active": True,
        "permissions": {},
    }
    tok = TAG + secrets.token_hex(16)
    session = {
        "session_token": tok,
        "user_id": uid,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }
    sys_msg_id = TAG + "sys_" + uuid.uuid4().hex[:8]
    sys_msg = {
        "message_id": sys_msg_id,
        "user_id": uid,
        "subject": "Notificación de prueba Recuérdame",
        "body_html": "<p>cuerpo</p>",
        "quote_number": "COT-TEST-001",
        "is_user_message": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_at": None,
        "deleted_at": None,
    }
    user_msg_id = TAG + "usr_" + uuid.uuid4().hex[:8]
    user_msg = {
        "message_id": user_msg_id,
        "user_id": uid,
        "subject": "Mensaje user-to-user",
        "body_html": "<p>hola</p>",
        "is_user_message": True,
        "from_user_id": "someone",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_at": None,
        "deleted_at": None,
    }

    headers = {"Authorization": f"Bearer {tok}"}
    try:
        await db.users.insert_one(user)
        await db.user_sessions.insert_one(session)
        await db.inbox_messages.insert_many([sys_msg, user_msg])

        async with httpx.AsyncClient(timeout=30) as client:
            # 1) Fijar recordatorio en el pasado (ya vencido)
            past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            r = await client.patch(f"{BASE}/inbox/{sys_msg_id}/remind", json={"remind_at": past}, headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["remind_at"], r.text

            # 2) GET /inbox/me → remind_due True
            r = await client.get(f"{BASE}/inbox/me", headers=headers)
            assert r.status_code == 200, r.text
            row = next((m for m in r.json()["items"] if m.get("message_id") == sys_msg_id), None)
            assert row is not None, "notificación no aparece en bandeja"
            assert row.get("remind_at"), "remind_at ausente"
            assert row.get("remind_due") is True, "remind_due debería ser True (vencido)"

            # 3) 400 para mensaje user-to-user
            r = await client.patch(f"{BASE}/inbox/{user_msg_id}/remind", json={"remind_at": past}, headers=headers)
            assert r.status_code == 400, f"esperaba 400, got {r.status_code}: {r.text}"

        # 4) Ejecutar el job del scheduler → debe disparar y marcar remind_fired
        from services.notification_scheduler import job_inbox_reminders_due
        await job_inbox_reminders_due()
        doc = await db.inbox_messages.find_one({"message_id": sys_msg_id}, {"_id": 0, "remind_fired": 1})
        assert doc.get("remind_fired") is True, "el job no marcó remind_fired"
        # La alerta se encoló en ws_outbox (usuario offline) con type reminder_due
        outbox = await db.ws_outbox.find_one({"user_id": uid, "payload.type": "reminder_due"})
        assert outbox is not None, "no se encoló la alerta reminder_due en ws_outbox"

        # 5) Limpiar recordatorio (remind_at None)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(f"{BASE}/inbox/{sys_msg_id}/remind", json={"remind_at": None}, headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["remind_at"] is None
            r = await client.get(f"{BASE}/inbox/me", headers=headers)
            row = next((m for m in r.json()["items"] if m.get("message_id") == sys_msg_id), None)
            assert not row.get("remind_at"), "remind_at debería estar limpio"
            assert row.get("remind_due") is False

        print("PASS: Función Recuérdame (set/due/job/400/clear) correcta.")
    finally:
        await db.inbox_messages.delete_many({"message_id": {"$in": [sys_msg_id, user_msg_id]}})
        await db.ws_outbox.delete_many({"user_id": uid})
        await db.user_sessions.delete_many({"session_token": tok})
        await db.users.delete_many({"user_id": uid})
        c.close()


def test_inbox_reminder_flow():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
