"""
Iteration 250 — Bug Fix E2E: 'Instrucciones para el Implementador' rendering in Ficha Técnica PDF.

Cubre:
- Ruta B (Proyectos Directos): POST /api/direct-projects con implementation_instructions plain text,
  luego GET /api/projects/{id}/ficha-tecnica y verificación que el texto aparece.
- Ruta A (Cotizaciones): POST /api/quotes/{id}/send-to-implementation con HTML rich-text,
  luego descarga de la Ficha Técnica del proyecto resultante.
- Sanitización: caracteres especiales (< > & comillas), saltos de línea, viñetas — PDF válido.
- Regresión: proyectos SIN instrucciones -> PDF 200 sin sección.
"""
import io
import os
import re
import time
import pytest
import requests
from pypdf import PdfReader
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import asyncio

load_dotenv('/app/backend/.env')

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

ADMIN_EMAIL = 'rgonzalez@megasoft.com.ve'
ADMIN_PASSWORD = 'admin123'


# ---------------- Fixtures ----------------
@pytest.fixture(scope='module')
def admin_token():
    r = requests.post(f'{BASE_URL}/api/auth/login',
                      json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f'Login failed: {r.status_code} {r.text}'
    return r.json()['session_token']


@pytest.fixture(scope='module')
def api(admin_token):
    s = requests.Session()
    s.headers.update({'Authorization': f'Bearer {admin_token}',
                      'Content-Type': 'application/json'})
    return s


@pytest.fixture(scope='module')
def client_id():
    async def _get():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        cl = await db.clients.find_one({}, {'_id': 0, 'client_id': 1})
        return cl['client_id']
    return asyncio.get_event_loop().run_until_complete(_get())


# ---------------- Helpers ----------------
def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join((p.extract_text() or '') for p in reader.pages)


def _normalize(txt: str) -> str:
    # Normaliza espacios/quiebres para búsqueda robusta en el texto extraído por pypdf
    return re.sub(r'\s+', ' ', txt).strip()


def _create_direct_project(api, client_id, instructions, quote_type='GATEWAY',
                           label='TEST-ITER250'):
    payload = {
        'client_id': client_id,
        'economic_group': f'{label} Grupo',
        'fantasy_name': f'{label} Comercio',
        'quote_type': quote_type,
        'sede': 'PYME',
        'cantidad_cajas': 1,
        'sponsor_bank_id': None,
        'sponsor_bank_name': None,
        'integrator_name': None,
        'integrator_app_name': None,
        'pinpad_provider': 'client',
        'pinpad_bank': None,
        'includes_link_pago': False,
        'includes_tokenizador': False,
        'server_name': 'Multicomercio MSC',
        'communication_type': 'SSL',
        'is_multistore': False,
        'stores': [],
        'project_type': 'simple',
        'boxes_grid': [{'bank_name': 'Banco de Venezuela',
                        'product_name': 'Tarjeta de Crédito/Débito (PG)',
                        'quantity': 1}],
        'implementation_instructions': instructions,
        'attachments': [],
    }
    r = api.post(f'{BASE_URL}/api/direct-projects', json=payload, timeout=60)
    assert r.status_code in (200, 201), f'create direct-project fail: {r.status_code} {r.text[:500]}'
    data = r.json()
    return data


def _download_ficha(api, project_id):
    r = api.get(f'{BASE_URL}/api/projects/{project_id}/ficha-tecnica',
                timeout=60)
    assert r.status_code == 200, f'ficha-tecnica fail: {r.status_code} {r.text[:500]}'
    assert r.headers.get('content-type', '').startswith('application/pdf'), \
        f'content-type inesperado: {r.headers.get("content-type")}'
    assert r.content[:4] == b'%PDF', 'contenido no es PDF válido'
    return r.content


# ---------------- Tests ----------------
class TestRouteBDirectProjectInstructions:
    """Ruta B: Proyectos Directos con instrucciones en texto plano."""

    def test_direct_project_plain_instructions_render_in_pdf(self, api, client_id):
        instructions = 'Prueba QA Directa: Configurar credenciales en ambiente de sandbox'
        proj = _create_direct_project(api, client_id, instructions, label='TEST-ITER250-B1')
        project_id = proj.get('project_id')
        assert project_id, f'missing project_id: {proj}'

        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)

        # Verifica la sección
        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' in _normalize(text).upper(), \
            'Sección de instrucciones no encontrada en el PDF'
        # Verifica el contenido íntegro (ignorando espacios)
        assert 'Prueba QA Directa' in text and 'sandbox' in text, \
            f'Texto de instrucciones no aparece íntegro. Extracto: {text[:1500]}'


