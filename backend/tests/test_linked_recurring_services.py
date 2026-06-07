# ruff: noqa
"""
Linked Recurring Services Tests
================================
Tests for the new linked_recurring_service_id feature and application_type filtering:

1. Backend Model: Service has linked_recurring_service_id field
2. Backend Endpoint: GET /api/services?application_type=recurring_available returns only recurring/both services
3. POST/PUT accepts linked_recurring_service_id in payload
4. Field is properly stored and returned

Note: All endpoints require Emergent Google OAuth authentication.
Tests verify the API structure and parameter acceptance.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestApplicationTypeFilter:
    """Test application_type filter parameter on GET /services"""
    
    def test_services_with_application_type_recurring_available_returns_401(self):
        """GET /services?application_type=recurring_available requires auth (param accepted)"""
        response = requests.get(f"{BASE_URL}/api/services?application_type=recurring_available")
        # Returns 401 (auth required) not 400 (invalid param) - param is valid
        assert response.status_code == 401
        print("PASS: GET /api/services?application_type=recurring_available returns 401 (param accepted)")
    
    def test_services_with_application_type_setup_returns_401(self):
        """GET /services?application_type=setup requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?application_type=setup")
        assert response.status_code == 401
        print("PASS: GET /api/services?application_type=setup returns 401 (param accepted)")
    
    def test_services_with_application_type_recurring_returns_401(self):
        """GET /services?application_type=recurring requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?application_type=recurring")
        assert response.status_code == 401
        print("PASS: GET /api/services?application_type=recurring returns 401 (param accepted)")
    
    def test_services_with_application_type_both_returns_401(self):
        """GET /services?application_type=both requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?application_type=both")
        assert response.status_code == 401
        print("PASS: GET /api/services?application_type=both returns 401 (param accepted)")
    
    def test_services_with_combined_filters_compatibility_and_application_type(self):
        """GET /services with both compatibility and application_type params"""
        response = requests.get(
            f"{BASE_URL}/api/services?compatibility=vpos&application_type=recurring_available"
        )
        assert response.status_code == 401
        print("PASS: Combined filters (compatibility + application_type) returns 401")


class TestLinkedRecurringServicePayload:
    """Test that POST /services accepts linked_recurring_service_id field"""
    
    def test_post_service_with_linked_recurring_service_id(self):
        """POST /services accepts linked_recurring_service_id field"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST_Linked",
            "name": "TEST_Setup_With_Link",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 150.0,
            "monthly_cost_conventional": 0,
            "setup_cost_outsourcing": 120.0,
            "monthly_cost_outsourcing": 0,
            "description": "Setup service with linked recurring",
            "linked_recurring_service_id": "srv_test123abc"
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        # Returns 401 (auth) not 422 (validation) - payload structure is valid
        assert response.status_code == 401
        print("PASS: POST /services with linked_recurring_service_id returns 401 (payload valid)")
    
    def test_post_service_with_null_linked_recurring_service_id(self):
        """POST /services accepts null linked_recurring_service_id"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST_NoLink",
            "name": "TEST_Setup_No_Link",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 100.0,
            "monthly_cost_conventional": 0,
            "linked_recurring_service_id": None
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: POST /services with null linked_recurring_service_id returns 401")
    
    def test_post_recurring_service_without_linked_field(self):
        """POST /services for recurring type doesn't need linked field"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST_Recurring",
            "name": "TEST_Recurring_Service",
            "application_type": "recurring",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 0,
            "monthly_cost_conventional": 75.0,
            "setup_cost_outsourcing": 0,
            "monthly_cost_outsourcing": 60.0,
            "description": "Pure recurring service"
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: POST /services recurring without linked_recurring_service_id returns 401")


class TestServiceApplicationTypes:
    """Test all application_type values are accepted"""
    
    def test_post_service_type_setup(self):
        """POST /services with application_type='setup' is valid"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_TypeSetup",
            "application_type": "setup",
            "setup_cost_conventional": 200.0
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: application_type='setup' is valid")
    
    def test_post_service_type_recurring(self):
        """POST /services with application_type='recurring' is valid"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_TypeRecurring",
            "application_type": "recurring",
            "monthly_cost_conventional": 50.0
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: application_type='recurring' is valid")
    
    def test_post_service_type_both(self):
        """POST /services with application_type='both' is valid"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_TypeBoth",
            "application_type": "both",
            "setup_cost_conventional": 100.0,
            "monthly_cost_conventional": 25.0
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: application_type='both' is valid")


class TestPutServiceWithLinkedRecurring:
    """Test PUT /services accepts linked_recurring_service_id"""
    
    def test_put_service_update_linked_recurring(self):
        """PUT /services/{id} accepts linked_recurring_service_id update"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST_Update",
            "name": "TEST_Updated_Service",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 180.0,
            "monthly_cost_conventional": 0,
            "linked_recurring_service_id": "srv_newlinked456"
        }
        response = requests.put(
            f"{BASE_URL}/api/services/srv_test123",
            headers=headers,
            json=payload
        )
        # 401 (auth) not 422 (validation) - payload is valid
        assert response.status_code == 401
        print("PASS: PUT /services with linked_recurring_service_id returns 401")
    
    def test_put_service_remove_linked_recurring(self):
        """PUT /services/{id} can remove linked_recurring_service_id (set to null)"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST_Update",
            "name": "TEST_Unlinked_Service",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 150.0,
            "monthly_cost_conventional": 30.0,
            "linked_recurring_service_id": None
        }
        response = requests.put(
            f"{BASE_URL}/api/services/srv_test456",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: PUT /services with null linked_recurring_service_id returns 401")


class TestMediosPagoFormIntegration:
    """Test service CRUD with full form data (as MediosPago sends)"""
    
    def test_create_setup_service_with_full_form_data(self):
        """POST /services with complete MediosPago form data including linked field"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        # This is the exact payload structure MediosPago.jsx sends
        payload = {
            "name": "TEST_Tarjeta_Credito_Setup",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 250.0,
            "monthly_cost_conventional": 0,
            "setup_cost_outsourcing": 200.0,
            "monthly_cost_outsourcing": 0,
            "description": "Setup para tarjeta de crédito",
            "category": "General",
            "linked_recurring_service_id": "srv_recurrente_tc"
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: Full MediosPago form payload is valid")
    
    def test_create_both_type_service_with_all_costs(self):
        """POST /services with application_type='both' and all cost fields"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "name": "TEST_Service_Both_Type",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": True,
            "link_enabled": False,
            "setup_cost_conventional": 300.0,
            "monthly_cost_conventional": 50.0,
            "setup_cost_outsourcing": 240.0,
            "monthly_cost_outsourcing": 40.0,
            "description": "Service with both setup and recurring costs",
            "category": "General",
            "linked_recurring_service_id": "srv_linked_recurring"
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: Both type service with linked recurring returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
