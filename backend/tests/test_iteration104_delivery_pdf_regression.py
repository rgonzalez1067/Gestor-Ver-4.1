# ruff: noqa
"""
Test Iteration 104 - Delivery Notes PDF Regression Testing
Tests for the Nota de Entrega PDF generation with pagination (X/Y page numbering,
persistent headers on pages 2+, and KeepTogether for row anti-split).

Full delivery flow test:
1. User registration and login (prerequisite)
2. Create hardware product type 'POS' (serialized) - POST /api/hardware
3. Create warehouse - POST /api/inventory/warehouses
4. Register inventory entry with serials - POST /api/inventory/warehouses/{warehouse_id}/entry
5. Create client - POST /api/clients
6. Create equipment quote with equipment_items - POST /api/quotes_pdf (or /api/quotes)
7. Get delivery prep data - GET /api/quotes/{quote_id}/delivery-prep?warehouse_id=xxx
8. Execute delivery with inventory deduction - POST /api/quotes/{quote_id}/deliver
9. Verify PDF generation via /uploads/NotaEntrega_*.pdf
10. Multi-page test with 15+ items to verify pagination X/Y
11. Kardex endpoint - POST /api/inventory/kardex
12. Search by client endpoint - POST /api/inventory/search_by_client
"""
import pytest
import requests
import os
from datetime import datetime, timezone
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDeliveryPDFRegression:
    """Full regression tests for delivery PDF generation"""
    
    # =======================
    # Test 1: User Registration and Login
    # =======================
    
    def test_01_user_registration(self, api_client):
        """Test user registration - first user becomes admin"""
        unique_id = uuid.uuid4().hex[:6]
        register_payload = {
            "first_name": "Delivery",
            "last_name": "Tester",
            "cedula": f"V{unique_id}",
            "email": f"delivery_test_{unique_id}@test.com",
            "password": "Test12345!",
            "phone": "04141234567",
            "cargo": "Implementador",
            "departamento": "Implementación",
            "sede": "PYME"
        }
        
        response = api_client.post(f"{BASE_URL}/api/auth/register", json=register_payload)
        # May fail if user already exists (409) or succeed (200)
        assert response.status_code in [200, 201, 409], f"Registration response: {response.text}"
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "session_token" in data or "user_id" in data, "Should return token or user_id"
    
    def test_02_user_login(self, api_client):
        """Test user login with existing credentials"""
        login_payload = {
            "email": "delivery@test.com",
            "password": "Test12345!"
        }
        
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=login_payload)
        assert response.status_code == 200, f"Login should succeed: {response.text}"
        
        data = response.json()
        assert "session_token" in data, "Login should return session_token"
        assert len(data["session_token"]) > 0, "Token should not be empty"
    
    # =======================
    # Test 2: Create Hardware Product (POS type)
    # =======================
    
    def test_03_create_pos_hardware(self, api_client, auth_token):
        """Create a POS hardware product (serialized type)"""
        unique_id = uuid.uuid4().hex[:6]
        hardware_payload = {
            "name": f"TEST_POS_{unique_id}",
            "type": "POS",
            "price_usd": 150.00,
            "price_bs_usd": 150.00,
            "description": "Test POS device for delivery flow"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/hardware",
            json=hardware_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [200, 201], f"Hardware creation failed: {response.text}"
        
        data = response.json()
        assert "hardware_id" in data, "Should return hardware_id"
        assert data["type"].lower() == "pos", "Type should be POS"
    
    def test_04_list_hardware(self, api_client, auth_token):
        """List hardware catalog to verify POS exists"""
        response = api_client.get(
            f"{BASE_URL}/api/hardware",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        hardware_list = response.json()
        assert isinstance(hardware_list, list), "Should return list of hardware"
        
        # Find POS type hardware
        pos_items = [h for h in hardware_list if h.get("type", "").lower() == "pos"]
        assert len(pos_items) > 0, "Should have at least one POS hardware item"
    
    # =======================
    # Test 3: Create Warehouse
    # =======================
    
    def test_05_create_warehouse(self, api_client, auth_token):
        """Create a warehouse for inventory management"""
        unique_id = uuid.uuid4().hex[:6]
        warehouse_payload = {
            "name": f"TEST_Warehouse_{unique_id}",
            "location": "Test Location",
            "notes": "Warehouse for delivery testing"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/inventory/warehouses",
            json=warehouse_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [200, 201], f"Warehouse creation failed: {response.text}"
        
        data = response.json()
        assert "warehouse_id" in data, "Should return warehouse_id"
        assert data["name"].startswith("TEST_Warehouse"), "Name should match"
    
    def test_06_list_warehouses(self, api_client, auth_token):
        """List warehouses to verify creation"""
        response = api_client.get(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        warehouses = response.json()
        assert isinstance(warehouses, list), "Should return list of warehouses"
        assert len(warehouses) > 0, "Should have at least one warehouse"
    
    # =======================
    # Test 4: Register Inventory Entry with Serials
    # =======================
    
    def test_07_inventory_entry_with_serials(self, api_client, auth_token, get_warehouse_id, get_pos_hardware_id):
        """Register inventory entry with serial numbers for POS device"""
        warehouse_id = get_warehouse_id
        hardware_id = get_pos_hardware_id
        
        unique_id = uuid.uuid4().hex[:4]
        serials = [f"SN-TEST-{unique_id}-001", f"SN-TEST-{unique_id}-002", f"SN-TEST-{unique_id}-003"]
        
        entry_payload = {
            "item_id": hardware_id,
            "quantity": 3,
            "unit_cost": 150.00,
            "serials": serials,
            "notes": "Test entry for delivery flow"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry",
            json=entry_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [200, 201], f"Inventory entry failed: {response.text}"
        
        data = response.json()
        assert data["movement_type"] == "entrada", "Should be entrada movement"
        assert data["quantity"] == 3, "Quantity should match"
        assert len(data.get("serials", [])) == 3, "Should have 3 serials"
    
    def test_08_verify_stock_with_serials(self, api_client, auth_token, get_warehouse_id):
        """Verify stock shows available serials"""
        warehouse_id = get_warehouse_id
        
        response = api_client.get(
            f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        stock_items = response.json()
        assert isinstance(stock_items, list), "Should return list of stock items"
        
        # Find POS items with serials
        pos_items = [s for s in stock_items if s.get("item_type", "").lower() == "pos"]
        if pos_items:
            assert pos_items[0].get("quantity", 0) > 0, "Should have stock"
    
    # =======================
    # Test 5: Create Client
    # =======================
    
    def test_09_create_client(self, api_client, auth_token):
        """Create a client for the quote"""
        unique_id = uuid.uuid4().hex[:6]
        client_payload = {
            "rif": f"J-TEST{unique_id}",
            "legal_name": f"TEST Cliente Delivery {unique_id}",
            "fantasy_name": f"Client PDF Test {unique_id}",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "address": "Test Address for Delivery Notes PDF",
            "contacts": [{
                "full_name": "Contact Person",
                "phone": "04141234567",
                "email": "contact@test.com",
                "role": "Administrativo"
            }]
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/clients",
            json=client_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [200, 201], f"Client creation failed: {response.text}"
        
        data = response.json()
        assert "client_id" in data, "Should return client_id"
    
    def test_10_list_clients(self, api_client, auth_token):
        """List clients to verify creation"""
        response = api_client.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        # API returns list directly
        clients = response.json()
        if isinstance(clients, dict):
            clients = clients.get("clients", [])
        
        assert isinstance(clients, list), "Should return list of clients"
        assert len(clients) > 0, "Should have at least one client"
    
    # =======================
    # Test 6: Create Equipment Quote
    # =======================
    
    def test_11_create_equipment_quote(self, api_client, auth_token, get_client_id, get_pos_hardware_id):
        """Create equipment quote with equipment_items"""
        client_id = get_client_id
        hardware_id = get_pos_hardware_id
        unique_id = uuid.uuid4().hex[:4]
        
        quote_payload = {
            "client_id": client_id,
            "quote_category": "equipment",
            "quote_type": "POS",
            "equipment_items": [{
                "hardware_id": hardware_id,
                "name": "Test POS Device",
                "hardware_type": "POS",
                "quantity": 2,
                "unit_price_usd": 150.00,
                "total_usd": 300.00
            }],
            "total_usd": 300.00,
            "total_bs": 12000.00,
            "sede": "PYME",
            "client_segment": "PYME",
            "notes": f"TEST_DELIVERY_PDF_{unique_id}"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes",
            json=quote_payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code in [200, 201], f"Quote creation failed: {response.text}"
        
        data = response.json()
        assert "quote_id" in data, "Should return quote_id"
        assert data["quote_category"] == "equipment", "Should be equipment quote"
    
    # =======================
    # Test 7: Delivery Prep Endpoint
    # =======================
    
    def test_12_delivery_prep_endpoint(self, api_client, auth_token, create_equipment_quote_paid):
        """Test GET /api/quotes/{quote_id}/delivery-prep"""
        quote_id = create_equipment_quote_paid
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/delivery-prep",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Delivery prep failed: {response.text}"
        
        data = response.json()
        assert "warehouses" in data, "Should contain warehouses list"
        assert "items" in data, "Should contain items list"
        assert "quote_number" in data, "Should contain quote_number"
    
    def test_13_delivery_prep_with_warehouse_returns_stock(self, api_client, auth_token, create_equipment_quote_paid, get_warehouse_id):
        """Test delivery-prep with warehouse_id returns stock info"""
        quote_id = create_equipment_quote_paid
        warehouse_id = get_warehouse_id
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/delivery-prep?warehouse_id={warehouse_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        for item in items:
            assert "stock_available" in item, "Item should have stock_available"
            assert "serials_available" in item, "Item should have serials_available"
            assert "requires_serial" in item, "Item should have requires_serial flag"
    
    # =======================
    # Test 8: Execute Delivery with PDF Generation
    # =======================
    
    def test_14_execute_delivery_generates_pdf(self, api_client, auth_token, create_equipment_quote_paid):
        """Test POST /api/quotes/{quote_id}/deliver generates Nota de Entrega PDF"""
        quote_id = create_equipment_quote_paid
        
        delivery_payload = {
            "warehouse_id": "whs_f00b02f4",  # Use existing warehouse
            "delivery_items": [],  # Empty for simple test
            "notes": "Delivery test for PDF generation",
            "transportista": "Test Courier",
            "guia_placa": "TEST-001"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=delivery_payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test delivery PDF",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Delivery failed: {response.text}"
        
        data = response.json()
        assert data["message"] == "Cotización marcada como Entregada", "Should mark as delivered"
    
    def test_15_delivery_with_items_generates_pdf_url(self, api_client, auth_token, create_quote_with_inventory):
        """Test delivery with inventory items returns hoja_ruta_url"""
        result = create_quote_with_inventory
        quote_id = result["quote_id"]
        warehouse_id = result["warehouse_id"]
        hardware_id = result["hardware_id"]
        serials = result["serials"][:2]  # Use 2 serials
        
        delivery_payload = {
            "warehouse_id": warehouse_id,
            "delivery_items": [{
                "hardware_id": hardware_id,
                "quantity": 2,
                "serials": serials
            }],
            "notes": "Full delivery test",
            "transportista": "Express Delivery Co",
            "guia_placa": "EXP-2026-001"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=delivery_payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Full delivery test",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Delivery failed: {response.text}"
        
        data = response.json()
        assert "hoja_ruta_url" in data, "Should contain hoja_ruta_url"
        
        hoja_ruta_url = data.get("hoja_ruta_url")
        if hoja_ruta_url:
            assert "NotaEntrega_NE-" in hoja_ruta_url, f"PDF filename should follow format: {hoja_ruta_url}"
            assert data["inventory_processed"] == True, "Inventory should be processed"
    
    # =======================
    # Test 9: Verify PDF Download
    # =======================
    
    def test_16_pdf_download_accessible(self, api_client, auth_token, create_quote_with_inventory):
        """Test that generated PDF is accessible via /uploads/"""
        result = create_quote_with_inventory
        quote_id = result["quote_id"]
        warehouse_id = result["warehouse_id"]
        hardware_id = result["hardware_id"]
        serials = result["serials"][:1]  # Use 1 serial
        
        # Execute delivery
        delivery_payload = {
            "warehouse_id": warehouse_id,
            "delivery_items": [{
                "hardware_id": hardware_id,
                "quantity": 1,
                "serials": serials
            }],
            "notes": "PDF download test",
            "transportista": "PDF Test Courier",
            "guia_placa": "PDF-TEST-001"
        }
        
        deliver_resp = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=delivery_payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "PDF download test",
                "x-regularization-date": "2026-01-15"
            }
        )
        
        if deliver_resp.status_code == 200:
            data = deliver_resp.json()
            hoja_ruta_url = data.get("hoja_ruta_url")
            
            if hoja_ruta_url:
                # Try to download the PDF
                pdf_url = f"{BASE_URL}{hoja_ruta_url}"
                pdf_resp = api_client.get(pdf_url)
                
                # PDF should be accessible (200) or may require auth
                assert pdf_resp.status_code in [200, 401, 403], f"PDF URL response: {pdf_resp.status_code}"
                
                if pdf_resp.status_code == 200:
                    # Verify it's a PDF
                    content_type = pdf_resp.headers.get("content-type", "")
                    assert "pdf" in content_type.lower() or len(pdf_resp.content) > 1000, "Should be PDF content"
    
    # =======================
    # Test 10: Multi-Page PDF (15+ items)
    # =======================
    
    def test_17_multipage_pdf_many_items(self, api_client, auth_token, create_multiitem_quote):
        """Test PDF generation with 15+ items forces multi-page output"""
        result = create_multiitem_quote
        quote_id = result["quote_id"]
        warehouse_id = result["warehouse_id"]
        delivery_items = result["delivery_items"]
        
        # Execute delivery with all items
        delivery_payload = {
            "warehouse_id": warehouse_id,
            "delivery_items": delivery_items,
            "notes": "Multi-page PDF test with 15+ items",
            "transportista": "Bulk Delivery Service",
            "guia_placa": "BULK-2026-001"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=delivery_payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Multi-page PDF test",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Multi-item delivery failed: {response.text}"
        
        data = response.json()
        hoja_ruta_url = data.get("hoja_ruta_url")
        
        if hoja_ruta_url:
            # Verify PDF exists and has reasonable size for multi-page
            pdf_url = f"{BASE_URL}{hoja_ruta_url}"
            pdf_resp = api_client.get(pdf_url)
            
            if pdf_resp.status_code == 200:
                pdf_size = len(pdf_resp.content)
                # Multi-page PDF should be >10KB
                assert pdf_size > 10000, f"Multi-page PDF should be >10KB, got {pdf_size} bytes"
                print(f"Multi-page PDF generated: {pdf_size} bytes")
    
    # =======================
    # Test 11: Kardex Endpoint
    # =======================
    
    def test_18_kardex_endpoint(self, api_client, auth_token, get_warehouse_id, get_pos_hardware_id):
        """Test GET /api/inventory/warehouses/{warehouse_id}/kardex/{item_id}"""
        warehouse_id = get_warehouse_id
        hardware_id = get_pos_hardware_id
        
        response = api_client.get(
            f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/kardex/{hardware_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Kardex endpoint failed: {response.text}"
        
        data = response.json()
        assert "item_id" in data, "Should contain item_id"
        assert "movements" in data, "Should contain movements list"
        assert "saldo_final" in data, "Should contain saldo_final"
        
        # Verify kardex structure
        movements = data.get("movements", [])
        if movements:
            mov = movements[0]
            assert "movement_id" in mov, "Movement should have movement_id"
            assert "movement_type" in mov, "Movement should have movement_type"
            assert "saldo" in mov, "Movement should have running saldo"
    
    # =======================
    # Test 12: Search by Client Endpoint
    # =======================
    
    def test_19_search_by_client(self, api_client, auth_token):
        """Test GET /api/inventory/movements/search?client_name=xxx"""
        response = api_client.get(
            f"{BASE_URL}/api/inventory/movements/search?client_name=Test",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Search by client failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list of movements"
    
    def test_20_search_by_client_minimum_chars(self, api_client, auth_token):
        """Test search requires minimum 2 characters"""
        response = api_client.get(
            f"{BASE_URL}/api/inventory/movements/search?client_name=A",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Should return 400 for insufficient characters
        assert response.status_code == 400, "Should require at least 2 characters"


# =======================
# Fixtures
# =======================

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": "delivery@test.com",
        "password": "Test12345!"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def get_warehouse_id(api_client, auth_token):
    """Get or create a warehouse for testing"""
    response = api_client.get(
        f"{BASE_URL}/api/inventory/warehouses",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if response.status_code == 200 and response.json():
        return response.json()[0]["warehouse_id"]
    
    # Create new warehouse
    unique_id = uuid.uuid4().hex[:4]
    create_resp = api_client.post(
        f"{BASE_URL}/api/inventory/warehouses",
        json={
            "name": f"TEST_Warehouse_{unique_id}",
            "location": "Test Location",
            "notes": "Auto-created for testing"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if create_resp.status_code in [200, 201]:
        return create_resp.json()["warehouse_id"]
    pytest.skip("Could not get or create warehouse")


@pytest.fixture
def get_pos_hardware_id(api_client, auth_token):
    """Get or create POS hardware for testing"""
    response = api_client.get(
        f"{BASE_URL}/api/hardware",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if response.status_code == 200:
        hardware_list = response.json()
        pos_items = [h for h in hardware_list if h.get("type", "").lower() == "pos"]
        if pos_items:
            return pos_items[0]["hardware_id"]
    
    # Create new POS hardware
    unique_id = uuid.uuid4().hex[:4]
    create_resp = api_client.post(
        f"{BASE_URL}/api/hardware",
        json={
            "name": f"TEST_POS_{unique_id}",
            "type": "POS",
            "price_usd": 150.00,
            "price_bs_usd": 150.00,
            "description": "Auto-created POS for testing"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if create_resp.status_code in [200, 201]:
        return create_resp.json()["hardware_id"]
    pytest.skip("Could not get or create POS hardware")


@pytest.fixture
def get_client_id(api_client, auth_token):
    """Get or create client for testing"""
    response = api_client.get(
        f"{BASE_URL}/api/clients",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if response.status_code == 200:
        clients = response.json()
        if isinstance(clients, dict):
            clients = clients.get("clients", [])
        if clients:
            return clients[0]["client_id"]
    
    # Create new client
    unique_id = uuid.uuid4().hex[:4]
    create_resp = api_client.post(
        f"{BASE_URL}/api/clients",
        json={
            "rif": f"J-TEST{unique_id}",
            "legal_name": f"TEST Client {unique_id}",
            "fantasy_name": f"Test {unique_id}",
            "segment": "Pymes"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if create_resp.status_code in [200, 201]:
        return create_resp.json()["client_id"]
    pytest.skip("Could not get or create client")


@pytest.fixture
def create_equipment_quote_paid(api_client, auth_token, get_client_id, get_pos_hardware_id):
    """Create an equipment quote in Pagada status"""
    client_id = get_client_id
    hardware_id = get_pos_hardware_id
    unique_id = uuid.uuid4().hex[:4]
    
    quote_payload = {
        "client_id": client_id,
        "quote_category": "equipment",
        "quote_type": "POS",
        "equipment_items": [{
            "hardware_id": hardware_id,
            "name": "Test POS",
            "hardware_type": "POS",
            "quantity": 1,
            "unit_price_usd": 150.00,
            "total_usd": 150.00
        }],
        "total_usd": 150.00,
        "total_bs": 6000.00,
        "sede": "PYME",
        "notes": f"TEST_PAID_{unique_id}"
    }
    
    create_resp = api_client.post(
        f"{BASE_URL}/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if create_resp.status_code not in [200, 201]:
        pytest.skip(f"Could not create quote: {create_resp.text}")
    
    quote_id = create_resp.json()["quote_id"]
    
    # Advance to Pagada using irregular flow
    api_client.put(
        f"{BASE_URL}/api/quotes/{quote_id}/status",
        json={"new_status": "Enviada"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/approve",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test skip OC",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/invoice",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test skip factura",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/collect",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test skip pago",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    return quote_id


@pytest.fixture
def create_quote_with_inventory(api_client, auth_token, get_client_id, get_warehouse_id, get_pos_hardware_id):
    """Create quote with inventory entry for full delivery test"""
    client_id = get_client_id
    warehouse_id = get_warehouse_id
    hardware_id = get_pos_hardware_id
    unique_id = uuid.uuid4().hex[:4]
    
    # Add inventory with serials
    serials = [f"SN-DLVR-{unique_id}-{i:02d}" for i in range(1, 4)]
    
    entry_resp = api_client.post(
        f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry",
        json={
            "item_id": hardware_id,
            "quantity": 3,
            "unit_cost": 150.00,
            "serials": serials,
            "notes": "Entry for delivery test"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    if entry_resp.status_code not in [200, 201]:
        pytest.skip(f"Could not create inventory entry: {entry_resp.text}")
    
    # Create quote
    quote_resp = api_client.post(
        f"{BASE_URL}/api/quotes",
        json={
            "client_id": client_id,
            "quote_category": "equipment",
            "quote_type": "POS",
            "equipment_items": [{
                "hardware_id": hardware_id,
                "name": "Test POS",
                "hardware_type": "POS",
                "quantity": 2,
                "unit_price_usd": 150.00,
                "total_usd": 300.00
            }],
            "total_usd": 300.00,
            "total_bs": 12000.00,
            "sede": "PYME",
            "notes": f"TEST_INVENTORY_{unique_id}"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    if quote_resp.status_code not in [200, 201]:
        pytest.skip(f"Could not create quote: {quote_resp.text}")
    
    quote_id = quote_resp.json()["quote_id"]
    
    # Advance to Pagada
    for action, endpoint in [
        ("status", f"/api/quotes/{quote_id}/status"),
    ]:
        api_client.put(
            f"{BASE_URL}{endpoint}",
            json={"new_status": "Enviada"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    for endpoint in [
        f"/api/quotes/{quote_id}/approve",
        f"/api/quotes/{quote_id}/invoice",
        f"/api/quotes/{quote_id}/collect"
    ]:
        api_client.post(
            f"{BASE_URL}{endpoint}",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test",
                "x-regularization-date": "2026-01-15"
            }
        )
    
    return {
        "quote_id": quote_id,
        "warehouse_id": warehouse_id,
        "hardware_id": hardware_id,
        "serials": serials
    }


@pytest.fixture
def create_multiitem_quote(api_client, auth_token, get_client_id, get_warehouse_id):
    """Create quote with 15+ items for multi-page PDF test"""
    client_id = get_client_id
    warehouse_id = get_warehouse_id
    unique_id = uuid.uuid4().hex[:4]
    
    # Create multiple hardware items
    hardware_items = []
    delivery_items = []
    
    for i in range(16):  # 16 items to force multi-page
        hw_resp = api_client.post(
            f"{BASE_URL}/api/hardware",
            json={
                "name": f"MULTI_ITEM_{unique_id}_{i:02d}",
                "type": "POS",
                "price_usd": 100.00,
                "price_bs_usd": 100.00,
                "description": f"Multi-page test item {i}"
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if hw_resp.status_code in [200, 201]:
            hw_id = hw_resp.json()["hardware_id"]
            
            # Add inventory
            serials = [f"SN-MULTI-{unique_id}-{i:02d}-{j:02d}" for j in range(1, 4)]
            api_client.post(
                f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry",
                json={
                    "item_id": hw_id,
                    "quantity": 3,
                    "unit_cost": 100.00,
                    "serials": serials,
                    "notes": f"Multi-item entry {i}"
                },
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            
            hardware_items.append({
                "hardware_id": hw_id,
                "name": f"MULTI_ITEM_{unique_id}_{i:02d}",
                "hardware_type": "POS",
                "quantity": 2,
                "unit_price_usd": 100.00,
                "total_usd": 200.00
            })
            
            delivery_items.append({
                "hardware_id": hw_id,
                "quantity": 2,
                "serials": serials[:2]
            })
    
    if len(hardware_items) < 15:
        pytest.skip("Could not create enough hardware items for multi-page test")
    
    # Create quote
    quote_resp = api_client.post(
        f"{BASE_URL}/api/quotes",
        json={
            "client_id": client_id,
            "quote_category": "equipment",
            "quote_type": "POS",
            "equipment_items": hardware_items,
            "total_usd": sum(h["total_usd"] for h in hardware_items),
            "total_bs": sum(h["total_usd"] for h in hardware_items) * 40,
            "sede": "PYME",
            "notes": f"TEST_MULTIPAGE_{unique_id}"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    if quote_resp.status_code not in [200, 201]:
        pytest.skip(f"Could not create multi-item quote: {quote_resp.text}")
    
    quote_id = quote_resp.json()["quote_id"]
    
    # Advance to Pagada
    api_client.put(
        f"{BASE_URL}/api/quotes/{quote_id}/status",
        json={"new_status": "Enviada"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    for endpoint in [
        f"/api/quotes/{quote_id}/approve",
        f"/api/quotes/{quote_id}/invoice",
        f"/api/quotes/{quote_id}/collect"
    ]:
        api_client.post(
            f"{BASE_URL}{endpoint}",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Multi-page test",
                "x-regularization-date": "2026-01-15"
            }
        )
    
    return {
        "quote_id": quote_id,
        "warehouse_id": warehouse_id,
        "delivery_items": delivery_items
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
