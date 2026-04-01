"""Route module: new_products.py — Pipeline de I+D de Nuevos Productos
   Con control de gobernanza: responsable activo por fase, bitácora restringida,
   y transiciones controladas.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
import logging

from config import db, get_current_user
from models import NewProduct, NewProductCreate, NewProductEvolutionEntry, StatusTransitionLog, BankIntegration

router = APIRouter()

NP_STATUSES = ["Negociación", "DESA", "SQA", "IMPLE", "Promovido"]


async def _log_transition(product_id: str, old_status: str, new_status: str, user: dict):
    """Registra una transición de estado con cálculo de lead time."""
    days_in_phase = None
    if old_status:
        last = await db.np_status_transitions.find_one(
            {"product_id": product_id, "new_status": old_status},
            {"_id": 0, "timestamp": 1},
            sort=[("timestamp", -1)]
        )
        if last and last.get("timestamp"):
            ts = last["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            days_in_phase = (datetime.now(timezone.utc) - ts).days

    entry = StatusTransitionLog(
        product_id=product_id,
        old_status=old_status,
        new_status=new_status,
        user_id=user.get("user_id", ""),
        user_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", ""),
        days_in_previous_phase=days_in_phase,
    )
    doc = entry.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.np_status_transitions.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _log_assignment(product_id: str, assigned_user_id: str, assigned_name: str, role: str, phase: str, assigned_by: dict):
    """Registra una asignación de responsable en el log de auditoría."""
    assigner_name = f"{assigned_by.get('first_name', '')} {assigned_by.get('last_name', '')}".strip() or assigned_by.get("email", "")
    doc = {
        "product_id": product_id,
        "assigned_user_id": assigned_user_id,
        "assigned_name": assigned_name,
        "role": role,
        "phase": phase,
        "assigned_by_user_id": assigned_by.get("user_id", ""),
        "assigned_by_name": assigner_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.np_responsable_assignments.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ==================== CRUD ====================

@router.post("/new-products")
async def create_new_product(body: NewProductCreate, authorization: Optional[str] = Header(None)):
    """Crea un nuevo producto en el pipeline I+D. Estado inicial: Negociación."""
    user = await get_current_user(authorization)

    bank = await db.banks.find_one({"bank_id": body.bank_id}, {"_id": 0, "name": 1})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")

    service = await db.services.find_one({"service_id": body.service_id}, {"_id": 0, "name": 1, "service_id": 1, "tipo_corp": 1})
    if not service:
        raise HTTPException(status_code=404, detail="Medio de pago no encontrado en el catálogo. Créelo primero en Medios de Pago.")

    product = NewProduct(
        service_id=body.service_id,
        service_name=service["name"],
        component_type=body.component_type,
        tipo_corp=service.get("tipo_corp", ""),
        bank_id=body.bank_id,
        bank_name=bank["name"],
        status="Negociación",
        notes=body.notes,
    )
    doc = product.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.new_products.insert_one(doc)
    doc.pop("_id", None)

    # Registrar transición inicial
    await _log_transition(doc["product_id"], "", "Negociación", user)

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
    await db.np_status_transitions.delete_many({"product_id": product_id})
    await db.np_responsable_assignments.delete_many({"product_id": product_id})
    return {"message": "Producto eliminado"}


# ==================== ASIGNACIÓN DE RESPONSABLE ====================

@router.post("/new-products/{product_id}/assign-responsable")
async def assign_responsable(product_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asigna un responsable de fase al producto. Registra auditoría."""
    user = await get_current_user(authorization)

    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    assigned_user_id = body.get("user_id")
    role = body.get("role")  # "Líder de Proyecto" o "Analista SQA"

    if not assigned_user_id or not role:
        raise HTTPException(status_code=400, detail="Se requiere 'user_id' y 'role'")

    if role not in ["Líder de Proyecto", "Analista SQA"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Opciones: 'Líder de Proyecto', 'Analista SQA'")

    # Buscar el usuario a asignar
    target_user = await db.users.find_one({"user_id": assigned_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario a asignar no encontrado")

    assigned_name = f"{target_user.get('first_name', '')} {target_user.get('last_name', '')}".strip() or target_user.get("email", "")

    # Actualizar el producto con el nuevo responsable
    await db.new_products.update_one(
        {"product_id": product_id},
        {"$set": {
            "usuario_responsable_fase": assigned_user_id,
            "responsable_nombre": assigned_name,
            "responsable_role": role,
        }}
    )

    # Registrar en log de auditoría
    await _log_assignment(product_id, assigned_user_id, assigned_name, role, product["status"], user)

    # Registrar en la bitácora de evolución automáticamente
    auto_entry = NewProductEvolutionEntry(
        product_id=product_id,
        comment=f"Asignación de responsable: {assigned_name} como {role}",
        phase=product["status"],
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    auto_doc = auto_entry.model_dump()
    auto_doc["created_at"] = auto_doc["created_at"].isoformat()
    auto_doc["auto_generated"] = True
    await db.new_product_evolution.insert_one(auto_doc)

    updated = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    return updated


@router.get("/new-products/{product_id}/assignments")
async def get_assignments(product_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene el historial de asignaciones de responsables."""
    await get_current_user(authorization)
    assignments = await db.np_responsable_assignments.find(
        {"product_id": product_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    return assignments


# ==================== STATUS CHANGE + HAND-OFF ====================

@router.put("/new-products/{product_id}/status")
async def update_new_product_status(product_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualiza el estado de un producto con control de gobernanza.
    
    Reglas:
    - Negociación → DESA: Requiere asignar un Líder de Proyecto (responsable_user_id + responsable_role)
    - DESA → SQA: Solo el Líder de Proyecto asignado puede mover
    - SQA → IMPLE: Solo el Analista SQA asignado puede mover (validación de calidad)
    """
    user = await get_current_user(authorization)

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

    current_user_id = user.get("user_id", "")
    responsable_id = product.get("usuario_responsable_fase")

    # === GOBERNANZA: Restricciones de transición ===

    # 1. Negociación → DESA: Requiere asignar Líder de Proyecto
    if old_status == "Negociación" and new_status == "DESA":
        resp_user_id = body.get("responsable_user_id")
        if not resp_user_id:
            raise HTTPException(status_code=400, detail="GOBERNANZA: Para mover a DESA debe asignar un Líder de Proyecto")

        # Buscar y asignar el Líder de Proyecto
        target = await db.users.find_one({"user_id": resp_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
        if not target:
            raise HTTPException(status_code=404, detail="Usuario a asignar no encontrado")

        assigned_name = f"{target.get('first_name', '')} {target.get('last_name', '')}".strip() or target.get("email", "")
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {
                "usuario_responsable_fase": resp_user_id,
                "responsable_nombre": assigned_name,
                "responsable_role": "Líder de Proyecto",
            }}
        )
        await _log_assignment(product_id, resp_user_id, assigned_name, "Líder de Proyecto", "DESA", user)

    # 2. DESA → SQA: Solo el Líder de Proyecto puede mover
    elif old_status == "DESA" and new_status == "SQA":
        if responsable_id and current_user_id != responsable_id:
            raise HTTPException(
                status_code=403,
                detail=f"GOBERNANZA: Solo el Líder de Proyecto asignado ({product.get('responsable_nombre', 'N/A')}) puede mover de DESA a SQA"
            )
        # Limpiar responsable al entrar a SQA (el Gerente de SQA asignará al Analista)
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {
                "usuario_responsable_fase": None,
                "responsable_nombre": None,
                "responsable_role": None,
            }}
        )

    # 3. SQA → IMPLE: Solo el Analista SQA asignado puede mover
    elif old_status == "SQA" and new_status == "IMPLE":
        if not responsable_id:
            raise HTTPException(
                status_code=403,
                detail="GOBERNANZA: No hay Analista SQA asignado. El Gerente de SQA debe asignar un analista antes de pasar a IMPLE."
            )
        if current_user_id != responsable_id:
            raise HTTPException(
                status_code=403,
                detail=f"GOBERNANZA: Solo el Analista SQA asignado ({product.get('responsable_nombre', 'N/A')}) puede autorizar el paso a IMPLE"
            )

    # Registrar transición con lead time
    transition = await _log_transition(product_id, old_status, new_status, user)
    days_in_phase = transition.get("days_in_previous_phase")
    days_text = f" (Tiempo transcurrido en fase {old_status}: {days_in_phase} días)" if days_in_phase is not None else ""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    # -- Notificación simulada enriquecida --
    try:
        sales_roles = ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]
        sales_users = await db.users.find(
            {"cargo": {"$in": sales_roles}},
            {"_id": 0, "email": 1, "first_name": 1}
        ).to_list(100)
        recipients = [u["email"] for u in sales_users if u.get("email")]

        if new_status == "IMPLE":
            logging.info(
                f"[EMAIL SIMULADO - CRITICO] El proceso de Integración del Medio de Pago "
                f"'{product['service_name']}', del Banco '{product['bank_name']}', "
                f"ha avanzado a la fase de IMPLE el día {now_str}.{days_text} "
                f"El producto ya está disponible en la ficha del Banco. "
                f"Destinatarios={recipients or 'Sin ejecutivos registrados'}"
            )
        else:
            logging.info(
                f"[EMAIL SIMULADO] El proceso de Integración del Medio de Pago "
                f"'{product['service_name']}', del Banco '{product['bank_name']}', "
                f"ha avanzado a la fase de {new_status} el día {now_str}.{days_text} "
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
            tipo_corp=product.get("tipo_corp", ""),
            status="PreProd",
            notes=f"Promovido desde Pipeline I+D (producto {product_id})",
        )
        intg_doc = integration.model_dump()
        intg_doc["created_at"] = intg_doc["created_at"].isoformat()
        intg_doc["source_product_id"] = product_id

        await db.banks.update_one(
            {"bank_id": bank_id},
            {"$push": {"integrations": intg_doc}}
        )

        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {
                "status": "Promovido",
                "promoted_integration_id": intg_doc["integration_id"],
                "promoted_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        await _log_transition(product_id, "IMPLE", "Promovido", user)
        promoted = True
        logging.info(f"Hand-off ejecutado: '{product['service_name']}' → integración '{intg_doc['integration_id']}' en banco '{product['bank_name']}'")
    else:
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {"status": new_status}}
        )

    updated = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if promoted:
        updated["_handoff"] = True
    return updated


# ==================== STATUS TRANSITIONS LOG ====================

@router.get("/new-products/{product_id}/transitions")
async def get_transitions(product_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene el historial completo de transiciones de estado."""
    await get_current_user(authorization)
    transitions = await db.np_status_transitions.find(
        {"product_id": product_id}, {"_id": 0}
    ).sort("timestamp", -1).to_list(500)
    return transitions


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
    """Agrega entrada a la bitácora. Solo el responsable de la fase activa puede escribir."""
    user = await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # === GOBERNANZA: Solo el responsable de fase puede escribir ===
    responsable_id = product.get("usuario_responsable_fase")
    current_user_id = user.get("user_id", "")
    user_role = user.get("role", "")

    if responsable_id and current_user_id != responsable_id and user_role != "admin":
        responsable_name = product.get("responsable_nombre", "N/A")
        responsable_role = product.get("responsable_role", "N/A")
        raise HTTPException(
            status_code=403,
            detail=f"GOBERNANZA: Solo {responsable_name} ({responsable_role}) puede escribir en la bitácora durante la fase {product['status']}. Su acceso es de Solo Lectura."
        )

    entry = NewProductEvolutionEntry(
        product_id=product_id,
        comment=body.get("comment", ""),
        phase=body.get("phase", product.get("status", "Negociación")),
        date=body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    doc = entry.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["author_user_id"] = current_user_id
    doc["author_name"] = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
    await db.new_product_evolution.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/new-products/{product_id}/evolution/{entry_id}")
async def update_evolution(product_id: str, entry_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualiza una entrada de bitácora. Solo el responsable puede editar."""
    user = await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # === GOBERNANZA ===
    responsable_id = product.get("usuario_responsable_fase")
    current_user_id = user.get("user_id", "")
    user_role = user.get("role", "")

    if responsable_id and current_user_id != responsable_id and user_role != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"GOBERNANZA: Solo el responsable activo ({product.get('responsable_nombre', 'N/A')}) puede modificar la bitácora."
        )

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
    """Elimina una entrada de bitácora. Solo el responsable puede eliminar."""
    user = await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # === GOBERNANZA ===
    responsable_id = product.get("usuario_responsable_fase")
    current_user_id = user.get("user_id", "")
    user_role = user.get("role", "")

    if responsable_id and current_user_id != responsable_id and user_role != "admin":
        raise HTTPException(
            status_code=403,
            detail=f"GOBERNANZA: Solo el responsable activo ({product.get('responsable_nombre', 'N/A')}) puede eliminar entradas de la bitácora."
        )

    result = await db.new_product_evolution.delete_one({"entry_id": entry_id, "product_id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return {"message": "Entrada eliminada"}
