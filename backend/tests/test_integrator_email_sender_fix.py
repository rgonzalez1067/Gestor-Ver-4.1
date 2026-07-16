"""Regression tests for iter282: envío de correos a Integradores debe usar el
remitente configurado en 'assignments.integradores' (impl_merchant@megasoft.com.ve),
NO el SENDER_EMAIL global (gestor@megasoft.com.ve).

Bug RCA: entity_communications.py::_send_and_log y send_mass_communication no
pasaban `sender` a send_email → fallback a SENDER_EMAIL.
Fix: pasar sender=await resolve_sender_for_area('integradores').

Aserción clave: el registro insertado en db.email_logs debe tener
`from == impl_merchant@megasoft.com.ve`.
"""
import asyncio
import json
import os
import time

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

EXPECTED_SENDER = "impl_merchant@megasoft.com.ve"
DEFAULT_SENDER = "gestor@megasoft.com.ve"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


async def _get_latest_email_log(db, action):
    cursor = db.email_logs.find({"action": action}, {"_id": 0}).sort("created_at", -1).limit(1)
    docs = await cursor.to_list(length=1)
    return docs[0] if docs else None


# ---------- Test 1: config/email-senders regresión ----------

def test_config_email_senders_returns_expected_assignment(api, auth_headers):
    r = api.get(f"{BASE_URL}/api/config/email-senders", headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    data = r.json()
    assignments = data.get("assignments") or {}
    senders = data.get("senders") or []
    assert assignments.get("integradores") == EXPECTED_SENDER, (
        f"assignments.integradores esperado={EXPECTED_SENDER}, actual={assignments.get('integradores')}"
    )
    active_emails = {(s.get("email") or "").lower() for s in senders if s.get("active", True)}
    assert EXPECTED_SENDER.lower() in active_emails, (
        f"El remitente {EXPECTED_SENDER} debe estar en senders activos. Actual: {senders}"
    )


# ---------- Test 2: resolve_sender_for_area('integradores') ----------

def test_resolve_sender_for_area_integradores(event_loop):
    """Ejecuta la función real del backend y verifica que devuelva impl_merchant."""
    import sys
    sys.path.insert(0, "/app/backend")
    from services.email_service import resolve_sender_for_area, invalidate_senders_cache

    async def _run():
        invalidate_senders_cache()
        return await resolve_sender_for_area("integradores")

    resolved = event_loop.run_until_complete(_run())
    assert resolved == EXPECTED_SENDER, (
        f"resolve_sender_for_area('integradores') debería devolver {EXPECTED_SENDER}, "
        f"pero devolvió {resolved}"
    )


# ---------- Test 3: envío individual a integrador ----------

def test_send_integrator_email_uses_configured_sender(api, auth_headers, db, event_loop):
    # Escoger un integrador con email válido
    r = api.get(f"{BASE_URL}/api/integrators?show_all=true", headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    payload = r.json()
    lst = payload if isinstance(payload, list) else (payload.get("integrators") or payload.get("items") or [])
    integrator = None
    for it in lst:
        e = (it.get("email") or "").strip()
        if e and "@" in e and "<" not in e:
            integrator = it
            break
    assert integrator, "No se encontró ningún integrador con email limpio para probar"
    integrator_id = integrator.get("integrator_id") or integrator.get("id")
    assert integrator_id

    ts = int(time.time())
    subject = f"TEST_iter282_sender_fix_{ts}"
    resp = api.post(
        f"{BASE_URL}/api/integrators/{integrator_id}/send-email",
        headers=auth_headers,
        data={
            "recipients": json.dumps(["qa_test@example.com"]),
            "subject": subject,
            "message": "Prueba automatizada: verifica que el remitente sea impl_merchant.",
            "internal_doc_ids": "[]",
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"send-email fallo {resp.status_code}: {resp.text}"

    # Consultar en Mongo el email_log más reciente
    async def _fetch():
        # esperar hasta 3s por si hay latencia de escritura
        for _ in range(6):
            log = await db.email_logs.find_one(
                {"action": "integrator_notification", "subject": subject},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
            if log:
                return log
            await asyncio.sleep(0.5)
        return None

    log = event_loop.run_until_complete(_fetch())
    assert log is not None, f"No se encontró email_log para subject={subject}"
    assert log.get("from") == EXPECTED_SENDER, (
        f"email_log.from esperado={EXPECTED_SENDER} pero fue={log.get('from')}. "
        f"log={log}"
    )
    assert log.get("from") != DEFAULT_SENDER, "El remitente NO debe ser el default global"


# ---------- Test 4: comunicación masiva a integradores ----------

def test_mass_communication_uses_configured_sender_and_bcc(api, auth_headers, db, event_loop):
    # Obtener plantilla context=INTEGRADORES
    tpl_id = None

    async def _get_tpl():
        # Preferir template flag correcto (context INTEGRADORES)
        tpl = await db.email_templates.find_one(
            {"context": "INTEGRADORES"},
            {"_id": 0, "template_id": 1},
        )
        return tpl

    tpl = event_loop.run_until_complete(_get_tpl())
    assert tpl and tpl.get("template_id"), "No hay plantilla con context=INTEGRADORES en la BD"
    tpl_id = tpl["template_id"]

    # Obtener integradores con email válido (uno o dos)
    r = api.get(f"{BASE_URL}/api/integrators/mass/recipients", headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    payload = r.json()
    items = payload.get("recipients") or []
    good_ids = [
        it.get("integrator_id") for it in items
        if it.get("has_email") and it.get("integrator_id")
    ][:2]
    assert good_ids, "No hay integradores con email válido para masivo"

    resp = api.post(
        f"{BASE_URL}/api/integrators/mass/communication",
        headers=auth_headers,
        data={
            "template_id": tpl_id,
            "integrator_ids": json.dumps(good_ids),
            "internal_doc_ids": "[]",
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"mass/communication fallo {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("recipients_count") >= 1

    # Verificar el log más reciente
    async def _fetch():
        for _ in range(6):
            log = await db.email_logs.find_one(
                {"action": "integrator_mass_communication"},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
            if log:
                return log
            await asyncio.sleep(0.5)
        return None

    log = event_loop.run_until_complete(_fetch())
    assert log is not None, "No se encontró email_log para integrator_mass_communication"
    assert log.get("from") == EXPECTED_SENDER, (
        f"masivo email_log.from esperado={EXPECTED_SENDER} pero fue={log.get('from')}. log={log}"
    )
    # Destinatarios reales en BCC → to debe ser [mass_sender], bcc_count >= 1
    to_field = log.get("to") or []
    assert to_field == [EXPECTED_SENDER], (
        f"En masivo, 'to' debe ser [{EXPECTED_SENDER}] (para evitar exponer destinatarios); "
        f"actual={to_field}"
    )
    assert (log.get("bcc_count") or 0) >= 1, f"bcc_count debe ser >=1, actual={log.get('bcc_count')}"
