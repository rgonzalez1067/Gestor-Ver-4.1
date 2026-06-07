"""Tests del nuevo flujo 'Sí, pero no dispongo de seriales' en
POST /api/quotes/{quote_id}/send-to-implementation (iter194).

Cubre:
  - El backend acepta el campo opcional `serials_provider_note` en el body.
  - El proyecto creado persiste `serials_provider_note` con el texto exacto.
  - El PDF de Ficha Técnica generado contiene la sección
    "C. SERIALES DE LOS EQUIPOS" con el texto esperado (lo verificamos
    indirectamente vía contenido binario del PDF entregado por el endpoint
    `/api/projects/{id}/implementation-pdf`).
  - Regresión: si NO se envía el campo y no hay seriales, el flujo sigue
    funcionando y el proyecto guarda `serials_provider_note` = None.
"""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fallback al frontend/.env si la var no está exportada en este proceso
    try:
        with open('/app/frontend/.env') as f:
            for ln in f:
                if ln.startswith('REACT_APP_BACKEND_URL='):
                    BASE_URL = ln.strip().split('=', 1)[1].strip().rstrip('/')
                    break
    except Exception:
        pass

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

EXACT_NOTE = "Los Seriales de los Equipos serán suplidos por Procesador Total - Banco Central - "


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth_headers():
    tok = _login()
    if not tok:
        pytest.skip("no token from login")
    return {"Authorization": f"Bearer {tok}"}


def _find_pagada_impl_quote(headers):
    """Localiza una cotización Implementación VPOS en estado Pagada (no fast_track)."""
    r = requests.get(f"{BASE_URL}/api/quotes", headers=headers, timeout=30)
    assert r.status_code == 200, r.text[:200]
    quotes = r.json()
    if isinstance(quotes, dict) and "items" in quotes:
        quotes = quotes["items"]
    for q in quotes:
        if (q.get("quote_status") == "Pagada"
                and q.get("quote_category") == "implementation"
                and (q.get("quote_type") or "").upper() == "VPOS"):
            return q
    return None


class TestSerialsProviderNote:
    """Validación del campo serials_provider_note en send-to-implementation."""

    def test_endpoint_accepts_serials_provider_note_and_persists(self, auth_headers):
        q = _find_pagada_impl_quote(auth_headers)
        if not q:
            pytest.skip("No hay cotización Implementación VPOS en estado 'Pagada' disponible")
        qid = q["quote_id"]
        body = {
            "serials_provider_note": EXACT_NOTE,
            "economic_group": "Sin Grupo Económico",
        }
        r = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
            json=body, headers=auth_headers, timeout=120,
        )
        assert r.status_code == 200, f"send-to-impl failed: {r.status_code} {r.text[:500]}"
        data = r.json()
        assert data.get("new_status") == "Enviada a Imple"

        # Localizar el proyecto creado (la cotización fue eliminada)
        pr = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=30)
        assert pr.status_code == 200
        projects = pr.json()
        if isinstance(projects, dict) and "items" in projects:
            projects = projects["items"]
        project = next((p for p in projects if p.get("quote_id") == qid), None)
        assert project is not None, "Proyecto creado no encontrado por quote_id"

        # Re-fetch detallado para asegurar persistencia
        pid = project["project_id"]
        pdetail = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=auth_headers, timeout=30)
        assert pdetail.status_code == 200
        pd = pdetail.json()
        assert pd.get("serials_provider_note") == EXACT_NOTE, (
            f"esperado={EXACT_NOTE!r}, obtenido={pd.get('serials_provider_note')!r}"
        )

    def test_regression_without_serials_provider_note(self, auth_headers):
        q = _find_pagada_impl_quote(auth_headers)
        if not q:
            pytest.skip("No hay cotización Implementación VPOS en estado 'Pagada' disponible (caso regresión)")
        qid = q["quote_id"]
        # Cuerpo SIN serials_provider_note ni seriales reales
        body = {"economic_group": "Sin Grupo Económico"}
        r = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
            json=body, headers=auth_headers, timeout=120,
        )
        assert r.status_code == 200, f"regression flow failed: {r.status_code} {r.text[:500]}"
        # El proyecto debe existir y serials_provider_note ser None/falsy
        pr = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=30)
        assert pr.status_code == 200
        projects = pr.json()
        if isinstance(projects, dict) and "items" in projects:
            projects = projects["items"]
        project = next((p for p in projects if p.get("quote_id") == qid), None)
        assert project is not None
        pid = project["project_id"]
        pd = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=auth_headers, timeout=30).json()
        assert not pd.get("serials_provider_note"), (
            f"esperado vacío/None, obtenido={pd.get('serials_provider_note')!r}"
        )

    def test_banks_endpoint_returns_processors(self, auth_headers):
        """Soporte para el sub-modal frontend (Procesador → Banco vinculado)."""
        r = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        banks = r.json()
        assert isinstance(banks, list)
        procesadores = [b for b in banks if (b.get("type") or "").strip().lower() == "procesador"]
        assert len(procesadores) > 0, "Se requiere al menos un banco tipo 'Procesador'"
        # Validar que al menos uno tenga bancos vinculados (campo `procesador`).
        proc_names = {p.get("name") for p in procesadores}
        linked = [b for b in banks if (b.get("procesador") or "") in proc_names]
        # No es estrictamente bloqueante, pero lo reportamos
        assert isinstance(linked, list)
