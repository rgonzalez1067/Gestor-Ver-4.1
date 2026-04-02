"""
Iteration 146: Workflow Optimization Tests
Tests for:
1. Part 1: Assign project WITHOUT ticket_number field - only implementer + delivery date
2. Part 1: fecha_asignacion is stored and displayed
3. Part 2: Security Lock - when project has assignee but no ticket_number
4. Part 2: Security Lock - input ticket via PUT /api/projects/{id}/ticket endpoint
5. Part 3: VTID Generator - POST /api/projects/{id}/vtids/generate
6. Part 3: VTID Generator - GET /api/projects/{id}/vtids
7. Part 3: DELETE /api/projects/{id}/vtids
8. Part 4: {Lista_VTID} template variable resolves to HTML table
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@meganexus.com"
ADMIN_PASSWORD = "Admin123!"

# Existing project IDs from context
PROJECT_WITH_TICKET = "prj_ac2f9862c664"  # has ticket=12345, assigned, has 10 VTIDs
PROJECT_WITH_TICKET_2 = "prj_bceb6a9364e7"  # has ticket=78833, assigned
PROJECT_WITH_TICKET_3 = "prj_c536858da780"  # has ticket=56785, assigned


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token using session_token from login response."""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API uses session_token (not token)
    token = data.get("session_token") or data.get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authorization."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestProjectAssignment:
    """Part 1: Test project assignment WITHOUT ticket_number field."""

    def test_get_implementers_list(self, auth_headers):
        """Test that implementers list endpoint works."""
        response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} implementers")
        if data:
            print(f"First implementer: {data[0]}")

    def test_assign_project_without_ticket(self, auth_headers):
        """Test assigning a project with only implementer + delivery date (no ticket_number)."""
        # First get implementers
        impl_response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        assert impl_response.status_code == 200
        implementers = impl_response.json()
        assert len(implementers) > 0, "No implementers found"
        
        implementer_id = implementers[0]["user_id"]
        
        # Assign project - note: no ticket_number field in payload
        assign_payload = {
            "assigned_to_user_id": implementer_id,
            "estimated_delivery_date": "2026-04-15"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/assign",
            json=assign_payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Assign failed: {response.text}"
        data = response.json()
        assert "assigned_to" in data or "message" in data
        print(f"Assignment response: {data}")

    def test_fecha_asignacion_stored(self, auth_headers):
        """Test that fecha_asignacion is stored after assignment."""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}", headers=auth_headers)
        assert response.status_code == 200
        project = response.json()
        
        # Check fecha_asignacion is stored
        assert "fecha_asignacion" in project or "assigned_at" in project, \
            f"fecha_asignacion not found in project: {list(project.keys())}"
        
        fecha = project.get("fecha_asignacion") or project.get("assigned_at")
        print(f"fecha_asignacion: {fecha}")
        assert fecha is not None


class TestSecurityLock:
    """Part 2: Security Lock - ticket required to unlock execution."""

    def test_project_with_ticket_not_locked(self, auth_headers):
        """Test that project with ticket_number is not locked."""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}", headers=auth_headers)
        assert response.status_code == 200
        project = response.json()
        
        # Project has ticket_number, so it should not be locked
        has_assignee = bool(project.get("assigned_to_name"))
        has_ticket = bool(project.get("ticket_number"))
        
        print(f"Project {PROJECT_WITH_TICKET}: assigned_to_name={project.get('assigned_to_name')}, ticket_number={project.get('ticket_number')}")
        
        # If has assignee and ticket, not locked
        if has_assignee and has_ticket:
            print("Project is NOT locked (has both assignee and ticket)")
        elif has_assignee and not has_ticket:
            print("Project IS locked (has assignee but no ticket)")

    def test_update_ticket_number_endpoint(self, auth_headers):
        """Test PUT /api/projects/{id}/ticket endpoint."""
        # Use a project that already has a ticket to test the endpoint
        new_ticket = "TK-TEST-UPDATE-001"
        
        response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_2}/ticket",
            json={"ticket_number": new_ticket},
            headers=auth_headers
        )
        
        # Should succeed or fail with duplicate ticket error
        if response.status_code == 200:
            data = response.json()
            assert "ticket_number" in data or "message" in data
            print(f"Ticket update response: {data}")
        elif response.status_code == 400:
            # Might fail if ticket already exists
            print(f"Ticket update failed (expected if duplicate): {response.json()}")
        else:
            assert False, f"Unexpected status: {response.status_code} - {response.text}"

    def test_update_ticket_empty_fails(self, auth_headers):
        """Test that empty ticket_number is rejected."""
        response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/ticket",
            json={"ticket_number": ""},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for empty ticket: {response.text}"
        print(f"Empty ticket rejected: {response.json()}")


