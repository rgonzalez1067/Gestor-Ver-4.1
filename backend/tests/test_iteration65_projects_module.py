# ruff: noqa
"""
Test iteration 65: Projects Module (Post-Venta)
Tests for the Projects module including:
- GET /api/projects - List all projects
- GET /api/projects/stats - Project statistics
- GET /api/projects/{project_id} - Get project detail
- PUT /api/projects/{project_id}/assign - Assign implementer
- PUT /api/projects/{project_id}/status - Update project status
- POST /api/projects/{project_id}/notes - Add note to project
- GET /api/projects/implementers/list - List implementers
- Trigger: Creating project from quote (Enviada a Imple status)
- Settings: implementation_manager_email field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"


class TestProjectsModule:
    """Test suite for Projects Module (Post-Venta)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - authenticate before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ==================== LIST PROJECTS ====================
    def test_get_projects_list(self):
        """GET /api/projects - Should return list of projects"""
        response = self.session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        projects = response.json()
        assert isinstance(projects, list), "Response should be a list"
        
        # Verify existing projects have required fields
        if len(projects) > 0:
            project = projects[0]
            required_fields = ["project_id", "project_number", "quote_id", "client_name", "status"]
            for field in required_fields:
                assert field in project, f"Project should have '{field}' field"
            print(f"✓ Found {len(projects)} projects. First: {project.get('project_number')}")
    
    # ==================== PROJECT STATS ====================
    def test_get_project_stats(self):
        """GET /api/projects/stats - Should return statistics by status"""
        response = self.session.get(f"{BASE_URL}/api/projects/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        stats = response.json()
        required_stats = ["total", "pending", "in_progress", "blocked", "completed"]
        for stat in required_stats:
            assert stat in stats, f"Stats should have '{stat}' field"
            assert isinstance(stats[stat], int), f"'{stat}' should be an integer"
        
        print(f"✓ Stats - Total: {stats['total']}, Pending: {stats['pending']}, In Progress: {stats['in_progress']}, Blocked: {stats['blocked']}, Completed: {stats['completed']}")
    
    # ==================== GET PROJECT DETAIL ====================
    def test_get_project_detail(self):
        """GET /api/projects/{project_id} - Should return project detail"""
        # First get list to find a project
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        assert list_response.status_code == 200
        
        projects = list_response.json()
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0]["project_id"]
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        project = response.json()
        assert project["project_id"] == project_id
        
        # Verify detailed fields
        detail_fields = ["quote_id", "quote_number", "client_name", "client_rif", "status", "notes", "services"]
        for field in detail_fields:
            assert field in project, f"Project detail should have '{field}' field"
        
        print(f"✓ Project detail: {project.get('project_number')} - Client: {project.get('client_name')}")
    
    def test_get_project_not_found(self):
        """GET /api/projects/{project_id} - Should return 404 for non-existent project"""
        response = self.session.get(f"{BASE_URL}/api/projects/nonexistent_project_id")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    # ==================== GET IMPLEMENTERS ====================
    def test_get_implementers_list(self):
        """GET /api/projects/implementers/list - Should return list of implementers"""
        response = self.session.get(f"{BASE_URL}/api/projects/implementers/list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        implementers = response.json()
        assert isinstance(implementers, list), "Response should be a list"
        
        # Verify implementer fields
        if len(implementers) > 0:
            impl = implementers[0]
            assert "user_id" in impl, "Implementer should have user_id"
            assert "first_name" in impl or "email" in impl, "Implementer should have name or email"
            print(f"✓ Found {len(implementers)} implementers. First: {impl.get('first_name', '')} {impl.get('last_name', '')}")
        else:
            print("✓ Implementers list is empty (fallback to all users if no specific cargos)")
    
    # ==================== ASSIGN PROJECT ====================
    def test_assign_project(self):
        """PUT /api/projects/{project_id}/assign - Should assign project to implementer"""
        # Get a project to assign
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = list_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        # Find a project that's not already assigned or use first available
        project = projects[0]
        project_id = project["project_id"]
        
        # Get an implementer
        impl_response = self.session.get(f"{BASE_URL}/api/projects/implementers/list")
        implementers = impl_response.json()
        
        if len(implementers) == 0:
            pytest.skip("No implementers available for testing")
        
        implementer_id = implementers[0]["user_id"]
        
        # Assign project
        assign_data = {
            "assigned_to_user_id": implementer_id,
            "estimated_delivery_date": "2026-02-15"
        }
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/assign", json=assign_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "message" in result
        assert "assigned_to" in result
        
        # Verify the project was updated
        verify_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = verify_response.json()
        assert updated_project["assigned_to_user_id"] == implementer_id
        assert updated_project["status"] == "Asignado / En Proceso"
        
        print(f"✓ Project assigned to {result['assigned_to']}")
    
    def test_assign_project_invalid_implementer(self):
        """PUT /api/projects/{project_id}/assign - Should return 404 for invalid implementer"""
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = list_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0]["project_id"]
        assign_data = {"assigned_to_user_id": "invalid_user_id"}
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/assign", json=assign_data)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    # ==================== UPDATE STATUS ====================
    def test_update_project_status(self):
        """PUT /api/projects/{project_id}/status - Should update project status"""
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = list_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0]["project_id"]
        current_status = projects[0]["status"]
        
        # Define valid status transitions
        status_options = [
            "Pendiente por Asignar",
            "Asignado / En Proceso", 
            "Detenido por Cliente/Banco",
            "Finalizado / Producción"
        ]
        
        # Pick a status different from current
        new_status = [s for s in status_options if s != current_status][0]
        
        status_data = {
            "new_status": new_status,
            "note": "Test status change"
        }
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/status", json=status_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "message" in result
        assert "new_status" in result
        assert result["new_status"] == new_status
        
        # Verify the project was updated
        verify_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = verify_response.json()
        assert updated_project["status"] == new_status
        
        # Verify note was added
        notes = updated_project.get("notes", [])
        assert len(notes) > 0, "Note should be added"
        latest_note = notes[-1]
        assert "Test status change" in latest_note.get("text", "") or new_status in latest_note.get("text", "")
        
        print(f"✓ Status updated to '{new_status}'")
    
    def test_update_project_invalid_status(self):
        """PUT /api/projects/{project_id}/status - Should return 400 for invalid status"""
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = list_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0]["project_id"]
        status_data = {"new_status": "Invalid Status"}
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/status", json=status_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    
    # ==================== ADD NOTE ====================
    def test_add_project_note(self):
        """POST /api/projects/{project_id}/notes - Should add note to project"""
        list_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = list_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for testing")
        
        project_id = projects[0]["project_id"]
        note_data = {"text": "Test note from iteration 65 testing"}
        
        response = self.session.post(f"{BASE_URL}/api/projects/{project_id}/notes", json=note_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "note_id" in result
        assert result["text"] == note_data["text"]
        
        # Verify note was added to project
        verify_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = verify_response.json()
        notes = updated_project.get("notes", [])
        
        # Find our note
        found = any(n.get("text") == note_data["text"] for n in notes)
        assert found, "Added note should be in project notes"
        
        print(f"✓ Note added: {note_data['text'][:30]}...")
    
    # ==================== SETTINGS - IMPLEMENTATION MANAGER EMAIL ====================
    def test_settings_implementation_manager_email(self):
        """GET/PUT /api/config/settings - Should support implementation_manager_email"""
        # Get current settings
        response = self.session.get(f"{BASE_URL}/api/config/settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        settings = response.json()
        # Verify implementation_manager_email field exists in response
        assert "implementation_manager_email" in settings, "Settings should have 'implementation_manager_email' field"
        
        print(f"✓ Implementation Manager Email configured: {settings.get('implementation_manager_email') or 'Not set'}")
    
    def test_update_settings_implementation_manager_email(self):
        """PUT /api/config/settings - Should update implementation_manager_email"""
        test_email = "gerente.test@empresa.com"
        
        update_data = {
            "implementation_manager_email": test_email
        }
        
        response = self.session.put(f"{BASE_URL}/api/config/settings", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify update
        verify_response = self.session.get(f"{BASE_URL}/api/config/settings")
        settings = verify_response.json()
        assert settings.get("implementation_manager_email") == test_email
        
        print(f"✓ Implementation Manager Email updated to: {test_email}")


class TestProjectTriggerFromQuote:
    """Test the trigger that creates a project when quote status changes to 'Enviada a Imple'"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_project_exists_for_implementation_quote(self):
        """Verify that projects exist and are linked to quotes"""
        # Get projects
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        
        projects = projects_response.json()
        if len(projects) == 0:
            pytest.skip("No projects to verify")
        
        # Verify each project has a quote_id
        for project in projects:
            assert "quote_id" in project, "Project should have quote_id"
            assert project["quote_id"], "quote_id should not be empty"
            assert "quote_number" in project
        
        print(f"✓ All {len(projects)} projects have valid quote references")
    
    def test_project_inherits_client_data(self):
        """Verify projects inherit client data from quote"""
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = projects_response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to verify")
        
        project = projects[0]
        
        # Verify client data fields
        client_fields = ["client_id", "client_name", "client_rif"]
        for field in client_fields:
            assert field in project, f"Project should have '{field}' field"
        
        print(f"✓ Project has client data: {project.get('client_name')} ({project.get('client_rif')})")
    
    def test_no_duplicate_project_for_same_quote(self):
        """Verify no duplicate projects exist for the same quote_id"""
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        projects = projects_response.json()
        
        if len(projects) <= 1:
            pytest.skip("Need more than 1 project to check for duplicates")
        
        quote_ids = [p.get("quote_id") for p in projects if p.get("quote_id")]
        unique_quote_ids = set(quote_ids)
        
        assert len(quote_ids) == len(unique_quote_ids), f"Found duplicate projects for same quote. Total: {len(quote_ids)}, Unique: {len(unique_quote_ids)}"
        
        print(f"✓ No duplicate projects found. {len(unique_quote_ids)} unique quote references.")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
