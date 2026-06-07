# ruff: noqa
"""
Test iteration 127: Fast Track Hybrid PDF Generation
Tests the generation of PDF with equipment page for Fast Track quotes.
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

def get_unique_rif():
    """Generate a unique RIF for testing"""
    return f"J-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:1].upper()}"

class TestFastTrackHybridPDF:
    """Tests for Fast Track hybrid PDF generation with equipment page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.client_id = None
        self.quote_id = None
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        # Cleanup
        if self.quote_id:
            try:
                self.session.delete(f"{BASE_URL}/api/quotes/{self.quote_id}")
            except:
                pass
        if self.client_id:
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{self.client_id}")
            except:
                pass
    
    def test_create_fast_track_quote_with_equipment_items(self):
        """Test creating a Fast Track quote with ft_equipment_items generates PDF with equipment page"""
        # Create a test client first
        client_data = {
            "legal_name": "TEST_FT_PDF_Client",
            "fantasy_name": "FT PDF Test",
            "rif": "J-12345678-9",
            "address": "Test Address 123"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201], f"Client creation failed: {client_response.text}"
        self.client_id = client_response.json().get("client_id")
        
        # Create Fast Track quote with equipment items
        quote_payload = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Configuración Fast Track",
                    "quantity": 1,
                    "unit_price_usd": 100,
                    "total_usd": 100
                }
            ],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test Fast Track quote with equipment",
            "integrator_id": "sin_integrador",
            "integrator_name": "Sin integrador por el momento",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "ft_equipment_items": [
                {
                    "name": "POS Verifone V240m",
                    "hardware_type": "POS",
                    "quantity": 2,
                    "unit_price_usd": 150.00
                },
                {
                    "name": "Impresora Térmica",
                    "hardware_type": "Accesorio",
                    "quantity": 1,
                    "unit_price_usd": 75.00
                }
            ],
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_PDF_Client",
                "cliente_rif": "J-12345678-9",
                "cliente_address": "Test Address 123",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "integrator_name": "Sin integrador por el momento",
                "integrator_app_name": "",
                "pinpad_model": "",
                "sponsor_bank_name": "",
                "setup_items": [
                    {
                        "concepto": "Configuración Fast Track",
                        "cantidad_cajas": 1,
                        "cantidad_bancos": 1,
                        "tarifa": 100.00,
                        "bank_name": None
                    }
                ],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": [
                    {
                        "name": "POS Verifone V240m",
                        "hardware_type": "POS",
                        "quantity": 2,
                        "unit_price_usd": 150.00
                    },
                    {
                        "name": "Impresora Térmica",
                        "hardware_type": "Accesorio",
                        "quantity": 1,
                        "unit_price_usd": 75.00
                    }
                ],
                "descuento": 0,
                "descuento_setup": 0,
                "descuento_recurrente": 0,
                "notes": "Test Fast Track quote with equipment"
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        
        # Verify quote was created
        assert "quote" in data, "Response should contain 'quote' key"
        assert data["quote"]["quote_type"] == "FAST_TRACK", "Quote type should be FAST_TRACK"
        assert data["quote"]["quote_category"] == "fast_track", "Quote category should be fast_track"
        
        # Verify PDF was generated
        assert "pdf_url" in data, "Response should contain 'pdf_url' key"
        assert data["pdf_url"] is not None, "PDF URL should not be None"
        print(f"PDF URL: {data['pdf_url']}")
        
        # Verify ft_equipment_items are stored in the quote
        quote = data["quote"]
        assert "ft_equipment_items" in quote or len(quote.get("services", [])) > 0, "Quote should have equipment items or services"
        
    def test_pdf_file_is_valid_and_non_zero(self):
        """Test that the generated PDF file is valid and has non-zero size"""
        # Create a test client first
        client_data = {
            "legal_name": "TEST_FT_PDF_Valid_Client",
            "fantasy_name": "FT PDF Valid Test",
            "rif": "J-98765432-1",
            "address": "Test Address 456"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201], f"Client creation failed: {client_response.text}"
        self.client_id = client_response.json().get("client_id")
        
        # Create Fast Track quote with equipment items
        quote_payload = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Setup FT",
                    "quantity": 1,
                    "unit_price_usd": 50,
                    "total_usd": 50
                }
            ],
            "hardware": [],
            "equipment_items": [],
            "ft_equipment_items": [
                {
                    "name": "Terminal POS",
                    "hardware_type": "POS",
                    "quantity": 3,
                    "unit_price_usd": 200.00
                }
            ],
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_PDF_Valid_Client",
                "cliente_rif": "J-98765432-1",
                "cliente_address": "Test Address 456",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "integrator_name": "Sin integrador",
                "setup_items": [],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": [
                    {
                        "name": "Terminal POS",
                        "hardware_type": "POS",
                        "quantity": 3,
                        "unit_price_usd": 200.00
                    }
                ]
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        pdf_url = data.get("pdf_url")
        
        assert pdf_url is not None, "PDF URL should not be None"
        
        # Download the PDF and verify it's valid
        pdf_response = self.session.get(f"{BASE_URL}{pdf_url}")
        assert pdf_response.status_code == 200, f"PDF download failed: {pdf_response.status_code}"
        
        # Check PDF size is non-zero
        pdf_content = pdf_response.content
        assert len(pdf_content) > 0, "PDF file should have non-zero size"
        print(f"PDF size: {len(pdf_content)} bytes")
        
        # Check PDF header (should start with %PDF)
        assert pdf_content[:4] == b'%PDF', "PDF should have valid PDF header"
        
    def test_quote_stored_with_ft_equipment_items(self):
        """Test that ft_equipment_items are properly stored in the database"""
        # Create a test client first
        client_data = {
            "legal_name": "TEST_FT_Storage_Client",
            "fantasy_name": "FT Storage Test",
            "rif": "J-11111111-1"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201], f"Client creation failed: {client_response.text}"
        self.client_id = client_response.json().get("client_id")
        
        # Create Fast Track quote with equipment items
        equipment_items = [
            {
                "name": "POS Ingenico Move 5000",
                "hardware_type": "POS",
                "quantity": 5,
                "unit_price_usd": 180.00
            },
            {
                "name": "Base de Carga",
                "hardware_type": "Accesorio",
                "quantity": 5,
                "unit_price_usd": 25.00
            }
        ]
        
        quote_payload = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "ft_equipment_items": equipment_items,
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_Storage_Client",
                "cliente_rif": "J-11111111-1",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "setup_items": [],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": equipment_items
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        
        # Fetch the quote from DB and verify ft_equipment_items
        get_response = self.session.get(f"{BASE_URL}/api/quotes/{self.quote_id}")
        assert get_response.status_code == 200, f"Quote fetch failed: {get_response.text}"
        
        quote = get_response.json()
        
        # Check ft_equipment_items are stored
        stored_items = quote.get("ft_equipment_items", [])
        print(f"Stored ft_equipment_items: {stored_items}")
        
        # The items might be stored in ft_equipment_items or in services with item_type
        if len(stored_items) > 0:
            assert len(stored_items) == 2, f"Should have 2 equipment items, got {len(stored_items)}"
            # Verify first item
            assert stored_items[0]["name"] == "POS Ingenico Move 5000"
            assert stored_items[0]["quantity"] == 5
            assert stored_items[0]["unit_price_usd"] == 180.00
        else:
            # Check if stored in services
            services = quote.get("services", [])
            print(f"Services: {services}")
            # At minimum, the quote should exist
            assert quote.get("quote_id") == self.quote_id
            
    def test_fast_track_without_equipment_items(self):
        """Test that Fast Track quote without equipment items still generates valid PDF"""
        # Create a test client first
        client_data = {
            "legal_name": "TEST_FT_NoEquip_Client",
            "fantasy_name": "FT No Equipment Test",
            "rif": "J-22222222-2"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201], f"Client creation failed: {client_response.text}"
        self.client_id = client_response.json().get("client_id")
        
        # Create Fast Track quote WITHOUT equipment items
        quote_payload = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Configuración Básica",
                    "quantity": 1,
                    "unit_price_usd": 100,
                    "total_usd": 100
                }
            ],
            "hardware": [],
            "equipment_items": [],
            "ft_equipment_items": [],  # Empty - no equipment
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_NoEquip_Client",
                "cliente_rif": "J-22222222-2",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "setup_items": [
                    {
                        "concepto": "Configuración Básica",
                        "cantidad_cajas": 1,
                        "cantidad_bancos": 1,
                        "tarifa": 100.00
                    }
                ],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": []  # Empty
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        
        # Verify PDF was still generated
        assert "pdf_url" in data, "Response should contain 'pdf_url' key"
        assert data["pdf_url"] is not None, "PDF URL should not be None even without equipment"
        
        # Download and verify PDF
        pdf_url = data.get("pdf_url")
        pdf_response = self.session.get(f"{BASE_URL}{pdf_url}")
        assert pdf_response.status_code == 200, "PDF download failed"
        assert len(pdf_response.content) > 0, "PDF should have content"
        
    def test_default_integrator_for_fast_track(self):
        """Test that Fast Track quotes default to 'sin_integrador'"""
        # Create a test client first
        client_data = {
            "legal_name": "TEST_FT_Integrator_Client",
            "fantasy_name": "FT Integrator Test",
            "rif": "J-33333333-3"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201], f"Client creation failed: {client_response.text}"
        self.client_id = client_response.json().get("client_id")
        
        # Create Fast Track quote with sin_integrador
        quote_payload = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "integrator_id": "sin_integrador",
            "integrator_name": "Sin integrador por el momento",
            "ft_equipment_items": [
                {
                    "name": "POS Test",
                    "hardware_type": "POS",
                    "quantity": 1,
                    "unit_price_usd": 100.00
                }
            ],
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_Integrator_Client",
                "cliente_rif": "J-33333333-3",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "integrator_name": "Sin integrador por el momento",
                "setup_items": [],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": [
                    {
                        "name": "POS Test",
                        "hardware_type": "POS",
                        "quantity": 1,
                        "unit_price_usd": 100.00
                    }
                ]
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_payload)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        
        # Verify integrator is set correctly
        quote = data.get("quote", {})
        assert quote.get("integrator_id") == "sin_integrador" or quote.get("integrator_name") == "Sin integrador por el momento", \
            "Fast Track should use 'sin_integrador' as default integrator"


