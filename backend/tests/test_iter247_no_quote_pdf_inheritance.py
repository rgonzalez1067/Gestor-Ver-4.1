# ruff: noqa
"""Backend tests — Iter 247. BUG FIX: proyecto ya NO debe heredar el PDF de la
cotización al enviarse a Implementación.

Escenarios cubiertos:
  A) Enviar a Implementación SIN anexos manuales → project.attachments == []
     (NO debe estar el PDF de la Cotización category='Cotización').
  B) Enviar a Implementación CON 2 anexos manuales → project.attachments
     contiene EXACTAMENTE esos 2, con source='quote_send_to_implementation'.
     Ninguno debe ser category='Cotización' ni tener inherited_from='cotización'.
  C) Regresión: los anexos manuales siguen siendo descargables por
     GET /api/projects/{project_id}/attachments/{aid}/download.
  D) Paridad Proyectos Directos: al no haber archivos, el botón 'Anexos'
     no debería mostrarse (attachments == []).

Se apoya en iter246 (base flow); refuerza aserciones estrictas
sobre la eliminación del legado (heredaba PDF de Cotización).
"""
import os
import time
import uuid
import pytest
import requests

_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _BACKEND_URL = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
assert _BACKEND_URL, "REACT_APP_BACKEND_URL not set"
BASE_URL = _BACKEND_URL.rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


