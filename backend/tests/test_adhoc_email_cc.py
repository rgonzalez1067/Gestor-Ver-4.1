"""
Iteration 65 — Tests for POST /api/projects/{project_id}/send-adhoc-email
Validates the new 'additional_recipients' (CC) form field:
- Sends email with CC list, returns {recipients, cc, message}
- Backward compatibility without additional_recipients
- Bitacora records CC in email_detail.cc and text contains 'CC:'
"""
import os
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    token = j.get("session_token") or j.get("token") or j.get("access_token")
    assert token
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def project_id(headers):
    """Pick the first available project."""
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=20)
    assert r.status_code == 200, f"GET /projects failed: {r.status_code}"
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("projects") or []
    assert items, "No projects available for testing"
    pid = items[0].get("project_id") or items[0].get("id")
    assert pid
    return pid


def _send_adhoc(headers, project_id, recipients, cc=None, subject="TEST_iter65 Adhoc"):
    form = {
        "recipients": json.dumps(recipients),
        "subject": subject,
        "message": "Mensaje de prueba iter65 — homologación CC.",
        "matrix_html": "",
    }
    if cc is not None:
        form["additional_recipients"] = json.dumps(cc)
    return requests.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=headers,
        data=form,
        timeout=60,
    )


# === FEATURE: send-adhoc-email with CC ===

def test_adhoc_email_with_cc_returns_recipients_and_cc(headers, project_id):
    to_list = ["TEST_adhoc_to@example.com"]
    cc_list = ["TEST_adhoc_cc1@example.com", "TEST_adhoc_cc2@example.com"]
    r = _send_adhoc(headers, project_id, to_list, cc=cc_list,
                    subject="TEST_iter65 Adhoc with CC")
    assert r.status_code == 200, f"adhoc-email failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("recipients") == to_list
    assert data.get("cc") == cc_list
    # message must include total count = TO + CC
    assert "3 destinatario" in data.get("message", ""), data.get("message")
    assert data.get("status") in ("sent", "simulated", "queued", "skipped", "error", "ok")
    assert "bitacora_entry_id" in data


def test_adhoc_email_without_cc_backward_compat(headers, project_id):
    to_list = ["TEST_adhoc_only_to@example.com"]
    r = _send_adhoc(headers, project_id, to_list, cc=None,
                    subject="TEST_iter65 Adhoc without CC")
    assert r.status_code == 200, f"backcompat failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("recipients") == to_list
    assert data.get("cc") == []
    assert "1 destinatario" in data.get("message", "")


def test_adhoc_email_with_empty_cc_array(headers, project_id):
    to_list = ["TEST_adhoc_empty_cc@example.com"]
    r = _send_adhoc(headers, project_id, to_list, cc=[],
                    subject="TEST_iter65 Adhoc empty CC")
    assert r.status_code == 200
    data = r.json()
    assert data.get("cc") == []


def test_adhoc_email_cc_filters_invalid_entries(headers, project_id):
    to_list = ["TEST_adhoc_filter@example.com"]
    cc_list = ["TEST_valid@example.com", "", "noemail-string", None, 123]
    # Backend should keep only valid emails
    form = {
        "recipients": json.dumps(to_list),
        "additional_recipients": json.dumps(cc_list),
        "subject": "TEST_iter65 Adhoc filter invalid CC",
        "message": "Filter test",
        "matrix_html": "",
    }
    r = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=headers, data=form, timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("cc") == ["TEST_valid@example.com"]


# === FEATURE: bitacora records CC ===

def test_bitacora_records_cc_in_email_detail(headers, project_id):
    to_list = ["TEST_bitacora_to@example.com"]
    cc_list = ["TEST_bitacora_cc1@example.com", "TEST_bitacora_cc2@example.com"]
    subject = "TEST_iter65 Bitacora CC"
    r = _send_adhoc(headers, project_id, to_list, cc=cc_list, subject=subject)
    assert r.status_code == 200, r.text
    entry_id = r.json().get("bitacora_entry_id")
    assert entry_id

    # GET bitacora and find the entry
    rb = requests.get(f"{BASE_URL}/api/projects/{project_id}/bitacora",
                      headers=headers, timeout=20)
    assert rb.status_code == 200
    entries = rb.json()
    found = next((e for e in entries if e.get("entry_id") == entry_id), None)
    assert found, f"Bitacora entry {entry_id} not found"
    # email_detail.cc must equal cc_list
    assert found.get("email_detail", {}).get("cc") == cc_list
    # text must contain 'CC:' and the CC emails
    text = found.get("text", "")
    assert "CC:" in text, f"text without 'CC:': {text}"
    for cc in cc_list:
        assert cc in text, f"cc {cc} missing from bitacora text"
    # text must also contain [Otras Notificaciones]
    assert "[Otras Notificaciones]" in text


def test_bitacora_without_cc_has_empty_cc_no_cc_tag(headers, project_id):
    to_list = ["TEST_bitacora_no_cc@example.com"]
    subject = "TEST_iter65 Bitacora sin CC"
    r = _send_adhoc(headers, project_id, to_list, cc=None, subject=subject)
    assert r.status_code == 200
    entry_id = r.json()["bitacora_entry_id"]
    rb = requests.get(f"{BASE_URL}/api/projects/{project_id}/bitacora",
                      headers=headers, timeout=20)
    entries = rb.json()
    found = next((e for e in entries if e.get("entry_id") == entry_id), None)
    assert found
    assert found.get("email_detail", {}).get("cc") == []
    assert "CC:" not in found.get("text", "")


# === Strategic internal-emails endpoint used by InternalEmailInput ===

def test_internal_emails_strategic_profile(headers):
    r = requests.get(f"{BASE_URL}/api/users/internal-emails?profile=strategic",
                     headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    # Accept either {users: [...]} or list
    items = data if isinstance(data, list) else data.get("users") or data.get("items") or []
    assert isinstance(items, list)
    # Each item should have an email
    for u in items[:5]:
        assert "email" in u or "Email" in u
