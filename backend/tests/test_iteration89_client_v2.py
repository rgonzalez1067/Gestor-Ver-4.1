# ruff: noqa
"""
Test iteration 89: Client Form v2.0 Redesign (4 Quadrants)
- New fields: condicion (Prospecto/Cliente), cantidad_tiendas, cantidad_cajas, ejecutivo_user_id
- Backend: POST/PUT clients with new fields persist correctly
- Backend: GET /api/auth/ejecutivos filters by cargo (Ejecutivo de Ventas Pyme, Ejecutivo de Ventas Corporativas)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

@pytest.fixture(scope="module")
def auth_session():
    """Login and get session token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gestor.com",
        "password": "Admin2026!"
    })
    
    if login_response.status_code != 200:
        pytest.skip(f"Auth failed: {login_response.text}")
    
    token = login_response.json().get("session_token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


class TestEjecutivosEndpoint:
    """Test GET /api/auth/ejecutivos - should return only users with Ejecutivo cargo"""
    
    def test_ejecutivos_endpoint_returns_200(self, auth_session):
        """Verify the endpoint returns 200"""
        response = auth_session.get(f"{BASE_URL}/api/auth/ejecutivos")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("GET /api/auth/ejecutivos returned status 200")
    
    def test_ejecutivos_returns_list(self, auth_session):
        """Verify the endpoint returns a list"""
        response = auth_session.get(f"{BASE_URL}/api/auth/ejecutivos")
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"Endpoint returns list with {len(data)} ejecutivos")
    
    def test_ejecutivos_filters_by_cargo(self, auth_session):
        """Verify only users with 'Ejecutivo de Ventas Pyme' or 'Ejecutivo de Ventas Corporativas' are returned"""
        response = auth_session.get(f"{BASE_URL}/api/auth/ejecutivos")
        assert response.status_code == 200
        
        ejecutivos = response.json()
        valid_cargos = ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]
        
        for ej in ejecutivos:
            cargo = ej.get("cargo", "")
            assert cargo in valid_cargos, f"User {ej.get('full_name')} has cargo '{cargo}' which is not in {valid_cargos}"
            print(f"  - {ej.get('full_name')}: {cargo} ✓")
        
        print(f"All {len(ejecutivos)} ejecutivos have valid cargo")
    
    def test_ejecutivos_have_required_fields(self, auth_session):
        """Verify ejecutivos have user_id, full_name, cargo fields"""
        response = auth_session.get(f"{BASE_URL}/api/auth/ejecutivos")
        ejecutivos = response.json()
        
        for ej in ejecutivos:
            assert "user_id" in ej, "Missing user_id for ejecutivo"
            assert "full_name" in ej, "Missing full_name for ejecutivo"
            assert "cargo" in ej, "Missing cargo for ejecutivo"
        
        print("All ejecutivos have required fields: user_id, full_name, cargo")


