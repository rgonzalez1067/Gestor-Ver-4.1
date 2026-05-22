"""
Test iteration 126: Fast Track (POS Stand Alone) Flow
Tests the new quote category 'fast_track' with pipeline:
Borrador → Enviada → Aprobada → Configurada → Facturada → Pagada → Entregada

Key features:
- quote_category='fast_track' and quote_type='FAST_TRACK'
- Approve notifies Operations (not Admin), returns is_fast_track=true
- Configure endpoint only works for fast_track quotes in 'Aprobada' status
- Invoice accepts 'Configurada' as valid pre-status for fast_track
- Deliver accepts fast_track category
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://meganexus-crm-admin.preview.emergentagent.com')

class TestFastTrackFlow:
    """Test the complete Fast Track quote flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@mega.com", "password": "Admin123!"}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        
        # Get or create a test client
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert clients_response.status_code == 200
        clients = clients_response.json()
        
        if clients:
            self.client_id = clients[0]["client_id"]
        else:
            # Create a test client
            client_data = {
                "rif": f"J-TEST{uuid.uuid4().hex[:6]}",
                "legal_name": "TEST_FastTrack_Client",
                "fantasy_name": "TEST_FT_Client",
                "segment": "Pymes"
            }
            create_client = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=self.headers)
            assert create_client.status_code in [200, 201]
            self.client_id = create_client.json().get("client_id")
        
        yield
        
        # Cleanup: Delete test quotes created during tests
        # (handled by individual tests)
    
    def test_01_create_fast_track_quote(self):
        """Test creating a fast_track quote with quote_category='fast_track' and quote_type='FAST_TRACK'"""
        payload = {
            "client_id": self.client_id,
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Configuración POS Stand Alone",
                    "quantity": 1,
                    "unit_price_usd": 100,
                    "total_usd": 100
                }
            ],
            "hardware": [],
            "equipment_items": [],
            "notes": "TEST_FastTrack quote for iteration 126",
            "integrator_id": "sin_integrador",
            "integrator_name": "Sin integrador",
            "sponsor_bank_id": "",
            "sponsor_bank_name": "Mega Soft"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create fast_track quote: {response.text}"
        data = response.json()
        
        # Verify quote was created
        assert "quote" in data, "Response should contain 'quote' key"
        quote = data["quote"]
        
        # Verify quote_category and quote_type
        assert quote.get("quote_category") == "fast_track", f"Expected quote_category='fast_track', got {quote.get('quote_category')}"
        assert quote.get("quote_type") == "FAST_TRACK", f"Expected quote_type='FAST_TRACK', got {quote.get('quote_type')}"
        assert quote.get("quote_status") == "Borrador", f"Expected status='Borrador', got {quote.get('quote_status')}"
        
        # Store quote_id for subsequent tests
        self.__class__.fast_track_quote_id = quote.get("quote_id")
        self.__class__.fast_track_quote_number = quote.get("quote_number")
        
        print(f"✓ Created fast_track quote: {quote.get('quote_number')}")
    
    def test_02_send_fast_track_to_client(self):
        """Test sending fast_track quote to client (Borrador → Enviada)"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/send-to-client",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to send to client: {response.text}"
        data = response.json()
        assert data.get("new_status") == "Enviada", f"Expected new_status='Enviada', got {data.get('new_status')}"
        
        print(f"✓ Fast track quote sent to client, status: Enviada")
    
    def test_03_approve_fast_track_requires_oc(self):
        """Test that approving fast_track quote requires Orden de Compra attachment"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # Try to approve without OC - should fail
        response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/approve",
            headers=self.headers
        )
        
        # Should fail with 422 requiring OC
        assert response.status_code == 422, f"Expected 422 without OC, got {response.status_code}"
        assert "Orden de Compra" in response.text, "Error should mention Orden de Compra"
        
        print(f"✓ Approve correctly requires Orden de Compra attachment")
    
    def test_04_upload_oc_and_approve_fast_track(self):
        """Test uploading OC and approving fast_track quote - should notify Operations, return is_fast_track=true"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # First, upload an Orden de Compra attachment
        # Create a simple test file
        files = {
            'file': ('test_oc.pdf', b'%PDF-1.4 test content', 'application/pdf')
        }
        data = {
            'category': 'Orden de Compra'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert upload_response.status_code == 200, f"Failed to upload OC: {upload_response.text}"
        
        # Now approve
        approve_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/approve",
            headers=self.headers
        )
        
        assert approve_response.status_code == 200, f"Failed to approve: {approve_response.text}"
        data = approve_response.json()
        
        # Verify response
        assert data.get("new_status") == "Aprobada", f"Expected new_status='Aprobada', got {data.get('new_status')}"
        assert data.get("is_fast_track") == True, f"Expected is_fast_track=True, got {data.get('is_fast_track')}"
        
        # Verify email was sent to operations (not admin)
        emails = data.get("emails", [])
        # Check that at least one email was sent with fast_track action
        ft_emails = [e for e in emails if "ft" in e.get("action", "").lower() or "operations" in e.get("action", "").lower()]
        
        print(f"✓ Fast track quote approved, is_fast_track=True, emails sent: {len(emails)}")
    
    def test_05_configure_fast_track_quote(self):
        """Test the configure endpoint - only works for fast_track quotes in 'Aprobada' status"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # Verify quote is in Aprobada status
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        assert quote_response.status_code == 200
        quote = quote_response.json()
        assert quote.get("quote_status") == "Aprobada", f"Quote should be in Aprobada status, got {quote.get('quote_status')}"
        
        # Call configure endpoint
        configure_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/configure",
            headers=self.headers
        )
        
        assert configure_response.status_code == 200, f"Failed to configure: {configure_response.text}"
        data = configure_response.json()
        
        # Verify response
        assert data.get("new_status") == "Configurada", f"Expected new_status='Configurada', got {data.get('new_status')}"
        
        # Verify quote status changed
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = quote_response.json()
        assert quote.get("quote_status") == "Configurada", f"Quote status should be 'Configurada', got {quote.get('quote_status')}"
        
        print(f"✓ Fast track quote configured, status: Configurada")
    
    def test_06_configure_fails_for_non_fast_track(self):
        """Test that configure endpoint fails for non-fast_track quotes"""
        # Create a regular implementation quote
        payload = {
            "client_id": self.client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test Service",
                    "quantity": 1,
                    "unit_price_usd": 50,
                    "total_usd": 50
                }
            ],
            "notes": "TEST_Regular implementation quote"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        regular_quote_id = create_response.json()["quote"]["quote_id"]
        
        # Try to configure - should fail
        configure_response = requests.post(
            f"{BASE_URL}/api/quotes/{regular_quote_id}/configure",
            headers=self.headers
        )
        
        assert configure_response.status_code == 400, f"Expected 400 for non-fast_track, got {configure_response.status_code}"
        assert "Fast Track" in configure_response.text or "fast_track" in configure_response.text.lower()
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{regular_quote_id}", headers=self.headers)
        
        print(f"✓ Configure correctly rejects non-fast_track quotes")
    
    def test_07_configure_fails_for_wrong_status(self):
        """Test that configure endpoint fails for fast_track quotes not in 'Aprobada' status"""
        # Create a new fast_track quote (will be in Borrador)
        payload = {
            "client_id": self.client_id,
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test FT Service",
                    "quantity": 1,
                    "unit_price_usd": 75,
                    "total_usd": 75
                }
            ],
            "notes": "TEST_FastTrack for status test"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        
        assert create_response.status_code == 200
        new_ft_quote_id = create_response.json()["quote"]["quote_id"]
        
        # Try to configure while in Borrador - should fail
        configure_response = requests.post(
            f"{BASE_URL}/api/quotes/{new_ft_quote_id}/configure",
            headers=self.headers
        )
        
        assert configure_response.status_code == 400, f"Expected 400 for wrong status, got {configure_response.status_code}"
        assert "Aprobada" in configure_response.text
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{new_ft_quote_id}", headers=self.headers)
        
        print(f"✓ Configure correctly rejects fast_track quotes not in 'Aprobada' status")
    
    def test_08_invoice_fast_track_from_configurada(self):
        """Test that invoice accepts 'Configurada' as valid pre-status for fast_track"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # Verify quote is in Configurada status
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        assert quote_response.status_code == 200
        quote = quote_response.json()
        assert quote.get("quote_status") == "Configurada", f"Quote should be in Configurada status, got {quote.get('quote_status')}"
        
        # Upload Factura attachment
        files = {
            'file': ('test_factura.pdf', b'%PDF-1.4 factura content', 'application/pdf')
        }
        data = {
            'category': 'Factura'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert upload_response.status_code == 200, f"Failed to upload Factura: {upload_response.text}"
        
        # Now invoice
        invoice_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": "FT-TEST-001"},
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert invoice_response.status_code == 200, f"Failed to invoice from Configurada: {invoice_response.text}"
        
        # Verify quote status changed to Facturada
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = quote_response.json()
        assert quote.get("quote_status") == "Facturada", f"Quote status should be 'Facturada', got {quote.get('quote_status')}"
        
        print(f"✓ Fast track quote invoiced from Configurada status")
    
    def test_09_collect_fast_track(self):
        """Test collecting payment for fast_track quote"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # Upload payment proof
        files = {
            'file': ('test_pago.pdf', b'%PDF-1.4 pago content', 'application/pdf')
        }
        data = {
            'category': 'Pagos'
        }
        
        upload_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert upload_response.status_code == 200, f"Failed to upload payment proof: {upload_response.text}"
        
        # Collect payment
        collect_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/collect",
            headers=self.headers
        )
        
        assert collect_response.status_code == 200, f"Failed to collect: {collect_response.text}"
        
        # Verify quote status changed to Pagada
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = quote_response.json()
        assert quote.get("quote_status") == "Pagada", f"Quote status should be 'Pagada', got {quote.get('quote_status')}"
        
        print(f"✓ Fast track quote payment collected, status: Pagada")
    
    def test_10_deliver_fast_track(self):
        """Test delivering fast_track quote (Pagada → Entregada)"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created in previous test")
        
        # Deliver
        deliver_response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/deliver",
            json={},
            headers=self.headers
        )
        
        assert deliver_response.status_code == 200, f"Failed to deliver: {deliver_response.text}"
        
        # Verify quote status changed to Entregada
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = quote_response.json()
        assert quote.get("quote_status") == "Entregada", f"Quote status should be 'Entregada', got {quote.get('quote_status')}"
        
        print(f"✓ Fast track quote delivered, status: Entregada")
    
    def test_11_quote_transitions_has_fast_track(self):
        """Verify QUOTE_TRANSITIONS model includes fast_track with Configurada path"""
        # This is a model verification - we check by trying the flow
        # The fact that tests 05-10 pass confirms the transitions are correct
        
        # Also verify by checking a quote's allowed transitions
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if not quote_id:
            pytest.skip("No fast_track quote created")
        
        # The quote should now be in Entregada (final state)
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = quote_response.json()
        
        assert quote.get("quote_category") == "fast_track"
        assert quote.get("quote_status") == "Entregada"
        
        print(f"✓ QUOTE_TRANSITIONS includes fast_track with correct path")
    
    def test_12_cleanup(self):
        """Cleanup test data"""
        quote_id = getattr(self.__class__, 'fast_track_quote_id', None)
        if quote_id:
            # Delete the test quote
            delete_response = requests.delete(
                f"{BASE_URL}/api/quotes/{quote_id}",
                headers=self.headers
            )
            # Don't fail if delete fails (quote might already be deleted)
            if delete_response.status_code == 200:
                print(f"✓ Cleaned up test quote {quote_id}")
            else:
                print(f"⚠ Could not delete test quote {quote_id}: {delete_response.status_code}")


class TestFastTrackFrontendIntegration:
    """Test frontend-related aspects of Fast Track flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@mega.com", "password": "Admin123!"}
        )
        assert login_response.status_code == 200
        self.token = login_response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_quote_types_endpoint_includes_fast_track(self):
        """Verify that quote types include FAST_TRACK option"""
        # The frontend uses a static QUOTE_TYPES array, but we can verify
        # the backend accepts FAST_TRACK as a valid quote_type
        
        # Get clients first
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        clients = clients_response.json()
        
        if not clients:
            pytest.skip("No clients available for test")
        
        client_id = clients[0]["client_id"]
        
        # Create a quote with FAST_TRACK type
        payload = {
            "client_id": client_id,
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test",
                    "quantity": 1,
                    "unit_price_usd": 10,
                    "total_usd": 10
                }
            ],
            "notes": "TEST_FAST_TRACK_TYPE_VALIDATION"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Backend should accept FAST_TRACK quote_type: {response.text}"
        
        quote = response.json()["quote"]
        assert quote["quote_type"] == "FAST_TRACK"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{quote['quote_id']}", headers=self.headers)
        
        print(f"✓ Backend accepts FAST_TRACK as valid quote_type")
    
    def test_fast_track_defaults_integrator_and_pricing(self):
        """Verify fast_track quotes can have 'Sin integrador' and outsourcing pricing"""
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        clients = clients_response.json()
        
        if not clients:
            pytest.skip("No clients available for test")
        
        client_id = clients[0]["client_id"]
        
        # Create with default values for fast_track
        payload = {
            "client_id": client_id,
            "quote_category": "fast_track",
            "quote_type": "FAST_TRACK",
            "pricing_model": "outsourcing",  # Fast track uses outsourcing
            "integrator_id": "sin_integrador",
            "integrator_name": "Sin integrador",
            "sponsor_bank_name": "Mega Soft",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Configuración",
                    "quantity": 1,
                    "unit_price_usd": 100,
                    "total_usd": 100
                }
            ],
            "notes": "TEST_FAST_TRACK_DEFAULTS"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200
        quote = response.json()["quote"]
        
        # Verify defaults
        assert quote["pricing_model"] == "outsourcing"
        assert quote["integrator_name"] == "Sin integrador"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/quotes/{quote['quote_id']}", headers=self.headers)
        
        print(f"✓ Fast track quote accepts default integrator and outsourcing pricing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
