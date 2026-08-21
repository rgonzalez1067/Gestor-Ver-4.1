"""
Tests for 'Último Seguimiento' feature (iter 319):
- Backend: bitacora updates last_followup_at only.
- Backend: send-notification target=client updates last_contact_at + last_followup_at + last_qualified_activity_at.
- Backend: send-adhoc-email updates all three timestamps.
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-overhaul.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
PROJECT_ID = "prj_e86a47af1bff"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token")
    assert tok, f"no token in response: {list(data.keys())}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get_project(headers):
    r = requests.get(f"{API}/projects/{PROJECT_ID}", headers=headers, timeout=30)
    assert r.status_code == 200, f"get project failed: {r.status_code} {r.text[:200]}"
    return r.json()


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _same_day_utc(iso_str):
    dt = _parse_iso(iso_str)
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return abs((now - dt).total_seconds()) < 3600  # within 1 hour = "today/now"


def test_project_exists_and_has_implementer(headers):
    p = _get_project(headers)
    assert p.get("project_id") == PROJECT_ID
    assert p.get("assigned_to_name"), "project must have assigned_to_name to render 'Último Seguimiento'"
    assert p.get("status") == "En Gestión", f"expected status 'En Gestión', got {p.get('status')}"


def test_A_bitacora_updates_only_last_followup(headers):
    before = _get_project(headers)
    prev_contact = before.get("last_contact_at")
    prev_qualified = before.get("last_qualified_activity_at")

    r = requests.post(
        f"{API}/projects/{PROJECT_ID}/bitacora",
        headers={**headers, "Content-Type": "application/json"},
        json={"text": "[TEST_iter319] verificación bitácora", "execution_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
        timeout=30,
    )
    assert r.status_code == 200, f"bitacora post failed: {r.status_code} {r.text[:200]}"

    after = _get_project(headers)
    assert _same_day_utc(after.get("last_followup_at")), f"last_followup_at not updated: {after.get('last_followup_at')}"
    # last_contact_at MUST NOT change
    assert after.get("last_contact_at") == prev_contact, (
        f"last_contact_at should NOT change on bitacora. before={prev_contact} after={after.get('last_contact_at')}"
    )
    # last_qualified_activity_at MUST NOT change
    assert after.get("last_qualified_activity_at") == prev_qualified, (
        f"last_qualified_activity_at should NOT change on bitacora. before={prev_qualified} after={after.get('last_qualified_activity_at')}"
    )


def test_B_send_notification_client_updates_all_and_resets_business_days(headers):
    r = requests.post(
        f"{API}/projects/{PROJECT_ID}/send-notification",
        headers=headers,
        data={"target": "client"},
        timeout=90,
    )
    assert r.status_code == 200, f"send-notification failed: {r.status_code} {r.text[:300]}"

    after = _get_project(headers)
    assert _same_day_utc(after.get("last_followup_at")), "last_followup_at not today"
    assert _same_day_utc(after.get("last_contact_at")), "last_contact_at not today"
    assert _same_day_utc(after.get("last_qualified_activity_at")), "last_qualified_activity_at not today"
    # business_days_in_state may be recomputed on read; if present should be 0
    bdis = after.get("business_days_in_state")
    if bdis is not None:
        assert bdis == 0, f"business_days_in_state expected 0 (green bar), got {bdis}"


def test_C_send_adhoc_email_updates_all(headers):
    r = requests.post(
        f"{API}/projects/{PROJECT_ID}/send-adhoc-email",
        headers=headers,
        data={
            "recipients": '["qa+test@example.com"]',
            "subject": "[TEST_iter319] adhoc",
            "message": "<p>test adhoc</p>",
        },
        timeout=90,
    )
    assert r.status_code == 200, f"send-adhoc-email failed: {r.status_code} {r.text[:300]}"

    after = _get_project(headers)
    assert _same_day_utc(after.get("last_followup_at")), "last_followup_at not today"
    assert _same_day_utc(after.get("last_contact_at")), "last_contact_at not today"
    assert _same_day_utc(after.get("last_qualified_activity_at")), "last_qualified_activity_at not today"
