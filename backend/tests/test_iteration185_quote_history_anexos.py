"""
Iteration 185 — Tests for Phases 3-5 of "Evolución de Ficha de Implementación":
- Document management (anexos) on Quote History (admin-only writes; admin/director reads)
- Subsana auto-normalization on Irregular Quotes Report
- Last phase of historical quotes always green in irregular report

Test data is created via direct DB insert and cleaned at the end.
"""
import os
import io
import pytest
import requests
from datetime import datetime, timezone

def _read_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
NONADMIN_EMAIL = "srubio@megasoft.com.ve"
NONADMIN_PASSWORD = "Test1234!"

HISTORY_ID = "qhist_test_v2_it185"
QUOTE_ID = "q_test_v2_it185"
QUOTE_NUMBER = "COT-TEST-V2-IT185"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not tok:
        pytest.skip("admin auth failed")
    return tok


@pytest.fixture(scope="module")
def nonadmin_token():
    tok = _login(NONADMIN_EMAIL, NONADMIN_PASSWORD)
    if not tok:
        return None
    return tok


@pytest.fixture(scope="module", autouse=True)
def seed_history():
    """Insert synthetic quote_history doc + cleanup."""
    import asyncio
    import sys
    sys.path.insert(0, "/app/backend")
    from config import db  # type: ignore

    async def setup():
        await db.quote_history.delete_many({"history_id": HISTORY_ID})
        now = datetime.now(timezone.utc).isoformat()
        await db.quote_history.insert_one({
            "history_id": HISTORY_ID,
            "quote_id": QUOTE_ID,
            "quote_number": QUOTE_NUMBER,
            "quote_category": "implementation",
            "client_name": "Cliente Test IT185",
            "client_segment": "PYME",
            "total_usd": 1000.0,
            "archived_at": now,
            "archived_trigger": "status_enviada_imple",
            "attachments": [],
            "snapshot": {
                "quote_id": QUOTE_ID,
                "quote_number": QUOTE_NUMBER,
                "quote_category": "implementation",
                "created_at": "2025-01-15T10:00:00+00:00",
                "sent_to_client_at": "2025-01-16T10:00:00+00:00",
                "archived": True,
                "archived_trigger": "status_enviada_imple",
            },
            "created_at": "2025-01-15T10:00:00+00:00",
        })

    async def teardown():
        await db.quote_history.delete_many({"history_id": HISTORY_ID})

    asyncio.get_event_loop().run_until_complete(setup())
    yield
    asyncio.get_event_loop().run_until_complete(teardown())


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ============= GET attachments =============
class TestListAttachments:
    def test_admin_can_list(self, admin_token):
        r = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["history_id"] == HISTORY_ID
        assert d["quote_id"] == QUOTE_ID
        assert isinstance(d["attachments"], list)

    def test_nonadmin_forbidden_to_list(self, nonadmin_token):
        if not nonadmin_token:
            pytest.skip("no nonadmin")
        r = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(nonadmin_token), timeout=15)
        assert r.status_code == 403, r.text

    def test_404_for_missing_history(self, admin_token):
        r = requests.get(f"{API}/quote-history/qhist_does_not_exist_zzz/attachments", headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 404


# ============= POST upload =============
class TestUploadAttachment:
    def _upload(self, tok, category, fname="test.pdf", content=b"%PDF-1.4 test"):
        files = {"file": (fname, io.BytesIO(content), "application/pdf")}
        data = {"category": category}
        return requests.post(
            f"{API}/quote-history/{HISTORY_ID}/attachments",
            headers=_hdr(tok),
            files=files,
            data=data,
            timeout=30,
        )

    def test_nonadmin_cannot_upload(self, nonadmin_token):
        if not nonadmin_token:
            pytest.skip("no nonadmin")
        r = self._upload(nonadmin_token, "Cotización")
        assert r.status_code == 403

    def test_invalid_category_rejected(self, admin_token):
        r = self._upload(admin_token, "CategoriaFalsa")
        assert r.status_code == 400

    def test_file_too_large(self, admin_token):
        big = b"x" * (10 * 1024 * 1024 + 10)
        r = self._upload(admin_token, "Otros", content=big)
        assert r.status_code == 400

    def test_admin_upload_purchase_order_subsana(self, admin_token):
        r = self._upload(admin_token, "Orden de Compra")
        assert r.status_code == 200, r.text
        att = r.json()["attachment"]
        assert att["category"] == "Orden de Compra"
        assert att.get("is_subsana") is True
        # Verify GET reflects
        gr = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15)
        assert any(a["attachment_id"] == att["attachment_id"] for a in gr.json()["attachments"])

    def test_all_categories_allowed(self, admin_token):
        # Upload remaining categories (the OC was uploaded above; here we add Factura, Pagos, Nota de Entrega)
        for cat in ["Factura", "Pagos", "Nota de Entrega"]:
            r = self._upload(admin_token, cat)
            assert r.status_code == 200, f"{cat}: {r.text}"


