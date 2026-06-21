"""
Iteration 124 backend tests:

Verifies the two bug fixes reported by the main agent:
  (1) PDF SYMMETRY: generate-pdf-with-template, preview-pdf-with-template and
      create-with-pdf must produce the SAME number of pages for the same CORP/PYME
      payload.
        * GATEWAY + CORP  -> 5 pages (4 base + 1 corp annex)
        * LINK_PAGO + CORP -> 6 pages (5 base + 1 corp annex)
        * GATEWAY + PYME  -> 8 pages
  (2) MODIFY REGRESSION: /api/quotes/{id}/regenerate-pdf on a CORP quote must
      keep CORP format (5 pages for GATEWAY / 6 pages for LINK_PAGO), not fall
      back to PyME.

We use the real backend through REACT_APP_BACKEND_URL (production preview ingress).
PDF page counts are measured with PyPDF2.
"""

import os
import io
import pytest
import requests
import PyPDF2

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

# Test corporate client
CORP_CLIENT_ID = "cli_ae3319659c30"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("token") or body.get("session_token") or body.get("access_token")
    assert tok, f"No token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _pdf_page_count(content: bytes) -> int:
    reader = PyPDF2.PdfReader(io.BytesIO(content))
    return len(reader.pages)


def _build_payload(quote_type: str, client_segment: str) -> dict:
    """Mimics the wizard's buildTemplatePdfData payload for a minimal PG/LP CORP/PYME quote."""
    return {
        "cliente_nombre": "PROMOTORA TANTALO C.A.",
        "cliente_rif": "J-12345678-9",
        "cliente_contacto": "TEST CONTACT",
        "cliente_address": "Caracas",
        "quote_type": quote_type,
        "pricing_model": "conventional",
        "cantidad_cajas": 1,
        "quote_number": "TEST-COT-2026-001",
        "integrator_name": "Integrador Test",
        "integrator_app_name": "AppTest",
        "pinpad_model": "Verifone P200",
        "sponsor_bank_name": "Banco de Venezuela",
        "template_type": "payment_gateway",
        "client_segment": client_segment,
        "client_id": CORP_CLIENT_ID if client_segment == "CORP" else "",
        "setup_items": [
            {"concepto": "Setup Gateway", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 100.0, "bank_name": "Banco de Venezuela", "tipo_corp": "GATEWAY"}
        ],
        "recurring_basic_items": [
            {"concepto": "Mensualidad Gateway", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 25.0, "bank_name": "Banco de Venezuela", "tipo_corp": "GATEWAY"}
        ],
        "recurring_other_items": [],
        "additional_items": [],
        "production_items": [],
        "pg_setup_items": [{"concepto": "Setup Gateway", "costo": 100.0}],
        "descuento": 0,
        "descuento_setup": 0,
        "descuento_recurrente": 0,
    }


# ============================================================
# (1) PDF SYMMETRY: same payload -> same page count across the 3 endpoints
# ============================================================
class TestPDFSymmetry:
    @pytest.mark.parametrize("quote_type,segment,expected_pages", [
        ("GATEWAY", "CORP", 5),
        ("LINK_PAGO", "CORP", 6),
        ("GATEWAY", "PYME", 8),
    ])
    def test_generate_and_preview_same_page_count(self, headers, quote_type, segment, expected_pages):
        payload = _build_payload(quote_type, segment)

        r_gen = requests.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template",
            json=payload, headers=headers, timeout=60,
        )
        assert r_gen.status_code == 200, f"generate-pdf-with-template failed: {r_gen.status_code} {r_gen.text[:300]}"
        gen_pages = _pdf_page_count(r_gen.content)

        r_prev = requests.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            json=payload, headers=headers, timeout=60,
        )
        assert r_prev.status_code == 200, f"preview-pdf-with-template failed: {r_prev.status_code} {r_prev.text[:300]}"
        prev_pages = _pdf_page_count(r_prev.content)

        assert gen_pages == prev_pages, (
            f"Generate vs Preview page mismatch for {quote_type}/{segment}: "
            f"generate={gen_pages} preview={prev_pages}"
        )
        assert gen_pages == expected_pages, (
            f"Expected {expected_pages} pages for {quote_type}/{segment}, got {gen_pages}"
        )


