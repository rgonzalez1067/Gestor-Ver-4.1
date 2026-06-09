"""Centro de Mensajes — Bandeja Interna.

Endpoints user-facing (NO admin-only) que permiten a cada usuario consultar
sus mensajes, marcarlos como leídos, eliminarlos (soft-delete), descargar
los adjuntos originales y **enviar mensajes a otros usuarios** (Iter46).

- GET    /api/inbox/me                              → lista de mensajes activos.
- GET    /api/inbox/me/summary                      → contadores.
- PATCH  /api/inbox/{id}/read                       → marca como leído.
- DELETE /api/inbox/{id}                            → soft-delete del mensaje.
- GET    /api/inbox/{id}/attachments/{idx}          → descarga del adjunto N.
- POST   /api/inbox/send                            → enviar mensaje a usuarios.
"""
import base64
import html as html_lib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from urllib.parse import quote

from config import db, get_current_user
from services.conversation_service import (
    append_message,
    conversation_for_user,
    find_or_create_conversation,
    mark_conversation_read,
)
from services.notification_service import manager


def _msg_preview(text: str, limit: int = 120) -> str:
    p = (text or "").strip().replace("\n", " ")
    return p[: limit - 1] + "…" if len(p) > limit else p


async def _push_internal_message(*, recipient_id: str, conversation_id: str, from_user_name: str, body: str, subject: str, created_at: str):
    """Empuja por WebSocket un aviso de mensaje interno al destinatario online."""
    try:
        await manager.send_to_user(recipient_id, {
            "type": "internal_message",
            "payload": {
                "conversation_id": conversation_id,
                "from_user_name": from_user_name,
                "preview": _msg_preview(body),
                "subject": subject or "",
                "created_at": created_at,
            },
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Inbox] No se pudo empujar internal_message a {recipient_id}: {e}")

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


def _remind_due(remind_at_iso: Optional[str]) -> bool:
    """True si el recordatorio (`remind_at`) ya venció (<= ahora)."""
    if not remind_at_iso:
        return False
    try:
        dt = datetime.fromisoformat(str(remind_at_iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return dt <= datetime.now(timezone.utc)


@router.get("/inbox/me")
async def list_my_inbox(
    limit: int = Query(50, ge=1, le=200),
    include_read: bool = Query(True),
    authorization: Optional[str] = Header(None),
):
    """Lista mezclada de bandeja: notificaciones del sistema + hilos de chat.

    Iter48: las conversaciones user-to-user se entregan como filas tipo
    `conversation` con su preview, el otro participante y el contador de
    no leídos del usuario actual. Las notificaciones del sistema mantienen
    el formato original (`type: "notification"`).

    Ordenado por timestamp descendente (`last_message_at` para hilos,
    `created_at` para notificaciones).
    """
    user = await get_current_user(authorization)
    user_id = user.get("user_id")

    items: list[dict] = []

    # ---- A) Notificaciones del sistema (NO incluye user-to-user legacy migrados) ----
    notif_query: dict = {
        "user_id": user_id,
        "deleted_at": None,
        "$or": [
            {"is_user_message": {"$ne": True}},
            {"migrated_to_conversation_id": {"$exists": False}, "is_user_message": True},
        ],
    }
    # Excluir explícitamente los migrados (que ya viven como conversaciones)
    notif_query = {
        "user_id": user_id,
        "deleted_at": None,
        "is_user_message": {"$ne": True},
    }
    if not include_read:
        notif_query["read_at"] = None

    cur = db.inbox_messages.find(notif_query, {"_id": 0}).sort("created_at", -1).limit(limit)
    async for m in cur:
        m["type"] = "notification"
        m["sla_color"] = _sla_color(m.get("created_at", ""))
        # Recuérdame (solo notificaciones del sistema): expone el vencimiento
        # configurado y un flag calculado en backend para la alerta visual.
        m["remind_at"] = m.get("remind_at")
        m["remind_due"] = _remind_due(m.get("remind_at"))
        slim_atts = []
        for a in (m.get("attachments_meta") or []):
            slim_atts.append({
                "filename": a.get("filename"),
                "size_bytes": a.get("size_bytes", 0),
                "mime_type": a.get("mime_type", "application/octet-stream"),
            })
        m["attachments_meta"] = slim_atts
        items.append(m)

    # ---- B) Conversaciones del usuario ----
    conv_cur = db.conversations.find(
        {"participants": user_id, "deleted_for": {"$ne": user_id}},
        {"_id": 0},
    ).sort("last_message_at", -1).limit(limit)
    async for conv in conv_cur:
        row = conversation_for_user(conv, user_id)
        row["sla_color"] = _sla_color(row.get("last_message_at", ""))
        # `created_at` se usa por el frontend como ancla temporal — apuntamos
        # al último mensaje para que el orden y el semáforo sean coherentes.
        row["created_at"] = row["last_message_at"]
        items.append(row)

    # Orden global por timestamp desc
    items.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    items = items[:limit]
    return {"items": items, "total": len(items), "user_id": user_id}


@router.get("/inbox/me/summary")
async def inbox_summary(authorization: Optional[str] = Header(None)):
    """Contadores para badges: notificaciones + conversaciones."""
    user = await get_current_user(authorization)
    user_id = user.get("user_id")
    # Notificaciones del sistema
    base = {"user_id": user_id, "deleted_at": None, "is_user_message": {"$ne": True}}
    notif_total = await db.inbox_messages.count_documents(base)
    notif_unread = await db.inbox_messages.count_documents({**base, "read_at": None})

    # Conversaciones activas del usuario
    conv_total = await db.conversations.count_documents(
        {"participants": user_id, "deleted_for": {"$ne": user_id}}
    )
    # Hilos con al menos un mensaje sin leer
    conv_unread = await db.conversations.count_documents(
        {
            "participants": user_id,
            "deleted_for": {"$ne": user_id},
            f"unread_for.{user_id}": {"$gt": 0},
        }
    )

    # SLA combinado: por mensajes de notificación + último mensaje de cada hilo
    cur = db.inbox_messages.find(base, {"_id": 0, "created_at": 1})
    counts = {"green": 0, "yellow": 0, "red": 0}
    async for m in cur:
        counts[_sla_color(m.get("created_at", ""))] += 1
    conv_cur = db.conversations.find(
        {"participants": user_id, "deleted_for": {"$ne": user_id}},
        {"_id": 0, "last_message_at": 1},
    )
    async for c in conv_cur:
        counts[_sla_color(c.get("last_message_at", ""))] += 1

    return {
        "total": notif_total + conv_total,
        "unread": notif_unread + conv_unread,
        "by_sla": counts,
    }


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


class RemindPayload(BaseModel):
    # ISO datetime (UTC). El frontend convierte el datetime-local a UTC con
    # `new Date(value).toISOString()`. `None` limpia el recordatorio.
    remind_at: Optional[str] = None


@router.patch("/inbox/{message_id}/remind")
async def set_reminder(
    message_id: str,
    payload: RemindPayload,
    authorization: Optional[str] = Header(None),
):
    """Función "Recuérdame" — SOLO para notificaciones del sistema.

    Configura (o limpia) el `remind_at` de un mensaje del sistema. Al vencer,
    el scheduler dispara una alerta visual en vivo (WebSocket/toast) y el
    listado marca el mensaje como vencido (`remind_due=True`).
    """
    user = await get_current_user(authorization)
    msg = await db.inbox_messages.find_one(
        {"message_id": message_id, "user_id": user["user_id"], "deleted_at": None},
        {"_id": 0, "is_user_message": 1},
    )
    # Nota: usar `msg is None` (no `not msg`) porque la proyección puede
    # devolver `{}` cuando el campo `is_user_message` no está presente en
    # mensajes legacy del sistema. `{}` es falsy y causaría un 404 falso.
    if msg is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    if msg.get("is_user_message"):
        raise HTTPException(
            status_code=400,
            detail="Recuérdame solo aplica a notificaciones del sistema",
        )

    if not payload.remind_at:
        # Limpiar recordatorio
        await db.inbox_messages.update_one(
            {"message_id": message_id, "user_id": user["user_id"]},
            {"$set": {"remind_at": None, "remind_fired": False}},
        )
        return {"status": "cleared", "message_id": message_id, "remind_at": None}

    # Normalizar y validar la fecha
    try:
        dt = datetime.fromisoformat(str(payload.remind_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha/hora inválida")

    remind_iso = dt.astimezone(timezone.utc).isoformat()
    await db.inbox_messages.update_one(
        {"message_id": message_id, "user_id": user["user_id"]},
        # remind_fired=False re-arma la alerta si el usuario reprograma la fecha.
        {"$set": {"remind_at": remind_iso, "remind_fired": False}},
    )
    return {"status": "ok", "message_id": message_id, "remind_at": remind_iso}


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


class BatchDeleteRequest(BaseModel):
    message_ids: list[str] = Field(default_factory=list)


@router.post("/inbox/batch-delete")
async def batch_delete_messages(body: BatchDeleteRequest, authorization: Optional[str] = Header(None)):
    """Borrado masivo/selectivo (soft-delete) de mensajes del usuario.
    Solo afecta mensajes que pertenecen al usuario autenticado y que no estén ya
    eliminados; se preservan en DB para auditoría."""
    user = await get_current_user(authorization)
    ids = [m for m in (body.message_ids or []) if m]
    if not ids:
        raise HTTPException(status_code=400, detail="No se proporcionaron mensajes para eliminar")
    res = await db.inbox_messages.update_many(
        {"message_id": {"$in": ids}, "user_id": user["user_id"], "deleted_at": None},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"status": "deleted", "deleted_count": res.modified_count, "requested": len(ids)}



@router.get("/inbox/{message_id}/attachments/{index}")
async def download_attachment(
    message_id: str,
    index: int,
    authorization: Optional[str] = Header(None),
):
    """Descarga del adjunto en la posición `index` (0-based) del mensaje.

    Validaciones:
      - El mensaje debe pertenecer al usuario autenticado y no estar eliminado.
      - `index` debe ser válido para la lista `attachments_meta`.
      - El adjunto debe tener `content_b64` (mensajes legacy sin contenido
        almacenado devolverán 410 Gone).
    """
    user = await get_current_user(authorization)
    msg = await db.inbox_messages.find_one(
        {"message_id": message_id, "user_id": user["user_id"], "deleted_at": None},
        {"_id": 0, "attachments_meta": 1},
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    atts = msg.get("attachments_meta") or []
    if index < 0 or index >= len(atts):
        raise HTTPException(status_code=404, detail="Adjunto no encontrado")
    att = atts[index]
    b64 = att.get("content_b64")
    if not b64:
        raise HTTPException(
            status_code=410,
            detail="El contenido de este adjunto no está disponible (mensaje legacy)",
        )
    try:
        data = base64.b64decode(b64)
    except Exception as e:
        logger.error(f"[inbox] Decodificación base64 falló msg={message_id} idx={index}: {e}")
        raise HTTPException(status_code=500, detail="Adjunto corrupto")

    filename = att.get("filename") or f"adjunto-{index}"
    mime = att.get("mime_type") or "application/octet-stream"
    # RFC 5987: filename* permite caracteres no-ASCII (acentos en PDFs típicos).
    disposition = (
        f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": disposition},
    )


# ==================== Iter46: Mensajería interna entre usuarios ====================

class SendUserMessagePayload(BaseModel):
    recipient_user_ids: list[str] = Field(..., min_length=1, max_length=50)
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("/inbox/send")
async def send_user_message(
    payload: SendUserMessagePayload,
    authorization: Optional[str] = Header(None),
):
    """Envía un mensaje user-to-user (Iter48: chat continuo).

    Por cada destinatario:
      - Encuentra (o crea) la conversación 1:1 por par+asunto normalizado.
      - Anexa el nuevo mensaje al final del hilo.
      - Si el destinatario había soft-borrado el hilo, se reactiva.

    Múltiples destinatarios → un hilo independiente por cada par.
    """
    sender = await get_current_user(authorization)
    sender_id = sender["user_id"]
    sender_name = (
        f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip()
        or sender.get("email", "")
    )
    sender_email = sender.get("email", "")

    ids = list({uid for uid in payload.recipient_user_ids if uid and uid != sender_id})
    if not ids:
        raise HTTPException(status_code=400, detail="Sin destinatarios válidos")

    users_cur = db.users.find(
        {"user_id": {"$in": ids}, "is_active": True},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1},
    )
    recipients = [u async for u in users_cur]
    if not recipients:
        raise HTTPException(status_code=404, detail="Ningún destinatario válido")

    delivered = []
    for r in recipients:
        rname = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or r.get("email", "")
        conv = await find_or_create_conversation(
            sender_id=sender_id,
            sender_name=sender_name,
            sender_email=sender_email,
            recipient_id=r["user_id"],
            recipient_name=rname,
            recipient_email=r.get("email", ""),
            subject=payload.subject,
        )
        msg = await append_message(
            conversation=conv,
            from_user_id=sender_id,
            from_user_name=sender_name,
            body_plain=payload.body,
        )
        await _push_internal_message(
            recipient_id=r["user_id"],
            conversation_id=conv["conversation_id"],
            from_user_name=sender_name,
            body=payload.body,
            subject=payload.subject,
            created_at=msg["created_at"],
        )
        delivered.append({
            "user_id": r["user_id"],
            "conversation_id": conv["conversation_id"],
            "message_id": msg["message_id"],
        })

    logger.info(
        f"[Inbox] user_message from={sender_id} → {len(delivered)} hilos subj='{payload.subject[:60]}'"
    )
    return {"status": "ok", "delivered_count": len(delivered), "delivered": delivered}


# ==================== Iter48: Endpoints de Conversaciones (Chat Continuo) ====================

class ReplyPayload(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


async def _load_conv_or_403(conversation_id: str, user_id: str) -> dict:
    conv = await db.conversations.find_one({"conversation_id": conversation_id}, {"_id": 0})
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    if user_id not in conv.get("participants", []):
        raise HTTPException(status_code=403, detail="No participas de esta conversación")
    return conv


@router.get("/inbox/conversations/{conversation_id}/messages")
async def get_conversation_thread(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
):
    """Devuelve el historial completo del hilo (ordenado ascendente) y marca
    automáticamente como leídos los mensajes del otro participante.
    """
    user = await get_current_user(authorization)
    user_id = user["user_id"]
    conv = await _load_conv_or_403(conversation_id, user_id)

    # Marcar como leídos los mensajes que no provienen del propio usuario
    await mark_conversation_read(conversation_id=conversation_id, user_id=user_id)

    msgs = []
    cur = db.conversation_messages.find(
        {"conversation_id": conversation_id}, {"_id": 0}
    ).sort("created_at", 1)
    async for m in cur:
        m["is_mine"] = m.get("from_user_id") == user_id
        msgs.append(m)

    # Construir cabecera para el frontend
    other_id = next((p for p in conv["participants"] if p != user_id), None)
    other_meta = (conv.get("participants_meta") or {}).get(other_id, {})
    header = {
        "conversation_id": conversation_id,
        "subject": conv.get("subject"),
        "other_user_id": other_id,
        "other_user_name": other_meta.get("name") or other_id or "",
        "other_user_email": other_meta.get("email") or "",
    }
    return {"conversation": header, "messages": msgs}


@router.post("/inbox/conversations/{conversation_id}/messages")
async def post_conversation_message(
    conversation_id: str,
    payload: ReplyPayload,
    authorization: Optional[str] = Header(None),
):
    """Anexa un nuevo mensaje al hilo. No crea una fila duplicada en la
    bandeja: el hilo único se actualiza con el nuevo `last_message_at`.
    """
    user = await get_current_user(authorization)
    user_id = user["user_id"]
    conv = await _load_conv_or_403(conversation_id, user_id)

    sender_name = (
        f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        or user.get("email", "")
    )
    msg = await append_message(
        conversation=conv,
        from_user_id=user_id,
        from_user_name=sender_name,
        body_plain=payload.body,
    )
    other_id = next((p for p in conv.get("participants", []) if p != user_id), None)
    if other_id:
        await _push_internal_message(
            recipient_id=other_id,
            conversation_id=conversation_id,
            from_user_name=sender_name,
            body=payload.body,
            subject=conv.get("subject") or "",
            created_at=msg["created_at"],
        )
    return {"status": "ok", "message": {**msg, "is_mine": True}}


@router.delete("/inbox/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
):
    """Soft-delete del hilo SOLO para el usuario actual. El otro participante
    sigue viendo la conversación en su bandeja. Si el otro envía un nuevo
    mensaje, el hilo se "revive" para este usuario."""
    user = await get_current_user(authorization)
    user_id = user["user_id"]
    await _load_conv_or_403(conversation_id, user_id)
    await db.conversations.update_one(
        {"conversation_id": conversation_id},
        {"$addToSet": {"deleted_for": user_id}},
    )
    return {"status": "deleted", "conversation_id": conversation_id}

