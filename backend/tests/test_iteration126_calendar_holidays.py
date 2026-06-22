"""Iteration 126 — Calendario Laboral (días festivos + RBAC).

Tests:
- GET /api/calendar/holidays (auth abierto)
- POST /api/calendar/holidays (admin-only, valida unicidad → 409)
- DELETE /api/calendar/holidays/{id} (admin-only)
- RBAC: POST/DELETE con usuario no-admin → 403
- GET /api/projects expone business_days_in_state
Limpieza: elimina cualquier festivo TEST_ creado y deja la colección como estaba.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
NON_ADMIN = {"email": "Jrojas@megasoft.com.ve", "password": "Test1234!"}


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed {email}: {r.status_code} {r.text[:200]}"
    j = r.json()
    return j.get("session_token") or j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN["email"], ADMIN["password"])


@pytest.fixture(scope="module")
def user_token():
    return _login(NON_ADMIN["email"], NON_ADMIN["password"])


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# Track created holidays for cleanup
_created_ids = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_headers):
    yield
    # Teardown: delete all holidays created during testing
    try:
        r = requests.get(f"{BASE_URL}/api/calendar/holidays", headers=admin_headers, timeout=20)
        if r.status_code == 200:
            for h in r.json():
                if h.get("holiday_id") in _created_ids:
                    requests.delete(f"{BASE_URL}/api/calendar/holidays/{h['holiday_id']}",
                                    headers=admin_headers, timeout=20)
    except Exception as e:
        print(f"Cleanup error: {e}")


class TestListHolidays:
    def test_list_holidays_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/calendar/holidays", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_holidays_non_admin_allowed(self, user_headers):
        r = requests.get(f"{BASE_URL}/api/calendar/holidays", headers=user_headers, timeout=20)
        assert r.status_code == 200, f"Lista debe estar abierta a autenticados: {r.text[:200]}"

    def test_list_holidays_unauth(self):
        r = requests.get(f"{BASE_URL}/api/calendar/holidays", timeout=20)
        assert r.status_code == 401


class TestCreateAndUnique:
    def test_create_specific_holiday(self, admin_headers):
        payload = {"holiday_date": "2026-12-25", "description": "TEST_Navidad", "recurring": False}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"Crear festivo: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data["holiday_date"] == "2026-12-25"
        assert data["description"] == "TEST_Navidad"
        assert data["recurring"] is False
        assert "holiday_id" in data
        assert "_id" not in data
        _created_ids.append(data["holiday_id"])

        # Verify via GET
        r2 = requests.get(f"{BASE_URL}/api/calendar/holidays", headers=admin_headers, timeout=20)
        ids = [h["holiday_id"] for h in r2.json()]
        assert data["holiday_id"] in ids

    def test_create_duplicate_specific_409(self, admin_headers):
        payload = {"holiday_date": "2026-12-25", "description": "TEST_Dup", "recurring": False}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 409, f"Esperado 409 por duplicado: {r.status_code} {r.text[:200]}"

    def test_create_recurring_holiday(self, admin_headers):
        payload = {"holiday_date": "2026-01-01", "description": "TEST_AnioNuevo", "recurring": True}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"Crear recurrente: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert data["recurring"] is True
        assert data.get("month_day") == "01-01"
        _created_ids.append(data["holiday_id"])

    def test_create_duplicate_recurring_409(self, admin_headers):
        payload = {"holiday_date": "2027-01-01", "description": "TEST_DupRec", "recurring": True}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 409, f"Esperado 409 por MM-DD recurrente duplicado: {r.status_code}"

    def test_create_invalid_date_400(self, admin_headers):
        payload = {"holiday_date": "no-es-fecha", "description": "TEST_Bad", "recurring": False}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 400


class TestRBAC:
    def test_post_forbidden_non_admin(self, user_headers):
        payload = {"holiday_date": "2026-07-04", "description": "TEST_NoAdmin", "recurring": False}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=user_headers, timeout=20)
        assert r.status_code == 403, f"Non-admin debe recibir 403: {r.status_code} {r.text[:200]}"

    def test_delete_forbidden_non_admin(self, user_headers, admin_headers):
        # Use one of the created holidays if any
        target = _created_ids[0] if _created_ids else None
        if not target:
            pytest.skip("No hay festivo creado para probar DELETE")
        r = requests.delete(f"{BASE_URL}/api/calendar/holidays/{target}", headers=user_headers, timeout=20)
        assert r.status_code == 403

    def test_unauth_post_401(self):
        r = requests.post(f"{BASE_URL}/api/calendar/holidays",
                          json={"holiday_date": "2026-08-15", "description": "X", "recurring": False}, timeout=20)
        assert r.status_code == 401


class TestDelete:
    def test_delete_holiday_admin(self, admin_headers):
        # Create a one-off then delete
        payload = {"holiday_date": "2026-11-30", "description": "TEST_ToDelete", "recurring": False}
        r = requests.post(f"{BASE_URL}/api/calendar/holidays", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        hid = r.json()["holiday_id"]

        r2 = requests.delete(f"{BASE_URL}/api/calendar/holidays/{hid}", headers=admin_headers, timeout=20)
        assert r2.status_code == 200

        # Verify gone
        r3 = requests.get(f"{BASE_URL}/api/calendar/holidays", headers=admin_headers, timeout=20)
        ids = [h["holiday_id"] for h in r3.json()]
        assert hid not in ids

    def test_delete_nonexistent_404(self, admin_headers):
        r = requests.delete(f"{BASE_URL}/api/calendar/holidays/hol_nonexistent", headers=admin_headers, timeout=20)
        assert r.status_code == 404


class TestProjectsBusinessDays:
    def test_projects_returns_business_days_in_state(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/projects", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"GET /api/projects: {r.status_code} {r.text[:200]}"
        data = r.json()
        projects = data if isinstance(data, list) else data.get("projects", [])
        if not projects:
            pytest.skip("No hay proyectos para validar business_days_in_state")
        # At least one project should have the field present (even if 0)
        with_field = [p for p in projects if "business_days_in_state" in p]
        assert len(with_field) > 0, "Ningún proyecto incluye 'business_days_in_state'"
        for p in with_field[:5]:
            assert isinstance(p["business_days_in_state"], int)
            assert p["business_days_in_state"] >= 0
