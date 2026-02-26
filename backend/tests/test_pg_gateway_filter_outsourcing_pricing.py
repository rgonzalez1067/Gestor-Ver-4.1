"""
Test Payment Gateway Flow - Iteration 49
Tests: 
1. gateway_available filtering on banks
2. outsourcing pricing auto-fill from services catalog
3. Persona Jurídica auto-load with $240.00
4. Bank-specific product filtering
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestGatewayAvailableFiltering:
    """Tests for gateway_available flag on bank products"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_banks_have_gateway_available_flag(self, headers):
        """Verify GET /api/banks returns products with gateway_available flag"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 200
        
        banks = response.json()
        assert len(banks) > 0, "No banks returned"
        
        # Check that products have gateway_available attribute
        bank_with_products = None
        for bank in banks:
            if bank.get('products'):
                bank_with_products = bank
                break
        
        assert bank_with_products is not None, "No bank found with products"
        
        # Verify gateway_available exists on products
        for product in bank_with_products['products']:
            assert 'gateway_available' in product, f"Product {product.get('product_name')} missing gateway_available flag"
    
    def test_banco_de_venezuela_gateway_products(self, headers):
        """Verify Banco de Venezuela shows only 2 gateway products: TDC and P2C"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 200
        
        banks = response.json()
        bdv = next((b for b in banks if 'venezuela' in b.get('name', '').lower()), None)
        assert bdv is not None, "Banco de Venezuela not found"
        
        # Filter gateway_available products
        gw_products = [p for p in bdv.get('products', []) if p.get('gateway_available')]
        product_names = [p.get('product_name') for p in gw_products]
        
        assert len(gw_products) == 2, f"Expected 2 gateway products for BdV, got {len(gw_products)}: {product_names}"
        
        # Check specific products
        assert 'Adquirientes para tarjetas de crédito (TDC)' in product_names, f"TDC not found in {product_names}"
        assert 'Adquirientes para P2C' in product_names, f"P2C not found in {product_names}"
    
    def test_banco_mercantil_gateway_products(self, headers):
        """Verify Banco Mercantil shows 3 gateway products: TDC, P2C, C2P"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 200
        
        banks = response.json()
        mercantil = next((b for b in banks if 'mercantil' in b.get('name', '').lower()), None)
        assert mercantil is not None, "Banco Mercantil not found"
        
        # Filter gateway_available products
        gw_products = [p for p in mercantil.get('products', []) if p.get('gateway_available')]
        product_names = [p.get('product_name') for p in gw_products]
        
        assert len(gw_products) == 3, f"Expected 3 gateway products for Mercantil, got {len(gw_products)}: {product_names}"
        
        # Check specific products
        assert 'Adquirientes para tarjetas de crédito (TDC)' in product_names, f"TDC not found in {product_names}"
        assert 'Adquirientes para P2C' in product_names, f"P2C not found in {product_names}"
        assert 'Adquirientes para C2P' in product_names, f"C2P not found in {product_names}"


class TestServicesOutsourcingPricing:
    """Tests for gateway_enabled services with setup_cost_outsourcing pricing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_services_have_gateway_enabled_flag(self, headers):
        """Verify GET /api/services returns gateway_enabled services with setup_cost_outsourcing"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        
        services = response.json()
        assert len(services) > 0, "No services returned"
        
        # Filter gateway_enabled services
        gw_services = [s for s in services if s.get('gateway_enabled')]
        assert len(gw_services) > 0, "No gateway_enabled services found"
        
        # Verify setup_cost_outsourcing exists on gateway_enabled services
        for service in gw_services:
            assert 'setup_cost_outsourcing' in service, f"Service {service.get('name')} missing setup_cost_outsourcing"
    
    def test_persona_juridica_outsourcing_price(self, headers):
        """Verify 'Persona Jurídica' has $240.00 outsourcing price"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        
        services = response.json()
        pj_service = next((s for s in services if 'persona jur' in s.get('name', '').lower()), None)
        
        assert pj_service is not None, "Persona Jurídica service not found"
        assert pj_service.get('gateway_enabled') == True, "Persona Jurídica should be gateway_enabled"
        assert pj_service.get('setup_cost_outsourcing') == 240.0, \
            f"Expected $240.00 for Persona Jurídica, got ${pj_service.get('setup_cost_outsourcing')}"
    
    def test_tdc_outsourcing_price(self, headers):
        """Verify 'Adquirientes para TDC' has $60.00 outsourcing price"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        
        services = response.json()
        tdc_service = next((s for s in services if 'tarjetas de crédito (tdc)' in s.get('name', '').lower()), None)
        
        assert tdc_service is not None, "TDC service not found"
        assert tdc_service.get('gateway_enabled') == True, "TDC should be gateway_enabled"
        assert tdc_service.get('application_type') == 'setup', "TDC should be setup type"
        assert tdc_service.get('setup_cost_outsourcing') == 60.0, \
            f"Expected $60.00 for TDC, got ${tdc_service.get('setup_cost_outsourcing')}"
    
    def test_p2c_outsourcing_price(self, headers):
        """Verify 'Adquirientes para P2C' has $36.00 outsourcing price"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        
        services = response.json()
        p2c_service = next((s for s in services if 'adquirientes para p2c' in s.get('name', '').lower()), None)
        
        assert p2c_service is not None, "P2C service not found"
        assert p2c_service.get('gateway_enabled') == True, "P2C should be gateway_enabled"
        assert p2c_service.get('setup_cost_outsourcing') == 36.0, \
            f"Expected $36.00 for P2C, got ${p2c_service.get('setup_cost_outsourcing')}"
    
    def test_c2p_outsourcing_price(self, headers):
        """Verify 'Adquirientes para C2P' has $36.00 outsourcing price"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        
        services = response.json()
        c2p_service = next((s for s in services if 'adquirientes para c2p' in s.get('name', '').lower()), None)
        
        assert c2p_service is not None, "C2P service not found"
        assert c2p_service.get('gateway_enabled') == True, "C2P should be gateway_enabled"
        assert c2p_service.get('setup_cost_outsourcing') == 36.0, \
            f"Expected $36.00 for C2P, got ${c2p_service.get('setup_cost_outsourcing')}"


class TestPgDefaultsEndpoint:
    """Tests for /api/pg-defaults endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_pg_defaults_returns_persona_juridica(self, headers):
        """Verify /api/pg-defaults returns 'Persona Jurídica' with $240.00 costo"""
        response = requests.get(f"{BASE_URL}/api/pg-defaults", headers=headers)
        assert response.status_code == 200, f"PG defaults endpoint failed: {response.text}"
        
        data = response.json()
        assert data.get('concepto') == 'Persona Jurídica', f"Expected 'Persona Jurídica', got {data.get('concepto')}"
        assert data.get('costo') == 240, f"Expected $240.00, got ${data.get('costo')}"


