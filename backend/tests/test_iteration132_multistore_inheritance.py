# ruff: noqa
"""
Test Iteration 132: Multistore Inheritance and Distribution Validation
Tests the 'Enviar a Implementación' flow with branch_details inheritance

Scenarios:
A) Quote WITH branch_details → should inherit stores automatically
B) Quote WITHOUT branch_details → should require manual multistore input
C) PDF generation with and without branch_details
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        return data["session_token"]
    
    def test_login_success(self, auth_token):
        """Test login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 10
        print(f"✓ Login successful, token: {auth_token[:20]}...")


class TestQuoteWithBranchDetails:
    """Test Scenario A: Quote WITH branch_details (quo_ad9cb906804b)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_quote_has_branch_details(self, headers):
        """Verify quote quo_ad9cb906804b has branch_details"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_ad9cb906804b", headers=headers)
        assert response.status_code == 200, f"Failed to get quote: {response.text}"
        
        data = response.json()
        branch_details = data.get("branch_details", [])
        
        assert len(branch_details) > 0, "Quote should have branch_details"
        assert len(branch_details) == 2, f"Expected 2 branches, got {len(branch_details)}"
        
        # Verify branch structure
        for branch in branch_details:
            assert "store_name" in branch, "Branch should have store_name"
            assert "quantity" in branch, "Branch should have quantity"
            assert branch["quantity"] > 0, "Branch quantity should be > 0"
        
        print(f"✓ Quote has {len(branch_details)} branches: {[b['store_name'] for b in branch_details]}")
    
    def test_quote_is_vpos_type(self, headers):
        """Verify quote is VPOS type (multistore eligible)"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_ad9cb906804b", headers=headers)
        data = response.json()
        
        assert data.get("quote_type") == "VPOS", f"Expected VPOS, got {data.get('quote_type')}"
        print("✓ Quote is VPOS type")


class TestQuoteWithoutBranchDetails:
    """Test Scenario B: Quote WITHOUT branch_details (quo_dd291a51e1dc)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_quote_has_no_branch_details(self, headers):
        """Verify quote quo_dd291a51e1dc has NO branch_details"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_dd291a51e1dc", headers=headers)
        assert response.status_code == 200, f"Failed to get quote: {response.text}"
        
        data = response.json()
        branch_details = data.get("branch_details", [])
        
        assert len(branch_details) == 0, f"Quote should have NO branch_details, got {len(branch_details)}"
        print("✓ Quote has no branch_details (Scenario B)")
    
    def test_quote_is_vpos_type(self, headers):
        """Verify quote is VPOS type"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_dd291a51e1dc", headers=headers)
        data = response.json()
        
        assert data.get("quote_type") == "VPOS", f"Expected VPOS, got {data.get('quote_type')}"
        print("✓ Quote is VPOS type")


