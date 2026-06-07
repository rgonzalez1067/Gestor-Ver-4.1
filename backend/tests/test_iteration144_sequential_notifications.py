# ruff: noqa
"""
Test Iteration 144: Sequential Notifications with Auto-Prefix by Send Count

Tests the new notification system where:
- POST /api/projects/{id}/send-notification no longer requires 'level' field
- POST /api/projects/{id}/preview-notification no longer requires 'level'
- Prefix is auto-calculated: 0=Primer Envío, 1=Primer Recordatorio, 2=Segundo Recordatorio, 3+=Tercer Recordatorio
- Bank notifications require client to be notified first
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

NOTIFICATION_PREFIXES = ['Primer Envío', 'Primer Recordatorio', 'Segundo Recordatorio', 'Tercer Recordatorio']

# Test project ID (multistore with banks)
TEST_PROJECT_ID = 'prj_c536858da780'


@pytest.fixture(scope="module")
def session_token():
    """Get session token for admin user"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@meganexus.com",
        "password": "Admin123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("session_token")


@pytest.fixture(scope="module")
def auth_headers(session_token):
    """Auth headers with session_token"""
    return {"Authorization": f"Bearer {session_token}"}


@pytest.fixture(scope="function")
def reset_notification_history(auth_headers):
    """Reset notification_history before each test"""
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    
    async def reset():
        client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
        db = client['test_database']
        await db.projects.update_one(
            {'project_id': TEST_PROJECT_ID},
            {'$set': {'notification_history': {}}}
        )
        client.close()
    
    asyncio.run(reset())
    yield
    # Cleanup after test
    asyncio.run(reset())


class TestPreviewNotificationAutoPrefix:
    """Test preview-notification endpoint with auto-prefix calculation"""
    
    def test_preview_client_first_send_returns_primer_envio(self, auth_headers, reset_notification_history):
        """First preview for client should return 'Primer Envío' prefix"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        
        # Verify auto-calculated prefix
        assert data.get("prefix") == "Primer Envío", f"Expected 'Primer Envío', got {data.get('prefix')}"
        assert data.get("send_number") == 1, f"Expected send_number=1, got {data.get('send_number')}"
        assert "[Primer Envío]" in data.get("subject", ""), f"Subject should contain [Primer Envío]: {data.get('subject')}"
    
    def test_preview_does_not_require_level_field(self, auth_headers, reset_notification_history):
        """Preview endpoint should work without 'level' field in body"""
        # Only send target, no level
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview should work without level: {response.text}"
        
        # Verify response structure
        data = response.json()
        assert "prefix" in data
        assert "send_number" in data
        assert "subject" in data
        assert "html" in data


class TestSendNotificationAutoPrefix:
    """Test send-notification endpoint with auto-prefix calculation"""
    
    def test_send_client_first_notification_primer_envio(self, auth_headers, reset_notification_history):
        """First send to client should use 'Primer Envío' prefix"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send failed: {response.text}"
        data = response.json()
        
        # Verify auto-calculated prefix
        assert data.get("level") == "Primer Envío", f"Expected 'Primer Envío', got {data.get('level')}"
        assert data.get("send_number") == 1, f"Expected send_number=1, got {data.get('send_number')}"
        assert "[Primer Envío]" in data.get("message", ""), "Message should contain [Primer Envío]"
    
    def test_send_client_second_notification_primer_recordatorio(self, auth_headers, reset_notification_history):
        """Second send to client should use 'Primer Recordatorio' prefix"""
        # First send
        response1 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response1.status_code == 200
        
        # Second send
        response2 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response2.status_code == 200, f"Second send failed: {response2.text}"
        data = response2.json()
        
        assert data.get("level") == "Primer Recordatorio", f"Expected 'Primer Recordatorio', got {data.get('level')}"
        assert data.get("send_number") == 2
    
    def test_send_client_third_notification_segundo_recordatorio(self, auth_headers, reset_notification_history):
        """Third send to client should use 'Segundo Recordatorio' prefix"""
        # Send 1, 2
        for _ in range(2):
            requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
                json={"target": "client"},
                headers=auth_headers
            )
        
        # Third send
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("level") == "Segundo Recordatorio", f"Expected 'Segundo Recordatorio', got {data.get('level')}"
        assert data.get("send_number") == 3
    
    def test_send_client_fourth_notification_tercer_recordatorio(self, auth_headers, reset_notification_history):
        """Fourth send to client should use 'Tercer Recordatorio' prefix"""
        # Send 1, 2, 3
        for _ in range(3):
            requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
                json={"target": "client"},
                headers=auth_headers
            )
        
        # Fourth send
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("level") == "Tercer Recordatorio", f"Expected 'Tercer Recordatorio', got {data.get('level')}"
        assert data.get("send_number") == 4
    
    def test_send_does_not_require_level_field(self, auth_headers, reset_notification_history):
        """Send endpoint should work without 'level' field in body"""
        # Only send target, no level
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Send should work without level: {response.text}"
        
        # Verify response structure
        data = response.json()
        assert "level" in data
        assert "send_number" in data
        assert "message" in data


