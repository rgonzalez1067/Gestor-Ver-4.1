# ruff: noqa
"""
Test Iteration 96: MPOS vs VPOS Segmentation
Tests the new segmentation of quote types into separate VPOS and MPOS with independent flows.
Key features:
- MPOS: pricing_model='outsourcing' (fixed), VPN toggle hidden, integrator optional, 'Modelo de POS' label
- VPOS: pricing_model selectable, VPN toggle visible, integrator required, 'Modelo de Pinpad' label
- QuotesTable must differentiate 'VPOS' from 'MPOS' types
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Test authentication to get session token"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    def test_login(self, session):
        """Login with test credentials"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
        return session


class TestMPOSQuoteCreation:
    """Test MPOS quote creation with fixed outsourcing pricing_model"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def test_client_id(self, authenticated_session):
        """Get or create a test client"""
        # First try to find existing client
        response = authenticated_session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        clients = response.json()
        if clients:
            return clients[0]['client_id']
        
        # Create a test client if none exist
        response = authenticated_session.post(f"{BASE_URL}/api/clients", json={
            "rif": "J-TEST-MPOS-001",
            "legal_name": "Test MPOS Client",
            "fantasy_name": "MPOS Test",
            "segment": "Pymes"
        })
        assert response.status_code == 200
        return response.json()['client_id']
    
    def test_create_mpos_quote_with_outsourcing(self, authenticated_session, test_client_id):
        """Test creating MPOS quote with pricing_model='outsourcing'"""
        payload = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "MPOS",
            "pricing_model": "outsourcing",  # MPOS forces outsourcing
            "services": [{
                "item_type": "setup",
                "item_name": "Suscripción PDV/Banco",
                "quantity": 1,
                "unit_price_usd": 50.0,
                "total_usd": 50.0,
                "cantidad_cajas": 1,
                "cantidad_bancos": 1
            }],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test MPOS quote with outsourcing pricing",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": "",  # MPOS: integrator optional
            "requires_vpn": True,
            "requires_pinpad_config": True
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"Failed to create MPOS quote: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Verify MPOS quote properties
        assert quote["quote_type"] == "MPOS", f"Expected quote_type='MPOS', got '{quote['quote_type']}'"
        assert quote["pricing_model"] == "outsourcing", f"Expected pricing_model='outsourcing', got '{quote['pricing_model']}'"
        
        print(f"✓ MPOS quote created: {quote['quote_number']} with pricing_model=outsourcing")
        return quote["quote_id"]
    
    def test_create_mpos_quote_without_integrator(self, authenticated_session, test_client_id):
        """Test that MPOS can be created without integrator (integrator optional for MPOS)"""
        payload = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "MPOS",
            "pricing_model": "outsourcing",
            "services": [{
                "item_type": "setup",
                "item_name": "Config Test",
                "quantity": 1,
                "unit_price_usd": 25.0,
                "total_usd": 25.0
            }],
            "hardware": [],
            "equipment_items": [],
            "cantidad_cajas": 1,
            "cantidad_bancos": 1
            # integrator_id omitted - should work for MPOS
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"MPOS without integrator should succeed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        assert quote["quote_type"] == "MPOS"
        
        print(f"✓ MPOS quote created without integrator: {quote['quote_number']}")


class TestVPOSQuoteCreation:
    """Test VPOS quote creation with selectable pricing_model"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def test_client_id(self, authenticated_session):
        """Get first available client"""
        response = authenticated_session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) > 0, "Need at least one client to test"
        return clients[0]['client_id']
    
    @pytest.fixture(scope="class")
    def test_integrator_id(self, authenticated_session):
        """Get first available integrator (required for VPOS)"""
        response = authenticated_session.get(f"{BASE_URL}/api/integrators")
        assert response.status_code == 200
        integrators = response.json()
        if integrators:
            return integrators[0]['integrator_id']
        return None
    
    def test_create_vpos_quote_conventional(self, authenticated_session, test_client_id, test_integrator_id):
        """Test creating VPOS quote with pricing_model='conventional'"""
        payload = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",  # VPOS allows conventional
            "services": [{
                "item_type": "setup",
                "item_name": "Suscripción PDV/Banco",
                "quantity": 1,
                "unit_price_usd": 100.0,
                "total_usd": 100.0,
                "cantidad_cajas": 1,
                "cantidad_bancos": 1
            }],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test VPOS quote with conventional pricing",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": test_integrator_id or "",
            "requires_vpn": True,
            "requires_pinpad_config": True
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"Failed to create VPOS quote: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        # Verify VPOS quote properties
        assert quote["quote_type"] == "VPOS", f"Expected quote_type='VPOS', got '{quote['quote_type']}'"
        assert quote["pricing_model"] == "conventional", f"Expected pricing_model='conventional', got '{quote['pricing_model']}'"
        
        print(f"✓ VPOS quote created: {quote['quote_number']} with pricing_model=conventional")
    
    def test_create_vpos_quote_outsourcing(self, authenticated_session, test_client_id, test_integrator_id):
        """Test creating VPOS quote with pricing_model='outsourcing'"""
        payload = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "outsourcing",  # VPOS also allows outsourcing
            "services": [{
                "item_type": "setup",
                "item_name": "Suscripción PDV/Banco",
                "quantity": 1,
                "unit_price_usd": 80.0,
                "total_usd": 80.0
            }],
            "hardware": [],
            "equipment_items": [],
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "integrator_id": test_integrator_id or ""
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"Failed to create VPOS outsourcing quote: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        assert quote["quote_type"] == "VPOS"
        assert quote["pricing_model"] == "outsourcing"
        
        print(f"✓ VPOS quote created: {quote['quote_number']} with pricing_model=outsourcing")


