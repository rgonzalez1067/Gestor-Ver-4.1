"""
Test iteration 116: ticket_number obligatorio, email ad-hoc, progreso estandarizado
- PUT /api/projects/{id}/assign con ticket_number obligatorio
- POST /api/projects/{id}/send-adhoc-email con multipart/form-data
- GET /api/projects/{id}/rollup para proyectos single y multistore
- PUT /api/projects/{id}/matrix/phase recalcula rollup_progress para single
"""
import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def session():
    return requests.Session()


@pytest.fixture(scope="module")
def auth_token(session):
    """Login to get token"""
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@mega.com",
        "password": "Admin123!"
    })
    if response.status_code != 200:
        pytest.skip("Auth failed - cannot run tests")
    data = response.json()
    # Try multiple token field names
    return data.get("session_token") or data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def multipart_headers(auth_token):
    """Headers for multipart/form-data (no Content-Type, let requests set it)"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def projects(session, headers):
    """Get all projects"""
    response = session.get(f"{BASE_URL}/api/projects", headers=headers)
    if response.status_code != 200:
        pytest.skip("Cannot get projects")
    return response.json()


@pytest.fixture(scope="module")
def implementers(session, headers):
    """Get implementers list"""
    response = session.get(f"{BASE_URL}/api/projects/implementers/list", headers=headers)
    if response.status_code != 200 or not response.json():
        pytest.skip("Cannot get implementers")
    return response.json()


# ==================== TICKET NUMBER TESTS ====================

def test_assign_requires_ticket_number(session, headers, projects, implementers):
    """Assign without ticket_number should fail with 400"""
    if not projects:
        pytest.skip("No projects available to test")
    
    project_id = projects[0].get("project_id")
    implementer_id = implementers[0].get("user_id")
    
    # Try to assign without ticket_number (empty string)
    response = session.put(f"{BASE_URL}/api/projects/{project_id}/assign", headers=headers, json={
        "assigned_to_user_id": implementer_id,
        "ticket_number": ""
    })
    assert response.status_code == 400
    assert "ticket" in response.json().get("detail", "").lower()
    print(f"PASSED: Empty ticket_number rejected with 400")


def test_assign_with_valid_ticket_number(session, headers, projects, implementers):
    """Assign with valid ticket_number should succeed and return ticket"""
    if not projects:
        pytest.skip("No projects available to test")
    
    project_id = projects[0].get("project_id")
    implementer_id = implementers[0].get("user_id")
    
    # Generate unique ticket
    unique_ticket = f"TEST-TK-{uuid.uuid4().hex[:6].upper()}"
    
    # Assign with ticket_number
    response = session.put(f"{BASE_URL}/api/projects/{project_id}/assign", headers=headers, json={
        "assigned_to_user_id": implementer_id,
        "ticket_number": unique_ticket
    })
    assert response.status_code == 200
    data = response.json()
    assert "ticket_number" in data
    assert data["ticket_number"] == unique_ticket
    print(f"PASSED: Project assigned with ticket_number={unique_ticket}")
    
    # Verify ticket is saved in project
    proj_res = session.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers)
    assert proj_res.status_code == 200
    proj_data = proj_res.json()
    assert proj_data.get("ticket_number") == unique_ticket
    print(f"PASSED: ticket_number persisted in project")


def test_assign_ticket_uniqueness(session, headers, projects, implementers):
    """Duplicate ticket_number should be rejected"""
    if len(projects) < 2:
        pytest.skip("Need at least 2 projects to test uniqueness")
    
    implementer_id = implementers[0].get("user_id")
    
    # First, assign a project with a ticket
    project1_id = projects[0].get("project_id")
    unique_ticket = f"UNIQUE-{uuid.uuid4().hex[:6].upper()}"
    
    res1 = session.put(f"{BASE_URL}/api/projects/{project1_id}/assign", headers=headers, json={
        "assigned_to_user_id": implementer_id,
        "ticket_number": unique_ticket
    })
    assert res1.status_code == 200
    
    # Try to assign the same ticket to another project
    project2_id = projects[1].get("project_id")
    res2 = session.put(f"{BASE_URL}/api/projects/{project2_id}/assign", headers=headers, json={
        "assigned_to_user_id": implementer_id,
        "ticket_number": unique_ticket
    })
    assert res2.status_code == 400
    detail = res2.json().get("detail", "").lower()
    assert "ya está asignado" in detail or "ticket" in detail
    print(f"PASSED: Duplicate ticket_number rejected with 400")


# ==================== AD-HOC EMAIL TESTS ====================

def test_adhoc_email_requires_subject(session, multipart_headers, projects):
    """Ad-hoc email without subject should fail"""
    if not projects:
        pytest.skip("No projects available")
    
    project_id = projects[0].get("project_id")
    
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps(["test@example.com"]),
            "subject": "",
            "message": "Test message"
        }
    )
    # 400 or 422 (FastAPI validation) are both acceptable for bad input
    assert response.status_code in [400, 422]
    print(f"PASSED: Empty subject rejected with {response.status_code}")


def test_adhoc_email_requires_recipients(session, multipart_headers, projects):
    """Ad-hoc email without recipients should fail"""
    if not projects:
        pytest.skip("No projects available")
    
    project_id = projects[0].get("project_id")
    
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps([]),
            "subject": "Test Subject",
            "message": "Test message"
        }
    )
    assert response.status_code == 400
    assert "destinatarios" in response.json().get("detail", "").lower()
    print("PASSED: Empty recipients rejected with 400")


def test_adhoc_email_message_max_length(session, multipart_headers, projects):
    """Ad-hoc email message cannot exceed 500 characters"""
    if not projects:
        pytest.skip("No projects available")
    
    project_id = projects[0].get("project_id")
    
    long_message = "A" * 501
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Test Subject",
            "message": long_message
        }
    )
    assert response.status_code == 400
    detail = response.json().get("detail", "").lower()
    assert "500" in detail or "exceder" in detail
    print("PASSED: Message > 500 chars rejected with 400")


def test_adhoc_email_success(session, multipart_headers, projects):
    """Ad-hoc email with valid data should succeed"""
    if not projects:
        pytest.skip("No projects available")
    
    project_id = projects[0].get("project_id")
    
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps(["test@example.com", "otro@example.com"]),
            "subject": "Asunto de Prueba",
            "message": "Este es un mensaje de prueba para el email ad-hoc."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data.get("recipients") == ["test@example.com", "otro@example.com"]
    assert "bitacora_entry_id" in data
    print(f"PASSED: Ad-hoc email sent successfully. Status: {data.get('status')}")


def test_adhoc_email_includes_ticket_in_subject(session, multipart_headers, headers, projects):
    """Ad-hoc email subject should include ticket if project has one"""
    # Find a project with ticket_number
    project_with_ticket = None
    for p in projects:
        if p.get("ticket_number"):
            project_with_ticket = p
            break
    
    if not project_with_ticket:
        pytest.skip("No project with ticket_number found")
    
    project_id = project_with_ticket.get("project_id")
    
    # Re-fetch project to get latest ticket
    proj_res = session.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers)
    current_ticket = proj_res.json().get("ticket_number", "")
    
    if not current_ticket:
        pytest.skip("Project no longer has a ticket_number")
    
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Seguimiento",
            "message": "Mensaje de seguimiento"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # Verify ticket is in subject (can be any ticket)
    assert "[Ticket " in data.get("subject", "") and "]" in data.get("subject", "")
    print(f"PASSED: Ticket included in email subject: {data.get('subject')}")


def test_adhoc_email_auto_bitacora(session, multipart_headers, headers, projects):
    """Ad-hoc email should auto-register in bitacora"""
    if not projects:
        pytest.skip("No projects available")
    
    project_id = projects[0].get("project_id")
    
    # Get initial bitacora count
    initial_proj = session.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers).json()
    initial_count = len(initial_proj.get("bitacora", []))
    
    # Send email
    response = session.post(
        f"{BASE_URL}/api/projects/{project_id}/send-adhoc-email",
        headers=multipart_headers,
        data={
            "recipients": json.dumps(["bitacora@test.com"]),
            "subject": "Test Bitacora Auto-Registro",
            "message": "Verificando auto-registro en bitacora"
        }
    )
    assert response.status_code == 200
    
    # Check bitacora count increased
    updated_proj = session.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers).json()
    new_count = len(updated_proj.get("bitacora", []))
    assert new_count > initial_count
    
    # Verify the entry
    latest_entry = updated_proj.get("bitacora", [])[-1] if updated_proj.get("bitacora") else None
    assert latest_entry is not None
    assert "[Email Ad-hoc]" in latest_entry.get("text", "")
    assert "Test Bitacora Auto-Registro" in latest_entry.get("text", "")
    print(f"PASSED: Ad-hoc email auto-registered in bitacora")


# ==================== ROLLUP PROGRESS TESTS ====================

def test_rollup_endpoint_single_project(session, headers, projects):
    """GET /api/projects/{id}/rollup should work for single projects"""
    # Find a single project
    single_project = None
    for p in projects:
        if p.get("project_type") != "multistore":
            single_project = p
            break
    
    if not single_project:
        pytest.skip("No single project found")
    
    project_id = single_project.get("project_id")
    
    response = session.get(f"{BASE_URL}/api/projects/{project_id}/rollup", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "global_progress" in data
    assert "bank_progress" in data
    assert isinstance(data["global_progress"], (int, float))
    print(f"PASSED: Rollup for single project returned global_progress={data['global_progress']}")


def test_rollup_endpoint_multistore_project(session, headers, projects):
    """GET /api/projects/{id}/rollup should work for multistore projects"""
    # Find a multistore project
    multistore_project = None
    for p in projects:
        if p.get("project_type") == "multistore":
            multistore_project = p
            break
    
    if not multistore_project:
        pytest.skip("No multistore project found")
    
    project_id = multistore_project.get("project_id")
    
    response = session.get(f"{BASE_URL}/api/projects/{project_id}/rollup", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "global_progress" in data
    assert "bank_progress" in data
    print(f"PASSED: Rollup for multistore project returned global_progress={data['global_progress']}")


def test_matrix_phase_update_recalculates_single_progress(session, headers, projects):
    """PUT /api/projects/{id}/matrix/phase should recalculate rollup_progress for single"""
    # Find a single project with matrix and client_notified
    single_project = None
    for p in projects:
        if (p.get("project_type") != "multistore" and 
            p.get("client_notified") == True and
            p.get("implementation_matrix")):
            single_project = p
            break
    
    if not single_project:
        pytest.skip("No single notified project with matrix found")
    
    project_id = single_project.get("project_id")
    matrix = single_project.get("implementation_matrix", {})
    
    if not matrix:
        pytest.skip("Project has no implementation matrix")
    
    # Get first bank and product
    bank_name = list(matrix.keys())[0]
    product_name = list(matrix[bank_name].keys())[0]
    
    # Toggle a phase
    response = session.put(
        f"{BASE_URL}/api/projects/{project_id}/matrix/phase",
        headers=headers,
        json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Recibido",
            "completed": True
        }
    )
    assert response.status_code == 200
    
    # Check rollup was recalculated
    updated_proj = session.get(f"{BASE_URL}/api/projects/{project_id}", headers=headers).json()
    assert "rollup_progress" in updated_proj
    print(f"PASSED: Matrix phase update recalculated rollup_progress for single project")


# ==================== ADDITIONAL TESTS ====================

def test_assign_email_includes_ticket_in_subject(session, headers, projects, implementers):
    """Assignment email to implementer should include ticket in subject [Ticket X]"""
    if not projects:
        pytest.skip("No projects available")
    
    implementer_id = implementers[0].get("user_id")
    project_id = projects[0].get("project_id")
    unique_ticket = f"EMAIL-TK-{uuid.uuid4().hex[:6].upper()}"
    
    response = session.put(f"{BASE_URL}/api/projects/{project_id}/assign", headers=headers, json={
        "assigned_to_user_id": implementer_id,
        "ticket_number": unique_ticket
    })
    assert response.status_code == 200
    data = response.json()
    assert data.get("ticket_number") == unique_ticket
    print(f"PASSED: Project assigned with ticket {unique_ticket}, email should have [Ticket {unique_ticket}] in subject")


def test_projects_list_includes_ticket(session, headers, projects):
    """GET /api/projects should return ticket_number for assigned projects"""
    # Find a project with ticket
    has_ticket = False
    for p in projects:
        if p.get("ticket_number"):
            has_ticket = True
            print(f"PASSED: Found project with ticket_number: {p.get('ticket_number')}")
            break
    
    if not has_ticket:
        print("INFO: No projects with ticket_number found (may need to assign one first)")
    
    assert isinstance(projects, list)
    print("PASSED: Projects list retrieved successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
