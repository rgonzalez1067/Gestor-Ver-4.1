"""Backend tests iter274 — Comunicación Masiva a Integradores (BCC).

Cubre:
  * GET /integrators/mass/recipients (con y sin filtro por tipo)
  * Permisología (403 no-admin sin flag; admin OK)
  * POST /integrators/mass/communication (envío BCC + adjuntos)
  * Validaciones 400 y 422
"""
import os
import io
import json
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

# Cargar .env del backend explícitamente (pytest no lo lee)
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env", override=False)

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or '').rstrip('/') + '/api'
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
NON_ADMIN = {"email": "jrojas@megasoft.com.ve", "password": "Test1234!"}


# ---------- Fixtures ---------- #
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="session")
def non_admin_token():
    r = requests.post(f"{BASE_URL}/auth/login", json=NON_ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"non-admin login failed: {r.status_code}")
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def non_admin_headers(non_admin_token):
    return {"Authorization": f"Bearer {non_admin_token}"}


@pytest.fixture(scope="session")
def test_integrators(admin_headers):
    """Crea 3 integradores de prueba (2 con email, 1 sin email), tipo=PG.
    Los borra al terminar junto con sus email_logs."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    ids = []
    docs = [
        {"integrator_id": f"int_TEST_{uuid.uuid4().hex[:8]}",
         "name": f"TEST_MASS_A_{uuid.uuid4().hex[:4]}",
         "email": "ragg1008+testA@example.com",
         "integration_type": "PG",
         "integrator_status": "En proceso",
         "contacts": [{"name": "Contacto A"}]},
        {"integrator_id": f"int_TEST_{uuid.uuid4().hex[:8]}",
         "name": f"TEST_MASS_B_{uuid.uuid4().hex[:4]}",
         "email": "ragg1008+testB@example.com",
         "integration_type": "PG",
         "integrator_status": "En proceso",
         "contacts": [{"name": "Contacto B"}]},
        {"integrator_id": f"int_TEST_{uuid.uuid4().hex[:8]}",
         "name": f"TEST_MASS_C_NOMAIL_{uuid.uuid4().hex[:4]}",
         "email": "",
         "integration_type": "PG",
         "integrator_status": "En proceso",
         "contacts": []},
    ]

    async def _setup():
        for d in docs:
            await db.integrators.insert_one({**d})
            ids.append(d["integrator_id"])

    asyncio.get_event_loop().run_until_complete(_setup())
    yield [d["integrator_id"] for d in docs], docs

    async def _teardown():
        await db.integrators.delete_many({"integrator_id": {"$in": ids}})
        await db.email_logs.delete_many({"action": "integrator_mass_communication",
                                          "bcc_count": {"$in": [1, 2]}})
        await db.bitacora.delete_many({"action": "integrator_mass_communication",
                                        "recipients_count": {"$in": [1, 2]}})
    asyncio.get_event_loop().run_until_complete(_teardown())
    client.close()


# ---------- Health / setup ---------- #
class TestHealth:
    def test_login_admin(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 5


# ---------- GET recipients ---------- #
class TestRecipients:
    def test_recipients_no_filter(self, admin_headers, test_integrators):
        r = requests.get(f"{BASE_URL}/integrators/mass/recipients", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Estructura
        assert set(["recipients", "total", "with_email", "integration_types"]).issubset(data.keys())
        assert isinstance(data["recipients"], list)
        # Contiene claves esperadas
        sample = data["recipients"][0]
        for k in ("integrator_id", "name", "contact", "email", "has_email",
                  "integration_type", "integration_type_label"):
            assert k in sample
        # Total razonable (~589 esperado por spec; tolerancia amplia)
        assert data["total"] >= 100, f"total demasiado bajo: {data['total']}"
        # integration_types debe incluir los 5 códigos
        codes = {t["code"] for t in data["integration_types"]}
        assert {"CR", "LP", "PG", "MP", "TK"}.issubset(codes)

    def test_recipients_pg_filter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/integrators/mass/recipients?integration_type=PG",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Todas las filas devueltas deben ser PG
        for row in data["recipients"]:
            assert row["integration_type"] == "PG", f"Fila no-PG: {row}"
        assert data["total"] >= 1

    def test_recipients_filter_reduces_total(self, admin_headers):
        r_all = requests.get(f"{BASE_URL}/integrators/mass/recipients",
                             headers=admin_headers, timeout=30).json()
        r_pg = requests.get(f"{BASE_URL}/integrators/mass/recipients?integration_type=PG",
                            headers=admin_headers, timeout=30).json()
        assert r_pg["total"] <= r_all["total"]

    def test_recipients_contact_dash_when_missing(self, admin_headers, test_integrators):
        """Los integradores sin contacto muestran contact=''; la UI pinta '—'."""
        ids, docs = test_integrators
        r = requests.get(f"{BASE_URL}/integrators/mass/recipients?integration_type=PG",
                         headers=admin_headers, timeout=30).json()
        found = {row["integrator_id"]: row for row in r["recipients"]}
        # El integrador C no tiene contacts
        c_id = ids[2]
        assert c_id in found, "Integrador de prueba C no encontrado"
        assert found[c_id]["contact"] == "" or found[c_id]["contact"] is None
        assert found[c_id]["has_email"] is False


# ---------- Permisos ---------- #
class TestPermissions:
    def test_forbidden_recipients_non_admin_no_flag(self, non_admin_headers):
        r = requests.get(f"{BASE_URL}/integrators/mass/recipients", headers=non_admin_headers, timeout=30)
        assert r.status_code == 403, f"Se esperaba 403, obtuvo {r.status_code}: {r.text[:200]}"

    def test_forbidden_send_non_admin_no_flag(self, non_admin_headers):
        data = {
            "template_id": "any",
            "integrator_ids": json.dumps(["fake"]),
            "internal_doc_ids": json.dumps([]),
        }
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=non_admin_headers, data=data, timeout=30)
        assert r.status_code == 403, f"Se esperaba 403, obtuvo {r.status_code}: {r.text[:200]}"


# ---------- POST send communication ---------- #
class TestSendCommunication:
    @pytest.fixture(scope="class")
    def real_template(self, admin_headers):
        r = requests.get(f"{BASE_URL}/email-templates?context=INTEGRADORES",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        tpls = r.json()
        if not tpls:
            pytest.skip("No hay plantillas de INTEGRADORES en la biblioteca")
        return tpls[0]

    @pytest.fixture(scope="class")
    def real_doc(self, admin_headers):
        r = requests.get(f"{BASE_URL}/entity-documents?context=INTEGRADORES",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        docs = r.json()
        if not docs:
            pytest.skip("No hay entity-documents INTEGRADORES")
        return docs[0]

    def _get_last_mass_log(self):
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]

        async def _fetch():
            cur = db.email_logs.find(
                {"action": "integrator_mass_communication"},
                {"_id": 0}
            ).sort("created_at", -1).limit(1)
            docs = await cur.to_list(1)
            return docs[0] if docs else None

        try:
            return asyncio.get_event_loop().run_until_complete(_fetch())
        finally:
            client.close()

    def test_send_success_bcc(self, admin_headers, test_integrators, real_template):
        ids, docs = test_integrators
        # Seleccionar los 2 con email + el que no tiene
        payload = {
            "template_id": real_template["template_id"],
            "integrator_ids": json.dumps(ids),  # incluye el sin email
            "internal_doc_ids": json.dumps([]),
        }
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=admin_headers, data=payload, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("recipients_count") == 2, body
        assert body.get("attachments_count") == 0
        # Verificar email_log
        log = self._get_last_mass_log()
        assert log is not None
        assert log["action"] == "integrator_mass_communication"
        assert log["bcc_count"] == 2
        # 'to' debe contener el remitente institucional
        assert any("megasoft" in (t or "").lower() for t in log["to"]), f"to={log['to']}"
        assert log.get("status") in ("sent", "simulated")

    def test_send_reject_empty_ids(self, admin_headers, real_template):
        payload = {
            "template_id": real_template["template_id"],
            "integrator_ids": json.dumps([]),
            "internal_doc_ids": json.dumps([]),
        }
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=admin_headers, data=payload, timeout=30)
        assert r.status_code == 400, r.text

    def test_send_reject_no_valid_email(self, admin_headers, test_integrators, real_template):
        ids, _docs = test_integrators
        # Solo el que no tiene email
        payload = {
            "template_id": real_template["template_id"],
            "integrator_ids": json.dumps([ids[2]]),
            "internal_doc_ids": json.dumps([]),
        }
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=admin_headers, data=payload, timeout=30)
        assert r.status_code == 400, r.text

    def test_send_missing_internal_doc_422(self, admin_headers, test_integrators, real_template):
        ids, _docs = test_integrators
        payload = {
            "template_id": real_template["template_id"],
            "integrator_ids": json.dumps(ids[:2]),
            "internal_doc_ids": json.dumps(["edoc_NONEXISTENT_XX"]),
        }
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=admin_headers, data=payload, timeout=30)
        assert r.status_code == 422, r.text

    def test_send_mixed_attachments(self, admin_headers, test_integrators, real_template, real_doc):
        ids, _docs = test_integrators
        payload = {
            "template_id": real_template["template_id"],
            "integrator_ids": json.dumps(ids[:2]),
            "internal_doc_ids": json.dumps([real_doc["document_id"]]),
        }
        files = [("files", ("local_test.txt", io.BytesIO(b"contenido local de prueba"), "text/plain"))]
        r = requests.post(f"{BASE_URL}/integrators/mass/communication",
                          headers=admin_headers, data=payload, files=files, timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["attachments_count"] == 2, body
        log = self._get_last_mass_log()
        assert log["attachment_count"] >= 2
        names = log.get("attachment_names") or []
        assert "local_test.txt" in names
        assert real_doc["filename"] in names
