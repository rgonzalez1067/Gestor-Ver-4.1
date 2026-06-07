# ruff: noqa
"""Pytest suite for entity_communications: integradores + nuevos productos
notification flow + templates + internal users autocomplete.
"""
import os
import io
import time
import pytest
import requests

def _get_base():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Read from frontend .env
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
    return (url or "").rstrip("/")

BASE_URL = _get_base()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Avila*0426"


# ==================== Fixtures ====================
@pytest.fixture(scope="session")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    data = r.json()
    return data.get("token") or data.get("access_token") or data.get("session_token")


@pytest.fixture(scope="session")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def integrator_id(headers):
    r = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    if not items:
        pytest.skip("No integrators in DB")
    return items[0].get("integrator_id") or items[0].get("id")


@pytest.fixture(scope="session")
def product_id(headers):
    r = requests.get(f"{BASE_URL}/api/new-products", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    if not items:
        pytest.skip("No new products in DB")
    return items[0].get("product_id") or items[0].get("id")


# ==================== /users/internal-emails ====================
class TestInternalEmails:
    def test_unauthorized(self):
        r = requests.get(f"{BASE_URL}/api/users/internal-emails", timeout=20)
        assert r.status_code in (401, 403)

    def test_list_internal_emails(self, headers):
        r = requests.get(f"{BASE_URL}/api/users/internal-emails", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        sample = data[0]
        for k in ("user_id", "email", "full_name", "role", "cargo", "label"):
            assert k in sample, f"missing {k}"
        for u in data:
            assert "@" in u["email"]


# ==================== entity-documents ====================
class TestEntityDocuments:
    uploaded_id = None

    def test_invalid_context(self, headers):
        r = requests.get(f"{BASE_URL}/api/entity-documents?context=FOO", headers=headers, timeout=20)
        assert r.status_code == 400

    def test_list_integradores(self, headers):
        r = requests.get(f"{BASE_URL}/api/entity-documents?context=INTEGRADORES", headers=headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upload_and_delete(self, headers):
        files = {"file": ("test_doc.txt", io.BytesIO(b"hello world TEST_"), "text/plain")}
        data = {
            "context": "INTEGRADORES",
            "name": "TEST_doc_pytest",
            "description": "test doc",
            "category": "General",
        }
        r = requests.post(
            f"{BASE_URL}/api/entity-documents/upload",
            headers=headers, data=data, files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["context"] == "INTEGRADORES"
        assert doc["name"] == "TEST_doc_pytest"
        assert "document_id" in doc
        TestEntityDocuments.uploaded_id = doc["document_id"]

        # GET should include it
        r2 = requests.get(
            f"{BASE_URL}/api/entity-documents?context=INTEGRADORES",
            headers=headers, timeout=20,
        )
        ids = [d["document_id"] for d in r2.json()]
        assert TestEntityDocuments.uploaded_id in ids

        # DELETE (admin)
        r3 = requests.delete(
            f"{BASE_URL}/api/entity-documents/{TestEntityDocuments.uploaded_id}",
            headers=headers, timeout=20,
        )
        assert r3.status_code == 200


# ==================== Email Templates context filter ====================
class TestEmailTemplatesContext:
    created_ids = []

    @pytest.mark.parametrize("ctx", ["INTEGRADORES", "NUEVOS_PRODUCTOS"])
    def test_create_get_delete(self, headers, ctx):
        tpl_id = f"TEST_tpl_{ctx.lower()}_{int(time.time())}"
        payload = {
            "template_id": tpl_id,
            "name": f"TEST plantilla {ctx}",
            "subject": "Saludo {nombre_integrador}",
            "body_html": "<p>Hola {contacto}</p>",
            "context": ctx,
        }
        r = requests.post(f"{BASE_URL}/api/email-templates", headers=headers, json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        TestEmailTemplatesContext.created_ids.append(tpl_id)

        # Filter by context
        r2 = requests.get(f"{BASE_URL}/api/email-templates?context={ctx}", headers=headers, timeout=20)
        assert r2.status_code == 200
        ids = [t["template_id"] for t in r2.json()]
        assert tpl_id in ids

        # Update (PUT requires full schema)
        full_update = {**payload, "subject": "Asunto editado"}
        r3 = requests.put(
            f"{BASE_URL}/api/email-templates/{tpl_id}", headers=headers,
            json=full_update, timeout=20,
        )
        assert r3.status_code == 200, r3.text

        # Delete
        r4 = requests.delete(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=headers, timeout=20)
        assert r4.status_code == 200


# ==================== Integrator preview / send-email ====================
class TestIntegratorEmail:
    def test_preview(self, headers, integrator_id):
        body = {
            "subject": "Hola {nombre_integrador}",
            "message": "Su RIF: {rif}, fase: {fase}",
        }
        r = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/preview-email",
            headers=headers, json=body, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "subject" in data and "message" in data
        # Variables should be replaced (no leftover braces of those keys)
        assert "{nombre_integrador}" not in data["subject"]
        assert "{rif}" not in data["message"]

    def test_send_email_creates_bitacora(self, headers, integrator_id):
        # Count bitacora before
        r0 = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=headers, timeout=20,
        )
        before = []
        if r0.status_code == 200:
            before = r0.json() if isinstance(r0.json(), list) else r0.json().get("items", [])
        else:
            pytest.skip(f"Bitacora endpoint returned {r0.status_code}")

        subject = f"TEST_pytest {int(time.time())}"
        data = {
            "recipients": '["test_recipient@example.com"]',
            "subject": subject,
            "message": "Mensaje de prueba para {nombre_integrador}",
            "internal_doc_ids": "[]",
        }
        r = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/send-email",
            headers=headers, data=data, timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "sent"

        # Re-fetch bitacora
        r2 = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=headers, timeout=20,
        )
        after = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        assert len(after) > len(before), "Bitacora should have a new entry"

        # Find the new entry
        new_entries = [e for e in after if subject in (e.get("description") or "")]
        assert new_entries, "Notification entry not found"
        entry = new_entries[0]
        assert entry.get("entry_type") == "notification"
        assert "email_data" in entry
        assert entry["email_data"]["subject"] == subject
        assert "test_recipient@example.com" in entry["email_data"]["recipients"]
        # created_at must include time (ISO)
        assert "T" in entry.get("created_at", "")

    def test_send_email_validates_recipients(self, headers, integrator_id):
        data = {
            "recipients": '[]',
            "subject": "x",
            "message": "y",
            "internal_doc_ids": "[]",
        }
        r = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/send-email",
            headers=headers, data=data, timeout=20,
        )
        assert r.status_code == 400


# ==================== New Product preview / send-email ====================
class TestNewProductEmail:
    def test_preview(self, headers, product_id):
        body = {
            "subject": "Producto: {producto}",
            "message": "Estado: {estado}, banco: {banco}",
        }
        r = requests.post(
            f"{BASE_URL}/api/new-products/{product_id}/preview-email",
            headers=headers, json=body, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "{producto}" not in data["subject"]
        assert "{estado}" not in data["message"]

    def test_send_email_creates_evolution_entry(self, headers, product_id):
        # Get evolution before
        r0 = requests.get(
            f"{BASE_URL}/api/new-products/{product_id}/evolution",
            headers=headers, timeout=20,
        )
        before = []
        if r0.status_code == 200:
            before = r0.json() if isinstance(r0.json(), list) else r0.json().get("items", [])
        else:
            pytest.skip(f"Evolution endpoint returned {r0.status_code}")

        subject = f"TEST_np_pytest {int(time.time())}"
        data = {
            "recipients": '["test_np@example.com"]',
            "subject": subject,
            "message": "Hola producto {producto}",
            "internal_doc_ids": "[]",
        }
        r = requests.post(
            f"{BASE_URL}/api/new-products/{product_id}/send-email",
            headers=headers, data=data, timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "sent"

        r2 = requests.get(
            f"{BASE_URL}/api/new-products/{product_id}/evolution",
            headers=headers, timeout=20,
        )
        after = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
        assert len(after) > len(before)

        new_entries = [e for e in after if subject in (e.get("comment") or e.get("description") or "")]
        assert new_entries, "Notification evolution entry not found"
        entry = new_entries[0]
        assert entry.get("entry_type") == "notification"
        assert "email_data" in entry
        assert entry["email_data"]["subject"] == subject
        assert "test_np@example.com" in entry["email_data"]["recipients"]
        assert "T" in entry["email_data"].get("sent_at", "")
