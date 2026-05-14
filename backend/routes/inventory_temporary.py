"""Route module: inventory_temporary.py — Asignaciones Temporales de Inventario.

Permite asignar ítems (con o sin serial) a un responsable de forma transitoria
(pruebas, demos, uso interno) y devolverlos posteriormente al stock.

Flujo:
  1. POST /inventory/temporary-assignments
     - Crea registro en `temporary_assignments` (status="asignado")
     - Genera movement_type="salida_temporal" en inventory_movements (descuenta stock)
     - Bloquea seriales en serial_assignments (status="asignado_temporal")
  2. POST /inventory/temporary-assignments/{id}/return
     - Marca asignación status="devuelto"
     - Genera movement_type="entrada_temporal" en inventory_movements (reingresa stock)
     - Libera seriales en serial_assignments

Indicadores visuales:
  - Items con asignaciones activas se resaltan en frontend (UX).
  - Asignaciones con más de 15 días disparan alerta visual (overdue).
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import logging
import uuid

from config import db, get_current_user
from models import InventoryMovement
from routes.inventory import (
    is_serialized,
    validate_warehouse_jurisdiction,
    _get_item_stock,
    check_stock_alert,
)

router = APIRouter()
logger = logging.getLogger(__name__)

OVERDUE_DAYS = 15


def _user_display(u: dict) -> str:
    if not u:
        return ""
    name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return name or u.get("email", "")


# ==================== CREATE TEMPORARY ASSIGNMENT ====================

@router.post("/inventory/temporary-assignments")
async def create_temporary_assignment(body: dict, authorization: Optional[str] = Header(None)):
    """Asigna temporalmente un ítem a un responsable. Descuenta del stock disponible."""
    user = await get_current_user(authorization)

    warehouse_id = body.get("warehouse_id")
    item_id = body.get("item_id")
    quantity = int(body.get("quantity") or 0)
    serials: List[str] = body.get("serials") or []
    responsible_user_id = body.get("responsible_user_id")
    responsible_external_name = (body.get("responsible_external_name") or "").strip()
    is_external = bool(body.get("is_external_responsible")) or responsible_user_id == "external"
    assigned_date = body.get("assigned_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reason = (body.get("reason") or "").strip()

    if not warehouse_id or not item_id or quantity <= 0:
        raise HTTPException(400, "warehouse_id, item_id y quantity > 0 son obligatorios")
    if is_external:
        if not responsible_external_name:
            raise HTTPException(400, "Indique el nombre del responsable externo")
    else:
        if not responsible_user_id:
            raise HTTPException(400, "Debe indicar el responsable")
    if not reason:
        raise HTTPException(400, "El motivo/descripción es obligatorio")
    if len(reason) > 500:
        raise HTTPException(400, "El motivo no puede exceder 500 caracteres")

    await validate_warehouse_jurisdiction(user, warehouse_id)

    wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(404, "Almacén no encontrado")

    item = await db.hardware.find_one({"hardware_id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Ítem no encontrado")
    requires_serial = is_serialized(item.get("type", ""))

    responsible = None
    responsible_name = ""
    responsible_email = ""
    if is_external:
        responsible_name = responsible_external_name
        responsible_email = ""
    else:
        responsible = await db.users.find_one({"user_id": responsible_user_id}, {"_id": 0})
        if not responsible:
            raise HTTPException(404, "Responsable no encontrado")
        responsible_name = _user_display(responsible)
        responsible_email = responsible.get("email", "")

    # Validar stock disponible (idéntico patrón a create_exit)
    stock = await _get_item_stock(warehouse_id, item_id)
    if stock["quantity"] < quantity:
        raise HTTPException(400, f"Stock insuficiente. Disponible: {stock['quantity']}, Solicitado: {quantity}")

    if requires_serial:
        if len(serials) != quantity:
            raise HTTPException(400, f"Debe seleccionar exactamente {quantity} serial(es)")
        for s in serials:
            if s not in stock.get("serials", []):
                raise HTTPException(400, f"Serial '{s}' no disponible en este almacén")

    now = datetime.now(timezone.utc)
    assignment_id = f"tmp_{uuid.uuid4().hex[:10]}"

    # 1) Registrar movimiento salida_temporal en kardex
    movement = InventoryMovement(
        warehouse_id=warehouse_id,
        item_id=item_id,
        item_name=item["name"],
        item_type=item.get("type", "General"),
        movement_type="salida_temporal",
        quantity=quantity,
        unit_cost=stock.get("weighted_cost", item.get("price_usd", 0)),
        serials=serials if requires_serial else [],
        reference=f"Asignación temporal #{assignment_id}",
        client_name=responsible_name,
        notes=f"[TEMPORAL] {reason}",
        created_by=_user_display(user),
    )
    mov_doc = movement.model_dump()
    mov_doc["created_at"] = mov_doc["created_at"].isoformat()
    mov_doc["temporary_assignment_id"] = assignment_id
    mov_doc["is_temporary"] = True
    await db.inventory_movements.insert_one(mov_doc)
    exit_movement_id = mov_doc["movement_id"]

    # 2) Crear registro de asignación temporal
    assignment = {
        "assignment_id": assignment_id,
        "item_id": item_id,
        "item_name": item["name"],
        "item_type": item.get("type", "General"),
        "warehouse_id": warehouse_id,
        "warehouse_name": wh.get("name", ""),
        "quantity": quantity,
        "serials": serials if requires_serial else [],
        "responsible_user_id": None if is_external else responsible_user_id,
        "responsible_name": responsible_name,
        "responsible_email": responsible_email,
        "is_external_responsible": is_external,
        "assigned_date": assigned_date,
        "reason": reason,
        "status": "asignado",
        "created_at": now.isoformat(),
        "created_by": user.get("user_id", ""),
        "created_by_name": _user_display(user),
        "exit_movement_id": exit_movement_id,
        "return_movement_id": None,
        "returned_at": None,
        "returned_by": None,
        "returned_by_name": None,
        "return_notes": None,
    }
    await db.temporary_assignments.insert_one(assignment)
    assignment.pop("_id", None)

    # 3) Bloquear seriales (si serializado) en serial_assignments
    if requires_serial and serials:
        bulk_docs = []
        for s in serials:
            bulk_docs.append({
                "assignment_id_ref": assignment_id,
                "serial": s,
                "item_id": item_id,
                "status": "asignado_temporal",
                "responsible_name": responsible_name,
                "created_at": now.isoformat(),
            })
        if bulk_docs:
            await db.serial_assignments.insert_many(bulk_docs)

    logger.info(
        f"[temp_assign] Created {assignment_id} item={item_id} qty={quantity} "
        f"responsible={responsible_email} by={user.get('email')}"
    )
    return assignment


# ==================== RETURN (Devolución) ====================

@router.post("/inventory/temporary-assignments/{assignment_id}/return")
async def return_temporary_assignment(
    assignment_id: str,
    body: Optional[dict] = None,
    authorization: Optional[str] = Header(None),
):
    """Devuelve el ítem al stock. Acepta {return_notes: str} opcional."""
    user = await get_current_user(authorization)

    assignment = await db.temporary_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    if not assignment:
        raise HTTPException(404, "Asignación temporal no encontrada")
    if assignment.get("status") == "devuelto":
        raise HTTPException(400, "Esta asignación ya fue devuelta")

    await validate_warehouse_jurisdiction(user, assignment["warehouse_id"])

    now = datetime.now(timezone.utc)
    return_notes = ((body or {}).get("return_notes") or "").strip()

    # 1) Registrar movimiento entrada_temporal (reingresa stock)
    movement = InventoryMovement(
        warehouse_id=assignment["warehouse_id"],
        item_id=assignment["item_id"],
        item_name=assignment["item_name"],
        item_type=assignment.get("item_type", "General"),
        movement_type="entrada_temporal",
        quantity=assignment["quantity"],
        unit_cost=0,  # no afecta costo (es reingreso de algo que ya estaba contabilizado)
        serials=assignment.get("serials", []),
        reference=f"Devolución asignación #{assignment_id}",
        client_name=assignment.get("responsible_name", ""),
        notes=f"[DEVOLUCIÓN] {return_notes}" if return_notes else "[DEVOLUCIÓN]",
        created_by=_user_display(user),
    )
    mov_doc = movement.model_dump()
    mov_doc["created_at"] = mov_doc["created_at"].isoformat()
    mov_doc["temporary_assignment_id"] = assignment_id
    mov_doc["is_temporary"] = True
    await db.inventory_movements.insert_one(mov_doc)
    return_movement_id = mov_doc["movement_id"]

    # 2) Actualizar asignación
    await db.temporary_assignments.update_one(
        {"assignment_id": assignment_id},
        {"$set": {
            "status": "devuelto",
            "returned_at": now.isoformat(),
            "returned_by": user.get("user_id", ""),
            "returned_by_name": _user_display(user),
            "return_notes": return_notes,
            "return_movement_id": return_movement_id,
        }},
    )

    # 3) Liberar seriales bloqueados
    if assignment.get("serials"):
        await db.serial_assignments.delete_many({
            "assignment_id_ref": assignment_id,
            "status": "asignado_temporal",
        })

    # 4) Si el ítem queda por debajo de min stock, dispara alerta (mismo patrón que exits)
    try:
        await check_stock_alert(
            assignment["warehouse_id"],
            assignment["item_id"],
            assignment["item_name"],
        )
    except Exception:
        pass

    logger.info(
        f"[temp_assign] Returned {assignment_id} by {user.get('email')} "
        f"return_movement={return_movement_id}"
    )
    updated = await db.temporary_assignments.find_one({"assignment_id": assignment_id}, {"_id": 0})
    return updated


# ==================== LIST / FILTER ====================

@router.get("/inventory/temporary-assignments")
async def list_temporary_assignments(
    status: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    item_id: Optional[str] = None,
    responsible_user_id: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Lista asignaciones temporales con filtros opcionales.
    `status` acepta: 'asignado' | 'devuelto' | 'overdue' (asignado >15 días).
    """
    await get_current_user(authorization)

    query: dict = {}
    overdue_only = False
    if status == "overdue":
        query["status"] = "asignado"
        overdue_only = True
    elif status in ("asignado", "devuelto"):
        query["status"] = status

    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    if item_id:
        query["item_id"] = item_id
    if responsible_user_id:
        query["responsible_user_id"] = responsible_user_id

    cursor = db.temporary_assignments.find(query, {"_id": 0}).sort("created_at", -1)
    items = await cursor.to_list(2000)

    # Enriquecer con flag overdue y días transcurridos
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=OVERDUE_DAYS)
    enriched = []
    for a in items:
        days_out = None
        is_overdue = False
        if a.get("status") == "asignado":
            try:
                created = datetime.fromisoformat(a["created_at"])
                days_out = (now - created).days
                is_overdue = created < threshold
            except Exception:
                pass
        a["days_out"] = days_out
        a["is_overdue"] = is_overdue
        if overdue_only and not is_overdue:
            continue
        enriched.append(a)

    return enriched


@router.get("/inventory/temporary-assignments/active-by-item")
async def get_active_assignments_by_item(authorization: Optional[str] = Header(None)):
    """Devuelve un mapa { item_id: [assignments_activas] } para resaltar
    en la UI los ítems con asignaciones activas (indicador naranja)."""
    await get_current_user(authorization)
    cursor = db.temporary_assignments.find(
        {"status": "asignado"}, {"_id": 0}
    )
    items = await cursor.to_list(2000)
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=OVERDUE_DAYS)
    by_item: dict = {}
    for a in items:
        try:
            created = datetime.fromisoformat(a["created_at"])
            a["is_overdue"] = created < threshold
            a["days_out"] = (now - created).days
        except Exception:
            a["is_overdue"] = False
            a["days_out"] = None
        by_item.setdefault(a["item_id"], []).append(a)
    return by_item