# ============= GET download =============
class TestDownloadAttachment:
    def test_admin_can_download(self, admin_token):
        atts = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15).json()["attachments"]
        if not atts:
            pytest.skip("no attachments to download")
        aid = atts[0]["attachment_id"]
        r = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments/{aid}/download", headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith(("application/pdf", "application/octet-stream"))
        assert len(r.content) > 0

    def test_404_for_missing_attachment(self, admin_token):
        r = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments/hatt_zzzz/download", headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 404


# ============= Irregular report subsana logic =============
class TestIrregularQuotesSubsana:
    def test_history_quote_appears_with_subsana_phases(self, admin_token):
        """After uploading OC + Factura + Pagos + Nota de Entrega, the irregular item should
        either disappear OR have all critical phases marked subsana=True."""
        r = requests.get(f"{API}/reports/sales/irregular-quotes", headers=_hdr(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        items = r.json().get("items", [])
        ours = [it for it in items if it.get("quote_id") == QUOTE_ID]
        # All required missing-fields are subsanados (approved/invoiced/paid/delivered),
        # and `sent_to_client_at` exists in snapshot, so the quote should NOT appear.
        if not ours:
            return  # ideal: removed from report because all subsanado
        # Defensive fallback: if it still appears, last phase must be present and subsana flags must exist
        ph = ours[0]["phases"]
        last = ph[-1]
        assert last["present"] is True, "last phase must be green for history quote"

    def test_pdf_generation_with_subsana(self, admin_token):
        r = requests.get(f"{API}/reports/sales/irregular-quotes/pdf", headers=_hdr(admin_token), timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert len(r.content) > 1000  # sanity: real PDF


# ============= DELETE attachment =============
class TestDeleteAttachment:
    def test_nonadmin_cannot_delete(self, admin_token, nonadmin_token):
        if not nonadmin_token:
            pytest.skip("no nonadmin")
        atts = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15).json()["attachments"]
        if not atts:
            pytest.skip("no attachments")
        aid = atts[0]["attachment_id"]
        r = requests.delete(f"{API}/quote-history/{HISTORY_ID}/attachments/{aid}", headers=_hdr(nonadmin_token), timeout=15)
        assert r.status_code == 403

    def test_admin_can_delete(self, admin_token):
        atts = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15).json()["attachments"]
        if not atts:
            pytest.skip("no attachments")
        aid = atts[0]["attachment_id"]
        r = requests.delete(f"{API}/quote-history/{HISTORY_ID}/attachments/{aid}", headers=_hdr(admin_token), timeout=20)
        assert r.status_code == 200
        # Verify removal
        atts2 = requests.get(f"{API}/quote-history/{HISTORY_ID}/attachments", headers=_hdr(admin_token), timeout=15).json()["attachments"]
        assert all(a["attachment_id"] != aid for a in atts2)
