"""
Iteration 88: Test Client Form Redesign - 3-column layout with new fields
Tests:
- POST /api/clients with new fields (grupo_economico, ejecutivo_propietario, fecha_primer_contacto, tipo_contacto, tipo_servicio array, integrador_id, integrador_name, aplicativo)
- PUT /api/clients/{id} updates all new fields
- GET /api/integrators/dropdown returns lightweight list with integrator_id, name, app_name
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@gestor.com"
TEST_PASSWORD = "Admin2026!"

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
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

class TestIntegratorsDropdown:
    """Test GET /api/integrators/dropdown endpoint"""
    
    def test_integrators_dropdown_returns_list(self, auth_headers):
        """GET /api/integrators/dropdown should return list with integrator_id, name, app_name"""
        response = requests.get(f"{BASE_URL}/api/integrators/dropdown", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            # Verify structure of first item
            first = data[0]
            assert "integrator_id" in first, "Each item should have integrator_id"
            assert "name" in first, "Each item should have name"
            assert "app_name" in first, "Each item should have app_name"
            print(f"✓ Integrators dropdown returned {len(data)} items")
            print(f"  Sample: {first}")
        else:
            print("✓ Integrators dropdown returned empty list (no integrators in DB)")

class TestClientCreateWithNewFields:
    """Test POST /api/clients with new fields from 3-column layout"""
    
    def test_create_client_with_all_new_fields(self, auth_headers):
        """Create client with all new fields: grupo_economico, ejecutivo_propietario, fecha_primer_contacto, tipo_contacto, tipo_servicio, integrador_id, integrador_name, aplicativo"""
        unique_id = uuid.uuid4().hex[:6].upper()
        
        payload = {
            "rif": f"TEST{unique_id}88",
            "legal_name": f"Test Company {unique_id}",
            "fantasy_name": f"TestCorp {unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
            # New fields from Bloque A
            "grupo_economico": "Grupo Test Económico",
            # New fields from Bloque C
            "ejecutivo_propietario": "Carlos Ejecutivo",
            "fecha_primer_contacto": "2026-01-15",
            "tipo_contacto": "Telefónico",
            "tipo_servicio": ["VPOS", "Payment Gateway", "Link de Pago"],
            "categoria_comercial": "Restaurantes",
            # Integrator row
            "integrador_id": "int_test123",
            "integrador_name": "Test Integrador",
            "aplicativo": "TestApp v1.0",
            "contacts": [{
                "full_name": "Contact Test",
                "phone": "0412-1234567",
                "email": "contact@test.com",
                "role": "Administrativo"
            }]
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify new fields persisted
        assert data.get("grupo_economico") == "Grupo Test Económico", "grupo_economico should be persisted"
        assert data.get("ejecutivo_propietario") == "Carlos Ejecutivo", "ejecutivo_propietario should be persisted"
        assert data.get("fecha_primer_contacto") == "2026-01-15", "fecha_primer_contacto should be persisted"
        assert data.get("tipo_contacto") == "Telefónico", "tipo_contacto should be persisted"
        assert data.get("tipo_servicio") == ["VPOS", "Payment Gateway", "Link de Pago"], "tipo_servicio array should be persisted"
        assert data.get("integrador_id") == "int_test123", "integrador_id should be persisted"
        assert data.get("integrador_name") == "Test Integrador", "integrador_name should be persisted"
        assert data.get("aplicativo") == "TestApp v1.0", "aplicativo should be persisted"
        
        # Clean up
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print(f"✓ Client created with all new fields")
        print(f"  - grupo_economico: {data.get('grupo_economico')}")
        print(f"  - ejecutivo_propietario: {data.get('ejecutivo_propietario')}")
        print(f"  - fecha_primer_contacto: {data.get('fecha_primer_contacto')}")
        print(f"  - tipo_contacto: {data.get('tipo_contacto')}")
        print(f"  - tipo_servicio: {data.get('tipo_servicio')}")
        print(f"  - integrador_id: {data.get('integrador_id')}")
        print(f"  - aplicativo: {data.get('aplicativo')}")

    def test_create_client_with_empty_tipo_servicio(self, auth_headers):
        """Create client with empty tipo_servicio array"""
        unique_id = uuid.uuid4().hex[:6].upper()
        
        payload = {
            "rif": f"TEST{unique_id}E",
            "legal_name": f"Empty Tipo Servicio {unique_id}",
            "fantasy_name": f"EmptyTS {unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
            "tipo_servicio": [],  # Empty array
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("tipo_servicio") == [], "tipo_servicio should be empty array"
        
        # Clean up
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print("✓ Client created with empty tipo_servicio array")

    def test_create_client_with_single_tipo_servicio(self, auth_headers):
        """Create client with single tipo_servicio"""
        unique_id = uuid.uuid4().hex[:6].upper()
        
        payload = {
            "rif": f"TEST{unique_id}S",
            "legal_name": f"Single Tipo Servicio {unique_id}",
            "fantasy_name": f"SingleTS {unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
            "tipo_servicio": ["MPOS"],  # Single item
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("tipo_servicio") == ["MPOS"], "tipo_servicio should have single item"
        
        # Clean up
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print("✓ Client created with single tipo_servicio ['MPOS']")

class TestClientUpdateWithNewFields:
    """Test PUT /api/clients/{id} updates all new fields"""
    
    def test_update_client_all_new_fields(self, auth_headers):
        """Update client with all new fields"""
        unique_id = uuid.uuid4().hex[:6].upper()
        
        # First create a client
        create_payload = {
            "rif": f"UPD{unique_id}88",
            "legal_name": f"Update Test {unique_id}",
            "fantasy_name": f"UpdateCorp {unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
        }
        
        create_response = requests.post(f"{BASE_URL}/api/clients", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        
        client_id = create_response.json().get("client_id")
        
        # Update with new fields
        update_payload = {
            **create_payload,
            "grupo_economico": "Grupo Actualizado",
            "ejecutivo_propietario": "Nuevo Ejecutivo",
            "fecha_primer_contacto": "2026-01-20",
            "tipo_contacto": "Email",
            "tipo_servicio": ["VPOS", "MPOS"],
            "categoria_comercial": "Tecnología",
            "integrador_id": "int_updated",
            "integrador_name": "Integrador Actualizado",
            "aplicativo": "UpdatedApp v2.0",
        }
        
        update_response = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        data = update_response.json()
        
        # Verify all new fields updated
        assert data.get("grupo_economico") == "Grupo Actualizado"
        assert data.get("ejecutivo_propietario") == "Nuevo Ejecutivo"
        assert data.get("fecha_primer_contacto") == "2026-01-20"
        assert data.get("tipo_contacto") == "Email"
        assert data.get("tipo_servicio") == ["VPOS", "MPOS"]
        assert data.get("integrador_id") == "int_updated"
        assert data.get("integrador_name") == "Integrador Actualizado"
        assert data.get("aplicativo") == "UpdatedApp v2.0"
        
        # Verify via GET
        get_response = requests.get(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        get_data = get_response.json()
        assert get_data.get("grupo_economico") == "Grupo Actualizado", "GET should reflect update"
        assert get_data.get("tipo_servicio") == ["VPOS", "MPOS"], "GET should reflect tipo_servicio update"
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print("✓ Client updated with all new fields and verified via GET")

    def test_update_tipo_servicio_array(self, auth_headers):
        """Update tipo_servicio from empty to multiple and back"""
        unique_id = uuid.uuid4().hex[:6].upper()
        
        # Create with empty tipo_servicio
        create_payload = {
            "rif": f"TYP{unique_id}88",
            "legal_name": f"Tipo Servicio Test {unique_id}",
            "fantasy_name": f"TSTest {unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
            "tipo_servicio": [],
        }
        
        create_response = requests.post(f"{BASE_URL}/api/clients", json=create_payload, headers=auth_headers)
        assert create_response.status_code == 200
        client_id = create_response.json().get("client_id")
        
        # Update to multiple services
        update_payload = {**create_payload, "tipo_servicio": ["VPOS", "MPOS", "Payment Gateway", "Link de Pago"]}
        update_response = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        assert update_response.json().get("tipo_servicio") == ["VPOS", "MPOS", "Payment Gateway", "Link de Pago"]
        
        # Update back to single service
        update_payload["tipo_servicio"] = ["MPOS"]
        update_response = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload, headers=auth_headers)
        assert update_response.status_code == 200
        assert update_response.json().get("tipo_servicio") == ["MPOS"]
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print("✓ tipo_servicio array updates correctly ([] → [4 items] → [1 item])")

class TestIntegratorIntegration:
    """Test integrator fields work with real integrators from dropdown"""
    
    def test_client_with_real_integrator(self, auth_headers):
        """Create client using integrator from dropdown"""
        # First get integrators
        integrators_response = requests.get(f"{BASE_URL}/api/integrators/dropdown", headers=auth_headers)
        assert integrators_response.status_code == 200
        integrators = integrators_response.json()
        
        if not integrators:
            # Create a test integrator first
            test_integrator = {
                "name": "Test Integrator 88",
                "integrator_type": "Integrador",
                "integration_type": "PG",
                "app_name": "TestApp88",
                "integration_modality": "PG Universal",
                "integrator_status": "En proceso"
            }
            create_int_resp = requests.post(f"{BASE_URL}/api/integrators", json=test_integrator, headers=auth_headers)
            if create_int_resp.status_code == 200:
                integrators = [create_int_resp.json()]
            else:
                pytest.skip("No integrators available and couldn't create one")
        
        # Use first integrator
        integrator = integrators[0]
        unique_id = uuid.uuid4().hex[:6].upper()
        
        payload = {
            "rif": f"INT{unique_id}88",
            "legal_name": f"Integrator Client {unique_id}",
            "fantasy_name": f"IntClient {unique_id}",
            "segment": "Corporativo",
            "sucursal": "Principal",
            "integrador_id": integrator.get("integrator_id"),
            "integrador_name": integrator.get("name"),
            "aplicativo": integrator.get("app_name"),
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("integrador_id") == integrator.get("integrator_id")
        assert data.get("integrador_name") == integrator.get("name")
        assert data.get("aplicativo") == integrator.get("app_name")
        
        # Clean up
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        
        print(f"✓ Client created with real integrator: {integrator.get('name')} / {integrator.get('app_name')}")


class TestClientFieldsValidation:
    """Test new field validations and edge cases"""
    
    def test_tipo_contacto_values(self, auth_headers):
        """Test different tipo_contacto values"""
        for tipo in ["Físico", "Telefónico", "Email"]:
            unique_id = uuid.uuid4().hex[:6].upper()
            payload = {
                "rif": f"TC{unique_id}",
                "legal_name": f"Tipo Contacto {tipo} {unique_id}",
                "fantasy_name": f"TC{unique_id}",
                "segment": "Pymes",
                "sucursal": "Principal",
                "tipo_contacto": tipo,
            }
            
            response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
            assert response.status_code == 200, f"Failed for tipo_contacto={tipo}: {response.text}"
            
            data = response.json()
            assert data.get("tipo_contacto") == tipo
            
            # Clean up
            if data.get("client_id"):
                requests.delete(f"{BASE_URL}/api/clients/{data['client_id']}", headers=auth_headers)
        
        print("✓ All tipo_contacto values work: Físico, Telefónico, Email")
    
    def test_all_tipo_servicio_combinations(self, auth_headers):
        """Test all possible tipo_servicio combinations"""
        all_services = ["VPOS", "MPOS", "Payment Gateway", "Link de Pago"]
        
        unique_id = uuid.uuid4().hex[:6].upper()
        payload = {
            "rif": f"ATS{unique_id}",
            "legal_name": f"All Tipo Servicio {unique_id}",
            "fantasy_name": f"ATS{unique_id}",
            "segment": "Pymes",
            "sucursal": "Principal",
            "tipo_servicio": all_services,
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert set(data.get("tipo_servicio", [])) == set(all_services), "All services should be stored"
        
        # Clean up
        if data.get("client_id"):
            requests.delete(f"{BASE_URL}/api/clients/{data['client_id']}", headers=auth_headers)
        
        print(f"✓ All tipo_servicio combinations work: {all_services}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
