"""
Iteration 121 — Corporate PG/LP PDF restructure tests.

Validates the pure helpers `apply_corporate_pg_lp_restructure` and
`append_quote_static_pages` from /app/backend/config.py and an e2e
sanity check on the preview-pdf-with-template endpoint for
GATEWAY/LINK_PAGO × PYME/CORP segments.
"""
import io
import os
import sys
import pytest
import requests
from pathlib import Path

# Ensure /app/backend is importable when running pytest from /app
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from PyPDF2 import PdfReader, PdfWriter  # noqa: E402
from reportlab.pdfgen import canvas as rl_canvas  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402

import config as cfg  # noqa: E402


# ---- BASE_URL discovery: prefer frontend public URL (used by user) ---------
def _read_env_url() -> str:
    # Prefer frontend/.env (public ingress) as required by the runbook
    frontend_env = Path("/app/frontend/.env")
    if frontend_env.exists():
        for line in frontend_env.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE_URL = _read_env_url()


# ============================================================================
# Helpers — synthetic PDF builders
# ============================================================================

def _make_pdf_with_n_pages(n: int, label_prefix: str = "BASE") -> io.BytesIO:
    """Generate a PDF in-memory with `n` distinguishable pages."""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter)
    for i in range(1, n + 1):
        c.setFont("Helvetica-Bold", 24)
        c.drawString(72, 720, f"{label_prefix}-PAGE-{i}")
        c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _count_pages(buf: io.BytesIO) -> int:
    buf.seek(0)
    return len(PdfReader(buf).pages)


# ============================================================================
# Pure function tests — these are the high-priority assertions
# ============================================================================

class TestApplyCorporatePGLPRestructure:
    """apply_corporate_pg_lp_restructure: truncar + fusionar anexo CORP."""

    def test_gateway_corp_returns_4_base_plus_1_anexo(self):
        base = _make_pdf_with_n_pages(8, label_prefix="PGBASE")
        out = cfg.apply_corporate_pg_lp_restructure(base, "GATEWAY")
        total = _count_pages(out)
        # 4 first base pages + 1 anexo_gateway_corp page (1 page file)
        assert total == 5, f"PG+CORP expected 5 pages, got {total}"

    def test_link_pago_corp_returns_5_base_plus_1_anexo(self):
        base = _make_pdf_with_n_pages(9, label_prefix="LPBASE")
        out = cfg.apply_corporate_pg_lp_restructure(base, "LINK_PAGO")
        total = _count_pages(out)
        # 5 first base pages + 1 anexo_link_corp page
        assert total == 6, f"LP+CORP expected 6 pages, got {total}"

    def test_unknown_quote_type_returns_buffer_unchanged(self):
        base = _make_pdf_with_n_pages(3)
        out = cfg.apply_corporate_pg_lp_restructure(base, "VPOS_MPOS")
        # No mapping → returns input as-is
        assert _count_pages(out) == 3

    def test_fallback_when_anexo_missing(self, tmp_path, monkeypatch):
        # Repoint STATIC_PDFS_DIR to an empty dir → fallback to append_pg_static_pages
        monkeypatch.setattr(cfg, "STATIC_PDFS_DIR", tmp_path)
        base = _make_pdf_with_n_pages(8)
        out = cfg.apply_corporate_pg_lp_restructure(base, "GATEWAY")
        # anexo_pg.pdf also missing in tmp_path → returns base unchanged (8 pages)
        assert _count_pages(out) == 8


