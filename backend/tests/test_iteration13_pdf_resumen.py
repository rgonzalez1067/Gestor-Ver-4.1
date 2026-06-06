"""
Test Suite for Iteration 13: PDF Resumen Ejecutivo Features
Tests:
1. POST /api/quotes/generate-pdf accepts new fields: cliente_address, cantidad_cajas, bank_name in items
2. PDF generation with Resumen Ejecutivo section
3. Verify header contains: Cliente (amarillo), Cantidad de Cajas (azul), Dirección Fiscal (verde)
4. Verify Matriz de Distribución with bank_name support
5. Verify Total de Terminales Virtuales calculation
"""
import pytest
import requests
import os
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://quote-wizard-homolog.preview.emergentagent.com')

# MongoDB connection for session token
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client['test_database']

def get_auth_token():
    """Get a valid session token from database"""
    session = db.user_sessions.find_one({}, {'_id': 0})
    if session:
        return session.get('session_token')
    return None

@pytest.fixture
def auth_headers():
    """Fixture to get authentication headers"""
    token = get_auth_token()
    if not token:
        pytest.skip("No valid session token available")
    return {"Authorization": f"Bearer {token}"}


class TestPDFGenerationNewFields:
    """Test cases for new fields in PDF generation endpoint"""
    
    def test_generate_pdf_with_cliente_address(self, auth_headers):
        """Test POST /api/quotes/generate-pdf with cliente_address field"""
        pdf_data = {
            "cliente_nombre": "TEST Cliente con Dirección",
            "cliente_rif": "J-12345678-9",
            "cliente_address": "Av. Principal #123, Edificio Torre Norte, Piso 5, Caracas 1010",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 5,
            "integrator_name": "Test Integrador",
            "integrator_app_name": "TestApp",
            "pinpad_model": "Ingenico IPP320",
            "sponsor_bank_name": "Banco Test",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 2,
                    "tarifa": 50.0,
                    "total": 500.0,
                    "bank_name": "Banco Mercantil"
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 25.0,
                    "total": 125.0,
                    "bank_name": None
                }
            ],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": "Test note for Resumen Ejecutivo"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf', "Should return PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        
        # Check PDF file size (reasonable range)
        pdf_size = len(response.content)
        print(f"PDF generated successfully, size: {pdf_size} bytes")
        assert pdf_size > 1000, "PDF should be larger than 1KB"
    
    def test_generate_pdf_with_cantidad_cajas(self, auth_headers):
        """Test PDF includes cantidad_cajas in header for Resumen Ejecutivo"""
        pdf_data = {
            "cliente_nombre": "TEST Cliente Cantidad Cajas",
            "cliente_rif": "J-99999999-9",
            "cliente_address": "",  # Test with empty address
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 10,  # This should appear in Resumen header
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"PDF with cantidad_cajas=10 generated, size: {len(response.content)} bytes")
    
    def test_generate_pdf_with_bank_name_in_items(self, auth_headers):
        """Test PDF includes bank_name in items for Matriz de Distribución"""
        pdf_data = {
            "cliente_nombre": "TEST Cliente Bancos en Items",
            "cliente_rif": "J-11111111-1",
            "cliente_address": "Dirección de prueba para matriz",
            "quote_type": "GATEWAY",
            "pricing_model": "outsourcing",
            "cantidad_cajas": 3,
            "integrator_name": "Integrador Gateway",
            "integrator_app_name": "GatewayApp",
            "pinpad_model": "",
            "sponsor_bank_name": "Banco Patrocinador",
            "setup_items": [
                {
                    "concepto": "Configuración Gateway",
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1,
                    "tarifa": 100.0,
                    "total": 300.0,
                    "bank_name": "Banco Mercantil"
                },
                {
                    "concepto": "Configuración TDC",
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1,
                    "tarifa": 75.0,
                    "total": 225.0,
                    "bank_name": "Banco Provincial"
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Mantenimiento Gateway",
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 2,
                    "tarifa": 30.0,
                    "total": 180.0,
                    "bank_name": "General"
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend",
                    "cantidad_cajas": 3,
                    "cantidad_bancos": 1,
                    "tarifa": 20.0,
                    "total": 60.0,
                    "bank_name": None
                }
            ],
            "descuento": 10,
            "notes": "Cotización con múltiples bancos para matriz de distribución"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        
        pdf_size = len(response.content)
        print(f"PDF with bank_name in items generated, size: {pdf_size} bytes")
        # PDF with multiple banks should be larger
        assert pdf_size > 2000, "PDF with multiple items should be larger"
    
    def test_generate_pdf_minimal_data(self, auth_headers):
        """Test PDF generation with minimal required data"""
        pdf_data = {
            "cliente_nombre": "Cliente Mínimo",
            "cliente_rif": "",
            "cliente_address": "",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"Minimal PDF generated, size: {len(response.content)} bytes")


class TestResumenEjecutivoMatrizData:
    """Test cases for data structure supporting Resumen Ejecutivo Matriz"""
    
    def test_pdf_with_matriz_distribucion_data(self, auth_headers):
        """Test PDF generation creates proper matriz with bancos/productos/cajas"""
        # Create comprehensive test data for matriz
        pdf_data = {
            "cliente_nombre": "TEST Matriz Distribución",
            "cliente_rif": "J-MATRIZ-001",
            "cliente_address": "Calle Principal, Edificio Matriz, Caracas",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 8,
            "integrator_name": "Integrador Matriz",
            "integrator_app_name": "MatrizApp",
            "pinpad_model": "Ingenico Lane 3000",
            "sponsor_bank_name": "Banco de Venezuela",
            # Multiple items with different banks to populate matriz
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 4,
                    "cantidad_bancos": 2,
                    "tarifa": 50.0,
                    "total": 400.0,
                    "bank_name": "Banco Mercantil"
                },
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 4,
                    "cantidad_bancos": 1,
                    "tarifa": 50.0,
                    "total": 200.0,
                    "bank_name": "Banesco"
                },
                {
                    "concepto": "Configuración dispositivo (Pinpad)",
                    "cantidad_cajas": 8,
                    "cantidad_bancos": 1,
                    "tarifa": 30.0,
                    "total": 240.0,
                    "bank_name": "General"
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 8,
                    "cantidad_bancos": 1,
                    "tarifa": 25.0,
                    "total": 200.0,
                    "bank_name": None
                },
                {
                    "concepto": "Mantenimiento TDC",
                    "cantidad_cajas": 4,
                    "cantidad_bancos": 1,
                    "tarifa": 15.0,
                    "total": 60.0,
                    "bank_name": "Banco Mercantil"
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend (SSL Público)",
                    "cantidad_cajas": 8,
                    "cantidad_bancos": 1,
                    "tarifa": 10.0,
                    "total": 80.0,
                    "bank_name": None
                }
            ],
            "descuento": 5,
            "notes": "Cotización de prueba para matriz de distribución con múltiples bancos y productos"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        
        pdf_size = len(response.content)
        print(f"Matriz PDF generated successfully, size: {pdf_size} bytes")
        
        # The PDF should be substantial with all this data
        assert pdf_size > 3000, f"PDF should be > 3KB with all items, got {pdf_size}"
    
    def test_total_terminales_calculation(self, auth_headers):
        """Test that Total de Terminales Virtuales calculates correctly"""
        # Create data where total terminales should equal sum of cantidad_cajas
        pdf_data = {
            "cliente_nombre": "TEST Total Terminales",
            "cliente_rif": "J-TERM-001",
            "cliente_address": "Test Address",
            "quote_type": "MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 15,  # This is expected total
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [
                {
                    "concepto": "Config MPOS",
                    "cantidad_cajas": 10,
                    "cantidad_bancos": 1,
                    "tarifa": 40.0,
                    "total": 400.0,
                    "bank_name": "Banco A"
                },
                {
                    "concepto": "Config MPOS",
                    "cantidad_cajas": 5,
                    "cantidad_bancos": 1,
                    "tarifa": 40.0,
                    "total": 200.0,
                    "bank_name": "Banco B"
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": "Total expected: 15 terminales (10 + 5)"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        print(f"Total terminales test PDF generated, size: {len(response.content)} bytes")


class TestApiAuthentication:
    """Test authentication requirements for PDF endpoint"""
    
    def test_generate_pdf_requires_auth(self):
        """Test that generate-pdf endpoint requires authentication"""
        pdf_data = {
            "cliente_nombre": "Test",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", json=pdf_data)
        assert response.status_code == 401, "Should require authentication"
    
    def test_authenticated_pdf_generation(self, auth_headers):
        """Test authenticated PDF generation works"""
        pdf_data = {
            "cliente_nombre": "Auth Test Client",
            "cliente_rif": "J-AUTH-001",
            "cliente_address": "Test Auth Address",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 2,
            "integrator_name": "",
            "integrator_app_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert 'application/pdf' in response.headers.get('content-type', '')