# -------------------- Fixtures --------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def admin_headers_json(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def borrador_impl_quotes(admin_headers_json):
    """Cotizaciones Borrador/implementation disponibles como fuente."""
    r = requests.get(
        f"{BASE_URL}/api/quotes?limit=200",
        headers=admin_headers_json,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    items = d if isinstance(d, list) else d.get("items") or d.get("quotes") or []
    cand = [
        q for q in items
        if q.get("quote_status") == "Borrador"
        and q.get("quote_category") == "implementation"
    ]
    if len(cand) < 2:
        pytest.skip(
            f"Se necesitan ≥ 2 cotizaciones Borrador/implementation. Encontradas: {len(cand)}"
        )
    return cand


# -------------------- Helpers --------------------
def _upload_manual(headers, filename, ct, raw):
    files = {"file": (filename, raw, ct)}
    r = requests.post(
        f"{BASE_URL}/api/quotes/manual-attachments/upload",
        headers=headers,
        files=files,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _send_to_impl(headers_json, quote_id, attachment_ids=None, reason="TEST_ITER247 excepcion"):
    hdr = dict(headers_json)
    hdr["x-exception-reason"] = reason
    if attachment_ids:
        hdr["x-manual-attachment-ids"] = ",".join(attachment_ids)
    r = requests.post(
        f"{BASE_URL}/api/quotes/{quote_id}/send-to-implementation",
        headers=hdr,
        json={},
        timeout=90,
    )
    return r


def _find_project_by_quote(headers_json, quote_id):
    r = requests.get(
        f"{BASE_URL}/api/projects?limit=300",
        headers=headers_json,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    items = d if isinstance(d, list) else d.get("items") or d.get("projects") or []
    for p in items:
        if p.get("quote_id") == quote_id:
            return p
    return None


def _get_project_detail(headers_json, project_id):
    r = requests.get(
        f"{BASE_URL}/api/projects/{project_id}",
        headers=headers_json,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _wait_project(headers_json, quote_id, retries=6, delay=0.5):
    proj = None
    for _ in range(retries):
        proj = _find_project_by_quote(headers_json, quote_id)
        if proj:
            return proj
        time.sleep(delay)
    return proj


def _assert_no_quote_pdf_leak(attachments):
    """Núcleo de la aserción del bug: NINGÚN item del proyecto debe:
       - tener category == 'Cotización'
       - tener inherited_from == 'cotización'
       - ser el PDF de la cotización (nombre 'Cotizacion_...' con source='inherited' o similar).
    """
    bad = []
    for a in attachments:
        cat = (a.get("category") or "").strip()
        inh = (a.get("inherited_from") or "").strip().lower()
        if cat == "Cotización" or cat.lower() == "cotización":
            bad.append({"reason": "category==Cotización", "att": a})
        if inh in ("cotización", "cotizacion", "quote"):
            bad.append({"reason": f"inherited_from={inh}", "att": a})
    assert not bad, f"Hay anexos que provienen de la cotización (bug fix regresó): {bad}"


# -------------------- Tests --------------------
class TestQuoteToProjectNoInheritance:
    """Contract del fix: proyecto ya NO hereda anexos de la cotización."""

    # ---------- Escenario A: sin anexos manuales ----------
    def test_scenario_A_no_manual_attachments_yields_empty_project_attachments(
        self, admin_headers_json, borrador_impl_quotes
    ):
        quote = borrador_impl_quotes[0]
        qid = quote["quote_id"]

        r = _send_to_impl(admin_headers_json, qid, attachment_ids=None)
        assert r.status_code == 200, f"send-to-impl fallo: {r.status_code} {r.text}"
        payload = r.json()
        assert payload.get("new_status") == "Enviada a Imple", payload

        proj = _wait_project(admin_headers_json, qid)
        assert proj is not None, f"No se encontró proyecto por quote_id={qid}"
        project_id = proj["project_id"]

        detail = _get_project_detail(admin_headers_json, project_id)
        atts = detail.get("attachments") or []

        # Aserción principal: SIN anexos, project.attachments == []
        assert atts == [], (
            f"BUG REGRESADO: project.attachments deberia estar VACIO, "
            f"got {len(atts)}: {atts}"
        )
        # Y aunque este vacio, aseguramos que no hay categoria 'Cotización'.
        _assert_no_quote_pdf_leak(atts)

        # Guardar para test de aislamiento posterior
        TestQuoteToProjectNoInheritance._prj_empty = {"project_id": project_id}

    # ---------- Escenario B: con anexos manuales ----------
    def test_scenario_B_with_manual_attachments_contains_only_those(
        self, admin_headers, admin_headers_json, borrador_impl_quotes
    ):
        a1 = _upload_manual(admin_headers, "TEST_ITER247_contrato.pdf", "application/pdf", PDF_BYTES)
        a2 = _upload_manual(admin_headers, "TEST_ITER247_mapa.png", "image/png", PNG_BYTES)
        expected_filenames = {a1["filename"], a2["filename"]}

        quote = borrador_impl_quotes[1]
        qid = quote["quote_id"]

        r = _send_to_impl(
            admin_headers_json,
            qid,
            attachment_ids=[a1["attachment_id"], a2["attachment_id"]],
        )
        assert r.status_code == 200, f"send-to-impl fallo: {r.status_code} {r.text}"
        assert r.json().get("new_status") == "Enviada a Imple"

        proj = _wait_project(admin_headers_json, qid)
        assert proj is not None, f"No se encontró proyecto por quote_id={qid}"
        project_id = proj["project_id"]

        detail = _get_project_detail(admin_headers_json, project_id)
        atts = detail.get("attachments") or []

        # Aserción CLAVE del fix: SOLO deben estar los 2 anexos manuales;
        # ningún PDF de Cotización heredado.
        assert len(atts) == 2, (
            f"esperados 2 anexos EXACTOS (solo manuales), got {len(atts)}: {atts}"
        )
        _assert_no_quote_pdf_leak(atts)

        # Los 2 deben tener source='quote_send_to_implementation'
        sources = [a.get("source") for a in atts]
        assert all(s == "quote_send_to_implementation" for s in sources), (
            f"sources inesperados: {sources}"
        )

        # Filenames y estructura
        got_filenames = {a.get("filename") for a in atts}
        assert got_filenames == expected_filenames, (
            f"filenames desalineados. esperados={expected_filenames} got={got_filenames}"
        )

        for a in atts:
            assert a.get("attachment_id", "").startswith("att_"), a
            assert a.get("storage_key", "").startswith(f"attachments/{project_id}/"), a
            assert a.get("url", "").startswith("/uploads/"), a
            assert (a.get("category") or "") == "Otros", (
                f"category del anexo manual debe ser 'Otros', got={a.get('category')}"
            )
            assert isinstance(a.get("file_size"), int) and a["file_size"] > 0

        TestQuoteToProjectNoInheritance._prj_with_manual = {
            "project_id": project_id,
            "attachments": atts,
        }

    # ---------- Escenario C: descarga sigue funcionando ----------
    def test_scenario_C_manual_attachments_downloadable(self, admin_headers_json):
        state = getattr(TestQuoteToProjectNoInheritance, "_prj_with_manual", None)
        if not state:
            pytest.skip("Depende del escenario B.")

        for a in state["attachments"]:
            url = f"{BASE_URL}/api/projects/{state['project_id']}/attachments/{a['attachment_id']}/download"
            r = requests.get(url, headers=admin_headers_json, timeout=30)
            assert r.status_code == 200, f"download fallo: {r.status_code} {r.text}"
            content = r.content
            fn = a["filename"].lower()
            if fn.endswith(".pdf"):
                assert content.startswith(b"%PDF-"), f"PDF invalido: {content[:20]!r}"
                assert content == PDF_BYTES, "PDF binario descargado no coincide con el subido"
            elif fn.endswith(".png"):
                assert content.startswith(b"\x89PNG\r\n\x1a\n"), f"PNG invalido: {content[:20]!r}"
                assert content == PNG_BYTES, "PNG binario descargado no coincide con el subido"

    # ---------- Escenario D: paridad con Proyectos Directos ----------
    def test_scenario_D_parity_direct_projects_empty_start(self, admin_headers_json):
        """El proyecto creado desde cotización SIN anexos manuales debe iniciar
        con project.attachments == [], igual que un Proyecto Directo. Esto
        garantiza que el botón 'Anexos' no aparezca en el UI (solo aparece si
        hay al menos 1 anexo)."""
        state = getattr(TestQuoteToProjectNoInheritance, "_prj_empty", None)
        if not state:
            pytest.skip("Depende del escenario A.")

        detail = _get_project_detail(admin_headers_json, state["project_id"])
        atts = detail.get("attachments")
        # Debe existir el campo (contract) y estar vacio.
        assert atts is not None, "project.attachments deberia ser [] (no None) por contract."
        assert atts == [], f"project.attachments deberia ser vacio: {atts}"

    # ---------- Aislamiento (mantiene la garantia de iter246) ----------
    def test_no_leak_between_projects(self, admin_headers_json):
        """El anexo manual del proyecto B no debe descargarse desde el project_id vacio (A)."""
        prj_with = getattr(TestQuoteToProjectNoInheritance, "_prj_with_manual", None)
        prj_empty = getattr(TestQuoteToProjectNoInheritance, "_prj_empty", None)
        if not prj_with or not prj_empty:
            pytest.skip("Depende de escenarios A y B.")

        aid = prj_with["attachments"][0]["attachment_id"]
        url = f"{BASE_URL}/api/projects/{prj_empty['project_id']}/attachments/{aid}/download"
        r = requests.get(url, headers=admin_headers_json, timeout=30)
        assert r.status_code == 404, f"esperado 404 por aislamiento, got {r.status_code}: {r.text[:200]}"
