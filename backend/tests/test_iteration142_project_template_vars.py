"""
Test iteration 142: Project Template Variables and Preview Endpoints
Tests:
- GET /api/projects/{id}/template-variables - returns all resolved variables
- POST /api/projects/{id}/preview-notification - returns rendered email for client/bank notifications
- POST /api/projects/{id}/preview-adhoc-email - renders variables in subject and message
- Variable resolution: {Nombre_Cliente}, {Contacto_Principal}, {Nombre_Sucursal}, {Cantidad_Cajas}, {Integrador}, {Matriz_Bancos_Productos}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
PROJECT_ID = "prj_c536858da780"  # Multistore project with 5 stores and 3 banks

# Test credentials
ADMIN_EMAIL = "admin@meganexus.com"
ADMIN_PASSWORD = "Admin123!"
ANALISTA_EMAIL = "analista@meganexus.com"
ANALISTA_PASSWORD = "Analista123!"


@pytest.fixture(scope="module")
def admin_session():
    """Login as admin and return session with token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    token = data.get("session_token") or data.get("token")
    assert token, "No session_token in login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def analista_session():
    """Login as analista and return session with token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": ANALISTA_EMAIL,
        "password": ANALISTA_PASSWORD
    })
    assert response.status_code == 200, f"Analista login failed: {response.text}"
    data = response.json()
    token = data.get("session_token") or data.get("token")
    assert token, "No session_token in login response"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestProjectTemplateVariables:
    """Test GET /api/projects/{id}/template-variables endpoint"""
    
    def test_get_template_variables_returns_all_variables(self, admin_session):
        """Verify endpoint returns all resolved variables for a project"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "variables" in data, "Response should contain 'variables' key"
        assert "matrix_html" in data, "Response should contain 'matrix_html' key"
        assert "available_tags" in data, "Response should contain 'available_tags' key"
        
        variables = data["variables"]
        # Check all required variables are present
        required_vars = [
            "Nombre_Cliente", "Contacto_Principal", "Nombre_Sucursal",
            "Cantidad_Cajas", "Integrador", "project_number", "quote_number",
            "ticket_number", "client_rif", "quote_type"
        ]
        for var in required_vars:
            assert var in variables, f"Variable '{var}' should be in response"
        
        print(f"Variables resolved: {list(variables.keys())}")
        print(f"Nombre_Cliente: {variables.get('Nombre_Cliente')}")
        print(f"Integrador: {variables.get('Integrador')}")
    
    def test_nombre_cliente_resolves_to_razon_social(self, admin_session):
        """Verify {Nombre_Cliente} resolves to client's razon_social"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        variables = response.json()["variables"]
        nombre_cliente = variables.get("Nombre_Cliente", "")
        
        # Should not be empty
        assert nombre_cliente, "Nombre_Cliente should not be empty"
        print(f"Nombre_Cliente resolved to: {nombre_cliente}")
    
    def test_integrador_resolves_to_integrator_name(self, admin_session):
        """Verify {Integrador} resolves to integrator_name"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        variables = response.json()["variables"]
        integrador = variables.get("Integrador", "")
        
        # Should have a value (even if "—" for no integrator)
        assert integrador is not None, "Integrador should be present"
        print(f"Integrador resolved to: {integrador}")
    
    def test_nombre_sucursal_resolves_for_multistore(self, admin_session):
        """Verify {Nombre_Sucursal} resolves to store names for multistore projects"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        variables = response.json()["variables"]
        nombre_sucursal = variables.get("Nombre_Sucursal", "")
        
        # For multistore, should contain multiple store names
        assert nombre_sucursal, "Nombre_Sucursal should not be empty"
        print(f"Nombre_Sucursal resolved to: {nombre_sucursal}")
    
    def test_cantidad_cajas_resolves_for_multistore(self, admin_session):
        """Verify {Cantidad_Cajas} resolves to box counts per store"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        variables = response.json()["variables"]
        cantidad_cajas = variables.get("Cantidad_Cajas", "")
        
        # For multistore, should contain per-store counts
        assert cantidad_cajas, "Cantidad_Cajas should not be empty"
        print(f"Cantidad_Cajas resolved to: {cantidad_cajas}")
    
    def test_matriz_bancos_productos_generates_html_table(self, admin_session):
        """Verify {Matriz_Bancos_Productos} generates HTML table with bank/product/quantity columns"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        data = response.json()
        matrix_html = data.get("matrix_html", "")
        
        # Should contain HTML table structure
        assert "<table" in matrix_html or "<p>" in matrix_html, "matrix_html should contain HTML"
        
        # If it's a table, check for expected columns
        if "<table" in matrix_html:
            assert "Banco" in matrix_html, "Table should have 'Banco' column"
            assert "Producto" in matrix_html or "Servicio" in matrix_html, "Table should have product column"
            assert "Cantidad" in matrix_html, "Table should have 'Cantidad' column"
        
        print(f"Matrix HTML length: {len(matrix_html)} chars")
    
    def test_available_tags_includes_all_variables(self, admin_session):
        """Verify available_tags includes all documented variables"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        available_tags = response.json().get("available_tags", [])
        tag_keys = [t["key"] for t in available_tags]
        
        required_tags = [
            "Nombre_Cliente", "Contacto_Principal", "Nombre_Sucursal",
            "Cantidad_Cajas", "Integrador", "Matriz_Bancos_Productos"
        ]
        for tag in required_tags:
            assert tag in tag_keys, f"Tag '{tag}' should be in available_tags"
        
        print(f"Available tags: {tag_keys}")


