"""Notification service — core logic for push notifications (WebSocket + DB + config).

Design:
- 16 event types (NOTIFICATION_EVENTS) — see /app/memory/PRD.md.
- `NotificationConfig` collection stores admin-toggled events + priority.
- `notifications` collection stores one doc per (user_id, event) instance.
- `ConnectionManager` maintains per-user WebSocket connections.
- `notify()` resolves recipients, persists, and pushes to connected sockets.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket

from config import db

logger = logging.getLogger(__name__)


# ==================== Event Catalog (16 eventos del Excel) ====================

NOTIFICATION_EVENTS: Dict[str, Dict[str, Any]] = {
    "quote_sent_to_client": {
        "label": "Cotización enviada al cliente",
        "default_priority": "low",
        "recipient_roles": ["creator", "creator_supervisor"],
        "category": "Cotizaciones",
    },
    "quote_approved": {
        "label": "Cotización aprobada (por cliente)",
        "default_priority": "high",
        "recipient_roles": ["admin_by_sede"],
        "category": "Cotizaciones",
    },
    "quote_invoiced": {
        "label": "Cotización facturada",
        "default_priority": "medium",
        "recipient_roles": ["creator"],
        "category": "Cotizaciones",
    },
    "quote_collected": {
        "label": "Cotización pagada/cobrada",
        "default_priority": "medium",
        "recipient_roles": ["creator", "creator_supervisor"],
        "category": "Cotizaciones",
    },
    "quote_delivered": {
        "label": "Cotización entregada",
        "default_priority": "medium",
        "recipient_roles": ["creator"],
        "category": "Cotizaciones",
    },
    "project_created": {
        "label": "Proyecto creado desde cotización",
        "default_priority": "high",
        "recipient_roles": ["implementation_manager"],
        "category": "Proyectos",
    },
    "project_assigned_to_me": {
        "label": "Proyecto asignado a mí",
        "default_priority": "high",
        "recipient_roles": ["assignee"],
        "category": "Proyectos",
    },
    "bank_notified_in_project": {
        "label": "Banco notificado en proyecto",
        "default_priority": "medium",
        "recipient_roles": ["assignee"],
        "category": "Proyectos",
    },
    "matrix_phase_completed": {
        "label": "Fase de matriz completada",
        "default_priority": "low",
        "recipient_roles": ["implementation_manager"],
        "category": "Proyectos",
    },
    "quote_repair_finalized": {
        "label": "Cotización reparada finalizada",
        "default_priority": "medium",
        "recipient_roles": ["admin_by_sede"],
        "category": "Reparaciones",
    },
    "quote_marked_irregular": {
        "label": "Cotización marcada irregular",
        "default_priority": "high",
        "recipient_roles": ["admin_by_sede"],
        "category": "Auditoría",
    },
    "taller_equipo_over_15_days": {
        "label": "Equipo en taller > 15 días",
        "default_priority": "high",
        "recipient_roles": ["almacen"],
        "category": "Taller",
        "scheduled": True,
    },
    "new_product_phase_changed": {
        "label": "Nuevo Producto cambió de fase",
        "default_priority": "low",
        "recipient_roles": ["sales_and_directors"],
        "category": "Nuevos Productos",
    },
    "project_assigned_not_started": {
        "label": "Proyecto asignado sin iniciar",
        "default_priority": "high",
        "recipient_roles": ["implementation_manager"],
        "category": "Proyectos",
        "scheduled": True,
    },
    "project_stalled_5_days": {
        "label": "Proyecto iniciado sin avance en 5 días",
        "default_priority": "high",
        "recipient_roles": ["implementation_manager"],
        "category": "Proyectos",
        "scheduled": True,
    },
    "initial_contact_created": {
        "label": "Clientes referidos / Contacto inicial registrado",
        "default_priority": "high",
        "recipient_roles": ["sales_by_sede"],
        "category": "Contactos",
    },
    "implementer_alert_due": {
        "label": "Mi Alerta del Implementador — vence/vencida",
        "default_priority": "medium",
        "recipient_roles": ["assignee"],
        "category": "Proyectos",
        "scheduled": True,
    },
}

PRIORITIES = {"high", "medium", "low"}


# ==================== Connection Manager (WebSocket) ====================

class ConnectionManager:
    """Mantiene un mapa user_id -> set de WebSockets conectados (soporta múltiples tabs)."""

    def __init__(self):
        self._active: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._active.setdefault(user_id, set()).add(websocket)
        logger.info(f"[WS] Connected user={user_id} total={self._count()}")

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._active.get(user_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    self._active.pop(user_id, None)
        logger.info(f"[WS] Disconnected user={user_id} total={self._count()}")

    def _count(self) -> int:
        return sum(len(v) for v in self._active.values())

    def local_user_ids(self) -> List[str]:
        """user_ids con al menos una conexión WS viva EN ESTE proceso."""
        return list(self._active.keys())

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        """Encola el mensaje en el backplane de Mongo (`ws_outbox`).

        En producción el backend corre con múltiples workers/réplicas y el
        registro de conexiones (`_active`) es local a cada proceso. Si el
        destinatario está conectado a OTRO proceso, una entrega directa en
        memoria nunca le llegaría. Por eso TODA entrega se publica en Mongo y
        el `_ws_dispatch_loop` de cada worker reparte a sus usuarios locales.
        """
        try:
            await db.ws_outbox.insert_one({
                "user_id": user_id,
                "payload": payload,
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WS] no se pudo encolar ws_outbox user={user_id}: {e}")

    async def deliver_local(self, user_id: str, payload: dict) -> None:
        """Entrega a todas las conexiones vivas del usuario EN ESTE proceso.
        Silenciosamente limpia conexiones muertas."""
        conns = list(self._active.get(user_id, set()))
        if not conns:
            return
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception as e:
                logger.warning(f"[WS] send failed user={user_id}: {e}")
                dead.append(ws)
        if dead:
            async with self._lock:
                conns_set = self._active.get(user_id)
                if conns_set:
                    for d in dead:
                        conns_set.discard(d)
                    if not conns_set:
                        self._active.pop(user_id, None)


manager = ConnectionManager()


# ==================== WebSocket Backplane (Mongo fan-out) ====================
# Cada worker corre este loop: consulta `ws_outbox` por mensajes dirigidos a
# usuarios conectados localmente, los reclama atómicamente (find_one_and_delete)
# y los entrega. Esto garantiza la entrega en tiempo real sin importar a qué
# réplica esté conectado el destinatario (Mongo es el bus compartido).

WS_DISPATCH_INTERVAL = 1.0  # segundos — casi instantáneo
_ws_dispatch_task: Optional["asyncio.Task"] = None
_ws_dispatch_stop = False


async def _ws_dispatch_loop() -> None:
    # Índice TTL para auto-limpiar mensajes no entregados (usuario offline).
    try:
        await db.ws_outbox.create_index("created_at", expireAfterSeconds=120)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[WS] no se pudo crear índice TTL ws_outbox: {e}")

    logger.info("[WS] dispatcher backplane iniciado")
    while not _ws_dispatch_stop:
        try:
            uids = manager.local_user_ids()
            if uids:
                while True:
                    doc = await db.ws_outbox.find_one_and_delete(
                        {"user_id": {"$in": uids}},
                        sort=[("created_at", 1)],
                    )
                    if not doc:
                        break
                    await manager.deliver_local(doc["user_id"], doc.get("payload") or {})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[WS] dispatch loop error: {e}")
        await asyncio.sleep(WS_DISPATCH_INTERVAL)
    logger.info("[WS] dispatcher backplane detenido")


def start_ws_dispatcher() -> None:
    global _ws_dispatch_task, _ws_dispatch_stop
    _ws_dispatch_stop = False
    if _ws_dispatch_task is None or _ws_dispatch_task.done():
        _ws_dispatch_task = asyncio.create_task(_ws_dispatch_loop())


def stop_ws_dispatcher() -> None:
    global _ws_dispatch_stop
    _ws_dispatch_stop = True
    if _ws_dispatch_task is not None:
        _ws_dispatch_task.cancel()


# ==================== Config helpers ====================

async def get_event_config(event_type: str) -> Dict[str, Any]:
    """Lee config del evento de BD; si no existe, retorna defaults del catálogo."""
    doc = await db.notification_config.find_one({"event_type": event_type}, {"_id": 0})
    defaults = NOTIFICATION_EVENTS.get(event_type, {})
    if not doc:
        return {
            "event_type": event_type,
            "label": defaults.get("label", event_type),
            "category": defaults.get("category", "General"),
            "is_active": True,
            "priority": defaults.get("default_priority", "medium"),
            "scheduled": defaults.get("scheduled", False),
        }
    return {
        "event_type": event_type,
        "label": defaults.get("label", doc.get("label", event_type)),
        "category": defaults.get("category", doc.get("category", "General")),
        "is_active": doc.get("is_active", True),
        "priority": doc.get("priority", defaults.get("default_priority", "medium")),
        "scheduled": defaults.get("scheduled", False),
    }


# ==================== Recipient Resolution ====================

async def _resolve_recipients(event_type: str, context: Dict[str, Any]) -> List[str]:
    """Retorna lista única de user_ids que deben recibir la notificación.

    Context keys esperados (opcionales según evento):
      - creator_user_id
      - assignee_user_id
      - sede (Pyme/TBP/CORP)
    Admins (role='admin') SIEMPRE reciben todas las notificaciones activas.
    """
    roles = NOTIFICATION_EVENTS.get(event_type, {}).get("recipient_roles", [])
    user_ids: Set[str] = set()

    sede = context.get("sede") or context.get("quote_sede") or context.get("project_sede")
    creator_id = context.get("creator_user_id")
    assignee_id = context.get("assignee_user_id")

    for role in roles:
        if role == "creator" and creator_id:
            user_ids.add(creator_id)

        elif role == "creator_supervisor" and creator_id:
            creator = await db.users.find_one(
                {"user_id": creator_id, "is_active": True},
                {"_id": 0, "supervisor_id": 1},
            )
            if creator and creator.get("supervisor_id"):
                user_ids.add(creator["supervisor_id"])

        elif role == "assignee" and assignee_id:
            user_ids.add(assignee_id)

        elif role == "admin_by_sede":
            q = {"departamento": "Administración", "is_active": True}
            if sede:
                q["sede"] = sede
            async for u in db.users.find(q, {"_id": 0, "user_id": 1}):
                user_ids.add(u["user_id"])

        elif role == "implementation_manager":
            # Gerente con cargo/dept que contengan Gerente/Implementación
            async for u in db.users.find(
                {
                    "is_active": True,
                    "$or": [
                        {"departamento": "Implementación", "cargo": {"$regex": "erente|efe|irector", "$options": "i"}},
                        {"cargo": {"$regex": "erente.*mplementaci|mplementaci.*erente", "$options": "i"}},
                    ],
                },
                {"_id": 0, "user_id": 1},
            ):
                user_ids.add(u["user_id"])

        elif role == "almacen":
            async for u in db.users.find(
                {
                    "is_active": True,
                    "$or": [
                        {"departamento": {"$regex": "lmac", "$options": "i"}},
                        {"role": "almacen"},
                        {"cargo": {"$regex": "lmac", "$options": "i"}},
                    ],
                },
                {"_id": 0, "user_id": 1},
            ):
                user_ids.add(u["user_id"])

        elif role == "sales_by_sede":
            q = {"is_active": True, "departamento": {"$regex": "entas", "$options": "i"}}
            if sede:
                q["sede"] = sede
            async for u in db.users.find(q, {"_id": 0, "user_id": 1}):
                user_ids.add(u["user_id"])

        elif role == "sales_and_directors":
            async for u in db.users.find(
                {
                    "is_active": True,
                    "$or": [
                        {"departamento": {"$regex": "entas|irecci", "$options": "i"}},
                        {"role": "director"},
                        {"cargo": {"$regex": "irector", "$options": "i"}},
                    ],
                },
                {"_id": 0, "user_id": 1},
            ):
                user_ids.add(u["user_id"])

    # Todas las notificaciones activas también van a admins (requisito explícito)
    async for u in db.users.find({"role": "admin", "is_active": True}, {"_id": 0, "user_id": 1}):
        user_ids.add(u["user_id"])

    return list(user_ids)


# ==================== Main API ====================

async def notify(
    event_type: str,
    title: str,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    link: Optional[str] = None,
    quote_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> int:
    """Dispara una notificación.

    1. Valida que el evento esté en catálogo.
    2. Lee config (activo + prioridad).
    3. Resuelve destinatarios.
    4. Inserta N docs (uno por usuario) en `notifications`.
    5. Empuja via WebSocket a los que estén online.

    Returns: cantidad de usuarios notificados.
    """
    if event_type not in NOTIFICATION_EVENTS:
        logger.warning(f"[notify] Evento desconocido: {event_type}")
        return 0

    cfg = await get_event_config(event_type)
    if not cfg.get("is_active", True):
        logger.info(f"[notify] Evento {event_type} está desactivado — se omite")
        return 0

    ctx = context or {}
    recipients = await _resolve_recipients(event_type, ctx)
    if not recipients:
        logger.info(f"[notify] Sin destinatarios para {event_type}")
        return 0

    now = datetime.now(timezone.utc)
    docs = []
    for uid in recipients:
        docs.append({
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": uid,
            "event_type": event_type,
            "event_label": cfg["label"],
            "category": cfg["category"],
            "priority": cfg["priority"],
            "title": title,
            "message": message,
            "link": link,
            "quote_id": quote_id,
            "project_id": project_id,
            "is_read": False,
            "created_at": now.isoformat(),
            "read_at": None,
        })

    if docs:
        await db.notifications.insert_many(docs)

    # Broadcast a conexiones vivas
    for d in docs:
        d_copy = {k: v for k, v in d.items() if k != "_id"}
        await manager.send_to_user(d["user_id"], {
            "type": "notification",
            "payload": d_copy,
        })

    logger.info(f"[notify] {event_type} → {len(docs)} usuario(s) · priority={cfg['priority']}")
    return len(docs)


def notify_sync_safe(*args, **kwargs) -> None:
    """Dispara notify() sin bloquear si la corutina falla.
    Útil cuando no queremos que una falla de notificación rompa el flujo principal."""
    try:
        asyncio.create_task(notify(*args, **kwargs))
    except Exception as e:
        logger.warning(f"[notify_sync_safe] fallo: {e}")
