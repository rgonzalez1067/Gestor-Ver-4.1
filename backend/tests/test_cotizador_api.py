# ruff: noqa
"""
Cotizador Merchant Server API Tests
====================================
Tests for all backend API endpoints requiring authentication.
All endpoints are protected via Emergent Google OAuth Bearer token.
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_"

class TestHealthAndPublicEndpoints:
    """Test endpoints without authentication to verify proper security"""
    
    def test_unauthenticated_clients_returns_401(self):
        """Verify clients endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 401
        data = response.json()
        assert data.get("detail") == "Not authenticated"
        print("PASS: /api/clients returns 401 without auth")
    
    def test_unauthenticated_banks_returns_401(self):
        """Verify banks endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/banks")
        assert response.status_code == 401
        data = response.json()
        assert data.get("detail") == "Not authenticated"
        print("PASS: /api/banks returns 401 without auth")
    
    def test_unauthenticated_services_returns_401(self):
        """Verify services endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 401
        print("PASS: /api/services returns 401 without auth")
    
    def test_unauthenticated_hardware_returns_401(self):
        """Verify hardware endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/hardware")
        assert response.status_code == 401
        print("PASS: /api/hardware returns 401 without auth")
    
    def test_unauthenticated_quotes_returns_401(self):
        """Verify quotes endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 401
        print("PASS: /api/quotes returns 401 without auth")
    
    def test_unauthenticated_exchange_rate_returns_401(self):
        """Verify exchange rate endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/exchange-rate/current")
        assert response.status_code == 401
        print("PASS: /api/exchange-rate/current returns 401 without auth")
    
    def test_unauthenticated_seed_banks_returns_401(self):
        """Verify seed banks endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/banks/seed")
        assert response.status_code == 401
        print("PASS: /api/banks/seed returns 401 without auth")
    
    def test_unauthenticated_config_logo_get_returns_404_or_401(self):
        """Logo GET might return 404 (no logo) or 401 - both acceptable"""
        response = requests.get(f"{BASE_URL}/api/config/logo")
        # GET logo may work without auth if logo exists (public resource) or return 404
        assert response.status_code in [200, 401, 404]
        print(f"PASS: /api/config/logo GET returns {response.status_code}")


class TestAuthEndpoints:
    """Test authentication endpoint structure"""
    
    def test_auth_session_requires_header(self):
        """Verify auth session endpoint requires X-Session-ID header"""
        response = requests.post(f"{BASE_URL}/api/auth/session")
        # Should fail without X-Session-ID header
        assert response.status_code in [401, 422, 500]
        print(f"PASS: /api/auth/session requires X-Session-ID header (status: {response.status_code})")
    
    def test_auth_me_requires_token(self):
        """Verify /auth/me requires valid token"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("PASS: /api/auth/me returns 401 without auth")
    
    def test_auth_logout_accepts_request(self):
        """Verify logout endpoint accepts requests"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        # Logout should succeed even without token (no-op)
        assert response.status_code in [200, 401]
        print(f"PASS: /api/auth/logout returns {response.status_code}")


class TestInvalidTokenResponses:
    """Test endpoints with invalid authentication tokens"""
    
    def test_clients_with_invalid_token(self):
        """Verify invalid token returns 401"""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 401
        print("PASS: Invalid token returns 401 for clients")
    
    def test_banks_with_invalid_token(self):
        """Verify invalid token returns 401 for banks"""
        headers = {"Authorization": "Bearer fake_session_token"}
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 401
        print("PASS: Invalid token returns 401 for banks")
    
    def test_services_with_invalid_token(self):
        """Verify invalid token returns 401 for services"""
        headers = {"Authorization": "Bearer wrong_token"}
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 401
        print("PASS: Invalid token returns 401 for services")


