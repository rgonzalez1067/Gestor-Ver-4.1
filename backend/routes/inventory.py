"""Route module: inventory.py — Módulo de Control de Inventarios Multialmacén"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import io

from config import db, get_current_user
from models import Warehouse, WarehouseCreate, InventoryMovement, SERIALIZED_TYPES

router = APIRouter()


def is_serialized(item_type: str) -> bool:
    """Determina si un tipo de ítem requiere serialización."""
    return (item_type or "").lower() in SERIALIZED_TYPES


# ==================== WAREHOUSES ====================

@router.post("/inventory/warehouses")
async def create_warehouse(body: WarehouseCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    wh = Warehouse(name=body.name, location=body.location, notes=body.notes)
    doc = wh.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.warehouses.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/inventory/warehouses")
async def list_warehouses(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    warehouses = await db.warehouses.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    return warehouses


@router.put("/inventory/warehouses/{warehouse_id}")
async def update_warehouse(warehouse_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    update = {}
    for f in ["name", "location", "notes"]:
        if f in body:
            update[f] = body[f]
    if not update:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    result = await db.warehouses.update_one({"warehouse_id": warehouse_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")
    updated = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    return updated


@router.delete("/inventory/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    count = await db.inventory_movements.count_documents({"warehouse_id": warehouse_id})
    if count > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar un almacén con movimientos registrados")
    result = await db.warehouses.delete_one({"warehouse_id": warehouse_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")
    return {"message": "Almacén eliminado"}


# ==================== STOCK VIEW ====================

@router.get("/inventory/warehouses/{warehouse_id}/stock")
async def get_warehouse_stock(warehouse_id: str, authorization: Optional[str] = Header(None)):
    """Calcula el saldo actual de cada ítem en un almacén."""
    await get_current_user(authorization)
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).to_list(10000)

    stock = {}  # item_id -> { name, type, qty, cost_total, serials[] }
    for m in movements:
        iid = m["item_id"]
        if iid not in stock:
            stock[iid] = {
                "item_id": iid,
                "item_name": m["item_name"],
                "item_type": m["item_type"],
                "quantity": 0,
                "cost_total": 0,
                "serials": [],
                "requires_serial": is_serialized(m["item_type"]),
            }
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        stock[iid]["quantity"] += sign * m["quantity"]
        stock[iid]["cost_total"] += sign * m["quantity"] * m.get("unit_cost", 0)

        if m.get("serials"):
            if sign > 0:
                stock[iid]["serials"].extend(m["serials"])
            else:
                for s in m["serials"]:
                    if s in stock[iid]["serials"]:
                        stock[iid]["serials"].remove(s)

    result = []
    for item in stock.values():
        qty = item["quantity"]
        item["avg_cost"] = round(item["cost_total"] / qty, 2) if qty > 0 else 0
        result.append(item)

    result.sort(key=lambda x: x["item_name"])
    return result


# ==================== INVENTORY ENTRIES ====================

@router.post("/inventory/warehouses/{warehouse_id}/entry")
async def create_entry(warehouse_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Registra entrada de inventario. Para hardware crítico, valida seriales."""
    user = await get_current_user(authorization)

    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    item_id = body.get("item_id")
    quantity = body.get("quantity", 0)
    unit_cost = body.get("unit_cost", 0)
    serials = body.get("serials", [])
    notes = body.get("notes", "")

    if not item_id or quantity <= 0:
        raise HTTPException(status_code=400, detail="item_id y quantity > 0 son obligatorios")

    # Buscar el ítem en Bienes y Servicios
    item = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado en Bienes y Servicios")

    requires_serial = is_serialized(item.get("type", ""))

    # Validar seriales para hardware crítico
    if requires_serial:
        if len(serials) != quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Para {item['type']}, debe registrar exactamente {quantity} serial(es). Recibidos: {len(serials)}"
            )
        # Verificar que los seriales no estén duplicados en ningún almacén
        for serial in serials:
            existing = await db.inventory_movements.find_one(
                {"serials": serial, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}},
                {"_id": 0, "movement_id": 1}
            )
            if existing:
                # Verificar que no esté activo (podría haber salido)
                exits = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_type": {"$in": ["salida", "transferencia_salida"]}}
                )
                entries = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}}
                )
                if entries > exits:
                    raise HTTPException(status_code=400, detail=f"El serial '{serial}' ya existe en inventario")

    movement = InventoryMovement(
        warehouse_id=warehouse_id,
        item_id=item_id,
        item_name=item["name"],
        item_type=item.get("type", "General"),
        movement_type="entrada",
        quantity=quantity,
        unit_cost=unit_cost or item.get("price_usd", 0),
        serials=serials if requires_serial else [],
        notes=notes,
        created_by=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
    )
    doc = movement.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.inventory_movements.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ==================== PARSE SERIALS FROM EXCEL ====================

