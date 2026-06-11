"""Reportes por Patrocinador — Cartera de Proyectos agrupada por Patrocinante.

Agrega los Proyectos de Implementación que nacieron de una cotización
patrocinada (Implementación Patrocinada), agrupándolos por la llave
"Patrocinador" (Banco directo o "Procesador — Banco" compuesto).

Acceso configurable vía Gestión de Seguridad → módulo `reportes_patrocinador`.
"""
import csv
import io
from typing import Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from config import db, require_permission

router = APIRouter()

# Orden canónico de estados para el desglose.
STATUS_ORDER = [
    "Por asignar",
    "Asignado",
    "En Gestión",
    "Suspendido",
    "Implementado parcial",
    "Culminado",
]


def _patrocinador_label(p: dict) -> Optional[str]:
    """Etiqueta del Patrocinador: usa la persistida o la calcula (legacy).
    Escenario A (Directo): "Banco". Escenario B (Compuesto): "Procesador — Banco".
    """
    if p.get("patrocinador_label"):
        return p["patrocinador_label"]
    if not p.get("sponsored_implementation"):
        return None
    bank = (p.get("sponsoring_bank_name") or "").strip()
    if not bank:
        return None
    proc = (p.get("sponsoring_processor_name") or "").strip()
    return f"{proc} — {bank}" if proc else bank


def _build_match(date_from: Optional[str], date_to: Optional[str]) -> dict:
    match = {"sponsored_implementation": True}
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to + "T23:59:59"
        match["created_at"] = rng
    return match


async def _collect(date_from, date_to, sponsor):
    """Devuelve (groups, totals) de la cartera por patrocinador."""
    cursor = db.projects.find(
        _build_match(date_from, date_to),
        {
            "_id": 0, "project_id": 1, "project_number": 1, "client_name": 1,
            "client_segment": 1, "quote_type": 1, "status": 1, "total_usd": 1,
            "created_at": 1, "created_by_name": 1, "assigned_to_name": 1,
            "sponsored_implementation": 1, "sponsoring_bank_name": 1,
            "sponsoring_processor_name": 1, "patrocinador_label": 1,
        },
    )

    groups: dict[str, dict] = {}
    async for p in cursor:
        label = _patrocinador_label(p)
        if not label:
            continue
        if sponsor and sponsor != "all" and label != sponsor:
            continue
        g = groups.setdefault(label, {
            "patrocinador": label,
            "processor_name": (p.get("sponsoring_processor_name") or "").strip() or None,
            "bank_name": (p.get("sponsoring_bank_name") or "").strip() or None,
            "is_composite": bool((p.get("sponsoring_processor_name") or "").strip()),
            "project_count": 0,
            "total_usd": 0.0,
            "status_breakdown": {},
            "projects": [],
        })
        g["project_count"] += 1
        g["total_usd"] += float(p.get("total_usd") or 0)
        st = p.get("status") or "Por asignar"
        g["status_breakdown"][st] = g["status_breakdown"].get(st, 0) + 1
        g["projects"].append({
            "project_id": p.get("project_id"),
            "project_number": p.get("project_number"),
            "client_name": p.get("client_name"),
            "segment": p.get("client_segment"),
            "type": p.get("quote_type"),
            "status": st,
            "total_usd": round(float(p.get("total_usd") or 0), 2),
            "generador": p.get("created_by_name") or "—",
            "implementador": p.get("assigned_to_name") or "—",
            "created_at": p.get("created_at"),
        })

    group_list = sorted(groups.values(), key=lambda x: x["project_count"], reverse=True)
    for g in group_list:
        g["total_usd"] = round(g["total_usd"], 2)
        g["projects"].sort(key=lambda x: x.get("created_at") or "", reverse=True)

    totals = {
        "sponsors": len(group_list),
        "projects": sum(g["project_count"] for g in group_list),
        "total_usd": round(sum(g["total_usd"] for g in group_list), 2),
    }
    return group_list, totals


@router.get("/reports/sponsors")
async def sponsor_portfolio_report(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sponsor: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Cartera de Proyectos agrupada por Patrocinador (Banco o Procesador—Banco)."""
    await require_permission(authorization, "reportes_patrocinador", "read")
    groups, totals = await _collect(date_from, date_to, sponsor)
    # Lista de patrocinadores disponibles (para el filtro del frontend).
    all_groups, _ = await _collect(date_from, date_to, None)
    sponsors_available = [g["patrocinador"] for g in all_groups]
    return {"groups": groups, "totals": totals, "sponsors_available": sponsors_available}


@router.get("/reports/sponsors/csv")
async def sponsor_portfolio_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sponsor: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Exporta la cartera por patrocinador a CSV (auditoría de cuentas)."""
    await require_permission(authorization, "reportes_patrocinador", "read")
    groups, _ = await _collect(date_from, date_to, sponsor)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Patrocinador", "Procesador", "Banco", "N° Proyecto", "Cliente",
        "Segmento", "Tipo", "Estado", "Monto USD", "Generador", "Implementador", "Fecha",
    ])
    for g in groups:
        for pr in g["projects"]:
            writer.writerow([
                g["patrocinador"], g["processor_name"] or "", g["bank_name"] or "",
                pr["project_number"], pr["client_name"], pr["segment"], pr["type"],
                pr["status"], pr["total_usd"], pr["generador"], pr["implementador"],
                (pr["created_at"] or "")[:10],
            ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cartera_por_patrocinador.csv"},
    )
