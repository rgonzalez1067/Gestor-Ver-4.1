"""Backend test — Endpoint de backfill de fecha 'Envío a Implementación'.

Valida:
  - Admin: POST /api/projects/backfill-impl-date → 200 con resumen y deja 0
    proyectos sin `sent_to_implementation_at` (idempotente / no destructivo).
  - No-admin: 403.
"""
import os
import requests

API = os.environ.get("REACT_APP_BACKEND_URL", "https://perfilado-contactos.preview.emergentagent.com").rstrip("/") + "/api"
ADMIN = {"email": "rgonzalez@megasoft.com.ve", "password": "admin123"}
CONSULTA = {"email": "srubio@megasoft.com.ve", "password": "Test1234!"}


def _token(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def test_backfill_requires_admin():
    tok = _token(CONSULTA)
    r = requests.post(f"{API}/projects/backfill-impl-date", headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    assert r.status_code == 403, r.text


def test_backfill_admin_idempotent():
    tok = _token(ADMIN)
    r = requests.post(f"{API}/projects/backfill-impl-date", headers={"Authorization": f"Bearer {tok}"}, timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    # Tras ejecutarlo, no debe quedar ningún proyecto sin la fecha.
    assert body["remaining_missing"] == 0, body
    # Idempotencia: una segunda corrida no actualiza nada.
    r2 = requests.post(f"{API}/projects/backfill-impl-date", headers={"Authorization": f"Bearer {tok}"}, timeout=120)
    assert r2.status_code == 200
    assert r2.json()["updated"] == 0, r2.json()
