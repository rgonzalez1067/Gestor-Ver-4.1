"""Tests para "Modificar Cotización" con elección de modo (in_place vs new_version).

Cubre:
  1. mode=new_version (default): crea nueva cotización con número siguiente.
  2. mode=in_place: mantiene mismo quote_id y quote_number, reinicia a Borrador,
     limpia attachments y timestamps. Bitácora con quién y cuándo.
  3. Bitácora siempre se registra en ambos modos.
"""
import asyncio
import os
import sys
import requests

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')

API = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


async def _seed():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    quote = {
        "quote_id": "qid_modify_test_001",
        "quote_number": "COT-MOD-TEST-001",
        "client_segment": "PYME",
        "sede": "PYME",
        "client_id": "test_cli_modify",
        "client_name": "TEST MODIFY",
        "quote_status": "Aprobada",
        "approved_at": "2026-01-15T10:00:00+00:00",
        "sent_to_client_at": "2026-01-10T12:00:00+00:00",
        "quote_type": "VPOS",
        "quote_category": "implementation",
        "total_usd": 200, "total_bs": 7200,
        "services": [], "hardware": [],
        "attachments": [{"filename": "old_anex.pdf", "url": "/uploads/old_anex.pdf", "category": "Cotización"}],
        "version": 1,
        "archived": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "created_by_user_id": "user_creator",
    }
    await db.quotes.update_one({"quote_id": quote["quote_id"]}, {"$set": quote}, upsert=True)


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.quotes.delete_many({"quote_id": {"$in": ["qid_modify_test_001"]}})
    await db.quotes.delete_many({"quote_number": {"$regex": "COT-MOD-TEST-"}})
    await db.quotes.delete_many({"parent_quote_id": "qid_modify_test_001"})
    await db.bitacora.delete_many({"quote_id": "qid_modify_test_001"})
    await db.bitacora.delete_many({"original_quote_id": "qid_modify_test_001"})


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def test_duplicate_in_place_keeps_number_and_resets():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        r = requests.post(
            f"{API}/api/quotes/qid_modify_test_001/duplicate",
            params={"mode": "in_place"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, f"in_place debe ser 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["mode"] == "in_place"
        assert data["new_quote_id"] == "qid_modify_test_001", f"in_place debe mantener mismo id, got {data}"
        assert data["new_quote_number"] == "COT-MOD-TEST-001", f"in_place debe mantener mismo número"

        async def _get_quote_and_bitacora():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            q = await db.quotes.find_one({"quote_id": "qid_modify_test_001"}, {"_id": 0})
            bit = await db.bitacora.find_one(
                {"quote_id": "qid_modify_test_001", "action": "quote_modified_in_place"},
                {"_id": 0},
            )
            return q, bit

        q, bit = asyncio.run(_get_quote_and_bitacora())
        assert q["quote_status"] == "Borrador", f"in_place debe reiniciar a Borrador, got {q['quote_status']}"
        assert q["approved_at"] is None, "in_place debe limpiar approved_at"
        assert q["sent_to_client_at"] is None, "in_place debe limpiar sent_to_client_at"
        assert q["attachments"] == [], "in_place debe limpiar attachments"
        assert q.get("modified_in_place_at"), "in_place debe registrar timestamp"
        assert q.get("modified_in_place_by"), "in_place debe registrar usuario"

        assert bit, "Debe existir entrada en bitácora con action=quote_modified_in_place"
        assert bit["previous_status"] == "Aprobada", f"bitácora debe registrar estado previo, got {bit}"
        assert bit.get("executed_by"), "bitácora debe registrar executed_by"
        assert bit.get("executed_at"), "bitácora debe registrar executed_at"
    finally:
        asyncio.run(_cleanup())


def test_duplicate_new_version_creates_new_quote():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        r = requests.post(
            f"{API}/api/quotes/qid_modify_test_001/duplicate",
            params={"mode": "new_version"},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "new_version"
        assert data["new_quote_id"] != "qid_modify_test_001", "new_version debe generar nuevo quote_id"
        assert data["new_quote_number"] != "COT-MOD-TEST-001", "new_version debe generar nuevo número"
        assert data["version"] == 2, f"new_version debe incrementar version, got {data['version']}"

        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            original = await db.quotes.find_one({"quote_id": "qid_modify_test_001"}, {"_id": 0})
            new_quote = await db.quotes.find_one({"quote_id": data["new_quote_id"]}, {"_id": 0})
            bit = await db.bitacora.find_one(
                {"original_quote_id": "qid_modify_test_001", "action": "quote_modified_new_version"},
                {"_id": 0},
            )
            return original, new_quote, bit

        original, new_quote, bit = asyncio.run(_check())
        # Original debe quedar intacta
        assert original["quote_status"] == "Aprobada", "Original debe permanecer en estado Aprobada"
        assert original["attachments"], "Original conserva sus attachments"
        # Nueva debe estar en Borrador, sin attachments
        assert new_quote["quote_status"] == "Borrador"
        assert new_quote["attachments"] == []
        assert new_quote["parent_quote_id"] == "qid_modify_test_001"
        assert bit, "Bitácora debe registrar new_version"
        assert bit.get("new_quote_id") == data["new_quote_id"]
    finally:
        asyncio.run(_cleanup())


def test_duplicate_default_mode_is_new_version():
    """Sin pasar el param `mode`, el comportamiento por default debe ser new_version
    (compatibilidad con clientes legacy)."""
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        r = requests.post(
            f"{API}/api/quotes/qid_modify_test_001/duplicate",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "new_version"
        assert data["new_quote_id"] != "qid_modify_test_001"
    finally:
        asyncio.run(_cleanup())
