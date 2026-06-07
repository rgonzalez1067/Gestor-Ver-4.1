# ruff: noqa
"""
Iteration 84 - Testing Irregular Administrative Flow for Quotes
Tests:
1. GET /api/quotes/irregular/count - returns count of irregular quotes
2. GET /api/quotes/audit-log - returns audit exception entries
3. POST /api/quotes/{id}/approve with x-exception-reason header when irregular (non-Enviada status)
4. POST /api/quotes/{id}/collect with x-exception-reason header when irregular (non-Facturada status)
5. POST /api/quotes/{id}/deliver with x-exception-reason header when irregular (non-Pagada status)
6. POST /api/quotes/{id}/approve WITHOUT x-exception-reason when status is NOT Enviada returns 422 with IRREGULAR prefix
7. POST /api/quotes/{id}/collect WITHOUT x-exception-reason when status is NOT Facturada returns 422 with IRREGULAR prefix
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def get_auth_token():
    """Login and get auth token"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "test@test.com",
        "password": "Test1234!"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # The API returns session_token, not token
    return data.get("session_token") or data.get("token")


class TestIrregularFlowAPI:
    """Tests for the Irregular Administrative Flow endpoints"""
    
    def test_get_irregular_count(self):
        """Test GET /api/quotes/irregular/count returns count of irregular quotes"""
        token = get_auth_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(f"{BASE_URL}/api/quotes/irregular/count", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert 'count' in data, "Response should contain 'count' field"
        assert isinstance(data['count'], int), "'count' should be an integer"
        print(f"✓ Irregular count endpoint works. Count: {data['count']}")
    
    def test_get_audit_log(self):
        """Test GET /api/quotes/audit-log returns audit exception entries"""
        token = get_auth_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        response = requests.get(f"{BASE_URL}/api/quotes/audit-log", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Audit log should be a list"
        
        # If there are entries, verify the structure
        if len(data) > 0:
            entry = data[0]
            expected_fields = ['audit_id', 'quote_id', 'action', 'expected_status', 
                             'actual_status', 'exception_reason']
            for field in expected_fields:
                assert field in entry, f"Audit entry should have '{field}' field"
        
        print(f"✓ Audit log endpoint works. Entries: {len(data)}")
    
    def test_approve_without_exception_reason_when_irregular(self):
        """Test POST /api/quotes/{id}/approve WITHOUT x-exception-reason when status is NOT Enviada returns 422"""
        token = get_auth_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        # Get quotes to find one in Borrador
        response = requests.get(f"{BASE_URL}/api/quotes", headers=headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        quotes = response.json()
        
        borrador_quote = None
        for quote in quotes:
            if quote.get('quote_status') == 'Borrador':
                borrador_quote = quote
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador status available")
        
        quote_id = borrador_quote['quote_id']
        
        # Try to approve without exception reason (quote is in Borrador, not Enviada)
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=headers)
        
        # Should return 422 with IRREGULAR prefix
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get('detail', '')
        assert 'IRREGULAR' in detail or 'motivo' in detail.lower(), f"Error should mention IRREGULAR flow: {detail}"
        print(f"✓ Approve without exception reason correctly returns 422: {detail}")
    
    def test_collect_without_exception_reason_when_irregular(self):
        """Test POST /api/quotes/{id}/collect WITHOUT x-exception-reason when status is NOT Facturada returns 422"""
        token = get_auth_token()
        headers = {'Authorization': f'Bearer {token}'}
        
        # Get quotes to find one in Borrador
        response = requests.get(f"{BASE_URL}/api/quotes", headers=headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        quotes = response.json()
        
        borrador_quote = None
        for quote in quotes:
            if quote.get('quote_status') == 'Borrador':
                borrador_quote = quote
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador status available")
        
        quote_id = borrador_quote['quote_id']
        
        # Try to collect without exception reason (quote is in Borrador, not Facturada)
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/collect", headers=headers)
        
        # Should return 422 with IRREGULAR prefix
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        
        data = response.json()
        detail = data.get('detail', '')
        assert 'IRREGULAR' in detail or 'motivo' in detail.lower(), f"Error should mention IRREGULAR flow: {detail}"
        print(f"✓ Collect without exception reason correctly returns 422: {detail}")


class TestIrregularFlowWithException:
    """Tests for irregular flow WITH exception headers (requires modifying quote status)"""

    def test_approve_with_exception_reason_but_missing_oc(self):
        """Test POST /api/quotes/{id}/approve with x-exception-reason but missing Orden de Compra"""
        token = get_auth_token()
        auth_headers = {'Authorization': f'Bearer {token}'}
        
        # Get quotes to find one in Borrador
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        quotes = response.json()
        
        borrador_quote = None
        for quote in quotes:
            if quote.get('quote_status') == 'Borrador':
                borrador_quote = quote
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador status available")
        
        quote_id = borrador_quote['quote_id']
        
        # Try to approve WITH exception reason
        headers = {
            **auth_headers,
            'x-exception-reason': 'TEST_REASON_Prueba de flujo irregular',
            'x-regularization-date': '2026-02-15'
        }
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/approve", headers=headers)
        
        # This should still fail because we need Orden de Compra attachment
        # The irregular flow just logs the exception, but the business rule still applies
        if response.status_code == 422:
            detail = response.json().get('detail', '')
            # Should be about missing Orden de Compra, not about irregular flow
            assert 'Orden de Compra' in detail, f"Should require OC after exception: {detail}"
            print(f"✓ Approve with exception but missing OC correctly requires document: {detail}")
        else:
            # If it passed, the quote had an OC already
            assert response.status_code == 200, f"Unexpected error: {response.text}"
            print("✓ Approve with exception passed (quote had OC)")
    
    def test_collect_with_exception_reason_but_missing_payment(self):
        """Test POST /api/quotes/{id}/collect with x-exception-reason but missing payment proof"""
        token = get_auth_token()
        auth_headers = {'Authorization': f'Bearer {token}'}
        
        # Get quotes to find one in Borrador
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        quotes = response.json()
        
        borrador_quote = None
        for quote in quotes:
            if quote.get('quote_status') == 'Borrador':
                borrador_quote = quote
                break
        
        if not borrador_quote:
            pytest.skip("No quote in Borrador status available")
        
        quote_id = borrador_quote['quote_id']
        
        # Try to collect WITH exception reason
        headers = {
            **auth_headers,
            'x-exception-reason': 'TEST_REASON_Prueba de cobro irregular',
            'x-regularization-date': '2026-02-20'
        }
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/collect", headers=headers)
        
        # This should still fail because we need payment proof attachment
        if response.status_code == 422:
            detail = response.json().get('detail', '')
            # Should be about missing payment proof, not about irregular flow
            assert 'pago' in detail.lower() or 'comprobante' in detail.lower(), f"Should require payment: {detail}"
            print(f"✓ Collect with exception but missing payment correctly requires document: {detail}")
        else:
            assert response.status_code == 200, f"Unexpected error: {response.text}"
            print("✓ Collect with exception passed (quote had payment proof)")
    
    def test_deliver_with_exception_reason_non_equipment(self):
        """Test POST /api/quotes/{id}/deliver with x-exception-reason on implementation quote"""
        token = get_auth_token()
        auth_headers = {'Authorization': f'Bearer {token}'}
        
        # Get quotes to find one that's NOT equipment
        response = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get quotes: {response.text}"
        quotes = response.json()
        
        impl_quote = None
        for quote in quotes:
            if quote.get('quote_category') != 'equipment':
                impl_quote = quote
                break
        
        if not impl_quote:
            pytest.skip("No implementation quote available")
        
        quote_id = impl_quote['quote_id']
        
        # Try to deliver an implementation quote WITH exception
        headers = {
            **auth_headers,
            'x-exception-reason': 'TEST_REASON_Prueba de entrega irregular',
            'x-regularization-date': '2026-02-25'
        }
        response = requests.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver", headers=headers)
        
        # Should fail because deliver only applies to equipment quotes
        assert response.status_code == 400, f"Expected 400 for non-equipment, got {response.status_code}: {response.text}"
        
        detail = response.json().get('detail', '')
        assert 'equipo' in detail.lower(), f"Should mention equipment-only: {detail}"
        print(f"✓ Deliver on implementation quote correctly rejected: {detail}")


class TestIrregularEndpointsAuth:
    """Test auth requirements for irregular endpoints"""
    
    def test_irregular_count_requires_auth(self):
        """Test that /api/quotes/irregular/count requires authentication"""
        response = requests.get(f"{BASE_URL}/api/quotes/irregular/count")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Irregular count endpoint requires authentication")
    
    def test_audit_log_requires_auth(self):
        """Test that /api/quotes/audit-log requires authentication"""
        response = requests.get(f"{BASE_URL}/api/quotes/audit-log")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Audit log endpoint requires authentication")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
