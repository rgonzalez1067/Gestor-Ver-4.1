"""Tests para la regla de visibilidad por Sede (Administración) y Director.

Cubre:
  1. Director (cargo contiene "Director") → ve TODAS las cotizaciones, sin importar sede.
  2. Administración Pyme → solo ve cotizaciones con client_segment=PYME.
  3. Administración Corp → solo ve cotizaciones con client_segment=CORP.
  4. GET /api/quotes/{id}: Administración bloquea acceso (403) si la sede no coincide.
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
    pw = _hash("Test1234!")
    users = [
        {
            "user_id": "test_admin_pyme", "email": "tadmin_pyme@megasoft.com.ve",
            "password_hash": pw, "first_name": "Admin", "last_name": "Pyme",
            "role": "user", "cargo": "Asistente Administrativo",
            "departamento": "Administración",
            "sede": "PYME", "is_active": True,
            "permissions": {"cotizaciones": "read"}, "menu_groups": {"gestion_comercial": True},
        },
        {
            "user_id": "test_admin_corp", "email": "tadmin_corp@megasoft.com.ve",
            "password_hash": pw, "first_name": "Admin", "last_name": "Corp",
            "role": "user", "cargo": "Asistente Administrativo",
            "departamento": "Administración",
            "sede": "CORP", "is_active": True,
            "permissions": {"cotizaciones": "read"}, "menu_groups": {"gestion_comercial": True},
        },
        {
            "user_id": "test_director", "email": "tdirector@megasoft.com.ve",
            "password_hash": pw, "first_name": "El", "last_name": "Director",
            "role": "user", "cargo": "Director General",
            "departamento": "Dirección",
            "sede": "PYME", "is_active": True,
            "permissions": {"cotizaciones": "read"}, "menu_groups": {"gestion_comercial": True},
        },
    ]
    for u in users:
        await db.users.update_one({"user_id": u["user_id"]}, {"$set": u}, upsert=True)

    # Cotizaciones de prueba: 2 sede PYME y 2 sede CORP
    quotes = []
    for i, segment in enumerate(["PYME", "PYME", "CORP", "CORP"]):
        quotes.append({
            "quote_id": f"qid_visib_test_{i:03d}",
            "quote_number": f"COT-VISIB-{i:03d}",
            "client_segment": segment,
            "client_id": f"test_client_{i}",
            "client_name": f"Cliente Test {i}",
            "quote_status": "Borrador",
            "created_by_user_id": "test_dept_unrelated",
            "created_by_name": "Otro",
            "created_at": "2026-01-01T00:00:00+00:00",
            "quote_type": "VPOS", "quote_category": "implementation",
            "total_usd": 0, "total_bs": 0, "subtotal_usd": 0, "exchange_rate": 36.0,
            "services": [], "hardware": [],
            "archived": False,
        })
    for q in quotes:
        await db.quotes.update_one({"quote_id": q["quote_id"]}, {"$set": q}, upsert=True)


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.users.delete_many({"user_id": {"$in": [
        "test_admin_pyme", "test_admin_corp", "test_director"
    ]}})
    await db.quotes.delete_many({"quote_id": {"$regex": "^qid_visib_test_"}})


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def _list_quotes(token):
    r = requests.get(f"{API}/api/quotes", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()


def _get_quote(token, qid):
    return requests.get(f"{API}/api/quotes/{qid}", headers={"Authorization": f"Bearer {token}"})


def test_admin_pyme_sees_only_pyme_quotes():
    asyncio.run(_seed())
    try:
        tok = _login("tadmin_pyme@megasoft.com.ve", "Test1234!")
        quotes = _list_quotes(tok)
        # Debe ver SOLO las dos PYME que sembramos
        seeded_visible = [q for q in quotes if q["quote_id"].startswith("qid_visib_test_")]
        seg_set = {q.get("client_segment") for q in seeded_visible}
        ids = {q["quote_id"] for q in seeded_visible}
        assert ids == {"qid_visib_test_000", "qid_visib_test_001"}, (
            f"Admin PYME debería ver SOLO las 2 cotizaciones PYME sembradas, vio: {ids}"
        )
        assert seg_set == {"PYME"}, f"Admin PYME debería ver solo segment=PYME, vio: {seg_set}"

        # GET /quotes/{id} sobre un CORP debe ser 403
        r = _get_quote(tok, "qid_visib_test_002")  # CORP
        assert r.status_code == 403, f"Admin PYME no debe acceder a CORP, got {r.status_code}"
        # GET /quotes/{id} sobre un PYME debe ser 200
        r = _get_quote(tok, "qid_visib_test_000")  # PYME
        assert r.status_code == 200, f"Admin PYME debe acceder a PYME, got {r.status_code}: {r.text}"
    finally:
        asyncio.run(_cleanup())


def test_admin_corp_sees_only_corp_quotes():
    asyncio.run(_seed())
    try:
        tok = _login("tadmin_corp@megasoft.com.ve", "Test1234!")
        quotes = _list_quotes(tok)
        seeded_visible = [q for q in quotes if q["quote_id"].startswith("qid_visib_test_")]
        seg_set = {q.get("client_segment") for q in seeded_visible}
        ids = {q["quote_id"] for q in seeded_visible}
        assert ids == {"qid_visib_test_002", "qid_visib_test_003"}, (
            f"Admin CORP debería ver SOLO las 2 cotizaciones CORP sembradas, vio: {ids}"
        )
        assert seg_set == {"CORP"}, f"Admin CORP debería ver solo segment=CORP, vio: {seg_set}"

        r = _get_quote(tok, "qid_visib_test_000")  # PYME
        assert r.status_code == 403, f"Admin CORP no debe acceder a PYME, got {r.status_code}"
        r = _get_quote(tok, "qid_visib_test_002")  # CORP
        assert r.status_code == 200, f"Admin CORP debe acceder a CORP, got {r.status_code}: {r.text}"
    finally:
        asyncio.run(_cleanup())


def test_director_sees_all_segments():
    asyncio.run(_seed())
    try:
        tok = _login("tdirector@megasoft.com.ve", "Test1234!")
        quotes = _list_quotes(tok)
        seeded_visible = [q for q in quotes if q["quote_id"].startswith("qid_visib_test_")]
        ids = {q["quote_id"] for q in seeded_visible}
        assert ids == {
            "qid_visib_test_000", "qid_visib_test_001",
            "qid_visib_test_002", "qid_visib_test_003",
        }, f"Director debería ver las 4 cotizaciones sembradas, vio: {ids}"

        # GET por ID en ambas sedes debe ser 200
        r = _get_quote(tok, "qid_visib_test_000")  # PYME
        assert r.status_code == 200, f"Director debe acceder a PYME, got {r.status_code}"
        r = _get_quote(tok, "qid_visib_test_002")  # CORP
        assert r.status_code == 200, f"Director debe acceder a CORP, got {r.status_code}"
    finally:
        asyncio.run(_cleanup())
