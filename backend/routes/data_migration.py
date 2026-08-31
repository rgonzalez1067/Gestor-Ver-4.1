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
import asyncio
import io
import json
import logging
import gc
import hashlib
import os
import secrets
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from bson.json_util import dumps as bson_dumps, loads as bson_loads
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, Response
from starlette.background import BackgroundTask

from config import db, get_current_user, UPLOADS_DIR
from services.pdf_storage import get_pdf_from_storage, save_pdf_dual, save_pdf_to_storage, list_storage_keys, storage_key_exists

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
    "inventory-warehouses": {
        "collection": "warehouses",
        "key": "warehouse_id",
        "label": "Almacenes (Inventario)",
    },
    "inventory-serial-assignments": {
        "collection": "serial_assignments",
        "key": "assignment_id",
        "label": "Asignación de Seriales (Inventario)",
    },
    "inventory-movement-audits": {
        "collection": "inventory_movement_audits",
        "key": "audit_id",
        "label": "Auditoría de Movimientos (Inventario)",
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
    "integrators": {
        "collection": "integrators",
        "key": "integrator_id",
        "label": "Integradores",
    },
    "servers": {
        "collection": "servers",
        "key": "server_id",
        "label": "Servidores",
    },
    "fiscal-printers": {
        "collection": "fiscal_printer_models",
        "key": "model_id",
        "label": "Impresoras Fiscales",
    },
}

# Módulo virtual multi-colección: respalda Usuarios + Perfiles/Roles de forma relacional.
USER_PERMISSIONS_MODULE = "user-permissions"
USER_PERMISSIONS_COLLECTIONS = (
    ("profiles", "profile_id"),  # primero perfiles (los usuarios referencian profile_id)
    ("users", "user_id"),
)

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

