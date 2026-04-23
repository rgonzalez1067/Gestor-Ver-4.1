"""Route module: initial_contacts.py — Gestión de Contacto Inicial (Leads)"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

from config import db, get_current_user

router = APIRouter()

# --- Models ---
class InitialContactCreate(BaseModel):
    contact_name: str
    phone: str
    email: str
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

class InitialContactTransfer(BaseModel):
    target_user_id: str
    comment: Optional[str] = None

# --- Helpers ---
HIERARCHY_CAN_ASSIGN = {
    "Director": ["Gerente"],
    "Gerente": ["Coordinador", "Ejecutivo"],
    "Coordinador": ["Ejecutivo"],
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
    if data.assigned_to_user_id and data.assigned_to_user_id != current_user["user_id"]:
        target = await get_user_by_id(data.assigned_to_user_id)
        if target:
            assigned_name = user_display(target)
            assigned_user_id = target["user_id"]
    
    contact = {
        "contact_id": contact_id,
        "contact_name": data.contact_name.strip(),
        "phone": data.phone.strip(),
        "email": data.email.strip(),
        "legal_name": data.legal_name.strip(),
        "interest_notes": (data.interest_notes or "").strip()[:300],
        "referred_by": (data.referred_by or "").strip(),
        "assigned_to_user_id": assigned_user_id,
        "assigned_to_name": assigned_name,
        "due_date": data.due_date or None,
        "created_by_user_id": current_user["user_id"],
        "created_by_name": creator_name,
        "sede": current_user.get("sede", "PYME"),
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
    
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {"$set": {"updated_at": now}, "$push": {"bitacora": entry}}
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
    
    new_client = {
        "client_id": client_id,
        "rif": "",
        "legal_name": contact["legal_name"],
        "fantasy_name": contact["legal_name"],
        "commercial_name": "",
        "contact_name": contact["contact_name"],
        "contact_phone": contact["phone"],
        "contact_email": contact["email"],
        "address": "",
        "sucursal": "",
        "branch_address": "",
        "additional_info": contact.get("interest_notes", "") or f"Convertido desde Contacto Inicial por {converter_name}",
        "client_status": "Prospecto",
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
    
    return {"message": f"Contacto convertido a Prospecto exitosamente", "client_id": client_id}


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
