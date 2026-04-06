"""Route module: inventory.py — Módulo de Control de Inventarios Multialmacén"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import io

from config import db, get_current_user, UPLOADS_DIR
from models import Warehouse, WarehouseCreate, InventoryMovement, SERIALIZED_TYPES
from services.email_service import send_email
from services.transfer_note_pdf import generate_transfer_note_pdf

router = APIRouter()
logger = logging.getLogger(__name__)


def is_serialized(item_type: str) -> bool:
    """Determina si un tipo de ítem requiere serialización."""
    return (item_type or "").lower() in SERIALIZED_TYPES


async def validate_warehouse_jurisdiction(user: dict, warehouse_id: str):
    """Valida que el usuario tenga jurisdicción sobre el almacén.
    Admin puede operar en cualquier almacén.
    Usuarios normales solo pueden escribir en su almacén asignado."""
    if user.get("role") == "admin":
        return  # Admin bypass
    almacen_asignado = user.get("almacen_asignado")
    if not almacen_asignado:
        return  # Sin almacén asignado → no se restringe (backward compatible)
    if almacen_asignado != warehouse_id:
        raise HTTPException(
            status_code=403,
            detail="No tiene jurisdicción sobre este almacén. Solo puede modificar su almacén asignado."
        )


# ==================== WAREHOUSES ====================

@router.post("/inventory/warehouses")
async def create_warehouse(body: WarehouseCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)

    # Resolver responsable
    resp_name, resp_email = "", ""
    if body.responsible_user_id:
        user = await db.users.find_one({"user_id": body.responsible_user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="Usuario responsable no encontrado")
        resp_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        resp_email = user.get("email", "")

    wh = Warehouse(
        name=body.name, location=body.location, notes=body.notes,
        responsible_user_id=body.responsible_user_id,
        responsible_name=resp_name, responsible_email=resp_email,
    )
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
    current_user = await get_current_user(authorization)
    await validate_warehouse_jurisdiction(current_user, warehouse_id)
    update = {}
    for f in ["name", "location", "notes"]:
        if f in body:
            update[f] = body[f]

    # Resolver responsable si se actualiza
    if "responsible_user_id" in body:
        uid = body["responsible_user_id"]
        if uid:
            user = await db.users.find_one({"user_id": uid}, {"_id": 0})
            if not user:
                raise HTTPException(status_code=404, detail="Usuario responsable no encontrado")
            update["responsible_user_id"] = uid
            update["responsible_name"] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            update["responsible_email"] = user.get("email", "")
        else:
            update["responsible_user_id"] = ""
            update["responsible_name"] = ""
            update["responsible_email"] = ""

    if not update:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    result = await db.warehouses.update_one({"warehouse_id": warehouse_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")
    updated = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    return updated


@router.delete("/inventory/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    await validate_warehouse_jurisdiction(current_user, warehouse_id)
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
    """Calcula el saldo actual de cada ítem en un almacén. Excluye precargas del stock disponible."""
    await get_current_user(authorization)
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(10000)

    stock = {}  # item_id -> { name, type, qty, cost_total, serials[], precarga_qty, precarga_serials[] }
    serial_dates_map = {}  # item_id -> { serial -> acquisition_date }
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
                "precarga_qty": 0,
                "precarga_serials": [],
                "has_precarga": False,
                "precarga_movements": [],
            }
            serial_dates_map[iid] = {}

        is_precarga = m.get("certification_status") == "precarga"
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        acq_date = m.get("acquisition_date") or m.get("created_at", "")

        if is_precarga:
            stock[iid]["precarga_qty"] += m["quantity"]
            if m.get("serials"):
                stock[iid]["precarga_serials"].extend(m["serials"])
            stock[iid]["has_precarga"] = True
            stock[iid]["precarga_movements"].append({
                "movement_id": m["movement_id"],
                "quantity": m["quantity"],
                "serials": m.get("serials", []),
                "created_at": m.get("created_at", ""),
                "notes": m.get("notes", ""),
            })
        else:
            stock[iid]["quantity"] += sign * m["quantity"]
            stock[iid]["cost_total"] += sign * m["quantity"] * m.get("unit_cost", 0)
            if m.get("serials"):
                if sign > 0:
                    stock[iid]["serials"].extend(m["serials"])
                    for s in m["serials"]:
                        serial_dates_map[iid][s] = acq_date
                else:
                    for s in m["serials"]:
                        if s in stock[iid]["serials"]:
                            stock[iid]["serials"].remove(s)
                        serial_dates_map[iid].pop(s, None)

    # Excluir seriales preasignados/asignados del stock disponible
    blocked_assignments = await db.serial_assignments.find(
        {"status": {"$in": ["preasignado", "asignado"]}},
        {"_id": 0, "serial": 1}
    ).to_list(10000)
    blocked_serials = {b["serial"] for b in blocked_assignments}

    result = []
    for item in stock.values():
        # Filtrar seriales bloqueados
        if item["serials"]:
            original_count = len(item["serials"])
            item["serials"] = [s for s in item["serials"] if s not in blocked_serials]
            blocked_count = original_count - len(item["serials"])
            item["preassigned_count"] = blocked_count
        else:
            item["preassigned_count"] = 0
        qty = item["quantity"]
        item["weighted_cost"] = round(item["cost_total"] / qty, 2) if qty > 0 else 0
        # FIFO: ordenar seriales por fecha de adquisición más antigua
        iid = item["item_id"]
        dates = serial_dates_map.get(iid, {})
        item["serials"].sort(key=lambda s: dates.get(s, "9999"))
        result.append(item)

    result.sort(key=lambda x: x["item_name"])

    # Enrich with min_stock config
    min_configs = await db.min_stock_config.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).to_list(1000)
    min_map = {c["item_id"]: c.get("min_stock", 0) for c in min_configs}
    for item in result:
        item["min_stock"] = min_map.get(item["item_id"], 0)
        item["below_min"] = item["quantity"] <= item["min_stock"] and item["min_stock"] > 0

    return result


# ==================== INVENTORY ENTRIES ====================

@router.post("/inventory/warehouses/{warehouse_id}/entry")
async def create_entry(warehouse_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Registra entrada de inventario. Soporta modo 'precarga' (cuarentena técnica)."""
    user = await get_current_user(authorization)
    await validate_warehouse_jurisdiction(user, warehouse_id)

    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    item_id = body.get("item_id")
    quantity = body.get("quantity", 0)
    unit_cost = body.get("unit_cost", 0)
    serials = body.get("serials", [])
    notes = body.get("notes", "")
    is_precarga = body.get("is_precarga", False)
    acquisition_date = body.get("acquisition_date", "")

    if not item_id or quantity <= 0:
        raise HTTPException(status_code=400, detail="item_id y quantity > 0 son obligatorios")

    item = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado en Bienes y Servicios")

    requires_serial = is_serialized(item.get("type", ""))

    if requires_serial:
        if len(serials) != quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Para {item['type']}, debe registrar exactamente {quantity} serial(es). Recibidos: {len(serials)}"
            )
        for serial in serials:
            existing = await db.inventory_movements.find_one(
                {"serials": serial, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}},
                {"_id": 0, "movement_id": 1}
            )
            if existing:
                exits = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_type": {"$in": ["salida", "transferencia_salida"]}}
                )
                entries = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}}
                )
                if entries > exits:
                    raise HTTPException(status_code=400, detail=f"El serial '{serial}' ya existe en inventario")

    # certification_status: "precarga" (cuarentena) o "certificado" (disponible)
    cert_status = "precarga" if is_precarga else "certificado"

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
    doc["certification_status"] = cert_status
    doc["acquisition_date"] = acquisition_date
    await db.inventory_movements.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ==================== CERTIFICATION (VALIDATE & CERTIFY) ====================

