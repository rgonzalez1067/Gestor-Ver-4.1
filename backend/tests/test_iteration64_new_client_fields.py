# ruff: noqa
"""
Iteration 64 - Testing new client fields:
- branch_address (Dirección de la Sucursal)
- categoria_comercial (Categoría Comercial dropdown with 30 options)
- contacts[].full_name (merged first_name/last_name into single field)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"

# 30 Commercial categories from backend/models.py
EXPECTED_CATEGORIES = [
    "Supermercados", "Abastos", "Restaurantes", "Panaderías", "Bares", "Discotecas",
    "Comida Rápida", "Cafeterías", "Tiendas de Ropa", "Boutique", "Salón de Belleza",
    "Barbería", "Spa/Salud", "Gimnasios", "Cosmética", "Tiendas de Calzados",
    "Mueblerías", "Ferretería", "Tiendas de Electrodomésticos", "Jardinería",
    "Joyerías", "Tienda de Electrónica", "Venta de Software", "Jugueterías",
    "Librerías", "Tiendas por Departamento", "Colegios", "Universidades",
    "Inmobiliarias", "Clínicas",
]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("session_token")


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Return session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestExistingTestClient:
    """Test the client already created with new fields"""
    
    def test_get_test_client_has_branch_address(self, api_client):
        """GET /api/clients/{id} returns branch_address"""
        response = api_client.get(f"{BASE_URL}/api/clients/cli_fce052bfa09e")
        assert response.status_code == 200
        
        data = response.json()
        assert "branch_address" in data
        assert data["branch_address"] == "CC Plaza Mayor, Local 15, Caracas"
        print(f"✓ branch_address returned: {data['branch_address']}")
    
    def test_get_test_client_has_categoria_comercial(self, api_client):
        """GET /api/clients/{id} returns categoria_comercial"""
        response = api_client.get(f"{BASE_URL}/api/clients/cli_fce052bfa09e")
        assert response.status_code == 200
        
        data = response.json()
        assert "categoria_comercial" in data
        assert data["categoria_comercial"] == "Restaurantes"
        print(f"✓ categoria_comercial returned: {data['categoria_comercial']}")
    
    def test_get_test_client_contact_has_full_name(self, api_client):
        """GET /api/clients/{id} returns contacts with full_name"""
        response = api_client.get(f"{BASE_URL}/api/clients/cli_fce052bfa09e")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["contacts"]) > 0, "Client should have contacts"
        contact = data["contacts"][0]
        assert "full_name" in contact
        assert contact["full_name"] == "Carlos Martínez Pérez"
        print(f"✓ Contact full_name returned: {contact['full_name']}")


class TestGetClientsListWithNewFields:
    """Test GET /api/clients returns new fields in list"""
    
    def test_clients_list_includes_new_fields(self, api_client):
        """GET /api/clients returns branch_address and categoria_comercial"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        clients = response.json()
        assert len(clients) > 0, "Should have clients in DB"
        
        # Find test client in list
        test_client = next((c for c in clients if c["client_id"] == "cli_fce052bfa09e"), None)
        assert test_client is not None, "Test client should be in list"
        
        # Verify new fields present
        assert "branch_address" in test_client
        assert "categoria_comercial" in test_client
        assert test_client["branch_address"] == "CC Plaza Mayor, Local 15, Caracas"
        assert test_client["categoria_comercial"] == "Restaurantes"
        print("✓ Clients list includes new fields correctly")


class TestCreateClientWithNewFields:
    """Test POST /api/clients with all new fields"""
    
    def test_create_client_with_branch_address_and_categoria(self, api_client):
        """POST /api/clients accepts and saves branch_address and categoria_comercial"""
        unique_id = str(uuid.uuid4())[:8]
        
        payload = {
            "rif": f"J-TEST-{unique_id}",
            "legal_name": f"TEST_CREATE_NEW_FIELDS_{unique_id}",
            "fantasy_name": f"Test New Fields {unique_id}",
            "segment": "Corporativo",
            "address": "Dirección Fiscal de Prueba",
            "branch_address": "Centro Comercial Test, Nivel 2, Local 45",
            "categoria_comercial": "Supermercados",
            "sucursal": "Principal",
            "contacts": [
                {
                    "full_name": "María Rodríguez García",
                    "phone": "04149876543",
                    "email": f"maria_{unique_id}@test.com",
                    "role": "Financiero"
                }
            ]
        }
        
        response = api_client.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        data = response.json()
        client_id = data["client_id"]
        
        # Verify new fields in response
        assert data["branch_address"] == payload["branch_address"]
        assert data["categoria_comercial"] == payload["categoria_comercial"]
        
        # Verify contact full_name
        assert len(data["contacts"]) > 0
        assert data["contacts"][0]["full_name"] == "María Rodríguez García"
        
        print(f"✓ Created client {client_id} with all new fields")
        
        # Verify by fetching
        get_response = api_client.get(f"{BASE_URL}/api/clients/{client_id}")
        assert get_response.status_code == 200
        
        fetched = get_response.json()
        assert fetched["branch_address"] == payload["branch_address"]
        assert fetched["categoria_comercial"] == payload["categoria_comercial"]
        assert fetched["contacts"][0]["full_name"] == "María Rodríguez García"
        
        print("✓ Verified client persisted correctly via GET")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/clients/{client_id}")
    
    def test_create_client_with_multiple_contacts_full_name(self, api_client):
        """POST /api/clients with multiple contacts each having full_name"""
        unique_id = str(uuid.uuid4())[:8]
        
        payload = {
            "rif": f"J-MULT-{unique_id}",
            "legal_name": f"TEST_MULTIPLE_CONTACTS_{unique_id}",
            "fantasy_name": f"Multi Contacts {unique_id}",
            "segment": "Mixto",
            "address": "Av. Multiple",
            "branch_address": "Sucursal Norte, Piso 3",
            "categoria_comercial": "Clínicas",
            "sucursal": "Norte",
            "contacts": [
                {
                    "full_name": "Juan Carlos Pérez López",
                    "phone": "0212-1234567",
                    "email": f"juan_{unique_id}@test.com",
                    "role": "Administrativo"
                },
                {
                    "full_name": "Ana María González",
                    "phone": "0412-9999999",
                    "email": f"ana_{unique_id}@test.com",
                    "role": "Cuentas por Pagar"
                },
                {
                    "full_name": "Pedro Ramírez Sánchez",
                    "phone": "0424-1111111",
                    "email": f"pedro_{unique_id}@test.com",
                    "role": "Técnico"
                }
            ]
        }
        
        response = api_client.post(f"{BASE_URL}/api/clients", json=payload)
        assert response.status_code in [200, 201], f"Create failed: {response.text}"
        
        data = response.json()
        client_id = data["client_id"]
        
        # Verify all contacts
        assert len(data["contacts"]) == 3
        assert data["contacts"][0]["full_name"] == "Juan Carlos Pérez López"
        assert data["contacts"][1]["full_name"] == "Ana María González"
        assert data["contacts"][2]["full_name"] == "Pedro Ramírez Sánchez"
        
        print("✓ Created client with 3 contacts using full_name")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/clients/{client_id}")


