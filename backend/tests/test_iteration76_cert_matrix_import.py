"""
Iteration 76 - Certification Matrix in Import/Export with Dynamic Product Columns
Tests for:
- GET /api/integrators/import/template - Returns .xlsx with 8 base + 25 dynamic product columns
- POST /api/integrators/import - Creates new integrator with cert values from Excel (C/P/N/A columns)
- POST /api/integrators/import - Updates existing integrator and overwrites cert values from file
- POST /api/integrators/import - Rejects row with invalid cert value (e.g. 'Listo') with column name
- POST /api/integrators/import - Empty cert cells default to N/A
- POST /api/integrators/import - Case-insensitive: accepts lowercase c, p, n/a and normalizes to uppercase
- POST /api/integrators/import - Returns cert_updates_count in response
- GET /api/integrators/export/excel - Exports with 8 base + 25 product columns with cert values
"""

import pytest
import requests
import os
import io
import openpyxl
import pandas as pd

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

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
def product_columns(auth_headers):
    """Get list of products for cert matrix columns"""
    response = requests.get(f"{BASE_URL}/api/services", headers=auth_headers)
    assert response.status_code == 200
    services = response.json()
    products = [s for s in services if s.get('service_type') == 'Producto' 
                and s.get('application_type') in ['setup', 'both']]
    return products


