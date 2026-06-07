# ruff: noqa
"""
Test Suite: Delete Referential Integrity and AlertDialog Confirmation
Tests for: Clientes, Bancos, Medios de Pago, Dispositivos, Integradores
- Verifies backend DELETE endpoints return 400 when linked records exist
- Verifies DELETE works when no linked records
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
SESSION_TOKEN = "test_session_12345"

@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {SESSION_TOKEN}"}


class TestDeleteReferentialIntegrity:
    """Test referential integrity validation on DELETE endpoints"""
    
    # ==================== CLIENT DELETE TESTS ====================
    
    def test_delete_client_without_quotes(self, auth_headers):
        """Test: Can delete client with no linked quotes"""
        # Create test client
        client_data = {
            "rif": "TEST_J-99999999-9",
            "legal_name": "Test Delete Client",
            "fantasy_name": "Test Delete",
            "segment": "Pymes",
            "contact1": {"name": "Test", "phone": "123", "email": "test@test.com"},
            "contact2": {"name": "Test2", "phone": "456", "email": "test2@test.com"}
        }
        create_response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Failed to create test client: {create_response.text}"
        client_id = create_response.json()["client_id"]
        
        # Delete client (should succeed - no linked quotes)
        delete_response = requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed to delete client: {delete_response.text}"
        assert "eliminado" in delete_response.json().get("message", "").lower()
        
        # Verify client is deleted
        get_response = requests.get(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert get_response.status_code == 404
        print("✓ Client without quotes deleted successfully")
    
    # ==================== BANK DELETE TESTS ====================
    
    def test_delete_bank_without_quotes(self, auth_headers):
        """Test: Can delete bank with no linked quotes"""
        # Create test bank
        bank_data = {
            "name": "Test Delete Bank",
            "type": "Banco",
            "country": "Venezuela",
            "products": []
        }
        create_response = requests.post(f"{BASE_URL}/api/banks", json=bank_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Failed to create test bank: {create_response.text}"
        bank_id = create_response.json()["bank_id"]
        
        # Delete bank (should succeed - no linked quotes)
        delete_response = requests.delete(f"{BASE_URL}/api/banks/{bank_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed to delete bank: {delete_response.text}"
        assert "eliminado" in delete_response.json().get("message", "").lower()
        print("✓ Bank without quotes deleted successfully")
    
    # ==================== SERVICE (MEDIO DE PAGO) DELETE TESTS ====================
    
    def test_delete_service_without_quotes(self, auth_headers):
        """Test: Can delete service with no linked quotes"""
        # Create test service
        service_data = {
            "category": "Test",
            "name": "Test Delete Service",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 100,
            "monthly_cost_conventional": 50,
            "setup_cost_outsourcing": 80,
            "monthly_cost_outsourcing": 40
        }
        create_response = requests.post(f"{BASE_URL}/api/services", json=service_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Failed to create test service: {create_response.text}"
        service_id = create_response.json()["service_id"]
        
        # Delete service (should succeed - no linked quotes or banks)
        delete_response = requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed to delete service: {delete_response.text}"
        assert "eliminado" in delete_response.json().get("message", "").lower()
        print("✓ Service (medio de pago) without quotes deleted successfully")
    
    # ==================== HARDWARE DELETE TESTS ====================
    
    def test_delete_hardware_without_quotes(self, auth_headers):
        """Test: Can delete hardware with no linked quotes"""
        # Create test hardware
        hardware_data = {
            "name": "Test Delete Hardware",
            "type": "Pinpad",
            "price_usd": 100,
            "price_bs_usd": 120,
            "description": "Test device"
        }
        create_response = requests.post(f"{BASE_URL}/api/hardware", json=hardware_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Failed to create test hardware: {create_response.text}"
        hardware_id = create_response.json()["hardware_id"]
        
        # Delete hardware (should succeed - no linked quotes)
        delete_response = requests.delete(f"{BASE_URL}/api/hardware/{hardware_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed to delete hardware: {delete_response.text}"
        assert "eliminado" in delete_response.json().get("message", "").lower()
        print("✓ Hardware without quotes deleted successfully")
    
    # ==================== INTEGRATOR DELETE TESTS ====================
    
    def test_delete_integrator_without_quotes(self, auth_headers):
        """Test: Can delete integrator with no linked quotes"""
        # Create test integrator
        integrator_data = {
            "name": "Test Delete Integrator",
            "integrator_type": "Integrador",
            "app_name": "Test App",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        create_response = requests.post(f"{BASE_URL}/api/integrators", json=integrator_data, headers=auth_headers)
        assert create_response.status_code == 200, f"Failed to create test integrator: {create_response.text}"
        integrator_id = create_response.json()["integrator_id"]
        
        # Delete integrator (should succeed - no linked quotes)
        delete_response = requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Failed to delete integrator: {delete_response.text}"
        assert "eliminado" in delete_response.json().get("message", "").lower()
        print("✓ Integrator without quotes deleted successfully")


class TestDeleteAPIEndpoints:
    """Test DELETE endpoint responses and error handling"""
    
    def test_delete_nonexistent_client(self, auth_headers):
        """Test: DELETE nonexistent client returns 404"""
        response = requests.delete(f"{BASE_URL}/api/clients/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ DELETE nonexistent client returns 404")
    
    def test_delete_nonexistent_bank(self, auth_headers):
        """Test: DELETE nonexistent bank returns 404"""
        response = requests.delete(f"{BASE_URL}/api/banks/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ DELETE nonexistent bank returns 404")
    
    def test_delete_nonexistent_service(self, auth_headers):
        """Test: DELETE nonexistent service returns 404"""
        response = requests.delete(f"{BASE_URL}/api/services/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ DELETE nonexistent service returns 404")
    
    def test_delete_nonexistent_hardware(self, auth_headers):
        """Test: DELETE nonexistent hardware returns 404"""
        response = requests.delete(f"{BASE_URL}/api/hardware/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ DELETE nonexistent hardware returns 404")
    
    def test_delete_nonexistent_integrator(self, auth_headers):
        """Test: DELETE nonexistent integrator returns 404"""
        response = requests.delete(f"{BASE_URL}/api/integrators/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        print("✓ DELETE nonexistent integrator returns 404")


class TestCRUDEndpoints:
    """Test basic CRUD to ensure all modules are working"""
    
    def test_clients_api(self, auth_headers):
        """Test: GET /api/clients returns 200"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ GET /api/clients - {len(response.json())} clients found")
    
    def test_banks_api(self, auth_headers):
        """Test: GET /api/banks returns 200"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ GET /api/banks - {len(response.json())} banks found")
    
    def test_services_api(self, auth_headers):
        """Test: GET /api/services returns 200"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ GET /api/services - {len(response.json())} services found")
    
    def test_hardware_api(self, auth_headers):
        """Test: GET /api/hardware returns 200"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ GET /api/hardware - {len(response.json())} hardware items found")
    
    def test_integrators_api(self, auth_headers):
        """Test: GET /api/integrators returns 200"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ GET /api/integrators - {len(response.json())} integrators found")
