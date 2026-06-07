# ruff: noqa
"""
Test suite for Iteration 81 - Integrators Module Simplification
Testing:
1. Evolution log endpoints with contact_person field
2. Bitácora endpoints with contact_name field  
3. Verification that phase field is backward compatible but not required
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_headers():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "test@test.com", "password": "Test1234!"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("session_token")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_integrator(auth_headers):
    """Create a test integrator with contacts for testing"""
    payload = {
        "name": f"TEST_Integrator_Simplification_{datetime.now().strftime('%H%M%S')}",
        "integrator_type": "Integrador",
        "integration_type": "PG",
        "app_name": "TestApp",
        "integration_modality": "REST",
        "integrator_status": "En proceso",
        "contacts": [
            {"name": "Juan Contacto", "email": "juan@test.com", "phone": "+58 412-1234567"},
            {"name": "Maria Contacto", "email": "maria@test.com", "phone": "+58 424-7654321"}
        ]
    }
    response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
    assert response.status_code == 200, f"Create integrator failed: {response.text}"
    integrator = response.json()
    
    yield integrator
    
    # Cleanup
    requests.delete(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}", headers=auth_headers)


class TestEvolutionEndpoints:
    """Test evolution log CRUD with contact_person field"""
    
    def test_create_evolution_with_contact_person(self, auth_headers, test_integrator):
        """POST /api/integrators/{id}/evolution accepts contact_person field"""
        payload = {
            "comment": "TEST evolution entry with contact person",
            "contact_person": "Juan Contacto",
            "date": "2026-01-15"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create evolution failed: {response.text}"
        
        data = response.json()
        assert "entry_id" in data
        assert data["entry_id"].startswith("evo_")
        assert data["comment"] == payload["comment"]
        assert data["contact_person"] == payload["contact_person"]
        assert data["date"] == payload["date"]
        
    def test_create_evolution_without_contact_person(self, auth_headers, test_integrator):
        """POST /api/integrators/{id}/evolution works without contact_person (optional)"""
        payload = {
            "comment": "TEST evolution entry without contact person",
            "date": "2026-01-14"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["comment"] == payload["comment"]
        # contact_person should be empty or not present
        assert data.get("contact_person", "") == ""
        
    def test_create_evolution_with_free_text_contact(self, auth_headers, test_integrator):
        """Evolution accepts any free text for contact_person (not just from contacts list)"""
        payload = {
            "comment": "TEST with free text contact",
            "contact_person": "External Person Not In Contacts",
            "date": "2026-01-13"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["contact_person"] == "External Person Not In Contacts"
        
    def test_get_evolution_returns_contact_person(self, auth_headers, test_integrator):
        """GET /api/integrators/{id}/evolution returns entries with contact_person"""
        response = requests.get(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        entries = response.json()
        assert isinstance(entries, list)
        # Check that entries have contact_person field
        for entry in entries:
            assert "contact_person" in entry
            assert "comment" in entry
            assert "date" in entry
            assert "entry_id" in entry
            
    def test_update_evolution_contact_person(self, auth_headers, test_integrator):
        """PATCH /api/integrators/{id}/evolution/{entry_id} can update contact_person"""
        # First create an entry
        create_payload = {
            "comment": "TEST entry to update",
            "contact_person": "Original Contact",
            "date": "2026-01-12"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=create_payload,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["entry_id"]
        
        # Update the contact_person
        update_payload = {
            "contact_person": "Updated Contact Person"
        }
        response = requests.patch(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution/{entry_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["contact_person"] == "Updated Contact Person"
        assert "updated_at" in data
        
    def test_delete_evolution_entry(self, auth_headers, test_integrator):
        """DELETE /api/integrators/{id}/evolution/{entry_id} removes entry"""
        # Create entry to delete
        create_payload = {
            "comment": "TEST entry to delete",
            "contact_person": "Delete Test",
            "date": "2026-01-11"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=create_payload,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["entry_id"]
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution/{entry_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify it's deleted
        get_response = requests.get(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            headers=auth_headers
        )
        entries = get_response.json()
        entry_ids = [e["entry_id"] for e in entries]
        assert entry_id not in entry_ids


class TestBitacoraEndpoints:
    """Test bitácora (management log) with contact_name field"""
    
    def test_create_bitacora_with_contact_name(self, auth_headers, test_integrator):
        """POST /api/integrators/{id}/bitacora accepts contact_name as free text"""
        payload = {
            "description": "TEST bitacora entry with contact name",
            "contact_name": "Maria Contacto",
            "date": "2026-01-15"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create bitacora failed: {response.text}"
        
        data = response.json()
        assert "entry_id" in data
        assert data["entry_id"].startswith("bit_")
        assert data["description"] == payload["description"]
        assert data["contact_name"] == payload["contact_name"]
        
    def test_create_bitacora_with_free_text_contact(self, auth_headers, test_integrator):
        """Bitácora accepts any free text for contact_name"""
        payload = {
            "description": "TEST bitacora with free text contact",
            "contact_name": "External Contact Not In List",
            "date": "2026-01-14"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["contact_name"] == "External Contact Not In List"
        
    def test_get_bitacora_returns_entries(self, auth_headers, test_integrator):
        """GET /api/integrators/{id}/bitacora returns entries with contact_name"""
        response = requests.get(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/bitacora",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        entries = response.json()
        assert isinstance(entries, list)
        for entry in entries:
            assert "entry_id" in entry
            assert "description" in entry
            # contact_name is optional but should be present in schema
            
    def test_update_bitacora_contact_name(self, auth_headers, test_integrator):
        """PATCH /api/integrators/{id}/bitacora/{entry_id} can update contact_name"""
        # Create entry
        create_payload = {
            "description": "TEST bitacora to update",
            "contact_name": "Original Name",
            "date": "2026-01-13"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/bitacora",
            json=create_payload,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        entry_id = create_response.json()["entry_id"]
        
        # Update
        update_payload = {"contact_name": "Updated Name"}
        response = requests.patch(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/bitacora/{entry_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["contact_name"] == "Updated Name"


class TestIntegratorTable:
    """Test that the integrators table returns correct fields (no Estatus/Fase columns)"""
    
    def test_get_integrators_returns_expected_fields(self, auth_headers):
        """GET /api/integrators returns integrators with expected structure"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert response.status_code == 200
        
        integrators = response.json()
        assert isinstance(integrators, list)
        
        if len(integrators) > 0:
            intg = integrators[0]
            # These fields should exist (used by table columns)
            assert "name" in intg
            assert "integration_type" in intg  # T.Int column
            assert "integrator_type" in intg   # Tipo column
            assert "app_name" in intg          # Aplicativo column
            assert "integration_modality" in intg  # Modalidad column
            assert "gestor" in intg            # Gestor column
            assert "categoria" in intg         # Categoría column
            assert "last_contact_date" in intg # Últ. Contacto column
            assert "integrator_id" in intg     # Acciones column (for actions)
            
            # These fields exist in backend but NOT shown as columns
            assert "integrator_status" in intg  # Used internally, not as visible column
            

