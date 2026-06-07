# ruff: noqa
"""
Test Iteration 125: Taller Equipos Tracking and Repair Delivery Features
Tests the new taller_equipos collection tracking and repair delivery workflow.

Features tested:
1. POST /api/quotes/{quote_id}/approve for repair quotes creates records in taller_equipos
2. GET /api/quotes/{quote_id}/repair-delivery-prep returns equipment grouped by model
3. POST /api/quotes/{quote_id}/repair-deliver updates taller_equipos to 'Entregado'
4. GET /api/taller-equipos returns equipment list with filtering
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login with admin credentials
    login_res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@mega.com",
        "password": "Admin123!"
    })
    
    if login_res.status_code != 200:
        pytest.skip(f"Could not authenticate: {login_res.text}")
    
    # API returns session_token, not token
    token = login_res.json().get("session_token") or login_res.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    return session


@pytest.fixture(scope="module")
def test_client(auth_session):
    """Create a test client for all tests"""
    unique_id = uuid.uuid4().hex[:8]
    client_data = {
        "legal_name": f"TEST_TallerClient_{unique_id}",
        "fantasy_name": f"TEST_TallerClient_{unique_id}",
        "rif": f"J-{unique_id[:8]}",
        "address": "Test Address 123",
        "contacts": [{"full_name": "Test Contact", "email": "test@test.com", "phone": "0414-1234567"}]
    }
    res = auth_session.post(f"{BASE_URL}/api/clients", json=client_data)
    if res.status_code not in [200, 201]:
        pytest.skip(f"Could not create test client: {res.text}")
    
    client = res.json()
    yield client
    
    # Cleanup
    auth_session.delete(f"{BASE_URL}/api/clients/{client['client_id']}")


def create_repair_quote(session, client, serials):
    """Helper to create a repair quote with serials"""
    repair_models = [{
        "model_name": "Test Pinpad Model",
        "model_id": "test_hw_id",
        "quantity": len(serials),
        "serials": serials
    }]
    
    payload = {
        "client_id": client["client_id"],
        "cliente_nombre": client.get("legal_name") or client.get("fantasy_name", "Test Client"),
        "cliente_rif": client.get("rif", ""),
        "cliente_address": client.get("address", ""),
        "equipment_type": "Reparación",
        "repair_models": repair_models,
        "repair_description": "Test repair for taller_equipos testing",
        "notes": "Test repair quote"
    }
    
    res = session.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload)
    # The endpoint returns PDF, quote_id is in header
    quote_id = res.headers.get('X-Quote-ID')
    return res.status_code, quote_id


def upload_attachment(session, quote_id, category, filename="test.pdf"):
    """Helper to upload an attachment"""
    files = {'file': (filename, b'%PDF-1.4 fake pdf content', 'application/pdf')}
    data = {'category': category}
    headers = {k: v for k, v in session.headers.items() if k.lower() != 'content-type'}
    return requests.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data=data, headers=headers)


class TestTallerEquiposEndpoint:
    """Test GET /api/taller-equipos endpoint"""
    
    def test_01_taller_equipos_endpoint_exists(self, auth_session):
        """Test GET /api/taller-equipos endpoint exists and returns data"""
        res = auth_session.get(f"{BASE_URL}/api/taller-equipos")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "equipos" in data, "Response should contain 'equipos' key"
        assert "total" in data, "Response should contain 'total' key"
        print(f"SUCCESS: GET /api/taller-equipos returns {data['total']} equipos")
    
    def test_02_taller_equipos_filter_by_client(self, auth_session, test_client):
        """Test GET /api/taller-equipos with client_id filter"""
        res = auth_session.get(f"{BASE_URL}/api/taller-equipos?client_id={test_client['client_id']}")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "equipos" in data
        # All returned equipos should belong to this client
        for eq in data["equipos"]:
            assert eq.get("client_id") == test_client['client_id'], "Equipment should belong to filtered client"
        print(f"SUCCESS: Filter by client_id works, found {data['total']} equipos")
    
    def test_03_taller_equipos_filter_by_estatus(self, auth_session):
        """Test GET /api/taller-equipos with estatus filter"""
        res = auth_session.get(f"{BASE_URL}/api/taller-equipos?estatus=En%20reparación")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "equipos" in data
        # All returned equipos should have the filtered status
        for eq in data["equipos"]:
            assert eq.get("estatus") == "En reparación", "Equipment should have filtered status"
        print(f"SUCCESS: Filter by estatus works, found {data['total']} equipos 'En reparación'")


class TestRepairQuoteCreation:
    """Test repair quote creation with serials"""
    
    def test_04_create_repair_quote_with_serials(self, auth_session, test_client):
        """Test creating a repair quote with serials"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-TEST-{unique_id}-001", f"SN-TEST-{unique_id}-002"]
        
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        
        assert status_code == 200, f"Expected 200, got {status_code}"
        assert quote_id is not None, "Response should contain quote_id in header"
        
        # Verify quote details
        quote_res = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_res.status_code == 200
        quote = quote_res.json()
        assert quote.get("quote_category") == "repair", "Quote category should be 'repair'"
        
        print(f"SUCCESS: Created repair quote {quote.get('quote_number')} with {len(serials)} serials")


