"""
Iteration 54: Race Condition Fix Tests

Tests the fix for the race condition that caused setup items to reset
when editing a quote. The bug was in the useEffect that propagated
header Cajas/Bancos values to items - it ran when isLoadingEdit changed,
overwriting saved per-item values.

Key fixes tested:
1. QuoteItem model includes lockBancos, autoBancos, bancosOverride, totalOverride, isAutoLinked
2. These metadata fields are persisted when creating/updating quotes
3. GET /api/quotes returns all metadata for correct UI restoration
4. descuento_setup and descuento_recurrente are persisted
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@admin.com"
TEST_PASSWORD = "testadmin123"

# Test quote ID created with specific data
TEST_QUOTE_ID = "quo_3264aef5eeb5"


class TestRaceConditionFix:
    """Tests for the race condition fix in quote editing"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for all tests"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_quote_item_model_has_metadata_fields(self):
        """Test that QuoteItem model includes all metadata fields"""
        # Get the test quote
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get quote: {response.text}"
        
        quote = response.json()
        services = quote.get("services", [])
        assert len(services) > 0, "Quote should have services"
        
        # Check that the first service has metadata fields
        first_service = services[0]
        expected_fields = ["lockBancos", "autoBancos", "bancosOverride", "totalOverride", "isAutoLinked"]
        
        for field in expected_fields:
            assert field in first_service, f"Service should have field '{field}'"
        
        print(f"✓ QuoteItem has all metadata fields: {expected_fields}")
    
    def test_setup_items_have_correct_lockBancos_values(self):
        """Test that setup items have correct lockBancos values"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        quote = response.json()
        setup_items = [s for s in quote["services"] if s["item_type"] == "setup"]
        
        # Check Suscripción PDV/Banco - should have lockBancos=false
        suscripcion = next((s for s in setup_items if "Suscripción PDV/Banco" in s["item_name"]), None)
        assert suscripcion is not None, "Should find 'Suscripción PDV/Banco' item"
        assert suscripcion["lockBancos"] == False, "Suscripción PDV/Banco should have lockBancos=false"
        print(f"✓ 'Suscripción PDV/Banco' has lockBancos=false")
        
        # Check Configuración Medio de Pago - should have autoBancos=true
        config_mp = next((s for s in setup_items if "Configuración Medio de Pago" in s["item_name"]), None)
        if config_mp:
            assert config_mp["autoBancos"] == True, "Configuración Medio de Pago should have autoBancos=true"
            print(f"✓ 'Configuración Medio de Pago' has autoBancos=true")
    
    def test_recurring_items_have_correct_lockBancos_values(self):
        """Test that recurring items have correct lockBancos values for N/A behavior"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        quote = response.json()
        recurring_items = [s for s in quote["services"] if s["item_type"] == "recurring_basic"]
        
        # 'Derecho de uso de plataforma MServer por PDV' (without / Banco) should have lockBancos=true
        derecho_pdv = next((s for s in recurring_items 
                           if "Derecho de uso de plataforma MServer por PDV" in s["item_name"] 
                           and "/ Banco" not in s["item_name"]), None)
        if derecho_pdv:
            assert derecho_pdv["lockBancos"] == True, \
                "'Derecho de uso... por PDV' should have lockBancos=true (shows N/A in UI)"
            print(f"✓ 'Derecho de uso de plataforma MServer por PDV' has lockBancos=true (N/A in UI)")
        
        # 'Derecho de uso de plataforma MServer por PDV / Banco' should have lockBancos=false
        derecho_banco = next((s for s in recurring_items 
                             if "Derecho de uso de plataforma MServer por PDV / Banco" in s["item_name"]), None)
        if derecho_banco:
            assert derecho_banco["lockBancos"] == False, \
                "'Derecho de uso... por PDV / Banco' should have lockBancos=false (editable Bancos)"
            print(f"✓ 'Derecho de uso de plataforma MServer por PDV / Banco' has lockBancos=false (editable)")
    
    def test_quote_has_correct_cajas_value(self):
        """Test that quote preserves cantidad_cajas at header level"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["cantidad_cajas"] == 15, f"Quote should have cantidad_cajas=15, got {quote['cantidad_cajas']}"
        assert quote["cantidad_bancos"] == 2, f"Quote should have cantidad_bancos=2, got {quote['cantidad_bancos']}"
        print(f"✓ Quote header has cantidad_cajas=15, cantidad_bancos=2")
    
    def test_quote_has_correct_descuento_values(self):
        """Test that quote preserves descuento_setup and descuento_recurrente"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        quote = response.json()
        assert quote["descuento_setup"] == 10.0, \
            f"Quote should have descuento_setup=10, got {quote['descuento_setup']}"
        assert quote["descuento_recurrente"] == 5.0, \
            f"Quote should have descuento_recurrente=5, got {quote['descuento_recurrente']}"
        print(f"✓ Quote has descuento_setup=10%, descuento_recurrente=5%")
    
    def test_setup_items_preserve_cantidad_cajas(self):
        """Test that each setup item preserves its cantidad_cajas value"""
        response = requests.get(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        quote = response.json()
        setup_items = [s for s in quote["services"] if s["item_type"] == "setup"]
        
        for item in setup_items:
            assert item["cantidad_cajas"] == 15, \
                f"Item '{item['item_name']}' should have cantidad_cajas=15, got {item['cantidad_cajas']}"
        
        print(f"✓ All {len(setup_items)} setup items have cantidad_cajas=15")
    
    def test_create_quote_persists_metadata(self):
        """Test that creating a new quote persists lockBancos and autoBancos metadata"""
        # First get a client ID
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        assert len(clients) > 0, "Need at least one client for test"
        client_id = clients[0]["client_id"]
        
        # Get an integrator
        integrators_resp = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert integrators_resp.status_code == 200
        integrators = integrators_resp.json()
        integrator_id = integrators[0]["integrator_id"] if integrators else None
        
        # Create a quote with metadata
        payload = {
            "client_id": client_id,
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 10,
            "cantidad_bancos": 3,
            "integrator_id": integrator_id,
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "TEST_Metadata_Item",
                    "quantity": 30,
                    "unit_price_usd": 5.0,
                    "total_usd": 150.0,
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 3,
                    "lockBancos": True,
                    "autoBancos": False,
                    "bancosOverride": None,
                    "totalOverride": None
                }
            ],
            "hardware": [],
            "descuento_setup": 15.0,
            "descuento_recurrente": 8.0,
            "pdf_data": None
        }
        
        create_resp = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        assert create_resp.status_code == 200, f"Failed to create quote: {create_resp.text}"
        
        create_data = create_resp.json()
        # Response can be wrapped in "quote" key or be the quote directly
        created_quote = create_data.get("quote", create_data)
        quote_id = created_quote["quote_id"]
        
        # Verify the metadata was persisted by fetching the quote
        get_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        assert get_resp.status_code == 200
        
        quote = get_resp.json()
        assert quote["descuento_setup"] == 15.0, "descuento_setup should be persisted"
        assert quote["descuento_recurrente"] == 8.0, "descuento_recurrente should be persisted"
        
        # Find our test item
        test_item = next((s for s in quote["services"] if "TEST_Metadata_Item" in s["item_name"]), None)
        assert test_item is not None, "Should find the test item"
        assert test_item["lockBancos"] == True, "lockBancos should be persisted as True"
        assert test_item["autoBancos"] == False, "autoBancos should be persisted as False"
        
        print(f"✓ Created quote {quote_id} with persisted metadata")
        
        # Cleanup - delete the test quote
        delete_resp = requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        print(f"✓ Cleaned up test quote {quote_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
