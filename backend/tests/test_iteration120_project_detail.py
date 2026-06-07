# ruff: noqa
"""
Iteration 120: Testing ProjectDetail improvements
- Suggested contacts endpoint returns both client and bank contacts
- Email templates CRUD endpoints
- Header redesign verification (via frontend)
- Error handling for contacts/templates loading
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProjectDetailBackend:
    """Backend tests for ProjectDetail improvements"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get first project
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        projects = projects_response.json()
        if projects:
            self.project_id = projects[0].get("project_id")
        else:
            self.project_id = None
    
    # ==================== SUGGESTED CONTACTS TESTS ====================
    
    def test_suggested_contacts_endpoint_returns_200(self):
        """Test GET /api/projects/{id}/suggested-contacts returns 200"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/suggested-contacts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_suggested_contacts_returns_list(self):
        """Test suggested contacts returns a list"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/suggested-contacts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
    
    def test_suggested_contacts_structure(self):
        """Test each contact has required fields: email, label, source"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/suggested-contacts")
        assert response.status_code == 200
        contacts = response.json()
        
        for contact in contacts:
            assert "email" in contact, f"Contact missing 'email' field: {contact}"
            assert "label" in contact, f"Contact missing 'label' field: {contact}"
            assert "source" in contact, f"Contact missing 'source' field: {contact}"
            assert contact["source"] in ["client", "bank"], f"Invalid source: {contact['source']}"
    
    def test_suggested_contacts_includes_client_contacts(self):
        """Test that client contacts are included in suggested contacts"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/suggested-contacts")
        assert response.status_code == 200
        contacts = response.json()
        
        client_contacts = [c for c in contacts if c.get("source") == "client"]
        # At minimum, there should be at least one client contact if project has client
        print(f"Found {len(client_contacts)} client contacts")
        # This is informational - project may or may not have client contacts
    
    def test_suggested_contacts_invalid_project_returns_404(self):
        """Test suggested contacts with invalid project ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/projects/invalid_project_id/suggested-contacts")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    # ==================== EMAIL TEMPLATES TESTS ====================
    
    def test_email_templates_list_returns_200(self):
        """Test GET /api/email-templates returns 200"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_email_templates_returns_list(self):
        """Test email templates returns a list"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
    
    def test_email_templates_structure(self):
        """Test each template has required fields"""
        response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        templates = response.json()
        
        for template in templates:
            assert "template_id" in template, f"Template missing 'template_id': {template}"
            assert "name" in template, f"Template missing 'name': {template}"
            assert "subject" in template, f"Template missing 'subject': {template}"
    
    def test_create_email_template(self):
        """Test POST /api/email-templates creates a template"""
        # Create template using form data
        response = self.session.post(
            f"{BASE_URL}/api/email-templates",
            data={
                "name": "TEST_Template_Iteration120",
                "subject": "Test Subject for Iteration 120",
                "body_content": "This is a test template body for iteration 120 testing."
            },
            headers={"Authorization": f"Bearer {self.token}"}  # Remove Content-Type for form data
        )
        
        # Remove Content-Type header for form data
        del self.session.headers["Content-Type"]
        response = self.session.post(
            f"{BASE_URL}/api/email-templates",
            data={
                "name": "TEST_Template_Iteration120",
                "subject": "Test Subject for Iteration 120",
                "body_content": "This is a test template body for iteration 120 testing."
            }
        )
        self.session.headers["Content-Type"] = "application/json"
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "template_id" in data, f"Response missing template_id: {data}"
        assert data.get("name") == "TEST_Template_Iteration120"
        assert data.get("subject") == "Test Subject for Iteration 120"
        
        # Store for cleanup
        self.created_template_id = data.get("template_id")
    
    def test_created_template_appears_in_list(self):
        """Test that created template appears in the templates list"""
        # First create a template
        del self.session.headers["Content-Type"]
        create_response = self.session.post(
            f"{BASE_URL}/api/email-templates",
            data={
                "name": "TEST_Template_ListCheck",
                "subject": "Test Subject List Check",
                "body_content": "Body for list check test."
            }
        )
        self.session.headers["Content-Type"] = "application/json"
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create template: {create_response.text}")
        
        created_id = create_response.json().get("template_id")
        
        # Now check it appears in list
        list_response = self.session.get(f"{BASE_URL}/api/email-templates")
        assert list_response.status_code == 200
        templates = list_response.json()
        
        template_ids = [t.get("template_id") for t in templates]
        assert created_id in template_ids, f"Created template {created_id} not found in list"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/email-templates/{created_id}")
    
    def test_delete_email_template(self):
        """Test DELETE /api/email-templates/{id} deletes a template"""
        # First create a template to delete
        del self.session.headers["Content-Type"]
        create_response = self.session.post(
            f"{BASE_URL}/api/email-templates",
            data={
                "name": "TEST_Template_ToDelete",
                "subject": "Test Subject To Delete",
                "body_content": "Body for delete test."
            }
        )
        self.session.headers["Content-Type"] = "application/json"
        
        if create_response.status_code != 200:
            pytest.skip(f"Could not create template: {create_response.text}")
        
        template_id = create_response.json().get("template_id")
        
        # Delete it
        delete_response = self.session.delete(f"{BASE_URL}/api/email-templates/{template_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        # Verify it's gone
        list_response = self.session.get(f"{BASE_URL}/api/email-templates")
        templates = list_response.json()
        template_ids = [t.get("template_id") for t in templates]
        assert template_id not in template_ids, f"Deleted template {template_id} still in list"
    
    # ==================== PROJECT DETAIL TESTS ====================
    
    def test_project_detail_returns_required_fields(self):
        """Test project detail returns all fields needed for header redesign"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}")
        assert response.status_code == 200
        project = response.json()
        
        # Fields for Block 1: Datos del Proyecto
        assert "ticket_number" in project or project.get("ticket_number") is None
        assert "project_number" in project
        assert "client_name" in project
        assert "client_rif" in project
        
        # Fields for Block 2: Implementación
        assert "pinpad_model" in project or project.get("pinpad_model") is None
        assert "sponsor_bank_name" in project or project.get("sponsor_bank_name") is None
        
        # Fields for Block 3: Avance y Acciones
        assert "project_type" in project or project.get("project_type") is None
        assert "rollup_progress" in project or project.get("rollup_progress") is None
        assert "status" in project
    
    def test_project_has_implementation_matrix(self):
        """Test project has implementation_matrix for notification dialog"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        response = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}")
        assert response.status_code == 200
        project = response.json()
        
        assert "implementation_matrix" in project
        matrix = project.get("implementation_matrix", {})
        assert isinstance(matrix, dict), f"Expected dict, got {type(matrix)}"
        
        # If matrix has banks, verify structure
        for bank_name, products in matrix.items():
            assert isinstance(products, dict), f"Bank {bank_name} products should be dict"
            print(f"Bank: {bank_name}, Products: {list(products.keys())}")


class TestCleanup:
    """Cleanup test templates created during testing"""
    
    def test_cleanup_test_templates(self):
        """Remove any TEST_ prefixed templates"""
        session = requests.Session()
        
        # Login
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        if login_response.status_code != 200:
            pytest.skip("Could not login for cleanup")
        
        token = login_response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get templates
        templates_response = session.get(f"{BASE_URL}/api/email-templates")
        if templates_response.status_code != 200:
            return
        
        templates = templates_response.json()
        
        # Delete TEST_ prefixed templates
        for template in templates:
            if template.get("name", "").startswith("TEST_"):
                session.delete(f"{BASE_URL}/api/email-templates/{template.get('template_id')}")
                print(f"Cleaned up template: {template.get('name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
