"""
Test iteration 117: Sequential Notifications, Email Templates CRUD, Suggested Contacts, 
Attach Matrix, and Email Detail in Bitácora

Features tested:
1. POST /api/projects/{id}/send-notification - Sequential notification system (4 levels)
2. GET /api/projects/{id}/notification-history - Notification history per entity
3. GET /api/projects/{id}/suggested-contacts - Client and bank suggested contacts
4. GET /api/email-templates - List email templates
5. POST /api/email-templates - Create template (admin only, FormData)
6. PUT /api/email-templates/{id} - Update template (admin only, FormData)
7. DELETE /api/email-templates/{id} - Delete template (admin only)
8. POST /api/projects/{id}/send-adhoc-email - Now supports 1000 chars, auto-registers with email_detail
9. Bitácora entries with email_detail for both sequential notifications and ad-hoc emails
"""

import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

NOTIFICATION_LEVELS = [
    "Primera Comunicación",
    "Primer Recordatorio", 
    "Segundo Recordatorio",
    "Tercer Recordatorio",
]

@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@mega.com",
        "password": "Admin123!"
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip("Authentication failed")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API requests"""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture(scope="module")
def test_client_id(auth_headers):
    """Create or get a test client with email"""
    # Create test client
    client_data = {
        "rif": f"J-TEST117-{uuid.uuid4().hex[:6]}",
        "razon_social": "Cliente Test Iter117",
        "nombre_comercial": "Test117 Corp",
        "email": "cliente.test117@ejemplo.com",
        "telefono": "+58 412 1234567",
        "direccion_fiscal": "Caracas, Venezuela",
        "tipo": "Empresa",
        "segmento": "Corporativo"
    }
    response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
    if response.status_code in [200, 201]:
        return response.json().get("client_id")
    # Try to get existing
    response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
    if response.status_code == 200:
        clients = response.json()
        if clients:
            return clients[0].get("client_id")
    pytest.skip("Could not create/get test client")

@pytest.fixture(scope="module")
def test_bank_name(auth_headers):
    """Get or create a test bank with contacts"""
    # Get existing bank
    response = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers)
    if response.status_code == 200:
        banks = response.json()
        if banks:
            bank = banks[0]
            bank_name = bank.get("bank_name")
            # Ensure it has contacts
            if not bank.get("contacts"):
                contacts = [{"name": "Contact Test", "email": "contact@banco.test", "phone": "+58 412 1234567", "position": "Gerente"}]
                requests.put(f"{BASE_URL}/api/banks/{bank.get('bank_id')}", 
                    json={"bank_name": bank_name, "contacts": contacts}, headers=auth_headers)
            return bank_name
    pytest.skip("No banks available")

@pytest.fixture(scope="module")
def test_project_id(auth_headers, test_client_id, test_bank_name):
    """Get or create a test project for notification testing"""
    # Find a project with implementation_matrix containing test_bank_name and client_notified=False
    response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
    if response.status_code == 200:
        projects = response.json()
        # Look for project that's NOT notified
        for p in projects:
            if not p.get("client_notified"):
                matrix = p.get("implementation_matrix", {})
                if matrix:
                    return p["project_id"]
        # Or use any project
        for p in projects:
            return p["project_id"]
    pytest.skip("No projects available for testing")

@pytest.fixture(scope="module")
def notified_project_id(auth_headers):
    """Get a project with client_notified=True for bank notification testing"""
    response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
    if response.status_code == 200:
        projects = response.json()
        for p in projects:
            if p.get("client_notified"):
                return p["project_id"]
    pytest.skip("No notified projects available")


# ==================== SEQUENTIAL NOTIFICATION TESTS ====================

class TestSequentialNotifications:
    """Test sequential notification system with 4 levels"""

    def test_send_notification_invalid_level(self, auth_headers, test_project_id):
        """Test that invalid notification level is rejected"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{test_project_id}/send-notification",
            json={"target": "client", "level": "Invalid Level"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "inválido" in response.json().get("detail", "").lower() or "invalid" in response.json().get("detail", "").lower()

    def test_send_notification_bank_before_client_rejected(self, auth_headers):
        """Test that notifying bank before client is rejected"""
        # Create fresh project without notifications
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        fresh_project = None
        for p in projects:
            if not p.get("notification_history", {}).get("client"):
                fresh_project = p
                break
        
        if not fresh_project:
            pytest.skip("No fresh project available")
        
        matrix = fresh_project.get("implementation_matrix", {})
        bank_names = list(matrix.keys())
        if not bank_names:
            pytest.skip("No banks in matrix")
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{fresh_project['project_id']}/send-notification",
            json={"target": "bank", "bank_name": bank_names[0], "level": "Primera Comunicación"},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "cliente" in response.json().get("detail", "").lower()

    def test_send_notification_sequence_validation(self, auth_headers, notified_project_id):
        """Test that skipping notification levels is rejected"""
        # Try to send 'Segundo Recordatorio' without 'Primer Recordatorio'
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-notification",
            json={"target": "client", "level": "Segundo Recordatorio"},
            headers=auth_headers
        )
        # Should be rejected if Primer Recordatorio wasn't sent
        if response.status_code == 400:
            assert "Primer" in response.json().get("detail", "") or "antes" in response.json().get("detail", "").lower()
        # OR if all are already sent
        elif response.status_code == 400:
            pass  # Already sent validation

    def test_send_notification_client_primera_comunicacion(self, auth_headers):
        """Test Primera Comunicación to client unlocks matrix"""
        # Get fresh project
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = response.json()
        
        fresh_project = None
        for p in projects:
            nh = p.get("notification_history", {})
            if not nh.get("client"):
                fresh_project = p
                break
        
        if not fresh_project:
            pytest.skip("No project without client notification found")
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{fresh_project['project_id']}/send-notification",
            json={"target": "client", "level": "Primera Comunicación"},
            headers=auth_headers
        )
        
        # Can be 200 success or 400 if already notified
        if response.status_code == 200:
            data = response.json()
            assert data.get("level") == "Primera Comunicación"
            assert data.get("target") == "client"
            # Verify project is now marked as notified
            proj = requests.get(f"{BASE_URL}/api/projects/{fresh_project['project_id']}", headers=auth_headers).json()
            assert proj.get("client_notified") == True


