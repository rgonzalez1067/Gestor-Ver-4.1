# ruff: noqa
"""
Test module: test_repair_collect_warehouse_template.py
Tests for the 5th repair email template: repair_collect_warehouse (PYME + CORP = 2 templates)
This template is triggered when payment is confirmed for repair quotes via collect endpoint.
Sends to Warehouse with CC to the executor.
Variables: {nro_cotizacion}, {nombre_cliente}, {lista_equipos_seriales}, {almacen_custodia}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected template IDs for repair_collect_warehouse
REPAIR_COLLECT_WAREHOUSE_IDS = [
    "repair_collect_warehouse_PYME",
    "repair_collect_warehouse_CORP"
]

# Expected variables for repair_collect_warehouse template
EXPECTED_VARIABLES = [
    "nro_cotizacion",
    "nombre_cliente", 
    "lista_equipos_seriales",
    "almacen_custodia"
]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("session_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Shared requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestRepairCollectWarehouseInListing:
    """Tests for GET /api/email-templates - verify repair_collect_warehouse templates exist"""

    def test_get_all_templates_includes_repair_collect_warehouse_pyme(self, api_client):
        """GET /api/email-templates should include repair_collect_warehouse_PYME"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        
        templates = response.json()
        template_ids = [t.get("template_id") for t in templates]
        
        assert "repair_collect_warehouse_PYME" in template_ids, \
            f"Missing repair_collect_warehouse_PYME in templates. Found: {[t for t in template_ids if 'repair' in t]}"
        
        print("✓ repair_collect_warehouse_PYME found in GET /api/email-templates")

    def test_get_all_templates_includes_repair_collect_warehouse_corp(self, api_client):
        """GET /api/email-templates should include repair_collect_warehouse_CORP"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        
        templates = response.json()
        template_ids = [t.get("template_id") for t in templates]
        
        assert "repair_collect_warehouse_CORP" in template_ids, \
            f"Missing repair_collect_warehouse_CORP in templates. Found: {[t for t in template_ids if 'repair' in t]}"
        
        print("✓ repair_collect_warehouse_CORP found in GET /api/email-templates")


class TestRepairCollectWarehousePYME:
    """Tests for GET /api/email-templates/repair_collect_warehouse_PYME"""

    def test_get_repair_collect_warehouse_pyme_returns_200(self, api_client):
        """GET /api/email-templates/repair_collect_warehouse_PYME should return 200"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_collect_warehouse_PYME"
        print("✓ GET /api/email-templates/repair_collect_warehouse_PYME returns 200")

    def test_repair_collect_warehouse_pyme_has_orden_despacho_subject(self, api_client):
        """repair_collect_warehouse_PYME subject should contain 'ORDEN DE DESPACHO'"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        subject = template.get("subject", "")
        
        assert "ORDEN DE DESPACHO" in subject.upper() or "DESPACHO" in subject.upper(), \
            f"Subject should contain 'ORDEN DE DESPACHO'. Got: {subject}"
        
        print(f"✓ repair_collect_warehouse_PYME subject contains 'ORDEN DE DESPACHO': {subject[:60]}...")

    def test_repair_collect_warehouse_pyme_has_lista_equipos_seriales(self, api_client):
        """repair_collect_warehouse_PYME body should contain {lista_equipos_seriales}"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        body = template.get("body_html", "")
        
        assert "{lista_equipos_seriales}" in body, \
            f"Body should contain {{lista_equipos_seriales}}. Body preview: {body[:200]}..."
        
        print("✓ repair_collect_warehouse_PYME body contains {lista_equipos_seriales}")

    def test_repair_collect_warehouse_pyme_has_almacen_custodia(self, api_client):
        """repair_collect_warehouse_PYME body should contain {almacen_custodia}"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        body = template.get("body_html", "")
        
        assert "{almacen_custodia}" in body, \
            f"Body should contain {{almacen_custodia}}. Body preview: {body[:200]}..."
        
        print("✓ repair_collect_warehouse_PYME body contains {almacen_custodia}")

    def test_repair_collect_warehouse_pyme_has_instrucciones_operativas(self, api_client):
        """repair_collect_warehouse_PYME body should contain 'Instrucciones Operativas'"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        body = template.get("body_html", "")
        
        assert "Instrucciones Operativas" in body or "instrucciones" in body.lower(), \
            f"Body should contain 'Instrucciones Operativas'. Body preview: {body[:300]}..."
        
        print("✓ repair_collect_warehouse_PYME body contains 'Instrucciones Operativas'")

    def test_repair_collect_warehouse_pyme_has_nro_cotizacion(self, api_client):
        """repair_collect_warehouse_PYME should contain {nro_cotizacion}"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        subject = template.get("subject", "")
        body = template.get("body_html", "")
        
        has_nro_cotizacion = "{nro_cotizacion}" in subject or "{nro_cotizacion}" in body
        assert has_nro_cotizacion, "Template should contain {nro_cotizacion}"
        
        print("✓ repair_collect_warehouse_PYME contains {nro_cotizacion}")

    def test_repair_collect_warehouse_pyme_has_nombre_cliente(self, api_client):
        """repair_collect_warehouse_PYME should contain {nombre_cliente}"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        subject = template.get("subject", "")
        body = template.get("body_html", "")
        
        has_nombre_cliente = "{nombre_cliente}" in subject or "{nombre_cliente}" in body
        assert has_nombre_cliente, "Template should contain {nombre_cliente}"
        
        print("✓ repair_collect_warehouse_PYME contains {nombre_cliente}")


