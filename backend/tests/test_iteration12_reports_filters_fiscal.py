"""Tests Iteration 12: Reportes admin, filtro predictivo, nota de entrega, impresora fiscal."""
import os
import sys
import asyncio
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import db  # noqa: E402


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_invoiced_exits_report_includes_movement_id_and_serials():
    """El reporte de salidas facturadas debe incluir movement_id y serials para el modal admin."""
    with open("/app/backend/routes/inventory.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Snippet de la función get_invoiced_exits_report
    idx = content.find("get_invoiced_exits_report")
    assert idx > 0, "Función no encontrada"
    snippet = content[idx:idx + 4000]
    assert '"movement_id"' in snippet
    assert '"serials"' in snippet


def test_hoja_ruta_pdf_white_header():
    """La hoja de ruta debe usar estilo blanco en encabezados sección 3 (contraste)."""
    with open("/app/backend/services/hoja_ruta_pdf.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "NECellWhite" in content
    assert "s_cell_white" in content


def test_deliver_uses_legal_name_for_razon_social():
    """deliver_quote debe pasar legal_name como client_name (Razón Social en PDF)."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    # Debe priorizar legal_name primero al construir client_name para la nota
    assert 'client.get("legal_name") or client.get("fantasy_name"' in content


def test_implementation_pdf_includes_fiscal_printer_section():
    """La Ficha Técnica debe imprimir 'Modelo de Impresora Fiscal' después de Seriales."""
    with open("/app/backend/services/implementation_pdf.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Modelo de Impresora Fiscal" in content
    assert "fiscal_printer_model" in content
    # Debe estar después del banner C. SERIALES DE LOS EQUIPOS
    seriales_idx = content.find("C. SERIALES DE LOS EQUIPOS")
    fiscal_idx = content.find("Modelo de Impresora Fiscal")
    resumen_idx = content.find("RESUMEN COMERCIAL")
    assert 0 < seriales_idx < fiscal_idx < resumen_idx, "Orden incorrecto en el PDF"


def test_project_persists_fiscal_printer_model():
    """_create_project_from_quote debe aceptar y persistir fiscal_printer_model."""
    with open("/app/backend/routes/quote_transitions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "fiscal_printer_model: str = None" in content
    assert 'project["fiscal_printer_model"]' in content


def test_send_to_implementation_accepts_fiscal_printer_model():
    """El payload SendToImplementationRequest debe aceptar fiscal_printer_model."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "fiscal_printer_model: Optional[str]" in content


def test_quote_filters_has_searchable_client_combobox():
    """QuoteFilters.jsx debe incluir el buscador predictivo de clientes."""
    with open("/app/frontend/src/components/quotes/QuoteFilters.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "ClientSearchableSelect" in content
    assert 'data-testid="filter-client-search"' in content


def test_quote_modals_has_fiscal_printer_phase_and_no_equipment_phase():
    """QuoteModals.jsx debe tener fase fiscal_printer y NO debe tener bloque equipment-phase."""
    with open("/app/frontend/src/components/quotes/QuoteModals.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "fiscal-printer-phase" in content
    assert "fiscal_printer" in content
    assert "equipment-phase" not in content, "Bloque equipment-phase debe estar removido"


def test_invoiced_exits_report_has_admin_modal():
    """InvoicedExitsReport debe incluir Modal admin y botón embebido condicional."""
    with open("/app/frontend/src/pages/InvoicedExitsReport.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "admin-edit-exit-modal" in content
    assert "isAdmin" in content
    assert "report-admin-tools-btn" in content
    assert "edit-exit-delete-btn" in content


def test_fiscal_printer_model_field_in_clients_route():
    """PATCH /clients/{id} debe aceptar modelo_impresora_fiscal."""
    with open("/app/backend/models.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "modelo_impresora_fiscal: Optional[str]" in content
