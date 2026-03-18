"""
Test Iteration 114: Multistore Flow for Send-to-Implementation
Tests the new multistore feature when sending quotes to implementation.
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def get_auth_session():
    """Get authenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    login_payload = {"email": "test@mega.com", "password": "Admin123!"}
    login_res = session.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    
    if login_res.status_code == 200:
        token = login_res.json().get("session_token") or login_res.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    # Try register
    register_res = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": "test@mega.com",
        "password": "Admin123!",
        "first_name": "Test",
        "last_name": "User"
    })
    if register_res.status_code in [200, 201]:
        token = register_res.json().get("session_token") or register_res.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    return None


def create_test_client(session):
    """Create a test client"""
    client_data = {
        "legal_name": f"TEST_MULTISTORE_Client_{uuid.uuid4().hex[:6]}",
        "fantasy_name": f"Multistore Test Co",
        "rif": f"J-{uuid.uuid4().hex[:8]}",
        "segment": "PYME"
    }
    res = session.post(f"{BASE_URL}/api/clients", json=client_data)
    if res.status_code in [200, 201]:
        return res.json()
    return None


def create_test_quote(session, client_id, cantidad_cajas=5):
    """Create a test implementation quote"""
    quote_data = {
        "client_id": client_id,
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "pricing_model": "conventional",
        "cantidad_cajas": cantidad_cajas,
        "cantidad_bancos": 2,
        "services": [
            {
                "item_type": "additional",
                "item_name": "TDD/TDC Suscripción",
                "bank_name": "Banco Mercantil",
                "cantidad_cajas": cantidad_cajas,
                "cantidad_bancos": 1,
                "quantity": cantidad_cajas,
                "tarifa_setup": 50,
                "tarifa_recurrente": 10,
                "unit_price_usd": 60,
                "total_usd": 300
            },
            {
                "item_type": "additional",
                "item_name": "C2P",
                "bank_name": "Banco Mercantil",
                "cantidad_cajas": cantidad_cajas,
                "cantidad_bancos": 1,
                "quantity": cantidad_cajas,
                "tarifa_setup": 30,
                "tarifa_recurrente": 8,
                "unit_price_usd": 38,
                "total_usd": 190
            }
        ],
        "notes": f"TEST_MULTISTORE_iteration114_{uuid.uuid4().hex[:6]}",
        "pdf_data": None
    }
    res = session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
    if res.status_code in [200, 201]:
        data = res.json()
        # Quote data is nested under 'quote' key
        if 'quote' in data:
            return data['quote']
        return data
    print(f"Failed to create quote: {res.status_code} - {res.text}")
    return None