class TestApproveRepairQuoteCreatesTallerEquipos:
    """Test that approving a repair quote creates records in taller_equipos"""
    
    def test_05_approve_repair_quote_creates_taller_equipos(self, auth_session, test_client):
        """Test that approving a repair quote creates records in taller_equipos"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-APPROVE-{unique_id}-001", f"SN-APPROVE-{unique_id}-002", f"SN-APPROVE-{unique_id}-003"]
        
        # Create repair quote
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        assert status_code == 200 and quote_id, "Failed to create quote"
        
        # Send to client first (required step)
        send_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        assert send_res.status_code == 200, f"Failed to send to client: {send_res.text}"
        
        # Upload Orden de Compra (required for approval)
        oc_res = upload_attachment(auth_session, quote_id, "Orden de Compra", "orden_compra.pdf")
        assert oc_res.status_code in [200, 201], f"Failed to upload OC: {oc_res.text}"
        
        # Approve the quote
        approve_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert approve_res.status_code == 200, f"Failed to approve: {approve_res.text}"
        
        approve_data = approve_res.json()
        assert approve_data.get("is_repair") == True, "Response should indicate is_repair=True"
        
        # Verify taller_equipos records were created
        taller_res = auth_session.get(f"{BASE_URL}/api/taller-equipos?client_id={test_client['client_id']}")
        assert taller_res.status_code == 200
        taller_data = taller_res.json()
        
        # Find our serials in taller_equipos
        found_serials = [eq["serial"] for eq in taller_data["equipos"] if eq["serial"] in serials]
        assert len(found_serials) == len(serials), f"Expected {len(serials)} serials in taller_equipos, found {len(found_serials)}"
        
        # Verify status is 'En reparación'
        for eq in taller_data["equipos"]:
            if eq["serial"] in serials:
                assert eq["estatus"] == "En reparación", f"Serial {eq['serial']} should have estatus 'En reparación'"
                assert eq["quote_id"] == quote_id, "Equipment should reference the quote"
        
        print(f"SUCCESS: Approving repair quote created {len(serials)} records in taller_equipos with estatus 'En reparación'")


class TestRepairDeliveryPrep:
    """Test repair-delivery-prep endpoint"""
    
    def test_06_repair_delivery_prep_endpoint(self, auth_session, test_client):
        """Test GET /api/quotes/{quote_id}/repair-delivery-prep returns equipment grouped by model"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-PREP-{unique_id}-001", f"SN-PREP-{unique_id}-002"]
        
        # Create and approve repair quote
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        assert status_code == 200 and quote_id
        
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        upload_attachment(auth_session, quote_id, "Orden de Compra")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Test repair-delivery-prep
        prep_res = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/repair-delivery-prep")
        
        assert prep_res.status_code == 200, f"Expected 200, got {prep_res.status_code}: {prep_res.text}"
        prep_data = prep_res.json()
        
        # Verify response structure
        assert "quote_id" in prep_data, "Response should contain quote_id"
        assert "quote_number" in prep_data, "Response should contain quote_number"
        assert "client_id" in prep_data, "Response should contain client_id"
        assert "client_name" in prep_data, "Response should contain client_name"
        assert "modelos" in prep_data, "Response should contain modelos array"
        assert "total_equipos" in prep_data, "Response should contain total_equipos"
        
        # Verify modelos structure
        assert len(prep_data["modelos"]) > 0, "Should have at least one modelo"
        for modelo in prep_data["modelos"]:
            assert "modelo" in modelo, "Modelo should have 'modelo' field"
            assert "serials" in modelo, "Modelo should have 'serials' array"
            for serial_info in modelo["serials"]:
                assert "taller_equipo_id" in serial_info, "Serial should have taller_equipo_id"
                assert "serial" in serial_info, "Serial should have serial number"
        
        print(f"SUCCESS: repair-delivery-prep returns {prep_data['total_equipos']} equipos grouped in {len(prep_data['modelos'])} modelo(s)")
    
    def test_07_repair_delivery_prep_only_for_repair_quotes(self, auth_session, test_client):
        """Test that repair-delivery-prep only works for repair quotes"""
        # Create a non-repair quote (equipment quote)
        payload = {
            "client_id": test_client["client_id"],
            "cliente_nombre": test_client.get("legal_name", "Test"),
            "equipment_type": "Verifone",  # Not repair
            "items": [{"name": "Test Item", "quantity": 1, "unit_price_usd": 100, "total_usd": 100}],
            "notes": "Test equipment quote"
        }
        
        create_res = auth_session.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload)
        quote_id = create_res.headers.get('X-Quote-ID')
        if not quote_id:
            pytest.skip("Could not create equipment quote")
        
        # Try repair-delivery-prep on non-repair quote
        prep_res = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/repair-delivery-prep")
        
        assert prep_res.status_code == 400, f"Expected 400 for non-repair quote, got {prep_res.status_code}"
        assert "reparación" in prep_res.json().get("detail", "").lower(), "Error should mention repair"
        print("SUCCESS: repair-delivery-prep correctly rejects non-repair quotes")


