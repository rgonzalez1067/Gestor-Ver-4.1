"""
Procesador + Patrocinio Relacional — flujo end-to-end (backend).

Valida:
  - El maestro de Bancos acepta type="Procesador" y persiste el campo `procesador`
    (vía API POST /api/banks).
  - Una cotización patrocinada con procesador genera un Proyecto cuyo
    `patrocinador_label` = "Procesador — Banco" (compuesto) y persiste los IDs.
  - El escenario directo (sin procesador) genera `patrocinador_label` = "Banco".

Registros temporales con prefijo TESTPROC_, limpiados por ID al final.
"""
import asyncio
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/app/backend")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BASE = "http://localhost:8001/api"
TAG = "TESTPROC_"


async def run():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    from routes.quote_transitions import _create_project_from_quote

    # Admin token para la API de bancos
    admin = await db.users.find_one({"email": "rgonzalez@megasoft.com.ve"}, {"_id": 0, "user_id": 1})
    assert admin, "Admin no encontrado"
    admin_tok = TAG + secrets.token_hex(16)
    await db.user_sessions.insert_one({
        "session_token": admin_tok,
        "user_id": admin["user_id"],
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })

    proc_name = f"{TAG}ProcX_{uuid.uuid4().hex[:4]}"
    bank_name = f"{TAG}BancoY_{uuid.uuid4().hex[:4]}"
    created_bank_ids = []
    uid = TAG + uuid.uuid4().hex[:8]
    client_id = TAG + "cli_" + uuid.uuid4().hex[:8]
    quote_ids = []
    project_ids = []

    try:
        headers = {"Authorization": f"Bearer {admin_tok}"}
        async with httpx.AsyncClient(timeout=30) as client:
            # 1) Crear Procesador vía API
            r = await client.post(f"{BASE}/banks", json={
                "name": proc_name, "type": "Procesador", "country": "Venezuela",
            }, headers=headers)
            assert r.status_code in (200, 201), f"crear procesador: {r.status_code} {r.text}"
            proc_id = r.json().get("bank_id")
            created_bank_ids.append(proc_id)
            assert r.json().get("type") == "Procesador"

            # 2) Crear Banco vinculado al Procesador vía API
            r = await client.post(f"{BASE}/banks", json={
                "name": bank_name, "type": "Banco", "country": "Venezuela",
                "procesador": proc_name,
            }, headers=headers)
            assert r.status_code in (200, 201), f"crear banco: {r.status_code} {r.text}"
            bank_id = r.json().get("bank_id")
            created_bank_ids.append(bank_id)
            assert r.json().get("procesador") == proc_name, "procesador no persistió"

        # Datos base para la transición a proyecto
        await db.users.insert_one({
            "user_id": uid, "email": f"{uid}@testproc.local",
            "first_name": "Ana", "last_name": "Vendedora", "role": "user", "sede": "PYME",
        })
        await db.clients.insert_one({
            "client_id": client_id, "legal_name": "Cliente Proc C.A.",
            "fantasy_name": "ProcCli", "rif": "J-99999999-9", "sucursal": "Principal",
        })

        # 3) Escenario COMPUESTO (Procesador → Banco)
        q1 = TAG + "quo_" + uuid.uuid4().hex[:8]
        quote_ids.append(q1)
        quote_comp = {
            "quote_id": q1, "quote_number": f"COT-{TAG}C", "client_id": client_id,
            "client_segment": "PYME", "quote_category": "implementation", "quote_type": "VPOS",
            "created_by_user_id": uid,
            "sponsored_implementation": True,
            "sponsoring_bank_id": bank_id, "sponsoring_bank_name": bank_name,
            "sponsoring_processor_id": proc_id, "sponsoring_processor_name": proc_name,
            "services": [], "hardware": [], "equipment_items": [], "total_usd": 100.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.quotes.insert_one(quote_comp)
        await _create_project_from_quote(quote_comp, q1, keep_quote_active=True)
        p1 = await db.projects.find_one({"quote_id": q1}, {"_id": 0})
        assert p1, "proyecto compuesto no creado"
        project_ids.append(p1.get("project_id"))
        expected = f"{proc_name} — {bank_name}"
        assert p1.get("patrocinador_label") == expected, f"label compuesto: {p1.get('patrocinador_label')!r} != {expected!r}"
        assert p1.get("sponsoring_processor_id") == proc_id
        assert p1.get("sponsoring_processor_name") == proc_name

        # 4) Escenario DIRECTO (solo Banco, sin procesador)
        q2 = TAG + "quo_" + uuid.uuid4().hex[:8]
        quote_ids.append(q2)
        quote_dir = {
            "quote_id": q2, "quote_number": f"COT-{TAG}D", "client_id": client_id,
            "client_segment": "PYME", "quote_category": "implementation", "quote_type": "VPOS",
            "created_by_user_id": uid,
            "sponsored_implementation": True,
            "sponsoring_bank_id": bank_id, "sponsoring_bank_name": bank_name,
            "sponsoring_processor_id": None, "sponsoring_processor_name": None,
            "services": [], "hardware": [], "equipment_items": [], "total_usd": 100.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.quotes.insert_one(quote_dir)
        await _create_project_from_quote(quote_dir, q2, keep_quote_active=True)
        p2 = await db.projects.find_one({"quote_id": q2}, {"_id": 0})
        assert p2, "proyecto directo no creado"
        project_ids.append(p2.get("project_id"))
        assert p2.get("patrocinador_label") == bank_name, f"label directo: {p2.get('patrocinador_label')!r}"

        print("PASS: Procesador + patrocinio relacional (compuesto y directo) correcto.")
    finally:
        for pid in project_ids:
            if pid:
                await db.projects.delete_many({"project_id": pid})
        await db.projects.delete_many({"quote_id": {"$in": quote_ids}})
        await db.quotes.delete_many({"quote_id": {"$in": quote_ids}})
        await db.banks.delete_many({"bank_id": {"$in": [b for b in created_bank_ids if b]}})
        await db.clients.delete_many({"client_id": client_id})
        await db.users.delete_many({"user_id": uid})
        await db.user_sessions.delete_many({"session_token": admin_tok})
        await db.ws_outbox.delete_many({"user_id": uid})
        c.close()


def test_processor_sponsorship_flow():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
