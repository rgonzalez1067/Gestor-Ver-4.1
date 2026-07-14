"""
Iteration 269 — Bug fix: firma de 'Otras Notificaciones' (ad-hoc project email)
debe reflejar al USUARIO que envía (nombre/email/teléfono), NO 'CRM - Gestor'.

Endpoints bajo prueba:
  - GET  /api/projects/{project_id}/template-variables
  - POST /api/projects/{project_id}/preview-adhoc-email
  - POST /api/projects/{project_id}/send-adhoc-email    (y verificación en db.email_logs)
"""
import os
import io
import json
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
ADMIN_EXPECTED_NAME = "Rafael González"

IMPL_EMAIL = "jrojas@megasoft.com.ve"
IMPL_PASSWORD = "Test1234!"

FORBIDDEN_NAME = "CRM - Gestor"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:200]}"
    data = r.json()
    return data.get("session_token") or data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def impl_token():
    try:
        return _login(IMPL_EMAIL, IMPL_PASSWORD)
    except AssertionError:
        pytest.skip("Impl user login failed — skipping second-actor regression")


@pytest.fixture(scope="module")
def project_id(admin_token) -> str:
    """Toma cualquier proyecto existente."""
    r = requests.get(
        f"{API}/projects",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"limit": 1},
        timeout=30,
    )
    assert r.status_code == 200, f"GET /projects failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    projects = data if isinstance(data, list) else (data.get("projects") or [])
    assert projects, "No projects available to test ad-hoc email flow"
    pid = projects[0].get("project_id") or projects[0].get("id")
    assert pid, f"Project object missing id: {projects[0]}"
    return pid


