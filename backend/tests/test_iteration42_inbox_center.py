# ruff: noqa
"""E2E test: Centro de Mensajes (Iter42).

Cubre los criterios de aceptación funcional:
  1) Smoke endpoints `/inbox/me` y `/summary`.
  2) Semáforo SLA (verde/amarillo/rojo) + soft-delete.
  3) `delivery_channel` persiste y se fuerza a `email` para `client_field`.
  4) Descarga de adjuntos (200 OK con content-type correcto, 404 fuera de
     rango, 410 si mensaje legacy sin content_b64).

Implementación: una única función async ejecutada con `asyncio.run()` para
reutilizar el event loop de motor (evita "Event loop is closed" entre tests).

Ejecutar:  cd /app/backend && python -m pytest tests/test_iteration42_inbox_center.py -v
"""
import asyncio
import base64
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


async def _run_all():
    """Ejecuta todas las verificaciones del Iter42 en un único event loop."""
    from config import db
    from services.inbox_service import deliver_to_inbox

    async with httpx.AsyncClient(timeout=30) as c:
        tok = await _login(c)
        uid = await _user_id(c, tok)
        h = {"Authorization": f"Bearer {tok}"}

        # ------- 1) Smoke endpoints -------
        r = await c.get(f"{BACKEND_URL}/inbox/me", headers=h)
        assert r.status_code == 200
        assert "items" in r.json() and "total" in r.json()

        r2 = await c.get(f"{BACKEND_URL}/inbox/me/summary", headers=h)
        assert r2.status_code == 200
        s = r2.json()
        assert set(s["by_sla"].keys()) == {"green", "yellow", "red"}

        # ------- 2) Semáforo + soft-delete -------
        await db.inbox_messages.delete_many({"subject": {"$regex": "^TEST_ITER42"}})
        now = datetime.now(timezone.utc)
        cases = [
            ("TEST_ITER42 verde", timedelta(hours=1), "green"),
            ("TEST_ITER42 amarillo", timedelta(hours=30), "yellow"),
            ("TEST_ITER42 rojo", timedelta(hours=60), "red"),
        ]
        ids = {}
        for subj, delta, expected in cases:
            res = await deliver_to_inbox(
                user_id=uid, recipient_email="x@y.z", recipient_name="X",
                subject=subj, html=f"<p>{subj}</p>", action_id="test_iter42",
            )
            mid = res["message_id"]
            ids[expected] = mid
            await db.inbox_messages.update_one(
                {"message_id": mid},
                {"$set": {"created_at": (now - delta).isoformat()}},
            )

        r = await c.get(f"{BACKEND_URL}/inbox/me?limit=200", headers=h)
        # En Iter48, los items pueden ser notifications o conversations.
        # Las pruebas SLA usan notifications creadas por `deliver_to_inbox`.
        items = {m["message_id"]: m for m in r.json()["items"] if m.get("type") != "conversation"}
        for color, mid in ids.items():
            assert items[mid]["sla_color"] == color
            assert items[mid]["subject"].startswith("TEST_ITER42")

        red_id = ids["red"]
        rdel = await c.delete(f"{BACKEND_URL}/inbox/{red_id}", headers=h)
        assert rdel.status_code == 200
        r2 = await c.get(f"{BACKEND_URL}/inbox/me?limit=200", headers=h)
        notif_ids = [m["message_id"] for m in r2.json()["items"] if m.get("type") != "conversation"]
        assert red_id not in notif_ids

        await db.inbox_messages.delete_many({"subject": {"$regex": "^TEST_ITER42"}})

        # ------- 3) delivery_channel persiste y se fuerza para client_field -------
        cat = await c.get(f"{BACKEND_URL}/action-notifications/catalog", headers=h)
        users = cat.json()["users"]
        tpl_id = next((t["template_id"] for t in cat.json()["templates"] if t.get("template_id")), None)
        assert users and tpl_id

        payload = {
            "business_type": "equipos",
            "product_subcategory": None,
            "action_id": "send_to_client",
            "recipients": [{
                "row_id": "row_test42_inbox", "type": "user",
                "user_id": users[0]["user_id"], "template_id": tpl_id,
                "send_pdf_attachments": False, "delivery_channel": "inbox",
            }],
        }
        rput = await c.put(f"{BACKEND_URL}/action-notifications/configs", json=payload, headers=h)
        assert rput.status_code == 200
        assert rput.json()["recipients"][0]["delivery_channel"] == "inbox"

        payload["recipients"] = [{
            "row_id": "row_test42_client", "type": "client_field", "user_id": None,
            "template_id": tpl_id, "send_pdf_attachments": True, "delivery_channel": "inbox",
        }]
        r2 = await c.put(f"{BACKEND_URL}/action-notifications/configs", json=payload, headers=h)
        assert r2.status_code == 200
        assert r2.json()["recipients"][0]["delivery_channel"] == "email", "client_field debe forzarse a email"

        # ------- 4) Descarga de adjuntos -------
        await db.inbox_messages.delete_many({"action_id": "test_iter42_att"})
        sample_pdf = b"%PDF-1.4\n%FakePDFforTests\n%%EOF"
        sample_b64 = base64.b64encode(sample_pdf).decode("ascii")
        ratt = await deliver_to_inbox(
            user_id=uid, recipient_email="x@y.z", recipient_name="X",
            subject="TEST_ITER42 con adjunto", html="<p>cuerpo</p>",
            action_id="test_iter42_att",
            attachments=[{"filename": "demo.pdf", "content": sample_b64}],
        )
        mid = ratt["message_id"]

        # Listado no debe exponer content_b64
        lst = await c.get(f"{BACKEND_URL}/inbox/me?limit=200", headers=h)
        item = next((m for m in lst.json()["items"] if m.get("message_id") == mid), None)
        assert item is not None
        att0 = item["attachments_meta"][0]
        assert att0["filename"] == "demo.pdf"
        assert att0["mime_type"] == "application/pdf"
        assert "content_b64" not in att0

        # Descarga binaria correcta
        rd = await c.get(f"{BACKEND_URL}/inbox/{mid}/attachments/0", headers=h)
        assert rd.status_code == 200
        assert rd.headers["content-type"].startswith("application/pdf")
        assert "demo.pdf" in rd.headers.get("content-disposition", "")
        assert rd.content == sample_pdf

        # Índice fuera de rango → 404
        rbad = await c.get(f"{BACKEND_URL}/inbox/{mid}/attachments/9", headers=h)
        assert rbad.status_code == 404

        # Mensaje legacy sin content_b64 → 410
        await db.inbox_messages.update_one(
            {"message_id": mid},
            {"$set": {"attachments_meta.0.content_b64": ""}},
        )
        rgone = await c.get(f"{BACKEND_URL}/inbox/{mid}/attachments/0", headers=h)
        assert rgone.status_code == 410

        await db.inbox_messages.delete_many({"action_id": "test_iter42_att"})

        # ------- 5) Iter46: mensajería user-to-user -------
        await db.inbox_messages.delete_many({"action_id": "user_message", "subject": {"$regex": "^TEST_ITER46"}})

        users_list = await c.get(f"{BACKEND_URL}/auth/users", headers=h)
        assert users_list.status_code == 200
        all_users = users_list.json()
        targets = [u["user_id"] for u in all_users if u["user_id"] != uid][:2]
        assert len(targets) >= 1, "no hay otros usuarios para test"

        rsend = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={
                "recipient_user_ids": targets,
                "subject": "TEST_ITER46 saludo",
                "body": "Hola!\n\n- Punto uno\n- Punto dos\n\nSaludos.",
            },
            headers=h,
        )
        assert rsend.status_code == 200, rsend.text
        sent = rsend.json()
        assert sent["delivered_count"] == len(targets)

        # Verificar que cada destinatario tiene su conversación (Iter48: chat continuo)
        for d in sent["delivered"]:
            assert "conversation_id" in d and "message_id" in d
            conv = await db.conversations.find_one(
                {"conversation_id": d["conversation_id"]}, {"_id": 0}
            )
            assert conv is not None
            assert uid in conv["participants"]
            assert conv["subject"] == "TEST_ITER46 saludo"
            msg = await db.conversation_messages.find_one(
                {"message_id": d["message_id"]}, {"_id": 0}
            )
            assert msg is not None
            assert msg["from_user_id"] == uid
            assert "Hola!" in msg["body_plain"]

        # Validación: lista vacía → 422 (min_length=1)
        rbad = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={"recipient_user_ids": [], "subject": "X", "body": "Y"},
            headers=h,
        )
        assert rbad.status_code == 422

        # Iter48: el body se almacena en `body_plain` literal sin transformar.
        # El render del chat usa `whitespace-pre-wrap` en CSS, así que el HTML
        # del cliente NO se interpreta — la seguridad es responsabilidad del
        # frontend (React escapa interpolaciones por defecto).
        rxss = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={
                "recipient_user_ids": [targets[0]],
                "subject": "TEST_ITER46 xss",
                "body": "<script>alert(1)</script><b>negrita</b>",
            },
            headers=h,
        )
        assert rxss.status_code == 200
        mid = rxss.json()["delivered"][0]["message_id"]
        msg = await db.conversation_messages.find_one({"message_id": mid}, {"_id": 0})
        assert msg is not None
        # El body_plain conserva el texto tal cual (literal). React lo escapa al renderizar.
        assert msg["body_plain"] == "<script>alert(1)</script><b>negrita</b>"

        # Cleanup Iter48
        await db.conversations.delete_many({"subject": {"$regex": "^TEST_ITER46"}})
        await db.conversation_messages.delete_many({"from_user_id": uid})

        # ------- 6) Iter48: Chat continuo end-to-end -------
        # Limpiar cualquier conversación previa con el target
        await db.conversations.delete_many({"participants": {"$all": [uid, targets[0]]}})

        # 6.1: nuevo hilo
        r6 = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={
                "recipient_user_ids": [targets[0]],
                "subject": "TEST_ITER48 hilo",
                "body": "Mensaje 1",
            },
            headers=h,
        )
        assert r6.status_code == 200
        conv_id = r6.json()["delivered"][0]["conversation_id"]

        # 6.2: 3 respuestas consecutivas → mismo hilo, NO crean filas duplicadas
        for body in ["Respuesta 2", "Respuesta 3", "Respuesta 4"]:
            rr = await c.post(
                f"{BACKEND_URL}/inbox/conversations/{conv_id}/messages",
                json={"body": body},
                headers=h,
            )
            assert rr.status_code == 200, rr.text

        # 6.3: GET messages — debe haber 4 mensajes asc
        rmsgs = await c.get(
            f"{BACKEND_URL}/inbox/conversations/{conv_id}/messages",
            headers=h,
        )
        assert rmsgs.status_code == 200
        thread = rmsgs.json()
        assert len(thread["messages"]) == 4
        bodies = [m["body_plain"] for m in thread["messages"]]
        assert bodies == ["Mensaje 1", "Respuesta 2", "Respuesta 3", "Respuesta 4"]
        # Todos son míos en este test
        assert all(m["is_mine"] for m in thread["messages"])

        # 6.4: la bandeja muestra UN SOLO row (hilo único)
        rinbox = await c.get(f"{BACKEND_URL}/inbox/me", headers=h)
        items = rinbox.json()["items"]
        convs = [i for i in items if i.get("type") == "conversation" and i.get("conversation_id") == conv_id]
        assert len(convs) == 1, f"esperaba 1 fila conversation, obtuve {len(convs)}"
        assert "Respuesta 4" in convs[0]["last_preview"]

        # 6.5: una conversación entre los mismos pero con OTRO asunto crea hilo separado
        r65 = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={
                "recipient_user_ids": [targets[0]],
                "subject": "TEST_ITER48 otro tema",
                "body": "Tema distinto",
            },
            headers=h,
        )
        conv_id_2 = r65.json()["delivered"][0]["conversation_id"]
        assert conv_id_2 != conv_id

        # 6.6: DELETE soft-archiva sólo para el usuario actual
        rdel = await c.delete(
            f"{BACKEND_URL}/inbox/conversations/{conv_id}",
            headers=h,
        )
        assert rdel.status_code == 200
        # Ya no aparece en la bandeja del admin
        rinbox2 = await c.get(f"{BACKEND_URL}/inbox/me", headers=h)
        convs2 = [
            i for i in rinbox2.json()["items"]
            if i.get("type") == "conversation" and i.get("conversation_id") == conv_id
        ]
        assert len(convs2) == 0

        # Pero el documento sigue existiendo en DB (no se borró)
        doc = await db.conversations.find_one({"conversation_id": conv_id}, {"_id": 0})
        assert doc is not None
        assert uid in doc["deleted_for"]

        # 6.7: summary cuenta conversaciones también
        rsum = await c.get(f"{BACKEND_URL}/inbox/me/summary", headers=h)
        assert rsum.status_code == 200
        s = rsum.json()
        assert isinstance(s["total"], int) and s["total"] >= 1

        # 6.8: no puedo enviarme mensaje a mí mismo (sender es excluido)
        rself = await c.post(
            f"{BACKEND_URL}/inbox/send",
            json={"recipient_user_ids": [uid], "subject": "self", "body": "x"},
            headers=h,
        )
        assert rself.status_code == 400

        # Cleanup final
        await db.conversations.delete_many({"subject": {"$regex": "^TEST_ITER48"}})
        await db.conversation_messages.delete_many({"conversation_id": {"$in": [conv_id, conv_id_2]}})


def test_inbox_center_full_suite():
    """Una sola función para reutilizar el event loop de motor."""
    asyncio.run(_run_all())
