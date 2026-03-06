"""
Iteration 63: Test RIF Digital Scan and Update Features
Tests for:
- POST /api/clients/parse-rif - extract RIF data from PDF/JPG/PNG
- POST /api/clients/{client_id}/update-from-rif - update existing client from RIF scan
- GET /api/clients/{client_id}/rif-document - download archived RIF document
"""

import pytest
import requests
import os
from PIL import Image
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"
TEST_CLIENT_ID = "cli_7cf444c80f4c"  # Client with existing rif_document_url


class TestAuthEndpoints:
    """Test auth endpoints as prerequisite for RIF features"""
    
    def test_register_endpoint_rejects_duplicate(self):
        """POST /api/auth/register should reject duplicate email"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Rafael",
            "last_name": "Gonzalez",
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "cedula": "V-12345678"
        })
        # Should return 400 because user already exists
        assert response.status_code == 400
        assert "registrado" in response.json().get("detail", "").lower() or "already" in response.json().get("detail", "").lower()
        print("✓ Register rejects duplicate email correctly")
    
    def test_login_endpoint_works(self):
        """POST /api/auth/login should return session token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "session_token" in data
        assert len(data["session_token"]) > 0
        print(f"✓ Login successful, token: {data['session_token'][:10]}...")


class TestParseRifEndpoint:
    """Tests for POST /api/clients/parse-rif endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Login and return auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["session_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_parse_rif_pdf_returns_extracted_data(self, auth_headers):
        """POST /api/clients/parse-rif should extract RIF from PDF"""
        test_pdf = "/tmp/test_rif.pdf"
        if not os.path.exists(test_pdf):
            pytest.skip(f"Test PDF not found at {test_pdf}")
        
        with open(test_pdf, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "rif" in data, "Response should contain 'rif' field"
        assert "legal_name" in data, "Response should contain 'legal_name' field"
        assert "address" in data, "Response should contain 'address' field"
        assert "is_duplicate" in data, "Response should contain 'is_duplicate' field"
        assert "existing_clients" in data, "Response should contain 'existing_clients' field"
        assert "source_format" in data, "Response should contain 'source_format' field"
        
        assert data["source_format"] == "PDF"
        print(f"✓ RIF extracted: {data['rif']}")
        print(f"✓ Legal name: {data['legal_name']}")
        print(f"✓ Address: {data['address'][:50]}..." if data['address'] else "✓ Address: (empty)")
    
    def test_parse_rif_rejects_unsupported_format(self, auth_headers):
        """POST /api/clients/parse-rif should reject .txt files"""
        fake_content = b"This is not a valid RIF document"
        files = {"file": ("document.txt", fake_content, "text/plain")}
        
        response = requests.post(
            f"{BASE_URL}/api/clients/parse-rif",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for .txt, got {response.status_code}"
        assert "Formato no soportado" in response.json().get("detail", "")
        print("✓ Unsupported format rejected correctly")
    
    def test_parse_rif_accepts_jpg_format(self, auth_headers):
        """POST /api/clients/parse-rif should accept JPG files (for image OCR)"""
        # Create a simple test image with text
        img = Image.new('RGB', (400, 200), color='white')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        
        files = {"file": ("rif_image.jpg", img_buffer, "image/jpeg")}
        
        response = requests.post(
            f"{BASE_URL}/api/clients/parse-rif",
            headers=auth_headers,
            files=files
        )
        
        # Should accept but might fail to extract RIF (blank image)
        # Either 200 with extracted data or 400 with "No se encontró un código RIF"
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        if response.status_code == 400:
            assert "RIF" in response.json().get("detail", "") or "texto" in response.json().get("detail", "").lower()
        print(f"✓ JPG format accepted (status: {response.status_code})")
    
    def test_parse_rif_accepts_png_format(self, auth_headers):
        """POST /api/clients/parse-rif should accept PNG files"""
        # Create a simple test image
        img = Image.new('RGB', (400, 200), color='white')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        files = {"file": ("rif_image.png", img_buffer, "image/png")}
        
        response = requests.post(
            f"{BASE_URL}/api/clients/parse-rif",
            headers=auth_headers,
            files=files
        )
        
        # Should accept but might fail to extract RIF (blank image)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        print(f"✓ PNG format accepted (status: {response.status_code})")
    
    def test_parse_rif_requires_authentication(self):
        """POST /api/clients/parse-rif should return 401 without auth"""
        test_pdf = "/tmp/test_rif.pdf"
        if not os.path.exists(test_pdf):
            pytest.skip(f"Test PDF not found at {test_pdf}")
        
        with open(test_pdf, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                files=files
            )
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestUpdateFromRifEndpoint:
    """Tests for POST /api/clients/{client_id}/update-from-rif endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Login and return auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["session_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_update_from_rif_updates_client_data(self, auth_headers):
        """POST /api/clients/{client_id}/update-from-rif should update client and archive document"""
        test_pdf = "/tmp/test_rif.pdf"
        if not os.path.exists(test_pdf):
            pytest.skip(f"Test PDF not found at {test_pdf}")
        
        # First get original client data
        get_response = requests.get(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            headers=auth_headers
        )
        assert get_response.status_code == 200, f"Client not found: {TEST_CLIENT_ID}"
        original_data = get_response.json()
        
        # Update from RIF
        with open(test_pdf, "rb") as f:
            files = {"file": ("rif_update.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}/update-from-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "message" in data, "Response should contain 'message'"
        assert "previous_data" in data, "Response should contain 'previous_data'"
        assert "updated_data" in data, "Response should contain 'updated_data'"
        assert "rif_document_url" in data, "Response should contain 'rif_document_url'"
        assert "source_format" in data, "Response should contain 'source_format'"
        
        # Verify document was archived
        assert data["rif_document_url"].startswith("/uploads/rif_documents/")
        
        print(f"✓ Client updated from RIF")
        print(f"✓ Previous RIF: {data['previous_data'].get('rif', 'N/A')}")
        print(f"✓ Updated RIF: {data['updated_data'].get('rif', 'N/A')}")
        print(f"✓ Document archived at: {data['rif_document_url']}")
    
    def test_update_from_rif_returns_404_for_invalid_client(self, auth_headers):
        """POST /api/clients/{client_id}/update-from-rif should return 404 for non-existent client"""
        test_pdf = "/tmp/test_rif.pdf"
        if not os.path.exists(test_pdf):
            pytest.skip(f"Test PDF not found at {test_pdf}")
        
        with open(test_pdf, "rb") as f:
            files = {"file": ("rif_update.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/invalid_client_id_xyz/update-from-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Returns 404 for non-existent client")
    
    def test_update_from_rif_requires_authentication(self):
        """POST /api/clients/{client_id}/update-from-rif should return 401 without auth"""
        test_pdf = "/tmp/test_rif.pdf"
        if not os.path.exists(test_pdf):
            pytest.skip(f"Test PDF not found at {test_pdf}")
        
        with open(test_pdf, "rb") as f:
            files = {"file": ("rif_update.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}/update-from-rif",
                files=files
            )
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestDownloadRifDocument:
    """Tests for GET /api/clients/{client_id}/rif-document endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Login and return auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["session_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_download_rif_document_returns_file(self, auth_headers):
        """GET /api/clients/{client_id}/rif-document should download archived RIF"""
        response = requests.get(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}/rif-document",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert len(response.content) > 0, "Response should contain file content"
        
        # Check content type is appropriate for PDF/image
        content_type = response.headers.get("content-type", "")
        valid_types = ["application/pdf", "image/jpeg", "image/png", "application/octet-stream"]
        assert any(t in content_type for t in valid_types), f"Unexpected content-type: {content_type}"
        
        print(f"✓ RIF document downloaded ({len(response.content)} bytes)")
        print(f"✓ Content-Type: {content_type}")
    
    def test_download_rif_returns_404_for_client_without_rif(self, auth_headers):
        """GET /api/clients/{client_id}/rif-document should return 404 if no RIF archived"""
        # Get list of clients and find one without rif_document_url
        clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert clients_response.status_code == 200
        clients = clients_response.json()
        
        client_without_rif = None
        for client in clients[:50]:  # Check first 50
            if not client.get("rif_document_url"):
                client_without_rif = client
                break
        
        if not client_without_rif:
            pytest.skip("All clients have RIF documents - cannot test 404 case")
        
        response = requests.get(
            f"{BASE_URL}/api/clients/{client_without_rif['client_id']}/rif-document",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert "no tiene" in response.json().get("detail", "").lower() or "not" in response.json().get("detail", "").lower()
        print(f"✓ Returns 404 for client without RIF: {client_without_rif['client_id']}")
    
    def test_download_rif_returns_404_for_invalid_client(self, auth_headers):
        """GET /api/clients/{client_id}/rif-document should return 404 for non-existent client"""
        response = requests.get(
            f"{BASE_URL}/api/clients/invalid_client_id_xyz/rif-document",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Returns 404 for non-existent client")
    
    def test_download_rif_requires_authentication(self):
        """GET /api/clients/{client_id}/rif-document should return 401 without auth"""
        response = requests.get(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}/rif-document"
        )
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestClientTableIntegration:
    """Integration tests for clients with RIF features in table view"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Login and return auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["session_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_clients_list_includes_rif_document_url(self, auth_headers):
        """GET /api/clients should include rif_document_url field when present"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        
        clients = response.json()
        assert len(clients) > 0, "Expected at least one client"
        
        # Find our test client with RIF document
        test_client = next((c for c in clients if c.get("client_id") == TEST_CLIENT_ID), None)
        assert test_client is not None, f"Test client {TEST_CLIENT_ID} not found"
        assert "rif_document_url" in test_client, "Client should have rif_document_url field"
        assert test_client["rif_document_url"].startswith("/uploads/"), "rif_document_url should start with /uploads/"
        
        print(f"✓ Found {len(clients)} clients")
        print(f"✓ Test client has rif_document_url: {test_client['rif_document_url']}")
    
    def test_client_detail_includes_rif_metadata(self, auth_headers):
        """GET /api/clients/{id} should include RIF metadata fields"""
        response = requests.get(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        client = response.json()
        
        # Check RIF-related fields
        assert "rif_document_url" in client, "Should have rif_document_url"
        assert "rif_document_filename" in client, "Should have rif_document_filename"
        assert "rif_updated_at" in client, "Should have rif_updated_at"
        assert "rif_updated_by" in client, "Should have rif_updated_by"
        
        print(f"✓ Client has RIF metadata:")
        print(f"  - rif_document_url: {client['rif_document_url']}")
        print(f"  - rif_document_filename: {client['rif_document_filename']}")
        print(f"  - rif_updated_at: {client['rif_updated_at']}")
        print(f"  - rif_updated_by: {client['rif_updated_by']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
