"""Test: Ficha Técnica PDF must print project.created_at date (frozen), not today.
Iteration 334 - Bug fix verification.
"""
import io
import os
import re
from datetime import datetime

import pytest
import requests
from pypdf import PdfReader

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env_path = "/app/frontend/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        url = line.split("=", 1)[1].strip()
                        break
    return url.rstrip("/")

BASE_URL = _load_backend_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        try:
            text += page.extract_text() or ""
            text += "\n"
        except Exception:
            pass
    return text


def _expected_spanish_date(iso_or_dt) -> str:
    if isinstance(iso_or_dt, str):
        dt = datetime.fromisoformat(iso_or_dt.replace("Z", "+00:00"))
    else:
        dt = iso_or_dt
    return f"{dt.day} de {SPANISH_MONTHS[dt.month]} de {dt.year}"


def test_ficha_tecnica_specific_project_frozen_date(session):
    """prj_826643491b64 has created_at=2026-04-29. PDF must show '29 de abril de 2026'."""
    pid = "prj_826643491b64"
    r = session.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica")
    assert r.status_code == 200, f"Ficha download failed: {r.status_code} {r.text[:300]}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), f"Not PDF: {r.headers}"
    text = _extract_text(r.content)
    print(f"[{pid}] PDF text sample:\n{text[:1500]}")

    today_str = _expected_spanish_date(datetime.utcnow())
    expected = "29 de abril de 2026"
    assert expected in text, f"Expected frozen date '{expected}' in PDF, got sample: {text[:800]}"
    # Should NOT be today's date (unless coincidentally today is 29 abril 2026)
    if today_str != expected:
        assert today_str not in text, f"PDF contains today's date '{today_str}' instead of frozen '{expected}'"


def test_ficha_tecnica_other_past_projects(session):
    """Sample 1-2 more past-dated projects and verify frozen date."""
    r = session.get(f"{BASE_URL}/api/projects", params={"limit": 200})
    assert r.status_code == 200, f"GET /api/projects failed: {r.status_code}"
    payload = r.json()
    projects = payload if isinstance(payload, list) else payload.get("projects", payload.get("items", []))
    assert isinstance(projects, list) and projects, "No projects returned"

    today = datetime.utcnow().date()
    candidates = []
    for p in projects:
        ca = p.get("created_at")
        if not ca:
            continue
        try:
            d = datetime.fromisoformat(str(ca).replace("Z", "+00:00")).date()
        except Exception:
            continue
        if d < today and (p.get("project_id") or p.get("id")) != "prj_826643491b64":
            candidates.append((p.get("project_id") or p.get("id"), d, ca))
        if len(candidates) >= 3:
            break

    if not candidates:
        pytest.skip("No other past-dated projects available")

    tested = 0
    errors = []
    for pid, d, ca in candidates[:2]:
        rr = session.get(f"{BASE_URL}/api/projects/{pid}/ficha-tecnica")
        if rr.status_code != 200:
            errors.append(f"{pid}: HTTP {rr.status_code}")
            continue
        text = _extract_text(rr.content)
        expected = _expected_spanish_date(datetime.fromisoformat(str(ca).replace("Z", "+00:00")))
        today_str = _expected_spanish_date(datetime.utcnow())
        print(f"[{pid}] created_at={ca} expected='{expected}' today='{today_str}'")
        if expected not in text:
            errors.append(f"{pid}: expected '{expected}' NOT in PDF. Sample: {text[:400]}")
            continue
        if today_str != expected and today_str in text:
            errors.append(f"{pid}: today's date '{today_str}' present instead of frozen")
            continue
        tested += 1

    assert tested >= 1, f"Could not verify any additional project. Errors: {errors}"
    assert not errors, f"Errors: {errors}"
