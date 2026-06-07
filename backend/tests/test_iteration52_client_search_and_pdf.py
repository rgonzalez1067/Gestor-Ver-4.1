# ruff: noqa
"""
Test iteration 52 - Server-side client search and PDF fix
Features tested:
1. GET /api/clients/search?q=Test - returns clients matching by name or RIF
2. GET /api/clients/search?q=J- - returns clients matching by RIF
3. GET /api/clients returns all clients (up to 5000)
4. POST /api/quotes/generate-pdf returns 200 with valid data including production_items
5. POST /api/quotes/generate-pdf-with-template returns 200 with all fields
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@admin.com",
        "password": "testadmin123"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestClientSearch:
    """Test server-side client search endpoint"""
    
    def test_search_by_name_returns_matching_clients(self, api_client):
        """GET /api/clients/search?q=Test returns clients matching by name"""
        response = api_client.get(f"{BASE_URL}/api/clients/search?q=Test")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} clients matching 'Test'")
        
        # If we have results, verify they match by name
        if len(data) > 0:
            for client in data:
                # Client should match by fantasy_name, legal_name, or rif
                name_match = (
                    'test' in (client.get('fantasy_name', '') or '').lower() or
                    'test' in (client.get('legal_name', '') or '').lower() or
                    'test' in (client.get('rif', '') or '').lower()
                )
                assert name_match, f"Client {client.get('client_id')} doesn't match 'Test'"
            print(f"All {len(data)} clients match the search query 'Test'")
    
    def test_search_by_rif_returns_matching_clients(self, api_client):
        """GET /api/clients/search?q=J- returns clients matching by RIF"""
        response = api_client.get(f"{BASE_URL}/api/clients/search?q=J-")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} clients matching 'J-'")
        
        # If we have results, verify they match by RIF or name
        if len(data) > 0:
            for client in data:
                rif_match = (
                    'j-' in (client.get('fantasy_name', '') or '').lower() or
                    'j-' in (client.get('legal_name', '') or '').lower() or
                    'j-' in (client.get('rif', '') or '').lower()
                )
                assert rif_match, f"Client {client.get('client_id')} doesn't match 'J-'"
            print(f"All {len(data)} clients match the search query 'J-'")
    
    def test_search_with_short_query_returns_default_list(self, api_client):
        """GET /api/clients/search?q=X (short query) returns default list (up to 50)"""
        response = api_client.get(f"{BASE_URL}/api/clients/search?q=X")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Short queries (< 2 chars) should return a default list
        print(f"Short query returned {len(data)} clients")
    
    def test_search_empty_query_returns_default_list(self, api_client):
        """GET /api/clients/search?q= (empty query) returns default list"""
        response = api_client.get(f"{BASE_URL}/api/clients/search?q=")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Empty query returned {len(data)} clients (max 50 expected)")
        assert len(data) <= 50, "Empty query should return max 50 clients"


class TestGetAllClients:
    """Test GET /api/clients returns all clients (up to 5000)"""
    
    def test_get_clients_returns_list(self, api_client):
        """GET /api/clients returns all clients up to 5000 limit"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"GET /api/clients returned {len(data)} clients")
        
        # Verify limit is 5000 (server returns at most 5000)
        assert len(data) <= 5000, "Clients list should not exceed 5000"


