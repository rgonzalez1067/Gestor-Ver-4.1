"""
Test Iteration 158: Dynamic Referidor Field Feature
Tests for the two-level referidor system: referidor_tipo (BANCO/CLIENTE/OTRO) + referidor_id + referidor_nombre
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestReferidorOptions:
    """Test GET /api/clients/referidor-options endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
    
    def test_referidor_options_returns_banks_and_clients(self):
        """GET /api/clients/referidor-options should return banks (30) and clients (315+)"""
        response = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "banks" in data, "Response should contain 'banks' key"
        assert "clients" in data, "Response should contain 'clients' key"
        
        # Verify banks count (should be around 30)
        banks = data["banks"]
        assert len(banks) >= 20, f"Expected at least 20 banks, got {len(banks)}"
        print(f"✓ Found {len(banks)} banks")
        
        # Verify clients count (should be 315+)
        clients = data["clients"]
        assert len(clients) >= 100, f"Expected at least 100 clients, got {len(clients)}"
        print(f"✓ Found {len(clients)} clients")
        
        # Verify bank structure
        if banks:
            bank = banks[0]
            assert "id" in bank, "Bank should have 'id' field"
            assert "name" in bank, "Bank should have 'name' field"
            print(f"✓ First bank: {bank['name']} (ID: {bank['id']})")
        
        # Verify client structure
        if clients:
            client = clients[0]
            assert "id" in client, "Client should have 'id' field"
            assert "name" in client, "Client should have 'name' field"
            assert "rif" in client, "Client should have 'rif' field"
            print(f"✓ First client: {client['name']} (RIF: {client['rif']})")


class TestCreateClientWithReferidor:
    """Test POST /api/clients with different referidor_tipo values"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.token = token
        self.created_client_ids = []
        
        # Get referidor options for test data
        options_response = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        self.referidor_options = options_response.json() if options_response.status_code == 200 else {"banks": [], "clients": []}
    
    def teardown_method(self, method):
        """Cleanup: Delete test clients"""
        for client_id in self.created_client_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{client_id}")
            except:
                pass
    
    def test_create_client_with_referidor_tipo_banco(self):
        """POST /api/clients with referidor_tipo=BANCO and valid bank_id"""
        banks = self.referidor_options.get("banks", [])
        if not banks:
            pytest.skip("No banks available for testing")
        
        bank = banks[0]
        unique_rif = f"J{int(time.time()) % 1000000000}"
        
        payload = {
            "rif": unique_rif,
            "legal_name": "TEST_Cliente Referido por Banco",
            "fantasy_name": "TEST_Banco Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor_tipo": "BANCO",
            "referidor_id": bank["id"],
            "referidor_nombre": bank["name"],
            "referidor": bank["name"],
            "sucursal": "Principal"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Failed to create client: {response.text}"
        
        data = response.json()
        self.created_client_ids.append(data["client_id"])
        
        # Verify referidor fields
        assert data.get("referidor_tipo") == "BANCO", f"Expected referidor_tipo=BANCO, got {data.get('referidor_tipo')}"
        assert data.get("referidor_id") == bank["id"], f"Expected referidor_id={bank['id']}, got {data.get('referidor_id')}"
        assert data.get("referidor_nombre") == bank["name"], f"Expected referidor_nombre={bank['name']}, got {data.get('referidor_nombre')}"
        print(f"✓ Created client with BANCO referidor: {bank['name']}")
    
    def test_create_client_with_referidor_tipo_cliente(self):
        """POST /api/clients with referidor_tipo=CLIENTE and valid client_id"""
        clients = self.referidor_options.get("clients", [])
        if not clients:
            pytest.skip("No clients available for testing")
        
        ref_client = clients[0]
        unique_rif = f"J{int(time.time()) % 1000000000 + 1}"
        
        payload = {
            "rif": unique_rif,
            "legal_name": "TEST_Cliente Referido por Cliente",
            "fantasy_name": "TEST_Cliente Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor_tipo": "CLIENTE",
            "referidor_id": ref_client["id"],
            "referidor_nombre": ref_client["name"],
            "referidor": ref_client["name"],
            "sucursal": "Principal"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Failed to create client: {response.text}"
        
        data = response.json()
        self.created_client_ids.append(data["client_id"])
        
        # Verify referidor fields
        assert data.get("referidor_tipo") == "CLIENTE", f"Expected referidor_tipo=CLIENTE, got {data.get('referidor_tipo')}"
        assert data.get("referidor_id") == ref_client["id"], f"Expected referidor_id={ref_client['id']}, got {data.get('referidor_id')}"
        assert data.get("referidor_nombre") == ref_client["name"], f"Expected referidor_nombre={ref_client['name']}, got {data.get('referidor_nombre')}"
        print(f"✓ Created client with CLIENTE referidor: {ref_client['name']}")
    
    def test_create_client_with_referidor_tipo_otro(self):
        """POST /api/clients with referidor_tipo=OTRO and free text"""
        unique_rif = f"J{int(time.time()) % 1000000000 + 2}"
        
        payload = {
            "rif": unique_rif,
            "legal_name": "TEST_Cliente Referido por Otro",
            "fantasy_name": "TEST_Otro Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "referidor_tipo": "OTRO",
            "referidor_id": None,
            "referidor_nombre": "Correo de Ventas",
            "referidor": "Correo de Ventas",
            "sucursal": "Principal"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Failed to create client: {response.text}"
        
        data = response.json()
        self.created_client_ids.append(data["client_id"])
        
        # Verify referidor fields
        assert data.get("referidor_tipo") == "OTRO", f"Expected referidor_tipo=OTRO, got {data.get('referidor_tipo')}"
        assert data.get("referidor_nombre") == "Correo de Ventas", f"Expected referidor_nombre='Correo de Ventas', got {data.get('referidor_nombre')}"
        print(f"✓ Created client with OTRO referidor: Correo de Ventas")


class TestUpdateClientReferidor:
    """Test PUT /api/clients/{id} to update referidor_tipo"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and create a test client"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get referidor options
        options_response = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        self.referidor_options = options_response.json() if options_response.status_code == 200 else {"banks": [], "clients": []}
        
        # Create test client
        unique_rif = f"J{int(time.time()) % 1000000000 + 3}"
        create_response = self.session.post(f"{BASE_URL}/api/clients", json={
            "rif": unique_rif,
            "legal_name": "TEST_Cliente Para Update",
            "fantasy_name": "TEST_Update Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "sucursal": "Principal"
        })
        assert create_response.status_code == 200, f"Failed to create test client: {create_response.text}"
        self.test_client = create_response.json()
        self.test_client_id = self.test_client["client_id"]
    
    def teardown_method(self, method):
        """Cleanup: Delete test client"""
        try:
            self.session.delete(f"{BASE_URL}/api/clients/{self.test_client_id}")
        except:
            pass
    
    def test_update_client_referidor_tipo(self):
        """PUT /api/clients/{id} should update referidor_tipo"""
        banks = self.referidor_options.get("banks", [])
        if not banks:
            pytest.skip("No banks available for testing")
        
        bank = banks[0]
        
        # Update with BANCO referidor
        update_payload = {
            "rif": self.test_client["rif"],
            "legal_name": self.test_client["legal_name"],
            "fantasy_name": self.test_client["fantasy_name"],
            "segment": self.test_client.get("segment", "Pymes"),
            "condicion": self.test_client.get("condicion", "Prospecto"),
            "sucursal": self.test_client.get("sucursal", "Principal"),
            "referidor_tipo": "BANCO",
            "referidor_id": bank["id"],
            "referidor_nombre": bank["name"],
            "referidor": bank["name"]
        }
        
        response = self.session.put(f"{BASE_URL}/api/clients/{self.test_client_id}", json=update_payload)
        assert response.status_code == 200, f"Failed to update client: {response.text}"
        
        data = response.json()
        assert data.get("referidor_tipo") == "BANCO", f"Expected referidor_tipo=BANCO, got {data.get('referidor_tipo')}"
        assert data.get("referidor_id") == bank["id"], f"Expected referidor_id={bank['id']}, got {data.get('referidor_id')}"
        print(f"✓ Updated client referidor_tipo to BANCO: {bank['name']}")


