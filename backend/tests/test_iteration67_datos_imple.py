"""Iteration 67 — Datos de Imple
Verifies:
- GET /api/implementation/default-coordinator returns the active user with profile 'Coordinador de Administracion'
- PUT /api/clients/{client_id}/imple-data updates the 5 fields and CASCADES to all branches with same RIF
- Independence: clients with different RIF are not modified
- Permission catalog contains 'datos_imple' module
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    return body.get("session_token") or body.get("token") or body.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Default coordinator ----------
def test_default_coordinator(auth_headers):
    r = requests.get(f"{BASE_URL}/api/implementation/default-coordinator", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("profile_found") is True, data
    assert data.get("user_id"), f"Expected user_id non-empty: {data}"
    assert "Angel" in data.get("name", "") or data.get("name"), f"Coordinator name: {data}"
    print("Default coordinator:", data)


# ---------- Permission catalog ----------
def test_permission_catalog_has_datos_imple(auth_headers):
    r = requests.get(f"{BASE_URL}/api/admin/permission-catalog", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    catalog = r.json()
    # catalog may be a list of groups or modules
    raw = str(catalog)
    assert "datos_imple" in raw, "datos_imple module missing in catalog"


# ---------- Get a RIF with multiple branches ----------
@pytest.fixture(scope="module")
def multi_branch_rif(auth_headers):
    r = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers, timeout=60)
    assert r.status_code == 200, r.text
    clients = r.json()
    by_rif = {}
    for c in clients:
        rif = (c.get("rif") or "").strip()
        if not rif:
            continue
        by_rif.setdefault(rif, []).append(c)
    multi = [(rif, items) for rif, items in by_rif.items() if len(items) >= 2]
    assert multi, "No RIF with multiple branches found"
    # Prefer J505366220 as per problem statement
    preferred = [m for m in multi if m[0].replace("-", "").replace(" ", "").upper().startswith("J505366220") or "J505366220" in m[0]]
    chosen = preferred[0] if preferred else max(multi, key=lambda x: len(x[1]))
    print(f"Chosen RIF {chosen[0]} with {len(chosen[1])} branches")
    return chosen  # (rif, [clients...])


@pytest.fixture(scope="module")
def control_client(auth_headers, multi_branch_rif):
    """Find a client with DIFFERENT RIF used as control (independence check)."""
    rif_target, _ = multi_branch_rif
    r = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers, timeout=60)
    clients = r.json()
    for c in clients:
        if (c.get("rif") or "") != rif_target and c.get("client_id"):
            return c
    pytest.skip("No control client with different RIF")


def test_imple_data_cascade(auth_headers, multi_branch_rif, control_client):
    rif, branches = multi_branch_rif
    target = branches[0]
    client_id = target["client_id"]

    # Capture control snapshot BEFORE
    r0 = requests.get(f"{BASE_URL}/api/clients/{control_client['client_id']}", headers=auth_headers, timeout=30)
    assert r0.status_code == 200, r0.text
    control_before = r0.json()

    # Get integrators + implementers + coordinators dropdowns
    integ_r = requests.get(f"{BASE_URL}/api/integrators/dropdown", headers=auth_headers, timeout=30)
    assert integ_r.status_code == 200, integ_r.text
    integs = integ_r.json()
    assert len(integs) >= 1, "No integrators"
    integ = integs[0]

    impl_r = requests.get(f"{BASE_URL}/api/auth/implementadores", headers=auth_headers, timeout=30)
    assert impl_r.status_code == 200, impl_r.text
    implementers = impl_r.json()
    assert len(implementers) >= 1, "No implementers"
    impl = implementers[0]

    coord_r = requests.get(f"{BASE_URL}/api/auth/coordinadores", headers=auth_headers, timeout=30)
    assert coord_r.status_code == 200, coord_r.text
    coords = coord_r.json()
    assert len(coords) >= 1, "No coordinators"
    coord = coords[0]

    payload = {
        "tipo_servicio": ["Componentes"],
        "integrador_id": integ.get("integrator_id") or integ.get("id"),
        "integrador_name": integ.get("name"),
        "aplicativo": integ.get("app_name") or "TestApp",
        "implementer_user_id": impl.get("user_id"),
        "implementer_name": f"{impl.get('first_name', '')} {impl.get('last_name', '')}".strip() or impl.get("name", "Implem"),
        "coordinator_user_id": coord.get("user_id"),
        "coordinator_name": f"{coord.get('first_name', '')} {coord.get('last_name', '')}".strip() or coord.get("name", "Coord"),
    }

    r = requests.put(f"{BASE_URL}/api/clients/{client_id}/imple-data", json=payload, headers=auth_headers, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    print("Update response:", body)
    assert body.get("rif") == rif
    assert body.get("modified", 0) >= 1
    assert body.get("branches_count", 0) == len(branches)

    # Verify cascade — another branch updated
    other_branch = branches[-1]
    r2 = requests.get(f"{BASE_URL}/api/clients/{other_branch['client_id']}", headers=auth_headers, timeout=30)
    assert r2.status_code == 200, r2.text
    other = r2.json()
    assert other.get("integrador_id") == payload["integrador_id"]
    assert other.get("aplicativo") == payload["aplicativo"]
    assert other.get("implementer_user_id") == payload["implementer_user_id"]
    assert other.get("coordinator_user_id") == payload["coordinator_user_id"]
    assert "Componentes" in (other.get("tipo_servicio") or [])

    # Verify independence — control client NOT updated
    r3 = requests.get(f"{BASE_URL}/api/clients/{control_client['client_id']}", headers=auth_headers, timeout=30)
    control_after = r3.json()
    # Critical: control's previous integrador_id should not now equal the new payload (unless it already was)
    if control_before.get("integrador_id") != payload["integrador_id"]:
        assert control_after.get("integrador_id") == control_before.get("integrador_id"), \
            "Control client (different RIF) got modified — cascade leak!"
    if control_before.get("aplicativo") != payload["aplicativo"]:
        assert control_after.get("aplicativo") == control_before.get("aplicativo")
