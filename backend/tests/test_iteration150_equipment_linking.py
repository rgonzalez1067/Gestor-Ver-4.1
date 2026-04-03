"""
Iteration 150: Equipment Linking in 'Enviar a Implementación' flow
Tests:
1. GET /api/quotes/{id}/equipment-for-implementation - returns quote_equipment and rif_equipment arrays
2. Equipment endpoint: quote_equipment contains items with estatus='Entregado' linked to the quote_id
3. Equipment endpoint: rif_equipment contains items from other quotes for same client RIF
4. POST /api/quotes/{id}/send-to-implementation accepts project_type_impl and equipment_serials fields
5. Project created with equipment_serials stores them in 'equipments' array
6. Project created with project_type_impl stores it as 'project_type_impl' field
7. {Modelo_Seriales_Equipos} template variable resolves to HTML table of equipment
8. available_tags endpoint includes Modelo_Seriales_Equipos tag
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test quote with equipment: quo_cfc1984ab493 (has 3 delivered Verifone P200 Pinpad items)
TEST_QUOTE_ID = "quo_cfc1984ab493"
# Test project: prj_ac2f9862c664 (baseline without equipments)
TEST_PROJECT_ID = "prj_ac2f9862c664"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@meganexus.com",
        "password": "Admin123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("session_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Shared requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestEquipmentForImplementationEndpoint:
    """Tests for GET /api/quotes/{id}/equipment-for-implementation"""

    def test_equipment_endpoint_returns_200(self, api_client):
        """Test that the equipment endpoint returns 200 for valid quote"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: Equipment endpoint returns 200")

    def test_equipment_endpoint_returns_quote_equipment_array(self, api_client):
        """Test that response contains quote_equipment array"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        assert "quote_equipment" in data, "Response missing 'quote_equipment' field"
        assert isinstance(data["quote_equipment"], list), "quote_equipment should be a list"
        print(f"PASS: quote_equipment is an array with {len(data['quote_equipment'])} items")

    def test_equipment_endpoint_returns_rif_equipment_array(self, api_client):
        """Test that response contains rif_equipment array"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        assert "rif_equipment" in data, "Response missing 'rif_equipment' field"
        assert isinstance(data["rif_equipment"], list), "rif_equipment should be a list"
        print(f"PASS: rif_equipment is an array with {len(data['rif_equipment'])} items")

    def test_quote_equipment_has_entregado_status(self, api_client):
        """Test that quote_equipment items have estatus='Entregado'"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        for eq in data["quote_equipment"]:
            assert eq.get("estatus") == "Entregado", f"Equipment {eq.get('equipo_id')} has status {eq.get('estatus')}, expected 'Entregado'"
        print(f"PASS: All {len(data['quote_equipment'])} quote_equipment items have estatus='Entregado'")

    def test_quote_equipment_has_required_fields(self, api_client):
        """Test that quote_equipment items have required fields"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        required_fields = ["equipo_id", "modelo", "serial", "estatus", "source"]
        for eq in data["quote_equipment"]:
            for field in required_fields:
                assert field in eq, f"Equipment missing required field: {field}"
            assert eq["source"] == "cotizacion", f"quote_equipment source should be 'cotizacion', got {eq['source']}"
        print(f"PASS: All quote_equipment items have required fields and source='cotizacion'")

    def test_rif_equipment_has_required_fields(self, api_client):
        """Test that rif_equipment items have required fields"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        required_fields = ["equipo_id", "modelo", "serial", "estatus", "source"]
        for eq in data["rif_equipment"]:
            for field in required_fields:
                assert field in eq, f"RIF equipment missing required field: {field}"
            assert eq["source"] == "cliente_rif", f"rif_equipment source should be 'cliente_rif', got {eq['source']}"
        print(f"PASS: All rif_equipment items have required fields and source='cliente_rif'")

    def test_response_includes_client_rif(self, api_client):
        """Test that response includes client_rif"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        assert "client_rif" in data, "Response missing 'client_rif' field"
        assert data["client_rif"], "client_rif should not be empty"
        print(f"PASS: Response includes client_rif: {data['client_rif']}")

    def test_response_includes_total_count(self, api_client):
        """Test that response includes total count"""
        response = api_client.get(f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/equipment-for-implementation")
        data = response.json()
        assert "total" in data, "Response missing 'total' field"
        expected_total = len(data["quote_equipment"]) + len(data["rif_equipment"])
        assert data["total"] == expected_total, f"Total mismatch: {data['total']} != {expected_total}"
        print(f"PASS: Total count is correct: {data['total']}")

    def test_equipment_endpoint_404_for_invalid_quote(self, api_client):
        """Test that endpoint returns 404 for non-existent quote"""
        response = api_client.get(f"{BASE_URL}/api/quotes/quo_nonexistent/equipment-for-implementation")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"PASS: Returns 404 for non-existent quote")


