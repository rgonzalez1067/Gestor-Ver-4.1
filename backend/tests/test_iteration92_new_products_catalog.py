"""
Test iteration 92: New Products Module - Catalog-based Selection & Audit Log
Tests for the enhanced features:
1. service_id instead of service_name for product creation
2. StatusTransitionLog for auditing state changes 
3. GET /api/new-products/{id}/transitions endpoint
4. Enhanced notifications with date and days_in_phase
5. Delete product also removes np_status_transitions entries
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def session():
    """Shared requests session with authorization"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Login with test user to get session token"""
    email = "np_test@test.com"
    password = "Test1234!"
    
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code == 200:
        token = login_resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"Logged in as {email}")
        return token
    
    pytest.fail(f"Cannot authenticate for tests: {login_resp.text}")


@pytest.fixture(scope="module")
def test_service(session, auth_token):
    """Create a test service of type 'Producto' for testing catalog-based selection"""
    unique_id = uuid.uuid4().hex[:6]
    service_data = {
        "category": "Test Category",
        "name": f"TEST_SERVICE_{unique_id}",
        "service_type": "Producto",
        "vpos_enabled": True,
        "mpos_enabled": True,
        "gateway_enabled": False,
        "link_enabled": False
    }
    resp = session.post(f"{BASE_URL}/api/services", json=service_data)
    assert resp.status_code in [200, 201], f"Failed to create service: {resp.text}"
    service = resp.json()
    print(f"Created test service: {service['service_id']}")
    yield service
    # Cleanup
    session.delete(f"{BASE_URL}/api/services/{service['service_id']}")


@pytest.fixture(scope="module")
def test_bank(session, auth_token):
    """Create a test bank for use in tests"""
    unique_id = uuid.uuid4().hex[:6]
    bank_data = {
        "name": f"TEST_BANK_IT92_{unique_id}",
        "type": "Banco",
        "country": "Venezuela"
    }
    resp = session.post(f"{BASE_URL}/api/banks", json=bank_data)
    assert resp.status_code in [200, 201], f"Failed to create bank: {resp.text}"
    bank = resp.json()
    print(f"Created test bank: {bank['bank_id']}")
    yield bank
    # Cleanup
    session.delete(f"{BASE_URL}/api/banks/{bank['bank_id']}")


