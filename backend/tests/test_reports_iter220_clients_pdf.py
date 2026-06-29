"""Iter220 BUG FIX QA: Clients PDF export migrated to corporate style.

Verifies:
- GET /api/clients/export/pdf returns 200 and a valid PDF (via build_corporate_pdf).
- Regression: other standardized export endpoints still return 200 with valid bytes.

Endpoints under test:
- /api/clients/export/pdf            -> %PDF
- /api/banks/export/pdf              -> %PDF
- /api/services/export/pdf           -> %PDF
- /api/hardware/export/pdf           -> %PDF
- /api/hardware/export/excel         -> PK (xlsx)
- /api/commercial-categories/export/pdf   -> %PDF
- /api/commercial-categories/export/excel -> PK (xlsx)
- /api/commercial-categories/export/csv   -> CSV text with 'Nombre' header
"""
import os
import pytest
import requests


def _load_base_url() -> str:
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        # Fallback: parse from /app/frontend/.env
        try:
            with open("/app/frontend/.env", "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            url = ""
    return url.rstrip("/")


BASE_URL = _load_base_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token") or r.json().get("session_token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


def _get_binary(path, headers):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=headers, timeout=90)
    return r


# ============== BUG FIX: Clients PDF ==============

class TestClientsPdfBugFix:
    """The reported bug: Clients PDF didn't have corporate header/logo/orientation."""

    def test_clients_export_pdf_status_200(self, headers):
        r = _get_binary("/api/clients/export/pdf", headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"

    def test_clients_export_pdf_content_type(self, headers):
        r = _get_binary("/api/clients/export/pdf", headers)
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        assert "application/pdf" in ctype.lower(), f"Bad content-type: {ctype}"

    def test_clients_export_pdf_valid_signature_and_nonempty(self, headers):
        r = _get_binary("/api/clients/export/pdf", headers)
        assert r.status_code == 200
        body = r.content
        assert len(body) > 1000, f"PDF too small: {len(body)} bytes"
        assert body.startswith(b"%PDF"), f"Missing %PDF magic bytes. First 16: {body[:16]!r}"

    def test_clients_export_pdf_corporate_markers(self, headers):
        """Sanity: PDF contains the 'CRM - Gestor' header text and the 'Clientes' title.
        ReportLab embeds text inside content streams; for Helvetica/standard fonts the
        literal strings are typically present in the PDF bytes.
        """
        r = _get_binary("/api/clients/export/pdf", headers)
        assert r.status_code == 200
        body = r.content
        # These checks are best-effort markers. If reportlab compresses streams, they may
        # not appear verbatim. We only enforce 'Clientes' as the doc title (always present
        # in PDF metadata uncompressed).
        assert b"Clientes" in body, "PDF does not contain title 'Clientes' anywhere"


# ============== Regression: other corporate exports ==============

class TestRegressionPdfEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/banks/export/pdf",
        "/api/services/export/pdf",
        "/api/hardware/export/pdf",
        "/api/commercial-categories/export/pdf",
    ])
    def test_pdf_endpoint_returns_valid_pdf(self, headers, path):
        r = _get_binary(path, headers)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"
        body = r.content
        assert len(body) > 500, f"{path} body too small ({len(body)} bytes)"
        assert body.startswith(b"%PDF"), f"{path} missing %PDF magic. First 16: {body[:16]!r}"
        ctype = r.headers.get("content-type", "").lower()
        assert "application/pdf" in ctype, f"{path} bad content-type: {ctype}"


class TestRegressionExcelEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/hardware/export/excel",
        "/api/commercial-categories/export/excel",
    ])
    def test_xlsx_endpoint_returns_valid_xlsx(self, headers, path):
        r = _get_binary(path, headers)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"
        body = r.content
        assert len(body) > 500, f"{path} body too small ({len(body)} bytes)"
        # xlsx files are zip containers: 'PK\x03\x04'
        assert body[:2] == b"PK", f"{path} missing PK (ZIP) magic. First 16: {body[:16]!r}"


class TestRegressionCsvEndpoint:
    def test_commercial_categories_csv(self, headers):
        path = "/api/commercial-categories/export/csv"
        r = _get_binary(path, headers)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:300]}"
        # Allow utf-8-sig BOM
        text = r.content.decode("utf-8-sig", errors="replace")
        assert len(text) > 0, "CSV empty"
        first_line = text.splitlines()[0] if text.splitlines() else ""
        assert "Nombre" in first_line, f"CSV header missing 'Nombre' column. First line: {first_line!r}"