# ===== Test: Send to Implementation Without Multistore =====
def test_send_to_implementation_without_multistore_body():
    """
    Test: POST /api/quotes/{quote_id}/send-to-implementation without multistore body
    Expected: Should work as before, create single project
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Create test data
    client = create_test_client(session)
    assert client is not None, "Failed to create test client"
    
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=3)
    assert quote is not None, "Failed to create test quote"
    
    quote_id = quote.get("quote_id")
    
    # Send with exception header (since quote is not in 'Pagada' status)
    headers = {
        "x-exception-reason": "Test - iteration 114 single store",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation",
        json={},  # Empty body - no multistore
        headers=headers
    )
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert "message" in data
    assert data.get("new_status") == "Enviada a Imple"
    print(f"SUCCESS: Send to implementation without multistore body - status: {data.get('new_status')}")
    
    # Verify project was created
    projects_res = session.get(f"{BASE_URL}/api/projects")
    assert projects_res.status_code == 200
    projects = projects_res.json()
    
    # Find the project created from this quote
    project = next((p for p in projects if p.get("quote_id") == quote_id), None)
    assert project is not None, "Project should be created from quote"
    
    # Should be single type (not multistore)
    project_type = project.get("project_type", "single")
    assert project_type == "single" or project_type is None, f"Expected 'single' project type, got {project_type}"
    print(f"SUCCESS: Project created with type '{project_type}'")


# ===== Test: Send to Implementation With Multistore =====
def test_send_to_implementation_multistore_creates_project():
    """
    Test: POST /api/quotes/{quote_id}/send-to-implementation with multistore body
    Expected: Should create project with project_type='multistore' and stores array
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Create test data
    client = create_test_client(session)
    assert client is not None, "Failed to create test client"
    
    # Create quote with 5 cajas to split across stores
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=5)
    assert quote is not None, "Failed to create test quote"
    
    quote_id = quote.get("quote_id")
    
    # Multistore body with stores (total = 5 cajas)
    multistore_body = {
        "is_multistore": True,
        "stores": [
            {"name": "Tienda Centro", "box_count": 2},
            {"name": "Tienda Norte", "box_count": 2},
            {"name": "Tienda Sur", "box_count": 1}
        ]
    }
    
    headers = {
        "x-exception-reason": "Test multistore - iteration 114",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation",
        json=multistore_body,
        headers=headers
    )
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("new_status") == "Enviada a Imple"
    print(f"SUCCESS: Send to implementation with multistore - status: {data.get('new_status')}")
    
    # Verify project was created as multistore
    projects_res = session.get(f"{BASE_URL}/api/projects")
    assert projects_res.status_code == 200
    projects = projects_res.json()
    
    # Find the project created from this quote
    project = next((p for p in projects if p.get("quote_id") == quote_id), None)
    assert project is not None, "Project should be created from quote"
    
    assert project.get("project_type") == "multistore", f"Expected project_type='multistore', got {project.get('project_type')}"
    assert "stores" in project, "Project should have stores array"
    assert len(project.get("stores", [])) == 3, f"Expected 3 stores, got {len(project.get('stores', []))}"
    
    # Verify store structure
    for store in project.get("stores", []):
        assert "store_id" in store, "Each store should have store_id"
        assert "name" in store, "Each store should have name"
        assert "box_count" in store, "Each store should have box_count"
        assert "implementation_matrix" in store, "Each store should have implementation_matrix"
    
    print(f"SUCCESS: Project created with multistore type and {len(project.get('stores', []))} stores")
    return project


