"""
Iter38 — Homologación motor de PDF (P0).

Valida que los 3 disparadores (Previsualizar / Exportar / Guardar) generen
EXACTAMENTE el mismo documento desde el backend, hidratando los nombres
desde Mongo a partir de los IDs (aislamiento de RBAC del usuario).
"""
import io
import os
import re

import pytest
import requests
from PyPDF2 import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # leer del .env del frontend si no está exportado
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

CLIENT_ID = "cli_2aa0ea072c7f"
INTEGRATOR_ID = "int_7c555185aa22"
PINPAD_ID = "hwr_3b365a77248a"
BANK_ID = "bnk_3997d471d939"


# ---- Fixtures ----------------------------------------------------------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login falló: {r.status_code} {r.text[:200]}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"login sin session_token: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _payload_vpos_pyme_empty_names():
    """Payload de Previsualizar/Exportar con nombres vacíos (escenario RBAC)."""
    return {
        "cliente_nombre": "",
        "cliente_rif": "",
        "integrator_name": "",
        "pinpad_model": "",
        "sponsor_bank_name": "",
        "client_id": CLIENT_ID,
        "integrator_id": INTEGRATOR_ID,
        "pinpad_id": PINPAD_ID,
        "sponsor_bank_id": BANK_ID,
        "quote_type": "VPOS",
        "client_segment": "PYME",
    }


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _pdf_pages(content: bytes) -> int:
    return len(PdfReader(io.BytesIO(content)).pages)


# ---- Tests -------------------------------------------------------------------
class TestPreviewPdfHydration:
    """POST /api/quotes/preview-pdf-with-template hidrata desde IDs."""

    def test_preview_returns_pdf_with_hydrated_names(self, session):
        r = session.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            json=_payload_vpos_pyme_empty_names(),
            timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "respuesta no es PDF binario"

        text = _pdf_text(r.content)
        # nombres autoritativos hidratados server-side
        assert "10 DE NOVIEMBRE" in text.upper(), "cliente no hidratado"
        assert "Equinoccio" in text, "integrador no hidratado"
        assert "Morefun" in text, "pinpad no hidratado"
        assert "Venezuela" in text, "banco patrocinador no hidratado"


class TestGeneratePdfParityWithPreview:
    """POST /api/quotes/generate-pdf-with-template == preview (texto/páginas)."""

    def test_export_pdf_matches_preview(self, session):
        payload = _payload_vpos_pyme_empty_names()
        r_prev = session.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template", json=payload, timeout=60
        )
        r_gen = session.post(
            f"{BASE_URL}/api/quotes/generate-pdf-with-template", json=payload, timeout=60
        )
        assert r_prev.status_code == 200, f"preview: {r_prev.status_code} {r_prev.text[:200]}"
        assert r_gen.status_code == 200, f"generate: {r_gen.status_code} {r_gen.text[:200]}"
        assert r_gen.headers.get("content-type", "").startswith("application/pdf")

        # mismo número de páginas
        assert _pdf_pages(r_prev.content) == _pdf_pages(r_gen.content), \
            "número de páginas distinto entre preview y export"

        # texto extraído idéntico (paridad funcional)
        t_prev = _pdf_text(r_prev.content)
        t_gen = _pdf_text(r_gen.content)
        # Normalizar para evitar diferencias de timestamps si los hay
        norm = lambda s: re.sub(r"\s+", " ", s).strip()
        assert norm(t_prev) == norm(t_gen), "texto del PDF difiere entre preview y export"


class TestCreateWithPdfHydration:
    """POST /api/quotes/create-with-pdf (GATEWAY) hidrata y persiste PDF."""

    def test_create_gateway_with_empty_names_hydrates(self, session):
        pdf_data = {
            "cliente_nombre": "",
            "cliente_rif": "",
            "integrator_name": "",
            "pinpad_model": "",
            "sponsor_bank_name": "",
            "client_id": CLIENT_ID,
            "integrator_id": INTEGRATOR_ID,
            "pinpad_id": PINPAD_ID,
            "sponsor_bank_id": BANK_ID,
            "quote_type": "GATEWAY",
            "client_segment": "PYME",
            "pg_setup_items": [
                {"description": "Setup Gateway", "amount": 500.0},
            ],
            "pg_monthly_items": [
                {"description": "Mensualidad Gateway", "amount": 120.0},
            ],
        }
        payload = {
            "client_id": CLIENT_ID,
            "client_name": "10 DE NOVIEMBRE, C.A.",
            "client_rif": "J505015214",
            "integrator_id": INTEGRATOR_ID,
            "quote_type": "GATEWAY",
            "client_segment": "PYME",
            "pdf_data": pdf_data,
            "pg_setup_items": pdf_data["pg_setup_items"],
            "pg_monthly_items": pdf_data["pg_monthly_items"],
        }
        r = session.post(
            f"{BASE_URL}/api/quotes/create-with-pdf", json=payload, timeout=90
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
        body = r.json()
        quote_obj = body.get("quote") or {}
        quote_id = (
            quote_obj.get("quote_id")
            or quote_obj.get("id")
            or body.get("quote_id")
            or body.get("id")
        )
        assert quote_id, f"create-with-pdf no devolvió quote_id: {body}"

        # descargar el PDF guardado (servido bajo /api/uploads/)
        pdf_rel = body.get("pdf_url") or quote_obj.get("quote_pdf_url")
        assert pdf_rel, f"create-with-pdf no devolvió pdf_url: {body}"
        # convertir /uploads/... -> /api/uploads/...
        if pdf_rel.startswith("/uploads/"):
            pdf_rel = "/api" + pdf_rel
        pdf_url = pdf_rel if pdf_rel.startswith("http") else f"{BASE_URL}{pdf_rel}"
        r_pdf = session.get(pdf_url, timeout=60)
        assert r_pdf.status_code == 200, f"descarga PDF: {r_pdf.status_code} {r_pdf.text[:200]}"
        assert r_pdf.content[:4] == b"%PDF"

        text = _pdf_text(r_pdf.content)
        assert "10 DE NOVIEMBRE" in text.upper(), "cliente no hidratado en PDF guardado"
        # tabla de costos recurrentes mensuales debe estar presente
        assert ("Costos Recurrentes" in text) or ("Recurrentes Mensuales" in text), \
            "no aparece la tabla de Costos Recurrentes Mensuales"

        # cleanup best-effort
        session.delete(f"{BASE_URL}/api/quotes/{quote_id}", timeout=30)
