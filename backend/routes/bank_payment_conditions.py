"""Route module: bank_payment_conditions.py

Módulo "Condiciones Banco/Medio de Pago": biblioteca de tips/condiciones técnicas
por binomio (Banco + Medio de Pago de tipo Setup) para los implementadores.
Gobernado por el módulo RBAC 'condiciones_banco_mediopago'.
"""
# ruff: noqa: F403, F405
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from config import db, require_permission

router = APIRouter()

MODULE = "condiciones_banco_mediopago"
MAX_LEN = 2000


class ConditionPayload(BaseModel):
    bank_id: str
    service_id: str
    conditions: str = ""


@router.get("/banco-mediopago-condiciones/banks")
async def bpc_list_banks(authorization: Optional[str] = Header(None)):
    """Bancos para el selector (gated por el módulo de condiciones, no por 'bancos')."""
    await require_permission(authorization, MODULE, "read")
    banks = await db.banks.find({}, {"_id": 0, "bank_id": 1, "name": 1}).to_list(1000)
    banks.sort(key=lambda b: (b.get("name") or "").lower())
    return banks


@router.get("/banco-mediopago-condiciones/medios-pago")
async def bpc_list_medios_pago(bank_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Medios de Pago que cumplen ESTRICTAMENTE Categoria='Producto' AND Tipo='Setup'
    (en el esquema: service_type='Producto' AND application_type='setup').

    Si se recibe `bank_id`, se filtra además a los medios que ESE banco tiene
    certificados (igual que en Cotizaciones): match por nombre contra los
    `products` del banco, excluyendo los que están en pre_producción."""
    await require_permission(authorization, MODULE, "read")
    docs = await db.services.find(
        {"service_type": "Producto", "application_type": "setup"},
        {"_id": 0, "service_id": 1, "name": 1},
    ).to_list(2000)

    if bank_id:
        bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0, "products": 1})
        certified = {
            (p.get("product_name") or "").strip().lower()
            for p in (bank or {}).get("products", [])
            if not p.get("pre_production")
        }
        docs = [d for d in docs if (d.get("name") or "").strip().lower() in certified]

    docs.sort(key=lambda s: (s.get("name") or "").lower())
    return docs


@router.get("/banco-mediopago-condiciones/condicion")
async def bpc_get_condition(bank_id: str, service_id: str, authorization: Optional[str] = Header(None)):
    """Lee el texto de condiciones del binomio banco+medio de pago (si existe)."""
    await require_permission(authorization, MODULE, "read")
    doc = await db.banco_mediopago_condiciones.find_one(
        {"bank_id": bank_id, "service_id": service_id}, {"_id": 0}
    )
    if not doc:
        return {"exists": False, "bank_id": bank_id, "service_id": service_id, "conditions": ""}
    return {"exists": True, **doc}


@router.post("/banco-mediopago-condiciones/condicion")
async def bpc_save_condition(payload: ConditionPayload, authorization: Optional[str] = Header(None)):
    """Crea/actualiza (upsert) la condición del binomio. Requiere permiso de edición."""
    user = await require_permission(authorization, MODULE, "edit")
    if not payload.bank_id or not payload.service_id:
        raise HTTPException(status_code=400, detail="Debe seleccionar un Banco y un Medio de Pago")
    text = payload.conditions or ""
    if len(text) > MAX_LEN:
        raise HTTPException(status_code=400, detail=f"El texto no puede exceder {MAX_LEN} caracteres")

    # Validar existencia del binomio contra los catálogos
    bank = await db.banks.find_one({"bank_id": payload.bank_id}, {"_id": 0, "name": 1})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    svc = await db.services.find_one(
        {"service_id": payload.service_id, "service_type": "Producto", "application_type": "setup"},
        {"_id": 0, "name": 1},
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Medio de Pago no válido (debe ser Producto/Setup)")

    now = datetime.now(timezone.utc).isoformat()
    await db.banco_mediopago_condiciones.update_one(
        {"bank_id": payload.bank_id, "service_id": payload.service_id},
        {"$set": {
            "bank_id": payload.bank_id,
            "service_id": payload.service_id,
            "bank_name": bank.get("name", ""),
            "service_name": svc.get("name", ""),
            "conditions": text,
            "updated_at": now,
            "updated_by": user.get("user_id"),
        }},
        upsert=True,
    )
    return {"success": True, "bank_id": payload.bank_id, "service_id": payload.service_id, "conditions": text}
