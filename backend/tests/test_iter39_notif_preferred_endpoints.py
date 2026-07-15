"""
Iter39 — Plantilla Preferida + Texto Enriquecido en Notificaciones de Proyecto.
HTTP-level tests against the deployed backend.

Endpoints under test:
- GET/PUT /api/project-notification-preferences
- GET /api/email-templates?context=IMPLEMENTACION (debe listar defaults de Proyecto)
- POST /api/projects/{id}/preview-notification (con template_id + custom_html)
- POST /api/projects/{id}/send-notification (con template_id + custom_html)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://dept-migration-bug.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "prj_826643491b64"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"no session_token in response: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- GET preferences returns defaults ---
def test_get_preferences_returns_three_destinations(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/project-notification-preferences", timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert "client" in data and "bank" in data and "bank_client" in data
    # Should be at least defaults
    assert data["client"] in ("project_notify_client", None) or isinstance(data["client"], str)


# --- PUT/replace preference for bank destination ---
def test_put_preference_persists_and_replaces(admin_client):
    # First PUT
    r1 = admin_client.put(
        f"{BASE_URL}/api/project-notification-preferences",
        json={"destination": "bank", "template_id": "project_notify_bank"},
        timeout=20,
    )
    assert r1.status_code == 200, r1.text[:300]
    g1 = admin_client.get(f"{BASE_URL}/api/project-notification-preferences", timeout=20).json()
    assert g1.get("bank") == "project_notify_bank"

    # Second PUT replaces
    r2 = admin_client.put(
        f"{BASE_URL}/api/project-notification-preferences",
        json={"destination": "bank", "template_id": "project_notify_bank_client"},
        timeout=20,
    )
    assert r2.status_code == 200
    g2 = admin_client.get(f"{BASE_URL}/api/project-notification-preferences", timeout=20).json()
    assert g2.get("bank") == "project_notify_bank_client"

    # Restore default
    admin_client.put(
        f"{BASE_URL}/api/project-notification-preferences",
        json={"destination": "bank", "template_id": "project_notify_bank"},
        timeout=20,
    )


def test_put_preference_invalid_destination_returns_400(admin_client):
    r = admin_client.put(
        f"{BASE_URL}/api/project-notification-preferences",
        json={"destination": "INVALID", "template_id": "project_notify_client"},
        timeout=20,
    )
    assert r.status_code in (400, 422), f"expected 400/422, got {r.status_code}: {r.text[:200]}"


def test_put_preference_unknown_template_returns_404(admin_client):
    r = admin_client.put(
        f"{BASE_URL}/api/project-notification-preferences",
        json={"destination": "client", "template_id": "no_existe_xyz"},
        timeout=20,
    )
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"


# --- email templates dropdown for IMPLEMENTACION ---
def test_email_templates_context_implementacion_lists_project_defaults(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/email-templates?context=IMPLEMENTACION", timeout=20)
    assert r.status_code == 200, r.text[:300]
    items = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("templates") or []
    ids = {t.get("id") or t.get("template_id") for t in items}
    expected = {"project_notify_client", "project_notify_bank", "project_notify_bank_client", "new_integration_project"}
    missing = expected - ids
    assert not missing, f"Missing default templates in dropdown: {missing}. Got ids: {ids}"


# --- Preview notification renders variables ---
def test_preview_notification_uses_template_and_renders_variables(admin_client):
    payload = {
        "target": "client",
        "template_id": "project_notify_client",
        "custom_html": "<p>Hola <strong>{Nombre_Cliente}</strong> — {project_number}</p>",
    }
    r = admin_client.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification", json=payload, timeout=30
    )
    assert r.status_code == 200, f"preview failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    assert "subject" in data and "html" in data
    assert data["subject"].startswith("[Primer Envío]"), f"subject prefix wrong: {data['subject']}"
    html = data["html"]
    # Variables resolved (no literal placeholders)
    assert "{Nombre_Cliente}" not in html, "Variable {Nombre_Cliente} not rendered"
    assert "{project_number}" not in html, "Variable {project_number} not rendered"
    # Expected client name appears
    assert "CAFE EUROPA" in html.upper() or "CAFE EUROPA 2015" in html.upper()


# --- Send notification: must not 500 even if Resend is not configured ---
def test_send_notification_processes_without_500(admin_client):
    payload = {
        "target": "client",
        "to_override": "qa+test@example.com",
        "template_id": "project_notify_client",
        "custom_html": "<p>QA test — {project_number}</p>",
    }
    r = admin_client.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/send-notification", json=payload, timeout=45
    )
    # Accept 200/202 (sent) or 4xx (config). NEVER 500.
    assert r.status_code != 500, f"server error on send: {r.text[:400]}"
    assert r.status_code < 500
