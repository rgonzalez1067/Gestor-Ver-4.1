"""
Test iteration 23: Optional fields (Pinpad, Sponsor Bank) and Delete quotes in any state
Tests:
1. Backend DELETE /api/quotes/{quote_id} allows deletion in any state
2. Create quote without Pinpad/Sponsor Bank fields
3. Quote state transitions and delete in non-Borrador states
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDeleteQuoteAnyState:
    """Test that quotes can be deleted in any state (not just Borrador)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session for tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
        
    def get_auth_headers(self):
        """Get authentication headers"""
        # Use test token from previous iteration
        return {"Authorization": "Bearer P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"}
    
    def test_delete_quote_in_borrador_state(self):
        """Test deleting a quote in Borrador state"""
        headers = self.get_auth_headers()
        
        # First, get clients to use for creating quote
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available for testing")
        client_id = clients_resp.json()[0]['client_id']
        
        # Create a new quote in Borrador state
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_DELETE_BORRADOR_" + uuid.uuid4().hex[:8]
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200, f"Failed to create quote: {create_resp.text}"
        quote = create_resp.json()
        quote_id = quote['quote_id']
        
        # Verify it's in Borrador state
        assert quote.get('quote_status') == 'Borrador'
        
        # Delete the quote
        delete_resp = self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert delete_resp.status_code == 200, f"Failed to delete Borrador quote: {delete_resp.text}"
        
        # Verify quote is deleted
        get_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert get_resp.status_code == 404, "Quote should not exist after deletion"
        print("PASSED: Delete quote in Borrador state works")
    
    def test_delete_quote_in_enviada_state(self):
        """Test deleting a quote in Enviada state - should now be allowed"""
        headers = self.get_auth_headers()
        
        # Get client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available")
        client_id = clients_resp.json()[0]['client_id']
        
        # Create quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "notes": "TEST_DELETE_ENVIADA_" + uuid.uuid4().hex[:8]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200
        quote_id = create_resp.json()['quote_id']
        
        # Change state to Enviada
        status_update = {"new_status": "Enviada"}
        update_resp = self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", headers=headers, json=status_update)
        assert update_resp.status_code == 200, f"Failed to update status to Enviada: {update_resp.text}"
        
        # Verify state is Enviada
        get_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert get_resp.json().get('quote_status') == 'Enviada'
        
        # Delete quote in Enviada state - should now work
        delete_resp = self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert delete_resp.status_code == 200, f"DELETE in Enviada state should work: {delete_resp.text}"
        
        # Verify deletion
        verify_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert verify_resp.status_code == 404, "Quote should be deleted"
        print("PASSED: Delete quote in Enviada state now works")
    
    def test_delete_quote_in_aprobada_state(self):
        """Test deleting a quote in Aprobada state - should now be allowed"""
        headers = self.get_auth_headers()
        
        # Get client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available")
        client_id = clients_resp.json()[0]['client_id']
        
        # Create quote
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "notes": "TEST_DELETE_APROBADA_" + uuid.uuid4().hex[:8]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200
        quote_id = create_resp.json()['quote_id']
        
        # Change state: Borrador -> Enviada -> Aprobada
        self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", headers=headers, json={"new_status": "Enviada"})
        update_resp = self.session.put(f"{BASE_URL}/api/quotes/{quote_id}/status", headers=headers, json={"new_status": "Aprobada"})
        assert update_resp.status_code == 200, f"Failed to update status to Aprobada: {update_resp.text}"
        
        # Verify state is Aprobada
        get_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert get_resp.json().get('quote_status') == 'Aprobada'
        
        # Delete quote in Aprobada state - should now work
        delete_resp = self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert delete_resp.status_code == 200, f"DELETE in Aprobada state should work: {delete_resp.text}"
        print("PASSED: Delete quote in Aprobada state now works")


