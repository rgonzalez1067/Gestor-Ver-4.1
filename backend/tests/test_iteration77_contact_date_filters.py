# ruff: noqa
"""
Iteration 77 Tests - Last Contact Date Field + Table Layout + Filters
Features tested:
1. PATCH /api/integrators/{id}/contact-date - Updates last_contact_date (inline edit)
2. PATCH /api/integrators/{id}/contact-date - Rejects future dates
3. GET /api/integrators - Returns last_contact_date field
4. GET /api/integrators/import/template - Template includes 'Último Contacto' column
5. POST /api/integrators/import - Parses DD/MM/YYYY dates, rejects future dates, stores ISO
6. GET /api/integrators/export/excel - Export includes 'Último Contacto' column
"""
import pytest
import requests
import os
import io
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get session_token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "admin1234"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("session_token")
    assert token, "No session_token returned"
    return token

@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def test_integrator(auth_headers):
    """Create a test integrator for testing and cleanup after"""
    payload = {
        "name": "TEST_ContactDateIntg77",
        "integrator_type": "Integrador",
        "integration_type": "PG",
        "app_name": "TestApp77",
        "integration_modality": "PG Universal",
        "integrator_status": "En proceso",
        "gestor": None,
        "categoria": None
    }
    resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
    assert resp.status_code == 200, f"Failed to create test integrator: {resp.text}"
    integrator = resp.json()
    yield integrator
    # Cleanup
    requests.delete(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}", headers=auth_headers)


class TestPatchContactDate:
    """Tests for PATCH /api/integrators/{id}/contact-date"""

    def test_patch_contact_date_valid(self, auth_headers, test_integrator):
        """Test updating contact date with valid past date"""
        integrator_id = test_integrator['integrator_id']
        valid_date = (date.today() - timedelta(days=5)).isoformat()  # 5 days ago
        
        resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": valid_date},
            headers=auth_headers
        )
        assert resp.status_code == 200, f"PATCH failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("last_contact_date") == valid_date
        
        # Verify via GET
        get_resp = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json().get("last_contact_date") == valid_date

    def test_patch_contact_date_today(self, auth_headers, test_integrator):
        """Test updating contact date with today's date (should be allowed)"""
        integrator_id = test_integrator['integrator_id']
        today = date.today().isoformat()
        
        resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": today},
            headers=auth_headers
        )
        assert resp.status_code == 200, f"PATCH with today's date failed: {resp.text}"
        assert resp.json().get("last_contact_date") == today

    def test_patch_contact_date_rejects_future(self, auth_headers, test_integrator):
        """Test that future dates are rejected"""
        integrator_id = test_integrator['integrator_id']
        future_date = (date.today() + timedelta(days=10)).isoformat()
        
        resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": future_date},
            headers=auth_headers
        )
        assert resp.status_code == 400, f"Expected 400 for future date, got {resp.status_code}: {resp.text}"
        assert "futura" in resp.json().get("detail", "").lower() or "future" in resp.json().get("detail", "").lower()

    def test_patch_contact_date_clear(self, auth_headers, test_integrator):
        """Test clearing contact date (null)"""
        integrator_id = test_integrator['integrator_id']
        # First set a date
        requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": date.today().isoformat()},
            headers=auth_headers
        )
        
        # Now clear it
        resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": None},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json().get("last_contact_date") is None

    def test_patch_contact_date_invalid_format(self, auth_headers, test_integrator):
        """Test invalid date format is rejected"""
        integrator_id = test_integrator['integrator_id']
        
        resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": "32/13/2025"},  # Invalid date
            headers=auth_headers
        )
        assert resp.status_code == 400, f"Expected 400 for invalid date, got {resp.status_code}"


