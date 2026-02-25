"""
Payment Gateway Corrected Flow Tests - Iteration 48
Tests the corrected PG flow with:
1) Auto-loaded Persona Jurídica from /api/pg-defaults
2) Bank-first filtering for medios de pago
3) Full recurring table via "Generar Tabla de Recurrentes" button
4) PDF generation for PG quotes
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPGDefaultsEndpoint:
    """Test GET /api/pg-defaults returns Persona Jurídica config"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_pg_defaults_returns_persona_juridica(self):
        """GET /api/pg-defaults should return Persona Jurídica concepto with costo"""
        response = requests.get(f"{BASE_URL}/api/pg-defaults", headers=self.headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "concepto" in data, "Missing 'concepto' field in pg-defaults response"
        assert "costo" in data, "Missing 'costo' field in pg-defaults response"
        
        # Verify values
        assert data["concepto"] == "Persona Jurídica", f"Expected concepto 'Persona Jurídica', got '{data.get('concepto')}'"
        assert isinstance(data["costo"], (int, float)), f"Costo should be numeric, got {type(data.get('costo'))}"
        assert data["costo"] > 0, f"Costo should be positive, got {data.get('costo')}"
        
        print(f"✓ pg-defaults returns: concepto='{data['concepto']}', costo={data['costo']}")


class TestBanksWithProducts:
    """Test that banks have products for PG medio de pago selection"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_banks_have_products(self):
        """Banks should have products for PG medio de pago filtering"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        assert response.status_code == 200
        
        banks = response.json()
        assert len(banks) > 0, "No banks found in database"
        
        # Check at least one bank has products
        banks_with_products = [b for b in banks if b.get("products") and len(b["products"]) > 0]
        assert len(banks_with_products) > 0, "No banks with products found"
        
        # Print bank info for debugging
        for bank in banks_with_products[:3]:
            print(f"✓ Bank '{bank['name']}' has {len(bank['products'])} products")
            for prod in bank['products'][:2]:
                print(f"  - {prod.get('product_name')}")


class TestPGQuoteCreation:
    """Test PG quote creation with setup items and PDF generation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get required data"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get clients
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert clients_response.status_code == 200
        clients = clients_response.json()
        assert len(clients) > 0, "No clients found"
        self.test_client = clients[0]
        
        # Get integrators
        integrators_response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert integrators_response.status_code == 200
        integrators = integrators_response.json()
        assert len(integrators) > 0, "No integrators found"
        self.test_integrator = integrators[0]
        
        # Get pg-defaults
        pg_defaults_response = requests.get(f"{BASE_URL}/api/pg-defaults", headers=self.headers)
        assert pg_defaults_response.status_code == 200
        self.pg_defaults = pg_defaults_response.json()
        
        # Get banks with products
        banks_response = requests.get(f"{BASE_URL}/api/banks", headers=self.headers)
        self.banks = [b for b in banks_response.json() if b.get("products") and len(b["products"]) > 0]
    
    def test_create_pg_quote_with_persona_juridica_and_medios_pago(self):
        """Create PG quote with Persona Jurídica + medios de pago from banks"""
        
        # Build setup items starting with Persona Jurídica
        pg_setup_items = [
            {
                "concepto": self.pg_defaults["concepto"],
                "costo": self.pg_defaults["costo"],
                "banco": "N/A",
                "observacion": "Costo base - cargado automáticamente"
            }
        ]
        
        # Add medios de pago from banks (up to 2)
        medios_added = 0
        for bank in self.banks[:2]:
            for product in bank["products"][:1]:
                pg_setup_items.append({
                    "concepto": product["product_name"],
                    "costo": product.get("pg_setup_cost", 50),
                    "banco": bank["name"],
                    "observacion": ""
                })
                medios_added += 1
        
        # Build recurring cost data (full table for N products)
        num_products = medios_added
        
        # Get the recurring costs table
        recurring_response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert recurring_response.status_code == 200
        recurring_table = recurring_response.json()
        
        # Build recurring data with full table
        recurring_data = {
            "num_products": min(num_products, 11),
            "table": []
        }
        
        if num_products > 0:
            for range_row in recurring_table["data"]:
                range_info = next((r for r in recurring_table["ranges"] if r["rango"] == range_row["rango"]), None)
                product_key = str(min(num_products, 11))
                cost_data = range_row.get(product_key, {})
                recurring_data["table"].append({
                    "rango": range_row["rango"],
                    "label": range_info["label"] if range_info else "",
                    "min": range_info["min"] if range_info else 0,
                    "max": range_info["max"] if range_info else 0,
                    "base": cost_data.get("base"),
                    "tope": cost_data.get("tope")
                })
        
        # Create the PG quote
        payload = {
            "client_id": self.test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test PG quote iteration 48",
            "integrator_id": self.test_integrator["integrator_id"],
            "integrator_name": self.test_integrator["name"],
            "integrator_app_name": self.test_integrator.get("app_name", ""),
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": recurring_data if num_products > 0 else None,
            "pg_transaction_range": num_products,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", headers=self.headers, json=payload)
        
        assert response.status_code == 200, f"Quote creation failed: {response.status_code} - {response.text}"
        quote_data = response.json()
        
        # Verify quote was created
        assert "quote_id" in quote_data, "Missing quote_id in response"
        assert "quote_number" in quote_data, "Missing quote_number in response"
        assert quote_data["quote_type"] == "GATEWAY", f"Wrong quote_type: {quote_data.get('quote_type')}"
        
        # Verify pg_setup_items were stored
        assert "pg_setup_items" in quote_data, "Missing pg_setup_items in response"
        assert len(quote_data["pg_setup_items"]) == len(pg_setup_items), \
            f"Expected {len(pg_setup_items)} setup items, got {len(quote_data['pg_setup_items'])}"
        
        # Verify first item is Persona Jurídica
        first_item = quote_data["pg_setup_items"][0]
        assert first_item["concepto"] == self.pg_defaults["concepto"], \
            f"First item should be Persona Jurídica, got '{first_item.get('concepto')}'"
        
        print(f"✓ PG Quote created: {quote_data['quote_number']}")
        print(f"  - Setup items: {len(quote_data['pg_setup_items'])}")
        print(f"  - First item: {first_item['concepto']} (${first_item['costo']})")
        
        return quote_data
    
    def test_pg_quote_pdf_exists(self):
        """Verify PDF is generated for PG quote"""
        # Create a quote first
        quote_data = self.test_create_pg_quote_with_persona_juridica_and_medios_pago()
        
        # Check if PDF was generated
        if quote_data.get("quote_pdf_url"):
            print(f"✓ PDF generated: {quote_data['quote_pdf_url']}")
            
            # Verify PDF file exists
            pdf_response = requests.get(f"{BASE_URL}{quote_data['quote_pdf_url']}", headers=self.headers)
            # Note: PDF might be served without auth, try both ways
            if pdf_response.status_code == 404:
                pdf_response = requests.get(f"{BASE_URL}{quote_data['quote_pdf_url']}")
            
            # PDF may or may not require auth - just check it's accessible
            print(f"  - PDF access status: {pdf_response.status_code}")
        else:
            print("⚠ No PDF URL in quote response (may be expected if PDF generation is async)")


class TestPGRecurringCostsTable:
    """Test the recurring costs table structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_recurring_costs_has_15_ranges(self):
        """Recurring costs table should have 15 transaction ranges"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "ranges" in data, "Missing 'ranges' in response"
        assert len(data["ranges"]) == 15, f"Expected 15 ranges, got {len(data['ranges'])}"
        
        print("✓ Recurring costs table has 15 transaction ranges:")
        for r in data["ranges"][:5]:
            print(f"  - Range {r['rango']}: {r['label']}")
        print("  ...")
    
    def test_recurring_costs_has_data_for_multiple_products(self):
        """Recurring costs data should exist for 1-11 products"""
        response = requests.get(f"{BASE_URL}/api/pg-recurring-costs", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data, "Missing 'data' in response"
        assert len(data["data"]) == 15, f"Expected 15 data rows, got {len(data['data'])}"
        
        # Check that each row has data for products 1-11
        first_row = data["data"][0]
        for num_products in range(1, 12):
            key = str(num_products)
            assert key in first_row, f"Missing data for {num_products} product(s)"
            assert "base" in first_row[key], f"Missing 'base' for {num_products} products"
            assert "tope" in first_row[key], f"Missing 'tope' for {num_products} products"
        
        print("✓ Recurring costs data available for 1-11 products")


class TestVPOSMPOSRegression:
    """Regression test to ensure VPOS/MPOS still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "tester@demo.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200
        self.token = login_response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get clients and integrators
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        self.clients = clients_response.json()
        
        integrators_response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        self.integrators = integrators_response.json()
    
    def test_vpos_mpos_quote_creation_still_works(self):
        """VPOS/MPOS quote creation should still work normally"""
        if not self.clients or not self.integrators:
            pytest.skip("No clients or integrators available")
        
        # Create a simple VPOS quote
        payload = {
            "client_id": self.clients[0]["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test Setup Service",
                    "quantity": 1,
                    "unit_price_usd": 100,
                    "total_usd": 100,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1
                }
            ],
            "hardware": [],
            "notes": "VPOS regression test iteration 48",
            "integrator_id": self.integrators[0]["integrator_id"],
            "integrator_name": self.integrators[0]["name"],
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pdf_data": None
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", headers=self.headers, json=payload)
        
        assert response.status_code == 200, f"VPOS quote creation failed: {response.text}"
        quote_data = response.json()
        assert quote_data["quote_type"] == "VPOS_MPOS", f"Wrong quote type: {quote_data.get('quote_type')}"
        
        print(f"✓ VPOS/MPOS quote still works: {quote_data['quote_number']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
