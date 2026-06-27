"""
Resolución dinámica de variables para plantillas de email del módulo de Proyectos.
Variables:
  {Nombre_Cliente}          → clientes.razon_social
  {Contacto_Principal}      → Primer contacto del cliente (nombre + apellido)
  {Nombre_Sucursal}         → Nombre(s) de sucursal(es) del proyecto
  {Cantidad_Cajas}          → Cajas por sucursal
  {Integrador}              → Nombre del integrador asignado
  {Matriz_Bancos_Productos} → Tabla HTML con Banco | Producto/Servicio | Cantidad
  + variables existentes del proyecto (ticket, quote_number, etc.)
"""
import logging
from config import db
from services.rif_formatter import format_rif

logger = logging.getLogger(__name__)


def _build_matrix_html(implementation_matrix: dict, services: list = None, bank_filter: str = None) -> str:
    """Genera la tabla HTML de Bancos y Productos desde implementation_matrix.

    Homologada estéticamente con {Matriz_Seguimiento_Evolutiva}: misma paleta
    corporativa (encabezado #1f3a5f, banda de banco #dbeafe con borde izquierdo
    azul, bordes #d8dee9), tipografía y padding. Cada banco se renderiza como un
    bloque independiente con su título y tabla (Producto/Servicio · Cantidad).

    `services` (opcional): si se provee, la columna Cantidad refleja `cantidad_cajas`
    real del item (banco, producto) de la cotización; si no, cae a 1.
    `bank_filter` (opcional): si se especifica, SOLO se emite el bloque de ese banco
    (match case-insensitive) — filtrado automático para envíos dirigidos a un Banco
    específico (confidencialidad interbancaria), sin intervención manual.
    """
    if not implementation_matrix:
        return ('<p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:6px 0;">'
                '<em>Sin matriz de implementación definida.</em></p>')

    # Indexar cantidades reales por (banco, producto) desde services
    qty_lookup = {}
    if services:
        for s in services:
            if s.get("item_type") not in ("additional", None):
                continue
            bn = (s.get("bank_name") or "").strip()
            name = (s.get("item_name") or s.get("name") or "").strip()
            if not bn or not name:
                continue
            cajas = s.get("cantidad_cajas") or s.get("quantity") or 0
            try:
                cajas = int(cajas)
            except (TypeError, ValueError):
                cajas = 0
            key = (bn.lower(), name.lower())
            qty_lookup[key] = qty_lookup.get(key, 0) + max(0, cajas)

    # Agrupar por banco, aplicando el filtro de banco si corresponde.
    bf = (bank_filter or "").strip().lower()
    from collections import OrderedDict
    bank_products = OrderedDict()
    for bank_name, products in implementation_matrix.items():
        if bf and (bank_name or "").strip().lower() != bf:
            continue
        prods = [p for p in (products or {}).keys()]
        if prods:
            bank_products[bank_name] = prods

    if not bank_products:
        msg = "Sin productos asociados para el destinatario." if bank_filter else "Sin productos en la matriz."
        return (f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:6px 0;">'
                f'<em>{msg}</em></p>')

    bd = "border:1px solid #d8dee9;"
    scope = f' · Banco: {bank_filter}' if bank_filter else ''
    caption = (f'<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">'
               f'Matriz de Bancos y Productos{scope}</div>')

    blocks = []
    for bank_name, prods in bank_products.items():
        head = ('<thead><tr style="background:#1f3a5f;color:#fff;">'
                f'<th style="padding:7px 10px;{bd}text-align:left;font-size:12px;font-weight:700;">Producto / Servicio</th>'
                f'<th style="padding:7px 10px;{bd}text-align:center;font-size:12px;font-weight:700;width:120px;">Cantidad</th>'
                '</tr></thead>')
        body = '<tbody>'
        for idx, prod_name in enumerate(prods):
            bg = "#f8fafc" if idx % 2 == 0 else "#ffffff"
            key = ((bank_name or "").strip().lower(), (prod_name or "").strip().lower())
            qty = qty_lookup.get(key, 0)
            qty_display = qty if qty > 0 else 1
            body += (f'<tr style="background:{bg};">'
                     f'<td style="padding:6px 10px;{bd}font-size:11px;color:#334155;">{prod_name}</td>'
                     f'<td style="padding:6px 10px;{bd}text-align:center;font-size:11px;color:#334155;font-weight:700;">{qty_display}</td>'
                     f'</tr>')
        body += '</tbody>'

        blocks.append(
            f'<div style="margin:0 0 18px;">'
            f'<div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;'
            f'background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">'
            f'Banco: {bank_name}</div>'
            f'<div style="overflow-x:auto;">'
            f'<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;">'
            f'{head}{body}</table></div></div>'
        )

    return caption + ''.join(blocks)


