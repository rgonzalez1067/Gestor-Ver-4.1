"""
Generador de PDF "Nota de Entrega" para entregas de equipos.
Documento formal con trazabilidad de inventario.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, Frame, PageTemplate
)
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
import io
import os
from datetime import datetime, timezone


COLOR_AZUL = colors.HexColor("#00447C")
COLOR_AZUL_CLARO = colors.HexColor("#E8F0FE")
COLOR_GRIS = colors.HexColor("#6B7280")
COLOR_GRIS_CLARO = colors.HexColor("#F3F4F6")
COLOR_BORDE = colors.HexColor("#D1D5DB")
FOOTER_TEXT = "Documento generado por MegaNexus - Trazabilidad de Inventario"


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(COLOR_GRIS)
    canvas.drawCentredString(
        doc.pagesize[0] / 2, 1.2 * cm,
        FOOTER_TEXT
    )
    canvas.drawRightString(
        doc.pagesize[0] - 2 * cm, 1.2 * cm,
        f"Pag. {canvas.getPageNumber()}"
    )
    canvas.restoreState()


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
):
    """
    Genera un PDF de Nota de Entrega formal.

    delivered_items: list of dicts con:
      - name: str
      - type: str (tipo de hardware)
      - category: str ("Equipo" o "Consumible")
      - quantity: int
      - serials: list[str]
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()

    s_title = ParagraphStyle("NETitle", parent=styles["Heading1"],
        fontSize=16, textColor=COLOR_AZUL, spaceAfter=2, alignment=TA_CENTER,
        fontName="Helvetica-Bold")
    s_subtitle = ParagraphStyle("NESubtitle", parent=styles["Normal"],
        fontSize=9, textColor=COLOR_GRIS, alignment=TA_CENTER, spaceAfter=10)
    s_section = ParagraphStyle("NESection", parent=styles["Heading2"],
        fontSize=10, textColor=COLOR_AZUL, spaceBefore=12, spaceAfter=4,
        fontName="Helvetica-Bold", borderPadding=(0, 0, 2, 0))
    s_label = ParagraphStyle("NELabel", parent=styles["Normal"],
        fontSize=8, textColor=COLOR_GRIS, leading=10)
    s_value = ParagraphStyle("NEValue", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold", leading=12)
    s_value_wrap = ParagraphStyle("NEValueWrap", parent=styles["Normal"],
        fontSize=9, textColor=colors.black, fontName="Helvetica-Bold",
        leading=12, wordWrap="CJK")
    s_small = ParagraphStyle("NESmall", parent=styles["Normal"],
        fontSize=7, textColor=COLOR_GRIS, leading=9)
    s_cell = ParagraphStyle("NECell", parent=styles["Normal"],
        fontSize=8, leading=10)
    s_cell_serial = ParagraphStyle("NECellSerial", parent=styles["Normal"],
        fontSize=7, textColor=colors.HexColor("#6D28D9"), leading=9)

    elements = []
    now = datetime.now(timezone.utc)

    # ==================== HEADER WITH LOGO ====================
    header_data = []
    logo_cell = ""
    if logo_path and os.path.exists(logo_path):
        try:
            logo_cell = Image(logo_path, width=4 * cm, height=1.5 * cm)
            logo_cell.hAlign = "LEFT"
        except Exception:
            logo_cell = ""

    header_data = [[
        logo_cell,
        Paragraph("NOTA DE ENTREGA", s_title),
    ]]
    header_table = Table(header_data, colWidths=[4.5 * cm, 13 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3 * cm))

    # ==================== 1. INFORMACION DEL DOCUMENTO ====================
    elements.append(Paragraph("1. Informacion del Documento", s_section))

    doc_data = [
        [
            Paragraph("Nro. Correlativo:", s_label),
            Paragraph(correlativo, s_value),
            Paragraph("Fecha de Emision:", s_label),
            Paragraph(now.strftime("%d/%m/%Y"), s_value),
        ],
        [
            Paragraph("Referencia Cotizacion:", s_label),
            Paragraph(quote_number or "—", s_value),
            Paragraph("Almacen de Origen:", s_label),
            Paragraph(warehouse_name or "—", s_value),
        ],
        [
            Paragraph("Proyecto Asociado:", s_label),
            Paragraph(project_number or "—", s_value),
            Paragraph("Estatus:", s_label),
            Paragraph("Despachado", s_value),
        ],
    ]
    doc_table = Table(doc_data, colWidths=[3.8 * cm, 4.5 * cm, 3.8 * cm, 5.4 * cm])
    doc_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 0), (2, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(doc_table)

    # ==================== 2. DATOS DEL CLIENTE Y DESTINO ====================
    elements.append(Paragraph("2. Datos del Cliente y Destino", s_section))

    # Address with word wrap
    address_para = Paragraph(client_address or "—", s_value_wrap) if client_address else Paragraph("—", s_value)

    client_data = [
        [
            Paragraph("Razon Social:", s_label),
            Paragraph(client_name or "—", s_value),
            Paragraph("RIF:", s_label),
            Paragraph(client_rif or "—", s_value),
        ],
        [
            Paragraph("Direccion de Entrega:", s_label),
            address_para,
            "",
            "",
        ],
        [
            Paragraph("Contacto:", s_label),
            Paragraph(client_contact_name or "—", s_value),
            Paragraph("Telefono:", s_label),
            Paragraph(client_contact_phone or "—", s_value),
        ],
    ]
    client_table = Table(client_data, colWidths=[3.8 * cm, 5.5 * cm, 2.8 * cm, 5.4 * cm])
    client_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 0), (2, 0), COLOR_GRIS_CLARO),
        ("BACKGROUND", (2, 2), (2, 2), COLOR_GRIS_CLARO),
        ("SPAN", (1, 1), (3, 1)),  # Address spans full width
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(client_table)

    # ==================== 3. DETALLE DE BIENES Y EQUIPOS ====================
    elements.append(Paragraph("3. Detalle de Bienes y Equipos", s_section))

    items_header = [
        Paragraph("<b>Item</b>", s_cell),
        Paragraph("<b>Descripcion del Bien / Servicio</b>", s_cell),
        Paragraph("<b>Cant.</b>", s_cell),
        Paragraph("<b>Tipo</b>", s_cell),
        Paragraph("<b>Seriales (Solo POS/Pinpad)</b>", s_cell),
    ]
    items_data = [items_header]

    SERIALIZED = ["pos", "pinpad", "mpos"]

    for idx, item in enumerate(delivered_items, 1):
        serials = item.get("serials", [])
        is_serialized = item.get("type", "").lower() in SERIALIZED
        if serials:
            serials_para = Paragraph(
                "<br/>".join([f"SN: {s}" for s in serials]),
                s_cell_serial
            )
        else:
            serials_para = Paragraph("N/A", s_small)

        category = item.get("category", "Equipo")
        items_data.append([
            Paragraph(str(idx), s_cell),
            Paragraph(item.get("name", "—"), s_cell),
            Paragraph(str(item.get("quantity", 0)), s_cell),
            Paragraph(category, s_cell),
            serials_para,
        ])

    items_table = Table(items_data, colWidths=[1 * cm, 6 * cm, 1.3 * cm, 2.5 * cm, 6.7 * cm])
    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Alternating rows
        *[("BACKGROUND", (0, i), (-1, i), COLOR_GRIS_CLARO) for i in range(2, len(items_data), 2)],
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)

    # Notes
    if notes:
        elements.append(Spacer(1, 0.2 * cm))
        elements.append(Paragraph(f"<i>Observaciones: {notes}</i>", s_small))

    # ==================== 4. CONTROL LOGISTICO Y TRANSPORTE ====================
    elements.append(Paragraph("4. Control Logistico y Transporte", s_section))

    logistic_data = [
        [
            Paragraph("Preparado por (Almacen):", s_label),
            Paragraph(delivered_by or "___________________________", s_value),
        ],
        [
            Paragraph("Transportado por:", s_label),
            Paragraph(transportista or "___________________________", s_value),
        ],
        [
            Paragraph("Nro. de Guia / Placa:", s_label),
            Paragraph(guia_placa or "___________________________", s_value),
        ],
    ]
    logistic_table = Table(logistic_data, colWidths=[4.5 * cm, 13 * cm])
    logistic_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(logistic_table)

    # ==================== 5. RECEPCION Y CONFORMIDAD ====================
    elements.append(Paragraph("5. Recepcion y Conformidad del Cliente", s_section))

    elements.append(Paragraph(
        "<i>Certifico haber recibido los equipos arriba descritos en perfecto estado y a entera satisfaccion.</i>",
        ParagraphStyle("NEDisclaimer", parent=styles["Normal"],
            fontSize=8, textColor=COLOR_GRIS, leading=10, spaceAfter=6)
    ))

    reception_data = [
        [
            Paragraph("Nombre de quien recibe:", s_label),
            Paragraph("___________________________", s_value),
        ],
        [
            Paragraph("Cedula / RIF:", s_label),
            Paragraph("___________________________", s_value),
        ],
        [
            Paragraph("Fecha y Hora:", s_label),
            Paragraph("____/____/________    ____:____", s_value),
        ],
        [
            Paragraph("Firma y Sello:", s_label),
            "",
        ],
    ]
    reception_table = Table(reception_data, colWidths=[4.5 * cm, 13 * cm], rowHeights=[None, None, None, 2.5 * cm])
    reception_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("BACKGROUND", (0, 0), (0, -1), COLOR_GRIS_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(reception_table)

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
