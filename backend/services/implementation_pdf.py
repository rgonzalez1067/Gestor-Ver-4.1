"""
Generador de PDF: Ficha Técnica de Implementación
Documento operativo para el equipo de operaciones/implementación.
Se genera al accionar "Enviar a Implementación".
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
import io
from datetime import datetime

from services.rif_formatter import format_rif


# Colores corporativos
COLOR_AZUL = colors.HexColor("#00447C")
COLOR_AZUL_CLARO = colors.HexColor("#E3F2FD")
COLOR_VERDE = colors.HexColor("#28A745")
COLOR_VERDE_CLARO = colors.HexColor("#E8F5E9")
COLOR_GRIS = colors.HexColor("#F5F5F5")
COLOR_AMARILLO = colors.HexColor("#FBBF24")
COLOR_TEXTO = colors.HexColor("#333333")
COLOR_BORDE = colors.HexColor("#E0E0E0")

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='DocTitle', fontName='Helvetica-Bold', fontSize=22,
        textColor=COLOR_AZUL, alignment=1, spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader', fontName='Helvetica-Bold', fontSize=13,
        textColor=colors.white, spaceBefore=14, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='BlockLabel', fontName='Helvetica-Bold', fontSize=10,
        textColor=COLOR_AZUL, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name='NormalText', fontName='Helvetica', fontSize=10,
        textColor=COLOR_TEXTO, leading=14, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name='SmallText', fontName='Helvetica', fontSize=9,
        textColor=COLOR_TEXTO, leading=12
    ))
    styles.add(ParagraphStyle(
        name='SmallWhite', fontName='Helvetica-Bold', fontSize=9,
        textColor=colors.white, leading=12
    ))
    styles.add(ParagraphStyle(
        name='FooterText', fontName='Helvetica', fontSize=8,
        textColor=colors.HexColor("#888888"), alignment=1
    ))
    return styles


def _section_banner(title, styles):
    """Crea un banner de sección azul con texto blanco"""
    t = Table([[Paragraph(title, styles['SectionHeader'])]], colWidths=[480])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_AZUL),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    return t


def _key_value_table(pairs, styles):
    """Tabla de pares clave-valor"""
    data = []
    for label, value in pairs:
        data.append([
            Paragraph(f"<b>{label}:</b>", styles['NormalText']),
            Paragraph(str(value or 'N/A'), styles['NormalText'])
        ])
    t = Table(data, colWidths=[180, 300])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (0, -1), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('BACKGROUND', (0, 0), (0, -1), COLOR_GRIS),
    ]))
    return t


def generate_implementation_pdf(quote: dict, client: dict, contacts: list, branches: list, logo_path: str = None) -> bytes:
    buf = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=50, rightMargin=50,
        topMargin=60, bottomMargin=50
    )

    elements = []
    now = datetime.now()
    fecha = f"{now.day} de {MESES_ES[now.month]} de {now.year}"
    quote_number = quote.get('quote_number', 'S/N')
    client_name = client.get('legal_name') or client.get('fantasy_name') or 'N/A'
    cantidad_cajas = quote.get('cantidad_cajas', 1)

    # ==================== 1. ENCABEZADO: Cotización y Fecha ====================
    elements.append(Paragraph("FICHA TECNICA DE IMPLEMENTACION", styles['DocTitle']))
    elements.append(Spacer(1, 4))

    meta_data = [[
        Paragraph(f"<b>Cotizacion:</b> {quote_number}", styles['NormalText']),
        Paragraph(f"<b>Fecha:</b> {fecha}", styles['NormalText']),
    ]]
    meta_t = Table(meta_data, colWidths=[280, 200])
    meta_t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_AZUL_CLARO),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
    ]))
    elements.append(meta_t)
    elements.append(Spacer(1, 16))

    # ==================== 2. IDENTIFICACIÓN DEL PROYECTO ====================
    elements.append(_section_banner("A. IDENTIFICACION DEL PROYECTO", styles))
    elements.append(Spacer(1, 6))

    quote_type = quote.get('quote_type', 'N/A')
    tipo_display = (
        'VPOS / MPOS' if quote_type in ('VPOS_MPOS', 'VPOS')
        else 'Payment Gateway' if quote_type == 'GATEWAY'
        else 'Link de Pago' if quote_type == 'LINK_PAGO'
        else 'MPOS (Imple + POS)' if quote_type == 'FAST_TRACK'
        else quote_type
    )

    economic_group = quote.get('economic_group') or 'Sin Grupo Económico'
    fantasy_name = quote.get('fantasy_name') or client.get('fantasy_name') or client_name

    elements.append(_key_value_table([
        ("Tipo de Proyecto", tipo_display),
        ("Grupo Económico", economic_group),
        ("Nombre del Comercio", client_name),
        ("RIF", format_rif(client.get('rif', 'N/A')) or 'N/A'),
        ("Nombre de Fantasía", fantasy_name),
    ], styles))
    elements.append(Spacer(1, 14))

    # ==================== 3. CONFIGURACIÓN TÉCNICA (incluye servidor) ====================
    elements.append(_section_banner("B. CONFIGURACION TECNICA (Hardware & Software)", styles))
    elements.append(Spacer(1, 6))

    tech_pairs = [
        ("Nombre del Integrador", quote.get('integrator_name', 'N/A')),
        ("Nombre del Aplicativo", quote.get('integrator_app_name', 'N/A')),
        ("Modelo de Pinpad", quote.get('pinpad_model', 'N/A')),
        ("Patrocinador de Pinpads", quote.get('sponsor_bank_name', 'N/A')),
    ]
    server_name = quote.get("server_name") or ""
    if server_name:
        tech_pairs.append(("Servidor de Instalacion", server_name))
    communication_type = quote.get("communication_type") or ""
    if communication_type:
        tech_pairs.append(("Tipo de Comunicacion", communication_type))

    elements.append(_key_value_table(tech_pairs, styles))
    elements.append(Spacer(1, 14))

    # ==================== 4. MODELO Y SERIALES DE EQUIPOS ====================
    pinpad_serials = quote.get("pinpad_serials") or []
    equipments = quote.get("equipments") or []
    all_serials = pinpad_serials + equipments
    if all_serials:
        elements.append(_section_banner("C. SERIALES DE LOS EQUIPOS", styles))
        elements.append(Spacer(1, 6))
        eq_data = [
            [Paragraph("<b>Modelo</b>", styles['SmallWhite']),
             Paragraph("<b>Serial</b>", styles['SmallWhite']),
             Paragraph("<b>Origen</b>", styles['SmallWhite'])],
        ]
        for eq in all_serials:
            source_label = "Inventario" if eq in pinpad_serials else "Taller/Entrega"
            eq_data.append([
                Paragraph(str(eq.get("modelo", "N/A")), styles['SmallText']),
                Paragraph(str(eq.get("serial", "N/A")), styles['SmallText']),
                Paragraph(source_label, styles['SmallText']),
            ])
        eq_table = Table(eq_data, colWidths=[180, 180, 120])
        eq_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        for i in range(1, len(eq_data)):
            if i % 2 == 0:
                eq_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS))
        eq_table.setStyle(TableStyle(eq_style))
        elements.append(eq_table)
        elements.append(Spacer(1, 14))

    # ==================== C.1 MODELO DE IMPRESORA FISCAL ====================
    # Bloque ubicado justo detrás de "Seriales de los Equipos" (Feb 2026):
    # imprime el modelo de impresora fiscal capturado en el wizard al
    # enviar a implementación, o tomado de la ficha del cliente.
    fiscal_printer_model = (quote.get("fiscal_printer_model") or client.get("modelo_impresora_fiscal") or "").strip()
    if fiscal_printer_model:
        elements.append(Paragraph("<b>Modelo de Impresora Fiscal</b>", styles['BlockLabel']))
        elements.append(Spacer(1, 4))
        fp_table = Table(
            [[Paragraph(fiscal_printer_model, styles['SmallText'])]],
            colWidths=[480],
        )
        fp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_GRIS),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(fp_table)
        elements.append(Spacer(1, 14))

    # ==================== 5. RESUMEN COMERCIAL ====================
    section_letter = "D" if all_serials else "C"
    elements.append(_section_banner(f"{section_letter}. RESUMEN COMERCIAL", styles))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("Resumen Ejecutivo", styles['BlockLabel']))
    elements.append(Spacer(1, 4))

    direccion = client.get('address', 'No especificada')
    summary_row1 = [
        [Paragraph("<b>Cliente</b>", styles['SmallText']),
         Paragraph(str(client_name), styles['SmallText']),
         Paragraph("<b>Cant. Cajas</b>", styles['SmallText']),
         Paragraph(str(cantidad_cajas), styles['SmallText'])]
    ]
    t1 = Table(summary_row1, colWidths=[80, 200, 90, 110])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COLOR_AMARILLO),
        ('BACKGROUND', (2, 0), (2, 0), COLOR_AZUL_CLARO),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t1)

    dir_row = [[Paragraph("<b>Dir. Fiscal</b>", styles['SmallText']),
                Paragraph(str(direccion), styles['SmallText'])]]
    t_dir = Table(dir_row, colWidths=[80, 400])
    t_dir.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_CLARO),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_dir)
    elements.append(Spacer(1, 6))

    # Tabla Bancos / Productos
    # Para cotizaciones Payment Gateway (quote_type='GATEWAY' o quote_category='implementation'
    # con pg_setup_items presentes), usamos pg_setup_items con columnas
    # N° / Concepto / Banco / Observación + fila TOTAL SETUP.
    quote_type_upper = (quote.get('quote_type') or '').upper()
    pg_setup_items = quote.get('pg_setup_items') or []
    is_payment_gateway = quote_type_upper in ('GATEWAY', 'LINK_PAGO') or (pg_setup_items and quote_type_upper != 'VPOS' and quote_type_upper != 'MPOS')

    if is_payment_gateway and pg_setup_items:
        pg_header = [
            Paragraph("<b>N°</b>", styles['SmallWhite']),
            Paragraph("<b>Concepto</b>", styles['SmallWhite']),
            Paragraph("<b>Banco</b>", styles['SmallWhite']),
            Paragraph("<b>Observación</b>", styles['SmallWhite']),
        ]
        pg_data = [pg_header]
        for idx, item in enumerate(pg_setup_items, 1):
            concepto = str(item.get('concepto') or item.get('item_name') or 'N/A')
            banco = str(item.get('banco') or 'N/A')
            observacion = str(item.get('observacion') or '')
            pg_data.append([
                Paragraph(str(idx), styles['SmallText']),
                Paragraph(concepto, styles['SmallText']),
                Paragraph(banco, styles['SmallText']),
                Paragraph(observacion, styles['SmallText']),
            ])

        pg_table = Table(pg_data, colWidths=[35, 200, 145, 100])
        pg_style = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ]
        # Filas alternas grises
        for i in range(1, len(pg_data)):
            if i % 2 == 0:
                pg_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS))
        pg_table.setStyle(TableStyle(pg_style))
        elements.append(pg_table)
    else:
        all_services = quote.get('services', [])
        additional_items = [s for s in all_services if s.get('item_type') == 'additional']
        if additional_items:
            bank_header = [
                Paragraph("<b>Banco</b>", styles['SmallWhite']),
                Paragraph("<b>Medio de Pago</b>", styles['SmallWhite']),
                Paragraph("<b>Cajas</b>", styles['SmallWhite']),
            ]
            bank_data = [bank_header]
            for item in additional_items:
                bank_data.append([
                    Paragraph(str(item.get('bank_name', 'N/A')), styles['SmallText']),
                    Paragraph(str(item.get('item_name', item.get('name', 'N/A'))), styles['SmallText']),
                    Paragraph(str(item.get('quantity', cantidad_cajas)), styles['SmallText']),
                ])
            bank_table = Table(bank_data, colWidths=[160, 230, 90])
            bank_style = [
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_AZUL),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]
            for i in range(1, len(bank_data)):
                if i % 2 == 0:
                    bank_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS))
            bank_table.setStyle(TableStyle(bank_style))
            elements.append(bank_table)

    elements.append(Spacer(1, 14))

    # ==================== 6. DISTRIBUCIÓN LOGÍSTICA ====================
    next_letter = chr(ord(section_letter) + 1)
    elements.append(_section_banner(f"{next_letter}. DISTRIBUCION LOGISTICA (Sucursales)", styles))
    elements.append(Spacer(1, 6))

    branch_header = [
        Paragraph("<b>#</b>", styles['SmallWhite']),
        Paragraph("<b>Nombre de Sucursal</b>", styles['SmallWhite']),
        Paragraph("<b>Cant. Cajas</b>", styles['SmallWhite']),
    ]
    branch_data = [branch_header]

    if branches and len(branches) > 0:
        for idx, b in enumerate(branches, 1):
            branch_data.append([
                Paragraph(str(idx), styles['SmallText']),
                Paragraph(str(b.get('store_name', f'Sucursal {idx}')), styles['SmallText']),
                Paragraph(str(b.get('quantity', 0)), styles['SmallText']),
            ])
    else:
        branch_data.append([
            Paragraph("1", styles['SmallText']),
            Paragraph("Sucursal Unica", styles['SmallText']),
            Paragraph(str(cantidad_cajas), styles['SmallText']),
        ])

    total_cajas = sum(b.get('quantity', 0) for b in branches) if branches else cantidad_cajas
    branch_data.append([
        Paragraph("", styles['SmallText']),
        Paragraph("<b>TOTAL</b>", styles['SmallText']),
        Paragraph(f"<b>{total_cajas}</b>", styles['SmallText']),
    ])

    branch_table = Table(branch_data, colWidths=[40, 330, 110])
    branch_style = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_AZUL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), COLOR_AZUL_CLARO),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]
    for i in range(1, len(branch_data) - 1):
        if i % 2 == 0:
            branch_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS))
    branch_table.setStyle(TableStyle(branch_style))
    elements.append(branch_table)
    elements.append(Spacer(1, 14))

    # ==================== 7. DIRECTORIO DE CONTACTOS ====================
    next_letter2 = chr(ord(next_letter) + 1)
    elements.append(_section_banner(f"{next_letter2}. DIRECTORIO DE CONTACTOS", styles))
    elements.append(Spacer(1, 6))

    contact_header = [
        Paragraph("<b>Nombre</b>", styles['SmallWhite']),
        Paragraph("<b>Cargo / Rol</b>", styles['SmallWhite']),
        Paragraph("<b>Telefono</b>", styles['SmallWhite']),
        Paragraph("<b>Email</b>", styles['SmallWhite']),
    ]
    contact_data = [contact_header]

    if contacts:
        for c in contacts:
            name = c.get('full_name') or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or 'N/A'
            contact_data.append([
                Paragraph(str(name), styles['SmallText']),
                Paragraph(str(c.get('role', c.get('position', 'N/A'))), styles['SmallText']),
                Paragraph(str(c.get('phone', 'N/A')), styles['SmallText']),
                Paragraph(str(c.get('email', 'N/A')), styles['SmallText']),
            ])
    else:
        contact_data.append([
            Paragraph("Sin contactos registrados", styles['SmallText']),
            Paragraph("-", styles['SmallText']),
            Paragraph("-", styles['SmallText']),
            Paragraph("-", styles['SmallText']),
        ])

    contact_table = Table(contact_data, colWidths=[130, 110, 110, 130])
    contact_style = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_AZUL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, COLOR_BORDE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i in range(1, len(contact_data)):
        if i % 2 == 0:
            contact_style.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS))
    contact_table.setStyle(TableStyle(contact_style))
    elements.append(contact_table)

    # ==================== 7.5 INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR ====================
    instructions_html = (quote or {}).get("implementation_instructions") or ""
    if instructions_html and instructions_html.strip():
        elements.append(Spacer(1, 18))
        elements.append(_section_banner("INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR", styles))
        elements.append(Spacer(1, 6))
        # ReportLab Paragraph admite un subset de HTML (<b>, <i>, <u>, <br/>, <br>).
        # Convertimos tags comunes del editor a los admitidos; los desconocidos se eliminan.
        import re as _re
        safe = instructions_html
        # <strong>→<b>, <em>→<i>
        safe = _re.sub(r"</?(strong)>", lambda m: "</b>" if m.group(0).startswith("</") else "<b>", safe, flags=_re.I)
        safe = _re.sub(r"</?(em)>", lambda m: "</i>" if m.group(0).startswith("</") else "<i>", safe, flags=_re.I)
        # <p>…</p> → contenido + <br/>
        safe = _re.sub(r"<p[^>]*>", "", safe, flags=_re.I)
        safe = _re.sub(r"</p>", "<br/>", safe, flags=_re.I)
        # <li>…</li> → • contenido + <br/>
        safe = _re.sub(r"<li[^>]*>", "&bull; ", safe, flags=_re.I)
        safe = _re.sub(r"</li>", "<br/>", safe, flags=_re.I)
        # Quitar <ul>/<ol>
        safe = _re.sub(r"</?(ul|ol)[^>]*>", "", safe, flags=_re.I)
        # Remover tags desconocidos excepto b, i, u, br
        safe = _re.sub(r"<(?!/?(?:b|i|u|br)(?:\s|/?>))[^>]+>", "", safe, flags=_re.I)
        instr_box = Table(
            [[Paragraph(safe, styles['NormalText'])]],
            colWidths=[480],
        )
        instr_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFBEB')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#F59E0B')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#FEF3C7')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(instr_box)

    # ==================== 8. PIE DE DOCUMENTO ====================
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        f"Documento generado automaticamente el {fecha} | Ref: {quote_number}",
        styles['FooterText']
    ))
    elements.append(Paragraph(
        "Este documento es de uso interno y exclusivo del equipo de operaciones.",
        styles['FooterText']
    ))

    doc.build(elements)
    return buf.getvalue()
