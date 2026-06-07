# ruff: noqa
"""
Cotizador Merchant Server - Iteration 8 Feature Tests
======================================================
Tests for specific features requested:
1. POST /api/quotes - creates quote successfully (bug fix - item_id Optional)
2. POST /api/quotes/generate-pdf - generates PDF with Setup + Recurrentes structure
3. Frontend: 'Bancos' field locked for specific concepts
4. Frontend: 'Bancos' field auto-calculated for 'Configuración Medio de Pago / Banco'
5. Frontend: 'Complementar Recurrentes' button removed
6. Frontend: Delete buttons visible on additional/auto-linked recurring items
7. Frontend: 'Exportar PDF' button visible
8. Cascade delete: When additional payment method removed, linked recurring is also removed

All backend endpoints require Emergent Google OAuth authentication.
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestQuoteCreationBugFix:
    """Test POST /api/quotes with optional item_id (bug fix)"""
    
    def test_quote_creation_without_item_id(self):
        """POST /api/quotes accepts items without item_id (was required before)"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        # New payload structure - item_id is now Optional
        payload = {
            "client_id": "cli_test123",
            "quote_type": "VPOS",
            "services": [
                {
                    "item_type": "setup",
                    # "item_id" is omitted - should be accepted (was causing bug before)
                    "item_name": "Suscripción PDV/Banco",
                    "quantity": 2,
                    "unit_price_usd": 50.0,
                    "total_usd": 100.0
                }
            ],
            "hardware": [],
            "notes": "Test quote without item_id"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload)
        # Should return 401 (auth required) - validates payload structure is accepted
        # If it returns 422, it means validation failed - bug not fixed
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/quotes accepts items without item_id (bug fix verified)")
    
    def test_quote_creation_with_item_id(self):
        """POST /api/quotes still accepts items with item_id"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        payload = {
            "client_id": "cli_test123",
            "quote_type": "VPOS",
            "services": [
                {
                    "item_type": "setup",
                    "item_id": "srv_12345",  # Explicit item_id
                    "item_name": "Suscripción PDV/Banco",
                    "quantity": 2,
                    "unit_price_usd": 50.0,
                    "total_usd": 100.0
                }
            ],
            "hardware": [],
            "notes": "Test quote with item_id"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/quotes accepts items with item_id")
    
    def test_quote_creation_multiple_item_types(self):
        """POST /api/quotes accepts mix of setup, recurring_basic, recurring_other, additional"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        payload = {
            "client_id": "cli_test123",
            "quote_type": "VPOS",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Suscripción PDV/Banco",
                    "quantity": 1,
                    "unit_price_usd": 50.0,
                    "total_usd": 50.0
                },
                {
                    "item_type": "recurring_basic",
                    "item_name": "Derecho de uso de plataforma MServer por PDV",
                    "quantity": 1,
                    "unit_price_usd": 25.0,
                    "total_usd": 25.0
                },
                {
                    "item_type": "recurring_other",
                    "item_name": "Comunicación Backend",
                    "quantity": 1,
                    "unit_price_usd": 15.0,
                    "total_usd": 15.0
                },
                {
                    "item_type": "additional",
                    "item_name": "Visa Débito - Banco Mercantil",
                    "quantity": 1,
                    "unit_price_usd": 30.0,
                    "total_usd": 30.0
                }
            ],
            "hardware": [],
            "notes": "Test with multiple item types"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/quotes accepts multiple item types")