class TestServiceIdCatalogSelection:
    """Tests for POST /api/new-products with service_id instead of service_name"""

    def test_create_product_with_service_id_resolves_name(self, session, auth_token, test_service, test_bank):
        """Test POST /api/new-products with service_id resolves service_name from catalog"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"],
            "notes": "Test product using service_id"
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        assert resp.status_code in [200, 201], f"Failed to create product: {resp.text}"
        
        product = resp.json()
        # Verify service_id is stored
        assert product["service_id"] == test_service["service_id"], "service_id should be stored"
        # Verify service_name is resolved from catalog
        assert product["service_name"] == test_service["name"], \
            f"Expected service_name '{test_service['name']}', got '{product['service_name']}'"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print(f"PASS: Product created with service_id resolving to '{product['service_name']}'")

    def test_create_product_with_nonexistent_service_returns_404(self, session, auth_token, test_bank):
        """Test POST /api/new-products with non-existent service_id returns 404"""
        product_data = {
            "service_id": "srv_non_existent_12345",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        
        error_detail = resp.json().get("detail", "").lower()
        assert "catálogo" in error_detail or "créelo" in error_detail, \
            "Error should mention creating the service first in catalog"
        
        print("PASS: Non-existent service_id returns 404 with appropriate message")


class TestStatusTransitionLog:
    """Tests for StatusTransitionLog audit feature"""

    def test_initial_transition_logged_on_create(self, session, auth_token, test_service, test_bank):
        """Test that initial transition ('' → 'Negociación') is logged on product creation"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = resp.json()
        
        # Check transitions
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/transitions")
        assert trans_resp.status_code == 200
        
        transitions = trans_resp.json()
        assert len(transitions) >= 1, "Should have at least 1 transition (initial)"
        
        # Find the initial transition
        initial = None
        for t in transitions:
            if t["old_status"] == "" and t["new_status"] == "Negociación":
                initial = t
                break
        
        assert initial is not None, "Initial transition ('' → 'Negociación') not found"
        assert initial["user_id"], "user_id should be recorded"
        assert initial["user_name"], "user_name should be recorded"
        assert initial["days_in_previous_phase"] is None, "days_in_previous_phase should be None for initial"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Initial transition logged with user_id and user_name")

    def test_status_change_records_transition_with_user_and_days(self, session, auth_token, test_service, test_bank):
        """Test PUT /api/new-products/{id}/status records StatusTransitionLog with all fields"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"]
        }
        
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Change status to DESA
        session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "DESA"})
        
        # Check transitions
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/transitions")
        transitions = trans_resp.json()
        
        # Find the DESA transition
        desa_trans = None
        for t in transitions:
            if t["new_status"] == "DESA":
                desa_trans = t
                break
        
        assert desa_trans is not None, "DESA transition not found"
        assert desa_trans["old_status"] == "Negociación"
        assert desa_trans["new_status"] == "DESA"
        assert desa_trans["user_id"], "user_id should be recorded"
        assert desa_trans["user_name"], "user_name should be recorded"
        assert "timestamp" in desa_trans, "timestamp should be present"
        # days_in_previous_phase can be 0 or a number
        assert "days_in_previous_phase" in desa_trans
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Status change records transition with old_status, new_status, user_id, user_name, timestamp")

    def test_transitions_endpoint_returns_descending_order(self, session, auth_token, test_service, test_bank):
        """Test GET /api/new-products/{id}/transitions returns transitions sorted by timestamp DESC"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Make multiple status changes
        session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "DESA"})
        session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "SQA"})
        
        # Get transitions
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/transitions")
        transitions = trans_resp.json()
        
        assert len(transitions) >= 3, f"Expected at least 3 transitions, got {len(transitions)}"
        
        # Check descending order by timestamp
        for i in range(len(transitions) - 1):
            ts1 = transitions[i]["timestamp"]
            ts2 = transitions[i + 1]["timestamp"]
            assert ts1 >= ts2, f"Transitions should be in descending order: {ts1} should be >= {ts2}"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Transitions endpoint returns transitions in descending order by timestamp")


class TestIMPLEDoubleTransition:
    """Tests for the IMPLE status change which creates 2 transitions"""

    def test_imple_creates_two_transitions_and_handoff(self, session, auth_token, test_service, test_bank):
        """Test PUT /status to IMPLE creates two transitions (→IMPLE and →Promovido) + hand-off"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        product_id = product["product_id"]
        
        # Change to DESA first, then to IMPLE
        session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "DESA"})
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "IMPLE"})
        
        result = status_resp.json()
        assert result["status"] == "Promovido", "Product should be Promovido after IMPLE"
        assert result.get("_handoff") == True, "Should have _handoff flag"
        
        # Check transitions
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product_id}/transitions")
        transitions = trans_resp.json()
        
        # Find IMPLE and Promovido transitions
        has_imple = any(t["new_status"] == "IMPLE" for t in transitions)
        has_promovido = any(t["new_status"] == "Promovido" and t["old_status"] == "IMPLE" for t in transitions)
        
        assert has_imple, "Should have transition to IMPLE"
        assert has_promovido, "Should have transition from IMPLE to Promovido"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product_id}")
        # Also clean up integration in bank
        bank_detail = session.get(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/detail").json()
        for intg in bank_detail.get("integrations", []):
            if test_service["name"] in intg.get("service_name", ""):
                session.delete(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/integrations/{intg['integration_id']}")
        
        print("PASS: IMPLE creates two transitions (SQA→IMPLE and IMPLE→Promovido) plus hand-off")


class TestDeleteProductCascade:
    """Tests for DELETE /api/new-products/{id} cascade to np_status_transitions"""

    def test_delete_product_removes_transitions(self, session, auth_token, test_service, test_bank):
        """Test DELETE /api/new-products/{id} also deletes associated transitions"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        product_id = product["product_id"]
        
        # Make some status changes
        session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "DESA"})
        session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "SQA"})
        
        # Verify transitions exist
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product_id}/transitions")
        assert len(trans_resp.json()) >= 3, "Should have at least 3 transitions before delete"
        
        # Delete product
        del_resp = session.delete(f"{BASE_URL}/api/new-products/{product_id}")
        assert del_resp.status_code == 200
        
        # Verify product deleted
        get_resp = session.get(f"{BASE_URL}/api/new-products/{product_id}")
        assert get_resp.status_code == 404
        
        # Verify transitions deleted
        trans_resp2 = session.get(f"{BASE_URL}/api/new-products/{product_id}/transitions")
        assert trans_resp2.status_code == 200  # Endpoint should return 200 with empty list
        assert len(trans_resp2.json()) == 0, "Transitions should be deleted with product"
        
        print("PASS: DELETE /api/new-products/{id} also removes associated transitions")


