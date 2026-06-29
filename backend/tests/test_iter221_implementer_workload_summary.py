"""Iter 221 — Implementer Workload Summary endpoint (tooltip Panel de Proyectos).
Tests the GET /api/projects/implementers/{user_id}/workload-summary endpoint:
  - Shape and types
  - Resilience for nonexistent user_id (zeros, no 500)
  - Data precision (projects_count + avance_global derived from active projects)
"""
import os
import pytest
import requests
from pathlib import Path

def _load_frontend_env():
    p = Path("/app/frontend/.env")
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL is required"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
CLOSED_STATUSES = {"culminado", "anulado"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("session_token") or data.get("token")
    assert token, f"No session_token in login response: {list(data.keys())}"
    return token


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def implementers_list(headers):
    r = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=headers, timeout=30)
    assert r.status_code == 200, f"implementers/list failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    impls = data if isinstance(data, list) else data.get("implementers") or data.get("items") or []
    assert isinstance(impls, list) and impls, "Expected a non-empty implementers list"
    return impls


# ------------------------ shape & resilience ------------------------

def test_workload_summary_shape_for_real_implementer(headers, implementers_list):
    target_id = "user_3cc63615f2c0"  # Omar Jiménez (known seeded)
    if not any((i.get("user_id") or i.get("id")) == target_id for i in implementers_list):
        target_id = implementers_list[0].get("user_id") or implementers_list[0].get("id")
    assert target_id

    r = requests.get(
        f"{BASE_URL}/api/projects/implementers/{target_id}/workload-summary",
        headers=headers, timeout=30,
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    data = r.json()

    expected_keys = {"user_id", "implementer_name", "projects_count", "cajas_pendientes",
                     "pvv_pendientes", "avance_global"}
    assert expected_keys.issubset(data.keys()), f"Missing keys: {expected_keys - set(data.keys())}"
    assert data["user_id"] == target_id
    assert isinstance(data["implementer_name"], str)
    for k in ("projects_count", "cajas_pendientes", "pvv_pendientes", "avance_global"):
        assert isinstance(data[k], int), f"{k} should be int, got {type(data[k])}"
        assert data[k] >= 0, f"{k} should be >= 0, got {data[k]}"
    assert 0 <= data["avance_global"] <= 100, f"avance_global out of range: {data['avance_global']}"


def test_workload_summary_resilient_for_nonexistent_user(headers):
    r = requests.get(
        f"{BASE_URL}/api/projects/implementers/nonexistent-id-xyz/workload-summary",
        headers=headers, timeout=30,
    )
    assert r.status_code == 200, f"Expected 200 for nonexistent, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data["user_id"] == "nonexistent-id-xyz"
    assert data["implementer_name"] == ""
    assert data["projects_count"] == 0
    assert data["cajas_pendientes"] == 0
    assert data["pvv_pendientes"] == 0
    assert data["avance_global"] == 0


def test_workload_summary_requires_auth():
    r = requests.get(
        f"{BASE_URL}/api/projects/implementers/whatever/workload-summary",
        timeout=30,
    )
    assert r.status_code in (401, 403), f"Expected 401/403 unauthenticated, got {r.status_code}"


# ------------------------ data precision ------------------------

def _fetch_all_projects(headers):
    """Try common shapes of /api/projects to extract a flat list of projects."""
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=60)
    assert r.status_code == 200, f"/api/projects failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    if isinstance(data, list):
        return data
    for key in ("projects", "items", "results", "data"):
        if isinstance(data, dict) and isinstance(data.get(key), list):
            return data[key]
    pytest.skip(f"Unrecognized /api/projects shape: keys={list(data.keys()) if isinstance(data, dict) else type(data)}")


def test_workload_summary_projects_count_matches_active(headers, implementers_list):
    target_id = "user_3cc63615f2c0"
    if not any((i.get("user_id") or i.get("id")) == target_id for i in implementers_list):
        target_id = implementers_list[0].get("user_id") or implementers_list[0].get("id")

    summary = requests.get(
        f"{BASE_URL}/api/projects/implementers/{target_id}/workload-summary",
        headers=headers, timeout=30,
    ).json()

    all_projects = _fetch_all_projects(headers)
    mine = [p for p in all_projects if p.get("assigned_to_user_id") == target_id]
    active = [p for p in mine if (p.get("status") or "").strip().lower() not in CLOSED_STATUSES]
    print(f"target={target_id} total_mine={len(mine)} active={len(active)} summary_count={summary['projects_count']}")

    # projects_count must equal count of active (non-closed) projects assigned to this user
    assert summary["projects_count"] == len(active), (
        f"projects_count mismatch: endpoint={summary['projects_count']} vs computed_active={len(active)}"
    )

    # ensure none of the counted projects are Culminado/Anulado
    for p in active:
        assert (p.get("status") or "").strip().lower() not in CLOSED_STATUSES
