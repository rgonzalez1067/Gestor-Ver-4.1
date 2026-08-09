"""Tests for Workload Excel (.xlsx) endpoint + parity with PDF (shared _workload_dataset)."""
import io
import os
import pytest
import requests
import openpyxl
from pymongo import MongoClient
from PyPDF2 import PdfReader  # optional; only for page-count sanity

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mongo_projects():
    client = MongoClient(MONGO_URL)
    docs = list(client[DB_NAME].projects.find({}, {"assigned_at": 1}))
    client.close()
    return docs


def _get_xlsx(headers, params=None):
    return requests.get(f"{BASE_URL}/api/projects/reports/workload-xlsx",
                        headers=headers, params=params or {}, timeout=90)


def _get_pdf(headers, params=None):
    return requests.get(f"{BASE_URL}/api/projects/reports/workload-pdf",
                        headers=headers, params=params or {}, timeout=90)


def _load_wb(content):
    return openpyxl.load_workbook(io.BytesIO(content), data_only=True)


def _count_data_rows(ws):
    """Count rows between header row (4) exclusive and TOTAL row (exclusive).
    If no TOTAL row, count all non-empty from row 5.
    """
    header_row = 4
    total_row = None
    for r in range(header_row + 1, ws.max_row + 1):
        v = ws.cell(row=r, column=1).value
        if isinstance(v, str) and v.startswith("TOTAL"):
            total_row = r
            break
    end = (total_row - 1) if total_row else ws.max_row
    n = 0
    for r in range(header_row + 1, end + 1):
        # A row is considered data if any of the first 4 cols is non-empty
        if any(ws.cell(row=r, column=c).value not in (None, "") for c in range(1, 5)):
            n += 1
    return n, total_row


# ============================================================
# Structural tests
# ============================================================
class TestWorkloadXlsxStructure:
    def test_no_filters_returns_xlsx(self, headers):
        r = _get_xlsx(headers)
        assert r.status_code == 200, r.text[:400]
        assert XLSX_CT in r.headers.get("Content-Type", ""), r.headers
        assert r.content[:2] == b"PK", "Not a zip/xlsx container"
        wb = _load_wb(r.content)
        assert "Reporte de Carga" in wb.sheetnames
        ws = wb["Reporte de Carga"]
        # Title A1
        assert ws.cell(row=1, column=1).value and "Reporte de Carga" in ws.cell(row=1, column=1).value
        # Subtitle A2 must include Generado + Agrupado por
        sub = ws.cell(row=2, column=1).value or ""
        assert "Generado" in sub and "Agrupado" in sub
        # Headers row 4
        expected = ["Implementador", "Cliente", "Generador", "RIF", "Tipo", "Cajas", "PVV",
                    "Estado", "% Avance", "Días háb.", "Impl. Original",
                    "Fecha Asignación", "Último Contacto"]
        actual = [ws.cell(row=4, column=i + 1).value for i in range(len(expected))]
        assert actual == expected, actual
        # TOTAL row exists
        n, total_row = _count_data_rows(ws)
        assert total_row is not None, "TOTAL row missing"
        assert n > 0

    def test_group_by_type(self, headers):
        r = _get_xlsx(headers, {"group_by": "type"})
        assert r.status_code == 200
        wb = _load_wb(r.content)
        ws = wb["Reporte de Carga"]
        sub = ws.cell(row=2, column=1).value or ""
        assert "Tipo de Proyecto" in sub


# ============================================================
# Filter respect + PDF parity
# ============================================================
class TestWorkloadXlsxFilters:
    def test_date_range_reduces_rows(self, headers, mongo_projects):
        # No-filter count
        r_all = _get_xlsx(headers)
        wb_all = _load_wb(r_all.content)
        n_all, _ = _count_data_rows(wb_all["Reporte de Carga"])

        params = {"date_from": "2026-06-10", "date_to": "2026-06-10"}
        r = _get_xlsx(headers, params)
        assert r.status_code == 200
        wb = _load_wb(r.content)
        n_filtered, _ = _count_data_rows(wb["Reporte de Carga"])
        assert n_filtered < n_all, f"Filtered ({n_filtered}) should be < all ({n_all})"

        # Expected universe from mongo: assigned_at str[:10] == '2026-06-10'
        expected = sum(1 for d in mongo_projects if str(d.get("assigned_at") or "")[:10] == "2026-06-10")
        assert n_filtered == expected, f"Excel rows {n_filtered} != mongo universe {expected}"

    def test_xlsx_count_matches_pdf_count(self, headers):
        params = {"date_from": "2026-06-10", "date_to": "2026-06-10"}
        r_x = _get_xlsx(headers, params)
        r_p = _get_pdf(headers, params)
        assert r_x.status_code == 200 and r_p.status_code == 200
        wb = _load_wb(r_x.content)
        n_xlsx, _ = _count_data_rows(wb["Reporte de Carga"])

        # Extract PDF count from subtitle "· Proyectos: N" if present; else parse text
        # Use the same subtitle logic: pull all text and search
        try:
            reader = PdfReader(io.BytesIO(r_p.content))
            all_text = ""
            for pg in reader.pages:
                all_text += (pg.extract_text() or "") + "\n"
        except Exception as e:
            pytest.skip(f"PyPDF2 could not read pdf: {e}")

        import re
        m = re.search(r"Total:\s*(\d+)\s*proyecto", all_text)
        assert m, "Could not find 'Total: N proyecto(s)' in PDF"
        n_pdf = int(m.group(1))
        assert n_xlsx == n_pdf, f"XLSX rows {n_xlsx} != PDF projects {n_pdf}"

    def test_empty_range_still_valid_xlsx(self, headers):
        r = _get_xlsx(headers, {"date_from": "2030-01-01", "date_to": "2030-01-02"})
        assert r.status_code == 200
        wb = _load_wb(r.content)
        ws = wb["Reporte de Carga"]
        n, _ = _count_data_rows(ws)
        assert n == 0
