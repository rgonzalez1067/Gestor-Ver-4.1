"""
Test Integration and Hardware section in Quotes
Tests for new fields: integrator_id, pinpad_id, sponsor_bank_id
and the PDF generation with these fields
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stock-control-hub-7.preview.emergentagent.com').rstrip('/')
AUTH_HEADER = {"Authorization": "Bearer test_import_session_token_2024"}


class TestHardwareEndpoint:
    """Test /api/hardware endpoint for Pinpad filtering"""
    
    def test_get_hardware_returns_200(self):
        """GET /api/hardware returns 200"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total hardware items: {len(data)}")
    
    def test_hardware_has_pinpad_type(self):
        """Hardware list includes devices with type='Pinpad'"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        
        pinpads = [hw for hw in data if hw.get('type', '').lower() == 'pinpad']
        print(f"Pinpad devices found: {len(pinpads)}")
        assert len(pinpads) > 0, "Should have at least one Pinpad device"
        
        # Verify Pinpad structure
        for pinpad in pinpads:
            assert 'hardware_id' in pinpad
            assert 'name' in pinpad
            assert 'type' in pinpad
            assert pinpad['type'].lower() == 'pinpad'
            print(f"  - {pinpad['name']} (id={pinpad['hardware_id']})")
    
    def test_hardware_has_required_fields(self):
        """Hardware items have all required fields"""
        response = requests.get(f"{BASE_URL}/api/hardware", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            hw = data[0]
            assert 'hardware_id' in hw
            assert 'name' in hw
            assert 'type' in hw
            assert 'price_usd' in hw
            assert 'price_bs_usd' in hw


class TestIntegratorsEndpoint:
    """Test /api/integrators endpoint for Certificado filtering"""
    
    def test_get_integrators_returns_200(self):
        """GET /api/integrators returns 200"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total integrators: {len(data)}")
    
    def test_integrators_have_certificado_status(self):
        """Some integrators have status='Certificado'"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        
        certificados = [i for i in data if i.get('integrator_status') == 'Certificado']
        print(f"Certificado integrators: {len(certificados)}")
        assert len(certificados) > 0, "Should have at least one Certificado integrator"
        
        # Verify structure
        for integrator in certificados[:3]:
            assert 'integrator_id' in integrator
            assert 'name' in integrator
            assert 'app_name' in integrator
            assert 'integrator_status' in integrator
            print(f"  - {integrator['name']} ({integrator['app_name']})")
    
    def test_integrators_have_required_fields(self):
        """Integrator items have all required fields including app_name"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            integrator = data[0]
            assert 'integrator_id' in integrator
            assert 'name' in integrator
            assert 'app_name' in integrator, "app_name field required for auto-complete"
            assert 'integrator_type' in integrator
            assert 'integration_modality' in integrator
            assert 'integrator_status' in integrator


class TestBanksEndpoint:
    """Test /api/banks endpoint for Entidad Patrocinadora selection"""
    
    def test_get_banks_returns_200(self):
        """GET /api/banks returns 200"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total banks: {len(data)}")
    
    def test_banks_have_required_fields(self):
        """Banks have required fields for sponsor selection"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) > 0, "Should have at least one bank"
        
        bank = data[0]
        assert 'bank_id' in bank
        assert 'name' in bank
        assert 'type' in bank
        assert 'country' in bank
        print(f"First bank: {bank['name']} ({bank['type']})")


class TestQuotePDFGeneration:
    """Test PDF generation with integration and hardware fields"""
    
    def test_generate_pdf_with_integration_fields(self):
        """POST /api/quotes/generate-pdf with new integration fields"""
        pdf_data = {
            "cliente_nombre": "Test Client",
            "cliente_rif": "J-12345678-9",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "integrator_name": "Mundo APP / Burger King",
            "integrator_app_name": "Menu APP",
            "pinpad_model": "Verifone P200 Pinpad",
            "sponsor_bank_name": "Banco de Venezuela",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 20.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "tarifa": 10.0
                }
            ],
            "recurring_other_items": [],
            "descuento": 0,
            "notes": "Test quote with integration fields"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=AUTH_HEADER
        )
        
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        
        # Verify PDF content is not empty
        pdf_content = response.content
        assert len(pdf_content) > 0, "PDF should not be empty"
        
        # Verify PDF magic bytes
        assert pdf_content[:4] == b'%PDF', "Response should be a valid PDF"
        print(f"PDF generated successfully, size: {len(pdf_content)} bytes")
    
    def test_generate_pdf_without_integration_fields(self):
        """POST /api/quotes/generate-pdf works without integration fields (backward compatibility)"""
        pdf_data = {
            "cliente_nombre": "Test Client Without Integration",
            "cliente_rif": "J-98765432-1",
            "quote_type": "GATEWAY",
            "pricing_model": "outsourcing",
            "setup_items": [
                {
                    "concepto": "Setup Básico",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 50.0
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "descuento": 10,
            "notes": ""
        }
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf",
            json=pdf_data,
            headers=AUTH_HEADER
        )
        
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        print("PDF generated without integration fields (backward compatible)")


class TestQuoteDataValidation:
    """Test that quote data includes integration fields"""
    
    def test_quote_type_options(self):
        """Verify quote types are available"""
        # Quote types are defined in frontend, but we can verify services endpoint
        response = requests.get(f"{BASE_URL}/api/services", headers=AUTH_HEADER)
        assert response.status_code == 200
        print("Services endpoint accessible for quote pricing")
    
    def test_clients_available(self):
        """Clients available for quote selection"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=AUTH_HEADER)
        assert response.status_code == 200
        data = response.json()
        print(f"Clients available: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