@router.post("/inventory/validate-certification/{movement_id}")
async def validate_certification(movement_id: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Compara seriales de una precarga contra un Excel de certificación física."""
    import pandas as pd
    await get_current_user(authorization)

    mov = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.get("certification_status") != "precarga":
        raise HTTPException(status_code=400, detail="Este movimiento ya está certificado o no es una precarga")

    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), header=None)
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo")

    excel_serials = []
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if val and val.lower() not in ('nan', 'none', '', 'serial', 'seriales'):
            excel_serials.append(val)

    precarga_serials = set(mov.get("serials", []))
    excel_set = set(excel_serials)

    matching = sorted(precarga_serials & excel_set)
    only_in_precarga = sorted(precarga_serials - excel_set)
    only_in_excel = sorted(excel_set - precarga_serials)
    has_mismatch = bool(only_in_precarga or only_in_excel)

    return {
        "movement_id": movement_id,
        "item_name": mov.get("item_name", ""),
        "precarga_count": len(precarga_serials),
        "excel_count": len(excel_set),
        "matching": matching,
        "matching_count": len(matching),
        "only_in_precarga": only_in_precarga,
        "only_in_excel": only_in_excel,
        "has_mismatch": has_mismatch,
    }


@router.post("/inventory/certify/{movement_id}")
async def certify_movement(movement_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Certifica una precarga. source='excel' actualiza seriales, 'original' mantiene los actuales."""
    await get_current_user(authorization)

    mov = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.get("certification_status") != "precarga":
        raise HTTPException(status_code=400, detail="Este movimiento ya está certificado")

    source = body.get("source", "original")  # "excel" or "original"
    update_fields = {"certification_status": "certificado"}

    if source == "excel":
        excel_serials = body.get("excel_serials", [])
        if not excel_serials:
            raise HTTPException(status_code=400, detail="Debe proporcionar los seriales del Excel")
        # Validate no duplicates in system
        for serial in excel_serials:
            existing = await db.inventory_movements.find_one(
                {
                    "serials": serial,
                    "movement_id": {"$ne": movement_id},
                    "movement_type": {"$in": ["entrada", "transferencia_entrada"]},
                },
                {"_id": 0, "movement_id": 1},
            )
            if existing:
                exits = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_type": {"$in": ["salida", "transferencia_salida"]}}
                )
                entries = await db.inventory_movements.count_documents(
                    {"serials": serial, "movement_id": {"$ne": movement_id}, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}}
                )
                if entries > exits:
                    raise HTTPException(status_code=400, detail=f"El serial '{serial}' ya existe en otro registro de inventario")
        update_fields["serials"] = excel_serials
        update_fields["quantity"] = len(excel_serials)

    result = await db.inventory_movements.update_one(
        {"movement_id": movement_id},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    updated = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    return updated


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


@router.post("/inventory/validate-serials-stock/{warehouse_id}/{item_id}")
async def validate_serials_against_stock(
    warehouse_id: str, item_id: str,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Valida seriales de un Excel contra el stock disponible de un ítem en un almacén.
    Retorna seriales válidos, no encontrados y duplicados."""
    import pandas as pd
    await get_current_user(authorization)

    stock = await _get_item_stock(warehouse_id, item_id)
    available = set(stock.get("serials", []))

    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), header=None)
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(content), header=None)
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo")

    excel_serials = []
    for _, row in df.iterrows():
        val = str(row.iloc[0]).strip()
        if val and val.lower() not in ('nan', 'none', '', 'serial', 'seriales'):
            excel_serials.append(val)

    # Detect internal duplicates in Excel
    seen = {}
    internal_duplicates = []
    for row_num, s in enumerate(excel_serials):
        if s in seen:
            internal_duplicates.append({"serial": s, "row1": seen[s] + 1, "row2": row_num + 1})
        else:
            seen[s] = row_num

    excel_set = set(excel_serials)
    valid = sorted(excel_set & available)
    not_found = sorted(excel_set - available)
    has_errors = len(not_found) > 0 or len(internal_duplicates) > 0

    return {
        "warehouse_id": warehouse_id,
        "item_id": item_id,
        "available_count": len(available),
        "excel_count": len(excel_set),
        "valid": valid,
        "valid_count": len(valid),
        "not_found": not_found,
        "not_found_count": len(not_found),
        "internal_duplicates": internal_duplicates,
        "has_errors": has_errors,
    }


# ==================== MANUAL EXIT ====================

@router.post("/inventory/warehouses/{warehouse_id}/exit")
async def create_exit(warehouse_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Registra salida manual de inventario."""
    user = await get_current_user(authorization)
    await validate_warehouse_jurisdiction(user, warehouse_id)

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
        unit_cost=stock.get("weighted_cost", item.get("price_usd", 0)),
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

    # Trigger CheckStock alert
    await check_stock_alert(warehouse_id, item_id, item["name"])

    return doc


# ==================== TRANSFERS ====================

@router.post("/inventory/transfer")
async def transfer_between_warehouses(body: dict, authorization: Optional[str] = Header(None)):
    """Transferencia atómica entre almacenes. Seriales se mueven intactos."""
    user = await get_current_user(authorization)
    # Validar jurisdicción sobre el almacén origen
    source_id = body.get("source_warehouse_id")
    if source_id:
        await validate_warehouse_jurisdiction(user, source_id)
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
        unit_cost=source_stock.get("weighted_cost", 0),
        serials=serials if requires_serial else [],
        reference=f"Transferencia a {dst_wh['name']}",
        transfer_id=transfer_id, notes=notes, created_by=user_name,
    )
    exit_doc = exit_mov.model_dump()
    exit_doc["created_at"] = exit_doc["created_at"].isoformat()
    exit_doc["certification_status"] = "certificado"

    # Entrada al destino — en estado "precarga" (cuarentena técnica)
    entry_mov = InventoryMovement(
        warehouse_id=dest_id, item_id=item_id,
        item_name=item["name"], item_type=item.get("type", "General"),
        movement_type="transferencia_entrada", quantity=quantity,
        unit_cost=source_stock.get("weighted_cost", 0),
        serials=serials if requires_serial else [],
        reference=f"Transferencia desde {src_wh['name']}",
        transfer_id=transfer_id, notes=notes, created_by=user_name,
    )
    entry_doc = entry_mov.model_dump()
    entry_doc["created_at"] = entry_doc["created_at"].isoformat()
    entry_doc["certification_status"] = "precarga"

    # Insertar ambos atómicamente
    await db.inventory_movements.insert_many([exit_doc, entry_doc])
    # Clean _id
    exit_doc.pop("_id", None)
    entry_doc.pop("_id", None)

    # Trigger CheckStock en almacén origen (donde se redujo stock)
    await check_stock_alert(source_id, item_id, item["name"])

    # Generar PDF "Nota de Entrega por Transferencia"
    transfer_note_url = None
    try:
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)

        # Correlativo TRF-YYYY-XXXX
        year = datetime.now(timezone.utc).strftime("%Y")
        counter_doc = await db.transfer_note_counter.find_one_and_update(
            {"year": year},
            {"$inc": {"counter": 1}},
            upsert=True,
            return_document=True,
        )
        if counter_doc and "_id" in counter_doc:
            del counter_doc["_id"]
        trf_num = counter_doc.get("counter", 1) if counter_doc else 1
        transfer_number = f"TRF-{year}-{trf_num:04d}"

        # Source warehouse info
        src_wh_full = await db.warehouses.find_one({"warehouse_id": source_id}, {"_id": 0})
        dst_wh_full = await db.warehouses.find_one({"warehouse_id": dest_id}, {"_id": 0})
        source_resp_name = src_wh_full.get("responsible_name", "") if src_wh_full else ""
        source_resp_cedula = ""
        if src_wh_full and src_wh_full.get("responsible_user_id"):
            resp_user = await db.users.find_one({"user_id": src_wh_full["responsible_user_id"]}, {"_id": 0})
            if resp_user:
                source_resp_cedula = resp_user.get("cedula", "")
        dest_resp_name = dst_wh_full.get("responsible_name", "") if dst_wh_full else ""

        transferred_items_pdf = [{
            "name": item["name"],
            "type": item.get("type", "General"),
            "quantity": quantity,
            "serials": serials if requires_serial else [],
        }]

        pdf_buffer = generate_transfer_note_pdf(
            transfer_number=transfer_number,
            source_warehouse_name=src_wh_full.get("name", "") if src_wh_full else "",
            source_responsible_name=source_resp_name,
            source_responsible_cedula=source_resp_cedula,
            dest_warehouse_name=dst_wh_full.get("name", "") if dst_wh_full else "",
            dest_responsible_name=dest_resp_name,
            transferred_items=transferred_items_pdf,
            transferred_by=user_name,
            notes=notes,
            logo_path=logo_path,
        )
        pdf_filename = f"TransferenciaAlmacen_{transfer_number}.pdf"
        pdf_path = UPLOADS_DIR / pdf_filename
        with open(pdf_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        transfer_note_url = f"/uploads/{pdf_filename}"

        # Store the transfer_number and pdf_url in both movements
        await db.inventory_movements.update_many(
            {"transfer_id": transfer_id},
            {"$set": {"transfer_number": transfer_number, "transfer_note_url": transfer_note_url}},
        )

        logger.info(f"Nota de Transferencia generada: {transfer_note_url}")
    except Exception as e:
        logger.error(f"Error generando Nota de Transferencia: {e}")
        import traceback
        traceback.print_exc()

    return {
        "transfer_id": transfer_id,
        "transfer_number": transfer_number if transfer_note_url else None,
        "transfer_note_url": transfer_note_url,
        "exit": exit_doc,
        "entry": entry_doc,
    }


# ==================== MOVEMENTS HISTORY ====================

@router.get("/inventory/warehouses/{warehouse_id}/movements")
async def get_movements(warehouse_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    return movements


# ==================== KARDEX POR PRODUCTO ====================

@router.get("/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
async def get_kardex(warehouse_id: str, item_id: str, authorization: Optional[str] = Header(None)):
    """Kardex del producto: historial cronológico de movimientos con saldo resultante."""
    await get_current_user(authorization)

    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id, "item_id": item_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(10000)

    # Calcular saldo acumulado
    saldo = 0
    kardex = []
    for m in movements:
        is_precarga = m.get("certification_status") == "precarga"
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        if not is_precarga:
            saldo += sign * m["quantity"]
        kardex.append({
            "movement_id": m["movement_id"],
            "date": m.get("created_at", ""),
            "movement_type": m["movement_type"],
            "quantity": m["quantity"],
            "signed_qty": sign * m["quantity"],
            "saldo": saldo,
            "unit_cost": m.get("unit_cost", 0),
            "serials": m.get("serials", []),
            "reference": m.get("reference", ""),
            "client_name": m.get("client_name", ""),
            "client_id": m.get("client_id", ""),
            "quote_id": m.get("quote_id", ""),
            "quote_number": m.get("quote_number", ""),
            "notes": m.get("notes", ""),
            "created_by": m.get("created_by", ""),
            "certification_status": m.get("certification_status", "certificado"),
            "acquisition_date": m.get("acquisition_date", ""),
        })

    # Info del producto
    hw = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    item_name = hw.get("name", "") if hw else (movements[0]["item_name"] if movements else "")
    item_type = hw.get("type", "") if hw else (movements[0]["item_type"] if movements else "")

    return {
        "item_id": item_id,
        "item_name": item_name,
        "item_type": item_type,
        "warehouse_id": warehouse_id,
        "saldo_final": saldo,
        "movements": kardex,
    }


# ==================== DESTINO DE MOVIMIENTO ====================

@router.get("/inventory/movements/{movement_id}/destination")
async def get_movement_destination(movement_id: str, authorization: Optional[str] = Header(None)):
    """Retorna info de destino (cliente) para un movimiento de salida."""
    await get_current_user(authorization)

    mov = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    if mov["movement_type"] not in ("salida",):
        raise HTTPException(status_code=400, detail="Solo movimientos de salida tienen destinatario")

    client_id = mov.get("client_id", "")
    client = None
    if client_id:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})

    return {
        "movement_id": movement_id,
        "client_id": client_id,
        "client_name": client.get("fantasy_name") or client.get("legal_name", "") if client else mov.get("client_name", ""),
        "client_rif": client.get("rif", "") if client else "",
        "client_address": client.get("address", "") if client else "",
        "quote_id": mov.get("quote_id", ""),
        "quote_number": mov.get("quote_number", "") or mov.get("reference", ""),
        "serials": mov.get("serials", []),
        "item_name": mov.get("item_name", ""),
        "quantity": mov.get("quantity", 0),
        "date": mov.get("created_at", ""),
    }


# ==================== BUSCADOR INVERSO POR CLIENTE ====================

@router.get("/inventory/movements/search")
async def search_movements_by_client(client_name: str = "", authorization: Optional[str] = Header(None)):
    """Buscar movimientos de salida por nombre de cliente."""
    await get_current_user(authorization)

    if not client_name or len(client_name) < 2:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos 2 caracteres del nombre del cliente")

    query = {
        "movement_type": "salida",
        "client_name": {"$regex": client_name, "$options": "i"},
    }
    movements = await db.inventory_movements.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)

    return movements