class TestAppendQuoteStaticPagesRouter:
    """append_quote_static_pages: ruteo producto × segmento."""

    def test_gateway_pyme_matches_append_pg_static_pages(self):
        base = _make_pdf_with_n_pages(5, label_prefix="PG_PYME_BASE")
        a = cfg.append_quote_static_pages(base, "GATEWAY", "PYME")
        # reset buffer & call legacy directly to compare page count
        base2 = _make_pdf_with_n_pages(5, label_prefix="PG_PYME_BASE")
        b = cfg.append_pg_static_pages(base2)
        assert _count_pages(a) == _count_pages(b), (
            f"GATEWAY+PYME page count mismatch: unified={_count_pages(a)} "
            f"legacy={_count_pages(b)}"
        )

    def test_link_pago_pyme_matches_append_pg_static_pages(self):
        base = _make_pdf_with_n_pages(6, label_prefix="LP_PYME_BASE")
        a = cfg.append_quote_static_pages(base, "LINK_PAGO", "PYME")
        base2 = _make_pdf_with_n_pages(6, label_prefix="LP_PYME_BASE")
        b = cfg.append_pg_static_pages(base2)
        assert _count_pages(a) == _count_pages(b), (
            f"LINK_PAGO+PYME page count mismatch: unified={_count_pages(a)} "
            f"legacy={_count_pages(b)}"
        )

    def test_gateway_corp_via_router_truncates_to_4_plus_anexo(self):
        base = _make_pdf_with_n_pages(8, label_prefix="PG_CORP_BASE")
        out = cfg.append_quote_static_pages(base, "GATEWAY", "CORP")
        assert _count_pages(out) == 5

    def test_link_pago_corp_via_router_truncates_to_5_plus_anexo(self):
        base = _make_pdf_with_n_pages(9, label_prefix="LP_CORP_BASE")
        out = cfg.append_quote_static_pages(base, "LINK_PAGO", "CORP")
        assert _count_pages(out) == 6

    def test_corp_segment_lowercase_is_normalized(self):
        base = _make_pdf_with_n_pages(8)
        out = cfg.append_quote_static_pages(base, "GATEWAY", "corp")
        assert _count_pages(out) == 5  # still truncated+merged

    def test_vpos_corp_uses_corporate_anexo(self):
        # VPOS_MPOS + CORP → append_corporate_static_pages (anexo_corporativa.pdf)
        base = _make_pdf_with_n_pages(4, label_prefix="VPOS_CORP")
        out = cfg.append_quote_static_pages(base, "VPOS_MPOS", "CORP")
        # anexo_corporativa.pdf exists; we just check pages grow
        assert _count_pages(out) > 4

    def test_first_4_pages_of_gateway_corp_are_base(self):
        """Garantiza que se conservan EXACTAMENTE las primeras 4 páginas base."""
        base = _make_pdf_with_n_pages(8, label_prefix="PGBASE")
        out = cfg.append_quote_static_pages(base, "GATEWAY", "CORP")
        out.seek(0)
        reader = PdfReader(out)
        # Extract text from each of the first 4 pages and check the label
        for i in range(4):
            txt = reader.pages[i].extract_text() or ""
            assert f"PGBASE-PAGE-{i + 1}" in txt, (
                f"Page {i + 1} content mismatch: got {txt!r}"
            )

    def test_first_5_pages_of_lp_corp_are_base(self):
        base = _make_pdf_with_n_pages(9, label_prefix="LPBASE")
        out = cfg.append_quote_static_pages(base, "LINK_PAGO", "CORP")
        out.seek(0)
        reader = PdfReader(out)
        for i in range(5):
            txt = reader.pages[i].extract_text() or ""
            assert f"LPBASE-PAGE-{i + 1}" in txt, (
                f"Page {i + 1} content mismatch: got {txt!r}"
            )


# ============================================================================
# E2E — preview-pdf-with-template endpoint
# ============================================================================

@pytest.fixture(scope="module")
def admin_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "rgonzalez@megasoft.com.ve", "password": "admin123"},
        timeout=30,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("session_token") or data.get("token")
    if not token:
        pytest.skip(f"No session_token in login response: {data}")
    return token


