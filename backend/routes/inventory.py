"""Route module: inventory.py — Módulo de Control de Inventarios Multialmacén"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import io

from config import db, get_current_user, UPLOADS_DIR
from models import Warehouse, WarehouseCreate, InventoryMovement, SERIALIZED_TYPES
from services.email_service import send_email, resolve_sender_for_area
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
                sender=await resolve_sender_for_area("inventarios"),
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

    # FIFO segmentado por almacén: las TRANSFERENCIAS deben formar parte del
    # ciclo FIFO del almacén destino. Antes el reporte solo procesaba
    # `entrada` y `salida` (ignorando `transferencia_entrada` y
    # `transferencia_salida`), lo que dejaba "lotes fantasma" en el almacén
    # origen y subdescontaba las salidas en el almacén destino.
    #
    # Reglas:
    #  - `entrada` y `transferencia_entrada` → crean lote en (item, warehouse).
    #  - `salida` y `transferencia_salida`  → descuentan FIFO en (item, warehouse).
    #  - Las precargas (cuarentena técnica de transferencias entrantes)
    #    SE INCLUYEN en el FIFO porque físicamente ya están en el almacén
    #    destino y forman parte del stock contable. Se marcan en el histórico.
    movs_cursor = db.inventory_movements.find(
        {
            "movement_type": {"$in": [
                "entrada", "transferencia_entrada",
                "salida", "transferencia_salida",
            ]},
        },
        {"_id": 0},
    ).sort("created_at", 1)
    all_movs = await movs_cursor.to_list(10000)

    # Separar para procesarlos en orden, manteniendo prioridad de entradas
    # antes de salidas del mismo timestamp para evitar saldo negativo
    # transitorio. Orden estable: created_at ASC + entradas (sign=1) primero.
    def _mov_order_key(m: dict):
        is_entry = m.get("movement_type") in ("entrada", "transferencia_entrada")
        return (m.get("created_at") or "", 0 if is_entry else 1)
    all_movs.sort(key=_mov_order_key)

    # Agrupar lotes por (item_id, warehouse_id) — FIFO SEGMENTADO POR ALMACÉN.
    # Cada almacén mantiene su propia capa de inventario. Una salida (incluso
    # una transferencia_salida) descuenta exclusivamente de los lotes
    # ingresados a ese almacén (sea por compra o por transferencia previa).
    items_entries: dict = {}  # (item_id, warehouse_id) -> {item_name, item_type, lots:[]}
    item_master: dict = {}    # item_id -> (item_name, item_type)
    # Salidas diferidas: salidas que ocurrieron cronológicamente ANTES de las
    # entradas (datos inconsistentes tras reconstrucciones manuales). Se
    # aplican al final, contra los lotes existentes en ese (item, warehouse).
    deferred_exits: list = []  # [(key, qty, mtype, m)]

    for m in all_movs:
        iid = m.get("item_id", "unknown")
        wid = m.get("warehouse_id", "")
        key = (iid, wid)
        mtype = m.get("movement_type", "")
        qty = m.get("quantity", 0)
        if iid not in item_master:
            item_master[iid] = (m.get("item_name", "Sin nombre"), m.get("item_type", ""))

        if mtype in ("entrada", "transferencia_entrada"):
            # Para entradas directas usamos acquisition_date (fecha de
            # compra). Para transferencias usamos created_at (fecha de
            # llegada física al almacén destino) porque ese es el orden FIFO
            # operativo en el nuevo almacén.
            if mtype == "transferencia_entrada":
                lot_date = (m.get("created_at") or "")[:10] if isinstance(m.get("created_at"), str) else ""
                supplier_label = m.get("reference", "") or "Transferencia recibida"
            else:
                lot_date = m.get("acquisition_date") or ((m.get("created_at") or "")[:10] if isinstance(m.get("created_at"), str) else "")
                supplier_label = m.get("supplier", "")

            items_entries.setdefault(key, {
                "item_name": m.get("item_name", "Sin nombre"),
                "item_type": m.get("item_type", ""),
                "warehouse_id": wid,
                "lots": [],
            })["lots"].append({
                "movement_id": m.get("movement_id", ""),
                "purchase_date": lot_date,
                "supplier": supplier_label,
                "invoice_ref": m.get("invoice_ref", ""),
                "quantity_purchased": qty,
                "unit_cost": m.get("unit_cost", 0),
                "remaining": qty,
                "warehouse_id": wid,
                "created_at": m.get("created_at", ""),
                "is_transfer_in": (mtype == "transferencia_entrada"),
            })
        elif mtype in ("salida", "transferencia_salida"):
            # Descontar FIFO en (item, warehouse) — ordenamos los lotes
            # actuales por fecha ANTES de descontar.
            if key not in items_entries or not items_entries[key]["lots"]:
                # Salida huérfana: la difiero para aplicarla al final contra
                # los lotes que aparezcan después (corrige datos
                # inconsistentes tras reconstrucciones de almacenes).
                deferred_exits.append((key, qty, mtype, m))
                continue
            items_entries[key]["lots"].sort(
                key=lambda lot: lot.get("purchase_date") or lot.get("created_at") or ""
            )
            to_deduct = qty
            for lot in items_entries[key]["lots"]:
                if to_deduct <= 0:
                    break
                d = min(lot["remaining"], to_deduct)
                lot["remaining"] -= d
                to_deduct -= d
            if to_deduct > 0:
                # Solo parcialmente descontada: difiero el remanente.
                deferred_exits.append((key, to_deduct, mtype, m))

    # Aplicar salidas diferidas al final (deferred FIFO) — útil cuando los
    # datos no están cronológicamente consistentes pero el saldo agregado sí.
    for key, qty, mtype, m in deferred_exits:
        if key not in items_entries:
            logger.warning(
                f"[asset-ledger] Salida huérfana sin lotes — item={key[0]} warehouse={key[1]} qty={qty} type={mtype}"
            )
            continue
        items_entries[key]["lots"].sort(
            key=lambda lot: lot.get("purchase_date") or lot.get("created_at") or ""
        )
        to_deduct = qty
        for lot in items_entries[key]["lots"]:
            if to_deduct <= 0:
                break
            d = min(lot["remaining"], to_deduct)
            lot["remaining"] -= d
            to_deduct -= d
        if to_deduct > 0:
            logger.warning(
                f"[asset-ledger] {mtype} excede stock FIFO total — item={key[0]} warehouse={key[1]} faltante={to_deduct}"
            )

    # Ordenar lotes finales por fecha (PEPS) DENTRO de cada (item, warehouse).
    for key in items_entries:
        items_entries[key]["lots"].sort(
            key=lambda lot: lot.get("purchase_date") or lot.get("created_at") or ""
        )

    
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

    # Pre-calcular histórico de movimientos por item (para el panel
    # colapsable "Movimientos históricos" del frontend). Mantiene
    # trazabilidad completa incluso de lotes ya consumidos/transferidos.
    history_by_iid: dict = {}
    for m in all_movs:
        iid = m.get("item_id")
        wid = m.get("warehouse_id", "")
        mtype = m.get("movement_type", "")
        qty = m.get("quantity", 0)
        sign = 1 if mtype in ("entrada", "transferencia_entrada") else -1
        history_by_iid.setdefault(iid, []).append({
            "date": (m.get("created_at") or "")[:19],
            "movement_type": mtype,
            "warehouse_id": wid,
            "warehouse_name": wh_map.get(wid, ""),
            "quantity": qty,
            "signed_quantity": sign * qty,
            "unit_cost": m.get("unit_cost", 0),
            "supplier": m.get("supplier", ""),
            "invoice_ref": m.get("invoice_ref", ""),
            "reference": m.get("reference", ""),
            "client_name": m.get("client_name", ""),
            "quote_number": m.get("quote_number", ""),
            "transfer_id": m.get("transfer_id", ""),
        })

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
            "history": history_by_iid.get(iid, []),
            "item_total": round(item_total, 2),
            "total_units": sum(lot["remaining"] for lot in active_lots_global),
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
            "serials": mov.get("serials", []),
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



# ==================== HERRAMIENTAS ADMINISTRATIVAS DE SERIALES ====================
# Solo Admin. Permite corregir asignaciones erróneas, reemplazar seriales por
# falla de fábrica y desasignar/marcar como "no asignable" (a la espera de
# reemplazo del proveedor). Todo cambio queda registrado en bitácora.


async def _require_admin_user(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo el rol Administrador puede ejecutar esta acción")
    return user


@router.get("/admin/inventory/serials/search")
async def admin_search_serial(
    q: str,
    authorization: Optional[str] = Header(None),
):
    """Busca asignaciones de serial por número exacto o parcial.
    Devuelve datos completos (cliente, cotización, almacén, estado).
    """
    await _require_admin_user(authorization)
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Mínimo 2 caracteres")
    qn = q.strip().upper()
    cursor = db.serial_assignments.find(
        {"serial": {"$regex": qn, "$options": "i"}},
        {"_id": 0},
    ).limit(50)
    results = await cursor.to_list(50)
    return {"count": len(results), "results": results}


@router.get("/admin/inventory/items")
async def admin_list_models(authorization: Optional[str] = Header(None)):
    """Lista de modelos POS/Pinpad con seriales en inventario.
    Devuelve solo los items que han tenido movimientos con seriales.
    """
    await _require_admin_user(authorization)

    # Items que han tenido entradas con seriales en movimientos
    item_ids_with_serials = await db.inventory_movements.distinct(
        "item_id",
        {"serials": {"$exists": True, "$ne": []}, "movement_type": {"$in": ["entrada", "transferencia_entrada"]}},
    )
    if not item_ids_with_serials:
        return {"count": 0, "items": []}

    hw_docs = await db.hardware.find(
        {"hardware_id": {"$in": item_ids_with_serials}},
        {"_id": 0, "hardware_id": 1, "name": 1, "type": 1},
    ).to_list(500)

    items = sorted(
        [{"item_id": h["hardware_id"], "name": h["name"], "type": h.get("type", "")} for h in hw_docs],
        key=lambda x: x["name"].lower(),
    )
    return {"count": len(items), "items": items}


@router.get("/admin/inventory/serials/by-item")
async def admin_serials_by_item(
    item_id: str,
    authorization: Optional[str] = Header(None),
):
    """Lista TODOS los seriales de un modelo (item_id) con su estado actual.
    Estados posibles: 'en_stock' (sin asignar), 'asignado', 'preasignado',
    'asignado_temporal', 'blacklist' (no asignable por falla).
    Permite al admin ver el inventario completo del modelo para gestionarlo.
    """
    await _require_admin_user(authorization)
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id requerido")

    # 1) Reconstruir el estado físico de cada serial usando el ÚLTIMO movimiento
    # (orden cronológico). Esto permite que una devolución (entrada posterior a
    # una salida) restablezca el serial a "en stock" sin marcarlo como vendido.
    last_mtype_by_serial: dict = {}
    last_wh_by_serial: dict = {}  # almacén del ÚLTIMO movimiento (adscripción física)
    cursor = db.inventory_movements.find(
        {"item_id": item_id, "serials": {"$exists": True, "$ne": []}},
        {"_id": 0, "movement_type": 1, "serials": 1, "created_at": 1, "warehouse_id": 1},
    ).sort("created_at", 1)  # asc → la última asignación sobreescribe
    async for m in cursor:
        mtype = m.get("movement_type")
        wh = m.get("warehouse_id")
        for s in (m.get("serials") or []):
            last_mtype_by_serial[s] = mtype
            last_wh_by_serial[s] = wh

    # Mapa de nombres de almacén (para mostrar el nombre en la grilla)
    wh_name_map: dict = {}
    async for w in db.warehouses.find({}, {"_id": 0, "warehouse_id": 1, "name": 1}):
        wh_name_map[w.get("warehouse_id")] = w.get("name")

    physical_serials = {s for s, mt in last_mtype_by_serial.items() if mt in ("entrada", "transferencia_entrada")}
    serials_left_stock = {s for s, mt in last_mtype_by_serial.items() if mt in ("salida", "transferencia_salida")}

    # 2) Asignaciones activas (preasignado/asignado/asignado_temporal)
    assignments_map: dict = {}
    async for a in db.serial_assignments.find(
        {"item_id": item_id},
        {"_id": 0},
    ):
        assignments_map[a["serial"]] = a

    # 3) Blacklist
    blacklist_map: dict = {}
    async for b in db.serial_blacklist.find({}, {"_id": 0}):
        blacklist_map[b["serial"]] = b

    # 4) Combinar todos los seriales conocidos
    all_serials = set(physical_serials) | set(assignments_map.keys()) | set(serials_left_stock)
    rows: list = []
    for s in sorted(all_serials):
        asg = assignments_map.get(s)
        bl = blacklist_map.get(s)
        if bl:
            status = "blacklist"
        elif asg:
            status = asg.get("status", "asignado")
        elif s in physical_serials:
            status = "en_stock"
        elif s in serials_left_stock:
            status = "vendido"
        else:
            status = "desconocido"

        # Almacén de adscripción: la asignación manda si existe; si no, el
        # almacén del último movimiento físico del serial. Si el id existe pero
        # el almacén fue eliminado (ref huérfana), se indica explícitamente.
        wh_id = (asg.get("warehouse_id") if asg else None) or last_wh_by_serial.get(s)
        if wh_id:
            wh_name = wh_name_map.get(wh_id) or "Almacén no identificado"
        else:
            wh_name = None

        rows.append({
            "serial": s,
            "status": status,
            "assignment_id": asg.get("assignment_id") if asg else None,
            "client_id": asg.get("client_id") if asg else None,
            "client_name": asg.get("client_name") if asg else None,
            "quote_id": asg.get("quote_id") if asg else None,
            "quote_number": asg.get("quote_number") if asg else None,
            "warehouse_id": wh_id,
            "warehouse_name": wh_name,
            "blacklist_reason": bl.get("reason") if bl else None,
            "previous_serial": asg.get("previous_serial") if asg else None,
            "replacement_reason": asg.get("replacement_reason") if asg else None,
        })

    counts = {
        "total": len(rows),
        "en_stock": sum(1 for r in rows if r["status"] == "en_stock"),
        "asignado": sum(1 for r in rows if r["status"] == "asignado"),
        "preasignado": sum(1 for r in rows if r["status"] == "preasignado"),
        "asignado_temporal": sum(1 for r in rows if r["status"] == "asignado_temporal"),
        "blacklist": sum(1 for r in rows if r["status"] == "blacklist"),
        "vendido": sum(1 for r in rows if r["status"] == "vendido"),
    }
    return {"item_id": item_id, "counts": counts, "serials": rows}


@router.post("/admin/inventory/serials/{assignment_id}/replace")
async def admin_replace_serial(
    assignment_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Reemplaza el número de serial en una asignación existente.
    Caso de uso: falla de fábrica, llega reemplazo del proveedor.
    body: { new_serial: str, reason: str, return_old_to_stock: bool }
    """
    user = await _require_admin_user(authorization)
    new_serial = (body.get("new_serial") or "").strip().upper()
    reason = (body.get("reason") or "").strip()
    return_old = bool(body.get("return_old_to_stock", False))
    if not new_serial:
        raise HTTPException(status_code=400, detail="new_serial requerido")
    if not reason:
        raise HTTPException(status_code=400, detail="reason requerido")

    asg = await db.serial_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not asg:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    old_serial = asg["serial"]
    if old_serial == new_serial:
        raise HTTPException(status_code=400, detail="El nuevo serial debe ser distinto del actual")

    conflict = await db.serial_assignments.find_one(
        {"serial": new_serial, "status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
        {"_id": 0, "assignment_id": 1, "quote_number": 1, "client_name": 1},
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"El serial {new_serial} ya esta asignado en {conflict.get('quote_number', '')} ({conflict.get('client_name', '')})",
        )

    # El nuevo serial no debe estar en la blacklist (sería contradictorio
    # reemplazar un serial defectuoso por otro marcado como no asignable).
    in_blacklist = await db.serial_blacklist.find_one(
        {"serial": new_serial}, {"_id": 0, "reason": 1}
    )
    if in_blacklist:
        raise HTTPException(
            status_code=409,
            detail=f"El serial {new_serial} esta en la lista de NO asignables ({in_blacklist.get('reason','')}). Liberarlo primero o usar otro.",
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.serial_assignments.update_one(
        {"assignment_id": assignment_id},
        {"$set": {
            "serial": new_serial,
            "previous_serial": old_serial,
            "replaced_at": now,
            "replaced_by": user.get("user_id"),
            "replaced_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
            "replacement_reason": reason,
        }},
    )

    await db.bitacora.insert_one({
        "action": "admin_serial_replace",
        "assignment_id": assignment_id,
        "old_serial": old_serial,
        "new_serial": new_serial,
        "reason": reason,
        "return_old_to_stock": return_old,
        "quote_number": asg.get("quote_number"),
        "client_name": asg.get("client_name"),
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    if not return_old:
        await db.serial_blacklist.update_one(
            {"serial": old_serial},
            {"$set": {
                "serial": old_serial,
                "reason": f"Reemplazado por falla en {asg.get('quote_number','')}: {reason}",
                "blocked_at": now,
                "blocked_by": user.get("email"),
                "source_assignment_id": assignment_id,
            }},
            upsert=True,
        )

    return {
        "ok": True,
        "assignment_id": assignment_id,
        "old_serial": old_serial,
        "new_serial": new_serial,
        "message": f"Serial reemplazado: {old_serial} -> {new_serial}",
    }


@router.post("/admin/inventory/serials/{assignment_id}/reassign-client")
async def admin_reassign_serial_client(
    assignment_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Reasigna un serial a otro cliente / cotizacion.
    body: { new_client_id: str, new_quote_id?: str, reason: str }
    """
    user = await _require_admin_user(authorization)
    new_client_id = (body.get("new_client_id") or "").strip()
    new_quote_id = (body.get("new_quote_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not new_client_id or not reason:
        raise HTTPException(status_code=400, detail="new_client_id y reason son requeridos")

    asg = await db.serial_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not asg:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")

    client = await db.clients.find_one({"client_id": new_client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente destino no encontrado")

    update_set: dict = {
        "previous_client_id": asg.get("client_id"),
        "previous_client_name": asg.get("client_name"),
        "previous_quote_id": asg.get("quote_id"),
        "previous_quote_number": asg.get("quote_number"),
        "client_id": new_client_id,
        "client_name": client.get("fantasy_name") or client.get("legal_name") or "",
        "client_rif": client.get("rif") or "",
        "reassigned_at": datetime.now(timezone.utc).isoformat(),
        "reassigned_by": user.get("user_id"),
        "reassignment_reason": reason,
    }
    if new_quote_id:
        new_quote = await db.quotes.find_one({"quote_id": new_quote_id}, {"_id": 0, "quote_number": 1})
        if not new_quote:
            raise HTTPException(status_code=404, detail="Cotizacion destino no encontrada")
        update_set["quote_id"] = new_quote_id
        update_set["quote_number"] = new_quote.get("quote_number", "")

    await db.serial_assignments.update_one(
        {"assignment_id": assignment_id},
        {"$set": update_set},
    )

    await db.bitacora.insert_one({
        "action": "admin_serial_reassign_client",
        "assignment_id": assignment_id,
        "serial": asg.get("serial"),
        "old_client_id": asg.get("client_id"),
        "new_client_id": new_client_id,
        "old_quote_id": asg.get("quote_id"),
        "new_quote_id": new_quote_id or asg.get("quote_id"),
        "reason": reason,
        "executed_by": user.get("email"),
        "executed_at": update_set["reassigned_at"],
    })

    return {"ok": True, "message": f"Serial {asg.get('serial')} reasignado a {update_set['client_name']}"}


@router.post("/admin/inventory/serials/{assignment_id}/unassign")
async def admin_unassign_serial(
    assignment_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Desasigna un serial y opcionalmente lo marca como NO asignable.
    body: { reason: str, mark_non_assignable: bool }
    """
    user = await _require_admin_user(authorization)
    reason = (body.get("reason") or "").strip()
    mark_non_assignable = bool(body.get("mark_non_assignable", True))
    if not reason:
        raise HTTPException(status_code=400, detail="reason requerido")

    asg = await db.serial_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not asg:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")

    serial = asg.get("serial")
    now = datetime.now(timezone.utc).isoformat()

    await db.serial_assignments.delete_one({"assignment_id": assignment_id})

    if mark_non_assignable:
        await db.serial_blacklist.update_one(
            {"serial": serial},
            {"$set": {
                "serial": serial,
                "reason": reason,
                "blocked_at": now,
                "blocked_by": user.get("email"),
                "source_assignment_id": assignment_id,
                "previous_client": asg.get("client_name"),
                "previous_quote": asg.get("quote_number"),
            }},
            upsert=True,
        )

    await db.bitacora.insert_one({
        "action": "admin_serial_unassign",
        "assignment_id": assignment_id,
        "serial": serial,
        "client_name": asg.get("client_name"),
        "quote_number": asg.get("quote_number"),
        "reason": reason,
        "mark_non_assignable": mark_non_assignable,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    msg = f"Serial {serial} desasignado"
    if mark_non_assignable:
        msg += " y marcado como NO ASIGNABLE (pendiente de reemplazo)"
    return {"ok": True, "message": msg}


@router.get("/admin/inventory/serials/blacklist")
async def admin_list_blacklist(authorization: Optional[str] = Header(None)):
    """Lista seriales marcados como no asignables (esperando reemplazo)."""
    await _require_admin_user(authorization)
    cursor = db.serial_blacklist.find({}, {"_id": 0}).sort("blocked_at", -1)
    items = await cursor.to_list(500)
    return {"count": len(items), "items": items}


@router.post("/admin/inventory/serials/blacklist/{serial}/release")
async def admin_release_blacklist(
    serial: str,
    authorization: Optional[str] = Header(None),
):
    """Libera un serial de la blacklist (ya llego reemplazo o se aclaro el caso)."""
    user = await _require_admin_user(authorization)
    res = await db.serial_blacklist.delete_one({"serial": serial.upper()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Serial no estaba en blacklist")
    await db.bitacora.insert_one({
        "action": "admin_serial_blacklist_release",
        "serial": serial,
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"ok": True, "message": f"Serial {serial} liberado de blacklist"}


# ==================== GESTIÓN DE SERIALES VENDIDOS ====================
# Permite al Administrador devolver/desasignar/eliminar seriales que
# físicamente salieron del stock (status "vendido" en la vista por modelo)
# y que NO tienen `assignment_id` activo en `serial_assignments`.
# Identificación: el serial aparece en algún `inventory_movements` con
# movement_type ∈ {salida, transferencia_salida} y no figura en una
# entrada/transferencia_entrada posterior.


async def _find_sold_serial_movement(serial: str) -> Optional[dict]:
    """Retorna el último movimiento de salida que contiene el serial."""
    serial_u = (serial or "").strip()
    if not serial_u:
        return None
    cursor = db.inventory_movements.find(
        {
            "movement_type": {"$in": ["salida", "transferencia_salida"]},
            "serials": serial_u,
        },
        {"_id": 0},
    ).sort("created_at", -1).limit(1)
    docs = await cursor.to_list(1)
    return docs[0] if docs else None


@router.post("/admin/inventory/serials/sold/{serial}/return-to-stock")
async def admin_return_sold_serial(
    serial: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Devuelve un serial vendido al stock asignable.

    Crea un movimiento de entrada (`entrada`) con el serial al almacén
    indicado y limpia eventual entrada en blacklist. NO altera la salida
    original (conserva trazabilidad histórica).

    body: { warehouse_id?: str, reason: str }
    Si no se especifica warehouse_id, se usa el del último movimiento de salida.
    """
    user = await _require_admin_user(authorization)
    serial_norm = (serial or "").strip()
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason requerido")

    last_out = await _find_sold_serial_movement(serial_norm)
    if not last_out:
        raise HTTPException(status_code=404, detail="No se encontró movimiento de salida para este serial")

    warehouse_id = (body.get("warehouse_id") or last_out.get("warehouse_id") or "").strip()
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="warehouse_id requerido")

    # Si ya está actualmente en stock o asignado, abortar
    active_asg = await db.serial_assignments.find_one(
        {"serial": serial_norm, "status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
        {"_id": 0},
    )
    if active_asg:
        raise HTTPException(
            status_code=409,
            detail=f"Serial activo en asignación {active_asg.get('status')} (cotización {active_asg.get('quote_number')}). No se puede devolver al stock.",
        )

    now = datetime.now(timezone.utc).isoformat()
    movement_id = f"mov_{uuid.uuid4().hex[:12]}"
    item_id = last_out.get("item_id")
    item_name = last_out.get("item_name") or ""
    unit_cost = last_out.get("unit_cost") or 0

    entry_doc = {
        "movement_id": movement_id,
        "item_id": item_id,
        "item_name": item_name,
        "warehouse_id": warehouse_id,
        "movement_type": "entrada",
        "quantity": 1,
        "unit_cost": unit_cost,
        "serials": [serial_norm],
        "supplier": "DEVOLUCIÓN ADMINISTRATIVA",
        "invoice_number": "",
        "notes": f"Devolución administrativa del serial {serial_norm}. Motivo: {reason}",
        "reference": f"Devolución de venta (origen: {last_out.get('movement_id', 'N/A')})",
        "created_at": now,
        "created_by": user.get("email"),
        "is_admin_return": True,
        "origin_movement_id": last_out.get("movement_id"),
    }
    await db.inventory_movements.insert_one(entry_doc)

    # Liberar de blacklist si estaba allí
    await db.serial_blacklist.delete_one({"serial": serial_norm})

    await db.bitacora.insert_one({
        "action": "admin_serial_return_to_stock",
        "serial": serial_norm,
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "origin_movement_id": last_out.get("movement_id"),
        "new_movement_id": movement_id,
        "reason": reason,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    return {"ok": True, "message": f"Serial {serial_norm} devuelto al stock", "movement_id": movement_id}


@router.post("/admin/inventory/serials/sold/{serial}/unassign")
async def admin_unassign_sold_serial(
    serial: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Desasigna un serial vendido (sin assignment_id activo) y opcionalmente
    lo manda a blacklist. Esta acción NO toca los movimientos de inventario,
    solo limpia rastros activos en `serial_assignments` (si quedó algún
    registro archivado) y registra la blacklist.

    body: { reason: str, mark_non_assignable: bool }
    """
    user = await _require_admin_user(authorization)
    serial_norm = (serial or "").strip()
    reason = (body.get("reason") or "").strip()
    mark_non_assignable = bool(body.get("mark_non_assignable", False))
    if not reason:
        raise HTTPException(status_code=400, detail="reason requerido")

    last_out = await _find_sold_serial_movement(serial_norm)
    if not last_out:
        raise HTTPException(status_code=404, detail="No se encontró movimiento de salida para este serial")

    # Limpiar asignaciones residuales (cualquier estado)
    del_res = await db.serial_assignments.delete_many({"serial": serial_norm})

    now = datetime.now(timezone.utc).isoformat()
    if mark_non_assignable:
        await db.serial_blacklist.update_one(
            {"serial": serial_norm},
            {"$set": {
                "serial": serial_norm,
                "reason": reason,
                "blocked_at": now,
                "blocked_by": user.get("email"),
                "previous_client": last_out.get("client_name"),
                "previous_quote": last_out.get("reference"),
                "source": "sold_unassign",
            }},
            upsert=True,
        )

    await db.bitacora.insert_one({
        "action": "admin_serial_sold_unassign",
        "serial": serial_norm,
        "item_id": last_out.get("item_id"),
        "client_name": last_out.get("client_name"),
        "reason": reason,
        "mark_non_assignable": mark_non_assignable,
        "removed_assignments": del_res.deleted_count,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    msg = f"Serial {serial_norm} desasignado"
    if mark_non_assignable:
        msg += " y marcado como NO ASIGNABLE"
    return {"ok": True, "message": msg, "removed_assignments": del_res.deleted_count}


@router.delete("/admin/inventory/serials/sold/{serial}")
async def admin_delete_sold_serial(
    serial: str,
    reason: Optional[str] = Header(None, alias="x-reason"),
    authorization: Optional[str] = Header(None),
):
    """Elimina un serial vendido del histórico: lo remueve de los movimientos
    de salida/transferencia_salida que lo contengan. Si el movimiento queda
    sin seriales y con cantidad 1, se borra; si contenía múltiples seriales,
    solo se quita ese serial y se decrementa la cantidad.

    Header: x-reason: <motivo>

    Limpia también blacklist y asignaciones residuales para que el serial
    desaparezca completamente del sistema.
    """
    user = await _require_admin_user(authorization)
    serial_norm = (serial or "").strip()
    motivo = (reason or "").strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="x-reason header requerido")

    # Buscar TODOS los movimientos que contengan el serial (entradas y salidas)
    affected_movements = []
    async for m in db.inventory_movements.find(
        {"serials": serial_norm},
        {"_id": 0},
    ):
        affected_movements.append(m)

    if not affected_movements:
        raise HTTPException(status_code=404, detail="Serial no encontrado en ningún movimiento")

    deleted_movs = 0
    updated_movs = 0
    for m in affected_movements:
        serials_list = [s for s in (m.get("serials") or []) if s != serial_norm]
        if not serials_list and (m.get("quantity", 1) <= 1):
            # Movimiento exclusivo de este serial → borrar
            await db.inventory_movements.delete_one({"movement_id": m["movement_id"]})
            deleted_movs += 1
        else:
            # Movimiento con varios seriales → recortar y reducir qty
            new_qty = max(1, int(m.get("quantity", 1)) - 1)
            await db.inventory_movements.update_one(
                {"movement_id": m["movement_id"]},
                {"$set": {"serials": serials_list, "quantity": new_qty}},
            )
            updated_movs += 1

    # Limpiar rastros residuales
    del_asg = await db.serial_assignments.delete_many({"serial": serial_norm})
    del_bl = await db.serial_blacklist.delete_one({"serial": serial_norm})

    now = datetime.now(timezone.utc).isoformat()
    await db.bitacora.insert_one({
        "action": "admin_serial_sold_delete",
        "serial": serial_norm,
        "movements_deleted": deleted_movs,
        "movements_updated": updated_movs,
        "assignments_removed": del_asg.deleted_count,
        "blacklist_removed": del_bl.deleted_count,
        "reason": motivo,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    return {
        "ok": True,
        "message": f"Serial {serial_norm} eliminado del sistema",
        "movements_deleted": deleted_movs,
        "movements_updated": updated_movs,
    }


# ==================== CRUD ADMIN DE SERIALES (Alta / Modificación) ====================
# Evolución del módulo "Gestionar Seriales": creación (alta) y edición
# (rename + reubicación de almacén) de números de serie, con auditoría.


@router.get("/admin/inventory/serializable-items")
async def admin_list_serializable_items(authorization: Optional[str] = Header(None)):
    """Lista de modelos de hardware serializables (POS/Pinpad/MPOS) para el
    alta de nuevos seriales. A diferencia de /admin/inventory/items, incluye
    modelos que aún NO tienen seriales registrados.
    """
    await _require_admin_user(authorization)
    docs = await db.hardware.find(
        {}, {"_id": 0, "hardware_id": 1, "name": 1, "type": 1}
    ).to_list(1000)
    items = sorted(
        [
            {"item_id": h["hardware_id"], "name": h.get("name", ""), "type": h.get("type", "")}
            for h in docs
            if is_serialized(h.get("type", ""))
        ],
        key=lambda x: (x["name"] or "").lower(),
    )
    return {"count": len(items), "items": items}


async def _serial_exists_anywhere(serial: str) -> bool:
    """True si el serial ya existe en movimientos, asignaciones o blacklist."""
    if await db.inventory_movements.find_one({"serials": serial}, {"_id": 1}):
        return True
    if await db.serial_assignments.find_one({"serial": serial}, {"_id": 1}):
        return True
    if await db.serial_blacklist.find_one({"serial": serial}, {"_id": 1}):
        return True
    return False


@router.post("/admin/inventory/serials/create")
async def admin_create_serials(body: dict, authorization: Optional[str] = Header(None)):
    """Da de alta uno o varios seriales nuevos en estado DISPONIBLE (en_stock).

    body: { item_id: str, warehouse_id: str, serials: [str, ...] }

    Crea un único movimiento de ENTRADA "ALTA ADMINISTRATIVA" con los seriales
    válidos en el almacén indicado. Rechaza seriales ya existentes (en stock,
    asignados o en blacklist). Registra auditoría en bitácora.
    """
    user = await _require_admin_user(authorization)
    item_id = (body.get("item_id") or "").strip()
    warehouse_id = (body.get("warehouse_id") or "").strip()
    raw_serials = body.get("serials") or []
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id (Producto) requerido")
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="warehouse_id (Almacén de adscripción) requerido")

    hw = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0, "name": 1, "type": 1})
    if not hw:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not is_serialized(hw.get("type", "")):
        raise HTTPException(status_code=400, detail="El producto seleccionado no es serializable (debe ser POS/Pinpad/MPOS)")

    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0, "name": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    # Normalizar: strip, descartar vacíos, dedupe preservando orden
    seen = set()
    serials = []
    for s in raw_serials:
        sn = (s or "").strip()
        if sn and sn not in seen:
            seen.add(sn)
            serials.append(sn)
    if not serials:
        raise HTTPException(status_code=400, detail="Debe indicar al menos un número de serial")

    created, skipped = [], []
    for sn in serials:
        if await _serial_exists_anywhere(sn):
            skipped.append({"serial": sn, "reason": "Ya existe en el sistema"})
        else:
            created.append(sn)

    if not created:
        raise HTTPException(
            status_code=409,
            detail=f"Todos los seriales ya existen. Omitidos: {', '.join(s['serial'] for s in skipped)}",
        )

    now = datetime.now(timezone.utc).isoformat()
    movement_id = f"mov_{uuid.uuid4().hex[:12]}"
    entry_doc = {
        "movement_id": movement_id,
        "item_id": item_id,
        "item_name": hw.get("name", ""),
        "warehouse_id": warehouse_id,
        "movement_type": "entrada",
        "quantity": len(created),
        "unit_cost": 0,
        "serials": created,
        "supplier": "ALTA ADMINISTRATIVA",
        "invoice_number": "",
        "notes": f"Alta administrativa de {len(created)} serial(es) por {user.get('email')}",
        "reference": "Alta administrativa de seriales",
        "created_at": now,
        "created_by": user.get("email"),
        "is_admin_creation": True,
    }
    await db.inventory_movements.insert_one(entry_doc)

    await db.bitacora.insert_one({
        "action": "admin_serial_create",
        "item_id": item_id,
        "item_name": hw.get("name", ""),
        "warehouse_id": warehouse_id,
        "warehouse_name": wh.get("name", ""),
        "serials_created": created,
        "serials_skipped": skipped,
        "movement_id": movement_id,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    return {
        "ok": True,
        "movement_id": movement_id,
        "created": created,
        "created_count": len(created),
        "skipped": skipped,
        "message": (
            f"{len(created)} serial(es) creado(s) en '{wh.get('name','')}'"
            + (f" · {len(skipped)} omitido(s) (ya existían)" if skipped else "")
        ),
    }


@router.put("/admin/inventory/serials/edit")
async def admin_edit_serial(body: dict, authorization: Optional[str] = Header(None)):
    """Modifica un serial existente: corrige el número (rename) y/o reubica su
    almacén de adscripción. No corrompe el histórico (rename propaga a todos
    los movimientos/asignaciones/blacklist; la reubicación de un serial en
    stock usa un par de movimientos de transferencia). Auditoría en bitácora.

    body: { current_serial: str, new_serial?: str, new_warehouse_id?: str, reason: str }
    """
    user = await _require_admin_user(authorization)
    current_serial = (body.get("current_serial") or "").strip()
    new_serial = (body.get("new_serial") or "").strip()
    new_warehouse_id = (body.get("new_warehouse_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not current_serial:
        raise HTTPException(status_code=400, detail="current_serial requerido")
    if not reason:
        raise HTTPException(status_code=400, detail="Motivo (reason) requerido para la auditoría")

    rename = bool(new_serial and new_serial != current_serial)
    relocate = bool(new_warehouse_id)
    if not rename and not relocate:
        raise HTTPException(status_code=400, detail="No hay cambios: indique nuevo serial y/o nuevo almacén")

    # Último movimiento físico (define item_id/item_name/almacén actual)
    last_mov = await db.inventory_movements.find_one(
        {"serials": current_serial}, {"_id": 0}, sort=[("created_at", -1)]
    )
    asg = await db.serial_assignments.find_one(
        {"serial": current_serial,
         "status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
        {"_id": 0},
    )
    if not last_mov and not asg:
        raise HTTPException(status_code=404, detail="Serial no encontrado en el sistema")

    now = datetime.now(timezone.utc).isoformat()
    audit = {
        "action": "admin_serial_edit",
        "current_serial": current_serial,
        "reason": reason,
        "executed_by": user.get("email"),
        "executed_at": now,
    }

    # ── 1) RENAME ──
    final_serial = current_serial
    if rename:
        if await _serial_exists_anywhere(new_serial):
            raise HTTPException(
                status_code=409,
                detail=f"El serial {new_serial} ya existe en el sistema. Use otro valor.",
            )
        await db.inventory_movements.update_many(
            {"serials": current_serial},
            {"$set": {"serials.$": new_serial}},
        )
        await db.serial_assignments.update_many(
            {"serial": current_serial}, {"$set": {"serial": new_serial}}
        )
        await db.serial_blacklist.update_many(
            {"serial": current_serial}, {"$set": {"serial": new_serial}}
        )
        final_serial = new_serial
        audit["new_serial"] = new_serial

    # ── 2) REUBICACIÓN DE ALMACÉN ──
    if relocate:
        wh = await db.warehouses.find_one({"warehouse_id": new_warehouse_id}, {"_id": 0, "name": 1})
        if not wh:
            raise HTTPException(status_code=404, detail="Almacén destino no encontrado")

        if asg:
            # Serial asignado/preasignado → actualizar el almacén de la asignación
            await db.serial_assignments.update_one(
                {"serial": final_serial,
                 "status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
                {"$set": {"warehouse_id": new_warehouse_id}},
            )
            audit["relocate_mode"] = "assignment"
        else:
            # Determinar estado físico actual a partir del último movimiento
            last_type = (last_mov or {}).get("movement_type")
            in_stock = last_type in ("entrada", "transferencia_entrada")
            if not in_stock:
                raise HTTPException(
                    status_code=400,
                    detail="No se puede reubicar un serial que no está en stock (vendido/no asignable). Devuélvalo al stock primero.",
                )
            old_wh = (last_mov or {}).get("warehouse_id")
            if old_wh == new_warehouse_id:
                raise HTTPException(status_code=400, detail="El serial ya está en ese almacén")
            item_id = (last_mov or {}).get("item_id")
            item_name = (last_mov or {}).get("item_name", "")
            base = {
                "item_id": item_id,
                "item_name": item_name,
                "quantity": 1,
                "unit_cost": (last_mov or {}).get("unit_cost", 0),
                "serials": [final_serial],
                "created_at": now,
                "created_by": user.get("email"),
                "is_admin_relocation": True,
                "notes": f"Reubicación administrativa del serial {final_serial}. Motivo: {reason}",
            }
            await db.inventory_movements.insert_one({
                **base,
                "movement_id": f"mov_{uuid.uuid4().hex[:12]}",
                "warehouse_id": old_wh,
                "movement_type": "transferencia_salida",
                "reference": f"Reubicación admin → {wh.get('name','')}",
            })
            await db.inventory_movements.insert_one({
                **base,
                "movement_id": f"mov_{uuid.uuid4().hex[:12]}",
                "warehouse_id": new_warehouse_id,
                "movement_type": "transferencia_entrada",
                "reference": "Reubicación administrativa (destino)",
            })
            audit["relocate_mode"] = "transfer"
            audit["old_warehouse_id"] = old_wh

        audit["new_warehouse_id"] = new_warehouse_id
        audit["new_warehouse_name"] = wh.get("name", "")

    await db.bitacora.insert_one(audit)

    return {
        "ok": True,
        "serial": final_serial,
        "renamed": rename,
        "relocated": relocate,
        "message": f"Serial actualizado: {current_serial}"
        + (f" → {final_serial}" if rename else "")
        + (f" · reubicado a {audit.get('new_warehouse_name','')}" if relocate else ""),
    }



@router.post("/admin/inventory/serials/assign")
async def admin_assign_serial(body: dict, authorization: Optional[str] = Header(None)):
    """Asigna un serial DISPONIBLE (en_stock) a un cliente (y opcionalmente a
    una cotización), dejándolo en estado 'asignado'. Auditoría en bitácora.

    body: { serial: str, client_id: str, quote_id?: str, reason: str }
    """
    user = await _require_admin_user(authorization)
    serial = (body.get("serial") or "").strip()
    client_id = (body.get("client_id") or "").strip()
    quote_id = (body.get("quote_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not serial:
        raise HTTPException(status_code=400, detail="serial requerido")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id (Cliente) requerido")
    if not reason:
        raise HTTPException(status_code=400, detail="Motivo (reason) requerido para la auditoría")

    active = await db.serial_assignments.find_one(
        {"serial": serial, "status": {"$in": ["preasignado", "asignado", "asignado_temporal"]}},
        {"_id": 0},
    )
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"El serial ya está {active.get('status')} (cotización {active.get('quote_number') or '—'}). Desasígnelo primero.",
        )
    if await db.serial_blacklist.find_one({"serial": serial}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="El serial está en la lista de NO asignables. Libérelo primero.")

    last_mov = await db.inventory_movements.find_one(
        {"serials": serial}, {"_id": 0}, sort=[("created_at", -1)]
    )
    if not last_mov:
        raise HTTPException(status_code=404, detail="Serial no encontrado en inventario")
    if last_mov.get("movement_type") not in ("entrada", "transferencia_entrada"):
        raise HTTPException(status_code=400, detail="Solo se puede asignar un serial Disponible (en stock).")

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    quote_number = ""
    if quote_id:
        q = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0, "quote_number": 1})
        if not q:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        quote_number = q.get("quote_number", "")

    now = datetime.now(timezone.utc).isoformat()
    assignment_id = f"sa_{uuid.uuid4().hex[:12]}"
    client_name = client.get("fantasy_name") or client.get("legal_name") or ""
    doc = {
        "assignment_id": assignment_id,
        "serial": serial,
        "item_id": last_mov.get("item_id"),
        "item_name": last_mov.get("item_name", ""),
        "warehouse_id": last_mov.get("warehouse_id"),
        "quote_id": quote_id or None,
        "quote_number": quote_number,
        "client_id": client_id,
        "client_name": client_name,
        "client_rif": client.get("rif", ""),
        "status": "asignado",
        "assigned_at": now,
        "assigned_by": user.get("user_id"),
        "assigned_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "is_admin_assignment": True,
        "assignment_reason": reason,
    }
    await db.serial_assignments.insert_one(doc)

    await db.bitacora.insert_one({
        "action": "admin_serial_assign",
        "serial": serial,
        "assignment_id": assignment_id,
        "client_id": client_id,
        "client_name": client_name,
        "quote_id": quote_id or None,
        "quote_number": quote_number,
        "warehouse_id": doc["warehouse_id"],
        "reason": reason,
        "executed_by": user.get("email"),
        "executed_at": now,
    })

    return {"ok": True, "assignment_id": assignment_id, "message": f"Serial {serial} asignado a {client_name}"}