def _build_vtid_list_html(vtids: list) -> str:
    """Genera una lista HTML de VTIDs generados."""
    if not vtids:
        return "<p><em>Sin terminales virtuales generados.</em></p>"

    html = (
        '<table style="border-collapse:collapse;width:auto;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead>'
        '<tr style="background:#2c3e50;color:white;">'
        '<th style="padding:8px 16px;text-align:center;border:1px solid #ddd;">#</th>'
        '<th style="padding:8px 16px;text-align:left;border:1px solid #ddd;">VTID</th>'
        '</tr>'
        '</thead><tbody>'
    )

    for idx, vtid in enumerate(vtids):
        bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
        code = vtid.get("code", "")
        html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:6px 16px;text-align:center;border:1px solid #e9ecef;">{idx + 1}</td>'
            f'<td style="padding:6px 16px;border:1px solid #e9ecef;font-weight:bold;">{code}</td>'
            f'</tr>'
        )

    html += '</tbody></table>'
    return html


def _build_vtid_list_html_grouped(groups: list) -> str:
    """Genera HTML de VTIDs agrupados por sucursal."""
    if not groups:
        return "<p><em>Sin terminales virtuales generados.</em></p>"

    html = ""
    for group in groups:
        name = group.get("name", "")
        vtids = group.get("vtids", [])
        if not vtids:
            continue
        html += f'<h4 style="color:#2c3e50;margin:16px 0 8px 0;font-family:Arial,sans-serif;">{name}</h4>'
        html += (
            '<table style="border-collapse:collapse;width:auto;font-family:Arial,sans-serif;font-size:13px;">'
            '<thead><tr style="background:#2c3e50;color:white;">'
            '<th style="padding:8px 16px;text-align:center;border:1px solid #ddd;">#</th>'
            '<th style="padding:8px 16px;text-align:left;border:1px solid #ddd;">VTID</th>'
            '</tr></thead><tbody>'
        )
        for idx, vtid in enumerate(vtids):
            bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            code = vtid.get("code", "")
            html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:6px 16px;text-align:center;border:1px solid #e9ecef;">{idx + 1}</td>'
                f'<td style="padding:6px 16px;border:1px solid #e9ecef;font-weight:bold;">{code}</td>'
                f'</tr>'
            )
        html += '</tbody></table>'
    return html if html else "<p><em>Sin terminales virtuales generados.</em></p>"




def _build_equipment_html(equipments: list) -> str:
    """Genera tabla HTML de equipos (Modelo - Serial)."""
    if not equipments:
        return "<p><em>Sin equipos asignados.</em></p>"

    # Group by modelo
    by_model = {}
    for eq in equipments:
        modelo = eq.get("modelo", "Desconocido")
        serial = eq.get("serial", "—")
        if modelo not in by_model:
            by_model[modelo] = []
        by_model[modelo].append(serial)

    html = (
        '<table style="border-collapse:collapse;width:auto;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead><tr style="background:#2c3e50;color:white;">'
        '<th style="padding:8px 16px;text-align:left;border:1px solid #ddd;">Modelo</th>'
        '<th style="padding:8px 16px;text-align:left;border:1px solid #ddd;">Serial</th>'
        '</tr></thead><tbody>'
    )

    idx = 0
    for modelo, serials in by_model.items():
        for serial in serials:
            bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:6px 16px;border:1px solid #e9ecef;">{modelo}</td>'
                f'<td style="padding:6px 16px;border:1px solid #e9ecef;font-weight:bold;">{serial}</td>'
                f'</tr>'
            )
            idx += 1

    html += '</tbody></table>'
    return html



def _build_stores_summary(stores: list) -> tuple:
    """Genera resúmenes de sucursales y cajas.
    Returns: (nombre_sucursal_str, cantidad_cajas_str)
    """
    if not stores or len(stores) == 0:
        return ("Sede Principal", "—")

    if len(stores) == 1:
        s = stores[0]
        return (s.get("name", "Sucursal"), str(s.get("box_count", "—")))

    # Multiple stores: list format
    names = []
    cajas_parts = []
    for s in stores:
        name = s.get("name", "Sucursal")
        bc = s.get("box_count", 0)
        names.append(name)
        cajas_parts.append(f"{name}: {bc}")

    total = sum(s.get("box_count", 0) for s in stores)
    return (
        ", ".join(names),
        " | ".join(cajas_parts) + f" (Total: {total})"
    )


def _build_stores_matrix_html(stores: list, fallback_name: str = "Sede Principal", fallback_cajas=None) -> str:
    """Genera tabla HTML 'Matriz de Sucursales': columnas Sucursal | Cantidad de Cajas,
    una fila por cada sucursal del proyecto + fila Total cuando hay más de una.
    Para proyectos sin sucursales explícitas (flujo PYME) usa el fallback provisto."""
    rows = []
    if stores:
        for s in stores:
            rows.append((s.get("name", "Sucursal"), s.get("box_count", 0) or 0))
    elif fallback_cajas not in (None, "", "—"):
        rows.append((fallback_name or "Sede Principal", fallback_cajas))

    if not rows:
        return "<p><em>Sin sucursales definidas.</em></p>"

    html = (
        '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead><tr style="background:#2c3e50;color:white;">'
        '<th style="padding:10px 12px;text-align:left;border:1px solid #ddd;">Sucursal</th>'
        '<th style="padding:10px 12px;text-align:center;border:1px solid #ddd;">Cantidad de Cajas</th>'
        '</tr></thead><tbody>'
    )
    total = 0
    for idx, (name, cajas) in enumerate(rows):
        bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
        try:
            total += int(cajas)
        except (TypeError, ValueError):
            pass
        html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 12px;border:1px solid #e9ecef;">{name}</td>'
            f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{cajas}</td>'
            f'</tr>'
        )
    if len(rows) > 1:
        html += (
            '<tr style="background:#eef2f7;font-weight:bold;">'
            '<td style="padding:8px 12px;border:1px solid #e9ecef;">Total</td>'
            f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{total}</td>'
            '</tr>'
        )
    html += '</tbody></table>'
    return html