class TestRepairDeliver:
    """Test repair-deliver endpoint"""
    
    def test_08_repair_deliver_updates_taller_equipos(self, auth_session, test_client):
        """Test POST /api/quotes/{quote_id}/repair-deliver updates taller_equipos to 'Entregado'"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-DELIVER-{unique_id}-001", f"SN-DELIVER-{unique_id}-002"]
        
        # Create quote
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        assert status_code == 200 and quote_id
        
        # Process through workflow
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        upload_attachment(auth_session, quote_id, "Orden de Compra")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        upload_attachment(auth_session, quote_id, "Factura", "factura.pdf")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        upload_attachment(auth_session, quote_id, "Pagos", "pago.pdf")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        
        # Get taller_equipo_ids for delivery
        prep_res = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/repair-delivery-prep")
        assert prep_res.status_code == 200
        prep_data = prep_res.json()
        
        # Collect only taller_equipo_ids for OUR serials (filter by serial name)
        selected_ids = []
        for modelo in prep_data["modelos"]:
            for serial_info in modelo["serials"]:
                if serial_info["serial"] in serials:
                    selected_ids.append(serial_info["taller_equipo_id"])
        
        assert len(selected_ids) == len(serials), f"Should find {len(serials)} equipment to deliver, found {len(selected_ids)}"
        
        # Deliver only our serials
        deliver_payload = {
            "selected_serials": selected_ids,
            "delivery_method": "personalizada",
            "receiver_name": "Test Receiver",
            "receiver_cedula": "V-12345678",
            "receiver_phone": "0414-1234567",
            "notes": "Test delivery"
        }
        
        deliver_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-deliver", json=deliver_payload)
        
        assert deliver_res.status_code == 200, f"Expected 200, got {deliver_res.status_code}: {deliver_res.text}"
        deliver_data = deliver_res.json()
        
        assert deliver_data.get("equipos_entregados") == len(serials), f"Should deliver {len(serials)} equipos"
        assert "hoja_ruta_url" in deliver_data, "Response should contain hoja_ruta_url (PDF)"
        
        # Verify taller_equipos status changed to 'Entregado'
        taller_res = auth_session.get(f"{BASE_URL}/api/taller-equipos?client_id={test_client['client_id']}&estatus=Entregado")
        assert taller_res.status_code == 200
        taller_data = taller_res.json()
        
        delivered_serials = [eq["serial"] for eq in taller_data["equipos"] if eq["serial"] in serials]
        assert len(delivered_serials) == len(serials), f"All {len(serials)} serials should be 'Entregado'"
        
        # Verify fecha_entrega is set
        for eq in taller_data["equipos"]:
            if eq["serial"] in serials:
                assert eq.get("fecha_entrega") is not None, "fecha_entrega should be set"
        
        # Verify quote status changed to 'Entregada'
        quote_res = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_res.status_code == 200
        assert quote_res.json().get("quote_status") == "Entregada", "Quote status should be 'Entregada'"
        
        print(f"SUCCESS: repair-deliver updated {len(serials)} equipos to 'Entregado' and generated PDF")
    
    def test_09_repair_deliver_requires_selected_serials(self, auth_session, test_client):
        """Test that repair-deliver requires at least one selected serial"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-EMPTY-{unique_id}-001"]
        
        # Create and process quote
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        assert status_code == 200 and quote_id
        
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        upload_attachment(auth_session, quote_id, "Orden de Compra")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        upload_attachment(auth_session, quote_id, "Factura")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        upload_attachment(auth_session, quote_id, "Pagos")
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        
        # Try to deliver with empty selected_serials
        deliver_payload = {
            "selected_serials": [],
            "delivery_method": "personalizada",
            "receiver_name": "Test"
        }
        
        deliver_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-deliver", json=deliver_payload)
        
        assert deliver_res.status_code == 400, f"Expected 400 for empty serials, got {deliver_res.status_code}"
        print("SUCCESS: repair-deliver correctly requires at least one selected serial")
    
    def test_10_repair_deliver_only_for_repair_quotes(self, auth_session, test_client):
        """Test that repair-deliver only works for repair quotes"""
        # Create a non-repair quote
        payload = {
            "client_id": test_client["client_id"],
            "cliente_nombre": test_client.get("legal_name", "Test"),
            "equipment_type": "Verifone",
            "items": [{"name": "Test Item", "quantity": 1, "unit_price_usd": 100, "total_usd": 100}],
            "notes": "Test"
        }
        
        create_res = auth_session.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload)
        quote_id = create_res.headers.get('X-Quote-ID')
        if not quote_id:
            pytest.skip("Could not create equipment quote")
        
        # Try repair-deliver on non-repair quote
        deliver_payload = {
            "selected_serials": ["fake_id"],
            "delivery_method": "personalizada",
            "receiver_name": "Test"
        }
        
        deliver_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-deliver", json=deliver_payload)
        
        assert deliver_res.status_code == 400, f"Expected 400 for non-repair quote, got {deliver_res.status_code}"
        print("SUCCESS: repair-deliver correctly rejects non-repair quotes")


