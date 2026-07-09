"""
Matriz Financiera Consolidada por tipo_corp para la aprobación de cotizaciones
Corporativas (VPOS / VPOS_MULTIRIF / MPOS / MPOS Imple+POS).

La matriz cruza:
  - Filas: Setup / Recurrentes / Ambos (Total).
  - Columnas: Derecho de Uso, Infraestructura (bloque "Hardware y Software"),
    Apoyo Técnico, Soporte y Monitoreo (bloque "Consultoría") + Total USD.

Montos NETOS (no incluyen IVA). Los valores en Bs. se derivan multiplicando el
monto USD por la tasa de cambio.

Se comparte entre el modal de aprobación (vía endpoint), el cuerpo HTML del
correo a Administración y el PDF de Cálculos Definitivos, para garantizar que
las tres superficies muestren exactamente la misma data que visó el aprobador.
"""
from typing import Optional

CORP_COLUMNS = ["Derecho de Uso", "Infraestructura", "Apoyo Técnico", "Soporte y Monitoreo"]

_ELIGIBLE_TYPES = {"VPOS", "VPOS_MULTIRIF", "MPOS", "FAST_TRACK"}


def is_corp_matrix_eligible(quote: dict) -> bool:
    """Elegible si es Corporativo (segmento CORP o creador de Ventas Corporativas)
    y el tipo de cotización pertenece a las líneas VPOS/VPOS_MULTIRIF/MPOS/FAST_TRACK."""
    seg = (quote.get("client_segment") or "").upper()
    dept = (quote.get("creator_departamento") or "").lower()
    is_corp = seg == "CORP" or "corporativ" in dept
    if not is_corp:
        return False
    qt = (quote.get("quote_type") or "").upper()
    cat = (quote.get("quote_category") or "").lower()
    return qt in _ELIGIBLE_TYPES or cat == "fast_track"


def _item_total_usd(s: dict) -> float:
    v = s.get("total_usd")
    if v is None:
        v = s.get("subtotal_usd")
    if v is None:
        unit = s.get("unit_price_usd") or s.get("price") or 0
        qty = s.get("quantity") or 1
        v = unit * qty
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def compute_corp_billing_matrix(quote: dict, tipo_corp_map: Optional[dict] = None) -> dict:
    """Calcula setup_by_corp y recurring_by_corp (USD netos) clasificando los
    `services` de la cotización por tipo_corp. `tipo_corp_map` resuelve el
    tipo_corp por nombre de concepto cuando el item no lo trae explícito."""
    tipo_corp_map = tipo_corp_map or {}
    setup_by_corp = {c: 0.0 for c in CORP_COLUMNS}
    recurring_by_corp = {c: 0.0 for c in CORP_COLUMNS}
    col_lookup = {c.lower().strip(): c for c in CORP_COLUMNS}

    for s in (quote.get("services") or []):
        total = _item_total_usd(s)
        if total == 0:
            continue
        tc = (s.get("tipo_corp") or "").strip()
        if not tc:
            name = (s.get("item_name") or s.get("name") or "").lower().strip()
            tc = tipo_corp_map.get(name, "")
        col = col_lookup.get(tc.lower().strip()) if tc else None
        if not col:
            continue
        item_type = (s.get("item_type") or "").lower()
        if item_type in ("recurring_basic", "recurring_other"):
            recurring_by_corp[col] += total
        else:
            setup_by_corp[col] += total

    return {
        "columns": CORP_COLUMNS,
        "setup_by_corp": setup_by_corp,
        "recurring_by_corp": recurring_by_corp,
        "setup_total_usd": sum(setup_by_corp.values()),
        "recurring_total_usd": sum(recurring_by_corp.values()),
    }


def _fmt(value_usd: float, currency: str, rate: float) -> str:
    if (currency or "USD").upper() == "BS":
        bs = value_usd * (rate or 0)
        return f"Bs. {bs:,.2f}"
    return f"${value_usd:,.2f}"


