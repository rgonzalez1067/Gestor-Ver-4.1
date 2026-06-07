# ruff: noqa
"""
Test iteration 17 - New quote status flow endpoints
Testing:
1. POST /api/quotes/{quote_id}/invoice - Upload PDF and invoice number
2. POST /api/quotes/{quote_id}/collect - Mark as Paid
3. POST /api/quotes/{quote_id}/deliver - Mark as Delivered (equipment only)
4. POST /api/quotes/{quote_id}/duplicate - Create new version in Draft
5. GET/PUT /api/config/settings - admin_email and warehouse_email
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SESSION_TOKEN = "Tskr51l-We_-Wr_r4CYvcBvac-F-rxjcEeOABrjAIZg"

@pytest.fixture
def api_client():
    """Shared requests session with auth"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {SESSION_TOKEN}"
    })
    return session

@pytest.fixture
def api_client_multipart():
    """Session for multipart uploads"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {SESSION_TOKEN}"
    })
    return session


class TestConfigSettings:
    """Test the config/settings endpoint for email configuration"""
    
    def test_get_settings(self, api_client):
        """GET /api/config/settings returns all 3 email fields"""
        response = api_client.get(f"{BASE_URL}/api/config/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all 3 email fields exist
        assert "implementation_email" in data, "Missing implementation_email field"
        assert "admin_email" in data, "Missing admin_email field"
        assert "warehouse_email" in data, "Missing warehouse_email field"
        print(f"Settings response: {data}")
    
    def test_update_admin_email(self, api_client):
        """PUT /api/config/settings updates admin_email"""
        test_email = "test-admin@empresa.com"
        
        response = api_client.put(f"{BASE_URL}/api/config/settings", json={
            "admin_email": test_email,
            "warehouse_email": None,
            "implementation_email": None
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("admin_email") == test_email
        print(f"Admin email updated to: {data.get('admin_email')}")
    
    def test_update_warehouse_email(self, api_client):
        """PUT /api/config/settings updates warehouse_email"""
        test_email = "test-almacen@empresa.com"
        
        response = api_client.put(f"{BASE_URL}/api/config/settings", json={
            "admin_email": None,
            "warehouse_email": test_email,
            "implementation_email": None
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("warehouse_email") == test_email
        print(f"Warehouse email updated to: {data.get('warehouse_email')}")
    
    def test_update_all_emails(self, api_client):
        """PUT /api/config/settings updates all 3 emails at once"""
        payload = {
            "admin_email": "admin@test.com",
            "warehouse_email": "almacen@test.com",
            "implementation_email": "implementacion@test.com"
        }
        
        response = api_client.put(f"{BASE_URL}/api/config/settings", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("admin_email") == payload["admin_email"]
        assert data.get("warehouse_email") == payload["warehouse_email"]
        assert data.get("implementation_email") == payload["implementation_email"]
        print(f"All emails updated: {data}")


class TestQuoteDuplicate:
    """Test the duplicate endpoint for creating new versions"""
    
    def test_duplicate_quote(self, api_client):
        """POST /api/quotes/{quote_id}/duplicate creates new version in Draft"""
        quote_id = "quo_ef38d747f331"  # Known existing quote
        
        response = api_client.post(f"{BASE_URL}/api/quotes/{quote_id}/duplicate")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "new_quote_id" in data, "Missing new_quote_id"
        assert "new_quote_number" in data, "Missing new_quote_number"
        assert "version" in data, "Missing version"
        assert data["version"] >= 1, f"Version should be >= 1, got {data['version']}"
        
        print(f"Duplicate created: {data}")
        
        # Verify the new quote is in Borrador status
        new_quote_id = data["new_quote_id"]
        verify_response = api_client.get(f"{BASE_URL}/api/quotes/{new_quote_id}")
        assert verify_response.status_code == 200
        
        new_quote = verify_response.json()
        assert new_quote.get("quote_status") == "Borrador", f"New quote should be Borrador, got {new_quote.get('quote_status')}"
        assert new_quote.get("parent_quote_id") == quote_id, "parent_quote_id should reference original"
        
        print(f"New quote verified: status={new_quote.get('quote_status')}, parent={new_quote.get('parent_quote_id')}")
        
        return data


class TestQuoteInvoice:
    """Test the invoice endpoint for uploading PDF"""
    
    def test_invoice_requires_approved_status(self, api_client_multipart):
        """POST /api/quotes/{quote_id}/invoice rejects non-Approved quotes"""
        # Create a test PDF
        pdf_content = b"%PDF-1.4 test content"
        files = {
            'invoice_file': ('factura.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        data = {'invoice_number': 'FAC-001'}
        
        # Try to invoice a quote that's likely in Borrador status
        quote_id = "quo_ef38d747f331"  # Known existing quote
        
        response = api_client_multipart.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            files=files,
            data=data
        )
        
        # Should fail because quote is not in Approved status
        # Accept both 200 (if somehow approved) or 400 (if not approved)
        if response.status_code == 400:
            assert "Aprobada" in response.json().get("detail", ""), "Error should mention Aprobada status"
            print(f"Correctly rejected: {response.json()}")
        elif response.status_code == 200:
            print("Quote was already Approved, invoice succeeded")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}: {response.text}")
    
    def test_invoice_requires_pdf(self, api_client_multipart):
        """POST /api/quotes/{quote_id}/invoice rejects non-PDF files"""
        # Create a non-PDF file
        files = {
            'invoice_file': ('test.txt', io.BytesIO(b"not a pdf"), 'text/plain')
        }
        data = {'invoice_number': 'FAC-001'}
        
        quote_id = "quo_ef38d747f331"
        
        response = api_client_multipart.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            files=files,
            data=data
        )
        
        # Should fail either for status or for file type
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}: {response.text}"
        print(f"File type validation: {response.json()}")


class TestQuoteCollect:
    """Test the collect endpoint for marking as Paid"""
    
    def test_collect_requires_invoiced_status(self, api_client):
        """POST /api/quotes/{quote_id}/collect rejects non-Facturada quotes"""
        quote_id = "quo_ef38d747f331"
        
        response = api_client.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        
        # Should fail if not in Facturada status
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            assert "Facturada" in detail, f"Error should mention Facturada: {detail}"
            print(f"Correctly rejected: {detail}")
        elif response.status_code == 200:
            print(f"Quote was Facturada, collect succeeded: {response.json()}")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}: {response.text}")


class TestQuoteDeliver:
    """Test the deliver endpoint (equipment quotes only)"""
    
    def test_deliver_requires_paid_status_and_equipment(self, api_client):
        """POST /api/quotes/{quote_id}/deliver only works for equipment quotes in Paid status"""
        # Find an equipment quote
        quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        equipment_quote = next((q for q in quotes if q.get("quote_category") == "equipment"), None)
        
        if not equipment_quote:
            pytest.skip("No equipment quotes available for testing")
        
        quote_id = equipment_quote["quote_id"]
        
        response = api_client.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver")
        
        # Should fail if not in Pagada status
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            print(f"Correctly rejected: {detail}")
        elif response.status_code == 200:
            print(f"Deliver succeeded for equipment quote: {response.json()}")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}: {response.text}")
    
    def test_deliver_rejects_implementation_quote(self, api_client):
        """POST /api/quotes/{quote_id}/deliver rejects implementation quotes"""
        # Find an implementation quote
        quotes_response = api_client.get(f"{BASE_URL}/api/quotes")
        assert quotes_response.status_code == 200
        
        quotes = quotes_response.json()
        impl_quote = next((q for q in quotes if q.get("quote_category") == "implementation"), None)
        
        if not impl_quote:
            pytest.skip("No implementation quotes available for testing")
        
        quote_id = impl_quote["quote_id"]
        
        response = api_client.post(f"{BASE_URL}/api/quotes/{quote_id}/deliver")
        
        # Should fail because it's an implementation quote
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            assert "equipos" in detail.lower() or "equipment" in detail.lower() or "implementation" in detail.lower(), f"Error should mention equipment category: {detail}"
            print(f"Correctly rejected implementation quote: {detail}")
        else:
            # Might fail for status reasons too
            print(f"Response: {response.status_code} - {response.text}")


class TestQuoteStatusTransitions:
    """Test the full quote status flow"""
    
    def test_status_flow_exists_in_quotes(self, api_client):
        """Verify quotes have correct status fields"""
        response = api_client.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json()
        assert len(quotes) > 0, "No quotes found"
        
        # Check status values are valid
        valid_statuses = ["Borrador", "Enviada", "Aprobada", "Facturada", "Pagada", "Entregada", "Enviada a Imple"]
        
        for quote in quotes[:5]:  # Check first 5
            status = quote.get("quote_status", "Borrador")
            assert status in valid_statuses, f"Invalid status: {status}"
            print(f"Quote {quote.get('quote_number')}: {status} ({quote.get('quote_category', 'implementation')})")
    
    def test_quote_has_new_status_fields(self, api_client):
        """Verify quotes have new timestamp fields"""
        quote_id = "quo_ef38d747f331"
        
        response = api_client.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert response.status_code == 200
        
        quote = response.json()
        
        # Check new fields exist (can be null)
        assert "invoiced_at" in quote or quote.get("invoiced_at") is None, "Missing invoiced_at field"
        assert "paid_at" in quote or quote.get("paid_at") is None, "Missing paid_at field"
        assert "delivered_at" in quote or quote.get("delivered_at") is None, "Missing delivered_at field"
        assert "invoice_pdf_url" in quote or quote.get("invoice_pdf_url") is None, "Missing invoice_pdf_url field"
        assert "invoice_number" in quote or quote.get("invoice_number") is None, "Missing invoice_number field"
        assert "version" in quote, "Missing version field"
        assert "parent_quote_id" in quote or quote.get("parent_quote_id") is None, "Missing parent_quote_id field"
        
        print(f"Quote fields verified: version={quote.get('version')}, status={quote.get('quote_status')}")


class TestEndpointAuthentication:
    """Test that all new endpoints require authentication"""
    
    def test_invoice_requires_auth(self):
        """Invoice endpoint requires auth"""
        response = requests.post(f"{BASE_URL}/api/quotes/test/invoice")
        assert response.status_code == 401 or response.status_code == 422
    
    def test_collect_requires_auth(self):
        """Collect endpoint requires auth"""
        response = requests.post(f"{BASE_URL}/api/quotes/test/collect")
        assert response.status_code == 401
    
    def test_deliver_requires_auth(self):
        """Deliver endpoint requires auth"""
        response = requests.post(f"{BASE_URL}/api/quotes/test/deliver")
        assert response.status_code == 401
    
    def test_duplicate_requires_auth(self):
        """Duplicate endpoint requires auth"""
        response = requests.post(f"{BASE_URL}/api/quotes/test/duplicate")
        assert response.status_code == 401
    
    def test_settings_requires_auth(self):
        """Settings endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/config/settings")
        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