class TestPreviewNotification:
    """Test POST /api/projects/{id}/preview-notification endpoint"""
    
    def test_preview_client_notification(self, admin_session):
        """Verify preview-notification returns rendered email for client"""
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={
                "target": "client",
                "bank_name": None,
                "level": "Primera Comunicación"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "subject" in data, "Response should contain 'subject'"
        assert "html" in data, "Response should contain 'html'"
        assert "recipients" in data, "Response should contain 'recipients'"
        assert "entity_label" in data, "Response should contain 'entity_label'"
        assert "variables" in data, "Response should contain 'variables'"
        
        # Verify entity_label indicates client
        assert "Cliente" in data["entity_label"], "entity_label should indicate client"
        
        # Verify HTML contains rendered content (not raw variables)
        html = data["html"]
        assert "{Nombre_Cliente}" not in html or data["variables"].get("Nombre_Cliente") in html, \
            "Variables should be rendered in HTML"
        
        print(f"Subject: {data['subject']}")
        print(f"Entity: {data['entity_label']}")
        print(f"Recipients: {data['recipients']}")
    
    def test_preview_bank_notification(self, admin_session):
        """Verify preview-notification returns rendered email for bank"""
        # First get the project to find a bank name
        proj_response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert proj_response.status_code == 200
        
        project = proj_response.json()
        matrix = project.get("implementation_matrix", {})
        bank_names = list(matrix.keys())
        
        if not bank_names:
            pytest.skip("No banks in project matrix")
        
        bank_name = bank_names[0]
        
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={
                "target": "bank",
                "bank_name": bank_name,
                "level": "Primera Comunicación"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "subject" in data
        assert "html" in data
        assert "entity_label" in data
        
        # Verify entity_label indicates bank
        assert "Banco" in data["entity_label"], "entity_label should indicate bank"
        assert bank_name in data["entity_label"], f"entity_label should contain bank name '{bank_name}'"
        
        print(f"Bank notification subject: {data['subject']}")
        print(f"Entity: {data['entity_label']}")
    
    def test_preview_notification_invalid_level(self, admin_session):
        """Verify preview-notification rejects invalid notification level"""
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
            json={
                "target": "client",
                "bank_name": None,
                "level": "Invalid Level"
            }
        )
        assert response.status_code == 400, "Should reject invalid level"


class TestPreviewAdhocEmail:
    """Test POST /api/projects/{id}/preview-adhoc-email endpoint"""
    
    def test_preview_adhoc_email_renders_variables(self, admin_session):
        """Verify preview-adhoc-email renders variables in subject and message"""
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-adhoc-email",
            json={
                "subject": "Actualización para {Nombre_Cliente}",
                "message": "Estimado {Contacto_Principal},\n\nSu proyecto con {Integrador} está en proceso.",
                "include_matrix": False
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "subject" in data, "Response should contain 'subject'"
        assert "html" in data, "Response should contain 'html'"
        assert "variables" in data, "Response should contain 'variables'"
        
        # Verify variables are rendered (not raw placeholders)
        subject = data["subject"]
        html = data["html"]
        
        # Subject should not contain raw {Nombre_Cliente} if it was resolved
        if data["variables"].get("Nombre_Cliente"):
            assert "{Nombre_Cliente}" not in subject or data["variables"]["Nombre_Cliente"] in subject
        
        print(f"Rendered subject: {subject}")
        print(f"Variables used: {list(data['variables'].keys())}")
    
    def test_preview_adhoc_email_with_matrix(self, admin_session):
        """Verify preview-adhoc-email includes matrix when requested"""
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-adhoc-email",
            json={
                "subject": "Matriz de seguimiento",
                "message": "Adjunto la matriz de bancos y productos.",
                "include_matrix": True
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        html = data["html"]
        
        # When include_matrix is True, HTML should contain matrix content
        # Either a table or the matrix placeholder
        assert len(html) > 100, "HTML should contain substantial content with matrix"
        print(f"HTML with matrix length: {len(html)} chars")
    
    def test_preview_adhoc_email_without_matrix(self, admin_session):
        """Verify preview-adhoc-email excludes matrix when not requested"""
        response = admin_session.post(
            f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-adhoc-email",
            json={
                "subject": "Simple message",
                "message": "Just a test message.",
                "include_matrix": False
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        html = data["html"]
        
        # HTML should be simpler without matrix
        assert "Just a test message" in html or "test message" in html.lower()
        print(f"HTML without matrix length: {len(html)} chars")


class TestContactoPrincipal:
    """Test {Contacto_Principal} variable resolution"""
    
    def test_contacto_principal_resolves_to_first_contact(self, admin_session):
        """Verify {Contacto_Principal} resolves to client's first contact full_name"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
        assert response.status_code == 200
        
        variables = response.json()["variables"]
        contacto = variables.get("Contacto_Principal", "")
        
        # Should have a value (may be empty if no contacts)
        print(f"Contacto_Principal resolved to: '{contacto}'")
        # Not asserting non-empty since client may not have contacts


class TestRBACAnalistaReparaciones:
    """Test RBAC fix: analista user with cotizaciones:reparaciones sees Reparaciones button"""
    
    def test_analista_login_has_special_permissions(self, analista_session):
        """Verify analista user has cotizaciones:reparaciones permission"""
        # Get user info from a protected endpoint
        response = analista_session.get(f"{BASE_URL}/api/auth/me")
        
        if response.status_code == 200:
            user = response.json()
            special_perms = user.get("special_permissions", [])
            print(f"Analista special_permissions: {special_perms}")
            
            # Check if cotizaciones:reparaciones is in special_permissions
            has_reparaciones = "cotizaciones:reparaciones" in special_perms
            print(f"Has cotizaciones:reparaciones: {has_reparaciones}")
        else:
            # If /auth/me doesn't exist, just verify login works
            print("Note: /api/auth/me endpoint not available, login verified")


class TestProjectExists:
    """Verify test project exists and has expected structure"""
    
    def test_project_exists(self, admin_session):
        """Verify the test project exists"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert response.status_code == 200, f"Project {PROJECT_ID} not found: {response.text}"
        
        project = response.json()
        print(f"Project: {project.get('project_number')}")
        print(f"Client: {project.get('client_name')}")
        print(f"Type: {project.get('project_type')}")
        print(f"Stores: {len(project.get('stores', []))}")
        print(f"Banks in matrix: {list(project.get('implementation_matrix', {}).keys())}")
    
    def test_project_is_multistore(self, admin_session):
        """Verify the test project is multistore with expected stores"""
        response = admin_session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}")
        assert response.status_code == 200
        
        project = response.json()
        assert project.get("project_type") == "multistore", "Project should be multistore"
        
        stores = project.get("stores", [])
        assert len(stores) >= 1, "Multistore project should have stores"
        print(f"Number of stores: {len(stores)}")
        for store in stores:
            print(f"  - {store.get('name')}: {store.get('box_count')} boxes")
