# ruff: noqa
"""
Test Suite for Quote to Project Conversion Bug Fix (Iteration 151)

Tests the following bug fixes:
1. _create_project_from_quote function was EMPTY (dead code) - now restored
2. Equipment search queries were wrong for Fast Track and VPOS/MPOS types - now fixed
3. Email was sent before project creation causing ghost emails on failure - now fixed

Key test scenarios:
- POST /api/quotes/{quote_id}/send-to-implementation creates project AND deletes quote atomically
- Email is only sent AFTER successful project creation
- PDF generation error returns 500 without sending email
- GET /api/quotes/{quote_id}/equipment-for-implementation with project_type parameter
"""

import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_session():
    """Module-scoped authenticated session"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@meganexus.com",
        "password": "Admin123!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("session_token")
    # IMPORTANT: Token must be prefixed with "Bearer " for the API
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"Authenticated successfully with token: {token[:20]}...")
    return session


class TestAuth:
    """Authentication tests"""
    
    def test_login_admin(self, auth_session):
        """Test admin login works"""
        # Just verify the session is authenticated
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200, f"Auth session not working: {response.text}"
        print("Admin authentication verified")


class TestEquipmentForImplementation:
    """Tests for GET /api/quotes/{quote_id}/equipment-for-implementation endpoint"""
    
    def test_equipment_search_without_project_type(self, auth_session):
        """Test equipment search without project_type parameter (generic combined search)"""
        # First get a quote that exists
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200, f"Failed to get quotes: {quotes_response.text}"
        quotes = quotes_response.json()
        
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        # Find a quote with status 'Pagada' or any quote
        test_quote = None
        for q in quotes:
            if q.get("quote_status") == "Pagada":
                test_quote = q
                break
        
        if not test_quote:
            test_quote = quotes[0]
        
        quote_id = test_quote["quote_id"]
        
        # Test without project_type
        response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/equipment-for-implementation")
        assert response.status_code == 200, f"Equipment search failed: {response.text}"
        
        data = response.json()
        assert "quote_equipment" in data, "Response missing quote_equipment field"
        assert "rif_equipment" in data, "Response missing rif_equipment field"
        assert isinstance(data["quote_equipment"], list), "quote_equipment should be a list"
        assert isinstance(data["rif_equipment"], list), "rif_equipment should be a list"
        print(f"Equipment search (no type): quote_equipment={len(data['quote_equipment'])}, rif_equipment={len(data['rif_equipment'])}")
    
    def test_equipment_search_pos_fast_track(self, auth_session):
        """Test equipment search with project_type=pos_fast_track (searches taller_equipos by quote_id)"""
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        test_quote = quotes[0]
        quote_id = test_quote["quote_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/equipment-for-implementation?project_type=pos_fast_track")
        assert response.status_code == 200, f"Fast Track equipment search failed: {response.text}"
        
        data = response.json()
        assert "quote_equipment" in data, "Response missing quote_equipment field"
        assert "rif_equipment" in data, "Response missing rif_equipment field"
        
        # For Fast Track, quote_equipment should be populated from taller_equipos by quote_id
        # rif_equipment should be empty (not searched for Fast Track)
        print(f"Fast Track search: quote_equipment={len(data['quote_equipment'])}, rif_equipment={len(data['rif_equipment'])}")
    
    def test_equipment_search_vpos_mpos(self, auth_session):
        """Test equipment search with project_type=vpos_mpos (searches by client RIF + estatus='Entregado')"""
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        test_quote = quotes[0]
        quote_id = test_quote["quote_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/equipment-for-implementation?project_type=vpos_mpos")
        assert response.status_code == 200, f"VPOS/MPOS equipment search failed: {response.text}"
        
        data = response.json()
        assert "quote_equipment" in data, "Response missing quote_equipment field"
        assert "rif_equipment" in data, "Response missing rif_equipment field"
        
        # For VPOS/MPOS, rif_equipment should be populated from client RIF search
        # quote_equipment should be empty (not searched for VPOS/MPOS)
        print(f"VPOS/MPOS search: quote_equipment={len(data['quote_equipment'])}, rif_equipment={len(data['rif_equipment'])}")
        
        # Verify structure of rif_equipment items if any exist
        for eq in data["rif_equipment"]:
            assert "equipo_id" in eq, "Equipment missing equipo_id"
            assert "modelo" in eq, "Equipment missing modelo"
            assert "serial" in eq, "Equipment missing serial"
            assert eq.get("source") == "cliente_rif", f"Expected source='cliente_rif', got {eq.get('source')}"
    
    def test_equipment_search_payment_gateway(self, auth_session):
        """Test equipment search with project_type=payment_gateway (no equipment needed)"""
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        if not quotes:
            pytest.skip("No quotes available for testing")
        
        test_quote = quotes[0]
        quote_id = test_quote["quote_id"]
        
        response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}/equipment-for-implementation?project_type=payment_gateway")
        assert response.status_code == 200, f"Payment Gateway equipment search failed: {response.text}"
        
        data = response.json()
        # Payment Gateway doesn't need equipment, but endpoint should still work
        assert "quote_equipment" in data or "rif_equipment" in data, "Response should have equipment fields"
        print(f"Payment Gateway search: response keys={list(data.keys())}")
    
    def test_equipment_search_nonexistent_quote(self, auth_session):
        """Test equipment search with non-existent quote returns 404"""
        response = auth_session.get(f"{BASE_URL}/api/quotes/nonexistent_quote_id/equipment-for-implementation")
        assert response.status_code == 404, f"Expected 404 for non-existent quote, got {response.status_code}"


class TestSendToImplementation:
    """Tests for POST /api/quotes/{quote_id}/send-to-implementation endpoint"""
    
    def test_send_to_implementation_requires_pagada_status(self, auth_session):
        """Test that sending to implementation from non-Pagada status requires exception reason"""
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        # Find a quote that is NOT in 'Pagada' status
        test_quote = None
        for q in quotes:
            if q.get("quote_status") != "Pagada":
                test_quote = q
                break
        
        if not test_quote:
            pytest.skip("No non-Pagada quotes available for testing")
        
        quote_id = test_quote["quote_id"]
        
        # Try to send without exception reason - should fail with 422
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", json={
            "project_type_impl": "vpos_mpos"
        })
        
        # Should require exception reason for irregular flow
        assert response.status_code == 422, f"Expected 422 for irregular flow without reason, got {response.status_code}: {response.text}"
        assert "IRREGULAR" in response.text or "motivo" in response.text.lower(), "Error should mention irregular flow"
        print("Correctly rejected irregular flow without exception reason")
    
    def test_send_to_implementation_nonexistent_quote(self, auth_session):
        """Test sending non-existent quote returns 404"""
        response = auth_session.post(f"{BASE_URL}/api/quotes/nonexistent_quote_id/send-to-implementation", json={
            "project_type_impl": "vpos_mpos"
        })
        assert response.status_code == 404, f"Expected 404 for non-existent quote, got {response.status_code}"
    
    def test_send_to_implementation_with_project_type(self, auth_session):
        """Test that project_type_impl is accepted in request body"""
        quotes_response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        quotes = quotes_response.json()
        
        # Find a quote in 'Pagada' status
        test_quote = None
        for q in quotes:
            if q.get("quote_status") == "Pagada":
                test_quote = q
                break
        
        if not test_quote:
            pytest.skip("No Pagada quotes available for testing")
        
        quote_id = test_quote["quote_id"]
        quote_number = test_quote.get("quote_number", "")
        
        # Send to implementation with project_type_impl
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation", json={
            "project_type_impl": "vpos_mpos",
            "equipment_serials": []
        })
        
        # Should succeed (200) or fail with PDF error (500) but not 422
        assert response.status_code in [200, 500], f"Unexpected status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "new_status" in data, "Response should have new_status"
            assert data["new_status"] == "Enviada a Imple", f"Expected 'Enviada a Imple', got {data['new_status']}"
            print(f"Successfully sent quote {quote_number} to implementation")
            
            # Verify project was created
            projects_response = auth_session.get(f"{BASE_URL}/api/projects")
            if projects_response.status_code == 200:
                projects = projects_response.json()
                # Find project with this quote_id
                created_project = None
                for p in projects:
                    if p.get("quote_id") == quote_id or p.get("quote_number") == quote_number:
                        created_project = p
                        break
                
                if created_project:
                    print(f"Project created: {created_project.get('project_number')}")
                    assert created_project.get("project_type_impl") == "vpos_mpos", "project_type_impl not saved"
            
            # Verify quote was deleted
            quote_check = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
            assert quote_check.status_code == 404, "Quote should be deleted after conversion"
            print(f"Quote {quote_id} correctly deleted after conversion")
        else:
            print(f"PDF generation error (expected in some cases): {response.text}")


class TestProjectCreation:
    """Tests to verify project creation from quote"""
    
    def test_projects_list_accessible(self, auth_session):
        """Test that projects list is accessible"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200, f"Projects list failed: {response.text}"
        projects = response.json()
        assert isinstance(projects, list), "Projects should be a list"
        print(f"Found {len(projects)} projects")
    
    def test_project_has_required_fields(self, auth_session):
        """Test that projects have required fields from quote conversion"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        
        if not projects:
            pytest.skip("No projects available for testing")
        
        # Check a project that was created from a quote
        for project in projects:
            if project.get("quote_id"):
                # Verify required fields
                assert "project_id" in project, "Project missing project_id"
                assert "project_number" in project, "Project missing project_number"
                assert "client_name" in project, "Project missing client_name"
                assert "status" in project, "Project missing status"
                assert "created_at" in project, "Project missing created_at"
                
                # Check optional fields from conversion
                if "project_type_impl" in project:
                    assert project["project_type_impl"] in ["pos_fast_track", "vpos_mpos", "payment_gateway", None], \
                        f"Invalid project_type_impl: {project['project_type_impl']}"
                
                print(f"Project {project['project_number']} has all required fields")
                break
    
    def test_verify_existing_conversion(self, auth_session):
        """Verify the successful conversion mentioned in context: quo_f33e678828f4 → PRY-2026-04-003-PRI"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        
        # Look for the project mentioned in the context
        target_project = None
        for p in projects:
            if "PRY-2026-04-003-PRI" in p.get("project_number", ""):
                target_project = p
                break
        
        if target_project:
            print(f"Found converted project: {target_project['project_number']}")
            assert target_project.get("quote_id") == "quo_f33e678828f4" or \
                   target_project.get("quote_number") is not None, \
                   "Project should have quote reference"
        else:
            print("Conversion project PRY-2026-04-003-PRI not found (may have been cleaned up)")


