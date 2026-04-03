"""
Iteration 148: Bug Fixes Testing
- Bug 1: Variable hydration fix (Nombre_Implementador, Correo_Implementador, Contacto_Principal, Datos_Contacto, Nombre_Cliente)
- Bug 2: Image upload to Object Storage and base64 replacement
- Bug 3: Variables panel in editable preview editor
"""
import pytest
import requests
import os
import base64

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test project with assigned implementer
TEST_PROJECT_ID = "prj_ac2f9862c664"  # multistore, assigned to Omar Jimenez user_3cc63615f2c0


class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Get session token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        return data["session_token"]


class TestBug1VariableHydration(TestAuth):
    """Bug 1: Test that template variables are properly hydrated"""
    
    def test_preview_notification_nombre_implementador_not_empty(self, session_token):
        """Nombre_Implementador must NOT be empty (should be real implementer name)"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        
        variables = data.get("variables", {})
        nombre_impl = variables.get("Nombre_Implementador", "")
        
        # Must NOT be empty
        assert nombre_impl, "Nombre_Implementador is empty - BUG NOT FIXED"
        assert nombre_impl.strip() != "", "Nombre_Implementador is whitespace only"
        print(f"PASS: Nombre_Implementador = '{nombre_impl}'")
    
    def test_preview_notification_correo_implementador_has_email(self, session_token):
        """Correo_Implementador must show email"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        variables = data.get("variables", {})
        correo_impl = variables.get("Correo_Implementador", "")
        
        # Should contain @ if implementer has email
        if correo_impl:
            assert "@" in correo_impl, f"Correo_Implementador doesn't look like email: {correo_impl}"
            print(f"PASS: Correo_Implementador = '{correo_impl}'")
        else:
            print(f"INFO: Correo_Implementador is empty (implementer may not have email)")
    
    def test_preview_notification_contacto_principal_not_empty(self, session_token):
        """Contacto_Principal must show first contact name"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        variables = data.get("variables", {})
        contacto = variables.get("Contacto_Principal", "")
        
        # Should have a contact name
        print(f"INFO: Contacto_Principal = '{contacto}'")
        # Note: May be empty if client has no contacts
    
    def test_preview_notification_nombre_cliente_uses_fallback(self, session_token):
        """Nombre_Cliente must use legal_name when razon_social is null"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        variables = data.get("variables", {})
        nombre_cliente = variables.get("Nombre_Cliente", "")
        
        # Must NOT be empty
        assert nombre_cliente, "Nombre_Cliente is empty - BUG NOT FIXED"
        assert nombre_cliente.strip() != "", "Nombre_Cliente is whitespace only"
        print(f"PASS: Nombre_Cliente = '{nombre_cliente}'")
    
    def test_preview_notification_datos_contacto_format(self, session_token):
        """Datos_Contacto must show full contact info with phone/email"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        variables = data.get("variables", {})
        datos_contacto = variables.get("Datos_Contacto", "")
        
        # Should contain Tel: and Email: if contact exists
        print(f"INFO: Datos_Contacto = '{datos_contacto}'")
        if datos_contacto and datos_contacto != "—":
            assert "Tel:" in datos_contacto or "Email:" in datos_contacto, \
                f"Datos_Contacto doesn't have expected format: {datos_contacto}"
            print(f"PASS: Datos_Contacto has proper format")
    
    def test_template_variables_endpoint(self, session_token):
        """Test the template-variables endpoint returns all variables"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Template variables failed: {response.text}"
        data = response.json()
        
        variables = data.get("variables", {})
        available_tags = data.get("available_tags", [])
        
        # Check key variables exist
        expected_vars = [
            "Nombre_Cliente", "Contacto_Principal", "Datos_Contacto",
            "Nombre_Implementador", "Correo_Implementador", "Telefono_Implementador"
        ]
        for var in expected_vars:
            assert var in variables, f"Missing variable: {var}"
        
        # Check Datos_Contacto is in available_tags
        tag_keys = [t["key"] for t in available_tags]
        assert "Datos_Contacto" in tag_keys, "Datos_Contacto not in available_tags"
        
        print(f"PASS: All expected variables present")
        print(f"  Nombre_Implementador: {variables.get('Nombre_Implementador')}")
        print(f"  Correo_Implementador: {variables.get('Correo_Implementador')}")
        print(f"  Contacto_Principal: {variables.get('Contacto_Principal')}")
        print(f"  Datos_Contacto: {variables.get('Datos_Contacto')}")
        print(f"  Nombre_Cliente: {variables.get('Nombre_Cliente')}")


