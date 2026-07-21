"""Tests for the Document Viewer/Download endpoint (iter 281).

Endpoint: GET /api/entity-documents/{document_id}/download

- With Authorization header + no query: 200, Content-Disposition=attachment.
- With ?inline=true&token=<session_token> (no header): 200, Content-Disposition=inline.
- Without any auth: 401.

We also exercise upload → download → delete round-trip with a small PDF.
"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://equipment-workflow-3.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


def _login() -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token") or r.json().get("session_token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def token() -> str:
    return _login()


@pytest.fixture(scope="module")
def auth_headers(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Minimal valid single-page PDF bytes
_MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000100 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%%EOF"
)


@pytest.fixture(scope="module")
def uploaded_doc(auth_headers):
    """Upload a small PDF and yield the created document, delete at the end."""
    files = {
        "file": ("TEST_Manual_Soporte_2026.pdf", io.BytesIO(_MINIMAL_PDF), "application/pdf"),
    }
    data = {
        "context": "INTEGRADORES",
        "name": "TEST_Manual_Soporte_2026",
        "description": "Documento de prueba automatizado iter281",
        "category": "General",
    }
    r = requests.post(f"{BASE_URL}/api/entity-documents/upload", headers=auth_headers, data=data, files=files, timeout=60)
    assert r.status_code == 200, f"Upload failed: {r.status_code} {r.text}"
    doc = r.json()
    assert doc.get("document_id"), f"No document_id in response: {doc}"
    assert doc.get("filename") == "TEST_Manual_Soporte_2026.pdf"
    yield doc
    # cleanup
    try:
        requests.delete(f"{BASE_URL}/api/entity-documents/{doc['document_id']}", headers=auth_headers, timeout=30)
    except Exception:
        pass


class TestEntityDocumentDownload:
    def test_download_with_header_returns_attachment(self, uploaded_doc, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/entity-documents/{uploaded_doc['document_id']}/download",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        cd = r.headers.get("Content-Disposition", "")
        assert cd.lower().startswith("attachment"), f"Expected attachment, got: {cd}"
        assert "TEST_Manual_Soporte_2026.pdf" in cd or "Manual_Soporte_2026" in cd
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
        assert len(r.content) == len(_MINIMAL_PDF)

    def test_download_inline_with_token_query(self, uploaded_doc, token):
        """Simulates iframe/img request: no Authorization header, only ?token=&inline=true."""
        r = requests.get(
            f"{BASE_URL}/api/entity-documents/{uploaded_doc['document_id']}/download",
            params={"inline": "true", "token": token},
            timeout=30,
        )
        assert r.status_code == 200
        cd = r.headers.get("Content-Disposition", "")
        assert cd.lower().startswith("inline"), f"Expected inline, got: {cd}"
        assert r.content.startswith(b"%PDF")

    def test_download_without_auth_returns_401(self, uploaded_doc):
        r = requests.get(
            f"{BASE_URL}/api/entity-documents/{uploaded_doc['document_id']}/download",
            timeout=30,
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"

    def test_download_invalid_token_returns_401(self, uploaded_doc):
        r = requests.get(
            f"{BASE_URL}/api/entity-documents/{uploaded_doc['document_id']}/download",
            params={"inline": "true", "token": "invalid_bad_token_xxx"},
            timeout=30,
        )
        assert r.status_code == 401

    def test_download_nonexistent_document_returns_404(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/entity-documents/edoc_doesnotexist999/download",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 404

    def test_list_documents_includes_uploaded(self, uploaded_doc, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/entity-documents",
            params={"context": "INTEGRADORES"},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        ids = [d.get("document_id") for d in r.json()]
        assert uploaded_doc["document_id"] in ids
