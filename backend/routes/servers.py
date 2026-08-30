"""Catálogo maestro de Servidores.

Campos:
  - server_id: str
  - tipo: Monocomercio | Multicomercio
  - descripcion: str (máx. 50 caracteres)
  - created_at: ISO
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import db, get_current_user

router = APIRouter(tags=["servers"])

SERVER_TIPOS = ["Monocomercio", "Multicomercio"]


class ServerCreate(BaseModel):
    tipo: str
    descripcion: str = ""


def _validate(payload: ServerCreate):
    tipo = (payload.tipo or "").strip()
    desc = (payload.descripcion or "").strip()
    if tipo not in SERVER_TIPOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Opciones: {', '.join(SERVER_TIPOS)}")
    if len(desc) > 50:
        raise HTTPException(status_code=400, detail="La descripción no puede superar los 50 caracteres")
    return tipo, desc


@router.get("/servers")
async def list_servers(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    return await db.servers.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/servers")
async def create_server(payload: ServerCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    tipo, desc = _validate(payload)
    existing = await db.servers.find_one(
        {"tipo": tipo, "descripcion": {"$regex": f"^{re.escape(desc)}$", "$options": "i"}}, {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un servidor con ese tipo y descripción")
    doc = {
        "server_id": f"srv_{uuid.uuid4().hex[:8]}",
        "tipo": tipo,
        "descripcion": desc,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.servers.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/servers/{server_id}")
async def update_server(server_id: str, payload: ServerCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    tipo, desc = _validate(payload)
    res = await db.servers.update_one({"server_id": server_id}, {"$set": {"tipo": tipo, "descripcion": desc}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")
    return await db.servers.find_one({"server_id": server_id}, {"_id": 0})


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str, authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    if (user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo el Administrador puede eliminar del catálogo")
    res = await db.servers.delete_one({"server_id": server_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")
    return {"message": "Servidor eliminado"}
