# ruff: noqa
"""
Iteration 86 - Equipment Quote PDF Bug Fixes Tests
Bug #1: PDF generated now saves to server and creates attachment automatically
Bug #2: UI freeze fix (tested via Playwright in frontend tests)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEquipmentQuotePDFBugs:
    """Test Bug #1 Fix: Equipment PDF generation creates quote with attachment"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@gestor.com",
            "password": "Admin2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get a test client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        assert len(clients) > 0, "No clients found for testing"
        self.test_client = clients[0]
        
        # Get hardware items
        hw_resp = self.session.get(f"{BASE_URL}/api/hardware")
        assert hw_resp.status_code == 200
        self.hardware = hw_resp.json()
        
        yield
        
        # Cleanup: Delete test quotes created during tests
        if hasattr(self, 'created_quote_ids'):
            for quote_id in self.created_quote_ids:
                try:
                    self.session.delete(f"{BASE_URL}/api/quotes/{quote_id}")
                except:
                    pass
    
    def test_01_generate_equipment_pdf_returns_pdf_content_type(self):
        """Bug #1 Fix: Endpoint should return application/pdf"""
        # Find a POS hardware item
        pos_items = [h for h in self.hardware if h.get('type') == 'POS']
        if not pos_items:
            pytest.skip("No POS hardware items available for testing")
        
        item = pos_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "cliente_address": self.test_client.get('address', ''),
            "equipment_type": "POS",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": item.get('type', 'POS'),
                "quantity": 1,
                "unit_price_usd": item.get('price_usd', 100),
                "total_usd": item.get('price_usd', 100)
            }],
            "notes": "TEST_iteration86_pdf_generation"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Content type assertion
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected application/pdf, got {content_type}"
        
        # PDF content assertion (PDF starts with %PDF)
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        # Store quote ID for cleanup
        quote_id = response.headers.get('x-quote-id')
        if quote_id:
            if not hasattr(self, 'created_quote_ids'):
                self.created_quote_ids = []
            self.created_quote_ids.append(quote_id)
    
    def test_02_generate_equipment_pdf_has_quote_headers(self):
        """Bug #1 Fix: Response should include X-Quote-Id and X-Quote-Number headers"""
        pos_items = [h for h in self.hardware if h.get('type') == 'POS']
        if not pos_items:
            pytest.skip("No POS hardware items available")
        
        item = pos_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "POS",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": "POS",
                "quantity": 2,
                "unit_price_usd": item.get('price_usd', 100),
                "total_usd": item.get('price_usd', 100) * 2
            }],
            "notes": "TEST_iteration86_headers"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        # X-Quote-Id header assertion
        quote_id = response.headers.get('x-quote-id')
        assert quote_id is not None, "X-Quote-Id header is missing"
        assert quote_id.startswith('quo_'), f"Invalid quote_id format: {quote_id}"
        
        # X-Quote-Number header assertion  
        quote_number = response.headers.get('x-quote-number')
        assert quote_number is not None, "X-Quote-Number header is missing"
        assert 'COT-' in quote_number, f"Invalid quote_number format: {quote_number}"
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_03_generate_equipment_pdf_creates_quote_in_db(self):
        """Bug #1 Fix: Quote should be created in database with quote_pdf_url"""
        pos_items = [h for h in self.hardware if h.get('type') == 'POS']
        if not pos_items:
            pytest.skip("No POS hardware items available")
        
        item = pos_items[0]
        test_client_name = self.test_client.get('legal_name', 'Test Client')
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": test_client_name,
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "POS",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": "POS",
                "quantity": 1,
                "unit_price_usd": item.get('price_usd', 100),
                "total_usd": item.get('price_usd', 100)
            }],
            "notes": "TEST_iteration86_db_creation"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        quote_id = response.headers.get('x-quote-id')
        assert quote_id is not None
        
        # GET the quote to verify it exists in DB
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200, f"Quote not found in DB: {quote_response.status_code}"
        
        quote = quote_response.json()
        
        # Data assertions
        assert quote['quote_id'] == quote_id
        assert quote.get('quote_pdf_url') is not None, "quote_pdf_url is missing"
        assert quote['quote_pdf_url'].startswith('/uploads/'), f"Invalid quote_pdf_url: {quote['quote_pdf_url']}"
        assert quote['quote_category'] == 'equipment'
        assert quote['equipment_type'] == 'POS'
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_04_generate_equipment_pdf_creates_attachment(self):
        """Bug #1 Fix: Quote should have an attachment with category='Cotización'"""
        pos_items = [h for h in self.hardware if h.get('type') == 'POS']
        if not pos_items:
            pytest.skip("No POS hardware items available")
        
        item = pos_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "POS",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": "POS",
                "quantity": 1,
                "unit_price_usd": item.get('price_usd', 100),
                "total_usd": item.get('price_usd', 100)
            }],
            "notes": "TEST_iteration86_attachment"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        quote_id = response.headers.get('x-quote-id')
        
        # GET the quote
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        quote = quote_response.json()
        
        # Attachment assertions
        attachments = quote.get('attachments', [])
        assert len(attachments) >= 1, "No attachments found"
        
        # Find the Cotización attachment
        cot_attachment = next((a for a in attachments if a.get('category') == 'Cotización'), None)
        assert cot_attachment is not None, "Attachment with category 'Cotización' not found"
        
        # Verify attachment fields
        assert cot_attachment.get('url') is not None, "Attachment URL is empty"
        assert cot_attachment['url'].startswith('/uploads/'), f"Invalid attachment URL: {cot_attachment['url']}"
        assert cot_attachment.get('filename', '').endswith('.pdf'), "Attachment is not a PDF"
        assert cot_attachment.get('content_type') == 'application/pdf'
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_05_pdf_file_exists_on_server(self):
        """Bug #1 Fix: PDF file should exist on server at /uploads/"""
        pos_items = [h for h in self.hardware if h.get('type') == 'POS']
        if not pos_items:
            pytest.skip("No POS hardware items available")
        
        item = pos_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "POS",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": "POS",
                "quantity": 1,
                "unit_price_usd": item.get('price_usd', 100),
                "total_usd": item.get('price_usd', 100)
            }],
            "notes": "TEST_iteration86_file_exists"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        quote_id = response.headers.get('x-quote-id')
        
        # GET the quote to get the PDF URL
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        quote = quote_response.json()
        pdf_url = quote.get('quote_pdf_url')
        
        # Try to access the PDF file via /api/uploads path (public endpoint)
        # Note: The pdf_url is stored as /uploads/xxx.pdf but accessed via /api/uploads/xxx.pdf
        pdf_file_url = f"{BASE_URL}/api{pdf_url}"
        pdf_file_response = self.session.get(pdf_file_url)
        
        assert pdf_file_response.status_code == 200, f"PDF file not accessible: {pdf_file_url}"
        # Check that response contains PDF data
        assert len(pdf_file_response.content) > 0, "PDF file is empty"
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_06_accessory_type_pdf_generation(self):
        """Test PDF generation for Accesorio equipment type"""
        # Find accessory items
        acc_items = [h for h in self.hardware if h.get('type') in ['Accesorio', 'Base']]
        if not acc_items:
            pytest.skip("No accessory hardware items available")
        
        item = acc_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "Accesorio",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": item.get('type', 'Accesorio'),
                "quantity": 3,
                "unit_price_usd": item.get('price_usd', 50),
                "total_usd": item.get('price_usd', 50) * 3
            }],
            "notes": "TEST_iteration86_accesorio"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        assert 'application/pdf' in response.headers.get('content-type', '')
        
        quote_id = response.headers.get('x-quote-id')
        assert quote_id is not None
        
        # Verify quote was created
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        quote = quote_response.json()
        assert quote['equipment_type'] == 'Accesorio'
        assert len(quote.get('attachments', [])) >= 1
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_07_repair_type_pdf_generation(self):
        """Test PDF generation for Reparación equipment type"""
        # For repairs, we can use maintenance/component items or just create minimal data
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "Reparación",
            "items": [{
                "hardware_id": "custom_repair_001",
                "name": "Diagnóstico y Reparación General",
                "hardware_type": "Mantenimiento",
                "quantity": 1,
                "unit_price_usd": 75.00,
                "total_usd": 75.00
            }],
            "notes": "TEST_iteration86_reparacion",
            "repair_description": "Equipo no enciende - posible falla en fuente de poder",
            "equipment_serial_number": "SN-TEST-12345",
            "estimated_delivery_date": "2026-03-20"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        assert 'application/pdf' in response.headers.get('content-type', '')
        
        quote_id = response.headers.get('x-quote-id')
        assert quote_id is not None
        
        # Verify quote was created with repair category
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        quote = quote_response.json()
        assert quote['equipment_type'] == 'Reparación'
        assert quote['quote_category'] == 'repair'
        assert quote.get('repair_description') == "Equipo no enciende - posible falla en fuente de poder"
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)
    
    def test_08_pinpad_type_pdf_generation(self):
        """Test PDF generation for Pinpad equipment type"""
        pinpad_items = [h for h in self.hardware if h.get('type') == 'Pinpad']
        if not pinpad_items:
            pytest.skip("No Pinpad hardware items available")
        
        item = pinpad_items[0]
        
        pdf_data = {
            "client_id": self.test_client['client_id'],
            "cliente_nombre": self.test_client.get('legal_name', 'Test Client'),
            "cliente_rif": self.test_client.get('rif', 'J-00000000-0'),
            "equipment_type": "Pinpad",
            "items": [{
                "hardware_id": item['hardware_id'],
                "name": item['name'],
                "hardware_type": "Pinpad",
                "quantity": 5,
                "unit_price_usd": item.get('price_usd', 400),
                "total_usd": item.get('price_usd', 400) * 5
            }],
            "notes": "TEST_iteration86_pinpad"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-equipment-pdf",
            json=pdf_data
        )
        
        assert response.status_code == 200
        
        quote_id = response.headers.get('x-quote-id')
        
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        quote = quote_response.json()
        assert quote['equipment_type'] == 'Pinpad'
        
        if not hasattr(self, 'created_quote_ids'):
            self.created_quote_ids = []
        self.created_quote_ids.append(quote_id)


class TestQuotesListWithEquipmentQuotes:
    """Test that equipment quotes appear correctly in quotes list"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@gestor.com",
            "password": "Admin2026!"
        })
        assert response.status_code == 200
        token = response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_equipment_quotes_in_list(self):
        """Verify equipment quotes appear in GET /api/quotes list"""
        response = self.session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        assert isinstance(quotes, list)
        
        # Check if there are any equipment quotes
        equipment_quotes = [q for q in quotes if q.get('quote_category') == 'equipment']
        
        # Should have at least some equipment quotes from previous tests
        print(f"Found {len(equipment_quotes)} equipment quotes in the list")
        
        if equipment_quotes:
            eq = equipment_quotes[0]
            # Verify equipment quote has expected fields
            assert 'quote_id' in eq
            assert 'quote_number' in eq
            assert eq.get('quote_category') in ['equipment', 'repair']
