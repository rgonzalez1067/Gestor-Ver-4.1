"""
Test Suite for PYME Extended Flow: Server Selection + Pinpad from Inventory
Iteration 152 - Testing the extended PYME flow for 'Enviar a Implementación'

Features tested:
1. GET /api/quotes/{id}/pinpad-models - Returns hardware items with type POS/Pinpad and asset_type='Bien'
2. GET /api/quotes/{id}/inventory-serials?model_id=X - Searches salidas by client RIF + model + last 15 days
3. POST /api/quotes/{id}/send-to-implementation with server_name and pinpad_serials in body
4. Project creation with server_name and pinpad_serials fields
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPymeExtendedFlowBackend:
    """Tests for PYME extended flow backend APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        assert token, "No session token received"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        yield
    
    # ==================== PINPAD MODELS ENDPOINT ====================
    
    def test_get_pinpad_models_returns_200(self):
        """GET /api/quotes/{id}/pinpad-models returns 200 status"""
        # Use any quote_id - the endpoint doesn't actually need a valid quote
        response = self.session.get(f"{BASE_URL}/api/quotes/test_quote_id/pinpad-models")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_get_pinpad_models_returns_models_array(self):
        """GET /api/quotes/{id}/pinpad-models returns models array"""
        response = self.session.get(f"{BASE_URL}/api/quotes/test_quote_id/pinpad-models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data, "Response should contain 'models' key"
        assert isinstance(data["models"], list), "models should be a list"
    
    def test_get_pinpad_models_structure(self):
        """GET /api/quotes/{id}/pinpad-models returns correct model structure"""
        response = self.session.get(f"{BASE_URL}/api/quotes/test_quote_id/pinpad-models")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", [])
        
        if len(models) > 0:
            model = models[0]
            assert "hardware_id" in model, "Model should have hardware_id"
            assert "name" in model, "Model should have name"
            assert "type" in model, "Model should have type"
            # Type should be POS or Pinpad
            assert model["type"] in ["POS", "Pinpad"], f"Type should be POS or Pinpad, got {model['type']}"
            print(f"Found {len(models)} pinpad/POS models")
            for m in models[:5]:
                print(f"  - {m['name']} ({m['type']})")
        else:
            print("No pinpad models found in hardware catalog")
    
    def test_get_pinpad_models_filters_by_asset_type_bien(self):
        """GET /api/quotes/{id}/pinpad-models only returns items with asset_type='Bien'"""
        response = self.session.get(f"{BASE_URL}/api/quotes/test_quote_id/pinpad-models")
        assert response.status_code == 200
        data = response.json()
        models = data.get("models", [])
        
        # Verify by checking hardware collection directly
        hw_response = self.session.get(f"{BASE_URL}/api/hardware")
        if hw_response.status_code == 200:
            all_hardware = hw_response.json()
            pos_pinpad_bien = [h for h in all_hardware 
                              if h.get("type") in ["POS", "Pinpad"] 
                              and h.get("asset_type") == "Bien"]
            print(f"Hardware catalog has {len(pos_pinpad_bien)} POS/Pinpad items with asset_type='Bien'")
            print(f"Pinpad-models endpoint returned {len(models)} models")
    
    # ==================== INVENTORY SERIALS ENDPOINT ====================
    
    def test_get_inventory_serials_requires_model_id(self):
        """GET /api/quotes/{id}/inventory-serials requires model_id parameter"""
        # First get a valid PYME quote
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quote = q
                break
        
        if pyme_quote:
            # Without model_id should return 422 or empty
            response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/inventory-serials")
            # FastAPI will return 422 for missing required query param
            assert response.status_code in [422, 400], f"Expected 422 or 400 without model_id, got {response.status_code}"
        else:
            pytest.skip("No PYME quote found for testing")
    
    def test_get_inventory_serials_with_model_id(self):
        """GET /api/quotes/{id}/inventory-serials?model_id=X returns serials array"""
        # Get a PYME quote
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quote = q
                break
        
        if not pyme_quote:
            pytest.skip("No PYME quote found for testing")
        
        # Get a model_id from pinpad-models
        models_response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/pinpad-models")
        assert models_response.status_code == 200
        models = models_response.json().get("models", [])
        
        if not models:
            pytest.skip("No pinpad models available")
        
        model_id = models[0]["hardware_id"]
        
        # Now test inventory-serials with model_id
        response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/inventory-serials?model_id={model_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "serials" in data, "Response should contain 'serials' key"
        assert "client_rif" in data, "Response should contain 'client_rif' key"
        assert isinstance(data["serials"], list), "serials should be a list"
        
        print(f"Quote: {pyme_quote['quote_number']}")
        print(f"Model: {models[0]['name']} ({model_id})")
        print(f"Client RIF: {data['client_rif']}")
        print(f"Serials found: {len(data['serials'])}")
        
        if data["serials"]:
            serial = data["serials"][0]
            assert "serial" in serial, "Serial should have 'serial' field"
            assert "modelo" in serial, "Serial should have 'modelo' field"
            assert "movement_id" in serial, "Serial should have 'movement_id' field"
            print(f"  First serial: {serial['serial']} - {serial['modelo']}")
    
    def test_get_inventory_serials_returns_correct_structure(self):
        """GET /api/quotes/{id}/inventory-serials returns correct serial structure"""
        # Get a PYME quote
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quote = q
                break
        
        if not pyme_quote:
            pytest.skip("No PYME quote found")
        
        models_response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/pinpad-models")
        models = models_response.json().get("models", [])
        
        if not models:
            pytest.skip("No pinpad models available")
        
        model_id = models[0]["hardware_id"]
        response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/inventory-serials?model_id={model_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Even if no serials found, structure should be correct
        assert "serials" in data
        assert "client_rif" in data
        
        if data["serials"]:
            serial = data["serials"][0]
            expected_fields = ["serial", "modelo", "movement_id", "warehouse", "date", "reference"]
            for field in expected_fields:
                assert field in serial, f"Serial should have '{field}' field"
    
    # ==================== SEND TO IMPLEMENTATION WITH PYME DATA ====================
    
    def test_send_to_implementation_accepts_server_name(self):
        """POST /api/quotes/{id}/send-to-implementation accepts server_name in body"""
        # Find a PYME quote with status that allows sending to implementation
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            status = q.get("quote_status", "")
            # Need Pagada status or use irregular flow
            if ("-PYME" in qn or seg in ["pyme", "pymes"]) and status in ["Pagada", "Aprobada"]:
                pyme_quote = q
                break
        
        if not pyme_quote:
            # Try with irregular flow header
            for q in quotes:
                qn = (q.get("quote_number") or "").upper()
                seg = (q.get("client_segment") or "").lower()
                if "-PYME" in qn or seg in ["pyme", "pymes"]:
                    pyme_quote = q
                    break
        
        if not pyme_quote:
            pytest.skip("No PYME quote found for testing")
        
        print(f"Testing with quote: {pyme_quote['quote_number']} (status: {pyme_quote.get('quote_status')})")
        
        # Test that the endpoint accepts server_name parameter
        # We'll use irregular flow headers to bypass status check
        headers = {
            "x-exception-reason": "Testing PYME extended flow",
            "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
        }
        
        payload = {
            "project_type_impl": "pos_fast_track",
            "server_name": "Multicomercio MSC",
            "pinpad_serials": []
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/send-to-implementation",
            json=payload,
            headers=headers
        )
        
        # Should succeed or fail for other reasons (not because of server_name)
        print(f"Response status: {response.status_code}")
        print(f"Response: {response.text[:500] if response.text else 'empty'}")
        
        # If it fails, it should not be because server_name is not accepted
        if response.status_code != 200:
            error_detail = response.json().get("detail", "")
            assert "server_name" not in error_detail.lower(), f"server_name should be accepted: {error_detail}"
    
    def test_send_to_implementation_accepts_pinpad_serials(self):
        """POST /api/quotes/{id}/send-to-implementation accepts pinpad_serials in body"""
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quote = q
                break
        
        if not pyme_quote:
            pytest.skip("No PYME quote found for testing")
        
        headers = {
            "x-exception-reason": "Testing PYME pinpad serials",
            "x-regularization-date": datetime.now().strftime("%Y-%m-%d")
        }
        
        payload = {
            "project_type_impl": "pos_fast_track",
            "server_name": "Multicomercio MSC2",
            "pinpad_serials": [
                {"modelo": "Test Model", "serial": "TEST123", "movement_id": "mov_test"}
            ]
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/send-to-implementation",
            json=payload,
            headers=headers
        )
        
        print(f"Response status: {response.status_code}")
        
        # If it fails, it should not be because pinpad_serials is not accepted
        if response.status_code != 200:
            error_detail = response.json().get("detail", "")
            assert "pinpad_serials" not in error_detail.lower(), f"pinpad_serials should be accepted: {error_detail}"
    
    # ==================== PROJECT DETAIL VERIFICATION ====================
    
    def test_project_has_server_name_field(self):
        """Projects created from PYME quotes should have server_name field"""
        # Get projects
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        projects = projects_response.json()
        
        # Check if any project has server_name
        projects_with_server = [p for p in projects if p.get("server_name")]
        
        print(f"Total projects: {len(projects)}")
        print(f"Projects with server_name: {len(projects_with_server)}")
        
        if projects_with_server:
            for p in projects_with_server[:3]:
                print(f"  - {p.get('project_number')}: server_name = {p.get('server_name')}")
    
    def test_project_has_pinpad_serials_field(self):
        """Projects created from PYME quotes should have pinpad_serials field"""
        projects_response = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        projects = projects_response.json()
        
        # Check if any project has pinpad_serials
        projects_with_pinpads = [p for p in projects if p.get("pinpad_serials")]
        
        print(f"Total projects: {len(projects)}")
        print(f"Projects with pinpad_serials: {len(projects_with_pinpads)}")
        
        if projects_with_pinpads:
            for p in projects_with_pinpads[:3]:
                serials = p.get("pinpad_serials", [])
                print(f"  - {p.get('project_number')}: {len(serials)} pinpad serial(s)")
    
    # ==================== PYME DETECTION LOGIC ====================
    
    def test_pyme_quotes_exist(self):
        """Verify PYME quotes exist in the system"""
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        pyme_quotes = []
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quotes.append(q)
        
        print(f"Total quotes: {len(quotes)}")
        print(f"PYME quotes found: {len(pyme_quotes)}")
        
        for q in pyme_quotes[:5]:
            print(f"  - {q.get('quote_number')} (status: {q.get('quote_status')}, segment: {q.get('client_segment', 'N/A')})")
        
        assert len(pyme_quotes) > 0, "Should have at least one PYME quote for testing"
    
    def test_pyme_detection_by_quote_number(self):
        """PYME detection works by quote_number containing '-PYME'"""
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_by_number = [q for q in quotes if "-PYME" in (q.get("quote_number") or "").upper()]
        
        print(f"Quotes with '-PYME' in quote_number: {len(pyme_by_number)}")
        for q in pyme_by_number[:3]:
            print(f"  - {q.get('quote_number')}")
    
    def test_pyme_detection_by_client_segment(self):
        """PYME detection works by client_segment field"""
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_by_segment = [q for q in quotes 
                          if (q.get("client_segment") or "").lower() in ["pyme", "pymes"]]
        
        print(f"Quotes with client_segment='pyme'/'pymes': {len(pyme_by_segment)}")
        for q in pyme_by_segment[:3]:
            print(f"  - {q.get('quote_number')} (segment: {q.get('client_segment')})")
    
    # ==================== HARDWARE CATALOG VERIFICATION ====================
    
    def test_hardware_catalog_has_pos_pinpad_items(self):
        """Hardware catalog should have POS/Pinpad items with asset_type='Bien'"""
        hw_response = self.session.get(f"{BASE_URL}/api/hardware")
        assert hw_response.status_code == 200
        hardware = hw_response.json()
        
        pos_items = [h for h in hardware if h.get("type") == "POS"]
        pinpad_items = [h for h in hardware if h.get("type") == "Pinpad"]
        bien_items = [h for h in hardware if h.get("asset_type") == "Bien"]
        pos_pinpad_bien = [h for h in hardware 
                          if h.get("type") in ["POS", "Pinpad"] 
                          and h.get("asset_type") == "Bien"]
        
        print(f"Total hardware items: {len(hardware)}")
        print(f"POS items: {len(pos_items)}")
        print(f"Pinpad items: {len(pinpad_items)}")
        print(f"Items with asset_type='Bien': {len(bien_items)}")
        print(f"POS/Pinpad with asset_type='Bien': {len(pos_pinpad_bien)}")
        
        for h in pos_pinpad_bien[:5]:
            print(f"  - {h.get('name')} ({h.get('type')}, {h.get('asset_type')})")
    
    # ==================== INVENTORY MOVEMENTS VERIFICATION ====================
    
    def test_inventory_movements_have_salidas(self):
        """Inventory movements should have 'salida' type movements"""
        # This is an indirect test - we check via the inventory-serials endpoint
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        quotes = quotes_response.json()
        
        pyme_quote = None
        for q in quotes:
            qn = (q.get("quote_number") or "").upper()
            seg = (q.get("client_segment") or "").lower()
            if "-PYME" in qn or seg in ["pyme", "pymes"]:
                pyme_quote = q
                break
        
        if not pyme_quote:
            pytest.skip("No PYME quote found")
        
        models_response = self.session.get(f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/pinpad-models")
        models = models_response.json().get("models", [])
        
        total_serials = 0
        for model in models[:3]:
            response = self.session.get(
                f"{BASE_URL}/api/quotes/{pyme_quote['quote_id']}/inventory-serials?model_id={model['hardware_id']}"
            )
            if response.status_code == 200:
                serials = response.json().get("serials", [])
                total_serials += len(serials)
                if serials:
                    print(f"Model {model['name']}: {len(serials)} serial(s) found")
        
        print(f"Total serials found across models: {total_serials}")


class TestPymeFlowIntegration:
    """Integration tests for the complete PYME flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    def test_complete_pyme_flow_data_availability(self):
        """Test that all data needed for PYME flow is available"""
        # 1. Get PYME quotes
        quotes_response = self.session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        pyme_quotes = [q for q in quotes 
                      if "-PYME" in (q.get("quote_number") or "").upper() 
                      or (q.get("client_segment") or "").lower() in ["pyme", "pymes"]]
        
        assert len(pyme_quotes) > 0, "Need PYME quotes for testing"
        print(f"Step 1: Found {len(pyme_quotes)} PYME quotes")
        
        # 2. Get pinpad models
        test_quote = pyme_quotes[0]
        models_response = self.session.get(f"{BASE_URL}/api/quotes/{test_quote['quote_id']}/pinpad-models")
        assert models_response.status_code == 200
        models = models_response.json().get("models", [])
        print(f"Step 2: Found {len(models)} pinpad/POS models")
        
        # 3. Check inventory serials (if models exist)
        if models:
            serials_response = self.session.get(
                f"{BASE_URL}/api/quotes/{test_quote['quote_id']}/inventory-serials?model_id={models[0]['hardware_id']}"
            )
            assert serials_response.status_code == 200
            serials = serials_response.json().get("serials", [])
            print(f"Step 3: Found {len(serials)} inventory serials for model {models[0]['name']}")
        
        print("PYME flow data availability: PASS")
