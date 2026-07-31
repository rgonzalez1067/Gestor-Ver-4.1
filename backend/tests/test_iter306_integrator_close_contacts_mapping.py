"""Iteration 306 — Tests para mapeo de 'Responsable Integrador' desde contacts[0]
(wizard) y validación 400 cuando no hay email válido.

Cobertura:
  A) MAPEO wizard: integrator con principal_contact_email="" y
     contacts=[{email:'integrador.desarrollo@cliente.com'}] → al cerrar, el
     email_log garantizado va a integrador.desarrollo@cliente.com Y las
     variables {usuario_integrador} se resuelven a ese correo (no quedan
     literales). El correo lleva Certificado + anexo.
  B) REGRESIÓN principal_contact_email: integrator con principal_contact_email
     válido y contacts=[] → cierre garantiza correo a ese email y variables OK.
  C) VALIDACIÓN 400: integrator sin email válido en ningún lado → POST close
     devuelve 400 con mensaje sobre 'Responsable por parte del Integrador' y
     el integrator NO cambia a 'Certificado'.
  D) FALLA A regresión: inbox_message del user destinatario incluye
     attachments_meta con content_b64 no vacío.
"""

import os
import io
import time
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
INBOX_USER_ID = "user_admin_main"


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    tok = j.get("session_token") or j.get("access_token") or j.get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(autouse=True, scope="module")
def _ensure_config():
    cfg = _db.other_action_configs.find_one({"action_id": "integration_project_closed"})
    if not cfg:
        _db.other_action_configs.insert_one({
            "action_id": "integration_project_closed",
            "enabled": True,
            "recipients": [
                {"row_id": "test_r1", "type": "user", "user_id": INBOX_USER_ID,
                 "template_id": None, "delivery_channel": "inbox"}
            ],
        })
    yield


_created_ids = []


def _create_integrator(name_suffix, principal_email="", contacts=None):
    """Crea directamente en Mongo un integrador para controlar exactamente los campos."""
    iid = f"TEST_integ_{uuid.uuid4().hex[:8]}"
    doc = {
        "integrator_id": iid,
        "name": f"TEST_Integ_{name_suffix}_{iid[-6:]}",
        "integrator_type": "Integrador",
        "integration_type": "MPOS",
        "app_name": f"TEST_App_{iid[-6:]}",
        "integration_modality": "Directa",
        "integrator_status": "En proceso",
        "project_scope": "new",
        "principal_contact_name": "Responsable Prueba" if principal_email else "",
        "principal_contact_email": principal_email or "",
        "principal_contact_phone": "+58-000-0000000" if principal_email else "",
        "contacts": contacts or [],
        "certifications": {},
        "created_at": _iso(time.time()),
    }
    _db.integrators.insert_one(doc)
    _created_ids.append(iid)
    return iid


def _cleanup():
    for iid in _created_ids:
        try:
            _db.integrators.delete_one({"integrator_id": iid})
            _db.integrator_certificates.delete_many({"integrator_id": iid})
        except Exception:
            pass


@pytest.fixture(scope="module", autouse=True)
def _teardown():
    yield
    _cleanup()


def _close_multipart(headers, iid, componente="TEST_Comp", version="1.0.0",
                     anexo_name="anexo_prueba.pdf"):
    anexo_bytes = b"%PDF-1.4\n%TEST-ANEXO\n" + os.urandom(200) + b"\n%%EOF"
    files = [("files", (anexo_name, io.BytesIO(anexo_bytes), "application/pdf"))]
    data = {"componente": componente, "version_componente": version}
    r = requests.post(
        f"{BASE_URL}/api/integrators/{iid}/close",
        data=data, files=files, headers=headers, timeout=60,
    )
    return r, anexo_bytes


# ---------- A) Caso Wizard: contacts[0].email ----------

