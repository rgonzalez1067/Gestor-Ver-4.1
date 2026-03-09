"""
Test iteration 82 - Timeline Viewer Feature
Tests the transformation of the FileText button to show 'Reporte Histórico' with bitácora entries
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTimelineViewer:
    """Test bitacora endpoint which powers the Timeline viewer modal"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get('session_token') or data.get('token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
    
    def test_get_integrators_list(self):
        """Test GET /api/integrators returns list of integrators"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert response.status_code == 200, f"Failed to get integrators: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        if len(data) > 0:
            # Check first integrator has required fields
            intg = data[0]
            assert 'integrator_id' in intg
            assert 'name' in intg
            print(f"Found {len(data)} integrators, first: {intg['name']}")
    
    def test_bitacora_sorted_by_date_desc(self):
        """Test GET /api/integrators/{id}/bitacora returns entries sorted by date descending (newest first)"""
        # Get first integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert response.status_code == 200
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available for testing")
        
        integrator_id = integrators[0]['integrator_id']
        
        # Get bitacora entries
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get bitacora: {response.text}"
        entries = response.json()
        
        if len(entries) >= 2:
            # Verify entries are sorted by date descending
            dates = [e.get('date', '') for e in entries]
            assert dates == sorted(dates, reverse=True), f"Entries not sorted by date desc: {dates}"
            print(f"Verified {len(entries)} entries sorted desc: {dates}")
        else:
            print(f"Only {len(entries)} entries, skipping sort verification")
    
    def test_bitacora_entry_has_required_fields(self):
        """Test bitacora entries have required fields for timeline display"""
        # Get first integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        
        # Get bitacora
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers
        )
        assert response.status_code == 200
        entries = response.json()
        
        if len(entries) == 0:
            pytest.skip("No bitacora entries available")
        
        # Check required fields for timeline display
        entry = entries[0]
        required_fields = ['entry_id', 'integrator_id', 'description', 'date']
        for field in required_fields:
            assert field in entry, f"Missing required field: {field}"
        
        # Check optional but displayed fields
        optional_displayed = ['contact_name', 'commitment', 'commitment_deadline', 'commitment_completed']
        for field in optional_displayed:
            assert field in entry, f"Missing timeline display field: {field}"
        
        print(f"Entry has all required fields: {list(entry.keys())}")
    
    def test_create_bitacora_entry_for_timeline(self):
        """Test creating a bitacora entry that will appear in timeline"""
        # Get or create test integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            # Create test integrator
            create_resp = requests.post(f"{BASE_URL}/api/integrators", headers=self.headers, json={
                "name": "TEST_Timeline_Integrator",
                "integrator_type": "Integrador",
                "app_name": "Test App",
                "integration_modality": "REST"
            })
            assert create_resp.status_code == 200, f"Failed to create integrator: {create_resp.text}"
            integrator_id = create_resp.json()['integrator_id']
        else:
            integrator_id = integrators[0]['integrator_id']
        
        # Create bitacora entry
        today = datetime.now().strftime("%Y-%m-%d")
        deadline = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        entry_data = {
            "description": "TEST_Timeline entry - verificación de integración",
            "contact_name": "Test Contact",
            "date": today,
            "commitment": "TEST_Verificar respuesta del sistema",
            "commitment_deadline": deadline
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers,
            json=entry_data
        )
        assert response.status_code == 200, f"Failed to create bitacora entry: {response.text}"
        
        created = response.json()
        assert created['description'] == entry_data['description']
        assert created['contact_name'] == entry_data['contact_name']
        assert created['date'] == entry_data['date']
        assert created['commitment'] == entry_data['commitment']
        assert created['commitment_deadline'] == entry_data['commitment_deadline']
        assert created['commitment_completed'] == False
        
        print(f"Created bitacora entry: {created['entry_id']}")
        
        # Cleanup - delete the entry
        requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{created['entry_id']}",
            headers=self.headers
        )
    
    def test_overdue_commitment_detection(self):
        """Test that overdue commitments can be detected (deadline passed, not completed)"""
        # Get first integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        
        # Create an overdue entry
        past_deadline = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        past_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
        
        entry_data = {
            "description": "TEST_Overdue entry for timeline testing",
            "contact_name": "Test Contact",
            "date": past_date,
            "commitment": "TEST_This should be marked as VENCIDO",
            "commitment_deadline": past_deadline,
            "commitment_completed": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers,
            json=entry_data
        )
        assert response.status_code == 200
        created = response.json()
        
        # Verify the entry has passed deadline
        today = datetime.now().strftime("%Y-%m-%d")
        assert created['commitment_deadline'] < today, "Deadline should be in the past"
        assert created['commitment_completed'] == False, "Should not be completed"
        
        print(f"Created overdue entry with deadline {created['commitment_deadline']}")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{created['entry_id']}",
            headers=self.headers
        )
    
    def test_mark_commitment_as_completed(self):
        """Test marking a commitment as completed (should show CUMPLIDO in timeline)"""
        # Get first integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        
        # Create entry
        today = datetime.now().strftime("%Y-%m-%d")
        entry_data = {
            "description": "TEST_Entry to mark as completed",
            "date": today,
            "commitment": "TEST_This will be marked CUMPLIDO",
            "commitment_deadline": today,
            "commitment_completed": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers,
            json=entry_data
        )
        assert response.status_code == 200
        created = response.json()
        
        # Mark as completed
        response = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{created['entry_id']}",
            headers=self.headers,
            json={"commitment_completed": True}
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated['commitment_completed'] == True
        
        print(f"Marked entry {created['entry_id']} as completed")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{created['entry_id']}",
            headers=self.headers
        )
    
    def test_evolution_endpoint_still_exists(self):
        """Test that evolution endpoint still exists for backwards compatibility (but modal removed)"""
        # Get first integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        
        # Evolution endpoint should still work
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/evolution",
            headers=self.headers
        )
        # May return 200 with data or empty array - both are valid
        assert response.status_code == 200, f"Evolution endpoint should still exist: {response.text}"
        print(f"Evolution endpoint returns: {len(response.json())} entries (backwards compatible)")
    
    def test_has_overdue_commitments_flag(self):
        """Test that integrator has_overdue_commitments flag is set correctly"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        assert response.status_code == 200
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        # Check that has_overdue_commitments field exists
        intg = integrators[0]
        assert 'has_overdue_commitments' in intg, "Missing has_overdue_commitments flag"
        print(f"Integrator {intg['name']} has_overdue_commitments: {intg['has_overdue_commitments']}")
    
    def test_bitacora_search_fields(self):
        """Test that bitacora entries have fields searchable in timeline (description, contact_name, commitment)"""
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers
        )
        assert response.status_code == 200
        entries = response.json()
        
        if len(entries) == 0:
            pytest.skip("No bitacora entries")
        
        # All entries should have searchable fields
        for entry in entries:
            assert 'description' in entry
            assert 'contact_name' in entry  # May be null but field should exist
            assert 'commitment' in entry    # May be null but field should exist
        
        print(f"Verified {len(entries)} entries have searchable fields")