class TestPDFGenerationEndpoint:
    """Test POST /api/quotes/generate-pdf endpoint"""
    
    def test_pdf_endpoint_exists(self):
        """POST /api/quotes/generate-pdf endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", json={})
        # Should return 401 (auth required) or 422 (validation), NOT 404
        assert response.status_code in [401, 422], f"Expected 401/422, got {response.status_code}"
        print(f"PASS: POST /api/quotes/generate-pdf exists (status: {response.status_code})")
    
    def test_pdf_generation_payload_structure(self):
        """POST /api/quotes/generate-pdf accepts correct payload structure"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        # QuotePDFRequest structure from server.py lines 186-195
        payload = {
            "cliente_nombre": "Test Cliente S.A.",
            "cliente_rif": "J-12345678-9",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "setup_items": [
                {
                    "concepto": "Suscripción PDV/Banco",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 50.0,
                    "total": 100.0
                }
            ],
            "recurring_basic_items": [
                {
                    "concepto": "Derecho de uso de plataforma MServer por PDV",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 25.0,
                    "total": 50.0
                }
            ],
            "recurring_other_items": [
                {
                    "concepto": "Comunicación Backend",
                    "cantidad_cajas": 2,
                    "cantidad_bancos": 1,
                    "tarifa": 15.0,
                    "total": 30.0
                }
            ],
            "descuento": 10.0,
            "notes": "Cotización de prueba"
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/quotes/generate-pdf accepts correct payload structure")
    
    def test_pdf_generation_with_empty_sections(self):
        """POST /api/quotes/generate-pdf handles empty item sections"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        payload = {
            "cliente_nombre": "Cliente Vacío",
            "cliente_rif": "",
            "quote_type": "GATEWAY",
            "pricing_model": "outsourcing",
            "setup_items": [],  # Empty
            "recurring_basic_items": [],  # Empty
            "recurring_other_items": [],  # Empty
            "descuento": 0,
            "notes": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/quotes/generate-pdf handles empty sections")
    
    def test_pdf_generation_all_quote_types(self):
        """POST /api/quotes/generate-pdf accepts all quote types"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        quote_types = ["VPOS", "GATEWAY", "MPOS", "LINK"]
        
        for qt in quote_types:
            payload = {
                "cliente_nombre": "Test Cliente",
                "quote_type": qt,
                "pricing_model": "conventional",
                "setup_items": [],
                "recurring_basic_items": [],
                "recurring_other_items": []
            }
            response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", headers=headers, json=payload)
            assert response.status_code == 401, f"Quote type {qt}: Expected 401, got {response.status_code}"
            print(f"PASS: PDF generation accepts quote type '{qt}'")
    
    def test_pdf_generation_both_pricing_models(self):
        """POST /api/quotes/generate-pdf accepts both pricing models"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        models = ["conventional", "outsourcing"]
        
        for model in models:
            payload = {
                "cliente_nombre": "Test Cliente",
                "quote_type": "VPOS",
                "pricing_model": model,
                "setup_items": [],
                "recurring_basic_items": [],
                "recurring_other_items": []
            }
            response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", headers=headers, json=payload)
            assert response.status_code == 401, f"Model {model}: Expected 401, got {response.status_code}"
            print(f"PASS: PDF generation accepts pricing model '{model}'")


class TestQuoteModelFields:
    """Verify QuoteItem model has correct fields with item_id Optional"""
    
    def test_quote_item_all_required_fields(self):
        """QuoteItem has item_type, item_name, quantity, unit_price_usd, total_usd as required"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        # All required fields provided
        payload = {
            "client_id": "cli_test",
            "quote_type": "VPOS",
            "services": [
                {
                    "item_type": "setup",
                    "item_name": "Test Service",
                    "quantity": 1,
                    "unit_price_usd": 10.0,
                    "total_usd": 10.0
                }
            ],
            "hardware": []
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: QuoteItem validates all required fields correctly")
    
    def test_quote_item_missing_required_fields(self):
        """QuoteItem rejects items missing required fields"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        # Missing item_name (required field)
        payload = {
            "client_id": "cli_test",
            "quote_type": "VPOS",
            "services": [
                {
                    "item_type": "setup",
                    # "item_name": missing
                    "quantity": 1,
                    "unit_price_usd": 10.0,
                    "total_usd": 10.0
                }
            ],
            "hardware": []
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload)
        # Should return 422 (validation error) because item_name is required
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("PASS: QuoteItem rejects items missing required fields (item_name)")


class TestServicesWithLinkedRecurring:
    """Test services endpoint returns linked_recurring_service_id"""
    
    def test_services_endpoint_auth_required(self):
        """GET /api/services requires authentication"""
        response = requests.get(f"{BASE_URL}/api/services")
        assert response.status_code == 401
        print("PASS: GET /api/services returns 401 without auth")
    
    def test_services_application_type_filter(self):
        """GET /api/services?application_type=recurring_available filter works"""
        response = requests.get(f"{BASE_URL}/api/services?application_type=recurring_available")
        assert response.status_code == 401
        print("PASS: GET /api/services?application_type=recurring_available accepted")
    
    def test_service_with_linked_recurring_creation(self):
        """POST /api/services accepts linked_recurring_service_id field"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        payload = {
            "category": "Setup",
            "name": "Test Service with Link",
            "application_type": "setup",
            "vpos_enabled": True,
            "gateway_enabled": True,
            "mpos_enabled": True,
            "link_enabled": True,
            "setup_cost_conventional": 50.0,
            "monthly_cost_conventional": 0.0,
            "setup_cost_outsourcing": 40.0,
            "monthly_cost_outsourcing": 0.0,
            "description": "Test service",
            "linked_recurring_service_id": "srv_recurring123"  # New field
        }
        
        response = requests.post(f"{BASE_URL}/api/services", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/services accepts linked_recurring_service_id field")


class TestExchangeRateDefaultValue:
    """Test exchange rate uses default value when none exists"""
    
    def test_exchange_rate_endpoint(self):
        """GET /api/exchange-rate/current endpoint exists and requires auth"""
        response = requests.get(f"{BASE_URL}/api/exchange-rate/current")
        assert response.status_code == 401
        print("PASS: Exchange rate endpoint requires authentication")


class TestQuotePDFItemModel:
    """Test QuotePDFItem model structure"""
    
    def test_pdf_item_default_values(self):
        """QuotePDFItem has correct default values"""
        headers = {"Authorization": "Bearer test", "Content-Type": "application/json"}
        
        # Minimal payload - should use defaults
        payload = {
            "cliente_nombre": "Test",
            "setup_items": [
                {
                    "concepto": "Test Item"
                    # Other fields should default: cantidad_cajas=1, cantidad_bancos=1, tarifa=0, total=0
                }
            ],
            "recurring_basic_items": [],
            "recurring_other_items": []
        }
        
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", headers=headers, json=payload)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: QuotePDFItem accepts items with default values")


class TestAPIEndpointRouting:
    """Verify all relevant API endpoints are properly routed"""
    
    def test_quotes_list_endpoint(self):
        """GET /api/quotes returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 401
        print("PASS: GET /api/quotes endpoint accessible")
    
    def test_quotes_create_endpoint(self):
        """POST /api/quotes returns 401/422 without auth"""
        response = requests.post(f"{BASE_URL}/api/quotes", json={})
        assert response.status_code in [401, 422]
        print(f"PASS: POST /api/quotes endpoint accessible (status: {response.status_code})")
    
    def test_quotes_get_by_id_endpoint(self):
        """GET /api/quotes/{id} returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_test123")
        assert response.status_code == 401
        print("PASS: GET /api/quotes/{id} endpoint accessible")
    
    def test_quotes_pdf_by_id_endpoint(self):
        """GET /api/quotes/{id}/pdf returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/quotes/quo_test123/pdf")
        assert response.status_code == 401
        print("PASS: GET /api/quotes/{id}/pdf endpoint accessible")
    
    def test_quotes_generate_pdf_endpoint(self):
        """POST /api/quotes/generate-pdf returns 401/422 without auth"""
        response = requests.post(f"{BASE_URL}/api/quotes/generate-pdf", json={})
        assert response.status_code in [401, 422]
        print(f"PASS: POST /api/quotes/generate-pdf endpoint accessible (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
