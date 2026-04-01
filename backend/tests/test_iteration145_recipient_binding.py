"""
Iteration 145: Test recipient data binding for project notifications
- Client emails from contacts[] array (not placeholders)
- Bank emails from contact_email field
- No placeholder emails like cliente@ejemplo.com
- additional_recipients (CC) support in send-notification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@meganexus.com"
ADMIN_PASSWORD = "Admin123!"
PROJECT_ID = "prj_c536858da780"

# Expected real emails from DB
EXPECTED_CLIENT_EMAILS = ["rgonzalez@megasoft.com.ve", "jdolande@megasoft.com.ve"]
EXPECTED_BANK_EMAIL = "rgonzalez@megasoft.com.ve"
BANK_NAME = "Banco Mercantil"

# Placeholder emails that should NOT appear
PLACEHOLDER_EMAILS = ["cliente@ejemplo.com", "contacto@banco.com", "example@example.com"]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("session_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestClientRecipientBinding:
    """Test that client notification recipients come from contacts[] array"""
    
    def test_preview_client_notification_returns_real_emails(self, auth_headers):
        """POST /api/projects/{id}/preview-notification for client returns real emails from contacts[]"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        recipients = data.get("recipients", [])
        
        # Should have recipients
        assert len(recipients) > 0, "No recipients returned for client notification"
        
        # Recipients should be real emails from contacts[]
        for email in recipients:
            assert email in EXPECTED_CLIENT_EMAILS, f"Unexpected email: {email}. Expected one of: {EXPECTED_CLIENT_EMAILS}"
        
        # Should contain at least the primary contact email
        assert EXPECTED_CLIENT_EMAILS[0] in recipients, f"Primary contact email {EXPECTED_CLIENT_EMAILS[0]} not in recipients"
        
        print(f"✓ Client recipients: {recipients}")
    
    def test_preview_client_notification_no_placeholders(self, auth_headers):
        """Verify no placeholder emails in client notification recipients"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={"target": "client", "bank_name": None},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        recipients = data.get("recipients", [])
        
        # No placeholder emails should be present
        for placeholder in PLACEHOLDER_EMAILS:
            assert placeholder not in recipients, f"Placeholder email {placeholder} found in recipients"
        
        print(f"✓ No placeholder emails in client recipients")


class TestBankRecipientBinding:
    """Test that bank notification recipients come from contact_email field"""
    
    def test_preview_bank_notification_returns_real_email(self, auth_headers):
        """POST /api/projects/{id}/preview-notification for bank returns real email from contact_email"""
        # First ensure client is notified (required for bank notifications)
        requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={"target": "client", "bank_name": None},
            headers=auth_headers
        )
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={"target": "bank", "bank_name": BANK_NAME},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        recipients = data.get("recipients", [])
        
        # Should have recipients
        assert len(recipients) > 0, "No recipients returned for bank notification"
        
        # Should contain the bank's contact_email
        assert EXPECTED_BANK_EMAIL in recipients, f"Bank contact_email {EXPECTED_BANK_EMAIL} not in recipients: {recipients}"
        
        print(f"✓ Bank recipients: {recipients}")
    
    def test_preview_bank_notification_no_placeholders(self, auth_headers):
        """Verify no placeholder emails in bank notification recipients"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={"target": "bank", "bank_name": BANK_NAME},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        recipients = data.get("recipients", [])
        
        # No placeholder emails should be present
        for placeholder in PLACEHOLDER_EMAILS:
            assert placeholder not in recipients, f"Placeholder email {placeholder} found in bank recipients"
        
        print(f"✓ No placeholder emails in bank recipients")


class TestAdditionalRecipientsCC:
    """Test additional_recipients (CC) support in send-notification"""
    
    def test_send_notification_accepts_additional_recipients(self, auth_headers):
        """POST /api/projects/{id}/send-notification accepts additional_recipients array for CC"""
        cc_emails = ["test-cc1@example.com", "test-cc2@example.com"]
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={
                "target": "client",
                "bank_name": None,
                "additional_recipients": cc_emails
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert data.get("status") in ["sent", "simulated"], f"Unexpected status: {data.get('status')}"
        
        print(f"✓ Send notification with CC accepted: {data.get('message')}")
    
    def test_notification_history_stores_cc_recipients(self, auth_headers):
        """Verify CC recipients are stored in notification history"""
        cc_emails = ["history-cc@example.com"]
        
        # Send notification with CC
        send_response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={
                "target": "client",
                "bank_name": None,
                "additional_recipients": cc_emails
            },
            headers=auth_headers
        )
        assert send_response.status_code == 200
        
        # Get notification history
        history_response = requests.get(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/notification-history",
            headers=auth_headers
        )
        assert history_response.status_code == 200
        
        history = history_response.json()
        client_history = history.get("client", [])
        
        # Find the latest entry
        assert len(client_history) > 0, "No client notification history found"
        latest_entry = client_history[-1]
        
        # Check CC is stored
        cc_in_history = latest_entry.get("cc", [])
        assert "history-cc@example.com" in cc_in_history, f"CC email not found in history. CC in history: {cc_in_history}"
        
        print(f"✓ CC recipients stored in history: {cc_in_history}")
    
    def test_send_notification_with_empty_cc(self, auth_headers):
        """Send notification with empty additional_recipients should work"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={
                "target": "client",
                "bank_name": None,
                "additional_recipients": []
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        print(f"✓ Send notification with empty CC works")
    
    def test_send_notification_with_null_cc(self, auth_headers):
        """Send notification with null additional_recipients should work"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={
                "target": "client",
                "bank_name": None,
                "additional_recipients": None
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        print(f"✓ Send notification with null CC works")


class TestBankNotificationWithCC:
    """Test CC support for bank notifications"""
    
    def test_send_bank_notification_with_cc(self, auth_headers):
        """Send bank notification with additional_recipients"""
        cc_emails = ["bank-cc@example.com"]
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            json={
                "target": "bank",
                "bank_name": BANK_NAME,
                "additional_recipients": cc_emails
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send bank notification failed: {response.text}"
        
        data = response.json()
        assert data.get("target") == "bank"
        assert data.get("bank_name") == BANK_NAME
        
        print(f"✓ Bank notification with CC sent: {data.get('message')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