class TestBookOpenButtonUnchanged:
    """Test that BookOpen button still opens bitacora creation modal (unchanged)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@test.com",
            "password": "Test1234!"
        })
        assert response.status_code == 200
        data = response.json()
        self.token = data.get('session_token') or data.get('token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
    
    def test_bitacora_crud_operations(self):
        """Test full CRUD on bitacora (used by BookOpen modal)"""
        # Get integrator
        response = requests.get(f"{BASE_URL}/api/integrators", headers=self.headers)
        integrators = response.json()
        
        if len(integrators) == 0:
            pytest.skip("No integrators available")
        
        integrator_id = integrators[0]['integrator_id']
        today = datetime.now().strftime("%Y-%m-%d")
        
        # CREATE
        create_data = {
            "description": "TEST_CRUD bitacora entry",
            "contact_name": "Test Person",
            "date": today,
            "commitment": "TEST_Commitment",
            "commitment_deadline": today
        }
        response = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers,
            json=create_data
        )
        assert response.status_code == 200
        created = response.json()
        entry_id = created['entry_id']
        print(f"Created: {entry_id}")
        
        # READ
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers
        )
        assert response.status_code == 200
        entries = response.json()
        found = any(e['entry_id'] == entry_id for e in entries)
        assert found, "Created entry should be in list"
        print(f"Read: found entry in list of {len(entries)}")
        
        # UPDATE
        response = requests.patch(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{entry_id}",
            headers=self.headers,
            json={"commitment_completed": True}
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated['commitment_completed'] == True
        print(f"Updated: commitment_completed = True")
        
        # DELETE
        response = requests.delete(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora/{entry_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        print(f"Deleted: {entry_id}")
        
        # Verify deletion
        response = requests.get(
            f"{BASE_URL}/api/integrators/{integrator_id}/bitacora",
            headers=self.headers
        )
        entries = response.json()
        found = any(e['entry_id'] == entry_id for e in entries)
        assert not found, "Deleted entry should not be in list"
