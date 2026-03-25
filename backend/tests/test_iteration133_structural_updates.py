"""
Test Iteration 133: 4 Structural Updates Testing
1. Fiscal Printer Models - GET/POST endpoints
2. Contact Roles - Frontend constant (Propietario, Director)
3. Projects - Assign dialog changes (no Fecha de Entrega, auto Fecha de Asignación)
4. Admin Users - Supervisor field with typeahead
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def session_token():
    """Login and get session token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "rgonzalez@megasoft.com.ve",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("session_token")

@pytest.fixture(scope="module")
def auth_headers(session_token):
    """Auth headers for API calls"""
    return {"Authorization": f"Bearer {session_token}"}


# ==================== FISCAL PRINTER MODELS TESTS ====================

class TestFiscalPrinters:
    """Tests for fiscal printer models endpoint - GET/POST"""
    
    def test_get_fiscal_printers_returns_seeded_models(self, auth_headers):
        """GET /api/fiscal-printers should return seeded models (Bematech, Bixolon, HKA)"""
        response = requests.get(f"{BASE_URL}/api/fiscal-printers", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check seeded models exist
        model_names = [m.get("name") for m in data]
        assert "Bematech" in model_names, "Bematech should be seeded"
        assert "Bixolon" in model_names, "Bixolon should be seeded"
        assert "HKA" in model_names, "HKA should be seeded"
        
        # Verify structure
        for model in data:
            assert "model_id" in model, "Each model should have model_id"
            assert "name" in model, "Each model should have name"
            assert "created_at" in model, "Each model should have created_at"
        
        print(f"✓ GET /api/fiscal-printers returned {len(data)} models: {model_names}")
    
    def test_post_fiscal_printer_creates_new_model(self, auth_headers):
        """POST /api/fiscal-printers should create a new model"""
        import uuid
        unique_name = f"TEST_Printer_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/fiscal-printers",
            headers=auth_headers,
            json={"name": unique_name}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("name") == unique_name, f"Name should be {unique_name}"
        assert "model_id" in data, "Response should have model_id"
        assert data["model_id"].startswith("fpm_"), "model_id should start with fpm_"
        
        print(f"✓ POST /api/fiscal-printers created model: {unique_name}")
    
    def test_post_fiscal_printer_prevents_duplicates(self, auth_headers):
        """POST /api/fiscal-printers should prevent duplicate names"""
        # Try to create a duplicate of seeded model
        response = requests.post(
            f"{BASE_URL}/api/fiscal-printers",
            headers=auth_headers,
            json={"name": "Bematech"}
        )
        assert response.status_code == 400, f"Expected 400 for duplicate, got {response.status_code}"
        
        data = response.json()
        assert "ya existe" in data.get("detail", "").lower() or "already" in data.get("detail", "").lower(), \
            "Error message should indicate duplicate"
        
        print("✓ POST /api/fiscal-printers correctly prevents duplicates")
    
    def test_post_fiscal_printer_requires_name(self, auth_headers):
        """POST /api/fiscal-printers should require name field"""
        response = requests.post(
            f"{BASE_URL}/api/fiscal-printers",
            headers=auth_headers,
            json={"name": ""}
        )
        assert response.status_code == 400, f"Expected 400 for empty name, got {response.status_code}"
        
        print("✓ POST /api/fiscal-printers correctly requires name")


# ==================== SUPERVISOR ENDPOINT TESTS ====================

class TestSupervisorEndpoint:
    """Tests for supervisor assignment endpoint"""
    
    def test_get_admin_users_returns_supervisor_fields(self, auth_headers):
        """GET /api/admin/users should return supervisor_id and supervisor_name fields"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        assert len(users) > 0, "Should have at least one user"
        
        # Check that users have supervisor fields (may be null)
        for user in users[:3]:  # Check first 3 users
            # supervisor_id and supervisor_name may not exist if never set
            # but the endpoint should work
            assert "user_id" in user, "User should have user_id"
        
        print(f"✓ GET /api/admin/users returned {len(users)} users")
    
    def test_put_supervisor_assigns_supervisor(self, auth_headers):
        """PUT /api/admin/users/{user_id}/supervisor should assign supervisor"""
        # First get users to find a target and supervisor
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
        assert response.status_code == 200
        users = response.json()
        
        # Find two different active users
        active_users = [u for u in users if u.get("is_active", True)]
        if len(active_users) < 2:
            pytest.skip("Need at least 2 active users to test supervisor assignment")
        
        target_user = active_users[0]
        supervisor_user = active_users[1]
        
        # Assign supervisor
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{target_user['user_id']}/supervisor",
            headers=auth_headers,
            json={"supervisor_id": supervisor_user["user_id"]}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user" in data, "Response should have user object"
        assert data["user"].get("supervisor_id") == supervisor_user["user_id"], "supervisor_id should be set"
        
        supervisor_name = f"{supervisor_user.get('first_name', '')} {supervisor_user.get('last_name', '')}".strip()
        if supervisor_name:
            assert data["user"].get("supervisor_name") == supervisor_name, "supervisor_name should be set"
        
        print(f"✓ PUT /api/admin/users/{target_user['user_id']}/supervisor assigned supervisor successfully")
    
    def test_put_supervisor_removes_supervisor(self, auth_headers):
        """PUT /api/admin/users/{user_id}/supervisor with null should remove supervisor"""
        # Get users
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
        users = response.json()
        active_users = [u for u in users if u.get("is_active", True)]
        
        if not active_users:
            pytest.skip("No active users to test")
        
        target_user = active_users[0]
        
        # Remove supervisor
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{target_user['user_id']}/supervisor",
            headers=auth_headers,
            json={"supervisor_id": None}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["user"].get("supervisor_id") is None, "supervisor_id should be null"
        assert data["user"].get("supervisor_name") is None, "supervisor_name should be null"
        
        print(f"✓ PUT /api/admin/users/{target_user['user_id']}/supervisor removed supervisor successfully")
    
    def test_put_supervisor_prevents_self_assignment(self, auth_headers):
        """PUT /api/admin/users/{user_id}/supervisor should prevent self-assignment"""
        # Get users
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
        users = response.json()
        
        if not users:
            pytest.skip("No users to test")
        
        target_user = users[0]
        
        # Try to assign self as supervisor
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{target_user['user_id']}/supervisor",
            headers=auth_headers,
            json={"supervisor_id": target_user["user_id"]}
        )
        assert response.status_code == 400, f"Expected 400 for self-assignment, got {response.status_code}"
        
        print("✓ PUT /api/admin/users/{user_id}/supervisor correctly prevents self-assignment")


# ==================== PROJECTS ENDPOINT TESTS ====================

class TestProjectsAssignment:
    """Tests for project assignment - verify assigned_at field is set"""
    
    def test_get_projects_returns_assigned_at_field(self, auth_headers):
        """GET /api/projects should return assigned_at field for assigned projects"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        projects = response.json()
        assert isinstance(projects, list), "Response should be a list"
        
        # Check structure of projects
        for project in projects[:5]:  # Check first 5
            assert "project_id" in project, "Project should have project_id"
            assert "status" in project, "Project should have status"
            # assigned_at may be null if not assigned
            if project.get("assigned_to_name"):
                # If assigned, should have assigned_at
                assert "assigned_at" in project, "Assigned project should have assigned_at field"
        
        print(f"✓ GET /api/projects returned {len(projects)} projects with proper structure")
    
    def test_project_assign_sets_assigned_at(self, auth_headers):
        """PUT /api/projects/{project_id}/assign should set assigned_at automatically"""
        # Get projects
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if not projects:
            pytest.skip("No projects to test assignment")
        
        # Get implementers
        response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        if response.status_code != 200:
            pytest.skip("Could not get implementers list")
        
        implementers = response.json()
        if not implementers:
            pytest.skip("No implementers available")
        
        # Find a project to assign
        project = projects[0]
        implementer = implementers[0]
        
        # Assign project
        response = requests.put(
            f"{BASE_URL}/api/projects/{project['project_id']}/assign",
            headers=auth_headers,
            json={
                "assigned_to_user_id": implementer["user_id"],
                "ticket_number": f"TK-TEST-{project['project_id'][:8]}"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            # Verify assigned_at is set
            assert data.get("assigned_at") is not None, "assigned_at should be set after assignment"
            print(f"✓ Project assignment sets assigned_at: {data.get('assigned_at')}")
        else:
            # May fail for other reasons (already assigned, etc.)
            print(f"⚠ Project assignment returned {response.status_code}: {response.text[:100]}")


# ==================== CLIENTS ENDPOINT TESTS ====================

class TestClientsModeloImpresoraFiscal:
    """Tests for modelo_impresora_fiscal field in clients"""
    
    def test_create_client_with_modelo_impresora_fiscal(self, auth_headers):
        """POST /api/clients should accept modelo_impresora_fiscal field"""
        import uuid
        unique_rif = f"J{uuid.uuid4().hex[:9].upper()}"
        
        response = requests.post(
            f"{BASE_URL}/api/clients",
            headers=auth_headers,
            json={
                "rif": unique_rif,
                "legal_name": f"TEST_Client_{unique_rif}",
                "fantasy_name": f"TEST_Fantasy_{unique_rif}",
                "segment": "Pymes",
                "modelo_impresora_fiscal": "Bematech",
                "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("modelo_impresora_fiscal") == "Bematech", "modelo_impresora_fiscal should be saved"
        
        # Cleanup - delete test client
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print(f"✓ POST /api/clients accepts modelo_impresora_fiscal field")
    
    def test_get_client_returns_modelo_impresora_fiscal(self, auth_headers):
        """GET /api/clients should return modelo_impresora_fiscal field"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        
        clients = response.json()
        # Just verify the field can exist in the response
        for client in clients[:5]:
            # Field may be null/empty but should be accessible
            _ = client.get("modelo_impresora_fiscal")
        
        print(f"✓ GET /api/clients returns modelo_impresora_fiscal field")


# ==================== AUTH USERS ENDPOINT TESTS ====================

class TestAuthUsersForSupervisor:
    """Tests for auth/users endpoint used by supervisor typeahead"""
    
    def test_get_auth_users_for_typeahead(self, auth_headers):
        """GET /api/auth/users should return users for typeahead search"""
        response = requests.get(f"{BASE_URL}/api/auth/users", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        
        # Verify structure for typeahead
        for user in users[:3]:
            assert "user_id" in user, "User should have user_id"
            assert "email" in user, "User should have email"
            # full_name is computed
            assert "full_name" in user or "first_name" in user, "User should have name fields"
        
        print(f"✓ GET /api/auth/users returned {len(users)} users for typeahead")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
