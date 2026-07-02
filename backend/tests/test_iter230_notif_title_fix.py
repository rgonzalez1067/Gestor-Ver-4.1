"""Iter 230 — Backend test for cosmetic fix on notification push title.

Bug: al enviar notificación de proyecto con target=client, el título de la
notificación push (evento bank_notified_in_project) mostraba
"Banco None notificado" (dando impresión de error).

Fix (routes/projects.py ~L1629): título dinámico según target:
  - target='client' o 'client_avance' o similar sin banco  → "Cliente notificado"
  - target='bank'                                          → "Banco {name} notificado"
  - target='bank_client'                                   → "Cliente + Banco {name} notificado"
Además: el `message` ya no contiene "Target:" (ahora solo trae
  "Proyecto {n} · Nivel {prefix_label}").

Esta suite dispara POST /api/projects/{id}/send-notification con distintos
targets y verifica el título/mensaje de la notificación push generada
usando el feed global GET /api/notifications/recent-activity (admin only).
"""

import os
import time
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "prj_e86a47af1bff"  # PRY-2026-05-002-PRI con dos bancos en matriz
DUMMY_TO = ["qatest_iter230@example.com"]


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def project(auth_headers):
    r = requests.get(f"{BASE_URL}/api/projects/{PROJECT_ID}", headers=auth_headers, timeout=15)
    assert r.status_code == 200, f"project not found: {r.status_code} {r.text}"
    return r.json()


def _send_notification(auth_headers, target, bank_name=None, to_override=None):
    """POST /api/projects/{id}/send-notification (multipart/form-data)."""
    data = {
        "target": target,
        "bank_name": bank_name or "",
        "additional_recipients": "[]",
        "to_override": json.dumps(to_override or DUMMY_TO),
        "custom_html": "",
        "custom_subject": "",
        "template_id": "",
        "attach_matrix": "false",
    }
    return requests.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification",
        data=data,
        headers=auth_headers,
        timeout=45,
    )


def _fetch_latest_push_for_project(auth_headers, project_id=PROJECT_ID, limit=30):
    """Uses admin-only feed /api/notifications/recent-activity.

    Returns the newest 'bank_notified_in_project' item for the given project.
    """
    r = requests.get(
        f"{BASE_URL}/api/notifications/recent-activity",
        params={"limit": limit},
        headers=auth_headers,
        timeout=15,
    )
    assert r.status_code == 200, f"recent-activity {r.status_code} {r.text}"
    items = r.json().get("items", [])
    for n in items:  # already ordered created_at desc
        if n.get("event_type") == "bank_notified_in_project" and n.get("project_id") == project_id:
            return n
    return None


# --------------------------------------------------------------------------- #
#  Regresión: send-notification devuelve 200 y respuesta con message éxito    #
# --------------------------------------------------------------------------- #

class TestSendNotificationRegression:
    def test_target_client_returns_200_and_success_message(self, auth_headers, project):
        # Ensure project has at least one client history so bank tests later can run
        resp = _send_notification(auth_headers, target="client")
        assert resp.status_code == 200, f"expected 200, got {resp.status_code} {resp.text}"
        payload = resp.json()
        assert "message" in payload
        assert payload.get("target") == "client"
        # Status del email service puede ser 'ok' | 'sent' | 'error_smtp' etc., pero endpoint mismo debe 200

    def test_target_bank_returns_200(self, auth_headers, project):
        bank_names = list((project.get("implementation_matrix") or {}).keys())
        assert bank_names, "project has no banks in implementation_matrix"
        bank = bank_names[0]
        # small delay so the previous send's push has a distinct created_at second
        time.sleep(1.2)
        resp = _send_notification(auth_headers, target="bank", bank_name=bank)
        assert resp.status_code == 200, f"expected 200, got {resp.status_code} {resp.text}"
        payload = resp.json()
        assert payload.get("target") == "bank"
        assert payload.get("bank_name") == bank


# --------------------------------------------------------------------------- #
#  Fix del título de la notificación push                                     #
# --------------------------------------------------------------------------- #

class TestPushNotificationTitleFix:
    """Verifica el bug fix: título legible según destinatario, sin 'Banco None'."""

    def test_client_target_title_is_cliente_notificado(self, auth_headers, project):
        # Trigger fresh client send so the push is the newest one
        time.sleep(1.2)
        resp = _send_notification(auth_headers, target="client")
        assert resp.status_code == 200, resp.text
        time.sleep(1.5)  # give time for background push write

        notif = _fetch_latest_push_for_project(auth_headers)
        assert notif is not None, "no bank_notified_in_project push found for project"
        title = notif.get("title", "")
        message = notif.get("message", "")

        # ---- Regression: NEVER 'Banco None notificado' ----
        assert "Banco None" not in title, (
            f"BUG REGRESSION: title still contains 'Banco None' -> {title!r}"
        )
        # ---- Expected exact title ----
        assert title == "Cliente notificado", (
            f"expected 'Cliente notificado', got {title!r}"
        )
        # ---- Message no longer contains 'Target:' ----
        assert "Target:" not in message, (
            f"message should not contain 'Target:' anymore -> {message!r}"
        )
        # ---- Message keeps expected structure ----
        assert "Proyecto" in message and "Nivel" in message, (
            f"expected 'Proyecto ... Nivel ...' in message -> {message!r}"
        )

    def test_bank_target_title_is_banco_named(self, auth_headers, project):
        bank_names = list((project.get("implementation_matrix") or {}).keys())
        assert bank_names, "no banks in matrix"
        bank = bank_names[0]

        time.sleep(1.2)
        resp = _send_notification(auth_headers, target="bank", bank_name=bank)
        assert resp.status_code == 200, resp.text
        time.sleep(1.5)

        notif = _fetch_latest_push_for_project(auth_headers)
        assert notif is not None, "no bank_notified push found"
        title = notif.get("title", "")

        # never 'Banco None'
        assert "Banco None" not in title
        assert title == f"Banco {bank} notificado", (
            f"expected 'Banco {bank} notificado', got {title!r}"
        )
        assert "Target:" not in (notif.get("message") or "")

    def test_bank_client_target_title(self, auth_headers, project):
        bank_names = list((project.get("implementation_matrix") or {}).keys())
        assert bank_names, "no banks in matrix"
        bank = bank_names[-1]  # usar el último para diferenciarlo

        time.sleep(1.2)
        resp = _send_notification(auth_headers, target="bank_client", bank_name=bank)
        assert resp.status_code == 200, resp.text
        time.sleep(1.5)

        notif = _fetch_latest_push_for_project(auth_headers)
        assert notif is not None, "no bank_notified push found for bank_client"
        title = notif.get("title", "")

        assert "Banco None" not in title
        assert title == f"Cliente + Banco {bank} notificado", (
            f"expected 'Cliente + Banco {bank} notificado', got {title!r}"
        )
        assert "Target:" not in (notif.get("message") or "")
