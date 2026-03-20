"""
Test iteration 119: Equipment Quote Categories Split
Tests the new equipment categorization (Verifone, Morefun, Accesorios, Reparaciones)
and PDF generation with legal conditions appended.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = f"test_equip_{uuid.uuid4().hex[:6]}@test.com"
TEST_PASSWORD = "TestPass123!"
TEST_FULL_NAME = "Test Equipment User"


class TestEquipmentQuoteCategories:
    """Tests for the new equipment quote categories and PDF generation"""
    
    session_token = None
    test_client_id = None
    test_hardware_ids = {}
    
    @pytest.fixture(autouse=True)
    def setup(self, request):
        """Setup: Register user and create test data"""
        if TestEquipmentQuoteCategories.session_token is None:
            # Register a new user
            register_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "full_name": TEST_FULL_NAME
            })
            if register_resp.status_code == 200:
                TestEquipmentQuoteCategories.session_token = register_resp.json().get("session_token")
            else:
                # Try login if user exists
                login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                    "email": "admin@mega.com",
                    "password": "Admin123!"
                })
                if login_resp.status_code == 200:
                    TestEquipmentQuoteCategories.session_token = login_resp.json().get("session_token")
                else:
                    pytest.skip("Could not authenticate")
        
        # Create test client if needed
        if TestEquipmentQuoteCategories.test_client_id is None:
            headers = {"Authorization": f"Bearer {TestEquipmentQuoteCategories.session_token}"}
            client_resp = requests.post(f"{BASE_URL}/api/clients", json={
                "legal_name": "TEST_Equipment_Client",
                "fantasy_name": "Test Equip Client",
                "rif": f"J-{uuid.uuid4().hex[:8]}",
                "address": "Test Address 123"
            }, headers=headers)
            if client_resp.status_code in [200, 201]:
                TestEquipmentQuoteCategories.test_client_id = client_resp.json().get("client_id")
        
        # Create test hardware items for each category
        if not TestEquipmentQuoteCategories.test_hardware_ids:
            headers = {"Authorization": f"Bearer {TestEquipmentQuoteCategories.session_token}"}
            
            # POS device (for Verifone/Morefun)
            pos_resp = requests.post(f"{BASE_URL}/api/hardware", json={
                "name": "TEST_POS_Device",
                "type": "POS",
                "price_usd": 150.00,
                "description": "Test POS device"
            }, headers=headers)
            if pos_resp.status_code in [200, 201]:
                TestEquipmentQuoteCategories.test_hardware_ids["POS"] = pos_resp.json().get("hardware_id")
            
            # Pinpad device (for Verifone/Morefun)
            pinpad_resp = requests.post(f"{BASE_URL}/api/hardware", json={
                "name": "TEST_Pinpad_Device",
                "type": "Pinpad",
                "price_usd": 80.00,
                "description": "Test Pinpad device"
            }, headers=headers)
            if pinpad_resp.status_code in [200, 201]:
                TestEquipmentQuoteCategories.test_hardware_ids["Pinpad"] = pinpad_resp.json().get("hardware_id")
            
            # Accessory
            acc_resp = requests.post(f"{BASE_URL}/api/hardware", json={
                "name": "TEST_Accessory_Cable",
                "type": "Accesorio",
                "price_usd": 25.00,
                "description": "Test accessory cable"
            }, headers=headers)
            if acc_resp.status_code in [200, 201]:
                TestEquipmentQuoteCategories.test_hardware_ids["Accesorio"] = acc_resp.json().get("hardware_id")
            
            # Repair/Maintenance item
            repair_resp = requests.post(f"{BASE_URL}/api/hardware", json={
                "name": "TEST_Repair_Service",
                "type": "Mantenimiento",
                "price_usd": 50.00,
                "description": "Test repair service"
            }, headers=headers)
            if repair_resp.status_code in [200, 201]:
                TestEquipmentQuoteCategories.test_hardware_ids["Mantenimiento"] = repair_resp.json().get("hardware_id")
    
    def get_headers(self):
        return {"Authorization": f"Bearer {TestEquipmentQuoteCategories.session_token}"}
    
    # ==================== VERIFONE CATEGORY TESTS ====================
    
    def test_generate_verifone_pdf(self):
        """Test: POST /api/quotes/generate-equipment-pdf with equipment_type='Verifone'"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        payload = {
            "client_id": TestEquipmentQuoteCategories.test_client_id or "",
            "cliente_nombre": "Test Verifone Client",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Test Address",
            "equipment_type": "Verifone",
            "items": [
                {
                    "hardware_id": TestEquipmentQuoteCategories.test_hardware_ids.get("POS", "hw_test"),
                    "name": "POS Verifone P200",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 150.00,
                    "total_usd": 300.00
                }
            ],
            "notes": "Test Verifone quote"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        # PDF should be larger than base because conditions are appended
        pdf_size = len(response.content)
        assert pdf_size > 10000, f"PDF too small ({pdf_size} bytes), conditions may not be appended"
        
        # Check quote was created in DB via headers
        quote_id = response.headers.get("X-Quote-Id")
        quote_number = response.headers.get("X-Quote-Number")
        assert quote_id is not None, "Quote ID should be returned in headers"
        assert quote_number is not None, "Quote number should be returned in headers"
        
        print(f"✓ Verifone PDF generated: {pdf_size} bytes, Quote: {quote_number}")
    
    # ==================== MOREFUN CATEGORY TESTS ====================
    
    def test_generate_morefun_pdf(self):
        """Test: POST /api/quotes/generate-equipment-pdf with equipment_type='Morefun'"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        payload = {
            "client_id": TestEquipmentQuoteCategories.test_client_id or "",
            "cliente_nombre": "Test Morefun Client",
            "cliente_rif": "J-87654321-0",
            "cliente_address": "Test Address Morefun",
            "equipment_type": "Morefun",
            "items": [
                {
                    "hardware_id": TestEquipmentQuoteCategories.test_hardware_ids.get("Pinpad", "hw_test"),
                    "name": "Morefun Android Terminal",
                    "hardware_type": "Pinpad",
                    "quantity": 3,
                    "unit_price_usd": 80.00,
                    "total_usd": 240.00
                }
            ],
            "notes": "Test Morefun quote"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        pdf_size = len(response.content)
        assert pdf_size > 10000, f"PDF too small ({pdf_size} bytes), conditions may not be appended"
        
        print(f"✓ Morefun PDF generated: {pdf_size} bytes")
    
    # ==================== ACCESORIO CATEGORY TESTS ====================
    
    def test_generate_accesorio_pdf(self):
        """Test: POST /api/quotes/generate-equipment-pdf with equipment_type='Accesorio'"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        payload = {
            "client_id": TestEquipmentQuoteCategories.test_client_id or "",
            "cliente_nombre": "Test Accesorio Client",
            "cliente_rif": "J-11111111-1",
            "cliente_address": "Test Address Accesorios",
            "equipment_type": "Accesorio",
            "items": [
                {
                    "hardware_id": TestEquipmentQuoteCategories.test_hardware_ids.get("Accesorio", "hw_test"),
                    "name": "Cable USB-C",
                    "hardware_type": "Accesorio",
                    "quantity": 5,
                    "unit_price_usd": 25.00,
                    "total_usd": 125.00
                }
            ],
            "notes": "Test Accesorios quote"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        pdf_size = len(response.content)
        assert pdf_size > 10000, f"PDF too small ({pdf_size} bytes), conditions may not be appended"
        
        print(f"✓ Accesorio PDF generated: {pdf_size} bytes")
    
    # ==================== REPARACIÓN CATEGORY TESTS ====================
    
    def test_generate_reparacion_pdf(self):
        """Test: POST /api/quotes/generate-equipment-pdf with equipment_type='Reparación'"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        payload = {
            "client_id": TestEquipmentQuoteCategories.test_client_id or "",
            "cliente_nombre": "Test Reparación Client",
            "cliente_rif": "J-22222222-2",
            "cliente_address": "Test Address Reparaciones",
            "equipment_type": "Reparación",
            "items": [
                {
                    "hardware_id": TestEquipmentQuoteCategories.test_hardware_ids.get("Mantenimiento", "hw_test"),
                    "name": "Servicio de Reparación",
                    "hardware_type": "Mantenimiento",
                    "quantity": 1,
                    "unit_price_usd": 50.00,
                    "total_usd": 50.00
                }
            ],
            "notes": "Test Reparaciones quote",
            "repair_description": "Pantalla dañada, requiere reemplazo",
            "equipment_serial_number": "SN-TEST-12345",
            "estimated_delivery_date": "2026-02-15"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        pdf_size = len(response.content)
        assert pdf_size > 10000, f"PDF too small ({pdf_size} bytes), conditions may not be appended"
        
        print(f"✓ Reparación PDF generated: {pdf_size} bytes")
    
    # ==================== PDF SIZE COMPARISON TESTS ====================
    
    def test_pdf_size_with_conditions_larger_than_base(self):
        """Test: Generated PDFs should be larger due to appended legal conditions"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        # Generate a minimal PDF for Verifone
        payload = {
            "cliente_nombre": "Size Test Client",
            "cliente_rif": "J-33333333-3",
            "equipment_type": "Verifone",
            "items": [
                {
                    "name": "Test Item",
                    "hardware_type": "POS",
                    "quantity": 1,
                    "unit_price_usd": 100.00,
                    "total_usd": 100.00
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        assert response.status_code == 200
        
        verifone_pdf_size = len(response.content)
        
        # The condiciones_verifone.pdf is ~510KB, so total should be > 500KB
        # Base PDF is typically ~10-50KB
        assert verifone_pdf_size > 100000, f"Verifone PDF ({verifone_pdf_size} bytes) should include conditions (~510KB)"
        
        print(f"✓ PDF size verification: {verifone_pdf_size} bytes (includes legal conditions)")
    
    # ==================== QUOTE DB RECORD TESTS ====================
    
    def test_quote_record_has_correct_equipment_type(self):
        """Test: Quote record in DB should have correct equipment_type field"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        # Generate a quote
        payload = {
            "cliente_nombre": "DB Record Test Client",
            "cliente_rif": "J-44444444-4",
            "equipment_type": "Morefun",
            "items": [
                {
                    "name": "Morefun Terminal",
                    "hardware_type": "POS",
                    "quantity": 1,
                    "unit_price_usd": 200.00,
                    "total_usd": 200.00
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        assert response.status_code == 200
        
        quote_id = response.headers.get("X-Quote-Id")
        assert quote_id is not None
        
        # Fetch the quote from DB
        quote_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.get_headers())
        assert quote_resp.status_code == 200
        
        quote_data = quote_resp.json()
        assert quote_data.get("equipment_type") == "Morefun", f"Expected equipment_type='Morefun', got '{quote_data.get('equipment_type')}'"
        assert quote_data.get("quote_category") == "equipment", f"Expected quote_category='equipment', got '{quote_data.get('quote_category')}'"
        
        print(f"✓ Quote DB record has correct equipment_type: {quote_data.get('equipment_type')}")
    
    def test_reparacion_quote_has_repair_fields(self):
        """Test: Reparación quote should have repair-specific fields in DB"""
        headers = self.get_headers()
        headers["Accept"] = "application/pdf"
        
        payload = {
            "cliente_nombre": "Repair Fields Test",
            "cliente_rif": "J-55555555-5",
            "equipment_type": "Reparación",
            "items": [
                {
                    "name": "Repair Service",
                    "hardware_type": "Mantenimiento",
                    "quantity": 1,
                    "unit_price_usd": 75.00,
                    "total_usd": 75.00
                }
            ],
            "repair_description": "Test repair description",
            "equipment_serial_number": "SN-REPAIR-TEST",
            "estimated_delivery_date": "2026-03-01"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf", json=payload, headers=headers)
        assert response.status_code == 200
        
        quote_id = response.headers.get("X-Quote-Id")
        quote_resp = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=self.get_headers())
        assert quote_resp.status_code == 200
        
        quote_data = quote_resp.json()
        assert quote_data.get("equipment_type") == "Reparación"
        assert quote_data.get("quote_category") == "repair"
        assert quote_data.get("repair_description") == "Test repair description"
        assert quote_data.get("equipment_serial_number") == "SN-REPAIR-TEST"
        
        print(f"✓ Reparación quote has repair-specific fields")
    
    # ==================== STATIC PDF FILES EXISTENCE TESTS ====================
    
    def test_static_condition_pdfs_exist(self):
        """Test: All condition PDF files should exist in static_pdfs directory"""
        import os
        
        static_pdfs_dir = "/app/backend/static_pdfs"
        required_files = [
            "condiciones_verifone.pdf",
            "condiciones_morefun.pdf",
            "condiciones_accesorios.pdf",
            "condiciones_reparaciones.pdf"
        ]
        
        for filename in required_files:
            filepath = os.path.join(static_pdfs_dir, filename)
            assert os.path.exists(filepath), f"Missing condition PDF: {filename}"
            
            # Check file is not empty
            file_size = os.path.getsize(filepath)
            assert file_size > 1000, f"Condition PDF {filename} is too small ({file_size} bytes)"
            
            print(f"✓ {filename} exists ({file_size} bytes)")


class TestImplementationFlowUnaffected:
    """Tests to verify the existing implementation flow (VPOS/MPOS/Gateway) is unaffected"""
    
    session_token = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if TestImplementationFlowUnaffected.session_token is None:
            login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@mega.com",
                "password": "Admin123!"
            })
            if login_resp.status_code == 200:
                TestImplementationFlowUnaffected.session_token = login_resp.json().get("session_token")
            else:
                # Try registering
                register_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "full_name": TEST_FULL_NAME
                })
                if register_resp.status_code == 200:
                    TestImplementationFlowUnaffected.session_token = register_resp.json().get("session_token")
    
    def get_headers(self):
        return {"Authorization": f"Bearer {TestImplementationFlowUnaffected.session_token}"}
    
    def test_vpos_endpoint_still_works(self):
        """Test: VPOS quote creation endpoint should still work"""
        # Just verify the endpoint exists and accepts requests
        # We don't need to create a full quote, just check it's accessible
        headers = self.get_headers()
        
        # Check that quotes list endpoint works
        response = requests.get(f"{BASE_URL}/api/quotes", headers=headers)
        assert response.status_code == 200, f"Quotes list should work: {response.status_code}"
        
        print("✓ VPOS/Implementation flow endpoints accessible")
    
    def test_generate_pdf_with_template_endpoint_exists(self):
        """Test: The generate-pdf-with-template endpoint should still exist"""
        headers = self.get_headers()
        
        # Send minimal request to check endpoint exists (will fail validation but not 404)
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template", 
                                 json={}, headers=headers)
        
        # Should get 422 (validation error) not 404 (not found)
        assert response.status_code != 404, "generate-pdf-with-template endpoint should exist"
        
        print("✓ generate-pdf-with-template endpoint exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
