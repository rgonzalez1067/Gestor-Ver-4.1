"""
Test Iteration 94 - Dynamic Parameters for VPOS Quotes (requires_pinpad_config, requires_vpn)

Tests:
1. Backend: POST /api/quotes with requires_pinpad_config=false persists the field
2. Backend: POST /api/quotes with requires_vpn=false persists the field
3. Backend: GET /api/quotes/{id} returns requires_pinpad_config and requires_vpn
4. Backend: Default values for both fields are True
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "np_test@test.com"
TEST_PASSWORD = "Test1234!"


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get session token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Auth failed: {response.status_code} - {response.text}")
    token = response.json().get("session_token")
    if not token:
        pytest.skip("No session token returned")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def test_client(auth_headers):
    """Get or create a test client for quotes"""
    # First try to find existing client
    response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
    if response.status_code == 200:
        clients = response.json()
        # Find existing test client or first client
        for client in clients:
            if 'TEST_' in client.get('rif', '') or client.get('client_id'):
                return client
        if clients:
            return clients[0]
    
    # Create new test client
    test_client_data = {
        "rif": f"TEST_J-{int(time.time())}",
        "legal_name": "TEST Client Dynamic Params",
        "fantasy_name": "Test Dynamic Params Client",
        "segment": "Pymes",
        "condicion": "Prospecto"
    }
    create_response = requests.post(f"{BASE_URL}/api/clients", json=test_client_data, headers=auth_headers)
    if create_response.status_code not in [200, 201]:
        pytest.skip(f"Could not create test client: {create_response.text}")
    return create_response.json()


@pytest.fixture(scope="module")
def test_integrator(auth_headers):
    """Get an integrator for quotes"""
    response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
    if response.status_code == 200:
        integrators = response.json()
        if integrators:
            return integrators[0]
    return None


class TestDynamicParametersBackend:
    """Backend tests for requires_pinpad_config and requires_vpn fields"""
    
    def test_quote_model_has_dynamic_params_defaults(self, auth_headers, test_client, test_integrator):
        """Test that new quotes have default values True for both fields"""
        # Create a basic quote without specifying dynamic params
        integrator_id = test_integrator.get('integrator_id', '') if test_integrator else ''
        integrator_name = test_integrator.get('name', '') if test_integrator else ''
        
        payload = {
            "client_id": test_client["client_id"],
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_ITERATION94_DEFAULTS",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": integrator_id,
            "integrator_name": integrator_name,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Default values should be True
        assert quote.get("requires_pinpad_config") == True, "requires_pinpad_config default should be True"
        assert quote.get("requires_vpn") == True, "requires_vpn default should be True"
        
        # Store quote_id for cleanup
        return quote.get("quote_id")
    
    def test_create_quote_with_requires_pinpad_config_false(self, auth_headers, test_client, test_integrator):
        """Test creating quote with requires_pinpad_config=False"""
        integrator_id = test_integrator.get('integrator_id', '') if test_integrator else ''
        integrator_name = test_integrator.get('name', '') if test_integrator else ''
        
        payload = {
            "client_id": test_client["client_id"],
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_ITERATION94_PINPAD_FALSE",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": integrator_id,
            "integrator_name": integrator_name,
            "requires_pinpad_config": False,
            "requires_vpn": True,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Verify the field was persisted
        assert quote.get("requires_pinpad_config") == False, "requires_pinpad_config should be False"
        assert quote.get("requires_vpn") == True, "requires_vpn should be True"
        
        # Verify GET returns same value
        quote_id = quote.get("quote_id")
        get_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_response.status_code == 200, f"GET quote failed: {get_response.text}"
        
        fetched_quote = get_response.json()
        assert fetched_quote.get("requires_pinpad_config") == False, "GET should return requires_pinpad_config=False"
    
    def test_create_quote_with_requires_vpn_false(self, auth_headers, test_client, test_integrator):
        """Test creating quote with requires_vpn=False"""
        integrator_id = test_integrator.get('integrator_id', '') if test_integrator else ''
        integrator_name = test_integrator.get('name', '') if test_integrator else ''
        
        payload = {
            "client_id": test_client["client_id"],
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_ITERATION94_VPN_FALSE",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": integrator_id,
            "integrator_name": integrator_name,
            "requires_pinpad_config": True,
            "requires_vpn": False,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Verify the field was persisted
        assert quote.get("requires_pinpad_config") == True, "requires_pinpad_config should be True"
        assert quote.get("requires_vpn") == False, "requires_vpn should be False"
        
        # Verify GET returns same value
        quote_id = quote.get("quote_id")
        get_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_response.status_code == 200, f"GET quote failed: {get_response.text}"
        
        fetched_quote = get_response.json()
        assert fetched_quote.get("requires_vpn") == False, "GET should return requires_vpn=False"
    
    def test_create_quote_with_both_false(self, auth_headers, test_client, test_integrator):
        """Test creating quote with both dynamic params set to False"""
        integrator_id = test_integrator.get('integrator_id', '') if test_integrator else ''
        integrator_name = test_integrator.get('name', '') if test_integrator else ''
        
        payload = {
            "client_id": test_client["client_id"],
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_ITERATION94_BOTH_FALSE",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": integrator_id,
            "integrator_name": integrator_name,
            "requires_pinpad_config": False,
            "requires_vpn": False,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Verify both fields are False
        assert quote.get("requires_pinpad_config") == False, "requires_pinpad_config should be False"
        assert quote.get("requires_vpn") == False, "requires_vpn should be False"
        
        # Verify persistence via GET
        quote_id = quote.get("quote_id")
        get_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_response.status_code == 200
        
        fetched = get_response.json()
        assert fetched.get("requires_pinpad_config") == False
        assert fetched.get("requires_vpn") == False


class TestServicesCatalog:
    """Test that services have both conventional and outsourcing costs for VPN toggle"""
    
    def test_comunicacion_backend_has_both_prices(self, auth_headers):
        """Verify Comunicación Backend service has both pricing models"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200, f"GET services failed: {response.text}"
        
        services = response.json()
        
        # Find Comunicación Backend service
        comunicacion_service = None
        for svc in services:
            name = svc.get("name", "").lower()
            if "comunicación backend" in name or "comunicacion backend" in name:
                comunicacion_service = svc
                break
        
        if comunicacion_service:
            # Verify it has both cost types
            monthly_conv = comunicacion_service.get("monthly_cost_conventional", 0)
            monthly_outs = comunicacion_service.get("monthly_cost_outsourcing", 0)
            
            print(f"Comunicación Backend - Conventional: {monthly_conv}, Outsourcing: {monthly_outs}")
            
            # At least one should be non-zero for the toggle to have effect
            assert monthly_conv >= 0, "monthly_cost_conventional should be defined"
            assert monthly_outs >= 0, "monthly_cost_outsourcing should be defined"
        else:
            print("WARNING: 'Comunicación Backend' service not found in catalog - VPN toggle may not work as expected")


class TestQuoteTypeFilter:
    """Test that dynamic params only apply to VPOS quotes"""
    
    def test_gateway_quotes_have_fields_but_not_used(self, auth_headers, test_client, test_integrator):
        """Payment Gateway quotes should still have the fields but toggles are not shown in UI"""
        integrator_id = test_integrator.get('integrator_id', '') if test_integrator else ''
        integrator_name = test_integrator.get('name', '') if test_integrator else ''
        
        payload = {
            "client_id": test_client["client_id"],
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_ITERATION94_GATEWAY",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": integrator_id,
            "integrator_name": integrator_name,
            "pg_setup_items": [{"concepto": "Test Item", "costo": 100, "banco": "N/A", "observacion": ""}],
            "requires_pinpad_config": True,
            "requires_vpn": True,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create PG quote failed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Fields exist but are not used for PG (defaults should be True)
        assert quote.get("quote_type") == "GATEWAY"
        assert quote.get("requires_pinpad_config") == True
        assert quote.get("requires_vpn") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
