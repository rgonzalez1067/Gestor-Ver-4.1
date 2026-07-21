"""Iter287 · Fase 2 Taller: Trazabilidad Recibido→Cotizado→En reparación (linked)
   y fallback legacy (repair_models sin linked → crear En reparación al aprobar).

   Tests:
   1. GET /taller/equipos-disponibles → sólo Recibido de un cliente.
   2. Flow LINKED: recepcion→cotización→enviar→aprobar sin duplicar equipos.
   3. Flow LEGACY fallback: repair_models sin linked → aprobar crea En reparación.
"""
import os
import time
import uuid
import json
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
CLIENT_ID = "cli_00bbd8a3c108"  # Prueba (RIF J0009273)
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

TS = int(time.time())
SERIAL_A = f"QATEST-{TS}-A"
SERIAL_B = f"QATEST-{TS}-B"
SERIAL_LEGACY_1 = f"QATEST-{TS}-LEG1"
SERIAL_LEGACY_2 = f"QATEST-{TS}-LEG2"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    }, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def db():
    """Direct Mongo access via pymongo (sync)."""
    from pymongo import MongoClient
    client = MongoClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]
    yield d
    # cleanup
    d.taller_equipos.delete_many({"serial": {"$regex": f"^QATEST-{TS}-"}})
    d.quotes.delete_many({"client_id": CLIENT_ID, "notes": {"$regex": "QA (linked|legacy) flow"}})
    client.close()


def _count_taller(d, client_id):
    return d.taller_equipos.count_documents({"client_id": client_id})


def _find_taller(d, serial):
    return d.taller_equipos.find_one({"serial": serial}, {"_id": 0})


# ============ Test 1: GET equipos-disponibles ============
class TestEquiposDisponibles:
    def test_recepcion_and_available_list(self, hdr, db):
        # Crear equipos recibidos
        payload = {
            "client_id": CLIENT_ID,
            "models": [{
                "model_id": "",
                "model_name": "PinpadQA",
                "serials": [SERIAL_A, SERIAL_B],
            }]
        }
        r = requests.post(f"{BASE_URL}/taller/recepcion", json=payload, headers=hdr, timeout=60)
        assert r.status_code == 200, f"recepcion failed: {r.text}"
        assert r.json().get("created") == 2

        # GET disponibles
        r2 = requests.get(f"{BASE_URL}/taller/equipos-disponibles?client_id={CLIENT_ID}", headers=hdr, timeout=30)
        assert r2.status_code == 200
        data = r2.json()
        assert "equipos" in data and "total" in data
        serials = [e.get("serial") for e in data["equipos"]]
        assert SERIAL_A in serials, f"SERIAL_A missing: {serials}"
        assert SERIAL_B in serials
        # Field shape check
        one = next(e for e in data["equipos"] if e.get("serial") == SERIAL_A)
        assert "taller_equipo_id" in one
        assert "modelo" in one
        assert "fecha_ingreso" in one

    def test_available_filters_only_recibido(self, hdr, db):
        # Create a taller doc manually with estatus != Recibido and verify it doesn't leak
        db.taller_equipos.insert_one({
            "taller_equipo_id": f"te_qa_{uuid.uuid4().hex[:8]}",
            "serial": f"QATEST-{TS}-OTHER",
            "modelo": "X", "modelo_id": "",
            "client_id": CLIENT_ID, "client_name": "Prueba",
            "estatus": "En reparación", "fecha_ingreso": "2025-01-01T00:00:00+00:00",
        })
        r = requests.get(f"{BASE_URL}/taller/equipos-disponibles?client_id={CLIENT_ID}", headers=hdr, timeout=30)
        assert r.status_code == 200
        serials = [e.get("serial") for e in r.json()["equipos"]]
        assert f"QATEST-{TS}-OTHER" not in serials


