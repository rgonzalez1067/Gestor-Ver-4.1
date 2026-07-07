"""
Iter 48 - MegaNexus 5-task package backend verification.

Covers:
  A) Quote channel resolution for Gateway/LinkPago (CORP segment derived from client).
  B) Inbox batch-delete endpoint (soft delete only user's selected messages).
  C) RBAC + audit trail for PUT /initial-contacts/{id} (admin only, bitacora entry).
  E) Branding: HTML title is 'CRM Gestor - Mega Soft' and 'emergent-badge' is absent.
  REGRESSION) POST /initial-contacts/{id}/assign still routable (decorator restored).
"""
import os
import re
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://heartbeat-clean.preview.emergentagent.com").rstrip("/")

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
USER = {"email": "srubio@megasoft.com.ve", "password": "Test1234!"}


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} -> {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("session_token") or data.get("token")
    assert tok, f"no session_token in login response: {data.keys()}"
    return tok


@pytest.fixture(scope="session")
def admin_token() -> str:
    return _login(ADMIN["email"], ADMIN["password"])


@pytest.fixture(scope="session")
def user_token() -> str:
    return _login(USER["email"], USER["password"])


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


# ====================== A) Quote channel CORP / PYME ======================
class TestQuoteChannelGateway:
    def _find_client(self, headers, predicate, label):
        r = requests.get(f"{BASE_URL}/api/clients", headers=headers, timeout=20)
        assert r.status_code == 200, f"GET /clients -> {r.status_code}"
        clients = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        for c in clients:
            if predicate(c):
                return c
        pytest.skip(f"No {label} client found in DB to validate channel resolution")

    def test_corporativo_client_yields_corp_segment(self, admin_headers):
        # Find a Corporativo client
        c = self._find_client(
            admin_headers,
            lambda c: (c.get("segment") or "").strip().lower() in ("corporativo", "corp"),
            "Corporativo",
        )
        client_id = c.get("client_id") or c.get("id")
        payload = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "pg_setup_items": [{"concepto": "Setup TEST_iter48", "costo": 100.0}],
            "notes": "TEST_iter48 - corp gateway channel",
        }
        r = requests.post(f"{BASE_URL}/api/quotes", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create quote -> {r.status_code}: {r.text[:300]}"
        q = r.json()
        assert q.get("client_segment") == "CORP", (
            f"Expected client_segment=CORP for Corporativo client + GATEWAY, got {q.get('client_segment')}"
        )
        assert q.get("quote_type") == "GATEWAY"

    def test_pyme_client_yields_pyme_segment(self, admin_headers):
        c = self._find_client(
            admin_headers,
            lambda c: (c.get("segment") or "").strip().lower() in ("pymes", "pyme", "emprendedor", "mixto"),
            "Pymes",
        )
        client_id = c.get("client_id") or c.get("id")
        payload = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "LINK_PAGO",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "pg_setup_items": [{"concepto": "Setup TEST_iter48 link", "costo": 50.0}],
            "notes": "TEST_iter48 - pyme link channel",
        }
        r = requests.post(f"{BASE_URL}/api/quotes", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create quote -> {r.status_code}: {r.text[:300]}"
        q = r.json()
        assert q.get("client_segment") == "PYME", (
            f"Expected client_segment=PYME for Pymes client + LINK_PAGO, got {q.get('client_segment')}"
        )


# ====================== B) Inbox batch-delete ======================
class TestInboxBatchDelete:
    def test_batch_delete_empty_returns_400(self, user_headers):
        r = requests.post(f"{BASE_URL}/api/inbox/batch-delete", headers=user_headers, json={"message_ids": []}, timeout=15)
        assert r.status_code == 400, f"expected 400 for empty ids, got {r.status_code}: {r.text[:200]}"

    def test_batch_delete_unknown_ids_returns_200_zero(self, user_headers):
        fake = [f"msg_TEST_{uuid.uuid4().hex[:8]}" for _ in range(2)]
        r = requests.post(f"{BASE_URL}/api/inbox/batch-delete", headers=user_headers, json={"message_ids": fake}, timeout=15)
        assert r.status_code == 200, f"unknown ids should return 200, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("status") == "deleted"
        assert body.get("requested") == 2
        assert body.get("deleted_count") == 0  # nothing matched

    def test_batch_delete_real_message_isolates_to_owner(self, user_headers):
        # List my inbox; if there's any message, try to delete one and verify it disappears.
        r = requests.get(f"{BASE_URL}/api/inbox", headers=user_headers, timeout=15)
        if r.status_code != 200:
            pytest.skip(f"GET /inbox not available for user: {r.status_code}")
        body = r.json()
        msgs = body if isinstance(body, list) else body.get("messages") or body.get("items") or []
        if not msgs:
            pytest.skip("No inbox messages for srubio - skipping live delete check")
        target = msgs[0]
        mid = target.get("message_id") or target.get("id")
        assert mid, f"no message_id field: keys={list(target.keys())}"
        rr = requests.post(f"{BASE_URL}/api/inbox/batch-delete", headers=user_headers, json={"message_ids": [mid]}, timeout=15)
        assert rr.status_code == 200, f"batch-delete -> {rr.status_code}: {rr.text[:200]}"
        out = rr.json()
        assert out.get("deleted_count") == 1, f"expected 1 deleted, got {out}"
        # Confirm message no longer in inbox listing
        r2 = requests.get(f"{BASE_URL}/api/inbox", headers=user_headers, timeout=15)
        if r2.status_code == 200:
            body2 = r2.json()
            msgs2 = body2 if isinstance(body2, list) else body2.get("messages") or body2.get("items") or []
            remaining_ids = {(m.get("message_id") or m.get("id")) for m in msgs2}
            assert mid not in remaining_ids, "Message still present after batch-delete"


# ====================== C) RBAC PUT /initial-contacts/{id} ======================
class TestInitialContactEdit:
    @pytest.fixture(scope="class")
    def seed_contact(self, admin_headers):
        payload = {
            "contact_name": "TEST_iter48 Contact",
            "legal_name": "TEST_iter48 Empresa",
            "phone": "04141111111",
            "email": "test_iter48@example.com",
            "sede": "PYME",
            "interest_notes": "creado por test iter48",
        }
        r = requests.post(f"{BASE_URL}/api/initial-contacts", headers=admin_headers, json=payload, timeout=20)
        assert r.status_code in (200, 201), f"seed create -> {r.status_code}: {r.text[:200]}"
        return r.json()

    def test_non_admin_cannot_edit(self, user_headers, seed_contact):
        cid = seed_contact.get("contact_id") or seed_contact.get("id")
        assert cid
        r = requests.put(f"{BASE_URL}/api/initial-contacts/{cid}", headers=user_headers,
                          json={"contact_name": "NoAdminCannotChange"}, timeout=15)
        assert r.status_code == 403, f"expected 403 non-admin, got {r.status_code}: {r.text[:200]}"

    def test_admin_can_edit_and_bitacora_records_change(self, admin_headers, seed_contact):
        cid = seed_contact.get("contact_id") or seed_contact.get("id")
        new_name = f"TEST_iter48 Edited {uuid.uuid4().hex[:4]}"
        r = requests.put(f"{BASE_URL}/api/initial-contacts/{cid}", headers=admin_headers,
                          json={"contact_name": new_name, "sede": "CORP"}, timeout=20)
        assert r.status_code == 200, f"admin edit -> {r.status_code}: {r.text[:200]}"
        updated = r.json()
        assert updated.get("contact_name") == new_name
        assert updated.get("sede") == "CORP"
        # bitacora entry with action='edited' must be present
        bitacora = updated.get("bitacora") or []
        actions = [e.get("action") for e in bitacora]
        assert "edited" in actions, f"no 'edited' entry in bitacora actions={actions}"

    def test_admin_edit_invalid_sede_returns_400(self, admin_headers, seed_contact):
        cid = seed_contact.get("contact_id") or seed_contact.get("id")
        r = requests.put(f"{BASE_URL}/api/initial-contacts/{cid}", headers=admin_headers,
                          json={"sede": "INVALID"}, timeout=15)
        assert r.status_code == 400, f"expected 400 invalid sede, got {r.status_code}"


# ====================== Regression: assign endpoint still routable ======================
class TestAssignEndpointRegression:
    def test_assign_endpoint_exists(self, admin_headers):
        # Hit assign with a clearly invalid contact_id; we must NOT get 405 (method not allowed)
        # nor 404 from the router. We expect 404 contact-not-found OR 422 validation.
        bogus_cid = f"contact_TEST_nonexistent_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{BASE_URL}/api/initial-contacts/{bogus_cid}/assign",
            headers=admin_headers,
            json={"assigned_to_user_id": "user_TEST_does_not_exist"},
            timeout=15,
        )
        assert r.status_code != 405, "Assign route is not registered (405 method not allowed)"
        # Acceptable: 404 (contact/user not found) or 403 (hierarchy)
        assert r.status_code in (404, 403, 400, 422), f"unexpected status {r.status_code}: {r.text[:200]}"


# ====================== E) Branding white-label ======================
class TestBranding:
    def test_title_and_no_emergent_badge(self):
        r = requests.get(f"{BASE_URL}/", timeout=20)
        assert r.status_code == 200, f"frontend index -> {r.status_code}"
        html = r.text
        # Title
        m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        assert m, "No <title> tag in served index.html"
        assert "CRM Gestor - Mega Soft" in m.group(1), f"Unexpected title: {m.group(1)!r}"
        # Badge removed from public/index.html
        assert 'id="emergent-badge"' not in html, "emergent-badge element is still present in served index.html"
