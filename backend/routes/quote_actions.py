"""Route module: quote_actions.py - Acciones del flujo de cotizaciones.

Nota (refactor Feb-2026):
 - Helpers de flujo regular/irregular y caché de plantillas extraídos a `quote_helpers.py`.
 - `_create_project_from_quote` extraído a `quote_transitions.py`.
 - Endpoints de Taller extraídos a `quote_taller.py`.
 - Endpoints de seriales/inventario/preasignación extraídos a `quote_serials.py`.
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import Response
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import io
import os
import base64

from config import db, get_current_user, UPLOADS_DIR, SENDER_EMAIL, generate_quote_number, render_email_template, inject_custom_message
from services.pdf_storage import save_pdf_dual
from models import *
from services.email_service import send_email
from services.workflow_notifications import send_workflow_notification
from services.hoja_ruta_pdf import generate_nota_entrega_pdf
from routes.quote_helpers import (
    QuoteStatusUpdate,
    EmailSendRequest,
    get_email_template,
    get_status_index,
    is_regularization,
    check_irregular_flow,
    log_audit_exception,
    mark_quote_irregular,
    REGULAR_FLOW,
    STATUS_ORDER,
)
from routes.quote_transitions import _create_project_from_quote
from services.notification_service import notify as _push_notify
from services.notification_engine import (
    try_dispatch as engine_try_dispatch,
    validate_client_email_required as engine_validate_client_email,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# ==================== Adjuntos manuales del modal "Personalizar Comunicación" ====================
# Tamaño máximo total de adjuntos manuales por envío (SMTP-friendly)
_MAX_MANUAL_ATTACHMENTS_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_MANUAL_MIME_PREFIXES = (
    "application/pdf", "image/", "text/",
    "application/vnd.openxmlformats-officedocument",
    "application/vnd.ms-excel", "application/msword",
    "application/octet-stream",  # genérico, validamos por extensión
)


async def _resolve_manual_attachments(ids_header: Optional[str]) -> list[dict]:
    """Convierte el header `x-manual-attachment-ids` (CSV de IDs) en lista
    [{filename, content (base64)}] consumible por _engine_or_legacy /
    send_workflow_notification. Limpia los registros temporales tras leerlos.
    """
    if not ids_header:
        return []
    ids = [s.strip() for s in ids_header.split(",") if s.strip()]
    if not ids:
        return []
    docs = await db.temp_manual_attachments.find(
        {"attachment_id": {"$in": ids}}, {"_id": 0}
    ).to_list(50)
    out = []
    consumed_ids = []
    total = 0
    for d in docs:
        total += int(d.get("size", 0) or 0)
        if total > _MAX_MANUAL_ATTACHMENTS_BYTES:
            logger.warning(f"[manual_attachments] tamaño total excedido ({total} > {_MAX_MANUAL_ATTACHMENTS_BYTES}). Truncando.")
            break
        out.append({
            "filename": d.get("filename"),
            "content": d.get("content_b64"),
            "content_type": d.get("content_type"),
        })
        consumed_ids.append(d.get("attachment_id"))
    # Limpieza: borramos sólo los temporales efectivamente consumidos.
    if consumed_ids:
        await db.temp_manual_attachments.delete_many({"attachment_id": {"$in": consumed_ids}})
    return out


@router.post("/quotes/manual-attachments/upload")
async def upload_manual_attachment(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Sube un adjunto manual para asociarlo a un próximo envío de correo.

    Valida tipo + tamaño individual. Devuelve un `attachment_id` que debe
    incluirse en el header `x-manual-attachment-ids` (CSV) al ejecutar la
    acción de envío. Los adjuntos temporales se borran tras consumirse o
    quedan caducos (TTL = 1h).
    """
    user = await get_current_user(authorization)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    size = len(raw)
    if size > _MAX_MANUAL_ATTACHMENTS_BYTES:
        raise HTTPException(status_code=413, detail=f"Archivo supera el límite de 10 MB ({size} bytes)")
    ct = (file.content_type or "application/octet-stream").lower()
    if not any(ct.startswith(p) for p in _ALLOWED_MANUAL_MIME_PREFIXES):
        # Permitimos por extensión también
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                       ".txt", ".csv", ".xlsx", ".xls", ".docx", ".doc"):
            raise HTTPException(status_code=415, detail=f"Tipo no permitido: {ct}")

    attachment_id = f"matt_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    doc = {
        "attachment_id": attachment_id,
        "filename": file.filename or "adjunto",
        "content_type": ct,
        "size": size,
        "content_b64": base64.b64encode(raw).decode("ascii"),
        "uploaded_by": user.get("email"),
        "uploaded_at": now.isoformat(),
        # `expires_at` se usa con TTL index si está configurado; el cleanup
        # one-shot también ocurre en _resolve_manual_attachments.
        "expires_at": now,
    }
    await db.temp_manual_attachments.insert_one(doc)
    return {
        "attachment_id": attachment_id,
        "filename": doc["filename"],
        "size": size,
        "content_type": ct,
    }