class TestBankNotificationValidation:
    """Test bank notification requires client to be notified first"""
    
    def test_bank_notification_requires_client_first(self, auth_headers):
        """Bank notification should fail if client hasn't been notified"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Reset notification_history AND client_notified flag
        async def reset_all():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client['test_database']
            await db.projects.update_one(
                {'project_id': TEST_PROJECT_ID},
                {'$set': {'notification_history': {}, 'client_notified': False}}
            )
            client.close()
        
        asyncio.run(reset_all())
        
        # Try to send bank notification without client notification
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "bank", "bank_name": "Banco Mercantil"},
            headers=auth_headers
        )
        
        # Should fail with 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "cliente" in response.json().get("detail", "").lower()
        
        # Restore client_notified flag
        async def restore():
            client = AsyncIOMotorClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
            db = client['test_database']
            await db.projects.update_one(
                {'project_id': TEST_PROJECT_ID},
                {'$set': {'client_notified': True}}
            )
            client.close()
        
        asyncio.run(restore())
    
    def test_bank_notification_works_after_client_notified(self, auth_headers, reset_notification_history):
        """Bank notification should work after client has been notified"""
        # First notify client
        response1 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response1.status_code == 200
        
        # Now bank notification should work
        response2 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "bank", "bank_name": "Banco Mercantil"},
            headers=auth_headers
        )
        assert response2.status_code == 200, f"Bank notification failed: {response2.text}"
        data = response2.json()
        
        # First bank notification should be "Primer Envío"
        assert data.get("level") == "Primer Envío"
        assert data.get("send_number") == 1
        assert data.get("target") == "bank"
        assert data.get("bank_name") == "Banco Mercantil"


class TestNotificationHistoryPersistence:
    """Test that notification history is correctly persisted and used for prefix calculation"""
    
    def test_history_increments_correctly(self, auth_headers, reset_notification_history):
        """Verify notification history increments with each send"""
        # Send 3 notifications
        for i in range(3):
            response = requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
                json={"target": "client"},
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("send_number") == i + 1
        
        # Get notification history
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/notification-history",
            headers=auth_headers
        )
        assert response.status_code == 200
        history = response.json()
        
        # Verify client history has 3 entries
        client_history = history.get("client", [])
        assert len(client_history) == 3, f"Expected 3 entries, got {len(client_history)}"
        
        # Verify levels are correct
        expected_levels = ["Primer Envío", "Primer Recordatorio", "Segundo Recordatorio"]
        for i, entry in enumerate(client_history):
            assert entry.get("level") == expected_levels[i], f"Entry {i} has wrong level"
            assert entry.get("send_number") == i + 1
    
    def test_preview_reflects_current_history_count(self, auth_headers, reset_notification_history):
        """Preview should reflect the current history count for next send"""
        # Send 2 notifications
        for _ in range(2):
            requests.post(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
                json={"target": "client"},
                headers=auth_headers
            )
        
        # Preview should show "Segundo Recordatorio" (3rd send)
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/preview-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("prefix") == "Segundo Recordatorio"
        assert data.get("send_number") == 3


class TestBankNotificationSequence:
    """Test bank notifications have their own sequence separate from client"""
    
    def test_bank_has_independent_sequence(self, auth_headers, reset_notification_history):
        """Each bank should have its own notification sequence"""
        # First notify client
        requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "client"},
            headers=auth_headers
        )
        
        # Send to first bank
        response1 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "bank", "bank_name": "Banco Mercantil"},
            headers=auth_headers
        )
        assert response1.status_code == 200
        assert response1.json().get("level") == "Primer Envío"
        assert response1.json().get("send_number") == 1
        
        # Send to second bank (should also be "Primer Envío")
        response2 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "bank", "bank_name": "Bancamiga"},
            headers=auth_headers
        )
        assert response2.status_code == 200
        assert response2.json().get("level") == "Primer Envío"
        assert response2.json().get("send_number") == 1
        
        # Send again to first bank (should be "Primer Recordatorio")
        response3 = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/send-notification",
            json={"target": "bank", "bank_name": "Banco Mercantil"},
            headers=auth_headers
        )
        assert response3.status_code == 200
        assert response3.json().get("level") == "Primer Recordatorio"
        assert response3.json().get("send_number") == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
