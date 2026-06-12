"""
Regresión: la Ficha Técnica de Implementación descargada desde el Proyecto
(endpoint GET /projects/{id}/ficha-tecnica) debe incluir el Resumen Ejecutivo
con la tabla de Bancos/Productos.

Bug original: download_ficha_tecnica construía `quote_like` desde la cotización
origen pero NO copiaba `services`/`pg_setup_items`. En Proyectos Directos el
quote_id es ficticio (no existe en `quotes`), por lo que `quote_like` quedaba sin
`services` y la tabla salía vacía.
"""
import io
from services.implementation_pdf import generate_implementation_pdf
from pdfminer.high_level import extract_text


def _client():
    return {"address": "AV TEST 123", "contacts": []}


def _vpos_quote_like_with_services():
    return {
        "quote_number": "PRY-TEST-001",
        "quote_type": "VPOS",
        "cantidad_cajas": 10,
        "client_name": "CLIENTE TEST C.A.",
        "services": [
            {"item_type": "additional", "item_name": "Tarjeta de Crédito/Débito", "bank_name": "Bancamiga", "quantity": 10},
            {"item_type": "additional", "item_name": "Pago con C2P", "bank_name": "Bancamiga", "quantity": 10},
            {"item_type": "additional", "item_name": "CASHEA", "bank_name": "Cashea", "quantity": 3},
        ],
        "pg_setup_items": [],
    }


def test_ficha_includes_bank_product_table():
    quote_like = _vpos_quote_like_with_services()
    pdf = generate_implementation_pdf(quote_like, _client(), [], [{"store_name": "Centro", "quantity": 10}])
    txt = extract_text(io.BytesIO(pdf))
    assert "RESUMEN COMERCIAL" in txt
    # La tabla de Bancos/Productos debe estar presente
    assert "Bancamiga" in txt
    assert "Cashea" in txt
    assert "Tarjeta de Crédito" in txt
    assert "Medio de Pago" in txt


def test_ficha_empty_services_still_renders_without_crash():
    """Si no hay services, no debe romper la generación (solo omite la tabla)."""
    quote_like = _vpos_quote_like_with_services()
    quote_like["services"] = []
    pdf = generate_implementation_pdf(quote_like, _client(), [], [])
    txt = extract_text(io.BytesIO(pdf))
    assert "RESUMEN COMERCIAL" in txt


def test_gateway_ficha_uses_pg_setup_items():
    quote_like = {
        "quote_number": "PRY-TEST-PG",
        "quote_type": "GATEWAY",
        "cantidad_cajas": 1,
        "client_name": "CLIENTE PG C.A.",
        "services": [],
        "pg_setup_items": [
            {"concepto": "Persona Jurídica", "banco": "N/A", "costo": 240, "observacion": "Costo Base"},
            {"concepto": "Tarjeta de Crédito/Débito (PG)", "banco": "Banco Mercantil", "costo": 60, "observacion": ""},
        ],
    }
    pdf = generate_implementation_pdf(quote_like, _client(), [], [])
    txt = extract_text(io.BytesIO(pdf))
    assert "RESUMEN COMERCIAL" in txt
    assert "Persona" in txt
    assert "Mercantil" in txt
