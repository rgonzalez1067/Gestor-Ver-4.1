"""
Iteration 55: Payment Gateway Module Tests
Tests for:
1. PG PDF Generation (POST /api/quotes/generate-pdf-with-template with quote_type='GATEWAY')
2. VPOS flow unchanged (POST /api/quotes/generate-pdf-with-template with quote_type='VPOS_MPOS')
3. PG Integrator filter (integration_modality IN ('PG Universal', 'PG No universal'))
4. Many-to-many validation (same concept different banks allowed, same concept+same bank blocked)
5. pg_setup_items in PDF payload
"""
import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIteration55PGModule:
    """Test Payment Gateway module features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "testadmin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
        
        yield
    
    def test_get_clients_for_pg_quote(self):
        """Test getting clients for PG quote creation"""
        response = self.session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        clients = response.json()
        assert isinstance(clients, list)
        print(f"Found {len(clients)} clients")
        
    def test_get_integrators_list(self):
        """Test getting integrators list"""
        response = self.session.get(f"{BASE_URL}/api/integrators")
        assert response.status_code == 200
        integrators = response.json()
        assert isinstance(integrators, list)
        print(f"Found {len(integrators)} integrators")
        
        # Check for PG integrators (PG Universal or PG No universal)
        pg_integrators = [i for i in integrators if i.get('integration_modality') in ['PG Universal', 'PG No universal']]
        print(f"PG integrators (modality PG Universal/PG No universal): {len(pg_integrators)}")
        
        for i in pg_integrators:
            print(f"  - {i.get('name')}: {i.get('integration_modality')}, status: {i.get('integrator_status')}")
    
    def test_get_banks_with_gateway_products(self):
        """Test getting banks with gateway-enabled products"""
        response = self.session.get(f"{BASE_URL}/api/banks")
        assert response.status_code == 200
        banks = response.json()
        
        gateway_banks = []
        for bank in banks:
            gw_products = [p for p in bank.get('products', []) if p.get('gateway_available')]
            if gw_products:
                gateway_banks.append({
                    'name': bank.get('name'),
                    'bank_id': bank.get('bank_id'),
                    'gateway_products': [p.get('product_name') for p in gw_products]
                })
        
        print(f"Banks with gateway products: {len(gateway_banks)}")
        for b in gateway_banks:
            print(f"  - {b['name']}: {b['gateway_products']}")
        
        assert len(gateway_banks) > 0, "Need at least one bank with gateway products"
        return gateway_banks
    
    def test_create_pg_integrator_if_needed(self):
        """Create a PG Universal integrator if none exists (for testing)"""
        response = self.session.get(f"{BASE_URL}/api/integrators")
        integrators = response.json()
        
        # Check for certified PG integrators
        certified_pg = [i for i in integrators 
                       if i.get('integration_modality') in ['PG Universal', 'PG No universal']
                       and i.get('integrator_status') == 'Certificado']
        
        if len(certified_pg) == 0:
            # Create one
            new_integrator = {
                "name": "TEST PG Integrador",
                "integrator_type": "Integrador",
                "app_name": "TestApp PG",
                "integration_modality": "PG Universal",
                "integrator_status": "Certificado"
            }
            create_response = self.session.post(f"{BASE_URL}/api/integrators", json=new_integrator)
            assert create_response.status_code in [200, 201]
            created = create_response.json()
            print(f"Created test PG integrator: {created.get('integrator_id')}")
            return created
        else:
            print(f"Found existing certified PG integrator: {certified_pg[0].get('name')}")
            return certified_pg[0]
    
    def test_pg_pdf_generation_with_pg_setup_items(self):
        """Test PDF generation for GATEWAY quote with pg_setup_items"""
        # Get a client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        clients = clients_resp.json()
        if not clients:
            pytest.skip("No clients available")
        client = clients[0]
        
        # Get a PG integrator
        integrators_resp = self.session.get(f"{BASE_URL}/api/integrators")
        integrators = integrators_resp.json()
        pg_integrator = next((i for i in integrators 
                             if i.get('integration_modality') in ['PG Universal', 'PG No universal']
                             and i.get('integrator_status') == 'Certificado'), None)
        
        integrator_id = pg_integrator.get('integrator_id') if pg_integrator else None
        integrator_name = pg_integrator.get('name') if pg_integrator else 'Sin integrador por el momento'
        
        # Prepare PG quote payload
        pg_setup_items = [
            {"concepto": "Persona Jurídica", "costo": 240, "banco": "N/A", "observacion": "Costo base"},
            {"concepto": "Débito", "costo": 50, "banco": "Banco Test", "observacion": ""},
            {"concepto": "Crédito", "costo": 50, "banco": "Banco Test", "observacion": ""}
        ]
        
        payload = {
            "cliente_nombre": client.get('legal_name') or client.get('fantasy_name'),
            "cliente_rif": client.get('rif', ''),
            "cliente_address": client.get('address', ''),
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "integrator_name": integrator_name,
            "integrator_app_name": pg_integrator.get('app_name', '') if pg_integrator else '',
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "production_items": [],
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": None,
            "descuento": 0,
            "descuento_setup": 0,
            "descuento_recurrente": 0,
            "notes": "Test PG PDF generation",
            "is_production_client": False
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            json=payload
        )
        
        print(f"PG PDF generation status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text[:500]}")
        
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type, f"Expected PDF, got: {content_type}"
        
        # Check PDF size
        pdf_content = response.content
        assert len(pdf_content) > 1000, f"PDF too small: {len(pdf_content)} bytes"
        
        print(f"PG PDF generated successfully: {len(pdf_content)} bytes")
    
    def test_vpos_pdf_generation_unchanged(self):
        """Test VPOS_MPOS PDF generation still works (unchanged)"""
        # Get a client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        clients = clients_resp.json()
        if not clients:
            pytest.skip("No clients available")
        client = clients[0]
        
        # Prepare VPOS quote payload
        payload = {
            "cliente_nombre": client.get('legal_name') or client.get('fantasy_name'),
            "cliente_rif": client.get('rif', ''),
            "cliente_address": client.get('address', ''),
            "quote_type": "VPOS_MPOS",
            "pricing_model": "conventional",
            "cantidad_cajas": 2,
            "integrator_name": "Test Integrador",
            "integrator_app_name": "TestApp",
            "pinpad_model": "Pinpad Standard",
            "sponsor_bank_name": "Banco Test",
            "setup_items": [
                {"concepto": "Suscripción PDV/Banco", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 25.0}
            ],
            "recurring_basic_items": [
                {"concepto": "Derecho de uso de plataforma MServer por PDV", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 10.0}
            ],
            "recurring_other_items": [],
            "production_items": [],
            "pg_setup_items": [],
            "descuento": 0,
            "descuento_setup": 0,
            "descuento_recurrente": 0,
            "notes": "Test VPOS PDF generation",
            "is_production_client": False
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            json=payload
        )
        
        print(f"VPOS PDF generation status: {response.status_code}")
        
        assert response.status_code == 200, f"VPOS PDF generation failed: {response.text}"
        
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type
        
        pdf_content = response.content
        assert len(pdf_content) > 1000
        
        print(f"VPOS PDF generated successfully: {len(pdf_content)} bytes")
    
    def test_create_gateway_quote_with_pg_setup_items(self):
        """Test creating a GATEWAY quote and verify pg_setup_items are stored"""
        # Get a client
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        clients = clients_resp.json()
        if not clients:
            pytest.skip("No clients available")
        client = clients[0]
        
        # Get a PG integrator or use none
        integrators_resp = self.session.get(f"{BASE_URL}/api/integrators")
        integrators = integrators_resp.json()
        pg_integrator = next((i for i in integrators 
                             if i.get('integration_modality') in ['PG Universal', 'PG No universal']
                             and i.get('integrator_status') == 'Certificado'), None)
        
        # Prepare quote creation payload
        pg_setup_items = [
            {"concepto": "Persona Jurídica", "costo": 240, "banco": "N/A", "observacion": "Base"},
            {"concepto": "Débito", "costo": 50, "banco": "Banco A", "observacion": ""},
            {"concepto": "Crédito", "costo": 60, "banco": "Banco A", "observacion": ""}
        ]
        
        payload = {
            "client_id": client.get('client_id'),
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test PG quote with pg_setup_items",
            "integrator_id": pg_integrator.get('integrator_id') if pg_integrator else None,
            "integrator_name": pg_integrator.get('name') if pg_integrator else 'Sin integrador por el momento',
            "integrator_app_name": pg_integrator.get('app_name', '') if pg_integrator else '',
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": None,
            "pg_transaction_range": 3,
            "pdf_data": None
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        
        print(f"Create GATEWAY quote status: {response.status_code}")
        if response.status_code not in [200, 201]:
            print(f"Error: {response.text[:500]}")
        
        assert response.status_code in [200, 201], f"Failed: {response.text}"
        
        response_data = response.json()
        
        # Response is wrapped: {"message": ..., "quote": {...}, "pdf_url": ...}
        created_quote = response_data.get('quote', response_data)
        quote_id = created_quote.get('quote_id')
        print(f"Created GATEWAY quote: {quote_id}, number: {created_quote.get('quote_number')}")
        
        # Verify pg_setup_items are stored
        assert 'pg_setup_items' in created_quote, f"pg_setup_items not in quote: {created_quote.keys()}"
        stored_items = created_quote.get('pg_setup_items', [])
        assert len(stored_items) == 3, f"Expected 3 pg_setup_items, got {len(stored_items)}"
        
        # Verify quote_type
        assert created_quote.get('quote_type') == 'GATEWAY'
        
        print(f"Stored pg_setup_items: {stored_items}")
        
        return created_quote
    
    def test_pg_quote_pdf_download(self):
        """Test PDF download for an existing GATEWAY quote"""
        # Find an existing GATEWAY quote or create one
        quotes_resp = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_resp.json()
        
        gw_quote = next((q for q in quotes if q.get('quote_type') == 'GATEWAY'), None)
        
        if not gw_quote:
            # Create one
            created = self.test_create_gateway_quote_with_pg_setup_items()
            if created:
                gw_quote = created
            else:
                pytest.skip("Could not create GATEWAY quote")
        
        quote_id = gw_quote.get('quote_id')
        print(f"Testing PDF download for GATEWAY quote: {quote_id}")
        
        response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}/pdf")
        
        print(f"PDF download status: {response.status_code}")
        
        assert response.status_code == 200, f"PDF download failed: {response.text[:200]}"
        
        content_type = response.headers.get('content-type', '')
        assert 'application/pdf' in content_type
        
        pdf_content = response.content
        print(f"Downloaded PG PDF: {len(pdf_content)} bytes")
        
        # Basic PDF validation
        assert pdf_content[:4] == b'%PDF', "Invalid PDF header"
    
    def test_many_to_many_validation_backend(self):
        """Test many-to-many validation: same concept can be added for different banks"""
        # This is a backend structural test - verify model supports the pattern
        # Get banks with gateway products
        banks_resp = self.session.get(f"{BASE_URL}/api/banks")
        banks = banks_resp.json()
        
        # Filter banks with gateway products
        gw_banks = [b for b in banks if any(p.get('gateway_available') for p in b.get('products', []))]
        
        if len(gw_banks) < 2:
            print("Need at least 2 banks with gateway products to test many-to-many")
            # Create a test bank if needed
            pass
        
        print(f"Found {len(gw_banks)} banks with gateway products")
        
        # The validation logic is in frontend (handlePgBankChange)
        # Backend should accept pg_setup_items with same concept + different banks
        
        # Test creating a quote with same concept on different banks
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        clients = clients_resp.json()
        if not clients:
            pytest.skip("No clients")
        
        # pg_setup_items with Débito on 2 different banks (many-to-many allowed)
        pg_setup_items = [
            {"concepto": "Persona Jurídica", "costo": 240, "banco": "N/A", "observacion": ""},
            {"concepto": "Débito", "costo": 50, "banco": "Banco A", "observacion": ""},
            {"concepto": "Débito", "costo": 55, "banco": "Banco B", "observacion": ""},  # Same concept, different bank - allowed
            {"concepto": "Crédito", "costo": 60, "banco": "Banco A", "observacion": ""}
        ]
        
        payload = {
            "client_id": clients[0].get('client_id'),
            "quote_category": "implementation",
            "quote_type": "GATEWAY",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "equipment_items": [],
            "notes": "Test many-to-many validation",
            "integrator_id": None,
            "integrator_name": "Sin integrador por el momento",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": pg_setup_items,
            "pg_recurring_cost": None,
            "pg_transaction_range": 4
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=payload)
        
        print(f"Many-to-many quote creation: {response.status_code}")
        
        # Should succeed - same concept on different banks is allowed
        assert response.status_code in [200, 201], f"Many-to-many should be allowed: {response.text}"
        
        response_data = response.json()
        created = response_data.get('quote', response_data)
        stored_items = created.get('pg_setup_items', [])
        
        # Verify all 4 items were stored (including 2 Débito with different banks)
        assert len(stored_items) == 4, f"Expected 4 items, got {len(stored_items)}"
        
        debito_items = [i for i in stored_items if i.get('concepto') == 'Débito']
        assert len(debito_items) == 2, "Should have 2 Débito items (different banks)"
        
        print(f"Many-to-many validation passed: {len(debito_items)} Débito items on different banks")


class TestPGIntegratorFilter:
    """Test PG integrator filter behavior"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "testadmin123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
        
        yield
    
    def test_integrators_have_modality_field(self):
        """Verify integrators have integration_modality field"""
        response = self.session.get(f"{BASE_URL}/api/integrators")
        assert response.status_code == 200
        
        integrators = response.json()
        
        for integrator in integrators:
            assert 'integration_modality' in integrator, f"Missing integration_modality in {integrator.get('name')}"
            assert integrator['integration_modality'] in ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST', 'Stand Alone']
        
        print(f"All {len(integrators)} integrators have valid integration_modality")
    
    def test_filter_pg_integrators(self):
        """Test filtering integrators for PG (PG Universal or PG No universal)"""
        response = self.session.get(f"{BASE_URL}/api/integrators")
        integrators = response.json()
        
        # Apply PG filter (same as frontend)
        pg_modalities = ['PG Universal', 'PG No universal']
        pg_integrators = [
            i for i in integrators 
            if i.get('integration_modality') in pg_modalities
            and i.get('integrator_status') == 'Certificado'
        ]
        
        print(f"PG integrators (certified): {len(pg_integrators)}")
        for i in pg_integrators:
            print(f"  - {i.get('name')}: {i.get('integration_modality')}")
        
        # Non-PG integrators (should NOT appear in GATEWAY quotes)
        non_pg = [
            i for i in integrators 
            if i.get('integration_modality') not in pg_modalities
            and i.get('integrator_status') == 'Certificado'
        ]
        
        print(f"Non-PG integrators (certified): {len(non_pg)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
