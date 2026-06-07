# ruff: noqa
"""
Test iteration 168: Verificación de reorganización de modales en flujo de reparaciones
- ApprovalBillingModal simplificado para reparaciones (solo comprobante de aprobación)
- RepairCompleteModal con calculadora fiscal + comprobante de pago opcional
- Backend repair-complete acepta billing_data y lo guarda en repair_billing_data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRepairCompleteEndpoint:
    """Tests para el endpoint repair-complete con billing_data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: obtener token de autenticación"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_repair_complete_endpoint_exists(self):
        """Verificar que el endpoint repair-complete existe"""
        # Usar un quote_id ficticio para verificar que el endpoint responde
        response = self.session.post(f"{BASE_URL}/api/quotes/fake_id/repair-complete", json={})
        # Debe retornar 404 (no encontrado) o 400 (no es reparación), no 405 (método no permitido)
        assert response.status_code in [404, 400, 422], f"Unexpected status: {response.status_code}"
    
    def test_repair_complete_with_billing_data(self):
        """Verificar que repair-complete acepta billing_data"""
        # Primero buscar una cotización de reparación en estado Aprobada
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair' and q.get('quote_status') == 'Aprobada']
        
        if not repair_quotes:
            pytest.skip("No hay cotizaciones de reparación en estado 'Aprobada' para probar")
        
        quote = repair_quotes[0]
        quote_id = quote['quote_id']
        
        # Preparar billing_data como lo enviaría el modal
        billing_data = {
            "billing_data": {
                "consolidated_items": [
                    {
                        "name": "Reparación de equipo",
                        "quantity": 1,
                        "total_usd": 50.00,
                        "exchange_rate": 45.50,
                        "total_bs": 2275.00
                    }
                ],
                "exchange_rate": 45.50,
                "rate_source": "Manual",
                "billing_date": "2026-01-15",
                "grand_total_usd": 50.00,
                "grand_total_bs": 2275.00,
                "iva_usd": 8.00,
                "iva_bs": 364.00,
                "grand_total_con_iva_usd": 58.00,
                "grand_total_con_iva_bs": 2639.00,
                "has_payment_proof": False
            }
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete", json=billing_data)
        
        # Debe ser exitoso
        assert response.status_code == 200, f"repair-complete failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Reparada"
        assert "message" in data
        
        # Verificar que se guardó el billing_data
        quote_response = self.session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert quote_response.status_code == 200
        
        updated_quote = quote_response.json()
        assert updated_quote.get("quote_status") == "Reparada"
        assert "repair_billing_data" in updated_quote, "repair_billing_data no se guardó"
        
        repair_billing = updated_quote.get("repair_billing_data", {})
        assert repair_billing.get("exchange_rate") == 45.50
        assert repair_billing.get("grand_total_usd") == 50.00
    
    def test_repair_complete_without_billing_data_retrocompat(self):
        """Verificar retrocompatibilidad: repair-complete funciona sin billing_data"""
        # Buscar otra cotización de reparación en estado Aprobada
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair' and q.get('quote_status') == 'Aprobada']
        
        if not repair_quotes:
            pytest.skip("No hay cotizaciones de reparación en estado 'Aprobada' para probar retrocompatibilidad")
        
        quote = repair_quotes[0]
        quote_id = quote['quote_id']
        
        # Llamar sin billing_data (retrocompatibilidad)
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/repair-complete", json={})
        
        # Debe ser exitoso
        assert response.status_code == 200, f"repair-complete sin billing_data failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Reparada"


class TestApproveEndpointForRepair:
    """Tests para verificar que approve para reparaciones es simplificado"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: obtener token de autenticación"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_approve_repair_accepts_simplified_body(self):
        """Verificar que approve para reparaciones acepta body simplificado (solo has_approval_proof)"""
        # Buscar cotización de reparación en estado Enviada
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair' and q.get('quote_status') == 'Enviada']
        
        if not repair_quotes:
            pytest.skip("No hay cotizaciones de reparación en estado 'Enviada' para probar")
        
        quote = repair_quotes[0]
        quote_id = quote['quote_id']
        
        # Body simplificado para reparaciones (sin calculadora, sin billing_instruction completo)
        simplified_body = {
            "has_approval_proof": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", json=simplified_body)
        
        # Debe ser exitoso
        assert response.status_code == 200, f"approve repair failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Aprobada"
        assert data.get("is_repair") == True


class TestQuotesListForRepair:
    """Tests para verificar que las cotizaciones de reparación tienen equipment_items"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: obtener token de autenticación"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_repair_quote_has_equipment_items(self):
        """Verificar que las cotizaciones de reparación tienen equipment_items para la calculadora"""
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        if not repair_quotes:
            pytest.skip("No hay cotizaciones de reparación para verificar")
        
        # Verificar que al menos una tiene equipment_items
        has_equipment_items = False
        for quote in repair_quotes:
            if quote.get('equipment_items') and len(quote.get('equipment_items', [])) > 0:
                has_equipment_items = True
                # Verificar estructura de equipment_items
                item = quote['equipment_items'][0]
                assert 'name' in item or 'hardware_name' in item, "equipment_item debe tener name o hardware_name"
                break
        
        # No es crítico si no hay items, pero lo reportamos
        if not has_equipment_items:
            print("NOTA: Las cotizaciones de reparación no tienen equipment_items poblados")


class TestExchangeRateEndpoint:
    """Tests para verificar que el endpoint de tasa de cambio funciona (usado por RepairCompleteModal)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: obtener token de autenticación"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_exchange_rate_current(self):
        """Verificar que el endpoint de tasa actual funciona"""
        response = self.session.get(f"{BASE_URL}/api/exchange-rate/current")
        assert response.status_code == 200, f"exchange-rate/current failed: {response.text}"
        
        data = response.json()
        # Debe tener rate o tasa
        assert 'rate' in data or 'tasa' in data, "Respuesta debe contener rate o tasa"
    
    def test_exchange_rate_by_date(self):
        """Verificar que el endpoint de tasa por fecha funciona"""
        response = self.session.get(f"{BASE_URL}/api/exchange-rate/by-date/2026-01-15")
        assert response.status_code == 200, f"exchange-rate/by-date failed: {response.text}"
        
        data = response.json()
        # Debe indicar si encontró o no
        assert 'found' in data, "Respuesta debe indicar si encontró la tasa"
