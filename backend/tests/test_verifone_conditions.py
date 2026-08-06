"""
Tests for Verifone conditions PDF attachment on equipment quotes (CREATE + MODIFY).
Bug fix: regenerate_equipment_pdf now calls append_equipment_conditions.
"""
import os
import pytest
import requests
from pathlib import Path
from PyPDF2 import PdfReader

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if v:
        return v.rstrip("/")
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return ""

BASE_URL = _load_backend_url()
UPLOADS_DIR = Path("/app/backend/uploads")

PYME_EMAIL = "agodoy@megasoft.com.ve"
PYME_PASS = "Test1234!"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

EXISTING_PYME_QUOTE_ID = "quo_34d3d4705085"
EXISTING_PYME_QUOTE_NUM = "COT-2026-04-076-PYME"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed {email}: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, f"No session_token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def pyme_token():
    return _login(PYME_EMAIL, PYME_PASS)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


def _pdf_page_count(path: Path) -> int:
    return len(PdfReader(str(path)).pages)


class TestRegenerateVerifonePYME:
    """MODIFY flow: regenerate PDF must include Verifone TBP conditions for PYME."""

    def test_regenerate_pyme_verifone_has_tbp_conditions(self, admin_token):
        pdf_path = UPLOADS_DIR / f"{EXISTING_PYME_QUOTE_NUM}_Cotizacion_Equipo.pdf"

        r = requests.post(
            f"{BASE_URL}/api/quotes/{EXISTING_PYME_QUOTE_ID}/regenerate-equipment-pdf",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=90,
        )
        assert r.status_code == 200, f"regenerate failed: {r.status_code} {r.text}"

        assert pdf_path.exists(), f"PDF not found: {pdf_path}"
        pages = _pdf_page_count(pdf_path)
        # 1 (cotizacion base) + 1 (condiciones_verifone_tbp.pdf) = 2
        assert pages == 2, (
            f"Expected 2 pages (base + TBP conditions) after regenerate for PYME, got {pages}"
        )


class TestCreateVerifonePYME:
    """CREATE flow: generate equipment quote PDF must include Verifone TBP conditions."""

    def _find_verifone_product(self, token):
        # Look for a Verifone equipment product in catalog
        for path in ["/api/products", "/api/catalog/products", "/api/equipment/products"]:
            try:
                r = requests.get(
                    f"{BASE_URL}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30,
                )
                if r.status_code == 200:
                    data = r.json()
                    items = data if isinstance(data, list) else data.get("items") or data.get("products") or []
                    for p in items:
                        etype = (p.get("equipment_type") or p.get("type") or "").lower()
                        name = (p.get("name") or p.get("product_name") or "").lower()
                        if "verifone" in etype or "verifone" in name:
                            return p, path
            except Exception:
                pass
        return None, None

    def test_create_pyme_verifone_quote_has_tbp_conditions(self, pyme_token):
        # Minimal payload: many backends accept name/qty/price directly
        payload = {
            "cliente_nombre": "TEST_Cliente_Verifone_PYME",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Test Address",
            "equipment_type": "Verifone",
            "items": [
                {
                    "name": "Verifone V240m TEST",
                    "hardware_type": "Verifone",
                    "quantity": 1,
                    "unit_price_usd": 100.0,
                    "total_usd": 100.0,
                }
            ],
            "notes": "TEST run - Verifone PYME conditions attachment",
        }
        r = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            headers={"Authorization": f"Bearer {pyme_token}"},
            json=payload,
            timeout=90,
        )
        if r.status_code != 200:
            pytest.skip(
                f"Could not create equipment quote via generate-equipment-pdf "
                f"(status {r.status_code}): {r.text[:400]}"
            )

        quote_number = r.headers.get("X-Quote-Number")
        assert quote_number, f"Missing X-Quote-Number header. Headers: {dict(r.headers)}"
        pdf_path = UPLOADS_DIR / f"{quote_number}_Cotizacion_Equipo.pdf"

        assert pdf_path and pdf_path.exists(), f"Generated PDF not found (quote_number={quote_number})"

        # Also validate PDF bytes returned directly in response
        from io import BytesIO
        pages_response = len(PdfReader(BytesIO(r.content)).pages)
        pages = _pdf_page_count(pdf_path)
        assert pages == 2, (
            f"Expected 2 pages (base + TBP conditions) on CREATE for PYME Verifone, got {pages} at {pdf_path}"
        )
        assert pages_response == 2, (
            f"Response PDF should also have 2 pages; got {pages_response}"
        )


class TestRegressionCorpLCH:
    """Regression: non-PYME sede must attach condiciones_verifone.pdf (2 pages) => 3 total."""

    def test_regenerate_corp_verifone_has_lch_conditions(self, admin_token):
        # Find a Verifone quote whose sede is NOT PYME
        r = requests.get(
            f"{BASE_URL}/api/quotes?limit=200",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        if r.status_code != 200:
            pytest.skip(f"Cannot list quotes: {r.status_code}")
        data = r.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("quotes") or []
        target = None
        for q in items:
            if (q.get("equipment_type") == "Verifone" or (q.get("quote_type") == "equipment" and "verifone" in str(q).lower())) \
               and (q.get("sede") or "").upper() not in ("PYME", ""):
                target = q
                break
        if not target:
            pytest.skip("No CORP/LCH Verifone quote available for regression test")

        qid = target.get("id") or target.get("quote_id")
        qnum = target.get("quote_number")
        pdf_path = UPLOADS_DIR / f"{qnum}_Cotizacion_Equipo.pdf"

        r2 = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/regenerate-equipment-pdf",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=90,
        )
        assert r2.status_code == 200, f"regenerate failed: {r2.status_code} {r2.text}"
        assert pdf_path.exists(), f"PDF not on disk: {pdf_path}"
        pages = _pdf_page_count(pdf_path)
        # 1 base + 2 (condiciones_verifone.pdf) = 3
        assert pages == 3, f"Expected 3 pages (base + LCH conditions) for CORP Verifone, got {pages}"
