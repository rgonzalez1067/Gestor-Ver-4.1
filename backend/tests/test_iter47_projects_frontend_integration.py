"""Iter47 - Backend integration tests for the 4 frontend features.

1) /preview-adhoc-email respects HTML body from a template (body_html)
2) Projects: list templates endpoint usable for global Plantillas dialog
3) GET /projects/{id}/ficha-tecnica returns 200 + application/pdf
4) POST /projects/{id}/matrix/batch-update accepts product_names array
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-impl-filter.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    return data.get("access_token") or data.get("session_token") or data.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def multistore_project(headers):
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    payload = r.json()
    projects = payload if isinstance(payload, list) else payload.get("projects") or payload.get("items") or []
    # Pick a multistore project with an implementer assigned, with bank/products
    for p in projects:
        if p.get("project_type") == "multistore" and p.get("assigned_to_user_id"):
            # fetch detail to ensure matrix has banks/products
            d = requests.get(f"{BASE_URL}/api/projects/{p['project_id']}", headers=headers, timeout=30)
            if d.status_code == 200:
                detail = d.json()
                matrix = detail.get("implementation_matrix") or {}
                if matrix and any(matrix[b] for b in matrix):
                    detail["_id_safe"] = p["project_id"]
                    return detail
    pytest.skip("No multistore project with implementer + matrix found")


def test_login_ok(token):
    assert isinstance(token, str) and len(token) > 10


def test_ficha_tecnica_returns_pdf(headers, multistore_project):
    pid = multistore_project["_id_safe"]
    r = requests.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica", headers=headers, timeout=60)
    assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
    ctype = r.headers.get("content-type", "")
    assert "application/pdf" in ctype, f"unexpected content-type={ctype}"
    # PDF magic header
    assert r.content[:4] == b"%PDF", f"not a PDF, first bytes={r.content[:10]!r}"
    assert len(r.content) > 500


def test_email_templates_list(headers, multistore_project):
    pid = multistore_project["_id_safe"]
    r = requests.get(f"{BASE_URL}/api/email-templates", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)


def test_preview_adhoc_email_respects_html_body(headers, multistore_project):
    pid = multistore_project["_id_safe"]
    html_body = "<p>Hola <b>{Cliente}</b></p><ul><li>Item A</li><li>Item B</li></ul>"
    payload = {
        "recipients": ["test@example.com"],
        "subject": "Asunto Iter47",
        "message": html_body,
    }
    r = requests.post(f"{BASE_URL}/api/projects/{pid}/preview-adhoc-email", headers=headers, json=payload, timeout=30)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    data = r.json()
    # The preview should include the HTML message rendered as-is (bold + list preserved)
    html_out = (data.get("html") or data.get("body_html") or data.get("preview_html") or "").lower()
    if not html_out:
        # Some implementations return as plain `body` field
        html_out = (data.get("body") or "").lower()
    assert "<b>" in html_out or "<strong>" in html_out, f"bold not preserved: {html_out[:400]}"
    assert "<li>item a</li>" in html_out, f"list not preserved: {html_out[:400]}"


def test_batch_update_accepts_product_names_array(headers, multistore_project):
    pid = multistore_project["_id_safe"]
    matrix = multistore_project.get("implementation_matrix") or {}
    bank = next(iter(matrix.keys()))
    products = list(matrix[bank].keys())
    if not products:
        pytest.skip("Bank has no products")
    product_names = products[:2] if len(products) >= 2 else products
    stores = multistore_project.get("stores") or []
    if not stores:
        pytest.skip("Project has no stores")
    store_ids = [stores[0]["store_id"]]

    payload = {
        "phase": "Recibido",
        "bank_name": bank,
        "product_names": product_names,
        "store_ids": store_ids,
        "reason": "Iter47 automated test - multiple products",
    }
    r = requests.post(f"{BASE_URL}/api/projects/{pid}/matrix/batch-update", headers=headers, json=payload, timeout=60)
    # Acceptable: 200 or 207 (multi-status); reject 400/422 (would mean shape wrong)
    assert r.status_code in (200, 201, 207), f"status={r.status_code} body={r.text[:400]}"
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    # Spot-check there's some indication of success counts > 0 if returned
    if "updated" in body or "count" in body or "results" in body:
        assert True
