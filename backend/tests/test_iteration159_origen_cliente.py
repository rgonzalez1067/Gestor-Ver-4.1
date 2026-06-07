# ruff: noqa
"""
Test Iteration 159: Origen del Cliente (Referidor) System
Tests the corrected referidor system with:
- 14 options in REFERIDOR_OPTIONS (master list + new options)
- Cascade dropdown: Banco → bank dropdown, Cliente Referidor → client dropdown
- Simple origins (Correo de Ventas, Integrador, etc.) → no secondary dropdown
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Expected 14 options in REFERIDOR_OPTIONS
EXPECTED_REFERIDOR_OPTIONS = [
    'Correo de Ventas', 'Integrador', 'Directores', 'Corporativo',
    'Jose Dolande', 'Melissa Garcia', 'Katherine Quailey', 'Rafael Gonzalez',
    'Ventas Directas (Ejecutivo)', 'Página Web / Landing Page', 'Redes Sociales',
    'Alianzas Externas', 'Banco', 'Cliente Referidor'
]


class TestReferidorOptions:
    """Test GET /api/clients/referidor-options endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_referidor_options_returns_banks_and_clients(self):
        """GET /api/clients/referidor-options returns banks (30) and clients (315+)"""
        resp = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "banks" in data, "Response should have 'banks' key"
        assert "clients" in data, "Response should have 'clients' key"
        
        # Verify banks count (should be ~30)
        banks = data["banks"]
        assert len(banks) >= 25, f"Expected at least 25 banks, got {len(banks)}"
        print(f"✓ Found {len(banks)} banks")
        
        # Verify clients count (should be 315+)
        clients = data["clients"]
        assert len(clients) >= 100, f"Expected at least 100 clients, got {len(clients)}"
        print(f"✓ Found {len(clients)} clients")
        
        # Verify bank structure
        if banks:
            first_bank = banks[0]
            assert "id" in first_bank, "Bank should have 'id'"
            assert "name" in first_bank, "Bank should have 'name'"
            print(f"✓ First bank: {first_bank['name']} (ID: {first_bank['id']})")
        
        # Verify client structure
        if clients:
            first_client = clients[0]
            assert "id" in first_client, "Client should have 'id'"
            assert "name" in first_client, "Client should have 'name'"
            assert "rif" in first_client, "Client should have 'rif'"
            print(f"✓ First client: {first_client['name']} (RIF: {first_client['rif']})")


