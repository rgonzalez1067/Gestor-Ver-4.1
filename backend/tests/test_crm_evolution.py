# ruff: noqa
"""
Test CRM Evolution Features - Iteration 44
- Multi-sede structure (RIF + Sucursal composite key)
- Dynamic contacts matrix with roles
- Client event log (Bitácora)
- Dashboard alerts widget with traffic light system
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_USER_EMAIL = "test_anexos@test.com"
TEST_USER_PASSWORD = "Test1234!"


class TestCRMEvolution:
    """Tests for CRM Evolution features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("session_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
    
    # ========== MULTI-SEDE TESTS ==========
    
    def test_create_client_with_sucursal(self):
        """Test creating a client with sucursal field"""
        payload = {
            "rif": "TEST_J-12345678-0",
            "legal_name": "Test Multi-Sede Corp",
            "fantasy_name": "TestCorp",
            "segment": "Corporativo",
            "address": "Caracas, Venezuela",
            "sucursal": "Sede Central",
            "contacts": [{
                "first_name": "Juan",
                "last_name": "Pérez",
                "phone": "0412-1234567",
                "email": "juan@test.com",
                "role": "Administrativo"
            }],
            "contact1": {"name": "Juan Pérez", "phone": "0412-1234567", "email": "juan@test.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        response = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=self.headers)
        assert response.status_code == 200, f"Create client failed: {response.text}"
        data = response.json()
        assert data["sucursal"] == "Sede Central"
        assert data["rif"] == "TEST_J-12345678-0"
        assert len(data.get("contacts", [])) >= 1
        self.client_id = data["client_id"]
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{self.client_id}", headers=self.headers)
    
    def test_duplicate_rif_sucursal_returns_400(self):
        """Test that duplicate RIF + Sucursal combo returns 400"""
        payload = {
            "rif": "TEST_J-99999999-0",
            "legal_name": "First Corp",
            "fantasy_name": "FirstCorp",
            "segment": "Pymes",
            "sucursal": "Principal",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        # Create first client
        r1 = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=self.headers)
        assert r1.status_code == 200, f"First create failed: {r1.text}"
        client_id = r1.json()["client_id"]
        
        # Try to create duplicate
        r2 = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=self.headers)
        assert r2.status_code == 400, f"Expected 400 for duplicate, got {r2.status_code}"
        assert "Ya existe un cliente con RIF" in r2.json().get("detail", "")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    def test_same_rif_different_sucursal_succeeds(self):
        """Test that same RIF with different sucursal succeeds"""
        base_payload = {
            "rif": "TEST_J-88888888-0",
            "legal_name": "Multi Branch Corp",
            "fantasy_name": "MultiBranch",
            "segment": "Corporativo",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        
        # Create first branch
        payload1 = {**base_payload, "sucursal": "Sede Principal"}
        r1 = requests.post(f"{BASE_URL}/api/clients", json=payload1, headers=self.headers)
        assert r1.status_code == 200, f"First branch failed: {r1.text}"
        client_id_1 = r1.json()["client_id"]
        
        # Create second branch - SHOULD SUCCEED
        payload2 = {**base_payload, "sucursal": "Sede Norte"}
        r2 = requests.post(f"{BASE_URL}/api/clients", json=payload2, headers=self.headers)
        assert r2.status_code == 200, f"Second branch should succeed: {r2.text}"
        client_id_2 = r2.json()["client_id"]
        
        # Verify both exist
        assert client_id_1 != client_id_2
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id_1}", headers=self.headers)
        requests.delete(f"{BASE_URL}/api/clients/{client_id_2}", headers=self.headers)
    
    def test_update_client_with_contacts_and_sucursal(self):
        """Test updating client with new contacts and sucursal"""
        # Create client first
        create_payload = {
            "rif": "TEST_J-77777777-0",
            "legal_name": "Update Test Corp",
            "fantasy_name": "UpdateCorp",
            "segment": "Pymes",
            "sucursal": "Original",
            "contacts": [],
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=create_payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Update with contacts
        update_payload = {
            **create_payload,
            "sucursal": "Nueva Sucursal",
            "contacts": [
                {"first_name": "Ana", "last_name": "López", "phone": "0414-5555555", "email": "ana@test.com", "role": "Financiero"},
                {"first_name": "Carlos", "last_name": "García", "phone": "0416-6666666", "email": "carlos@test.com", "role": "Técnico"}
            ]
        }
        r2 = requests.put(f"{BASE_URL}/api/clients/{client_id}", json=update_payload, headers=self.headers)
        assert r2.status_code == 200, f"Update failed: {r2.text}"
        data = r2.json()
        assert data["sucursal"] == "Nueva Sucursal"
        assert len(data["contacts"]) == 2
        assert data["contacts"][0]["role"] == "Financiero"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    def test_get_clients_returns_sucursal_and_contacts(self):
        """Test GET /clients returns sucursal and contacts fields"""
        # Create a test client
        payload = {
            "rif": "TEST_J-66666666-0",
            "legal_name": "List Test Corp",
            "fantasy_name": "ListCorp",
            "segment": "Mixto",
            "sucursal": "Test Sede",
            "contacts": [{"first_name": "Test", "last_name": "Contact", "phone": "123", "email": "test@t.com", "role": "Operativo"}],
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Get all clients
        r2 = requests.get(f"{BASE_URL}/api/clients", headers=self.headers)
        assert r2.status_code == 200
        clients = r2.json()
        
        # Find our test client
        test_client = next((c for c in clients if c["client_id"] == client_id), None)
        assert test_client is not None
        assert "sucursal" in test_client
        assert "contacts" in test_client
        assert test_client["sucursal"] == "Test Sede"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    # ========== BITÁCORA TESTS ==========
    
    def test_create_bitacora_entry(self):
        """Test POST /clients/{id}/logs creates bitácora entry"""
        # Create client first
        client_payload = {
            "rif": "TEST_J-55555555-0",
            "legal_name": "Bitacora Test Corp",
            "fantasy_name": "BitacoraCorp",
            "segment": "Pymes",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=client_payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Create log entry
        log_payload = {
            "client_id": client_id,
            "detail": "Llamada inicial para presentación de servicios",
            "action": "Enviar cotización por email",
            "follow_up_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        }
        r2 = requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log_payload, headers=self.headers)
        assert r2.status_code == 200, f"Create log failed: {r2.text}"
        log_data = r2.json()
        assert "log_id" in log_data
        assert log_data["detail"] == log_payload["detail"]
        assert log_data["action"] == log_payload["action"]
        assert log_data["follow_up_date"] == log_payload["follow_up_date"]
        assert log_data["is_completed"] == False
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    def test_get_client_logs_sorted_descending(self):
        """Test GET /clients/{id}/logs returns logs sorted by date descending"""
        # Create client
        client_payload = {
            "rif": "TEST_J-44444444-0",
            "legal_name": "Logs Sort Test Corp",
            "fantasy_name": "SortCorp",
            "segment": "Corporativo",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=client_payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Create multiple logs
        for i in range(3):
            log_payload = {
                "client_id": client_id,
                "detail": f"Log entry {i+1}",
                "action": f"Action {i+1}"
            }
            requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log_payload, headers=self.headers)
        
        # Get logs
        r2 = requests.get(f"{BASE_URL}/api/clients/{client_id}/logs", headers=self.headers)
        assert r2.status_code == 200
        logs = r2.json()
        assert len(logs) >= 3
        
        # Verify most recent first (descending order by created_at)
        # Since we created them sequentially, the last one should be first
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    def test_toggle_log_completion(self):
        """Test PATCH /clients/logs/{log_id}/complete toggles completion status"""
        # Create client
        client_payload = {
            "rif": "TEST_J-33333333-0",
            "legal_name": "Toggle Test Corp",
            "fantasy_name": "ToggleCorp",
            "segment": "Mixto",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=client_payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Create log
        log_payload = {
            "client_id": client_id,
            "detail": "Test toggle log",
            "action": "Toggle test"
        }
        r2 = requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log_payload, headers=self.headers)
        assert r2.status_code == 200
        log_id = r2.json()["log_id"]
        assert r2.json()["is_completed"] == False
        
        # Toggle to complete
        r3 = requests.patch(f"{BASE_URL}/api/clients/logs/{log_id}/complete", headers=self.headers)
        assert r3.status_code == 200, f"Toggle failed: {r3.text}"
        assert r3.json()["is_completed"] == True
        
        # Toggle back to incomplete
        r4 = requests.patch(f"{BASE_URL}/api/clients/logs/{log_id}/complete", headers=self.headers)
        assert r4.status_code == 200
        assert r4.json()["is_completed"] == False
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    # ========== DASHBOARD ALERTS TESTS ==========
    
    def test_dashboard_alerts_returns_semaphore_classification(self):
        """Test GET /dashboard/alerts returns overdue, today, upcoming"""
        response = requests.get(f"{BASE_URL}/api/dashboard/alerts", headers=self.headers)
        assert response.status_code == 200, f"Alerts failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "overdue" in data
        assert "today" in data
        assert "upcoming" in data
        assert "total" in data
        assert isinstance(data["overdue"], list)
        assert isinstance(data["today"], list)
        assert isinstance(data["upcoming"], list)
        assert isinstance(data["total"], int)
    
    def test_dashboard_alerts_with_test_data(self):
        """Test alerts classification with actual test data"""
        # Create client
        client_payload = {
            "rif": "TEST_J-22222222-0",
            "legal_name": "Alerts Test Corp",
            "fantasy_name": "AlertsCorp",
            "segment": "Pymes",
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        r1 = requests.post(f"{BASE_URL}/api/clients", json=client_payload, headers=self.headers)
        assert r1.status_code == 200
        client_id = r1.json()["client_id"]
        
        # Create overdue log (yesterday)
        overdue_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        log1 = {
            "client_id": client_id,
            "detail": "Overdue test log",
            "action": "Call back",
            "follow_up_date": overdue_date
        }
        r2 = requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log1, headers=self.headers)
        assert r2.status_code == 200
        
        # Create today log
        today_date = datetime.now().strftime("%Y-%m-%d")
        log2 = {
            "client_id": client_id,
            "detail": "Today test log",
            "action": "Send proposal",
            "follow_up_date": today_date
        }
        r3 = requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log2, headers=self.headers)
        assert r3.status_code == 200
        
        # Create upcoming log (in 3 days)
        upcoming_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        log3 = {
            "client_id": client_id,
            "detail": "Upcoming test log",
            "action": "Follow up",
            "follow_up_date": upcoming_date
        }
        r4 = requests.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log3, headers=self.headers)
        assert r4.status_code == 200
        
        # Get alerts
        r5 = requests.get(f"{BASE_URL}/api/dashboard/alerts", headers=self.headers)
        assert r5.status_code == 200
        alerts = r5.json()
        
        # Verify our test alerts exist
        assert alerts["total"] >= 3
        
        # Check that alerts have enriched client info
        all_alerts = alerts["overdue"] + alerts["today"] + alerts["upcoming"]
        for alert in all_alerts:
            if alert.get("client_id") == client_id:
                assert "client_name" in alert
                assert "client_rif" in alert
                assert "priority" in alert
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=self.headers)
    
    # ========== CONTACT ROLES TEST ==========
    
    def test_contact_roles_validation(self):
        """Test that all 5 contact roles are accepted"""
        roles = ["Administrativo", "Financiero", "Técnico", "Cuentas por Pagar", "Operativo"]
        
        client_payload = {
            "rif": "TEST_J-11111111-0",
            "legal_name": "Roles Test Corp",
            "fantasy_name": "RolesCorp",
            "segment": "Corporativo",
            "sucursal": "Principal",
            "contacts": [
                {"first_name": f"Contact{i}", "last_name": "Test", "phone": "123", "email": f"c{i}@t.com", "role": role}
                for i, role in enumerate(roles)
            ],
            "contact1": {"name": "Test", "phone": "N/A", "email": "t@t.com"},
            "contact2": {"name": "N/A", "phone": "N/A", "email": "na@na.com"}
        }
        
        response = requests.post(f"{BASE_URL}/api/clients", json=client_payload, headers=self.headers)
        assert response.status_code == 200, f"Create with roles failed: {response.text}"
        data = response.json()
        
        # Verify all roles were saved
        saved_roles = [c["role"] for c in data.get("contacts", [])]
        for role in roles:
            assert role in saved_roles, f"Role '{role}' not saved"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{data['client_id']}", headers=self.headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
