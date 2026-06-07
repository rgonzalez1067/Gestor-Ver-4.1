# ruff: noqa
"""
Iteration 80 - Product Evolution (Bitácora) and Integration Report Grouping Tests
Tests for:
1. GET /api/banks/integrations/report (flat mode and grouped modes)
2. POST/GET/PATCH/DELETE /api/banks/{bank_id}/integrations/{integration_id}/evolution
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token using test credentials"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "Test1234!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["session_token"]

@pytest.fixture(scope="module")
def api_client(auth_token):
    """Create session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session

@pytest.fixture(scope="module")
def test_bank_with_integration(api_client):
    """Get a bank with integrations or create one for testing"""
    # First try to get an existing bank with integrations
    response = api_client.get(f"{BASE_URL}/api/banks")
    banks = response.json()
    
    for bank in banks:
        if bank.get('integrations') and len(bank.get('integrations', [])) > 0:
            bank_id = bank['bank_id']
            integration_id = bank['integrations'][0]['integration_id']
            return {"bank_id": bank_id, "integration_id": integration_id, "created": False}
    
    # If no bank with integration found, create one
    if len(banks) > 0:
        bank_id = banks[0]['bank_id']
        # Create a test integration
        new_integration = {
            "service_name": "TEST_Evolution_Product",
            "component_type": "VPOS/MPOS",
            "status": "DESA",
            "notes": "Test integration for evolution log testing"
        }
        create_response = api_client.post(
            f"{BASE_URL}/api/banks/{bank_id}/integrations",
            json=new_integration
        )
        assert create_response.status_code == 200, f"Failed to create test integration: {create_response.text}"
        integration_id = create_response.json().get('integration_id')
        return {"bank_id": bank_id, "integration_id": integration_id, "created": True}
    
    pytest.skip("No banks available for testing")


# ==================== INTEGRATION REPORT FLAT MODE ====================

class TestIntegrationReportFlat:
    """Test GET /api/banks/integrations/report without grouping (flat mode)"""
    
    def test_report_flat_returns_list(self, api_client):
        """Flat mode returns a list of integrations"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Flat mode should return list, got {type(data)}"
    
    def test_report_flat_entry_structure(self, api_client):
        """Each entry in flat list has required fields"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            required_fields = ['bank_id', 'bank_name', 'integration_id', 'service_name', 
                             'component_type', 'status', 'notes', 'bank_logo_url']
            for field in required_fields:
                assert field in entry, f"Missing required field: {field}"


# ==================== INTEGRATION REPORT GROUPED MODE ====================

class TestIntegrationReportGroupedByBank:
    """Test GET /api/banks/integrations/report?group_by=bank"""
    
    def test_group_by_bank_returns_dict(self, api_client):
        """Grouped by bank returns a dictionary with groups"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=bank")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict), f"Grouped mode should return dict, got {type(data)}"
        assert "group_by" in data, "Response should have group_by field"
        assert data["group_by"] == "bank", f"group_by should be 'bank', got {data.get('group_by')}"
        assert "groups" in data, "Response should have groups field"
        assert "total" in data, "Response should have total count"
    
    def test_group_by_bank_group_structure(self, api_client):
        """Each group has label, count, and items"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=bank")
        data = response.json()
        groups = data.get("groups", {})
        
        if len(groups) > 0:
            for key, group in groups.items():
                assert "label" in group, f"Group {key} missing label"
                assert "count" in group, f"Group {key} missing count"
                assert "items" in group, f"Group {key} missing items"
                assert isinstance(group["items"], list), "Items should be a list"
                assert group["count"] == len(group["items"]), "Count should match items length"


class TestIntegrationReportGroupedByProduct:
    """Test GET /api/banks/integrations/report?group_by=product"""
    
    def test_group_by_product_returns_dict(self, api_client):
        """Grouped by product returns a dictionary with groups"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=product")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict), f"Grouped mode should return dict, got {type(data)}"
        assert data.get("group_by") == "product", "group_by should be 'product'"
    
    def test_group_by_product_groups_by_service_name(self, api_client):
        """Products are grouped by service_name"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=product")
        data = response.json()
        groups = data.get("groups", {})
        
        for key, group in groups.items():
            # Group key should be service_name
            # All items in this group should have the same service_name
            if len(group.get("items", [])) > 0:
                service_names = set(item["service_name"] for item in group["items"])
                assert len(service_names) == 1, "All items in product group should have same service_name"


