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
    {"id": "proyectos_directos", "label": "Proyectos Directos", "has_sub": False},
]

PRODUCT_SUBCATEGORIES = [
    {"id": "vpos", "label": "VPOS"},
    {"id": "mpos_tablet", "label": "MPOS Tablet"},
    {"id": "mpos_imple_pos", "label": "MPOS Imple+POS"},
    {"id": "payment_gateway", "label": "Payment Gateway"},
    {"id": "link_pago", "label": "Link de Pago"},
]

# Acciones disponibles. Cada acción tiene un id estable + label + lista de PDFs
# que produce hoy (informativo para la UI; en Fase 2 estos PDFs se adjuntarán
# automáticamente cuando la fila tenga `send_pdf_attachments=True`).
ACTIONS = [
    {"id": "send_to_client", "label": "Enviar al Cliente",
     "pdfs_default": ["Cotización (PDF)"]},
    {"id": "approve", "label": "Aprobación",
     "pdfs_default": ["Cálculos Definitivos (PDF)"]},
    {"id": "preassign_serials", "label": "Preasignación de Seriales",
     "pdfs_default": []},
    {"id": "configure", "label": "Configuración",
     "pdfs_default": []},
    {"id": "invoice", "label": "Factura/Proforma",
     "pdfs_default": ["Factura (PDF)"]},
    {"id": "collect", "label": "Cobranza",
     "pdfs_default": []},
    {"id": "send_to_implementation", "label": "Enviar a Implementación",
     "pdfs_default": ["Ficha Técnica (PDF)"]},
    {"id": "deliver", "label": "Marcar como entregada",
     "pdfs_default": ["Nota de Entrega (PDF)"]},
    {"id": "repair_complete", "label": "Reparada",
     "pdfs_default": ["Cálculos Definitivos Reparación (PDF)"]},
]


