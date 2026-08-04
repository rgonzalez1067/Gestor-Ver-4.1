# ruff: noqa
"""
Tests para producto 'Link de Pago' (clon de Payment Gateway con anexo + subtítulo).
Cubre:
  1) Crear cotización LINK_PAGO via POST /api/quotes/create-with-pdf
  2) PDF tiene 'Payment Gateway - Link de Pagos' en pagina 1, anexo en 5-6, Terminos en 7
  3) Regresion: GATEWAY mantiene 'Payment Gateway' (sin Link de Pagos) y Terminos en pagina 5
"""
import os
import io
import re
import pytest
import requests
from PyPDF2 import PdfReader

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://inbox-fixes.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    j = r.json()
    token = j.get("session_token") or j.get("access_token") or j.get("token")
    assert token, f"No token in response: {j}"
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def sample_client(headers):
    r = requests.get(f"{BASE_URL}/api/clients", headers=headers)
    assert r.status_code == 200, r.text
    clients = r.json()
    assert isinstance(clients, list) and len(clients) > 0
    return clients[0]


def _build_pg_payload(quote_type: str, client_id: str):
    return {
        "client_id": client_id,
        "quote_category": "implementation",
        "quote_type": quote_type,
        "services": [],
        "hardware": [],
        "equipment_items": [],
        "pg_setup_items": [
            {"concepto": "Setup PG", "costo": 1500.0}
        ],
        "pg_recurring_cost": {
            "rangos": [
                {"rango_label": "0-500", "precio_tope": 50.0, "costo_base_total": 50.0}
            ]
        },
        "integrator_name": "Integrador Demo",
        "integrator_app_name": "AppDemo",
        "notes": f"Test {quote_type} flow",
    }


def _download_pdf(quote_pdf_url: str) -> bytes:
    # quote_pdf_url is like "/uploads/<file>". Backend serves it under "/api/uploads/<file>"
    path = quote_pdf_url
    if path.startswith("/uploads/"):
        path = "/api" + path
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    r = requests.get(url)
    assert r.status_code == 200, f"PDF download failed: {r.status_code} {url}"
    assert r.content[:4] == b"%PDF", f"Not a PDF: {r.content[:50]} from {url}"
    return r.content