class TestSanitization:
    """Caracteres especiales, saltos de línea y viñetas no rompen el PDF."""

    def test_direct_project_plain_ampersand_and_newlines(self, api, client_id):
        """Plain-text sin patrones tipo tag: & + comillas + saltos de línea + viñetas."""
        instructions = (
            'Configurar TLS 1.2\n'
            'Requiere & confirmar credenciales con "operador"\n'
            '- Paso 1: descargar cert.pem\n'
            '- Paso 2: reiniciar servicio\n'
            'Notas & advertencias finales'
        )
        proj = _create_direct_project(api, client_id, instructions, label='TEST-ITER250-B2A')
        project_id = proj['project_id']

        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)

        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' in _normalize(text).upper()
        for frag in ['TLS 1.2', 'confirmar credenciales', '"operador"',
                     'Paso 1', 'Paso 2', 'cert.pem', 'reiniciar servicio',
                     'Notas', 'advertencias finales']:
            assert frag in text, f'Fragmento faltante: {frag!r}. Extracto: {text[:1500]}'
        # '&' se preserva (aunque escapado en PDF, al extraer se ve como '&')
        assert '&' in text, 'Ampersand no aparece en el PDF'

    def test_direct_project_plain_with_tag_like_content(self, api, client_id):
        """BUG probable: plain-text con '<algo>' es detectado como HTML por la
        heurística en implementation_pdf.py (regex <[a-zA-Z/][^>]*>) y el 'tag'
        se elimina. En Ruta B (textarea texto plano) esto NO debería ocurrir.
        """
        instructions = (
            'Configurar TLS 1.2 en <server>\n'
            'Reiniciar servicio (uso <admin>)\n'
            'Fin de instrucciones'
        )
        proj = _create_direct_project(api, client_id, instructions, label='TEST-ITER250-B2B')
        project_id = proj['project_id']

        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)

        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' in _normalize(text).upper()
        # Estos fragmentos SÍ deben aparecer aunque contengan '<' '>'
        assert '<server>' in text, (
            f'BUG: plain-text con "<server>" es tratado como HTML y stripped. '
            f'Extracto: {text[text.upper().find("INSTRUCCIONES"):][:400]!r}'
        )
        assert '<admin>' in text, (
            f'BUG: plain-text con "<admin>" es stripped. '
            f'Extracto: {text[text.upper().find("INSTRUCCIONES"):][:400]!r}'
        )

    def test_direct_project_html_like_from_editor(self, api, client_id):
        # Simula HTML rich-text (viñetas + bold + saltos) — Route A editor payload.
        instructions_html = (
            '<p>Servidor destino puerto 443, requiere <strong>TLS 1.2</strong></p>'
            '<ul>'
            '<li>Instalar certificado &amp; validar cadena</li>'
            '<li>Notificar a &lt;NOC&gt;</li>'
            '</ul>'
            '<p>Contacto: soporte&#64;empresa.com</p>'
        )
        proj = _create_direct_project(api, client_id, instructions_html,
                                      label='TEST-ITER250-B3')
        project_id = proj['project_id']
        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)

        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' in _normalize(text).upper()
        for frag in ['Servidor destino puerto 443', 'TLS 1.2',
                     'Instalar certificado', 'validar cadena',
                     'Notificar', 'NOC', 'Contacto']:
            assert frag in text, f'HTML fragment missing: {frag!r}. Extracto: {text[:1500]}'


