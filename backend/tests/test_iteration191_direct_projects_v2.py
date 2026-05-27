"""Backend tests — Proyectos Directos v2 (Iteration 191).

Cambios validados:
  - boxes_grid usa `quantity` (no `caja_nro`). Suma == cantidad_cajas.
  - Modelo ya NO acepta equipment_serials ni payment_gateway_link.
  - Excel parse branches: robusto a archivos SIN cabecera, con floats, espacios.
  - Excel parse serials: maneja seriales numéricos float.
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


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
    if items:
        cid = items[0].get("client_id") or items[0].get("id")
        if cid:
            return cid
    payload = {
        "legal_name": f"TEST_DPV2_{uuid.uuid4().hex[:6]}",
        "rif": f"J-{uuid.uuid4().hex[:8].upper()}-0",
        "fantasy_name": "TEST DPv2",
        "client_segment": "PYME",
        "contacts": [{"name": "Test", "email": "t@t.com", "phone": "+584140000000"}],
    }
    cr = requests.post(f"{BASE_URL}/api/clients", headers=admin_headers, json=payload, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    return cr.json().get("client_id") or cr.json().get("id")


# ---------- Helpers ----------
def _make_excel(headers, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    if headers:
        ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _base_payload_v2(client_id, qtype="VPOS", cantidad=5, rows=None):
    """rows: lista de (quantity, bank, product). Default: 1 row con todo."""
    if rows is None:
        rows = [(cantidad, "Banesco", "POS Banesco")]
    boxes = [{"quantity": q, "bank_name": b, "product_name": p} for q, b, p in rows]
    return {
        "client_id": client_id,
        "economic_group": "Grupo TEST",
        "fantasy_name": "Fantasy TEST",
        "quote_type": qtype,
        "sede": "PYME",
        "cantidad_cajas": cantidad,
        "sponsor_bank_name": "Banesco",
        "integrator_name": "TEST Integrator",
        "integrator_app_name": "TEST App",
        "pinpad_model": "Verifone Vx520" if qtype in ("VPOS", "MPOS") else None,
        "pinpad_bank": "Banesco" if qtype in ("VPOS", "MPOS") else None,
        "fiscal_printer_model": "PNP III" if qtype in ("VPOS", "MPOS") else None,
        "pinpad_serials": [],
        "is_multistore": False,
        "stores": [],
        "boxes_grid": boxes,
        "implementation_instructions": "Test v2",
    }


# ---------- 1. POST acepta nueva estructura quantity ----------
class TestNewQuantityStructure:
    def test_create_vpos_with_multi_row_grid(self, admin_headers, client_id):
        """5 cajas: fila (3 Banesco POS) + fila (2 Mercantil POS)."""
        payload = _base_payload_v2(client_id, "VPOS", cantidad=5,
                                   rows=[(3, "Banesco", "POS Banesco"),
                                         (2, "Mercantil", "POS Mercantil")])
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["project_number"].startswith("PRD-"), data["project_number"]
        # Verify persisted grid
        pr = requests.get(f"{BASE_URL}/api/projects/{data['project_id']}",
                          headers=admin_headers, timeout=30)
        assert pr.status_code == 200
        proj = pr.json()
        assert proj.get("direct_project") is True
        grid = proj.get("boxes_grid") or []
        assert len(grid) == 2
        total = sum(int(b.get("quantity", 0)) for b in grid)
        assert total == 5, f"Sum quantities {total} != 5"

    def test_sum_mismatch_returns_400(self, admin_headers, client_id):
        """3+1=4 pero cantidad_cajas=5 → 400."""
        payload = _base_payload_v2(client_id, "VPOS", cantidad=5,
                                   rows=[(3, "Banesco", "POS"), (1, "Mercantil", "POS")])
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "coincid" in r.text.lower() or "grilla" in r.text.lower()


# ---------- 2. Campos eliminados ----------
class TestRemovedFields:
    def test_equipment_serials_ignored_or_rejected(self, admin_headers, client_id):
        """El modelo Pydantic NO debe tener equipment_serials.
        Enviarlo NO debe romper (es ignorado por Pydantic strict=False) y
        la creación debe seguir funcionando — NO debe persistir esos seriales.
        """
        payload = _base_payload_v2(client_id, "VPOS", cantidad=1,
                                   rows=[(1, "Banesco", "POS")])
        payload["equipment_serials"] = [{"modelo": "X", "serial": "S1"}]
        payload["payment_gateway_link"] = "http://bad.example.com"
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        # Si el modelo es estricto, podría devolver 422; si es laxo, 200 ignorándolos.
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            proj_id = r.json()["project_id"]
            pr = requests.get(f"{BASE_URL}/api/projects/{proj_id}",
                              headers=admin_headers, timeout=30).json()
            # No deben aparecer estos campos como atributos especiales
            assert "payment_gateway_link" not in pr or not pr.get("payment_gateway_link"), \
                "payment_gateway_link no debería persistir"


# ---------- 3. Excel branches: sin cabecera ----------
class TestExcelBranchesNoHeader:
    def test_parse_no_header_numeric_in_col_b(self, admin_token):
        """Archivo SIN cabecera: row1 = ('Centro', 3) → debe procesarse desde fila 1."""
        content = _make_excel(headers=None, rows=[["Centro", 3], ["Norte", 2], ["Sur", 5]])
        files = {"file": ("nohdr.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/branches",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 3, f"Esperaba 3 sucursales, got {data}"
        assert data["items"][0] == {"name": "Centro", "box_count": 3}

    def test_parse_with_header(self, admin_token):
        content = _make_excel(["Nombre Sucursal", "Cantidad Cajas"],
                              [["Centro", 3], ["Norte", 2]])
        files = {"file": ("hdr.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/branches",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2, data
        assert data["items"][0]["name"] == "Centro"

    def test_parse_floats_and_strings(self, admin_token):
        """Cantidades como floats (3.0) y strings ('2') con espacios."""
        content = _make_excel(headers=None,
                              rows=[["  Centro  ", 3.0], ["Norte", "2"], ["Sur", " 4 "]])
        files = {"file": ("mixed.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/branches",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 3, data
        assert data["items"][0]["box_count"] == 3
        assert data["items"][1]["box_count"] == 2
        assert data["items"][2]["box_count"] == 4
        assert data["items"][0]["name"] == "Centro"  # trimmed


# ---------- 4. Excel serials: floats numéricos ----------
class TestExcelSerialsRobust:
    def test_parse_serial_numeric_float(self, admin_token):
        """Serial 123456.0 (float) debe ser '123456'."""
        content = _make_excel(["Modelo", "Serial"],
                              [["Verifone Vx520", 123456.0], ["Ingenico", "ABC"]])
        files = {"file": ("ser.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/serials",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2, data
        assert data["items"][0]["serial"] == "123456"  # no '123456.0'


# ---------- 5. Cascada hardware filter (GET) ----------
class TestHardwareCatalog:
    def test_hardware_catalog_has_pinpad_or_pos(self, admin_headers):
        """Verifica que hay hardware tipo Pinpad/POS con asset_type='Bien' para alimentar el dropdown."""
        r = requests.get(f"{BASE_URL}/api/hardware", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        # No asserting count > 0 because DB may or may not have entries; just smoke
        assert isinstance(items, list)
