"""
Iteration 253 — Backend regression test

Bug fix: POST /api/quotes/{quote_id}/configure sobre una cotización fast_track
(MPOS Imple + POS) YA NO debe devolver 400 por estado. Antes fallaba con
"Solo se puede configurar desde estado Aprobada. Estado actual: Enviada a Imple".

Se mantiene la restricción de categoría: cotizaciones NO fast_track siguen
devolviendo 400.
"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login falló: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("session_token") or body.get("access_token") or body.get("token")
    assert token, f"No se encontró token en respuesta: {body}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def fast_track_quote(db):
    """Devuelve el quote_id de una cotización fast_track existente."""
    q = db.quotes.find_one({"quote_category": "fast_track"}, {"_id": 0, "quote_id": 1})
    if not q:
        pytest.skip("No hay cotización fast_track en DB para probar")
    return q["quote_id"]


@pytest.fixture(scope="module")
def non_fast_track_quote(db):
    """Devuelve el quote_id de una cotización NO fast_track."""
    q = db.quotes.find_one({"quote_category": {"$ne": "fast_track"}}, {"_id": 0, "quote_id": 1, "quote_category": 1})
    if not q:
        pytest.skip("No hay cotización NO fast_track en DB para probar")
    return q["quote_id"]


def _force_status(db, quote_id, status):
    db.quotes.update_one({"quote_id": quote_id}, {"$set": {"quote_status": status}})


# ---------- Tests ----------

class TestMposConfigureStateFix:
    """Regresión Iter253: configure ya no exige estado 'Aprobada' para fast_track."""

    def test_configure_from_enviada_a_imple_returns_200(self, db, auth_headers, fast_track_quote):
        # Forzar estado != Aprobada (aquí exactamente el estado reportado como bug)
        _force_status(db, fast_track_quote, "Enviada a Imple")
        r = requests.post(
            f"{BASE_URL}/api/quotes/{fast_track_quote}/configure",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"Esperado 200, recibido {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("new_status") == "Configurada", data
        assert data.get("quote_id") == fast_track_quote

        # Verificar persistencia en DB
        q = db.quotes.find_one({"quote_id": fast_track_quote}, {"_id": 0})
        assert q["quote_status"] == "Configurada"
        assert q.get("configured_at"), "Falta configured_at en DB"

    @pytest.mark.parametrize("status", ["Configurada", "Facturada", "Pagada"])
    def test_configure_from_other_states_returns_200(self, db, auth_headers, fast_track_quote, status):
        _force_status(db, fast_track_quote, status)
        r = requests.post(
            f"{BASE_URL}/api/quotes/{fast_track_quote}/configure",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"[{status}] Esperado 200, recibido {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("new_status") == "Configurada"

        q = db.quotes.find_one({"quote_id": fast_track_quote}, {"_id": 0})
        assert q["quote_status"] == "Configurada"

    def test_configure_from_aprobada_still_works(self, db, auth_headers, fast_track_quote):
        _force_status(db, fast_track_quote, "Aprobada")
        r = requests.post(
            f"{BASE_URL}/api/quotes/{fast_track_quote}/configure",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"Esperado 200 desde Aprobada, recibido {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("new_status") == "Configurada"

    def test_configure_non_fast_track_returns_400(self, auth_headers, non_fast_track_quote):
        r = requests.post(
            f"{BASE_URL}/api/quotes/{non_fast_track_quote}/configure",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 400, f"Esperado 400 por categoría, recibido {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "MPOS" in detail or "fast_track" in detail.lower(), (
            f"Mensaje inesperado: {detail}"
        )

    def test_configure_nonexistent_quote_returns_404(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/quotes/quo_doesnotexist_xyz/configure",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 404, f"Esperado 404, recibido {r.status_code}: {r.text}"
