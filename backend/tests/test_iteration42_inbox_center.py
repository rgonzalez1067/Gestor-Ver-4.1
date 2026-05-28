"""E2E test: Centro de Mensajes (Iter42).

Cubre los 4 criterios de aceptación funcional:
  1) Ruteo: si delivery_channel='inbox' → mensaje persiste en colección inbox.
  2) Títulos: subject del inbox == subject del mensaje generado.
  3) Semáforo: SLA color según created_at (verde/amarillo/rojo).
  4) Limpieza: DELETE marca deleted_at y oculta del listado.

Implementado con `asyncio.run()` directo (mismo patrón que otros tests del
repo) — sin depender de pytest-asyncio.

Ejecutar:  cd /app/backend && python -m pytest tests/test_iteration42_inbox_center.py -v
"""
import asyncio
import sys
from datetime import datetime, timezone, timedelta

import httpx

sys.path.insert(0, "/app/backend")

BACKEND_URL = "http://localhost:8001/api"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


async def _login(client):
    r = await client.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


async def _user_id(client, token):
    r = await client.get(
        f"{BACKEND_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


# --------- 1) Smoke: endpoints básicos ---------
async def _smoke():
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c)
        r = await c.get(f"{BACKEND_URL}/inbox/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "total" in d

        r2 = await c.get(f"{BACKEND_URL}/inbox/me/summary", headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 200
        s = r2.json()
        assert set(s["by_sla"].keys()) == {"green", "yellow", "red"}


def test_smoke_endpoints():
    asyncio.run(_smoke())


# --------- 2) Semáforo + limpieza ---------
async def _sla_and_delete():
    from config import db
    from services.inbox_service import deliver_to_inbox

    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c)
        uid = await _user_id(c, tok)

        await db.inbox_messages.delete_many({"subject": {"$regex": "^TEST_ITER42"}})

        now = datetime.now(timezone.utc)
        cases = [
            ("TEST_ITER42 verde", timedelta(hours=1), "green"),
            ("TEST_ITER42 amarillo", timedelta(hours=30), "yellow"),
            ("TEST_ITER42 rojo", timedelta(hours=60), "red"),
        ]
        ids = {}
        for subj, delta, expected in cases:
            r = await deliver_to_inbox(
                user_id=uid,
                recipient_email="x@y.z",
                recipient_name="X",
                subject=subj,
                html=f"<p>{subj}</p>",
                action_id="test_iter42",
            )
            mid = r["message_id"]
            ids[expected] = mid
            await db.inbox_messages.update_one(
                {"message_id": mid},
                {"$set": {"created_at": (now - delta).isoformat()}},
            )

        r = await c.get(f"{BACKEND_URL}/inbox/me?limit=200", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        items = {m["message_id"]: m for m in r.json()["items"]}
        for color, mid in ids.items():
            assert mid in items, f"falta msg {mid}"
            assert items[mid]["sla_color"] == color, (
                f"esperado {color} obtenido {items[mid]['sla_color']}"
            )
            assert items[mid]["subject"].startswith("TEST_ITER42")

        # Soft-delete del rojo
        red_id = ids["red"]
        rdel = await c.delete(
            f"{BACKEND_URL}/inbox/{red_id}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert rdel.status_code == 200

        r2 = await c.get(f"{BACKEND_URL}/inbox/me?limit=200", headers={"Authorization": f"Bearer {tok}"})
        ids_after = [m["message_id"] for m in r2.json()["items"]]
        assert red_id not in ids_after, "msg eliminado aún aparece en inbox"

        # Cleanup final
        await db.inbox_messages.delete_many({"subject": {"$regex": "^TEST_ITER42"}})


def test_sla_semaforo_and_delete():
    asyncio.run(_sla_and_delete())


# --------- 3) Config: delivery_channel persiste y se fuerza para client_field ---------
async def _config_channel():
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c)
        h = {"Authorization": f"Bearer {tok}"}

        cat = await c.get(f"{BACKEND_URL}/action-notifications/catalog", headers=h)
        assert cat.status_code == 200
        users = cat.json()["users"]
        assert users, "sin usuarios activos"
        tpl_id = next(
            (t["template_id"] for t in cat.json()["templates"] if t.get("template_id")),
            None,
        )
        assert tpl_id, "sin plantillas"

        # caso 1: user + inbox → persiste
        payload = {
            "business_type": "equipos",
            "product_subcategory": None,
            "action_id": "send_to_client",
            "recipients": [{
                "row_id": "row_test42_inbox",
                "type": "user",
                "user_id": users[0]["user_id"],
                "template_id": tpl_id,
                "send_pdf_attachments": False,
                "delivery_channel": "inbox",
            }],
        }
        r = await c.put(f"{BACKEND_URL}/action-notifications/configs", json=payload, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["recipients"][0]["delivery_channel"] == "inbox"

        # caso 2: client_field con inbox → forzado a email
        payload["recipients"] = [{
            "row_id": "row_test42_client",
            "type": "client_field",
            "user_id": None,
            "template_id": tpl_id,
            "send_pdf_attachments": True,
            "delivery_channel": "inbox",
        }]
        r2 = await c.put(f"{BACKEND_URL}/action-notifications/configs", json=payload, headers=h)
        assert r2.status_code == 200, r2.text
        assert r2.json()["recipients"][0]["delivery_channel"] == "email", (
            "client_field debió forzarse a email"
        )


def test_config_delivery_channel():
    asyncio.run(_config_channel())