class TestPGQuoteCreationWithOutsourcingPrices:
    """Tests for creating PG quotes with correct outsourcing prices stored"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def client_id(self, headers):
        """Get first available client"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) > 0, "No clients available"
        return clients[0].get('client_id')
    
    @pytest.fixture(scope="class")
    def integrator_id(self, headers):
        """Get first available integrator"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=headers)
        assert response.status_code == 200
        integrators = response.json()
        if len(integrators) > 0:
            return integrators[0].get('integrator_id')
        return None
    
    def test_create_pg_quote_with_outsourcing_prices(self, headers, client_id, integrator_id):
        """Create PG quote and verify outsourcing prices are stored correctly"""
        if not integrator_id:
            pytest.skip("No integrators available")
        
        # Build pg_setup_items with expected outsourcing prices
        pg_setup_items = [
            {"concepto": "Persona Jurídica", "costo": 240.0, "banco": "N/A", "observacion": "Auto-cargado"},
            {"concepto": "Adquirientes para tarjetas de crédito (TDC)", "costo": 60.0, "banco": "Banco de Venezuela", "observacion": ""},
            {"concepto": "Adquirientes para P2C", "costo": 36.0, "banco": "Banco de Venezuela", "observacion": ""}
        ]
        
        payload = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "TEST_PG_outsourcing_prices",
            "integrator_id": integrator_id,
            "integrator_name": "Test Integrator",
            "integrator_app_name": "Test App",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": None,
            "pg_transaction_range": 2,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, headers=headers)
        assert response.status_code == 200 or response.status_code == 201, f"Failed to create PG quote: {response.text}"
        
        data = response.json()
        quote_id = data.get('quote_id')
        assert quote_id is not None, "Quote ID not returned"
        
        # Fetch the created quote and verify pg_setup_items
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert quote_response.status_code == 200
        
        quote_data = quote_response.json()
        stored_items = quote_data.get('pg_setup_items', [])
        
        # Verify Persona Jurídica with $240
        pj_item = next((i for i in stored_items if i.get('concepto') == 'Persona Jurídica'), None)
        assert pj_item is not None, "Persona Jurídica not found in stored items"
        assert pj_item.get('costo') == 240.0, f"Expected $240 for PJ, got ${pj_item.get('costo')}"
        
        # Verify TDC with $60
        tdc_item = next((i for i in stored_items if 'TDC' in i.get('concepto', '')), None)
        assert tdc_item is not None, "TDC not found in stored items"
        assert tdc_item.get('costo') == 60.0, f"Expected $60 for TDC, got ${tdc_item.get('costo')}"
        
        # Verify P2C with $36
        p2c_item = next((i for i in stored_items if 'P2C' in i.get('concepto', '')), None)
        assert p2c_item is not None, "P2C not found in stored items"
        assert p2c_item.get('costo') == 36.0, f"Expected $36 for P2C, got ${p2c_item.get('costo')}"
        
        # Verify total calculation: 240 + 60 + 36 = 336
        expected_total = 336.0
        actual_total = sum(item.get('costo', 0) for item in stored_items)
        assert actual_total == expected_total, f"Expected total ${expected_total}, got ${actual_total}"
        
        # Cleanup: delete test quote
        delete_response = requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert delete_response.status_code in [200, 204], f"Failed to cleanup test quote: {delete_response.text}"


class TestVPOSMPOSRegression:
    """Regression tests to ensure VPOS/MPOS flow still works"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_banks_have_vpos_available_products(self, headers):
        """Verify banks still have vpos_available products"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 200
        
        banks = response.json()
        
        # Find banks with vpos_available products
        vpos_products_found = False
        for bank in banks:
            for product in bank.get('products', []):
                if product.get('vpos_available'):
                    vpos_products_found = True
                    break
            if vpos_products_found:
                break
        
        assert vpos_products_found, "No vpos_available products found - VPOS/MPOS flow may be broken"
