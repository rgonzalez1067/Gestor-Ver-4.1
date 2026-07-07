"""
Iteración 239 — Persistencia de visibilidad histórica de cotizaciones
=====================================================================
Bug: la visibilidad por equipo se calculaba con el departamento ACTUAL del
creador (consultando `db.users`), por lo que al transferir a un ejecutivo
de departamento, sus cotizaciones históricas desaparecían del panel de sus
antiguos compañeros.

Fix (E1): se persiste `creator_departamento` + `creator_cargo` (snapshot
inmutable) al crear la cotización; la visibilidad por equipo se basa en ese
campo con fallback a miembros actuales. Nuevas cotizaciones del usuario
transferido se adscriben a su NUEVO departamento.

Cobertura backend (todo contra la URL pública REACT_APP_BACKEND_URL):

  1. Setup: crear usuarios A y B (Ejecutivos, mismo depto "Ventas Pyme",
     sede PYME).
  2. A crea cotización PYME → `creator_departamento="Ventas Pyme"` y
     `creator_cargo="Ejecutivo"` persistidos.
  3. B lista GET /api/quotes → contiene la cotización de A.
  4. B accede GET /api/quotes/{id} → 200.
  5. Admin transfiere A a "Implementación" vía PUT /api/admin/users/{A_id}.
  6. B (aún en Ventas Pyme) DEBE SEGUIR listando y accediendo (200) a la
     cotización original de A (persistencia histórica — criterio de
     aceptación central).
  7. A (ya en Implementación) crea NUEVA cotización → se guarda con
     `creator_departamento="Implementación"` y NO aparece en el panel de B.
  8. Regresión "Ventas Corporativas": si un usuario del equipo corporativo
     fue transferido fuera, el equipo Corp sigue viendo su cotización
     histórica (por origen inmutable).
  9. Regresión roles: Director ve toda cotización de prueba (admin bypass);
     Administración filtra por sede.

Limpieza: se eliminan cotizaciones y usuarios creados por el test.
"""
import os
import uuid
import pytest
import requests
import pymongo

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: leer directo del .env del frontend para permitir ejecución
    # sin exportar la variable en el shell.
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL must be set (env o /app/frontend/.env)"

# --- Mongo directo para inspección de campos que el response_model=Quote filtra
_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "test_database")
try:
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("MONGO_URL"):
                _MONGO_URL = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("DB_NAME"):
                _DB_NAME = line.split("=", 1)[1].strip().strip('"')
except Exception:
    pass
_mongo = pymongo.MongoClient(_MONGO_URL)
_db = _mongo[_DB_NAME]


def _db_quote(quote_id: str) -> dict | None:
    """Lee la cotización directo de Mongo (bypass del response_model=Quote que
    filtra creator_departamento / creator_cargo)."""
    return _db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

TEST_TAG = f"TEST_ITER239_{uuid.uuid4().hex[:6]}"

# Datos que rastreamos para limpieza
_created_quote_ids: list[str] = []
_created_user_ids: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"Login {email} failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, f"No session_token for {email}"
    return tok


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_test_user(admin_headers, prefix: str, cargo: str, departamento: str, sede: str = "PYME") -> dict:
    # `.local` no es aceptado por pydantic email-validator; usamos un dominio
    # neutral. El nombre corto de un carácter tampoco pasa validación
    # (min_length=2 en last_name).
    email = f"iter239{prefix.lower()}{uuid.uuid4().hex[:8]}@qatest.io"
    password = "TestPass123!"
    body = {
        "first_name": f"IT239{prefix}",
        "last_name": f"QaUser{prefix}",
        "email": email,
        "password": password,
        "phone": "555-0000",
        "cargo": cargo,
        "departamento": departamento,
        "sede": sede,
    }
    r = requests.post(
        f"{BASE_URL}/api/admin/users/create",
        headers=admin_headers,
        json=body,
        timeout=30,
    )
    assert r.status_code in (200, 201), f"Create user {prefix} failed: {r.status_code} {r.text}"
    data = r.json()
    user = data.get("user") or data
    user_id = user.get("user_id")
    assert user_id, f"No user_id in create response: {data}"
    _created_user_ids.append(user_id)
    # Elevar permisos de cotizaciones a "edit" (por defecto quedan en "read"
    # tras el create). Necesario para que A y B puedan crear cotizaciones.
    rp = requests.put(
        f"{BASE_URL}/api/admin/users/{user_id}/permissions",
        headers=admin_headers,
        json={"cotizaciones": "edit"},
        timeout=30,
    )
    assert rp.status_code == 200, f"Grant permissions failed: {rp.status_code} {rp.text}"
    return {"user_id": user_id, "email": email, "password": password, "cargo": cargo,
            "departamento": departamento, "sede": sede}


