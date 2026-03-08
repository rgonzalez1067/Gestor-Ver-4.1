"""
Iteration 75 - Import Wizard Modal with Template Download and Mode Selection
Tests for:
- GET /api/integrators/import/template - Downloads .xlsx template with 3 sheets
- POST /api/integrators/import with mode=upsert - Updates existing, creates new
- POST /api/integrators/import with mode=insert_only - Skips duplicates with error
- ImportResult has updated_count separate from success_count
- Gestor validation against users DB
- Integration_type validation (CR/LP/PG/MP/TK)
"""

import pytest
import requests
import os
import io
import openpyxl

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin1234"


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get session token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("session_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestTemplateDownload:
    """Test GET /api/integrators/import/template - Template download endpoint"""
    
    def test_template_download_returns_xlsx_file(self, auth_headers):
        """GET /api/integrators/import/template should return .xlsx file"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200, f"Template download failed: {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in content_type or \
               "application/octet-stream" in content_type, \
               f"Expected xlsx content type, got {content_type}"
        
        # Check content disposition
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp.lower(), "Should be an attachment"
        assert ".xlsx" in content_disp or "plantilla" in content_disp.lower(), \
               f"Expected xlsx filename, got {content_disp}"
        
        print(f"SUCCESS: Template download returns xlsx file, size: {len(response.content)} bytes")
    
    def test_template_has_three_sheets(self, auth_headers):
        """Template should have 3 sheets: Plantilla, Instrucciones, Valores Válidos"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Parse the Excel file
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet_names = workbook.sheetnames
        
        print(f"Template sheets: {sheet_names}")
        
        # Should have 3 sheets
        assert len(sheet_names) == 3, f"Expected 3 sheets, got {len(sheet_names)}: {sheet_names}"
        
        # Check sheet names
        assert "Plantilla" in sheet_names, "Missing 'Plantilla' sheet"
        assert "Instrucciones" in sheet_names, "Missing 'Instrucciones' sheet"
        assert "Valores Válidos" in sheet_names, "Missing 'Valores Válidos' sheet"
        
        print("SUCCESS: Template has all 3 required sheets")
    
    def test_plantilla_sheet_has_correct_columns(self, auth_headers):
        """Plantilla sheet should have correct column headers"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200
        
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        plantilla_sheet = workbook["Plantilla"]
        
        # Get header row (row 1)
        header_row = [cell.value for cell in plantilla_sheet[1]]
        
        print(f"Plantilla headers: {header_row}")
        
        # Expected columns
        expected_columns = ["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus", 
                          "Tipo Integración", "Gestor", "Categoría"]
        
        for col in expected_columns:
            assert col in header_row, f"Missing column '{col}' in Plantilla sheet"
        
        print("SUCCESS: Plantilla sheet has all required columns")
    
    def test_valores_validos_has_valid_integration_types(self, auth_headers):
        """Valores Válidos sheet should list valid integration types"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200
        
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        valores_sheet = workbook["Valores Válidos"]
        
        # Get all values from the sheet
        all_values = []
        for row in valores_sheet.iter_rows(values_only=True):
            all_values.extend([str(v) for v in row if v])
        
        content_str = " ".join(all_values)
        
        # Check for integration types
        for int_type in ["CR", "LP", "PG", "MP", "TK"]:
            assert int_type in content_str, f"Missing integration type '{int_type}' in Valores Válidos"
        
        print("SUCCESS: Valores Válidos includes all integration types (CR/LP/PG/MP/TK)")
    
    def test_template_requires_authentication(self):
        """Template endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/integrators/import/template")
        
        # Should fail without auth
        assert response.status_code in [401, 403, 422], \
               f"Expected auth error, got {response.status_code}"
        
        print("SUCCESS: Template endpoint requires authentication")


class TestImportModeUpsert:
    """Test POST /api/integrators/import with mode=upsert"""
    
    def test_import_upsert_creates_new_records(self, auth_headers):
        """mode=upsert should create new records"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_UpsertNew1_It75,Integrador,App1,REST,En proceso,CR,
TEST_UpsertNew2_It75,Comercio,App2,MPOS,Certificado,MP,"""
        
        files = {
            'file': ('test_upsert_new.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200, f"Import failed: {response.text}"
        result = response.json()
        
        print(f"Upsert new: status={result['status']}, created={result['success_count']}, updated={result['updated_count']}")
        
        # Should have created 2 records
        assert result["success_count"] >= 2, f"Expected 2 created, got {result['success_count']}"
        assert result["status"] == "success", f"Expected success, got {result['status']}"
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        for name in ["TEST_UpsertNew1_It75", "TEST_UpsertNew2_It75"]:
            intg = next((i for i in integrators if i["name"] == name), None)
            if intg:
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: mode=upsert creates new records correctly")
    
    def test_import_upsert_updates_existing_records(self, auth_headers):
        """mode=upsert should update existing records (composite key: name + integration_type)"""
        # First, create an integrator
        create_payload = {
            "name": "TEST_UpsertUpdate_It75",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": "OriginalApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created = create_response.json()
        integrator_id = created["integrator_id"]
        
        # Now import with upsert mode - same name + integration_type
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_UpsertUpdate_It75,Integrador,UpdatedApp,PG Universal,Certificado,PG,"""
        
        files = {
            'file': ('test_upsert_update.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        print(f"Upsert update: status={result['status']}, created={result['success_count']}, updated={result['updated_count']}")
        
        # Should have updated, not created
        assert result["updated_count"] >= 1, f"Expected 1 updated, got {result['updated_count']}"
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        updated = get_response.json()
        
        assert updated["app_name"] == "UpdatedApp", f"App name should be updated, got {updated['app_name']}"
        assert updated["integration_modality"] == "PG Universal", f"Modality should be updated"
        assert updated["integrator_status"] == "Certificado", f"Status should be updated"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        
        print("SUCCESS: mode=upsert updates existing records correctly")
    
    def test_import_upsert_preserves_certifications(self, auth_headers):
        """mode=upsert should preserve existing certifications when updating"""
        # Create integrator and set a certification
        create_payload = {
            "name": "TEST_UpsertCert_It75",
            "integrator_type": "Integrador",
            "integration_type": "CR",
            "app_name": "CertApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created = create_response.json()
        integrator_id = created["integrator_id"]
        
        # Get and store original certifications
        get_response = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        original_certs = get_response.json().get("certifications", {})
        
        # Import with upsert - update other fields
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_UpsertCert_It75,Integrador,UpdatedCertApp,MPOS,Certificado,CR,"""
        
        files = {
            'file': ('test_upsert_cert.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        
        # Verify certifications are preserved
        get_response = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        updated = get_response.json()
        
        # Certifications should still exist
        assert updated.get("certifications") is not None, "Certifications should be preserved"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        
        print("SUCCESS: mode=upsert preserves certifications")


class TestImportModeInsertOnly:
    """Test POST /api/integrators/import with mode=insert_only"""
    
    def test_import_insert_only_creates_new_records(self, auth_headers):
        """mode=insert_only should create new records"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InsertNew1_It75,Integrador,App1,REST,En proceso,LP,
TEST_InsertNew2_It75,Comercio,App2,Bridge PG,Certificado,TK,"""
        
        files = {
            'file': ('test_insert_new.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'insert_only'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        print(f"Insert only new: status={result['status']}, created={result['success_count']}")
        
        # Should have created 2 records
        assert result["success_count"] >= 2, f"Expected 2 created, got {result['success_count']}"
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        for name in ["TEST_InsertNew1_It75", "TEST_InsertNew2_It75"]:
            intg = next((i for i in integrators if i["name"] == name), None)
            if intg:
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: mode=insert_only creates new records correctly")
    
    def test_import_insert_only_skips_existing_with_error(self, auth_headers):
        """mode=insert_only should skip existing records with duplicate error"""
        # First create an integrator
        create_payload = {
            "name": "TEST_InsertSkip_It75",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": "ExistingApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created = create_response.json()
        integrator_id = created["integrator_id"]
        original_app_name = created["app_name"]
        
        # Try to import same name + integration_type with insert_only mode
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InsertSkip_It75,Integrador,NewApp,MPOS,Certificado,PG,"""
        
        files = {
            'file': ('test_insert_skip.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'insert_only'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        print(f"Insert only skip: status={result['status']}, errors={result['error_count']}, skipped={result['skipped_count']}")
        
        # Should have error for duplicate
        assert result["error_count"] >= 1 or result["skipped_count"] >= 1, \
               "Should report error/skip for duplicate"
        
        # Check for duplicate error type
        errors = result.get("errors", [])
        has_duplicate_error = any(
            e.get("error_type") == "duplicate" for e in errors
        )
        print(f"Errors: {errors}")
        assert has_duplicate_error, "Should have duplicate error type"
        
        # Verify original record was NOT updated
        get_response = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        unchanged = get_response.json()
        
        assert unchanged["app_name"] == original_app_name, \
               f"Original should be unchanged, got {unchanged['app_name']}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        
        print("SUCCESS: mode=insert_only skips existing with duplicate error")


class TestImportUpdatedCountSeparate:
    """Test that updated_count is returned separately from success_count"""
    
    def test_upsert_returns_separate_counts(self, auth_headers):
        """Upsert should return separate success_count (created) and updated_count"""
        # Create one integrator first
        create_payload = {
            "name": "TEST_SeparateCounts_It75",
            "integrator_type": "Integrador",
            "integration_type": "CR",
            "app_name": "OrigApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created = create_response.json()
        
        # Import with 1 existing (to update) and 1 new (to create)
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_SeparateCounts_It75,Integrador,UpdatedApp,MPOS,Certificado,CR,
TEST_BrandNew_It75,Comercio,BrandNewApp,PG Universal,En proceso,PG,"""
        
        files = {
            'file': ('test_separate.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        print(f"Separate counts: created={result['success_count']}, updated={result['updated_count']}")
        
        # Should have 1 created and 1 updated
        assert "updated_count" in result, "Response must include updated_count"
        assert result["success_count"] >= 1, "Should have at least 1 created"
        assert result["updated_count"] >= 1, "Should have at least 1 updated"
        
        # Message should mention both
        message = result.get("message", "")
        assert "actualizado" in message.lower() or "creado" in message.lower(), \
               f"Message should mention created/updated: {message}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{created['integrator_id']}", headers=auth_headers)
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_BrandNew_It75"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: updated_count is returned separately from success_count")


class TestGestorValidation:
    """Test gestor validation against users DB"""
    
    def test_invalid_gestor_returns_error(self, auth_headers):
        """Import with non-existent gestor should return validation error"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InvalidGestor_It75,Integrador,App1,REST,En proceso,CR,NonExistentGestor12345"""
        
        files = {
            'file': ('test_gestor.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have error
        assert result["error_count"] >= 1, "Should report error for invalid gestor"
        
        errors = result.get("errors", [])
        has_gestor_error = any(
            "gestor" in e.get("column", "").lower() or 
            "gestor" in e.get("message", "").lower()
            for e in errors
        )
        
        print(f"Errors: {errors}")
        assert has_gestor_error, "Should have error about gestor validation"
        
        print("SUCCESS: Invalid gestor correctly rejected")


class TestIntegrationTypeValidation:
    """Test integration_type validation (CR/LP/PG/MP/TK only)"""
    
    def test_invalid_integration_type_returns_error(self, auth_headers):
        """Import with invalid integration_type should return validation error"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InvalidIntType_It75,Integrador,App1,REST,En proceso,INVALID_TYPE,"""
        
        files = {
            'file': ('test_int_type.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        data = {'mode': 'upsert'}
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files,
            data=data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have error
        assert result["error_count"] >= 1, "Should report error for invalid integration_type"
        
        errors = result.get("errors", [])
        has_type_error = any(
            "integración" in e.get("column", "").lower() or 
            "integración" in e.get("message", "").lower() or
            "tipo" in e.get("message", "").lower()
            for e in errors
        )
        
        print(f"Errors: {errors}")
        assert has_type_error, "Should have error about integration_type validation"
        
        print("SUCCESS: Invalid integration_type correctly rejected")
    
    def test_valid_integration_types_accepted(self, auth_headers):
        """All valid integration types (CR/LP/PG/MP/TK) should be accepted"""
        valid_types = ['CR', 'LP', 'PG', 'MP', 'TK']
        created_ids = []
        
        for int_type in valid_types:
            csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_ValidType_{int_type}_It75,Integrador,App{int_type},REST,En proceso,{int_type},"""
            
            files = {
                'file': (f'test_{int_type}.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
            }
            data = {'mode': 'upsert'}
            headers = {"Authorization": auth_headers["Authorization"]}
            
            response = requests.post(
                f"{BASE_URL}/api/integrators/import",
                headers=headers,
                files=files,
                data=data
            )
            
            assert response.status_code == 200
            result = response.json()
            
            assert result["error_count"] == 0, f"Type {int_type} should be accepted, got errors: {result.get('errors')}"
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        for int_type in valid_types:
            intg = next((i for i in integrators if i["name"] == f"TEST_ValidType_{int_type}_It75"), None)
            if intg:
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print(f"SUCCESS: All valid integration types ({valid_types}) accepted")


class TestDefaultMode:
    """Test that default mode is upsert"""
    
    def test_import_without_mode_uses_upsert(self, auth_headers):
        """Import without explicit mode should use upsert (default)"""
        # Create an integrator
        create_payload = {
            "name": "TEST_DefaultMode_It75",
            "integrator_type": "Integrador",
            "integration_type": "CR",
            "app_name": "OrigApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created = create_response.json()
        
        # Import without mode parameter - should default to upsert
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_DefaultMode_It75,Integrador,UpdatedNoMode,MPOS,Certificado,CR,"""
        
        files = {
            'file': ('test_default.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        # No mode parameter
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200
        result = response.json()
        
        print(f"Default mode: status={result['status']}, updated={result['updated_count']}")
        
        # Should update (upsert behavior), not create new
        assert result["updated_count"] >= 1, "Default should use upsert mode"
        
        # Verify update happened
        get_response = requests.get(f"{BASE_URL}/api/integrators/{created['integrator_id']}", headers=auth_headers)
        updated = get_response.json()
        
        assert updated["app_name"] == "UpdatedNoMode", f"Should be updated, got {updated['app_name']}"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{created['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Default mode is upsert")
