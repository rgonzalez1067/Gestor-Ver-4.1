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
import gc
import os
import secrets
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from bson.json_util import dumps as bson_dumps, loads as bson_loads
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form
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

def _fb_upload_path(upload_id: str) -> str:
    safe = "".join(ch for ch in (upload_id or "") if ch.isalnum() or ch in "-_")
    if not safe:
        raise HTTPException(status_code=400, detail="upload_id inválido")
    return os.path.join(tempfile.gettempdir(), f"fb_upload_{safe}.zip")


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
    """File-like NO buscable para escribir un ZIP en streaming (zipfile usa
    data descriptors). Acumula bytes que se drenan y envían por la respuesta."""
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


@router.post("/admin/full-backup/export-ticket")
async def full_backup_export_ticket(authorization: Optional[str] = Header(None)):
    """Genera un ticket de descarga de corta vida (5 min) para poder disparar
    el export como descarga NATIVA del navegador (streaming a disco), ya que un
    <a>/window.location no puede enviar el header Authorization."""
    user = await _require_admin(authorization)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.download_tickets.insert_one({
        "token": token,
        "purpose": "full-backup-export",
        "user_id": user.get("user_id"),
        "user_email": user.get("email"),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    })
    return {"ticket": token}


@router.get("/admin/full-backup/export")
async def full_backup_export(authorization: Optional[str] = Header(None), ticket: Optional[str] = None):
    """Exporta TODA la base de datos a un ZIP en STREAMING (un JSON Extended por
    colección). Envía bytes desde el primer instante y de forma continua, con
    memoria acotada (un documento a la vez), para evitar timeouts del proxy/CDN
    en bases grandes. Acepta auth por header (Authorization) o por `ticket` de
    descarga de corta vida (para descargas nativas del navegador)."""
    if authorization:
        user = await _require_admin(authorization)
    elif ticket:
        doc = await db.download_tickets.find_one({"token": ticket, "purpose": "full-backup-export"})
        if not doc:
            raise HTTPException(status_code=401, detail="Ticket de descarga inválido")
        # un solo uso
        await db.download_tickets.delete_one({"_id": doc["_id"]})
        try:
            expired = datetime.fromisoformat(doc["expires_at"]) < datetime.now(timezone.utc)
        except Exception:
            expired = True
        if expired:
            raise HTTPException(status_code=401, detail="Ticket de descarga expirado")
        user = await db.users.find_one({"user_id": doc.get("user_id")})
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Solo administradores")
    else:
        raise HTTPException(status_code=401, detail="No autorizado")
    cols = sorted(await db.list_collection_names())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"full_backup_{db.name}_{ts}.zip"

    # El ZIP se ESCRIBE A DISCO (archivo temporal) documento por documento y
    # luego se sirve con FileResponse (Content-Length real). Antes se enviaba
    # en streaming por trozos SIN Content-Length (chunked), y el CDN/ingress de
    # producción truncaba el último tramo (el "central directory" del ZIP),
    # dejando el archivo dañado ("Unexpected end of archive") aunque pesara
    # cientos de MB. Con un archivo en disco + tamaño declarado, el proxy no
    # puede truncarlo y la memoria del pod se mantiene baja (un doc a la vez).
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="full_backup_")
    os.close(tmp_fd)

    manifest = {
        "schema_version": 1,
        "type": "full-database-backup",
        "format": "mongodb-extended-json",
        "db_name": db.name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": user.get("email"),
        "exported_by_name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        "collections": [],
    }
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            _since_gc = 0
            for cname in cols:
                count = 0
                # batch_size chico → acota lo que el motor precarga en memoria
                cursor = db[cname].find({}).batch_size(50)
                with zf.open(f"collections/{cname}.json", "w") as entry:
                    entry.write(b"[")
                    first = True
                    async for doc in cursor:
                        piece = (b"" if first else b",") + b"\n" + bson_dumps(doc, ensure_ascii=False).encode("utf-8")
                        entry.write(piece)
                        del piece, doc
                        first = False
                        count += 1
                        _since_gc += 1
                        if _since_gc >= 2000:  # liberar memoria del intérprete periódicamente
                            gc.collect()
                            _since_gc = 0
                    entry.write(b"\n]" if count else b"]")
                manifest["collections"].append({"name": cname, "count": count})

            zf.writestr("_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        size_bytes = os.path.getsize(tmp_path)

        try:
            await db.bitacora.insert_one({
                "action": "full_backup_export",
                "db_name": db.name,
                "collections": len(cols),
                "size_bytes": size_bytes,
                "executed_by": user.get("email"),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

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
            "Cache-Control": "no-store",
            "X-Total-Collections": str(len(cols)),
            "X-Content-Type-Options": "nosniff",
        },
        background=BackgroundTask(_cleanup, tmp_path),
    )


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
    """Inicia una carga por chunks. Devuelve un upload_id."""
    await _require_admin(authorization)
    upload_id = uuid.uuid4().hex
    open(_fb_upload_path(upload_id), "wb").close()
    return {"upload_id": upload_id}


@router.post("/admin/full-backup/upload-chunk")
async def full_backup_upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(0),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Anexa un chunk del ZIP al archivo temporal (los chunks llegan en orden)."""
    await _require_admin(authorization)
    path = _fb_upload_path(upload_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="upload_id no encontrado (inicia la carga primero)")
    data = await file.read()
    with open(path, "ab") as f:
        f.write(data)
    return {"ok": True, "chunk_index": chunk_index, "received_bytes": len(data), "total_bytes": os.path.getsize(path)}


@router.post("/admin/full-backup/restore")
async def full_backup_restore(
    upload_id: str = Form(...),
    mode: str = Form("replace"),  # "replace": además borra colecciones que no estén en el respaldo; "merge": solo reemplaza las presentes
    collections: Optional[str] = Form(None),  # JSON array de nombres → restauración SELECTIVA (solo esas)
    authorization: Optional[str] = Header(None),
):
    """Restaura la base de datos desde el ZIP subido por chunks.
    Cada colección se DROP + re-inserta => réplica exacta.
    Si se envía `collections` (subconjunto), restaura SOLO esas y nunca borra
    colecciones fuera de la selección. Preserva la sesión del admin."""
    user = await _require_admin(authorization)
    caller_token = authorization.replace("Bearer ", "").strip() if authorization else None

    # Parsear selección de colecciones (restauración selectiva)
    selected = None
    if collections:
        try:
            parsed = json.loads(collections)
            if isinstance(parsed, list):
                selected = {str(x) for x in parsed if str(x).strip()}
        except Exception:
            selected = {c.strip() for c in collections.split(",") if c.strip()}
    selective = bool(selected)

    path = _fb_upload_path(upload_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Respaldo subido no encontrado (¿expiró?)")

    try:
        zf = zipfile.ZipFile(path)
    except Exception:
        try:
            os.unlink(path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="El archivo subido no es un ZIP válido")

    names = zf.namelist()
    if "_manifest.json" not in names:
        raise HTTPException(status_code=400, detail="ZIP inválido: falta _manifest.json")
    try:
        manifest = json.loads(zf.read("_manifest.json"))
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer _manifest.json")
    if manifest.get("type") != "full-database-backup":
        raise HTTPException(status_code=400, detail="El archivo no es un Respaldo Total de Base de Datos")

    col_files = [n for n in names if n.startswith("collections/") and n.endswith(".json")]
    if not col_files:
        raise HTTPException(status_code=400, detail="El respaldo no contiene colecciones")

    backup_cols = set()
    summary = []
    skipped = []
    BATCH = 500
    for n in col_files:
        cname = n[len("collections/"):-len(".json")]
        backup_cols.add(cname)
        if selective and cname not in selected:
            continue  # restauración selectiva: no tocar colecciones fuera de la selección
        raw = zf.read(n).decode("utf-8")
        docs = bson_loads(raw) if raw.strip() else []
        await db[cname].drop()
        inserted = 0
        for i in range(0, len(docs), BATCH):
            batch = docs[i:i + BATCH]
            if batch:
                await db[cname].insert_many(batch, ordered=False)
                inserted += len(batch)
        summary.append({"name": cname, "restored": inserted})

    if selective:
        # Reportar colecciones pedidas que no existen en el respaldo
        skipped = sorted(selected - backup_cols)
        if not summary:
            raise HTTPException(status_code=400, detail="Ninguna de las colecciones seleccionadas existe en el respaldo")

    # El borrado de colecciones "extra" SOLO aplica en restauración COMPLETA
    # (no selectiva) y en modo "replace".
    dropped_extra = []
    if mode == "replace" and not selective:
        for cname in await db.list_collection_names():
            if cname not in backup_cols:
                await db[cname].drop()
                dropped_extra.append(cname)

    # Preservar la sesión del admin que ejecuta (si su usuario existe en el
    # respaldo restaurado) para no dejarlo fuera del sistema.
    session_preserved = False
    if caller_token and user.get("user_id"):
        try:
            user_exists = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "user_id": 1})
            if user_exists and not await db.user_sessions.find_one({"session_token": caller_token}):
                await db.user_sessions.insert_one({
                    "user_id": user["user_id"],
                    "session_token": caller_token,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "restored_after_full_backup": True,
                })
                session_preserved = True
        except Exception:
            pass

    try:
        await db.bitacora.insert_one({
            "action": "full_backup_restore",
            "mode": mode,
            "selective": selective,
            "selected_collections": sorted(selected) if selective else None,
            "source_db": manifest.get("db_name"),
            "source_exported_at": manifest.get("exported_at"),
            "restored_collections": len(summary),
            "dropped_extra_collections": dropped_extra,
            "executed_by": user.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    try:
        os.unlink(path)
    except Exception:
        pass

    return {
        "status": "ok",
        "selective": selective,
        "source_db": manifest.get("db_name"),
        "source_exported_at": manifest.get("exported_at"),
        "restored_collections": len(summary),
        "restored_documents": sum(s["restored"] for s in summary),
        "summary": summary,
        "skipped_collections": skipped,
        "dropped_extra_collections": dropped_extra,
        "session_preserved": session_preserved,
    }
