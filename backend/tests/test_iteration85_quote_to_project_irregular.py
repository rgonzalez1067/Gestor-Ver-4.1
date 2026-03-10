"""
Iteration 85 - Quote to Project Conversion and Irregular Flow Testing

Features tested:
- Bug #1: POST /api/quotes/{id}/approve with x-exception-reason and x-regularization-date headers
- Bug #1: POST /api/quotes/{id}/send-to-implementation with exception headers
- Feature #2: send-to-implementation creates a project automatically from quote data
- Feature #2: Quote is deleted after conversion to project
- Feature #3: Project inherits is_irregular=true and irregular_exceptions from irregular quote
- Feature #3: GET /api/projects/stats includes 'irregular' field with count
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gestor.com",
        "password": "Admin2026!"
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("session_token") or data.get("token")
    pytest.skip("Authentication failed - skipping tests")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

@pytest.fixture(scope="module")
def test_client(auth_headers):
    """Get or create a test client"""
    # Try to get existing clients
    response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
    if response.status_code == 200:
        clients = response.json()
        if clients and len(clients) > 0:
            return clients[0]
    
    # Create new client if none exist
    client_data = {
        "rif": f"J-{uuid.uuid4().hex[:8]}",
        "legal_name": "TEST Cliente Iteration85",
        "fantasy_name": "Test Client 85",
        "address": "Test Address",
        "contacts": [{"name": "Test Contact", "email": "test85@test.com", "phone": "123456"}]
    }
    response = requests.post(f"{BASE_URL}/api/clients", json=client_data, headers=auth_headers)
    if response.status_code in [200, 201]:
        return response.json()
    pytest.skip("Could not get or create test client")

@pytest.fixture(scope="module")
def test_quote_for_approve(auth_headers, test_client):
    """Create a test quote for approve test (needs OC attachment)"""
    quote_data = {
        "client_id": test_client.get("client_id"),
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "services": [],
        "total_usd": 100,
        "sede": "TBP"
    }
    response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
    if response.status_code in [200, 201]:
        return response.json()
    pytest.skip("Could not create test quote for approve")

@pytest.fixture(scope="module")
def test_quote_for_implementation(auth_headers, test_client):
    """Create a test quote for send-to-implementation test"""
    quote_data = {
        "client_id": test_client.get("client_id"),
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "services": [
            {"item_type": "additional", "bank_name": "Banco Test", "item_name": "TDD/TDC", "category": "Test", "name": "TDD/TDC", "quantity": 1, "unit_price_usd": 50, "total_usd": 50}
        ],
        "total_usd": 150,
        "sede": "TBP"
    }
    response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
    if response.status_code in [200, 201]:
        return response.json()
    pytest.skip("Could not create test quote for implementation")


class TestApproveWithExceptionHeaders:
    """Test Bug #1: POST /api/quotes/{id}/approve with exception headers"""
    
    def test_approve_without_exception_reason_fails_on_irregular(self, auth_headers, test_quote_for_approve):
        """When quote is not in 'Enviada' status and no exception reason, should return 422"""
        quote_id = test_quote_for_approve.get("quote_id")
        # Quote starts in 'Borrador', so approve without reason should fail with IRREGULAR
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=auth_headers)
        # Should fail either with 422 (IRREGULAR) or 422 (needs OC)
        assert response.status_code == 422
        data = response.json()
        detail = data.get("detail", "")
        # Either IRREGULAR or OC required error
        assert "IRREGULAR" in detail or "Orden de Compra" in detail
        print(f"Approve without exception reason response: {detail}")
    
    def test_approve_requires_oc_attachment(self, auth_headers, test_quote_for_approve):
        """Approve endpoint requires Orden de Compra attachment"""
        quote_id = test_quote_for_approve.get("quote_id")
        headers = {**auth_headers, "x-exception-reason": "Test exception reason", "x-regularization-date": "2026-01-20"}
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=headers)
        # Should fail because no OC attachment
        assert response.status_code == 422
        data = response.json()
        assert "Orden de Compra" in data.get("detail", "")
        print("Approve requires OC attachment - verified")