class TestOptionalPinpadAndSponsorBank:
    """Test that Pinpad and Sponsor Bank fields are now optional"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
    
    def get_auth_headers(self):
        return {"Authorization": "Bearer P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"}
    
    def test_create_quote_without_pinpad_and_sponsor_bank(self):
        """Test creating a quote without selecting Pinpad or Sponsor Bank"""
        headers = self.get_auth_headers()
        
        # Get required data
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available")
        client_id = clients_resp.json()[0]['client_id']
        
        integrators_resp = self.session.get(f"{BASE_URL}/api/integrators", headers=headers)
        if integrators_resp.status_code != 200 or not integrators_resp.json():
            pytest.skip("No integrators available")
        integrator = integrators_resp.json()[0]
        
        # Create quote WITHOUT pinpad_id and sponsor_bank_id
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "integrator_id": integrator['integrator_id'],
            "integrator_name": integrator['name'],
            "integrator_app_name": integrator['app_name'],
            # NO pinpad_id - should be optional
            # NO sponsor_bank_id - should be optional
            "cantidad_cajas": 2,
            "cantidad_bancos": 1,
            "services": [],
            "hardware": [],
            "notes": "TEST_NO_PINPAD_NO_SPONSOR_" + uuid.uuid4().hex[:8]
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200, f"Should create quote without pinpad/sponsor: {create_resp.text}"
        
        quote = create_resp.json()
        assert quote.get('client_id') == client_id
        assert quote.get('integrator_id') == integrator['integrator_id']
        assert quote.get('pinpad_id') is None, "Pinpad should be null"
        assert quote.get('sponsor_bank_id') is None, "Sponsor bank should be null"
        
        # Clean up - delete the test quote
        quote_id = quote['quote_id']
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        print("PASSED: Create quote without Pinpad and Sponsor Bank works")
    
    def test_create_quote_with_only_integrator(self):
        """Test creating a quote with only integrator selected (no pinpad, no sponsor)"""
        headers = self.get_auth_headers()
        
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available")
        client_id = clients_resp.json()[0]['client_id']
        
        integrators_resp = self.session.get(f"{BASE_URL}/api/integrators", headers=headers)
        if integrators_resp.status_code != 200 or not integrators_resp.json():
            pytest.skip("No integrators available")
        integrator = integrators_resp.json()[0]
        
        # Create with empty strings for pinpad and sponsor (simulating "none" selection)
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "integrator_id": integrator['integrator_id'],
            "integrator_name": integrator['name'],
            "integrator_app_name": integrator['app_name'],
            "pinpad_id": None,  # Explicitly null
            "pinpad_model": None,
            "sponsor_bank_id": None,  # Explicitly null
            "sponsor_bank_name": None,
            "cantidad_cajas": 1,
            "services": [],
            "hardware": [],
            "notes": "TEST_ONLY_INTEGRATOR_" + uuid.uuid4().hex[:8]
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200, f"Quote creation should succeed: {create_resp.text}"
        
        quote = create_resp.json()
        quote_id = quote['quote_id']
        
        # Verify quote was created successfully
        get_resp = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert get_resp.status_code == 200
        saved_quote = get_resp.json()
        
        assert saved_quote['integrator_id'] == integrator['integrator_id']
        assert saved_quote.get('pinpad_id') is None
        assert saved_quote.get('sponsor_bank_id') is None
        
        # Clean up
        self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        print("PASSED: Create quote with only integrator (no pinpad/sponsor) works")


class TestDeleteEndpointResponse:
    """Test DELETE endpoint response format"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
    
    def get_auth_headers(self):
        return {"Authorization": "Bearer P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"}
    
    def test_delete_nonexistent_quote_returns_404(self):
        """Test that deleting a non-existent quote returns 404"""
        headers = self.get_auth_headers()
        
        fake_id = "quo_nonexistent123"
        delete_resp = self.session.delete(f"{BASE_URL}/api/quotes/{fake_id}", headers=headers)
        assert delete_resp.status_code == 404, "Should return 404 for non-existent quote"
        print("PASSED: Delete non-existent quote returns 404")
    
    def test_delete_quote_returns_success_message(self):
        """Test that successful delete returns proper message"""
        headers = self.get_auth_headers()
        
        # Get client and create quote
        clients_resp = self.session.get(f"{BASE_URL}/api/clients", headers=headers)
        if clients_resp.status_code != 200 or not clients_resp.json():
            pytest.skip("No clients available")
        client_id = clients_resp.json()[0]['client_id']
        
        quote_data = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "notes": "TEST_DELETE_MESSAGE_" + uuid.uuid4().hex[:8]
        }
        create_resp = self.session.post(f"{BASE_URL}/api/quotes", headers=headers, json=quote_data)
        assert create_resp.status_code == 200
        
        quote = create_resp.json()
        quote_id = quote['quote_id']
        quote_number = quote['quote_number']
        
        # Delete and check response
        delete_resp = self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers)
        assert delete_resp.status_code == 200
        
        result = delete_resp.json()
        assert 'message' in result, "Response should contain message"
        assert quote_number in result['message'], f"Message should contain quote number: {result}"
        assert 'quote_id' in result, "Response should contain quote_id"
        print(f"PASSED: Delete returns proper message: {result['message']}")
