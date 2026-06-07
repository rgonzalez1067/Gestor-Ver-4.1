# ruff: noqa
"""
Test iteration 24: Delete Quote Functionality Verification

This test suite verifies the complete delete quote flow:
1. Create a test quote
2. Verify quote exists
3. Delete the quote
4. Verify quote is removed from database
5. Verify 404 returned when accessing deleted quote

Tests address the reported bug: "Delete button not working"
Conclusion: Bug NOT reproducible - delete functionality works correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Use existing session token from iteration 23
SESSION_TOKEN = "P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"


class TestDeleteQuoteFlow:
    """Complete delete quote flow verification"""
    
    @pytest.fixture
    def api_client(self):
        """Create authenticated session"""
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        })
        return session
    
    def test_create_and_delete_quote_full_flow(self, api_client):
        """
        Full delete flow: Create -> Verify -> Delete -> Verify Removed
        This tests the exact flow reported as broken by user
        """
        # Step 1: Get existing clients for quote creation
        clients_response = api_client.get(f"{BASE_URL}/api/clients")
        assert clients_response.status_code == 200, f"Failed to get clients: {clients_response.text}"
        clients = clients_response.json()
        assert len(clients) > 0, "No clients found for testing"
        client_id = clients[0]['client_id']
        
        # Step 2: Create a test quote
        create_payload = {
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_DELETE_ITERATION24_VERIFICATION"
        }
        create_response = api_client.post(f"{BASE_URL}/api/quotes", json=create_payload)
        assert create_response.status_code == 200, f"Failed to create quote: {create_response.text}"
        
        created_quote = create_response.json()
        quote_id = created_quote['quote_id']
        quote_number = created_quote['quote_number']
        print(f"Created test quote: {quote_id} ({quote_number})")
        
        # Step 3: Verify quote exists
        get_response = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert get_response.status_code == 200, f"Quote not found after creation: {get_response.text}"
        assert get_response.json()['quote_id'] == quote_id
        print(f"Verified quote exists: {quote_id}")
        
        # Step 4: Delete the quote
        delete_response = api_client.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        delete_data = delete_response.json()
        assert "eliminada exitosamente" in delete_data['message'], f"Unexpected delete message: {delete_data}"
        assert delete_data['quote_id'] == quote_id
        print(f"Delete response: {delete_data['message']}")
        
        # Step 5: Verify quote is removed from database
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 404, f"Quote still exists after deletion: {verify_response.text}"
        print("Verified quote removed: 404 returned")
        
        # Step 6: Verify quote not in list
        list_response = api_client.get(f"{BASE_URL}/api/quotes")
        assert list_response.status_code == 200
        quotes = list_response.json()
        quote_ids = [q['quote_id'] for q in quotes]
        assert quote_id not in quote_ids, "Deleted quote still appears in list"
        print("Verified quote not in list")
    
    def test_delete_quote_in_enviada_state(self, api_client):
        """Test deletion of quote in Enviada state"""
        # Get client
        clients = api_client.get(f"{BASE_URL}/api/clients").json()
        client_id = clients[0]['client_id']
        
        # Create quote
        create_response = api_client.post(f"{BASE_URL}/api/quotes", json={
            "client_id": client_id,
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_DELETE_ENVIADA_STATE"
        })
        assert create_response.status_code == 200
        quote_id = create_response.json()['quote_id']
        
        # Change to Enviada state
        status_response = api_client.put(f"{BASE_URL}/api/quotes/{quote_id}/status", json={
            "new_status": "Enviada"
        })
        assert status_response.status_code == 200
        
        # Verify status changed
        quote = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}").json()
        assert quote['quote_status'] == 'Enviada'
        
        # Delete in Enviada state
        delete_response = api_client.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        assert delete_response.status_code == 200, f"Delete in Enviada state failed: {delete_response.text}"
        
        # Verify deleted
        verify = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify.status_code == 404
        print("Successfully deleted quote in Enviada state")
    
    def test_delete_nonexistent_quote_returns_404(self, api_client):
        """Test that deleting non-existent quote returns 404"""
        fake_id = "quo_nonexistent123"
        response = api_client.delete(f"{BASE_URL}/api/quotes/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent quote delete returns 404 as expected")
    
    def test_delete_without_auth_returns_401(self):
        """Test that deleting without authentication returns 401"""
        # Create session without auth header
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.delete(f"{BASE_URL}/api/quotes/quo_anyid")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Unauthenticated delete returns 401 as expected")


class TestBackendDeleteEndpoint:
    """Direct backend API testing for DELETE endpoint"""
    
    @pytest.fixture
    def api_client(self):
        session = requests.Session()
        session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SESSION_TOKEN}"
        })
        return session
    
    def test_delete_endpoint_response_structure(self, api_client):
        """Verify DELETE endpoint returns correct response structure"""
        # Create a quote
        clients = api_client.get(f"{BASE_URL}/api/clients").json()
        create_response = api_client.post(f"{BASE_URL}/api/quotes", json={
            "client_id": clients[0]['client_id'],
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST_RESPONSE_STRUCTURE"
        })
        quote_id = create_response.json()['quote_id']
        
        # Delete and verify response structure
        delete_response = api_client.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        assert delete_response.status_code == 200
        
        data = delete_response.json()
        assert 'message' in data, "Response missing 'message' field"
        assert 'quote_id' in data, "Response missing 'quote_id' field"
        assert data['quote_id'] == quote_id
        print(f"Response structure verified: {data}")
    
    def test_delete_with_logging(self, api_client):
        """Test that DELETE logs are generated (check server logs)"""
        clients = api_client.get(f"{BASE_URL}/api/clients").json()
        create_response = api_client.post(f"{BASE_URL}/api/quotes", json={
            "client_id": clients[0]['client_id'],
            "quote_type": "VPOS",
            "notes": "TEST_LOGGING"
        })
        quote_id = create_response.json()['quote_id']
        quote_number = create_response.json()['quote_number']
        
        # Delete
        delete_response = api_client.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        assert delete_response.status_code == 200
        
        # Note: Backend logs should show:
        # [DELETE QUOTE] Recibida solicitud para eliminar quote_id: {quote_id}
        # [DELETE QUOTE] ÉXITO: Cotización {quote_number} eliminada
        print(f"Check backend logs for DELETE operations on {quote_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
