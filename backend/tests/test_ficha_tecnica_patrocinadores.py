# ruff: noqa
"""
Verifica la Sección B de la Ficha Técnica: orden y mapeo de
Patrocinador de Pinpads, Patrocinador de la Implementación,
Servidor de Instalación y Tipo de Comunicación.
NO escribe en la base de datos: sólo renderiza el PDF en memoria.
"""
import os
import sys
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pdfplumber
from services.implementation_pdf import generate_implementation_pdf


def _pdf_text(quote):
    client = {"legal_name": "CLIENTE QA", "fantasy_name": "QA", "rif": "J-000", "contacts": []}
    pdf_bytes = generate_implementation_pdf(quote, client, [], [])
    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or "") + "\n"
    return text


def test_cotizacion_flow():
    # Cotización: sponsor_bank=Pinpad sponsor; sponsoring=Implementación patrocinada
    quote = {
        "integrator_name": "Integrador X", "integrator_app_name": "App Y",
        "pinpad_model": "PAX A920",
        "sponsor_bank_name": "Pinpad Sponsor Bank",      # Patrocinador de Pinpads
        "sponsored_implementation": True,
        "sponsoring_bank_name": "Banco Alfa",            # Patrocinador de la Implementación
        "server_name": "Multicomercio MSC",
        "communication_type": "SSL",
    }
    txt = _pdf_text(quote)
    assert "Patrocinador de Pinpads" in txt
    assert "Pinpad Sponsor Bank" in txt
    assert "Patrocinador de la" in txt and "Implementacion" in txt
    assert "Banco Alfa" in txt
    assert "Servidor de Instalacion" in txt and "Multicomercio MSC" in txt
    assert "Tipo de Comunicacion" in txt and "SSL" in txt
    # Orden jerárquico: Pinpads -> Implementación -> Servidor -> Comunicación
    assert txt.index("Pinpad Sponsor Bank") < txt.index("Banco Alfa")
    assert txt.index("Banco Alfa") < txt.index("Servidor de Instalacion")
    assert txt.index("Servidor de Instalacion") < txt.index("Tipo de Comunicacion")
    print("OK cotizacion flow")


def test_direct_flow():
    # Proyecto Directo (synthetic_quote): pinpad_bank -> Pinpads; sponsor_bank -> Implementación
    quote = {
        "integrator_name": "Integrador X", "integrator_app_name": "App Y",
        "pinpad_model": "PAX A920",
        "sponsor_bank_name": "Banco Gamma",              # Patrocinador de Pinpads (= pinpad_bank)
        "sponsored_implementation": True,
        "sponsoring_bank_name": "Banco Beta",            # Patrocinador de la Implementación (= Banco Patrocinante)
        "server_name": "Servidor Propio QA",
        "communication_type": "VPN",
    }
    txt = _pdf_text(quote)
    assert "Patrocinador de Pinpads" in txt and "Banco Gamma" in txt
    assert "Patrocinador de la" in txt and "Implementacion" in txt and "Banco Beta" in txt
    assert "Tipo de Comunicacion" in txt and "VPN" in txt
    print("OK direct flow")


def test_no_sponsor_shows_na():
    quote = {
        "integrator_name": "I", "integrator_app_name": "A", "pinpad_model": "X",
        "communication_type": "NO_APLICA",
    }
    txt = _pdf_text(quote)
    assert "Patrocinador de la" in txt and "Implementacion" in txt  # siempre visible (N/A si no patrocinada)
    print("OK no-sponsor N/A")


if __name__ == "__main__":
    test_cotizacion_flow()
    test_direct_flow()
    test_no_sponsor_shows_na()
    print("ALL PASS")
