"""
Iter263 — Endpoint GET /api/quotes/{id}/tokenizador-billing-line

Valida el condicional de 'Configuración del Tokenizador' para cotizaciones
Link de Pago según link_pago_variant.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inbox-fixes.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

QUOTE_LINKPAGO = "quo_4493ae3aea8d"   # COT-2026-07-056-PYME, variant=link_pago
QUOTE_AMBOS = "quo_228bc3a17586"      # COT-2026-07-058-PYME, variant=ambos


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def test_link_pago_variant_returns_applies_false(hdr):
    r = requests.get(f"{BASE_URL}/api/quotes/{QUOTE_LINKPAGO}/tokenizador-billing-line", headers=hdr, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("applies") is False, f"variant=link_pago debe devolver applies:false, got {data}"


def test_ambos_variant_returns_applies_true_150(hdr):
    r = requests.get(f"{BASE_URL}/api/quotes/{QUOTE_AMBOS}/tokenizador-billing-line", headers=hdr, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("applies") is True
    assert data.get("found") is True
    assert data.get("concepto") == "Configuración del Tokenizador"
    assert float(data.get("monto_usd") or 0) == 150.0, f"esperado 150.0 got {data.get('monto_usd')}"


def test_nonexistent_quote_returns_404(hdr):
    r = requests.get(f"{BASE_URL}/api/quotes/quo_does_not_exist_zzz/tokenizador-billing-line", headers=hdr, timeout=20)
    assert r.status_code == 404


def test_unauthenticated_rejected():
    r = requests.get(f"{BASE_URL}/api/quotes/{QUOTE_AMBOS}/tokenizador-billing-line", timeout=20)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


def test_gateway_quote_returns_applies_false(hdr):
    """Regresión: cualquier cotización NO LINK_PAGO debe devolver applies:false."""
    # Buscar una cotización GATEWAY
    r = requests.get(f"{BASE_URL}/api/quotes", headers=hdr, timeout=30)
    assert r.status_code == 200
    payload = r.json()
    quotes = payload if isinstance(payload, list) else payload.get("quotes") or payload.get("data") or []
    gw = next((q for q in quotes if (q.get("quote_type") or "").upper() == "GATEWAY"), None)
    if not gw:
        pytest.skip("No GATEWAY quote found for regression check")
    qid = gw.get("quote_id") or gw.get("id")
    r2 = requests.get(f"{BASE_URL}/api/quotes/{qid}/tokenizador-billing-line", headers=hdr, timeout=20)
    assert r2.status_code == 200
    assert r2.json().get("applies") is False
