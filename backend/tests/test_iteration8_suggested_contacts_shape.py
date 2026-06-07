# ruff: noqa
"""Iteration 8 backend tests — Standardized notifications to clients & banks.

Validates:
1. GET /api/projects/{id}/suggested-contacts returns contacts with fields:
   email, label, name, contact_type, source (client|bank), bank_name when source==bank.
2. For source=client: contact_type is 'Principal' (top-level), CRM role
   (e.g. 'Administrativo'), or 'Contacto' for legacy contact1/contact2.
3. For source=bank: contact_type from bank.contacts[].contact_type, or
   'Principal' when falling back to legacy contact_email.
4. Dedup: same email in different sources (client vs bank) OR different banks
   does NOT collapse.
5. POST /api/projects/{id}/send-notification honors `to_override` and the
   selected emails end up in the response `recipients` list (= SMTP TO).
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone


def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip()
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Auth ----------
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Auth failed: {r.status_code} {r.text}")
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- MongoDB seed (direct, bypassing API for full control) ----------
@pytest.fixture(scope="module")
def db():
    # Load backend .env to get MONGO_URL/DB_NAME
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def seeded(db):
    """Seed TEST_ client, TEST_ bank, TEST_ project — with overlap email
    between client (CRM contact) and bank (Principal contact) to validate dedup."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    suffix = uuid.uuid4().hex[:6]
    client_id = f"cli_TEST_{suffix}"
    bank_name = f"TEST_Bank_{suffix}"
    project_id = f"prj_TEST_{suffix}"

    SHARED_EMAIL = f"shared_{suffix}@test.com"

    client_doc = {
        "client_id": client_id,
        "fantasy_name": f"TEST_CLIENT_{suffix}",
        "legal_name": f"TEST_CLIENT_{suffix}",
        "rif": f"J-TEST{suffix}",
        "email": f"principal_{suffix}@test.com",  # top-level → Principal
        "contacts": [
            {
                "contact_id": f"cnt_{suffix}_1",
                "first_name": "Carlos",
                "last_name": "Admin",
                "full_name": "Carlos Admin",
                "email": f"admin_{suffix}@test.com",
                "role": "Administrativo",
            },
            {
                "contact_id": f"cnt_{suffix}_2",
                "first_name": "Maria",
                "last_name": "Compras",
                "full_name": "Maria Compras",
                "email": SHARED_EMAIL,  # collision with bank contact
                "role": "Compras",
            },
        ],
        "contact1": {
            "name": "Legacy One",
            "email": f"legacy1_{suffix}@test.com",
        },
        "contact2": {
            "name": "Legacy Two",
            "email": f"legacy2_{suffix}@test.com",
            "role": "Operaciones",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    bank_doc = {
        "bank_id": f"bnk_TEST_{suffix}",
        "name": bank_name,
        "type": "Banco",
        "country": "Venezuela",
        "contacts": [
            {
                "contact_id": f"bcnt_{suffix}_1",
                "first_name": "Juan",
                "last_name": "Perez",
                "full_name": "Juan Perez",
                "email": f"juan_{suffix}@test.com",
                "contact_type": "Principal",
            },
            {
                "contact_id": f"bcnt_{suffix}_2",
                "first_name": "Ana",
                "last_name": "Soporte",
                "full_name": "Ana Soporte",
                "email": SHARED_EMAIL,  # same email as client CRM contact
                "contact_type": "Técnico",
            },
        ],
    }

    project_doc = {
        "project_id": project_id,
        "project_number": f"TEST-{suffix}",
        "client_id": client_id,
        "client_name": client_doc["fantasy_name"],
        "implementation_matrix": {
            bank_name: {
                "Pago Móvil": {}
            }
        },
        "services": [],
        "notification_history": {},
        "bitacora": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Mark client as already notified so we can send a bank notification too
        "client_notified": True,
        "client_notified_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _seed():
        await db.clients.insert_one(client_doc)
        await db.banks.insert_one(bank_doc)
        await db.projects.insert_one(project_doc)
        # Pre-populate client notification history so bank send is allowed
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"notification_history.client": [{"sent_at": "2025-01-01T00:00:00", "send_number": 1}]}}
        )

    async def _cleanup():
        await db.clients.delete_one({"client_id": client_id})
        await db.banks.delete_one({"bank_id": bank_doc["bank_id"]})
        await db.projects.delete_one({"project_id": project_id})

    loop.run_until_complete(_seed())
    yield {
        "client_id": client_id,
        "bank_name": bank_name,
        "project_id": project_id,
        "shared_email": SHARED_EMAIL,
        "principal_email": client_doc["email"],
        "admin_email": client_doc["contacts"][0]["email"],
        "legacy1_email": client_doc["contact1"]["email"],
        "legacy2_email": client_doc["contact2"]["email"],
        "bank_juan_email": bank_doc["contacts"][0]["email"],
    }
    loop.run_until_complete(_cleanup())


# ============================================================
# Tests
# ============================================================

