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

    # Title
    elements.append(Paragraph("CÁLCULOS DEFINITIVOS DE FACTURACIÓN", title_style))
    elements.append(Paragraph("Documento interno — No enviar al cliente", subtitle_style))
    elements.append(Spacer(1, 6))

    # Client info
    elements.append(Paragraph("Datos del Cliente", header_style))
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'N/A'
    legal_name = client.get('legal_name') or 'N/A'
    rif = client.get('rif') or 'N/A'
    quote_number = quote.get('quote_number') or 'N/A'

    info_data = [
        ['Cliente:', client_name],
        ['Razón Social:', legal_name],
        ['RIF:', rif],
        ['Nro. Cotización:', quote_number],
        ['Fecha de Aprobación:', datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # Consolidated setup items table
    items = billing_instruction.get('consolidated_items', [])
    exchange_rate = billing_instruction.get('exchange_rate', 0)

    elements.append(Paragraph("Conceptos de Setup Consolidados", header_style))
    elements.append(Paragraph(f"Tasa de Cambio aplicada: <b>Bs. {exchange_rate:.2f} / $</b>", normal_style))
    elements.append(Spacer(1, 8))

    # Table header
    table_data = [['Concepto', 'Cant.', 'Monto ($)', 'Tasa Bs./$', 'Total (Bs.)']]
    for item in items:
        bs_val = item.get('total_bs', item.get('total_usd', 0) * exchange_rate)
        override_mark = ' *' if item.get('is_override') else ''
        table_data.append([
            item.get('name', 'N/A'),
            str(item.get('quantity', 1)),
            f"${item.get('total_usd', 0):,.2f}",
            f"{exchange_rate:,.2f}",
            f"Bs. {bs_val:,.2f}{override_mark}",
        ])

    # Subtotal row
    subtotal_usd = billing_instruction.get('grand_total_usd', 0)
    subtotal_bs = billing_instruction.get('grand_total_bs', 0)
    table_data.append(['SUBTOTAL', '', f"${subtotal_usd:,.2f}", '', f"Bs. {subtotal_bs:,.2f}"])

    # IVA row
    iva_usd = billing_instruction.get('iva_usd', subtotal_usd * 0.16)
    iva_bs = billing_instruction.get('iva_bs', subtotal_bs * 0.16)
    table_data.append(['IVA (16%)', '', f"${iva_usd:,.2f}", '', f"Bs. {iva_bs:,.2f}"])

    # Total row
    total_usd = billing_instruction.get('grand_total_con_iva_usd', subtotal_usd + iva_usd)
    total_bs = billing_instruction.get('grand_total_con_iva_bs', subtotal_bs + iva_bs)
    table_data.append(['TOTAL GENERAL', '', f"${total_usd:,.2f}", '', f"Bs. {total_bs:,.2f}"])

    num_items = len(items)
    col_widths = [7*cm, 1.5*cm, 3*cm, 2.5*cm, 3.5*cm]
    t = Table(table_data, colWidths=col_widths)

    style_commands = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        # Body
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, num_items), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        # Subtotal row
        ('BACKGROUND', (0, num_items + 1), (-1, num_items + 1), colors.HexColor('#f0f0f0')),
        ('FONTNAME', (0, num_items + 1), (-1, num_items + 1), 'Helvetica-Bold'),
        # IVA row
        ('BACKGROUND', (0, num_items + 2), (-1, num_items + 2), colors.HexColor('#f0f0f0')),
        # Total row
        ('BACKGROUND', (0, num_items + 3), (-1, num_items + 3), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, num_items + 3), (-1, num_items + 3), colors.white),
        ('FONTNAME', (0, num_items + 3), (-1, num_items + 3), 'Helvetica-Bold'),
        ('FONTSIZE', (0, num_items + 3), (-1, num_items + 3), 10),
    ]
    t.setStyle(TableStyle(style_commands))
    elements.append(t)

    # Override note
    has_overrides = any(i.get('is_override') for i in items)
    if has_overrides:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("* Valores marcados con asterisco fueron ajustados manualmente por el ejecutivo.", footer_style))

    # Payment proof note
    if billing_instruction.get('has_payment_proof'):
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("El ejecutivo adjuntó comprobante de pago anticipado a este correo.", ParagraphStyle('Note', parent=normal_style, textColor=colors.HexColor('#27ae60'), fontName='Helvetica-Bold')))

    # Footer: executor name + timestamp
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"Procesado por: <b>{executor_name}</b>", normal_style))
    elements.append(Paragraph(f"Generado: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC')}", footer_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Este documento es de uso interno y no debe ser compartido con el cliente.", footer_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
