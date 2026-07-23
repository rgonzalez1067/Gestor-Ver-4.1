"""Reporte de Gestión de Implementadores (V2).

Todas las métricas están estrictamente acotadas al rango de fechas [date_from, date_to].
Fuentes de fecha por evento:
- Asignados: project.assigned_at
- Culminado/Suspendido/Implementado parcial/En Gestión: bitácora type='status_change' (execution_date)
- PVV (Recibido/Configurado/Testeado/En Producción): celda de implementation_matrix (updated_at) -> processed
- Notificaciones Cliente/Banco: bitácora type='notification' (created_by = emisor, email_detail.target)
"""
import io
from fastapi import APIRouter, Header, HTTPException
from typing import Optional, List
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel

from config import db, get_current_user, UPLOADS_DIR

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


# --- Grupos de métricas para el PDF (mismo orden que la UI) ---
_PDF_GROUPS = [
    ("A. Gestión de Proyectos de Integración", [
        ("asignados", "Proyectos Asignados"),
        ("con_ticket", "Proyectos con Ticket Asignado"),
        ("en_gestion", "Proyectos en Gestión"),
        ("culminados", "Proyectos Culminados"),
        ("cajas_culminados", "Cajas en proyectos culminados"),
        ("parcial", "Proyectos implementados parcialmente"),
        ("suspendidos", "Proyectos Suspendidos"),
    ]),
    ("B. Puntos de Venta Virtuales (PVV)", [
        ("pvv_recibidos", "PVV Recibidos"),
        ("pvv_configurados", "PVV Configurados"),
        ("pvv_probados", "PVV Probados"),
        ("pvv_produccion", "PVV en Producción"),
    ]),
    ("C. Notificaciones y Comunicaciones", [
        ("notif_clientes", "Notificaciones a Clientes"),
        ("notif_bancos", "Notificaciones a Bancos"),
    ]),
]

_ACCENT = "#4f46e5"       # indigo-600
_ACCENT_DARK = "#3730a3"  # indigo-800
_LIGHT = "#eef2ff"        # indigo-50
_BORDER = "#e2e8f0"       # slate-200


def _metrics_table(metrics: dict):
    """Construye una única tabla con las 13 métricas agrupadas por sección."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle

    rows = []
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor(_BORDER)),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(_BORDER)),
    ]
    r = 0
    for title, items in _PDF_GROUPS:
        rows.append([title, ""])
        style_cmds += [
            ("SPAN", (0, r), (1, r)),
            ("BACKGROUND", (0, r), (1, r), colors.HexColor(_ACCENT)),
            ("TEXTCOLOR", (0, r), (1, r), colors.white),
            ("FONTNAME", (0, r), (1, r), "Helvetica-Bold"),
            ("FONTSIZE", (0, r), (1, r), 10),
        ]
        r += 1
        for key, label in items:
            rows.append([label, str(metrics.get(key, 0))])
            style_cmds += [
                ("ALIGN", (1, r), (1, r), "RIGHT"),
                ("FONTNAME", (1, r), (1, r), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, r), (1, r), colors.HexColor(_ACCENT_DARK)),
            ]
            r += 1
    t = Table(rows, colWidths=[125 * mm, 40 * mm])
    t.setStyle(TableStyle(style_cmds))
    return t


def _render_report_pdf(data: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, HRFlowable,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Reporte de Gestión de Implementadores",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "corpTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=15, textColor=colors.HexColor(_ACCENT_DARK), leading=18,
    )
    sub_style = ParagraphStyle(
        "corpSub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, textColor=colors.HexColor("#64748b"), leading=13,
    )
    impl_style = ParagraphStyle(
        "implName", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=13, textColor=colors.HexColor("#0f172a"), leading=16,
    )
    period_style = ParagraphStyle(
        "period", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor("#64748b"), leading=12,
    )

    # --- Encabezado corporativo (logo + título) ---
    logo_file = UPLOADS_DIR / "logo.png"
    header_text = [
        Paragraph("Reporte de Gestión de Implementadores", title_style),
    ]
    if logo_file.exists():
        try:
            img = Image(str(logo_file))
            iw, ih = img.imageWidth, img.imageHeight
            target_h = 16 * mm
            img.drawHeight = target_h
            img.drawWidth = iw * (target_h / ih)
            header_row = Table([[img, header_text]], colWidths=[42 * mm, 132 * mm])
        except Exception:
            header_row = Table([["", header_text]], colWidths=[0, 174 * mm])
    else:
        header_row = Table([[header_text]], colWidths=[174 * mm])
    header_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    gen_str = ""
    try:
        gen_dt = datetime.fromisoformat(data["generated_at"]).astimezone(ZoneInfo("America/Caracas"))
        gen_str = gen_dt.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        gen_str = str(data.get("generated_at", ""))
    period_line = (
        f"Periodo consultado: <b>{_fmt_ddmmyyyy(data['date_from'])}</b> "
        f"al <b>{_fmt_ddmmyyyy(data['date_to'])}</b>  ·  Generado: {gen_str}"
    )

    def _build_header():
        return [
            header_row,
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=1.2, color=colors.HexColor(_ACCENT)),
            Spacer(1, 4),
            Paragraph(period_line, period_style),
            Spacer(1, 12),
        ]

    story = []
    results = data.get("results", [])

    for i, r in enumerate(results):
        if i > 0:
            story.append(PageBreak())
        story += _build_header()
        story.append(Paragraph(r.get("implementer_name", ""), impl_style))
        story.append(Spacer(1, 8))
        story.append(_metrics_table(r.get("metrics", {})))

    # --- Resumen consolidado (suma de todos) ---
    if results:
        totals = _empty_metrics()
        for r in results:
            for k, v in (r.get("metrics") or {}).items():
                if k in totals:
                    totals[k] += int(v or 0)
        story.append(PageBreak())
        story += _build_header()
        story.append(Paragraph(
            f"Resumen Consolidado — {len(results)} implementador(es)", impl_style))
        story.append(Spacer(1, 8))
        story.append(_metrics_table(totals))

    if not story:
        story.append(Paragraph("Sin datos para el criterio seleccionado.", sub_style))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(18 * mm, 10 * mm, "Megasoft · Reporte de Gestión de Implementadores")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()


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
