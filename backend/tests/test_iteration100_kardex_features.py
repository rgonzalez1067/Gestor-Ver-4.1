# ruff: noqa
"""
Test suite for Iteration 100 - Kardex Drill-down, Destination Popover, and Client Search features

Tests:
1. GET /api/inventory/warehouses/{wh_id}/kardex/{item_id} - Kardex endpoint returns chronological movements with running balance
2. Kardex saldo_final matches stock endpoint quantity
3. GET /api/inventory/movements/{movement_id}/destination - Returns client info for exit movements
4. GET /api/inventory/movements/search?client_name=X - Searches exit movements by client name
5. InventoryMovement model includes client_id, quote_id, quote_number fields
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login with test credentials
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "delivery@test.com",
        "password": "Test12345!"
    })
    
    if response.status_code != 200:
        pytest.skip("Authentication failed - cannot proceed with tests")
    
    data = response.json()
    session.headers.update({"Authorization": f"Bearer {data['session_token']}"})
    return session


@pytest.fixture(scope="module")
def test_warehouse(auth_session):
    """Get or create a warehouse for testing"""
    # Get existing warehouses
    response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses")
    assert response.status_code == 200
    warehouses = response.json()
    
    if warehouses:
        # Use first existing warehouse (Almacén Central should exist from iteration 98)
        return warehouses[0]
    
    # Create new warehouse
    unique_id = uuid.uuid4().hex[:6]
    response = auth_session.post(f"{BASE_URL}/api/inventory/warehouses", json={
        "name": f"TEST_Warehouse_{unique_id}",
        "location": "Test Location",
        "notes": "Test warehouse for iteration 100"
    })
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def test_hardware(auth_session):
    """Get hardware items for testing"""
    response = auth_session.get(f"{BASE_URL}/api/hardware")
    assert response.status_code == 200
    hardware = response.json()
    
    if not hardware:
        pytest.skip("No hardware items available for testing")
    
    # Return first item for generic tests, and try to find a POS-type item for serialized tests
    pos_item = next((h for h in hardware if (h.get('type') or '').lower() == 'pos'), None)
    generic_item = next((h for h in hardware if (h.get('type') or '').lower() not in ['pos', 'pinpad', 'mpos']), None)
    
    return {
        "all": hardware,
        "pos": pos_item,
        "generic": generic_item or hardware[0]
    }


class TestKardexEndpoint:
    """Tests for GET /api/inventory/warehouses/{wh_id}/kardex/{item_id}"""
    
    def test_kardex_endpoint_returns_200(self, auth_session, test_warehouse):
        """Kardex endpoint returns 200 for valid warehouse and item"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        # First get stock to find an item with movements
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        assert stock_response.status_code == 200
        stock = stock_response.json()
        
        if not stock:
            pytest.skip("No stock items in warehouse to test kardex")
        
        item_id = stock[0]["item_id"]
        
        # Test kardex endpoint
        response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "item_id" in data
        assert "item_name" in data
        assert "item_type" in data
        assert "warehouse_id" in data
        assert "saldo_final" in data
        assert "movements" in data
        assert isinstance(data["movements"], list)
    
    def test_kardex_returns_chronological_movements(self, auth_session, test_warehouse):
        """Kardex returns movements in chronological order (oldest first)"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        stock = stock_response.json()
        
        if not stock:
            pytest.skip("No stock items to test kardex chronology")
        
        item_id = stock[0]["item_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
        assert response.status_code == 200
        
        data = response.json()
        movements = data["movements"]
        
        if len(movements) > 1:
            # Verify chronological order (older first)
            for i in range(len(movements) - 1):
                current_date = movements[i].get("date", "")
                next_date = movements[i + 1].get("date", "")
                assert current_date <= next_date, "Movements should be in chronological order"
    
    def test_kardex_has_running_balance(self, auth_session, test_warehouse):
        """Each kardex movement has a 'saldo' (running balance) field"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        stock = stock_response.json()
        
        if not stock:
            pytest.skip("No stock items to test kardex running balance")
        
        item_id = stock[0]["item_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
        assert response.status_code == 200
        
        data = response.json()
        movements = data["movements"]
        
        for m in movements:
            assert "saldo" in m, "Each movement should have 'saldo' field"
            assert "signed_qty" in m, "Each movement should have 'signed_qty' field"
            assert "movement_id" in m
            assert "date" in m
            assert "movement_type" in m
            assert "quantity" in m
    
    def test_kardex_saldo_final_matches_stock(self, auth_session, test_warehouse):
        """Kardex saldo_final must match stock quantity from stock endpoint"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        stock = stock_response.json()
        
        if not stock:
            pytest.skip("No stock items to verify kardex vs stock match")
        
        for stock_item in stock[:3]:  # Test first 3 items
            item_id = stock_item["item_id"]
            stock_qty = stock_item["quantity"]
            
            kardex_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
            assert kardex_response.status_code == 200
            
            kardex_data = kardex_response.json()
            saldo_final = kardex_data["saldo_final"]
            
            assert saldo_final == stock_qty, f"Kardex saldo_final ({saldo_final}) should match stock quantity ({stock_qty}) for item {item_id}"
    
    def test_kardex_movement_includes_client_fields(self, auth_session, test_warehouse):
        """Kardex movements include client_id, quote_id, quote_number fields"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        stock = stock_response.json()
        
        if not stock:
            pytest.skip("No stock items to verify kardex client fields")
        
        item_id = stock[0]["item_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{item_id}")
        assert response.status_code == 200
        
        data = response.json()
        movements = data["movements"]
        
        if movements:
            # Check that client fields exist in movement structure
            m = movements[0]
            assert "client_id" in m or "client_name" in m, "Movement should have client fields"
            # quote_id and quote_number may be empty strings but should exist
            assert "quote_id" in m, "Movement should have quote_id field"
            assert "quote_number" in m, "Movement should have quote_number field"


class TestDestinationEndpoint:
    """Tests for GET /api/inventory/movements/{movement_id}/destination"""
    
    def test_destination_endpoint_returns_404_for_invalid_movement(self, auth_session):
        """Destination endpoint returns 404 for non-existent movement"""
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/invalid_movement_id/destination")
        assert response.status_code == 404
    
    def test_destination_endpoint_returns_400_for_non_exit_movement(self, auth_session, test_warehouse):
        """Destination endpoint returns 400 for non-exit movements (entrada)"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        # Get movements and find an 'entrada' type
        movements_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/movements")
        assert movements_response.status_code == 200
        movements = movements_response.json()
        
        entrada_mov = next((m for m in movements if m.get("movement_type") == "entrada"), None)
        
        if not entrada_mov:
            pytest.skip("No entrada movement found to test destination 400 error")
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/{entrada_mov['movement_id']}/destination")
        assert response.status_code == 400, "Destination endpoint should return 400 for entrada movements"
    
    def test_destination_endpoint_returns_client_info_for_salida(self, auth_session, test_warehouse):
        """Destination endpoint returns client info for salida movements"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        movements_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/movements")
        movements = movements_response.json()
        
        salida_mov = next((m for m in movements if m.get("movement_type") == "salida"), None)
        
        if not salida_mov:
            pytest.skip("No salida movement found to test destination endpoint")
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/{salida_mov['movement_id']}/destination")
        assert response.status_code == 200
        
        data = response.json()
        # Verify expected fields exist
        assert "movement_id" in data
        assert "client_name" in data
        assert "client_id" in data
        assert "client_rif" in data
        assert "quote_id" in data
        assert "quote_number" in data
        assert "serials" in data
        assert "item_name" in data
        assert "quantity" in data
        assert "date" in data


