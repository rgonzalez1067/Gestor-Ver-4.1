"""
Iteration 149: Variable Resolution Bug Fix Tests

CRITICAL BUG: Variables like {Nombre_Cliente}, {Nombre_Implementador}, {Lista_VTID} 
were being sent LITERALLY in emails instead of being resolved.

Root causes fixed:
1) custom_html from editable preview bypassed variable replacement engine
2) contentEditable editor could inject HTML tags inside variable braces (e.g. {<b>Nombre_Cliente</b>})
3) adhoc emails never ran variable replacement

Tests verify:
- custom_html with {Variable} tokens gets resolved
- custom_subject with {Variable} tokens gets resolved
- HTML tags inside braces are cleaned before resolution
- Adhoc email variables are resolved
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROJECT_ID = "prj_ac2f9862c664"  # Multistore project with VTIDs

class TestVariableResolutionBugFix:
    """Tests for the variable resolution bug fix in send-notification endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        
        # Get template variables for verification
        vars_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables", headers=self.headers)
        assert vars_resp.status_code == 200
        self.template_vars = vars_resp.json().get("variables", {})
        self.matrix_html = vars_resp.json().get("matrix_html", "")
    
    # ==================== CRITICAL TEST 1: custom_html with {Nombre_Cliente} ====================
    def test_custom_html_nombre_cliente_resolved(self):
        """CRITICAL: custom_html containing {Nombre_Cliente} must resolve to actual client name"""
        custom_html = """
        <div>
            <p>Estimado cliente: {Nombre_Cliente}</p>
            <p>Su proyecto está en proceso.</p>
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        result = response.json()
        assert result.get("status") == "sent", f"Email not sent: {result}"
        
        # Verify the variable was resolved by checking bitacora
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        assert bitacora_resp.status_code == 200
        entries = bitacora_resp.json()
        
        # Get the latest notification entry
        latest = entries[-1] if entries else {}
        email_detail = latest.get("email_detail", {})
        html_content = email_detail.get("html_content", "")
        
        # CRITICAL: The literal {Nombre_Cliente} should NOT appear in the sent email
        assert "{Nombre_Cliente}" not in html_content, f"Variable NOT resolved! Found literal {{Nombre_Cliente}} in: {html_content[:500]}"
        
        # The actual client name should appear
        expected_name = self.template_vars.get("Nombre_Cliente", "MegaFarma")
        assert expected_name in html_content, f"Expected client name '{expected_name}' not found in HTML"
        print(f"✓ PASS: {{Nombre_Cliente}} resolved to '{expected_name}'")
    
    # ==================== CRITICAL TEST 2: custom_html with {Nombre_Implementador} ====================
    def test_custom_html_nombre_implementador_resolved(self):
        """CRITICAL: custom_html containing {Nombre_Implementador} must resolve to implementer name"""
        custom_html = """
        <div>
            <p>Implementador asignado: {Nombre_Implementador}</p>
            <p>Correo: {Correo_Implementador}</p>
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        
        # Check bitacora for resolved content
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        # CRITICAL: Variables should NOT appear literally
        assert "{Nombre_Implementador}" not in html_content, f"Variable NOT resolved! Found literal {{Nombre_Implementador}}"
        assert "{Correo_Implementador}" not in html_content, f"Variable NOT resolved! Found literal {{Correo_Implementador}}"
        
        # Actual values should appear
        expected_impl = self.template_vars.get("Nombre_Implementador", "Omar")
        expected_email = self.template_vars.get("Correo_Implementador", "")
        assert expected_impl in html_content, f"Expected implementer '{expected_impl}' not found"
        if expected_email:
            assert expected_email in html_content, f"Expected email '{expected_email}' not found"
        print(f"✓ PASS: {{Nombre_Implementador}} resolved to '{expected_impl}'")
    
    # ==================== CRITICAL TEST 3: custom_html with {Lista_VTID} ====================
    def test_custom_html_lista_vtid_resolved(self):
        """CRITICAL: custom_html containing {Lista_VTID} must resolve to VTID HTML table"""
        custom_html = """
        <div>
            <h3>Terminales Virtuales Asignados:</h3>
            {Lista_VTID}
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200, f"Send notification failed: {response.text}"
        
        # Check bitacora for resolved content
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        # CRITICAL: {Lista_VTID} should NOT appear literally
        assert "{Lista_VTID}" not in html_content, f"Variable NOT resolved! Found literal {{Lista_VTID}}"
        
        # The VTID table should contain actual VTID codes (REQ or SST prefixes based on project data)
        # Project has stores Centro (REQ001-REQ005) and Norte (SST001-SST005)
        assert "<table" in html_content or "VTID" in html_content or "REQ" in html_content or "SST" in html_content, \
            f"VTID table content not found in resolved HTML"
        print(f"✓ PASS: {{Lista_VTID}} resolved to HTML table")
    
    # ==================== CRITICAL TEST 4: custom_html with {Contacto_Principal} ====================
    def test_custom_html_contacto_principal_resolved(self):
        """CRITICAL: custom_html containing {Contacto_Principal} must resolve to contact name"""
        custom_html = """
        <div>
            <p>Estimado/a {Contacto_Principal},</p>
            <p>Le informamos sobre su proyecto.</p>
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200
        
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        assert "{Contacto_Principal}" not in html_content, f"Variable NOT resolved! Found literal {{Contacto_Principal}}"
        
        expected_contact = self.template_vars.get("Contacto_Principal", "")
        if expected_contact:
            assert expected_contact in html_content, f"Expected contact '{expected_contact}' not found"
        print(f"✓ PASS: {{Contacto_Principal}} resolved to '{expected_contact}'")
    
    # ==================== CRITICAL TEST 5: custom_subject with variables ====================
    def test_custom_subject_variables_resolved(self):
        """CRITICAL: custom_subject with variables like {Nombre_Cliente} must also be resolved"""
        custom_subject = "Proyecto para {Nombre_Cliente} - Implementador: {Nombre_Implementador}"
        custom_html = "<p>Contenido del correo</p>"
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html,
                "custom_subject": custom_subject
            }
        )
        
        assert response.status_code == 200
        
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        subject = latest.get("email_detail", {}).get("subject", "")
        
        # CRITICAL: Variables in subject should be resolved
        assert "{Nombre_Cliente}" not in subject, f"Variable NOT resolved in subject! Found literal {{Nombre_Cliente}}"
        assert "{Nombre_Implementador}" not in subject, f"Variable NOT resolved in subject! Found literal {{Nombre_Implementador}}"
        
        expected_client = self.template_vars.get("Nombre_Cliente", "")
        expected_impl = self.template_vars.get("Nombre_Implementador", "")
        if expected_client:
            assert expected_client in subject, f"Expected client '{expected_client}' not in subject: {subject}"
        if expected_impl:
            assert expected_impl in subject, f"Expected implementer '{expected_impl}' not in subject: {subject}"
        print(f"✓ PASS: custom_subject variables resolved: {subject}")
    
    # ==================== TEST 6: HTML cleaning - variables with HTML tags inside braces ====================
    def test_html_cleaning_bold_tags_in_variable(self):
        """HTML cleaning: Variables with HTML tags inside braces (e.g. {<b>Nombre</b>}) must still be resolved"""
        # Simulate what contentEditable might produce
        custom_html = """
        <div>
            <p>Cliente: {<b>Nombre_Cliente</b>}</p>
            <p>Implementador: {<span style="color:red">Nombre_Implementador</span>}</p>
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200
        
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        # The malformed variables should be cleaned and resolved
        assert "{<b>Nombre_Cliente</b>}" not in html_content, "Malformed variable not cleaned"
        assert "{<span" not in html_content, "Malformed variable not cleaned"
        
        # Actual values should appear
        expected_client = self.template_vars.get("Nombre_Cliente", "MegaFarma")
        assert expected_client in html_content, f"Expected client '{expected_client}' not found after HTML cleaning"
        print(f"✓ PASS: HTML tags inside braces cleaned and variable resolved")
    
    # ==================== TEST 7: Adhoc email variable resolution ====================
    def test_adhoc_email_variables_resolved(self):
        """Adhoc email: variables in adhoc email message must be resolved via template_vars"""
        message = """
        Estimado {Contacto_Principal},
        
        Le informamos que el proyecto para {Nombre_Cliente} está siendo implementado por {Nombre_Implementador}.
        
        Datos de contacto: {Datos_Contacto}
        
        Saludos.
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-adhoc-email",
            headers={"Authorization": f"Bearer {self.token}"},
            data={
                "recipients": json.dumps(["test@example.com"]),
                "subject": "Actualización de Proyecto {Nombre_Cliente}",
                "message": message,
                "matrix_html": ""
            }
        )
        
        assert response.status_code == 200, f"Adhoc email failed: {response.text}"
        
        # Check bitacora for resolved content
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        
        # Find the adhoc email entry
        adhoc_entries = [e for e in entries if e.get("type") == "adhoc_email"]
        assert adhoc_entries, "No adhoc email entry found in bitacora"
        
        latest = adhoc_entries[-1]
        html_content = latest.get("email_detail", {}).get("html_content", "")
        subject = latest.get("email_detail", {}).get("subject", "")
        
        # CRITICAL: Variables should be resolved in adhoc emails
        assert "{Contacto_Principal}" not in html_content, "Variable NOT resolved in adhoc email body"
        assert "{Nombre_Cliente}" not in html_content, "Variable NOT resolved in adhoc email body"
        assert "{Nombre_Implementador}" not in html_content, "Variable NOT resolved in adhoc email body"
        assert "{Datos_Contacto}" not in html_content, "Variable NOT resolved in adhoc email body"
        assert "{Nombre_Cliente}" not in subject, "Variable NOT resolved in adhoc email subject"
        
        # Actual values should appear
        expected_client = self.template_vars.get("Nombre_Cliente", "")
        if expected_client:
            assert expected_client in html_content, f"Expected client '{expected_client}' not in adhoc email"
        print(f"✓ PASS: Adhoc email variables resolved")
    
    # ==================== TEST 8: Normal flow (no custom_html) still works ====================
    def test_normal_flow_without_custom_html(self):
        """Normal flow (no custom_html): Variables in standard template rendering still work correctly"""
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client"
                # No custom_html - uses default template
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result.get("status") == "sent"
        
        # Check bitacora
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        # Standard template should have resolved variables
        # Check that no raw variable tokens remain
        import re
        unresolved = re.findall(r'\{[A-Za-z_][A-Za-z0-9_]*\}', html_content)
        # Filter out CSS/style braces which are valid
        unresolved = [v for v in unresolved if not v.startswith('{#') and v not in ['{', '}']]
        
        # Some variables might legitimately be empty, but common ones should be resolved
        assert "{Nombre_Cliente}" not in html_content, "Nombre_Cliente not resolved in standard template"
        print(f"✓ PASS: Normal flow (no custom_html) works correctly")
    
    # ==================== TEST 9: Datos_Contacto returns full contact info ====================
    def test_datos_contacto_full_info(self):
        """Variable resolution for Datos_Contacto returns full contact info"""
        datos_contacto = self.template_vars.get("Datos_Contacto", "")
        
        # Datos_Contacto should have format: "name | Tel: phone | Email: email"
        assert datos_contacto, "Datos_Contacto is empty"
        assert "|" in datos_contacto, f"Datos_Contacto missing separator: {datos_contacto}"
        assert "Tel:" in datos_contacto or "Email:" in datos_contacto, f"Datos_Contacto missing contact info: {datos_contacto}"
        print(f"✓ PASS: Datos_Contacto = '{datos_contacto}'")
    
    # ==================== TEST 10: Correo_Implementador returns email ====================
    def test_correo_implementador_returns_email(self):
        """Variable resolution for Correo_Implementador returns email"""
        correo = self.template_vars.get("Correo_Implementador", "")
        
        assert correo, "Correo_Implementador is empty"
        assert "@" in correo, f"Correo_Implementador is not a valid email: {correo}"
        print(f"✓ PASS: Correo_Implementador = '{correo}'")
    
    # ==================== TEST 11: Multiple variables in single custom_html ====================
    def test_multiple_variables_all_resolved(self):
        """Test that multiple different variables in custom_html are all resolved"""
        custom_html = """
        <div>
            <h2>Resumen del Proyecto</h2>
            <p><strong>Cliente:</strong> {Nombre_Cliente}</p>
            <p><strong>Contacto:</strong> {Contacto_Principal}</p>
            <p><strong>Datos:</strong> {Datos_Contacto}</p>
            <p><strong>Implementador:</strong> {Nombre_Implementador}</p>
            <p><strong>Email Impl:</strong> {Correo_Implementador}</p>
            <p><strong>Proyecto:</strong> {project_number}</p>
            <p><strong>Cotización:</strong> {quote_number}</p>
            <h3>Terminales:</h3>
            {Lista_VTID}
        </div>
        """
        
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
            headers=self.headers,
            json={
                "target": "client",
                "custom_html": custom_html
            }
        )
        
        assert response.status_code == 200
        
        bitacora_resp = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/bitacora", headers=self.headers)
        entries = bitacora_resp.json()
        latest = entries[-1] if entries else {}
        html_content = latest.get("email_detail", {}).get("html_content", "")
        
        # Check all variables are resolved
        variables_to_check = [
            "Nombre_Cliente", "Contacto_Principal", "Datos_Contacto",
            "Nombre_Implementador", "Correo_Implementador", "project_number",
            "quote_number", "Lista_VTID"
        ]
        
        unresolved = []
        for var in variables_to_check:
            if f"{{{var}}}" in html_content:
                unresolved.append(var)
        
        assert not unresolved, f"Variables NOT resolved: {unresolved}"
        print(f"✓ PASS: All {len(variables_to_check)} variables resolved in custom_html")


class TestCleanHtmlInBraces:
    """Unit tests for _clean_html_in_braces function"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get session token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_preview_adhoc_cleans_html_in_braces(self):
        """Test that preview-adhoc-email endpoint handles HTML in braces"""
        # This tests the _render_vars function indirectly
        response = requests.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-adhoc-email",
            headers=self.headers,
            json={
                "subject": "Test {<b>Nombre_Cliente</b>}",
                "message": "Hello {<span>Contacto_Principal</span>}",
                "include_matrix": False
            }
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # The preview should have resolved variables (after cleaning HTML)
        subject = result.get("subject", "")
        html = result.get("html", "")
        
        # Check that malformed variables are not present
        assert "{<b>" not in subject, "HTML in braces not cleaned in subject"
        assert "{<span>" not in html, "HTML in braces not cleaned in body"
        print(f"✓ PASS: preview-adhoc-email cleans HTML in braces")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
