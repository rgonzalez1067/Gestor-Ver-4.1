"""
Iter33 — Validate the two production-reported quote creation bugs:
- POST /api/quotes/generate-equipment-pdf (Reparaciones) with repair_models
- POST /api/quotes/create-with-pdf (Payment Gateway, quote_type=GATEWAY)
- Regression: Reparaciones legacy (bulk_serials / single serial) without repair_models
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-impl-filter.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
CLIENT_ID = "cli_d7a6037a7cf7"  # ASTROCEL CELULARES
INTEGRATOR_ID = "int_7c555185aa22"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tk = r.json().get("token") or r.json().get("access_token") or r.json().get("session_token")
    assert tk, f"No token in response: {r.json()}"
    return tk


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _equip_payload_with_repair_models():
    return {
        "client_id": CLIENT_ID,
        "cliente_nombre": "ASTROCEL CELULARES, C.A.",
        "cliente_rif": "J-00000000-0",
        "equipment_type": "Reparación",
        "items": [
            {
                "name": "Reparación de Pinpad",
                "hardware_type": "Pinpad",
                "quantity": 3,
                "unit_price_usd": 50.0,
                "total_usd": 150.0,
                "serials": [],
            }
        ],
        "repair_description": "Equipos con falla de pantalla y teclado, requiere diagnóstico.",
        "repair_models": [
            {"model_name": "Morefun R90", "quantity": 2, "serials": ["RM001", "RM002"]},
            {"model_name": "Newland N910", "quantity": 1, "serials": ["NL001"]},
        ],
    }


def _equip_payload_legacy_bulk():
    return {
        "client_id": CLIENT_ID,
        "cliente_nombre": "ASTROCEL CELULARES, C.A.",
        "cliente_rif": "J-00000000-0",
        "equipment_type": "Reparación",
        "items": [
            {
                "name": "Reparación general",
                "hardware_type": "Pinpad",
                "quantity": 2,
                "unit_price_usd": 40.0,
                "total_usd": 80.0,
                "serials": [],
            }
        ],
        "repair_description": "Falla en cargador y pantalla.",
        "bulk_serials": ["LEG001", "LEG002"],
    }


def _gateway_payload():
    return {
        "client_id": CLIENT_ID,
        "client_name": "ASTROCEL CELULARES, C.A.",
        "client_rif": "J-00000000-0",
        "integrator_id": INTEGRATOR_ID,
        "quote_category": "service",
        "quote_type": "GATEWAY",
        "services": [],
        "hardware": [],
        "equipment_items": [],
        "iva_exempt": False,
        "exchange_rate": 40.0,
        "pg_setup_items": [
            {
                "banco": "Banco de Venezuela",
                "medio_pago": "Tarjeta de Crédito",
                "costo": 250.0,
                "descripcion": "Setup PG Tarjeta de Crédito"
            }
        ],
        "pg_recurrent_basic": [],
        "pg_recurrent_other": [],
    }


# ---------- TESTS ----------

class TestReparacionesWithRepairModels:
    def test_generate_pdf_with_repair_models(self, headers):
        """The bug: NameError {total_units} -> fixed to {_total_units}.
        Must return 200 + application/pdf when repair_models are sent."""
        r = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=_equip_payload_with_repair_models(),
            headers=headers,
            timeout=60,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"Expected application/pdf, got {ct}; body[:200]={r.content[:200]}"
        assert len(r.content) > 1000, f"PDF too small: {len(r.content)} bytes"
        assert r.content[:4] == b"%PDF", f"Not a PDF: starts with {r.content[:8]}"


class TestReparacionesLegacy:
    def test_generate_pdf_legacy_bulk_serials(self, headers):
        """Regression: legacy path (bulk_serials, no repair_models) must still work."""
        r = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=_equip_payload_legacy_bulk(),
            headers=headers,
            timeout=60,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"


class TestPaymentGatewayQuote:
    def test_create_pg_quote(self, headers):
        """Payment Gateway quote creation must return 2xx and include a quote_number."""
        r = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=_gateway_payload(),
            headers=headers,
            timeout=60,
        )
        assert r.status_code in (200, 201), f"Expected 2xx, got {r.status_code}: {r.text[:800]}"
        data = r.json()
        quote = data.get("quote") or data
        assert quote.get("quote_number") or quote.get("quote_id"), f"Missing quote_number/id: {data}"
        print(f"PG Quote created: quote_number={quote.get('quote_number')}, id={quote.get('quote_id')}")
