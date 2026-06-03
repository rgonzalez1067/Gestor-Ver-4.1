"""Backup Center backend tests - validates 9-entity export/import flow"""
import os
import io
import json
import zipfile
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fallback to frontend .env file
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

EXPECTED_MODULES = {
    "clients", "banks", "payment-methods", "hardware",
    "commercial-categories", "inventory-movements", "taller-equipos",
    "user-permissions", "integrators"
}


@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token")


@pytest.fixture
def admin_client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}"})
    return s


# === Entities listing ===
def test_entities_list_returns_9(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/admin/backup-center/entities")
    assert r.status_code == 200
    data = r.json()
    ents = data.get("entities", [])
    assert len(ents) == 9, f"Expected 9 entities, got {len(ents)}"
    modules = {e["module"] for e in ents}
    assert modules == EXPECTED_MODULES, f"Missing/extra modules: got {modules}"
    # check counts are integers
    for e in ents:
        assert "label" in e and "count" in e
        assert isinstance(e["count"], int)


# === Single entity export ===
@pytest.mark.parametrize("module", ["banks", "integrators", "user-permissions"])
def test_export_single_module(admin_client, module):
    r = admin_client.get(f"{BASE_URL}/api/admin/migration/{module}/export")
    assert r.status_code == 200, f"export {module}: {r.status_code} {r.text[:200]}"
    # body must be valid JSON
    payload = r.json()
    assert isinstance(payload, dict) or isinstance(payload, list)


# === ZIP bulk export ===
def test_export_zip_multiple_modules(admin_client):
    modules = ["banks", "integrators", "user-permissions"]
    r = admin_client.post(f"{BASE_URL}/api/admin/backup-center/export-zip",
                          json={"modules": modules})
    assert r.status_code == 200, f"zip export: {r.status_code} {r.text[:200]}"
    # Verify it is a valid ZIP
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert "_manifest.json" in names
    for m in modules:
        assert any(m in n for n in names), f"Module file {m} missing in zip: {names}"


# === Import preview ===
def test_user_permissions_round_trip_idempotent(admin_client):
    # 1. Export
    exp = admin_client.get(f"{BASE_URL}/api/admin/migration/user-permissions/export")
    assert exp.status_code == 200
    file_bytes = exp.content
    # 2. Preview
    files = {"file": ("user_permissions.json", file_bytes, "application/json")}
    prev = admin_client.post(f"{BASE_URL}/api/admin/migration/user-permissions/import-preview",
                             files=files)
    assert prev.status_code == 200, prev.text[:300]
    pdata = prev.json()
    assert "to_create_count" in pdata and "to_update_count" in pdata
    # 3. Apply
    files = {"file": ("user_permissions.json", file_bytes, "application/json")}
    appl = admin_client.post(f"{BASE_URL}/api/admin/migration/user-permissions/import-apply",
                             files=files)
    assert appl.status_code == 200, appl.text[:300]
    adata = appl.json()
    # idempotent => 0 inserted, N updated
    assert adata.get("inserted", 0) == 0, f"Expected 0 inserted on round-trip, got {adata}"
    assert adata.get("updated", 0) > 0


def test_integrators_round_trip_idempotent(admin_client):
    exp = admin_client.get(f"{BASE_URL}/api/admin/migration/integrators/export")
    assert exp.status_code == 200
    fb = exp.content
    files = {"file": ("integrators.json", fb, "application/json")}
    prev = admin_client.post(f"{BASE_URL}/api/admin/migration/integrators/import-preview",
                             files=files)
    assert prev.status_code == 200, prev.text[:200]
    files = {"file": ("integrators.json", fb, "application/json")}
    appl = admin_client.post(f"{BASE_URL}/api/admin/migration/integrators/import-apply",
                             files=files)
    assert appl.status_code == 200, appl.text[:200]
    assert appl.json().get("inserted", 0) == 0


# === Permissions: non-admin must be blocked ===
def test_non_admin_blocked():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "srubio@megasoft.com.ve", "password": "Test1234!"})
    if r.status_code != 200:
        pytest.skip("non-admin user not available")
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    h = {"Authorization": f"Bearer {tok}"}
    r2 = requests.get(f"{BASE_URL}/api/admin/backup-center/entities", headers=h)
    assert r2.status_code in (401, 403), f"Non-admin should be blocked, got {r2.status_code}"
