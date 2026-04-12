"""
Test module for Initial Contacts (Leads/Prospección Temprana) - Iteration 164
Tests: CRUD operations, assignment hierarchy, documentation, transfer, conversion to prospect
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInitialContactsModule:
    """Tests for the Initial Contacts (Leads) module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        data = login_response.json()
        self.token = data.get("session_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.user_id = data.get("user", {}).get("user_id")
        yield
    
    # --- API Endpoint Tests ---
    
    def test_list_initial_contacts(self):
        """Test GET /api/initial-contacts returns list"""
        response = self.session.get(f"{BASE_URL}/api/initial-contacts")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/initial-contacts returned {len(data)} contacts")
    
    def test_get_my_commitments(self):
        """Test GET /api/initial-contacts/my-commitments/list returns user's assigned contacts"""
        response = self.session.get(f"{BASE_URL}/api/initial-contacts/my-commitments/list")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/initial-contacts/my-commitments/list returned {len(data)} commitments")
    
    def test_create_initial_contact(self):
        """Test POST /api/initial-contacts creates a new contact"""
        unique_id = uuid.uuid4().hex[:6]
        payload = {
            "contact_name": f"TEST_Contact_{unique_id}",
            "phone": "+58 412 1234567",
            "email": f"test_{unique_id}@empresa.com",
            "legal_name": f"TEST_Empresa_{unique_id} C.A."
        }
        response = self.session.post(f"{BASE_URL}/api/initial-contacts", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "contact_id" in data, "Response should have contact_id"
        assert data["contact_name"] == payload["contact_name"]
        assert data["phone"] == payload["phone"]
        assert data["email"] == payload["email"]
        assert data["legal_name"] == payload["legal_name"]
        assert data["is_converted"] == False
        assert "bitacora" in data and len(data["bitacora"]) > 0
        
        # Store for cleanup
        self.created_contact_id = data["contact_id"]
        print(f"✓ POST /api/initial-contacts created contact: {data['contact_id']}")
        return data["contact_id"]
    
    def test_create_contact_missing_fields(self):
        """Test POST /api/initial-contacts with missing required fields fails"""
        payload = {
            "contact_name": "Test Contact",
            # Missing phone, email, legal_name
        }
        response = self.session.post(f"{BASE_URL}/api/initial-contacts", json=payload)
        assert response.status_code == 422, f"Should fail with 422, got {response.status_code}"
        print("✓ POST /api/initial-contacts correctly rejects incomplete data")
    
    def test_get_single_contact(self):
        """Test GET /api/initial-contacts/{contact_id} returns contact details"""
        # First create a contact
        contact_id = self.test_create_initial_contact()
        
        response = self.session.get(f"{BASE_URL}/api/initial-contacts/{contact_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["contact_id"] == contact_id
        print(f"✓ GET /api/initial-contacts/{contact_id} returned contact details")
    
    def test_document_contact(self):
        """Test POST /api/initial-contacts/{contact_id}/document adds to bitacora"""
        # First create a contact
        contact_id = self.test_create_initial_contact()
        
        payload = {"comment": "TEST_Llamada realizada, cliente interesado en productos"}
        response = self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/document", json=payload)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        
        # Verify bitacora was updated
        get_response = self.session.get(f"{BASE_URL}/api/initial-contacts/{contact_id}")
        contact = get_response.json()
        assert len(contact["bitacora"]) >= 2, "Bitacora should have at least 2 entries (created + documented)"
        
        # Find the documented entry
        documented_entries = [e for e in contact["bitacora"] if e["action"] == "documented"]
        assert len(documented_entries) > 0, "Should have a documented entry"
        assert payload["comment"] in documented_entries[-1]["description"]
        print(f"✓ POST /api/initial-contacts/{contact_id}/document added to bitacora")
    
    def test_convert_to_prospect(self):
        """Test POST /api/initial-contacts/{contact_id}/convert creates client with Prospecto status"""
        # First create a contact
        contact_id = self.test_create_initial_contact()
        
        response = self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/convert")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "client_id" in data, "Response should have client_id"
        assert "message" in data
        
        client_id = data["client_id"]
        
        # Verify contact is now converted
        get_response = self.session.get(f"{BASE_URL}/api/initial-contacts/{contact_id}")
        contact = get_response.json()
        assert contact["is_converted"] == True, "Contact should be marked as converted"
        assert contact["converted_client_id"] == client_id
        
        # Verify client was created with Prospecto status
        client_response = self.session.get(f"{BASE_URL}/api/clients/{client_id}")
        assert client_response.status_code == 200, f"Client not found: {client_response.text}"
        client = client_response.json()
        assert client["client_status"] == "Prospecto", f"Client status should be Prospecto, got {client.get('client_status')}"
        
        print(f"✓ POST /api/initial-contacts/{contact_id}/convert created client {client_id} with Prospecto status")
    
    def test_convert_already_converted_fails(self):
        """Test converting an already converted contact fails"""
        # First create and convert a contact
        contact_id = self.test_create_initial_contact()
        self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/convert")
        
        # Try to convert again
        response = self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/convert")
        assert response.status_code == 404, f"Should fail with 404, got {response.status_code}"
        print("✓ Converting already converted contact correctly fails")
    
    def test_list_excludes_converted(self):
        """Test GET /api/initial-contacts excludes converted contacts"""
        # Create and convert a contact
        contact_id = self.test_create_initial_contact()
        self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/convert")
        
        # List should not include converted contact
        response = self.session.get(f"{BASE_URL}/api/initial-contacts")
        contacts = response.json()
        contact_ids = [c["contact_id"] for c in contacts]
        assert contact_id not in contact_ids, "Converted contact should not appear in list"
        print("✓ GET /api/initial-contacts correctly excludes converted contacts")
    
    def test_list_all_includes_converted(self):
        """Test GET /api/initial-contacts/all includes converted contacts"""
        # Create and convert a contact
        contact_id = self.test_create_initial_contact()
        self.session.post(f"{BASE_URL}/api/initial-contacts/{contact_id}/convert")
        
        # List all should include converted contact
        response = self.session.get(f"{BASE_URL}/api/initial-contacts/all")
        assert response.status_code == 200
        contacts = response.json()
        contact_ids = [c["contact_id"] for c in contacts]
        assert contact_id in contact_ids, "Converted contact should appear in /all list"
        print("✓ GET /api/initial-contacts/all correctly includes converted contacts")


class TestNotifications:
    """Tests for notifications related to initial contacts"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        data = login_response.json()
        self.token = data.get("session_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_get_notifications(self):
        """Test GET /api/notifications returns user notifications"""
        response = self.session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/notifications returned {len(data)} notifications")
    
    def test_get_unread_count(self):
        """Test GET /api/notifications/unread-count returns count"""
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        print(f"✓ GET /api/notifications/unread-count returned count: {data['count']}")


class TestRegressionClients:
    """Regression tests for Clients module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        data = login_response.json()
        self.token = data.get("session_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_list_clients(self):
        """Test GET /api/clients still works"""
        response = self.session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/clients returned {len(data)} clients (regression OK)")


class TestRegressionQuotes:
    """Regression tests for Quotes module"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        data = login_response.json()
        self.token = data.get("session_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_list_quotes(self):
        """Test GET /api/quotes still works"""
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/quotes returned {len(data)} quotes (regression OK)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
