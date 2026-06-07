# ruff: noqa
"""Tests para acción 'Reparada' (repair-complete) de cotizaciones de Reparación.

Verifica que:
  1. Se generen los correos a Administración + Cliente.
  2. SOLO el correo de Administración lleve el PDF "Cálculos Definitivos".
  3. El correo del Cliente NO lleve attachments.
"""
import asyncio
import json as _json
import os
import secrets
import hashlib
import sys

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
    # Cliente con address + contacto
    client = {
        "client_id": "test_cli_repair_001",
        "rif": "J888888888",
        "legal_name": "REPAIR TEST CLIENT, C.A.",
        "fantasy_name": "REPAIR TEST",
        "address": "Av. Reparaciones 12, Caracas",
        "segment": "Pymes",
        "contacts": [{
            "full_name": "Pedro Repair",
            "email": "pedro@repair.test",
            "phone": "+58-414-8888888",
        }],
    }
    await db.clients.update_one({"client_id": client["client_id"]}, {"$set": client}, upsert=True)
    # Cotización de Reparación en estado Aprobada (precondición de repair-complete)
    quote = {
        "quote_id": "qid_repair_test_001",
        "quote_number": "COT-REPAIR-TEST-001",
        "client_segment": "PYME",
        "sede": "PYME",
        "client_id": client["client_id"],
        "client_name": client["fantasy_name"],
        "client_rif": client["rif"],
        "quote_status": "Aprobada",
        "quote_type": "REPAIR",
        "quote_category": "repair",
        "total_usd": 200, "total_bs": 7200, "subtotal_usd": 200, "exchange_rate": 36.0,
        "services": [], "hardware": [],
        "repair_models": [
            {"model_id": "m1", "model_name": "VeriFone VX520", "serials": ["SN001", "SN002"]}
        ],
        "archived": False,
        "created_by_user_id": "user_admin_main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    await db.quotes.update_one({"quote_id": quote["quote_id"]}, {"$set": quote}, upsert=True)
    # Asegurar config con admin_email para sede PYME
    cfg = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    emails_by_sede = (cfg or {}).get("emails_by_sede", {}) if cfg else {}
    emails_by_sede.setdefault("PYME", {})["admin"] = emails_by_sede.get("PYME", {}).get("admin") or "admin.test@megasoft.test"
    await db.config.update_one(
        {"type": "app_settings"},
        {"$set": {"emails_by_sede": emails_by_sede, "type": "app_settings"}},
        upsert=True,
    )


async def _cleanup():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]
    await db.clients.delete_many({"client_id": "test_cli_repair_001"})
    await db.quotes.delete_many({"quote_id": "qid_repair_test_001"})
    await db.email_logs.delete_many({"quote_id": "qid_repair_test_001"})


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def test_repair_complete_admin_gets_pdf_client_does_not():
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        billing_data = {
            "consolidated_items": [
                {"name": "Reparación VX520 (Mano de obra)", "quantity": 2,
                 "total_usd": 200.0, "exchange_rate": 36.0, "total_bs": 7200.0}
            ],
            "exchange_rate": 36.0, "rate_source": "BCV", "billing_date": "2026-02-15",
            "grand_total_usd": 200.0, "grand_total_bs": 7200.0,
            "iva_usd": 32.0, "iva_bs": 1152.0,
            "grand_total_con_iva_usd": 232.0, "grand_total_con_iva_bs": 8352.0,
        }
        r = requests.post(
            f"{API}/api/quotes/qid_repair_test_001/repair-complete",
            json={"billing_data": billing_data},
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, f"repair-complete debe ser 200, got {r.status_code}: {r.text}"

        # Validar email_logs: admin debe tener has_attachment=True, cliente=False
        async def _get_logs():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            logs = await db.email_logs.find(
                {"quote_id": "qid_repair_test_001"},
                {"_id": 0, "action": 1, "to": 1, "has_attachment": 1},
            ).to_list(20)
            return logs
        logs = asyncio.run(_get_logs())
        assert logs, "Debe existir al menos un email_log para esta cotización"

        admin_logs = [lg for lg in logs if lg.get("action") in ("repair_complete_admin", "repair_complete_no_config")]
        client_logs = [lg for lg in logs if lg.get("action") == "repair_complete_client"]
        assert admin_logs, f"Debe existir log para admin/no_config, vio {[lg.get('action') for lg in logs]}"
        assert client_logs, f"Debe existir log para cliente, vio {[lg.get('action') for lg in logs]}"

        for al in admin_logs:
            assert al.get("has_attachment") is True, (
                f"El correo a admin DEBE llevar attachment (PDF Cálculos Definitivos), log={al}"
            )
        for cl in client_logs:
            assert cl.get("has_attachment") in (False, None), (
                f"El correo al cliente NO debe llevar attachment, log={cl}"
            )
    finally:
        asyncio.run(_cleanup())


def test_repair_complete_without_billing_data_no_pdf():
    """Si por algún motivo no se envía billing_data, ni admin ni cliente reciben PDF."""
    asyncio.run(_seed())
    try:
        tok = _login("rgonzalez@megasoft.com.ve", "admin123")
        r = requests.post(
            f"{API}/api/quotes/qid_repair_test_001/repair-complete",
            json={},  # sin billing_data
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 200, f"repair-complete sin billing_data debe ser 200, got {r.status_code}: {r.text}"

        async def _get_logs():
            c = AsyncIOMotorClient(os.environ['MONGO_URL'])
            db = c[os.environ['DB_NAME']]
            return await db.email_logs.find(
                {"quote_id": "qid_repair_test_001"},
                {"_id": 0, "action": 1, "has_attachment": 1},
            ).to_list(20)
        logs = asyncio.run(_get_logs())
        for log in logs:
            assert log.get("has_attachment") in (False, None), (
                f"Sin billing_data, NINGÚN correo debe llevar attachment, log={log}"
            )
    finally:
        asyncio.run(_cleanup())
