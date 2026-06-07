# ruff: noqa
"""Valida la entrega cross-worker: un proceso SIN la conexión WS encola en
`ws_outbox` y el dispatcher del backend (otro proceso) entrega al cliente.
"""
import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone, timedelta

import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import db  # noqa: E402

WS_BASE = os.environ.get("BASE", "http://localhost:8001").replace("http", "ws")


async def main():
    u = await db.users.find_one({"email": "srubio@megasoft.com.ve"}, {"_id": 0, "user_id": 1})
    uid = u["user_id"]
    tok = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    await db.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "created_at": now.isoformat(),
    })

    url = f"{WS_BASE}/api/ws/notifications/{uid}?token={tok}"
    got = []
    async with websockets.connect(url) as ws:
        print("WS conectado", uid)
        await asyncio.sleep(1.5)
        # Simula OTRO worker que NO tiene la conexión: inserta directo en outbox.
        await db.ws_outbox.insert_one({
            "user_id": uid,
            "payload": {"type": "internal_message", "payload": {"preview": "cross-worker test"}},
            "created_at": datetime.now(timezone.utc),
        })
        print("Encolado en ws_outbox desde proceso externo (sin conexión local)")
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=6)
                msg = json.loads(raw)
                if msg.get("type") == "internal_message":
                    print(">>> ENTREGADO por dispatcher del backend:", msg["payload"].get("preview"))
                    got.append(True)
                    break
        except asyncio.TimeoutError:
            print("TIMEOUT — no se entregó")
    print("=== RESULTADO cross-worker:", "OK" if got else "FALLÓ")


if __name__ == "__main__":
    asyncio.run(main())
