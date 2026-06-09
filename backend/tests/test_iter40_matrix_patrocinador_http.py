"""Iter40 — HTTP regression: matrix_html en /template-variables, {Patrocinador}
condicional vía /preview-notification, y no-corrupción de tablas adyacentes a
variables."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
PROJECT_ID = "prj_826643491b64"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    token = r.json().get("session_token") or r.json().get("access_token")
    assert token, r.json()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def test_template_variables_matrix_and_patrocinador(session):
    r = session.get(f"{BASE_URL}/api/projects/{PROJECT_ID}/template-variables")
    assert r.status_code == 200, r.text
    data = r.json()
    # matrix_html debe ser una tabla poblada
    matrix = data.get("matrix_html") or ""
    assert "<table" in matrix, f"matrix_html sin <table>: {matrix[:200]}"
    assert "Banco Activo" in matrix, f"Banco Activo no encontrado en matrix_html: {matrix[:400]}"
    # variables.Patrocinador presente y no vacío
    variables = data.get("variables") or {}
    assert "Patrocinador" in variables, list(variables.keys())[:20]
    assert variables["Patrocinador"], variables["Patrocinador"]


def test_preview_patrocinador_renders_and_table_preserved(session):
    payload = {
        "target": "bank_client",
        "destination": "bank_client",
        "custom_html": "<p>{Patrocinador}</p><table><tbody><tr><td><p>Banco Activo</p></td><td><p>Tarjeta</p></td></tr></tbody></table>",
    }
    r = session.post(f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    html = body.get("html") or body.get("body") or body.get("body_html") or ""
    # {Patrocinador} se renderizó (no queda literal)
    assert "{Patrocinador}" not in html, "Patrocinador no se resolvió"
    # CAFE EUROPA es cliente no patrocinado => debe aparecer su nombre/fantasía
    assert "CAFE EUROPA" in html.upper() or "EUROPA" in html.upper(), html[:500]
    # tabla intacta y con bordes aplicados por _style_email_tables
    assert "<table" in html, "tabla consumida"
    assert "Banco Activo" in html
    assert "Tarjeta" in html
    assert re.search(r"border\s*:\s*1px\s+solid", html), "bordes email-safe no aplicados"


def test_preview_patrocinador_sponsored_vs_unsponsored(session):
    # No patrocinado (CAFE EUROPA)
    r1 = session.post(
        f"{BASE_URL}/api/projects/{PROJECT_ID}/preview-notification",
        json={"target": "bank_client", "destination": "bank_client", "custom_html": "<p>{Patrocinador}</p>"},
    )
    assert r1.status_code == 200
    html1 = r1.json().get("html") or ""
    assert "{Patrocinador}" not in html1
    unsponsored_val = re.sub(r"<[^>]+>", "", html1).strip()
    assert unsponsored_val, "Patrocinador vacío en proyecto no patrocinado"

    # Buscar un proyecto patrocinado vía /api/projects
    r = session.get(f"{BASE_URL}/api/projects")
    assert r.status_code == 200
    projects = r.json()
    if isinstance(projects, dict):
        projects = projects.get("projects") or projects.get("items") or []
    sponsored = next(
        (p for p in projects if p.get("sponsored_implementation") and p.get("sponsoring_bank_name")),
        None,
    )
    if not sponsored:
        pytest.skip("No hay proyecto patrocinado para validar variante sponsored")
    pid = sponsored.get("id") or sponsored.get("project_id")
    bank = sponsored["sponsoring_bank_name"]
    r2 = session.post(
        f"{BASE_URL}/api/projects/{pid}/preview-notification",
        json={"target": "bank_client", "destination": "bank_client", "custom_html": "<p>{Patrocinador}</p>"},
    )
    assert r2.status_code == 200, r2.text
    html2 = r2.json().get("html") or ""
    assert bank in html2, f"Esperaba {bank} en {html2[:300]}"
