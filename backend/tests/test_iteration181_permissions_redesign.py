# ruff: noqa
"""Iter 181 — Redesign módulo de Seguridad y Perfiles de Acceso.
Tests:
- GET /admin/permission-catalog (admin-only, shape)
- PUT /admin/users/{id}/menu-groups (valida catálogo, persiste, admin-only)
- PUT /admin/users/{id}/permissions (acepta module_ids nuevos + legacy)
- PUT /admin/users/{id}/special-permissions (filtra flags desconocidos)
- Auto-migración menu_groups en /auth/login + /auth/me
- Admin-only endpoints: POST /integrators/import 403, DELETE /integrators/bulk/all 403, DELETE /projects/{id} 403, DELETE /taller-equipos/{id} 403
"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-impl-filter.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "ragg1008@gmail.com"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def non_admin_user(admin_headers):
    """Find a non-admin user to test with."""
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    users = r.json()
    for u in users:
        if u.get("role") == "user" and u.get("is_active", True):
            return u
    pytest.skip("No non-admin user available")


@pytest.fixture(scope="module")
def non_admin_token(admin_headers, non_admin_user):
    """Reset password for non-admin user and login."""
    uid = non_admin_user["user_id"]
    # Generate a reset link via admin endpoint
    r = requests.post(f"{BASE_URL}/api/admin/users/{uid}/reset-password",
                      headers=admin_headers, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot reset non-admin password: {r.status_code} {r.text}")
    reset_link = r.json().get("reset_link", "")
    token = reset_link.split("token=")[-1] if "token=" in reset_link else None
    if not token:
        pytest.skip("No reset token")
    new_pass = "Test1234!"
    r2 = requests.post(f"{BASE_URL}/api/auth/reset-password",
                       json={"token": token, "new_password": new_pass}, timeout=20)
    assert r2.status_code == 200, r2.text
    r3 = requests.post(f"{BASE_URL}/api/auth/login",
                       json={"email": non_admin_user["email"], "password": new_pass}, timeout=20)
    assert r3.status_code == 200, r3.text
    return r3.json()["session_token"]


# ============================================================
# 1. Catalog
# ============================================================
class TestPermissionCatalog:
    def test_catalog_admin_ok(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/permission-catalog",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["menu_groups"]) == 7
        assert len(d["modules"]) == 16
        assert len(d["levels"]) == 3
        assert len(d["special_permissions"]) == 7
        assert len(d["admin_only_actions"]) == 4
        level_values = {lv["value"] for lv in d["levels"]}
        assert level_values == {"none", "read", "edit"}

    def test_catalog_non_admin_403(self, non_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/permission-catalog",
                         headers={"Authorization": f"Bearer {non_admin_token}"}, timeout=15)
        assert r.status_code == 403


# ============================================================
# 2. Menu groups
# ============================================================
class TestMenuGroups:
    def test_update_menu_groups_persist(self, admin_headers, non_admin_user):
        uid = non_admin_user["user_id"]
        payload = {"menu_groups": {
            "dashboard": True,
            "gestion_comercial": False,
            "INVALID_ID": True,  # should be ignored
        }}
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/menu-groups",
                         headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        user = r.json()["user"]
        assert user["menu_groups"]["gestion_comercial"] is False
        assert user["menu_groups"]["dashboard"] is True
        assert "INVALID_ID" not in user["menu_groups"]
        # re-GET to verify persistence
        r2 = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=15)
        found = next((u for u in r2.json() if u["user_id"] == uid), None)
        assert found and found["menu_groups"]["gestion_comercial"] is False
        # Restore to True
        requests.put(f"{BASE_URL}/api/admin/users/{uid}/menu-groups",
                     headers=admin_headers,
                     json={"menu_groups": {"gestion_comercial": True}}, timeout=15)

    def test_update_menu_groups_non_admin_403(self, non_admin_token, non_admin_user):
        r = requests.put(f"{BASE_URL}/api/admin/users/{non_admin_user['user_id']}/menu-groups",
                         headers={"Authorization": f"Bearer {non_admin_token}",
                                  "Content-Type": "application/json"},
                         json={"menu_groups": {"dashboard": False}}, timeout=15)
        assert r.status_code == 403


# ============================================================
# 3. Permissions (new modules + legacy)
# ============================================================
class TestPermissions:
    def test_update_permissions_new_and_legacy(self, admin_headers, non_admin_user):
        uid = non_admin_user["user_id"]
        payload = {
            "initial_contacts": "edit",
            "quote_history": "read",
            "commercial_categories": "edit",
            "reportes_contables": "read",
            "exchange_rate": "edit",
            "cotizaciones": "read",   # legacy
            "clientes": "edit",        # legacy
            "UNKNOWN_MODULE": "edit",  # should be ignored
        }
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                         headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        perms = r.json()["user"]["permissions"]
        assert perms.get("initial_contacts") == "edit"
        assert perms.get("quote_history") == "read"
        assert perms.get("commercial_categories") == "edit"
        assert perms.get("reportes_contables") == "read"
        assert perms.get("exchange_rate") == "edit"
        assert perms.get("cotizaciones") == "read"
        assert perms.get("clientes") == "edit"
        assert "UNKNOWN_MODULE" not in perms


# ============================================================
# 4. Special Permissions
# ============================================================
class TestSpecialPermissions:
    def test_filter_unknown_flags(self, admin_headers, non_admin_user):
        uid = non_admin_user["user_id"]
        payload = {"special_permissions": [
            "proyectos:create",
            "cotizaciones:impl_pyme",
            "cotizaciones:impl_corp",
            "cotizaciones:equipos",
            "cotizaciones:reparaciones",
            "inventarios:create_warehouse",
            "integradores:create",
            "hack:admin",          # unknown
            "invalid_flag",         # unknown
        ]}
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/special-permissions",
                         headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        sp = set(r.json()["user"]["special_permissions"])
        assert "hack:admin" not in sp
        assert "invalid_flag" not in sp
        assert "proyectos:create" in sp
        assert "inventarios:create_warehouse" in sp
        assert len(sp) == 7
        # cleanup
        requests.put(f"{BASE_URL}/api/admin/users/{uid}/special-permissions",
                     headers=admin_headers,
                     json={"special_permissions": []}, timeout=15)


# ============================================================
# 5. Auto-migración + /auth/me
# ============================================================
class TestAutoMigration:
    def test_me_contains_menu_groups(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert "menu_groups" in me
        # Admin should have all groups truthy
        groups = me["menu_groups"]
        assert isinstance(groups, dict)
        assert len(groups) >= 7

    def test_non_admin_login_populates_groups(self, non_admin_token):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {non_admin_token}"}, timeout=15)
        assert r.status_code == 200
        assert "menu_groups" in r.json()
        assert len(r.json()["menu_groups"]) >= 7


# ============================================================
# 6. Admin-only endpoints (non-admin should get 403)
# ============================================================
class TestAdminOnlyEnforcement:
    def test_integrators_import_non_admin_403(self, non_admin_token):
        # Multipart upload — endpoint should reject before parsing
        files = {"file": ("x.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/integrators/import",
                          headers={"Authorization": f"Bearer {non_admin_token}"},
                          files=files, timeout=20)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:200]}"

    def test_integrators_bulk_all_non_admin_403(self, non_admin_token):
        r = requests.delete(f"{BASE_URL}/api/integrators/bulk/all",
                            headers={"Authorization": f"Bearer {non_admin_token}"}, timeout=15)
        assert r.status_code == 403

    def test_project_delete_non_admin_403(self, non_admin_token):
        r = requests.delete(f"{BASE_URL}/api/projects/nonexistent-id-probe",
                            headers={"Authorization": f"Bearer {non_admin_token}"}, timeout=15)
        # Must be 403 (role-gate) BEFORE 404 (existence)
        assert r.status_code == 403

    def test_taller_equipo_delete_non_admin_403(self, non_admin_token):
        r = requests.delete(f"{BASE_URL}/api/taller-equipos/nonexistent-id-probe",
                            headers={"Authorization": f"Bearer {non_admin_token}"}, timeout=15)
        assert r.status_code == 403
