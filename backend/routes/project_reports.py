"""
Reporte Dinámico de Estatus / Avance de Proyectos.
- GET /api/projects/{project_id}/report/avance        → JSON consolidado con filtros.
- GET /api/projects/{project_id}/report/avance/pdf    → PDF elegante (línea gráfica MegaNexus).

Filtros (query params, opcionales y combinables):
  - banks=Banco1,Banco2          (lista coma-separada de bank_name)
  - products=Prod1,Prod2          (lista coma-separada de product_name)
  - store_id=st_xxx | all         (solo aplica a proyectos multistore)
"""
import io
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
import weasyprint

from config import db, get_current_user

router = APIRouter()

PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _filter_matrix(matrix: dict, banks: List[str], products: List[str]) -> dict:
    """Filtra una implementation_matrix por bancos y productos seleccionados."""
    if not isinstance(matrix, dict):
        return {}
    out = {}
    for bank, bank_products in matrix.items():
        if banks and bank not in banks:
            continue
        bank_filtered = {}
        for prod, phases in (bank_products or {}).items():
            if products and prod.strip() not in [p.strip() for p in products]:
                continue
            bank_filtered[prod] = phases or {}
        if bank_filtered:
            out[bank] = bank_filtered
    return out


def _aggregate_phases(matrices: list) -> dict:
    """Recibe una lista de implementation_matrix (ya filtradas) y calcula totales por fase.
    El 'expected' de cada fase es la suma de los terminales esperados por producto
    (cada terminal pasa por TODAS las fases, así que el expected por fase = expected del producto).
    Devuelve: {phase: {expected, processed, percent, completed_count, total_items}}"""
    totals = {ph: {"expected": 0, "processed": 0, "completed_count": 0, "total_items": 0} for ph in PHASES}
    for matrix in matrices:
        for _bank, products in (matrix or {}).items():
            for _prod, phases in (products or {}).items():
                # El "expected" del producto = máximo entre todas las fases (típicamente coinciden,
                # pero si alguna fase no fue inicializada, el max representa el total real).
                product_expected = 0
                for ph in PHASES:
                    info = (phases or {}).get(ph) or {}
                    e = int(info.get("expected") or 0)
                    if e > product_expected:
                        product_expected = e
                if product_expected == 0:
                    continue  # producto sin terminales esperados → no se cuenta
                for ph in PHASES:
                    info = (phases or {}).get(ph) or {}
                    processed = int(info.get("processed") or 0)
                    completed = bool(info.get("completed"))
                    totals[ph]["expected"] += product_expected
                    totals[ph]["processed"] += processed
                    totals[ph]["total_items"] += 1
                    if completed:
                        totals[ph]["completed_count"] += 1

    for ph in PHASES:
        e = totals[ph]["expected"] or 0
        p = totals[ph]["processed"] or 0
        totals[ph]["percent"] = round((p / e) * 100, 1) if e > 0 else 0.0
    return totals


def _build_matrix_rows(matrices_by_label: list, banks: List[str], products: List[str]) -> list:
    """Construye filas detalladas para la tabla del reporte.
    matrices_by_label: [(label, matrix), ...] — label = nombre tienda o '—' para single.
    """
    rows = []
    for label, matrix in matrices_by_label:
        for bank, bank_products in (matrix or {}).items():
            for prod, phases in (bank_products or {}).items():
                row = {
                    "store_label": label,
                    "bank": bank,
                    "product": prod.strip(),
                    "phases": {},
                }
                for ph in PHASES:
                    info = (phases or {}).get(ph) or {}
                    expected = int(info.get("expected") or 0)
                    processed = int(info.get("processed") or 0)
                    row["phases"][ph] = {
                        "expected": expected,
                        "processed": processed,
                        "completed": bool(info.get("completed")),
                        "percent": round((processed / expected) * 100, 1) if expected > 0 else 0.0,
                    }
                rows.append(row)
    return rows


