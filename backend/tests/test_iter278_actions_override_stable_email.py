# ruff: noqa
"""Iter 278 — Actions Override for Equipos quotes.

Tests:
1. GET /api/quote-action-overrides prunes stale allowed_user_ids (users that no
   longer resolve) and returns allowed_user_emails resolved against CURRENT users.
2. PUT with agodoy's current user_id denormalizes allowed_user_emails properly.
3. Regression: PUT still denormalizes allowed_user_emails from valid ids.
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
AGODOY_EMAIL = "agodoy@megasoft.com.ve"

BIZ = "equipos"
SUB = "clientes_pyme"
ACTION_ID = "send_to_client"
CONFIG_KEY = f"{BIZ}|{SUB}|{ACTION_ID}"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    token = (
        r.json().get("session_token")
        or r.json().get("access_token")
        or r.json().get("token")
    )
    assert token, f"No token in login response: {r.json()}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def agodoy_user_id(admin_headers):
    """Fetch agodoy's current user_id via /api/auth/users (admin only)."""
    r = requests.get(f"{BASE_URL}/api/auth/users", headers=admin_headers, timeout=30)
    assert r.status_code == 200, f"list users failed: {r.status_code} {r.text}"
    data = r.json()
    users = data if isinstance(data, list) else data.get("users") or data.get("items") or []
    for u in users:
        if (u.get("email") or "").strip().lower() == AGODOY_EMAIL:
            uid = u.get("user_id") or u.get("id")
            assert uid, f"agodoy user missing user_id field: {u}"
            return uid
    pytest.skip(f"agodoy user not found in /api/auth/users. sample={users[:2]}")


def _get_override(admin_headers, config_key):
    r = requests.get(
        f"{BASE_URL}/api/quote-action-overrides", headers=admin_headers, timeout=30
    )
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    for it in items:
        if it.get("config_key") == config_key:
            return it
    return None


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
def cleanup(admin_headers):
    """Ensure no leftover override at start and end."""
    _delete_override(admin_headers, CONFIG_KEY)
    yield
    _delete_override(admin_headers, CONFIG_KEY)


# ---------------------------------------------------------------------------
# Test 1: stale user_ids are pruned; empty list means "todos"
# ---------------------------------------------------------------------------
def test_stale_user_ids_are_pruned(admin_headers):
    """PUT with a stale user_id → GET should return allowed_user_ids=[] and
    allowed_user_emails=[] (empty = todos)."""
    stale_id = "user_STALE_noexiste_iter278_" + str(int(time.time()))
    put_payload = {
        "business_type": BIZ,
        "product_subcategory": SUB,
        "action_id": ACTION_ID,
        "custom_label": None,
        "enabled": True,
        "required_roles": [],
        "required_cargos": [],
        "allowed_user_ids": [stale_id],
    }
    put_r = requests.put(
        f"{BASE_URL}/api/quote-action-overrides",
        headers=admin_headers,
        json=put_payload,
        timeout=30,
    )
    assert put_r.status_code == 200, f"PUT failed: {put_r.status_code} {put_r.text}"
    assert put_r.json().get("config_key") == CONFIG_KEY

    ov = _get_override(admin_headers, CONFIG_KEY)
    assert ov is not None, f"override {CONFIG_KEY} not found in list"

    # Poda: stale IDs must be pruned from allowed_user_ids
    assert ov.get("allowed_user_ids") == [], (
        f"stale id was NOT pruned. allowed_user_ids={ov.get('allowed_user_ids')}"
    )
    # And allowed_user_emails must be empty since we could not resolve stale id
    assert ov.get("allowed_user_emails") == [], (
        f"allowed_user_emails should be empty for stale id, got {ov.get('allowed_user_emails')}"
    )
    # cleanup for next test
    _delete_override(admin_headers, CONFIG_KEY)


