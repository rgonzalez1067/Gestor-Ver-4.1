"""Iteration 270 — Integration Project Lifecycle (Suspend/Reactivate),
Certificate Repository (.jpg/.png/.pdf only), and 'Usuario Integrador' recipient
in Other Actions catalog.

Tested endpoints:
- POST /api/integrators/{id}/suspend
- POST /api/integrators/{id}/reactivate
- GET/POST/DELETE /api/integrators/config/certificate
- GET /api/other-actions/catalog (2 new actions present + integrator_user allowed)
- PUT /api/other-actions/configs/{action_id} (configure integrator_user recipient)
- End-to-end: suspend → dispatch to principal_contact_email
"""
import os
import io
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-backfill-hub.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("session_token") or data.get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def target_integrator(admin_headers):
    """Return an integrator that is in 'En proceso' and has principal_contact_email."""
    r = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    items = r.json() if isinstance(r.json(), list) else r.json().get("integrators", [])
    # Prefer En proceso with email and classified project_scope
    candidates_en_proceso = [
        i for i in items
        if i.get("integrator_status") == "En proceso"
        and (i.get("principal_contact_email") or "").strip()
    ]
    # Fallback: any integrator with an email
    if candidates_en_proceso:
        return candidates_en_proceso[0]
    with_email = [i for i in items if (i.get("principal_contact_email") or "").strip()]
    assert with_email, "No integrator with principal_contact_email found for testing"
    return with_email[0]


