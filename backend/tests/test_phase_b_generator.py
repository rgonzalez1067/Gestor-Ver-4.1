"""
Proyectos — Registro del "Generador" (creador) — Fase B (P0).

Valida que `_create_project_from_quote` persiste `created_by_name` y
`created_by_user_id` resolviendo el nombre del usuario que originó la
cotización (cuando la cotización no trae el nombre cacheado).

Crea registros temporales con prefijo TESTGEN_ y los elimina por ID al final.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
TAG = "TESTGEN_"


async def run():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    # Inyectar la conexión correcta en el módulo (usa config.db)
    from routes.quote_transitions import _create_project_from_quote

    uid = TAG + uuid.uuid4().hex[:8]
    user = {
        "user_id": uid,
        "email": f"{uid}@testgen.local",
        "first_name": "Carlos",
        "last_name": "Generador",
        "role": "user",
        "sede": "PYME",
        "is_active": True,
    }
    client_id = TAG + "cli_" + uuid.uuid4().hex[:8]
    client = {
        "client_id": client_id,
        "legal_name": "Cliente Generador C.A.",
        "fantasy_name": "GenTest",
        "rif": "J-12345678-9",
        "sucursal": "Principal",
    }
    quote_id = TAG + "quo_" + uuid.uuid4().hex[:8]
    quote = {
        "quote_id": quote_id,
        "quote_number": f"COT-TESTGEN-{uuid.uuid4().hex[:4]}",
        "client_id": client_id,
        "client_segment": "PYME",
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "created_by_user_id": uid,
        # Sin created_by_name → fuerza la resolución vía lookup de usuarios.
        "services": [],
        "hardware": [],
        "equipment_items": [],
        "total_usd": 100.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    project_id = None
    try:
        await db.users.insert_one(user)
        await db.clients.insert_one(client)
        await db.quotes.insert_one(quote)

        await _create_project_from_quote(quote, quote_id, keep_quote_active=True)

        proj = await db.projects.find_one({"quote_id": quote_id}, {"_id": 0})
        assert proj is not None, "El proyecto no se creó"
        project_id = proj.get("project_id")
        assert proj.get("created_by_user_id") == uid, f"created_by_user_id incorrecto: {proj.get('created_by_user_id')}"
        assert proj.get("created_by_name") == "Carlos Generador", (
            f"created_by_name no resuelto: {proj.get('created_by_name')!r}"
        )
        print("PASS: Generador (created_by_name) resuelto y persistido en el proyecto nuevo.")
    finally:
        if project_id:
            await db.projects.delete_many({"project_id": project_id})
        await db.projects.delete_many({"quote_id": quote_id})
        await db.quotes.delete_many({"quote_id": quote_id})
        await db.clients.delete_many({"client_id": client_id})
        await db.users.delete_many({"user_id": uid})
        await db.ws_outbox.delete_many({"user_id": uid})
        c.close()


def test_project_generator_persisted():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