class TestPDFGeneration:
    """Test PDF generation with and without branch_details"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_pdf_generation_with_branch_details(self, headers):
        """Test PDF generation for quote WITH branch_details (no 500 error)"""
        # Get quote data first
        response = requests.get(f"{BASE_URL}/api/quotes/quo_ad9cb906804b", headers=headers)
        assert response.status_code == 200
        quote_data = response.json()
        
        # Prepare PDF request payload using correct field names (cliente_nombre, etc.)
        pdf_payload = {
            "template_type": "vpos_pyme",
            "quote_number": quote_data.get("quote_number", "TEST-PDF-001"),
            "cliente_nombre": quote_data.get("client_name", "Test Client"),
            "cliente_rif": "J-12345678-9",
            "quote_type": quote_data.get("quote_type", "VPOS"),
            "pricing_model": quote_data.get("pricing_model", "outsourcing"),
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "branch_details": quote_data.get("branch_details", []),  # Include branch_details
            "integrator_name": quote_data.get("integrator_name", "Test Integrator"),
            "integrator_app_name": quote_data.get("integrator_app_name", "Test App"),
            "pinpad_model": quote_data.get("pinpad_model", "Ingenico"),
            "cantidad_cajas": quote_data.get("cantidad_cajas", 10),
        }
        
        # Test PDF generation endpoint - returns PDF file directly
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            headers=headers,
            json=pdf_payload
        )
        
        # Should NOT return 500
        assert response.status_code != 500, f"PDF generation returned 500 error: {response.text}"
        assert response.status_code == 200, f"PDF generation failed with {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Verify PDF content starts with PDF header
        assert response.content[:4] == b'%PDF', "Response should be a valid PDF file"
        print(f"✓ PDF generated successfully with branch_details (size: {len(response.content)} bytes)")
    
    def test_pdf_generation_without_branch_details(self, headers):
        """Test PDF generation for quote WITHOUT branch_details (no 500 error)"""
        # Get quote data first
        response = requests.get(f"{BASE_URL}/api/quotes/quo_dd291a51e1dc", headers=headers)
        assert response.status_code == 200
        quote_data = response.json()
        
        # Prepare PDF request payload using correct field names
        pdf_payload = {
            "template_type": "vpos_pyme",
            "quote_number": quote_data.get("quote_number", "TEST-PDF-002"),
            "cliente_nombre": quote_data.get("client_name", "Test Client"),
            "cliente_rif": "J-12345678-9",
            "quote_type": quote_data.get("quote_type", "VPOS"),
            "pricing_model": quote_data.get("pricing_model", "outsourcing"),
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "branch_details": [],  # Empty branch_details
            "integrator_name": quote_data.get("integrator_name", "Test Integrator"),
            "integrator_app_name": quote_data.get("integrator_app_name", "Test App"),
            "pinpad_model": quote_data.get("pinpad_model", "Ingenico"),
            "cantidad_cajas": quote_data.get("cantidad_cajas", 20),
        }
        
        # Test PDF generation endpoint - returns PDF file directly
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            headers=headers,
            json=pdf_payload
        )
        
        # Should NOT return 500
        assert response.status_code != 500, f"PDF generation returned 500 error: {response.text}"
        assert response.status_code == 200, f"PDF generation failed with {response.status_code}: {response.text}"
        
        # Verify PDF content type
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Verify PDF content starts with PDF header
        assert response.content[:4] == b'%PDF', "Response should be a valid PDF file"
        print(f"✓ PDF generated successfully without branch_details (size: {len(response.content)} bytes)")


class TestSendToImplementationEndpoint:
    """Test send-to-implementation endpoint with multistore data"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_endpoint_exists(self, headers):
        """Verify send-to-implementation endpoint exists"""
        # Test with a non-existent quote to verify endpoint routing
        response = requests.post(
            f"{BASE_URL}/api/quotes/nonexistent_quote/send-to-implementation",
            headers=headers,
            json={"is_multistore": False, "stores": None}
        )
        # Should return 404 (quote not found), not 405 (method not allowed)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ send-to-implementation endpoint exists and routes correctly")
    
    def test_endpoint_accepts_multistore_payload(self, headers):
        """Verify endpoint accepts multistore payload structure"""
        # Test with a non-existent quote but valid payload
        payload = {
            "is_multistore": True,
            "stores": [
                {"name": "Store A", "box_count": 5},
                {"name": "Store B", "box_count": 5}
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/quotes/nonexistent_quote/send-to-implementation",
            headers=headers,
            json=payload
        )
        # Should return 404 (quote not found), not 422 (validation error)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✓ Endpoint accepts multistore payload structure")


class TestQuotesListAPI:
    """Test quotes list API returns branch_details"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_quotes_list_includes_branch_details(self, headers):
        """Verify quotes list API returns branch_details field"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Find our test quote with branch_details
        test_quote = next((q for q in data if q.get("quote_id") == "quo_ad9cb906804b"), None)
        
        if test_quote:
            assert "branch_details" in test_quote, "Quote in list should have branch_details field"
            assert len(test_quote.get("branch_details", [])) == 2, "Should have 2 branches"
            print("✓ Quotes list includes branch_details for quo_ad9cb906804b")
        else:
            print("⚠ Test quote quo_ad9cb906804b not found in list (may have been sent to implementation)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
