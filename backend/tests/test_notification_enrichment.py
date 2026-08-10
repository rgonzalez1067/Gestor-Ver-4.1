"""Tests for notification push enrichment + financial sanitization.

Covers services/notification_service.notify():
 (1) Project notification with client + ticket → prefix
     "[Cliente: X] [Ticket #: Y] - <msg>"
 (2) Project notification without ticket → only "[Cliente: X] - <msg>"
 (3) Quote (non-project) notification → only "[Cliente: X] - <msg>", no ticket tag
 (4) Financial sanitization: no amounts/currencies in title/message
 (5) No client/project/quote → still creates notification (sanitized) — no crash
Also unit-tests _sanitize_financial regex directly.
"""
import asyncio
import os
import sys
import uuid
import pytest

# Ensure backend on sys.path
BACKEND_DIR = "/app/backend"
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import db  # noqa: E402
from services.notification_service import (  # noqa: E402
    notify,
    _sanitize_financial,
    _strip_redundant_client,
)


# ---------- Helpers ----------

async def _make_test_user(sede="PYME"):
    uid = f"tst_{uuid.uuid4().hex[:10]}"
    await db.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@test.local",
        "first_name": "Test",
        "last_name": "User",
        "role": "user",
        "departamento": "Implementación",
        "cargo": "Implementador",
        "sede": sede,
        "is_active": True,
    })
    return uid


async def _cleanup(user_ids=None, project_ids=None, quote_ids=None):
    if user_ids:
        await db.users.delete_many({"user_id": {"$in": user_ids}})
        await db.notifications.delete_many({"user_id": {"$in": user_ids}})
    if project_ids:
        await db.projects.delete_many({"project_id": {"$in": project_ids}})
    if quote_ids:
        await db.quotes.delete_many({"quote_id": {"$in": quote_ids}})


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------- Unit tests for _sanitize_financial ----------

class TestSanitizeFinancial:
    def test_removes_dollar_symbol(self):
        assert "$1,500.00" not in _sanitize_financial("Costo total $1,500.00 aprobado")
        assert "aprobado" in _sanitize_financial("Costo total $1,500.00 aprobado")

    def test_removes_usd_prefix(self):
        out = _sanitize_financial("Total USD 2,300 confirmado")
        assert "USD" not in out and "2,300" not in out
        assert "confirmado" in out

    def test_removes_bs(self):
        out = _sanitize_financial("Monto Bs. 1.500,00 registrado")
        assert "Bs" not in out and "1.500,00" not in out
        assert "registrado" in out

    def test_removes_ves_suffix(self):
        out = _sanitize_financial("Pagado 450 VES ok")
        assert "VES" not in out and "450" not in out
        assert "ok" in out

    def test_removes_euro(self):
        out = _sanitize_financial("Precio €200 aceptado")
        assert "€" not in out and "200" not in out
        assert "aceptado" in out

    def test_keeps_operational_text(self):
        out = _sanitize_financial("Proyecto aprobado")
        assert out == "Proyecto aprobado"

    def test_none_and_empty(self):
        assert _sanitize_financial(None) is None
        assert _sanitize_financial("") == ""


class TestStripRedundantClient:
    def test_strips_prefix(self):
        assert _strip_redundant_client("Cliente Alfa - approved", "Alfa") == "approved"

    def test_strips_colon(self):
        assert _strip_redundant_client("Cliente: Alfa - approved", "Alfa") == "approved"

    def test_no_match(self):
        assert _strip_redundant_client("Approved by admin", "Alfa") == "Approved by admin"


# ---------- Integration tests for notify() ----------

# All async DB tests are consolidated into one session because Motor's
# executor binds to the first loop it saw. Running each async test in its own
# loop (pytest-asyncio default) triggers "Event loop is closed" on the 2nd+.