# Mapping: qué acciones aplican a cada combinación (business_type, product_subcategory).
# Sub-categoría null para tipos sin sub-cats (Equipos, Reparaciones).
# La UI debe mostrar SOLO estas acciones por combinación, no todo el catálogo.
ALLOWED_ACTIONS_BY_BIZ_SUB = {
    ("implementacion_pyme", "vpos"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_pyme", "mpos_tablet"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_pyme", "payment_gateway"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_pyme", "link_pago"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_pyme", "mpos_imple_pos"): [
        "send_to_client", "approve", "preassign_serials", "configure",
        "invoice", "collect", "deliver", "send_to_implementation",
    ],
    ("implementacion_corp", "vpos"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_corp", "mpos_tablet"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_corp", "payment_gateway"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_corp", "link_pago"): [
        "send_to_client", "approve", "invoice", "collect", "send_to_implementation",
    ],
    ("implementacion_corp", "mpos_imple_pos"): [
        "send_to_client", "approve", "preassign_serials", "configure",
        "invoice", "collect", "deliver", "send_to_implementation",
    ],
    ("equipos", None): [
        "send_to_client", "approve", "invoice", "collect", "deliver",
    ],
    ("reparaciones", None): [
        "send_to_client", "approve", "repair_complete", "invoice", "collect", "deliver",
    ],
    ("proyectos_directos", None): [
        "send_to_implementation",
    ],
}


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
        "is_project_template": 1, "is_custom": 1, "group": 1,
    }).to_list(500)
    # Categorización de plantillas para el dropdown del Motor: prioridad
    #   1. Campo explícito `group` (set por el creador al guardar la plantilla)
    #   2. Sufijo `_PYME` / `_CORP` en el `template_id` (legacy)
    #   3. Campo `sede` (PYME/CORP)
    #   4. Flag `is_project_template` o context "implement" → "Implementación"
    #   5. Context heurístico (equip/repair)
    #   6. "General"
    PROJECT_TEMPLATE_IDS = {
        "project_notify_client", "project_notify_bank_client", "project_implementation_initial",
        "implementer_assigned", "implementation_completed", "new_integration_project",
    }
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
        elif t.get("is_project_template") or tid in PROJECT_TEMPLATE_IDS or "implement" in ctx:
            t["category"] = "Implementación"
        elif "equip" in ctx:
            t["category"] = "Equipos"
        elif "repair" in ctx or "reparac" in ctx:
            t["category"] = "Reparaciones"
        else:
            t["category"] = "General"

    # Diccionario: lista de actions permitidas por (biz_type, sub_cat) — el frontend
    # filtra qué acciones mostrar por combinación.
    allowed = {}
    for (biz, sub), action_ids in ALLOWED_ACTIONS_BY_BIZ_SUB.items():
        key = f"{biz}|{sub or '_'}"
        allowed[key] = action_ids

    # Mezclar custom actions del módulo de personalización para que el Motor las
    # exponga como `actions` válidas y permita configurar destinatarios+plantillas.
    custom_actions = await db.quote_custom_actions.find({}, {"_id": 0}).to_list(500)
    actions_extended = list(ACTIONS) + [
        {
            "id": ca["action_id"],
            "label": ca.get("label", ca["action_id"]),
            "is_custom": True,
        }
        for ca in custom_actions if ca.get("enabled", True)
    ]
    # Extender allowed_actions_by_biz_sub para incluir custom actions
    allowed_extended = {k: list(v) for k, v in allowed.items()}
    for ca in custom_actions:
        if not ca.get("enabled", True):
            continue
        biz_id = ca.get("business_type")
        sub_id = ca.get("product_subcategory")
        biz_def = next((b for b in BUSINESS_TYPES if b["id"] == biz_id), None)
        if not biz_def:
            continue
        # Si la custom action no especifica sub, aplica a TODAS las subs del biz
        if biz_def.get("has_sub") and sub_id:
            key = f"{biz_id}|{sub_id}"
            if key in allowed_extended and ca["action_id"] not in allowed_extended[key]:
                allowed_extended[key].append(ca["action_id"])
        elif biz_def.get("has_sub"):
            for k, lst in allowed_extended.items():
                if k.startswith(f"{biz_id}|") and ca["action_id"] not in lst:
                    lst.append(ca["action_id"])
        else:
            key = f"{biz_id}|_"
            if key in allowed_extended and ca["action_id"] not in allowed_extended[key]:
                allowed_extended[key].append(ca["action_id"])

    return {
        "business_types": BUSINESS_TYPES,
        "product_subcategories": PRODUCT_SUBCATEGORIES,
        "actions": actions_extended,
        "allowed_actions_by_biz_sub": allowed_extended,
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
    # Aceptar también action_ids de custom actions (creadas vía /quote-custom-actions)
    custom_action_ids = {ca["action_id"] async for ca in db.quote_custom_actions.find({}, {"_id": 0, "action_id": 1})}
    valid_actions_extended = valid_actions | custom_action_ids
    if payload.action_id not in valid_actions_extended:
        raise HTTPException(status_code=400, detail=f"action_id inválido. Válidos legacy: {sorted(valid_actions)}; custom: {sorted(custom_action_ids)}")
    # Validar que la acción esté permitida para esta combinación (biz, sub).
    # Para custom actions saltamos esta validación porque ellas mismas definen
    # su biz/sub al crearse.
    if payload.action_id in valid_actions:
        allowed_for_combo = ALLOWED_ACTIONS_BY_BIZ_SUB.get(
            (payload.business_type, payload.product_subcategory), []
        )
        if allowed_for_combo and payload.action_id not in allowed_for_combo:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Acción '{payload.action_id}' no aplica a {payload.business_type}"
                    + (f" / {payload.product_subcategory}" if payload.product_subcategory else "")
                    + f". Permitidas: {allowed_for_combo}"
                ),
            )

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


# ==================== FASE 3: Seeder Legacy + Auditoría ====================

# Mapeo de cada (action_id, business_type) → "perfil legacy" sugerido para el seeder.
# - client_field: cliente recibe correo (cuando la acción legacy le envía).
# - template_pattern: nombre de plantilla a buscar (sede primero, luego genérica).
# Las combinaciones NO listadas aquí son acciones internas (admin/ventas/almacén)
# que no podemos pre-poblar sin un mapa user_id explícito — el admin las completa
# manualmente.
LEGACY_CLIENT_FACING = {
    # action_id → list of business_types donde el cliente recibe correo
    "send_to_client": ["implementacion_pyme", "implementacion_corp", "equipos", "reparaciones"],
    "approve":        ["reparaciones"],  # solo en repair se notifica al cliente directo
    "repair_complete": ["reparaciones"],
}

# Patrón de plantilla por (action_id, business_type) — busca primero por sede, luego genérica.
LEGACY_TEMPLATE_PATTERNS = {
    ("send_to_client", "implementacion_pyme"):  ["quote_sent_PYME", "quote_sent"],
    ("send_to_client", "implementacion_corp"):  ["quote_sent_CORP", "quote_sent"],
    ("send_to_client", "equipos"):              ["equipment_sent_PYME", "equipment_sent"],
    ("send_to_client", "reparaciones"):         ["repair_quote_sent_PYME", "repair_quote_sent"],
    ("approve", "reparaciones"):                ["repair_approved_PYME", "repair_approved"],
    ("repair_complete", "reparaciones"):        ["repair_complete_client_PYME", "repair_complete_client"],
}


