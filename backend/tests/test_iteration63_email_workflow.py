"""
Test Iteration 63: Email Service and Complete Quote Workflow
Tests the simulated email engine and complete quote workflow transitions.

Features tested:
1. Complete workflow: Borrador -> Enviada (send-to-client)
2. Approve flow with Orden de Compra attachment
3. Invoice flow with Factura attachment
4. Collect flow with Pagos attachment
5. Send to Implementation flow
6. GET /api/email-logs returns email history
7. Email template variable resolution (no #{quote_number} in subject)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0226*02"


@pytest.fixture(scope="module")
def auth_session():
    """Module-level authenticated session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    login_response = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if login_response.status_code != 200:
        pytest.skip(f"Login failed: {login_response.status_code}")
    
    login_data = login_response.json()
    # API returns session_token not token
    token = login_data.get("session_token") or login_data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
    else:
        pytest.skip("No token in login response")
    
    yield session
    session.close()


class TestEmailWorkflow:
    """Test the complete email workflow with simulated emails"""
    
    def test_01_get_email_logs_endpoint(self, auth_session):
        """Test GET /api/email-logs returns email history"""
        response = auth_session.get(f"{BASE_URL}/api/email-logs")
        assert response.status_code == 200, f"Email logs failed: {response.text}"
        
        data = response.json()
        assert "email_logs" in data, "Response should have email_logs array"
        assert "count" in data, "Response should have count field"
        
        # Verify log structure if logs exist
        if data["email_logs"]:
            log = data["email_logs"][0]
            expected_fields = ["email_log_id", "action", "to", "subject", "status", "created_at"]
            for field in expected_fields:
                assert field in log, f"Email log should have {field} field"
            
            # Check status is valid
            assert log["status"] in ["sent", "simulated", "error"], f"Invalid status: {log['status']}"
        
        print(f"Email logs endpoint working. Found {data['count']} logs")
    
    def test_02_find_borrador_quote_with_pdf(self, auth_session):
        """Find a Borrador quote with PDF for testing workflow"""
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        assert response.status_code == 200
        
        quotes = response.json().get("quotes", [])
        borrador_quotes = [q for q in quotes if q.get("quote_status") == "Borrador" and q.get("quote_pdf_url")]
        
        print(f"Found {len(borrador_quotes)} Borrador quotes with PDF")
        
        if borrador_quotes:
            quote = borrador_quotes[0]
            print(f"Sample Borrador quote: {quote.get('quote_number')} - {quote.get('quote_id')}")
    
    def test_03_send_to_client_workflow(self, auth_session):
        """Test send-to-client transitions quote to Enviada status and logs email"""
        # First find a borrador quote
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        borrador_quotes = [q for q in quotes if q.get("quote_status") == "Borrador" and q.get("quote_pdf_url")]
        
        if not borrador_quotes:
            pytest.skip("No Borrador quotes with PDF found")
        
        quote = borrador_quotes[0]
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "")
        
        # Send to client
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-client")
        assert response.status_code == 200, f"Send to client failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Enviada", f"Status should be Enviada, got: {data.get('new_status')}"
        assert "recipient" in data, "Response should include recipient email"
        assert "email_log_id" in data, "Response should include email_log_id"
        
        # Verify status in simulated response
        assert data.get("status") in ["sent", "simulated"], f"Email status invalid: {data.get('status')}"
        
        # Verify quote status updated
        verify_response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("quote_status") == "Enviada"
        
        print(f"Send to client successful. Quote {quote_number} now Enviada. Email status: {data.get('status')}")
    
    def test_04_upload_orden_compra_attachment(self, auth_session):
        """Test uploading Orden de Compra attachment for approve workflow"""
        # Find an Enviada quote
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        enviada_quotes = [q for q in quotes if q.get("quote_status") == "Enviada"]
        
        if not enviada_quotes:
            pytest.skip("No Enviada quotes found for attachment test")
        
        quote = enviada_quotes[0]
        quote_id = quote["quote_id"]
        
        # Check if already has Orden de Compra
        attachments = quote.get("attachments", [])
        has_oc = any(a.get("category") == "Orden de Compra" for a in attachments)
        
        if not has_oc:
            # Create a simple test PDF file
            test_pdf_path = "/tmp/test_orden_compra.pdf"
            with open(test_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n%Test PDF file for testing\n%%EOF")
            
            with open(test_pdf_path, "rb") as f:
                files = {"file": ("orden_compra.pdf", f, "application/pdf")}
                data = {"category": "Orden de Compra"}
                
                # Remove Content-Type for multipart
                headers = {"Authorization": auth_session.headers.get("Authorization")}
                
                response = requests.post(
                    f"{BASE_URL}/api/quotes/{quote_id}/attachments",
                    files=files,
                    data=data,
                    headers=headers
                )
            
            assert response.status_code == 200, f"Upload attachment failed: {response.text}"
            attachment_data = response.json()
            assert attachment_data.get("attachment", {}).get("category") == "Orden de Compra"
            print(f"Uploaded Orden de Compra to quote {quote_id}")
        else:
            print(f"Quote {quote_id} already has Orden de Compra")
    
    def test_05_approve_quote_workflow(self, auth_session):
        """Test approve transitions quote to Aprobada status"""
        # Find an Enviada quote with Orden de Compra
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        enviada_quotes = [
            q for q in quotes 
            if q.get("quote_status") == "Enviada" 
            and any(a.get("category") == "Orden de Compra" for a in q.get("attachments", []))
        ]
        
        if not enviada_quotes:
            pytest.skip("No Enviada quotes with Orden de Compra found")
        
        quote = enviada_quotes[0]
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "")
        
        # Approve quote
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/approve")
        assert response.status_code == 200, f"Approve failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Aprobada", f"Status should be Aprobada, got: {data.get('new_status')}"
        assert "emails" in data, "Response should include emails array"
        
        # Verify email was logged
        emails = data.get("emails", [])
        if emails:
            email = emails[0]
            assert email.get("status") in ["sent", "simulated"], f"Email status invalid: {email.get('status')}"
            assert "email_log_id" in email, "Email should have email_log_id"
        
        # Verify quote status
        verify_response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("quote_status") == "Aprobada"
        
        print(f"Approve successful. Quote {quote_number} now Aprobada")
    
    def test_06_upload_factura_attachment(self, auth_session):
        """Test uploading Factura attachment for invoice workflow"""
        # Find an Aprobada quote
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        aprobada_quotes = [q for q in quotes if q.get("quote_status") == "Aprobada"]
        
        if not aprobada_quotes:
            pytest.skip("No Aprobada quotes found for Factura test")
        
        quote = aprobada_quotes[0]
        quote_id = quote["quote_id"]
        
        # Check if already has Factura
        attachments = quote.get("attachments", [])
        has_factura = any(a.get("category") == "Factura" for a in attachments)
        
        if not has_factura:
            test_pdf_path = "/tmp/test_factura.pdf"
            with open(test_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n%Test Factura PDF\n%%EOF")
            
            with open(test_pdf_path, "rb") as f:
                files = {"file": ("factura.pdf", f, "application/pdf")}
                data = {"category": "Factura"}
                
                headers = {"Authorization": auth_session.headers.get("Authorization")}
                
                response = requests.post(
                    f"{BASE_URL}/api/quotes/{quote_id}/attachments",
                    files=files,
                    data=data,
                    headers=headers
                )
            
            assert response.status_code == 200, f"Upload Factura failed: {response.text}"
            print(f"Uploaded Factura to quote {quote_id}")
        else:
            print(f"Quote {quote_id} already has Factura")
    
    def test_07_invoice_quote_workflow(self, auth_session):
        """Test invoice transitions quote to Facturada status"""
        # Find an Aprobada quote with Factura attachment
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        aprobada_quotes = [
            q for q in quotes 
            if q.get("quote_status") == "Aprobada" 
            and any(a.get("category") == "Factura" for a in q.get("attachments", []))
        ]
        
        if not aprobada_quotes:
            pytest.skip("No Aprobada quotes with Factura found")
        
        quote = aprobada_quotes[0]
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "")
        
        # Invoice quote (using Form data)
        headers = {"Authorization": auth_session.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/invoice",
            data={"invoice_number": f"FAC-{quote_number}"},
            headers=headers
        )
        assert response.status_code == 200, f"Invoice failed: {response.text}"
        
        data = response.json()
        assert "emails" in data, "Response should include emails array"
        
        # Verify quote status
        verify_response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("quote_status") == "Facturada"
        
        print(f"Invoice successful. Quote {quote_number} now Facturada")
    
    def test_08_upload_pagos_attachment(self, auth_session):
        """Test uploading Pagos attachment for collect workflow"""
        # Find a Facturada quote
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        facturada_quotes = [q for q in quotes if q.get("quote_status") == "Facturada"]
        
        if not facturada_quotes:
            pytest.skip("No Facturada quotes found for Pagos test")
        
        quote = facturada_quotes[0]
        quote_id = quote["quote_id"]
        
        # Check if already has Pagos
        attachments = quote.get("attachments", [])
        has_pagos = any(a.get("category") == "Pagos" for a in attachments)
        
        if not has_pagos:
            test_pdf_path = "/tmp/test_pago.pdf"
            with open(test_pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n%Test Pago PDF\n%%EOF")
            
            with open(test_pdf_path, "rb") as f:
                files = {"file": ("comprobante_pago.pdf", f, "application/pdf")}
                data = {"category": "Pagos"}
                
                headers = {"Authorization": auth_session.headers.get("Authorization")}
                
                response = requests.post(
                    f"{BASE_URL}/api/quotes/{quote_id}/attachments",
                    files=files,
                    data=data,
                    headers=headers
                )
            
            assert response.status_code == 200, f"Upload Pagos failed: {response.text}"
            print(f"Uploaded Pagos to quote {quote_id}")
        else:
            print(f"Quote {quote_id} already has Pagos")
    
    def test_09_collect_quote_workflow(self, auth_session):
        """Test collect transitions quote to Pagada status"""
        # Find a Facturada quote with Pagos attachment
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        facturada_quotes = [
            q for q in quotes 
            if q.get("quote_status") == "Facturada" 
            and any(a.get("category") == "Pagos" for a in q.get("attachments", []))
        ]
        
        if not facturada_quotes:
            pytest.skip("No Facturada quotes with Pagos found")
        
        quote = facturada_quotes[0]
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "")
        quote_category = quote.get("quote_category", "implementation")
        
        # Collect quote
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/collect")
        assert response.status_code == 200, f"Collect failed: {response.text}"
        
        data = response.json()
        assert data.get("message") == "Cotización marcada como Pagada"
        
        # Verify quote status
        verify_response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("quote_status") == "Pagada"
        
        print(f"Collect successful. Quote {quote_number} now Pagada (category: {quote_category})")
    
    def test_10_send_to_implementation_workflow(self, auth_session):
        """Test send-to-implementation transitions quote to 'Enviada a Imple' status"""
        # Find a Pagada quote (implementation category)
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        # For implementation category quotes
        pagada_quotes = [
            q for q in quotes 
            if q.get("quote_status") == "Pagada" 
            and q.get("quote_category", "implementation") == "implementation"
        ]
        
        if not pagada_quotes:
            pytest.skip("No Pagada implementation quotes found")
        
        quote = pagada_quotes[0]
        quote_id = quote["quote_id"]
        quote_number = quote.get("quote_number", "")
        
        # Send to implementation
        response = auth_session.post(f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation")
        assert response.status_code == 200, f"Send to implementation failed: {response.text}"
        
        data = response.json()
        assert data.get("new_status") == "Enviada a Imple", f"Status should be 'Enviada a Imple', got: {data.get('new_status')}"
        assert "email_log_id" in data, "Response should include email_log_id"
        
        # Verify quote status
        verify_response = auth_session.get(f"{BASE_URL}/api/quotes/{quote_id}")
        assert verify_response.status_code == 200
        assert verify_response.json().get("quote_status") == "Enviada a Imple"
        
        print(f"Send to implementation successful. Quote {quote_number} now 'Enviada a Imple'")
    
    def test_11_email_logs_after_workflow(self, auth_session):
        """Verify email logs contain entries from workflow actions"""
        response = auth_session.get(f"{BASE_URL}/api/email-logs?limit=50")
        assert response.status_code == 200
        
        logs = response.json().get("email_logs", [])
        
        # Verify we have logs
        assert len(logs) > 0, "Should have email logs after workflow"
        
        # Check for different action types
        actions_found = set(log.get("action") for log in logs)
        print(f"Actions found in logs: {actions_found}")
        
        # Verify log structure
        for log in logs[:5]:  # Check first 5 logs
            assert "email_log_id" in log
            assert "status" in log
            assert log["status"] in ["sent", "simulated", "error"]
            assert "action" in log
            assert "to" in log
            assert "subject" in log
            assert "created_at" in log
            
            # Verify subject doesn't have unresolved template variables
            subject = log.get("subject", "")
            assert "#{" not in subject, f"Subject has unresolved variable: {subject}"
            assert "{{" not in subject, f"Subject has unresolved variable: {subject}"
        
        print(f"Email logs verified. Found {len(logs)} logs with actions: {actions_found}")
    
    def test_12_email_template_resolution(self, auth_session):
        """Verify email templates resolve variables correctly (no #{quote_number} in subject)"""
        response = auth_session.get(f"{BASE_URL}/api/email-logs?limit=20")
        assert response.status_code == 200
        
        logs = response.json().get("email_logs", [])
        
        for log in logs:
            subject = log.get("subject", "")
            
            # Check subject for unresolved template variables
            unresolved_patterns = ["#{", "{{"]
            for pattern in unresolved_patterns:
                assert pattern not in subject, f"Unresolved variable in subject: {subject}"
            
            # Log shows quote_number was resolved
            if log.get("quote_number"):
                assert log["quote_number"] not in ["", None], "quote_number should be set in log"
        
        print("Email template resolution check complete - all variables resolved correctly")


class TestEmailServiceValidation:
    """Additional tests for email service validation"""
    
    def test_workflow_requires_attachments(self, auth_session):
        """Verify workflow actions require correct attachments"""
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        # Find an Enviada quote WITHOUT Orden de Compra
        enviada_no_oc = [
            q for q in quotes 
            if q.get("quote_status") == "Enviada" 
            and not any(a.get("category") == "Orden de Compra" for a in q.get("attachments", []))
        ]
        
        if enviada_no_oc:
            quote = enviada_no_oc[0]
            response = auth_session.post(f"{BASE_URL}/api/quotes/{quote['quote_id']}/approve")
            # Should fail with 422 - attachment required
            assert response.status_code == 422, f"Should require Orden de Compra, got: {response.status_code}"
            print("Approve correctly requires Orden de Compra attachment")
        else:
            print("No Enviada quotes without OC found - skipping attachment validation")
    
    def test_workflow_status_transitions(self, auth_session):
        """Verify workflow enforces correct status transitions"""
        response = auth_session.get(f"{BASE_URL}/api/quotes")
        quotes = response.json().get("quotes", [])
        
        # Find a Borrador quote and try to approve (should fail)
        borrador_quotes = [q for q in quotes if q.get("quote_status") == "Borrador"]
        
        if borrador_quotes:
            quote = borrador_quotes[0]
            response = auth_session.post(f"{BASE_URL}/api/quotes/{quote['quote_id']}/approve")
            # Should fail - can't approve Borrador directly
            assert response.status_code == 400, f"Should reject approve from Borrador, got: {response.status_code}"
            print("Workflow correctly enforces status transitions")
        else:
            print("No Borrador quotes found - skipping transition validation")
