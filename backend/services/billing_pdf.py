"""
PDF de Cálculos Definitivos — Hoja de trabajo interna para Administración.
Contiene: datos del cliente, conceptos de Setup consolidados, tasa de cambio, IVA y totales.
"""
import io
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_billing_pdf(quote: dict, client: dict, billing_instruction: dict, executor_name: str) -> bytes:
    """Genera el PDF de Cálculos Definitivos para Administración."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=1.5*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Custom styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#2c3e50'), spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#7f8c8d'), spaceAfter=12)
    header_style = ParagraphStyle('SectionHeader', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#2c3e50'), spaceBefore=14, spaceAfter=6)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#333333'))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#999999'))
    # Style for table cells that need wrapping
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#333333'), leading=11)
    cell_bold_style = ParagraphStyle('CellBoldStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#2c3e50'), fontName='Helvetica-Bold', leading=11)
    cell_right_style = ParagraphStyle('CellRightStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#333333'), alignment=2, leading=11)
    cell_center_style = ParagraphStyle('CellCenterStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#333333'), alignment=1, leading=11)

    # Title
    elements.append(Paragraph("CÁLCULOS DEFINITIVOS DE FACTURACIÓN", title_style))
    elements.append(Paragraph("Documento interno — No enviar al cliente", subtitle_style))
    elements.append(Spacer(1, 6))

    # Client info - use Paragraphs for proper wrapping
    elements.append(Paragraph("Datos del Cliente", header_style))
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'N/A'
    legal_name = client.get('legal_name') or 'N/A'
    rif = client.get('rif') or 'N/A'
    quote_number = quote.get('quote_number') or 'N/A'
    billing_date = billing_instruction.get('billing_date', '')
    approval_date = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')

    info_data = [
        [Paragraph('<b>Cliente:</b>', cell_bold_style), Paragraph(client_name, cell_style)],
        [Paragraph('<b>Razón Social:</b>', cell_bold_style), Paragraph(legal_name, cell_style)],
        [Paragraph('<b>RIF:</b>', cell_bold_style), Paragraph(rif, cell_style)],
        [Paragraph('<b>Nro. Cotización:</b>', cell_bold_style), Paragraph(quote_number, cell_style)],
        [Paragraph('<b>Fecha de Facturación:</b>', cell_bold_style), Paragraph(billing_date or 'No especificada', cell_style)],
        [Paragraph('<b>Fecha de Aprobación:</b>', cell_bold_style), Paragraph(approval_date, cell_style)],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 13*cm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # Consolidated setup items table
    items = billing_instruction.get('consolidated_items', [])
    exchange_rate = billing_instruction.get('exchange_rate', 0)
    rate_source = billing_instruction.get('rate_source', 'Manual')

    elements.append(Paragraph("Conceptos de Setup y Productos Consolidados", header_style))
    elements.append(Paragraph(f"Tasa de Cambio aplicada: <b>Bs. {exchange_rate:,.2f} / $</b> — Fuente: {rate_source}", normal_style))
    elements.append(Spacer(1, 8))

    # Table header - use Paragraphs for headers too
    header_cell_style = ParagraphStyle('HeaderCell', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName='Helvetica-Bold', leading=11)
    header_center = ParagraphStyle('HeaderCenter', parent=header_cell_style, alignment=1)
    header_right = ParagraphStyle('HeaderRight', parent=header_cell_style, alignment=2)

    table_data = [[
        Paragraph('Concepto', header_cell_style),
        Paragraph('Cant.', header_center),
        Paragraph('Monto ($)', header_right),
        Paragraph('Tasa Bs./$', header_center),
        Paragraph('Total (Bs.)', header_right),
    ]]

    for item in items:
        bs_val = item.get('total_bs', item.get('total_usd', 0) * exchange_rate)
        table_data.append([
            Paragraph(item.get('name', 'N/A'), cell_style),
            Paragraph(str(item.get('quantity', 1)), cell_center_style),
            Paragraph(f"${item.get('total_usd', 0):,.2f}", cell_right_style),
            Paragraph(f"{exchange_rate:,.2f}", cell_center_style),
            Paragraph(f"Bs. {bs_val:,.2f}", cell_right_style),
        ])

    # Summary rows style
    cell_bold_right = ParagraphStyle('CellBoldRight', parent=cell_right_style, fontName='Helvetica-Bold')

    # Subtotal row
    subtotal_usd = billing_instruction.get('grand_total_usd', 0)
    subtotal_bs = billing_instruction.get('grand_total_bs', 0)
    table_data.append([
        Paragraph('<b>SUBTOTAL</b>', cell_bold_style), '',
        Paragraph(f"<b>${subtotal_usd:,.2f}</b>", cell_bold_right), '',
        Paragraph(f"<b>Bs. {subtotal_bs:,.2f}</b>", cell_bold_right),
    ])

    # IVA row
    iva_usd = billing_instruction.get('iva_usd', subtotal_usd * 0.16)
    iva_bs = billing_instruction.get('iva_bs', subtotal_bs * 0.16)
    table_data.append([
        Paragraph('IVA (16%)', cell_style), '',
        Paragraph(f"${iva_usd:,.2f}", cell_right_style), '',
        Paragraph(f"Bs. {iva_bs:,.2f}", cell_right_style),
    ])

    # Total row
    total_usd = billing_instruction.get('grand_total_con_iva_usd', subtotal_usd + iva_usd)
    total_bs = billing_instruction.get('grand_total_con_iva_bs', subtotal_bs + iva_bs)
    total_white_style = ParagraphStyle('TotalWhite', parent=cell_style, textColor=colors.white, fontName='Helvetica-Bold', fontSize=10, alignment=2)
    total_white_left = ParagraphStyle('TotalWhiteLeft', parent=total_white_style, alignment=0)
    table_data.append([
        Paragraph('<b>TOTAL GENERAL</b>', total_white_left), '',
        Paragraph(f"<b>${total_usd:,.2f}</b>", total_white_style), '',
        Paragraph(f"<b>Bs. {total_bs:,.2f}</b>", total_white_style),
    ])

    num_items = len(items)
    # Adjusted column widths: wider concept, wider Bs. total for large numbers
    col_widths = [6.5*cm, 1.5*cm, 2.8*cm, 2.5*cm, 4.2*cm]
    t = Table(table_data, colWidths=col_widths)

    style_commands = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        # Body
        ('ROWBACKGROUNDS', (0, 1), (-1, num_items), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Subtotal row
        ('BACKGROUND', (0, num_items + 1), (-1, num_items + 1), colors.HexColor('#f0f0f0')),
        # IVA row
        ('BACKGROUND', (0, num_items + 2), (-1, num_items + 2), colors.HexColor('#f0f0f0')),
        # Total row
        ('BACKGROUND', (0, num_items + 3), (-1, num_items + 3), colors.HexColor('#2c3e50')),
    ]
    t.setStyle(TableStyle(style_commands))
    elements.append(t)

    # Payment proof note
    if billing_instruction.get('has_payment_proof'):
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("El ejecutivo adjuntó comprobante de pago anticipado a este correo.", ParagraphStyle('Note', parent=normal_style, textColor=colors.HexColor('#27ae60'), fontName='Helvetica-Bold')))

    # Approval proof note
    if billing_instruction.get('has_approval_proof'):
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("El ejecutivo adjuntó comprobante de aprobación de cotización a este correo.", ParagraphStyle('Note2', parent=normal_style, textColor=colors.HexColor('#2980b9'), fontName='Helvetica-Bold')))

    # Footer: executor name + timestamp
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"Procesado por: <b>{executor_name}</b>", normal_style))
    elements.append(Paragraph(f"Generado: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC')}", footer_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Este documento es de uso interno y no debe ser compartido con el cliente.", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
