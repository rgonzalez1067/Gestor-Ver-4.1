"""Iter271 - Cierre automatizado de Proyectos de Integración.

Cubre 4 escenarios:
  A) Depósito de Certificado (upload PDF + GET exists)
  B) BYPASS Ambiente de Prueba (qa_close_tenv)
  C) ESTÁNDAR NUEVO (qa_close_new) — 400 sin campos, éxito con Componente/Versión
  D) AMPLIACIÓN (qa_close_exp) — replaced=True + una sola fila del binomio
"""
import asyncio
import os
import sys
import pytest
import requests

# Cargar .env del backend para MONGO_URL / DB_NAME
_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.abspath(os.path.join(_HERE, "..", ".env")))
except Exception:
    pass

from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://integrator-hub-6.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _get_db():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


async def _reseed_qa_integrators():
    db = _get_db()
    now = "2026-01-01T00:00:00+00:00"
    docs = [
        {"integrator_id": "qa_close_new", "name": "QA_CLOSE_NEW", "app_name": "AppNueva",
         "integrator_type": "Comercio", "integration_type": "API Rest", "integration_modality": "Directa",
         "integrator_status": "En proceso", "project_scope": "new",
         "principal_contact_email": "qa_integrador@test.com",
         "certifications": {"prod_c2p": "C", "prod_verificacion_p2c": "C", "prod_biopago": "P"},
         "created_at": now},
        {"integrator_id": "qa_close_tenv", "name": "QA_CLOSE_TENV", "app_name": "AppPrueba",
         "integrator_type": "Comercio", "integration_type": "API Rest", "integration_modality": "Directa",
         "integrator_status": "En proceso", "project_scope": "test_environment",
         "certifications": {"prod_c2p": "C", "prod_verificacion_p2c": "C", "prod_biopago": "P"},
         "created_at": now},
        {"integrator_id": "qa_close_base", "name": "QA_CLOSE_AMP", "app_name": "AppVieja",
         "integrator_type": "Comercio", "integration_type": "Plugin", "integration_modality": "Directa",
         "integrator_status": "Certificado", "project_scope": None,
         "cert_version": "v1.0", "cert_component": "SDK Base",
         "certifications": {"prod_c2p": "C"},
         "created_at": now},
        {"integrator_id": "qa_close_exp", "name": "QA_CLOSE_AMP", "app_name": "AppNuevaAmp",
         "integrator_type": "Comercio", "integration_type": "Plugin", "integration_modality": "Directa",
         "integrator_status": "En proceso", "project_scope": "expansion",
         "principal_contact_email": "qa_amp@test.com",
         "certifications": {"prod_c2p": "C", "prod_verificacion_p2c": "C", "prod_biopago": "P"},
         "created_at": now},
    ]
    for d in docs:
        await db.integrators.update_one(
            {"integrator_id": d["integrator_id"]},
            {"$set": d},
            upsert=True,
        )


@pytest.fixture(scope="module", autouse=True)
def _reseed():
    _run(_reseed_qa_integrators())
    yield


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("session_token") or body.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _mini_pdf_bytes():
    # Minimal valid PDF (1 page, blank). ~500 bytes.
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<<>>>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000053 00000 n \n"
        b"0000000098 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n170\n%%EOF\n"
    )


