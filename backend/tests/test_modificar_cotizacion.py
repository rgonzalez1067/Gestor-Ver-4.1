"""
Test script for Modificar Cotización functionality (iteration 21)
Testing:
1. Creating a quote with cantidad_cajas and cantidad_bancos values
2. Verifying the quote data is saved correctly
3. Using the duplicate endpoint to create a new version
4. Updating the duplicated quote
5. Verifying the original quote remains intact
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workflow-opt.preview.emergentagent.com')

# Session token from previous test iteration
TEST_SESSION_TOKEN = "P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"


class TestModificarCotizacion:
    """Test cases for Modificar Cotización functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_01_authentication_working(self):
        """Test that authentication with session token works"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=self.headers)
        
        # If session expired, we need to note this
        if response.status_code == 401:
            pytest.skip("Session token expired - manual authentication required")
        
        assert response.status_code == 200, f"Auth failed: {response.text}"
        data = response.json()
        assert "user_id" in data or "email" in data
        print(f"Authenticated as: {data.get('email', data.get('name', 'unknown'))}")
    
    def test_02_list_quotes(self):
        """Test listing quotes to find existing data"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        if response.status_code == 401:
            pytest.skip("Authentication required")
        
        assert response.status_code == 200, f"Failed to list quotes: {response.text}"
        quotes = response.json()
        print(f"Found {len(quotes)} quotes in database")
        
        # Show last 3 quotes
        for quote in quotes[:3]:
            print(f"  - {quote.get('quote_number')}: {quote.get('quote_status')} - cantidad_cajas={quote.get('cantidad_cajas')}, cantidad_bancos={quote.get('cantidad_bancos')}")
    
    def test_03_get_clients_for_quote(self):
        """Get available clients for creating a quote"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        
        if response.status_code == 401:
            pytest.skip("Authentication required")
        
        assert response.status_code == 200, f"Failed to get clients: {response.text}"
        clients = response.json()
        assert len(clients) > 0, "No clients found - need to create test data"
        print(f"Found {len(clients)} clients")
        
        # Store first client for later tests
        self.client_id = clients[0].get('client_id')
        print(f"Using client: {clients[0].get('legal_name')} ({self.client_id})")
    
    def test_04_create_quote_with_cantidad_values(self):
        """Create a new quote with specific cantidad_cajas and cantidad_bancos values"""
        # First get a client
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        if clients_response.status_code == 401:
            pytest.skip("Authentication required")
        
        clients = clients_response.json()
        if not clients:
            pytest.skip("No clients available")
        
        client_id = clients[0].get('client_id')
        
        # Create quote with specific cantidad values
        quote_payload = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "quote_category": "implementation",
            "pricing_model": "conventional",
            "cantidad_cajas": 3,  # Specific test value
            "cantidad_bancos": 2,  # Specific test value
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Suscripción PDV/Banco",
                    "quantity": 6,  # 3 cajas * 2 bancos
                    "unit_price_usd": 5.00,
                    "total_usd": 30.00,
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 2
                },
                {
                    "item_type": "setup",
                    "item_name": "Configuración dispositivo (Pinpad o POS)",
                    "quantity": 3,  # 3 cajas * 1 banco (lockBancos)
                    "unit_price_usd": 5.00,
                    "total_usd": 15.00,
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1
                },
                {
                    "item_type": "recurring_basic",
                    "item_name": "Derecho de uso de plataforma MServer por PDV",
                    "quantity": 3,
                    "unit_price_usd": 8.00,
                    "total_usd": 24.00,
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1
                },
                {
                    "item_type": "recurring_basic",
                    "item_name": "Derecho de uso de plataforma MServer por PDV / Banco",
                    "quantity": 6,
                    "unit_price_usd": 2.00,
                    "total_usd": 12.00,
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 2
                },
                {
                    "item_type": "recurring_other",
                    "item_name": "Comunicación Backend (SSL Público o VPN, APN, etc.)",
                    "quantity": 3,
                    "unit_price_usd": 2.00,
                    "total_usd": 6.00,
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1
                }
            ],
            "hardware": [],
            "notes": "TEST_ITERATION21 - Quote created for Modificar Cotización test"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_payload, headers=self.headers)
        
        assert response.status_code == 200, f"Failed to create quote: {response.text}"
        
        created_quote = response.json()
        print(f"Created quote: {created_quote.get('quote_number')} (ID: {created_quote.get('quote_id')})")
        
        # Verify cantidad values at quote level
        assert created_quote.get('cantidad_cajas') == 3, f"Expected cantidad_cajas=3, got {created_quote.get('cantidad_cajas')}"
        assert created_quote.get('cantidad_bancos') == 2, f"Expected cantidad_bancos=2, got {created_quote.get('cantidad_bancos')}"
        
        # Verify services have cantidad values
        services = created_quote.get('services', [])
        assert len(services) > 0, "No services in created quote"
        
        for service in services:
            assert 'cantidad_cajas' in service, f"Service {service.get('item_name')} missing cantidad_cajas"
            assert 'cantidad_bancos' in service, f"Service {service.get('item_name')} missing cantidad_bancos"
            print(f"  Service: {service.get('item_name')} - cajas={service.get('cantidad_cajas')}, bancos={service.get('cantidad_bancos')}, tarifa={service.get('unit_price_usd')}")
        
        # Store for later tests
        pytest.created_quote_id = created_quote.get('quote_id')
        pytest.created_quote_number = created_quote.get('quote_number')
        
        print(f"✓ Quote {pytest.created_quote_number} created with cantidad_cajas=3, cantidad_bancos=2")
    
    def test_05_verify_quote_data_persisted(self):
        """Verify the created quote data was correctly persisted"""
        if not hasattr(pytest, 'created_quote_id'):
            # Try to get the latest test quote
            response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
            if response.status_code != 200:
                pytest.skip("Cannot retrieve quotes")
            
            quotes = response.json()
            test_quotes = [q for q in quotes if "TEST_ITERATION21" in (q.get('notes') or '')]
            if not test_quotes:
                pytest.skip("No test quote found from previous test")
            
            pytest.created_quote_id = test_quotes[0].get('quote_id')
            pytest.created_quote_number = test_quotes[0].get('quote_number')
        
        # Fetch the specific quote
        response = requests.get(f"{BASE_URL}/api/quotes/{pytest.created_quote_id}", headers=self.headers)
        
        assert response.status_code == 200, f"Failed to get quote: {response.text}"
        
        quote = response.json()
        
        # Verify cantidad values at quote level
        assert quote.get('cantidad_cajas') == 3, f"cantidad_cajas not persisted correctly: {quote.get('cantidad_cajas')}"
        assert quote.get('cantidad_bancos') == 2, f"cantidad_bancos not persisted correctly: {quote.get('cantidad_bancos')}"
        
        # Verify services data
        services = quote.get('services', [])
        setup_items = [s for s in services if s.get('item_type') == 'setup']
        recurring_basic = [s for s in services if s.get('item_type') == 'recurring_basic']
        recurring_other = [s for s in services if s.get('item_type') == 'recurring_other']
        
        print(f"Quote {quote.get('quote_number')} has:")
        print(f"  - cantidad_cajas: {quote.get('cantidad_cajas')}")
        print(f"  - cantidad_bancos: {quote.get('cantidad_bancos')}")
        print(f"  - {len(setup_items)} setup items")
        print(f"  - {len(recurring_basic)} recurring_basic items")
        print(f"  - {len(recurring_other)} recurring_other items")
        
        # Verify services have cantidad_cajas and cantidad_bancos
        for service in services:
            print(f"  Service '{service.get('item_name')}': cajas={service.get('cantidad_cajas')}, bancos={service.get('cantidad_bancos')}, price={service.get('unit_price_usd')}")
            assert service.get('cantidad_cajas') is not None, f"Service {service.get('item_name')} missing cantidad_cajas"
            assert service.get('cantidad_bancos') is not None, f"Service {service.get('item_name')} missing cantidad_bancos"
        
        print("✓ Quote data persisted correctly with cantidad values")
    
    def test_06_duplicate_quote_endpoint(self):
        """Test the duplicate endpoint creates a new version"""
        if not hasattr(pytest, 'created_quote_id'):
            pytest.skip("No quote ID from previous test")
        
        # Call duplicate endpoint
        response = requests.post(
            f"{BASE_URL}/api/quotes/{pytest.created_quote_id}/duplicate",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to duplicate quote: {response.text}"
        
        result = response.json()
        print(f"Duplicate result: {result}")
        
        # Verify response structure
        assert 'new_quote_id' in result, "Response missing new_quote_id"
        assert 'new_quote_number' in result, "Response missing new_quote_number"
        assert 'version' in result, "Response missing version"
        assert 'parent_quote_id' in result, "Response missing parent_quote_id"
        
        # Verify new version is incremented
        assert result['version'] > 1, f"Expected version > 1, got {result['version']}"
        
        # Store duplicated quote info
        pytest.duplicated_quote_id = result['new_quote_id']
        pytest.duplicated_quote_number = result['new_quote_number']
        
        print(f"✓ Created new version: {result['new_quote_number']} (version {result['version']})")
    
    def test_07_verify_duplicate_has_correct_data(self):
        """Verify the duplicated quote has all the correct data including cantidad values"""
        if not hasattr(pytest, 'duplicated_quote_id'):
            pytest.skip("No duplicated quote ID from previous test")
        
        # Fetch the duplicated quote
        response = requests.get(f"{BASE_URL}/api/quotes/{pytest.duplicated_quote_id}", headers=self.headers)
        
        assert response.status_code == 200, f"Failed to get duplicated quote: {response.text}"
        
        quote = response.json()
        
        # Verify quote is in Borrador status
        assert quote.get('quote_status') == 'Borrador', f"Expected status 'Borrador', got '{quote.get('quote_status')}'"
        
        # Verify cantidad values at quote level were copied
        assert quote.get('cantidad_cajas') == 3, f"cantidad_cajas not copied: {quote.get('cantidad_cajas')}"
        assert quote.get('cantidad_bancos') == 2, f"cantidad_bancos not copied: {quote.get('cantidad_bancos')}"
        
        # Verify services were copied with cantidad values
        services = quote.get('services', [])
        assert len(services) > 0, "No services in duplicated quote"
        
        for service in services:
            assert service.get('cantidad_cajas') is not None, f"Service {service.get('item_name')} missing cantidad_cajas"
            assert service.get('cantidad_bancos') is not None, f"Service {service.get('item_name')} missing cantidad_bancos"
            assert service.get('unit_price_usd') is not None, f"Service {service.get('item_name')} missing unit_price_usd"
        
        # Verify parent reference
        assert quote.get('parent_quote_id') == pytest.created_quote_id, "Parent quote ID not set correctly"
        
        print(f"✓ Duplicated quote {quote.get('quote_number')} has correct data:")
        print(f"  - cantidad_cajas: {quote.get('cantidad_cajas')}")
        print(f"  - cantidad_bancos: {quote.get('cantidad_bancos')}")
        print(f"  - status: {quote.get('quote_status')}")
        print(f"  - services: {len(services)}")
        print(f"  - parent_quote_id: {quote.get('parent_quote_id')}")
    
    def test_08_update_duplicated_quote(self):
        """Update the duplicated quote with new values"""
        if not hasattr(pytest, 'duplicated_quote_id'):
            pytest.skip("No duplicated quote ID from previous test")
        
        # Prepare update payload - change cantidad_cajas and update services
        update_payload = {
            "cantidad_cajas": 5,  # Changed from 3 to 5
            "cantidad_bancos": 3,  # Changed from 2 to 3
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Suscripción PDV/Banco",
                    "quantity": 15,  # 5 cajas * 3 bancos
                    "unit_price_usd": 5.00,
                    "total_usd": 75.00,
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 3
                },
                {
                    "item_type": "setup",
                    "item_name": "Configuración dispositivo (Pinpad o POS)",
                    "quantity": 5,  # 5 cajas * 1 banco (lockBancos)
                    "unit_price_usd": 5.00,
                    "total_usd": 25.00,
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1
                },
                {
                    "item_type": "recurring_basic",
                    "item_name": "Derecho de uso de plataforma MServer por PDV",
                    "quantity": 5,
                    "unit_price_usd": 8.00,
                    "total_usd": 40.00,
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1
                }
            ],
            "notes": "TEST_ITERATION21 - Updated quote (modified version)"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/quotes/{pytest.duplicated_quote_id}",
            json=update_payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to update quote: {response.text}"
        
        updated_quote = response.json()
        
        # Verify updated values
        assert updated_quote.get('cantidad_cajas') == 5, f"cantidad_cajas not updated: {updated_quote.get('cantidad_cajas')}"
        assert updated_quote.get('cantidad_bancos') == 3, f"cantidad_bancos not updated: {updated_quote.get('cantidad_bancos')}"
        
        print(f"✓ Updated quote {updated_quote.get('quote_number')}:")
        print(f"  - cantidad_cajas: {updated_quote.get('cantidad_cajas')} (was 3)")
        print(f"  - cantidad_bancos: {updated_quote.get('cantidad_bancos')} (was 2)")
    
    def test_09_verify_original_quote_unchanged(self):
        """Verify the original quote remains unchanged after modification"""
        if not hasattr(pytest, 'created_quote_id'):
            pytest.skip("No original quote ID from previous test")
        
        # Fetch the original quote
        response = requests.get(f"{BASE_URL}/api/quotes/{pytest.created_quote_id}", headers=self.headers)
        
        assert response.status_code == 200, f"Failed to get original quote: {response.text}"
        
        original_quote = response.json()
        
        # Verify original values remain unchanged
        assert original_quote.get('cantidad_cajas') == 3, f"Original cantidad_cajas was modified: {original_quote.get('cantidad_cajas')}"
        assert original_quote.get('cantidad_bancos') == 2, f"Original cantidad_bancos was modified: {original_quote.get('cantidad_bancos')}"
        
        # Verify services remain unchanged
        services = original_quote.get('services', [])
        assert len(services) == 5, f"Original services count changed: {len(services)}"
        
        print(f"✓ Original quote {original_quote.get('quote_number')} unchanged:")
        print(f"  - cantidad_cajas: {original_quote.get('cantidad_cajas')} (expected 3)")
        print(f"  - cantidad_bancos: {original_quote.get('cantidad_bancos')} (expected 2)")
        print(f"  - services count: {len(services)} (expected 5)")
    
    def test_10_verify_two_separate_quotes_exist(self):
        """Verify both original and modified quotes exist as separate records"""
        if not hasattr(pytest, 'created_quote_id') or not hasattr(pytest, 'duplicated_quote_id'):
            pytest.skip("Missing quote IDs from previous tests")
        
        # Fetch both quotes
        original_response = requests.get(f"{BASE_URL}/api/quotes/{pytest.created_quote_id}", headers=self.headers)
        modified_response = requests.get(f"{BASE_URL}/api/quotes/{pytest.duplicated_quote_id}", headers=self.headers)
        
        assert original_response.status_code == 200
        assert modified_response.status_code == 200
        
        original = original_response.json()
        modified = modified_response.json()
        
        # Verify they are different quotes
        assert original.get('quote_id') != modified.get('quote_id'), "Same quote ID - not duplicated correctly"
        assert original.get('quote_number') != modified.get('quote_number'), "Same quote number - not duplicated correctly"
        
        # Verify different values
        assert original.get('cantidad_cajas') != modified.get('cantidad_cajas'), "cantidad_cajas should be different"
        assert original.get('cantidad_bancos') != modified.get('cantidad_bancos'), "cantidad_bancos should be different"
        
        print(f"✓ Two separate quotes exist:")
        print(f"  Original: {original.get('quote_number')} - cajas={original.get('cantidad_cajas')}, bancos={original.get('cantidad_bancos')}")
        print(f"  Modified: {modified.get('quote_number')} - cajas={modified.get('cantidad_cajas')}, bancos={modified.get('cantidad_bancos')}")


class TestQuoteItemsPreserveData:
    """Test that QuoteItem fields are properly preserved through the flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.headers = {
            "Authorization": f"Bearer {TEST_SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_quote_item_cantidad_fields(self):
        """Test that QuoteItem preserves cantidad_cajas and cantidad_bancos"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        
        if response.status_code == 401:
            pytest.skip("Authentication required")
        
        quotes = response.json()
        
        # Find quotes with services
        quotes_with_services = [q for q in quotes if q.get('services')]
        
        if not quotes_with_services:
            pytest.skip("No quotes with services found")
        
        # Check latest quote with services
        quote = quotes_with_services[0]
        services = quote.get('services', [])
        
        print(f"Checking quote {quote.get('quote_number')} services:")
        
        items_with_cantidad = 0
        items_without_cantidad = 0
        
        for service in services:
            if service.get('cantidad_cajas') is not None and service.get('cantidad_bancos') is not None:
                items_with_cantidad += 1
                print(f"  ✓ {service.get('item_name')}: cajas={service.get('cantidad_cajas')}, bancos={service.get('cantidad_bancos')}")
            else:
                items_without_cantidad += 1
                print(f"  ✗ {service.get('item_name')}: MISSING cantidad values")
        
        print(f"\nSummary: {items_with_cantidad} items have cantidad values, {items_without_cantidad} missing")
        
        # For newer quotes, all items should have cantidad values
        if "TEST_ITERATION21" in (quote.get('notes') or ''):
            assert items_without_cantidad == 0, f"Some items missing cantidad values in test quote"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
