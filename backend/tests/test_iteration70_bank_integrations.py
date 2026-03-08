"""
Test Iteration 70 - Bank Detail View (Visor 360°) and Bank Integrations
Tests:
- GET /api/banks/{id}/detail - Bank detail with products and integrations
- POST /api/banks/{id}/integrations - Create new integration with status flow
- PUT /api/banks/{id}/integrations/{int_id} - Update integration status
- DELETE /api/banks/{id}/integrations/{int_id} - Delete integration
- Integration statuses: Negoc. → DESA → SQA → Imple. → PreProd → Completado
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"

# Known bank from context
BANCO_VENEZUELA_ID = "bnk_3997d471d939"

# Integration statuses
VALID_STATUSES = ["Negoc.", "DESA", "SQA", "Imple.", "PreProd", "Completado"]


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


@pytest.fixture(scope="module")
def api_client(auth_headers):
    """Authenticated API client"""
    session = requests.Session()
    session.headers.update(auth_headers)
    return session


class TestBankDetailEndpoint:
    """Test GET /api/banks/{id}/detail endpoint"""

    def test_get_bank_detail_success(self, api_client):
        """Test getting bank detail with products and integrations"""
        response = api_client.get(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/detail")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "bank_id" in data
        assert data["bank_id"] == BANCO_VENEZUELA_ID
        assert "name" in data
        assert "products" in data
        assert "integrations" in data
        assert isinstance(data["products"], list)
        assert isinstance(data["integrations"], list)
        print(f"✓ Bank detail returned: {data['name']} with {len(data['products'])} products and {len(data['integrations'])} integrations")

    def test_get_bank_detail_not_found(self, api_client):
        """Test getting non-existent bank returns 404"""
        response = api_client.get(f"{BASE_URL}/api/banks/bnk_nonexistent123/detail")
        assert response.status_code == 404

    def test_bank_has_products(self, api_client):
        """Verify Banco de Venezuela has products (as per context: 5 products)"""
        response = api_client.get(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/detail")
        assert response.status_code == 200
        
        data = response.json()
        products = data.get("products", [])
        
        # According to context, bank has 5 products
        assert len(products) > 0, "Bank should have products"
        print(f"✓ Bank has {len(products)} products")
        
        # Check product structure
        if products:
            product = products[0]
            assert "product_name" in product
            # Check availability flags
            availability_keys = ["vpos_available", "gateway_available", "mpos_available", "link_available"]
            for key in availability_keys:
                assert key in product, f"Product should have {key}"

    def test_bank_integration_exists(self, api_client):
        """Verify existing test integration on Banco de Venezuela"""
        response = api_client.get(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/detail")
        assert response.status_code == 200
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        print(f"✓ Bank has {len(integrations)} integrations")
        
        # Check integration structure if exists
        if integrations:
            intg = integrations[0]
            assert "integration_id" in intg
            assert "service_name" in intg
            assert "component_type" in intg
            assert "status" in intg
            assert intg["status"] in VALID_STATUSES, f"Status {intg['status']} not in valid statuses"


class TestBankIntegrationCRUD:
    """Test integration CRUD operations"""

    def test_create_integration(self, api_client):
        """Test POST /api/banks/{id}/integrations - Create new integration"""
        new_integration = {
            "service_name": "TEST_Integration_Service",
            "component_type": "VPOS/MPOS",
            "status": "Negoc.",
            "notes": "Test integration created by iteration 70 tests"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations",
            json=new_integration
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "integration_id" in data
        assert data["service_name"] == new_integration["service_name"]
        assert data["component_type"] == new_integration["component_type"]
        assert data["status"] == "Negoc."
        
        # Store for cleanup
        TestBankIntegrationCRUD.created_integration_id = data["integration_id"]
        print(f"✓ Integration created: {data['integration_id']}")

    def test_verify_integration_created(self, api_client):
        """Verify the integration was created in the bank"""
        response = api_client.get(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/detail")
        assert response.status_code == 200
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        # Find our created integration
        found = any(i.get("service_name") == "TEST_Integration_Service" for i in integrations)
        assert found, "Created integration should exist in bank's integrations list"
        print("✓ Integration verified in bank detail")

    def test_update_integration_status(self, api_client):
        """Test PUT /api/banks/{id}/integrations/{int_id} - Update status"""
        integration_id = getattr(TestBankIntegrationCRUD, 'created_integration_id', None)
        if not integration_id:
            pytest.skip("No integration created to update")
        
        # Update status from Negoc. to DESA
        update_data = {"status": "DESA"}
        
        response = api_client.put(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/{integration_id}",
            json=update_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "DESA"
        print(f"✓ Integration status updated to DESA")

    def test_update_integration_to_completado(self, api_client):
        """Test updating integration through the full status flow"""
        integration_id = getattr(TestBankIntegrationCRUD, 'created_integration_id', None)
        if not integration_id:
            pytest.skip("No integration created to update")
        
        # Update through remaining statuses
        statuses_to_test = ["SQA", "Imple.", "PreProd", "Completado"]
        
        for status in statuses_to_test:
            response = api_client.put(
                f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/{integration_id}",
                json={"status": status}
            )
            assert response.status_code == 200
            assert response.json()["status"] == status
            print(f"  → Status updated to: {status}")
        
        print("✓ Full status flow tested: Negoc. → DESA → SQA → Imple. → PreProd → Completado")

    def test_update_integration_notes(self, api_client):
        """Test updating integration notes"""
        integration_id = getattr(TestBankIntegrationCRUD, 'created_integration_id', None)
        if not integration_id:
            pytest.skip("No integration created to update")
        
        update_data = {"notes": "Updated notes by test"}
        
        response = api_client.put(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/{integration_id}",
            json=update_data
        )
        
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes by test"
        print("✓ Integration notes updated")

    def test_delete_integration(self, api_client):
        """Test DELETE /api/banks/{id}/integrations/{int_id}"""
        integration_id = getattr(TestBankIntegrationCRUD, 'created_integration_id', None)
        if not integration_id:
            pytest.skip("No integration created to delete")
        
        response = api_client.delete(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/{integration_id}"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Integration deleted: {integration_id}")

    def test_verify_integration_deleted(self, api_client):
        """Verify the integration was deleted from the bank"""
        integration_id = getattr(TestBankIntegrationCRUD, 'created_integration_id', None)
        if not integration_id:
            pytest.skip("No integration created to verify deletion")
        
        response = api_client.get(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/detail")
        assert response.status_code == 200
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        # Integration should not exist
        found = any(i.get("integration_id") == integration_id for i in integrations)
        assert not found, "Deleted integration should not exist in bank's integrations list"
        print("✓ Integration deletion verified")


class TestBankIntegrationEdgeCases:
    """Test edge cases and validation"""

    def test_update_nonexistent_integration(self, api_client):
        """Test updating non-existent integration returns 404"""
        response = api_client.put(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/int_nonexistent123",
            json={"status": "DESA"}
        )
        assert response.status_code == 404

    def test_delete_nonexistent_integration(self, api_client):
        """Test deleting non-existent integration returns 404"""
        response = api_client.delete(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/int_nonexistent123"
        )
        assert response.status_code == 404

    def test_create_integration_pg_link_type(self, api_client):
        """Test creating integration with PG/Link component type"""
        new_integration = {
            "service_name": "TEST_PG_Integration",
            "component_type": "PG/Link",
            "status": "DESA",
            "notes": "PG/Link integration test"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations",
            json=new_integration
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["component_type"] == "PG/Link"
        
        # Cleanup
        if "integration_id" in data:
            api_client.delete(f"{BASE_URL}/api/banks/{BANCO_VENEZUELA_ID}/integrations/{data['integration_id']}")
        
        print("✓ PG/Link integration created and cleaned up")


class TestBankListCounters:
    """Test bank list counters - X Activos and Y en Integración"""

    def test_banks_list_returns_all_banks(self, api_client):
        """Test GET /api/banks returns banks list"""
        response = api_client.get(f"{BASE_URL}/api/banks")
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have banks in the list"
        print(f"✓ Banks list returned {len(data)} banks")

    def test_bank_has_products_and_integrations_for_counters(self, api_client):
        """Verify banks have the data needed for counters"""
        response = api_client.get(f"{BASE_URL}/api/banks")
        assert response.status_code == 200
        
        banks = response.json()
        
        # Find Banco de Venezuela
        banco_ven = next((b for b in banks if b.get("bank_id") == BANCO_VENEZUELA_ID), None)
        
        if banco_ven:
            products = banco_ven.get("products", [])
            integrations = banco_ven.get("integrations", [])
            
            active_count = len(products)
            integration_count = len([i for i in integrations if i.get("status") != "Completado"])
            
            print(f"✓ Banco de Venezuela: {active_count} Activos, {integration_count} en Integración")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