# Fases canónicas de implementación por sucursal (deben coincidir con STORE_PHASES del frontend).
_MULTIRIF_STORE_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]


def _multirif_store_progress(store: dict) -> int:
    """Avance % de una sucursal = fases completadas / fases totales de su matriz."""
    sm = store.get("implementation_matrix") or {}
    completed = total = 0
    for products in sm.values():
        for phases in (products or {}).values():
            for ph in _MULTIRIF_STORE_PHASES:
                total += 1
                if ((phases or {}).get(ph) or {}).get("completed"):
                    completed += 1
    return round(completed / total * 100) if total else 0


def _multirif_weighted_progress(stores: list) -> int:
    """Avance ponderado por cantidad de cajas sobre un conjunto de sucursales."""
    if not stores:
        return 0
    total_boxes = sum(int(s.get("box_count") or 0) for s in stores)
    if total_boxes == 0:
        return round(sum(_multirif_store_progress(s) for s in stores) / len(stores))
    return round(sum(_multirif_store_progress(s) * int(s.get("box_count") or 0) for s in stores) / total_boxes)


def _build_multirif_distribution_html(project: dict, with_progress: bool = False) -> str:
    """Tabla HTML jerárquica Multi-RIF: Cliente (RIF) -> Sucursales -> Cajas.
    Si with_progress=True, agrega una columna 'Avance' (% por sucursal y por RIF)."""
    rifs = project.get("rifs") or []
    stores = project.get("stores") or []
    if not rifs and not stores:
        return "<p><em>No aplica: este proyecto no es Multi-RIF.</em></p>"

    cols = 3 if with_progress else 2
    th_avance = '<th style="padding:10px 12px;text-align:center;border:1px solid #ddd;">Avance</th>' if with_progress else ''
    html = (
        '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead><tr style="background:#2c3e50;color:white;">'
        '<th style="padding:10px 12px;text-align:left;border:1px solid #ddd;">Cliente (RIF) / Sucursal</th>'
        '<th style="padding:10px 12px;text-align:center;border:1px solid #ddd;">Cajas</th>'
        f'{th_avance}'
        '</tr></thead><tbody>'
    )
    grand_boxes = 0
    for rif in rifs:
        rif_stores = [s for s in stores if s.get("rif_id") == rif.get("rif_id")]
        rif_boxes = int(rif.get("box_count") or 0)
        grand_boxes += rif_boxes
        rif_av = _multirif_weighted_progress(rif_stores) if with_progress else None
        av_cell = f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;font-weight:bold;color:#2c3e50;">{rif_av}%</td>' if with_progress else ''
        html += (
            '<tr style="background:#e3f2fd;font-weight:bold;color:#1565c0;">'
            f'<td style="padding:8px 12px;border:1px solid #e9ecef;">{rif.get("client_name", "Cliente")} — RIF: {rif.get("rif", "")}</td>'
            f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{rif_boxes}</td>'
            f'{av_cell}'
            '</tr>'
        )
        if not rif_stores:
            html += (
                f'<tr><td style="padding:6px 12px 6px 28px;border:1px solid #e9ecef;color:#888;"><em>(sin sucursales)</em></td>'
                f'<td style="text-align:center;border:1px solid #e9ecef;">—</td>'
                + ('<td style="text-align:center;border:1px solid #e9ecef;">—</td>' if with_progress else '')
                + '</tr>'
            )
        for idx, s in enumerate(rif_stores):
            bg = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            s_av = f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{_multirif_store_progress(s)}%</td>' if with_progress else ''
            html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:8px 12px 8px 28px;border:1px solid #e9ecef;">{s.get("name", "Sucursal")}</td>'
                f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{int(s.get("box_count") or 0)}</td>'
                f'{s_av}'
                '</tr>'
            )
    # Total general
    total_av = f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{_multirif_weighted_progress(stores)}%</td>' if with_progress else ''
    html += (
        '<tr style="background:#eef2f7;font-weight:bold;">'
        '<td style="padding:8px 12px;border:1px solid #e9ecef;">TOTAL GENERAL</td>'
        f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{grand_boxes}</td>'
        f'{total_av}'
        '</tr>'
    )
    html += '</tbody></table>'
    return html


