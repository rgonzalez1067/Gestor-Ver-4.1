"""
Iteration 79 - Tests for Technical Contacts and Bitácora Module
Features tested:
1. POST /api/integrators - Create integrator with contacts array [{name, email, phone}]
2. PUT /api/integrators/{id} - Update integrator with contacts
3. GET /api/integrators - Verify has_overdue_commitments flag returned
4. POST /api/integrators/{id}/bitacora - Create entry with description, contact_id, date, commitment, commitment_deadline
   - Auto-updates last_contact_date on integrator
5. GET /api/integrators/{id}/bitacora - Get chronological history
6. PATCH /api/integrators/{id}/bitacora/{entry_id} - Mark commitment as completed
7. DELETE /api/integrators/{id}/bitacora/{entry_id} - Delete entry
"""
import pytest
import requests
import os
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Auth setup for all tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Authenticate and get session_token"""
        # Try admin first
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin1234"
        })
        
        if response.status_code != 200:
            # Register test user
            requests.post(f"{BASE_URL}/api/auth/register", json={
                "first_name": "Test",
                "last_name": "User79",
                "email": "testuser79@test.com",
                "password": "Test1234!",
                "cedula": "V12345679",
                "sede": "TBP"
            })
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "testuser79@test.com",
                "password": "Test1234!"
            })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("session_token") or data.get("token")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestIntegratorWithContacts(TestAuthentication):
    """Test POST/PUT /api/integrators with contacts array"""
    
    def test_create_integrator_with_contacts(self, auth_headers):
        """Create integrator with array of technical contacts"""
        payload = {
            "name": "TEST_ContactsIntg79",
            "integrator_type": "Integrador",
            "integration_type": "PG",
            "app_name": "ContactsApp79",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso",
            "contacts": [
                {"name": "Juan Pérez", "email": "juan@test.com", "phone": "+58 412-1234567"},
                {"name": "María García", "email": "maria@test.com", "phone": "+58 414-9876543"}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert "contacts" in data, "contacts field missing in response"
        assert len(data["contacts"]) == 2, f"Expected 2 contacts, got {len(data['contacts'])}"
        
        # Verify contact structure
        contact = data["contacts"][0]
        assert "contact_id" in contact, "contact_id missing"
        assert contact["name"] == "Juan Pérez", f"Contact name mismatch: {contact['name']}"
        assert contact["email"] == "juan@test.com", f"Contact email mismatch: {contact['email']}"
        
        # Store ID for cleanup
        integrator_id = data["integrator_id"]
        print(f"PASSED: Created integrator with 2 contacts. ID: {integrator_id}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
    
    def test_update_integrator_contacts(self, auth_headers):
        """Update integrator with modified contacts"""
        # First create
        create_payload = {
            "name": "TEST_UpdateContacts79",
            "integrator_type": "Comercio",
            "app_name": "UpdateApp79",
            "integration_modality": "MPOS",
            "integrator_status": "En proceso",
            "contacts": [{"name": "Initial Contact", "email": "initial@test.com", "phone": "+58 412-0000000"}]
        }
        create_resp = requests.post(f"{BASE_URL}/api/integrators", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 200
        integrator_id = create_resp.json()["integrator_id"]
        
        # Update with new contacts
        update_payload = {
            "name": "TEST_UpdateContacts79",
            "integrator_type": "Comercio",
            "app_name": "UpdateApp79Updated",
            "integration_modality": "MPOS",
            "integrator_status": "Certificado",
            "contacts": [
                {"name": "New Contact 1", "email": "new1@test.com", "phone": "+58 412-1111111"},
                {"name": "New Contact 2", "email": "new2@test.com", "phone": "+58 412-2222222"},
                {"name": "New Contact 3", "email": "new3@test.com", "phone": "+58 412-3333333"}
            ]
        }
        
        update_resp = requests.put(f"{BASE_URL}/api/integrators/{integrator_id}", json=update_payload, headers=auth_headers)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        
        updated = update_resp.json()
        assert len(updated["contacts"]) == 3, f"Expected 3 contacts after update, got {len(updated['contacts'])}"
        
        # Verify via GET
        get_resp = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
        fetched = get_resp.json()
        assert len(fetched["contacts"]) == 3
        
        print(f"PASSED: Updated integrator with 3 contacts")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
    
    def test_create_integrator_without_contacts(self, auth_headers):
        """Create integrator without contacts (should work)"""
        payload = {
            "name": "TEST_NoContacts79",
            "integrator_type": "Integrador",
            "app_name": "NoContactsApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        
        response = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        # contacts should be None or empty list
        contacts = data.get("contacts") or []
        assert len(contacts) == 0, f"Expected no contacts, got {len(contacts)}"
        
        print(f"PASSED: Created integrator without contacts")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{data['integrator_id']}", headers=auth_headers)


class TestHasOverdueCommitments(TestAuthentication):
    """Test GET /api/integrators returns has_overdue_commitments flag"""
    
    def test_no_overdue_commitments_flag_false(self, auth_headers):
        """Integrator without bitácora entries has has_overdue_commitments=False"""
        # Create integrator
        payload = {
            "name": "TEST_NoOverdue79",
            "integrator_type": "Integrador",
            "app_name": "NoOverdueApp",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso"
        }
        create_resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert create_resp.status_code == 200
        integrator_id = create_resp.json()["integrator_id"]
        
        # GET all integrators
        list_resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert list_resp.status_code == 200
        
        integrators = list_resp.json()
        test_intg = next((i for i in integrators if i["integrator_id"] == integrator_id), None)
        assert test_intg is not None, "Test integrator not found"
        
        assert "has_overdue_commitments" in test_intg, "has_overdue_commitments field missing"
        assert test_intg["has_overdue_commitments"] == False, f"Expected False, got {test_intg['has_overdue_commitments']}"
        
        print(f"PASSED: Integrator without bitácora has has_overdue_commitments=False")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)
    
    def test_overdue_commitment_flag_true(self, auth_headers):
        """Integrator with overdue commitment has has_overdue_commitments=True"""
        # Create integrator
        payload = {
            "name": "TEST_WithOverdue79",
            "integrator_type": "Integrador",
            "app_name": "OverdueApp",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso"
        }
        create_resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert create_resp.status_code == 200
        integrator_id = create_resp.json()["integrator_id"]
        
        # Add bitácora entry with overdue commitment (deadline in the past)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        bitacora_payload = {
            "description": "Test gestión con compromiso vencido",
            "date": yesterday,
            "commitment": "Enviar documentación",
            "commitment_deadline": yesterday,  # Already overdue
            "commitment_completed": False
        }
        bitacora_resp = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=bitacora_payload,
            headers=auth_headers
        )
        assert bitacora_resp.status_code == 200, f"Bitácora creation failed: {bitacora_resp.text}"
        
        # GET all integrators and check flag
        list_resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        assert list_resp.status_code == 200
        
        integrators = list_resp.json()
        test_intg = next((i for i in integrators if i["integrator_id"] == integrator_id), None)
        assert test_intg is not None
        
        assert test_intg["has_overdue_commitments"] == True, \
            f"Expected True for overdue commitment, got {test_intg['has_overdue_commitments']}"
        
        print(f"PASSED: Integrator with overdue commitment has has_overdue_commitments=True")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)


class TestBitacoraEndpoints(TestAuthentication):
    """Test all bitácora CRUD endpoints"""
    
    @pytest.fixture
    def test_integrator_with_contacts(self, auth_headers):
        """Create test integrator with contacts for bitácora tests"""
        payload = {
            "name": "TEST_Bitacora79",
            "integrator_type": "Integrador",
            "app_name": "BitacoraApp",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso",
            "contacts": [
                {"name": "Contact One", "email": "contact1@test.com", "phone": "+58 412-1111111"},
                {"name": "Contact Two", "email": "contact2@test.com", "phone": "+58 412-2222222"}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        integrator = resp.json()
        yield integrator
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator['integrator_id']}", headers=auth_headers)
    
    def test_create_bitacora_entry(self, auth_headers, test_integrator_with_contacts):
        """POST /api/integrators/{id}/bitacora creates entry"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        contact_id = test_integrator_with_contacts["contacts"][0]["contact_id"]
        
        today = date.today().isoformat()
        future_date = (date.today() + timedelta(days=7)).isoformat()
        
        payload = {
            "description": "Llamada de seguimiento inicial",
            "contact_id": contact_id,
            "contact_name": "Contact One",
            "date": today,
            "commitment": "Enviar credenciales de prueba",
            "commitment_deadline": future_date
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Create bitácora failed: {response.text}"
        
        data = response.json()
        assert "entry_id" in data, "entry_id missing"
        assert data["description"] == payload["description"]
        assert data["contact_id"] == contact_id
        assert data["commitment"] == payload["commitment"]
        assert data["commitment_deadline"] == future_date
        assert data["commitment_completed"] == False
        
        print(f"PASSED: Bitácora entry created. Entry ID: {data['entry_id']}")
        return data["entry_id"]
    
    def test_create_bitacora_auto_updates_last_contact_date(self, auth_headers, test_integrator_with_contacts):
        """Creating bitácora entry auto-updates integrator's last_contact_date"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        
        # Check current last_contact_date
        before = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers).json()
        initial_date = before.get("last_contact_date")
        
        # Create bitácora entry
        today = date.today().isoformat()
        payload = {
            "description": "Gestión para verificar actualización de fecha",
            "date": today,
            "commitment": None,
            "commitment_deadline": None
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Verify last_contact_date was updated
        after = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers).json()
        assert after["last_contact_date"] == today, \
            f"Expected last_contact_date={today}, got {after['last_contact_date']}"
        
        print(f"PASSED: last_contact_date auto-updated from {initial_date} to {today}")
    
    def test_get_bitacora_chronological(self, auth_headers, test_integrator_with_contacts):
        """GET /api/integrators/{id}/bitacora returns entries in chronological order"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        
        # Create multiple entries with different dates
        dates = [
            (date.today() - timedelta(days=5)).isoformat(),
            (date.today() - timedelta(days=2)).isoformat(),
            date.today().isoformat()
        ]
        
        for i, d in enumerate(dates):
            payload = {
                "description": f"Entry {i+1}",
                "date": d
            }
            resp = requests.post(
                f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
                json=payload,
                headers=auth_headers
            )
            assert resp.status_code == 200
        
        # GET bitácora
        list_resp = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}/bitacora", headers=auth_headers)
        assert list_resp.status_code == 200
        
        entries = list_resp.json()
        assert len(entries) >= 3, f"Expected at least 3 entries, got {len(entries)}"
        
        # Verify descending order (most recent first)
        for i in range(len(entries) - 1):
            assert entries[i]["date"] >= entries[i+1]["date"], \
                f"Entries not in descending order: {entries[i]['date']} < {entries[i+1]['date']}"
        
        print(f"PASSED: Bitácora returns {len(entries)} entries in chronological (descending) order")
    
    def test_patch_bitacora_mark_completed(self, auth_headers, test_integrator_with_contacts):
        """PATCH /api/integrators/{id}/bitacora/{entry_id} marks commitment as completed"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        
        # Create entry with commitment
        payload = {
            "description": "Gestión con compromiso",
            "date": date.today().isoformat(),
            "commitment": "Tarea pendiente",
            "commitment_deadline": (date.today() + timedelta(days=3)).isoformat(),
            "commitment_completed": False
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert create_resp.status_code == 200
        entry_id = create_resp.json()["entry_id"]
        
        # Mark as completed
        patch_resp = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{entry_id}",
            json={"commitment_completed": True},
            headers=auth_headers
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        updated = patch_resp.json()
        assert updated["commitment_completed"] == True, f"Expected True, got {updated['commitment_completed']}"
        
        print(f"PASSED: Bitácora entry marked as completed")
    
    def test_delete_bitacora_entry(self, auth_headers, test_integrator_with_contacts):
        """DELETE /api/integrators/{id}/bitacora/{entry_id} removes entry"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        
        # Create entry
        payload = {
            "description": "Entry to delete",
            "date": date.today().isoformat()
        }
        create_resp = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert create_resp.status_code == 200
        entry_id = create_resp.json()["entry_id"]
        
        # Delete entry
        delete_resp = requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{entry_id}",
            headers=auth_headers
        )
        assert delete_resp.status_code == 200, f"DELETE failed: {delete_resp.text}"
        
        # Verify entry is gone
        list_resp = requests.get(f"{BASE_URL}/api/integrators/{integrator_id}/bitacora", headers=auth_headers)
        entries = list_resp.json()
        entry_ids = [e["entry_id"] for e in entries]
        assert entry_id not in entry_ids, "Deleted entry still exists"
        
        print(f"PASSED: Bitácora entry deleted successfully")
    
    def test_delete_nonexistent_entry_returns_404(self, auth_headers, test_integrator_with_contacts):
        """DELETE non-existent bitácora entry returns 404"""
        integrator_id = test_integrator_with_contacts["integrator_id"]
        fake_entry_id = "bit_nonexistent123"
        
        response = requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{fake_entry_id}",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print(f"PASSED: DELETE non-existent entry returns 404")
    
    def test_create_bitacora_nonexistent_integrator_returns_404(self, auth_headers):
        """POST bitácora for non-existent integrator returns 404"""
        fake_integrator_id = "int_nonexistent123"
        
        payload = {
            "description": "Test entry",
            "date": date.today().isoformat()
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{fake_integrator_id}/bitacora",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print(f"PASSED: POST bitácora for non-existent integrator returns 404")


class TestCompletedCommitmentNotOverdue(TestAuthentication):
    """Test that completed commitments don't trigger has_overdue_commitments"""
    
    def test_completed_overdue_not_flagged(self, auth_headers):
        """Completed commitment with past deadline doesn't flag as overdue"""
        # Create integrator
        payload = {
            "name": "TEST_CompletedNotOverdue79",
            "integrator_type": "Integrador",
            "app_name": "CompletedApp",
            "integration_modality": "REST",
            "integrator_status": "En proceso"
        }
        create_resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert create_resp.status_code == 200
        integrator_id = create_resp.json()["integrator_id"]
        
        # Create bitácora with past deadline BUT marked as completed
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        bitacora_payload = {
            "description": "Compromiso cumplido",
            "date": yesterday,
            "commitment": "Tarea completada",
            "commitment_deadline": yesterday,
            "commitment_completed": True  # COMPLETED
        }
        requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=bitacora_payload,
            headers=auth_headers
        )
        
        # Check flag is False (because commitment is completed)
        list_resp = requests.get(f"{BASE_URL}/api/integrators", headers=auth_headers)
        integrators = list_resp.json()
        test_intg = next((i for i in integrators if i["integrator_id"] == integrator_id), None)
        
        assert test_intg["has_overdue_commitments"] == False, \
            "Completed commitment should not flag as overdue"
        
        print(f"PASSED: Completed commitment with past deadline not flagged as overdue")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)


