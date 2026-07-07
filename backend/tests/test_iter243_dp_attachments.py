# ruff: noqa
"""Backend tests — Iter 243. Proyectos Directos: Anexos pre-envío.

Cubre:
- POST /api/direct-projects/upload-attachment (staging)
    * Aceptación de tipos válidos (PDF/imagen/csv)
    * Rechazo de tipos no permitidos (.txt, .exe) → 400
    * Rechazo de archivos > 10MB → 400
- POST /api/direct-projects con `attachments`
    * Se persisten en project.attachments (verificado por GET /api/projects/{id})
    * attachments_count en la respuesta
- POST /api/direct-projects SIN anexos → attachments_count=0 (flujo intacto)
"""
import io
import os
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


# -------------------- Fixtures --------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def admin_headers_json(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_id(admin_headers_json):
    """Obtiene un client_id existente para vincular proyectos directos."""
    r = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers_json, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
    assert items, "Necesito al menos un cliente para pruebas"
    for it in items:
        cid = it.get("client_id") or it.get("id")
        if cid:
            return cid
    pytest.skip("No hay clientes disponibles con client_id")


def _base_payload(client_id, cantidad=2, attachments=None):
    boxes = [{"caja_nro": i + 1, "quantity": 1, "bank_name": "Banesco", "product_name": "POS Banesco"}
             for i in range(cantidad)]
    payload = {
        "client_id": client_id,
        "economic_group": "TEST_ITER243 Grupo",
        "fantasy_name": "TEST_ITER243 Fantasy",
        "quote_type": "VPOS",
        "sede": "PYME",
        "cantidad_cajas": cantidad,
        "sponsor_bank_id": None,
        "sponsor_bank_name": "Banesco",
        "integrator_name": "TEST_ITER243 Integrator",
        "integrator_app_name": "TEST_ITER243 App",
        "pinpad_model": "Verifone Vx520",
        "pinpad_bank": "Banesco",
        "fiscal_printer_model": "PNP III",
        "equipment_serials": [],
        "pinpad_serials": [],
        "is_multistore": False,
        "stores": [],
        "boxes_grid": boxes,
        "implementation_instructions": "TEST_ITER243 instructions",
        "server_name": "Multicomercio MSC",
        "comm_type": "SSL",
        "attachments": attachments or [],
    }
    return payload


# -------------------- Upload attachment --------------------
class TestUploadAttachment:
    """POST /api/direct-projects/upload-attachment"""

    def test_upload_pdf_success(self, admin_headers):
        # PDF minimo valido (empieza con %PDF-)
        pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        files = {"file": ("TEST_ITER243.pdf", pdf_bytes, "application/pdf")}
        data = {"category": "Contrato"}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        # Metadata contract
        assert body["attachment_id"].startswith("att_")
        assert body["filename"] == "TEST_ITER243.pdf"
        assert body["storage_key"].startswith("attachments/direct_staging/")
        assert body["url"].startswith("/uploads/")
        assert body["file_size"] == len(pdf_bytes)
        assert body["category"] == "Contrato"
        assert body["content_type"] == "application/pdf"

    def test_upload_png_success(self, admin_headers):
        # PNG minimo (magic bytes)
        png_bytes = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        files = {"file": ("TEST_ITER243.png", png_bytes, "image/png")}
        data = {"category": "Imagen"}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["category"] == "Imagen"
        assert body["file_size"] == len(png_bytes)

    def test_upload_txt_rejected(self, admin_headers):
        files = {"file": ("TEST_ITER243.txt", b"hola", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data={"category": "Otros"},
                          timeout=30)
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "")
        assert "Tipo de archivo no permitido" in detail or ".txt" in detail

    def test_upload_exe_rejected(self, admin_headers):
        files = {"file": ("TEST_ITER243.exe", b"MZ\x00\x00", "application/octet-stream")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data={"category": "Otros"},
                          timeout=30)
        assert r.status_code == 400, r.text

    def test_upload_oversize_rejected(self, admin_headers):
        # > 10MB
        big = b"\x00" * (10 * 1024 * 1024 + 1024)
        files = {"file": ("TEST_ITER243_big.pdf", big, "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data={"category": "Otros"},
                          timeout=60)
        assert r.status_code == 400, r.text
        assert "10MB" in r.json().get("detail", "")

    def test_upload_requires_auth(self):
        pdf_bytes = b"%PDF-1.4\n"
        files = {"file": ("x.pdf", pdf_bytes, "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          files=files, data={"category": "Otros"}, timeout=30)
        assert r.status_code in (401, 403), r.text


# -------------------- Create DP with/without attachments --------------------
class TestDirectProjectWithAttachments:
    """Flujo completo: staging → create → persistencia en project.attachments"""

    def _upload_pdf(self, admin_headers, category="Contrato", label="A"):
        pdf_bytes = (
            b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        )
        files = {"file": (f"TEST_ITER243_{label}.pdf", pdf_bytes, "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/upload-attachment",
                          headers=admin_headers, files=files, data={"category": category},
                          timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_create_dp_with_two_attachments(self, admin_headers, admin_headers_json, client_id):
        # 1) sube 2 anexos
        ref1 = self._upload_pdf(admin_headers, "Contrato", "A")
        ref2 = self._upload_pdf(admin_headers, "Otros", "B")

        # 2) crea proyecto con esas refs
        payload = _base_payload(client_id, cantidad=2, attachments=[ref1, ref2])
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers_json, json=payload, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["attachments_count"] == 2, body
        project_id = body["project_id"]
        assert project_id.startswith("prj_")

        # 3) GET del proyecto → attachments persistidos
        pr = requests.get(f"{BASE_URL}/api/projects/{project_id}",
                          headers=admin_headers_json, timeout=30)
        assert pr.status_code == 200, pr.text
        proj = pr.json()
        assert "attachments" in proj, proj.keys()
        atts = proj["attachments"]
        assert isinstance(atts, list) and len(atts) == 2, atts
        # Los IDs coinciden con los del staging
        ids = {a["attachment_id"] for a in atts}
        assert ref1["attachment_id"] in ids
        assert ref2["attachment_id"] in ids
        # Metadata core preservada
        for a in atts:
            assert a["filename"].startswith("TEST_ITER243_")
            assert a["storage_key"].startswith("attachments/direct_staging/")
            assert a["uploaded_by"]
            assert a.get("source") == "direct_project_creation"
            assert a.get("category") in ("Contrato", "Otros")

    def test_create_dp_without_attachments(self, admin_headers_json, client_id):
        payload = _base_payload(client_id, cantidad=1, attachments=[])
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers_json, json=payload, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["attachments_count"] == 0
        project_id = body["project_id"]
        # GET → attachments vacío/ausente
        pr = requests.get(f"{BASE_URL}/api/projects/{project_id}",
                          headers=admin_headers_json, timeout=30)
        assert pr.status_code == 200, pr.text
        proj = pr.json()
        atts = proj.get("attachments") or []
        # Puede ser lista vacía o no estar el campo — ambos son válidos si es 0.
        assert len(atts) == 0, atts
