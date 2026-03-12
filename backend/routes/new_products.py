"""Route module: new_products.py — Pipeline de I+D de Nuevos Productos"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid

from config import db, get_current_user
from models import NewProduct, NewProductCreate, NewProductEvolutionEntry, BankIntegration

router = APIRouter()

NP_STATUSES = ["Negociación", "DESA", "SQA", "IMPLE", "Promovido"]

# ==================== CRUD ====================

@router.post("/new-products")
async def create_new_product(body: NewProductCreate, authorization: Optional[str] = Header(None)):
    """Crea un nuevo producto en el pipeline I+D. Estado inicial: Negociación."""
    await get_current_user(authorization)

    bank = await db.banks.find_one({"bank_id": body.bank_id}, {"_id": 0, "name": 1})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")

    product = NewProduct(
        service_name=body.service_name,
        component_type=body.component_type,
        bank_id=body.bank_id,
        bank_name=bank["name"],
        status="Negociación",
        notes=body.notes,
    )
    doc = product.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.new_products.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/new-products")
async def list_new_products(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    products = await db.new_products.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return products


@router.get("/new-products/{product_id}")
async def get_new_product(product_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.delete("/new-products/{product_id}")
async def delete_new_product(product_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.new_products.delete_one({"product_id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    await db.new_product_evolution.delete_many({"product_id": product_id})
    return {"message": "Producto eliminado"}


# ==================== STATUS CHANGE + HAND-OFF ====================

@router.put("/new-products/{product_id}/status")
async def update_new_product_status(product_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualiza el estado de un producto. Si pasa a IMPLE, ejecuta hand-off automático al banco."""
    await get_current_user(authorization)

    new_status = body.get("status")
    if new_status not in NP_STATUSES or new_status == "Promovido":
        raise HTTPException(status_code=400, detail=f"Estado inválido. Permitidos: {NP_STATUSES[:-1]}")

    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if product["status"] == "Promovido":
        raise HTTPException(status_code=400, detail="El producto ya fue promovido y no puede cambiar de estado")

    old_status = product["status"]
    if new_status == old_status:
        return product

    # -- Notificación simulada --
    try:
        sales_roles = ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]
        sales_users = await db.users.find(
            {"cargo": {"$in": sales_roles}},
            {"_id": 0, "email": 1, "first_name": 1}
        ).to_list(100)
        recipients = [u["email"] for u in sales_users if u.get("email")]

        if new_status == "IMPLE":
            logging.info(
                f"[EMAIL SIMULADO - CRITICO] Producto listo para banco: "
                f"'{product['service_name']}' ahora disponible en la ficha de '{product['bank_name']}'. "
                f"Destinatarios={recipients or 'Sin ejecutivos registrados'}"
            )
        else:
            logging.info(
                f"[EMAIL SIMULADO] Avance pipeline I+D: "
                f"'{product['service_name']}' pasó de {old_status} a {new_status}. "
                f"Banco={product['bank_name']}. "
                f"Destinatarios={recipients or 'Sin ejecutivos registrados'}"
            )
    except Exception as e:
        logging.error(f"Error al preparar notificación de nuevo producto: {e}")

    # -- Hand-off automático a integraciones del banco cuando llega a IMPLE --
    promoted = False
    if new_status == "IMPLE":
        bank_id = product["bank_id"]
        integration = BankIntegration(
            service_name=product["service_name"],
            component_type=product["component_type"],
            status="PreProd",
            notes=f"Promovido desde Pipeline I+D (producto {product_id})",
        )
        intg_doc = integration.model_dump()
        intg_doc["created_at"] = intg_doc["created_at"].isoformat()

        await db.banks.update_one(
            {"bank_id": bank_id},
            {"$push": {"integrations": intg_doc}}
        )

        # Marcar como Promovido
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {"status": "Promovido", "promoted_integration_id": intg_doc["integration_id"], "promoted_at": datetime.now(timezone.utc).isoformat()}}
        )
        promoted = True
        logging.info(f"Hand-off ejecutado: producto '{product['service_name']}' insertado como integración '{intg_doc['integration_id']}' en banco '{product['bank_name']}'")
    else:
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {"status": new_status}}
        )

    updated = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if promoted:
        updated["_handoff"] = True
    return updated


# ==================== EVOLUTION LOG ====================

@router.get("/new-products/{product_id}/evolution")
async def get_evolution(product_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    entries = await db.new_product_evolution.find(
        {"product_id": product_id}, {"_id": 0}
    ).sort("date", -1).to_list(500)
    return entries


@router.post("/new-products/{product_id}/evolution")
async def add_evolution(product_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    entry = NewProductEvolutionEntry(
        product_id=product_id,
        comment=body.get("comment", ""),
        phase=body.get("phase", product.get("status", "Negociación")),
        date=body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    doc = entry.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.new_product_evolution.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/new-products/{product_id}/evolution/{entry_id}")
async def update_evolution(product_id: str, entry_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    update_fields = {}
    for field in ["comment", "phase", "date"]:
        if field in body:
            update_fields[field] = body[field]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.new_product_evolution.update_one(
        {"entry_id": entry_id, "product_id": product_id}, {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    updated = await db.new_product_evolution.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated


@router.delete("/new-products/{product_id}/evolution/{entry_id}")
async def delete_evolution(product_id: str, entry_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.new_product_evolution.delete_one({"entry_id": entry_id, "product_id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return {"message": "Entrada eliminada"}
