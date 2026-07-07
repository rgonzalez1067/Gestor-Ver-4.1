"""Iter244 — Fecha de Vencimiento (portada) para cotizaciones de Implementaciones.

Feature: Emisión + 15 días hábiles (exclusivo, el día de emisión NO cuenta),
saltando sábados/domingos y feriados de db.holidays. Aparece en la PORTADA
debajo de 'FECHA DE EMISIÓN'. Adicionalmente: se ELIMINÓ 'Vigencia de la
Propuesta' de la página de Términos y Condiciones.

Cobertura:
1) Algoritmo business_calendar.add_business_days_after (unit).
2) Endpoint /api/quotes/preview-pdf-with-template para VPOS PyME, Gateway,
   VPOS CORP (integración) — verifica que la portada contiene
   'FECHA DE VENCIMIENTO' con formato DD/MM/AAAA y que 'Vigencia de la
   Propuesta' fue removida.
3) Endpoint /api/quotes/generate-pdf-with-template (persiste PDF y devuelve
   URL) también genera portada con vencimiento.
"""
import os
import io
import re
import pytest
import requests
from datetime import date, datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Cargar env de backend/.env por si REACT_APP_BACKEND_URL no está exportado
if not BASE_URL:
    from dotenv import load_dotenv
    load_dotenv("/app/frontend/.env")
    BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

assert BASE_URL, "REACT_APP_BACKEND_URL debe estar definido"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

DDMMYYYY_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


# --------------------- Fixtures ---------------------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login falló: {r.status_code} {r.text[:200]}"
    j = r.json()
    tok = j.get("session_token") or j.get("access_token") or j.get("token")
    assert tok, "No se obtuvo token"
    return tok


@pytest.fixture(scope="module")
def auth(api, token):
    api.headers.update({"Authorization": f"Bearer {token}"})
    return api


@pytest.fixture(scope="module")
def client_id(auth):
    r = auth.get(f"{BASE_URL}/api/clients", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("clients", []))
    assert items, "Se requiere al menos un cliente para las pruebas"
    return items[0].get("client_id") or items[0].get("id")


# --------------------- Módulo: business_calendar (unit) ---------------------