# ============ 1. GET template-variables ============
class TestTemplateVariables:
    def test_admin_signature_has_admin_name(self, admin_token, project_id):
        r = requests.get(
            f"{API}/projects/{project_id}/template-variables",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        variables = r.json().get("variables", {})
        firma = variables.get("Firma_Notificacion_Global", "")
        assert firma, "Firma_Notificacion_Global missing in variables"
        assert FORBIDDEN_NAME not in firma, (
            f"[BUG] Firma contiene '{FORBIDDEN_NAME}' cuando debería ser del usuario. "
            f"Firma HTML: {firma[:400]}"
        )
        assert ADMIN_EXPECTED_NAME in firma, (
            f"Firma no incluye nombre esperado '{ADMIN_EXPECTED_NAME}'. Firma: {firma[:400]}"
        )

    def test_impl_signature_has_impl_name_not_admin(self, impl_token, project_id):
        r = requests.get(
            f"{API}/projects/{project_id}/template-variables",
            headers={"Authorization": f"Bearer {impl_token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        firma = r.json().get("variables", {}).get("Firma_Notificacion_Global", "")
        assert firma
        assert FORBIDDEN_NAME not in firma, f"[BUG] '{FORBIDDEN_NAME}' presente para user Jrojas: {firma[:400]}"
        # Debe reflejar al implementador — su email debe estar
        assert IMPL_EMAIL.lower() in firma.lower(), (
            f"Firma no incluye email del implementador. Firma: {firma[:400]}"
        )
        # Y NO debe incluir el nombre del admin (aislamiento por usuario)
        assert ADMIN_EXPECTED_NAME not in firma, (
            f"Firma de Jrojas incluye por error el nombre del admin. Firma: {firma[:400]}"
        )


# ============ 2. POST preview-adhoc-email ============
class TestPreviewAdhocEmail:
    def _preview(self, token, project_id, message):
        return requests.post(
            f"{API}/projects/{project_id}/preview-adhoc-email",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "subject": "TEST_iter269 firma ad-hoc",
                "message": message,
                "include_matrix": False,
            },
            timeout=30,
        )

    def test_preview_admin_signature(self, admin_token, project_id):
        msg = "Hola, esta es la prueba de firma. {Firma_Notificacion_Global}"
        r = self._preview(admin_token, project_id, msg)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        html = r.json().get("html", "")
        assert html, "preview html vacío"
        assert FORBIDDEN_NAME not in html, (
            f"[BUG] Preview contiene '{FORBIDDEN_NAME}'. HTML: {html[:800]}"
        )
        assert ADMIN_EXPECTED_NAME in html, (
            f"Preview no incluye nombre del admin '{ADMIN_EXPECTED_NAME}'. HTML: {html[:800]}"
        )
        # Sanity — la variable {Firma_Notificacion_Global} debe estar resuelta (no literal)
        assert "{Firma_Notificacion_Global}" not in html, "Variable no fue resuelta"

    def test_preview_impl_signature(self, impl_token, project_id):
        msg = "Prueba firma implementador. {Firma_Notificacion_Global}"
        r = self._preview(impl_token, project_id, msg)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        html = r.json().get("html", "")
        assert FORBIDDEN_NAME not in html, f"[BUG] '{FORBIDDEN_NAME}' en preview de impl: {html[:800]}"
        assert IMPL_EMAIL.lower() in html.lower(), (
            f"Preview no incluye email del implementador. HTML: {html[:800]}"
        )
        assert ADMIN_EXPECTED_NAME not in html, (
            f"Preview de impl incluye nombre del admin (aislamiento roto)."
        )


# ============ 3. POST send-adhoc-email + email_logs ============
class TestSendAdhocEmail:
    """Nota: db.email_logs solo guarda html_preview[:500]. La firma completa (con
    el nombre) cae fuera de ese truncado, así que la aserción principal aquí es
    que 'CRM - Gestor' NO aparezca ni en subject ni en preview. La presencia del
    nombre del usuario ya se valida en TestPreviewAdhocEmail (endpoint preview
    devuelve el HTML completo)."""

    ADMIN_MARKER = "TEST_iter269_ADMIN_send"
    IMPL_MARKER = "TEST_iter269_IMPL_send"

    def _send(self, token, project_id, message, subject_marker):
        data = {
            "recipients": json.dumps(["qa-test@example.com"]),
            "additional_recipients": "[]",
            "subject": subject_marker,
            "message": message,
            "matrix_html": "",
        }
        return requests.post(
            f"{API}/projects/{project_id}/send-adhoc-email",
            headers={"Authorization": f"Bearer {token}"},
            data=data,
            timeout=60,
        )

    def _find_log(self, admin_token, subject_marker):
        r = requests.get(
            f"{API}/email-logs?limit=100",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        logs = r.json().get("email_logs", [])
        for lg in logs:
            if lg.get("action") == "adhoc_project_email" and subject_marker in (lg.get("subject") or ""):
                return lg
        return None

    def test_send_admin_signature_no_crm_gestor(self, admin_token, project_id):
        msg = "{Firma_Notificacion_Global}\n\nPrueba envío ad-hoc admin."
        r = self._send(admin_token, project_id, msg, self.ADMIN_MARKER)
        assert r.status_code in (200, 202), f"send failed: {r.status_code} {r.text[:300]}"
        time.sleep(1.5)
        log = self._find_log(admin_token, self.ADMIN_MARKER)
        assert log is not None, f"No se encontró email_log con subject '{self.ADMIN_MARKER}'"
        preview = log.get("html_preview") or ""
        assert preview, "html_preview vacío"
        # Aserción principal del bug: la firma NO debe usar 'CRM - Gestor'
        assert FORBIDDEN_NAME not in preview, (
            f"[BUG] email_logs.html_preview contiene '{FORBIDDEN_NAME}': {preview[:600]}"
        )
        # Y tampoco en el subject
        assert FORBIDDEN_NAME not in (log.get("subject") or "")
        # Sanity: la variable {Firma_Notificacion_Global} debe estar resuelta
        assert "{Firma_Notificacion_Global}" not in preview, "Variable no resuelta en envío"
        # Sanity: el bloque de firma debe iniciar dentro del preview
        assert "border-top:1px solid #e5e7eb" in preview, (
            f"El bloque de firma no aparece en html_preview: {preview[:600]}"
        )

    def test_send_impl_signature_no_crm_gestor(self, impl_token, admin_token, project_id):
        msg = "{Firma_Notificacion_Global}\n\nPrueba envío ad-hoc impl."
        r = self._send(impl_token, project_id, msg, self.IMPL_MARKER)
        assert r.status_code in (200, 202), f"send impl failed: {r.status_code} {r.text[:300]}"
        time.sleep(1.5)
        log = self._find_log(admin_token, self.IMPL_MARKER)
        assert log is not None, f"No se encontró email_log del envío impl (subject='{self.IMPL_MARKER}')"
        preview = log.get("html_preview") or ""
        assert FORBIDDEN_NAME not in preview, (
            f"[BUG] email_logs impl contiene '{FORBIDDEN_NAME}': {preview[:600]}"
        )
        assert "{Firma_Notificacion_Global}" not in preview
        assert "border-top:1px solid #e5e7eb" in preview
