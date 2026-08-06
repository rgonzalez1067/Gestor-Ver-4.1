"""iter312 — Regresión de correos a Integradores (dispatch_other_action):
  FALLA A: `from` del email_log debe ser 'impl_merchant@megasoft.com.ve' (área integradores),
           NO 'gestor@megasoft.com.ve' (SENDER_EMAIL global).
  FALLA B: Ningún destinatario debe recibir 2 correos para el mismo evento
           (dedup en dispatch_other_action a nivel de recipients + guaranteed_to).
  REGRESIÓN: send_email respeta `sender` explícito (no lo fuerza global).

Endpoints usados:
  - POST /api/auth/login
  - PUT  /api/integrators/{id}/assign-implementador  → dispara 'implementer_assignment'
"""
import asyncio
import os
import time

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

# ---- URLs / creds ----
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
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


# ---- Fixtures ----
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db(event_loop):
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def api():
    return requests.Session()


@pytest.fixture(scope="module")
def auth_headers(api):
    r = api.post(f"{BASE_URL}/api/auth/login",
                 json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, "No token"
    return {"Authorization": f"Bearer {tok}"}


# ---- Test 1: config integradores → impl_merchant (sanity) ----
def test_email_senders_assignment_integradores_is_impl_merchant(api, auth_headers):
    r = api.get(f"{BASE_URL}/api/config/email-senders", headers=auth_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert (data.get("assignments") or {}).get("integradores") == EXPECTED_SENDER


# ---- Helper: fetch email logs by action & after timestamp ----
async def _fetch_logs(db, action_regex: str, after_iso: str, max_wait_s: float = 6.0):
    end = time.time() + max_wait_s
    logs = []
    while time.time() < end:
        cursor = db.email_logs.find(
            {"action": {"$regex": action_regex}, "created_at": {"$gte": after_iso}},
            {"_id": 0},
        ).sort("created_at", -1)
        logs = await cursor.to_list(length=100)
        if logs:
            return logs
        await asyncio.sleep(0.5)
    return logs


# ---- Test 2: notify-new-project (E2E) ----
def test_notify_new_project_uses_impl_merchant_sender_and_no_duplicates(
    api, auth_headers, db, event_loop,
):
    # 1) Buscar integrador con al menos un contacto (para first_contact)
    async def _get_integrator():
        return await db.integrators.find_one(
            {"contacts.0.email": {"$regex": ".+@.+"}},
            {"_id": 0, "integrator_id": 1, "name": 1},
        )
    integrator = event_loop.run_until_complete(_get_integrator())
    assert integrator, "No hay integradores con contacto para probar"
    integrator_id = integrator["integrator_id"]

    # 2) Marca temporal ANTES del disparo (para filtrar logs)
    import datetime as _dt
    trigger_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    # 3) Ejecutar notify-new-project con dos destinatarios adicionales, uno
    #    igual (case-diff) al implementation_manager_email para provocar dedup.
    #    Manager configurado: rgonzalez@megasoft.com.ve
    resp = api.post(
        f"{BASE_URL}/api/integrators/{integrator_id}/notify-new-project",
        headers=auth_headers,
        json={
            "custom_message": "test iter312",
            "additional_recipients": "Rgonzalez@Megasoft.com.ve,qa_extra_iter312@example.com",
        },
        timeout=60,
    )
    assert resp.status_code == 200, f"notify-new-project falló {resp.status_code}: {resp.text}"

    # 4) Recuperar logs producidos por este evento
    logs = event_loop.run_until_complete(
        _fetch_logs(db, r"^new_integration_project", trigger_iso)
    )
    assert logs, f"No se encontró email_log para new_integration_project después de {trigger_iso}"

    # FALLA A: TODOS los logs deben tener from=impl_merchant
    bad_from = [lg for lg in logs if lg.get("from") != EXPECTED_SENDER]
    assert not bad_from, (
        f"FALLA A no corregida — algunos logs tienen from!=impl_merchant. "
        f"bad={[(lg.get('from'), lg.get('to')) for lg in bad_from]}"
    )
    # Reply-To también debe estar seteado al mismo remitente
    for lg in logs:
        assert lg.get("reply_to") == EXPECTED_SENDER, (
            f"reply_to esperado={EXPECTED_SENDER}, actual={lg.get('reply_to')} log={lg}"
        )

    # FALLA B: dedup por destinatario (case-insensitive) en el mismo evento
    from collections import Counter
    all_to = []
    for lg in logs:
        for e in (lg.get("to") or []):
            all_to.append(e.strip().lower())
    dupes = [e for e, n in Counter(all_to).items() if n > 1]
    assert not dupes, (
        f"FALLA B no corregida — destinatarios duplicados en el mismo evento: {dupes}. "
        f"logs={[(lg.get('action'), lg.get('to')) for lg in logs]}"
    )


# ---- Test 3: dispatch_other_action dedup unitario (guaranteed_to overlap con recipients) ----
def test_dispatch_dedup_when_guaranteed_overlaps_recipients(event_loop, monkeypatch):
    """Sin depender del endpoint: llama dispatch_other_action directamente con un
    guaranteed_to que YA aparece en los recipients configurados y verifica que
    send_email sea invocado exactamente 1 vez por destinatario y con `sender`."""
    import sys
    sys.path.insert(0, "/app/backend")

    # Insertar una config sintética para action_id de prueba
    fake_action = f"iter312_dedup_{int(time.time())}"

    async def _prep_cfg(db, action_id, recipient_email):
        await db.other_action_configs.insert_one({
            "action_id": action_id,
            "enabled": True,
            "recipients": [
                {"row_id": "r1", "type": "custom", "email": recipient_email,
                 "name": "Overlap", "delivery_channel": "email"},
            ],
        })

    async def _cleanup_cfg(db, action_id):
        await db.other_action_configs.delete_one({"action_id": action_id})

    async def _run():
        from motor.motor_asyncio import AsyncIOMotorClient
        c = AsyncIOMotorClient(MONGO_URL)
        db2 = c[DB_NAME]
        target = "overlap_test@example.com"
        await _prep_cfg(db2, fake_action, target)
        try:
            # Parchear send_email para contar llamadas
            from services import other_actions_engine as oae
            calls = []

            async def fake_send(**kw):
                calls.append(kw)
                return {"status": "sent"}

            monkeypatch.setattr(oae, "send_email", fake_send)
            # También parchear los templates a algo trivial
            async def fake_tpl(_id):
                return None
            monkeypatch.setattr(oae, "_load_template", fake_tpl)

            result = await oae.dispatch_other_action(
                action_id=fake_action,
                template_vars={},
                current_user=None,
                fallback_subject="test",
                guaranteed_to=[target.upper(), "extra@example.com"],  # overlap con recipient
                sender=EXPECTED_SENDER,
            )
            return calls, result
        finally:
            await _cleanup_cfg(db2, fake_action)

    calls, result = event_loop.run_until_complete(_run())
    tos = [(kw.get("to") or [None])[0] for kw in calls]
    # Cada destinatario debe aparecer exactamente 1 vez (case-insensitive)
    lowered = [t.lower() for t in tos if t]
    assert lowered.count("overlap_test@example.com") == 1, (
        f"Destinatario overlap debe recibir 1 sola vez; llamadas={tos}"
    )
    assert lowered.count("extra@example.com") == 1
    # Todas las llamadas deben propagar sender=impl_merchant y reply_to=impl_merchant
    for kw in calls:
        assert kw.get("sender") == EXPECTED_SENDER, f"sender no propagado: {kw}"
        assert kw.get("reply_to") == EXPECTED_SENDER, f"reply_to no propagado: {kw}"


# ---- Test 4: Regresión — send_email respeta sender explícito no-integradores ----
def test_send_email_respects_custom_sender_no_global_override(event_loop, db):
    """Si un caller pasa sender='cotizaciones@x' NO debe cambiarse a impl_merchant.
    Verifica que send_email registra en email_logs `from` = sender pasado."""
    import sys, uuid
    sys.path.insert(0, "/app/backend")
    from services.email_service import send_email

    custom_sender = "cotizador_test@megasoft.com.ve"
    subject = f"TEST_iter312_regression_{uuid.uuid4().hex[:6]}"

    async def _run():
        await send_email(
            to=["qa_regression@example.com"],
            subject=subject,
            html="<p>regression</p>",
            action="test_regression_quote",
            sender=custom_sender,
        )
        # buscar log
        for _ in range(6):
            log = await db.email_logs.find_one(
                {"subject": subject}, {"_id": 0}, sort=[("created_at", -1)]
            )
            if log:
                return log
            await asyncio.sleep(0.3)
        return None

    log = event_loop.run_until_complete(_run())
    assert log is not None, "No se registró email_log de regresión"
    assert log.get("from") == custom_sender, (
        f"Regresión: from debe ser sender pasado ({custom_sender}), actual={log.get('from')}"
    )
    assert log.get("from") != EXPECTED_SENDER, (
        "Regresión rota: send_email está forzando impl_merchant globalmente"
    )
