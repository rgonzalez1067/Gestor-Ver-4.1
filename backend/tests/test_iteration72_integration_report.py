# ruff: noqa
"""
Iteration 72 - Integration Report Feature Tests
Tests for GET /api/banks/integrations/report endpoint and related functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "rgonzalez@megasoft.com.ve",
        "password": "Avila*0226*02"
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


class TestIntegrationReportEndpoint:
    """Test GET /api/banks/integrations/report endpoint"""
    
    def test_report_returns_200(self, api_client):
        """Report endpoint should return 200 status"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_report_returns_list(self, api_client):
        """Report should return a list"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        assert isinstance(data, list), "Report should return a list"
    
    def test_report_entry_has_required_fields(self, api_client):
        """Each report entry should have required fields"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            required_fields = ['bank_id', 'bank_name', 'service_name', 'component_type', 'status', 'notes']
            for field in required_fields:
                assert field in entry, f"Missing required field: {field}"
    
    def test_report_entry_has_integration_id(self, api_client):
        """Each report entry should have integration_id for navigation"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            assert 'integration_id' in entry, "Missing integration_id field"
            assert entry['integration_id'].startswith('int_'), "integration_id should start with int_"
    
    def test_report_includes_bank_logo_url(self, api_client):
        """Each report entry should have bank_logo_url field (can be null)"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        
        if len(data) > 0:
            entry = data[0]
            assert 'bank_logo_url' in entry, "Missing bank_logo_url field"
    
    def test_report_sorted_by_phase_priority(self, api_client):
        """Report should be sorted by phase priority (most advanced first)"""
        response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        data = response.json()
        
        # Phase order: Completado=0, PreProd=1, Imple.=2, SQA=3, DESA=4, Negoc.=5
        PHASE_ORDER = {"Completado": 0, "PreProd": 1, "Imple.": 2, "SQA": 3, "DESA": 4, "Negoc.": 5}
        
        if len(data) > 1:
            prev_priority = -1
            for entry in data:
                status = entry.get('status', '')
                priority = PHASE_ORDER.get(status, 99)
                # Each entry should have priority >= previous (lower priority values are more advanced)
                assert priority >= prev_priority, f"Sorting error: {status} should come after previous status"
                prev_priority = priority
    
    def test_report_requires_auth(self):
        """Report endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/banks/integrations/report")
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"


class TestIntegrationCRUD:
    """Test integration CRUD operations and report reflection"""
    
    @pytest.fixture
    def test_bank_id(self, api_client):
        """Get a bank ID for testing"""
        response = api_client.get(f"{BASE_URL}/api/banks")
        data = response.json()
        assert len(data) > 0, "No banks found for testing"
        return data[0]['bank_id']
    
    def test_create_integration_appears_in_report(self, api_client, test_bank_id):
        """Creating an integration should make it appear in the report"""
        # Create a test integration
        new_integration = {
            "service_name": "TEST_Integration_Report",
            "component_type": "VPOS/MPOS",
            "status": "DESA",
            "notes": "Test integration for iteration 72"
        }
        
        create_response = api_client.post(
            f"{BASE_URL}/api/banks/{test_bank_id}/integrations",
            json=new_integration
        )
        assert create_response.status_code == 200, f"Failed to create integration: {create_response.text}"
        created = create_response.json()
        integration_id = created.get('integration_id')
        
        try:
            # Check it appears in report
            report_response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
            report_data = report_response.json()
            
            found = any(
                entry.get('integration_id') == integration_id 
                for entry in report_data
            )
            assert found, "Created integration not found in report"
            
        finally:
            # Cleanup - delete the test integration
            api_client.delete(f"{BASE_URL}/api/banks/{test_bank_id}/integrations/{integration_id}")
    
    def test_delete_integration_removes_from_report(self, api_client, test_bank_id):
        """Deleting an integration should remove it from the report"""
        # Create a test integration
        new_integration = {
            "service_name": "TEST_Delete_From_Report",
            "component_type": "PG/Link",
            "status": "Negoc.",
            "notes": "Test deletion from report"
        }
        
        create_response = api_client.post(
            f"{BASE_URL}/api/banks/{test_bank_id}/integrations",
            json=new_integration
        )
        assert create_response.status_code == 200
        created = create_response.json()
        integration_id = created.get('integration_id')
        
        # Verify it's in the report
        report_response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        found_before = any(
            entry.get('integration_id') == integration_id 
            for entry in report_response.json()
        )
        assert found_before, "Integration should be in report before deletion"
        
        # Delete the integration
        delete_response = api_client.delete(f"{BASE_URL}/api/banks/{test_bank_id}/integrations/{integration_id}")
        assert delete_response.status_code == 200
        
        # Verify it's no longer in the report
        report_response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
        found_after = any(
            entry.get('integration_id') == integration_id 
            for entry in report_response.json()
        )
        assert not found_after, "Deleted integration should not be in report"
    
    def test_update_integration_status_changes_sort_order(self, api_client, test_bank_id):
        """Updating integration status should affect report sorting"""
        # Create a test integration with low priority (Negoc.)
        new_integration = {
            "service_name": "TEST_Sort_Order",
            "component_type": "VPOS/MPOS",
            "status": "Negoc.",
            "notes": "Test sort order change"
        }
        
        create_response = api_client.post(
            f"{BASE_URL}/api/banks/{test_bank_id}/integrations",
            json=new_integration
        )
        assert create_response.status_code == 200
        created = create_response.json()
        integration_id = created.get('integration_id')
        
        try:
            # Update to high priority status (PreProd)
            update_response = api_client.put(
                f"{BASE_URL}/api/banks/{test_bank_id}/integrations/{integration_id}",
                json={"status": "PreProd"}
            )
            assert update_response.status_code == 200
            
            # Verify the report contains the updated status
            report_response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
            report_data = report_response.json()
            
            test_entry = next(
                (e for e in report_data if e.get('integration_id') == integration_id),
                None
            )
            assert test_entry is not None, "Integration not found in report"
            assert test_entry['status'] == 'PreProd', f"Status should be PreProd, got {test_entry['status']}"
            
        finally:
            # Cleanup
            api_client.delete(f"{BASE_URL}/api/banks/{test_bank_id}/integrations/{integration_id}")


class TestStatusPhasePriority:
    """Test phase priority sorting with different statuses"""
    
    @pytest.fixture
    def test_bank_id(self, api_client):
        """Get a bank ID for testing"""
        response = api_client.get(f"{BASE_URL}/api/banks")
        data = response.json()
        return data[0]['bank_id']
    
    def test_preprod_sorts_before_sqa(self, api_client, test_bank_id):
        """PreProd integrations should appear before SQA in report"""
        # Create two integrations with different statuses
        integrations_created = []
        
        sqa_integration = {
            "service_name": "TEST_SQA_Sort",
            "component_type": "VPOS/MPOS",
            "status": "SQA",
            "notes": "SQA test"
        }
        
        preprod_integration = {
            "service_name": "TEST_PreProd_Sort",
            "component_type": "VPOS/MPOS", 
            "status": "PreProd",
            "notes": "PreProd test"
        }
        
        # Create SQA first
        res1 = api_client.post(f"{BASE_URL}/api/banks/{test_bank_id}/integrations", json=sqa_integration)
        assert res1.status_code == 200
        integrations_created.append(res1.json().get('integration_id'))
        
        # Create PreProd second
        res2 = api_client.post(f"{BASE_URL}/api/banks/{test_bank_id}/integrations", json=preprod_integration)
        assert res2.status_code == 200
        integrations_created.append(res2.json().get('integration_id'))
        
        try:
            # Get report
            report_response = api_client.get(f"{BASE_URL}/api/banks/integrations/report")
            report_data = report_response.json()
            
            # Find positions
            preprod_idx = None
            sqa_idx = None
            for idx, entry in enumerate(report_data):
                if entry.get('service_name') == 'TEST_PreProd_Sort':
                    preprod_idx = idx
                if entry.get('service_name') == 'TEST_SQA_Sort':
                    sqa_idx = idx
            
            assert preprod_idx is not None, "PreProd integration not found in report"
            assert sqa_idx is not None, "SQA integration not found in report"
            assert preprod_idx < sqa_idx, f"PreProd should come before SQA (PreProd idx={preprod_idx}, SQA idx={sqa_idx})"
            
        finally:
            # Cleanup
            for int_id in integrations_created:
                api_client.delete(f"{BASE_URL}/api/banks/{test_bank_id}/integrations/{int_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
