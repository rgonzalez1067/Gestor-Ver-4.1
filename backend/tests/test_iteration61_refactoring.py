"""
Iteration 61: Backend Refactoring Test Suite
Tests all major endpoints across all 12 route modules after the modular refactoring
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://rif-sync-portal.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"

class TestAuthentication:
    """Test auth.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for all tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data
        return data["session_token"]
    
    def test_login_success(self):
        """Test POST /api/auth/login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
    
    def test_login_invalid_credentials(self):
        """Test POST /api/auth/login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
    
    def test_get_me(self, auth_token):
        """Test GET /api/auth/me"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "role" in data
        assert "sede" in data


class TestDashboard:
    """Test dashboard.py routes - NEW FEATURES"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_dashboard_stats(self, auth_token):
        """Test GET /api/dashboard/stats returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Verify all required fields exist
        assert "totalQuotes" in data
        assert "totalClients" in data
        assert "totalBanks" in data
        assert "totalMediosPago" in data
        assert "totalHardware" in data
        assert "exchangeRate" in data
        # Verify types
        assert isinstance(data["totalQuotes"], int)
        assert isinstance(data["totalClients"], int)
        assert isinstance(data["totalBanks"], int)
    
    def test_dashboard_stats_values(self, auth_token):
        """Test that dashboard stats return reasonable values"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        data = response.json()
        # Based on context: DB has ~143 quotes, 309 clients, 36 banks
        assert data["totalQuotes"] > 100, f"Expected >100 quotes, got {data['totalQuotes']}"
        assert data["totalClients"] > 200, f"Expected >200 clients, got {data['totalClients']}"
        assert data["totalBanks"] > 30, f"Expected >30 banks, got {data['totalBanks']}"
    
    def test_dashboard_alerts(self, auth_token):
        """Test GET /api/dashboard/alerts"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/alerts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "overdue" in data
        assert "today" in data
        assert "upcoming" in data
        assert "total" in data
    
    def test_missing_pdfs_endpoint(self, auth_token):
        """Test GET /api/dashboard/missing-pdfs - NEW FEATURE"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/missing-pdfs",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "missing_pdfs" in data
        assert "count" in data
        assert isinstance(data["missing_pdfs"], list)
        # Each item should have quote_id, quote_number
        if data["count"] > 0:
            first_item = data["missing_pdfs"][0]
            assert "quote_id" in first_item
            assert "quote_number" in first_item


class TestClients:
    """Test clients.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_clients(self, auth_token):
        """Test GET /api/clients"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify client structure
        first_client = data[0]
        assert "client_id" in first_client
        assert "rif" in first_client
        assert "legal_name" in first_client
    
    def test_search_clients(self, auth_token):
        """Test GET /api/clients/search"""
        response = requests.get(
            f"{BASE_URL}/api/clients/search?q=test",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200


class TestBanks:
    """Test banks.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_banks(self, auth_token):
        """Test GET /api/banks"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify bank structure
        first_bank = data[0]
        assert "bank_id" in first_bank
        assert "name" in first_bank
        assert "products" in first_bank


class TestServices:
    """Test services.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_services(self, auth_token):
        """Test GET /api/services"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0


class TestHardware:
    """Test hardware.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_hardware(self, auth_token):
        """Test GET /api/hardware"""
        response = requests.get(
            f"{BASE_URL}/api/hardware",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0


class TestIntegrators:
    """Test integrators.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_integrators(self, auth_token):
        """Test GET /api/integrators"""
        response = requests.get(
            f"{BASE_URL}/api/integrators",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestQuotes:
    """Test quotes.py routes"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_quotes(self, auth_token):
        """Test GET /api/quotes"""
        response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify quote structure
        first_quote = data[0]
        assert "quote_id" in first_quote
        assert "quote_number" in first_quote
        assert "total_usd" in first_quote
    
    def test_pg_recurring_costs(self, auth_token):
        """Test GET /api/pg-recurring-costs"""
        response = requests.get(
            f"{BASE_URL}/api/pg-recurring-costs",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "ranges" in data
        assert "data" in data


class TestRegeneratePDF:
    """Test regenerate-pdf endpoint - NEW FEATURE"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_regenerate_pdf_for_missing(self, auth_token):
        """Test POST /api/quotes/{id}/regenerate-pdf for a quote without PDF"""
        # First get the list of quotes missing PDFs
        response = requests.get(
            f"{BASE_URL}/api/dashboard/missing-pdfs",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            # Pick first quote to regenerate
            quote_id = data["missing_pdfs"][0]["quote_id"]
            quote_number = data["missing_pdfs"][0]["quote_number"]
            
            # Test regenerate endpoint
            regen_response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/regenerate-pdf",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            # It may fail for some quotes (e.g., equipment quotes), but should not return 500 error
            # Accept 200 (success) or 4xx (validation error)
            assert regen_response.status_code in [200, 400, 422, 404], \
                f"Unexpected status {regen_response.status_code}: {regen_response.text}"
            
            if regen_response.status_code == 200:
                regen_data = regen_response.json()
                assert "pdf_url" in regen_data
                assert "quote_number" in regen_data
                print(f"Successfully regenerated PDF for {quote_number}")
        else:
            pytest.skip("No quotes without PDF to test regeneration")
    
    def test_regenerate_pdf_invalid_quote(self, auth_token):
        """Test POST /api/quotes/{id}/regenerate-pdf with invalid quote_id"""
        response = requests.post(
            f"{BASE_URL}/api/quotes/invalid_id_123/regenerate-pdf",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404


class TestExchangeRate:
    """Test exchange rate endpoint in services.py"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["session_token"]
    
    def test_get_exchange_rate(self, auth_token):
        """Test GET /api/exchange-rate/current"""
        response = requests.get(
            f"{BASE_URL}/api/exchange-rate/current",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "rate" in data
        assert data["rate"] > 0


class TestUnauthorizedAccess:
    """Test that endpoints require authentication"""
    
    def test_dashboard_stats_unauthorized(self):
        """Test GET /api/dashboard/stats without auth"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 401
    
    def test_quotes_unauthorized(self):
        """Test GET /api/quotes without auth"""
        response = requests.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 401
    
    def test_clients_unauthorized(self):
        """Test GET /api/clients without auth"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 401