class TestGetClientWithReferidor:
    """Test GET /api/clients/{id} returns referidor fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and create a test client with referidor"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get referidor options
        options_response = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        self.referidor_options = options_response.json() if options_response.status_code == 200 else {"banks": [], "clients": []}
        
        # Create test client with BANCO referidor
        banks = self.referidor_options.get("banks", [])
        self.test_bank = banks[0] if banks else None
        
        unique_rif = f"J{int(time.time()) % 1000000000 + 4}"
        create_payload = {
            "rif": unique_rif,
            "legal_name": "TEST_Cliente Para GET",
            "fantasy_name": "TEST_GET Ref",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "sucursal": "Principal"
        }
        
        if self.test_bank:
            create_payload.update({
                "referidor_tipo": "BANCO",
                "referidor_id": self.test_bank["id"],
                "referidor_nombre": self.test_bank["name"],
                "referidor": self.test_bank["name"]
            })
        
        create_response = self.session.post(f"{BASE_URL}/api/clients", json=create_payload)
        assert create_response.status_code == 200, f"Failed to create test client: {create_response.text}"
        self.test_client = create_response.json()
        self.test_client_id = self.test_client["client_id"]
    
    def teardown_method(self, method):
        """Cleanup: Delete test client"""
        try:
            self.session.delete(f"{BASE_URL}/api/clients/{self.test_client_id}")
        except:
            pass
    
    def test_get_client_returns_referidor_fields(self):
        """GET /api/clients/{id} should return referidor_tipo, referidor_id, referidor_nombre"""
        response = self.session.get(f"{BASE_URL}/api/clients/{self.test_client_id}")
        assert response.status_code == 200, f"Failed to get client: {response.text}"
        
        data = response.json()
        
        # Verify referidor fields exist in response
        assert "referidor_tipo" in data, "Response should contain 'referidor_tipo' field"
        assert "referidor_id" in data, "Response should contain 'referidor_id' field"
        assert "referidor_nombre" in data, "Response should contain 'referidor_nombre' field"
        
        if self.test_bank:
            assert data.get("referidor_tipo") == "BANCO", f"Expected referidor_tipo=BANCO, got {data.get('referidor_tipo')}"
            assert data.get("referidor_id") == self.test_bank["id"], f"Expected referidor_id={self.test_bank['id']}, got {data.get('referidor_id')}"
            assert data.get("referidor_nombre") == self.test_bank["name"], f"Expected referidor_nombre={self.test_bank['name']}, got {data.get('referidor_nombre')}"
            print(f"✓ GET client returns referidor fields: tipo={data.get('referidor_tipo')}, nombre={data.get('referidor_nombre')}")
        else:
            print("✓ GET client returns referidor fields (no bank data to verify)")


class TestImportTemplateReferidorColumns:
    """Test GET /api/clients/template has referidor columns"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_template_has_referidor_columns(self):
        """GET /api/clients/template should have 'Referidor Tipo' and 'Referidor Identificador' columns"""
        response = self.session.get(f"{BASE_URL}/api/clients/template")
        assert response.status_code == 200, f"Failed to get template: {response.text}"
        
        # Check content type is Excel
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type or "excel" in content_type.lower() or "octet-stream" in content_type, \
            f"Expected Excel file, got content-type: {content_type}"
        
        # Check content disposition
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "plantilla_clientes.xlsx" in content_disposition, \
            f"Expected filename 'plantilla_clientes.xlsx', got: {content_disposition}"
        
        print("✓ Template download successful with correct filename")
        
        # Parse Excel to verify columns
        import io
        try:
            import pandas as pd
            excel_content = io.BytesIO(response.content)
            df = pd.read_excel(excel_content, sheet_name='Plantilla')
            columns = list(df.columns)
            
            assert 'Referidor Tipo' in columns, f"'Referidor Tipo' column not found. Columns: {columns}"
            assert 'Referidor Identificador' in columns, f"'Referidor Identificador' column not found. Columns: {columns}"
            
            print(f"✓ Template has 'Referidor Tipo' column at position {columns.index('Referidor Tipo')}")
            print(f"✓ Template has 'Referidor Identificador' column at position {columns.index('Referidor Identificador')}")
            
            # Check sample values
            if len(df) > 0:
                sample_tipo = df['Referidor Tipo'].iloc[0]
                sample_ident = df['Referidor Identificador'].iloc[0]
                print(f"✓ Sample values: Tipo='{sample_tipo}', Identificador='{sample_ident}'")
                
        except ImportError:
            print("⚠ pandas not available, skipping column verification")
            pytest.skip("pandas not available for Excel parsing")


