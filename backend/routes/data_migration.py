"""
Data Migration: Export/Import de catálogos maestros entre ambientes (Preview ↔ Deploy).
Solo administradores. Formato JSON consistente entre export e import.

Módulos soportados:
  - banks                 → collection 'banks'                 (key: bank_id)
  - payment-methods       → collection 'services'              (key: service_id)
  - hardware              → collection 'hardware'              (key: hardware_id)
  - commercial-categories → collection 'commercial_categories' (key: category_id)
  - quotes-bundle         → multi-collection: 'quotes' + 'quote_history' + 'projects'
                            con anexos en ZIP separado.
"""
import io
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from starlette.background import BackgroundTask

from config import db, get_current_user, UPLOADS_DIR
from services.pdf_storage import get_pdf_from_storage, save_pdf_dual

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------- Mapeo de módulos ----------
MODULES = {
    "banks": {
        "collection": "banks",
        "key": "bank_id",
        "label": "Bancos",
    },
    "payment-methods": {
        "collection": "services",
        "key": "service_id",
        "label": "Medios de Pago",
    },
    "hardware": {
        "collection": "hardware",
        "key": "hardware_id",
        "label": "Bienes y Servicios",
    },
    "commercial-categories": {
        "collection": "commercial_categories",
        "key": "category_id",
        "label": "Categorías Comerciales",
    },
    "users": {
        "collection": "users",
        "key": "user_id",
        "label": "Usuarios",
    },
    "inventory-movements": {
        "collection": "inventory_movements",
        "key": "movement_id",
        "label": "Movimientos de Inventario",
    },
    "clients": {
        "collection": "clients",
        "key": "client_id",
        "label": "Clientes",
    },
    "quote-history": {
        "collection": "quote_history",
        "key": "history_id",
        "label": "Histórico de Cotizaciones",
    },
    "taller-equipos": {
        "collection": "taller_equipos",
        "key": "taller_equipo_id",
        "label": "Equipos en Taller",
    },
}

# Campos que NO deben sobreescribirse al importar usuarios (sesión / bloqueos transitorios)
USER_SANITIZE_FIELDS = ("failed_attempts", "locked_until", "session_token", "last_login_ip", "last_login_at")


def _get_module_or_404(module: str):
    if module not in MODULES:
        raise HTTPException(status_code=404, detail=f"Módulo '{module}' no soportado")
    return MODULES[module]


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar migración de datos")
    return user


# ==================== EXPORT ====================

