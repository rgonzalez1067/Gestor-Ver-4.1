# ruff: noqa
"""Iter 279 — REINFORCEMENT of Actions Override for Equipos quotes.

Novel coverage beyond iter278:
  * `_attach_allowed_emails` prunes not only stale allowed_user_ids but ALSO
    denormalized allowed_user_emails whose user was deleted → the enforcement
    engine and the config UI see the exact same effective set.
  * Regression: an override authorising an EXISTING user (joliveros) still
    surfaces that email in allowed_user_emails (legitimate restrictions kept).

Tests (per the review_request):
  1. PUT override with allowed_user_ids=[stale_id] → GET returns
     allowed_user_ids=[] and allowed_user_emails=[] (empty = todos).
  2. PUT override equipos|clientes_pyme|invoice with joliveros' user_id →
     GET returns allowed_user_emails=['joliveros@megasoft.com.ve'].
  3. Regression: existing equipos|clientes_pyme|approve override authorising
     joliveros must keep allowed_user_emails=['joliveros@megasoft.com.ve'].
  4. Ghost email pruning: inject a stale denormalized email directly into
     Mongo → GET must strip it (email not in current users → pruned).
  5. Mixed ghost + valid email pruning: injected ghost stripped, joliveros
     preserved.
"""
import os
import time
import pytest
import requests

# Load REACT_APP_BACKEND_URL from frontend/.env if not present in env.
if not os.environ.get("REACT_APP_BACKEND_URL"):
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
JOLIVEROS_EMAIL = "joliveros@megasoft.com.ve"
JOLIVEROS_USER_ID_EXPECTED = "user_4f7c4697b820"  # per review_request

BIZ = "equipos"
SUB = "clientes_pyme"

SEND_KEY = f"{BIZ}|{SUB}|send_to_client"
INVOICE_KEY = f"{BIZ}|{SUB}|invoice"
APPROVE_KEY = f"{BIZ}|{SUB}|approve"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("access_token") or body.get("token")
    assert token, f"No token in login response: {body}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def joliveros_user_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/auth/users", headers=admin_headers, timeout=30)
    assert r.status_code == 200, f"list users failed: {r.status_code} {r.text}"
    data = r.json()
    users = data if isinstance(data, list) else data.get("users") or data.get("items") or []
    for u in users:
        if (u.get("email") or "").strip().lower() == JOLIVEROS_EMAIL:
            uid = u.get("user_id") or u.get("id")
            assert uid, f"joliveros user missing user_id: {u}"
            return uid
    pytest.skip(f"joliveros user not found. sample={users[:2]}")


def _get_override(admin_headers, config_key):
    r = requests.get(
        f"{BASE_URL}/api/quote-action-overrides", headers=admin_headers, timeout=30
    )
    assert r.status_code == 200, r.text
    for it in r.json().get("items", []):
        if it.get("config_key") == config_key:
            return it
    return None


def _put_override(admin_headers, biz, sub, action, allowed_user_ids):
    payload = {
        "business_type": biz,
        "product_subcategory": sub,
        "action_id": action,
        "enabled": True,
        "allowed_user_ids": allowed_user_ids,
    }
    r = requests.put(
        f"{BASE_URL}/api/quote-action-overrides",
        headers=admin_headers,
        json=payload,
        timeout=30,
    )
    assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
    return r.json()


def _delete_override(admin_headers, config_key):
    try:
        requests.delete(
            f"{BASE_URL}/api/quote-action-overrides/{config_key}",
            headers=admin_headers,
            timeout=30,
        )
    except Exception:
        pass


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_overrides(admin_headers):
    """Ensure no leftover TEST override at start/end for SEND_KEY and INVOICE_KEY.
    Never touches APPROVE_KEY (legitimate preexisting restriction to joliveros)."""
    _delete_override(admin_headers, SEND_KEY)
    _delete_override(admin_headers, INVOICE_KEY)
    yield
    _delete_override(admin_headers, SEND_KEY)
    _delete_override(admin_headers, INVOICE_KEY)


# ---------------------------------------------------------------------------
# Direct Mongo helpers to inject stale denormalized emails (simulates data
# persisted BEFORE the fix). Uses the same MONGO_URL/DB_NAME the backend uses.
# ---------------------------------------------------------------------------
def _mongo_client():
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        # Load from backend/.env
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    assert mongo_url and db_name, "MONGO_URL/DB_NAME missing"
    return MongoClient(mongo_url), db_name