def resolve_matrix_rows(bm: dict):
    """Devuelve la lista de filas activas a renderizar según row_mode + la fila TOTAL.
    Cada fila: (label, {col: usd}, total_usd)."""
    row_mode = (bm.get("row_mode") or "both").lower()
    setup = bm.get("setup_by_corp") or {}
    recurring = bm.get("recurring_by_corp") or {}
    cols = bm.get("columns") or CORP_COLUMNS

    rows = []
    show_setup = row_mode in ("both", "setup")
    show_rec = row_mode in ("both", "recurring")
    if show_setup:
        rows.append(("Setup", setup, sum(setup.get(c, 0) for c in cols)))
    if show_rec:
        rows.append(("Recurrentes", recurring, sum(recurring.get(c, 0) for c in cols)))

    total_by_col = {c: (setup.get(c, 0) if show_setup else 0) + (recurring.get(c, 0) if show_rec else 0) for c in cols}
    total_general = sum(total_by_col.values())
    return rows, total_by_col, total_general


def build_corp_matrix_html(bm: dict) -> str:
    """Construye el bloque HTML de la Matriz Financiera Consolidada para el correo."""
    if not bm:
        return ""
    currency = (bm.get("currency") or "USD").upper()
    rate = float(bm.get("exchange_rate") or 0)
    cols = bm.get("columns") or CORP_COLUMNS
    rows, total_by_col, total_general = resolve_matrix_rows(bm)

    cur_label = "Bs." if currency == "BS" else "USD ($)"
    th = "style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#fff;background:#00447C;text-align:center'"
    th_sub = "style='border:1px solid #cbd5e1;padding:6px 8px;font-size:11px;color:#fff;background:#336699;text-align:center'"
    td = "style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#1e293b;text-align:right'"
    td_lbl = "style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#00447C;font-weight:700;text-align:left'"

    header = (
        f"<tr>"
        f"<th rowspan='2' {th}>Concepto</th>"
        f"<th colspan='2' {th}>Hardware y Software</th>"
        f"<th colspan='2' {th}>Consultoría</th>"
        f"<th rowspan='2' {th}>Total ({cur_label})</th>"
        f"</tr>"
        f"<tr>"
        + "".join(f"<th {th_sub}>{c}</th>" for c in cols)
        + "</tr>"
    )

    body_rows = ""
    for label, by_col, row_total in rows:
        cells = "".join(f"<td {td}>{_fmt(by_col.get(c, 0), currency, rate)}</td>" for c in cols)
        body_rows += f"<tr><td {td_lbl}>{label}</td>{cells}<td {td} ><b>{_fmt(row_total, currency, rate)}</b></td></tr>"

    total_cells = "".join(
        f"<td style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#fff;background:#1E293B;text-align:right;font-weight:700'>{_fmt(total_by_col.get(c, 0), currency, rate)}</td>"
        for c in cols
    )
    total_row = (
        f"<tr>"
        f"<td style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#fff;background:#1E293B;font-weight:700;text-align:left'>TOTAL GENERAL</td>"
        f"{total_cells}"
        f"<td style='border:1px solid #cbd5e1;padding:8px 10px;font-size:12px;color:#1E293B;background:#F59E0B;text-align:right;font-weight:700'>{_fmt(total_general, currency, rate)}</td>"
        f"</tr>"
    )

    rate_note = f" · Tasa: Bs. {rate:,.2f}/$" if currency == "BS" and rate else ""
    return (
        "<div style='margin:18px 0'>"
        "<p style='margin:0 0 8px;font-size:13px;color:#00447C;font-weight:700;text-transform:uppercase;letter-spacing:.4px'>Instrucciones de Facturación</p>"
        "<table style='border-collapse:collapse;width:100%'>"
        f"<thead>{header}</thead>"
        f"<tbody>{body_rows}{total_row}</tbody>"
        "</table>"
        f"<p style='margin:6px 0 0;font-size:11px;color:#64748b'>Montos no incluyen IVA{rate_note}.</p>"
        "</div>"
    )