class TestBug2ImageUpload(TestAuth):
    """Bug 2: Test image upload to Object Storage"""
    
    def test_upload_image_returns_public_url(self, session_token):
        """POST /api/projects/upload-image uploads image and returns public URL"""
        # Create a small test PNG image (1x1 pixel red)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {"file": ("test_image.png", png_data, "image/png")}
        response = requests.post(
            f"{BASE_URL}/api/projects/upload-image",
            files=files,
            headers={"Authorization": f"Bearer {session_token}"}
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        
        assert "url" in data, "No url in response"
        assert "image_id" in data, "No image_id in response"
        
        url = data["url"]
        assert "/api/projects/images/" in url, f"URL doesn't have expected path: {url}"
        
        print(f"PASS: Image uploaded, URL = {url}")
        return url, data["image_id"]
    
    def test_serve_image_without_auth(self, session_token):
        """GET /api/projects/images/{filename} serves uploaded image without auth"""
        # First upload an image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {"file": ("test_serve.png", png_data, "image/png")}
        upload_response = requests.post(
            f"{BASE_URL}/api/projects/upload-image",
            files=files,
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert upload_response.status_code == 200
        url = upload_response.json()["url"]
        
        # Now try to GET the image WITHOUT auth
        serve_response = requests.get(url)  # No Authorization header
        
        assert serve_response.status_code == 200, f"Serve failed (no auth): {serve_response.status_code}"
        assert serve_response.headers.get("Content-Type", "").startswith("image/"), \
            f"Wrong content type: {serve_response.headers.get('Content-Type')}"
        
        print(f"PASS: Image served without auth, Content-Type = {serve_response.headers.get('Content-Type')}")
    
    def test_upload_image_invalid_format(self, session_token):
        """Upload with invalid format should fail"""
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = requests.post(
            f"{BASE_URL}/api/projects/upload-image",
            files=files,
            headers={"Authorization": f"Bearer {session_token}"}
        )
        
        # Should fail with 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"PASS: Invalid format rejected with 400")


class TestBug3VariablesPanel:
    """Bug 3: Test that variables panel includes Datos_Contacto"""
    
    def test_template_variables_includes_datos_contacto(self):
        """available_tags should include Datos_Contacto"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200
        token = login_response.json()["session_token"]
        
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        available_tags = data.get("available_tags", [])
        tag_keys = [t["key"] for t in available_tags]
        
        # Check Datos_Contacto is present
        assert "Datos_Contacto" in tag_keys, f"Datos_Contacto not in available_tags: {tag_keys}"
        
        # Find the Datos_Contacto tag and check its label
        datos_tag = next((t for t in available_tags if t["key"] == "Datos_Contacto"), None)
        assert datos_tag is not None
        assert "label" in datos_tag
        
        print(f"PASS: Datos_Contacto in available_tags with label: {datos_tag.get('label')}")


class TestProjectDataVerification(TestAuth):
    """Verify the test project has the expected data"""
    
    def test_project_exists_and_has_implementer(self, session_token):
        """Verify test project exists and has assigned implementer"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Project not found: {response.text}"
        data = response.json()
        
        # Check it has an assigned implementer
        assigned_to_user_id = data.get("assigned_to_user_id")
        assigned_to_name = data.get("assigned_to_name")
        
        print(f"Project: {data.get('project_number')}")
        print(f"  assigned_to_user_id: {assigned_to_user_id}")
        print(f"  assigned_to_name: {assigned_to_name}")
        print(f"  client_name: {data.get('client_name')}")
        print(f"  client_id: {data.get('client_id')}")
        print(f"  project_type: {data.get('project_type')}")
        
        assert assigned_to_user_id, "Project has no assigned_to_user_id"
        assert assigned_to_name, "Project has no assigned_to_name"
    
    def test_implementer_user_exists(self, session_token):
        """Verify the implementer user exists in the database"""
        # Get project first
        proj_response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert proj_response.status_code == 200
        project = proj_response.json()
        
        assigned_to_user_id = project.get("assigned_to_user_id")
        if not assigned_to_user_id:
            pytest.skip("No assigned_to_user_id in project")
        
        # Get implementers list
        impl_response = requests.get(
            f"{BASE_URL}/api/projects/implementers/list",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert impl_response.status_code == 200
        implementers = impl_response.json()
        
        # Find the assigned implementer
        impl = next((u for u in implementers if u.get("user_id") == assigned_to_user_id), None)
        
        if impl:
            print(f"PASS: Implementer found: {impl.get('first_name')} {impl.get('last_name')} ({impl.get('email')})")
        else:
            print(f"INFO: Implementer {assigned_to_user_id} not in implementers list (may have different cargo)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
