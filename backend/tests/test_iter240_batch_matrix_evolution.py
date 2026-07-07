"""
Iter240 — Backend regression for the multi-selection Batch Matrix Update feature:
- POST /api/projects/{id}/matrix/batch-update
- Non-multistore project (prj_e86a47af1bff, PRY-2026-05-002-PRI)
- Multistore project (prj_e3cc3f3af922, PRY-2026-05-031-PRI)
- Legacy compat + validations + bitacora entry
"""
import os
import copy
import pytest
import requests

def _load_base_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    return ""

BASE_URL = _load_base_url()
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

PRJ_SINGLE = "prj_e86a47af1bff"   # No multitienda
PRJ_MULTI = "prj_e3cc3f3af922"    # Multitienda (1 tienda)

STORE_PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]


# -------------------- fixtures --------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in login: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _get_project(hdr, pid):
    r = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=hdr, timeout=30)
    assert r.status_code == 200, f"GET /projects/{pid} -> {r.status_code} {r.text[:200]}"
    return r.json()


@pytest.fixture(scope="module")
def snapshot_single(hdr):
    """Snapshot & restore implementation_matrix of NO-multitienda project."""
    p = _get_project(hdr, PRJ_SINGLE)
    original = copy.deepcopy(p.get("implementation_matrix") or {})
    yield p
    # NOTE: restore is best-effort via direct-DB not possible from tests; we leave the marks.
    # Bitacora entries will remain (audit purpose).


@pytest.fixture(scope="module")
def snapshot_multi(hdr):
    p = _get_project(hdr, PRJ_MULTI)
    yield p


# -------------------- BACKEND: validations --------------------

class TestValidations:
    def test_missing_phases_returns_400(self, hdr):
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr,
            json={"phases": [], "bank_products": {"Banco Mercantil": ["Pago C2P (PG)"]},
                  "store_ids": [], "reason": "QA no phases"},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"
        assert "fase" in r.text.lower()

    def test_missing_bank_products_returns_400(self, hdr):
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr,
            json={"phases": ["Recibido"], "bank_products": {}, "store_ids": [], "reason": "QA no bank"},
            timeout=30,
        )
        assert r.status_code == 400
        assert "banco" in r.text.lower() or "medio" in r.text.lower()

    def test_bank_with_empty_products_returns_400(self, hdr):
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr,
            json={"phases": ["Recibido"], "bank_products": {"Banco Mercantil": []},
                  "store_ids": [], "reason": "QA empty prods"},
            timeout=30,
        )
        assert r.status_code == 400

    def test_invalid_phase_returns_400(self, hdr):
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr,
            json={"phases": ["FaseInexistenteXYZ"],
                  "bank_products": {"Banco Mercantil": ["Pago C2P (PG)"]},
                  "store_ids": [], "reason": "QA invalid phase"},
            timeout=30,
        )
        assert r.status_code == 400
        assert "inv" in r.text.lower() or "fase" in r.text.lower()

    def test_multistore_without_store_ids_returns_400(self, hdr, snapshot_multi):
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_MULTI}/matrix/batch-update",
            headers=hdr,
            json={"phases": ["Recibido"],
                  "bank_products": {"Banesco Banco Universal": ["Pago C2P (PG)"]},
                  "store_ids": [], "reason": "QA multi no stores"},
            timeout=30,
        )
        assert r.status_code == 400
        assert "tienda" in r.text.lower()


# -------------------- BACKEND: no-multistore cruce --------------------

