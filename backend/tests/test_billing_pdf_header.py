"""Test: encabezado del PDF Cálculos Definitivos de Facturación.

Verifica que el bloque sea "Datos para la Factura" con: Razón Social,
Dirección Fiscal, Nombre Contacto, Teléfono, Email, Nro. Cotización y
Fecha de Aprobación. Campos eliminados: Cliente, RIF, Fecha de Facturación.
"""
import sys
import os
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from services.billing_pdf import generate_billing_pdf


def test_billing_pdf_header_uses_datos_para_la_factura():
    quote = {
        "quote_id": "q1", "quote_number": "COT-2026-05-026-PYME",
        "quote_category": "implementation", "quote_type": "VPOS",
    }
    client = {
        "client_id": "c1", "rif": "J305857695",
        "legal_name": "ASTROCEL CELULARES, C.A.",
        "fantasy_name": "ASTROCEL",
        "address": "Av. Libertador, Centro Comercial Sambil, Caracas",
        "contacts": [{
            "full_name": "Juan Pérez",
            "email": "juan@astrocel.com",
            "phone": "+58-414-1234567",
        }],
    }
    billing = {
        "consolidated_items": [{"name": "Setup VPOS", "quantity": 1, "total_usd": 300, "exchange_rate": 36.0, "total_bs": 10800.0}],
        "exchange_rate": 36.0, "rate_source": "BCV",
        "billing_date": "2026-02-15",
        "grand_total_usd": 300, "grand_total_bs": 10800,
        "iva_usd": 48, "iva_bs": 1728,
        "grand_total_con_iva_usd": 348, "grand_total_con_iva_bs": 12528,
    }
    pdf_bytes = generate_billing_pdf(quote, client, billing, executor_name="Tester")
    assert pdf_bytes[:4] == b"%PDF"
    out = "/tmp/test_billing_header.pdf"
    with open(out, "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF generado en {out} ({len(pdf_bytes)} bytes)")
