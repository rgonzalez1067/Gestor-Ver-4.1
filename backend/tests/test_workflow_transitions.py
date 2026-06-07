# ruff: noqa
"""
Test workflow-based state transitions for quotations
Tests the evidence-based state transitions (Workflows) for the quotation system.

Tests cover:
1. POST /api/quotes/{quote_id}/approve - requires 'Orden de Compra' attachment
2. POST /api/quotes/{quote_id}/invoice - requires 'Factura' attachment, accepts invoice_number
3. POST /api/quotes/{quote_id}/collect - requires 'Pagos' attachment(s)
4. ATTACHMENT_CATEGORIES validation
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test_anexos@test.com"
TEST_PASSWORD = "Test1234!"

class TestWorkflowTransitions:
    """Tests for workflow-based state transitions requiring document uploads"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login", 
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.text}")
        
        self.token = login_response.json().get("session_token")
        self.auth_header = {"Authorization": f"Bearer {self.token}"}
        
        yield
    
    def _get(self, path):
        """GET request with auth"""
        return self.session.get(f"{BASE_URL}{path}", headers=self.auth_header)
    
    def _post_json(self, path, json_data=None):
        """POST request with JSON body"""
        headers = {**self.auth_header, "Content-Type": "application/json"}
        return self.session.post(f"{BASE_URL}{path}", json=json_data, headers=headers)
    
    def _post_form(self, path, data=None):
        """POST request with form data"""
        return self.session.post(f"{BASE_URL}{path}", data=data, headers=self.auth_header)
    
    def _post_file(self, path, files, data=None):
        """POST request with file upload (multipart/form-data)"""
        return self.session.post(f"{BASE_URL}{path}", files=files, data=data, headers=self.auth_header)
    
    def _put_json(self, path, json_data=None):
        """PUT request with JSON body"""
        headers = {**self.auth_header, "Content-Type": "application/json"}
        return self.session.put(f"{BASE_URL}{path}", json=json_data, headers=headers)
    
    def _delete(self, path):
        """DELETE request with auth"""
        return self.session.delete(f"{BASE_URL}{path}", headers=self.auth_header)
    
    def _get_client_id(self):
        """Get or create a client ID for tests"""
        clients_response = self._get("/api/clients")
        if clients_response.status_code == 200 and clients_response.json():
            return clients_response.json()[0]["client_id"]
        
        # Create a test client
        client_data = {
            "rif": f"J-TEST-{int(time.time())}",
            "legal_name": f"TEST_Workflow_Client_{int(time.time())}",
            "fantasy_name": "Test Workflow Company",
            "segment": "Pymes",
            "contact1": {"name": "Test", "phone": "1234567890", "email": "test@test.com"},
            "contact2": {"name": "Test2", "phone": "1234567890", "email": "test2@test.com"}
        }
        client_response = self._post_json("/api/clients", client_data)
        assert client_response.status_code == 200
        return client_response.json()["client_id"]
    
    def _create_quote(self, client_id):
        """Create a test quote"""
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self._post_json("/api/quotes", quote_data)
        assert quote_response.status_code == 200
        return quote_response.json()["quote_id"]
    
    def _upload_attachment(self, quote_id, category, filename='test.pdf'):
        """Upload an attachment to a quote"""
        files = {'file': (filename, b'Test file content for ' + category.encode(), 'application/pdf')}
        data = {'category': category}
        return self._post_file(f"/api/quotes/{quote_id}/attachments", files, data)
    
    def _move_to_enviada(self, quote_id):
        """Change quote status to Enviada"""
        return self._put_json(f"/api/quotes/{quote_id}/status", {"new_status": "Enviada"})
    
    def _move_to_aprobada(self, quote_id):
        """Move quote to Aprobada status (uploads OC and approves)"""
        self._move_to_enviada(quote_id)
        upload_resp = self._upload_attachment(quote_id, "Orden de Compra", "orden_compra.pdf")
        assert upload_resp.status_code == 200, f"Failed to upload OC: {upload_resp.text}"
        approve_resp = self._post_json(f"/api/quotes/{quote_id}/approve")
        assert approve_resp.status_code == 200, f"Failed to approve: {approve_resp.text}"
        return approve_resp
    
    def _move_to_facturada(self, quote_id, invoice_number=None):
        """Move quote to Facturada status"""
        self._move_to_aprobada(quote_id)
        upload_resp = self._upload_attachment(quote_id, "Factura", "factura.pdf")
        assert upload_resp.status_code == 200, f"Failed to upload Factura: {upload_resp.text}"
        data = {"invoice_number": invoice_number} if invoice_number else {}
        invoice_resp = self._post_form(f"/api/quotes/{quote_id}/invoice", data)
        assert invoice_resp.status_code == 200, f"Failed to invoice: {invoice_resp.text}"
        return invoice_resp
    
    # ==================== ATTACHMENT CATEGORIES TESTS ====================
    
    def test_attachment_categories_includes_five_categories(self):
        """Verify ATTACHMENT_CATEGORIES includes all 5 categories"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        expected_categories = ["Cotización", "Orden de Compra", "Factura", "Pagos", "Otros"]
        
        for category in expected_categories:
            upload_response = self._upload_attachment(quote_id, category, f'test_{category.replace(" ", "_")}.pdf')
            assert upload_response.status_code == 200, f"Category '{category}' should be valid. Response: {upload_response.text}"
        
        # Cleanup
        self._delete(f"/api/quotes/{quote_id}")
        print(f"✓ All 5 attachment categories are valid: {expected_categories}")
    
    def test_attachment_pagos_category_accepted(self):
        """Verify 'Pagos' is accepted as valid attachment category"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        upload_response = self._upload_attachment(quote_id, "Pagos", "comprobante_pago.pdf")
        
        assert upload_response.status_code == 200, f"'Pagos' category should be valid. Response: {upload_response.text}"
        assert upload_response.json().get("attachment", {}).get("category") == "Pagos"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ 'Pagos' category is accepted for attachments")
    
    def test_attachment_invalid_category_rejected(self):
        """Verify invalid attachment categories are rejected"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        files = {'file': ('test_invalid.txt', b'Test content', 'text/plain')}
        data = {'category': 'InvalidCategory'}
        upload_response = self._post_file(f"/api/quotes/{quote_id}/attachments", files, data)
        
        assert upload_response.status_code == 400, f"Invalid category should be rejected. Response: {upload_response.text}"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Invalid attachment categories are rejected with 400")
    
    # ==================== APPROVE ENDPOINT TESTS ====================
    
    def test_approve_returns_422_without_orden_compra(self):
        """POST /api/quotes/{quote_id}/approve returns 422 if no 'Orden de Compra' attachment"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Change status to Enviada
        status_response = self._move_to_enviada(quote_id)
        assert status_response.status_code == 200, f"Failed to change status: {status_response.text}"
        
        # Try to approve without Orden de Compra
        approve_response = self._post_json(f"/api/quotes/{quote_id}/approve")
        
        assert approve_response.status_code == 422, f"Expected 422, got {approve_response.status_code}. Response: {approve_response.text}"
        assert "Orden de Compra" in approve_response.json().get("detail", "")
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Approve returns 422 when 'Orden de Compra' attachment is missing")
    
    def test_approve_succeeds_with_orden_compra(self):
        """POST /api/quotes/{quote_id}/approve succeeds if 'Orden de Compra' attachment exists"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Enviada
        self._move_to_enviada(quote_id)
        
        # Upload Orden de Compra
        upload_response = self._upload_attachment(quote_id, "Orden de Compra", "orden_compra.pdf")
        assert upload_response.status_code == 200, f"Failed to upload: {upload_response.text}"
        
        # Approve
        approve_response = self._post_json(f"/api/quotes/{quote_id}/approve")
        
        assert approve_response.status_code == 200, f"Expected 200, got {approve_response.status_code}. Response: {approve_response.text}"
        assert approve_response.json().get("new_status") == "Aprobada"
        
        # Verify status changed
        get_response = self._get(f"/api/quotes/{quote_id}")
        assert get_response.json().get("quote_status") == "Aprobada"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Approve succeeds when 'Orden de Compra' attachment exists")
    
    # ==================== INVOICE ENDPOINT TESTS ====================
    
    def test_invoice_returns_422_without_factura(self):
        """POST /api/quotes/{quote_id}/invoice returns 422 if no 'Factura' attachment"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Aprobada (uploads OC and approves)
        self._move_to_aprobada(quote_id)
        
        # Try to invoice without Factura
        invoice_response = self._post_form(f"/api/quotes/{quote_id}/invoice")
        
        assert invoice_response.status_code == 422, f"Expected 422, got {invoice_response.status_code}. Response: {invoice_response.text}"
        assert "Factura" in invoice_response.json().get("detail", "")
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Invoice returns 422 when 'Factura' attachment is missing")
    
    def test_invoice_succeeds_with_factura(self):
        """POST /api/quotes/{quote_id}/invoice succeeds if 'Factura' attachment exists"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Aprobada
        self._move_to_aprobada(quote_id)
        
        # Upload Factura
        upload_response = self._upload_attachment(quote_id, "Factura", "factura.pdf")
        assert upload_response.status_code == 200
        
        # Invoice with invoice_number
        invoice_response = self._post_form(f"/api/quotes/{quote_id}/invoice", {"invoice_number": "FAC-2024-001"})
        
        assert invoice_response.status_code == 200, f"Expected 200, got {invoice_response.status_code}. Response: {invoice_response.text}"
        assert invoice_response.json().get("invoice_number") == "FAC-2024-001"
        
        # Verify status and invoice_number
        get_response = self._get(f"/api/quotes/{quote_id}")
        quote_data = get_response.json()
        assert quote_data.get("quote_status") == "Facturada"
        assert quote_data.get("invoice_number") == "FAC-2024-001"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Invoice succeeds with 'Factura' attachment and accepts invoice_number as form data")
    
    def test_invoice_accepts_form_data_invoice_number(self):
        """Verify invoice endpoint accepts invoice_number as Form data"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Aprobada
        self._move_to_aprobada(quote_id)
        
        # Upload Factura
        self._upload_attachment(quote_id, "Factura", "factura.pdf")
        
        # Test with specific invoice number
        test_invoice_number = f"TEST-INV-{int(time.time())}"
        invoice_response = self._post_form(f"/api/quotes/{quote_id}/invoice", {"invoice_number": test_invoice_number})
        
        assert invoice_response.status_code == 200
        assert invoice_response.json().get("invoice_number") == test_invoice_number
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Invoice endpoint correctly accepts invoice_number as Form data")
    
    # ==================== COLLECT ENDPOINT TESTS ====================
    
    def test_collect_returns_422_without_pagos(self):
        """POST /api/quotes/{quote_id}/collect returns 422 if no 'Pagos' attachment"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Facturada
        self._move_to_facturada(quote_id)
        
        # Try to collect without Pagos
        collect_response = self._post_json(f"/api/quotes/{quote_id}/collect")
        
        assert collect_response.status_code == 422, f"Expected 422, got {collect_response.status_code}. Response: {collect_response.text}"
        assert "pago" in collect_response.json().get("detail", "").lower()
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Collect returns 422 when 'Pagos' attachment is missing")
    
    def test_collect_succeeds_with_pagos(self):
        """POST /api/quotes/{quote_id}/collect succeeds if 'Pagos' attachment(s) exist"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Facturada
        self._move_to_facturada(quote_id)
        
        # Upload Pagos
        upload_response = self._upload_attachment(quote_id, "Pagos", "comprobante_pago.pdf")
        assert upload_response.status_code == 200
        
        # Collect
        collect_response = self._post_json(f"/api/quotes/{quote_id}/collect")
        
        assert collect_response.status_code == 200, f"Expected 200, got {collect_response.status_code}. Response: {collect_response.text}"
        
        # Verify status
        get_response = self._get(f"/api/quotes/{quote_id}")
        assert get_response.json().get("quote_status") == "Pagada"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Collect succeeds when 'Pagos' attachment(s) exist")
    
    def test_collect_succeeds_with_multiple_pagos(self):
        """Verify collect works with multiple payment proof attachments"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Facturada
        self._move_to_facturada(quote_id)
        
        # Upload multiple Pagos attachments
        upload1 = self._upload_attachment(quote_id, "Pagos", "pago1_transferencia.pdf")
        assert upload1.status_code == 200
        
        upload2 = self._upload_attachment(quote_id, "Pagos", "pago2_deposito.pdf")
        assert upload2.status_code == 200
        
        # Collect
        collect_response = self._post_json(f"/api/quotes/{quote_id}/collect")
        assert collect_response.status_code == 200
        
        # Verify attachments
        get_response = self._get(f"/api/quotes/{quote_id}/attachments")
        attachments = get_response.json().get("attachments", [])
        pagos_attachments = [a for a in attachments if a.get("category") == "Pagos"]
        assert len(pagos_attachments) >= 2, "Should have multiple Pagos attachments"
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Collect succeeds with multiple 'Pagos' attachments (multi-file support)")
    
    # ==================== STATE VALIDATION TESTS ====================
    
    def test_approve_requires_enviada_status(self):
        """Approve should only work for quotes in 'Enviada' status"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Try to approve from Borrador (should fail)
        approve_response = self._post_json(f"/api/quotes/{quote_id}/approve")
        assert approve_response.status_code == 400
        assert "Enviada" in approve_response.json().get("detail", "")
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Approve correctly validates quote must be in 'Enviada' status")
    
    def test_invoice_requires_aprobada_status(self):
        """Invoice should only work for quotes in 'Aprobada' status"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Enviada only
        self._move_to_enviada(quote_id)
        
        # Try to invoice from Enviada (should fail)
        invoice_response = self._post_form(f"/api/quotes/{quote_id}/invoice")
        assert invoice_response.status_code == 400
        assert "Aprobada" in invoice_response.json().get("detail", "")
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Invoice correctly validates quote must be in 'Aprobada' status")
    
    def test_collect_requires_facturada_status(self):
        """Collect should only work for quotes in 'Facturada' status"""
        client_id = self._get_client_id()
        quote_id = self._create_quote(client_id)
        
        # Move to Aprobada only
        self._move_to_aprobada(quote_id)
        
        # Try to collect from Aprobada (should fail)
        collect_response = self._post_json(f"/api/quotes/{quote_id}/collect")
        assert collect_response.status_code == 400
        assert "Facturada" in collect_response.json().get("detail", "")
        
        self._delete(f"/api/quotes/{quote_id}")
        print("✓ Collect correctly validates quote must be in 'Facturada' status")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
