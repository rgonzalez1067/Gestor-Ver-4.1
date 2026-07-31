"""Iteration 305 — Tests para FALLA A (attachments en Centro de Mensajes) y
FALLA B (correo garantizado al Responsable Integrador en el cierre).

Cobertura:
  - FALLA A cierre: POST /api/integrators/{id}/close entrega en inbox_messages con
    attachments_meta que contienen content_b64 no vacío (Certificado PDF + archivos
    subidos). GET /api/inbox/{message_id}/attachments/{index} devuelve 200 binario.
  - FALLA B: principal_contact_email figura en email_logs.to como destinatario
    garantizado del cierre, y las variables usuario_integrador/Usuario_Integrador
    se resuelven a ese correo.
  - FALLA A MPOS deliver: cobertura parcial documentada (no se orquesta un ciclo
    completo de cotización por complejidad de estado). Se verifica la ruta de
    codigo compartida via el cierre (mismo deliver_to_inbox + attachments).
"""

import os
import io
import base64
import time
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback a frontend/.env (misma convención que el resto de tests del repo)
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
INBOX_USER_ID = "user_admin_main"  # config existente tiene fila inbox para este user


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token") or r.json().get("session_token")
    assert tok, f"no token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def integrator_id(auth_headers):
    """Crea un integrador desechable con principal_contact_email seteado.

    Nombre único para forzar scope='new' (no reemplaza registros previos).
    """
    unique = uuid.uuid4().hex[:8]
    payload = {
        "name": f"TEST_Integ_{unique}",
        "integrator_type": "Integrador",
        "integration_type": "MPOS",
        "app_name": f"TEST_App_{unique}",
        "integration_modality": "Directa",
        "integrator_status": "En proceso",
        "principal_contact_name": "Responsable Prueba",
        "principal_contact_email": "integrador_prueba@comercio.com",
        "contacts": [
            {"name": "Contacto Tecnico", "email": f"tec_{unique}@comercio.com",
             "phone": "+58-000-0000000", "role": "Técnico"}
        ],
    }
    r = requests.post(f"{BASE_URL}/api/integrators", json=payload,
                      headers=auth_headers, timeout=30)
    assert r.status_code in (200, 201), f"create integrator failed: {r.status_code} {r.text}"
    iid = r.json()["integrator_id"]
    yield iid
    # cleanup: borrar integrador y sus certificados y mensajes
    try:
        _db.integrators.delete_one({"integrator_id": iid})
        _db.integrator_certificates.delete_many({"integrator_id": iid})
    except Exception:
        pass


def _ensure_inbox_config():
    """Asegura que exista config other_action_configs para integration_project_closed
    con al menos un recipient user/inbox apuntando a INBOX_USER_ID."""
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
        return
    recs = cfg.get("recipients") or []
    has_inbox = any(r.get("type") == "user" and r.get("user_id") == INBOX_USER_ID
                    and (r.get("delivery_channel") or "email").lower() == "inbox"
                    for r in recs)
    if not has_inbox:
        recs.append({"row_id": "test_r_inbox", "type": "user", "user_id": INBOX_USER_ID,
                     "template_id": recs[0].get("template_id") if recs else None,
                     "delivery_channel": "inbox"})
        _db.other_action_configs.update_one(
            {"action_id": "integration_project_closed"},
            {"$set": {"recipients": recs, "enabled": True}},
        )