class TestTallerEquiposFields:
    """Test taller_equipos record structure"""
    
    def test_11_taller_equipos_has_required_fields(self, auth_session, test_client):
        """Test that taller_equipos records have all required fields"""
        unique_id = uuid.uuid4().hex[:6]
        serials = [f"SN-FIELDS-{unique_id}-001"]
        
        # Create and approve repair quote
        status_code, quote_id = create_repair_quote(auth_session, test_client, serials)
        assert status_code == 200 and quote_id
        
        auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        upload_attachment(auth_session, quote_id, "Orden de Compra")
        approve_res = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert approve_res.status_code == 200, f"Approve failed: {approve_res.text}"
        
        # Get taller_equipos - search without estatus filter to find all
        taller_res = auth_session.get(f"{BASE_URL}/api/taller-equipos?client_id={test_client['client_id']}")
        assert taller_res.status_code == 200
        
        # Find our serial (it should be in "En reparación" status)
        our_equipo = None
        for eq in taller_res.json()["equipos"]:
            if eq["serial"] == serials[0]:
                our_equipo = eq
                break
        
        assert our_equipo is not None, f"Should find serial {serials[0]} in taller_equipos. Found: {[eq['serial'] for eq in taller_res.json()['equipos'][:5]]}"
        
        # Verify required fields
        required_fields = [
            "taller_equipo_id",
            "serial",
            "modelo",
            "client_id",
            "quote_id",
            "quote_number",
            "estatus",
            "fecha_ingreso"
        ]
        
        for field in required_fields:
            assert field in our_equipo, f"taller_equipo should have '{field}' field"
            assert our_equipo[field] is not None, f"'{field}' should not be None"
        
        # Verify values - status could be "En reparación" or "Entregado" depending on test order
        assert our_equipo["estatus"] in ["En reparación", "Entregado"], f"Unexpected status: {our_equipo['estatus']}"
        assert our_equipo["client_id"] == test_client["client_id"]
        assert our_equipo["quote_id"] == quote_id
        
        print(f"SUCCESS: taller_equipos record has all required fields: {required_fields}")


class TestIrregularFlow:
    """Test irregular flow handling"""
    
    def test_12_repair_deliver_returns_404_for_nonexistent_quote(self, auth_session):
        """Test that repair-deliver returns 404 for non-existent quote"""
        deliver_payload = {
            "selected_serials": ["fake_id"],
            "delivery_method": "personalizada",
            "receiver_name": "Test"
        }
        
        deliver_res = auth_session.post(f"{BASE_URL}/api/quotes/nonexistent_quote_id/repair-deliver", json=deliver_payload)
        
        assert deliver_res.status_code == 404, f"Expected 404 for non-existent quote, got {deliver_res.status_code}"
        print("SUCCESS: repair-deliver returns 404 for non-existent quote")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
