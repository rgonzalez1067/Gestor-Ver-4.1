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


def _build_matrix_html(implementation_matrix: dict, services: list = None) -> str:
    """Genera tabla HTML de Bancos y Productos desde implementation_matrix.

    `services` (opcional): lista de servicios del proyecto/cotización original.
    Si se provee, la columna Cantidad refleja `cantidad_cajas` real del item
    (banco, producto) en la cotización; si no, cae a 1.
    """
    if not implementation_matrix:
        return "<p><em>Sin matriz de implementación definida.</em></p>"

    # Indexar cantidades reales por (banco, producto) desde services
    qty_lookup = {}
    if services:
        for s in services:
            if s.get("item_type") not in ("additional", None):
                # Solo items "additional" representan productos por banco
                continue
            bn = (s.get("bank_name") or "").strip()
            name = (s.get("item_name") or s.get("name") or "").strip()
            if not bn or not name:
                continue
            # Preferir cantidad_cajas; fallback a quantity
            cajas = s.get("cantidad_cajas") or s.get("quantity") or 0
            try:
                cajas = int(cajas)
            except (TypeError, ValueError):
                cajas = 0
            key = (bn.lower(), name.lower())
            # Si el mismo banco/producto aparece varias veces, sumar
            qty_lookup[key] = qty_lookup.get(key, 0) + max(0, cajas)

    rows = []
    for bank_name, products in implementation_matrix.items():
        for product_name in products.keys():
            rows.append((bank_name, product_name))

    if not rows:
        return "<p><em>Sin productos en la matriz.</em></p>"

    html = (
        '<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px;">'
        '<thead>'
        '<tr style="background:#2c3e50;color:white;">'
        '<th style="padding:10px 12px;text-align:left;border:1px solid #ddd;">Banco</th>'
        '<th style="padding:10px 12px;text-align:left;border:1px solid #ddd;">Producto / Servicio</th>'
        '<th style="padding:10px 12px;text-align:center;border:1px solid #ddd;">Cantidad</th>'
        '</tr>'
        '</thead><tbody>'
    )

    # Group by bank
    from collections import defaultdict
    bank_products = defaultdict(list)
    for bank, prod in rows:
        bank_products[bank].append(prod)

    row_idx = 0
    for bank_name, prods in bank_products.items():
        for prod_name in prods:
            bg = "#f8f9fa" if row_idx % 2 == 0 else "#ffffff"
            # Lookup case-insensitive y trim para matchear nombres con trailing spaces
            key = ((bank_name or "").strip().lower(), (prod_name or "").strip().lower())
            qty = qty_lookup.get(key, 0)
            qty_display = qty if qty > 0 else 1
            html += (
                f'<tr style="background:{bg};">'
                f'<td style="padding:8px 12px;border:1px solid #e9ecef;">{bank_name}</td>'
                f'<td style="padding:8px 12px;border:1px solid #e9ecef;">{prod_name}</td>'
                f'<td style="padding:8px 12px;text-align:center;border:1px solid #e9ecef;">{qty_display}</td>'
                f'</tr>'
            )
            row_idx += 1

    html += '</tbody></table>'
    return html


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
        "Rif_Cliente": format_rif(project.get("client_rif", "")),
        "Contacto_Principal": contacto_principal,
        "Datos_Contacto": f"{contacto_principal} | Tel: {contacto_telefono} | Email: {contacto_email}" if contacto_principal else "—",
        "Telefono_Contacto": contacto_telefono,
        "Email_Contacto": contacto_email,
        "Nombre_Sucursal": nombre_sucursal,
        "Cantidad_Cajas": cantidad_cajas,
        "Integrador": integrador,
        "Aplicativo_Integracion": aplicativo_integracion,
        "Nombre_Implementador": nombre_implementador,
        "Correo_Implementador": correo_implementador,
        "Telefono_Implementador": telefono_implementador,
        "Matriz_Bancos_Productos": matriz_html,
        "Lista_VTID": lista_vtid,
        "Modelo_Seriales_Equipos": modelo_seriales_html,
        "Modelo_Seriales_POS": modelo_seriales_pos_html,
        "Servidor_Instalacion": servidor_instalacion or "No asignado",
        "Tipo_Comunicacion": tipo_comunicacion or "No asignado",

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

    return variables
