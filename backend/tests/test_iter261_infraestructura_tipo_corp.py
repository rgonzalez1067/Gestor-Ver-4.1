"""
Iter261 — Validación del concepto 'Infraestructura' en Tipo Corp:
1. Catálogo Medios de Pago (/api/services):
   - Crear un servicio con tipo_corp='Infraestructura' y verificar persistencia.
   - Confirmar que /api/services devuelve el registro con tipo_corp correcto.
   - Cleanup: DELETE del servicio TEST_ creado.
2. PDF CORP (VPOS) via POST /api/quotes/preview-pdf-with-template:
   - Con client_segment='CORP' y items con tipo_corp='Infraestructura',
     el PDF debe incluir el string 'Infraestructura' (columna nueva) en la
     tabla de COSTOS DE IMPLEMENTACIÓN (Página 3).
3. PDF PYME (regresión) via POST /api/quotes/preview-pdf-with-template:
   - Con client_segment='PYME' el PDF NO debe incluir el string
     'Infraestructura' (formato tradicional intacto).
"""
import os
import re
import io
import uuid
import requests
import pytest

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://inbox-fixes.preview.emergentagent.com",
).rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
CLIENT_ID = "cli_d7a6037a7cf7"  # ASTROCEL CELULARES


# ------------------------- fixtures -------------------------

@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    tk = body.get("token") or body.get("access_token") or body.get("session_token")
    assert tk, f"No token in response: {body}"
    return tk


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ------------------------- 1) Catálogo -------------------------

class TestServiceTipoCorpInfraestructura:
    """Validaciones del catálogo /api/services para tipo_corp='Infraestructura'."""

    created_service_id = None

    def test_create_service_with_infraestructura(self, headers):
        payload = {
            "name": f"TEST_Infra_{uuid.uuid4().hex[:8]}",
            "abreviatura": "TSTINF",
            "service_type": "Servicio",
            "tipo_corp": "Infraestructura",
            "application_type": "both",
            "category": "General",
            "vpos_enabled": True,
            "gateway_enabled": False,
            "mpos_enabled": False,
            "link_enabled": False,
            "setup_cost_conventional": 25.5,
            "monthly_cost_conventional": 10.0,
            "setup_cost_outsourcing": 30.0,
            "monthly_cost_outsourcing": 12.0,
            "description": "Servicio de prueba iter261 tipo_corp Infraestructura",
        }
        r = requests.post(f"{BASE_URL}/api/services", json=payload, headers=headers, timeout=30)
        assert r.status_code in (200, 201), f"Create failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("tipo_corp") == "Infraestructura", (
            f"tipo_corp no persistió al crear: {body.get('tipo_corp')}"
        )
        assert body.get("service_id"), "service_id no fue devuelto tras crear"
        TestServiceTipoCorpInfraestructura.created_service_id = body["service_id"]

    def test_get_service_persists_tipo_corp(self, headers):
        sid = TestServiceTipoCorpInfraestructura.created_service_id
        assert sid, "No hay service_id de creación previa"
        r = requests.get(f"{BASE_URL}/api/services", headers=headers, timeout=30)
        assert r.status_code == 200, f"GET /services falló: {r.status_code} {r.text}"
        rows = r.json()
        found = next((s for s in rows if s.get("service_id") == sid), None)
        assert found is not None, f"Servicio recién creado no aparece en /services"
        assert found.get("tipo_corp") == "Infraestructura", (
            f"tipo_corp del GET no es 'Infraestructura': {found.get('tipo_corp')}"
        )

    def test_zzz_cleanup_delete_service(self, headers):
        sid = TestServiceTipoCorpInfraestructura.created_service_id
        if not sid:
            pytest.skip("Nada que borrar")
        r = requests.delete(f"{BASE_URL}/api/services/{sid}", headers=headers, timeout=30)
        assert r.status_code in (200, 204), (
            f"DELETE /services/{sid} falló: {r.status_code} {r.text}"
        )


# ------------------------- 2) PDF CORP tiene columna Infraestructura -------------------------

