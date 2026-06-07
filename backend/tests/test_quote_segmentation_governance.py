# ruff: noqa
"""
Gobierno de Datos — Segmentación de Cotizaciones de Implementación (P0).

Valida en el límite de seguridad (backend GET /api/quotes) que:
  - Un usuario de sede PYME solo ve cotizaciones de Implementación PYME.
  - Un usuario de sede CORP solo ve cotizaciones de Implementación CORP.
  - El segmento (client_segment = user_sede) es el discriminador, INDEPENDIENTE
    del filtro departamental (ambos gerentes comparten el mismo departamento).

Crea registros temporales con prefijo TESTSEG_ y los elimina por ID al final
(NUNCA usa delete_many({})).
"""
import asyncio
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BASE = "http://localhost:8001/api"

TAG = "TESTSEG_"
DEPT = TAG + "Dept"


def _user(sede, cargo):
    uid = TAG + uuid.uuid4().hex[:8]
    return {
        "user_id": uid,
        "email": f"{uid}@testseg.local",
        "first_name": "Seg",
        "last_name": sede,
        "role": "user",
        "sede": sede,
        "cargo": cargo,
        "departamento": DEPT,
        "is_active": True,
        "permissions": {"cotizaciones": "edit"},
        "special_permissions": ["cotizaciones:impl_pyme", "cotizaciones:impl_corp"],
    }


def _session(user_id):
    tok = TAG + secrets.token_hex(16)
    return {
        "session_token": tok,
        "user_id": user_id,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
    }


def _quote(creator_uid, segment):
    qid = TAG + uuid.uuid4().hex[:8]
    return {
        "quote_id": qid,
        "quote_number": f"{TAG}{segment}-{uuid.uuid4().hex[:4]}",
        "client_id": TAG + "client",
        "client_name": f"Cliente {segment}",
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "client_segment": segment,
        "sede": segment,
        "created_by_user_id": creator_uid,
        "subtotal_usd": 100.0,
        "total_usd": 100.0,
        "exchange_rate": 40.0,
        "total_bs": 4000.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archived": False,
    }


async def run():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    pyme_mgr = _user("PYME", "Gerente")
    corp_mgr = _user("CORP", "Gerente")
    member = _user("PYME", "Ejecutivo")  # creador común de ambas cotizaciones

    pyme_sess = _session(pyme_mgr["user_id"])
    corp_sess = _session(corp_mgr["user_id"])

    q_pyme = _quote(member["user_id"], "PYME")
    q_corp = _quote(member["user_id"], "CORP")

    created_users = [pyme_mgr, corp_mgr, member]
    created_sessions = [pyme_sess, corp_sess]
    created_quotes = [q_pyme, q_corp]

    try:
        await db.users.insert_many(created_users)
        await db.user_sessions.insert_many(created_sessions)
        await db.quotes.insert_many(created_quotes)

        async with httpx.AsyncClient(timeout=30) as client:
            r_pyme = await client.get(
                f"{BASE}/quotes",
                headers={"Authorization": f"Bearer {pyme_sess['session_token']}"},
            )
            r_corp = await client.get(
                f"{BASE}/quotes",
                headers={"Authorization": f"Bearer {corp_sess['session_token']}"},
            )

        assert r_pyme.status_code == 200, r_pyme.text
        assert r_corp.status_code == 200, r_corp.text

        pyme_ids = {q["quote_id"] for q in r_pyme.json()}
        corp_ids = {q["quote_id"] for q in r_corp.json()}

        # PYME manager: ve PYME, NO ve CORP
        assert q_pyme["quote_id"] in pyme_ids, "PYME mgr debería ver la cotización PYME"
        assert q_corp["quote_id"] not in pyme_ids, "PYME mgr NO debe ver la cotización CORP (segmentación)"

        # CORP manager: ve CORP, NO ve PYME
        assert q_corp["quote_id"] in corp_ids, "CORP mgr debería ver la cotización CORP"
        assert q_pyme["quote_id"] not in corp_ids, "CORP mgr NO debe ver la cotización PYME (segmentación)"

        # Confirmar que TODAS las implementación devueltas respetan el segmento del usuario
        for q in r_pyme.json():
            if q.get("quote_category") == "implementation":
                assert (q.get("client_segment") or "PYME").upper() == "PYME"
        for q in r_corp.json():
            if q.get("quote_category") == "implementation":
                assert (q.get("client_segment") or "PYME").upper() == "CORP"

        print("PASS: Segmentación de cotizaciones de Implementación PYME/CORP correcta.")
    finally:
        await db.quotes.delete_many({"quote_id": {"$in": [q["quote_id"] for q in created_quotes]}})
        await db.user_sessions.delete_many({"session_token": {"$in": [s["session_token"] for s in created_sessions]}})
        await db.users.delete_many({"user_id": {"$in": [u["user_id"] for u in created_users]}})
        c.close()


def test_quote_segmentation_governance():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
