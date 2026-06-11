"""
Tests for Iteration 60: 
  1. /api/projects/{project_id}/preview-notification returns subject ending with [prefix_label]
     and HTML body non-empty.
  2. Same for target='bank' if project has banks in implementation_matrix.
"""
import os
import re
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
SAMPLE_PROJECT_ID = "prj_62903d69d10a"

PREFIX_LABELS = ["Primer Envío", "Primer Recordatorio", "Segundo Recordatorio", "Tercer Recordatorio"]


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    }, timeout=20)
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}",
    })
    return s


@pytest.fixture(scope="module")
def project(client):
    r = client.get(f"{BASE_URL}/api/projects/{SAMPLE_PROJECT_ID}", timeout=20)
    assert r.status_code == 200, f"Project not accessible: {r.status_code} {r.text[:200]}"
    return r.json()


def _assert_subject_has_prefix_at_end(subject: str):
    # Subject must end with one of the prefix labels in square brackets.
    m = re.search(r"\[(.+?)\]\s*$", subject)
    assert m, f"Subject must end with [prefix]. Got: {subject!r}"
    label = m.group(1)
    assert label in PREFIX_LABELS, f"Unexpected prefix label '{label}'. Subject: {subject!r}"
    # And must NOT start with [prefix]
    assert not subject.lstrip().startswith("["), f"Subject must NOT start with [prefix]. Got: {subject!r}"


# ============== CLIENT TARGET ==============
def test_preview_notification_client_prefix_at_end(client):
    payload = {"target": "client", "to_override": ["x@y.com"]}
    r = client.post(
        f"{BASE_URL}/api/projects/{SAMPLE_PROJECT_ID}/preview-notification",
        json=payload, timeout=30,
    )
    assert r.status_code == 200, f"preview-notification failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    assert "subject" in data, f"No subject in response: {data}"
    assert "html" in data, f"No html in response: {list(data.keys())}"
    print("CLIENT subject:", data["subject"])
    _assert_subject_has_prefix_at_end(data["subject"])
    assert data["html"], "HTML body must not be empty"
    # Should be rendered HTML — contain at least an HTML tag
    assert "<" in data["html"] and ">" in data["html"], "HTML body does not look like HTML"


# ============== BANK TARGET ==============
def test_preview_notification_bank_prefix_at_end(client, project):
    matrix = project.get("implementation_matrix") or {}
    bank_names = list(matrix.keys())
    if not bank_names:
        pytest.skip(f"Project {SAMPLE_PROJECT_ID} has no banks in implementation_matrix")
    bank_name = bank_names[0]
    payload = {"target": "bank", "bank_name": bank_name, "to_override": ["x@y.com"]}
    r = client.post(
        f"{BASE_URL}/api/projects/{SAMPLE_PROJECT_ID}/preview-notification",
        json=payload, timeout=30,
    )
    assert r.status_code == 200, f"preview-notification (bank) failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    print(f"BANK ({bank_name}) subject:", data["subject"])
    _assert_subject_has_prefix_at_end(data["subject"])
    assert data["html"], "HTML body (bank) must not be empty"
    assert "<" in data["html"], "HTML body (bank) does not look like HTML"


# ============== HTML CONTENT IS NOT EMPTY (main bug) ==============
def test_preview_notification_client_html_not_empty(client):
    payload = {"target": "client", "to_override": ["x@y.com"]}
    r = client.post(
        f"{BASE_URL}/api/projects/{SAMPLE_PROJECT_ID}/preview-notification",
        json=payload, timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    # Strip all HTML tags and whitespace, ensure there is text content rendered
    text_only = re.sub(r"<[^>]+>", "", data["html"]).strip()
    assert len(text_only) > 20, f"Rendered text content is too short: {text_only!r}"
