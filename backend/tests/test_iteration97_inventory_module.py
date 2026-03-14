"""
Test Iteration 97 - Inventory Module (Módulo de Control de Inventarios Multialmacén)

Tests cover:
1. Warehouse CRUD operations (create, list, update, delete)
2. Entry operations with validation by type (general=quantity only, hardware=serials required)
3. Serial validation (duplicate serial check, quantity=serial count validation)
4. Stock calculation using algebraic formula (entrada+transf_entrada - salida - transf_salida)
5. Exit operations with stock and serial validation
6. Atomic transfers between warehouses
7. Movement history retrieval
8. Excel serial parsing endpoint
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInventoryAuth:
    """Authentication fixture for inventory tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Login and get session token"""
        # Login to get session token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "np_test@test.com",
            "password": "Test1234!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
    def get_headers(self):
        return self.headers


class TestWarehouseCRUD(TestInventoryAuth):
    """Warehouse CRUD tests: create, list, update, delete"""
    
    def test_list_warehouses(self):
        """GET /api/inventory/warehouses - List warehouses"""
        response = requests.get(f"{BASE_URL}/api/inventory/warehouses", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify existing warehouses from seed data
        wh_ids = [w["warehouse_id"] for w in data]
        print(f"Found {len(data)} warehouses: {wh_ids}")
        
    def test_create_warehouse(self):
        """POST /api/inventory/warehouses - Create warehouse"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "name": f"TEST_Almacén_{unique_id}",
            "location": "Ubicación de prueba",
            "notes": "Notas de prueba"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses", json=payload, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "warehouse_id" in data
        assert data["name"] == payload["name"]
        assert data["location"] == payload["location"]
        print(f"Created warehouse: {data['warehouse_id']}")
        # Cleanup - delete this warehouse (it has no movements)
        del_response = requests.delete(f"{BASE_URL}/api/inventory/warehouses/{data['warehouse_id']}", headers=self.headers)
        assert del_response.status_code == 200
        
    def test_update_warehouse(self):
        """PUT /api/inventory/warehouses/{id} - Update warehouse"""
        # First create a warehouse
        unique_id = uuid.uuid4().hex[:6]
        create_payload = {"name": f"TEST_WH_Update_{unique_id}", "location": "Loc1"}
        create_response = requests.post(f"{BASE_URL}/api/inventory/warehouses", json=create_payload, headers=self.headers)
        assert create_response.status_code == 200
        wh_id = create_response.json()["warehouse_id"]
        
        # Update it
        update_payload = {"name": f"TEST_WH_Updated_{unique_id}", "location": "Updated Location"}
        update_response = requests.put(f"{BASE_URL}/api/inventory/warehouses/{wh_id}", json=update_payload, headers=self.headers)
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["name"] == update_payload["name"]
        assert data["location"] == update_payload["location"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/inventory/warehouses/{wh_id}", headers=self.headers)
        
    def test_delete_warehouse_empty(self):
        """DELETE /api/inventory/warehouses/{id} - Delete empty warehouse succeeds"""
        # Create a warehouse
        unique_id = uuid.uuid4().hex[:6]
        create_response = requests.post(f"{BASE_URL}/api/inventory/warehouses", 
            json={"name": f"TEST_WH_Delete_{unique_id}"}, headers=self.headers)
        assert create_response.status_code == 200
        wh_id = create_response.json()["warehouse_id"]
        
        # Delete it (no movements, should succeed)
        delete_response = requests.delete(f"{BASE_URL}/api/inventory/warehouses/{wh_id}", headers=self.headers)
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert "message" in data
        print(f"Deleted warehouse: {wh_id}")
        
    def test_delete_warehouse_with_movements_fails(self):
        """DELETE /api/inventory/warehouses/{id} - Delete warehouse with movements fails"""
        # Use existing warehouse with movements (whs_f00b02f4 has stock)
        response = requests.delete(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4", headers=self.headers)
        assert response.status_code == 400
        data = response.json()
        assert "movimientos" in data.get("detail", "").lower() or "movement" in data.get("detail", "").lower()


class TestInventoryEntries(TestInventoryAuth):
    """Test entry operations with type-based validation"""
    
    def test_entry_general_type_no_serials(self):
        """POST entry for non-serialized type (Base) - quantity only, no serials needed"""
        # hwr_eb4e1ffdf44f is Base (non-serialized)
        payload = {
            "item_id": "hwr_eb4e1ffdf44f",
            "quantity": 5,
            "unit_cost": 10.0,
            "notes": "TEST Entry - General type"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/entry", 
            json=payload, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 5
        assert data["movement_type"] == "entrada"
        assert data["serials"] == []  # Non-serialized shouldn't have serials
        print(f"Entry created: {data['movement_id']}")
        
    def test_entry_hardware_requires_serials(self):
        """POST entry for serialized type (POS) - fails without serials"""
        # hwr_3b365a77248a is POS (serialized type)
        payload = {
            "item_id": "hwr_3b365a77248a",
            "quantity": 2,
            "unit_cost": 100.0,
            "notes": "TEST Entry - Hardware without serials should fail"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/entry", 
            json=payload, headers=self.headers)
        # Should fail because POS requires serials
        assert response.status_code == 400
        data = response.json()
        assert "serial" in data.get("detail", "").lower()
        
    def test_entry_hardware_with_serials_quantity_mismatch(self):
        """POST entry for POS - fails if serial count != quantity"""
        payload = {
            "item_id": "hwr_3b365a77248a",
            "quantity": 3,
            "unit_cost": 100.0,
            "serials": ["TEST_SN_001", "TEST_SN_002"],  # Only 2 serials for qty 3
            "notes": "TEST Entry - Serials count mismatch"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/entry", 
            json=payload, headers=self.headers)
        assert response.status_code == 400
        data = response.json()
        assert "serial" in data.get("detail", "").lower() or "3" in data.get("detail", "")
        
    def test_entry_hardware_with_correct_serials(self):
        """POST entry for POS - succeeds with matching serial count"""
        unique = uuid.uuid4().hex[:6]
        payload = {
            "item_id": "hwr_3b365a77248a",  # POS
            "quantity": 2,
            "unit_cost": 150.0,
            "serials": [f"TEST_SN_{unique}_A", f"TEST_SN_{unique}_B"],
            "notes": "TEST Entry - Correct serials"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/entry", 
            json=payload, headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["serials"]) == 2
        assert data["quantity"] == 2
        print(f"Hardware entry created with serials: {data['serials']}")
        
    def test_entry_duplicate_serial_fails(self):
        """POST entry - fails if serial already exists active in inventory"""
        # SN001 is already in whs_f00b02f4 based on seed data
        payload = {
            "item_id": "hwr_3b365a77248a",  # POS
            "quantity": 1,
            "unit_cost": 100.0,
            "serials": ["SN001"],  # Already exists
            "notes": "TEST Entry - Duplicate serial"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_164dac03/entry", 
            json=payload, headers=self.headers)
        # Should fail because SN001 is already active
        assert response.status_code == 400
        data = response.json()
        assert "SN001" in data.get("detail", "") or "serial" in data.get("detail", "").lower()


class TestStockCalculation(TestInventoryAuth):
    """Test stock calculation with algebraic formula"""
    
    def test_get_warehouse_stock(self):
        """GET /api/inventory/warehouses/{id}/stock - Returns calculated stock"""
        response = requests.get(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/stock", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Each stock item should have key fields
        for item in data:
            assert "item_id" in item
            assert "item_name" in item
            assert "quantity" in item
            assert "avg_cost" in item
            assert "serials" in item
            assert "requires_serial" in item
        print(f"Stock items found: {len(data)}")
        if data:
            print(f"Sample stock item: {data[0]['item_name']} - qty: {data[0]['quantity']}")


class TestInventoryExits(TestInventoryAuth):
    """Test exit operations with stock and serial validation"""
    
    def test_exit_insufficient_stock_fails(self):
        """POST exit - fails if stock insufficient"""
        # Try to exit way more than available
        payload = {
            "item_id": "hwr_3b365a77248a",  # POS
            "quantity": 9999,
            "reference": "TEST_REF",
            "notes": "TEST Exit - Should fail"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/exit", 
            json=payload, headers=self.headers)
        assert response.status_code == 400
        data = response.json()
        assert "stock" in data.get("detail", "").lower() or "insuficiente" in data.get("detail", "").lower()
        
    def test_exit_serialized_without_serials_fails(self):
        """POST exit for serialized type - fails without selecting serials"""
        payload = {
            "item_id": "hwr_3b365a77248a",  # POS (serialized)
            "quantity": 1,
            "serials": [],  # No serials selected
            "reference": "TEST_REF"
        }
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/exit", 
            json=payload, headers=self.headers)
        assert response.status_code == 400


class TestTransfers(TestInventoryAuth):
    """Test atomic transfer operations between warehouses"""
    
    def test_transfer_requires_all_fields(self):
        """POST transfer - fails without required fields"""
        payload = {
            "source_warehouse_id": "whs_f00b02f4"
            # Missing dest_warehouse_id, item_id, quantity
        }
        response = requests.post(f"{BASE_URL}/api/inventory/transfer", 
            json=payload, headers=self.headers)
        assert response.status_code == 400
        
    def test_transfer_same_source_dest_fails(self):
        """POST transfer - fails if source == destination"""
        payload = {
            "source_warehouse_id": "whs_f00b02f4",
            "dest_warehouse_id": "whs_f00b02f4",  # Same as source
            "item_id": "hwr_eb4e1ffdf44f",
            "quantity": 1
        }
        response = requests.post(f"{BASE_URL}/api/inventory/transfer", 
            json=payload, headers=self.headers)
        assert response.status_code == 400
        data = response.json()
        assert "igual" in data.get("detail", "").lower() or "mismo" in data.get("detail", "").lower() or "same" in data.get("detail", "").lower()
        
    def test_transfer_insufficient_stock_fails(self):
        """POST transfer - fails if source stock insufficient"""
        payload = {
            "source_warehouse_id": "whs_f00b02f4",
            "dest_warehouse_id": "whs_164dac03",
            "item_id": "hwr_eb4e1ffdf44f",  # Base (non-serialized)
            "quantity": 99999  # Way more than available
        }
        response = requests.post(f"{BASE_URL}/api/inventory/transfer", 
            json=payload, headers=self.headers)
        assert response.status_code == 400
        data = response.json()
        assert "stock" in data.get("detail", "").lower() or "insuficiente" in data.get("detail", "").lower()


class TestMovementHistory(TestInventoryAuth):
    """Test movement history retrieval"""
    
    def test_get_movements(self):
        """GET /api/inventory/warehouses/{id}/movements - Returns movement history"""
        response = requests.get(f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/movements", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            m = data[0]
            assert "movement_id" in m
            assert "movement_type" in m
            assert "item_name" in m
            assert "quantity" in m
            assert "created_at" in m
            print(f"Found {len(data)} movements, latest: {m['movement_type']} - {m['item_name']}")


class TestParseSerials(TestInventoryAuth):
    """Test Excel serial parsing endpoint"""
    
    def test_parse_serials_endpoint_exists(self):
        """POST /api/inventory/parse-serials - Endpoint accessible"""
        # Just verify endpoint exists and requires a file
        response = requests.post(f"{BASE_URL}/api/inventory/parse-serials", headers=self.headers)
        # Should fail with 422 because no file provided, not 404
        assert response.status_code in [400, 422], f"Unexpected status: {response.status_code}"


class TestEndToEndFlow(TestInventoryAuth):
    """End-to-end flow tests for complete inventory operations"""
    
    def test_full_entry_exit_flow_non_serialized(self):
        """Full flow: Entry -> Check Stock -> Exit -> Verify Stock Reduced"""
        item_id = "hwr_eb4e1ffdf44f"  # Base (non-serialized)
        warehouse_id = "whs_f00b02f4"
        
        # 1. Get initial stock
        initial_stock_resp = requests.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock", headers=self.headers)
        assert initial_stock_resp.status_code == 200
        initial_stock = initial_stock_resp.json()
        initial_qty = next((s["quantity"] for s in initial_stock if s["item_id"] == item_id), 0)
        
        # 2. Create entry
        entry_payload = {
            "item_id": item_id,
            "quantity": 10,
            "unit_cost": 5.0,
            "notes": "TEST Entry for flow test"
        }
        entry_resp = requests.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", 
            json=entry_payload, headers=self.headers)
        assert entry_resp.status_code == 200
        
        # 3. Verify stock increased
        after_entry_stock = requests.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock", headers=self.headers).json()
        after_entry_qty = next((s["quantity"] for s in after_entry_stock if s["item_id"] == item_id), 0)
        assert after_entry_qty == initial_qty + 10, f"Expected {initial_qty + 10}, got {after_entry_qty}"
        
        # 4. Create exit
        exit_payload = {
            "item_id": item_id,
            "quantity": 3,
            "reference": "TEST_EXIT_REF",
            "notes": "TEST Exit for flow test"
        }
        exit_resp = requests.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/exit", 
            json=exit_payload, headers=self.headers)
        assert exit_resp.status_code == 200
        
        # 5. Verify stock decreased
        after_exit_stock = requests.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock", headers=self.headers).json()
        after_exit_qty = next((s["quantity"] for s in after_exit_stock if s["item_id"] == item_id), 0)
        assert after_exit_qty == after_entry_qty - 3, f"Expected {after_entry_qty - 3}, got {after_exit_qty}"
        print(f"Full flow verified: {initial_qty} -> +10 -> {after_entry_qty} -> -3 -> {after_exit_qty}")


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
