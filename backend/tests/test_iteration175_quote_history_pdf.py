"""Retest PDF fix for /api/quote-history/{id}/pdf across all categories.

Validates fix in /app/backend/routes/quote_history.py where download_quote_history_pdf
now dispatches by quote_category:
- equipment/repair -> regenerate_equipment_pdf + FileResponse
- fast_track/implementation -> generate_quote_pdf (binary Response)

Expected:
- 200 OK + Content-Type application/pdf (or first 4 bytes '%PDF')
- Never 500 or JSON
- Without auth: 401/403
"""
import os
import pytest
import requests

from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Avila*0426"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    tok = body.get("session_token") or body.get("access_token") or body.get("token")
    assert tok, f"No token in login response: {list(body.keys())}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def history_rows(admin_headers):
    r = requests.get(f"{BASE_URL}/api/quote-history", headers=admin_headers, timeout=30)
    assert r.status_code == 200, f"List failed: {r.status_code} {r.text[:200]}"
    rows = r.json()
    assert isinstance(rows, list) and len(rows) >= 1, f"Expected archived quotes, got {len(rows) if isinstance(rows, list) else rows}"
    return rows


def _assert_pdf_response(r, label):
    assert r.status_code == 200, f"[{label}] Expected 200, got {r.status_code}. Body (first 300): {r.text[:300]}"
    ctype = r.headers.get("content-type", "").lower()
    # Must be application/pdf, never JSON
    assert "application/pdf" in ctype, f"[{label}] Expected application/pdf, got '{ctype}'. Body[:200]={r.content[:200]!r}"
    assert "json" not in ctype, f"[{label}] Got JSON content-type: {ctype}"
    # Magic bytes
    assert r.content[:4] == b"%PDF", f"[{label}] Missing %PDF magic. First bytes: {r.content[:8]!r}"
    # Reasonable size
    assert len(r.content) > 500, f"[{label}] PDF too small: {len(r.content)} bytes"


class TestQuoteHistoryPDFByCategory:
    """Download PDF for each available category and assert binary PDF response."""

    def test_pdf_for_all_existing_history_rows(self, admin_headers, history_rows):
        """Iterate every archived quote and verify 200 + application/pdf."""
        failures = []
        categories_seen = set()
        for row in history_rows:
            hid = row["history_id"]
            cat = row.get("quote_category", "implementation")
            categories_seen.add(cat)
            r = requests.get(
                f"{BASE_URL}/api/quote-history/{hid}/pdf",
                headers=admin_headers,
                timeout=90,
            )
            try:
                _assert_pdf_response(r, f"{cat}:{hid}")
            except AssertionError as e:
                failures.append(str(e))
        assert not failures, "PDF download failures:\n" + "\n".join(failures)
        print(f"[PDF test] Categories covered: {sorted(categories_seen)}")

    @pytest.mark.parametrize("category", ["equipment", "repair", "fast_track", "implementation"])
    def test_pdf_per_category_if_available(self, admin_headers, history_rows, category):
        """For each of the 4 categories, if at least one archived quote exists, PDF must be binary."""
        candidates = [r for r in history_rows if r.get("quote_category") == category]
        if not candidates:
            pytest.skip(f"No archived quotes of category={category}")
        row = candidates[0]
        hid = row["history_id"]
        r = requests.get(
            f"{BASE_URL}/api/quote-history/{hid}/pdf",
            headers=admin_headers,
            timeout=90,
        )
        _assert_pdf_response(r, f"{category}:{hid}")

    def test_pdf_no_auth_returns_401_or_403(self, history_rows):
        """Without auth header, endpoint must return 401/403, never 200 PDF or 500."""
        hid = history_rows[0]["history_id"]
        r = requests.get(f"{BASE_URL}/api/quote-history/{hid}/pdf", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403 without auth, got {r.status_code} body={r.text[:200]}"

    def test_pdf_bogus_token_returns_401_or_403(self, history_rows):
        hid = history_rows[0]["history_id"]
        r = requests.get(
            f"{BASE_URL}/api/quote-history/{hid}/pdf",
            headers={"Authorization": "Bearer invalid.token.value"},
            timeout=20,
        )
        assert r.status_code in (401, 403), f"Expected 401/403 with bogus token, got {r.status_code}"

    def test_pdf_not_found_returns_404(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/quote-history/qhist_DOES_NOT_EXIST/pdf",
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 404, f"Expected 404 for non-existent history, got {r.status_code}"