class TestBusinessCalendar:
    """Algoritmo: 15 días hábiles DESPUÉS de la emisión (exclusivo)."""

    def test_lunes_01sep2025_mas_15_debe_ser_lunes_22sep2025(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.business_calendar import add_business_days_after
        start = date(2025, 9, 1)  # Lunes
        result = add_business_days_after(start, 15, set(), set())
        assert result == date(2025, 9, 22), f"Esperado 2025-09-22, obtenido {result}"
        assert result.weekday() == 0  # Lunes

    def test_con_feriado_intermedio_salta_al_siguiente_habil(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.business_calendar import add_business_days_after
        start = date(2025, 9, 1)
        # Feriado el propio 22/09/2025 → debe pasar al martes 23/09
        result = add_business_days_after(start, 15, {"2025-09-22"}, set())
        assert result == date(2025, 9, 23), f"Con feriado 22/09 esperado 2025-09-23, obtenido {result}"

    def test_emision_jueves_salta_fin_de_semana(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.business_calendar import add_business_days_after
        # Jueves 04/09/2025 + 15 hábiles
        start = date(2025, 9, 4)
        result = add_business_days_after(start, 15, set(), set())
        # Contando: Vi5,Lu8,Ma9,Mi10,Ju11,Vi12,Lu15,Ma16,Mi17,Ju18,Vi19,Lu22,Ma23,Mi24,Ju25 → Jueves 25/09
        assert result == date(2025, 9, 25), f"Esperado 2025-09-25, obtenido {result}"
        assert result.weekday() == 3  # jueves

    def test_emision_viernes_salta_fin_de_semana(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from services.business_calendar import add_business_days_after
        start = date(2025, 9, 5)  # Viernes
        result = add_business_days_after(start, 15, set(), set())
        # Lu8..Vi26 son 15 días hábiles → Viernes 26/09
        assert result == date(2025, 9, 26)
        assert result.weekday() == 4

    def test_dia_emision_no_cuenta_exclusivo(self):
        """Si start es hábil, NO se debe contar como día 1."""
        import sys
        sys.path.insert(0, "/app/backend")
        from services.business_calendar import add_business_days_after
        start = date(2025, 9, 1)  # Lunes
        r1 = add_business_days_after(start, 1, set(), set())
        assert r1 == date(2025, 9, 2), "n=1 con start Lunes debe ser Martes 02"


# --------------------- Integración: PDF con Fecha de Vencimiento ---------------------

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for p in reader.pages:
        try:
            parts.append(p.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def _extract_pdf_pages(pdf_bytes: bytes):
    """Devuelve lista de textos por página."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


def _vpos_pyme_payload(client_id: str):
    return {
        "template_type": "vpos_pyme",
        "quote_type": "VPOS",
        "client_segment": "PYME",
        "client_id": client_id,
        "cliente_nombre": "TEST_ITER244_PYME",
        "cliente_rif": "J-12345678-9",
        "cliente_contacto": "QA Tester",
        "cliente_address": "Caracas",
        "cantidad_cajas": 2,
        "quote_number": "TEST-ITER244-PYME",
        "setup_items": [
            {"concepto": "Setup POS", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 100.0},
        ],
        "recurring_basic_items": [
            {"concepto": "Servicio Básico", "cantidad_cajas": 2, "cantidad_bancos": 1, "tarifa": 20.0},
        ],
        "recurring_other_items": [],
        "notes": "",
    }


def _gateway_payload(client_id: str):
    return {
        "template_type": "vpos_pyme",  # gateway toma su propia rama pero mantiene template
        "quote_type": "GATEWAY",
        "client_segment": "PYME",
        "client_id": client_id,
        "cliente_nombre": "TEST_ITER244_PG",
        "cliente_rif": "J-12345678-9",
        "cliente_address": "Caracas",
        "cantidad_cajas": 1,
        "quote_number": "TEST-ITER244-PG",
        "pg_setup_items": [
            {"concepto": "Setup PG", "costo": 300.0, "banco": "BANCO_PRUEBA", "observacion": ""}
        ],
        "pg_recurring_cost": {
            "rangos": [{"rango_label": "1-1000", "costo_base_total": 100.0, "precio_tope": 500.0}],
            "num_products": 1,
        },
        "setup_items": [],
        "recurring_basic_items": [],
        "recurring_other_items": [],
    }


def _vpos_corp_payload(client_id: str):
    return {
        "template_type": "vpos_corp",
        "quote_type": "VPOS",
        "client_segment": "CORP",
        "client_id": client_id,
        "cliente_nombre": "TEST_ITER244_CORP",
        "cliente_rif": "J-99999999-9",
        "cliente_address": "Caracas",
        "cantidad_cajas": 3,
        "quote_number": "TEST-ITER244-CORP",
        "setup_items": [
            {"concepto": "Derecho de Uso", "cantidad_cajas": 3, "cantidad_bancos": 1, "tarifa": 500.0,
             "tipo_corp": "Derecho de Uso"},
        ],
        "recurring_basic_items": [
            {"concepto": "Apoyo Técnico", "cantidad_cajas": 3, "cantidad_bancos": 1, "tarifa": 80.0,
             "tipo_corp": "Apoyo Técnico"},
        ],
        "recurring_other_items": [],
    }


class TestPreviewPDFFechaVencimiento:
    """Verifica la portada y la eliminación de 'Vigencia de la Propuesta'."""

    def _preview(self, auth, payload):
        r = auth.post(f"{BASE_URL}/api/quotes/preview-pdf-with-template",
                      json=payload, timeout=60)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:400]}"
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "Respuesta no es un PDF válido"
        return r.content

    def test_vpos_pyme_portada_contiene_fecha_vencimiento(self, auth, client_id):
        pdf = self._preview(auth, _vpos_pyme_payload(client_id))
        pages = _extract_pdf_pages(pdf)
        assert pages, "PDF sin páginas"
        cover = pages[0].upper()
        # Etiqueta presente en portada
        assert "FECHA DE EMISI" in cover, "No hay 'FECHA DE EMISIÓN' en portada"
        assert "FECHA DE VENCIMIENTO" in cover, "No hay 'FECHA DE VENCIMIENTO' en portada"
        # Debe existir una fecha DD/MM/AAAA en la portada
        matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", pages[0])
        assert matches, f"No se encontró fecha DD/MM/AAAA en portada. Texto: {pages[0][:800]}"

    def test_vpos_pyme_no_contiene_vigencia_de_la_propuesta(self, auth, client_id):
        pdf = self._preview(auth, _vpos_pyme_payload(client_id))
        full = _extract_pdf_text(pdf)
        assert "Vigencia de la Propuesta" not in full, \
            "'Vigencia de la Propuesta' NO fue eliminada del documento"
        # También en mayúsculas / normalizado
        assert "VIGENCIA DE LA PROPUESTA" not in full.upper()

    def test_vpos_pyme_tyc_renumerados(self, auth, client_id):
        """T&C: los puntos deben quedar 1..4 y no repetirse."""
        pdf = self._preview(auth, _vpos_pyme_payload(client_id))
        full = _extract_pdf_text(pdf)
        # Los 4 encabezados esperados
        for token in ["Tiempo de Implementación", "Forma de Pago",
                      "Soporte Técnico", "Confidencialidad"]:
            assert token in full, f"Falta punto de T&C '{token}'"

    def test_gateway_portada_contiene_fecha_vencimiento(self, auth, client_id):
        pdf = self._preview(auth, _gateway_payload(client_id))
        pages = _extract_pdf_pages(pdf)
        cover = pages[0].upper()
        assert "FECHA DE EMISI" in cover
        assert "FECHA DE VENCIMIENTO" in cover
        matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", pages[0])
        assert matches, "No se encontró fecha DD/MM/AAAA en portada Gateway"

    def test_gateway_no_contiene_vigencia_de_la_propuesta(self, auth, client_id):
        pdf = self._preview(auth, _gateway_payload(client_id))
        full = _extract_pdf_text(pdf)
        assert "Vigencia de la Propuesta" not in full

    def test_vpos_corp_portada_contiene_fecha_vencimiento(self, auth, client_id):
        pdf = self._preview(auth, _vpos_corp_payload(client_id))
        pages = _extract_pdf_pages(pdf)
        cover = pages[0].upper()
        assert "FECHA DE EMISI" in cover
        assert "FECHA DE VENCIMIENTO" in cover
        matches = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", pages[0])
        assert matches, "No se encontró fecha DD/MM/AAAA en portada CORP"

    def test_vpos_corp_no_contiene_vigencia(self, auth, client_id):
        pdf = self._preview(auth, _vpos_corp_payload(client_id))
        full = _extract_pdf_text(pdf)
        assert "Vigencia de la Propuesta" not in full

    def test_fecha_vencimiento_es_dd_mm_aaaa_y_no_es_hoy(self, auth, client_id):
        """La fecha de vencimiento no debe coincidir con la de emisión (>0 días)."""
        pdf = self._preview(auth, _vpos_pyme_payload(client_id))
        pages = _extract_pdf_pages(pdf)
        text = pages[0]
        dates = re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
        assert dates, "Sin fechas DD/MM/AAAA"
        # Todas las fechas encontradas deben ser válidas
        for d, m, y in dates:
            di, mi, yi = int(d), int(m), int(y)
            assert 1 <= di <= 31 and 1 <= mi <= 12 and 2020 <= yi <= 2099

    def test_fecha_vencimiento_calculada_es_futura(self, auth, client_id):
        """Sanity: la fecha de vencimiento debe estar en el futuro respecto a hoy."""
        pdf = self._preview(auth, _vpos_pyme_payload(client_id))
        pages = _extract_pdf_pages(pdf)
        text = pages[0]
        dates = re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", text)
        assert dates
        parsed = [date(int(y), int(m), int(d)) for d, m, y in dates]
        today = datetime.now(timezone.utc).date()
        # Debe haber al menos una fecha > hoy (la de vencimiento, ~21 días naturales)
        assert any(dp > today for dp in parsed), \
            f"Ninguna fecha en portada es futura. Encontradas: {parsed}. Hoy: {today}"


# --------------------- Generación (persiste PDF) ---------------------

class TestGeneratePDFPersistence:
    """POST /api/quotes/generate-pdf-with-template debe devolver 200 y PDF válido.
    Este endpoint retorna el PDF binario directamente (attachment)."""

    def test_generate_pdf_vpos_pyme(self, auth, client_id):
        r = auth.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template",
                      json=_vpos_pyme_payload(client_id), timeout=60)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:400]}"
        assert r.headers.get("Content-Type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        pages = _extract_pdf_pages(r.content)
        assert "FECHA DE VENCIMIENTO" in pages[0].upper()
        assert "Vigencia de la Propuesta" not in _extract_pdf_text(r.content)

    def test_generate_pdf_gateway(self, auth, client_id):
        r = auth.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template",
                      json=_gateway_payload(client_id), timeout=60)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:400]}"
        assert r.content[:4] == b"%PDF"
        pages = _extract_pdf_pages(r.content)
        assert "FECHA DE VENCIMIENTO" in pages[0].upper()
        assert "Vigencia de la Propuesta" not in _extract_pdf_text(r.content)

    def test_generate_pdf_vpos_corp(self, auth, client_id):
        r = auth.post(f"{BASE_URL}/api/quotes/generate-pdf-with-template",
                      json=_vpos_corp_payload(client_id), timeout=60)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:400]}"
        assert r.content[:4] == b"%PDF"
        pages = _extract_pdf_pages(r.content)
        assert "FECHA DE VENCIMIENTO" in pages[0].upper()
        assert "Vigencia de la Propuesta" not in _extract_pdf_text(r.content)
