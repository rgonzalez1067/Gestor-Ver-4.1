"""
Iter 277 — Bug Fix P0: Persistencia/Coexistencia de Integradores ante Ambiente de Pruebas

Regla de negocio:
- Un integrador con integrator_status='Certificado' que recibe una Asignación de
  Ambiente de Prueba NO debe canibalizar su perfil. Debe:
    * Coexistir en la Grilla de Integradores (GET /api/integrators default)
    * Seguir elegible para cotizaciones (integrator_status permanece 'Certificado')
    * Marcar project_scope='test_environment' con status_before_test_env='Certificado'
- Al CERRAR el Ambiente de Prueba:
    * NO archivar (NO integrator_status='Cerrado')
    * Restaurar status_before_test_env (ej 'Certificado')
    * project_scope=None
    * bypass=True, 200 OK
    * El documento maestro debe persistir en DB (NO eliminado)
- Regresión estándar (project_scope='new' o 'component'):
    * close_integrator_project sigue exigiendo componente+versión (400 si falta)
    * Al cerrar bien pasa a integrator_status='Certificado'
"""

import os
import pytest
import requests
from pathlib import Path


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL is required")


BASE_URL = _load_backend_url()

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    """Login admin y devuelve session_token."""
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _create_integrator(auth_headers, name_suffix, status="Certificado", scope=None):
    """Crea un integrador de prueba y devuelve su integrator_id."""
    payload = {
        "name": f"TEST_ITER277_{name_suffix}",
        "integrator_type": "Integrador",
        "integration_type": "P2C",
        "app_name": "TEST_APP_277",
        "integration_modality": "Directa",
        "integrator_status": status,
    }
    r = requests.post(f"{API}/integrators", json=payload, headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"Create integrator failed: {r.status_code} {r.text}"
    data = r.json()
    integrator_id = data["integrator_id"]

    # NOTA: al crear el primer registro con un nombre, get_or_create clasifica el
    # project_scope automáticamente ('new'). Para tests que necesitan project_scope=None,
    # forzamos a None vía update directo (no expuesto por API, mejor usar el flujo
    # normal y aceptar 'new' cuando corresponda). Para nuestro escenario 'Certificado'
    # queremos project_scope=None; forzamos vía PUT o direct DB set.
    return integrator_id


def _fetch(auth_headers, integrator_id):
    r = requests.get(f"{API}/integrators", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    for item in r.json():
        if item.get("integrator_id") == integrator_id:
            return item
    return None


def _delete_integrator(auth_headers, integrator_id):
    try:
        requests.delete(f"{API}/integrators/{integrator_id}", headers=auth_headers, timeout=30)
    except Exception:
        pass


# ---------- TESTS ----------

class TestAssignTestEnvironmentPreservesCertificado:
    """P0: assign-test-environment sobre integrador 'Certificado' NO canibaliza estatus."""

    def test_assign_test_env_preserves_certificado_status(self, auth_headers):
        # Setup: crear integrador
        integrator_id = _create_integrator(auth_headers, "assign_cert_preserve", status="Certificado")
        try:
            # Antes de assign: verificar existe y está Certificado
            before = _fetch(auth_headers, integrator_id)
            assert before is not None, "Integrator not created"
            assert before["integrator_status"] == "Certificado"

            # Assign test environment
            payload = {"start_date": "2026-02-01", "end_date": "2026-02-28"}
            r = requests.post(
                f"{API}/integrators/{integrator_id}/assign-test-environment",
                json=payload, headers=auth_headers, timeout=30,
            )
            assert r.status_code == 200, f"assign-test-environment failed: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("status") == "ok"
            intg = body.get("integrator")
            assert intg is not None

            # Assertions clave: estatus preservado y snapshot guardado
            assert intg["integrator_status"] == "Certificado", (
                f"integrator_status debe seguir 'Certificado', fue: {intg['integrator_status']}"
            )
            assert intg["project_scope"] == "test_environment"
            assert intg.get("status_before_test_env") == "Certificado"
            assert intg.get("test_env_start_date", "").startswith("2026-02-01")
            assert intg.get("test_env_end_date", "").startswith("2026-02-28")
        finally:
            _delete_integrator(auth_headers, integrator_id)


class TestListingWhileTestEnvActive:
    """P0: mientras el Ambiente de Prueba está activo, el integrador debe seguir en la grilla."""

    def test_get_integrators_default_still_returns_test_env_integrator(self, auth_headers):
        integrator_id = _create_integrator(auth_headers, "listing_active", status="Certificado")
        try:
            payload = {"start_date": "2026-02-01", "end_date": "2026-02-28"}
            r = requests.post(
                f"{API}/integrators/{integrator_id}/assign-test-environment",
                json=payload, headers=auth_headers, timeout=30,
            )
            assert r.status_code == 200

            # GET /api/integrators default (sin params) — debe seguir devolviéndolo
            r = requests.get(f"{API}/integrators", headers=auth_headers, timeout=30)
            assert r.status_code == 200
            items = r.json()
            match = [i for i in items if i.get("integrator_id") == integrator_id]
            assert len(match) == 1, "El integrador con Ambiente de Prueba activo NO aparece en la grilla default"
            intg = match[0]
            assert intg["integrator_status"] == "Certificado"
            assert intg["project_scope"] == "test_environment"
            # Sigue siendo elegible para cotizaciones (regla wizard: integrator_status==='Certificado')
        finally:
            _delete_integrator(auth_headers, integrator_id)


class TestCloseTestEnvRestoresStatus:
    """P0: cerrar Ambiente de Prueba restaura estatus previo (NO archiva, NO borra)."""

    def test_close_test_env_restores_certificado_and_preserves_record(self, auth_headers):
        integrator_id = _create_integrator(auth_headers, "close_restore", status="Certificado")
        try:
            # Asignar test env
            r = requests.post(
                f"{API}/integrators/{integrator_id}/assign-test-environment",
                json={"start_date": "2026-02-01", "end_date": "2026-02-28"},
                headers=auth_headers, timeout=30,
            )
            assert r.status_code == 200

            # Cerrar (multipart/form-data, SIN componente/versión — bypass test_environment)
            close_headers = {"Authorization": auth_headers["Authorization"]}  # sin Content-Type json
            r = requests.post(
                f"{API}/integrators/{integrator_id}/close",
                headers=close_headers,
                data={},  # sin componente ni version
                files=[],  # no attachments
                timeout=60,
            )
            assert r.status_code == 200, f"close bypass falló: {r.status_code} {r.text}"
            body = r.json()
            assert body.get("status") == "ok"
            assert body.get("bypass") is True, "El close de test_environment debe devolver bypass=True"

            intg = body.get("integrator")
            assert intg is not None
            # Estatus restaurado a 'Certificado' (NO 'Cerrado')
            assert intg["integrator_status"] == "Certificado", (
                f"Debe restaurarse a 'Certificado', fue: {intg['integrator_status']}"
            )
            assert intg["integrator_status"] != "Cerrado"
            # project_scope quedó null
            assert intg.get("project_scope") in (None, ""), (
                f"project_scope debe ser None, fue: {intg.get('project_scope')}"
            )
            # snapshot limpiado
            assert intg.get("status_before_test_env") in (None, ""), "status_before_test_env debe estar unset"

            # Verificar que el documento maestro persiste (no eliminado)
            r = requests.get(f"{API}/integrators?show_all=true", headers=auth_headers, timeout=30)
            assert r.status_code == 200
            all_items = r.json()
            match = [i for i in all_items if i.get("integrator_id") == integrator_id]
            assert len(match) == 1, "El registro maestro fue ELIMINADO al cerrar el Ambiente de Prueba (bug)"
            assert match[0]["integrator_status"] == "Certificado"
        finally:
            _delete_integrator(auth_headers, integrator_id)

    def test_close_test_env_still_appears_in_default_grid(self, auth_headers):
        """Al cerrar el Ambiente de Prueba, el integrador restaurado a 'Certificado'
        sigue apareciendo en la vista default (GET /api/integrators sin filtros)."""
        integrator_id = _create_integrator(auth_headers, "close_still_in_grid", status="Certificado")
        try:
            requests.post(
                f"{API}/integrators/{integrator_id}/assign-test-environment",
                json={"start_date": "2026-02-01", "end_date": "2026-02-28"},
                headers=auth_headers, timeout=30,
            )
            close_headers = {"Authorization": auth_headers["Authorization"]}
            r = requests.post(
                f"{API}/integrators/{integrator_id}/close",
                headers=close_headers, data={}, files=[], timeout=60,
            )
            assert r.status_code == 200

            # Grilla default (excluye solo 'Cerrado')
            r = requests.get(f"{API}/integrators", headers=auth_headers, timeout=30)
            assert r.status_code == 200
            items = r.json()
            match = [i for i in items if i.get("integrator_id") == integrator_id]
            assert len(match) == 1, "Integrador no aparece en grilla default tras cerrar Ambiente de Prueba"
            assert match[0]["integrator_status"] == "Certificado"
            assert match[0].get("project_scope") in (None, "")
        finally:
            _delete_integrator(auth_headers, integrator_id)


class TestStandardCloseStillRequiresComponent:
    """Regresión: cierre de proyecto ESTÁNDAR (scope 'new') sigue exigiendo componente+versión."""

    def test_standard_close_without_component_returns_400(self, auth_headers):
        # Crear integrador (primer registro → scope='new' automático)
        integrator_id = _create_integrator(auth_headers, "std_close_missing_comp", status="En proceso")
        try:
            # Confirmar scope='new'
            intg = _fetch(auth_headers, integrator_id)
            assert intg is not None
            assert intg.get("project_scope") == "new", (
                f"Primer registro debía clasificar como 'new'; fue: {intg.get('project_scope')}"
            )

            close_headers = {"Authorization": auth_headers["Authorization"]}
            r = requests.post(
                f"{API}/integrators/{integrator_id}/close",
                headers=close_headers,
                data={},  # sin componente ni versión
                files=[],
                timeout=60,
            )
            assert r.status_code == 400, (
                f"Cierre estándar sin componente/versión debe devolver 400, fue: {r.status_code} {r.text}"
            )
            detail = (r.json() or {}).get("detail", "")
            assert "Componente" in detail and "Versión" in detail
        finally:
            _delete_integrator(auth_headers, integrator_id)

    def test_standard_close_with_component_moves_to_certificado(self, auth_headers):
        integrator_id = _create_integrator(auth_headers, "std_close_ok", status="En proceso")
        try:
            close_headers = {"Authorization": auth_headers["Authorization"]}
            # Adjuntar un archivo vacío mínimo — files=[] es válido según el endpoint
            r = requests.post(
                f"{API}/integrators/{integrator_id}/close",
                headers=close_headers,
                data={"componente": "MotorCore", "version_componente": "1.2.3"},
                files=[],
                timeout=90,
            )
            assert r.status_code == 200, f"Cierre estándar OK falló: {r.status_code} {r.text}"

            # Verificar que quedó Certificado con project_scope=None
            all_items = requests.get(f"{API}/integrators?show_all=true", headers=auth_headers, timeout=30).json()
            match = [i for i in all_items if i.get("integrator_id") == integrator_id]
            assert len(match) == 1, "Registro estándar fue eliminado incorrectamente al cerrar"
            intg = match[0]
            assert intg["integrator_status"] == "Certificado"
            assert intg.get("project_scope") in (None, "")
        finally:
            _delete_integrator(auth_headers, integrator_id)


class TestRoundTripFullScenario:
    """Escenario integral: Certificado → assign test env → close test env → sigue Certificado."""

    def test_round_trip_certified_integrator(self, auth_headers):
        integrator_id = _create_integrator(auth_headers, "round_trip", status="Certificado")
        try:
            # (1) assign
            r = requests.post(
                f"{API}/integrators/{integrator_id}/assign-test-environment",
                json={"start_date": "2026-03-01", "end_date": "2026-03-31"},
                headers=auth_headers, timeout=30,
            )
            assert r.status_code == 200
            intg = r.json()["integrator"]
            assert intg["integrator_status"] == "Certificado"
            assert intg["project_scope"] == "test_environment"
            assert intg["status_before_test_env"] == "Certificado"

            # (2) sigue en grilla + elegible para cotizaciones
            grid = requests.get(f"{API}/integrators", headers=auth_headers, timeout=30).json()
            found = next((i for i in grid if i.get("integrator_id") == integrator_id), None)
            assert found is not None
            assert found["integrator_status"] == "Certificado"

            # (3) close bypass
            close_headers = {"Authorization": auth_headers["Authorization"]}
            r = requests.post(
                f"{API}/integrators/{integrator_id}/close",
                headers=close_headers, data={}, files=[], timeout=60,
            )
            assert r.status_code == 200
            body = r.json()
            assert body["bypass"] is True
            final = body["integrator"]
            assert final["integrator_status"] == "Certificado"
            assert final.get("project_scope") in (None, "")

            # (4) persistencia final: sigue existiendo
            grid = requests.get(f"{API}/integrators", headers=auth_headers, timeout=30).json()
            found = next((i for i in grid if i.get("integrator_id") == integrator_id), None)
            assert found is not None, "El integrador desapareció tras el ciclo assign→close (bug crítico)"
            assert found["integrator_status"] == "Certificado"
        finally:
            _delete_integrator(auth_headers, integrator_id)
