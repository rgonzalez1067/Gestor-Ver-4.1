"""Regresión: el PDF de cotizaciones de clientes Corporativos debe reflejar el
% de descuento y el monto descontado en las matrices de Setup y Recurrente,
restándose del total (IVA calculado sobre el neto)."""
import io
import fitz  # PyMuPDF
from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator


def _build_corp_pdf(desc_setup, desc_recurrente):
    req = TemplateQuotePDFRequest(
        cliente_nombre="Cliente Corp Test",
        cliente_rif="J-123",
        client_segment="CORP",
        quote_type="Verifone",
        quote_number="COT-TEST-CORP",
        setup_items=[{"concepto": "Licencia POS", "cantidad_cajas": 3, "cantidad_bancos": 2, "tarifa": 53.0, "tipo_corp": "Derecho de Uso"}],
        recurring_basic_items=[{"concepto": "Soporte mensual", "cantidad_cajas": 3, "cantidad_bancos": 2, "tarifa": 47.22, "tipo_corp": "Soporte y Monitoreo"}],
        descuento_setup=desc_setup,
        descuento_recurrente=desc_recurrente,
    )
    buf = DynamicQuotePDFGenerator(req, None).generate()
    return buf.getvalue()


def _page_text(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(p.get_text() for p in doc)


def test_corp_discount_rows_present():
    text = _page_text(_build_corp_pdf(10, 5))
    # Filas de descuento visibles en ambas matrices
    assert "Descuento (10%):" in text
    assert "Descuento (5%):" in text
    assert "Subtotal Neto:" in text
    # Monto descontado del Setup (318.00 * 10% = 31.80) y neto 286.20
    assert "-$31.80" in text
    assert "$286.20" in text


def test_corp_no_discount_no_rows():
    text = _page_text(_build_corp_pdf(0, 0))
    # Sin descuento declarado, no se inyectan filas de descuento
    assert "Descuento (" not in text
    assert "Subtotal Neto:" not in text
