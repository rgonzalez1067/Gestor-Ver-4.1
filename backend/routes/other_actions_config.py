"""Configuración de otras Acciones — Motor Dinámico para acciones NO ligadas a
cotizaciones.

Permite al admin definir, por cada acción registrada (cambio de fase de Nuevos
Productos, creación de Proyecto de Integración), qué usuarios internos reciben
qué plantilla y por qué canal (Correo / Centro de Mensajes), además de un toggle
global de activación.

Endpoints:
  - GET    /api/other-actions/catalog          → acciones + usuarios + plantillas.
  - GET    /api/other-actions/configs          → todas las configs.
  - GET    /api/other-actions/configs/{action} → una config.
  - PUT    /api/other-actions/configs          → upsert.

La RBAC se aplica vía middleware (módulo `config_otras_acciones`).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config import db, get_current_user

router = APIRouter(tags=["other-actions"])
logger = logging.getLogger("other-actions")


# Variables disponibles para las 3 acciones de cambio de estado de Proyecto.
# Incluyen el comentario del modal de justificación ({Comentario_Estado} y su
# alias {Comentario_Cierre}) más el universo de variables de Proyecto
# (resueltas por services.project_template_vars.resolve_project_template_vars).
_PROJECT_STATUS_VARS = [
    "Comentario_Estado", "Comentario_Cierre", "Estado_Proyecto",
    "Nombre_Cliente", "Nombre_Fantasia", "Rif_Cliente", "Contacto_Principal",
    "Nro_Proyecto", "Nro_Ticket", "Tipo_Proyecto", "Patrocinador",
    "Nombre_Implementador", "Correo_Implementador",
    "Matriz_Bancos_Productos", "Matriz_Sucursales",
    "Matriz_Avance_Proyecto", "Matriz_Avance_Proyecto_Con_Fecha",
    "Matriz_Seguimiento_Evolutiva",
    "usuario_ejecutor", "fecha_sistema",
]


# Catálogo de "otras acciones" desacopladas del hardcode. Cada acción documenta
# las variables disponibles para usar en la plantilla seleccionada.
OTHER_ACTIONS = [
    {
        "id": "new_product_phase_change",
        "label": "Cambio de Estado o Fase de Nuevos Productos",
        "description": "Se dispara al crear un producto y en cada cambio de fase del ciclo completo: Negociación → DESA → SQA → IMPLE y las fases de Implementación (PreProd → Primer Prod → Masificación).",
        "variables": [
            "nombre_producto", "nombre_banco", "fase_actual", "nueva_fase", "dias_fase_saliente",
            "dias_totales_proyecto", "responsable_fase_entrante", "tipo_evento",
            "componente", "estatus", "estatus_anterior", "dias_en_fase", "equipo_trabajo", "usuario_responsable", "fecha_sistema",
        ],
    },
    {
        "id": "new_integration_project",
        "label": "Creación de un Nuevo Proyecto de Integración",
        "description": "Se dispara al dar de alta un Proyecto de Integración (alta de integrador).",
        "variables": [
            "nombre_integrador", "tipo_integracion", "nombre_aplicativo",
            "nombre_responsable", "email_responsable", "telefono_responsable",
            "usuario_creador", "fecha_sistema",
            "Productos_Certificar_Integrador", "Productos_nuevos",
        ],
    },
    {
        "id": "implementer_assignment",
        "label": "Asignación del Implementador en Proyecto de Integración",
        "description": "Se dispara al asignar un implementador a un proyecto de integración.",
        "variables": [
            "nombre_implementador", "email_implementador", "nombre_integrador",
            "nombre_aplicativo", "tipo_integracion", "tipo_integrador",
            "asignado_por", "contactos_tecnicos", "fecha_sistema",
        ],
    },
    {
        "id": "cotizacion_equipos_infra",
        "label": "Cotización Equipos Infra",
        "description": "Se dispara al confirmar 'Enviar al Cliente' una cotización de un cliente Corporativo cuando el operador indica que la cotización incluye Equipos de Infraestructura. Notifica a usuarios internos del sistema (correo o Centro de Mensajes) según la plantilla configurada.",
        "variables": [
            "Nombre_Cliente", "Rif_Cliente", "Cotizacion_Nro", "Cantidad_Cajas",
            "Nombre_Ejecutivo", "Email_Ejecutivo", "Contacto_Principal",
            "nombre_cliente", "nombre_fantasia", "rif_cliente", "numero_cotizacion",
            "segmento", "monto_total_usd", "ejecutivo", "usuario_ejecutor", "fecha_sistema",
        ],
    },
    {
        "id": "implementer_response",
        "label": "Respuesta del Implementador",
        "description": "Se dispara automáticamente (en background) cuando un usuario con rol de Implementador registra el 'Nro de Ticket' en un Proyecto (transición de vacío a un valor) y guarda el formulario.",
        "variables": [
            "project_number", "Nro_Proyecto", "ticket_number", "Nro_Ticket",
            "client_name", "Nombre_Cliente", "Nombre_Implementador", "Correo_Implementador",
            "assigned_to", "quote_number", "usuario_ejecutor", "fecha_sistema",
        ],
    },
    {
        "id": "project_status_suspendido",
        "label": "Notificación de Proyecto Suspendido",
        "description": "Se dispara (en background) en el momento exacto en que el estado de un Proyecto se actualiza a 'Suspendido', justo después de que el operador confirma el modal de justificación (comentario + anexo). El comentario viaja en {Comentario_Estado}.",
        "variables": _PROJECT_STATUS_VARS,
    },
    {
        "id": "project_status_implementado_parcial",
        "label": "Notificación de Proyecto Implementado Parcial",
        "description": "Se dispara (en background) cuando un Proyecto se guarda con el estado 'Implementado parcial', tras confirmar el modal de justificación. El comentario viaja en {Comentario_Estado}.",
        "variables": _PROJECT_STATUS_VARS,
    },
    {
        "id": "project_status_culminado",
        "label": "Notificación de Proyecto Culminado",
        "description": "Se dispara (en background) cuando el operador consolida el cierre del caso y el estado se actualiza a 'Culminado', tras confirmar el modal de justificación. El comentario de cierre viaja en {Comentario_Estado}.",
        "variables": _PROJECT_STATUS_VARS,
    },
    {
        "id": "integration_project_closed",
        "label": "Cierre de Proyecto de Integración",
        "description": "Se dispara al presionar el botón 'Cerrar Proyecto' de un Proyecto de Integración (ficha del Integrador) y confirmar la acción. Notifica a los usuarios parametrizados (correo o Centro de Mensajes) según la plantilla configurada.",
        "variables": [
            "nombre_integrador", "Integrador", "integrator_name",
            "nombre_aplicativo", "app_name", "tipo_integracion", "tipo_integrador",
            "modalidad_integracion", "nombre_implementador", "Nombre_Implementador",
            "email_implementador", "Correo_Implementador",
            "componente", "Componente", "version_componente", "Version_Componente",
            "Productos", "Productos_Certificados", "Medios_Certificados",
            "cerrado_por", "Cerrado_Por", "usuario_ejecutor", "fecha_sistema", "Fecha_Sistema",
        ],
    },
    {
        "id": "integration_project_suspended",
        "label": "Suspensión de Proyecto de Integración",
        "description": "Se dispara al presionar 'Suspender Proyecto' en la ficha de un Proyecto de Integración activo (pantalla de Integradores). El proyecto pasa a estatus 'Suspendido'.",
        "variables": [
            "nombre_integrador", "Integrador", "integrator_name",
            "nombre_aplicativo", "app_name", "tipo_integracion", "tipo_integrador",
            "modalidad_integracion", "nombre_implementador", "Nombre_Implementador",
            "email_integrador", "Correo_Integrador",
            "usuario_ejecutor", "fecha_sistema", "Fecha_Sistema",
        ],
    },
    {
        "id": "integration_project_reactivated",
        "label": "Reactivación de Proyecto de Integración",
        "description": "Se dispara al presionar 'Reactivar Proyecto' en un Proyecto de Integración suspendido (pantalla de Integradores). El proyecto vuelve a estatus 'En proceso'.",
        "variables": [
            "nombre_integrador", "Integrador", "integrator_name",
            "nombre_aplicativo", "app_name", "tipo_integracion", "tipo_integrador",
            "modalidad_integracion", "nombre_implementador", "Nombre_Implementador",
            "email_integrador", "Correo_Integrador",
            "usuario_ejecutor", "fecha_sistema", "Fecha_Sistema",
        ],
    },
    {
        "id": "test_environment_expired",
        "label": "Vencimiento de Ambiente de Pruebas",
        "description": "Se dispara automáticamente (en background) cuando el contador de días hábiles de una 'Asignación de Ambiente de Prueba' llega a cero (0), es decir, al alcanzar la Fecha Final de vigencia. Notifica a los usuarios parametrizados (correo o Centro de Mensajes) según la plantilla configurada.",
        "variables": [
            "nombre_integrador", "Integrador", "integrator_name",
            "nombre_aplicativo", "app_name", "tipo_integracion", "tipo_integrador",
            "nombre_implementador", "Nombre_Implementador", "email_implementador", "Correo_Implementador",
            "fecha_inicio_ambiente", "Fecha_Inicio_Ambiente",
            "fecha_fin_ambiente", "Fecha_Fin_Ambiente",
            "usuario_ejecutor", "fecha_sistema", "Fecha_Sistema",
        ],
    },
]
OTHER_ACTION_IDS = {a["id"] for a in OTHER_ACTIONS}


# ---------- Models ----------
class RecipientRow(BaseModel):
    row_id: str = Field(default_factory=lambda: f"row_{uuid.uuid4().hex[:8]}")
    type: str = "user"  # sólo usuarios internos (no hay correo de cliente)
    user_id: Optional[str] = None
    template_id: Optional[str] = None
    send_pdf_attachments: bool = False
    delivery_channel: str = "email"  # "email" | "inbox"


class OtherActionConfigPayload(BaseModel):
    action_id: str
    enabled: bool = True
    recipients: list[RecipientRow] = Field(default_factory=list)


async def _require_auth(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    return user


# ---------- Endpoints ----------
@router.get("/other-actions/catalog")
async def get_catalog(authorization: Optional[str] = Header(None)):
    """Acciones disponibles + usuarios internos activos + plantillas (agrupadas)."""
    await _require_auth(authorization)

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
    # Orden alfabético estricto (A-Z) por nombre para agilizar la búsqueda.
    users.sort(key=lambda u: (u.get("label") or "").lower())

    templates = await db.email_templates.find({}, {
        "_id": 0, "template_id": 1, "name": 1, "subject": 1,
        "context": 1, "sede": 1, "category": 1, "group": 1,
    }).to_list(500)
    # Categorización para el dropdown (mismo criterio que action_notifications).
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

    return {"actions": OTHER_ACTIONS, "users": users, "templates": templates}


@router.get("/other-actions/configs")
async def list_configs(authorization: Optional[str] = Header(None)):
    await _require_auth(authorization)
    items = await db.other_action_configs.find({}, {"_id": 0}).to_list(100)
    return {"items": items, "total": len(items)}


@router.get("/other-actions/configs/{action_id}")
async def get_config(action_id: str, authorization: Optional[str] = Header(None)):
    await _require_auth(authorization)
    cfg = await db.other_action_configs.find_one({"action_id": action_id}, {"_id": 0})
    if not cfg:
        return {"action_id": action_id, "enabled": True, "recipients": [], "exists": False}
    return cfg


@router.put("/other-actions/configs")
async def upsert_config(payload: OtherActionConfigPayload, authorization: Optional[str] = Header(None)):
    user = await _require_auth(authorization)
    if payload.action_id not in OTHER_ACTION_IDS:
        raise HTTPException(status_code=400, detail=f"action_id inválido. Válidos: {sorted(OTHER_ACTION_IDS)}")

    ALLOWED_RECIPIENT_TYPES = {"user", "session_user", "session_executive", "project_implementer", "integrator_user"}
    for r in payload.recipients:
        if r.type not in ALLOWED_RECIPIENT_TYPES:
            raise HTTPException(status_code=400, detail=f"Tipo de destinatario inválido: {r.type}")
        if r.type == "user" and not r.user_id:
            raise HTTPException(status_code=400, detail="user_id requerido para destinatarios de tipo 'user'")
        if r.delivery_channel not in ("email", "inbox"):
            raise HTTPException(status_code=400, detail=f"delivery_channel inválido: {r.delivery_channel}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "action_id": payload.action_id,
        "enabled": payload.enabled,
        "recipients": [r.model_dump() for r in payload.recipients],
        "updated_at": now,
        "updated_by": user.get("email"),
        "updated_by_name": (
            f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
        ),
    }
    await db.other_action_configs.update_one(
        {"action_id": payload.action_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    saved = await db.other_action_configs.find_one({"action_id": payload.action_id}, {"_id": 0})
    return saved