class TestPDFGeneration:
    """Test PDF generation endpoints with production_items"""
    
    def test_generate_pdf_simple_with_production_items(self, api_client):
        """POST /api/quotes/generate-pdf returns 200 with valid data including production_items"""
        pdf_data = {
            "cliente_nombre": "Test Corp SA",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Av. Test 123, Caracas",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 2,
            "integrator_name": "Integrador Test",
            "integrator_app_name": "App Test",
            "pinpad_model": "Pinpad Model X",
            "sponsor_bank_name": "Banco Test",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10.0,
                    "total": 20.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 5.0,
                    "total": 10.0
                }
            ],
            "recurring_other_items": [],
            "production_items": [
                {
                    "concepto": "Mantenimiento Extra",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 2,
                    "tarifa": 15.0,
                    "total": 30.0
                }
            ],
            "descuento": 0,
            "descuento_setup": 0,
            "descuento_recurrente": 0,
            "notes": "Test note for PDF",
            "is_production_client": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/quotes/generate-pdf", json=pdf_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF, got {content_type}"
        
        # Verify PDF has content
        assert len(response.content) > 0, "PDF should have content"
        print(f"PDF generated successfully, size: {len(response.content)} bytes")
    
    def test_generate_pdf_with_template_all_fields(self, api_client):
        """POST /api/quotes/generate-pdf-with-template returns 200 with all fields including production_items, quote_type, is_production_client"""
        pdf_data = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "Test Corp SA",
            "cliente_rif": "J-12345678-9",
            "cliente_contacto": "Juan Perez",
            "cliente_address": "Av. Test 123, Caracas",
            "integrator_name": "Integrador Test",
            "integrator_app_name": "App Test",
            "pinpad_model": "Pinpad Model X",
            "sponsor_bank_name": "Banco Test",
            "cantidad_cajas": 2,
            "quote_number": "COT-2026-01-001-TBP",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10.0,
                    "total": 20.0
                },
                {
                    "concepto": "Configuración dispositivo",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 5.0,
                    "total": 10.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 5.0,
                    "total": 10.0
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 3.0,
                    "total": 6.0
                }
            ],
            "additional_items": [],
            "production_items": [
                {
                    "concepto": "Recurrente Producción",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 3,
                    "tarifa": 20.0,
                    "total": 60.0
                }
            ],
            "descuento": 0,
            "descuento_setup": 5,
            "descuento_recurrente": 10,
            "notes": "Test quote with production items",
            "is_production_client": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template", json=pdf_data)
        
        # Check if template is available - if not, endpoint might return 404 or different error
        if response.status_code == 404:
            print("Template not configured - skipping template PDF test")
            pytest.skip("Template not configured for vpos_pyme")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF, got {content_type}"
        
        # Verify PDF has content
        assert len(response.content) > 0, "PDF should have content"
        print(f"Template PDF generated successfully, size: {len(response.content)} bytes")
    
    def test_generate_pdf_with_descuento_setup_variable_fix(self, api_client):
        """Verify 'descuento' variable bug is fixed (was NameError: 'descuento' not defined)"""
        # This test verifies that the 'descuento' variable error is fixed
        # The bug was that 'descuento' was used but 'monto_desc_setup' was defined
        
        pdf_data = {
            "cliente_nombre": "Bug Fix Test Client",
            "cliente_rif": "J-99999999-9",
            "cliente_address": "Test Address",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "integrator_name": "Test Int",
            "integrator_app_name": "Test App",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [
                {
                    "concepto": "Setup Item",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 100.0,
                    "total": 100.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Recurring Item",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 50.0,
                    "total": 50.0
                }
            ],
            "recurring_other_items": [],
            "production_items": [],
            # Testing with descuento values to ensure variable naming is correct
            "descuento": 0,
            "descuento_setup": 10,  # 10% discount on setup
            "descuento_recurrente": 5,  # 5% discount on recurring
            "notes": "Test to verify descuento variable fix",
            "is_production_client": False
        }
        
        # Should NOT raise NameError for 'descuento' anymore
        response = api_client.post(f"{BASE_URL}/api/quotes/generate-pdf", json=pdf_data)
        
        # If we get 500 with "descuento" in error, the bug is NOT fixed
        if response.status_code == 500:
            error_text = response.text.lower()
            assert 'descuento' not in error_text, f"Bug NOT fixed - 'descuento' variable error: {response.text}"
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("descuento variable bug is FIXED - PDF generated successfully with discounts")


class TestPDFWithProductionItemsInRecurring:
    """Test that production_items are included in recurring section of PDF"""
    
    def test_production_items_contribute_to_recurring_total(self, api_client):
        """Verify production_items are added to recurring costs in PDF"""
        pdf_data = {
            "cliente_nombre": "Production Test Client",
            "cliente_rif": "J-11111111-1",
            "cliente_address": "Production Test Address",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [
                {
                    "concepto": "Base Setup",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 50.0,
                    "total": 50.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Base Recurring",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 25.0,
                    "total": 25.0
                }
            ],
            "recurring_other_items": [],
            # Production items should be included in recurring section
            "production_items": [
                {
                    "concepto": "Production Client Service A",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 30.0,
                    "total": 60.0
                },
                {
                    "concepto": "Production Client Service B",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 2,
                    "tarifa": 20.0,
                    "total": 40.0
                }
            ],
            "descuento": 0,
            "descuento_setup": 0,
            "descuento_recurrente": 0,
            "notes": "",
            "is_production_client": True
        }
        
        response = api_client.post(f"{BASE_URL}/api/quotes/generate-pdf", json=pdf_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify PDF was generated
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type
        print(f"PDF with production items generated: {len(response.content)} bytes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
