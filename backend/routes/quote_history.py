"""Módulo Histórico de Cotizaciones.
Snapshot inmutable de cotizaciones al alcanzar estado final o convertirse en Proyecto.
Solo lectura + descarga de PDF. Acceso: admin (Administrador del Sistema) o cargo='Director'.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
import logging

from config import db, get_current_user

router = APIRouter()


def _can_access_history(user: dict) -> bool:
    """Solo admin (Administrador del Sistema) o cargo='Director'."""
    return user.get("role") == "admin" or (user.get("cargo") or "").strip() == "Director"


async def archive_quote_to_history(quote_id: str, trigger: str, user: Optional[dict] = None) -> Optional[dict]:
    """Genera snapshot del quote y lo archiva. Marca el quote original con archived=True.

    trigger: 'status_entregada', 'status_enviada_imple', 'action_complete'.
    """
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        logging.warning(f"[quote_history] Quote {quote_id} no existe")
        return None

    # Evitar duplicados
    existing = await db.quote_history.find_one({"quote_id": quote_id}, {"_id": 0})
    if existing:
        logging.info(f"[quote_history] Quote {quote_id} ya archivada previamente")
        if not quote.get("archived"):
            await db.quotes.update_one({"quote_id": quote_id}, {"$set": {"archived": True, "archived_at": datetime.now(timezone.utc).isoformat()}})
        return existing

    # Resolver factura asociada (si aplica)
    invoice_number = quote.get("invoice_number") or quote.get("delivery_invoice_number")
    if not invoice_number:
        # Buscar en movimientos de inventario por referencia
        movs = await db.inventory_movements.find({"quote_id": quote_id, "movement_type": "salida"}, {"_id": 0}).to_list(10)
        for mv in movs:
            ref = mv.get("reference", "")
            if "FAC" in (ref or "").upper() or "FACTURA" in (ref or "").upper():
                invoice_number = ref
                break

    # Resolver responsable (quien creó la cotización)
    responsible = {
        "user_id": quote.get("created_by_user_id") or quote.get("created_by_id", ""),
        "name": quote.get("created_by_name") or quote.get("created_by", ""),
        "role": quote.get("created_by_role", ""),
    }

    # Carpeta de anexos
    attachments_folder = f"/uploads/quotes/{quote_id}"
    attachments_list = quote.get("attachments") or []

    now = datetime.now(timezone.utc).isoformat()
    archived_by_name = ""
    archived_by_email = ""
    if user:
        archived_by_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
        archived_by_email = user.get("email", "")

    history_doc = {
        "history_id": f"qhist_{quote_id}",
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number"),
        "quote_category": quote.get("quote_category"),
        "quote_type": quote.get("quote_type"),
        "quote_status_final": quote.get("quote_status"),
        "client_id": quote.get("client_id"),
        "client_name": quote.get("client_name"),
        "subtotal_usd": quote.get("subtotal_usd"),
        "total_usd": quote.get("total_usd"),
        "total_bs": quote.get("total_bs"),
        "exchange_rate": quote.get("exchange_rate"),
        "services": quote.get("services", []),
        "hardware": quote.get("hardware", []),
        "equipment_items": quote.get("equipment_items", []),
        "ft_equipment_items": quote.get("ft_equipment_items", []),
        "repair_models": quote.get("repair_models", []),
        "notes": quote.get("notes"),
        "invoice_number": invoice_number,
        "responsible": responsible,
        "attachments_folder": attachments_folder,
        "attachments": attachments_list,
        "archived_at": now,
        "archived_trigger": trigger,
        "archived_by_name": archived_by_name,
        "archived_by_email": archived_by_email,
        "snapshot": {k: v for k, v in quote.items() if k != "_id"},
        "created_at": quote.get("created_at"),
        "project_id": quote.get("project_id"),
    }
    await db.quote_history.insert_one(history_doc)

    # Marcar cotización original como archivada (no se borra por integridad referencial con proyectos/inventario)
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {
            "archived": True,
            "archived_at": now,
            "archived_trigger": trigger,
        }}
    )
    history_doc.pop("_id", None)
    logging.info(f"[quote_history] Quote {quote_id} archivado. Trigger: {trigger}")
    return history_doc


async def check_and_archive_on_status_change(quote_id: str, new_status: str, user: Optional[dict] = None):
    """Invocado tras cada transición de estado. Archiva si se llegó al estado final de la categoría."""
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        return
    category = quote.get("quote_category", "implementation")
    final_states = {
        "implementation": "Enviada a Imple",
        "equipment": "Entregada",
        "fast_track": "Entregada",
        "repair": "Entregada",
    }
    final = final_states.get(category)
    if not final:
        return
    if new_status == final:
        trigger_map = {
            "Enviada a Imple": "status_enviada_imple",
            "Entregada": "status_entregada",
        }
        await archive_quote_to_history(quote_id, trigger_map.get(new_status, "status_final"), user)


# ==================== ENDPOINTS ====================

@router.get("/quote-history")
async def list_quote_history(
    search: Optional[str] = None,
    quote_category: Optional[str] = None,
    client_id: Optional[str] = None,
    invoice_number: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """Lista cotizaciones archivadas con filtros. Restringido."""
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")

    query = {}
    if quote_category:
        query["quote_category"] = quote_category
    if client_id:
        query["client_id"] = client_id
    if invoice_number:
        query["invoice_number"] = {"$regex": invoice_number, "$options": "i"}
    if search:
        query["$or"] = [
            {"quote_number": {"$regex": search, "$options": "i"}},
            {"client_name": {"$regex": search, "$options": "i"}},
            {"invoice_number": {"$regex": search, "$options": "i"}},
        ]
    if from_date or to_date:
        date_q = {}
        if from_date:
            date_q["$gte"] = from_date
        if to_date:
            date_q["$lte"] = to_date
        query["archived_at"] = date_q

    cursor = db.quote_history.find(query, {"_id": 0, "snapshot": 0}).sort("archived_at", -1)
    docs = await cursor.to_list(1000)
    return docs


@router.get("/quote-history/{history_id}")
async def get_quote_history(history_id: str, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")
    doc = await db.quote_history.find_one({"history_id": history_id}, {"_id": 0})
    if not doc:
        # Fallback: lookup por quote_id
        doc = await db.quote_history.find_one({"quote_id": history_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return doc


@router.get("/quote-history/{history_id}/pdf")
async def download_quote_history_pdf(history_id: str, authorization: Optional[str] = Header(None)):
    """Descarga el PDF original. Reusa el endpoint existente /quotes/{id}/pdf (funciona aunque archived=True)."""
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")
    doc = await db.quote_history.find_one({"history_id": history_id}, {"_id": 0})
    if not doc:
        doc = await db.quote_history.find_one({"quote_id": history_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    # Delega al endpoint existente pasando el quote_id original
    from routes.quotes import generate_quote_pdf as _gen_pdf
    return await _gen_pdf(doc["quote_id"], authorization=authorization)


@router.post("/quote-history/migrate-legacy")
async def migrate_legacy_quotes(authorization: Optional[str] = Header(None)):
    """Migración única: archiva cotizaciones existentes con estatus final y aún no archivadas."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede ejecutar migración")

    final_query = {
        "archived": {"$ne": True},
        "$or": [
            {"quote_status": "Enviada a Imple"},
            {"quote_status": "Entregada"},
        ],
    }
    cursor = db.quotes.find(final_query, {"_id": 0, "quote_id": 1, "quote_status": 1, "quote_category": 1})
    count = 0
    skipped = 0
    async for q in cursor:
        status = q.get("quote_status")
        trigger = "status_entregada" if status == "Entregada" else "status_enviada_imple"
        result = await archive_quote_to_history(q["quote_id"], trigger, current_user)
        if result:
            count += 1
        else:
            skipped += 1
    return {"migrated": count, "skipped": skipped}