async def _engine_or_legacy(
    action_id: str,
    quote: dict,
    current_user: dict,
    custom_message: Optional[str] = None,
    cc_emails: Optional[list] = None,
    extra_attachments: Optional[list] = None,
    **pdf_ctx,
):
    """Phase 2 — Dynamic Notification Engine wrapper with safe legacy fallback.

    Returns:
      - list[dict] with dispatch outcome → caller MUST skip legacy email flow.
      - None → no dynamic config OR engine errored; caller MUST run legacy flow.

    Raises HTTP 400 if dynamic config requires `client_field` but quote has no
    client email registered. This guard is the ONLY way the engine can abort
    the action; in any other failure scenario it returns None and trusts
    legacy.

    `extra_attachments`: forwarded to the engine as siempre-adjuntos (eg.
    payment receipts, custom modal uploads). Independent del flag
    `send_pdf_attachments` por destinatario.
    """
    try:
        warn = await engine_validate_client_email(action_id, quote)
    except Exception as e:
        logger.warning(f"[engine] validate_client_email_required errored for {action_id}: {e}")
        warn = None
    if warn:
        raise HTTPException(status_code=400, detail=warn)
    try:
        dispatched = await engine_try_dispatch(
            action_id,
            quote,
            current_user,
            custom_message=custom_message,
            cc_emails=cc_emails or [],
            extra_attachments=extra_attachments or None,
            **pdf_ctx,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[engine] dispatch failed for {action_id}, falling back to legacy: {e}", exc_info=True)
        return None
    if dispatched:
        return [{
            "status": "engine_dispatched",
            "engine": "notification_engine",
            "action": action_id,
        }]
    return None


async def _push_quote_event(event_type: str, quote: dict, title: str, message: str) -> None:
    """Wrapper delgado para disparar notificaciones push sin ensuciar cada endpoint."""
    try:
        await _push_notify(
            event_type=event_type,
            title=title,
            message=message,
            context={
                "creator_user_id": quote.get("created_by_user_id"),
                "sede": quote.get("sede"),
            },
            link=f"/quotes",
            quote_id=quote.get("quote_id"),
        )
    except Exception as e:
        logger.warning(f"[notify] {event_type} failed: {e}")

@router.get("/quotes/irregular/count")
async def get_irregular_count(authorization: Optional[str] = Header(None)):
    """Devuelve el conteo de cotizaciones en estado irregular."""
    await get_current_user(authorization)
    count = await db.quotes.count_documents({"is_irregular": True})
    return {"count": count}


@router.post("/admin/quotes/regularize-batch")
async def admin_regularize_batch(
    body: Optional[dict] = None,
    authorization: Optional[str] = Header(None),
):
    """
    Regularización masiva retroactiva (admin-only).

    Proceso:
      1) Identifica todas las cotizaciones con `is_irregular: True`.
      2) Para cada una, completa `status_history` con los estados intermedios
         faltantes usando los timestamps reales de la cotización (approved_at,
         invoiced_at, paid_at, etc.). Las entradas backfill se marcan con
         `user: "Sistema (backfill)"` y `action: "_backfill"`.
      3) Aplica `try_auto_regularize_quote()` para desmarcar las que cumplan
         el criterio (current_status >= ACTION_RESULT_STATUS de cada excepción).

    Body:
      { "dry_run": true|false }   default: false

    Respuesta:
      { total_irregular_before, backfilled, regularized, still_irregular,
        details: {...} }
    """
    current_user = await get_current_user(authorization)
    if (current_user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    dry_run = bool((body or {}).get("dry_run", False))

    from routes.quote_helpers import (
        try_auto_regularize_quote,
        ACTION_RESULT_STATUS,
    )

    STATUS_TIMESTAMP_FIELD = {
        "Enviada": "sent_to_client_at",
        "Aprobada": "approved_at",
        "Reparada": "repaired_at",
        "Facturada": "invoiced_at",
        "Pagada": "paid_at",
        "Entregada": "delivered_at",
        "Enviada a Imple": "sent_to_implementation_at",
    }

    irregulars = await db.quotes.find({"is_irregular": True}).to_list(2000)
    total_before = len(irregulars)

    backfill_log = []
    will_regularize = []
    cannot_regularize = []

    for q in irregulars:
        qid = q["quote_id"]
        current_status = q.get("quote_status", "Borrador")
        idx = get_status_index(current_status)
        if idx <= 0:
            cannot_regularize.append({
                "quote_number": q.get("quote_number"),
                "status": current_status,
                "reason": "Estado Borrador o desconocido",
            })
            continue

        # 1) Verificar criterio (a): current_status >= result_status de cada excepción
        active_excs = [
            e for e in (q.get("irregular_exceptions") or [])
            if isinstance(e, dict) and not e.get("is_regularization_marker")
        ]
        unmet = []
        for exc in active_excs:
            action = exc.get("action")
            rs = ACTION_RESULT_STATUS.get(action)
            if not rs:
                continue
            if get_status_index(rs) > idx:
                unmet.append({"action": action, "needs": rs})
        if unmet:
            cannot_regularize.append({
                "quote_number": q.get("quote_number"),
                "status": current_status,
                "reason": "current_status no alcanza el estado-resultado de la excepción",
                "unmet": unmet,
            })
            continue

        # 2) Construir entradas de backfill (estados faltantes en status_history)
        history = q.get("status_history") or []
        present = {h.get("status") for h in history if isinstance(h, dict) and h.get("status")}
        present.add(current_status)
        required = STATUS_ORDER[1:idx + 1]
        missing = [s for s in required if s not in present]

        created_at = q.get("created_at") or datetime.now(timezone.utc).isoformat()
        new_entries = []
        last_ts = created_at
        for s in missing:
            ts_field = STATUS_TIMESTAMP_FIELD.get(s)
            ts = q.get(ts_field) if ts_field else None
            if not ts:
                ts = last_ts
            last_ts = ts
            new_entries.append({
                "status": s,
                "action": "_backfill",
                "detail": "Backfill automático para regularización retroactiva",
                "timestamp": ts,
                "user": "Sistema (backfill)",
            })

        if missing and not dry_run:
            await db.quotes.update_one(
                {"quote_id": qid},
                {"$push": {"status_history": {"$each": new_entries}}}
            )
            backfill_log.append({
                "quote_number": q.get("quote_number"),
                "status": current_status,
                "added_steps": missing,
            })
        elif missing:
            backfill_log.append({
                "quote_number": q.get("quote_number"),
                "status": current_status,
                "added_steps": missing,
                "dry_run": True,
            })

        will_regularize.append({
            "quote_id": qid,
            "quote_number": q.get("quote_number"),
            "status": current_status,
        })

    # Aplicar regularización (omite la escritura si dry_run)
    regularized = []
    if not dry_run:
        for w in will_regularize:
            if await try_auto_regularize_quote(w["quote_id"]):
                regularized.append({
                    "quote_number": w["quote_number"],
                    "status": w["status"],
                })

    final_count = (
        total_before - len(regularized)
        if not dry_run
        else total_before
    )

    return {
        "dry_run": dry_run,
        "total_irregular_before": total_before,
        "total_irregular_after": final_count,
        "backfilled_count": len(backfill_log),
        "regularized_count": len(regularized) if not dry_run else len(will_regularize),
        "cannot_regularize_count": len(cannot_regularize),
        "details": {
            "backfilled": backfill_log,
            "regularized": regularized if not dry_run else will_regularize,
            "cannot_regularize": cannot_regularize,
        },
    }


@router.get("/quotes/audit-log")
async def get_audit_log(authorization: Optional[str] = Header(None)):
    """Devuelve el log de auditoría de excepciones de flujo."""
    await get_current_user(authorization)
    entries = await db.audit_exceptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return entries

@router.get("/quotes/{quote_id}/audit-log")
async def get_quote_audit_log(quote_id: str, authorization: Optional[str] = Header(None)):
    """Devuelve el log de auditoría de excepciones para una cotización específica."""
    await get_current_user(authorization)
    entries = await db.audit_exceptions.find({"quote_id": quote_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries


@router.put("/quotes/{quote_id}/status")
async def update_quote_status(quote_id: str, status_update: QuoteStatusUpdate, authorization: Optional[str] = Header(None)):
    """Actualiza el estatus de una cotización validando transiciones permitidas"""
    await get_current_user(authorization)
    
    if status_update.new_status not in QUOTE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Estados válidos: {QUOTE_STATUSES}")
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    quote_category = quote.get("quote_category", "implementation")
    
    transitions = QUOTE_TRANSITIONS.get(quote_category, QUOTE_TRANSITIONS["implementation"])
    allowed_next_states = transitions.get(current_status, [])
    
    if status_update.new_status not in allowed_next_states:
        raise HTTPException(
            status_code=400,
            detail=f"Transición no permitida: '{current_status}' → '{status_update.new_status}'. Transiciones válidas: {allowed_next_states}"
        )
    
    # Timestamp según el nuevo estado
    timestamp_map = {
        "Enviada": "sent_to_client_at",
        "Aprobada": "approved_at",
        "Reparada": "repaired_at",
        "Facturada": "invoiced_at",
        "Pagada": "paid_at",
        "Entregada": "delivered_at",
        "Enviada a Imple": "sent_to_implementation_at",
    }
    update_fields = {"quote_status": status_update.new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
    if status_update.new_status in timestamp_map:
        update_fields[timestamp_map[status_update.new_status]] = datetime.now(timezone.utc).isoformat()

    # Registrar la transición en status_history (necesario para auto-regularización)
    current_user_doc = await get_current_user(authorization)
    user_label = f"{current_user_doc.get('first_name', '')} {current_user_doc.get('last_name', '')}".strip() or current_user_doc.get('email', 'Sistema')
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {
            "$set": update_fields,
            "$push": {"status_history": {
                "status": status_update.new_status,
                "action": "update_status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_label,
            }},
        }
    )

    # Si la cotización estaba marcada irregular, verificar si ya completó
    # todos los pasos del stepper para desmarcarla automáticamente.
    try:
        from routes.quote_helpers import try_auto_regularize_quote
        was_regularized = await try_auto_regularize_quote(quote_id)
        if was_regularized:
            logger.info(f"[quotes] {quote_id} auto-regularizada al alcanzar {status_update.new_status}")
    except Exception as e:
        logger.warning(f"[quotes] No se pudo verificar auto-regularización de {quote_id}: {e}")

    # === TRIGGER: Archivar en Histórico ANTES de crear proyecto (que borra la cotización) ===
    if status_update.new_status == "Enviada a Imple":
        try:
            from routes.quote_history import archive_quote_to_history
            current_user = await get_current_user(authorization)
            await archive_quote_to_history(quote_id, "status_enviada_imple", current_user)
        except Exception as e:
            logger.error(f"Error archivando cotización {quote_id} al histórico: {e}")

    # === TRIGGER: Crear Proyecto al enviar a Implementación ===
    if status_update.new_status == "Enviada a Imple":
        try:
            await _create_project_from_quote(quote, quote_id)
        except Exception as e:
            logger.error(f"Error creando proyecto desde cotización {quote_id}: {e}")

    # === TRIGGER: Archivar otros estados finales (Entregada etc.) ===
    if status_update.new_status != "Enviada a Imple":
        try:
            from routes.quote_history import check_and_archive_on_status_change
            current_user = await get_current_user(authorization)
            await check_and_archive_on_status_change(quote_id, status_update.new_status, current_user)
        except Exception as e:
            logger.error(f"Error archivando cotización {quote_id} al histórico: {e}")

    return {"message": f"Estado actualizado a '{status_update.new_status}'", "previous_status": current_status, "new_status": status_update.new_status}


@router.post("/quotes/{quote_id}/approve")
async def approve_quote(
    quote_id: str,
    payload: Optional[str] = Form(None),
    payment_files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None),
    exception_reason: Optional[str] = Header(None, alias="x-exception-reason"),
    regularization_date: Optional[str] = Header(None, alias="x-regularization-date"),
    custom_message: Optional[str] = Header(None, alias="x-custom-message"),
    additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"),
    manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids"),
):
    """Aprobar una cotización con instrucción de facturación.

    Acepta multipart/form-data:
      - `payload` (str, JSON): datos de billing_instruction (consolidated_items, exchange_rate, ...).
      - `payment_files` (List[UploadFile], opcional): comprobantes de pago anticipado a
        adjuntar SOLO al correo de Administración. NO se almacenan en quote.attachments.

    El soporte de aprobación (Orden de Compra) sí persiste en `quote.attachments` y se sube
    de forma independiente al endpoint /quotes/{id}/attachments antes de invocar este.
    """
    import json as _json

    current_user = await get_current_user(authorization)

    body: dict = {}
    if payload:
        try:
            body = _json.loads(payload)
            if not isinstance(body, dict):
                body = {}
        except Exception:
            raise HTTPException(status_code=400, detail="Payload JSON inválido en form field 'payload'")

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Enviada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para aprobar sin haber enviado al cliente")
        await mark_quote_irregular(quote_id, "approve", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "approve", "Enviada", current_status, exception_reason, regularization_date, current_user)
    
    # Obtener cliente
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Guardar datos de instrucción de facturación si se proporcionan
    billing_data = {}
    if body.get("consolidated_items"):
        billing_data = {
            "billing_instruction": {
                "consolidated_items": body["consolidated_items"],
                "exchange_rate": body.get("exchange_rate", 0),
                "grand_total_usd": body.get("grand_total_usd", 0),
                "grand_total_bs": body.get("grand_total_bs", 0),
                "iva_usd": body.get("iva_usd", 0),
                "iva_bs": body.get("iva_bs", 0),
                "grand_total_con_iva_usd": body.get("grand_total_con_iva_usd", 0),
                "grand_total_con_iva_bs": body.get("grand_total_con_iva_bs", 0),
                "has_payment_proof": body.get("has_payment_proof", False),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
    
    # Actualizar estado (solo si NO es regularización retroactiva)
    is_regul = is_regularization(current_status, "approve")
    update_fields = {"approved_at": datetime.now(timezone.utc).isoformat(), **billing_data}
    if not is_regul:
        update_fields["quote_status"] = "Aprobada"
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": update_fields}
    )

    # TRIGGER: Si es reparación, insertar seriales en taller_equipos
    is_repair = quote.get("quote_category") == "repair"
    if is_repair and not is_regul:
        repair_models = quote.get("repair_models", [])
        now_iso = datetime.now(timezone.utc).isoformat()
        taller_docs = []
        for rm in repair_models:
            model_name = rm.get("model_name", "")
            model_id = rm.get("model_id", "")
            for serial in rm.get("serials", []):
                taller_docs.append({
                    "taller_equipo_id": f"te_{uuid.uuid4().hex[:12]}",
                    "serial": serial,
                    "modelo": model_name,
                    "modelo_id": model_id,
                    "client_id": quote.get("client_id", ""),
                    "client_name": client_name,
                    "quote_id": quote_id,
                    "quote_number": quote.get("quote_number", ""),
                    "estatus": "En reparación",
                    "fecha_ingreso": now_iso,
                    "fecha_entrega": None,
                })
        if taller_docs:
            await db.taller_equipos.insert_many(taller_docs)
            logger.info(f"Taller: {len(taller_docs)} equipo(s) ingresados para cotización {quote.get('quote_number')}")
    
    # Preparar email via Workflow Notification
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    email_results = []
    is_repair = quote.get("quote_category") == "repair"
    is_fast_track = quote.get("quote_category") == "fast_track"

    # === Notification Engine (Phase 2) — pre-generar PDFs y anexos disponibles para hook ===
    # Generamos los binarios upfront para pasarlos tanto al engine como al
    # legacy. Si el engine retorna una lista, saltamos legacy.
    _engine_pdf_quote_bytes = None
    _engine_pdf_billing_bytes = None
    _engine_extra_attachments: list[dict] = []
    # PDF de cotización: aplica para implementación, equipos y fast_track
    # (no para reparación, que tiene su propio PDF de Cálculos en repair-complete).
    if not is_repair:
        pdf_url_pre = quote.get("quote_pdf_url")
        if pdf_url_pre:
            try:
                _pdf_path = UPLOADS_DIR / pdf_url_pre.replace("/uploads/", "")
                if _pdf_path.exists():
                    _engine_pdf_quote_bytes = open(_pdf_path, "rb").read()
            except Exception as _e:
                logger.warning(f"[approve] No se pudo precargar PDF de cotización: {_e}")
        # PDF de Cálculos Definitivos: se genera siempre que vengan items
        # consolidados en billing_instruction. Aplica también a fast_track
        # (MPOS Imple+POS), donde la cotización es MIXTA: contiene una sección
        # Implementación y otra de Pinpads.
        if billing_data.get("billing_instruction") and billing_data["billing_instruction"].get("consolidated_items"):
            try:
                from services.billing_pdf import generate_billing_pdf
                _exec_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "Sistema"
                _engine_pdf_billing_bytes = generate_billing_pdf(quote, client, billing_data["billing_instruction"], _exec_name)
            except Exception as _e:
                logger.warning(f"[approve] No se pudo precargar Cálculos Definitivos: {_e}")
    # Comprobantes de pago anticipado (multipart) — efímeros, NO se persisten.
    # Se anexan SIEMPRE al correo (engine y legacy).
    if payment_files:
        for _pf in payment_files:
            try:
                _raw = await _pf.read()
                if not _raw:
                    continue
                _engine_extra_attachments.append({
                    "filename": _pf.filename or "pago_anticipado.pdf",
                    "content": base64.b64encode(_raw).decode("utf-8"),
                })
            except Exception as _e:
                logger.warning(f"[Approve] No se pudo leer payment_file {_pf.filename}: {_e}")

    # Anexos manuales del modal "Personalizar Comunicación" (CSV de IDs en header).
    _manual_attachments = await _resolve_manual_attachments(manual_attachment_ids)
    if _manual_attachments:
        _engine_extra_attachments.extend(_manual_attachments)

    _engine_result = await _engine_or_legacy(
        "approve", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        extra_attachments=_engine_extra_attachments or None,
        quote_pdf_bytes=_engine_pdf_quote_bytes,
        billing_pdf_bytes=_engine_pdf_billing_bytes,
    )
    if _engine_result is not None:
        email_results = _engine_result
        billing_instruction = billing_data.get("billing_instruction") if billing_data else None
        await _push_quote_event(
            "quote_approved", quote,
            title=f"Cotización {quote.get('quote_number','')} aprobada",
            message=f"Cliente {quote.get('client_name','')} · Total USD ${quote.get('total_usd',0):,.2f}",
        )
        return {
            "message": "Cotización aprobada exitosamente" + (" — Pendiente de Reparación" if is_repair else " — Pendiente de Configuración" if is_fast_track else ""),
            "quote_id": quote_id,
            "new_status": "Aprobada",
            "emails": email_results,
            "is_repair": is_repair,
            "is_fast_track": is_fast_track,
            "billing_instruction": billing_instruction,
        }

    if is_fast_track:
        # Fast Track: Notificar a Administración + Operaciones con plantilla fast_track_approved
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        raw_sede = quote.get("sede", "PYME")
        norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
        sede_emails = (config.get("emails_by_sede", {}) if config else {}).get(norm_sede, {})
        
        ft_recipients = []
        admin_email = sede_emails.get("admin")
        ops_email = sede_emails.get("operations")
        if admin_email:
            ft_recipients.append(admin_email)
        if ops_email and ops_email != admin_email:
            ft_recipients.append(ops_email)
        if not ft_recipients:
            ft_recipients.append("admin@sede.local")

        # Adjuntos para fast_track: PDF de Cotización + Cálculos Definitivos
        # (cuando aplique) + comprobantes de pago anticipado efímeros.
        ft_attachments = list(_engine_extra_attachments) if _engine_extra_attachments else []
        if _engine_pdf_billing_bytes:
            ft_attachments.append({
                "filename": f"Calculos_Definitivos_{quote.get('quote_number', 'N-A')}.pdf",
                "content": base64.b64encode(_engine_pdf_billing_bytes).decode("utf-8"),
            })
            logger.info(f"[Approve/FastTrack] Cálculos Definitivos adjunto para {quote.get('quote_number')}")

        # Mergear adjuntos ya computados (payment_files + manual_attachments) con los de Fast Track.
        merged_ft_attachments = list(ft_attachments)
        if _engine_extra_attachments:
            merged_ft_attachments.extend(_engine_extra_attachments)

        email_results = await send_workflow_notification(
            action="approve",
            quote=quote,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
            pdf_buffer=_engine_pdf_quote_bytes,
            extra_attachments=merged_ft_attachments if merged_ft_attachments else None,
            template_base_override="fast_track_approved",
            override_recipients=ft_recipients,
        )
    elif is_repair:
        # Enviar confirmación de aprobación al CLIENTE
        contacts = client.get('contacts', []) if client else []
        client_email = None
        if contacts:
            client_email = contacts[0].get('email')
        if not client_email:
            contact1 = client.get('contact1') or {} if client else {}
            client_email = contact1.get('email') if isinstance(contact1, dict) else None
        if not client_email or client_email == 'sin@email.com':
            client_email = f"cliente_{(client or {}).get('rif', 'unknown')}@simulado.local"

        contacto_cliente = client_name
        if contacts:
            contacto_cliente = contacts[0].get('full_name') or contacts[0].get('name') or client_name

        quote_sede = quote.get("sede", "PYME")
        norm_sede = "PYME" if quote_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if quote_sede in ("CORP", "Corp", "Corporativo") else quote_sede
        ra_template = await get_email_template(f"repair_approved_{norm_sede}")
        if not ra_template:
            ra_template = await get_email_template("repair_approved")
        if not ra_template:
            ra_template = {
                "subject": "Confirmación de Aprobación - Cotización Nro. {nro_cotizacion}",
                "body_html": "<h2>Aprobación Confirmada</h2><p>Hola, <strong>{contacto_cliente}</strong>. Confirmamos la aprobación de la cotización <strong>{nro_cotizacion}</strong>. Sus equipos han ingresado a nuestro taller técnico.</p>"
            }
        ra_vars = {
            "nro_cotizacion": quote.get('quote_number', ''),
            "quote_number": quote.get('quote_number', ''),
            "nombre_cliente": client_name,
            "client_name": client_name,
            "contacto_cliente": contacto_cliente,
            "Nombre_Ejecutivo": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "",
            "Email_Ejecutivo": current_user.get("email", "") if current_user else "",
        }
        ra_subject = render_email_template(ra_template["subject"], ra_vars)
        ra_html = render_email_template(ra_template["body_html"], ra_vars)

        r = await send_email(to=[client_email], subject=ra_subject, html=ra_html, action="repair_approved_client", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)
        for cc in cc_emails:
            r = await send_email(to=[cc], subject=f"[CC] {ra_subject}", html=ra_html, action="repair_approved_cc", quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)
    else:
        # Cargar PDF de la cotización para adjuntar
        pdf_buffer = None
        pdf_url = quote.get("quote_pdf_url")
        if pdf_url:
            pdf_path = UPLOADS_DIR / pdf_url.replace("/uploads/", "")
            if pdf_path.exists():
                pdf_buffer = open(pdf_path, 'rb').read()

        # Cargar soportes de pago anticipado EFÍMEROS — ya fueron leídos arriba al
        # construir _engine_extra_attachments (el caller los puede haber consumido
        # del stream). Reutilizamos esos para evitar doble lectura.
        approval_attachments_b64 = list(_engine_extra_attachments) if _engine_extra_attachments else []


        # Generar PDF de Cálculos Definitivos (si hay billing_instruction)
        if billing_data.get("billing_instruction") and billing_data["billing_instruction"].get("consolidated_items"):
            try:
                from services.billing_pdf import generate_billing_pdf
                executor_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "Sistema"
                billing_pdf_bytes = generate_billing_pdf(quote, client, billing_data["billing_instruction"], executor_name)
                approval_attachments_b64.append({
                    "filename": f"Calculos_Definitivos_{quote.get('quote_number', 'N-A')}.pdf",
                    "content": base64.b64encode(billing_pdf_bytes).decode('utf-8')
                })
                logger.info(f"[Approve] PDF de Cálculos Definitivos generado para {quote.get('quote_number')}")
            except Exception as e:
                logger.error(f"Error generando PDF de Cálculos Definitivos: {e}")

        # Workflow centralizado: approve → Administración + Ventas (sede) + PDF adjunto
        # Para equipos, usar plantilla específica de equipos
        eq_template_override = "equipment_approved" if quote.get("quote_category") == "equipment" else None
        # Mergear approval_attachments con los _engine_extra_attachments
        # (payment_files + manual_attachments del modal Personalizar Comunicación)
        merged_approval = list(approval_attachments_b64 or [])
        if _engine_extra_attachments:
            merged_approval.extend(_engine_extra_attachments)

        email_results = await send_workflow_notification(
            action="approve",
            quote=quote,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
            pdf_buffer=pdf_buffer,
            extra_attachments=merged_approval if merged_approval else None,
            template_base_override=eq_template_override,
        )

    # Generar tabla de instrucción de facturación para incluir en respuesta
    billing_instruction = billing_data.get("billing_instruction") if billing_data else None

    # Push notification (evento #2 Cotización aprobada)
    await _push_quote_event(
        "quote_approved", quote,
        title=f"Cotización {quote.get('quote_number','')} aprobada",
        message=f"Cliente {quote.get('client_name','')} · Total USD ${quote.get('total_usd',0):,.2f}",
    )

    return {
        "message": "Cotización aprobada exitosamente" + (" — Pendiente de Reparación" if is_repair else " — Pendiente de Configuración" if is_fast_track else ""),
        "quote_id": quote_id,
        "new_status": "Aprobada",
        "emails": email_results,
        "is_repair": is_repair,
        "is_fast_track": is_fast_track,
        "billing_instruction": billing_instruction
    }


@router.post("/quotes/{quote_id}/configure")
async def configure_quote(quote_id: str, authorization: Optional[str] = Header(None), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Marcar cotización Fast Track como Configurada y notificar a Administración para facturar."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "fast_track":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones MPOS (Imple + POS)")

    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Aprobada":
        raise HTTPException(status_code=400, detail=f"Solo se puede configurar desde estado 'Aprobada'. Estado actual: '{current_status}'")

    # Cambiar estado a "Configurada"
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {
            "quote_status": "Configurada",
            "configured_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Workflow Notification: configure → Almacén (sede) con mensaje de pre-alerta
    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    client_name = client.get("fantasy_name") or client.get("legal_name") if client else "Cliente"
    quote["client_name"] = client_name
    quote["client_rif"] = client.get("rif", "N/A") if client else "N/A"

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # Anexos manuales subidos en el modal "Personalizar Comunicación"
    _manual_attachments = await _resolve_manual_attachments(manual_attachment_ids)

    # === Notification Engine (Phase 2) ===
    _engine_result = await _engine_or_legacy(
        "configure", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        extra_attachments=_manual_attachments or None,
    )
    if _engine_result is not None:
        return {
            "message": "Equipos configurados. Notificación enviada a Administración para facturar.",
            "quote_id": quote_id,
            "new_status": "Configurada",
            "emails": _engine_result,
        }

    # Resolver warehouse email de la sede
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    raw_sede = quote.get("sede", "PYME")
    norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
    sede_emails = (config.get("emails_by_sede", {}) if config else {}).get(norm_sede, {})
    warehouse_email = sede_emails.get("warehouse")
    if not warehouse_email:
        warehouse_email = "almacen@sede.local"

    # Resolver datos del ejecutivo creador
    creator_name, creator_email = "", ""
    creator_user_id = quote.get("created_by_user_id")
    if creator_user_id:
        creator = await db.users.find_one({"user_id": creator_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
        if creator:
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            creator_email = creator.get("email", "")

    ft_config_subject = f"Equipos Configurados - {quote.get('quote_number', '')} - {client_name}"
    ft_config_html = f'''<div style="font-family:'Segoe UI',Arial,sans-serif;max-width:700px;margin:0 auto;">
<div style="background:#003366;color:#fff;padding:18px 28px;border-radius:6px 6px 0 0;">
<h2 style="margin:0;font-size:18px;">Gestión de Almacén — Equipos Configurados</h2></div>
<div style="padding:24px 28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 6px 6px;">
<p>Equipos configurados por Operaciones, disponibles para ser entregados.</p>
<table style="border-collapse:collapse;width:100%;max-width:500px;margin:16px 0;">
<tr style="background:#f8fafc;"><td style="padding:10px 16px;border:1px solid #e2e8f0;font-weight:bold;color:#475569;width:40%;">Cotización</td><td style="padding:10px 16px;border:1px solid #e2e8f0;">{quote.get("quote_number", "")}</td></tr>
<tr><td style="padding:10px 16px;border:1px solid #e2e8f0;font-weight:bold;color:#475569;">Cliente</td><td style="padding:10px 16px;border:1px solid #e2e8f0;">{client_name}</td></tr>
<tr style="background:#f8fafc;"><td style="padding:10px 16px;border:1px solid #e2e8f0;font-weight:bold;color:#475569;">Tipo</td><td style="padding:10px 16px;border:1px solid #e2e8f0;">MPOS (Imple + POS)</td></tr>
</table>
<p style="font-size:14px;color:#64748b;"><strong>Ejecutivo:</strong> {creator_name} ({creator_email})</p>
<p style="margin-top:12px;padding:10px 14px;background:#fef3c7;border-left:4px solid #f59e0b;border-radius:4px;font-size:14px;color:#92400e;">
<strong>Nota:</strong> Los equipos están listos para despacho una vez se registre el pago/facturación.</p>
</div></div>'''

    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        ft_config_html = inject_custom_message(ft_config_html, custom_message, user_name, max_chars=500)

    email_results = []
    r = await send_email(to=[warehouse_email], subject=ft_config_subject, html=ft_config_html, action="configure_ft_warehouse", quote_id=quote_id, quote_number=quote.get("quote_number"))
    email_results.append(r)
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {ft_config_subject}", html=ft_config_html, action="configure_ft_cc", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)

    return {
        "message": "Equipos configurados. Notificación enviada a Administración para facturar.",
        "quote_id": quote_id,
        "new_status": "Configurada",
        "emails": email_results
    }


@router.post("/quotes/{quote_id}/repair-complete")
async def repair_complete(quote_id: str, body: dict = None, authorization: Optional[str] = Header(None), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Marcar reparación como completada y notificar a Administración para facturar."""
    current_user = await get_current_user(authorization)
    if body is None:
        body = {}

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    current_status = quote.get("quote_status", "Borrador")
    if current_status != "Aprobada":
        raise HTTPException(status_code=400, detail=f"Solo se puede marcar como reparada desde estado 'Aprobada'. Estado actual: '{current_status}'")

    # Guardar billing_data si viene del modal con calculadora
    billing_data = body.get("billing_data")
    update_fields = {
        "quote_status": "Reparada",
        "repaired_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if billing_data:
        update_fields["repair_billing_data"] = billing_data

    # Cambiar estado a "Reparada"
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": update_fields}
    )

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # === Notification Engine (Phase 2) ===
    _engine_billing_pdf_bytes = None
    if billing_data:
        try:
            from services.billing_pdf import generate_billing_pdf
            _client_for_pdf = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
            _exec_full = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else ""
            _engine_billing_pdf_bytes = generate_billing_pdf(
                quote=quote, client=_client_for_pdf or {},
                billing_instruction=billing_data, executor_name=_exec_full,
            )
        except Exception as _e:
            logger.warning(f"[repair-complete] No se pudo precargar Cálculos Definitivos para engine: {_e}")

    _engine_result = await _engine_or_legacy(
        "repair_complete", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        billing_pdf_bytes=_engine_billing_pdf_bytes,
        extra_attachments=(await _resolve_manual_attachments(manual_attachment_ids)) or None,
    )
    if _engine_result is not None:
        await _push_quote_event(
            "quote_repair_finalized", quote,
            title=f"Reparación {quote.get('quote_number','')} finalizada",
            message=f"Cliente {quote.get('client_name','')} · Lista para entregar",
        )
        return {
            "message": "Reparación marcada como completada. Notificación enviada a Administración y Cliente.",
            "quote_id": quote_id,
            "new_status": "Reparada",
            "emails": _engine_result,
        }

    # Notificar a Administración (misma lógica que approve para no-reparaciones)
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "PYME")
    norm_sede = "PYME" if quote_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if quote_sede in ("CORP", "Corp", "Corporativo") else quote_sede
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(norm_sede, {}) or emails_by_sede.get(quote_sede, {})
    admin_email = sede_emails.get("admin") or (config.get("admin_email") if config else None)
    sales_email = sede_emails.get("sales") if sede_emails else None

    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    client_name = client.get("fantasy_name") or client.get("legal_name") if client else "Cliente"

    # Obtener datos del contacto del cliente
    contacts = client.get('contacts', []) if client else []
    client_email = None
    if contacts:
        client_email = contacts[0].get('email')
    if not client_email:
        contact1 = client.get('contact1') or {} if client else {}
        client_email = contact1.get('email') if isinstance(contact1, dict) else None
    if not client_email or client_email == 'sin@email.com':
        client_email = f"cliente_{(client or {}).get('rif', 'unknown')}@simulado.local"

    contacto_cliente = client_name
    if contacts:
        contacto_cliente = contacts[0].get('full_name') or contacts[0].get('name') or contacts[0].get('first_name') or client_name

    # Construir lista de modelos/seriales desde taller_equipos
    equipos_taller = await db.taller_equipos.find(
        {"quote_id": quote_id, "estatus": "En reparación"}, {"_id": 0, "modelo": 1, "serial": 1}
    ).to_list(1000)
    modelos_map = {}
    for eq in equipos_taller:
        modelo = eq.get("modelo", "Sin modelo")
        if modelo not in modelos_map:
            modelos_map[modelo] = []
        modelos_map[modelo].append(eq.get("serial", ""))
    lista_modelos_seriales_html = ""
    for modelo, serials in modelos_map.items():
        lista_modelos_seriales_html += f"<p style='margin:4px 0'><strong>{modelo}</strong>: {', '.join(serials)}</p>"
    if not lista_modelos_seriales_html:
        for rm in quote.get("repair_models", []):
            lista_modelos_seriales_html += f"<p style='margin:4px 0'><strong>{rm.get('model_name', 'N/A')}</strong>: {', '.join(rm.get('serials', []))}</p>"

    # --- Cargar plantilla: Notificación de Reparación Finalizada (Sede) ---
    rc_template = await get_email_template(f"repair_complete_client_{norm_sede}")
    if not rc_template:
        rc_template = await get_email_template("repair_complete_client")
    if not rc_template:
        rc_template = {
            "subject": "Sus equipos ya han sido reparados - {nro_cotizacion}",
            "body_html": "<h2>Reparación Finalizada</h2><p>Estimado(a) <strong>{contacto_cliente}</strong>, el proceso de reparación para sus equipos bajo la cotización <strong>{nro_cotizacion}</strong> ha finalizado exitosamente.</p><div>{lista_modelos_seriales}</div><p>Su solicitud ha pasado a Administración para la emisión de la Factura correspondiente.</p>"
        }
    rc_vars = {
        "nro_cotizacion": quote.get("quote_number", ""),
        "quote_number": quote.get("quote_number", ""),
        "nombre_cliente": client_name,
        "client_name": client_name,
        "contacto_cliente": contacto_cliente,
        "lista_modelos_seriales": lista_modelos_seriales_html,
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Nombre_Ejecutivo": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "",
        "Email_Ejecutivo": current_user.get("email", "") if current_user else "",
    }
    rc_subject = render_email_template(rc_template["subject"], rc_vars)
    rc_html = render_email_template(rc_template["body_html"], rc_vars)

    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        rc_html = inject_custom_message(rc_html, custom_message, user_name, max_chars=300)

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # Generar PDF "Cálculos Definitivos para la Factura" SOLO si vino billing_data del modal.
    # Este PDF se adjunta exclusivamente al correo de Administración/Ventas, NUNCA al cliente.
    admin_attachments = None
    if billing_data:
        try:
            from services.billing_pdf import generate_billing_pdf
            executor_full_name = (
                f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
                if current_user else ""
            )
            pdf_bytes = generate_billing_pdf(
                quote=quote,
                client=client or {},
                billing_instruction=billing_data,
                executor_name=executor_full_name,
            )
            admin_attachments = [{
                "filename": f"Calculos_Definitivos_{quote.get('quote_number', quote_id)}.pdf",
                "content": base64.b64encode(pdf_bytes).decode('utf-8'),
            }]
            logger.info(f"[repair-complete] PDF Cálculos Definitivos generado ({len(pdf_bytes)} bytes) para {quote.get('quote_number')}")
        except Exception as e:
            logger.error(f"[repair-complete] Error generando PDF Cálculos Definitivos: {e}")
            admin_attachments = None

    # Enviar con plantilla Reparación Finalizada a Admin + Cliente
    email_results = []
    if admin_email:
        r = await send_email(to=[admin_email], subject=rc_subject, html=rc_html, action="repair_complete_admin", quote_id=quote_id, quote_number=quote.get("quote_number"), attachments=admin_attachments)
        email_results.append(r)
    if sales_email:
        r = await send_email(to=[sales_email], subject=f"[VENTAS] {rc_subject}", html=rc_html, action="repair_complete_sales", quote_id=quote_id, quote_number=quote.get("quote_number"), attachments=admin_attachments)
        email_results.append(r)
    if not admin_email and not sales_email:
        r = await send_email(to=["admin@sede.local"], subject=rc_subject, html=rc_html, action="repair_complete_no_config", quote_id=quote_id, quote_number=quote.get("quote_number"), attachments=admin_attachments)
        email_results.append(r)

    # Enviar al cliente — SIN attachments (el PDF de cálculos es interno)
    r = await send_email(to=[client_email], subject=rc_subject, html=rc_html, action="repair_complete_client", quote_id=quote_id, quote_number=quote.get("quote_number"))
    email_results.append(r)

    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {rc_subject}", html=rc_html, action="repair_complete_cc", quote_id=quote_id, quote_number=quote.get("quote_number"))
        email_results.append(r)

    # Push notification (evento #10 Cotización reparada finalizada)
    await _push_quote_event(
        "quote_repair_finalized", quote,
        title=f"Reparación {quote.get('quote_number','')} finalizada",
        message=f"Cliente {quote.get('client_name','')} · Lista para entregar",
    )

    return {
        "message": "Reparación marcada como completada. Notificación enviada a Administración y Cliente.",
        "quote_id": quote_id,
        "new_status": "Reparada",
        "emails": email_results
    }


@router.post("/quotes/{quote_id}/send-to-client")
async def send_quote_to_client(quote_id: str, authorization: Optional[str] = Header(None), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Envía la cotización por email al cliente con el PDF adjunto"""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # === Notification Engine (Phase 2) ===
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]
    _engine_pdf_quote_bytes = None
    pdf_url_pre = quote.get("quote_pdf_url")
    if pdf_url_pre:
        try:
            _pdf_path = UPLOADS_DIR / pdf_url_pre.replace("/uploads/", "")
            if _pdf_path.exists():
                _engine_pdf_quote_bytes = open(_pdf_path, "rb").read()
        except Exception as _e:
            logger.warning(f"[send-to-client] No se pudo precargar PDF de cotización: {_e}")
    _manual_attachments = await _resolve_manual_attachments(manual_attachment_ids)
    _engine_result = await _engine_or_legacy(
        "send_to_client", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        quote_pdf_bytes=_engine_pdf_quote_bytes,
        extra_attachments=_manual_attachments or None,
    )
    if _engine_result is not None:
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {"sent_to_client_at": datetime.now(timezone.utc).isoformat(), "quote_status": "Enviada"}}
        )
        await _push_quote_event(
            "quote_sent_to_client", quote,
            title=f"Cotización {quote.get('quote_number','')} enviada al cliente",
            message="Despachado por Motor de Notificaciones",
        )
        return {
            "message": "Cotización enviada (motor dinámico)",
            "new_status": "Enviada",
            "emails": _engine_result,
        }

    # Obtener email(s) del contacto
    contacts = client.get('contacts', [])
    client_emails = []
    for c in contacts:
        em = c.get('email', '')
        if em and em != 'sin@email.com' and '@' in em:
            client_emails.append(em)
    # Fallback: contact1 legacy
    if not client_emails:
        contact1 = client.get('contact1') or {}
        legacy_email = contact1.get('email') if isinstance(contact1, dict) else None
        if legacy_email and legacy_email != 'sin@email.com' and '@' in legacy_email:
            client_emails.append(legacy_email)
    # Fallback simulado
    if not client_emails:
        client_emails = [f"cliente_{client.get('rif', 'unknown')}@simulado.local"]
    client_email = client_emails[0]  # Primary for main send
    
    # Preparar plantilla (buscar por sede primero, luego genérica)
    sede = quote.get("sede", "PYME")
    norm_sede = "PYME" if sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if sede in ("CORP", "Corp", "Corporativo") else sede
    is_repair_quote = quote.get("quote_category") == "repair"
    is_equipment_quote = quote.get("quote_category") == "equipment"

    if is_repair_quote:
        # Plantilla específica de reparaciones
        template = await get_email_template(f"repair_quote_sent_{norm_sede}")
        if not template:
            template = await get_email_template("repair_quote_sent")
    elif is_equipment_quote:
        # Plantilla específica de equipos
        template = await get_email_template(f"equipment_sent_{norm_sede}")
        if not template:
            template = await get_email_template("equipment_sent")
    else:
        template = await get_email_template(f"quote_sent_{norm_sede}")
        if not template:
            template = await get_email_template("quote_sent")
    if not template:
        template = {
            "subject": "Cotización {{quote_number}} - {{company_name}}",
            "body_html": "<h2>Estimado {{client_name}}</h2><p>Adjunto encontrará la cotización <strong>{{quote_number}}</strong>.</p><p>Total: ${{total_usd}} USD</p>"
        }
    
    # Resolver datos del ejecutivo creador
    creator_name, creator_email = "", ""
    creator_user_id = quote.get("created_by_user_id")
    if creator_user_id:
        creator = await db.users.find_one({"user_id": creator_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
        if creator:
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            creator_email = creator.get("email", "")

    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'

    # Resolver contacto principal del cliente
    contacto_cliente = client_name
    if contacts:
        contacto_cliente = contacts[0].get('full_name') or contacts[0].get('name') or client_name

    # Construir resumen de modelos para reparaciones
    modelos_resumen = ""
    if is_repair_quote:
        repair_models = quote.get("repair_models", [])
        if repair_models:
            parts = [f"{rm.get('model_name', 'N/A')} (x{len(rm.get('serials', []))})" for rm in repair_models]
            modelos_resumen = ", ".join(parts)

    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "nro_cotizacion": quote.get('quote_number', ''),
        "Cotizacion_Nro": quote.get('quote_number', ''),
        "client_name": client_name,
        "nombre_cliente": client_name,
        "Nombre_Cliente": client_name,
        "Rif_Cliente": client.get('rif', 'N/A'),
        "contacto_cliente": contacto_cliente,
        "client_rif": client.get('rif', 'N/A'),
        "quote_type": quote.get('quote_type', 'N/A'),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Monto_Total": f"{quote.get('total_usd', 0):,.2f}",
        "company_name": "Merchant Server",
        "sede_name": norm_sede,
        "Nombre_Ejecutivo": creator_name,
        "Email_Ejecutivo": creator_email,
        "modelos_resumen": modelos_resumen,
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    # Agregar mensaje personalizado
    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content = inject_custom_message(html_content, custom_message, user_name, max_chars=300)

    # Parsear destinatarios adicionales
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # Preparar attachment PDF si existe
    pdf_attachments = None
    pdf_url = quote.get("quote_pdf_url")
    if pdf_url:
        pdf_path = UPLOADS_DIR / pdf_url.replace("/uploads/", "")
        if pdf_path.exists():
            with open(pdf_path, 'rb') as f:
                pdf_base64 = base64.b64encode(f.read()).decode('utf-8')
            pdf_attachments = [{"filename": f"cotizacion_{quote.get('quote_number', 'quote')}.pdf", "content": pdf_base64}]

    # Enviar (real o simulado)
    # Para equipos: enviar a TODOS los emails registrados del cliente
    if is_equipment_quote and len(client_emails) > 1:
        email_result = await send_email(
            to=client_emails, subject=subject, html=html_content,
            action="send_to_client", quote_id=quote_id, quote_number=quote.get('quote_number'),
            attachments=pdf_attachments
        )
    else:
        email_result = await send_email(
            to=[client_email], subject=subject, html=html_content,
            action="send_to_client", quote_id=quote_id, quote_number=quote.get('quote_number'),
            attachments=pdf_attachments
        )
    
    # Enviar a destinatarios adicionales (CC)
    cc_results = []
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="send_to_client_cc", quote_id=quote_id, quote_number=quote.get('quote_number'), attachments=pdf_attachments)
        cc_results.append(r)
    
    # Actualizar estado
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {"sent_to_client_at": datetime.now(timezone.utc).isoformat(), "quote_status": "Enviada"}}
    )

    # Push notification (evento #1 Cotización enviada al cliente)
    await _push_quote_event(
        "quote_sent_to_client", quote,
        title=f"Cotización {quote.get('quote_number','')} enviada al cliente",
        message=f"Destinatario: {client_email}",
    )

    return {
        "message": f"Cotización enviada a {client_email}",
        "recipient": client_email,
        "new_status": "Enviada",
        **email_result
    }


class SendToImplementationRequest(BaseModel):
    is_multistore: Optional[bool] = False
    stores: Optional[list] = None
    project_type_impl: Optional[str] = None  # "pos_fast_track", "vpos_mpos", "payment_gateway"
    equipment_serials: Optional[list] = None  # [{modelo, serial, nota_entrega_id?}]
    server_name: Optional[str] = None  # "Multicomercio MSC", "Multicomercio MSC2", o texto libre
    economic_group: Optional[str] = None  # Grupo Económico (texto libre)
    fantasy_name: Optional[str] = None    # Nombre de Fantasía (texto libre)
    pinpad_serials: Optional[list] = None  # [{modelo, serial, movement_id}]
    implementation_instructions: Optional[str] = None  # HTML rich-text (máx 500 chars de texto visible)
    fiscal_printer_model: Optional[str] = None  # Modelo de impresora fiscal (capturado en el modal del wizard)


def _validate_instructions_length(html: Optional[str], max_chars: int = 500) -> Optional[str]:
    """Valida que el HTML de instrucciones no supere max_chars de texto visible
    y sanitiza las etiquetas contra XSS (elimina <script>, <iframe>, on*=, javascript:).
    Retorna el HTML saneado (posiblemente vacío) o None si es vacío.
    Lanza HTTP 422 si excede el límite.
    """
    import re
    if not html or not html.strip():
        return None
    # Sanitización mínima (TipTap en el frontend ya emite HTML limpio, pero el
    # backend es la última línea de defensa ante clientes que bypasean el editor).
    safe = str(html)
    safe = re.sub(r"<(script|iframe|object|embed|style|meta|link)\b[^>]*>.*?</\1>", "", safe, flags=re.I | re.S)
    safe = re.sub(r"<(script|iframe|object|embed|style|meta|link)\b[^>]*/?>", "", safe, flags=re.I)
    safe = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", safe, flags=re.I)
    safe = re.sub(r"\son\w+\s*=\s*'[^']*'", "", safe, flags=re.I)
    safe = re.sub(r"javascript:\s*", "", safe, flags=re.I)

    plain = re.sub(r"<[^>]+>", "", safe)
    plain = plain.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    if len(plain) > max_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Las instrucciones adicionales superan el límite de {max_chars} caracteres (actual: {len(plain)}).",
        )
    return safe.strip()

@router.post("/quotes/{quote_id}/send-to-implementation")
async def send_quote_to_implementation(quote_id: str, body: Optional[SendToImplementationRequest] = None, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Envía la cotización al equipo de implementación. Soporta flujo irregular."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    # MPOS (Imple + POS / fast_track): el flujo institucional es
    # Aprobada → (Preasign) → Configurada → Enviar a Implementación → Entregada,
    # SIN paso obligatorio por Facturada/Pagada. No marcar como irregular
    # cuando el usuario sigue este camino feliz.
    is_fast_track = (quote.get("quote_category") == "fast_track") or (
        (quote.get("quote_type") or "").upper() == "FAST_TRACK"
    )
    if is_fast_track:
        # Estados válidos sin disparar ruptura: Aprobada, Configurada, o
        # cualquier estado posterior a Aprobada en el orden natural.
        is_irregular = current_status not in (
            "Aprobada", "Configurada", "Facturada", "Pagada"
        )
    else:
        is_irregular = current_status != "Pagada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para enviar a implementación sin pago registrado")
        await mark_quote_irregular(quote_id, "send-to-implementation", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "send-to-implementation", "Pagada", current_status, exception_reason, regularization_date, current_user)
    
    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    quote["client_name"] = client_name
    quote["client_rif"] = client.get('rif', 'N/A') if client else 'N/A'

    # Generar PDF de Ficha Técnica de Implementación
    from services.implementation_pdf import generate_implementation_pdf
    contacts = client.get('contacts', []) if client else []

    # PASO 1: Resolver distribución de sucursales (priorizar datos del modal multitienda)
    if body and body.is_multistore and body.stores:
        # Datos frescos del modal: convertir al formato branch_details
        branches = [{"store_name": s.get("name", ""), "quantity": s.get("box_count", 0)} for s in body.stores]
        # Persistir en BD para consistencia
        await db.quotes.update_one({"quote_id": quote_id}, {"$set": {"branch_details": branches}})
    else:
        # PASO 2: Consulta fresca a la BD (no usar caché de la variable quote)
        fresh_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0, "branch_details": 1})
        branches = (fresh_quote or {}).get('branch_details', [])

    # PASO 3: Generar PDF (si falla, retornar error sin enviar email ni tocar BD)
    # Inyectar datos PYME (servidor/pinpads) en el quote para el PDF
    if body and body.server_name:
        quote["server_name"] = body.server_name
    # Grupo Económico y Nombre de Fantasía con defaults sensatos
    if body and body.economic_group is not None:
        quote["economic_group"] = body.economic_group.strip() if body.economic_group.strip() else "Sin Grupo Económico"
    else:
        quote["economic_group"] = "Sin Grupo Económico"
    if body and body.fantasy_name is not None and body.fantasy_name.strip():
        quote["fantasy_name"] = body.fantasy_name.strip()
    else:
        # Hereda de Nombre del Comercio (legal_name) o fantasy_name del cliente
        quote["fantasy_name"] = client_name
    if body and body.pinpad_serials:
        quote["pinpad_serials"] = body.pinpad_serials
    if body and body.equipment_serials:
        quote["equipments"] = body.equipment_serials
    # Instrucciones adicionales para el implementador (HTML rich-text, máx 500 chars visibles)
    impl_instructions = _validate_instructions_length(body.implementation_instructions if body else None, 500)
    quote["implementation_instructions"] = impl_instructions
    try:
        impl_pdf_bytes = generate_implementation_pdf(quote, client or {}, contacts, branches)
    except Exception as e:
        logger.error(f"Error generando PDF de implementación para {quote_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando Ficha Técnica PDF: {str(e)}")

    # PASO 4: Crear Proyecto PRIMERO (transaccional a nivel de aplicación)
    # Si falla, NO se envía email ni se modifica la cotización
    is_mpos_fast_track = (quote.get("quote_category") == "fast_track")
    try:
        quote_for_project = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
        if not quote_for_project:
            raise HTTPException(status_code=404, detail="Cotización no encontrada al crear proyecto")

        # === ARCHIVAR EN HISTÓRICO antes de crear el proyecto (que borra la cotización) ===
        # EXCEPCIÓN: Para MPOS Imple+POS (fast_track), la cotización se
        # PRESERVA activa en la grilla principal hasta el "Marcar como
        # Entregada" — por lo tanto NO se archiva aquí.
        if not is_mpos_fast_track:
            try:
                from routes.quote_history import archive_quote_to_history
                await archive_quote_to_history(quote_id, "status_enviada_imple", current_user)
            except Exception as arch_err:
                logger.error(f"Error archivando {quote_id} al histórico: {arch_err}")

        multistore_data = None
        if body and body.is_multistore and body.stores:
            multistore_data = {"is_multistore": True, "stores": body.stores}
        equipment_data = None
        if body and body.equipment_serials:
            equipment_data = body.equipment_serials
        pt_impl = body.project_type_impl if body else None
        srv_name = body.server_name if body else None
        pp_serials = body.pinpad_serials if body else None
        # Inyectar Grupo Económico y Nombre de Fantasía ya normalizados (con defaults aplicados arriba)
        eg = quote.get("economic_group")
        fn = quote.get("fantasy_name")
        ii = quote.get("implementation_instructions")
        # Modelo de impresora fiscal (capturado en el wizard) → persistir en
        # la cotización y propagar al proyecto para que aparezca en la Ficha Técnica.
        fp_model = (body.fiscal_printer_model if body else None) or ""
        if fp_model:
            quote["fiscal_printer_model"] = fp_model
            await db.quotes.update_one(
                {"quote_id": quote_id},
                {"$set": {"fiscal_printer_model": fp_model}},
            )
        await _create_project_from_quote(
            quote_for_project, quote_id, multistore_data, equipment_data,
            pt_impl, srv_name, pp_serials, eg, fn, ii,
            keep_quote_active=is_mpos_fast_track,
            fiscal_printer_model=fp_model,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creando proyecto desde cotización {quote_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando proyecto: {str(e)}")

    # PASO 5: Solo enviar email si el proyecto se creó exitosamente
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # Anexos manuales del modal "Personalizar Comunicación"
    _manual_attachments = await _resolve_manual_attachments(manual_attachment_ids)

    # === Notification Engine (Phase 2) ===
    _engine_result = await _engine_or_legacy(
        "send_to_implementation", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        implementation_pdf_bytes=impl_pdf_bytes,
        extra_attachments=_manual_attachments or None,
    )
    if _engine_result is not None:
        return {"message": "Enviado a implementación", "new_status": "Enviada a Imple", "emails": _engine_result}

    email_results = await send_workflow_notification(
        action="send-to-implementation",
        quote=quote,
        current_user=current_user,
        custom_message=custom_message,
        pdf_buffer=impl_pdf_bytes,
        cc_emails=cc_emails,
        extra_attachments=_manual_attachments or None,
    )

    return {"message": "Enviado a implementación", "new_status": "Enviada a Imple", "emails": email_results}


# ==================== FLUJO DE FACTURACIÓN Y COBRO ====================

@router.post("/quotes/{quote_id}/invoice")
async def invoice_quote(quote_id: str, invoice_number: str = Form(None), exception_reason: str = Form(None), regularization_date: str = Form(None), authorization: Optional[str] = Header(None), x_exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), x_regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Facturar cotización - Requiere anexo de 'Factura'. Soporta flujo irregular y mensaje personalizado."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    quote_category = quote.get("quote_category", "implementation")
    expected_invoice_status = "Reparada" if quote_category == "repair" else "Configurada" if quote_category == "fast_track" else "Aprobada"
    is_irregular = current_status != expected_invoice_status
    
    exc_reason = exception_reason or x_exception_reason
    exc_date = regularization_date or x_regularization_date
    
    if is_irregular:
        if not exc_reason:
            raise HTTPException(status_code=422, detail=f"IRREGULAR:Debe proporcionar un motivo para facturar sin estado '{expected_invoice_status}'")
        await mark_quote_irregular(quote_id, "invoice", exc_reason, exc_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "invoice", expected_invoice_status, current_status, exc_reason, exc_date, current_user)
    
    attachments = quote.get("attachments", [])
    factura_attachments = [a for a in attachments if a.get("category") == "Factura"]
    if not factura_attachments:
        raise HTTPException(status_code=422, detail="Debe cargar el documento de Factura antes de facturar la cotización")
    
    invoice_url = factura_attachments[-1].get("url", "")
    
    is_regul = is_regularization(current_status, "invoice")
    update_set = {
        "invoiced_at": datetime.now(timezone.utc).isoformat(),
        "invoice_pdf_url": invoice_url,
        "invoice_number": invoice_number
    }
    if not is_regul:
        update_set["quote_status"] = "Facturada"
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_set})

    # === Notification Engine (Phase 2) ===
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]
    _engine_invoice_pdf_bytes = None
    try:
        _factura = factura_attachments[-1]
        _factura_path = UPLOADS_DIR / _factura.get("url", "").replace("/uploads/", "")
        if _factura_path.exists():
            _engine_invoice_pdf_bytes = open(_factura_path, "rb").read()
    except Exception as _e:
        logger.warning(f"[invoice] No se pudo precargar factura para engine: {_e}")
    _engine_result = await _engine_or_legacy(
        "invoice", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        invoice_pdf_bytes=_engine_invoice_pdf_bytes,
        extra_attachments=(await _resolve_manual_attachments(manual_attachment_ids)) or None,
    )
    if _engine_result is not None:
        await _push_quote_event(
            "quote_invoiced", quote,
            title=f"Cotización {quote.get('quote_number','')} facturada",
            message=f"Factura: {invoice_number}",
        )
        return {"message": "Cotización facturada exitosamente", "invoice_pdf_url": invoice_url, "invoice_number": invoice_number, "emails": _engine_result}

    # Enviar notificación con archivo de Factura adjunto
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    quote_sede = quote.get("sede", "PYME")
    norm_sede = "PYME" if quote_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if quote_sede in ("CORP", "Corp", "Corporativo") else quote_sede
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(norm_sede, {})
    admin_email = sede_emails.get("admin") or (config.get("admin_email") if config else None)
    sales_email = sede_emails.get("sales") if sede_emails else None

    client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
    client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
    
    # Buscar plantilla por sede primero, luego genérica
    is_equipment_quote = quote.get("quote_category") == "equipment"
    is_fast_track_quote = quote.get("quote_category") == "fast_track"
    is_repair_quote = quote.get("quote_category") == "repair"
    if is_equipment_quote or is_fast_track_quote:
        template = await get_email_template(f"equipment_invoice_{norm_sede}")
        if not template:
            template = await get_email_template("equipment_invoice")
    elif is_repair_quote:
        template = await get_email_template(f"repair_invoice_{norm_sede}")
        if not template:
            template = await get_email_template("repair_invoice")
    else:
        template = await get_email_template(f"invoice_{norm_sede}")
        if not template:
            template = await get_email_template("invoice")
    if not template:
        template = {
            "subject": "Cotización {{quote_number}} Facturada",
            "body_html": "<h2>Cotización Facturada</h2><p>La cotización <strong>{{quote_number}}</strong> ha sido facturada.</p><p><strong>Cliente:</strong> {{client_name}}</p><p><strong>Factura:</strong> {{invoice_number}}</p><p><strong>Total USD:</strong> ${{total_usd}}</p>"
        }
    
    # Resolver datos del ejecutivo creador
    creator_name, creator_email = "", ""
    creator_user_id = quote.get("created_by_user_id")
    if creator_user_id:
        creator = await db.users.find_one({"user_id": creator_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
        if creator:
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            creator_email = creator.get("email", "")

    template_vars = {
        "quote_number": quote.get('quote_number', ''),
        "Cotizacion_Nro": quote.get('quote_number', ''),
        "Nombre_Cliente": client_name,
        "client_name": client_name,
        "Rif_Cliente": client.get('rif', 'N/A') if client else 'N/A',
        "client_rif": client.get('rif', 'N/A') if client else 'N/A',
        "invoice_number": invoice_number or 'No especificado',
        "Referencia_Factura": invoice_number or 'No especificado',
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Monto_Total": f"{quote.get('total_usd', 0):.2f}",
        "sede_name": norm_sede,
        "Nombre_Ejecutivo": creator_name,
        "Email_Ejecutivo": creator_email,
    }
    subject = render_email_template(template["subject"], template_vars)
    html_content = render_email_template(template["body_html"], template_vars)

    # Agregar mensaje personalizado
    if custom_message and custom_message.strip():
        user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content = inject_custom_message(html_content, custom_message, user_name, max_chars=300)

    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # Preparar adjunto de Factura con nombre descriptivo
    factura_file = factura_attachments[-1]
    factura_path = UPLOADS_DIR / factura_file.get("url", "").replace("/uploads/", "")
    invoice_attachments = None
    if factura_path.exists():
        with open(factura_path, 'rb') as f:
            factura_b64 = base64.b64encode(f.read()).decode('utf-8')
        # Nombre descriptivo: Factura_{Nro_Cotizacion}_{Nombre_Cliente}.ext
        original_name = factura_file.get("filename", "factura.pdf")
        ext = original_name.rsplit('.', 1)[-1] if '.' in original_name else 'pdf'
        safe_client = (client_name or "Cliente").replace(" ", "_").replace("/", "_")[:40]
        descriptive_name = f"Factura_{quote.get('quote_number', 'SN')}_{safe_client}.{ext}"
        invoice_attachments = [{"filename": descriptive_name, "content": factura_b64}]

    email_results = []
    # Para equipos y fast_track: enviar SOLO a Ventas sede. Para reparaciones: a Operaciones sede. Para implementación: a Admin + Ventas
    if is_equipment_quote or is_fast_track_quote:
        recipients = [(sales_email, "invoice_sales")]
        if not sales_email:
            recipients = [("ventas@sede.local", "invoice_no_config")]
    elif is_repair_quote:
        operations_email = sede_emails.get("operations") if sede_emails else None
        recipients = [(operations_email, "invoice_repair_operations")]
        if not operations_email:
            recipients = [(admin_email, "invoice_repair_admin")]
        if not operations_email and not admin_email:
            recipients = [("operaciones@sede.local", "invoice_no_config")]
    else:
        recipients = [(admin_email, "invoice_admin"), (sales_email, "invoice_sales")]
        if not admin_email and not sales_email:
            recipients = [("admin@sede.local", "invoice_no_config")]
    
    for email, action in recipients:
        if email:
            prefix = "[VENTAS] " if "sales" in action else ""
            r = await send_email(to=[email], subject=f"{prefix}{subject}", html=html_content, action=action, quote_id=quote_id, quote_number=quote.get('quote_number'), attachments=invoice_attachments)
            email_results.append(r)
    
    for cc in cc_emails:
        r = await send_email(to=[cc], subject=f"[CC] {subject}", html=html_content, action="invoice_cc", quote_id=quote_id, quote_number=quote.get('quote_number'), attachments=invoice_attachments)
        email_results.append(r)

    # Push notification (evento #3 Cotización facturada)
    await _push_quote_event(
        "quote_invoiced", quote,
        title=f"Cotización {quote.get('quote_number','')} facturada",
        message=f"Factura: {invoice_number}",
    )

    return {"message": "Cotización facturada exitosamente", "invoice_pdf_url": invoice_url, "invoice_number": invoice_number, "emails": email_results}


@router.post("/quotes/{quote_id}/collect")
async def collect_quote(quote_id: str, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Marcar cotización como Pagada - Requiere anexos en categoría 'Pagos'. Soporta flujo irregular y mensaje personalizado."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Facturada"
    
    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para cobrar sin facturar previamente")
        await mark_quote_irregular(quote_id, "collect", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "collect", "Facturada", current_status, exception_reason, regularization_date, current_user)
    
    attachments = quote.get("attachments", [])
    payment_proofs = [a for a in attachments if a.get("category") == "Pagos"]
    if not payment_proofs:
        raise HTTPException(status_code=422, detail="Debe cargar al menos un comprobante de pago antes de registrar el cobro")
    
    is_regul = is_regularization(current_status, "collect")
    update_set = {"paid_at": datetime.now(timezone.utc).isoformat()}
    if not is_regul:
        update_set["quote_status"] = "Pagada"
    
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_set})
    
    email_results = []
    quote_category = quote.get("quote_category", "implementation")
    
    # Parsear CC y mensaje personalizado
    cc_emails = [e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()]

    # === Notification Engine (Phase 2) ===
    # Cargar comprobantes de pago como extra_attachments (siempre se anexan).
    _engine_extra: list[dict] = []
    for _pp in payment_proofs:
        try:
            _pp_path = UPLOADS_DIR / _pp.get("url", "").replace("/uploads/", "")
            if _pp_path.exists():
                with open(_pp_path, "rb") as _fh:
                    _engine_extra.append({
                        "filename": _pp.get("name") or _pp_path.name,
                        "content": base64.b64encode(_fh.read()).decode("utf-8"),
                    })
        except Exception as _e:
            logger.warning(f"[collect] No se pudo leer comprobante de pago {_pp.get('name')}: {_e}")

    # Anexos manuales del modal "Personalizar Comunicación"
    _manual_attachments = await _resolve_manual_attachments(manual_attachment_ids)
    if _manual_attachments:
        _engine_extra.extend(_manual_attachments)

    _engine_result = await _engine_or_legacy(
        "collect", quote, current_user,
        custom_message=custom_message, cc_emails=cc_emails,
        extra_attachments=_engine_extra or None,
    )
    if _engine_result is not None:
        raw_sede = quote.get("sede", quote.get("client_segment", "PYME"))
        norm_sede_audit = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
        user_name_audit = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "Sistema"
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$push": {"status_history": {
                "status": "Pagada",
                "action": "collect",
                "detail": f"Notificación enviada vía Motor Dinámico (Sede {norm_sede_audit})",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": user_name_audit,
            }}}
        )
        # Auto-regularización tras pushear nuevo status
        try:
            from routes.quote_helpers import try_auto_regularize_quote
            await try_auto_regularize_quote(quote_id)
        except Exception:
            pass
        await _push_quote_event(
            "quote_collected", quote,
            title=f"Cotización {quote.get('quote_number','')} cobrada/pagada",
            message=f"Cliente {quote.get('client_name','')} · Total USD ${quote.get('total_usd',0):,.2f}",
        )
        return {"message": "Cotización marcada como Pagada", "emails": _engine_result}

    if quote_category == "equipment":
        # Usar plantilla equipment_collect para notificar pago de equipos
        # Destino: Almacén sede (warehouse)
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        quote["client_name"] = client_name
        quote["client_rif"] = client.get('rif', 'N/A') if client else 'N/A'

        # Resolver warehouse email de la sede
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        raw_sede = quote.get("sede", "PYME")
        norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
        sede_emails = config.get("emails_by_sede", {}).get(norm_sede, {}) if config else {}
        warehouse_email = sede_emails.get("warehouse")
        if not warehouse_email:
            warehouse_email = "almacen@simulado.local"

        email_results = await send_workflow_notification(
            action="collect",
            quote=quote,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
            template_base_override="equipment_collect",
            override_recipients=[warehouse_email],
        )
    elif quote_category == "fast_track":
        # Fast Track: Notificar a Almacén con plantilla Orden de Entrega de Equipos
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        quote["client_name"] = client_name
        quote["client_rif"] = client.get('rif', 'N/A') if client else 'N/A'

        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        raw_sede = quote.get("sede", "PYME")
        norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
        sede_emails = config.get("emails_by_sede", {}).get(norm_sede, {}) if config else {}
        warehouse_email = sede_emails.get("warehouse")
        if not warehouse_email:
            warehouse_email = "almacen@simulado.local"

        email_results = await send_workflow_notification(
            action="collect",
            quote=quote,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
            template_base_override="equipment_delivery",
            override_recipients=[warehouse_email],
        )
    elif quote_category == "repair":
        # Reparaciones: Enviar ORDEN DE DESPACHO al Almacén + CC al ejecutivo
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        quote_sede = quote.get("sede", "PYME")
        norm_sede = "PYME" if quote_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if quote_sede in ("CORP", "Corp", "Corporativo") else quote_sede
        emails_by_sede = config.get("emails_by_sede", {}) if config else {}
        sede_emails = emails_by_sede.get(norm_sede, {})
        warehouse_email = sede_emails.get("warehouse") or (config.get("warehouse_email") if config else None)
        if not warehouse_email:
            warehouse_email = "almacen@simulado.local"

        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'

        # Resolver almacén de custodia (sede del equipo)
        sede_names = {"PYME": "Torre Banco Plaza", "TBP": "Torre Banco Plaza", "CORP": "Los Chaguaramos"}
        almacen_custodia = sede_names.get(norm_sede, norm_sede)

        # Construir lista de equipos/seriales desde taller_equipos
        equipos_taller = await db.taller_equipos.find(
            {"quote_id": quote_id, "estatus": "En reparación"}, {"_id": 0, "modelo": 1, "serial": 1}
        ).to_list(1000)
        modelos_map = {}
        for eq in equipos_taller:
            modelo = eq.get("modelo", "Sin modelo")
            if modelo not in modelos_map:
                modelos_map[modelo] = []
            modelos_map[modelo].append(eq.get("serial", ""))
        lista_equipos_html = ""
        for modelo, serials in modelos_map.items():
            lista_equipos_html += f"<p style='margin:4px 0'><strong>{modelo}</strong> ({len(serials)} uds): {', '.join(serials)}</p>"
        if not lista_equipos_html:
            # Fallback desde repair_models de la cotización
            for rm in quote.get("repair_models", []):
                srs = rm.get("serials", [])
                lista_equipos_html += f"<p style='margin:4px 0'><strong>{rm.get('model_name', 'N/A')}</strong> ({len(srs)} uds): {', '.join(srs)}</p>"
        if not lista_equipos_html:
            lista_equipos_html = "<p>Ver detalle en la cotización del sistema.</p>"

        # Cargar plantilla
        rw_template = await get_email_template(f"repair_collect_warehouse_{norm_sede}")
        if not rw_template:
            rw_template = await get_email_template("repair_collect_warehouse")
        if not rw_template:
            rw_template = {
                "subject": "ORDEN DE DESPACHO: Pago Confirmado - Cotización #{nro_cotizacion} - {nombre_cliente}",
                "body_html": "<h2>Orden de Despacho — Equipos Reparados</h2><p>Pago confirmado para <strong>{nombre_cliente}</strong>. Se autoriza la salida de los activos bajo custodia.</p><p><strong>Cotización:</strong> {nro_cotizacion}</p><div>{lista_equipos_seriales}</div><p><strong>Ubicación:</strong> {almacen_custodia}</p>"
            }

        # Resolver datos del ejecutivo creador
        creator_name, creator_email = "", ""
        creator_user_id = quote.get("created_by_user_id")
        if creator_user_id:
            creator = await db.users.find_one({"user_id": creator_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
            if creator:
                creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
                creator_email = creator.get("email", "")

        rw_vars = {
            "nro_cotizacion": quote.get("quote_number", ""),
            "quote_number": quote.get("quote_number", ""),
            "nombre_cliente": client_name,
            "client_name": client_name,
            "lista_equipos_seriales": lista_equipos_html,
            "almacen_custodia": almacen_custodia,
            "Nombre_Ejecutivo": creator_name,
            "Email_Ejecutivo": creator_email,
        }
        rw_subject = render_email_template(rw_template["subject"], rw_vars)
        rw_html = render_email_template(rw_template["body_html"], rw_vars)

        if custom_message and custom_message.strip():
            user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            rw_html = inject_custom_message(rw_html, custom_message, user_name, max_chars=300)

        # Enviar al Almacén
        r = await send_email(to=[warehouse_email], subject=rw_subject, html=rw_html, action="repair_collect_warehouse", quote_id=quote_id, quote_number=quote.get('quote_number'))
        email_results.append(r)

        # CC al Ejecutivo creador (informativo)
        if creator_email and "@" in creator_email:
            r = await send_email(to=[creator_email], subject=f"[CC] {rw_subject}", html=rw_html, action="repair_collect_cc_exec", quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)

        for cc in cc_emails:
            r = await send_email(to=[cc], subject=f"[CC] {rw_subject}", html=rw_html, action="repair_collect_cc", quote_id=quote_id, quote_number=quote.get('quote_number'))
            email_results.append(r)
    else:
        # Workflow centralizado: collect → Ventas (sede) con plantilla comprobante_pago
        client = await db.clients.find_one({"client_id": quote['client_id']}, {"_id": 0})
        client_name = client.get('fantasy_name') or client.get('legal_name') if client else 'Cliente'
        quote["client_name"] = client_name
        
        email_results = await send_workflow_notification(
            action="collect",
            quote=quote,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
        )
    
    # Registrar audit trail en la cotización (status_history)
    raw_sede = quote.get("sede", quote.get("client_segment", "PYME"))
    norm_sede_audit = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
    user_name_audit = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() if current_user else "Sistema"
    # Extraer emails de los resultados de envío (campo 'message' contiene "Email enviado a X")
    sent_addresses = []
    for r in email_results:
        if r.get("status") in ("sent", "simulated"):
            msg = r.get("message", "")
            if "enviado a " in msg:
                sent_addresses.append(msg.split("enviado a ")[-1])
    audit_detail = f"Notificación de pago enviada a Ventas Sede {norm_sede_audit}"
    if sent_addresses:
        audit_detail += f" ({', '.join(sent_addresses)})"
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$push": {"status_history": {
            "status": "Pagada",
            "action": "collect",
            "detail": audit_detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user_name_audit
        }}}
    )
    # Auto-regularización tras pushear nuevo status
    try:
        from routes.quote_helpers import try_auto_regularize_quote
        await try_auto_regularize_quote(quote_id)
    except Exception:
        pass
    
    # Push notification (evento #4 Cotización pagada/cobrada)
    await _push_quote_event(
        "quote_collected", quote,
        title=f"Cotización {quote.get('quote_number','')} cobrada/pagada",
        message=f"Cliente {quote.get('client_name','')} · Total USD ${quote.get('total_usd',0):,.2f}",
    )

    return {"message": "Cotización marcada como Pagada", "emails": email_results}


