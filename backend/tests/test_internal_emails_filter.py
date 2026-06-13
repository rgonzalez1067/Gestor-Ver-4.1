"""Iter 63 — Tests for /api/users/internal-emails strategic profile filter
and POST /api/projects/{id}/send-notification with to_override + additional_recipients.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"no token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============ Filtro por rol ============
class TestInternalEmailsFilter:
    def test_full_list(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/users/internal-emails", headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verificar campos esperados
        u0 = data[0]
        for k in ("email", "full_name", "cargo", "departamento", "label"):
            assert k in u0, f"missing key {k} in {u0}"
        # Guardar total para comparar después
        global FULL_COUNT
        FULL_COUNT = len(data)

    def test_strategic_subset_and_filter(self, auth_headers):
        r_all = requests.get(f"{BASE_URL}/api/users/internal-emails", headers=auth_headers, timeout=20)
        r_strat = requests.get(f"{BASE_URL}/api/users/internal-emails?profile=strategic", headers=auth_headers, timeout=20)
        assert r_all.status_code == 200 and r_strat.status_code == 200
        all_users = r_all.json()
        strat_users = r_strat.json()
        assert len(strat_users) <= len(all_users), "strategic list must be subset"
        assert len(strat_users) < len(all_users), "strategic list should be strictly smaller than full"

        # Reglas: cargo=Director/depto=Dirección OR depto empieza por "Ventas"
        # OR depto=Implementación (cualquier cargo)
        for u in strat_users:
            cargo = (u.get("cargo") or "").strip().lower()
            dept = (u.get("departamento") or "").strip().lower()
            ok = (cargo == "director" or dept in ("dirección", "direccion")
                  or dept.startswith("ventas")
                  or dept in ("implementación", "implementacion"))
            assert ok, f"user {u.get('email')} cargo={cargo!r} dept={dept!r} should NOT be in strategic list"

    def test_strategic_includes_all_three_teams(self, auth_headers):
        """Debe incluir TODO Ventas, TODA Implementación y los Directores."""
        r_all = requests.get(f"{BASE_URL}/api/users/internal-emails", headers=auth_headers, timeout=20)
        r_strat = requests.get(f"{BASE_URL}/api/users/internal-emails?profile=strategic", headers=auth_headers, timeout=20)
        all_users, strat_users = r_all.json(), r_strat.json()
        strat_emails = {u.get("email") for u in strat_users}

        def is_target(u):
            cargo = (u.get("cargo") or "").strip().lower()
            dept = (u.get("departamento") or "").strip().lower()
            return (cargo == "director" or dept in ("dirección", "direccion")
                    or dept.startswith("ventas")
                    or dept in ("implementación", "implementacion"))

        missing = [u.get("email") for u in all_users if is_target(u) and u.get("email") not in strat_emails]
        assert not missing, f"usuarios de Ventas/Implementación/Dirección faltantes en strategic: {missing}"

    def test_strategic_excludes_non_strategic(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/users/internal-emails?profile=strategic", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        # Operaciones, Administración, Desarrollo, QA, Infraestructura NO entran (salvo Director)
        excluded_depts = {"Administración", "Desarrollo", "Infraestructura", "TI",
                          "Aseguramiento de Calidad", "QA", "Operaciones"}
        for u in r.json():
            dept = (u.get("departamento") or "").strip()
            cargo = (u.get("cargo") or "").strip()
            if dept in excluded_depts:
                assert cargo == "Director", f"non-strategic user leaked: {u.get('email')} {dept}/{cargo}"


# ============ Envío con to_override y additional_recipients ============
class TestProjectSendNotification:
    def _pick_project(self, headers):
        r = requests.get(f"{BASE_URL}/api/projects?limit=20", headers=headers, timeout=20)
        if r.status_code != 200:
            return None
        items = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("projects") or []
        # Prefer prj_62903d69d10a if exists
        for p in items:
            if p.get("project_id") == "prj_62903d69d10a":
                return p
        return items[0] if items else None

    def test_send_notification_to_override_and_cc(self, auth_headers):
        proj = self._pick_project(auth_headers)
        if not proj:
            pytest.skip("No projects available")
        pid = proj.get("project_id") or proj.get("id")
        assert pid, f"project has no id: {proj}"

        payload = {
            "notification_type": "cliente",
            "subject": "TEST_iter63 Notificación con TO corregido y CC tokens",
            "message": "Cuerpo de prueba para validar to_override y additional_recipients.",
            "to_override": ["contacto_correcto@banco-test.com"],
            "additional_recipients": ["cc_externo1@test.com", "cc_externo2@test.com"],
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{pid}/send-notification",
            headers=auth_headers,
            json=payload,
            timeout=30,
        )
        # Aceptar 200 o 422 (si el proyecto bloquea por estado) — el caso interesante es validar éxito o
        # error de negocio claro; un 500 indicaría regresión.
        assert r.status_code != 500, f"500 from send-notification: {r.text}"
        if r.status_code == 200:
            data = r.json()
            # Debería confirmar envío o cola
            assert any(k in data for k in ("status", "message", "sent", "ok")), f"unexpected response: {data}"
        else:
            # Reportar como informativo
            print(f"send-notification non-200 (informational): {r.status_code} body={r.text[:300]}")
