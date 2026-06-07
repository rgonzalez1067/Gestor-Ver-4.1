# ruff: noqa
"""
Test iteration 93 - Testing tipo_corp field in Services (Medios de Pago) module

Tests:
1. POST /api/services with valid tipo_corp creates service
2. POST /api/services without tipo_corp fails validation (required field in ServiceCreate Literal)
3. POST /api/services with invalid tipo_corp fails validation
4. PUT /api/services/{id} can update tipo_corp
5. GET /api/services returns tipo_corp in each service
6. POST /api/new-products inherits tipo_corp from service
7. PUT /api/new-products/{id}/status to IMPLE propagates tipo_corp to bank integration

Credentials: np_test@test.com / Test1234!
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestTipoCorp:
    """Tests for tipo_corp field in services and propagation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        self.session_token = data.get("session_token") or data.get("token")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.session_token}"
        }
        yield
    
    # =========== SERVICE TESTS ===========
    
    def test_create_service_with_valid_tipo_corp_derecho_uso(self):
        """POST /api/services with tipo_corp='Derecho de Uso' should create service"""
        payload = {
            "name": "TEST_TipoCorp_DerechoUso",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "Derecho de Uso",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": False,
            "link_enabled": False,
            "setup_cost_conventional": 100.0,
            "monthly_cost_conventional": 50.0
        }
        resp = requests.post(f"{BASE_URL}/api/services", json=payload, headers=self.headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["tipo_corp"] == "Derecho de Uso"
        assert data["name"] == "TEST_TipoCorp_DerechoUso"
        print(f"PASS: Created service with tipo_corp='Derecho de Uso', service_id={data['service_id']}")
        # Clean up
        requests.delete(f"{BASE_URL}/api/services/{data['service_id']}", headers=self.headers)

    def test_create_service_with_valid_tipo_corp_apoyo_tecnico(self):
        """POST /api/services with tipo_corp='Apoyo Técnico' should create service"""
        payload = {
            "name": "TEST_TipoCorp_ApoyoTecnico",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "Apoyo Técnico",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": False,
            "link_enabled": False
        }
        resp = requests.post(f"{BASE_URL}/api/services", json=payload, headers=self.headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["tipo_corp"] == "Apoyo Técnico"
        print(f"PASS: Created service with tipo_corp='Apoyo Técnico', service_id={data['service_id']}")
        # Clean up
        requests.delete(f"{BASE_URL}/api/services/{data['service_id']}", headers=self.headers)

    def test_create_service_with_valid_tipo_corp_soporte_monitoreo(self):
        """POST /api/services with tipo_corp='Soporte y Monitoreo' should create service"""
        payload = {
            "name": "TEST_TipoCorp_SoporteMonitoreo",
            "category": "General",
            "service_type": "Producto",
            "tipo_corp": "Soporte y Monitoreo",
            "application_type": "recurring",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": True,
            "link_enabled": False
        }
        resp = requests.post(f"{BASE_URL}/api/services", json=payload, headers=self.headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["tipo_corp"] == "Soporte y Monitoreo"
        print(f"PASS: Created service with tipo_corp='Soporte y Monitoreo', service_id={data['service_id']}")
        # Clean up
        requests.delete(f"{BASE_URL}/api/services/{data['service_id']}", headers=self.headers)

    def test_create_service_without_tipo_corp_fails_validation(self):
        """POST /api/services without tipo_corp should fail (required field in Literal)"""
        payload = {
            "name": "TEST_NoTipoCorp",
            "category": "General",
            "service_type": "Servicio",
            # tipo_corp missing - should fail
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True
        }
        resp = requests.post(f"{BASE_URL}/api/services", json=payload, headers=self.headers)
        # Pydantic should return 422 for missing required field
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        print("PASS: POST without tipo_corp correctly returns 422 validation error")

    def test_create_service_with_invalid_tipo_corp_fails(self):
        """POST /api/services with invalid tipo_corp value should fail validation"""
        payload = {
            "name": "TEST_InvalidTipoCorp",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "InvalidValue",  # Not in the Literal values
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True
        }
        resp = requests.post(f"{BASE_URL}/api/services", json=payload, headers=self.headers)
        # Pydantic Literal should reject invalid values with 422
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        print("PASS: POST with invalid tipo_corp correctly returns 422 validation error")

    def test_update_service_tipo_corp(self):
        """PUT /api/services/{id} should allow updating tipo_corp"""
        # First create a service
        create_payload = {
            "name": "TEST_UpdateTipoCorp",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "Derecho de Uso",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True
        }
        create_resp = requests.post(f"{BASE_URL}/api/services", json=create_payload, headers=self.headers)
        assert create_resp.status_code == 200, f"Create failed: {create_resp.text}"
        service_id = create_resp.json()["service_id"]
        
        # Update tipo_corp
        update_payload = {
            "name": "TEST_UpdateTipoCorp",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "Apoyo Técnico",  # Changed
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True
        }
        update_resp = requests.put(f"{BASE_URL}/api/services/{service_id}", json=update_payload, headers=self.headers)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        data = update_resp.json()
        assert data["tipo_corp"] == "Apoyo Técnico", f"Expected 'Apoyo Técnico', got '{data.get('tipo_corp')}'"
        print("PASS: Updated tipo_corp from 'Derecho de Uso' to 'Apoyo Técnico'")
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=self.headers)

    def test_get_services_returns_tipo_corp(self):
        """GET /api/services should return tipo_corp in each service"""
        # Create a test service
        create_payload = {
            "name": "TEST_GetTipoCorp",
            "category": "General",
            "service_type": "Servicio",
            "tipo_corp": "Soporte y Monitoreo",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True
        }
        create_resp = requests.post(f"{BASE_URL}/api/services", json=create_payload, headers=self.headers)
        assert create_resp.status_code == 200
        service_id = create_resp.json()["service_id"]
        
        # Get all services and find our test service
        get_resp = requests.get(f"{BASE_URL}/api/services", headers=self.headers)
        assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
        services = get_resp.json()
        
        test_service = next((s for s in services if s["service_id"] == service_id), None)
        assert test_service is not None, "Test service not found in list"
        assert "tipo_corp" in test_service, "tipo_corp field missing from service"
        assert test_service["tipo_corp"] == "Soporte y Monitoreo"
        print("PASS: GET /api/services includes tipo_corp field")
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=self.headers)

    # =========== NEW PRODUCTS PROPAGATION TESTS ===========
    
    def test_new_product_inherits_tipo_corp_from_service(self):
        """POST /api/new-products should inherit tipo_corp from the selected service"""
        # Create a service with tipo_corp
        service_payload = {
            "name": "TEST_NewProductTipoCorp",
            "category": "General",
            "service_type": "Producto",
            "tipo_corp": "Derecho de Uso",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": True,
            "link_enabled": False
        }
        svc_resp = requests.post(f"{BASE_URL}/api/services", json=service_payload, headers=self.headers)
        assert svc_resp.status_code == 200, f"Service create failed: {svc_resp.text}"
        service_id = svc_resp.json()["service_id"]
        
        # Get a bank (use existing bank bnk_579bdec2964d)
        bank_id = "bnk_579bdec2964d"
        
        # Create new product
        np_payload = {
            "service_id": service_id,
            "component_type": "VPOS/MPOS",
            "bank_id": bank_id,
            "notes": "TEST - verifying tipo_corp inheritance"
        }
        np_resp = requests.post(f"{BASE_URL}/api/new-products", json=np_payload, headers=self.headers)
        assert np_resp.status_code == 200, f"New product create failed: {np_resp.text}"
        np_data = np_resp.json()
        
        # Verify tipo_corp was inherited
        assert "tipo_corp" in np_data, "tipo_corp field missing from new product"
        assert np_data["tipo_corp"] == "Derecho de Uso", f"Expected 'Derecho de Uso', got '{np_data.get('tipo_corp')}'"
        print(f"PASS: New product inherited tipo_corp='Derecho de Uso' from service, product_id={np_data['product_id']}")
        
        # Clean up
        requests.delete(f"{BASE_URL}/api/new-products/{np_data['product_id']}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=self.headers)

    def test_handoff_propagates_tipo_corp_to_bank_integration(self):
        """PUT /api/new-products/{id}/status to IMPLE should propagate tipo_corp to bank integration"""
        # Create a service with tipo_corp
        service_payload = {
            "name": "TEST_HandoffTipoCorp",
            "category": "General",
            "service_type": "Producto",
            "tipo_corp": "Apoyo Técnico",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": True,
            "link_enabled": False
        }
        svc_resp = requests.post(f"{BASE_URL}/api/services", json=service_payload, headers=self.headers)
        assert svc_resp.status_code == 200, f"Service create failed: {svc_resp.text}"
        service_id = svc_resp.json()["service_id"]
        
        # Get a bank
        bank_id = "bnk_579bdec2964d"
        
        # Create new product
        np_payload = {
            "service_id": service_id,
            "component_type": "VPOS/MPOS",
            "bank_id": bank_id,
            "notes": "TEST - verifying handoff tipo_corp propagation"
        }
        np_resp = requests.post(f"{BASE_URL}/api/new-products", json=np_payload, headers=self.headers)
        assert np_resp.status_code == 200
        product_id = np_resp.json()["product_id"]
        
        # Move through pipeline to IMPLE (triggers hand-off)
        # Negociación -> DESA
        requests.put(f"{BASE_URL}/api/new-products/{product_id}/status", 
                    json={"status": "DESA"}, headers=self.headers)
        # DESA -> SQA
        requests.put(f"{BASE_URL}/api/new-products/{product_id}/status", 
                    json={"status": "SQA"}, headers=self.headers)
        # SQA -> IMPLE (triggers hand-off and Promovido)
        imple_resp = requests.put(f"{BASE_URL}/api/new-products/{product_id}/status", 
                                  json={"status": "IMPLE"}, headers=self.headers)
        assert imple_resp.status_code == 200, f"IMPLE transition failed: {imple_resp.text}"
        imple_data = imple_resp.json()
        
        # Verify product is now Promovido
        assert imple_data.get("status") == "Promovido", f"Expected 'Promovido', got '{imple_data.get('status')}'"
        assert imple_data.get("_handoff") is True, "Hand-off flag should be True"
        
        # Get bank detail to verify integration was created with tipo_corp
        bank_resp = requests.get(f"{BASE_URL}/api/banks/{bank_id}/detail", headers=self.headers)
        assert bank_resp.status_code == 200, f"Bank detail failed: {bank_resp.text}"
        bank_data = bank_resp.json()
        
        # Find the new integration by service_name
        integrations = bank_data.get("integrations", [])
        new_intg = next((i for i in integrations if i.get("service_name") == "TEST_HandoffTipoCorp"), None)
        assert new_intg is not None, "Integration not found in bank"
        assert new_intg.get("tipo_corp") == "Apoyo Técnico", f"Expected tipo_corp='Apoyo Técnico', got '{new_intg.get('tipo_corp')}'"
        print(f"PASS: Hand-off propagated tipo_corp='Apoyo Técnico' to bank integration, integration_id={new_intg.get('integration_id')}")
        
        # Clean up - delete integration from bank
        requests.delete(f"{BASE_URL}/api/banks/{bank_id}/integrations/{new_intg['integration_id']}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/services/{service_id}", headers=self.headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