async def _scenario_project_with_client_and_ticket():
    uid = await _make_test_user()
    pid = f"tstprj_{uuid.uuid4().hex[:8]}"
    await db.projects.insert_one({
        "project_id": pid,
        "client_name": "Corporación Alfa",
        "ticket_number": "T-9912",
    })
    try:
        n = await notify(
            event_type="project_assigned_to_me",
            title="Proyecto asignado por $1,500.00",
            message="Asignado. Costo total USD 2,300 aprobado.",
            context={"assignee_user_id": uid},
            project_id=pid,
        )
        assert n >= 1
        doc = await db.notifications.find_one({"user_id": uid, "project_id": pid})
        assert doc is not None
        msg = doc["message"]
        title = doc["title"]
        assert msg.startswith("[Cliente: Corporación Alfa] [Ticket #: T-9912] - "), f"Unexpected msg: {msg!r}"
        # No financial info
        for bad in ["$", "USD", "1,500", "2,300", "€", "Bs", "VES"]:
            assert bad not in msg, f"Found {bad!r} in msg: {msg!r}"
            assert bad not in title, f"Found {bad!r} in title: {title!r}"
        # Operational verb still there
        assert "aprobado" in msg.lower() or "asignado" in msg.lower()
    finally:
        await _cleanup(user_ids=[uid], project_ids=[pid])


async def _scenario_project_without_ticket_omits_tag():
    uid = await _make_test_user()
    pid = f"tstprj_{uuid.uuid4().hex[:8]}"
    await db.projects.insert_one({
        "project_id": pid,
        "client_name": "Beta Corp",
        "ticket_number": "",  # empty → tag must be omitted
    })
    try:
        n = await notify(
            event_type="project_assigned_to_me",
            title="Nuevo proyecto",
            message="Se ha asignado el proyecto.",
            context={"assignee_user_id": uid},
            project_id=pid,
        )
        assert n >= 1
        doc = await db.notifications.find_one({"user_id": uid, "project_id": pid})
        assert doc is not None
        msg = doc["message"]
        assert msg.startswith("[Cliente: Beta Corp] - "), f"Unexpected msg: {msg!r}"
        assert "[Ticket" not in msg, f"Ticket tag should be absent: {msg!r}"
    finally:
        await _cleanup(user_ids=[uid], project_ids=[pid])


async def _scenario_quote_has_client_no_ticket():
    uid = await _make_test_user()
    qid = f"tstq_{uuid.uuid4().hex[:8]}"
    await db.quotes.insert_one({
        "quote_id": qid,
        "client_name": "Gamma Ltda",
        "sede": "PYME",
    })
    try:
        n = await notify(
            event_type="quote_approved",
            title="Cotización aprobada por $5,000",
            message="Cotización aprobada por el cliente.",
            context={"creator_user_id": uid, "sede": "PYME"},
            quote_id=qid,
        )
        # recipients: admin_by_sede — our test user is not admin, so may or may not be recipient.
        # But since we passed creator_user_id? No — quote_approved uses admin_by_sede only.
        # We need to grab any notification for this quote.
        docs = [d async for d in db.notifications.find({"quote_id": qid})]
        assert docs, f"No notifications persisted (n={n})"
        for doc in docs:
            msg = doc["message"]
            title = doc["title"]
            assert msg.startswith("[Cliente: Gamma Ltda] - "), f"Unexpected msg: {msg!r}"
            assert "[Ticket" not in msg
            for bad in ["$", "USD", "5,000"]:
                assert bad not in title, f"Financial leak in title: {title!r}"
                assert bad not in msg, f"Financial leak in msg: {msg!r}"
    finally:
        # cleanup any created notifications for this quote
        await db.notifications.delete_many({"quote_id": qid})
        await _cleanup(user_ids=[uid], quote_ids=[qid])


async def _scenario_financial_sanitization_multiple_currencies():
    uid = await _make_test_user()
    pid = f"tstprj_{uuid.uuid4().hex[:8]}"
    await db.projects.insert_one({
        "project_id": pid,
        "client_name": "Delta",
        "ticket_number": "T-1",
    })
    try:
        await notify(
            event_type="project_assigned_to_me",
            title="Total $1,500.00 / USD 2,300 / Bs. 1.500,00 / 450 VES / €200",
            message="Aprobado por $99, USD 88, Bs 77, 66 VES, €55.",
            context={"assignee_user_id": uid},
            project_id=pid,
        )
        doc = await db.notifications.find_one({"user_id": uid, "project_id": pid})
        assert doc is not None
        title, msg = doc["title"], doc["message"]
        for bad in ["$", "USD", "Bs", "VES", "€", "1,500", "2,300", "1.500,00", "450", "200", "99", "88", "77", "66", "55"]:
            assert bad not in title, f"Financial leak in title: {title!r} (found {bad!r})"
            assert bad not in msg, f"Financial leak in msg: {msg!r} (found {bad!r})"
        assert msg.startswith("[Cliente: Delta] [Ticket #: T-1] - ")
        assert "aprobado" in msg.lower()
    finally:
        await _cleanup(user_ids=[uid], project_ids=[pid])


