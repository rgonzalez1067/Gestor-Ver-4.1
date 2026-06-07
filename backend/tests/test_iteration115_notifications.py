# ruff: noqa
"""
Test Iteration 115: Notification Hierarchy & Multistore Matrix Flow
Tests the new notification system and matrix blocking/unlocking logic.

Features tested:
- POST /api/projects/{id}/notify-client - Mark client_notified=true, send simulated email
- POST /api/projects/{id}/notify-bank - Consolidated bank notification (one per bank)
- PUT /api/projects/{id}/matrix/phase - Matrix updates with hard stop validation
- PUT /api/projects/{id}/stores/{store_id}/matrix/phase - Store phases (no "Notificado")
- GET /api/projects/{id}/rollup - Rollup calculation for multistore
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
        "legal_name": f"TEST_NOTIFICATION_Client_{uuid.uuid4().hex[:6]}",
        "fantasy_name": "Notification Test Co",
        "rif": f"J-{uuid.uuid4().hex[:8]}",
        "segment": "PYME",
        "email": "testclient@example.com"
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
            },
            {
                "item_type": "additional",
                "item_name": "QR Pago Móvil",
                "bank_name": "Banesco",
                "cantidad_cajas": cantidad_cajas,
                "cantidad_bancos": 1,
                "quantity": cantidad_cajas,
                "tarifa_setup": 40,
                "tarifa_recurrente": 5,
                "unit_price_usd": 45,
                "total_usd": 225
            }
        ],
        "notes": f"TEST_NOTIFICATION_iteration115_{uuid.uuid4().hex[:6]}",
        "pdf_data": None
    }
    res = session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
    if res.status_code in [200, 201]:
        data = res.json()
        if 'quote' in data:
            return data['quote']
        return data
    print(f"Failed to create quote: {res.status_code} - {res.text}")
    return None


def create_single_project(session, client):
    """Create a single-type project"""
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=3)
    if not quote:
        return None
    
    headers = {
        "x-exception-reason": "Test notification - iteration 115 single",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote.get('quote_id')}/send-to-implementation",
        json={},
        headers=headers
    )
    
    if res.status_code == 200:
        projects_res = session.get(f"{BASE_URL}/api/projects")
        projects = projects_res.json()
        return next((p for p in projects if p.get("quote_id") == quote.get("quote_id")), None)
    return None


def create_multistore_project(session, client):
    """Create a multistore-type project"""
    quote = create_test_quote(session, client.get("client_id"), cantidad_cajas=5)
    if not quote:
        return None
    
    multistore_body = {
        "is_multistore": True,
        "stores": [
            {"name": "Tienda Centro", "box_count": 2},
            {"name": "Tienda Norte", "box_count": 2},
            {"name": "Tienda Sur", "box_count": 1}
        ]
    }
    
    headers = {
        "x-exception-reason": "Test notification - iteration 115 multistore",
        "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
    }
    
    res = session.post(
        f"{BASE_URL}/api/quotes/{quote.get('quote_id')}/send-to-implementation",
        json=multistore_body,
        headers=headers
    )
    
    if res.status_code == 200:
        projects_res = session.get(f"{BASE_URL}/api/projects")
        projects = projects_res.json()
        return next((p for p in projects if p.get("quote_id") == quote.get("quote_id")), None)
    return None


# ==================== NOTIFY CLIENT TESTS ====================

class TestNotifyClient:
    """Tests for POST /api/projects/{id}/notify-client"""
    
    def test_notify_client_success(self):
        """Notify client should mark client_notified=true and return success"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        assert client is not None, "Failed to create test client"
        
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        
        # Verify client_notified is initially false
        assert project.get("client_notified") in [False, None], "client_notified should be false initially"
        
        # Notify client
        res = session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data.get("client_notified") == True
        assert "message" in data
        print(f"SUCCESS: notify-client returned: {data.get('message')}")
        
        # Verify persistence - GET project and check client_notified
        project_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_res.status_code == 200
        updated_project = project_res.json()
        
        assert updated_project.get("client_notified") == True, "client_notified should be persisted as True"
        assert updated_project.get("client_notified_at") is not None, "client_notified_at should be set"
        print(f"SUCCESS: client_notified persisted. Notified at: {updated_project.get('client_notified_at')}")
    
    def test_notify_client_already_notified_returns_400(self):
        """Attempting to notify client again should return 400"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        
        # First notification
        res1 = session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        assert res1.status_code == 200
        
        # Second notification should fail
        res2 = session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        assert res2.status_code == 400, f"Expected 400, got {res2.status_code}: {res2.text}"
        
        detail = res2.json().get("detail", "").lower()
        assert "ya" in detail or "already" in detail, f"Error should mention already notified: {detail}"
        print("SUCCESS: Double notification correctly rejected with 400")
    
    def test_notify_client_invalid_project_returns_404(self):
        """Notify client on non-existent project should return 404"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        res = session.post(f"{BASE_URL}/api/projects/nonexistent_project_12345/notify-client")
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("SUCCESS: Invalid project returns 404")


