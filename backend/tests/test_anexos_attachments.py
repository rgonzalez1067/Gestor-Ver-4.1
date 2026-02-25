"""
Test suite for the Anexos (Attachments) module - Iteration 42
Tests for: GET, POST, DELETE attachment endpoints
"""
import pytest
import requests
import os
import json
from io import BytesIO

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test_anexos@test.com"
TEST_PASSWORD = "Test1234!"

# Valid attachment categories
VALID_CATEGORIES = [
    "Cotización Original",
    "Orden de Compra",
    "Factura",
    "Otros"
]


class TestAnexosAttachments:
    """Test suite for Attachment/Anexos endpoints"""
    
    session_token = None
    test_quote_id = None
    test_attachment_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self, api_client):
        """Setup: Login and get a quote_id for testing"""
        # Login to get session token
        if not TestAnexosAttachments.session_token:
            login_response = api_client.post(f"{BASE_URL}/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            if login_response.status_code == 200:
                TestAnexosAttachments.session_token = login_response.json().get("session_token")
                print(f"✓ Logged in successfully, token obtained")
            else:
                pytest.skip(f"Cannot login: {login_response.status_code} - {login_response.text}")
        
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        # Get existing quotes to find a test quote
        if not TestAnexosAttachments.test_quote_id:
            quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
            if quotes_response.status_code == 200:
                quotes = quotes_response.json()
                if quotes and len(quotes) > 0:
                    TestAnexosAttachments.test_quote_id = quotes[0].get("quote_id")
                    print(f"✓ Using quote_id: {TestAnexosAttachments.test_quote_id}")
                else:
                    pytest.skip("No quotes available for testing")
            else:
                pytest.skip(f"Cannot fetch quotes: {quotes_response.status_code}")

    def test_01_login_success(self, api_client):
        """Test login endpoint returns session_token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "session_token not in response"
        assert "user" in data, "user not in response"
        print(f"✓ Login successful, user: {data['user'].get('email')}")

    def test_02_get_attachments_empty_or_existing(self, api_client):
        """Test GET /api/quotes/{quote_id}/attachments returns list"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        assert response.status_code == 200, f"GET attachments failed: {response.text}"
        
        data = response.json()
        assert "attachments" in data, "attachments field missing in response"
        assert "quote_id" in data, "quote_id field missing in response"
        assert isinstance(data["attachments"], list), "attachments should be a list"
        print(f"✓ GET attachments successful, found {len(data['attachments'])} attachment(s)")

    def test_03_upload_attachment_cotizacion_original(self, api_client):
        """Test POST /api/quotes/{quote_id}/attachments - Upload file with valid category"""
        # For file upload, remove Content-Type header (requests will set it automatically for multipart)
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        # Create a test PDF-like file
        test_file_content = b'%PDF-1.4 test content for attachment'
        files = {
            'file': ('TEST_test_attachment.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'Cotización Original'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        resp_data = response.json()
        assert "attachment" in resp_data, "attachment field missing in response"
        assert resp_data["attachment"]["category"] == "Cotización Original", "Category mismatch"
        assert "attachment_id" in resp_data["attachment"], "attachment_id missing"
        
        # Save for later tests
        TestAnexosAttachments.test_attachment_id = resp_data["attachment"]["attachment_id"]
        print(f"✓ Uploaded attachment: {TestAnexosAttachments.test_attachment_id}")

    def test_04_upload_attachment_orden_compra(self, api_client):
        """Test uploading to 'Orden de Compra' category"""
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        test_file_content = b'%PDF-1.4 orden de compra content'
        files = {
            'file': ('TEST_orden_compra.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'Orden de Compra'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        resp_data = response.json()
        assert resp_data["attachment"]["category"] == "Orden de Compra"
        print(f"✓ Uploaded 'Orden de Compra' attachment")

    def test_05_upload_attachment_factura(self, api_client):
        """Test uploading to 'Factura' category"""
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        test_file_content = b'%PDF-1.4 factura content'
        files = {
            'file': ('TEST_factura.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'Factura'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        resp_data = response.json()
        assert resp_data["attachment"]["category"] == "Factura"
        print(f"✓ Uploaded 'Factura' attachment")

    def test_06_upload_attachment_otros(self, api_client):
        """Test uploading to 'Otros' category"""
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        test_file_content = b'%PDF-1.4 otros content'
        files = {
            'file': ('TEST_otros.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'Otros'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.text}"
        resp_data = response.json()
        assert resp_data["attachment"]["category"] == "Otros"
        print(f"✓ Uploaded 'Otros' attachment")

    def test_07_upload_invalid_category_returns_400(self, api_client):
        """Test POST with invalid category returns 400 error"""
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        test_file_content = b'%PDF-1.4 invalid category test'
        files = {
            'file': ('TEST_invalid.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'InvalidCategory'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        resp_data = response.json()
        assert "detail" in resp_data, "Error detail missing"
        assert "inválida" in resp_data["detail"].lower() or "invalid" in resp_data["detail"].lower(), \
            f"Error message should mention invalid category: {resp_data['detail']}"
        print(f"✓ Invalid category correctly returns 400: {resp_data['detail']}")

    def test_08_get_attachments_after_uploads(self, api_client):
        """Test GET returns uploaded attachments"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        assert response.status_code == 200, f"GET failed: {response.text}"
        
        data = response.json()
        attachments = data.get("attachments", [])
        
        # Filter test attachments (those with TEST_ prefix)
        test_attachments = [a for a in attachments if a.get("filename", "").startswith("TEST_")]
        assert len(test_attachments) >= 4, f"Expected at least 4 test attachments, found {len(test_attachments)}"
        
        # Verify all categories are represented
        categories_found = set(a.get("category") for a in test_attachments)
        for cat in VALID_CATEGORIES:
            assert cat in categories_found, f"Category '{cat}' not found in attachments"
        
        print(f"✓ All 4 categories verified in attachments")

    def test_09_download_attachment(self, api_client):
        """Test GET /api/quotes/{quote_id}/attachments/{attachment_id}/download"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        # First get attachments to find one to download
        response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        assert response.status_code == 200
        
        attachments = response.json().get("attachments", [])
        test_attachments = [a for a in attachments if a.get("filename", "").startswith("TEST_")]
        
        if not test_attachments:
            pytest.skip("No test attachments to download")
        
        attachment_id = test_attachments[0]["attachment_id"]
        
        # Download the attachment
        download_response = api_client.get(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments/{attachment_id}/download"
        )
        
        assert download_response.status_code == 200, f"Download failed: {download_response.text}"
        assert len(download_response.content) > 0, "Downloaded file is empty"
        print(f"✓ Downloaded attachment {attachment_id}, size: {len(download_response.content)} bytes")

    def test_10_delete_attachment(self, api_client):
        """Test DELETE /api/quotes/{quote_id}/attachments/{attachment_id}"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        # Get attachments to find test ones to delete
        response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        assert response.status_code == 200
        
        attachments = response.json().get("attachments", [])
        test_attachments = [a for a in attachments if a.get("filename", "").startswith("TEST_")]
        
        if not test_attachments:
            pytest.skip("No test attachments to delete")
        
        attachment_to_delete = test_attachments[0]
        attachment_id = attachment_to_delete["attachment_id"]
        
        # Delete the attachment
        delete_response = api_client.delete(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments/{attachment_id}"
        )
        
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        resp_data = delete_response.json()
        assert "message" in resp_data, "Message missing in delete response"
        print(f"✓ Deleted attachment {attachment_id}")
        
        # Verify it's gone
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        assert verify_response.status_code == 200
        remaining = verify_response.json().get("attachments", [])
        assert not any(a["attachment_id"] == attachment_id for a in remaining), "Deleted attachment still present"
        print(f"✓ Verified attachment was removed from quote")

    def test_11_get_attachments_nonexistent_quote(self, api_client):
        """Test GET with nonexistent quote_id returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/quotes/quo_nonexistent123/attachments")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Nonexistent quote correctly returns 404")

    def test_12_upload_to_nonexistent_quote(self, api_client):
        """Test POST to nonexistent quote returns 404"""
        headers = {"Authorization": f"Bearer {TestAnexosAttachments.session_token}"}
        
        test_file_content = b'%PDF-1.4 test'
        files = {
            'file': ('test.pdf', BytesIO(test_file_content), 'application/pdf')
        }
        data = {
            'category': 'Otros'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/quo_nonexistent123/attachments",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Upload to nonexistent quote correctly returns 404")

    def test_13_delete_nonexistent_attachment(self, api_client):
        """Test DELETE nonexistent attachment returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.delete(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments/att_nonexistent1"
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Delete nonexistent attachment correctly returns 404")

    def test_14_download_nonexistent_attachment(self, api_client):
        """Test download nonexistent attachment returns 404"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.get(
            f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments/att_nonexistent1/download"
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Download nonexistent attachment correctly returns 404")

    def test_15_cleanup_test_attachments(self, api_client):
        """Cleanup: Remove all TEST_ prefixed attachments"""
        api_client.headers.update({"Authorization": f"Bearer {TestAnexosAttachments.session_token}"})
        
        response = api_client.get(f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments")
        if response.status_code != 200:
            return
        
        attachments = response.json().get("attachments", [])
        test_attachments = [a for a in attachments if a.get("filename", "").startswith("TEST_")]
        
        deleted_count = 0
        for att in test_attachments:
            del_response = api_client.delete(
                f"{BASE_URL}/api/quotes/{TestAnexosAttachments.test_quote_id}/attachments/{att['attachment_id']}"
            )
            if del_response.status_code == 200:
                deleted_count += 1
        
        print(f"✓ Cleanup: Removed {deleted_count} test attachments")


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session