class TestRegressionNoInstructions:
    """Proyectos SIN instrucciones no deben romper la generación del PDF."""

    def test_direct_project_no_instructions_pdf_ok(self, api, client_id):
        proj = _create_direct_project(api, client_id, None, label='TEST-ITER250-B4')
        project_id = proj['project_id']
        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)
        # No debe aparecer la sección
        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' not in _normalize(text).upper(), \
            'Sección de instrucciones no debería aparecer si no hay contenido'
        # Pero el PDF debe seguir siendo válido y contener el nombre del comercio
        assert 'TEST-ITER250-B4 Comercio' in text or 'TEST-ITER250-B4' in text, \
            'PDF no incluye datos básicos del proyecto'


class TestRouteAQuoteSendToImplementation:
    """Ruta A: Cotización → Enviar a Implementación con instrucciones HTML."""

    def test_send_paid_quote_with_html_instructions_and_verify_ficha(self, api):
        # Reseed quotes (idempotente)
        import subprocess
        subprocess.run(['python3', '/app/backend/tests/seed_iter248_test_quotes.py'],
                       check=True, timeout=30, capture_output=True)

        # Localizar quote GATEWAY seedada (Pagada)
        async def _find():
            c = AsyncIOMotorClient(MONGO_URL)
            db = c[DB_NAME]
            q = await db.quotes.find_one(
                {'quote_number': 'COT-TEST-ITER248-GW-001'}, {'_id': 0})
            return q
        quote = asyncio.get_event_loop().run_until_complete(_find())
        assert quote is not None, 'Seed quote GATEWAY no encontrada'
        quote_id = quote['quote_id']

        instructions_html = (
            '<p>Prueba QA: Servidor destino puerto <strong>443</strong>, requiere '
            '<em>TLS 1.2</em></p>'
            '<ul><li>Validar credenciales &amp; endpoint</li>'
            '<li>Notificar &lt;NOC&gt;</li></ul>'
        )
        body = {
            'project_type_impl': 'payment_gateway',
            'server_name': 'Multicomercio MSC',
            'economic_group': 'TEST-ITER250-A1 Grupo',
            'fantasy_name': 'TEST-ITER250-A1 Comercio',
            'implementation_instructions': instructions_html,
        }
        r = api.post(f'{BASE_URL}/api/quotes/{quote_id}/send-to-implementation',
                     json=body, timeout=60)
        assert r.status_code == 200, f'send-to-implementation fail: {r.status_code} {r.text[:600]}'
        data = r.json()

        # Localizar el proyecto creado por quote_id
        async def _find_project():
            c = AsyncIOMotorClient(MONGO_URL)
            db = c[DB_NAME]
            p = await db.projects.find_one({'quote_id': quote_id}, {'_id': 0})
            return p
        # Un pequeño delay por si la escritura es async
        time.sleep(1)
        project = asyncio.get_event_loop().run_until_complete(_find_project())
        assert project is not None, f'No se encontró proyecto para quote {quote_id}. Response: {data}'
        project_id = project['project_id']

        # Verifica persistencia en BD
        assert project.get('implementation_instructions'), \
            f'implementation_instructions no persistidas en proyecto: {project.get("implementation_instructions")!r}'

        pdf = _download_ficha(api, project_id)
        text = _pdf_text(pdf)
        assert 'INSTRUCCIONES ADICIONALES PARA EL IMPLEMENTADOR' in _normalize(text).upper()
        for frag in ['Prueba QA', 'Servidor destino puerto', '443',
                     'TLS 1.2', 'Validar credenciales', 'endpoint',
                     'Notificar', 'NOC']:
            assert frag in text, f'Fragmento HTML faltante: {frag!r}. Extracto: {text[:1500]}'


# ---------------- Cleanup ----------------
@pytest.fixture(scope='module', autouse=True)
def _cleanup():
    yield
    async def _cln():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        # Borrar proyectos y quotes de prueba
        pres = await db.projects.delete_many(
            {'economic_group': {'$regex': '^TEST-ITER250'}})
        qres = await db.quotes.delete_many(
            {'quote_number': {'$regex': 'TEST-ITER248'}})
        # También limpiar quotes en historic si aplica
        try:
            await db.quote_history.delete_many(
                {'quote_number': {'$regex': 'TEST-ITER248'}})
        except Exception:
            pass
        print(f'\nCleanup: projects={pres.deleted_count}, quotes={qres.deleted_count}')
    try:
        asyncio.get_event_loop().run_until_complete(_cln())
    except Exception as e:
        print('cleanup error:', e)
