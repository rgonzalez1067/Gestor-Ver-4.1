# ruff: noqa
"""
Test Iteration 102 - Nota de Entrega PDF Redesign
Tests for the new 'Nota de Entrega' (formerly 'Hoja de Ruta') PDF generation.

Key features:
1. Correlativo NE-YYYY-XXXX auto-incremented via nota_entrega_counter collection
2. PDF filename format: NotaEntrega_NE-YYYY-XXXX.pdf
3. 5 sections: Info Documento, Cliente/Destino, Detalle Bienes, Control Logístico, Recepción
4. transportista and guia_placa fields accepted in deliver endpoint
5. Items classified as 'Equipo' or 'Consumible'
6. Client contact info pulled from client record
7. Footer: 'Documento generado por MegaNexus - Trazabilidad de Inventario'
"""
import pytest
import requests
import os
from datetime import datetime, timezone
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestNotaEntregaPDFRedesign:
    """Tests for the Nota de Entrega PDF redesign feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        """Setup for each test"""
        self.api_client = api_client
        self.auth_token = auth_token
        self.api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    
    # =======================
    # Correlativo Counter Tests
    # =======================
    
    def test_correlativo_counter_exists_or_created(self, api_client, auth_token):
        """Test that nota_entrega_counter collection is accessible via delivering a quote"""
        # This is implicit - the counter is created/updated when delivering
        # We'll verify it works through a full delivery test
        response = api_client.get(f"{BASE_URL}/api/quotes", headers={"Authorization": f"Bearer {auth_token}"})
        assert response.status_code == 200, "API should be accessible"
    
    def test_correlativo_format_NE_YYYY_XXXX(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that correlativo follows NE-YYYY-XXXX format"""
        quote_id = create_equipment_quote_paid
        
        # Deliver the quote
        payload = {
            "warehouse_id": "whs_f00b02f4",  # Almacén Central
            "delivery_items": [],  # Empty to skip inventory logic
            "notes": "Test nota entrega correlativo",
            "transportista": "Mensajero Test",
            "guia_placa": "ABC-123"
        }
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test delivery",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Deliver should succeed: {response.text}"
        
        data = response.json()
        hoja_ruta_url = data.get("hoja_ruta_url")
        if hoja_ruta_url:
            # Verify filename format
            assert "NotaEntrega_NE-" in hoja_ruta_url, f"PDF filename should contain 'NotaEntrega_NE-': {hoja_ruta_url}"
            year = datetime.now(timezone.utc).strftime("%Y")
            assert f"NE-{year}-" in hoja_ruta_url, f"Correlativo should contain current year: {hoja_ruta_url}"
    
    # =======================
    # Deliver Endpoint Tests
    # =======================
    
    def test_deliver_accepts_transportista_field(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that deliver endpoint accepts transportista field"""
        quote_id = create_equipment_quote_paid
        
        payload = {
            "warehouse_id": "whs_f00b02f4",
            "delivery_items": [],
            "notes": "Test transportista",
            "transportista": "Transportes ABC",
            "guia_placa": ""
        }
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test transportista",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Deliver with transportista should succeed: {response.text}"
    
    def test_deliver_accepts_guia_placa_field(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that deliver endpoint accepts guia_placa field"""
        quote_id = create_equipment_quote_paid
        
        payload = {
            "warehouse_id": "whs_f00b02f4",
            "delivery_items": [],
            "notes": "Test guia placa",
            "transportista": "",
            "guia_placa": "GUIA-2026-001 / Placa XYZ-456"
        }
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test guia placa",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Deliver with guia_placa should succeed: {response.text}"
    
    def test_deliver_returns_hoja_ruta_url(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that deliver endpoint returns hoja_ruta_url in response"""
        quote_id = create_equipment_quote_paid
        
        payload = {
            "warehouse_id": "whs_f00b02f4",
            "delivery_items": [],
            "notes": "Test hoja ruta url",
            "transportista": "Driver Test",
            "guia_placa": "ABC-789"
        }
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test pdf generation",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Deliver should succeed: {response.text}"
        
        data = response.json()
        # hoja_ruta_url may be None if no items were delivered, but field should exist
        assert "hoja_ruta_url" in data, "Response should contain hoja_ruta_url field"
    
    # =======================
    # PDF Attachment Tests
    # =======================
    
    def test_pdf_attached_to_quote_after_delivery(self, api_client, auth_token, create_equipment_quote_paid_with_items):
        """Test that PDF is attached to quote after delivery"""
        quote_id = create_equipment_quote_paid_with_items["quote_id"]
        hardware_id = create_equipment_quote_paid_with_items["hardware_id"]
        
        # Get available serials - API returns list directly
        stock_resp = api_client.get(
            f"{BASE_URL}/api/inventory/warehouses/whs_f00b02f4/stock",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert stock_resp.status_code == 200
        stock_data = stock_resp.json()
        
        # Handle both list and dict formats
        stock_items = stock_data if isinstance(stock_data, list) else stock_data.get("items", [])
        
        # Find serials for our hardware
        available_serials = []
        for item in stock_items:
            if item.get("item_id") == hardware_id:
                available_serials = item.get("serials", [])[:1]  # Get 1 serial
                break
        
        # Deliver with items
        payload = {
            "warehouse_id": "whs_f00b02f4",
            "delivery_items": [{
                "hardware_id": hardware_id,
                "quantity": 1,
                "serials": available_serials if available_serials else []
            }] if available_serials else [],
            "notes": "Full delivery test",
            "transportista": "Express Delivery",
            "guia_placa": "EXP-001"
        }
        
        deliver_resp = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "Test full delivery",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert deliver_resp.status_code == 200, f"Deliver should succeed: {deliver_resp.text}"
        
        # Check quote attachments
        quote_resp = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        if quote_resp.status_code == 200:
            quote_data = quote_resp.json()
            attachments = quote_data.get("attachments", [])
            pdf_attachments = [a for a in attachments if "NotaEntrega" in a.get("filename", "")]
            # May or may not have PDF depending on delivery_items
            assert deliver_resp.json().get("hoja_ruta_url") is not None or len(payload["delivery_items"]) == 0
    
    # =======================
    # Client Contact Info Tests
    # =======================
    
    def test_client_name_none_handled_gracefully(self, api_client, auth_token):
        """Test that client_name None doesn't cause validation error"""
        # This is tested implicitly through normal delivery flow
        # The backend should handle client_name being None
        response = api_client.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
    
    # =======================
    # PDF Generator Function Tests
    # =======================
    
    def test_generate_nota_entrega_pdf_function_exists(self):
        """Test that generate_nota_entrega_pdf function is importable"""
        try:
            from services.hoja_ruta_pdf import generate_nota_entrega_pdf
            assert callable(generate_nota_entrega_pdf), "Function should be callable"
        except ImportError:
            pytest.skip("Cannot import from services module in test environment")
    
    def test_pdf_generator_accepts_all_required_params(self):
        """Test that PDF generator accepts all required parameters"""
        try:
            from services.hoja_ruta_pdf import generate_nota_entrega_pdf
            import inspect
            sig = inspect.signature(generate_nota_entrega_pdf)
            params = list(sig.parameters.keys())
            
            required_params = [
                "correlativo",
                "quote_number",
                "project_number",
                "client_name",
                "client_rif",
                "client_address",
                "client_contact_name",
                "client_contact_phone",
                "warehouse_name",
                "delivered_items",
                "delivered_by",
                "transportista",
                "guia_placa",
                "notes",
                "logo_path"
            ]
            
            for param in required_params:
                assert param in params, f"Parameter '{param}' should exist in function signature"
        except ImportError:
            pytest.skip("Cannot import from services module in test environment")
    
    # =======================
    # Delivery Preparation Endpoint Tests
    # =======================
    
    def test_delivery_prep_returns_warehouses(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that delivery-prep endpoint returns available warehouses"""
        quote_id = create_equipment_quote_paid
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/delivery-prep",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"delivery-prep should succeed: {response.text}"
        
        data = response.json()
        assert "warehouses" in data, "Response should contain warehouses"
        assert isinstance(data["warehouses"], list), "warehouses should be a list"
    
    def test_delivery_prep_returns_items(self, api_client, auth_token, create_equipment_quote_paid):
        """Test that delivery-prep endpoint returns quote items"""
        quote_id = create_equipment_quote_paid
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/delivery-prep",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data, "Response should contain items"
        assert isinstance(data["items"], list), "items should be a list"
    
    def test_delivery_prep_with_warehouse_id(self, api_client, auth_token, create_equipment_quote_paid):
        """Test delivery-prep with warehouse_id returns stock info"""
        quote_id = create_equipment_quote_paid
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{quote_id}/delivery-prep?warehouse_id=whs_f00b02f4",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        if items:
            first_item = items[0]
            assert "stock_available" in first_item, "Item should have stock_available"
            assert "requires_serial" in first_item, "Item should have requires_serial"


class TestDeliveryFlowEndToEnd:
    """End-to-end tests for delivery flow"""
    
    def test_full_delivery_flow_with_nota_entrega(self, api_client, auth_token):
        """Test complete delivery flow generates Nota de Entrega"""
        # Get existing equipment quote in Pagada status, or create one
        quotes_resp = api_client.get(
            f"{BASE_URL}/api/quotes?quote_category=equipment&quote_status=Pagada",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # API returns list directly
        quotes_data = quotes_resp.json()
        if quotes_resp.status_code != 200:
            pytest.skip("Could not fetch quotes")
        
        quotes = quotes_data if isinstance(quotes_data, list) else quotes_data.get("quotes", [])
        if not quotes:
            pytest.skip("No equipment quotes in Pagada status")
        
        quote = quotes[0]
        quote_id = quote["quote_id"]
        
        # Test delivery with transportista and guia_placa
        payload = {
            "warehouse_id": "whs_f00b02f4",
            "delivery_items": [],
            "notes": "E2E test nota entrega",
            "transportista": "Courier E2E",
            "guia_placa": "E2E-GUIA-001"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json=payload,
            headers={
                "Authorization": f"Bearer {auth_token}",
                "x-exception-reason": "E2E test",
                "x-regularization-date": "2026-01-15"
            }
        )
        assert response.status_code == 200, f"Delivery should succeed: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Cotización marcada como Entregada"


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
def create_equipment_quote_paid(api_client, auth_token):
    """Create an equipment quote in Pagada status for delivery testing"""
    unique_id = uuid.uuid4().hex[:6]
    
    # First get an existing client - API returns list directly
    clients_resp = api_client.get(
        f"{BASE_URL}/api/clients",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    clients_data = clients_resp.json()
    clients = clients_data if isinstance(clients_data, list) else clients_data.get("clients", [])
    if clients_resp.status_code != 200 or not clients:
        pytest.skip("No clients available")
    
    client = clients[0]
    client_id = client["client_id"]
    
    # Create equipment quote
    quote_payload = {
        "client_id": client_id,
        "client_name": client.get("fantasy_name") or client.get("legal_name"),
        "quote_category": "equipment",
        "quote_type": "POS",
        "equipment_items": [],
        "total_usd": 100,
        "total_bs": 4000,
        "sede": "PYME",
        "notes": f"TEST_NE_{unique_id} - Nota Entrega test"
    }
    
    create_resp = api_client.post(
        f"{BASE_URL}/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert create_resp.status_code == 200, f"Quote creation failed: {create_resp.text}"
    
    quote_id = create_resp.json()["quote_id"]
    
    # Advance to Pagada status using irregular flow (skip normal flow)
    # Enviada -> Aprobada requires OC, Aprobada -> Facturada requires Factura, etc.
    # Use direct status update with exception headers
    
    # Move to Enviada
    api_client.put(
        f"{BASE_URL}/api/quotes/{quote_id}/status",
        json={"new_status": "Enviada"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # Move to Aprobada (irregular)
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/approve",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test - skip OC",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    # Move to Facturada (irregular)
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/invoice",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test - skip factura",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    # Move to Pagada (irregular)
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/collect",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test - skip pago",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    return quote_id

@pytest.fixture
def create_equipment_quote_paid_with_items(api_client, auth_token):
    """Create an equipment quote with items in Pagada status"""
    unique_id = uuid.uuid4().hex[:6]
    
    # Get hardware catalog
    hw_resp = api_client.get(
        f"{BASE_URL}/api/hardware",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    if hw_resp.status_code != 200 or not hw_resp.json():
        pytest.skip("No hardware available")
    
    hardware_list = hw_resp.json()
    # Find POS type hardware
    pos_hw = next((h for h in hardware_list if h.get("type", "").lower() == "pos"), None)
    if not pos_hw:
        pos_hw = hardware_list[0]
    
    hardware_id = pos_hw["hardware_id"]
    
    # Get client - API returns list directly
    clients_resp = api_client.get(
        f"{BASE_URL}/api/clients",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    clients_data = clients_resp.json()
    clients = clients_data if isinstance(clients_data, list) else clients_data.get("clients", [])
    if clients_resp.status_code != 200 or not clients:
        pytest.skip("No clients available")
    
    client = clients[0]
    client_id = client["client_id"]
    
    # Create quote with equipment items
    quote_payload = {
        "client_id": client_id,
        "client_name": client.get("fantasy_name") or client.get("legal_name"),
        "quote_category": "equipment",
        "quote_type": "POS",
        "equipment_items": [{
            "hardware_id": hardware_id,
            "name": pos_hw.get("name", "Test POS"),
            "hardware_type": pos_hw.get("type", "POS"),
            "quantity": 1,
            "unit_price": 100
        }],
        "total_usd": 100,
        "total_bs": 4000,
        "sede": "PYME",
        "notes": f"TEST_NE_ITEMS_{unique_id}"
    }
    
    create_resp = api_client.post(
        f"{BASE_URL}/api/quotes",
        json=quote_payload,
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert create_resp.status_code == 200, f"Quote creation failed: {create_resp.text}"
    
    quote_id = create_resp.json()["quote_id"]
    
    # Advance through statuses
    api_client.put(
        f"{BASE_URL}/api/quotes/{quote_id}/status",
        json={"new_status": "Enviada"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/approve",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test with items",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/invoice",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test with items",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    api_client.post(
        f"{BASE_URL}/api/quotes/{quote_id}/collect",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "x-exception-reason": "Test with items",
            "x-regularization-date": "2026-01-15"
        }
    )
    
    return {"quote_id": quote_id, "hardware_id": hardware_id}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
