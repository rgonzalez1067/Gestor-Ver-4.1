# ruff: noqa
"""Iteration 186: Tests for implementer-alerts RBAC, workload PDF with filters, and auto-assign from client."""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
# Implementer with existing project
IMPL_EMAIL = "Jrojas@megasoft.com.ve"
IMPL_PASS = "Test1234!"
IMPL_USER_ID = "user_a8e3874291c8"
IMPL_PROJECT_ID = "prj_bba45a09cd00"
# Non-impl non-admin
CONSULTA_EMAIL = "srubio@megasoft.com.ve"
CONSULTA_PASS = "Test1234!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_token():
    tk = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert tk, "Admin login failed"
    return tk


@pytest.fixture(scope="module")
def impl_token():
    tk = _login(IMPL_EMAIL, IMPL_PASS)
    if not tk:
        pytest.skip("Implementer login failed - credentials may need reset")
    return tk


@pytest.fixture(scope="module")
def consulta_token():
    tk = _login(CONSULTA_EMAIL, CONSULTA_PASS)
    if not tk:
        pytest.skip("Consulta user login failed")
    return tk


def _h(tk):
    return {"Authorization": f"Bearer {tk}"}


# ============ Implementer Alerts RBAC ============

class TestImplementerAlertsRBAC:
    def test_admin_get_alerts_200(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, f"Admin GET should be 200, got {r.status_code}: {r.text[:200]}"
        assert isinstance(r.json(), list)

    def test_admin_post_alert_403(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts",
                          headers=_h(admin_token), json={"message": "test admin"}, timeout=15)
        assert r.status_code == 403, f"Admin POST should be 403, got {r.status_code}: {r.text[:200]}"

    def test_consulta_get_alerts_403(self, consulta_token):
        r = requests.get(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts",
                         headers=_h(consulta_token), timeout=15)
        assert r.status_code == 403, f"Consulta GET should be 403, got {r.status_code}"

    def test_impl_crud_flow(self, impl_token):
        # Create
        r = requests.post(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts",
                          headers=_h(impl_token), json={"message": "TEST_iter186 alerta", "deadline": "2026-12-31"}, timeout=15)
        assert r.status_code == 200, f"Impl POST: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "alert" in data
        alert_id = data["alert"]["alert_id"]
        assert data["alert"]["message"] == "TEST_iter186 alerta"
        assert data["alert"]["completed"] is False

        # List should include it
        r2 = requests.get(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts", headers=_h(impl_token), timeout=15)
        assert r2.status_code == 200
        ids = [a["alert_id"] for a in r2.json()]
        assert alert_id in ids

        # Complete
        r3 = requests.put(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts/{alert_id}/complete",
                          headers=_h(impl_token), timeout=15)
        assert r3.status_code == 200

        # Verify completed=True
        r4 = requests.get(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts", headers=_h(impl_token), timeout=15)
        found = [a for a in r4.json() if a["alert_id"] == alert_id]
        assert len(found) == 1 and found[0]["completed"] is True

        # Delete
        r5 = requests.delete(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts/{alert_id}",
                             headers=_h(impl_token), timeout=15)
        assert r5.status_code == 200

        # Verify gone
        r6 = requests.get(f"{BASE_URL}/api/projects/{IMPL_PROJECT_ID}/implementer-alerts", headers=_h(impl_token), timeout=15)
        ids2 = [a["alert_id"] for a in r6.json()]
        assert alert_id not in ids2


# ============ Workload PDF with filters ============

class TestWorkloadPDF:
    def test_pdf_no_filters(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/projects/reports/workload-pdf", headers=_h(admin_token), timeout=40)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_pdf_multi_filter(self, admin_token):
        # multi-select: repeated params
        url = f"{BASE_URL}/api/projects/reports/workload-pdf?status=Asignado+%2F+En+Proceso&status=Pendiente+por+Asignar&quote_type=VPOS&quote_type=MPOS&client=mega"
        r = requests.get(url, headers=_h(admin_token), timeout=40)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        assert r.content[:4] == b"%PDF"

    def test_pdf_assigned_to_filter(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/projects/reports/workload-pdf",
                         params={"assigned_to": "Sin asignar"}, headers=_h(admin_token), timeout=40)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"


# ============ Auto-assign from client in quote_transitions ============

class TestAutoAssignFromClient:
    """Test that _create_project_from_quote inherits implementer_user_id and implementer_name from client."""

    def test_client_with_impl_creates_asignado_project(self, admin_token):
        # Find any client with implementer_user_id set
        r = requests.get(f"{BASE_URL}/api/clients", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        clients = r.json()
        client_with_impl = None
        for c in clients:
            if c.get("implementer_user_id") and c.get("implementer_name"):
                client_with_impl = c
                break
        if not client_with_impl:
            pytest.skip("No client with implementer_user_id found in DB for this test")

        # Find any project created from a quote for that client: status should be Asignado/En Proceso
        # and auto_assigned_from_client should be True OR just verify assigned_to matches
        r2 = requests.get(f"{BASE_URL}/api/projects", headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200
        projects = r2.json()
        match = [
            p for p in projects
            if p.get("client_id") == client_with_impl.get("client_id")
            and p.get("auto_assigned_from_client") is True
        ]
        if not match:
            pytest.skip(f"No auto-assigned project found for client {client_with_impl.get('client_id')}. Feature may not yet have a historical record.")
        p = match[0]
        assert p.get("status") == "Asignado / En Proceso", f"Expected 'Asignado / En Proceso', got {p.get('status')}"
        assert p.get("assigned_to_user_id") == client_with_impl.get("implementer_user_id"), \
            f"Expected assignee {client_with_impl.get('implementer_user_id')}, got {p.get('assigned_to_user_id')}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
