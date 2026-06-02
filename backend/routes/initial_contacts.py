"""Route module: initial_contacts.py — Gestión de Contacto Inicial (Leads)"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid
import logging

from config import db, get_current_user
from services.assignment_notifications import (
    notify_initial_contact_assigned,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Models ---
class InitialContactCreate(BaseModel):
    contact_name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    legal_name: str
    interest_notes: Optional[str] = ""
    referred_by: Optional[str] = ""
    assigned_to_user_id: Optional[str] = None
    due_date: Optional[str] = None

class InitialContactAssign(BaseModel):
    assigned_to_user_id: str
    comment: Optional[str] = None

class InitialContactDocument(BaseModel):
    comment: str
    # Iter52: fecha del próximo contacto planificado (opcional, formato ISO).
    next_contact_date: Optional[str] = None

class InitialContactTransfer(BaseModel):
    target_user_id: str
    comment: Optional[str] = None

# --- Helpers ---
HIERARCHY_CAN_ASSIGN = {
    "Director": ["Gerente"],
    "Gerente": ["Coordinador", "Ejecutivo"],
    "Coordinador": ["Ejecutivo"],
    "Ejecutivo": ["Ejecutivo"],
}

async def get_user_by_id(user_id: str):
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return user

def user_display(user):
    if not user:
        return "Desconocido"
    return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get('email', '')

# --- Endpoints ---

@router.get("/initial-contacts")
async def list_initial_contacts(authorization: Optional[str] = Header(None)):
    """Lista contactos iniciales. Admins/Directores ven todos. Otros ven los asignados a ellos y subordinados."""
    current_user = await get_current_user(authorization)
    
    contacts = await db.initial_contacts.find(
        {"is_converted": False}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    return contacts


@router.get("/initial-contacts/all")
async def list_all_initial_contacts(authorization: Optional[str] = Header(None)):
    """Lista TODOS los contactos (incluyendo convertidos) para historial."""
    current_user = await get_current_user(authorization)
    contacts = await db.initial_contacts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return contacts


@router.post("/initial-contacts")
async def create_initial_contact(data: InitialContactCreate, authorization: Optional[str] = Header(None)):
    """Crear un nuevo contacto inicial."""
    current_user = await get_current_user(authorization)
    
    contact_id = f"ic_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    creator_name = user_display(current_user)

    # Resolver usuario asignado (si se proporcionó)
    assigned_user_id = data.assigned_to_user_id or current_user["user_id"]
    assigned_name = creator_name
    assigned_user_doc = None
    if data.assigned_to_user_id and data.assigned_to_user_id != current_user["user_id"]:
        target = await get_user_by_id(data.assigned_to_user_id)
        if target:
            assigned_name = user_display(target)
            assigned_user_id = target["user_id"]
            assigned_user_doc = target

    # Determinar sede válida (PYME o CORP). Si la sede del usuario actual o
    # del asignado no está en la lista permitida (ej. "TBP" para admins de
    # plataforma), caer a "PYME" como default seguro.
    def _valid_sede(s):
        return s if s in ("PYME", "CORP") else None
    sede = (
        _valid_sede((assigned_user_doc or {}).get("sede"))
        or _valid_sede(current_user.get("sede"))
        or "PYME"
    )
    
    contact = {
        "contact_id": contact_id,
        "contact_name": data.contact_name.strip(),
        "phone": (data.phone or "").strip(),
        "email": (data.email or "").strip(),
        "legal_name": data.legal_name.strip(),
        "interest_notes": (data.interest_notes or "").strip()[:300],
        "referred_by": (data.referred_by or "").strip(),
        "assigned_to_user_id": assigned_user_id,
        "assigned_to_name": assigned_name,
        "due_date": data.due_date or None,
        "created_by_user_id": current_user["user_id"],
        "created_by_name": creator_name,
        "sede": sede,
        "is_converted": False,
        "converted_client_id": None,
        "created_at": now,
        "updated_at": now,
        "bitacora": [
            {
                "entry_id": f"be_{uuid.uuid4().hex[:8]}",
                "action": "created",
                "description": f"Contacto creado por {creator_name}" + (f". Asignado a {assigned_name}" if assigned_name != creator_name else "") + (f". Fecha limite: {data.due_date}" if data.due_date else ""),
                "user_id": current_user["user_id"],
                "user_name": creator_name,
                "timestamp": now
            }
        ]
    }
    
    await db.initial_contacts.insert_one(contact)
    contact.pop("_id", None)
    
    # Notificar al asignado si es diferente al creador
    if assigned_user_id != current_user["user_id"]:
        notification = {
            "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
            "user_id": assigned_user_id,
            "type": "initial_contact_assigned",
            "title": "Nuevo Contacto Asignado",
            "message": f"{contact['legal_name']} - Asignado por {creator_name}",
            "reference_id": contact_id,
            "is_read": False,
            "created_at": now
        }
        await db.notifications.insert_one(notification)

        # Email asíncrono al ejecutivo asignado (fire-and-forget, no bloquea UI)
        try:
            await notify_initial_contact_assigned(
                contact=contact,
                target_user=assigned_user_doc or await get_user_by_id(assigned_user_id),
                assigner_name=creator_name,
            )
        except Exception as e:
            logger.warning(f"[email] notify_initial_contact_assigned (create) failed: {e}")

    # Push notification WebSocket (evento #16 Contacto inicial registrado)
    try:
        from services.notification_service import notify as _push_notify
        # Derivar sede: Pyme/Corp según el created_by
        creator_sede = None
        if assigned_user_id:
            creator_doc = await db.users.find_one({"user_id": assigned_user_id}, {"_id": 0, "sede": 1})
            if creator_doc:
                creator_sede = creator_doc.get("sede")
        await _push_notify(
            event_type="initial_contact_created",
            title=f"Nuevo Contacto Inicial registrado",
            message=f"{contact.get('legal_name','')} · RIF {contact.get('rif','')}",
            context={
                "creator_user_id": assigned_user_id,
                "sede": creator_sede,
            },
            link=f"/initial-contacts",
        )
    except Exception:
        pass

    return contact


@router.post("/initial-contacts/{contact_id}/assign")
async def assign_initial_contact(contact_id: str, data: InitialContactAssign, authorization: Optional[str] = Header(None)):
    """Asignar o reasignar un contacto a otro usuario. Valida jerarquía."""
    current_user = await get_current_user(authorization)
    
    contact = await db.initial_contacts.find_one({"contact_id": contact_id, "is_converted": False}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado o ya convertido")
    
    target_user = await get_user_by_id(data.assigned_to_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
    
    # Validate hierarchy
    my_cargo = current_user.get("cargo", "")
    is_admin = current_user.get("role") == "admin"
    target_cargo = target_user.get("cargo", "")
    
    if not is_admin:
        allowed_target_cargos = HIERARCHY_CAN_ASSIGN.get(my_cargo, [])
        if target_cargo not in allowed_target_cargos and my_cargo != "Director":
            raise HTTPException(status_code=403, detail=f"Un {my_cargo} no puede asignar a un {target_cargo}")
    
    now = datetime.now(timezone.utc).isoformat()
    assigner_name = user_display(current_user)
    target_name = user_display(target_user)
    
    entry = {
        "entry_id": f"be_{uuid.uuid4().hex[:8]}",
        "action": "assigned",
        "description": f"Asignado a {target_name} por {assigner_name}" + (f". Nota: {data.comment}" if data.comment else ""),
        "user_id": current_user["user_id"],
        "user_name": assigner_name,
        "timestamp": now
    }
    
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {
            "$set": {
                "assigned_to_user_id": target_user["user_id"],
                "assigned_to_name": target_name,
                "updated_at": now
            },
            "$push": {"bitacora": entry}
        }
    )
    
    # Create notification for the target user
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": target_user["user_id"],
        "type": "initial_contact_assigned",
        "title": "Nuevo Contacto Asignado",
        "message": f"{contact['legal_name']} - Asignado por {assigner_name}",
        "reference_id": contact_id,
        "is_read": False,
        "created_at": now
    }
    await db.notifications.insert_one(notification)

    # Email asíncrono al ejecutivo (NO bloquea la respuesta HTTP)
    try:
        # Refrescamos el contacto con los datos asignados frescos para que la
        # plantilla incluya nombre/sla actualizados.
        contact_for_email = {**contact, "assigned_to_user_id": target_user["user_id"], "assigned_to_name": target_name}
        await notify_initial_contact_assigned(
            contact=contact_for_email,
            target_user=target_user,
            assigner_name=assigner_name,
        )
    except Exception as e:
        logger.warning(f"[email] notify_initial_contact_assigned (assign) failed: {e}")

    return {"message": f"Contacto asignado a {target_name}", "assigned_to": target_name}


@router.post("/initial-contacts/{contact_id}/document")
async def document_initial_contact(contact_id: str, data: InitialContactDocument, authorization: Optional[str] = Header(None)):
    """Documentar gestión del contacto (agregar comentario a bitácora)."""
    current_user = await get_current_user(authorization)
    
    contact = await db.initial_contacts.find_one({"contact_id": contact_id, "is_converted": False}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado o ya convertido")
    
    now = datetime.now(timezone.utc).isoformat()
    user_name = user_display(current_user)
    
    entry = {
        "entry_id": f"be_{uuid.uuid4().hex[:8]}",
        "action": "documented",
        "description": data.comment.strip(),
        "user_id": current_user["user_id"],
        "user_name": user_name,
        "timestamp": now
    }
    
    # Iter52: mantener "last_contact_date" / "next_contact_date" sincronizados.
    # Cada gestión actualiza last_contact_date al instante; next_contact_date
    # solo si el agente la informó (no se sobrescribe con vacío).
    set_fields = {"updated_at": now, "last_contact_date": now}
    if data.next_contact_date:
        set_fields["next_contact_date"] = data.next_contact_date.strip()
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {"$set": set_fields, "$push": {"bitacora": entry}}
    )
    
    return {"message": "Gestion documentada exitosamente"}


@router.post("/initial-contacts/{contact_id}/transfer")
async def transfer_initial_contact(contact_id: str, data: InitialContactTransfer, authorization: Optional[str] = Header(None)):
    """Transferir contacto entre áreas (Pyme <-> Corp). Solo Gerentes pueden transferir."""
    current_user = await get_current_user(authorization)
    
    contact = await db.initial_contacts.find_one({"contact_id": contact_id, "is_converted": False}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado o ya convertido")
    
    my_cargo = current_user.get("cargo", "")
    is_admin = current_user.get("role") == "admin"
    if my_cargo != "Gerente" and my_cargo != "Director" and not is_admin:
        raise HTTPException(status_code=403, detail="Solo Gerentes o Directores pueden transferir contactos entre areas")
    
    target_user = await get_user_by_id(data.target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario destino no encontrado")
    
    now = datetime.now(timezone.utc).isoformat()
    from_name = user_display(current_user)
    to_name = user_display(target_user)
    new_sede = target_user.get("sede", "PYME")
    
    entry = {
        "entry_id": f"be_{uuid.uuid4().hex[:8]}",
        "action": "transferred",
        "description": f"Transferido a {to_name} (Sede {new_sede}) por {from_name}" + (f". Nota: {data.comment}" if data.comment else ""),
        "user_id": current_user["user_id"],
        "user_name": from_name,
        "timestamp": now
    }
    
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {
            "$set": {
                "assigned_to_user_id": target_user["user_id"],
                "assigned_to_name": to_name,
                "sede": new_sede,
                "updated_at": now
            },
            "$push": {"bitacora": entry}
        }
    )
    
    # Notification
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": target_user["user_id"],
        "type": "initial_contact_transferred",
        "title": "Contacto Transferido",
        "message": f"{contact['legal_name']} - Transferido por {from_name}",
        "reference_id": contact_id,
        "is_read": False,
        "created_at": now
    }
    await db.notifications.insert_one(notification)

    # Email asíncrono al nuevo responsable (mismo template que asignación)
    try:
        contact_for_email = {**contact, "assigned_to_user_id": target_user["user_id"], "assigned_to_name": to_name, "sede": new_sede}
        await notify_initial_contact_assigned(
            contact=contact_for_email,
            target_user=target_user,
            assigner_name=from_name,
        )
    except Exception as e:
        logger.warning(f"[email] notify_initial_contact_assigned (transfer) failed: {e}")

    return {"message": f"Contacto transferido a {to_name} (Sede {new_sede})"}


@router.post("/initial-contacts/{contact_id}/convert")
async def convert_to_prospect(contact_id: str, authorization: Optional[str] = Header(None)):
    """Convertir contacto inicial a Prospecto (crea registro en Clientes)."""
    current_user = await get_current_user(authorization)
    
    contact = await db.initial_contacts.find_one({"contact_id": contact_id, "is_converted": False}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado o ya convertido")
    
    now = datetime.now(timezone.utc).isoformat()
    converter_name = user_display(current_user)
    
    # Create client record with status "Prospecto"
    client_id = f"cli_{uuid.uuid4().hex[:12]}"
    
    # Migrar bitácora completa del contacto inicial + entrada de conversión
    conversion_entry = {
        "entry_id": f"be_{uuid.uuid4().hex[:8]}",
        "action": "converted",
        "description": f"Convertido a Prospecto por {converter_name}. Cliente ID: {client_id}",
        "user_id": current_user["user_id"],
        "user_name": converter_name,
        "timestamp": now
    }
    migrated_bitacora = list(contact.get("bitacora", [])) + [conversion_entry]
    
    # Precargar primer contacto del Prospecto con los datos del Contacto Inicial.
    # Según requerimiento: Nombre/Teléfono/Email del contacto inicial son el primer contacto del cliente.
    initial_full_name = (contact.get("contact_name") or "").strip()
    initial_phone = (contact.get("phone") or "").strip()
    initial_email = (contact.get("email") or "").strip()
    first_contact = None
    if initial_full_name or initial_phone or initial_email:
        first_contact = {
            "contact_id": f"cnt_{uuid.uuid4().hex[:8]}",
            "full_name": initial_full_name,
            "first_name": None,
            "last_name": None,
            "phone": initial_phone,
            "email": initial_email,
            "role": "Administrativo",
        }

    new_client = {
        "client_id": client_id,
        "rif": "",
        "legal_name": contact["legal_name"],
        "fantasy_name": contact["legal_name"],
        "commercial_name": "",
        "contact_name": contact["contact_name"],
        "contact_phone": contact["phone"],
        "contact_email": contact["email"],
        "contacts": [first_contact] if first_contact else [],
        "address": "",
        "sucursal": "",
        "branch_address": "",
        "additional_info": contact.get("interest_notes", "") or f"Convertido desde Contacto Inicial por {converter_name}",
        "client_status": "Prospecto",
        "condicion": "Prospecto",
        "account_executive_id": current_user["user_id"],
        "account_executive_name": converter_name,
        "owner_id": current_user["user_id"],
        "owner_name": converter_name,
        "sede": contact.get("sede", "PYME"),
        "bitacora": migrated_bitacora,
        "created_at": now,
        "updated_at": now
    }
    
    await db.clients.insert_one(new_client)

    # ──────────────────────────────────────────────────────────────────────
    # HERENCIA DE BITÁCORA (initial_contact_logs → client_logs)
    # Copiamos íntegramente las entradas de la bitácora unificada del
    # Contacto Inicial al nuevo Cliente, conservando trazabilidad mediante
    # el campo `origin = "initial_contact"`. El UI muestra un badge
    # "Origen: Contacto Inicial" para cada entrada heredada.
    # ──────────────────────────────────────────────────────────────────────
    inherited_count = 0
    try:
        cursor = db.initial_contact_logs.find(
            {"contact_id": contact_id}, {"_id": 0}
        ).sort("created_at", 1)
        async for src in cursor:
            inherited = {
                "log_id": f"log_{uuid.uuid4().hex[:12]}",
                "client_id": client_id,
                "contact_date": src.get("contact_date") or now[:10],
                "detail": src.get("detail") or "",
                "action": src.get("action"),
                "follow_up_date": src.get("follow_up_date"),
                "contacted_person": src.get("contacted_person"),
                "is_completed": bool(src.get("is_completed", False)),
                "created_by": src.get("created_by"),
                "created_by_name": src.get("created_by_name"),
                "created_at": src.get("created_at") or now,
                "origin": "initial_contact",
                "origin_contact_id": contact_id,
                "origin_log_id": src.get("log_id"),
            }
            await db.client_logs.insert_one(inherited)
            inherited_count += 1
    except Exception as e:
        logger.warning(
            f"[initial_contacts] No se pudieron heredar logs del contacto "
            f"{contact_id} al cliente {client_id}: {e}"
        )

    # Entrada de conversión también en client_logs para trazabilidad
    await db.client_logs.insert_one({
        "log_id": f"log_{uuid.uuid4().hex[:12]}",
        "client_id": client_id,
        "contact_date": now[:10],
        "detail": f"[CONVERSIÓN] Prospecto creado a partir del Contacto Inicial. {inherited_count} entrada(s) de bitácora heredada(s).",
        "action": "Convertido a Prospecto",
        "follow_up_date": None,
        "contacted_person": None,
        "is_completed": True,
        "created_by": current_user.get("email", "unknown"),
        "created_by_name": converter_name,
        "created_at": now,
        "origin": "initial_contact",
        "origin_contact_id": contact_id,
    })

    # Mark contact as converted
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {
            "$set": {
                "is_converted": True,
                "converted_client_id": client_id,
                "updated_at": now
            },
            "$push": {"bitacora": conversion_entry}
        }
    )

    return {
        "message": "Contacto convertido a Prospecto exitosamente",
        "client_id": client_id,
        "inherited_logs": inherited_count,
    }


@router.get("/initial-contacts/{contact_id}")
async def get_initial_contact(contact_id: str, authorization: Optional[str] = Header(None)):
    """Obtener detalle de un contacto inicial."""
    await get_current_user(authorization)
    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    return contact


@router.get("/initial-contacts/my-commitments/list")
async def get_my_commitments(authorization: Optional[str] = Header(None)):
    """Obtener contactos asignados al usuario actual + los de sus subordinados (para supervisores)."""
    current_user = await get_current_user(authorization)
    my_id = current_user["user_id"]
    my_cargo = current_user.get("cargo", "")
    my_sede = current_user.get("sede", "PYME")
    is_admin = current_user.get("role") == "admin"
    
    if is_admin or my_cargo == "Director":
        # Directors and admins see all
        contacts = await db.initial_contacts.find(
            {"is_converted": False}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
    elif my_cargo in ("Gerente", "Coordinador"):
        # Gerentes/Coordinadores see their own + subordinates in same sede
        subordinate_cargos = HIERARCHY_CAN_ASSIGN.get(my_cargo, [])
        subordinate_users = await db.users.find(
            {"cargo": {"$in": subordinate_cargos}, "sede": my_sede, "is_active": True},
            {"_id": 0, "user_id": 1}
        ).to_list(100)
        subordinate_ids = [u["user_id"] for u in subordinate_users]
        all_ids = [my_id] + subordinate_ids
        contacts = await db.initial_contacts.find(
            {"is_converted": False, "assigned_to_user_id": {"$in": all_ids}}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
    else:
        # Ejecutivos see only their own
        contacts = await db.initial_contacts.find(
            {"is_converted": False, "assigned_to_user_id": my_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
    
    return contacts


# NOTA: los endpoints /api/notifications se centralizaron en /app/backend/routes/notifications.py
# (refactor iter 180, Sistema de Push Notifications P1 con WebSocket).


@router.delete("/initial-contacts/{contact_id}")
async def delete_initial_contact(contact_id: str, authorization: Optional[str] = Header(None)):
    """Elimina permanentemente un contacto inicial. Solo administradores.
    Bloquea la eliminación si el contacto ya fue convertido a cliente."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar contactos iniciales")

    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")

    if contact.get("is_converted"):
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: el contacto ya fue convertido a cliente. Elimine primero el cliente relacionado.",
        )

    await db.initial_contacts.delete_one({"contact_id": contact_id})
    logger.info(
        f"[initial_contacts] deleted {contact_id} ({contact.get('legal_name', '')}) "
        f"by {current_user.get('email')}"
    )
    return {"message": "Contacto eliminado exitosamente"}


