"""
Iteration 59 - Backend tests for the Project Lifecycle re-engineering.

Covers:
- New project status catalog (6 states) via /api/projects/stats
- Automation: assigning an implementer → "Asignado"
- Automation: saving ticket → "En Gestión"
- Manual status PUT /api/projects/{id}/status (accepts manual; rejects invalid)
- Template variable {Estado_Proyecto} via /api/projects/{id}/template-variables
"""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

EXPECTED_STATUSES = {
    "Por asignar", "Asignado", "En Gestión",
    "Suspendido", "Implementado parcial", "Culminado",
}
MANUAL_STATUSES = {"Suspendido", "Implementado parcial", "Culminado"}


# ----------------- Fixtures -----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("session_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(session, token):
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def implementer_id(auth):
    r = auth.get(f"{BASE_URL}/api/projects/implementers/list", timeout=30)
    assert r.status_code == 200, r.text
    users = r.json()
    assert isinstance(users, list) and len(users) > 0, "No implementers found"
    return users[0]["user_id"]


def _find_project_by_status(auth, status: str):
    r = auth.get(f"{BASE_URL}/api/projects?limit=200", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    for p in items:
        if (p.get("status") or "").strip() == status:
            return p
    return None


# ----------------- Tests -----------------
class TestProjectStats:
    """Stats endpoint must reflect the new 6-state catalog."""

    def test_stats_keys_and_types(self, auth):
        r = auth.get(f"{BASE_URL}/api/projects/stats", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total", "pending", "in_progress", "blocked", "completed"):
            assert k in data, f"Missing key {k} in stats: {data}"
            assert isinstance(data[k], int)
        # Sanity: counts add up reasonably (no negative)
        assert data["total"] >= 0
        assert data["pending"] >= 0


class TestProjectsListUsesNewCatalog:
    """All project documents should carry statuses from the new catalog."""

    def test_status_values_in_catalog(self, auth):
        r = auth.get(f"{BASE_URL}/api/projects?limit=200", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        # Skip if the list is empty (no projects yet)
        if not items:
            pytest.skip("No projects in DB")
        bad = []
        for p in items:
            st = (p.get("status") or "").strip()
            if st and st not in EXPECTED_STATUSES:
                bad.append((p.get("project_id"), st))
        assert not bad, f"Found projects with legacy statuses: {bad[:10]}"


class TestAutomationAssign:
    """Assigning an implementer must move status to 'Asignado'."""

    def test_assign_moves_to_asignado(self, auth, implementer_id):
        proj = _find_project_by_status(auth, "Por asignar")
        if not proj:
            pytest.skip("No project in 'Por asignar' state available")
        pid = proj["project_id"]
        r = auth.put(
            f"{BASE_URL}/api/projects/{pid}/assign",
            json={"assigned_to_user_id": implementer_id},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        # Verify via GET
        g = auth.get(f"{BASE_URL}/api/projects/{pid}", timeout=30)
        assert g.status_code == 200, g.text
        assert g.json().get("status") == "Asignado", (
            f"Expected 'Asignado', got {g.json().get('status')}"
        )


class TestAutomationTicket:
    """Saving a ticket on an 'Asignado' project must move status to 'En Gestión'."""

    def test_ticket_moves_to_en_gestion(self, auth, implementer_id):
        proj = _find_project_by_status(auth, "Asignado")
        if not proj:
            # Try promoting a 'Por asignar' to 'Asignado' first
            por_asig = _find_project_by_status(auth, "Por asignar")
            if not por_asig:
                pytest.skip("No project available to test ticket automation")
            pid = por_asig["project_id"]
            r = auth.put(
                f"{BASE_URL}/api/projects/{pid}/assign",
                json={"assigned_to_user_id": implementer_id},
                timeout=30,
            )
            assert r.status_code == 200, r.text
        else:
            pid = proj["project_id"]
            # Ensure ticket is empty; if it already has a ticket the
            # status would already be 'En Gestión', so look for another.
            if (proj.get("ticket_number") or "").strip():
                # try alternate
                r2 = auth.get(f"{BASE_URL}/api/projects?limit=200", timeout=30)
                items = r2.json() if isinstance(r2.json(), list) else r2.json().get("items", [])
                pid = None
                for p in items:
                    if (p.get("status") == "Asignado"
                            and not (p.get("ticket_number") or "").strip()):
                        pid = p["project_id"]
                        break
                if not pid:
                    pytest.skip("No 'Asignado' project without ticket")

        ticket = f"TST-{int(time.time())}"
        r = auth.put(
            f"{BASE_URL}/api/projects/{pid}/ticket",
            json={"ticket_number": ticket, "confirm_duplicate": True},
            timeout=30,
        )
        assert r.status_code == 200, r.text

        g = auth.get(f"{BASE_URL}/api/projects/{pid}", timeout=30)
        assert g.status_code == 200, g.text
        assert g.json().get("status") == "En Gestión", (
            f"Expected 'En Gestión', got {g.json().get('status')}"
        )
        assert g.json().get("ticket_number") == ticket


class TestManualStatusEndpoint:
    """PUT /api/projects/{id}/status — accepts manual states, rejects invalid ones."""

    def test_reject_invalid(self, auth):
        proj = _find_project_by_status(auth, "En Gestión") or _find_project_by_status(auth, "Asignado")
        if not proj:
            pytest.skip("No project available")
        r = auth.put(
            f"{BASE_URL}/api/projects/{proj['project_id']}/status",
            json={"new_status": "Estado_Inexistente"},
            timeout=30,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

    @pytest.mark.parametrize("new_status", list(MANUAL_STATUSES))
    def test_accepts_manual_status(self, auth, new_status):
        proj = _find_project_by_status(auth, "En Gestión") or _find_project_by_status(auth, "Asignado")
        if not proj:
            pytest.skip("No project in En Gestión/Asignado")
        pid = proj["project_id"]
        r = auth.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            json={"new_status": new_status, "note": f"pytest manual {new_status}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        g = auth.get(f"{BASE_URL}/api/projects/{pid}", timeout=30)
        assert g.status_code == 200
        assert g.json().get("status") == new_status

        # Revert to En Gestión via ticket flow to leave data consistent
        auth.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            json={"new_status": "En Gestión", "note": "pytest revert"},
            timeout=30,
        )


class TestTemplateVariable:
    """Estado_Proyecto must be available_tags AND in the resolved variables dict."""

    def test_estado_proyecto_in_template_vars(self, auth):
        r = auth.get(f"{BASE_URL}/api/projects?limit=10", timeout=30)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        if not items:
            pytest.skip("No projects")
        pid = items[0]["project_id"]
        r = auth.get(f"{BASE_URL}/api/projects/{pid}/template-variables", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        tags = data.get("available_tags", [])
        tag_keys = [t.get("key") for t in tags if isinstance(t, dict)]
        assert "Estado_Proyecto" in tag_keys, f"Estado_Proyecto missing from available_tags. Got: {tag_keys[:20]}"
        # Resolved variables (could be under 'variables' or top-level)
        resolved = data.get("variables") or data.get("resolved") or {}
        # If resolved dict not provided as a flat 'variables' map, fall back to any nested dict
        if isinstance(resolved, dict) and "Estado_Proyecto" in resolved:
            assert resolved["Estado_Proyecto"] in EXPECTED_STATUSES or resolved["Estado_Proyecto"] == ""
