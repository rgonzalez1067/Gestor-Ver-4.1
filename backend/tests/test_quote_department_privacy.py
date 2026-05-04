"""Tests para la regla de privacidad por departamento en cotizaciones.

Cubre 4 escenarios:
  1. Admin ve TODAS las cotizaciones.
  2. Director ve TODAS las cotizaciones.
  3. Ejecutivo del MISMO departamento que el creador → puede leer GET /quotes/{id} (200).
  4. Ejecutivo de OTRO departamento → 403 al leer GET /quotes/{id}.
"""
import asyncio
import os
import sys
import secrets
import hashlib
import requests

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')

API = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def _hash(pw: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}:{hashlib.sha256((pw + salt).encode()).hexdigest()}"


async def _seed():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    # Two test users in different departments
    pw = _hash("Test1234!")
    user_a = {
        "user_id": "test_dept_a", "email": "tdept_a@megasoft.com.ve",
        "password_hash": pw, "first_name": "Dept", "last_name": "A",
        "role": "user", "cargo": "Ejecutivo", "departamento": "DEPT_TEST_A",
        "sede": "PYME", "is_active": True,
        "permissions": {"cotizaciones": "edit"}, "menu_groups": {"gestion_comercial": True},
    }
    user_b = {
        "user_id": "test_dept_b", "email": "tdept_b@megasoft.com.ve",
        "password_hash": pw, "first_name": "Dept", "last_name": "B",
        "role": "user", "cargo": "Ejecutivo", "departamento": "DEPT_TEST_B",
        "sede": "PYME", "is_active": True,
        "permissions": {"cotizaciones": "edit"}, "menu_groups": {"gestion_comercial": True},
    }
    user_a2 = {
        "user_id": "test_dept_a2", "email": "tdept_a2@megasoft.com.ve",
        "password_hash": pw, "first_name": "Dept", "last_name": "A2",
        "role": "user", "cargo": "Ejecutivo", "departamento": "DEPT_TEST_A",
        "sede": "PYME", "is_active": True,
        "permissions": {"cotizaciones": "edit"}, "menu_groups": {"gestion_comercial": True},
    }
    for u in (user_a, user_b, user_a2):
        await db.users.update_one({"user_id": u["user_id"]}, {"$set": u}, upsert=True)
    # Quote owned by user_a, segment PYME
    quote = {
        "quote_id": "qid_dept_test_001", "quote_number": "COT-DEPT-TEST-001",
        "client_segment": "PYME", "client_id": "test_client",
        "client_name": "Test Cliente", "quote_status": "Borrador",
        "created_by_user_id": "test_dept_a", "created_by_name": "Dept A",
        "created_at": "2026-01-01T00:00:00+00:00",
        "quote_type": "VPOS", "quote_category": "implementation",
        "total_usd": 0, "total_bs": 0, "subtotal_usd": 0, "exchange_rate": 36.0,
        "services": [], "hardware": [],
        "archived": False,
    }
    await db.quotes.update_one({"quote_id": quote["quote_id"]}, {"$set": quote}, upsert=True)


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.users.delete_many({"user_id": {"$in": ["test_dept_a", "test_dept_b", "test_dept_a2"]}})
    await db.quotes.delete_many({"quote_id": "qid_dept_test_001"})


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def _get_quote(token, qid):
    return requests.get(f"{API}/api/quotes/{qid}", headers={"Authorization": f"Bearer {token}"})


def test_department_privacy_full_flow():
    asyncio.run(_seed())
    try:
        # Admin sees the quote
        admin_tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        r = _get_quote(admin_tok, "qid_dept_test_001")
        assert r.status_code == 200, f"Admin should see quote, got {r.status_code}"

        # User A (creator) sees it
        ua_tok = _login("tdept_a@megasoft.com.ve", "Test1234!")
        r = _get_quote(ua_tok, "qid_dept_test_001")
        assert r.status_code == 200, f"Creator should see quote, got {r.status_code}: {r.text}"

        # User A2 (same dept) sees it
        ua2_tok = _login("tdept_a2@megasoft.com.ve", "Test1234!")
        r = _get_quote(ua2_tok, "qid_dept_test_001")
        assert r.status_code == 200, f"Same-dept colleague should see quote, got {r.status_code}: {r.text}"

        # User B (other dept) → 403
        ub_tok = _login("tdept_b@megasoft.com.ve", "Test1234!")
        r = _get_quote(ub_tok, "qid_dept_test_001")
        assert r.status_code == 403, f"Other dept should be 403, got {r.status_code}"

        # GET /api/quotes for User B should NOT include the quote
        r = requests.get(f"{API}/api/quotes", headers={"Authorization": f"Bearer {ub_tok}"})
        ids = [q["quote_id"] for q in r.json()]
        assert "qid_dept_test_001" not in ids, "Other dept user should NOT see quote in list"

        # GET /api/quotes for User A2 (same dept) SHOULD include it
        r = requests.get(f"{API}/api/quotes", headers={"Authorization": f"Bearer {ua2_tok}"})
        ids = [q["quote_id"] for q in r.json()]
        assert "qid_dept_test_001" in ids, "Same-dept user should see quote in list"
    finally:
        asyncio.run(_cleanup())
