"""
Generador de PDF "Nota de Entrega" para entregas de equipos.
Documento formal con trazabilidad de inventario.
Soporta: encabezados persistentes en todas las páginas, paginación X/Y, anti-split de filas.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    KeepTogether, PageBreak,
)
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfgen import canvas as pdfgen_canvas
import io
import os
from datetime import datetime, timezone

from services.rif_formatter import format_rif


COLOR_AZUL = colors.HexColor("#00447C")
COLOR_GRIS = colors.HexColor("#6B7280")
COLOR_GRIS_CLARO = colors.HexColor("#F3F4F6")
COLOR_BORDE = colors.HexColor("#D1D5DB")
FOOTER_TEXT = "Documento generado por MegaNexus - Trazabilidad de Inventario"

PAGE_W, PAGE_H = letter
MARGIN_L = 1.8 * cm
MARGIN_R = 1.8 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


# ======================== NUMBERED CANVAS (X/Y) ========================

class NumberedCanvas(pdfgen_canvas.Canvas):
    """Canvas que soporta paginación X/Y (Página 1/3, 2/3, 3/3)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            pdfgen_canvas.Canvas.showPage(self)
        pdfgen_canvas.Canvas.save(self)

    def _draw_page_number(self, total):
        self.setFont("Helvetica", 7)
        self.setFillColor(COLOR_GRIS)
        self.drawCentredString(
            PAGE_W / 2, 1.2 * cm,
            FOOTER_TEXT
        )
        self.drawRightString(
            PAGE_W - MARGIN_R, 1.2 * cm,
            f"Pagina {self._pageNumber} / {total}"
        )


# ======================== HEADER DRAWING ========================

def _draw_persistent_header(canvas, doc, header_info):
    """Dibuja encabezado persistente: Logo + Título + Bloque 1 (Info Documento)."""
    canvas.saveState()
    y_top = PAGE_H - 1.2 * cm

    # --- Logo ---
    logo_path = header_info.get("logo_path")
    if logo_path and os.path.exists(logo_path):
        try:
            canvas.drawImage(
                logo_path, MARGIN_L, y_top - 1.2 * cm,
                width=3.5 * cm, height=1.2 * cm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass

    # --- Título ---
    canvas.setFont("Helvetica-Bold", 14)
    canvas.setFillColor(COLOR_AZUL)
    canvas.drawCentredString(PAGE_W / 2, y_top - 0.5 * cm, "NOTA DE ENTREGA")

    # --- Bloque 1: Info compacta (Correlativo | Fecha | Cliente | RIF) ---
    y_info = y_top - 1.8 * cm
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(COLOR_GRIS)

    info_items = [
        ("Nro:", header_info.get("correlativo", "")),
        ("Fecha:", header_info.get("fecha", "")),
        ("Cliente:", header_info.get("client_name", "")[:35]),
        ("RIF:", header_info.get("client_rif", "")),
    ]
    x = MARGIN_L
    for label, value in info_items:
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(COLOR_GRIS)
        canvas.drawString(x, y_info, label)
        w_label = canvas.stringWidth(label, "Helvetica", 7) + 2
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.black)
        canvas.drawString(x + w_label, y_info, value)
        x += w_label + canvas.stringWidth(value, "Helvetica-Bold", 7) + 14

    # --- Línea separadora ---
    canvas.setStrokeColor(COLOR_BORDE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, y_info - 0.3 * cm, PAGE_W - MARGIN_R, y_info - 0.3 * cm)

    canvas.restoreState()


def _on_first_page(canvas, doc):
    """Primera página: sin encabezado repetido (ya está en el flowable content)."""
    pass  # Header is in flowable elements for page 1


def _make_later_pages_handler(header_info):
    """Crea handler para páginas 2+ con encabezado persistente."""
    def handler(canvas, doc):
        _draw_persistent_header(canvas, doc, header_info)
    return handler


# ======================== MAIN GENERATOR ========================