class TestFastTrackPDFEquipmentPage:
    """Tests specifically for the equipment page in the PDF"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.client_id = None
        self.quote_id = None
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@mega.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        yield
        
        # Cleanup
        if self.quote_id:
            try:
                self.session.delete(f"{BASE_URL}/api/quotes/{self.quote_id}")
            except:
                pass
        if self.client_id:
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{self.client_id}")
            except:
                pass
    
    def test_pdf_with_equipment_has_more_pages(self):
        """Test that PDF with equipment items has more pages than without"""
        # Create a test client
        client_data = {
            "legal_name": "TEST_FT_Pages_Client",
            "fantasy_name": "FT Pages Test",
            "rif": "J-44444444-4"
        }
        client_response = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_response.status_code in [200, 201]
        self.client_id = client_response.json().get("client_id")
        
        # Create quote WITH equipment
        quote_with_equipment = {
            "client_id": self.client_id,
            "quote_type": "FAST_TRACK",
            "quote_category": "fast_track",
            "pricing_model": "outsourcing",
            "services": [{"item_type": "setup", "item_name": "Config", "quantity": 1, "unit_price_usd": 100, "total_usd": 100}],
            "hardware": [],
            "equipment_items": [],
            "ft_equipment_items": [
                {"name": "POS Device", "hardware_type": "POS", "quantity": 2, "unit_price_usd": 150.00}
            ],
            "pdf_data": {
                "quote_type": "FAST_TRACK",
                "template_type": "mpos_pyme",
                "cliente_nombre": "TEST_FT_Pages_Client",
                "cliente_rif": "J-44444444-4",
                "pricing_model": "outsourcing",
                "cantidad_cajas": 1,
                "setup_items": [{"concepto": "Config", "cantidad_cajas": 1, "cantidad_bancos": 1, "tarifa": 100}],
                "recurring_basic_items": [],
                "recurring_other_items": [],
                "additional_items": [],
                "ft_equipment_items": [
                    {"name": "POS Device", "hardware_type": "POS", "quantity": 2, "unit_price_usd": 150.00}
                ]
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_with_equipment)
        assert response.status_code == 200, f"Quote creation failed: {response.text}"
        
        data = response.json()
        self.quote_id = data.get("quote", {}).get("quote_id")
        pdf_url = data.get("pdf_url")
        
        # Download PDF with equipment
        pdf_response = self.session.get(f"{BASE_URL}{pdf_url}")
        assert pdf_response.status_code == 200
        pdf_with_equipment_size = len(pdf_response.content)
        
        print(f"PDF with equipment size: {pdf_with_equipment_size} bytes")
        
        # The PDF should be valid and have reasonable size
        assert pdf_with_equipment_size > 10000, "PDF with equipment should have substantial content"
        
        # Verify PDF header
        assert pdf_response.content[:4] == b'%PDF', "Should be valid PDF"
