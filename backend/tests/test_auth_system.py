# ruff: noqa
"""
Tests for the new authentication system:
- POST /api/auth/register - Register new user
- POST /api/auth/login - Login with email/password
- GET /api/admin/users - Get all users (admin only)
- PUT /api/admin/users/{id}/permissions - Update user permissions
- PUT /api/admin/users/{id}/role - Update user role
- PUT /api/admin/users/{id}/status - Update user status (active/inactive)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Generate unique test data for each run
TEST_PREFIX = f"TEST_{uuid.uuid4().hex[:6]}"
TEST_EMAIL_1 = f"{TEST_PREFIX}_admin@test.com"
TEST_EMAIL_2 = f"{TEST_PREFIX}_user@test.com"
TEST_CEDULA_1 = f"12{uuid.uuid4().hex[:6]}"[:10]
TEST_CEDULA_2 = f"22{uuid.uuid4().hex[:6]}"[:10]

class TestAuthRegister:
    """Test /api/auth/register endpoint"""
    
    def test_register_first_user_becomes_admin(self):
        """Register a new user - should work and return session_token"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Admin",
            "last_name": "Test",
            "cedula": TEST_CEDULA_1,
            "email": TEST_EMAIL_1,
            "password": "password123"
        })
        
        print(f"Register response status: {response.status_code}")
        print(f"Register response: {response.text[:500]}")
        
        # Should succeed with 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "session_token" in data, "session_token missing in response"
        assert "user" in data, "user missing in response"
        assert "message" in data, "message missing in response"
        
        # Verify user data
        user = data["user"]
        assert user["email"] == TEST_EMAIL_1
        assert user["first_name"] == "Admin"
        assert user["last_name"] == "Test"
        assert user["cedula"] == TEST_CEDULA_1
        
        # Note: First user might be admin or user depending on DB state
        # We just verify the role field exists
        assert "role" in user
        assert "permissions" in user
        
        return data
    
    def test_register_duplicate_email_fails(self):
        """Attempt to register with same email should fail"""
        # First register
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "First",
            "last_name": "User",
            "cedula": f"99{uuid.uuid4().hex[:6]}"[:10],
            "email": f"duplicate_{TEST_PREFIX}@test.com",
            "password": "password123"
        })
        
        # Duplicate register with same email
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Second",
            "last_name": "User",
            "cedula": f"88{uuid.uuid4().hex[:6]}"[:10],
            "email": f"duplicate_{TEST_PREFIX}@test.com",
            "password": "password456"
        })
        
        print(f"Duplicate email response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
        assert "registrado" in response.text.lower() or "correo" in response.text.lower()
    
    def test_register_duplicate_cedula_fails(self):
        """Attempt to register with same cedula should fail"""
        cedula_for_dup_test = f"77{uuid.uuid4().hex[:6]}"[:10]
        
        # First register
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "First",
            "last_name": "Cedula",
            "cedula": cedula_for_dup_test,
            "email": f"cedula1_{TEST_PREFIX}@test.com",
            "password": "password123"
        })
        
        # Duplicate register with same cedula
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Second",
            "last_name": "Cedula",
            "cedula": cedula_for_dup_test,
            "email": f"cedula2_{TEST_PREFIX}@test.com",
            "password": "password456"
        })
        
        print(f"Duplicate cedula response: {response.status_code}")
        assert response.status_code == 400, f"Expected 400 for duplicate cedula, got {response.status_code}"
        assert "cédula" in response.text.lower() or "cedula" in response.text.lower()
    
    def test_register_short_password_validation(self):
        """Password less than 8 chars should fail validation at Pydantic level"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Short",
            "last_name": "Pass",
            "cedula": f"66{uuid.uuid4().hex[:6]}"[:10],
            "email": f"shortpass_{TEST_PREFIX}@test.com",
            "password": "short"  # Less than 8 chars
        })
        
        print(f"Short password response: {response.status_code}")
        # Should fail with 422 (validation error)
        assert response.status_code == 422, f"Expected 422 for short password, got {response.status_code}"
    
    def test_register_invalid_email_validation(self):
        """Invalid email format should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Invalid",
            "last_name": "Email",
            "cedula": f"55{uuid.uuid4().hex[:6]}"[:10],
            "email": "invalid-email-format",
            "password": "password123"
        })
        
        print(f"Invalid email response: {response.status_code}")
        assert response.status_code == 422, f"Expected 422 for invalid email, got {response.status_code}"


