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
from services.pdf_storage import save_pdf_dual

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


async def _warehouse_is_lch(warehouse_id: str) -> bool:
    """Heurística para identificar el almacén Los Chaguaramos (Corporativo).
    Cubre el caso donde el nombre cambia ligeramente entre ambientes.
    """
    if not warehouse_id:
        return False
    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0, "name": 1})
    if not wh:
        return False
    name = (wh.get("name") or "").lower()
    return ("chaguaramos" in name) or ("corporativo" in name) or name.endswith(" lch")


async def validate_lch_corp_dispatch(user: dict, warehouse_id: str):
    """Bloquea salidas/despachos del Almacén Los Chaguaramos cuando el usuario
    no pertenece a la sede Corp. Admin bypass.

    Aplica a: salidas manuales, transferencias salida, asignaciones temporales
    y cualquier operación que reduzca el stock físico del LCH.
    """
    if user.get("role") == "admin":
        return
    if not await _warehouse_is_lch(warehouse_id):
        return
    sede = (user.get("sede") or "").upper()
    if sede != "CORP":
        raise HTTPException(
            status_code=403,
            detail="Operación rechazada. El Almacén Los Chaguaramos está restringido exclusivamente para usuarios del segmento Corp.",
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


@router.delete("/inventory/movements/{movement_id}")
async def delete_movement(movement_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar un movimiento de inventario. Solo administradores."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar movimientos")
    result = await db.inventory_movements.delete_one({"movement_id": movement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return {"message": "Movimiento eliminado"}


# ==================== EDICIÓN MANUAL DE MOVIMIENTOS (ADMIN-ONLY) ====================
# Caso de uso: arranque del sistema / corrección de data legacy. El admin puede
# editar cualquier campo del movimiento. Cada cambio queda registrado en
# `inventory_movement_audits` para trazabilidad.

# Campos prohibidos (identificadores estructurales / derivados)
_MOVEMENT_PROTECTED_FIELDS = {"movement_id", "_id", "created_at", "created_by"}


@router.put("/inventory/movements/{movement_id}")
async def update_movement(
    movement_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Edición libre de un movimiento (solo admin).
    Pensado para corrección de carga inicial. Registra audit trail con
    valores antes/después de cada campo modificado."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden editar movimientos")

    movement = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    if not movement:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    # Filtrar campos protegidos y construir diff
    incoming = {k: v for k, v in (body or {}).items() if k not in _MOVEMENT_PROTECTED_FIELDS}
    if not incoming:
        raise HTTPException(status_code=400, detail="No se enviaron campos editables")

    changes = {}
    for key, new_val in incoming.items():
        old_val = movement.get(key)
        # Normaliza serials list (acepta string CSV o lista)
        if key == "serials" and isinstance(new_val, str):
            new_val = [s.strip() for s in new_val.split(",") if s.strip()]
        # Normaliza cantidad/costo a número
        if key == "quantity" and new_val is not None:
            try:
                new_val = int(new_val)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="quantity debe ser numérico")
        if key == "unit_cost" and new_val is not None:
            try:
                new_val = float(new_val)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="unit_cost debe ser numérico")
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}

    if not changes:
        return {"message": "Sin cambios", "movement_id": movement_id, "changes_count": 0}

    # Aplicar cambios al documento
    update_payload = {k: v["new"] for k, v in changes.items()}
    update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_payload["last_edited_by"] = current_user.get("user_id", "")
    update_payload["last_edited_by_name"] = (
        f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        or current_user.get("email", "")
    )
    await db.inventory_movements.update_one(
        {"movement_id": movement_id}, {"$set": update_payload}
    )

    # Registrar audit log
    audit_doc = {
        "audit_id": f"aud_{uuid.uuid4().hex[:10]}",
        "movement_id": movement_id,
        "warehouse_id": movement.get("warehouse_id"),
        "item_id": movement.get("item_id"),
        "item_name": movement.get("item_name"),
        "edited_by": current_user.get("user_id", ""),
        "edited_by_name": update_payload["last_edited_by_name"],
        "edited_by_email": current_user.get("email", ""),
        "edited_at": datetime.now(timezone.utc).isoformat(),
        "changes": changes,
    }
    await db.inventory_movement_audits.insert_one(audit_doc)
    audit_doc.pop("_id", None)

    updated = await db.inventory_movements.find_one({"movement_id": movement_id}, {"_id": 0})
    logger.info(
        f"[inventory] Movement {movement_id} edited by {current_user.get('email')} "
        f"changes={list(changes.keys())}"
    )
    return {
        "message": "Movimiento actualizado",
        "movement": updated,
        "changes_count": len(changes),
        "audit": audit_doc,
    }