async def _build_export_payload(module: str, user: dict) -> dict:
    """Construye el payload JSON de exportación para un módulo (simple o multi-colección)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    exporter = {
        "exported_at": now_iso,
        "exported_by": user.get("email"),
        "exported_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
    }

    if module == USER_PERMISSIONS_MODULE:
        collections = {}
        total = 0
        for cname, ckey in USER_PERMISSIONS_COLLECTIONS:
            docs = await db[cname].find({}, {"_id": 0}).to_list(None)
            collections[cname] = {"key": ckey, "documents": docs}
            total += len(docs)
        return {
            "schema_version": 1,
            "module": module,
            "multi": True,
            "label": "Permisos de Usuarios",
            **exporter,
            "count": total,
            "collections": collections,
        }

    cfg = _get_module_or_404(module)
    docs = await db[cfg["collection"]].find({}, {"_id": 0}).to_list(None)
    return {
        "schema_version": 1,
        "module": module,
        "collection": cfg["collection"],
        "key": cfg["key"],
        **exporter,
        "count": len(docs),
        "documents": docs,
    }


@router.get("/admin/migration/{module}/export")
async def export_module(module: str, authorization: Optional[str] = Header(None)):
    """Exporta TODOS los documentos del módulo en formato JSON estandarizado.
    El archivo resultante puede ser usado tal cual en /import-preview e /import-apply."""
    user = await _require_admin(authorization)
    payload = await _build_export_payload(module, user)

    # Bitácora
    await db.bitacora.insert_one({
        "action": "data_migration_export",
        "module": module,
        "count": payload.get("count", 0),
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
    payload = await _read_payload(file)

    # --- Módulo virtual multi-colección: Permisos de Usuarios (users + profiles) ---
    if module == USER_PERMISSIONS_MODULE:
        if payload.get("module") != module:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo es del módulo '{payload.get('module')}', pero se está importando en '{module}'.",
            )
        cols = payload.get("collections") or {}
        total_in_file = 0
        to_create_total = 0
        to_update_total = 0
        breakdown = {}
        for cname, ckey in USER_PERMISSIONS_COLLECTIONS:
            block = cols.get(cname) or {}
            docs = block.get("documents") or []
            keys = [d[ckey] for d in docs if isinstance(d, dict) and d.get(ckey)]
            existing = await db[cname].find({ckey: {"$in": keys}}, {"_id": 0, ckey: 1}).to_list(None)
            existing_keys = {e[ckey] for e in existing}
            tc = len([k for k in keys if k not in existing_keys])
            tu = len([k for k in keys if k in existing_keys])
            breakdown[cname] = {"total": len(docs), "to_create": tc, "to_update": tu}
            total_in_file += len(docs)
            to_create_total += tc
            to_update_total += tu
        return {
            "module": module,
            "multi": True,
            "exported_at": payload.get("exported_at"),
            "exported_by": payload.get("exported_by"),
            "total_in_file": total_in_file,
            "valid_count": total_in_file,
            "invalid_count": 0,
            "duplicates_in_file": [],
            "to_create_count": to_create_total,
            "to_update_count": to_update_total,
            "breakdown": breakdown,
        }

    cfg = _get_module_or_404(module)
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
    total_existing = await db[cfg["collection"]].count_documents({})
    to_delete_count = max(0, total_existing - len(to_update))

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
        "to_delete_count": to_delete_count,
        "existing_count": total_existing,
        "to_create_sample": to_create[:5],
        "to_update_sample": to_update[:5],
    }


# ==================== IMPORT: APPLY ====================

async def _apply_upsert_docs(collection_name: str, key: str, docs: list, user: dict, sanitize_users: bool = False, replace: bool = False):
    """Upsert idempotente de una lista de documentos por su id natural.
    Si replace=True, además ELIMINA de la colección los documentos cuyo id no
    está en el respaldo (réplica exacta del backup). Por seguridad, en la
    colección 'users' nunca se elimina al usuario que ejecuta la importación.
    Devuelve (inserted, updated, skipped, errors, deleted)."""
    collection = db[collection_name]
    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = updated = skipped = deleted = 0
    errors = []

    incoming_keys = [d[key] for d in docs if isinstance(d, dict) and d.get(key)]
    existing_docs = await collection.find({key: {"$in": incoming_keys}}, {"_id": 0}).to_list(None)
    existing_map = {e[key]: e for e in existing_docs}

    for d in docs:
        if not isinstance(d, dict) or not d.get(key):
            skipped += 1
            errors.append({"reason": "missing_key", "key_field": key})
            continue
        try:
            doc = {k: v for k, v in d.items() if k != "_id"}
            if sanitize_users:
                for f in USER_SANITIZE_FIELDS:
                    if f == "failed_attempts":
                        doc[f] = 0
                    elif f == "locked_until":
                        doc[f] = None
                    else:
                        doc.pop(f, None)
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

    # Réplica exacta: eliminar los registros que NO vienen en el respaldo.
    if replace:
        keep = set(incoming_keys)
        if collection_name == "users" and user.get("user_id"):
            keep.add(user.get("user_id"))  # nunca borrar al admin que importa
        del_res = await collection.delete_many({key: {"$nin": list(keep)}})
        deleted = del_res.deleted_count

    return inserted, updated, skipped, errors, deleted


async def _apply_import_payload(module: str, payload: dict, user: dict, mode: str = "upsert") -> dict:
    """Aplica un payload de import para un módulo (simple o multi-colección user-permissions).
    mode='upsert' (por defecto): agrega/actualiza sin borrar.
    mode='replace' (réplica exacta): además elimina los registros que NO están en el respaldo,
    dejando la colección idéntica al backup. Registra bitácora. Devuelve un dict-resumen."""
    now_iso = datetime.now(timezone.utc).isoformat()
    replace = (mode == "replace")

    # --- Módulo virtual multi-colección: Permisos de Usuarios (users + profiles) ---
    if module == USER_PERMISSIONS_MODULE:
        if payload.get("module") != module:
            raise HTTPException(
                status_code=400,
                detail=f"El archivo es del módulo '{payload.get('module')}', pero se está importando en '{module}'.",
            )
        cols = payload.get("collections") or {}
        total_inserted = total_updated = total_skipped = total_deleted = 0
        breakdown = {}
        all_errors = []
        # Perfiles primero, luego usuarios (mantiene la relación profile_id consistente)
        for cname, ckey in USER_PERMISSIONS_COLLECTIONS:
            block = cols.get(cname) or {}
            cdocs = block.get("documents") or []
            ins, upd, skp, errs, dele = await _apply_upsert_docs(
                cname, ckey, cdocs, user, sanitize_users=(cname == "users"), replace=replace
            )
            breakdown[cname] = {"inserted": ins, "updated": upd, "skipped": skp, "deleted": dele}
            total_inserted += ins
            total_updated += upd
            total_skipped += skp
            total_deleted += dele
            all_errors.extend(errs)

        await db.bitacora.insert_one({
            "action": "data_migration_import",
            "module": module,
            "mode": mode,
            "breakdown": breakdown,
            "inserted": total_inserted,
            "updated": total_updated,
            "skipped": total_skipped,
            "deleted": total_deleted,
            "source_exported_at": payload.get("exported_at"),
            "source_exported_by": payload.get("exported_by"),
            "executed_by": user.get("email"),
            "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
            "executed_at": now_iso,
        })

        return {
            "module": module,
            "multi": True,
            "mode": mode,
            "breakdown": breakdown,
            "inserted": total_inserted,
            "updated": total_updated,
            "skipped": total_skipped,
            "deleted": total_deleted,
            "errors": all_errors[:20],
            "message": (
                f"Permisos de Usuarios importados: {total_inserted} creado(s), "
                f"{total_updated} actualizado(s), {total_skipped} omitido(s)"
                + (f", {total_deleted} eliminado(s)." if replace else ".")
            ),
        }

    cfg = _get_module_or_404(module)
    docs = _validate_payload(payload, cfg, module)

    inserted, updated, skipped, errors, deleted = await _apply_upsert_docs(
        cfg["collection"], cfg["key"], docs, user, sanitize_users=(module == "users"), replace=replace
    )

    await db.bitacora.insert_one({
        "action": "data_migration_import",
        "module": module,
        "collection": cfg["collection"],
        "mode": mode,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "deleted": deleted,
        "source_exported_at": payload.get("exported_at"),
        "source_exported_by": payload.get("exported_by"),
        "executed_by": user.get("email"),
        "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
        "executed_at": now_iso,
    })

    return {
        "module": module,
        "collection": cfg["collection"],
        "mode": mode,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "deleted": deleted,
        "errors": errors[:20],
        "message": (
            f"Migración completada: {inserted} creado(s), {updated} actualizado(s), {skipped} omitido(s)"
            + (f", {deleted} eliminado(s)." if replace else ".")
        ),
    }


@router.post("/admin/migration/{module}/import-apply")
async def import_apply(
    module: str,
    file: UploadFile = File(...),
    mode: str = Form("upsert"),
    authorization: Optional[str] = Header(None),
):
    """Aplica el import. mode='upsert' agrega/actualiza; mode='replace' deja la
    colección idéntica al respaldo (borra lo que no está en el backup).
    Conserva created_at original al actualizar; refresca updated_at."""
    user = await _require_admin(authorization)
    payload = await _read_payload(file)
    return await _apply_import_payload(module, payload, user, mode=mode)


# =====================================================================
# CENTRO DE RESPALDOS — Grilla unificada + Exportación masiva (ZIP)
# =====================================================================
# Las 9 entidades gobernadas por el Centro de Respaldos (Configuración).
# Excluidos a propósito: cotizaciones, histórico y proyectos (se respaldan
# en sus propias vistas, fuera de este centro).
BACKUP_CENTER_ENTITIES = [
    {"module": "clients", "label": "Clientes"},
    {"module": "banks", "label": "Bancos"},
    {"module": "payment-methods", "label": "Medios de Pago"},
    {"module": "hardware", "label": "Bienes y Servicios"},
    {"module": "commercial-categories", "label": "Categoría Comercial"},
    {"module": "inventory-movements", "label": "Inventarios"},
    {"module": "inventory-warehouses", "label": "Almacenes (Inventario)"},
    {"module": "inventory-serial-assignments", "label": "Asignación de Seriales (Inventario)"},
    {"module": "inventory-movement-audits", "label": "Auditoría de Movimientos (Inventario)"},
    {"module": "taller-equipos", "label": "Equipos en Reparación"},
    {"module": USER_PERMISSIONS_MODULE, "label": "Permisos de Usuarios"},
    {"module": "integrators", "label": "Integradores"},
    {"module": "servers", "label": "Servidores"},
    {"module": "fiscal-printers", "label": "Impresoras Fiscales"},
]


async def _entity_count(module: str) -> int:
    if module == USER_PERMISSIONS_MODULE:
        total = 0
        for cname, _ in USER_PERMISSIONS_COLLECTIONS:
            total += await db[cname].count_documents({})
        return total
    cfg = MODULES.get(module)
    if not cfg:
        return 0
    return await db[cfg["collection"]].count_documents({})


@router.get("/admin/backup-center/entities")
async def backup_center_entities(authorization: Optional[str] = Header(None)):
    """Lista las entidades del Centro de Respaldos con su conteo de registros."""
    await _require_admin(authorization)
    out = []
    for e in BACKUP_CENTER_ENTITIES:
        out.append({**e, "count": await _entity_count(e["module"])})
    return {"entities": out}


@router.post("/admin/backup-center/export-zip")
async def backup_center_export_zip(payload: dict, authorization: Optional[str] = Header(None)):
    """Exportación masiva: empaqueta las entidades seleccionadas en un único ZIP
    con un archivo JSON por entidad (mismo formato que el export individual)."""
    user = await _require_admin(authorization)
    modules = payload.get("modules") or []
    valid_modules = {e["module"] for e in BACKUP_CENTER_ENTITIES}
    selected = [m for m in modules if m in valid_modules]
    if not selected:
        raise HTTPException(status_code=400, detail="No se indicaron entidades válidas para exportar")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"exported_at": datetime.now(timezone.utc).isoformat(), "exported_by": user.get("email"), "modules": []}
        for m in selected:
            data = await _build_export_payload(m, user)
            zf.writestr(f"{m}.json", json.dumps(data, ensure_ascii=False, default=str, indent=2))
            manifest["modules"].append({"module": m, "count": data.get("count", 0)})
        zf.writestr("_manifest.json", json.dumps(manifest, ensure_ascii=False, default=str, indent=2))
    buf.seek(0)

    await db.bitacora.insert_one({
        "action": "backup_center_export_zip",
        "modules": selected,
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    filename = f"backup_center_{ts}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/backup-center/history")
async def backup_center_history(authorization: Optional[str] = Header(None)):
    """Historial de respaldos/restauraciones (auditoría): exportaciones e
    importaciones realizadas en el Centro de Respaldos, con fecha y usuario."""
    await _require_admin(authorization)
    actions = [
        "data_migration_export", "data_migration_import",
        "backup_center_export_zip", "backup_center_import_zip",
    ]
    label_map = {e["module"]: e["label"] for e in BACKUP_CENTER_ENTITIES}
    rows = await db.bitacora.find(
        {"action": {"$in": actions}}, {"_id": 0}
    ).sort("executed_at", -1).limit(60).to_list(None)

    history = []
    for r in rows:
        action = r.get("action", "")
        is_export = "export" in action
        is_zip = "zip" in action
        mods = r.get("modules")
        if mods:
            modules_label = ", ".join(label_map.get(m, m) for m in mods)
        else:
            modules_label = label_map.get(r.get("module"), r.get("module") or "—")
        history.append({
            "action": action,
            "kind": "export" if is_export else "import",
            "scope": "masivo" if is_zip else "entidad",
            "mode": r.get("mode"),
            "modules_label": modules_label,
            "modules_count": len(mods) if mods else 1,
            "inserted": r.get("inserted", 0),
            "updated": r.get("updated", 0),
            "deleted": r.get("deleted", 0),
            "skipped": r.get("skipped", 0),
            "count": r.get("count", 0),
            "executed_by": r.get("executed_by") or r.get("executed_by_name") or "—",
            "executed_at": r.get("executed_at"),
            "errors": len(r.get("errors") or []),
        })
    return {"history": history, "total": len(history)}



def _module_from_zip_entry(name: str) -> Optional[str]:
    """Deriva el slug del módulo desde el nombre del archivo dentro del ZIP.
    Ignora _manifest.json, carpetas y archivos no-JSON."""
    base = name.rsplit("/", 1)[-1]
    if not base.endswith(".json") or base.startswith("_") or base.startswith("."):
        return None
    return base[: -len(".json")]


@router.post("/admin/backup-center/import-preview-zip")
async def backup_center_import_preview_zip(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Lee un ZIP de respaldo y devuelve, por entidad, cuántos registros se
    crearán/actualizarán. NO modifica datos."""
    await _require_admin(authorization)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Debe subir un archivo .zip de respaldo")

    raw = await file.read()
    valid_modules = {e["module"] for e in BACKUP_CENTER_ENTITIES}
    label_map = {e["module"]: e["label"] for e in BACKUP_CENTER_ENTITIES}
    entities = []
    skipped_files = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                module = _module_from_zip_entry(name)
                if module is None:
                    continue
                if module not in valid_modules:
                    skipped_files.append(name)
                    continue
                try:
                    payload = json.loads(zf.read(name).decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    skipped_files.append(name)
                    continue

                if module == USER_PERMISSIONS_MODULE:
                    cols = payload.get("collections") or {}
                    total = sum(len((cols.get(c) or {}).get("documents") or []) for c, _ in USER_PERMISSIONS_COLLECTIONS)
                else:
                    total = len(payload.get("documents") or [])
                entities.append({"module": module, "label": label_map.get(module, module), "records": total})
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo no es un ZIP válido")

    if not entities:
        raise HTTPException(status_code=400, detail="El ZIP no contiene archivos de respaldo válidos de las entidades soportadas")

    return {"entities": entities, "skipped_files": skipped_files, "total_entities": len(entities)}


@router.post("/admin/backup-center/import-zip")
async def backup_center_import_zip(
    file: UploadFile = File(...),
    mode: str = Form("upsert"),
    authorization: Optional[str] = Header(None),
):
    """Importación masiva: restaura TODAS las entidades contenidas en un ZIP de
    respaldo. mode='upsert' agrega/actualiza; mode='replace' deja cada entidad
    idéntica al respaldo (réplica exacta, borra lo que no está en el backup)."""
    user = await _require_admin(authorization)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Debe subir un archivo .zip de respaldo")

    raw = await file.read()
    valid_modules = {e["module"] for e in BACKUP_CENTER_ENTITIES}
    results = []
    errors = []
    # user-permissions de último para que perfiles/usuarios se restauren al final
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            entries = []
            for name in zf.namelist():
                module = _module_from_zip_entry(name)
                if module is None or module not in valid_modules:
                    continue
                entries.append((module, name))
            entries.sort(key=lambda x: (x[0] == USER_PERMISSIONS_MODULE, x[0]))

            for module, name in entries:
                try:
                    payload = json.loads(zf.read(name).decode("utf-8"))
                    res = await _apply_import_payload(module, payload, user, mode=mode)
                    results.append({
                        "module": module,
                        "inserted": res.get("inserted", 0),
                        "updated": res.get("updated", 0),
                        "skipped": res.get("skipped", 0),
                        "deleted": res.get("deleted", 0),
                    })
                except HTTPException as he:
                    errors.append({"module": module, "error": he.detail})
                except Exception as e:  # noqa: BLE001
                    errors.append({"module": module, "error": str(e)})
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo no es un ZIP válido")

    if not results and not errors:
        raise HTTPException(status_code=400, detail="El ZIP no contiene archivos de respaldo válidos de las entidades soportadas")

    total_inserted = sum(r["inserted"] for r in results)
    total_updated = sum(r["updated"] for r in results)
    total_skipped = sum(r["skipped"] for r in results)
    total_deleted = sum(r.get("deleted", 0) for r in results)

    await db.bitacora.insert_one({
        "action": "backup_center_import_zip",
        "mode": mode,
        "modules": [r["module"] for r in results],
        "inserted": total_inserted,
        "updated": total_updated,
        "skipped": total_skipped,
        "deleted": total_deleted,
        "errors": errors,
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "results": results,
        "errors": errors,
        "total_inserted": total_inserted,
        "total_updated": total_updated,
        "total_skipped": total_skipped,
        "total_deleted": total_deleted,
        "message": (
            f"Importación masiva completada: {len(results)} entidad(es), "
            f"{total_inserted} creado(s), {total_updated} actualizado(s), {total_skipped} omitido(s)"
            + (f", {total_deleted} eliminado(s)." if mode == "replace" else ".")
            + (f" {len(errors)} con error." if errors else "")
        ),
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


# ---------------------------------------------------------------------------
# CONTINGENCIA · IMPORT PAGINADO ANEXOS — Subida individual por archivo.
# ---------------------------------------------------------------------------
# Diseñado para sortear el límite de tamaño del ingress (típicamente 1MB en
# nginx por defecto) y los timeouts del proxy: cada archivo se sube en su
# propia request pequeña. El cliente (browser) extrae el ZIP localmente con
# JSZip y emite N peticiones POST. Es el simétrico del download paginado.
# ---------------------------------------------------------------------------
@router.post("/admin/quotes-bundle-migration/import-attachment")
async def quotes_bundle_import_attachment(
    path: str = Form(...),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Restaura UN solo anexo dado su path relativo (relativo a /uploads/)."""
    user = await _require_admin(authorization)
    rel = (path or "").lstrip("/")
    if not rel or ".." in rel.replace("\\", "/").split("/"):
        raise HTTPException(status_code=400, detail="Path inválido")
    if rel == "manifest.json":
        return {"ok": True, "skipped": True, "reason": "manifest"}

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")

    try:
        local_path = UPLOADS_DIR / rel
        save_pdf_dual(local_path, raw, rel)
        # Verificación de integridad: confirmar que el archivo quedó escrito en
        # disco. Esto NO valida storage (su fallo es silencioso por diseño)
        # pero al menos asegura que el binario llegó completo al filesystem.
        if not local_path.exists():
            raise IOError(f"archivo no presente tras write: {local_path}")
        actual_size = local_path.stat().st_size
        if actual_size != len(raw):
            raise IOError(f"tamaño inconsistente tras write: esperado={len(raw)} actual={actual_size}")
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error(f"[import-attachment] fallo guardando {rel}: {e}")
        raise HTTPException(status_code=500, detail=f"Error guardando {rel}: {e}")

    # Bitácora ligera (sin spam: una sola línea con el contador es suficiente
    # cuando se usa en lote; aquí solo log de debug si se necesita rastrear).
    await db.bitacora.insert_one({
        "action": "quotes_bundle_import_attachment_single",
        "path": rel,
        "size": len(raw),
        "executed_by": user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "path": rel, "size": len(raw)}



# ==================== AUTO-RECOVERY: ATTACHMENTS → OBJECT STORAGE ====================

@router.post("/admin/attachments/recover-to-storage")
async def recover_attachments_to_storage(
    dry_run: bool = False,
    skip: int = 0,
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    """Audita anexos en `quotes.attachments` y `quote_history.attachments`
    y los sube al Object Storage si no están allí.

    Paginado por defecto en lotes de 50 (skip/limit) para evitar timeouts del
    proxy (K8s ingress ~60s). El frontend debe llamar repetidamente hasta que
    `done=true`.

    Params:
      - dry_run=true: solo escanea y reporta, no sube nada.
      - skip: offset para paginar (default 0).
      - limit: tamaño del lote (default 50, max 200).

    Returns: { scanned, already_in_storage, uploaded, missing_everywhere,
               errors, total, processed_so_far, done, next_skip,
               missing_details, by_collection }
    """
    import asyncio as _asyncio

    user = await _require_admin(authorization)
    limit = max(1, min(int(limit or 50), 200))
    skip = max(0, int(skip or 0))

    # 1) Recolectar TODOS los pares (ordenados de forma estable) para paginar
    all_tasks: list = []  # (coll_name, parent_id, parent_number, client_name, attachment)

    async for q in db.quotes.find(
        {"attachments": {"$exists": True, "$ne": []}},
        {"_id": 0, "quote_id": 1, "quote_number": 1, "client_name": 1, "attachments": 1},
    ).sort("quote_id", 1):
        for att in (q.get("attachments") or []):
            all_tasks.append(("quotes", q.get("quote_id"), q.get("quote_number") or "",
                              q.get("client_name") or "", att))

    async for h in db.quote_history.find(
        {"attachments": {"$exists": True, "$ne": []}},
        {"_id": 0, "history_id": 1, "quote_id": 1, "quote_number": 1, "client_name": 1, "attachments": 1},
    ).sort("history_id", 1):
        for att in (h.get("attachments") or []):
            all_tasks.append(("quote_history", h.get("history_id"), h.get("quote_number") or "",
                              h.get("client_name") or "", att))

    total = len(all_tasks)
    batch = all_tasks[skip: skip + limit]

    # Inventario de claves en Object Storage (UNA sola llamada de red por lote).
    # Verificar existencia en memoria evita descargar cada archivo y elimina el
    # timeout del proxy (Cloudflare 524) que ocurría con get_pdf_from_storage por anexo.
    try:
        storage_keys = await _asyncio.to_thread(list_storage_keys)
    except Exception as e:
        logger.warning(f"[recover] No se pudo listar el inventario de storage: {e}")
        storage_keys = set()

    # 2) Procesar el lote con concurrencia controlada
    sem = _asyncio.Semaphore(8)
    missing_details: list = []
    error_details: list = []
    counters = {"scanned": 0, "already_ok": 0, "uploaded": 0,
                "missing_everywhere": 0, "errors": 0}
    by_collection = {"quotes": {"scanned": 0, "ok": 0, "uploaded": 0, "missing": 0},
                     "quote_history": {"scanned": 0, "ok": 0, "uploaded": 0, "missing": 0}}

    async def _process(coll_name: str, parent_id: str, parent_number: str, client_name: str, attachment: dict):
        async with sem:
            counters["scanned"] += 1
            by_collection[coll_name]["scanned"] += 1

            rel = (attachment.get("url") or "").replace("/uploads/", "").lstrip("/")
            att_id = attachment.get("attachment_id", "?")
            if not rel:
                counters["errors"] += 1
                error_details.append({"collection": coll_name, "parent_id": parent_id,
                                       "attachment_id": att_id, "reason": "url vacía/inválida"})
                return

            try:
                obj = rel in storage_keys
                if not obj:
                    # El inventario global se trunca a 1000 claves; verificar de forma
                    # autoritativa por archivo evita re-subir archivos que YA existen
                    # (por eso el KPI "por subir" no convergía).
                    obj = await _asyncio.to_thread(storage_key_exists, rel)
            except Exception as e:
                obj = None
                logger.warning(f"[recover] storage existence check error {rel}: {e}")

            if obj:
                counters["already_ok"] += 1
                by_collection[coll_name]["ok"] += 1
                return

            local_path = UPLOADS_DIR / rel
            if not local_path.exists():
                counters["missing_everywhere"] += 1
                by_collection[coll_name]["missing"] += 1
                missing_details.append({
                    "collection": coll_name, "parent_id": parent_id,
                    "parent_number": parent_number, "client_name": client_name,
                    "attachment_id": att_id,
                    "filename": attachment.get("filename"), "rel_path": rel,
                    "content_type": attachment.get("content_type") or "",
                    "uploaded_at": attachment.get("uploaded_at") or attachment.get("created_at") or "",
                })
                return

            if dry_run:
                counters["uploaded"] += 1
                by_collection[coll_name]["uploaded"] += 1
                return

            try:
                content = await _asyncio.to_thread(local_path.read_bytes)
                ctype = attachment.get("content_type") or "application/octet-stream"
                ok = await _asyncio.to_thread(save_pdf_to_storage, content, rel, ctype)
                if ok:
                    counters["uploaded"] += 1
                    by_collection[coll_name]["uploaded"] += 1
                else:
                    counters["errors"] += 1
                    error_details.append({"collection": coll_name, "parent_id": parent_id,
                                           "attachment_id": att_id, "reason": "put_object False"})
            except Exception as e:
                counters["errors"] += 1
                error_details.append({"collection": coll_name, "parent_id": parent_id,
                                       "attachment_id": att_id, "reason": str(e)})

    await _asyncio.gather(*[_process(*t) for t in batch])

    processed = skip + len(batch)
    done = processed >= total

    # Bitácora solo al final del último lote (evita spam)
    if done:
        await db.bitacora.insert_one({
            "action": "attachments_recover_to_storage",
            "dry_run": dry_run,
            "total": total,
            **counters,
            "executed_by": user.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "dry_run": dry_run,
        "total": total,
        "processed_so_far": processed,
        "done": done,
        "next_skip": processed if not done else None,
        "scanned": counters["scanned"],
        "already_in_storage": counters["already_ok"],
        "uploaded": counters["uploaded"],
        "missing_everywhere": counters["missing_everywhere"],
        "errors": counters["errors"],
        "by_collection": by_collection,
        "missing_details": missing_details,
        "missing_details_total": len(missing_details),
        "error_details": error_details[:20],
        "message": (
            f"{'[DRY-RUN] ' if dry_run else ''}"
            f"Lote: {len(batch)} | Ya en storage: {counters['already_ok']} | "
            f"{'A subir' if dry_run else 'Subidos'}: {counters['uploaded']} | "
            f"Sin archivo: {counters['missing_everywhere']} | Errores: {counters['errors']}"
        ),
    }




# ==================== RESPALDO TOTAL DE BASE DE DATOS ====================
# Respalda/restaura TODAS las colecciones (incluye bitácora, correos, config,
# contadores, sesiones, mensajería, etc.) con fidelidad exacta usando Extended
# JSON (preserva _id ObjectId, fechas y tipos BSON). La restauración hace
# drop + insert por colección => réplica exacta del respaldo. La subida es por
# chunks para evitar límites del proxy con archivos grandes.

def _assemble_upload_to_gridfs_sync(upload_id: str, db_name: str) -> str:
    """Ensambla los chunks (guardados en Mongo) en un único archivo GridFS y
    devuelve su gridfs_id. Memoria O(1): escribe chunk por chunk. Almacenamiento
    COMPARTIDO entre réplicas (evita el /tmp por-pod que rompía con 2 réplicas).
    Reutiliza el ensamblado si ya existe (idempotente)."""
    from pymongo import MongoClient
    from bson import ObjectId
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    try:
        up = sdb.fb_uploads.find_one({"upload_id": upload_id})
        if not up:
            raise HTTPException(status_code=404, detail="Respaldo subido no encontrado (¿expiró?)")
        if up.get("assembled_gridfs_id"):
            return str(up["assembled_gridfs_id"])
        bucket = _sync_gridfs_bucket(sdb)
        grid_in = bucket.open_upload_stream(f"upload_{upload_id}.zip", metadata={"upload_id": upload_id})
        try:
            for ch in sdb.fb_upload_chunks.find({"upload_id": upload_id}).sort("chunk_index", 1):
                grid_in.write(bytes(ch["data"]))
            grid_in.close()
        except Exception:
            try:
                grid_in.abort()
            except Exception:
                pass
            raise
        gid = grid_in._id
        sdb.fb_uploads.update_one({"upload_id": upload_id}, {"$set": {"assembled_gridfs_id": gid}})
        sdb.fb_upload_chunks.delete_many({"upload_id": upload_id})
        return str(gid)
    finally:
        sclient.close()


def _cleanup_upload_sync(upload_id: str, db_name: str):
    """Borra el buffer de subida (chunks + archivo GridFS ensamblado + doc)."""
    from pymongo import MongoClient
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    try:
        up = sdb.fb_uploads.find_one({"upload_id": upload_id}) or {}
        gid = up.get("assembled_gridfs_id")
        if gid:
            try:
                _sync_gridfs_bucket(sdb).delete(gid)
            except Exception:
                pass
        sdb.fb_upload_chunks.delete_many({"upload_id": upload_id})
        sdb.fb_uploads.delete_one({"upload_id": upload_id})
    finally:
        sclient.close()



@router.get("/admin/full-backup/info")
async def full_backup_info(authorization: Optional[str] = Header(None)):
    """Lista todas las colecciones con su conteo (para la UI del Respaldo Total)."""
    await _require_admin(authorization)
    cols = sorted(await db.list_collection_names())
    out = []
    total_docs = 0
    for name in cols:
        cnt = await db[name].count_documents({})
        total_docs += cnt
        out.append({"name": name, "count": cnt})
    return {
        "db_name": db.name,
        "total_collections": len(cols),
        "total_documents": total_docs,
        "collections": out,
    }


class _ZipStreamBuf:
    """File-like NO buscable para escribir un ZIP en streaming (data descriptors)."""
    def __init__(self):
        self.buf = bytearray()
        self._pos = 0
    def write(self, b):
        self.buf += b
        self._pos += len(b)
        return len(b)
    def tell(self):
        return self._pos
    def flush(self):
        pass
    def seekable(self):
        return False
    def drain(self):
        if self.buf:
            out = bytes(self.buf)
            self.buf.clear()
            return out
        return b""


# =====================================================================
# RESPALDO TOTAL — Modelo ASÍNCRONO (build en 2º plano → descarga de archivo listo)
# =====================================================================
# Problema resuelto:
#   - Streaming chunked SIN Content-Length → el CDN truncaba el final del ZIP.
#   - Build sincrónico + FileResponse → el origen no enviaba bytes por minutos
#     mientras armaba el ZIP y Cloudflare cortaba con 524 (timeout ~100s).
# Solución:
#   1) POST /admin/full-backup/build        → arma el ZIP en disco en 2º plano.
#   2) GET  /admin/full-backup/build-status → el cliente sondea hasta "ready".
#   3) GET  /admin/full-backup/export       → sirve el archivo YA LISTO con
#      FileResponse (Content-Length real, primer byte inmediato → sin 524 ni
#      truncado). Auth por header o por `ticket` (descarga nativa del navegador).
# La memoria del pod se mantiene O(1): se lee un documento a la vez.
# =====================================================================
# El artefacto del respaldo se guarda en GridFS de MongoDB (almacenamiento
# COMPARTIDO entre réplicas), NO en el disco local del pod. Producción corre
# 2 réplicas sin afinidad de sesión: el build ocurría en el /tmp de un pod y la
# descarga caía en el otro → HTTP 410. Con GridFS cualquier réplica sirve el
# archivo, y el streaming (subida/bajada) mantiene la memoria O(1) sin tocar el
# disco efímero de 1Gi.
_BACKUP_BUCKET = "backups"

# Colecciones que NUNCA se incluyen en el dump:
#  - backups.files / backups.chunks: el propio transporte GridFS del respaldo
#    (incluirlas causaría recursión y tamaño explosivo).
#  - backup_jobs / download_tickets / restore_jobs: estado operativo transitorio.
#  - fb_uploads / fb_upload_chunks: buffer transitorio de subida por chunks.
_BACKUP_EXCLUDE = {
    f"{_BACKUP_BUCKET}.files",
    f"{_BACKUP_BUCKET}.chunks",
    "backup_jobs",
    "download_tickets",
    "restore_jobs",
    "fb_uploads",
    "fb_upload_chunks",
}

# Respaldo Total V2 — SEGMENTACIÓN Y DESACOPLE DE MAESTRAS
# Las 11 colecciones maestras "de negocio" del Centro de Respaldos se EXCLUYEN
# del Respaldo Total (se respaldan/restauran por su rutina propia). users y
# profiles se MANTIENEN en el Total para garantizar el login tras un desastre.
_MASTER_EXCLUDE = {
    "clients",
    "banks",
    "services",                    # Medios de Pago
    "hardware",                    # Bienes y Servicios
    "commercial_categories",
    "inventory_movements",
    "warehouses",
    "serial_assignments",
    "inventory_movement_audits",
    "taller_equipos",
    "integrators",
}

# Tamaño máximo (bytes, sin comprimir) por segmento del Respaldo Total V2.
SEGMENT_MAX_BYTES = 50 * 1024 * 1024

# Colecciones CRÍTICAS de acceso que NUNCA deben eliminarse en el paso de
# "borrado de sobrantes" de una restauración en modo `replace`, aunque el ZIP
# que se está restaurando no las contenga. Garantiza que el login sobreviva a
# una restauración modular (varios ZIP por grupo) o parcial.
_LOGIN_PROTECT = {"users", "profiles"}



def _sync_gridfs_bucket(sdb):
    from gridfs import GridFSBucket
    return GridFSBucket(sdb, bucket_name=_BACKUP_BUCKET)


def _async_gridfs_bucket():
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    return AsyncIOMotorGridFSBucket(db, bucket_name=_BACKUP_BUCKET)


async def _delete_backup_gridfs(gridfs_id):
    if not gridfs_id:
        return
    try:
        await _async_gridfs_bucket().delete(gridfs_id)
    except Exception:
        pass


class _GridZipWriter:
    """Adaptador de escritura para pasar un stream de GridFS a zipfile.
    GridIn.write() devuelve None; zipfile necesita que write() devuelva el nº de
    bytes y expone tell(). Marcamos el stream como NO buscable → zipfile usa
    data descriptors (válido para streaming). No cierra el GridIn (se cierra
    aparte para finalizar el archivo)."""
    def __init__(self, grid_in):
        self._g = grid_in
        self._pos = 0
    def write(self, data):
        self._g.write(data)
        n = len(data)
        self._pos += n
        return n
    def tell(self):
        return self._pos
    def flush(self):
        pass
    def seekable(self):
        return False
    def close(self):
        pass


async def _cleanup_stale_backups(max_age_hours: int = 2):
    """Borra jobs y sus archivos GridFS más viejos que max_age_hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    try:
        async for j in db.backup_jobs.find({}):
            try:
                created = datetime.fromisoformat(j.get("created_at"))
            except Exception:
                created = None
            if created is None or created < cutoff:
                await _delete_backup_gridfs(j.get("gridfs_id"))
                await db.backup_jobs.delete_one({"_id": j["_id"]})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[full-backup] cleanup stale fallo: {e}")


def _build_full_backup_sync(job_id: str, user: dict, db_name: str, only_collections=None, group_label=None):
    """Arma el ZIP de la BD (o de un SUBCONJUNTO/grupo de colecciones) y lo escribe
    DIRECTO a GridFS con pymongo síncrono en un hilo. `only_collections` limita el
    respaldo a ese grupo (respaldo modular); si es None, respalda todo (menos las
    12 maestras y las colecciones internas). El progreso va en `backup_jobs`."""
    from pymongo import MongoClient

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    lbl = f"_{group_label}" if group_label else ""
    filename = f"full_backup_{db_name}{lbl}_{ts}.zip"

    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    bucket = _sync_gridfs_bucket(sdb)
    grid_in = bucket.open_upload_stream(f"{job_id}.zip", metadata={"job_id": job_id, "filename": filename})
    closed = False
    try:
        all_cols = sorted(sdb.list_collection_names())
        if only_collections:
            subset = set(only_collections)
            cols = [c for c in all_cols if c in subset and c not in _BACKUP_EXCLUDE]
            excluded_present = []
        else:
            excluded_present = sorted([c for c in all_cols if c in _MASTER_EXCLUDE])
            cols = [c for c in all_cols if c not in _BACKUP_EXCLUDE and c not in _MASTER_EXCLUDE]
        logger.info(
            f"[full-backup] job {job_id} grupo={group_label or 'TOTAL'}: maestras EXCLUIDAS ({len(excluded_present)})={excluded_present} "
            f"| colecciones a respaldar={len(cols)}"
        )
        manifest = {
            "schema_version": 2,
            "type": "full-database-backup-segmented",
            "format": "mongodb-extended-json-jsonl",
            "db_name": db_name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": user.get("email"),
            "exported_by_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "excluded_masters": excluded_present,
            "group_label": group_label,
            "is_partial": bool(only_collections),
            "segment_max_bytes": SEGMENT_MAX_BYTES,
            "segments": [],
            "collections": [],
        }
        col_counts = []
        # Estado de segmentación (un ZIP anidado por segmento, ≤ SEGMENT_MAX_BYTES)
        seg_state = {"idx": 0, "buf": None, "zf": None, "bytes": 0, "parts": []}

        def _new_segment():
            buf = io.BytesIO()
            seg_state["buf"] = buf
            seg_state["zf"] = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
            seg_state["bytes"] = 0
            seg_state["parts"] = []

        def _finalize_segment(container):
            if seg_state["zf"] is None:
                return
            seg_state["zf"].close()
            data = seg_state["buf"].getvalue()
            seg_state["idx"] += 1
            seg_name = f"segments/segment_{seg_state['idx']:04d}.zip"
            container.writestr(seg_name, data)
            manifest["segments"].append({
                "index": seg_state["idx"],
                "filename": seg_name,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "parts": seg_state["parts"],
            })
            sdb.backup_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"progress_segments": seg_state["idx"]}},
            )
            seg_state["buf"] = None
            seg_state["zf"] = None
            seg_state["bytes"] = 0
            seg_state["parts"] = []
            gc.collect()

        with zipfile.ZipFile(_GridZipWriter(grid_in), "w", zipfile.ZIP_STORED) as container:
            done_cols = 0
            for cname in cols:
                if seg_state["zf"] is None:
                    _new_segment()
                count = 0
                part_index = 1
                part_name = f"collections/{cname}.part{part_index:04d}.jsonl"
                entry = seg_state["zf"].open(part_name, "w")
                part_count = 0
                part_hash = hashlib.sha256()
                cursor = sdb[cname].find({}, no_cursor_timeout=True).batch_size(500)
                try:
                    for doc in cursor:
                        line = bson_dumps(doc, ensure_ascii=False).encode("utf-8") + b"\n"
                        entry.write(line)
                        part_hash.update(line)
                        part_count += 1
                        count += 1
                        seg_state["bytes"] += len(line)
                        del doc, line
                        # Corte de segmento: cerrar parte y segmento; continuar la
                        # misma colección en un segmento nuevo (parte siguiente).
                        if seg_state["bytes"] >= SEGMENT_MAX_BYTES:
                            entry.close()
                            seg_state["parts"].append({
                                "collection": cname, "part": part_index,
                                "count": part_count, "sha256": part_hash.hexdigest(),
                            })
                            _finalize_segment(container)
                            _new_segment()
                            part_index += 1
                            part_name = f"collections/{cname}.part{part_index:04d}.jsonl"
                            entry = seg_state["zf"].open(part_name, "w")
                            part_count = 0
                            part_hash = hashlib.sha256()
                finally:
                    cursor.close()
                entry.close()
                seg_state["parts"].append({
                    "collection": cname, "part": part_index,
                    "count": part_count, "sha256": part_hash.hexdigest(),
                })
                col_counts.append({"name": cname, "count": count})
                done_cols += 1
                sdb.backup_jobs.update_one(
                    {"job_id": job_id},
                    {"$set": {"progress_collections": done_cols, "total_collections": len(cols)}},
                )
            _finalize_segment(container)
            manifest["collections"] = col_counts
            manifest["total_collections"] = len(col_counts)
            manifest["total_documents"] = sum(c["count"] for c in col_counts)
            container.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        grid_in.close()  # finaliza el archivo GridFS
        closed = True
        gridfs_id = grid_in._id
        fdoc = sdb[f"{_BACKUP_BUCKET}.files"].find_one({"_id": gridfs_id}) or {}
        size_bytes = int(fdoc.get("length", 0))
        sdb.backup_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "ready",
                "gridfs_id": gridfs_id,
                "filename": filename,
                "size_bytes": size_bytes,
                "collections": len(cols),
                "manifest_collections": manifest["collections"],
                "exported_at": manifest["exported_at"],
                "schema_version": 2,
                "segments": len(manifest["segments"]),
                "excluded_masters": manifest["excluded_masters"],
                "ready_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        try:
            sdb.bitacora.insert_one({
                "action": "full_backup_export",
                "db_name": db_name,
                "collections": len(cols),
                "size_bytes": size_bytes,
                "executed_by": user.get("email"),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
    except Exception as e:  # noqa: BLE001
        logger.error(f"[full-backup] build job {job_id} fallo: {e}")
        # descartar el artefacto parcial
        try:
            if not closed:
                grid_in.abort()
            elif getattr(grid_in, "_id", None) is not None:
                bucket.delete(grid_in._id)
        except Exception:
            pass
        try:
            sdb.backup_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "error", "error": str(e)}},
            )
        except Exception:
            pass
    finally:
        try:
            sclient.close()
        except Exception:
            pass


