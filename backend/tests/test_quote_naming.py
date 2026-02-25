"""
Test Quote Naming Convention: COT-AAAA-MM-NNN-SEDE
Tests the new definitive quotation naming system with:
- Format COT-AAAA-MM-NNN-SEDE (year-month-sequence-sede)
- Independent counters per sede (TBP vs LCH)
- Sequential counter increments (001, 002, 003...)
- Attachment filenames using quote number as base
"""
import pytest
import requests
import os
import re
from datetime import datetime
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test users
TBP_USER = {"email": "test_anexos@test.com", "password": "Test1234!"}
LCH_USER = {"email": "test_lch@test.com", "password": "Test1234!"}


class TestQuoteNamingConvention:
    """Test quote naming format COT-AAAA-MM-NNN-SEDE"""
    
    @pytest.fixture(scope="class")
    def tbp_session(self):
        """Get authenticated session for TBP user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=TBP_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"TBP login failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def lch_session(self):
        """Get authenticated session for LCH user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=LCH_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"LCH login failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def test_client(self, tbp_session):
        """Create a test client for quotes"""
        client_data = {
            "rif": f"J-TEST-NAMING-{datetime.now().strftime('%H%M%S')}",
            "legal_name": "Test Naming Client",
            "fantasy_name": "Test Naming",
            "segment": "Pymes",
            "address": "Test Address",
            "sucursal": "Principal"
        }
        resp = tbp_session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert resp.status_code == 200, f"Failed to create test client: {resp.text}"
        return resp.json()
    
    def test_tbp_user_sede_is_tbp(self, tbp_session):
        """Verify TBP user has sede=TBP"""
        resp = tbp_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        user = resp.json()
        assert user.get("sede") == "TBP", f"Expected TBP sede, got {user.get('sede')}"
        print(f"✓ TBP user verified: {user.get('email')} with sede={user.get('sede')}")
    
    def test_lch_user_sede_is_lch(self, lch_session):
        """Verify LCH user has sede=LCH"""
        resp = lch_session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 200
        user = resp.json()
        assert user.get("sede") == "LCH", f"Expected LCH sede, got {user.get('sede')}"
        print(f"✓ LCH user verified: {user.get('email')} with sede={user.get('sede')}")
    
    def test_tbp_quote_has_tbp_format(self, tbp_session, test_client):
        """Test TBP user creates quote with COT-AAAA-MM-NNN-TBP format"""
        quote_data = {
            "client_id": test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        resp = tbp_session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert resp.status_code == 200, f"Failed to create quote: {resp.text}"
        
        quote = resp.json()
        quote_number = quote.get("quote_number", "")
        
        # Validate format: COT-YYYY-MM-NNN-TBP
        now = datetime.now()
        expected_pattern = rf"COT-{now.year}-{now.strftime('%m')}-\d{{3}}-TBP"
        assert re.match(expected_pattern, quote_number), f"Quote number {quote_number} doesn't match pattern {expected_pattern}"
        
        # Verify sede is stored
        assert quote.get("sede") == "TBP", f"Expected sede=TBP, got {quote.get('sede')}"
        
        print(f"✓ TBP quote created: {quote_number}")
        return quote
    
    def test_lch_quote_has_lch_format(self, lch_session, test_client):
        """Test LCH user creates quote with COT-AAAA-MM-NNN-LCH format"""
        quote_data = {
            "client_id": test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        resp = lch_session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert resp.status_code == 200, f"Failed to create quote: {resp.text}"
        
        quote = resp.json()
        quote_number = quote.get("quote_number", "")
        
        # Validate format: COT-YYYY-MM-NNN-LCH
        now = datetime.now()
        expected_pattern = rf"COT-{now.year}-{now.strftime('%m')}-\d{{3}}-LCH"
        assert re.match(expected_pattern, quote_number), f"Quote number {quote_number} doesn't match pattern {expected_pattern}"
        
        # Verify sede is stored
        assert quote.get("sede") == "LCH", f"Expected sede=LCH, got {quote.get('sede')}"
        
        print(f"✓ LCH quote created: {quote_number}")
        return quote
    
    def test_counter_increments_correctly(self, tbp_session, test_client):
        """Test that counter increments sequentially (001, 002, 003...)"""
        # Create 2 consecutive quotes
        quote_numbers = []
        for i in range(2):
            quote_data = {
                "client_id": test_client["client_id"],
                "quote_category": "implementation",
                "quote_type": "VPOS",
                "pricing_model": "conventional",
                "services": [],
                "hardware": []
            }
            resp = tbp_session.post(f"{BASE_URL}/api/quotes", json=quote_data)
            assert resp.status_code == 200, f"Failed to create quote {i+1}: {resp.text}"
            quote_numbers.append(resp.json().get("quote_number", ""))
        
        # Extract sequence numbers
        seq1 = int(quote_numbers[0].split("-")[3])
        seq2 = int(quote_numbers[1].split("-")[3])
        
        # Verify increment
        assert seq2 == seq1 + 1, f"Expected sequential increment: {seq1} -> {seq2}"
        print(f"✓ Counter increments correctly: {quote_numbers[0]} -> {quote_numbers[1]}")
    
    def test_sedes_have_independent_counters(self, tbp_session, lch_session, test_client):
        """Test TBP and LCH have independent monthly counters"""
        # Create a quote for TBP
        tbp_quote_data = {
            "client_id": test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        tbp_resp = tbp_session.post(f"{BASE_URL}/api/quotes", json=tbp_quote_data)
        assert tbp_resp.status_code == 200
        tbp_quote_number = tbp_resp.json().get("quote_number", "")
        
        # Create a quote for LCH
        lch_quote_data = {
            "client_id": test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        lch_resp = lch_session.post(f"{BASE_URL}/api/quotes", json=lch_quote_data)
        assert lch_resp.status_code == 200
        lch_quote_number = lch_resp.json().get("quote_number", "")
        
        # Verify different sedes
        assert tbp_quote_number.endswith("-TBP"), f"TBP quote should end with -TBP: {tbp_quote_number}"
        assert lch_quote_number.endswith("-LCH"), f"LCH quote should end with -LCH: {lch_quote_number}"
        
        # Both can exist with same sequence number but different sedes
        print(f"✓ Independent counters: TBP={tbp_quote_number}, LCH={lch_quote_number}")


class TestQuoteAttachmentNaming:
    """Test attachment filename nomenclature based on quote number"""
    
    @pytest.fixture(scope="class")
    def tbp_session(self):
        """Get authenticated session for TBP user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=TBP_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"TBP login failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def test_quote(self, tbp_session):
        """Create a test quote for attachment tests"""
        # First create a client
        client_data = {
            "rif": f"J-TEST-ATT-{datetime.now().strftime('%H%M%S')}",
            "legal_name": "Test Attachment Client",
            "fantasy_name": "Test Attach",
            "segment": "Pymes",
            "address": "Test Address",
            "sucursal": "Principal"
        }
        client_resp = tbp_session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_resp.status_code == 200
        client = client_resp.json()
        
        # Create a quote
        quote_data = {
            "client_id": client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_resp = tbp_session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_resp.status_code == 200
        return quote_resp.json()
    
    def test_orden_compra_filename(self, tbp_session, test_quote):
        """Test 'Orden de Compra' attachment uses COT-..._OrdenCompra.pdf format"""
        quote_id = test_quote["quote_id"]
        quote_number = test_quote["quote_number"]
        
        # Create a fake PDF file
        pdf_content = b"%PDF-1.4 fake orden de compra content"
        files = {"file": ("test_oc.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"category": "Orden de Compra"}
        
        # Remove Content-Type header for multipart form
        headers = {"Authorization": tbp_session.headers.get("Authorization")}
        
        resp = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        assert resp.status_code == 200, f"Failed to upload attachment: {resp.text}"
        
        attachment = resp.json().get("attachment", {})
        filename = attachment.get("filename", "")
        
        # Expected format: COT-YYYY-MM-NNN-TBP_OrdenCompra.pdf
        expected_filename = f"{quote_number}_OrdenCompra.pdf"
        assert filename == expected_filename, f"Expected {expected_filename}, got {filename}"
        
        print(f"✓ Orden de Compra filename: {filename}")
    
    def test_factura_filename(self, tbp_session, test_quote):
        """Test 'Factura' attachment uses COT-..._Factura.pdf format"""
        quote_id = test_quote["quote_id"]
        quote_number = test_quote["quote_number"]
        
        pdf_content = b"%PDF-1.4 fake factura content"
        files = {"file": ("test_factura.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"category": "Factura"}
        
        headers = {"Authorization": tbp_session.headers.get("Authorization")}
        
        resp = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        assert resp.status_code == 200, f"Failed to upload attachment: {resp.text}"
        
        attachment = resp.json().get("attachment", {})
        filename = attachment.get("filename", "")
        
        expected_filename = f"{quote_number}_Factura.pdf"
        assert filename == expected_filename, f"Expected {expected_filename}, got {filename}"
        
        print(f"✓ Factura filename: {filename}")
    
    def test_pagos_filename_with_numbered_suffix(self, tbp_session, test_quote):
        """Test 'Pagos' attachments get numbered suffix (_Pago_1, _Pago_2)"""
        quote_id = test_quote["quote_id"]
        quote_number = test_quote["quote_number"]
        
        headers = {"Authorization": tbp_session.headers.get("Authorization")}
        
        # Upload first Pago
        pdf_content1 = b"%PDF-1.4 fake pago 1 content"
        files1 = {"file": ("pago1.pdf", io.BytesIO(pdf_content1), "application/pdf")}
        data1 = {"category": "Pagos"}
        
        resp1 = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files1,
            data=data1,
            headers=headers
        )
        assert resp1.status_code == 200
        filename1 = resp1.json().get("attachment", {}).get("filename", "")
        
        # First Pago should have _1 suffix
        assert "_Pago_1" in filename1, f"First Pago should have _Pago_1 suffix: {filename1}"
        
        # Upload second Pago
        pdf_content2 = b"%PDF-1.4 fake pago 2 content"
        files2 = {"file": ("pago2.pdf", io.BytesIO(pdf_content2), "application/pdf")}
        data2 = {"category": "Pagos"}
        
        resp2 = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files2,
            data=data2,
            headers=headers
        )
        assert resp2.status_code == 200
        filename2 = resp2.json().get("attachment", {}).get("filename", "")
        
        # Second Pago should have _2 suffix
        assert "_Pago_2" in filename2, f"Second Pago should have _Pago_2 suffix: {filename2}"
        
        print(f"✓ Pagos filenames with numbered suffix: {filename1}, {filename2}")
    
    def test_otros_filename_with_numbered_suffix(self, tbp_session, test_quote):
        """Test 'Otros' attachments get numbered suffix"""
        quote_id = test_quote["quote_id"]
        quote_number = test_quote["quote_number"]
        
        headers = {"Authorization": tbp_session.headers.get("Authorization")}
        
        # Upload Otros attachment
        pdf_content = b"%PDF-1.4 fake otros content"
        files = {"file": ("otros.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"category": "Otros"}
        
        resp = requests.post(
            f"{BASE_URL}/api/quotes/{quote_id}/attachments",
            files=files,
            data=data,
            headers=headers
        )
        assert resp.status_code == 200
        filename = resp.json().get("attachment", {}).get("filename", "")
        
        # Otros should have _1 suffix for first file
        assert "_Otros_1" in filename, f"Otros should have _Otros_1 suffix: {filename}"
        
        print(f"✓ Otros filename with numbered suffix: {filename}")


class TestDuplicateQuoteNaming:
    """Test duplicate/modify endpoint uses new naming convention"""
    
    @pytest.fixture(scope="class")
    def tbp_session(self):
        """Get authenticated session for TBP user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=TBP_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"TBP login failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def original_quote(self, tbp_session):
        """Create original quote to duplicate"""
        # Create client
        client_data = {
            "rif": f"J-TEST-DUP-{datetime.now().strftime('%H%M%S')}",
            "legal_name": "Test Duplicate Client",
            "fantasy_name": "Test Dup",
            "segment": "Pymes",
            "address": "Test Address",
            "sucursal": "Principal"
        }
        client_resp = tbp_session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_resp.status_code == 200
        client = client_resp.json()
        
        # Create quote
        quote_data = {
            "client_id": client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": []
        }
        quote_resp = tbp_session.post(f"{BASE_URL}/api/quotes", json=quote_data)
        assert quote_resp.status_code == 200
        return quote_resp.json()
    
    def test_duplicate_quote_gets_new_nomenclature(self, tbp_session, original_quote):
        """Test duplicated quote gets new COT-AAAA-MM-NNN-SEDE number"""
        quote_id = original_quote["quote_id"]
        original_number = original_quote["quote_number"]
        
        resp = tbp_session.post(f"{BASE_URL}/api/quotes/{quote_id}/duplicate")
        assert resp.status_code == 200, f"Failed to duplicate quote: {resp.text}"
        
        result = resp.json()
        new_number = result.get("new_quote_number", "")
        
        # Should be different from original
        assert new_number != original_number, "Duplicated quote should have different number"
        
        # Should follow the same format
        now = datetime.now()
        expected_pattern = rf"COT-{now.year}-{now.strftime('%m')}-\d{{3}}-TBP"
        assert re.match(expected_pattern, new_number), f"New number {new_number} doesn't match pattern"
        
        # Extract sequence numbers
        orig_seq = int(original_number.split("-")[3])
        new_seq = int(new_number.split("-")[3])
        
        # New sequence should be greater than original (uses same counter)
        assert new_seq > orig_seq, f"New sequence {new_seq} should be > original {orig_seq}"
        
        print(f"✓ Duplicate quote: {original_number} -> {new_number}")
    
    def test_duplicate_preserves_sede(self, tbp_session, original_quote):
        """Test duplicated quote preserves original sede"""
        quote_id = original_quote["quote_id"]
        
        resp = tbp_session.post(f"{BASE_URL}/api/quotes/{quote_id}/duplicate")
        assert resp.status_code == 200
        
        new_quote_id = resp.json().get("new_quote_id")
        
        # Fetch the new quote
        quote_resp = tbp_session.get(f"{BASE_URL}/api/quotes/{new_quote_id}")
        assert quote_resp.status_code == 200
        
        new_quote = quote_resp.json()
        assert new_quote.get("sede") == "TBP", f"Duplicated quote sede should be TBP"
        assert new_quote.get("quote_number", "").endswith("-TBP"), "Quote number should end with -TBP"
        
        print(f"✓ Duplicated quote preserves sede: TBP")


class TestCreateWithPDFNaming:
    """Test create-with-pdf endpoint uses new naming convention"""
    
    @pytest.fixture(scope="class")
    def tbp_session(self):
        """Get authenticated session for TBP user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=TBP_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"TBP login failed: {resp.status_code}")
    
    @pytest.fixture(scope="class")
    def test_client(self, tbp_session):
        """Create test client"""
        client_data = {
            "rif": f"J-TEST-PDF-{datetime.now().strftime('%H%M%S')}",
            "legal_name": "Test PDF Client",
            "fantasy_name": "Test PDF",
            "segment": "Pymes",
            "address": "Test Address",
            "sucursal": "Principal"
        }
        resp = tbp_session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert resp.status_code == 200
        return resp.json()
    
    def test_create_with_pdf_uses_new_naming(self, tbp_session, test_client):
        """Test create-with-pdf generates quote with COT-AAAA-MM-NNN-SEDE format"""
        quote_data = {
            "client_id": test_client["client_id"],
            "quote_category": "implementation",
            "quote_type": "VPOS",
            "pricing_model": "conventional",
            "services": [],
            "hardware": [],
            "pdf_data": None  # No PDF data, just test quote creation
        }
        
        resp = tbp_session.post(f"{BASE_URL}/api/quotes/create-with-pdf", json=quote_data)
        assert resp.status_code == 200, f"Failed to create quote: {resp.text}"
        
        result = resp.json()
        quote = result.get("quote", {})
        quote_number = quote.get("quote_number", "")
        
        # Validate format
        now = datetime.now()
        expected_pattern = rf"COT-{now.year}-{now.strftime('%m')}-\d{{3}}-TBP"
        assert re.match(expected_pattern, quote_number), f"Quote number {quote_number} doesn't match pattern"
        
        print(f"✓ Create-with-pdf quote: {quote_number}")


class TestGetQuotesDisplay:
    """Test GET /quotes returns quotes with new format"""
    
    @pytest.fixture(scope="class")
    def tbp_session(self):
        """Get authenticated session for TBP user"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        resp = session.post(f"{BASE_URL}/api/auth/login", json=TBP_USER)
        if resp.status_code == 200:
            token = resp.json().get("session_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            return session
        pytest.skip(f"TBP login failed: {resp.status_code}")
    
    def test_get_quotes_includes_new_format(self, tbp_session):
        """Test GET /quotes returns quotes with COT-AAAA-MM-NNN-SEDE format"""
        resp = tbp_session.get(f"{BASE_URL}/api/quotes")
        assert resp.status_code == 200, f"Failed to get quotes: {resp.text}"
        
        quotes = resp.json()
        assert isinstance(quotes, list), "Response should be a list"
        
        # Check for quotes with new format
        now = datetime.now()
        new_format_pattern = rf"COT-{now.year}-{now.strftime('%m')}-\d{{3}}-(TBP|LCH)"
        new_format_quotes = [q for q in quotes if re.match(new_format_pattern, q.get("quote_number", ""))]
        
        assert len(new_format_quotes) > 0, "Should have quotes with new naming format"
        
        # Verify each new format quote has sede field
        for quote in new_format_quotes:
            assert quote.get("sede") in ["TBP", "LCH"], f"Quote {quote.get('quote_number')} missing valid sede"
        
        print(f"✓ Found {len(new_format_quotes)} quotes with new naming format")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
