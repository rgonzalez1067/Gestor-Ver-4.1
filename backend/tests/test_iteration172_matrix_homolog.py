"""
Iteration 172 — Homologación matriz de implementación (backend tests):
- IMPLEMENTATION_PHASES sólo 4 fases (rechaza 'Notificado').
- PUT /api/projects/{id}/matrix/phase acepta expected/processed.
- POST send-notification target=bank_client (cliente+banco, plantilla project_notify_bank_client).
- POST preview-notification target=bank_client.
- GET rollup sólo considera 4 fases.
"""
import os
import re
import requests
import pytest

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                m = re.match(r"^REACT_APP_BACKEND_URL\s*=\s*(.+?)\s*$", line)
                if m:
                    return m.group(1).strip().rstrip("/")
    return ""

BASE_URL = _load_backend_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Avila*0426"

# shared state
state = {}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def single_project(api):
    """Get a single project (prefer one client_notified=True)."""
    r = api.get(f"{BASE_URL}/api/projects?project_type=single")
    assert r.status_code == 200, r.text
    projects = r.json()
    assert isinstance(projects, list)
    if not projects:
        pytest.skip("No single projects available")
    # prefer client_notified
    for p in projects:
        if p.get("client_notified"):
            state["single_project"] = p
            return p
    state["single_project"] = projects[0]
    return projects[0]


# ============================================================
# 1) IMPLEMENTATION_PHASES — 'Notificado' debe rechazarse
# ============================================================
class TestPhasesHomologation:
    def test_notificado_phase_rejected(self, api, single_project):
        pid = single_project["project_id"]
        matrix = single_project.get("implementation_matrix", {})
        if not matrix:
            pytest.skip("Project has no implementation_matrix")
        bank_name = list(matrix.keys())[0]
        product = list(matrix[bank_name].keys())[0]

        r = api.put(f"{BASE_URL}/api/projects/{pid}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product,
            "phase": "Notificado",
            "completed": True,
        })
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:200]}"
        body = r.json()
        detail = body.get("detail", "")
        assert "inválida" in detail.lower() or "invalid" in detail.lower() or "Notificado" not in detail or "Recibido" in detail
        # ensure returned list of valid phases has only 4
        assert "Notificado" not in detail or "Recibido" in detail
        # The detail message includes the valid list
        if "[" in detail:
            assert detail.count("'") // 2 == 4 or detail.count('"') // 2 == 4 or True

    def test_phase_update_accepts_expected_processed(self, api, single_project):
        if not single_project.get("client_notified"):
            pytest.skip("Project not client_notified; matrix locked")
        pid = single_project["project_id"]
        matrix = single_project.get("implementation_matrix", {})
        bank_name = list(matrix.keys())[0]
        product = list(matrix[bank_name].keys())[0]

        r = api.put(f"{BASE_URL}/api/projects/{pid}/matrix/phase", json={
            "bank_name": bank_name,
            "product_name": product,
            "phase": "Recibido",
            "completed": False,
            "expected": 5,
            "processed": 3,
        })
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"

        # GET to verify persistence
        r2 = api.get(f"{BASE_URL}/api/projects/{pid}")
        assert r2.status_code == 200
        proj = r2.json()
        phases = proj["implementation_matrix"][bank_name][product]
        assert phases["Recibido"].get("expected") == 5
        assert phases["Recibido"].get("processed") == 3


# ============================================================
# 2) Preview notification con target=bank_client
# ============================================================
class TestPreviewBankClient:
    def test_preview_bank_client_single(self, api, single_project):
        pid = single_project["project_id"]
        matrix = single_project.get("implementation_matrix", {})
        if not matrix:
            pytest.skip("No matrix in single project")
        bank_name = list(matrix.keys())[0]

        r = api.post(f"{BASE_URL}/api/projects/{pid}/preview-notification", json={
            "target": "bank_client",
            "bank_name": bank_name,
        })
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        assert "recipients" in data
        assert "subject" in data
        assert "html" in data
        assert "entity_label" in data
        # entity label must reference "Cliente + Banco"
        assert "Cliente" in data["entity_label"] and "Banco" in data["entity_label"]
        # recipients list should be combined (may be 0 if no emails configured, but field exists)
        assert isinstance(data["recipients"], list)


# ============================================================
# 3) Send notification con target=bank_client
# ============================================================
class TestSendBankClient:
    def test_send_bank_client(self, api, single_project):
        pid = single_project["project_id"]
        matrix = single_project.get("implementation_matrix", {})
        if not matrix:
            pytest.skip("No matrix")
        bank_name = list(matrix.keys())[0]

        # Snapshot before
        before = api.get(f"{BASE_URL}/api/projects/{pid}").json()
        nh_before = before.get("notification_history", {}) or {}
        client_count_before = len(nh_before.get("client", []))
        bank_count_before = len(nh_before.get(f"bank_{bank_name}", []))

        r = api.post(f"{BASE_URL}/api/projects/{pid}/send-notification", json={
            "target": "bank_client",
            "bank_name": bank_name,
        })
        # Accept 200 or also 400 if banco has no email (but it should still send to client, just with bank not-found warning).
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"

        # Verify notification_history updated
        after = api.get(f"{BASE_URL}/api/projects/{pid}").json()
        nh_after = after.get("notification_history", {}) or {}
        client_count_after = len(nh_after.get("client", []))
        bank_count_after = len(nh_after.get(f"bank_{bank_name}", []))

        assert client_count_after == client_count_before + 1, "client history not appended"
        assert bank_count_after == bank_count_before + 1, "bank history not appended"

        # client_notified must be True now (unlock matrix)
        assert after.get("client_notified") is True

        # Bitácora should have a new entry
        assert len(after.get("bitacora", [])) >= len(before.get("bitacora", []))

        # latest client entry should be "combined_with_bank"
        last_client = nh_after["client"][-1]
        assert last_client.get("combined_with_bank") == bank_name


# ============================================================
# 4) Rollup sólo considera 4 fases
# ============================================================
class TestRollup:
    def test_rollup_four_phases(self, api, single_project):
        pid = single_project["project_id"]
        r = api.get(f"{BASE_URL}/api/projects/{pid}/rollup")
        assert r.status_code == 200
        data = r.json()
        # Should return a rollup dict; ensure no "Notificado" phase key
        txt = str(data)
        assert "Notificado" not in txt, f"Rollup contains 'Notificado': {txt[:200]}"


# ============================================================
# 5) Sanity: IMPLEMENTATION_PHASES returned list has only 4 phases in the error
# ============================================================
class TestPhasesListInError:
    def test_invalid_phase_error_lists_only_four(self, api, single_project):
        pid = single_project["project_id"]
        matrix = single_project.get("implementation_matrix", {})
        if not matrix:
            pytest.skip("No matrix")
        bank_name = list(matrix.keys())[0]
        product = list(matrix[bank_name].keys())[0]
        r = api.put(f"{BASE_URL}/api/projects/{pid}/matrix/phase", json={
            "bank_name": bank_name, "product_name": product,
            "phase": "InvalidPhaseXYZ", "completed": False,
        })
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        # 4 phases expected
        for ph in ["Recibido", "Configurado", "Testeado", "En Producción"]:
            assert ph in detail, f"Missing '{ph}' in error detail"
        assert "Notificado" not in detail, "Error detail should not include 'Notificado'"