def _pdf_preview_payload(segment: str) -> dict:
    """Payload mínimo para preview-pdf-with-template.
    Se incluyen items setup y recurrentes con tipo_corp='Infraestructura'
    para poder ver el efecto en la matriz CORP.
    """
    return {
        "template_type": "vpos_corp" if segment == "CORP" else "vpos_pyme",
        "client_id": CLIENT_ID,
        "cliente_nombre": "ASTROCEL CELULARES, C.A.",
        "cliente_rif": "J-00000000-0",
        "cliente_contacto": "Contacto Test",
        "cliente_address": "Caracas",
        "integrator_name": "Integrator Test",
        "integrator_app_name": "AppTest",
        "pinpad_model": "P200",
        "sponsor_bank_name": "Banco Test",
        "cantidad_cajas": 1,
        "quote_number": f"TEST-INF-{segment}",
        "fecha_vencimiento": "31/12/2026",
        "setup_items": [
            {"concepto": "Setup DdU", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 42.0, "total": 42.0, "tipo_corp": "Derecho de Uso"},
            {"concepto": "Setup Infra", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 25.5, "total": 25.5, "tipo_corp": "Infraestructura"},
        ],
        "recurring_basic_items": [
            {"concepto": "Recurrente Infra", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 10.0, "total": 10.0, "tipo_corp": "Infraestructura"},
            {"concepto": "Recurrente Soporte", "cantidad_cajas": 1, "cantidad_bancos": 1,
             "tarifa": 22.58, "total": 22.58, "tipo_corp": "Soporte y Monitoreo"},
        ],
        "recurring_other_items": [],
        "additional_items": [],
        "production_items": [],
        "pg_setup_items": [],
        "pricing_model": "conventional",
        "quote_type": "VPOS_MPOS",
        "client_segment": segment,
        "iva_exempt": False,
        "descuento": 0,
        "descuento_setup": 0,
        "descuento_recurrente": 0,
    }


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extrae texto plano de un PDF y colapsa espacios/saltos en un solo espacio.
    Los PDFs generados con ReportLab suelen partir cabeceras multilínea
    ('Hardware y\\nSoftware'), por lo que normalizamos whitespace para poder
    hacer asserts robustas del tipo `'Hardware y Software' in text`.
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        from PyPDF2 import PdfReader  # type: ignore
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for p in reader.pages:
        try:
            parts.append(p.extract_text() or "")
        except Exception:
            parts.append("")
    raw = "\n".join(parts)
    # Colapsa cualquier secuencia de whitespace a un solo espacio
    return re.sub(r"\s+", " ", raw)


class TestPdfInfraestructuraColumn:
    """Verifica que el PDF CORP muestra 'Infraestructura' y el PYME NO."""

    def test_pdf_corp_contains_infraestructura(self, headers):
        payload = _pdf_preview_payload("CORP")
        r = requests.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            json=payload,
            headers=headers,
            timeout=60,
        )
        assert r.status_code == 200, f"preview CORP falló: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), (
            f"content-type inesperado CORP: {r.headers.get('content-type')}"
        )
        text = _pdf_text(r.content)
        assert "Infraestructura" in text, (
            "El PDF CORP NO contiene 'Infraestructura' (esperado columna nueva). "
            f"Primeros 500 chars: {text[:500]!r}"
        )
        # También esperamos los otros títulos de la matriz CORP
        assert "Derecho de Uso" in text, "PDF CORP debe contener 'Derecho de Uso'"
        assert "Hardware y Software" in text, "PDF CORP debe contener supercabecera 'Hardware y Software'"

    def test_pdf_pyme_does_not_contain_infraestructura(self, headers):
        payload = _pdf_preview_payload("PYME")
        # PYME estándar NO debería producir la matriz por tipo_corp. Aún así,
        # metemos los items con tipo_corp para verificar que la columna NO
        # aparece en el PDF PYME (regresión).
        r = requests.post(
            f"{BASE_URL}/api/quotes/preview-pdf-with-template",
            json=payload,
            headers=headers,
            timeout=60,
        )
        assert r.status_code == 200, f"preview PYME falló: {r.status_code} {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), (
            f"content-type inesperado PYME: {r.headers.get('content-type')}"
        )
        text = _pdf_text(r.content)
        # Aviso: si un concepto se llama literalmente 'Infra' o 'Infraestructura' podría
        # aparecer como concepto del item. Buscamos específicamente la columna cabecera:
        # 'Hardware y Software' con subdivisión 'Infraestructura' (formato CORP).
        # Regla estricta: no debe aparecer la palabra 'Infraestructura' como cabecera.
        # Aquí verificamos ausencia general: si tu item se llama 'Setup Infra' está bien.
        header_infra_pattern = re.compile(r"Infraestructura", re.IGNORECASE)
        occurrences = header_infra_pattern.findall(text)
        # En PYME, ningún ítem/columna incluye 'Infraestructura' salvo si un concepto
        # literal lo tuviera. Nuestros conceptos PYME son 'Setup Infra' y 'Recurrente Infra',
        # así que 'Infraestructura' no debe aparecer.
        assert not occurrences, (
            f"PDF PYME NO debe contener 'Infraestructura' pero apareció {len(occurrences)} vez(veces). "
            f"Primeros 500 chars: {text[:500]!r}"
        )
