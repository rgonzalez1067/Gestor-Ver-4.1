"""
Reglas de Visibilidad de la bandeja de Proyectos (Parte 4) — gobernanza P0.

Valida GET /api/projects según rol/área:
  - Ejecutivo Ventas Pyme  → proyectos generados por el ÁREA Pyme (creador en dept 'Ventas Pyme').
  - Ejecutivo Ventas Corp  → propios (created_by) + sede CORP (client_segment).
  - Implementador          → solo proyectos donde es el Implementador Asignado.
  - Coordinador/Gerente de Implementación → todos.
  - Admin / otros          → todos.

Registros temporales con prefijo TESTVIS_, limpiados por ID al final.
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
TAG = "TESTVIS_"


def _u(cargo, dept, sede="PYME"):
    uid = TAG + uuid.uuid4().hex[:8]
    return {
        "user_id": uid, "email": f"{uid}@testvis.local",
        "first_name": "Vis", "last_name": cargo, "role": "user",
        "cargo": cargo, "departamento": dept, "sede": sede, "is_active": True,
        "permissions": {"proyectos": "read"},
    }


def _sess(uid):
    return {"session_token": TAG + secrets.token_hex(16), "user_id": uid,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}


def _p(created_by, segment, assigned_to=None):
    pid = TAG + uuid.uuid4().hex[:8]
    return {
        "project_id": pid, "project_number": pid, "client_name": "C",
        "client_segment": segment, "status": "Pendiente por Asignar",
        "created_by_user_id": created_by, "assigned_to_user_id": assigned_to,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def _ids(client, token, my_ids):
    r = await client.get(f"{BASE}/projects", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return {p["project_id"] for p in r.json() if p["project_id"] in my_ids}


async def run():
    c = AsyncIOMotorClient(MONGO_URL); db = c[DB_NAME]

    pyme1 = _u("Ejecutivo", "Ventas Pyme", "PYME")
    pyme2 = _u("Ejecutivo", "Ventas Pyme", "PYME")
    corp = _u("Ejecutivo", "Ventas Corporativas", "CORP")
    impl = _u("Implementador", "Implementación", "PYME")
    coord = _u("Coordinador", "Implementación", "PYME")
    other = _u("Ejecutivo", "Ventas Corporativas", "CORP")  # creador ajeno

    users = [pyme1, pyme2, corp, impl, coord, other]
    sessions = {u["user_id"]: _sess(u["user_id"]) for u in users}

    # Proyectos
    proj_pyme1 = _p(pyme1["user_id"], "PYME", assigned_to=impl["user_id"])
    proj_pyme2 = _p(pyme2["user_id"], "PYME")
    proj_corp_self = _p(corp["user_id"], "CORP")
    proj_corp_other = _p(other["user_id"], "CORP")
    proj_pyme_byother = _p(other["user_id"], "PYME")  # PYME creado por corp-other
    proj_assigned_impl = _p(other["user_id"], "CORP", assigned_to=impl["user_id"])
    projects = [proj_pyme1, proj_pyme2, proj_corp_self, proj_corp_other, proj_pyme_byother, proj_assigned_impl]
    my_ids = {p["project_id"] for p in projects}

    try:
        await db.users.insert_many(users)
        await db.user_sessions.insert_many(list(sessions.values()))
        await db.projects.insert_many(projects)

        async with httpx.AsyncClient(timeout=30) as client:
            # Ejecutivo Pyme → proyectos creados por dept Ventas Pyme (pyme1 + pyme2)
            seen = await _ids(client, sessions[pyme1["user_id"]]["session_token"], my_ids)
            assert seen == {proj_pyme1["project_id"], proj_pyme2["project_id"]}, f"Pyme exec ve: {seen}"

            # Ejecutivo Corp → propios + sede CORP (corp_self, corp_other, assigned_impl es CORP)
            seen = await _ids(client, sessions[corp["user_id"]]["session_token"], my_ids)
            expected_corp = {proj_corp_self["project_id"], proj_corp_other["project_id"], proj_assigned_impl["project_id"]}
            assert seen == expected_corp, f"Corp exec ve: {seen} != {expected_corp}"

            # Implementador → solo asignados a él (proj_pyme1, proj_assigned_impl)
            seen = await _ids(client, sessions[impl["user_id"]]["session_token"], my_ids)
            assert seen == {proj_pyme1["project_id"], proj_assigned_impl["project_id"]}, f"Implementador ve: {seen}"

            # Coordinador de Implementación → todos los de prueba
            seen = await _ids(client, sessions[coord["user_id"]]["session_token"], my_ids)
            assert seen == my_ids, f"Coordinador Impl debe ver todos: faltan {my_ids - seen}"

        print("PASS: Reglas de visibilidad de Proyectos (Pyme/Corp/Implementador/Coordinador) correctas.")
    finally:
        await db.projects.delete_many({"project_id": {"$in": list(my_ids)}})
        await db.user_sessions.delete_many({"session_token": {"$in": [s["session_token"] for s in sessions.values()]}})
        await db.users.delete_many({"user_id": {"$in": [u["user_id"] for u in users]}})
        c.close()


def test_project_visibility_rules():
    asyncio.run(run())


if __name__ == "__main__":
    asyncio.run(run())