# ==================== NOTIFY BANK TESTS ====================

class TestNotifyBank:
    """Tests for POST /api/projects/{id}/notify-bank"""
    
    def test_notify_bank_requires_client_notified(self):
        """Notify bank should fail if client hasn't been notified first"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0] if matrix else "Banco Mercantil"
        
        # Try to notify bank without notifying client first
        res = session.post(
            f"{BASE_URL}/api/projects/{project_id}/notify-bank",
            json={"bank_name": bank_name}
        )
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "").lower()
        assert "cliente" in detail or "client" in detail, f"Error should mention client: {detail}"
        print("SUCCESS: Bank notification correctly blocked - client not notified first")
    
    def test_notify_bank_success_after_client_notified(self):
        """Notify bank should work after client is notified"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0] if matrix else "Banco Mercantil"
        
        # First notify client
        client_res = session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        assert client_res.status_code == 200, "Failed to notify client"
        
        # Now notify bank
        bank_res = session.post(
            f"{BASE_URL}/api/projects/{project_id}/notify-bank",
            json={"bank_name": bank_name}
        )
        
        assert bank_res.status_code == 200, f"Expected 200, got {bank_res.status_code}: {bank_res.text}"
        data = bank_res.json()
        
        assert data.get("bank_name") == bank_name
        assert "products_notified" in data
        assert len(data.get("products_notified", [])) > 0, "Should have products notified"
        print(f"SUCCESS: Bank '{bank_name}' notified with products: {data.get('products_notified')}")
        
        # Verify persistence
        project_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = project_res.json()
        bank_notifications = updated_project.get("bank_notifications", {})
        
        assert bank_name in bank_notifications, "Bank should be in bank_notifications"
        assert bank_notifications[bank_name].get("notified_at") is not None
        print("SUCCESS: Bank notification persisted")
    
    def test_notify_bank_already_notified_returns_400(self):
        """Attempting to notify same bank again should return 400"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0] if matrix else "Banco Mercantil"
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # First bank notification
        res1 = session.post(
            f"{BASE_URL}/api/projects/{project_id}/notify-bank",
            json={"bank_name": bank_name}
        )
        assert res1.status_code == 200
        
        # Second bank notification should fail
        res2 = session.post(
            f"{BASE_URL}/api/projects/{project_id}/notify-bank",
            json={"bank_name": bank_name}
        )
        
        assert res2.status_code == 400, f"Expected 400, got {res2.status_code}: {res2.text}"
        detail = res2.json().get("detail", "").lower()
        assert "ya" in detail or "already" in detail, f"Error should mention already: {detail}"
        print("SUCCESS: Double bank notification correctly rejected")
    
    def test_notify_bank_invalid_bank_returns_404(self):
        """Notify non-existent bank should return 404"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # Try invalid bank
        res = session.post(
            f"{BASE_URL}/api/projects/{project_id}/notify-bank",
            json={"bank_name": "Banco Inexistente XYZ"}
        )
        
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"
        print("SUCCESS: Invalid bank returns 404")


# ==================== MATRIX PHASE UPDATE TESTS (SINGLE) ====================

