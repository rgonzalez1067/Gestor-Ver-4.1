"""Action Notifications — Motor Dinámico de Notificaciones (Fase 1).

Endpoints para el nuevo sistema de configuración de acciones que permite al
admin definir, por cada (tipo_negocio, sub_categoria, accion), qué destinatarios
reciben qué plantilla.

Esta fase 1 expone:
  - GET  /action-notifications/catalog       → catálogo de tipos, sub-cats, acciones, usuarios, plantillas.
  - GET  /action-notifications/configs       → todas las configs.
  - GET  /action-notifications/configs/{key} → una config (key = biz_type|sub|action).
  - PUT  /action-notifications/configs       → upsert.
  - DELETE /action-notifications/configs/{key} → eliminar.

NO toca el motor de envío real — eso es Fase 2.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config import db, get_current_user

router = APIRouter(tags=["action-notifications"])
logger = logging.getLogger("action-notifications")


# ---------- Catálogo estático ----------
BUSINESS_TYPES = [
    {"id": "implementacion_pyme", "label": "Implementaciones Pyme", "has_sub": True},
    {"id": "implementacion_corp", "label": "Implementaciones Corp", "has_sub": True},
    {"id": "equipos", "label": "Equipos", "has_sub": False},
    {"id": "reparaciones", "label": "Reparaciones", "has_sub": False},
]

PRODUCT_SUBCATEGORIES = [
    {"id": "vpos", "label": "VPOS"},
    {"id": "mpos_tablet", "label": "MPOS Tablet"},
    {"id": "mpos_imple_pos", "label": "MPOS Imple+POS"},
    {"id": "payment_gateway", "label": "Payment Gateway"},
]

# Acciones disponibles. Cada acción tiene un id estable + label + lista de PDFs
# que produce hoy (informativo para la UI; en Fase 2 estos PDFs se adjuntarán
# automáticamente cuando la fila tenga `send_pdf_attachments=True`).
ACTIONS = [
    {"id": "send_to_client", "label": "Enviar al Cliente",
     "pdfs_default": ["Cotización (PDF)"]},
    {"id": "approve", "label": "Aprobar",
     "pdfs_default": ["Cálculos Definitivos (PDF)"]},
    {"id": "send_to_implementation", "label": "Enviar a Implementación",
     "pdfs_default": ["Ficha Técnica (PDF)"]},
    {"id": "configure", "label": "Configurar",
     "pdfs_default": []},
    {"id": "invoice", "label": "Facturar",
     "pdfs_default": ["Factura (PDF)"]},
    {"id": "collect", "label": "Cobrar",
     "pdfs_default": []},
    {"id": "deliver", "label": "Entregar",
     "pdfs_default": ["Nota de Entrega (PDF)"]},
    {"id": "repair_complete", "label": "Reparada",
     "pdfs_default": ["Cálculos Definitivos Reparación (PDF)"]},
    {"id": "repair_deliver", "label": "Entregar Reparación",
     "pdfs_default": ["Nota de Entrega Reparación (PDF)"]},
]


def _config_key(business_type: str, sub_category: Optional[str], action_id: str) -> str:
    return f"{business_type}|{sub_category or '_'}|{action_id}"


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administrador puede acceder a esta configuración")
    return user


# ---------- Models ----------
class RecipientRow(BaseModel):
    row_id: str = Field(default_factory=lambda: f"row_{uuid.uuid4().hex[:8]}")
    type: str  # "client_field" | "user"
    user_id: Optional[str] = None  # requerido si type=="user"
    template_id: Optional[str] = None
    send_pdf_attachments: bool = True


class ActionConfigPayload(BaseModel):
    business_type: str
    product_subcategory: Optional[str] = None
    action_id: str
    recipients: list[RecipientRow] = Field(default_factory=list)


# ---------- Endpoints ----------
@router.get("/action-notifications/catalog")
async def get_catalog(authorization: Optional[str] = Header(None)):
    """Devuelve catálogo completo: tipos negocio, sub-categorías, acciones,
    usuarios activos del sistema y plantillas agrupadas por sede/contexto.
    """
    await _require_admin(authorization)

    users_cur = db.users.find({"is_active": True}, {
        "_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1,
        "departamento": 1, "cargo": 1, "sede": 1,
    })
    users = [{
        "user_id": u["user_id"],
        "label": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email", "(sin nombre)"),
        "email": u.get("email", ""),
        "departamento": u.get("departamento", ""),
        "cargo": u.get("cargo", ""),
        "sede": u.get("sede", ""),
    } async for u in users_cur]

    templates = await db.email_templates.find({}, {
        "_id": 0, "template_id": 1, "name": 1, "subject": 1,
        "context": 1, "sede": 1, "category": 1, "is_active": 1,
    }).to_list(500)
    # Categorizar plantillas: si tiene `category` lo respeta, si no lo deriva
    # del campo legacy `sede` o `context`.
    for t in templates:
        if not t.get("category"):
            sede = (t.get("sede") or "").upper()
            ctx = (t.get("context") or "").upper()
            if sede == "PYME":
                t["category"] = "Pyme"
            elif sede == "CORP":
                t["category"] = "Corp"
            elif "IMPLEMENT" in ctx:
                t["category"] = "Implementación"
            else:
                t["category"] = "General"

    return {
        "business_types": BUSINESS_TYPES,
        "product_subcategories": PRODUCT_SUBCATEGORIES,
        "actions": ACTIONS,
        "users": users,
        "templates": templates,
    }


@router.get("/action-notifications/configs")
async def list_configs(authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    items = await db.action_notification_configs.find({}, {"_id": 0}).to_list(2000)
    return {"items": items, "total": len(items)}


@router.get("/action-notifications/configs/{config_key}")
async def get_config(config_key: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    cfg = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0})
    if not cfg:
        return {"config_key": config_key, "recipients": [], "exists": False}
    return cfg


@router.put("/action-notifications/configs")
async def upsert_config(payload: ActionConfigPayload, authorization: Optional[str] = Header(None)):
    user = await _require_admin(authorization)

    # Validaciones
    valid_biz = {b["id"] for b in BUSINESS_TYPES}
    if payload.business_type not in valid_biz:
        raise HTTPException(status_code=400, detail=f"business_type inválido. Válidos: {sorted(valid_biz)}")
    biz = next((b for b in BUSINESS_TYPES if b["id"] == payload.business_type), None)
    if biz["has_sub"]:
        valid_sub = {s["id"] for s in PRODUCT_SUBCATEGORIES}
        if payload.product_subcategory not in valid_sub:
            raise HTTPException(status_code=400, detail=f"product_subcategory inválido. Requerido para {payload.business_type}")
    else:
        payload.product_subcategory = None
    valid_actions = {a["id"] for a in ACTIONS}
    if payload.action_id not in valid_actions:
        raise HTTPException(status_code=400, detail=f"action_id inválido. Válidos: {sorted(valid_actions)}")

    for r in payload.recipients:
        if r.type not in ("client_field", "user"):
            raise HTTPException(status_code=400, detail=f"Tipo de destinatario inválido: {r.type}")
        if r.type == "user" and not r.user_id:
            raise HTTPException(status_code=400, detail="user_id requerido para destinatarios de tipo 'user'")

    config_key = _config_key(payload.business_type, payload.product_subcategory, payload.action_id)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "config_key": config_key,
        "business_type": payload.business_type,
        "product_subcategory": payload.product_subcategory,
        "action_id": payload.action_id,
        "recipients": [r.model_dump() for r in payload.recipients],
        "updated_at": now,
        "updated_by": user.get("email"),
        "updated_by_name": (
            f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
        ),
    }
    await db.action_notification_configs.update_one(
        {"config_key": config_key},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    saved = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0})
    return saved


@router.delete("/action-notifications/configs/{config_key}")
async def delete_config(config_key: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    res = await db.action_notification_configs.delete_one({"config_key": config_key})
    return {"deleted": res.deleted_count, "config_key": config_key}
