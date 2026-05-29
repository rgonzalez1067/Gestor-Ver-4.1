"""Servicio de Conversaciones — Iter48 (Chat Continuo).

Modelo:
  - `conversations`: cabecera del hilo 1:1 entre dos usuarios, agrupada por
    (par_de_usuarios + asunto_normalizado).
  - `conversation_messages`: mensajes individuales dentro del hilo,
    ordenados cronológicamente.

Diseño:
  - El asunto se normaliza quitando prefijos "Re:" para que respuestas
    consecutivas caigan en el mismo hilo (decisión de UX del usuario).
  - `participants` se almacena SIEMPRE ordenado para garantizar unicidad
    del par sin importar quién inicia.
  - `unread_for[user_id]` es un contador denormalizado para evitar scans
    de mensajes al construir el listado del inbox.
  - `deleted_for` permite soft-delete por usuario: un participante puede
    archivar el hilo sin afectar la vista del otro.
"""
import html as html_lib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import db

logger = logging.getLogger("conversation_service")


def normalize_subject(subject: str) -> str:
    """Elimina prefijos `Re:` repetidos para colapsar respuestas en un mismo
    hilo. Conserva el contenido principal (`re: re: Hola` → `hola`).
    """
    s = (subject or "").strip()
    while re.match(r"^re:\s*", s, flags=re.IGNORECASE):
        s = re.sub(r"^re:\s*", "", s, count=1, flags=re.IGNORECASE)
    return s.strip().lower()


def make_pair(user_a: str, user_b: str) -> list[str]:
    """Devuelve el par de usuarios ordenado (clave canónica del hilo)."""
    return sorted([user_a, user_b])


def render_body_html(body_plain: str) -> str:
    """HTML seguro estilo WhatsApp: escape + envolver en `<pre>` para
    preservar saltos de línea. Útil si se desea exportar el mensaje a un
    cliente externo en el futuro; el chat usa `body_plain` directo."""
    safe = html_lib.escape(body_plain or "")
    return (
        "<pre style=\"margin:0;font-family:inherit;font-size:14px;"
        "line-height:1.55;white-space:pre-wrap;word-break:break-word;\">"
        f"{safe}</pre>"
    )


async def find_or_create_conversation(
    *,
    sender_id: str,
    sender_name: str,
    sender_email: str,
    recipient_id: str,
    recipient_name: str,
    recipient_email: str,
    subject: str,
) -> dict:
    """Busca un hilo existente para el par + asunto normalizado; si no
    existe, lo crea. Idempotente.
    """
    pair = make_pair(sender_id, recipient_id)
    subj_norm = normalize_subject(subject)
    existing = await db.conversations.find_one(
        {"participants": pair, "subject_normalized": subj_norm},
        {"_id": 0},
    )
    if existing:
        return existing

    conv_id = f"conv_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "conversation_id": conv_id,
        "participants": pair,
        "participants_meta": {
            sender_id: {"name": sender_name, "email": sender_email},
            recipient_id: {"name": recipient_name, "email": recipient_email},
        },
        "subject": subject.strip() or "(sin asunto)",
        "subject_normalized": subj_norm or "(sin asunto)",
        "created_at": now,
        "last_message_at": now,
        "last_preview": "",
        "last_sender_id": "",
        "unread_for": {sender_id: 0, recipient_id: 0},
        "deleted_for": [],
    }
    await db.conversations.insert_one(doc)
    doc.pop("_id", None)
    logger.info(f"[conv] creada {conv_id} pair={pair} subj='{subj_norm}'")
    return doc


async def append_message(
    *,
    conversation: dict,
    from_user_id: str,
    from_user_name: str,
    body_plain: str,
) -> dict:
    """Inserta un mensaje y actualiza la cabecera del hilo de forma atómica.

    - Incrementa el contador de no-leídos del OTRO participante.
    - Resetea el del emisor (acaba de enviar, ya no tiene pendientes).
    - Si el receptor había soft-borrado el hilo (`deleted_for`), se restaura
      automáticamente: el nuevo mensaje "revive" la conversación.
    """
    conv_id = conversation["conversation_id"]
    participants = conversation["participants"]
    other_id = next((p for p in participants if p != from_user_id), None)
    if other_id is None:
        raise ValueError(f"from_user_id {from_user_id} no es participante del hilo {conv_id}")

    msg_id = f"msg_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc).isoformat()
    preview = (body_plain or "").strip().replace("\n", " ")
    if len(preview) > 140:
        preview = preview[:137] + "…"

    msg = {
        "message_id": msg_id,
        "conversation_id": conv_id,
        "from_user_id": from_user_id,
        "from_user_name": from_user_name,
        "body_plain": body_plain,
        "created_at": now,
        "read_by": [from_user_id],
    }
    await db.conversation_messages.insert_one(msg)
    # `insert_one` muta el dict agregando `_id: ObjectId` que no es JSON-serializable.
    msg.pop("_id", None)

    await db.conversations.update_one(
        {"conversation_id": conv_id},
        {
            "$set": {
                "last_message_at": now,
                "last_preview": preview,
                "last_sender_id": from_user_id,
                f"unread_for.{from_user_id}": 0,
            },
            "$inc": {f"unread_for.{other_id}": 1},
            # Si el receptor lo había borrado, lo "revivimos" para él.
            "$pull": {"deleted_for": other_id},
        },
    )
    return msg


