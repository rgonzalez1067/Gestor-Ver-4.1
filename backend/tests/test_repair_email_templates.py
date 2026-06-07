# ruff: noqa
"""
Test module: test_repair_email_templates.py
Tests for the 4 new repair email templates (PYME + CORP = 8 total):
1. repair_quote_sent - Envío Cotización de Reparación al Cliente
2. repair_approved - Aprobación Cotización de Reparación
3. repair_complete_client - Notificación Reparación Finalizada
4. repair_delivery - Orden de Entrega de Equipos Reparados
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected repair template IDs
REPAIR_TEMPLATE_IDS = [
    "repair_quote_sent_PYME",
    "repair_quote_sent_CORP",
    "repair_approved_PYME",
    "repair_approved_CORP",
    "repair_complete_client_PYME",
    "repair_complete_client_CORP",
    "repair_delivery_PYME",
    "repair_delivery_CORP"
]

# Expected variables per template type
EXPECTED_VARIABLES = {
    "repair_quote_sent": ["nro_cotizacion", "contacto_cliente", "modelos_resumen"],
    "repair_approved": ["nro_cotizacion", "contacto_cliente"],
    "repair_complete_client": ["nro_cotizacion", "contacto_cliente", "lista_modelos_seriales"],
    "repair_delivery": ["nro_nota_entrega", "tipo_nota_entrega", "cantidad_entregada", "estatus_entrega"]
}


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


class TestRepairEmailTemplatesListing:
    """Tests for GET /api/email-templates - verify all 8 repair templates exist"""

    def test_get_all_templates_returns_repair_templates(self, api_client):
        """GET /api/email-templates should return all 8 repair templates"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        
        templates = response.json()
        assert isinstance(templates, list), "Response should be a list"
        
        # Extract template IDs
        template_ids = [t.get("template_id") for t in templates]
        
        # Verify all 8 repair templates exist
        for repair_id in REPAIR_TEMPLATE_IDS:
            assert repair_id in template_ids, f"Missing repair template: {repair_id}"
        
        print("✓ All 8 repair templates found in GET /api/email-templates")

    def test_repair_templates_have_correct_structure(self, api_client):
        """Verify repair templates have required fields"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        
        templates = response.json()
        repair_templates = [t for t in templates if t.get("template_id", "").startswith("repair_")]
        
        assert len(repair_templates) >= 8, f"Expected at least 8 repair templates, got {len(repair_templates)}"
        
        for template in repair_templates:
            assert "template_id" in template, f"Missing template_id in {template}"
            assert "name" in template, f"Missing name in {template}"
            assert "subject" in template, f"Missing subject in {template}"
            assert "body_html" in template, f"Missing body_html in {template}"
            
        print("✓ All repair templates have correct structure")


class TestRepairQuoteSentTemplate:
    """Tests for repair_quote_sent template (PYME and CORP)"""

    def test_get_repair_quote_sent_pyme(self, api_client):
        """GET /api/email-templates/repair_quote_sent_PYME should return template with nro_cotizacion"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_quote_sent_PYME")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_quote_sent_PYME"
        assert "{nro_cotizacion}" in template.get("subject", ""), "Subject should contain {nro_cotizacion}"
        
        body = template.get("body_html", "")
        assert "{contacto_cliente}" in body, "Body should contain {contacto_cliente}"
        assert "{modelos_resumen}" in body, "Body should contain {modelos_resumen}"
        
        print("✓ repair_quote_sent_PYME template verified with correct variables")

    def test_get_repair_quote_sent_corp(self, api_client):
        """GET /api/email-templates/repair_quote_sent_CORP should return template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_quote_sent_CORP")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_quote_sent_CORP"
        assert "{nro_cotizacion}" in template.get("subject", "")
        
        print("✓ repair_quote_sent_CORP template verified")


class TestRepairApprovedTemplate:
    """Tests for repair_approved template (PYME and CORP)"""

    def test_get_repair_approved_pyme(self, api_client):
        """GET /api/email-templates/repair_approved_PYME should return approval template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_approved_PYME")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_approved_PYME"
        assert "{nro_cotizacion}" in template.get("subject", "")
        
        body = template.get("body_html", "")
        assert "{contacto_cliente}" in body, "Body should contain {contacto_cliente}"
        
        print("✓ repair_approved_PYME template verified")

    def test_get_repair_approved_corp(self, api_client):
        """GET /api/email-templates/repair_approved_CORP should return approval template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_approved_CORP")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_approved_CORP"
        
        print("✓ repair_approved_CORP template verified")


class TestRepairCompleteClientTemplate:
    """Tests for repair_complete_client template (PYME and CORP)"""

    def test_get_repair_complete_client_pyme(self, api_client):
        """GET /api/email-templates/repair_complete_client_PYME should return template with lista_modelos_seriales"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_complete_client_PYME")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_complete_client_PYME"
        
        body = template.get("body_html", "")
        assert "{lista_modelos_seriales}" in body, "Body should contain {lista_modelos_seriales}"
        assert "{contacto_cliente}" in body, "Body should contain {contacto_cliente}"
        
        print("✓ repair_complete_client_PYME template verified with lista_modelos_seriales")

    def test_get_repair_complete_client_corp(self, api_client):
        """GET /api/email-templates/repair_complete_client_CORP should return template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_complete_client_CORP")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_complete_client_CORP"
        
        print("✓ repair_complete_client_CORP template verified")


class TestRepairDeliveryTemplate:
    """Tests for repair_delivery template (PYME and CORP)"""

    def test_get_repair_delivery_pyme(self, api_client):
        """GET /api/email-templates/repair_delivery_PYME should return template with delivery variables"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_delivery_PYME")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_delivery_PYME"
        
        subject = template.get("subject", "")
        body = template.get("body_html", "")
        
        # Check for delivery-specific variables
        assert "{nro_nota_entrega}" in subject or "{nro_nota_entrega}" in body, "Should contain {nro_nota_entrega}"
        assert "{tipo_nota_entrega}" in body, "Body should contain {tipo_nota_entrega}"
        assert "{cantidad_entregada}" in body, "Body should contain {cantidad_entregada}"
        assert "{estatus_entrega}" in body, "Body should contain {estatus_entrega}"
        
        print("✓ repair_delivery_PYME template verified with all delivery variables")

    def test_get_repair_delivery_corp(self, api_client):
        """GET /api/email-templates/repair_delivery_CORP should return template"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_delivery_CORP")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        template = response.json()
        assert template.get("template_id") == "repair_delivery_CORP"
        
        print("✓ repair_delivery_CORP template verified")


class TestRepairTemplateUpdate:
    """Tests for updating repair templates via PUT"""

    def test_update_repair_quote_sent_pyme(self, api_client):
        """PUT /api/email-templates/repair_quote_sent_PYME should update template"""
        # First get the current template
        get_response = api_client.get(f"{BASE_URL}/api/email-templates/repair_quote_sent_PYME")
        assert get_response.status_code == 200
        original_template = get_response.json()
        
        # Update with modified subject
        updated_template = {
            **original_template,
            "subject": "TEST UPDATE - Presupuesto de Reparación - Cotización Nro. {nro_cotizacion}"
        }
        
        put_response = api_client.put(
            f"{BASE_URL}/api/email-templates/repair_quote_sent_PYME",
            json=updated_template
        )
        assert put_response.status_code == 200, f"Update failed: {put_response.text}"
        
        # Verify update persisted
        verify_response = api_client.get(f"{BASE_URL}/api/email-templates/repair_quote_sent_PYME")
        assert verify_response.status_code == 200
        verified_template = verify_response.json()
        assert "TEST UPDATE" in verified_template.get("subject", ""), "Update should persist"
        
        # Reset to original
        reset_response = api_client.post(f"{BASE_URL}/api/email-templates/reset/repair_quote_sent_PYME")
        assert reset_response.status_code == 200
        
        print("✓ repair_quote_sent_PYME template update and reset verified")


class TestRepairTemplateDesign:
    """Tests for template design elements"""

    def test_repair_templates_have_professional_design(self, api_client):
        """Verify repair templates have professional HTML design with #2c3e50 header"""
        response = api_client.get(f"{BASE_URL}/api/email-templates")
        assert response.status_code == 200
        
        templates = response.json()
        repair_templates = [t for t in templates if t.get("template_id", "").startswith("repair_")]
        
        for template in repair_templates:
            body = template.get("body_html", "")
            # Check for professional design elements
            assert "#2c3e50" in body or "2c3e50" in body, f"Template {template.get('template_id')} should have #2c3e50 header color"
            
        print("✓ All repair templates have professional design with #2c3e50 header")

    def test_repair_delivery_has_orange_button(self, api_client):
        """Verify repair_delivery template has #f39c12 orange action button"""
        response = api_client.get(f"{BASE_URL}/api/email-templates/repair_delivery_PYME")
        assert response.status_code == 200
        
        template = response.json()
        body = template.get("body_html", "")
        
        # Check for orange button color
        assert "#f39c12" in body or "f39c12" in body, "repair_delivery should have #f39c12 orange button"
        
        print("✓ repair_delivery template has orange action button")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
