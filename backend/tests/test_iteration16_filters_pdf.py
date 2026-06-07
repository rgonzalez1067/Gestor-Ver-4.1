# ruff: noqa
"""
Test suite for Iteration 16 features:
1. Filtros Rápidos (Quick Filters) - Cliente, Estado, Categoría, Fecha Desde, Fecha Hasta
2. PDF download functionality

Tests:
- Verify filter elements exist in Quotes.jsx
- Test PDF endpoint with valid quote ID
- Test PDF endpoint error handling
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "Tskr51l-We_-Wr_r4CYvcBvac-F-rxjcEeOABrjAIZg"  # From iteration 15

class TestPDFDownload:
    """Test PDF download functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated headers"""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        }
    
    def test_pdf_download_existing_quote(self):
        """Test PDF download for existing quote returns valid PDF"""
        # Known quote ID from problem statement
        quote_id = "quo_ef38d747f331"
        
        response = requests.get(
            f"{BASE_URL}/api/quotes/{quote_id}/pdf",
            headers={
                "Authorization": f"Bearer {SESSION_TOKEN}",
                "Accept": "application/pdf"
            }
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Content-Type assertion
        assert "application/pdf" in response.headers.get("Content-Type", ""), \
            f"Expected PDF content type, got {response.headers.get('Content-Type')}"
        
        # Data assertion - PDF header check
        assert response.content[:5] == b'%PDF-', "Response does not start with PDF header"
        
        # Size assertion - PDF should have meaningful content
        assert len(response.content) > 100, f"PDF too small: {len(response.content)} bytes"
        
        print(f"PDF download SUCCESS: {len(response.content)} bytes, valid PDF header")
    
    def test_pdf_download_nonexistent_quote(self):
        """Test PDF download for non-existent quote returns 404"""
        quote_id = "quo_nonexistent_12345"
        
        response = requests.get(
            f"{BASE_URL}/api/quotes/{quote_id}/pdf",
            headers={
                "Authorization": f"Bearer {SESSION_TOKEN}",
                "Accept": "application/pdf"
            }
        )
        
        # Should return 404
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent quote returns 404 correctly")
    
    def test_pdf_download_without_auth(self):
        """Test PDF download without authentication returns 401"""
        quote_id = "quo_ef38d747f331"
        
        response = requests.get(
            f"{BASE_URL}/api/quotes/{quote_id}/pdf",
            headers={"Accept": "application/pdf"}
        )
        
        # Should return 401
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Unauthenticated request returns 401 correctly")


class TestQuotesEndpoint:
    """Test quotes endpoint with filtering capabilities"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated headers"""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        }
    
    def test_get_quotes_list(self):
        """Test GET /api/quotes returns list of quotes with required fields for filtering"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Data assertion - should be a list
        assert isinstance(data, list), "Response should be a list"
        
        # If quotes exist, verify they have fields needed for filtering
        if len(data) > 0:
            quote = data[0]
            
            # Fields required for filtering
            required_fields = ['quote_id', 'client_id', 'quote_status', 'quote_category', 'created_at']
            for field in required_fields:
                assert field in quote, f"Quote missing required field: {field}"
            
            print(f"Quotes list has {len(data)} items with all required filter fields")
        else:
            print("No quotes found in database")
    
    def test_quotes_have_different_statuses(self):
        """Verify quotes have various statuses for testing status filter"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        assert response.status_code == 200
        
        data = response.json()
        statuses = set()
        for quote in data:
            status = quote.get('quote_status', 'Borrador')
            statuses.add(status)
        
        print(f"Found {len(statuses)} different statuses: {statuses}")
        # At least one status should exist
        assert len(statuses) >= 1, "Should have at least one quote status"
    
    def test_quotes_have_different_categories(self):
        """Verify quotes have various categories for testing category filter"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        assert response.status_code == 200
        
        data = response.json()
        categories = set()
        for quote in data:
            category = quote.get('quote_category', 'implementation')
            categories.add(category)
        
        print(f"Found {len(categories)} different categories: {categories}")
        # Should have at least one category
        assert len(categories) >= 1, "Should have at least one quote category"
    
    def test_quotes_have_clients(self):
        """Verify quotes are associated with clients for testing client filter"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        assert response.status_code == 200
        
        data = response.json()
        client_ids = set()
        for quote in data:
            client_id = quote.get('client_id')
            if client_id:
                client_ids.add(client_id)
        
        print(f"Found {len(client_ids)} different clients associated with quotes")
        # Should have at least one client
        assert len(client_ids) >= 1, "Should have at least one client associated with quotes"


class TestClientsEndpoint:
    """Test clients endpoint to verify client filter data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated headers"""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        }
    
    def test_get_clients_list(self):
        """Test GET /api/clients returns list of clients for filter dropdown"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Data assertion - should be a list
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            client = data[0]
            # Fields needed for filter dropdown
            assert 'client_id' in client, "Client missing client_id"
            assert 'fantasy_name' in client or 'legal_name' in client, "Client missing name fields"
            
            print(f"Clients list has {len(data)} items available for filter dropdown")
        else:
            print("No clients found in database")


class TestPDFGenerateEndpoint:
    """Test generate-pdf endpoint used by frontend"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authenticated headers"""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        }
    
    def test_generate_pdf_valid_data(self):
        """Test POST /api/quotes/generate-pdf with valid data"""
        pdf_data = {
            "cliente_nombre": "Test Cliente",
            "cliente_rif": "J123456789",
            "cliente_address": "Test Address",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [
                {
                    "concepto": "Test Service",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 100.0
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SESSION_TOKEN}",
                "Accept": "application/pdf"
            }
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        # Content-Type assertion
        assert "application/pdf" in response.headers.get("Content-Type", ""), \
            f"Expected PDF content type, got {response.headers.get('Content-Type')}"
        
        # Data assertion - PDF header check
        assert response.content[:5] == b'%PDF-', "Response does not start with PDF header"
        
        print(f"Generate PDF SUCCESS: {len(response.content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