@router.get("/inventory/movements/{movement_id}/audit")
async def get_movement_audit(
    movement_id: str, authorization: Optional[str] = Header(None)
):
    """Historial de ediciones de un movimiento. Solo admin."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver auditoría")
    cursor = db.inventory_movement_audits.find(
        {"movement_id": movement_id}, {"_id": 0}
    ).sort("edited_at", -1)
    audits = [a async for a in cursor]
    return {"movement_id": movement_id, "total": len(audits), "audits": audits}



# ==================== STOCK VIEW ====================

@router.get("/inventory/warehouses/{warehouse_id}/stock")
async def get_warehouse_stock(warehouse_id: str, authorization: Optional[str] = Header(None)):
    """Calcula el saldo actual de cada ítem en un almacén. Excluye precargas del stock disponible."""
    await get_current_user(authorization)
    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(2000)

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
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada", "entrada_temporal") else -1
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
    # (incluye asignaciones temporales para que no aparezcan como disponibles)
    blocked_assignments = await db.serial_assignments.find(
        {"status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
        {"_id": 0, "serial": 1, "status": 1, "quote_number": 1, "client_name": 1, "item_id": 1, "responsible_name": 1, "assignment_id_ref": 1}
    ).to_list(2000)
    blocked_serials = {b["serial"] for b in blocked_assignments}
    blocked_details = {b["serial"]: b for b in blocked_assignments}

    result = []
    for item in stock.values():
        iid = item["item_id"]
        # Separar seriales disponibles vs preasignados
        if item["serials"]:
            available = []
            preassigned_list = []
            for s in item["serials"]:
                if s in blocked_serials:
                    detail = blocked_details.get(s, {})
                    preassigned_list.append({
                        "serial": s,
                        "status": detail.get("status", "preasignado"),
                        "quote_number": detail.get("quote_number", ""),
                        "client_name": detail.get("client_name", ""),
                    })
                else:
                    available.append(s)
            item["serials"] = available
            item["preassigned_count"] = len(preassigned_list)
            item["preassigned_serials"] = preassigned_list
        else:
            item["preassigned_count"] = 0
            item["preassigned_serials"] = []
        qty = item["quantity"]
        item["weighted_cost"] = round(item["cost_total"] / qty, 2) if qty > 0 else 0
        # FIFO: ordenar seriales por fecha de adquisición más antigua
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
    doc["supplier"] = (body.get("supplier", "") or "")[:30]
    doc["invoice_ref"] = (body.get("invoice_ref", "") or "")[:20]
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
    await validate_lch_corp_dispatch(user, warehouse_id)

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
        # Transferencia desde LCH es un despacho físico → aplica restricción Corp.
        await validate_lch_corp_dispatch(user, source_id)
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
        save_pdf_dual(pdf_path, pdf_buffer.getvalue(), pdf_filename)
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
    ).sort("created_at", 1).to_list(2000)

    # Calcular saldo acumulado
    saldo = 0
    kardex = []
    for m in movements:
        is_precarga = m.get("certification_status") == "precarga"
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada", "entrada_temporal") else -1
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
    ).sort("created_at", 1).to_list(2000)

    qty = 0
    cost_total = 0
    serials = []
    serial_dates = {}  # serial -> acquisition_date (para FIFO)
    for m in movements:
        # Excluir precargas del stock disponible
        if m.get("certification_status") == "precarga":
            continue
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada", "entrada_temporal") else -1
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


@router.get("/inventory/accounting-report")
async def get_accounting_report(authorization: Optional[str] = Header(None)):
    """Reporte Contable de Inventarios — Costo Promedio Ponderado (CPP).
    Calcula el Kardex histórico por ítem con CPP dinámico."""
    await get_current_user(authorization)
    
    # Obtener todos los movimientos ordenados cronológicamente
    movements = await db.inventory_movements.find(
        {}, {"_id": 0}
    ).sort("created_at", 1).to_list(2000)
    
    # Agrupar movimientos por item_id
    items_map = {}  # item_id -> { name, type, movements[] }
    for m in movements:
        iid = m.get("item_id", "unknown")
        if iid not in items_map:
            items_map[iid] = {
                "item_id": iid,
                "item_name": m.get("item_name", "Sin nombre"),
                "item_type": m.get("item_type", ""),
                "movements": []
            }
        items_map[iid]["movements"].append({
            "date": m.get("acquisition_date") or (m.get("created_at", "")[:10] if isinstance(m.get("created_at"), str) else ""),
            "movement_type": m.get("movement_type", "entrada"),
            "quantity": m.get("quantity", 0),
            "unit_cost": m.get("unit_cost", 0),
            "warehouse_name": m.get("warehouse_name", ""),
            "warehouse_id": m.get("warehouse_id", ""),
            "reference": m.get("reference", ""),
            "supplier": m.get("supplier", ""),
            "invoice_ref": m.get("invoice_ref", ""),
            "notes": m.get("notes", ""),
            "created_by": m.get("created_by", ""),
            "created_at": m.get("created_at", ""),
        })
    
    # Calcular CPP para cada item
    report_items = []
    grand_total = 0
    
    for iid, item_data in items_map.items():
        current_qty = 0
        current_value = 0
        current_cpp = 0
        kardex_rows = []
        
        for mov in item_data["movements"]:
            qty = mov["quantity"]
            is_entrada = mov["movement_type"] in ("entrada", "transferencia_entrada", "entrada_temporal")
            
            if is_entrada:
                batch_value = qty * mov["unit_cost"]
                current_value += batch_value
                current_qty += qty
                current_cpp = round(current_value / current_qty, 2) if current_qty > 0 else 0
                kardex_rows.append({
                    **mov,
                    "type_label": "ENTRADA",
                    "cost_used": mov["unit_cost"],
                    "subtotal": round(batch_value, 2),
                    "balance_qty": current_qty,
                    "balance_value": round(current_value, 2),
                    "cpp": current_cpp,
                })
            else:
                exit_cost = current_cpp
                exit_value = round(qty * exit_cost, 2)
                current_qty -= qty
                current_value -= exit_value
                if current_qty < 0:
                    current_qty = 0
                    current_value = 0
                kardex_rows.append({
                    **mov,
                    "type_label": "SALIDA",
                    "cost_used": round(exit_cost, 2),
                    "subtotal": round(exit_value, 2),
                    "balance_qty": current_qty,
                    "balance_value": round(current_value, 2),
                    "cpp": current_cpp,
                })
        
        total_value = round(current_qty * current_cpp, 2) if current_qty > 0 else 0
        grand_total += total_value
        
        report_items.append({
            "item_id": iid,
            "item_name": item_data["item_name"],
            "item_type": item_data["item_type"],
            "kardex": kardex_rows,
            "current_qty": current_qty,
            "current_cpp": current_cpp,
            "total_value": total_value,
        })
    
    return {
        "report_date": datetime.now(timezone.utc).isoformat(),
        "items": report_items,
        "grand_total": round(grand_total, 2),
        "total_items": len(report_items),
    }



# ==================== REPORTE MAYOR DE ACTIVOS (PEPS / FIFO) ====================

@router.get("/inventory/asset-ledger")
async def get_asset_ledger(authorization: Optional[str] = Header(None)):
    """Reporte Mayor de Activos — Valoración PEPS (FIFO).

    Reglas:
    - Incluye TODAS las entradas a cualquier almacén (algunos ítems como POS y
      PinPads del segmento Pyme se reciben directamente en TBP sin pasar por
      LCH; antes se filtraba `warehouse_id = lch_id` lo que los excluía).
    - Transferencias NO son salidas reales, solo movimientos físicos.
    - Salidas reales (ventas) se descuentan del lote más antiguo por item.
    - Solo muestra lotes con saldo > 0.
    """
    await get_current_user(authorization)

    # Identificar almacenes para el desglose por bodega
    warehouses = await db.warehouses.find({}, {"_id": 0}).to_list(50)
    lch_id = None
    tbp_id = None
    # Heurística mejorada para identificar LCH (Los Chaguaramos / Corporativo)
    # y TBP (Torre Banco Plaza / Pyme). Antes el match de TBP era demasiado
    # permisivo (`banco|plaza|tbp|pyme`) y podía agarrar el equivocado.
    for wh in warehouses:
        name_lower = (wh.get("name", "") or "").lower()
        if lch_id is None and ("chaguaramos" in name_lower or "lch" in name_lower or "corporativ" in name_lower):
            lch_id = wh["warehouse_id"]
        if tbp_id is None and ("torre banco" in name_lower or "tbp" in name_lower or "pyme" in name_lower):
            tbp_id = wh["warehouse_id"]
    # Fallback: si solo hay 1 almacén lo asignamos a LCH.
    if not lch_id and warehouses:
        lch_id = warehouses[0]["warehouse_id"]

    # FIX (bug crítico): NO filtramos por warehouse_id — POS/PinPads del
    # segmento Pyme entran directamente al TBP y antes quedaban excluidos.
    all_entries = await db.inventory_movements.find(
        {"movement_type": "entrada"}, {"_id": 0}
    ).sort("acquisition_date", 1).to_list(5000)

    # Obtener TODAS las salidas reales (NO transferencias)
    all_exits = await db.inventory_movements.find(
        {"movement_type": "salida"}, {"_id": 0}
    ).sort("created_at", 1).to_list(5000)
    
    # Agrupar por (item_id, warehouse_id) — FIFO SEGMENTADO POR ALMACÉN.
    # Cada almacén mantiene su propia capa de inventario. Una salida del
    # almacén X descuenta exclusivamente de los lotes ingresados a X (nunca
    # mezcla con LCH u otros). Esto preserva la integridad financiera del
    # Mayor de Activos cuando el mismo SKU tiene costos distintos por sede.
    items_entries = {}  # (item_id, warehouse_id) -> {item_name, item_type, lots:[]}
    item_master = {}    # item_id -> (item_name, item_type) para el reporte final
    for entry in all_entries:
        iid = entry.get("item_id", "unknown")
        wid = entry.get("warehouse_id", "")
        key = (iid, wid)
        if key not in items_entries:
            items_entries[key] = {
                "item_name": entry.get("item_name", "Sin nombre"),
                "item_type": entry.get("item_type", ""),
                "warehouse_id": wid,
                "lots": [],
            }
        if iid not in item_master:
            item_master[iid] = (entry.get("item_name", "Sin nombre"), entry.get("item_type", ""))
        items_entries[key]["lots"].append({
            "movement_id": entry.get("movement_id", ""),
            "purchase_date": entry.get("acquisition_date") or (entry.get("created_at", "")[:10] if isinstance(entry.get("created_at"), str) else ""),
            "supplier": entry.get("supplier", ""),
            "invoice_ref": entry.get("invoice_ref", ""),
            "quantity_purchased": entry.get("quantity", 0),
            "unit_cost": entry.get("unit_cost", 0),
            "remaining": entry.get("quantity", 0),
            "warehouse_id": wid,
            "created_at": entry.get("created_at", ""),
        })

    # Agrupar salidas por (item_id, warehouse_id) — SOLO descuentan del
    # almacén donde se generó la salida.
    exits_by_key = {}
    for ex in all_exits:
        iid = ex.get("item_id", "unknown")
        wid = ex.get("warehouse_id", "")
        key = (iid, wid)
        exits_by_key.setdefault(key, []).append(ex.get("quantity", 0))

    # Ordenar lotes por fecha (PEPS) DENTRO de cada (item, warehouse).
    for key in items_entries:
        items_entries[key]["lots"].sort(
            key=lambda l: l.get("purchase_date") or l.get("created_at") or ""
        )

    # Aplicar PEPS segmentado: la salida de un almacén descuenta sólo de
    # los lotes ingresados a ese mismo almacén.
    for key, exit_list in exits_by_key.items():
        if key not in items_entries:
            # Salida sin entrada previa en el mismo almacén → log y skip.
            # No descontamos de otros almacenes (eso era el bug).
            continue
        total_to_deduct = sum(exit_list)
        for lot in items_entries[key]["lots"]:
            if total_to_deduct <= 0:
                break
            deduct = min(lot["remaining"], total_to_deduct)
            lot["remaining"] -= deduct
            total_to_deduct -= deduct
    
    # Construir reporte: solo lotes con saldo > 0
    # Calcular stock actual por almacén para cada item
    all_movements = await db.inventory_movements.find({}, {"_id": 0, "item_id": 1, "warehouse_id": 1, "movement_type": 1, "quantity": 1}).to_list(10000)
    
    # Mapear warehouses por ID
    wh_map = {w["warehouse_id"]: w.get("name", "") for w in warehouses}

    # Calcular stock por almacén por item
    stock_by_wh = {}  # item_id -> {warehouse_id -> qty}
    for m in all_movements:
        iid = m.get("item_id", "")
        wid = m.get("warehouse_id", "")
        mtype = m.get("movement_type", "")
        qty = m.get("quantity", 0)
        
        if iid not in stock_by_wh:
            stock_by_wh[iid] = {}
        if wid not in stock_by_wh[iid]:
            stock_by_wh[iid][wid] = 0
        
        if mtype in ("entrada", "transferencia_entrada"):
            stock_by_wh[iid][wid] += qty
        elif mtype in ("salida", "transferencia_salida"):
            stock_by_wh[iid][wid] -= qty
    
    report_items = []
    grand_total = 0

    # Reagrupar los (item_id, warehouse_id) por item_id para el reporte final.
    # Cada item muestra todos sus lotes activos, etiquetados con el almacén.
    items_by_iid: dict = {}
    for (iid, wid), data in items_entries.items():
        items_by_iid.setdefault(iid, []).append(data)

    for iid, group_list in items_by_iid.items():
        active_lots_global = []
        for data in group_list:
            for lot in data["lots"]:
                if lot["remaining"] > 0:
                    active_lots_global.append(lot)
        if not active_lots_global:
            continue

        item_name, item_type = item_master.get(iid, ("Sin nombre", ""))
        item_total = 0
        lot_details = []
        for lot in active_lots_global:
            lot_value = round(lot["remaining"] * lot["unit_cost"], 2)
            item_total += lot_value
            lot_details.append({
                "purchase_date": lot["purchase_date"],
                "supplier": lot["supplier"],
                "invoice_ref": lot["invoice_ref"],
                "quantity_purchased": lot["quantity_purchased"],
                "remaining": lot["remaining"],
                "unit_cost": lot["unit_cost"],
                "lot_value": lot_value,
                "warehouse_id": lot.get("warehouse_id", ""),
                "warehouse_name": wh_map.get(lot.get("warehouse_id", ""), ""),
            })

        grand_total += item_total

        # Desglose por almacén (basado en movimientos consolidados).
        item_stock = stock_by_wh.get(iid, {})
        units_lch = max(item_stock.get(lch_id, 0), 0) if lch_id else 0
        units_tbp = max(item_stock.get(tbp_id, 0), 0) if tbp_id else 0

        report_items.append({
            "item_id": iid,
            "item_name": item_name,
            "item_type": item_type,
            "lots": lot_details,
            "item_total": round(item_total, 2),
            "total_units": sum(l["remaining"] for l in active_lots_global),
            "units_lch": units_lch,
            "units_tbp": units_tbp,
        })
    
    # Ordenar por nombre
    report_items.sort(key=lambda x: x["item_name"])
    
    return {
        "report_date": datetime.now(timezone.utc).isoformat(),
        "method": "PEPS (FIFO)",
        "source_warehouse": lch_id,
        "items": report_items,
        "grand_total": round(grand_total, 2),
        "total_items": len(report_items),
    }


@router.get("/inventory/invoiced-exits-report")
async def get_invoiced_exits_report(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """Reporte de Relación de Salidas Facturadas — agrupado por almacén."""
    await get_current_user(authorization)

    query = {"movement_type": "salida"}
    if desde or hasta:
        date_filter = {}
        if desde:
            date_filter["$gte"] = desde
        if hasta:
            date_filter["$lte"] = hasta + "T23:59:59"
        query["created_at"] = date_filter

    movements = await db.inventory_movements.find(
        query, {"_id": 0}
    ).sort("created_at", 1).to_list(5000)

    warehouses = await db.warehouses.find({}, {"_id": 0}).to_list(50)
    wh_map = {w["warehouse_id"]: w.get("name", w["warehouse_id"]) for w in warehouses}

    grouped = {}
    for mov in movements:
        wh_id = mov.get("warehouse_id", "unknown")
        wh_name = wh_map.get(wh_id, wh_id)
        if wh_name not in grouped:
            grouped[wh_name] = {"warehouse_name": wh_name, "warehouse_id": wh_id, "exits": [], "total_units": 0}

        ref = mov.get("reference", "")
        invoice = ""
        if "Factura:" in ref:
            invoice = ref.split("Factura:")[1].split("|")[0].strip()
        elif mov.get("notes") and "Factura:" in mov.get("notes", ""):
            invoice = mov["notes"].split("Factura:")[1].split("|")[0].strip()

        fecha = mov.get("created_at", "")[:10] if mov.get("created_at") else ""
        qty = mov.get("quantity", 0)

        grouped[wh_name]["exits"].append({
            "movement_id": mov.get("movement_id", ""),
            "fecha": fecha,
            "item_name": mov.get("item_name", ""),
            "item_type": mov.get("item_type", ""),
            "quantity": qty,
            "unit_cost": mov.get("unit_cost", 0),
            "invoice_number": invoice,
            "reference": ref,
            "client_name": mov.get("client_name", ""),
            "quote_number": mov.get("quote_number", ""),
            "notes": mov.get("notes", ""),
            "created_by": mov.get("created_by", ""),
        })
        grouped[wh_name]["total_units"] += qty

    return {
        "report_date": datetime.now(timezone.utc).isoformat(),
        "date_range": {"desde": desde, "hasta": hasta},
        "warehouses": list(grouped.values()),
        "total_exits": sum(g["total_units"] for g in grouped.values()),
    }
