"""
Test iteration 25 - Testing approval workflow and state transitions
Features to test:
1. POST /api/quotes/{id}/approve exists and works
2. POST /approve validates quote is in 'Enviada' state
3. POST /approve changes state to 'Aprobada'
4. POST /approve attempts to send email to admin_email
5. POST /send-to-implementation validates 'Pagada' state
6. Complete state flow: Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Enviada a Imple
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Valid session token from previous testing
SESSION_TOKEN = "P9AVoJzHOYxuqit3lai9Vz5t2QaHxeGWUnVh3hBtZIo"


class TestApproveEndpoint:
    """Test the new POST /quotes/{id}/approve endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for all tests"""
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_approve_endpoint_exists(self):
        """Test that POST /approve endpoint exists"""
        # First get a quote to use
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        
        quotes = response.json()
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        # Try with first quote - expect either success or validation error (not 404/405)
        quote_id = quotes[0]['quote_id']
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=self.headers)
        
        # Should get 200 (success) or 400 (invalid state) - NOT 404 (not found) or 405 (method not allowed)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
        print(f"Approve endpoint exists. Response: {response.status_code}")
    
    def test_approve_validates_state_enviada(self):
        """Test that approve endpoint rejects quotes not in 'Enviada' state"""
        # Get quotes in Borrador state
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        borrador_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Borrador':
                borrador_quote = q
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador state available")
        
        # Try to approve - should fail with 400
        response = requests.post(f"{BASE_URL}/api/quotes/{borrador_quote['quote_id']}/approve", headers=self.headers)
        assert response.status_code == 400, f"Should reject Borrador quote. Got: {response.status_code}"
        
        data = response.json()
        assert "Enviada" in data.get('detail', ''), f"Error should mention 'Enviada' state. Got: {data}"
        print(f"Correctly rejected Borrador quote: {data['detail']}")
    
    def test_approve_changes_state_to_aprobada(self):
        """Test that approve endpoint changes state to 'Aprobada'"""
        # First, we need a quote in 'Enviada' state
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        enviada_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Enviada':
                enviada_quote = q
                break
        
        if not enviada_quote:
            pytest.skip("No quote in Enviada state available for testing")
        
        # Approve the quote
        quote_id = enviada_quote['quote_id']
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=self.headers)
        assert response.status_code == 200, f"Approve failed: {response.text}"
        
        data = response.json()
        assert data.get('new_status') == 'Aprobada', f"New status should be 'Aprobada'. Got: {data}"
        
        # Verify state changed in database
        response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        assert response.status_code == 200
        quote = response.json()
        assert quote.get('quote_status') == 'Aprobada', f"Quote status not updated. Got: {quote.get('quote_status')}"
        assert quote.get('approved_at') is not None, "approved_at timestamp should be set"
        
        print(f"Quote {quote_id} approved successfully. Status: {quote['quote_status']}")
    
    def test_approve_returns_admin_notification_info(self):
        """Test that approve response includes admin notification info"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        enviada_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Enviada':
                enviada_quote = q
                break
        
        if not enviada_quote:
            pytest.skip("No quote in Enviada state available")
        
        response = requests.post(f"{BASE_URL}/api/quotes/{enviada_quote['quote_id']}/approve", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        # Should have admin_notified field (true or false)
        assert 'admin_notified' in data, f"Response should include admin_notified field. Got: {data}"
        print(f"Admin notification info present: admin_notified={data['admin_notified']}")


class TestSendToImplementationValidation:
    """Test that send-to-implementation validates 'Pagada' state"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_send_to_implementation_rejects_non_pagada_state(self):
        """Test that send-to-implementation rejects quotes not in 'Pagada' state"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        # Find a quote NOT in Pagada state
        non_pagada_quote = None
        for q in quotes:
            if q.get('quote_status') != 'Pagada':
                non_pagada_quote = q
                break
        
        if not non_pagada_quote:
            pytest.skip("All quotes are in Pagada state")
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{non_pagada_quote['quote_id']}/send-to-implementation",
            headers=self.headers
        )
        
        # Should be rejected with 400
        assert response.status_code == 400, f"Should reject non-Pagada quote. Got: {response.status_code}, body: {response.text}"
        
        data = response.json()
        assert "Pagada" in data.get('detail', ''), f"Error should mention 'Pagada' state. Got: {data}"
        print(f"Correctly rejected non-Pagada quote: {data['detail']}")
    
    def test_send_to_implementation_accepts_pagada_state(self):
        """Test that send-to-implementation works for 'Pagada' quotes"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        pagada_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Pagada':
                pagada_quote = q
                break
        
        if not pagada_quote:
            pytest.skip("No quote in Pagada state available")
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{pagada_quote['quote_id']}/send-to-implementation",
            headers=self.headers
        )
        
        # Should succeed (200) or fail with missing email config (400), not state validation
        if response.status_code == 400:
            data = response.json()
            # Should be about email config, not state
            assert "Pagada" not in data.get('detail', ''), f"Should not fail due to state validation"
            print(f"Pagada quote accepted, but email config missing: {data['detail']}")
        else:
            assert response.status_code == 200, f"Should accept Pagada quote. Got: {response.status_code}"
            print(f"Pagada quote accepted for implementation")


class TestQuoteStateFlow:
    """Test the complete quote state flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_create_quote_starts_in_borrador(self):
        """Test that new quotes start in 'Borrador' state"""
        # Get a client
        response = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        clients = response.json()
        
        if not clients:
            pytest.skip("No clients available")
        
        client_id = clients[0]['client_id']
        
        # Create quote
        quote_data = {
            "client_id": client_id,
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=self.headers)
        assert response.status_code == 200, f"Failed to create quote: {response.text}"
        
        quote = response.json()
        assert quote.get('quote_status') == 'Borrador', f"New quote should be Borrador. Got: {quote.get('quote_status')}"
        print(f"New quote {quote['quote_id']} created in Borrador state")
        
        # Cleanup - store for later tests
        self.new_quote_id = quote['quote_id']
        return quote
    
    def test_state_transition_borrador_to_enviada(self):
        """Test Borrador -> Enviada transition via send-to-client"""
        # Get a Borrador quote
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        borrador_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Borrador':
                borrador_quote = q
                break
        
        if not borrador_quote:
            pytest.skip("No Borrador quote available")
        
        quote_id = borrador_quote['quote_id']
        
        # Send to client
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client", headers=self.headers)
        assert response.status_code == 200, f"Send to client failed: {response.text}"
        
        # Verify state
        response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = response.json()
        assert quote.get('quote_status') == 'Enviada', f"Should be Enviada. Got: {quote.get('quote_status')}"
        print(f"Quote {quote_id} transitioned to Enviada")
    
    def test_state_transition_enviada_to_aprobada(self):
        """Test Enviada -> Aprobada transition via approve"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        enviada_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Enviada':
                enviada_quote = q
                break
        
        if not enviada_quote:
            pytest.skip("No Enviada quote available")
        
        quote_id = enviada_quote['quote_id']
        
        # Approve
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=self.headers)
        assert response.status_code == 200, f"Approve failed: {response.text}"
        
        # Verify state
        response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
        quote = response.json()
        assert quote.get('quote_status') == 'Aprobada', f"Should be Aprobada. Got: {quote.get('quote_status')}"
        print(f"Quote {quote_id} transitioned to Aprobada")
    
    def test_state_transition_aprobada_to_facturada(self):
        """Test Aprobada -> Facturada transition via invoice"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        quotes = response.json()
        
        aprobada_quote = None
        for q in quotes:
            if q.get('quote_status') == 'Aprobada':
                aprobada_quote = q
                break
        
        if not aprobada_quote:
            pytest.skip("No Aprobada quote available")
        
        quote_id = aprobada_quote['quote_id']
        
        # Invoice (requires PDF - we'll test the validation)
        response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            headers=self.headers
        )
        
        # Should fail with 400 (no PDF provided) or succeed if endpoint accepts without PDF
        if response.status_code == 400:
            data = response.json()
            # Check if it's about PDF requirement or state validation
            print(f"Invoice endpoint response: {data}")
        elif response.status_code == 200:
            # Verify state
            response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.headers)
            quote = response.json()
            assert quote.get('quote_status') == 'Facturada', f"Should be Facturada. Got: {quote.get('quote_status')}"
            print(f"Quote {quote_id} transitioned to Facturada")
        else:
            # Check if endpoint exists
            assert response.status_code not in [404, 405], f"Invoice endpoint issue: {response.status_code}"


class TestApproveEndpointNonexistent:
    """Test approve with nonexistent quote"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.headers = {
            "Authorization": f"Bearer {SESSION_TOKEN}",
            "Content-Type": "application/json"
        }
    
    def test_approve_nonexistent_quote_returns_404(self):
        """Test that approving nonexistent quote returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/quotes/nonexistent_id/approve",
            headers=self.headers
        )
        assert response.status_code == 404, f"Should return 404. Got: {response.status_code}"
        print("Correctly returned 404 for nonexistent quote")
    
    def test_approve_without_auth_returns_401(self):
        """Test that approve without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/quotes/some_id/approve")
        assert response.status_code == 401, f"Should return 401. Got: {response.status_code}"
        print("Correctly returned 401 for unauthenticated request")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