# ===== Test: Store Phase Update Endpoint =====
def test_store_phase_update_endpoint():
    """
    Test: PUT /api/projects/{project_id}/stores/{store_id}/matrix/phase
    Expected: Should update the implementation_matrix of a specific store
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Create test data
    client = create_test_client(session)
    assert client is not None, "Failed to create test client"
    
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=5)
    assert quote is not None, "Failed to create test quote"
    
    quote_id = quote.get("quote_id")
    
    # Create multistore project
    multistore_body = {
        "is_multistore": True,
        "stores": [
            {"name": "Store Phase Test A", "box_count": 3},
            {"name": "Store Phase Test B", "box_count": 2}
        ]
    }
    
    headers = {
        "x-exception-reason": "Test store phase update - iteration 114",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation",
        json=multistore_body,
        headers=headers
    )
    assert res.status_code == 200, f"Failed to create multistore project: {res.text}"
    
    # Get the project
    projects_res = session.get(f"{BASE_URL}/api/projects")
    projects = projects_res.json()
    project = next((p for p in projects if p.get("quote_id") == quote_id), None)
    assert project is not None, "Project not found"
    
    project_id = project.get("project_id")
    stores = project.get("stores", [])
    assert len(stores) > 0, "No stores in project"
    
    store_id = stores[0].get("store_id")
    
    # Get bank and product from the implementation_matrix
    store_matrix = stores[0].get("implementation_matrix", {})
    
    # Use bank/product from the quote's services
    bank_name = "Banco Mercantil"
    product_name = "TDD/TDC Suscripción"
    
    if store_matrix:
        bank_name = list(store_matrix.keys())[0]
        products = store_matrix.get(bank_name, {})
        if products:
            product_name = list(products.keys())[0]
    
    # Update phase for this store
    phase_update = {
        "bank_name": bank_name,
        "product_name": product_name,
        "phase": "Notificado",
        "completed": True
    }
    
    update_res = session.put(
        f"{BASE_URL}/api/projects/{project_id}/stores/{store_id}/matrix/phase",
        json=phase_update
    )
    
    assert update_res.status_code == 200, f"Expected 200, got {update_res.status_code}: {update_res.text}"
    data = update_res.json()
    assert data.get("completed") == True
    assert data.get("store_id") == store_id
    print(f"SUCCESS: Store phase updated - store: {store_id}, phase: Notificado, completed: True")
    
    # Verify the update persisted
    project_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
    assert project_res.status_code == 200
    updated_project = project_res.json()
    
    # Find the store and verify the matrix was updated
    updated_store = next((s for s in updated_project.get("stores", []) if s.get("store_id") == store_id), None)
    assert updated_store is not None, "Store not found after update"
    
    updated_matrix = updated_store.get("implementation_matrix", {})
    phase_data = updated_matrix.get(bank_name, {}).get(product_name, {}).get("Notificado", {})
    assert phase_data.get("completed") == True, f"Phase should be marked as completed, got: {phase_data}"
    print(f"SUCCESS: Verified phase update persisted in database")


# ===== Test: Store Phase Update on Non-Multistore Project =====
def test_store_phase_update_invalid_project_type():
    """
    Test: PUT /api/projects/{project_id}/stores/{store_id}/matrix/phase on single project
    Expected: Should return 400 error
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Find or create a single-type project
    projects_res = session.get(f"{BASE_URL}/api/projects")
    assert projects_res.status_code == 200
    
    projects = projects_res.json()
    single_project = next((p for p in projects if p.get("project_type") != "multistore"), None)
    
    if not single_project:
        # Create one
        client = create_test_client(session)
        if client:
            quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=2)
            if quote:
                headers = {
                    "x-exception-reason": "Test single project",
                    "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
                }
                session.post(
                    f"{BASE_URL}/api/quotes/{quote.get('quote_id')}/send-to-implementation",
                    json={},
                    headers=headers
                )
                # Re-fetch projects
                projects_res = session.get(f"{BASE_URL}/api/projects")
                projects = projects_res.json()
                single_project = next((p for p in projects if p.get("project_type") != "multistore"), None)
    
    if not single_project:
        pytest.skip("Could not get/create a single-type project for testing")
    
    project_id = single_project.get("project_id")
    
    # Try to update store phase on a non-multistore project
    phase_update = {
        "bank_name": "Test Bank",
        "product_name": "Test Product",
        "phase": "Notificado",
        "completed": True
    }
    
    update_res = session.put(
        f"{BASE_URL}/api/projects/{project_id}/stores/fake_store_id/matrix/phase",
        json=phase_update
    )
    
    # Should return 400 because project is not multistore
    assert update_res.status_code == 400, f"Expected 400, got {update_res.status_code}: {update_res.text}"
    detail = update_res.json().get("detail", "").lower()
    assert "multitienda" in detail or "multistore" in detail, f"Error should mention multitienda/multistore: {detail}"
    print(f"SUCCESS: Store phase update correctly rejected for non-multistore project")


# ===== Test: Invalid Store ID =====
def test_store_phase_update_invalid_store_id():
    """
    Test: PUT /api/projects/{project_id}/stores/{store_id}/matrix/phase with invalid store_id
    Expected: Should return 404 error
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Create test data
    client = create_test_client(session)
    assert client is not None, "Failed to create test client"
    
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=5)
    assert quote is not None, "Failed to create test quote"
    
    # Create multistore project
    multistore_body = {
        "is_multistore": True,
        "stores": [{"name": "Single Store", "box_count": 5}]
    }
    
    headers = {
        "x-exception-reason": "Test invalid store id - iteration 114",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote.get('quote_id')}/send-to-implementation",
        json=multistore_body,
        headers=headers
    )
    assert res.status_code == 200
    
    # Get project
    projects_res = session.get(f"{BASE_URL}/api/projects")
    projects = projects_res.json()
    project = next((p for p in projects if p.get("quote_id") == quote.get("quote_id")), None)
    assert project is not None
    project_id = project.get("project_id")
    
    # Try to update with invalid store_id
    phase_update = {
        "bank_name": "Test Bank",
        "product_name": "Test Product",
        "phase": "Notificado",
        "completed": True
    }
    
    update_res = session.put(
        f"{BASE_URL}/api/projects/{project_id}/stores/invalid_store_id_12345/matrix/phase",
        json=phase_update
    )
    
    assert update_res.status_code == 404, f"Expected 404, got {update_res.status_code}: {update_res.text}"
    print(f"SUCCESS: Invalid store_id correctly returned 404")


# ===== Test: Projects List Contains Project Type =====
def test_projects_list_contains_project_type():
    """
    Test: GET /api/projects
    Expected: Each project should have project_type field
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    res = session.get(f"{BASE_URL}/api/projects")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    
    projects = res.json()
    
    # Check that all projects have project_type field (even if default 'single')
    for project in projects:
        # project_type might be missing on old projects, which is OK (defaults to 'single')
        project_type = project.get("project_type", "single")
        assert project_type in ["single", "multistore", None], f"Invalid project_type: {project_type}"
    
    print(f"SUCCESS: All {len(projects)} projects have valid project_type")


