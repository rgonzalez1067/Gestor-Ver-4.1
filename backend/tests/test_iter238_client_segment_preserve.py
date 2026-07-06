"""
Iteración 238 — Bug de degradación de segmento CORP→PYME en el flujo 'Modificar'.

Cobertura backend:
  1. Crear cotización con client_segment='CORP' (via POST /api/quotes) → almacenamiento correcto.
  2. Flujo Modificar: POST /api/quotes/{id}/duplicate + PUT /api/quotes/{new_id} SIN client_segment
     → la nueva versión NO se degrada a PYME.
  3. Mismo flujo enviando client_segment='CORP' explícito → persiste 'CORP'.
  4. Enviar client_segment='Corporativo' → se normaliza a 'CORP'.
  5. PUT sin client_segment sobre cotización CORP existente NO borra el segmento.
  6. POST /api/quotes/{id}/regenerate-pdf sobre CORP conserva client_segment='CORP' y responde 200.
  7. Regresión: PYME + duplicate + PUT sin segmento conserva 'PYME'.

Limpieza: se eliminan las cotizaciones TEST_ generadas.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token")
    assert tok, f"No session_token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_id(headers):
    r = requests.get(f"{BASE_URL}/api/clients", headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert items, "No clients found"
    return items[0]["client_id"]


# Track created quote_ids for cleanup
_created_quote_ids: list[str] = []


def _create_quote(headers, client_id, segment: str) -> dict:
    """Crea una cotización mínima VPOS con el segmento dado."""
    payload = {
        "client_id": client_id,
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "services": [
            {
                "item_id": f"svc_{uuid.uuid4().hex[:8]}",
                "item_name": f"TEST_SEG_{segment}_svc",
                "item_type": "setup",
                "unit_price_usd": 100.0,
                "quantity": 1,
                "total_usd": 100.0,
                "cantidad_cajas": 1,
                "cantidad_bancos": 1,
            }
        ],
        "hardware": [],
        "equipment_items": [],
        "cantidad_cajas": 1,
        "cantidad_bancos": 1,
        "notes": f"TEST_ITER238 seg={segment}",
        "client_segment": segment,
    }
    r = requests.post(f"{BASE_URL}/api/quotes", headers=headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create quote failed: {r.status_code} {r.text}"
    q = r.json()
    _created_quote_ids.append(q["quote_id"])
    return q


def _get_quote(headers, quote_id: str) -> dict:
    r = requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET quote failed: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Test 1 — Crear CORP se persiste como 'CORP'
# ---------------------------------------------------------------------------
def test_create_corp_stores_corp(headers, client_id):
    quote = _create_quote(headers, client_id, "CORP")
    assert quote["client_segment"] == "CORP", (
        f"Cotización creada con client_segment='CORP' se almacenó como {quote.get('client_segment')}"
    )
    persisted = _get_quote(headers, quote["quote_id"])
    assert persisted["client_segment"] == "CORP"


# ---------------------------------------------------------------------------
# Test 2 — duplicate + PUT SIN client_segment sobre CORP NO degrada a PYME
# ---------------------------------------------------------------------------
def test_modify_corp_without_segment_preserves_corp(headers, client_id):
    original = _create_quote(headers, client_id, "CORP")
    assert original["client_segment"] == "CORP"

    # POST duplicate
    r = requests.post(
        f"{BASE_URL}/api/quotes/{original['quote_id']}/duplicate",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, f"duplicate failed: {r.status_code} {r.text}"
    dup = r.json()
    new_id = dup["new_quote_id"]
    _created_quote_ids.append(new_id)

    # PUT actualiza notas SIN incluir client_segment (reproduce el bug original)
    put_payload = {"notes": "TEST_ITER238 modificada sin segmento", "cantidad_cajas": 2}
    r = requests.put(
        f"{BASE_URL}/api/quotes/{new_id}", headers=headers, json=put_payload, timeout=30
    )
    assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"

    updated = _get_quote(headers, new_id)
    assert updated["client_segment"] == "CORP", (
        f"BUG: cotización CORP se degradó a {updated.get('client_segment')} tras duplicate+PUT sin segmento"
    )
    assert updated["notes"] == "TEST_ITER238 modificada sin segmento"
    assert updated["cantidad_cajas"] == 2


# ---------------------------------------------------------------------------
# Test 3 — duplicate + PUT con client_segment='CORP' explícito
# ---------------------------------------------------------------------------
def test_modify_corp_with_explicit_corp_persists(headers, client_id):
    original = _create_quote(headers, client_id, "CORP")
    r = requests.post(
        f"{BASE_URL}/api/quotes/{original['quote_id']}/duplicate",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    new_id = r.json()["new_quote_id"]
    _created_quote_ids.append(new_id)

    put_payload = {"client_segment": "CORP", "notes": "TEST_ITER238 CORP explícito"}
    r = requests.put(
        f"{BASE_URL}/api/quotes/{new_id}", headers=headers, json=put_payload, timeout=30
    )
    assert r.status_code == 200

    updated = _get_quote(headers, new_id)
    assert updated["client_segment"] == "CORP"


# ---------------------------------------------------------------------------
# Test 4 — Normalización 'Corporativo' → 'CORP'
# ---------------------------------------------------------------------------
def test_put_normalizes_corporativo_to_corp(headers, client_id):
    original = _create_quote(headers, client_id, "CORP")
    r = requests.post(
        f"{BASE_URL}/api/quotes/{original['quote_id']}/duplicate",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    new_id = r.json()["new_quote_id"]
    _created_quote_ids.append(new_id)

    put_payload = {"client_segment": "Corporativo"}
    r = requests.put(
        f"{BASE_URL}/api/quotes/{new_id}", headers=headers, json=put_payload, timeout=30
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("client_segment") == "CORP", (
        f"'Corporativo' debía normalizarse a 'CORP', obtuvo {body.get('client_segment')}"
    )
    persisted = _get_quote(headers, new_id)
    assert persisted["client_segment"] == "CORP"


# ---------------------------------------------------------------------------
# Test 5 — PUT sin client_segment sobre CORP no borra el segmento existente
# ---------------------------------------------------------------------------
def test_put_without_segment_does_not_erase(headers, client_id):
    corp = _create_quote(headers, client_id, "CORP")
    # PUT actualiza sólo notas
    r = requests.put(
        f"{BASE_URL}/api/quotes/{corp['quote_id']}",
        headers=headers,
        json={"notes": "TEST_ITER238 preservar segmento"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("client_segment") == "CORP", (
        f"BUG: PUT sin client_segment cambió el segmento a {body.get('client_segment')}"
    )


# ---------------------------------------------------------------------------
# Test 6 — regenerate-pdf sobre CORP conserva segmento y responde 200
# ---------------------------------------------------------------------------
def test_regenerate_pdf_preserves_corp(headers, client_id):
    corp = _create_quote(headers, client_id, "CORP")
    r = requests.post(
        f"{BASE_URL}/api/quotes/{corp['quote_id']}/regenerate-pdf",
        headers=headers,
        json={},
        timeout=60,
    )
    # Aceptamos 200 o 201; si falla por dependencias PDF, reportar
    assert r.status_code in (200, 201), (
        f"regenerate-pdf falló: {r.status_code} {r.text[:400]}"
    )
    persisted = _get_quote(headers, corp["quote_id"])
    assert persisted["client_segment"] == "CORP", (
        f"BUG: regenerate-pdf cambió el segmento a {persisted.get('client_segment')}"
    )


# ---------------------------------------------------------------------------
# Test 7 — Regresión: PYME + duplicate + PUT sin segmento conserva 'PYME'
# ---------------------------------------------------------------------------
def test_pyme_modify_preserves_pyme(headers, client_id):
    pyme = _create_quote(headers, client_id, "PYME")
    assert pyme["client_segment"] == "PYME"

    r = requests.post(
        f"{BASE_URL}/api/quotes/{pyme['quote_id']}/duplicate",
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    new_id = r.json()["new_quote_id"]
    _created_quote_ids.append(new_id)

    r = requests.put(
        f"{BASE_URL}/api/quotes/{new_id}",
        headers=headers,
        json={"notes": "TEST_ITER238 regresión PYME"},
        timeout=30,
    )
    assert r.status_code == 200

    updated = _get_quote(headers, new_id)
    assert updated["client_segment"] == "PYME"


# ---------------------------------------------------------------------------
# Cleanup module-scoped
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def _cleanup(headers):
    yield
    for qid in _created_quote_ids:
        try:
            requests.delete(f"{BASE_URL}/api/quotes/{qid}", headers=headers, timeout=15)
        except Exception:
            pass
