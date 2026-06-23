"""
Iteration 126 - Projects Panel: Production countdown banner + Ficha Técnica quick
access + Ventas Corporativas collective visibility.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"No session_token in response for {email}: {data}"
    return token


@pytest.fixture(scope="module")
def admin_token():
    return _login("rgonzalez@megasoft.com.ve", "admin123")


@pytest.fixture(scope="module")
def vendedor_a_token():
    return _login("mmartin@megasoft.com.ve", "Test1234!")


@pytest.fixture(scope="module")
def vendedor_b_token():
    return _login("mposligua@megasoft.com.ve", "Test1234!")


@pytest.fixture(scope="module")
def implementador_token():
    return _login("Jrojas@megasoft.com.ve", "Test1234!")


def _get_projects(token: str):
    r = requests.get(f"{API}/projects", headers={"Authorization": f"Bearer {token}"}, timeout=60)
    assert r.status_code == 200, f"GET /projects failed: {r.status_code} {r.text[:300]}"
    return r.json()


# === Feature 1: production_days_left field is injected on every project ===
class TestProductionCountdownField:
    def test_admin_projects_have_production_days_left_field(self, admin_token):
        projects = _get_projects(admin_token)
        assert len(projects) > 0
        # every project must carry the key (value can be None / int / -1)
        missing = [p.get("project_id") for p in projects if "production_days_left" not in p]
        assert not missing, f"production_days_left missing in {len(missing)} projects (e.g. {missing[:3]})"

    def test_imminent_project_has_countdown_for_2026_06_24(self, admin_token):
        """The project with fecha_estimada_produccion=2026-06-24 must expose
        production_days_left within banner threshold (<=5). The review request
        named PRY-2026-06-061-PRI but in DB the matching project is the one
        carrying that fecha (see body of test for resolution)."""
        projects = _get_projects(admin_token)
        target = next((p for p in projects
                       if (p.get("fecha_estimada_produccion") or "").startswith("2026-06-24")), None)
        assert target is not None, "No project with fecha_estimada_produccion=2026-06-24 found"
        dl = target.get("production_days_left")
        assert isinstance(dl, int), f"production_days_left should be int, got {type(dl)}"
        assert dl <= 5, f"Expected dl <= 5 to show amber banner, got {dl}"
        assert dl >= 0, f"Date is upcoming so dl should be >= 0, got {dl}"

    def test_far_future_projects_do_not_trigger_banner(self, admin_token):
        projects = _get_projects(admin_token)
        # Projects with production_days_left > 5 OR None should NOT render banner (frontend rule).
        # Backend just exposes the value; assert there exist such projects (banner hidden case).
        far_or_none = [p for p in projects
                       if p.get("production_days_left") is None or (isinstance(p.get("production_days_left"), int) and p["production_days_left"] > 5)]
        assert len(far_or_none) > 0, "Expected at least one project with no/far production date"


# === Feature 2: Ficha Técnica endpoint returns a PDF ===
class TestFichaTecnicaEndpoint:
    def test_ficha_tecnica_pdf_download(self, admin_token):
        projects = _get_projects(admin_token)
        assert projects
        pid = projects[0]["project_id"]
        r = requests.get(
            f"{API}/projects/{pid}/ficha-tecnica",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60,
        )
        assert r.status_code == 200, f"Ficha técnica failed for {pid}: {r.status_code} {r.text[:300]}"
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower(), f"Expected pdf content-type, got {ct}"
        assert r.content[:4] == b"%PDF", "Response is not a valid PDF (missing %PDF header)"


# === Feature 3: Ventas Corporativas collective visibility ===
class TestCorpCollectiveVisibility:
    def test_vendedor_a_sees_team_projects(self, vendedor_a_token):
        projects = _get_projects(vendedor_a_token)
        assert len(projects) >= 30, f"Vendedor A should see ~37 team projects, got {len(projects)}"
        creators = {p.get("created_by_user_id") for p in projects if p.get("created_by_user_id")}
        assert len(creators) >= 2, f"Expected multiple distinct creators, got {creators}"

    def test_vendedor_b_sees_same_team_projects_as_vendedor_a(self, vendedor_a_token, vendedor_b_token):
        a = _get_projects(vendedor_a_token)
        b = _get_projects(vendedor_b_token)
        a_ids = {p["project_id"] for p in a}
        b_ids = {p["project_id"] for p in b}
        assert a_ids == b_ids, (
            f"Corp collective visibility broken. "
            f"A-only: {list(a_ids - b_ids)[:5]} ; B-only: {list(b_ids - a_ids)[:5]}"
        )
        assert len(a_ids) >= 30

    def test_vendedor_b_sees_projects_not_created_by_self(self, vendedor_b_token):
        projects = _get_projects(vendedor_b_token)
        # Identify Vendedor B's user_id from /auth/me
        me = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {vendedor_b_token}"},
            timeout=30,
        )
        assert me.status_code == 200, me.text
        my_uid = me.json().get("user_id")
        assert my_uid
        foreign = [p for p in projects if p.get("created_by_user_id") and p["created_by_user_id"] != my_uid]
        assert len(foreign) > 0, "Vendedor B should also see projects created by OTHER corp members"


# === Feature 4: Implementador isolation regression ===
class TestImplementadorIsolation:
    def test_implementador_sees_only_assigned(self, implementador_token):
        projects = _get_projects(implementador_token)
        me = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {implementador_token}"},
            timeout=30,
        )
        assert me.status_code == 200
        my_uid = me.json().get("user_id")
        assert my_uid
        # Every project visible must be assigned to this implementer
        for p in projects:
            assert p.get("assigned_to_user_id") == my_uid, (
                f"Implementador leak: project {p.get('project_id')} assigned to "
                f"{p.get('assigned_to_user_id')} (expected {my_uid})"
            )
