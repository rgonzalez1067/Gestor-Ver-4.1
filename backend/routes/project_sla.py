"""Rutas de Configuración de Tiempos y SLA de Proyectos.

  - GET  /api/project-sla/config            → matriz de días + etapas
  - PUT  /api/project-sla/config            → guarda la matriz
  - GET  /api/project-sla/catalog           → acciones + usuarios + plantillas
  - GET  /api/project-sla/actions           → todas las configs de acción
  - PUT  /api/project-sla/actions           → upsert de una config de acción
  - POST /api/project-sla/evaluate          → corre la evaluación on-demand (QA/admin)
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
import uuid

from config import db, get_current_user
from services.project_sla_engine import (
    STAGE_DEFS, STAGE_KEYS, DEFAULT_THRESHOLDS, SLA_CONFIG_ID,
    SLA_ACTIONS, SLA_ACTION_IDS, SLA_TEMPLATE_VARIABLES,
    get_sla_config, run_sla_evaluation,
)

router = APIRouter(tags=["project-sla"])
logger = logging.getLogger("project-sla")


# ---------- Models ----------
class StageThreshold(BaseModel):
    warning_days: int = 2
    delay_days: int = 4


class SlaConfigPayload(BaseModel):
    stages: dict[str, StageThreshold]


class SlaRecipientRow(BaseModel):
    row_id: str = Field(default_factory=lambda: f"row_{uuid.uuid4().hex[:8]}")
    type: str = "owner"  # owner | external_client | user
    user_id: Optional[str] = None
    template_id: Optional[str] = None
    delivery_channel: str = "email"  # email | inbox


class SlaActionConfigPayload(BaseModel):
    action_id: str
    enabled: bool = True
    recipients: list[SlaRecipientRow] = Field(default_factory=list)


async def _require_auth(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return user


# ---------- Config (matriz) ----------
@router.get("/project-sla/config")
async def get_config(authorization: Optional[str] = Header(None)):
    await _require_auth(authorization)
    cfg = await get_sla_config()
    return {"config": cfg, "stages": STAGE_DEFS}


@router.put("/project-sla/config")
async def save_config(payload: SlaConfigPayload, authorization: Optional[str] = Header(None)):
    user = await _require_auth(authorization)
    stages = {}
    for k in STAGE_KEYS:
        th = payload.stages.get(k)
        if th is None:
            stages[k] = dict(DEFAULT_THRESHOLDS[k])
            continue
        w, d = int(th.warning_days), int(th.delay_days)
        if w < 0 or d < 0:
            raise HTTPException(status_code=400, detail="Los días no pueden ser negativos")
        if d < w:
            raise HTTPException(status_code=400, detail=f"En la etapa '{k}', los días de retraso ({d}) deben ser ≥ a los de advertencia ({w})")
        stages[k] = {"warning_days": w, "delay_days": d}

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "config_id": SLA_CONFIG_ID, "stages": stages, "updated_at": now,
        "updated_by": user.get("email"),
        "updated_by_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", ""),
    }
    await db.project_sla_config.update_one(
        {"config_id": SLA_CONFIG_ID},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    saved = await db.project_sla_config.find_one({"config_id": SLA_CONFIG_ID}, {"_id": 0})
    return saved


# ---------- Catálogo y acciones ----------
@router.get("/project-sla/catalog")
async def get_catalog(authorization: Optional[str] = Header(None)):
    await _require_auth(authorization)

    users = [{
        "user_id": u["user_id"],
        "label": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email", "(sin nombre)"),
        "email": u.get("email", ""),
        "departamento": u.get("departamento", ""),
        "cargo": u.get("cargo", ""),
    } async for u in db.users.find({"is_active": True}, {
        "_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "departamento": 1, "cargo": 1,
    })]

    templates = await db.email_templates.find({}, {
        "_id": 0, "template_id": 1, "name": 1, "subject": 1, "context": 1, "sede": 1, "category": 1, "group": 1,
    }).to_list(500)
    for t in templates:
        if t.get("group"):
            t["category"] = t["group"]
            continue
        tid = (t.get("template_id") or "")
        sede = (t.get("sede") or "").strip().upper()
        ctx = (t.get("context") or "").strip().lower()
        if tid.endswith("_PYME") or sede == "PYME":
            t["category"] = "Pyme"
        elif tid.endswith("_CORP") or sede == "CORP":
            t["category"] = "Corp"
        elif t.get("is_project_template") or "implement" in ctx or "integr" in ctx:
            t["category"] = "Implementación"
        else:
            t["category"] = "General"

    actions = [{**a, "variables": SLA_TEMPLATE_VARIABLES} for a in SLA_ACTIONS]
    return {"actions": actions, "users": users, "templates": templates, "stages": STAGE_DEFS}


@router.get("/project-sla/actions")
async def list_actions(authorization: Optional[str] = Header(None)):
    await _require_auth(authorization)
    items = await db.project_sla_action_configs.find({}, {"_id": 0}).to_list(50)
    return {"items": items, "total": len(items)}


@router.put("/project-sla/actions")
async def upsert_action(payload: SlaActionConfigPayload, authorization: Optional[str] = Header(None)):
    user = await _require_auth(authorization)
    if payload.action_id not in SLA_ACTION_IDS:
        raise HTTPException(status_code=400, detail=f"action_id inválido. Válidos: {sorted(SLA_ACTION_IDS)}")
    for r in payload.recipients:
        if r.type not in ("owner", "external_client", "user"):
            raise HTTPException(status_code=400, detail=f"Tipo de destinatario inválido: {r.type}")
        if r.type == "user" and not r.user_id:
            raise HTTPException(status_code=400, detail="user_id requerido para destinatarios de tipo 'user'")
        if r.delivery_channel not in ("email", "inbox"):
            raise HTTPException(status_code=400, detail=f"delivery_channel inválido: {r.delivery_channel}")
        if r.type == "external_client" and r.delivery_channel == "inbox":
            raise HTTPException(status_code=400, detail="Un cliente externo no puede recibir por Centro de Mensajes (use Correo)")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "action_id": payload.action_id, "enabled": payload.enabled,
        "recipients": [r.model_dump() for r in payload.recipients],
        "updated_at": now, "updated_by": user.get("email"),
    }
    await db.project_sla_action_configs.update_one(
        {"action_id": payload.action_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return await db.project_sla_action_configs.find_one({"action_id": payload.action_id}, {"_id": 0})


@router.post("/project-sla/evaluate")
async def evaluate_now(authorization: Optional[str] = Header(None)):
    """Corre la evaluación SLA on-demand (para QA / verificación inmediata)."""
    await _require_auth(authorization)
    result = await run_sla_evaluation()
    return {"message": "Evaluación SLA ejecutada", **result}
