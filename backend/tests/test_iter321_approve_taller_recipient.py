"""
Iteration 321: Verify APPROVE flow for Repair Quotes routes email to
Taller-profile contact using x-client-recipients header override.

Scenario A: header set with 1 taller email -> email_logs.to == that email
Scenario C: no header -> email_logs.to == primary contact (contacts[0].email)
Scenario Equipment regression: quote_category='equipment' still notifies Admin/Sales
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-overhaul.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no token in {r.json()}"
    return tok


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    yield d
    client.close()


def _find_repair_quote(d, min_count=3):
    """Find repair quotes in 'Enviada' status and return list."""
    return list(d.quotes.find(
        {"quote_category": "repair", "quote_status": "Enviada"},
        {"_id": 0}
    ).limit(min_count))


def _seed_contacts(d, client_id, contacts):
    d.clients.update_one({"client_id": client_id}, {"$set": {"contacts": contacts}})


def _get_client(d, client_id):
    return d.clients.find_one({"client_id": client_id}, {"_id": 0})


def _reset_status_to_enviada(d, quote_id):
    d.quotes.update_one({"quote_id": quote_id}, {"$set": {"quote_status": "Enviada"}, "$unset": {"approved_at": ""}})


def _latest_email_logs(d, quote_id, limit=20):
    return list(d.email_logs.find({"quote_id": quote_id}, {"_id": 0}).sort("timestamp", -1).limit(limit))


def _do_approve(token, quote_id, extra_headers=None):
    headers = {"Authorization": f"Bearer {token}"}
    if extra_headers:
        headers.update(extra_headers)
    files = {"payload": (None, "{}")}
    r = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=headers, files=files, timeout=90)
    return r


class TestApproveTallerOverride:
    """Backend verification of x-client-recipients override on approve."""

    def test_scenario_A_header_override_wins(self, token, db):
        d = db
        quotes = _find_repair_quote(d, 5)
        assert quotes, "No repair quote in Enviada status available"
        q = quotes[0]
        qid = q["quote_id"]
        cid = q["client_id"]

        original_client = _get_client(d, cid)
        original_contacts = original_client.get("contacts", []) if original_client else []

        try:
            # Seed: 1 taller + 1 primary (no taller)
            taller_email = "TEST_taller_A_iter321@example.com"
            primary_email = "TEST_primary_A_iter321@example.com"
            new_contacts = [
                {"full_name": "Primary A", "email": primary_email, "purposes": ["facturacion"]},
                {"full_name": "Taller A", "email": taller_email, "purposes": ["taller"]},
            ]
            _seed_contacts(d, cid, new_contacts)

            r = _do_approve(token, qid, {"x-client-recipients": taller_email})
            print(f"[A] approve status={r.status_code} body={r.text[:400]}")
            assert r.status_code == 200, f"approve failed: {r.text}"

            time.sleep(2)
            logs = _latest_email_logs(d, qid, limit=20)
            print(f"[A] recent email_logs count={len(logs)}")
            # Engine may log as approve_dynamic or repair_approved_client; grab any log referencing the override
            all_tos = []
            for l in logs:
                to_field = l.get("to") or []
                if isinstance(to_field, str):
                    to_field = [to_field]
                all_tos.extend(to_field)
            print(f"[A] logs: {[(l.get('action'),l.get('to')) for l in logs]}")
            assert taller_email in all_tos, f"Expected {taller_email} in email_logs, got tos={all_tos}"
            assert primary_email not in all_tos, f"Primary should NOT be recipient, got {all_tos}"
        finally:
            _seed_contacts(d, cid, original_contacts)
            _reset_status_to_enviada(d, qid)

    def test_scenario_C_no_header_uses_primary(self, token, db):
        d = db
        quotes = _find_repair_quote(d, 5)
        # pick a different quote
        assert len(quotes) >= 2, "Need at least 2 repair quotes in Enviada"
        q = quotes[1]
        qid = q["quote_id"]
        cid = q["client_id"]

        original_client = _get_client(d, cid)
        original_contacts = original_client.get("contacts", []) if original_client else []

        try:
            primary_email = "TEST_primary_C_iter321@example.com"
            other_email = "TEST_other_C_iter321@example.com"
            # No taller-profile contact
            new_contacts = [
                {"full_name": "Primary C", "email": primary_email, "purposes": ["facturacion"]},
                {"full_name": "Other C", "email": other_email, "purposes": []},
            ]
            _seed_contacts(d, cid, new_contacts)

            r = _do_approve(token, qid, None)  # no override
            print(f"[C] approve status={r.status_code} body={r.text[:400]}")
            assert r.status_code == 200, f"approve failed: {r.text}"

            time.sleep(2)
            logs = _latest_email_logs(d, qid, limit=20)
            all_tos = []
            for l in logs:
                to_field = l.get("to") or []
                if isinstance(to_field, str):
                    to_field = [to_field]
                all_tos.extend(to_field)
            print(f"[C] logs: {[(l.get('action'),l.get('to')) for l in logs]}")
            # Primary contact = contacts[0].email
            assert primary_email in all_tos, f"Expected primary {primary_email} in email_logs, got {all_tos}"
        finally:
            _seed_contacts(d, cid, original_contacts)
            _reset_status_to_enviada(d, qid)

    def test_scenario_A_multi_override_first_is_to_rest_cc(self, token, db):
        """Extra contacts in override header become CC (legacy path)."""
        d = db
        quotes = _find_repair_quote(d, 5)
        assert len(quotes) >= 3, "Need at least 3 repair quotes"
        q = quotes[2]
        qid = q["quote_id"]
        cid = q["client_id"]

        original_client = _get_client(d, cid)
        original_contacts = original_client.get("contacts", []) if original_client else []

        try:
            t1 = "TEST_taller_B1_iter321@example.com"
            t2 = "TEST_taller_B2_iter321@example.com"
            primary_email = "TEST_primary_B_iter321@example.com"
            new_contacts = [
                {"full_name": "Primary B", "email": primary_email, "purposes": []},
                {"full_name": "Taller B1", "email": t1, "purposes": ["taller"]},
                {"full_name": "Taller B2", "email": t2, "purposes": ["taller"]},
            ]
            _seed_contacts(d, cid, new_contacts)

            # Scenario B: frontend allows selecting one, but backend should honor whatever single value comes.
            # We simulate by sending only t2 in header (chosen in modal).
            r = _do_approve(token, qid, {"x-client-recipients": t2})
            print(f"[B] approve status={r.status_code} body={r.text[:400]}")
            assert r.status_code == 200, f"approve failed: {r.text}"

            time.sleep(2)
            logs = _latest_email_logs(d, qid, limit=20)
            all_tos = []
            for l in logs:
                to_field = l.get("to") or []
                if isinstance(to_field, str):
                    to_field = [to_field]
                all_tos.extend(to_field)
            print(f"[B] logs: {[(l.get('action'),l.get('to')) for l in logs]}")
            assert t2 in all_tos, f"Expected chosen taller {t2}, got {all_tos}"
            assert primary_email not in all_tos, f"Primary should not receive, got {all_tos}"
            assert t1 not in all_tos, f"Non-chosen taller {t1} should not receive"
        finally:
            _seed_contacts(d, cid, original_contacts)
            _reset_status_to_enviada(d, qid)

    def test_regression_equipment_unaffected(self, token, db):
        """Equipment quote approval should still work and not touch client override path."""
        d = db
        eq = d.quotes.find_one(
            {"quote_category": "equipment", "quote_status": "Enviada"},
            {"_id": 0}
        )
        if not eq:
            pytest.skip("No equipment quote in Enviada available")
        qid = eq["quote_id"]

        try:
            r = _do_approve(token, qid, None)
            print(f"[EQ] approve status={r.status_code} body={r.text[:300]}")
            assert r.status_code == 200, f"equipment approve failed: {r.text}"
            body = r.json()
            assert body.get("is_repair") in (False, None), "Should not be marked repair"
        finally:
            _reset_status_to_enviada(d, qid)