def _fmt_short_date(value) -> str:
    """ISO → 'dd/mm/yyyy'. Vacío si no parsea."""
    if not value:
        return ""
    try:
        from datetime import datetime as _dt
        d = _dt.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _phase_cell_value(phase_data: dict):
    """Valor de una celda de fase según las reglas de negocio:
      - Fase Cumplida/Finalizada  → '100%'
      - Fase En Proceso           → '{pct}%' (processed/expected real)
      - Fase No Iniciada          → '—' (guion, sin ceros)
    Retorna (texto, tipo) con tipo ∈ {'done','progress','none'}.
    """
    pd = phase_data or {}
    try:
        expected = int(pd.get("expected") or 0)
    except (TypeError, ValueError):
        expected = 0
    try:
        processed = int(pd.get("processed") or 0)
    except (TypeError, ValueError):
        processed = 0
    if pd.get("completed"):
        return ("100%", "done")
    if processed > 0 and expected > 0:
        if processed >= expected:
            return ("100%", "done")
        return (f"{round(processed / expected * 100)}%", "progress")
    return ("—", "none")


def _avance_phase_table(matrix: dict, with_dates: bool = False) -> str:
    """Tabla HTML Banco → Producto → 4 Fases para una matriz de implementación.
    Si `with_dates`, cada celda con avance muestra debajo la fecha (updated_at)
    en que se alcanzó ese porcentaje."""
    phases = _MULTIRIF_STORE_PHASES
    if not matrix:
        return '<p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:2px 0 10px;"><em>Sin matriz de implementación.</em></p>'
    th_phases = ''.join(
        f'<th style="padding:8px 10px;border:1px solid #ddd;text-align:center;">{p}</th>' for p in phases
    )
    html = (
        '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:12px;margin:4px 0 12px;">'
        '<thead><tr style="background:#2c3e50;color:white;">'
        '<th style="padding:8px 10px;border:1px solid #ddd;text-align:left;">Banco / Producto</th>'
        f'{th_phases}</tr></thead><tbody>'
    )
    for bank, products in matrix.items():
        html += (
            f'<tr style="background:#e8eef5;color:#1f3a5f;font-weight:bold;">'
            f'<td colspan="{len(phases) + 1}" style="padding:6px 10px;border:1px solid #e9ecef;">Banco: {bank}</td></tr>'
        )
        for product, phdata in (products or {}).items():
            cells = ''
            for p in phases:
                pcell = (phdata or {}).get(p)
                val, kind = _phase_cell_value(pcell)
                color = '#16a34a' if kind == 'done' else '#d97706' if kind == 'progress' else '#9ca3af'
                weight = '700' if kind in ('done', 'progress') else '400'
                date_html = ''
                if with_dates and kind in ('done', 'progress'):
                    ds = _fmt_short_date((pcell or {}).get('updated_at'))
                    if ds:
                        date_html = (
                            f'<div style="font-size:10px;color:#64748b;font-weight:400;margin-top:2px;">{ds}</div>'
                        )
                cells += (
                    f'<td style="padding:6px 10px;border:1px solid #e9ecef;text-align:center;'
                    f'color:{color};font-weight:{weight};">{val}{date_html}</td>'
                )
            html += f'<tr><td style="padding:6px 10px 6px 22px;border:1px solid #e9ecef;">{product}</td>{cells}</tr>'
    html += '</tbody></table>'
    return html


def _avance_store_block(store: dict, rif_label: str = "", with_dates: bool = False) -> str:
    """Bloque de una sucursal: encabezado (nombre · cajas · avance) + tabla de fases."""
    name = store.get("name", "Sucursal")
    boxes = store.get("box_count", 0) or 0
    pct = _multirif_store_progress(store)
    color = '#16a34a' if pct >= 100 else '#d97706' if pct > 0 else '#9ca3af'
    suffix = f' · {rif_label}' if rif_label else ''
    header = (
        f'<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#334155;'
        f'margin:8px 0 0;padding:6px 10px;background:#f1f5f9;border-left:3px solid {color};">'
        f'Sucursal: {name} · {boxes} caja(s){suffix} · '
        f'<span style="color:{color};font-weight:700;">Avance {pct}%</span></div>'
    )
    return header + _avance_phase_table(store.get("implementation_matrix") or {}, with_dates=with_dates)


def _build_avance_matrix_html(project: dict, with_dates: bool = False) -> str:
    """Variable {Matriz_Avance_Proyecto}: matriz jerárquica de avance.
      - Estándar (single):        Banco → Producto → Fases
      - Multitienda / Multi-RIF:  Tienda/Sucursal → Banco → Producto → Fases
    Cabecera con KPI de Avance Global (el mismo del dashboard del proyecto).
    Si `with_dates`, cada % muestra la fecha en que se alcanzó (variable
    {Matriz_Avance_Proyecto_Con_Fecha})."""
    ptype = (project.get("project_type") or "").lower()
    stores = project.get("stores") or []
    rollup = project.get("rollup_progress") or {}
    global_pct = rollup.get("global_progress")
    if global_pct is None:
        global_pct = _multirif_weighted_progress(stores) if stores else 0
    try:
        gp = round(float(global_pct))
    except (TypeError, ValueError):
        gp = 0
    gcolor = '#16a34a' if gp >= 100 else '#2563eb' if gp > 0 else '#9ca3af'
    header = (
        '<div style="font-family:Arial,sans-serif;margin:6px 0 12px;padding:10px 14px;border-radius:8px;'
        'background:#f0f6ff;border:1px solid #cfe0f5;">'
        '<span style="font-size:13px;color:#334155;font-weight:600;">Avance Global del Proyecto:</span> '
        f'<span style="font-size:16px;font-weight:800;color:{gcolor};">{gp}%</span></div>'
    )

    if ptype in ("multistore", "multirif") and stores:
        blocks = []
        rifs = project.get("rifs") or []
        if ptype == "multirif" and rifs:
            for rif in rifs:
                rif_stores = [s for s in stores if s.get("rif_id") == rif.get("rif_id")]
                if not rif_stores:
                    continue
                blocks.append(
                    f'<div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#1565c0;'
                    f'margin:12px 0 2px;">{rif.get("client_name", "Cliente")} — RIF: {rif.get("rif", "")}</div>'
                )
                for s in rif_stores:
                    blocks.append(_avance_store_block(s, with_dates=with_dates))
            # Sucursales sin RIF asociado (borde): mostrarlas igual.
            assigned_ids = {rid for rif in rifs for rid in [rif.get("rif_id")]}
            orphan = [s for s in stores if s.get("rif_id") not in assigned_ids]
            for s in orphan:
                blocks.append(_avance_store_block(s, with_dates=with_dates))
        else:
            for s in stores:
                blocks.append(_avance_store_block(s, with_dates=with_dates))
        return header + ''.join(blocks)

    # Proyecto estándar (single)
    return header + _avance_phase_table(project.get("implementation_matrix") or {}, with_dates=with_dates)


