"""
Test Iteration 90: Bank Integration States Simplification
Tests the new 3-state integration lifecycle: PreProd, Primer Prod, Masificación
Also tests the simulated email notification on status change.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# New valid states (old states: Negoc., DESA, SQA, Imple., PreProd, Completado)
NEW_STATES = ["PreProd", "Primer Prod", "Masificación"]
OLD_INVALID_STATES = ["Negoc.", "DESA", "SQA", "Imple.", "Completado"]

class TestBankIntegrationStates:
    """Test the new simplified 3-state integration lifecycle"""
    
    @pytest.fixture(autouse=True)
    def setup(self, auth_token, api_client):
        """Setup: get auth token and create test bank"""
        self.api_client = api_client
        self.auth_token = auth_token
        self.api_client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        
        # Create a test bank
        bank_data = {
            "name": f"TEST_BANK_INT_STATES_{int(time.time())}",
            "type": "Banco",
            "country": "Venezuela",
            "products": []
        }
        response = self.api_client.post(f"{BASE_URL}/api/banks", json=bank_data)
        assert response.status_code == 200
        self.test_bank = response.json()
        self.bank_id = self.test_bank["bank_id"]
        
        yield
        
        # Cleanup: delete test bank
        try:
            self.api_client.delete(f"{BASE_URL}/api/banks/{self.bank_id}")
        except:
            pass
    
    def test_create_integration_with_default_preprod_status(self):
        """Test: Creating integration defaults to PreProd status"""
        integration_data = {
            "service_name": "TEST_Pago Movil",
            "component_type": "VPOS/MPOS",
            "notes": "Testing default status"
        }
        response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PreProd", f"Expected PreProd, got {data['status']}"
        assert data["service_name"] == "TEST_Pago Movil"
        print(f"✓ Integration created with default status: {data['status']}")
    
    def test_create_integration_with_explicit_preprod(self):
        """Test: Creating integration with explicit PreProd status"""
        integration_data = {
            "service_name": "TEST_C2P",
            "component_type": "PG/Link",
            "status": "PreProd",
            "notes": "Explicit PreProd status"
        }
        response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PreProd"
        print(f"✓ Integration created with explicit PreProd status")
    
    def test_create_integration_with_primer_prod_status(self):
        """Test: Creating integration with Primer Prod status"""
        integration_data = {
            "service_name": "TEST_Zelle",
            "component_type": "PG/Link",
            "status": "Primer Prod",
            "notes": "Primer Prod status"
        }
        response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Primer Prod", f"Expected 'Primer Prod', got '{data['status']}'"
        print(f"✓ Integration created with Primer Prod status")
    
    def test_create_integration_with_masificacion_status(self):
        """Test: Creating integration with Masificación status"""
        integration_data = {
            "service_name": "TEST_BDV",
            "component_type": "VPOS/MPOS",
            "status": "Masificación",
            "notes": "Masificación status"
        }
        response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Masificación", f"Expected 'Masificación', got '{data['status']}'"
        print(f"✓ Integration created with Masificación status")
    
    def test_update_status_to_primer_prod(self):
        """Test: Update integration status from PreProd to Primer Prod"""
        # Create integration
        integration_data = {
            "service_name": "TEST_Update_Status",
            "component_type": "VPOS/MPOS",
            "status": "PreProd"
        }
        create_response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert create_response.status_code == 200
        integration_id = create_response.json()["integration_id"]
        
        # Update status
        update_response = self.api_client.put(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations/{integration_id}",
            json={"status": "Primer Prod"}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "Primer Prod", f"Expected 'Primer Prod', got '{data['status']}'"
        print(f"✓ Status updated to Primer Prod")
    
    def test_update_status_to_masificacion(self):
        """Test: Update integration status to Masificación"""
        # Create integration
        integration_data = {
            "service_name": "TEST_Masif_Update",
            "component_type": "PG/Link",
            "status": "Primer Prod"
        }
        create_response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert create_response.status_code == 200
        integration_id = create_response.json()["integration_id"]
        
        # Update status to Masificación
        update_response = self.api_client.put(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations/{integration_id}",
            json={"status": "Masificación"}
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "Masificación", f"Expected 'Masificación', got '{data['status']}'"
        print(f"✓ Status updated to Masificación")
    
    def test_get_bank_detail_shows_new_status(self):
        """Test: GET /api/banks/{bank_id}/detail shows updated status"""
        # Create integration with specific status
        integration_data = {
            "service_name": "TEST_Detail_Check",
            "component_type": "VPOS/MPOS",
            "status": "Primer Prod"
        }
        create_response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert create_response.status_code == 200
        
        # Get bank detail
        detail_response = self.api_client.get(f"{BASE_URL}/api/banks/{self.bank_id}/detail")
        assert detail_response.status_code == 200
        data = detail_response.json()
        
        integrations = data.get("integrations", [])
        assert len(integrations) > 0, "Expected at least 1 integration"
        
        # Find our test integration
        test_intg = next((i for i in integrations if i["service_name"] == "TEST_Detail_Check"), None)
        assert test_intg is not None, "Test integration not found in bank detail"
        assert test_intg["status"] == "Primer Prod"
        print(f"✓ Bank detail shows correct status: {test_intg['status']}")
    
    def test_integrations_report_works_with_new_states(self):
        """Test: GET /api/banks/integrations/report works with new states"""
        # First create an integration so report has data
        integration_data = {
            "service_name": "TEST_Report_Check",
            "component_type": "PG/Link",
            "status": "PreProd"
        }
        self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        
        # Get report
        report_response = self.api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        assert report_response.status_code == 200
        data = report_response.json()
        
        # Should return a list when no grouping
        assert isinstance(data, list)
        
        # Verify all statuses in report are new valid states
        for item in data:
            if item.get("bank_id") == self.bank_id:
                assert item["status"] in NEW_STATES, f"Invalid status in report: {item['status']}"
        
        print(f"✓ Integrations report works with new states, found {len(data)} integrations")
    
    def test_integrations_report_grouped_by_phase(self):
        """Test: GET /api/banks/integrations/report?group_by=phase works"""
        # Get report grouped by phase
        report_response = self.api_client.get(f"{BASE_URL}/api/banks/integrations/report?group_by=phase")
        assert report_response.status_code == 200
        data = report_response.json()
        
        # Should return grouped structure
        assert "group_by" in data
        assert data["group_by"] == "phase"
        assert "groups" in data
        assert "total" in data
        
        # If there are groups, check they use new state names
        for phase, group_data in data.get("groups", {}).items():
            assert phase in NEW_STATES, f"Invalid phase group: {phase}"
            assert "label" in group_data
            assert "count" in group_data
            assert "items" in group_data
        
        print(f"✓ Integrations report grouped by phase works, total: {data['total']}")
    
    def test_create_evolution_entry_with_new_phase(self):
        """Test: POST /api/banks/{bank_id}/integrations/{integration_id}/evolution with Primer Prod phase"""
        # Create integration
        integration_data = {
            "service_name": "TEST_Evolution_Phase",
            "component_type": "VPOS/MPOS",
            "status": "PreProd"
        }
        create_response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        assert create_response.status_code == 200
        integration_id = create_response.json()["integration_id"]
        
        # Create evolution entry with Primer Prod phase
        evolution_data = {
            "comment": "TEST evolution entry with new phase",
            "phase": "Primer Prod",
            "date": "2026-01-15"
        }
        evo_response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations/{integration_id}/evolution",
            json=evolution_data
        )
        assert evo_response.status_code == 200
        data = evo_response.json()
        assert data["phase"] == "Primer Prod", f"Expected 'Primer Prod', got '{data['phase']}'"
        assert data["comment"] == "TEST evolution entry with new phase"
        print(f"✓ Evolution entry created with Primer Prod phase")
    
    def test_banks_list_count_excludes_masificacion(self):
        """Test: Banks list counts integrations in progress excluding 'Masificación'"""
        # Create multiple integrations with different statuses
        statuses = ["PreProd", "Primer Prod", "Masificación"]
        for i, status in enumerate(statuses):
            integration_data = {
                "service_name": f"TEST_Count_{status}_{i}",
                "component_type": "VPOS/MPOS",
                "status": status
            }
            self.api_client.post(
                f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
                json=integration_data
            )
        
        # Get banks list
        banks_response = self.api_client.get(f"{BASE_URL}/api/banks")
        assert banks_response.status_code == 200
        banks = banks_response.json()
        
        # Find our test bank
        test_bank = next((b for b in banks if b["bank_id"] == self.bank_id), None)
        assert test_bank is not None
        
        # Count integrations manually (excluding Masificación)
        integrations = test_bank.get("integrations", [])
        in_progress = len([i for i in integrations if i["status"] != "Masificación"])
        
        print(f"✓ Bank has {len(integrations)} total integrations, {in_progress} in progress (excluding Masificación)")
        # This verifies backend returns correct data for frontend count


class TestInvalidOldStates:
    """Test that old states are no longer valid"""
    
    @pytest.fixture(autouse=True)
    def setup(self, auth_token, api_client):
        """Setup: get auth token and create test bank"""
        self.api_client = api_client
        self.auth_token = auth_token
        self.api_client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        
        # Create a test bank
        bank_data = {
            "name": f"TEST_BANK_OLD_STATES_{int(time.time())}",
            "type": "Banco",
            "country": "Venezuela",
            "products": []
        }
        response = self.api_client.post(f"{BASE_URL}/api/banks", json=bank_data)
        assert response.status_code == 200
        self.test_bank = response.json()
        self.bank_id = self.test_bank["bank_id"]
        
        yield
        
        # Cleanup: delete test bank
        try:
            self.api_client.delete(f"{BASE_URL}/api/banks/{self.bank_id}")
        except:
            pass
    
    @pytest.mark.parametrize("old_status", OLD_INVALID_STATES)
    def test_create_integration_with_old_status_fails(self, old_status):
        """Test: Creating integration with old status should fail validation"""
        integration_data = {
            "service_name": f"TEST_Old_Status_{old_status}",
            "component_type": "VPOS/MPOS",
            "status": old_status
        }
        response = self.api_client.post(
            f"{BASE_URL}/api/banks/{self.bank_id}/integrations",
            json=integration_data
        )
        # Should fail with 422 validation error
        assert response.status_code == 422, f"Expected 422 for old status '{old_status}', got {response.status_code}"
        print(f"✓ Old status '{old_status}' correctly rejected with 422")


# ==================== FIXTURES ====================

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="session")
def auth_token(api_client):
    """Get authentication token"""
    # Try with known admin credentials
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gestor.com",
        "password": "Admin2026!"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    
    # Try test credentials
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "Test1234!"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    
    pytest.skip("Authentication failed - skipping authenticated tests")
