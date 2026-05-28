"""Iter39 — PVV + direct projects + workload PDF backend tests."""
import os
import pytest
import requests

def _load_backend_url():
    url = os.environ.get('REACT_APP_BACKEND_URL')
    if not url:
        # Fallback to frontend/.env (testing context)
        try:
            with open('/app/frontend/.env') as f:
                for line in f:
                    if line.startswith('REACT_APP_BACKEND_URL='):
                        url = line.split('=', 1)[1].strip()
                        break
        except Exception:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip('/')


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    }, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------- Test: GET /api/projects includes pvv_count ----------
class TestProjectsListPvv:
    def test_projects_list_includes_pvv_count(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        # response is a list or {projects: [...]}
        projects = data if isinstance(data, list) else data.get("projects", data.get("items", []))
        assert isinstance(projects, list), f"unexpected shape: {type(data)}"
        assert len(projects) > 0, "expected at least 1 project"
        # Every project must include pvv_count, never null
        missing = [p.get("id") for p in projects if "pvv_count" not in p]
        nulls = [p.get("id") for p in projects if p.get("pvv_count") is None]
        assert not missing, f"{len(missing)} projects missing pvv_count: {missing[:5]}"
        assert not nulls, f"{len(nulls)} projects have pvv_count=null: {nulls[:5]}"
        # All ints
        for p in projects:
            assert isinstance(p["pvv_count"], int), f"pvv_count not int for {p.get('id')}: {p['pvv_count']}"
        # store for next tests
        TestProjectsListPvv.sample_projects = projects

    def test_pvv_formula_matches_helper(self, auth_headers):
        """pvv_count = cantidad_cajas × n_combos (or just cantidad_cajas if matrix empty)."""
        projects = getattr(TestProjectsListPvv, "sample_projects", None)
        assert projects, "previous test should have populated sample_projects"
        # Need full project to validate matrix — list endpoint may not include matrix
        mismatches = []
        checked = 0
        for p in projects[:15]:
            pid = p.get("project_id") or p.get("id")
            if not pid:
                continue
            detail = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=auth_headers, timeout=30)
            if detail.status_code != 200:
                continue
            d = detail.json()
            matrix = d.get("implementation_matrix") or {}
            n_combos = 0
            for bank, prods in matrix.items():
                if isinstance(prods, dict):
                    n_combos += len(prods)
            cajas = int(d.get("cantidad_cajas") or d.get("box_count") or 0)
            expected = cajas if n_combos <= 0 else cajas * n_combos
            actual = d.get("pvv_count")
            if actual != expected:
                mismatches.append({"id": pid, "cajas": cajas, "n_combos": n_combos,
                                   "expected": expected, "actual": actual})
            checked += 1
        assert checked > 0, "no projects could be checked"
        assert not mismatches, f"PVV mismatches in {len(mismatches)}/{checked}: {mismatches[:5]}"

    def test_pvv_at_least_equals_cajas(self, auth_headers):
        projects = getattr(TestProjectsListPvv, "sample_projects", None) or []
        bad = []
        for p in projects:
            cajas = p.get("cantidad_cajas") or p.get("box_count") or 0
            try:
                cajas = int(cajas)
            except Exception:
                cajas = 0
            pvv = p.get("pvv_count", 0)
            if cajas > 0 and pvv < cajas:
                bad.append({"id": p.get("id"), "cajas": cajas, "pvv": pvv})
        assert not bad, f"PVV < cajas in {len(bad)} projects: {bad[:5]}"


# ---------- Test: GET /api/projects/{id} includes pvv_count ----------
class TestProjectDetailPvv:
    def test_detail_includes_pvv(self, auth_headers):
        # Pick a project with assignee from list
        r = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        data = r.json()
        projects = data if isinstance(data, list) else data.get("projects", data.get("items", []))
        # Find one with assigned_to_user_id
        target = next((p for p in projects if p.get("assigned_to_user_id") or p.get("assigned_to_name")), None)
        if not target:
            target = projects[0]
        pid = target.get("project_id") or target.get("id")
        d = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=auth_headers, timeout=30)
        assert d.status_code == 200, f"detail failed: {d.status_code} {d.text[:200]}"
        body = d.json()
        assert "pvv_count" in body, "detail missing pvv_count"
        assert isinstance(body["pvv_count"], int)
        assert body["pvv_count"] >= 0


# ---------- Test: Direct projects count ----------
class TestDirectProjects:
    def test_direct_projects_exist(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        data = r.json()
        projects = data if isinstance(data, list) else data.get("projects", data.get("items", []))
        direct = [p for p in projects if p.get("direct_project") is True]
        # Expected ~9 per spec
        assert len(direct) >= 1, f"expected direct_project=true rows, got {len(direct)}"
        print(f"Direct projects count: {len(direct)}")

    def test_unassigned_projects_exist(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers, timeout=60)
        assert r.status_code == 200
        data = r.json()
        projects = data if isinstance(data, list) else data.get("projects", data.get("items", []))
        unassigned = [p for p in projects if not p.get("assigned_to_user_id")]
        print(f"Unassigned projects: {len(unassigned)} / total {len(projects)}")
        assert len(unassigned) >= 1


# ---------- Test: Workload PDF ----------
class TestWorkloadPdf:
    def test_workload_pdf_returns_pdf(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/projects/reports/workload-pdf",
                         headers=auth_headers, timeout=60)
        assert r.status_code == 200, f"status {r.status_code}: {r.text[:300]}"
        ct = r.headers.get("content-type", "").lower()
        assert "application/pdf" in ct, f"content-type not pdf: {ct}"
        assert r.content[:8].startswith(b"%PDF-"), f"missing PDF header, got: {r.content[:20]!r}"
        print(f"PDF size: {len(r.content)} bytes, header: {r.content[:8]!r}")
