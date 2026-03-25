"""
Test Suite for Iteration 130 - ABAC Evolution Features
Tests the three pillars of the ABAC system:
1. Special Permissions (overrides) - allows read-only users to have specific write actions
2. Hierarchical Quote Visibility - Ejecutivo/Coordinador/Gerente/Admin hierarchy
3. Warehouse Jurisdiction - users can only edit their assigned warehouse
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Avila*0226*02"

class TestABACFeatures:
    """Test suite for ABAC (Attribute-Based Access Control) features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.admin_token = None
        self.test_user_id = None
        self.test_user_token = None
        self.test_warehouse_id = None
        yield
        # Cleanup will be done in individual tests
    
    def login_admin(self):
        """Login as admin and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        self.admin_token = data["session_token"]
        return self.admin_token
    
    def create_test_user(self, cargo="Ejecutivo de Ventas Pyme", departamento="Ventas"):
        """Create a test user with specific cargo and departamento"""
        unique_id = uuid.uuid4().hex[:8]
        email = f"TEST_abac_{unique_id}@test.com"
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/users/create",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={
                "email": email,
                "password": "TestPass123!",
                "first_name": "Test",
                "last_name": f"ABAC_{unique_id}",
                "cedula": f"V-{unique_id}",
                "cargo": cargo,
                "departamento": departamento,
                "sede": "PYME"
            }
        )
        assert response.status_code == 200, f"Failed to create test user: {response.text}"
        user_data = response.json()["user"]
        return user_data, email
    
    def login_test_user(self, email, password="TestPass123!"):
        """Login as test user and return token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        assert response.status_code == 200, f"Test user login failed: {response.text}"
        data = response.json()
        return data["session_token"], data["user"]


