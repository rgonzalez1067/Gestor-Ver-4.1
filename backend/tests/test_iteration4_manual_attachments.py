# ruff: noqa
"""Iteration 4 — Adjuntos manuales en modal 'Personalizar Comunicación'.

Covers:
- POST /api/quotes/manual-attachments/upload (PDF OK, 415 .exe, 400 vacío, 413 >10MB)
- Custom action endpoint acepta header x-manual-attachment-ids sin error 500
- Regresión: /api/quotes y /api/reports/sales/funnel/delivered_breakdown
"""
import os
import io
import pytest
import requests

_BACKEND = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND:
    # Read frontend/.env as fallback
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _BACKEND = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
assert _BACKEND, "REACT_APP_BACKEND_URL not set"
BASE_URL = _BACKEND.rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PWD = "admin123"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200, r.text
    token = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert token
    return {"Authorization": f"Bearer {token}"}


# ---------- Upload endpoint ----------
def test_upload_pdf_ok(auth_headers):
    pdf_bytes = b"%PDF-1.4\n%test pdf small\n%%EOF"
    files = {"file": ("test_TEST_dummy.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/quotes/manual-attachments/upload",
                      headers=auth_headers, files=files, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["attachment_id"].startswith("matt_")
    assert data["filename"] == "test_TEST_dummy.pdf"
    assert data["size"] == len(pdf_bytes)
    assert data["content_type"].startswith("application/pdf")


def test_upload_exe_rejected(auth_headers):
    files = {"file": ("malware_TEST.exe", io.BytesIO(b"MZ\x90\x00binarystuff"),
                      "application/x-msdownload")}
    r = requests.post(f"{BASE_URL}/api/quotes/manual-attachments/upload",
                      headers=auth_headers, files=files, timeout=30)
    assert r.status_code == 415, r.text


def test_upload_empty_400(auth_headers):
    files = {"file": ("empty_TEST.pdf", io.BytesIO(b""), "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/quotes/manual-attachments/upload",
                      headers=auth_headers, files=files, timeout=30)
    assert r.status_code == 400, r.text


def test_upload_too_large_413(auth_headers):
    big = b"\x00" * (11 * 1024 * 1024)
    files = {"file": ("big_TEST.pdf", io.BytesIO(big), "application/pdf")}
    r = requests.post(f"{BASE_URL}/api/quotes/manual-attachments/upload",
                      headers=auth_headers, files=files, timeout=60)
    assert r.status_code == 413, r.text


# ---------- Custom action accepts header ----------
def test_custom_action_endpoint_accepts_header(auth_headers):
    """Verifica que custom-action endpoint NO falle con 500 al pasar el header."""
    # Pick any quote
    r = requests.get(f"{BASE_URL}/api/quotes?limit=1", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    payload = r.json()
    quotes = payload if isinstance(payload, list) else payload.get("items") or payload.get("quotes") or []
    if not quotes:
        pytest.skip("No quotes to test custom action header propagation")
    quote_id = quotes[0]["quote_id"]

    # Upload a small dummy attachment first
    files = {"file": ("c_TEST.pdf", io.BytesIO(b"%PDF-1.4\nx\n%%EOF"), "application/pdf")}
    up = requests.post(f"{BASE_URL}/api/quotes/manual-attachments/upload",
                       headers=auth_headers, files=files, timeout=30)
    assert up.status_code == 200
    matt_id = up.json()["attachment_id"]

    # Call custom-action with a likely non-existent action id; the header path
    # must not cause an HTTP 500. Acceptable: 200/4xx/422; we reject 500.
    headers = dict(auth_headers)
    headers["x-manual-attachment-ids"] = matt_id
    r = requests.post(
        f"{BASE_URL}/api/quotes/{quote_id}/custom-action/nonexistent_action_TEST",
        headers=headers, timeout=30)
    assert r.status_code != 500, f"Internal server error w/ header: {r.text}"


# ---------- Regression ----------
def test_quotes_list_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items") or payload.get("quotes") or []
    assert isinstance(items, list)


def test_funnel_delivered_breakdown_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/reports/sales/funnel",
                     headers=auth_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "delivered_breakdown" in data
    db_ = data["delivered_breakdown"]
    for k in ("implementaciones", "equipos", "reparaciones"):
        assert k in db_


def test_auth_login_regression():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200
    assert r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