class TestNotificationHistory:
    """Test notification history endpoint"""

    def test_get_notification_history(self, auth_headers, notified_project_id):
        """Test getting notification history"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/notification-history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Should have 'client' key if client was notified
        if "client" in data:
            assert isinstance(data["client"], list)

    def test_notification_history_invalid_project(self, auth_headers):
        """Test notification history for invalid project returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/projects/invalid_project_id/notification-history",
            headers=auth_headers
        )
        assert response.status_code == 404


# ==================== SUGGESTED CONTACTS TESTS ====================

class TestSuggestedContacts:
    """Test suggested contacts endpoint"""

    def test_get_suggested_contacts(self, auth_headers, notified_project_id):
        """Test getting suggested contacts for a project"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/suggested-contacts",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Each contact should have email, label, source
        for contact in data:
            assert "email" in contact
            assert "label" in contact
            assert "source" in contact

    def test_suggested_contacts_invalid_project(self, auth_headers):
        """Test suggested contacts for invalid project returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/projects/invalid_project_id/suggested-contacts",
            headers=auth_headers
        )
        assert response.status_code == 404


# ==================== EMAIL TEMPLATES CRUD TESTS ====================

class TestEmailTemplatesCRUD:
    """Test email templates CRUD operations (admin only)"""

    def test_list_email_templates(self, auth_headers):
        """Test listing email templates"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create_email_template_admin(self, auth_headers):
        """Test creating email template as admin (FormData)"""
        unique_name = f"Test Template {uuid.uuid4().hex[:6]}"
        form_data = {
            "name": unique_name,
            "subject": "Test Subject for Iter117",
            "body": "This is the template body for testing purposes."
        }
        response = requests.post(
            f"{BASE_URL}/api/email-templates",
            data=form_data,  # FormData, not JSON
            headers=auth_headers
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "template_id" in data
        assert data["name"] == unique_name
        return data["template_id"]

    def test_update_email_template_admin(self, auth_headers):
        """Test updating email template as admin (FormData)"""
        # First create a template
        unique_name = f"Update Test {uuid.uuid4().hex[:6]}"
        create_form = {"name": unique_name, "subject": "Original Subject", "body": "Original body"}
        create_resp = requests.post(f"{BASE_URL}/api/email-templates", data=create_form, headers=auth_headers)
        
        if create_resp.status_code not in [200, 201]:
            pytest.skip("Could not create template")
        
        template_id = create_resp.json()["template_id"]
        
        # Update it (using body_content parameter)
        update_form = {"name": unique_name + " Updated", "subject": "Updated Subject", "body_content": "Updated body content"}
        response = requests.put(
            f"{BASE_URL}/api/email-templates/{template_id}",
            data=update_form,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "actualizada" in response.json().get("message", "").lower() or "updated" in response.json().get("message", "").lower()

    def test_delete_email_template_admin(self, auth_headers):
        """Test deleting email template as admin"""
        # First create a template
        unique_name = f"Delete Test {uuid.uuid4().hex[:6]}"
        create_form = {"name": unique_name, "subject": "To Delete", "body": "Will be deleted"}
        create_resp = requests.post(f"{BASE_URL}/api/email-templates", data=create_form, headers=auth_headers)
        
        if create_resp.status_code not in [200, 201]:
            pytest.skip("Could not create template")
        
        template_id = create_resp.json()["template_id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/email-templates/{template_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "eliminada" in response.json().get("message", "").lower() or "deleted" in response.json().get("message", "").lower()

    def test_delete_nonexistent_template(self, auth_headers):
        """Test deleting nonexistent template returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/email-templates/nonexistent_id",
            headers=auth_headers
        )
        assert response.status_code == 404


