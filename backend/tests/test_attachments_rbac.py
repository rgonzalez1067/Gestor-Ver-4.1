"""Backend tests — Matriz estricta de permisos de Anexos (Histórico de Cotizaciones).

Reglas validadas (módulo `quote_history`):
  - Consulta (read):   GET listar/descargar OK; POST 403; DELETE 403.
  - Edición Total (edit): GET OK; POST 200; DELETE 403 (solo admin elimina).
  - Administrador (role): GET OK; POST 200; DELETE 200.
  - Excepción Taller: POST con context='taller_repair' no exige quote_history:edit
    (flujo de Reparación completada no se bloquea).

El test de "Edición Total" altera temporalmente el nivel de un usuario de prueba
(srubio) a `edit` y lo revierte a `read` en el teardown.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://rif-distribution.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
CONSULTA = {"email": "srubio@megasoft.com.ve", "password": "Test1234!"}  # quote_history=read

_uploaded = []  # (quote_id, attachment_id) creados para limpiar


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def admin():
    return _sess(_login(ADMIN))


@pytest.fixture(scope="session")
def consulta():
    return _sess(_login(CONSULTA))


@pytest.fixture(scope="session")
def quote_id(admin):
    r = admin.get(f"{API}/quotes?limit=1", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("quotes") or data.get("items"))
    assert items, "No hay cotizaciones para probar"
    return items[0]["quote_id"]


def teardown_module(module):
    """Elimina (como admin) los anexos creados y asegura srubio en read."""
    s = _sess(_login(ADMIN))
    for qid, aid in _uploaded:
        s.delete(f"{API}/quotes/{qid}/attachments/{aid}", timeout=30)
    # asegurar revert del nivel de srubio
    try:
        import asyncio
        from config import db

        async def _revert():
            await db.users.update_one({"email": CONSULTA["email"]}, {"$set": {"permissions.quote_history": "read"}})
        asyncio.get_event_loop().run_until_complete(_revert())
    except Exception:
        pass


def _upload(sess, quote_id, **extra):
    files = {"file": ("anexo_qa.txt", b"qa test content", "text/plain")}
    data = {"category": "Otros", **extra}
    return sess.post(f"{API}/quotes/{quote_id}/attachments", files=files, data=data, timeout=60)


# ---------------- Consulta (read) ----------------
def test_consulta_can_list(consulta, quote_id):
    r = consulta.get(f"{API}/quotes/{quote_id}/attachments", timeout=30)
    assert r.status_code == 200, r.text


def test_consulta_cannot_upload(consulta, quote_id):
    r = _upload(consulta, quote_id)
    assert r.status_code == 403, r.text


def test_consulta_cannot_delete(consulta, quote_id):
    r = consulta.delete(f"{API}/quotes/{quote_id}/attachments/att_inexistente", timeout=30)
    assert r.status_code == 403, r.text


def test_taller_context_bypasses_quote_history(consulta, quote_id):
    """El flujo de Taller (context=taller_repair) no se bloquea por quote_history."""
    r = _upload(consulta, quote_id, context="taller_repair")
    assert r.status_code == 200, r.text
    _uploaded.append((quote_id, r.json()["attachment"]["attachment_id"]))


# ---------------- Administrador ----------------
def test_admin_upload_and_delete(admin, quote_id):
    r = _upload(admin, quote_id)
    assert r.status_code == 200, r.text
    aid = r.json()["attachment"]["attachment_id"]
    rd = admin.delete(f"{API}/quotes/{quote_id}/attachments/{aid}", timeout=30)
    assert rd.status_code == 200, rd.text


# ---------------- Edición Total (edit) ----------------
def test_edicion_total_can_upload_but_not_delete(quote_id):
    import asyncio
    from config import db

    async def _set(level):
        await db.users.update_one({"email": CONSULTA["email"]}, {"$set": {"permissions.quote_history": level}})

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_set("edit"))
        sess = _sess(_login(CONSULTA))
        r = _upload(sess, quote_id)
        assert r.status_code == 200, r.text
        aid = r.json()["attachment"]["attachment_id"]
        # Edición Total NO puede eliminar (solo admin)
        rd = sess.delete(f"{API}/quotes/{quote_id}/attachments/{aid}", timeout=30)
        assert rd.status_code == 403, rd.text
        _uploaded.append((quote_id, aid))
    finally:
        loop.run_until_complete(_set("read"))
        loop.close()
