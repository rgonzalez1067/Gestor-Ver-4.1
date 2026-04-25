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


@router.delete("/new-products/maintenance/promoted")
async def delete_promoted_products(authorization: Optional[str] = Header(None)):
    """Mantenimiento: elimina TODOS los productos en estado 'Promovido' (ya copiados a un banco).
    Limpia también su evolución, transiciones y asignaciones. Solo admin."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar mantenimiento")

    promoted = await db.new_products.find(
        {"status": "Promovido"},
        {"_id": 0, "product_id": 1, "name": 1},
    ).to_list(None)
    ids = [p["product_id"] for p in promoted]
    if not ids:
        return {"deleted_count": 0, "message": "No hay productos promovidos para eliminar.", "deleted": []}

    res = await db.new_products.delete_many({"product_id": {"$in": ids}})
    await db.new_product_evolution.delete_many({"product_id": {"$in": ids}})
    await db.np_status_transitions.delete_many({"product_id": {"$in": ids}})
    await db.np_responsable_assignments.delete_many({"product_id": {"$in": ids}})

    # Bitácora de la acción
    await db.np_maintenance_log.insert_one({
        "action": "purge_promoted",
        "deleted_count": res.deleted_count,
        "product_ids": ids,
        "executed_by": user.get("email"),
        "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "deleted_count": res.deleted_count,
        "message": f"Se eliminaron {res.deleted_count} producto(s) promovido(s) del pipeline.",
        "deleted": [p["name"] for p in promoted],
    }


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

    # Construir equipo completo
    equipo_user_ids = body.get("equipo_user_ids", [])
    equipo_fase = []
    all_ids = list(set(equipo_user_ids)) if equipo_user_ids else [assigned_user_id]
    for uid in all_ids:
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1})
        if u:
            name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email", "")
            equipo_fase.append({"user_id": uid, "name": name, "cargo": u.get("cargo", ""), "email": u.get("email", "")})

    # Actualizar el producto con el nuevo equipo
    await db.new_products.update_one(
        {"product_id": product_id},
        {"$set": {
            "usuario_responsable_fase": assigned_user_id,
            "responsable_nombre": assigned_name,
            "responsable_role": role,
            "equipo_fase": equipo_fase,
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

    # 1. Negociación → DESA: Requiere asignar equipo de Desarrolladores
    if old_status == "Negociación" and new_status == "DESA":
        resp_user_id = body.get("responsable_user_id")
        equipo_user_ids = body.get("equipo_user_ids", [])
        if not resp_user_id:
            raise HTTPException(status_code=400, detail="GOBERNANZA: Para mover a DESA debe asignar al menos un Desarrollador")

        # Construir equipo completo
        equipo_fase = []
        all_ids = list(set(equipo_user_ids)) if equipo_user_ids else [resp_user_id]
        for uid in all_ids:
            target = await db.users.find_one({"user_id": uid}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1})
            if target:
                name = f"{target.get('first_name', '')} {target.get('last_name', '')}".strip() or target.get("email", "")
                equipo_fase.append({"user_id": uid, "name": name, "cargo": target.get("cargo", ""), "email": target.get("email", "")})

        assigned_name = ", ".join([e["name"] for e in equipo_fase])
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {
                "usuario_responsable_fase": resp_user_id,
                "responsable_nombre": equipo_fase[0]["name"] if equipo_fase else assigned_name,
                "responsable_role": "Líder de Proyecto",
                "equipo_fase": equipo_fase,
            }}
        )
        await _log_assignment(product_id, resp_user_id, assigned_name, "Equipo DESA", "DESA", user)

    # 2. DESA → SQA: Solo el equipo DESA puede mover
    elif old_status == "DESA" and new_status == "SQA":
        equipo_ids = [e["user_id"] for e in product.get("equipo_fase", [])]
        if responsable_id:
            equipo_ids.append(responsable_id)
        if equipo_ids and current_user_id not in equipo_ids and user.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="GOBERNANZA: Solo el equipo DESA asignado puede mover de DESA a SQA"
            )
        # Limpiar equipo al entrar a SQA
        await db.new_products.update_one(
            {"product_id": product_id},
            {"$set": {
                "usuario_responsable_fase": None,
                "responsable_nombre": None,
                "responsable_role": None,
                "equipo_fase": [],
            }}
        )

    # 3. SQA → IMPLE: Solo el equipo SQA asignado puede mover
    elif old_status == "SQA" and new_status == "IMPLE":
        equipo_ids = [e["user_id"] for e in product.get("equipo_fase", [])]
        if responsable_id:
            equipo_ids.append(responsable_id)
        if not equipo_ids:
            raise HTTPException(
                status_code=403,
                detail="GOBERNANZA: No hay equipo SQA asignado. Debe asignar analistas antes de pasar a IMPLE."
            )
        if current_user_id not in equipo_ids and user.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="GOBERNANZA: Solo el equipo SQA asignado puede autorizar el paso a IMPLE"
            )

    # Registrar transición con lead time
    transition = await _log_transition(product_id, old_status, new_status, user)
    days_in_phase = transition.get("days_in_previous_phase")
    days_text = f" (Tiempo transcurrido en fase {old_status}: {days_in_phase} días)" if days_in_phase is not None else ""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    # -- Notificación por email a Gerencia de Ventas y Gerente de Implementación --
    try:
        # Destinatarios: Gerentes de Ventas + Gerente de Implementación + Coordinadores
        notify_cargos = ["Gerente", "Coordinador", "Director"]
        notify_deptos = ["Ventas Pyme", "Ventas Corporativas", "Implementación"]
        notify_users = await db.users.find(
            {"is_active": True, "$or": [
                {"cargo": {"$in": notify_cargos}, "departamento": {"$in": notify_deptos}},
                {"cargo": "Director"},
            ]},
            {"_id": 0, "email": 1, "first_name": 1}
        ).to_list(100)
        recipients = list(set([u["email"] for u in notify_users if u.get("email")]))

        # Equipo asignado
        equipo = product.get("equipo_fase", [])
        equipo_html = ""
        if equipo:
            equipo_html = "<ul style='margin:10px 0;padding-left:20px;'>"
            for e in equipo:
                equipo_html += f"<li style='margin:4px 0;'><strong>{e.get('name','')}</strong> — {e.get('cargo','')}</li>"
            equipo_html += "</ul>"
        elif product.get("responsable_nombre"):
            equipo_html = f"<p style='margin:10px 0;'><strong>{product.get('responsable_nombre')}</strong></p>"
        else:
            equipo_html = "<p style='margin:10px 0;color:#94a3b8;'>Por definir</p>"

        service_name = product.get("service_name", "N/A")
        bank_name = product.get("bank_name", "N/A")

        email_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:650px;margin:0 auto;padding:20px;">
          <div style="background:#003366;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;font-size:20px;">Actualización de Nuevos Proyectos</h1>
            <p style="color:#93c5fd;margin:4px 0 0;font-size:14px;">Producto: {service_name} — Banco: {bank_name}</p>
          </div>
          <div style="background:#f8fafc;padding:25px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
            <p style="color:#334155;font-size:14px;">Reciban un cordial saludo.</p>
            <p style="color:#475569;font-size:14px;">
              El día de hoy, el proyecto de Integración del Medio de Pago <strong>{service_name}</strong>,
              para el Banco/Entidad: <strong>{bank_name}</strong>,
              ha pasado al Estatus: <span style="color:#003366;font-weight:bold;font-size:15px;">{new_status}</span>.{days_text}
            </p>
            <p style="color:#475569;font-size:14px;">Será atendido por el siguiente equipo de trabajo:</p>
            {equipo_html}
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
            <p style="color:#94a3b8;font-size:12px;text-align:center;">Sistema de Gestión de Proyectos — Mega Soft</p>
          </div>
        </div>
        """

        if recipients:
            from services.email_service import send_email
            await send_email(
                to=recipients,
                subject=f"Actualización de Nuevos Proyectos - Producto: {service_name} - Banco: {bank_name}",
                html=email_html,
                action="new_product_status_change"
            )
            logging.info(f"[NP] Email de actualización enviado a {len(recipients)} destinatarios para {service_name}/{bank_name} → {new_status}")
        else:
            logging.info(f"[NP] Sin destinatarios para notificación de {service_name}/{bank_name} → {new_status}")
    except Exception as e:
        logging.error(f"Error al enviar notificación de nuevo producto: {e}")

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

    # Push notification (evento #13 Nuevo Producto cambió de fase)
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="new_product_phase_changed",
            title=f"Nuevo Producto: fase {new_status}",
            message=f"{product.get('service_name','')} · Banco {product.get('bank_name','')} · Componente: {product.get('component_type','')}",
            context={},
            link="/new-products",
        )
    except Exception:
        pass

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

    # === GOBERNANZA: Solo equipo asignado, supervisores o admin pueden escribir ===
    responsable_id = product.get("usuario_responsable_fase")
    equipo_ids = [e["user_id"] for e in product.get("equipo_fase", [])]
    if responsable_id:
        equipo_ids.append(responsable_id)
    current_user_id = user.get("user_id", "")
    user_role = user.get("role", "")
    user_cargo = user.get("cargo", "")
    is_supervisor = user_cargo in ("Gerente", "Director")

    if equipo_ids and current_user_id not in equipo_ids and user_role != "admin" and not is_supervisor:
        raise HTTPException(
            status_code=403,
            detail=f"GOBERNANZA: Solo el equipo asignado y supervisores pueden escribir en la bitácora durante la fase {product['status']}."
        )

    # Fecha del sistema (no manipulable)
    system_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = NewProductEvolutionEntry(
        product_id=product_id,
        comment=body.get("comment", ""),
        phase=body.get("phase", product.get("status", "Negociación")),
        date=system_date,  # Siempre fecha del sistema
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
