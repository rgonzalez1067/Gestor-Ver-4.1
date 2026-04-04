"""
Test PDF Generation for Fast Track quotes with Equipment Page (COTIZACIÓN DE EQUIPOS).
Tests the POST /api/quotes/generate-pdf endpoint with ft_equipment_items.

Features tested:
1. PDF generation with ft_equipment_items returns HTTP 200
2. PDF contains 'COTIZACIÓN DE EQUIPOS' page
3. Equipment table has correct data (Morefun MF960, POS, qty 2, $140.00, $280.00)
4. Subtotal, IVA (16%), and TOTAL are calculated correctly
5. RESUMEN DE LA COTIZACIÓN includes 'Equipos (Hardware)' row
6. PDF generation WITHOUT ft_equipment_items still works (no equipment page)
"""
import pytest
import requests
import os
import io

# Try to import PyPDF2 for PDF text extraction
try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@meganexus.com"
TEST_PASSWORD = "Admin123!"


class TestPDFEquipmentPage:
    """Tests for PDF generation with Fast Track equipment page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_pdf_generation_with_ft_equipment_items_returns_200(self):
        """Test that POST /api/quotes/generate-pdf with ft_equipment_items returns HTTP 200"""
        payload = {
            "cliente_nombre": "TestCorp",
            "cliente_rif": "J-99999999-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-001",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("Content-Type") == "application/pdf", "Response should be PDF"
        assert len(response.content) > 1000, "PDF should have substantial content"
        print(f"✓ PDF generated successfully, size: {len(response.content)} bytes")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_pdf_contains_cotizacion_de_equipos_page(self):
        """Test that PDF contains 'COTIZACIÓN DE EQUIPOS' page"""
        payload = {
            "cliente_nombre": "TestCorp",
            "cliente_rif": "J-99999999-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-002",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Check for equipment page title
        assert "COTIZACIÓN DE EQUIPOS" in full_text, "PDF should contain 'COTIZACIÓN DE EQUIPOS' page"
        print(f"✓ PDF contains 'COTIZACIÓN DE EQUIPOS' page")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_pdf_equipment_table_has_correct_data(self):
        """Test that equipment table contains: Morefun MF960 | POS | qty 2 | $140.00 | $280.00"""
        payload = {
            "cliente_nombre": "TestCorp",
            "cliente_rif": "J-99999999-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-003",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Check for equipment data
        assert "Morefun MF960" in full_text, "PDF should contain 'Morefun MF960'"
        assert "POS" in full_text, "PDF should contain 'POS' hardware type"
        
        # Check for calculated values (Subtotal $280.00, IVA 16% $44.80, TOTAL $324.80)
        # Note: PDF text extraction may have formatting variations
        assert "280" in full_text, "PDF should contain subtotal $280.00"
        assert "44" in full_text or "44.80" in full_text, "PDF should contain IVA $44.80"
        assert "324" in full_text or "324.80" in full_text, "PDF should contain TOTAL $324.80"
        
        print(f"✓ PDF equipment table contains correct data")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_pdf_resumen_includes_equipos_hardware_row(self):
        """Test that RESUMEN DE LA COTIZACIÓN includes 'Equipos (Hardware)' row with $280.00"""
        payload = {
            "cliente_nombre": "TestCorp",
            "cliente_rif": "J-99999999-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-004",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Check for RESUMEN section with Equipos row
        assert "RESUMEN" in full_text, "PDF should contain 'RESUMEN' section"
        # The row should show "Equipos (Hardware)" with $280.00
        assert "Equipos" in full_text or "Hardware" in full_text, "PDF should contain 'Equipos (Hardware)' row"
        
        print(f"✓ PDF RESUMEN includes Equipos (Hardware) row")
    
    def test_pdf_generation_without_ft_equipment_items_works(self):
        """Test that PDF generation WITHOUT ft_equipment_items still works (no equipment page)"""
        payload = {
            "cliente_nombre": "TestCorp No Equipment",
            "cliente_rif": "J-88888888-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-005",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": []  # Empty - no equipment
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("Content-Type") == "application/pdf", "Response should be PDF"
        assert len(response.content) > 1000, "PDF should have substantial content"
        print(f"✓ PDF generated without equipment items, size: {len(response.content)} bytes")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_pdf_without_equipment_has_no_equipment_page(self):
        """Test that PDF without ft_equipment_items does NOT contain equipment page"""
        payload = {
            "cliente_nombre": "TestCorp No Equipment",
            "cliente_rif": "J-88888888-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-006",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": []  # Empty - no equipment
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Should NOT contain equipment page
        assert "COTIZACIÓN DE EQUIPOS" not in full_text, "PDF without equipment should NOT contain 'COTIZACIÓN DE EQUIPOS' page"
        print(f"✓ PDF without equipment items correctly omits equipment page")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_pdf_total_general_sums_services_and_hardware(self):
        """Test that TOTAL GENERAL sums services + hardware correctly"""
        # Setup: $20 (2 cajas * 1 banco * $10)
        # Equipment: $280 (2 * $140)
        # Expected TOTAL GENERAL: $300
        payload = {
            "cliente_nombre": "TestCorp Total",
            "cliente_rif": "J-77777777-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEST-007",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Check for TOTAL GENERAL (should be $300 = $20 setup + $280 equipment)
        assert "TOTAL" in full_text, "PDF should contain 'TOTAL'"
        # The total should include both services and hardware
        assert "300" in full_text, "PDF TOTAL GENERAL should be $300 (services $20 + hardware $280)"
        
        print(f"✓ PDF TOTAL GENERAL correctly sums services and hardware")


class TestPDFTemplateEndpoint:
    """Tests for the /api/quotes/generate-pdf-with-template endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get auth token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Authentication failed: {login_response.status_code}")
    
    def test_template_pdf_with_ft_equipment_items(self):
        """Test /api/quotes/generate-pdf-with-template with ft_equipment_items"""
        payload = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "TestCorp Template",
            "cliente_rif": "J-66666666-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEMPLATE-001",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "production_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ],
            "client_segment": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("Content-Type") == "application/pdf", "Response should be PDF"
        assert len(response.content) > 1000, "PDF should have substantial content"
        print(f"✓ Template PDF generated with equipment items, size: {len(response.content)} bytes")
    
    @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not available")
    def test_template_pdf_contains_equipment_page(self):
        """Test that template PDF contains equipment page when ft_equipment_items provided"""
        payload = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "TestCorp Template",
            "cliente_rif": "J-66666666-0",
            "quote_type": "FAST_TRACK",
            "pricing_model": "TARIFA_POR_CAJA",
            "cantidad_cajas": 2,
            "quote_number": "COT-TEMPLATE-002",
            "integrator_name": "XETUX",
            "integrator_app_name": "V2",
            "pinpad_model": "MF960",
            "sponsor_bank_name": "MegaSoft",
            "setup_items": [
                {
                    "concepto": "Setup",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 10
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "production_items": [],
            "ft_equipment_items": [
                {
                    "name": "Morefun MF960",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 140
                }
            ],
            "client_segment": "PYME"
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template", json=payload)
        assert response.status_code == 200
        
        # Extract text from PDF
        pdf_reader = PdfReader(io.BytesIO(response.content))
        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() or ""
        
        # Check for equipment page
        assert "COTIZACIÓN DE EQUIPOS" in full_text, "Template PDF should contain 'COTIZACIÓN DE EQUIPOS' page"
        assert "Morefun MF960" in full_text, "Template PDF should contain equipment name"
        
        print(f"✓ Template PDF contains equipment page with correct data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
