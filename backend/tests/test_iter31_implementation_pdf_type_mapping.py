"""Iter31 — Validar mapeo 'Tipo de Proyecto' en Ficha Técnica PDF.

Reglas:
  - VPOS              -> 'VPOS'
  - MPOS / FAST_TRACK -> 'MPOS'  (consolidado, sin "VPOS / MPOS")
  - GATEWAY           -> 'Payment Gateway'
  - LINK_PAGO / LINK  -> 'Link de Pago'
  - VPOS_MPOS legacy  -> 'VPOS'
"""
import io
import sys
import os
import pytest

sys.path.insert(0, "/app/backend")

from services.implementation_pdf import generate_implementation_pdf  # noqa: E402

try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader  # type: ignore


CLIENT = {
    "client_id": "cli_test",
    "legal_name": "TEST Cliente SA",
    "fantasy_name": "TEST",
    "rif": "J123456789",
    "address": "Av. Test",
    "iva_exempt": False,
}
CONTACTS = [{"full_name": "T", "role": "Ops", "phone": "x", "email": "t@t"}]
BRANCHES = [{"store_name": "Suc 1", "quantity": 1}]


def _build_quote(qtype: str) -> dict:
    return {
        "quote_number": "TEST-001",
        "quote_type": qtype,
        "cantidad_cajas": 1,
        "economic_group": "TEST",
        "fantasy_name": "TEST",
        "services": [
            {"item_type": "additional", "bank_name": "Banco X", "item_name": "Prod", "quantity": 1}
        ],
        "pg_setup_items": [],
        "pinpad_serials": [{"modelo": "Pax A50", "serial": "S001"}],
        "equipments": [],
    }


def _pdf_text(quote: dict) -> str:
    pdf = generate_implementation_pdf(quote, CLIENT, CONTACTS, BRANCHES)
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


@pytest.mark.parametrize("qtype,expected,must_not", [
    ("VPOS", "VPOS", "VPOS / MPOS"),
    ("MPOS", "MPOS", "VPOS / MPOS"),
    ("FAST_TRACK", "MPOS", "VPOS / MPOS"),
    ("GATEWAY", "Payment Gateway", "VPOS / MPOS"),
    ("LINK_PAGO", "Link de Pago", "VPOS / MPOS"),
    ("LINK", "Link de Pago", "VPOS / MPOS"),
    ("VPOS_MPOS", "VPOS", "VPOS / MPOS"),
])
def test_tipo_de_proyecto_mapping(qtype, expected, must_not):
    text = _pdf_text(_build_quote(qtype))
    # Tipo de Proyecto: <expected> debe aparecer
    # (extract_text puede romper espacios; comprobamos substring tras "Tipo")
    # Para FAST_TRACK / VPOS_MPOS / MPOS no debe aparecer la cadena combinada vieja.
    assert must_not not in text, f"[{qtype}] PDF aún contiene '{must_not}' (combinado legacy)"
    # Validar etiqueta + valor en alguna parte
    # Algunos extractores meten saltos de línea entre label y value: buscamos substring del valor
    # tras la palabra "Tipo" para asegurar contexto.
    idx = text.find("Tipo")
    assert idx >= 0, "No se encontró la etiqueta 'Tipo de Proyecto' en el PDF"
    window = text[idx:idx + 200]
    assert expected in window, (
        f"[{qtype}] Esperaba '{expected}' cerca de 'Tipo de Proyecto', "
        f"obtuve: {window!r}"
    )


def test_mpos_pdf_has_no_legacy_combined_label():
    """Regresión específica: el viejo label 'VPOS / MPOS' no debe aparecer en MPOS."""
    text = _pdf_text(_build_quote("MPOS"))
    assert "VPOS / MPOS" not in text
    assert "MPOS" in text
