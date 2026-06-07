# ruff: noqa
"""
Iteration 109 Tests - Integrators Assignment Board Reingeniería
Tests for:
1. PUT /api/integrators/{id}/assign endpoint - assigns user, updates gestor, sends simulated email
2. POST /api/integrators - creates integrator WITHOUT requiring gestor field
3. GET /api/integrators - returns integrators including unassigned ones
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "test@mega.com"
TEST_PASSWORD = "Admin123!"

class TestIntegratorAssignment:
    """Tests for new integrator assignment features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        data = login_res.json()
        token = data.get("session_token") or data.get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        
        # Get users list for assignment testing
        users_res = self.session.get(f"{BASE_URL}/api/auth/users")
        if users_res.status_code == 200:
            self.users = users_res.json()
        else:
            self.users = []
        
        yield
        
        # Cleanup - delete test integrators
        integrators_res = self.session.get(f"{BASE_URL}/api/integrators")
        if integrators_res.status_code == 200:
            for intg in integrators_res.json():
                if intg.get('name', '').startswith('TEST_IT109_'):
                    self.session.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}")
    
    def test_01_create_integrator_without_gestor(self):
        """POST /api/integrators - should create integrator without gestor field"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_IT109_NoGestor_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "TestApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
            # NOTE: No 'gestor' field - should work
        }
        
        res = self.session.post(f"{BASE_URL}/api/integrators", json=payload)
        assert res.status_code == 200, f"Create integrator failed: {res.text}"
        
        data = res.json()
        assert data["name"] == payload["name"]
        assert data.get("gestor") in [None, "", None]  # Gestor should be null/empty
        assert "integrator_id" in data
        
        # Store for cleanup
        self.created_integrator_id = data["integrator_id"]
        print(f"✓ Created integrator without gestor: {data['integrator_id']}")
    
    def test_02_get_integrators_includes_unassigned(self):
        """GET /api/integrators - should return integrators including those without gestor"""
        # First create an unassigned integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_Unassigned_{unique_id}",
            "integrator_type": "Comercio",
            "app_name": "UnassignedApp",
            "integration_modality": "MPOS",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        created = create_res.json()
        
        # Now get all integrators
        res = self.session.get(f"{BASE_URL}/api/integrators")
        assert res.status_code == 200, f"Get integrators failed: {res.text}"
        
        data = res.json()
        assert isinstance(data, list)
        
        # Find our created integrator
        found = None
        for intg in data:
            if intg["integrator_id"] == created["integrator_id"]:
                found = intg
                break
        
        assert found is not None, "Created unassigned integrator not found in list"
        assert found.get("gestor") in [None, "", None]
        print("✓ GET /api/integrators includes unassigned integrators")
    
    def test_03_assign_endpoint_exists(self):
        """PUT /api/integrators/{id}/assign - endpoint should exist"""
        # First create a test integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_AssignTest_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "AssignTestApp",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        integrator_id = integrator["integrator_id"]
        
        # Try to call assign without user_id - should get 400, not 404
        res = self.session.put(f"{BASE_URL}/api/integrators/{integrator_id}/assign", json={})
        assert res.status_code == 400, f"Expected 400 for missing user_id, got {res.status_code}"
        
        data = res.json()
        assert "user_id" in str(data.get("detail", "")).lower() or "user_id" in str(data).lower()
        print("✓ PUT /api/integrators/{id}/assign endpoint exists and validates input")
    
    def test_04_assign_gestor_successfully(self):
        """PUT /api/integrators/{id}/assign - should assign user and update gestor"""
        if not self.users:
            pytest.skip("No users available for assignment test")
        
        # Create unassigned integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_ToAssign_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "ToAssignApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        integrator_id = integrator["integrator_id"]
        
        # Get first user to assign
        user_to_assign = self.users[0]
        user_id = user_to_assign.get("user_id")
        assert user_id, "User has no user_id"
        
        # Assign the gestor
        assign_res = self.session.put(f"{BASE_URL}/api/integrators/{integrator_id}/assign", json={
            "user_id": user_id
        })
        assert assign_res.status_code == 200, f"Assign failed: {assign_res.text}"
        
        data = assign_res.json()
        assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
        assert "integrator" in data, "Response should include integrator"
        assert "message" in data, "Response should include message"
        
        # Verify integrator was updated
        updated = data["integrator"]
        assert updated.get("gestor"), "Gestor should be set after assignment"
        assert updated.get("gestor_user_id") == user_id, "gestor_user_id should match assigned user"
        
        print(f"✓ Successfully assigned gestor to integrator: {updated.get('gestor')}")
    
    def test_05_assign_sends_email_notification(self):
        """PUT /api/integrators/{id}/assign - should return email notification result"""
        if not self.users:
            pytest.skip("No users available for assignment test")
        
        # Create unassigned integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_EmailTest_{unique_id}",
            "integrator_type": "Comercio",
            "app_name": "EmailTestApp",
            "integration_modality": "Bridge PG",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        integrator_id = integrator["integrator_id"]
        
        # Get user with email to assign
        user_to_assign = None
        for u in self.users:
            if u.get("email"):
                user_to_assign = u
                break
        
        if not user_to_assign:
            pytest.skip("No user with email available")
        
        # Assign and check email response
        assign_res = self.session.put(f"{BASE_URL}/api/integrators/{integrator_id}/assign", json={
            "user_id": user_to_assign["user_id"]
        })
        assert assign_res.status_code == 200
        
        data = assign_res.json()
        assert "email" in data, "Response should include email result"
        
        email_result = data["email"]
        # Email should be simulated since Resend is mocked
        assert email_result.get("simulated") == True or email_result.get("status") in ["ok", "simulated"]
        
        print(f"✓ Email notification result included: {email_result}")
    
    def test_06_assign_nonexistent_integrator(self):
        """PUT /api/integrators/{id}/assign - should return 404 for nonexistent integrator"""
        if not self.users:
            pytest.skip("No users available")
        
        fake_id = "int_nonexistent_12345"
        res = self.session.put(f"{BASE_URL}/api/integrators/{fake_id}/assign", json={
            "user_id": self.users[0]["user_id"]
        })
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("✓ Returns 404 for nonexistent integrator")
    
    def test_07_assign_nonexistent_user(self):
        """PUT /api/integrators/{id}/assign - should return 404 for nonexistent user"""
        # Create integrator first
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_BadUser_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "BadUserApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        
        # Try to assign non-existent user
        res = self.session.put(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}/assign", json={
            "user_id": "user_nonexistent_xyz"
        })
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("✓ Returns 404 for nonexistent user")
    
    def test_08_verify_assigned_at_and_assigned_by(self):
        """PUT /api/integrators/{id}/assign - should set assigned_at and assigned_by fields"""
        if not self.users:
            pytest.skip("No users available")
        
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_AssignMeta_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "MetaTestApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        
        # Assign
        assign_res = self.session.put(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}/assign", json={
            "user_id": self.users[0]["user_id"]
        })
        assert assign_res.status_code == 200
        
        data = assign_res.json()
        updated = data["integrator"]
        
        # Verify metadata fields
        assert updated.get("assigned_at"), "assigned_at should be set"
        assert updated.get("assigned_by"), "assigned_by should be set"
        
        print(f"✓ Assignment metadata set: assigned_at={updated.get('assigned_at')}, assigned_by={updated.get('assigned_by')}")
    
    def test_09_get_existing_unassigned_integrator(self):
        """Verify existing integrator 'NuevoProyecto PendienteAsig' (if exists) has no gestor"""
        res = self.session.get(f"{BASE_URL}/api/integrators")
        assert res.status_code == 200
        
        integrators = res.json()
        
        # Look for the mentioned test integrator
        unassigned_found = False
        for intg in integrators:
            if not intg.get("gestor"):
                unassigned_found = True
                print(f"✓ Found unassigned integrator: {intg['name']} (id: {intg['integrator_id']})")
                break
        
        if not unassigned_found:
            print("No unassigned integrators found in current data")
        
        # This test just verifies the endpoint works and returns data correctly
        assert isinstance(integrators, list)
        print(f"✓ Total integrators: {len(integrators)}")


class TestIntegratorCRUDWithoutGestor:
    """Verify CRUD operations work without gestor field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200
        data = login_res.json()
        token = data.get("session_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
        # Cleanup
        integrators_res = self.session.get(f"{BASE_URL}/api/integrators")
        if integrators_res.status_code == 200:
            for intg in integrators_res.json():
                if intg.get('name', '').startswith('TEST_IT109_CRUD_'):
                    self.session.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}")
    
    def test_create_minimal_integrator(self):
        """Create integrator with only required fields (no gestor)"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_IT109_CRUD_Minimal_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "MinimalApp",
            "integration_modality": "REST"
        }
        
        res = self.session.post(f"{BASE_URL}/api/integrators", json=payload)
        assert res.status_code == 200, f"Create failed: {res.text}"
        
        data = res.json()
        assert data["name"] == payload["name"]
        assert data.get("gestor") in [None, ""]
        assert data.get("integrator_status") == "En proceso"  # Default status
        print("✓ Minimal integrator created successfully without gestor")
    
    def test_update_integrator_without_gestor(self):
        """Update integrator without changing gestor"""
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT109_CRUD_Update_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": "UpdateTestApp",
            "integration_modality": "REST"
        }
        
        create_res = self.session.post(f"{BASE_URL}/api/integrators", json=create_payload)
        assert create_res.status_code == 200
        integrator = create_res.json()
        
        # Update with new app_name but no gestor
        update_payload = {
            "name": integrator["name"],
            "integrator_type": "Integrador",
            "app_name": "UpdatedAppName",
            "integration_modality": "REST",
            "integrator_status": "Certificado"
        }
        
        update_res = self.session.put(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}", json=update_payload)
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated = update_res.json()
        assert updated["app_name"] == "UpdatedAppName"
        assert updated["integrator_status"] == "Certificado"
        print("✓ Integrator updated successfully without gestor field")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