class TestExistingProductsWithService:
    """Test using the existing seed data mentioned in credentials"""

    def test_existing_promoted_product_has_transitions(self, session, auth_token):
        """Test that existing promoted product npd_79da11fa has full transition history"""
        product_id = "npd_79da11fa"
        
        # Check if product exists
        get_resp = session.get(f"{BASE_URL}/api/new-products/{product_id}")
        if get_resp.status_code == 404:
            pytest.skip("Existing product npd_79da11fa not found - may have been deleted")
        
        assert get_resp.status_code == 200
        product = get_resp.json()
        assert product["status"] == "Promovido"
        
        # Check transitions
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product_id}/transitions")
        assert trans_resp.status_code == 200
        
        transitions = trans_resp.json()
        assert len(transitions) >= 5, f"Promoted product should have 5+ transitions, got {len(transitions)}"
        
        # Verify transition sequence includes Promovido
        statuses = [t["new_status"] for t in transitions]
        assert "Promovido" in statuses, "Should have Promovido transition"
        assert "Negociación" in statuses, "Should have Negociación transition"
        
        print(f"PASS: Existing promoted product has {len(transitions)} transitions logged")

    def test_can_use_existing_service_for_new_product(self, session, auth_token, test_bank):
        """Test using the existing service 'QR Pay Test' (srv_cd9496203508) for a new product"""
        service_id = "srv_cd9496203508"
        
        # Verify service exists
        services_resp = session.get(f"{BASE_URL}/api/services")
        services = services_resp.json()
        service = next((s for s in services if s["service_id"] == service_id), None)
        
        if not service:
            pytest.skip("Existing service srv_cd9496203508 not found")
        
        product_data = {
            "service_id": service_id,
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"],
            "notes": "Test using existing catalog service"
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        assert resp.status_code in [200, 201], f"Failed: {resp.text}"
        
        product = resp.json()
        assert product["service_id"] == service_id
        assert product["service_name"] == service["name"]
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print(f"PASS: Can use existing service '{service['name']}' from catalog")


class TestTransitionLogFields:
    """Detailed tests for StatusTransitionLog fields"""

    def test_transition_has_all_required_fields(self, session, auth_token, test_service, test_bank):
        """Test each transition has: transition_id, product_id, old_status, new_status, timestamp, user_id, user_name, days_in_previous_phase"""
        product_data = {
            "service_id": test_service["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Change status
        session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "DESA"})
        
        trans_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/transitions")
        transitions = trans_resp.json()
        
        required_fields = ["transition_id", "product_id", "old_status", "new_status", 
                         "timestamp", "user_id", "user_name", "days_in_previous_phase"]
        
        for t in transitions:
            for field in required_fields:
                assert field in t, f"Missing field '{field}' in transition"
            
            # Verify transition_id format
            assert t["transition_id"].startswith("stl_"), f"transition_id should start with 'stl_'"
            # Verify product_id matches
            assert t["product_id"] == product["product_id"]
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: All transitions have required fields with correct formats")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