# ==================== MIN STOCK CONFIG ====================

@router.put("/inventory/warehouses/{warehouse_id}/min-stock/{item_id}")
async def set_min_stock(warehouse_id: str, item_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Define el stock mínimo para un ítem en un almacén."""
    current_user = await get_current_user(authorization)
    await validate_warehouse_jurisdiction(current_user, warehouse_id)

    min_stock = body.get("min_stock", 0)
    if not isinstance(min_stock, (int, float)) or min_stock < 0:
        raise HTTPException(status_code=400, detail="Stock mínimo no puede ser negativo")

    min_stock = int(min_stock)

    await db.min_stock_config.update_one(
        {"warehouse_id": warehouse_id, "item_id": item_id},
        {"$set": {
            "warehouse_id": warehouse_id,
            "item_id": item_id,
            "min_stock": min_stock,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"warehouse_id": warehouse_id, "item_id": item_id, "min_stock": min_stock}


@router.get("/inventory/warehouses/{warehouse_id}/min-stock")
async def get_min_stock_config(warehouse_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene toda la configuración de stock mínimo para un almacén."""
    await get_current_user(authorization)
    configs = await db.min_stock_config.find({"warehouse_id": warehouse_id}, {"_id": 0}).to_list(500)
    return configs


# ==================== HELPERS ====================

async def check_stock_alert(warehouse_id: str, item_id: str, item_name: str):
    """Verifica si el stock actual es <= al mínimo configurado y envía alerta por email."""
    try:
        config = await db.min_stock_config.find_one(
            {"warehouse_id": warehouse_id, "item_id": item_id}, {"_id": 0}
        )
        if not config or config.get("min_stock", 0) <= 0:
            return  # No hay mínimo configurado

        min_stock = config["min_stock"]
        stock = await _get_item_stock(warehouse_id, item_id)
        current_qty = stock["quantity"]

        if current_qty <= min_stock:
            wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
            if not wh:
                return

            wh_name = wh.get("name", "")
            resp_name = wh.get("responsible_name", "Responsable")
            resp_email = wh.get("responsible_email", "")

            if not resp_email:
                logger.warning(f"Alerta stock mínimo: No hay email de responsable para almacén '{wh_name}'")
                return

            subject = f"ALERTA: Stock Minimo Alcanzado - {wh_name}"
            html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #DC2626; color: white; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                    <h2 style="margin: 0;">Alerta de Reabastecimiento</h2>
                </div>
                <div style="padding: 24px; border: 1px solid #E5E7EB; border-top: 0; border-radius: 0 0 8px 8px;">
                    <p>Hola <strong>{resp_name}</strong>,</p>
                    <p>Te informamos que el siguiente item ha alcanzado o superado su nivel de stock critico:</p>
                    <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                        <tr style="background: #FEF2F2;">
                            <td style="padding: 10px; border: 1px solid #FECACA; font-weight: bold;">Item:</td>
                            <td style="padding: 10px; border: 1px solid #FECACA;">{item_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #E5E7EB; font-weight: bold;">Almacen:</td>
                            <td style="padding: 10px; border: 1px solid #E5E7EB;">{wh_name}</td>
                        </tr>
                        <tr style="background: #FEF2F2;">
                            <td style="padding: 10px; border: 1px solid #FECACA; font-weight: bold; color: #DC2626;">Stock Actual:</td>
                            <td style="padding: 10px; border: 1px solid #FECACA; font-weight: bold; color: #DC2626; font-size: 18px;">{current_qty}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #E5E7EB; font-weight: bold;">Minimo Definido:</td>
                            <td style="padding: 10px; border: 1px solid #E5E7EB;">{min_stock}</td>
                        </tr>
                    </table>
                    <p>Por favor, gestiona el reabastecimiento con el departamento de compras para evitar interrupciones en las entregas.</p>
                    <hr style="border: 0; border-top: 1px solid #E5E7EB; margin: 16px 0;" />
                    <p style="color: #6B7280; font-size: 12px;">Este es un mensaje automatico del sistema de inventarios.</p>
                </div>
            </div>
            """
            await send_email(
                to=[resp_email],
                subject=subject,
                html=html,
                action="stock_alert",
            )
            logger.info(f"Alerta de stock mínimo enviada: {item_name} en {wh_name} (actual: {current_qty}, min: {min_stock})")
    except Exception as e:
        logger.error(f"Error en check_stock_alert: {e}")

async def _get_item_stock(warehouse_id: str, item_id: str) -> dict:
    """Calcula stock actual de un ítem en un almacén. Excluye precargas. Seriales ordenados FIFO."""
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id, "item_id": item_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(10000)

    qty = 0
    cost_total = 0
    serials = []
    serial_dates = {}  # serial -> acquisition_date (para FIFO)
    for m in movements:
        # Excluir precargas del stock disponible
        if m.get("certification_status") == "precarga":
            continue
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        qty += sign * m["quantity"]
        cost_total += sign * m["quantity"] * m.get("unit_cost", 0)
        acq_date = m.get("acquisition_date") or m.get("created_at", "")
        if m.get("serials"):
            if sign > 0:
                serials.extend(m["serials"])
                for s in m["serials"]:
                    serial_dates[s] = acq_date
            else:
                for s in m["serials"]:
                    if s in serials:
                        serials.remove(s)
                    serial_dates.pop(s, None)

    # Ordenar seriales por fecha de adquisición (FIFO: más antiguos primero)
    serials.sort(key=lambda s: serial_dates.get(s, "9999"))

    return {
        "quantity": qty,
        "cost_total": cost_total,
        "weighted_cost": round(cost_total / qty, 2) if qty > 0 else 0,
        "serials": serials,
        "serial_dates": serial_dates,
    }
