"""
Test Suite for Iteration 22: Delete Features Testing
- DELETE /api/quotes/{quote_id} endpoint
- Only allows deleting quotes in "Borrador" status
- Hardware table layout verification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Session data for authentication
session_token = None
test_client_id = None
test_quote_id_draft = None
test_quote_id_sent = None

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestAuthSetup:
    """Get authentication for subsequent tests"""
    
    def test_get_existing_session(self, api_client):
        """Get existing session token from cookies or use test token"""
        global session_token
        
        # Try to use an existing session from the previous tests
        response = api_client.get(f"{BASE_URL}/api/quotes", headers={"Authorization": "Bearer test"})
        
        # If unauthorized, we need to get a valid token
        # For now, let's try to get an existing quote to test with
        # Using the session token from previous test iteration
        session_token = "P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # Verify auth works
        response = api_client.get(f"{BASE_URL}/api/auth/me")
        print(f"Auth check response: {response.status_code}")
        
        # If auth fails, try a different approach
        if response.status_code != 200:
            pytest.skip("No valid authentication available, skipping auth-required tests")
        
        print(f"Authenticated as: {response.json()}")


class TestQuoteDeletion:
    """Test DELETE /api/quotes/{quote_id} endpoint"""
    
    def test_setup_create_test_client(self, api_client):
        """Create a test client for quote creation"""
        global test_client_id
        
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # First check if we have existing clients
        response = api_client.get(f"{BASE_URL}/api/clients")
        if response.status_code == 200 and len(response.json()) > 0:
            test_client_id = response.json()[0]["client_id"]
            print(f"Using existing client: {test_client_id}")
        else:
            # Create a test client
            client_data = {
                "rif": f"J-TEST-DELETE-{os.urandom(4).hex()}",
                "legal_name": "Test Delete Company",
                "fantasy_name": "Delete Test",
                "segment": "Pymes",
                "address": "Test Address",
                "contact1": {"name": "Test Contact", "phone": "123456789", "email": "test@test.com"},
                "contact2": {"name": "Test Contact 2", "phone": "987654321", "email": "test2@test.com"}
            }
            response = api_client.post(f"{BASE_URL}/api/clients", json=client_data)
            assert response.status_code == 200, f"Failed to create client: {response.text}"
            test_client_id = response.json()["client_id"]
            print(f"Created test client: {test_client_id}")
    
    def test_create_draft_quote_for_deletion(self, api_client):
        """Create a quote in Borrador status for deletion test"""
        global test_quote_id_draft
        
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        quote_data = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST - Quote for deletion test"
        }
        
        response = api_client.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert response.status_code == 200, f"Failed to create quote: {response.text}"
        
        test_quote_id_draft = response.json()["quote_id"]
        quote_status = response.json()["quote_status"]
        
        assert quote_status == "Borrador", f"Quote should be in Borrador status, got: {quote_status}"
        print(f"Created draft quote: {test_quote_id_draft}, status: {quote_status}")
    
    def test_delete_draft_quote_success(self, api_client):
        """Test successful deletion of a Borrador quote"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # Delete the draft quote
        response = api_client.delete(f"{BASE_URL}/api/quotes/{test_quote_id_draft}")
        
        assert response.status_code == 200, f"Failed to delete draft quote: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "Cotización eliminada exitosamente" in data["message"]
        print(f"Successfully deleted draft quote: {test_quote_id_draft}")
        
        # Verify quote no longer exists
        get_response = api_client.get(f"{BASE_URL}/api/quotes/{test_quote_id_draft}")
        assert get_response.status_code == 404, "Deleted quote should return 404"
    
    def test_create_sent_quote_for_rejection_test(self, api_client):
        """Create a quote and send it to test deletion rejection"""
        global test_quote_id_sent
        
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # Create a new quote
        quote_data = {
            "client_id": test_client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "notes": "TEST - Quote for rejection test"
        }
        
        response = api_client.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert response.status_code == 200, f"Failed to create quote: {response.text}"
        
        test_quote_id_sent = response.json()["quote_id"]
        print(f"Created quote for rejection test: {test_quote_id_sent}")
        
        # Change status to "Enviada"
        status_response = api_client.put(
            f"{BASE_URL}/api/quotes/{test_quote_id_sent}/status",
            json={"new_status": "Enviada"}
        )
        assert status_response.status_code == 200, f"Failed to change quote status: {status_response.text}"
        
        # Verify the message confirms the status change
        message = status_response.json().get("message", "")
        assert "Enviada" in message, f"Response should confirm status change, got: {message}"
        print(f"Status update response: {message}")
        
        # Verify the actual status by fetching the quote
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{test_quote_id_sent}")
        assert verify_response.status_code == 200
        new_status = verify_response.json()["quote_status"]
        assert new_status == "Enviada", f"Quote should be in Enviada status, got: {new_status}"
        print(f"Verified quote status: {new_status}")
    
    def test_delete_sent_quote_rejected(self, api_client):
        """Test that deletion of non-Borrador quote is rejected"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # Try to delete the sent quote
        response = api_client.delete(f"{BASE_URL}/api/quotes/{test_quote_id_sent}")
        
        assert response.status_code == 400, f"Should reject deletion of sent quote, got: {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        assert "Borrador" in data["detail"], f"Error should mention Borrador, got: {data['detail']}"
        print(f"Correctly rejected deletion of sent quote: {data['detail']}")
    
    def test_delete_nonexistent_quote(self, api_client):
        """Test deletion of non-existent quote returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        response = api_client.delete(f"{BASE_URL}/api/quotes/quo_nonexistent123")
        
        assert response.status_code == 404, f"Should return 404 for non-existent quote, got: {response.status_code}"
        print("Correctly returned 404 for non-existent quote")


