"""
Iteration 161: Delete User Feature + Frontend Regression Tests
Tests:
1. DELETE /api/admin/users/{user_id} - Delete user functionality
2. Login regression
3. User management CRUD regression
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

class TestDeleteUserFeature:
    """Tests for the new Delete User feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("session_token")
            self.admin_user_id = data.get("user", {}).get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Admin login failed - skipping tests")
    
    def test_01_login_works(self):
        """Regression: Login endpoint works correctly"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert "user" in data
        assert data["user"]["email"] == "rgonzalez@megasoft.com.ve"
        print("✓ Login works correctly")
    
    def test_02_get_users_list(self):
        """Regression: Admin can get users list"""
        response = self.session.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)
        print(f"✓ Got {len(users)} users from admin endpoint")
    
    def test_03_create_test_user_for_deletion(self):
        """Create a test user that will be deleted"""
        unique_id = uuid.uuid4().hex[:8]
        test_user_data = {
            "email": f"TEST_delete_user_{unique_id}@test.com",
            "password": "TestPass123!",
            "first_name": "TEST_Delete",
            "last_name": "User",
            "cedula": f"V-TEST{unique_id}",
            "phone": "+58 412 1234567",
            "cargo": "Analista",
            "departamento": "Desarrollo",
            "sede": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/admin/users/create", json=test_user_data)
        assert response.status_code == 200, f"Failed to create test user: {response.text}"
        
        data = response.json()
        assert "user" in data
        self.test_user_id = data["user"]["user_id"]
        self.test_user_email = test_user_data["email"]
        print(f"✓ Created test user: {self.test_user_email} (ID: {self.test_user_id})")
        
        # Store for next test
        pytest.test_user_id = self.test_user_id
        pytest.test_user_email = self.test_user_email
    
    def test_04_delete_user_success(self):
        """Test: DELETE /api/admin/users/{user_id} deletes user successfully"""
        test_user_id = getattr(pytest, 'test_user_id', None)
        if not test_user_id:
            pytest.skip("No test user created")
        
        response = self.session.delete(f"{BASE_URL}/api/admin/users/{test_user_id}")
        assert response.status_code == 200, f"Delete failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "eliminado" in data["message"].lower() or "deleted" in data["message"].lower()
        print(f"✓ User deleted successfully: {data['message']}")
    
    def test_05_verify_user_deleted(self):
        """Verify the deleted user no longer exists"""
        test_user_id = getattr(pytest, 'test_user_id', None)
        if not test_user_id:
            pytest.skip("No test user to verify")
        
        # Try to get users list and verify deleted user is not there
        response = self.session.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 200
        
        users = response.json()
        user_ids = [u.get("user_id") for u in users]
        assert test_user_id not in user_ids, "Deleted user still appears in users list"
        print("✓ Verified user no longer exists in users list")
    
    def test_06_delete_self_should_fail(self):
        """Test: Admin cannot delete themselves"""
        response = self.session.delete(f"{BASE_URL}/api/admin/users/{self.admin_user_id}")
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        print(f"✓ Self-deletion correctly blocked: {data['detail']}")
    
    def test_07_delete_nonexistent_user(self):
        """Test: Deleting non-existent user returns 404"""
        fake_user_id = "user_nonexistent123"
        response = self.session.delete(f"{BASE_URL}/api/admin/users/{fake_user_id}")
        assert response.status_code == 404
        print("✓ Non-existent user deletion returns 404")


class TestUserManagementRegression:
    """Regression tests for User Management CRUD"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Admin login failed")
    
    def test_01_create_user(self):
        """Regression: Create user works"""
        unique_id = uuid.uuid4().hex[:8]
        user_data = {
            "email": f"TEST_regression_{unique_id}@test.com",
            "password": "TestPass123!",
            "first_name": "TEST_Regression",
            "last_name": "User",
            "cedula": f"V-REG{unique_id}",
            "sede": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/admin/users/create", json=user_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "user" in data
        pytest.regression_user_id = data["user"]["user_id"]
        print(f"✓ Create user works: {user_data['email']}")
    
    def test_02_update_user(self):
        """Regression: Update user works"""
        user_id = getattr(pytest, 'regression_user_id', None)
        if not user_id:
            pytest.skip("No user to update")
        
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "cargo": "Gerente"
        }
        
        response = self.session.put(f"{BASE_URL}/api/admin/users/{user_id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["user"]["first_name"] == "Updated"
        print("✓ Update user works")
    
    def test_03_toggle_user_status(self):
        """Regression: Toggle user status works"""
        user_id = getattr(pytest, 'regression_user_id', None)
        if not user_id:
            pytest.skip("No user to toggle")
        
        # Deactivate
        response = self.session.put(f"{BASE_URL}/api/admin/users/{user_id}/status?is_active=false")
        assert response.status_code == 200
        print("✓ Deactivate user works")
        
        # Reactivate
        response = self.session.put(f"{BASE_URL}/api/admin/users/{user_id}/status?is_active=true")
        assert response.status_code == 200
        print("✓ Reactivate user works")
    
    def test_04_cleanup_regression_user(self):
        """Cleanup: Delete regression test user"""
        user_id = getattr(pytest, 'regression_user_id', None)
        if user_id:
            response = self.session.delete(f"{BASE_URL}/api/admin/users/{user_id}")
            assert response.status_code == 200
            print("✓ Cleanup: Regression user deleted")


class TestPagesLoadRegression:
    """Regression tests for main pages API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "admin123"
        })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Admin login failed")
    
    def test_quotes_endpoint(self):
        """Regression: Quotes endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Quotes endpoint works: {len(data)} quotes")
    
    def test_projects_endpoint(self):
        """Regression: Projects endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Projects endpoint works: {len(data)} projects")
    
    def test_new_products_endpoint(self):
        """Regression: New Products endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/new-products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ New Products endpoint works: {len(data)} products")
    
    def test_clients_endpoint(self):
        """Regression: Clients endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Clients endpoint works: {len(data)} clients")
    
    def test_banks_endpoint(self):
        """Regression: Banks endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/banks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Banks endpoint works: {len(data)} banks")
    
    def test_services_endpoint(self):
        """Regression: Services endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/services")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Services endpoint works: {len(data)} services")