async def _load_project_with_filters(project_id: str, banks_csv: Optional[str], products_csv: Optional[str], stores_csv: Optional[str]):
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    banks_filter = _split_csv(banks_csv)
    products_filter = _split_csv(products_csv)
    stores_filter = [s for s in _split_csv(stores_csv) if s and s != "all"]

    project_type = proj.get("project_type", "single")

    # Recolectar matrices a evaluar
    matrices_by_label = []  # [(label, matrix)]
    if project_type == "multistore":
        for st in (proj.get("stores") or []):
            if stores_filter and st.get("store_id") not in stores_filter:
                continue
            label = st.get("name") or st.get("store_id") or "—"
            mat = _filter_matrix(st.get("implementation_matrix") or {}, banks_filter, products_filter)
            if mat:
                matrices_by_label.append((label, mat))
    else:
        mat = _filter_matrix(proj.get("implementation_matrix") or {}, banks_filter, products_filter)
        if mat:
            matrices_by_label.append(("—", mat))

    return proj, matrices_by_label, {
        "banks": banks_filter,
        "products": products_filter,
        "stores": stores_filter if stores_filter else ["all"],
    }


def _project_header(proj: dict) -> dict:
    return {
        "client_name": proj.get("client_name"),
        "client_segment": proj.get("client_segment"),
        "ticket_number": proj.get("ticket_number"),
        "project_number": proj.get("project_number"),
        "quote_number": proj.get("quote_number"),
        "integrator_name": proj.get("integrator_name"),
        "integrator_app_name": proj.get("integrator_app_name"),
        "assigned_to_name": proj.get("assigned_to_name"),
        "assigned_at": proj.get("fecha_asignacion") or proj.get("assigned_at"),
        "status": proj.get("status"),
        "project_type": proj.get("project_type"),
    }


@router.get("/projects/{project_id}/report/avance")
async def project_progress_report(
    project_id: str,
    banks: Optional[str] = Query(None, description="Lista coma-separada de bank_name"),
    products: Optional[str] = Query(None, description="Lista coma-separada de product_name"),
    stores: Optional[str] = Query(None, description="Lista coma-separada de store_id"),
    store_id: Optional[str] = Query(None, description="(deprecated) un solo store_id; usar 'stores'"),
    authorization: Optional[str] = Header(None),
):
    """Devuelve el reporte en JSON: encabezado + matriz filtrada + totales por fase."""
    await get_current_user(authorization)
    stores_csv = stores or store_id
    proj, matrices_by_label, filters = await _load_project_with_filters(project_id, banks, products, stores_csv)

    header = _project_header(proj)
    rows = _build_matrix_rows(matrices_by_label, filters["banks"], filters["products"])
    totals = _aggregate_phases([m for _l, m in matrices_by_label])

    # Catálogos disponibles para popular la pantalla de filtros (no filtrados)
    available_banks = []
    available_products = []
    available_stores = []
    if proj.get("project_type") == "multistore":
        for st in (proj.get("stores") or []):
            available_stores.append({"store_id": st.get("store_id"), "name": st.get("name"), "box_count": st.get("box_count", 0)})
            for b, ps in ((st.get("implementation_matrix") or {})).items():
                if b not in available_banks:
                    available_banks.append(b)
                for p in (ps or {}).keys():
                    p_clean = p.strip()
                    if p_clean not in available_products:
                        available_products.append(p_clean)
    else:
        for b, ps in (proj.get("implementation_matrix") or {}).items():
            if b not in available_banks:
                available_banks.append(b)
            for p in (ps or {}).keys():
                p_clean = p.strip()
                if p_clean not in available_products:
                    available_products.append(p_clean)

    return {
        "header": header,
        "filters": filters,
        "available": {
            "banks": sorted(available_banks),
            "products": sorted(available_products),
            "stores": available_stores,
        },
        "totals": totals,
        "rows": rows,
        "row_count": len(rows),
    }


def _phase_cell_html(info: dict) -> str:
    """Render una celda de fase con estilo (verde si completa, gris si vacía, color por progreso)."""
    expected = info["expected"]
    processed = info["processed"]
    pct = info["percent"]
    if expected == 0:
        return '<td class="ph empty">—</td>'
    if info["completed"] or pct >= 100:
        cls = "ph done"
    elif pct >= 50:
        cls = "ph mid"
    elif pct > 0:
        cls = "ph low"
    else:
        cls = "ph zero"
    return f'<td class="{cls}"><div class="num">{processed}/{expected}</div><div class="pct">{pct:g}%</div></td>'