# ---------------------------------------------------------------------------
# Test 2: valid user_id is denormalized into allowed_user_emails
# ---------------------------------------------------------------------------
def test_valid_user_id_denormalizes_email(admin_headers, agodoy_user_id):
    """PUT with agodoy's CURRENT user_id → GET returns allowed_user_emails
    including agodoy@megasoft.com.ve."""
    put_payload = {
        "business_type": BIZ,
        "product_subcategory": SUB,
        "action_id": ACTION_ID,
        "custom_label": None,
        "enabled": True,
        "required_roles": [],
        "required_cargos": [],
        "allowed_user_ids": [agodoy_user_id],
    }
    put_r = requests.put(
        f"{BASE_URL}/api/quote-action-overrides",
        headers=admin_headers,
        json=put_payload,
        timeout=30,
    )
    assert put_r.status_code == 200, f"PUT failed: {put_r.text}"

    ov = _get_override(admin_headers, CONFIG_KEY)
    assert ov is not None, f"override not found"
    # agodoy_user_id is valid → must survive pruning
    assert agodoy_user_id in (ov.get("allowed_user_ids") or []), (
        f"valid user_id {agodoy_user_id} was pruned incorrectly: {ov.get('allowed_user_ids')}"
    )
    emails_lc = [e.lower() for e in (ov.get("allowed_user_emails") or [])]
    assert AGODOY_EMAIL in emails_lc, (
        f"agodoy email missing from allowed_user_emails: {emails_lc}"
    )
    _delete_override(admin_headers, CONFIG_KEY)


# ---------------------------------------------------------------------------
# Test 3: Mix — stale + valid → stale pruned, valid preserved
# ---------------------------------------------------------------------------
def test_mixed_stale_and_valid_ids(admin_headers, agodoy_user_id):
    stale_id = "user_STALE_mix_iter278"
    put_payload = {
        "business_type": BIZ,
        "product_subcategory": SUB,
        "action_id": ACTION_ID,
        "enabled": True,
        "allowed_user_ids": [stale_id, agodoy_user_id],
    }
    put_r = requests.put(
        f"{BASE_URL}/api/quote-action-overrides",
        headers=admin_headers,
        json=put_payload,
        timeout=30,
    )
    assert put_r.status_code == 200, put_r.text

    ov = _get_override(admin_headers, CONFIG_KEY)
    assert ov is not None
    ids = ov.get("allowed_user_ids") or []
    assert stale_id not in ids, f"stale id must be pruned: {ids}"
    assert agodoy_user_id in ids, f"valid id must survive: {ids}"
    emails = [e.lower() for e in (ov.get("allowed_user_emails") or [])]
    assert AGODOY_EMAIL in emails, emails
    _delete_override(admin_headers, CONFIG_KEY)


# ---------------------------------------------------------------------------
# Test 4: Regression — empty allowed_user_ids means todos (emails also empty)
# ---------------------------------------------------------------------------
def test_empty_list_means_todos(admin_headers):
    put_payload = {
        "business_type": BIZ,
        "product_subcategory": SUB,
        "action_id": ACTION_ID,
        "enabled": True,
        "allowed_user_ids": [],
    }
    r = requests.put(
        f"{BASE_URL}/api/quote-action-overrides",
        headers=admin_headers,
        json=put_payload,
        timeout=30,
    )
    assert r.status_code == 200

    ov = _get_override(admin_headers, CONFIG_KEY)
    assert ov is not None
    assert ov.get("allowed_user_ids") == []
    assert ov.get("allowed_user_emails") == []
    _delete_override(admin_headers, CONFIG_KEY)


# ---------------------------------------------------------------------------
# Test 5: agodoy login works (sanity — needed for frontend tests)
# ---------------------------------------------------------------------------
def test_agodoy_login_works():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": AGODOY_EMAIL, "password": "Test1234!"},
        timeout=30,
    )
    assert r.status_code == 200, f"agodoy login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("access_token") or body.get("token")
    assert token
    # Also verify special_permissions includes cotizaciones:equipos
    user = body.get("user") or {}
    sp = user.get("special_permissions") or []
    assert "cotizaciones:equipos" in sp, f"special_permissions missing cotizaciones:equipos: {sp}"