# ============ Test 2: FLOW LINKED (Recibido → Cotizado → En reparación) ============
class TestFlowLinked:
    def test_full_linked_flow(self, hdr, db):
        # Pre-condiciones: los dos equipos QA existen y están 'Recibido'
        eq_a = _find_taller(db, SERIAL_A)
        eq_b = _find_taller(db, SERIAL_B)
        assert eq_a and eq_a["estatus"] == "Recibido"
        assert eq_b and eq_b["estatus"] == "Recibido"
        linked_ids = [eq_a["taller_equipo_id"], eq_b["taller_equipo_id"]]

        # Baseline count antes del approve
        base_count = _count_taller(db, CLIENT_ID)

        # 1) Crear cotización de reparación vinculada
        payload = {
            "client_id": CLIENT_ID,
            "cliente_nombre": "Prueba",
            "cliente_rif": "J0009273",
            "equipment_type": "Reparación",
            "items": [],
            "notes": "QA linked flow",
            "repair_description": "QA test linked flow",
            "repair_models": [],
            "linked_taller_equipo_ids": linked_ids,
        }
        r = requests.post(f"{BASE_URL}/quotes/generate-equipment-pdf", json=payload, headers=hdr, timeout=90)
        assert r.status_code == 200, f"Quote gen failed: {r.status_code} {r.text[:300]}"
        quote_id = r.headers.get("X-Quote-Id")
        quote_number = r.headers.get("X-Quote-Number")
        assert quote_id and quote_number, f"Missing quote headers: {dict(r.headers)}"

        # Verificar cambios a 'Cotizado'
        eq_a2 = _find_taller(db, SERIAL_A)
        eq_b2 = _find_taller(db, SERIAL_B)
        assert eq_a2["estatus"] == "Cotizado", f"esperado Cotizado got {eq_a2['estatus']}"
        assert eq_b2["estatus"] == "Cotizado"
        assert eq_a2.get("quote_id") == quote_id
        assert eq_a2.get("quote_number") == quote_number

        # 2) Transicionar a 'Enviada'
        r2 = requests.put(f"{BASE_URL}/quotes/{quote_id}/status",
                          json={"new_status": "Enviada"}, headers=hdr, timeout=30)
        assert r2.status_code == 200, f"status→Enviada failed: {r2.text}"

        # 3) Aprobar (multipart/form-data)
        files = {"payload": (None, json.dumps({}))}
        r3 = requests.post(f"{BASE_URL}/quotes/{quote_id}/approve",
                           files=files, headers=hdr, timeout=90)
        assert r3.status_code == 200, f"approve failed: {r3.status_code} {r3.text[:400]}"

        # Verificar cambio a 'En reparación'
        eq_a3 = _find_taller(db, SERIAL_A)
        eq_b3 = _find_taller(db, SERIAL_B)
        assert eq_a3["estatus"] == "En reparación", f"esperado En reparación got {eq_a3['estatus']}"
        assert eq_b3["estatus"] == "En reparación"

        # Verificar que NO se crearon registros nuevos
        after_count = _count_taller(db, CLIENT_ID)
        assert after_count == base_count, (
            f"El approve no debe crear equipos nuevos. base={base_count} after={after_count}"
        )


# ============ Test 3: FALLBACK LEGACY (repair_models, sin linked_ids) ============
class TestFallbackLegacy:
    def test_legacy_creates_en_reparacion_on_approve(self, hdr, db):
        base_count = _count_taller(db, CLIENT_ID)

        # 1) Crear cotización con repair_models (sin linked_taller_equipo_ids)
        payload = {
            "client_id": CLIENT_ID,
            "cliente_nombre": "Prueba",
            "cliente_rif": "J0009273",
            "equipment_type": "Reparación",
            "items": [],
            "notes": "QA legacy flow",
            "repair_description": "QA legacy fallback test",
            "repair_models": [{
                "model_name": "PinpadLegacyQA",
                "model_id": "",
                "quantity": 2,
                "serials": [SERIAL_LEGACY_1, SERIAL_LEGACY_2],
            }],
            "linked_taller_equipo_ids": [],
        }
        r = requests.post(f"{BASE_URL}/quotes/generate-equipment-pdf", json=payload, headers=hdr, timeout=90)
        assert r.status_code == 200, f"Quote gen failed: {r.text[:300]}"
        quote_id = r.headers.get("X-Quote-Id")
        quote_number = r.headers.get("X-Quote-Number")
        assert quote_id and quote_number

        # Verificar que NO se creó nada nuevo en taller_equipos todavía
        mid_count = _count_taller(db, CLIENT_ID)
        assert mid_count == base_count, (
            f"Legacy: al crear cotización, no debe insertarse en taller. base={base_count} mid={mid_count}"
        )

        # 2) Enviar
        r2 = requests.put(f"{BASE_URL}/quotes/{quote_id}/status",
                          json={"new_status": "Enviada"}, headers=hdr, timeout=30)
        assert r2.status_code == 200

        # 3) Aprobar → debe crear los dos registros En reparación
        files = {"payload": (None, json.dumps({}))}
        r3 = requests.post(f"{BASE_URL}/quotes/{quote_id}/approve",
                           files=files, headers=hdr, timeout=90)
        assert r3.status_code == 200, f"approve failed: {r3.text[:400]}"

        # Verificar creación
        eq1 = _find_taller(db, SERIAL_LEGACY_1)
        eq2 = _find_taller(db, SERIAL_LEGACY_2)
        assert eq1 is not None, f"Legacy: falta {SERIAL_LEGACY_1}"
        assert eq2 is not None, f"Legacy: falta {SERIAL_LEGACY_2}"
        assert eq1["estatus"] == "En reparación"
        assert eq2["estatus"] == "En reparación"
        assert eq1.get("quote_id") == quote_id

        after_count = _count_taller(db, CLIENT_ID)
        assert after_count == base_count + 2, (
            f"Legacy: debe crear 2 registros nuevos. base={base_count} after={after_count}"
        )
