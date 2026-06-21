"""Tests for new feature:
1) POST /api/email-templates/append-signature  (admin-only, idempotent)
2) {Firma_Notificacion_Global} is resolved in preview-email endpoints of
   Clientes, Integradores, Nuevos Productos, Contactos Iniciales.
"""
import os
import pytest
import requests
from pathlib import Path


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    # Read from frontend/.env (source of truth per system prompt)
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_backend_url()
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
# srubio password is desynced in the DB; use Jrojas as the non-admin instead.
USER = {"email": "Jrojas@megasoft.com.ve", "password": "Test1234!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login {creds['email']} -> {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"no token in login response: {list(data.keys())}"
    return token


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def user_token():
    return _login(USER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- 1) append-signature endpoint ----------

class TestAppendSignatureEndpoint:
    def test_non_admin_forbidden(self, user_token):
        r = requests.post(
            f"{BASE_URL}/api/email-templates/append-signature",
            headers=_h(user_token),
            timeout=30,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_unauthenticated_forbidden(self):
        r = requests.post(
            f"{BASE_URL}/api/email-templates/append-signature", timeout=20
        )
        # Should not be 200; expect 401/403
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"

    def test_admin_idempotent(self, admin_token):
        # First call (may update 0 since main agent already ran it; just must be 200)
        r1 = requests.post(
            f"{BASE_URL}/api/email-templates/append-signature",
            headers=_h(admin_token),
            timeout=60,
        )
        assert r1.status_code == 200, f"{r1.status_code} {r1.text[:300]}"
        d1 = r1.json()
        for k in ("updated", "skipped", "total", "message"):
            assert k in d1, f"missing key {k} in response {d1}"
        assert isinstance(d1["updated"], int)
        assert isinstance(d1["skipped"], int)

        # Second call must be idempotent -> updated == 0
        r2 = requests.post(
            f"{BASE_URL}/api/email-templates/append-signature",
            headers=_h(admin_token),
            timeout=60,
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["updated"] == 0, f"idempotency broken: 2nd call updated={d2['updated']} (resp={d2})"
        assert d2["skipped"] >= 1
        assert d2["total"] == d2["skipped"]


# ---------- 2) preview-email resolution of Firma_Notificacion_Global ----------

SIGNATURE_RAZON_SOCIAL = "Mega Soft"  # appears as "Mega Soft Computación" in signature


def _pick_first_id(path, token, id_keys=("id",)):
    """GET a list endpoint and return the first record's id (or None)."""
    r = requests.get(f"{BASE_URL}{path}", headers=_h(token), timeout=30)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data if isinstance(data, list) else (
        data.get("items") or data.get("data") or data.get("results") or []
    )
    if not items:
        return None
    rec = items[0]
    for k in id_keys:
        if rec.get(k):
            return rec[k]
    return None


@pytest.fixture(scope="module")
def ids(admin_token):
    return {
        "client": _pick_first_id("/api/clients?limit=1", admin_token, id_keys=("client_id", "id", "_id")),
        "integrator": _pick_first_id("/api/integrators?limit=1", admin_token, id_keys=("integrator_id", "id", "_id")),
        "new_product": _pick_first_id("/api/new-products?limit=1", admin_token, id_keys=("product_id", "new_product_id", "id", "_id")),
        "initial_contact": _pick_first_id("/api/initial-contacts?limit=1", admin_token, id_keys=("contact_id", "initial_contact_id", "id", "_id")),
    }


def _assert_signature_in_message(resp_json):
    """Validate the rendered message contains the signature block (razon social)."""
    msg = resp_json.get("message") or resp_json.get("body_html") or resp_json.get("body") or ""
    assert msg, f"no message field in response: {list(resp_json.keys())}"
    # The variable should be replaced (no raw token left) AND must contain the razon social
    assert "{Firma_Notificacion_Global}" not in msg, "Variable not resolved: raw token left in message"
    assert SIGNATURE_RAZON_SOCIAL in msg, f"Signature missing 'Mega Soft' in message. Snippet: {msg[-400:]}"


PREVIEW_PAYLOAD = {
    "subject": "Prueba firma",
    "body_html": "<p>Hola,</p><p>{Firma_Notificacion_Global}</p>",
    "message": "<p>Hola,</p><p>{Firma_Notificacion_Global}</p>",
}


class TestPreviewEmailSignature:

    def test_client_preview(self, admin_token, ids):
        cid = ids["client"]
        if not cid:
            pytest.skip("No client available to test preview-email")
        r = requests.post(
            f"{BASE_URL}/api/clients/{cid}/preview-email",
            headers=_h(admin_token),
            json=PREVIEW_PAYLOAD,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        _assert_signature_in_message(r.json())

    def test_integrator_preview(self, admin_token, ids):
        iid = ids["integrator"]
        if not iid:
            pytest.skip("No integrator available to test preview-email")
        r = requests.post(
            f"{BASE_URL}/api/integrators/{iid}/preview-email",
            headers=_h(admin_token),
            json=PREVIEW_PAYLOAD,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        _assert_signature_in_message(r.json())

    def test_new_product_preview(self, admin_token, ids):
        pid = ids["new_product"]
        if not pid:
            pytest.skip("No new-product available to test preview-email")
        r = requests.post(
            f"{BASE_URL}/api/new-products/{pid}/preview-email",
            headers=_h(admin_token),
            json=PREVIEW_PAYLOAD,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        _assert_signature_in_message(r.json())

    def test_initial_contact_preview(self, admin_token, ids):
        cid = ids["initial_contact"]
        if not cid:
            pytest.skip("No initial-contact available to test preview-email")
        r = requests.post(
            f"{BASE_URL}/api/initial-contacts/{cid}/preview-email",
            headers=_h(admin_token),
            json=PREVIEW_PAYLOAD,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        _assert_signature_in_message(r.json())
