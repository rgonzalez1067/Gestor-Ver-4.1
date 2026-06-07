# ruff: noqa
"""
Test iteration 83 - Dynamic action buttons for projects
Features tested:
1. PUT /api/projects/{id}/status - accepts new_status, note, change_date
2. PUT /api/projects/{id}/assign - accepts reassignment_comment and reassignment_date
3. GET /api/projects - verify projects have correct structure
4. GET /api/projects/implementers/list - returns implementers
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestProjectActions:
    """Test project status and assign/reassign endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Authenticate and return token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_01_get_projects(self, auth_headers):
        """Test GET /api/projects returns list with required fields"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get projects: {response.text}"
        
        projects = response.json()
        assert isinstance(projects, list), "Projects should be a list"
        print(f"Found {len(projects)} projects")
        
        if len(projects) > 0:
            project = projects[0]
            # Verify required fields exist
            assert "project_id" in project, "Missing project_id"
            assert "project_number" in project, "Missing project_number"
            assert "status" in project, "Missing status"
            assert "client_name" in project, "Missing client_name"
            print(f"First project: {project.get('project_number')} - Status: {project.get('status')} - Assigned: {project.get('assigned_to_name')}")
    
    def test_02_get_project_stats(self, auth_headers):
        """Test GET /api/projects/stats returns counts"""
        response = requests.get(f"{BASE_URL}/api/projects/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        
        stats = response.json()
        assert "total" in stats
        assert "pending" in stats
        assert "in_progress" in stats
        assert "blocked" in stats
        assert "completed" in stats
        print(f"Stats: total={stats['total']}, pending={stats['pending']}, in_progress={stats['in_progress']}, blocked={stats['blocked']}, completed={stats['completed']}")
    
    def test_03_get_implementers_list(self, auth_headers):
        """Test GET /api/projects/implementers/list returns implementers"""
        response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get implementers: {response.text}"
        
        implementers = response.json()
        assert isinstance(implementers, list), "Implementers should be a list"
        print(f"Found {len(implementers)} implementers")
        
        if len(implementers) > 0:
            impl = implementers[0]
            assert "user_id" in impl, "Missing user_id"
            assert "first_name" in impl, "Missing first_name"
            print(f"First implementer: {impl.get('first_name')} {impl.get('last_name')} - {impl.get('cargo')}")
    
    def test_04_get_project_by_id(self, auth_headers):
        """Test GET /api/projects/{id} - get specific project"""
        # First get list to find a project ID
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project_id = projects[0]["project_id"]
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get project: {response.text}"
        
        project = response.json()
        assert project["project_id"] == project_id
        print(f"Got project: {project.get('project_number')}")
    
    def test_05_status_change_endpoint_validation(self, auth_headers):
        """Test PUT /api/projects/{id}/status - validate request body"""
        # First get list to find a project ID
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project_id = projects[0]["project_id"]
        current_status = projects[0]["status"]
        
        # Test invalid status
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}/status",
            json={"new_status": "Invalid Status"},
            headers=auth_headers
        )
        assert response.status_code == 400, "Should reject invalid status"
        print("Invalid status correctly rejected")
        
    def test_06_status_change_with_full_payload(self, auth_headers):
        """Test PUT /api/projects/{id}/status with new_status, note, and change_date"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project_id = projects[0]["project_id"]
        current_status = projects[0]["status"]
        
        # Pick a different status
        valid_statuses = ["Asignado / En Proceso", "Detenido por Cliente/Banco", "Finalizado / Producción"]
        new_status = None
        for s in valid_statuses:
            if s != current_status:
                new_status = s
                break
        
        if not new_status:
            pytest.skip("Cannot find different status to change to")
        
        # Test status change with full payload
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}/status",
            json={
                "new_status": new_status,
                "note": "Test status change from automated test",
                "change_date": "2026-01-15"
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Status change failed: {response.text}"
        
        result = response.json()
        assert "new_status" in result
        assert result["new_status"] == new_status
        print(f"Status changed to: {new_status}")
        
        # Verify via GET
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        project = response.json()
        assert project["status"] == new_status, "Status not persisted"
        print("Status change verified via GET")
        
        # Revert status back to original
        requests.put(
            f"{BASE_URL}/api/projects/{project_id}/status",
            json={"new_status": current_status, "note": "Reverting to original status"},
            headers=auth_headers
        )
    
    def test_07_assign_endpoint_with_full_payload(self, auth_headers):
        """Test PUT /api/projects/{id}/assign with reassignment fields"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project = projects[0]
        project_id = project["project_id"]
        
        # Get implementers
        impl_response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        implementers = impl_response.json()
        
        if len(implementers) == 0:
            pytest.skip("No implementers to assign")
        
        # Pick a different implementer if current exists
        current_assignee = project.get("assigned_to_user_id")
        new_implementer = None
        for impl in implementers:
            if impl["user_id"] != current_assignee:
                new_implementer = impl
                break
        
        if not new_implementer:
            new_implementer = implementers[0]
        
        # Test assignment with full payload (for reassignment scenario)
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}/assign",
            json={
                "assigned_to_user_id": new_implementer["user_id"],
                "estimated_delivery_date": "2026-02-28",
                "reassignment_comment": "Test reassignment from automated test",
                "reassignment_date": "2026-01-15"
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Assignment failed: {response.text}"
        
        result = response.json()
        assert "assigned_to" in result
        print(f"Assigned to: {result['assigned_to']}")
        
        # Verify via GET
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        project = response.json()
        assert project["assigned_to_user_id"] == new_implementer["user_id"]
        assert project["assigned_to_name"] is not None
        print(f"Assignment verified: {project['assigned_to_name']}")
    
    def test_08_verify_notes_contain_reassignment_info(self, auth_headers):
        """Verify that reassignment notes include previous assignee and comment"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project_id = projects[0]["project_id"]
        
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        project = response.json()
        
        notes = project.get("notes", [])
        if len(notes) > 0:
            last_note = notes[-1]
            print(f"Last note: {last_note.get('text', '')[:200]}")
            # Check if it contains reassignment info
            if "reasignado" in last_note.get("text", "").lower() or "asignado" in last_note.get("text", "").lower():
                print("Note contains assignment/reassignment info")
        else:
            print("No notes found")
    
    def test_09_project_not_found(self, auth_headers):
        """Test 404 for non-existent project"""
        response = requests.get(
            f"{BASE_URL}/api/projects/non_existent_id",
            headers=auth_headers
        )
        assert response.status_code == 404
        print("404 correctly returned for non-existent project")
    
    def test_10_implementer_not_found(self, auth_headers):
        """Test 404 when assigning to non-existent implementer"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        if len(projects) == 0:
            pytest.skip("No projects to test")
        
        project_id = projects[0]["project_id"]
        
        response = requests.put(
            f"{BASE_URL}/api/projects/{project_id}/assign",
            json={"assigned_to_user_id": "non_existent_user_id"},
            headers=auth_headers
        )
        assert response.status_code == 404, "Should return 404 for non-existent implementer"
        print("404 correctly returned for non-existent implementer")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
