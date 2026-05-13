"""Helpers compartidos para el flujo de cotizaciones.

Extraído de `quote_actions.py` para desacoplar lógica de soporte (flujo regular/irregular,
auditoría, caché de plantillas) del enrutador HTTP.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr
import uuid

from config import db
from routes.seed_and_templates import generate_email_templates_by_sede


# === Plantillas ==========================================================

# Cache de plantillas por defecto (generadas desde código)
_DEFAULT_TEMPLATES_CACHE = None


async def get_email_template(template_id: str) -> Optional[dict]:
    """Busca plantilla primero en la BD, luego en los defaults generados por código."""
    global _DEFAULT_TEMPLATES_CACHE
    # 1. Buscar en MongoDB
    tpl = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    if tpl:
        return tpl
    # 2. Buscar en defaults generados por código
    if _DEFAULT_TEMPLATES_CACHE is None:
        _DEFAULT_TEMPLATES_CACHE = generate_email_templates_by_sede()
    default_tpl = _DEFAULT_TEMPLATES_CACHE.get(template_id)
    if default_tpl:
        return default_tpl
    return None


# === Modelos de request ==================================================

class QuoteStatusUpdate(BaseModel):
    new_status: str


class EmailSendRequest(BaseModel):
    quote_id: str
    recipient_email: EmailStr
    subject: Optional[str] = None
    message: Optional[str] = None


# === Flujo regular / irregular ===========================================

# Flujo regular: Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Entregada/Implementación
REGULAR_FLOW = {
    'approve': 'Enviada',
    'invoice': 'Aprobada',
    'collect': 'Facturada',
    'deliver': 'Pagada',
    'send_implementation': 'Pagada',
}
# NOTE: preserved verbatim from quote_actions.py (collect follows invoice status)

STATUS_ORDER = ['Borrador', 'Enviada', 'Aprobada', 'Facturada', 'Pagada', 'Entregada', 'En Implementación']


def get_status_index(status: str) -> int:
    """Obtiene el índice de un estado en el flujo normal."""
    if status in STATUS_ORDER:
        return STATUS_ORDER.index(status)
    return -1


def is_regularization(current_status: str, action: str) -> bool:
    """Determina si la acción es una regularización (el estado actual ya superó el paso)."""
    action_result = {'approve': 'Aprobada', 'invoice': 'Facturada', 'collect': 'Pagada'}
    result_status = action_result.get(action)
    if not result_status:
        return False
    return get_status_index(current_status) > get_status_index(result_status)


async def check_irregular_flow(quote: dict, action: str, current_user: dict) -> bool:
    """Verifica si la acción es irregular."""
    expected_status = REGULAR_FLOW.get(action)
    current_status = quote.get("quote_status", "Borrador")
    if expected_status and current_status != expected_status:
        return True
    return False


async def log_audit_exception(quote_id, quote_number, action, expected_status, actual_status, reason, regularization_date, user):
    """Registra excepción de flujo en la colección de auditoría."""
    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    entry = {
        "audit_id": f"aud_{uuid.uuid4().hex[:8]}",
        "quote_id": quote_id,
        "quote_number": quote_number,
        "action": action,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "exception_reason": reason,
        "regularization_date": regularization_date,
        "user_id": user.get("user_id", ""),
        "user_name": user_name,
        "created_at": now
    }
    await db.audit_exceptions.insert_one(entry)
    entry.pop("_id", None)
    return entry


async def mark_quote_irregular(quote_id: str, action: str, reason: str, regularization_date):
    """Marca la cotización como irregular y agrega la excepción."""
    exception_entry = {
        "action": action,
        "reason": reason,
        "regularization_date": regularization_date,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # Ensure irregular_exceptions is an array (handles null or missing field)
    await db.quotes.update_one(
        {"quote_id": quote_id, "$or": [{"irregular_exceptions": None}, {"irregular_exceptions": {"$exists": False}}]},
        {"$set": {"irregular_exceptions": []}}
    )
    await db.quotes.update_one({"quote_id": quote_id}, {
        "$set": {"is_irregular": True},
        "$push": {"irregular_exceptions": exception_entry}
    })
    # Push notification (evento #11 Cotización marcada irregular)
    try:
        from services.notification_service import notify as _push_notify
        quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if quote:
            await _push_notify(
                event_type="quote_marked_irregular",
                title=f"Cotización {quote.get('quote_number','')} marcada IRREGULAR",
                message=f"Acción: {action} · Razón: {reason}",
                context={
                    "creator_user_id": quote.get("created_by_user_id"),
                    "sede": quote.get("sede"),
                },
                link="/quotes?filter=irregular",
                quote_id=quote_id,
            )
    except Exception:
        pass


# Mapeo acción → estado que la acción produce (estado al que SE LLEGA al ejecutarla).
# Usado para auto-regularización: si la cotización ya alcanzó (en cualquier momento)
# el estado producido por cada acción excepcional, se considera regularizada.
ACTION_RESULT_STATUS = {
    'approve': 'Aprobada',
    'invoice': 'Facturada',
    'collect': 'Pagada',
    'deliver': 'Entregada',
    'send_implementation': 'Enviada a Imple',
}


async def try_auto_regularize_quote(quote_id: str) -> bool:
    """
    Verifica si una cotización irregular ya completó (avanzó por) todos los
    estados que originalmente "se saltó". Si sí, desmarca `is_irregular`.

    Criterio (sin saltos):
      Para cada `irregular_exception` con `action` en ACTION_RESULT_STATUS,
      el `quote_status` actual debe estar en una posición >= a la del
      estado producido por esa acción Y los estados intermedios entre el
      estado actual y 'Borrador' deben estar presentes en `status_history`
      (es decir, el stepper completó cada paso intermedio).

    Devuelve True si la cotización fue regularizada en esta llamada.
    """
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote or not quote.get("is_irregular"):
        return False

    current_status = quote.get("quote_status", "Borrador")
    current_idx = get_status_index(current_status)
    if current_idx <= 0:
        return False  # 'Borrador' o desconocido

    exceptions = quote.get("irregular_exceptions") or []
    # Excepciones activas (excluyendo markers de auto-regularización previa)
    active_excs = [
        e for e in exceptions
        if isinstance(e, dict) and not e.get("is_regularization_marker")
    ]
    if not active_excs:
        return False

    # 1) Toda excepción debe tener su estado-resultado <= current_status
    for exc in active_excs:
        action = exc.get("action")
        result_status = ACTION_RESULT_STATUS.get(action)
        if not result_status:
            continue
        result_idx = get_status_index(result_status)
        if result_idx > current_idx:
            return False  # aún no se ha llegado al estado de esa acción

    # 2) Verificar stepper sin saltos: todos los estados intermedios deben
    # aparecer en status_history (al menos uno con cada status).
    history = quote.get("status_history") or []
    visited = {h.get("status") for h in history if isinstance(h, dict) and h.get("status")}
    visited.add(current_status)
    # Estados requeridos: STATUS_ORDER[1..current_idx] (sin Borrador)
    required = STATUS_ORDER[1:current_idx + 1]
    missing = [s for s in required if s not in visited]
    if missing:
        return False

    # Todos los criterios cumplidos → auto-regularizar
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {
            "$set": {
                "is_irregular": False,
                "regularized_at": now_iso,
                "regularized_auto": True,
            },
            "$push": {
                "irregular_exceptions": {
                    "action": "_auto_regularize",
                    "reason": "Stepper completo sin saltos — regularización automática",
                    "regularization_date": now_iso[:10],
                    "created_at": now_iso,
                    "is_regularization_marker": True,
                }
            },
        },
    )
    return True