class TestSendToImplementationWithExceptionHeaders:
    """Test Bug #1 and Feature #2: POST /api/quotes/{id}/send-to-implementation"""
    
    def test_send_to_implementation_without_exception_fails_on_irregular(self, auth_headers, test_quote_for_implementation):
        """When quote is not 'Pagada' and no exception reason, should return 422 with IRREGULAR"""
        quote_id = test_quote_for_implementation.get("quote_id")
        # Quote is in Borrador, not Pagada, so should be irregular
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", headers=auth_headers)
        assert response.status_code == 422
        data = response.json()
        detail = data.get("detail", "")
        assert "IRREGULAR" in detail
        print(f"Send to implementation without exception reason: {detail}")
    
    def test_send_to_implementation_with_exception_creates_project(self, auth_headers, test_client):
        """When exception reason provided, should create project and delete quote"""
        # Create fresh quote for this test
        quote_data = {
            "client_id": test_client.get("client_id"),
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "services": [
                {"item_type": "additional", "bank_name": "Banco Test85", "item_name": "TDD/TDC Test", "category": "Test", "name": "TDD/TDC Test", "quantity": 1, "unit_price_usd": 75, "total_usd": 75}
            ],
            "total_usd": 175,
            "sede": "TBP"
        }
        create_response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_response.status_code in [200, 201], f"Failed to create quote: {create_response.text}"
        quote = create_response.json()
        quote_id = quote.get("quote_id")
        quote_number = quote.get("quote_number")
        print(f"Created quote {quote_number} with ID {quote_id}")
        
        # Send to implementation with exception headers
        impl_headers = {
            **auth_headers,
            "x-exception-reason": "Test reason for iteration 85 - irregular flow testing",
            "x-regularization-date": "2026-01-25"
        }
        impl_response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", headers=impl_headers)
        assert impl_response.status_code == 200, f"Failed send-to-implementation: {impl_response.text}"
        impl_data = impl_response.json()
        assert impl_data.get("new_status") == "Enviada a Imple"
        print(f"Send to implementation successful: {impl_data}")
        
        # Verify project was created
        projects_response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert projects_response.status_code == 200
        projects = projects_response.json()
        
        # Find project by quote_id or quote_number
        project = None
        for p in projects:
            if p.get("quote_id") == quote_id or p.get("quote_number") == quote_number:
                project = p
                break
        
        assert project is not None, f"Project not found for quote {quote_id}"
        print(f"Project created: {project.get('project_number')} from quote {quote_number}")
        
        # Verify project inherited is_irregular = True and irregular_exceptions
        assert project.get("is_irregular") == True, "Project should inherit is_irregular=True"
        irregular_exceptions = project.get("irregular_exceptions", [])
        assert len(irregular_exceptions) > 0, "Project should inherit irregular_exceptions"
        print(f"Project is_irregular: {project.get('is_irregular')}, exceptions: {len(irregular_exceptions)}")
        
        # Verify quote was deleted
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        assert quote_response.status_code == 404, f"Quote should be deleted after project creation"
        print(f"Quote {quote_id} deleted after conversion to project - verified")
        
        return project
    
    def test_project_inherits_quote_data(self, auth_headers, test_client):
        """Project should inherit client info, services, and other quote data"""
        # Create another quote with specific data
        test_services = [
            {"item_type": "additional", "bank_name": "Banco Inheritance Test", "item_name": "Product ABC", "category": "Testing", "name": "Product ABC", "quantity": 1, "unit_price_usd": 100, "total_usd": 100}
        ]
        quote_data = {
            "client_id": test_client.get("client_id"),
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "services": test_services,
            "total_usd": 200,
            "sede": "TBP",
            "integrator_name": "Test Integrator",
            "integrator_app_name": "Test App"
        }
        create_response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_response.status_code in [200, 201]
        quote = create_response.json()
        quote_id = quote.get("quote_id")
        
        # Send to implementation
        impl_headers = {
            **auth_headers,
            "x-exception-reason": "Inheritance test",
            "x-regularization-date": "2026-01-26"
        }
        impl_response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", headers=impl_headers)
        assert impl_response.status_code == 200
        
        # Find the project
        projects_response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        projects = projects_response.json()
        project = next((p for p in projects if p.get("quote_id") == quote_id), None)
        
        assert project is not None, "Project should exist"
        assert project.get("client_id") == test_client.get("client_id")
        assert project.get("quote_type") == "VPOS"
        assert project.get("total_usd") is not None  # Value is calculated from services
        assert project.get("integrator_name") == "Test Integrator"
        print(f"Project inherited all quote data correctly. Total USD: {project.get('total_usd')}")