class TestSpecialPermissions(TestABACFeatures):
    """Test Pillar 1: Special Permissions (overrides)"""
    
    def test_special_permissions_endpoint_saves_and_returns(self):
        """Test PUT /api/admin/users/{user_id}/special-permissions saves and returns array"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Set special permissions
        special_perms = ["integradores:create", "cotizaciones:create"]
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"special_permissions": special_perms}
        )
        
        assert response.status_code == 200, f"Failed to set special permissions: {response.text}"
        data = response.json()
        assert "user" in data
        assert data["user"]["special_permissions"] == special_perms
        print(f"✓ Special permissions saved: {special_perms}")
    
    def test_special_permissions_invalid_format_filtered(self):
        """Test that invalid permission formats are filtered out"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Try to set invalid permissions (no colon)
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"special_permissions": ["invalid", "integradores:create", "also_invalid"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Only valid format should be saved
        assert data["user"]["special_permissions"] == ["integradores:create"]
        print("✓ Invalid permission formats correctly filtered")
    
    def test_rbac_override_user_with_read_and_create_can_post(self):
        """Test user with read + integradores:create can POST /api/integrators"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Set user to read-only for integradores
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"integradores": "read"}
        )
        assert response.status_code == 200
        
        # Add special permission for create
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"special_permissions": ["integradores:create"]}
        )
        assert response.status_code == 200
        
        # Login as test user
        test_token, _ = self.login_test_user(email)
        
        # Try to POST (should succeed due to override)
        response = self.session.post(
            f"{BASE_URL}/api/integrators",
            headers={"Authorization": f"Bearer {test_token}"},
            json={
                "name": f"TEST_Integrator_{uuid.uuid4().hex[:6]}",
                "integrator_type": "Integrador",
                "app_name": "TestApp"
            }
        )
        
        assert response.status_code == 200, f"POST should succeed with special permission: {response.text}"
        print("✓ User with read + integradores:create can POST to /api/integrators")
    
    def test_rbac_override_user_cannot_put_without_edit(self):
        """Test user with read + integradores:create CANNOT PUT /api/integrators"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Set user to read-only for integradores with create override
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"integradores": "read"}
        )
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"special_permissions": ["integradores:create"]}
        )
        
        # First create an integrator as admin
        response = self.session.post(
            f"{BASE_URL}/api/integrators",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={
                "name": f"TEST_Integrator_{uuid.uuid4().hex[:6]}",
                "integrator_type": "Integrador",
                "app_name": "TestApp"
            }
        )
        assert response.status_code == 200
        integrator_id = response.json()["integrator_id"]
        
        # Login as test user
        test_token, _ = self.login_test_user(email)
        
        # Try to PUT (should fail - only :create override, not :edit)
        response = self.session.put(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            headers={"Authorization": f"Bearer {test_token}"},
            json={
                "name": "Updated Name",
                "integrator_type": "Integrador",
                "app_name": "TestApp"
            }
        )
        
        assert response.status_code == 403, f"PUT should be blocked: {response.text}"
        print("✓ User with read + integradores:create CANNOT PUT to /api/integrators")
    
    def test_login_response_includes_special_permissions(self):
        """Test that login response includes special_permissions field"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Set special permissions
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"special_permissions": ["integradores:create"]}
        )
        
        # Login as test user
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "TestPass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "special_permissions" in data["user"], "Login response missing special_permissions"
        assert data["user"]["special_permissions"] == ["integradores:create"]
        print("✓ Login response includes special_permissions")


class TestAlmacenAsignado(TestABACFeatures):
    """Test Pillar 3: Warehouse Jurisdiction (almacen_asignado)"""
    
    def test_almacen_endpoint_saves_and_returns(self):
        """Test PUT /api/admin/users/{user_id}/almacen saves and returns almacen_asignado"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # First get a warehouse
        response = self.session.get(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        warehouses = response.json()
        
        if not warehouses:
            # Create a test warehouse
            response = self.session.post(
                f"{BASE_URL}/api/inventory/warehouses",
                headers={"Authorization": f"Bearer {self.admin_token}"},
                json={"name": f"TEST_Warehouse_{uuid.uuid4().hex[:6]}", "location": "Test Location"}
            )
            assert response.status_code == 200
            warehouse_id = response.json()["warehouse_id"]
        else:
            warehouse_id = warehouses[0]["warehouse_id"]
        
        # Assign warehouse to user
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"almacen_asignado": warehouse_id}
        )
        
        assert response.status_code == 200, f"Failed to assign warehouse: {response.text}"
        data = response.json()
        assert data["user"]["almacen_asignado"] == warehouse_id
        print(f"✓ Almacén asignado saved: {warehouse_id}")
    
    def test_almacen_endpoint_validates_warehouse_exists(self):
        """Test that assigning non-existent warehouse returns 404"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Try to assign non-existent warehouse
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"almacen_asignado": "nonexistent_warehouse_id"}
        )
        
        assert response.status_code == 404, f"Should return 404 for non-existent warehouse: {response.text}"
        print("✓ Non-existent warehouse correctly returns 404")
    
    def test_almacen_can_be_unassigned(self):
        """Test that almacen can be set to null to unassign"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Unassign warehouse
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"almacen_asignado": None}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["almacen_asignado"] is None
        print("✓ Almacén can be unassigned (set to null)")
    
    def test_login_response_includes_almacen_asignado(self):
        """Test that login response includes almacen_asignado field"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Get a warehouse
        response = self.session.get(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        warehouses = response.json()
        
        if warehouses:
            warehouse_id = warehouses[0]["warehouse_id"]
            # Assign warehouse
            self.session.put(
                f"{BASE_URL}/api/admin/users/{user_id}/almacen",
                headers={"Authorization": f"Bearer {self.admin_token}"},
                json={"almacen_asignado": warehouse_id}
            )
        
        # Login as test user
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "TestPass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "almacen_asignado" in data["user"], "Login response missing almacen_asignado"
        print("✓ Login response includes almacen_asignado")
    
    def test_login_response_includes_cargo_and_departamento(self):
        """Test that login response includes cargo and departamento fields"""
        self.login_admin()
        user_data, email = self.create_test_user(cargo="Gerente de Ventas", departamento="Ventas")
        
        # Login as test user
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": "TestPass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "cargo" in data["user"], "Login response missing cargo"
        assert "departamento" in data["user"], "Login response missing departamento"
        assert data["user"]["cargo"] == "Gerente de Ventas"
        assert data["user"]["departamento"] == "Ventas"
        print("✓ Login response includes cargo and departamento")


class TestWarehouseJurisdiction(TestABACFeatures):
    """Test warehouse jurisdiction enforcement"""
    
    def test_user_can_write_to_assigned_warehouse(self):
        """Test user with almacen_asignado can write to their assigned warehouse"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Create a test warehouse
        response = self.session.post(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"name": f"TEST_WH_Assigned_{uuid.uuid4().hex[:6]}", "location": "Test"}
        )
        assert response.status_code == 200
        warehouse_id = response.json()["warehouse_id"]
        
        # Assign warehouse to user
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"almacen_asignado": warehouse_id}
        )
        
        # Give user edit permission for inventarios
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"inventarios": "edit"}
        )
        
        # Login as test user
        test_token, _ = self.login_test_user(email)
        
        # Try to update the assigned warehouse (should succeed)
        response = self.session.put(
            f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"notes": "Updated by assigned user"}
        )
        
        assert response.status_code == 200, f"Should be able to update assigned warehouse: {response.text}"
        print("✓ User can write to their assigned warehouse")
    
    def test_user_cannot_write_to_different_warehouse(self):
        """Test user with almacen_asignado gets 403 when trying to write to different warehouse"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Create two warehouses
        response = self.session.post(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"name": f"TEST_WH_Assigned_{uuid.uuid4().hex[:6]}", "location": "Test"}
        )
        assert response.status_code == 200
        assigned_warehouse_id = response.json()["warehouse_id"]
        
        response = self.session.post(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"name": f"TEST_WH_Other_{uuid.uuid4().hex[:6]}", "location": "Test"}
        )
        assert response.status_code == 200
        other_warehouse_id = response.json()["warehouse_id"]
        
        # Assign first warehouse to user
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"almacen_asignado": assigned_warehouse_id}
        )
        
        # Give user edit permission for inventarios
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"inventarios": "edit"}
        )
        
        # Login as test user
        test_token, _ = self.login_test_user(email)
        
        # Try to update the OTHER warehouse (should fail with 403)
        response = self.session.put(
            f"{BASE_URL}/api/inventory/warehouses/{other_warehouse_id}",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"notes": "Should not be allowed"}
        )
        
        assert response.status_code == 403, f"Should get 403 for different warehouse: {response.text}"
        assert "jurisdicción" in response.json().get("detail", "").lower() or "almacén" in response.json().get("detail", "").lower()
        print("✓ User gets 403 when trying to write to different warehouse")
    
    def test_admin_can_write_to_any_warehouse(self):
        """Test admin can write to any warehouse regardless of assignment"""
        self.login_admin()
        
        # Create a warehouse
        response = self.session.post(
            f"{BASE_URL}/api/inventory/warehouses",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"name": f"TEST_WH_Admin_{uuid.uuid4().hex[:6]}", "location": "Test"}
        )
        assert response.status_code == 200
        warehouse_id = response.json()["warehouse_id"]
        
        # Admin should be able to update any warehouse
        response = self.session.put(
            f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"notes": "Updated by admin"}
        )
        
        assert response.status_code == 200, f"Admin should be able to update any warehouse: {response.text}"
        print("✓ Admin can write to any warehouse")


class TestHierarchicalQuotes(TestABACFeatures):
    """Test Pillar 2: Hierarchical Quote Visibility"""
    
    def test_ejecutivo_sees_only_own_quotes(self):
        """Test Ejecutivo only sees quotes they created"""
        self.login_admin()
        
        # Create an Ejecutivo user
        user_data, email = self.create_test_user(cargo="Ejecutivo de Ventas Pyme", departamento="Ventas")
        user_id = user_data["user_id"]
        
        # Give user read permission for cotizaciones
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"cotizaciones": "edit", "clientes": "edit"}
        )
        
        # Login as test user
        test_token, user_info = self.login_test_user(email)
        
        # Get quotes as Ejecutivo
        response = self.session.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        assert response.status_code == 200
        quotes = response.json()
        
        # All quotes should be created by this user (or empty if no quotes)
        for quote in quotes:
            assert quote.get("created_by_user_id") == user_id, f"Ejecutivo should only see own quotes"
        
        print(f"✓ Ejecutivo sees only own quotes ({len(quotes)} quotes)")
    
    def test_admin_sees_all_quotes(self):
        """Test Admin sees all quotes"""
        self.login_admin()
        
        # Get quotes as admin
        response = self.session.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert response.status_code == 200
        quotes = response.json()
        
        # Admin should see all quotes (no filter applied)
        print(f"✓ Admin sees all quotes ({len(quotes)} quotes)")
    
    def test_gerente_sees_department_quotes(self):
        """Test Gerente sees all quotes from their department"""
        self.login_admin()
        
        # Create a Gerente user
        user_data, email = self.create_test_user(cargo="Gerente de Ventas", departamento="Ventas")
        user_id = user_data["user_id"]
        
        # Give user read permission for cotizaciones
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"cotizaciones": "read"}
        )
        
        # Login as Gerente
        test_token, _ = self.login_test_user(email)
        
        # Get quotes as Gerente
        response = self.session.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        assert response.status_code == 200
        quotes = response.json()
        
        # Gerente should see quotes from their department
        print(f"✓ Gerente sees department quotes ({len(quotes)} quotes)")
    
    def test_director_sees_all_quotes(self):
        """Test Director sees all quotes"""
        self.login_admin()
        
        # Create a Director user
        user_data, email = self.create_test_user(cargo="Director Comercial", departamento="Dirección")
        user_id = user_data["user_id"]
        
        # Give user read permission for cotizaciones
        self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/permissions",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"cotizaciones": "read"}
        )
        
        # Login as Director
        test_token, _ = self.login_test_user(email)
        
        # Get quotes as Director
        response = self.session.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {test_token}"}
        )
        
        assert response.status_code == 200
        quotes = response.json()
        
        # Director should see all quotes (no filter)
        print(f"✓ Director sees all quotes ({len(quotes)} quotes)")


class TestAdminEndpointsProtection(TestABACFeatures):
    """Test that admin endpoints are protected"""
    
    def test_special_permissions_requires_admin(self):
        """Test PUT /api/admin/users/{user_id}/special-permissions requires admin"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Login as non-admin user
        test_token, _ = self.login_test_user(email)
        
        # Try to set special permissions as non-admin
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/special-permissions",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"special_permissions": ["integradores:create"]}
        )
        
        assert response.status_code == 403, f"Non-admin should get 403: {response.text}"
        print("✓ Special permissions endpoint requires admin")
    
    def test_almacen_endpoint_requires_admin(self):
        """Test PUT /api/admin/users/{user_id}/almacen requires admin"""
        self.login_admin()
        user_data, email = self.create_test_user()
        user_id = user_data["user_id"]
        
        # Login as non-admin user
        test_token, _ = self.login_test_user(email)
        
        # Try to assign warehouse as non-admin
        response = self.session.put(
            f"{BASE_URL}/api/admin/users/{user_id}/almacen",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"almacen_asignado": "some_warehouse_id"}
        )
        
        assert response.status_code == 403, f"Non-admin should get 403: {response.text}"
        print("✓ Almacen endpoint requires admin")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