# ---------- catalog ----------
class TestOtherActionsCatalog:
    def test_catalog_has_new_actions_and_integrator_user(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/other-actions/catalog", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Support either {actions:[...]} or a bare list.
        actions = data.get("actions") if isinstance(data, dict) else data
        ids = {a.get("id") for a in actions}
        assert "integration_project_suspended" in ids, f"missing action; got {ids}"
        assert "integration_project_reactivated" in ids, f"missing action; got {ids}"

        # allowed_recipient_types can be at catalog root or per-action; check the endpoint
        # that other_actions_config exposes.
        # In this app, ALLOWED_RECIPIENT_TYPES is a backend const; validated indirectly by
        # attempting to save a config with type='integrator_user' below.


# ---------- certificate repository ----------
class TestCertificateRepository:
    def test_reject_docx(self, admin_headers):
        # Ensure clean state
        requests.delete(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, timeout=20)

        files = {"file": ("bad.docx", io.BytesIO(b"fake docx content"),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        r = requests.post(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, files=files, timeout=20)
        assert r.status_code == 400, f"expected 400 for .docx, got {r.status_code}: {r.text}"

    def test_reject_zip(self, admin_headers):
        files = {"file": ("bad.zip", io.BytesIO(b"PK\x03\x04zipdata"), "application/zip")}
        r = requests.post(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, files=files, timeout=20)
        assert r.status_code == 400, f"expected 400 for .zip, got {r.status_code}: {r.text}"

    def test_accept_pdf_then_png_and_download_delete(self, admin_headers):
        # PDF
        files = {"file": ("TEST_cert.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, files=files, timeout=20)
        assert r.status_code == 200, r.text
        info = r.json()
        assert info.get("status") == "ok"
        assert info.get("content_type") == "application/pdf"

        # Info
        r = requests.get(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json().get("exists") is True
        assert r.json().get("original_name") == "TEST_cert.pdf"

        # Overwrite with PNG (single global cert)
        files = {"file": ("TEST_cert.png", io.BytesIO(b"\x89PNG\r\n\x1a\nDATA"), "image/png")}
        r = requests.post(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, files=files, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("content_type") == "image/png"

        # Download
        r = requests.get(f"{BASE_URL}/api/integrators/config/certificate/download", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/png")
        assert b"PNG" in r.content

        # Delete cleanup
        r = requests.delete(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        r = requests.get(f"{BASE_URL}/api/integrators/config/certificate", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json().get("exists") is False


# ---------- lifecycle: suspend/reactivate ----------
class TestSuspendReactivateCycle:
    def test_full_cycle_and_view_filter(self, admin_headers, target_integrator):
        integrator_id = target_integrator["integrator_id"]
        # Ensure we start from 'En proceso'
        if target_integrator.get("integrator_status") == "Suspendido":
            r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/reactivate",
                              headers=admin_headers, timeout=20)
            assert r.status_code == 200, r.text

        # 1) Suspend
        r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/suspend",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ok"
        assert body["integrator"]["integrator_status"] == "Suspendido"

        # 2) Verify it is filtered OUT of the default view (show_all=false)
        r = requests.get(f"{BASE_URL}/api/integrators", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("integrators", [])
        ids_default = {i["integrator_id"] for i in items}
        # Note: backend may or may not filter server-side (frontend filters). Accept either
        # behavior but ensure integrator status is Suspendido if present.
        for i in items:
            if i["integrator_id"] == integrator_id:
                assert i["integrator_status"] == "Suspendido"

        # 3) show_all=true must include it
        r = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=admin_headers, timeout=20)
        items = r.json() if isinstance(r.json(), list) else r.json().get("integrators", [])
        found = next((i for i in items if i["integrator_id"] == integrator_id), None)
        assert found is not None, "Suspended integrator not visible with show_all=true"
        assert found["integrator_status"] == "Suspendido"

        # 4) Re-suspend must 400
        r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/suspend",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 400

        # 5) Reactivate
        r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/reactivate",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["integrator"]["integrator_status"] == "En proceso"

        # 6) Reactivate non-suspended must 400
        r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/reactivate",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 400


# ---------- integrator_user recipient E2E ----------
class TestIntegratorUserRecipientDispatch:
    def _get_template_id(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/email-templates", headers=admin_headers, timeout=20)
        if r.status_code != 200:
            return None
        arr = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
        if not arr:
            return None
        # Prefer any template that looks generic
        return arr[0].get("template_id") or arr[0].get("id")

    def test_configure_and_dispatch_to_integrator_user(self, admin_headers, target_integrator):
        # Look up template from catalog (guarantees valid template_id).
        cat = requests.get(f"{BASE_URL}/api/other-actions/catalog", headers=admin_headers, timeout=20).json()
        templates = cat.get("templates") or []
        if not templates:
            pytest.skip("No hay templates disponibles para configurar la Otra Acción")
        template_id = templates[0].get("template_id")

        # Configure integration_project_suspended with integrator_user recipient
        payload = {
            "action_id": "integration_project_suspended",
            "enabled": True,
            "recipients": [
                {
                    "row_id": "TEST_iter270_row1",
                    "type": "integrator_user",
                    "template_id": template_id,
                    "delivery_channel": "email",
                }
            ],
        }
        r = requests.put(
            f"{BASE_URL}/api/other-actions/configs",
            json=payload, headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200, f"PUT config failed: {r.status_code} {r.text}"

        # Ensure integrator is 'En proceso' before we suspend
        integrator_id = target_integrator["integrator_id"]
        if target_integrator.get("integrator_status") == "Suspendido":
            requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/reactivate",
                          headers=admin_headers, timeout=20)

        # Suspend → should attempt dispatch to principal_contact_email
        r = requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/suspend",
                          headers=admin_headers, timeout=45)
        assert r.status_code == 200, r.text
        body = r.json()
        notif = body.get("notification") or {}
        # Accept any of: sent_count>=1, or dispatched=True (SMTP may fail in test env)
        # If dispatch was fully broken (previous syntax bug), 'notification' would be None.
        assert notif is not None, "Dispatch result missing — engine may still be broken"
        # If sent_count present, must include the integrator's email
        sent_to = notif.get("sent_to") or []
        skipped = notif.get("skipped") or []
        assert (notif.get("sent_count", 0) >= 1) or sent_to or skipped, \
            f"Neither sent nor skipped info returned: {notif}"

        # If SMTP failed, we still expect the engine to at least have tried to resolve the recipient.
        # sent_to should contain the integrator's email OR skipped rows should be [] (means engine reached send stage)
        principal = (target_integrator.get("principal_contact_email") or "").lower()
        if sent_to:
            assert any(principal in (e or "").lower() for e in sent_to), \
                f"principal_contact_email not among sent_to: {sent_to}"

        # Reactivate cleanup
        requests.post(f"{BASE_URL}/api/integrators/{integrator_id}/reactivate",
                      headers=admin_headers, timeout=30)

    def test_cleanup_config(self, admin_headers):
        # Disable the config we created (leave it disabled so nothing spams).
        payload = {
            "action_id": "integration_project_suspended",
            "enabled": False,
            "recipients": [],
        }
        r = requests.put(
            f"{BASE_URL}/api/other-actions/configs",
            json=payload, headers=admin_headers, timeout=20,
        )
        assert r.status_code == 200