class TestSingleProjectBatchUpdate:
    def test_cross_multi_bank_multi_phase_success(self, hdr, snapshot_single):
        # Verify banks/products exist in matrix beforehand
        p = _get_project(hdr, PRJ_SINGLE)
        assert not (p.get("project_type") in ("multistore", "multirif") and p.get("stores")), \
            "expected no-multistore project"
        assert p.get("client_notified"), "project must be client_notified"
        matrix = p.get("implementation_matrix") or {}
        for b in ["Banco Mercantil", "Banco Nacional de Crédito (BNC)"]:
            assert b in matrix, f"bank {b} missing in matrix: {list(matrix.keys())}"
            assert "Pago C2P (PG)" in matrix[b], f"product missing under {b}: {list(matrix[b].keys())}"

        payload = {
            "phases": ["Recibido", "Configurado"],
            "bank_products": {
                "Banco Mercantil": ["Pago C2P (PG)"],
                "Banco Nacional de Crédito (BNC)": ["Pago C2P (PG)"],
            },
            "store_ids": [],
            "reason": "QA iter240 cruce non-multistore",
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr, json=payload, timeout=30,
        )
        assert r.status_code == 200, f"batch-update failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("is_multistore") is False
        assert set(body.get("phases", [])) == {"Recibido", "Configurado"}
        assert set(body.get("banks", [])) == {"Banco Mercantil", "Banco Nacional de Crédito (BNC)"}
        assert body.get("bitacora_entry_id")

        # GET → verify completed=true in project.implementation_matrix
        p2 = _get_project(hdr, PRJ_SINGLE)
        m2 = p2.get("implementation_matrix") or {}
        for b in ["Banco Mercantil", "Banco Nacional de Crédito (BNC)"]:
            prod = m2[b]["Pago C2P (PG)"]
            for ph in ["Recibido", "Configurado"]:
                cell = prod.get(ph) or {}
                assert cell.get("completed") is True, \
                    f"cell {b}/Pago C2P (PG)/{ph} not completed: {cell}"
                assert cell.get("batch_updated") is True

    def test_bitacora_entry_created(self, hdr):
        p = _get_project(hdr, PRJ_SINGLE)
        bit = p.get("bitacora") or []
        batch_entries = [e for e in bit if e.get("entry_type") == "batch_matrix_update"]
        assert batch_entries, "no batch_matrix_update entry in bitacora"
        last = batch_entries[-1]
        meta = last.get("batch_meta") or {}
        assert meta.get("is_multistore") is False
        assert "Recibido" in (meta.get("phases") or []) or "Configurado" in (meta.get("phases") or [])
        assert meta.get("bank_products"), "batch_meta.bank_products missing"

    def test_legacy_shape_still_works(self, hdr):
        payload = {
            "phase": "Recibido",
            "bank_name": "Banco Mercantil",
            "product_names": ["Pago C2P (PG)"],
            "store_ids": [],
            "reason": "QA iter240 legacy shape",
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_SINGLE}/matrix/batch-update",
            headers=hdr, json=payload, timeout=30,
        )
        assert r.status_code == 200, f"legacy shape failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("is_multistore") is False
        assert body.get("phases") == ["Recibido"]
        assert body.get("banks") == ["Banco Mercantil"]


# -------------------- BACKEND: multistore cruce --------------------

class TestMultistoreProjectBatchUpdate:
    def test_multistore_cross_two_banks_success(self, hdr, snapshot_multi):
        p = _get_project(hdr, PRJ_MULTI)
        assert p.get("project_type") in ("multistore", "multirif")
        stores = p.get("stores") or []
        assert stores, "multistore project must have at least one store"
        store_id = stores[0].get("store_id")
        assert store_id
        assert p.get("client_notified"), "project must be client_notified"

        # Get a store matrix to know banks/products present
        s_matrix = stores[0].get("implementation_matrix") or {}
        banks_in_store = list(s_matrix.keys())
        # Pick two banks that exist in store matrix
        target_banks = [b for b in ["Banesco Banco Universal", "Banco Nacional de Crédito (BNC)"]
                        if b in banks_in_store]
        if len(target_banks) < 2:
            pytest.skip(f"store matrix does not contain both target banks; has: {banks_in_store}")

        # Pick a product present under both banks
        def _first_product(bank):
            prods = list((s_matrix.get(bank) or {}).keys())
            assert prods, f"bank {bank} has no products in store matrix"
            return prods[0]

        bp = {b: [_first_product(b)] for b in target_banks}

        payload = {
            "phases": ["Recibido", "Configurado"],
            "bank_products": bp,
            "store_ids": [store_id],
            "reason": "QA iter240 cruce multistore",
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{PRJ_MULTI}/matrix/batch-update",
            headers=hdr, json=payload, timeout=30,
        )
        assert r.status_code == 200, f"multistore batch-update failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("is_multistore") is True
        assert body.get("stores_processed")
        assert len(body["stores_processed"]) == 1
        assert body["stores_processed"][0]["store_id"] == store_id

        # Verify store matrix now has completed=true for both banks/phases
        p2 = _get_project(hdr, PRJ_MULTI)
        s2 = next((s for s in (p2.get("stores") or []) if s.get("store_id") == store_id), None)
        assert s2
        m2 = s2.get("implementation_matrix") or {}
        for b, prods in bp.items():
            for prod in prods:
                for ph in ["Recibido", "Configurado"]:
                    cell = ((m2.get(b) or {}).get(prod) or {}).get(ph) or {}
                    assert cell.get("completed") is True, \
                        f"multistore cell {b}/{prod}/{ph} not completed: {cell}"

        # Rollup progress should exist and be a percentage number
        rp = p2.get("rollup_progress")
        assert rp is not None, "rollup_progress missing on project after batch update"

    def test_multistore_bitacora(self, hdr):
        p = _get_project(hdr, PRJ_MULTI)
        bit = p.get("bitacora") or []
        entries = [e for e in bit if e.get("entry_type") == "batch_matrix_update"]
        assert entries, "no batch_matrix_update bitacora entry on multistore project"
        meta = entries[-1].get("batch_meta") or {}
        assert meta.get("is_multistore") is True
        assert meta.get("stores"), "batch_meta.stores empty"