def _inject_denormalized_emails(config_key, allowed_user_emails, allowed_user_ids=None):
    """Directly set allowed_user_emails on the override doc (bypasses PUT
    which would resolve fresh). Used to simulate 'ghost' denormalized data."""
    client, db_name = _mongo_client()
    try:
        coll = client[db_name].quote_action_overrides
        coll.update_one(
            {"config_key": config_key},
            {"$set": {"allowed_user_emails": allowed_user_emails,
                      "allowed_user_ids": allowed_user_ids or []}},
        )
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Test 1 — stale user_ids → allowed_user_ids=[] and allowed_user_emails=[]
# ---------------------------------------------------------------------------
def test_stale_user_ids_pruned_empty_means_todos(admin_headers):
    stale_id = "user_STALE_noexiste_iter279_" + str(int(time.time()))
    _put_override(admin_headers, BIZ, SUB, "send_to_client", [stale_id])
    ov = _get_override(admin_headers, SEND_KEY)
    assert ov is not None, f"override {SEND_KEY} not found in list"
    assert ov.get("allowed_user_ids") == [], (
        f"stale id NOT pruned. allowed_user_ids={ov.get('allowed_user_ids')}"
    )
    assert ov.get("allowed_user_emails") == [], (
        f"allowed_user_emails should be empty for stale id, got {ov.get('allowed_user_emails')}"
    )


# ---------------------------------------------------------------------------
# Test 2 — valid user_id (joliveros) denormalizes email correctly on invoice
# ---------------------------------------------------------------------------
def test_valid_user_id_joliveros_denormalizes_email(admin_headers, joliveros_user_id):
    _put_override(admin_headers, BIZ, SUB, "invoice", [joliveros_user_id])
    ov = _get_override(admin_headers, INVOICE_KEY)
    assert ov is not None, f"override {INVOICE_KEY} not found"
    emails_lc = sorted([(e or "").strip().lower() for e in (ov.get("allowed_user_emails") or [])])
    assert emails_lc == [JOLIVEROS_EMAIL], (
        f"Expected only joliveros in allowed_user_emails, got {emails_lc}"
    )
    ids = ov.get("allowed_user_ids") or []
    assert joliveros_user_id in ids, (
        f"Expected joliveros user_id in allowed_user_ids, got {ids}"
    )


# ---------------------------------------------------------------------------
# Test 3 — REGRESSION: existing approve override still restricted to joliveros
# ---------------------------------------------------------------------------
def test_regression_existing_approve_override_keeps_joliveros(admin_headers):
    ov = _get_override(admin_headers, APPROVE_KEY)
    if ov is None:
        pytest.skip(f"preexisting override {APPROVE_KEY} not present in this env")
    emails_lc = sorted([(e or "").strip().lower() for e in (ov.get("allowed_user_emails") or [])])
    assert JOLIVEROS_EMAIL in emails_lc, (
        f"regression: joliveros must remain in approve.allowed_user_emails, got {emails_lc}"
    )


# ---------------------------------------------------------------------------
# Test 4 — DENORMALIZED GHOST EMAIL is pruned by _attach_allowed_emails
# (this is the NEW behavior of the reinforcement fix — beyond iter278)
# ---------------------------------------------------------------------------
def test_ghost_denormalized_email_pruned(admin_headers):
    # Create override empty via PUT, then inject a stale email directly.
    _put_override(admin_headers, BIZ, SUB, "send_to_client", [])
    ghost_email = "ghost_deleted_user_iter279@example.invalid"
    _inject_denormalized_emails(SEND_KEY, [ghost_email], [])
    ov = _get_override(admin_headers, SEND_KEY)
    assert ov is not None
    emails_lc = [(e or "").strip().lower() for e in (ov.get("allowed_user_emails") or [])]
    assert ghost_email not in emails_lc, (
        f"ghost email NOT pruned by _attach_allowed_emails: {emails_lc}"
    )
    # With only a ghost email injected → effective set must be empty (todos).
    assert emails_lc == [], (
        f"only-ghost override must resolve to empty (todos), got {emails_lc}"
    )


# ---------------------------------------------------------------------------
# Test 5 — MIXED: ghost + valid → ghost pruned, valid preserved
# ---------------------------------------------------------------------------
def test_mixed_ghost_and_valid_denormalized_emails(admin_headers):
    _put_override(admin_headers, BIZ, SUB, "send_to_client", [])
    ghost_email = "ghost_mix_iter279@example.invalid"
    _inject_denormalized_emails(SEND_KEY, [ghost_email, JOLIVEROS_EMAIL], [])
    ov = _get_override(admin_headers, SEND_KEY)
    assert ov is not None
    emails_lc = sorted([(e or "").strip().lower() for e in (ov.get("allowed_user_emails") or [])])
    assert ghost_email not in emails_lc, f"ghost NOT pruned: {emails_lc}"
    assert JOLIVEROS_EMAIL in emails_lc, f"valid email dropped: {emails_lc}"