@router.get("/projects/{project_id}/report/avance/pdf")
async def project_progress_report_pdf(
    project_id: str,
    banks: Optional[str] = Query(None),
    products: Optional[str] = Query(None),
    stores: Optional[str] = Query(None),
    store_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Genera PDF elegante con membrete MegaNexus."""
    user = await get_current_user(authorization)
    stores_csv = stores or store_id
    proj, matrices_by_label, filters = await _load_project_with_filters(project_id, banks, products, stores_csv)
    header = _project_header(proj)
    rows = _build_matrix_rows(matrices_by_label, filters["banks"], filters["products"])
    totals = _aggregate_phases([m for _l, m in matrices_by_label])

    # Helpers
    def fmt_dt(iso):
        if not iso:
            return "—"
        try:
            return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%d/%m/%Y")
        except Exception:
            return str(iso)[:10]

    is_multi = proj.get("project_type") == "multistore"

    # Tabla principal
    body_rows_html = ""
    if not rows:
        body_rows_html = f'<tr><td colspan="{(7 if is_multi else 6)}" class="empty-row">No hay datos para los filtros aplicados.</td></tr>'
    else:
        last_store = None
        for r in rows:
            if is_multi and r["store_label"] != last_store:
                body_rows_html += f'<tr class="store-row"><td colspan="{6 if is_multi else 5}">🏬 {r["store_label"]}</td></tr>'
                last_store = r["store_label"]
            phase_cells = "".join(_phase_cell_html(r["phases"][ph]) for ph in PHASES)
            body_rows_html += (
                f'<tr><td class="bank">{r["bank"]}</td><td class="prod">{r["product"]}</td>{phase_cells}</tr>'
            )

    # Filtros aplicados
    filt_chips = []
    if filters["banks"]:
        filt_chips.append(f"Bancos: {', '.join(filters['banks'])}")
    if filters["products"]:
        filt_chips.append(f"Productos: {', '.join(filters['products'])}")
    if filters["stores"] and filters["stores"] != ["all"]:
        names = []
        for sid in filters["stores"]:
            st_match = next((s for s in (proj.get("stores") or []) if s.get("store_id") == sid), None)
            names.append((st_match or {}).get("name", sid))
        filt_chips.append(f"Tiendas: {', '.join(names)}")
    filters_str = " · ".join(filt_chips) if filt_chips else "Todo el Proyecto (sin filtros)"

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    user_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Reporte de Avance — {header.get('project_number')}</title>
<style>
  @page {{ size: A4 landscape; margin: 14mm 12mm; @bottom-right {{ content: "Pág. " counter(page) " / " counter(pages); font-size: 9px; color: #64748b; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica','Arial',sans-serif; color: #0f172a; font-size: 10px; margin:0; }}
  .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 3px solid #0c4a6e; padding-bottom: 10px; margin-bottom: 12px; }}
  .brand {{ font-size: 22px; font-weight: 800; color: #0c4a6e; letter-spacing: -0.5px; }}
  .brand .sub {{ display: block; font-size: 10px; font-weight: 500; color: #64748b; letter-spacing: 1px; margin-top: 2px; }}
  .meta-right {{ text-align: right; font-size: 9px; color: #475569; }}
  .meta-right .title {{ font-size: 14px; font-weight: 700; color: #0c4a6e; margin-bottom: 4px; }}
  .info-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px 14px; padding: 8px 12px; background: #f1f5f9; border-radius: 6px; margin-bottom: 12px; }}
  .info-cell .lbl {{ font-size: 8.5px; color: #64748b; text-transform: uppercase; letter-spacing: .4px; }}
  .info-cell .val {{ font-size: 10.5px; font-weight: 700; color: #0f172a; margin-top: 1px; word-break: break-word; }}
  .filters-bar {{ font-size: 9.5px; color: #475569; padding: 4px 0 8px 0; border-bottom: 1px dashed #cbd5e1; margin-bottom: 8px; }}
  .filters-bar b {{ color: #0c4a6e; }}
  .summary {{ display: flex; gap: 6px; margin-bottom: 10px; }}
  .summary .box {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 10px; text-align: center; }}
  .summary .box .ph {{ font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: .4px; }}
  .summary .box .vals {{ font-size: 16px; font-weight: 700; color: #0f172a; margin: 2px 0; }}
  .summary .box .pct {{ font-size: 11px; color: #0c4a6e; font-weight: 600; }}
  .summary .box.done {{ background: #ecfdf5; border-color: #a7f3d0; }}
  .summary .box.mid {{ background: #fef9c3; border-color: #fde68a; }}
  .summary .box.low {{ background: #fee2e2; border-color: #fecaca; }}
  table.matrix {{ width: 100%; border-collapse: collapse; }}
  table.matrix thead th {{ background: #0c4a6e; color: white; font-size: 9.5px; padding: 6px 8px; text-align: left; font-weight: 600; }}
  table.matrix thead th.ph {{ text-align: center; }}
  table.matrix tbody td {{ padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; vertical-align: middle; }}
  table.matrix tbody td.bank {{ font-weight: 600; color: #0f172a; }}
  table.matrix tbody td.prod {{ color: #334155; }}
  td.ph {{ text-align: center; font-size: 10px; line-height: 1.1; min-width: 70px; }}
  td.ph .num {{ font-weight: 700; }}
  td.ph .pct {{ font-size: 8.5px; color: #64748b; }}
  td.ph.done {{ background: #d1fae5; color: #065f46; }}
  td.ph.done .pct {{ color: #047857; font-weight: 600; }}
  td.ph.mid  {{ background: #fef3c7; color: #92400e; }}
  td.ph.low  {{ background: #fee2e2; color: #991b1b; }}
  td.ph.zero {{ background: #f1f5f9; color: #94a3b8; }}
  td.ph.empty {{ color: #cbd5e1; text-align: center; }}
  tr.store-row td {{ background: #e0f2fe; color: #075985; font-weight: 700; padding: 4px 8px; font-size: 10px; }}
  td.empty-row {{ text-align: center; padding: 18px; color: #94a3b8; font-style: italic; }}
  .footer {{ margin-top: 12px; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 8.5px; color: #94a3b8; text-align: center; }}
</style></head>
<body>
  <div class="header">
    <div>
      <div class="brand">MegaNexus<span class="sub">GESTIÓN DE IMPLEMENTACIÓN</span></div>
    </div>
    <div class="meta-right">
      <div class="title">Reporte de Estatus / Avance</div>
      <div>Generado: <b>{now_str}</b></div>
      <div>Por: <b>{user_name}</b></div>
    </div>
  </div>

  <div class="info-grid">
    <div class="info-cell"><div class="lbl">Cliente</div><div class="val">{header.get('client_name') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Nro. Ticket</div><div class="val">{header.get('ticket_number') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Nro. Proyecto</div><div class="val">{header.get('project_number') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Cotización</div><div class="val">{header.get('quote_number') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Integrador</div><div class="val">{header.get('integrator_name') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Aplicativo</div><div class="val">{header.get('integrator_app_name') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Implementador</div><div class="val">{header.get('assigned_to_name') or '—'}</div></div>
    <div class="info-cell"><div class="lbl">Fecha Asignación</div><div class="val">{fmt_dt(header.get('assigned_at'))}</div></div>
  </div>

  <div class="filters-bar"><b>Filtros aplicados:</b> {filters_str}</div>

  <div class="summary">
    {"".join(
        f'<div class="box {"done" if totals[ph]["percent"]>=100 else "mid" if totals[ph]["percent"]>=50 else "low"}">'
        f'<div class="ph">{ph}</div>'
        f'<div class="vals">{totals[ph]["processed"]}/{totals[ph]["expected"]}</div>'
        f'<div class="pct">{totals[ph]["percent"]:g}%</div>'
        f'</div>' for ph in PHASES
    )}
  </div>

  <table class="matrix">
    <thead>
      <tr>
        <th>Banco / Ente</th>
        <th>Producto</th>
        {"".join(f'<th class="ph">{ph}</th>' for ph in PHASES)}
      </tr>
    </thead>
    <tbody>{body_rows_html}</tbody>
  </table>

  <div class="footer">MegaNexus · Reporte de Avance generado automáticamente · Documento confidencial</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"avance_{(header.get('project_number') or 'proyecto')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
