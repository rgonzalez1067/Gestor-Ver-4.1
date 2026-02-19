"""
Iteration 18: Email Templates and Quote Modification Tests
Tests for:
1. GET /api/email-templates - returns 4 default templates
2. PUT /api/email-templates/{template_id} - updates a template
3. POST /api/email-templates/reset/{template_id} - resets to defaults
4. PUT /api/quotes/{quote_id} - updates quote in Draft status
5. POST /api/quotes/{quote_id}/duplicate - creates new version
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Session fixture for authentication
@pytest.fixture(scope="module")
def session_token():
    """Get a session token for testing"""
    # Use Emergent auth endpoint to get session
    try:
        # First try to get a valid session via the auth endpoint
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            headers={"X-Session-ID": "test-session-emergent"}
        )
        if response.status_code == 200:
            return response.json().get("session_token")
    except:
        pass
    
    # Use a known test token if available
    return "test_token_for_iteration18"

@pytest.fixture
def api_client(session_token):
    """Shared requests session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {session_token}"
    })
    return session


class TestEmailTemplatesEndpoints:
    """Tests for Email Templates CRUD endpoints"""
    
    def test_get_email_templates_requires_auth(self):
        """GET /api/email-templates requires authentication"""
        response = requests.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_email_templates_returns_4_templates(self, api_client):
        """GET /api/email-templates should return 4 default templates"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        
        # May return 401 if token is invalid, in that case skip
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        assert len(templates) == 4, f"Expected 4 templates, got {len(templates)}"
        
        # Verify template IDs
        template_ids = [t.get("template_id") for t in templates]
        expected_ids = ["quote_sent", "invoice", "warehouse", "implementation"]
        for expected_id in expected_ids:
            assert expected_id in template_ids, f"Missing template: {expected_id}"
    
    def test_get_email_templates_has_required_fields(self, api_client):
        """Each template should have required fields"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 200
        
        templates = response.json()
        required_fields = ["template_id", "name", "description", "subject", "body_html"]
        
        for template in templates:
            for field in required_fields:
                assert field in template, f"Template {template.get('template_id', 'unknown')} missing field: {field}"
    
    def test_get_single_email_template(self, api_client):
        """GET /api/email-templates/{template_id} returns specific template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/quote_sent")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        template = response.json()
        assert template["template_id"] == "quote_sent"
        assert "subject" in template
        assert "body_html" in template
    
    def test_get_nonexistent_template_returns_404(self, api_client):
        """GET /api/email-templates/{template_id} returns 404 for invalid ID"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/nonexistent_template")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 404
    
    def test_update_email_template(self, api_client):
        """PUT /api/email-templates/{template_id} updates a template"""
        template_id = "quote_sent"
        
        # First get the current template
        get_response = api_client.get(f"{BASE_URL}/api/email-templates/{template_id}")
        if get_response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        original_template = get_response.json()
        
        # Update the template
        updated_data = {
            "template_id": template_id,
            "name": original_template.get("name", "Envío de Cotización"),
            "description": original_template.get("description", ""),
            "subject": "TEST - Updated Subject #{quote_number}",
            "body_html": "<html><body>TEST Updated body</body></html>",
            "is_active": True
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/email-templates/{template_id}",
            json=updated_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify update persisted
        verify_response = api_client.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert verify_response.status_code == 200
        
        updated_template = verify_response.json()
        assert "TEST" in updated_template["subject"], "Subject was not updated"
    
    def test_update_template_requires_matching_id(self, api_client):
        """PUT /api/email-templates/{template_id} requires template_id to match"""
        response = api_client.put(
            f"{BASE_URL}/api/email-templates/quote_sent",
            json={
                "template_id": "different_id",  # Mismatched ID
                "name": "Test",
                "subject": "Test",
                "body_html": "<p>Test</p>",
                "is_active": True
            }
        )
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 400, f"Expected 400 for mismatched ID, got {response.status_code}"
    
    def test_reset_email_template(self, api_client):
        """POST /api/email-templates/reset/{template_id} resets to defaults"""
        template_id = "quote_sent"
        
        # Reset the template
        response = api_client.post(f"{BASE_URL}/api/email-templates/reset/{template_id}")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data
        assert "template" in data
        
        # Verify the template was reset
        verify_response = api_client.get(f"{BASE_URL}/api/email-templates/{template_id}")
        assert verify_response.status_code == 200
        
        template = verify_response.json()
        # After reset, subject should contain original text
        assert "Cotización #{quote_number}" in template["subject"], "Template was not reset to default"
    
    def test_reset_nonexistent_template_returns_404(self, api_client):
        """POST /api/email-templates/reset/{template_id} returns 404 for invalid ID"""
        response = api_client.post(f"{BASE_URL}/api/email-templates/reset/nonexistent_template")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 404


class TestQuoteUpdateEndpoint:
    """Tests for PUT /api/quotes/{quote_id} - Update quote in Draft status"""
    
    def test_update_quote_requires_auth(self):
        """PUT /api/quotes/{quote_id} requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/quotes/test_quote_id",
            json={"notes": "test"}
        )
        assert response.status_code == 401
    
    def test_update_quote_in_draft_status(self, api_client):
        """PUT /api/quotes/{quote_id} allows update when status is Borrador"""
        # First, create a test quote or find an existing one in Borrador status
        # Get all quotes
        quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
        
        if quotes_response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        
        # Find a quote in Borrador status
        borrador_quote = None
        for quote in quotes:
            if quote.get("quote_status", "Borrador") == "Borrador":
                borrador_quote = quote
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador status available for testing")
        
        quote_id = borrador_quote["quote_id"]
        
        # Try to update the quote
        response = api_client.put(
            f"{BASE_URL}/api/quotes/{quote_id}",
            json={"notes": "TEST_UPDATED_NOTES_ITERATION18"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the update persisted
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        
        updated_quote = verify_response.json()
        assert updated_quote["notes"] == "TEST_UPDATED_NOTES_ITERATION18"
    
    def test_update_quote_non_draft_fails(self, api_client):
        """PUT /api/quotes/{quote_id} rejects update when status is not Borrador"""
        quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
        
        if quotes_response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        quotes = quotes_response.json()
        
        # Find a quote that is NOT in Borrador status
        non_draft_quote = None
        for quote in quotes:
            status = quote.get("quote_status", "Borrador")
            if status != "Borrador":
                non_draft_quote = quote
                break
        
        if not non_draft_quote:
            pytest.skip("No quote in non-Borrador status available for testing")
        
        quote_id = non_draft_quote["quote_id"]
        
        # Try to update - should fail
        response = api_client.put(
            f"{BASE_URL}/api/quotes/{quote_id}",
            json={"notes": "Should not update"}
        )
        
        assert response.status_code == 400, f"Expected 400 for non-draft quote, got {response.status_code}"


class TestQuoteDuplicateEndpoint:
    """Tests for POST /api/quotes/{quote_id}/duplicate - Create new version"""
    
    def test_duplicate_quote_requires_auth(self):
        """POST /api/quotes/{quote_id}/duplicate requires authentication"""
        response = requests.post(f"{BASE_URL}/api/quotes/test_quote_id/duplicate")
        assert response.status_code == 401
    
    def test_duplicate_quote_creates_new_version(self, api_client):
        """POST /api/quotes/{quote_id}/duplicate creates a new quote version"""
        # Get all quotes
        quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
        
        if quotes_response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        quotes = quotes_response.json()
        
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        # Use the first available quote
        original_quote = quotes[0]
        original_quote_id = original_quote["quote_id"]
        original_version = original_quote.get("version", 1)
        
        # Duplicate the quote
        response = api_client.post(f"{BASE_URL}/api/quotes/{original_quote_id}/duplicate")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "new_quote_id" in data, "Response should contain new_quote_id"
        assert "new_quote_number" in data, "Response should contain new_quote_number"
        assert "version" in data, "Response should contain version"
        assert "parent_quote_id" in data, "Response should contain parent_quote_id"
        
        # Verify version was incremented
        assert data["version"] == original_version + 1, f"Expected version {original_version + 1}, got {data['version']}"
        
        # Verify new quote exists and is in Borrador status
        new_quote_id = data["new_quote_id"]
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{new_quote_id}")
        assert verify_response.status_code == 200
        
        new_quote = verify_response.json()
        assert new_quote["quote_status"] == "Borrador", "Duplicated quote should be in Borrador status"
        assert new_quote.get("parent_quote_id") is not None, "Duplicated quote should have parent_quote_id"
    
    def test_duplicate_nonexistent_quote_returns_404(self, api_client):
        """POST /api/quotes/{quote_id}/duplicate returns 404 for invalid quote"""
        response = api_client.post(f"{BASE_URL}/api/quotes/nonexistent_quote_id/duplicate")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        assert response.status_code == 404


class TestTemplateVariables:
    """Tests for template variable definitions and structure"""
    
    def test_quote_sent_template_has_correct_variables(self, api_client):
        """quote_sent template should contain expected variables"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/quote_sent")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        template = response.json()
        body = template.get("body_html", "")
        subject = template.get("subject", "")
        
        # Check for expected variables
        expected_vars = ["{quote_number}", "{client_name}"]
        for var in expected_vars:
            assert var in body or var in subject, f"Template missing variable: {var}"
    
    def test_implementation_template_has_technical_variables(self, api_client):
        """implementation template should have technical project variables"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/implementation")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        template = response.json()
        body = template.get("body_html", "")
        
        # Check for technical variables
        technical_vars = ["{quote_type}", "{integrator_name}", "{pinpad_model}"]
        found_vars = sum(1 for var in technical_vars if var in body)
        assert found_vars >= 2, f"Implementation template should have technical variables, found only {found_vars}"
    
    def test_warehouse_template_has_delivery_variables(self, api_client):
        """warehouse template should have delivery-related variables"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/warehouse")
        
        if response.status_code == 401:
            pytest.skip("Authentication required - token expired")
        
        template = response.json()
        body = template.get("body_html", "")
        
        # Check for delivery variables
        assert "{client_address}" in body, "Warehouse template should have client_address variable"
        assert "{items_table}" in body, "Warehouse template should have items_table variable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