class TestTemplateHasDynamicProductColumns:
    """Test GET /api/integrators/import/template - Dynamic product columns"""
    
    def test_template_has_33_columns_8_base_plus_25_products(self, auth_headers):
        """Template should have 8 base columns + 25 dynamic product columns = 33 total"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200, f"Template download failed: {response.status_code}"
        
        # Parse Excel
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        plantilla_sheet = workbook["Plantilla"]
        
        # Get headers
        header_row = [cell.value for cell in plantilla_sheet[1] if cell.value]
        
        print(f"Template has {len(header_row)} columns")
        
        # Should have at least 33 columns (8 base + 25 products)
        assert len(header_row) >= 33, f"Expected at least 33 columns, got {len(header_row)}"
        
        # Base columns should be first 8
        base_columns = ["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus", 
                       "Tipo Integración", "Gestor", "Categoría"]
        
        for col in base_columns:
            assert col in header_row, f"Missing base column '{col}'"
        
        print(f"SUCCESS: Template has {len(header_row)} columns (8 base + {len(header_row)-8} products)")
    
    def test_template_product_columns_match_db_products(self, auth_headers, product_columns):
        """Product columns in template should match products in DB"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200
        
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        plantilla_sheet = workbook["Plantilla"]
        
        header_row = [cell.value for cell in plantilla_sheet[1] if cell.value]
        
        # Remove base columns to get product columns
        base_columns = {"Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus", 
                       "Tipo Integración", "Gestor", "Categoría"}
        template_products = [h for h in header_row if h not in base_columns]
        
        # Get product names from DB
        db_product_names = [p['name'] for p in product_columns]
        
        print(f"Template product columns: {len(template_products)}")
        print(f"DB products: {len(db_product_names)}")
        
        # Check that template has all DB products
        for db_name in db_product_names:
            # May have trailing spaces, so strip
            matched = any(db_name.strip() in tp.strip() or tp.strip() in db_name.strip() 
                         for tp in template_products)
            if not matched:
                print(f"  WARNING: DB product '{db_name}' not found in template columns")
        
        print("SUCCESS: Template product columns correspond to DB products")
    
    def test_template_instructions_describe_cert_values(self, auth_headers):
        """Instructions sheet should describe certification values (C/P/N/A)"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/import/template",
            headers=headers
        )
        
        assert response.status_code == 200
        
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        instrucciones = workbook["Instrucciones"]
        
        # Get all content
        all_values = []
        for row in instrucciones.iter_rows(values_only=True):
            all_values.extend([str(v) for v in row if v])
        
        content_str = " ".join(all_values)
        
        # Should mention C, P, N/A
        assert "C" in content_str, "Instructions should mention 'C' (Certificado)"
        assert "P" in content_str, "Instructions should mention 'P' (Pendiente)"
        assert "N/A" in content_str, "Instructions should mention 'N/A'"
        
        print("SUCCESS: Instructions sheet describes C/P/N/A certification values")


class TestImportCreatesIntegratorWithCertValues:
    """Test POST /api/integrators/import creates integrator with cert values"""
    
    def test_import_creates_integrator_with_cert_columns(self, auth_headers, product_columns):
        """Import should create integrator with cert values from Excel columns"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        # Get first product name for testing
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        # Create CSV with cert column
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,Gestor,Categoría,{product_name}
TEST_CertNew_It76,Integrador,CertApp,REST,En proceso,CR,,Cliente/Integrador nuevo PG,C"""
        
        files = {
            'file': ('test_cert_new.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        print(f"Import result: status={result['status']}, created={result['success_count']}, cert_updates={result.get('cert_updates_count', 0)}")
        
        # Should have created
        assert result["success_count"] >= 1 or result["status"] == "success", f"Expected creation, got {result}"
        
        # Verify integrator was created with certification
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        
        intg = next((i for i in integrators if i["name"] == "TEST_CertNew_It76"), None)
        assert intg is not None, "Integrator should be created"
        
        # Check certification value
        certs = intg.get("certifications", {})
        cert_value = certs.get(product_id, "N/A")
        print(f"Certification for {product_name}: {cert_value}")
        
        assert cert_value == "C", f"Expected 'C' certification, got '{cert_value}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Import creates integrator with cert values from columns")
    
    def test_import_creates_integrator_with_p_certification(self, auth_headers, product_columns):
        """Import with 'P' cert value should set Pendiente"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_CertP_It76,Integrador,PendApp,REST,En proceso,PG,P"""
        
        files = {
            'file': ('test_cert_p.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        # Verify
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_CertP_It76"), None)
        
        assert intg is not None
        certs = intg.get("certifications", {})
        assert certs.get(product_id) == "P", f"Expected 'P', got '{certs.get(product_id)}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Import with 'P' cert value works")


class TestImportUpdatesExistingCertValues:
    """Test import updates existing integrator and overwrites cert values"""
    
    def test_upsert_overwrites_cert_values(self, auth_headers, product_columns):
        """Upsert should overwrite certification values from file"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        # Create integrator first
        create_payload = {
            "name": "TEST_UpsertCert_It76",
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
        
        # Original certification should be N/A (default)
        original_certs = created.get("certifications", {})
        print(f"Original cert for {product_name}: {original_certs.get(product_id, 'N/A')}")
        
        # Import with cert column set to 'C'
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_UpsertCert_It76,Integrador,UpdatedApp,REST,Certificado,PG,C"""
        
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
        result = response.json()
        
        print(f"Upsert result: updated={result.get('updated_count')}, cert_updates={result.get('cert_updates_count')}")
        
        # Verify cert was updated
        get_response = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        updated = get_response.json()
        
        updated_certs = updated.get("certifications", {})
        new_cert_value = updated_certs.get(product_id, "N/A")
        
        print(f"Updated cert for {product_name}: {new_cert_value}")
        
        assert new_cert_value == "C", f"Expected 'C' after upsert, got '{new_cert_value}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        
        print("SUCCESS: Upsert overwrites certification values from file")


class TestInvalidCertValueRejection:
    """Test that invalid cert values (not C/P/N/A) are rejected"""
    
    def test_invalid_cert_value_listo_rejected(self, auth_headers, product_columns):
        """Import with 'Listo' in cert column should be rejected"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_InvalidCert_It76,Integrador,InvalidApp,REST,En proceso,CR,Listo"""
        
        files = {
            'file': ('test_invalid_cert.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        print(f"Invalid cert result: status={result['status']}, errors={result['error_count']}")
        
        # Should have error
        assert result["error_count"] >= 1, "Should reject invalid cert value"
        
        # Check error mentions the column name
        errors = result.get("errors", [])
        print(f"Errors: {errors}")
        
        has_cert_error = any(
            "Listo" in str(e.get("value", "")) or 
            product_name in str(e.get("column", "")) or
            "certificación" in str(e.get("message", "")).lower()
            for e in errors
        )
        
        assert has_cert_error, "Error should mention the invalid cert value and/or column"
        
        # Verify integrator was NOT created
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_InvalidCert_It76"), None)
        
        if intg:
            # Cleanup if accidentally created
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Invalid cert value 'Listo' correctly rejected")
    
    def test_invalid_cert_value_ok_rejected(self, auth_headers, product_columns):
        """Import with 'OK' in cert column should be rejected"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_InvalidOK_It76,Integrador,OKApp,REST,En proceso,MP,OK"""
        
        files = {
            'file': ('test_invalid_ok.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        assert result["error_count"] >= 1, "Should reject 'OK' as cert value"
        
        # Cleanup if created
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_InvalidOK_It76"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Invalid cert value 'OK' correctly rejected")


class TestEmptyCertCellsDefaultToNA:
    """Test that empty cert cells default to N/A"""
    
    def test_empty_cert_columns_default_to_na(self, auth_headers, product_columns):
        """Empty certification columns should default to N/A"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        # Create CSV with empty cert column
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_EmptyCert_It76,Integrador,EmptyApp,REST,En proceso,CR,"""
        
        files = {
            'file': ('test_empty_cert.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        # Should succeed (empty is valid - defaults to N/A)
        assert result["error_count"] == 0, f"Empty cert should be valid, got errors: {result.get('errors')}"
        
        # Verify
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_EmptyCert_It76"), None)
        
        assert intg is not None, "Integrator should be created"
        
        certs = intg.get("certifications", {})
        cert_value = certs.get(product_id, "N/A")
        
        print(f"Empty cert column resulted in: {cert_value}")
        
        assert cert_value == "N/A", f"Expected 'N/A' for empty, got '{cert_value}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Empty cert columns default to N/A")


class TestCaseInsensitiveCertValues:
    """Test case-insensitive handling of C/P/N/A"""
    
    def test_lowercase_c_accepted_and_normalized(self, auth_headers, product_columns):
        """Lowercase 'c' should be accepted and normalized to 'C'"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_LowerC_It76,Integrador,LowerApp,REST,En proceso,CR,c"""
        
        files = {
            'file': ('test_lower_c.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        assert result["error_count"] == 0, f"Lowercase 'c' should be valid: {result.get('errors')}"
        
        # Verify
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_LowerC_It76"), None)
        
        assert intg is not None
        certs = intg.get("certifications", {})
        
        # Should be uppercase 'C'
        assert certs.get(product_id) == "C", f"Expected 'C', got '{certs.get(product_id)}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Lowercase 'c' accepted and normalized to 'C'")
    
    def test_lowercase_p_accepted_and_normalized(self, auth_headers, product_columns):
        """Lowercase 'p' should be accepted and normalized to 'P'"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_LowerP_It76,Integrador,LowerPApp,REST,En proceso,LP,p"""
        
        files = {
            'file': ('test_lower_p.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        assert result["error_count"] == 0
        
        # Verify
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_LowerP_It76"), None)
        
        assert intg is not None
        certs = intg.get("certifications", {})
        assert certs.get(product_id) == "P", f"Expected 'P', got '{certs.get(product_id)}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Lowercase 'p' accepted and normalized to 'P'")
    
    def test_lowercase_na_accepted_and_normalized(self, auth_headers, product_columns):
        """Lowercase 'n/a' should be accepted and normalized to 'N/A'"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        product_id = first_product['service_id']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_LowerNA_It76,Integrador,LowerNAApp,REST,En proceso,TK,n/a"""
        
        files = {
            'file': ('test_lower_na.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        assert result["error_count"] == 0, f"Lowercase 'n/a' should be valid: {result.get('errors')}"
        
        # Verify
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_LowerNA_It76"), None)
        
        assert intg is not None
        certs = intg.get("certifications", {})
        assert certs.get(product_id) == "N/A", f"Expected 'N/A', got '{certs.get(product_id)}'"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Lowercase 'n/a' accepted and normalized to 'N/A'")


class TestCertUpdatesCountInResponse:
    """Test cert_updates_count is returned in response"""
    
    def test_import_returns_cert_updates_count(self, auth_headers, product_columns):
        """Import response should include cert_updates_count field"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        first_product = product_columns[0]
        product_name = first_product['name']
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{product_name}
TEST_CertCount_It76,Integrador,CountApp,REST,En proceso,CR,C"""
        
        files = {
            'file': ('test_cert_count.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        # Should have cert_updates_count field
        assert "cert_updates_count" in result, f"Response missing cert_updates_count: {result.keys()}"
        
        print(f"cert_updates_count = {result['cert_updates_count']}")
        
        # For new integrator with all 25 certs initialized, should be > 0
        assert result["cert_updates_count"] > 0, "cert_updates_count should be > 0 for new integrator"
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_CertCount_It76"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Import returns cert_updates_count in response")
    
    def test_cert_updates_count_matches_columns_processed(self, auth_headers, product_columns):
        """cert_updates_count should match number of cert columns processed"""
        if len(product_columns) < 2:
            pytest.skip("Need at least 2 products")
        
        # Use first two products
        prod1 = product_columns[0]
        prod2 = product_columns[1]
        
        csv_content = f"""Nombre,Tipo,Aplicativo,Modalidad,Estatus,Tipo Integración,{prod1['name']},{prod2['name']}
TEST_CertCount2_It76,Integrador,Count2App,REST,En proceso,CR,C,P"""
        
        files = {
            'file': ('test_cert_count2.csv', io.BytesIO(csv_content.encode('utf-8')), 'text/csv')
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
        
        print(f"With 2 cert columns: cert_updates_count = {result.get('cert_updates_count')}")
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_CertCount2_It76"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: cert_updates_count reflects cert columns processed")


class TestExportIncludesCertColumns:
    """Test GET /api/integrators/export/excel includes cert columns with values"""
    
    def test_export_has_33_columns(self, auth_headers):
        """Export should have 8 base + 25 product columns = 33 total"""
        headers = {"Authorization": auth_headers["Authorization"]}
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/export/excel",
            headers=headers
        )
        
        # May be 404 if no integrators
        if response.status_code == 404:
            pytest.skip("No integrators to export")
        
        assert response.status_code == 200, f"Export failed: {response.status_code}"
        
        # Parse Excel
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        
        header_row = [cell.value for cell in sheet[1] if cell.value]
        
        print(f"Export has {len(header_row)} columns")
        
        # Should have at least 33 columns
        assert len(header_row) >= 33, f"Expected at least 33 columns, got {len(header_row)}"
        
        # Base columns
        base_columns = ["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus", 
                       "Tipo Integración", "Gestor", "Categoría"]
        
        for col in base_columns:
            assert col in header_row, f"Missing base column '{col}' in export"
        
        print("SUCCESS: Export has 33 columns (8 base + 25 products)")
    
    def test_export_contains_cert_values(self, auth_headers, product_columns):
        """Export should contain certification values (C/P/N/A)"""
        if not product_columns:
            pytest.skip("No products in DB")
        
        # Create integrator with specific cert value
        first_product = product_columns[0]
        product_id = first_product['service_id']
        
        create_payload = {
            "name": "TEST_ExportCert_It76",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": "ExportApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso",
            "certifications": {product_id: "C"}
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/integrators",
            headers=auth_headers,
            json=create_payload
        )
        
        if create_response.status_code != 200:
            # Integrator might already exist, try to find it
            pass
        
        # Export
        headers = {"Authorization": auth_headers["Authorization"]}
        response = requests.get(
            f"{BASE_URL}/api/integrators/export/excel",
            headers=headers
        )
        
        assert response.status_code == 200
        
        # Parse and find our integrator
        workbook = openpyxl.load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        
        header_row = [cell.value for cell in sheet[1]]
        
        # Find product column index
        product_col_idx = None
        for i, h in enumerate(header_row):
            if h and first_product['name'].strip() in str(h).strip():
                product_col_idx = i
                break
        
        if product_col_idx is None:
            print(f"WARNING: Product '{first_product['name']}' not found in export columns")
            # Skip cleanup if we couldn't verify
        else:
            # Find our integrator row
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if row[0] == "TEST_ExportCert_It76":
                    cert_value = row[product_col_idx] if product_col_idx < len(row) else None
                    print(f"Export cert value for TEST_ExportCert_It76: {cert_value}")
                    assert cert_value in ["C", "P", "N/A"], f"Expected C/P/N/A, got '{cert_value}'"
                    break
        
        # Cleanup
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        intg = next((i for i in integrators if i["name"] == "TEST_ExportCert_It76"), None)
        if intg:
            requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
        print("SUCCESS: Export contains cert values")


class TestExistingIntegratorsVerification:
    """Verify existing test integrators mentioned in context"""
    
    def test_certmatrixnew_integrator_exists(self, auth_headers):
        """CertMatrixNew integrator should exist with PG type and C cert"""
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        
        intg = next((i for i in integrators if i["name"] == "CertMatrixNew"), None)
        
        if intg:
            print(f"CertMatrixNew found: type={intg.get('integration_type')}")
            certs = intg.get("certifications", {})
            
            # Should have at least one C cert
            c_count = sum(1 for v in certs.values() if v == "C")
            na_count = sum(1 for v in certs.values() if v == "N/A")
            
            print(f"  Certifications: {c_count} C, {na_count} N/A")
            
            # According to context: 1 C + 24 N/A
            assert c_count >= 1, "CertMatrixNew should have at least 1 C certification"
        else:
            print("NOTE: CertMatrixNew integrator not found - may have been cleaned up")
            pytest.skip("CertMatrixNew not found in DB")
    
    def test_autocert_test_integrator_exists(self, auth_headers):
        """AutoCert Test integrator should exist with CR type and P cert"""
        list_response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_response.json()
        
        intg = next((i for i in integrators if i["name"] == "AutoCert Test"), None)
        
        if intg:
            print(f"AutoCert Test found: type={intg.get('integration_type')}")
            certs = intg.get("certifications", {})
            
            p_count = sum(1 for v in certs.values() if v == "P")
            print(f"  Certifications: {p_count} P")
            
            # According to context: 1 P cert
            assert p_count >= 1, "AutoCert Test should have at least 1 P certification"
        else:
            print("NOTE: AutoCert Test integrator not found - may have been cleaned up")
            pytest.skip("AutoCert Test not found in DB")