def generate_nota_entrega_pdf(
    correlativo: str,
    quote_number: str,
    project_number: str,
    client_name: str,
    client_rif: str,
    client_address: str,
    client_contact_name: str,
    client_contact_phone: str,
    warehouse_name: str,
    delivered_items: list,
    delivered_by: str,
    transportista: str = "",
    guia_placa: str = "",
    notes: str = "",
    logo_path: str = None,
    delivery_method: str = "personalizada",
    receiver_name: str = "",
    receiver_cedula: str = "",
    receiver_phone: str = "",
    courier_name: str = "",
    courier_office: str = "",
    is_final_delivery: bool = True,
):
    buffer = io.BytesIO()

    now = datetime.now(timezone.utc)
    fecha_str = now.strftime("%d/%m/%Y")

    # Header info for persistent headers on pages 2+
    # Normalizamos RIF a 9 dígitos (padding de ceros) para todos los puntos
    # donde se imprima en el PDF (encabezado persistente y bloque cliente).
    rif_fmt = format_rif(client_rif)
    header_info = {
        "correlativo": correlativo,
        "fecha": fecha_str,
        "client_name": client_name or "",
        "client_rif": rif_fmt,
        "logo_path": logo_path,
    }

    # Margins: pages 2+ have extra top margin for persistent header
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
    )

    styles = getSampleStyleSheet()

    s_title = ParagraphStyle("NETitle", parent=styles["Heading1"],
        fontSize=16, textColor=COLOR_AZUL, spaceAfter=2, alignment=TA_CENTER,
        fontName="Helvetica-Bold")
    s_section = ParagraphStyle("NESection", parent=styles["Heading2"],
        fontSize=10, textColor=COLOR_AZUL, spaceBefore=10, spaceAfter=4,
        fontName="Helvetica-Bold")
    s_label = ParagraphStyle("NELabel", parent=styles["Normal"],
        fontSize=8, textColor=COLOR_GRIS, leading=10)
    s_value = ParagraphStyle("NEValue", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold", leading=12)
    s_small = ParagraphStyle("NESmall", parent=styles["Normal"],
        fontSize=7, textColor=COLOR_GRIS, leading=9)
    s_cell = ParagraphStyle("NECell", parent=styles["Normal"],
        fontSize=8, leading=10, wordWrap="CJK")
    s_cell_serial = ParagraphStyle("NECellSerial", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor("#6D28D9"), leading=9, wordWrap="CJK")

    elements = []

    # ==================== PAGE 1: HEADER (logo + title) ====================
    header_data = []
    logo_cell = ""
    if logo_path and os.path.exists(logo_path):
        try:
            logo_cell = Image(logo_path, width=4 * cm, height=1.5 * cm)
            logo_cell.hAlign = "LEFT"
        except Exception:
            logo_cell = ""

    # Título dinámico: PARCIAL o FINAL según saldo de equipos
    titulo_nota = "NOTA DE ENTREGA FINAL" if is_final_delivery else "NOTA DE ENTREGA PARCIAL"

    header_data = [[logo_cell, Paragraph(titulo_nota, s_title)]]
    header_table = Table(header_data, colWidths=[4.5 * cm, CONTENT_W - 4.5 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))

    # ==================== 1. INFO DOCUMENTO ====================
    elements.append(Paragraph("1. Informacion del Documento", s_section))
    cw = [CONTENT_W * 0.22, CONTENT_W * 0.28, CONTENT_W * 0.22, CONTENT_W * 0.28]
    doc_data = [
        [Paragraph("Nro. Correlativo:", s_label), Paragraph(correlativo, s_value),
         Paragraph("Fecha de Emision:", s_label), Paragraph(fecha_str, s_value)],
        [Paragraph("Referencia Cotizacion:", s_label), Paragraph(quote_number or "—", s_value),
         Paragraph("Almacen de Origen:", s_label), Paragraph(warehouse_name or "—", s_value)],
        [Paragraph("Proyecto Asociado:", s_label), Paragraph(project_number or "—", s_value),
         Paragraph("Estatus:", s_label), Paragraph("Despachado", s_value)],
    ]
    info_tbl = Table(doc_data, colWidths=cw)
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_tbl)

    # ==================== 2. CLIENTE Y DESTINO ====================
    elements.append(Paragraph("2. Datos del Cliente y Destino", s_section))
    s_value_addr = ParagraphStyle("NEValueAddr", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold",
        leading=12, wordWrap="CJK")
    address_para = Paragraph(client_address or "—", s_value_addr)
    cw2 = [CONTENT_W * 0.22, CONTENT_W * 0.32, CONTENT_W * 0.16, CONTENT_W * 0.30]
    client_data = [
        [Paragraph("Razon Social:", s_label), Paragraph(client_name or "—", s_value),
         Paragraph("RIF:", s_label), Paragraph(rif_fmt or "—", s_value)],
        [Paragraph("Direccion de Entrega:", s_label), address_para, "", ""],
        [Paragraph("Contacto:", s_label), Paragraph(client_contact_name or "—", s_value),
         Paragraph("Telefono:", s_label), Paragraph(client_contact_phone or "—", s_value)],
    ]
    cli_tbl = Table(client_data, colWidths=cw2)
    cli_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 0), (2, 0), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 2), (2, 2), COLOR_GRIS_CLARO),
        ("SPAN", (1, 1), (3, 1)),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(cli_tbl)

    # ==================== 3. DETALLE DE BIENES ====================
    elements.append(Paragraph("3. Detalle de Bienes y Equipos", s_section))

    # Estilo para encabezados blancos sobre fondo azul (mejora de contraste)
    s_cell_white = ParagraphStyle("NECellWhite", parent=styles["Normal"],
        fontSize=8, textColor=colors.white, leading=10, wordWrap="CJK",
        fontName="Helvetica-Bold", alignment=TA_CENTER)

    items_header = [
        Paragraph("Item", s_cell_white),
        Paragraph("Descripcion del Bien / Servicio", s_cell_white),
        Paragraph("Cant.", s_cell_white),
        Paragraph("Tipo", s_cell_white),
        Paragraph("Seriales (Solo POS/Pinpad)", s_cell_white),
    ]
    # Anchos fijos: Item=1, Descripcion=5.5, Cant=1.2, Tipo=2, Seriales=restante
    w_item = 1 * cm
    w_desc = 5.5 * cm
    w_qty = 1.2 * cm
    w_type = 2 * cm
    w_serials = CONTENT_W - w_item - w_desc - w_qty - w_type
    item_col_widths = [w_item, w_desc, w_qty, w_type, w_serials]

    # Build header-only table (will repeat via splitInRow=1)
    header_tbl = Table([items_header], colWidths=item_col_widths)
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, 0), 0.5, COLOR_BORDE),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("LEFTPADDING", (0, 0), (-1, 0), 4),
        ("RIGHTPADDING", (0, 0), (-1, 0), 4),
    ]))
    elements.append(header_tbl)

    # Each item row wrapped in KeepTogether to prevent splitting
    for idx, item in enumerate(delivered_items, 1):
        serials = item.get("serials", [])
        if serials:
            # Multi-column layout for serials (3 columns) to reduce pages
            if len(serials) > 4:
                cols = 3
                rows_needed = (len(serials) + cols - 1) // cols
                serial_cells = []
                for r in range(rows_needed):
                    row_serials = []
                    for c in range(cols):
                        idx_s = r * cols + c
                        if idx_s < len(serials):
                            row_serials.append(Paragraph(f"SN: {serials[idx_s]}", s_cell_serial))
                        else:
                            row_serials.append(Paragraph("", s_cell_serial))
                    serial_cells.append(row_serials)
                serial_col_w = w_serials / cols
                serial_tbl = Table(serial_cells, colWidths=[serial_col_w] * cols)
                serial_tbl.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]))
                serials_para = serial_tbl
            else:
                serials_para = Paragraph("<br/>".join([f"SN: {s}" for s in serials]), s_cell_serial)
        else:
            serials_para = Paragraph("NO APLICA", s_small)

        category = item.get("category", "Equipo")
        row_data = [[
            Paragraph(str(idx), s_cell),
            Paragraph(item.get("name", "—"), s_cell),
            Paragraph(str(item.get("quantity", 0)), s_cell),
            Paragraph(category, s_cell),
            serials_para,
        ]]
        row_bg = COLOR_GRIS_CLARO if idx % 2 == 0 else colors.white
        row_tbl = Table(row_data, colWidths=item_col_widths)
        row_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), row_bg),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "CENTER"),
            ("ALIGN", (3, 0), (3, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("GRID", (0, 0), (-1, 0), 0.5, COLOR_BORDE),
            ("TOPPADDING", (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("LEFTPADDING", (0, 0), (-1, 0), 4),
            ("RIGHTPADDING", (0, 0), (-1, 0), 4),
        ]))
        elements.append(KeepTogether([row_tbl]))

    # Notes
    if notes:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(f"<i>Observaciones: {notes}</i>", s_small))

    # ==================== 4. CONTROL LOGISTICO ====================
    elements.append(Paragraph("4. Control Logistico y Transporte", s_section))

    method_label = "Entrega Personalizada" if delivery_method != "courier" else "Courier"
    log_data = [
        [Paragraph("Preparado por (Almacen):", s_label),
         Paragraph(delivered_by or "___________________________", s_value)],
        [Paragraph("Metodo de Envio:", s_label),
         Paragraph(method_label, s_value)],
    ]
    if delivery_method == "courier":
        log_data.extend([
            [Paragraph("Courier:", s_label),
             Paragraph(courier_name or "___________________________", s_value)],
            [Paragraph("Oficina de Destino:", s_label),
             Paragraph(courier_office or "___________________________", s_value)],
            [Paragraph("Contacto Receptor:", s_label),
             Paragraph(f"{receiver_name or '—'}  |  Ced: {receiver_cedula or '—'}  |  Tel: {receiver_phone or '—'}", s_value)],
        ])
    else:
        log_data.extend([
            [Paragraph("Receptor:", s_label),
             Paragraph(receiver_name or transportista or "___________________________", s_value)],
            [Paragraph("Cedula Receptor:", s_label),
             Paragraph(receiver_cedula or "___________________________", s_value)],
            [Paragraph("Telefono Receptor:", s_label),
             Paragraph(receiver_phone or "___________________________", s_value)],
        ])

    log_cw = [CONTENT_W * 0.28, CONTENT_W * 0.72]
    log_tbl = Table(log_data, colWidths=log_cw)
    log_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(KeepTogether([log_tbl]))

    # ==================== 5. RECEPCION Y CONFORMIDAD ====================
    # Salto de página forzado para dejar espacio limpio de firma
    elements.append(PageBreak())

    # El encabezado persistente (logo + título + info) ya se dibuja
    # automáticamente en páginas 2+ por _draw_persistent_header.
    # Solo agregamos espaciado adicional (~4 líneas) antes de la sección.
    elements.append(Spacer(1, 1.5 * cm))

    elements.append(Paragraph("5. Recepcion y Conformidad del Cliente", s_section))
    elements.append(Paragraph(
        "<i>Certifico haber recibido los equipos arriba descritos en perfecto estado y a entera satisfaccion.</i>",
        ParagraphStyle("NEDisclaimer", parent=styles["Normal"],
            fontSize=8, textColor=COLOR_GRIS, leading=10, spaceAfter=6)
    ))
    rec_cw = [CONTENT_W * 0.28, CONTENT_W * 0.72]
    rec_data = [
        [Paragraph("Nombre de quien recibe:", s_label), Paragraph("___________________________", s_value)],
        [Paragraph("Cedula / RIF:", s_label), Paragraph("___________________________", s_value)],
        [Paragraph("Fecha y Hora:", s_label), Paragraph("____/____/________    ____:____", s_value)],
        [Paragraph("Firma y Sello:", s_label), ""],
    ]
    rec_tbl = Table(rec_data, colWidths=rec_cw,
                    rowHeights=[None, None, None, 2.5 * cm])
    rec_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(rec_tbl)

    # Build with NumberedCanvas for X/Y pagination
    doc.build(
        elements,
        onFirstPage=_on_first_page,
        onLaterPages=_make_later_pages_handler(header_info),
        canvasmaker=NumberedCanvas,
    )
    buffer.seek(0)
    return buffer