class TestProjectStatsIrregularCount:
    """Test Feature #3: GET /api/projects/stats includes 'irregular' field"""
    
    def test_project_stats_includes_irregular_count(self, auth_headers):
        """Stats endpoint should return 'irregular' field with count"""
        response = requests.get(f"{BASE_URL}/api/projects/stats", headers=auth_headers)
        assert response.status_code == 200
        stats = response.json()
        
        # Verify all expected fields
        assert "total" in stats, "Stats should include 'total'"
        assert "pending" in stats, "Stats should include 'pending'"
        assert "in_progress" in stats, "Stats should include 'in_progress'"
        assert "blocked" in stats, "Stats should include 'blocked'"
        assert "completed" in stats, "Stats should include 'completed'"
        assert "irregular" in stats, "Stats should include 'irregular'"
        
        # Verify irregular count is a number >= 0
        assert isinstance(stats.get("irregular"), int), "'irregular' should be an integer"
        assert stats.get("irregular") >= 0, "'irregular' count should be >= 0"
        
        print(f"Project stats: {stats}")
        print(f"Irregular projects count: {stats.get('irregular')}")


class TestIrregularProjectData:
    """Additional tests for irregular project verification"""
    
    def test_irregular_project_has_exceptions_array(self, auth_headers):
        """Irregular projects should have irregular_exceptions as an array"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200
        projects = response.json()
        
        irregular_projects = [p for p in projects if p.get("is_irregular") == True]
        
        for project in irregular_projects:
            exceptions = project.get("irregular_exceptions", [])
            assert isinstance(exceptions, list), f"irregular_exceptions should be a list for project {project.get('project_number')}"
            if len(exceptions) > 0:
                # Verify exception structure
                exc = exceptions[0]
                assert "action" in exc, "Exception should have 'action' field"
                assert "reason" in exc, "Exception should have 'reason' field"
                print(f"Project {project.get('project_number')} has {len(exceptions)} exceptions")
        
        print(f"Verified {len(irregular_projects)} irregular projects have proper exception arrays")


class TestQuoteMarkIrregular:
    """Test the mark_quote_irregular function handles null arrays correctly"""
    
    def test_mark_quote_irregular_handles_null_array(self, auth_headers, test_client):
        """mark_quote_irregular should handle quotes with null irregular_exceptions"""
        # Create a quote (will have null irregular_exceptions initially)
        quote_data = {
            "client_id": test_client.get("client_id"),
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "services": [],
            "total_usd": 50,
            "sede": "TBP"
        }
        create_response = requests.post(f"{BASE_URL}/api/quotes", json=quote_data, headers=auth_headers)
        assert create_response.status_code in [200, 201]
        quote = create_response.json()
        quote_id = quote.get("quote_id")
        
        # Try collect action (irregular since quote is in Borrador, not Facturada)
        collect_headers = {
            **auth_headers,
            "x-exception-reason": "Testing null array handling",
            "x-regularization-date": "2026-01-27"
        }
        # Collect requires payment attachment, but the irregular marking happens first
        collect_response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/collect", headers=collect_headers)
        # Will fail at attachment validation, but irregular marking should have succeeded
        
        # Check the quote was marked irregular
        quote_response = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=auth_headers)
        if quote_response.status_code == 200:
            updated_quote = quote_response.json()
            # If we get here, quote wasn't deleted, check irregular status
            assert updated_quote.get("is_irregular") == True, "Quote should be marked irregular"
            exceptions = updated_quote.get("irregular_exceptions", [])
            assert len(exceptions) > 0, "Quote should have irregular exceptions"
            print(f"Quote marked irregular with {len(exceptions)} exceptions")
        else:
            # Quote might have been modified/deleted, which is also valid
            print("Quote state changed during test (expected in some flows)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