async def _run_build_in_thread(job_id: str, user: dict, db_name: str, only_collections=None, group_label=None):
    """Lanza el build síncrono en un hilo del executor (no bloquea el loop)."""
    try:
        await asyncio.to_thread(_build_full_backup_sync, job_id, user, db_name, only_collections, group_label)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[full-backup] thread wrapper job {job_id} fallo: {e}")
        try:
            await db.backup_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "error", "error": str(e)}},
            )
        except Exception:
            pass


def _compute_backup_groups_sync(db_name: str, target_bytes: int = 80 * 1024 * 1024):
    """Calcula grupos MODULARES por tamaño: cada colección grande (> target) queda
    en su propio grupo; las pequeñas se empaquetan (first-fit decreasing) en grupos
    equilibrados ≤ target. Excluye las 12 maestras (rutina propia) y las internas."""
    from pymongo import MongoClient
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    try:
        cols = [c for c in sorted(sdb.list_collection_names())
                if c not in _BACKUP_EXCLUDE and c not in _MASTER_EXCLUDE]
        sized = []
        for c in cols:
            try:
                st = sdb.command("collStats", c)
                size = int(st.get("size", 0))  # tamaño BSON sin comprimir
                count = int(st.get("count", 0))
            except Exception:
                size, count = 0, sdb[c].estimated_document_count()
            sized.append({"name": c, "size": size, "count": count})
        sized.sort(key=lambda x: x["size"], reverse=True)

        big = [c for c in sized if c["size"] > target_bytes]
        small = [c for c in sized if c["size"] <= target_bytes]

        groups = []
        for c in big:
            groups.append({"collections": [c], "size": c["size"]})
        # first-fit decreasing para las pequeñas
        bins = []
        for c in small:
            placed = False
            for b in bins:
                if b["size"] + c["size"] <= target_bytes:
                    b["collections"].append(c)
                    b["size"] += c["size"]
                    placed = True
                    break
            if not placed:
                bins.append({"collections": [c], "size": c["size"]})
        groups.extend(bins)

        result = []
        for i, g in enumerate(groups, start=1):
            names = [c["name"] for c in g["collections"]]
            if len(names) == 1:
                label = names[0]
            else:
                label = f"grupo_{i:02d}"
            result.append({
                "group_id": f"g{i:02d}",
                "label": label,
                "is_large_isolated": len(names) == 1 and g["size"] > target_bytes,
                "est_size_bytes": g["size"],
                "collections": [{"name": c["name"], "size_bytes": c["size"], "count": c["count"]} for c in g["collections"]],
            })
        return {"target_bytes": target_bytes, "total_groups": len(result), "groups": result}
    finally:
        sclient.close()