async def _scenario_no_client_no_project_still_works():
    """Event without project/quote/client — should still create sanitized notification, no crash."""
    uid = await _make_test_user()
    try:
        # Use event with 'assignee' recipient to target our test user directly.
        n = await notify(
            event_type="bank_notified_in_project",
            title="Banco notificado por $1,000",
            message="Se envió notificación al banco.",
            context={"assignee_user_id": uid},
            project_id=None,
        )
        assert n >= 1
        doc = await db.notifications.find_one({"user_id": uid, "event_type": "bank_notified_in_project"})
        assert doc is not None
        title, msg = doc["title"], doc["message"]
        # Sanitized, no prefix (no client_name)
        assert "$" not in title and "$" not in msg
        assert "1,000" not in title and "1,000" not in msg
        assert not msg.startswith("[Cliente:"), f"Should NOT have prefix without client: {msg!r}"
        assert "banco" in msg.lower()
    finally:
        await _cleanup(user_ids=[uid])


# ---------- Single async runner: all DB scenarios in ONE event loop ----------

def test_all_notification_scenarios():
    """Runs all async scenarios (unit + E2E) sequentially in a single
    asyncio.run() so the Motor client's thread-executor stays bound to one loop."""
    import os
    import requests

    BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
    assert BASE_URL, "REACT_APP_BACKEND_URL not set"

    session = requests.Session()
    login = session.post(f"{BASE_URL}/api/auth/login",
                         json={"email": "rgonzalez@megasoft.com.ve", "password": "admin123"},
                         timeout=15)
    assert login.status_code == 200, f"login failed: {login.status_code} {login.text}"
    token = login.json().get("session_token") or login.json().get("token")
    assert token, f"no token in login response: {login.json()}"
    session.headers.update({"Authorization": f"Bearer {token}"})

    async def _e2e():
        proj = await db.projects.find_one(
            {"ticket_number": {"$exists": True, "$ne": ""},
             "assigned_to_user_id": {"$exists": True, "$ne": None}},
            {"_id": 0, "project_id": 1, "client_name": 1, "ticket_number": 1,
             "assigned_to_user_id": 1, "client_sede": 1},
        )
        assert proj, "No project with ticket_number + assignee found in DB"
        pid, assignee = proj["project_id"], proj["assigned_to_user_id"]
        client_name, ticket = proj["client_name"], proj["ticket_number"]

        before = await db.notifications.count_documents(
            {"user_id": assignee, "project_id": pid, "event_type": "project_assigned_to_me"}
        )

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: session.put(
                f"{BASE_URL}/api/projects/{pid}/assign",
                json={"assigned_to_user_id": assignee},
                timeout=20,
            ),
        )
        assert resp.status_code == 200, f"assign failed: {resp.status_code} {resp.text}"

        doc = await db.notifications.find_one(
            {"user_id": assignee, "project_id": pid, "event_type": "project_assigned_to_me"},
            sort=[("created_at", -1)],
        )
        after = await db.notifications.count_documents(
            {"user_id": assignee, "project_id": pid, "event_type": "project_assigned_to_me"}
        )
        assert doc is not None, "No push notification persisted after assign"
        assert after == before + 1, f"expected +1 notification (before={before} after={after})"
        expected_prefix = f"[Cliente: {client_name}] [Ticket #: {ticket}]"
        assert doc["message"].startswith(expected_prefix), \
            f"Unexpected msg.\n  expected start: {expected_prefix!r}\n  got: {doc['message']!r}"
        for bad in ["$", "USD", "€", "Bs.", "VES", "EUR"]:
            assert bad not in doc["title"], f"Financial leak in title: {doc['title']!r}"
            assert bad not in doc["message"], f"Financial leak in msg: {doc['message']!r}"
        print(f"[E2E OK] project_id={pid} msg={doc['message']!r}")

    async def _run_all():
        await _scenario_project_with_client_and_ticket()
        await _scenario_project_without_ticket_omits_tag()
        await _scenario_quote_has_client_no_ticket()
        await _scenario_financial_sanitization_multiple_currencies()
        await _scenario_no_client_no_project_still_works()
        await _e2e()
    asyncio.run(_run_all())


# ---------- E2E kept as trivial passthrough (real work in test_all_notification_scenarios) ----------

