"""Iteration 275 — Repositorio Multiversión de Certificados por Integrador.

Cobertura:
  * POST /api/integrators/{id}/certificates (multipart)
      - Acepta PDF válido (200)
      - Rechaza .txt (400)
      - Rechaza PDF inválido sin cabecera %PDF- (400)
      - 403 para usuario sin rol permitido
  * NO SOBREESCRITURA: 2 uploads → GET list total=2, orden desc, ambos descargables
  * POST /api/integrators/{id}/close incrementa el contador (origin='system', origin_label='Sistema - Cierre Automático')
  * GET /api/integrators/certificates/counts contiene {integrator_id: n}
  * Cleanup: elimina integradores y sus certificados al finalizar
"""
import io
import os
import uuid
import pytest
import requests
from pathlib import Path


def _load_env():
    for p in ["/app/frontend/.env", "/app/backend/.env"]:
        try:
            for line in Path(p).read_text().splitlines():
                if line.strip().startswith("REACT_APP_BACKEND_URL"):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
        except Exception:
            continue
    return None


_URL = os.environ.get("REACT_APP_BACKEND_URL") or _load_env()
assert _URL, "REACT_APP_BACKEND_URL not configured"
BASE_URL = _URL.rstrip("/") + "/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PWD = "admin123"
NOROLE_EMAIL = "jrojas@megasoft.com.ve"   # cargo Implementador (role=user)
NOROLE_PWD = "Test1234!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, f"login admin failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def norole_token():
    # jrojas is role=user (Implementador cargo). The API guard is on role=(admin/implementador/coordinador/gestor)
    # so a plain 'user' should get 403 for POST/close.
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": NOROLE_EMAIL, "password": NOROLE_PWD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Non-admin user not available: {r.status_code} {r.text[:120]}")
    return r.json()["session_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _valid_pdf_bytes():
    """Generate a minimal valid PDF using reportlab."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, f"TEST_CERT_ITER275 {uuid.uuid4().hex[:6]}")
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def integrator_id(admin_token):
    """Create a TEST_ integrator with the required attributes for close_integrator_project.

    We use POST /integrators (admin) to create it and mark project_scope='new' with a certification value 'C'.
    """
    payload = {
        "name": f"TEST_CERT_ITER275_{uuid.uuid4().hex[:6]}",
        "integrator_type": "Integrador",
        "app_name": "TEST_APP",
        "integration_type": "PG",
        "integrator_status": "En proceso",
        "project_scope": "new",
        "certifications": {"Tarjeta de Crédito": "C"},
    }
    r = requests.post(f"{BASE_URL}/integrators", json=payload, headers=_h(admin_token), timeout=20)
    assert r.status_code in (200, 201), f"create integrator failed: {r.status_code} {r.text}"
    data = r.json()
    intg_id = data.get("integrator_id") or (data.get("integrator") or {}).get("integrator_id") or data.get("id")
    assert intg_id, f"cannot resolve integrator_id from response: {data}"
    yield intg_id
    # --- Teardown: delete integrator + its certificates ---
    try:
        # delete certificates directly via mongo? we do it via a dedicated cleanup endpoint if any; otherwise
        # use mongo shell fallback (not available in-container tests). We rely on backend admin delete + best effort.
        requests.delete(f"{BASE_URL}/integrators/{intg_id}", headers=_h(admin_token), timeout=20)
    except Exception:
        pass
    # Best-effort: purge integrator_certificates via a mongo helper if exposed. Not available → we drop only
    # via direct mongo connection below.
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        DB_NAME = os.environ.get("DB_NAME", "test_database")

        async def _purge():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.integrator_certificates.delete_many({"integrator_id": intg_id})
            await db.integrators.delete_many({"integrator_id": intg_id})
            client.close()
        asyncio.get_event_loop().run_until_complete(_purge())
    except Exception:
        pass


# ---------- tests ----------
class TestManualCertificateUpload:
    def test_upload_valid_pdf_returns_ok(self, admin_token, integrator_id):
        files = {"file": ("Certificado_Etapa1.pdf", _valid_pdf_bytes(), "application/pdf")}
        r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("certificate_id", "").startswith("cert_")
        assert data.get("original_name") == "Certificado_Etapa1.pdf"

    def test_upload_txt_is_rejected_400(self, admin_token, integrator_id):
        files = {"file": ("fake.txt", b"hello world", "text/plain")}
        r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400
        assert "PDF" in r.text

    def test_upload_fake_pdf_no_header_rejected_400(self, admin_token, integrator_id):
        # Extension is .pdf, mime says pdf, but bytes don't start with %PDF-
        files = {"file": ("bad.pdf", b"NOTAPDFFILE\x00\x01\x02", "application/pdf")}
        r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400
        assert "válido" in r.text or "PDF" in r.text

    def test_norole_user_gets_403(self, norole_token, integrator_id):
        files = {"file": ("cert.pdf", _valid_pdf_bytes(), "application/pdf")}
        r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                          headers=_h(norole_token), files=files, timeout=20)
        assert r.status_code == 403, f"expected 403 got {r.status_code} {r.text[:200]}"


class TestNoOverwriteAccumulative:
    """Sube 2 PDFs y verifica que total=2, orden desc, y ambos descargables."""

    def test_two_uploads_and_list_desc_and_download(self, admin_token, integrator_id):
        # (test 1 already uploaded Etapa1 in previous class; but pytest may reorder classes.
        # To be safe, upload another two here to reach total>=2.)
        for label in ["Certificado_Etapa2.pdf", "Certificado_Etapa3.pdf"]:
            files = {"file": (label, _valid_pdf_bytes(), "application/pdf")}
            r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                              headers=_h(admin_token), files=files, timeout=30)
            assert r.status_code == 200, f"upload {label}: {r.status_code} {r.text}"

        # List
        r = requests.get(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2, f"expected >=2 certs, got {data['total']}"
        certs = data["certificates"]
        # Verify chronological DESC by created_at
        for i in range(len(certs) - 1):
            assert certs[i]["created_at"] >= certs[i + 1]["created_at"], "not sorted DESC"

        # Newest should be Etapa3 (last one uploaded here)
        assert certs[0]["original_name"] == "Certificado_Etapa3.pdf"

        # Download 2 of them and verify PDF header
        for c in certs[:2]:
            cert_id = c["certificate_id"]
            r2 = requests.get(f"{BASE_URL}/integrators/certificates/{cert_id}/download",
                              headers=_h(admin_token), timeout=20)
            assert r2.status_code == 200
            assert "application/pdf" in r2.headers.get("Content-Type", "").lower()
            assert r2.content[:5] == b"%PDF-", f"not a PDF: first bytes = {r2.content[:8]!r}"


class TestCountsEndpoint:
    def test_counts_contains_integrator(self, admin_token, integrator_id):
        r = requests.get(f"{BASE_URL}/integrators/certificates/counts",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "counts" in data
        assert integrator_id in data["counts"], f"integrator {integrator_id} missing in {data['counts']}"
        assert data["counts"][integrator_id] >= 2


class TestCloseAutoAccumulation:
    """POST /integrators/{id}/close debe agregar UN certificado más con origin='system'."""

    def test_close_increments_counter_and_stores_system_cert(self, admin_token, integrator_id):
        # Count before
        r0 = requests.get(f"{BASE_URL}/integrators/certificates/counts",
                          headers=_h(admin_token), timeout=20)
        before = r0.json()["counts"].get(integrator_id, 0)

        # Close (multipart form). We deliberately do NOT include extra files.
        data = {"componente": "Tokenizador", "version_componente": "1.0.0"}
        r = requests.post(f"{BASE_URL}/integrators/{integrator_id}/close",
                          headers=_h(admin_token), data=data, timeout=45)
        assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
        body = r.json()
        assert body.get("bypass") is False
        assert body.get("certificate_generated") is True

        # Count after: +1
        r1 = requests.get(f"{BASE_URL}/integrators/certificates/counts",
                          headers=_h(admin_token), timeout=20)
        after = r1.json()["counts"].get(integrator_id, 0)
        assert after == before + 1, f"count did not increment: {before} → {after}"

        # Verify the newest entry has origin='system'
        r2 = requests.get(f"{BASE_URL}/integrators/{integrator_id}/certificates",
                          headers=_h(admin_token), timeout=20)
        certs = r2.json()["certificates"]
        assert certs, "empty history"
        newest = certs[0]
        assert newest["origin"] == "system", newest
        assert "Sistema" in newest["origin_label"], newest["origin_label"]

        # Manual certs still present (coexistence)
        manual_count = sum(1 for c in certs if c.get("origin") == "manual")
        assert manual_count >= 2, f"manual certs disappeared: {manual_count}"
