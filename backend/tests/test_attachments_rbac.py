"""Backend tests — RBAC de Anexos (dos matrices independientes).

1) Anexos de COTIZACIONES VIGENTES  (/quotes/{id}/attachments)
   Gobernados por el módulo `cotizaciones` (+ permisos especiales cotizaciones:*),
   INDEPENDIENTES del Histórico:
     - read (GET/descargar): Admin, o cotizaciones>=Consulta, o especial cotizaciones:*
     - edit (POST):          Admin, o cotizaciones=Edición, o especial cotizaciones:*
     - delete:               solo Admin
     - Excepción Taller: POST context='taller_repair' no se bloquea (autenticado).

2) Anexos del HISTÓRICO  (/quote-history/{id}/attachments)
   Gobernados por el módulo `quote_history` (Matriz estricta de Anexos):
     - Consulta(read): GET OK; POST 403; DELETE 403
     - Edición(edit):  GET OK; POST 200; DELETE 403
     - Admin:          GET/POST/DELETE OK

Usa la cuenta real de Operaciones (ragg1008) flexionando temporalmente sus
permisos en BD y restaurándolos siempre en el teardown.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
OPS = {"email": "ragg1008@gmail.com", "password": "admin123"}  # Analista de Operaciones

_uploaded = []        # (quote_id, attachment_id)
_uploaded_hist = []   # (history_id, attachment_id)
_original_perms = {}  # snapshot para restaurar


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def _sess(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def _db():
    import os
    import config  # noqa: F401 — asegura load_dotenv
    from pymongo import MongoClient
    cli = MongoClient(os.environ["MONGO_URL"])
    return cli, cli[os.environ["DB_NAME"]]


def _snapshot_ops():
    cli, db = _db()
    u = db.users.find_one({"email": OPS["email"]}, {"_id": 0, "permissions": 1, "special_permissions": 1})
    cli.close()
    return u or {}


def _set_ops(*, cotizaciones=None, quote_history=None, special=None):
    cli, db = _db()
    setter = {}
    if cotizaciones is not None:
        setter["permissions.cotizaciones"] = cotizaciones
    if quote_history is not None:
        setter["permissions.quote_history"] = quote_history
    if special is not None:
        setter["special_permissions"] = special
    if setter:
        db.users.update_one({"email": OPS["email"]}, {"$set": setter})
    cli.close()


def _restore_ops():
    cli, db = _db()
    perms = _original_perms.get("permissions", {}) or {}
    db.users.update_one({"email": OPS["email"]}, {"$set": {
        "permissions.cotizaciones": perms.get("cotizaciones", "edit"),
        "permissions.quote_history": perms.get("quote_history", "none"),
        "special_permissions": _original_perms.get("special_permissions", []) or [],
    }})
    cli.close()


@pytest.fixture(scope="session", autouse=True)
def _capture_and_restore():
    global _original_perms
    _original_perms = _snapshot_ops()
    yield
    _restore_ops()


@pytest.fixture(scope="session")
def admin():
    return _sess(_login(ADMIN))


@pytest.fixture(scope="session")
def quote_id(admin):
    r = admin.get(f"{API}/quotes?limit=1", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("quotes") or data.get("items"))
    assert items, "No hay cotizaciones para probar"
    return items[0]["quote_id"]


@pytest.fixture(scope="session")
def history_id(admin):
    r = admin.get(f"{API}/quote-history?limit=1", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("items") or data.get("history") or data.get("records"))
    assert items, "No hay registros de histórico para probar"
    return items[0]["history_id"]


def teardown_module(module):
    s = _sess(_login(ADMIN))
    for qid, aid in _uploaded:
        s.delete(f"{API}/quotes/{qid}/attachments/{aid}", timeout=30)
    for hid, aid in _uploaded_hist:
        s.delete(f"{API}/quote-history/{hid}/attachments/{aid}", timeout=30)


def _upload(sess, quote_id, **extra):
    files = {"file": ("anexo_qa.txt", b"qa test content", "text/plain")}
    data = {"category": "Otros", **extra}
    return sess.post(f"{API}/quotes/{quote_id}/attachments", files=files, data=data, timeout=60)


def _upload_hist(sess, history_id, **extra):
    files = {"file": ("anexo_qa.txt", b"qa test content", "text/plain")}
    data = {"category": "Otros", **extra}
    return sess.post(f"{API}/quote-history/{history_id}/attachments", files=files, data=data, timeout=60)


# ============================================================
# 1) Anexos de COTIZACIONES VIGENTES  (módulo `cotizaciones`)
# ============================================================
def test_ops_cotizaciones_edit_can_list_and_upload_but_not_delete(quote_id):
    """OPS con cotizaciones=edit (+ especiales): GET 200, POST 200, DELETE 403."""
    _set_ops(cotizaciones="edit", special=["cotizaciones:equipos", "cotizaciones:reparaciones"])
    sess = _sess(_login(OPS))
    assert sess.get(f"{API}/quotes/{quote_id}/attachments", timeout=30).status_code == 200
    r = _upload(sess, quote_id)
    assert r.status_code == 200, r.text
    aid = r.json()["attachment"]["attachment_id"]
    _uploaded.append((quote_id, aid))
    rd = sess.delete(f"{API}/quotes/{quote_id}/attachments/{aid}", timeout=30)
    assert rd.status_code == 403, rd.text  # solo admin elimina


def test_ops_consulta_only_can_list_but_not_upload(quote_id):
    """cotizaciones=read, sin especiales: GET 200, POST 403."""
    _set_ops(cotizaciones="read", special=[])
    sess = _sess(_login(OPS))
    assert sess.get(f"{API}/quotes/{quote_id}/attachments", timeout=30).status_code == 200
    assert _upload(sess, quote_id).status_code == 403


def test_no_cotizaciones_access_is_blocked(quote_id):
    """Sin acceso a cotizaciones ni especiales: GET 403, POST 403."""
    _set_ops(cotizaciones="none", special=[])
    sess = _sess(_login(OPS))
    assert sess.get(f"{API}/quotes/{quote_id}/attachments", timeout=30).status_code == 403
    assert _upload(sess, quote_id).status_code == 403


def test_taller_context_bypasses_rbac(quote_id):
    """context='taller_repair' no se bloquea aunque no haya acceso a cotizaciones."""
    _set_ops(cotizaciones="none", special=[])
    sess = _sess(_login(OPS))
    r = _upload(sess, quote_id, context="taller_repair")
    assert r.status_code == 200, r.text
    _uploaded.append((quote_id, r.json()["attachment"]["attachment_id"]))


def test_admin_upload_and_delete_cotizacion(admin, quote_id):
    r = _upload(admin, quote_id)
    assert r.status_code == 200, r.text
    aid = r.json()["attachment"]["attachment_id"]
    assert admin.delete(f"{API}/quotes/{quote_id}/attachments/{aid}", timeout=30).status_code == 200


# ============================================================
# 2) Anexos del HISTÓRICO  (módulo `quote_history`)
# ============================================================
def test_hist_consulta_can_list_not_upload(history_id):
    _set_ops(quote_history="read")
    sess = _sess(_login(OPS))
    assert sess.get(f"{API}/quote-history/{history_id}/attachments", timeout=30).status_code == 200
    assert _upload_hist(sess, history_id).status_code == 403


def test_hist_edicion_can_upload_not_delete(history_id):
    _set_ops(quote_history="edit")
    sess = _sess(_login(OPS))
    r = _upload_hist(sess, history_id)
    assert r.status_code == 200, r.text
    aid = r.json()["attachment"]["attachment_id"]
    _uploaded_hist.append((history_id, aid))
    assert sess.delete(f"{API}/quote-history/{history_id}/attachments/{aid}", timeout=30).status_code == 403


def test_hist_no_access_blocked(history_id):
    _set_ops(quote_history="none")
    sess = _sess(_login(OPS))
    assert sess.get(f"{API}/quote-history/{history_id}/attachments", timeout=30).status_code == 403


def test_hist_admin_upload_and_delete(admin, history_id):
    r = _upload_hist(admin, history_id)
    assert r.status_code == 200, r.text
    aid = r.json()["attachment"]["attachment_id"]
    assert admin.delete(f"{API}/quote-history/{history_id}/attachments/{aid}", timeout=30).status_code == 200
