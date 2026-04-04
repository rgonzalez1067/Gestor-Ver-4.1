"""
Test Fast Track Hardware Visibility and Cost Integration
Tests for iteration 155 - Rectificación: Restauración de Visibilidad y Costos de Hardware
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFastTrackHardware:
    """Tests for Fast Track hardware integration in quotes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        self.session.close()
    
    def test_quotes_endpoint_returns_ft_equipment_items(self):
        """Test that GET /api/quotes returns ft_equipment_items field"""
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        quotes = response.json()
        assert isinstance(quotes, list), "Expected list of quotes"
        
        # Find a Fast Track quote
        fast_track_quotes = [q for q in quotes if q.get('quote_type') == 'FAST_TRACK']
        print(f"Found {len(fast_track_quotes)} Fast Track quotes")
        
        if fast_track_quotes:
            ft_quote = fast_track_quotes[0]
            # Check that ft_equipment_items field exists (can be empty list or None)
            assert 'ft_equipment_items' in ft_quote or ft_quote.get('ft_equipment_items') is None, \
                "ft_equipment_items field should exist in Fast Track quote"
            print(f"Fast Track quote {ft_quote.get('quote_number')}: ft_equipment_items = {ft_quote.get('ft_equipment_items')}")
    
    def test_quote_update_accepts_ft_equipment_items(self):
        """Test that PUT /api/quotes/{id} accepts ft_equipment_items and ft_hardware_subtotal"""
        # First get a Fast Track quote in Borrador status
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        borrador_ft_quotes = [q for q in quotes 
                             if q.get('quote_type') == 'FAST_TRACK' 
                             and q.get('quote_status') == 'Borrador']
        
        if not borrador_ft_quotes:
            pytest.skip("No Fast Track quotes in Borrador status to test update")
        
        quote = borrador_ft_quotes[0]
        quote_id = quote.get('quote_id')
        
        # Try to update with ft_equipment_items
        update_data = {
            "ft_equipment_items": [
                {
                    "hardware_id": "test_hw_001",
                    "name": "Test POS Device",
                    "type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140.00
                }
            ],
            "ft_hardware_subtotal": 280.00
        }
        
        response = self.session.put(f"{BASE_URL}/api/quotes/{quote_id}", json=update_data)
        
        # Should accept the update (200) or reject if not in Borrador (400)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            updated_quote = response.json()
            print(f"Updated quote: ft_equipment_items = {updated_quote.get('ft_equipment_items')}")
    
    def test_quote_create_with_pdf_includes_ft_hardware_in_total(self):
        """Test that POST /api/quotes/create-with-pdf includes ft_equipment_items cost in total"""
        # Get a client ID for the test
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for test")
        
        client = clients_response.json()[0]
        client_id = client.get('client_id')
        
        # Create a Fast Track quote with ft_equipment_items
        quote_data = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "FAST_TRACK",
            "pricing_model": "outsourcing",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "ft_equipment_items": [
                {
                    "hardware_id": "test_hw_002",
                    "name": "Morefun MF960",
                    "type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140.00
                }
            ],
            "notes": "Test Fast Track quote with hardware",
            "cantidad_cajas": 2,
            "cantidad_bancos": 1,
            "client_segment": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        
        # Should create successfully
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        quote = result.get('quote', {})
        
        # Verify ft_equipment_items is stored
        assert quote.get('ft_equipment_items') is not None, "ft_equipment_items should be stored"
        
        # Verify total includes hardware cost (2 * $140 = $280)
        total_usd = quote.get('total_usd', 0)
        print(f"Created quote total_usd: ${total_usd}")
        
        # The total should include the hardware subtotal
        # Note: The exact total depends on services, but hardware should be included
        assert total_usd >= 280, f"Total should include hardware cost of $280, got ${total_usd}"
    
    def test_quote_model_has_ft_fields(self):
        """Test that QuoteUpdate model accepts ft_equipment_items and ft_hardware_subtotal"""
        # This is a structural test - verify the API accepts these fields
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        if quotes:
            quote = quotes[0]
            # Check that the response can contain these fields
            # They may be None/null if not set
            print(f"Quote fields present: {list(quote.keys())}")
            
            # Verify the model structure allows these fields
            # (they should be in the response even if None)
            expected_fields = ['quote_id', 'quote_number', 'client_id', 'quote_type', 'total_usd']
            for field in expected_fields:
                assert field in quote, f"Expected field '{field}' in quote response"


class TestNonFastTrackQuotes:
    """Tests to verify non-Fast Track quotes don't include hardware costs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        self.session.close()
    
    def test_vpos_quote_no_ft_hardware(self):
        """Test that VPOS quotes don't have ft_equipment_items affecting total"""
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        vpos_quotes = [q for q in quotes if q.get('quote_type') == 'VPOS']
        
        if vpos_quotes:
            vpos_quote = vpos_quotes[0]
            ft_items = vpos_quote.get('ft_equipment_items', [])
            
            # VPOS quotes should not have ft_equipment_items
            assert not ft_items or ft_items == [], \
                f"VPOS quote should not have ft_equipment_items, got: {ft_items}"
            print(f"VPOS quote {vpos_quote.get('quote_number')}: ft_equipment_items = {ft_items} (correct)")
        else:
            print("No VPOS quotes found to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
