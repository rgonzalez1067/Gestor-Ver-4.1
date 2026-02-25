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
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.text}")
        
        self.token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        # Cleanup: No specific cleanup needed - quotes are preserved for other tests
    
    # ==================== ATTACHMENT CATEGORIES TESTS ====================
    
    def test_attachment_categories_includes_five_categories(self):
        """Verify ATTACHMENT_CATEGORIES includes all 5 categories"""
        # Create a test quote first to test attachment upload
        # Get a client ID for creating quotes
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            # Create a test client
            client_data = {
                "rif": f"J-TEST-{int(time.time())}",
                "legal_name": f"TEST_Workflow_Client_{int(time.time())}",
                "fantasy_name": "Test Workflow Company",
                "segment": "Pymes",
                "contact1": {"name": "Test", "phone": "1234567890", "email": "test@test.com"},
                "contact2": {"name": "Test2", "phone": "1234567890", "email": "test2@test.com"}
            }
            client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
            assert client_response.status_code == 200
            client_id = client_response.json()["client_id"]
        else:
            client_id = clients_response.json()[0]["client_id"]
        
        # Create a test quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Test each of the 5 categories
        expected_categories = ["Cotización", "Orden de Compra", "Factura", "Pagos", "Otros"]
        
        for category in expected_categories:
            # Upload a test file with each category
            files = {
                'file': (f'test_{category.replace(" ", "_")}.txt', b'Test file content', 'text/plain')
            }
            data = {'category': category}
            
            upload_response = self.session.post(
                f"{BASE_URL}/api/quotes/{quote_id}/attachments",
                files=files,
                data=data
            )
            
            # Should accept all 5 categories
            assert upload_response.status_code == 200, f"Category '{category}' should be valid. Response: {upload_response.text}"
        
        # Cleanup test quote
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print(f"✓ All 5 attachment categories are valid: {expected_categories}")
    
    def test_attachment_pagos_category_accepted(self):
        """Verify 'Pagos' is accepted as valid attachment category"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create a test quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Upload with 'Pagos' category
        files = {
            'file': ('comprobante_pago.pdf', b'Test payment proof', 'application/pdf')
        }
        data = {'category': 'Pagos'}
        
        upload_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == 200, f"'Pagos' category should be valid. Response: {upload_response.text}"
        assert upload_response.json().get("attachment", {}).get("category") == "Pagos"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ 'Pagos' category is accepted for attachments")
    
    def test_attachment_invalid_category_rejected(self):
        """Verify invalid attachment categories are rejected"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create a test quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Try to upload with invalid category
        files = {
            'file': ('test_invalid.txt', b'Test content', 'text/plain')
        }
        data = {'category': 'InvalidCategory'}
        
        upload_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data
        )
        
        assert upload_response.status_code == 400, f"Invalid category should be rejected. Response: {upload_response.text}"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Invalid attachment categories are rejected with 400")
    
    # ==================== APPROVE ENDPOINT TESTS ====================
    
    def test_approve_returns_422_without_orden_compra(self):
        """POST /api/quotes/{quote_id}/approve returns 422 if no 'Orden de Compra' attachment"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create a test quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Change status to Enviada (required state before approve)
        status_response = self.session.put(
            f"{BASE_URL}/api/quotes/{quote_id}/status",
            json={"new_status": "Enviada"}
        )
        assert status_response.status_code == 200, f"Failed to change status to Enviada: {status_response.text}"
        
        # Try to approve without Orden de Compra attachment
        approve_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        assert approve_response.status_code == 422, f"Expected 422, got {approve_response.status_code}. Response: {approve_response.text}"
        assert "Orden de Compra" in approve_response.json().get("detail", "")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Approve returns 422 when 'Orden de Compra' attachment is missing")
    
    def test_approve_succeeds_with_orden_compra(self):
        """POST /api/quotes/{quote_id}/approve succeeds if 'Orden de Compra' attachment exists"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create a test quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Change status to Enviada
        status_response = self.session.put(
            f"{BASE_URL}/api/quotes/{quote_id}/status",
            json={"new_status": "Enviada"}
        )
        assert status_response.status_code == 200
        
        # Upload Orden de Compra attachment
        files = {
            'file': ('orden_compra.pdf', b'Purchase order content', 'application/pdf')
        }
        data = {'category': 'Orden de Compra'}
        
        upload_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data
        )
        assert upload_response.status_code == 200, f"Failed to upload Orden de Compra: {upload_response.text}"
        
        # Now approve should succeed
        approve_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        assert approve_response.status_code == 200, f"Expected 200, got {approve_response.status_code}. Response: {approve_response.text}"
        assert approve_response.json().get("new_status") == "Aprobada"
        
        # Verify quote status changed
        get_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert get_response.status_code == 200
        assert get_response.json().get("quote_status") == "Aprobada"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Approve succeeds when 'Orden de Compra' attachment exists")
    
    # ==================== INVOICE ENDPOINT TESTS ====================
    
    def test_invoice_returns_422_without_factura(self):
        """POST /api/quotes/{quote_id}/invoice returns 422 if no 'Factura' attachment"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote, set to Enviada, add Orden de Compra, approve
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Change status to Enviada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Upload Orden de Compra and approve
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Try to invoice without Factura attachment
        invoice_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        
        assert invoice_response.status_code == 422, f"Expected 422, got {invoice_response.status_code}. Response: {invoice_response.text}"
        assert "Factura" in invoice_response.json().get("detail", "")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Invoice returns 422 when 'Factura' attachment is missing")
    
    def test_invoice_succeeds_with_factura(self):
        """POST /api/quotes/{quote_id}/invoice succeeds if 'Factura' attachment exists"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote, move to Aprobada status
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Change status to Enviada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Upload Orden de Compra and approve
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        approve_resp = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert approve_resp.status_code == 200, f"Approve failed: {approve_resp.text}"
        
        # Upload Factura attachment
        files = {'file': ('factura.pdf', b'Invoice document content', 'application/pdf')}
        upload_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data={'category': 'Factura'}
        )
        assert upload_response.status_code == 200
        
        # Invoice with invoice_number
        invoice_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "FAC-2024-001"}
        )
        
        assert invoice_response.status_code == 200, f"Expected 200, got {invoice_response.status_code}. Response: {invoice_response.text}"
        assert invoice_response.json().get("invoice_number") == "FAC-2024-001"
        
        # Verify quote status and invoice_number
        get_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert get_response.status_code == 200
        quote_data = get_response.json()
        assert quote_data.get("quote_status") == "Facturada"
        assert quote_data.get("invoice_number") == "FAC-2024-001"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Invoice succeeds with 'Factura' attachment and accepts invoice_number as form data")
    
    def test_invoice_accepts_form_data_invoice_number(self):
        """Verify invoice endpoint accepts invoice_number as Form data"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote, move to Aprobada status
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Change status to Enviada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Upload Orden de Compra and approve
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Upload Factura
        files = {'file': ('factura.pdf', b'Invoice document', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Factura'})
        
        # Test with specific invoice number
        test_invoice_number = f"TEST-INV-{int(time.time())}"
        invoice_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": test_invoice_number}
        )
        
        assert invoice_response.status_code == 200
        assert invoice_response.json().get("invoice_number") == test_invoice_number
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Invoice endpoint correctly accepts invoice_number as Form data")
    
    # ==================== COLLECT ENDPOINT TESTS ====================
    
    def test_collect_returns_422_without_pagos(self):
        """POST /api/quotes/{quote_id}/collect returns 422 if no 'Pagos' attachment"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote and move through states to Facturada
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Move to Enviada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Upload Orden de Compra and approve
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Upload Factura and invoice
        files = {'file': ('factura.pdf', b'Invoice document', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Factura'})
        invoice_resp = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        assert invoice_resp.status_code == 200
        
        # Try to collect without Pagos attachment
        collect_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        
        assert collect_response.status_code == 422, f"Expected 422, got {collect_response.status_code}. Response: {collect_response.text}"
        assert "pago" in collect_response.json().get("detail", "").lower()
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Collect returns 422 when 'Pagos' attachment is missing")
    
    def test_collect_succeeds_with_pagos(self):
        """POST /api/quotes/{quote_id}/collect succeeds if 'Pagos' attachment(s) exist"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote and move through states
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Move to Enviada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Upload Orden de Compra and approve
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Upload Factura and invoice
        files = {'file': ('factura.pdf', b'Invoice document', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Factura'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        
        # Upload Pagos attachment
        files = {'file': ('comprobante_pago.pdf', b'Payment proof content', 'application/pdf')}
        upload_response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data={'category': 'Pagos'}
        )
        assert upload_response.status_code == 200
        
        # Now collect should succeed
        collect_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        
        assert collect_response.status_code == 200, f"Expected 200, got {collect_response.status_code}. Response: {collect_response.text}"
        
        # Verify quote status changed to Pagada
        get_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert get_response.status_code == 200
        assert get_response.json().get("quote_status") == "Pagada"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Collect succeeds when 'Pagos' attachment(s) exist")
    
    def test_collect_succeeds_with_multiple_pagos(self):
        """Verify collect works with multiple payment proof attachments"""
        # Get a client ID
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote and move through states
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Move through workflow states
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        files = {'file': ('orden_compra.pdf', b'Purchase order', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        files = {'file': ('factura.pdf', b'Invoice', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Factura'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        
        # Upload multiple Pagos attachments
        files1 = {'file': ('pago1_transferencia.pdf', b'Payment 1', 'application/pdf')}
        upload1 = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files1, data={'category': 'Pagos'})
        assert upload1.status_code == 200
        
        files2 = {'file': ('pago2_deposito.pdf', b'Payment 2', 'application/pdf')}
        upload2 = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files2, data={'category': 'Pagos'})
        assert upload2.status_code == 200
        
        # Collect should succeed with multiple payment proofs
        collect_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        assert collect_response.status_code == 200
        
        # Verify attachments count
        get_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}/attachments")
        assert get_response.status_code == 200
        attachments = get_response.json().get("attachments", [])
        pagos_attachments = [a for a in attachments if a.get("category") == "Pagos"]
        assert len(pagos_attachments) >= 2, "Should have multiple Pagos attachments"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Collect succeeds with multiple 'Pagos' attachments (multi-file support)")
    
    # ==================== STATE VALIDATION TESTS ====================
    
    def test_approve_requires_enviada_status(self):
        """Approve should only work for quotes in 'Enviada' status"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote (stays in Borrador)
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_response.status_code == 200
        quote_id = quote_response.json()["quote_id"]
        
        # Try to approve from Borrador status (should fail)
        approve_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert approve_response.status_code == 400
        assert "Enviada" in approve_response.json().get("detail", "")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Approve correctly validates quote must be in 'Enviada' status")
    
    def test_invoice_requires_aprobada_status(self):
        """Invoice should only work for quotes in 'Aprobada' status"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote in Enviada status
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        quote_id = quote_response.json()["quote_id"]
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        
        # Try to invoice from Enviada status (should fail - needs to be Aprobada)
        invoice_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/invoice")
        assert invoice_response.status_code == 400
        assert "Aprobada" in invoice_response.json().get("detail", "")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Invoice correctly validates quote must be in 'Aprobada' status")
    
    def test_collect_requires_facturada_status(self):
        """Collect should only work for quotes in 'Facturada' status"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client_id = clients_response.json()[0]["client_id"]
        
        # Create quote and move to Aprobada
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_response = self.session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        quote_id = quote_response.json()["quote_id"]
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={"new_status": "Enviada"})
        files = {'file': ('oc.pdf', b'OC', 'application/pdf')}
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'})
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Try to collect from Aprobada status (should fail - needs to be Facturada)
        collect_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        assert collect_response.status_code == 400
        assert "Facturada" in collect_response.json().get("detail", "")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        print("✓ Collect correctly validates quote must be in 'Facturada' status")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
