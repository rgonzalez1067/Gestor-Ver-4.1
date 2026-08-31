"""Depuración de Archivos por periodos (Admin).

Módulo de mantenimiento genérico: permite calcular cuántos registros existen en
un periodo específico y depurarlos (eliminación permanente) para reducir el peso
de colecciones de alto volumen. Antes solo aplicaba a `inbox_messages`; ahora
soporta un catálogo blanco (whitelist) de colecciones depurables.

Colecciones soportadas: inbox_messages, notifications, email_logs, bitacora,
user_sessions.

Endpoints (todos admin-only):
- GET  /api/admin/records/cleanup/collections              → catálogo + conteo total.
- GET  /api/admin/records/cleanup/{collection}/stats       → panorama + desglose por mes.
- POST /api/admin/records/cleanup/{collection}/preview     → cuenta y tamaño de un rango.
- POST /api/admin/records/cleanup/{collection}/purge       → elimina permanentemente el rango.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import db, get_current_user

router = APIRouter(prefix="/admin/records/cleanup", tags=["records-cleanup"])
logger = logging.getLogger("records_cleanup")


# Catálogo blanco de colecciones depurables. `date_fields` define el orden de
# coalescencia (primer campo presente gana) para resolver la fecha del registro.
CLEANABLE_COLLECTIONS = {
    "inbox_messages": {"label": "Inbox (Buzón interno)", "date_fields": ["created_at"]},
    "notifications": {"label": "Notificaciones", "date_fields": ["created_at"]},
    "email_logs": {"label": "Logs de Correo", "date_fields": ["created_at"]},
    "bitacora": {"label": "Bitácora", "date_fields": ["executed_at", "created_at", "date"]},
    "user_sessions": {"label": "Sesiones de Usuario", "date_fields": ["created_at"]},
}


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden depurar archivos")
    return user


def _get_cfg_or_404(collection: str) -> dict:
    cfg = CLEANABLE_COLLECTIONS.get(collection)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Colección '{collection}' no depurable")
    return cfg


class PeriodBody(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD (inclusivo)


def _period_bounds(start_date: str, end_date: str) -> tuple[str, str]:
    """Devuelve (inicio_inclusivo, fin_exclusivo) como cadenas ISO comparables."""
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


def _date_expr(date_fields: list) -> dict:
    """Expresión de coalescencia de fecha ($ifNull anidado, termina en "")."""
    expr = ""
    for f in reversed(date_fields):
        expr = {"$ifNull": [f"${f}", expr]}
    return expr


def _range_query(cfg: dict, start_incl: str, end_excl: str) -> dict:
    de = _date_expr(cfg["date_fields"])
    return {"$expr": {"$and": [
        {"$gte": [de, start_incl]},
        {"$lt": [de, end_excl]},
    ]}}


async def _count_and_size(collection: str, query: dict) -> dict:
    """Cuenta documentos y estima el tamaño total en bytes vía $bsonSize."""
    coll = db[collection]
    count = await coll.count_documents(query)
    size_bytes = 0
    if count:
        pipeline = [
            {"$match": query},
            {"$group": {"_id": None, "size": {"$sum": {"$bsonSize": "$$ROOT"}}}},
        ]
        agg = await coll.aggregate(pipeline).to_list(1)
        if agg:
            size_bytes = int(agg[0].get("size") or 0)
    return {"count": count, "size_bytes": size_bytes}


@router.get("/collections")
async def list_collections(authorization: Optional[str] = Header(None)):
    """Catálogo de colecciones depurables con su conteo total de registros."""
    await _require_admin(authorization)
    out = []
    for key, cfg in CLEANABLE_COLLECTIONS.items():
        total = await db[key].count_documents({})
        out.append({"collection": key, "label": cfg["label"], "total_count": total})
    return {"collections": out}


@router.get("/{collection}/stats")
async def cleanup_stats(collection: str, authorization: Optional[str] = Header(None)):
    """Panorama general de la colección + desglose por mes (para elegir periodo)."""
    await _require_admin(authorization)
    cfg = _get_cfg_or_404(collection)
    coll = db[collection]
    de = _date_expr(cfg["date_fields"])

    totals = await _count_and_size(collection, {})

    oldest = newest = None
    by_month = []
    if totals["count"]:
        # Excluir registros sin fecha resoluble (dateExpr == "")
        base_match = {"$match": {"$expr": {"$ne": [de, ""]}}}

        rng = await coll.aggregate([
            base_match,
            {"$group": {"_id": None, "oldest": {"$min": de}, "newest": {"$max": de}}},
        ]).to_list(1)
        if rng:
            oldest = rng[0].get("oldest")
            newest = rng[0].get("newest")

        rows = await coll.aggregate([
            base_match,
            {"$group": {
                "_id": {"$substrBytes": [de, 0, 7]},
                "count": {"$sum": 1},
                "size_bytes": {"$sum": {"$bsonSize": "$$ROOT"}},
            }},
            {"$sort": {"_id": -1}},
        ]).to_list(500)
        by_month = [
            {"month": r["_id"], "count": r["count"], "size_bytes": int(r.get("size_bytes") or 0)}
            for r in rows if r.get("_id")
        ]

    return {
        "collection": collection,
        "label": cfg["label"],
        "total_count": totals["count"],
        "total_size_bytes": totals["size_bytes"],
        "oldest": oldest,
        "newest": newest,
        "by_month": by_month,
    }


@router.post("/{collection}/preview")
async def cleanup_preview(collection: str, body: PeriodBody, authorization: Optional[str] = Header(None)):
    """Calcula cuántos registros y qué tamaño ocupa el periodo seleccionado."""
    await _require_admin(authorization)
    cfg = _get_cfg_or_404(collection)
    start_incl, end_excl = _period_bounds(body.start_date, body.end_date)
    result = await _count_and_size(collection, _range_query(cfg, start_incl, end_excl))
    return {
        "collection": collection,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "count": result["count"],
        "size_bytes": result["size_bytes"],
    }


@router.post("/{collection}/purge")
async def cleanup_purge(collection: str, body: PeriodBody, authorization: Optional[str] = Header(None)):
    """Elimina permanentemente los registros de la colección dentro del periodo."""
    user = await _require_admin(authorization)
    cfg = _get_cfg_or_404(collection)
    start_incl, end_excl = _period_bounds(body.start_date, body.end_date)

    res = await db[collection].delete_many(_range_query(cfg, start_incl, end_excl))
    deleted = res.deleted_count
    logger.info(
        f"[RecordsCleanup] admin={user.get('email') or user.get('user_id')} "
        f"purgó {deleted} registro(s) de '{collection}' rango {body.start_date}..{body.end_date}"
    )
    return {
        "collection": collection,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "deleted_count": deleted,
    }
