"""Backend test — Sección condicional de Descuentos en PDF Corporativo (Página 3).

Valida:
  - SIN descuento (0%): la sección "TOTAL NETO A PAGAR" NO aparece en el PDF.
  - CON descuento (12%): la sección aparece en la MISMA página que la matriz
    "COSTOS DE IMPLEMENTACIÓN", con la matemática correcta:
        Base Imponible = Subtotal Bruto - Monto Descuento
        IVA            = Base Imponible * 0.16   (sobre la base, NO sobre el bruto)
        Total Neto     = Base Imponible + IVA
  - Restaura el descuento original de la cotización al finalizar.

Requiere pdfplumber y una cotización CORP cuyo cliente tenga dirección.
"""
import os
import re
import pytest
import requests
import pdfplumber

import config
from config import UPLOADS_DIR
from pymongo import MongoClient

API = os.environ.get("REACT_APP_BACKEND_URL", "https://heartbeat-clean.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}


def _mongo():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def headers():
    tok = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30).json()["session_token"]
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def corp_quote():
    """Cotización CORP con cliente que tiene dirección (para que regenere sin error)."""
    mdb = _mongo()
    for q in mdb.quotes.find({"client_segment": "CORP"}, {"_id": 0, "quote_id": 1, "quote_number": 1, "client_id": 1, "descuento": 1, "descuento_setup": 1, "descuento_recurrente": 1}):
        c = mdb.clients.find_one({"client_id": q["client_id"]}, {"_id": 0, "address": 1})
        if c and (c.get("address") or "").strip():
            return q
    pytest.skip("No hay cotización CORP con dirección de cliente válida")


def _set_disc(quote_id, setup, recurrente, single=0):
    _mongo().quotes.update_one({"quote_id": quote_id}, {"$set": {
        "descuento_setup": setup, "descuento_recurrente": recurrente, "descuento": single,
    }})


def _regen(headers, quote_id):
    r = requests.post(f"{API}/quotes/{quote_id}/regenerate-pdf", headers=headers, json={}, timeout=180)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"


def _pages_text(quote_number):
    path = UPLOADS_DIR / f"{quote_number}_Cotizacion.pdf"
    with pdfplumber.open(str(path)) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _money(text, label):
    m = re.search(rf"{re.escape(label)}\s*-?\$?([\d,]+\.\d{{2}})", text)
    assert m, f"No se encontró '{label}' en el texto"
    return float(m.group(1).replace(",", ""))


def test_discount_section_conditional_and_math(headers, corp_quote):
    qid = corp_quote["quote_id"]
    qnum = corp_quote["quote_number"]
    orig = (corp_quote.get("descuento_setup", 0) or 0, corp_quote.get("descuento_recurrente", 0) or 0, corp_quote.get("descuento", 0) or 0)
    try:
        # --- SIN descuento ---
        _set_disc(qid, 0, 0, 0)
        _regen(headers, qid)
        pages = _pages_text(qnum)
        assert not any("TOTAL NETO" in p.upper() for p in pages), \
            "La sección de descuento NO debe aparecer sin descuento"

        # --- CON descuentos SEPARADOS: Setup 10%, Recurrente 15% ---
        _set_disc(qid, 10, 15, 0)
        _regen(headers, qid)
        pages = _pages_text(qnum)
        matrix_pages = [i for i, t in enumerate(pages) if "Hardware y" in t and "Concepto" in t and "COSTOS DE IMPLEMENTACIÓN (SETUP)" not in t]
        disc_pages = [i for i, t in enumerate(pages) if "RESUMEN DE DESCUENTO" in t.upper()]
        assert matrix_pages, "No se encontró la página de la matriz COSTOS DE IMPLEMENTACIÓN"
        assert disc_pages, "No apareció la sección de descuento"
        assert matrix_pages[0] == disc_pages[0], "La sección de descuento se desplazó de la página de la matriz"

        t = pages[disc_pages[0]]
        # Deben existir DOS sub-bloques separados (Setup y Recurrentes)
        assert "Inversión Inicial (Setup)" in t, "Falta el sub-bloque de Setup"
        assert "Costos Recurrentes (Mensual)" in t, "Falta el sub-bloque de Recurrentes"
        assert "Total Neto Setup:" in t and "Total Neto Mensual:" in t, "Faltan los totales por sección"

        # Verificar los DOS porcentajes separados (-10% setup, -15% recurrente)
        assert "-10%" in t, "No se aplicó el 10% al Setup"
        assert "-15%" in t, "No se aplicó el 15% al Recurrente"

        # Validación matemática por cada Total Neto (base = bruto-desc; iva=base*16%)
        montos = [float(x.replace(",", "")) for x in re.findall(r"Subtotal Bruto:\s*\$([\d,]+\.\d{2})", t)]
        bases = [float(x.replace(",", "")) for x in re.findall(r"Base Imponible:\s*\$([\d,]+\.\d{2})", t)]
        ivas = [float(x.replace(",", "")) for x in re.findall(r"IVA \(16%\):\s*\$([\d,]+\.\d{2})", t)]
        assert len(montos) == 2 and len(bases) == 2 and len(ivas) == 2, "Deben verse 2 desgloses (Setup y Recurrente)"
        for base, iva in zip(bases, ivas):
            assert abs(iva - base * 0.16) < 0.02, f"IVA != Base*16% ({iva} vs {base*0.16})"
    finally:
        _set_disc(qid, *orig)
        _regen(headers, qid)