@router.get("/admin/full-backup/groups")
async def full_backup_groups(authorization: Optional[str] = Header(None)):
    """Devuelve los grupos MODULARES calculados por tamaño (para respaldar/restaurar
    por grupos independientes). Las 12 maestras van por su rutina propia."""
    await _require_admin(authorization)
    return await asyncio.to_thread(_compute_backup_groups_sync, db.name)


@router.post("/admin/full-backup/build")
async def full_backup_build(
    collections: Optional[str] = Form(None),
    group_label: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Inicia el armado en 2º plano. Sin `collections` → Respaldo Total (menos las
    12 maestras). Con `collections` (JSON array) → respaldo MODULAR de ese grupo,
    etiquetado con `group_label` (cada grupo es un .zip independiente reutilizable
    con el mismo motor de restauración V2). Devuelve job_id para sondear."""
    user = await _require_admin(authorization)
    await _cleanup_stale_backups()

    only_collections = None
    if collections:
        try:
            parsed = json.loads(collections)
            if isinstance(parsed, list):
                only_collections = [str(x) for x in parsed if str(x).strip()]
        except Exception:
            only_collections = [c.strip() for c in collections.split(",") if c.strip()]

    # Borrar solo el respaldo previo del MISMO alcance (total vs. este grupo)
    scope_filter = {"user_id": user.get("user_id"), "group_label": group_label}
    try:
        async for prev in db.backup_jobs.find(scope_filter):
            await _delete_backup_gridfs(prev.get("gridfs_id"))
            await db.backup_jobs.delete_one({"_id": prev["_id"]})
    except Exception:
        pass

    job_id = uuid.uuid4().hex
    total_cols = len(only_collections) if only_collections else len(await db.list_collection_names())
    await db.backup_jobs.insert_one({
        "job_id": job_id,
        "status": "building",
        "user_id": user.get("user_id"),
        "user_email": user.get("email"),
        "group_label": group_label,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress_collections": 0,
        "total_collections": total_cols,
        "gridfs_id": None,
        "filename": None,
        "size_bytes": None,
        "error": None,
    })
    user_min = {
        "email": user.get("email"),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
    }
    asyncio.create_task(_run_build_in_thread(job_id, user_min, db.name, only_collections, group_label))
    return {"job_id": job_id, "status": "building", "total_collections": total_cols, "group_label": group_label}


@router.get("/admin/full-backup/build-status")
async def full_backup_build_status(job_id: str, authorization: Optional[str] = Header(None)):
    """Estado del armado del Respaldo Total (building | ready | error)."""
    await _require_admin(authorization)
    job = await db.backup_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job de respaldo no encontrado o expirado")
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "ready": job.get("status") == "ready",
        "size_bytes": job.get("size_bytes"),
        "filename": job.get("filename"),
        "collections": job.get("collections"),
        "progress_collections": job.get("progress_collections", 0),
        "total_collections": job.get("total_collections", 0),
        "error": job.get("error"),
    }


@router.post("/admin/full-backup/export-ticket")
async def full_backup_export_ticket(
    payload: dict = Body(default=None),
    authorization: Optional[str] = Header(None),
):
    """Genera un ticket de descarga de un solo uso (5 min) para disparar la
    descarga NATIVA del navegador (un <a> no puede enviar Authorization).
    Debe indicarse el job_id de un respaldo ya listo (status=ready)."""
    user = await _require_admin(authorization)
    job_id = (payload or {}).get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="Falta job_id del respaldo")
    job = await db.backup_jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job de respaldo no encontrado o expirado")
    if job.get("status") != "ready":
        raise HTTPException(status_code=409, detail="El respaldo aún no está listo")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.download_tickets.insert_one({
        "token": token,
        "purpose": "full-backup-export",
        "job_id": job_id,
        "user_id": user.get("user_id"),
        "user_email": user.get("email"),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    })
    return {"ticket": token}


@router.get("/admin/full-backup/export")
async def full_backup_export(
    authorization: Optional[str] = Header(None),
    ticket: Optional[str] = None,
    job_id: Optional[str] = None,
):
    """Sirve el ZIP del Respaldo Total YA ARMADO (por /build) haciendo STREAMING
    desde GridFS (almacenamiento COMPARTIDO entre réplicas) con Content-Length
    real → cualquier réplica lo sirve, sin 524 ni truncado por el CDN, y memoria
    O(1). Auth por header (Authorization + job_id) o por `ticket` (descarga
    nativa del navegador)."""
    resolved_job_id = None
    if ticket:
        ticket_doc = await db.download_tickets.find_one({"token": ticket, "purpose": "full-backup-export"})
        if not ticket_doc:
            raise HTTPException(status_code=401, detail="Ticket de descarga inválido")
        try:
            expired = datetime.fromisoformat(ticket_doc["expires_at"]) < datetime.now(timezone.utc)
        except Exception:
            expired = True
        if expired:
            await db.download_tickets.delete_one({"_id": ticket_doc["_id"]})
            raise HTTPException(status_code=401, detail="Ticket de descarga expirado")
        u = await db.users.find_one({"user_id": ticket_doc.get("user_id")})
        if not u or u.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Solo administradores")
        resolved_job_id = ticket_doc.get("job_id")
    elif authorization:
        await _require_admin(authorization)
        resolved_job_id = job_id
    else:
        raise HTTPException(status_code=401, detail="No autorizado")

    if not resolved_job_id:
        raise HTTPException(status_code=400, detail="Falta job_id del respaldo")
    job = await db.backup_jobs.find_one({"job_id": resolved_job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado o expirado")
    if job.get("status") != "ready":
        raise HTTPException(status_code=409, detail="El respaldo aún no está listo")

    gridfs_id = job.get("gridfs_id")
    if not gridfs_id:
        raise HTTPException(status_code=410, detail="El archivo de respaldo ya no está disponible; genera uno nuevo")
    try:
        grid_out = await _async_gridfs_bucket().open_download_stream(gridfs_id)
    except Exception:
        raise HTTPException(status_code=410, detail="El archivo de respaldo ya no está disponible; genera uno nuevo")

    length = grid_out.length
    filename = job.get("filename") or f"full_backup_{db.name}.zip"

    async def _iter():
        try:
            while True:
                chunk = await grid_out.readchunk()
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                await db.backup_jobs.update_one(
                    {"job_id": resolved_job_id},
                    {"$set": {"downloaded_at": datetime.now(timezone.utc).isoformat()}},
                )
            except Exception:
                pass

    headers = {
        "Content-Length": str(length),
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(_iter(), media_type="application/zip", headers=headers)



@router.get("/admin/full-backup/collection")
async def full_backup_collection_page(
    name: str,
    after: Optional[str] = None,
    max_docs: int = 1000,
    authorization: Optional[str] = Header(None),
):
    """Devuelve una PÁGINA de documentos de una colección en Extended JSON,
    para ensamblar el ZIP en el navegador (evita cargar toda la base en el pod).
    Paginación por _id (índice nativo). El cuerpo es Extended-JSON separado por
    comas (sin corchetes); el cliente los concatena y envuelve en [ ... ].
    Memoria del pod por request: acotada (~pocos MB)."""
    await _require_admin(authorization)
    MAX_BYTES = 8 * 1024 * 1024  # cortar la página al superar ~8MB (menos requests, memoria del pod acotada)
    max_docs = max(1, min(int(max_docs or 1000), 20000))

    q = {}
    if after:
        try:
            q = {"_id": {"$gt": bson_loads(after)}}
        except Exception:
            raise HTTPException(status_code=400, detail="cursor 'after' inválido")

    cursor = db[name].find(q).sort("_id", 1).batch_size(20)
    parts = []
    last_id = None
    n = 0
    nbytes = 0
    stopped_early = False
    async for doc in cursor:
        last_id = doc.get("_id")
        s = bson_dumps(doc, ensure_ascii=False)
        parts.append(s)
        n += 1
        nbytes += len(s)
        if n >= max_docs or nbytes >= MAX_BYTES:
            stopped_early = True
            break

    has_more = False
    next_after = ""
    if stopped_early and last_id is not None:
        nxt = await db[name].find_one({"_id": {"$gt": last_id}}, {"_id": 1})
        has_more = nxt is not None
        if has_more:
            next_after = bson_dumps(last_id)

    body = ",".join(parts)
    headers = {
        "X-Has-More": "1" if has_more else "0",
        "X-Next-After": next_after,
        "X-Count": str(n),
        "Cache-Control": "no-store",
    }
    return Response(content=body, media_type="text/plain; charset=utf-8", headers=headers)


@router.post("/admin/full-backup/upload-init")
async def full_backup_upload_init(authorization: Optional[str] = Header(None)):
    """Inicia una carga por chunks. Devuelve un upload_id. Los chunks se guardan
    en Mongo (almacenamiento compartido entre réplicas), no en /tmp del pod."""
    await _require_admin(authorization)
    upload_id = uuid.uuid4().hex
    await db.fb_uploads.insert_one({
        "upload_id": upload_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assembled_gridfs_id": None,
    })
    return {"upload_id": upload_id}


@router.post("/admin/full-backup/upload-chunk")
async def full_backup_upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(0),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Guarda un chunk del ZIP en Mongo (fb_upload_chunks). Idempotente por
    (upload_id, chunk_index)."""
    await _require_admin(authorization)
    up = await db.fb_uploads.find_one({"upload_id": upload_id})
    if not up:
        raise HTTPException(status_code=404, detail="upload_id no encontrado (inicia la carga primero)")
    data = await file.read()
    await db.fb_upload_chunks.update_one(
        {"upload_id": upload_id, "chunk_index": chunk_index},
        {"$set": {"data": data}},
        upsert=True,
    )
    return {"ok": True, "chunk_index": chunk_index, "received_bytes": len(data)}


@router.post("/admin/full-backup/upload-manifest")
async def full_backup_upload_manifest(
    upload_id: str = Form(...),
    authorization: Optional[str] = Header(None),
):
    """Ensambla el ZIP subido (chunks Mongo → GridFS) y el SERVIDOR lee su
    manifiesto (sin JSZip en el navegador). Soporta V1 (`_manifest.json`) y V2
    (`backup_manifest.json`). Memoria O(1)."""
    await _require_admin(authorization)
    gid = await asyncio.to_thread(_assemble_upload_to_gridfs_sync, upload_id, db.name)
    result = await asyncio.to_thread(_read_backup_manifest_sync, gid, db.name)
    return result


def _read_backup_manifest_sync(gridfs_id, db_name: str) -> dict:
    """Lee el manifiesto (V1/V2) desde un ZIP en GridFS. Memoria O(1)."""
    from pymongo import MongoClient
    from bson import ObjectId
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    stream = None
    try:
        stream = _sync_gridfs_bucket(sdb).open_download_stream(ObjectId(gridfs_id))
        size_bytes = getattr(stream, "length", None)
        zf = zipfile.ZipFile(stream)
        names = zf.namelist()
        if "backup_manifest.json" in names:
            manifest = json.loads(zf.read("backup_manifest.json"))
            cols = manifest.get("collections") or []
            return {
                "schema_version": manifest.get("schema_version", 2),
                "db_name": manifest.get("db_name"),
                "exported_at": manifest.get("exported_at"),
                "exported_by": manifest.get("exported_by"),
                "excluded_masters": manifest.get("excluded_masters", []),
                "segments": len(manifest.get("segments", [])),
                "size_bytes": size_bytes,
                "collections": cols,
            }
        if "_manifest.json" in names:
            manifest = json.loads(zf.read("_manifest.json"))
            if manifest.get("type") != "full-database-backup":
                raise HTTPException(status_code=400, detail="El archivo no es un Respaldo Total de Base de Datos")
            cols = manifest.get("collections") or []
            if not cols:
                col_files = [n for n in names if n.startswith("collections/") and n.endswith(".json")]
                cols = [{"name": n[len("collections/"):-len(".json")], "count": None} for n in col_files]
            return {
                "schema_version": 1,
                "db_name": manifest.get("db_name"),
                "exported_at": manifest.get("exported_at"),
                "exported_by": manifest.get("exported_by"),
                "excluded_masters": [],
                "segments": 0,
                "size_bytes": size_bytes,
                "collections": cols,
            }
        raise HTTPException(status_code=400, detail="El archivo no es un Respaldo Total (falta el manifiesto)")
    finally:
        try:
            if stream is not None:
                stream.close()
        except Exception:
            pass
        sclient.close()


def _rjob_update(sdb, job_id, **fields):
    """Actualiza el documento de progreso de restauración (checkpoints)."""
    if not job_id:
        return
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        sdb.restore_jobs.update_one({"job_id": job_id}, {"$set": fields})
    except Exception:
        pass


def _restore_full_backup_sync(path, mode: str, selected, selective: bool, caller_token, user: dict, db_name: str, gridfs_id=None, job_id=None) -> dict:
    """Restaura la BD desde el ZIP usando pymongo SÍNCRONO en un HILO aparte.
    Detecta el formato:
      - V2 SEGMENTADO (`backup_manifest.json`): valida el checksum de TODOS los
        segmentos antes de inyectar; restaura segmento por segmento liberando
        memoria; soporta checkpoints/reanudación vía `restore_jobs`.
      - V1 MONOLÍTICO (`collections/<x>.json`): compatibilidad hacia atrás.
    Fuente del ZIP: `gridfs_id` (stream buscable desde GridFS) o `path` (disco)."""
    from pymongo import MongoClient
    from bson.json_util import loads as _loads

    BATCH = 5000
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    summary = []
    backup_cols = set()
    dropped_extra = []
    zip_source = None
    try:
        if gridfs_id is not None:
            from bson import ObjectId
            gid = gridfs_id if isinstance(gridfs_id, ObjectId) else ObjectId(str(gridfs_id))
            zip_source = _sync_gridfs_bucket(sdb).open_download_stream(gid)
            zf = zipfile.ZipFile(zip_source)
        else:
            zf = zipfile.ZipFile(path)
        names = zf.namelist()

        if "backup_manifest.json" in names:
            # ==================== V2 SEGMENTADO ====================
            manifest = json.loads(zf.read("backup_manifest.json"))
            segments = manifest.get("segments", [])
            for c in manifest.get("collections", []):
                backup_cols.add(c["name"])

            # 1) Validación de integridad (checksums) de TODOS los segmentos
            #    ANTES de iniciar la inyección de datos.
            _rjob_update(sdb, job_id, status="validating", total_segments=len(segments),
                         message="Validando integridad de segmentos…")
            for seg in segments:
                data = zf.read(seg["filename"])
                if hashlib.sha256(data).hexdigest() != seg.get("sha256"):
                    raise ValueError(f"Checksum inválido en {seg['filename']}: respaldo corrupto o incompleto")
                del data
            gc.collect()

            # 2) Restauración secuencial e idempotente con checkpoints.
            rjob = sdb.restore_jobs.find_one({"job_id": job_id}) if job_id else None
            completed = set((rjob or {}).get("completed_segments", []))
            started = set((rjob or {}).get("collections_started", []))
            restored_counts = {s["name"]: s["restored"] for s in (rjob or {}).get("summary", [])}
            _rjob_update(sdb, job_id, status="restoring", message="Restaurando segmentos…")
            for seg in segments:
                if seg["index"] in completed:
                    continue
                data = zf.read(seg["filename"])
                inner = zipfile.ZipFile(io.BytesIO(data))
                for part in seg.get("parts", []):
                    cname = part["collection"]
                    if selective and cname not in selected:
                        continue
                    coll = sdb[cname]
                    if cname not in started:
                        coll.drop()          # drop UNA sola vez por colección
                        started.add(cname)
                        restored_counts.setdefault(cname, 0)
                    pname = f"collections/{cname}.part{part['part']:04d}.jsonl"
                    inserted = 0
                    batch = []
                    with inner.open(pname) as fh:
                        for rawline in io.TextIOWrapper(fh, encoding="utf-8"):
                            line = rawline.strip()
                            if not line:
                                continue
                            batch.append(_loads(line))
                            if len(batch) >= BATCH:
                                coll.insert_many(batch, ordered=False, bypass_document_validation=True)
                                inserted += len(batch)
                                batch = []
                        if batch:
                            coll.insert_many(batch, ordered=False, bypass_document_validation=True)
                            inserted += len(batch)
                    restored_counts[cname] = restored_counts.get(cname, 0) + inserted
                completed.add(seg["index"])
                del data, inner
                gc.collect()
                # Mantener viva la sesión del operador entre segmentos: la
                # restauración de `user_sessions` borraría su token; lo re-insertamos
                # (idempotente) para que el sondeo de progreso no reciba 401.
                if caller_token and user.get("user_id"):
                    try:
                        sdb.user_sessions.update_one(
                            {"session_token": caller_token},
                            {"$setOnInsert": {
                                "user_id": user["user_id"],
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "restored_after_full_backup": True,
                            }},
                            upsert=True,
                        )
                    except Exception:
                        pass
                _rjob_update(sdb, job_id,
                             completed_segments=sorted(completed),
                             collections_started=sorted(started),
                             progress_segments=len(completed),
                             summary=[{"name": k, "restored": v} for k, v in restored_counts.items()])
            summary = [{"name": k, "restored": v} for k, v in restored_counts.items()]

            if mode == "replace" and not selective:
                # BORRADO DE SOBRANTES (réplica exacta destructiva): SOLO se permite
                # para un Respaldo TOTAL marcado explícitamente (is_partial == False).
                # Un respaldo MODULAR/parcial (por grupo) o de formato antiguo (sin
                # marca) NUNCA elimina colecciones ausentes del ZIP: así, restaurar un
                # grupo jamás blanquea las colecciones de los demás grupos.
                is_total_backup = (manifest.get("is_partial") is False) and not manifest.get("group_label")
                if is_total_backup:
                    protected = backup_cols | _BACKUP_EXCLUDE | _MASTER_EXCLUDE | _LOGIN_PROTECT
                    for cname in sdb.list_collection_names():
                        if cname not in protected:
                            sdb[cname].drop()
                            dropped_extra.append(cname)
        else:
            # ==================== V1 MONOLÍTICO (compatibilidad) ====================
            col_files = [n for n in names if n.startswith("collections/") and n.endswith(".json")]
            for n in col_files:
                cname = n[len("collections/"):-len(".json")]
                backup_cols.add(cname)
                if selective and cname not in selected:
                    continue
                coll = sdb[cname]
                coll.drop()
                inserted = 0
                batch = []
                used_fallback = False
                try:
                    with zf.open(n) as fh:
                        for rawline in io.TextIOWrapper(fh, encoding="utf-8"):
                            line = rawline.strip()
                            if not line or line == "[" or line == "]":
                                continue
                            if line.endswith(","):
                                line = line[:-1].rstrip()
                            if not line:
                                continue
                            try:
                                doc = _loads(line)
                            except Exception:
                                used_fallback = True
                                break
                            batch.append(doc)
                            if len(batch) >= BATCH:
                                coll.insert_many(batch, ordered=False, bypass_document_validation=True)
                                inserted += len(batch)
                                batch = []
                        if not used_fallback and batch:
                            coll.insert_many(batch, ordered=False, bypass_document_validation=True)
                            inserted += len(batch)
                            batch = []
                except Exception:
                    used_fallback = True
                if used_fallback:
                    coll.drop()
                    inserted = 0
                    raw = zf.read(n).decode("utf-8")
                    docs = _loads(raw) if raw.strip() else []
                    for i in range(0, len(docs), BATCH):
                        b = docs[i:i + BATCH]
                        if b:
                            coll.insert_many(b, ordered=False, bypass_document_validation=True)
                            inserted += len(b)
                summary.append({"name": cname, "restored": inserted})

            if mode == "replace" and not selective:
                protected = backup_cols | _LOGIN_PROTECT
                for cname in sdb.list_collection_names():
                    if cname not in protected:
                        sdb[cname].drop()
                        dropped_extra.append(cname)

        session_preserved = False
        if caller_token and user.get("user_id"):
            try:
                if sdb.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "user_id": 1}) and \
                        not sdb.user_sessions.find_one({"session_token": caller_token}):
                    sdb.user_sessions.insert_one({
                        "user_id": user["user_id"],
                        "session_token": caller_token,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "restored_after_full_backup": True,
                    })
                    session_preserved = True
            except Exception:
                pass

        return {
            "summary": summary,
            "backup_cols": sorted(backup_cols),
            "dropped_extra": dropped_extra,
            "session_preserved": session_preserved,
        }
    finally:
        try:
            if zip_source is not None:
                zip_source.close()
        except Exception:
            pass
        try:
            sclient.close()
        except Exception:
            pass