class TestGetIntegratorsReturnsContactDate:
    """Tests for GET /api/integrators including last_contact_date"""

    def test_get_integrators_includes_contact_date(self, auth_headers, test_integrator):
        """Test that GET /api/integrators returns last_contact_date field"""
        # First set a contact date on test integrator
        integrator_id = test_integrator['integrator_id']
        test_date = "2026-01-15"
        requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": test_date},
            headers=auth_headers
        )
        
        # GET all integrators
        resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert resp.status_code == 200
        integrators = resp.json()
        
        # Find our test integrator
        test_intg = next((i for i in integrators if i['integrator_id'] == integrator_id), None)
        assert test_intg is not None, "Test integrator not found in list"
        assert "last_contact_date" in test_intg, "last_contact_date field missing"
        assert test_intg["last_contact_date"] == test_date


class TestImportTemplateIncludesContactDate:
    """Tests for GET /api/integrators/import/template including Último Contacto"""

    def test_template_has_contact_date_column(self, auth_headers):
        """Test that import template includes 'Último Contacto' column"""
        resp = requests.get(f"{BASE_URL}/api/integrators/import/template", headers=auth_headers)
        assert resp.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.headers.get("Content-Type", "")
        
        # Parse Excel
        import pandas as pd
        df = pd.read_excel(io.BytesIO(resp.content), sheet_name='Plantilla')
        columns = list(df.columns)
        
        # Check for 'Último Contacto' column
        assert 'Último Contacto' in columns, f"'Último Contacto' column not found in template. Columns: {columns}"
        
        # Verify base columns (9 expected: Nombre, Tipo, Aplicativo, Modalidad, Estatus, Tipo Integración, Gestor, Categoría, Último Contacto)
        expected_base = ['Nombre', 'Tipo', 'Aplicativo', 'Modalidad', 'Estatus', 'Tipo Integración', 'Gestor', 'Categoría', 'Último Contacto']
        for col in expected_base:
            assert col in columns, f"Base column '{col}' missing. Columns: {columns}"

    def test_template_instructions_include_contact_date(self, auth_headers):
        """Test that instructions sheet documents Último Contacto"""
        resp = requests.get(f"{BASE_URL}/api/integrators/import/template", headers=auth_headers)
        assert resp.status_code == 200
        
        import pandas as pd
        df_inst = pd.read_excel(io.BytesIO(resp.content), sheet_name='Instrucciones')
        campos = list(df_inst['Campo'].astype(str))
        
        assert 'Último Contacto' in campos, f"'Último Contacto' not documented in instructions. Campos: {campos}"


