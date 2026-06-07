# ruff: noqa
"""
Test Iteration 165: Client Email Templates Bug Fix
Tests for the bug fix where frontend was sending 'body' instead of 'body_html' 
and missing 'template_id' when creating email templates for CLIENTES context.

Bug Fix Summary:
- Frontend now sends template_id (auto-generated as cli_tpl_xxxxx) 
- Frontend now sends body_html instead of body
- ClientEmailDialog reads tpl.body_html when selecting a template
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClientEmailTemplates:
    """Tests for Client Email Templates CRUD with context=CLIENTES"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("session_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        yield
        
        # Cleanup: Delete test templates
        try:
            templates = self.session.get(f"{BASE_URL}/api/email-templates?context=CLIENTES").json()
            for tpl in templates:
                if tpl.get("template_id", "").startswith("TEST_cli_tpl_"):
                    self.session.delete(f"{BASE_URL}/api/email-templates/{tpl['template_id']}")
        except:
            pass

    def test_01_login_success(self):
        """Test login returns session_token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert response.status_code == 200
        data = response.json()
        # Backend returns session_token, not token
        assert "session_token" in data or "token" in data
        print("✓ Login successful, session_token received")

    def test_02_list_client_templates(self):
        """Test GET /api/email-templates?context=CLIENTES returns templates"""
        response = self.session.get(f"{BASE_URL}/api/email-templates?context=CLIENTES")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} templates with context=CLIENTES")

    def test_03_create_client_template_with_correct_fields(self):
        """Test POST /api/email-templates with template_id and body_html (BUG FIX)"""
        # This is the corrected payload that frontend now sends
        template_id = f"TEST_cli_tpl_{int(time.time())}"
        payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Bienvenida Cliente",
            "subject": "Bienvenido {{nombre}}",
            "body_html": "<p>Estimado {{contacto}},</p><p>Es un placer darle la bienvenida.</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/email-templates", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("template_id") == template_id
        print(f"✓ Created template with template_id={template_id} and body_html")
        
        # Verify template was created
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert get_response.status_code == 200
        template = get_response.json()
        assert template["body_html"] == payload["body_html"]
        assert template["context"] == "CLIENTES"
        print("✓ Verified template persisted with correct body_html")

    def test_04_create_template_without_template_id_fails(self):
        """Test POST /api/email-templates without template_id fails (validation)"""
        # This was the old buggy payload - missing template_id
        payload = {
            "name": "TEST Plantilla Sin ID",
            "subject": "Test Subject",
            "body_html": "<p>Test body</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/email-templates", json=payload)
        # Should fail with 422 validation error
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Correctly rejected template without template_id (422)")

    def test_05_create_template_with_body_instead_of_body_html_fails(self):
        """Test POST /api/email-templates with 'body' instead of 'body_html' fails"""
        # This was the old buggy payload - using 'body' instead of 'body_html'
        template_id = f"TEST_cli_tpl_body_{int(time.time())}"
        payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Con Body Incorrecto",
            "subject": "Test Subject",
            "body": "<p>This uses wrong field name</p>",  # Wrong field!
            "context": "CLIENTES",
            "is_active": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/email-templates", json=payload)
        # Should fail with 422 validation error because body_html is required
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Correctly rejected template with 'body' instead of 'body_html' (422)")

    def test_06_update_client_template(self):
        """Test PUT /api/email-templates/{template_id} updates template"""
        # First create a template
        template_id = f"TEST_cli_tpl_update_{int(time.time())}"
        create_payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Para Actualizar",
            "subject": "Asunto Original",
            "body_html": "<p>Contenido original</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/email-templates", json=create_payload)
        assert create_response.status_code == 200
        
        # Update the template
        update_payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Actualizada",
            "subject": "Asunto Actualizado {{nombre}}",
            "body_html": "<p>Contenido actualizado para {{contacto}}</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        update_response = self.session.put(f"{BASE_URL}/api/email-templates/{template_id}", json=update_payload)
        assert update_response.status_code == 200
        print(f"✓ Updated template {template_id}")
        
        # Verify update persisted
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert get_response.status_code == 200
        template = get_response.json()
        assert template["name"] == "TEST Plantilla Actualizada"
        assert template["subject"] == "Asunto Actualizado {{nombre}}"
        assert "Contenido actualizado" in template["body_html"]
        print("✓ Verified template update persisted correctly")

    def test_07_delete_client_template(self):
        """Test DELETE /api/email-templates/{template_id} removes template"""
        # First create a template
        template_id = f"TEST_cli_tpl_delete_{int(time.time())}"
        create_payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Para Eliminar",
            "subject": "Test",
            "body_html": "<p>Test</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/email-templates", json=create_payload)
        assert create_response.status_code == 200
        
        # Delete the template
        delete_response = self.session.delete(f"{BASE_URL}/api/email-templates/{template_id}")
        assert delete_response.status_code == 200
        print(f"✓ Deleted template {template_id}")
        
        # Verify deletion
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert get_response.status_code == 404
        print("✓ Verified template no longer exists (404)")

    def test_08_get_single_template_returns_body_html(self):
        """Test GET /api/email-templates/{template_id} returns body_html field"""
        # Create a template
        template_id = f"TEST_cli_tpl_get_{int(time.time())}"
        body_html_content = "<p>Estimado {{contacto}},</p><p>Gracias por su preferencia.</p>"
        create_payload = {
            "template_id": template_id,
            "name": "TEST Plantilla Para Obtener",
            "subject": "Gracias {{nombre}}",
            "body_html": body_html_content,
            "context": "CLIENTES",
            "is_active": True
        }
        
        self.session.post(f"{BASE_URL}/api/email-templates", json=create_payload)
        
        # Get the template
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert get_response.status_code == 200
        template = get_response.json()
        
        # Verify body_html is returned (this is what ClientEmailDialog reads)
        assert "body_html" in template, "Template should have body_html field"
        assert template["body_html"] == body_html_content
        print("✓ GET template returns body_html field correctly")


class TestClientDocuments:
    """Tests for Client Communication Documents"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("session_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        yield
        
        # Cleanup: Delete test documents
        try:
            docs = self.session.get(f"{BASE_URL}/api/client-documents").json()
            for doc in docs:
                if doc.get("name", "").startswith("TEST_"):
                    self.session.delete(f"{BASE_URL}/api/client-documents/{doc['document_id']}")
        except:
            pass

    def test_01_list_client_documents(self):
        """Test GET /api/client-documents returns list"""
        response = self.session.get(f"{BASE_URL}/api/client-documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} client documents")

    def test_02_upload_client_document(self):
        """Test POST /api/client-documents/upload uploads file"""
        # Create a test file
        files = {
            'file': ('TEST_flyer.pdf', b'%PDF-1.4 test content', 'application/pdf')
        }
        data = {
            'name': 'TEST_Flyer Promocional',
            'description': 'Documento de prueba',
            'category': 'Marketing'
        }
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/client-documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        doc = response.json()
        assert "document_id" in doc
        assert doc["name"] == "TEST_Flyer Promocional"
        print(f"✓ Uploaded document with id={doc['document_id']}")
        
        # Store for cleanup
        self.test_doc_id = doc["document_id"]

    def test_03_delete_client_document(self):
        """Test DELETE /api/client-documents/{document_id} removes document"""
        # First upload a document
        files = {
            'file': ('TEST_delete.pdf', b'%PDF-1.4 delete test', 'application/pdf')
        }
        data = {
            'name': 'TEST_Documento Para Eliminar',
            'description': 'Se eliminará',
            'category': 'General'
        }
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/client-documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        assert upload_response.status_code == 200
        doc_id = upload_response.json()["document_id"]
        
        # Delete the document
        delete_response = self.session.delete(f"{BASE_URL}/api/client-documents/{doc_id}")
        assert delete_response.status_code == 200
        print(f"✓ Deleted document {doc_id}")
        
        # Verify it's gone from list
        list_response = self.session.get(f"{BASE_URL}/api/client-documents")
        docs = list_response.json()
        doc_ids = [d["document_id"] for d in docs]
        assert doc_id not in doc_ids
        print("✓ Verified document no longer in list")


class TestClientEmailSend:
    """Tests for sending emails to clients"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("session_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        yield

    def test_01_get_clients_list(self):
        """Test GET /api/clients returns clients for email testing"""
        response = self.session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} clients")
        
        if len(data) > 0:
            self.test_client = data[0]
            print(f"✓ Will use client: {self.test_client.get('legal_name', 'N/A')}")

    def test_02_preview_client_email(self):
        """Test POST /api/clients/{client_id}/preview-email renders variables"""
        # Get a client first
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        clients = clients_response.json()
        
        if not clients:
            pytest.skip("No clients available for testing")
        
        client = clients[0]
        client_id = client.get("client_id")
        
        # Preview email
        preview_payload = {
            "subject": "Hola {{nombre}}",
            "message": "Estimado {{contacto}}, su RIF es {{rif}}."
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/clients/{client_id}/preview-email",
            json=preview_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "subject" in data
        assert "message" in data
        # Variables should be replaced
        assert "{{nombre}}" not in data["subject"] or client.get("legal_name") is None
        print(f"✓ Preview email rendered: subject='{data['subject'][:50]}...'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
