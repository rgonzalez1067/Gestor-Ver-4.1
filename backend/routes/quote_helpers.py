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