def _run_restore_job_sync(restore_job_id, mode, selected, selective, caller_token, user_min, db_name, gridfs_id):
    """Ejecuta la restauración (V1/V2) escribiendo checkpoints en restore_jobs.
    En error deja el job como 'error' (reanudable); en éxito lo marca 'ready'."""
    from pymongo import MongoClient
    sclient = MongoClient(os.environ["MONGO_URL"])
    sdb = sclient[db_name]
    try:
        result = _restore_full_backup_sync(
            None, mode, selected, selective, caller_token, user_min, db_name, gridfs_id, job_id=restore_job_id
        )
        summary = result["summary"]
        backup_cols = set(result["backup_cols"])
        skipped = sorted(selected - backup_cols) if selective else []
        sdb.restore_jobs.update_one({"job_id": restore_job_id}, {"$set": {
            "status": "ready",
            "summary": summary,
            "restored_collections": len(summary),
            "restored_documents": sum(s["restored"] for s in summary),
            "dropped_extra": result["dropped_extra"],
            "skipped_collections": skipped,
            "session_preserved": result["session_preserved"],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }})
    except Exception as e:  # noqa: BLE001
        logger.error(f"[full-restore] job {restore_job_id} fallo: {e}")
        sdb.restore_jobs.update_one({"job_id": restore_job_id}, {"$set": {"status": "error", "error": str(e)}})
    finally:
        sclient.close()


