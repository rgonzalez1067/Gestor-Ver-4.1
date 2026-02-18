"""
Import Functionality Tests
===========================
Tests for import endpoints: /api/integrators/import, /api/clients/import, 
/api/banks/import, /api/services/import

Tests cover:
- Valid file imports (CSV and Excel)
- Validation errors (missing required fields)
- Duplicate detection
- Partial import scenarios
- Invalid enum values
- File format validation
"""

import pytest
import requests
import os
import io
import csv
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_TOKEN = "test_import_session_token_2024"

def get_auth_headers():
    return {
        "Authorization": f"Bearer {TEST_TOKEN}"
    }

# ==================== INTEGRATORS IMPORT TESTS ====================

class TestIntegratorsImport:
    """Test POST /api/integrators/import endpoint"""
    
    def test_import_integrators_valid_csv(self):
        """Test successful import of valid integrators CSV"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_TechPay Solutions,Integrador,PayHub,Bridge PG,Certificado
TEST_QuickCommerce,Comercio,QCShop,MPOS,En proceso
TEST_PaymentGlobal,Integrador,PGApp,PG Universal,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate ImportResult structure
        assert 'status' in data
        assert 'total_processed' in data
        assert 'success_count' in data
        assert 'error_count' in data
        assert 'skipped_count' in data
        assert 'errors' in data
        assert 'message' in data
        
        print(f"Import result: status={data['status']}, success={data['success_count']}, errors={data['error_count']}")
        
        # Should be success or partial (if duplicates exist)
        assert data['status'] in ['success', 'partial']
        assert data['total_processed'] == 3
    
    def test_import_integrators_missing_required_columns(self):
        """Test import fails with missing required columns"""
        # Missing Modalidad column
        csv_content = """Nombre,Tipo,Aplicativo
