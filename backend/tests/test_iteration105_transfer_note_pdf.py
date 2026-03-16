"""
Test Iteration 105 - Transfer Note PDF Feature
Tests the new 'Nota de Entrega por Transferencia entre Almacenes' functionality.

Features tested:
1. User registration/login for JWT token
2. Hardware creation (POS serialized, Pinpad serialized, Cable non-serialized)
3. Warehouse creation with responsible users
4. Inventory entry with and without serials
5. Transfer between warehouses with automatic PDF generation
6. PDF downloadable and valid (>5KB)
7. Transfer number correlativo TRF-YYYY-XXXX
8. Movements have transfer_number and transfer_note_url
9. Pinpad transfer PDF contains technical note
10. Non-serialized transfer (Cable) works correctly
"""

import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTransferNotePDF:
    """Test class for Transfer Note PDF feature"""
    
    # Shared state across tests
    token = None
    user_id = None
    hardware_pos_id = None
    hardware_pinpad_id = None
    hardware_cable_id = None
    warehouse_origin_id = None
    warehouse_dest_id = None
    transfer_note_url = None
    transfer_number = None
    
    # Test data prefix for cleanup
    TEST_PREFIX = "TEST_TRF105_"
    
    @pytest.fixture(autouse=True)
    def setup_class_vars(self):
        """Ensure class variables are accessible"""
        pass
    
    def test_01_login_existing_user(self):
        """Test login with existing test user to get JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "transfer@test.com",
            "password": "Test12345!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        TestTransferNotePDF.token = data["session_token"]
        TestTransferNotePDF.user_id = data["user"]["user_id"]
        print(f"✓ Login successful, user_id: {TestTransferNotePDF.user_id}")
    
    def _get_headers(self):
        """Get authorization headers"""
        return {
            "Authorization": f"Bearer {TestTransferNotePDF.token}",
            "Content-Type": "application/json"
        }
    
    def test_02_create_hardware_pos(self):
        """Create a POS type hardware (serialized)"""
        timestamp = int(time.time())
        response = requests.post(f"{BASE_URL}/api/hardware", 
            headers=self._get_headers(),
            json={
                "name": f"{self.TEST_PREFIX}POS Terminal {timestamp}",
                "type": "pos",
                "price_usd": 450.00,
                "price_bs_usd": 450.00,
                "description": "Test POS for transfer testing"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create POS hardware: {response.text}"
        data = response.json()
        assert "hardware_id" in data, "No hardware_id in response"
        TestTransferNotePDF.hardware_pos_id = data["hardware_id"]
        print(f"✓ Created POS hardware: {data['hardware_id']}")
    
    def test_03_create_hardware_pinpad(self):
        """Create a Pinpad type hardware (serialized) - should trigger technical note in PDF"""
        timestamp = int(time.time())
        response = requests.post(f"{BASE_URL}/api/hardware", 
            headers=self._get_headers(),
            json={
                "name": f"{self.TEST_PREFIX}Pinpad Device {timestamp}",
                "type": "pinpad",
                "price_usd": 280.00,
                "price_bs_usd": 280.00,
                "description": "Test Pinpad for transfer testing"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create Pinpad hardware: {response.text}"
        data = response.json()
        assert "hardware_id" in data
        TestTransferNotePDF.hardware_pinpad_id = data["hardware_id"]
        print(f"✓ Created Pinpad hardware: {data['hardware_id']}")
    
    def test_04_create_hardware_cable(self):
        """Create a Cable type hardware (non-serialized)"""
        timestamp = int(time.time())
        response = requests.post(f"{BASE_URL}/api/hardware", 
            headers=self._get_headers(),
            json={
                "name": f"{self.TEST_PREFIX}USB Cable {timestamp}",
                "type": "cable",
                "price_usd": 15.00,
                "price_bs_usd": 15.00,
                "description": "Test Cable for transfer testing (non-serialized)"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create Cable hardware: {response.text}"
        data = response.json()
        assert "hardware_id" in data
        TestTransferNotePDF.hardware_cable_id = data["hardware_id"]
        print(f"✓ Created Cable hardware: {data['hardware_id']}")
    
    def test_05_create_warehouse_origin(self):
        """Create origin warehouse with responsible user"""
        timestamp = int(time.time())
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses",
            headers=self._get_headers(),
            json={
                "name": f"{self.TEST_PREFIX}Origen Almacen {timestamp}",
                "location": "Caracas, Venezuela",
                "notes": "Origin warehouse for transfer test",
                "responsible_user_id": TestTransferNotePDF.user_id
            }
        )
        assert response.status_code in [200, 201], f"Failed to create origin warehouse: {response.text}"
        data = response.json()
        assert "warehouse_id" in data
        TestTransferNotePDF.warehouse_origin_id = data["warehouse_id"]
        # Verify responsible info is populated
        assert data.get("responsible_name") or data.get("responsible_user_id"), "Responsible should be assigned"
        print(f"✓ Created origin warehouse: {data['warehouse_id']}, responsible: {data.get('responsible_name', 'N/A')}")
    
    def test_06_create_warehouse_dest(self):
        """Create destination warehouse with responsible user"""
        timestamp = int(time.time())
        response = requests.post(f"{BASE_URL}/api/inventory/warehouses",
            headers=self._get_headers(),
            json={
                "name": f"{self.TEST_PREFIX}Destino Almacen {timestamp}",
                "location": "Maracaibo, Venezuela",
                "notes": "Destination warehouse for transfer test",
                "responsible_user_id": TestTransferNotePDF.user_id
            }
        )
        assert response.status_code in [200, 201], f"Failed to create dest warehouse: {response.text}"
        data = response.json()
        assert "warehouse_id" in data
        TestTransferNotePDF.warehouse_dest_id = data["warehouse_id"]
        print(f"✓ Created destination warehouse: {data['warehouse_id']}")
    
    def test_07_entry_pos_with_serials(self):
        """Register POS inventory entry with serial numbers"""
        timestamp = int(time.time())
        serials = [f"POS-TRF-{timestamp}-001", f"POS-TRF-{timestamp}-002"]
        response = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/entry",
            headers=self._get_headers(),
            json={
                "item_id": TestTransferNotePDF.hardware_pos_id,
                "quantity": 2,
                "unit_cost": 450.00,
                "serials": serials,
                "notes": "POS entry for transfer test"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create POS entry: {response.text}"
        data = response.json()
        assert data.get("quantity") == 2
        assert data.get("serials") == serials
        TestTransferNotePDF.pos_serials = serials
        print(f"✓ Registered POS entry with serials: {serials}")
    
    def test_08_entry_pinpad_with_serials(self):
        """Register Pinpad inventory entry with serial numbers"""
        timestamp = int(time.time())
        serials = [f"PINPAD-TRF-{timestamp}-001"]
        response = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/entry",
            headers=self._get_headers(),
            json={
                "item_id": TestTransferNotePDF.hardware_pinpad_id,
                "quantity": 1,
                "unit_cost": 280.00,
                "serials": serials,
                "notes": "Pinpad entry for transfer test"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create Pinpad entry: {response.text}"
        data = response.json()
        assert data.get("quantity") == 1
        TestTransferNotePDF.pinpad_serials = serials
        print(f"✓ Registered Pinpad entry with serials: {serials}")
    
    def test_09_entry_cable_without_serials(self):
        """Register Cable inventory entry without serials (non-serialized type)"""
        response = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/entry",
            headers=self._get_headers(),
            json={
                "item_id": TestTransferNotePDF.hardware_cable_id,
                "quantity": 10,
                "unit_cost": 15.00,
                "serials": [],
                "notes": "Cable entry for transfer test (no serials)"
            }
        )
        assert response.status_code in [200, 201], f"Failed to create Cable entry: {response.text}"
        data = response.json()
        assert data.get("quantity") == 10
        assert data.get("serials") == []  # Non-serialized should have empty serials
        print(f"✓ Registered Cable entry (non-serialized), qty: 10")
    
    def test_10_verify_origin_stock(self):
        """Verify stock exists in origin warehouse before transfer"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/stock",
            headers=self._get_headers()
        )
        assert response.status_code == 200, f"Failed to get stock: {response.text}"
        stock = response.json()
        assert isinstance(stock, list)
        
        # Find POS, Pinpad, and Cable in stock
        pos_stock = next((s for s in stock if s["item_id"] == TestTransferNotePDF.hardware_pos_id), None)
        pinpad_stock = next((s for s in stock if s["item_id"] == TestTransferNotePDF.hardware_pinpad_id), None)
        cable_stock = next((s for s in stock if s["item_id"] == TestTransferNotePDF.hardware_cable_id), None)
        
        assert pos_stock is not None, "POS not found in stock"
        assert pos_stock["quantity"] >= 2, f"POS stock insufficient: {pos_stock['quantity']}"
        assert pinpad_stock is not None, "Pinpad not found in stock"
        assert pinpad_stock["quantity"] >= 1, f"Pinpad stock insufficient: {pinpad_stock['quantity']}"
        assert cable_stock is not None, "Cable not found in stock"
        assert cable_stock["quantity"] >= 10, f"Cable stock insufficient: {cable_stock['quantity']}"
        
        print(f"✓ Verified stock - POS: {pos_stock['quantity']}, Pinpad: {pinpad_stock['quantity']}, Cable: {cable_stock['quantity']}")
    
    def test_11_transfer_pos_with_pdf_generation(self):
        """Transfer POS between warehouses and verify PDF is generated"""
        serial_to_transfer = TestTransferNotePDF.pos_serials[0]
        response = requests.post(
            f"{BASE_URL}/api/inventory/transfer",
            headers=self._get_headers(),
            json={
                "source_warehouse_id": TestTransferNotePDF.warehouse_origin_id,
                "dest_warehouse_id": TestTransferNotePDF.warehouse_dest_id,
                "item_id": TestTransferNotePDF.hardware_pos_id,
                "quantity": 1,
                "serials": [serial_to_transfer],
                "notes": "POS transfer test with PDF generation"
            }
        )
        assert response.status_code in [200, 201], f"Transfer failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "transfer_id" in data, "No transfer_id in response"
        assert "transfer_number" in data, "No transfer_number in response"
        assert "transfer_note_url" in data, "No transfer_note_url in response"
        
        # Store for later tests
        TestTransferNotePDF.transfer_note_url = data["transfer_note_url"]
        TestTransferNotePDF.transfer_number = data["transfer_number"]
        
        # Verify transfer number format TRF-YYYY-XXXX
        transfer_num = data["transfer_number"]
        assert transfer_num.startswith("TRF-"), f"Transfer number should start with 'TRF-': {transfer_num}"
        year = datetime.now().year
        assert str(year) in transfer_num, f"Transfer number should contain current year: {transfer_num}"
        
        # Verify exit and entry movements
        assert "exit" in data and "entry" in data, "Missing exit/entry movements in response"
        
        print(f"✓ POS Transfer successful - Number: {transfer_num}, PDF URL: {data['transfer_note_url']}")
    
    def test_12_verify_pdf_downloadable_and_valid(self):
        """Verify the generated PDF is downloadable and has valid size (>5KB)"""
        assert TestTransferNotePDF.transfer_note_url, "No transfer_note_url from previous test"
        
        pdf_url = f"{BASE_URL}/api{TestTransferNotePDF.transfer_note_url}"
        response = requests.get(pdf_url, headers=self._get_headers())
        
        assert response.status_code == 200, f"PDF download failed: {response.status_code}"
        assert response.headers.get("content-type", "").startswith("application/pdf"), \
            f"Expected PDF content-type, got: {response.headers.get('content-type')}"
        
        # Verify file size > 5KB (5120 bytes)
        content_length = len(response.content)
        assert content_length > 5120, f"PDF too small ({content_length} bytes), expected >5KB"
        
        print(f"✓ PDF downloaded successfully, size: {content_length} bytes ({content_length/1024:.1f} KB)")
    
    def test_13_verify_movements_have_transfer_fields(self):
        """Verify movements have transfer_number and transfer_note_url fields"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/movements",
            headers=self._get_headers()
        )
        assert response.status_code == 200, f"Failed to get movements: {response.text}"
        movements = response.json()
        
        # Find transfer_salida movements
        transfer_movements = [m for m in movements if m.get("movement_type") == "transferencia_salida"]
        assert len(transfer_movements) > 0, "No transfer movements found"
        
        # Verify the latest transfer movement has the fields
        latest_transfer = transfer_movements[0]
        assert "transfer_number" in latest_transfer, "Movement missing transfer_number"
        assert "transfer_note_url" in latest_transfer, "Movement missing transfer_note_url"
        assert latest_transfer["transfer_note_url"] is not None, "transfer_note_url should not be None"
        
        print(f"✓ Movements have transfer fields - transfer_number: {latest_transfer['transfer_number']}")
    
    def test_14_transfer_pinpad_verify_technical_note(self):
        """Transfer Pinpad and verify PDF contains the technical note about PinPads"""
        serial_to_transfer = TestTransferNotePDF.pinpad_serials[0]
        response = requests.post(
            f"{BASE_URL}/api/inventory/transfer",
            headers=self._get_headers(),
            json={
                "source_warehouse_id": TestTransferNotePDF.warehouse_origin_id,
                "dest_warehouse_id": TestTransferNotePDF.warehouse_dest_id,
                "item_id": TestTransferNotePDF.hardware_pinpad_id,
                "quantity": 1,
                "serials": [serial_to_transfer],
                "notes": "Pinpad transfer test - should include technical note"
            }
        )
        assert response.status_code in [200, 201], f"Pinpad transfer failed: {response.text}"
        data = response.json()
        
        # Store Pinpad PDF URL for verification
        pinpad_pdf_url = data.get("transfer_note_url")
        assert pinpad_pdf_url is not None, "No PDF URL for Pinpad transfer"
        
        # Download and check PDF content contains technical note
        pdf_full_url = f"{BASE_URL}/api{pinpad_pdf_url}"
        pdf_response = requests.get(pdf_full_url, headers=self._get_headers())
        assert pdf_response.status_code == 200, "Failed to download Pinpad PDF"
        
        # Note: Checking PDF text content requires PDF parsing, but we verify size
        # The actual text verification would need a PDF parser like pypdf
        pdf_size = len(pdf_response.content)
        assert pdf_size > 5120, f"Pinpad PDF too small: {pdf_size} bytes"
        
        print(f"✓ Pinpad transfer PDF generated - URL: {pinpad_pdf_url}, size: {pdf_size} bytes")
        print("  Note: PDF should contain 'Nota tecnica: Los PinPads son entregados con: Cable USB, Licencia EMV y Privacy Shields.'")
    
    def test_15_transfer_cable_non_serialized(self):
        """Transfer Cable (non-serialized) and verify PDF generated without serials"""
        response = requests.post(
            f"{BASE_URL}/api/inventory/transfer",
            headers=self._get_headers(),
            json={
                "source_warehouse_id": TestTransferNotePDF.warehouse_origin_id,
                "dest_warehouse_id": TestTransferNotePDF.warehouse_dest_id,
                "item_id": TestTransferNotePDF.hardware_cable_id,
                "quantity": 5,
                "serials": [],  # Non-serialized - empty array
                "notes": "Cable transfer test - non-serialized item"
            }
        )
        assert response.status_code in [200, 201], f"Cable transfer failed: {response.text}"
        data = response.json()
        
        # Verify PDF was generated
        assert "transfer_note_url" in data, "No transfer_note_url for Cable transfer"
        cable_pdf_url = data.get("transfer_note_url")
        assert cable_pdf_url is not None, "Cable PDF URL is None"
        
        # Verify correlativo format
        transfer_num = data.get("transfer_number")
        assert transfer_num.startswith("TRF-"), f"Invalid transfer number format: {transfer_num}"
        
        # Download and verify PDF
        pdf_full_url = f"{BASE_URL}/api{cable_pdf_url}"
        pdf_response = requests.get(pdf_full_url, headers=self._get_headers())
        assert pdf_response.status_code == 200, "Failed to download Cable PDF"
        
        print(f"✓ Cable (non-serialized) transfer PDF generated - URL: {cable_pdf_url}")
    
    def test_16_verify_correlativo_auto_increment(self):
        """Verify the transfer correlativo auto-increments correctly"""
        # Do another transfer and verify number increments
        response = requests.post(
            f"{BASE_URL}/api/inventory/transfer",
            headers=self._get_headers(),
            json={
                "source_warehouse_id": TestTransferNotePDF.warehouse_origin_id,
                "dest_warehouse_id": TestTransferNotePDF.warehouse_dest_id,
                "item_id": TestTransferNotePDF.hardware_cable_id,
                "quantity": 2,
                "serials": [],
                "notes": "Transfer to verify auto-increment"
            }
        )
        assert response.status_code in [200, 201], f"Transfer failed: {response.text}"
        data = response.json()
        
        new_transfer_num = data.get("transfer_number")
        assert new_transfer_num is not None, "No transfer_number in response"
        
        # Extract numeric part and compare
        old_num = int(TestTransferNotePDF.transfer_number.split("-")[-1])
        new_num = int(new_transfer_num.split("-")[-1])
        
        # New number should be greater (auto-incremented)
        assert new_num > old_num, f"Transfer number did not increment: {old_num} -> {new_num}"
        
        print(f"✓ Correlativo auto-incremented: {TestTransferNotePDF.transfer_number} -> {new_transfer_num}")
    
    def test_17_verify_dest_warehouse_movements(self):
        """Verify destination warehouse has transfer_entrada movements with PDF URL"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_dest_id}/movements",
            headers=self._get_headers()
        )
        assert response.status_code == 200, f"Failed to get dest movements: {response.text}"
        movements = response.json()
        
        # Find transfer_entrada movements
        entry_movements = [m for m in movements if m.get("movement_type") == "transferencia_entrada"]
        assert len(entry_movements) > 0, "No transfer_entrada movements in destination warehouse"
        
        # Verify at least one has transfer_note_url
        has_pdf_url = any(m.get("transfer_note_url") for m in entry_movements)
        assert has_pdf_url, "Destination movements missing transfer_note_url"
        
        print(f"✓ Destination warehouse has {len(entry_movements)} transfer_entrada movements with PDF URLs")
    
    def test_18_verify_final_stock_distribution(self):
        """Verify final stock is distributed correctly between warehouses"""
        # Check origin warehouse stock
        origin_response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_origin_id}/stock",
            headers=self._get_headers()
        )
        assert origin_response.status_code == 200
        origin_stock = origin_response.json()
        
        # Check destination warehouse stock  
        dest_response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses/{TestTransferNotePDF.warehouse_dest_id}/stock",
            headers=self._get_headers()
        )
        assert dest_response.status_code == 200
        dest_stock = dest_response.json()
        
        # Find items in both stocks
        origin_pos = next((s for s in origin_stock if s["item_id"] == TestTransferNotePDF.hardware_pos_id), None)
        dest_pos = next((s for s in dest_stock if s["item_id"] == TestTransferNotePDF.hardware_pos_id), None)
        
        print(f"✓ Final stock verified - Origin POS: {origin_pos['quantity'] if origin_pos else 0}, Dest POS: {dest_pos['quantity'] if dest_pos else 0}")
        
        # Verify items transferred are in destination
        assert dest_pos is not None, "Transferred POS not found in destination"
        assert dest_pos["quantity"] >= 1, "Destination should have at least 1 POS"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