class TestIntegratorFormFields:
    """Test that integrator create/update doesn't require 'Fase' field"""
    
    def test_create_integrator_without_phase(self, auth_headers):
        """POST /api/integrators works without integration_phase field"""
        payload = {
            "name": f"TEST_NoPhase_{datetime.now().strftime('%H%M%S')}",
            "integrator_type": "Comercio",
            "integration_type": "CR",
            "app_name": "TestApp",
            "integration_modality": "MPOS",
            "integrator_status": "En proceso"
            # Note: No integration_phase field
        }
        response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        intg = response.json()
        assert intg["name"] == payload["name"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{intg['integrator_id']}", headers=auth_headers)
        
    def test_update_integrator_without_phase(self, auth_headers, test_integrator):
        """PUT /api/integrators/{id} works without integration_phase"""
        payload = {
            "name": test_integrator["name"],
            "integrator_type": test_integrator["integrator_type"],
            "integration_type": test_integrator["integration_type"],
            "app_name": "UpdatedAppName",
            "integration_modality": test_integrator["integration_modality"],
            "integrator_status": "En proceso"
            # No integration_phase
        }
        response = requests.put(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["app_name"] == "UpdatedAppName"


class TestEvolutionBackwardsCompatibility:
    """Test that evolution entries still work with legacy 'phase' field for backwards compatibility"""
    
    def test_evolution_still_accepts_phase_field(self, auth_headers, test_integrator):
        """Evolution endpoint still accepts phase field for backward compatibility"""
        payload = {
            "comment": "TEST backward compat with phase",
            "phase": "Desarrollo",  # Legacy field
            "contact_person": "New Contact Field",
            "date": "2026-01-10"
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # Both fields should be stored
        assert data["contact_person"] == "New Contact Field"
        # phase may still be stored for backward compat
        
    def test_update_evolution_with_phase_still_works(self, auth_headers, test_integrator):
        """PATCH evolution still allows updating phase field"""
        # Create entry
        create_payload = {
            "comment": "TEST update phase",
            "date": "2026-01-09"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution",
            json=create_payload,
            headers=auth_headers
        )
        entry_id = create_response.json()["entry_id"]
        
        # Update with both phase and contact_person
        update_payload = {
            "phase": "QA",
            "contact_person": "Updated via PATCH"
        }
        response = requests.patch(
            f"{BASE_URL}/api/integrators/{test_integrator['integrator_id']}/evolution/{entry_id}",
            json=update_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["contact_person"] == "Updated via PATCH"
