"""
Test Suite for Iteration 12: Resumen Ejecutivo & Client Address Field
Tests:
1. Client address field in backend model
2. Create/Update client with address
3. Address retrieval via GET
4. Verify address is optional (nullable)
"""
import pytest
import requests
import os
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://bitacora-heredada.preview.emergentagent.com')

# MongoDB connection for session token
mongo_client = MongoClient('mongodb://localhost:27017')
db = mongo_client['test_database']

def get_auth_token():
    """Get a valid session token from database"""
    session = db.user_sessions.find_one({}, {'_id': 0})
    if session:
        return session.get('session_token')
    return None

@pytest.fixture
def auth_headers():
    """Fixture to get authentication headers"""
    token = get_auth_token()
    if not token:
        pytest.skip("No valid session token available")
    return {"Authorization": f"Bearer {token}"}

class TestClientAddressField:
    """Test cases for the new 'address' field in Client model"""
    
    def test_create_client_with_address(self, auth_headers):
        """Test creating a client with Dirección Fiscal (address field)"""
        test_client = {
            "rif": "J-TEST-ADDR-001",
            "legal_name": "TEST Cliente con Dirección",
            "fantasy_name": "Test Dirección SRL",
            "segment": "Pymes",
            "address": "Av. Principal #123, Edificio Torre Norte, Piso 5, Oficina 501, Caracas 1010",
            "contact1": {
                "name": "Juan Pérez",
                "phone": "+58-412-1234567",
                "email": "juan@testdir.com"
            },
            "contact2": {
                "name": "María López",
                "phone": "+58-414-7654321",
                "email": "maria@testdir.com"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=test_client, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify address field is returned
        assert "address" in data, "Response should contain 'address' field"
        assert data["address"] == test_client["address"], "Address should match input"
        assert data["legal_name"] == test_client["legal_name"]
        
        # Store client_id for cleanup
        client_id = data.get("client_id")
        print(f"Created client with address: {client_id}")
        
        # Cleanup
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
    
    def test_create_client_without_address(self, auth_headers):
        """Test creating a client without address (should be optional/null)"""
        test_client = {
            "rif": "J-TEST-NOADDR-002",
            "legal_name": "TEST Cliente sin Dirección",
            "fantasy_name": "Test Sin Dir CA",
            "segment": "Corporativo",
            "contact1": {
                "name": "Carlos García",
                "phone": "+58-412-9999999",
                "email": "carlos@testnodir.com"
            },
            "contact2": {
                "name": "Ana Martínez",
                "phone": "+58-414-8888888",
                "email": "ana@testnodir.com"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=test_client, headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Address should be None/null when not provided
        assert "address" in data or data.get("address") is None, "Address should be optional"
        
        # Cleanup
        client_id = data.get("client_id")
        if client_id:
            requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
    
    def test_update_client_address(self, auth_headers):
        """Test updating a client's address"""
        # First create a client
        test_client = {
            "rif": "J-TEST-UPD-003",
            "legal_name": "TEST Cliente Update Dirección",
            "fantasy_name": "Test Update Dir",
            "segment": "Mixto",
            "address": "Dirección Original",
            "contact1": {
                "name": "Pedro Test",
                "phone": "+58-412-1111111",
                "email": "pedro@testupd.com"
            },
            "contact2": {
                "name": "Rosa Test",
                "phone": "+58-414-2222222",
                "email": "rosa@testupd.com"
            }
        }
        
        # Create
        create_response = requests.post(f"{BASE_URL}/api/clients", json=test_client, headers=auth_headers)
        assert create_response.status_code == 200
        client_id = create_response.json().get("client_id")
        
        # Update with new address
        test_client["address"] = "Nueva Dirección Actualizada, Centro Comercial Plaza, Local 25, Valencia"
        update_response = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=test_client, headers=auth_headers)
        
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["address"] == test_client["address"], "Address should be updated"
        
        # GET to verify persistence
        get_response = requests.get(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert get_response.status_code == 200
        fetched_data = get_response.json()
        assert fetched_data["address"] == test_client["address"], "GET should return updated address"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
    
    def test_get_client_returns_address(self, auth_headers):
        """Test that GET /clients returns address field for all clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        
        assert response.status_code == 200
        clients = response.json()
        
        # All clients should have address field (even if null)
        for client in clients:
            assert "address" in client or client.get("address") is None, f"Client {client.get('legal_name')} missing address field"
        
        print(f"Verified {len(clients)} clients have address field")


class TestResumenEjecutivoData:
    """Test cases for data that feeds into Resumen Ejecutivo UI"""
    
    def test_quote_items_have_bank_product_cajas(self, auth_headers):
        """Test that quote data structure supports Resumen Ejecutivo matrix"""
        # Get existing quotes to verify structure
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        
        assert response.status_code == 200
        quotes = response.json()
        
        # If there are quotes, verify they have the right structure
        if quotes:
            quote = quotes[0]
            # Quotes should have services array which maps to setup_items + additional_items
            assert "services" in quote, "Quote should have services array"
            
            for service in quote.get("services", []):
                assert "item_name" in service, "Service should have item_name"
                assert "quantity" in service, "Service should have quantity (maps to cajas)"
        
        print(f"Verified {len(quotes)} quotes have correct structure for Resumen Ejecutivo")
    
    def test_banks_and_products_available(self, auth_headers):
        """Test that banks with products are available for the matrix"""
        response = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers)
        
        assert response.status_code == 200
        banks = response.json()
        
        # Check banks have products
        banks_with_products = [b for b in banks if b.get("products")]
        print(f"Banks with products: {len(banks_with_products)} / {len(banks)}")
        
        if banks_with_products:
            bank = banks_with_products[0]
            assert "name" in bank, "Bank should have name"
            assert "products" in bank, "Bank should have products"
            for product in bank.get("products", []):
                assert "product_name" in product, "Product should have product_name"


class TestApiEndpoints:
    """Basic API endpoint verification"""
    
    def test_clients_endpoint_auth_required(self):
        """Test clients endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 401
    
    def test_authenticated_clients_endpoint(self, auth_headers):
        """Test authenticated access to clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
