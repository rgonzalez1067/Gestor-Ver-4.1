"""
Test RBAC System - Iteration 129
Tests for strict RBAC implementation where 'read' permission is purely consultive.
Backend: POST/PUT/PATCH/DELETE blocked with 403 for 'read' permission users
Frontend: Action buttons hidden for read-only users
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Avila*0226*02"


class TestRBACBackend:
    """Test RBAC middleware enforcement on backend APIs"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token for setup operations"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def read_only_user(self, admin_token):
        """Create a read-only test user and return credentials"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"test_readonly_{unique_id}@test.com"
        password = "TestPass123!"
        
        # Register new user
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "ReadOnly",
            "cedula": f"V{unique_id}",
            "phone": "04121234567",
            "cargo": "Tester",
            "departamento": "Ventas",
            "sede": "PYME"
        })
        
        if register_response.status_code not in [200, 201]:
            pytest.skip(f"User registration failed: {register_response.text}")
        
        user_data = register_response.json()
        user_id = user_data.get("user", {}).get("user_id")
        
        # Set all permissions to 'read' using admin token
        all_read_permissions = {
            "clientes": "read",
            "cotizaciones": "read",
            "bancos": "read",
            "medios_pago": "read",
            "dispositivos": "read",
            "integradores": "read",
            "configuracion": "read",
            "proyectos": "read",
            "inventarios": "read",
            "taller_equipos": "read",
            "nuevos_productos": "read"
        }
        
        perm_response = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            json=all_read_permissions,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if perm_response.status_code != 200:
            pytest.skip(f"Setting permissions failed: {perm_response.text}")
        
        # Re-login to get fresh token with updated permissions
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Re-login failed: {login_response.text}")
        
        return {
            "email": email,
            "password": password,
            "user_id": user_id,
            "token": login_response.json().get("session_token")
        }
    
    # ==================== CLIENTS MODULE ====================
    
    def test_read_user_can_get_clients(self, read_only_user):
        """Read-only user should be able to GET clients"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /clients should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /clients (status: {response.status_code})")
    
    def test_read_user_blocked_post_clients(self, read_only_user):
        """Read-only user should be blocked from POST clients"""
        response = requests.post(
            f"{BASE_URL}/api/clients",
            json={
                "rif": "J123456789",
                "legal_name": "Test Company",
                "fantasy_name": "Test",
                "segment": "Pymes",
                "contact1": {"name": "Test", "phone": "123", "email": "test@test.com"}
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /clients should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /clients (status: {response.status_code})")
    
    def test_read_user_blocked_put_clients(self, read_only_user, admin_token):
        """Read-only user should be blocked from PUT clients"""
        # First get a client ID using admin
        clients_response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        clients = clients_response.json()
        if not clients:
            pytest.skip("No clients available for testing")
        
        client_id = clients[0].get("client_id")
        
        response = requests.put(
            f"{BASE_URL}/api/clients/{client_id}",
            json={"fantasy_name": "Updated Name"},
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"PUT /clients should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from PUT /clients (status: {response.status_code})")
    
    def test_read_user_blocked_delete_clients(self, read_only_user, admin_token):
        """Read-only user should be blocked from DELETE clients"""
        # Get a client ID
        clients_response = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        clients = clients_response.json()
        if not clients:
            pytest.skip("No clients available for testing")
        
        client_id = clients[0].get("client_id")
        
        response = requests.delete(
            f"{BASE_URL}/api/clients/{client_id}",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"DELETE /clients should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from DELETE /clients (status: {response.status_code})")
    
    # ==================== BANKS MODULE ====================
    
    def test_read_user_can_get_banks(self, read_only_user):
        """Read-only user should be able to GET banks"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /banks should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /banks (status: {response.status_code})")
    
    def test_read_user_blocked_post_banks(self, read_only_user):
        """Read-only user should be blocked from POST banks"""
        response = requests.post(
            f"{BASE_URL}/api/banks",
            json={
                "name": "Test Bank",
                "type": "Banco",
                "country": "Venezuela"
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /banks should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /banks (status: {response.status_code})")
    
    # ==================== QUOTES MODULE ====================
    
    def test_read_user_can_get_quotes(self, read_only_user):
        """Read-only user should be able to GET quotes"""
        response = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /quotes should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /quotes (status: {response.status_code})")
    
    def test_read_user_blocked_post_quotes(self, read_only_user):
        """Read-only user should be blocked from POST quotes"""
        response = requests.post(
            f"{BASE_URL}/api/quotes",
            json={
                "client_id": "test_client",
                "quote_type": "VPOS",
                "services": []
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /quotes should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /quotes (status: {response.status_code})")
    
    # ==================== HARDWARE MODULE ====================
    
    def test_read_user_can_get_hardware(self, read_only_user):
        """Read-only user should be able to GET hardware"""
        response = requests.get(
            f"{BASE_URL}/api/hardware",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /hardware should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /hardware (status: {response.status_code})")
    
    def test_read_user_blocked_post_hardware(self, read_only_user):
        """Read-only user should be blocked from POST hardware"""
        response = requests.post(
            f"{BASE_URL}/api/hardware",
            json={
                "name": "Test Device",
                "type": "Pinpad",
                "price_usd": 100
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /hardware should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /hardware (status: {response.status_code})")
    
    # ==================== SERVICES (MEDIOS PAGO) MODULE ====================
    
    def test_read_user_can_get_services(self, read_only_user):
        """Read-only user should be able to GET services"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /services should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /services (status: {response.status_code})")
    
    def test_read_user_blocked_post_services(self, read_only_user):
        """Read-only user should be blocked from POST services"""
        response = requests.post(
            f"{BASE_URL}/api/services",
            json={
                "name": "Test Service",
                "category": "General",
                "application_type": "both"
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /services should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /services (status: {response.status_code})")
    
    # ==================== INTEGRATORS MODULE ====================
    
    def test_read_user_can_get_integrators(self, read_only_user):
        """Read-only user should be able to GET integrators"""
        response = requests.get(
            f"{BASE_URL}/api/integrators",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /integrators should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /integrators (status: {response.status_code})")
    
    def test_read_user_blocked_post_integrators(self, read_only_user):
        """Read-only user should be blocked from POST integrators"""
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            json={
                "name": "Test Integrator",
                "app_name": "TestApp"
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /integrators should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /integrators (status: {response.status_code})")
    
    # ==================== INVENTORY MODULE ====================
    
    def test_read_user_can_get_inventory_warehouses(self, read_only_user):
        """Read-only user should be able to GET inventory warehouses"""
        response = requests.get(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /inventory/warehouses should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /inventory/warehouses (status: {response.status_code})")
    
    def test_read_user_blocked_post_inventory(self, read_only_user):
        """Read-only user should be blocked from POST inventory warehouses"""
        response = requests.post(
            f"{BASE_URL}/api/inventory/warehouses",
            json={
                "name": "Test Warehouse",
                "location": "Test Location"
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /inventory/warehouses should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /inventory/warehouses (status: {response.status_code})")
    
    # ==================== NEW PRODUCTS MODULE ====================
    
    def test_read_user_can_get_new_products(self, read_only_user):
        """Read-only user should be able to GET new products"""
        response = requests.get(
            f"{BASE_URL}/api/new-products",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /new-products should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /new-products (status: {response.status_code})")
    
    def test_read_user_blocked_post_new_products(self, read_only_user):
        """Read-only user should be blocked from POST new products"""
        response = requests.post(
            f"{BASE_URL}/api/new-products",
            json={
                "service_id": "test_service",
                "component_type": "VPOS/MPOS",
                "bank_id": "test_bank"
            },
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 403, f"POST /new-products should return 403 for read-only user, got {response.status_code}"
        print(f"✓ Read-only user blocked from POST /new-products (status: {response.status_code})")
    
    # ==================== PROJECTS MODULE ====================
    
    def test_read_user_can_get_projects(self, read_only_user):
        """Read-only user should be able to GET projects"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        assert response.status_code == 200, f"GET /projects should return 200, got {response.status_code}"
        print(f"✓ Read-only user can GET /projects (status: {response.status_code})")
    
    # ==================== ADMIN BYPASS ====================
    
    def test_admin_can_post_clients(self, admin_token):
        """Admin user should bypass RBAC and be able to POST clients"""
        unique_id = uuid.uuid4().hex[:8]
        response = requests.post(
            f"{BASE_URL}/api/clients",
            json={
                "rif": f"J{unique_id}",
                "legal_name": f"Test Admin Company {unique_id}",
                "fantasy_name": f"Test Admin {unique_id}",
                "segment": "Pymes",
                "contact1": {"name": "Admin Test", "phone": "123", "email": "admin@test.com"}
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Admin should be able to create (201) or get validation error (422) but NOT 403
        assert response.status_code != 403, f"Admin should not get 403, got {response.status_code}"
        print(f"✓ Admin bypasses RBAC for POST /clients (status: {response.status_code})")
    
    def test_admin_can_post_banks(self, admin_token):
        """Admin user should bypass RBAC and be able to POST banks"""
        unique_id = uuid.uuid4().hex[:8]
        response = requests.post(
            f"{BASE_URL}/api/banks",
            json={
                "name": f"Test Admin Bank {unique_id}",
                "type": "Banco",
                "country": "Venezuela"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Admin should be able to create (201) or get validation error (422) but NOT 403
        assert response.status_code != 403, f"Admin should not get 403, got {response.status_code}"
        print(f"✓ Admin bypasses RBAC for POST /banks (status: {response.status_code})")


class TestRBACPermissionLevels:
    """Test different permission levels"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("session_token")
    
    def test_admin_login_returns_admin_role(self, admin_token):
        """Verify admin user has admin role"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        user_data = response.json()
        assert user_data.get("role") == "admin", f"Expected admin role, got {user_data.get('role')}"
        print(f"✓ Admin user has role='admin'")
    
    def test_new_user_gets_read_permissions_by_default(self, admin_token):
        """Verify new users get 'read' permissions by default (not first user)"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"test_newuser_{unique_id}@test.com"
        
        # Register new user
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "TestPass123!",
            "first_name": "New",
            "last_name": "User",
            "cedula": f"V{unique_id}",
            "phone": "04121234567",
            "cargo": "Tester",
            "departamento": "Ventas",
            "sede": "PYME"
        })
        
        if register_response.status_code not in [200, 201]:
            pytest.skip(f"User registration failed: {register_response.text}")
        
        user_data = register_response.json().get("user", {})
        permissions = user_data.get("permissions", {})
        
        # Non-first users should get 'read' permissions by default
        for module, level in permissions.items():
            assert level == "read", f"Expected 'read' for {module}, got {level}"
        
        print(f"✓ New user gets 'read' permissions by default")


class TestRBACErrorMessages:
    """Test RBAC error messages are informative"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def read_only_user(self, admin_token):
        """Create a read-only test user"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"test_readonly_err_{unique_id}@test.com"
        password = "TestPass123!"
        
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "ReadOnly",
            "cedula": f"V{unique_id}",
            "phone": "04121234567",
            "cargo": "Tester",
            "departamento": "Ventas",
            "sede": "PYME"
        })
        
        if register_response.status_code not in [200, 201]:
            pytest.skip(f"User registration failed: {register_response.text}")
        
        user_data = register_response.json()
        user_id = user_data.get("user", {}).get("user_id")
        
        # Set all permissions to 'read'
        all_read_permissions = {
            "clientes": "read",
            "cotizaciones": "read",
            "bancos": "read",
            "medios_pago": "read",
            "dispositivos": "read",
            "integradores": "read",
            "configuracion": "read",
            "proyectos": "read",
            "inventarios": "read",
            "taller_equipos": "read",
            "nuevos_productos": "read"
        }
        
        requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            json=all_read_permissions,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Re-login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        
        return {
            "token": login_response.json().get("session_token")
        }
    
    def test_403_error_contains_module_info(self, read_only_user):
        """Verify 403 error message contains module information"""
        response = requests.post(
            f"{BASE_URL}/api/clients",
            json={"rif": "J123", "legal_name": "Test"},
            headers={"Authorization": f"Bearer {read_only_user['token']}"}
        )
        
        assert response.status_code == 403
        error_detail = response.json().get("detail", "")
        # Error should mention the module or permission issue
        assert "clientes" in error_detail.lower() or "escritura" in error_detail.lower() or "permiso" in error_detail.lower(), \
            f"Error message should be informative, got: {error_detail}"
        print(f"✓ 403 error message is informative: {error_detail}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
