"""
PDF Download Tests for Cotizador Merchant Server
Tests PDF generation endpoints for Quotes, Clients, and Banks modules
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://import-wizard-42.preview.emergentagent.com')
SESSION_TOKEN = "test_session_pdf_12345"

@pytest.fixture
def api_client():
    """Shared requests session with authentication"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    })
    return session


class TestQuotesPDFDownload:
    """Test PDF download functionality for Quotes module"""
    
    def test_quotes_list_available(self, api_client):
        """Verify quotes are available for PDF download testing"""
        response = api_client.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        quotes = response.json()
        assert len(quotes) > 0, "No quotes available for testing"
        print(f"Found {len(quotes)} quotes available")
    
    def test_quote_pdf_endpoint_returns_pdf(self, api_client):
        """Test GET /api/quotes/{id}/pdf returns valid PDF"""
        # First get a quote with data
        response = api_client.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        quotes = response.json()
        
        # Find a quote with services (COT-2026-042 has data)
        quote_id = None
        for q in quotes:
            if q.get('services') and len(q['services']) > 0:
                quote_id = q['quote_id']
                break
        
        if not quote_id:
            quote_id = quotes[0]['quote_id']
        
        # Request PDF
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/pdf",
            headers={"Accept": "application/pdf"}
        )
        
        # Assert response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        # Assert Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type, f"Expected application/pdf, got {content_type}"
        
        # Assert Content-Disposition
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp, f"Expected attachment, got {content_disp}"
        assert 'filename=' in content_disp, f"Expected filename in Content-Disposition: {content_disp}"
        
        # Assert PDF content
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content.startswith(b'%PDF'), f"Content doesn't start with %PDF, got: {content[:20]}"
        
        print(f"SUCCESS: PDF downloaded - {len(content)} bytes")
    
    def test_quote_pdf_not_found(self, api_client):
        """Test PDF endpoint returns 404 for non-existent quote"""
        response = api_client.get(
            f"{BASE_URL}/api/quotes/quo_nonexistent123/pdf",
            headers={"Accept": "application/pdf"}
        )
        assert response.status_code == 404
    
    def test_quote_pdf_unauthorized(self):
        """Test PDF endpoint returns 401 without auth token"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/quo_a4de16cf7ab2/pdf",
            headers={"Accept": "application/pdf"}
        )
        assert response.status_code == 401


class TestClientsPDFExport:
    """Test PDF export functionality for Clients module"""
    
    def test_clients_pdf_export(self, api_client):
        """Test GET /api/clients/export/pdf returns valid PDF"""
        response = api_client.get(
            f"{BASE_URL}/api/clients/export/pdf",
            headers={"Accept": "application/pdf"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Assert Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type
        
        # Assert Content-Disposition
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp
        assert 'clientes.pdf' in content_disp.lower()
        
        # Assert PDF content
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content.startswith(b'%PDF')
        
        print(f"SUCCESS: Clients PDF exported - {len(content)} bytes")
    
    def test_clients_pdf_unauthorized(self):
        """Test clients PDF export returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/clients/export/pdf")
        assert response.status_code == 401


class TestBanksPDFExport:
    """Test PDF export functionality for Banks module"""
    
    def test_banks_pdf_export(self, api_client):
        """Test GET /api/banks/export/pdf returns valid PDF"""
        response = api_client.get(
            f"{BASE_URL}/api/banks/export/pdf",
            headers={"Accept": "application/pdf"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Assert Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type
        
        # Assert Content-Disposition
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp
        assert 'bancos.pdf' in content_disp.lower()
        
        # Assert PDF content
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content.startswith(b'%PDF')
        
        print(f"SUCCESS: Banks PDF exported - {len(content)} bytes")
    
    def test_banks_pdf_unauthorized(self):
        """Test banks PDF export returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/banks/export/pdf")
        assert response.status_code == 401


class TestServicesPDFExport:
    """Test PDF export functionality for Services/Medios de Pago module"""
    
    def test_services_pdf_export(self, api_client):
        """Test GET /api/services/export/pdf returns valid PDF"""
        response = api_client.get(
            f"{BASE_URL}/api/services/export/pdf",
            headers={"Accept": "application/pdf"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Assert Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type
        
        # Assert PDF content
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content.startswith(b'%PDF')
        
        print(f"SUCCESS: Services PDF exported - {len(content)} bytes")


class TestQuotePDFGeneration:
    """Test POST /api/quotes/generate-pdf endpoint for on-the-fly PDF generation"""
    
    def test_generate_pdf_from_data(self, api_client):
        """Test generating PDF from quote data without saving to DB"""
        pdf_data = {
            "cliente_nombre": "Test Cliente",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Test Address",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 5,
            "integrator_name": "Test Integrator",
            "integrator_app_name": "TestApp",
            "pinpad_model": "Pinpad V3",
            "sponsor_bank_name": "Test Bank",
            "setup_items": [
                {
                    "concepto": "Setup Service",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 2,
                    "tarifa": 100.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Monthly Service",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 2,
                    "tarifa": 50.0
                }
            ],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": "Test quote notes"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers={"Accept": "application/pdf"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Assert Content-Type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type
        
        # Assert PDF content
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content.startswith(b'%PDF')
        
        print(f"SUCCESS: Generated PDF from data - {len(content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