class TestRepairCollectWarehouseCORP:
    """Tests for GET /api/email-templates/repair_collect_warehouse_CORP"""

    def test_get_repair_collect_warehouse_corp_returns_200(self, api_client):
        """GET /api/email-templates/repair_collect_warehouse_CORP should return 200"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_CORP")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_collect_warehouse_CORP"
        print("✓ GET /api/email-templates/repair_collect_warehouse_CORP returns 200")

    def test_repair_collect_warehouse_corp_has_orden_despacho_subject(self, api_client):
        """repair_collect_warehouse_CORP subject should contain 'ORDEN DE DESPACHO'"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_CORP")
        assert response.status_code == 200
        
        template = response.json()
        subject = template.get("subject", "")
        
        assert "ORDEN DE DESPACHO" in subject.upper() or "DESPACHO" in subject.upper(), \
            f"Subject should contain 'ORDEN DE DESPACHO'. Got: {subject}"
        
        print(f"✓ repair_collect_warehouse_CORP subject contains 'ORDEN DE DESPACHO': {subject[:60]}...")

    def test_repair_collect_warehouse_corp_has_required_variables(self, api_client):
        """repair_collect_warehouse_CORP should have all required variables"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_CORP")
        assert response.status_code == 200
        
        template = response.json()
        subject = template.get("subject", "")
        body = template.get("body_html", "")
        full_content = subject + body
        
        for var in EXPECTED_VARIABLES:
            assert f"{{{var}}}" in full_content, f"Missing variable {{{var}}} in template"
        
        print("✓ repair_collect_warehouse_CORP has all required variables")


class TestRepairCollectWarehouseUpdate:
    """Tests for PUT /api/email-templates/repair_collect_warehouse_PYME"""

    def test_update_repair_collect_warehouse_pyme(self, api_client):
        """PUT /api/email-templates/repair_collect_warehouse_PYME should update template"""
        # First get the current template
        get_response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert get_response.status_code == 200
        original_template = get_response.json()
        
        # Update with modified subject
        updated_template = {
            **original_template,
            "subject": "TEST UPDATE - ORDEN DE DESPACHO: Pago Confirmado - Cotización #{nro_cotizacion}"
        }
        
        put_response = api_client.put(
            f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME",
            json=updated_template
        )
        assert put_response.status_code == 200, f"Update failed: {put_response.text}"
        
        # Verify update persisted
        verify_response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert verify_response.status_code == 200
        verified_template = verify_response.json()
        assert "TEST UPDATE" in verified_template.get("subject", ""), "Update should persist"
        
        # Reset to original
        reset_response = api_client.post(f"{BASE_URL}/api/email-templates/reset/repair_collect_warehouse_PYME")
        assert reset_response.status_code == 200
        
        print("✓ repair_collect_warehouse_PYME template update and reset verified")


class TestRepairCollectWarehouseDesign:
    """Tests for template design elements"""

    def test_repair_collect_warehouse_has_professional_design(self, api_client):
        """Verify repair_collect_warehouse templates have professional HTML design"""
        for template_id in REPAIR_COLLECT_WAREHOUSE_IDS:
            response = api_client.get(f"{BASE_URL}/api/email-templates/{template_id}")
            assert response.status_code == 200
            
            template = response.json()
            body = template.get("body_html", "")
            
            # Check for professional design elements (header color)
            assert "#2c3e50" in body or "2c3e50" in body, \
                f"Template {template_id} should have #2c3e50 header color"
            
        print("✓ All repair_collect_warehouse templates have professional design with #2c3e50 header")

    def test_repair_collect_warehouse_has_warning_section(self, api_client):
        """Verify repair_collect_warehouse has warning/instructions section with #f39c12 color"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_collect_warehouse_PYME")
        assert response.status_code == 200
        
        template = response.json()
        body = template.get("body_html", "")
        
        # Check for warning section color (orange)
        assert "#f39c12" in body or "#fff8e1" in body or "#e67e22" in body, \
            "Template should have warning section with orange/yellow styling"
        
        print("✓ repair_collect_warehouse has warning/instructions section with proper styling")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
