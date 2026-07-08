"""
Iter69 — Reingeniería de Proyectos: gestión de estados con auditoría.

Verifica el nuevo endpoint multipart PUT /api/projects/{id}/status:
  - Estado inválido -> 400
  - Anulado (sin archivo)  -> bitácora type='status_change' + new_status correcto
  - Suspendido + adjunto    -> bitácora.attachments con filename/url
  - Reactivación 'En Gestión' (cleanup)

Usa credenciales admin y el project_id sugerido (prj_a7368898fca6).
"""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://corp-pyme-sync.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
TARGET_PROJECT_ID = "prj_a7368898fca6"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={
        "email": "rgonzalez@megasoft.com.ve",
        "password": "admin123",
    }, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def project_id(headers):
    # Validar que existe; si no, escoger uno cualquiera no cerrado
    r = requests.get(f"{API}/projects/{TARGET_PROJECT_ID}", headers=headers, timeout=30)
    if r.status_code == 200:
        return TARGET_PROJECT_ID
    # fallback: listar y tomar el primero en estado 'En Gestión' o similar
    rl = requests.get(f"{API}/projects", headers=headers, timeout=30)
    assert rl.status_code == 200, rl.text[:200]
    items = rl.json() if isinstance(rl.json(), list) else rl.json().get("items", [])
    for p in items:
        if p.get("status") in ("En Gestión", "Asignado", "Por asignar"):
            return p["project_id"]
    pytest.skip("No hay project_id disponible para probar")


def _bitacora(headers, pid):
    r = requests.get(f"{API}/projects/{pid}/bitacora", headers=headers, timeout=30)
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    return body if isinstance(body, list) else body.get("bitacora", body.get("items", []))


def test_invalid_status_returns_400(headers, project_id):
    r = requests.put(
        f"{API}/projects/{project_id}/status",
        headers=headers,
        data={"new_status": "EstadoInventado123", "note": "test"},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"


def test_change_to_anulado_creates_bitacora(headers, project_id):
    note = "TEST_Iter69 anulado por validación QA"
    r = requests.put(
        f"{API}/projects/{project_id}/status",
        headers=headers,
        data={"new_status": "Anulado", "note": note, "change_date": "2026-01-15"},
        timeout=30,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("new_status") == "Anulado"
    assert "bitacora_entry_id" in data

    time.sleep(0.5)
    entries = _bitacora(headers, project_id)
    # Busca la entrada recién creada
    found = [e for e in entries if e.get("entry_id") == data["bitacora_entry_id"]]
    assert found, f"bitacora entry not found id={data['bitacora_entry_id']}"
    entry = found[0]
    assert entry.get("type") == "status_change"
    assert entry.get("new_status") == "Anulado"
    assert note in (entry.get("text") or "")


def test_change_to_suspendido_with_attachment(headers, project_id):
    files = {"file": ("evidencia_qa.txt", io.BytesIO(b"evidencia QA Iter69"), "text/plain")}
    data = {"new_status": "Suspendido", "note": "TEST_Iter69 suspendido con anexo", "change_date": "2026-01-15"}
    r = requests.put(
        f"{API}/projects/{project_id}/status",
        headers=headers,
        data=data,
        files=files,
        timeout=30,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    body = r.json()
    assert body.get("new_status") == "Suspendido"

    time.sleep(0.5)
    entries = _bitacora(headers, project_id)
    found = [e for e in entries if e.get("entry_id") == body["bitacora_entry_id"]]
    assert found, "bitacora entry not found"
    entry = found[0]
    assert entry.get("type") == "status_change"
    assert entry.get("new_status") == "Suspendido"
    atts = entry.get("attachments") or []
    assert len(atts) == 1, f"expected 1 attachment, got {atts}"
    att = atts[0]
    assert att.get("filename") == "evidencia_qa.txt"
    assert att.get("url", "").startswith("/uploads/status_changes/")


def test_reactivate_to_en_gestion_cleanup(headers, project_id):
    """Revertir el proyecto a 'En Gestión' para no dejarlo cerrado."""
    r = requests.put(
        f"{API}/projects/{project_id}/status",
        headers=headers,
        data={"new_status": "En Gestión", "note": "TEST_Iter69 cleanup reactivación", "change_date": "2026-01-15"},
        timeout=30,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    assert r.json().get("new_status") == "En Gestión"

    # Verificar estado actual
    pr = requests.get(f"{API}/projects/{project_id}", headers=headers, timeout=30)
    assert pr.status_code == 200
    assert pr.json().get("status") == "En Gestión"