# ===================== {Matriz_Seguimiento_Evolutiva} =====================
# Matriz bidimensional multinivel: eje vertical = RIF → Tienda/Sucursal (+ Cajas);
# eje horizontal = Banco → Producto → Fases (Rec/Conf/Test/Prod) con % de avance.
# Modular por banco: si `bank_filter` se especifica, solo se renderiza ese banco
# (para envíos dirigidos a un Banco específico — confidencialidad interbancaria).

_SEG_PHASES = [("Recibido", "Rec"), ("Configurado", "Conf"), ("Testeado", "Test"), ("En Producción", "Prod")]


def _seg_banks_products(matrix: dict, bank_filter: str = None) -> list:
    """Lista ordenada [(banco, [productos])] desde la matriz plantilla del proyecto.
    Si `bank_filter`, conserva solo ese banco (match case-insensitive)."""
    out = []
    bf = (bank_filter or "").strip().lower()
    for bank, products in (matrix or {}).items():
        if bf and (bank or "").strip().lower() != bf:
            continue
        prods = [p for p in (products or {}).keys()]
        if prods:
            out.append((bank, prods))
    return out


def _seg_rows(project: dict) -> list:
    """Filas verticales: [{rif_label, name, boxes, matrix}] agrupables por RIF."""
    ptype = (project.get("project_type") or "").lower()
    stores = project.get("stores") or []
    rows = []
    if ptype in ("multistore", "multirif") and stores:
        rifs = project.get("rifs") or []
        if ptype == "multirif" and rifs:
            for rif in rifs:
                rlabel = f'{rif.get("client_name", "Cliente")} — RIF: {format_rif(rif.get("rif", ""))}'
                rstores = [s for s in stores if s.get("rif_id") == rif.get("rif_id")]
                for s in rstores:
                    rows.append({"rif_label": rlabel, "name": s.get("name", "Sucursal"),
                                 "boxes": int(s.get("box_count") or 0), "matrix": s.get("implementation_matrix") or {}})
            assigned = {rif.get("rif_id") for rif in rifs}
            for s in [s for s in stores if s.get("rif_id") not in assigned]:
                rows.append({"rif_label": "Sin RIF asignado", "name": s.get("name", "Sucursal"),
                             "boxes": int(s.get("box_count") or 0), "matrix": s.get("implementation_matrix") or {}})
        else:
            rlabel = f'{project.get("client_name", "Cliente")} — RIF: {format_rif(project.get("client_rif", ""))}'
            for s in stores:
                rows.append({"rif_label": rlabel, "name": s.get("name", "Sucursal"),
                             "boxes": int(s.get("box_count") or 0), "matrix": s.get("implementation_matrix") or {}})
    else:
        # Single: una fila = el proyecto mismo.
        rlabel = f'{project.get("client_name", "Cliente")} — RIF: {format_rif(project.get("client_rif", ""))}'
        services = project.get("services", []) or []
        boxes = project.get("cantidad_cajas") or max((s.get("cantidad_cajas", 0) for s in services), default=0) or 0
        rows.append({"rif_label": rlabel, "name": project.get("client_sede") or "Sede Principal",
                     "boxes": int(boxes or 0), "matrix": project.get("implementation_matrix") or {}})
    return rows


def _seg_cell_v2(phase_data: dict):
    """Celda V2: '% / Cajas Estimadas / Cajas Recibidas' (ej. '80% / 10 / 8').
    Estimadas = expected, Recibidas = processed. Retorna (texto, color)."""
    pd = phase_data or {}
    try:
        expected = int(pd.get("expected") or 0)
    except (TypeError, ValueError):
        expected = 0
    try:
        processed = int(pd.get("processed") or 0)
    except (TypeError, ValueError):
        processed = 0
    if pd.get("completed"):
        pct = 100
    elif expected > 0:
        pct = min(round(processed / expected * 100), 100)
    else:
        pct = 0
    color = '#16a34a' if pct >= 100 else '#d97706' if pct > 0 else '#64748b'
    return (f"{pct}% / {expected} / {processed}", color)


