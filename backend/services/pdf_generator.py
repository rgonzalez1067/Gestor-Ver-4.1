"""
Generador de PDFs dinámico para cotizaciones VPOS y Payment Gateway.
"""
from pydantic import BaseModel
from typing import List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Frame, PageTemplate, BaseDocTemplate, PageBreak
from reportlab.lib.units import inch, cm, mm
from reportlab.pdfgen import canvas as canvas_module
import io
import os
import logging
from datetime import datetime, timedelta

from models import QuotePDFItem

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas_module.Canvas):
    """Canvas estándar — solo para compatibilidad de import."""
    pass

class TemplateQuotePDFRequest(BaseModel):
    """Modelo para generar PDF usando plantilla configurada"""
    template_type: str = "vpos_pyme"  # Tipo de plantilla a usar
    # Datos del cliente (campos amarillos Página 1 y 2)
    cliente_nombre: str
    cliente_rif: str = ""
    cliente_contacto: str = ""  # Persona de contacto
    cliente_address: str = ""
    # Datos de la solicitud (campos amarillos)
    integrator_name: str = ""
    integrator_app_name: str = ""  # Nombre del Aplicativo de Caja
    pinpad_model: str = ""
    sponsor_bank_name: str = ""  # Patrocinador
    cantidad_cajas: int = 1
    # Número de cotización
    quote_number: str = ""
    # Items de cotización
    setup_items: List[QuotePDFItem] = []
    recurring_basic_items: List[QuotePDFItem] = []
    recurring_other_items: List[QuotePDFItem] = []
    additional_items: List[QuotePDFItem] = []  # Items de sesión setup (medios de pago con banco)
    production_items: List[QuotePDFItem] = []  # Items de cliente en producción
    pg_setup_items: List[dict] = []  # Items de setup PG: {concepto, costo, banco, observacion}
    pg_recurring_cost: Optional[dict] = None  # {rangos: [{rango_label, costo_base_total, precio_tope}], num_products: int}
    include_recurring: bool = True  # Si False, omite la sección de costos recurrentes del PDF
    descuento: float = 0
    descuento_setup: float = 0
    descuento_recurrente: float = 0
    notes: str = ""
    pricing_model: str = "conventional"
    quote_type: str = "VPOS_MPOS"
    is_production_client: bool = False
    # Fast Track: items de equipos para el PDF híbrido
    ft_equipment_items: List[dict] = []  # [{name, hardware_type, quantity, unit_price_usd}]
    # Detalle de sucursales
    branch_details: List[dict] = []  # [{store_name, quantity}]
    # Segmento del cliente para determinar el tipo de PDF
    client_segment: str = "PYME"  # "PYME" o "CORP"
    # Cliente exento de IVA — suprime impuesto en cálculos del PDF y herencia a facturación
    iva_exempt: bool = False
    # ====== IDs para hidratación server-side (aislamiento de RBAC) ======
    # El backend resuelve los nombres autoritativos desde Mongo usando estos IDs,
    # garantizando que Previsualizar/Exportar/Guardar produzcan el MISMO documento
    # sin depender de los catálogos que el frontend (limitado por permisos) tenga cargados.
    client_id: Optional[str] = None
    integrator_id: Optional[str] = None
    pinpad_id: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_processor_id: Optional[str] = None


# ==================== CLASE PARA PDF CON FLUJO DINÁMICO ====================

