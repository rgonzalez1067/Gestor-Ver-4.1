"""
Iteration 231 — Link de Pago / Tokenizador variants (link_pago_variant)

Objetivo:
  - Verificar que el generador PDF y el endpoint preview-pdf-with-template
    respetan la variante seleccionada (link_pago / tokenizador / ambos).
  - Página 5 = anexo variable; página final = Términos (dentro del generator).
  - Página counts esperados (generación directa):
        link_pago  -> 6 (Portada, Resumen, Setup, Recurrentes, Anexo LP, Terminos)
        tokenizador-> 6 (Portada, Resumen, Setup, Recurrentes, Anexo Tokenizador, Terminos)
        ambos      -> 7 (+1 anexo)
  - En la ruta HTTP se anexa además `anexo_pg.pdf` (3 páginas) de Términos legales
    al final, dando 9/9/10. Se valida el DELTA (ambos = link_pago + 1) y la
    persistencia del campo `link_pago_variant`.
"""
import io
import os
import sys
import pytest
import requests
from PyPDF2 import PdfReader

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PWD = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    tk = r.json().get("session_token") or r.json().get("token")
    assert tk, f"Missing token in login response: {r.json()}"
    return tk


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _build_body(variant: str) -> dict:
    return {
        "cliente_nombre": "ACME Test LP",
        "cliente_rif": "J-12345678-9",
        "cliente_contacto": "QA Contacto",
        "quote_number": f"TEST-LP-{variant.upper()}",
        "quote_type": "LINK_PAGO",
        "link_pago_variant": variant,
        "client_segment": "PYME",
        "pg_setup_items": [
            {"concepto": "Persona Jurídica", "costo": 240, "banco": "N/A", "observacion": "Costo Base"}
        ],
        "pg_recurring_cost": {
            "rangos": [{"rango_label": "0-1000", "costo_base_total": 100, "precio_tope": 200}],
            "num_products": 1,
        },
    }


# ---------- Direct generator tests (unit-level) ----------
class TestDirectGenerator:
    """Sanity: el generador dinámico produce 6/6/7 páginas según variante."""

    def _gen(self, variant):
        from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator
        req = TemplateQuotePDFRequest(**_build_body(variant))
        buf = DynamicQuotePDFGenerator(req).generate()
        buf.seek(0)
        return len(PdfReader(buf).pages)

    def test_direct_link_pago_has_6_pages(self):
        assert self._gen("link_pago") == 6

    def test_direct_tokenizador_has_6_pages(self):
        assert self._gen("tokenizador") == 6

    def test_direct_ambos_has_7_pages(self):
        assert self._gen("ambos") == 7

    def test_static_anexos_exist(self):
        for p in [
            "/app/backend/static/anexos/link_pago_anexo.pdf",
            "/app/backend/static/anexos/tokenizador_anexo.pdf",
        ]:
            assert os.path.exists(p), f"Missing anexo: {p}"


# ---------- HTTP endpoint tests ----------
class TestPreviewPdfEndpoint:
    """POST /api/quotes/preview-pdf-with-template respeta link_pago_variant."""

    def _post(self, api, auth_headers, variant):
        r = api.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            json=_build_body(variant),
            headers=auth_headers,
            timeout=60,
        )
        return r

    def test_preview_link_pago_200(self, api, auth_headers):
        r = self._post(api, auth_headers, "link_pago")
        assert r.status_code == 200, r.text[:400]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        pages = len(PdfReader(io.BytesIO(r.content)).pages)
        assert pages >= 6, f"Expected >=6 pages, got {pages}"
        # cache count for delta
        pytest.pages_link_pago = pages

    def test_preview_tokenizador_same_count_as_link_pago(self, api, auth_headers):
        r = self._post(api, auth_headers, "tokenizador")
        assert r.status_code == 200, r.text[:400]
        pages = len(PdfReader(io.BytesIO(r.content)).pages)
        # ambos comparten conteo (uno reemplaza al otro en pág 5)
        assert pages == getattr(pytest, "pages_link_pago", pages), (
            f"tokenizador={pages} vs link_pago={getattr(pytest,'pages_link_pago',None)}"
        )
        pytest.pages_tokenizador = pages

    def test_preview_ambos_one_more_page(self, api, auth_headers):
        r = self._post(api, auth_headers, "ambos")
        assert r.status_code == 200, r.text[:400]
        pages = len(PdfReader(io.BytesIO(r.content)).pages)
        expected = getattr(pytest, "pages_link_pago", None)
        assert expected is not None, "test order broken"
        assert pages == expected + 1, f"ambos={pages}, expected {expected+1}"


