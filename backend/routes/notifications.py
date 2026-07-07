"""Routes: /api/notifications/* + WebSocket /ws/notifications/{user_id}"""
from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging

from config import db, get_current_user
from services.notification_service import (
    NOTIFICATION_EVENTS, PRIORITIES, manager, get_event_config,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== REST: Notifications feed ====================

@router.get("/notifications/recent-activity")
async def recent_activity(
    limit: int = Query(10, ge=1, le=30),
    authorization: Optional[str] = Header(None),
):
    """Feed global empresa-wide de las últimas notificaciones. Solo admin o director.

    Deduplica por (event_type, quote_id|project_id) para evitar mostrar múltiples copias
    de un mismo evento dirigido a varios usuarios.
    """
    user = await get_current_user(authorization)
    role = user.get("role")
    cargo = (user.get("cargo") or "").lower()
    if role != "admin" and role != "director" and "director" not in cargo:
        raise HTTPException(403, "Solo administradores o directores")

    # Traer más para poder deduplicar y aun así devolver `limit`
    cursor = db.notifications.find({}, {"_id": 0}).sort("created_at", -1).limit(limit * 5)
    seen = set()
    items = []
    async for n in cursor:
        # Dedup: misma notify() genera 1 doc por destinatario, agrupamos por
        # (event_type, quote/project, timestamp redondeado al segundo).
        ts = (n.get("created_at") or "")[:19]  # YYYY-MM-DDTHH:MM:SS
        key = (
            n.get("event_type"),
            n.get("quote_id") or n.get("project_id") or n.get("title", ""),
            ts,
        )
        if key in seen:
            continue
        seen.add(key)
        n.pop("user_id", None)
        n.pop("read_at", None)
        n.pop("is_read", None)
        items.append(n)
        if len(items) >= limit:
            break

    return {"items": items, "count": len(items)}


@router.get("/notifications")
async def list_my_notifications(
    limit: int = Query(50, ge=1, le=200),
    only_unread: bool = False,
    authorization: Optional[str] = Header(None),
):
    """Notificaciones del usuario autenticado (más recientes primero)."""
    user = await get_current_user(authorization)
    q = {"user_id": user["user_id"]}
    if only_unread:
        q["is_read"] = False
    cursor = db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [n async for n in cursor]
    unread = await db.notifications.count_documents({"user_id": user["user_id"], "is_read": False})
    return {"items": items, "unread_count": unread}


@router.get("/notifications/unread-count")
async def unread_count(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    count = await db.notifications.count_documents({"user_id": user["user_id"], "is_read": False})
    return {"count": count}


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"is_read": True, "read_at": now}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Notificación no encontrada")
    return {"message": "ok"}


@router.post("/notifications/mark-all-read")
async def mark_all_read(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.notifications.update_many(
        {"user_id": user["user_id"], "is_read": False},
        {"$set": {"is_read": True, "read_at": now}},
    )
    return {"message": "ok", "updated": res.modified_count}


# ==================== REST: Admin config ====================

class NotificationConfigPayload(BaseModel):
    is_active: Optional[bool] = None
    priority: Optional[str] = None


@router.get("/notifications/config")
async def get_all_config(authorization: Optional[str] = Header(None)):
    """Lista todos los eventos del catálogo con su config actual. Requerido para admin UI."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Solo administradores")
    items = []
    for event_type in NOTIFICATION_EVENTS.keys():
        items.append(await get_event_config(event_type))
    # Ordenar por category → label
    items.sort(key=lambda e: (e.get("category", ""), e.get("label", "")))
    return {"items": items, "priorities": ["high", "medium", "low"]}


@router.put("/notifications/config/{event_type}")
async def update_config(
    event_type: str,
    payload: NotificationConfigPayload,
    authorization: Optional[str] = Header(None),
):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(403, "Solo administradores")
    if event_type not in NOTIFICATION_EVENTS:
        raise HTTPException(404, "Evento desconocido")

    upd = {}
    if payload.is_active is not None:
        upd["is_active"] = bool(payload.is_active)
    if payload.priority is not None:
        if payload.priority not in PRIORITIES:
            raise HTTPException(400, f"Prioridad inválida, debe ser: {', '.join(PRIORITIES)}")
        upd["priority"] = payload.priority
    if not upd:
        return await get_event_config(event_type)

    upd["event_type"] = event_type
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    upd["updated_by"] = user.get("email", "")

    await db.notification_config.update_one(
        {"event_type": event_type},
        {"$set": upd},
        upsert=True,
    )
    return await get_event_config(event_type)


# ==================== WebSocket ====================

@router.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)):
    """WS persistente. Autentica con ?token=session_token. Cada mensaje del servidor es JSON."""
    # Validación básica: el token debe corresponder a un usuario activo con ese user_id
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0, "user_id": 1})
    if not session or session.get("user_id") != user_id:
        await websocket.close(code=4401, reason="invalid token")
        return
    user = await db.users.find_one({"user_id": user_id, "is_active": True}, {"_id": 0, "user_id": 1})
    if not user:
        await websocket.close(code=4401, reason="user not found")
        return

    await manager.connect(user_id, websocket)
    try:
        # Enviar un "hello" para que el cliente sepa que conectó
        await websocket.send_json({"type": "hello", "user_id": user_id})
        while True:
            # Mantener viva la conexión; cliente envía 'ping' cada ~30s (heartbeat)
            msg = await websocket.receive_text()
            if msg == "ping":
                manager.touch(websocket)
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[WS] error user={user_id}: {e}")
    finally:
        await manager.disconnect(user_id, websocket)