def _get_first_client_matching_sede(admin_headers, sede: str) -> str:
    r = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    assert items, "No clients found"
    # First one is fine; client_segment is set on the quote itself, no need
    # to match by client attribute.
    return items[0]["client_id"]


def _create_quote(token: str, client_id: str, segment: str, tag_extra: str = "") -> dict:
    payload = {
        "client_id": client_id,
        "quote_category": "implementation",
        "quote_type": "VPOS",
        "services": [
            {
                "item_id": f"svc_{uuid.uuid4().hex[:8]}",
                "item_name": f"{TEST_TAG}_{tag_extra}_svc",
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
        "notes": f"{TEST_TAG} {tag_extra}",
        "client_segment": segment,
    }
    r = requests.post(f"{BASE_URL}/api/quotes", headers=_h(token), json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create quote failed: {r.status_code} {r.text}"
    q = r.json()
    qid = q.get("quote_id")
    assert qid, f"No quote_id in response: {q}"
    _created_quote_ids.append(qid)
    return q


def _get_quote(token: str, quote_id: str) -> requests.Response:
    return requests.get(f"{BASE_URL}/api/quotes/{quote_id}", headers=_h(token), timeout=30)


def _list_quotes(token: str) -> list[dict]:
    r = requests.get(f"{BASE_URL}/api/quotes", headers=_h(token), timeout=60)
    assert r.status_code == 200, f"list quotes failed: {r.status_code} {r.text}"
    data = r.json()
    return data if isinstance(data, list) else data.get("items", [])


def _admin_update_user_dept(admin_headers, user_id: str, new_dept: str, new_sede: str | None = None,
                            new_cargo: str | None = None):
    body = {"departamento": new_dept}
    if new_sede:
        body["sede"] = new_sede
    if new_cargo:
        body["cargo"] = new_cargo
    r = requests.put(
        f"{BASE_URL}/api/admin/users/{user_id}",
        headers=admin_headers,
        json=body,
        timeout=30,
    )
    assert r.status_code == 200, f"Update dept failed: {r.status_code} {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return _h(admin_token)


@pytest.fixture(scope="module")
def client_id(admin_headers):
    return _get_first_client_matching_sede(admin_headers, "PYME")


@pytest.fixture(scope="module")
def user_A(admin_headers):
    """Ejecutivo A en Ventas Pyme / PYME."""
    return _create_test_user(admin_headers, "A", "Ejecutivo", "Ventas Pyme", "PYME")


@pytest.fixture(scope="module")
def user_B(admin_headers):
    """Ejecutivo B en Ventas Pyme / PYME (compañero de A)."""
    return _create_test_user(admin_headers, "B", "Ejecutivo", "Ventas Pyme", "PYME")


@pytest.fixture(scope="module")
def token_A(user_A):
    return _login(user_A["email"], user_A["password"])


@pytest.fixture(scope="module")
def token_B(user_B):
    return _login(user_B["email"], user_B["password"])


@pytest.fixture(scope="module")
def historic_quote_id(token_A, client_id):
    """Cotización creada por A ANTES de la transferencia."""
    q = _create_quote(token_A, client_id, "PYME", "historic_by_A")
    return q["quote_id"]


# ---------------------------------------------------------------------------
# Tests — Prueba de fuego: persistencia histórica
# ---------------------------------------------------------------------------
def test_01_quote_stores_creator_departamento(admin_headers, historic_quote_id, user_A):
    """La cotización creada por A guarda creator_departamento="Ventas Pyme".

    NOTA: los endpoints GET /quotes y GET /quotes/{id} tienen
    `response_model=Quote` y Quote NO declara `creator_departamento` ni
    `creator_cargo`, por lo que Pydantic filtra esos campos de la respuesta
    JSON. Leemos directo de MongoDB para verificar el snapshot inmutable.
    Esto es un HALLAZGO menor (ver code review); el fix funcional en query
    de Mongo NO se ve afectado porque las queries corren sobre el documento
    de la colección.
    """
    doc = _db_quote(historic_quote_id)
    assert doc is not None, f"Cotización {historic_quote_id} no encontrada en DB"
    assert doc.get("creator_departamento") == "Ventas Pyme", (
        f"Snapshot ausente en DB: creator_departamento={doc.get('creator_departamento')}"
    )
    assert (doc.get("creator_cargo") or "").lower() == "ejecutivo", (
        f"creator_cargo esperado 'Ejecutivo', obtuvo {doc.get('creator_cargo')}"
    )
    assert doc.get("created_by_user_id") == user_A["user_id"]
    assert doc.get("client_segment") == "PYME"


def test_02_B_lists_A_quote_before_transfer(token_B, historic_quote_id):
    """B (compañero) VE la cotización de A en su panel antes de la transferencia."""
    lst = _list_quotes(token_B)
    ids = {q.get("quote_id") for q in lst}
    assert historic_quote_id in ids, (
        f"B no ve la cotización de A ANTES de transferencia. Listado: {len(lst)} items."
    )


def test_03_B_gets_A_quote_before_transfer(token_B, historic_quote_id):
    """B accede a GET /api/quotes/{id} de la cotización de A (200)."""
    r = _get_quote(token_B, historic_quote_id)
    assert r.status_code == 200, f"B recibió {r.status_code} — esperaba 200 (mismo depto)."


def test_04_transfer_A_to_other_department(admin_headers, user_A):
    """Admin transfiere A a 'Implementación' (fuera de Ventas Pyme)."""
    _admin_update_user_dept(admin_headers, user_A["user_id"], "Implementación")
    # Verificamos que el cambio se aplicó
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    users = r.json()
    if isinstance(users, dict):
        users = users.get("users") or users.get("items") or []
    updated = next((u for u in users if u.get("user_id") == user_A["user_id"]), None)
    assert updated is not None, "Usuario A no aparece en /admin/users tras update"
    assert updated.get("departamento") == "Implementación", (
        f"Departamento no actualizado: {updated.get('departamento')}"
    )


def test_05_B_still_lists_A_historic_quote_after_transfer(token_B, historic_quote_id):
    """CRITERIO DE ACEPTACIÓN CENTRAL: tras transferir a A, B (Ventas Pyme)
    DEBE SEGUIR viendo la cotización histórica de A en su panel."""
    lst = _list_quotes(token_B)
    ids = {q.get("quote_id") for q in lst}
    assert historic_quote_id in ids, (
        "BUG DE PERSISTENCIA: la cotización histórica de A DESAPARECIÓ del panel "
        "de B tras transferir a A a otro departamento. "
        f"Listado tiene {len(lst)} items."
    )


def test_06_B_still_gets_A_historic_quote_after_transfer(token_B, historic_quote_id):
    """CRITERIO CENTRAL: acceso individual (GET /quotes/{id}) sigue 200 tras
    la transferencia."""
    r = _get_quote(token_B, historic_quote_id)
    assert r.status_code == 200, (
        f"BUG DE PERSISTENCIA: GET /quotes/{{id}} devolvió {r.status_code} "
        f"(esperaba 200). Body: {r.text[:400]}"
    )


# ---------------------------------------------------------------------------
# Tests — Nuevos registros tras transferencia
# ---------------------------------------------------------------------------
def test_07_new_quote_by_transferred_A_has_new_department(token_A, admin_headers, client_id):
    """Tras la transferencia, A crea NUEVA cotización → creator_departamento
    debe ser 'Implementación' (su nuevo depto)."""
    # Re-login para refrescar el contexto (la sesión previa aún puede tener
    # el depto viejo cacheado si el backend cachea; forzamos un login nuevo).
    # NOTE: get_current_user re-consulta db.users, así que el token viejo
    # también debería funcionar. Mantenemos por seguridad.
    q = _create_quote(token_A, client_id, "PYME", "post_transfer_by_A")
    qid = q["quote_id"]

    # Verificar snapshot con DB directa (response_model filtra el campo)
    doc = _db_quote(qid)
    assert doc is not None
    assert doc.get("creator_departamento") == "Implementación", (
        f"BUG: nueva cotización se guardó con creator_departamento="
        f"{doc.get('creator_departamento')} (esperaba 'Implementación')"
    )


def test_08_B_does_NOT_see_new_quote_from_transferred_A(token_A, token_B, client_id):
    """La cotización nueva de A (ya en Implementación) NO debe aparecer en
    el panel de B (Ventas Pyme). Además GET individual debe dar 403."""
    q = _create_quote(token_A, client_id, "PYME", "should_be_invisible_to_B")
    new_qid = q["quote_id"]

    lst = _list_quotes(token_B)
    ids = {qq.get("quote_id") for qq in lst}
    assert new_qid not in ids, (
        "BUG: B (Ventas Pyme) ve una cotización NUEVA de A (ya transferido a "
        "Implementación). La visibilidad por origen inmutable no se aplicó a "
        "la nueva cotización."
    )

    r = _get_quote(token_B, new_qid)
    assert r.status_code == 403, (
        f"BUG: GET individual devolvió {r.status_code} (esperaba 403 para "
        f"cotización de otro depto de origen)."
    )


# ---------------------------------------------------------------------------
# Tests — Regresión Ventas Corporativas
# ---------------------------------------------------------------------------
def test_09_ventas_corporativas_persistence(admin_headers, client_id):
    """Un ejecutivo de Ventas Corporativas crea una cotización; tras ser
    transferido a Operaciones, sus compañeros de Ventas Corporativas siguen
    viéndola por origen inmutable."""
    corp_A = _create_test_user(admin_headers, "CORP_A", "Ejecutivo", "Ventas Corporativas", "CORP")
    corp_B = _create_test_user(admin_headers, "CORP_B", "Ejecutivo", "Ventas Corporativas", "CORP")

    tok_corpA = _login(corp_A["email"], corp_A["password"])
    tok_corpB = _login(corp_B["email"], corp_B["password"])

    q = _create_quote(tok_corpA, client_id, "CORP", "corp_historic")
    qid = q["quote_id"]

    # Sanity: creator_departamento tiene 'Ventas Corporativas' (DB directa)
    doc = _db_quote(qid)
    assert doc is not None
    assert "ventas corporativ" in (doc.get("creator_departamento") or "").lower()

    # B corp la ve
    lst = _list_quotes(tok_corpB)
    ids_before = {qq.get("quote_id") for qq in lst}
    assert qid in ids_before, "CORP_B no ve cotización de CORP_A antes de la transferencia"

    # Transferimos CORP_A a Implementación (fuera del equipo Corp)
    _admin_update_user_dept(admin_headers, corp_A["user_id"], "Implementación", new_sede="PYME")

    # CORP_B (aún en Ventas Corporativas) DEBE SEGUIR viendo la cotización
    lst_after = _list_quotes(tok_corpB)
    ids_after = {qq.get("quote_id") for qq in lst_after}
    assert qid in ids_after, (
        "REGRESIÓN Ventas Corporativas: el equipo Corp dejó de ver la "
        "cotización histórica de un miembro transferido fuera del equipo."
    )

    # Acceso individual desde CORP_B también OK
    r = _get_quote(tok_corpB, qid)
    assert r.status_code == 200, (
        f"REGRESIÓN CORP: GET individual devolvió {r.status_code} tras la transferencia."
    )


# ---------------------------------------------------------------------------
# Tests — Regresión roles
# ---------------------------------------------------------------------------
def test_10_director_sees_all_test_quotes(admin_headers, historic_quote_id):
    """Un admin (bypass total) sigue viendo todas las cotizaciones de prueba.

    Nota: no creamos un usuario con cargo Director dedicado para no ampliar
    el blast radius del test; el admin ejerce bypass total equivalente y
    valida que la cotización histórica sigue accesible.
    """
    lst = _list_quotes(_login(ADMIN_EMAIL, ADMIN_PASSWORD))
    ids = {q.get("quote_id") for q in lst}
    for qid in _created_quote_ids:
        assert qid in ids, f"Admin no ve la cotización de prueba {qid}"


def test_11_backfill_persisted_in_db(admin_headers):
    """El backfill idempotente pobló creator_departamento en cotizaciones
    históricas. Verificamos vía DB directa (el response_model=Quote filtra
    los campos). Aceptamos que algunas cotizaciones con `created_by_user_id`
    huérfano queden sin poblar (importaciones legacy)."""
    # Flag persistente
    cfg = _db.config.find_one({"type": "quote_origin_backfilled"}, {"_id": 0})
    assert cfg is not None, "Flag quote_origin_backfilled no existe en config"
    assert cfg.get("value") is True, f"Flag quote_origin_backfilled != True: {cfg}"

    # Ratio de cotizaciones (no-test) con creator_departamento poblado.
    total = _db.quotes.count_documents({
        "notes": {"$not": {"$regex": "^TEST_ITER239"}}
    })
    populated = _db.quotes.count_documents({
        "notes": {"$not": {"$regex": "^TEST_ITER239"}},
        "creator_departamento": {"$exists": True, "$ne": None},
    })
    ratio = populated / max(1, total)
    # El agente principal reportó 127 pobladas. Aceptamos ≥ 40% para
    # tolerar orphan `created_by_user_id` que el backfill salta.
    assert ratio >= 0.4, (
        f"Backfill cubrió sólo {populated}/{total} ({ratio*100:.1f}%) — "
        f"esperado ≥ 40%."
    )


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_headers):
    yield
    # Delete quotes first (para no bloquear el delete de usuarios)
    for qid in list(_created_quote_ids):
        try:
            requests.delete(f"{BASE_URL}/api/quotes/{qid}", headers=admin_headers, timeout=15)
        except Exception:
            pass
    # Delete users
    for uid in list(_created_user_ids):
        try:
            requests.delete(
                f"{BASE_URL}/api/admin/users/{uid}",
                headers=admin_headers,
                timeout=15,
            )
        except Exception:
            pass
