# ruff: noqa
"""
Iter 180 — Initial Contacts: DELETE (admin-only) + flexible phone/email + transfer payload.

Covers:
  - POST /api/initial-contacts with only phone (no email) → 200
  - POST /api/initial-contacts with only email (no phone) → 200
  - POST /api/initial-contacts with neither phone nor email → backend permits (201/200)
  - POST /api/initial-contacts/{id}/transfer accepts {target_user_id, comment}
  - DELETE /api/initial-contacts/{id} as admin → 200
  - DELETE /api/initial-contacts/{id} unknown id → 404
  - DELETE on already-converted contact → 409
"""
import os
import pytest
import requests
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://action-key-mismatch.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "ragg1008@gmail.com"
ADMIN_PASSWORD = "admin123"


# -------- Fixtures --------
@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed status={r.status_code} body={r.text[:200]}")
    token = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {r.json()}")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def cleanup_ids():
    created = []
    yield created
    # Best-effort cleanup
    try:
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        token = r.json().get("session_token") or r.json().get("token")
        if token:
            s.headers.update({"Authorization": f"Bearer {token}"})
            for cid in created:
                s.delete(f"{BASE_URL}/api/initial-contacts/{cid}")
    except Exception:
        pass


# -------- Create: phone/email flexibility --------
class TestCreateFlexibleContact:
    def test_create_with_only_phone(self, admin_client, cleanup_ids):
        payload = {
            "contact_name": "TEST_OnlyPhone Person",
            "phone": "+58 412 0000001",
            "email": "",
            "legal_name": f"TEST_OnlyPhone_{uuid.uuid4().hex[:6]}",
        }
        r = admin_client.post(f"{BASE_URL}/api/initial-contacts", json=payload)
        assert r.status_code in (200, 201), f"status={r.status_code} body={r.text[:200]}"
        data = r.json()
        assert data["phone"] == payload["phone"]
        assert data["email"] == ""
        assert data["contact_id"].startswith("ic_")
        cleanup_ids.append(data["contact_id"])

    def test_create_with_only_email(self, admin_client, cleanup_ids):
        payload = {
            "contact_name": "TEST_OnlyEmail Person",
            "phone": "",
            "email": "test_onlyemail@example.com",
            "legal_name": f"TEST_OnlyEmail_{uuid.uuid4().hex[:6]}",
        }
        r = admin_client.post(f"{BASE_URL}/api/initial-contacts", json=payload)
        assert r.status_code in (200, 201), f"status={r.status_code} body={r.text[:200]}"
        data = r.json()
        assert data["email"] == payload["email"]
        assert data["phone"] == ""
        cleanup_ids.append(data["contact_id"])

    def test_create_with_neither(self, admin_client, cleanup_ids):
        # Backend does not enforce; frontend does. Validate backend acceptance.
        payload = {
            "contact_name": "TEST_NoContact Person",
            "phone": "",
            "email": "",
            "legal_name": f"TEST_NoContact_{uuid.uuid4().hex[:6]}",
        }
        r = admin_client.post(f"{BASE_URL}/api/initial-contacts", json=payload)
        assert r.status_code in (200, 201), f"Backend must allow both empty; got {r.status_code}"
        data = r.json()
        cleanup_ids.append(data["contact_id"])


# -------- Transfer --------
class TestTransferPayload:
    def test_transfer_accepts_target_user_id_and_comment(self, admin_client, cleanup_ids):
        # Create contact
        legal = f"TEST_Transfer_{uuid.uuid4().hex[:6]}"
        cr = admin_client.post(f"{BASE_URL}/api/initial-contacts", json={
            "contact_name": "TEST_Transfer Person",
            "phone": "+58 412 9999999",
            "legal_name": legal,
        })
        assert cr.status_code in (200, 201), cr.text[:200]
        cid = cr.json()["contact_id"]
        cleanup_ids.append(cid)

        # Pick a target user (any active user other than me)
        me = admin_client.get(f"{BASE_URL}/api/auth/me").json()
        users = admin_client.get(f"{BASE_URL}/api/auth/users").json() or []
        target = next((u for u in users if u.get("user_id") != me.get("user_id") and u.get("is_active", True)), None)
        if not target:
            pytest.skip("No alternate target user available for transfer test")

        r = admin_client.post(
            f"{BASE_URL}/api/initial-contacts/{cid}/transfer",
            json={"target_user_id": target["user_id"], "comment": "TEST transfer comment"},
        )
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
        # Verify persisted in bitacora via GET
        detail = admin_client.get(f"{BASE_URL}/api/initial-contacts/{cid}").json()
        actions = [e.get("action") for e in detail.get("bitacora", [])]
        assert "transferred" in actions, f"Expected 'transferred' entry; bitacora={actions}"
        assert detail["assigned_to_user_id"] == target["user_id"]

    def test_transfer_missing_target_returns_422(self, admin_client, cleanup_ids):
        cr = admin_client.post(f"{BASE_URL}/api/initial-contacts", json={
            "contact_name": "TEST_TransferBad",
            "phone": "+58 412 8888888",
            "legal_name": f"TEST_TransferBad_{uuid.uuid4().hex[:6]}",
        })
        cid = cr.json()["contact_id"]
        cleanup_ids.append(cid)
        r = admin_client.post(f"{BASE_URL}/api/initial-contacts/{cid}/transfer", json={"comment": "no target"})
        assert r.status_code in (400, 422), f"Expected 422/400; got {r.status_code}"


# -------- Delete --------
class TestDeleteAdmin:
    def test_delete_as_admin_success(self, admin_client):
        cr = admin_client.post(f"{BASE_URL}/api/initial-contacts", json={
            "contact_name": "TEST_Delete Person",
            "phone": "+58 412 7777777",
            "legal_name": f"TEST_Delete_{uuid.uuid4().hex[:6]}",
        })
        assert cr.status_code in (200, 201), cr.text[:200]
        cid = cr.json()["contact_id"]

        r = admin_client.delete(f"{BASE_URL}/api/initial-contacts/{cid}")
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"

        # Verify it no longer exists
        g = admin_client.get(f"{BASE_URL}/api/initial-contacts/{cid}")
        assert g.status_code == 404, f"Expected 404 after delete; got {g.status_code}"

    def test_delete_unknown_id_returns_404(self, admin_client):
        r = admin_client.delete(f"{BASE_URL}/api/initial-contacts/ic_doesnotexist_xyz")
        assert r.status_code == 404

    def test_delete_converted_returns_409(self, admin_client, cleanup_ids):
        # Create a contact, convert it, then try deleting
        legal = f"TEST_ConvThenDel_{uuid.uuid4().hex[:6]}"
        cr = admin_client.post(f"{BASE_URL}/api/initial-contacts", json={
            "contact_name": "TEST_ConvThenDel",
            "phone": "+58 412 6666666",
            "legal_name": legal,
        })
        cid = cr.json()["contact_id"]
        cleanup_ids.append(cid)

        conv = admin_client.post(f"{BASE_URL}/api/initial-contacts/{cid}/convert")
        if conv.status_code != 200:
            pytest.skip(f"Could not convert to test 409 path: {conv.status_code} {conv.text[:200]}")
        client_id = conv.json().get("client_id")

        r = admin_client.delete(f"{BASE_URL}/api/initial-contacts/{cid}")
        assert r.status_code == 409, f"Expected 409 on converted; got {r.status_code} body={r.text[:200]}"

        # Cleanup the client produced by conversion
        if client_id:
            try:
                admin_client.delete(f"{BASE_URL}/api/clients/{client_id}")
            except Exception:
                pass
