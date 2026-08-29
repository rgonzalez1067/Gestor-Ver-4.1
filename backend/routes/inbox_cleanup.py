"""Depuración de la colección `inbox_messages` (Admin).

Permite calcular cuántos registros existen en un periodo específico y depurar
(eliminar de forma permanente) esa selección para reducir el peso de la
colección. Función permanente de mantenimiento.

Endpoints (todos admin-only):
- GET  /api/admin/inbox/cleanup/stats            → panorama general + desglose por mes.
- POST /api/admin/inbox/cleanup/preview          → cuenta y tamaño aprox. de un rango.
- POST /api/admin/inbox/cleanup/purge            → elimina permanentemente el rango.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import db, get_current_user

router = APIRouter(prefix="/admin/inbox/cleanup", tags=["inbox-cleanup"])
logger = logging.getLogger("inbox_cleanup")


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden depurar el buzón interno")
    return user


class PeriodBody(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD (inclusivo)


def _period_bounds(start_date: str, end_date: str) -> tuple[str, str]:
    """Devuelve (inicio_inclusivo, fin_exclusivo) como cadenas ISO comparables.

    `created_at` se guarda como ISO string; el rango se resuelve con
    comparación lexicográfica de prefijos de fecha, robusta ante distintos
    sufijos de zona horaria.
    """
    try:
        d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
        d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas. Use formato YYYY-MM-DD")
    if d1 < d0:
        raise HTTPException(status_code=400, detail="La fecha final no puede ser anterior a la inicial")
    start_inclusive = f"{d0.isoformat()}T00:00:00"
    end_exclusive = f"{(d1 + timedelta(days=1)).isoformat()}T00:00:00"
    return start_inclusive, end_exclusive


async def _count_and_size(query: dict) -> dict:
    """Cuenta documentos y estima el tamaño total en bytes vía $bsonSize."""
    count = await db.inbox_messages.count_documents(query)
    size_bytes = 0
    if count:
        pipeline = [
            {"$match": query},
            {"$group": {"_id": None, "size": {"$sum": {"$bsonSize": "$$ROOT"}}}},
        ]
        agg = await db.inbox_messages.aggregate(pipeline).to_list(1)
        if agg:
            size_bytes = int(agg[0].get("size") or 0)
    return {"count": count, "size_bytes": size_bytes}


@router.get("/stats")
async def cleanup_stats(authorization: Optional[str] = Header(None)):
    """Panorama general de la colección + desglose por mes (para elegir periodo)."""
    await _require_admin(authorization)

    totals = await _count_and_size({})

    oldest_doc = await db.inbox_messages.find_one({}, {"_id": 0, "created_at": 1}, sort=[("created_at", 1)])
    newest_doc = await db.inbox_messages.find_one({}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])

    # Desglose por mes (YYYY-MM) con conteo y tamaño
    by_month = []
    if totals["count"]:
        pipeline = [
            {"$group": {
                "_id": {"$substrBytes": ["$created_at", 0, 7]},
                "count": {"$sum": 1},
                "size_bytes": {"$sum": {"$bsonSize": "$$ROOT"}},
            }},
            {"$sort": {"_id": -1}},
        ]
        rows = await db.inbox_messages.aggregate(pipeline).to_list(500)
        by_month = [
            {"month": r["_id"], "count": r["count"], "size_bytes": int(r.get("size_bytes") or 0)}
            for r in rows if r.get("_id")
        ]

    return {
        "total_count": totals["count"],
        "total_size_bytes": totals["size_bytes"],
        "oldest": (oldest_doc or {}).get("created_at"),
        "newest": (newest_doc or {}).get("created_at"),
        "by_month": by_month,
    }


@router.post("/preview")
async def cleanup_preview(body: PeriodBody, authorization: Optional[str] = Header(None)):
    """Calcula cuántos registros y qué tamaño ocupa el periodo seleccionado."""
    await _require_admin(authorization)
    start_inclusive, end_exclusive = _period_bounds(body.start_date, body.end_date)
    query = {"created_at": {"$gte": start_inclusive, "$lt": end_exclusive}}
    result = await _count_and_size(query)
    return {
        "start_date": body.start_date,
        "end_date": body.end_date,
        "count": result["count"],
        "size_bytes": result["size_bytes"],
    }


@router.post("/purge")
async def cleanup_purge(body: PeriodBody, authorization: Optional[str] = Header(None)):
    """Elimina permanentemente los mensajes del buzón dentro del periodo."""
    user = await _require_admin(authorization)
    start_inclusive, end_exclusive = _period_bounds(body.start_date, body.end_date)
    query = {"created_at": {"$gte": start_inclusive, "$lt": end_exclusive}}

    res = await db.inbox_messages.delete_many(query)
    deleted = res.deleted_count
    logger.info(
        f"[InboxCleanup] admin={user.get('email') or user.get('user_id')} "
        f"purgó {deleted} mensaje(s) del rango {body.start_date}..{body.end_date}"
    )
    return {
        "start_date": body.start_date,
        "end_date": body.end_date,
        "deleted_count": deleted,
    }
