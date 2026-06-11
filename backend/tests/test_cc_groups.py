"""Iter64 — CRUD de grupos de destinatarios CC reutilizables.
Endpoints: POST/GET/DELETE /api/cc-groups
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert token, f"No token in {r.json()}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def created_ids():
    return []


def _cleanup(ids, headers):
    for gid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/cc-groups/{gid}", headers=headers, timeout=10)
        except Exception:
            pass


# ---------- BASIC CRUD ----------

class TestCcGroupsCrud:
    def test_list_initial(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/cc-groups", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Ensure no _id leaks
        for g in data:
            assert "_id" not in g
            assert "name_lower" not in g

    def test_create_valid(self, auth_headers, created_ids):
        name = f"TEST_iter64_{uuid.uuid4().hex[:6]}"
        payload = {"name": name, "emails": ["A@test.com", "b@test.com", "a@test.com"]}
        r = requests.post(f"{BASE_URL}/api/cc-groups", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == name
        # Dedupe case-insensitive: a@test.com duplicado debe eliminarse → 2 correos
        assert len(body["emails"]) == 2
        assert "group_id" in body
        assert "_id" not in body and "name_lower" not in body
        created_ids.append(body["group_id"])

        # GET verify persistence + sort by name
        rg = requests.get(f"{BASE_URL}/api/cc-groups", headers=auth_headers, timeout=15)
        assert rg.status_code == 200
        names = [g["name"] for g in rg.json()]
        assert name in names
        names_lower = [n.lower() for n in names]
        assert names_lower == sorted(names_lower)

    def test_create_empty_name_400(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/cc-groups",
                          json={"name": "  ", "emails": ["x@y.com"]},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_create_no_valid_emails_400(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/cc-groups",
                          json={"name": "TEST_empty", "emails": ["", "no-arroba", "  "]},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_create_updates_when_name_exists(self, auth_headers, created_ids):
        name = f"TEST_iter64_upd_{uuid.uuid4().hex[:5]}"
        r1 = requests.post(f"{BASE_URL}/api/cc-groups",
                           json={"name": name, "emails": ["one@x.com"]},
                           headers=auth_headers, timeout=15)
        assert r1.status_code == 200
        gid1 = r1.json()["group_id"]
        created_ids.append(gid1)

        r2 = requests.post(f"{BASE_URL}/api/cc-groups",
                           json={"name": name, "emails": ["two@x.com", "three@x.com"]},
                           headers=auth_headers, timeout=15)
        assert r2.status_code == 200
        body = r2.json()
        # Mismo group_id, emails reemplazados
        assert body["group_id"] == gid1
        assert set(e.lower() for e in body["emails"]) == {"two@x.com", "three@x.com"}

    def test_delete_existing_and_404(self, auth_headers, created_ids):
        # Create transient
        r = requests.post(f"{BASE_URL}/api/cc-groups",
                          json={"name": f"TEST_del_{uuid.uuid4().hex[:5]}",
                                "emails": ["del@x.com"]},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200
        gid = r.json()["group_id"]

        d = requests.delete(f"{BASE_URL}/api/cc-groups/{gid}", headers=auth_headers, timeout=15)
        assert d.status_code == 200

        # GET no longer present
        listing = requests.get(f"{BASE_URL}/api/cc-groups", headers=auth_headers, timeout=15).json()
        assert all(g.get("group_id") != gid for g in listing)

        # 404 second delete
        d2 = requests.delete(f"{BASE_URL}/api/cc-groups/{gid}", headers=auth_headers, timeout=15)
        assert d2.status_code == 404

    def test_zzz_cleanup(self, auth_headers, created_ids):
        _cleanup(created_ids, auth_headers)