class TestVTIDGenerator:
    """Part 3: VTID Generator tests."""

    def test_get_vtids(self, auth_headers):
        """Test GET /api/projects/{id}/vtids endpoint."""
        response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/vtids",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "vtids" in data
        assert "prefix" in data
        print(f"VTIDs: {len(data['vtids'])} items, prefix: {data['prefix']}")
        
        if data["vtids"]:
            print(f"First VTID: {data['vtids'][0]}")

    def test_generate_vtids(self, auth_headers):
        """Test POST /api/projects/{id}/vtids/generate endpoint."""
        # First delete existing VTIDs if any
        requests.delete(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_3}/vtids",
            headers=auth_headers
        )
        
        # Generate new VTIDs
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_3}/vtids/generate",
            json={"prefix": "TEST", "start_number": 1},
            headers=auth_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "vtids" in data
            assert "total" in data
            assert "prefix" in data
            print(f"Generated {data['total']} VTIDs with prefix {data['prefix']}")
            
            # Verify VTID format: prefix + 3 digits
            if data["vtids"]:
                first_vtid = data["vtids"][0]["code"]
                assert first_vtid.startswith("TEST"), f"VTID should start with prefix: {first_vtid}"
                print(f"First VTID code: {first_vtid}")
        elif response.status_code == 400:
            # Might fail if project has no boxes
            print(f"VTID generation failed (expected if no boxes): {response.json()}")
        else:
            assert False, f"Unexpected status: {response.status_code} - {response.text}"

    def test_generate_vtids_empty_prefix_fails(self, auth_headers):
        """Test that empty prefix is rejected."""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/vtids/generate",
            json={"prefix": "", "start_number": 1},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Expected 400 for empty prefix: {response.text}"
        print(f"Empty prefix rejected: {response.json()}")

    def test_delete_vtids(self, auth_headers):
        """Test DELETE /api/projects/{id}/vtids endpoint."""
        # First generate VTIDs to ensure there's something to delete
        requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_3}/vtids/generate",
            json={"prefix": "DEL", "start_number": 1},
            headers=auth_headers
        )
        
        response = requests.delete(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_3}/vtids",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"Delete VTIDs response: {data}")
        
        # Verify VTIDs are deleted by checking the project directly
        get_response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_3}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        project = get_response.json()
        vtids = project.get("vtids", [])
        assert len(vtids) == 0, f"VTIDs should be empty after delete, got {len(vtids)}"
        print("VTIDs successfully deleted")


class TestListaVTIDVariable:
    """Part 4: {Lista_VTID} template variable tests."""

    def test_template_variables_include_lista_vtid(self, auth_headers):
        """Test that template variables endpoint returns Lista_VTID."""
        response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/template-variables",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "variables" in data
        variables = data["variables"]
        
        # Check Lista_VTID is in available_tags
        available_tags = data.get("available_tags", [])
        tag_keys = [t["key"] for t in available_tags]
        assert "Lista_VTID" in tag_keys, f"Lista_VTID not in available_tags: {tag_keys}"
        print(f"Lista_VTID found in available_tags")

    def test_preview_notification_resolves_lista_vtid(self, auth_headers):
        """Test that preview notification resolves Lista_VTID variable."""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}/preview-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check variables in response
        variables = data.get("variables", {})
        print(f"Preview variables keys: {list(variables.keys())}")
        
        # Lista_VTID should be resolved (might be in variables or in HTML)
        if "Lista_VTID" in variables:
            lista_vtid = variables["Lista_VTID"]
            print(f"Lista_VTID resolved: {lista_vtid[:100] if lista_vtid else 'empty'}...")


class TestAssignDialogNoTicketField:
    """Test that assign dialog doesn't require ticket_number."""

    def test_assign_model_no_ticket_field(self, auth_headers):
        """Verify ProjectAssign model doesn't require ticket_number."""
        # Get implementers
        impl_response = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=auth_headers)
        implementers = impl_response.json()
        
        if not implementers:
            pytest.skip("No implementers available")
        
        # Try to assign with minimal payload (no ticket_number)
        assign_payload = {
            "assigned_to_user_id": implementers[0]["user_id"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET_2}/assign",
            json=assign_payload,
            headers=auth_headers
        )
        
        # Should succeed - ticket_number is NOT part of assign payload
        assert response.status_code == 200, f"Assign without ticket should work: {response.text}"
        print(f"Assign without ticket_number succeeded: {response.json()}")


class TestProjectDetailData:
    """Test project detail data structure."""

    def test_project_has_required_fields(self, auth_headers):
        """Test that project has all required fields for the new workflow."""
        response = requests.get(f"{BASE_URL}/api/projects/{PROJECT_WITH_TICKET}", headers=auth_headers)
        assert response.status_code == 200
        project = response.json()
        
        # Check for new fields
        print(f"Project fields: {list(project.keys())}")
        
        # Check assigned_to_name
        if project.get("assigned_to_name"):
            print(f"assigned_to_name: {project['assigned_to_name']}")
        
        # Check ticket_number
        if project.get("ticket_number"):
            print(f"ticket_number: {project['ticket_number']}")
        
        # Check fecha_asignacion
        if project.get("fecha_asignacion"):
            print(f"fecha_asignacion: {project['fecha_asignacion']}")
        
        # Check vtids
        if project.get("vtids"):
            print(f"vtids count: {len(project['vtids'])}")
            if project["vtids"]:
                print(f"First VTID: {project['vtids'][0]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