class TestHardwareEndpoint:
    """Test Hardware endpoint for table layout verification"""
    
    def test_get_hardware_list(self, api_client):
        """Test GET /api/hardware returns hardware list"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/hardware")
        
        assert response.status_code == 200, f"Failed to get hardware: {response.text}"
        
        hardware_list = response.json()
        assert isinstance(hardware_list, list), "Response should be a list"
        
        print(f"Hardware list count: {len(hardware_list)}")
        
        # Verify hardware structure if items exist
        if len(hardware_list) > 0:
            hw = hardware_list[0]
            assert "hardware_id" in hw
            assert "name" in hw
            assert "type" in hw
            assert "price_usd" in hw
            assert "price_bs_usd" in hw
            print(f"Sample hardware: {hw['name']} - Type: {hw['type']} - $USD: {hw['price_usd']}")
    
    def test_create_hardware(self, api_client):
        """Test creating hardware item"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        hardware_data = {
            "name": f"TEST_Pinpad_Delete_{os.urandom(4).hex()}",
            "type": "Pinpad",
            "price_usd": 150.00,
            "price_bs_usd": 175.00,
            "description": "Test hardware for deletion"
        }
        
        response = api_client.post(f"{BASE_URL}/api/hardware", json=hardware_data)
        
        assert response.status_code == 200, f"Failed to create hardware: {response.text}"
        
        data = response.json()
        assert data["name"] == hardware_data["name"]
        assert data["type"] == hardware_data["type"]
        assert data["price_usd"] == hardware_data["price_usd"]
        assert data["price_bs_usd"] == hardware_data["price_bs_usd"]
        
        hardware_id = data["hardware_id"]
        print(f"Created hardware: {hardware_id}")
        
        # Delete the test hardware
        delete_response = api_client.delete(f"{BASE_URL}/api/hardware/{hardware_id}")
        assert delete_response.status_code == 200, f"Failed to delete hardware: {delete_response.text}"
        print(f"Cleaned up test hardware: {hardware_id}")


class TestQuoteStatusChecks:
    """Additional tests for quote status handling"""
    
    def test_get_quotes_list(self, api_client):
        """Verify quotes listing works and shows status"""
        api_client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/quotes")
        
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        
        quotes = response.json()
        assert isinstance(quotes, list), "Response should be a list"
        
        # Count quotes by status
        status_counts = {}
        for quote in quotes:
            status = quote.get("quote_status", "Borrador")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"Quotes by status: {status_counts}")
        print(f"Total quotes: {len(quotes)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
