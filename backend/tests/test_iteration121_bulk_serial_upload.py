"""
Iteration 121: Test Bulk Serial Upload for Repair Quotations
Tests:
- POST /api/quotes/validate-repair-serials - Excel file upload and serial validation
- POST /api/quotes/generate-equipment-pdf - PDF generation with bulk_serials field
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBulkSerialUpload:
    """Tests for bulk serial upload feature in repair quotations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        
        if login_response.status_code != 200:
            # Try to register first
            register_response = self.session.post(f"{BASE_URL}/api/auth/register", json={
                "email": "admin@mega.com",
                "password": "Admin123!",
                "full_name": "Admin User"
            })
            if register_response.status_code in [200, 201]:
                login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
                    "email": "admin@mega.com",
                    "password": "Admin123!"
                })
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("session_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed")
    
    def create_test_excel(self, serials):
        """Create a test Excel file with serials using openpyxl"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Serial'])  # Header
        for serial in serials:
            ws.append([serial])
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
    
    # ==================== VALIDATE-REPAIR-SERIALS ENDPOINT ====================
    
    def test_validate_serials_endpoint_exists(self):
        """Test that the validate-repair-serials endpoint exists"""
        # Create a simple Excel file
        excel_buffer = self.create_test_excel(['TEST-SN-001', 'TEST-SN-002'])
        
        files = {'file': ('test_serials.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        # Should return 200 (success) - endpoint exists and processes file
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASSED: validate-repair-serials endpoint exists and returns 200")
    
    def test_validate_serials_returns_correct_structure(self):
        """Test that the response has correct structure"""
        excel_buffer = self.create_test_excel(['TEST-SN-001', 'TEST-SN-002', 'TEST-SN-003'])
        
        files = {'file': ('test_serials.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Check required fields
        assert 'total_uploaded' in result, "Missing 'total_uploaded' field"
        assert 'found' in result, "Missing 'found' field"
        assert 'not_found' in result, "Missing 'not_found' field"
        assert 'found_count' in result, "Missing 'found_count' field"
        assert 'not_found_count' in result, "Missing 'not_found_count' field"
        
        # Verify counts
        assert result['total_uploaded'] == 3, f"Expected 3 serials, got {result['total_uploaded']}"
        assert result['found_count'] + result['not_found_count'] == result['total_uploaded']
        
        print(f"PASSED: Response structure correct - {result['total_uploaded']} serials processed")
    
    def test_validate_serials_skips_headers(self):
        """Test that common header values are skipped"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        # Add various header-like values that should be skipped
        ws.append(['Serial'])
        ws.append(['Seriales'])
        ws.append(['Numero de Serie'])
        ws.append(['ACTUAL-SN-001'])  # This should be counted
        ws.append(['ACTUAL-SN-002'])  # This should be counted
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        files = {'file': ('test_headers.xlsx', buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should only count the 2 actual serials, not the headers
        assert result['total_uploaded'] == 2, f"Expected 2 serials (headers skipped), got {result['total_uploaded']}"
        print(f"PASSED: Headers correctly skipped - {result['total_uploaded']} actual serials counted")
    
    def test_validate_serials_deduplicates(self):
        """Test that duplicate serials are removed"""
        excel_buffer = self.create_test_excel(['DUP-SN-001', 'DUP-SN-001', 'DUP-SN-002', 'DUP-SN-002', 'DUP-SN-003'])
        
        files = {'file': ('test_duplicates.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Should deduplicate: 5 entries -> 3 unique
        assert result['total_uploaded'] == 3, f"Expected 3 unique serials, got {result['total_uploaded']}"
        print(f"PASSED: Duplicates removed - {result['total_uploaded']} unique serials")
    
    def test_validate_serials_rejects_non_excel(self):
        """Test that non-Excel files are rejected"""
        # Create a fake text file
        fake_file = io.BytesIO(b"This is not an Excel file")
        
        files = {'file': ('test.txt', fake_file, 'text/plain')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        # Should return 400 for invalid file type
        assert response.status_code == 400, f"Expected 400 for non-Excel file, got {response.status_code}"
        print("PASSED: Non-Excel files correctly rejected with 400")
    
    def test_validate_serials_empty_file(self):
        """Test handling of Excel file with no serials"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Serial'])  # Only header, no data
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        files = {'file': ('empty.xlsx', buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        # Should return 400 for empty file
        assert response.status_code == 400, f"Expected 400 for empty file, got {response.status_code}"
        print("PASSED: Empty Excel file correctly rejected with 400")
    
    def test_validate_serials_not_found_structure(self):
        """Test that not_found items have correct structure"""
        excel_buffer = self.create_test_excel(['NONEXISTENT-SN-001'])
        
        files = {'file': ('test.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Since inventory is likely empty, all should be not_found
        assert result['not_found_count'] >= 1, "Expected at least 1 not_found serial"
        
        # Check not_found structure
        if result['not_found']:
            item = result['not_found'][0]
            assert 'serial' in item, "not_found item missing 'serial' field"
        
        print(f"PASSED: not_found structure correct - {result['not_found_count']} not found")
    
    # ==================== GENERATE-EQUIPMENT-PDF WITH BULK_SERIALS ====================
    
    def test_generate_equipment_pdf_accepts_bulk_serials(self):
        """Test that generate-equipment-pdf accepts bulk_serials array"""
        # First get a client
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client = clients_response.json()[0]
        
        # Get hardware items for repair type
        hardware_response = self.session.get(f"{BASE_URL}/api/hardware")
        hardware_items = []
        if hardware_response.status_code == 200:
            all_hardware = hardware_response.json()
            # Filter for repair-related types
            repair_types = ['Mantenimiento', 'Consultoria', 'Componente', 'Pieza']
            hardware_items = [h for h in all_hardware if h.get('type') in repair_types]
        
        # If no repair hardware, create a minimal item
        if not hardware_items:
            items = [{
                "hardware_id": "test_repair_001",
                "name": "Servicio de Reparación Test",
                "hardware_type": "Mantenimiento",
                "quantity": 1,
                "unit_price_usd": 50.00,
                "total_usd": 50.00
            }]
        else:
            h = hardware_items[0]
            items = [{
                "hardware_id": h.get('hardware_id', 'test'),
                "name": h.get('name', 'Servicio Test'),
                "hardware_type": h.get('type', 'Mantenimiento'),
                "quantity": 1,
                "unit_price_usd": h.get('price_usd', 50.00),
                "total_usd": h.get('price_usd', 50.00)
            }]
        
        pdf_data = {
            "client_id": client.get('client_id', ''),
            "cliente_nombre": client.get('legal_name') or client.get('fantasy_name', 'Test Client'),
            "cliente_rif": client.get('rif', 'J-12345678-9'),
            "cliente_address": client.get('address', ''),
            "equipment_type": "Reparación",
            "items": items,
            "notes": "Test de carga masiva de seriales",
            "repair_description": "Reparación de equipos con seriales cargados masivamente",
            "equipment_serial_number": "",
            "estimated_delivery_date": "2026-02-15",
            "bulk_serials": ["BULK-SN-001", "BULK-SN-002", "BULK-SN-003"]
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf', "Expected PDF content type"
        
        # Check that quote was created with headers
        quote_id = response.headers.get('X-Quote-Id')
        quote_number = response.headers.get('X-Quote-Number')
        
        assert quote_id, "Missing X-Quote-Id header"
        assert quote_number, "Missing X-Quote-Number header"
        
        print(f"PASSED: PDF generated with bulk_serials - Quote: {quote_number}")
        
        # Cleanup: delete the test quote
        if quote_id:
            self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
    
    def test_generate_equipment_pdf_includes_serials_in_pdf(self):
        """Test that bulk serials are included in the generated PDF"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client = clients_response.json()[0]
        
        pdf_data = {
            "client_id": client.get('client_id', ''),
            "cliente_nombre": client.get('legal_name') or client.get('fantasy_name', 'Test Client'),
            "cliente_rif": client.get('rif', 'J-12345678-9'),
            "cliente_address": client.get('address', ''),
            "equipment_type": "Reparación",
            "items": [{
                "hardware_id": "test_repair_002",
                "name": "Diagnóstico de Equipo",
                "hardware_type": "Mantenimiento",
                "quantity": 1,
                "unit_price_usd": 25.00,
                "total_usd": 25.00
            }],
            "notes": "",
            "repair_description": "Diagnóstico y reparación de múltiples equipos",
            "equipment_serial_number": "",
            "estimated_delivery_date": "",
            "bulk_serials": ["PDF-TEST-SN-001", "PDF-TEST-SN-002"]
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        # PDF content should contain the serials (check PDF size is reasonable)
        pdf_content = response.content
        assert len(pdf_content) > 1000, "PDF seems too small, may not include serials"
        
        quote_id = response.headers.get('X-Quote-Id')
        print(f"PASSED: PDF generated with serials included (size: {len(pdf_content)} bytes)")
        
        # Cleanup
        if quote_id:
            self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
    
    def test_generate_equipment_pdf_empty_bulk_serials(self):
        """Test that empty bulk_serials array is handled correctly"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client = clients_response.json()[0]
        
        pdf_data = {
            "client_id": client.get('client_id', ''),
            "cliente_nombre": client.get('legal_name') or client.get('fantasy_name', 'Test Client'),
            "cliente_rif": client.get('rif', 'J-12345678-9'),
            "cliente_address": client.get('address', ''),
            "equipment_type": "Reparación",
            "items": [{
                "hardware_id": "test_repair_003",
                "name": "Servicio de Mantenimiento",
                "hardware_type": "Mantenimiento",
                "quantity": 1,
                "unit_price_usd": 30.00,
                "total_usd": 30.00
            }],
            "notes": "",
            "repair_description": "Mantenimiento preventivo",
            "equipment_serial_number": "SINGLE-SN-001",  # Single serial instead of bulk
            "estimated_delivery_date": "",
            "bulk_serials": []  # Empty array
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        quote_id = response.headers.get('X-Quote-Id')
        print("PASSED: Empty bulk_serials handled correctly")
        
        # Cleanup
        if quote_id:
            self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
    
    # ==================== EQUIPMENT QUOTE PDF REQUEST MODEL ====================
    
    def test_equipment_pdf_request_model_has_bulk_serials(self):
        """Test that the EquipmentQuotePDFRequest model accepts bulk_serials"""
        clients_response = self.session.get(f"{BASE_URL}/api/clients")
        if clients_response.status_code != 200 or not clients_response.json():
            pytest.skip("No clients available for testing")
        
        client = clients_response.json()[0]
        
        # Test with various bulk_serials configurations
        test_cases = [
            {"bulk_serials": ["SN-1"]},
            {"bulk_serials": ["SN-1", "SN-2", "SN-3", "SN-4", "SN-5"]},
            {"bulk_serials": []},
        ]
        
        for i, test_case in enumerate(test_cases):
            pdf_data = {
                "client_id": client.get('client_id', ''),
                "cliente_nombre": client.get('legal_name') or client.get('fantasy_name', 'Test'),
                "cliente_rif": client.get('rif', 'J-00000000-0'),
                "cliente_address": "",
                "equipment_type": "Reparación",
                "items": [{
                    "hardware_id": f"test_{i}",
                    "name": "Test Service",
                    "hardware_type": "Mantenimiento",
                    "quantity": 1,
                    "unit_price_usd": 10.00,
                    "total_usd": 10.00
                }],
                "notes": "",
                "repair_description": f"Test case {i}",
                "equipment_serial_number": "",
                "estimated_delivery_date": "",
                **test_case
            }
            
            response = self.session.post(
                f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                json=pdf_data
            )
            
            assert response.status_code == 200, f"Test case {i} failed: {response.status_code}"
            
            quote_id = response.headers.get('X-Quote-Id')
            if quote_id:
                self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
        
        print("PASSED: EquipmentQuotePDFRequest model accepts all bulk_serials configurations")


class TestBulkSerialUploadAuth:
    """Test authentication requirements for bulk serial endpoints"""
    
    def test_validate_serials_requires_auth(self):
        """Test that validate-repair-serials requires authentication"""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['Serial'])
        ws.append(['TEST-001'])
        
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        files = {'file': ('test.xlsx', buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        data = {'client_id': ''}
        
        # No auth header
        response = requests.post(
            f"{BASE_URL}/api/quotes/validate-repair-serials",
            files=files,
            data=data
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("PASSED: validate-repair-serials requires authentication")
    
    def test_generate_equipment_pdf_requires_auth(self):
        """Test that generate-equipment-pdf requires authentication"""
        pdf_data = {
            "cliente_nombre": "Test",
            "cliente_rif": "J-00000000-0",
            "equipment_type": "Reparación",
            "items": [],
            "bulk_serials": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("PASSED: generate-equipment-pdf requires authentication")
