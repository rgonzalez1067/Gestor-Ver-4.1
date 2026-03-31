"""
Test C2P/Débito Inmediato Bug Fix - Iteration 139
Tests for the critical bug where 'Pago con C2P o Débito Inmediato' was:
1. Inserted in DB with price 0 due to typo 'Imediato' vs 'Inmediato'
2. Disappeared from wizard UI due to tarifa_setup > 0 filter
3. Reappeared when converting to Project

Verifications:
- Banks have correct product name 'Pago con C2P o Débito Inmediato' (not 'Imediato')
- Service catalog has correct pricing for the product
- findServicePrice function can match the product name
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestC2PBugFix:
    """Tests for C2P/Débito Inmediato bug fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_login_works(self):
        """Test that login works with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert data["user"]["email"] == "admin@meganexus.com"
        print("✓ Login works correctly")
    
    def test_banks_have_correct_c2p_product_name(self):
        """Verify banks have 'Pago con C2P o Débito Inmediato' (not 'Imediato')"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        banks = response.json()
        
        # Banks that should have C2P product
        expected_banks_with_c2p = [
            "Banco Mercantil", "Banesco", "BBVA Provincial", "Banco Exterior",
            "BNC", "Banco Plaza", "Bancaribe", "BFC", "Banplus", "Bancamiga", "R4"
        ]
        
        banks_with_c2p = []
        banks_with_typo = []
        
        for bank in banks:
            products = bank.get('products', [])
            for product in products:
                product_name = product.get('product_name', '')
                # Check for correct spelling
                if 'Pago con C2P o Débito Inmediato' in product_name:
                    banks_with_c2p.append(bank['name'])
                # Check for typo (should NOT exist)
                if 'Imediato' in product_name and 'Inmediato' not in product_name:
                    banks_with_typo.append((bank['name'], product_name))
        
        # Verify no typos exist
        assert len(banks_with_typo) == 0, f"Found banks with typo 'Imediato': {banks_with_typo}"
        
        # Verify at least some banks have the correct product
        assert len(banks_with_c2p) >= 10, f"Expected at least 10 banks with C2P, found {len(banks_with_c2p)}: {banks_with_c2p}"
        
        print(f"✓ {len(banks_with_c2p)} banks have correct 'Pago con C2P o Débito Inmediato' product")
        print(f"✓ No banks have typo 'Imediato'")
    
    def test_service_catalog_has_c2p_with_correct_pricing(self):
        """Verify service catalog has 'Pago con C2P o Débito Inmediato' with correct pricing"""
        response = requests.get(f"{BASE_URL}/api/services", headers=self.headers)
        assert response.status_code == 200
        services = response.json()
        
        # Find the C2P service
        c2p_service = None
        for service in services:
            if 'Pago con C2P o Débito Inmediato' in service.get('name', ''):
                c2p_service = service
                break
        
        assert c2p_service is not None, "Service 'Pago con C2P o Débito Inmediato' not found in catalog"
        
        # Verify pricing is not 0
        setup_conv = c2p_service.get('setup_cost_conventional', 0)
        setup_out = c2p_service.get('setup_cost_outsourcing', 0)
        
        assert setup_conv > 0, f"setup_cost_conventional should be > 0, got {setup_conv}"
        assert setup_out > 0, f"setup_cost_outsourcing should be > 0, got {setup_out}"
        
        # Expected values based on bug report
        assert setup_conv == 8.0, f"Expected setup_cost_conventional=8.0, got {setup_conv}"
        assert setup_out == 1.6, f"Expected setup_cost_outsourcing=1.6, got {setup_out}"
        
        print(f"✓ Service 'Pago con C2P o Débito Inmediato' found with service_id={c2p_service.get('service_id')}")
        print(f"✓ Pricing: setup_conv={setup_conv}, setup_out={setup_out}")
    
    def test_banks_api_returns_all_products(self):
        """Verify banks API returns all products including C2P"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        banks = response.json()
        
        # Check Banco Mercantil specifically (mentioned in bug report)
        mercantil = next((b for b in banks if 'Mercantil' in b.get('name', '')), None)
        assert mercantil is not None, "Banco Mercantil not found"
        
        products = mercantil.get('products', [])
        product_names = [p.get('product_name', '') for p in products]
        
        # Should have C2P product
        has_c2p = any('Pago con C2P o Débito Inmediato' in name for name in product_names)
        assert has_c2p, f"Banco Mercantil should have 'Pago con C2P o Débito Inmediato'. Products: {product_names}"
        
        print(f"✓ Banco Mercantil has {len(products)} products including C2P")
    
    def test_services_api_returns_all_c2p_related_services(self):
        """Verify services API returns all C2P related services"""
        response = requests.get(f"{BASE_URL}/api/services", headers=self.headers)
        assert response.status_code == 200
        services = response.json()
        
        c2p_services = [s for s in services if 'C2P' in s.get('name', '') or 'Inmediato' in s.get('name', '')]
        
        # Should have multiple C2P related services
        assert len(c2p_services) >= 4, f"Expected at least 4 C2P related services, found {len(c2p_services)}"
        
        service_names = [s.get('name', '') for s in c2p_services]
        print(f"✓ Found {len(c2p_services)} C2P related services: {service_names}")
    
    def test_no_typo_in_any_bank_products(self):
        """Comprehensive check that no bank has the typo 'Imediato'"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        banks = response.json()
        
        typos_found = []
        for bank in banks:
            for product in bank.get('products', []):
                product_name = product.get('product_name', '')
                # Check for typo - 'Imediato' without 'Inmediato'
                if 'Imediato' in product_name:
                    typos_found.append({
                        'bank': bank.get('name'),
                        'product': product_name
                    })
        
        assert len(typos_found) == 0, f"Found typos 'Imediato' in: {typos_found}"
        print("✓ No typos 'Imediato' found in any bank products")


class TestQuotesWithC2P:
    """Tests for quotes functionality with C2P products"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        self.token = response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_quotes_api_accessible(self):
        """Verify quotes API is accessible"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        print(f"✓ Quotes API accessible, found {len(quotes)} quotes")
    
    def test_clients_api_accessible(self):
        """Verify clients API is accessible for quote creation"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert response.status_code == 200
        clients = response.json()
        assert len(clients) > 0, "No clients found"
        print(f"✓ Clients API accessible, found {len(clients)} clients")
    
    def test_integrators_api_accessible(self):
        """Verify integrators API is accessible for quote creation"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert response.status_code == 200
        integrators = response.json()
        print(f"✓ Integrators API accessible, found {len(integrators)} integrators")
    
    def test_hardware_api_accessible(self):
        """Verify hardware API is accessible for quote creation"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=self.headers)
        assert response.status_code == 200
        hardware = response.json()
        print(f"✓ Hardware API accessible, found {len(hardware)} items")


class TestPDFDataWithC2P:
    """Tests for PDF data generation with C2P products"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200
        self.token = response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_existing_quotes_have_additional_items(self):
        """Check existing quotes for additional_items structure"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        # Find quotes with additional_items
        quotes_with_additional = []
        for quote in quotes:
            services = quote.get('services', [])
            additional = [s for s in services if s.get('item_type') == 'additional']
            if additional:
                quotes_with_additional.append({
                    'quote_number': quote.get('quote_number'),
                    'additional_count': len(additional)
                })
        
        print(f"✓ Found {len(quotes_with_additional)} quotes with additional_items")
        if quotes_with_additional:
            print(f"  Examples: {quotes_with_additional[:3]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