# ============================================================
# (2) MODIFY REGRESSION: regenerate-pdf on a stored CORP quote must keep CORP format
# ============================================================
class TestModifyCorpRegeneratePDF:
    """
    Creates a temporary CORP quote (GATEWAY then LINK_PAGO) via create-with-pdf,
    calls regenerate-pdf, asserts page count matches the CORP format, then
    cleans up the test quote.
    """

    def _create_corp_quote(self, headers, quote_type: str) -> str:
        # create-with-pdf uses a flat QuoteCreateWithPDF model (not nested)
        payload = {
            "client_id": CORP_CLIENT_ID,
            "quote_category": "implementation",
            "quote_type": quote_type,
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "services": [
                {
                    "item_name": "Setup Gateway",
                    "item_type": "setup",
                    "quantity": 1,
                    "unit_price_usd": 100.0,
                    "total_usd": 100.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "bank_name": "Banco de Venezuela",
                    "tipo_corp": "GATEWAY",
                },
                {
                    "item_name": "Mensualidad Gateway",
                    "item_type": "recurring_basic",
                    "quantity": 1,
                    "unit_price_usd": 25.0,
                    "total_usd": 25.0,
                    "cantidad_cajas": 1,
                    "cantidad_bancos": 1,
                    "bank_name": "Banco de Venezuela",
                    "tipo_corp": "GATEWAY",
                },
            ],
            "hardware": [],
            "equipment_items": [],
            "pg_setup_items": [{"concepto": "Setup Gateway", "costo": 100.0}],
            "client_segment": "CORP",
            "integrator_name": "Integrador Test",
            "sponsor_bank_name": "Banco de Venezuela",
            "pinpad_model": "Verifone P200",
            "notes": "TEST_ITER124 - delete me",
            "pdf_data": _build_payload(quote_type, "CORP"),
        }
        r = requests.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload, headers=headers, timeout=60,
        )
        assert r.status_code in (200, 201), f"create-with-pdf failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        qid = (body.get("quote") or {}).get("quote_id") or body.get("quote_id")
        assert qid, f"No quote_id in response: {body}"
        return qid

    def _delete_quote(self, headers, quote_id: str):
        try:
            requests.delete(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers, timeout=30)
        except Exception:
            pass

    @pytest.mark.parametrize("quote_type,expected_pages", [
        ("GATEWAY", 5),
        ("LINK_PAGO", 6),
    ])
    def test_regenerate_pdf_keeps_corp_format(self, headers, quote_type, expected_pages):
        quote_id = self._create_corp_quote(headers, quote_type)
        try:
            r = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/regenerate-pdf",
                json={}, headers=headers, timeout=60,
            )
            assert r.status_code == 200, f"regenerate-pdf failed: {r.status_code} {r.text[:500]}"
            content_type = r.headers.get("content-type", "")

            if "application/pdf" in content_type:
                pages = _pdf_page_count(r.content)
            else:
                # JSON response with pdf_url pointing to the saved file (real flow).
                body = r.json()
                pdf_url = body.get("pdf_url") or (body.get("attachment") or {}).get("url")
                assert pdf_url, f"regenerate-pdf returned no pdf_url: {body}"
                # The URL is relative, e.g. /uploads/<name>.pdf
                # Backend exposes uploaded files under /api/uploads through the ingress
                if pdf_url.startswith("http"):
                    full = pdf_url
                elif pdf_url.startswith("/api/"):
                    full = f"{BASE_URL}{pdf_url}"
                elif pdf_url.startswith("/uploads/"):
                    full = f"{BASE_URL}/api{pdf_url}"
                else:
                    full = f"{BASE_URL}{pdf_url}"
                dl = requests.get(full, headers=headers, timeout=60)
                assert dl.status_code == 200, f"Could not download regenerated PDF: {dl.status_code}"
                assert "application/pdf" in (dl.headers.get("content-type") or ""), (
                    f"Expected PDF, got {dl.headers.get('content-type')}"
                )
                pages = _pdf_page_count(dl.content)

            assert pages == expected_pages, (
                f"After regenerate-pdf, CORP {quote_type} got {pages} pages, expected {expected_pages} "
                f"(would indicate downgrade to PyME)"
            )
        finally:
            self._delete_quote(headers, quote_id)


# ============================================================
# (3) READ-ONLY regression check against an existing real CORP quote
# ============================================================
class TestExistingCorpQuoteRegenerate:
    """Regression-style check on a known-existing CORP GATEWAY quote
    referenced in iter123 (quo_05e569ead910). The previous failure was that
    regenerate-pdf was downgrading CORP -> PYME (8 pages instead of 5).
    """

    def test_quo_05e569ead910_stays_corp(self, headers):
        qid = "quo_05e569ead910"
        rq = requests.get(f"{BASE_URL}/api/quotes/{qid}", headers=headers, timeout=30)
        if rq.status_code != 200:
            pytest.skip(f"Reference quote {qid} not present in this environment")
        q = rq.json()
        assert q.get("client_segment") == "CORP"
        assert q.get("quote_type") == "GATEWAY"

        r = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/regenerate-pdf",
            json={}, headers=headers, timeout=60,
        )
        assert r.status_code == 200, f"regenerate-pdf failed: {r.status_code} {r.text[:400]}"

        content_type = r.headers.get("content-type", "")
        if "application/pdf" in content_type:
            content = r.content
        else:
            body = r.json()
            pdf_url = body.get("pdf_url") or (body.get("attachment") or {}).get("url")
            assert pdf_url, f"No pdf_url in response: {body}"
            full = pdf_url if pdf_url.startswith("http") else (
                f"{BASE_URL}{pdf_url}" if pdf_url.startswith("/api/") else f"{BASE_URL}/api{pdf_url}"
            )
            dl = requests.get(full, headers=headers, timeout=60)
            assert dl.status_code == 200
            content = dl.content

        pages = _pdf_page_count(content)
        assert pages == 5, f"Existing CORP GATEWAY quote regenerated to {pages} pages (expected 5; PyME=8 would indicate regression)"