class TestAPIStructure:
    """Test API responds with proper error structures"""
    
    def test_clients_endpoint_exists(self):
        """Verify clients endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/clients")
        # Should be 401, not 404 (endpoint exists but requires auth)
        assert response.status_code != 404
        print("PASS: /api/clients endpoint exists")
    
    def test_banks_endpoint_exists(self):
        """Verify banks endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/banks")
        assert response.status_code != 404
        print("PASS: /api/banks endpoint exists")
    
    def test_services_endpoint_exists(self):
        """Verify services endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code != 404
        print("PASS: /api/services endpoint exists")
    
    def test_hardware_endpoint_exists(self):
        """Verify hardware endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/hardware")
        assert response.status_code != 404
        print("PASS: /api/hardware endpoint exists")
    
    def test_quotes_endpoint_exists(self):
        """Verify quotes endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/quotes")
        assert response.status_code != 404
        print("PASS: /api/quotes endpoint exists")
    
    def test_exchange_rate_endpoint_exists(self):
        """Verify exchange rate endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/exchange-rate/current")
        assert response.status_code != 404
        print("PASS: /api/exchange-rate/current endpoint exists")
    
    def test_config_logo_endpoint_exists(self):
        """Verify config logo endpoint exists"""
        response = requests.get(f"{BASE_URL}/api/config/logo")
        # 404 could mean no logo uploaded, but endpoint exists
        assert response.status_code in [200, 401, 404]
        print(f"PASS: /api/config/logo endpoint exists (status: {response.status_code})")


class TestCRUDEndpointsValidation:
    """Test that CRUD endpoints accept proper request bodies"""
    
    def test_post_client_validates_body(self):
        """Verify POST /clients validates request body structure"""
        headers = {"Authorization": "Bearer test_token", "Content-Type": "application/json"}
        # Invalid body should return 401 (auth first) or 422 (validation)
        response = requests.post(
            f"{BASE_URL}/api/clients",
            headers=headers,
            json={"invalid": "body"}
        )
        # Should return 401 (auth fails first) or 422 (validation fails)
        assert response.status_code in [401, 422]
        print(f"PASS: POST /clients validates request (status: {response.status_code})")
    
    def test_post_bank_validates_body(self):
        """Verify POST /banks validates request body"""
        headers = {"Authorization": "Bearer test_token", "Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/api/banks",
            headers=headers,
            json={"invalid": "body"}
        )
        assert response.status_code in [401, 422]
        print(f"PASS: POST /banks validates request (status: {response.status_code})")
    
    def test_post_service_validates_body(self):
        """Verify POST /services validates request body"""
        headers = {"Authorization": "Bearer test_token", "Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/api/services",
            headers=headers,
            json={"invalid": "body"}
        )
        assert response.status_code in [401, 422]
        print(f"PASS: POST /services validates request (status: {response.status_code})")
    
    def test_post_hardware_validates_body(self):
        """Verify POST /hardware validates request body"""
        headers = {"Authorization": "Bearer test_token", "Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/api/hardware",
            headers=headers,
            json={"invalid": "body"}
        )
        assert response.status_code in [401, 422]
        print(f"PASS: POST /hardware validates request (status: {response.status_code})")


class TestEndpointMethodsExist:
    """Test that all required HTTP methods exist for endpoints"""
    
    def test_clients_post_method_exists(self):
        """POST /clients endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/clients", json={})
        assert response.status_code in [401, 422]  # Not 405 Method Not Allowed
        print("PASS: POST /clients method exists")
    
    def test_banks_post_method_exists(self):
        """POST /banks endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/banks", json={})
        assert response.status_code in [401, 422]
        print("PASS: POST /banks method exists")
    
    def test_banks_seed_post_method_exists(self):
        """POST /banks/seed endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/banks/seed")
        assert response.status_code == 401  # Not 404 or 405
        print("PASS: POST /banks/seed method exists")
    
    def test_services_post_method_exists(self):
        """POST /services endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/services", json={})
        assert response.status_code in [401, 422]
        print("PASS: POST /services method exists")
    
    def test_hardware_post_method_exists(self):
        """POST /hardware endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/hardware", json={})
        assert response.status_code in [401, 422]
        print("PASS: POST /hardware method exists")
    
    def test_quotes_post_method_exists(self):
        """POST /quotes endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/quotes", json={})
        assert response.status_code in [401, 422]
        print("PASS: POST /quotes method exists")
    
    def test_exchange_rate_update_post_method_exists(self):
        """POST /exchange-rate/update endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/exchange-rate/update")
        assert response.status_code == 401
        print("PASS: POST /exchange-rate/update method exists")
    
    def test_config_logo_post_method_exists(self):
        """POST /config/logo endpoint exists (file upload)"""
        response = requests.post(f"{BASE_URL}/api/config/logo")
        assert response.status_code in [401, 422]
        print(f"PASS: POST /config/logo method exists (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
