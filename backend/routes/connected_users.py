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
