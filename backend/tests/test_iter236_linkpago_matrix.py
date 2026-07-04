"""
Iteration 236 - BUG FIX: implementation_matrix vacía para cotización LINK_PAGO
al enviar a implementación.

RCA: en `routes/quote_transitions.py::_create_project_from_quote`, la variable
`is_gateway` solo detectaba quote_type=='GATEWAY'. Para LINK_PAGO la matriz se
construía desde `services` (vacío en PG) en vez de `pg_setup_items`.

FIX (L106): is_gateway ahora es True para ('GATEWAY','LINK_PAGO').

Cobertura:
  A) LINK_PAGO con pg_setup_items que incluyen 2 items con banco válido
     (Banesco + otro) y 1 item con banco 'N/A' (Persona Jurídica):
     - send-to-implementation -> project.implementation_matrix POBLADA con
       los bancos válidos, ignorando 'N/A'.
     - Cada entrada banco+concepto contiene las 4 fases (Recibido, Configurado,
       Testeado, En Producción) con expected=1, processed=0, completed=False.
  B) REGRESIÓN GATEWAY: misma estructura de pg_setup_items con quote_type=
     'GATEWAY' produce la misma matriz.
  C) COHERENCIA FICHA vs MATRIZ (LINK_PAGO): bancos y conceptos en
     implementation_matrix coinciden con los mostrados en la Ficha Técnica
     PDF del proyecto.
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


def _build_quote_doc(client, quote_type: str, link_pago_variant: str | None):
    """Construye un doc de cotización Pagada con pg_setup_items típicos.

    pg_setup_items:
      - "Persona Jurídica" con banco 'N/A' (item conceptual fijo — debe ignorarse en matriz)
      - "Setup Banesco" con banco 'Banesco'
      - "Setup BDV" con banco 'Banco de Venezuela'
    """
    qid = f"quo_test236_{uuid.uuid4().hex[:8]}"
    qnumber = f"TEST-236-{quote_type[:2]}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "quote_id": qid,
        "quote_number": qnumber,
        "client_id": client["client_id"],
        "client_name": client.get("fantasy_name") or client.get("legal_name"),
        "client_rif": client.get("rif"),
        "client_segment": "PYME",
        "sede": "PYME",
        "quote_type": quote_type,
        "quote_category": "quote",
        "quote_status": "Pagada",
        "services": [],
        "pg_setup_items": [
            {
                "concepto": "Persona Jurídica",
                "banco": "N/A",
                "costo": 100.0,
                "observacion": "Item conceptual fijo (no va a matriz)",
            },
            {
                "concepto": "Setup Banesco",
                "banco": "Banesco",
                "costo": 200.0,
                "observacion": "TEST 236 banco valido A",
            },
            {
                "concepto": "Setup BDV",
                "banco": "Banco de Venezuela",
                "costo": 200.0,
                "observacion": "TEST 236 banco valido B",
            },
        ],
        "hardware": [],
        "equipment_items": [],
        "branch_details": [],
        "sponsor_bank_id": None,
        "sponsor_bank_name": None,
        "integrator_name": "TEST Integrator 236",
        "cantidad_cajas": 1,
        "economic_group": "TEST_iter236",
        "fantasy_name": client.get("fantasy_name") or client.get("legal_name") or "TEST",
        "total_usd": 500.0,
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
    if link_pago_variant is not None:
        doc["link_pago_variant"] = link_pago_variant
    return qid, doc


def _assert_matrix_shape(matrix: dict, expected_banks: set[str], expected_concepts_by_bank: dict[str, set[str]]):
    """Valida estructura de implementation_matrix.

    - claves de nivel 1 = bancos esperados EXACTAMENTE (no debe estar 'N/A')
    - por banco, claves = conceptos esperados
    - por concepto, cada fase (Recibido/Configurado/Testeado/En Producción) tiene {expected:1, processed:0, completed:False}
    """
    assert matrix, f"implementation_matrix vacía: {matrix}"
    assert set(matrix.keys()) == expected_banks, (
        f"bancos en matriz {set(matrix.keys())} != esperados {expected_banks}"
    )
    for bank, concepts in expected_concepts_by_bank.items():
        assert set(matrix[bank].keys()) == concepts, (
            f"conceptos en {bank}: {set(matrix[bank].keys())} != {concepts}"
        )
        for concept, phases in matrix[bank].items():
            for phase in ("Recibido", "Configurado", "Testeado", "En Producción"):
                assert phase in phases, f"falta fase '{phase}' en {bank}/{concept}: {phases}"
                p = phases[phase]
                assert p.get("expected") == 1, f"{bank}/{concept}/{phase}.expected != 1: {p}"
                assert p.get("processed") == 0, f"{bank}/{concept}/{phase}.processed != 0: {p}"
                assert p.get("completed") is False, f"{bank}/{concept}/{phase}.completed != False: {p}"


# ---------------- TESTS ----------------

class TestImplementationMatrixLinkPago:
    """A: LINK_PAGO debe construir matriz desde pg_setup_items (fix del bug)."""

    def _cleanup(self, mongo_db, qid):
        proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0, "project_id": 1})
        if proj:
            mongo_db.projects.delete_one({"project_id": proj["project_id"]})
        mongo_db.quotes.delete_one({"quote_id": qid})
        # También limpiar historial si el archivo se creó
        try:
            mongo_db.quotes_history.delete_many({"quote_id": qid})
        except Exception:
            pass

    def test_link_pago_populates_matrix_ignoring_na(self, headers, mongo_db, a_client):
        qid, doc = _build_quote_doc(a_client, "LINK_PAGO", "ambos")
        mongo_db.quotes.insert_one(doc)
        try:
            body = {
                "is_multistore": False, "stores": [],
                "server_name": "Multicomercio MSC",
                "economic_group": "TEST_iter236",
                "fantasy_name": "TEST 236",
            }
            r = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
                headers=headers, json=body, timeout=90,
            )
            assert r.status_code in (200, 201), (
                f"send-to-implementation LINK_PAGO fallo: {r.status_code} {r.text[:500]}"
            )

            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None, "proyecto no creado desde LINK_PAGO"

            # BANKS: N/A debe ser ignorado
            bank_names = {b.get("bank_name") for b in (proj.get("banks") or [])}
            assert "N/A" not in bank_names, f"banks incluye 'N/A': {bank_names}"
            assert "Banesco" in bank_names, f"falta Banesco en banks: {bank_names}"
            assert "Banco de Venezuela" in bank_names, f"falta BDV en banks: {bank_names}"

            # MATRIZ: shape correcta
            matrix = proj.get("implementation_matrix") or {}
            _assert_matrix_shape(
                matrix,
                expected_banks={"Banesco", "Banco de Venezuela"},
                expected_concepts_by_bank={
                    "Banesco": {"Setup Banesco"},
                    "Banco de Venezuela": {"Setup BDV"},
                },
            )
        finally:
            self._cleanup(mongo_db, qid)

    def test_gateway_regression_matrix_still_populated(self, headers, mongo_db, a_client):
        """Cotización GATEWAY con la misma estructura debe producir matriz idéntica."""
        qid, doc = _build_quote_doc(a_client, "GATEWAY", None)
        mongo_db.quotes.insert_one(doc)
        try:
            body = {
                "is_multistore": False, "stores": [],
                "server_name": "Multicomercio MSC",
                "economic_group": "TEST_iter236",
                "fantasy_name": "TEST 236 GW",
            }
            r = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
                headers=headers, json=body, timeout=90,
            )
            assert r.status_code in (200, 201), (
                f"send-to-implementation GATEWAY fallo: {r.status_code} {r.text[:500]}"
            )
            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None, "proyecto no creado desde GATEWAY"

            bank_names = {b.get("bank_name") for b in (proj.get("banks") or [])}
            assert "N/A" not in bank_names
            assert "Banesco" in bank_names
            assert "Banco de Venezuela" in bank_names

            matrix = proj.get("implementation_matrix") or {}
            _assert_matrix_shape(
                matrix,
                expected_banks={"Banesco", "Banco de Venezuela"},
                expected_concepts_by_bank={
                    "Banesco": {"Setup Banesco"},
                    "Banco de Venezuela": {"Setup BDV"},
                },
            )
        finally:
            self._cleanup(mongo_db, qid)

    def test_ficha_tecnica_coherent_with_matrix_linkpago(self, headers, mongo_db, a_client):
        """La Ficha Técnica del proyecto debe listar los mismos bancos/conceptos
        que están en implementation_matrix (banco válido)."""
        qid, doc = _build_quote_doc(a_client, "LINK_PAGO", "ambos")
        mongo_db.quotes.insert_one(doc)
        try:
            body = {
                "is_multistore": False, "stores": [],
                "server_name": "Multicomercio MSC",
                "economic_group": "TEST_iter236",
                "fantasy_name": "TEST 236 FT",
            }
            r = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
                headers=headers, json=body, timeout=90,
            )
            assert r.status_code in (200, 201), r.text[:400]

            proj = mongo_db.projects.find_one({"quote_id": qid}, {"_id": 0})
            assert proj is not None
            pid = proj["project_id"]
            matrix_banks = set((proj.get("implementation_matrix") or {}).keys())

            pdf_r = requests.get(
                f"{BASE_URL}/api/projects/{pid}/ficha-tecnica",
                headers={"Authorization": headers["Authorization"]},
                timeout=60,
            )
            assert pdf_r.status_code == 200
            text = _pdf_text_from_bytes(pdf_r.content)

            # Cada banco de la matriz debe aparecer en la Ficha Técnica
            for b in matrix_banks:
                assert b in text, f"banco '{b}' de la matriz no encontrado en Ficha Técnica"
            # Los conceptos válidos también
            assert "Setup Banesco" in text
            assert "Setup BDV" in text
            # Persona Jurídica sí aparece en Ficha (es item conceptual visible) pero NO como banco en matriz
            # Aserción ya cubierta en test previo (N/A ausente en matrix keys).
        finally:
            self._cleanup(mongo_db, qid)
