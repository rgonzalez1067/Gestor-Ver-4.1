"""
Generador de PDF "Nota de Entrega por Transferencia entre Almacenes".
Documento formal con trazabilidad de equipos y responsabilidad de custodios.
Soporta: encabezados persistentes, paginación X/Y, nota técnica condicional para Pinpads.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    KeepTogether,
)
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas as pdfgen_canvas
import io
import os
from datetime import datetime, timezone


COLOR_AZUL = colors.HexColor("#00447C")
COLOR_GRIS = colors.HexColor("#6B7280")
COLOR_GRIS_CLARO = colors.HexColor("#F3F4F6")
COLOR_BORDE = colors.HexColor("#D1D5DB")
FOOTER_TEXT = "Documento generado por MegaNexus - Control de Inventarios"

PAGE_W, PAGE_H = letter
MARGIN_L = 1.8 * cm
MARGIN_R = 1.8 * cm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

SERIALIZED_TYPES = ["pos", "pinpad", "mpos"]


class NumberedCanvas(pdfgen_canvas.Canvas):
    """Canvas con paginación X/Y."""

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
        self.drawCentredString(PAGE_W / 2, 1.2 * cm, FOOTER_TEXT)
        self.drawRightString(
            PAGE_W - MARGIN_R, 1.2 * cm,
            f"Pagina {self._pageNumber} / {total}",
        )


def _draw_persistent_header(canvas, doc, header_info):
    """Encabezado persistente en páginas 2+."""
    canvas.saveState()
    y_top = PAGE_H - 1.2 * cm

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

    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(COLOR_AZUL)
    canvas.drawCentredString(
        PAGE_W / 2, y_top - 0.4 * cm,
        "NOTA DE ENTREGA POR TRANSFERENCIA ENTRE ALMACENES",
    )

    y_info = y_top - 1.6 * cm
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(COLOR_GRIS)
    info_items = [
        ("Nro:", header_info.get("transfer_number", "")),
        ("Fecha:", header_info.get("fecha", "")),
        ("Origen:", header_info.get("source_name", "")[:25]),
        ("Destino:", header_info.get("dest_name", "")[:25]),
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

    canvas.setStrokeColor(COLOR_BORDE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, y_info - 0.3 * cm, PAGE_W - MARGIN_R, y_info - 0.3 * cm)

    canvas.restoreState()


def _on_first_page(canvas, doc):
    pass


def _make_later_pages_handler(header_info):
    def handler(canvas, doc):
        _draw_persistent_header(canvas, doc, header_info)
    return handler


def generate_transfer_note_pdf(
    transfer_number: str,
    source_warehouse_name: str,
    source_responsible_name: str,
    source_responsible_cedula: str,
    dest_warehouse_name: str,
    dest_responsible_name: str,
    transferred_items: list,
    transferred_by: str,
    notes: str = "",
    logo_path: str = None,
):
    """
    Genera un PDF de Nota de Entrega por Transferencia entre Almacenes.

    transferred_items: list of dicts with keys:
        name, type, quantity, serials (list of str)
    """
    buffer = io.BytesIO()
    now = datetime.now(timezone.utc)
    fecha_str = now.strftime("%d/%m/%Y")
    hora_str = now.strftime("%H:%M")

    header_info = {
        "transfer_number": transfer_number,
        "fecha": fecha_str,
        "source_name": source_warehouse_name or "",
        "dest_name": dest_warehouse_name or "",
        "logo_path": logo_path,
    }

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
    )

    styles = getSampleStyleSheet()

    s_title = ParagraphStyle(
        "TTitle", parent=styles["Heading1"],
        fontSize=14, textColor=COLOR_AZUL, spaceAfter=2,
        alignment=TA_CENTER, fontName="Helvetica-Bold",
    )
    s_section = ParagraphStyle(
        "TSection", parent=styles["Heading2"],
        fontSize=10, textColor=COLOR_AZUL, spaceBefore=10, spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    s_label = ParagraphStyle(
        "TLabel", parent=styles["Normal"],
        fontSize=8, textColor=COLOR_GRIS, leading=10,
    )
    s_value = ParagraphStyle(
        "TValue", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold", leading=12,
    )
    s_small = ParagraphStyle(
        "TSmall", parent=styles["Normal"],
        fontSize=7, textColor=COLOR_GRIS, leading=9,
    )
    s_cell = ParagraphStyle(
        "TCell", parent=styles["Normal"],
        fontSize=8, leading=10, wordWrap="CJK",
    )
    s_cell_serial = ParagraphStyle(
        "TCellSerial", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor("#6D28D9"), leading=9, wordWrap="CJK",
    )
    s_note = ParagraphStyle(
        "TNote", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#92400E"),
        fontName="Helvetica-BoldOblique", leading=11, spaceBefore=6, spaceAfter=6,
    )

    elements = []

    # ==================== HEADER (Pagina 1) ====================
    header_data = []
    logo_cell = ""
    if logo_path and os.path.exists(logo_path):
        try:
            logo_cell = Image(logo_path, width=4 * cm, height=1.5 * cm)
            logo_cell.hAlign = "LEFT"
        except Exception:
            logo_cell = ""

    header_data = [[logo_cell, Paragraph("NOTA DE ENTREGA POR TRANSFERENCIA<br/>ENTRE ALMACENES", s_title)]]
    header_table = Table(header_data, colWidths=[4.5 * cm, CONTENT_W - 4.5 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))

    # ==================== 1. INFORMACION DE TRANSFERENCIA ====================
    elements.append(Paragraph("1. Informacion de la Transferencia", s_section))
    cw = [CONTENT_W * 0.22, CONTENT_W * 0.28, CONTENT_W * 0.22, CONTENT_W * 0.28]
    doc_data = [
        [
            Paragraph("Nro. Transferencia:", s_label),
            Paragraph(transfer_number, s_value),
            Paragraph("Fecha:", s_label),
            Paragraph(fecha_str, s_value),
        ],
        [
            Paragraph("Hora:", s_label),
            Paragraph(hora_str, s_value),
            Paragraph("Realizado por:", s_label),
            Paragraph(transferred_by or "—", s_value),
        ],
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

    # ==================== 2. RUTA DE TRANSFERENCIA ====================
    elements.append(Paragraph("2. Ruta de Transferencia", s_section))
    cw2 = [CONTENT_W * 0.22, CONTENT_W * 0.28, CONTENT_W * 0.22, CONTENT_W * 0.28]
    route_data = [
        [
            Paragraph("Almacen Origen:", s_label),
            Paragraph(source_warehouse_name or "—", s_value),
            Paragraph("Almacen Destino:", s_label),
            Paragraph(dest_warehouse_name or "—", s_value),
        ],
        [
            Paragraph("Responsable Origen:", s_label),
            Paragraph(source_responsible_name or "—", s_value),
            Paragraph("Responsable Destino:", s_label),
            Paragraph(dest_responsible_name or "—", s_value),
        ],
    ]
    route_tbl = Table(route_data, colWidths=cw2)
    route_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(route_tbl)

    # ==================== 3. DETALLE DE ITEMS ====================
    elements.append(Paragraph("3. Detalle de Bienes Transferidos", s_section))

    items_header = [
        Paragraph("<b>Item</b>", s_cell),
        Paragraph("<b>Descripcion del Bien</b>", s_cell),
        Paragraph("<b>Cant.</b>", s_cell),
        Paragraph("<b>Tipo</b>", s_cell),
        Paragraph("<b>Seriales</b>", s_cell),
    ]
    # Anchos fijos: Item=1, Descripcion=5.5, Cant=1.2, Tipo=2, Seriales=restante
    t_w_item = 1 * cm
    t_w_desc = 5.5 * cm
    t_w_qty = 1.2 * cm
    t_w_type = 2 * cm
    t_w_serials = CONTENT_W - t_w_item - t_w_desc - t_w_qty - t_w_type
    item_col_widths = [t_w_item, t_w_desc, t_w_qty, t_w_type, t_w_serials]

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

    has_pinpads = False
    for idx, item in enumerate(transferred_items, 1):
        item_type = (item.get("type") or "").lower()
        if item_type == "pinpad":
            has_pinpads = True

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
                serial_col_w = t_w_serials / cols
                serial_tbl_inner = Table(serial_cells, colWidths=[serial_col_w] * cols)
                serial_tbl_inner.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]))
                serials_para = serial_tbl_inner
            else:
                serials_para = Paragraph("<br/>".join([f"SN: {s}" for s in serials]), s_cell_serial)
        else:
            serials_para = Paragraph("NO APLICA", s_small)

        row_data = [[
            Paragraph(str(idx), s_cell),
            Paragraph(item.get("name", "—"), s_cell),
            Paragraph(str(item.get("quantity", 0)), s_cell),
            Paragraph(item.get("type", "General"), s_cell),
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

    # Nota técnica condicional para Pinpads
    if has_pinpads:
        elements.append(Paragraph(
            "Nota tecnica: Los PinPads son entregados con: Cable USB, Licencia EMV y Privacy Shields.",
            s_note,
        ))

    # Observaciones
    if notes:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(f"<i>Observaciones: {notes}</i>", s_small))

    # ==================== 4. FIRMAS DE RESPONSABILIDAD ====================
    elements.append(Paragraph("4. Firmas de Responsabilidad", s_section))

    # Sub-bloque: Entregado Por (Origen) y Recibido Por
    sig_col = CONTENT_W * 0.48
    sig_label = ParagraphStyle(
        "SigLabel", parent=styles["Normal"],
        fontSize=8, textColor=COLOR_GRIS, leading=10,
    )
    sig_value = ParagraphStyle(
        "SigValue", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold", leading=12,
    )
    sig_blank = ParagraphStyle(
        "SigBlank", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, leading=12,
    )
    sig_disclaimer = ParagraphStyle(
        "SigDisclaimer", parent=styles["Normal"],
        fontSize=7, textColor=COLOR_GRIS, leading=9, fontName="Helvetica-Oblique",
    )

    # Build signature table: Left = Origen, Right = Recepcion
    sig_data = [
        [
            Paragraph("<b>ENTREGADO POR (Almacen Origen)</b>", sig_label),
            Paragraph("<b>RECIBIDO POR</b>", sig_label),
        ],
        [
            Paragraph(f"Nombre: {source_responsible_name or '___________________________'}", sig_value),
            Paragraph("Nombre: ___________________________", sig_blank),
        ],
        [
            Paragraph(f"Cedula: {source_responsible_cedula or '___________________________'}", sig_value),
            Paragraph("Cedula: ___________________________", sig_blank),
        ],
        [
            Paragraph("Firma: ___________________________", sig_blank),
            Paragraph("Firma: ___________________________", sig_blank),
        ],
        [
            Paragraph("Fecha: ___________________________", sig_blank),
            Paragraph("Fecha: ___________________________", sig_blank),
        ],
    ]
    sig_tbl = Table(sig_data, colWidths=[sig_col, sig_col])
    sig_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(KeepTogether([sig_tbl]))

    # Nota aclaratoria
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph(
        "<i>Nota: Quien recibe no es necesariamente el responsable del almacen destino.</i>",
        sig_disclaimer,
    ))

    # Build PDF
    doc.build(
        elements,
        onFirstPage=_on_first_page,
        onLaterPages=_make_later_pages_handler(header_info),
        canvasmaker=NumberedCanvas,
    )
    buffer.seek(0)
    return buffer
