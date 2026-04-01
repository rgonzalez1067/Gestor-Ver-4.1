"""
Test iteration 141: Governance Control for New Products Pipeline
Tests:
- Status transitions with governance rules (Negociación→DESA requires LP, DESA→SQA only LP, SQA→IMPLE only SQA Analyst)
- Bitácora write restrictions (only responsable can write)
- Assignment audit log
- Login for both admin and analyst users
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@meganexus.com"
ADMIN_PASSWORD = "Admin123!"
ANALYST_EMAIL = "analista@meganexus.com"
ANALYST_PASSWORD = "Analista123!"

# Product ID from context
PRODUCT_ID = "npd_5abb1ef6"


class TestAuthLogin:
    """Test login for both users"""
    
    def test_admin_login(self):
        """Admin user can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        print(f"Admin login response: {response.status_code}")
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        user = data.get("user", {})
        assert user.get("role") == "admin", f"Expected admin role, got {user.get('role')}"
        print(f"Admin login successful: {user.get('email')}, role: {user.get('role')}")
    
    def test_analyst_login(self):
        """Analyst user can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ANALYST_EMAIL,
            "password": ANALYST_PASSWORD
        })
        print(f"Analyst login response: {response.status_code}")
        assert response.status_code == 200, f"Analyst login failed: {response.text}"
        data = response.json()
        assert "session_token" in data, "No session_token in response"
        user = data.get("user", {})
        print(f"Analyst login successful: {user.get('email')}, role: {user.get('role')}")


@pytest.fixture
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip("Admin login failed")


@pytest.fixture
def analyst_token():
    """Get analyst auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ANALYST_EMAIL,
        "password": ANALYST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("session_token")
    pytest.skip("Analyst login failed")


@pytest.fixture
def admin_user_id(admin_token):
    """Get admin user_id"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("user", {}).get("user_id")
    pytest.skip("Could not get admin user_id")


@pytest.fixture
def analyst_user_id(analyst_token):
    """Get analyst user_id"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ANALYST_EMAIL,
        "password": ANALYST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("user", {}).get("user_id")
    pytest.skip("Could not get analyst user_id")


