"""
Iteration 235 - Ficha Técnica: Sección "C. COMPONENTES ADICIONALES"

Cobertura:
  A) Proyectos Directos GATEWAY: incluye_link_pago / incluye_tokenizador
     - POST /api/direct-projects -> project.additional_components persistido
     - GET  /api/projects/{id}/ficha-tecnica -> PDF con sección "C. COMPONENTES ADICIONALES"
       y corrimiento de "D. RESUMEN COMERCIAL" cuando aplica.
  B) Cotización unificada LINK_PAGO con link_pago_variant='ambos':
     - Insert de quote sintética en Mongo (para no depender del flujo completo Aprobar/Pagar).
     - POST /api/quotes/{qid}/send-to-implementation
     - Verifica que _create_project_from_quote deduce additional_components desde link_pago_variant.
     - Verifica que la Ficha Técnica del proyecto refleja AMBAS líneas en "Si" sin intervención manual.
  C) Ausencia de sección C cuando ambas respuestas son "No" (regression).
"""
import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient
from pypdf import PdfReader

def _read_frontend_env_backend_url() -> str:
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p, "r", encoding="utf-8"):
            line = line.strip()
            if line.startswith("REACT_APP_BACKEND_URL"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env_backend_url()).rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not defined"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------------- fixtures ----------------

@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    }, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def a_client(headers):
    r = requests.get(f"{BASE_URL}/api/clients?limit=5", headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data.get("clients") if isinstance(data, dict) else data
    assert items, "no clients available"
    return items[0]


@pytest.fixture(scope="module")
def pg_bank(headers):
    r = requests.get(f"{BASE_URL}/api/banks", headers=headers, timeout=30)
    assert r.status_code == 200
    banks = r.json() if isinstance(r.json(), list) else r.json().get("banks", [])
    for b in banks:
        for p in (b.get("products") or []):
            if p.get("gateway_available"):
                return {"bank_name": b["name"], "product_name": p["product_name"]}
    pytest.skip("no gateway product available")


@pytest.fixture(scope="module")
def gateway_integrator(headers):
    r = requests.get(f"{BASE_URL}/api/integrators?limit=50", headers=headers, timeout=30)
    assert r.status_code == 200
    lst = r.json() if isinstance(r.json(), list) else r.json().get("integrators", [])
    for it in lst:
        if (it.get("integration_type") or "").upper() == "PG":
            return it
    return lst[0] if lst else {}


# ---------------- helpers ----------------

def _pdf_text_from_bytes(b: bytes) -> str:
    reader = PdfReader(io.BytesIO(b))
    parts = []
    for pg in reader.pages:
        try:
            parts.append(pg.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts)


def _create_direct_gateway_project(headers, client, pg_bank, integrator,
                                   includes_link_pago: bool, includes_tokenizador: bool):
    payload = {
        "client_id": client["client_id"],
        "economic_group": "TEST_iter235",
        "fantasy_name": client.get("fantasy_name") or client.get("legal_name") or "",
        "quote_type": "GATEWAY",
        "sede": (client.get("client_segment") or "PYME").upper(),
        "cantidad_cajas": 1,
        "sponsor_bank_id": None,
        "sponsor_bank_name": None,
        "integrator_id": integrator.get("integrator_id"),
        "integrator_name": integrator.get("name"),
        "integrator_app_name": integrator.get("app_name"),
        "includes_link_pago": includes_link_pago,
        "includes_tokenizador": includes_tokenizador,
        "is_multistore": False,
        "stores": [],
        "project_type": "simple",
        "shared_matrix": True,
        "multirif_distribution": [],
        "boxes_grid": [
            {"bank_name": pg_bank["bank_name"], "product_name": pg_bank["product_name"], "quantity": 1}
        ],
        "implementation_instructions": "TEST_iter235 auto",
    }
    r = requests.post(f"{BASE_URL}/api/direct-projects", headers=headers, json=payload, timeout=60)
    return r


# ---------------- TESTS: PROYECTOS DIRECTOS ----------------

class TestDirectProjectsGatewayComponents:
    """A: sección C via includes_link_pago / includes_tokenizador."""

    def test_create_gateway_link_pago_si_tokenizador_no(
        self, headers, a_client, pg_bank, gateway_integrator, mongo_db
    ):
        r = _create_direct_gateway_project(headers, a_client, pg_bank, gateway_integrator,
                                           includes_link_pago=True, includes_tokenizador=False)
        assert r.status_code in (200, 201), f"create direct project failed: {r.status_code} {r.text}"
        data = r.json()
        pid = data.get("project_id") or data.get("project", {}).get("project_id")
        assert pid, f"no project_id in response: {data}"

        # DB assertion: additional_components persistido
        proj = mongo_db.projects.find_one({"project_id": pid}, {"_id": 0})
        assert proj is not None
        ac = proj.get("additional_components") or {}
        assert ac.get("link_pago") is True
        assert ac.get("tokenizador") is False

        # PDF assertion: sección C + corrimiento a D. RESUMEN COMERCIAL
        pdf_r = requests.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica",
                             headers={"Authorization": headers["Authorization"]}, timeout=60)
        assert pdf_r.status_code == 200, f"ficha-tecnica failed: {pdf_r.status_code}"
        assert pdf_r.headers.get("content-type", "").lower().startswith("application/pdf")
        text = _pdf_text_from_bytes(pdf_r.content)

        assert "COMPONENTES ADICIONALES" in text, f"no section C. Text sample:\n{text[:2000]}"
        assert "C. COMPONENTES ADICIONALES" in text or "C.COMPONENTES ADICIONALES" in text.replace(" ", "") or "C.  COMPONENTES ADICIONALES" in text
        # respuestas específicas
        assert "Link de Pago" in text
        assert "Tokenizador" in text
        # corrimiento de letra
        assert "D. RESUMEN COMERCIAL" in text or "D.RESUMEN COMERCIAL" in text.replace(" ", "")

        # cleanup
        mongo_db.projects.delete_one({"project_id": pid})

    def test_create_gateway_both_no_omits_section_c(
        self, headers, a_client, pg_bank, gateway_integrator, mongo_db
    ):
        r = _create_direct_gateway_project(headers, a_client, pg_bank, gateway_integrator,
                                           includes_link_pago=False, includes_tokenizador=False)
        assert r.status_code in (200, 201), f"create direct project failed: {r.status_code} {r.text}"
        data = r.json()
        pid = data.get("project_id") or data.get("project", {}).get("project_id")
        assert pid

        # PDF assertion: sin sección C, y RESUMEN COMERCIAL debe seguir siendo 'C.'
        pdf_r = requests.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica",
                             headers={"Authorization": headers["Authorization"]}, timeout=60)
        assert pdf_r.status_code == 200
        text = _pdf_text_from_bytes(pdf_r.content)
        assert "COMPONENTES ADICIONALES" not in text, "section C should be omitted when both are No"
        # Cuando no hay sección C, RESUMEN COMERCIAL usa la letra 'C.' (o la siguiente si hay Seriales)
        # Basta con verificar que no aparece D. RESUMEN COMERCIAL (letra corrida).
        assert "D. RESUMEN COMERCIAL" not in text

        mongo_db.projects.delete_one({"project_id": pid})


