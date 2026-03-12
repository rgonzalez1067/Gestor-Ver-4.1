"""
Test iteration 91: New Products (R&D Pipeline) Module
Tests for the pipeline lifecycle of new payment methods before official deployment.
States flow: Negociación → DESA → SQA → IMPLE → Promovido
Hand-off: When changing to IMPLE, the product is automatically inserted as BankIntegration with PreProd status.
Email notifications are MOCKED (logged to backend console).
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
    """Register and login to get session token"""
    email = "testadmin@gestor.com"
    password = "Admin2026!"
    
    # Try to login first
    login_resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    
    if login_resp.status_code == 200:
        token = login_resp.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"Logged in successfully, token obtained")
        return token
    
    # If login fails, try to register with a unique cedula
    unique_cedula = f"T{uuid.uuid4().hex[:8]}"
    register_resp = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "Admin",
        "cedula": unique_cedula,
        "sede": "TBP"
    })
    
    if register_resp.status_code in [200, 201]:
        data = register_resp.json()
        token = data.get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        print(f"Registered and logged in, token obtained")
        return token
    
    # Registration might fail due to email already exists but with wrong password
    # In that case, we need to use existing credentials
    print(f"Login failed: {login_resp.text}")
    print(f"Register failed: {register_resp.text}")
    pytest.fail(f"Cannot authenticate for tests. Login: {login_resp.text}, Register: {register_resp.text}")

@pytest.fixture(scope="module")
def test_bank(session, auth_token):
    """Create a test bank for use in new products tests"""
    unique_id = uuid.uuid4().hex[:6]
    bank_data = {
        "name": f"TEST_BANK_NPD_{unique_id}",
        "type": "Banco",
        "country": "Venezuela"
    }
    resp = session.post(f"{BASE_URL}/api/banks", json=bank_data)
    assert resp.status_code == 200 or resp.status_code == 201, f"Failed to create bank: {resp.text}"
    bank = resp.json()
    yield bank
    # Cleanup
    session.delete(f"{BASE_URL}/api/banks/{bank['bank_id']}")


class TestNewProductsModule:
    """Tests for the New Products R&D Pipeline Module"""

    # ==================== CREATE TESTS ====================

    def test_create_new_product_born_in_negociacion(self, session, auth_token, test_bank):
        """Test POST /api/new-products - Product should be created with initial status 'Negociación'"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_Product_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"],
            "notes": "Test product for R&D pipeline"
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        assert resp.status_code == 200 or resp.status_code == 201, f"Failed to create product: {resp.text}"
        
        product = resp.json()
        assert product["status"] == "Negociación", f"Expected status 'Negociación', got '{product['status']}'"
        assert product["service_name"] == product_data["service_name"]
        assert product["component_type"] == product_data["component_type"]
        assert product["bank_id"] == test_bank["bank_id"]
        assert product["bank_name"] == test_bank["name"]
        assert product["product_id"].startswith("npd_"), f"product_id should start with 'npd_', got {product['product_id']}"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print(f"PASS: Product created with initial status 'Negociación'")

    def test_create_new_product_with_invalid_bank(self, session, auth_token):
        """Test POST /api/new-products with non-existent bank returns 404"""
        product_data = {
            "service_name": "TEST_Product_InvalidBank",
            "component_type": "PG/Link",
            "bank_id": "non_existent_bank_id",
            "notes": "Should fail"
        }
        
        resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Invalid bank_id returns 404")

    # ==================== LIST AND GET TESTS ====================

    def test_list_all_new_products(self, session, auth_token, test_bank):
        """Test GET /api/new-products - List all products"""
        # First create a product
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_List_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # List products
        list_resp = session.get(f"{BASE_URL}/api/new-products")
        assert list_resp.status_code == 200, f"Failed to list products: {list_resp.text}"
        
        products = list_resp.json()
        assert isinstance(products, list)
        
        # Verify our product is in the list
        product_ids = [p["product_id"] for p in products]
        assert product["product_id"] in product_ids
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print(f"PASS: Listed products successfully, found {len(products)} products")

    def test_get_specific_product(self, session, auth_token, test_bank):
        """Test GET /api/new-products/{product_id} - Get specific product"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_Get_{unique_id}",
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"],
            "notes": "Specific product test"
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Get the product
        get_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}")
        assert get_resp.status_code == 200
        
        fetched = get_resp.json()
        assert fetched["product_id"] == product["product_id"]
        assert fetched["service_name"] == product_data["service_name"]
        assert fetched["notes"] == product_data["notes"]
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Got specific product successfully")

    def test_get_nonexistent_product(self, session, auth_token):
        """Test GET /api/new-products/{product_id} with non-existent ID returns 404"""
        resp = session.get(f"{BASE_URL}/api/new-products/npd_nonexistent123")
        assert resp.status_code == 404
        print("PASS: Non-existent product returns 404")

    # ==================== STATUS CHANGE TESTS ====================

    def test_status_change_to_desa(self, session, auth_token, test_bank):
        """Test PUT /api/new-products/{product_id}/status - Change to DESA"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_DESA_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Change to DESA
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "DESA"})
        assert status_resp.status_code == 200, f"Failed to change status: {status_resp.text}"
        
        updated = status_resp.json()
        assert updated["status"] == "DESA"
        
        # Verify persistence
        get_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}")
        assert get_resp.json()["status"] == "DESA"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Status changed to DESA successfully")

    def test_status_change_to_sqa(self, session, auth_token, test_bank):
        """Test PUT /api/new-products/{product_id}/status - Change to SQA"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_SQA_{unique_id}",
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Change to SQA
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "SQA"})
        assert status_resp.status_code == 200
        
        updated = status_resp.json()
        assert updated["status"] == "SQA"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Status changed to SQA successfully")

    def test_status_change_to_imple_handoff(self, session, auth_token, test_bank):
        """Test PUT /api/new-products/{product_id}/status - Change to IMPLE triggers hand-off
        
        When changing to IMPLE:
        1. Product status should become 'Promovido'
        2. A new BankIntegration should be created with status 'PreProd'
        3. Response should have _handoff=True
        """
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_HANDOFF_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"],
            "notes": "Testing automatic hand-off to bank"
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        product_id = product["product_id"]
        
        # Change to IMPLE (triggers hand-off)
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "IMPLE"})
        assert status_resp.status_code == 200, f"Failed hand-off: {status_resp.text}"
        
        updated = status_resp.json()
        # Product should now be Promovido
        assert updated["status"] == "Promovido", f"Expected 'Promovido', got '{updated['status']}'"
        # Should have hand-off flag
        assert updated.get("_handoff") == True, "Expected _handoff=True in response"
        # Should have promoted_integration_id
        assert "promoted_integration_id" in updated, "Expected promoted_integration_id in response"
        
        # Verify the integration was created in the bank
        bank_detail_resp = session.get(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/detail")
        assert bank_detail_resp.status_code == 200
        
        bank_detail = bank_detail_resp.json()
        integrations = bank_detail.get("integrations", [])
        
        # Find the new integration
        new_integration = None
        for intg in integrations:
            if intg.get("service_name") == product_data["service_name"]:
                new_integration = intg
                break
        
        assert new_integration is not None, "Integration not found in bank after hand-off"
        assert new_integration["status"] == "PreProd", f"Expected integration status 'PreProd', got '{new_integration['status']}'"
        assert "Promovido desde Pipeline I+D" in new_integration.get("notes", ""), "Integration notes should reference source product"
        
        # Cleanup - delete product and integration
        session.delete(f"{BASE_URL}/api/new-products/{product_id}")
        if new_integration:
            session.delete(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/integrations/{new_integration['integration_id']}")
        
        print("PASS: IMPLE status change triggered hand-off successfully")

    def test_cannot_change_status_of_promoted_product(self, session, auth_token, test_bank):
        """Test PUT /api/new-products/{product_id}/status - Cannot change a 'Promovido' product status"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_NOCHG_{unique_id}",
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        product_id = product["product_id"]
        
        # First promote the product
        session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "IMPLE"})
        
        # Try to change status again - should fail with 400
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "DESA"})
        assert status_resp.status_code == 400, f"Expected 400, got {status_resp.status_code}"
        
        error_detail = status_resp.json().get("detail", "")
        assert "promovido" in error_detail.lower() or "ya fue" in error_detail.lower(), "Error should mention product already promoted"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product_id}")
        # Also cleanup the integration created in the bank
        bank_resp = session.get(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/detail")
        if bank_resp.status_code == 200:
            for intg in bank_resp.json().get("integrations", []):
                if product_data["service_name"] in intg.get("service_name", ""):
                    session.delete(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/integrations/{intg['integration_id']}")
        
        print("PASS: Cannot change status of promoted product - returns 400")

    def test_invalid_status_value(self, session, auth_token, test_bank):
        """Test PUT /api/new-products/{product_id}/status with invalid status value"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_INVST_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Try invalid status
        status_resp = session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "InvalidStatus"})
        assert status_resp.status_code == 400
        
        # Also try "Promovido" directly (should be rejected)
        status_resp2 = session.put(f"{BASE_URL}/api/new-products/{product['product_id']}/status", json={"status": "Promovido"})
        assert status_resp2.status_code == 400, "Direct 'Promovido' status should be rejected"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Invalid status values rejected with 400")

    # ==================== DELETE TESTS ====================

    def test_delete_new_product(self, session, auth_token, test_bank):
        """Test DELETE /api/new-products/{product_id} - Delete product"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_DEL_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Delete
        del_resp = session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        assert del_resp.status_code == 200
        
        # Verify deleted
        get_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}")
        assert get_resp.status_code == 404
        
        print("PASS: Product deleted successfully")

    def test_delete_nonexistent_product(self, session, auth_token):
        """Test DELETE /api/new-products/{product_id} with non-existent ID returns 404"""
        resp = session.delete(f"{BASE_URL}/api/new-products/npd_nonexistent123")
        assert resp.status_code == 404
        print("PASS: Delete non-existent product returns 404")

    # ==================== EVOLUTION LOG TESTS ====================

    def test_create_evolution_entry(self, session, auth_token, test_bank):
        """Test POST /api/new-products/{product_id}/evolution - Create evolution log entry"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_EVO_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Create evolution entry
        evo_data = {
            "comment": "Primera reunión con equipo técnico del banco",
            "phase": "Negociación",
            "date": "2026-01-15"
        }
        evo_resp = session.post(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution", json=evo_data)
        assert evo_resp.status_code == 200 or evo_resp.status_code == 201, f"Failed to create evolution: {evo_resp.text}"
        
        entry = evo_resp.json()
        assert entry["comment"] == evo_data["comment"]
        assert entry["phase"] == evo_data["phase"]
        assert entry["date"] == evo_data["date"]
        assert entry["entry_id"].startswith("npe_"), f"entry_id should start with 'npe_', got {entry['entry_id']}"
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Evolution entry created successfully")

    def test_list_evolution_entries(self, session, auth_token, test_bank):
        """Test GET /api/new-products/{product_id}/evolution - List evolution log"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_EVOLIST_{unique_id}",
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Create multiple entries
        entries_data = [
            {"comment": "Entry 1 - Started negotiations", "phase": "Negociación", "date": "2026-01-10"},
            {"comment": "Entry 2 - Moving to development", "phase": "DESA", "date": "2026-01-12"},
        ]
        for evo_data in entries_data:
            session.post(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution", json=evo_data)
        
        # List entries
        list_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution")
        assert list_resp.status_code == 200
        
        entries = list_resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 2
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print(f"PASS: Listed {len(entries)} evolution entries")

    def test_update_evolution_entry(self, session, auth_token, test_bank):
        """Test PATCH /api/new-products/{product_id}/evolution/{entry_id} - Edit evolution entry"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_EVOUPD_{unique_id}",
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Create entry
        evo_data = {"comment": "Original comment", "phase": "Negociación", "date": "2026-01-10"}
        evo_resp = session.post(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution", json=evo_data)
        entry = evo_resp.json()
        
        # Update entry
        update_data = {"comment": "Updated comment", "phase": "DESA"}
        patch_resp = session.patch(
            f"{BASE_URL}/api/new-products/{product['product_id']}/evolution/{entry['entry_id']}", 
            json=update_data
        )
        assert patch_resp.status_code == 200, f"Failed to update: {patch_resp.text}"
        
        updated = patch_resp.json()
        assert updated["comment"] == "Updated comment"
        assert updated["phase"] == "DESA"
        assert "updated_at" in updated
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Evolution entry updated successfully")

    def test_delete_evolution_entry(self, session, auth_token, test_bank):
        """Test DELETE /api/new-products/{product_id}/evolution/{entry_id} - Delete evolution entry"""
        unique_id = uuid.uuid4().hex[:6]
        product_data = {
            "service_name": f"TEST_EVODEL_{unique_id}",
            "component_type": "PG/Link",
            "bank_id": test_bank["bank_id"]
        }
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        
        # Create entry
        evo_data = {"comment": "Entry to delete", "phase": "Negociación"}
        evo_resp = session.post(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution", json=evo_data)
        entry = evo_resp.json()
        
        # Delete entry
        del_resp = session.delete(
            f"{BASE_URL}/api/new-products/{product['product_id']}/evolution/{entry['entry_id']}"
        )
        assert del_resp.status_code == 200
        
        # Verify deleted - list should not contain the entry
        list_resp = session.get(f"{BASE_URL}/api/new-products/{product['product_id']}/evolution")
        entries = list_resp.json()
        entry_ids = [e["entry_id"] for e in entries]
        assert entry["entry_id"] not in entry_ids
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product['product_id']}")
        print("PASS: Evolution entry deleted successfully")

    # ==================== HAND-OFF VERIFICATION TEST ====================

    def test_handoff_creates_integration_in_bank_detail(self, session, auth_token, test_bank):
        """Test that after hand-off, GET /api/banks/{bank_id}/detail shows the new integration"""
        unique_id = uuid.uuid4().hex[:6]
        service_name = f"TEST_VERIFY_HANDOFF_{unique_id}"
        product_data = {
            "service_name": service_name,
            "component_type": "VPOS/MPOS",
            "bank_id": test_bank["bank_id"],
            "notes": "Verify hand-off integration"
        }
        
        # Create product
        create_resp = session.post(f"{BASE_URL}/api/new-products", json=product_data)
        product = create_resp.json()
        product_id = product["product_id"]
        
        # Trigger hand-off
        session.put(f"{BASE_URL}/api/new-products/{product_id}/status", json={"status": "IMPLE"})
        
        # Verify in bank detail
        bank_detail_resp = session.get(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/detail")
        assert bank_detail_resp.status_code == 200
        
        bank = bank_detail_resp.json()
        integrations = bank.get("integrations", [])
        
        # Find our integration
        found_integration = None
        for intg in integrations:
            if intg.get("service_name") == service_name:
                found_integration = intg
                break
        
        assert found_integration is not None, f"Integration '{service_name}' not found in bank detail after hand-off"
        assert found_integration["status"] == "PreProd"
        assert found_integration["component_type"] == "VPOS/MPOS"
        assert f"producto {product_id}" in found_integration.get("notes", "").lower()
        
        # Cleanup
        session.delete(f"{BASE_URL}/api/new-products/{product_id}")
        if found_integration:
            session.delete(f"{BASE_URL}/api/banks/{test_bank['bank_id']}/integrations/{found_integration['integration_id']}")
        
        print("PASS: Hand-off integration verified in bank detail")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