@router.get("/admin/migration/{module}/export")
async def export_module(module: str, authorization: Optional[str] = Header(None)):
    """Exporta TODOS los documentos del módulo en formato JSON estandarizado.
    El archivo resultante puede ser usado tal cual en /import-preview e /import-apply."""
    user = await _require_admin(authorization)
    cfg = _get_module_or_404(module)

    docs = await db[cfg["collection"]].find({}, {"_id": 0}).to_list(None)

    payload = {
        "schema_version": 1,
        "module": module,
        "collection": cfg["collection"],
        "key": cfg["key"],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": user.get("email"),
        "exported_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "count": len(docs),
        "documents": docs,
    }

    # Bitácora
    await db.bitacora.insert_one({
        "action": "data_migration_export",
        "module": module,
        "collection": cfg["collection"],
        "count": len(docs),
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    filename = f"{module}_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==================== IMPORT: PREVIEW ====================

async def _read_payload(file: UploadFile) -> dict:
    try:
        raw = await file.read()
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Archivo JSON inválido: {e}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Archivo no es UTF-8 válido")


def _validate_payload(payload: dict, cfg: dict, module: str):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Estructura JSON inválida (se esperaba un objeto)")
    if payload.get("module") != module:
        raise HTTPException(
            status_code=400,
            detail=f"El archivo es del módulo '{payload.get('module')}', pero se está importando en '{module}'.",
        )
    if payload.get("collection") != cfg["collection"]:
        raise HTTPException(status_code=400, detail="La colección del archivo no coincide con el módulo destino.")
    docs = payload.get("documents")
    if not isinstance(docs, list):
        raise HTTPException(status_code=400, detail="Campo 'documents' faltante o no es lista")
    return docs


@router.post("/admin/migration/{module}/import-preview")
async def import_preview(
    module: str,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Lee el archivo y devuelve un resumen de qué pasará si se aplica el import.
    NO modifica datos. Devuelve cuántos se crearán y cuántos se actualizarán."""
    await _require_admin(authorization)
    cfg = _get_module_or_404(module)
    payload = await _read_payload(file)
    docs = _validate_payload(payload, cfg, module)

    key = cfg["key"]
    incoming_keys = []
    invalid = 0
    duplicates_in_file = []
    seen = set()
    for d in docs:
        if not isinstance(d, dict) or not d.get(key):
            invalid += 1
            continue
        kv = d[key]
        if kv in seen:
            duplicates_in_file.append(kv)
        else:
            seen.add(kv)
            incoming_keys.append(kv)

    existing = await db[cfg["collection"]].find(
        {key: {"$in": incoming_keys}}, {"_id": 0, key: 1}
    ).to_list(None)
    existing_keys = {e[key] for e in existing}

    to_update = [k for k in incoming_keys if k in existing_keys]
    to_create = [k for k in incoming_keys if k not in existing_keys]

    return {
        "module": module,
        "collection": cfg["collection"],
        "exported_at": payload.get("exported_at"),
        "exported_by": payload.get("exported_by"),
        "total_in_file": len(docs),
        "valid_count": len(incoming_keys),
        "invalid_count": invalid,
        "duplicates_in_file": duplicates_in_file,
        "to_create_count": len(to_create),
        "to_update_count": len(to_update),
        "to_create_sample": to_create[:5],
        "to_update_sample": to_update[:5],
    }


# ==================== IMPORT: APPLY ====================

@router.post("/admin/migration/{module}/import-apply")
async def import_apply(
    module: str,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Aplica el import: hace upsert de cada documento por su id natural.
    Conserva created_at original al actualizar; refresca updated_at."""
    user = await _require_admin(authorization)
    cfg = _get_module_or_404(module)
    payload = await _read_payload(file)
    docs = _validate_payload(payload, cfg, module)

    key = cfg["key"]
    collection = db[cfg["collection"]]
    now_iso = datetime.now(timezone.utc).isoformat()

    inserted = 0
    updated = 0
    skipped = 0
    errors = []

    # Pre-cargar existentes para distinguir create vs update
    incoming_keys = [d[key] for d in docs if isinstance(d, dict) and d.get(key)]
    existing_docs = await collection.find(
        {key: {"$in": incoming_keys}}, {"_id": 0}
    ).to_list(None)
    existing_map = {e[key]: e for e in existing_docs}

    for d in docs:
        if not isinstance(d, dict) or not d.get(key):
            skipped += 1
            errors.append({"reason": "missing_key", "key_field": key})
            continue
        try:
            doc = {k: v for k, v in d.items() if k != "_id"}
            # Sanitización especial para 'users': resetear bloqueos/sesiones (no propagarlos del origen)
            if module == "users":
                for f in USER_SANITIZE_FIELDS:
                    if f == "failed_attempts":
                        doc[f] = 0
                    elif f == "locked_until":
                        doc[f] = None
                    else:
                        doc.pop(f, None)
            kv = doc[key]
            if kv in existing_map:
                # Conservar created_at original si existe
                original_created = existing_map[kv].get("created_at")
                if original_created and not doc.get("created_at"):
                    doc["created_at"] = original_created
                doc["updated_at"] = now_iso
                doc["updated_by"] = user.get("email")
                await collection.update_one({key: kv}, {"$set": doc})
                updated += 1
            else:
                if not doc.get("created_at"):
                    doc["created_at"] = now_iso
                doc["imported_at"] = now_iso
                doc["imported_by"] = user.get("email")
                await collection.insert_one(doc)
                inserted += 1
        except Exception as e:
            skipped += 1
            errors.append({"key": d.get(key), "error": str(e)})

    # Bitácora
    await db.bitacora.insert_one({
        "action": "data_migration_import",
        "module": module,
        "collection": cfg["collection"],
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "source_exported_at": payload.get("exported_at"),
        "source_exported_by": payload.get("exported_by"),
        "executed_by": user.get("email"),
        "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "executed_at": now_iso,
    })

    return {
        "module": module,
        "collection": cfg["collection"],
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "message": f"Migración completada: {inserted} creado(s), {updated} actualizado(s), {skipped} omitido(s).",
    }


# =====================================================================
# QUOTES BUNDLE — Cotizaciones + Histórico + Proyectos + Anexos
# =====================================================================
# Diferente al patrón simple de catálogos: este "módulo virtual" abarca
# múltiples colecciones. Los anexos (binarios) viajan en un ZIP aparte
# para evitar inflar el JSON con base64.
#
# Endpoints:
#   GET  /admin/quotes-bundle-migration/export-data         → JSON
#   GET  /admin/quotes-bundle-migration/export-attachments  → ZIP de archivos
#   POST /admin/quotes-bundle-migration/import-preview      → resumen
#   POST /admin/quotes-bundle-migration/import-data         → upsert masivo
#   POST /admin/quotes-bundle-migration/import-attachments  → restaura archivos al storage
# =====================================================================

QUOTES_BUNDLE_COLLECTIONS = [
    {"collection": "quotes",        "key": "quote_id",   "label": "Cotizaciones"},
    {"collection": "quote_history", "key": "history_id", "label": "Cotizaciones Históricas"},
    {"collection": "projects",      "key": "project_id", "label": "Proyectos"},
]


def _collect_attachment_paths(docs: list) -> set:
    """Extrae el set de paths relativos (debajo de /uploads/) que deben
    acompañar al export. Incluye anexos del array `attachments` y los PDFs
    principales referenciados por `quote_pdf_url` / `invoice_pdf_url` / etc.
    """
    paths = set()
    for d in docs:
        if not isinstance(d, dict):
            continue
        for att in (d.get("attachments") or []):
            url = (att.get("url") or "").strip()
            if url.startswith("/uploads/"):
                paths.add(url[len("/uploads/"):])
        for url_field in ("quote_pdf_url", "invoice_pdf_url", "delivery_note_pdf_url",
                          "repair_pdf_url", "implementation_pdf_url"):
            url = (d.get(url_field) or "").strip()
            if url.startswith("/uploads/"):
                paths.add(url[len("/uploads/"):])
        snap = d.get("snapshot") or {}
        for att in (snap.get("attachments") or []):
            url = (att.get("url") or "").strip()
            if url.startswith("/uploads/"):
                paths.add(url[len("/uploads/"):])
    return paths


def _read_file_for_export(rel_path: str) -> Optional[bytes]:
    """1° Object Storage, fallback a filesystem."""
    obj = get_pdf_from_storage(rel_path)
    if obj:
        return obj[0]
    local = UPLOADS_DIR / rel_path
    if local.exists() and local.is_file():
        try:
            return local.read_bytes()
        except Exception as e:
            logger.warning(f"[quotes-bundle] read fail {rel_path}: {e}")
    return None


@router.get("/admin/quotes-bundle-migration/export-data")
async def quotes_bundle_export_data(authorization: Optional[str] = Header(None)):
    """Descarga JSON con todas las cotizaciones, históricos y proyectos.
    NO incluye binarios — los anexos se exportan por separado vía
    /export-attachments."""
    user = await _require_admin(authorization)

    payload_collections = {}
    counts = {}
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        docs = await db[cfg["collection"]].find({}, {"_id": 0}).to_list(None)
        payload_collections[cfg["collection"]] = docs
        counts[cfg["collection"]] = len(docs)

    payload = {
        "schema_version": 1,
        "module": "quotes-bundle",
        "collections": payload_collections,
        "counts": counts,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": user.get("email"),
        "exported_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
    }

    await db.bitacora.insert_one({
        "action": "quotes_bundle_export_data",
        "counts": counts,
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    filename = f"quotes_bundle_data_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/quotes-bundle-migration/export-attachments")
async def quotes_bundle_export_attachments(authorization: Optional[str] = Header(None)):
    """ZIP con TODOS los anexos y PDFs referenciados por las cotizaciones,
    históricos y proyectos. Estructura: manifest.json + <rel_path>... ."""
    user = await _require_admin(authorization)
    all_docs = []
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        async for d in db[cfg["collection"]].find({}, {
            "_id": 0,
            "attachments": 1,
            "snapshot": 1,
            "quote_pdf_url": 1, "invoice_pdf_url": 1,
            "delivery_note_pdf_url": 1, "repair_pdf_url": 1,
            "implementation_pdf_url": 1,
            cfg["key"]: 1,
        }):
            all_docs.append(d)

    paths = _collect_attachment_paths(all_docs)

    buf = io.BytesIO()
    included, missing = [], []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(paths):
            data = _read_file_for_export(rel)
            if data is None:
                missing.append(rel)
                continue
            zf.writestr(rel, data)
            included.append({"path": rel, "size": len(data)})

        manifest = {
            "schema_version": 1,
            "module": "quotes-bundle-attachments",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": user.get("email"),
            "exported_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
            "files_included": included,
            "files_missing": missing,
            "total_included": len(included),
            "total_missing": len(missing),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    buf.seek(0)
    payload = buf.getvalue()
    buf.close()

    await db.bitacora.insert_one({
        "action": "quotes_bundle_export_attachments",
        "files_included": len(included),
        "files_missing": len(missing),
        "size_bytes": len(payload),
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    filename = f"quotes_bundle_attachments_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    # Generador en chunks de 64 KB. Resuelve corrupción cuando el proxy/ingress
    # trunca respuestas si se itera el BytesIO por líneas (binarios con \n
    # pueden confundir a NGINX/Cloudflare). Además fijamos Content-Length para
    # que el cliente detecte downloads incompletos.
    def _iter_chunks(data: bytes, chunk: int = 64 * 1024):
        for i in range(0, len(data), chunk):
            yield data[i:i + chunk]

    return StreamingResponse(
        _iter_chunks(payload),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload)),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# CONTINGENCIA — Export Attachments via temp file streaming (low-memory).
# ---------------------------------------------------------------------------
# Usar cuando el endpoint `/export-attachments` (en memoria) falle por:
#   - Timeout del proxy/ingress (504/Gateway).
#   - "body stream already read" tras transferencia parcial.
#   - Datasets grandes que saturan la memoria del backend.
# El ZIP se escribe a un archivo temporal en disco y se sirve con FileResponse,
# liberando memoria del proceso. Tras servirlo se elimina automáticamente.
# ---------------------------------------------------------------------------
@router.get("/admin/quotes-bundle-migration/export-attachments-streamed")
async def quotes_bundle_export_attachments_streamed(
    authorization: Optional[str] = Header(None),
):
    user = await _require_admin(authorization)

    all_docs = []
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        async for d in db[cfg["collection"]].find({}, {
            "_id": 0,
            "attachments": 1,
            "snapshot": 1,
            "quote_pdf_url": 1, "invoice_pdf_url": 1,
            "delivery_note_pdf_url": 1, "repair_pdf_url": 1,
            "implementation_pdf_url": 1,
            cfg["key"]: 1,
        }):
            all_docs.append(d)

    paths = _collect_attachment_paths(all_docs)

    # Crear archivo temporal y escribir el ZIP directamente — no se carga el
    # contenido completo en memoria. Cada archivo se vuelca uno a uno.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="quotes_bundle_")
    os.close(tmp_fd)

    included, missing = [], []
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in sorted(paths):
                data = _read_file_for_export(rel)
                if data is None:
                    missing.append(rel)
                    continue
                zf.writestr(rel, data)
                included.append({"path": rel, "size": len(data)})

            manifest = {
                "schema_version": 1,
                "module": "quotes-bundle-attachments",
                "mode": "streamed",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exported_by": user.get("email"),
                "exported_by_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                "files_included": included,
                "files_missing": missing,
                "total_included": len(included),
                "total_missing": len(missing),
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        size_bytes = os.path.getsize(tmp_path)

        await db.bitacora.insert_one({
            "action": "quotes_bundle_export_attachments_streamed",
            "files_included": len(included),
            "files_missing": len(missing),
            "size_bytes": size_bytes,
            "executed_by": user.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

        filename = f"quotes_bundle_attachments_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"

        # FileResponse maneja Range, Content-Length y stream de disco eficientemente.
        # BackgroundTask elimina el archivo temporal después de enviarlo.
        def _cleanup(p):
            try:
                os.unlink(p)
            except Exception:  # pragma: no cover
                pass

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=filename,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "X-Files-Included": str(len(included)),
                "X-Files-Missing": str(len(missing)),
            },
            background=BackgroundTask(_cleanup, tmp_path),
        )
    except Exception:
        # Si algo falla durante la creación del zip, eliminar el temp y propagar.
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _validate_bundle_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Estructura JSON inválida")
    if payload.get("module") != "quotes-bundle":
        raise HTTPException(
            status_code=400,
            detail=f"El archivo es del módulo '{payload.get('module')}'. Esperado: 'quotes-bundle'.",
        )
    cols = payload.get("collections")
    if not isinstance(cols, dict):
        raise HTTPException(status_code=400, detail="Campo 'collections' faltante o inválido")
    return cols


# ---------------------------------------------------------------------------
# CONTINGENCIA · PAGINACIÓN — Export por colección + página.
# ---------------------------------------------------------------------------
# Diseñado para evitar el 504 Gateway Timeout en producción cuando el bundle
# completo no cabe en una sola request. El cliente itera por (collection, page)
# y arma el JSON final en memoria local. Cada request descarga máximo `limit`
# documentos y suele responder en <2s incluso con datasets grandes.
# Compatible 100% con el endpoint de import-preview existente.
# ---------------------------------------------------------------------------
_VALID_BUNDLE_COLLECTIONS = {cfg["collection"] for cfg in QUOTES_BUNDLE_COLLECTIONS}


@router.get("/admin/quotes-bundle-migration/page")
async def quotes_bundle_export_page(
    collection: str,
    skip: int = 0,
    limit: int = 100,
    authorization: Optional[str] = Header(None),
):
    """Descarga una página de documentos de UNA colección del bundle.

    Query params:
      - collection: una de {quotes, quote_history, projects}.
      - skip: offset.
      - limit: tamaño de página (1..500). Recomendado 100.
    """
    await _require_admin(authorization)
    if collection not in _VALID_BUNDLE_COLLECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Colección '{collection}' no permitida. Válidas: {sorted(_VALID_BUNDLE_COLLECTIONS)}",
        )
    if limit <= 0 or limit > 500:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 500")
    if skip < 0:
        raise HTTPException(status_code=400, detail="skip debe ser >= 0")

    total = await db[collection].count_documents({})
    docs = await db[collection].find({}, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    return JSONResponse({
        "collection": collection,
        "skip": skip,
        "limit": limit,
        "total": total,
        "returned": len(docs),
        "has_more": (skip + len(docs)) < total,
        "docs": json.loads(json.dumps(docs, default=str)),
    })


@router.get("/admin/quotes-bundle-migration/counts")
async def quotes_bundle_counts(authorization: Optional[str] = Header(None)):
    """Devuelve conteos por colección del bundle. Útil para planificar paginación."""
    await _require_admin(authorization)
    counts = {}
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        counts[cfg["collection"]] = await db[cfg["collection"]].count_documents({})
    return {"counts": counts, "collections": sorted(_VALID_BUNDLE_COLLECTIONS)}


# ---------------------------------------------------------------------------
# CONTINGENCIA · PAGINACIÓN ANEXOS — Lista + descarga individual de archivos.
# ---------------------------------------------------------------------------
# El cliente itera la lista de paths y descarga cada uno con un endpoint binario
# minimalista. Luego empaqueta todo en un ZIP en el browser (con JSZip).
# Inmune al 504 porque cada archivo viaja en una request <2s.
# ---------------------------------------------------------------------------
@router.get("/admin/quotes-bundle-migration/attachments-list")
async def quotes_bundle_attachments_list(authorization: Optional[str] = Header(None)):
    """Lista todos los rel_paths del bundle, con tamaño en bytes cuando se puede
    determinar (None si está en object storage remoto y no se descargó aún)."""
    await _require_admin(authorization)
    all_docs = []
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        async for d in db[cfg["collection"]].find({}, {
            "_id": 0,
            "attachments": 1, "snapshot": 1,
            "quote_pdf_url": 1, "invoice_pdf_url": 1,
            "delivery_note_pdf_url": 1, "repair_pdf_url": 1,
            "implementation_pdf_url": 1,
            cfg["key"]: 1,
        }):
            all_docs.append(d)
    paths = sorted(_collect_attachment_paths(all_docs))
    items = []
    for rel in paths:
        size = None
        try:
            local = UPLOADS_DIR / rel
            if local.exists():
                size = local.stat().st_size
        except Exception:
            size = None
        items.append({"path": rel, "size": size})
    return {"total": len(items), "items": items}


@router.get("/admin/quotes-bundle-migration/attachment")
async def quotes_bundle_attachment_download(
    path: str,
    authorization: Optional[str] = Header(None),
):
    """Descarga UN anexo del bundle por su rel_path (relativo a /uploads/).

    Protege contra path traversal: el path debe ser relativo y resolverse
    DENTRO de UPLOADS_DIR. Si no está en disco local, se intenta object storage.
    """
    await _require_admin(authorization)
    if not path or path.startswith("/") or ".." in path.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail="Path inválido")

    data = _read_file_for_export(path)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {path}")

    # Determinar nombre de archivo y media type
    filename = path.rsplit("/", 1)[-1] or "attachment.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    media_map = {
        "pdf": "application/pdf",
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "gif": "image/gif", "webp": "image/webp",
        "txt": "text/plain", "json": "application/json",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = media_map.get(ext, "application/octet-stream")

    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
            "X-Original-Path": path,
            "Cache-Control": "no-store",
        },
    )


# ---------------------------------------------------------------------------
# CONTINGENCIA — Export JSON de datos via temp file streaming (low-memory).
# ---------------------------------------------------------------------------
# Variante de `/export-data` que escribe el JSON a disco con cursor MongoDB
# en streaming (sin cargar todas las colecciones en memoria). Usar cuando el
# endpoint estándar falle por timeouts o memoria saturada con datasets grandes.
# ---------------------------------------------------------------------------
@router.get("/admin/quotes-bundle-migration/export-data-streamed")
async def quotes_bundle_export_data_streamed(
    authorization: Optional[str] = Header(None),
):
    user = await _require_admin(authorization)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="quotes_bundle_data_")
    os.close(tmp_fd)

    counts = {}
    try:
        # Escribir JSON manualmente con un cursor por colección. Esto evita
        # mantener todos los documentos en memoria simultáneamente.
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("{\n")
            f.write('  "schema_version": 1,\n')
            f.write('  "module": "quotes-bundle",\n')
            f.write('  "mode": "streamed",\n')
            f.write('  "exported_at": ' + json.dumps(datetime.now(timezone.utc).isoformat()) + ",\n")
            f.write('  "exported_by": ' + json.dumps(user.get("email", "")) + ",\n")
            exporter_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            f.write('  "exported_by_name": ' + json.dumps(exporter_name) + ",\n")
            f.write('  "collections": {\n')

            for col_idx, cfg in enumerate(QUOTES_BUNDLE_COLLECTIONS):
                cname = cfg["collection"]
                f.write(f'    "{cname}": [')
                count = 0
                first = True
                async for doc in db[cname].find({}, {"_id": 0}):
                    if not first:
                        f.write(",")
                    f.write("\n      ")
                    f.write(json.dumps(doc, ensure_ascii=False, default=str))
                    first = False
                    count += 1
                f.write("\n    ]")
                if col_idx < len(QUOTES_BUNDLE_COLLECTIONS) - 1:
                    f.write(",")
                f.write("\n")
                counts[cname] = count

            f.write('  },\n')
            f.write('  "counts": ' + json.dumps(counts) + "\n")
            f.write("}\n")

        await db.bitacora.insert_one({
            "action": "quotes_bundle_export_data_streamed",
            "counts": counts,
            "size_bytes": os.path.getsize(tmp_path),
            "executed_by": user.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

        filename = f"quotes_bundle_data_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

        def _cleanup(p):
            try:
                os.unlink(p)
            except Exception:  # pragma: no cover
                pass

        return FileResponse(
            tmp_path,
            media_type="application/json",
            filename=filename,
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
                "X-Counts-Quotes": str(counts.get("quotes", 0)),
                "X-Counts-History": str(counts.get("quote_history", 0)),
                "X-Counts-Projects": str(counts.get("projects", 0)),
            },
            background=BackgroundTask(_cleanup, tmp_path),
        )
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


@router.post("/admin/quotes-bundle-migration/import-preview")
async def quotes_bundle_import_preview(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Lee el JSON y devuelve un resumen por colección sin modificar BD."""
    await _require_admin(authorization)
    payload = await _read_payload(file)
    cols = _validate_bundle_payload(payload)

    summary = []
    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        docs = cols.get(cfg["collection"], []) or []
        valid_keys = []
        invalid = 0
        for d in docs:
            if isinstance(d, dict) and d.get(cfg["key"]):
                valid_keys.append(d[cfg["key"]])
            else:
                invalid += 1
        existing = await db[cfg["collection"]].find(
            {cfg["key"]: {"$in": valid_keys}}, {"_id": 0, cfg["key"]: 1}
        ).to_list(None)
        existing_keys = {e[cfg["key"]] for e in existing}
        to_update = sum(1 for k in valid_keys if k in existing_keys)
        to_create = len(valid_keys) - to_update
        summary.append({
            "collection": cfg["collection"],
            "label": cfg["label"],
            "total_in_file": len(docs),
            "valid": len(valid_keys),
            "invalid": invalid,
            "to_create": to_create,
            "to_update": to_update,
        })

    return {
        "module": "quotes-bundle",
        "exported_at": payload.get("exported_at"),
        "exported_by": payload.get("exported_by"),
        "summary": summary,
    }


@router.post("/admin/quotes-bundle-migration/import-data")
async def quotes_bundle_import_data(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Aplica el upsert por colección usando el id natural de cada una."""
    user = await _require_admin(authorization)
    payload = await _read_payload(file)
    cols = _validate_bundle_payload(payload)

    now_iso = datetime.now(timezone.utc).isoformat()
    results = []

    for cfg in QUOTES_BUNDLE_COLLECTIONS:
        docs = cols.get(cfg["collection"], []) or []
        collection = db[cfg["collection"]]
        key = cfg["key"]
        inserted = updated = skipped = 0
        errors = []

        valid_keys = [d[key] for d in docs if isinstance(d, dict) and d.get(key)]
        existing = await collection.find({key: {"$in": valid_keys}}, {"_id": 0}).to_list(None)
        existing_map = {e[key]: e for e in existing}

        for d in docs:
            if not isinstance(d, dict) or not d.get(key):
                skipped += 1
                errors.append({"reason": "missing_key", "key_field": key})
                continue
            try:
                doc = {k: v for k, v in d.items() if k != "_id"}
                kv = doc[key]
                if kv in existing_map:
                    original_created = existing_map[kv].get("created_at")
                    if original_created and not doc.get("created_at"):
                        doc["created_at"] = original_created
                    doc["updated_at"] = now_iso
                    doc["updated_by"] = user.get("email")
                    await collection.update_one({key: kv}, {"$set": doc})
                    updated += 1
                else:
                    if not doc.get("created_at"):
                        doc["created_at"] = now_iso
                    doc["imported_at"] = now_iso
                    doc["imported_by"] = user.get("email")
                    await collection.insert_one(doc)
                    inserted += 1
            except Exception as e:
                skipped += 1
                errors.append({"key": d.get(key), "error": str(e)})

        results.append({
            "collection": cfg["collection"],
            "label": cfg["label"],
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "errors": errors[:10],
        })

    await db.bitacora.insert_one({
        "action": "quotes_bundle_import_data",
        "results": results,
        "source_exported_at": payload.get("exported_at"),
        "source_exported_by": payload.get("exported_by"),
        "executed_by": user.get("email"),
        "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "executed_at": now_iso,
    })

    totals = {
        "inserted": sum(r["inserted"] for r in results),
        "updated": sum(r["updated"] for r in results),
        "skipped": sum(r["skipped"] for r in results),
    }
    return {
        "module": "quotes-bundle",
        "results": results,
        "totals": totals,
        "message": (
            f"Migración completada: {totals['inserted']} creado(s), "
            f"{totals['updated']} actualizado(s), {totals['skipped']} omitido(s)."
        ),
    }


@router.post("/admin/quotes-bundle-migration/import-attachments")
async def quotes_bundle_import_attachments(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Restaura los archivos del ZIP al Object Storage + filesystem.
    Cada archivo conserva su path relativo original (`attachments/.../*.pdf`)."""
    user = await _require_admin(authorization)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Archivo no es un ZIP válido")

    restored = 0
    skipped = 0
    errors = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        rel = info.filename.lstrip("/")
        # Evitar el manifest y rutas que quieran salir del directorio
        if rel == "manifest.json" or ".." in rel.split("/"):
            skipped += 1
            continue
        try:
            data = zf.read(info)
            local_path = UPLOADS_DIR / rel
            save_pdf_dual(local_path, data, rel)
            restored += 1
        except Exception as e:
            errors.append({"path": rel, "error": str(e)})
            skipped += 1

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.bitacora.insert_one({
        "action": "quotes_bundle_import_attachments",
        "restored": restored,
        "skipped": skipped,
        "executed_by": user.get("email"),
        "executed_at": now_iso,
    })

    return {
        "module": "quotes-bundle-attachments",
        "restored": restored,
        "skipped": skipped,
        "errors": errors[:20],
        "message": f"Restauración completada: {restored} archivo(s) restaurado(s), {skipped} omitido(s).",
    }