async def mark_conversation_read(*, conversation_id: str, user_id: str) -> int:
    """Marca todos los mensajes del hilo como leídos por `user_id`.

    Devuelve el número de mensajes actualizados. Resetea el contador
    `unread_for[user_id]` a 0 en la cabecera.
    """
    res = await db.conversation_messages.update_many(
        {"conversation_id": conversation_id, "read_by": {"$ne": user_id}},
        {"$addToSet": {"read_by": user_id}},
    )
    await db.conversations.update_one(
        {"conversation_id": conversation_id},
        {"$set": {f"unread_for.{user_id}": 0}},
    )
    return res.modified_count


async def migrate_legacy_user_messages() -> int:
    """Migración idempotente: convierte mensajes user-to-user de `inbox_messages`
    (Iter46/47) en conversaciones del nuevo modelo (Iter48).

    Estrategia:
      - Procesa solo docs con `is_user_message == True` y `migrated_to_conversation_id`
        no establecido.
      - Crea (o reutiliza) la conversación correspondiente por par+asunto.
      - Inserta el mensaje en `conversation_messages` preservando `created_at`.
      - Marca el doc original como migrado (no se borra para auditoría).

    Devuelve el número de mensajes migrados.
    """
    cursor = db.inbox_messages.find(
        {"is_user_message": True, "migrated_to_conversation_id": {"$exists": False}},
        {"_id": 0},
    ).sort("created_at", 1)

    migrated = 0
    async for doc in cursor:
        from_id = doc.get("from_user_id") or ""
        from_name = doc.get("from_user_name") or ""
        from_email = doc.get("from_user_email") or ""
        recipient_id = doc.get("user_id") or ""
        recipient_name = doc.get("recipient_name") or ""
        recipient_email = doc.get("recipient_email") or ""
        subject = doc.get("subject") or "(sin asunto)"
        body_plain = doc.get("body_plain") or ""
        if not body_plain:
            # Mensajes con body_html pero sin body_plain (legacy temprano):
            # extraemos texto del HTML de forma trivial. Suficiente para
            # preservar contenido.
            body_plain = re.sub(r"<[^>]+>", "", doc.get("body_html") or "")

        if not from_id or not recipient_id:
            await db.inbox_messages.update_one(
                {"message_id": doc["message_id"]},
                {"$set": {"migrated_to_conversation_id": None, "migration_skipped": True}},
            )
            continue

        conv = await find_or_create_conversation(
            sender_id=from_id,
            sender_name=from_name,
            sender_email=from_email,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            subject=subject,
        )
        msg = await append_message(
            conversation=conv,
            from_user_id=from_id,
            from_user_name=from_name,
            body_plain=body_plain,
        )
        # Sobrescribir created_at del mensaje para preservar el timestamp original
        original_ts = doc.get("created_at")
        if original_ts:
            await db.conversation_messages.update_one(
                {"message_id": msg["message_id"]},
                {"$set": {"created_at": original_ts}},
            )
            await db.conversations.update_one(
                {"conversation_id": conv["conversation_id"]},
                {"$set": {"last_message_at": original_ts}},
            )

        await db.inbox_messages.update_one(
            {"message_id": doc["message_id"]},
            {"$set": {"migrated_to_conversation_id": conv["conversation_id"]}},
        )
        migrated += 1

    if migrated:
        logger.info(f"[conv] migrados {migrated} mensajes user-to-user legacy")
    return migrated


def conversation_for_user(conv: dict, user_id: str) -> dict:
    """Construye la fila de inbox que el frontend espera para una conversación.
    Calcula el "otro participante" y el contador de no leídos del usuario.
    """
    participants = conv.get("participants", [])
    other_id = next((p for p in participants if p != user_id), None)
    meta = conv.get("participants_meta") or {}
    other_meta = meta.get(other_id) or {}
    return {
        "type": "conversation",
        "conversation_id": conv["conversation_id"],
        "subject": conv.get("subject") or "(sin asunto)",
        "other_user_id": other_id,
        "other_user_name": other_meta.get("name") or other_id or "",
        "other_user_email": other_meta.get("email") or "",
        "last_preview": conv.get("last_preview") or "",
        "last_message_at": conv.get("last_message_at") or conv.get("created_at"),
        "last_sender_id": conv.get("last_sender_id") or "",
        "unread_count": int((conv.get("unread_for") or {}).get(user_id, 0)),
        "is_user_message": True,
    }
