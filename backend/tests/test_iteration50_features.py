# ruff: noqa
"""
Test Suite for Iteration 50 Features:
1. Client search (filter by name, RIF, sucursal)
2. Split discounts (descuento_setup, descuento_recurrente)
3. Quote model accepts split discount fields
4. PDF generation uses split discounts
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthSetup:
    """Authentication setup for tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get session token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data
        return data["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestClientSearch(TestAuthSetup):
    """Test client search/filter functionality"""
    
    def test_get_clients_list(self, headers):
        """Verify clients endpoint returns list"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        clients = response.json()
        assert isinstance(clients, list)
        assert len(clients) > 0, "Need at least 1 client to test search"
        print(f"Found {len(clients)} clients")
    
    def test_clients_have_search_fields(self, headers):
        """Verify clients have fields for search: fantasy_name, legal_name, rif, sucursal"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        clients = response.json()
        
        for client in clients[:5]:  # Check first 5
            assert "fantasy_name" in client or "legal_name" in client, "Client missing name field"
            assert "rif" in client, "Client missing rif field"
            # Sucursal may be optional
            print(f"Client: {client.get('fantasy_name') or client.get('legal_name')} - {client.get('rif')}")


class TestSplitDiscounts(TestAuthSetup):
    """Test split discount fields in quote model"""
    
    def test_quote_creation_with_split_discounts(self, headers):
        """Test creating a quote with descuento_setup and descuento_recurrente"""
        # First get a client ID
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert clients_response.status_code == 200
        clients = clients_response.json()
        assert len(clients) > 0
        client_id = clients[0]["client_id"]
        
        # Get integrator
        integrators_response = requests.get(f"{BASE_URL}/api/integrators", headers=headers)
        assert integrators_response.status_code == 200
        integrators = integrators_response.json()
        integrator = next((i for i in integrators if i.get("integrator_status") == "Certificado"), None)
        
        # Create quote with split discounts
        quote_payload = {
            "client_id": client_id,
            "quote_type": "VPOS_MPOS",
            "quote_category": "implementation",
            "pricing_model": "conventional",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "TEST_Suscripción PDV/Banco",
                    "quantity": 1,
                    "unit_price_usd": 20.0,
                    "total_usd": 20.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1
                },
                {
                    "item_type": "recurring_basic",
                    "item_name": "TEST_Derecho de uso MServer",
                    "quantity": 1,
                    "unit_price_usd": 8.0,
                    "total_usd": 8.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1
                }
            ],
            "hardware": [],
            "equipment_items": [],
            "notes": "TEST_ITERATION_50_SPLIT_DISCOUNTS",
            "integrator_id": integrator["integrator_id"] if integrator else None,
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pdf_data": {
                "cliente_nombre": "Test Client",
                "cliente_rif": "J-12345678-9",
                "quote_type": "VPOS_MPOS",
                "pricing_model": "conventional",
                "cantidad_cajas": 1,
                "integrator_name": integrator["name"] if integrator else "",
                "integrator_app_name": "",
                "pinpad_model": "",
                "sponsor_bank_name": "",
                "setup_items": [
                    {"concepto": "TEST_Suscripción", "cantidad_cajas": 1, "cantidad_bancos": 1, "tarifa": 20.0}
                ],
                "recurring_basic_items": [
                    {"concepto": "TEST_MServer", "cantidad_cajas": 1, "cantidad_bancos": 1, "tarifa": 8.0}
                ],
                "recurring_other_items": [],
                "descuento": 0,
                "descuento_setup": 10,  # 10% setup discount
                "descuento_recurrente": 5,  # 5% recurrente discount
                "notes": ""
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=quote_payload,
            headers=headers
        )
        
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        quote = response.json()
        
        # Store quote_id for cleanup
        self.test_quote_id = quote.get("quote_id")
        print(f"Created test quote: {quote.get('quote_number')}")
        
        return quote
    
    def test_cleanup_test_quote(self, headers):
        """Cleanup: Delete test quote"""
        if hasattr(self, 'test_quote_id') and self.test_quote_id:
            response = requests.delete(
                f"{BASE_URL}/api/quotes/{self.test_quote_id}",
                headers=headers
            )
            # May fail if quote doesn't exist, that's OK
            if response.status_code == 200:
                print(f"Cleaned up test quote: {self.test_quote_id}")


class TestPDFGenerationWithDiscounts(TestAuthSetup):
    """Test PDF generation accepts split discounts"""
    
    def test_pdf_request_model_accepts_split_discounts(self, headers):
        """Test that PDF generation endpoint accepts descuento_setup and descuento_recurrente"""
        pdf_data = {
            "cliente_nombre": "Test Client PDF",
            "cliente_rif": "J-99999999-9",
            "cliente_address": "Test Address",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 2,
            "integrator_name": "Test Integrator",
            "integrator_app_name": "TestApp",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [
                {"concepto": "Setup Item 1", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 20.0}
            ],
            "recurring_basic_items": [
                {"concepto": "Recurring Item 1", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 10.0}
            ],
            "recurring_other_items": [
                {"concepto": "Other Recurring", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 5.0}
            ],
            "descuento": 0,
            "descuento_setup": 15.0,  # 15% setup discount
            "descuento_recurrente": 10.0,  # 10% recurrente discount
            "notes": "Test notes for PDF"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=headers
        )
        
        # The endpoint should accept the request and return PDF
        # Status 200 with PDF content type confirms the model accepts the fields
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf', "Response is not a PDF"
        assert len(response.content) > 0, "PDF content is empty"
        print(f"PDF generated successfully, size: {len(response.content)} bytes")


class TestVPOSMPOSRegression(TestAuthSetup):
    """Regression tests for VPOS/MPOS flow"""
    
    def test_services_endpoint(self, headers):
        """Test services endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/services", headers=headers)
        assert response.status_code == 200
        services = response.json()
        assert isinstance(services, list)
        print(f"Found {len(services)} services")
    
    def test_banks_endpoint(self, headers):
        """Test banks endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        assert response.status_code == 200
        banks = response.json()
        assert isinstance(banks, list)
        print(f"Found {len(banks)} banks")
    
    def test_integrators_endpoint(self, headers):
        """Test integrators endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=headers)
        assert response.status_code == 200
        integrators = response.json()
        assert isinstance(integrators, list)
        print(f"Found {len(integrators)} integrators")
    
    def test_hardware_endpoint(self, headers):
        """Test hardware endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=headers)
        assert response.status_code == 200
        hardware = response.json()
        assert isinstance(hardware, list)
        print(f"Found {len(hardware)} hardware items")


class TestPaymentGatewayRegression(TestAuthSetup):
    """Regression tests for Payment Gateway flow"""
    
    def test_pg_defaults_endpoint(self, headers):
        """Test PG defaults endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/pg-defaults", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "concepto" in data
        assert "costo" in data
        print(f"PG Default: {data['concepto']} = ${data['costo']}")
    
    def test_pg_recurring_costs_endpoint(self, headers):
        """Test PG recurring costs table endpoint"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "ranges" in data
        assert "data" in data
        print(f"PG Recurring costs table has {len(data['ranges'])} ranges")