async def _launch_restore_job(restore_job_id):
    """Lanza el runner en un hilo. Limpia el buffer de subida SOLO si terminó
    con éxito (para permitir reanudar en caso de error)."""
    job = await db.restore_jobs.find_one({"job_id": restore_job_id})
    if not job:
        return
    selected = set(job.get("selected") or []) or None
    await asyncio.to_thread(
        _run_restore_job_sync, restore_job_id, job.get("mode"), selected,
        bool(job.get("selective")), job.get("caller_token"),
        {"user_id": job.get("user_id"), "email": job.get("email")},
        db.name, job.get("gridfs_id"),
    )
    final = await db.restore_jobs.find_one({"job_id": restore_job_id})
    if final and final.get("status") == "ready":
        await db.bitacora.insert_one({
            "action": "full_backup_restore",
            "source": job.get("source"),
            "mode": job.get("mode"),
            "selective": bool(job.get("selective")),
            "source_exported_at": job.get("source_exported_at"),
            "restored_collections": final.get("restored_collections"),
            "executed_by": job.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
        if job.get("upload_id"):
            try:
                await asyncio.to_thread(_cleanup_upload_sync, job.get("upload_id"), db.name)
            except Exception:
                pass


async def _create_and_start_restore(*, source, gridfs_id, mode, collections, user, caller_token,
                                     upload_id=None, source_exported_at=None, source_label=None):
    selected = None
    if collections:
        try:
            parsed = json.loads(collections)
            if isinstance(parsed, list):
                selected = [str(x) for x in parsed if str(x).strip()]
        except Exception:
            selected = [c.strip() for c in collections.split(",") if c.strip()]
    selective = bool(selected)
    restore_job_id = uuid.uuid4().hex
    await db.restore_jobs.insert_one({
        "job_id": restore_job_id,
        "status": "queued",
        "source": source,
        "gridfs_id": gridfs_id,
        "upload_id": upload_id,
        "mode": mode,
        "selective": selective,
        "selected": selected,
        "caller_token": caller_token,
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "source_exported_at": source_exported_at,
        "source_label": source_label,
        "completed_segments": [],
        "collections_started": [],
        "summary": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    asyncio.create_task(_launch_restore_job(restore_job_id))
    return restore_job_id


@router.post("/admin/full-backup/restore")
async def full_backup_restore(
    upload_id: str = Form(...),
    mode: str = Form("replace"),
    collections: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Restaura desde el ZIP subido por chunks (ensamblado a GridFS). Arranca un
    job ASÍNCRONO (con checkpoints/reanudación) y devuelve restore_job_id para
    sondear el progreso. Soporta formato V1 (monolítico) y V2 (segmentado)."""
    user = await _require_admin(authorization)
    caller_token = authorization.replace("Bearer ", "").strip() if authorization else None
    gid = await asyncio.to_thread(_assemble_upload_to_gridfs_sync, upload_id, db.name)
    meta = await asyncio.to_thread(_read_backup_manifest_sync, gid, db.name)
    restore_job_id = await _create_and_start_restore(
        source="file-upload", gridfs_id=gid, mode=mode, collections=collections,
        user=user, caller_token=caller_token, upload_id=upload_id,
        source_exported_at=meta.get("exported_at"), source_label=meta.get("db_name"),
    )
    return {"status": "started", "restore_job_id": restore_job_id, "schema_version": meta.get("schema_version")}


@router.get("/admin/full-backup/restore-status")
async def full_backup_restore_status(job_id: str, authorization: Optional[str] = Header(None)):
    """Estado/progreso de una restauración asíncrona (para sondeo desde la UI)."""
    await _require_admin(authorization)
    job = await db.restore_jobs.find_one(
        {"job_id": job_id},
        {"_id": 0, "caller_token": 0, "gridfs_id": 0},
    )
    if not job:
        raise HTTPException(status_code=404, detail="Restauración no encontrada")
    return job


@router.post("/admin/full-backup/restore-resume")
async def full_backup_restore_resume(job_id: str = Form(...), authorization: Optional[str] = Header(None)):
    """Reanuda una restauración interrumpida desde el último segmento válido
    (checkpoints). Reutiliza el mismo ZIP en GridFS y omite segmentos completados."""
    await _require_admin(authorization)
    job = await db.restore_jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Restauración no encontrada")
    if job.get("status") == "ready":
        return {"status": "ready", "message": "La restauración ya había finalizado."}
    if not job.get("gridfs_id"):
        raise HTTPException(status_code=400, detail="No se puede reanudar: el respaldo fuente ya no está disponible.")
    await db.restore_jobs.update_one({"job_id": job_id}, {"$set": {"status": "queued", "error": None}})
    asyncio.create_task(_launch_restore_job(job_id))
    return {"status": "resumed", "restore_job_id": job_id}




@router.get("/admin/full-backup/latest")
async def full_backup_latest(authorization: Optional[str] = Header(None)):
    """Devuelve el último respaldo LISTO del usuario que sigue disponible en el
    servidor (GridFS), con su lista de colecciones — para restaurar SIN subir el
    archivo ni leerlo con JSZip en el navegador."""
    user = await _require_admin(authorization)
    job = await db.backup_jobs.find_one(
        {"user_id": user.get("user_id"), "status": "ready", "gridfs_id": {"$ne": None}},
        {"_id": 0},
        sort=[("ready_at", -1)],
    )
    if not job:
        return {"available": False}
    return {
        "available": True,
        "job_id": job.get("job_id"),
        "filename": job.get("filename"),
        "size_bytes": job.get("size_bytes"),
        "exported_at": job.get("exported_at") or job.get("ready_at"),
        "collections": job.get("manifest_collections") or [],
        "db_name": db.name,
    }


@router.post("/admin/full-backup/restore-from-server")
async def full_backup_restore_from_server(
    job_id: str = Form(...),
    mode: str = Form("merge"),
    collections: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """Restaura DIRECTO desde un respaldo ya guardado en el servidor (GridFS).
    Arranca un job ASÍNCRONO (con checkpoints/reanudación) y devuelve
    restore_job_id para sondear el progreso. Soporta V1 y V2 (segmentado)."""
    user = await _require_admin(authorization)
    caller_token = authorization.replace("Bearer ", "").strip() if authorization else None

    job = await db.backup_jobs.find_one({"job_id": job_id})
    if not job or job.get("status") != "ready" or not job.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Respaldo del servidor no encontrado o expirado; genera uno nuevo")

    restore_job_id = await _create_and_start_restore(
        source="server-gridfs", gridfs_id=job.get("gridfs_id"), mode=mode, collections=collections,
        user=user, caller_token=caller_token, upload_id=None,
        source_exported_at=job.get("exported_at"), source_label=job.get("filename"),
    )
    return {"status": "started", "restore_job_id": restore_job_id, "schema_version": job.get("schema_version", 1)}

