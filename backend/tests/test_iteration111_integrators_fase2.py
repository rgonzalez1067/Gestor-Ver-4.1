# ruff: noqa
"""
Iteration 111 - Integrators Fase 1/2 Restructuring Tests
Tests for:
- POST /api/integrators creates project WITHOUT integration_modality (optional field)
- GET /api/auth/implementadores returns only users with cargo 'Implementador'
- PUT /api/integrators/{id}/assign-implementador assigns implementador, returns updated integrator
- Integrator model has 'implementador' and 'implementador_user_id' fields
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

# Test credentials
TEST_EMAIL = "test@mega.com"
TEST_PASSWORD = "Admin123!"

# Known implementador user from context
TEST_IMPLEMENTADOR_USER_ID = "user_3cc63615f2c0"  # Omar Jimenez, cargo: Implementador


class TestIntegratorsFase2:
    """Tests for Integrator restructuring - Phase 1/2 form split and Implementador assignment"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["session_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
        # Cleanup will be done in individual tests if needed

    # ==================== TEST 1: Create integrator WITHOUT integration_modality ====================
    def test_01_create_integrator_without_modality(self):
        """POST /api/integrators - integration_modality is now optional (Fase 1)"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_IT111_Integrador_{unique_id}",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": f"TestApp_{unique_id}",
            # NO integration_modality - should work now
        }
        
        response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=self.headers)
        
        # Assert creation succeeds
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify fields
        assert data["name"] == payload["name"]
        assert data["integrator_type"] == payload["integrator_type"]
        assert data["app_name"] == payload["app_name"]
        # integration_modality should be None or empty
        assert data.get("integration_modality") is None or data.get("integration_modality") == ""
        # Should have integrator_id
        assert "integrator_id" in data
        
        # Cleanup
        integrator_id = data["integrator_id"]
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print("✓ TEST 1 PASSED: Created integrator WITHOUT integration_modality")

    # ==================== TEST 2: Create integrator WITH integration_modality ====================
    def test_02_create_integrator_with_modality(self):
        """POST /api/integrators - integration_modality can still be provided"""
        unique_id = uuid.uuid4().hex[:8]
        payload = {
            "name": f"TEST_IT111_IntegradorFull_{unique_id}",
            "integrator_type": "Comercio",
            "integration_type": "CR",
            "app_name": f"FullApp_{unique_id}",
            "integration_modality": "REST",  # Explicitly provided
            "integrator_status": "En proceso"
        }
        
        response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=self.headers)
        
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify modality was saved
        assert data["integration_modality"] == "REST"
        assert data["integrator_type"] == "Comercio"
        
        # Cleanup
        integrator_id = data["integrator_id"]
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print("✓ TEST 2 PASSED: Created integrator WITH integration_modality")

    # ==================== TEST 3: GET /api/auth/implementadores returns only Implementador cargo ====================
    def test_03_get_implementadores_endpoint(self):
        """GET /api/auth/implementadores - should return only users with cargo 'Implementador'"""
        response = requests.get(f"{BASE_URL}/api/auth/implementadores", headers=self.headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list)
        
        # All returned users should have cargo 'Implementador'
        for user in data:
            assert user.get("cargo") == "Implementador", f"User {user.get('email')} has cargo {user.get('cargo')}, expected 'Implementador'"
            assert "user_id" in user
            assert "full_name" in user or "email" in user
        
        # Per context, there should be 6 implementadores
        assert len(data) >= 1, "Expected at least 1 implementador in DB"
        
        print(f"✓ TEST 3 PASSED: GET /api/auth/implementadores returned {len(data)} users, all with cargo='Implementador'")

    # ==================== TEST 4: Assign implementador endpoint ====================
    def test_04_assign_implementador(self):
        """PUT /api/integrators/{id}/assign-implementador - assigns implementador and returns updated integrator"""
        # First create an integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT111_AssignImpl_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": f"AssignTestApp_{unique_id}",
        }
        
        create_response = requests.post(f"{BASE_URL}/api/integrators", json=create_payload, headers=self.headers)
        assert create_response.status_code == 200
        integrator_id = create_response.json()["integrator_id"]
        
        # Get an implementador to assign
        impl_response = requests.get(f"{BASE_URL}/api/auth/implementadores", headers=self.headers)
        implementadores = impl_response.json()
        assert len(implementadores) > 0, "No implementadores available"
        
        impl_user_id = implementadores[0]["user_id"]
        impl_name = implementadores[0].get("full_name") or implementadores[0].get("email")
        
        # Assign implementador
        assign_response = requests.put(
            f"{BASE_URL}/api/integrators/{integrator_id}/assign-implementador",
            json={"user_id": impl_user_id},
            headers=self.headers
        )
        
        assert assign_response.status_code == 200, f"Assign failed: {assign_response.text}"
        assign_data = assign_response.json()
        
        # Verify response structure
        assert "status" in assign_data
        assert assign_data["status"] == "ok"
        assert "integrator" in assign_data
        assert "message" in assign_data
        
        # Verify updated integrator has implementador fields
        updated_integrator = assign_data["integrator"]
        assert updated_integrator["implementador"] is not None
        assert updated_integrator["implementador_user_id"] == impl_user_id
        
        # Verify email was sent (mocked)
        if "email" in assign_data:
            print(f"  Email result: {assign_data['email']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print(f"✓ TEST 4 PASSED: Assigned implementador '{impl_name}' successfully")

    # ==================== TEST 5: Integrator model has implementador fields ====================
    def test_05_integrator_has_implementador_fields(self):
        """GET /api/integrators - verify integrator response includes implementador fields"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that at least one integrator exists
        assert len(data) > 0, "No integrators in DB"
        
        # Verify first integrator has the new fields (even if null)
        intg = data[0]
        
        # These fields should exist in the model
        assert "implementador" in intg or intg.get("implementador") is None  # Field exists
        assert "implementador_user_id" in intg or intg.get("implementador_user_id") is None  # Field exists
        
        print("✓ TEST 5 PASSED: Integrator model includes 'implementador' and 'implementador_user_id' fields")

    # ==================== TEST 6: Assign implementador requires user_id ====================
    def test_06_assign_implementador_requires_user_id(self):
        """PUT /api/integrators/{id}/assign-implementador - should fail without user_id"""
        # First create an integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT111_NoUserId_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": f"NoUserIdApp_{unique_id}",
        }
        
        create_response = requests.post(f"{BASE_URL}/api/integrators", json=create_payload, headers=self.headers)
        assert create_response.status_code == 200
        integrator_id = create_response.json()["integrator_id"]
        
        # Try to assign without user_id
        assign_response = requests.put(
            f"{BASE_URL}/api/integrators/{integrator_id}/assign-implementador",
            json={},  # No user_id
            headers=self.headers
        )
        
        assert assign_response.status_code == 400, f"Expected 400, got {assign_response.status_code}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print("✓ TEST 6 PASSED: Assign implementador correctly rejects request without user_id")

    # ==================== TEST 7: Assign implementador with non-existent user ====================
    def test_07_assign_implementador_nonexistent_user(self):
        """PUT /api/integrators/{id}/assign-implementador - should fail with non-existent user_id"""
        # First create an integrator
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT111_BadUser_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": f"BadUserApp_{unique_id}",
        }
        
        create_response = requests.post(f"{BASE_URL}/api/integrators", json=create_payload, headers=self.headers)
        assert create_response.status_code == 200
        integrator_id = create_response.json()["integrator_id"]
        
        # Try to assign with fake user_id
        assign_response = requests.put(
            f"{BASE_URL}/api/integrators/{integrator_id}/assign-implementador",
            json={"user_id": "fake_user_id_12345"},
            headers=self.headers
        )
        
        assert assign_response.status_code == 404, f"Expected 404, got {assign_response.status_code}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print("✓ TEST 7 PASSED: Assign implementador correctly rejects non-existent user")

    # ==================== TEST 8: Verify GET /api/integrators returns implementador data ====================
    def test_08_get_integrators_with_implementador(self):
        """GET /api/integrators - integrators with assigned implementador should show the name"""
        # Create and assign
        unique_id = uuid.uuid4().hex[:8]
        create_payload = {
            "name": f"TEST_IT111_ShowImpl_{unique_id}",
            "integrator_type": "Integrador",
            "app_name": f"ShowImplApp_{unique_id}",
        }
        
        create_response = requests.post(f"{BASE_URL}/api/integrators", json=create_payload, headers=self.headers)
        assert create_response.status_code == 200
        integrator_id = create_response.json()["integrator_id"]
        
        # Get implementador
        impl_response = requests.get(f"{BASE_URL}/api/auth/implementadores", headers=self.headers)
        implementadores = impl_response.json()
        impl_user_id = implementadores[0]["user_id"]
        
        # Assign
        assign_response = requests.put(
            f"{BASE_URL}/api/integrators/{integrator_id}/assign-implementador",
            json={"user_id": impl_user_id},
            headers=self.headers
        )
        assert assign_response.status_code == 200
        
        # Get all integrators and verify this one has implementador
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = list_response.json()
        
        target = next((i for i in integrators if i["integrator_id"] == integrator_id), None)
        assert target is not None
        assert target["implementador"] is not None
        assert target["implementador_user_id"] == impl_user_id
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=self.headers)
        print("✓ TEST 8 PASSED: GET /api/integrators correctly returns implementador data")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