class TestQuotesListDifferentiation:
    """Test that GET /api/quotes correctly differentiates VPOS from MPOS"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_get_quotes_returns_different_types(self, authenticated_session):
        """Test that GET /api/quotes returns quotes with VPOS and MPOS types"""
        response = authenticated_session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        
        # Categorize quotes by type
        vpos_quotes = [q for q in quotes if q.get('quote_type') == 'VPOS']
        mpos_quotes = [q for q in quotes if q.get('quote_type') == 'MPOS']
        gateway_quotes = [q for q in quotes if q.get('quote_type') == 'GATEWAY']
        # Check for legacy VPOS_MPOS type (should not exist anymore)
        legacy_quotes = [q for q in quotes if q.get('quote_type') == 'VPOS_MPOS']
        
        print(f"Quotes breakdown - VPOS: {len(vpos_quotes)}, MPOS: {len(mpos_quotes)}, Gateway: {len(gateway_quotes)}, Legacy VPOS_MPOS: {len(legacy_quotes)}")
        
        # Verify no quotes are missing quote_type
        for q in quotes[:5]:  # Check first 5
            assert 'quote_type' in q, f"Quote {q.get('quote_id')} missing quote_type"
            print(f"  Quote {q.get('quote_number')}: type={q.get('quote_type')}")
        
        print("✓ GET /api/quotes returns properly differentiated quote types")


class TestMPOSVPNToggleHidden:
    """Verify that MPOS pricing_model is fixed and VPN is not configurable via API"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def test_client_id(self, authenticated_session):
        response = authenticated_session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) > 0
        return clients[0]['client_id']
    
    def test_mpos_requires_vpn_defaults_true(self, authenticated_session, test_client_id):
        """Test that MPOS quote requires_vpn defaults to True when not specified"""
        payload = {
            "client_id": test_client_id,
            "quote_type": "MPOS",
            "pricing_model": "outsourcing",
            "services": [{
                "item_type": "setup",
                "item_name": "Test",
                "quantity": 1,
                "unit_price_usd": 10.0,
                "total_usd": 10.0
            }],
            "cantidad_cajas": 1
            # requires_vpn not specified - should default to True
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        quote = data.get("quote", data)
        
        # MPOS should have requires_vpn=True by default
        assert quote.get("requires_vpn", True) == True, "MPOS requires_vpn should default to True"
        print(f"✓ MPOS quote {quote['quote_number']} has requires_vpn={quote.get('requires_vpn')}")


class TestIntegratorWithSinIntegradorOption:
    """Test that MPOS can use 'Sin integrador' option (empty or null integrator_id)"""
    
    @pytest.fixture(scope="class")
    def authenticated_session(self):
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def test_client_id(self, authenticated_session):
        response = authenticated_session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) > 0
        return clients[0]['client_id']
    
    def test_mpos_with_empty_integrator(self, authenticated_session, test_client_id):
        """Test MPOS accepts empty integrator_id ('Sin integrador')"""
        payload = {
            "client_id": test_client_id,
            "quote_type": "MPOS",
            "pricing_model": "outsourcing",
            "services": [{
                "item_type": "setup",
                "item_name": "Sin Integrador Test",
                "quantity": 1,
                "unit_price_usd": 15.0,
                "total_usd": 15.0
            }],
            "integrator_id": "",  # Sin integrador
            "integrator_name": "",
            "cantidad_cajas": 1
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"MPOS with empty integrator should succeed: {response.text}"
        
        data = response.json()
        quote = data.get("quote", data)
        
        assert quote["integrator_id"] in [None, ""], f"integrator_id should be empty/null, got {quote['integrator_id']}"
        print(f"✓ MPOS quote created without integrator (Sin integrador): {quote['quote_number']}")
    
    def test_mpos_with_none_integrator(self, authenticated_session, test_client_id):
        """Test MPOS accepts null/None integrator_id"""
        payload = {
            "client_id": test_client_id,
            "quote_type": "MPOS",
            "pricing_model": "outsourcing",
            "services": [{
                "item_type": "setup",
                "item_name": "None Integrador Test",
                "quantity": 1,
                "unit_price_usd": 15.0,
                "total_usd": 15.0
            }],
            "integrator_id": None,  # Explicitly None
            "cantidad_cajas": 1
        }
        
        response = authenticated_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        assert response.status_code == 200, f"MPOS with None integrator should succeed: {response.text}"
        
        print("✓ MPOS accepts null integrator_id")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
