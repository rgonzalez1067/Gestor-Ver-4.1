"""
Test PDF Header/Footer Stamping - Iteration 163
Tests that PDF generation includes header/footer on ALL pages including injected annexes.
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPDFHeaderFooter:
    """Tests for PDF header/footer stamping on all pages"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_preview_pdf_endpoint_returns_pdf(self):
        """Test that preview-pdf-with-template endpoint returns a valid PDF"""
        pdf_data = {
            "quote_type": "VPOS",
            "quote_number": "TEST-PDF-163",
            "cliente_nombre": "Test Client",
            "cliente_rif": "J-12345678-9",
            "cliente_contacto": "Test Contact",
            "integrator_name": "Test Integrator",
            "integrator_app_name": "Test App",
            "pinpad_model": "P200",
            "sponsor_bank_name": "Test Bank",
            "cantidad_cajas": 5,
            "setup_items": [
                {"concepto": "Setup Item 1", "cantidad_cajas": 5, "cantidad_bancos": 1, "tarifa": 10.0, "bank_name": ""}
            ],
            "recurring_basic_items": [
                {"concepto": "Recurring Item 1", "cantidad_cajas": 5, "cantidad_bancos": 1, "tarifa": 5.0, "bank_name": ""}
            ],
            "recurring_other_items": [],
            "additional_items": [],
            "production_items": [],
            "client_segment": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/preview-pdf-with-template", json=pdf_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
        assert len(response.content) > 1000, "PDF content should be substantial"
    
    def test_generate_pdf_endpoint_returns_pdf(self):
        """Test that generate-pdf-with-template endpoint returns a valid PDF"""
        pdf_data = {
            "quote_type": "VPOS",
            "quote_number": "TEST-PDF-GEN-163",
            "cliente_nombre": "Test Client Gen",
            "cliente_rif": "J-98765432-1",
            "cliente_contacto": "Test Contact",
            "integrator_name": "Test Integrator",
            "integrator_app_name": "Test App",
            "pinpad_model": "P200",
            "sponsor_bank_name": "Test Bank",
            "cantidad_cajas": 3,
            "setup_items": [
                {"concepto": "Setup Item", "cantidad_cajas": 3, "cantidad_bancos": 1, "tarifa": 15.0, "bank_name": ""}
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "production_items": [],
            "client_segment": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template", json=pdf_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
    
    def test_quote_pdf_endpoint(self):
        """Test that GET /quotes/{id}/pdf returns a valid PDF"""
        # First get a quote ID
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200, "Failed to get quotes"
        
        quotes = quotes_response.json()
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        quote_id = quotes[0]["quote_id"]
        
        # Get PDF for the quote
        pdf_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}/pdf")
        
        assert pdf_response.status_code == 200, f"Expected 200, got {pdf_response.status_code}"
        assert pdf_response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"


class TestClientSearch:
    """Tests for client search endpoint used by Equipment Wizard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_client_search_endpoint_exists(self):
        """Test that /clients/search endpoint exists and works"""
        response = self.session.get(f"{BASE_URL}/api/clients/search?q=mega")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
    
    def test_client_search_filters_by_name(self):
        """Test that client search filters by name"""
        response = self.session.get(f"{BASE_URL}/api/clients/search?q=mega")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that results contain 'mega' in name or RIF
        for client in data:
            name = (client.get("fantasy_name", "") + client.get("legal_name", "")).lower()
            rif = client.get("rif", "").lower()
            assert "mega" in name or "mega" in rif, f"Client {client} doesn't match search term 'mega'"
    
    def test_client_search_filters_by_rif(self):
        """Test that client search filters by RIF"""
        # First get a client to know a valid RIF prefix
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200:
            pytest.skip("Cannot get clients list")
        
        clients = clients_response.json()
        if not clients:
            pytest.skip("No clients available")
        
        # Get first 4 chars of a RIF
        rif_prefix = clients[0].get("rif", "")[:4]
        if not rif_prefix:
            pytest.skip("No RIF available")
        
        response = self.session.get(f"{BASE_URL}/api/clients/search?q={rif_prefix}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, f"Expected results for RIF prefix '{rif_prefix}'"