def _build_seguimiento_evolutiva_html(project: dict, bank_filter: str = None) -> str:
    """Variable {Matriz_Seguimiento_Evolutiva} (V2).

    Renderiza un bloque (tabla) independiente por banco, apilados verticalmente.
    Cada tabla: eje vertical = RIF → Tiendas; columnas = Producto×Fase;
    celda = '% / Cajas Estimadas / Cajas Recibidas'.
    Si `bank_filter`, solo se emite el bloque de ese banco (descarte modular).
    """
    banks = _seg_banks_products(project.get("implementation_matrix") or {}, bank_filter)
    rows = _seg_rows(project)
    if not banks:
        msg = "Sin bancos asociados para el destinatario." if bank_filter else "Sin matriz de implementación."
        return f'<p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:6px 0;"><em>{msg}</em></p>'

    bd = "border:1px solid #d8dee9;"
    blocks = []
    for bank, prods in banks:
        # Columnas: una por (producto, fase).
        cols = [(p, full) for p in prods for full, _short in _SEG_PHASES]
        total_cols = 1 + len(cols)

        # Encabezado de 2 niveles: producto (colspan 4) + Fase I..IV
        head = ('<thead><tr style="background:#1f3a5f;color:#fff;">'
                f'<th rowspan="2" style="padding:7px 10px;{bd}text-align:left;font-size:11px;min-width:170px;vertical-align:middle;">Estructura del Cliente</th>')
        for p in prods:
            head += (f'<th colspan="4" style="padding:7px 9px;{bd}text-align:center;font-size:12px;font-weight:700;">{p}</th>')
        head += '</tr><tr style="background:#2c5378;color:#fff;">'
        for p in prods:
            for fl in ("Fase I", "Fase II", "Fase III", "Fase IV"):
                head += (f'<th style="padding:6px 8px;{bd}text-align:center;font-size:11px;font-weight:600;">{fl}</th>')
        head += '</tr></thead>'

        # Cuerpo: banda RIF + filas de tienda.
        body = '<tbody>'
        last_rif = None
        for row in rows:
            if row["rif_label"] != last_rif:
                last_rif = row["rif_label"]
                body += (f'<tr><td colspan="{total_cols}" style="padding:6px 10px;{bd}'
                         f'background:#e8eef5;color:#1f3a5f;font-weight:700;font-size:12px;">RIF: {last_rif}</td></tr>')
            rmatrix = row["matrix"] or {}
            cells = ''
            for p, full in cols:
                phdata = ((rmatrix.get(bank) or {}).get(p)) or {}
                val, color = _seg_cell_v2(phdata.get(full))
                cells += (f'<td style="padding:6px 9px;{bd}text-align:center;font-size:11px;'
                          f'color:{color};font-weight:700;white-space:nowrap;">{val}</td>')
            body += (f'<tr><td style="padding:6px 10px;{bd}font-size:11px;color:#334155;">'
                     f'<span style="color:#94a3b8;">└─</span> {row["name"]}</td>{cells}</tr>')
        body += '</tbody>'

        legend = ('<div style="font-family:Arial,sans-serif;font-size:10.5px;color:#64748b;'
                  'margin:4px 0 0;text-align:left;"><strong>Estatus de las Fases:</strong> '
                  'Fase I = Recibido &nbsp;|&nbsp; Fase II = Configurado &nbsp;|&nbsp; '
                  'Fase III = Testeado &nbsp;|&nbsp; Fase IV = En Producción</div>')

        blocks.append(
            f'<div style="margin:0 0 18px;">'
            f'<div style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:#16324f;'
            f'background:#dbeafe;padding:7px 12px;border-left:4px solid #1f3a5f;border-radius:4px;margin-bottom:6px;">'
            f'{bank}</div>'
            f'<div style="overflow-x:auto;">'
            f'<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;">'
            f'{head}{body}</table></div>{legend}</div>'
        )

    scope = f' · Banco: {bank_filter}' if bank_filter else ' · Todos los bancos'
    caption = (f'<div style="font-family:Arial,sans-serif;font-size:12px;font-weight:600;color:#475569;margin:6px 0 8px;">'
               f'Matriz de Seguimiento Evolutiva{scope}'
               f'<span style="font-weight:400;color:#94a3b8;"> — formato celda: % avance / cajas estimadas / cajas recibidas</span></div>')
    return caption + ''.join(blocks)






