"""Módulo Histórico de Cotizaciones.
Snapshot inmutable de cotizaciones al alcanzar estado final o convertirse en Proyecto.
Solo lectura + descarga de PDF. Acceso: admin (Administrador del Sistema) o cargo='Director'.
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
import io
import re
import uuid
import logging

from config import db, get_current_user, UPLOADS_DIR
from models import ATTACHMENT_CATEGORIES
from services.pdf_storage import save_pdf_dual, get_pdf_from_storage

router = APIRouter()


def _can_access_history(user: dict) -> bool:
    """Acceso al Histórico: por la Matriz de Seguridad (permiso `quote_history`),
    o admin (Administrador del Sistema), o cargo='Director' (legacy)."""
    if user.get("role") == "admin":
        return True
    if (user.get("cargo") or "").strip() == "Director":
        return True
    return (user.get("permissions", {}) or {}).get("quote_history", "none") != "none"


async def archive_quote_to_history(quote_id: str, trigger: str, user: Optional[dict] = None) -> Optional[dict]:
    """Genera snapshot del quote y lo archiva. Marca el quote original con archived=True.

    trigger: 'status_entregada', 'status_enviada_imple', 'action_complete'.
    """
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        logging.warning(f"[quote_history] Quote {quote_id} no existe")
        return None

    # Evitar duplicados
    existing = await db.quote_history.find_one({"quote_id": quote_id}, {"_id": 0})
    if existing:
        logging.info(f"[quote_history] Quote {quote_id} ya archivada previamente")
        if not quote.get("archived"):
            await db.quotes.update_one({"quote_id": quote_id}, {"$set": {"archived": True, "archived_at": datetime.now(timezone.utc).isoformat()}})
        return existing

    # Resolver factura asociada (si aplica)
    invoice_number = quote.get("invoice_number") or quote.get("delivery_invoice_number")
    if not invoice_number:
        # Buscar en movimientos de inventario por referencia
        movs = await db.inventory_movements.find({"quote_id": quote_id, "movement_type": "salida"}, {"_id": 0}).to_list(10)
        for mv in movs:
            ref = mv.get("reference", "")
            if "FAC" in (ref or "").upper() or "FACTURA" in (ref or "").upper():
                invoice_number = ref
                break

    # Resolver responsable (quien creó la cotización)
    responsible = {
        "user_id": quote.get("created_by_user_id") or quote.get("created_by_id", ""),
        "name": quote.get("created_by_name") or quote.get("created_by", ""),
        "role": quote.get("created_by_role", ""),
    }

    # Carpeta de anexos
    attachments_folder = f"/uploads/quotes/{quote_id}"
    attachments_list = quote.get("attachments") or []

    now = datetime.now(timezone.utc).isoformat()
    archived_by_name = ""
    archived_by_email = ""
    if user:
        archived_by_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
        archived_by_email = user.get("email", "")

    history_doc = {
        "history_id": f"qhist_{quote_id}",
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number"),
        "quote_category": quote.get("quote_category"),
        "quote_type": quote.get("quote_type"),
        "quote_status_final": quote.get("quote_status"),
        "client_id": quote.get("client_id"),
        "client_name": quote.get("client_name"),
        "subtotal_usd": quote.get("subtotal_usd"),
        "total_usd": quote.get("total_usd"),
        "total_bs": quote.get("total_bs"),
        "exchange_rate": quote.get("exchange_rate"),
        "services": quote.get("services", []),
        "hardware": quote.get("hardware", []),
        "equipment_items": quote.get("equipment_items", []),
        "ft_equipment_items": quote.get("ft_equipment_items", []),
        "repair_models": quote.get("repair_models", []),
        "notes": quote.get("notes"),
        "invoice_number": invoice_number,
        "responsible": responsible,
        "attachments_folder": attachments_folder,
        "attachments": attachments_list,
        "archived_at": now,
        "archived_trigger": trigger,
        "archived_by_name": archived_by_name,
        "archived_by_email": archived_by_email,
        "snapshot": {k: v for k, v in quote.items() if k != "_id"},
        "created_at": quote.get("created_at"),
        "project_id": quote.get("project_id"),
    }
    await db.quote_history.insert_one(history_doc)

    # Marcar cotización original como archivada (no se borra por integridad referencial con proyectos/inventario)
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$set": {
            "archived": True,
            "archived_at": now,
            "archived_trigger": trigger,
        }}
    )
    history_doc.pop("_id", None)
    logging.info(f"[quote_history] Quote {quote_id} archivado. Trigger: {trigger}")
    return history_doc


async def check_and_archive_on_status_change(quote_id: str, new_status: str, user: Optional[dict] = None):
    """Invocado tras cada transición de estado. Archiva si se llegó al estado final de la categoría."""
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        return
    category = quote.get("quote_category", "implementation")
    final_states = {
        "implementation": "Enviada a Imple",
        "equipment": "Entregada",
        "fast_track": "Entregada",
        "repair": "Entregada",
    }
    final = final_states.get(category)
    if not final:
        return
    if new_status == final:
        trigger_map = {
            "Enviada a Imple": "status_enviada_imple",
            "Entregada": "status_entregada",
        }
        await archive_quote_to_history(quote_id, trigger_map.get(new_status, "status_final"), user)


# ==================== ENDPOINTS ====================

@router.get("/quote-history")
async def list_quote_history(
    search: Optional[str] = None,
    quote_category: Optional[str] = None,
    client_id: Optional[str] = None,
    invoice_number: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """Lista cotizaciones archivadas con filtros. Restringido."""
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")

    query = {}
    if quote_category:
        query["quote_category"] = quote_category
    if client_id:
        query["client_id"] = client_id
    if invoice_number:
        query["invoice_number"] = {"$regex": re.escape(invoice_number), "$options": "i"}
    if search:
        # Escapar caracteres especiales de regex para que la búsqueda sea una
        # coincidencia literal de substring (estilo LIKE %texto%). Sin esto, nombres
        # de cliente con paréntesis u otros metacaracteres (p.ej. "..., C.A.)")
        # producían una regex inválida y un error 500.
        safe = re.escape(search.strip())
        query["$or"] = [
            {"quote_number": {"$regex": safe, "$options": "i"}},
            {"client_name": {"$regex": safe, "$options": "i"}},
            {"invoice_number": {"$regex": safe, "$options": "i"}},
        ]
    if from_date or to_date:
        date_q = {}
        if from_date:
            date_q["$gte"] = from_date
        if to_date:
            date_q["$lte"] = to_date
        query["archived_at"] = date_q

    cursor = db.quote_history.find(query, {"_id": 0, "snapshot": 0}).sort("archived_at", -1)
    docs = await cursor.to_list(1000)
    return docs


@router.get("/quote-history/{history_id}")
async def get_quote_history(history_id: str, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")
    doc = await db.quote_history.find_one({"history_id": history_id}, {"_id": 0})
    if not doc:
        # Fallback: lookup por quote_id
        doc = await db.quote_history.find_one({"quote_id": history_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return doc


@router.delete("/quote-history/{history_id}")
async def delete_quote_history(history_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un registro del Histórico — exclusivo para administradores del sistema.

    Operación irreversible. Está pensada para depurar registros corruptos o
    de prueba. NO restaura la cotización al flujo activo, solo borra del
    repositorio de auditoría.
    """
    current_user = await get_current_user(authorization)
    if (current_user.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden depurar el histórico")

    # Buscar por history_id o quote_id
    doc = await db.quote_history.find_one({"history_id": history_id}, {"_id": 0, "quote_number": 1, "client_name": 1})
    if not doc:
        doc = await db.quote_history.find_one({"quote_id": history_id}, {"_id": 0, "quote_number": 1, "client_name": 1})
        if not doc:
            raise HTTPException(status_code=404, detail="Registro no encontrado")
        result = await db.quote_history.delete_one({"quote_id": history_id})
    else:
        result = await db.quote_history.delete_one({"history_id": history_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    return {
        "ok": True,
        "message": f"Registro {doc.get('quote_number','')} ({doc.get('client_name','')}) eliminado del histórico",
        "deleted_count": result.deleted_count,
    }


@router.get("/quote-history/{history_id}/pdf")
async def download_quote_history_pdf(history_id: str, authorization: Optional[str] = Header(None)):
    """Descarga el PDF original. Usa el generador correcto según la categoría de la cotización."""
    from fastapi.responses import Response, FileResponse
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")
    doc = await db.quote_history.find_one({"history_id": history_id}, {"_id": 0})
    if not doc:
        doc = await db.quote_history.find_one({"quote_id": history_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    category = doc.get("quote_category", "implementation")
    quote_id = doc["quote_id"]
    quote_number = doc.get("quote_number", quote_id)

    # Dispatch: equipos/reparaciones → regenerar + leer del disco (endpoint devuelve JSON con pdf_url)
    if category in ("equipment", "repair"):
        from routes.quotes import regenerate_equipment_pdf as _gen_eq_pdf
        result = await _gen_eq_pdf(quote_id, data={}, authorization=authorization)
        # result es dict con pdf_url relativa
        rel_url = (result or {}).get("pdf_url") if isinstance(result, dict) else None
        if not rel_url:
            raise HTTPException(status_code=500, detail="No se pudo generar el PDF")
        file_path = f"/app/backend{rel_url}" if rel_url.startswith("/") else f"/app/backend/{rel_url}"
        import os
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Archivo PDF no encontrado: {rel_url}")
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=f"historico_{quote_number}.pdf"
        )

    # implementation / fast_track → endpoint devuelve binary Response
    from routes.quotes import generate_quote_pdf as _gen_pdf
    return await _gen_pdf(quote_id, authorization=authorization)


@router.post("/quote-history/migrate-legacy")
async def migrate_legacy_quotes(authorization: Optional[str] = Header(None)):
    """Migración única: archiva cotizaciones existentes con estatus final y aún no archivadas."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede ejecutar migración")

    final_query = {
        "archived": {"$ne": True},
        "$or": [
            {"quote_status": "Enviada a Imple"},
            {"quote_status": "Entregada"},
        ],
    }
    cursor = db.quotes.find(final_query, {"_id": 0, "quote_id": 1, "quote_status": 1, "quote_category": 1})
    count = 0
    skipped = 0
    async for q in cursor:
        status = q.get("quote_status")
        trigger = "status_entregada" if status == "Entregada" else "status_enviada_imple"
        result = await archive_quote_to_history(q["quote_id"], trigger, current_user)
        if result:
            count += 1
        else:
            skipped += 1
    return {"migrated": count, "skipped": skipped}


# =====================================================================
# ANEXOS DEL HISTÓRICO — gestión documental para subsano de auditoría.
# Solo Administradores del Sistema pueden subir / eliminar anexos. Director
# y Admin pueden visualizar/descargar.
# =====================================================================

def _is_system_admin(user: dict) -> bool:
    return (user.get("role") or "").lower() == "admin"


@router.get("/quote-history/{history_id}/attachments")
async def list_history_attachments(history_id: str, authorization: Optional[str] = Header(None)):
    """Lista anexos del registro histórico. Lectura: Director o Admin."""
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido a Director o Administrador del Sistema")
    doc = await db.quote_history.find_one(
        {"$or": [{"history_id": history_id}, {"quote_id": history_id}]},
        {"_id": 0, "history_id": 1, "quote_id": 1, "quote_number": 1, "attachments": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Registro histórico no encontrado")
    return {
        "history_id": doc.get("history_id"),
        "quote_id": doc.get("quote_id"),
        "quote_number": doc.get("quote_number"),
        "attachments": doc.get("attachments", []) or [],
    }


@router.post("/quote-history/{history_id}/attachments")
async def upload_history_attachment(
    history_id: str,
    file: UploadFile = File(...),
    category: str = Form(...),
    authorization: Optional[str] = Header(None),
):
    """Sube un anexo al registro del histórico. Solo administrador del sistema."""
    current_user = await get_current_user(authorization)
    if not _is_system_admin(current_user):
        raise HTTPException(status_code=403, detail="Solo administradores pueden subir anexos al histórico")

    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoría inválida. Opciones: {', '.join(ATTACHMENT_CATEGORIES)}")

    doc = await db.quote_history.find_one(
        {"$or": [{"history_id": history_id}, {"quote_id": history_id}]},
        {"_id": 0, "history_id": 1, "quote_id": 1, "quote_number": 1, "attachments": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Registro histórico no encontrado")

    # Tamaño máx. 10 MB
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo no debe superar los 10MB")

    quote_id = doc.get("quote_id")
    quote_number = doc.get("quote_number") or quote_id

    attachment_id = f"hatt_{uuid.uuid4().hex[:12]}"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    cat_short = (
        {
            "Cotización": "Cotizacion",
            "Orden de Compra": "OrdenCompra",
            "Soporte de Aprobación": "Aprobacion",
            "Factura": "Factura",
            "Pagos": "Pago",
            "Nota de Entrega": "NotaEntrega",
            "Otros": "Otros",
        }
        .get(category, category.replace(" ", ""))
    )
    existing_in_cat = [a for a in (doc.get("attachments") or []) if a.get("category") == category]
    suffix = f"_{len(existing_in_cat) + 1}" if existing_in_cat else ""
    display_filename = f"HIST_{quote_number}_{cat_short}{suffix}{file_ext}"
    safe_filename = f"{attachment_id}{file_ext}"

    # Storage path bajo "attachments/history/{quote_id}/..."
    rel_dir = f"attachments/history/{quote_id}"
    local_dir = UPLOADS_DIR / "attachments" / "history" / quote_id
    local_dir.mkdir(parents=True, exist_ok=True)
    file_path = local_dir / safe_filename
    relative_key = f"{rel_dir}/{safe_filename}"

    # Dual write: filesystem + Object Storage
    save_pdf_dual(file_path, content, relative_key)

    # Categorías que sí subsanan irregularidades — alineado con SUBSANA_CATEGORY_MAP
    # de sales_reports.py. 'Otros' es documentación miscelánea y NO normaliza fases.
    # Nota: 'Soporte de Aprobación' fue removido del whitelist (consistencia con
    # módulo de Cotizaciones activas). El mapeo backend lo conserva para anexos
    # legacy ya cargados previamente.
    SUBSANA_CATEGORIES = {
        "Cotización", "Orden de Compra",
        "Factura", "Pagos", "Nota de Entrega",
    }
    attachment = {
        "attachment_id": attachment_id,
        "category": category,
        "filename": display_filename,
        "url": f"/uploads/{relative_key}",
        "uploaded_by": current_user.get("email", "unknown"),
        "uploaded_by_name": (
            f"{current_user.get('first_name','')} {current_user.get('last_name','')}".strip()
            or current_user.get("email", "unknown")
        ),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "is_subsana": category in SUBSANA_CATEGORIES,
    }

    await db.quote_history.update_one(
        {"history_id": doc.get("history_id")},
        {"$push": {"attachments": attachment}},
    )
    return {"message": "Anexo subido exitosamente", "attachment": attachment}


@router.delete("/quote-history/{history_id}/attachments/{attachment_id}")
async def delete_history_attachment(history_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un anexo del histórico. Solo administrador del sistema."""
    current_user = await get_current_user(authorization)
    if not _is_system_admin(current_user):
        raise HTTPException(status_code=403, detail="Solo administradores pueden depurar anexos del histórico")

    doc = await db.quote_history.find_one(
        {"$or": [{"history_id": history_id}, {"quote_id": history_id}]},
        {"_id": 0, "history_id": 1, "attachments": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Registro histórico no encontrado")
    attachment = next((a for a in (doc.get("attachments") or []) if a.get("attachment_id") == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")

    # Limpieza opcional del archivo físico (storage falla silenciosamente).
    try:
        rel = (attachment.get("url") or "").replace("/uploads/", "")
        local_path = UPLOADS_DIR / rel
        if local_path.exists():
            local_path.unlink()
    except Exception:
        logging.exception("No se pudo eliminar archivo físico del anexo histórico")

    await db.quote_history.update_one(
        {"history_id": doc.get("history_id")},
        {"$pull": {"attachments": {"attachment_id": attachment_id}}},
    )
    return {"message": "Anexo eliminado exitosamente"}


@router.get("/quote-history/{history_id}/attachments/{attachment_id}/download")
async def download_history_attachment(history_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Descarga un anexo histórico. Lectura: Director o Admin."""
    current_user = await get_current_user(authorization)
    if not _can_access_history(current_user):
        raise HTTPException(status_code=403, detail="Acceso restringido")
    doc = await db.quote_history.find_one(
        {"$or": [{"history_id": history_id}, {"quote_id": history_id}]},
        {"_id": 0, "attachments": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    attachment = next((a for a in (doc.get("attachments") or []) if a.get("attachment_id") == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")

    rel = (attachment.get("url") or "").replace("/uploads/", "")
    filename = attachment.get("filename", attachment_id)
    declared_ctype = attachment.get("content_type", "application/octet-stream")

    # 1) FS local primero — instantáneo. 2) Object Storage como fallback.
    local_path = UPLOADS_DIR / rel
    if local_path.exists():
        return FileResponse(
            path=str(local_path),
            filename=filename,
            media_type=declared_ctype,
        )

    obj = get_pdf_from_storage(rel)
    if not obj:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    content, ctype = obj
    return StreamingResponse(
        io.BytesIO(content),
        media_type=ctype or declared_ctype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