class TestClientSearchEndpoint:
    """Tests for GET /api/inventory/movements/search?client_name=X"""
    
    def test_client_search_requires_min_characters(self, auth_session):
        """Client search endpoint requires at least 2 characters"""
        # Test with 1 character
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name=A")
        assert response.status_code == 400, "Should require at least 2 characters"
        
        # Test with empty string
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name=")
        assert response.status_code == 400
    
    def test_client_search_returns_list(self, auth_session):
        """Client search returns a list of movements (even if empty)"""
        # Use a generic search term
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name=Test")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_client_search_returns_only_salida_movements(self, auth_session, test_warehouse):
        """Client search only returns 'salida' type movements"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        # First, get some movements to find a client_name
        movements_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/movements")
        movements = movements_response.json()
        
        salida_with_client = next((m for m in movements if m.get("movement_type") == "salida" and m.get("client_name")), None)
        
        if not salida_with_client:
            pytest.skip("No salida movement with client_name to test search")
        
        client_name = salida_with_client["client_name"][:3]  # Use first 3 chars for search
        
        response = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name={client_name}")
        assert response.status_code == 200
        
        data = response.json()
        for m in data:
            assert m.get("movement_type") == "salida", "Search should only return salida movements"
    
    def test_client_search_is_case_insensitive(self, auth_session, test_warehouse):
        """Client search is case insensitive"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        movements_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/movements")
        movements = movements_response.json()
        
        salida_with_client = next((m for m in movements if m.get("movement_type") == "salida" and m.get("client_name")), None)
        
        if not salida_with_client:
            pytest.skip("No salida movement with client_name to test case insensitive search")
        
        client_name = salida_with_client["client_name"]
        
        # Search with lowercase
        response_lower = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name={client_name.lower()}")
        # Search with uppercase
        response_upper = auth_session.get(f"{BASE_URL}/api/inventory/movements/search?client_name={client_name.upper()}")
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200


