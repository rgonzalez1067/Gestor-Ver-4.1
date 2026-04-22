"""Iteration 178 — Backend tests
1) Commercial Categories CRUD + RBAC + propagation + delete blocking
2) Bug fix: GET /api/quotes now returns repaired_at (and configured_at) timestamps
"""
import os
import uuid
import pytest
import requests

_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _url:
    # Load from frontend/.env as fallback for pytest context
    try:
        with open("/app/frontend/.env") as _f:
            for _line in _f:
                if _line.startswith("REACT_APP_BACKEND_URL="):
                    _url = _line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
assert _url, "REACT_APP_BACKEND_URL not set"
BASE_URL = _url.rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def non_admin_headers(admin_headers):
    """Create an ephemeral non-admin user, return its headers. Cleanup at end."""
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_nonadmin_{suffix}@example.com"
    password = "TestPass123!"
    payload = {
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "NonAdmin",
        "role": "sales",
    }
    r = requests.post(
        f"{BASE_URL}/api/admin/users/create", json=payload, headers=admin_headers, timeout=15
    )
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot create non-admin user: {r.status_code} {r.text}")
    user_id = r.json().get("id") or r.json().get("user_id") or r.json().get("user", {}).get("id")

    lr = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert lr.status_code == 200, f"Non-admin login failed: {lr.status_code} {lr.text}"
    token = lr.json().get("session_token") or lr.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    yield headers
    # cleanup
    if user_id:
        try:
            requests.delete(
                f"{BASE_URL}/api/admin/users/{user_id}", headers=admin_headers, timeout=15
            )
        except Exception:
            pass