class TestImportWithReferidorValidation:
    """Test POST /api/clients/import with referidor validation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@meganexus.com",
            "password": "Admin123!"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get referidor options for test data
        options_response = self.session.get(f"{BASE_URL}/api/clients/referidor-options")
        self.referidor_options = options_response.json() if options_response.status_code == 200 else {"banks": [], "clients": []}
        self.created_client_ids = []
    
    def teardown_method(self, method):
        """Cleanup: Delete test clients"""
        for client_id in self.created_client_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{client_id}")
            except:
                pass
    
    def test_import_with_banco_referidor(self):
        """Import client with referidor_tipo=BANCO should validate bank name"""
        import io
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not available")
        
        banks = self.referidor_options.get("banks", [])
        if not banks:
            pytest.skip("No banks available for testing")
        
        bank_name = banks[0]["name"]
        unique_rif = f"J-{int(time.time()) % 100000000}-1"
        
        # Create test Excel file
        data = {
            'RIF': [unique_rif],
            'Sucursal': ['Principal'],
            'Nombre Jurídico': ['TEST_Import Banco Ref'],
            'Nombre Fantasía': ['TEST_Import Banco'],
            'Segmento': ['Pymes'],
            'Condición': ['Prospecto'],
            'Referidor Tipo': ['BANCO'],
            'Referidor Identificador': [bank_name]
        }
        df = pd.DataFrame(data)
        
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        files = {'file': ('test_import.xlsx', excel_buffer, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": self.session.headers.get("Authorization")}
        response = requests.post(f"{BASE_URL}/api/clients/import", files=files, headers=headers)
        
        assert response.status_code == 200, f"Import failed: {response.text}"
        result = response.json()
        
        print(f"Import result: status={result.get('status')}, success={result.get('success_count')}, errors={result.get('error_count')}")
        
        if result.get('success_count', 0) > 0:
            # Find and verify the created client
            clients_response = self.session.get(f"{BASE_URL}/api/clients")
            if clients_response.status_code == 200:
                clients = clients_response.json()
                test_client = next((c for c in clients if c.get('rif', '').replace('-', '') == unique_rif.replace('-', '')), None)
                if test_client:
                    self.created_client_ids.append(test_client['client_id'])
                    assert test_client.get('referidor_tipo') == 'BANCO', f"Expected referidor_tipo=BANCO, got {test_client.get('referidor_tipo')}"
                    print(f"✓ Imported client has referidor_tipo=BANCO, referidor_nombre={test_client.get('referidor_nombre')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
