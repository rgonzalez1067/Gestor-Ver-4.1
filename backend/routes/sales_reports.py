"""Reportes de Ventas — endpoints agregados sobre `quotes`.

Tres reportes principales:
- Funnel: conteo y montos por estado del flujo (Enviada, Aprobada, Facturada, Pagada, Entregada).
- Aging: cotizaciones no finalizadas con días en su estado actual (buckets 0-7, 8-15, 16-30, >30).
- Monthly: cotizado, facturado y cobrado por mes para el año filtrado.
"""
from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
import io
import weasyprint

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



# =====================================================================
# FASE 2 — Reportes adicionales
# =====================================================================

@router.get("/reports/sales/receivables")
async def receivables_report(
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Cuentas por cobrar: cotizaciones facturadas pero no pagadas.
    Buckets 0-30, 31-60, 61-90, >90 días desde `invoiced_at`.
    Devuelve lista detallada y top deudores agrupados por cliente."""
    await get_current_user(authorization)

    base = {}
    if segment and segment != "all":
        base["client_segment"] = segment
    if category and category != "all":
        base["quote_category"] = category

    quotes = await db.quotes.find(
        {"$and": [base, {"invoiced_at": {"$exists": True, "$ne": None}}]},
        {"_id": 0, "quote_id": 1, "quote_number": 1, "client_id": 1, "client_name": 1,
         "client_segment": 1, "quote_category": 1, "total_usd": 1,
         "invoiced_at": 1, "paid_at": 1, "invoice_number": 1,
         "created_by_user_id": 1},
    ).to_list(None)

    # Filtrar las que no están pagadas (paid_at null o ausente)
    pending = [q for q in quotes if not q.get("paid_at")]

    # Mapeo de gestor
    user_ids = list({q.get("created_by_user_id") for q in pending if q.get("created_by_user_id")})
    user_map = {}
    if user_ids:
        users = await db.users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1},
        ).to_list(None)
        for u in users:
            full = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or u.get("email", "")
            user_map[u["user_id"]] = full

    rows = []
    buckets = {"0-30": 0, "31-60": 0, "61-90": 0, ">90": 0}
    bucket_amounts = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, ">90": 0.0}
    by_client = {}

    for q in pending:
        days = _days_since(q.get("invoiced_at"))
        amt = float(q.get("total_usd") or 0)
        if days <= 30:
            b = "0-30"
        elif days <= 60:
            b = "31-60"
        elif days <= 90:
            b = "61-90"
        else:
            b = ">90"
        buckets[b] += 1
        bucket_amounts[b] += amt
        rows.append({
            "quote_id": q.get("quote_id"),
            "quote_number": q.get("quote_number"),
            "invoice_number": q.get("invoice_number"),
            "client_id": q.get("client_id"),
            "client_name": q.get("client_name"),
            "client_segment": q.get("client_segment"),
            "total_usd": round(amt, 2),
            "days_since_invoice": days,
            "bucket": b,
            "gestor": user_map.get(q.get("created_by_user_id"), ""),
            "invoiced_at": q.get("invoiced_at"),
        })
        cid = q.get("client_id") or "SIN_ID"
        if cid not in by_client:
            by_client[cid] = {
                "client_id": cid,
                "client_name": q.get("client_name", ""),
                "client_segment": q.get("client_segment", ""),
                "amount_usd": 0.0,
                "invoices": 0,
                "max_days": 0,
            }
        by_client[cid]["amount_usd"] += amt
        by_client[cid]["invoices"] += 1
        by_client[cid]["max_days"] = max(by_client[cid]["max_days"], days)

    rows.sort(key=lambda r: r["days_since_invoice"], reverse=True)
    top_debtors = sorted(by_client.values(), key=lambda c: c["amount_usd"], reverse=True)[:10]
    for d in top_debtors:
        d["amount_usd"] = round(d["amount_usd"], 2)

    return {
        "rows": rows,
        "buckets": [
            {"bucket": k, "count": buckets[k], "amount_usd": round(bucket_amounts[k], 2)}
            for k in ["0-30", "31-60", "61-90", ">90"]
        ],
        "top_debtors": top_debtors,
        "total_pending_usd": round(sum(r["total_usd"] for r in rows), 2),
        "total_pending_count": len(rows),
    }


@router.get("/reports/sales/clients-ranking")
async def clients_ranking_report(
    year: int = Query(...),
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    top_n: int = Query(20),
    authorization: Optional[str] = Header(None),
):
    """Ranking de clientes por monto (cotizado en el año).
    Calcula tendencia ↑↓ comparando trimestre actual vs anterior."""
    await get_current_user(authorization)

    base = {}
    if segment and segment != "all":
        base["client_segment"] = segment
    if category and category != "all":
        base["quote_category"] = category

    quotes = await db.quotes.find(base, {
        "_id": 0, "client_id": 1, "client_name": 1, "client_segment": 1,
        "total_usd": 1, "created_at": 1, "paid_at": 1,
    }).to_list(None)

    today = datetime.now(timezone.utc)
    current_q_start_month = ((today.month - 1) // 3) * 3 + 1
    current_q_year = today.year

    by_client = {}
    for q in quotes:
        ca = q.get("created_at")
        if not ca:
            continue
        try:
            dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year != year:
            continue
        amt = float(q.get("total_usd") or 0)
        cid = q.get("client_id") or "SIN_ID"
        if cid not in by_client:
            by_client[cid] = {
                "client_id": cid,
                "client_name": q.get("client_name", ""),
                "client_segment": q.get("client_segment", ""),
                "total_usd": 0.0,
                "quotes_count": 0,
                "amount_current_q": 0.0,
                "amount_prev_q": 0.0,
                "paid_usd": 0.0,
            }
        by_client[cid]["total_usd"] += amt
        by_client[cid]["quotes_count"] += 1
        if q.get("paid_at"):
            by_client[cid]["paid_usd"] += amt
        # Quarter logic
        q_month = ((dt.month - 1) // 3) * 3 + 1
        if dt.year == current_q_year and q_month == current_q_start_month:
            by_client[cid]["amount_current_q"] += amt
        elif (dt.year == current_q_year and q_month == current_q_start_month - 3) or \
             (current_q_start_month == 1 and dt.year == current_q_year - 1 and q_month == 10):
            by_client[cid]["amount_prev_q"] += amt

    ranking = sorted(by_client.values(), key=lambda c: c["total_usd"], reverse=True)[:top_n]
    for r in ranking:
        cur, prev = r["amount_current_q"], r["amount_prev_q"]
        if prev == 0 and cur > 0:
            r["trend_pct"] = None  # nuevo
        elif prev == 0:
            r["trend_pct"] = 0
        else:
            r["trend_pct"] = round((cur - prev) / prev * 100, 1)
        r["total_usd"] = round(r["total_usd"], 2)
        r["paid_usd"] = round(r["paid_usd"], 2)
        r["amount_current_q"] = round(r["amount_current_q"], 2)
        r["amount_prev_q"] = round(r["amount_prev_q"], 2)

    return {
        "year": year,
        "ranking": ranking,
        "total_amount": round(sum(r["total_usd"] for r in ranking), 2),
        "current_quarter": current_q_start_month,
    }


@router.get("/reports/sales/repair-productivity")
async def repair_productivity_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Productividad del taller de reparaciones.
    - Lead times: Enviada→Reparada y Reparada→Entregada por implementador (gestor).
    - SLA breach: % de reparaciones con lead time total > 7 días."""
    await get_current_user(authorization)

    match = {"quote_category": "repair", "quote_status": {"$in": ["Reparada", "Facturada", "Pagada", "Entregada"]}}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        match["created_at"] = rng

    quotes = await db.quotes.find(match, {
        "_id": 0, "quote_id": 1, "quote_number": 1, "client_name": 1,
        "sent_to_client_at": 1, "repaired_at": 1, "delivered_at": 1,
        "created_by_user_id": 1, "total_usd": 1,
    }).to_list(None)

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

    def _hours_diff(a, b):
        if not a or not b:
            return None
        try:
            da = datetime.fromisoformat(a.replace("Z", "+00:00"))
            dbb = datetime.fromisoformat(b.replace("Z", "+00:00"))
            return round((dbb - da).total_seconds() / 3600, 1)
        except Exception:
            return None

    by_implementor = {}
    rows = []
    sla_total = 0
    sla_breach = 0
    for q in quotes:
        gestor = user_map.get(q.get("created_by_user_id"), "Sin asignar")
        repair_h = _hours_diff(q.get("sent_to_client_at"), q.get("repaired_at"))
        deliver_h = _hours_diff(q.get("repaired_at"), q.get("delivered_at"))
        total_h = None
        if repair_h is not None and deliver_h is not None:
            total_h = round(repair_h + deliver_h, 1)
        if total_h is not None:
            sla_total += 1
            if total_h / 24 > 7:
                sla_breach += 1

        if gestor not in by_implementor:
            by_implementor[gestor] = {"gestor": gestor, "count": 0, "repair_total_h": 0.0, "deliver_total_h": 0.0, "samples_repair": 0, "samples_deliver": 0}
        by_implementor[gestor]["count"] += 1
        if repair_h is not None:
            by_implementor[gestor]["repair_total_h"] += repair_h
            by_implementor[gestor]["samples_repair"] += 1
        if deliver_h is not None:
            by_implementor[gestor]["deliver_total_h"] += deliver_h
            by_implementor[gestor]["samples_deliver"] += 1

        rows.append({
            "quote_id": q.get("quote_id"),
            "quote_number": q.get("quote_number"),
            "client_name": q.get("client_name"),
            "gestor": gestor,
            "repair_lead_h": repair_h,
            "deliver_lead_h": deliver_h,
            "total_lead_days": round(total_h / 24, 2) if total_h else None,
            "total_usd": round(float(q.get("total_usd") or 0), 2),
        })

    by_imp_list = []
    for k, v in by_implementor.items():
        avg_repair = v["repair_total_h"] / v["samples_repair"] if v["samples_repair"] else None
        avg_deliver = v["deliver_total_h"] / v["samples_deliver"] if v["samples_deliver"] else None
        by_imp_list.append({
            "gestor": v["gestor"],
            "count": v["count"],
            "avg_repair_hours": round(avg_repair, 1) if avg_repair else None,
            "avg_deliver_hours": round(avg_deliver, 1) if avg_deliver else None,
            "avg_total_days": round((avg_repair + avg_deliver) / 24, 2) if avg_repair and avg_deliver else None,
        })
    by_imp_list.sort(key=lambda x: x["count"], reverse=True)

    return {
        "rows": rows,
        "by_implementor": by_imp_list,
        "sla_total": sla_total,
        "sla_breach": sla_breach,
        "sla_pct": round((sla_breach / sla_total * 100), 2) if sla_total else 0,
    }


@router.get("/reports/sales/stock-vs-demand")
async def stock_vs_demand_report(
    months_back: int = Query(6),
    authorization: Optional[str] = Header(None),
):
    """Stock actual vs demanda histórica (últimos N meses).
    - Stock = sum(entradas) - sum(salidas) en `inventory_movements` por item_id.
    - Demanda = unidades cotizadas (`equipment_items[].quantity`) en quotes recientes."""
    await get_current_user(authorization)

    cutoff = datetime.now(timezone.utc).replace(day=1)
    for _ in range(months_back):
        # restar mes (aprox 30 días)
        cutoff = cutoff.replace(day=15)
        prev_month = cutoff.month - 1
        prev_year = cutoff.year
        if prev_month == 0:
            prev_month = 12
            prev_year -= 1
        cutoff = cutoff.replace(year=prev_year, month=prev_month, day=1)
    cutoff_iso = cutoff.isoformat()

    # Stock: agrupar movimientos por item
    pipeline = [
        {"$group": {
            "_id": "$item_id",
            "in_qty": {"$sum": {"$cond": [{"$eq": ["$movement_type", "entrada"]}, "$quantity", 0]}},
            "out_qty": {"$sum": {"$cond": [{"$eq": ["$movement_type", "salida"]}, "$quantity", 0]}},
            "item_name": {"$first": "$item_name"},
            "item_type": {"$first": "$item_type"},
        }},
    ]
    stock = {}
    async for d in db.inventory_movements.aggregate(pipeline):
        iid = d["_id"]
        if not iid:
            continue
        stock[iid] = {
            "item_id": iid,
            "item_name": d.get("item_name", ""),
            "item_type": d.get("item_type", ""),
            "stock": int((d.get("in_qty") or 0) - (d.get("out_qty") or 0)),
            "demand": 0,
            "quotes_count": 0,
        }

    # Demanda: equipment_items en quotes recientes
    quotes = await db.quotes.find(
        {"created_at": {"$gte": cutoff_iso}, "equipment_items": {"$exists": True, "$ne": []}},
        {"_id": 0, "equipment_items": 1, "quote_id": 1},
    ).to_list(None)
    seen_items_per_quote = {}
    for q in quotes:
        for it in (q.get("equipment_items") or []):
            iid = it.get("hardware_id")
            if not iid:
                continue
            if iid not in stock:
                stock[iid] = {
                    "item_id": iid,
                    "item_name": it.get("name", ""),
                    "item_type": it.get("hardware_type", ""),
                    "stock": 0,
                    "demand": 0,
                    "quotes_count": 0,
                }
            stock[iid]["demand"] += int(it.get("quantity") or 0)
            qkey = q.get("quote_id")
            seen_items_per_quote.setdefault(iid, set()).add(qkey)

    for iid, s in stock.items():
        s["quotes_count"] = len(seen_items_per_quote.get(iid, set()))
        # Velocidad mensual (demanda/mes)
        s["monthly_demand"] = round(s["demand"] / months_back, 2)
        # Cobertura: meses de stock disponibles si demanda continúa
        if s["monthly_demand"] > 0:
            s["coverage_months"] = round(s["stock"] / s["monthly_demand"], 2)
        else:
            s["coverage_months"] = None
        # Semáforo
        if s["monthly_demand"] == 0:
            s["status"] = "no_demand"
        elif s["coverage_months"] is None:
            s["status"] = "ok"
        elif s["coverage_months"] < 1:
            s["status"] = "critical"
        elif s["coverage_months"] < 2:
            s["status"] = "warning"
        else:
            s["status"] = "ok"

    items = sorted(stock.values(), key=lambda s: s["demand"], reverse=True)
    return {
        "items": items[:30],  # top 30 por demanda
        "months_back": months_back,
        "summary": {
            "critical": sum(1 for s in items if s["status"] == "critical"),
            "warning": sum(1 for s in items if s["status"] == "warning"),
            "ok": sum(1 for s in items if s["status"] == "ok"),
        },
    }


@router.get("/reports/sales/leads-funnel")
async def leads_funnel_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Funnel de Contactos Iniciales — conversión global y por origen (`referred_by`)."""
    await get_current_user(authorization)

    match = {}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        match["created_at"] = rng

    contacts = await db.initial_contacts.find(match, {
        "_id": 0, "contact_id": 1, "is_converted": 1, "referred_by": 1,
        "created_at": 1, "updated_at": 1, "converted_client_id": 1,
    }).to_list(None)

    by_origin = {}
    total = len(contacts)
    converted = 0
    days_to_convert = []

    for c in contacts:
        origin = (c.get("referred_by") or "Sin origen").strip() or "Sin origen"
        if origin not in by_origin:
            by_origin[origin] = {"origin": origin, "total": 0, "converted": 0}
        by_origin[origin]["total"] += 1
        if c.get("is_converted"):
            converted += 1
            by_origin[origin]["converted"] += 1
            # Tiempo de conversión: created_at vs updated_at (cuando fue convertido)
            ca, ua = c.get("created_at"), c.get("updated_at")
            if ca and ua:
                try:
                    da = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                    db_ = datetime.fromisoformat(ua.replace("Z", "+00:00"))
                    days_to_convert.append((db_ - da).days)
                except Exception:
                    pass

    origins = []
    for k, v in by_origin.items():
        rate = round((v["converted"] / v["total"] * 100), 2) if v["total"] else 0
        origins.append({**v, "conversion_pct": rate})
    origins.sort(key=lambda x: x["total"], reverse=True)

    avg_convert_days = round(sum(days_to_convert) / len(days_to_convert), 1) if days_to_convert else None

    return {
        "total_leads": total,
        "converted": converted,
        "conversion_pct": round((converted / total * 100), 2) if total else 0,
        "avg_convert_days": avg_convert_days,
        "by_origin": origins,
    }


# =====================================================================
# COTIZACIONES EN ESTADO IRREGULAR
# =====================================================================

# Flujos por categoría (espejo de FLOWS en frontend/components/quotes/QuoteStatusStepper.jsx)
CATEGORY_FLOWS = {
    "repair": [
        ("created_at", "Creada"),
        ("sent_to_client_at", "Enviada al Cliente"),
        ("approved_at", "Aprobada"),
        ("repaired_at", "Reparada"),
        ("invoiced_at", "Facturada"),
        ("paid_at", "Pagada"),
        ("delivered_at", "Entregada"),
    ],
    "fast_track": [
        ("created_at", "Creada"),
        ("sent_to_client_at", "Enviada al Cliente"),
        ("approved_at", "Aprobada"),
        ("configured_at", "Configurada"),
        ("invoiced_at", "Facturada"),
        ("paid_at", "Pagada"),
        ("delivered_at", "Entregada"),
    ],
    "equipment": [
        ("created_at", "Creada"),
        ("sent_to_client_at", "Enviada al Cliente"),
        ("approved_at", "Aprobada"),
        ("invoiced_at", "Facturada"),
        ("paid_at", "Pagada"),
        ("delivered_at", "Entregada"),
    ],
    "implementation": [
        ("created_at", "Creada"),
        ("sent_to_client_at", "Enviada al Cliente"),
        ("approved_at", "Aprobada"),
        ("invoiced_at", "Facturada"),
        ("paid_at", "Pagada"),
        ("sent_to_implementation_at", "Enviada a Imple"),
    ],
}
DEFAULT_FLOW = CATEGORY_FLOWS["implementation"]


def _get_flow(cat: Optional[str]) -> list:
    return CATEGORY_FLOWS.get((cat or "").lower(), DEFAULT_FLOW)


def _is_to_project_trigger(trigger: Optional[str]) -> bool:
    """Normaliza el archived_trigger y detecta si la cotización pasó a Proyecto.

    Acepta dos familias de valores usadas en distintas zonas del código:
    - Etiquetas legibles: 'Enviada a Imple', 'Enviada a Implementación', etc.
    - Códigos internos: 'status_enviada_imple', 'status_enviada_imple_recovered', etc.
    """
    if not trigger:
        return False
    norm = str(trigger).strip().lower().replace(" ", "_")
    return "enviada_imple" in norm or "enviada_a_imple" in norm


# Mapa de subsano: una categoría de anexo subsana la falta de timestamp en
# la fase indicada. Útil para que un Administrador, al subir el documento
# faltante en el Histórico, normalice automáticamente el reporte de
# irregularidades (la celda pasa de roja a verde).
SUBSANA_CATEGORY_MAP = {
    "Cotización": "sent_to_client_at",
    "Soporte de Aprobación": "approved_at",
    "Orden de Compra": "approved_at",
    "Factura": "invoiced_at",
    "Pagos": "paid_at",
    "Nota de Entrega": "delivered_at",
}


def _get_subsanados(q: dict) -> set:
    """Devuelve el set de campos (timestamps) cuya falta queda subsanada por
    los anexos cargados en la cotización."""
    fields = set()
    for att in (q.get("attachments") or []):
        f = SUBSANA_CATEGORY_MAP.get(att.get("category"))
        if f:
            fields.add(f)
    return fields


def _detect_irregularities(q: dict) -> list:
    """Una fase es irregular si una fase POSTERIOR del flujo tiene timestamp pero ella NO.
    Usa el flujo correspondiente a `quote_category`. Para `implementation`, también
    cuenta `archived_at` con trigger 'Enviada a Imple' como `sent_to_implementation_at`.

    Reglas de normalización adicionales:
    - Si la cotización proviene del Histórico (`_is_history`), la última fase del
      flujo se considera SIEMPRE cumplida (verde) — ya completó el ciclo.
    - Si existe un anexo del Histórico cuya categoría subsana una fase faltante
      (ver `SUBSANA_CATEGORY_MAP`), esa fase se considera cumplida.

    Adicionalmente marca como irregular cualquier cotización que:
    - Pasó a Proyecto (archived + trigger 'Enviada a Imple') sin `approved_at`.
    """
    cat = (q.get("quote_category") or "").lower()
    flow = _get_flow(cat)

    # Para implementation: si pasó a proyecto vía archived, ese trigger sustituye sent_to_implementation_at
    is_to_project = bool(q.get("archived")) and _is_to_project_trigger(q.get("archived_trigger"))
    is_history = bool(q.get("_is_history"))
    subsanados = _get_subsanados(q)
    final_field = flow[-1][0] if flow else None

    def has_ts(field):
        if field == "sent_to_implementation_at" and cat == "implementation":
            return bool(q.get(field)) or is_to_project
        # Histórico → fase final siempre verde (ya cerró ciclo operativo)
        if is_history and field == final_field:
            return True
        # Subsanado por anexo cargado en el Histórico
        if field in subsanados:
            return True
        return bool(q.get(field))

    issues = []
    last_ts_idx = -1
    for i, (field, _label) in enumerate(flow):
        if has_ts(field):
            last_ts_idx = i

    if last_ts_idx > 0:
        for i, (field, label) in enumerate(flow):
            if i < last_ts_idx and not has_ts(field):
                issues.append(f"Falta fecha de {label}")

    # Check explícito: pasó a Proyecto sin aprobación.
    # Si el Admin subió "Soporte de Aprobación" / "Orden de Compra" en el
    # histórico, la falta se considera subsanada.
    if is_to_project and not q.get("approved_at") and "approved_at" not in subsanados:
        msg = "Pasó a Proyecto sin Aprobación previa"
        if msg not in issues:
            issues.append(msg)

    return issues


def _format_phase_timeline(q: dict) -> list:
    """Devuelve [{field, label, timestamp, present, subsana}] siguiendo el flujo de la categoría."""
    cat = (q.get("quote_category") or "").lower()
    flow = _get_flow(cat)
    is_to_project = bool(q.get("archived")) and _is_to_project_trigger(q.get("archived_trigger"))
    is_history = bool(q.get("_is_history"))
    subsanados = _get_subsanados(q)
    final_field = flow[-1][0] if flow else None

    out = []
    for field, label in flow:
        ts = q.get(field)
        # En implementation, usar archived_at si llegó por ese trigger y no hay sent_to_implementation_at
        if field == "sent_to_implementation_at" and cat == "implementation" and not ts and is_to_project:
            ts = q.get("archived_at")

        is_subsana = (not ts) and (field in subsanados)
        is_final_history = is_history and (field == final_field) and not ts
        # Para histórico, cuando la fase final no tiene timestamp explícito, usamos archived_at
        if is_final_history:
            ts = q.get("archived_at") or ts

        present = bool(ts) or is_subsana or is_final_history
        out.append({
            "field": field,
            "label": label,
            "timestamp": ts or None,
            "present": present,
            "subsana": is_subsana,
        })

    # Para categorías no-implementation que pasaron a proyecto: añadir marca extra
    if is_to_project and cat != "implementation":
        out.append({
            "field": "archived_at",
            "label": "Pasada a Proyecto",
            "timestamp": q.get("archived_at"),
            "present": bool(q.get("archived_at")),
            "subsana": False,
        })
    return out


async def _collect_irregular_quotes(match: dict) -> list:
    """Une `quotes` activas + `quote_history` (archivadas a proyecto) y filtra solo las irregulares."""
    irregulars = []

    # 1) Cotizaciones activas (no archivadas o aún en quotes)
    async for q in db.quotes.find(match, {"_id": 0}):
        issues = _detect_irregularities(q)
        if not issues:
            continue
        irregulars.append({
            "quote_id": q.get("quote_id"),
            "quote_number": q.get("quote_number"),
            "quote_category": q.get("quote_category"),
            "quote_type": q.get("quote_type"),
            "client_name": q.get("client_name"),
            "client_segment": q.get("client_segment"),
            "current_status": q.get("quote_status") or "—",
            "total_usd": q.get("total_usd") or 0,
            "passed_to_project": bool(q.get("archived")) and _is_to_project_trigger(q.get("archived_trigger")),
            "archived": bool(q.get("archived")),
            "archived_trigger": q.get("archived_trigger"),
            "phases": _format_phase_timeline(q),
            "issues": issues,
            "source": "quotes",
        })

    # 2) Cotizaciones históricas (incluye las pasadas a Proyecto)
    # `quote_history` snapshotea todo en el campo 'snapshot' que contiene los timestamps originales.
    async for h in db.quote_history.find(match, {"_id": 0}):
        snap = h.get("snapshot") or {}
        # mezclar campos del top-level con snapshot (fallbacks)
        combined = {**snap, **{k: h.get(k) for k in ("quote_id", "quote_number", "quote_category", "quote_type", "client_name", "archived_trigger")}}
        # Marcar como archivada y trigger desde el history
        combined["archived"] = True
        combined["_is_history"] = True
        # Anexos: priorizar los del documento histórico (incluye los subsanos
        # cargados por Admin sobre el registro archivado).
        combined["attachments"] = h.get("attachments") or snap.get("attachments") or []
        if not combined.get("archived_trigger"):
            combined["archived_trigger"] = h.get("archived_trigger")
        # Forzar archived_at desde el history
        combined.setdefault("archived_at", h.get("archived_at"))
        # Si snapshot no traía estos campos, derivarlos
        combined.setdefault("client_segment", snap.get("client_segment"))
        combined.setdefault("total_usd", h.get("total_usd"))

        # Aplicar filtros básicos (date range / segment / category) sobre `created_at` del snapshot
        if "$gte" in (match.get("created_at") or {}) or "$lte" in (match.get("created_at") or {}):
            ca = combined.get("created_at") or h.get("created_at")
            if not ca:
                continue
            rng = match["created_at"]
            if "$gte" in rng and ca < rng["$gte"]:
                continue
            if "$lte" in rng and ca > rng["$lte"]:
                continue
        if match.get("client_segment") and combined.get("client_segment") != match["client_segment"]:
            continue
        if match.get("quote_category") and combined.get("quote_category") != match["quote_category"]:
            continue

        issues = _detect_irregularities(combined)
        if not issues:
            continue

        # Evitar duplicados con `quotes` (si la cotización aún no fue removida)
        if any(x["quote_id"] == combined.get("quote_id") for x in irregulars):
            continue

        irregulars.append({
            "quote_id": combined.get("quote_id"),
            "quote_number": combined.get("quote_number"),
            "quote_category": combined.get("quote_category"),
            "quote_type": combined.get("quote_type"),
            "client_name": combined.get("client_name"),
            "client_segment": combined.get("client_segment"),
            "current_status": (combined.get("quote_status") or h.get("quote_status_final") or "Archivada"),
            "total_usd": combined.get("total_usd") or 0,
            "passed_to_project": _is_to_project_trigger(combined.get("archived_trigger")),
            "archived": True,
            "archived_trigger": combined.get("archived_trigger"),
            "phases": _format_phase_timeline(combined),
            "issues": issues,
            "source": "quote_history",
        })

    irregulars.sort(key=lambda x: (x.get("quote_number") or ""), reverse=True)
    return irregulars


@router.get("/reports/sales/irregular-quotes")
async def irregular_quotes_report(
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Lista de cotizaciones con fases sin timestamp esperado.
    Acepta los mismos filtros que el resto del módulo: segmento, categoría, rango de fechas."""
    await get_current_user(authorization)
    match = _build_match(date_from, date_to, segment, category)
    items = await _collect_irregular_quotes(match)

    # KPIs
    by_issue = {}
    passed_to_project = 0
    total_usd = 0.0
    for it in items:
        if it.get("passed_to_project"):
            passed_to_project += 1
        try:
            total_usd += float(it.get("total_usd") or 0)
        except Exception:
            pass
        for iss in it["issues"]:
            by_issue[iss] = by_issue.get(iss, 0) + 1

    return {
        "total_irregular": len(items),
        "passed_to_project": passed_to_project,
        "total_usd": round(total_usd, 2),
        "by_issue": by_issue,
        "items": items,
    }


@router.get("/reports/sales/irregular-quotes/pdf")
async def irregular_quotes_pdf(
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """PDF elegante del reporte de cotizaciones irregulares."""
    user = await get_current_user(authorization)
    match = _build_match(date_from, date_to, segment, category)
    items = await _collect_irregular_quotes(match)

    passed_to_project = sum(1 for it in items if it.get("passed_to_project"))
    by_issue = {}
    total_usd = 0.0
    for it in items:
        try:
            total_usd += float(it.get("total_usd") or 0)
        except Exception:
            pass
        for iss in it["issues"]:
            by_issue[iss] = by_issue.get(iss, 0) + 1

    def fmt_ts(iso: Optional[str]) -> str:
        if not iso:
            return "—"
        try:
            return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        except Exception:
            return str(iso)[:10]

    sections_html = []
    for it in items:
        # Timeline horizontal
        chips = ""
        for ph in it["phases"]:
            if ph.get("subsana"):
                cls = "phase-subsana"
            elif ph["present"]:
                cls = "phase-ok"
            else:
                cls = "phase-missing"
            label = ph["label"] + (" ✓ subsanado" if ph.get("subsana") else "")
            chips += f'<div class="ph {cls}"><div class="ph-label">{label}</div><div class="ph-ts">{fmt_ts(ph["timestamp"])}</div></div>'

        issues_html = " ".join(f'<span class="issue">⚠ {i}</span>' for i in it["issues"])
        proj_badge = '<span class="badge-proj">🚀 Pasó a Proyecto</span>' if it.get("passed_to_project") else ""
        cat = (it.get("quote_category") or "—").capitalize()
        seg = (it.get("client_segment") or "—").upper()
        amount = f"${(it.get('total_usd') or 0):,.2f}"
        # Tipo de Negocio (VPOS/MPOS/Payment/Link)
        qt = (it.get("quote_type") or "").upper()
        type_label_map = {"VPOS": "VPOS", "MPOS": "MPOS", "GATEWAY": "Payment", "LINK": "Link de Pago"}
        type_color_map = {
            "VPOS":    ("#dbeafe", "#1e40af", "#bfdbfe"),
            "MPOS":    ("#d1fae5", "#065f46", "#a7f3d0"),
            "GATEWAY": ("#ede9fe", "#5b21b6", "#ddd6fe"),
            "LINK":    ("#f1f5f9", "#334155", "#e2e8f0"),
        }
        type_label = type_label_map.get(qt, "—") if qt else "—"
        bg, fg, br = type_color_map.get(qt, ("#f8fafc", "#475569", "#e2e8f0"))
        type_badge = (
            f'<span style="display:inline-block; padding:2px 6px; font-size:9px; font-weight:600; '
            f'border-radius:4px; background:{bg}; color:{fg}; border:1px solid {br}; margin-left:6px;">'
            f'{type_label}</span>'
        ) if type_label != "—" else ""

        sections_html.append(f"""
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="qnum">{it.get('quote_number') or '—'}</span>
              {type_badge}
              <span class="muted">·</span>
              <span class="client">{it.get('client_name') or '—'}</span>
              {proj_badge}
            </div>
            <div class="card-meta">
              <span>Categoría: <b>{cat}</b></span>
              <span>Segmento: <b>{seg}</b></span>
              <span>Estado actual: <b>{it.get('current_status')}</b></span>
              <span>Monto: <b>{amount}</b></span>
            </div>
          </div>
          <div class="timeline">{chips}</div>
          <div class="issues">{issues_html}</div>
        </div>
        """)

    if not sections_html:
        sections_html.append('<div class="empty">No se encontraron cotizaciones irregulares con los filtros aplicados. ✅</div>')

    by_issue_chips = " ".join(
        f'<span class="kpi-issue">{n} × {k}</span>' for k, n in sorted(by_issue.items(), key=lambda x: -x[1])
    ) or '<span class="muted">—</span>'

    filters_label = []
    if date_from or date_to:
        filters_label.append(f"Fecha: {date_from or '—'} → {date_to or '—'}")
    if segment and segment != "all":
        filters_label.append(f"Segmento: {segment}")
    if category and category != "all":
        filters_label.append(f"Categoría: {category}")
    filters_str = " · ".join(filters_label) if filters_label else "Sin filtros aplicados"

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    user_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Cotizaciones en Estado Irregular</title>
<style>
  @page {{ size: A4; margin: 16mm 12mm; @bottom-right {{ content: "Pág. " counter(page) " / " counter(pages); font-size: 9px; color: #64748b; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica','Arial',sans-serif; color: #0f172a; font-size: 10px; margin:0; }}
  .cover {{ border-left: 5px solid #f43f5e; padding: 10px 0 14px 16px; margin-bottom: 14px; }}
  .cover h1 {{ font-size: 22px; margin: 0 0 4px 0; color: #0f172a; }}
  .cover p {{ margin: 2px 0; color: #475569; font-size: 10px; }}
  .summary {{ display: flex; gap: 8px; margin: 0 0 14px 0; }}
  .stat {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; }}
  .stat .lbl {{ font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: .4px; }}
  .stat .val {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 2px; }}
  .stat.rose {{ border-left: 4px solid #f43f5e; }}
  .stat.amber {{ border-left: 4px solid #f59e0b; }}
  .stat.violet {{ border-left: 4px solid #8b5cf6; }}
  .stat.slate {{ border-left: 4px solid #64748b; }}
  .by-issue {{ margin: 4px 0 14px 0; font-size: 9.5px; }}
  .kpi-issue {{ display: inline-block; padding: 2px 8px; margin: 0 4px 4px 0; border-radius: 12px; background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; page-break-inside: avoid; background: #fff; }}
  .card-head {{ border-bottom: 1px dashed #e2e8f0; padding-bottom: 4px; margin-bottom: 6px; }}
  .card-title {{ font-size: 11.5px; font-weight: 700; }}
  .card-title .qnum {{ color: #0c4a6e; font-family: monospace; }}
  .card-title .muted {{ color: #cbd5e1; margin: 0 4px; }}
  .card-title .client {{ color: #0f172a; }}
  .card-meta {{ font-size: 9px; color: #475569; display: flex; gap: 12px; margin-top: 2px; }}
  .badge-proj {{ display: inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 12px; background: linear-gradient(90deg,#a78bfa,#7c3aed); color: white; font-size: 8.5px; font-weight: 600; vertical-align: middle; }}
  .timeline {{ display: flex; gap: 4px; margin: 6px 0; flex-wrap: wrap; }}
  .ph {{ flex: 1; min-width: 80px; padding: 4px 6px; border-radius: 4px; text-align: center; border: 1px solid; }}
  .phase-ok {{ background: #ecfdf5; border-color: #a7f3d0; color: #065f46; }}
  .phase-subsana {{ background: #ecfeff; border-color: #67e8f9; color: #0e7490; }}
  .phase-missing {{ background: #fef2f2; border-color: #fecaca; color: #991b1b; }}
  .ph-label {{ font-size: 8.5px; font-weight: 600; }}
  .ph-ts {{ font-size: 8.5px; margin-top: 1px; font-family: monospace; }}
  .issues {{ margin-top: 4px; }}
  .issue {{ display: inline-block; padding: 1px 8px; margin-right: 4px; border-radius: 10px; background: #fef3c7; color: #92400e; border: 1px solid #fde68a; font-size: 9px; }}
  .empty {{ padding: 30px; text-align: center; color: #16a34a; font-size: 13px; }}
  .footer {{ margin-top: 12px; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 8.5px; color: #94a3b8; text-align: center; }}
</style></head>
<body>
  <div class="cover">
    <h1>Cotizaciones en Estado Irregular</h1>
    <p>Cotizaciones cuyo flujo presenta fases avanzadas sin timestamp en fases previas.</p>
    <p>Generado el <b>{now_str}</b> · Por <b>{user_name}</b></p>
    <p><b>Filtros:</b> {filters_str}</p>
  </div>

  <div class="summary">
    <div class="stat rose"><div class="lbl">Cotizaciones irregulares</div><div class="val">{len(items)}</div></div>
    <div class="stat violet"><div class="lbl">Pasadas a Proyecto</div><div class="val">{passed_to_project}</div></div>
    <div class="stat amber"><div class="lbl">Tipos de irregularidad</div><div class="val">{len(by_issue)}</div></div>
    <div class="stat slate"><div class="lbl">Monto total (USD)</div><div class="val">${total_usd:,.0f}</div></div>
  </div>

  <div class="by-issue"><b>Resumen de irregularidades:</b> {by_issue_chips}</div>

  {''.join(sections_html)}

  <div class="footer">MegaNexus · Reporte generado automáticamente · Documento confidencial</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"cotizaciones_irregulares_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =====================================================================
# RESUMEN EJECUTIVO — PDF agregado de los 8 reportes
# =====================================================================

@router.get("/reports/sales/executive-summary")
async def executive_summary_pdf(
    year: int = Query(...),
    segment: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Genera un PDF de resumen ejecutivo (1-2 páginas) consolidando los 8 reportes
    con KPIs y top 5 de cada uno. Útil para envío diario por email/WhatsApp.
    Requiere flag especial `reportes_ventas:executive_summary` o rol admin."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        sp = current_user.get("special_permissions") or []
        if "reportes_ventas:executive_summary" not in sp:
            raise HTTPException(status_code=403, detail="Requiere permiso especial 'Generar Resumen Ejecutivo PDF'.")

    # Reusar las funciones públicas (no las re-llamamos por HTTP, ejecutamos la lógica directa).
    funnel = await funnel_report(date_from, date_to, segment, category, authorization)
    aging = await aging_report(segment, category, authorization)
    monthly = await monthly_report(year, category, segment, authorization)
    receivables = await receivables_report(segment, category, authorization)
    ranking = await clients_ranking_report(year, segment, category, 5, authorization)
    productivity = await repair_productivity_report(date_from, date_to, authorization)
    stock = await stock_vs_demand_report(6, authorization)
    leads = await leads_funnel_report(date_from, date_to, authorization)

    def fmt_usd(n):
        try:
            return "${:,.2f}".format(float(n or 0)).replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "$0,00"

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    user_name = f"{current_user.get('first_name','')} {current_user.get('last_name','')}".strip() or current_user.get("email", "")

    filters_chips = []
    if segment and segment != "all":
        filters_chips.append(f"Segmento: {segment}")
    if category and category != "all":
        filters_chips.append(f"Categoría: {category}")
    if date_from:
        filters_chips.append(f"Desde: {date_from}")
    if date_to:
        filters_chips.append(f"Hasta: {date_to}")
    filters_chips.append(f"Año mensual: {year}")
    chips_html = " · ".join(f'<span class="chip">{c}</span>' for c in filters_chips)

    # ---- Bloques HTML por reporte ----
    funnel_rows = "".join(
        f'<tr><td>{s["stage"]}</td><td class="r">{s["count"]}</td><td class="r">{fmt_usd(s["amount_usd"])}</td></tr>'
        for s in funnel["stages"]
    )

    aging_buckets = "".join(
        f'<tr><td>{b["bucket"]} días</td><td class="r">{b["count"]}</td><td class="r">{fmt_usd(b["amount_usd"])}</td></tr>'
        for b in aging["buckets"]
    )

    monthly_rows = "".join(
        f'<tr><td>{["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][m["month"]-1]}</td>'
        f'<td class="r">{fmt_usd(m["cotizado"])}</td><td class="r">{fmt_usd(m["facturado"])}</td><td class="r">{fmt_usd(m["cobrado"])}</td></tr>'
        for m in monthly["months"] if (m["cotizado"] or m["facturado"] or m["cobrado"])
    ) or '<tr><td colspan="4" class="empty">Sin datos para el año seleccionado</td></tr>'

    rec_buckets = "".join(
        f'<tr><td>{b["bucket"]} días</td><td class="r">{b["count"]}</td><td class="r">{fmt_usd(b["amount_usd"])}</td></tr>'
        for b in receivables["buckets"]
    )
    top_debtors = "".join(
        f'<tr><td>{d["client_name"]}</td><td class="r">{d["invoices"]}</td><td class="r">{fmt_usd(d["amount_usd"])}</td><td class="r">{d["max_days"]}d</td></tr>'
        for d in receivables["top_debtors"][:5]
    ) or '<tr><td colspan="4" class="empty">Sin deudas pendientes</td></tr>'

    ranking_rows = "".join(
        f'<tr><td>{i+1}</td><td>{r["client_name"][:45]}</td><td class="r">{r["quotes_count"]}</td><td class="r">{fmt_usd(r["total_usd"])}</td></tr>'
        for i, r in enumerate(ranking["ranking"][:5])
    ) or '<tr><td colspan="4" class="empty">Sin cotizaciones en el año</td></tr>'

    prod_rows = "".join(
        f'<tr><td>{i["gestor"]}</td><td class="r">{i["count"]}</td>'
        f'<td class="r">{i["avg_repair_hours"] if i["avg_repair_hours"] is not None else "—"}h</td>'
        f'<td class="r">{i["avg_total_days"] if i["avg_total_days"] is not None else "—"}d</td></tr>'
        for i in productivity["by_implementor"][:5]
    ) or '<tr><td colspan="4" class="empty">Sin reparaciones en el período</td></tr>'

    def stock_color(s):
        return {"critical": "#dc2626", "warning": "#d97706", "ok": "#059669"}.get(s, "#64748b")
    stock_rows = "".join(
        f'<tr><td>{s["item_name"][:48]}</td><td class="r">{s["stock"]}</td>'
        f'<td class="r">{s["demand"]}</td>'
        f'<td class="r" style="color:{stock_color(s["status"])};font-weight:bold">{s["status"].upper()}</td></tr>'
        for s in stock["items"][:5]
    )

    leads_origins = "".join(
        f'<tr><td>{o["origin"]}</td><td class="r">{o["total"]}</td><td class="r">{o["converted"]}</td><td class="r">{o["conversion_pct"]}%</td></tr>'
        for o in leads["by_origin"][:5]
    ) or '<tr><td colspan="4" class="empty">Sin leads en el período</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Resumen Ejecutivo de Ventas</title>
<style>
@page {{ size: A4; margin: 12mm; @bottom-center {{ content: "Página " counter(page) " de " counter(pages); font-size: 8px; color: #94a3b8; }} }}
body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 9px; color: #1e293b; }}
h1 {{ font-size: 18px; margin: 0 0 4px 0; color: #0f172a; }}
h2 {{ font-size: 11px; margin: 10px 0 4px 0; padding: 4px 8px; background: #f1f5f9; color: #0f172a; border-left: 3px solid #0ea5e9; }}
.subtitle {{ color: #64748b; font-size: 9px; }}
.chip {{ background: #e0f2fe; color: #075985; padding: 2px 6px; border-radius: 8px; font-size: 8px; margin-right: 4px; }}
.kpis {{ display: flex; gap: 6px; margin: 6px 0 4px; }}
.kpi {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 8px; }}
.kpi .label {{ font-size: 7px; color: #64748b; text-transform: uppercase; font-weight: bold; }}
.kpi .value {{ font-size: 13px; font-weight: bold; color: #0f172a; margin-top: 2px; }}
.kpi.green {{ background: #f0fdf4; border-color: #bbf7d0; }} .kpi.green .value {{ color: #166534; }}
.kpi.red {{ background: #fef2f2; border-color: #fecaca; }} .kpi.red .value {{ color: #991b1b; }}
.kpi.amber {{ background: #fffbeb; border-color: #fde68a; }} .kpi.amber .value {{ color: #92400e; }}
.kpi.blue {{ background: #eff6ff; border-color: #bfdbfe; }} .kpi.blue .value {{ color: #1e40af; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 2px; }}
th, td {{ padding: 3px 6px; text-align: left; border-bottom: 1px solid #f1f5f9; font-size: 8.5px; }}
th {{ background: #f8fafc; font-weight: bold; color: #475569; text-transform: uppercase; font-size: 7px; letter-spacing: 0.4px; }}
td.r, th.r {{ text-align: right; font-family: 'Courier New', monospace; }}
.empty {{ text-align: center; color: #94a3b8; font-style: italic; padding: 8px; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
.section {{ break-inside: avoid; page-break-inside: avoid; }}
header {{ border-bottom: 2px solid #0f172a; padding-bottom: 6px; margin-bottom: 8px; }}
.brand {{ color: #0ea5e9; font-weight: bold; }}
</style></head>
<body>
<header>
  <h1>Resumen Ejecutivo de Ventas</h1>
  <div class="subtitle"><span class="brand">MegaNexus</span> · Generado el {now_str} por {user_name}</div>
  <div style="margin-top:4px">{chips_html}</div>
</header>

<!-- Embudo + KPIs principales -->
<div class="section">
  <h2>1. Embudo de Cotizaciones</h2>
  <div class="kpis">
    <div class="kpi"><div class="label">Cotizaciones</div><div class="value">{funnel["totals"]["quotes_total"]}</div></div>
    <div class="kpi blue"><div class="label">Monto cotizado</div><div class="value">{fmt_usd(funnel["totals"]["amount_total_usd"])}</div></div>
    <div class="kpi green"><div class="label">Conv. Pagada</div><div class="value">{funnel["totals"]["conversion_sent_to_paid"]}%</div></div>
    <div class="kpi blue"><div class="label">Conv. Entregada</div><div class="value">{funnel["totals"]["conversion_sent_to_delivered"]}%</div></div>
  </div>
  <table><thead><tr><th>Etapa</th><th class="r">Cotizaciones</th><th class="r">Monto USD</th></tr></thead><tbody>{funnel_rows}</tbody></table>
</div>

<div class="grid2">
  <!-- Aging -->
  <div class="section">
    <h2>2. Aging de Cotizaciones (pendientes)</h2>
    <table><thead><tr><th>Bucket</th><th class="r">#</th><th class="r">USD</th></tr></thead><tbody>{aging_buckets}</tbody></table>
  </div>
  <!-- Receivables -->
  <div class="section">
    <h2>4. Por Cobrar (Aging facturas)</h2>
    <div class="kpis">
      <div class="kpi red" style="flex:none;width:100%"><div class="label">Total por cobrar</div><div class="value">{fmt_usd(receivables["total_pending_usd"])} ({receivables["total_pending_count"]} facturas)</div></div>
    </div>
    <table><thead><tr><th>Bucket</th><th class="r">#</th><th class="r">USD</th></tr></thead><tbody>{rec_buckets}</tbody></table>
  </div>
</div>

<!-- Mensual -->
<div class="section">
  <h2>3. Ventas Mensuales {year}</h2>
  <div class="kpis">
    <div class="kpi blue"><div class="label">Cotizado</div><div class="value">{fmt_usd(monthly["totals"]["cotizado"])}</div></div>
    <div class="kpi amber"><div class="label">Facturado</div><div class="value">{fmt_usd(monthly["totals"]["facturado"])}</div></div>
    <div class="kpi green"><div class="label">Cobrado</div><div class="value">{fmt_usd(monthly["totals"]["cobrado"])}</div></div>
  </div>
  <table><thead><tr><th>Mes</th><th class="r">Cotizado</th><th class="r">Facturado</th><th class="r">Cobrado</th></tr></thead><tbody>{monthly_rows}</tbody></table>
</div>

<div class="grid2">
  <!-- Top Deudores -->
  <div class="section">
    <h2>4b. Top 5 Deudores</h2>
    <table><thead><tr><th>Cliente</th><th class="r">#</th><th class="r">Monto</th><th class="r">Días</th></tr></thead><tbody>{top_debtors}</tbody></table>
  </div>
  <!-- Top Clientes -->
  <div class="section">
    <h2>5. Top 5 Clientes ({year})</h2>
    <table><thead><tr><th>#</th><th>Cliente</th><th class="r">Cot.</th><th class="r">Total</th></tr></thead><tbody>{ranking_rows}</tbody></table>
  </div>
</div>

<div class="grid2">
  <!-- Productividad -->
  <div class="section">
    <h2>6. Productividad de Reparaciones</h2>
    <div class="kpis">
      <div class="kpi"><div class="label">Reparaciones</div><div class="value">{productivity["sla_total"]}</div></div>
      <div class="kpi red"><div class="label">SLA Breach</div><div class="value">{productivity["sla_breach"]} ({productivity["sla_pct"]}%)</div></div>
    </div>
    <table><thead><tr><th>Gestor</th><th class="r">#</th><th class="r">Avg rep.</th><th class="r">Avg total</th></tr></thead><tbody>{prod_rows}</tbody></table>
  </div>
  <!-- Stock -->
  <div class="section">
    <h2>7. Stock vs. Demanda — Top 5</h2>
    <div class="kpis">
      <div class="kpi red"><div class="label">Crítico</div><div class="value">{stock["summary"]["critical"]}</div></div>
      <div class="kpi amber"><div class="label">Alerta</div><div class="value">{stock["summary"]["warning"]}</div></div>
      <div class="kpi green"><div class="label">OK</div><div class="value">{stock["summary"]["ok"]}</div></div>
    </div>
    <table><thead><tr><th>Ítem</th><th class="r">Stock</th><th class="r">Demanda</th><th class="r">Estado</th></tr></thead><tbody>{stock_rows}</tbody></table>
  </div>
</div>

<!-- Leads -->
<div class="section">
  <h2>8. Funnel de Leads (Contactos Iniciales)</h2>
  <div class="kpis">
    <div class="kpi"><div class="label">Total Leads</div><div class="value">{leads["total_leads"]}</div></div>
    <div class="kpi green"><div class="label">Convertidos</div><div class="value">{leads["converted"]}</div></div>
    <div class="kpi blue"><div class="label">% Conversión</div><div class="value">{leads["conversion_pct"]}%</div></div>
    <div class="kpi"><div class="label">Días promedio</div><div class="value">{leads["avg_convert_days"] if leads["avg_convert_days"] is not None else "—"}</div></div>
  </div>
  <table><thead><tr><th>Origen</th><th class="r">Leads</th><th class="r">Convertidos</th><th class="r">%</th></tr></thead><tbody>{leads_origins}</tbody></table>
</div>

</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"resumen_ejecutivo_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

