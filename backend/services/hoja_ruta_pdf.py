"""
Generador de PDF "Hoja de Ruta" para entregas de equipos.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch, cm
import io
from datetime import datetime, timezone


COLOR_AZUL = colors.HexColor("#00447C")
COLOR_GRIS_CLARO = colors.HexColor("#F3F4F6")


def generate_hoja_ruta_pdf(
    quote_number: str,
    client_name: str,
    client_rif: str,
    client_address: str,
    warehouse_name: str,
    delivered_items: list,
    delivered_by: str,
    notes: str = "",
    logo_path: str = None,
):
    """
    Genera un PDF de Hoja de Ruta para entrega de equipos.

    delivered_items: list of dicts con:
      - name: str
      - type: str
      - quantity: int
      - serials: list[str]
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "HRTitle", parent=styles["Heading1"],
        fontSize=18, textColor=COLOR_AZUL, spaceAfter=6, alignment=1,
    ))
    styles.add(ParagraphStyle(
        "HRSubtitle", parent=styles["Normal"],
        fontSize=10, textColor=colors.gray, alignment=1, spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        "HRLabel", parent=styles["Normal"],
        fontSize=9, textColor=colors.gray, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "HRValue", parent=styles["Normal"],
        fontSize=10, textColor=colors.black, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "HRSmall", parent=styles["Normal"],
        fontSize=8, textColor=colors.gray,
    ))

    elements = []

    # Header
    elements.append(Paragraph("HOJA DE RUTA", styles["HRTitle"]))
    elements.append(Paragraph("Documento de Entrega de Equipos", styles["HRSubtitle"]))
    elements.append(Spacer(1, 0.3 * cm))

    # Info block
    now = datetime.now(timezone.utc)
    info_data = [
        ["Cotización:", quote_number, "Fecha:", now.strftime("%d/%m/%Y %H:%M")],
        ["Cliente:", client_name, "RIF:", client_rif],
        ["Dirección:", client_address or "—", "Almacén Origen:", warehouse_name],
        ["Responsable:", delivered_by, "", ""],
    ]
    info_table = Table(info_data, colWidths=[2.2 * cm, 7 * cm, 2.8 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.gray),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.gray),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5 * cm))

    # Items table
    header_row = ["#", "Equipo / Producto", "Tipo", "Cantidad", "Serial(es)"]
    table_data = [header_row]

    for idx, item in enumerate(delivered_items, 1):
        serials_str = ", ".join(item.get("serials", [])) if item.get("serials") else "N/A"
        # Wrap long serial lists
        if len(serials_str) > 50:
            serials_str = Paragraph(serials_str, styles["HRSmall"])
        table_data.append([
            str(idx),
            item.get("name", "—"),
            item.get("type", "—"),
            str(item.get("quantity", 0)),
            serials_str,
        ])

    items_table = Table(table_data, colWidths=[0.8 * cm, 5.5 * cm, 2.5 * cm, 1.8 * cm, 6.4 * cm])
    items_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Alternating rows
        *[("BACKGROUND", (0, i), (-1, i), COLOR_GRIS_CLARO) for i in range(2, len(table_data), 2)],
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.5 * cm))

    # Notes
    if notes:
        elements.append(Paragraph("Observaciones:", styles["HRLabel"]))
        elements.append(Paragraph(notes, styles["HRValue"]))
        elements.append(Spacer(1, 0.3 * cm))

    # Signature section
    elements.append(Spacer(1, 1.5 * cm))
    sig_data = [
        ["Entregado por:", "", "Recibido por:", ""],
        ["", "", "", ""],
        ["Firma: ___________________________", "", "Firma: ___________________________", ""],
        ["Nombre: " + delivered_by, "", "Nombre: ___________________________", ""],
        ["Fecha: " + now.strftime("%d/%m/%Y"), "", "Fecha: ___________________________", ""],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 1 * cm, 8 * cm, 0])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, 0), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