class TestBitacoraEntryStructure(TestAuthentication):
    """Test BitacoraEntry model has all required fields"""
    
    def test_bitacora_entry_has_all_fields(self, auth_headers):
        """Verify all fields in BitacoraEntry response"""
        # Create integrator
        payload = {
            "name": "TEST_EntryStructure79",
            "integrator_type": "Integrador",
            "app_name": "StructureApp",
            "integration_modality": "PG Universal",
            "integrator_status": "En proceso",
            "contacts": [{"name": "Test Contact", "email": "tc@test.com", "phone": "+58 412-0000000"}]
        }
        create_resp = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=auth_headers)
        assert create_resp.status_code == 200
        integrator = create_resp.json()
        integrator_id = integrator["integrator_id"]
        contact_id = integrator["contacts"][0]["contact_id"]
        
        # Create full bitácora entry
        today = date.today().isoformat()
        deadline = (date.today() + timedelta(days=5)).isoformat()
        
        bitacora_payload = {
            "description": "Descripción completa de la gestión",
            "contact_id": contact_id,
            "contact_name": "Test Contact",
            "date": today,
            "commitment": "Compromiso de prueba",
            "commitment_deadline": deadline
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            json=bitacora_payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        entry = response.json()
        
        # Verify all required fields
        required_fields = [
            "entry_id", "integrator_id", "description", "contact_id", 
            "contact_name", "date", "commitment", "commitment_deadline", 
            "commitment_completed", "created_at"
        ]
        
        for field in required_fields:
            assert field in entry, f"Missing field: {field}"
        
        # Verify field values
        assert entry["entry_id"].startswith("bit_"), f"entry_id format wrong: {entry['entry_id']}"
        assert entry["integrator_id"] == integrator_id
        assert entry["description"] == bitacora_payload["description"]
        assert entry["contact_id"] == contact_id
        assert entry["contact_name"] == "Test Contact"
        assert entry["date"] == today
        assert entry["commitment"] == bitacora_payload["commitment"]
        assert entry["commitment_deadline"] == deadline
        assert entry["commitment_completed"] == False
        assert entry["created_at"] is not None
        
        print(f"PASSED: BitacoraEntry has all required fields with correct values")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