# ============================================================================
# BITÁCORA — Espejo del modelo de Clientes para uso unificado.
# Cada entrada vive en `initial_contact_logs`. Si tiene `follow_up_date` y
# `is_completed=False`, aparece como alerta en el Dashboard de Seguimiento.
# ============================================================================

class InitialContactLogCreate(BaseModel):
    detail: str
    action: Optional[str] = None
    follow_up_date: Optional[str] = None
    contacted_person: Optional[str] = None


@router.get("/initial-contacts/{contact_id}/logs")
async def list_initial_contact_logs(contact_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    cursor = db.initial_contact_logs.find(
        {"contact_id": contact_id}, {"_id": 0}
    ).sort("created_at", -1)
    return [doc async for doc in cursor]


@router.post("/initial-contacts/{contact_id}/logs")
async def add_initial_contact_log(
    contact_id: str,
    payload: InitialContactLogCreate,
    authorization: Optional[str] = Header(None),
):
    current_user = await get_current_user(authorization)
    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")
    if not payload.detail.strip():
        raise HTTPException(400, "El detalle es obligatorio")

    now = datetime.now(timezone.utc)
    log_doc = {
        "log_id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "detail": payload.detail.strip(),
        "action": (payload.action or "").strip() or None,
        "follow_up_date": payload.follow_up_date or None,
        "contacted_person": payload.contacted_person or None,
        "contact_date": now.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "created_by": current_user.get("user_id"),
        "created_by_name": user_display(current_user),
        "is_completed": False,
        "origin": "initial_contact",
    }
    await db.initial_contact_logs.insert_one(log_doc)
    # Bump timestamp del contacto para indicar última gestión
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {"$set": {"last_activity_at": now.isoformat()}},
    )
    log_doc.pop("_id", None)
    return log_doc


