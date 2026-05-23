"""Tests Iteration 14: Botón Volver embebido + propagación de anexos en DeliveryDialog."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_invoiced_exits_report_has_back_button():
    """El reporte debe tener un botón de Volver embebido (no del navegador)."""
    with open("/app/frontend/src/pages/InvoicedExitsReport.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "useNavigate" in content
    assert "navigate(-1)" in content
    assert 'data-testid="report-back-btn"' in content


def test_delivery_dialog_accepts_email_headers():
    """DeliveryDialog debe aceptar emailHeaders y mergearlos al POST /deliver."""
    with open("/app/frontend/src/components/quotes/DeliveryDialog.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "emailHeaders = null" in content
    assert "...(emailHeaders || {})" in content


def test_quotes_propagates_email_headers_to_delivery_dialog():
    """Quotes.jsx debe capturar getEmailHeaders() al confirmar y pasarlos al DeliveryDialog."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "deliveryEmailHeaders" in content
    assert "handleDeliverQuote(quoteId, pendingAction?.exceptionHeaders || null, getEmailHeaders())" in content
    # Modal de QuoteModals.jsx recibe la prop emailHeaders
    with open("/app/frontend/src/components/quotes/QuoteModals.jsx", "r", encoding="utf-8") as f:
        qm = f.read()
    assert "emailHeaders={deliveryEmailHeaders}" in qm