@router.get("/quotes/{quote_id}/delivery-prep")
async def delivery_preparation(quote_id: str, warehouse_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Devuelve los datos de preparación para entrega: items de la cotización y stock disponible."""
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if quote.get("quote_category") not in ("equipment", "fast_track"):
        raise HTTPException(status_code=400, detail="Solo cotizaciones de equipos o Fast Track soportan entrega")

    # Para Fast Track usar ft_equipment_items, para equipment usar equipment_items
    if quote.get("quote_category") == "fast_track":
        equipment_items = quote.get("ft_equipment_items", [])
    else:
        equipment_items = quote.get("equipment_items", [])

    # Almacenes disponibles
    warehouses = await db.warehouses.find({}, {"_id": 0}).sort("name", 1).to_list(100)

    # Stock por almacén si se especifica
    stock_by_item = {}
    if warehouse_id:
        movements = await db.inventory_movements.find(
            {"warehouse_id": warehouse_id}, {"_id": 0}
        ).to_list(2000)
        stock = {}
        for m in movements:
            iid = m["item_id"]
            if iid not in stock:
                stock[iid] = {"quantity": 0, "serials": [], "item_type": m.get("item_type", "")}
            sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
            stock[iid]["quantity"] += sign * m["quantity"]
            if m.get("serials"):
                if sign > 0:
                    stock[iid]["serials"].extend(m["serials"])
                else:
                    for s in m["serials"]:
                        if s in stock[iid]["serials"]:
                            stock[iid]["serials"].remove(s)
        stock_by_item = stock

    # Enrich items with stock info
    # `requires_serial` se calcula desde el catálogo `hardware` (no desde el
    # snapshot guardado en la cotización ni desde stock), para asegurar
    # consistencia con `deliver_quote` y evitar el bug en el que el frontend
    # mostraba el ítem como no-serializado y el backend lo exigía serializado.
    items_with_stock = []
    hw_ids = [item.get("hardware_id", "") for item in equipment_items if item.get("hardware_id")]
    hw_map = {}
    if hw_ids:
        async for h in db.hardware.find({"hardware_id": {"$in": hw_ids}}, {"_id": 0, "hardware_id": 1, "type": 1}):
            hw_map[h["hardware_id"]] = h.get("type", "")
    for item in equipment_items:
        hw_id = item.get("hardware_id", "")
        st = stock_by_item.get(hw_id, {})
        canonical_type = hw_map.get(hw_id) or st.get("item_type", "") or item.get("hardware_type", "")
        items_with_stock.append({
            "hardware_id": hw_id,
            "name": item.get("name", ""),
            "hardware_type": canonical_type,
            "quantity_quoted": item.get("quantity", 1),
            "stock_available": st.get("quantity", 0),
            "serials_available": st.get("serials", []),
            "requires_serial": (canonical_type or "").lower() in SERIALIZED_TYPES,
        })

    return {
        "quote_number": quote.get("quote_number", ""),
        "client_id": quote.get("client_id", ""),
        "client_name": quote.get("client_name", ""),
        "warehouses": warehouses,
        "items": items_with_stock,
    }


@router.post("/quotes/{quote_id}/deliver")
async def deliver_quote(quote_id: str, body: dict = {}, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Marcar cotización de equipos o reparaciones como Entregada, con deducción automática de inventario y generación de Hoja de Ruta."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    quote_category = quote.get("quote_category", "implementation")
    if quote_category not in ["equipment", "repair", "fast_track"]:
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de equipos o reparaciones")

    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Pagada"

    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para entregar sin pago registrado")
        await mark_quote_irregular(quote_id, "deliver", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "deliver", "Pagada", current_status, exception_reason, regularization_date, current_user)

    warehouse_id = body.get("warehouse_id")
    delivery_items = body.get("delivery_items", [])
    delivery_notes = body.get("notes", "")
    # Logistics fields
    delivery_method = body.get("delivery_method", "personalizada")
    receiver_name = body.get("receiver_name", "")
    receiver_cedula = body.get("receiver_cedula", "")
    receiver_phone = body.get("receiver_phone", "")
    courier_name = body.get("courier_name", "")
    courier_office = body.get("courier_office", "")
    delivery_invoice_number = body.get("invoice_number", "")
    # Legacy compatibility
    transportista = courier_name if delivery_method == "courier" else receiver_name
    guia_placa = courier_office if delivery_method == "courier" else ""
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()

    # Get client info
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    # Para Nota de Entrega: "Razón Social" debe ser SIEMPRE el legal_name (Nombre Jurídico).
    # Antes se usaba fantasy_name como fallback primario, causando que la nota imprimiera
    # el nombre de fantasía bajo la etiqueta "Razón Social".
    client_name = (client.get("legal_name") or client.get("fantasy_name", "") or "") if client else (quote.get("client_name") or "")
    client_rif = (client.get("rif") or "") if client else ""
    client_address = (client.get("address") or "") if client else ""

    hoja_ruta_url = None
    delivered_pdf_items = []

    # Fast Track con equipos (Mega Soft): usar ft_equipment_items de la cotización
    is_fast_track_with_equipment = quote_category == "fast_track" and quote.get("ft_equipment_items")
    
    if is_fast_track_with_equipment and not delivery_items:
        # Construir delivered_pdf_items desde ft_equipment_items
        for ft_item in quote.get("ft_equipment_items", []):
            delivered_pdf_items.append({
                "name": ft_item.get("name", "Equipo"),
                "type": ft_item.get("hardware_type", "POS"),
                "quantity": int(ft_item.get("quantity", 1)),
                "serials": [],
                "category": "Equipo"
            })

    # Process inventory exits if warehouse and items provided
    if warehouse_id and delivery_items:
        wh = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0})
        if not wh:
            raise HTTPException(status_code=404, detail="Almacén no encontrado")

        warehouse_name = wh.get("name", "")

        # ============================================================
        # FASE 1 — PRE-VALIDACIÓN ATÓMICA
        # Recorrer TODOS los items y validar stock + seriales ANTES de
        # insertar cualquier movimiento. Si algún item falla, abortamos
        # sin modificar la BD (evita descontar parcialmente del inventario
        # y dejar la cotización en estado inconsistente).
        # ============================================================
        validated_items: list = []  # [{hw, hw_type, requires_serial, qty, serials, avg_cost}]
        for d_item in delivery_items:
            hw_id = d_item.get("hardware_id", "")
            qty = d_item.get("quantity", 0)
            serials = d_item.get("serials", []) or []
            if not hw_id or qty <= 0:
                continue

            hw = await db.hardware.find_one({"hardware_id": hw_id}, {"_id": 0})
            if not hw:
                raise HTTPException(status_code=404, detail=f"Producto {hw_id} no encontrado en catálogo")

            hw_type = hw.get("type", "General")
            requires_serial = hw_type.lower() in SERIALIZED_TYPES

            # Stock + seriales disponibles
            movements = await db.inventory_movements.find(
                {"warehouse_id": warehouse_id, "item_id": hw_id}, {"_id": 0}
            ).to_list(2000)
            stock_qty = 0
            stock_serials: list = []
            cost_total = 0
            for m in movements:
                sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
                stock_qty += sign * m["quantity"]
                cost_total += sign * m["quantity"] * m.get("unit_cost", 0)
                if m.get("serials"):
                    if sign > 0:
                        stock_serials.extend(m["serials"])
                    else:
                        for s in m["serials"]:
                            if s in stock_serials:
                                stock_serials.remove(s)
            avg_cost = round(cost_total / stock_qty, 2) if stock_qty > 0 else 0

            if stock_qty < qty:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente de '{hw['name']}'. Disponible: {stock_qty}, Solicitado: {qty}")

            if requires_serial:
                # Compatibilidad: el frontend puede haber enviado serials=[]
                # si `delivery-prep` clasificó el ítem como no-serializado
                # (desalineación entre catálogo y snapshot de la cotización).
                # Cuando el usuario sí seleccionó seriales, deben coincidir
                # con la cantidad. Cuando no, exigirlos.
                if len(serials) != qty:
                    raise HTTPException(status_code=400, detail=f"Debe seleccionar {qty} serial(es) para '{hw['name']}'")
                for s in serials:
                    if s not in stock_serials:
                        raise HTTPException(status_code=400, detail=f"Serial '{s}' no disponible en almacén")

            validated_items.append({
                "hw": hw, "hw_type": hw_type, "requires_serial": requires_serial,
                "qty": qty, "serials": serials, "avg_cost": avg_cost,
            })

        # ============================================================
        # FASE 2 — EJECUCIÓN (inserts)
        # Todas las validaciones pasaron → procesar inserts.
        # ============================================================
        for v in validated_items:
            hw = v["hw"]
            hw_type = v["hw_type"]
            requires_serial = v["requires_serial"]
            qty = v["qty"]
            serials = v["serials"]
            avg_cost = v["avg_cost"]

            exit_mov = InventoryMovement(
                warehouse_id=warehouse_id,
                item_id=hw["hardware_id"],
                item_name=hw["name"],
                item_type=hw_type,
                movement_type="salida",
                quantity=qty,
                unit_cost=avg_cost,
                serials=serials if requires_serial else [],
                reference=f"Factura: {delivery_invoice_number or 'S/N'} | Cotización: {quote.get('quote_number', '')}",
                client_name=client_name,
                client_id=quote.get("client_id", ""),
                quote_id=quote_id,
                quote_number=quote.get("quote_number", ""),
                notes=f"Salida automática por entrega de cotización {quote.get('quote_number', '')}",
                created_by=user_name,
            )
            doc = exit_mov.model_dump()
            doc["created_at"] = doc["created_at"].isoformat()
            await db.inventory_movements.insert_one(doc)
            doc.pop("_id", None)

            # Trigger CheckStock alert
            from routes.inventory import check_stock_alert
            await check_stock_alert(warehouse_id, hw["hardware_id"], hw["name"])

            delivered_pdf_items.append({
                "name": hw["name"],
                "type": hw_type,
                "quantity": qty,
                "serials": serials if requires_serial else [],
            })

    # Generate Nota de Entrega PDF (for both warehouse delivery and Fast Track with equipment)
    if delivered_pdf_items:
        try:
            logo_path = None
            logo_file = UPLOADS_DIR / "logo.png"
            if logo_file.exists():
                logo_path = str(logo_file)

            # Generate correlativo NE-YYYY-XXXX
            year = datetime.now(timezone.utc).strftime("%Y")
            last_ne = await db.nota_entrega_counter.find_one_and_update(
                {"year": year},
                {"$inc": {"counter": 1}},
                upsert=True,
                return_document=True,
            )
            if last_ne and "_id" in last_ne:
                del last_ne["_id"]
            ne_num = last_ne.get("counter", 1) if last_ne else 1
            correlativo = f"NE-{year}-{ne_num:04d}"

            # Get project info if exists
            project = await db.projects.find_one({"quote_id": quote_id}, {"_id": 0})
            project_number = project.get("project_number", "") if project else ""

            # Get client contact info
            contact_name = ""
            contact_phone = ""
            if client:
                contact1 = client.get("contact1") or {}
                contacts_crm = client.get("contacts", [])
                if contact1 and contact1.get("name"):
                    contact_name = contact1.get("name", "")
                    contact_phone = contact1.get("phone", "")
                elif contacts_crm:
                    contact_name = contacts_crm[0].get("full_name", "")
                    contact_phone = contacts_crm[0].get("phone", "")

            # Classify items (Equipo vs Consumible)
            SERIALIZED = ["pos", "pinpad", "mpos"]
            for pdi in delivered_pdf_items:
                if "category" not in pdi:
                    pdi["category"] = "Equipo" if pdi.get("type", "").lower() in SERIALIZED else "Consumible"

            # Determine warehouse name for PDF
            warehouse_name_for_pdf = ""
            if warehouse_id:
                wh_doc = await db.warehouses.find_one({"warehouse_id": warehouse_id}, {"_id": 0, "name": 1})
                warehouse_name_for_pdf = wh_doc.get("name", "") if wh_doc else ""
            elif is_fast_track_with_equipment:
                warehouse_name_for_pdf = "Despacho Fast Track"

            pdf_buffer = generate_nota_entrega_pdf(
                correlativo=correlativo,
                quote_number=quote.get("quote_number", ""),
                project_number=project_number,
                client_name=client_name,
                client_rif=client_rif,
                client_address=client_address,
                client_contact_name=contact_name,
                client_contact_phone=contact_phone,
                warehouse_name=warehouse_name_for_pdf,
                delivered_items=delivered_pdf_items,
                delivered_by=user_name,
                transportista=transportista,
                guia_placa=guia_placa,
                notes=delivery_notes,
                logo_path=logo_path,
                delivery_method=delivery_method,
                receiver_name=receiver_name,
                receiver_cedula=receiver_cedula,
                receiver_phone=receiver_phone,
                courier_name=courier_name,
                courier_office=courier_office,
            )
            pdf_filename = f"NotaEntrega_{correlativo}.pdf"
            pdf_path = UPLOADS_DIR / pdf_filename
            save_pdf_dual(pdf_path, pdf_buffer.getvalue(), pdf_filename)
            hoja_ruta_url = f"/uploads/{pdf_filename}"

            # Attach to quote
            attachment = {
                "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
                "category": "Nota de Entrega",
                "filename": pdf_filename,
                "url": hoja_ruta_url,
                "uploaded_by": current_user.get("email", "system"),
                "uploaded_by_name": user_name,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "content_type": "application/pdf",
            }
            await db.quotes.update_one(
                {"quote_id": quote_id},
                {"$push": {"attachments": attachment}}
            )

            # Also attach to client annexes
            if client:
                client_attachment = {**attachment, "attachment_id": f"att_{uuid.uuid4().hex[:12]}"}
                await db.clients.update_one(
                    {"client_id": quote.get("client_id")},
                    {"$push": {"attachments": client_attachment}}
                )

            logger.info(f"Nota de Entrega generada: {hoja_ruta_url}")
        except Exception as e:
            logger.error(f"Error generando Nota de Entrega: {e}")
            import traceback
            traceback.print_exc()

    # Update quote status
    update_set = {
        "quote_status": "Entregada",
        "delivered_at": datetime.now(timezone.utc).isoformat()
    }
    if delivery_invoice_number:
        update_set["delivery_invoice_number"] = delivery_invoice_number
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": update_set})

    # === TRIGGER: Archivar en histórico (estado final) ===
    try:
        from routes.quote_history import archive_quote_to_history
        await archive_quote_to_history(quote_id, "status_entregada", current_user if 'current_user' in dir() else None)
    except Exception as e:
        logger.error(f"Error archivando cotización {quote_id} al histórico: {e}")

    # Fast Track: Transicionar seriales preasignados → asignados + crear movimiento de salida
    # (movido arriba del engine: side-effect de inventario debe ejecutarse SIEMPRE,
    # con o sin notificación dinámica)
    if quote_category == "fast_track":
        try:
            preassigned = await db.serial_assignments.find(
                {"quote_id": quote_id, "status": "preasignado"}, {"_id": 0}
            ).to_list(500)
            if preassigned:
                now_deliver = datetime.now(timezone.utc).isoformat()
                client_doc = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
                deliver_rif = client_doc.get("rif", "N/A") if client_doc else "N/A"
                serial_list = [p["serial"] for p in preassigned]
                await db.serial_assignments.update_many(
                    {"quote_id": quote_id, "status": "preasignado"},
                    {"$set": {
                        "status": "asignado",
                        "assigned_at": now_deliver,
                        "client_rif": deliver_rif,
                    }}
                )
                wh_id = preassigned[0].get("warehouse_id", "")
                it_id = preassigned[0].get("item_id", "")
                it_name = preassigned[0].get("item_name", "")
                exit_movement = InventoryMovement(
                    movement_id=f"mov_{uuid.uuid4().hex[:12]}",
                    warehouse_id=wh_id,
                    item_id=it_id,
                    item_name=it_name,
                    item_type="pos",
                    movement_type="salida",
                    quantity=len(serial_list),
                    unit_cost=0,
                    serials=serial_list,
                    notes=f"Factura: {delivery_invoice_number or 'S/N'} | Entrega Fast Track - {quote.get('quote_number', '')} - {client_name}",
                    created_by=current_user.get("user_id", ""),
                )
                exit_doc = exit_movement.model_dump()
                exit_doc["created_at"] = exit_doc["created_at"].isoformat()
                await db.inventory_movements.insert_one(exit_doc)
                logger.info(f"[Deliver FT] {len(serial_list)} seriales transicionados a 'asignado' y descargados de inventario")
        except Exception as e:
            logger.error(f"[Deliver FT] Error transicionando seriales: {e}")

    # === Notification Engine (Phase 2) ===
    # El motor solo despacha si hay config admin para esta combinación. Si no
    # hay config, devuelve None y se mantiene la lógica legacy (Fast Track
    # email / sin email para equipment / repair).
    _engine_ne_pdf_bytes = None
    if hoja_ruta_url:
        try:
            _ne_path = UPLOADS_DIR / hoja_ruta_url.replace("/uploads/", "")
            if _ne_path.exists():
                _engine_ne_pdf_bytes = open(_ne_path, "rb").read()
        except Exception as _e:
            logger.warning(f"[deliver] No se pudo precargar Nota de Entrega para engine: {_e}")
    _engine_result = await _engine_or_legacy(
        "deliver", quote, current_user,
        custom_message=custom_message,
        cc_emails=[e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()],
        delivery_note_pdf_bytes=_engine_ne_pdf_bytes,
        extra_attachments=(await _resolve_manual_attachments(manual_attachment_ids)) or None,
    )
    if _engine_result is not None:
        await _push_quote_event(
            "quote_delivered", quote,
            title=f"Cotización {quote.get('quote_number','')} entregada",
            message=f"Items entregados: {len(delivered_pdf_items)} · Cliente {quote.get('client_name','')}",
        )
        return {
            "message": "Cotización marcada como Entregada (motor dinámico)",
            "inventory_processed": len(delivered_pdf_items) > 0,
            "items_delivered": len(delivered_pdf_items),
            "hoja_ruta_url": hoja_ruta_url,
            "emails": _engine_result,
        }

    # Fast Track: Notificar a Ventas con "Equipos listos para ser entregados" + Nota de Entrega PDF
    if quote_category == "fast_track":
        try:
            config_ft = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
            raw_sede_ft = quote.get("sede", "PYME")
            norm_sede_ft = "PYME" if raw_sede_ft in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede_ft in ("CORP", "Corp", "Corporativo") else raw_sede_ft
            sede_emails_ft = (config_ft.get("emails_by_sede", {}) if config_ft else {}).get(norm_sede_ft, {})
            sales_email_ft = sede_emails_ft.get("sales")
            if not sales_email_ft:
                sales_email_ft = "ventas@sede.local"

            creator_name_ft, creator_email_ft = "", ""
            creator_uid = quote.get("created_by_user_id")
            if creator_uid:
                creator_doc = await db.users.find_one({"user_id": creator_uid}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
                if creator_doc:
                    creator_name_ft = f"{creator_doc.get('first_name', '')} {creator_doc.get('last_name', '')}".strip()
                    creator_email_ft = creator_doc.get("email", "")

            deliver_subject = f"Entrega de Equipos - {quote.get('quote_number', '')} - {client_name}"
            deliver_html = f'''<div style="font-family:'Segoe UI',Arial,sans-serif;max-width:700px;margin:0 auto;">
<div style="background:#003366;color:#fff;padding:18px 28px;border-radius:6px 6px 0 0;">
<h2 style="margin:0;font-size:18px;">Equipos Asignados Listos para ser Entregados</h2></div>
<div style="padding:24px 28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 6px 6px;">
<p>Se informa que los equipos de la cotización <strong>{quote.get("quote_number", "")}</strong> (POS Stand Alone - Fast Track) han sido marcados para entrega.</p>
<table style="border-collapse:collapse;width:100%;max-width:500px;margin:16px 0;">
<tr style="background:#f8fafc;"><td style="padding:10px 16px;border:1px solid #e2e8f0;font-weight:bold;color:#475569;width:40%;">Cotización</td><td style="padding:10px 16px;border:1px solid #e2e8f0;">{quote.get("quote_number", "")}</td></tr>
<tr><td style="padding:10px 16px;border:1px solid #e2e8f0;font-weight:bold;color:#475569;">Cliente</td><td style="padding:10px 16px;border:1px solid #e2e8f0;">{client_name}</td></tr>
</table>
<p style="font-size:14px;color:#64748b;"><strong>Ejecutivo:</strong> {creator_name_ft} ({creator_email_ft})</p>
<p style="font-size:14px;color:#64748b;">Por favor coordine con el cliente la logística de entrega final.</p>
</div></div>'''

            # Adjuntar PDF de Nota de Entrega si se generó
            deliver_attachments = None
            if hoja_ruta_url:
                ne_path = UPLOADS_DIR / hoja_ruta_url.replace("/uploads/", "")
                if ne_path.exists():
                    with open(ne_path, "rb") as f:
                        deliver_attachments = [{
                            "filename": ne_path.name,
                            "content": base64.b64encode(f.read()).decode("utf-8"),
                        }]

            r = await send_email(
                to=[sales_email_ft], subject=deliver_subject, html=deliver_html,
                action="deliver_ft_sales", quote_id=quote_id, quote_number=quote.get("quote_number"),
                attachments=deliver_attachments,
            )
            logger.info(f"[FastTrack Deliver] Notificación enviada a Ventas: {sales_email_ft} | {r.get('status')}")
        except Exception as e:
            logger.error(f"[FastTrack Deliver] Error enviando notificación a Ventas: {e}")

    # Push notification (evento #5 Cotización entregada)
    await _push_quote_event(
        "quote_delivered", quote,
        title=f"Cotización {quote.get('quote_number','')} entregada",
        message=f"Items entregados: {len(delivered_pdf_items)} · Cliente {quote.get('client_name','')}",
    )

    return {
        "message": "Cotización marcada como Entregada",
        "inventory_processed": len(delivered_pdf_items) > 0,
        "items_delivered": len(delivered_pdf_items),
        "hoja_ruta_url": hoja_ruta_url,
    }


# ===================== ENTREGA DE REPARACIONES =====================

@router.get("/quotes/{quote_id}/repair-delivery-prep")
async def repair_delivery_prep(quote_id: str, authorization: Optional[str] = Header(None)):
    """Obtener equipos en reparación del cliente para selección de entrega."""
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    client_id = quote.get("client_id", "")

    # Obtener equipos en reparación de ESTA cotización
    equipos_cursor = db.taller_equipos.find(
        {"quote_id": quote_id, "estatus": "En reparación"},
        {"_id": 0}
    )
    equipos = await equipos_cursor.to_list(1000)

    # Contar ya entregados de esta cotización (para info de saldo)
    total_entregados = await db.taller_equipos.count_documents(
        {"quote_id": quote_id, "estatus": "Entregado"}
    )

    # Agrupar por modelo
    modelos_map = {}
    for eq in equipos:
        modelo = eq.get("modelo", "Sin modelo")
        if modelo not in modelos_map:
            modelos_map[modelo] = {
                "modelo": modelo,
                "modelo_id": eq.get("modelo_id", ""),
                "serials": [],
            }
        modelos_map[modelo]["serials"].append({
            "taller_equipo_id": eq.get("taller_equipo_id"),
            "serial": eq.get("serial", ""),
            "quote_number": eq.get("quote_number", ""),
            "fecha_ingreso": eq.get("fecha_ingreso", ""),
        })

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name", "")) if client else ""

    return {
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "quote_status": quote.get("quote_status", ""),
        "client_id": client_id,
        "client_name": client_name,
        "client_rif": (client.get("rif", "") if client else ""),
        "client_address": (client.get("address", "") if client else ""),
        "modelos": list(modelos_map.values()),
        "total_equipos": len(equipos),
        "total_entregados": total_entregados,
        "entrega_completa": quote.get("entrega_completa", False),
    }


@router.post("/quotes/{quote_id}/repair-deliver")
async def repair_deliver(quote_id: str, body: dict = {}, authorization: Optional[str] = Header(None), exception_reason: Optional[str] = Header(None, alias="x-exception-reason"), regularization_date: Optional[str] = Header(None, alias="x-regularization-date"), custom_message: Optional[str] = Header(None, alias="x-custom-message"), additional_recipients: Optional[str] = Header(None, alias="x-additional-recipients"), manual_attachment_ids: Optional[str] = Header(None, alias="x-manual-attachment-ids")):
    """Entregar equipos reparados: actualiza taller_equipos, genera Nota de Entrega, cambia estado."""
    current_user = await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if quote.get("quote_category") != "repair":
        raise HTTPException(status_code=400, detail="Esta acción solo aplica a cotizaciones de reparación")

    # Bloquear si ya fue entregada totalmente
    if quote.get("entrega_completa"):
        raise HTTPException(status_code=400, detail="Esta cotización ya fue entregada totalmente. No se pueden despachar más equipos.")

    current_status = quote.get("quote_status", "Borrador")
    is_irregular = current_status != "Pagada"

    if is_irregular:
        if not exception_reason:
            raise HTTPException(status_code=422, detail="IRREGULAR:Debe proporcionar un motivo para entregar sin pago registrado")
        await mark_quote_irregular(quote_id, "repair-deliver", exception_reason, regularization_date)
        await log_audit_exception(quote_id, quote.get("quote_number"), "repair-deliver", "Pagada", current_status, exception_reason, regularization_date, current_user)

    selected_serials = body.get("selected_serials", [])  # Lista de taller_equipo_id
    delivery_method = body.get("delivery_method", "personalizada")
    receiver_name = body.get("receiver_name", "")
    receiver_cedula = body.get("receiver_cedula", "")
    receiver_phone = body.get("receiver_phone", "")
    courier_name = body.get("courier_name", "")
    courier_office = body.get("courier_office", "")
    delivery_notes = body.get("notes", "")
    repair_invoice_number = body.get("invoice_number", "")
    consumed_supplies = body.get("consumed_supplies", [])  # [{item_id, quantity}]

    if not selected_serials:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un equipo para entregar")

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Obtener info del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name", "")) if client else (quote.get("client_name") or "")
    client_rif = (client.get("rif", "") if client else "")
    client_address = (client.get("address", "") if client else "")

    # Obtener los equipos seleccionados de taller_equipos
    equipos_to_deliver = await db.taller_equipos.find(
        {"taller_equipo_id": {"$in": selected_serials}, "estatus": "En reparación"},
        {"_id": 0}
    ).to_list(1000)

    if not equipos_to_deliver:
        raise HTTPException(status_code=400, detail="No se encontraron equipos válidos para entregar")

    # Calcular saldo: total en taller "En reparación" para esta cotización vs los que se entregan ahora
    total_pendientes = await db.taller_equipos.count_documents(
        {"quote_id": quote_id, "estatus": "En reparación"}
    )
    cantidad_entregando = len(equipos_to_deliver)
    is_final_delivery = (cantidad_entregando >= total_pendientes)

    # Agrupar por modelo para el PDF
    modelos_pdf = {}
    for eq in equipos_to_deliver:
        modelo = eq.get("modelo", "Sin modelo")
        if modelo not in modelos_pdf:
            modelos_pdf[modelo] = {"name": modelo, "type": "Equipo", "quantity": 0, "serials": [], "category": "Equipo"}
        modelos_pdf[modelo]["quantity"] += 1
        modelos_pdf[modelo]["serials"].append(eq.get("serial", ""))

    delivered_pdf_items = list(modelos_pdf.values())

    # Generar Nota de Entrega PDF
    hoja_ruta_url = None
    correlativo = ""
    try:
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)

        year = datetime.now(timezone.utc).strftime("%Y")
        last_ne = await db.nota_entrega_counter.find_one_and_update(
            {"year": year},
            {"$inc": {"counter": 1}},
            upsert=True,
            return_document=True,
        )
        if last_ne and "_id" in last_ne:
            del last_ne["_id"]
        ne_num = last_ne.get("counter", 1) if last_ne else 1
        correlativo = f"NE-{year}-{ne_num:04d}"

        contact_name = ""
        contact_phone = ""
        if client:
            contact1 = client.get("contact1") or {}
            if isinstance(contact1, dict) and contact1.get("name"):
                contact_name = contact1.get("name", "")
                contact_phone = contact1.get("phone", "")

        transportista = courier_name if delivery_method == "courier" else receiver_name
        guia_placa = courier_office if delivery_method == "courier" else ""

        pdf_buffer = generate_nota_entrega_pdf(
            correlativo=correlativo,
            quote_number=quote.get("quote_number", ""),
            project_number="",
            client_name=client_name,
            client_rif=client_rif,
            client_address=client_address,
            client_contact_name=contact_name,
            client_contact_phone=contact_phone,
            warehouse_name="Taller de Reparación",
            delivered_items=delivered_pdf_items,
            delivered_by=user_name,
            transportista=transportista,
            guia_placa=guia_placa,
            notes=delivery_notes,
            logo_path=logo_path,
            delivery_method=delivery_method,
            receiver_name=receiver_name,
            receiver_cedula=receiver_cedula,
            receiver_phone=receiver_phone,
            courier_name=courier_name,
            courier_office=courier_office,
            is_final_delivery=is_final_delivery,
        )
        pdf_filename = f"NotaEntrega_Reparacion_{correlativo}.pdf"
        pdf_path = UPLOADS_DIR / pdf_filename
        save_pdf_dual(pdf_path, pdf_buffer.getvalue(), pdf_filename)
        hoja_ruta_url = f"/uploads/{pdf_filename}"

        # Adjuntar a la cotización
        attachment = {
            "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
            "category": "Nota de Entrega",
            "filename": pdf_filename,
            "url": hoja_ruta_url,
            "uploaded_by": current_user.get("email", "system"),
            "uploaded_by_name": user_name,
            "uploaded_at": now_iso,
            "content_type": "application/pdf",
        }
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$push": {"attachments": attachment}}
        )

        if client:
            client_att = {**attachment, "attachment_id": f"att_{uuid.uuid4().hex[:12]}"}
            await db.clients.update_one(
                {"client_id": quote.get("client_id")},
                {"$push": {"attachments": client_att}}
            )

        logger.info(f"Nota de Entrega Reparación generada: {hoja_ruta_url}")
    except Exception as e:
        # Capturamos con stack completo y marcamos hoja_ruta_url como None para
        # que el envío de correo respete la regla "no enviar sin anexo correcto".
        logger.error(f"[Repair Delivery] Error generando Nota de Entrega Reparación: {e}")
        import traceback
        traceback.print_exc()
        hoja_ruta_url = None

    # UPDATE masivo: cambiar estatus a "Entregado" con fecha_entrega
    await db.taller_equipos.update_many(
        {"taller_equipo_id": {"$in": selected_serials}},
        {"$set": {"estatus": "Entregado", "fecha_entrega": now_iso}}
    )

    # Solo marcar la cotización como "Entregada" si es entrega final (saldo = 0)
    if is_final_delivery:
        await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
            "quote_status": "Entregada",
            "delivered_at": now_iso,
            "entrega_completa": True,
        }})
        # === TRIGGER: Archivar en histórico (estado final) ===
        try:
            from routes.quote_history import archive_quote_to_history
            await archive_quote_to_history(quote_id, "status_entregada", current_user if 'current_user' in dir() else None)
        except Exception as e:
            logger.error(f"Error archivando cotización {quote_id} al histórico: {e}")
    else:
        # Entrega parcial: mantener estado actual, registrar entrega parcial
        await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
            "last_partial_delivery_at": now_iso,
        }})

    tipo_entrega = "FINAL" if is_final_delivery else "PARCIAL"

    # --- Registrar salida de insumos consumidos en Almacén TBP ---
    supply_exit_results = []
    if consumed_supplies and len(consumed_supplies) > 0:
        # Buscar almacén TBP (Torre Banco Plaza / Pymes)
        tbp_wh = await db.warehouses.find_one(
            {"$or": [{"name": {"$regex": "Torre Banco", "$options": "i"}}, {"name": {"$regex": "TBP", "$options": "i"}}, {"name": {"$regex": "Pymes", "$options": "i"}}]},
            {"_id": 0}
        )
        tbp_warehouse_id = tbp_wh["warehouse_id"] if tbp_wh else None

        if tbp_warehouse_id:
            for supply in consumed_supplies:
                s_item_id = supply.get("item_id")
                s_quantity = supply.get("quantity", 0)
                if not s_item_id or s_quantity <= 0:
                    continue
                item = await db.hardware.find_one({"hardware_id": s_item_id}, {"_id": 0})
                if not item:
                    continue
                try:
                    movement = {
                        "movement_id": f"mov_{uuid.uuid4().hex[:12]}",
                        "warehouse_id": tbp_warehouse_id,
                        "item_id": s_item_id,
                        "item_name": item.get("name", ""),
                        "item_type": item.get("type", "General"),
                        "movement_type": "salida",
                        "quantity": s_quantity,
                        "unit_cost": item.get("price_usd", 0),
                        "serials": [],
                        "reference": f"Factura: {repair_invoice_number or 'S/N'} | Cotización: {quote.get('quote_number', '')}",
                        "client_name": client_name,
                        "notes": f"Insumo consumido en reparación. Factura: {repair_invoice_number or 'N/A'}",
                        "created_by": user_name,
                        "created_at": now_iso,
                    }
                    await db.inventory_movements.insert_one(movement)
                    movement.pop("_id", None)
                    supply_exit_results.append({"item": item.get("name"), "quantity": s_quantity, "status": "ok"})
                except Exception as e:
                    logger.error(f"Error registrando salida de insumo {s_item_id}: {e}")
                    supply_exit_results.append({"item": s_item_id, "quantity": s_quantity, "status": "error", "detail": str(e)})

    # Guardar factura en la cotización si fue proporcionada
    if repair_invoice_number:
        await db.quotes.update_one({"quote_id": quote_id}, {"$set": {"repair_delivery_invoice": repair_invoice_number}})

    # --- Notificación al CLIENTE: Entrega de Equipos Reparados ---
    # Si la Nota de Entrega NO se generó (hoja_ruta_url is None), NO enviamos
    # correo — evita correos sin anexo o que se confundan con la acción
    # previa. Se loguea explícitamente y se devuelve un flag al frontend.
    nota_entrega_b64 = None
    email_sent_repair_deliver = False
    if hoja_ruta_url:
        try:
            ne_pdf_path = UPLOADS_DIR / hoja_ruta_url.replace("/uploads/", "")
            if ne_pdf_path.exists():
                with open(ne_pdf_path, 'rb') as f:
                    nota_entrega_b64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception as _e:
            logger.error(f"[Repair Delivery] No se pudo leer Nota de Entrega: {_e}")

    if not nota_entrega_b64:
        logger.warning(
            f"[Repair Delivery] Nota de Entrega no disponible para {quote.get('quote_number')} "
            f"— NO se envía correo (evita anexo incorrecto o sin anexo)."
        )
    else:
        # --- Motor dinámico primero, con SOLO la Nota de Entrega ---
        # Si el admin configuró destinatarios para `repair-deliver` en el
        # catálogo, el motor despacha. Si no, fallback al envío legacy a
        # cliente. El motor NO inyecta ningún otro PDF (gracias a que solo
        # pasamos `delivery_note_pdf_bytes` y NO otros *_pdf_bytes).
        ne_bytes_for_engine = base64.b64decode(nota_entrega_b64)
        try:
            _engine_result_rd = await _engine_or_legacy(
                "repair-deliver", quote, current_user,
                custom_message=custom_message,
                cc_emails=[e.strip() for e in (additional_recipients or "").split(",") if e.strip() and "@" in e.strip()],
                delivery_note_pdf_bytes=ne_bytes_for_engine,
                extra_attachments=(await _resolve_manual_attachments(manual_attachment_ids)) or None,
            )
        except Exception as _e:
            logger.warning(f"[Repair Delivery] Motor dinámico falló, fallback legacy: {_e}")
            _engine_result_rd = None

        if _engine_result_rd is not None:
            email_sent_repair_deliver = True
            logger.info(f"[Repair Delivery] Motor dinámico despachó la entrega de {quote.get('quote_number')}")
        else:
            # --- Fallback legacy al cliente, solo con Nota de Entrega ---
            try:
                contacts_crm = client.get('contacts', []) if client else []
                client_email_delivery = None
                if contacts_crm:
                    client_email_delivery = contacts_crm[0].get('email')
                if not client_email_delivery:
                    contact1_d = client.get('contact1') or {} if client else {}
                    client_email_delivery = contact1_d.get('email') if isinstance(contact1_d, dict) else None
                if not client_email_delivery or client_email_delivery == 'sin@email.com':
                    client_email_delivery = f"cliente_{(client or {}).get('rif', 'unknown')}@simulado.local"

                contacto_cliente_d = client_name
                if contacts_crm:
                    contacto_cliente_d = contacts_crm[0].get('full_name') or contacts_crm[0].get('name') or client_name

                quote_sede = quote.get("sede", "PYME")
                norm_sede_d = "PYME" if quote_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if quote_sede in ("CORP", "Corp", "Corporativo") else quote_sede
                rd_template = await get_email_template(f"repair_delivery_{norm_sede_d}")
                if not rd_template:
                    rd_template = await get_email_template("repair_delivery")
                if not rd_template:
                    rd_template = {
                        "subject": "Entrega de Equipos Reparados - Nota de Entrega Nro. {nro_nota_entrega}",
                        "body_html": "<h2>Entrega de Equipos Reparados</h2><p>Estimado(a) <strong>{contacto_cliente}</strong>, se ha generado una <strong>{tipo_nota_entrega}</strong> para sus equipos.</p><p>Nota: {nro_nota_entrega} | Equipos: {cantidad_entregada} | Estatus: {estatus_entrega}</p>"
                    }

                rd_vars = {
                    "nro_cotizacion": quote.get("quote_number", ""),
                    "quote_number": quote.get("quote_number", ""),
                    "nombre_cliente": client_name,
                    "client_name": client_name,
                    "contacto_cliente": contacto_cliente_d,
                    "tipo_nota_entrega": "Entrega Final" if is_final_delivery else "Entrega Parcial",
                    "nro_nota_entrega": correlativo,
                    "cantidad_entregada": str(cantidad_entregando),
                    "estatus_entrega": "Finalizado" if is_final_delivery else "Pendiente",
                    "Nombre_Ejecutivo": user_name,
                }
                rd_subject = render_email_template(rd_template["subject"], rd_vars)
                rd_html = render_email_template(rd_template["body_html"], rd_vars)

                # ÚNICO adjunto: la Nota de Entrega recién generada.
                rd_attachments = [{"filename": f"NotaEntrega_{correlativo}.pdf", "content": nota_entrega_b64}]

                r = await send_email(
                    to=[client_email_delivery], subject=rd_subject, html=rd_html,
                    action="repair_delivery_client", quote_id=quote_id, quote_number=quote.get("quote_number"),
                    attachments=rd_attachments
                )
                email_sent_repair_deliver = bool((r or {}).get("status") in ("sent", "queued") or (r or {}).get("id"))
                logger.info(f"[Repair Delivery/legacy] Notificación al cliente: {client_email_delivery} | {r.get('status')}")
            except Exception as e:
                logger.error(f"Error enviando notificación de entrega al cliente: {e}")

    return {
        "message": f"Entrega {tipo_entrega} registrada: {len(equipos_to_deliver)} equipo(s) entregados",
        "equipos_entregados": len(equipos_to_deliver),
        "hoja_ruta_url": hoja_ruta_url,
        "is_final_delivery": is_final_delivery,
        "tipo_entrega": tipo_entrega,
        "supply_exits": supply_exit_results,
        "invoice_number": repair_invoice_number,
        "email_sent": email_sent_repair_deliver,
        "email_warning": None if email_sent_repair_deliver else "Correo no enviado: la Nota de Entrega no se pudo generar. Revise los logs.",
    }




@router.post("/quotes/{quote_id}/duplicate")
async def duplicate_quote(
    quote_id: str,
    mode: Optional[str] = "new_version",
    authorization: Optional[str] = Header(None),
):
    """Modificar cotización en 2 modos:
      - mode=new_version (default, comportamiento histórico): crea una NUEVA cotización
        con nuevo `quote_id` y `quote_number`, deja la original intacta.
      - mode=in_place: reinicia la MISMA cotización (mismo `quote_id` y `quote_number`)
        a estado Borrador, limpia attachments y timestamps de fases. Útil cuando se
        necesita preservar la secuencia de números (recuperación post-deploy, errores).
        Se registra entrada de bitácora con quién y cuándo.
    """
    current_user = await get_current_user(authorization)

    original_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not original_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    if mode == "in_place":
        previous_status = original_quote.get("quote_status")
        previous_version = original_quote.get("version", 1)
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "quote_status": "Borrador",
                "sent_to_client_at": None,
                "approved_at": None,
                "invoiced_at": None,
                "paid_at": None,
                "delivered_at": None,
                "repaired_at": None,
                "sent_to_implementation_at": None,
                "invoice_pdf_url": None,
                "quote_pdf_url": None,
                "implementation_pdf_url": None,
                "delivery_note_pdf_url": None,
                "repair_pdf_url": None,
                "invoice_number": None,
                "attachments": [],
                "modified_in_place_at": datetime.now(timezone.utc).isoformat(),
                "modified_in_place_by": current_user.get("email"),
                "modified_in_place_by_name": (
                    f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
                    or current_user.get("email", "")
                ),
            }},
        )
        await db.bitacora.insert_one({
            "action": "quote_modified_in_place",
            "quote_id": quote_id,
            "quote_number": original_quote.get("quote_number"),
            "previous_status": previous_status,
            "version": previous_version,
            "executed_by": current_user.get("email"),
            "executed_by_name": (
                f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
                or current_user.get("email", "")
            ),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
        return {
            "message": "Cotización reiniciada al estado Borrador (manteniendo número original)",
            "new_quote_id": quote_id,
            "new_quote_number": original_quote.get("quote_number"),
            "version": previous_version,
            "parent_quote_id": original_quote.get("parent_quote_id") or quote_id,
            "mode": "in_place",
        }

    # mode == "new_version" (default) — crea nueva cotización con nuevo número
    quote_sede = original_quote.get("sede", "PYME")
    new_quote_number = await generate_quote_number(quote_sede)

    original_version = original_quote.get("version", 1)
    parent_id = original_quote.get("parent_quote_id") or quote_id

    new_quote = {
        **original_quote,
        "quote_id": f"quo_{uuid.uuid4().hex[:12]}",
        "quote_number": new_quote_number,
        "quote_status": "Borrador",
        "version": original_version + 1,
        "parent_quote_id": parent_id,
        "sent_to_client_at": None,
        "approved_at": None,
        "invoiced_at": None,
        "paid_at": None,
        "delivered_at": None,
        "sent_to_implementation_at": None,
        "invoice_pdf_url": None,
        "quote_pdf_url": None,
        "invoice_number": None,
        "attachments": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.quotes.insert_one(new_quote)

    await db.bitacora.insert_one({
        "action": "quote_modified_new_version",
        "original_quote_id": quote_id,
        "original_quote_number": original_quote.get("quote_number"),
        "new_quote_id": new_quote["quote_id"],
        "new_quote_number": new_quote_number,
        "executed_by": current_user.get("email"),
        "executed_by_name": (
            f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
            or current_user.get("email", "")
        ),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "message": "Nueva versión creada exitosamente",
        "new_quote_id": new_quote["quote_id"],
        "new_quote_number": new_quote_number,
        "version": new_quote["version"],
        "parent_quote_id": parent_id,
        "mode": "new_version",
    }


# ==================== EMAIL LOG ====================

@router.get("/email-logs")
async def get_email_logs(limit: int = 50, authorization: Optional[str] = Header(None)):
    """Retorna el historial de correos enviados/simulados"""
    await get_current_user(authorization)
    logs = await db.email_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return {"email_logs": logs, "count": len(logs)}



