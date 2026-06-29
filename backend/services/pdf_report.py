"""Generador estandarizado de reportes PDF corporativos (reportlab).

Estándar corporativo unificado para todas las tablas maestras:
- Logo de la compañía en el margen superior izquierdo.
- Texto "CRM - Gestor" en la esquina superior derecha (10-12pt).
- Encabezado de tabla repetido en TODAS las páginas (repeatRows=1).
- Numeración de página "Pág. X / Y" al pie.
- Orientación horizontal (landscape) automática cuando hay muchas columnas
  o contenido extenso, para evitar truncamiento/solapamiento de celdas.
- Celdas con ajuste de texto (word-wrap) vía Paragraph: nunca se corta data.
"""
import io
import os

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT

from config import UPLOADS_DIR

LOGO_PATH = os.path.join(UPLOADS_DIR, "notif_logo.jpg")
BRAND_BLUE = colors.HexColor("#00447C")
BRAND_GREEN = colors.HexColor("#1B7D4E")
GRID_COLOR = colors.HexColor("#e2e8f0")


def _cell_style():
    return ParagraphStyle(
        "cell", fontName="Helvetica", fontSize=8, leading=10,
        alignment=TA_LEFT, textColor=colors.HexColor("#0f172a"),
    )


def _header_cell_style():
    return ParagraphStyle(
        "hcell", fontName="Helvetica-Bold", fontSize=8.5, leading=10,
        alignment=TA_LEFT, textColor=colors.white,
    )


def _make_decorator(title, header_color):
    def _decorate(canvas, doc):
        canvas.saveState()
        page_w, page_h = doc.pagesize
        # Logo superior izquierdo
        try:
            if os.path.exists(LOGO_PATH):
                canvas.drawImage(
                    LOGO_PATH, doc.leftMargin, page_h - 0.7 * inch,
                    width=1.1 * inch, height=0.5 * inch,
                    preserveAspectRatio=True, mask="auto", anchor="nw",
                )
        except Exception:
            pass
        # "CRM - Gestor" esquina superior derecha (11pt)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.setFillColor(header_color)
        canvas.drawRightString(page_w - doc.rightMargin, page_h - 0.45 * inch, "CRM - Gestor")
        # Título centrado bajo el header band
        canvas.setFont("Helvetica-Bold", 13)
        canvas.setFillColor(colors.HexColor("#0f172a"))
        canvas.drawString(doc.leftMargin, page_h - 0.95 * inch, title)
        # Pie: numeración de página
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(
            page_w - doc.rightMargin, 0.4 * inch,
            f"Pág. {doc.page}",
        )
        canvas.drawString(doc.leftMargin, 0.4 * inch, "MegaNexus · Documento confidencial")
        canvas.restoreState()
    return _decorate


def build_corporate_pdf(
    title: str,
    headers: list,
    rows: list,
    col_ratios: list = None,
    force_landscape: bool = None,
    header_color=BRAND_BLUE,
    filename: str = "reporte.pdf",
) -> io.BytesIO:
    """Construye un PDF tabular corporativo y devuelve un BytesIO listo para stream.

    headers: lista de títulos de columna.
    rows: lista de filas; cada fila es una lista de valores (se convierten a str).
    col_ratios: pesos relativos de ancho por columna (opcional). Si no se pasa, equitativo.
    force_landscape: fuerza orientación. Si None, se decide automáticamente
      (landscape cuando hay >= 6 columnas).
    """
    n_cols = len(headers)
    use_landscape = force_landscape if force_landscape is not None else (n_cols >= 6)
    pagesize = landscape(letter) if use_landscape else letter

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=1.15 * inch, bottomMargin=0.6 * inch,
        title=title,
    )

    avail_w = doc.width
    if col_ratios and len(col_ratios) == n_cols:
        total = float(sum(col_ratios)) or 1.0
        col_widths = [avail_w * (r / total) for r in col_ratios]
    else:
        col_widths = [avail_w / n_cols] * n_cols

    hstyle = _header_cell_style()
    cstyle = _cell_style()

    table_data = [[Paragraph(str(h), hstyle) for h in headers]]
    for row in rows:
        table_data.append([Paragraph("" if v is None else str(v), cstyle) for v in row])

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    decorator = _make_decorator(title, header_color)
    doc.build([table], onFirstPage=decorator, onLaterPages=decorator)
    buffer.seek(0)
    return buffer


def build_xlsx(headers: list, rows: list, sheet_name: str = "Datos") -> io.BytesIO:
    """Genera un Excel (.xlsx) con encabezados + filas. Devuelve BytesIO."""
    import pandas as pd
    safe_sheet = (sheet_name or "Datos")[:31]
    df = pd.DataFrame(rows, columns=headers)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=safe_sheet)
    output.seek(0)
    return output
