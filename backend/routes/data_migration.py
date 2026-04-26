"""
Data Migration: Export/Import de catálogos maestros entre ambientes (Preview ↔ Deploy).
Solo administradores. Formato JSON consistente entre export e import.

Módulos soportados:
  - banks                 → collection 'banks'                 (key: bank_id)
  - payment-methods       → collection 'services'              (key: service_id)
  - hardware              → collection 'hardware'              (key: hardware_id)
  - commercial-categories → collection 'commercial_categories' (key: category_id)
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from config import db, get_current_user

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
