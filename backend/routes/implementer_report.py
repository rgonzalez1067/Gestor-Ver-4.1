"""Reporte de Gestión de Implementadores (V2).

Todas las métricas están estrictamente acotadas al rango de fechas [date_from, date_to].
Fuentes de fecha por evento:
- Asignados: project.assigned_at
- Culminado/Suspendido/Implementado parcial/En Gestión: bitácora type='status_change' (execution_date)
- PVV (Recibido/Configurado/Testeado/En Producción): celda de implementation_matrix (updated_at) -> processed
- Notificaciones Cliente/Banco: bitácora type='notification' (created_by = emisor, email_detail.target)
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional, List
from datetime import datetime, date, timezone
from pydantic import BaseModel

from config import db, get_current_user

router = APIRouter()

IMPLEMENTATION_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]
PHASE_KEYS = {
    "Recibido": "pvv_recibidos",
    "Configurado": "pvv_configurados",
    "Testeado": "pvv_probados",
    "En Producción": "pvv_produccion",
}


class ImplementerReportRequest(BaseModel):
    date_from: str  # YYYY-MM-DD
    date_to: str    # YYYY-MM-DD
    implementer_ids: List[str] = []  # vacío o ["all"] => todos


def _to_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _in_range(s, d0: date, d1: date) -> bool:
    d = _to_date(s)
    return d is not None and d0 <= d <= d1


def _project_total_cajas(p: dict) -> int:
    try:
        c = int(p.get("cantidad_cajas") or p.get("box_count") or 0)
    except (TypeError, ValueError):
        c = 0
    if c <= 0 and p.get("rifs"):
        c = sum(int(r.get("box_count") or 0) for r in (p.get("rifs") or []))
    return c


def _status_transitions(p: dict):
    out = []
    for e in (p.get("bitacora") or []):
        if e.get("type") == "status_change" and e.get("new_status"):
            out.append((e["new_status"], e.get("execution_date") or e.get("created_at")))
    return out


def _empty_metrics():
    return {
        "asignados": 0,
        "con_ticket": 0,
        "en_gestion": 0,
        "culminados": 0,
        "cajas_culminados": 0,
        "parcial": 0,
        "suspendidos": 0,
        "pvv_recibidos": 0,
        "pvv_configurados": 0,
        "pvv_probados": 0,
        "pvv_produccion": 0,
        "notif_clientes": 0,
        "notif_bancos": 0,
    }


async def _implementers_index():
    """Devuelve dict {user_id: nombre} de implementadores: cargo 'Implementador'
    o usuarios que aparezcan como asignados en algún proyecto."""
    result = {}
    async for u in db.users.find(
        {"cargo": {"$regex": "implementad", "$options": "i"}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "is_active": 1},
    ):
        name = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or u.get("email", "")
        result[u["user_id"]] = name
    # Añadir asignados históricos aunque no tengan el cargo
    async for p in db.projects.find(
        {"assigned_to_user_id": {"$nin": [None, ""]}},
        {"_id": 0, "assigned_to_user_id": 1, "assigned_to_name": 1},
    ):
        uid = p.get("assigned_to_user_id")
        if uid and uid not in result:
            result[uid] = p.get("assigned_to_name") or uid
    return result


@router.get("/reports/implementers/list")
async def list_implementers(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    idx = await _implementers_index()
    items = [{"user_id": uid, "name": name} for uid, name in idx.items()]
    items.sort(key=lambda x: x["name"].lower())
    return {"implementers": items, "total": len(items)}


async def _build_report(payload: ImplementerReportRequest) -> dict:
    d0 = _to_date(payload.date_from)
    d1 = _to_date(payload.date_to)
    if not d0 or not d1:
        raise HTTPException(status_code=400, detail="Rango de fechas inválido (formato YYYY-MM-DD)")
    if d0 > d1:
        raise HTTPException(status_code=400, detail="La fecha 'Desde' no puede ser mayor que 'Hasta'")

    idx = await _implementers_index()
    ids = payload.implementer_ids or []
    if not ids or "all" in ids:
        target_ids = list(idx.keys())
    else:
        target_ids = [i for i in ids if i in idx]
    if not target_ids:
        raise HTTPException(status_code=400, detail="No se encontraron implementadores para el criterio seleccionado")

    projects = await db.projects.find(
        {},
        {"_id": 0, "project_id": 1, "project_number": 1, "assigned_to_user_id": 1,
         "assigned_to_name": 1, "assigned_at": 1, "status": 1, "completed_at": 1,
         "ticket_number": 1, "cantidad_cajas": 1, "box_count": 1, "rifs": 1,
         "bitacora": 1, "implementation_matrix": 1},
    ).to_list(20000)

    results = []
    for impl_id in target_ids:
        m = _empty_metrics()
        assigned = [p for p in projects if p.get("assigned_to_user_id") == impl_id]
        for p in assigned:
            if _in_range(p.get("assigned_at"), d0, d1):
                m["asignados"] += 1
            trans = _status_transitions(p)

            def _has_trans(status):
                return any(st == status and _in_range(dt, d0, d1) for st, dt in trans)

            culm = _has_trans("Culminado")
            if not culm and p.get("status") == "Culminado" and _in_range(p.get("completed_at"), d0, d1):
                culm = True
            if culm:
                m["culminados"] += 1
                m["cajas_culminados"] += _project_total_cajas(p)
            if _has_trans("Implementado parcial"):
                m["parcial"] += 1
            if _has_trans("Suspendido"):
                m["suspendidos"] += 1
            engest = _has_trans("En Gestión")
            assigned_with_ticket = (
                bool((p.get("ticket_number") or "").strip())
                and _in_range(p.get("assigned_at"), d0, d1)
                and p.get("status") in ("En Gestión", "Configurado en espera del Cliente", "Implementado parcial", "Culminado")
            )
            if engest or assigned_with_ticket:
                m["con_ticket"] += 1
                m["en_gestion"] += 1
            matrix = p.get("implementation_matrix") or {}
            if isinstance(matrix, dict):
                for _bank, prods in matrix.items():
                    if not isinstance(prods, dict):
                        continue
                    for _prod, phases in prods.items():
                        if not isinstance(phases, dict):
                            continue
                        for ph in IMPLEMENTATION_PHASES:
                            cell = phases.get(ph)
                            if isinstance(cell, dict) and _in_range(cell.get("updated_at"), d0, d1):
                                try:
                                    proc = int(cell.get("processed") or 0)
                                except (TypeError, ValueError):
                                    proc = 0
                                m[PHASE_KEYS[ph]] += proc

        for p in projects:
            for e in (p.get("bitacora") or []):
                if e.get("type") != "notification" or e.get("created_by") != impl_id:
                    continue
                det = e.get("email_detail") or {}
                dt_s = det.get("sent_at") or e.get("execution_date") or e.get("created_at")
                if not _in_range(dt_s, d0, d1):
                    continue
                tgt = det.get("target")
                if tgt in ("client", "bank_client"):
                    m["notif_clientes"] += 1
                if tgt in ("bank", "bank_client"):
                    m["notif_bancos"] += 1

        results.append({"implementer_id": impl_id, "implementer_name": idx.get(impl_id, impl_id), "metrics": m})

    results.sort(key=lambda x: x["implementer_name"].lower())
    return {
        "date_from": payload.date_from,
        "date_to": payload.date_to,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": results,
    }


@router.post("/reports/implementers/generate")
async def generate_implementer_report(payload: ImplementerReportRequest, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    return await _build_report(payload)


def _fmt_ddmmyyyy(s):
    d = _to_date(s)
    return d.strftime("%d/%m/%Y") if d else str(s)


@router.post("/reports/implementers/generate-pdf")
async def generate_implementer_report_pdf(payload: ImplementerReportRequest, authorization: Optional[str] = Header(None)):
    from fastapi.responses import StreamingResponse
    await get_current_user(authorization)
    data = await _build_report(payload)
    pdf = _render_report_pdf(data)
    filename = f"Reporte_Implementadores_{payload.date_from}_{payload.date_to}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
