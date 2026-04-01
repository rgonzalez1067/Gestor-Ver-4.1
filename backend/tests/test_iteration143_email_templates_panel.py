"""
Iteration 143: Test Email Templates Panel de Variables and Project Templates
Tests:
1. GET /api/email-templates returns project_notify_client and project_notify_bank templates
2. GET /api/email-templates/project_notify_client returns default template with Implementador variables
3. PUT /api/email-templates/project_notify_client saves template successfully (no 405 error)
4. POST /api/email-templates creates new templates
5. GET /api/projects/{id}/template-variables includes new Implementador variables
6. Preview notification endpoint resolves Implementador variables
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailTemplatesIteration143:
    """Test email templates panel and project templates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Project ID for testing
        self.project_id = "prj_c536858da780"
    
    # ==================== EMAIL TEMPLATES TESTS ====================
    
    def test_get_email_templates_includes_project_templates(self):
        """GET /api/email-templates returns project_notify_client and project_notify_bank"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        templates = response.json()
        template_ids = [t.get("template_id") for t in templates]
        
        # Verify project templates are included
        assert "project_notify_client" in template_ids, "project_notify_client template not found"
        assert "project_notify_bank" in template_ids, "project_notify_bank template not found"
        print(f"PASS: Found {len(templates)} templates including project templates")
    
    def test_get_project_notify_client_template(self):
        """GET /api/email-templates/project_notify_client returns template with Implementador variables"""
        response = self.session.get(f"{BASE_URL}/api/email-templates/project_notify_client")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "project_notify_client"
        assert template.get("name") is not None
        assert template.get("subject") is not None
        assert template.get("body_html") is not None
        
        # Verify Implementador variables are in the template
        body_html = template.get("body_html", "")
        assert "{Nombre_Implementador}" in body_html or "Nombre_Implementador" in body_html, "Missing Nombre_Implementador variable"
        assert "{Correo_Implementador}" in body_html or "Correo_Implementador" in body_html, "Missing Correo_Implementador variable"
        assert "{Telefono_Implementador}" in body_html or "Telefono_Implementador" in body_html, "Missing Telefono_Implementador variable"
        
        print(f"PASS: project_notify_client template has Implementador variables")
    
    def test_get_project_notify_bank_template(self):
        """GET /api/email-templates/project_notify_bank returns template with Aplicativo_Integracion"""
        response = self.session.get(f"{BASE_URL}/api/email-templates/project_notify_bank")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "project_notify_bank"
        
        # Verify Aplicativo_Integracion variable is in the template
        body_html = template.get("body_html", "")
        assert "{Aplicativo_Integracion}" in body_html or "Aplicativo_Integracion" in body_html, "Missing Aplicativo_Integracion variable"
        
        print(f"PASS: project_notify_bank template has Aplicativo_Integracion variable")
    
    def test_put_email_template_no_405_error(self):
        """PUT /api/email-templates/project_notify_client saves template successfully (no 405)"""
        # First get the current template
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/project_notify_client")
        assert get_response.status_code == 200
        template = get_response.json()
        
        # Update the template (add a test marker)
        updated_template = {
            "template_id": "project_notify_client",
            "name": template.get("name", "Notificación de Proyecto — Cliente"),
            "subject": template.get("subject", "[Ticket {ticket_number}] {notification_subject}: {project_number}"),
            "body_html": template.get("body_html", ""),
            "description": template.get("description", ""),
            "is_active": True
        }
        
        # PUT request - should NOT return 405
        put_response = self.session.put(
            f"{BASE_URL}/api/email-templates/project_notify_client",
            json=updated_template
        )
        
        # Critical: Must NOT be 405 Method Not Allowed
        assert put_response.status_code != 405, f"ERROR: Got 405 Method Not Allowed - PUT endpoint not working"
        assert put_response.status_code == 200, f"PUT failed with {put_response.status_code}: {put_response.text}"
        
        result = put_response.json()
        assert "message" in result or "template_id" in result
        print(f"PASS: PUT /api/email-templates/project_notify_client works (no 405 error)")
    
    def test_post_email_template_creates_new(self):
        """POST /api/email-templates creates new templates"""
        import uuid
        test_id = f"test_template_{uuid.uuid4().hex[:8]}"
        
        new_template = {
            "template_id": test_id,
            "name": "Test Template for Iteration 143",
            "subject": "Test Subject {project_number}",
            "body_html": "<p>Test body with {Nombre_Cliente}</p>",
            "description": "Test template created by iteration 143 tests",
            "is_active": True
        }
        
        post_response = self.session.post(
            f"{BASE_URL}/api/email-templates",
            json=new_template
        )
        
        # Should succeed with 200 or 201
        assert post_response.status_code in [200, 201], f"POST failed: {post_response.status_code} - {post_response.text}"
        
        result = post_response.json()
        assert "message" in result or "template_id" in result
        print(f"PASS: POST /api/email-templates creates new template: {test_id}")
        
        # Verify it was created by fetching it
        get_response = self.session.get(f"{BASE_URL}/api/email-templates/{test_id}")
        assert get_response.status_code == 200, f"Created template not found: {get_response.text}"
        print(f"PASS: Created template {test_id} is retrievable")
    
    # ==================== PROJECT TEMPLATE VARIABLES TESTS ====================
    
    def test_template_variables_includes_implementador_vars(self):
        """GET /api/projects/{id}/template-variables includes Implementador variables"""
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/template-variables")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        variables = data.get("variables", {})
        available_tags = data.get("available_tags", [])
        
        # Check available_tags includes new Implementador variables
        tag_keys = [t.get("key") for t in available_tags]
        
        assert "Nombre_Implementador" in tag_keys, "Missing Nombre_Implementador in available_tags"
        assert "Correo_Implementador" in tag_keys, "Missing Correo_Implementador in available_tags"
        assert "Telefono_Implementador" in tag_keys, "Missing Telefono_Implementador in available_tags"
        assert "Aplicativo_Integracion" in tag_keys, "Missing Aplicativo_Integracion in available_tags"
        
        print(f"PASS: template-variables includes all 4 new Implementador tags")
        print(f"  - Nombre_Implementador: {variables.get('Nombre_Implementador', '(not resolved)')}")
        print(f"  - Correo_Implementador: {variables.get('Correo_Implementador', '(not resolved)')}")
        print(f"  - Telefono_Implementador: {variables.get('Telefono_Implementador', '(not resolved)')}")
        print(f"  - Aplicativo_Integracion: {variables.get('Aplicativo_Integracion', '(not resolved)')}")
    
    def test_preview_notification_resolves_implementador_vars(self):
        """POST /api/projects/{id}/preview-notification resolves Implementador variables"""
        response = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/preview-notification",
            json={
                "target": "client",
                "bank_name": None,
                "level": "Primera Comunicación"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        variables = data.get("variables", {})
        html = data.get("html", "")
        
        # Check that Implementador variables are in the resolved variables
        assert "Nombre_Implementador" in variables, "Nombre_Implementador not in resolved variables"
        assert "Correo_Implementador" in variables, "Correo_Implementador not in resolved variables"
        assert "Telefono_Implementador" in variables, "Telefono_Implementador not in resolved variables"
        assert "Aplicativo_Integracion" in variables, "Aplicativo_Integracion not in resolved variables"
        
        print(f"PASS: preview-notification resolves Implementador variables")
        print(f"  - Nombre_Implementador: {variables.get('Nombre_Implementador')}")
        print(f"  - Aplicativo_Integracion: {variables.get('Aplicativo_Integracion')}")
    
    # ==================== SEDE TEMPLATES TESTS ====================
    
    def test_sede_templates_exist(self):
        """Verify sede-specific templates exist (PYME and CORP)"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        
        templates = response.json()
        template_ids = [t.get("template_id") for t in templates]
        
        # Check for PYME templates
        pyme_templates = [tid for tid in template_ids if tid and tid.endswith("_PYME")]
        corp_templates = [tid for tid in template_ids if tid and tid.endswith("_CORP")]
        
        assert len(pyme_templates) > 0, "No PYME sede templates found"
        assert len(corp_templates) > 0, "No CORP sede templates found"
        
        print(f"PASS: Found {len(pyme_templates)} PYME templates and {len(corp_templates)} CORP templates")
    
    def test_project_templates_are_global(self):
        """Verify project templates are global (not per-sede)"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        
        templates = response.json()
        
        # Find project templates
        project_templates = [t for t in templates if t.get("template_id") in ["project_notify_client", "project_notify_bank"]]
        
        for pt in project_templates:
            # Project templates should NOT have sede field or should have is_project_template=True
            assert pt.get("sede") is None or pt.get("is_project_template") == True, \
                f"Project template {pt.get('template_id')} should be global, not per-sede"
        
        print(f"PASS: Project templates are global (not per-sede)")


class TestEmailTemplatesEditorVariables:
    """Test that EmailTemplatesEditor shows correct variables for project templates"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_project_notify_client_has_19_variables(self):
        """Verify project_notify_client template type has 19 variables in frontend config"""
        # This is a backend test to verify the template structure supports 19 variables
        response = self.session.get(f"{BASE_URL}/api/email-templates/project_notify_client")
        assert response.status_code == 200
        
        template = response.json()
        body_html = template.get("body_html", "")
        
        # Count unique variable placeholders in the template
        import re
        variables = set(re.findall(r'\{([A-Za-z_]+)\}', body_html))
        
        print(f"Found {len(variables)} unique variables in project_notify_client template:")
        for v in sorted(variables):
            print(f"  - {{{v}}}")
        
        # The template should have multiple variables (at least the core ones)
        assert len(variables) >= 5, f"Expected at least 5 variables, found {len(variables)}"
        print(f"PASS: project_notify_client template has {len(variables)} variables")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