@router.patch("/initial-contacts/logs/{log_id}/complete")
async def toggle_initial_contact_log_complete(
    log_id: str, authorization: Optional[str] = Header(None)
):
    await get_current_user(authorization)
    log = await db.initial_contact_logs.find_one({"log_id": log_id}, {"_id": 0})
    if not log:
        raise HTTPException(404, "Entrada no encontrada")
    new_state = not log.get("is_completed", False)
    await db.initial_contact_logs.update_one(
        {"log_id": log_id}, {"$set": {"is_completed": new_state}}
    )
    return {"log_id": log_id, "is_completed": new_state}


# ============================================================================
# CERRAR GESTIÓN — Admin only. Marca el contacto como "closed" sin borrarlo.
# La fila se renderizará con fondo azul (estado "gestionado, no activo").
# ============================================================================

class InitialContactClose(BaseModel):
    reason: str


@router.post("/initial-contacts/{contact_id}/close")
async def close_initial_contact(
    contact_id: str,
    payload: InitialContactClose,
    authorization: Optional[str] = Header(None),
):
    """Cierra la gestión de un contacto inicial. Disponible para todos los
    usuarios con acceso al módulo (ya no es admin-only). El cierre queda
    registrado automáticamente en la bitácora unificada con timestamp y autor."""
    current_user = await get_current_user(authorization)
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, "El motivo de cierre es obligatorio")

    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")
    if contact.get("status") == "closed":
        raise HTTPException(400, "El contacto ya está cerrado")

    now = datetime.now(timezone.utc)
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {"$set": {
            "status": "closed",
            "closed_at": now.isoformat(),
            "closed_by": current_user.get("user_id"),
            "closed_by_name": user_display(current_user),
            "closed_reason": payload.reason.strip(),
        }},
    )
    # Registrar el cierre como entrada de bitácora para trazabilidad
    await db.initial_contact_logs.insert_one({
        "log_id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "detail": f"[CIERRE DE GESTIÓN] {payload.reason.strip()}",
        "action": None,
        "follow_up_date": None,
        "contacted_person": None,
        "contact_date": now.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "created_by": current_user.get("user_id"),
        "created_by_name": user_display(current_user),
        "is_completed": True,
        "origin": "initial_contact_closure",
    })
    logger.info(
        f"[initial_contacts] CLOSED {contact_id} by {current_user.get('email')} "
        f"reason={payload.reason!r}"
    )
    return {"contact_id": contact_id, "status": "closed", "closed_at": now.isoformat()}


