"""
Iter262 — Backend tests for CORP Billing Matrix endpoint
GET /api/quotes/{quote_id}/corp-billing-matrix

Requirements:
- CORP + VPOS/VPOS_MULTIRIF/MPOS/FAST_TRACK -> eligible:true + matrix data
- PYME quotes -> eligible:false
- Non-existent quote -> 404
- Matrix contains the 4 CORP_COLUMNS (Derecho de Uso, Infraestructura, Apoyo Técnico, Soporte y Monitoreo)
- COT-052 (quo_2ed5a92f607f) known values: setup DdU 12.2 / Apoyo 12.0; recurring DdU 10.05 / Infra 7.0 / Soporte 7.25
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://corp-pyme-sync.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "rgonzalez@megasoft.com.ve", "password": "admin123"},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Endpoint validation ---
class TestCorpBillingMatrixEndpoint:
    """GET /api/quotes/{id}/corp-billing-matrix"""

    def test_cot052_matrix_matches_expected_values(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/quotes/quo_2ed5a92f607f/corp-billing-matrix",
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["eligible"] is True
        assert data["columns"] == [
            "Derecho de Uso",
            "Infraestructura",
            "Apoyo Técnico",
            "Soporte y Monitoreo",
        ]
        setup = data["setup_by_corp"]
        rec = data["recurring_by_corp"]
        assert round(setup["Derecho de Uso"], 2) == 12.20
        assert round(setup["Apoyo Técnico"], 2) == 12.00
        assert round(rec["Derecho de Uso"], 2) == 10.05
        assert round(rec["Infraestructura"], 2) == 7.00
        assert round(rec["Soporte y Monitoreo"], 2) == 7.25
        # Totals coherent
        assert round(data["setup_total_usd"], 2) == round(sum(setup.values()), 2)
        assert round(data["recurring_total_usd"], 2) == round(sum(rec.values()), 2)

    def test_pyme_quote_returns_not_eligible(self, headers):
        # PYME FAST_TRACK COT-051 (quo_066ab2120a0d)
        r = requests.get(
            f"{BASE_URL}/api/quotes/quo_066ab2120a0d/corp-billing-matrix",
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json() == {"eligible": False}

    def test_non_existent_quote_returns_404(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/quotes/quo_does_not_exist_zz/corp-billing-matrix",
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 404

    def test_corp_vpos_054_eligible_with_all_columns(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/quotes/quo_e94860a13420/corp-billing-matrix",
            headers=headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["eligible"] is True
        for col in ["Derecho de Uso", "Infraestructura", "Apoyo Técnico", "Soporte y Monitoreo"]:
            assert col in data["setup_by_corp"]
            assert col in data["recurring_by_corp"]
        # Sanity: totals >= 0
        assert data["setup_total_usd"] >= 0
        assert data["recurring_total_usd"] >= 0

    def test_endpoint_requires_auth(self):
        r = requests.get(
            f"{BASE_URL}/api/quotes/quo_2ed5a92f607f/corp-billing-matrix",
            timeout=30,
        )
        assert r.status_code in (401, 403)
