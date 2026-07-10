"""Iter242 — Módulo de Comunicación Directa al Usuario + Sesiones Activas.

Tests:
1. POST /api/admin/direct-message — validaciones (body vacío, sin destinatarios), 403 no-admin.
2. GET/POST/DELETE /api/admin/message-templates — CRUD + 403 no-admin.
3. GET /api/admin/connected-users — shape + 403 no-admin.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-impl-filter.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
NON_ADMIN_EMAIL = "mmartin@megasoft.com.ve"
NON_ADMIN_PASSWORD = "Test1234!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed {email}: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token")
    assert tok, f"No token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}


@pytest.fixture(scope="module")
def user_headers():
    return {"Authorization": f"Bearer {_login(NON_ADMIN_EMAIL, NON_ADMIN_PASSWORD)}"}


# ==================== /admin/connected-users ====================

class TestConnectedUsers:
    def test_admin_list_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/connected-users", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert "total_users" in data
        assert "total_connections" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total_users"], int)
        assert isinstance(data["total_connections"], int)
        # No MongoDB _id leakage
        for it in data["items"]:
            assert "_id" not in it
            for k in ("user_id", "full_name", "email", "connections"):
                assert k in it, f"missing {k} in item"

    def test_non_admin_403(self, user_headers):
        r = requests.get(f"{API}/admin/connected-users", headers=user_headers, timeout=15)
        assert r.status_code == 403


# ==================== /admin/direct-message ====================

class TestDirectMessage:
    def test_empty_body_400(self, admin_headers):
        r = requests.post(f"{API}/admin/direct-message", headers=admin_headers,
                          json={"body": "   ", "level": "medium", "recipient_ids": []}, timeout=15)
        assert r.status_code == 400
        assert "vac" in r.json().get("detail", "").lower()

    def test_no_recipients_400(self, admin_headers):
        r = requests.post(f"{API}/admin/direct-message", headers=admin_headers,
                          json={"body": "Prueba TEST_ITER242", "level": "low",
                                "all_online": False, "recipient_ids": []}, timeout=15)
        assert r.status_code == 400
        assert "destinatario" in r.json().get("detail", "").lower()

    def test_non_admin_403(self, user_headers):
        r = requests.post(f"{API}/admin/direct-message", headers=user_headers,
                          json={"body": "hola", "level": "low", "all_online": True}, timeout=15)
        assert r.status_code == 403

    def test_all_online_send(self, admin_headers):
        """Con all_online=True aunque no haya conexiones locales, el endpoint
        debería resolver recipient_ids desde manager.local_user_ids(). Si no hay
        conexiones activas, retorna 400 (sin destinatarios). Ese es un
        escenario válido en el preview single-worker sin sockets vivos."""
        r = requests.post(f"{API}/admin/direct-message", headers=admin_headers,
                          json={"body": "TEST_ITER242 broadcast", "level": "medium",
                                "all_online": True}, timeout=15)
        # 400 si no hay conectados; 200 si hay
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            data = r.json()
            assert data.get("delivered") >= 1
            assert data.get("level") == "medium"

    def test_send_to_specific_recipient(self, admin_headers):
        """Enviar a un user_id conocido (aunque no esté online); debe aceptar
        y persistir. delivered=1."""
        # Envía al propio admin como recipient — user_id retrievable
        me = requests.get(f"{API}/auth/me", headers=admin_headers, timeout=15)
        assert me.status_code == 200
        my_id = me.json().get("user_id") or me.json().get("id")
        assert my_id
        r = requests.post(f"{API}/admin/direct-message", headers=admin_headers,
                          json={"body": "TEST_ITER242 mensaje al admin",
                                "level": "high", "recipient_ids": [my_id]}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["delivered"] == 1
        assert data["level"] == "high"


# ==================== /admin/message-templates ====================

class TestMessageTemplates:
    _created_id = None

    def test_non_admin_get_403(self, user_headers):
        r = requests.get(f"{API}/admin/message-templates", headers=user_headers, timeout=15)
        assert r.status_code == 403

    def test_non_admin_post_403(self, user_headers):
        r = requests.post(f"{API}/admin/message-templates", headers=user_headers,
                          json={"text": "TEST_ITER242 tpl"}, timeout=15)
        assert r.status_code == 403

    def test_list_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/message-templates", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)

    def test_create_empty_400(self, admin_headers):
        r = requests.post(f"{API}/admin/message-templates", headers=admin_headers,
                          json={"text": "  "}, timeout=15)
        assert r.status_code == 400

    def test_create_get_delete_cycle(self, admin_headers):
        # CREATE
        r = requests.post(f"{API}/admin/message-templates", headers=admin_headers,
                          json={"title": "TEST_ITER242 título", "text": "TEST_ITER242 cuerpo plantilla"}, timeout=15)
        assert r.status_code == 200, r.text
        tpl = r.json()
        assert "template_id" in tpl
        assert tpl["text"] == "TEST_ITER242 cuerpo plantilla"
        assert tpl["title"] == "TEST_ITER242 título"
        tpl_id = tpl["template_id"]

        # GET → confirma que está en lista
        r2 = requests.get(f"{API}/admin/message-templates", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        ids = [t["template_id"] for t in r2.json()["items"]]
        assert tpl_id in ids

        # DELETE
        r3 = requests.delete(f"{API}/admin/message-templates/{tpl_id}", headers=admin_headers, timeout=15)
        assert r3.status_code == 200

        # Verify removed
        r4 = requests.get(f"{API}/admin/message-templates", headers=admin_headers, timeout=15)
        ids2 = [t["template_id"] for t in r4.json()["items"]]
        assert tpl_id not in ids2


# ==================== Cleanup ====================

@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    yield
    try:
        headers = {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}
        r = requests.get(f"{API}/admin/message-templates", headers=headers, timeout=15)
        if r.status_code == 200:
            for t in r.json().get("items", []):
                if "TEST_ITER242" in (t.get("text", "") + t.get("title", "")):
                    requests.delete(f"{API}/admin/message-templates/{t['template_id']}", headers=headers, timeout=15)
    except Exception:
        pass
