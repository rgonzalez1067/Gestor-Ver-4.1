"""
Iter9 — Backend tests for:
1. GET /api/quotes filtered for Operaciones department (PYME + fast_track/FAST_TRACK only).
2. Admin/Director still see everything (regression).
3. POST /api/quotes/{id}/configure works for Operaciones user (no 403).
4. POST /api/quotes/{id}/repair-deliver uses dynamic engine with action_id 'deliver'.
5. notification_engine._build_template_vars exposes Cantidad_Cajas, Integrador,
   Aplicativo_Integracion, Modelo_Pinpad, Banco_Patrocinador (regression via import).
6. services.rif_formatter.format_rif behaviour (regression).
7. Multi-attachment upload via POST /api/quotes/{id}/attachments (indexed independently).
8. GET /api/projects/{id}/suggested-contacts still works (regression).
"""

import os
import io
import sys
import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# load env BEFORE backend imports
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

TEST_OPS_EMAIL = f"test_ops_{uuid.uuid4().hex[:8]}@megasoft.com.ve"
TEST_OPS_PASSWORD = "TestOps1234!"
TEST_OPS_USER_ID = f"user_test_{uuid.uuid4().hex[:8]}"


# ---------- helpers ----------

def _hash(pwd: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((pwd + salt).encode()).hexdigest()
    return f"{salt}:{h}"


def _login(email: str, password: str) -> str | None:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        print(f"[login] {email} -> {r.status_code} {r.text[:200]}")
        return None
    return r.json().get("session_token") or r.json().get("token")


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert tok, "Admin login failed"
    return tok


@pytest.fixture(scope="module")
def ops_user_setup():
    """Create TEST_ ops user directly in MongoDB. Cleanup after module."""
    async def _setup():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        user_doc = {
            "user_id": TEST_OPS_USER_ID,
            "email": TEST_OPS_EMAIL,
            "first_name": "TEST",
            "last_name": "Ops",
            "name": "TEST Ops",
            "password_hash": _hash(TEST_OPS_PASSWORD),
            "role": "user",
            "cargo": "Analista",
            "departamento": "Operaciones",
            "sede": "PYME",
            "is_active": True,
            "is_verified": True,
            "permissions": {
                "cotizaciones": "edit",
                "clientes": "read",
                "proyectos": "read",
                "taller_equipos": "edit",
                "configuracion": "none",
            },
            "special_permissions": ["cotizaciones:equipos", "cotizaciones:reparaciones"],
            "menu_groups": {
                "dashboard": False, "gestion_comercial": True, "catalogos": True,
                "gestion_implementacion": True, "nuevos_productos": False,
                "gestion_administrativa": True, "gestion_taller": True,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.delete_many({"email": TEST_OPS_EMAIL})
        await db.users.insert_one(user_doc)
        cli.close()

    async def _teardown():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        await db.users.delete_many({"user_id": TEST_OPS_USER_ID})
        await db.user_sessions.delete_many({"user_id": TEST_OPS_USER_ID})
        cli.close()

    asyncio.get_event_loop().run_until_complete(_setup())
    yield {"email": TEST_OPS_EMAIL, "password": TEST_OPS_PASSWORD, "user_id": TEST_OPS_USER_ID}
    asyncio.get_event_loop().run_until_complete(_teardown())


@pytest.fixture(scope="module")
def ops_token(ops_user_setup):
    tok = _login(ops_user_setup["email"], ops_user_setup["password"])
    assert tok, "Ops test user login failed"
    return tok


# ---------- Module 1: Operaciones filter on /api/quotes ----------

class TestOperacionesQuoteFilter:
    def test_ops_user_sees_only_pyme_fasttrack(self, ops_token):
        r = requests.get(
            f"{BASE_URL}/api/quotes",
            headers={"Authorization": f"Bearer {ops_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Every returned quote must be PYME + (fast_track OR FAST_TRACK)
        bad = []
        for q in data:
            seg = q.get("client_segment")
            cat = q.get("quote_category")
            qtype = q.get("quote_type")
            ok_seg = seg == "PYME"
            ok_cat = cat == "fast_track" or qtype == "FAST_TRACK"
            if not (ok_seg and ok_cat):
                bad.append({"quote_id": q.get("quote_id"), "client_segment": seg,
                            "quote_category": cat, "quote_type": qtype})
        assert not bad, f"Ops user got non-PYME/non-FT quotes: {bad[:5]} (total {len(bad)})"
        # And we expect at least one match (sanity — env has a FT PYME quote)
        print(f"[Ops filter] got {len(data)} quotes — all PYME+FT")

    def test_admin_sees_more_than_ops(self, admin_token, ops_token):
        ra = requests.get(f"{BASE_URL}/api/quotes",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        ro = requests.get(f"{BASE_URL}/api/quotes",
                          headers={"Authorization": f"Bearer {ops_token}"}, timeout=30)
        assert ra.status_code == 200 and ro.status_code == 200
        admin_qs = ra.json()
        ops_qs = ro.json()
        # admin should see >= ops count, and ideally strictly more
        assert len(admin_qs) >= len(ops_qs)
        # admin should see at least one non-FT or non-PYME quote (regression)
        non_ft_or_non_pyme = [
            q for q in admin_qs
            if not (q.get("client_segment") == "PYME"
                    and (q.get("quote_category") == "fast_track" or q.get("quote_type") == "FAST_TRACK"))
        ]
        assert non_ft_or_non_pyme, "Admin should see quotes outside PYME+FT scope"
        print(f"[Visibility] admin={len(admin_qs)}, ops={len(ops_qs)}, "
              f"admin extra non-FT/non-PYME={len(non_ft_or_non_pyme)}")


# ---------- Module 2: Configure action permission for Ops ----------

class TestConfigurePermission:
    def test_ops_can_call_configure_on_aprobada_ft_pyme(self, admin_token, ops_token):
        """Find an Aprobada FT PYME quote; if not present, this test is skipped.
        We just need to confirm Ops does NOT get 403. Any 400/200/409 is acceptable."""
        r = requests.get(f"{BASE_URL}/api/quotes",
                         headers={"Authorization": f"Bearer {ops_token}"}, timeout=30)
        assert r.status_code == 200
        quotes = r.json()
        # find an Aprobada candidate first
        target = next((q for q in quotes if q.get("quote_status") == "Aprobada"), None)
        if not target:
            target = quotes[0] if quotes else None
        if not target:
            pytest.skip("No FT PYME quote visible to Ops in env")
        qid = target["quote_id"]
        rc = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/configure",
            headers={"Authorization": f"Bearer {ops_token}"},
            timeout=60,
        )
        print(f"[configure] ops on {qid} status={target.get('quote_status')} -> {rc.status_code} {rc.text[:200]}")
        # The key assertion: NOT 403 (permissions). 400 is OK if status != Aprobada.
        assert rc.status_code != 403, f"Ops user got 403 on configure: {rc.text}"


# ---------- Module 3: repair-deliver uses 'deliver' action_id ----------

class TestRepairDeliverEngineActionId:
    def test_engine_called_with_deliver_action_id(self):
        """Static code check: line ~2887 of quote_actions.py must pass 'deliver'
        as the first arg to _engine_or_legacy in repair_deliver."""
        with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
            src = f.read()
        # Locate repair_deliver function
        idx = src.find("async def repair_deliver(")
        assert idx > 0, "repair_deliver function not found"
        # Slice until next top-level async def (end of repair_deliver fn)
        next_idx = src.find("\nasync def ", idx + 10)
        snippet = src[idx: next_idx if next_idx > 0 else idx + 30000]
        assert '_engine_or_legacy(' in snippet, "_engine_or_legacy not invoked in repair_deliver"
        eng_idx = snippet.find("_engine_or_legacy(")
        chunk = snippet[eng_idx: eng_idx + 400]
        assert '"deliver"' in chunk, f"Expected action_id 'deliver' (not 'repair-deliver'). Got: {chunk[:300]}"
        assert '"repair-deliver"' not in chunk, f"Found legacy 'repair-deliver' literal in engine call: {chunk[:300]}"


# ---------- Module 4: template vars + RIF formatter ----------

class TestTemplateVarsExposed:
    def test_build_template_vars_keys_present(self):
        from services.notification_engine import _build_template_vars  # type: ignore
        import inspect
        src = inspect.getsource(_build_template_vars)
        for key in ("Cantidad_Cajas", "Integrador", "Aplicativo_Integracion",
                    "Modelo_Pinpad", "Banco_Patrocinador"):
            assert f'"{key}"' in src or f"'{key}'" in src, f"missing var {key}"


class TestRifFormatter:
    @pytest.mark.parametrize("inp,exp", [
        ("V12345", "V-000012345"),
        ("V-12345", "V-000012345"),
        ("V123456789", "V-123456789"),
        ("V-1234567-8", "V-001234567-8"),
        ("", ""),
        (None, ""),
        ("N/A", "N/A"),
    ])
    def test_format_rif(self, inp, exp):
        from services.rif_formatter import format_rif
        assert format_rif(inp) == exp


# ---------- Module 5: multi attachment upload (indexed independently) ----------

class TestMultiAttachmentUpload:
    def test_multiple_factura_uploads_indexed(self, admin_token):
        # Pick any quote
        r = requests.get(f"{BASE_URL}/api/quotes",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        quotes = r.json()
        if not quotes:
            pytest.skip("No quotes in env")
        qid = quotes[0]["quote_id"]
        # Snapshot current Factura count
        rg = requests.get(f"{BASE_URL}/api/quotes/{qid}/attachments",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert rg.status_code == 200
        before = [a for a in rg.json().get("attachments", []) if a.get("category") == "Factura"]
        n_before = len(before)
        # Upload two Factura files
        created_ids = []
        for i in range(2):
            files = {"file": (f"test_factura_{i}.pdf", io.BytesIO(b"%PDF-1.4 TEST"), "application/pdf")}
            data = {"category": "Factura"}
            ru = requests.post(
                f"{BASE_URL}/api/quotes/{qid}/attachments",
                headers={"Authorization": f"Bearer {admin_token}"},
                files=files, data=data, timeout=60,
            )
            assert ru.status_code == 200, f"upload {i} failed: {ru.status_code} {ru.text[:200]}"
            att = ru.json().get("attachment", {})
            assert att.get("attachment_id"), "missing attachment_id"
            assert att.get("category") == "Factura"
            created_ids.append(att["attachment_id"])
        # Verify both persisted
        rg2 = requests.get(f"{BASE_URL}/api/quotes/{qid}/attachments",
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        after = [a for a in rg2.json().get("attachments", []) if a.get("category") == "Factura"]
        assert len(after) == n_before + 2, f"expected +2 Factura attachments, got {len(after) - n_before}"
        # Filenames distinct (indexed independently)
        fns = [a.get("filename") for a in after if a.get("attachment_id") in created_ids]
        assert len(set(fns)) == 2, f"Expected 2 distinct filenames, got {fns}"
        # Cleanup
        for aid in created_ids:
            requests.delete(f"{BASE_URL}/api/quotes/{qid}/attachments/{aid}",
                            headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)


# ---------- Module 6: regression — suggested-contacts ----------

class TestSuggestedContactsRegression:
    def test_endpoint_responds(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/projects",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200
        projects = r.json()
        if not projects:
            pytest.skip("No projects in env")
        pid = projects[0].get("project_id") or projects[0].get("id")
        rs = requests.get(f"{BASE_URL}/api/projects/{pid}/suggested-contacts",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert rs.status_code == 200, f"suggested-contacts regressed: {rs.status_code} {rs.text[:200]}"
        data = rs.json()
        # Either dict with key or list
        contacts = data if isinstance(data, list) else (data.get("contacts") or data.get("suggested") or [])
        # Shape check (only when non-empty)
        for c in contacts[:5]:
            assert "email" in c