async def _find_template_id(patterns: list[str]) -> Optional[str]:
    """Busca la primera plantilla cuyo template_id coincida con alguno de los patterns."""
    for p in patterns:
        tpl = await db.email_templates.find_one({"template_id": p}, {"_id": 0, "template_id": 1})
        if tpl:
            return tpl["template_id"]
    return None


@router.post("/action-notifications/seed-legacy")
async def seed_legacy(
    overwrite: bool = False,
    authorization: Optional[str] = Header(None),
):
    """Pre-carga la matriz de configuraciones según el comportamiento legacy.

    Para cada (business_type, sub_category, action_id) permitido:
      - Si la combinación es client-facing (send_to_client / approve_repair /
        repair_complete), pre-llena fila `client_field` con la plantilla
        equivalente al envío legacy.
      - Si NO es client-facing, crea config vacía (skeleton) para que el
        admin la complete con destinatarios internos.

    Por defecto NO sobrescribe configs existentes con recipients ya definidos.
    Pasa `overwrite=true` para forzar regeneración (úsalo con cuidado).
    """
    user = await _require_admin(authorization)
    now = datetime.now(timezone.utc).isoformat()
    created, skipped, updated = 0, 0, 0

    for (biz, sub), action_ids in ALLOWED_ACTIONS_BY_BIZ_SUB.items():
        for action_id in action_ids:
            config_key = _config_key(biz, sub, action_id)
            existing = await db.action_notification_configs.find_one({"config_key": config_key}, {"_id": 0})
            if existing and existing.get("recipients") and not overwrite:
                skipped += 1
                continue

            # Construir recipients según patrón legacy
            recipients: list[dict] = []
            client_facing_biz = LEGACY_CLIENT_FACING.get(action_id, [])
            if biz in client_facing_biz:
                tpl_id = await _find_template_id(
                    LEGACY_TEMPLATE_PATTERNS.get((action_id, biz), [])
                )
                # Solo `send_to_client` adjunta el PDF al cliente (la cotización).
                # En `approve` y `repair_complete` el PDF (Cálculos Definitivos)
                # NUNCA se envía al cliente — es interno para Administración.
                client_send_pdf = action_id == "send_to_client"
                recipients.append({
                    "row_id": f"row_{uuid.uuid4().hex[:8]}",
                    "type": "client_field",
                    "user_id": None,
                    "template_id": tpl_id,
                    "send_pdf_attachments": client_send_pdf,
                })

            doc = {
                "config_key": config_key,
                "business_type": biz,
                "product_subcategory": sub,
                "action_id": action_id,
                "recipients": recipients,
                "auto_seeded": True,
                "updated_at": now,
                "updated_by": user.get("email"),
            }
            res = await db.action_notification_configs.update_one(
                {"config_key": config_key},
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            if res.upserted_id:
                created += 1
            else:
                updated += 1

    # Bitácora
    await db.bitacora.insert_one({
        "action": "action_notifications_seed_legacy",
        "executed_by": user.get("email"),
        "executed_at": now,
        "created": created, "updated": updated, "skipped": skipped,
        "overwrite": overwrite,
    })
    return {
        "message": "Matriz legacy precargada",
        "created": created,
        "updated": updated,
        "skipped_existing": skipped,
        "total_combinations": sum(len(a) for a in ALLOWED_ACTIONS_BY_BIZ_SUB.values()),
    }


@router.get("/action-notifications/audit-log")
async def audit_log(
    limit: int = 50,
    offset: int = 0,
    action_id: Optional[str] = None,
    business_type: Optional[str] = None,
    quote_number: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Reporte de auditoría: lista de despachos del motor dinámico.

    Lee de `db.bitacora` los registros con `action=notification_engine_dispatch`
    y aplica filtros opcionales. Útil para que el admin vea qué correos fueron
    enviados vía el motor (vs. legacy), cuántos destinatarios alcanzó cada
    despacho y qué filas fueron saltadas (con motivo).
    """
    await _require_admin(authorization)

    query: dict = {"action": "notification_engine_dispatch"}
    if action_id:
        query["action_id"] = action_id
    if quote_number:
        query["quote_number"] = quote_number
    if business_type:
        # business_type está embebido en config_key (formato "biz|sub|action")
        query["config_key"] = {"$regex": f"^{business_type}\\|"}
    if date_from or date_to:
        date_q: dict = {}
        if date_from:
            date_q["$gte"] = date_from
        if date_to:
            date_q["$lte"] = date_to + ("T23:59:59" if len(date_to) == 10 else "")
        query["executed_at"] = date_q

    total = await db.bitacora.count_documents(query)
    items = await (
        db.bitacora.find(query, {"_id": 0})
        .sort("executed_at", -1)
        .skip(max(0, offset))
        .limit(min(max(1, limit), 500))
        .to_list(500)
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}