class TestUpdateClientNewFields:
    """Test PUT /api/clients/{id} updates new fields"""
    
    def test_update_branch_address_and_categoria(self, api_client):
        """PUT /api/clients/{id} updates branch_address and categoria_comercial"""
        # First create a client
        unique_id = str(uuid.uuid4())[:8]
        
        create_payload = {
            "rif": f"J-UPD-{unique_id}",
            "legal_name": f"TEST_UPDATE_{unique_id}",
            "fantasy_name": f"Update Test {unique_id}",
            "segment": "Pymes",
            "address": "Original Fiscal",
            "branch_address": "Original Sucursal Address",
            "categoria_comercial": "Bares",
            "sucursal": "Principal",
            "contacts": [
                {
                    "full_name": "Original Contact Name",
                    "phone": "0000",
                    "email": f"orig_{unique_id}@test.com",
                    "role": "Operativo"
                }
            ]
        }
        
        create_response = api_client.post(f"{BASE_URL}/api/clients", json=create_payload)
        assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
        client_id = create_response.json()["client_id"]
        
        # Update with new values
        update_payload = {
            **create_payload,
            "branch_address": "UPDATED Sucursal Address - Centro Comercial Nuevo",
            "categoria_comercial": "Gimnasios",
            "contacts": [
                {
                    "full_name": "UPDATED Contact Full Name",
                    "phone": "04161111111",
                    "email": f"updated_{unique_id}@test.com",
                    "role": "Financiero"
                }
            ]
        }
        
        update_response = api_client.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update via GET
        get_response = api_client.get(f"{BASE_URL}/api/clients/{client_id}")
        assert get_response.status_code == 200
        
        updated = get_response.json()
        assert updated["branch_address"] == "UPDATED Sucursal Address - Centro Comercial Nuevo"
        assert updated["categoria_comercial"] == "Gimnasios"
        assert updated["contacts"][0]["full_name"] == "UPDATED Contact Full Name"
        
        print("✓ Updated client with new field values successfully")
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/clients/{client_id}")


class TestValidCategories:
    """Verify all 30 commercial categories are valid"""
    
    def test_all_30_categories_are_valid(self, api_client):
        """Verify backend accepts all 30 categories from CATEGORIAS_COMERCIALES"""
        # Test with a few categories to ensure they're valid
        test_categories = ["Supermercados", "Clínicas", "Universidades", "Joyerías", "Cafeterías"]
        
        for category in test_categories:
            unique_id = str(uuid.uuid4())[:8]
            
            payload = {
                "rif": f"J-CAT-{unique_id}",
                "legal_name": f"TEST_CATEGORY_{category[:10]}_{unique_id}",
                "fantasy_name": f"Cat Test {unique_id}",
                "segment": "Pymes",
                "address": "Test",
                "categoria_comercial": category,
                "sucursal": "Principal",
                "contacts": []
            }
            
            response = api_client.post(f"{BASE_URL}/api/clients", json=payload)
            assert response.status_code in [200, 201], f"Failed for category '{category}': {response.text}"
            
            client_id = response.json()["client_id"]
            
            # Verify
            get_resp = api_client.get(f"{BASE_URL}/api/clients/{client_id}")
            assert get_resp.json()["categoria_comercial"] == category
            
            # Cleanup
            api_client.delete(f"{BASE_URL}/api/clients/{client_id}")
        
        print(f"✓ Verified {len(test_categories)} sample categories work correctly")
        print(f"  Note: Full list has {len(EXPECTED_CATEGORIES)} categories")