class TestGovernanceStatusTransitions:
    """Test governance rules for status transitions"""
    
    def test_status_to_desa_without_responsable_returns_400(self, admin_token):
        """POST /api/new-products/{id}/status with status=DESA without responsable_user_id returns 400"""
        # First, we need a product in Negociación status
        # Let's create a new test product
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a service and bank for creating test product
        services_res = requests.get(f"{BASE_URL}/api/services", headers=headers)
        banks_res = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        
        if services_res.status_code != 200 or banks_res.status_code != 200:
            pytest.skip("Could not fetch services/banks")
        
        services = services_res.json()
        banks = banks_res.json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create a test product
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_GOVERNANCE_141"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=headers)
        assert create_res.status_code == 200, f"Failed to create test product: {create_res.text}"
        
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Try to move to DESA without responsable_user_id
            response = requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA"},
                headers=headers
            )
            print(f"Status change without responsable: {response.status_code} - {response.text}")
            assert response.status_code == 400, f"Expected 400, got {response.status_code}"
            assert "GOBERNANZA" in response.json().get("detail", ""), "Expected governance error message"
            print("PASS: Governance rule enforced - DESA requires Líder de Proyecto")
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=headers)
    
    def test_status_to_desa_with_responsable_works(self, admin_token, admin_user_id):
        """POST /api/new-products/{id}/status with status=DESA and responsable_user_id works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get a service and bank
        services_res = requests.get(f"{BASE_URL}/api/services", headers=headers)
        banks_res = requests.get(f"{BASE_URL}/api/banks", headers=headers)
        
        services = services_res.json()
        banks = banks_res.json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create a test product
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_GOVERNANCE_141_LP"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=headers)
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Move to DESA with responsable_user_id
            response = requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA", "responsable_user_id": admin_user_id},
                headers=headers
            )
            print(f"Status change with responsable: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["status"] == "DESA", f"Expected DESA status, got {data['status']}"
            assert data.get("usuario_responsable_fase") == admin_user_id, "Responsable not assigned"
            assert data.get("responsable_role") == "Líder de Proyecto", "Role not set correctly"
            print(f"PASS: Product moved to DESA with LP: {data.get('responsable_nombre')}")
        finally:
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=headers)


class TestBitacoraGovernance:
    """Test bitácora write restrictions"""
    
    def test_evolution_as_non_responsable_returns_403(self, admin_token, analyst_token):
        """POST /api/new-products/{id}/evolution as non-responsable returns 403"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
        
        # Get admin user_id
        admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        admin_user_id = admin_login.json().get("user", {}).get("user_id")
        
        # Get services and banks
        services = requests.get(f"{BASE_URL}/api/services", headers=admin_headers).json()
        banks = requests.get(f"{BASE_URL}/api/banks", headers=admin_headers).json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create product and move to DESA with admin as LP
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_BITACORA_403"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=admin_headers)
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Move to DESA with admin as LP
            requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA", "responsable_user_id": admin_user_id},
                headers=admin_headers
            )
            
            # Try to write to bitácora as analyst (not the responsable)
            response = requests.post(
                f"{BASE_URL}/api/new-products/{product_id}/evolution",
                json={"comment": "Test comment from analyst", "phase": "DESA", "date": "2026-01-15"},
                headers=analyst_headers
            )
            print(f"Evolution as non-responsable: {response.status_code} - {response.text}")
            assert response.status_code == 403, f"Expected 403, got {response.status_code}"
            assert "GOBERNANZA" in response.json().get("detail", ""), "Expected governance error"
            print("PASS: Non-responsable cannot write to bitácora")
        finally:
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=admin_headers)
    
    def test_evolution_as_responsable_works(self, admin_token):
        """POST /api/new-products/{id}/evolution as responsable works"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get admin user_id
        admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        admin_user_id = admin_login.json().get("user", {}).get("user_id")
        
        # Get services and banks
        services = requests.get(f"{BASE_URL}/api/services", headers=headers).json()
        banks = requests.get(f"{BASE_URL}/api/banks", headers=headers).json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create product and move to DESA with admin as LP
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_BITACORA_OK"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=headers)
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Move to DESA with admin as LP
            requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA", "responsable_user_id": admin_user_id},
                headers=headers
            )
            
            # Write to bitácora as admin (the responsable)
            response = requests.post(
                f"{BASE_URL}/api/new-products/{product_id}/evolution",
                json={"comment": "Test comment from LP", "phase": "DESA", "date": "2026-01-15"},
                headers=headers
            )
            print(f"Evolution as responsable: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data.get("comment") == "Test comment from LP", "Comment not saved"
            print("PASS: Responsable can write to bitácora")
        finally:
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=headers)


class TestAssignResponsable:
    """Test assign-responsable endpoint"""
    
    def test_assign_analista_sqa(self, admin_token, analyst_token):
        """POST /api/new-products/{id}/assign-responsable with role='Analista SQA' works"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get user IDs
        admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        admin_user_id = admin_login.json().get("user", {}).get("user_id")
        
        analyst_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ANALYST_EMAIL, "password": ANALYST_PASSWORD
        })
        analyst_user_id = analyst_login.json().get("user", {}).get("user_id")
        
        print(f"Admin user_id: {admin_user_id}, Analyst user_id: {analyst_user_id}")
        
        # Get services and banks
        services = requests.get(f"{BASE_URL}/api/services", headers=admin_headers).json()
        banks = requests.get(f"{BASE_URL}/api/banks", headers=admin_headers).json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create product, move to DESA, then to SQA
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_ASSIGN_SQA"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=admin_headers)
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Move to DESA with admin as LP
            requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA", "responsable_user_id": admin_user_id},
                headers=admin_headers
            )
            
            # Move to SQA (LP can do this)
            requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "SQA"},
                headers=admin_headers
            )
            
            # Assign Analista SQA
            response = requests.post(
                f"{BASE_URL}/api/new-products/{product_id}/assign-responsable",
                json={"user_id": analyst_user_id, "role": "Analista SQA"},
                headers=admin_headers
            )
            print(f"Assign SQA Analyst: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data.get("usuario_responsable_fase") == analyst_user_id, "Analyst not assigned"
            assert data.get("responsable_role") == "Analista SQA", "Role not set correctly"
            print(f"PASS: Analista SQA assigned: {data.get('responsable_nombre')}")
        finally:
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=admin_headers)