class TestMatrixPhaseUpdateSingle:
    """Tests for PUT /api/projects/{id}/matrix/phase (single projects)"""
    
    def test_matrix_phase_blocked_without_client_notification(self):
        """Matrix phase update should fail if client hasn't been notified"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Try to update phase without client notification
        res = session.put(
            f"{BASE_URL}/api/projects/{project_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Recibido",
                "completed": True
            }
        )
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "").lower()
        assert "cliente" in detail or "client" in detail or "notificar" in detail, f"Error: {detail}"
        print("SUCCESS: Matrix update blocked - client not notified (Hard Stop working)")
    
    def test_matrix_phase_works_after_client_notification(self):
        """Matrix phase update should work after client is notified"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # First notify client
        client_res = session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        assert client_res.status_code == 200
        
        # Now update phase
        res = session.put(
            f"{BASE_URL}/api/projects/{project_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Recibido",
                "completed": True
            }
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("completed") == True
        print("SUCCESS: Matrix phase updated after client notification")
        
        # Verify persistence
        project_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = project_res.json()
        updated_matrix = updated_project.get("implementation_matrix", {})
        phase_data = updated_matrix.get(bank_name, {}).get(product_name, {}).get("Recibido", {})
        
        assert phase_data.get("completed") == True, "Phase update should persist"
        print("SUCCESS: Phase update persisted")
    
    def test_matrix_phase_blocked_for_multistore(self):
        """Matrix phase update should fail for multistore projects (read-only)"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        matrix = project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0] if matrix else "Banco Mercantil"
        products = matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "TDD/TDC Suscripción"
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # Try to update main matrix (should fail for multistore)
        res = session.put(
            f"{BASE_URL}/api/projects/{project_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Recibido",
                "completed": True
            }
        )
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "").lower()
        assert "multitienda" in detail or "multistore" in detail or "solo lectura" in detail or "read" in detail, f"Error: {detail}"
        print("SUCCESS: Main matrix update blocked for multistore project (read-only)")


# ==================== STORE MATRIX PHASE UPDATE TESTS (MULTISTORE) ====================

class TestStoreMatrixPhaseUpdate:
    """Tests for PUT /api/projects/{id}/stores/{store_id}/matrix/phase"""
    
    def test_store_phase_blocked_without_client_notification(self):
        """Store phase update should fail if client hasn't been notified"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        stores = project.get("stores", [])
        assert len(stores) > 0, "Project should have stores"
        
        store = stores[0]
        store_id = store.get("store_id")
        store_matrix = store.get("implementation_matrix", {})
        bank_name = list(store_matrix.keys())[0] if store_matrix else "Banco Mercantil"
        products = store_matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "TDD/TDC Suscripción"
        
        # Try to update store phase without client notification
        res = session.put(
            f"{BASE_URL}/api/projects/{project_id}/stores/{store_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Recibido",
                "completed": True
            }
        )
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "").lower()
        assert "cliente" in detail or "client" in detail or "notificar" in detail, f"Error: {detail}"
        print("SUCCESS: Store phase update blocked - client not notified")
    
    def test_store_phase_rejects_notificado_phase(self):
        """Store phase update should reject 'Notificado' as a valid phase"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        stores = project.get("stores", [])
        store = stores[0]
        store_id = store.get("store_id")
        store_matrix = store.get("implementation_matrix", {})
        bank_name = list(store_matrix.keys())[0] if store_matrix else "Banco Mercantil"
        products = store_matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "TDD/TDC Suscripción"
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # Try to use "Notificado" phase (not valid for stores)
        res = session.put(
            f"{BASE_URL}/api/projects/{project_id}/stores/{store_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Notificado",  # Invalid for stores
                "completed": True
            }
        )
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "").lower()
        assert "fase" in detail or "phase" in detail or "inválid" in detail or "invalid" in detail, f"Error: {detail}"
        print("SUCCESS: 'Notificado' phase correctly rejected for store matrix")
    
    def test_store_phase_accepts_valid_phases(self):
        """Store phase update should accept valid STORE_PHASES"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        stores = project.get("stores", [])
        store = stores[0]
        store_id = store.get("store_id")
        store_matrix = store.get("implementation_matrix", {})
        bank_name = list(store_matrix.keys())[0] if store_matrix else "Banco Mercantil"
        products = store_matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "TDD/TDC Suscripción"
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # Test all valid STORE_PHASES: Recibido, Configurado, Testeado, En Producción
        valid_phases = ["Recibido", "Configurado", "Testeado", "En Producción"]
        
        for phase in valid_phases:
            res = session.put(
                f"{BASE_URL}/api/projects/{project_id}/stores/{store_id}/matrix/phase",
                json={
                    "bank_name": bank_name,
                    "product_name": product_name,
                    "phase": phase,
                    "completed": True
                }
            )
            
            assert res.status_code == 200, f"Expected 200 for phase '{phase}', got {res.status_code}: {res.text}"
            print(f"SUCCESS: Phase '{phase}' accepted for store matrix")
    
    def test_store_phase_triggers_rollup_recalculation(self):
        """Store phase update should recalculate rollup_progress"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        stores = project.get("stores", [])
        store = stores[0]
        store_id = store.get("store_id")
        store_matrix = store.get("implementation_matrix", {})
        bank_name = list(store_matrix.keys())[0] if store_matrix else "Banco Mercantil"
        products = store_matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "TDD/TDC Suscripción"
        
        # Notify client first
        session.post(f"{BASE_URL}/api/projects/{project_id}/notify-client")
        
        # Check initial rollup_progress (may be None or empty dict initially)
        initial_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        initial_project = initial_res.json()
        initial_rollup = initial_project.get("rollup_progress") or {}
        initial_global = initial_rollup.get("global_progress", 0) if initial_rollup else 0
        
        # Update a phase
        session.put(
            f"{BASE_URL}/api/projects/{project_id}/stores/{store_id}/matrix/phase",
            json={
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": "Recibido",
                "completed": True
            }
        )
        
        # Check updated rollup_progress
        updated_res = session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = updated_res.json()
        updated_rollup = updated_project.get("rollup_progress") or {}
        updated_global = updated_rollup.get("global_progress", 0) if updated_rollup else 0
        
        # Rollup should be calculated after a phase update - should have data now
        assert updated_rollup is not None, "rollup_progress should exist after phase update"
        assert "global_progress" in updated_rollup, "Should have global_progress calculated"
        # Progress should have increased (or at minimum stay the same if already complete)
        assert updated_global >= initial_global, f"Progress should increase: {initial_global} -> {updated_global}"
        print(f"SUCCESS: Rollup recalculated: {initial_global}% -> {updated_global}%")


# ==================== ROLLUP ENDPOINT TESTS ====================

class TestRollupEndpoint:
    """Tests for GET /api/projects/{id}/rollup"""
    
    def test_rollup_returns_data_for_multistore(self):
        """Rollup endpoint should return progress data for multistore projects"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_multistore_project(session, client)
        assert project is not None, "Failed to create multistore project"
        
        project_id = project.get("project_id")
        
        res = session.get(f"{BASE_URL}/api/projects/{project_id}/rollup")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "global_progress" in data, "Should have global_progress"
        assert "bank_progress" in data, "Should have bank_progress"
        assert isinstance(data.get("bank_progress"), dict), "bank_progress should be dict"
        
        print(f"SUCCESS: Rollup data returned: global={data.get('global_progress')}%, banks={list(data.get('bank_progress', {}).keys())}")
    
    def test_rollup_rejects_single_projects(self):
        """Rollup endpoint should reject single (non-multistore) projects"""
        session = get_auth_session()
        assert session is not None, "Failed to authenticate"
        
        client = create_test_client(session)
        project = create_single_project(session, client)
        assert project is not None, "Failed to create single project"
        
        project_id = project.get("project_id")
        
        res = session.get(f"{BASE_URL}/api/projects/{project_id}/rollup")
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        
        detail = res.json().get("detail", "").lower()
        assert "multitienda" in detail or "multistore" in detail, f"Error should mention multitienda: {detail}"
        print("SUCCESS: Rollup correctly rejected for single project")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
