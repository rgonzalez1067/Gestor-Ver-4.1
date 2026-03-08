"""
Test Iteration 73 - Integrators Module Evolution
Tests for new fields: integration_type, gestor, categoria, certifications
And certification matrix feature
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIntegratorsModuleAuth:
    """Authentication and users list for gestor dropdown"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["session_token"]
    
    def test_auth_users_returns_list(self, auth_token):
        """GET /api/auth/users returns list of active users with full_name"""
        response = requests.get(
            f"{BASE_URL}/api/auth/users",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        assert len(users) > 0
        # Check structure
        user = users[0]
        assert "user_id" in user
        assert "full_name" in user
        assert "email" in user
        print(f"✓ Found {len(users)} users for gestor dropdown")
    
    def test_auth_users_requires_auth(self):
        """GET /api/auth/users requires authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/users")
        assert response.status_code in [401, 403]


class TestIntegratorsCRUD:
    """CRUD operations for integrators with new fields"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        assert response.status_code == 200
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def created_integrator_id(self, auth_token):
        """Create test integrator and return ID for cleanup"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Integrator_{unique_id}",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": f"TEST_App_{unique_id}",
            "integration_modality": "REST",
            "integrator_status": "En proceso",
            "gestor": "Admin Test",
            "categoria": "Cliente/Integrador nuevo PG",
            "certifications": {}
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        integrator = response.json()
        integrator_id = integrator["integrator_id"]
        yield integrator_id
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_get_integrators_list(self, auth_token):
        """GET /api/integrators returns list with new fields"""
        response = requests.get(
            f"{BASE_URL}/api/integrators",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        integrators = response.json()
        assert isinstance(integrators, list)
        assert len(integrators) > 0
        # Check structure includes new fields
        integrator = integrators[0]
        required_fields = ["integrator_id", "name", "integrator_type", "app_name", 
                          "integration_modality", "integrator_status", 
                          "integration_type", "gestor", "categoria", "certifications"]
        for field in required_fields:
            assert field in integrator, f"Missing field: {field}"
        print(f"✓ Found {len(integrators)} integrators with all required fields")
    
    def test_get_integrators_filter_by_status(self, auth_token):
        """GET /api/integrators with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/integrators?integrator_status=Certificado",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        integrators = response.json()
        for intg in integrators:
            assert intg["integrator_status"] == "Certificado"
        print(f"✓ Filter by status works - {len(integrators)} Certificado integrators")
    
    def test_get_integrators_filter_by_type(self, auth_token):
        """GET /api/integrators with type filter"""
        response = requests.get(
            f"{BASE_URL}/api/integrators?integrator_type=Integrador",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        integrators = response.json()
        for intg in integrators:
            assert intg["integrator_type"] == "Integrador"
        print(f"✓ Filter by type works - {len(integrators)} Integrador type")
    
    def test_create_integrator_with_new_fields(self, auth_token):
        """POST /api/integrators creates with all new fields"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_New_{unique_id}",
            "integrator_type": "Comercio",
            "integration_type": "CR",  # Caja Registradora
            "app_name": f"TEST_CajaApp_{unique_id}",
            "integration_modality": "Bridge PG",
            "integrator_status": "En proceso",
            "gestor": "Admin Test",
            "categoria": "Cliente/Integrador nuevo VPOS",
            "certifications": {"srv_test": "P"}
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        integrator = response.json()
        
        # Verify all fields
        assert integrator["name"] == payload["name"]
        assert integrator["integrator_type"] == "Comercio"
        assert integrator["integration_type"] == "CR"
        assert integrator["app_name"] == payload["app_name"]
        assert integrator["integration_modality"] == "Bridge PG"
        assert integrator["gestor"] == "Admin Test"
        assert integrator["categoria"] == "Cliente/Integrador nuevo VPOS"
        assert integrator["certifications"] == {"srv_test": "P"}
        print(f"✓ Created integrator with all new fields: {integrator['integrator_id']}")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/integrators/{integrator['integrator_id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_update_integrator_certifications(self, auth_token, created_integrator_id):
        """PUT /api/integrators/{id} updates certifications dict"""
        # Get current state
        get_response = requests.get(
            f"{BASE_URL}/api/integrators/{created_integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 200
        current = get_response.json()
        
        # Update with certifications
        update_payload = {
            "name": current["name"],
            "integrator_type": current["integrator_type"],
            "integration_type": current["integration_type"],
            "app_name": current["app_name"],
            "integration_modality": current["integration_modality"],
            "integrator_status": current["integrator_status"],
            "gestor": current["gestor"],
            "categoria": current["categoria"],
            "certifications": {
                "srv_9ab0b8e30dc7": "C",  # Tarjeta Crédito/Débito
                "srv_516ce343d5f2": "P",  # TDD/TDC Divisas
                "srv_1521acede404": "N/A" # P2C
            }
        }
        response = requests.put(
            f"{BASE_URL}/api/integrators/{created_integrator_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        updated = response.json()
        
        # Verify certifications updated
        assert updated["certifications"]["srv_9ab0b8e30dc7"] == "C"
        assert updated["certifications"]["srv_516ce343d5f2"] == "P"
        assert updated["certifications"]["srv_1521acede404"] == "N/A"
        print(f"✓ Updated certifications for {created_integrator_id}")
        
        # GET to verify persistence
        verify_response = requests.get(
            f"{BASE_URL}/api/integrators/{created_integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert verify_response.status_code == 200
        verified = verify_response.json()
        assert verified["certifications"]["srv_9ab0b8e30dc7"] == "C"
        print("✓ Certifications persisted in database")
    
    def test_update_integrator_gestor_and_categoria(self, auth_token, created_integrator_id):
        """PUT /api/integrators/{id} updates gestor and categoria"""
        get_response = requests.get(
            f"{BASE_URL}/api/integrators/{created_integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        current = get_response.json()
        
        update_payload = {
            "name": current["name"],
            "integrator_type": current["integrator_type"],
            "integration_type": "LP",  # Change to Link de Pago
            "app_name": current["app_name"],
            "integration_modality": current["integration_modality"],
            "integrator_status": "Certificado",
            "gestor": "Naylen Arevalo",  # Different gestor
            "categoria": "Cliente/Integrador nuevo Link de Pago",
            "certifications": current.get("certifications") or {}
        }
        response = requests.put(
            f"{BASE_URL}/api/integrators/{created_integrator_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        updated = response.json()
        
        assert updated["integration_type"] == "LP"
        assert updated["gestor"] == "Naylen Arevalo"
        assert updated["categoria"] == "Cliente/Integrador nuevo Link de Pago"
        assert updated["integrator_status"] == "Certificado"
        print(f"✓ Updated gestor, categoria, integration_type")
    
    def test_delete_integrator(self, auth_token):
        """DELETE /api/integrators/{id} removes integrator"""
        # Create one to delete
        unique_id = uuid.uuid4().hex[:6]
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            json={
                "name": f"TEST_ToDelete_{unique_id}",
                "integrator_type": "Integrador",
                "app_name": f"TEST_DeleteApp_{unique_id}",
                "integration_modality": "MPOS",
                "integrator_status": "Suspendido"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert create_response.status_code == 200
        integrator_id = create_response.json()["integrator_id"]
        
        # Delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 404
        print(f"✓ Deleted integrator {integrator_id} successfully")


class TestServicesForCertMatrix:
    """Test services endpoint for certification matrix products"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        assert response.status_code == 200
        return response.json()["session_token"]
    
    def test_services_returns_products_for_cert_matrix(self, auth_token):
        """GET /api/services returns products with service_type='Producto' and application_type in ('setup', 'both')"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        services = response.json()
        
        # Filter products for cert matrix
        cert_products = [
            s for s in services
            if s.get("service_type") == "Producto" 
            and s.get("application_type") in ("setup", "both")
        ]
        
        assert len(cert_products) > 0, "No products found for certification matrix"
        print(f"✓ Found {len(cert_products)} products for certification matrix")
        
        # Verify structure
        product = cert_products[0]
        assert "service_id" in product
        assert "name" in product
        print(f"✓ Sample product: {product['name']} ({product['service_id']})")


class TestIntegrationTypes:
    """Test all integration type values"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        return response.json()["session_token"]
    
    @pytest.mark.parametrize("integration_type,label", [
        ("CR", "Caja Registradora"),
        ("LP", "Link de Pago"),
        ("PG", "Payment Gateway"),
        ("MP", "Mobile POS"),
        ("TK", "Tokenizador"),
    ])
    def test_create_with_each_integration_type(self, auth_token, integration_type, label):
        """Create integrator with each integration_type value"""
        unique_id = uuid.uuid4().hex[:6]
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            json={
                "name": f"TEST_{integration_type}_{unique_id}",
                "integrator_type": "Integrador",
                "integration_type": integration_type,
                "app_name": f"TEST_{label}_{unique_id}",
                "integration_modality": "REST",
                "integrator_status": "En proceso"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        created = response.json()
        assert created["integration_type"] == integration_type
        print(f"✓ Created with integration_type={integration_type} ({label})")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/integrators/{created['integrator_id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
