# ruff: noqa
"""
Test iteration 66: Projects Module Optimization
Features tested:
- PUT /api/projects/{id}/matrix/phase - Update implementation matrix phase
- POST /api/projects/{id}/bitacora - Add bitacora entry (text + execution_date)
- GET /api/projects/{id}/bitacora - Get bitacora entries  
- PUT /api/projects/{id}/priority - Update priority (Alta/Media/Normal only)
- GET /api/projects - Verify projects have implementation_matrix, attachments, bitacora
- GET /api/projects/implementers/list - List implementers
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"

# Project with implementation_matrix (from context: PRY-2026-03-001-PRI)
PROJECT_WITH_MATRIX = "prj_b50654b1c659"


class TestProjectsOptimization:
    """Test suite for Projects Module Optimization (iteration 66)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - authenticate before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    # ==================== GET PROJECTS WITH NEW FIELDS ====================
    def test_get_projects_with_new_fields(self):
        """GET /api/projects - Should return projects with implementation_matrix, attachments, bitacora"""
        response = self.session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        projects = response.json()
        assert isinstance(projects, list), "Response should be a list"
        assert len(projects) > 0, "Should have at least one project"
        
        # Check if any project has implementation_matrix
        project_with_matrix = next((p for p in projects if p.get("implementation_matrix")), None)
        assert project_with_matrix is not None, "Should have at least one project with implementation_matrix"
        
        # Verify fields in the project with matrix
        assert "implementation_matrix" in project_with_matrix
        assert "attachments" in project_with_matrix
        assert "bitacora" in project_with_matrix
        
        print(f"✓ Found {len(projects)} projects. Project with matrix: {project_with_matrix.get('project_number')}")
        print(f"  - Banks in matrix: {list(project_with_matrix['implementation_matrix'].keys())}")
        print(f"  - Attachments count: {len(project_with_matrix.get('attachments', []))}")
    
    # ==================== IMPLEMENTATION MATRIX PHASE UPDATE ====================
    def test_update_matrix_phase_success(self):
        """PUT /api/projects/{id}/matrix/phase - Should update phase to completed"""
        project_id = PROJECT_WITH_MATRIX
        
        # First get the project to see available banks
        project_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert project_response.status_code == 200
        project = project_response.json()
        
        matrix = project.get("implementation_matrix", {})
        if not matrix:
            pytest.skip("Project has no implementation_matrix")
        
        # Get first bank and product
        bank_name = list(matrix.keys())[0]
        products = matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "Servicio"
        
        # Update phase
        phase_data = {
            "bank_name": bank_name,
            "product_name": product_name,
            "phase": "Notificado",
            "completed": True
        }
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json=phase_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result["bank"] == bank_name
        assert result["product"] == product_name
        assert result["phase"] == "Notificado"
        assert result["completed"] == True
        
        # Verify persistence
        verify_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        updated_project = verify_response.json()
        updated_phase = updated_project["implementation_matrix"][bank_name][product_name].get("Notificado", {})
        assert updated_phase.get("completed") == True, "Phase should be marked as completed"
        
        print(f"✓ Phase 'Notificado' for {bank_name}/{product_name} marked as completed")
    
    def test_update_matrix_phase_invalid_phase(self):
        """PUT /api/projects/{id}/matrix/phase - Should return 400 for invalid phase"""
        project_id = PROJECT_WITH_MATRIX
        
        phase_data = {
            "bank_name": "Test Bank",
            "product_name": "Test Product",
            "phase": "InvalidPhase",
            "completed": True
        }
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json=phase_data)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "Fase inválida" in response.json().get("detail", "")
        
        print("✓ Invalid phase rejected with 400")
    
    def test_update_matrix_phase_all_phases(self):
        """PUT /api/projects/{id}/matrix/phase - Should accept all valid phases"""
        project_id = PROJECT_WITH_MATRIX
        valid_phases = ["Notificado", "Recibido", "Configurado", "Testeado", "En Producción"]
        
        # Get a bank from the matrix
        project_response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        project = project_response.json()
        matrix = project.get("implementation_matrix", {})
        
        if not matrix:
            pytest.skip("No implementation matrix")
        
        bank_name = list(matrix.keys())[0]
        products = matrix.get(bank_name, {})
        product_name = list(products.keys())[0] if products else "Servicio"
        
        for phase in valid_phases:
            phase_data = {
                "bank_name": bank_name,
                "product_name": product_name,
                "phase": phase,
                "completed": True
            }
            response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/matrix/phase", json=phase_data)
            assert response.status_code == 200, f"Phase '{phase}' should be accepted. Got {response.status_code}: {response.text}"
        
        print(f"✓ All 5 phases accepted: {valid_phases}")
    
    # ==================== BITACORA ENDPOINTS ====================
    def test_add_bitacora_entry(self):
        """POST /api/projects/{id}/bitacora - Should add entry with text and execution_date"""
        project_id = PROJECT_WITH_MATRIX
        
        entry_data = {
            "text": "TEST_Prueba de bitácora iteration 66",
            "execution_date": "2026-01-15"
        }
        
        response = self.session.post(f"{BASE_URL}/api/projects/{project_id}/bitacora", json=entry_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert "entry_id" in result, "Should return entry_id"
        assert result["text"] == entry_data["text"]
        assert result["execution_date"] == entry_data["execution_date"]
        assert "created_by" in result
        assert "created_by_name" in result
        assert "created_at" in result
        
        print(f"✓ Bitacora entry added: {result['entry_id']}")
    
    def test_get_bitacora(self):
        """GET /api/projects/{id}/bitacora - Should return bitacora entries"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}/bitacora")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        bitacora = response.json()
        assert isinstance(bitacora, list), "Should return a list"
        
        # Find our test entry
        test_entry = next((e for e in bitacora if "TEST_" in e.get("text", "")), None)
        if test_entry:
            assert "entry_id" in test_entry
            assert "text" in test_entry
            assert "execution_date" in test_entry
            print(f"✓ Bitacora has {len(bitacora)} entries. Found test entry.")
        else:
            print(f"✓ Bitacora has {len(bitacora)} entries")
    
    def test_bitacora_not_found_project(self):
        """GET /api/projects/{id}/bitacora - Should return 404 for non-existent project"""
        response = self.session.get(f"{BASE_URL}/api/projects/nonexistent_id/bitacora")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Bitacora for non-existent project returns 404")
    
    # ==================== PRIORITY UPDATE ====================
    def test_update_priority_alta(self):
        """PUT /api/projects/{id}/priority - Should accept 'Alta'"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/priority", json={"priority": "Alta"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify
        verify = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert verify.json().get("priority") == "Alta"
        print("✓ Priority 'Alta' accepted and persisted")
    
    def test_update_priority_media(self):
        """PUT /api/projects/{id}/priority - Should accept 'Media'"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/priority", json={"priority": "Media"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Priority 'Media' accepted")
    
    def test_update_priority_normal(self):
        """PUT /api/projects/{id}/priority - Should accept 'Normal'"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/priority", json={"priority": "Normal"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Priority 'Normal' accepted")
    
    def test_update_priority_invalid_baja(self):
        """PUT /api/projects/{id}/priority - Should reject 'Baja' (not valid)"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/priority", json={"priority": "Baja"})
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "Prioridad inválida" in response.json().get("detail", "")
        print("✓ Priority 'Baja' correctly rejected")
    
    def test_update_priority_invalid_urgente(self):
        """PUT /api/projects/{id}/priority - Should reject 'Urgente' (not valid)"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.put(f"{BASE_URL}/api/projects/{project_id}/priority", json={"priority": "Urgente"})
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Priority 'Urgente' correctly rejected")
    
    # ==================== IMPLEMENTERS LIST ====================
    def test_get_implementers_list(self):
        """GET /api/projects/implementers/list - Should return list of implementers"""
        response = self.session.get(f"{BASE_URL}/api/projects/implementers/list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        implementers = response.json()
        assert isinstance(implementers, list), "Response should be a list"
        
        if len(implementers) > 0:
            impl = implementers[0]
            assert "user_id" in impl
            print(f"✓ Found {len(implementers)} implementers")
        else:
            print("✓ Implementers list returned (empty - may fallback to all users)")
    
    # ==================== PROJECT DETAIL WITH NEW FIELDS ====================
    def test_get_project_detail_with_new_fields(self):
        """GET /api/projects/{id} - Should return project with implementation_matrix, attachments, bitacora"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        project = response.json()
        
        # Check implementation_matrix structure
        assert "implementation_matrix" in project, "Should have implementation_matrix"
        matrix = project["implementation_matrix"]
        assert isinstance(matrix, dict), "implementation_matrix should be a dict"
        assert len(matrix) > 0, "implementation_matrix should have banks"
        
        # Check attachments (inherited from quote)
        assert "attachments" in project, "Should have attachments"
        attachments = project["attachments"]
        assert isinstance(attachments, list), "attachments should be a list"
        if len(attachments) > 0:
            att = attachments[0]
            assert "attachment_id" in att
            assert "filename" in att
            assert "url" in att
            assert "category" in att
            assert att.get("inherited_from") == "cotización", "Should be inherited from cotización"
        
        # Check bitacora
        assert "bitacora" in project, "Should have bitacora"
        assert isinstance(project["bitacora"], list), "bitacora should be a list"
        
        # Check technical header fields
        assert "pinpad_model" in project
        assert "sponsor_bank_name" in project
        
        print(f"✓ Project {project['project_number']} has:")
        print(f"  - {len(matrix)} banks in matrix: {list(matrix.keys())[:3]}...")
        print(f"  - {len(attachments)} attachments (inherited)")
        print(f"  - {len(project['bitacora'])} bitacora entries")
        print(f"  - Pinpad: {project.get('pinpad_model') or 'N/A'}, Sponsor: {project.get('sponsor_bank_name') or 'N/A'}")


class TestQuoteTriggerCreatesProjectWithMatrix:
    """Test that quote trigger creates project with implementation_matrix and inherited attachments"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_project_has_implementation_matrix_structure(self):
        """Verify project has correct implementation_matrix structure (Banks × Products)"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        assert response.status_code == 200
        
        project = response.json()
        matrix = project.get("implementation_matrix", {})
        
        # Verify structure: { bankName: { productName: { phase: {completed, updated_at, updated_by} } } }
        for bank_name, products in matrix.items():
            assert isinstance(products, dict), f"Bank '{bank_name}' products should be a dict"
            for product_name, phases in products.items():
                assert isinstance(phases, dict), f"Product '{product_name}' phases should be a dict"
        
        print("✓ Implementation matrix structure verified")
        print(f"  Banks: {list(matrix.keys())}")
    
    def test_project_inherits_attachments_from_quote(self):
        """Verify project inherits attachments from source quote"""
        project_id = PROJECT_WITH_MATRIX
        
        response = self.session.get(f"{BASE_URL}/api/projects/{project_id}")
        project = response.json()
        
        attachments = project.get("attachments", [])
        if len(attachments) == 0:
            pytest.skip("No attachments to verify")
        
        for att in attachments:
            assert att.get("inherited_from") == "cotización", "Attachment should be inherited from cotización"
            assert "attachment_id" in att
            assert "filename" in att
            assert "url" in att
            assert "category" in att
        
        print(f"✓ {len(attachments)} attachments inherited from quote")
        for att in attachments:
            print(f"  - {att['filename']} ({att['category']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