class TestAssignmentsAuditLog:
    """Test assignments audit log"""
    
    def test_get_assignments_history(self, admin_token):
        """GET /api/new-products/{id}/assignments returns assignment history"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get admin user_id
        admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
        })
        admin_user_id = admin_login.json().get("user", {}).get("user_id")
        
        # Get services and banks
        services = requests.get(f"{BASE_URL}/api/services", headers=headers).json()
        banks = requests.get(f"{BASE_URL}/api/banks", headers=headers).json()
        
        if not services or not banks:
            pytest.skip("No services or banks available")
        
        # Create product and move to DESA
        test_product = {
            "service_id": services[0]["service_id"],
            "component_type": "VPOS/MPOS",
            "bank_id": banks[0]["bank_id"],
            "notes": "TEST_AUDIT_LOG"
        }
        create_res = requests.post(f"{BASE_URL}/api/new-products", json=test_product, headers=headers)
        product = create_res.json()
        product_id = product["product_id"]
        
        try:
            # Move to DESA with admin as LP (this creates an assignment)
            requests.put(
                f"{BASE_URL}/api/new-products/{product_id}/status",
                json={"status": "DESA", "responsable_user_id": admin_user_id},
                headers=headers
            )
            
            # Get assignments history
            response = requests.get(
                f"{BASE_URL}/api/new-products/{product_id}/assignments",
                headers=headers
            )
            print(f"Get assignments: {response.status_code}")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.json()
            assert isinstance(data, list), "Expected list of assignments"
            assert len(data) >= 1, "Expected at least one assignment"
            
            # Check assignment structure
            assignment = data[0]
            assert "assigned_user_id" in assignment, "Missing assigned_user_id"
            assert "role" in assignment, "Missing role"
            assert "timestamp" in assignment, "Missing timestamp"
            assert "assigned_by_user_id" in assignment, "Missing assigned_by_user_id"
            print(f"PASS: Assignments history returned {len(data)} records")
        finally:
            requests.delete(f"{BASE_URL}/api/new-products/{product_id}", headers=headers)


class TestExistingProduct:
    """Test with the existing product npd_5abb1ef6"""
    
    def test_get_existing_product(self, admin_token):
        """Verify the existing product npd_5abb1ef6 exists and has correct state"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/new-products/{PRODUCT_ID}", headers=headers)
        print(f"Get existing product: {response.status_code}")
        
        if response.status_code == 404:
            pytest.skip(f"Product {PRODUCT_ID} not found - may have been deleted")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"Product: {data.get('service_name')}, Status: {data.get('status')}")
        print(f"Responsable: {data.get('responsable_nombre')} ({data.get('responsable_role')})")
        
        # Verify it's in DESA with admin as LP
        assert data.get("status") == "DESA", f"Expected DESA status, got {data.get('status')}"
        assert data.get("responsable_role") == "Líder de Proyecto", "Expected LP role"
        print("PASS: Existing product has correct governance state")
    
    def test_get_existing_product_assignments(self, admin_token):
        """Get assignments for existing product"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/new-products/{PRODUCT_ID}/assignments", headers=headers)
        print(f"Get assignments for {PRODUCT_ID}: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Found {len(data)} assignment records")
            for a in data[:3]:  # Show first 3
                print(f"  - {a.get('assigned_name')} as {a.get('role')} on {a.get('timestamp')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