class TestClientCreateWithNewFields:
    """Test POST /api/clients with new v2 fields"""
    
    def test_create_client_with_condicion_prospecto(self, auth_session):
        """Create client with condicion=Prospecto"""
        payload = {
            "rif": "TEST_J999888771",
            "legal_name": "TEST Empresa Prospecto CA",
            "fantasy_name": "TEST ProspectoCorp",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact", "phone": "0412-1234567", "email": "test@test.com", "role": "Administrativo"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("condicion") == "Prospecto", f"Expected condicion 'Prospecto', got {data.get('condicion')}"
        print(f"Created client with condicion='Prospecto' - client_id: {data.get('client_id')}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")
    
    def test_create_client_with_condicion_cliente(self, auth_session):
        """Create client with condicion=Cliente"""
        payload = {
            "rif": "TEST_J999888772",
            "legal_name": "TEST Empresa Cliente CA",
            "fantasy_name": "TEST ClienteCorp",
            "segment": "Corporativo",
            "condicion": "Cliente",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Test Contact 2", "phone": "0414-9876543", "email": "test2@test.com", "role": "Financiero"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("condicion") == "Cliente", f"Expected condicion 'Cliente', got {data.get('condicion')}"
        print(f"Created client with condicion='Cliente' - client_id: {data.get('client_id')}")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")
    
    def test_create_client_with_cantidad_tiendas(self, auth_session):
        """Create client with cantidad_tiendas field"""
        payload = {
            "rif": "TEST_J999888773",
            "legal_name": "TEST Multi-Tiendas CA",
            "fantasy_name": "TEST MultiStore",
            "segment": "Corporativo",
            "condicion": "Cliente",
            "cantidad_tiendas": 15,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Store Manager", "phone": "0416-5551234", "email": "manager@multi.com", "role": "Operativo"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("cantidad_tiendas") == 15, f"Expected cantidad_tiendas=15, got {data.get('cantidad_tiendas')}"
        print("Created client with cantidad_tiendas=15")
        
        # Verify persistence via GET
        get_response = auth_session.get(f"{BASE_URL}/api/clients/{data.get('client_id')}")
        fetched = get_response.json()
        assert fetched.get("cantidad_tiendas") == 15, f"Persistence failed: expected 15, got {fetched.get('cantidad_tiendas')}"
        print("Verified cantidad_tiendas persisted correctly via GET")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")
    
    def test_create_client_with_cantidad_cajas(self, auth_session):
        """Create client with cantidad_cajas field"""
        payload = {
            "rif": "TEST_J999888774",
            "legal_name": "TEST Cajas Corp CA",
            "fantasy_name": "TEST CajasCorp",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "cantidad_cajas": 50,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Cajero Jefe", "phone": "0424-7778899", "email": "cajas@corp.com", "role": "Operativo"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("cantidad_cajas") == 50, f"Expected cantidad_cajas=50, got {data.get('cantidad_cajas')}"
        print("Created client with cantidad_cajas=50")
        
        # Verify persistence via GET
        get_response = auth_session.get(f"{BASE_URL}/api/clients/{data.get('client_id')}")
        fetched = get_response.json()
        assert fetched.get("cantidad_cajas") == 50, f"Persistence failed: expected 50, got {fetched.get('cantidad_cajas')}"
        print("Verified cantidad_cajas persisted correctly via GET")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")
    
    def test_create_client_with_all_new_v2_fields(self, auth_session):
        """Create client with all new v2 fields: condicion, cantidad_tiendas, cantidad_cajas, ejecutivo_user_id"""
        # First get an ejecutivo
        ej_response = auth_session.get(f"{BASE_URL}/api/auth/ejecutivos")
        ejecutivos = ej_response.json()
        
        ejecutivo_id = None
        ejecutivo_name = ""
        if ejecutivos:
            ejecutivo_id = ejecutivos[0].get("user_id")
            ejecutivo_name = ejecutivos[0].get("full_name")
        
        payload = {
            "rif": "TEST_J999888775",
            "legal_name": "TEST Full V2 Corp CA",
            "fantasy_name": "TEST FullV2Corp",
            "segment": "Corporativo",
            "condicion": "Cliente",
            "cantidad_tiendas": 25,
            "cantidad_cajas": 100,
            "ejecutivo_user_id": ejecutivo_id,
            "ejecutivo_propietario": ejecutivo_name,
            "sucursal": "Sede Central",
            "address": "Av. Principal Centro, Torre X",
            "grupo_economico": "TEST Grupo Mega",
            "categoria_comercial": "Supermercado",
            "tipo_servicio": ["VPOS", "Payment Gateway"],
            "contacts": [{"full_name": "Director Comercial", "phone": "0212-5550000", "email": "director@fullv2.com", "role": "Administrativo"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify all new fields
        assert data.get("condicion") == "Cliente"
        assert data.get("cantidad_tiendas") == 25
        assert data.get("cantidad_cajas") == 100
        if ejecutivo_id:
            assert data.get("ejecutivo_user_id") == ejecutivo_id
            assert data.get("ejecutivo_propietario") == ejecutivo_name
        
        print("Created client with ALL v2 fields:")
        print(f"  - condicion: {data.get('condicion')}")
        print(f"  - cantidad_tiendas: {data.get('cantidad_tiendas')}")
        print(f"  - cantidad_cajas: {data.get('cantidad_cajas')}")
        print(f"  - ejecutivo_user_id: {data.get('ejecutivo_user_id')}")
        print(f"  - ejecutivo_propietario: {data.get('ejecutivo_propietario')}")
        
        # Verify via GET
        get_response = auth_session.get(f"{BASE_URL}/api/clients/{data.get('client_id')}")
        fetched = get_response.json()
        assert fetched.get("condicion") == "Cliente"
        assert fetched.get("cantidad_tiendas") == 25
        assert fetched.get("cantidad_cajas") == 100
        print("All v2 fields verified via GET")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")


class TestClientUpdateWithNewFields:
    """Test PUT /api/clients/{id} with new v2 fields"""
    
    def test_update_condicion_prospecto_to_cliente(self, auth_session):
        """Create as Prospecto, update to Cliente"""
        # Create
        create_payload = {
            "rif": "TEST_J999888776",
            "legal_name": "TEST Update Condicion CA",
            "fantasy_name": "TEST UpdateCond",
            "segment": "Pymes",
            "condicion": "Prospecto",
            "sucursal": "Principal",
            "contacts": [{"full_name": "Contact", "phone": "0412-0000001", "email": "upd@test.com", "role": "Administrativo"}]
        }
        
        create_response = auth_session.post(f"{BASE_URL}/api/clients", json=create_payload)
        assert create_response.status_code == 200
        created = create_response.json()
        client_id = created.get("client_id")
        
        assert created.get("condicion") == "Prospecto"
        print("Created client as Prospecto")
        
        # Update to Cliente
        update_payload = {**create_payload, "condicion": "Cliente"}
        update_response = auth_session.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload)
        assert update_response.status_code == 200
        
        updated = update_response.json()
        assert updated.get("condicion") == "Cliente", f"Expected 'Cliente', got {updated.get('condicion')}"
        print("Updated condicion to Cliente successfully")
        
        # Verify via GET
        get_response = auth_session.get(f"{BASE_URL}/api/clients/{client_id}")
        fetched = get_response.json()
        assert fetched.get("condicion") == "Cliente"
        print("Verified condicion change persisted via GET")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{client_id}")
    
    def test_update_cantidad_tiendas_and_cajas(self, auth_session):
        """Create client, then update cantidad_tiendas and cantidad_cajas"""
        # Create
        create_payload = {
            "rif": "TEST_J999888777",
            "legal_name": "TEST Update Cantidades CA",
            "fantasy_name": "TEST UpdCant",
            "segment": "Corporativo",
            "condicion": "Cliente",
            "cantidad_tiendas": 5,
            "cantidad_cajas": 20,
            "sucursal": "Principal",
            "contacts": [{"full_name": "Ops Manager", "phone": "0412-0000002", "email": "ops@test.com", "role": "Operativo"}]
        }
        
        create_response = auth_session.post(f"{BASE_URL}/api/clients", json=create_payload)
        assert create_response.status_code == 200
        created = create_response.json()
        client_id = created.get("client_id")
        
        print(f"Created client: tiendas={created.get('cantidad_tiendas')}, cajas={created.get('cantidad_cajas')}")
        
        # Update quantities
        update_payload = {**create_payload, "cantidad_tiendas": 30, "cantidad_cajas": 150}
        update_response = auth_session.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload)
        assert update_response.status_code == 200
        
        updated = update_response.json()
        assert updated.get("cantidad_tiendas") == 30
        assert updated.get("cantidad_cajas") == 150
        print(f"Updated quantities: tiendas={updated.get('cantidad_tiendas')}, cajas={updated.get('cantidad_cajas')}")
        
        # Verify via GET
        get_response = auth_session.get(f"{BASE_URL}/api/clients/{client_id}")
        fetched = get_response.json()
        assert fetched.get("cantidad_tiendas") == 30
        assert fetched.get("cantidad_cajas") == 150
        print("Verified updated quantities persisted via GET")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{client_id}")


class TestCondicionDefaultValue:
    """Test that condicion defaults to 'Prospecto' when not provided"""
    
    def test_condicion_defaults_to_prospecto(self, auth_session):
        """Create client without specifying condicion - should default to Prospecto"""
        payload = {
            "rif": "TEST_J999888778",
            "legal_name": "TEST Default Condicion CA",
            "fantasy_name": "TEST DefCond",
            "segment": "Pymes",
            # No condicion specified
            "sucursal": "Principal",
            "contacts": [{"full_name": "Default Test", "phone": "0412-0000003", "email": "def@test.com", "role": "Administrativo"}]
        }
        
        response = auth_session.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # Default should be Prospecto as defined in models.py
        assert data.get("condicion") == "Prospecto", f"Expected default 'Prospecto', got {data.get('condicion')}"
        print("Verified condicion defaults to 'Prospecto' when not provided")
        
        # Cleanup
        auth_session.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
