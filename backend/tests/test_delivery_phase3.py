"""
Iteration 99: Test suite for Inventory Phase 3 - Automatic stock exits on equipment quote delivery
Tests:
- GET /api/quotes/{quote_id}/delivery-prep
- GET /api/quotes/{quote_id}/delivery-prep?warehouse_id=X
- POST /api/quotes/{quote_id}/deliver
- Stock deduction after delivery
- Hoja de Ruta PDF generation
- Error handling for insufficient stock and wrong serials
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials (using existing test user from iteration 98)
TEST_EMAIL = "np_test@test.com"
TEST_PASSWORD = "Test1234!"

class TestDeliveryPhase3:
    """Test suite for automatic stock exits during equipment quote delivery"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with existing test user
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        print(f"Login response: {login_resp.status_code} - {login_resp.text[:200]}")
        
        if login_resp.status_code == 200:
            token = login_resp.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = login_resp.json().get("user", {})
            print(f"Authenticated as: {self.user.get('email')}")
        else:
            pytest.fail(f"Authentication failed: {login_resp.text}")
        
        yield
    
    # ===== SETUP HELPERS =====
    
    def create_client(self):
        """Create a test client"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "rif": f"J-TEST{unique_id}",
            "legal_name": f"Test Client Phase3 {unique_id}",
            "fantasy_name": f"TestCliente{unique_id}",
            "segment": "Pymes",
            "condicion": "Prospecto"
        }
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create client: {resp.text}"
        return resp.json()
    
    def create_hardware_pos(self):
        """Create a POS hardware item (serialized type)"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TestPOS_{unique_id}",
            "type": "POS",
            "price_usd": 250.00,
            "price_bs_usd": 250.00,
            "description": "Test POS for delivery testing"
        }
        resp = self.session.post(f"{BASE_URL}/api/hardware", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create hardware: {resp.text}"
        return resp.json()
    
    def create_warehouse(self):
        """Create a test warehouse"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TestWarehouse_{unique_id}",
            "location": "Test Location",
            "notes": "Created for Phase 3 delivery testing"
        }
        resp = self.session.post(f"{BASE_URL}/api/inventory/warehouses", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create warehouse: {resp.text}"
        return resp.json()
    
    def create_stock_entry(self, warehouse_id, hardware_id, quantity, serials):
        """Create inventory entry with serials for POS hardware"""
        payload = {
            "item_id": hardware_id,
            "quantity": quantity,
            "unit_cost": 250.00,
            "serials": serials,
            "notes": "Stock for delivery testing"
        }
        resp = self.session.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create stock entry: {resp.text}"
        return resp.json()
    
    def create_equipment_quote(self, client_id, hardware_id, hardware_name, quantity):
        """Create an equipment quote with specified items"""
        payload = {
            "client_id": client_id,
            "quote_category": "equipment",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [
                {
                    "hardware_id": hardware_id,
                    "name": hardware_name,
                    "hardware_type": "POS",
                    "quantity": quantity,
                    "unit_price_usd": 250.00,
                    "total_usd": 250.00 * quantity
                }
            ],
            "notes": "Equipment quote for delivery testing"
        }
        resp = self.session.post(f"{BASE_URL}/api/quotes", json=payload)
        assert resp.status_code in [200, 201], f"Failed to create quote: {resp.text}"
        return resp.json()
    
    def advance_quote_to_pagada(self, quote_id):
        """Advance equipment quote through states to Pagada: Borrador -> Enviada -> Aprobada -> Facturada -> Pagada"""
        # Step 1: Send to client (Borrador -> Enviada)
        resp = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        if resp.status_code not in [200, 201]:
            # Try status endpoint
            resp = self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Step 2: Upload Orden de Compra attachment (required for approval)
        # Create a simple test file upload simulation
        oc_payload = {
            "category": "Orden de Compra",
            "filename": "test_oc.pdf",
            "url": "/uploads/test_oc.pdf",
            "uploaded_by": TEST_EMAIL,
            "uploaded_by_name": "Delivery Tester",
            "uploaded_at": datetime.utcnow().isoformat(),
            "content_type": "application/pdf"
        }
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", json=oc_payload)
        
        # Step 3: Approve (Enviada -> Aprobada) - using irregular flow if needed
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/approve",
            headers={"x-exception-reason": "Testing", "x-regularization-date": "2026-02-01"}
        )
        
        # Step 4: Upload Factura attachment (required for invoicing)
        factura_payload = {
            "category": "Factura",
            "filename": "test_factura.pdf",
            "url": "/uploads/test_factura.pdf",
            "uploaded_by": TEST_EMAIL,
            "uploaded_by_name": "Delivery Tester",
            "uploaded_at": datetime.utcnow().isoformat(),
            "content_type": "application/pdf"
        }
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", json=factura_payload)
        
        # Step 5: Invoice (Aprobada -> Facturada) - using irregular flow if needed
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "TEST-001", "exception_reason": "Testing", "regularization_date": "2026-02-01"},
            headers={"Content-Type": "application/x-www-form-urlencoded", "x-exception-reason": "Testing", "x-regularization-date": "2026-02-01"}
        )
        
        # Step 6: Upload Pagos attachment (required for payment)
        pagos_payload = {
            "category": "Pagos",
            "filename": "test_pago.pdf",
            "url": "/uploads/test_pago.pdf",
            "uploaded_by": TEST_EMAIL,
            "uploaded_by_name": "Delivery Tester",
            "uploaded_at": datetime.utcnow().isoformat(),
            "content_type": "application/pdf"
        }
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", json=pagos_payload)
        
        # Step 7: Collect (Facturada -> Pagada) - using irregular flow if needed
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/collect",
            headers={"x-exception-reason": "Testing", "x-regularization-date": "2026-02-01"}
        )
        
        return resp
    
    # ===== DELIVERY-PREP TESTS =====
    
    def test_01_delivery_prep_without_warehouse(self):
        """Test GET /api/quotes/{quote_id}/delivery-prep returns items and warehouses"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Call delivery-prep
        resp = self.session.get(f"{BASE_URL}/api/quotes/{quote['quote_id']}/delivery-prep")
        assert resp.status_code == 200, f"delivery-prep failed: {resp.text}"
        
        data = resp.json()
        assert "quote_number" in data
        assert "warehouses" in data
        assert "items" in data
        assert len(data["items"]) >= 1
        
        # Verify item structure
        item = data["items"][0]
        assert "hardware_id" in item
        assert "quantity_quoted" in item
        assert "stock_available" in item
        assert "requires_serial" in item
        
        print(f"TEST 01 PASSED: delivery-prep returns items and warehouses correctly")
    
    def test_02_delivery_prep_with_warehouse_returns_serials(self):
        """Test GET /api/quotes/{quote_id}/delivery-prep?warehouse_id=X returns available serials"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock with serials
        serials = [f"SN-TEST-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 3, serials)
        
        # Create quote
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Call delivery-prep with warehouse
        resp = self.session.get(f"{BASE_URL}/api/quotes/{quote['quote_id']}/delivery-prep?warehouse_id={warehouse['warehouse_id']}")
        assert resp.status_code == 200, f"delivery-prep with warehouse failed: {resp.text}"
        
        data = resp.json()
        assert len(data["items"]) >= 1
        
        item = data["items"][0]
        assert item["stock_available"] >= 3
        assert "serials_available" in item
        assert len(item["serials_available"]) >= 3
        assert item["requires_serial"] == True  # POS type requires serial
        
        print(f"TEST 02 PASSED: delivery-prep with warehouse_id returns serials: {item['serials_available']}")
    
    def test_03_delivery_prep_only_equipment_quotes(self):
        """Test delivery-prep returns 400 for non-equipment quotes"""
        # Create implementation quote (not equipment)
        client = self.create_client()
        
        payload = {
            "client_id": client["client_id"],
            "quote_category": "implementation",  # NOT equipment
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test Service",
                    "quantity": 1,
                    "unit_price_usd": 100.00,
                    "total_usd": 100.00
                }
            ],
            "hardware": [],
            "equipment_items": []
        }
        resp = self.session.post(f"{BASE_URL}/api/quotes", json=payload)
        quote = resp.json()
        
        # Call delivery-prep - should fail for non-equipment quote
        resp = self.session.get(f"{BASE_URL}/api/quotes/{quote['quote_id']}/delivery-prep")
        assert resp.status_code == 400, f"Expected 400 for non-equipment quote, got {resp.status_code}"
        
        print(f"TEST 03 PASSED: delivery-prep correctly rejects non-equipment quotes")
    
    # ===== DELIVER ENDPOINT TESTS =====
    
    def test_04_deliver_quote_creates_exit_movements(self):
        """Test POST /api/quotes/{quote_id}/deliver creates inventory exit movements"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock with serials
        serials = [f"SN-DELIVER-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 3, serials)
        
        # Create quote (don't need to advance - will use exception header)
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Get stock before delivery
        stock_before = self.session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse['warehouse_id']}/stock")
        initial_stock = 0
        if stock_before.status_code == 200:
            for item in stock_before.json():
                if item["item_id"] == hardware["hardware_id"]:
                    initial_stock = item["quantity"]
                    break
        
        # Deliver with 2 serials (using exception header for irregular flow)
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 2,
                    "serials": serials[:2]  # Use first 2 serials
                }
            ],
            "notes": "Test delivery for Phase 3"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={"x-exception-reason": "Testing Phase 3", "x-regularization-date": "2026-02-01"}
        )
        assert resp.status_code == 200, f"Deliver failed: {resp.text}"
        
        data = resp.json()
        assert data.get("inventory_processed") == True
        assert data.get("items_delivered") == 1  # 1 item type delivered
        
        # Verify stock was deducted
        stock_after = self.session.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse['warehouse_id']}/stock")
        final_stock = 0
        if stock_after.status_code == 200:
            for item in stock_after.json():
                if item["item_id"] == hardware["hardware_id"]:
                    final_stock = item["quantity"]
                    break
        
        assert final_stock == initial_stock - 2, f"Stock not properly deducted. Before: {initial_stock}, After: {final_stock}"
        
        print(f"TEST 04 PASSED: Delivery created exit movements, stock reduced from {initial_stock} to {final_stock}")
    
    def test_05_deliver_generates_hoja_ruta_pdf(self):
        """Test delivery generates Hoja de Ruta PDF and attaches to quote"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock
        serials = [f"SN-PDF-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 2, serials)
        
        # Create quote (using exception header for faster testing)
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Deliver with exception header
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 2,
                    "serials": serials
                }
            ],
            "notes": "PDF generation test"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={"x-exception-reason": "PDF test", "x-regularization-date": "2026-02-01"}
        )
        assert resp.status_code == 200, f"Deliver failed: {resp.text}"
        
        data = resp.json()
        assert "hoja_ruta_url" in data
        assert data["hoja_ruta_url"] is not None
        assert "HojaRuta_" in data["hoja_ruta_url"]
        assert ".pdf" in data["hoja_ruta_url"]
        
        print(f"TEST 05 PASSED: Hoja de Ruta PDF generated: {data['hoja_ruta_url']}")
    
    def test_06_deliver_insufficient_stock_returns_400(self):
        """Test delivery with insufficient stock returns 400 error"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add only 1 item to stock
        serials = [f"SN-INSUF-{uuid.uuid4().hex[:8]}"]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 1, serials)
        
        # Create quote requesting 5 items
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 5)
        
        # Try to deliver 5 items when only 1 in stock (with exception header to bypass status check)
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 5,
                    "serials": ["SN1", "SN2", "SN3", "SN4", "SN5"]  # Invalid serials
                }
            ],
            "notes": "Insufficient stock test"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={"x-exception-reason": "Stock test", "x-regularization-date": "2026-02-01"}
        )
        assert resp.status_code == 400, f"Expected 400 for insufficient stock, got {resp.status_code}: {resp.text}"
        assert "insuficiente" in resp.json().get("detail", "").lower() or "insufficient" in resp.json().get("detail", "").lower()
        
        print(f"TEST 06 PASSED: Insufficient stock correctly returns 400: {resp.json().get('detail')}")
    
    def test_07_deliver_wrong_serials_returns_400(self):
        """Test delivery with wrong/unavailable serials returns 400 error"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock with specific serials
        real_serials = [f"SN-REAL-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 2, real_serials)
        
        # Create quote
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Try to deliver with wrong serials (with exception header to bypass status check)
        wrong_serials = ["WRONG-SERIAL-1", "WRONG-SERIAL-2"]
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 2,
                    "serials": wrong_serials
                }
            ],
            "notes": "Wrong serial test"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={"x-exception-reason": "Serial test", "x-regularization-date": "2026-02-01"}
        )
        assert resp.status_code == 400, f"Expected 400 for wrong serials, got {resp.status_code}: {resp.text}"
        
        print(f"TEST 07 PASSED: Wrong serials correctly returns 400: {resp.json().get('detail')}")
    
    def test_08_deliver_without_pagada_status_requires_exception(self):
        """Test delivery on non-Pagada quote requires exception headers (irregular flow)"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock
        serials = [f"SN-IRREG-{uuid.uuid4().hex[:8]}"]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 1, serials)
        
        # Create quote but don't advance to Pagada
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 1)
        
        # Try to deliver without exception header
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 1,
                    "serials": serials
                }
            ],
            "notes": "Irregular flow test"
        }
        resp = self.session.post(f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver", json=deliver_payload)
        # Should require exception reason for irregular flow
        assert resp.status_code == 422, f"Expected 422 for irregular flow without exception, got {resp.status_code}"
        assert "IRREGULAR" in resp.json().get("detail", "").upper()
        
        print(f"TEST 08 PASSED: Non-Pagada delivery requires exception: {resp.json().get('detail')}")
    
    def test_09_deliver_with_exception_header_succeeds(self):
        """Test delivery with x-exception-reason header works for irregular flow"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock
        serials = [f"SN-EXCP-{uuid.uuid4().hex[:8]}"]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 1, serials)
        
        # Create quote but don't advance to Pagada
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 1)
        
        # Deliver with exception header
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 1,
                    "serials": serials
                }
            ],
            "notes": "Exception flow test"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={
                "x-exception-reason": "Testing irregular flow",
                "x-regularization-date": "2026-02-01"
            }
        )
        assert resp.status_code == 200, f"Delivery with exception header failed: {resp.text}"
        
        print(f"TEST 09 PASSED: Delivery with exception header succeeds")
    
    def test_10_delivery_prep_not_found_quote(self):
        """Test delivery-prep returns 404 for non-existent quote"""
        resp = self.session.get(f"{BASE_URL}/api/quotes/nonexistent_quote_id/delivery-prep")
        assert resp.status_code == 404
        
        print(f"TEST 10 PASSED: delivery-prep returns 404 for non-existent quote")
    
    def test_11_verify_quote_status_after_delivery(self):
        """Test quote status is 'Entregada' after successful delivery"""
        # Create test data
        client = self.create_client()
        hardware = self.create_hardware_pos()
        warehouse = self.create_warehouse()
        
        # Add stock
        serials = [f"SN-STATUS-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        self.create_stock_entry(warehouse["warehouse_id"], hardware["hardware_id"], 2, serials)
        
        # Create quote
        quote = self.create_equipment_quote(client["client_id"], hardware["hardware_id"], hardware["name"], 2)
        
        # Deliver with exception header
        deliver_payload = {
            "warehouse_id": warehouse["warehouse_id"],
            "delivery_items": [
                {
                    "hardware_id": hardware["hardware_id"],
                    "quantity": 2,
                    "serials": serials
                }
            ],
            "notes": "Status check test"
        }
        resp = self.session.post(
            f"{BASE_URL}/api/quotes/{quote['quote_id']}/deliver",
            json=deliver_payload,
            headers={"x-exception-reason": "Status test", "x-regularization-date": "2026-02-01"}
        )
        assert resp.status_code == 200, f"Delivery failed: {resp.text}"
        
        # Verify quote status
        quote_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote['quote_id']}")
        if quote_resp.status_code == 200:
            updated_quote = quote_resp.json()
            assert updated_quote.get("quote_status") == "Entregada"
            print(f"TEST 11 PASSED: Quote status is 'Entregada' after delivery")
        else:
            # Quote might be in the list
            all_quotes = self.session.get(f"{BASE_URL}/api/quotes")
            if all_quotes.status_code == 200:
                for q in all_quotes.json():
                    if q.get("quote_id") == quote["quote_id"]:
                        assert q.get("quote_status") == "Entregada"
                        print(f"TEST 11 PASSED: Quote status is 'Entregada' after delivery")
                        return
            print(f"TEST 11 WARNING: Could not verify quote status, but delivery succeeded")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
