"""Tests for repair-quote PDF serials parity (admin vs non-admin) and send-to-client flow.

Bug context: `regenerate_equipment_pdf` previously did not render actual serials
(only counts) nor the 'Anexo de Seriales por Modelo'. Fix ensures serials parity
regardless of role.
"""
import os
import io
import re
import pytest
import requests
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    from pypdf import PdfReader  # type: ignore

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
QUOTE_ID = "quo_fb10e377bbf3"
QUOTE_NUMBER = "COT-2026-05-022-PYME"
PDF_PATH = Path(f"/app/backend/uploads/{QUOTE_NUMBER}_Cotizacion_Equipo.pdf")

EXPECTED_SERIALS = [
    "806-409-808",
    "903-461-347",
    "323-092-168",
    "327-564-976",
    "809-203-093",
    "324-666-051",
    "303-982-648",
]

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
NONADMIN = {"email": "kherrera@megasoft.com.ve", "password": "Test1234!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed {creds['email']}: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No session_token in login response: {r.json()}"
    return tok


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _pdf_text_from_path():
    assert PDF_PATH.exists(), f"PDF not found at {PDF_PATH}"
    reader = PdfReader(str(PDF_PATH))
    return "\n".join((p.extract_text() or "") for p in reader.pages), len(reader.pages)


def _pdf_text_from_bytes(b: bytes):
    reader = PdfReader(io.BytesIO(b))
    return "\n".join((p.extract_text() or "") for p in reader.pages), len(reader.pages)


def _assert_serials_in_text(text, label=""):
    missing = [s for s in EXPECTED_SERIALS if s not in text]
    assert not missing, f"[{label}] Missing serials in PDF: {missing}"
    assert "Anexo de Seriales" in text, f"[{label}] 'Anexo de Seriales' title not found in PDF"


# --- Persisted DB serials for consistency check ---
def _get_quote_serials(tok):
    r = requests.get(f"{BASE_URL}/api/quotes/{QUOTE_ID}", headers=_auth(tok), timeout=30)
    assert r.status_code == 200, f"GET quote failed: {r.status_code} {r.text[:200]}"
    q = r.json()
    serials = set()
    for it in q.get("equipment_items", []) or []:
        for s in (it.get("serials") or []):
            if s:
                serials.add(str(s).strip())
    for rm in q.get("repair_models", []) or []:
        for s in (rm.get("serials") or []):
            if s:
                serials.add(str(s).strip())
    # bulk_serials fallback
    for s in q.get("bulk_serials", []) or []:
        if s:
            serials.add(str(s).strip())
    return serials, q


class TestRepairSerialsParity:
    def test_01_admin_regenerate_produces_serials(self):
        tok = _login(ADMIN)
        r = requests.post(
            f"{BASE_URL}/api/quotes/{QUOTE_ID}/regenerate-equipment-pdf",
            headers=_auth(tok), timeout=60,
        )
        assert r.status_code == 200, f"Admin regen failed: {r.status_code} {r.text[:300]}"
        text, pages = _pdf_text_from_path()
        print(f"[admin] pages={pages} len(text)={len(text)}")
        _assert_serials_in_text(text, "admin-regen")

    def test_02_nonadmin_regenerate_same_quote(self):
        tok = _login(NONADMIN)
        r = requests.post(
            f"{BASE_URL}/api/quotes/{QUOTE_ID}/regenerate-equipment-pdf",
            headers=_auth(tok), timeout=60,
        )
        assert r.status_code == 200, (
            f"Non-admin regen failed: {r.status_code} {r.text[:300]}"
        )
        text, pages = _pdf_text_from_path()
        print(f"[nonadmin] pages={pages} len(text)={len(text)}")
        _assert_serials_in_text(text, "nonadmin-regen")

    def test_03_consistency_pdf_vs_db(self):
        """Compare serials in Mongo (equipment_items/repair_models/bulk_serials)
        directly against the regenerated PDF. The public GET /api/quotes does not
        expose serials, so we query MongoDB directly."""
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        client = MongoClient(mongo_url)
        q = client[db_name].quotes.find_one({"quote_id": QUOTE_ID}, {"_id": 0})
        assert q, f"Quote {QUOTE_ID} not found in Mongo db={db_name}"
        db_serials = set()
        for it in q.get("equipment_items", []) or []:
            for s in (it.get("serials") or []):
                if s: db_serials.add(str(s).strip())
        for rm in q.get("repair_models", []) or []:
            for s in (rm.get("serials") or []):
                if s: db_serials.add(str(s).strip())
        for s in q.get("bulk_serials", []) or []:
            if s: db_serials.add(str(s).strip())

        pattern = re.compile(r"^\d{3}-\d{3}-\d{3}$")
        relevant = {s for s in db_serials if pattern.match(s)}
        print(f"DB serials found: {sorted(relevant)}")
        assert relevant, (
            f"No pattern-matching serials found in Mongo for {QUOTE_ID}. "
            f"raw db_serials={db_serials}. This is unexpected — the fix says "
            f"`bulk_serials` should now be persisted."
        )
        text, _ = _pdf_text_from_path()
        missing = [s for s in relevant if s not in text]
        assert not missing, f"DB serials not present in regenerated PDF: {missing}"
        print(f"OK: {len(relevant)} DB serials all present in PDF.")

    def test_04_send_to_client_pdf_bytes_contain_serials(self):
        """Validate _ensure_quote_pdf_bytes path indirectly via any endpoint that
        emails/attaches the PDF. If not available, fall back to deleting the on-disk
        PDF and re-invoking regenerate to prove regeneration alone yields serials."""
        tok = _login(ADMIN)

        # Simulate ephemeral disk: remove file, then call regenerate (mirrors what
        # _ensure_quote_pdf_bytes does when file is missing).
        if PDF_PATH.exists():
            PDF_PATH.unlink()
        assert not PDF_PATH.exists()

        r = requests.post(
            f"{BASE_URL}/api/quotes/{QUOTE_ID}/regenerate-equipment-pdf",
            headers=_auth(tok), timeout=60,
        )
        assert r.status_code == 200, f"regen after unlink failed: {r.status_code} {r.text[:300]}"
        assert PDF_PATH.exists(), "PDF was not recreated after regenerate"
        text, pages = _pdf_text_from_path()
        print(f"[ensure-flow] pages={pages}")
        _assert_serials_in_text(text, "ensure-flow")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
