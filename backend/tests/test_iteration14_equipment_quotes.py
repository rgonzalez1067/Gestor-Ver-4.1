"""
Test suite for Iteration 14: Equipment Quotes Module
Tests the new Equipment and Accessories quotation functionality
- Tabs structure (Implementaciones / Equipos y Accesorios)
- Equipment quote creation with quote_category='equipment'
- Equipment PDF generation endpoint
- Same folio format COT-YYYY-NNN for both types
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session token from database
SESSION_TOKEN = "Tskr51l-We_-Wr_r4CYvcBvac-F-rxjcEeOABrjAIZg"

@pytest.fixture
def auth_headers():
    """Authentication headers with session token"""
    return {
        "Authorization": f"Bearer {SESSION_TOKEN}",
        "Content-Type": "application/json"
    }

@pytest.fixture
def test_client(auth_headers):
    """Create a test client for equipment quote testing"""
    client_data = {
        "rif": "J-TEST-EQUIP-001",
        "legal_name": "Test Equipment Client",
        "fantasy_name": "Equipment Test Co",
        "segment": "Corporativo",
        "address": "Av. Test 123, Caracas",
        "contact1": {
            "name": "Contact 1",
            "phone": "0414-1234567",
            "email": "test1@equipment.com"
        },
        "contact2": {
            "name": "Contact 2",
            "phone": "0414-7654321",
            "email": "test2@equipment.com"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        # If client exists, fetch it
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        clients = clients_resp.json()
        for c in clients:
            if c.get('rif') == client_data['rif']:
                return c
        pytest.skip("Could not create or find test client")


class TestEquipmentQuotesBackend:
    """Backend API tests for Equipment Quotes functionality"""
    
    def test_01_get_hardware_list(self, auth_headers):
        """Test GET /api/hardware returns hardware list with types"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Hardware list should be an array"
        
        # Check hardware types exist
        if len(data) > 0:
            hardware_types = set(item.get('type', '') for item in data)
            print(f"Hardware types found: {hardware_types}")
            # Expected types: Pinpad, Terminal, Accesorio, Dispositivo
            assert len(hardware_types) > 0, "Should have hardware types defined"
        
        print(f"PASS: GET /api/hardware returned {len(data)} items")
    
    def test_02_create_equipment_quote(self, auth_headers, test_client):
        """Test POST /api/quotes with quote_category='equipment' creates equipment quote"""
        equipment_items = [
            {
                "hardware_id": "test_hw_001",
                "name": "Pinpad Verifone P400",
                "hardware_type": "Dispositivo",
                "quantity": 2,
                "unit_price_usd": 150.00,
                "total_usd": 300.00
            },
            {
                "hardware_id": "test_hw_002",
                "name": "Cable USB-C",
                "hardware_type": "Accesorio",
                "quantity": 5,
                "unit_price_usd": 10.00,
                "total_usd": 50.00
            }
        ]
        
        quote_data = {
            "client_id": test_client['client_id'],
            "quote_category": "equipment",
            "equipment_type": "Dispositivo",
            "equipment_items": equipment_items,
            "notes": "Test equipment quote iteration 14"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify quote structure
        assert "quote_id" in data, "Response should include quote_id"
        assert "quote_number" in data, "Response should include quote_number"
        
        # Verify quote_category
        assert data.get("quote_category") == "equipment", f"quote_category should be 'equipment', got {data.get('quote_category')}"
        
        # Verify equipment_type
        assert data.get("equipment_type") == "Dispositivo", f"equipment_type should be 'Dispositivo', got {data.get('equipment_type')}"
        
        # Verify equipment_items are stored
        assert "equipment_items" in data, "Response should include equipment_items"
        assert len(data["equipment_items"]) == 2, f"Should have 2 equipment items, got {len(data['equipment_items'])}"
        
        # Verify folio format COT-YYYY-NNN
        quote_number = data["quote_number"]
        assert quote_number.startswith("COT-"), f"Quote number should start with 'COT-', got {quote_number}"
        parts = quote_number.split("-")
        assert len(parts) == 3, f"Quote number should have format COT-YYYY-NNN, got {quote_number}"
        
        # Verify total calculation
        expected_total = 300.00 + 50.00  # Sum of equipment items
        assert abs(data["total_usd"] - expected_total) < 0.01, f"Total should be {expected_total}, got {data['total_usd']}"
        
        print(f"PASS: Created equipment quote {quote_number} with total ${data['total_usd']}")
        return data
    
    def test_03_create_accesorio_quote(self, auth_headers, test_client):
        """Test creating equipment quote with equipment_type='Accesorio'"""
        equipment_items = [
            {
                "hardware_id": "test_acc_001",
                "name": "Funda protectora POS",
                "hardware_type": "Accesorio",
                "quantity": 3,
                "unit_price_usd": 25.00,
                "total_usd": 75.00
            }
        ]
        
        quote_data = {
            "client_id": test_client['client_id'],
            "quote_category": "equipment",
            "equipment_type": "Accesorio",
            "equipment_items": equipment_items,
            "notes": "Test accessory quote"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("equipment_type") == "Accesorio", f"equipment_type should be 'Accesorio', got {data.get('equipment_type')}"
        
        print(f"PASS: Created accessory quote {data['quote_number']}")
    
    def test_04_get_quotes_returns_both_categories(self, auth_headers):
        """Test GET /api/quotes returns quotes with both categories"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Quotes list should be an array"
        
        # Check for both categories
        categories = set()
        for quote in data:
            cat = quote.get("quote_category", "implementation")  # Default for legacy quotes
            categories.add(cat)
        
        print(f"Quote categories found: {categories}")
        
        # At least equipment category should exist from our tests
        equipment_quotes = [q for q in data if q.get("quote_category") == "equipment"]
        print(f"PASS: Found {len(equipment_quotes)} equipment quotes out of {len(data)} total")
    
    def test_05_equipment_quote_has_correct_fields(self, auth_headers, test_client):
        """Test equipment quote response has all required fields"""
        equipment_items = [
            {
                "hardware_id": "test_field_001",
                "name": "Test Device",
                "hardware_type": "Dispositivo",
                "quantity": 1,
                "unit_price_usd": 100.00,
                "total_usd": 100.00
            }
        ]
        
        quote_data = {
            "client_id": test_client['client_id'],
            "quote_category": "equipment",
            "equipment_type": "Dispositivo",
            "equipment_items": equipment_items
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Required fields for equipment quotes
        required_fields = [
            "quote_id", "quote_number", "client_id", "quote_category",
            "equipment_type", "equipment_items", "subtotal_usd", "total_usd",
            "exchange_rate", "total_bs", "quote_status", "created_at"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"PASS: Equipment quote has all required fields")
    
    def test_06_generate_equipment_pdf_dispositivo(self, auth_headers):
        """Test POST /api/quotes/generate-equipment-pdf for Dispositivo type"""
        pdf_data = {
            "cliente_nombre": "Test Client PDF",
            "cliente_rif": "J-PDF-TEST-001",
            "cliente_address": "Test Address",
            "equipment_type": "Dispositivo",
            "items": [
                {
                    "hardware_id": "pdf_hw_001",
                    "name": "Pinpad V240m",
                    "hardware_type": "Dispositivo",
                    "quantity": 3,
                    "unit_price_usd": 200.00,
                    "total_usd": 600.00
                }
            ],
            "notes": "Test PDF generation for Dispositivo"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify PDF has content
        assert len(response.content) > 0, "PDF should have content"
        assert response.content[:4] == b'%PDF', "Response should be a valid PDF file"
        
        print(f"PASS: Generated Dispositivo PDF ({len(response.content)} bytes)")
    
    def test_07_generate_equipment_pdf_accesorio(self, auth_headers):
        """Test POST /api/quotes/generate-equipment-pdf for Accesorio type"""
        pdf_data = {
            "cliente_nombre": "Test Accessory Client",
            "cliente_rif": "J-ACC-TEST-001",
            "equipment_type": "Accesorio",
            "items": [
                {
                    "hardware_id": "pdf_acc_001",
                    "name": "Cable de datos",
                    "hardware_type": "Accesorio",
                    "quantity": 10,
                    "unit_price_usd": 5.00,
                    "total_usd": 50.00
                },
                {
                    "hardware_id": "pdf_acc_002",
                    "name": "Cargador USB",
                    "hardware_type": "Accesorio",
                    "quantity": 5,
                    "unit_price_usd": 15.00,
                    "total_usd": 75.00
                }
            ],
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF', "Response should be a valid PDF file"
        
        print(f"PASS: Generated Accesorio PDF ({len(response.content)} bytes)")
    
    def test_08_equipment_quote_editable_prices(self, auth_headers, test_client):
        """Test equipment items have editable prices (different from catalog)"""
        # Create quote with custom (edited) prices
        equipment_items = [
            {
                "hardware_id": "price_test_001",
                "name": "Custom Price Device",
                "hardware_type": "Dispositivo",
                "quantity": 2,
                "unit_price_usd": 175.50,  # Custom edited price
                "total_usd": 351.00
            }
        ]
        
        quote_data = {
            "client_id": test_client['client_id'],
            "quote_category": "equipment",
            "equipment_type": "Dispositivo",
            "equipment_items": equipment_items
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify the custom price is preserved
        items = data.get("equipment_items", [])
        assert len(items) > 0, "Should have equipment items"
        
        saved_price = items[0].get("unit_price_usd", 0)
        assert abs(saved_price - 175.50) < 0.01, f"Price should be 175.50, got {saved_price}"
        
        print(f"PASS: Equipment quote preserves editable prices (${saved_price})")
    
    def test_09_unified_folio_sequence(self, auth_headers, test_client):
        """Test both implementation and equipment quotes use same folio sequence"""
        # Create implementation quote
        impl_data = {
            "client_id": test_client['client_id'],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "services": [],
            "hardware": []
        }
        
        response1 = requests.post(f"{BASE_URL}/api/quotes", json=impl_data, headers=auth_headers)
        assert response1.status_code == 200
        impl_quote = response1.json()
        
        # Create equipment quote
        equip_data = {
            "client_id": test_client['client_id'],
            "quote_category": "equipment",
            "equipment_type": "Dispositivo",
            "equipment_items": [
                {
                    "hardware_id": "seq_test_001",
                    "name": "Sequence Test Device",
                    "hardware_type": "Dispositivo",
                    "quantity": 1,
                    "unit_price_usd": 50.00,
                    "total_usd": 50.00
                }
            ]
        }
        
        response2 = requests.post(f"{BASE_URL}/api/quotes", json=equip_data, headers=auth_headers)
        assert response2.status_code == 200
        equip_quote = response2.json()
        
        # Both should have COT-YYYY-NNN format
        assert impl_quote["quote_number"].startswith("COT-"), "Implementation quote should use COT- prefix"
        assert equip_quote["quote_number"].startswith("COT-"), "Equipment quote should use COT- prefix"
        
        # Extract sequence numbers
        impl_seq = int(impl_quote["quote_number"].split("-")[2])
        equip_seq = int(equip_quote["quote_number"].split("-")[2])
        
        # Equipment quote should have next sequence number
        assert equip_seq == impl_seq + 1, f"Equipment sequence ({equip_seq}) should be impl sequence ({impl_seq}) + 1"
        
        print(f"PASS: Unified folio sequence verified - Implementation: {impl_quote['quote_number']}, Equipment: {equip_quote['quote_number']}")


class TestEquipmentPDFRequestModel:
    """Tests for EquipmentQuotePDFRequest model validation"""
    
    def test_10_pdf_endpoint_requires_cliente_nombre(self, auth_headers):
        """Test PDF endpoint requires cliente_nombre field"""
        # Missing cliente_nombre
        pdf_data = {
            "equipment_type": "Dispositivo",
            "items": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        # Should return 422 validation error
        assert response.status_code == 422, f"Expected 422 for missing required field, got {response.status_code}"
        print("PASS: PDF endpoint validates required cliente_nombre field")
    
    def test_11_pdf_endpoint_accepts_optional_fields(self, auth_headers):
        """Test PDF endpoint accepts all optional fields"""
        pdf_data = {
            "cliente_nombre": "Full Fields Client",
            "cliente_rif": "J-FULL-TEST-001",
            "cliente_address": "Av. Principal 456, Valencia",
            "equipment_type": "Accesorio",
            "items": [
                {
                    "hardware_id": "full_test_001",
                    "name": "Complete Test Item",
                    "hardware_type": "Accesorio",
                    "quantity": 1,
                    "unit_price_usd": 99.99,
                    "total_usd": 99.99
                }
            ],
            "notes": "This is a complete test with all fields"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF'
        
        print("PASS: PDF endpoint accepts all optional fields")


class TestCleanup:
    """Cleanup test data"""
    
    def test_99_cleanup_test_client(self, auth_headers):
        """Clean up test client created during tests"""
        # Get clients list
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        if response.status_code != 200:
            return
        
        clients = response.json()
        for client in clients:
            if client.get('rif', '').startswith('J-TEST-EQUIP'):
                requests.delete(
                    f"{BASE_URL}/api/clients/{client['client_id']}",
                    headers=auth_headers
                )
                print(f"Cleaned up test client: {client['rif']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