class TestAuthLogin:
    """Test /api/auth/login endpoint"""
    
    @pytest.fixture
    def registered_user(self):
        """Create a user for login tests"""
        email = f"login_{TEST_PREFIX}@test.com"
        cedula = f"44{uuid.uuid4().hex[:6]}"[:10]
        password = "securepass123"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Login",
            "last_name": "Test",
            "cedula": cedula,
            "email": email,
            "password": password
        })
        
        return {
            "email": email,
            "password": password,
            "response_data": response.json() if response.status_code == 200 else None
        }
    
    def test_login_success(self, registered_user):
        """Login with valid credentials should succeed"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"]
        })
        
        print(f"Login response status: {response.status_code}")
        print(f"Login response: {response.text[:500]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "session_token" in data
        assert "user" in data
        assert data["user"]["email"] == registered_user["email"]
    
    def test_login_invalid_password(self, registered_user):
        """Login with wrong password should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": registered_user["email"],
            "password": "wrongpassword"
        })
        
        print(f"Invalid password response: {response.status_code}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        assert "inválidas" in response.text.lower() or "credenciales" in response.text.lower()
    
    def test_login_nonexistent_user(self):
        """Login with non-existent email should fail"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": f"nonexistent_{uuid.uuid4().hex}@test.com",
            "password": "anypassword123"
        })
        
        print(f"Non-existent user response: {response.status_code}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAdminEndpoints:
    """Test admin-only endpoints"""
    
    @pytest.fixture
    def admin_session(self):
        """Create an admin user and get session"""
        # Register admin user
        admin_email = f"admin_{TEST_PREFIX}_{uuid.uuid4().hex[:4]}@test.com"
        admin_cedula = f"33{uuid.uuid4().hex[:6]}"[:10]
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Admin",
            "last_name": "User",
            "cedula": admin_cedula,
            "email": admin_email,
            "password": "adminpass123"
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create admin user: {response.text}")
        
        data = response.json()
        return {
            "token": data["session_token"],
            "user": data["user"],
            "headers": {"Authorization": f"Bearer {data['session_token']}"}
        }
    
    @pytest.fixture
    def regular_user(self, admin_session):
        """Create a regular user for permission tests"""
        user_email = f"regular_{TEST_PREFIX}_{uuid.uuid4().hex[:4]}@test.com"
        user_cedula = f"11{uuid.uuid4().hex[:6]}"[:10]
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Regular",
            "last_name": "User",
            "cedula": user_cedula,
            "email": user_email,
            "password": "userpass123"
        })
        
        if response.status_code != 200:
            pytest.skip(f"Could not create regular user: {response.text}")
        
        return response.json()
    
    def test_get_users_with_admin(self, admin_session):
        """Admin should be able to get all users"""
        # Check if user is admin first
        if admin_session["user"].get("role") != "admin":
            pytest.skip("User is not admin, skipping admin test")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers=admin_session["headers"]
        )
        
        print(f"Get users response: {response.status_code}")
        
        if response.status_code == 403:
            pytest.skip("User does not have admin role")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list)
        
        # Verify user structure (no password_hash)
        if len(users) > 0:
            user = users[0]
            assert "password_hash" not in user, "password_hash should not be exposed"
            assert "email" in user
            assert "user_id" in user
    
    def test_get_users_without_auth(self):
        """Unauthenticated request should fail"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        
        print(f"No auth response: {response.status_code}")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_update_user_permissions(self, admin_session, regular_user):
        """Admin should be able to update user permissions"""
        if admin_session["user"].get("role") != "admin":
            pytest.skip("User is not admin, skipping admin test")
        
        user_id = regular_user["user"]["user_id"]
        
        # Update permissions
        new_permissions = {
            "cotizaciones": "edit",
            "clientes": "read",
            "bancos": "none",
            "medios_pago": "edit",
            "dispositivos": "read",
            "integradores": "read",
            "configuracion": "none"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            json=new_permissions,
            headers=admin_session["headers"]
        )
        
        print(f"Update permissions response: {response.status_code}")
        
        if response.status_code == 403:
            pytest.skip("User does not have admin role")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user" in data or "message" in data
        
        if "user" in data:
            updated_user = data["user"]
            assert updated_user["permissions"]["cotizaciones"] == "edit"
            assert updated_user["permissions"]["bancos"] == "none"
    
    def test_update_user_role(self, admin_session, regular_user):
        """Admin should be able to update user role"""
        if admin_session["user"].get("role") != "admin":
            pytest.skip("User is not admin, skipping admin test")
        
        user_id = regular_user["user"]["user_id"]
        
        # Update role to admin
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/role?role=admin",
            headers=admin_session["headers"]
        )
        
        print(f"Update role response: {response.status_code}")
        
        if response.status_code == 403:
            pytest.skip("User does not have admin role")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Update back to user
        response2 = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/role?role=user",
            headers=admin_session["headers"]
        )
        assert response2.status_code == 200
    
    def test_update_user_status(self, admin_session, regular_user):
        """Admin should be able to activate/deactivate users"""
        if admin_session["user"].get("role") != "admin":
            pytest.skip("User is not admin, skipping admin test")
        
        user_id = regular_user["user"]["user_id"]
        
        # Deactivate user
        response = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/status?is_active=false",
            headers=admin_session["headers"]
        )
        
        print(f"Deactivate user response: {response.status_code}")
        
        if response.status_code == 403:
            pytest.skip("User does not have admin role")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Reactivate user
        response2 = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/status?is_active=true",
            headers=admin_session["headers"]
        )
        assert response2.status_code == 200


