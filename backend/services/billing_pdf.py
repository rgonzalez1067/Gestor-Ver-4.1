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
from services.rif_formatter import format_rif


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

    # Datos para la Factura — campos requeridos por Administración
    elements.append(Paragraph("Datos para la Factura", header_style))
    legal_name = client.get('legal_name') or client.get('fantasy_name') or 'N/A'
    address = (client.get('address') or '').strip() or 'No especificada'
    contacts = client.get('contacts') or []
    primary_contact = contacts[0] if contacts else (client.get('contact1') or {})
    if isinstance(primary_contact, dict):
        contact_name = (
            primary_contact.get('full_name')
            or primary_contact.get('name')
            or f"{primary_contact.get('first_name', '')} {primary_contact.get('last_name', '')}".strip()
            or 'No especificado'
        )
        contact_phone = primary_contact.get('phone') or primary_contact.get('telefono') or 'No especificado'
        contact_email = primary_contact.get('email') or 'No especificado'
    else:
        contact_name = contact_phone = contact_email = 'No especificado'
    quote_number = quote.get('quote_number') or 'N/A'
    approval_date = datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')

    info_data = [
        [Paragraph('<b>RIF:</b>', cell_bold_style), Paragraph(format_rif(client.get('rif')) or 'N/A', cell_style)],
        [Paragraph('<b>Razón Social:</b>', cell_bold_style), Paragraph(legal_name, cell_style)],
        [Paragraph('<b>Dirección Fiscal:</b>', cell_bold_style), Paragraph(address, cell_style)],
        [Paragraph('<b>Nombre Contacto:</b>', cell_bold_style), Paragraph(contact_name, cell_style)],
        [Paragraph('<b>Teléfono:</b>', cell_bold_style), Paragraph(contact_phone, cell_style)],
        [Paragraph('<b>Email:</b>', cell_bold_style), Paragraph(contact_email, cell_style)],
        [Paragraph('<b>Nro. Cotización:</b>', cell_bold_style), Paragraph(quote_number, cell_style)],
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

    # === Matriz Financiera Consolidada (aprobación Corporativa) ===
    # Si el aprobador visó la matriz por tipo_corp, se renderiza en lugar del
    # listado ítem-por-ítem, respetando la moneda ($/Bs.) y las filas elegidas.
    _bm = billing_instruction.get('billing_matrix')
    if _bm:
        from services.corp_billing_matrix import resolve_matrix_rows, _fmt as _bm_fmt
        _currency = (_bm.get('currency') or 'USD').upper()
        _rate = float(_bm.get('exchange_rate') or 0)
        _cols = _bm.get('columns') or ["Derecho de Uso", "Infraestructura", "Apoyo Técnico", "Soporte y Monitoreo"]
        _rows, _total_by_col, _total_general = resolve_matrix_rows(_bm)
        _cur_label = "Bs." if _currency == "BS" else "USD ($)"

        elements.append(Paragraph("Instrucciones de Facturación", header_style))
        _note = f"Moneda: {_cur_label}"
        if _currency == "BS" and _rate:
            _note += f" — Tasa aplicada: Bs.{_rate:,.2f} / $"
        elements.append(Paragraph(_note, normal_style))
        elements.append(Spacer(1, 8))

        _hs = ParagraphStyle('MtxH', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName='Helvetica-Bold', alignment=1, leading=11)
        _cl = ParagraphStyle('MtxL', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#00447C'), fontName='Helvetica-Bold', leading=11)
        _cr = ParagraphStyle('MtxR', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#1e293b'), alignment=2, leading=11)
        _cwhite = ParagraphStyle('MtxW', parent=_cr, textColor=colors.white, fontName='Helvetica-Bold')

        mtx_data = [
            [Paragraph('Concepto', _hs), Paragraph('Hardware y Software', _hs), '', Paragraph('Consultoría', _hs), '', Paragraph(f'Total ({_cur_label})', _hs)],
            ['', Paragraph('Derecho de Uso', _hs), Paragraph('Infraestructura', _hs), Paragraph('Apoyo técnico', _hs), Paragraph('Soporte y Monitoreo', _hs), ''],
        ]
        for label, by_col, row_total in _rows:
            mtx_data.append([
                Paragraph(label, _cl),
                *[Paragraph(_bm_fmt(by_col.get(c, 0), _currency, _rate), _cr) for c in _cols],
                Paragraph(f"<b>{_bm_fmt(row_total, _currency, _rate)}</b>", _cr),
            ])
        mtx_data.append([
            Paragraph('TOTAL GENERAL', _cwhite),
            *[Paragraph(_bm_fmt(_total_by_col.get(c, 0), _currency, _rate), _cwhite) for c in _cols],
            Paragraph(_bm_fmt(_total_general, _currency, _rate), ParagraphStyle('MtxGT', parent=_cr, fontName='Helvetica-Bold')),
        ])
        mtx_tbl = Table(mtx_data, colWidths=[3.0*cm, 2.7*cm, 2.7*cm, 2.7*cm, 2.9*cm, 3.0*cm])
        _last = len(mtx_data) - 1
        mtx_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#336699')),
            ('SPAN', (1, 0), (2, 0)),
            ('SPAN', (3, 0), (4, 0)),
            ('SPAN', (0, 0), (0, 1)),
            ('SPAN', (5, 0), (5, 1)),
            ('BACKGROUND', (0, _last), (-1, _last), colors.HexColor('#1E293B')),
            ('BACKGROUND', (5, _last), (5, _last), colors.HexColor('#F59E0B')),
            ('TEXTCOLOR', (5, _last), (5, _last), colors.HexColor('#1E293B')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(mtx_tbl)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("Montos no incluyen IVA.", footer_style))
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # Consolidated setup items table
    items = billing_instruction.get('consolidated_items', [])
    exchange_rate = billing_instruction.get('exchange_rate', 0)
    rate_source = billing_instruction.get('rate_source', 'Manual')
    is_equipment = quote.get('quote_category') == 'equipment'
    is_repair = quote.get('quote_category') == 'repair'

    if is_equipment:
        section_title = "Equipos y Accesorios Cotizados"
    elif is_repair:
        section_title = "Items de Reparación Consolidados"
    else:
        section_title = "Conceptos de Setup y Productos Consolidados"
    elements.append(Paragraph(section_title, header_style))
    elements.append(Paragraph(f"Tasa de Cambio aplicada: <b>Bs.{exchange_rate:,.2f} / $</b> — Fuente: {rate_source}", normal_style))
    elements.append(Spacer(1, 8))

    # Header styles
    header_cell_style = ParagraphStyle('HeaderCell', parent=styles['Normal'], fontSize=9, textColor=colors.white, fontName='Helvetica-Bold', leading=11)
    header_center = ParagraphStyle('HeaderCenter', parent=header_cell_style, alignment=1)
    header_right = ParagraphStyle('HeaderRight', parent=header_cell_style, alignment=2)

    if is_equipment:
        concept_label = 'Equipo / Accesorio'
    elif is_repair:
        concept_label = 'Concepto / Servicio'
    else:
        concept_label = 'Concepto'

    cell_bold_right = ParagraphStyle('CellBoldRight', parent=cell_right_style, fontName='Helvetica-Bold')
    total_white_style = ParagraphStyle('TotalWhite', parent=cell_style, textColor=colors.white, fontName='Helvetica-Bold', fontSize=10, alignment=2)
    total_white_left = ParagraphStyle('TotalWhiteLeft', parent=total_white_style, alignment=0)
    col_widths = [4.8*cm, 1.3*cm, 2.5*cm, 2.2*cm, 3.2*cm, 3.5*cm]

    def _build_invoice_table(block_items: list, subtotal_label: str) -> Table:
        """Construye una mini-factura: header + rows + Subtotal + IVA + TOTAL.
        Cada bloque tiene su propio IVA y TOTAL. No depende del agregado global.
        """
        td = [[
            Paragraph(concept_label, header_cell_style),
            Paragraph('Cant.', header_center),
            Paragraph('Monto ($)', header_right),
            Paragraph('Tasa Bs./$', header_center),
            Paragraph('C.U. Bs.', header_right),
            Paragraph('Total (Bs.)', header_right),
        ]]
        sub_usd = 0.0
        sub_bs = 0.0
        for item in block_items:
            usd_val = float(item.get('total_usd', 0) or 0)
            bs_val = float(item.get('total_bs', usd_val * exchange_rate) or 0)
            qty = item.get('quantity', 1) or 1
            cu_bs = bs_val / qty if qty > 0 else 0
            td.append([
                Paragraph(item.get('name', 'N/A'), cell_style),
                Paragraph(str(qty), cell_center_style),
                Paragraph(f"${usd_val:,.2f}", cell_right_style),
                Paragraph(f"{exchange_rate:,.2f}", cell_center_style),
                Paragraph(f"<nobr>Bs.{cu_bs:,.2f}</nobr>", cell_right_style),
                Paragraph(f"<nobr>Bs.{bs_val:,.2f}</nobr>", cell_right_style),
            ])
            sub_usd += usd_val
            sub_bs += bs_val
        n_rows = len(td) - 1  # excluyendo header

        iva_usd_b = sub_usd * 0.16
        iva_bs_b = sub_bs * 0.16
        total_usd_b = sub_usd + iva_usd_b
        total_bs_b = sub_bs + iva_bs_b
        td.append([
            Paragraph(f'<b>{subtotal_label}</b>', cell_bold_style), '',
            Paragraph(f"<b>${sub_usd:,.2f}</b>", cell_bold_right), '', '',
            Paragraph(f"<nobr><b>Bs.{sub_bs:,.2f}</b></nobr>", cell_bold_right),
        ])
        td.append([
            Paragraph('IVA (16%)', cell_style), '',
            Paragraph(f"${iva_usd_b:,.2f}", cell_right_style), '', '',
            Paragraph(f"<nobr>Bs.{iva_bs_b:,.2f}</nobr>", cell_right_style),
        ])
        td.append([
            Paragraph('<b>TOTAL</b>', total_white_left), '',
            Paragraph(f"<nobr><b>${total_usd_b:,.2f}</b></nobr>", total_white_style), '', '',
            Paragraph(f"<nobr><b>Bs.{total_bs_b:,.2f}</b></nobr>", total_white_style),
        ])

        tbl = Table(td, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('ROWBACKGROUNDS', (0, 1), (-1, n_rows), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, n_rows + 1), (-1, n_rows + 1), colors.HexColor('#f0f0f0')),
            ('BACKGROUND', (0, n_rows + 2), (-1, n_rows + 2), colors.HexColor('#f0f0f0')),
            ('BACKGROUND', (0, n_rows + 3), (-1, n_rows + 3), colors.HexColor('#2c3e50')),
        ]))
        return tbl

    has_sections = any((it.get('section') for it in items))

    if has_sections:
        # Cotización MIXTA (típico Fast Track / MPOS Imple+POS): renderizamos
        # UNA mini-factura independiente por sección (Implementación, Pinpads,
        # ...). Cada bloque tiene su propio Subtotal/IVA/TOTAL, sin mezclar
        # los costos. NO se emite un total combinado.
        order: list[str] = []
        bucket: dict[str, list] = {}
        for it in items:
            sec = it.get('section') or 'Otros'
            if sec not in bucket:
                bucket[sec] = []
                order.append(sec)
            bucket[sec].append(it)

        section_subtitle_style = ParagraphStyle(
            'SectionSubtitle', parent=header_style, fontSize=12,
            textColor=colors.HexColor('#1f3a5f'), spaceBefore=10, spaceAfter=4,
        )
        for idx, sec_name in enumerate(order):
            elements.append(Paragraph(f"<b>Factura {idx + 1}: {sec_name}</b>", section_subtitle_style))
            elements.append(_build_invoice_table(bucket[sec_name], f"SUBTOTAL {sec_name.upper()}"))
            elements.append(Spacer(1, 14))

        elements.append(Paragraph(
            "<i>Nota: cada sección se factura por separado. Los totales mostrados arriba "
            "son independientes y NO deben combinarse en una sola factura.</i>",
            ParagraphStyle('NoteSep', parent=normal_style, textColor=colors.HexColor('#7f8c8d'), fontSize=8),
        ))
    else:
        # Comportamiento legacy: una sola tabla con Subtotal/IVA/Total.
        # Usamos los valores ya calculados por el frontend para mantener
        # paridad con la vista previa del modal.
        subtotal_label = 'SUBTOTAL (Equipos)' if is_equipment else 'SUBTOTAL'
        td = [[
            Paragraph(concept_label, header_cell_style),
            Paragraph('Cant.', header_center),
            Paragraph('Monto ($)', header_right),
            Paragraph('Tasa Bs./$', header_center),
            Paragraph('C.U. Bs.', header_right),
            Paragraph('Total (Bs.)', header_right),
        ]]
        for item in items:
            usd_val = float(item.get('total_usd', 0) or 0)
            bs_val = float(item.get('total_bs', usd_val * exchange_rate) or 0)
            qty = item.get('quantity', 1) or 1
            cu_bs = bs_val / qty if qty > 0 else 0
            td.append([
                Paragraph(item.get('name', 'N/A'), cell_style),
                Paragraph(str(qty), cell_center_style),
                Paragraph(f"${usd_val:,.2f}", cell_right_style),
                Paragraph(f"{exchange_rate:,.2f}", cell_center_style),
                Paragraph(f"<nobr>Bs.{cu_bs:,.2f}</nobr>", cell_right_style),
                Paragraph(f"<nobr>Bs.{bs_val:,.2f}</nobr>", cell_right_style),
            ])
        n_rows = len(td) - 1
        sub_usd_g = billing_instruction.get('grand_total_usd', 0)
        sub_bs_g = billing_instruction.get('grand_total_bs', 0)
        iva_usd_g = billing_instruction.get('iva_usd', sub_usd_g * 0.16)
        iva_bs_g = billing_instruction.get('iva_bs', sub_bs_g * 0.16)
        total_usd_g = billing_instruction.get('grand_total_con_iva_usd', sub_usd_g + iva_usd_g)
        total_bs_g = billing_instruction.get('grand_total_con_iva_bs', sub_bs_g + iva_bs_g)
        td.append([
            Paragraph(f'<b>{subtotal_label}</b>', cell_bold_style), '',
            Paragraph(f"<b>${sub_usd_g:,.2f}</b>", cell_bold_right), '', '',
            Paragraph(f"<nobr><b>Bs.{sub_bs_g:,.2f}</b></nobr>", cell_bold_right),
        ])
        td.append([
            Paragraph('IVA (16%)', cell_style), '',
            Paragraph(f"${iva_usd_g:,.2f}", cell_right_style), '', '',
            Paragraph(f"<nobr>Bs.{iva_bs_g:,.2f}</nobr>", cell_right_style),
        ])
        td.append([
            Paragraph('<b>TOTAL GENERAL</b>', total_white_left), '',
            Paragraph(f"<nobr><b>${total_usd_g:,.2f}</b></nobr>", total_white_style), '', '',
            Paragraph(f"<nobr><b>Bs.{total_bs_g:,.2f}</b></nobr>", total_white_style),
        ])
        t = Table(td, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('ROWBACKGROUNDS', (0, 1), (-1, n_rows), [colors.white, colors.HexColor('#f8f9fa')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, n_rows + 1), (-1, n_rows + 1), colors.HexColor('#f0f0f0')),
            ('BACKGROUND', (0, n_rows + 2), (-1, n_rows + 2), colors.HexColor('#f0f0f0')),
            ('BACKGROUND', (0, n_rows + 3), (-1, n_rows + 3), colors.HexColor('#2c3e50')),
        ]))
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
