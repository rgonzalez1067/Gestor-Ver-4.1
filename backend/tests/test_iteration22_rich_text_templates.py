"""
Iteration 22 - Rich Text Editor (TipTap) backend regression tests.

Validates:
  1. POST /api/email-templates accepts long body_html (>2000 chars) with rich HTML tags
     <p><strong><em><u><s><ul><li>; GET retrieves the exact same HTML (no truncation).
  2. GET /api/email-templates?context=CLIENTES filters correctly.
  3. Regression: GET /api/quotes with admin still works (RBAC Operaciones not broken).
"""
import os
import uuid
import pytest
import requests

def _load_base_url():
    v = os.environ.get('REACT_APP_BACKEND_URL')
    if not v:
        try:
            with open('/app/frontend/.env') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        v = line.strip().split('=', 1)[1]
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL must be set"
    return v.rstrip('/')

BASE_URL = _load_base_url()
ADMIN_EMAIL = 'rgonzalez@megasoft.com.ve'
ADMIN_PASSWORD = 'admin123'


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- 1. Long body_html with rich tags ----------
def _build_long_html(min_len: int = 2500) -> str:
    base = (
        "<p><strong>Estimado {nombre}</strong>, le saluda <em>Mega Soft</em>. "
        "Le confirmamos su <u>solicitud</u> con RIF <s>{rif_anterior}</s> ahora {rif}.</p>"
        "<ul><li>Item <strong>uno</strong></li>"
        "<li>Item <em>dos</em></li>"
        "<li>Item con enlace <a href=\"https://megasoft.com.ve\">aquí</a></li></ul>"
        "<p style=\"text-align:center\">Centrado de prueba</p>"
        "<p><span style=\"color:#dc2626\">Texto en rojo</span> y "
        "<mark data-color=\"#FEF3C7\" style=\"background-color:#FEF3C7\">resaltado</mark>.</p>"
    )
    out = ""
    i = 0
    while len(out) < min_len:
        out += base.replace("{nombre}", f"CLIENTE_{i}").replace("{rif_anterior}", f"V-{i:08d}-{i%10}")
        i += 1
    return out


def test_create_template_with_long_rich_html(auth_headers):
    tpl_id = f"TEST_rich_long_{uuid.uuid4().hex[:8]}"
    body_html = _build_long_html(2500)
    assert len(body_html) > 2000

    payload = {
        "template_id": tpl_id,
        "name": "TEST Rich Long Template",
        "subject": "Saludo a {nombre}",
        "body_html": body_html,
        "context": "CLIENTES",
        "is_active": True,
        "is_custom": True,
        "group": "General",
    }
    r = requests.post(f"{BASE_URL}/api/email-templates", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:300]}"
    j = r.json()
    assert j.get("template_id") == tpl_id

    # GET back and compare full body_html
    g = requests.get(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=auth_headers, timeout=20)
    assert g.status_code == 200, f"get failed: {g.status_code} {g.text[:300]}"
    fetched = g.json()
    assert fetched["template_id"] == tpl_id
    assert fetched["body_html"] == body_html, (
        f"body_html mismatch: sent {len(body_html)} chars, got {len(fetched.get('body_html',''))} chars"
    )
    # Verify rich tags preserved
    for tag in ["<p>", "<strong>", "<em>", "<u>", "<s>", "<ul>", "<li>", 'href="https://megasoft.com.ve"']:
        assert tag in fetched["body_html"], f"missing tag in persisted HTML: {tag}"

    # Cleanup
    requests.delete(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=auth_headers, timeout=10)


def test_update_template_preserves_rich_html(auth_headers):
    tpl_id = f"TEST_rich_upd_{uuid.uuid4().hex[:8]}"
    initial_html = "<p>Inicial</p>"
    payload = {
        "template_id": tpl_id, "name": "TEST upd", "subject": "S",
        "body_html": initial_html, "context": "INTEGRADORES", "is_active": True,
    }
    requests.post(f"{BASE_URL}/api/email-templates", json=payload, headers=auth_headers, timeout=20).raise_for_status()

    long_html = _build_long_html(2200)
    payload["body_html"] = long_html
    r = requests.put(f"{BASE_URL}/api/email-templates/{tpl_id}", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200

    g = requests.get(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=auth_headers, timeout=20)
    assert g.status_code == 200
    assert g.json()["body_html"] == long_html

    requests.delete(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=auth_headers, timeout=10)


# ---------- 2. Context filter ----------
def test_get_templates_filter_context_clientes(auth_headers):
    tpl_id = f"TEST_ctx_cli_{uuid.uuid4().hex[:8]}"
    requests.post(f"{BASE_URL}/api/email-templates",
                  json={"template_id": tpl_id, "name": "TEST CLI ctx", "subject": "S",
                        "body_html": "<p>Body</p>", "context": "CLIENTES", "is_active": True},
                  headers=auth_headers, timeout=20).raise_for_status()
    try:
        r = requests.get(f"{BASE_URL}/api/email-templates?context=CLIENTES", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        # Every returned template must be CLIENTES
        for t in items:
            assert (t.get("context") or "").upper() == "CLIENTES", f"non-CLIENTES leaked: {t.get('template_id')}"
        ids = [t["template_id"] for t in items]
        assert tpl_id in ids
    finally:
        requests.delete(f"{BASE_URL}/api/email-templates/{tpl_id}", headers=auth_headers, timeout=10)


def test_get_templates_filter_context_integradores(auth_headers):
    r = requests.get(f"{BASE_URL}/api/email-templates?context=INTEGRADORES", headers=auth_headers, timeout=20)
    assert r.status_code == 200
    items = r.json()
    for t in items:
        ctx = (t.get("context") or "").upper()
        assert ctx == "INTEGRADORES", f"non-INTEGRADORES leaked: {t.get('template_id')} ctx={ctx}"


# ---------- 3. Regression: quotes endpoint with admin ----------
def test_admin_get_quotes_regression(auth_headers):
    r = requests.get(f"{BASE_URL}/api/quotes", headers=auth_headers, timeout=30)
    assert r.status_code == 200, f"quotes endpoint broken: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert isinstance(data, list)
    # Admin should see many quotes (not filtered)
    assert len(data) > 0, "admin sees zero quotes — RBAC may have leaked into admin scope"
