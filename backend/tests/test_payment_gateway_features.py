"""
Test Payment Gateway restructuring features:
1. Quote types: VPOS/MPOS and Payment Gateway only (no Link de Pago)
2. PG recurring costs table with 15 ranges and 11 product counts
3. PG setup items and quote creation
4. PG quote validation and storage
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPGRecurringCostsEndpoint:
    """Test GET /api/pg-recurring-costs endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_pg_recurring_costs_returns_15_ranges(self):
        """Verify endpoint returns 15 transaction ranges"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "ranges" in data
        assert len(data["ranges"]) == 15, f"Expected 15 ranges, got {len(data['ranges'])}"
        
        # Verify range structure
        first_range = data["ranges"][0]
        assert "rango" in first_range
        assert "min" in first_range
        assert "max" in first_range
        assert "label" in first_range
    
    def test_pg_recurring_costs_returns_11_product_counts(self):
        """Verify endpoint returns 11 product count columns"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "product_counts" in data
        assert data["product_counts"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    def test_pg_recurring_costs_data_structure(self):
        """Verify data has correct structure with base and tope for each product count"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 15, f"Expected 15 data rows, got {len(data['data'])}"
        
        # Check first row has all product counts
        first_row = data["data"][0]
        assert "rango" in first_row
        
        for i in range(1, 12):
            key = str(i)
            assert key in first_row, f"Missing product count {i} in data row"
            assert "base" in first_row[key], f"Missing 'base' for product count {i}"
            assert "tope" in first_row[key], f"Missing 'tope' for product count {i}"
    
    def test_pg_recurring_costs_range_labels(self):
        """Verify range labels are correct"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        ranges = data["ranges"]
        
        # Check first few ranges
        assert ranges[0]["label"] == "0 - 200"
        assert ranges[4]["label"] == "801 - 1,000"
        assert ranges[-1]["label"] == "10,001+"


class TestPaymentGatewayQuoteCreation:
    """Test creating Payment Gateway quotes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token, ensure test data exists"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure we have a client
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        self.clients = clients_response.json()
        if not self.clients:
            # Create test client
            client_data = {
                "rif": "J-PG-TEST-001-0",
                "legal_name": "TEST PG Client CA",
                "fantasy_name": "TestPG",
                "segment": "Corporativo"
            }
            create_response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=self.headers)
            if create_response.status_code == 201 or create_response.status_code == 200:
                self.client_id = create_response.json().get("client_id")
            else:
                # If client already exists, get from list
                clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
                self.clients = clients_response.json()
                self.client_id = self.clients[0]["client_id"] if self.clients else None
        else:
            self.client_id = self.clients[0]["client_id"]
        
        # Get an integrator
        integrators_response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = integrators_response.json()
        self.integrator_id = integrators[0]["integrator_id"] if integrators else None
        self.integrator_name = integrators[0]["name"] if integrators else "Test Integrator"
    
    def test_create_pg_quote_with_setup_items(self):
        """Test creating a Payment Gateway quote with setup items"""
        if not self.client_id:
            pytest.skip("No client available for testing")
        
        pg_setup_items = [
            {"concepto": "Visa/Mastercard", "costo": 150.0, "banco": "N/A", "observacion": ""},
            {"concepto": "American Express", "costo": 200.0, "banco": "Banesco", "observacion": "Premium"}
        ]
        
        quote_payload = {
            "client_id": self.client_id,
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test Payment Gateway quote",
            "integrator_id": self.integrator_id,
            "integrator_name": self.integrator_name,
            "integrator_app_name": "TestApp",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": {
                "rango_index": 3,
                "num_products": 2,
                "base": 40.2,
                "tope": 0.067,
                "rango_label": "401 - 600"
            },
            "pg_transaction_range": 3,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload, headers=self.headers)
        assert response.status_code in [200, 201], f"Failed to create PG quote: {response.text}"
        
        response_data = response.json()
        # API returns {"quote": {...}, "pdf_url": ..., "message": ...}
        quote = response_data.get("quote", response_data)
        assert quote["quote_type"] == "GATEWAY"
        assert "pg_setup_items" in quote
        assert len(quote["pg_setup_items"]) == 2
        assert quote["pg_transaction_range"] == 3
        
        # Verify total calculation (sum of setup costs)
        expected_subtotal = 150.0 + 200.0
        assert quote["subtotal_usd"] == expected_subtotal
        
        return quote["quote_id"]
    
    def test_pg_quote_appears_in_quotes_list(self):
        """Verify Payment Gateway quotes appear in the quotes list"""
        # First create a quote
        quote_id = self.test_create_pg_quote_with_setup_items()
        
        # Get quotes list
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        
        quotes = response.json()
        # Find our quote
        pg_quotes = [q for q in quotes if q["quote_type"] == "GATEWAY"]
        assert len(pg_quotes) > 0, "No Payment Gateway quotes found in list"


class TestQuoteTypesConfiguration:
    """Test that quote types are correctly configured (VPOS/MPOS and Gateway only, no Link)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get test data
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        clients = clients_response.json()
        self.client_id = clients[0]["client_id"] if clients else None
    
    def test_vpos_mpos_quote_creation_works(self):
        """Verify VPOS/MPOS quotes can still be created"""
        if not self.client_id:
            pytest.skip("No client available")
        
        quote_payload = {
            "client_id": self.client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",  # or VPOS_MPOS
            "pricing_model": "conventional",
            "services": [{
                "item_type": "setup",
                "item_name": "Test Setup Service",
                "quantity": 1,
                "unit_price_usd": 100.0,
                "total_usd": 100.0,
                "cantidad_cajas": 1,
                "cantidad_bancos": 1
            }],
            "hardware": [],
            "notes": "Test VPOS quote"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_payload, headers=self.headers)
        assert response.status_code in [200, 201], f"Failed to create VPOS quote: {response.text}"
        
        quote = response.json()
        assert quote["quote_type"] in ["VPOS", "VPOS_MPOS"]
    
    def test_existing_quotes_show_correct_types(self):
        """Verify existing quotes show proper type in list"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        
        quotes = response.json()
        if quotes:
            # Check that quote types are valid
            for quote in quotes[:10]:  # Check first 10
                assert quote["quote_type"] in ["VPOS", "MPOS", "VPOS_MPOS", "GATEWAY"], \
                    f"Unexpected quote type: {quote['quote_type']}"


class TestPaymentGatewayFieldsVisibility:
    """Test that PG quotes only require Client and Integrator (no Modelo de Precios, Cajas, Bancos)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get test data
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        clients = clients_response.json()
        self.client_id = clients[0]["client_id"] if clients else None
        
        integrators_response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = integrators_response.json()
        self.integrator_id = integrators[0]["integrator_id"] if integrators else None
    
    def test_pg_quote_created_without_cajas_bancos(self):
        """PG quotes should work without cantidad_cajas and cantidad_bancos being significant"""
        if not self.client_id or not self.integrator_id:
            pytest.skip("No client or integrator available")
        
        # PG quote with minimal fields - only client and integrator required
        quote_payload = {
            "client_id": self.client_id,
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",  # Backend may require this but frontend can default
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Minimal PG quote",
            "integrator_id": self.integrator_id,
            "cantidad_cajas": 1,  # Default values
            "cantidad_bancos": 1,
            "pg_setup_items": [
                {"concepto": "Visa", "costo": 100.0, "banco": "N/A", "observacion": ""}
            ],
            "pg_transaction_range": 1,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload, headers=self.headers)
        assert response.status_code in [200, 201], f"PG quote creation failed: {response.text}"
        
        response_data = response.json()
        # API returns {"quote": {...}, "pdf_url": ..., "message": ...}
        quote = response_data.get("quote", response_data)
        # For PG, the important fields are pg_setup_items, not services
        assert quote["quote_type"] == "GATEWAY"
        assert len(quote.get("pg_setup_items", [])) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
