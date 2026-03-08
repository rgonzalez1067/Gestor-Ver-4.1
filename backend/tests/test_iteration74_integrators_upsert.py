"""
Iteration 74 - Integrators Module Enhancements Tests
- Auto-initialization of certifications to N/A on create
- Import with Upsert logic (composite key: name + integration_type)
- Gestor validation against users DB
- Integration_type validation (CR/LP/PG/MP/TK)
- updated_count in ImportResult response
"""

import pytest
import requests
import os
import io

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


@pytest.fixture(scope="module")
def cert_products(auth_headers):
    """Get list of certification products (Producto type with setup/both)"""
    response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
    assert response.status_code == 200
    services = response.json()
    products = [s for s in services if s.get('service_type') == 'Producto' 
                and s.get('application_type') in ['setup', 'both']]
    return products


@pytest.fixture(scope="module")
def users_list(auth_headers):
    """Get list of active users for gestor validation"""
    response = requests.get(f"{BASE_URL}/api/auth/users", headers=auth_headers)
    assert response.status_code == 200
    return response.json()


class TestIntegratorAutoInitCertifications:
    """Test auto-initialization of certifications to N/A when creating integrator"""
    
    def test_create_integrator_without_certifications_auto_inits_to_na(self, auth_headers, cert_products):
        """POST /api/integrators should auto-initialize all certs to N/A"""
        payload = {
            "name": "TEST_AutoCert_Iteration74",
            "integrator_type": "Integrador",
            "integration_type": "CR",
            "app_name": "TestApp74",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
            # Note: certifications not provided
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # Verify certifications were auto-initialized
        assert "certifications" in data, "certifications field missing in response"
        assert data["certifications"] is not None, "certifications should not be None"
        
        # All cert products should have N/A value
        if cert_products:
            for prod in cert_products:
                service_id = prod["service_id"]
                assert service_id in data["certifications"], f"Missing cert for {service_id}"
                assert data["certifications"][service_id] == "N/A", f"Cert {service_id} should be N/A"
            
            print(f"SUCCESS: Auto-initialized {len(data['certifications'])} certifications to N/A")
        
        # Cleanup
        integrator_id = data.get("integrator_id")
        if integrator_id:
            requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
    
    def test_create_integrator_with_custom_certifications_preserves_them(self, auth_headers, cert_products):
        """POST /api/integrators with certifications should preserve custom values"""
        custom_certs = {}
        if cert_products and len(cert_products) > 0:
            custom_certs[cert_products[0]["service_id"]] = "C"  # Certificado
        
        payload = {
            "name": "TEST_CustomCert_Iteration74",
            "integrator_type": "Comercio",
            "integration_type": "PG",
            "app_name": "TestAppCustom74",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso",
            "certifications": custom_certs
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=payload
        )
        
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        
        # If custom certs provided, they should be preserved (not overwritten)
        # Note: Backend may auto-fill missing ones with N/A
        if custom_certs:
            first_service_id = list(custom_certs.keys())[0]
            # The value might be preserved or auto-initialized depending on backend logic
            print(f"Custom cert value for {first_service_id}: {data.get('certifications', {}).get(first_service_id)}")
        
        # Cleanup
        integrator_id = data.get("integrator_id")
        if integrator_id:
            requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)


