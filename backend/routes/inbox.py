"""Centro de Mensajes — Bandeja Interna.

Endpoints user-facing (NO admin-only) que permiten a cada usuario consultar
sus mensajes, marcarlos como leídos y eliminarlos (soft-delete).

- GET    /api/inbox/me          → lista de mensajes activos del usuario.
- GET    /api/inbox/me/summary  → contadores (unread, total, by_sla).
- PATCH  /api/inbox/{id}/read   → marca como leído (idempotente).
- DELETE /api/inbox/{id}        → soft-delete del mensaje.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from config import db, get_current_user

router = APIRouter(tags=["inbox"])
logger = logging.getLogger("inbox")


def _sla_color(created_at_iso: str) -> str:
    """Devuelve `green` | `yellow` | `red` según antigüedad del mensaje.

    - ≤24h → green
    - 24-48h → yellow
    - >48h → red

    El cálculo se hace siempre en backend para que el cliente no dependa
    de su reloj local. Si la fecha no es parseable, devuelve `green`
    (conservador para no estresar al usuario).
    """
    try:
        # `fromisoformat` acepta ISO con `+00:00` o naive.
        dt = datetime.fromisoformat(created_at_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return "green"
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    if age_hours <= 24:
        return "green"
    if age_hours <= 48:
        return "yellow"
    return "red"


@router.get("/inbox/me")
async def list_my_inbox(
    limit: int = Query(50, ge=1, le=200),
    include_read: bool = Query(True),
    authorization: Optional[str] = Header(None),
):
    """Lista los mensajes activos (no eliminados) del usuario autenticado.

    Ordenado por `created_at` descendente. Incluye el flag `sla_color`
    calculado en backend.
    """
    user = await get_current_user(authorization)
    user_id = user.get("user_id")
    query: dict = {"user_id": user_id, "deleted_at": None}
    if not include_read:
        query["read_at"] = None

    cur = db.inbox_messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = []
    async for m in cur:
        m["sla_color"] = _sla_color(m.get("created_at", ""))
        items.append(m)
    return {"items": items, "total": len(items), "user_id": user_id}


@router.get("/inbox/me/summary")
async def inbox_summary(authorization: Optional[str] = Header(None)):
    """Contadores rápidos para badges de menú: total, no leídos y por SLA."""
    user = await get_current_user(authorization)
    user_id = user.get("user_id")
    base = {"user_id": user_id, "deleted_at": None}
    total = await db.inbox_messages.count_documents(base)
    unread = await db.inbox_messages.count_documents({**base, "read_at": None})

    # Conteo por SLA — barrido en memoria sobre los activos (rangos manejables).
    cur = db.inbox_messages.find(base, {"_id": 0, "created_at": 1})
    counts = {"green": 0, "yellow": 0, "red": 0}
    async for m in cur:
        counts[_sla_color(m.get("created_at", ""))] += 1
    return {"total": total, "unread": unread, "by_sla": counts}


@router.patch("/inbox/{message_id}/read")
async def mark_read(message_id: str, authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    res = await db.inbox_messages.update_one(
        {"message_id": message_id, "user_id": user["user_id"], "deleted_at": None, "read_at": None},
        {"$set": {"read_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        # Idempotente: si ya estaba leído o no existe, no fallamos
        exists = await db.inbox_messages.find_one(
            {"message_id": message_id, "user_id": user["user_id"]}, {"_id": 0, "read_at": 1}
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")
        return {"status": "already_read", "message_id": message_id}
    return {"status": "ok", "message_id": message_id}


@router.delete("/inbox/{message_id}")
async def delete_message(message_id: str, authorization: Optional[str] = Header(None)):
    """Soft-delete del mensaje: se preserva en DB para auditoría pero deja
    de aparecer en la bandeja del usuario."""
    user = await get_current_user(authorization)
    res = await db.inbox_messages.update_one(
        {"message_id": message_id, "user_id": user["user_id"], "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado o ya eliminado")
    return {"status": "deleted", "message_id": message_id}
