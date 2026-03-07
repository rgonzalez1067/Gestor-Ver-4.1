"""
Test Iteration 68 - Banks Module Redesign
Tests:
1. POST /api/banks/upload-logo - Logo upload with resize
2. POST /api/banks - Create bank with new fields (rif, bank_code, contact_name, contact_phone, contact_email, bank_logo_url)
3. PUT /api/banks/{id} - Update bank with new fields
4. GET /api/banks - Returns banks with new fields
5. DELETE /api/banks/{id} - Delete bank with confirmation
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestBanksRedesign:
    """Test new bank module features - Iteration 68"""
    
    auth_token = None
    test_bank_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before tests"""
        if TestBanksRedesign.auth_token is None:
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "rgonzalez@megasoft.com.ve",
                "password": "Avila*0226*02"
            })
            assert response.status_code == 200, f"Login failed: {response.text}"
            data = response.json()
            TestBanksRedesign.auth_token = data.get("session_token") or data.get("token")
    
    def get_headers(self):
        return {"Authorization": f"Bearer {TestBanksRedesign.auth_token}"}
    
    # === LOGO UPLOAD TESTS ===
    
    def test_01_upload_logo_endpoint_exists(self):
        """Test that upload-logo endpoint exists and requires image"""
        # Test with non-image file should fail
        response = requests.post(
            f"{BASE_URL}/api/banks/upload-logo",
            headers=self.get_headers(),
            files={"file": ("test.txt", b"not an image", "text/plain")}
        )
        assert response.status_code == 400, f"Expected 400 for non-image, got {response.status_code}"
        assert "imagen" in response.json().get("detail", "").lower()
        print("PASSED: upload-logo endpoint rejects non-image files")
    
    def test_02_upload_logo_with_image(self):
        """Test uploading actual image file"""
        # Create a minimal valid PNG (1x1 transparent pixel)
        png_data = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 dimensions
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0x00, 0x00, 0x00,
            0x01, 0x00, 0x01, 0x00, 0x05, 0x0F, 0xEB, 0xB1,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82
        ])
        
        response = requests.post(
            f"{BASE_URL}/api/banks/upload-logo",
            headers=self.get_headers(),
            files={"file": ("test_logo.png", png_data, "image/png")}
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        data = response.json()
        assert "logo_url" in data, "Response should contain logo_url"
        assert data["logo_url"].startswith("/api/uploads/bank_logos/"), f"Invalid logo_url format: {data['logo_url']}"
        print(f"PASSED: Logo uploaded, URL: {data['logo_url']}")
    
    # === CREATE BANK WITH NEW FIELDS ===
    
    def test_03_create_bank_with_new_fields(self):
        """Test creating bank with all new fields"""
        bank_data = {
            "name": "TEST_Banco Prueba Iteration 68",
            "type": "Banco",
            "country": "Venezuela",
            "rif": "J-12345678-9",
            "bank_code": "0199",
            "contact_name": "Maria Garcia - Gerente de Canales",
            "contact_phone": "+58 412-1234567",
            "contact_email": "mgarcia@testbank.com",
            "bank_logo_url": "/api/uploads/bank_logos/test.png",
            "products": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers(),
            json=bank_data
        )
        assert response.status_code == 200, f"Create bank failed: {response.text}"
        data = response.json()
        
        # Verify all fields persisted
        assert data["name"] == bank_data["name"]
        assert data["rif"] == bank_data["rif"]
        assert data["bank_code"] == bank_data["bank_code"]
        assert data["contact_name"] == bank_data["contact_name"]
        assert data["contact_phone"] == bank_data["contact_phone"]
        assert data["contact_email"] == bank_data["contact_email"]
        assert data["bank_logo_url"] == bank_data["bank_logo_url"]
        assert "bank_id" in data
        
        TestBanksRedesign.test_bank_id = data["bank_id"]
        print(f"PASSED: Bank created with all new fields, ID: {data['bank_id']}")
    
    def test_04_get_banks_returns_new_fields(self):
        """Test GET /api/banks returns all new fields"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers()
        )
        assert response.status_code == 200, f"GET banks failed: {response.text}"
        banks = response.json()
        
        assert len(banks) > 0, "No banks returned"
        
        # Find our test bank
        test_bank = next((b for b in banks if b.get("bank_id") == TestBanksRedesign.test_bank_id), None)
        assert test_bank is not None, "Test bank not found in list"
        
        # Verify new fields are present
        assert test_bank.get("rif") == "J-12345678-9"
        assert test_bank.get("bank_code") == "0199"
        assert test_bank.get("contact_name") == "Maria Garcia - Gerente de Canales"
        assert test_bank.get("contact_phone") == "+58 412-1234567"
        assert test_bank.get("contact_email") == "mgarcia@testbank.com"
        assert test_bank.get("bank_logo_url") == "/api/uploads/bank_logos/test.png"
        print(f"PASSED: GET banks returns all new fields for {len(banks)} banks")
    
    def test_05_update_bank_with_new_fields(self):
        """Test PUT /api/banks/{id} updates new fields"""
        assert TestBanksRedesign.test_bank_id is not None, "No test bank ID"
        
        updated_data = {
            "name": "TEST_Banco Prueba Updated",
            "type": "Fintech",
            "country": "Venezuela",
            "rif": "J-98765432-1",
            "bank_code": "0162",
            "contact_name": "Carlos Perez - Director Comercial",
            "contact_phone": "+58 414-9876543",
            "contact_email": "cperez@testbank.com",
            "bank_logo_url": "/api/uploads/bank_logos/updated.png",
            "products": []
        }
        
        response = requests.put(
            f"{BASE_URL}/api/banks/{TestBanksRedesign.test_bank_id}",
            headers=self.get_headers(),
            json=updated_data
        )
        assert response.status_code == 200, f"Update bank failed: {response.text}"
        data = response.json()
        
        # Verify all updated fields
        assert data["name"] == updated_data["name"]
        assert data["type"] == updated_data["type"]
        assert data["rif"] == updated_data["rif"]
        assert data["bank_code"] == updated_data["bank_code"]
        assert data["contact_name"] == updated_data["contact_name"]
        assert data["contact_phone"] == updated_data["contact_phone"]
        assert data["contact_email"] == updated_data["contact_email"]
        assert data["bank_logo_url"] == updated_data["bank_logo_url"]
        print("PASSED: Bank updated with all new fields")
    
    def test_06_verify_update_persisted(self):
        """Verify update was persisted via GET"""
        assert TestBanksRedesign.test_bank_id is not None, "No test bank ID"
        
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers()
        )
        assert response.status_code == 200
        banks = response.json()
        
        test_bank = next((b for b in banks if b.get("bank_id") == TestBanksRedesign.test_bank_id), None)
        assert test_bank is not None, "Test bank not found"
        
        # Verify updated values persisted
        assert test_bank.get("rif") == "J-98765432-1"
        assert test_bank.get("bank_code") == "0162"
        assert test_bank.get("contact_name") == "Carlos Perez - Director Comercial"
        print("PASSED: Update persisted and verified via GET")
    
    def test_07_create_bank_minimal_fields(self):
        """Test creating bank with only required fields (new fields are optional)"""
        bank_data = {
            "name": "TEST_Banco Minimo",
            "type": "Banco",
            "country": "Venezuela",
            "products": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers(),
            json=bank_data
        )
        assert response.status_code == 200, f"Create minimal bank failed: {response.text}"
        data = response.json()
        
        # New fields should be None/null
        assert data.get("rif") is None
        assert data.get("bank_code") is None
        assert data.get("contact_name") is None
        assert data.get("contact_phone") is None
        assert data.get("contact_email") is None
        assert data.get("bank_logo_url") is None
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/banks/{data['bank_id']}", headers=self.get_headers())
        print("PASSED: Bank created with minimal fields, new fields are optional")
    
    def test_08_delete_bank(self):
        """Test DELETE /api/banks/{id}"""
        assert TestBanksRedesign.test_bank_id is not None, "No test bank ID"
        
        response = requests.delete(
            f"{BASE_URL}/api/banks/{TestBanksRedesign.test_bank_id}",
            headers=self.get_headers()
        )
        assert response.status_code == 200, f"Delete bank failed: {response.text}"
        data = response.json()
        assert "message" in data or "eliminado" in str(data).lower()
        print("PASSED: Bank deleted successfully")
    
    def test_09_verify_delete_persisted(self):
        """Verify delete was persisted"""
        assert TestBanksRedesign.test_bank_id is not None, "No test bank ID"
        
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers()
        )
        assert response.status_code == 200
        banks = response.json()
        
        test_bank = next((b for b in banks if b.get("bank_id") == TestBanksRedesign.test_bank_id), None)
        assert test_bank is None, "Deleted bank should not be in list"
        print("PASSED: Deleted bank no longer in list")
    
    def test_10_delete_nonexistent_bank_returns_404(self):
        """Test deleting non-existent bank returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/banks/nonexistent_id",
            headers=self.get_headers()
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASSED: Delete non-existent bank returns 404")
    
    def test_11_existing_banks_have_null_new_fields(self):
        """Verify existing banks can have null/None values for new fields"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers=self.get_headers()
        )
        assert response.status_code == 200
        banks = response.json()
        
        # Check that existing banks without new fields still work
        for bank in banks[:5]:  # Check first 5 banks
            # These fields might be None or missing - that's OK
            _ = bank.get("rif")
            _ = bank.get("bank_code")
            _ = bank.get("contact_name")
            _ = bank.get("contact_phone")
            _ = bank.get("contact_email")
            _ = bank.get("bank_logo_url")
        
        print(f"PASSED: Checked {min(5, len(banks))} existing banks - compatible with new schema")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