class InitialContactReopen(BaseModel):
    reason: Optional[str] = ""
    new_due_date: Optional[str] = None  # YYYY-MM-DD; si vacío, se aplica hoy+5 días


@router.post("/initial-contacts/{contact_id}/reopen")
async def reopen_initial_contact(
    contact_id: str,
    payload: Optional[InitialContactReopen] = None,
    authorization: Optional[str] = Header(None),
):
    """Reabre una gestión cerrada. Disponible para todos los usuarios con
    acceso al módulo. Al reabrir, el SLA se resetea: la `due_date` queda
    en `new_due_date` (si fue provista) o en hoy + 5 días, de modo que
    el indicador visual arranque en VERDE (En Tiempo) como una gestión nueva."""
    current_user = await get_current_user(authorization)
    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")
    if contact.get("status") != "closed":
        raise HTTPException(400, "El contacto no está cerrado")

    now = datetime.now(timezone.utc)
    reopen_reason = (payload.reason if payload else "") or ""
    reopen_reason = reopen_reason.strip()

    # Calcular nueva fecha límite (reset SLA → arranca en verde)
    from datetime import timedelta
    raw_new_due = (payload.new_due_date if payload else None) or ""
    raw_new_due = raw_new_due.strip()
    if raw_new_due:
        new_due_date = raw_new_due
    else:
        new_due_date = (now + timedelta(days=5)).strftime("%Y-%m-%d")

    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {
            "$set": {
                "status": "active",
                "due_date": new_due_date,
                "reopened_at": now.isoformat(),
                "reopened_by": current_user.get("user_id"),
                "reopened_by_name": user_display(current_user),
                "updated_at": now.isoformat(),
            },
            "$unset": {
                "closed_at": "",
                "closed_by": "",
                "closed_by_name": "",
                "closed_reason": "",
            },
        },
    )
    # Registrar la reapertura como entrada de bitácora para trazabilidad
    detail = f"[REAPERTURA DE GESTIÓN] Nueva fecha límite: {new_due_date}"
    if reopen_reason:
        detail += f". Motivo: {reopen_reason}"
    await db.initial_contact_logs.insert_one({
        "log_id": str(uuid.uuid4()),
        "contact_id": contact_id,
        "detail": detail,
        "action": None,
        "follow_up_date": None,
        "contacted_person": None,
        "contact_date": now.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "created_by": current_user.get("user_id"),
        "created_by_name": user_display(current_user),
        "is_completed": True,
        "origin": "initial_contact_reopen",
    })
    logger.info(
        f"[initial_contacts] REOPENED {contact_id} by {current_user.get('email')} "
        f"new_due_date={new_due_date}"
    )
    return {
        "contact_id": contact_id,
        "status": "active",
        "reopened_at": now.isoformat(),
        "new_due_date": new_due_date,
    }

