"""
Iteration 87 - Testing 3 Critical Issues:
1. State machine flexibility for irregular quotes (allow invoice/collect even when 'Entregada')
2. Clients table action buttons overflow fix (DropdownMenu implementation)
3. RIF normalization (sanitize_rif removes hyphens, spaces, special chars)

Test Credentials: admin@gestor.com / Admin2026!
Base URL: https://audit-proyectos-v2.preview.emergentagent.com
"""
import pytest
import requests
import os
import time
import uuid

# Base URL from environment variable
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://audit-proyectos-v2.preview.emergentagent.com').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token for the test session"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gestor.com",
        "password": "Admin2026!"
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed with status {response.status_code}: {response.text}")
    data = response.json()
    return data.get("session_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers for authenticated requests"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def test_client_id(auth_headers):
    """Create a test client and return its ID"""
    # Clean RIF without hyphens for test
    test_rif = f"TEST_J{uuid.uuid4().hex[:9].upper()}"
    client_data = {
        "legal_name": "Test Client Iteration 87",
        "fantasy_name": "Test Client 87",
        "rif": test_rif,
        "address": "Test Address",
        "segment": "Pymes",
        "sucursal": "Principal",
        "contacts": [{"full_name": "Test Contact", "phone": "04121234567", "email": "test@test.com", "role": "Administrativo"}]
    }
    response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
    if response.status_code not in [200, 201]:
        pytest.skip(f"Failed to create test client: {response.text}")
    return response.json()["client_id"]


# ====================================================================================
# ISSUE #3: RIF NORMALIZATION TESTS
# sanitize_rif should strip all non-alphanumeric chars and uppercase
# ====================================================================================

class TestRIFNormalization:
    """Tests for Issue #3: RIF normalization (remove hyphens, spaces, special chars)"""

    def test_create_client_with_hyphenated_rif_sanitizes(self, auth_headers):
        """Create client with RIF 'J-98765432-1' should save as 'J987654321'"""
        # Use unique RIF
        unique_suffix = uuid.uuid4().hex[:4].upper()
        raw_rif = f"J-9876{unique_suffix}-1"
        expected_sanitized = f"J9876{unique_suffix}1"
        
        client_data = {
            "legal_name": f"Test RIF Sanitization {unique_suffix}",
            "fantasy_name": f"TestRIF{unique_suffix}",
            "rif": raw_rif,
            "address": "Test Address for RIF",
            "segment": "Pymes",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "04121111111", "email": "test@rif.com", "role": "Administrativo"}]
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed to create client: {response.text}"
        
        created_client = response.json()
        actual_rif = created_client["rif"]
        
        # Verify RIF was sanitized (no hyphens)
        assert "-" not in actual_rif, f"RIF should not contain hyphens: {actual_rif}"
        assert actual_rif == expected_sanitized, f"Expected '{expected_sanitized}', got '{actual_rif}'"
        print(f"✓ RIF sanitized correctly: '{raw_rif}' → '{actual_rif}'")
        
        # Store client_id for cleanup
        return created_client["client_id"]

    def test_create_client_with_spaces_in_rif(self, auth_headers):
        """Create client with RIF 'V - 11111111 - 1' should save as 'V111111111'"""
        unique_suffix = uuid.uuid4().hex[:4].upper()
        raw_rif = f"V - 1111{unique_suffix} - 1"
        expected_sanitized = f"V1111{unique_suffix}1"
        
        client_data = {
            "legal_name": f"Test RIF Spaces {unique_suffix}",
            "fantasy_name": f"TestSpaces{unique_suffix}",
            "rif": raw_rif,
            "address": "Test Address",
            "segment": "Pymes",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Contact", "phone": "04121111111", "email": "t@t.com", "role": "Administrativo"}]
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Failed to create client: {response.text}"
        
        created_client = response.json()
        actual_rif = created_client["rif"]
        
        # Verify spaces and hyphens removed
        assert " " not in actual_rif, f"RIF should not contain spaces: {actual_rif}"
        assert "-" not in actual_rif, f"RIF should not contain hyphens: {actual_rif}"
        assert actual_rif == expected_sanitized, f"Expected '{expected_sanitized}', got '{actual_rif}'"
        print(f"✓ RIF with spaces sanitized: '{raw_rif}' → '{actual_rif}'")
        
        return created_client["client_id"]

    def test_update_client_sanitizes_rif(self, auth_headers):
        """PUT /api/clients/{id} with RIF containing hyphens should sanitize"""
        # First create a client with clean RIF
        unique_suffix = uuid.uuid4().hex[:6].upper()
        clean_rif = f"G{unique_suffix}00"
        
        create_data = {
            "legal_name": f"Test Update RIF {unique_suffix}",
            "fantasy_name": f"UpdateTest{unique_suffix}",
            "rif": clean_rif,
            "address": "Test",
            "segment": "Corporativo",
            "sucursal": "Principal",
            "contacts": [{"full_name": "C", "phone": "0", "email": "c@c.com", "role": "Administrativo"}]
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/clients", json=create_data, headers=auth_headers)
        assert create_resp.status_code in [200, 201]
        client_id = create_resp.json()["client_id"]
        
        # Now update with hyphenated RIF
        update_suffix = uuid.uuid4().hex[:6].upper()
        hyphenated_rif = f"G-{update_suffix}-9"
        expected_sanitized = f"G{update_suffix}9"
        
        update_data = {
            "legal_name": f"Updated Test {update_suffix}",
            "fantasy_name": f"Updated{update_suffix}",
            "rif": hyphenated_rif,
            "address": "Updated Address",
            "segment": "Corporativo",
            "sucursal": "Principal",
            "contacts": [{"full_name": "C", "phone": "0", "email": "c@c.com", "role": "Administrativo"}]
        }
        
        update_resp = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_data, headers=auth_headers)
        assert update_resp.status_code == 200, f"Failed to update: {update_resp.text}"
        
        updated_client = update_resp.json()
        actual_rif = updated_client["rif"]
        
        assert "-" not in actual_rif, f"Updated RIF should not contain hyphens: {actual_rif}"
        assert actual_rif == expected_sanitized, f"Expected '{expected_sanitized}', got '{actual_rif}'"
        print(f"✓ RIF sanitized on update: '{hyphenated_rif}' → '{actual_rif}'")

    def test_lowercase_rif_uppercased(self, auth_headers):
        """Verify lowercase RIF letters are uppercased"""
        unique_suffix = uuid.uuid4().hex[:6]  # lowercase
        raw_rif = f"j-{unique_suffix}-1"  # lowercase j
        expected_sanitized = f"J{unique_suffix.upper()}1"  # uppercase
        
        client_data = {
            "legal_name": f"Test Lowercase RIF {unique_suffix}",
            "fantasy_name": f"LowerTest{unique_suffix}",
            "rif": raw_rif,
            "address": "Test",
            "segment": "Pymes",
            "sucursal": "Principal",
            "contacts": [{"full_name": "C", "phone": "0", "email": "c@c.com", "role": "Administrativo"}]
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
        assert response.status_code in [200, 201]
        
        created = response.json()
        actual_rif = created["rif"]
        
        assert actual_rif == expected_sanitized, f"Expected uppercase '{expected_sanitized}', got '{actual_rif}'"
        print(f"✓ RIF uppercased: '{raw_rif}' → '{actual_rif}'")


# ====================================================================================
# ISSUE #1: STATE MACHINE FLEXIBILITY FOR IRREGULAR QUOTES
# Test: Create quote → Deliver with exception → Invoice with exception → Collect
# ====================================================================================

class TestIrregularQuoteFlow:
    """Tests for Issue #1: State machine flexibility for irregular quotes"""

    def test_full_irregular_flow_entregada_to_invoice_to_collect(self, auth_headers, test_client_id):
        """
        Full test of irregular quote flow:
        1. Create equipment quote
        2. Mark as Entregada with exception (skipping normal flow)
        3. Invoice the 'Entregada' quote with exception
        4. Collect the 'Facturada' quote
        """
        # Step 1: Create an equipment quote
        quote_data = {
            "client_id": test_client_id,
            "quote_category": "equipment",
            "quote_type": "VPOS",
            "equipment_type": "POS (Dispositivo)",
            "services": [],
            "hardware": [],
            "equipment_items": [{
                "hardware_id": f"hwr_test_{uuid.uuid4().hex[:8]}",
                "name": "Test POS Device",
                "hardware_type": "Dispositivo",
                "unit_price_usd": 100.0,
                "quantity": 2,
                "total_usd": 200.0
            }],
            "notes": "Iteration 87 - Irregular flow test"
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_resp.status_code in [200, 201], f"Failed to create quote: {create_resp.text}"
        
        quote = create_resp.json()
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "Unknown")
        initial_status = quote.get("quote_status", "Borrador")
        
        print(f"✓ Quote created: {quote_number} (ID: {quote_id}), Status: {initial_status}")
        
        # Step 2: Mark as Entregada with exception (skipping Enviada → Aprobada → Facturada → Pagada flow)
        deliver_headers = {**auth_headers, "x-exception-reason": "Entrega anticipada por urgencia del cliente", "x-regularization-date": "2026-02-01"}
        
        deliver_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver", headers=deliver_headers)
        assert deliver_resp.status_code == 200, f"Failed to deliver quote: {deliver_resp.text}"
        
        deliver_result = deliver_resp.json()
        print(f"✓ Quote delivered with exception: {deliver_result.get('message')}")
        
        # Verify quote is now Entregada
        get_quote_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_quote_resp.status_code == 200
        quote_after_deliver = get_quote_resp.json()
        assert quote_after_deliver["quote_status"] == "Entregada", f"Expected 'Entregada', got '{quote_after_deliver['quote_status']}'"
        assert quote_after_deliver.get("is_irregular") == True, "Quote should be marked as irregular"
        print(f"✓ Quote status verified: Entregada, is_irregular: True")
        
        # Step 3: Upload Factura attachment (required for invoicing)
        # Create a simple PDF-like file for testing
        factura_file = ("test_factura.pdf", b"%PDF-1.4 Test Factura Content", "application/pdf")
        upload_data = {"category": "Factura"}
        upload_headers = {"Authorization": auth_headers["Authorization"]}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files={"file": factura_file},
            data=upload_data,
            headers=upload_headers
        )
        assert upload_resp.status_code == 200, f"Failed to upload Factura: {upload_resp.text}"
        print(f"✓ Factura attachment uploaded")
        
        # Step 4: Invoice the Entregada quote with exception
        invoice_headers = {**auth_headers, "x-exception-reason": "Facturación post-entrega por solicitud administrativa", "x-regularization-date": "2026-02-15"}
        
        # Use form data for invoice endpoint
        invoice_data = {
            "invoice_number": f"FAC-{quote_number}",
            "exception_reason": "Facturación post-entrega por solicitud administrativa",
            "regularization_date": "2026-02-15"
        }
        
        invoice_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice", data=invoice_data, headers={"Authorization": auth_headers["Authorization"]})
        assert invoice_resp.status_code == 200, f"Failed to invoice quote: {invoice_resp.text}"
        
        invoice_result = invoice_resp.json()
        print(f"✓ Quote invoiced with exception: {invoice_result.get('message')}")
        
        # Verify quote is now Facturada
        get_quote_resp2 = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_quote_resp2.status_code == 200
        quote_after_invoice = get_quote_resp2.json()
        assert quote_after_invoice["quote_status"] == "Facturada", f"Expected 'Facturada', got '{quote_after_invoice['quote_status']}'"
        print(f"✓ Quote status after invoice: Facturada")
        
        # Step 5: Upload Pagos attachment (required for collect)
        pagos_file = ("test_pago.pdf", b"%PDF-1.4 Test Pago Content", "application/pdf")
        pagos_data = {"category": "Pagos"}
        
        pagos_resp = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files={"file": pagos_file},
            data=pagos_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )
        assert pagos_resp.status_code == 200, f"Failed to upload Pagos: {pagos_resp.text}"
        print(f"✓ Pagos attachment uploaded")
        
        # Step 6: Collect (mark as Pagada) - this should work normally since quote is now Facturada
        collect_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/collect", headers=auth_headers)
        assert collect_resp.status_code == 200, f"Failed to collect quote: {collect_resp.text}"
        
        collect_result = collect_resp.json()
        print(f"✓ Quote collected: {collect_result.get('message')}")
        
        # Verify final status is Pagada
        get_quote_resp3 = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert get_quote_resp3.status_code == 200
        quote_final = get_quote_resp3.json()
        assert quote_final["quote_status"] == "Pagada", f"Expected 'Pagada', got '{quote_final['quote_status']}'"
        
        # Verify irregular_exceptions array has entries
        irregular_exceptions = quote_final.get("irregular_exceptions", [])
        assert len(irregular_exceptions) >= 2, f"Expected at least 2 irregular exceptions, got {len(irregular_exceptions)}"
        
        actions_logged = [exc.get("action") for exc in irregular_exceptions]
        assert "deliver" in actions_logged, "Missing 'deliver' action in irregular_exceptions"
        assert "invoice" in actions_logged, "Missing 'invoice' action in irregular_exceptions"
        
        print(f"✓ FULL IRREGULAR FLOW COMPLETED: Borrador → Entregada → Facturada → Pagada")
        print(f"  Quote: {quote_number}")
        print(f"  Irregular exceptions logged: {actions_logged}")

    def test_deliver_without_exception_reason_fails(self, auth_headers, test_client_id):
        """Deliver from non-Pagada status without exception reason should fail"""
        # Create quote
        quote_data = {
            "client_id": test_client_id,
            "quote_category": "equipment",
            "quote_type": "VPOS",
            "equipment_type": "POS (Dispositivo)",
            "services": [],
            "hardware": [],
            "equipment_items": [{"hardware_id": f"hwr_test_{uuid.uuid4().hex[:8]}", "name": "Test Device", "hardware_type": "Dispositivo", "unit_price_usd": 50.0, "quantity": 1, "total_usd": 50.0}],
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_resp.status_code in [200, 201]
        quote_id = create_resp.json()["quote_id"]
        
        # Try to deliver without exception headers (should fail since quote is in Borrador, not Pagada)
        deliver_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver", headers=auth_headers)
        assert deliver_resp.status_code == 422, f"Expected 422 for missing exception, got {deliver_resp.status_code}"
        
        error_detail = deliver_resp.json().get("detail", "")
        assert "IRREGULAR" in error_detail or "motivo" in error_detail.lower(), f"Expected irregular error, got: {error_detail}"
        print(f"✓ Deliver without exception correctly rejected: {error_detail}")

    def test_invoice_without_factura_attachment_fails(self, auth_headers, test_client_id):
        """Invoice action without Factura attachment should fail"""
        # Create quote
        quote_data = {
            "client_id": test_client_id,
            "quote_category": "equipment",
            "quote_type": "VPOS",
            "equipment_type": "Accesorio",
            "services": [],
            "hardware": [],
            "equipment_items": [{"hardware_id": f"hwr_test_{uuid.uuid4().hex[:8]}", "name": "Accessory", "hardware_type": "Accesorio", "unit_price_usd": 25.0, "quantity": 1, "total_usd": 25.0}],
        }
        
        create_resp = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_resp.status_code in [200, 201]
        quote_id = create_resp.json()["quote_id"]
        
        # First deliver with exception
        deliver_headers = {**auth_headers, "x-exception-reason": "Test", "x-regularization-date": "2026-01-01"}
        deliver_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver", headers=deliver_headers)
        assert deliver_resp.status_code == 200
        
        # Try to invoice without uploading Factura attachment
        invoice_data = {"invoice_number": "FAC-TEST", "exception_reason": "Test", "regularization_date": "2026-01-01"}
        invoice_resp = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice", data=invoice_data, headers={"Authorization": auth_headers["Authorization"]})
        
        assert invoice_resp.status_code == 422, f"Expected 422, got {invoice_resp.status_code}"
        error = invoice_resp.json().get("detail", "")
        assert "Factura" in error, f"Expected Factura error, got: {error}"
        print(f"✓ Invoice without Factura attachment correctly rejected: {error}")


# ====================================================================================
# ISSUE #2: CLIENTS TABLE ACTIONS VERIFICATION (Backend-side)
# Note: UI verification will be done via Playwright
# ====================================================================================

class TestClientsEndpoints:
    """Tests for clients endpoints that support the UI actions"""

    def test_get_clients_returns_list(self, auth_headers):
        """GET /api/clients should return client list"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        clients = response.json()
        assert isinstance(clients, list), "Expected list of clients"
        print(f"✓ GET /api/clients returned {len(clients)} clients")

    def test_get_client_by_id(self, auth_headers, test_client_id):
        """GET /api/clients/{id} should return single client"""
        response = requests.get(f"{BASE_URL}/api/clients/{test_client_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        client = response.json()
        assert client["client_id"] == test_client_id
        print(f"✓ GET /api/clients/{test_client_id} returned client: {client.get('legal_name')}")

    def test_get_client_logs_empty_initially(self, auth_headers, test_client_id):
        """GET /api/clients/{id}/logs should return empty list for new client"""
        response = requests.get(f"{BASE_URL}/api/clients/{test_client_id}/logs", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        logs = response.json()
        assert isinstance(logs, list), "Expected list of logs"
        print(f"✓ GET client logs returned {len(logs)} entries")

    def test_create_client_log(self, auth_headers, test_client_id):
        """POST /api/clients/{id}/logs should create a log entry"""
        log_data = {
            "client_id": test_client_id,
            "detail": "Test log entry for iteration 87",
            "action": "Follow up on test",
            "follow_up_date": "2026-02-01"
        }
        response = requests.post(f"{BASE_URL}/api/clients/{test_client_id}/logs", json=log_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        log = response.json()
        assert "log_id" in log
        assert log["detail"] == log_data["detail"]
        print(f"✓ Created client log: {log['log_id']}")


# ====================================================================================
# HEALTH CHECK & AUTH
# ====================================================================================

class TestHealthAndAuth:
    """Basic health checks"""

    def test_auth_login(self):
        """Test login endpoint works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@gestor.com",
            "password": "Admin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data or "token" in data
        print(f"✓ Authentication successful")

    def test_quotes_endpoint_accessible(self, auth_headers):
        """Test quotes endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        print(f"✓ Quotes endpoint accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