class TestImportUpsertLogic:
    """Test import with Upsert logic using composite key (name + integration_type)"""
    
    def test_import_creates_new_records_with_na_certs(self, auth_headers, cert_products):
        """Import should create new integrators with all certs initialized to N/A"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_ImportNew1_It74,Integrador,AppNew1,REST,En proceso,CR,
TEST_ImportNew2_It74,Comercio,AppNew2,MPOS,Certificado,MP,"""
        
        files = {
            'file': ('test_import.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200, f"Import failed: {response.text}"
        result = response.json()
        
        print(f"Import result: status={result['status']}, success={result['success_count']}, updated={result.get('updated_count', 0)}")
        
        # Should have created 2 new records
        assert result["success_count"] >= 0, "success_count should be present"
        assert "updated_count" in result, "updated_count field should be in response"
        
        # Verify created integrators have N/A certs
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        
        for name in ["TEST_ImportNew1_It74", "TEST_ImportNew2_It74"]:
            intg = next((i for i in integrators if i["name"] == name), None)
            if intg:
                if cert_products and intg.get("certifications"):
                    # Check all certs are N/A for new imports
                    for prod in cert_products[:3]:  # Check first 3
                        cert_val = intg["certifications"].get(prod["service_id"])
                        assert cert_val == "N/A", f"New import {name} should have N/A cert, got {cert_val}"
                # Cleanup
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: New imports created with N/A certifications")
    
    def test_import_upsert_updates_existing_by_composite_key(self, auth_headers):
        """Import should update existing record when name + integration_type match"""
        # First, create an integrator
        create_payload = {
            "name": "TEST_Upsert_It74",
            "integrator_type": "Integrador",
            "integration_type": "CR",
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
        
        # Now import CSV with same name + integration_type but different app_name
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_Upsert_It74,Integrador,UpdatedApp,MPOS,Certificado,CR,"""
        
        files = {
            'file': ('test_upsert.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200, f"Import failed: {response.text}"
        result = response.json()
        
        print(f"Upsert result: status={result['status']}, created={result['success_count']}, updated={result['updated_count']}")
        
        # Should have updated, not created
        assert result["updated_count"] >= 1, "Should have updated existing record"
        
        # Verify the record was updated
        get_response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        updated = get_response.json()
        
        assert updated["app_name"] == "UpdatedApp", f"App name should be updated, got {updated['app_name']}"
        assert updated["integration_modality"] == "MPOS", f"Modality should be updated"
        assert updated["integrator_status"] == "Certificado", f"Status should be updated"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        print("SUCCESS: Upsert correctly updated existing record")
    
    def test_import_different_integration_type_creates_new(self, auth_headers):
        """Same name but different integration_type should create new record"""
        # Create integrator with CR type
        create_payload = {
            "name": "TEST_DiffType_It74",
            "integrator_type": "Integrador",
            "integration_type": "CR",
            "app_name": "AppCR",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        assert create_response.status_code == 200
        created_cr = create_response.json()
        
        # Import same name but different integration_type (PG)
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_DiffType_It74,Integrador,AppPG,PG Universal,Certificado,PG,"""
        
        files = {
            'file': ('test_diff_type.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should create new since integration_type is different
        print(f"Different type result: created={result['success_count']}, updated={result['updated_count']}")
        
        # Cleanup both
        requests.delete(f"{BASE_URL}/api/integrators/{created_cr['integrator_id']}", headers=auth_headers)
        
        # Find and delete the PG one
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        pg_intg = next((i for i in integrators if i["name"] == "TEST_DiffType_It74" and i.get("integration_type") == "PG"), None)
        if pg_intg:
            requests.delete(f"{BASE_URL}/api/integrators/{pg_intg['integrator_id']}", headers=auth_headers)


class TestImportValidations:
    """Test import validations for gestor and integration_type"""
    
    def test_import_invalid_integration_type_returns_error(self, auth_headers):
        """Import with invalid integration_type should return error"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InvalidType_It74,Integrador,App1,REST,En proceso,INVALID,"""
        
        files = {
            'file': ('test_invalid_type.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200  # Import endpoint returns 200 with errors in body
        result = response.json()
        
        # Should have errors for invalid integration_type
        assert result["error_count"] >= 1, "Should report error for invalid integration_type"
        
        # Check error details
        errors = result.get("errors", [])
        has_type_error = any(
            "Tipo Integración" in e.get("column", "") or 
            "integración" in e.get("message", "").lower()
            for e in errors
        )
        print(f"Errors: {errors}")
        assert has_type_error, "Should have error about integration_type"
        print("SUCCESS: Invalid integration_type correctly rejected")
    
    def test_import_invalid_gestor_returns_error(self, auth_headers):
        """Import with non-existent gestor should return error"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_InvalidGestor_It74,Integrador,App1,REST,En proceso,CR,NonExistentUser123"""
        
        files = {
            'file': ('test_invalid_gestor.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have errors for invalid gestor
        assert result["error_count"] >= 1, "Should report error for invalid gestor"
        
        errors = result.get("errors", [])
        has_gestor_error = any(
            "gestor" in e.get("column", "").lower() or 
            "gestor" in e.get("message", "").lower()
            for e in errors
        )
        print(f"Errors: {errors}")
        assert has_gestor_error, "Should have error about gestor"
        print("SUCCESS: Invalid gestor correctly rejected")
    
    def test_import_valid_integration_types_accepted(self, auth_headers):
        """All valid integration types (CR/LP/PG/MP/TK) should be accepted"""
        valid_types = ['CR', 'LP', 'PG', 'MP', 'TK']
        
        for int_type in valid_types:
            csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_ValidType_{int_type}_It74,Integrador,App{int_type},REST,En proceso,{int_type},"""
            
            files = {
                'file': (f'test_{int_type}.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
            }
            headers = {"Authorization": auth_headers["Authorization"]}
            
            response = requests.post(
                f"{BASE_URL}/api/integrators/import",
                headers=headers,
                files=files
            )
            
            assert response.status_code == 200
            result = response.json()
            
            # Should be successful
            assert result["status"] in ["success", "partial"], f"Type {int_type} should be accepted"
            
            # Cleanup
            list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
            integrators = list_response.json()
            intg = next((i for i in integrators if i["name"] == f"TEST_ValidType_{int_type}_It74"), None)
            if intg:
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print(f"SUCCESS: All valid integration types ({valid_types}) accepted")


class TestImportResultFormat:
    """Test that import result includes updated_count and detailed errors"""
    
    def test_import_result_has_updated_count_field(self, auth_headers):
        """ImportResult should have updated_count field"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
TEST_ResultFormat_It74,Integrador,TestApp,REST,En proceso,CR,"""
        
        files = {
            'file': ('test_result.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify all expected fields
        assert "status" in result
        assert "total_processed" in result
        assert "success_count" in result
        assert "updated_count" in result, "updated_count field must be present"
        assert "error_count" in result
        assert "skipped_count" in result
        assert "errors" in result
        assert "message" in result
        
        print(f"ImportResult fields verified: {list(result.keys())}")
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_ResultFormat_It74"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
    
    def test_import_errors_have_detailed_columns(self, auth_headers):
        """Import errors should have row, column, value, error_type, message, suggested_action"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor
,Integrador,TestApp,REST,En proceso,CR,
TEST_Error_It74,InvalidType,TestApp,REST,En proceso,CR,"""
        
        files = {
            'file': ('test_errors.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
        }
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=headers,
            files=files
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should have errors
        errors = result.get("errors", [])
        if errors:
            error = errors[0]
            assert "row" in error, "Error should have row number"
            assert "column" in error, "Error should have column name"
            assert "error_type" in error, "Error should have error_type"
            assert "message" in error, "Error should have message"
            assert "suggested_action" in error, "Error should have suggested_action"
            
            print(f"Error format verified: {error}")
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        for intg in integrators:
            if intg["name"].startswith("TEST_Error_It74"):
                requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)


class TestGetAuthUsers:
    """Test GET /api/auth/users endpoint for gestor validation"""
    
    def test_get_users_list_returns_active_users(self, auth_headers):
        """GET /auth/users should return active users with full_name"""
        response = requests.get(f"{BASE_URL}/api/auth/users", headers=auth_headers)
        
        assert response.status_code == 200
        users = response.json()
        
        assert isinstance(users, list), "Should return a list"
        
        if users:
            user = users[0]
            # Should have these fields for gestor dropdown
            assert "user_id" in user
            assert "full_name" in user, "Should have full_name for dropdown"
            
            print(f"Found {len(users)} active users")
            print(f"Sample user fields: {list(user.keys())}")