async def resolve_project_template_vars(project: dict) -> dict:
    """Resuelve todas las variables dinámicas de un proyecto para inyectar en plantillas.
    
    Args:
        project: Documento del proyecto de MongoDB
    
    Returns:
        dict con todas las variables resueltas
    """
    # === Datos básicos del proyecto ===
    ticket = project.get("ticket_number", "")
    project_number = project.get("project_number", "")
    quote_number = project.get("quote_number", "")

    # === {Nombre_Cliente} — from clientes.razon_social / legal_name / fantasy_name ===
    client_name = project.get("client_name", "")
    client_id = project.get("client_id")
    razon_social = client_name  # fallback
    client_fantasy = project.get("fantasy_name", "") or ""
    contacto_principal = ""
    contacto_telefono = ""
    contacto_email = ""

    if client_id:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if client:
            razon_social = (
                client.get("razon_social")
                or client.get("legal_name")
                or client.get("fantasy_name")
                or client.get("nombre_comercial")
                or client.get("name")
                or client_name
            )
            if not client_fantasy:
                client_fantasy = client.get("fantasy_name") or client.get("nombre_comercial") or ""
            # {Contacto_Principal} — primer contacto
            contacts = client.get("contacts", [])
            if contacts:
                c = contacts[0]
                contacto_principal = c.get("full_name", "")
                if not contacto_principal:
                    first = c.get("first_name", c.get("nombre", ""))
                    last = c.get("last_name", c.get("apellido", ""))
                    contacto_principal = f"{first} {last}".strip()
                if not contacto_principal:
                    contacto_principal = c.get("name", c.get("email", ""))
                contacto_telefono = c.get("phone", c.get("telefono", ""))
                contacto_email = c.get("email", "")
            else:
                # Fallback: contact1 field (legacy)
                c1 = client.get("contact1", {})
                if c1:
                    contacto_principal = c1.get("name", "")
                    contacto_telefono = c1.get("phone", "")
                    contacto_email = c1.get("email", "")

    # === {Nombre_Sucursal} y {Cantidad_Cajas} ===
    stores = project.get("stores", [])
    nombre_sucursal, cantidad_cajas = _build_stores_summary(stores)

    # If no stores, use project-level data
    if not stores:
        # Single-store project: use client_sede or just "Sede Principal"
        nombre_sucursal = project.get("client_sede", "Sede Principal")
        # Try to get total boxes from services
        services = project.get("services", [])
        if services:
            cajas = max((s.get("cantidad_cajas", 0) for s in services), default=0)
            cantidad_cajas = str(cajas) if cajas else "—"

    # === {Matriz_Sucursales} — tabla Sucursal | Cantidad de Cajas ===
    matriz_sucursales_html = _build_stores_matrix_html(
        stores, fallback_name=nombre_sucursal, fallback_cajas=cantidad_cajas
    )

    # === {Integrador} ===
    integrador = project.get("integrator_name", "—")

    # === {Nombre_Implementador}, {Correo_Implementador}, {Telefono_Implementador} ===
    nombre_implementador = project.get("assigned_to_name", "")
    correo_implementador = ""
    telefono_implementador = ""
    assigned_to_id = project.get("assigned_to_user_id")
    if assigned_to_id:
        impl_user = await db.users.find_one({"user_id": assigned_to_id}, {"_id": 0})
        if impl_user:
            nombre_implementador = f"{impl_user.get('first_name', '')} {impl_user.get('last_name', '')}".strip() or nombre_implementador
            correo_implementador = impl_user.get("email", "")
            telefono_implementador = impl_user.get("phone", "") or impl_user.get("telefono", "")

    # === {Aplicativo_Integracion} ===
    aplicativo_integracion = project.get("integrator_app_name", "—")

    # === {Matriz_Bancos_Productos} ===
    matrix = project.get("implementation_matrix", {})
    project_services = project.get("services", []) or []
    matriz_html = _build_matrix_html(matrix, services=project_services)

    # === {Patrocinador} — variable lógica condicional ===
    # SÍ patrocinada: nombre del Banco (o "Banco - Procesador"). NO patrocinada: Nombre de Fantasía del cliente.
    sponsored = project.get("sponsored_implementation")
    sponsoring_bank = (project.get("sponsoring_bank_name") or "").strip()
    sponsoring_processor = (project.get("sponsoring_processor_name") or "").strip()
    if sponsored and sponsoring_bank:
        patrocinador = f"{sponsoring_bank} - {sponsoring_processor}" if sponsoring_processor else sponsoring_bank
    else:
        patrocinador = client_fantasy or razon_social or client_name

    # === {Lista_VTID} ===
    # Combine project-level + store-level VTIDs
    vtids = project.get("vtids", [])
    stores_for_vtid = project.get("stores", [])
    all_vtids_grouped = []
    if vtids:
        all_vtids_grouped.append({"name": "General", "vtids": vtids})
    for s in stores_for_vtid:
        s_vtids = s.get("vtids", [])
        if s_vtids:
            all_vtids_grouped.append({"name": s.get("name", "Sucursal"), "vtids": s_vtids})
    lista_vtid = _build_vtid_list_html_grouped(all_vtids_grouped) if all_vtids_grouped else _build_vtid_list_html(vtids)

    # === {Modelo_Seriales_Equipos} ===
    equipments = project.get("equipments", [])
    modelo_seriales_html = _build_equipment_html(equipments)

    # === {Modelo_Seriales_POS} === (Pinpads desde inventario - flujo PYME)
    pinpad_serials = project.get("pinpad_serials", [])
    all_pos_serials = pinpad_serials + equipments
    modelo_seriales_pos_html = _build_equipment_html(all_pos_serials) if all_pos_serials else "<em>Sin equipos POS/Pinpad vinculados</em>"

    # === {Servidor_Instalacion} === (flujo PYME)
    servidor_instalacion = project.get("server_name", "")

    # === {Tipo_Comunicacion} === (SSL/VPN) — fila siguiente a Servidor de Instalación
    tipo_comunicacion = project.get("communication_type", "")

    # === Ejecutivo asignado al proyecto ===
    assigned_name = project.get("assigned_to_name", "")

    # === Fecha de Asignación + Fecha de Desbloqueo (Ticket) ===
    def _fmt_date(value):
        if not value:
            return ""
        try:
            from datetime import datetime as _dt
            if isinstance(value, str):
                # Try ISO
                try:
                    dt = _dt.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return value
            else:
                dt = value
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return str(value)

    fecha_asignacion = _fmt_date(project.get("assigned_at"))
    fecha_desbloqueo_ticket = _fmt_date(project.get("unblocked_at"))

    # === Variables consolidadas ===
    variables = {
        # Variables nuevas (Diccionario Técnico)
        "Nombre_Cliente": razon_social,
        "Nombre_Fantasia": client_fantasy or razon_social or client_name,
        "Rif_Cliente": format_rif(project.get("client_rif", "")),
        "Contacto_Principal": contacto_principal,
        "Datos_Contacto": f"{contacto_principal} | Tel: {contacto_telefono} | Email: {contacto_email}" if contacto_principal else "—",
        "Telefono_Contacto": contacto_telefono,
        "Email_Contacto": contacto_email,
        "Nombre_Sucursal": nombre_sucursal,
        "Cantidad_Cajas": cantidad_cajas,
        "Matriz_Sucursales": matriz_sucursales_html,
        "Integrador": integrador,
        "Aplicativo_Integracion": aplicativo_integracion,
        "Nombre_Implementador": nombre_implementador,
        "Correo_Implementador": correo_implementador,
        "Telefono_Implementador": telefono_implementador,
        "Matriz_Bancos_Productos": matriz_html,
        "Matriz_MultiRif_Distribucion": _build_multirif_distribution_html(project, with_progress=False),
        "Matriz_MultiRif_Avance": _build_multirif_distribution_html(project, with_progress=True),
        "Matriz_Avance_Proyecto": _build_avance_matrix_html(project),
        "Matriz_Avance_Proyecto_Con_Fecha": _build_avance_matrix_html(project, with_dates=True),
        "Matriz_Seguimiento_Evolutiva": _build_seguimiento_evolutiva_html(project),
        "Patrocinador": patrocinador,
        "Lista_VTID": lista_vtid,
        "Modelo_Seriales_Equipos": modelo_seriales_html,
        "Modelo_Seriales_POS": modelo_seriales_pos_html,
        "Servidor_Instalacion": servidor_instalacion or "No asignado",
        "Tipo_Comunicacion": tipo_comunicacion or "No asignado",

        # === Estado del proyecto (texto plano del estado actual) ===
        "Estado_Proyecto": project.get("status", "") or "",

        # === Alias en PascalCase español (lo que muestra el panel lateral del editor) ===
        "Nro_Proyecto": project_number or "",
        "Ticket_Nro": ticket or "",
        "Nro_Ticket": ticket or "",  # alias adicional por si se inserta como "Nro_Ticket"
        "Tipo_Proyecto": project.get("quote_type", "") or "",
        "Fecha_Asignacion": fecha_asignacion,
        "Fecha_Desbloqueo_Ticket": fecha_desbloqueo_ticket,

        # Variables estándar del proyecto (snake_case — alias en inglés)
        "project_number": project_number,
        "quote_number": quote_number,
        "ticket_number": ticket,
        "client_name": client_name,
        "client_rif": format_rif(project.get("client_rif", "")),
        "client_segment": project.get("client_segment", ""),
        "quote_type": project.get("quote_type", ""),
        "integrator_name": integrador,
        "integrator_app_name": project.get("integrator_app_name", ""),
        "pinpad_model": project.get("pinpad_model", ""),
        "total_usd": f"{project.get('total_usd', 0):.2f}",
        "assigned_to": assigned_name,
        "sede_name": project.get("client_segment", "PYME"),
    }

    # === HOMOLOGACIÓN Cotizaciones ↔ Proyectos ===
    # Las plantillas de Proyectos deben disponer de TODAS las variables del
    # entorno de Cotizaciones. Se construyen desde la cotización original
    # (quote_id) y, para Proyectos Directos sin cotización, desde el propio
    # proyecto (best-effort). Las variables del proyecto tienen prioridad sobre
    # las de la cotización en las claves compartidas (valores más actuales).
    quote_vars = {}
    try:
        from services.notification_engine import _build_template_vars
        source = None
        if project.get("quote_id"):
            source = await db.quotes.find_one({"quote_id": project["quote_id"]}, {"_id": 0})
        quote_vars = await _build_template_vars(source or project)
    except Exception:
        quote_vars = {}

    # Firma institucional global (baseline: CRM - Gestor para flujos sin actor;
    # los flujos manuales la sobreescriben con el usuario que detona).
    try:
        from services.signature import build_signature_html
        variables["Firma_Notificacion_Global"] = await build_signature_html(None)
    except Exception:
        pass

    return {**quote_vars, **variables}
