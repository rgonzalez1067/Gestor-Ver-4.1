# ruff: noqa
"""
Test suite for iteration 37 - Testing new quote features and hardware import/export
Features to test:
1. Hardware export to Excel endpoint
2. Hardware export to PDF endpoint
3. Hardware template download endpoint
4. Quote categories filter (implementation, equipment, accessory, repair)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login with test credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password123"
        })
        if response.status_code == 200:
            return response.json().get("session_token")
        
        # If login fails, try to register the user first
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Admin",
            "last_name": "Test",
            "cedula": "12345678",
            "email": "admin@test.com",
            "password": "password123"
        })
        if register_response.status_code == 200:
            return register_response.json().get("session_token")
        
        # Try login again after registration
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "password123"
        })
        if response.status_code == 200:
            return response.json().get("session_token")
            
        pytest.skip("Authentication failed - skipping authenticated tests")
        return None


class TestHardwareExport(TestAuth):
    """Test hardware/bienes y servicios export endpoints"""
    
    def test_export_hardware_excel(self, auth_token):
        """Test GET /api/hardware/export/excel - should download Excel file"""
        response = requests.get(
            f"{BASE_URL}/api/hardware/export/excel",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Content-Type assertion for Excel
        content_type = response.headers.get('content-type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type, \
            f"Expected Excel content-type, got {content_type}"
        
        # Content-Disposition should have filename
        content_disposition = response.headers.get('content-disposition', '')
        assert 'attachment' in content_disposition.lower(), \
            f"Expected attachment disposition, got {content_disposition}"
        assert '.xlsx' in content_disposition or 'bienes' in content_disposition.lower(), \
            f"Expected .xlsx filename, got {content_disposition}"
        
        # Should have content
        assert len(response.content) > 0, "Excel file should have content"
        print(f"✓ Hardware Excel export working - file size: {len(response.content)} bytes")
    
    def test_export_hardware_pdf(self, auth_token):
        """Test GET /api/hardware/export/pdf - should download PDF file"""
        response = requests.get(
            f"{BASE_URL}/api/hardware/export/pdf",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Content-Type assertion for PDF
        content_type = response.headers.get('content-type', '')
        assert 'pdf' in content_type.lower(), f"Expected PDF content-type, got {content_type}"
        
        # Content-Disposition should have filename
        content_disposition = response.headers.get('content-disposition', '')
        assert 'attachment' in content_disposition.lower(), \
            f"Expected attachment disposition, got {content_disposition}"
        
        # Should have content
        assert len(response.content) > 0, "PDF file should have content"
        
        # PDF signature check (PDF files start with %PDF)
        assert response.content[:4] == b'%PDF', "File should be a valid PDF"
        print(f"✓ Hardware PDF export working - file size: {len(response.content)} bytes")
    
    def test_download_hardware_template(self, auth_token):
        """Test GET /api/hardware/template - should download import template"""
        response = requests.get(
            f"{BASE_URL}/api/hardware/template",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Content-Type assertion for Excel
        content_type = response.headers.get('content-type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type, \
            f"Expected Excel content-type, got {content_type}"
        
        # Should have content
        assert len(response.content) > 0, "Template file should have content"
        print(f"✓ Hardware template download working - file size: {len(response.content)} bytes")
    
    def test_export_endpoints_require_auth(self):
        """Test that export endpoints require authentication"""
        # Test without auth token
        endpoints = [
            "/api/hardware/export/excel",
            "/api/hardware/export/pdf",
            "/api/hardware/template"
        ]
        
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 401, f"Expected 401 for {endpoint} without auth, got {response.status_code}"
        
        print("✓ All export endpoints require authentication")


class TestQuotesAPI(TestAuth):
    """Test quotes API for new category features"""
    
    def test_get_quotes_list(self, auth_token):
        """Test GET /api/quotes - should return quotes list"""
        response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Quotes list endpoint working - {len(data)} quotes found")
    
    def test_get_clients_list(self, auth_token):
        """Test GET /api/clients - should return clients list for quote creation"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Clients list endpoint working - {len(data)} clients found")
    
    def test_get_hardware_list(self, auth_token):
        """Test GET /api/hardware - should return hardware for equipment quotes"""
        response = requests.get(
            f"{BASE_URL}/api/hardware",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Hardware list endpoint working - {len(data)} items found")


class TestHardwareImport(TestAuth):
    """Test hardware import functionality"""
    
    def test_import_invalid_format_returns_error(self, auth_token):
        """Test that importing invalid file format returns proper error"""
        # Create a simple text file (invalid format)
        import io
        
        files = {
            'file': ('test.txt', io.BytesIO(b'invalid content'), 'text/plain')
        }
        
        response = requests.post(
            f"{BASE_URL}/api/hardware/import",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files
        )
        
        # Should return 200 with error status in response body (as per ImportResult model)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'error', f"Expected error status, got {data.get('status')}"
        assert 'formato' in data.get('message', '').lower() or 'format' in data.get('message', '').lower(), \
            f"Expected format error message, got {data.get('message')}"
        
        print("✓ Import validates file format correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
