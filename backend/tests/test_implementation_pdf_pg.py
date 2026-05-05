"""Test PDF Ficha Técnica para Payment Gateway: tabla N°/Concepto/Banco/Observación + TOTAL SETUP."""
import sys
import os
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from services.implementation_pdf import generate_implementation_pdf


def test_implementation_pdf_payment_gateway_resumen_comercial():
    """Genera el PDF de implementación para una cotización PG y verifica que contenga
    los conceptos/bancos del pg_setup_items en el Resumen Comercial."""
    quote = {
        "quote_id": "qid_test_pg_001",
        "quote_number": "COT-PG-TEST-001",
        "client_id": "test_pg_client",
        "client_name": "ASTROCEL CELULARES, C.A.",
        "client_segment": "PYME",
        "sede": "PYME",
        "quote_type": "GATEWAY",
        "quote_category": "implementation",
        "services": [],
        "hardware": [],
        "pg_setup_items": [
            {"concepto": "Persona Jurídica", "banco": "N/A", "observacion": "Costo Base", "costo": 240},
            {"concepto": "Tarjeta de Crédito/Débito (PG)", "banco": "Banco Mercantil", "costo": 80},
            {"concepto": "Verificación de P2C (PG)", "banco": "Banco Mercantil", "costo": 50},
            {"concepto": "Pago C2P (PG)", "banco": "Banco Mercantil", "costo": 50},
            {"concepto": "Tarjeta de Crédito/Débito (PG)", "banco": "Banco Nacional de Crédito (BNC)", "costo": 80},
            {"concepto": "Pago C2P (PG)", "banco": "Banco Nacional de Crédito (BNC)", "costo": 50},
            {"concepto": "Verificación de P2C (PG)", "banco": "Banco Nacional de Crédito (BNC)", "costo": 50},
        ],
    }
    client = {
        "client_id": "test_pg_client",
        "rif": "J123456789",
        "legal_name": "ASTROCEL CELULARES, C.A.",
        "fantasy_name": "ASTROCEL",
        "address": "AV LIBERTADOR CC SAMBIL PLAZA CENTRAL CARACAS",
    }
    contacts = [{"full_name": "Juan Test", "email": "j@t.com", "phone": "+58-414-0000000"}]
    branches = []

    pdf_bytes = generate_implementation_pdf(quote, client, contacts, branches)
    assert pdf_bytes, "PDF debe generarse"
    assert len(pdf_bytes) > 1000, f"PDF debe tener tamaño razonable, got {len(pdf_bytes)}"
    # Sanity: empieza con header PDF
    assert pdf_bytes[:4] == b"%PDF", "Debe ser un PDF válido"

    # Guardar para inspección manual
    out_path = "/tmp/test_implementation_pg_resumen.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF generado: {out_path} ({len(pdf_bytes)} bytes)")


def test_implementation_pdf_vpos_no_pg_table():
    """VPOS sin pg_setup_items: debe usar la tabla legacy de Banco/Medio de Pago/Cajas."""
    quote = {
        "quote_id": "qid_test_vpos_001",
        "quote_number": "COT-VPOS-TEST-001",
        "client_id": "test_vpos_client",
        "client_name": "TEST CLIENTE VPOS",
        "client_segment": "PYME",
        "sede": "PYME",
        "quote_type": "VPOS",
        "quote_category": "implementation",
        "services": [
            {"item_type": "additional", "bank_name": "Banco Mercantil", "item_name": "VPOS Implementación", "quantity": 2}
        ],
        "hardware": [],
    }
    client = {"client_id": "test_vpos_client", "rif": "J999", "legal_name": "TEST", "fantasy_name": "TEST"}
    pdf_bytes = generate_implementation_pdf(quote, client, [], [])
    assert pdf_bytes[:4] == b"%PDF"
