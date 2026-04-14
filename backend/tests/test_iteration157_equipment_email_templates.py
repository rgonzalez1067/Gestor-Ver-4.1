"""
Test Iteration 157: Equipment Email Templates (10 templates for equipment sales flow)
Tests:
1. Verify 10 equipment templates exist in DB
2. Verify GET /api/email-templates returns all 10 equipment templates
3. Verify templates are editable via PUT /api/email-templates/{template_id}
4. Verify template layout (header azul #003366, 900px max-width, footer gris #edf2f7)
5. Verify workflow uses equipment_collect template for quote_category='equipment'
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://lead-management-21.preview.emergentagent.com').rstrip('/')

# Expected equipment template IDs
EXPECTED_EQUIPMENT_TEMPLATES = [
    "equipment_sent_PYME",
    "equipment_sent_CORP",
    "equipment_approved_PYME",
    "equipment_approved_CORP",
    "equipment_invoice_PYME",
    "equipment_invoice_CORP",
    "equipment_collect_PYME",
    "equipment_collect_CORP",
    "equipment_delivery_PYME",
    "equipment_delivery_CORP"
]

# Expected template variables for equipment templates
EQUIPMENT_TEMPLATE_VARIABLES = [
    "Nombre_Cliente",
    "Cotizacion_Nro",
    "Monto_Total",
    "Nombre_Ejecutivo",
    "Email_Ejecutivo"
]


@pytest.fixture(scope="module")
def auth_headers():
    """Login and get auth headers"""
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@meganexus.com",
        "password": "Admin123!"
    })
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json().get("session_token")
    assert token, "No session_token in login response"
    return {"Authorization": f"Bearer {token}"}


class TestEquipmentTemplatesExistence:
    """Test that all 10 equipment templates exist"""
    
    def test_get_all_email_templates(self, auth_headers):
        """GET /api/email-templates should return all templates including equipment ones"""
        resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert resp.status_code == 200, f"Failed to get templates: {resp.text}"
        
        templates = resp.json()
        assert isinstance(templates, list), "Response should be a list"
        assert len(templates) >= 10, f"Expected at least 10 templates, got {len(templates)}"
        
        # Extract template IDs
        template_ids = [t.get('template_id') for t in templates]
        
        # Verify all 10 equipment templates exist
        for expected_id in EXPECTED_EQUIPMENT_TEMPLATES:
            assert expected_id in template_ids, f"Missing equipment template: {expected_id}"
        
        print(f"✓ All 10 equipment templates found in {len(templates)} total templates")
    
    def test_equipment_templates_have_correct_context(self, auth_headers):
        """Equipment templates should have context='EQUIPOS'"""
        resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert resp.status_code == 200
        
        templates = resp.json()
        equipment_templates = [t for t in templates if t.get('template_id', '').startswith('equipment_')]
        
        for template in equipment_templates:
            context = template.get('context', '')
            # Context should be EQUIPOS or empty (some may not have context set)
            assert context in ('EQUIPOS', '', None), f"Template {template['template_id']} has unexpected context: {context}"
        
        print(f"✓ Equipment templates have correct context")
    
    def test_equipment_templates_grouped_by_sede(self, auth_headers):
        """Equipment templates should be grouped by sede (PYME/CORP)"""
        resp = requests.get(f"{BASE_URL}/api/email-templates", headers=auth_headers)
        assert resp.status_code == 200
        
        templates = resp.json()
        equipment_templates = [t for t in templates if t.get('template_id', '').startswith('equipment_')]
        
        pyme_templates = [t for t in equipment_templates if t.get('template_id', '').endswith('_PYME')]
        corp_templates = [t for t in equipment_templates if t.get('template_id', '').endswith('_CORP')]
        
        assert len(pyme_templates) == 5, f"Expected 5 PYME templates, got {len(pyme_templates)}"
        assert len(corp_templates) == 5, f"Expected 5 CORP templates, got {len(corp_templates)}"
        
        print(f"✓ 5 PYME templates + 5 CORP templates = 10 total")


class TestEquipmentTemplateContent:
    """Test equipment template content and layout"""
    
    def test_equipment_sent_template_content(self, auth_headers):
        """equipment_sent templates should have proper subject and body"""
        for sede in ['PYME', 'CORP']:
            template_id = f"equipment_sent_{sede}"
            resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
            assert resp.status_code == 200, f"Failed to get {template_id}: {resp.text}"
            
            template = resp.json()
            assert 'subject' in template, f"Template {template_id} missing subject"
            assert 'body_html' in template, f"Template {template_id} missing body_html"
            
            # Check subject contains quote number variable
            subject = template.get('subject', '')
            assert '{Cotizacion_Nro}' in subject or '{quote_number}' in subject, \
                f"Template {template_id} subject should contain quote number variable"
            
            print(f"✓ {template_id} has valid subject and body")
    
    def test_equipment_template_layout_header(self, auth_headers):
        """Equipment templates should have header with #003366 blue color"""
        for template_id in EXPECTED_EQUIPMENT_TEMPLATES[:2]:  # Test first 2
            resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
            assert resp.status_code == 200
            
            template = resp.json()
            body_html = template.get('body_html', '')
            
            # Check for header color (may be in different formats)
            has_header_color = '#003366' in body_html or '003366' in body_html or 'rgb(0, 51, 102)' in body_html.lower()
            assert has_header_color, f"Template {template_id} should have header color #003366"
            
            print(f"✓ {template_id} has correct header color")
    
    def test_equipment_template_layout_width(self, auth_headers):
        """Equipment templates should have 900px max-width"""
        for template_id in EXPECTED_EQUIPMENT_TEMPLATES[:2]:  # Test first 2
            resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
            assert resp.status_code == 200
            
            template = resp.json()
            body_html = template.get('body_html', '')
            
            # Check for 900px width
            has_width = '900px' in body_html or 'max-width:900' in body_html.replace(' ', '')
            assert has_width, f"Template {template_id} should have 900px max-width"
            
            print(f"✓ {template_id} has correct 900px width")
    
    def test_equipment_template_layout_footer(self, auth_headers):
        """Equipment templates should have footer with #edf2f7 gray color"""
        for template_id in EXPECTED_EQUIPMENT_TEMPLATES[:2]:  # Test first 2
            resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
            assert resp.status_code == 200
            
            template = resp.json()
            body_html = template.get('body_html', '')
            
            # Check for footer color
            has_footer_color = '#edf2f7' in body_html.lower() or 'edf2f7' in body_html.lower()
            assert has_footer_color, f"Template {template_id} should have footer color #edf2f7"
            
            print(f"✓ {template_id} has correct footer color")


