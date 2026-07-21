"""Backend tests — Iteration 286: Taller Recepción de Equipos (Fase 1).

Cubre:
- POST /api/taller/recepcion crea equipos con estatus 'Recibido'
- GET /api/other-actions/catalog incluye 'taller_recepcion_equipos'
- GET /api/admin/permission-catalog incluye módulos 'taller_recepcion' (Recepción de Equipos)
  y 'taller_equipos' renombrado a 'Consulta de Taller'
- GET /api/taller-equipos filtrado por estatus='Recibido' devuelve los recién creados
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

SERIAL_PREFIX = f"QA-REC-{int(time.time())}"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token")
    assert tok, f"No token in response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def a_client(headers):
    """Obtiene un cliente cualquiera existente para las pruebas."""
    r = requests.get(f"{BASE_URL}/api/clients/search?q=a", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    arr = r.json()
    assert isinstance(arr, list) and len(arr) > 0, "No hay clientes para la prueba"
    return arr[0]


# ---------------------------------------------------------------------------
# Otras Acciones — catálogo incluye taller_recepcion_equipos
# ---------------------------------------------------------------------------
class TestOtherActionsCatalog:
    def test_catalog_has_taller_recepcion_equipos(self, headers):
        r = requests.get(f"{BASE_URL}/api/other-actions/catalog", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "actions" in data
        ids = [a["id"] for a in data["actions"]]
        assert "taller_recepcion_equipos" in ids, f"Missing action, got: {ids}"
        action = next(a for a in data["actions"] if a["id"] == "taller_recepcion_equipos")
        # variables clave documentadas
        for v in ("Nombre_Cliente", "Equipos_Recibidos", "Cantidad_Equipos", "Fecha_Recepcion"):
            assert v in action["variables"], f"Missing var {v} in {action['variables']}"


# ---------------------------------------------------------------------------
# Permission catalog — taller_recepcion y taller_equipos (renombrado)
# ---------------------------------------------------------------------------
class TestPermissionCatalog:
    def test_catalog_includes_taller_modules(self, headers):
        r = requests.get(f"{BASE_URL}/api/admin/permission-catalog", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        modules = {m["id"]: m for m in data.get("modules", [])}
        assert "taller_recepcion" in modules, "Falta módulo taller_recepcion"
        assert modules["taller_recepcion"]["name"] == "Recepción de Equipos"
        assert modules["taller_recepcion"]["group"] == "gestion_taller"

        assert "taller_equipos" in modules
        assert modules["taller_equipos"]["name"] == "Consulta de Taller"
        assert modules["taller_equipos"]["group"] == "gestion_taller"


# ---------------------------------------------------------------------------
# POST /api/taller/recepcion — flujo completo y persistencia
# ---------------------------------------------------------------------------
class TestRecepcion:
    created_serials = []

    def test_recepcion_creates_equipos_recibido(self, headers, a_client):
        payload = {
            "client_id": a_client["client_id"],
            "client_name": a_client.get("fantasy_name") or a_client.get("legal_name") or "",
            "client_rif": a_client.get("rif") or "",
            "models": [
                {
                    "model_id": "",
                    "model_name": "POS QA Model",
                    "serials": [f"{SERIAL_PREFIX}-A", f"{SERIAL_PREFIX}-B"],
                }
            ],
        }
        r = requests.post(f"{BASE_URL}/api/taller/recepcion", headers=headers, json=payload, timeout=30)
        assert r.status_code == 200, f"POST recepcion failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("created") == 2
        assert data.get("estatus") == "Recibido"
        TestRecepcion.created_serials = [f"{SERIAL_PREFIX}-A", f"{SERIAL_PREFIX}-B"]

    def test_recepcion_no_serials_returns_400(self, headers, a_client):
        payload = {
            "client_id": a_client["client_id"],
            "models": [{"model_name": "POS QA", "serials": []}],
        }
        r = requests.post(f"{BASE_URL}/api/taller/recepcion", headers=headers, json=payload, timeout=15)
        assert r.status_code == 400, f"Should be 400, got {r.status_code}: {r.text}"

    def test_taller_equipos_filter_recibido(self, headers):
        # Filtrar por estatus 'Recibido' — deben aparecer los seriales QA
        r = requests.get(f"{BASE_URL}/api/taller-equipos?estatus=Recibido",
                         headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        equipos = data.get("equipos", [])
        serials = {e.get("serial") for e in equipos}
        for s in TestRecepcion.created_serials:
            assert s in serials, f"Serial {s} no aparece en Recibido. Total={len(serials)}"

    def test_taller_equipos_search_by_serial(self, headers):
        if not TestRecepcion.created_serials:
            pytest.skip("No hay seriales creados")
        target = TestRecepcion.created_serials[0]
        r = requests.get(f"{BASE_URL}/api/taller-equipos?search={target}",
                         headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        equipos = data.get("equipos", [])
        found = [e for e in equipos if e.get("serial") == target]
        assert len(found) == 1, f"Se esperaba 1 registro, se hallaron {len(found)}"
        eq = found[0]
        assert eq["estatus"] == "Recibido"
        assert eq.get("modelo") == "POS QA Model"


# ---------------------------------------------------------------------------
# Teardown — limpieza de seriales QA creados
# ---------------------------------------------------------------------------
def test_zzz_cleanup(headers):
    """Ejecuta después que las pruebas: elimina registros con prefijo QA-REC-.
    (name starts with 'test_zzz_' para ordenar al final)."""
    if not TestRecepcion.created_serials:
        pytest.skip("Nada que limpiar")
    r = requests.get(f"{BASE_URL}/api/taller-equipos?search={SERIAL_PREFIX}",
                     headers=headers, timeout=15)
    assert r.status_code == 200
    equipos = r.json().get("equipos", [])
    for eq in equipos:
        tid = eq.get("taller_equipo_id") or eq.get("taller_id")
        if tid:
            requests.delete(f"{BASE_URL}/api/taller-equipos/{tid}", headers=headers, timeout=10)
    # Nota: el endpoint delete usa taller_equipo_id; los docs creados usan taller_id.
    # Este cleanup best-effort no falla si la limpieza no procede.
