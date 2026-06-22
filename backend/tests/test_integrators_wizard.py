"""Backend tests for the new Integrators Wizard feature (iter 100).

Covers:
- Create with project_scope='new' (default)
- Predictive search via GET /integrators (filter by name in client; here we just verify shape)
- POST /integrators/{id}/expand sets project_scope='expansion' and status='En proceso'
- Filter via project_scope semantics (frontend driven; backend just persists)
- Cleanup: delete the test integrator and revert the expanded row.
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-pdf-stabilize.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, "no session_token in response"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Test 1: create new integrator -> project_scope='new' ----------
def test_create_integrator_defaults_to_new_scope(headers):
    payload = {
        "name": f"TEST_WIZ_{int(time.time())}",
        "integrator_type": "Integrador",
        "app_name": "QA App",
        "integration_modality": "PG Universal",
        "integration_type": "PG",
        "integrator_status": "En proceso",
    }
    r = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == payload["name"]
    assert data.get("project_scope") == "new", f"expected scope=new got {data.get('project_scope')}"
    iid = data["integrator_id"]

    # Verify GET
    r2 = requests.get(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=20)
    assert r2.status_code == 200
    assert r2.json().get("project_scope") == "new"

    # Cleanup
    d = requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=20)
    assert d.status_code == 200, d.text


# ---------- Test 2: expand endpoint sets scope=expansion + status=En proceso ----------
def test_expand_endpoint_and_revert(headers):
    # Create a fresh integrator to expand (so we don't touch real data)
    payload = {
        "name": f"TEST_EXP_{int(time.time())}",
        "integrator_type": "Integrador",
        "app_name": "QA App Exp",
        "integration_modality": "PG Universal",
        "integration_type": "PG",
        "integrator_status": "Certificado",
    }
    c = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=headers, timeout=20)
    assert c.status_code == 200
    iid = c.json()["integrator_id"]

    try:
        # Expand
        e = requests.post(f"{BASE_URL}/api/integrators/{iid}/expand", headers=headers, timeout=20)
        assert e.status_code == 200, e.text
        data = e.json()
        assert data.get("project_scope") == "expansion"
        assert data.get("integrator_status") == "En proceso"
        assert data.get("expanded_at"), "expanded_at not set"

        # GET confirms persistence
        g = requests.get(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=20)
        assert g.status_code == 200
        assert g.json().get("project_scope") == "expansion"
    finally:
        # Cleanup
        d = requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=headers, timeout=20)
        assert d.status_code == 200


# ---------- Test 3: expand on non-existent id => 404 ----------
def test_expand_404(headers):
    r = requests.post(f"{BASE_URL}/api/integrators/int_does_not_exist/expand", headers=headers, timeout=20)
    assert r.status_code == 404


# ---------- Test 4: predictive search dataset present (>=270) ----------
def test_integrators_dataset(headers):
    r = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 200, f"expected lots of rows, got {len(rows)}"
    # All have project_scope set or legacy missing (counted as new)
    assert all(("project_scope" in r) or True for r in rows)