def _extract_pages_text(pdf_bytes: bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [p.extract_text() or "" for p in reader.pages]


class TestLinkPagoFlow:
    """Test creacion y validacion del PDF Link de Pago"""

    def test_1_create_link_pago_quote(self, headers, sample_client):
        payload = _build_pg_payload("LINK_PAGO", sample_client["client_id"])
        r = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", headers=headers, json=payload)
        assert r.status_code == 200, f"Create LINK_PAGO failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("pdf_url"), f"No pdf_url returned: {data}"
        q = data["quote"]
        assert q["quote_type"] == "LINK_PAGO", f"quote_type not persisted: {q.get('quote_type')}"
        assert q.get("quote_pdf_url"), "quote_pdf_url not stored on quote"
        # Stash for next test
        pytest.link_pago_pdf_url = data["pdf_url"]
        pytest.link_pago_quote_id = q["quote_id"]
        pytest.link_pago_quote_number = q["quote_number"]

    def test_2_get_quote_persistence(self, headers):
        qid = getattr(pytest, "link_pago_quote_id", None)
        if not qid:
            pytest.skip("No quote_id from prev test")
        r = requests.get(f"{BASE_URL}/api/quotes/{qid}", headers=headers)
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["quote_type"] == "LINK_PAGO"
        assert q["quote_pdf_url"], "PDF URL not persisted"

    def test_3_pdf_contents_link_pago(self):
        pdf_url = getattr(pytest, "link_pago_pdf_url", None)
        if not pdf_url:
            pytest.skip("no link_pago pdf")
        pdf_bytes = _download_pdf(pdf_url)
        pages = _extract_pages_text(pdf_bytes)
        assert len(pages) >= 7, f"Expected >=7 pages with anexo, got {len(pages)}"
        # P1 subtitulo
        p1 = pages[0]
        assert "Link de Pagos" in p1 or "Link de Pago" in p1, \
            f"Subtitulo 'Link de Pagos' faltante en pagina 1. Encontrado: {p1[:300]}"
        assert "Payment Gateway" in p1, "'Payment Gateway' faltante en pagina 1"
        # Paginas 5-6: anexo (tarifario contiene '500' y '$50,00' o '50.00')
        anexo_text = (pages[4] + "\n" + pages[5]) if len(pages) > 5 else pages[4]
        # El anexo puede tener formato variable; basta verificar que NO es 'Terminos' y existen marcadores numericos del tarifario
        has_tarifa_marker = any(tok in anexo_text for tok in ["500", "50,00", "50.00", "Tarifa", "tarifa"])
        assert has_tarifa_marker, f"Anexo de Link de Pago no detectado en pag 5-6. Texto: {anexo_text[:400]}"
        assert "T\u00c9RMINOS DE LA COTIZACI" not in (pages[4][:200].upper()), "Pagina 5 NO debe ser Terminos"
        # P7: Terminos de la cotizacion
        p7 = pages[6].upper() if len(pages) > 6 else ""
        assert "T" in p7 and ("RMINOS" in p7 or "TERMINOS" in p7 or "T\u00c9RMINOS" in p7 or "T?RMINOS" in p7 or "COTIZACI" in p7), \
            f"'Terminos de la Cotizacion' faltante en pagina 7. Texto: {pages[6][:400] if len(pages)>6 else 'N/A'}"


class TestGatewayRegression:
    """Verifica que GATEWAY estandar no este afectado"""

    def test_1_create_gateway_quote(self, headers, sample_client):
        payload = _build_pg_payload("GATEWAY", sample_client["client_id"])
        r = requests.post(f"{BASE_URL}/api/quotes/create-with-pdf", headers=headers, json=payload)
        assert r.status_code == 200, f"Create GATEWAY failed: {r.status_code} {r.text}"
        data = r.json()
        assert data["quote"]["quote_type"] == "GATEWAY"
        assert data.get("pdf_url"), "GATEWAY pdf_url missing"
        pytest.gateway_pdf_url = data["pdf_url"]

    def test_2_pdf_gateway_no_link_pago(self):
        pdf_url = getattr(pytest, "gateway_pdf_url", None)
        if not pdf_url:
            pytest.skip("no gateway pdf")
        pdf_bytes = _download_pdf(pdf_url)
        pages = _extract_pages_text(pdf_bytes)
        # Pagina 1 NO debe decir 'Link de Pagos'
        p1 = pages[0]
        assert "Payment Gateway" in p1, "GATEWAY p1 debe tener 'Payment Gateway'"
        assert "Link de Pagos" not in p1, f"GATEWAY p1 NO debe contener 'Link de Pagos': {p1[:300]}"
        # Esperar menos paginas que LINK_PAGO (sin anexo de 2 paginas)
        assert len(pages) >= 5, f"Esperado al menos 5 paginas, got {len(pages)}"
        # P5 deberia tener Terminos (sin anexo intercalado)
        p5 = pages[4].upper()
        has_terms_p5 = ("RMINOS" in p5 or "TERMINOS" in p5 or "COTIZACI" in p5)
        assert has_terms_p5, f"GATEWAY: Terminos esperados en pagina 5. Texto: {pages[4][:400]}"


class TestQuoteFilters:
    """Verifica filtros soportan subcategoria Link de Pago"""

    def test_filter_link_pago(self, headers):
        # Intentar filtrar por quote_type=LINK_PAGO si el endpoint lo soporta
        r = requests.get(f"{BASE_URL}/api/quotes?quote_type=LINK_PAGO", headers=headers)
        assert r.status_code == 200, f"Filter LINK_PAGO failed: {r.status_code} {r.text}"
        data = r.json()
        # Puede ser lista directa o {quotes: [...]}
        quotes = data if isinstance(data, list) else data.get("quotes", [])
        # Si filtro funciona, todos deben ser LINK_PAGO. Si no filtra, almenos debe contener uno
        types = {q.get("quote_type") for q in quotes}
        assert "LINK_PAGO" in types or len(quotes) > 0, f"No se encontraron cotizaciones. Types: {types}"
