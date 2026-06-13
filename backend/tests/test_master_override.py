"""
Tests for Master Override (Super-Admin) — iteration 70.
- RBAC: admin -> 200, no-admin -> 403
- Single override: reconstruye banks/services/implementation_matrix sin huérfanos
- Multistore: matriz top-level es unión de tiendas, banks consistente
- Ficha técnica sigue funcionando después del override
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
NON_ADMIN = {"email": "srubio@megasoft.com.ve", "password": "Test1234!"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(NON_ADMIN)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _list_projects(tok):
    r = requests.get(f"{API}/projects", headers=_h(tok), timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    return data if isinstance(data, list) else data.get("projects", data.get("items", []))


def _get_project(tok, pid):
    r = requests.get(f"{API}/projects/{pid}", headers=_h(tok), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _pick_single(tok):
    for p in _list_projects(tok):
        if p.get("project_type") != "multistore":
            return p["project_id"]
    pytest.skip("No single project available")


def _pick_multistore(tok):
    for p in _list_projects(tok):
        if p.get("project_type") == "multistore":
            full = _get_project(tok, p["project_id"])
            if (full.get("stores") or []):
                return full["project_id"]
    pytest.skip("No multistore project with stores available")


def _vpos_bank(tok):
    """Pick a bank with at least 2 VPOS products."""
    r = requests.get(f"{API}/banks", headers=_h(tok), timeout=30)
    assert r.status_code == 200, r.text
    for b in r.json():
        prods = [p["product_name"] for p in (b.get("products") or []) if p.get("vpos_available")]
        if len(prods) >= 2:
            return b["name"], prods[:2]
    pytest.skip("No bank with >=2 VPOS products")


# ===================== RBAC =====================
def test_master_override_rbac_non_admin_forbidden(user_token):
    # Need any existing project id; we use admin to list but call as non-admin
    admin_tok = _login(ADMIN)
    pid = _list_projects(admin_tok)[0]["project_id"]
    r = requests.put(
        f"{API}/projects/{pid}/master-override",
        headers=_h(user_token),
        json={"status": "En Gestión"},
        timeout=30,
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


def test_master_override_rbac_admin_allowed(admin_token):
    pid = _pick_single(admin_token)
    r = requests.put(
        f"{API}/projects/{pid}/master-override",
        headers=_h(admin_token),
        json={},  # no-op payload, just check 200
        timeout=30,
    )
    assert r.status_code == 200, r.text


# ===================== SINGLE OVERRIDE =====================
def test_master_override_single_reconstructs_relations(admin_token):
    pid = _pick_single(admin_token)
    bank_name, prods = _vpos_bank(admin_token)
    payload = {
        "status": "En Gestión",
        "quote_type": "VPOS",
        "banks_products": [{"bank_name": bank_name, "products": prods}],
    }
    r = requests.put(f"{API}/projects/{pid}/master-override", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code == 200, r.text

    p = _get_project(admin_token, pid)
    assert p.get("status") == "En Gestión"
    assert (p.get("quote_type") or "").upper() == "VPOS"

    # banks[] reconstructed: only the chosen bank
    banks = [b.get("bank_name") for b in (p.get("banks") or [])]
    assert banks == [bank_name], f"banks expected exactly [{bank_name}], got {banks}"

    # implementation_matrix reconstructed: only the chosen bank with selected products
    matrix = p.get("implementation_matrix") or {}
    assert set(matrix.keys()) == {bank_name}
    # Backend trims product names; compare normalized sets
    assert set((k or "").strip() for k in (matrix[bank_name] or {}).keys()) == set((p or "").strip() for p in prods)

    # services (additional) consistent: every additional service belongs to chosen bank+prods
    additional = [s for s in (p.get("services") or []) if s.get("item_type") == "additional"]
    if additional:
        for s in additional:
            assert s.get("bank_name", bank_name) in [bank_name, None, ""], f"orphan service: {s}"


# ===================== MULTISTORE OVERRIDE =====================
def test_master_override_multistore_union(admin_token):
    pid = _pick_multistore(admin_token)
    p = _get_project(admin_token, pid)
    bank_name, prods = _vpos_bank(admin_token)
    stores = p.get("stores") or []
    # Change ONLY the first store
    first_store_id = stores[0]["store_id"]
    payload = {
        "quote_type": "VPOS",
        "stores_products": [
            {"store_id": first_store_id, "banks_products": [{"bank_name": bank_name, "products": prods[:1]}]}
        ],
    }
    r = requests.put(f"{API}/projects/{pid}/master-override", headers=_h(admin_token), json=payload, timeout=30)
    assert r.status_code == 200, r.text

    p2 = _get_project(admin_token, pid)
    # First store matrix reconstructed
    s0 = next(s for s in p2["stores"] if s["store_id"] == first_store_id)
    assert set((s0.get("implementation_matrix") or {}).keys()) == {bank_name}

    # Top-level implementation_matrix is union of all stores
    union_banks = set()
    for s in p2["stores"]:
        for bn in (s.get("implementation_matrix") or {}).keys():
            union_banks.add(bn)
    assert set((p2.get("implementation_matrix") or {}).keys()) == union_banks, "top-level matrix should be union of stores"
    assert bank_name in (p2.get("implementation_matrix") or {})

    # banks[] consistent with union
    assert set(b.get("bank_name") for b in (p2.get("banks") or [])) == union_banks


# ===================== FICHA TECNICA =====================
def test_ficha_tecnica_after_override(admin_token):
    pid = _pick_single(admin_token)
    # Run an override first to ensure data was just reconstructed
    bank_name, prods = _vpos_bank(admin_token)
    requests.put(
        f"{API}/projects/{pid}/master-override",
        headers=_h(admin_token),
        json={"quote_type": "VPOS", "banks_products": [{"bank_name": bank_name, "products": prods}]},
        timeout=30,
    )
    r = requests.get(f"{API}/projects/{pid}/ficha-tecnica", headers=_h(admin_token), timeout=60)
    assert r.status_code == 200, f"ficha-tecnica failed: {r.status_code} {r.text[:300]}"
    # Should be a PDF
    ctype = r.headers.get("content-type", "")
    assert "pdf" in ctype.lower() or r.content[:4] == b"%PDF", f"unexpected content-type: {ctype}"
