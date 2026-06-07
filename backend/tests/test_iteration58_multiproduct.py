# ruff: noqa
"""
Test iteration 58 - MultiProductSelector and Dashboard Stats
Tests:
1. Dashboard stats endpoint returns correct counts
2. Banks endpoint returns banks with products array having product_name and gateway_available
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"


class TestDashboardStats:
    """Dashboard stats endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_dashboard_stats_returns_correct_structure(self):
        """Test GET /api/dashboard/stats returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        # Verify all required fields exist
        assert "totalQuotes" in data
        assert "totalClients" in data
        assert "totalBanks" in data
        assert "totalMediosPago" in data
        assert "totalHardware" in data
        assert "exchangeRate" in data
        print(f"Dashboard stats: {data}")
    
    def test_dashboard_stats_values_are_numbers(self):
        """Test that all stats are numeric values"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data["totalQuotes"], int)
        assert isinstance(data["totalClients"], int)
        assert isinstance(data["totalBanks"], int)
        assert isinstance(data["totalMediosPago"], int)
        assert isinstance(data["totalHardware"], int)
        assert isinstance(data["exchangeRate"], (int, float))
    
    def test_dashboard_stats_expected_counts(self):
        """Test that counts match expected values (130 quotes, 309 clients, 36 banks)"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        # Values as mentioned in the review request
        assert data["totalQuotes"] == 130, f"Expected 130 quotes, got {data['totalQuotes']}"
        assert data["totalClients"] == 309, f"Expected 309 clients, got {data['totalClients']}"
        assert data["totalBanks"] == 36, f"Expected 36 banks, got {data['totalBanks']}"
        print(f"Counts verified: quotes={data['totalQuotes']}, clients={data['totalClients']}, banks={data['totalBanks']}")


class TestBanksEndpoint:
    """Banks endpoint tests for product structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_banks_returns_products_array(self):
        """Test GET /api/banks returns banks with products array"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        
        banks = response.json()
        assert isinstance(banks, list)
        assert len(banks) > 0
        
        # Check first bank has products array
        bank = banks[0]
        assert "products" in bank
        assert isinstance(bank["products"], list)
        print(f"First bank '{bank['name']}' has {len(bank['products'])} products")
    
    def test_bank_products_have_required_fields(self):
        """Test that bank products have product_name and gateway_available fields"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        
        banks = response.json()
        
        # Find a bank with products
        banks_with_products = [b for b in banks if len(b.get("products", [])) > 0]
        assert len(banks_with_products) > 0, "No banks with products found"
        
        for bank in banks_with_products[:5]:  # Check first 5 banks
            for product in bank["products"]:
                assert "product_name" in product, f"product_name missing in bank {bank['name']}"
                assert "gateway_available" in product, f"gateway_available missing in bank {bank['name']}"
                assert isinstance(product["gateway_available"], bool)
                print(f"  Bank '{bank['name']}' product: {product['product_name']}, gateway={product['gateway_available']}")
    
    def test_some_products_have_gateway_available_true(self):
        """Test that some bank products have gateway_available=True"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        
        banks = response.json()
        
        gateway_products = []
        for bank in banks:
            for product in bank.get("products", []):
                if product.get("gateway_available", False):
                    gateway_products.append({
                        "bank": bank["name"],
                        "product": product["product_name"]
                    })
        
        assert len(gateway_products) > 0, "No products with gateway_available=True found"
        print(f"Found {len(gateway_products)} products with gateway_available=True")
        for gp in gateway_products[:5]:
            print(f"  {gp['bank']}: {gp['product']}")
    
    def test_some_products_have_vpos_available_true(self):
        """Test that some bank products have vpos_available=True"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        
        banks = response.json()
        
        vpos_products = []
        for bank in banks:
            for product in bank.get("products", []):
                if product.get("vpos_available", False):
                    vpos_products.append({
                        "bank": bank["name"],
                        "product": product["product_name"]
                    })
        
        assert len(vpos_products) > 0, "No products with vpos_available=True found"
        print(f"Found {len(vpos_products)} products with vpos_available=True")


class TestIntegrators:
    """Test integrators endpoint for quote creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_integrators_list(self):
        """Test GET /api/integrators returns list"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert response.status_code == 200
        
        integrators = response.json()
        assert isinstance(integrators, list)
        print(f"Found {len(integrators)} integrators")


class TestClients:
    """Test clients endpoint for quote creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_clients_list(self):
        """Test GET /api/clients returns list with 309 clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert response.status_code == 200
        
        clients = response.json()
        assert isinstance(clients, list)
        assert len(clients) == 309, f"Expected 309 clients, got {len(clients)}"
        print(f"Found {len(clients)} clients")


class TestServices:
    """Test services/medios de pago endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_services_list(self):
        """Test GET /api/services returns service catalog"""
        response = requests.get(f"{BASE_URL}/api/services", headers=self.headers)
        assert response.status_code == 200
        
        services = response.json()
        assert isinstance(services, list)
        print(f"Found {len(services)} services in catalog")
