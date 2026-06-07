# ruff: noqa
"""
Test iteration 118: Email Templates Body Content Fix, Matrix HTML Separation, and UX Improvements

Features tested:
1. POST /api/email-templates - Uses body_content as field (not body)
2. PUT /api/email-templates/{id} - Uses body_content to update template
3. POST /api/projects/{id}/send-adhoc-email - matrix_html is a separate field
4. POST /api/projects/{id}/send-adhoc-email - 1000 char limit only applies to message field (not matrix_html)
5. GET /api/projects/{id}/suggested-contacts - Returns client and bank contacts
6. GET /api/email-templates - List email templates
7. DELETE /api/email-templates/{id} - Delete template
"""

import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@mega.com",
        "password": "Admin123!"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    # Try registration if login fails
    reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": "admin@mega.com",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "Test"
    })
    if reg_response.status_code in [200, 201]:
        login_again = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        if login_again.status_code == 200:
            return login_again.json().get("session_token")
    pytest.skip("Authentication failed - cannot get token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API requests"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def notified_project_id(auth_headers):
    """Get a project with client_notified=True"""
    response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
    if response.status_code == 200:
        projects = response.json()
        for p in projects:
            if p.get("client_notified"):
                return p["project_id"]
        # If no notified project, use any project
        if projects:
            return projects[0]["project_id"]
    pytest.skip("No projects available for testing")


# ==================== EMAIL TEMPLATES BODY_CONTENT TESTS ====================

class TestEmailTemplateBodyContent:
    """Test email template CRUD using body_content field"""

    def test_create_template_with_body_content(self, auth_headers):
        """Test POST /api/email-templates uses body_content field"""
        unique_name = f"Test Template 118 {uuid.uuid4().hex[:6]}"
        form_data = {
            "name": unique_name,
            "subject": "Test Subject Iteration 118",
            "body_content": "This is the body content for iteration 118 testing."
        }
        response = requests.post(
            f"{BASE_URL}/api/email-templates",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code in [200, 201], f"Expected 200/201 but got {response.status_code}: {response.text}"
        data = response.json()
        assert "template_id" in data, "Response should contain template_id"
        assert data["name"] == unique_name
        assert data.get("body") == "This is the body content for iteration 118 testing."
        return data["template_id"]

    def test_update_template_with_body_content(self, auth_headers):
        """Test PUT /api/email-templates/{id} uses body_content field"""
        # First create a template
        unique_name = f"Update Test 118 {uuid.uuid4().hex[:6]}"
        create_form = {
            "name": unique_name,
            "subject": "Original Subject",
            "body_content": "Original body content"
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/email-templates",
            data=create_form,
            headers=auth_headers
        )
        assert create_resp.status_code in [200, 201], f"Create failed: {create_resp.text}"
        template_id = create_resp.json()["template_id"]

        # Update using body_content (not body)
        update_form = {
            "name": unique_name + " Updated",
            "subject": "Updated Subject 118",
            "body_content": "Updated body content for iteration 118"
        }
        response = requests.put(
            f"{BASE_URL}/api/email-templates/{template_id}",
            data=update_form,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Update failed: {response.text}"

        # Verify the update
        list_resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert list_resp.status_code == 200
        templates = list_resp.json()
        updated = next((t for t in templates if t["template_id"] == template_id), None)
        assert updated is not None
        assert updated["body"] == "Updated body content for iteration 118"
        assert updated["subject"] == "Updated Subject 118"

    def test_template_crud_full_flow(self, auth_headers):
        """Test complete CRUD flow for templates"""
        # CREATE
        unique_name = f"CRUD Flow 118 {uuid.uuid4().hex[:6]}"
        create_form = {
            "name": unique_name,
            "subject": "CRUD Subject",
            "body_content": "CRUD body content"
        }
        create_resp = requests.post(f"{BASE_URL}/api/email-templates", data=create_form, headers=auth_headers)
        assert create_resp.status_code in [200, 201]
        template_id = create_resp.json()["template_id"]

        # READ (via list)
        list_resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert list_resp.status_code == 200
        templates = list_resp.json()
        created = next((t for t in templates if t["template_id"] == template_id), None)
        assert created is not None
        assert created["name"] == unique_name

        # UPDATE
        update_form = {
            "name": unique_name + " UPDATED",
            "subject": "CRUD Updated Subject",
            "body_content": "CRUD updated body"
        }
        update_resp = requests.put(f"{BASE_URL}/api/email-templates/{template_id}", data=update_form, headers=auth_headers)
        assert update_resp.status_code == 200

        # DELETE
        delete_resp = requests.delete(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
        assert delete_resp.status_code == 200

        # Verify deleted
        list_after = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        templates_after = list_after.json()
        deleted = next((t for t in templates_after if t["template_id"] == template_id), None)
        assert deleted is None


# ==================== MATRIX HTML SEPARATION TESTS ====================

class TestMatrixHtmlSeparation:
    """Test that matrix_html is separate from message char limit"""

    def test_adhoc_email_with_matrix_html_separate_field(self, auth_headers, notified_project_id):
        """Test POST /api/projects/{id}/send-adhoc-email accepts matrix_html as separate field"""
        # Message at exactly 1000 chars (max allowed)
        message = "A" * 1000
        # Matrix HTML can be any size - it's separate
        matrix_html = """
        <table border="1" style="width:100%;">
            <tr><th>Banco</th><th>Producto</th><th>Estado</th></tr>
            <tr><td>Banco Test</td><td>Producto Test</td><td>Completado</td></tr>
        </table>
        """ * 10  # About 3000+ chars
        
        form_data = {
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Test Matrix HTML Separate Field",
            "message": message,
            "matrix_html": matrix_html
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200 but got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data.get("message", "").lower() or "enviado" in data.get("message", "").lower()

    def test_message_limit_1000_chars_only(self, auth_headers, notified_project_id):
        """Test that 1000 char limit applies only to message, not matrix_html"""
        # Message over 1000 chars should fail
        message_over = "B" * 1001
        form_data = {
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Test Over 1000 chars",
            "message": message_over
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 400, "Should reject message over 1000 chars"
        assert "1000" in response.json().get("detail", "")

    def test_message_1000_with_large_matrix_works(self, auth_headers, notified_project_id):
        """Test 1000 char message + large matrix_html works (matrix doesn't count)"""
        message = "C" * 1000  # Exactly at limit
        # Very large matrix
        matrix_html = "<div>" + ("X" * 5000) + "</div>"
        
        form_data = {
            "recipients": json.dumps(["matrix.test@example.com"]),
            "subject": "Large Matrix Test",
            "message": message,
            "matrix_html": matrix_html
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Should accept: message at 1000 + large matrix. Got {response.status_code}: {response.text}"

    def test_bitacora_includes_matrix_tag(self, auth_headers, notified_project_id):
        """Test bitácora entry shows [+Matriz] when matrix is attached"""
        form_data = {
            "recipients": json.dumps(["bitacora.matrix@example.com"]),
            "subject": f"Matrix Tag Test {uuid.uuid4().hex[:6]}",
            "message": "Testing matrix tag in bitacora",
            "matrix_html": "<table><tr><td>Test</td></tr></table>"
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 200

        # Check bitácora for [+Matriz] tag
        bitacora_resp = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/bitacora",
            headers=auth_headers
        )
        assert bitacora_resp.status_code == 200
        entries = bitacora_resp.json()
        
        # Find entry with matrix tag
        found_matrix_tag = False
        for entry in entries:
            if "[+Matriz]" in entry.get("text", ""):
                found_matrix_tag = True
                break
        
        assert found_matrix_tag, "Bitácora entry should include [+Matriz] tag when matrix is attached"


# ==================== SUGGESTED CONTACTS TESTS ====================

class TestSuggestedContacts:
    """Test suggested contacts for notifications dialog"""

    def test_suggested_contacts_returns_contacts(self, auth_headers, notified_project_id):
        """Test GET /api/projects/{id}/suggested-contacts returns contact list"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/suggested-contacts",
            headers=auth_headers
        )
        assert response.status_code == 200
        contacts = response.json()
        assert isinstance(contacts, list)
        # Each contact should have required fields
        for contact in contacts:
            assert "email" in contact
            assert "label" in contact
            assert "source" in contact
            assert contact["source"] in ["client", "bank"]

    def test_suggested_contacts_invalid_project(self, auth_headers):
        """Test 404 for invalid project ID"""
        response = requests.get(
            f"{BASE_URL}/api/projects/invalid_id_12345/suggested-contacts",
            headers=auth_headers
        )
        assert response.status_code == 404


# ==================== TEMPLATE SELECT AUTO-FILL TESTS ====================

class TestTemplateSelectFunctionality:
    """Test template select populates subject and message"""

    def test_template_body_stored_correctly(self, auth_headers):
        """Test that template body is stored and retrieved correctly"""
        # Create template with specific body
        unique_name = f"AutoFill Test {uuid.uuid4().hex[:6]}"
        expected_body = "Este es el cuerpo del mensaje predefinido para la plantilla."
        expected_subject = "Asunto de Plantilla AutoFill"
        
        create_form = {
            "name": unique_name,
            "subject": expected_subject,
            "body_content": expected_body
        }
        create_resp = requests.post(f"{BASE_URL}/api/email-templates", data=create_form, headers=auth_headers)
        assert create_resp.status_code in [200, 201]
        template_id = create_resp.json()["template_id"]

        # Retrieve and verify
        list_resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert list_resp.status_code == 200
        templates = list_resp.json()
        
        template = next((t for t in templates if t["template_id"] == template_id), None)
        assert template is not None
        assert template["subject"] == expected_subject
        assert template["body"] == expected_body

        # Cleanup
        requests.delete(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