class TestIntegrationReportGroupedByPhase:
    """Test GET /api/banks/integrations/report?group_by=phase"""
    
    def test_group_by_phase_returns_dict(self, api_client):
        """Grouped by phase returns a dictionary with groups"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=phase")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict), f"Grouped mode should return dict, got {type(data)}"
        assert data.get("group_by") == "phase", "group_by should be 'phase'"
    
    def test_group_by_phase_uses_status_labels(self, api_client):
        """Phase groups use proper status labels"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=phase")
        data = response.json()
        groups = data.get("groups", {})
        
        # Valid phase labels
        valid_phases = ["Negoc.", "DESA", "SQA", "Imple.", "PreProd", "Completado"]
        
        for key, group in groups.items():
            assert key in valid_phases, f"Phase key '{key}' not in valid phases"
            if len(group.get("items", [])) > 0:
                statuses = set(item["status"] for item in group["items"])
                assert len(statuses) == 1, "All items in phase group should have same status"
                assert list(statuses)[0] == key, "Items status should match group key"


class TestIntegrationReportAuth:
    """Test authentication requirements"""
    
    def test_report_requires_auth(self):
        """Report endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/banks/integrations/report")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
    
    def test_report_with_invalid_group_returns_flat(self, api_client):
        """Invalid group_by parameter returns flat list"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=invalid")
        assert response.status_code == 200
        data = response.json()
        # Invalid group_by should return flat list
        assert isinstance(data, list), "Invalid group_by should return flat list"


# ==================== PRODUCT EVOLUTION CRUD ====================

class TestProductEvolutionCRUD:
    """Test evolution log CRUD operations"""
    
    def test_get_evolution_empty_list(self, api_client, test_bank_with_integration):
        """Get evolution returns empty list for new integration"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        response = api_client.get(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Evolution should return a list"
    
    def test_create_evolution_entry(self, api_client, test_bank_with_integration):
        """Create a new evolution entry"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        new_entry = {
            "comment": "TEST: Hito técnico de prueba para iteration 80",
            "phase": "DESA",
            "date": datetime.now().strftime("%Y-%m-%d")
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution",
            json=new_entry
        )
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "entry_id" in data, "Response should have entry_id"
        assert data["entry_id"].startswith("pev_"), "entry_id should start with pev_"
        assert data["comment"] == new_entry["comment"], "Comment should match"
        assert data["phase"] == new_entry["phase"], "Phase should match"
        assert data["date"] == new_entry["date"], "Date should match"
        assert "created_at" in data, "Should have created_at"
        
        # Store for cleanup
        test_bank_with_integration["test_entry_id"] = data["entry_id"]
    
    def test_get_evolution_after_create(self, api_client, test_bank_with_integration):
        """Evolution list should contain created entry"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        entry_id = test_bank_with_integration.get("test_entry_id")
        
        if not entry_id:
            pytest.skip("No entry created to verify")
        
        response = api_client.get(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution"
        )
        assert response.status_code == 200
        data = response.json()
        
        found = any(e.get("entry_id") == entry_id for e in data)
        assert found, "Created entry should appear in evolution list"
    
    def test_update_evolution_entry(self, api_client, test_bank_with_integration):
        """Update an evolution entry"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        entry_id = test_bank_with_integration.get("test_entry_id")
        
        if not entry_id:
            pytest.skip("No entry created to update")
        
        update_data = {
            "comment": "TEST: Comentario actualizado en iteration 80",
            "phase": "SQA"
        }
        
        response = api_client.patch(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}",
            json=update_data
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        
        assert data["comment"] == update_data["comment"], "Comment should be updated"
        assert data["phase"] == update_data["phase"], "Phase should be updated"
        assert "updated_at" in data, "Should have updated_at timestamp"
    
    def test_delete_evolution_entry(self, api_client, test_bank_with_integration):
        """Delete an evolution entry"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        entry_id = test_bank_with_integration.get("test_entry_id")
        
        if not entry_id:
            pytest.skip("No entry created to delete")
        
        response = api_client.delete(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}"
        )
        assert response.status_code == 200, f"Delete failed: {response.text}"
        data = response.json()
        assert "message" in data, "Should have success message"
        
        # Verify deletion
        get_response = api_client.get(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution"
        )
        entries = get_response.json()
        found = any(e.get("entry_id") == entry_id for e in entries)
        assert not found, "Deleted entry should not appear in list"


class TestProductEvolutionErrors:
    """Test error handling for evolution endpoints"""
    
    def test_evolution_nonexistent_bank_404(self, api_client):
        """Creating evolution for non-existent bank returns 404"""
        response = api_client.post(
            f"{BASE_URL}/api/banks/nonexistent_bank/integrations/nonexistent_int/evolution",
            json={"comment": "Test", "phase": "DESA", "date": "2025-01-01"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_evolution_nonexistent_integration_404(self, api_client, test_bank_with_integration):
        """Creating evolution for non-existent integration returns 404"""
        bank_id = test_bank_with_integration["bank_id"]
        
        response = api_client.post(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/nonexistent_int/evolution",
            json={"comment": "Test", "phase": "DESA", "date": "2025-01-01"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_update_nonexistent_entry_404(self, api_client, test_bank_with_integration):
        """Updating non-existent entry returns 404"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        response = api_client.patch(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/nonexistent_entry",
            json={"comment": "Updated"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_delete_nonexistent_entry_404(self, api_client, test_bank_with_integration):
        """Deleting non-existent entry returns 404"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        response = api_client.delete(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/nonexistent_entry"
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_update_with_empty_body_400(self, api_client, test_bank_with_integration):
        """Update with no fields returns 400"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        # First create an entry to update
        create_resp = api_client.post(
            f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution",
            json={"comment": "TEST: To delete", "phase": "DESA", "date": "2025-01-01"}
        )
        if create_resp.status_code != 200:
            pytest.skip("Could not create test entry")
        
        entry_id = create_resp.json().get("entry_id")
        
        try:
            response = api_client.patch(
                f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}",
                json={}
            )
            assert response.status_code == 400, f"Expected 400 for empty update, got {response.status_code}"
        finally:
            # Cleanup
            api_client.delete(
                f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}"
            )


