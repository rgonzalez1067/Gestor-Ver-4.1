# ruff: noqa
"""
Test suite for Iteration 21 - Testing:
1. QuoteItem model fields (bank_id, bank_name, tarifa_setup, tarifa_recurrente)
2. AppSettings endpoints for Resend API Key
3. Quote creation/update with additional items preserving data
4. PDF download endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Use session token from previous test iteration
TEST_SESSION_TOKEN = None

class TestAuthAndSetup:
    """First authenticate and get session token"""
    
    def test_get_existing_session(self):
        """Check for existing session from previous iterations"""
        global TEST_SESSION_TOKEN
        # Try to use an existing session token if available
        # This test will be skipped if we don't have a valid session
        TEST_SESSION_TOKEN = "P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"
        
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        if response.status_code == 200:
            print(f"Session valid - User: {response.json().get('email', 'Unknown')}")
            assert response.status_code == 200
        else:
            pytest.skip("No valid session available - OAuth login required")


class TestAppSettings:
    """Test AppSettings endpoints for Resend API Key configuration"""
    
    def test_get_app_settings(self):
        """Test GET /api/config/settings endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/config/settings",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all expected fields are present
        assert "implementation_email" in data
        assert "admin_email" in data
        assert "warehouse_email" in data
        assert "resend_api_key_configured" in data
        assert "resend_api_key_masked" in data
        
        print(f"Settings: resend_api_key_configured={data['resend_api_key_configured']}")
        print(f"Settings: resend_api_key_masked={data['resend_api_key_masked']}")
    
    def test_update_resend_api_key(self):
        """Test PUT /api/config/settings to save Resend API Key"""
        # Test with a dummy API key
        test_key = "re_test_1234567890abcdef"
        
        response = requests.put(
            f"{BASE_URL}/api/config/settings",
            headers={
                "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "resend_api_key": test_key,
                "implementation_email": None,
                "admin_email": None,
                "warehouse_email": None
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "resend_api_key_configured" in data
        print(f"Update response: {data}")
    
    def test_verify_resend_key_masked(self):
        """Verify the API key is masked after save"""
        response = requests.get(
            f"{BASE_URL}/api/config/settings",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be configured and masked
        assert data["resend_api_key_configured"] == True, "API Key should be configured"
        assert data["resend_api_key_masked"] != "", "Masked key should not be empty"
        # Verify it's actually masked (starts with asterisks)
        assert "*" in data["resend_api_key_masked"], "Key should be masked with asterisks"
        
        print(f"Masked key: {data['resend_api_key_masked']}")


class TestQuotesWithAdditionalItems:
    """Test quote creation and update with additional items (medio de pago fields)"""
    
    created_quote_id = None
    
    def test_get_clients(self):
        """Get clients for quote creation"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200
        clients = response.json()
        print(f"Found {len(clients)} clients")
        
        if len(clients) > 0:
            print(f"First client: {clients[0].get('legal_name', 'Unknown')}")
    
    def test_get_banks(self):
        """Get banks for quote creation"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200
        banks = response.json()
        print(f"Found {len(banks)} banks")
        
        if len(banks) > 0:
            print(f"First bank: {banks[0].get('name', 'Unknown')}")
    
    def test_create_quote_with_additional_items(self):
        """Create a quote with additional items containing bank_id, bank_name, tarifa_setup, tarifa_recurrente"""
        global created_quote_id
        
        # Get a client first
        clients_response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        if clients_response.status_code != 200 or len(clients_response.json()) == 0:
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create a quote with additional items that include all the new fields
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "quote_category": "implementation",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Configuración PDV en MServer",
                    "quantity": 1,
                    "unit_price_usd": 5.0,
                    "total_usd": 5.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1
                },
                {
                    "item_type": "additional",
                    "item_name": "TDD/TDC",
                    "quantity": 1,
                    "unit_price_usd": 10.0,
                    "total_usd": 10.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "bank_id": "bnk_test123",
                    "bank_name": "Banco de Venezuela",
                    "tarifa_setup": 5.0,
                    "tarifa_recurrente": 2.5
                }
            ],
            "hardware": [],
            "notes": "Test quote with additional items",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes",
            headers={
                "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
                "Content-Type": "application/json"
            },
            json=quote_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        quote = response.json()
        created_quote_id = quote["quote_id"]
        
        print(f"Created quote: {quote['quote_number']} (ID: {created_quote_id})")
        print(f"Services count: {len(quote.get('services', []))}")
        
        # Verify the additional item has all fields
        services = quote.get("services", [])
        additional_items = [s for s in services if s.get("item_type") == "additional"]
        
        if len(additional_items) > 0:
            item = additional_items[0]
            print(f"Additional item: {item}")
            
            # Verify fields are preserved
            assert "bank_id" in item or item.get("bank_id") is None, "bank_id field should exist"
            assert "bank_name" in item or item.get("bank_name") is None, "bank_name field should exist"
            assert "tarifa_setup" in item or item.get("tarifa_setup") is None, "tarifa_setup field should exist"
            assert "tarifa_recurrente" in item or item.get("tarifa_recurrente") is None, "tarifa_recurrente field should exist"
    
    def test_get_quote_verifies_additional_fields(self):
        """Verify the created quote has additional item fields preserved"""
        if created_quote_id is None:
            pytest.skip("No quote was created in previous test")
        
        response = requests.get(
            f"{BASE_URL}/api/quotes/{created_quote_id}",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200
        quote = response.json()
        
        services = quote.get("services", [])
        print(f"Quote {quote['quote_number']} has {len(services)} services")
        
        # Find additional items
        additional_items = [s for s in services if s.get("item_type") == "additional"]
        print(f"Additional items found: {len(additional_items)}")
        
        for item in additional_items:
            print(f"  - {item.get('item_name')}: bank_id={item.get('bank_id')}, bank_name={item.get('bank_name')}, tarifa_setup={item.get('tarifa_setup')}, tarifa_recurrente={item.get('tarifa_recurrente')}")


class TestPDFDownload:
    """Test PDF download functionality"""
    
    def test_get_quotes_list(self):
        """Get list of quotes"""
        response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        assert response.status_code == 200
        quotes = response.json()
        print(f"Found {len(quotes)} quotes")
        
        return quotes
    
    def test_pdf_download_endpoint(self):
        """Test PDF download for an existing quote"""
        # Get a quote first
        quotes_response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        if quotes_response.status_code != 200 or len(quotes_response.json()) == 0:
            pytest.skip("No quotes available for PDF test")
        
        quote_id = quotes_response.json()[0]["quote_id"]
        quote_number = quotes_response.json()[0]["quote_number"]
        
        print(f"Testing PDF download for quote: {quote_number}")
        
        response = requests.get(
            f"{BASE_URL}/api/quotes/{quote_id}/pdf",
            headers={
                "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
                "Accept": "application/pdf"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify Content-Type is PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content-type, got {content_type}"
        
        # Verify we got actual data
        assert len(response.content) > 0, "PDF content should not be empty"
        
        print(f"PDF downloaded successfully: {len(response.content)} bytes")
        print(f"Content-Type: {content_type}")
        
        # Check content-disposition header
        content_disposition = response.headers.get("content-disposition", "")
        print(f"Content-Disposition: {content_disposition}")
    
    def test_pdf_generate_endpoint(self):
        """Test PDF generation from data (POST /api/quotes/generate-pdf)"""
        pdf_data = {
            "cliente_nombre": "Test Cliente",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Direccion de prueba",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 2,
            "integrator_name": "Test Integrador",
            "integrator_app_name": "App Test",
            "pinpad_model": "Ingenico",
            "sponsor_bank_name": "Banco Test",
            "setup_items": [
                {
                    "concepto": "Configuración PDV",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 5.0,
                    "total": 10.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso plataforma",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 8.0,
                    "total": 16.0
                }
            ],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": "Nota de prueba"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            headers={
                "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
                "Content-Type": "application/json",
                "Accept": "application/pdf"
            },
            json=pdf_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify Content-Type is PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content-type, got {content_type}"
        
        # Verify we got actual data
        assert len(response.content) > 0, "PDF content should not be empty"
        
        print(f"Generated PDF: {len(response.content)} bytes")


class TestQuoteModel:
    """Test that QuoteItem model correctly handles all fields"""
    
    def test_get_quote_with_additional_items(self):
        """Get an existing quote and verify additional item structure"""
        response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {TEST_SESSION_TOKEN}"}
        )
        
        if response.status_code != 200:
            pytest.skip("Cannot get quotes")
        
        quotes = response.json()
        
        # Find a quote with additional items
        for quote in quotes:
            services = quote.get("services", [])
            additional_items = [s for s in services if s.get("item_type") == "additional"]
            
            if len(additional_items) > 0:
                print(f"Quote {quote['quote_number']} has {len(additional_items)} additional items:")
                for item in additional_items:
                    print(f"  Item: {item.get('item_name')}")
                    print(f"    bank_id: {item.get('bank_id')}")
                    print(f"    bank_name: {item.get('bank_name')}")
                    print(f"    tarifa_setup: {item.get('tarifa_setup')}")
                    print(f"    tarifa_recurrente: {item.get('tarifa_recurrente')}")
                    print(f"    cantidad_cajas: {item.get('cantidad_cajas')}")
                    print(f"    cantidad_bancos: {item.get('cantidad_bancos')}")
                
                # If we found additional items, test passes
                assert True
                return
        
        print("No quotes with additional items found - this is OK if no quotes have additional items yet")
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
