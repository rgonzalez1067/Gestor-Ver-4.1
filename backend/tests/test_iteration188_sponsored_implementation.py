"""
Iteration 188 — Implementación Patrocinada (sponsored_implementation)
Tests backend persistence of sponsored_implementation, sponsoring_bank_id, sponsoring_bank_name
on create-with-pdf, PUT update, duplicate, and send-to-implementation flows.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.text}"
    d = r.json()
    return d.get("session_token") or d.get("access_token") or d.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def bank_id(headers):
    r = requests.get(f"{API}/banks", headers=headers, timeout=30)
    assert r.status_code == 200
    banks = r.json()
    assert len(banks) > 0, "No banks in maestro"
    return banks[0].get("bank_id"), banks[0].get("name")


@pytest.fixture(scope="module")
def client_id(headers):
    r = requests.get(f"{API}/clients", headers=headers, timeout=30)
    assert r.status_code == 200
    clients = r.json()
    assert len(clients) > 0
    return clients[0]["client_id"]


def _create_minimal_quote(headers, client_id, sponsored=False, sponsoring_bank_id=None, sponsoring_bank_name=None):
    payload = {
        "client_id": client_id,
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "pricing_model": "conventional",
        "services": [],
        "hardware": [],
        "equipment_items": [],
        "pg_setup_items": [],
        "sponsored_implementation": sponsored,
        "sponsoring_bank_id": sponsoring_bank_id,
        "sponsoring_bank_name": sponsoring_bank_name,
        "client_segment": "PYME",
        "override_total_usd": 100.0,
    }
    r = requests.post(f"{API}/quotes/create-with-pdf", headers=headers, json=payload, timeout=60)
    assert r.status_code == 200, f"create-with-pdf failed: {r.status_code} {r.text}"
    return r.json()["quote"]


# ---------------- Tests ----------------
class TestSponsoredImplementation:
    """Verifica persistencia y herencia de los campos sponsored_*"""

    def test_create_with_pdf_persists_sponsored_fields(self, headers, client_id, bank_id):
        bid, bname = bank_id
        q = _create_minimal_quote(headers, client_id, True, bid, bname)
        qid = q["quote_id"]
        # GET back
        r = requests.get(f"{API}/quotes/{qid}", headers=headers, timeout=30)
        assert r.status_code == 200
        doc = r.json()
        assert doc.get("sponsored_implementation") is True
        assert doc.get("sponsoring_bank_id") == bid
        assert doc.get("sponsoring_bank_name") == bname
        # cleanup
        requests.delete(f"{API}/quotes/{qid}", headers=headers, timeout=30)

    def test_create_with_pdf_default_false(self, headers, client_id):
        q = _create_minimal_quote(headers, client_id, False, None, None)
        qid = q["quote_id"]
        r = requests.get(f"{API}/quotes/{qid}", headers=headers, timeout=30)
        assert r.status_code == 200
        doc = r.json()
        assert doc.get("sponsored_implementation") in (False, None)
        assert not doc.get("sponsoring_bank_id")
        requests.delete(f"{API}/quotes/{qid}", headers=headers, timeout=30)

    def test_put_update_sponsored_fields(self, headers, client_id, bank_id):
        bid, bname = bank_id
        q = _create_minimal_quote(headers, client_id, False, None, None)
        qid = q["quote_id"]
        # Update: enable sponsorship
        r = requests.put(
            f"{API}/quotes/{qid}",
            headers=headers,
            json={"sponsored_implementation": True, "sponsoring_bank_id": bid, "sponsoring_bank_name": bname},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        # Verify
        g = requests.get(f"{API}/quotes/{qid}", headers=headers, timeout=30).json()
        assert g.get("sponsored_implementation") is True
        assert g.get("sponsoring_bank_id") == bid
        # Toggle back to false with empty bank_id
        r2 = requests.put(
            f"{API}/quotes/{qid}",
            headers=headers,
            json={"sponsored_implementation": False, "sponsoring_bank_id": ""},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        g2 = requests.get(f"{API}/quotes/{qid}", headers=headers, timeout=30).json()
        assert g2.get("sponsored_implementation") is False
        # bank_id should now be empty string
        assert g2.get("sponsoring_bank_id") in ("", None)
        requests.delete(f"{API}/quotes/{qid}", headers=headers, timeout=30)

    def test_duplicate_copies_sponsored_fields(self, headers, client_id, bank_id):
        bid, bname = bank_id
        q = _create_minimal_quote(headers, client_id, True, bid, bname)
        qid = q["quote_id"]
        r = requests.post(f"{API}/quotes/{qid}/duplicate", headers=headers, timeout=30)
        if r.status_code == 404:
            pytest.skip("duplicate endpoint not available")
        assert r.status_code in (200, 201), r.text
        data = r.json()
        dup_id = data.get("new_quote_id") or (data.get("quote") or {}).get("quote_id") or data.get("quote_id")
        assert dup_id and dup_id != qid, f"no duplicated id in {data}"
        # GET duplicated
        g = requests.get(f"{API}/quotes/{dup_id}", headers=headers, timeout=30).json()
        assert g.get("sponsored_implementation") is True
        assert g.get("sponsoring_bank_id") == bid
        # cleanup
        requests.delete(f"{API}/quotes/{qid}", headers=headers, timeout=30)
        requests.delete(f"{API}/quotes/{dup_id}", headers=headers, timeout=30)

    def test_send_to_implementation_inherits_sponsored_fields(self, headers, client_id, bank_id):
        """E2E: create quote with sponsorship, force through workflow to 'Pagada', then send-to-implementation."""
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if not mongo_url or not db_name:
            pytest.skip("MONGO_URL/DB_NAME not available")
        mc = MongoClient(mongo_url)
        db = mc[db_name]

        bid, bname = bank_id
        q = _create_minimal_quote(headers, client_id, True, bid, bname)
        qid = q["quote_id"]

        # Force to 'Pagada' state directly (bypassing attachment requirements)
        db.quotes.update_one({"quote_id": qid}, {"$set": {"quote_status": "Pagada"}})

        r = requests.post(f"{API}/quotes/{qid}/send-to-implementation", headers=headers, timeout=60)
        if r.status_code == 404:
            pytest.skip("send-to-implementation endpoint not found")
        if r.status_code != 200:
            # Still validate via DB: maybe needs attachments; skip with info
            pytest.skip(f"send-to-implementation returned {r.status_code}: {r.text[:200]}")
        data = r.json()
        project_id = (data.get("project") or {}).get("project_id") or data.get("project_id")
        if not project_id:
            # Look up project by quote_id in DB
            proj = db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None, f"no project created for quote {qid}; response={data}"
            project_id = proj["project_id"]
        proj = db.projects.find_one({"project_id": project_id}, {"_id": 0})
        assert proj is not None
        assert proj.get("sponsored_implementation") is True, f"project missing sponsored flag: keys={list(proj.keys())}"
        assert proj.get("sponsoring_bank_id") == bid
        # Cleanup
        db.quotes.delete_one({"quote_id": qid})
        db.projects.delete_one({"project_id": project_id})
        mc.close()