def _build_preview_payload(quote_type: str, segment: str) -> dict:
    """Minimum TemplateQuotePDFRequest payload."""
    return {
        "template_type": "pg_pyme" if quote_type == "GATEWAY" else "link_pago_pyme",
        "cliente_nombre": "TEST CLIENT CORP PG/LP",
        "cliente_rif": "J123456789",
        "cliente_contacto": "Test Contacto",
        "cliente_address": "Av. Test",
        "integrator_name": "Test Integrator",
        "integrator_app_name": "Test App",
        "pinpad_model": "Verifone",
        "sponsor_bank_name": "Banco Test",
        "cantidad_cajas": 1,
        "quote_number": "TEST-COT-PREVIEW",
        "setup_items": [],
        "recurring_basic_items": [],
        "recurring_other_items": [],
        "additional_items": [],
        "production_items": [],
        "pg_setup_items": [
            {"concepto": "Setup PG", "costo": 100, "banco": "Banco Test", "observacion": ""}
        ],
        "pg_recurring_cost": {
            "rangos": [
                {"rango_label": "1-100 trx", "costo_base_total": 50, "precio_tope": 80}
            ],
            "num_products": 1,
        },
        "include_recurring": True,
        "descuento": 0,
        "descuento_setup": 0,
        "descuento_recurrente": 0,
        "notes": "",
        "pricing_model": "conventional",
        "quote_type": quote_type,
        "is_production_client": False,
        "ft_equipment_items": [],
        "branch_details": [],
        "is_multirif": False,
        "multirif_distribution": [],
        "client_segment": segment,
        "iva_exempt": False,
    }


def _preview(token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/api/quotes/preview-pdf-with-template",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )


class TestPreviewEndpointE2E:
    """E2E: hit preview-pdf-with-template and check the produced PDF page count."""

    def test_gateway_pyme_preview(self, admin_token):
        resp = _preview(admin_token, _build_preview_payload("GATEWAY", "PYME"))
        assert resp.status_code == 200, f"PG+PYME preview failed: {resp.status_code} {resp.text[:300]}"
        assert resp.headers.get("content-type", "").startswith("application/pdf")
        n = _count_pages(io.BytesIO(resp.content))
        # Should include base + anexo_pg.pdf standard appendix → more than 4 pages
        assert n > 4, f"PG+PYME expected >4 pages, got {n}"

    def test_gateway_corp_preview_truncated_to_5(self, admin_token):
        resp = _preview(admin_token, _build_preview_payload("GATEWAY", "CORP"))
        assert resp.status_code == 200, f"PG+CORP preview failed: {resp.status_code} {resp.text[:300]}"
        n = _count_pages(io.BytesIO(resp.content))
        # PG base generates 5 pages → CORP keeps first 4 + 1 anexo corp = 5
        assert n == 5, f"PG+CORP expected exactly 5 pages, got {n}"

    def test_link_pago_pyme_preview(self, admin_token):
        resp = _preview(admin_token, _build_preview_payload("LINK_PAGO", "PYME"))
        assert resp.status_code == 200, f"LP+PYME preview failed: {resp.status_code} {resp.text[:300]}"
        n = _count_pages(io.BytesIO(resp.content))
        assert n > 5, f"LP+PYME expected >5 pages, got {n}"

    def test_link_pago_corp_preview_truncated_to_6(self, admin_token):
        resp = _preview(admin_token, _build_preview_payload("LINK_PAGO", "CORP"))
        assert resp.status_code == 200, f"LP+CORP preview failed: {resp.status_code} {resp.text[:300]}"
        n = _count_pages(io.BytesIO(resp.content))
        # LP base generates 6 pages → CORP keeps first 5 + 1 anexo corp = 6
        assert n == 6, f"LP+CORP expected exactly 6 pages, got {n}"

    def test_gateway_pyme_vs_corp_have_different_structure(self, admin_token):
        pyme_resp = _preview(admin_token, _build_preview_payload("GATEWAY", "PYME"))
        corp_resp = _preview(admin_token, _build_preview_payload("GATEWAY", "CORP"))
        assert pyme_resp.status_code == 200 and corp_resp.status_code == 200
        n_pyme = _count_pages(io.BytesIO(pyme_resp.content))
        n_corp = _count_pages(io.BytesIO(corp_resp.content))
        assert n_corp < n_pyme, (
            f"CORP({n_corp}) should have fewer pages than PYME({n_pyme}) due to truncation"
        )
