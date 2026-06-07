# ruff: noqa
"""
Test suite for Client Import Functionality (iteration_45)
Tests the improved import feature with:
- Template download (Excel with 3 sheets: Plantilla, Instrucciones, Valores Válidos)
- Import validation (RIF+Sucursal as unique key)
- CRM contacts support
- Detailed error reporting
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClientImportTemplate:
    """Tests for GET /api/clients/template - Excel template download"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token before each test"""
        self.session = requests.Session()
        # Login to get session token
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test_anexos@test.com",
            "password": "Test1234!"
        })
        if response.status_code == 200:
            token = response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_template_endpoint_returns_excel(self):
        """Template endpoint should return an Excel file"""
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type is Excel
        content_type = response.headers.get('Content-Type', '')
        assert 'spreadsheetml' in content_type or 'application/vnd' in content_type, \
            f"Expected Excel content type, got {content_type}"
        
        # Check content-disposition for filename
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'plantilla_clientes.xlsx' in content_disp, \
            f"Expected plantilla_clientes.xlsx in Content-Disposition, got {content_disp}"
    
    def test_template_has_three_sheets(self):
        """Template Excel should have 3 sheets: Plantilla, Instrucciones, Valores Válidos"""
        import pandas as pd
        
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert response.status_code == 200
        
        # Read Excel file
        excel_data = io.BytesIO(response.content)
        excel_file = pd.ExcelFile(excel_data)
        
        # Verify sheet names
        expected_sheets = ['Plantilla', 'Instrucciones', 'Valores Válidos']
        actual_sheets = excel_file.sheet_names
        
        for sheet in expected_sheets:
            assert sheet in actual_sheets, f"Sheet '{sheet}' not found. Got: {actual_sheets}"
    
    def test_plantilla_sheet_has_required_columns(self):
        """Plantilla sheet should have all required columns"""
        import pandas as pd
        
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert response.status_code == 200
        
        excel_data = io.BytesIO(response.content)
        df = pd.read_excel(excel_data, sheet_name='Plantilla')
        
        # Check required columns
        required_columns = [
            'RIF', 'Sucursal', 'Nombre Jurídico', 'Nombre Fantasía', 
            'Segmento', 'Dirección', 'Contacto Nombre', 'Contacto Apellido',
            'Contacto Teléfono', 'Contacto Email', 'Contacto Rol'
        ]
        
        for col in required_columns:
            assert col in df.columns, f"Column '{col}' not found in Plantilla sheet. Got: {list(df.columns)}"
    
    def test_plantilla_sheet_has_sample_data(self):
        """Plantilla sheet should have sample data"""
        import pandas as pd
        
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert response.status_code == 200
        
        excel_data = io.BytesIO(response.content)
        df = pd.read_excel(excel_data, sheet_name='Plantilla')
        
        # Should have at least 2 sample rows
        assert len(df) >= 2, f"Plantilla should have sample data, got {len(df)} rows"
    
    def test_valores_validos_has_segments_and_roles(self):
        """Valores Válidos sheet should list valid segments and contact roles"""
        import pandas as pd
        
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert response.status_code == 200
        
        excel_data = io.BytesIO(response.content)
        df = pd.read_excel(excel_data, sheet_name='Valores Válidos')
        
        # Check for Roles column
        roles_col = None
        for col in df.columns:
            if 'rol' in col.lower():
                roles_col = col
                break
        
        assert roles_col is not None, f"Expected roles column, got columns: {list(df.columns)}"
        
        # Verify valid roles listed
        valid_roles = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo']
        roles_in_sheet = df[roles_col].dropna().tolist()
        
        for role in valid_roles:
            assert role in roles_in_sheet, f"Role '{role}' not found in Valores Válidos"


