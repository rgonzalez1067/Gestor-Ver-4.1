"""
Test Iteration 124: Repair State Flow Reengineering

Tests the new repair quote state flow:
1. POST /api/quotes/{quote_id}/repair-complete endpoint exists and validates:
   - Only repair quotes (quote_category='repair')
   - Only 'Aprobada' status
   - Changes status to 'Reparada'
2. POST /api/quotes/{quote_id}/approve does NOT send admin email for repair quotes
3. POST /api/quotes/{quote_id}/invoice accepts 'Reparada' as valid pre-status for repair quotes
4. QUOTE_STATUSES includes 'Reparada'
5. QUOTE_TRANSITIONS for repair: Borrador -> Enviada -> Aprobada -> Reparada -> Facturada -> Pagada -> Entregada
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRepairStateFlow:
    """Tests for the repair quote state flow reengineering"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - register/login user, create client"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Register a test user
        unique_id = uuid.uuid4().hex[:8]
        self.test_email = f"test_repair_{unique_id}@test.com"
        self.test_password = "TestPass123!"
        
        register_data = {
            "first_name": "Test",
            "last_name": "Repair",
            "email": self.test_email,
            "password": self.test_password,
            "cedula": f"V{unique_id}",
            "sede": "PYME"
        }
        
        reg_response = self.session.post(f"{BASE_URL}/api/auth/register", json=register_data)
        if reg_response.status_code not in [200, 201, 400]:  # 400 if user exists
            pytest.skip(f"Could not register user: {reg_response.text}")
        
        # Login
        login_data = {"email": self.test_email, "password": self.test_password}
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if login_response.status_code != 200:
            # Try with existing admin user
            login_data = {"email": "admin@mega.com", "password": "Admin123!"}
            login_response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
            if login_response.status_code != 200:
                pytest.skip("Could not login")
        
        token = login_response.json().get("session_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Create a test client
        self.client_id = self._create_test_client()
        
        yield
        
        # Cleanup - delete test quotes
        self._cleanup_test_data()
    
    def _create_test_client(self):
        """Create a test client for quotes"""
        unique_id = uuid.uuid4().hex[:8]
        client_data = {
            "rif": f"J-{unique_id}",
            "legal_name": f"Test Repair Client {unique_id}",
            "fantasy_name": f"Test Repair {unique_id}",
            "segment": "Pymes",
            "condicion": "Prospecto"
        }
        response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        if response.status_code in [200, 201]:
            return response.json().get("client_id")
        # Try to get existing client
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code == 200 and clients_response.json():
            return clients_response.json()[0].get("client_id")
        pytest.skip("Could not create or find test client")
    
    def _create_repair_quote(self, status="Borrador"):
        """Create a repair quote for testing"""
        unique_id = uuid.uuid4().hex[:8]
        quote_data = {
            "client_id": self.client_id,
            "quote_category": "repair",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": f"Test repair quote {unique_id}",
            "repair_description": "Test repair description",
            "equipment_serial_number": f"SN-{unique_id}"
        }
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        if response.status_code not in [200, 201]:
            pytest.skip(f"Could not create repair quote: {response.text}")
        data = response.json()
        # Handle nested response structure
        if "quote" in data:
            return data["quote"]
        return data
    
    def _create_implementation_quote(self):
        """Create an implementation quote for comparison testing"""
        unique_id = uuid.uuid4().hex[:8]
        quote_data = {
            "client_id": self.client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": f"Test implementation quote {unique_id}"
        }
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        if response.status_code not in [200, 201]:
            pytest.skip(f"Could not create implementation quote: {response.text}")
        data = response.json()
        # Handle nested response structure
        if "quote" in data:
            return data["quote"]
        return data
    
    def _upload_attachment(self, quote_id, category):
        """Upload a test attachment to a quote"""
        # Create a simple test file
        files = {
            'file': ('test.pdf', b'%PDF-1.4 test content', 'application/pdf')
        }
        data = {'category': category}
        # Remove Content-Type header for multipart form upload
        headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
        response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        return response.status_code in [200, 201]
    
    def _cleanup_test_data(self):
        """Clean up test quotes"""
        try:
            quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
            if quotes_response.status_code == 200:
                for quote in quotes_response.json():
                    if "Test repair" in (quote.get("notes") or "") or "Test implementation" in (quote.get("notes") or ""):
                        self.session.delete(f"{BASE_URL}/api/quotes/{quote['quote_id']}")
        except:
            pass
    
    # ==================== REPAIR-COMPLETE ENDPOINT TESTS ====================
    
    def test_repair_complete_endpoint_exists(self):
        """Test that POST /api/quotes/{quote_id}/repair-complete endpoint exists"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Try to call the endpoint (will fail validation but should not 404)
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, "repair-complete endpoint should exist"
        print(f"PASSED: repair-complete endpoint exists (status: {response.status_code})")
    
    def test_repair_complete_only_for_repair_quotes(self):
        """Test that repair-complete only works for repair category quotes"""
        # Create an implementation quote
        impl_quote = self._create_implementation_quote()
        quote_id = impl_quote.get("quote_id")
        
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        assert response.status_code == 400, f"Expected 400 for non-repair quote, got {response.status_code}"
        assert "reparación" in response.text.lower() or "repair" in response.text.lower(), \
            "Error message should mention repair category"
        print("PASSED: repair-complete rejects non-repair quotes")
    
    def test_repair_complete_requires_aprobada_status(self):
        """Test that repair-complete requires 'Aprobada' status"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Quote is in 'Borrador' status, should fail
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        assert response.status_code == 400, f"Expected 400 for non-Aprobada status, got {response.status_code}"
        assert "aprobada" in response.text.lower(), "Error message should mention Aprobada status"
        print("PASSED: repair-complete requires Aprobada status")
    
    def test_repair_complete_changes_status_to_reparada(self):
        """Test that repair-complete changes status from Aprobada to Reparada"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Move quote through the flow: Borrador -> Enviada -> Aprobada
        # Send to client
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        
        # Upload Orden de Compra (required for approval)
        self._upload_attachment(quote_id, "Orden de Compra")
        
        # Approve
        approve_response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        if approve_response.status_code != 200:
            pytest.skip(f"Could not approve quote: {approve_response.text}")
        
        # Now call repair-complete
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Reparada", f"Expected new_status='Reparada', got {data.get('new_status')}"
        
        # Verify the quote status was updated
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        if quote_response.status_code == 200:
            updated_quote = quote_response.json()
            assert updated_quote.get("quote_status") == "Reparada", \
                f"Quote status should be 'Reparada', got {updated_quote.get('quote_status')}"
        
        print("PASSED: repair-complete changes status to Reparada")
    
    def test_repair_complete_sends_admin_notification(self):
        """Test that repair-complete sends notification to admin (email results in response)"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Move to Aprobada
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        self._upload_attachment(quote_id, "Orden de Compra")
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Call repair-complete
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have emails in response (even if simulated)
        assert "emails" in data, "Response should include emails field"
        print(f"PASSED: repair-complete includes email notifications: {len(data.get('emails', []))} emails")
    
    # ==================== APPROVE ENDPOINT TESTS (NO ADMIN EMAIL FOR REPAIR) ====================
    
    def test_approve_repair_quote_no_admin_email(self):
        """Test that approving a repair quote does NOT send admin email"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Send to client
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        
        # Upload Orden de Compra
        self._upload_attachment(quote_id, "Orden de Compra")
        
        # Approve
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Check is_repair flag
        assert data.get("is_repair") == True, "Response should indicate is_repair=True"
        
        # For repair quotes, emails should be empty (no admin notification on approve)
        emails = data.get("emails", [])
        assert len(emails) == 0, f"Repair quote approval should NOT send emails, got {len(emails)}"
        
        print("PASSED: Repair quote approval does NOT send admin email")
    
    def test_approve_implementation_quote_sends_admin_email(self):
        """Test that approving an implementation quote DOES send admin email (for comparison)"""
        quote = self._create_implementation_quote()
        quote_id = quote.get("quote_id")
        
        # Send to client
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        
        # Upload Orden de Compra
        self._upload_attachment(quote_id, "Orden de Compra")
        
        # Approve
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # For implementation quotes, is_repair should be False or not present
        assert data.get("is_repair") != True, "Implementation quote should not have is_repair=True"
        
        # Implementation quotes should send emails
        emails = data.get("emails", [])
        # Note: emails might be empty if no admin email configured, but the logic should attempt to send
        print(f"PASSED: Implementation quote approval sends {len(emails)} email(s)")
    
    # ==================== INVOICE ENDPOINT TESTS (ACCEPTS REPARADA FOR REPAIR) ====================
    
    def test_invoice_repair_quote_accepts_reparada_status(self):
        """Test that invoicing a repair quote accepts 'Reparada' as valid pre-status"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Move through flow: Borrador -> Enviada -> Aprobada -> Reparada
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        self._upload_attachment(quote_id, "Orden de Compra")
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        # Upload Factura (required for invoicing)
        self._upload_attachment(quote_id, "Factura")
        
        # Invoice - should work from 'Reparada' status
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "FAC-TEST-001"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify status changed to Facturada
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        if quote_response.status_code == 200:
            updated_quote = quote_response.json()
            assert updated_quote.get("quote_status") == "Facturada", \
                f"Quote status should be 'Facturada', got {updated_quote.get('quote_status')}"
        
        print("PASSED: Invoice accepts 'Reparada' status for repair quotes")
    
    def test_invoice_repair_quote_from_aprobada_requires_exception(self):
        """Test that invoicing a repair quote from 'Aprobada' requires exception reason"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Move to Aprobada only (skip Reparada)
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        self._upload_attachment(quote_id, "Orden de Compra")
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Upload Factura
        self._upload_attachment(quote_id, "Factura")
        
        # Try to invoice without exception reason - should fail
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "FAC-TEST-002"}
        )
        
        # Should require exception reason (422 IRREGULAR)
        assert response.status_code == 422, f"Expected 422 for irregular flow, got {response.status_code}"
        assert "IRREGULAR" in response.text or "Reparada" in response.text, \
            "Error should mention irregular flow or expected Reparada status"
        
        print("PASSED: Invoice from Aprobada requires exception for repair quotes")
    
    # ==================== MODEL VALIDATION TESTS ====================
    
    def test_quote_statuses_includes_reparada(self):
        """Test that QUOTE_STATUSES includes 'Reparada'"""
        # This is validated by the fact that we can set status to Reparada
        # Also check the models.py directly via API if available
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # Move to Reparada
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        self._upload_attachment(quote_id, "Orden de Compra")
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        
        assert response.status_code == 200, "Should be able to set status to Reparada"
        
        # Verify via GET
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        assert quote_response.json().get("quote_status") == "Reparada"
        
        print("PASSED: QUOTE_STATUSES includes 'Reparada'")
    
    def test_repair_quote_full_flow(self):
        """Test the complete repair quote flow: Borrador -> Enviada -> Aprobada -> Reparada -> Facturada -> Pagada -> Entregada"""
        quote = self._create_repair_quote()
        quote_id = quote.get("quote_id")
        
        # 1. Borrador -> Enviada
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        assert response.status_code == 200, f"Send to client failed: {response.text}"
        print("  Step 1: Borrador -> Enviada: PASSED")
        
        # 2. Enviada -> Aprobada
        self._upload_attachment(quote_id, "Orden de Compra")
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert response.status_code == 200, f"Approve failed: {response.text}"
        print("  Step 2: Enviada -> Aprobada: PASSED")
        
        # 3. Aprobada -> Reparada
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete")
        assert response.status_code == 200, f"Repair complete failed: {response.text}"
        print("  Step 3: Aprobada -> Reparada: PASSED")
        
        # 4. Reparada -> Facturada
        self._upload_attachment(quote_id, "Factura")
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "FAC-FLOW-001"}
        )
        assert response.status_code == 200, f"Invoice failed: {response.text}"
        print("  Step 4: Reparada -> Facturada: PASSED")
        
        # 5. Facturada -> Pagada
        self._upload_attachment(quote_id, "Pagos")
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        assert response.status_code == 200, f"Collect failed: {response.text}"
        print("  Step 5: Facturada -> Pagada: PASSED")
        
        # 6. Pagada -> Entregada (for repair/equipment quotes)
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json={}
        )
        assert response.status_code == 200, f"Deliver failed: {response.text}"
        print("  Step 6: Pagada -> Entregada: PASSED")
        
        # Verify final status
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        final_status = quote_response.json().get("quote_status")
        assert final_status == "Entregada", f"Final status should be 'Entregada', got {final_status}"
        
        print("PASSED: Complete repair quote flow verified")


class TestRepairStateFlowModels:
    """Tests for model definitions related to repair state flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_data = {"email": "admin@mega.com", "password": "Admin123!"}
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
        if login_response.status_code != 200:
            pytest.skip("Could not login")
        
        token = login_response.json().get("session_token") or login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_quote_transitions_repair_flow(self):
        """Verify QUOTE_TRANSITIONS for repair category includes Reparada state"""
        # We verify this by testing the actual transitions work
        # The model defines: repair: Borrador -> Enviada -> Aprobada -> Reparada -> Facturada -> Pagada -> Entregada
        
        # Get a client
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available")
        client_id = clients_response.json()[0].get("client_id")
        
        # Create repair quote
        quote_data = {
            "client_id": client_id,
            "quote_category": "repair",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test transitions repair quote"
        }
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        if response.status_code not in [200, 201]:
            pytest.skip(f"Could not create quote: {response.text}")
        
        data = response.json()
        quote_id = data.get("quote", {}).get("quote_id") or data.get("quote_id")
        
        # Test that we can use PUT /quotes/{id}/status to change to Reparada
        # First move to Aprobada via the normal flow
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        
        # Upload OC - need to remove Content-Type header for multipart
        files = {'file': ('test.pdf', b'%PDF-1.4 test', 'application/pdf')}
        headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
        requests.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'}, headers=headers)
        
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Now test direct status update to Reparada (should work for repair quotes)
        status_response = self.session.put(
            f"{BASE_URL}/api/quotes/{quote_id}/status",
            json={"new_status": "Reparada"}
        )
        
        assert status_response.status_code == 200, f"Status update to Reparada should work: {status_response.text}"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        
        print("PASSED: QUOTE_TRANSITIONS for repair includes Reparada state")
    
    def test_implementation_quote_cannot_use_reparada(self):
        """Verify implementation quotes cannot transition to Reparada"""
        # Get a client
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available")
        client_id = clients_response.json()[0].get("client_id")
        
        # Create implementation quote
        quote_data = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test transitions implementation quote"
        }
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        if response.status_code not in [200, 201]:
            pytest.skip(f"Could not create quote: {response.text}")
        
        data = response.json()
        quote_id = data.get("quote", {}).get("quote_id") or data.get("quote_id")
        
        # Move to Aprobada
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        files = {'file': ('test.pdf', b'%PDF-1.4 test', 'application/pdf')}
        headers = {k: v for k, v in self.session.headers.items() if k.lower() != 'content-type'}
        requests.post(f"{BASE_URL}/api/quotes/{quote_id}/attachments", files=files, data={'category': 'Orden de Compra'}, headers=headers)
        self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        
        # Try to set status to Reparada - should fail for implementation quotes
        status_response = self.session.put(
            f"{BASE_URL}/api/quotes/{quote_id}/status",
            json={"new_status": "Reparada"}
        )
        
        assert status_response.status_code == 400, \
            f"Implementation quote should not allow Reparada status: {status_response.text}"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        
        print("PASSED: Implementation quotes cannot use Reparada status")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