# ---------- Persistence via create-with-pdf ----------
class TestQuotePersistenceLinkPagoVariant:
    """Al crear una cotización LINK_PAGO con create-with-pdf, la variante
    debe quedar persistida en Mongo y recuperable por GET /quotes/{id}."""

    created_quote_ids: list = []

    def _first_client(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/clients", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        clients = data if isinstance(data, list) else data.get("clients") or data.get("data") or []
        assert len(clients) > 0, "No hay clientes en catálogo"
        return clients[0]

    def _create_lp_quote(self, api, auth_headers, variant):
        client = self._first_client(api, auth_headers)
        payload = {
            "client_id": client.get("client_id") or client.get("id"),
            "quote_type": "LINK_PAGO",
            "link_pago_variant": variant,
            "pricing_model": "conventional",
            "cantidad_cajas": 1,
            "cantidad_bancos": 1,
            "pg_setup_items": [
                {"concepto": "Persona Jurídica", "costo": 240, "banco": "N/A", "observacion": "Costo Base"}
            ],
            "pg_recurring_cost": {
                "rangos": [{"rango_label": "0-1000", "costo_base_total": 100, "precio_tope": 200}],
                "num_products": 1,
            },
            "setup_items": [],
            "recurring_basic_items": [],
            "recurring_other_items": [],
            "additional_items": [],
            "notes": f"TEST_iter231 {variant}",
            "pdf_data": {
                **_build_body(variant),
                "cliente_nombre": client.get("legal_name") or client.get("fantasy_name") or "TEST_",
                "cliente_rif": client.get("rif", "J-000-0"),
            },
        }
        r = api.post(
            f"{BASE_URL}/api/quotes/create-with-pdf",
            json=payload, headers=auth_headers, timeout=60,
        )
        return r, client

    @pytest.mark.parametrize("variant", ["link_pago", "tokenizador", "ambos"])
    def test_create_persists_variant(self, api, auth_headers, variant):
        r, _ = self._create_lp_quote(api, auth_headers, variant)
        assert r.status_code in (200, 201), f"[{variant}] status={r.status_code} body={r.text[:400]}"
        js = r.json()
        # respuesta puede envolver la quote
        quote = js.get("quote") or js
        qid = quote.get("quote_id") or quote.get("id") or js.get("quote_id")
        assert qid, f"Missing quote_id in response: {js}"
        TestQuotePersistenceLinkPagoVariant.created_quote_ids.append(qid)

        # GET para verificar persistencia
        g = api.get(f"{BASE_URL}/api/quotes/{qid}", headers=auth_headers, timeout=30)
        assert g.status_code == 200, g.text[:300]
        stored = g.json()
        assert stored.get("link_pago_variant") == variant, (
            f"[{variant}] stored variant = {stored.get('link_pago_variant')}"
        )
        assert stored.get("quote_type") == "LINK_PAGO"

    @classmethod
    def teardown_class(cls):
        """Best-effort cleanup: eliminar las cotizaciones TEST creadas."""
        if not cls.created_quote_ids:
            return
        # login para reconstruir token en teardown (no dependa de fixture)
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=15)
            tk = r.json().get("session_token") or r.json().get("token")
            headers = {"Authorization": f"Bearer {tk}"}
            for qid in cls.created_quote_ids:
                try:
                    requests.delete(f"{BASE_URL}/api/quotes/{qid}", headers=headers, timeout=10)
                except Exception:
                    pass
        except Exception:
            pass