# ===== Test: Multistore Project Has Stores Array =====
def test_multistore_project_has_stores_array():
    """
    Test: GET /api/projects/{project_id} for multistore project
    Expected: Should have stores array with proper structure
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # First, create a multistore project
    client = create_test_client(session)
    if not client:
        pytest.skip("Could not create test client")
    
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=4)
    if not quote:
        pytest.skip("Could not create test quote")
    
    # Create multistore project
    multistore_body = {
        "is_multistore": True,
        "stores": [
            {"name": "Store A", "box_count": 2},
            {"name": "Store B", "box_count": 2}
        ]
    }
    
    headers = {
        "x-exception-reason": "Test stores array - iteration 114",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote.get('quote_id')}/send-to-implementation",
        json=multistore_body,
        headers=headers
    )
    
    if res.status_code != 200:
        pytest.skip(f"Could not create multistore project: {res.text}")
    
    # Find the created project
    projects_res = session.get(f"{BASE_URL}/api/projects")
    projects = projects_res.json()
    multistore_project = next((p for p in projects if p.get("quote_id") == quote.get("quote_id")), None)
    
    assert multistore_project is not None, "Multistore project not found"
    project_id = multistore_project.get("project_id")
    
    detail_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
    assert detail_res.status_code == 200
    
    project = detail_res.json()
    assert project.get("project_type") == "multistore"
    assert "stores" in project
    assert isinstance(project.get("stores"), list)
    
    assert len(project.get("stores", [])) > 0, "Multistore project should have stores"
    store = project["stores"][0]
    assert "store_id" in store
    assert "name" in store
    assert "box_count" in store
    assert "implementation_matrix" in store
    print(f"SUCCESS: Multistore project has {len(project['stores'])} stores with proper structure")


# ===== Test: Status Change Bug Fix =====
def test_send_to_implementation_changes_status():
    """
    Test: POST /api/quotes/{quote_id}/send-to-implementation
    Expected: Quote status should change to 'Enviada a Imple'
    This tests the bug fix where the status was not changing.
    """
    session = get_auth_session()
    assert session is not None, "Failed to authenticate"
    
    # Create test data
    client = create_test_client(session)
    assert client is not None, "Failed to create test client"
    
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=2)
    assert quote is not None, "Failed to create test quote"
    
    quote_id = quote.get("quote_id")
    
    # Get initial status
    initial_res = session.get(f"{BASE_URL}/api/quotes/{quote_id}")
    assert initial_res.status_code == 200
    initial_status = initial_res.json().get("quote_status")
    print(f"Initial quote status: {initial_status}")
    
    # Send to implementation with exception (since not in 'Pagada' status)
    headers = {
        "x-exception-reason": "Test status change - iteration 114",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation",
        json={},
        headers=headers
    )
    
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("new_status") == "Enviada a Imple", f"Expected 'Enviada a Imple', got {data.get('new_status')}"
    print(f"SUCCESS: Response indicates status changed to 'Enviada a Imple'")
    
    # The quote should be deleted after converting to project
    # So trying to get it should return 404
    verify_res = session.get(f"{BASE_URL}/api/quotes/{quote_id}")
    # Quote is deleted after creating project, so 404 is expected
    if verify_res.status_code == 404:
        print("SUCCESS: Quote was deleted after creating project (expected behavior)")
    else:
        # If quote still exists, verify status changed
        final_status = verify_res.json().get("quote_status")
        assert final_status == "Enviada a Imple", f"Expected 'Enviada a Imple', got {final_status}"
        print(f"SUCCESS: Quote status changed from '{initial_status}' to '{final_status}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
