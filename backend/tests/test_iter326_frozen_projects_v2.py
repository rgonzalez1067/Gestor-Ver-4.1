"""
Iteration 326 - V2 Congelado (Frozen Projects) backend tests.

Covers:
- Freeze rules (only from 'En Gestión', note required)
- Freeze snapshots sla_days_at_freeze
- SLA evaluate does NOT change sla_days while frozen
- Unfreeze -> back to 'En Gestión' with resumed sla_days
- /projects/stats includes 'frozen'
- /project-sla/config exposes and persists frozen_notify_frequency_days (default 7, rejects <1)
- /other-actions/catalog includes project_status_congelado
- POST /project-sla/run-frozen-alerts returns 200
"""
import os
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    return "http://localhost:8001"

BASE_URL = _load_backend_url()

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def en_gestion_project(headers):
    """Pick an 'En Gestión' project that is NOT the pre-existing frozen one."""
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("projects") or []
    candidates = [p for p in items if p.get("status") == "En Gestión" and p.get("project_id") != "prj_644200469bf5"]
    assert candidates, "No 'En Gestión' project available for freeze test"
    # Prefer one with sla_days > 0 to make the resume assertion meaningful
    candidates.sort(key=lambda p: -(p.get("sla_days") or 0))
    return candidates[0]


