# ruff: noqa
"""Backend tests — Iter 246. Homologación de anexos: Cotización → Proyecto.

Cubre:
- POST /api/quotes/manual-attachments/upload (staging temp)
- POST /api/quotes/{quote_id}/send-to-implementation con header
  `x-manual-attachment-ids` → los anexos deben persistirse en
  project.attachments con la MISMA estructura que Proyectos Directos.
- GET /api/projects/{project_id}/attachments/{attachment_id}/download
  para los anexos persistidos desde la cotización.
- Regresión: enviar a Implementación sin anexos → proyecto sin
  project.attachments (no rompe el flujo).
- Aislamiento: los anexos del proyecto A NO deben aparecer en el proyecto B.
"""
import os
import time
import uuid
import base64
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

# PDF minimo valido para prueba (magic %PDF-)
PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
# PNG minimo (magic bytes)
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
    """Devuelve una lista de cotizaciones en estado Borrador + implementation."""
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
def _upload_manual(admin_headers, filename, ct, raw):
    files = {"file": (filename, raw, ct)}
    r = requests.post(
        f"{BASE_URL}/api/quotes/manual-attachments/upload",
        headers=admin_headers,
        files=files,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _send_to_impl(admin_headers_json, quote_id, attachment_ids=None, reason="TEST_ITER246 excepcion"):
    hdr = dict(admin_headers_json)
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


def _find_project_by_quote(admin_headers_json, quote_id):
    """Busca en /api/projects el proyecto cuyo quote_id coincide."""
    r = requests.get(
        f"{BASE_URL}/api/projects?limit=200",
        headers=admin_headers_json,
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    items = d if isinstance(d, list) else d.get("items") or d.get("projects") or []
    for p in items:
        if p.get("quote_id") == quote_id:
            return p
    # Fallback: pedir el proyecto por-id no es posible sin conocerlo — devolver None.
    return None


# -------------------- Test class --------------------
class TestQuoteImplAttachmentsHomologation:
    """Homologación: anexos subidos en 'Personalizar Comunicación' al enviar
    a Implementación → persistidos en project.attachments (paridad con
    Proyectos Directos)."""

    def test_manual_upload_pdf_ok(self, admin_headers):
        body = _upload_manual(admin_headers, "TEST_ITER246_A.pdf", "application/pdf", PDF_BYTES)
        assert body["attachment_id"].startswith("matt_"), body
        assert body["filename"] == "TEST_ITER246_A.pdf"
        assert body["size"] == len(PDF_BYTES)
        assert body["content_type"].startswith("application/pdf")

    def test_manual_upload_png_ok(self, admin_headers):
        body = _upload_manual(admin_headers, "TEST_ITER246_map.png", "image/png", PNG_BYTES)
        assert body["attachment_id"].startswith("matt_"), body
        assert body["filename"] == "TEST_ITER246_map.png"

    def test_send_to_impl_persists_attachments(
        self, admin_headers, admin_headers_json, borrador_impl_quotes
    ):
        """Flujo completo: upload → send-to-impl → project.attachments."""
        # 1) Preparar 2 anexos manuales
        a1 = _upload_manual(admin_headers, "TEST_ITER246_contrato.pdf", "application/pdf", PDF_BYTES)
        a2 = _upload_manual(admin_headers, "TEST_ITER246_mapa.png", "image/png", PNG_BYTES)
        att_ids_expected = {a1["attachment_id"], a2["attachment_id"]}

        # 2) Tomar la 1ra cotización disponible y enviarla a implementación
        quote = borrador_impl_quotes[0]
        qid = quote["quote_id"]
        r = _send_to_impl(admin_headers_json, qid, attachment_ids=list(att_ids_expected))
        assert r.status_code == 200, f"send-to-impl fallo: {r.status_code} {r.text}"
        payload = r.json()
        assert payload.get("new_status") == "Enviada a Imple", payload

        # 3) Buscar el proyecto creado por quote_id
        # Esperar un instante para que el $push termine (mongo es rápido, pero por seguridad).
        proj = None
        for _ in range(5):
            proj = _find_project_by_quote(admin_headers_json, qid)
            if proj:
                break
            time.sleep(0.5)
        assert proj is not None, f"No se encontró proyecto por quote_id={qid}"
        project_id = proj["project_id"]

        # 4) GET del proyecto — obtenemos el detalle completo con attachments
        r = requests.get(
            f"{BASE_URL}/api/projects/{project_id}",
            headers=admin_headers_json,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        detail = r.json()

        all_atts = detail.get("attachments") or []
        # El proyecto puede heredar además el PDF de la cotización (category="Cotización",
        # inherited_from="cotización"). Filtramos SOLO los manuales para el contract test.
        atts = [a for a in all_atts if a.get("source") == "quote_send_to_implementation"]
        assert len(atts) == 2, (
            f"esperados 2 anexos con source='quote_send_to_implementation', "
            f"got {len(atts)} de {len(all_atts)} totales: {all_atts}"
        )

        # 5) Verificar contract/estructura (paridad Proyectos Directos + campos exigidos)
        for a in atts:
            # attachment_id nuevo (att_...) — NO reutiliza el matt_ del staging
            aid = a.get("attachment_id", "")
            assert aid.startswith("att_"), f"attachment_id inesperado: {aid}"
            assert a.get("filename", "").startswith("TEST_ITER246_")
            # storage_key exacto: attachments/{project_id}/...
            assert a.get("storage_key", "").startswith(f"attachments/{project_id}/"), a
            assert a.get("url", "").startswith("/uploads/")
            assert a.get("uploaded_by")
            assert a.get("uploaded_by_name")
            assert a.get("uploaded_at")
            assert isinstance(a.get("file_size"), int) and a["file_size"] > 0
            assert a.get("content_type")
            assert a.get("category") == "Otros"
            assert a.get("source") == "quote_send_to_implementation"

        # Guardar para próximos tests
        TestQuoteImplAttachmentsHomologation._prj_with_atts = {
            "project_id": project_id,
            "attachments": atts,
        }

    def test_download_persisted_attachments_ok(self, admin_headers_json):
        state = getattr(TestQuoteImplAttachmentsHomologation, "_prj_with_atts", None)
        if not state:
            pytest.skip("Depende de test_send_to_impl_persists_attachments (skipped/fallado).")

        for a in state["attachments"]:
            url = f"{BASE_URL}/api/projects/{state['project_id']}/attachments/{a['attachment_id']}/download"
            r = requests.get(url, headers=admin_headers_json, timeout=30)
            assert r.status_code == 200, f"download fallo: {r.status_code} {r.text}"
            # El binario devuelto debe coincidir con lo subido
            # PDF: los primeros 5 bytes son %PDF-
            # PNG: los primeros 8 bytes son la firma PNG estándar
            fn = a["filename"].lower()
            content = r.content
            if fn.endswith(".pdf"):
                assert content.startswith(b"%PDF-"), f"contenido PDF invalido: {content[:20]!r}"
                assert content == PDF_BYTES, "El binario descargado no coincide con el original"
            elif fn.endswith(".png"):
                assert content.startswith(b"\x89PNG\r\n\x1a\n"), f"contenido PNG invalido: {content[:20]!r}"
                assert content == PNG_BYTES, "El binario descargado no coincide con el original"

    def test_download_nonexistent_attachment_404(self, admin_headers_json):
        state = getattr(TestQuoteImplAttachmentsHomologation, "_prj_with_atts", None)
        if not state:
            pytest.skip("Depende de test_send_to_impl_persists_attachments.")
        fake_id = f"att_{uuid.uuid4().hex[:12]}"
        url = f"{BASE_URL}/api/projects/{state['project_id']}/attachments/{fake_id}/download"
        r = requests.get(url, headers=admin_headers_json, timeout=30)
        assert r.status_code == 404, r.text

    def test_send_to_impl_without_attachments_ok(
        self, admin_headers_json, borrador_impl_quotes
    ):
        """Regresión: si no hay anexos manuales, el proyecto se crea igual y
        project.attachments queda vacío (o ausente)."""
        # Usar una cotización DISTINTA a la del test anterior
        quote = borrador_impl_quotes[1]
        qid = quote["quote_id"]
        r = _send_to_impl(admin_headers_json, qid, attachment_ids=None)
        assert r.status_code == 200, r.text
        assert r.json().get("new_status") == "Enviada a Imple"

        proj = None
        for _ in range(5):
            proj = _find_project_by_quote(admin_headers_json, qid)
            if proj:
                break
            time.sleep(0.5)
        assert proj is not None, f"No se encontró proyecto por quote_id={qid}"

        d = requests.get(
            f"{BASE_URL}/api/projects/{proj['project_id']}",
            headers=admin_headers_json,
            timeout=30,
        )
        assert d.status_code == 200, d.text
        all_atts = d.json().get("attachments") or []
        # Filtrar solo los provenientes del modal 'Personalizar Comunicación' —
        # el proyecto puede heredar el PDF de la cotización (category="Cotización").
        manual_atts = [a for a in all_atts if a.get("source") == "quote_send_to_implementation"]
        assert len(manual_atts) == 0, (
            f"esperado 0 anexos manuales, got {len(manual_atts)}: {manual_atts}"
        )

        # Guardar para siguiente test (aislamiento)
        TestQuoteImplAttachmentsHomologation._prj_without_atts = {
            "project_id": proj["project_id"],
        }

    def test_no_leak_between_projects(self, admin_headers_json):
        """Aislamiento: los anexos del proyecto A no deben descargarse desde
        el proyecto B (aunque el attachment_id sea válido en A)."""
        prj_a = getattr(TestQuoteImplAttachmentsHomologation, "_prj_with_atts", None)
        prj_b = getattr(TestQuoteImplAttachmentsHomologation, "_prj_without_atts", None)
        if not prj_a or not prj_b:
            pytest.skip("Depende de test_send_to_impl_persists_attachments y sin_attachments.")

        # Intentar descargar el anexo del proyecto A usando el project_id del B → 404
        aid = prj_a["attachments"][0]["attachment_id"]
        url = f"{BASE_URL}/api/projects/{prj_b['project_id']}/attachments/{aid}/download"
        r = requests.get(url, headers=admin_headers_json, timeout=30)
        assert r.status_code == 404, f"esperado 404 por aislamiento, got {r.status_code} {r.text[:200]}"

    def test_send_to_impl_without_reason_fails_422(
        self, admin_headers_json, borrador_impl_quotes
    ):
        """Sanity: sin motivo de excepción en Borrador → 422 (IRREGULAR)."""
        if len(borrador_impl_quotes) < 3:
            pytest.skip("No hay una 3ra cotización disponible para prueba negativa.")
        quote = borrador_impl_quotes[2]
        qid = quote["quote_id"]
        hdr = dict(admin_headers_json)
        # NO enviar x-exception-reason
        r = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/send-to-implementation",
            headers=hdr,
            json={},
            timeout=30,
        )
        assert r.status_code == 422, r.text
        assert "IRREGULAR" in r.json().get("detail", ""), r.text
