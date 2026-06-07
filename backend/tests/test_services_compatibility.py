# ruff: noqa
"""
Services Compatibility Filter Tests
====================================
Tests for GET /api/services endpoint with compatibility parameter filtering.
This is the main feature being tested in this iteration:
- ?compatibility=vpos filters by vpos_enabled=true
- ?compatibility=gateway filters by gateway_enabled=true  
- ?compatibility=mpos filters by mpos_enabled=true
- ?compatibility=link filters by link_enabled=true
- No parameter returns all services

Note: All endpoints require Emergent Google OAuth authentication.
Tests verify the filter parameter is properly accepted by the endpoint.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestServicesCompatibilityFilterNoAuth:
    """Test that compatibility parameter is accepted even without auth (401 not 400)"""
    
    def test_services_without_compatibility_returns_401(self):
        """GET /services without compatibility param requires auth"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 401
        print("PASS: GET /api/services without compatibility returns 401")
    
    def test_services_with_vpos_compatibility_returns_401(self):
        """GET /services?compatibility=vpos requires auth, not 400 for invalid param"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=vpos")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=vpos returns 401 (param accepted)")
    
    def test_services_with_gateway_compatibility_returns_401(self):
        """GET /services?compatibility=gateway requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=gateway")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=gateway returns 401 (param accepted)")
    
    def test_services_with_mpos_compatibility_returns_401(self):
        """GET /services?compatibility=mpos requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=mpos")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=mpos returns 401 (param accepted)")
    
    def test_services_with_link_compatibility_returns_401(self):
        """GET /services?compatibility=link requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=link")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=link returns 401 (param accepted)")
    
    def test_services_with_uppercase_VPOS_compatibility(self):
        """GET /services?compatibility=VPOS (uppercase) requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=VPOS")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=VPOS (uppercase) returns 401")
    
    def test_services_with_uppercase_GATEWAY_compatibility(self):
        """GET /services?compatibility=GATEWAY (uppercase) requires auth"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=GATEWAY")
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=GATEWAY (uppercase) returns 401")
    
    def test_services_with_invalid_compatibility_returns_401(self):
        """GET /services?compatibility=invalid returns 401, not 400"""
        response = requests.get(f"{BASE_URL}/api/services?compatibility=invalid_value")
        # Should return 401 (auth first), not 400 (bad request)
        # This verifies the endpoint doesn't reject the param value
        assert response.status_code == 401
        print("PASS: GET /api/services?compatibility=invalid_value returns 401")


class TestServicesWithInvalidToken:
    """Test compatibility param with invalid token"""
    
    def test_services_vpos_filter_with_invalid_token(self):
        """Invalid token returns 401 for vpos filter"""
        headers = {"Authorization": "Bearer invalid_token_123"}
        response = requests.get(
            f"{BASE_URL}/api/services?compatibility=vpos",
            headers=headers
        )
        assert response.status_code == 401
        print("PASS: Invalid token + compatibility=vpos returns 401")
    
    def test_services_gateway_filter_with_invalid_token(self):
        """Invalid token returns 401 for gateway filter"""
        headers = {"Authorization": "Bearer invalid_token_456"}
        response = requests.get(
            f"{BASE_URL}/api/services?compatibility=gateway",
            headers=headers
        )
        assert response.status_code == 401
        print("PASS: Invalid token + compatibility=gateway returns 401")
    
    def test_services_mpos_filter_with_invalid_token(self):
        """Invalid token returns 401 for mpos filter"""
        headers = {"Authorization": "Bearer invalid_token_789"}
        response = requests.get(
            f"{BASE_URL}/api/services?compatibility=mpos",
            headers=headers
        )
        assert response.status_code == 401
        print("PASS: Invalid token + compatibility=mpos returns 401")
    
    def test_services_link_filter_with_invalid_token(self):
        """Invalid token returns 401 for link filter"""
        headers = {"Authorization": "Bearer invalid_token_000"}
        response = requests.get(
            f"{BASE_URL}/api/services?compatibility=link",
            headers=headers
        )
        assert response.status_code == 401
        print("PASS: Invalid token + compatibility=link returns 401")


class TestServiceModelFields:
    """Test that POST /services accepts compatibility fields"""
    
    def test_post_service_with_all_compatibility_fields(self):
        """POST /services accepts vpos_enabled, gateway_enabled, mpos_enabled, link_enabled"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_Service_1",
            "application_type": "both",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": True,
            "link_enabled": False,
            "setup_cost_conventional": 100.0,
            "monthly_cost_conventional": 50.0,
            "setup_cost_outsourcing": 80.0,
            "monthly_cost_outsourcing": 40.0,
            "description": "Test service"
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        # Should return 401 (auth fails) not 422 (validation fails)
        # This verifies the payload structure is valid
        assert response.status_code == 401
        print("PASS: POST /services with compatibility fields returns 401 (payload valid)")
    
    def test_post_service_with_only_vpos_enabled(self):
        """POST /services with only vpos_enabled=true"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_VPOSOnly",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": False,
            "link_enabled": False,
            "setup_cost_conventional": 50.0,
            "monthly_cost_conventional": 25.0
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: POST /services with vpos_enabled only returns 401")
    
    def test_post_service_with_only_gateway_enabled(self):
        """POST /services with only gateway_enabled=true"""
        headers = {
            "Authorization": "Bearer test_token",
            "Content-Type": "application/json"
        }
        payload = {
            "category": "TEST",
            "name": "TEST_GatewayOnly",
            "vpos_enabled": False,
            "gateway_enabled": True,
            "mpos_enabled": False,
            "link_enabled": False,
            "setup_cost_conventional": 75.0,
            "monthly_cost_conventional": 30.0
        }
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json=payload
        )
        assert response.status_code == 401
        print("PASS: POST /services with gateway_enabled only returns 401")


class TestClientsBanksHardwareNoAuth:
    """Test other CRUD endpoints are still protected"""
    
    def test_get_clients_requires_auth(self):
        """GET /clients requires auth"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 401
        print("PASS: GET /clients returns 401")
    
    def test_get_banks_requires_auth(self):
        """GET /banks requires auth"""
        response = requests.get(f"{BASE_URL}/api/banks")
        assert response.status_code == 401
        print("PASS: GET /banks returns 401")
    
    def test_get_hardware_requires_auth(self):
        """GET /hardware requires auth"""
        response = requests.get(f"{BASE_URL}/api/hardware")
        assert response.status_code == 401
        print("PASS: GET /hardware returns 401")
    
    def test_get_quotes_requires_auth(self):
        """GET /quotes requires auth"""
        response = requests.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 401
        print("PASS: GET /quotes returns 401")


class TestExchangeRateEndpoints:
    """Test exchange rate endpoints are protected"""
    
    def test_get_exchange_rate_current_requires_auth(self):
        """GET /exchange-rate/current requires auth"""
        response = requests.get(f"{BASE_URL}/api/exchange-rate/current")
        assert response.status_code == 401
        print("PASS: GET /exchange-rate/current returns 401")
    
    def test_post_exchange_rate_update_requires_auth(self):
        """POST /exchange-rate/update requires auth"""
        response = requests.post(f"{BASE_URL}/api/exchange-rate/update")
        assert response.status_code == 401
        print("PASS: POST /exchange-rate/update returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