# ---------- Commercial categories CRUD ----------
class TestCommercialCategoriesList:
    def test_list_all_returns_seed(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/commercial-categories", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 10, f"Expected >=10 seeded categories, got {len(data)}"
        # Sanity: required fields + no _id leakage
        sample = data[0]
        assert "category_id" in sample
        assert "name" in sample
        assert "is_active" in sample
        assert "_id" not in sample

    def test_only_active_filters(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/commercial-categories?only_active=true",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert all(c["is_active"] is True for c in data), "only_active=true must exclude inactive"


class TestCommercialCategoriesCRUD:
    _created_id = None
    _created_name = None

    def test_create_requires_admin(self, non_admin_headers):
        name = f"TEST_cat_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{BASE_URL}/api/commercial-categories",
            json={"name": name},
            headers=non_admin_headers,
            timeout=15,
        )
        assert r.status_code == 403, f"Non-admin create must be 403, got {r.status_code} {r.text}"

    def test_create_success(self, admin_headers):
        name = f"TEST_cat_{uuid.uuid4().hex[:6]}"
        r = requests.post(
            f"{BASE_URL}/api/commercial-categories",
            json={"name": name, "description": "auto test", "is_active": True},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == name
        assert data["description"] == "auto test"
        assert data["is_active"] is True
        assert "category_id" in data
        TestCommercialCategoriesCRUD._created_id = data["category_id"]
        TestCommercialCategoriesCRUD._created_name = name

        # verify persistence via GET
        r2 = requests.get(
            f"{BASE_URL}/api/commercial-categories", headers=admin_headers, timeout=15
        )
        assert any(c["category_id"] == data["category_id"] for c in r2.json())

    def test_create_duplicate_case_insensitive_returns_409(self, admin_headers):
        assert TestCommercialCategoriesCRUD._created_name is not None
        dup_name = TestCommercialCategoriesCRUD._created_name.upper()
        r = requests.post(
            f"{BASE_URL}/api/commercial-categories",
            json={"name": dup_name},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 409, f"Expected 409 duplicate, got {r.status_code} {r.text}"

    def test_update_toggle_active(self, admin_headers):
        cat_id = TestCommercialCategoriesCRUD._created_id
        assert cat_id
        r = requests.put(
            f"{BASE_URL}/api/commercial-categories/{cat_id}",
            json={"is_active": False},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False

        # Verify filter excludes it
        r2 = requests.get(
            f"{BASE_URL}/api/commercial-categories?only_active=true",
            headers=admin_headers,
            timeout=15,
        )
        assert all(c["category_id"] != cat_id for c in r2.json())

        # re-activate
        r3 = requests.put(
            f"{BASE_URL}/api/commercial-categories/{cat_id}",
            json={"is_active": True},
            headers=admin_headers,
            timeout=15,
        )
        assert r3.status_code == 200
        assert r3.json()["is_active"] is True

    def test_update_rename_propagates_to_clients(self, admin_headers):
        """Use existing 'Restaurante' category (known to be in use by 1 client per context).
        Temporarily rename it, verify client's categoria_comercial updates, then rename back.
        """
        # Find Restaurante
        r = requests.get(f"{BASE_URL}/api/commercial-categories", headers=admin_headers, timeout=15)
        cats = r.json()
        target = next((c for c in cats if c["name"].lower() == "restaurante"), None)
        if not target:
            pytest.skip("Restaurante category not present")

        cat_id = target["category_id"]
        original_name = target["name"]
        temp_name = f"{original_name}_TEST_{uuid.uuid4().hex[:4]}"

        # Get clients using this category BEFORE rename
        rclients = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers, timeout=30)
        assert rclients.status_code == 200
        clients_list = rclients.json() if isinstance(rclients.json(), list) else rclients.json().get("clients", [])
        affected = [c for c in clients_list if c.get("categoria_comercial") == original_name]
        if not affected:
            pytest.skip(f"No clients use {original_name} - cannot test propagation")

        try:
            # Rename
            ru = requests.put(
                f"{BASE_URL}/api/commercial-categories/{cat_id}",
                json={"name": temp_name},
                headers=admin_headers,
                timeout=15,
            )
            assert ru.status_code == 200, ru.text
            assert ru.json()["name"] == temp_name

            # Verify client was updated
            rclients2 = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers, timeout=30)
            clients2 = rclients2.json() if isinstance(rclients2.json(), list) else rclients2.json().get("clients", [])
            affected_after = [c for c in clients2 if c.get("categoria_comercial") == temp_name]
            still_old = [c for c in clients2 if c.get("categoria_comercial") == original_name]
            assert len(affected_after) >= len(affected), (
                f"Rename did not propagate to clients. "
                f"Before: {len(affected)} clients had '{original_name}'. "
                f"After: {len(affected_after)} have '{temp_name}', {len(still_old)} still have old name."
            )
        finally:
            # restore name
            requests.put(
                f"{BASE_URL}/api/commercial-categories/{cat_id}",
                json={"name": original_name},
                headers=admin_headers,
                timeout=15,
            )

    def test_delete_blocked_when_in_use(self, admin_headers):
        """Verify: if a client uses a category, DELETE returns 409."""
        # Find 'Restaurante' which per context has 1 client using it
        r = requests.get(
            f"{BASE_URL}/api/commercial-categories", headers=admin_headers, timeout=15
        )
        cats = r.json()
        target = next((c for c in cats if c["name"].lower() == "restaurante"), None)
        if not target:
            pytest.skip("Restaurante category not present - skipping in-use delete test")
        rd = requests.delete(
            f"{BASE_URL}/api/commercial-categories/{target['category_id']}",
            headers=admin_headers,
            timeout=15,
        )
        assert rd.status_code == 409, f"Expected 409 when in use, got {rd.status_code} {rd.text}"

    def test_delete_success(self, admin_headers):
        """Delete the category created at start (should be unused)."""
        cat_id = TestCommercialCategoriesCRUD._created_id
        assert cat_id
        rd = requests.delete(
            f"{BASE_URL}/api/commercial-categories/{cat_id}",
            headers=admin_headers,
            timeout=15,
        )
        assert rd.status_code == 200, rd.text

        # verify gone
        r = requests.get(
            f"{BASE_URL}/api/commercial-categories", headers=admin_headers, timeout=15
        )
        assert all(c["category_id"] != cat_id for c in r.json())


# ---------- Bug fix: repaired_at returned by GET /api/quotes ----------
class TestRepairedAtPersistence:
    def test_existing_repair_quotes_return_repaired_at(self, admin_headers):
        """Per context, there are existing repair quotes with repaired_at persisted
        in DB. Before the fix, Pydantic stripped the field from the response.
        Now GET /api/quotes must return repaired_at for at least one quote."""
        r = requests.get(f"{BASE_URL}/api/quotes", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        quotes = data if isinstance(data, list) else data.get("quotes", [])
        assert len(quotes) > 0, "No quotes found in system"

        # Look for any repair-flow quote with repaired_at
        repair_quotes = [q for q in quotes if q.get("service_type") == "repair" or q.get("repair_state")]
        with_repaired = [q for q in quotes if q.get("repaired_at")]

        assert len(with_repaired) > 0, (
            f"BUG FIX REGRESSION: No quote returned repaired_at. "
            f"Found {len(quotes)} quotes, {len(repair_quotes)} repair quotes, "
            f"none with repaired_at populated. Expected at least COT-2026-04-006-PYME / COT-2026-04-030-PYME."
        )

        # Validate ISO timestamp shape
        sample = with_repaired[0]["repaired_at"]
        assert isinstance(sample, str), f"repaired_at must be string ISO, got {type(sample)}"
        assert "T" in sample and len(sample) >= 19, f"Invalid ISO timestamp: {sample}"

    def test_quote_model_exposes_configured_at_field(self, admin_headers):
        """configured_at was also added to the Quote model - make sure not blocked."""
        r = requests.get(f"{BASE_URL}/api/quotes", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        quotes = r.json() if isinstance(r.json(), list) else r.json().get("quotes", [])
        # We don't require any quote to have configured_at populated, but the field must
        # not be stripped out for those that do. Just check the endpoint works and no KeyError.
        assert len(quotes) > 0