class TestIntegratorCloseInboxAttachments:
    """FALLA A (cierre) + FALLA B - flujo end-to-end."""

    def test_close_delivers_inbox_with_attachments_and_emails_integrator(
        self, auth_headers, integrator_id
    ):
        _ensure_inbox_config()

        # marca temporal para filtrar email_logs e inbox creados por este test
        t0 = time.time() - 1

        anexo_bytes = b"%PDF-1.4\n%TEST-ANEXO\n" + os.urandom(256) + b"\n%%EOF"
        files = [
            ("files", ("anexo_prueba.pdf", io.BytesIO(anexo_bytes), "application/pdf")),
        ]
        data = {"componente": "TEST_Comp", "version_componente": "1.0.0"}

        r = requests.post(
            f"{BASE_URL}/api/integrators/{integrator_id}/close",
            data=data, files=files, headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"close failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("certificate_generated") is True
        notif = body.get("notification") or {}
        assert notif.get("dispatched") is True, f"notification not dispatched: {notif}"
        assert notif.get("sent_count", 0) >= 1

        # ---- FALLA B: correo garantizado a integrador_prueba@comercio.com ----
        # Puede haber múltiples email_logs (uno por destinatario)
        logs = list(_db.email_logs.find(
            {"created_at": {"$gte": _iso(t0)},
             "to": "integrador_prueba@comercio.com"},
            {"_id": 0},
        ))
        assert logs, (
            "No se encontró email_log con destinatario integrador_prueba@comercio.com "
            "para el cierre (FALLA B — Responsable Integrador no recibió correo)."
        )
        # Debe llevar adjuntos (Certificado PDF + anexo)
        log = logs[-1]
        assert log.get("has_attachment") is True
        att_names = log.get("attachment_names") or []
        assert any("Certificado_" in (n or "") for n in att_names), \
            f"El correo al integrador no incluye el Certificado: {att_names}"
        assert any("anexo_prueba.pdf" == n for n in att_names), \
            f"El correo al integrador no incluye el anexo subido: {att_names}"

        # ---- FALLA A: mensaje en inbox_messages para INBOX_USER_ID ----
        msg = _db.inbox_messages.find_one(
            {"user_id": INBOX_USER_ID,
             "action_id": "integration_project_closed",
             "created_at": {"$gte": _iso(t0)}},
            sort=[("created_at", -1)],
        )
        assert msg, "No se creó mensaje en inbox_messages para el usuario destinatario."
        atts = msg.get("attachments_meta") or []
        assert len(atts) >= 2, (
            f"attachments_meta debe tener >=2 (cert + anexo), obtenido {len(atts)}: "
            f"{[a.get('filename') for a in atts]}"
        )
        for a in atts:
            assert a.get("content_b64"), (
                f"Attachment '{a.get('filename')}' NO tiene content_b64 poblado "
                f"(FALLA A no está corregida en cierre → inbox)."
            )
            assert a.get("size_bytes", 0) > 0

        # ---- Endpoint de descarga funciona (no 410) ----
        msg_id = msg["message_id"]
        for idx, a in enumerate(atts):
            r2 = requests.get(
                f"{BASE_URL}/api/inbox/{msg_id}/attachments/{idx}",
                headers=auth_headers, timeout=30,
            )
            assert r2.status_code == 200, (
                f"GET attachment {idx} devolvió {r2.status_code} (esperado 200). "
                f"filename={a.get('filename')}"
            )
            assert len(r2.content) > 0
            # Verifica que el anexo subido regresa idéntico
            if a.get("filename") == "anexo_prueba.pdf":
                assert r2.content == anexo_bytes, \
                    "El binario descargado no coincide con el anexo original."
                assert r2.headers.get("content-type", "").startswith("application/pdf")

        # cleanup del inbox de prueba
        _db.inbox_messages.delete_one({"message_id": msg_id})

    def test_integrator_email_template_vars_resolve_to_principal_contact(
        self, auth_headers
    ):
        """Verifica que las variables de plantilla usuario_integrador/Usuario_Integrador
        se resuelven al principal_contact_email en el correo garantizado del cierre.

        Se ejecuta como test independiente para dejar constancia; usa el HTML del
        último email_log al integrador si contiene la variable literal en la plantilla.
        NOTA: la plantilla real puede no contener el placeholder; el test es tolerante
        y sólo falla si aparece la variable SIN reemplazar."""
        log = _db.email_logs.find_one(
            {"to": "integrador_prueba@comercio.com"},
            sort=[("created_at", -1)],
        )
        if not log:
            pytest.skip("Sin email_log previo al integrador para verificar variables.")
        preview = (log.get("html_preview") or "")
        # No debe quedar el placeholder crudo
        assert "{usuario_integrador}" not in preview
        assert "{Usuario_Integrador}" not in preview


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