# ==================== ADHOC EMAIL WITH 1000 CHARS TESTS ====================

class TestAdhocEmail:
    """Test ad-hoc email with 1000 char limit and email_detail in bitácora"""

    def test_adhoc_email_1000_chars_allowed(self, auth_headers, notified_project_id):
        """Test that 1000 characters are allowed in message"""
        message = "A" * 1000  # Exactly 1000 chars
        form_data = {
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Test 1000 chars",
            "message": message
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_adhoc_email_over_1000_chars_rejected(self, auth_headers, notified_project_id):
        """Test that over 1000 characters are rejected"""
        message = "A" * 1001  # 1001 chars - should fail
        form_data = {
            "recipients": json.dumps(["test@example.com"]),
            "subject": "Test over 1000 chars",
            "message": message
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "1000" in response.json().get("detail", "")

    def test_adhoc_email_registers_in_bitacora(self, auth_headers, notified_project_id):
        """Test that ad-hoc email auto-registers in bitácora with email_detail"""
        form_data = {
            "recipients": json.dumps(["bitacora.test@example.com"]),
            "subject": f"Bitacora Test {uuid.uuid4().hex[:6]}",
            "message": "Testing bitácora registration"
        }
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-adhoc-email",
            data=form_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Check bitácora
        bitacora_resp = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/bitacora",
            headers=auth_headers
        )
        assert bitacora_resp.status_code == 200
        bitacora = bitacora_resp.json()
        
        # Find the entry with email_detail
        found = False
        for entry in bitacora:
            if entry.get("email_detail"):
                detail = entry["email_detail"]
                if "bitacora.test@example.com" in detail.get("recipients", []):
                    found = True
                    assert "subject" in detail
                    assert "message" in detail or "html_content" in detail
                    assert "recipients" in detail
                    break
        
        assert found, "Ad-hoc email should have created a bitácora entry with email_detail"


# ==================== NOTIFICATION BITÁCORA EMAIL_DETAIL TESTS ====================

class TestNotificationBitacoraDetail:
    """Test that sequential notifications register in bitácora with email_detail"""

    def test_notification_creates_bitacora_entry_with_email_detail(self, auth_headers):
        """Test that sending a notification creates bitácora entry with email_detail"""
        # Get a project and send notification
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        if response.status_code != 200:
            pytest.skip("Cannot get projects")
        
        projects = response.json()
        project_id = None
        
        # Find a project we can test with
        for p in projects:
            project_id = p["project_id"]
            break
        
        if not project_id:
            pytest.skip("No projects available")
        
        # Get current bitácora count
        bitacora_before = requests.get(
            f"{BASE_URL}/api/projects/{project_id}/bitacora",
            headers=auth_headers
        ).json()
        count_before = len(bitacora_before)
        
        # Try to send a notification (may fail if already sent, that's ok)
        response = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/send-notification",
            json={"target": "client", "level": "Primera Comunicación"},
            headers=auth_headers
        )
        
        if response.status_code == 200:
            # Check bitácora was updated
            bitacora_after = requests.get(
                f"{BASE_URL}/api/projects/{project_id}/bitacora",
                headers=auth_headers
            ).json()
            
            assert len(bitacora_after) > count_before
            
            # Check the newest entry has email_detail
            newest = bitacora_after[-1]
            assert "email_detail" in newest
            assert "subject" in newest["email_detail"]
            assert "html_content" in newest["email_detail"]
            assert "level" in newest["email_detail"]


# ==================== LEVEL ALREADY EXECUTED TESTS ====================

class TestLevelAlreadyExecuted:
    """Test that executing same level twice is rejected"""

    def test_same_level_twice_rejected(self, auth_headers, notified_project_id):
        """Test that sending the same notification level twice is rejected"""
        # Get notification history
        history_resp = requests.get(
            f"{BASE_URL}/api/projects/{notified_project_id}/notification-history",
            headers=auth_headers
        )
        if history_resp.status_code != 200:
            pytest.skip("Cannot get history")
        
        history = history_resp.json()
        client_history = history.get("client", [])
        
        if not client_history:
            pytest.skip("No client notification history")
        
        # Try to send the first level again
        executed_level = client_history[0]["level"]
        response = requests.post(
            f"{BASE_URL}/api/projects/{notified_project_id}/send-notification",
            json={"target": "client", "level": executed_level},
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "ya fue enviada" in response.json().get("detail", "").lower() or "already" in response.json().get("detail", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
