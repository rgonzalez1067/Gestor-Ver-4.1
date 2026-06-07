# ruff: noqa
"""Backend tests — Módulo Proyectos Directos (Iteration 190).

Cubre el flujo del nuevo endpoint POST /api/direct-projects + plantillas Excel +
catálogo de notificaciones + RBAC.
"""
import io
import os
import uuid
import pytest
import requests

_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND_URL:
    # Read from frontend/.env when running pytest directly
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
NON_ADMIN_EMAIL = "srubio@megasoft.com.ve"
NON_ADMIN_PASS = "Test1234!"


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def non_admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": NON_ADMIN_EMAIL, "password": NON_ADMIN_PASS}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Non-admin login failed: {r.status_code} {r.text}")
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_id(admin_headers):
    """Obtiene un client_id existente o crea TEST_DP_CLIENT."""
    r = requests.get(f"{BASE_URL}/api/clients", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
    if items:
        cid = items[0].get("client_id") or items[0].get("id")
        if cid:
            return cid
    # Create new client
    payload = {
        "legal_name": f"TEST_DP_CLIENT_{uuid.uuid4().hex[:6]}",
        "rif": f"J-{uuid.uuid4().hex[:8].upper()}-0",
        "fantasy_name": "TEST DP",
        "client_segment": "PYME",
        "contacts": [{"name": "Test Contact", "email": "test@test.com", "phone": "+584140000000"}],
    }
    cr = requests.post(f"{BASE_URL}/api/clients", headers=admin_headers, json=payload, timeout=30)
    assert cr.status_code in (200, 201), cr.text
    cid = cr.json().get("client_id") or cr.json().get("id")
    assert cid, cr.text
    return cid


# ---------- Tests: Action Notifications catalog ----------
class TestActionNotificationsCatalog:
    def test_catalog_includes_proyectos_directos(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/action-notifications/catalog",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        biz_types = [b["id"] for b in data.get("business_types", [])]
        assert "proyectos_directos" in biz_types, f"biz_types: {biz_types}"
        allowed = data.get("allowed_actions_by_biz_sub", {})
        # Key uses '_' for None subcategory
        key = "proyectos_directos|_"
        assert key in allowed, f"keys: {list(allowed.keys())}"
        assert "send_to_implementation" in allowed[key]


# ---------- Tests: Excel templates ----------
class TestExcelTemplates:
    def test_serials_template_downloads(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/direct-projects/excel-templates/serials",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text
        # xlsx files start with PK (zip)
        assert r.content[:2] == b"PK", "Not an xlsx file"
        assert "spreadsheetml" in r.headers.get("Content-Type", "")

    def test_branches_template_downloads(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/direct-projects/excel-templates/branches",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.content[:2] == b"PK"


# ---------- Tests: Excel parsing ----------
def _make_excel(headers, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


class TestExcelParsing:
    def test_parse_serials(self, admin_token):
        content = _make_excel(["Modelo", "Serial"],
                              [["Verifone Vx520", "S001"], ["Ingenico", "S002"]])
        files = {"file": ("serials.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/serials",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert data["items"][0]["modelo"] == "Verifone Vx520"
        assert data["items"][0]["serial"] == "S001"

    def test_parse_branches(self, admin_token):
        content = _make_excel(["Nombre Sucursal", "Cantidad Cajas"],
                              [["Centro", 3], ["Norte", 2]])
        files = {"file": ("branches.xlsx", content,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/branches",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert data["items"][0]["name"] == "Centro"
        assert data["items"][0]["box_count"] == 3


# ---------- Tests: POST /api/direct-projects ----------
def _base_payload(client_id, qtype="VPOS", cantidad=2, multi=False):
    boxes = [{"caja_nro": i + 1, "bank_name": "Banesco", "product_name": "POS Banesco"}
             for i in range(cantidad)]
    payload = {
        "client_id": client_id,
        "economic_group": "Grupo TEST",
        "fantasy_name": "Fantasy TEST",
        "quote_type": qtype,
        "sede": "PYME",
        "cantidad_cajas": cantidad,
        "sponsor_bank_id": None,
        "sponsor_bank_name": "Banesco",
        "integrator_name": "TEST Integrator",
        "integrator_app_name": "TEST App",
        "pinpad_model": "Verifone Vx520" if qtype in ("VPOS", "MPOS") else None,
        "pinpad_bank": "Banesco" if qtype in ("VPOS", "MPOS") else None,
        "fiscal_printer_model": "PNP III" if qtype in ("VPOS", "MPOS") else None,
        "equipment_serials": [],
        "pinpad_serials": [],
        "is_multistore": multi,
        "stores": [],
        "boxes_grid": boxes,
        "implementation_instructions": "Test instructions",
    }
    return payload


class TestDirectProjectCreation:
    def test_create_vpos_success(self, admin_headers, client_id):
        payload = _base_payload(client_id, "VPOS", cantidad=2)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["project_id"].startswith("prj_") or "project_id" in data
        assert data["project_number"].startswith("PRD-"), data["project_number"]
        # Verify project in GET /api/projects
        pr = requests.get(f"{BASE_URL}/api/projects/{data['project_id']}",
                          headers=admin_headers, timeout=30)
        assert pr.status_code == 200, pr.text
        proj = pr.json()
        assert proj.get("origin") == "direct"
        assert proj.get("direct_project") is True
        assert proj.get("project_number") == data["project_number"]
        assert "boxes_grid" in proj
        assert len(proj["boxes_grid"]) == 2

    def test_vpos_requires_pinpad(self, admin_headers, client_id):
        payload = _base_payload(client_id, "VPOS", cantidad=1)
        payload["pinpad_model"] = None
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "pinpad" in r.text.lower() or "Pinpad" in r.text

    def test_grid_row_count_mismatch(self, admin_headers, client_id):
        payload = _base_payload(client_id, "VPOS", cantidad=3)
        # Only 2 rows
        payload["boxes_grid"] = payload["boxes_grid"][:2]
        # But still has pinpad
        payload["pinpad_model"] = "Verifone Vx520"
        # Re-add 2 boxes
        payload["boxes_grid"] = [
            {"caja_nro": 1, "bank_name": "Banesco", "product_name": "POS"},
            {"caja_nro": 2, "bank_name": "Banesco", "product_name": "POS"},
        ]
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "grilla" in r.text.lower() or "3" in r.text

    def test_multistore_sum_mismatch(self, admin_headers, client_id):
        payload = _base_payload(client_id, "VPOS", cantidad=3, multi=True)
        # 3 boxes
        payload["boxes_grid"] = [
            {"caja_nro": 1, "bank_name": "Banesco", "product_name": "POS"},
            {"caja_nro": 2, "bank_name": "Banesco", "product_name": "POS"},
            {"caja_nro": 3, "bank_name": "Banesco", "product_name": "POS"},
        ]
        # But stores sum to 5
        payload["stores"] = [{"name": "Centro", "box_count": 2},
                             {"name": "Norte", "box_count": 3}]
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "suma" in r.text.lower() or "coincid" in r.text.lower()

    def test_gateway_does_not_need_pinpad(self, admin_headers, client_id):
        payload = _base_payload(client_id, "GATEWAY", cantidad=1)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["project_number"].startswith("PRD-")


# ---------- Tests: RBAC ----------
class TestRBAC:
    def test_non_admin_blocked(self, non_admin_token, client_id):
        payload = _base_payload(client_id, "VPOS", cantidad=1)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers={"Authorization": f"Bearer {non_admin_token}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=30)
        assert r.status_code == 403, f"Expected 403 got {r.status_code}: {r.text}"
