# ruff: noqa
"""Reproducción del bug: push WS a múltiples destinatarios.

Crea sesiones directas en DB para 2 usuarios, conecta sus WS, envía un
mensaje interno a ambos desde admin y reporta qué clientes reciben el evento.
"""
import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone, timedelta

import httpx
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import db  # noqa: E402

BASE = os.environ.get("BASE", "http://localhost:8001")
WS_BASE = BASE.replace("http", "ws")

ADMIN = ("rgonzalez@megasoft.com.ve", "admin123")


async def make_session(user_id):
    tok = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": tok,
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "created_at": now.isoformat(),
    })
    return tok


async def ws_listen(user_id, token, received, label):
    url = f"{WS_BASE}/api/ws/notifications/{user_id}?token={token}"
    async with websockets.connect(url) as ws:
        print(f"[{label}] WS conectado user={user_id}")
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=8)
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                if msg.get("type") == "internal_message":
                    print(f"[{label}] >>> RECIBIDO internal_message")
                    received.append(label)
        except asyncio.TimeoutError:
            print(f"[{label}] timeout (fin de escucha)")


async def main():
    u1 = await db.users.find_one({"email": "srubio@megasoft.com.ve"}, {"_id": 0, "user_id": 1})
    u2 = await db.users.find_one({"email": "Jrojas@megasoft.com.ve"}, {"_id": 0, "user_id": 1})
    u1_id, u2_id = u1["user_id"], u2["user_id"]
    u1_tok = await make_session(u1_id)
    u2_tok = await make_session(u2_id)

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        r.raise_for_status()
        admin_tok = r.json()["session_token"]

        received = []
        t1 = asyncio.create_task(ws_listen(u1_id, u1_tok, received, "U1"))
        t2 = asyncio.create_task(ws_listen(u2_id, u2_tok, received, "U2"))
        await asyncio.sleep(2)

        r = await client.post(
            f"{BASE}/api/inbox/send",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "recipient_user_ids": [u1_id, u2_id],
                "subject": "Prueba multi WS",
                "body": "Mensaje de prueba multi-destinatario.",
            },
        )
        print("send status:", r.status_code, r.json())

        await asyncio.gather(t1, t2)
        print("\n=== RESULTADO === Recibieron WS:", sorted(set(received)))


if __name__ == "__main__":
    asyncio.run(main())
