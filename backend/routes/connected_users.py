"""Routes: /api/admin/connected-users — Iter57.

Endpoint admin-only que expone los usuarios con conexión WebSocket activa al
servidor (`ConnectionManager` del notification_service). El conteo se calcula
en tiempo real desde el manager en memoria, así que refleja el estado real
del proceso backend en este nodo de Kubernetes.

NOTA: el manager vive en memoria por proceso. Con múltiples réplicas (HPA),
este endpoint mostraría solo las conexiones del pod que lo atiende. Para
producción multinodo se requeriría un store compartido (Redis pub/sub), pero
hoy el deployment corre como single-replica.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from config import db, get_current_user
from services.notification_service import manager

router = APIRouter(tags=["admin"])
logger = logging.getLogger("connected_users")


@router.get("/admin/connected-users")
async def list_connected_users(authorization: Optional[str] = Header(None)):
    """Lista los usuarios con WebSocket activo en el servidor.

    Devuelve para cada usuario: identidad, departamento, nº de conexiones
    abiertas (multi-tab) y un timestamp aproximado de conexión.

    Acceso restringido a `role == 'admin'` o `is_admin == True`.
    """
    user = await get_current_user(authorization)
    if user.get("role") != "admin" and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Solo administradores")

    # Snapshot del estado interno del ConnectionManager
    active = dict(manager._active)  # noqa: SLF001 — acceso intencional al snapshot
    user_ids = list(active.keys())
    total_connections = sum(len(s) for s in active.values())

    if not user_ids:
        return {"items": [], "total_users": 0, "total_connections": 0}

    # Hidratar info de usuario en una sola query
    profiles_cur = db.users.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1,
         "department": 1, "departamento": 1, "role": 1, "picture": 1, "sede": 1},
    )
    profiles = {u["user_id"]: u async for u in profiles_cur}

    items = []
    for uid, sockets in active.items():
        p = profiles.get(uid, {})
        full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or p.get("email", uid)
        items.append({
            "user_id": uid,
            "full_name": full_name,
            "email": p.get("email", ""),
            "department": p.get("department") or p.get("departamento") or "",
            "role": p.get("role", ""),
            "sede": p.get("sede", ""),
            "picture": p.get("picture"),
            "connections": len(sockets),
        })
    items.sort(key=lambda r: r["full_name"].lower())
    return {
        "items": items,
        "total_users": len(items),
        "total_connections": total_connections,
    }


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin" and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Solo administradores")
    return user


# ==================== MENSAJES DIRECTOS (Broadcast / Multicast) ====================

@router.post("/admin/direct-message")
async def send_direct_message(body: dict, authorization: Optional[str] = Header(None)):
    """Envía un mensaje directo (push por WebSocket) a uno, varios o TODOS los
    usuarios conectados. Niveles: low (toast), medium (modal azul), high (modal rojo)."""
    user = await _require_admin(authorization)
    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    level = (body.get("level") or "medium").lower()
    if level not in ("low", "medium", "high"):
        level = "medium"

    all_online = bool(body.get("all_online"))
    recipient_ids = list(manager.local_user_ids()) if all_online else (body.get("recipient_ids") or [])
    recipient_ids = [r for r in dict.fromkeys(recipient_ids) if r]
    if not recipient_ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos un destinatario conectado")

    sender_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "Administrador")
    now = datetime.now(timezone.utc).isoformat()
    dm_id = f"dm_{uuid.uuid4().hex[:10]}"
    payload = {
        "type": "direct_message",
        "payload": {"id": dm_id, "level": level, "body": text, "from": sender_name, "created_at": now},
    }
    for uid in recipient_ids:
        await manager.send_to_user(uid, payload)

    await db.direct_messages.insert_one({
        "id": dm_id, "level": level, "body": text, "from": sender_name,
        "from_user_id": user.get("user_id"), "recipient_ids": recipient_ids,
        "all_online": all_online, "created_at": now,
    })
    return {"message": f"Mensaje enviado a {len(recipient_ids)} usuario(s) conectado(s)", "delivered": len(recipient_ids), "level": level}


# ==================== PLANTILLAS DE MENSAJES (Preelaborados) ====================

@router.get("/admin/message-templates")
async def list_message_templates(authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    tpls = await db.message_templates.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"items": tpls}


@router.post("/admin/message-templates")
async def create_message_template(body: dict, authorization: Optional[str] = Header(None)):
    user = await _require_admin(authorization)
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto de la plantilla no puede estar vacío")
    tpl = {
        "template_id": f"tpl_{uuid.uuid4().hex[:10]}",
        "title": (body.get("title") or text[:40]).strip(),
        "text": text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("email"),
    }
    await db.message_templates.insert_one(dict(tpl))
    return tpl


@router.delete("/admin/message-templates/{template_id}")
async def delete_message_template(template_id: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    await db.message_templates.delete_one({"template_id": template_id})
    return {"message": "Plantilla eliminada"}
