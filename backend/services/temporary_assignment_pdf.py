"""
Generador de PDF "Comprobante de Asignación Temporal de Equipos".
Documento de respaldo para entrega transitoria de inventario a personal
interno o terceros (integradores, contratistas). Incluye firma del responsable.
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
from datetime import datetime, timezone

COLOR_NARANJA = colors.HexColor("#D97706")
COLOR_AZUL = colors.HexColor("#00447C")
COLOR_GRIS = colors.HexColor("#6B7280")
COLOR_GRIS_CLARO = colors.HexColor("#F3F4F6")
COLOR_BORDE = colors.HexColor("#D1D5DB")
FOOTER_TEXT = "Documento generado por MegaNexus — Asignación Temporal de Inventario"


def generate_temporary_assignment_pdf(assignment: dict, items_detail: list = None) -> bytes:
    """
    Genera el PDF de comprobante de asignación temporal.

    assignment: dict con campos del documento `temporary_assignments`.
    items_detail: opcional, lista para múltiples ítems (futuro). Si no se pasa,
                  se usa la info del propio assignment (un solo ítem).
    """
    buffer = io.BytesIO()
    now = datetime.now(timezone.utc)
    fecha_emision = now.strftime("%d/%m/%Y %H:%M")
    is_external = bool(assignment.get("is_external_responsible"))

    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
    )

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("Title", parent=styles["Heading1"],
                             fontSize=15, textColor=COLOR_NARANJA, alignment=TA_CENTER,
                             fontName="Helvetica-Bold", spaceAfter=4)
    s_sub = ParagraphStyle("Sub", parent=styles["Normal"],
                           fontSize=9, textColor=COLOR_GRIS, alignment=TA_CENTER, spaceAfter=10)
    s_section = ParagraphStyle("Section", parent=styles["Heading2"],
                               fontSize=10, textColor=COLOR_AZUL, spaceBefore=10, spaceAfter=4,
                               fontName="Helvetica-Bold")
    s_label = ParagraphStyle("Label", parent=styles["Normal"],
                             fontSize=8, textColor=COLOR_GRIS, leading=10)
    s_value = ParagraphStyle("Value", parent=styles["Normal"],
                             fontSize=9, fontName="Helvetica-Bold", leading=12)
    s_cell = ParagraphStyle("Cell", parent=styles["Normal"],
                            fontSize=8, leading=10, wordWrap="CJK")
    s_note = ParagraphStyle("Note", parent=styles["Normal"],
                            fontSize=8, textColor=colors.HexColor("#92400E"),
                            fontName="Helvetica-Oblique", leading=11, spaceBefore=6, spaceAfter=6)

    story = []
    # === Encabezado ===
    story.append(Paragraph("COMPROBANTE DE ASIGNACIÓN TEMPORAL DE EQUIPOS", s_title))
    story.append(Paragraph(
        f"Documento Nº <b>{assignment.get('assignment_id','')}</b> · Emitido: {fecha_emision}",
        s_sub
    ))
    if is_external:
        story.append(Paragraph(
            "⚠ ENTREGA A PERSONA EXTERNA — Requiere firma del responsable.",
            s_note
        ))

    # === Datos del responsable ===
    story.append(Paragraph("DATOS DEL RESPONSABLE", s_section))
    resp_email = assignment.get("responsible_email") or "—"
    resp_tipo = "Externo (integrador/contratista)" if is_external else "Personal Interno"
    info_rows = [
        [Paragraph("Tipo:", s_label), Paragraph(resp_tipo, s_value)],
        [Paragraph("Nombre:", s_label), Paragraph(assignment.get("responsible_name", ""), s_value)],
    ]
    if not is_external:
        info_rows.append([Paragraph("Email:", s_label), Paragraph(resp_email, s_value)])
    info_rows.append([Paragraph("Fecha asignación:", s_label),
                      Paragraph(assignment.get("assigned_date", ""), s_value)])
    info_rows.append([Paragraph("Almacén origen:", s_label),
                      Paragraph(assignment.get("warehouse_name", ""), s_value)])
    info_rows.append([Paragraph("Entregado por:", s_label),
                      Paragraph(assignment.get("created_by_name", ""), s_value)])

    t_info = Table(info_rows, colWidths=[4 * cm, None])
    t_info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, COLOR_BORDE),
    ]))
    story.append(t_info)

    # === Motivo / Descripción (incluye empresa + teléfono para externos) ===
    story.append(Paragraph("MOTIVO / DESCRIPCIÓN", s_section))
    motivo_box = Table(
        [[Paragraph((assignment.get("reason") or "").replace("\n", "<br/>"), s_cell)]],
        colWidths=[None],
    )
    motivo_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_GRIS_CLARO),
        ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(motivo_box)

    # === Equipos asignados ===
    story.append(Paragraph("EQUIPOS ENTREGADOS", s_section))
    rows = [[
        Paragraph("<b>Equipo</b>", s_cell),
        Paragraph("<b>Tipo</b>", s_cell),
        Paragraph("<b>Cant.</b>", s_cell),
        Paragraph("<b>Seriales</b>", s_cell),
    ]]
    items = items_detail or [{
        "name": assignment.get("item_name", ""),
        "type": assignment.get("item_type", "General"),
        "quantity": assignment.get("quantity", 0),
        "serials": assignment.get("serials", []) or [],
    }]
    for it in items:
        serials_text = ", ".join(it.get("serials", [])) if it.get("serials") else "NO APLICA"
        rows.append([
            Paragraph(it.get("name", ""), s_cell),
            Paragraph(it.get("type", "General"), s_cell),
            Paragraph(str(it.get("quantity", 0)), s_cell),
            Paragraph(serials_text, s_cell),
        ])
    t = Table(rows, colWidths=[5.5 * cm, 2.5 * cm, 1.5 * cm, None])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, COLOR_BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    # === Declaración y firma ===
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<b>DECLARACIÓN:</b> El responsable identificado en este documento recibe en su poder, en calidad "
        "de asignación temporal, los equipos arriba detallados. Se compromete a su custodia, buen uso y "
        "devolución íntegra. Cualquier daño, pérdida o demora en la devolución será de su entera "
        "responsabilidad. La devolución debe realizarse a través del sistema MegaNexus generando el "
        "movimiento correspondiente.",
        s_cell,
    ))
    story.append(Spacer(1, 20))

    sig_rows = [[
        Paragraph("_________________________________<br/><font size=8>RECIBE</font><br/>"
                  f"<b>{assignment.get('responsible_name','')}</b>", s_cell),
        Paragraph("_________________________________<br/><font size=8>ENTREGA</font><br/>"
                  f"<b>{assignment.get('created_by_name','')}</b>", s_cell),
    ]]
    t_sig = Table(sig_rows, colWidths=[8 * cm, 8 * cm])
    t_sig.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_sig)

    story.append(Spacer(1, 14))
    story.append(Paragraph(FOOTER_TEXT, ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=7,
        textColor=COLOR_GRIS, alignment=TA_CENTER,
    )))

    doc.build(story)
    return buffer.getvalue()