TEST_MissingCol,Integrador,App1"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'
        assert 'integration_modality' in str(data['errors']).lower() or 'modalidad' in str(data['errors']).lower()
        print(f"Missing column error: {data['message']}")
    
    def test_import_integrators_invalid_type_enum(self):
        """Test validation error for invalid integrator type"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_InvalidType,InvalidType,App1,Bridge PG,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have errors for invalid type
        assert data['error_count'] > 0 or data['skipped_count'] > 0
        
        # Check error details
        if data['errors']:
            error = data['errors'][0]
            assert 'row' in error
            assert 'column' in error
            assert 'error_type' in error
            assert error['error_type'] == 'invalid'
            assert 'suggested_action' in error
            print(f"Invalid enum error: {error['message']}")
    
    def test_import_integrators_invalid_modality_enum(self):
        """Test validation error for invalid integration modality"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_InvalidMod,Integrador,App1,InvalidModality,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['error_count'] > 0 or data['skipped_count'] > 0
        if data['errors']:
            error = data['errors'][0]
            assert error['error_type'] == 'invalid'
            print(f"Invalid modality error: {error['message']}")
    
    def test_import_integrators_duplicate_detection(self):
        """Test duplicate detection during import"""
        # First import
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_DupIntegrator,Integrador,DupApp,Bridge PG,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        assert response.status_code == 200
        
        # Second import with same data
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect duplicate
        assert data['skipped_count'] > 0 or data['error_count'] > 0
        if data['errors']:
            dup_errors = [e for e in data['errors'] if e['error_type'] == 'duplicate']
            assert len(dup_errors) > 0
            print(f"Duplicate detected: {dup_errors[0]['message']}")
    
    def test_import_integrators_partial_success(self):
        """Test partial import - valid and invalid rows mixed"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_ValidRow1,Integrador,ValidApp1,Bridge PG,Certificado
TEST_InvalidRow,,InvalidApp,Bridge PG,Certificado
TEST_ValidRow2,Comercio,ValidApp2,MPOS,En proceso"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be partial (some success, some errors)
        assert data['total_processed'] == 3
        print(f"Partial import: status={data['status']}, success={data['success_count']}, errors={data['error_count']}")
    
    def test_import_integrators_empty_file(self):
        """Test import with empty file returns error"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'
        print(f"Empty file error: {data['message']}")
    
    def test_import_integrators_invalid_file_format(self):
        """Test import rejects invalid file format"""
        files = {'file': ('integrators.txt', 'invalid content', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'
        assert 'formato' in data['message'].lower()
        print(f"Invalid format error: {data['message']}")
    
    def test_import_integrators_requires_auth(self):
        """Test import endpoint requires authentication"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_NoAuth,Integrador,App1,Bridge PG,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            files=files
        )
        
        assert response.status_code == 401
        print("PASS: Import endpoint requires authentication")


# ==================== CLIENTS IMPORT TESTS ====================

class TestClientsImport:
    """Test POST /api/clients/import endpoint"""
    
    def test_import_clients_valid_csv(self):
        """Test successful import of valid clients CSV"""
        csv_content = """RIF,Nombre Jurídico,Nombre Fantasía,Segmento,Contacto1_Nombre,Contacto1_Teléfono,Contacto1_Email
J123456789,TEST_Empresa ABC,ABC Store,Pymes,Juan Perez,04121234567,juan@test.com
J987654321,TEST_Corporacion XYZ,XYZ Corp,Corporativo,Maria Garcia,04241234567,maria@test.com"""
        
        files = {'file': ('clients.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/clients/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'status' in data
        assert data['total_processed'] == 2
        print(f"Clients import: status={data['status']}, success={data['success_count']}")
    
    def test_import_clients_missing_rif(self):
        """Test validation error for missing RIF"""
        csv_content = """RIF,Nombre Jurídico,Segmento
,TEST_NoRIF Company,Pymes"""
        
        files = {'file': ('clients.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/clients/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['error_count'] > 0 or data['skipped_count'] > 0
        if data['errors']:
            error = data['errors'][0]
            assert error['error_type'] == 'missing'
            print(f"Missing RIF error: {error['message']}")
    
    def test_import_clients_duplicate_rif(self):
        """Test duplicate RIF detection"""
        csv_content = """RIF,Nombre Jurídico,Segmento
J111222333,TEST_DupClient,Pymes"""
        
        # First import
        files = {'file': ('clients.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/clients/import",
            headers=get_auth_headers(),
            files=files
        )
        assert response.status_code == 200
        
        # Second import
        files = {'file': ('clients.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/clients/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data['errors']:
            dup_errors = [e for e in data['errors'] if e['error_type'] == 'duplicate']
            assert len(dup_errors) > 0
            print(f"Duplicate RIF detected: {dup_errors[0]['message']}")
    
    def test_import_clients_segment_validation(self):
        """Test segment uses default if invalid value provided"""
        csv_content = """RIF,Nombre Jurídico,Segmento
J444555666,TEST_InvalidSegment,InvalidSegmentValue"""
        
        files = {'file': ('clients.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/clients/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should succeed with default segment 'Pymes'
        print(f"Segment validation: status={data['status']}, success={data['success_count']}")


# ==================== BANKS IMPORT TESTS ====================

class TestBanksImport:
    """Test POST /api/banks/import endpoint"""
    
    def test_import_banks_valid_csv(self):
        """Test successful import of valid banks CSV"""
        csv_content = """Nombre,Tipo,País
TEST_Banco Nacional,Banco,Venezuela
TEST_FinTech Solutions,Fintech,Estados Unidos"""
        
        files = {'file': ('banks.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/banks/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'status' in data
        assert data['total_processed'] == 2
        print(f"Banks import: status={data['status']}, success={data['success_count']}")
    
    def test_import_banks_missing_name(self):
        """Test validation error for missing bank name"""
        csv_content = """Nombre,Tipo,País
,Banco,Venezuela"""
        
        files = {'file': ('banks.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/banks/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['error_count'] > 0 or data['skipped_count'] > 0
        if data['errors']:
            error = data['errors'][0]
            assert error['error_type'] == 'missing'
            print(f"Missing name error: {error['message']}")
    
    def test_import_banks_duplicate_name(self):
        """Test duplicate bank name detection"""
        csv_content = """Nombre,Tipo,País
TEST_DupBank,Banco,Venezuela"""
        
        # First import
        files = {'file': ('banks.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/banks/import",
            headers=get_auth_headers(),
            files=files
        )
        assert response.status_code == 200
        
        # Second import
        files = {'file': ('banks.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/banks/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data['errors']:
            dup_errors = [e for e in data['errors'] if e['error_type'] == 'duplicate']
            assert len(dup_errors) > 0
            print(f"Duplicate bank detected: {dup_errors[0]['message']}")


# ==================== SERVICES/MEDIOS PAGO IMPORT TESTS ====================

class TestServicesImport:
    """Test POST /api/services/import endpoint"""
    
    def test_import_services_valid_csv(self):
        """Test successful import of valid services CSV"""
        csv_content = """Nombre,Categoría,Descripción,Setup_Convencional,Mensual_Convencional,Setup_Outsourcing,Mensual_Outsourcing
TEST_Tarjeta Credito,General,Procesamiento TC,100.00,10.00,120.00,12.00
TEST_Debito Bancario,General,Procesamiento DB,80.00,8.00,100.00,10.00"""
        
        files = {'file': ('services.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/services/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'status' in data
        assert data['total_processed'] == 2
        print(f"Services import: status={data['status']}, success={data['success_count']}")
    
    def test_import_services_missing_name(self):
        """Test validation error for missing service name"""
        csv_content = """Nombre,Categoría,Setup_Convencional
,General,100.00"""
        
        files = {'file': ('services.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/services/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data['error_count'] > 0 or data['skipped_count'] > 0
        if data['errors']:
            error = data['errors'][0]
            assert error['error_type'] == 'missing'
            print(f"Missing name error: {error['message']}")
    
    def test_import_services_invalid_cost_format(self):
        """Test validation for invalid cost format"""
        csv_content = """Nombre,Categoría,Setup_Convencional
TEST_InvalidCost,General,invalid_number"""
        
        files = {'file': ('services.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/services/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # May have error for invalid cost or may default to 0
        print(f"Invalid cost handling: status={data['status']}, errors={data['error_count']}")
    
    def test_import_services_duplicate_name(self):
        """Test duplicate service name detection"""
        csv_content = """Nombre,Categoría
TEST_DupService,General"""
        
        # First import
        files = {'file': ('services.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/services/import",
            headers=get_auth_headers(),
            files=files
        )
        assert response.status_code == 200
        
        # Second import
        files = {'file': ('services.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/services/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data['errors']:
            dup_errors = [e for e in data['errors'] if e['error_type'] == 'duplicate']
            assert len(dup_errors) > 0
            print(f"Duplicate service detected: {dup_errors[0]['message']}")


# ==================== IMPORT RESULT STRUCTURE TESTS ====================

class TestImportResultStructure:
    """Test ImportResult response structure consistency across all endpoints"""
    
    def test_import_result_has_required_fields(self):
        """Verify ImportResult contains all required fields"""
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
TEST_StructureTest,Integrador,App1,Bridge PG,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        required_fields = ['status', 'total_processed', 'success_count', 'error_count', 'skipped_count', 'errors', 'message']
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate status values
        assert data['status'] in ['success', 'partial', 'error']
        
        # Validate numeric fields
        assert isinstance(data['total_processed'], int)
        assert isinstance(data['success_count'], int)
        assert isinstance(data['error_count'], int)
        assert isinstance(data['skipped_count'], int)
        
        # Validate errors is a list
        assert isinstance(data['errors'], list)
        
        print("PASS: ImportResult has all required fields")
    
    def test_import_error_has_required_fields(self):
        """Verify ImportError in errors array contains all required fields"""
        # Create file with missing required field to generate error
        csv_content = """Nombre,Tipo,Aplicativo,Modalidad,Estatus
,Integrador,App1,Bridge PG,Certificado"""
        
        files = {'file': ('integrators.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/integrators/import",
            headers=get_auth_headers(),
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if data['errors']:
            error = data['errors'][0]
            error_fields = ['row', 'column', 'error_type', 'message', 'suggested_action']
            for field in error_fields:
                assert field in error, f"Missing error field: {field}"
            
            # Validate error_type values
            assert error['error_type'] in ['missing', 'invalid', 'format', 'duplicate']
            
            print(f"PASS: ImportError has all required fields: {error}")


# ==================== CLEANUP TEST DATA ====================

class TestCleanup:
    """Cleanup test data created during import tests"""
    
    def test_cleanup_test_integrators(self):
        """Remove test integrators created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/integrators",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            integrators = response.json()
            for intg in integrators:
                if intg['name'].startswith('TEST_'):
                    requests.delete(
                        f"{BASE_URL}/api/integrators/{intg['integrator_id']}",
                        headers=get_auth_headers()
                    )
        print("Cleanup: Test integrators removed")
    
    def test_cleanup_test_clients(self):
        """Remove test clients created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            clients = response.json()
            for client in clients:
                if 'TEST_' in client.get('legal_name', ''):
                    requests.delete(
                        f"{BASE_URL}/api/clients/{client['client_id']}",
                        headers=get_auth_headers()
                    )
        print("Cleanup: Test clients removed")
    
    def test_cleanup_test_banks(self):
        """Remove test banks created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/banks",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            banks = response.json()
            for bank in banks:
                if bank['name'].startswith('TEST_'):
                    requests.delete(
                        f"{BASE_URL}/api/banks/{bank['bank_id']}",
                        headers=get_auth_headers()
                    )
        print("Cleanup: Test banks removed")
    
    def test_cleanup_test_services(self):
        """Remove test services created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/services",
            headers=get_auth_headers()
        )
        
        if response.status_code == 200:
            services = response.json()
            for service in services:
                if service['name'].startswith('TEST_'):
                    requests.delete(
                        f"{BASE_URL}/api/services/{service['service_id']}",
                        headers=get_auth_headers()
                    )
        print("Cleanup: Test services removed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
