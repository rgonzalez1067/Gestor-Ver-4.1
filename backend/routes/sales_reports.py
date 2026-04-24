"""Reportes de Ventas — endpoints agregados sobre `quotes`.

Tres reportes principales:
- Funnel: conteo y montos por estado del flujo (Enviada, Aprobada, Facturada, Pagada, Entregada).
- Aging: cotizaciones no finalizadas con días en su estado actual (buckets 0-7, 8-15, 16-30, >30).
- Monthly: cotizado, facturado y cobrado por mes para el año filtrado.
"""
from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional
from datetime import datetime, timezone

from config import db, get_current_user

router = APIRouter()

# Orden canónico del flujo (ignora 'Borrador' y 'Reparada' que es intermedio).
FUNNEL_STAGES = [
    ("Enviada", "sent_to_client_at"),
    ("Aprobada", "approved_at"),
    ("Facturada", "invoiced_at"),
    ("Pagada", "paid_at"),
    ("Entregada", "delivered_at"),
]


def _build_match(date_from: Optional[str], date_to: Optional[str],
                 segment: Optional[str], category: Optional[str]) -> dict:
    match = {}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        match["created_at"] = rng
    if segment and segment != "all":
        match["client_segment"] = segment
    if category and category != "all":
        match["quote_category"] = category
    return match


def _days_since(iso_str: str) -> int:
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(0, delta.days)
    except Exception:
        return 0


@router.get("/reports/sales/funnel")
async def funnel_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Conteo y monto agregado por etapa del flujo (cumulativo histórico).
    Una cotización aporta a cada etapa por la que pasó (timestamp != null)."""
    await get_current_user(authorization)
    match = _build_match(date_from, date_to, segment, category)

    quotes = await db.quotes.find(match, {
        "_id": 0, "quote_id": 1, "total_usd": 1, "quote_status": 1,
        "sent_to_client_at": 1, "approved_at": 1,
        "invoiced_at": 1, "paid_at": 1, "delivered_at": 1,
    }).to_list(None)

    stages = []
    for stage_name, ts_field in FUNNEL_STAGES:
        count = sum(1 for q in quotes if q.get(ts_field))
        amount = sum(float(q.get("total_usd") or 0) for q in quotes if q.get(ts_field))
        stages.append({
            "stage": stage_name,
            "count": count,
            "amount_usd": round(amount, 2),
        })

    sent = stages[0]["count"] or 0
    paid = next((s["count"] for s in stages if s["stage"] == "Pagada"), 0)
    delivered = next((s["count"] for s in stages if s["stage"] == "Entregada"), 0)
    return {
        "stages": stages,
        "totals": {
            "quotes_total": len(quotes),
            "amount_total_usd": round(sum(float(q.get("total_usd") or 0) for q in quotes), 2),
            "conversion_sent_to_paid": round((paid / sent * 100), 2) if sent else 0,
            "conversion_sent_to_delivered": round((delivered / sent * 100), 2) if sent else 0,
        },
    }


@router.get("/reports/sales/aging")
async def aging_report(
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Cotizaciones NO finalizadas (no Entregada y no archivadas) con días en estado actual.
    Buckets: 0-7, 8-15, 16-30, >30."""
    await get_current_user(authorization)

    match = {
        "quote_status": {"$nin": ["Entregada", "Borrador"]},
        "archived": {"$ne": True},
    }
    if segment and segment != "all":
        match["client_segment"] = segment
    if category and category != "all":
        match["quote_category"] = category

    quotes = await db.quotes.find(match, {
        "_id": 0, "quote_id": 1, "quote_number": 1, "client_name": 1,
        "client_segment": 1, "quote_category": 1, "quote_status": 1,
        "total_usd": 1, "created_by_user_id": 1, "created_at": 1,
        "sent_to_client_at": 1, "approved_at": 1,
        "invoiced_at": 1, "paid_at": 1, "repaired_at": 1,
    }).to_list(None)

    # Resolver gestor desde users
    user_ids = list({q.get("created_by_user_id") for q in quotes if q.get("created_by_user_id")})
    user_map = {}
    if user_ids:
        users = await db.users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1},
        ).to_list(None)
        for u in users:
            full = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or u.get("email", "")
            user_map[u["user_id"]] = full

    # Mapeo estado → timestamp del último cambio a ese estado
    status_ts_map = {
        "Enviada": "sent_to_client_at",
        "Aprobada": "approved_at",
        "Reparada": "repaired_at",
        "Facturada": "invoiced_at",
        "Pagada": "paid_at",
    }

    rows = []
    buckets = {"0-7": 0, "8-15": 0, "16-30": 0, ">30": 0}
    bucket_amounts = {"0-7": 0.0, "8-15": 0.0, "16-30": 0.0, ">30": 0.0}
    for q in quotes:
        status = q.get("quote_status", "")
        ts_field = status_ts_map.get(status, "created_at")
        last_ts = q.get(ts_field) or q.get("created_at")
        days = _days_since(last_ts)
        amt = float(q.get("total_usd") or 0)
        if days <= 7:
            b = "0-7"
        elif days <= 15:
            b = "8-15"
        elif days <= 30:
            b = "16-30"
        else:
            b = ">30"
        buckets[b] += 1
        bucket_amounts[b] += amt
        rows.append({
            "quote_id": q.get("quote_id"),
            "quote_number": q.get("quote_number"),
            "client_name": q.get("client_name"),
            "client_segment": q.get("client_segment"),
            "quote_category": q.get("quote_category"),
            "quote_status": status,
            "total_usd": round(amt, 2),
            "days_in_state": days,
            "bucket": b,
            "gestor": user_map.get(q.get("created_by_user_id"), ""),
            "last_change_at": last_ts,
        })

    rows.sort(key=lambda r: r["days_in_state"], reverse=True)
    return {
        "rows": rows,
        "buckets": [
            {"bucket": k, "count": buckets[k], "amount_usd": round(bucket_amounts[k], 2)}
            for k in ["0-7", "8-15", "16-30", ">30"]
        ],
    }