class TestClientImportValidation:
    """Tests for POST /api/clients/import - Import with validation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth token before each test"""
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test_anexos@test.com",
            "password": "Test1234!"
        })
        if response.status_code == 200:
            token = response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def _create_test_excel(self, data_rows: list) -> bytes:
        """Helper to create test Excel file"""
        import pandas as pd
        
        columns = ['RIF', 'Sucursal', 'Nombre Jurídico', 'Nombre Fantasía', 
                   'Segmento', 'Dirección', 'Contacto Nombre', 'Contacto Apellido',
                   'Contacto Teléfono', 'Contacto Email', 'Contacto Rol']
        
        df = pd.DataFrame(data_rows, columns=columns)
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name='Plantilla')
        output.seek(0)
        return output.getvalue()
    
    def test_import_valid_client(self):
        """Import should succeed with valid client data"""
        import uuid
        
        unique_rif = f"J-TEST-{uuid.uuid4().hex[:6].upper()}"
        
        test_data = [[
            unique_rif, 'Principal', 'TEST Empresa Import', 'TEST Import Corp',
            'Corporativo', 'Av Test 123', 'Carlos', 'Tester',
            '0412-1234567', 'carlos@test.com', 'Administrativo'
        ]]
        
        excel_bytes = self._create_test_excel(test_data)
        
        files = {'file': ('test_import.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['status'] == 'success', f"Expected success, got {result}"
        assert result['success_count'] == 1
        assert result['error_count'] == 0
        
        # Cleanup - delete test client
        clients = self.session.get(f"{BASE_URL}/api/clients").json()
        for c in clients:
            if c['rif'] == unique_rif:
                self.session.delete(f"{BASE_URL}/api/clients/{c['client_id']}")
    
    def test_import_validates_rif_sucursal_unique_key(self):
        """Import should reject duplicate RIF+Sucursal combinations"""
        import uuid
        
        unique_rif = f"J-DUP-{uuid.uuid4().hex[:6].upper()}"
        
        # First import - should succeed
        test_data = [[
            unique_rif, 'Principal', 'TEST Duplicate Check', 'DupCheck Corp',
            'Pymes', '', 'Ana', 'Test', '0414-1111111', 'ana@test.com', 'Financiero'
        ]]
        
        excel_bytes = self._create_test_excel(test_data)
        files = {'file': ('import1.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response1 = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response1.status_code == 200
        assert response1.json()['status'] == 'success'
        
        # Second import with same RIF+Sucursal - should fail/report duplicate
        excel_bytes2 = self._create_test_excel(test_data)
        files2 = {'file': ('import2.xlsx', excel_bytes2, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response2 = self.session.post(f"{BASE_URL}/api/clients/import", files=files2)
        
        assert response2.status_code == 200
        result2 = response2.json()
        
        # Should report error or skip due to duplicate
        assert result2['success_count'] == 0 or result2['skipped_count'] >= 1, \
            f"Duplicate should be skipped, got: {result2}"
        
        # Verify error mentions duplicate
        if result2['errors']:
            has_duplicate_error = any('duplicate' in str(e).lower() or 'existe' in str(e).lower() 
                                      for e in result2['errors'])
            assert has_duplicate_error, f"Expected duplicate error, got: {result2['errors']}"
        
        # Cleanup
        clients = self.session.get(f"{BASE_URL}/api/clients").json()
        for c in clients:
            if c['rif'] == unique_rif:
                self.session.delete(f"{BASE_URL}/api/clients/{c['client_id']}")
    
    def test_import_allows_same_rif_different_sucursal(self):
        """Import should allow same RIF with different Sucursal"""
        import uuid
        
        unique_rif = f"J-MULTI-{uuid.uuid4().hex[:6].upper()}"
        
        # Import two rows with same RIF but different Sucursal
        test_data = [
            [unique_rif, 'Principal', 'TEST Multi Sede', 'MultiSede Corp', 'Corporativo', '', 'Jose', 'Main', '0412-0000001', 'jose@test.com', 'Administrativo'],
            [unique_rif, 'Sede Norte', 'TEST Multi Sede', 'MultiSede Norte', 'Corporativo', '', 'Maria', 'Norte', '0412-0000002', 'maria@test.com', 'Técnico']
        ]
        
        excel_bytes = self._create_test_excel(test_data)
        files = {'file': ('multi_sede.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['success_count'] == 2, f"Both clients should import, got: {result}"
        assert result['error_count'] == 0
        
        # Cleanup
        clients = self.session.get(f"{BASE_URL}/api/clients").json()
        for c in clients:
            if c['rif'] == unique_rif:
                self.session.delete(f"{BASE_URL}/api/clients/{c['client_id']}")
    
    def test_import_validates_required_fields(self):
        """Import should report errors for missing required fields"""
        # Missing RIF
        test_data_no_rif = [[
            '', 'Principal', 'Test No RIF', 'NoRIF Corp',
            'Pymes', '', '', '', '', '', ''
        ]]
        
        excel_bytes = self._create_test_excel(test_data_no_rif)
        files = {'file': ('no_rif.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['success_count'] == 0, "Should not import row without RIF"
        assert len(result['errors']) > 0, "Should report error for missing RIF"
        
        # Check error message mentions RIF
        error_messages = [str(e) for e in result['errors']]
        has_rif_error = any('rif' in msg.lower() for msg in error_messages)
        assert has_rif_error, f"Error should mention RIF, got: {error_messages}"
    
    def test_import_validates_nombre_juridico_required(self):
        """Import should report errors for missing Nombre Jurídico"""
        import uuid
        
        unique_rif = f"J-NOLEGAL-{uuid.uuid4().hex[:6].upper()}"
        
        test_data = [[
            unique_rif, 'Principal', '', 'NoLegal Corp',  # Empty legal_name
            'Pymes', '', '', '', '', '', ''
        ]]
        
        excel_bytes = self._create_test_excel(test_data)
        files = {'file': ('no_legal.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        
        assert result['success_count'] == 0, "Should not import without legal name"
        assert len(result['errors']) > 0, "Should report error for missing legal name"
    
    def test_import_creates_crm_contacts(self):
        """Imported clients should have CRM contacts with roles"""
        import uuid
        
        unique_rif = f"J-CRM-{uuid.uuid4().hex[:6].upper()}"
        
        test_data = [[
            unique_rif, 'Principal', 'TEST CRM Contact', 'CRM Corp',
            'Corporativo', 'Av CRM 123', 'Pedro', 'Contacto',
            '0416-5551234', 'pedro@crmtest.com', 'Técnico'
        ]]
        
        excel_bytes = self._create_test_excel(test_data)
        files = {'file': ('crm_contact.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'success'
        
        # Get the imported client and verify contacts
        clients = self.session.get(f"{BASE_URL}/api/clients").json()
        imported_client = next((c for c in clients if c['rif'] == unique_rif), None)
        
        assert imported_client is not None, "Imported client should exist"
        assert 'contacts' in imported_client, "Client should have contacts field"
        assert len(imported_client['contacts']) >= 1, "Client should have at least 1 contact"
        
        contact = imported_client['contacts'][0]
        assert contact['first_name'] == 'Pedro', f"Contact first name should be Pedro, got: {contact}"
        assert contact['last_name'] == 'Contacto', f"Contact last name should be Contacto, got: {contact}"
        assert contact['role'] == 'Técnico', f"Contact role should be Técnico, got: {contact}"
        assert 'contact_id' in contact, "Contact should have contact_id"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/clients/{imported_client['client_id']}")
    
    def test_import_returns_detailed_error_result(self):
        """Import should return detailed error info for each row"""
        test_data = [
            ['', 'Principal', '', '', '', '', '', '', '', '', ''],  # Missing both RIF and legal name
        ]
        
        excel_bytes = self._create_test_excel(test_data)
        files = {'file': ('errors.xlsx', excel_bytes, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert response.status_code == 200
        result = response.json()
        
        # Check error structure
        assert 'errors' in result
        assert len(result['errors']) > 0
        
        error = result['errors'][0]
        assert 'row' in error, "Error should include row number"
        assert 'column' in error, "Error should include column name"
        assert 'message' in error, "Error should include message"


class TestClientImportIntegration:
    """Integration tests for complete import flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test_anexos@test.com",
            "password": "Test1234!"
        })
        if response.status_code == 200:
            token = response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_download_template_then_import(self):
        """Full flow: download template, modify it, import clients"""
        import pandas as pd
        import uuid
        
        # Step 1: Download template
        template_response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert template_response.status_code == 200
        
        # Step 2: Read template and add test data
        excel_data = io.BytesIO(template_response.content)
        df = pd.read_excel(excel_data, sheet_name='Plantilla')
        
        unique_rif = f"J-FLOW-{uuid.uuid4().hex[:6].upper()}"
        
        # Clear sample data and add test data
        df = df.iloc[0:0]  # Clear all rows
        new_row = {
            'RIF': unique_rif,
            'Sucursal': 'Test Sucursal',
            'Nombre Jurídico': 'TEST Flow Import CA',
            'Nombre Fantasía': 'FlowTest Corp',
            'Segmento': 'Mixto',
            'Dirección': 'Av Test Flow 456',
            'Contacto Nombre': 'Flow',
            'Contacto Apellido': 'Tester',
            'Contacto Teléfono': '0412-9999999',
            'Contacto Email': 'flow@test.com',
            'Contacto Rol': 'Cuentas por Pagar'
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Step 3: Export to bytes
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        
        # Step 4: Import
        files = {'file': ('flow_import.xlsx', output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        import_response = self.session.post(f"{BASE_URL}/api/clients/import", files=files)
        
        assert import_response.status_code == 200
        result = import_response.json()
        assert result['status'] == 'success', f"Import should succeed, got: {result}"
        
        # Step 5: Verify client exists with correct data
        clients = self.session.get(f"{BASE_URL}/api/clients").json()
        imported = next((c for c in clients if c['rif'] == unique_rif), None)
        
        assert imported is not None
        assert imported['sucursal'] == 'Test Sucursal'
        assert imported['segment'] == 'Mixto'
        assert len(imported.get('contacts', [])) >= 1
        assert imported['contacts'][0]['role'] == 'Cuentas por Pagar'
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/clients/{imported['client_id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
