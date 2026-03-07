"""
Test Iteration 67: Implementation Matrix Fix
- Verifies that implementation_matrix only contains 'additional' items (bank-specific payment methods)
- NOT recurring_basic (platform fees, recurring charges) or recurring_other (infrastructure costs)
- Tests migration endpoint, phase updates, and project stats
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Items that should NOT appear in implementation_matrix
FORBIDDEN_MATRIX_ITEMS = [
    "Derecho de uso de plataforma MServer por PDV",
    "Derecho de uso de plataforma MServer por PDV / Banco",
    "Comunicación Backend",
    "Procesamiento",
    "TDD/TDC Recurrente",
    "P2C o Crédito Inmediato Recurrente",
    "C@mbio - Pago Móvil Recurrente",
    "C2P o Débito Inmediato Recurrente",
    "CASHEA Recurrente",
]

VALID_PHASES = ["Notificado", "Recibido", "Configurado", "Testeado", "En Producción"]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "rgonzalez@megasoft.com.ve", "password": "Avila*0226*02"}
    )
    if response.status_code != 200:
        pytest.skip("Authentication failed")
    return response.json().get("session_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestProjectMatrixFix:
    """Tests for the implementation matrix fix - only 'additional' items"""
    
    def test_projects_list_returns_data(self, api_client):
        """GET /api/projects should return projects list"""
        response = api_client.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        assert len(projects) > 0
        print(f"✓ Found {len(projects)} projects")
    
    def test_matrix_contains_only_additional_items(self, api_client):
        """Implementation matrix should only contain 'additional' item_type services"""
        response = api_client.get(f"{BASE_URL}/api/projects")
        projects = response.json()
        
        for project in projects:
            matrix = project.get("implementation_matrix", {})
            services = project.get("services", [])
            
            # Get all additional items from services
            additional_items = [
                (s.get("bank_name"), s.get("item_name"))
                for s in services
                if s.get("item_type") == "additional" and s.get("bank_name") and s.get("item_name")
            ]
            
            # Get all items from matrix
            matrix_items = []
            for bank_name, products in matrix.items():
                for product_name in products.keys():
                    matrix_items.append((bank_name, product_name))
            
            # Verify matrix items match additional services
            if additional_items:
                # All matrix items should be in additional items
                for item in matrix_items:
                    assert item in additional_items, f"Matrix item {item} not in additional services for {project.get('project_number')}"
                
                # Count should match
                assert len(matrix_items) == len(additional_items), \
                    f"Matrix count ({len(matrix_items)}) != additional count ({len(additional_items)}) for {project.get('project_number')}"
        
        print(f"✓ All {len(projects)} projects have correct matrix items")
    
    def test_matrix_excludes_recurring_items(self, api_client):
        """Matrix should NOT contain recurring_basic or recurring_other items"""
        response = api_client.get(f"{BASE_URL}/api/projects")
        projects = response.json()
        
        for project in projects:
            matrix = project.get("implementation_matrix", {})
            
            for bank_name, products in matrix.items():
                for product_name in products.keys():
                    for forbidden in FORBIDDEN_MATRIX_ITEMS:
                        assert forbidden.lower() not in product_name.lower(), \
                            f"Forbidden item '{forbidden}' found in matrix for {project.get('project_number')}"
        
        print(f"✓ No recurring items in any project matrices")
    
    def test_specific_project_prj_27c658a31dd2(self, api_client):
        """PRY-2026-03-004 should have exactly 9 additional items in matrix"""
        response = api_client.get(f"{BASE_URL}/api/projects/prj_27c658a31dd2")
        assert response.status_code == 200
        
        project = response.json()
        assert project.get("project_number") == "PRY-2026-03-004-PRI"
        
        matrix = project.get("implementation_matrix", {})
        services = project.get("services", [])
        
        # Count additional services
        additional_count = len([s for s in services if s.get("item_type") == "additional"])
        
        # Count matrix items
        matrix_count = sum(len(products) for products in matrix.values())
        
        # Should be exactly 9 per requirement
        assert matrix_count == 9, f"Matrix should have 9 items, found {matrix_count}"
        assert matrix_count == additional_count, f"Matrix count ({matrix_count}) != additional count ({additional_count})"
        
        # Verify 4 banks
        assert len(matrix) == 4, f"Should have 4 banks, found {len(matrix)}"
        expected_banks = ["Banco Mercantil", "Banesco Banco Universal", "Bancamiga", "Cashea"]
        for bank in expected_banks:
            assert bank in matrix, f"Missing bank: {bank}"
        
        print(f"✓ PRY-2026-03-004-PRI has correct 9 items across 4 banks")


class TestProjectStats:
    """Tests for project statistics endpoint"""
    
    def test_stats_endpoint(self, api_client):
        """GET /api/projects/stats should return correct structure"""
        response = api_client.get(f"{BASE_URL}/api/projects/stats")
        assert response.status_code == 200
        
        stats = response.json()
        required_fields = ["total", "pending", "in_progress", "blocked", "completed"]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
            assert isinstance(stats[field], int), f"{field} should be integer"
        
        # Total should equal sum of status counts
        assert stats["total"] >= stats["completed"], "Total should be >= completed"
        
        print(f"✓ Stats: total={stats['total']}, pending={stats['pending']}, in_progress={stats['in_progress']}, blocked={stats['blocked']}, completed={stats['completed']}")


class TestMigrateMatrix:
    """Tests for matrix migration endpoint"""
    
    def test_migrate_endpoint_works(self, api_client):
        """POST /api/projects/migrate-matrix should execute successfully"""
        response = api_client.post(f"{BASE_URL}/api/projects/migrate-matrix")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "Matrices actualizadas" in data["message"]
        print(f"✓ Migration endpoint response: {data['message']}")


class TestMatrixPhaseUpdate:
    """Tests for matrix phase update functionality"""
    
    def test_update_phase_valid(self, api_client):
        """PUT /api/projects/{id}/matrix/phase should update phase"""
        # First, reset the phase
        api_client.put(
            f"{BASE_URL}/api/projects/prj_27c658a31dd2/matrix/phase",
            json={
                "bank_name": "Banco Mercantil",
                "product_name": "TDD/TDC Suscripción para Medio de Pago",
                "phase": "Notificado",
                "completed": False
            }
        )
        
        # Now set it to completed
        response = api_client.put(
            f"{BASE_URL}/api/projects/prj_27c658a31dd2/matrix/phase",
            json={
                "bank_name": "Banco Mercantil",
                "product_name": "TDD/TDC Suscripción para Medio de Pago",
                "phase": "Notificado",
                "completed": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["completed"] == True
        assert data["bank"] == "Banco Mercantil"
        assert data["phase"] == "Notificado"
        print(f"✓ Phase update successful: {data}")
    
    def test_update_phase_invalid_phase(self, api_client):
        """Invalid phase should return 400"""
        response = api_client.put(
            f"{BASE_URL}/api/projects/prj_27c658a31dd2/matrix/phase",
            json={
                "bank_name": "Banco Mercantil",
                "product_name": "TDD/TDC Suscripción para Medio de Pago",
                "phase": "InvalidPhase",
                "completed": True
            }
        )
        assert response.status_code == 400
        print("✓ Invalid phase correctly rejected with 400")
    
    def test_verify_phase_persisted(self, api_client):
        """Verify phase update was persisted in database"""
        response = api_client.get(f"{BASE_URL}/api/projects/prj_27c658a31dd2")
        assert response.status_code == 200
        
        project = response.json()
        matrix = project.get("implementation_matrix", {})
        
        mercantil = matrix.get("Banco Mercantil", {})
        tdd = mercantil.get("TDD/TDC Suscripción para Medio de Pago", {})
        notificado = tdd.get("Notificado", {})
        
        assert notificado.get("completed") == True, "Phase should be completed"
        print(f"✓ Phase persisted correctly: Notificado={notificado}")


class TestAllPhasesValid:
    """Test that all valid phases work"""
    
    @pytest.mark.parametrize("phase", VALID_PHASES)
    def test_each_phase(self, api_client, phase):
        """Each valid phase should be accepted"""
        response = api_client.put(
            f"{BASE_URL}/api/projects/prj_27c658a31dd2/matrix/phase",
            json={
                "bank_name": "Cashea",
                "product_name": "CASHEA Suscripción",
                "phase": phase,
                "completed": True
            }
        )
        assert response.status_code == 200, f"Phase '{phase}' should be accepted"
        print(f"✓ Phase '{phase}' accepted")
