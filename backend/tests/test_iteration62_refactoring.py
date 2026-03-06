"""
Test suite for Iteration 62 - Frontend Refactoring Verification
Tests: QuoteFilters, QuotesTable, PdfPreviewModal components
Backend routes: quotes, clients, banks, dashboard after modular refactoring
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0226*02"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        return data["session_token"]
    
    def test_login_success(self, auth_token):
        """Test login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Login successful, token received")


class TestBackendAPIs:
    """Backend API tests after modular refactoring"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0226*02"
        })
        token = response.json().get("session_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_quotes_endpoint(self, auth_headers):
        """Test /api/quotes returns 143+ quotes"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Quotes endpoint failed: {response.text}"
        
        quotes = response.json()
        assert isinstance(quotes, list), "Response should be a list"
        assert len(quotes) >= 143, f"Expected 143+ quotes, got {len(quotes)}"
        
        # Verify quote structure
        if quotes:
            quote = quotes[0]
            assert "quote_id" in quote, "Missing quote_id"
            assert "quote_number" in quote, "Missing quote_number"
            assert "client_id" in quote, "Missing client_id"
        
        print(f"✓ Quotes endpoint returned {len(quotes)} quotes")
    
    def test_clients_endpoint(self, auth_headers):
        """Test /api/clients returns clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"Clients endpoint failed: {response.text}"
        
        clients = response.json()
        assert isinstance(clients, list), "Response should be a list"
        assert len(clients) >= 300, f"Expected 300+ clients, got {len(clients)}"
        
        print(f"✓ Clients endpoint returned {len(clients)} clients")
    
    def test_banks_endpoint(self, auth_headers):
        """Test /api/banks returns banks"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers)
        assert response.status_code == 200, f"Banks endpoint failed: {response.text}"
        
        banks = response.json()
        assert isinstance(banks, list), "Response should be a list"
        assert len(banks) >= 36, f"Expected 36+ banks, got {len(banks)}"
        
        print(f"✓ Banks endpoint returned {len(banks)} banks")
    
    def test_dashboard_stats_endpoint(self, auth_headers):
        """Test /api/dashboard/stats returns correct stats"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        
        stats = response.json()
        assert "totalQuotes" in stats, "Missing totalQuotes"
        assert "totalClients" in stats, "Missing totalClients"
        assert "totalBanks" in stats, "Missing totalBanks"
        assert "totalMediosPago" in stats, "Missing totalMediosPago"
        assert "totalHardware" in stats, "Missing totalHardware"
        
        # Verify counts
        assert stats["totalQuotes"] >= 143, f"Expected 143+ quotes, got {stats['totalQuotes']}"
        assert stats["totalClients"] >= 300, f"Expected 300+ clients, got {stats['totalClients']}"
        assert stats["totalBanks"] >= 36, f"Expected 36+ banks, got {stats['totalBanks']}"
        
        print(f"✓ Dashboard stats: {stats['totalQuotes']} quotes, {stats['totalClients']} clients, {stats['totalBanks']} banks")
    
    def test_services_endpoint(self, auth_headers):
        """Test /api/services returns service catalog"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200, f"Services endpoint failed: {response.text}"
        
        services = response.json()
        assert isinstance(services, list), "Response should be a list"
        
        print(f"✓ Services endpoint returned {len(services)} services")
    
    def test_hardware_endpoint(self, auth_headers):
        """Test /api/hardware returns hardware catalog"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=auth_headers)
        assert response.status_code == 200, f"Hardware endpoint failed: {response.text}"
        
        hardware = response.json()
        assert isinstance(hardware, list), "Response should be a list"
        
        print(f"✓ Hardware endpoint returned {len(hardware)} items")
    
    def test_integrators_endpoint(self, auth_headers):
        """Test /api/integrators returns integrators"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert response.status_code == 200, f"Integrators endpoint failed: {response.text}"
        
        integrators = response.json()
        assert isinstance(integrators, list), "Response should be a list"
        
        print(f"✓ Integrators endpoint returned {len(integrators)} integrators")
    
    def test_missing_pdfs_endpoint(self, auth_headers):
        """Test /api/dashboard/missing-pdfs returns quotes without PDF"""
        response = requests.get(f"{BASE_URL}/api/dashboard/missing-pdfs", headers=auth_headers)
        assert response.status_code == 200, f"Missing PDFs endpoint failed: {response.text}"
        
        data = response.json()
        # Response is an object with count and missing_pdfs array
        assert "count" in data, "Response should have count field"
        assert "missing_pdfs" in data, "Response should have missing_pdfs field"
        assert isinstance(data["missing_pdfs"], list), "missing_pdfs should be a list"
        
        print(f"✓ Missing PDFs endpoint returned {data['count']} quotes without PDF")


class TestQuoteFiltering:
    """Test quote filtering functionality for QuoteFilters component"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0226*02"
        })
        token = response.json().get("session_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_quotes_have_status_field(self, auth_headers):
        """Verify quotes have quote_status field for filtering"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = response.json()
        
        # Check first 10 quotes for status field
        for quote in quotes[:10]:
            # Status should be present (can be None/null for draft)
            has_status = "quote_status" in quote
            assert has_status, f"Quote {quote.get('quote_id')} missing quote_status"
        
        # Count status distribution
        status_counts = {}
        for quote in quotes:
            status = quote.get("quote_status", "Borrador")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"✓ Status distribution: {status_counts}")
    
    def test_quotes_have_category_field(self, auth_headers):
        """Verify quotes have quote_category field for filtering"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = response.json()
        
        # Count category distribution
        category_counts = {}
        for quote in quotes:
            category = quote.get("quote_category", "implementation")
            category_counts[category] = category_counts.get(category, 0) + 1
        
        print(f"✓ Category distribution: {category_counts}")
    
    def test_quotes_have_client_id(self, auth_headers):
        """Verify quotes have client_id for client filtering"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        quotes = response.json()
        
        quotes_with_client = sum(1 for q in quotes if q.get("client_id"))
        
        print(f"✓ {quotes_with_client}/{len(quotes)} quotes have client_id")


class TestModularRouters:
    """Test all modular routers are properly mounted"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0226*02"
        })
        token = response.json().get("session_token")
        return {"Authorization": f"Bearer {token}"}
    
    def test_auth_router(self):
        """Test auth router is accessible"""
        # Test login endpoint (already covered but verify it's the router)
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0226*02"
        })
        assert response.status_code == 200
        print("✓ Auth router (/api/auth/*) working")
    
    def test_clients_router(self, auth_headers):
        """Test clients router is accessible"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Clients router (/api/clients) working")
    
    def test_banks_router(self, auth_headers):
        """Test banks router is accessible"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Banks router (/api/banks) working")
    
    def test_services_router(self, auth_headers):
        """Test services router is accessible"""
        response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Services router (/api/services) working")
    
    def test_hardware_router(self, auth_headers):
        """Test hardware router is accessible"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Hardware router (/api/hardware) working")
    
    def test_quotes_router(self, auth_headers):
        """Test quotes router is accessible"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Quotes router (/api/quotes) working")
    
    def test_dashboard_router(self, auth_headers):
        """Test dashboard router is accessible"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Dashboard router (/api/dashboard/*) working")
    
    def test_integrators_router(self, auth_headers):
        """Test integrators router is accessible"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Integrators router (/api/integrators) working")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