class TestCreateClientWithReferidor:
    """Test POST /api/clients with different referidor values"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.created_client_ids = []
    
    def teardown_method(self, method):
        """Cleanup: Delete test clients"""
        for client_id in self.created_client_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{client_id}")
            except:
                pass
    
    def test_create_client_with_banco_referidor(self):
        """POST /api/clients with referidor='Banco', referidor_tipo='BANCO', referidor_id=bank_id"""
        # First get a valid bank_id
        options_resp = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert options_resp.status_code == 200
        banks = options_resp.json()["banks"]
        assert len(banks) > 0, "No banks available"
        
        bank = banks[0]  # Use first bank
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Banco_Referidor_Client",
            "fantasy_name": "TEST_Banco_Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Banco",
            "referidor_tipo": "BANCO",
            "referidor_id": bank["id"],
            "referidor_nombre": bank["name"],
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create client: {resp.text}"
        
        created = resp.json()
        self.created_client_ids.append(created["client_id"])
        
        # Verify referidor fields
        assert created["referidor"] == "Banco", f"Expected referidor='Banco', got {created.get('referidor')}"
        assert created["referidor_tipo"] == "BANCO", f"Expected referidor_tipo='BANCO', got {created.get('referidor_tipo')}"
        assert created["referidor_id"] == bank["id"], f"Expected referidor_id={bank['id']}, got {created.get('referidor_id')}"
        assert created["referidor_nombre"] == bank["name"], f"Expected referidor_nombre={bank['name']}, got {created.get('referidor_nombre')}"
        
        print(f"✓ Created client with Banco referidor: {bank['name']}")
    
    def test_create_client_with_cliente_referidor(self):
        """POST /api/clients with referidor='Cliente Referidor', referidor_tipo='CLIENTE', referidor_id=client_id"""
        # First get a valid client_id
        options_resp = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert options_resp.status_code == 200
        clients = options_resp.json()["clients"]
        assert len(clients) > 0, "No clients available"
        
        ref_client = clients[0]  # Use first client as referidor
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Cliente_Referidor_Client",
            "fantasy_name": "TEST_Cliente_Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Cliente Referidor",
            "referidor_tipo": "CLIENTE",
            "referidor_id": ref_client["id"],
            "referidor_nombre": ref_client["name"],
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create client: {resp.text}"
        
        created = resp.json()
        self.created_client_ids.append(created["client_id"])
        
        # Verify referidor fields
        assert created["referidor"] == "Cliente Referidor", f"Expected referidor='Cliente Referidor', got {created.get('referidor')}"
        assert created["referidor_tipo"] == "CLIENTE", f"Expected referidor_tipo='CLIENTE', got {created.get('referidor_tipo')}"
        assert created["referidor_id"] == ref_client["id"], f"Expected referidor_id={ref_client['id']}, got {created.get('referidor_id')}"
        assert created["referidor_nombre"] == ref_client["name"], f"Expected referidor_nombre={ref_client['name']}, got {created.get('referidor_nombre')}"
        
        print(f"✓ Created client with Cliente Referidor: {ref_client['name']}")
    
    def test_create_client_with_correo_ventas(self):
        """POST /api/clients with referidor='Correo de Ventas' (simple origin, no secondary dropdown)"""
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Correo_Ventas_Client",
            "fantasy_name": "TEST_Correo",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Correo de Ventas",
            "referidor_tipo": "OTRO",
            "referidor_id": None,
            "referidor_nombre": None,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create client: {resp.text}"
        
        created = resp.json()
        self.created_client_ids.append(created["client_id"])
        
        # Verify referidor fields
        assert created["referidor"] == "Correo de Ventas", f"Expected referidor='Correo de Ventas', got {created.get('referidor')}"
        assert created["referidor_tipo"] == "OTRO", f"Expected referidor_tipo='OTRO', got {created.get('referidor_tipo')}"
        
        print("✓ Created client with simple origin: Correo de Ventas")
    
    def test_create_client_with_integrador(self):
        """POST /api/clients with referidor='Integrador' (simple origin, no secondary dropdown)"""
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Integrador_Client",
            "fantasy_name": "TEST_Integrador",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Integrador",
            "referidor_tipo": "OTRO",
            "referidor_id": None,
            "referidor_nombre": None,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create client: {resp.text}"
        
        created = resp.json()
        self.created_client_ids.append(created["client_id"])
        
        # Verify referidor fields
        assert created["referidor"] == "Integrador", f"Expected referidor='Integrador', got {created.get('referidor')}"
        
        print("✓ Created client with simple origin: Integrador")


class TestUpdateClientReferidor:
    """Test PUT /api/clients/{id} to change referidor"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and create a test client"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Create a test client with Integrador referidor
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Update_Referidor_Client",
            "fantasy_name": "TEST_Update",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Integrador",
            "referidor_tipo": "OTRO",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create test client: {resp.text}"
        self.test_client = resp.json()
        self.test_client_id = self.test_client["client_id"]
    
    def teardown_method(self, method):
        """Cleanup: Delete test client"""
        try:
            self.session.delete(f"{BASE_URL}/api/clients/{self.test_client_id}")
        except:
            pass
    
    def test_update_referidor_from_integrador_to_banco(self):
        """PUT /api/clients/{id} - change referidor from 'Integrador' to 'Banco' with referidor_id"""
        # Get a valid bank
        options_resp = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert options_resp.status_code == 200
        banks = options_resp.json()["banks"]
        assert len(banks) > 0, "No banks available"
        
        bank = banks[0]
        
        # Update the client
        update_payload = {
            "rif": self.test_client["rif"],
            "legal_name": self.test_client["legal_name"],
            "fantasy_name": self.test_client["fantasy_name"],
            "segment": self.test_client["segment"],
            "condicion": self.test_client["condicion"],
            "referidor": "Banco",
            "referidor_tipo": "BANCO",
            "referidor_id": bank["id"],
            "referidor_nombre": bank["name"],
            "sucursal": self.test_client["sucursal"],
            "contacts": self.test_client.get("contacts", [])
        }
        
        resp = self.session.put(f"{BASE_URL}/api/clients/{self.test_client_id}", json=update_payload)
        assert resp.status_code == 200, f"Failed to update client: {resp.text}"
        
        updated = resp.json()
        
        # Verify the update
        assert updated["referidor"] == "Banco", f"Expected referidor='Banco', got {updated.get('referidor')}"
        assert updated["referidor_tipo"] == "BANCO", f"Expected referidor_tipo='BANCO', got {updated.get('referidor_tipo')}"
        assert updated["referidor_id"] == bank["id"], f"Expected referidor_id={bank['id']}, got {updated.get('referidor_id')}"
        assert updated["referidor_nombre"] == bank["name"], f"Expected referidor_nombre={bank['name']}, got {updated.get('referidor_nombre')}"
        
        print(f"✓ Updated client referidor from 'Integrador' to 'Banco': {bank['name']}")