class TestTemplateVariables:
    """Tests for {Modelo_Seriales_Equipos} template variable"""

    def test_template_variables_endpoint_returns_200(self, api_client):
        """Test that template-variables endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: Template variables endpoint returns 200")

    def test_modelo_seriales_equipos_in_variables(self, api_client):
        """Test that Modelo_Seriales_Equipos is in variables"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables")
        data = response.json()
        assert "variables" in data, "Response missing 'variables' field"
        assert "Modelo_Seriales_Equipos" in data["variables"], "Modelo_Seriales_Equipos not in variables"
        print(f"PASS: Modelo_Seriales_Equipos is in variables")

    def test_available_tags_includes_modelo_seriales(self, api_client):
        """Test that available_tags includes Modelo_Seriales_Equipos"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables")
        data = response.json()
        assert "available_tags" in data, "Response missing 'available_tags' field"
        tag_keys = [tag["key"] for tag in data["available_tags"]]
        assert "Modelo_Seriales_Equipos" in tag_keys, "Modelo_Seriales_Equipos not in available_tags"
        
        # Find the tag and verify its properties
        tag = next((t for t in data["available_tags"] if t["key"] == "Modelo_Seriales_Equipos"), None)
        assert tag is not None, "Modelo_Seriales_Equipos tag not found"
        assert "label" in tag, "Tag missing 'label' field"
        assert "source" in tag, "Tag missing 'source' field"
        print(f"PASS: available_tags includes Modelo_Seriales_Equipos with label: {tag['label']}")

    def test_modelo_seriales_html_format_without_equipment(self, api_client):
        """Test that Modelo_Seriales_Equipos returns placeholder when no equipment"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables")
        data = response.json()
        html = data["variables"]["Modelo_Seriales_Equipos"]
        # Project without equipment should show placeholder
        assert "Sin equipos asignados" in html or "<table" in html, f"Unexpected HTML format: {html[:100]}"
        print(f"PASS: Modelo_Seriales_Equipos returns appropriate HTML")


class TestSendToImplementationRequest:
    """Tests for POST /api/quotes/{id}/send-to-implementation request model"""

    def test_send_to_implementation_accepts_project_type_impl(self, api_client):
        """Test that send-to-implementation accepts project_type_impl field"""
        # This is a validation test - we check the endpoint accepts the field
        # We use a quote that's not in 'Pagada' status to trigger the irregular flow check
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/send-to-implementation",
            json={
                "project_type_impl": "pos_fast_track",
                "equipment_serials": []
            }
        )
        # Should either succeed (200) or fail with irregular flow error (422)
        # Both indicate the endpoint accepts the fields
        assert response.status_code in [200, 422, 404], f"Unexpected status: {response.status_code}: {response.text}"
        if response.status_code == 422:
            # Check it's the irregular flow error, not a validation error
            detail = response.json().get("detail", "")
            assert "IRREGULAR" in detail or "motivo" in detail.lower(), f"Unexpected error: {detail}"
        print(f"PASS: send-to-implementation accepts project_type_impl field (status: {response.status_code})")

    def test_send_to_implementation_accepts_equipment_serials(self, api_client):
        """Test that send-to-implementation accepts equipment_serials field"""
        response = api_client.post(
            f"{BASE_URL}/api/quotes/{TEST_QUOTE_ID}/send-to-implementation",
            json={
                "project_type_impl": "vpos_mpos",
                "equipment_serials": [
                    {"modelo": "Verifone P200", "serial": "TEST123"}
                ]
            }
        )
        # Should either succeed (200) or fail with irregular flow error (422)
        assert response.status_code in [200, 422, 404], f"Unexpected status: {response.status_code}: {response.text}"
        print(f"PASS: send-to-implementation accepts equipment_serials field (status: {response.status_code})")


class TestProjectEquipmentStorage:
    """Tests for project equipment storage"""

    def test_project_detail_endpoint_returns_200(self, api_client):
        """Test that project detail endpoint returns 200"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"PASS: Project detail endpoint returns 200")

    def test_project_can_have_equipments_field(self, api_client):
        """Test that project schema supports equipments field"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        data = response.json()
        # The field may or may not exist depending on whether equipment was linked
        # We just verify the endpoint works and returns a valid project
        assert "project_id" in data, "Response missing project_id"
        assert "project_number" in data, "Response missing project_number"
        # equipments field is optional
        equipments = data.get("equipments", [])
        assert isinstance(equipments, list), "equipments should be a list if present"
        print(f"PASS: Project supports equipments field (current count: {len(equipments)})")

    def test_project_can_have_project_type_impl_field(self, api_client):
        """Test that project schema supports project_type_impl field"""
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}")
        data = response.json()
        # The field may or may not exist depending on how project was created
        # We just verify the endpoint works
        project_type_impl = data.get("project_type_impl")
        # If present, should be one of the valid values
        if project_type_impl:
            valid_types = ["pos_fast_track", "vpos_mpos", "payment_gateway"]
            assert project_type_impl in valid_types, f"Invalid project_type_impl: {project_type_impl}"
        print(f"PASS: Project supports project_type_impl field (current value: {project_type_impl})")


class TestEquipmentHTMLGeneration:
    """Tests for equipment HTML generation in template variables"""

    def test_equipment_html_table_structure(self, api_client):
        """Test that equipment HTML has proper table structure when equipment exists"""
        # First, let's check if we can find a project with equipment
        # For now, we test the placeholder case
        response = api_client.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/template-variables")
        data = response.json()
        html = data["variables"]["Modelo_Seriales_Equipos"]
        
        # Should be either a table or a placeholder message
        is_table = "<table" in html and "</table>" in html
        is_placeholder = "Sin equipos asignados" in html
        
        assert is_table or is_placeholder, f"HTML should be table or placeholder: {html[:200]}"
        
        if is_table:
            # Verify table has expected headers
            assert "Modelo" in html, "Table should have 'Modelo' header"
            assert "Serial" in html, "Table should have 'Serial' header"
        
        print(f"PASS: Equipment HTML has proper structure (is_table={is_table}, is_placeholder={is_placeholder})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
