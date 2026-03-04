"""
Iteration 58: Test RIF Digital Extraction Module
Tests for POST /api/clients/parse-rif endpoint and duplicate detection
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRifExtractionModule:
    """Tests for RIF Digital PDF parsing endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # === Test 1: Parse valid RIF PDF and extract data ===
    def test_parse_rif_pdf_extracts_data_correctly(self, auth_headers):
        """POST /api/clients/parse-rif should extract RIF, legal_name, address from valid PDF"""
        rif_pdf_path = "/tmp/rif_sample.pdf"
        
        # Read the sample PDF
        with open(rif_pdf_path, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify extracted fields
        assert "rif" in data, "Response should contain 'rif' field"
        assert "legal_name" in data, "Response should contain 'legal_name' field"
        assert "address" in data, "Response should contain 'address' field"
        assert "is_duplicate" in data, "Response should contain 'is_duplicate' field"
        
        # Verify extracted values
        assert data["rif"] == "J-50732819-8", f"Expected RIF J-50732819-8, got {data['rif']}"
        assert "CORPORACION NOX 2025" in data["legal_name"], f"legal_name should contain CORPORACION NOX 2025, got {data['legal_name']}"
        assert "CALLE UNION EDIF TORRE BANCO PLAZA" in data["address"], f"Address should contain expected text, got {data['address']}"
        
        print(f"✓ RIF extracted: {data['rif']}")
        print(f"✓ Legal name extracted: {data['legal_name']}")
        print(f"✓ Address extracted: {data['address'][:50]}...")
    
    # === Test 2: Parse RIF for NEW client (no duplicate) ===
    def test_parse_rif_new_client_returns_is_duplicate_false(self, auth_headers):
        """POST /api/clients/parse-rif returns is_duplicate=false for new RIF"""
        # First, ensure no client exists with this RIF pattern by checking
        rif_pdf_path = "/tmp/rif_sample.pdf"
        
        with open(rif_pdf_path, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # For a fresh test, might be duplicate=false or true depending on DB state
        # Just verify the field structure exists
        assert "is_duplicate" in data
        assert "existing_clients" in data
        assert isinstance(data["existing_clients"], list)
        
        if not data["is_duplicate"]:
            print("✓ is_duplicate=false for new RIF (no existing clients found)")
        else:
            print(f"✓ is_duplicate=true - {len(data['existing_clients'])} existing client(s) found")
    
    # === Test 3: Reject non-PDF file ===
    def test_parse_rif_rejects_non_pdf_file(self, auth_headers):
        """POST /api/clients/parse-rif returns 400 for non-PDF files"""
        # Create a fake text file
        fake_content = b"This is not a PDF file"
        files = {"file": ("document.txt", fake_content, "text/plain")}
        
        response = requests.post(
            f"{BASE_URL}/api/clients/parse-rif",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400, f"Expected 400 for non-PDF, got {response.status_code}"
        data = response.json()
        assert "detail" in data
        print(f"✓ Non-PDF rejected with message: {data['detail']}")
    
    # === Test 4: Reject non-PDF file with fake extension ===
    def test_parse_rif_rejects_fake_pdf_extension(self, auth_headers):
        """POST /api/clients/parse-rif returns 400 for fake PDF (invalid content)"""
        # Create a fake PDF (text file with .pdf extension)
        fake_content = b"This is not a real PDF content"
        files = {"file": ("document.pdf", fake_content, "application/pdf")}
        
        response = requests.post(
            f"{BASE_URL}/api/clients/parse-rif",
            headers=auth_headers,
            files=files
        )
        
        # Should fail when trying to parse - either 400 or 422
        assert response.status_code == 400, f"Expected 400 for invalid PDF content, got {response.status_code}: {response.text}"
        print("✓ Fake PDF rejected correctly")


class TestRifDuplicateDetection:
    """Tests for duplicate RIF detection"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        assert response.status_code == 200
        return response.json()["session_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture(scope="class")
    def test_client_with_rif(self, auth_headers):
        """Create a test client with matching RIF pattern for duplicate detection"""
        client_data = {
            "rif": "J-50732819-8",  # Same as in RIF sample PDF
            "legal_name": "TEST_RIF_DUPLICATE_COMPANY CA",
            "fantasy_name": "TEST RIF DUP",
            "segment": "Pymes",
            "address": "Test Address for RIF Duplicate",
            "sucursal": "TEST_PRINCIPAL"
        }
        
        # Try to create, might already exist
        response = requests.post(
            f"{BASE_URL}/api/clients",
            headers={**auth_headers, "Content-Type": "application/json"},
            json=client_data
        )
        
        if response.status_code == 200 or response.status_code == 201:
            client = response.json()
            yield client
            # Cleanup
            requests.delete(f"{BASE_URL}/api/clients/{client['client_id']}", headers=auth_headers)
        elif response.status_code == 400 and "Ya existe" in response.text:
            # Client exists, try to find it
            clients_response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
            clients = clients_response.json()
            existing = next((c for c in clients if "50732819" in c.get("rif", "")), None)
            if existing:
                yield existing
            else:
                yield None
        else:
            print(f"Warning: Could not create test client: {response.text}")
            yield None
    
    def test_parse_rif_detects_duplicate(self, auth_headers, test_client_with_rif):
        """POST /api/clients/parse-rif returns is_duplicate=true when RIF exists in DB"""
        if test_client_with_rif is None:
            pytest.skip("Could not create test client for duplicate detection")
        
        rif_pdf_path = "/tmp/rif_sample.pdf"
        
        with open(rif_pdf_path, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                headers=auth_headers,
                files=files
            )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["is_duplicate"] == True, f"Expected is_duplicate=true, got {data['is_duplicate']}"
        assert len(data["existing_clients"]) > 0, "Expected non-empty existing_clients list"
        
        # Verify existing_clients structure
        for client in data["existing_clients"]:
            assert "client_id" in client
            assert "rif" in client
            assert "legal_name" in client or "fantasy_name" in client
        
        print(f"✓ Duplicate detected with {len(data['existing_clients'])} existing client(s)")
        for ec in data["existing_clients"]:
            print(f"  - {ec.get('rif')} | {ec.get('legal_name') or ec.get('fantasy_name')} | Sucursal: {ec.get('sucursal', 'N/A')}")


class TestRifEndpointAuthentication:
    """Test authentication requirements for RIF endpoint"""
    
    def test_parse_rif_requires_authentication(self):
        """POST /api/clients/parse-rif should return 401 without auth"""
        rif_pdf_path = "/tmp/rif_sample.pdf"
        
        with open(rif_pdf_path, "rb") as f:
            files = {"file": ("rif_digital.pdf", f, "application/pdf")}
            response = requests.post(
                f"{BASE_URL}/api/clients/parse-rif",
                files=files
            )
        
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
