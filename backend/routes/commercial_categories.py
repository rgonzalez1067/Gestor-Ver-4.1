"""Route module: commercial_categories.py
Catálogo dinámico de Categorías Comerciales para clientes.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import re
import uuid
import logging

from config import db, get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


def _name_regex(name: str) -> dict:
    """Regex case-insensitive con escape de metacaracteres para evitar ReDoS / falsos matches."""
    return {"$regex": f"^{re.escape(name)}$", "$options": "i"}


class CommercialCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True


class CommercialCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/commercial-categories")
async def list_commercial_categories(
    only_active: bool = False,
    authorization: Optional[str] = Header(None),
):
    """Lista categorías comerciales. Por defecto devuelve todas (para el admin del catálogo).
    Pasar `only_active=true` para el dropdown de clientes (solo activas).
    """
    await get_current_user(authorization)
    query = {"is_active": True} if only_active else {}
    cats = await db.commercial_categories.find(query, {"_id": 0}).sort("name", 1).to_list(500)
    return cats


async def _categories_export_rows():
    cats = await db.commercial_categories.find({}, {"_id": 0}).sort("name", 1).to_list(500)
    headers = ['Nombre', 'Descripción', 'Estado']
    rows = []
    for c in cats:
        rows.append([
            c.get('name', ''),
            c.get('description', '') or '',
            'Activa' if c.get('is_active', True) else 'Inactiva',
        ])
    return headers, rows


@router.get("/commercial-categories/export/pdf")
async def export_commercial_categories_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    from fastapi.responses import StreamingResponse
    from services.pdf_report import build_corporate_pdf

    headers, rows = await _categories_export_rows()
    buffer = build_corporate_pdf(
        title="Categorías Comerciales",
        headers=headers, rows=rows,
        col_ratios=[2.4, 4.6, 1.2],
    )
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=categorias_comerciales.pdf"}
    )


@router.get("/commercial-categories/export/excel")
async def export_commercial_categories_excel(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    from fastapi.responses import StreamingResponse
    from services.pdf_report import build_xlsx

    headers, rows = await _categories_export_rows()
    buffer = build_xlsx(headers, rows, sheet_name="Categorías Comerciales")
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=categorias_comerciales.xlsx"}
    )


@router.get("/commercial-categories/export/csv")
async def export_commercial_categories_csv(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    from fastapi.responses import StreamingResponse
    from services.pdf_report import build_csv

    headers, rows = await _categories_export_rows()
    buffer = build_csv(headers, rows)
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=categorias_comerciales.csv"}
    )




@router.post("/commercial-categories")
async def create_commercial_category(
    payload: CommercialCategoryCreate,
    authorization: Optional[str] = Header(None),
):
    """Crea una nueva categoría comercial. Solo admin."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar el catálogo")

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")

    # Unicidad case-insensitive
    existing = await db.commercial_categories.find_one(
        {"name": _name_regex(name)},
        {"_id": 0, "category_id": 1},
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una categoría con ese nombre")

    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
    doc = {
        "category_id": f"cat_{uuid.uuid4().hex[:12]}",
        "name": name,
        "description": (payload.description or "").strip() or None,
        "is_active": bool(payload.is_active),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user_name,
        "updated_at": None,
        "updated_by": None,
    }
    await db.commercial_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/commercial-categories/{category_id}")
async def update_commercial_category(
    category_id: str,
    payload: CommercialCategoryUpdate,
    authorization: Optional[str] = Header(None),
):
    """Actualiza una categoría. Solo admin. Propaga el cambio de nombre a clientes."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar el catálogo")

    cat = await db.commercial_categories.find_one({"category_id": category_id}, {"_id": 0})
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    update_fields = {}
    old_name = cat["name"]
    new_name = None
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="El nombre no puede quedar vacío")
        if new_name.lower() != old_name.lower():
            dup = await db.commercial_categories.find_one(
                {"name": _name_regex(new_name), "category_id": {"$ne": category_id}},
                {"_id": 0, "category_id": 1},
            )
            if dup:
                raise HTTPException(status_code=409, detail="Ya existe otra categoría con ese nombre")
        update_fields["name"] = new_name
    if payload.description is not None:
        update_fields["description"] = payload.description.strip() or None
    if payload.is_active is not None:
        update_fields["is_active"] = bool(payload.is_active)

    if not update_fields:
        return cat

    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_fields["updated_by"] = user_name

    await db.commercial_categories.update_one(
        {"category_id": category_id},
        {"$set": update_fields},
    )

    # Propagar renombre a clientes que usen el nombre anterior
    if new_name and new_name != old_name:
        await db.clients.update_many(
            {"categoria_comercial": old_name},
            {"$set": {"categoria_comercial": new_name}},
        )

    refreshed = await db.commercial_categories.find_one({"category_id": category_id}, {"_id": 0})
    return refreshed


@router.delete("/commercial-categories/{category_id}")
async def delete_commercial_category(
    category_id: str,
    authorization: Optional[str] = Header(None),
):
    """Elimina una categoría. Solo admin.
    Bloquea el borrado si está siendo usada por clientes (protege integridad)."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar el catálogo")

    cat = await db.commercial_categories.find_one({"category_id": category_id}, {"_id": 0, "name": 1})
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    # Conteo robusto: match case-insensitive y trim defensivo
    in_use = await db.clients.count_documents({"categoria_comercial": _name_regex(cat["name"])})
    if in_use > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: {in_use} cliente(s) usan esta categoría. Desactívela o reasigne los clientes primero.",
        )

    await db.commercial_categories.delete_one({"category_id": category_id})
    return {"message": "Categoría eliminada"}


@router.post("/commercial-categories/seed-from-existing-clients")
async def seed_from_existing(authorization: Optional[str] = Header(None)):
    """Seed one-shot: crea entradas del catálogo a partir de los valores `categoria_comercial`
    ya usados por clientes, evitando perder datos tras la migración. Solo admin."""
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "")
    distinct_names: List[str] = await db.clients.distinct(
        "categoria_comercial", {"categoria_comercial": {"$nin": [None, ""]}}
    )

    created = []
    for raw in distinct_names:
        name = (raw or "").strip()
        if not name:
            continue
        existing = await db.commercial_categories.find_one(
            {"name": _name_regex(name)},
            {"_id": 0, "category_id": 1},
        )
        if existing:
            continue
        doc = {
            "category_id": f"cat_{uuid.uuid4().hex[:12]}",
            "name": name,
            "description": None,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": f"{user_name} (seed)",
            "updated_at": None,
            "updated_by": None,
        }
        await db.commercial_categories.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

    total = await db.commercial_categories.count_documents({})
    return {"created": len(created), "total_in_catalog": total, "new_entries": created}