@router.get("/reports/sales/monthly")
async def monthly_report(
    year: int = Query(...),
    category: Optional[str] = Query(None),
    segment: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Cotizado / Facturado / Cobrado por mes para el año dado.
    - cotizado: total_usd de quotes creados en el mes (created_at).
    - facturado: total_usd de quotes con invoiced_at en el mes.
    - cobrado: total_usd de quotes con paid_at en el mes.
    """
    await get_current_user(authorization)

    base_match = {}
    if category and category != "all":
        base_match["quote_category"] = category
    if segment and segment != "all":
        base_match["client_segment"] = segment

    quotes = await db.quotes.find(base_match, {
        "_id": 0, "total_usd": 1,
        "created_at": 1, "invoiced_at": 1, "paid_at": 1,
    }).to_list(None)

    months = [{"month": m, "cotizado": 0.0, "facturado": 0.0, "cobrado": 0.0,
               "cotizado_count": 0, "facturado_count": 0, "cobrado_count": 0}
              for m in range(1, 13)]

    def month_of(iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if dt.year != year:
                return None
            return dt.month
        except Exception:
            return None

    for q in quotes:
        amt = float(q.get("total_usd") or 0)
        m_c = month_of(q.get("created_at"))
        if m_c:
            months[m_c - 1]["cotizado"] += amt
            months[m_c - 1]["cotizado_count"] += 1
        m_i = month_of(q.get("invoiced_at"))
        if m_i:
            months[m_i - 1]["facturado"] += amt
            months[m_i - 1]["facturado_count"] += 1
        m_p = month_of(q.get("paid_at"))
        if m_p:
            months[m_p - 1]["cobrado"] += amt
            months[m_p - 1]["cobrado_count"] += 1

    for row in months:
        for k in ("cotizado", "facturado", "cobrado"):
            row[k] = round(row[k], 2)

    totals = {
        "cotizado": round(sum(r["cotizado"] for r in months), 2),
        "facturado": round(sum(r["facturado"] for r in months), 2),
        "cobrado": round(sum(r["cobrado"] for r in months), 2),
    }
    return {"year": year, "months": months, "totals": totals}
