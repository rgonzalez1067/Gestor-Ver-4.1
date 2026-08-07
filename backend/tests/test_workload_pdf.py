"""Tests for Workload PDF endpoint: no-filter bug fix + assigned_at date range feature."""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"


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


def _fetch_pdf(headers, params=None):
    return requests.get(f"{BASE_URL}/api/projects/reports/workload-pdf",
                        headers=headers, params=params or {}, timeout=90)


def _assert_pdf(r, min_size=1000):
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:400]}"
    assert "application/pdf" in r.headers.get("Content-Type", ""), r.headers
    assert r.content.startswith(b"%PDF"), "Content does not start with %PDF"
    assert len(r.content) >= min_size, f"PDF too small: {len(r.content)}"


class TestWorkloadPdfBugFix:
    """Bug fix: generation without any filters must succeed."""

    def test_no_filters_returns_pdf(self, headers):
        r = _fetch_pdf(headers)
        _assert_pdf(r, min_size=1000)

    def test_no_filters_group_by_type(self, headers):
        r = _fetch_pdf(headers, {"group_by": "type"})
        _assert_pdf(r, min_size=1000)


class TestWorkloadPdfDateRange:
    """Feature: strict filter by assigned_at (YYYY-MM-DD lexicographic)."""

    def _count_in_range(self, docs, df=None, dt=None):
        c = 0
        for d in docs:
            a = d.get("assigned_at")
            if not a:
                continue
            s = str(a)[:10]
            if df and s < df:
                continue
            if dt and s > dt:
                continue
            c += 1
        return c

    def test_full_report_baseline(self, headers):
        r = _fetch_pdf(headers)
        _assert_pdf(r)
        self._full_size = len(r.content)

    def test_range_with_data_smaller_than_full(self, headers):
        full = _fetch_pdf(headers)
        _assert_pdf(full)
        ranged = _fetch_pdf(headers, {"date_from": "2026-06-01", "date_to": "2026-06-30"})
        _assert_pdf(ranged)
        assert len(ranged.content) < len(full.content), (
            f"Ranged PDF ({len(ranged.content)}) should be smaller than full ({len(full.content)})")

    def test_empty_range_2030_returns_valid_pdf(self, headers):
        r = _fetch_pdf(headers, {"date_from": "2030-01-01", "date_to": "2030-01-31"})
        _assert_pdf(r, min_size=500)

    def test_only_date_from(self, headers):
        r = _fetch_pdf(headers, {"date_from": "2026-06-10"})
        _assert_pdf(r)

    def test_only_date_to(self, headers):
        r = _fetch_pdf(headers, {"date_to": "2026-06-10"})
        _assert_pdf(r)

    def test_single_day_range(self, headers, mongo_projects):
        expected = self._count_in_range(mongo_projects, "2026-06-10", "2026-06-10")
        r = _fetch_pdf(headers, {"date_from": "2026-06-10", "date_to": "2026-06-10"})
        _assert_pdf(r)
        # Log for visibility
        print(f"[single-day 2026-06-10] expected projects={expected}, pdf_bytes={len(r.content)}")

    def test_no_regression_with_status_filter(self, headers):
        r = _fetch_pdf(headers, {"date_from": "2026-06-01", "date_to": "2026-06-30", "status": "in_progress"})
        _assert_pdf(r, min_size=500)
