# ruff: noqa
"""Iteration 183 — Tests for Profiles master & ceiling (techo de permisos).

Covers:
- GET /api/admin/profiles lists 4 seed profiles with user_count.
- POST /api/admin/profiles (create, duplicate name 409).
- POST /api/admin/profiles/{id}/duplicate (suffix '(copia)').
- DELETE /api/admin/profiles/{id} (200 when no users, 409 when users linked).
- PUT /api/admin/users/{id}/profile (assigns + copies perms baseline; null removes).
- Ceiling on permissions/menu-groups/special-permissions (403 on elevation).
- Admin role exempt from ceiling.
- Profile update re-syncs linked users downward.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "ragg1008@gmail.com"
ADMIN_PASSWORD = "admin123"

SEED_NAMES = {"Vendedor Pyme", "Vendedor Corp", "Gerente Operativo", "Operador Taller"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def profiles_list(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/profiles", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def seed_map(profiles_list):
    """Map name -> profile dict for the 4 seed profiles."""
    return {p["name"]: p for p in profiles_list if p["name"] in SEED_NAMES}


# ---------- test user fixture: create a fresh non-admin user ----------
@pytest.fixture(scope="module")
def test_user(admin_headers):
    suffix = uuid.uuid4().hex[:6]
    email = f"TEST_ceiling_{suffix}@megasoft.com.ve"
    payload = {"email": email, "password": "Test1234!",
               "first_name": "TEST", "last_name": f"Ceiling{suffix}",
               "name": f"TEST Ceiling {suffix}", "role": "user"}
    r = requests.post(f"{BASE_URL}/api/admin/users/create", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create test user: {r.status_code} {r.text}"
    user = r.json().get("user") or r.json()
    yield user
    # teardown
    uid = user.get("user_id") or user.get("id")
    if uid:
        requests.delete(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_headers, timeout=30)


# ============================================================
# 1. Seed profiles
# ============================================================
class TestSeedProfiles:
    def test_four_seed_profiles_present(self, profiles_list):
        names = {p["name"] for p in profiles_list}
        for n in SEED_NAMES:
            assert n in names, f"Missing seed profile: {n}"

    def test_profiles_have_user_count(self, profiles_list):
        for p in profiles_list:
            assert "user_count" in p, f"Profile {p['name']} missing user_count"
            assert isinstance(p["user_count"], int)

    def test_vendedor_pyme_shape(self, seed_map):
        p = seed_map["Vendedor Pyme"]
        assert p["menu_groups"].get("gestion_taller") is False
        assert "cotizaciones:impl_pyme" in p["special_permissions"]
        assert p["permissions"].get("bancos") == "read"


# ============================================================
# 2. CRUD profiles
# ============================================================
class TestProfileCRUD:
    def test_create_profile_ok(self, admin_headers):
        name = f"TEST_Profile_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/admin/profiles", headers=admin_headers,
                          json={"name": name, "description": "tmp"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == name
        assert data["user_count"] == 0
        assert "profile_id" in data
        # cleanup
        requests.delete(f"{BASE_URL}/api/admin/profiles/{data['profile_id']}", headers=admin_headers, timeout=30)

    def test_create_duplicate_409(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/profiles", headers=admin_headers,
                          json={"name": "Vendedor Pyme"}, timeout=30)
        assert r.status_code == 409

    def test_duplicate_profile_suffix_copia(self, admin_headers, seed_map):
        src = seed_map["Operador Taller"]
        r = requests.post(f"{BASE_URL}/api/admin/profiles/{src['profile_id']}/duplicate",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        dup = r.json()
        assert "(copia)" in dup["name"]
        assert dup["profile_id"] != src["profile_id"]
        assert dup["permissions"].get("taller_equipos") == "edit"
        # cleanup
        requests.delete(f"{BASE_URL}/api/admin/profiles/{dup['profile_id']}", headers=admin_headers, timeout=30)

    def test_delete_profile_without_users_ok(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/profiles", headers=admin_headers,
                          json={"name": f"TEST_Del_{uuid.uuid4().hex[:6]}"}, timeout=30)
        pid = r.json()["profile_id"]
        r2 = requests.delete(f"{BASE_URL}/api/admin/profiles/{pid}", headers=admin_headers, timeout=30)
        assert r2.status_code == 200

    def test_delete_profile_with_users_409(self, admin_headers, seed_map, test_user):
        # assign pyme to test_user
        pyme = seed_map["Vendedor Pyme"]
        uid = test_user.get("user_id") or test_user.get("id")
        r_assign = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                                headers=admin_headers, json={"profile_id": pyme["profile_id"]}, timeout=30)
        assert r_assign.status_code == 200, r_assign.text
        # try delete
        r = requests.delete(f"{BASE_URL}/api/admin/profiles/{pyme['profile_id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 409
        assert "usuario" in r.json().get("detail", "").lower()


# ============================================================
# 3. Assign profile copies baseline
# ============================================================
class TestAssignProfile:
    def test_assign_copies_permissions_baseline(self, admin_headers, seed_map, test_user):
        pyme = seed_map["Vendedor Pyme"]
        uid = test_user.get("user_id") or test_user.get("id")
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                         headers=admin_headers, json={"profile_id": pyme["profile_id"]}, timeout=30)
        assert r.status_code == 200
        updated = r.json()["user"]
        assert updated["profile_id"] == pyme["profile_id"]
        # Baseline: bancos == read (from pyme profile)
        assert updated["permissions"].get("bancos") == "read"
        # menu_groups.gestion_taller == False
        assert updated["menu_groups"].get("gestion_taller") is False
        assert "cotizaciones:impl_pyme" in updated["special_permissions"]

    def test_unassign_profile_null(self, admin_headers, test_user):
        uid = test_user.get("user_id") or test_user.get("id")
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                         headers=admin_headers, json={"profile_id": None}, timeout=30)
        assert r.status_code == 200
        assert r.json()["user"].get("profile_id") is None


# ============================================================
# 4. Ceiling enforcement
# ============================================================
class TestCeiling:
    def _reassign_pyme(self, admin_headers, seed_map, test_user):
        pyme = seed_map["Vendedor Pyme"]
        uid = test_user.get("user_id") or test_user.get("id")
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                         headers=admin_headers, json={"profile_id": pyme["profile_id"]}, timeout=30)
        assert r.status_code == 200
        return uid, pyme

    def test_permissions_elevation_blocked_403(self, admin_headers, seed_map, test_user):
        uid, pyme = self._reassign_pyme(admin_headers, seed_map, test_user)
        # bancos in pyme is 'read' → try 'edit' should 403
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                         headers=admin_headers, json={"bancos": "edit"}, timeout=30)
        assert r.status_code == 403, r.text
        detail = r.json().get("detail", "")
        assert "Acceso restringido" in detail
        assert "Vendedor Pyme" in detail
        assert "bancos" in detail

    def test_permissions_downgrade_ok_200(self, admin_headers, seed_map, test_user):
        uid, _ = self._reassign_pyme(admin_headers, seed_map, test_user)
        # bancos read → none is a downgrade, allowed
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                         headers=admin_headers, json={"bancos": "none"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["user"]["permissions"]["bancos"] == "none"

    def test_menu_groups_elevation_blocked(self, admin_headers, seed_map, test_user):
        uid, _ = self._reassign_pyme(admin_headers, seed_map, test_user)
        # pyme has gestion_taller=False → set to True should 403
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/menu-groups",
                         headers=admin_headers, json={"menu_groups": {"gestion_taller": True}}, timeout=30)
        assert r.status_code == 403
        assert "Vendedor Pyme" in r.json().get("detail", "")

    def test_special_permissions_not_in_profile_blocked(self, admin_headers, seed_map, test_user):
        uid, _ = self._reassign_pyme(admin_headers, seed_map, test_user)
        # Pyme includes impl_pyme + equipos, NOT impl_corp
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/special-permissions",
                         headers=admin_headers,
                         json={"special_permissions": ["cotizaciones:impl_corp"]}, timeout=30)
        assert r.status_code == 403
        assert "cotizaciones:impl_corp" in r.json().get("detail", "")

    def test_special_permissions_in_profile_ok(self, admin_headers, seed_map, test_user):
        uid, _ = self._reassign_pyme(admin_headers, seed_map, test_user)
        r = requests.put(f"{BASE_URL}/api/admin/users/{uid}/special-permissions",
                         headers=admin_headers,
                         json={"special_permissions": ["cotizaciones:impl_pyme"]}, timeout=30)
        assert r.status_code == 200
        assert "cotizaciones:impl_pyme" in r.json()["user"]["special_permissions"]


# ============================================================
# 5. Admin role exempt from ceiling
# ============================================================
class TestAdminExempt:
    def test_admin_with_profile_exempt_from_ceiling(self, admin_headers, seed_map):
        # Create a TEST admin user, assign pyme, try to elevate — should succeed.
        suffix = uuid.uuid4().hex[:6]
        email = f"TEST_admin_ex_{suffix}@megasoft.com.ve"
        r = requests.post(f"{BASE_URL}/api/admin/users/create", headers=admin_headers,
                          json={"email": email, "password": "Test1234!",
                                "first_name": "TESTAdmin", "last_name": f"Exempt{suffix}",
                                "name": f"TEST Admin Exempt {suffix}", "role": "admin"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        admin_user = r.json().get("user") or r.json()
        uid = admin_user.get("user_id") or admin_user.get("id")
        # Promote to admin (create endpoint hardcodes role=user)
        rprom = requests.put(f"{BASE_URL}/api/admin/users/{uid}/role?role=admin",
                             headers=admin_headers, timeout=30)
        assert rprom.status_code == 200, f"Promote to admin failed: {rprom.text}"
        try:
            pyme = seed_map["Vendedor Pyme"]
            # assign profile to this admin
            r2 = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                              headers=admin_headers, json={"profile_id": pyme["profile_id"]}, timeout=30)
            assert r2.status_code == 200
            # Try elevation — should NOT be blocked for admin
            r3 = requests.put(f"{BASE_URL}/api/admin/users/{uid}/permissions",
                              headers=admin_headers, json={"bancos": "edit"}, timeout=30)
            assert r3.status_code == 200, f"Admin should be exempt, got {r3.status_code}: {r3.text}"
            assert r3.json()["user"]["permissions"]["bancos"] == "edit"
            # menu_groups elevation also allowed
            r4 = requests.put(f"{BASE_URL}/api/admin/users/{uid}/menu-groups",
                              headers=admin_headers, json={"menu_groups": {"gestion_taller": True}}, timeout=30)
            assert r4.status_code == 200
            # special-permissions elevation allowed
            r5 = requests.put(f"{BASE_URL}/api/admin/users/{uid}/special-permissions",
                              headers=admin_headers,
                              json={"special_permissions": ["cotizaciones:impl_corp"]}, timeout=30)
            assert r5.status_code == 200
        finally:
            requests.delete(f"{BASE_URL}/api/admin/users/{uid}", headers=admin_headers, timeout=30)


# ============================================================
# 6. Profile update re-syncs linked users downward
# ============================================================
class TestProfileResync:
    def test_downgrade_profile_resyncs_users(self, admin_headers, test_user):
        # Create fresh profile with bancos=read, assign to user, then change bancos to none.
        suffix = uuid.uuid4().hex[:6]
        r = requests.post(f"{BASE_URL}/api/admin/profiles", headers=admin_headers,
                          json={"name": f"TEST_Resync_{suffix}",
                                "permissions": {"bancos": "read"},
                                "menu_groups": {"gestion_taller": True},
                                "special_permissions": ["cotizaciones:impl_pyme"]}, timeout=30)
        assert r.status_code == 200, r.text
        pid = r.json()["profile_id"]
        uid = test_user.get("user_id") or test_user.get("id")
        try:
            # assign
            ra = requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                              headers=admin_headers, json={"profile_id": pid}, timeout=30)
            assert ra.status_code == 200
            assert ra.json()["user"]["permissions"].get("bancos") == "read"

            # downgrade profile bancos: read → none
            rp = requests.put(f"{BASE_URL}/api/admin/profiles/{pid}", headers=admin_headers,
                              json={"permissions": {"bancos": "none"}}, timeout=30)
            assert rp.status_code == 200
            assert rp.json()["permissions"]["bancos"] == "none"

            # Verify user re-synced: GET /admin/users (single)
            rg = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=30)
            assert rg.status_code == 200
            users = rg.json() if isinstance(rg.json(), list) else rg.json().get("users", [])
            target = next((u for u in users if (u.get("user_id") or u.get("id")) == uid), None)
            assert target is not None, "user not found in list"
            assert target["permissions"].get("bancos") == "none", \
                f"User bancos not re-synced: {target['permissions'].get('bancos')}"
        finally:
            # unassign user, then delete profile
            requests.put(f"{BASE_URL}/api/admin/users/{uid}/profile",
                         headers=admin_headers, json={"profile_id": None}, timeout=30)
            requests.delete(f"{BASE_URL}/api/admin/profiles/{pid}", headers=admin_headers, timeout=30)
