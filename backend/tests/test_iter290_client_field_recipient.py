"""Iter 290 — Fix: whitelist ALLOWED_RECIPIENT_TYPES ahora incluye 'client_field'.

Casos validados:
  1) PUT /api/other-actions/configs con recipient type='client_field'
     (user_id=null, delivery_channel='email') para action_id='taller_recepcion_equipos'
     → HTTP 200 y persiste (antes 400 'Tipo de destinatario inválido: client_field').
  2) type='client_field' con delivery_channel='inbox' → guarda 200 y fuerza 'email' en respuesta.
  3) Regresión: tipos existentes con user_id/session_user/session_executive/
     project_implementer/integrator_user siguen funcionando (200); user sin user_id → 400.

Cleanup: al finalizar borra el doc db.other_action_configs para
'taller_recepcion_equipos' (estaba vacío antes de este run — verificado).
"""
import os
import time

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL no seteado")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
ACTION_ID = "taller_recepcion_equipos"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"login falló: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("session_token") or body.get("token") or body.get("access_token")
    assert tok, f"token vacío en respuesta login: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module", autouse=True)
def preserve_original_and_cleanup():
    """Guarda el doc existente (si lo hay) y lo restaura/borra al final."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    original = db.other_action_configs.find_one({"action_id": ACTION_ID})
    yield
    # Teardown: restaurar exactamente el estado previo.
    if original is None:
        db.other_action_configs.delete_one({"action_id": ACTION_ID})
    else:
        db.other_action_configs.replace_one(
            {"action_id": ACTION_ID}, original, upsert=True
        )
    client.close()


# ---------- Helpers ----------
def _put_config(headers, recipients, enabled=True):
    payload = {"action_id": ACTION_ID, "enabled": enabled, "recipients": recipients}
    return requests.put(
        f"{BASE_URL}/api/other-actions/configs", json=payload, headers=headers, timeout=30
    )


def _get_config(headers):
    return requests.get(
        f"{BASE_URL}/api/other-actions/configs/{ACTION_ID}", headers=headers, timeout=30
    )


# ---------- Tests ----------
class TestClientFieldRecipient:
    def test_1_save_client_field_email_returns_200_and_persists(self, headers):
        """El fix principal: type='client_field' + user_id=null + email → 200 y persiste."""
        recipients = [
            {
                "type": "client_field",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            }
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 200, (
            f"Esperado 200 al guardar client_field/email, obtuvo {r.status_code}: {r.text}"
        )
        body = r.json()
        assert body["action_id"] == ACTION_ID
        assert body["enabled"] is True
        assert len(body["recipients"]) == 1
        saved = body["recipients"][0]
        assert saved["type"] == "client_field"
        assert saved["user_id"] is None
        assert saved["delivery_channel"] == "email"

        # GET → debe reflejar lo persistido
        g = _get_config(headers)
        assert g.status_code == 200
        gbody = g.json()
        assert len(gbody["recipients"]) == 1
        assert gbody["recipients"][0]["type"] == "client_field"
        assert gbody["recipients"][0]["delivery_channel"] == "email"

    def test_2_client_field_inbox_is_forced_to_email(self, headers):
        """client_field es externo: inbox debe forzarse a email en persistencia."""
        recipients = [
            {
                "type": "client_field",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "inbox",  # ← debe forzarse a email
            }
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 200, (
            f"Esperado 200 con inbox→email, obtuvo {r.status_code}: {r.text}"
        )
        saved = r.json()["recipients"][0]
        assert saved["type"] == "client_field"
        assert saved["delivery_channel"] == "email", (
            f"delivery_channel debía forzarse a 'email' para client_field, quedó '{saved['delivery_channel']}'"
        )

        # GET también debe mostrar email
        g = _get_config(headers).json()
        assert g["recipients"][0]["delivery_channel"] == "email"

    def test_3_regression_user_type_without_user_id_returns_400(self, headers):
        recipients = [
            {
                "type": "user",
                "user_id": None,  # falta → 400
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            }
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 400, (
            f"user sin user_id debe devolver 400, obtuvo {r.status_code}: {r.text}"
        )
        assert "user_id" in r.text.lower()

    def test_4_regression_existing_types_still_work(self, headers):
        """Los tipos existentes se guardan sin error (200)."""
        # session_* / project_implementer / integrator_user no requieren user_id.
        recipients = [
            {
                "type": "session_user",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            },
            {
                "type": "session_executive",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "inbox",
            },
            {
                "type": "project_implementer",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            },
            {
                "type": "integrator_user",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "inbox",
            },
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 200, (
            f"Regresión tipos existentes falló ({r.status_code}): {r.text}"
        )
        body = r.json()
        types_saved = sorted([x["type"] for x in body["recipients"]])
        assert types_saved == sorted(
            ["session_user", "session_executive", "project_implementer", "integrator_user"]
        )

    def test_5_regression_user_with_user_id_works(self, headers):
        """type='user' con user_id válido devuelve 200 (regresión)."""
        # Obtener un user_id real del catálogo
        cat = requests.get(
            f"{BASE_URL}/api/other-actions/catalog", headers=headers, timeout=30
        )
        assert cat.status_code == 200
        users = cat.json().get("users", [])
        assert len(users) > 0, "No hay usuarios activos en el catálogo"
        uid = users[0]["user_id"]

        recipients = [
            {
                "type": "user",
                "user_id": uid,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            }
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 200, (
            f"user con user_id válido falló ({r.status_code}): {r.text}"
        )
        saved = r.json()["recipients"][0]
        assert saved["type"] == "user"
        assert saved["user_id"] == uid

    def test_6_invalid_recipient_type_still_rejected(self, headers):
        """Un tipo no whitelisted sigue devolviendo 400 con mensaje claro."""
        recipients = [
            {
                "type": "wildcard_bogus",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            }
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 400
        assert "wildcard_bogus" in r.text or "inválido" in r.text.lower()

    def test_7_mixed_row_client_field_and_user(self, headers):
        """Config mixta client_field + user con user_id → 200 y ambas persisten."""
        cat = requests.get(
            f"{BASE_URL}/api/other-actions/catalog", headers=headers, timeout=30
        )
        uid = cat.json()["users"][0]["user_id"]

        recipients = [
            {
                "type": "user",
                "user_id": uid,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            },
            {
                "type": "client_field",
                "user_id": None,
                "template_id": None,
                "send_pdf_attachments": False,
                "delivery_channel": "email",
            },
        ]
        r = _put_config(headers, recipients)
        assert r.status_code == 200, f"mix falló: {r.status_code} {r.text}"
        body = r.json()
        types = sorted([x["type"] for x in body["recipients"]])
        assert types == ["client_field", "user"]

        # GET también debe reflejar 2 rows persistidos
        g = _get_config(headers).json()
        assert len(g["recipients"]) == 2
