"""Tests para el flujo Aprobación de cotización (multipart con payment_files efímeros).

Cubre:
  1. Aprobación SIN payment files: solo payload JSON (form field `payload`).
  2. Aprobación con payment files: archivos no se persisten en quote.attachments.
  3. Custom message hasta 300 caracteres aceptado.
"""
import asyncio
import os
import sys
import io
import json as _json
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
    # Cliente de prueba con address + contacto
    client = {
        "client_id": "test_cli_approve_001",
        "rif": "J999999999",
        "legal_name": "ASTRO CLIENTE TEST, C.A.",
        "fantasy_name": "ASTRO TEST",
        "address": "Av Libertador Local AR46 Caracas Miranda",
        "segment": "Pymes",
        "contacts": [{
            "full_name": "Juan Pérez",
            "email": "juan@astrotest.com",
            "phone": "+58 414 1234567",
        }],
    }
    await db.clients.update_one({"client_id": client["client_id"]}, {"$set": client}, upsert=True)
    # Cotización Enviada (regular) — Implementación VPOS
    quote = {
        "quote_id": "qid_approve_test_001",
        "quote_number": "COT-APPROVE-TEST-001",
        "client_segment": "PYME",
        "sede": "PYME",
        "client_id": client["client_id"],
        "client_name": client["fantasy_name"],
        "client_rif": client["rif"],
        "quote_status": "Enviada",
        "quote_type": "VPOS",
        "quote_category": "implementation",
        "total_usd": 348, "total_bs": 0, "subtotal_usd": 348, "exchange_rate": 36.0,
        "services": [], "hardware": [],
        "archived": False,
        "attachments": [],
        "created_by_user_id": "test_creator",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    await db.quotes.update_one({"quote_id": quote["quote_id"]}, {"$set": quote}, upsert=True)


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.clients.delete_many({"client_id": "test_cli_approve_001"})
    await db.quotes.delete_many({"quote_id": "qid_approve_test_001"})


async def _reset_quote_status():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.quotes.update_one(
        {"quote_id": "qid_approve_test_001"},
        {"$set": {"quote_status": "Enviada", "approved_at": None, "attachments": []}},
    )


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def _payload(custom=None):
    return {
        "consolidated_items": [
            {"name": "VPOS Setup", "quantity": 1, "total_usd": 300,
             "exchange_rate": 36.0, "total_bs": 10800.0}
        ],
        "exchange_rate": 36.0, "rate_source": "BCV", "billing_date": "2026-02-15",
        "grand_total_usd": 300, "grand_total_bs": 10800.0,
        "iva_usd": 48, "iva_bs": 1728.0,
        "grand_total_con_iva_usd": 348, "grand_total_con_iva_bs": 12528.0,
        "has_payment_proof": False, "has_approval_proof": False,
    }


def test_approve_without_payment_files():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        files = {"payload": (None, _json.dumps(_payload()))}
        r = requests.post(
            f"{API}/api/quotes/qid_approve_test_001/approve",
            files=files,
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, f"approve sin payment files debe ser 200, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("new_status") == "Aprobada"
    finally:
        asyncio.run(_cleanup())


def test_approve_with_payment_files_not_persisted():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        # Multipart con payload + payment_files efímero
        files = [
            ("payload", (None, _json.dumps(_payload()))),
            ("payment_files", ("pago_anticipado.txt", b"comprobante de pago anticipado", "text/plain")),
        ]
        r = requests.post(
            f"{API}/api/quotes/qid_approve_test_001/approve",
            files=files,
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, f"approve con payment_files debe ser 200, got {r.status_code}: {r.text}"

        # Verificar que el archivo NO se persistió en quote.attachments
        async def _check():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            return await db.quotes.find_one(
                {"quote_id": "qid_approve_test_001"}, {"_id": 0, "attachments": 1}
            )
        q = asyncio.run(_check())
        atts = (q or {}).get("attachments") or []
        cats = [a.get("category") for a in atts]
        assert "Soporte de Aprobación" not in cats, f"Pago anticipado NO debe persistirse, vio cats={cats}"
    finally:
        asyncio.run(_cleanup())


def test_approve_with_300_char_custom_message():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        msg_300 = "A" * 300
        files = {"payload": (None, _json.dumps(_payload()))}
        r = requests.post(
            f"{API}/api/quotes/qid_approve_test_001/approve",
            files=files,
            headers={
                "Authorization": f"Bearer {tok}",
                "x-custom-message": msg_300,
            },
        )
        assert r.status_code == 200, f"approve con mensaje de 300 chars debe ser 200, got {r.status_code}: {r.text}"
    finally:
        asyncio.run(_cleanup())
