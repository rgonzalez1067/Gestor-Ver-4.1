# ruff: noqa
"""Iteration 187 — Consolidated send-to-implementation flow.

Backend checks:
- _validate_instructions_length helper: 500-char enforcement (unit).
- POST /api/quotes/{id}/send-to-implementation with implementation_instructions:
  * 501 visible chars -> 422 with detail mentioning "500".
  * Valid HTML (<501 chars) -> 200 and the new project persists
    `implementation_instructions` and `economic_group` / `fantasy_name`.
- Ficha Técnica PDF rendering not thrown (service exercised via the happy path).
"""
import os
import sys
import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL missing")
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    assert tok, f"token not found: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json",
    }


# ---------- Unit: helper ----------
def test_helper_validates_500_chars():
    from routes.quote_actions import _validate_instructions_length
    from fastapi import HTTPException

    assert _validate_instructions_length("") is None
    assert _validate_instructions_length("<p><strong>ok</strong></p>") == "<p><strong>ok</strong></p>"
    with pytest.raises(HTTPException) as exc:
        _validate_instructions_length("<p>" + ("A" * 501) + "</p>")
    assert exc.value.status_code == 422
    assert "500" in exc.value.detail


# ---------- Finding a test quote ----------
def _find_candidate_quote(headers):
    """Prefer Pagada, fallback any quote if we can bypass with x-exception-reason."""
    r = requests.get(f"{BASE_URL}/api/quotes", headers=headers, timeout=30)
    if r.status_code != 200:
        return None, None
    quotes = r.json()
    if not isinstance(quotes, list):
        return None, None
    # Prefer Pagada
    for q in quotes:
        if q.get("quote_status") == "Pagada":
            return q.get("quote_id"), "Pagada"
    # Fallback: any quote
    for q in quotes:
        if q.get("quote_id"):
            return q.get("quote_id"), q.get("quote_status")
    return None, None


# ---------- Integration: 422 on >500 visible chars ----------
def test_send_to_implementation_rejects_over_500(headers):
    qid, status = _find_candidate_quote(headers)
    if not qid:
        pytest.skip("No quotes available for integration test")

    body = {
        "project_type_impl": "vpos_mpos",
        "server_name": "Multicomercio MSC",
        "economic_group": "TEST_GROUP_ITER187",
        "fantasy_name": "TEST_FANTASY_ITER187",
        "implementation_instructions": "<p>" + ("A" * 501) + "</p>",
    }
    # Use x-exception-reason to bypass status check if non-Pagada
    h = dict(headers)
    if status != "Pagada":
        h["x-exception-reason"] = "TEST_iter187_over500"

    r = requests.post(
        f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
        json=body,
        headers=h,
        timeout=30,
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text[:300]}"
    detail = (r.json() or {}).get("detail", "")
    assert "500" in str(detail), f"detail missing '500': {detail}"


# ---------- Integration: happy path (<500 chars) ----------
def test_send_to_implementation_accepts_valid_html(headers):
    qid, status = _find_candidate_quote(headers)
    if not qid:
        pytest.skip("No quotes available for integration test")

    html = "<p><strong>Instalar</strong> y <em>verificar</em> pinpad.</p>"
    body = {
        "project_type_impl": "vpos_mpos",
        "server_name": "Multicomercio MSC",
        "economic_group": "TEST_GROUP_ITER187",
        "fantasy_name": "TEST_FANTASY_ITER187",
        "implementation_instructions": html,
    }
    h = dict(headers)
    if status != "Pagada":
        h["x-exception-reason"] = "TEST_iter187_happy_path"

    r = requests.post(
        f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
        json=body,
        headers=h,
        timeout=60,
    )
    # If the quote got consumed by a previous run or there's a server-side
    # constraint (ie "Proyecto ya existe"), tolerate that but fail on 422/5xx.
    if r.status_code == 404:
        pytest.skip(f"Quote {qid} no longer available (probably consumed earlier).")
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:400]}"

    # Verify the project now contains implementation_instructions and the extras
    projs = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert projs.status_code == 200
    matched = [p for p in projs.json() if p.get("quote_id") == qid]
    assert matched, "project was not persisted for the test quote"
    proj = matched[0]
    assert proj.get("implementation_instructions") == html, (
        f"implementation_instructions missing/wrong: {proj.get('implementation_instructions')}"
    )
    assert proj.get("economic_group") == "TEST_GROUP_ITER187"
    assert proj.get("fantasy_name") == "TEST_FANTASY_ITER187"
    assert proj.get("project_type_impl") == "vpos_mpos"
    assert proj.get("server_name") == "Multicomercio MSC"