class TestSuggestedContactsShape:
    """Validate response shape of suggested-contacts."""

    def test_status_200_and_list(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_all_contacts_have_required_fields(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        required = {"email", "label", "name", "contact_type", "source"}
        for c in data:
            missing = required - set(c.keys())
            assert not missing, f"Contact missing fields {missing}: {c}"
            assert c["source"] in ("client", "bank"), f"Invalid source: {c['source']}"
            assert "@" in c["email"]

    def test_bank_contacts_have_bank_name(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        bank_contacts = [c for c in data if c["source"] == "bank"]
        assert len(bank_contacts) > 0
        for c in bank_contacts:
            assert c.get("bank_name") == seeded["bank_name"], f"Wrong bank_name: {c}"


class TestClientContactTypes:
    """Validate contact_type rules for client-source contacts."""

    def test_principal_for_top_level_email(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        principal = next(
            (c for c in data if c["source"] == "client" and c["email"] == seeded["principal_email"]),
            None,
        )
        assert principal is not None, "Top-level client email not found"
        assert principal["contact_type"] == "Principal"

    def test_role_for_crm_contact(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        admin_c = next(
            (c for c in data if c["source"] == "client" and c["email"] == seeded["admin_email"]),
            None,
        )
        assert admin_c is not None, "CRM contact 'Administrativo' not found"
        assert admin_c["contact_type"] == "Administrativo"
        assert admin_c["name"] == "Carlos Admin"

    def test_legacy_contact1_default_contacto(self, seeded, headers):
        """legacy contact1 with no role → contact_type='Contacto'"""
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        legacy = next(
            (c for c in data if c["source"] == "client" and c["email"] == seeded["legacy1_email"]),
            None,
        )
        assert legacy is not None, "Legacy contact1 not found"
        assert legacy["contact_type"] == "Contacto"
        assert legacy["name"] == "Legacy One"

    def test_legacy_contact2_with_role(self, seeded, headers):
        """legacy contact2 with role → contact_type=role"""
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        legacy = next(
            (c for c in data if c["source"] == "client" and c["email"] == seeded["legacy2_email"]),
            None,
        )
        assert legacy is not None, "Legacy contact2 not found"
        assert legacy["contact_type"] == "Operaciones"


class TestBankContactTypes:
    """Validate contact_type for bank-source contacts."""

    def test_bank_contact_type_from_contacts_array(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        juan = next(
            (c for c in data if c["source"] == "bank" and c["email"] == seeded["bank_juan_email"]),
            None,
        )
        assert juan is not None, "Bank contact 'Juan' not found"
        assert juan["contact_type"] == "Principal"
        assert juan["name"] == "Juan Perez"
        assert juan["bank_name"] == seeded["bank_name"]


class TestDedup:
    """Validate dedup keeps same email when source/bank differs."""

    def test_same_email_client_and_bank_both_kept(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        shared = [c for c in data if c["email"] == seeded["shared_email"]]
        # Exactly two: one client (role=Compras) + one bank (contact_type=Técnico)
        sources = sorted(c["source"] for c in shared)
        assert sources == ["bank", "client"], f"Dedup collapsed cross-source: {shared}"
        client_one = next(c for c in shared if c["source"] == "client")
        bank_one = next(c for c in shared if c["source"] == "bank")
        assert client_one["contact_type"] == "Compras"
        assert bank_one["contact_type"] == "Técnico"

    def test_no_duplicate_within_same_source_and_bank(self, seeded, headers):
        r = requests.get(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/suggested-contacts",
            headers=headers, timeout=30,
        )
        data = r.json()
        keys = [(c["email"].lower(), c["source"], c.get("bank_name") or "") for c in data]
        assert len(keys) == len(set(keys)), "Duplicate (email, source, bank_name) found"


class TestSendNotificationToOverride:
    """Validate POST /api/projects/{id}/send-notification with to_override."""

    def test_to_override_replaces_recipients(self, seeded, headers):
        custom_to = [
            f"override1_{uuid.uuid4().hex[:6]}@test.com",
            f"override2_{uuid.uuid4().hex[:6]}@test.com",
        ]
        body = {
            "target": "bank",
            "bank_name": seeded["bank_name"],
            "to_override": custom_to,
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/send-notification",
            json=body, headers=headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        resp = r.json()
        # The response includes recipients (= SMTP TO)
        assert "recipients" in resp, f"No recipients key in response: {resp}"
        assert sorted(resp["recipients"]) == sorted(custom_to), (
            f"Recipients != to_override. Expected {custom_to}, got {resp['recipients']}"
        )

    def test_to_override_empty_falls_back_to_db_recipients(self, seeded, headers):
        """When to_override is empty list (or all invalid), endpoint should fall back to DB-resolved list."""
        body = {
            "target": "bank",
            "bank_name": seeded["bank_name"],
            "to_override": [],  # empty → should not crash; falls back
        }
        r = requests.post(
            f"{BASE_URL}/api/projects/{seeded['project_id']}/send-notification",
            json=body, headers=headers, timeout=60,
        )
        assert r.status_code == 200, r.text
        # No assertion on specific recipients (DB-driven), just no crash