# --- (A) Depósito de Certificado ---
class TestCertificateDeposit:
    def test_a1_upload_pdf_to_deposit(self, headers):
        files = {"file": ("cert_base.pdf", _mini_pdf_bytes(), "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/integrators/config/certificate", headers=headers, files=files)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok", data
        assert data.get("original_name") == "cert_base.pdf"

    def test_a2_get_info_shows_exists(self, headers):
        r = requests.get(f"{BASE_URL}/api/integrators/config/certificate", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data.get("exists") is True, f"esperado exists=True, got {data}"


# --- (B) BYPASS Ambiente de Prueba ---
class TestBypassTestEnvironment:
    def test_b1_close_test_env_bypass(self, headers):
        # asegurar que qa_close_tenv está en estado en proceso + scope test_environment
        r0 = requests.get(f"{BASE_URL}/api/integrators/qa_close_tenv", headers=headers)
        assert r0.status_code == 200, r0.text
        j0 = r0.json()
        assert j0.get("project_scope") == "test_environment", f"seed roto: {j0.get('project_scope')}"

        r = requests.post(
            f"{BASE_URL}/api/integrators/qa_close_tenv/close",
            headers=headers,
            data={},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("bypass") is True, f"bypass esperado True: {data}"
        assert data.get("integrator", {}).get("integrator_status") == "Cerrado"
        # No cert / no notification
        assert data.get("notification") in (None, {}, ), f"no debería haber notification: {data.get('notification')}"


# --- (C) ESTÁNDAR NUEVO ---
class TestStandardNewClose:
    def test_c1_missing_fields_returns_400(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/integrators/qa_close_new/close",
            headers=headers,
            data={},  # sin componente/version
        )
        assert r.status_code == 400, f"esperado 400 sin campos, got {r.status_code}: {r.text}"

    def test_c2_close_new_success_with_certificate(self, headers):
        # sanity: el registro debe estar activo
        r0 = requests.get(f"{BASE_URL}/api/integrators/qa_close_new", headers=headers)
        assert r0.status_code == 200
        assert r0.json().get("integrator_status") != "Certificado", "seed ya cerrado — re-seedear"

        r = requests.post(
            f"{BASE_URL}/api/integrators/qa_close_new/close",
            headers=headers,
            data={
                "componente": "Plugin WooCommerce",
                "version_componente": "v2.4.1",
                "extra_recipients": "qa_extra@example.com",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("bypass") is False
        assert data.get("replaced") is False
        assert data.get("certificate_generated") is True, f"cert no generado: {data}"
        pc = data.get("productos_certificados") or ""
        # formato con ' / ' cuando hay más de un producto certificado
        assert isinstance(pc, str), pc
        assert data["integrator"]["integrator_status"] == "Certificado"

    def test_c3_appears_in_ver_todos_after_close(self, headers):
        # Con show_all debe estar; en la Vista de Proyectos activos (filtro cliente por
        # project_scope in {new, component, expansion, test_environment}) el registro
        # Certificado sale del listado (project_scope se pone a null tras el cierre).
        r_all = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=headers)
        assert r_all.status_code == 200
        rows_all = r_all.json()
        row = next((i for i in rows_all if i.get("integrator_id") == "qa_close_new"), None)
        assert row is not None, "no aparece en show_all=true"
        assert row.get("integrator_status") == "Certificado"
        # project_scope debe quedar null (fuera de la vista de proyectos activos filtrada por FE)
        assert row.get("project_scope") in (None, ""), f"project_scope debía ser null: {row.get('project_scope')}"


# --- (D) AMPLIACIÓN ---
class TestExpansionClose:
    def test_d1_close_expansion_replaces_base(self, headers):
        # Antes del cierre: 2 filas del binomio (base Certificado + expansion en proceso)
        r_all = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=headers)
        assert r_all.status_code == 200
        pre_rows = [i for i in r_all.json() if i.get("name") == "QA_CLOSE_AMP" and i.get("integration_type") == "Plugin"]
        pre_ids = sorted([i.get("integrator_id") for i in pre_rows])
        assert set(pre_ids) >= {"qa_close_base", "qa_close_exp"}, f"binomio pre-cierre inesperado: {pre_ids}"

        r = requests.post(
            f"{BASE_URL}/api/integrators/qa_close_exp/close",
            headers=headers,
            data={"componente": "SDK Android", "version_componente": "v3.0"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("replaced") is True, f"esperado replaced=True: {data}"
        assert data.get("certificate_generated") is True

    def test_d2_only_one_row_of_binomio_remains(self, headers):
        r_all = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=headers)
        assert r_all.status_code == 200
        rows = [i for i in r_all.json() if i.get("name") == "QA_CLOSE_AMP" and i.get("integration_type") == "Plugin"]
        assert len(rows) == 1, f"debería quedar 1 sola fila, hay {len(rows)}: {[r.get('integrator_id') for r in rows]}"
        row = rows[0]
        assert row.get("integrator_id") == "qa_close_base", f"debería conservarse qa_close_base: {row.get('integrator_id')}"
        # Datos NUEVOS: app_name y version del cierre
        assert row.get("app_name") == "AppNuevaAmp", f"app_name debía ser 'AppNuevaAmp': {row.get('app_name')}"
        assert row.get("integrator_status") == "Certificado"
        # cert_version no está expuesto por response_model=Integrator; validar en DB directa
        _db = _get_db()
        _doc = _run(_db.integrators.find_one({"integrator_id": "qa_close_base"}, {"_id": 0}))
        assert _doc.get("cert_version") == "v3.0", f"cert_version en DB: {_doc.get('cert_version')}"
        assert _doc.get("cert_component") == "SDK Android", f"cert_component en DB: {_doc.get('cert_component')}"

        # El registro de expansion debe haber sido eliminado
        r_exp = requests.get(f"{BASE_URL}/api/integrators/qa_close_exp", headers=headers)
        assert r_exp.status_code == 404, f"qa_close_exp debía estar eliminado: {r_exp.status_code}"


# --- (E) Empty deposit → certificate_generated=false (pero cierre procede) ---
class TestEmptyDepositStillCloses:
    """Después de todo, borramos el certificado y creamos un nuevo integrador dummy
    para probar que sin PDF en depósito, certificate_generated=False (no bloquea)."""

    def test_e1_delete_deposit(self, headers):
        r = requests.delete(f"{BASE_URL}/api/integrators/config/certificate", headers=headers)
        assert r.status_code in (200, 204)
        r2 = requests.get(f"{BASE_URL}/api/integrators/config/certificate", headers=headers)
        assert r2.status_code == 200
        assert r2.json().get("exists") is False

    def test_e2_close_without_deposit_still_ok(self, headers):
        # Crear integrador de prueba (usa endpoint upsert)
        payload = {
            "name": "QA_CLOSE_EMPTY_DEPOSIT",
            "app_name": "AppSinDeposito",
            "integration_type": "API Rest",
            "integrator_type": "Comercio",
            "integration_modality": "Directa",
            "project_scope": "new",
            "principal_contact_email": "qa_empty@example.com",
            "certifications": {"P2C": "C"},
        }
        rc = requests.post(f"{BASE_URL}/api/integrators", headers=headers, json=payload)
        assert rc.status_code in (200, 201), rc.text
        new_id = rc.json().get("integrator_id")
        assert new_id

        try:
            r = requests.post(
                f"{BASE_URL}/api/integrators/{new_id}/close",
                headers=headers,
                data={"componente": "X", "version_componente": "1.0"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("bypass") is False
            assert data.get("certificate_generated") is False, "sin PDF depósito → cert_generated=False"
            assert data["integrator"]["integrator_status"] == "Certificado"
        finally:
            requests.delete(f"{BASE_URL}/api/integrators/{new_id}", headers=headers)