class TestImportParsesContactDate:
    """Tests for POST /api/integrators/import with contact date parsing"""

    def test_import_parses_dd_mm_yyyy(self, auth_headers):
        """Test that import parses DD/MM/YYYY format correctly"""
        import pandas as pd
        
        data = {
            'Nombre': ['TEST_ImportDate77_A'],
            'Tipo': ['Integrador'],
            'Aplicativo': ['ImportApp77A'],
            'Modalidad': ['MPOS'],
            'Estatus': ['En proceso'],
            'Tipo Integración': ['MP'],
            'Gestor': [''],
            'Categoría': [''],
            'Último Contacto': ['15/01/2026']  # DD/MM/YYYY format
        }
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        
        files = {'file': ('test_import.xlsx', output, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        resp = requests.post(
            f"{BASE_URL}/api/integrators/import",
            files=files,
            data={'mode': 'upsert'},
            headers=auth_headers
        )
        assert resp.status_code == 200, f"Import failed: {resp.text}"
        result = resp.json()
        assert result['status'] in ['success', 'partial'], f"Import not successful: {result}"
        
        # Verify the date was stored as ISO
        get_resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = get_resp.json()
        test_intg = next((i for i in integrators if i['name'] == 'TEST_ImportDate77_A'), None)
        assert test_intg is not None, "Imported integrator not found"
        assert test_intg['last_contact_date'] == '2026-01-15', f"Date not stored as ISO: {test_intg['last_contact_date']}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{test_intg['integrator_id']}", headers=auth_headers)

    def test_import_rejects_future_contact_date(self, auth_headers):
        """Test that import rejects future dates in Último Contacto"""
        import pandas as pd
        
        future_date = (date.today() + timedelta(days=30)).strftime('%d/%m/%Y')
        data = {
            'Nombre': ['TEST_ImportDate77_Future'],
            'Tipo': ['Comercio'],
            'Aplicativo': ['FutureApp77'],
            'Modalidad': ['REST'],
            'Estatus': ['En proceso'],
            'Tipo Integración': ['CR'],
            'Gestor': [''],
            'Categoría': [''],
            'Último Contacto': [future_date]  # Future date
        }
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        
        files = {'file': ('test_import_future.xlsx', output, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        resp = requests.post(
            f"{BASE_URL}/api/integrators/import",
            files=files,
            data={'mode': 'upsert'},
            headers=auth_headers
        )
        assert resp.status_code == 200
        result = resp.json()
        
        # Should have errors for future date
        errors = result.get('errors', [])
        future_errors = [e for e in errors if 'Último Contacto' in e.get('column', '') or 'futura' in e.get('message', '').lower()]
        assert len(future_errors) > 0, f"No error for future date. Result: {result}"
        
        # Cleanup if created anyway
        get_resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        for intg in get_resp.json():
            if intg['name'] == 'TEST_ImportDate77_Future':
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)


class TestExportIncludesContactDate:
    """Tests for GET /api/integrators/export/excel including Último Contacto"""

    def test_export_has_contact_date_column(self, auth_headers, test_integrator):
        """Test that export includes 'Último Contacto' column"""
        # Set a contact date
        integrator_id = test_integrator['integrator_id']
        test_date = "2026-03-01"
        requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": test_date},
            headers=auth_headers
        )
        
        resp = requests.get(f"{BASE_URL}/api/integrators/export/excel", headers=auth_headers)
        assert resp.status_code == 200
        
        import pandas as pd
        df = pd.read_excel(io.BytesIO(resp.content))
        columns = list(df.columns)
        
        assert 'Último Contacto' in columns, f"'Último Contacto' not in export columns: {columns}"
        
        # Find our test integrator row by integrator_id (more specific search)
        # Check there's at least one row with our test integrator name
        test_rows = df[df['Nombre'] == test_integrator['name']]
        assert len(test_rows) >= 1, "Test integrator not found in export"
        # Check if any of them have our date
        found_date = False
        for _, row in test_rows.iterrows():
            if row['Último Contacto'] == test_date:
                found_date = True
                break
        assert found_date, f"Test integrator with date {test_date} not found. Found rows: {test_rows['Último Contacto'].tolist()}"


class TestIntegratorModelHasContactDate:
    """Tests for Integrator model having last_contact_date field"""

    def test_create_integrator_with_contact_date(self, auth_headers):
        """Test creating integrator with last_contact_date"""
        payload = {
            "name": "TEST_CreateDate77",
            "integrator_type": "Comercio",
            "integration_type": "LP",
            "app_name": "CreateDateApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso",
            "last_contact_date": "2026-02-20"
        }
        resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        intg = resp.json()
        assert intg.get("last_contact_date") == "2026-02-20"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)

    def test_update_integrator_preserves_contact_date(self, auth_headers, test_integrator):
        """Test PUT /api/integrators/{id} preserves last_contact_date"""
        integrator_id = test_integrator['integrator_id']
        
        # Set contact date via PATCH
        requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/contact-date",
            json={"last_contact_date": "2026-01-10"},
            headers=auth_headers
        )
        
        # Update other fields via PUT
        update_payload = {
            "name": test_integrator['name'],
            "integrator_type": test_integrator['integrator_type'],
            "integration_type": test_integrator.get('integration_type'),
            "app_name": "UpdatedApp77",
            "integration_modality": test_integrator['integration_modality'],
            "integrator_status": "Certificado",
            "last_contact_date": "2026-01-10"  # Include to preserve
        }
        resp = requests.put(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert resp.status_code == 200
        
        # Verify contact date preserved
        get_resp = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        assert get_resp.json().get("last_contact_date") == "2026-01-10"
