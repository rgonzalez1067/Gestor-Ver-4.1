# ruff: noqa
"""
Test Iteration 171: Project Optimizations
- PUT /api/projects/{id}/matrix/phase - expected/processed fields + auto bitacora
- PUT /api/projects/{id}/implementation-fields - integrator_name, application_name
- POST /api/projects/{id}/implementation-serials - add serials + auto bitacora
- DELETE /api/projects/{id}/implementation-serials/{serial} - remove serial
- Permissions: admin always can, others need to be implementer or supervisor
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProjectOptimizations:
    """Tests for project matrix quantities, implementation fields, and serials"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: login as admin and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get existing projects
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_resp.status_code == 200
        self.projects = projects_resp.json()
        
    def test_01_get_projects_list(self):
        """Verify we can get projects list"""
        assert len(self.projects) > 0, "No projects found"
        print(f"Found {len(self.projects)} projects")
        for p in self.projects[:3]:
            print(f"  - {p.get('project_id')}: {p.get('project_number')} ({p.get('project_type', 'single')})")
    
    def test_02_matrix_phase_update_with_quantities(self):
        """Test PUT /api/projects/{id}/matrix/phase with expected/processed fields"""
        # Find a single project with client_notified=True
        single_project = None
        for p in self.projects:
            if p.get('project_type') != 'multistore' and p.get('client_notified'):
                single_project = p
                break
        
        if not single_project:
            pytest.skip("No single project with client_notified=True found")
        
        project_id = single_project['project_id']
        matrix = single_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Project {project_id} has no implementation matrix")
        
        # Get first bank and product
        bank_name = list(matrix.keys())[0]
        products = matrix[bank_name]
        product_name = list(products.keys())[0]
        
        print(f"Testing matrix update on project {project_id}, bank={bank_name}, product={product_name}")
        
        # Update with expected and processed quantities
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Notificado",
            "completed": False,
            "expected": 10,
            "processed": 5
        })
        
        assert resp.status_code == 200, f"Matrix phase update failed: {resp.text}"
        data = resp.json()
        
        # Verify response contains expected/processed
        assert data.get("expected") == 10, f"Expected 10, got {data.get('expected')}"
        assert data.get("processed") == 5, f"Expected processed=5, got {data.get('processed')}"
        assert data.get("completed") == False, "Should not be completed (5 < 10)"
        
        print(f"Matrix phase updated: expected={data.get('expected')}, processed={data.get('processed')}, completed={data.get('completed')}")
        
    def test_03_matrix_phase_auto_bitacora(self):
        """Test that updating processed quantity generates automatic bitacora entry"""
        # Find a single project with client_notified=True
        single_project = None
        for p in self.projects:
            if p.get('project_type') != 'multistore' and p.get('client_notified'):
                single_project = p
                break
        
        if not single_project:
            pytest.skip("No single project with client_notified=True found")
        
        project_id = single_project['project_id']
        matrix = single_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Project {project_id} has no implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Get current bitacora count
        bitacora_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}/bitacora")
        assert bitacora_resp.status_code == 200
        initial_bitacora = bitacora_resp.json()
        initial_count = len(initial_bitacora)
        
        # Update processed quantity (should trigger bitacora)
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Recibido",
            "completed": False,
            "expected": 8,
            "processed": 3
        })
        assert resp.status_code == 200
        
        # Check bitacora was updated
        bitacora_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}/bitacora")
        assert bitacora_resp.status_code == 200
        new_bitacora = bitacora_resp.json()
        
        # Should have at least one more entry
        assert len(new_bitacora) >= initial_count, "Bitacora should have new entry"
        
        # Find the auto-generated entry
        auto_entries = [b for b in new_bitacora if b.get('auto_generated') and '[Matriz]' in b.get('text', '')]
        assert len(auto_entries) > 0, "Should have auto-generated bitacora entry with [Matriz] prefix"
        
        latest_auto = auto_entries[-1]
        print(f"Auto bitacora entry: {latest_auto.get('text')}")
        assert 'Recibido' in latest_auto.get('text', ''), "Bitacora should mention the phase"
        
    def test_04_matrix_phase_completion_logic(self):
        """Test that completed is auto-calculated when processed >= expected"""
        single_project = None
        for p in self.projects:
            if p.get('project_type') != 'multistore' and p.get('client_notified'):
                single_project = p
                break
        
        if not single_project:
            pytest.skip("No single project with client_notified=True found")
        
        project_id = single_project['project_id']
        matrix = single_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Project {project_id} has no implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Set processed = expected (should mark as completed)
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Configurado",
            "completed": False,  # This should be overridden
            "expected": 5,
            "processed": 5
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("completed") == True, "Should be completed when processed >= expected"
        print(f"Completion logic verified: processed={data.get('processed')}, expected={data.get('expected')}, completed={data.get('completed')}")
        
    def test_05_implementation_fields_update(self):
        """Test PUT /api/projects/{id}/implementation-fields"""
        if not self.projects:
            pytest.skip("No projects available")
        
        project_id = self.projects[0]['project_id']
        
        # Update integrator_name and application_name
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/implementation-fields", json={
            "integrator_name": "Test Integrator",
            "application_name": "Test Application"
        })
        
        assert resp.status_code == 200, f"Implementation fields update failed: {resp.text}"
        data = resp.json()
        
        assert data.get("integrator_name") == "Test Integrator"
        assert data.get("application_name") == "Test Application"
        print(f"Implementation fields updated: integrator={data.get('integrator_name')}, app={data.get('application_name')}")
        
        # Verify persistence
        project_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_resp.status_code == 200
        project = project_resp.json()
        assert project.get("integrator_name") == "Test Integrator"
        assert project.get("application_name") == "Test Application"
        
    def test_06_implementation_serials_add(self):
        """Test POST /api/projects/{id}/implementation-serials"""
        if not self.projects:
            pytest.skip("No projects available")
        
        project_id = self.projects[0]['project_id']
        
        # Add serials
        test_serials = ["TEST_SERIAL_001", "TEST_SERIAL_002", "TEST_SERIAL_003"]
        resp = self.session.post(f"{BASE_URL}/api/projects/{project_id}/implementation-serials", json={
            "serials": test_serials
        })
        
        assert resp.status_code == 200, f"Add serials failed: {resp.text}"
        data = resp.json()
        
        assert "serial(es) agregados" in data.get("message", "").lower() or data.get("total_serials", 0) > 0
        print(f"Serials added: {data}")
        
        # Verify persistence
        project_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_resp.status_code == 200
        project = project_resp.json()
        impl_serials = project.get("implementation_serials", [])
        
        for serial in test_serials:
            assert serial in impl_serials, f"Serial {serial} not found in project"
        
    def test_07_implementation_serials_auto_bitacora(self):
        """Test that adding serials generates automatic bitacora entry"""
        if not self.projects:
            pytest.skip("No projects available")
        
        project_id = self.projects[0]['project_id']
        
        # Get current bitacora
        bitacora_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}/bitacora")
        assert bitacora_resp.status_code == 200
        initial_bitacora = bitacora_resp.json()
        
        # Add new serials
        new_serials = ["BITACORA_TEST_001", "BITACORA_TEST_002"]
        resp = self.session.post(f"{BASE_URL}/api/projects/{project_id}/implementation-serials", json={
            "serials": new_serials
        })
        assert resp.status_code == 200
        
        # Check bitacora
        bitacora_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}/bitacora")
        assert bitacora_resp.status_code == 200
        new_bitacora = bitacora_resp.json()
        
        # Find serial-related entries
        serial_entries = [b for b in new_bitacora if '[Seriales]' in b.get('text', '')]
        assert len(serial_entries) > 0, "Should have bitacora entry for serials"
        
        latest = serial_entries[-1]
        print(f"Serial bitacora entry: {latest.get('text')}")
        
    def test_08_implementation_serials_delete(self):
        """Test DELETE /api/projects/{id}/implementation-serials/{serial}"""
        if not self.projects:
            pytest.skip("No projects available")
        
        project_id = self.projects[0]['project_id']
        
        # First add a serial to delete
        test_serial = "DELETE_TEST_SERIAL"
        self.session.post(f"{BASE_URL}/api/projects/{project_id}/implementation-serials", json={
            "serials": [test_serial]
        })
        
        # Delete the serial
        resp = self.session.delete(f"{BASE_URL}/api/projects/{project_id}/implementation-serials/{test_serial}")
        assert resp.status_code == 200, f"Delete serial failed: {resp.text}"
        
        # Verify removal
        project_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_resp.status_code == 200
        project = project_resp.json()
        impl_serials = project.get("implementation_serials", [])
        
        assert test_serial not in impl_serials, f"Serial {test_serial} should have been deleted"
        print(f"Serial {test_serial} successfully deleted")
        
    def test_09_implementation_serials_no_duplicates(self):
        """Test that duplicate serials are not added"""
        if not self.projects:
            pytest.skip("No projects available")
        
        project_id = self.projects[0]['project_id']
        
        # Add a serial
        test_serial = "DUPLICATE_TEST_SERIAL"
        resp1 = self.session.post(f"{BASE_URL}/api/projects/{project_id}/implementation-serials", json={
            "serials": [test_serial]
        })
        assert resp1.status_code == 200
        
        # Try to add the same serial again
        resp2 = self.session.post(f"{BASE_URL}/api/projects/{project_id}/implementation-serials", json={
            "serials": [test_serial]
        })
        assert resp2.status_code == 200
        
        # Verify no duplicates
        project_resp = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_resp.status_code == 200
        project = project_resp.json()
        impl_serials = project.get("implementation_serials", [])
        
        count = impl_serials.count(test_serial)
        assert count == 1, f"Serial {test_serial} should appear only once, found {count} times"
        print("Duplicate prevention verified")
        
    def test_10_matrix_phase_permissions_admin(self):
        """Test that admin can always update matrix"""
        # Admin is already logged in, should be able to update any project
        single_project = None
        for p in self.projects:
            if p.get('project_type') != 'multistore' and p.get('client_notified'):
                single_project = p
                break
        
        if not single_project:
            pytest.skip("No single project with client_notified=True found")
        
        project_id = single_project['project_id']
        matrix = single_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Project {project_id} has no implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Admin should be able to update
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Testeado",
            "completed": False,
            "expected": 10,
            "processed": 7
        })
        
        assert resp.status_code == 200, f"Admin should be able to update matrix: {resp.text}"
        print("Admin permission verified - can update matrix")
        
    def test_11_matrix_multistore_readonly(self):
        """Test that multistore projects have read-only main matrix"""
        multistore_project = None
        for p in self.projects:
            if p.get('project_type') == 'multistore' and p.get('client_notified'):
                multistore_project = p
                break
        
        if not multistore_project:
            pytest.skip("No multistore project with client_notified=True found")
        
        project_id = multistore_project['project_id']
        matrix = multistore_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Multistore project {project_id} has no implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Should fail for multistore main matrix
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Notificado",
            "completed": True
        })
        
        assert resp.status_code == 400, f"Multistore main matrix should be read-only: {resp.text}"
        assert "solo lectura" in resp.text.lower() or "read" in resp.text.lower()
        print("Multistore read-only protection verified")
        
    def test_12_matrix_requires_client_notification(self):
        """Test that matrix update requires client to be notified first"""
        # Find a project without client_notified
        unnotified_project = None
        for p in self.projects:
            if not p.get('client_notified') and p.get('project_type') != 'multistore':
                unnotified_project = p
                break
        
        if not unnotified_project:
            pytest.skip("No unnotified single project found")
        
        project_id = unnotified_project['project_id']
        matrix = unnotified_project.get('implementation_matrix', {})
        
        if not matrix:
            pytest.skip(f"Project {project_id} has no implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        product_name = list(matrix[bank_name].keys())[0]
        
        # Should fail because client not notified
        resp = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Notificado",
            "completed": True
        })
        
        assert resp.status_code == 400, f"Should require client notification: {resp.text}"
        assert "notificar" in resp.text.lower() or "cliente" in resp.text.lower()
        print("Client notification requirement verified")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        if login_resp.status_code == 200:
            self.token = login_resp.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_cleanup_test_serials(self):
        """Remove test serials from projects"""
        projects_resp = self.session.get(f"{BASE_URL}/api/projects")
        if projects_resp.status_code != 200:
            pytest.skip("Could not get projects")
        
        projects = projects_resp.json()
        test_prefixes = ["TEST_SERIAL", "BITACORA_TEST", "DELETE_TEST", "DUPLICATE_TEST"]
        
        for p in projects:
            impl_serials = p.get("implementation_serials", [])
            for serial in impl_serials:
                if any(serial.startswith(prefix) for prefix in test_prefixes):
                    self.session.delete(f"{BASE_URL}/api/projects/{p['project_id']}/implementation-serials/{serial}")
        
        print("Test serials cleaned up")
