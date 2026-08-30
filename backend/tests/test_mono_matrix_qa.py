"""Tests for FIX: Monotienda project implementation_matrix pre-populated with exact quantities
   and NO regression for Multitienda projects."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
PHASES = ["Recibido", "Configurado", "Testeado", "En Producción"]


@pytest.fixture(scope="module")
def token():
    # Try common login endpoints
    for path in ["/api/auth/login", "/api/login"]:
        r = requests.post(f"{BASE_URL}{path}", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r.status_code == 200:
            data = r.json()
            tok = data.get("session_token") or data.get("access_token") or data.get("token") or (data.get("data") or {}).get("access_token")
            if tok:
                return tok
    pytest.skip("Cannot authenticate admin")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _find_project_by_quote(headers, quote_id):
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, params={"limit": 500})
    assert r.status_code == 200, f"GET /api/projects returned {r.status_code}: {r.text[:400]}"
    payload = r.json()
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("projects") or payload.get("data") or []
    else:
        items = payload
    for p in items:
        if p.get("quote_id") == quote_id or p.get("quote_number") in ("COT-MONO-QA", "COT-MULTI-QA") and p.get("quote_id") == quote_id:
            return p
    # Fallback loose match
    for p in items:
        if p.get("quote_id") == quote_id:
            return p
    return None


def _send_to_impl(headers, quote_id):
    h = dict(headers)
    h["x-exception-reason"] = "QA test"
    r = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", headers=h, json={})
    return r


def test_monotienda_matrix_exact_quantities(headers):
    r = _send_to_impl(headers, "qt_mono_qa")
    # It's OK if it fails due to email side-effects; project may still be created. Also idempotent.
    print(f"MONO send-to-impl status={r.status_code} body={r.text[:300]}")

    project = _find_project_by_quote(headers, "qt_mono_qa")
    assert project is not None, "Monotienda project not found after conversion"

    assert project.get("project_type") == "single", f"Expected project_type='single', got {project.get('project_type')}"

    matrix = project.get("implementation_matrix") or {}
    assert "Banco A QA" in matrix, f"Banco A QA not in matrix keys={list(matrix.keys())}"
    assert "Banco B QA" in matrix, f"Banco B QA not in matrix keys={list(matrix.keys())}"

    a = matrix["Banco A QA"].get("Pago Movil QA")
    b = matrix["Banco B QA"].get("Pago Movil QA")
    assert a is not None, f"Missing Pago Movil QA for Banco A: {matrix['Banco A QA']}"
    assert b is not None, f"Missing Pago Movil QA for Banco B: {matrix['Banco B QA']}"

    for phase in PHASES:
        assert phase in a, f"Banco A missing phase {phase}: {a}"
        assert a[phase].get("expected") == 2, f"Banco A phase {phase} expected!=2: {a[phase]}"
        assert phase in b, f"Banco B missing phase {phase}: {b}"
        assert b[phase].get("expected") == 4, f"Banco B phase {phase} expected!=4: {b[phase]}"


def test_multitienda_no_regression(headers):
    r = _send_to_impl(headers, "qt_multi_qa")
    print(f"MULTI send-to-impl status={r.status_code} body={r.text[:300]}")

    project = _find_project_by_quote(headers, "qt_multi_qa")
    assert project is not None, "Multitienda project not found after conversion"

    assert project.get("project_type") == "multistore", f"Expected multistore, got {project.get('project_type')}"

    stores = project.get("stores") or []
    assert len(stores) == 2, f"Expected 2 stores, got {len(stores)}"

    # Top-level implementation_matrix cells should NOT be pre-populated for multistore
    top_matrix = project.get("implementation_matrix") or {}
    for bank in ("Banco A QA", "Banco B QA"):
        if bank in top_matrix:
            cell = top_matrix[bank].get("Pago Movil QA")
            # If present, must be empty dict (no expected pre-populated)
            if cell:
                # verify no expected value assigned
                for phase in PHASES:
                    if phase in cell:
                        assert "expected" not in cell[phase] or cell[phase].get("expected") in (0, None), \
                            f"Multitienda top-matrix should not pre-populate expected: bank={bank} phase={phase} cell={cell[phase]}"

    # Per-store implementation_matrix: cells for known banks must be empty {}
    for i, store in enumerate(stores):
        store_matrix = store.get("implementation_matrix") or {}
        for bank in ("Banco A QA", "Banco B QA"):
            if bank in store_matrix:
                cell = store_matrix[bank].get("Pago Movil QA", {})
                assert cell == {} or cell is None, \
                    f"Store {i} bank {bank} expected empty cell, got: {cell}"
