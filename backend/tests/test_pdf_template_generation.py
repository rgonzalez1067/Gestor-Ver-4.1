# ruff: noqa
"""
Backend Tests for Dynamic PDF Generation with Templates
=======================================================
Tests the new PDF generation system that uses uploaded templates.

Features to test:
1. GET /api/config/templates - Returns template status
2. GET /api/quotes/check-template/{template_type} - Check specific template
3. POST /api/quotes/generate-pdf-with-template - Generate PDF with template

Template: vpos_pyme.pdf (already uploaded in /app/backend/uploads/templates/)
"""

import pytest
import requests
import os
import json
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "password123"


class TestPDFTemplateGeneration:
    """Tests for the Dynamic PDF Quote Generator with Templates"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
        
        data = response.json()
        return data.get("session_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, session_token):
        """Returns headers with authentication"""
        return {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json"
        }
    
    # ==================== Test 1: GET /api/config/templates ====================
    def test_get_templates_status(self, auth_headers):
        """
        Test: GET /api/config/templates returns template status correctly
        Expected: 200 OK with template status dictionary
        """
        response = requests.get(
            f"{BASE_URL}/api/config/templates",
            headers=auth_headers
        )
        
        # Assert status code
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Assert response is JSON dictionary
        data = response.json()
        assert isinstance(data, dict), "Response should be a dictionary"
        
        # Assert has template types
        print(f"Template status response: {json.dumps(data, indent=2)}")
        
        return data
    
    # ==================== Test 2: vpos_pyme template availability ====================
    def test_vpos_pyme_template_available(self, auth_headers):
        """
        Test: The vpos_pyme template should be marked as available (exists: true)
        Expected: vpos_pyme has exists: true
        """
        response = requests.get(
            f"{BASE_URL}/api/config/templates",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check vpos_pyme exists in response
        assert "vpos_pyme" in data, f"vpos_pyme should be in response. Keys: {list(data.keys())}"
        
        # Check vpos_pyme is marked as existing
        vpos_pyme_status = data.get("vpos_pyme", {})
        assert vpos_pyme_status.get("exists") == True, f"vpos_pyme should exist. Status: {vpos_pyme_status}"
        
        print(f"vpos_pyme template status: {vpos_pyme_status}")
    
    # ==================== Test 3: Check template endpoint ====================
    def test_check_template_endpoint_vpos_pyme(self, auth_headers):
        """
        Test: GET /api/quotes/check-template/vpos_pyme returns available
        Expected: available: true
        """
        response = requests.get(
            f"{BASE_URL}/api/quotes/check-template/vpos_pyme",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("template_type") == "vpos_pyme"
        assert data.get("available") == True, f"vpos_pyme should be available: {data}"
        
        print(f"Check template response: {json.dumps(data, indent=2)}")
    
    # ==================== Test 4: Generate PDF with template ====================
    def test_generate_pdf_with_template(self, auth_headers):
        """
        Test: POST /api/quotes/generate-pdf-with-template generates a valid PDF
        Expected: 200 OK with PDF content, size > 500KB (due to template)
        """
        # Prepare test data for PDF generation
        pdf_request_data = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "Empresa Test S.A.",
            "cliente_rif": "J-12345678-9",
            "cliente_contacto": "Juan Pérez",
            "cliente_address": "Av. Principal, Caracas",
            "integrator_name": "Integrador Tech",
            "integrator_app_name": "POS Manager Pro",
            "pinpad_model": "PAX S80",
            "sponsor_bank_name": "Banco Test",
            "cantidad_cajas": 5,
            "quote_number": f"COT-TEST-{datetime.now().strftime('%Y%m%d%H%M')}",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 100.00,
                    "total": 500.00,
                    "bank_name": None
                },
                {
                    "concepto": "Configuración dispositivo (Pinpad o POS)",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 50.00,
                    "total": 250.00,
                    "bank_name": None
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 25.00,
                    "total": 125.00,
                    "bank_name": None
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend (SSL Público o VPN)",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 15.00,
                    "total": 75.00,
                    "bank_name": None
                }
            ],
            "descuento": 0,
            "notes": "Cotización de prueba para testing automatizado",
            "quote_type": "VPOS",
            "pricing_model": "conventional"
        }
        
        # Make request
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            headers={
                "Authorization": auth_headers["Authorization"],
                "Content-Type": "application/json",
                "Accept": "application/pdf"
            },
            json=pdf_request_data
        )
        
        # Assert status code
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Assert content type is PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Assert PDF starts with %PDF
        pdf_content = response.content
        assert pdf_content[:4] == b"%PDF", f"PDF should start with %PDF, got: {pdf_content[:20]}"
        
        # Assert PDF size is reasonable (> 500KB due to template)
        pdf_size = len(pdf_content)
        print(f"Generated PDF size: {pdf_size} bytes ({pdf_size/1024:.1f} KB)")
        
        # The template itself is ~935KB, so the generated PDF should be substantial
        assert pdf_size > 500 * 1024, f"PDF size should be > 500KB (template-based). Got: {pdf_size/1024:.1f} KB"
        
        # Check X-Template-Used header
        template_used = response.headers.get("X-Template-Used")
        assert template_used == "vpos_pyme", f"X-Template-Used should be vpos_pyme, got: {template_used}"
        
        print(f"PDF generated successfully with template: {template_used}")
        print(f"Content-Disposition: {response.headers.get('content-disposition', 'N/A')}")
    
    # ==================== Test 5: Generate PDF without template (404) ====================
    def test_generate_pdf_nonexistent_template(self, auth_headers):
        """
        Test: POST /api/quotes/generate-pdf-with-template with non-existent template
        Expected: 404 error
        """
        pdf_request_data = {
            "template_type": "nonexistent_template",
            "cliente_nombre": "Test Client",
            "cliente_rif": "J-12345678-9",
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            headers=auth_headers,
            json=pdf_request_data
        )
        
        # Should return 404 for non-existent template
        assert response.status_code == 404, f"Expected 404 for non-existent template, got {response.status_code}"
        
        error_detail = response.json().get("detail", "")
        assert "plantilla" in error_detail.lower() or "template" in error_detail.lower(), \
            f"Error should mention template. Got: {error_detail}"
        
        print(f"Non-existent template handled correctly: {error_detail}")
    
    # ==================== Test 6: Preview PDF with template ====================
    def test_preview_pdf_with_template(self, auth_headers):
        """
        Test: POST /api/quotes/preview-pdf-with-template generates inline PDF
        Expected: 200 OK with PDF content, inline disposition
        """
        pdf_request_data = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "Preview Client",
            "cliente_rif": "J-11111111-1",
            "cliente_contacto": "Preview Contact",
            "integrator_name": "Preview Integrator",
            "integrator_app_name": "Preview App",
            "cantidad_cajas": 1,
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            headers={
                "Authorization": auth_headers["Authorization"],
                "Content-Type": "application/json",
                "Accept": "application/pdf"
            },
            json=pdf_request_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        
        # Should be PDF
        assert response.content[:4] == b"%PDF", "Should be valid PDF"
        
        # Check Content-Disposition is inline (for preview)
        disposition = response.headers.get("content-disposition", "")
        assert "inline" in disposition.lower(), f"Preview should have inline disposition, got: {disposition}"
        
        print(f"Preview PDF generated, size: {len(response.content)/1024:.1f} KB")
    
    # ==================== Test 7: Check non-existent template ====================
    def test_check_nonexistent_template(self, auth_headers):
        """
        Test: GET /api/quotes/check-template/{non_existent} returns available: false
        """
        response = requests.get(
            f"{BASE_URL}/api/quotes/check-template/payment_gateway",
            headers=auth_headers
        )
        
        # Endpoint should still return 200 (not 404)
        assert response.status_code == 200, f"Check template should return 200 even for missing, got {response.status_code}"
        
        data = response.json()
        # payment_gateway template likely doesn't exist yet
        print(f"payment_gateway template check: {data}")
        # Note: We can't assert available is False because it might exist
        assert "available" in data, "Response should include 'available' field"
        assert "template_type" in data, "Response should include 'template_type' field"


class TestPDFTemplateGenerationWithData:
    """Tests PDF generation with complete quote data"""
    
    @pytest.fixture(scope="class")
    def session_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code}")
        
        return response.json().get("session_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, session_token):
        return {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json"
        }
    
    def test_pdf_with_multiple_banks(self, auth_headers):
        """
        Test: Generate PDF with multiple banks in setup/recurring items
        Tests the bank distribution matrix in page 2
        """
        pdf_request_data = {
            "template_type": "vpos_pyme",
            "cliente_nombre": "Multi-Bank Corp S.A.",
            "cliente_rif": "J-98765432-1",
            "cliente_contacto": "María García",
            "cliente_address": "Torre Norte, Piso 15",
            "integrator_name": "MultiPay Systems",
            "integrator_app_name": "UnifiedPOS",
            "pinpad_model": "Ingenico Lane 3000",
            "sponsor_bank_name": "Banco Principal",
            "cantidad_cajas": 10,
            "quote_number": f"COT-MULTI-{datetime.now().strftime('%H%M%S')}",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 3,
                    "tarifa": 100.00,
                    "total": 3000.00,
                    "bank_name": None
                },
                {
                    "concepto": "Configuración Medio de Pago - Banco A",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 75.00,
                    "total": 750.00,
                    "bank_name": "Banco A"
                },
                {
                    "concepto": "Configuración Medio de Pago - Banco B",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 75.00,
                    "total": 750.00,
                    "bank_name": "Banco B"
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 30.00,
                    "total": 300.00,
                    "bank_name": None
                },
                {
                    "concepto": "Mantenimiento Medio de Pago - Banco A",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 20.00,
                    "total": 200.00,
                    "bank_name": "Banco A"
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 50.00,
                    "total": 500.00,
                    "bank_name": None
                }
            ],
            "descuento": 10,
            "notes": "Cotización con múltiples bancos y descuento aplicado",
            "quote_type": "VPOS",
            "pricing_model": "conventional"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            headers={
                "Authorization": auth_headers["Authorization"],
                "Content-Type": "application/json",
                "Accept": "application/pdf"
            },
            json=pdf_request_data
        )
        
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text[:500]}"
        assert response.content[:4] == b"%PDF", "Should be valid PDF"
        
        pdf_size = len(response.content)
        print(f"Multi-bank PDF generated: {pdf_size/1024:.1f} KB")
        assert pdf_size > 500 * 1024, f"PDF should be > 500KB, got {pdf_size/1024:.1f} KB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
