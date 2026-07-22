"""
Iteration 292 — Reporte de Gestión de Implementadores V2
Endpoints:
  - GET  /api/reports/implementers/list
  - POST /api/reports/implementers/generate

Validaciones:
  1) list devuelve implementadores con user_id + name
  2) generate con implementer_ids=['all'] devuelve estructura y 13 métricas por bloque
  3) Aislamiento temporal para user_76c8aa92c813:
        - 2026-07-01..2026-07-31 -> culminados=0, cajas_culminados=0
        - 2026-06-01..2026-06-30 -> culminados=4, cajas_culminados=36
  4) Validación de fechas: from>to => 400, formato inválido => 400
  5) implementer_ids con un solo id filtra a un solo bloque
  6) Estructura de notificaciones (13 métricas presentes con enteros >=0)
"""
import os
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    env_path = Path('/app/frontend/.env')
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_frontend_env()
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = 'rgonzalez@megasoft.com.ve'
ADMIN_PASSWORD = 'admin123'

METRIC_KEYS = [
    'asignados', 'con_ticket', 'en_gestion', 'culminados', 'cajas_culminados',
    'parcial', 'suspendidos',
    'pvv_recibidos', 'pvv_configurados', 'pvv_probados', 'pvv_produccion',
    'notif_clientes', 'notif_bancos',
]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get('session_token') or data.get('token') or data.get('access_token')
    assert tok, f"no token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# --- 1) list ---
def test_list_implementers(auth_headers):
    r = requests.get(f"{BASE_URL}/api/reports/implementers/list", headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 'implementers' in d and 'total' in d
    assert isinstance(d['implementers'], list)
    assert d['total'] == len(d['implementers'])
    assert d['total'] >= 1
    for it in d['implementers']:
        assert 'user_id' in it and 'name' in it
        assert isinstance(it['user_id'], str) and it['user_id']
        assert isinstance(it['name'], str)
    # Save for other tests via env-like module cache
    test_list_implementers.result = d


# --- 2) generate all: estructura ---
def test_generate_all_structure(auth_headers):
    payload = {"date_from": "2026-01-01", "date_to": "2026-12-31", "implementer_ids": ["all"]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ('date_from', 'date_to', 'generated_at', 'count', 'results'):
        assert k in d, f"missing key {k}"
    assert d['date_from'] == "2026-01-01"
    assert d['date_to'] == "2026-12-31"
    assert d['count'] == len(d['results'])
    assert d['count'] >= 1
    for block in d['results']:
        assert 'implementer_id' in block and 'implementer_name' in block and 'metrics' in block
        m = block['metrics']
        for mk in METRIC_KEYS:
            assert mk in m, f"metric missing: {mk} in block {block['implementer_id']}"
            assert isinstance(m[mk], int), f"metric {mk} not int"
            assert m[mk] >= 0
    test_generate_all_structure.result = d


# --- 3) Aislamiento temporal (prueba de fuego) ---
TARGET_IMPL = 'user_76c8aa92c813'


def _find_block(results, impl_id):
    for b in results:
        if b['implementer_id'] == impl_id:
            return b
    return None


def test_isolation_july_empty(auth_headers):
    """En Julio 2026 el implementador target no tiene culminados."""
    payload = {"date_from": "2026-07-01", "date_to": "2026-07-31",
               "implementer_ids": [TARGET_IMPL]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['count'] == 1
    block = _find_block(d['results'], TARGET_IMPL)
    assert block is not None, f"target impl block missing: {d}"
    m = block['metrics']
    assert m['culminados'] == 0, f"expected 0 culminados en julio, got {m['culminados']}"
    assert m['cajas_culminados'] == 0, f"expected 0 cajas en julio, got {m['cajas_culminados']}"


def test_isolation_june_full(auth_headers):
    """En Junio 2026 debe haber 4 culminados / 36 cajas para el target."""
    payload = {"date_from": "2026-06-01", "date_to": "2026-06-30",
               "implementer_ids": [TARGET_IMPL]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    block = _find_block(d['results'], TARGET_IMPL)
    assert block is not None
    m = block['metrics']
    assert m['culminados'] == 4, f"expected 4 culminados en junio, got {m['culminados']}"
    assert m['cajas_culminados'] == 36, f"expected 36 cajas en junio, got {m['cajas_culminados']}"


def test_isolation_year_matches(auth_headers):
    """El total anual también debe reflejar 4 y 36 (los eventos existen solo en junio)."""
    payload = {"date_from": "2026-01-01", "date_to": "2026-12-31",
               "implementer_ids": [TARGET_IMPL]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    block = _find_block(d['results'], TARGET_IMPL)
    assert block is not None
    m = block['metrics']
    assert m['culminados'] == 4, f"expected 4 culminados anual, got {m['culminados']}"
    assert m['cajas_culminados'] == 36, f"expected 36 cajas anual, got {m['cajas_culminados']}"


# --- 4) Validaciones ---
def test_date_from_gt_to_returns_400(auth_headers):
    payload = {"date_from": "2026-07-31", "date_to": "2026-07-01",
               "implementer_ids": ["all"]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 400, r.text


def test_invalid_date_returns_400(auth_headers):
    payload = {"date_from": "bad-date", "date_to": "2026-07-01",
               "implementer_ids": ["all"]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 400, r.text


def test_unknown_implementer_returns_400(auth_headers):
    """Si el id no existe en el índice, no hay targets => 400."""
    payload = {"date_from": "2026-01-01", "date_to": "2026-12-31",
               "implementer_ids": ["nonexistent_id_xyz"]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 400, r.text


# --- 5) filtro por un solo implementador ---
def test_single_implementer_filter(auth_headers):
    payload = {"date_from": "2026-06-01", "date_to": "2026-06-30",
               "implementer_ids": [TARGET_IMPL]}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['count'] == 1
    assert d['results'][0]['implementer_id'] == TARGET_IMPL


# --- 6) empty implementer_ids equivale a "todos" ---
def test_empty_ids_equals_all(auth_headers):
    payload = {"date_from": "2026-06-01", "date_to": "2026-06-30",
               "implementer_ids": []}
    r = requests.post(f"{BASE_URL}/api/reports/implementers/generate",
                      headers=auth_headers, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d['count'] >= 1
