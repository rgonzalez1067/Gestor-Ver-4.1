# ruff: noqa
"""
Iteration 69 - Service Type Feature Tests
Tests for mandatory 'Tipo' field (Producto/Servicio) in Medios de Pago catalog.
- Producto = tangible (Pinpads, Cables)
- Servicio = intangible (Mantenimiento, Licencia)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestServiceTypeCreate:
    """Tests for POST /api/services with service_type field"""
    
    def test_create_service_with_type_producto(self, auth_headers):
        """Test creating a service with service_type='Producto'"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "category": "General",
            "name": f"TEST_Pinpad Modelo {unique_id}",
            "service_type": "Producto",
            "application_type": "setup",
            "setup_cost_conventional": 100.0,
            "monthly_cost_conventional": 0,
            "description": "Test Producto - Tangible item"
        }
        
        response = requests.post(f"{BASE_URL}/api/services", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["service_type"] == "Producto", f"Expected 'Producto', got '{data.get('service_type')}'"
        assert data["name"] == payload["name"]
        
        # Cleanup
        service_id = data["service_id"]
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=auth_headers)
        print("✅ Created service with service_type='Producto' successfully")
    
    def test_create_service_with_type_servicio(self, auth_headers):
        """Test creating a service with service_type='Servicio'"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "category": "General",
            "name": f"TEST_Mantenimiento {unique_id}",
            "service_type": "Servicio",
            "application_type": "recurring",
            "setup_cost_conventional": 0,
            "monthly_cost_conventional": 50.0,
            "description": "Test Servicio - Intangible item"
        }
        
        response = requests.post(f"{BASE_URL}/api/services", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["service_type"] == "Servicio", f"Expected 'Servicio', got '{data.get('service_type')}'"
        assert data["name"] == payload["name"]
        
        # Cleanup
        service_id = data["service_id"]
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=auth_headers)
        print("✅ Created service with service_type='Servicio' successfully")
    
    def test_create_service_without_type_defaults_to_servicio(self, auth_headers):
        """Test that creating a service without service_type defaults to 'Servicio'"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "category": "General",
            "name": f"TEST_DefaultType {unique_id}",
            "application_type": "both",
            "setup_cost_conventional": 25.0,
            "monthly_cost_conventional": 10.0,
            # service_type is NOT provided
        }
        
        response = requests.post(f"{BASE_URL}/api/services", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["service_type"] == "Servicio", f"Expected default 'Servicio', got '{data.get('service_type')}'"
        
        # Cleanup
        service_id = data["service_id"]
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=auth_headers)
        print("✅ Default service_type='Servicio' applied correctly")


class TestServiceTypeRead:
    """Tests for GET /api/services returning service_type field"""
    
    def test_get_services_returns_service_type(self, auth_headers):
        """Test that GET /api/services returns service_type for all services"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        services = response.json()
        assert isinstance(services, list), "Expected list of services"
        assert len(services) > 0, "Expected at least one service in the database"
        
        # Check that all services have service_type field (either Producto or Servicio)
        for service in services[:10]:  # Check first 10
            assert "service_type" in service, f"service_type missing in service {service.get('name')}"
            assert service["service_type"] in ["Producto", "Servicio"], \
                f"Invalid service_type: {service.get('service_type')}"
        
        print(f"✅ GET /api/services returns service_type field for {len(services)} services")


class TestServiceTypeUpdate:
    """Tests for PUT /api/services/{id} updating service_type field"""
    
    def test_update_service_type(self, auth_headers):
        """Test updating service_type from Servicio to Producto"""
        unique_id = uuid.uuid4().hex[:8]
        
        # Create a service with service_type='Servicio'
        create_payload = {
            "category": "General",
            "name": f"TEST_UpdateType {unique_id}",
            "service_type": "Servicio",
            "application_type": "both",
            "setup_cost_conventional": 50.0,
            "monthly_cost_conventional": 20.0
        }
        
        create_response = requests.post(f"{BASE_URL}/api/services", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created_service = create_response.json()
        service_id = created_service["service_id"]
        
        # Update service_type to 'Producto'
        update_payload = {
            "category": "General",
            "name": create_payload["name"],
            "service_type": "Producto",
            "application_type": "setup",
            "setup_cost_conventional": 75.0,
            "monthly_cost_conventional": 0
        }
        
        update_response = requests.put(f"{BASE_URL}/api/services/{service_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated_service = update_response.json()
        assert updated_service["service_type"] == "Producto", \
            f"Expected 'Producto' after update, got '{updated_service.get('service_type')}'"
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        services = get_response.json()
        found_service = next((s for s in services if s["service_id"] == service_id), None)
        assert found_service is not None, "Updated service not found in GET"
        assert found_service["service_type"] == "Producto", "Update not persisted correctly"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=auth_headers)
        print("✅ service_type updated from 'Servicio' to 'Producto' successfully")


class TestServiceTypeCountsAndDistribution:
    """Test service_type distribution in the database"""
    
    def test_services_have_valid_types(self, auth_headers):
        """Verify all services have valid service_type values"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200
        
        services = response.json()
        producto_count = sum(1 for s in services if s.get("service_type") == "Producto")
        servicio_count = sum(1 for s in services if s.get("service_type") == "Servicio")
        other_count = len(services) - producto_count - servicio_count
        
        print("Service type distribution:")
        print(f"  - Producto: {producto_count}")
        print(f"  - Servicio: {servicio_count}")
        print(f"  - Other/None: {other_count}")
        
        # All services should have either Producto or Servicio (or default to Servicio)
        assert other_count == 0, f"Found {other_count} services with invalid/missing service_type"
        print(f"✅ All {len(services)} services have valid service_type values")


class TestServiceTypeCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_services(self, auth_headers):
        """Clean up any remaining TEST_ services"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        if response.status_code == 200:
            services = response.json()
            test_services = [s for s in services if s.get("name", "").startswith("TEST_")]
            
            for service in test_services:
                delete_response = requests.delete(
                    f"{BASE_URL}/api/services/{service['service_id']}", 
                    headers=auth_headers
                )
                if delete_response.status_code == 200:
                    print(f"  Cleaned up: {service['name']}")
            
            print(f"✅ Cleanup completed: {len(test_services)} test services removed")