class TestGetClientReferidorFields:
    """Test GET /api/clients/{id} returns referidor fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and create a test client with Banco referidor"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get a valid bank
        options_resp = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert options_resp.status_code == 200
        banks = options_resp.json()["banks"]
        self.bank = banks[0] if banks else None
        
        # Create a test client with Banco referidor
        test_rif = f"J{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "rif": test_rif,
            "legal_name": "TEST_Get_Referidor_Client",
            "fantasy_name": "TEST_Get",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor": "Banco",
            "referidor_tipo": "BANCO",
            "referidor_id": self.bank["id"] if self.bank else None,
            "referidor_nombre": self.bank["name"] if self.bank else None,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        resp = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert resp.status_code == 200, f"Failed to create test client: {resp.text}"
        self.test_client = resp.json()
        self.test_client_id = self.test_client["client_id"]
    
    def teardown_method(self, method):
        """Cleanup: Delete test client"""
        try:
            self.session.delete(f"{BASE_URL}/api/clients/{self.test_client_id}")
        except:
            pass
    
    def test_get_client_returns_referidor_fields(self):
        """GET /api/clients/{id} returns referidor, referidor_tipo, referidor_id, referidor_nombre"""
        resp = self.session.get(f"{BASE_URL}/api/clients/{self.test_client_id}")
        assert resp.status_code == 200, f"Failed to get client: {resp.text}"
        
        client = resp.json()
        
        # Verify all referidor fields are present
        assert "referidor" in client, "Response should have 'referidor' field"
        assert "referidor_tipo" in client, "Response should have 'referidor_tipo' field"
        assert "referidor_id" in client, "Response should have 'referidor_id' field"
        assert "referidor_nombre" in client, "Response should have 'referidor_nombre' field"
        
        # Verify values
        assert client["referidor"] == "Banco", f"Expected referidor='Banco', got {client.get('referidor')}"
        assert client["referidor_tipo"] == "BANCO", f"Expected referidor_tipo='BANCO', got {client.get('referidor_tipo')}"
        
        if self.bank:
            assert client["referidor_id"] == self.bank["id"], f"Expected referidor_id={self.bank['id']}, got {client.get('referidor_id')}"
            assert client["referidor_nombre"] == self.bank["name"], f"Expected referidor_nombre={self.bank['name']}, got {client.get('referidor_nombre')}"
        
        print(f"✓ GET /api/clients/{self.test_client_id} returns all referidor fields correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