@router.post("/inventory/parse-serials")
async def parse_serials_from_excel(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Extrae seriales de un archivo Excel (columna única)."""
    await get_current_user(authorization)
    import pandas as pd
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), header=None)
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo")

    serials = []
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if val and val.lower() not in ('nan', 'none', '', 'serial', 'seriales'):
            serials.append(val)

    return {"serials": serials, "count": len(serials)}


# ==================== MANUAL EXIT ====================

@router.post("/inventory/warehouses/{warehouse_id}/exit")
async def create_exit(warehouse_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Registra salida manual de inventario."""
    user = await get_current_user(authorization)

    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    item_id = body.get("item_id")
    quantity = body.get("quantity", 0)
    serials = body.get("serials", [])
    reference = body.get("reference", "")
    client_name = body.get("client_name", "")
    notes = body.get("notes", "")

    if not item_id or quantity <= 0:
        raise HTTPException(status_code=400, detail="item_id y quantity > 0 son obligatorios")

    item = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    requires_serial = is_serialized(item.get("type", ""))

    # Validar stock suficiente
    stock = await _get_item_stock(warehouse_id, item_id)
    if stock["quantity"] < quantity:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {stock['quantity']}, Solicitado: {quantity}")

    if requires_serial:
        if len(serials) != quantity:
            raise HTTPException(status_code=400, detail=f"Debe seleccionar exactamente {quantity} serial(es)")
        # Validar que los seriales estén disponibles en este almacén
        for s in serials:
            if s not in stock.get("serials", []):
                raise HTTPException(status_code=400, detail=f"Serial '{s}' no disponible en este almacén")

    movement = InventoryMovement(
        warehouse_id=warehouse_id,
        item_id=item_id,
        item_name=item["name"],
        item_type=item.get("type", "General"),
        movement_type="salida",
        quantity=quantity,
        unit_cost=stock.get("avg_cost", item.get("price_usd", 0)),
        serials=serials if requires_serial else [],
        reference=reference,
        client_name=client_name,
        notes=notes,
        created_by=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
    )
    doc = movement.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.inventory_movements.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ==================== TRANSFERS ====================

@router.post("/inventory/transfer")
async def transfer_between_warehouses(body: dict, authorization: Optional[str] = Header(None)):
    """Transferencia atómica entre almacenes. Seriales se mueven intactos."""
    user = await get_current_user(authorization)

    source_id = body.get("source_warehouse_id")
    dest_id = body.get("dest_warehouse_id")
    item_id = body.get("item_id")
    quantity = body.get("quantity", 0)
    serials = body.get("serials", [])
    notes = body.get("notes", "")

    if not all([source_id, dest_id, item_id]) or quantity <= 0:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios")
    if source_id == dest_id:
        raise HTTPException(status_code=400, detail="Origen y destino no pueden ser iguales")

    for wid in [source_id, dest_id]:
        wh = await db.warehouses.find_one({"warehouse_id": wid}, {"_id": 0})
        if not wh:
            raise HTTPException(status_code=404, detail=f"Almacén {wid} no encontrado")

    item = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    requires_serial = is_serialized(item.get("type", ""))
    source_stock = await _get_item_stock(source_id, item_id)

    if source_stock["quantity"] < quantity:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente en origen. Disponible: {source_stock['quantity']}")

    if requires_serial:
        if len(serials) != quantity:
            raise HTTPException(status_code=400, detail=f"Debe seleccionar exactamente {quantity} serial(es)")
        for s in serials:
            if s not in source_stock.get("serials", []):
                raise HTTPException(status_code=400, detail=f"Serial '{s}' no disponible en almacén origen")

    transfer_id = f"txf_{uuid.uuid4().hex[:8]}"
    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    src_wh = await db.warehouses.find_one({"warehouse_id": source_id}, {"_id": 0, "name": 1})
    dst_wh = await db.warehouses.find_one({"warehouse_id": dest_id}, {"_id": 0, "name": 1})

    # Salida del origen
    exit_mov = InventoryMovement(
        warehouse_id=source_id, item_id=item_id,
        item_name=item["name"], item_type=item.get("type", "General"),
        movement_type="transferencia_salida", quantity=quantity,
        unit_cost=source_stock.get("avg_cost", 0),
        serials=serials if requires_serial else [],
        reference=f"Transferencia a {dst_wh['name']}",
        transfer_id=transfer_id, notes=notes, created_by=user_name,
    )
    exit_doc = exit_mov.model_dump()
    exit_doc["created_at"] = exit_doc["created_at"].isoformat()

    # Entrada al destino
    entry_mov = InventoryMovement(
        warehouse_id=dest_id, item_id=item_id,
        item_name=item["name"], item_type=item.get("type", "General"),
        movement_type="transferencia_entrada", quantity=quantity,
        unit_cost=source_stock.get("avg_cost", 0),
        serials=serials if requires_serial else [],
        reference=f"Transferencia desde {src_wh['name']}",
        transfer_id=transfer_id, notes=notes, created_by=user_name,
    )
    entry_doc = entry_mov.model_dump()
    entry_doc["created_at"] = entry_doc["created_at"].isoformat()

    # Insertar ambos atómicamente
    await db.inventory_movements.insert_many([exit_doc, entry_doc])
    # Clean _id
    exit_doc.pop("_id", None)
    entry_doc.pop("_id", None)

    return {"transfer_id": transfer_id, "exit": exit_doc, "entry": entry_doc}


# ==================== MOVEMENTS HISTORY ====================

@router.get("/inventory/warehouses/{warehouse_id}/movements")
async def get_movements(warehouse_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    return movements


# ==================== HELPERS ====================

async def _get_item_stock(warehouse_id: str, item_id: str) -> dict:
    """Calcula stock actual de un ítem en un almacén."""
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id, "item_id": item_id}, {"_id": 0}
    ).to_list(10000)

    qty = 0
    cost_total = 0
    serials = []
    for m in movements:
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        qty += sign * m["quantity"]
        cost_total += sign * m["quantity"] * m.get("unit_cost", 0)
        if m.get("serials"):
            if sign > 0:
                serials.extend(m["serials"])
            else:
                for s in m["serials"]:
                    if s in serials:
                        serials.remove(s)

    return {
        "quantity": qty,
        "cost_total": cost_total,
        "avg_cost": round(cost_total / qty, 2) if qty > 0 else 0,
        "serials": serials,
    }