class TestWizardContactsMapping:
    def test_close_maps_from_contacts0_email(self, auth_headers):
        target_email = "integrador.desarrollo@cliente.com"
        iid = _create_integrator(
            "wizard",
            principal_email="",  # ficha wizard NO tiene principal_contact_email
            contacts=[{"name": "Dev Contacto",
                       "email": target_email,
                       "phone": "+58-212-0000000",
                       "role": "Desarrollo"}],
        )
        t0 = time.time() - 1
        r, anexo_bytes = _close_multipart(auth_headers, iid)
        assert r.status_code == 200, f"close failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("certificate_generated") is True
        notif = body.get("notification") or {}
        assert notif.get("dispatched") is True

        # Estado del integrador: Certificado
        cur = _db.integrators.find_one({"integrator_id": iid}, {"_id": 0})
        assert cur.get("integrator_status") == "Certificado"

        # (a) email garantizado a contacts[0].email
        logs = list(_db.email_logs.find(
            {"created_at": {"$gte": _iso(t0)}, "to": target_email},
            {"_id": 0},
        ))
        assert logs, (
            f"No se encontró email_log con destinatario {target_email} "
            f"(FALLA: mapeo desde contacts[0] no funciona)."
        )
        log = logs[-1]
        assert log.get("has_attachment") is True
        att_names = log.get("attachment_names") or []
        assert any("Certificado_" in (n or "") for n in att_names), \
            f"El correo no incluye el Certificado: {att_names}"
        assert any(n == "anexo_prueba.pdf" for n in att_names), \
            f"El correo no incluye anexo: {att_names}"

        # (b) variables {usuario_integrador}/{Usuario_Integrador} resueltas
        preview = (log.get("html_preview") or "") + (log.get("body_html") or "") + \
                  (log.get("subject") or "")
        assert "{usuario_integrador}" not in preview, \
            "La variable {usuario_integrador} quedó sin resolver."
        assert "{Usuario_Integrador}" not in preview, \
            "La variable {Usuario_Integrador} quedó sin resolver."

        # (d) inbox message con attachments_meta.content_b64 no vacío
        msg = _db.inbox_messages.find_one(
            {"user_id": INBOX_USER_ID,
             "action_id": "integration_project_closed",
             "created_at": {"$gte": _iso(t0)}},
            sort=[("created_at", -1)],
        )
        if msg:
            atts = msg.get("attachments_meta") or []
            assert len(atts) >= 2, f"attachments_meta debe tener >=2, got {len(atts)}"
            for a in atts:
                assert a.get("content_b64"), \
                    f"Attachment '{a.get('filename')}' sin content_b64 (FALLA A regresión)."
            _db.inbox_messages.delete_one({"message_id": msg["message_id"]})


# ---------- B) Regresión: principal_contact_email ----------

class TestPrincipalContactEmailRegression:
    def test_close_uses_principal_contact_email_when_contacts_empty(self, auth_headers):
        target_email = "principal.responsable@empresa.com"
        iid = _create_integrator("full", principal_email=target_email, contacts=[])
        t0 = time.time() - 1
        r, _ = _close_multipart(auth_headers, iid)
        assert r.status_code == 200, f"close failed: {r.status_code} {r.text}"

        logs = list(_db.email_logs.find(
            {"created_at": {"$gte": _iso(t0)}, "to": target_email},
            {"_id": 0},
        ))
        assert logs, f"No email a principal_contact_email {target_email}"
        log = logs[-1]
        preview = (log.get("html_preview") or "") + (log.get("body_html") or "")
        assert "{usuario_integrador}" not in preview
        assert "{Usuario_Integrador}" not in preview


# ---------- C) Validación 400: sin email de responsable ----------

class TestValidationNoResponsableEmail:
    def test_close_returns_400_when_no_valid_responsable_email(self, auth_headers):
        iid = _create_integrator(
            "noemail",
            principal_email="",  # sin principal
            contacts=[{"name": "Solo nombre", "email": "", "phone": "+58-0000"},
                      {"name": "Otro", "email": "no-es-email", "phone": ""}],
        )
        r, _ = _close_multipart(auth_headers, iid)
        assert r.status_code == 400, (
            f"Se esperaba 400 por Responsable sin email válido, obtenido "
            f"{r.status_code} body={r.text[:400]}"
        )
        detail = ""
        try:
            detail = (r.json().get("detail") or "").lower()
        except Exception:
            detail = r.text.lower()
        assert "responsable" in detail and ("integrador" in detail or "e-mail" in detail
                                            or "email" in detail or "correo" in detail), \
            f"Mensaje de error no menciona 'Responsable/e-mail': {detail!r}"

        # No debe haber cambiado a Certificado
        cur = _db.integrators.find_one({"integrator_id": iid}, {"_id": 0})
        assert cur.get("integrator_status") != "Certificado", \
            "El integrador cambió a Certificado a pesar del 400 (rollback fallido)."