class DynamicQuotePDFGenerator:
    """Generador de PDF con flujo dinámico y salto de página automático"""
    
    # Colores corporativos
    COLOR_AZUL = colors.HexColor("#00447C")
    COLOR_AZUL_OSCURO = colors.HexColor("#1E3A5F")  # Dark blue for equipment table header
    COLOR_VERDE = colors.HexColor("#28A745") 
    COLOR_VERDE_CLARO = colors.HexColor("#E8F5E9")
    COLOR_AZUL_CLARO = colors.HexColor("#E3F2FD")
    COLOR_GRIS = colors.HexColor("#F5F5F5")
    COLOR_TEXTO = colors.HexColor("#333333")
    
    def __init__(self, data: TemplateQuotePDFRequest, logo_path: Optional[str] = None):
        self.data = data
        # Normalización fiscal: RIF a 9 dígitos con padding de ceros para
        # TODOS los PDFs (portada, resumen ejecutivo, totales). Feb 2026.
        try:
            from services.rif_formatter import format_rif
            if self.data.cliente_rif:
                self.data.cliente_rif = format_rif(self.data.cliente_rif)
        except Exception:
            # Si la utilidad falla por algún motivo, dejamos el RIF como vino.
            pass
        self.logo_path = logo_path
        self.buffer = io.BytesIO()
        self.page_width, self.page_height = letter
        self.margin = 50
        self.styles = self._create_styles()
        
    def _create_styles(self):
        """Crear estilos personalizados para el documento"""
        styles = getSampleStyleSheet()
        
        # Título principal
        styles.add(ParagraphStyle(
            name='TituloPortada',
            fontName='Helvetica-Bold',
            fontSize=28,
            textColor=self.COLOR_AZUL,
            alignment=1,  # Centro
            spaceAfter=15
        ))
        
        # Subtítulo (más grande pero menor que el título)
        styles.add(ParagraphStyle(
            name='Subtitulo',
            fontName='Helvetica-Bold',
            fontSize=18,  # Aumentado de 14 a 18
            textColor=self.COLOR_AZUL,
            alignment=1,
            spaceAfter=10
        ))
        
        # Encabezado de sección
        styles.add(ParagraphStyle(
            name='SeccionHeader',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=self.COLOR_AZUL,
            spaceBefore=15,
            spaceAfter=8
        ))
        
        # Texto normal
        styles.add(ParagraphStyle(
            name='TextoNormal',
            fontName='Helvetica',
            fontSize=10,
            textColor=self.COLOR_TEXTO,
            leading=14,
            spaceAfter=6
        ))
        
        # Campo etiqueta
        styles.add(ParagraphStyle(
            name='CampoEtiqueta',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=self.COLOR_AZUL
        ))
        
        # Campo valor
        styles.add(ParagraphStyle(
            name='CampoValor',
            fontName='Helvetica',
            fontSize=10,
            textColor=self.COLOR_TEXTO
        ))
        
        # Pie de página
        styles.add(ParagraphStyle(
            name='PiePagina',
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.gray,
            alignment=1
        ))
        
        return styles
    
    def _build_modern_cover(self, subtitle: str, info_pairs: list, fecha_actual: str, eyebrow: str = "PROPUESTA COMERCIAL"):
        """Construye la portada moderna y profesional (página 1).

        Diseño:
        - Hero card en azul corporativo con eyebrow + título + subtítulo.
        - Línea de acento dorada.
        - Bloque "Preparado para" con datos clave del cliente y proyecto en
          tabla zebra (filas pares grises) y columnas etiquetada / valor.
        - Tarjeta inferior con # Cotización y Fecha destacados.
        - Sello "Documento confidencial" sutil al pie del bloque.
        Mantiene EXACTAMENTE los mismos datos previos — solo cambia el diseño.

        Args:
            subtitle: línea bajo el título (ej. "Merchant Server - Plataforma de Pagos").
            info_pairs: [(label, value), ...] — sin filtros, se renderiza tal cual.
            fecha_actual: fecha legible en español.
            eyebrow: tagline en mayúsculas pequeñas (default "PROPUESTA COMERCIAL").
        """
        elements = []
        usable_w = self.page_width - 2 * self.margin
        cover_accent = colors.HexColor("#D4A017")  # dorado MegaNexus

        # 1) Espaciado superior tras el encabezado del logo
        elements.append(Spacer(1, 30))

        # 2) Hero card (bloque azul oscuro con título centrado en blanco)
        eyebrow_style = ParagraphStyle(
            'CoverEyebrow', fontName='Helvetica-Bold', fontSize=10,
            textColor=colors.HexColor("#A8C5E0"), alignment=1,
            spaceAfter=8, letterSpacing=3,
        )
        hero_title_style = ParagraphStyle(
            'CoverHeroTitle', fontName='Helvetica-Bold', fontSize=30,
            textColor=colors.white, alignment=1, leading=34, spaceAfter=6,
        )
        hero_sub_style = ParagraphStyle(
            'CoverHeroSub', fontName='Helvetica', fontSize=13,
            textColor=colors.HexColor("#E8F0F8"), alignment=1, leading=16,
        )
        hero_inner = [
            [Paragraph(eyebrow, eyebrow_style)],
            [Paragraph("COTIZACIÓN DE SERVICIOS", hero_title_style)],
            [Paragraph(subtitle, hero_sub_style)],
        ]
        hero_tbl = Table(hero_inner, colWidths=[usable_w])
        hero_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.COLOR_AZUL),
            ('TOPPADDING', (0, 0), (-1, 0), 22),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 0),
            ('TOPPADDING', (0, 1), (-1, 1), 2),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 2),
            ('TOPPADDING', (0, 2), (-1, 2), 0),
            ('BOTTOMPADDING', (0, 2), (-1, 2), 26),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 30),
            ('RIGHTPADDING', (0, 0), (-1, -1), 30),
        ]))
        elements.append(hero_tbl)

        # 3) Línea de acento dorada (separador delgado)
        accent = Table([[""]], colWidths=[usable_w], rowHeights=[3])
        accent.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cover_accent),
        ]))
        elements.append(accent)

        elements.append(Spacer(1, 32))

        # 4) Encabezado de la sección de datos
        section_label_style = ParagraphStyle(
            'CoverSectionLabel', fontName='Helvetica-Bold', fontSize=11,
            textColor=self.COLOR_AZUL, leading=13, spaceAfter=10,
            letterSpacing=2,
        )
        elements.append(Paragraph("PREPARADO PARA", section_label_style))

        # 5) Tabla zebra de datos del cliente / proyecto
        label_style = ParagraphStyle(
            'CoverInfoLabel', fontName='Helvetica-Bold', fontSize=9,
            textColor=colors.HexColor("#5C6B7A"), leading=12, letterSpacing=1,
        )
        value_style = ParagraphStyle(
            'CoverInfoValue', fontName='Helvetica-Bold', fontSize=12,
            textColor=colors.HexColor("#0F2A47"), leading=15,
        )
        info_rows = []
        for label, value in info_pairs:
            info_rows.append([
                Paragraph(str(label).upper(), label_style),
                Paragraph(str(value) if value else "—", value_style),
            ])

        info_tbl = Table(info_rows, colWidths=[usable_w * 0.34, usable_w * 0.66])
        info_style = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor("#E2E8F0")),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
            ('LINEBEFORE', (0, 0), (0, -1), 3, self.COLOR_AZUL),
        ]
        # zebra: filas impares con fondo gris muy suave
        for idx in range(len(info_rows)):
            if idx % 2 == 1:
                info_style.append(
                    ('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#F8FAFC"))
                )
        info_tbl.setStyle(TableStyle(info_style))
        elements.append(info_tbl)

        elements.append(Spacer(1, 28))

        # 6) Tarjeta inferior: # Cotización + Fecha (2 columnas)
        meta_label = ParagraphStyle(
            'CoverMetaLabel', fontName='Helvetica-Bold', fontSize=9,
            textColor=colors.HexColor("#94A3B8"), leading=12, letterSpacing=2,
        )
        meta_value_big = ParagraphStyle(
            'CoverMetaValue', fontName='Helvetica-Bold', fontSize=16,
            textColor=self.COLOR_AZUL, leading=20,
        )
        meta_value_med = ParagraphStyle(
            'CoverMetaValueMed', fontName='Helvetica-Bold', fontSize=13,
            textColor=colors.HexColor("#0F2A47"), leading=16,
        )
        col_quote = [
            [Paragraph("NÚMERO DE COTIZACIÓN", meta_label)],
            [Paragraph(self.data.quote_number or "—", meta_value_big)],
        ]
        col_date = [
            [Paragraph("FECHA DE EMISIÓN", meta_label)],
            [Paragraph(fecha_actual, meta_value_med)],
        ]
        inner_quote = Table(col_quote)
        inner_quote.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ]))
        inner_date = Table(col_date)
        inner_date.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 0),
        ]))

        meta_card = Table(
            [[inner_quote, inner_date]],
            colWidths=[usable_w * 0.55, usable_w * 0.45],
        )
        meta_card.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ('LINEBEFORE', (0, 0), (0, -1), 4, cover_accent),
            ('LEFTPADDING', (0, 0), (-1, -1), 18),
            ('RIGHTPADDING', (0, 0), (-1, -1), 18),
            ('TOPPADDING', (0, 0), (-1, -1), 16),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        elements.append(meta_card)

        elements.append(Spacer(1, 18))

        # 7) Sello de confidencialidad sutil
        seal_style = ParagraphStyle(
            'CoverSeal', fontName='Helvetica-Oblique', fontSize=8,
            textColor=colors.HexColor("#94A3B8"), alignment=1, leading=11,
        )
        elements.append(Paragraph(
            "Documento confidencial • Mega Soft Computación C.A. • "
            "Esta propuesta es exclusiva para el destinatario indicado.",
            seal_style,
        ))

        elements.append(PageBreak())
        return elements

    def _header_footer(self, canvas, doc):
        """Añadir encabezado y pie de página a cada página"""
        canvas.saveState()
        
        # Encabezado - Logo
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                canvas.drawImage(self.logo_path, self.margin, self.page_height - 70, 
                               width=120, height=50, preserveAspectRatio=True)
            except Exception:
                pass
        
        # Línea de encabezado
        canvas.setStrokeColor(self.COLOR_AZUL)
        canvas.setLineWidth(2)
        canvas.line(self.margin, self.page_height - 80, 
                   self.page_width - self.margin, self.page_height - 80)
        
        # Número de cotización y fecha en encabezado (derecha)
        if self.data.quote_number:
            canvas.setFont('Helvetica-Bold', 10)
            canvas.setFillColor(self.COLOR_AZUL)
            canvas.drawRightString(self.page_width - self.margin, self.page_height - 55, 
                                  f"Cotizacion: {self.data.quote_number}")
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawRightString(self.page_width - self.margin, self.page_height - 68, 
                                  f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
        
        # Pie de página - línea separadora
        canvas.setStrokeColor(self.COLOR_GRIS)
        canvas.setLineWidth(1)
        canvas.line(self.margin, 40, self.page_width - self.margin, 40)
        
        # Pie: Nota legal (izquierda) + Número de página (derecha)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(self.margin, 25, 
                         "Documento Confidencial - Propiedad de Mega Soft Computacion C.A.")
        canvas.drawRightString(self.page_width - self.margin, 25, 
                              f"Pagina {doc.page}")
        
        canvas.restoreState()
    
    def _create_info_table(self, data_pairs, col_widths=None):
        """Crear tabla de información con etiquetas y valores"""
        if col_widths is None:
            col_widths = [150, 300]
        
        table_data = []
        for label, value in data_pairs:
            table_data.append([
                Paragraph(f"<b>{label}:</b>", self.styles['CampoEtiqueta']),
                Paragraph(str(value) if value else "—", self.styles['CampoValor'])
            ])
        
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return table
    
    def _create_items_table(self, items, title, header_color, show_tax=True, discount_pct=0):
        """Crear tabla de items de cotización con desglose fiscal.
        discount_pct: % de descuento a aplicar sobre el subtotal ANTES del IVA
        (se muestra el % y el monto descontado, restándose del total)."""
        elements = []
        
        # Título de la sección
        elements.append(Paragraph(title, self.styles['SeccionHeader']))
        
        if not items:
            elements.append(Paragraph("No hay items en esta sección.", self.styles['TextoNormal']))
            return elements, 0
        
        # Preparar datos de la tabla
        table_data = [['N°', 'Concepto', 'Cajas', 'Bancos', 'Tarifa', 'Total']]
        
        subtotal = 0
        for i, item in enumerate(items, 1):
            total_item = item.cantidad_cajas * item.cantidad_bancos * item.tarifa
            subtotal += total_item
            
            table_data.append([
                str(i),
                item.concepto[:45] + ('...' if len(item.concepto) > 45 else ''),
                str(item.cantidad_cajas),
                str(item.cantidad_bancos),
                f"${item.tarifa:.2f}",
                f"${total_item:.2f}"
            ])
        
        # Crear tabla de items
        col_widths = [25, 230, 45, 45, 65, 75]
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Estilos de la tabla
        style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            
            # Cuerpo
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # N°
            ('ALIGN', (2, 1), (5, -1), 'CENTER'),  # Números
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            
            # Bordes
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ])
        
        # Alternar colores de filas
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)
        
        table.setStyle(style)
        elements.append(table)
        
        # Tabla de totales fiscales (si show_tax es True)
        if show_tax:
            _iva_rate = 0.0 if getattr(self.data, 'iva_exempt', False) else 0.16
            _iva_label = "IVA (Exento):" if getattr(self.data, 'iva_exempt', False) else "IVA (16%):"
            disc_pct = discount_pct or 0
            # El descuento se aplica sobre el subtotal ANTES del IVA
            if disc_pct > 100:
                monto_descuento = disc_pct  # compatibilidad: valor absoluto
                disc_label_pct = ""
            else:
                monto_descuento = subtotal * (disc_pct / 100.0)
                disc_label_pct = f" ({disc_pct:g}%)"
            base_imponible = subtotal - monto_descuento
            iva = base_imponible * _iva_rate
            total_con_iva = base_imponible + iva

            has_discount = bool(disc_pct and disc_pct > 0)
            totals_data = [['Subtotal:', f"${subtotal:.2f}"]]
            if has_discount:
                totals_data.append([f"Descuento{disc_label_pct}:", f"-${monto_descuento:.2f}"])
                totals_data.append(['Subtotal Neto:', f"${base_imponible:.2f}"])
            totals_data.append([_iva_label, f"${iva:.2f}"])
            totals_data.append(['Total:', f"${total_con_iva:.2f}"])

            totals_table = Table(totals_data, colWidths=[405, 75])
            _ts = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LINEABOVE', (0, 0), (-1, 0), 1, header_color),
                ('BACKGROUND', (0, -1), (-1, -1), header_color),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ]
            if has_discount:
                # Resaltar la fila de descuento (índice 1) en verde
                _ts.append(('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor("#16A34A")))
            totals_table.setStyle(TableStyle(_ts))
            elements.append(totals_table)
        
        elements.append(Spacer(1, 10))
        
        return elements, subtotal
    
    def _create_bank_products_table(self):
        """Crear tabla de Bancos/Productos/Cajas para el resumen (estilo igual al frontend)
        IMPORTANTE: Usa SOLO additional_items (items de Sesion Setup con bank_name)"""
        elements = []
        
        # Colores para las celdas (igual que el frontend)
        COLOR_AMARILLO = colors.HexColor("#FBBF24")  # bg-amber-400
        COLOR_AZUL_CLARO = colors.HexColor("#BFDBFE")  # bg-blue-200
        COLOR_VERDE_CLARO = colors.HexColor("#BBF7D0")  # bg-green-200
        
        # ===== FILA 1: Cliente y Cantidad de Cajas en la misma fila (2 columnas) =====
        # Usar Paragraph para el nombre del cliente para que haga word-wrap en nombres largos
        cliente_nombre_style = ParagraphStyle(
            'ClienteNombreStyle', fontName='Helvetica', fontSize=9, leading=11, wordWrap='LTR'
        )
        row1_data = [[
            # Celda 1: Cliente (más ancha para nombres largos)
            Table(
                [[Paragraph("<b>Cliente</b>", self.styles['CampoEtiqueta']),
                  Paragraph(str(self.data.cliente_nombre), cliente_nombre_style)]],
                colWidths=[90, 200]
            ),
            # Celda 2: Cantidad de Cajas (más compacta)
            Table(
                [[Paragraph("<b>Cantidad de Cajas</b>", self.styles['CampoEtiqueta']), str(self.data.cantidad_cajas)]],
                colWidths=[110, 80]
            )
        ]]
        
        # Crear tabla externa para la fila 1
        row1_table = Table(row1_data, colWidths=[295, 185])
        row1_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        
        # Estilizar las subtablas internas
        cliente_table = row1_data[0][0]
        cliente_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_AMARILLO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        cajas_table = row1_data[0][1]
        cajas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_AZUL_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(row1_table)
        elements.append(Spacer(1, 5))
        
        # ===== FILA 2: Dirección Fiscal (puede ser de 2 líneas si es muy larga) =====
        direccion = self.data.cliente_address or "No especificada"
        # Si la dirección es muy larga (más de 60 caracteres), permitir que fluya en múltiples líneas
        direccion_style = ParagraphStyle(
            'DireccionStyle',
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            wordWrap='LTR'
        )
        
        direccion_data = [[
            Paragraph("<b>Dirección Fiscal</b>", self.styles['CampoEtiqueta']),
            Paragraph(direccion, direccion_style)
        ]]
        
        direccion_table = Table(direccion_data, colWidths=[100, 380])
        direccion_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(direccion_table)
        elements.append(Spacer(1, 12))
        
        # ===== TABLA DE BANCOS/PRODUCTOS/CAJAS =====
        # Usar SOLO additional_items (items de Sesion Setup con banco)
        bank_product_map = {}
        total_cajas = 0
        
        for item in self.data.additional_items:
            if item.bank_name:  # Solo items con banco asociado
                bank_name = item.bank_name
                # Usar el concepto completo como nombre del producto
                producto = item.concepto
                key = f"{bank_name}-{producto}"
                
                if key not in bank_product_map:
                    bank_product_map[key] = {
                        'bank': bank_name,
                        'product': producto,
                        'cajas': 0
                    }
                bank_product_map[key]['cajas'] += item.cantidad_cajas or 1
        
        # Calcular total de cajas
        for data in bank_product_map.values():
            total_cajas += data['cajas']
        
        # Si no hay items con banco, mostrar mensaje
        if not bank_product_map:
            elements.append(Paragraph("No hay medios de pago seleccionados", self.styles['TextoNormal']))
            elements.append(Spacer(1, 15))
            return elements
        
        # Crear tabla de Bancos/Productos/Cajas con colores de encabezado
        table_data = [['Bancos', 'Productos', 'Cantidad de Cajas']]
        
        # Estilo para celdas de productos (text wrap para evitar desbordamiento)
        producto_style = ParagraphStyle(
            'ProductoCell',
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            wordWrap='LTR'
        )
        
        for data in bank_product_map.values():
            table_data.append([data['bank'], Paragraph(data['product'], producto_style), str(data['cajas'])])
        
        table = Table(table_data, colWidths=[160, 230, 90])
        table.setStyle(TableStyle([
            # Encabezados con colores
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_CLARO),  # Bancos - verde
            ('BACKGROUND', (1, 0), (1, 0), COLOR_AZUL_CLARO),   # Productos - azul
            ('BACKGROUND', (2, 0), (2, 0), COLOR_AMARILLO),     # Cantidad - amarillo
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        # Alternar colores de filas
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)]))
        
        elements.append(table)
        
        # Total de terminales virtuales
        total_display = total_cajas if total_cajas > 0 else self.data.cantidad_cajas
        total_data = [['Total de Terminales Virtuales:', str(total_display)]]
        total_table = Table(total_data, colWidths=[390, 90])
        total_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),  # bg-slate-100
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('LINEABOVE', (0, 0), (-1, 0), 2, colors.HexColor("#94A3B8")),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def generate(self):
        """Generar el PDF completo con flujo dinámico"""
        if self.data.quote_type == 'LINK_PAGO':
            return self._generate_link_pago()
        if self.data.quote_type == 'GATEWAY':
            return self.generate_pg()
        if self.data.client_segment == 'CORP':
            return self.generate_vpos_corp()
        return self.generate_vpos()

    def _generate_link_pago(self):
        """Genera el PDF de Link de Pago: reusa el flujo de Payment Gateway,
        modifica el subtítulo de portada y posteriormente inserta el anexo
        estático "Link de Pago" como página 5 (antes de los Términos de la
        Cotización). Retorna un BytesIO compatible con append_pg_static_pages.
        """
        # 1) Marcar bandera para que generate_pg() use el subtítulo de Link de Pago
        self._link_pago_mode = True
        try:
            pg_buffer = self.generate_pg()  # BytesIO (self.buffer)
        finally:
            self._link_pago_mode = False

        # 2) Insertar el anexo en la posición 5 (índice 4)
        try:
            import os
            import io as _io
            from PyPDF2 import PdfReader, PdfWriter

            anexo_path = os.path.join(
                os.path.dirname(__file__), "..", "static", "anexos", "link_pago_anexo.pdf"
            )
            if not os.path.exists(anexo_path):
                logger.warning(f"[pdf_generator] Anexo Link de Pago no encontrado: {anexo_path}")
                return pg_buffer

            # PdfReader acepta BytesIO directamente
            pg_buffer.seek(0)
            base_reader = PdfReader(pg_buffer)
            anexo_reader = PdfReader(anexo_path)
            writer = PdfWriter()

            base_pages = list(base_reader.pages)
            # El PDF base de PG tiene 5 páginas (Portada, Resumen, Setup, Recurrentes, Términos).
            # Insertamos el anexo en la posición 5 (índice 4), desplazando Términos a la página 6.
            # Solo se inyecta la 1ra página del anexo (la 2da página suele ser una hoja en blanco
            # residual del export del documento original).
            insert_idx = 4 if len(base_pages) >= 5 else max(0, len(base_pages) - 1)
            anexo_pages_to_insert = anexo_reader.pages[:1]

            for i, p in enumerate(base_pages):
                if i == insert_idx:
                    for ap in anexo_pages_to_insert:
                        writer.add_page(ap)
                writer.add_page(p)
            # Edge case: si insert_idx >= len(base_pages), agregamos al final
            if insert_idx >= len(base_pages):
                for ap in anexo_pages_to_insert:
                    writer.add_page(ap)

            out = _io.BytesIO()
            writer.write(out)
            out.seek(0)
            return out
        except Exception as e:
            logger.error(f"[pdf_generator] Error intercalando anexo Link de Pago: {e}")
            pg_buffer.seek(0)
            return pg_buffer
    
    def generate_vpos(self):
        
        # Meses en español
        MESES_ES = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        # Crear documento con flujo automático
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=100,  # Espacio para encabezado
            bottomMargin=60  # Espacio para pie de página
        )
        
        elements = []
        
        # Fecha actual en español
        now = datetime.now()
        fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"
        
        # ==================== PÁGINA 1: PORTADA (diseño moderno) ====================
        info_portada = [
            ("Cliente", self.data.cliente_nombre),
            ("RIF", self.data.cliente_rif),
            ("Cantidad de Cajas", str(self.data.cantidad_cajas)),
            ("Integrador", self.data.integrator_name),
            ("Aplicativo de Caja", self.data.integrator_app_name),
            ("Modelo Pinpad", self.data.pinpad_model),
            ("Banco Patrocinador", self.data.sponsor_bank_name),
        ]
        elements.extend(self._build_modern_cover(
            subtitle="Merchant Server · Plataforma de Pagos",
            info_pairs=info_portada,
            fecha_actual=fecha_actual,
        ))
        
        # ==================== PÁGINA 2: CUERPO DEL DOCUMENTO ====================
        # Carta de presentación
        carta_header = f"""
        <b>Señores:</b> {self.data.cliente_nombre}<br/>
        <b>RIF:</b> {self.data.cliente_rif}<br/>
        <b>Att:</b> {self.data.cliente_contacto or 'Departamento de Compras'}<br/><br/>
        """
        elements.append(Paragraph(carta_header, self.styles['TextoNormal']))
        
        # Texto corregido según solicitud del usuario
        carta_body = f"""
        Por medio de la presente, nos complace presentarle nuestra propuesta comercial para la implementación 
        de terminales virtuales de pago en sus puntos de venta. La solución propuesta se implementa con la 
        integración del Merchant Server con el aplicativo <b>{self.data.integrator_app_name}</b> desarrollado 
        por <b>{self.data.integrator_name}</b>, garantizando una experiencia de cobro segura y eficiente.
        """
        elements.append(Paragraph(carta_body, self.styles['TextoNormal']))
        elements.append(Spacer(1, 15))
        
        # RESUMEN EJECUTIVO (inmediatamente después del párrafo)
        elements.append(Paragraph("RESUMEN EJECUTIVO", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 8))
        
        # Tabla de resumen con estilo igual al frontend (Cliente/Cajas/Dirección + Bancos/Productos)
        elements.extend(self._create_bank_products_table())
        
        # Salto de página
        elements.append(PageBreak())
        
        # ==================== PÁGINA 3: COSTOS ====================
        # Costos de Setup con desglose fiscal
        setup_elements, subtotal_setup = self._create_items_table(
            self.data.setup_items, 
            "COSTOS DE IMPLEMENTACIÓN (SETUP)", 
            self.COLOR_AZUL,
            show_tax=True
        )
        elements.extend(setup_elements)
        
        # Costos Recurrentes con desglose fiscal (solo si include_recurring es True)
        subtotal_recurrente = 0
        if self.data.include_recurring:
            all_recurring = self.data.recurring_basic_items + self.data.recurring_other_items + self.data.production_items
            recurring_elements, subtotal_recurrente = self._create_items_table(
                all_recurring, 
                "COSTOS RECURRENTES MENSUALES", 
                self.COLOR_VERDE,
                show_tax=True
            )
            elements.extend(recurring_elements)
        
        # Notas (si existen) - van en esta página
        if self.data.notes:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(f"<b>Notas:</b> {self.data.notes}", self.styles['TextoNormal']))
        
        # Salto de página para el Resumen de Inversión
        elements.append(PageBreak())
        
        # ==================== PÁGINA 4: RESUMEN DE LA INVERSIÓN ====================
        elements.append(Paragraph("RESUMEN DE LA INVERSIÓN", self.styles['TituloPortada']))
        elements.append(Spacer(1, 20))
        
        # Calcular totales con IVA (cero si cliente exento)
        _iva_rate = 0.0 if getattr(self.data, 'iva_exempt', False) else 0.16
        _iva_label_setup = "IVA Setup (Exento)" if getattr(self.data, 'iva_exempt', False) else "IVA Setup (16%)"
        _iva_label_recurrente = "IVA Recurrente (Exento)" if getattr(self.data, 'iva_exempt', False) else "IVA Recurrente (16%)"
        iva_setup = subtotal_setup * _iva_rate
        iva_recurrente = subtotal_recurrente * _iva_rate
        
        # Manejar descuentos independientes
        desc_setup_val = getattr(self.data, 'descuento_setup', 0) or 0
        desc_recurrente_val = getattr(self.data, 'descuento_recurrente', 0) or 0
        # Fallback to old single descuento for backward compatibility
        if desc_setup_val == 0 and desc_recurrente_val == 0:
            desc_setup_val = self.data.descuento or 0
        # Setup discount (percentage-based)
        monto_desc_setup = subtotal_setup * (desc_setup_val / 100) if desc_setup_val <= 100 else desc_setup_val
        subtotal_setup_con_descuento = subtotal_setup - monto_desc_setup
        iva_setup_con_descuento = subtotal_setup_con_descuento * _iva_rate
        total_setup_final = subtotal_setup_con_descuento + iva_setup_con_descuento
        
        # Recurrente discount (percentage-based)
        monto_desc_recurrente = subtotal_recurrente * (desc_recurrente_val / 100) if desc_recurrente_val <= 100 else desc_recurrente_val
        subtotal_recurrente_con_descuento = subtotal_recurrente - monto_desc_recurrente
        iva_recurrente_con_descuento = subtotal_recurrente_con_descuento * _iva_rate
        total_recurrente_final = subtotal_recurrente_con_descuento + iva_recurrente_con_descuento
        
        # Construir tabla de resumen
        resumen_data = [['Concepto', 'Monto (USD)']]
        
        # Setup
        resumen_data.append(['Subtotal Setup', f"${subtotal_setup:.2f}"])
        if monto_desc_setup > 0:
            resumen_data.append([f'Descuento Setup ({desc_setup_val}%)', f"-${monto_desc_setup:.2f}"])
            resumen_data.append(['Subtotal con Descuento', f"${subtotal_setup_con_descuento:.2f}"])
            resumen_data.append([_iva_label_setup, f"${iva_setup_con_descuento:.2f}"])
        else:
            resumen_data.append([_iva_label_setup, f"${iva_setup:.2f}"])
        resumen_data.append(['TOTAL SETUP (Pago Unico)', f"${total_setup_final:.2f}"])
        
        # Recurrentes (solo si include_recurring es True)
        if self.data.include_recurring:
            resumen_data.append(['', ''])  # Fila vacía separadora
            resumen_data.append(['Subtotal Recurrente', f"${subtotal_recurrente:.2f}"])
            if monto_desc_recurrente > 0:
                resumen_data.append([f'Descuento Recurrente ({desc_recurrente_val}%)', f"-${monto_desc_recurrente:.2f}"])
                resumen_data.append(['Subtotal con Descuento', f"${subtotal_recurrente_con_descuento:.2f}"])
                resumen_data.append([_iva_label_recurrente, f"${iva_recurrente_con_descuento:.2f}"])
            else:
                resumen_data.append([_iva_label_recurrente, f"${iva_recurrente:.2f}"])
            resumen_data.append(['TOTAL MENSUAL', f"${total_recurrente_final:.2f}"])
        
        # Gran total
        resumen_data.append(['', ''])
        resumen_data.append(['INVERSION INICIAL (Setup)', f"${total_setup_final:.2f}"])
        if self.data.include_recurring:
            resumen_data.append(['COSTO MENSUAL RECURRENTE', f"${total_recurrente_final:.2f}"])
        
        resumen_table = Table(resumen_data, colWidths=[360, 120])
        
        # Determinar índices de filas importantes
        idx_total_setup = 5 if monto_desc_setup <= 0 else 6
        
        resumen_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            # Destacar total setup
            ('BACKGROUND', (0, idx_total_setup), (-1, idx_total_setup), self.COLOR_AZUL_CLARO),
            ('FONTNAME', (0, idx_total_setup), (-1, idx_total_setup), 'Helvetica-Bold'),
            # Destacar total mensual
            ('BACKGROUND', (0, -3), (-1, -3), self.COLOR_VERDE_CLARO),
            ('FONTNAME', (0, -3), (-1, -3), 'Helvetica-Bold'),
            # Destacar filas finales
            ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor("#1E293B")),  # slate-800
            ('TEXTCOLOR', (0, -2), (-1, -1), colors.white),
            ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        elements.append(resumen_table)
        
        # ==================== PÁGINA 5 (FAST TRACK): COTIZACIÓN DE EQUIPOS ====================
        if self.data.quote_type == 'FAST_TRACK' and self.data.ft_equipment_items:
            elements.append(PageBreak())
            
            elements.append(Paragraph("COTIZACIÓN DE EQUIPOS", ParagraphStyle(
                'EquiposTitulo',
                parent=self.styles['TituloPortada'],
                fontSize=18,
                alignment=1,
                spaceAfter=6
            )))
            elements.append(Paragraph(
                "MPOS (Imple + POS) — Equipos incluidos en esta propuesta",
                ParagraphStyle('EquiposSubtitulo', parent=self.styles['TextoNormal'], alignment=1, fontSize=10, textColor=colors.HexColor("#64748B"), spaceAfter=16)
            ))
            
            # Tabla de equipos
            eq_header_style = ParagraphStyle('EqHeaderStyle', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white)
            eq_header = [
                Paragraph("<b>Descripción del Equipo</b>", eq_header_style),
                Paragraph("<b>Tipo</b>", eq_header_style),
                Paragraph("<b>Cant.</b>", ParagraphStyle('EqHdrCant', parent=eq_header_style, alignment=1)),
                Paragraph("<b>P. Unitario (USD)</b>", ParagraphStyle('EqHdrPU', parent=eq_header_style, alignment=2)),
                Paragraph("<b>Total (USD)</b>", ParagraphStyle('EqHdrT', parent=eq_header_style, alignment=2)),
            ]
            eq_rows = [eq_header]
            eq_subtotal = 0
            
            for item in self.data.ft_equipment_items:
                name = item.get("name", "Equipo")
                hw_type = item.get("hardware_type", "POS")
                qty = int(item.get("quantity", 1))
                unit_price = float(item.get("unit_price_usd", 0))
                total = qty * unit_price
                eq_subtotal += total
                
                eq_rows.append([
                    Paragraph(name, self.styles['TextoNormal']),
                    Paragraph(hw_type, self.styles['TextoNormal']),
                    Paragraph(str(qty), ParagraphStyle('EqQty', parent=self.styles['TextoNormal'], alignment=1)),
                    Paragraph(f"${unit_price:,.2f}", ParagraphStyle('EqPrice', parent=self.styles['TextoNormal'], alignment=2)),
                    Paragraph(f"${total:,.2f}", ParagraphStyle('EqTotal', parent=self.styles['TextoNormal'], alignment=2)),
                ])
            
            # Subtotal, IVA, Total (PYME)
            _eq_iva_rate = 0.0 if getattr(self.data, 'iva_exempt', False) else 0.16
            _eq_iva_label = "<b>IVA (Exento):</b>" if getattr(self.data, 'iva_exempt', False) else "<b>IVA (16%):</b>"
            eq_iva = eq_subtotal * _eq_iva_rate
            eq_grand_total = eq_subtotal + eq_iva
            
            eq_rows.append([
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("<b>Subtotal:</b>", ParagraphStyle('EqST', parent=self.styles['TextoNormal'], alignment=2)),
                Paragraph(f"<b>${eq_subtotal:,.2f}</b>", ParagraphStyle('EqSTv', parent=self.styles['TextoNormal'], alignment=2)),
            ])
            eq_rows.append([
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph(_eq_iva_label, ParagraphStyle('EqIVA', parent=self.styles['TextoNormal'], alignment=2)),
                Paragraph(f"<b>${eq_iva:,.2f}</b>", ParagraphStyle('EqIVAv', parent=self.styles['TextoNormal'], alignment=2)),
            ])
            eq_rows.append([
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("", self.styles['TextoNormal']),
                Paragraph("<b>TOTAL:</b>", ParagraphStyle('EqTOT', parent=self.styles['TextoNormal'], alignment=2, textColor=colors.white)),
                Paragraph(f"<b>${eq_grand_total:,.2f}</b>", ParagraphStyle('EqTOTv', parent=self.styles['TextoNormal'], alignment=2, textColor=colors.white)),
            ])
            
            eq_col_widths = [200, 70, 50, 90, 90]
            eq_table = Table(eq_rows, colWidths=eq_col_widths)
            eq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL_OSCURO),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -4), 0.5, colors.HexColor("#E0E0E0")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor("#F8FAFC")]),
                # Totals styling
                ('LINEABOVE', (3, -3), (-1, -3), 1, colors.HexColor("#CBD5E1")),
                ('BACKGROUND', (3, -1), (-1, -1), colors.HexColor("#1E293B")),
                ('TEXTCOLOR', (3, -1), (-1, -1), colors.white),
                ('FONTNAME', (3, -3), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(eq_table)
            
            elements.append(Spacer(1, 16))
            elements.append(Paragraph(
                "<b>Nota:</b> Los equipos se entregan configurados y listos para operar. "
                "La garantía cubre defectos de fábrica por 12 meses. No incluye daños por mal uso.",
                ParagraphStyle('EqNota', parent=self.styles['TextoNormal'], fontSize=9, textColor=colors.HexColor("#64748B"), spaceAfter=8)
            ))
        
        # ==================== PÁGINA CONDICIONAL: RELACIÓN DE TIENDAS ====================
        branch_details = getattr(self.data, 'branch_details', []) or []
        if branch_details:
            elements.append(PageBreak())
            elements.append(Paragraph("RELACIÓN DE TIENDAS", ParagraphStyle(
                'TiendasTitulo',
                parent=self.styles['TituloPortada'],
                fontSize=18,
                alignment=1,
                spaceAfter=10
            )))
            elements.append(Spacer(1, 15))
            
            # Tabla de sucursales
            branch_table_data = [
                [
                    Paragraph("<b>N°</b>", ParagraphStyle('BH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)),
                    Paragraph("<b>Nombre de Tienda / Sucursal</b>", ParagraphStyle('BH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white)),
                    Paragraph("<b>Cantidad de Cajas</b>", ParagraphStyle('BH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)),
                ]
            ]
            total_cajas = 0
            for i, branch in enumerate(branch_details, 1):
                qty = int(branch.get('quantity', 0))
                total_cajas += qty
                branch_table_data.append([
                    Paragraph(str(i), ParagraphStyle('BC', fontName='Helvetica', fontSize=9, alignment=1)),
                    Paragraph(str(branch.get('store_name', '')), ParagraphStyle('BN', fontName='Helvetica', fontSize=9)),
                    Paragraph(str(qty), ParagraphStyle('BQ', fontName='Helvetica', fontSize=9, alignment=1)),
                ])
            # Fila de totales
            branch_table_data.append([
                Paragraph("", ParagraphStyle('BE', fontName='Helvetica', fontSize=9)),
                Paragraph("<b>TOTAL</b>", ParagraphStyle('BT', fontName='Helvetica-Bold', fontSize=10, alignment=2)),
                Paragraph(f"<b>{total_cajas}</b>", ParagraphStyle('BTQ', fontName='Helvetica-Bold', fontSize=10, alignment=1)),
            ])
            
            col_widths_branch = [40, 340, 100]
            branch_table = Table(branch_table_data, colWidths=col_widths_branch, repeatRows=1)
            branch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            elements.append(branch_table)
        
        # Salto de página para Términos
        elements.append(PageBreak())
        
        # ==================== PÁGINA 5: TÉRMINOS DE LA COTIZACIÓN ====================
        elements.append(Paragraph("TÉRMINOS DE LA COTIZACIÓN", ParagraphStyle(
            'TerminosTitulo',
            parent=self.styles['TituloPortada'],
            fontSize=18,
            alignment=1,  # Centrado
            spaceAfter=10
        )))
        elements.append(Spacer(1, 20))
        
        # Fecha de vigencia en español
        vigencia_date = now + timedelta(days=5)
        vigencia_fecha = f"{vigencia_date.day} de {MESES_ES[vigencia_date.month]} de {vigencia_date.year}"
        
        terminos = f"""
        <b>1. Vigencia de la Propuesta</b><br/>
        La presente oferta económica tiene una vigencia de <b>5 días hábiles</b> a partir de su emisión.
        Fecha de vencimiento: <b>{vigencia_fecha}</b><br/><br/>
        
        <b>2. Tiempo de Implementación</b><br/>
        El tiempo estimado de implementación queda sujeto a la prontitud con la que las entidades 
        bancarias remitan la información técnica de afiliados y terminales de los productos seleccionados.<br/><br/>
        
        <b>3. Forma de Pago</b><br/>
        - Costos de Setup: 100% después de aprobar la propuesta para dar inicio al Proyecto<br/>
        - Costos Recurrentes: Facturación mensual vencida<br/><br/>
        
        <b>4. Soporte Técnico</b><br/>
        Se incluye soporte técnico 24/7 para incidencias relacionadas con la plataforma de pagos.<br/><br/>
        
        <b>5. Confidencialidad</b><br/>
        Toda la información contenida en este documento es confidencial y de uso exclusivo
        del destinatario.
        """
        elements.append(Paragraph(terminos, self.styles['TextoNormal']))
        
        # Construir documento con encabezado y pie de página
        doc.build(elements)
        
        self.buffer.seek(0)
        return self.buffer
    
    def _create_corp_financial_summary(self):
        """Crear la tabla de Costos de Implementación agrupada por tipo_corp para clientes corporativos.
        Nueva Página 3: agrupa items en Setup y Recurrentes, con columnas por tipo_corp."""
        elements = []
        
        elements.append(Paragraph("COSTOS DE IMPLEMENTACIÓN", self.styles['TituloPortada']))
        elements.append(Spacer(1, 20))
        
        # Definir columnas tipo_corp
        CORP_COLUMNS = ["Derecho de Uso", "Apoyo Técnico", "Soporte y Monitoreo"]
        
        # Recopilar todos los items con sus tipo_corp
        # NOTA: setup_items ya incluye additional_items con tarifa_setup > 0 (los fusiona el frontend)
        # NO añadir additional_items aquí para evitar doble conteo
        all_setup = list(self.data.setup_items)
        all_recurring = list(self.data.recurring_basic_items) + list(self.data.recurring_other_items) + list(self.data.production_items)
        
        # Calcular totales por tipo_corp y tipo (setup/recurrente)
        setup_by_corp = {}
        recurring_by_corp = {}
        
        for col in CORP_COLUMNS:
            setup_by_corp[col] = 0
            recurring_by_corp[col] = 0
        
        def _classify_item(item, target_dict):
            """Clasifica un item en la columna tipo_corp correspondiente."""
            tc = getattr(item, 'tipo_corp', None) or ''
            total_item = (item.cantidad_cajas or 1) * (item.cantidad_bancos or 1) * (item.tarifa or 0)
            if total_item == 0:
                return
            # Match exacto (case-insensitive)
            for col in CORP_COLUMNS:
                if tc and col.lower().strip() == tc.lower().strip():
                    target_dict[col] += total_item
                    return
            # NO default a primera columna: items sin tipo_corp no se clasifican
            # para evitar inflar "Derecho de Uso" incorrectamente
        
        for item in all_setup:
            _classify_item(item, setup_by_corp)
        
        for item in all_recurring:
            _classify_item(item, recurring_by_corp)
        
        # Calcular totales por columna y por fila
        total_setup = sum(setup_by_corp.values())
        total_recurring = sum(recurring_by_corp.values())
        total_by_col = {}
        for col in CORP_COLUMNS:
            total_by_col[col] = setup_by_corp[col] + recurring_by_corp[col]
        grand_total = total_setup + total_recurring
        
        # Construir tabla: Header con agrupación
        # Fila 0 (encabezado principal):  Concepto | Hardware y Software | Consultoría (colspan 2) | Total
        # Fila 1 (subencabezado):  "" | Derecho de Uso | Apoyo técnico | Soporte y Monitoreo | ""
        
        header_style = ParagraphStyle('CorpHeaderStyle', fontName='Helvetica-Bold', fontSize=11, textColor=colors.white, alignment=1)
        subheader_style = ParagraphStyle('CorpSubHeaderStyle', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)
        cell_style = ParagraphStyle('CorpCellStyle', fontName='Helvetica', fontSize=9, alignment=2)
        cell_bold_style = ParagraphStyle('CorpCellBoldStyle', fontName='Helvetica-Bold', fontSize=9, alignment=2)
        label_style = ParagraphStyle('CorpLabelStyle', fontName='Helvetica-Bold', fontSize=9, textColor=self.COLOR_AZUL)
        
        # Headers
        row_header = [
            Paragraph("<b>Concepto</b>", header_style),
            Paragraph("<b>Hardware y<br/>Software</b>", header_style),
            Paragraph("<b>Consultoría</b>", header_style),
            '',  # Merged with Consultoría
            Paragraph("<b>Total</b>", header_style),
        ]
        
        row_subheader = [
            '',
            Paragraph("<b>Derecho de Uso</b>", subheader_style),
            Paragraph("<b>Apoyo técnico</b>", subheader_style),
            Paragraph("<b>Soporte y<br/>Monitoreo</b>", subheader_style),
            '',
        ]
        
        # Data rows
        row_setup = [
            Paragraph("Set-up", label_style),
            Paragraph(f"${setup_by_corp['Derecho de Uso']:,.2f}", cell_style),
            Paragraph(f"${setup_by_corp['Apoyo Técnico']:,.2f}", cell_style),
            Paragraph(f"${setup_by_corp['Soporte y Monitoreo']:,.2f}", cell_style),
            Paragraph(f"${total_setup:,.2f}", cell_bold_style),
        ]
        
        row_recurring = [
            Paragraph("* Recurrentes", label_style),
            Paragraph(f"${recurring_by_corp['Derecho de Uso']:,.2f}", cell_style),
            Paragraph(f"${recurring_by_corp['Apoyo Técnico']:,.2f}", cell_style),
            Paragraph(f"${recurring_by_corp['Soporte y Monitoreo']:,.2f}", cell_style),
            Paragraph(f"${total_recurring:,.2f}", cell_bold_style),
        ]
        
        row_total = [
            Paragraph("<b>Total</b>", ParagraphStyle('CorpTotalLabel', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white)),
            Paragraph(f"<b>${total_by_col['Derecho de Uso']:,.2f}</b>", ParagraphStyle('CorpTotalCell', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=2)),
            Paragraph(f"<b>${total_by_col['Apoyo Técnico']:,.2f}</b>", ParagraphStyle('CorpTotalCell2', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=2)),
            Paragraph(f"<b>${total_by_col['Soporte y Monitoreo']:,.2f}</b>", ParagraphStyle('CorpTotalCell3', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=2)),
            Paragraph(f"<b>${grand_total:,.2f}</b>", ParagraphStyle('CorpGrandTotal', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, alignment=2)),
        ]
        
        table_data = [row_header, row_subheader, row_setup, row_recurring, row_total]
        
        col_widths = [85, 105, 100, 100, 90]
        table = Table(table_data, colWidths=col_widths)
        
        COLOR_AMARILLO = colors.HexColor("#F59E0B")
        
        table.setStyle(TableStyle([
            # Header row 0
            ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('SPAN', (2, 0), (3, 0)),  # Merge "Consultoría" across 2 columns
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            
            # Subheader row 1
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#336699")),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.white),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            
            # Data rows
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#F0F4F8")),
            ('BACKGROUND', (0, 3), (-1, 3), colors.white),
            
            # Total row
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0, 4), (-1, 4), colors.white),
            # Highlight grand total cell in yellow
            ('BACKGROUND', (4, 4), (4, 4), COLOR_AMARILLO),
            ('TEXTCOLOR', (4, 4), (4, 4), colors.HexColor("#1E293B")),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        
        # Notas al pie
        nota_style = ParagraphStyle('CorpNota', fontName='Helvetica', fontSize=8, textColor=colors.HexColor("#DC2626"), leading=10)
        elements.append(Paragraph("Montos no incluyen IVA", nota_style))
        elements.append(Spacer(1, 8))
        
        nota_amarillo_style = ParagraphStyle('CorpNotaAmarillo', fontName='Helvetica', fontSize=8, textColor=self.COLOR_TEXTO, leading=10)
        elements.append(Paragraph(
            "Monto resaltado en amarillo es el que deberá ser pagado al momento de ser aprobado este presupuesto",
            nota_amarillo_style
        ))
        elements.append(Spacer(1, 8))
        
        nota_recurrente_style = ParagraphStyle('CorpNotaRec', fontName='Helvetica', fontSize=8, textColor=self.COLOR_TEXTO, leading=10)
        elements.append(Paragraph(
            "*El recurrente mes aplicará desde el momento que sean activadas las cajas registradoras",
            nota_recurrente_style
        ))
        
        return elements, total_setup, total_recurring
    
    def generate_vpos_corp(self):
        """Generar PDF para cotizaciones VPOS de clientes Corporativos.
        Estructura:
          Pág 1: Portada (mantener)
          Pág 2: Resumen Ejecutivo (mantener)
          Pág 3: Costos de Implementación agrupados (NUEVA - reemplaza págs 3+4)
          Pág 4: (Condicional) Equipos Fast Track si aplica
          Luego: Anexo Corporativa se añade externamente
        """
        MESES_ES = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=100,
            bottomMargin=60
        )
        
        elements = []
        now = datetime.now()
        fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"
        
        # ==================== PÁGINA 1: PORTADA (diseño moderno, igual a VPOS) ====================
        info_portada = [
            ("Cliente", self.data.cliente_nombre),
            ("RIF", self.data.cliente_rif),
            ("Cantidad de Cajas", str(self.data.cantidad_cajas)),
            ("Integrador", self.data.integrator_name),
            ("Aplicativo de Caja", self.data.integrator_app_name),
            ("Modelo Pinpad", self.data.pinpad_model),
            ("Banco Patrocinador", self.data.sponsor_bank_name),
        ]
        elements.extend(self._build_modern_cover(
            subtitle="Merchant Server · Plataforma de Pagos",
            info_pairs=info_portada,
            fecha_actual=fecha_actual,
        ))
        
        # ==================== PÁGINA 2: RESUMEN EJECUTIVO (igual que VPOS estándar) ====================
        carta_header = f"""
        <b>Señores:</b> {self.data.cliente_nombre}<br/>
        <b>RIF:</b> {self.data.cliente_rif}<br/>
        <b>Att:</b> {self.data.cliente_contacto or 'Departamento de Compras'}<br/><br/>
        """
        elements.append(Paragraph(carta_header, self.styles['TextoNormal']))
        
        carta_body = f"""
        Por medio de la presente, nos complace presentarle nuestra propuesta comercial para la implementación 
        de terminales virtuales de pago en sus puntos de venta. La solución propuesta se implementa con la 
        integración del Merchant Server con el aplicativo <b>{self.data.integrator_app_name}</b> desarrollado 
        por <b>{self.data.integrator_name}</b>, garantizando una experiencia de cobro segura y eficiente.
        """
        elements.append(Paragraph(carta_body, self.styles['TextoNormal']))
        elements.append(Spacer(1, 15))
        
        elements.append(Paragraph("RESUMEN EJECUTIVO", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 8))
        
        elements.extend(self._create_bank_products_table())
        
        elements.append(PageBreak())
        
        # ==================== PÁGINA 3: COSTOS DE IMPLEMENTACIÓN (NUEVA) ====================
        corp_elements, total_setup, total_recurring = self._create_corp_financial_summary()
        elements.extend(corp_elements)
        
        # ==================== PÁGINA 4: DETALLE TÉCNICO ÍTEM POR ÍTEM ====================
        # Misma estructura que Página 3 de PDF Pyme: desglose individual de cada componente
        elements.append(PageBreak())
        
        setup_elements, subtotal_setup_detail = self._create_items_table(
            self.data.setup_items,
            "COSTOS DE IMPLEMENTACIÓN (SETUP)",
            self.COLOR_AZUL,
            show_tax=True,
            discount_pct=(getattr(self.data, 'descuento_setup', 0) or 0)
        )
        elements.extend(setup_elements)
        
        all_recurring = list(self.data.recurring_basic_items) + list(self.data.recurring_other_items) + list(self.data.production_items)
        recurring_elements, subtotal_recurring_detail = self._create_items_table(
            all_recurring,
            "COSTOS RECURRENTES MENSUALES",
            self.COLOR_VERDE,
            show_tax=True,
            discount_pct=(getattr(self.data, 'descuento_recurrente', 0) or 0)
        )
        elements.extend(recurring_elements)
        
        # ==================== PÁGINA (condicional): EQUIPOS FAST TRACK ====================
        if self.data.quote_type == 'FAST_TRACK' and self.data.ft_equipment_items:
            elements.append(PageBreak())
            
            elements.append(Paragraph("COTIZACIÓN DE EQUIPOS", ParagraphStyle(
                'CorpEquiposTitulo',
                parent=self.styles['TituloPortada'],
                fontSize=18,
                alignment=1,
                spaceAfter=6
            )))
            elements.append(Paragraph(
                "MPOS (Imple + POS) — Equipos incluidos en esta propuesta",
                ParagraphStyle('CorpEquiposSubtitulo', parent=self.styles['TextoNormal'], alignment=1, fontSize=10, textColor=colors.HexColor("#64748B"), spaceAfter=16)
            ))
            
            eq_header = [
                Paragraph("<b>Descripción del Equipo</b>", ParagraphStyle('CorpEqH1', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white)),
                Paragraph("<b>Tipo</b>", ParagraphStyle('CorpEqH2', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white)),
                Paragraph("<b>Cant.</b>", ParagraphStyle('CorpEqH3', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, alignment=1)),
                Paragraph("<b>P. Unitario (USD)</b>", ParagraphStyle('CorpEqH4', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, alignment=2)),
                Paragraph("<b>Total (USD)</b>", ParagraphStyle('CorpEqH5', fontName='Helvetica-Bold', fontSize=10, textColor=colors.white, alignment=2)),
            ]
            eq_rows = [eq_header]
            eq_subtotal = 0
            
            for item in self.data.ft_equipment_items:
                name = item.get("name", "Equipo")
                hw_type = item.get("hardware_type", "POS")
                qty = int(item.get("quantity", 1))
                unit_price = float(item.get("unit_price_usd", 0))
                total = qty * unit_price
                eq_subtotal += total
                
                eq_rows.append([
                    Paragraph(name, self.styles['TextoNormal']),
                    Paragraph(hw_type, self.styles['TextoNormal']),
                    Paragraph(str(qty), ParagraphStyle('CorpEqQty', parent=self.styles['TextoNormal'], alignment=1)),
                    Paragraph(f"${unit_price:,.2f}", ParagraphStyle('CorpEqPrice', parent=self.styles['TextoNormal'], alignment=2)),
                    Paragraph(f"${total:,.2f}", ParagraphStyle('CorpEqTotal', parent=self.styles['TextoNormal'], alignment=2)),
                ])
            
            _corp_iva_rate = 0.0 if getattr(self.data, 'iva_exempt', False) else 0.16
            _corp_iva_label = "<b>IVA (Exento):</b>" if getattr(self.data, 'iva_exempt', False) else "<b>IVA (16%):</b>"
            eq_iva = eq_subtotal * _corp_iva_rate
            eq_grand_total = eq_subtotal + eq_iva
            
            eq_rows.append(['', '', '',
                Paragraph("<b>Subtotal:</b>", ParagraphStyle('CorpEqST', parent=self.styles['TextoNormal'], alignment=2)),
                Paragraph(f"<b>${eq_subtotal:,.2f}</b>", ParagraphStyle('CorpEqSTv', parent=self.styles['TextoNormal'], alignment=2)),
            ])
            eq_rows.append(['', '', '',
                Paragraph(_corp_iva_label, ParagraphStyle('CorpEqIVA', parent=self.styles['TextoNormal'], alignment=2)),
                Paragraph(f"<b>${eq_iva:,.2f}</b>", ParagraphStyle('CorpEqIVAv', parent=self.styles['TextoNormal'], alignment=2)),
            ])
            eq_rows.append(['', '', '',
                Paragraph("<b>TOTAL:</b>", ParagraphStyle('CorpEqTOT', parent=self.styles['TextoNormal'], alignment=2, textColor=colors.white)),
                Paragraph(f"<b>${eq_grand_total:,.2f}</b>", ParagraphStyle('CorpEqTOTv', parent=self.styles['TextoNormal'], alignment=2, textColor=colors.white)),
            ])
            
            eq_col_widths = [200, 70, 50, 90, 90]
            eq_table = Table(eq_rows, colWidths=eq_col_widths)
            eq_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL_OSCURO),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -4), 0.5, colors.HexColor("#E0E0E0")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor("#F8FAFC")]),
                ('LINEABOVE', (3, -3), (-1, -3), 1, colors.HexColor("#CBD5E1")),
                ('BACKGROUND', (3, -1), (-1, -1), colors.HexColor("#1E293B")),
                ('TEXTCOLOR', (3, -1), (-1, -1), colors.white),
                ('FONTNAME', (3, -3), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(eq_table)
            
            elements.append(Spacer(1, 16))
            elements.append(Paragraph(
                "<b>Nota:</b> Los equipos se entregan configurados y listos para operar. "
                "La garantía cubre defectos de fábrica por 12 meses. No incluye daños por mal uso.",
                ParagraphStyle('CorpEqNota', parent=self.styles['TextoNormal'], fontSize=9, textColor=colors.HexColor("#64748B"), spaceAfter=8)
            ))
        
        # ==================== PÁGINA CONDICIONAL: RELACIÓN DE TIENDAS (CORP) ====================
        branch_details = getattr(self.data, 'branch_details', []) or []
        if branch_details:
            elements.append(PageBreak())
            elements.append(Paragraph("RELACIÓN DE TIENDAS", ParagraphStyle(
                'TiendasTituloCorp', parent=self.styles['TituloPortada'], fontSize=18, alignment=1, spaceAfter=10
            )))
            elements.append(Spacer(1, 15))
            branch_table_data = [
                [Paragraph("<b>N°</b>", ParagraphStyle('CBH', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1)),
                 Paragraph("<b>Nombre de Tienda / Sucursal</b>", ParagraphStyle('CBH2', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white)),
                 Paragraph("<b>Cantidad de Cajas</b>", ParagraphStyle('CBH3', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white, alignment=1))]
            ]
            total_cajas = 0
            for i, branch in enumerate(branch_details, 1):
                qty = int(branch.get('quantity', 0))
                total_cajas += qty
                branch_table_data.append([
                    Paragraph(str(i), ParagraphStyle('CBC', fontName='Helvetica', fontSize=9, alignment=1)),
                    Paragraph(str(branch.get('store_name', '')), ParagraphStyle('CBN', fontName='Helvetica', fontSize=9)),
                    Paragraph(str(qty), ParagraphStyle('CBQ', fontName='Helvetica', fontSize=9, alignment=1)),
                ])
            branch_table_data.append([
                Paragraph("", ParagraphStyle('CBE', fontName='Helvetica', fontSize=9)),
                Paragraph("<b>TOTAL</b>", ParagraphStyle('CBT', fontName='Helvetica-Bold', fontSize=10, alignment=2)),
                Paragraph(f"<b>{total_cajas}</b>", ParagraphStyle('CBTQ', fontName='Helvetica-Bold', fontSize=10, alignment=1)),
            ])
            branch_table = Table(branch_table_data, colWidths=[40, 340, 100], repeatRows=1)
            branch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'), ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8), ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8FAFC')]),
                ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            elements.append(branch_table)
        
        # NO añadir términos - el Anexo Corporativa los reemplaza
        # El anexo se fusiona externamente en config.py
        
        doc.build(elements)
        
        self.buffer.seek(0)
        return self.buffer
    
    def generate_pg(self):
        """Generar el PDF para Payment Gateway - Unificado con estética VPOS"""
        
        MESES_ES = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
        }
        
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            leftMargin=self.margin,
            rightMargin=self.margin,
            topMargin=100,
            bottomMargin=60
        )
        
        elements = []
        now = datetime.now()
        fecha_actual = f"{now.day} de {MESES_ES[now.month]} de {now.year}"
        
        # ==================== PÁGINA 1: PORTADA (diseño moderno) ====================
        # Subtítulo dinámico: Payment Gateway vs Payment Gateway - Link de Pagos
        if getattr(self, "_link_pago_mode", False):
            pg_subtitle = "Payment Gateway · Link de Pagos"
        else:
            pg_subtitle = "Payment Gateway · Plataforma de Pagos"

        info_portada = [
            ("Cliente", self.data.cliente_nombre),
            ("RIF", self.data.cliente_rif),
            ("Integrador", self.data.integrator_name or "Sin integrador por el momento"),
            ("Aplicativo", self.data.integrator_app_name),
        ]
        elements.extend(self._build_modern_cover(
            subtitle=pg_subtitle,
            info_pairs=info_portada,
            fecha_actual=fecha_actual,
        ))
        
        # ==================== PÁGINA 2: RESUMEN EJECUTIVO ====================
        # Carta de presentación (idéntica a VPOS)
        carta_header = f"""
        <b>Señores:</b> {self.data.cliente_nombre}<br/>
        <b>RIF:</b> {self.data.cliente_rif}<br/>
        <b>Att:</b> {self.data.cliente_contacto or 'Departamento de Compras'}<br/><br/>
        """
        elements.append(Paragraph(carta_header, self.styles['TextoNormal']))
        
        integrator_text = f'el aplicativo <b>{self.data.integrator_app_name}</b> desarrollado por <b>{self.data.integrator_name}</b>' if self.data.integrator_name and self.data.integrator_name != 'Sin integrador por el momento' else 'su plataforma de e-commerce'
        carta_body = f"""
        Por medio de la presente, nos complace presentarle nuestra propuesta comercial para la implementación 
        del servicio de <b>Payment Gateway</b> a través del Merchant Server. La solución propuesta se integra con 
        {integrator_text}, garantizando una experiencia de cobro segura y eficiente para transacciones en línea.
        """
        elements.append(Paragraph(carta_body, self.styles['TextoNormal']))
        elements.append(Spacer(1, 15))
        
        # Título Resumen Ejecutivo
        elements.append(Paragraph("RESUMEN EJECUTIVO", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 8))
        
        # Tabla de Bancos y Productos (sin "Persona Jurídica")
        producto_style = ParagraphStyle(
            'PGProductoCell',
            fontName='Helvetica',
            fontSize=7.5,
            leading=9,
            wordWrap='LTR'
        )
        
        bank_product_map = {}
        if self.data.pg_setup_items:
            pg_items = self.data.pg_setup_items
        else:
            pg_items = [{"concepto": i.concepto, "costo": i.tarifa, "banco": i.bank_name or ""} for i in self.data.setup_items]
        
        for item in pg_items:
            concepto = str(item.get('concepto', ''))
            # Filtrar "Persona Jurídica"
            if 'persona jur' in concepto.lower():
                continue
            banco = str(item.get('banco', ''))
            if not banco:
                continue
            key = banco
            if key not in bank_product_map:
                bank_product_map[key] = {'bank': banco, 'products': set()}
            bank_product_map[key]['products'].add(concepto)
        
        if bank_product_map:
            table_data = [['Bancos', 'Productos']]
            for data_entry in bank_product_map.values():
                products_str = ', '.join(data_entry['products'])
                table_data.append([data_entry['bank'], Paragraph(products_str, producto_style)])
            
            table = Table(table_data, colWidths=[180, 310])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (0, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ]))
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)]))
            elements.append(table)
        
        elements.append(PageBreak())
        
        # ==================== PÁGINA 3: INVERSIÓN EN SETUP ====================
        elements.append(Paragraph("INVERSIÓN EN SETUP / ARRANQUE", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 8))
        
        concepto_style = ParagraphStyle(
            'PGConceptoCell',
            fontName='Helvetica',
            fontSize=7,
            leading=9,
            wordWrap='LTR'
        )
        banco_style = ParagraphStyle(
            'PGBancoCell',
            fontName='Helvetica',
            fontSize=7,
            leading=9,
            wordWrap='LTR'
        )
        obs_style = ParagraphStyle(
            'PGObsCell',
            fontName='Helvetica',
            fontSize=7,
            leading=9,
            wordWrap='LTR'
        )
        
        if pg_items:
            pg_table_data = [['N°', 'Concepto', 'Costo (USD)', 'Banco', 'Observación']]
            subtotal_setup = 0
            
            for idx, item in enumerate(pg_items, 1):
                costo = item.get('costo', 0) or 0
                subtotal_setup += costo
                obs = str(item.get('observacion', '') or '')
                if 'cargado automáticamente' in obs.lower():
                    obs = 'Costo Base'
                pg_table_data.append([
                    str(idx),
                    Paragraph(str(item.get('concepto', '')), concepto_style),
                    f"${costo:.2f}",
                    Paragraph(str(item.get('banco', '')), banco_style),
                    Paragraph(obs, obs_style)
                ])
            
            pg_table_data.append(['', 'TOTAL SETUP', f"${subtotal_setup:.2f}", '', ''])
            
            col_widths = [25, 165, 75, 115, 110]
            pg_table = Table(pg_table_data, colWidths=col_widths, repeatRows=1)
            
            pg_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_AZUL),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('TOPPADDING', (0, 0), (-1, 0), 6),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (2, 1), (2, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, -1), (-1, -1), self.COLOR_AZUL_CLARO),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (-1, -1), 8),
            ]))
            
            for i in range(1, len(pg_table_data) - 1):
                if i % 2 == 0:
                    pg_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), self.COLOR_GRIS)]))
            
            elements.append(pg_table)
        
        elements.append(PageBreak())
        
        # ==================== PÁGINA 4: COSTOS RECURRENTES ====================
        elements.append(Paragraph("COSTOS RECURRENTES MENSUALES", self.styles['SeccionHeader']))
        elements.append(Spacer(1, 4))
        
        all_recurring = self.data.recurring_basic_items + self.data.recurring_other_items + self.data.production_items
        pg_rc = self.data.pg_recurring_cost
        if pg_rc and (pg_rc.get('rangos') or pg_rc.get('table')):
            num_products = pg_rc.get('num_products', 1)
            elements.append(Paragraph(
                f"Calculado para <b>{num_products}</b> medio(s) de pago",
                ParagraphStyle('CalcPara', parent=self.styles['TextoNormal'], fontSize=9, spaceAfter=6)
            ))
            
            rec_table_data = [['Rango', 'Transacciones', 'Total Base', 'Precio Tope por\nrango']]
            
            # Soportar ambos formatos: rangos (guardado) y table (frontend)
            rangos = pg_rc.get('rangos', [])
            if not rangos and pg_rc.get('table'):
                rangos = [{
                    'rango_label': r.get('label', ''),
                    'costo_base_total': r.get('base', 0),
                    'precio_tope': r.get('tope', 0)
                } for r in pg_rc['table']]
            for idx, rango in enumerate(rangos, 1):
                costo_base = rango.get('costo_base_total', 0)
                precio_tope = rango.get('precio_tope', 0)
                label = rango.get('rango_label', str(idx))
                
                base_str = f"${costo_base:.2f}" if costo_base and costo_base > 0 else "Negociable"
                tope_str = f"${precio_tope:.6f}" if precio_tope else ""
                
                rec_table_data.append([str(idx), label, base_str, tope_str])
            
            col_widths = [55, 140, 120, 130]
            rec_table = Table(rec_table_data, colWidths=col_widths, repeatRows=1)
            
            header_bg = self.COLOR_AZUL
            alt_row_bg = colors.HexColor("#DCE6F1")
            
            base_style = [
                ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B0B0")),
            ]
            
            rec_table.setStyle(TableStyle(base_style))
            
            for i in range(1, len(rec_table_data)):
                if i % 2 == 0:
                    rec_table.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), alt_row_bg)]))
            
            elements.append(rec_table)
        elif all_recurring:
            # Fallback: tabla simple si no hay rangos
            rec_concepto_style = ParagraphStyle(
                'PGRecConceptoCell', fontName='Helvetica', fontSize=8, leading=10, wordWrap='LTR'
            )
            rec_table_data = [['N°', 'Concepto', 'Cant.', 'Tarifa (USD)', 'Total (USD)']]
            subtotal_rec = 0
            for idx, item in enumerate(all_recurring, 1):
                cant = (item.cantidad_cajas or 1) * (item.cantidad_bancos or 1)
                total_item = cant * (item.tarifa or 0)
                subtotal_rec += total_item
                rec_table_data.append([str(idx), Paragraph(item.concepto, rec_concepto_style), str(cant), f"${item.tarifa:.2f}", f"${total_item:.2f}"])
            rec_table_data.append(['', 'TOTAL RECURRENTE', '', '', f"${subtotal_rec:.2f}"])
            col_widths = [25, None, 35, 70, 80]
            rec_table = Table(rec_table_data, colWidths=col_widths, repeatRows=1, hAlign='CENTER')
            rec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLOR_VERDE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ('BACKGROUND', (0, -1), (-1, -1), self.COLOR_VERDE),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(rec_table)
        
        if self.data.notes:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(f"<b>Notas:</b> {self.data.notes}", self.styles['TextoNormal']))
        
        elements.append(PageBreak())
        
        # ==================== PÁGINA 5: TÉRMINOS DE LA COTIZACIÓN ====================
        elements.append(Paragraph("TÉRMINOS DE LA COTIZACIÓN", ParagraphStyle(
            'PGTerminosTitulo',
            parent=self.styles['TituloPortada'],
            fontSize=18,
            alignment=1,
            spaceAfter=10
        )))
        elements.append(Spacer(1, 20))
        
        vigencia_date = now + timedelta(days=5)
        vigencia_fecha = f"{vigencia_date.day} de {MESES_ES[vigencia_date.month]} de {vigencia_date.year}"
        
        terminos = f"""
        <b>1. Vigencia de la Propuesta</b><br/>
        La presente oferta económica tiene una vigencia de <b>5 días hábiles</b> a partir de su emisión.
        Fecha de vencimiento: <b>{vigencia_fecha}</b><br/><br/>
        
        <b>2. Tiempo de Implementación</b><br/>
        El tiempo estimado de implementación queda sujeto a la prontitud con la que las entidades 
        bancarias remitan la información técnica de afiliados y terminales de los productos seleccionados.<br/><br/>
        
        <b>3. Forma de Pago</b><br/>
        - Costos de Setup: 100% después de aprobar la propuesta para dar inicio al Proyecto<br/>
        - Costos Recurrentes: Facturación mensual vencida<br/><br/>
        
        <b>4. Soporte Técnico</b><br/>
        Se incluye soporte técnico 24/7 para incidencias relacionadas con la plataforma de pagos.<br/><br/>
        
        <b>5. Confidencialidad</b><br/>
        Toda la información contenida en este documento es confidencial y de uso exclusivo
        del destinatario.
        """
        elements.append(Paragraph(terminos, self.styles['TextoNormal']))
        
        doc.build(elements)
        
        self.buffer.seek(0)
        return self.buffer


def create_overlay_pdf(data: TemplateQuotePDFRequest, page_width: float, page_height: float, page_num: int):
    """[LEGACY] Crea un PDF overlay para el modo de plantilla base - Solo para compatibilidad"""
    buffer = io.BytesIO()
    c = canvas_module.Canvas(buffer, pagesize=(page_width, page_height))
    c.save()
    buffer.seek(0)
    return buffer