# ---------- Config (frozen_notify_frequency_days) ----------
class TestSlaConfigFrozenFrequency:
    def test_get_config_has_frozen_frequency(self, headers):
        r = requests.get(f"{BASE_URL}/api/project-sla/config", headers=headers, timeout=15)
        assert r.status_code == 200
        cfg = r.json().get("config") or {}
        assert "frozen_notify_frequency_days" in cfg, f"missing key in {cfg}"
        assert int(cfg["frozen_notify_frequency_days"]) >= 1

    def test_put_config_persists_frequency(self, headers):
        # Read current stages to keep them intact
        cur = requests.get(f"{BASE_URL}/api/project-sla/config", headers=headers, timeout=15).json()
        stages = cur["config"]["stages"]
        prev_freq = int(cur["config"].get("frozen_notify_frequency_days") or 7)

        payload = {"stages": stages, "frozen_notify_frequency_days": 9}
        r = requests.put(f"{BASE_URL}/api/project-sla/config", headers=headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text

        # Verify persisted
        cur2 = requests.get(f"{BASE_URL}/api/project-sla/config", headers=headers, timeout=15).json()
        assert int(cur2["config"]["frozen_notify_frequency_days"]) == 9

        # Restore
        payload["frozen_notify_frequency_days"] = prev_freq
        requests.put(f"{BASE_URL}/api/project-sla/config", headers=headers, json=payload, timeout=15)

    def test_put_config_rejects_less_than_1(self, headers):
        cur = requests.get(f"{BASE_URL}/api/project-sla/config", headers=headers, timeout=15).json()
        stages = cur["config"]["stages"]
        payload = {"stages": stages, "frozen_notify_frequency_days": 0}
        r = requests.put(f"{BASE_URL}/api/project-sla/config", headers=headers, json=payload, timeout=15)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


# ---------- Other actions catalog ----------
class TestOtherActionsCongelado:
    def test_catalog_contains_project_status_congelado(self, headers):
        r = requests.get(f"{BASE_URL}/api/other-actions/catalog", headers=headers, timeout=15)
        assert r.status_code == 200
        actions = r.json().get("actions") or []
        ids = [a.get("id") for a in actions]
        assert "project_status_congelado" in ids, f"missing project_status_congelado in {ids}"


# ---------- Stats includes frozen ----------
class TestProjectsStats:
    def test_stats_includes_frozen(self, headers):
        r = requests.get(f"{BASE_URL}/api/projects/stats", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "frozen" in data
        assert isinstance(data["frozen"], int)
        assert data["frozen"] >= 1  # prj_644200469bf5 is Congelado in env


# ---------- Run frozen alerts on-demand ----------
class TestRunFrozenAlerts:
    def test_run_frozen_alerts_ok(self, headers):
        r = requests.post(f"{BASE_URL}/api/project-sla/run-frozen-alerts", headers=headers, timeout=30)
        assert r.status_code == 200, r.text


# ---------- Freeze / Unfreeze full cycle ----------
class TestFreezeUnfreezeCycle:
    def test_freeze_requires_note(self, headers, en_gestion_project):
        pid = en_gestion_project["project_id"]
        r = requests.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            headers=headers,
            data={"new_status": "Congelado", "note": "   "},
            timeout=30,
        )
        assert r.status_code == 400
        assert "justificación" in r.text.lower() or "justificacion" in r.text.lower()

    def test_full_cycle_freeze_evaluate_unfreeze(self, headers, en_gestion_project):
        pid = en_gestion_project["project_id"]
        sla_before = int(en_gestion_project.get("sla_days") or 0)

        # FREEZE
        r = requests.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            headers=headers,
            data={"new_status": "Congelado", "note": "TEST_iter326 QA freeze"},
            timeout=30,
        )
        assert r.status_code == 200, r.text

        # Verify state
        g = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=headers, timeout=15)
        assert g.status_code == 200
        pj = g.json()
        assert pj["status"] == "Congelado"
        assert pj.get("is_frozen") is True
        assert pj.get("frozen_at")
        assert pj.get("freeze_reason") == "TEST_iter326 QA freeze"
        assert int(pj.get("sla_days_at_freeze") or -1) == sla_before

        sla_frozen = int(pj.get("sla_days") or 0)
        color_frozen = pj.get("sla_color")

        # Cannot re-freeze from Congelado
        r2 = requests.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            headers=headers,
            data={"new_status": "Congelado", "note": "again"},
            timeout=30,
        )
        assert r2.status_code == 400

        # Run SLA evaluate
        ev = requests.post(f"{BASE_URL}/api/project-sla/evaluate", headers=headers, timeout=60)
        assert ev.status_code == 200, ev.text

        # SLA should be unchanged for frozen project
        g2 = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=headers, timeout=15)
        pj2 = g2.json()
        assert pj2["status"] == "Congelado"
        assert int(pj2.get("sla_days") or 0) == sla_frozen, f"sla_days changed while frozen: {sla_frozen} -> {pj2.get('sla_days')}"
        assert pj2.get("sla_color") == color_frozen

        # UNFREEZE -> only 'En Gestión' allowed
        bad = requests.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            headers=headers,
            data={"new_status": "Culminado", "note": "x"},
            timeout=30,
        )
        assert bad.status_code == 400

        # Unfreeze to En Gestión
        u = requests.put(
            f"{BASE_URL}/api/projects/{pid}/status",
            headers=headers,
            data={"new_status": "En Gestión", "note": "TEST_iter326 unfreeze"},
            timeout=30,
        )
        assert u.status_code == 200, u.text

        # After unfreeze + evaluate, sla_days must resume near sla_days_at_freeze (not reset)
        requests.post(f"{BASE_URL}/api/project-sla/evaluate", headers=headers, timeout=60)
        g3 = requests.get(f"{BASE_URL}/api/projects/{pid}", headers=headers, timeout=15)
        pj3 = g3.json()
        assert pj3["status"] == "En Gestión"
        assert pj3.get("is_frozen") is False
        resumed = int(pj3.get("sla_days") or 0)
        # Allow tolerance of 0..1 business day depending on time of run
        assert resumed >= sla_before, f"expected resumed>={sla_before}, got {resumed}"
        assert resumed <= sla_before + 1

    def test_freeze_from_non_en_gestion_rejected(self, headers):
        # prj_644200469bf5 is Congelado in env => cannot freeze it again
        r = requests.put(
            f"{BASE_URL}/api/projects/prj_644200469bf5/status",
            headers=headers,
            data={"new_status": "Congelado", "note": "should fail"},
            timeout=30,
        )
        assert r.status_code == 400
