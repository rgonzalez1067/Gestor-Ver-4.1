# ruff: noqa
"""Backend tests — Direct Projects Iter38 (Jan 2026).

Validates:
  1. POST /api/direct-projects accepts pinpad_serials with empty modelo.
  2. POST /api/direct-projects validates cantidad_cajas == len(pinpad_serials) for VPOS/MPOS.
  3. POST /api/direct-projects does NOT validate sum(boxes_grid) vs cantidad_cajas.
  4. POST /api/direct-projects still validates sum(stores.box_count) == cantidad_cajas (multitienda).
  5. Created project number uses PRY- prefix (NOT PRD-).
  6. POST /api/direct-projects/excel-parse/serials accepts files with only Serial column (modelo='').
"""
import io
import os
import uuid
import pytest
import requests

_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                _BACKEND_URL = line.split("=", 1)[1].strip()
                break
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
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
    assert items, "No clients in DB to test against"
    return items[0].get("client_id") or items[0].get("id")


def _payload(client_id, qtype="VPOS", cantidad=5, serials=None, boxes=None,
             is_multistore=False, stores=None):
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
        "fiscal_printer_model": None,
        "pinpad_serials": serials if serials is not None else [],
        "is_multistore": is_multistore,
        "stores": stores or [],
        "boxes_grid": boxes if boxes is not None else [
            {"quantity": 1, "bank_name": "Banesco", "product_name": "POS Banesco"}
        ],
        "implementation_instructions": "Test Iter38",
    }


# ---------- 1. pinpad_serials with empty modelo ----------
class TestPinpadSerialEmptyModelo:
    def test_create_with_empty_modelo_succeeds(self, admin_headers, client_id):
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(3)]
        payload = _payload(client_id, "VPOS", cantidad=3, serials=serials)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "project_number" in data
        assert data["project_number"].startswith("PRY-"), \
            f"Expected PRY- prefix, got {data['project_number']}"


# ---------- 2. cantidad_cajas vs len(pinpad_serials) ----------
class TestSerialsCountValidation:
    def test_4_serials_vs_5_cajas_returns_400(self, admin_headers, client_id):
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(4)]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "serial" in r.text.lower() or "coincid" in r.text.lower()

    def test_5_serials_vs_5_cajas_succeeds(self, admin_headers, client_id):
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(5)]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["project_number"].startswith("PRY-")

    def test_link_pago_no_serial_check(self, admin_headers, client_id):
        """LINK_PAGO no requiere validar seriales (no es VPOS/MPOS)."""
        payload = _payload(client_id, "LINK_PAGO", cantidad=2, serials=[])
        # boxes_grid sum no validates
        payload["boxes_grid"] = [{"quantity": 1, "bank_name": "Banesco", "product_name": "Link"}]
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text


# ---------- 3. boxes_grid sum is INDEPENDENT ----------
class TestBoxesGridIndependent:
    def test_grid_more_than_cantidad_succeeds(self, admin_headers, client_id):
        """5 cajas + grid con 10 cajas debe pasar (independiente)."""
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(5)]
        boxes = [{"quantity": 10, "bank_name": "Banesco", "product_name": "POS Banesco"}]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials, boxes=boxes)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text

    def test_grid_less_than_cantidad_succeeds(self, admin_headers, client_id):
        """5 cajas + grid con 1 caja debe pasar."""
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(5)]
        boxes = [{"quantity": 1, "bank_name": "Banesco", "product_name": "POS Banesco"}]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials, boxes=boxes)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text


# ---------- 4. multitienda sum still validated ----------
class TestMultitiendaSum:
    def test_multistore_sum_mismatch_returns_400(self, admin_headers, client_id):
        """5 cajas + stores que suman 6 → 400."""
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(5)]
        stores = [{"name": "Suc A", "box_count": 3}, {"name": "Suc B", "box_count": 3}]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials,
                           is_multistore=True, stores=stores)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "sucursal" in r.text.lower() or "cantidad" in r.text.lower()

    def test_multistore_sum_match_succeeds(self, admin_headers, client_id):
        serials = [{"serial": f"TEST_S{i}_{uuid.uuid4().hex[:4]}", "modelo": ""} for i in range(5)]
        stores = [{"name": "Suc A", "box_count": 2}, {"name": "Suc B", "box_count": 3}]
        payload = _payload(client_id, "VPOS", cantidad=5, serials=serials,
                           is_multistore=True, stores=stores)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text


# ---------- 5. PRY- numbering ----------
class TestPryNumbering:
    def test_project_number_starts_with_pry(self, admin_headers, client_id):
        serials = [{"serial": f"TEST_S{uuid.uuid4().hex[:6]}", "modelo": ""}]
        payload = _payload(client_id, "VPOS", cantidad=1, serials=serials)
        r = requests.post(f"{BASE_URL}/api/direct-projects",
                          headers=admin_headers, json=payload, timeout=60)
        assert r.status_code == 200, r.text
        pn = r.json()["project_number"]
        assert pn.startswith("PRY-"), f"Expected PRY- prefix, got {pn}"
        assert not pn.startswith("PRD-"), f"Must NOT be PRD-: {pn}"


# ---------- 6. Excel parse serials: only Serial column ----------
class TestExcelSerialsOnlySerial:
    def test_parse_only_serial_column(self, admin_token):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Serial"])
        ws.append(["S001"])
        ws.append(["S002"])
        ws.append(["S003"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        files = {"file": ("only_serial.xlsx", buf.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/direct-projects/excel-parse/serials",
                          headers={"Authorization": f"Bearer {admin_token}"},
                          files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # The parser may need both columns; check whether modelo='' is accepted.
        # Iter38 expectation: items returned with modelo=''
        if data.get("total", 0) >= 3:
            for it in data["items"]:
                assert it["serial"] in ("S001", "S002", "S003")
                # modelo should be empty (Iter38: optional)
                assert it.get("modelo", "") == ""
        else:
            # If parser still rejects, this is a bug to report
            pytest.fail(
                f"Excel parser rejected file with only Serial column: {data}. "
                "Iter38 requires modelo to be optional in parser."
            )