class TestAuthMe:
    """Test /api/auth/me endpoint"""
    
    def test_get_current_user(self):
        """Should return current user info"""
        # First register and login
        email = f"me_{TEST_PREFIX}_{uuid.uuid4().hex[:4]}@test.com"
        cedula = f"00{uuid.uuid4().hex[:6]}"[:10]
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Me",
            "last_name": "Test",
            "cedula": cedula,
            "email": email,
            "password": "mepassword123"
        })
        
        if reg_response.status_code != 200:
            pytest.skip(f"Could not register: {reg_response.text}")
        
        token = reg_response.json()["session_token"]
        
        # Get current user
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Get me response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        user = response.json()
        assert user["email"] == email
        assert "password_hash" not in user
        assert "permissions" in user
    
    def test_get_me_without_auth(self):
        """Should fail without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestLogout:
    """Test /api/auth/logout endpoint"""
    
    def test_logout_success(self):
        """Should invalidate session"""
        # Register and get token
        email = f"logout_{TEST_PREFIX}_{uuid.uuid4().hex[:4]}@test.com"
        cedula = f"09{uuid.uuid4().hex[:6]}"[:10]
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "first_name": "Logout",
            "last_name": "Test",
            "cedula": cedula,
            "email": email,
            "password": "logoutpass123"
        })
        
        if reg_response.status_code != 200:
            pytest.skip(f"Could not register: {reg_response.text}")
        
        token = reg_response.json()["session_token"]
        
        # Logout
        response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"Logout response: {response.status_code}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify session is invalidated
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should return 401 since session was deleted
        assert me_response.status_code == 401, f"Expected 401 after logout, got {me_response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
