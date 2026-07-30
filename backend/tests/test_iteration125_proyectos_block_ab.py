"""
Iteration 125 — Gestor MegaNexus Proyectos
BLOQUE A (bugs) + BLOQUE B (features):
  - PUT /api/projects/{id}/status guard for 'Configurado en espera del Cliente'
  - PUT /api/projects/{id}/implementation-fields persists fecha_estimada_produccion
  - /api/clients/{id}/preview-email returns HTML with 'cid:firma_logo'
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pdf-backfill-hub.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
PRJ_EN_GESTION = "prj_9affacb36c89"
PRJ_ASIGNADO = "prj_826643491b64"
NEW_STATUS = "Configurado en espera del Cliente"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def restore_state(auth_headers):
    """Capture initial state of prj_9affacb36c89 and restore at teardown."""
    yield
    # Restore to 'En Gestión' if drifted
    try:
        r = requests.get(f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}", headers=auth_headers, timeout=15)
        if r.status_code == 200 and r.json().get("status") != "En Gestión":
            requests.put(
                f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/status",
                headers=auth_headers,
                data={"new_status": "En Gestión"},
                timeout=15,
            )
        # Clear fecha_estimada_produccion
        requests.put(
            f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/implementation-fields",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"fecha_estimada_produccion": None},
            timeout=15,
        )
    except Exception as e:
        print(f"Teardown best-effort failed: {e}")


# ============ BACKEND (a) — Status guard ============

class TestStatusGuard:
    def test_status_guard_blocks_from_non_gestion(self, auth_headers):
        """Proyecto Asignado -> debe rechazarse con 400."""
        # Sanity: verify project status
        g = requests.get(f"{BASE_URL}/api/projects/{PRJ_ASIGNADO}", headers=auth_headers, timeout=15)
        assert g.status_code == 200
        current = g.json().get("status")
        assert current != "En Gestión", f"prj_826643491b64 unexpectedly in En Gestión (now: {current})"

        r = requests.put(
            f"{BASE_URL}/api/projects/{PRJ_ASIGNADO}/status",
            headers=auth_headers,
            data={"new_status": NEW_STATUS},
            timeout=15,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "En Gestión" in r.text or "solo puede" in r.text.lower()

    def test_status_guard_accepts_from_en_gestion(self, auth_headers):
        """Proyecto En Gestión -> 200 y persiste el nuevo estado."""
        # Ensure starting state
        g = requests.get(f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}", headers=auth_headers, timeout=15)
        assert g.status_code == 200
        if g.json().get("status") != "En Gestión":
            # restore
            requests.put(
                f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/status",
                headers=auth_headers,
                data={"new_status": "En Gestión"},
                timeout=15,
            )

        r = requests.put(
            f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/status",
            headers=auth_headers,
            data={"new_status": NEW_STATUS},
            timeout=15,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

        # Verify via GET
        g2 = requests.get(f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}", headers=auth_headers, timeout=15)
        assert g2.status_code == 200
        assert g2.json().get("status") == NEW_STATUS

        # Restore
        rr = requests.put(
            f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/status",
            headers=auth_headers,
            data={"new_status": "En Gestión"},
            timeout=15,
        )
        assert rr.status_code == 200


# ============ BACKEND (b) — implementation-fields fecha persistence ============

class TestImplementationFieldsFecha:
    def test_persist_fecha_estimada_produccion(self, auth_headers):
        fecha = "2026-08-15"
        r = requests.put(
            f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/implementation-fields",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"fecha_estimada_produccion": fecha},
            timeout=15,
        )
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"

        g = requests.get(f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}", headers=auth_headers, timeout=15)
        assert g.status_code == 200
        body = g.json()
        # field may be returned as 'YYYY-MM-DD' or ISO datetime
        val = body.get("fecha_estimada_produccion")
        assert val is not None, f"fecha_estimada_produccion not persisted: {body}"
        assert "2026-08-15" in str(val), f"Unexpected value: {val}"

    def test_clear_fecha_estimada_produccion(self, auth_headers):
        r = requests.put(
            f"{BASE_URL}/api/projects/{PRJ_EN_GESTION}/implementation-fields",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"fecha_estimada_produccion": None},
            timeout=15,
        )
        assert r.status_code == 200


# ============ BACKEND (c) — preview-email Firma_Notificacion_Global = cid:firma_logo ============

class TestPreviewEmailSignatureCid:
    def test_signature_uses_cid_firma_logo(self, auth_headers):
        """Pick any client and verify {Firma_Notificacion_Global} resolves to HTML with cid:firma_logo."""
        # find a client
        lr = requests.get(f"{BASE_URL}/api/clients?limit=1", headers=auth_headers, timeout=20)
        assert lr.status_code == 200, lr.text
        data = lr.json()
        items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
        assert items, f"no clients found in: {data}"
        client_id = items[0].get("client_id") or items[0].get("id")
        assert client_id

        r = requests.post(
            f"{BASE_URL}/api/clients/{client_id}/preview-email",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"subject": "Test", "message": "Saludos.<br/>{Firma_Notificacion_Global}"},
            timeout=20,
        )
        assert r.status_code == 200, f"preview-email failed: {r.status_code} {r.text}"
        msg = r.json().get("message", "")
        assert "cid:firma_logo" in msg, f"signature does NOT use cid:firma_logo. Got: {msg[:600]}"
        # Make sure no raw http URL is used as logo src in signature block
        # We accept http urls inside hyperlinks but NOT as <img src="http..."> for the footer logo.
        assert 'src="http' not in msg.split("cid:firma_logo")[0][-200:], "Image src appears to be http URL"


# ============ BACKEND (2.1) — upload-image returns {url} ============

class TestUploadImage:
    def test_upload_image_returns_url(self, auth_headers):
        # Minimal valid PNG (1x1 transparent)
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
            "890000000D49444154789C636400010000000500010D0A2DB40000000049454E"
            "44AE426082"
        )
        files = {"file": ("paste.png", png, "image/png")}
        r = requests.post(
            f"{BASE_URL}/api/projects/upload-image",
            headers={"Authorization": auth_headers["Authorization"]},
            files=files,
            timeout=20,
        )
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
        data = r.json()
        assert "url" in data and data["url"].startswith("http"), data
        # GET the URL to make sure it is reachable
        gr = requests.get(data["url"], timeout=15)
        assert gr.status_code == 200, f"image not served: {gr.status_code}"


# ============ BACKEND (2.3) — ghost variable cleaning regex ============

class TestSubjectGhostCleaning:
    def test_regex_strips_unresolved_tokens(self):
        """Same regex used at routes/projects.py L1103 — must strip un-replaced {Token}."""
        import re
        s = "Implementación PRJ-123 {Token_Fantasma} llamada de {OtroVar}  "
        s2 = re.sub(r"\{\{?\s*[A-Za-z0-9_áéíóúÁÉÍÓÚñÑ]+\s*\}?\}", "", s)
        s2 = re.sub(r"\s{2,}", " ", s2).strip()
        assert "{Token_Fantasma}" not in s2
        assert "{OtroVar}" not in s2
        assert "Implementación PRJ-123" in s2
