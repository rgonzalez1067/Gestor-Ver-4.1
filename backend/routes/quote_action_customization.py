"""Personalización del flujo de acciones de cotizaciones (Fase A + B).

- **Override de acciones legacy** (Fase B): permite renombrar el botón,
  desactivarlo o restringir qué cargos pueden ejecutarlo. NO toca side-effects.

- **Acciones Custom** (Fase A): el admin crea una nueva acción que aparece
  en el menú entre las legacy. Su única función es enviar correos según las
  configuraciones del Motor de Notificaciones. NO transiciona estados.
"""
from typing import Optional, List
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import os, uuid

from config import db, get_current_user

router = APIRouter()

# Acciones legacy permitidas para override (NO se pueden borrar, solo
# renombrar/desactivar/permisos).
LEGACY_ACTION_IDS = [
    "send_to_client", "approve", "configure", "repair_complete",
    "invoice", "collect", "deliver", "send_to_implementation",
]

ALLOWED_BIZ_TYPES = [
    "implementacion_pyme", "implementacion_corp", "equipos", "reparaciones",
]


async def _require_admin(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(401, "No autorizado")
    if user.get("role") != "admin":
        raise HTTPException(403, "Solo administradores")
    return user


async def _require_user(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(401, "No autorizado")
    return user


def _build_key(biz: str, sub: Optional[str], action_id: str) -> str:
    return f"{biz}|{sub or '_'}|{action_id}"


# ============================================================================
# MODELS
# ============================================================================

class ActionOverride(BaseModel):
    """Fase B: override de acción legacy."""
    business_type: str
    product_subcategory: Optional[str] = None
    action_id: str
    custom_label: Optional[str] = None  # None = usa label original
    enabled: bool = True
    required_roles: List[str] = Field(default_factory=list)  # vacío = sin restricción extra
    required_cargos: List[str] = Field(default_factory=list)  # cargos puntuales (ej. "Administración")


class CustomAction(BaseModel):
    """Fase A: nueva acción creada por el usuario."""
    action_id: str  # slug único (a-z0-9_)
    business_type: str
    product_subcategory: Optional[str] = None
    label: str  # texto del botón
    position_after: Optional[str] = None  # legacy action_id "approve" / "collect" / etc. None = al final
    enabled: bool = True
    required_roles: List[str] = Field(default_factory=list)
    required_cargos: List[str] = Field(default_factory=list)
    icon: Optional[str] = None  # nombre lucide-react (ej. "Mail")
    color: Optional[str] = None  # tailwind color (ej. "blue", "purple")
    description: Optional[str] = None


# ============================================================================
# OVERRIDES — Fase B
# ============================================================================

@router.get("/quote-action-overrides")
async def list_overrides(authorization: Optional[str] = Header(None)):
    """Lista todos los overrides. Disponible para todos los usuarios (necesario
    para construir el menú en frontend)."""
    await _require_user(authorization)
    items = await db.quote_action_overrides.find({}, {"_id": 0}).to_list(500)
    return {"items": items, "legacy_action_ids": LEGACY_ACTION_IDS}


@router.put("/quote-action-overrides")
async def upsert_override(payload: ActionOverride, authorization: Optional[str] = Header(None)):
    user = await _require_admin(authorization)
    if payload.action_id not in LEGACY_ACTION_IDS:
        raise HTTPException(400, f"action_id no es legacy: {payload.action_id}")
    if payload.business_type not in ALLOWED_BIZ_TYPES:
        raise HTTPException(400, f"business_type inválido: {payload.business_type}")
    config_key = _build_key(payload.business_type, payload.product_subcategory, payload.action_id)
    doc = payload.model_dump()
    doc["config_key"] = config_key
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_by"] = user.get("email")
    await db.quote_action_overrides.update_one(
        {"config_key": config_key},
        {"$set": doc, "$setOnInsert": {"created_at": doc["updated_at"]}},
        upsert=True,
    )
    return {"ok": True, "config_key": config_key}


@router.delete("/quote-action-overrides/{config_key}")
async def delete_override(config_key: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    res = await db.quote_action_overrides.delete_one({"config_key": config_key})
    return {"deleted": res.deleted_count}


# ============================================================================
# CUSTOM ACTIONS — Fase A
# ============================================================================

@router.get("/quote-custom-actions")
async def list_custom_actions(authorization: Optional[str] = Header(None)):
    await _require_user(authorization)
    items = await db.quote_custom_actions.find({}, {"_id": 0}).to_list(500)
    return {"items": items, "legacy_action_ids": LEGACY_ACTION_IDS}


@router.put("/quote-custom-actions")
async def upsert_custom_action(payload: CustomAction, authorization: Optional[str] = Header(None)):
    user = await _require_admin(authorization)
    import re
    if not re.match(r"^[a-z][a-z0-9_]{2,40}$", payload.action_id):
        raise HTTPException(400, "action_id debe ser slug a-z0-9_ (3-40 caracteres, empezar con letra)")
    if payload.action_id in LEGACY_ACTION_IDS:
        raise HTTPException(400, f"action_id reservado: {payload.action_id}")
    if payload.business_type not in ALLOWED_BIZ_TYPES:
        raise HTTPException(400, f"business_type inválido: {payload.business_type}")
    if payload.position_after and payload.position_after not in LEGACY_ACTION_IDS:
        raise HTTPException(400, f"position_after debe ser un legacy action_id válido o null")

    config_key = _build_key(payload.business_type, payload.product_subcategory, payload.action_id)
    doc = payload.model_dump()
    doc["config_key"] = config_key
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_by"] = user.get("email")
    await db.quote_custom_actions.update_one(
        {"config_key": config_key},
        {"$set": doc, "$setOnInsert": {"created_at": doc["updated_at"]}},
        upsert=True,
    )
    return {"ok": True, "config_key": config_key}


@router.delete("/quote-custom-actions/{config_key}")
async def delete_custom_action(config_key: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    res = await db.quote_custom_actions.delete_one({"config_key": config_key})
    return {"deleted": res.deleted_count}


# ============================================================================
# DISPATCH — ejecutar una acción custom para una cotización específica
# ============================================================================

@router.post("/quotes/{quote_id}/custom-action/{action_id}")
async def dispatch_custom_action(
    quote_id: str,
    action_id: str,
    payload: dict = None,
    authorization: Optional[str] = Header(None),
):
    """Dispara una acción custom: envía correos según la matriz del Motor de
    Notificaciones para la combinación (biz × sub × action_id).

    No transiciona estado de la cotización. Solo registra en bitácora.

    Body opcional: { custom_message: str, additional_recipients: str }
    """
    user = await _require_user(authorization)
    payload = payload or {}

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(404, "Cotización no encontrada")

    # Resolver biz/sub
    from services.notification_engine import _quote_to_biz_sub, try_dispatch, validate_client_email_required
    biz, sub = _quote_to_biz_sub(quote)
    if not biz:
        raise HTTPException(400, "No se pudo mapear el tipo de cotización")

    # Verificar que la custom action exista y esté activa
    config_key = _build_key(biz, sub, action_id)
    custom = await db.quote_custom_actions.find_one({"config_key": config_key}, {"_id": 0})
    if not custom:
        # También aceptamos coincidencia por sub=None (acción global del biz)
        custom = await db.quote_custom_actions.find_one(
            {"action_id": action_id, "business_type": biz, "product_subcategory": None}, {"_id": 0}
        )
    if not custom or not custom.get("enabled", True):
        raise HTTPException(404, f"Acción custom '{action_id}' no encontrada o inactiva para esta cotización")

    # Verificar permisos (cargo o role)
    user_role = user.get("role", "")
    user_cargo = user.get("cargo", "")
    req_roles = custom.get("required_roles") or []
    req_cargos = custom.get("required_cargos") or []
    if req_roles and user_role not in req_roles:
        raise HTTPException(403, f"Tu rol ({user_role}) no puede ejecutar esta acción")
    if req_cargos and user_cargo not in req_cargos:
        raise HTTPException(403, f"Tu cargo ({user_cargo}) no puede ejecutar esta acción")

    # Validar email del cliente si la config dinámica lo requiere
    warn = await validate_client_email_required(action_id, quote)
    if warn:
        raise HTTPException(400, warn)

    custom_message = payload.get("custom_message") or None
    additional_recipients = payload.get("additional_recipients") or ""
    cc_emails = [e.strip() for e in additional_recipients.split(",") if e.strip() and "@" in e.strip()]

    dispatched = await try_dispatch(
        action_id, quote, user,
        custom_message=custom_message,
        cc_emails=cc_emails,
    )

    if not dispatched:
        raise HTTPException(
            400,
            f"No se ha configurado destinatarios para la acción '{custom.get('label', action_id)}'. "
            "Configúralos primero en el Motor de Notificaciones."
        )

    return {
        "ok": True,
        "action_id": action_id,
        "label": custom.get("label", action_id),
        "message": f"Acción '{custom.get('label', action_id)}' ejecutada correctamente",
    }