# ---------------- TESTS: COTIZACIÓN UNIFICADA LINK_PAGO / TOKENIZADOR ----------------

class TestUnifiedQuoteLinkPagoDeduction:
    """B: additional_components deducidos desde link_pago_variant en send-to-implementation."""

    @pytest.fixture(scope="class")
    def paid_link_pago_quote_ambos(self, mongo_db, a_client):
        """Inserta directamente una cotización LINK_PAGO en estado Pagada con link_pago_variant='ambos'.
        Esto permite invocar send-to-implementation sin recorrer todo el pipeline Aprobar/Facturar/Pagar.
        """
        qid = f"quo_test235_{uuid.uuid4().hex[:8]}"
        qnumber = f"TEST-235-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "quote_id": qid,
            "quote_number": qnumber,
            "client_id": a_client["client_id"],
            "client_name": a_client.get("fantasy_name") or a_client.get("legal_name"),
            "client_rif": a_client.get("rif"),
            "client_segment": "PYME",
            "sede": "PYME",
            "quote_type": "LINK_PAGO",
            "quote_category": "quote",
            "quote_status": "Pagada",
            "link_pago_variant": "ambos",
            "services": [],
            "pg_setup_items": [],
            "hardware": [],
            "equipment_items": [],
            "branch_details": [],
            "sponsor_bank_id": None,
            "sponsor_bank_name": None,
            "integrator_name": "TEST Integrator",
            "cantidad_cajas": 1,
            "economic_group": "TEST_iter235",
            "fantasy_name": a_client.get("fantasy_name") or a_client.get("legal_name"),
            "total_usd": 0,
            "total_bs": 0,
            "iva_exempt": False,
            "created_at": now,
            "created_by_user_id": "user_admin_main",
            "is_irregular": False,
            "irregular_exceptions": [],
            "attachments": [],
            "pinpad_serials": [],
            "equipments": [],
        }
        mongo_db.quotes.insert_one(doc)
        yield qid
        # cleanup
        proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0, "project_id": 1})
        if proj:
            mongo_db.projects.delete_one({"project_id": proj["project_id"]})
        mongo_db.quotes.delete_one({"quote_id": qid})

    def test_send_to_implementation_ambos_creates_project_with_both_components(
        self, headers, mongo_db, paid_link_pago_quote_ambos
    ):
        qid = paid_link_pago_quote_ambos
        # send-to-implementation
        body = {"is_multistore": False, "stores": [], "server_name": "Multicomercio MSC",
                "economic_group": "TEST_iter235", "fantasy_name": "TEST"}
        r = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
            headers=headers, json=body, timeout=90,
        )
        assert r.status_code in (200, 201), f"send-to-implementation failed: {r.status_code} {r.text[:500]}"

        # Verificar proyecto creado con additional_components deducido
        proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
        assert proj is not None, "project not created"
        ac = proj.get("additional_components") or {}
        assert ac.get("link_pago") is True, f"link_pago should be True, got {ac}"
        assert ac.get("tokenizador") is True, f"tokenizador should be True, got {ac}"

        pid = proj["project_id"]

        # Ficha Técnica debe contener sección C con ambas líneas 'Si'
        pdf_r = requests.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica",
                             headers={"Authorization": headers["Authorization"]}, timeout=60)
        assert pdf_r.status_code == 200
        text = _pdf_text_from_bytes(pdf_r.content)
        assert "COMPONENTES ADICIONALES" in text
        # Debe haber 2 respuestas 'Si' en la sección C (link_pago + tokenizador)
        # Buscamos las líneas literales
        assert "Link de Pago" in text
        assert "Tokenizador" in text
        # No debe aparecer "Link de Pago" seguido de "No"
        # (aserción indirecta) verificamos que el orden y que hay al menos dos 'Si' cerca de la sección
        # Contar Si en el bloque
        idx = text.find("COMPONENTES ADICIONALES")
        block = text[idx: idx + 400]
        # Case-insensitive "si" en respuestas
        si_count = block.count("Si")
        no_count = block.count("No")
        assert si_count >= 2, f"esperado 2 respuestas 'Si', block:\n{block}"

    def test_link_pago_variant_link_pago_only(self, headers, mongo_db, a_client):
        """Ruta 'link_pago' -> LDP Si / Tok No"""
        qid = f"quo_test235b_{uuid.uuid4().hex[:8]}"
        mongo_db.quotes.insert_one({
            "quote_id": qid,
            "quote_number": f"TEST-235B-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            "client_id": a_client["client_id"],
            "client_name": a_client.get("fantasy_name") or a_client.get("legal_name"),
            "client_rif": a_client.get("rif"),
            "client_segment": "PYME", "sede": "PYME",
            "quote_type": "LINK_PAGO", "quote_category": "quote",
            "quote_status": "Pagada", "link_pago_variant": "link_pago",
            "services": [], "pg_setup_items": [], "hardware": [], "equipment_items": [],
            "branch_details": [], "sponsor_bank_id": None, "sponsor_bank_name": None,
            "integrator_name": "TEST", "cantidad_cajas": 1,
            "economic_group": "TEST_iter235", "fantasy_name": "TEST",
            "total_usd": 0, "total_bs": 0, "iva_exempt": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by_user_id": "user_admin_main",
            "is_irregular": False, "irregular_exceptions": [], "attachments": [],
            "pinpad_serials": [], "equipments": [],
        })
        try:
            r = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
                headers=headers, json={"is_multistore": False, "stores": [], "server_name": "Multicomercio MSC"},
                timeout=90,
            )
            assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None
            ac = proj.get("additional_components") or {}
            assert ac.get("link_pago") is True
            assert ac.get("tokenizador") is False
        finally:
            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0, "project_id": 1})
            if proj:
                mongo_db.projects.delete_one({"project_id": proj["project_id"]})
            mongo_db.quotes.delete_one({"quote_id": qid})

    def test_link_pago_variant_tokenizador_only(self, headers, mongo_db, a_client):
        """Ruta 'tokenizador' -> LDP No / Tok Si"""
        qid = f"quo_test235c_{uuid.uuid4().hex[:8]}"
        mongo_db.quotes.insert_one({
            "quote_id": qid,
            "quote_number": f"TEST-235C-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            "client_id": a_client["client_id"],
            "client_name": a_client.get("fantasy_name") or a_client.get("legal_name"),
            "client_rif": a_client.get("rif"),
            "client_segment": "PYME", "sede": "PYME",
            "quote_type": "LINK_PAGO", "quote_category": "quote",
            "quote_status": "Pagada", "link_pago_variant": "tokenizador",
            "services": [], "pg_setup_items": [], "hardware": [], "equipment_items": [],
            "branch_details": [], "sponsor_bank_id": None, "sponsor_bank_name": None,
            "integrator_name": "TEST", "cantidad_cajas": 1,
            "economic_group": "TEST_iter235", "fantasy_name": "TEST",
            "total_usd": 0, "total_bs": 0, "iva_exempt": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by_user_id": "user_admin_main",
            "is_irregular": False, "irregular_exceptions": [], "attachments": [],
            "pinpad_serials": [], "equipments": [],
        })
        try:
            r = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
                headers=headers, json={"is_multistore": False, "stores": [], "server_name": "Multicomercio MSC"},
                timeout=90,
            )
            assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None
            ac = proj.get("additional_components") or {}
            assert ac.get("link_pago") is False
            assert ac.get("tokenizador") is True
        finally:
            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0, "project_id": 1})
            if proj:
                mongo_db.projects.delete_one({"project_id": proj["project_id"]})
            mongo_db.quotes.delete_one({"quote_id": qid})