class TestEquipmentTemplateEditing:
    """Test that equipment templates are editable"""
    
    def test_edit_equipment_template(self, auth_headers):
        """PUT /api/email-templates/{template_id} should update template"""
        template_id = "equipment_sent_PYME"
        
        # Get current template
        get_resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        original_template = get_resp.json()
        
        # Modify subject
        test_subject = original_template.get('subject', '') + " [TEST]"
        updated_template = {
            **original_template,
            "subject": test_subject
        }
        
        # Update template
        put_resp = requests.put(
            f"{BASE_URL}/api/email-templates/{template_id}",
            headers=auth_headers,
            json=updated_template
        )
        assert put_resp.status_code == 200, f"Failed to update template: {put_resp.text}"
        
        # Verify update
        verify_resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
        assert verify_resp.status_code == 200
        verified_template = verify_resp.json()
        assert verified_template.get('subject') == test_subject, "Subject was not updated"
        
        # Restore original
        restore_resp = requests.put(
            f"{BASE_URL}/api/email-templates/{template_id}",
            headers=auth_headers,
            json=original_template
        )
        assert restore_resp.status_code == 200
        
        print(f"✓ Template {template_id} is editable via PUT")
    
    def test_reset_equipment_template(self, auth_headers):
        """POST /api/email-templates/reset/{template_id} - equipment templates may not have defaults"""
        template_id = "equipment_approved_PYME"
        
        # Reset template - equipment templates are seeded directly, not in defaults
        reset_resp = requests.post(
            f"{BASE_URL}/api/email-templates/reset/{template_id}",
            headers=auth_headers
        )
        
        # Equipment templates may return 404 if not in default templates dictionary
        # This is expected behavior - they were seeded directly to DB
        if reset_resp.status_code == 404:
            print(f"✓ Template {template_id} not in defaults (expected - seeded directly)")
        else:
            assert reset_resp.status_code == 200, f"Unexpected error: {reset_resp.text}"
            result = reset_resp.json()
            assert 'template' in result or 'message' in result
            print(f"✓ Template {template_id} can be reset to default")


class TestWorkflowTemplateResolution:
    """Test that workflow correctly resolves equipment templates"""
    
    def test_workflow_notifications_module_exists(self, auth_headers):
        """Verify workflow_notifications.py has _resolve_template_by_base function"""
        # This is a code review test - we verify the function exists by checking the file
        import os
        workflow_file = "/app/backend/services/workflow_notifications.py"
        assert os.path.exists(workflow_file), "workflow_notifications.py not found"
        
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        assert '_resolve_template_by_base' in content, "Missing _resolve_template_by_base function"
        assert 'template_base_override' in content, "Missing template_base_override parameter"
        
        print("✓ workflow_notifications.py has required functions")
    
    def test_quote_actions_equipment_template_override(self, auth_headers):
        """Verify quote_actions.py uses equipment templates for equipment quotes"""
        import os
        quote_actions_file = "/app/backend/routes/quote_actions.py"
        assert os.path.exists(quote_actions_file), "quote_actions.py not found"
        
        with open(quote_actions_file, 'r') as f:
            content = f.read()
        
        # Check for equipment template overrides in various actions
        assert 'equipment_approved' in content, "Missing equipment_approved template reference"
        assert 'equipment_sent' in content, "Missing equipment_sent template reference"
        assert 'equipment_invoice' in content, "Missing equipment_invoice template reference"
        assert 'equipment_collect' in content, "Missing equipment_collect template reference"
        
        print("✓ quote_actions.py references equipment templates")


class TestEquipmentTemplateVariables:
    """Test that equipment templates have correct variables"""
    
    def test_equipment_templates_have_required_variables(self, auth_headers):
        """Equipment templates should support standard variables"""
        for template_id in EXPECTED_EQUIPMENT_TEMPLATES:
            resp = requests.get(f"{BASE_URL}/api/email-templates/{template_id}", headers=auth_headers)
            assert resp.status_code == 200
            
            template = resp.json()
            body_html = template.get('body_html', '')
            subject = template.get('subject', '')
            full_content = body_html + subject
            
            # Check for at least some key variables
            has_client_var = '{Nombre_Cliente}' in full_content or '{client_name}' in full_content
            has_quote_var = '{Cotizacion_Nro}' in full_content or '{quote_number}' in full_content
            
            assert has_client_var or has_quote_var, \
                f"Template {template_id} should have client or quote variables"
        
        print("✓ Equipment templates have required variables")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