class TestProductEvolutionAuth:
    """Test authentication for evolution endpoints"""
    
    def test_get_evolution_requires_auth(self):
        """GET evolution requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/banks/any_bank/integrations/any_int/evolution"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_post_evolution_requires_auth(self):
        """POST evolution requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/banks/any_bank/integrations/any_int/evolution",
            json={"comment": "Test", "phase": "DESA", "date": "2025-01-01"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestEvolutionDateOrder:
    """Test evolution entries are sorted by date descending"""
    
    def test_entries_sorted_descending(self, api_client, test_bank_with_integration):
        """Evolution entries should be sorted by date descending (newest first)"""
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        
        # Create entries with different dates
        entries_created = []
        dates = ["2025-01-10", "2025-01-05", "2025-01-15"]
        
        for date in dates:
            response = api_client.post(
                f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution",
                json={"comment": f"TEST: Entry for {date}", "phase": "DESA", "date": date}
            )
            if response.status_code == 200:
                entries_created.append(response.json().get("entry_id"))
        
        try:
            # Get entries
            response = api_client.get(
                f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution"
            )
            data = response.json()
            
            # Filter to only our test entries
            test_entries = [e for e in data if e.get("entry_id") in entries_created]
            
            if len(test_entries) > 1:
                # Verify descending date order
                for i in range(len(test_entries) - 1):
                    assert test_entries[i]["date"] >= test_entries[i+1]["date"], \
                        f"Entries should be sorted by date descending: {test_entries[i]['date']} >= {test_entries[i+1]['date']}"
        finally:
            # Cleanup
            for entry_id in entries_created:
                api_client.delete(
                    f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}"
                )


# ==================== CLEANUP TEST INTEGRATION IF CREATED ====================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_integration(request, api_client, test_bank_with_integration):
    """Cleanup test integration if we created one"""
    yield
    if test_bank_with_integration.get("created"):
        bank_id = test_bank_with_integration["bank_id"]
        integration_id = test_bank_with_integration["integration_id"]
        api_client.delete(f"{BASE_URL}/api/banks/{bank_id}/integrations/{integration_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