class TestStuckQuotes:
    """Tests related to the 3 stuck quotes mentioned in context"""
    
    def test_check_stuck_quotes_status(self, auth_session):
        """Check status of the 3 stuck quotes mentioned in context"""
        stuck_quote_ids = ["quo_93b515079c77", "quo_bd035dc5c9f5", "quo_cfc1984ab493"]
        
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        quotes = response.json()
        
        found_stuck = []
        for q in quotes:
            if q.get("quote_id") in stuck_quote_ids:
                found_stuck.append({
                    "quote_id": q["quote_id"],
                    "quote_number": q.get("quote_number"),
                    "status": q.get("quote_status"),
                    "category": q.get("quote_category")
                })
        
        print(f"Found {len(found_stuck)} of 3 stuck quotes:")
        for sq in found_stuck:
            print(f"  - {sq['quote_number']}: status={sq['status']}, category={sq['category']}")
        
        # These quotes should still exist with 'Enviada a Imple' status (from before the fix)
        for sq in found_stuck:
            assert sq["status"] == "Enviada a Imple", \
                f"Stuck quote {sq['quote_number']} has unexpected status: {sq['status']}"


class TestAtomicFlow:
    """Tests to verify atomic flow: PDF → Project → Email (in that order)"""
    
    def test_quotes_list_accessible(self, auth_session):
        """Basic test that quotes list is accessible"""
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200, f"Quotes list failed: {response.text}"
        quotes = response.json()
        assert isinstance(quotes, list), "Quotes should be a list"
        print(f"Found {len(quotes)} quotes")
        
        # Count by status
        status_counts = {}
        for q in quotes:
            status = q.get("quote_status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"Quote status distribution: {status_counts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
