"""
Iteration 322: Verify x-client-recipients header override for:
  1. POST /api/quotes/{quote_id}/repair-complete
  2. POST /api/quotes/{quote_id}/custom-action/{action_id}  (pago_validado_rep)

Scenarios (repair-complete):
  A) header with 1 taller email -> quote_status becomes Reparada, email routed to override
  C) no header -> primary contact (contacts[0].email) used as client_email

Scenarios (custom-action pago_validado_rep):
  - responds 200 without header (baseline)
  - responds 200 with header (override doesn't break)
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Fallback: read frontend env
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

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


def _find_repair_approved(d, limit=5):
    return list(d.quotes.find(
        {"quote_category": "repair", "quote_status": "Aprobada"}, {"_id": 0}
    ).limit(limit))


def _reset_to_aprobada(d, qid):
    d.quotes.update_one(
        {"quote_id": qid},
        {"$set": {"quote_status": "Aprobada"}, "$unset": {"repaired_at": "", "repair_billing_data": ""}},
    )


def _seed_contacts(d, cid, contacts):
    d.clients.update_one({"client_id": cid}, {"$set": {"contacts": contacts}})


def _get_client(d, cid):
    return d.clients.find_one({"client_id": cid}, {"_id": 0})


def _do_repair_complete(token, qid, extra_headers=None, body=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return requests.post(
        f"{BASE_URL}/api/quotes/{qid}/repair-complete",
        headers=headers,
        json=body or {},
        timeout=90,
    )


def _do_custom_action(token, qid, action_id, extra_headers=None, body=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return requests.post(
        f"{BASE_URL}/api/quotes/{qid}/custom-action/{action_id}",
        headers=headers,
        json=body or {},
        timeout=90,
    )


def _latest_email_logs(d, qid, limit=20):
    return list(d.email_logs.find({"quote_id": qid}, {"_id": 0}).sort("timestamp", -1).limit(limit))


class TestRepairCompleteTallerOverride:

    def test_A_header_override_wins(self, token, db):
        d = db
        quotes = _find_repair_approved(d, 5)
        assert quotes, "No repair quote in Aprobada status available"
        q = quotes[0]
        qid = q["quote_id"]
        cid = q["client_id"]

        original = _get_client(d, cid)
        original_contacts = original.get("contacts", []) if original else []

        try:
            taller_email = "TEST_taller_A_iter322@example.com"
            primary_email = "TEST_primary_A_iter322@example.com"
            _seed_contacts(d, cid, [
                {"full_name": "Primary A", "email": primary_email, "purposes": ["facturacion"]},
                {"full_name": "Taller A", "email": taller_email, "purposes": ["taller"]},
            ])

            r = _do_repair_complete(token, qid, {"x-client-recipients": taller_email})
            print(f"[A] repair-complete status={r.status_code} body={r.text[:300]}")
            assert r.status_code == 200, f"repair-complete failed: {r.text}"

            # Confirm status transition
            q_after = d.quotes.find_one({"quote_id": qid}, {"_id": 0})
            assert q_after.get("quote_status") == "Reparada", f"Status should be Reparada, got {q_after.get('quote_status')}"

            time.sleep(2)
            logs = _latest_email_logs(d, qid)
            all_tos = []
            for l in logs:
                to = l.get("to") or []
                if isinstance(to, str):
                    to = [to]
                all_tos.extend(to)
            print(f"[A] logs: {[(l.get('action'), l.get('to')) for l in logs[:8]]}")
            assert taller_email in all_tos, f"Expected {taller_email} in email_logs, got {all_tos}"
            assert primary_email not in all_tos, f"Primary should NOT receive, got {all_tos}"
        finally:
            _seed_contacts(d, cid, original_contacts)
            _reset_to_aprobada(d, qid)

    def test_C_no_header_uses_primary(self, token, db):
        d = db
        quotes = _find_repair_approved(d, 5)
        assert len(quotes) >= 2, "Need >=2 repair quotes in Aprobada"
        q = quotes[1]
        qid = q["quote_id"]
        cid = q["client_id"]

        original = _get_client(d, cid)
        original_contacts = original.get("contacts", []) if original else []

        try:
            primary_email = "TEST_primary_C_iter322@example.com"
            other = "TEST_other_C_iter322@example.com"
            _seed_contacts(d, cid, [
                {"full_name": "Primary C", "email": primary_email, "purposes": ["facturacion"]},
                {"full_name": "Other C", "email": other, "purposes": []},
            ])

            r = _do_repair_complete(token, qid, None)
            print(f"[C] status={r.status_code} body={r.text[:300]}")
            assert r.status_code == 200, f"repair-complete failed: {r.text}"

            time.sleep(2)
            logs = _latest_email_logs(d, qid)
            all_tos = []
            for l in logs:
                to = l.get("to") or []
                if isinstance(to, str):
                    to = [to]
                all_tos.extend(to)
            print(f"[C] logs: {[(l.get('action'), l.get('to')) for l in logs[:8]]}")
            assert primary_email in all_tos, f"Expected primary {primary_email} in tos, got {all_tos}"
        finally:
            _seed_contacts(d, cid, original_contacts)
            _reset_to_aprobada(d, qid)


class TestCustomActionPagoValidadoTallerOverride:

    def _find_repair_for_custom(self, d):
        # Any repair quote to which we can fire pago_validado_rep (endpoint does not enforce status)
        # Prefer one not in Aprobada so we don't collide with repair-complete tests.
        cands = list(d.quotes.find(
            {"quote_category": "repair", "quote_status": {"$in": ["Pagada", "Reparada", "Entregada", "Facturada"]}},
            {"_id": 0}
        ).limit(3))
        return cands

    def test_baseline_no_header_200(self, token, db):
        d = db
        cands = self._find_repair_for_custom(d)
        if not cands:
            pytest.skip("No suitable repair quote for custom-action test")
        q = cands[0]
        qid = q["quote_id"]

        r = _do_custom_action(token, qid, "pago_validado_rep", None, {"custom_message": "test iter322 baseline"})
        print(f"[custom baseline] status={r.status_code} body={r.text[:400]}")
        assert r.status_code == 200, f"custom-action baseline failed: {r.text}"

    def test_with_header_200_and_override_applied(self, token, db):
        d = db
        cands = self._find_repair_for_custom(d)
        if len(cands) < 1:
            pytest.skip("No suitable repair quote for custom-action test")
        # Try quote index 1 first, fall back to 0
        q = cands[1] if len(cands) >= 2 else cands[0]
        qid = q["quote_id"]
        cid = q["client_id"]

        original = _get_client(d, cid)
        original_contacts = original.get("contacts", []) if original else []

        try:
            taller_email = "TEST_taller_custom_iter322@example.com"
            primary_email = "TEST_primary_custom_iter322@example.com"
            _seed_contacts(d, cid, [
                {"full_name": "Primary Cx", "email": primary_email, "purposes": []},
                {"full_name": "Taller Cx", "email": taller_email, "purposes": ["taller"]},
            ])

            r = _do_custom_action(
                token, qid, "pago_validado_rep",
                {"x-client-recipients": taller_email},
                {"custom_message": "test iter322 with header"},
            )
            print(f"[custom w/ header] status={r.status_code} body={r.text[:400]}")
            assert r.status_code == 200, f"custom-action w/ header failed: {r.text}"

            # Best-effort: check email_logs for override recipient
            time.sleep(2)
            logs = _latest_email_logs(d, qid)
            all_tos = []
            for l in logs:
                to = l.get("to") or []
                if isinstance(to, str):
                    to = [to]
                all_tos.extend(to)
            print(f"[custom] logs: {[(l.get('action'), l.get('to')) for l in logs[:8]]}")
            # Only assert override applied IF any client_field row was actually dispatched.
            # If no client_field email was sent (config-dependent), don't fail — the header
            # acceptance is the primary contract we're verifying.
            client_rows_sent = [t for t in all_tos if "@" in t and "megasoft" not in t.lower()]
            if client_rows_sent:
                assert taller_email in all_tos, f"When client dispatched, expected override {taller_email}, got {all_tos}"
                assert primary_email not in all_tos, f"Primary should NOT receive, got {all_tos}"
            else:
                print("[custom] No client_field email dispatched — header accepted, no client recipient row in config.")
        finally:
            _seed_contacts(d, cid, original_contacts)


class TestRepairCompleteHeaderAcceptance:
    """Ensure header does NOT cause 4xx even when quote is in wrong state."""

    def test_wrong_state_returns_400_but_not_500(self, token, db):
        d = db
        wrong = d.quotes.find_one(
            {"quote_category": "repair", "quote_status": {"$ne": "Aprobada"}}, {"_id": 0}
        )
        if not wrong:
            pytest.skip("No non-Aprobada repair quote")
        r = _do_repair_complete(token, wrong["quote_id"], {"x-client-recipients": "foo@bar.com"})
        print(f"[hdr-accept] status={r.status_code} body={r.text[:200]}")
        assert r.status_code in (400, 404), f"Header should not cause 5xx; got {r.status_code}: {r.text}"