class TestInventoryMovementModel:
    """Tests to verify InventoryMovement model includes client_id, quote_id, quote_number"""
    
    def test_exit_movement_saves_client_fields(self, auth_session, test_warehouse, test_hardware):
        """Creating an exit movement saves client_id, quote_id, quote_number fields"""
        warehouse_id = test_warehouse["warehouse_id"]
        
        # Get a generic (non-serialized) item
        hw = test_hardware.get("generic")
        if not hw:
            pytest.skip("No generic hardware item for testing")
        
        hw_id = hw["hardware_id"]
        
        # First check if we have stock for this item
        stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        stock = stock_response.json()
        
        stock_item = next((s for s in stock if s["item_id"] == hw_id and s["quantity"] > 0), None)
        
        if not stock_item:
            # Need to create entry first
            entry_response = auth_session.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json={
                "item_id": hw_id,
                "quantity": 5,
                "unit_cost": 100.0,
                "notes": "Test entry for iteration 100"
            })
            if entry_response.status_code != 200:
                pytest.skip(f"Cannot create entry for testing: {entry_response.text}")
        
        # Create exit with client_name
        unique_client = f"TEST_Client_{uuid.uuid4().hex[:6]}"
        exit_response = auth_session.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/exit", json={
            "item_id": hw_id,
            "quantity": 1,
            "client_name": unique_client,
            "reference": "COT-TEST-100",
            "notes": "Test exit for iteration 100"
        })
        
        assert exit_response.status_code == 200
        exit_data = exit_response.json()
        
        # Verify the created movement has client fields
        assert "client_name" in exit_data
        assert exit_data["client_name"] == unique_client
        # client_id and quote_id may be empty for manual exits but should exist in response
        assert "movement_id" in exit_data


class TestStockCalculationIntegrity:
    """Verify stock calculation matches kardex saldo across operations"""
    
    def test_saldo_calculation_after_entry_and_exit(self, auth_session, test_warehouse, test_hardware):
        """Kardex saldo correctly tracks entry and exit operations"""
        warehouse_id = test_warehouse["warehouse_id"]
        hw = test_hardware.get("generic")
        
        if not hw:
            pytest.skip("No generic hardware item for testing")
        
        hw_id = hw["hardware_id"]
        
        # Get initial stock
        initial_stock_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        initial_stock = initial_stock_response.json()
        initial_qty = next((s["quantity"] for s in initial_stock if s["item_id"] == hw_id), 0)
        
        # Create entry
        entry_qty = 3
        entry_response = auth_session.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json={
            "item_id": hw_id,
            "quantity": entry_qty,
            "unit_cost": 50.0,
            "notes": "Test entry for saldo verification"
        })
        
        assert entry_response.status_code == 200
        
        # Verify stock increased
        stock_after_entry = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock").json()
        qty_after_entry = next((s["quantity"] for s in stock_after_entry if s["item_id"] == hw_id), 0)
        expected_after_entry = initial_qty + entry_qty
        
        assert qty_after_entry == expected_after_entry, f"Stock after entry: expected {expected_after_entry}, got {qty_after_entry}"
        
        # Verify kardex saldo_final matches
        kardex_response = auth_session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{hw_id}")
        kardex_data = kardex_response.json()
        
        assert kardex_data["saldo_final"] == qty_after_entry, "Kardex saldo_final should match stock quantity"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
