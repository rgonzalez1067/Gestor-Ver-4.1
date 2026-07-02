"""Iteration 228 backend tests — Integrators lifecycle + Test Environment.

Covers:
  - P0 BUG: PUT /api/integrators/{id} must NOT close a project by editing an
    ordinary field; scope/status must be preserved. A PUT with
    integrator_status='Cerrado' returns 422 (Literal mismatch). A PUT on a
    Cerrado record does not reactivate it.
  - POST /api/integrators/{id}/close → sets Cerrado + project_scope=None and
    returns a 'notification' key (dispatch of 'integration_project_closed').
  - Matrix read-only guard: PUT certifications on a Cerrado/scope-None
    integrator returns 403. Same PUT on an Active Project succeeds (200).
  - POST /api/integrators/{id}/assign-test-environment: sets
    project_scope='test_environment' + dates + status 'En proceso'; GET returns
    test_env_days_left as int; end<start → 400; nonexistent id → 404.
  - GET /api/other-actions/catalog exposes 'integration_project_closed' and
    'test_environment_expired' entries (with label + variables) and both are
    configurable via POST /api/other-actions/config.

Cleanup:
  - All created integrators are prefixed 'QATEST_' and deleted at end via a
    direct Mongo query. The real integrator 'Saint de Venezuela' is untouched.
"""

import os
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

CREATED_IDS: list[str] = []


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No session_token in login response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _make_integrator(h, scope: str | None = "new", status: str = "En proceso", suffix: str | None = None):
    suffix = suffix or uuid.uuid4().hex[:6]
    payload = {
        "name": f"QATEST_INT_{suffix}",
        "integrator_type": "Integrador",
        "app_name": f"QATEST_APP_{suffix}",
        "integration_modality": "REST",
        "integrator_status": status,
        "project_scope": scope,
        "certifications": {},
    }
    r = requests.post(f"{API}/integrators", json=payload, headers=h, timeout=30)
    assert r.status_code in (200, 201), f"create failed: {r.status_code} {r.text}"
    data = r.json()
    iid = data.get("integrator_id") or data.get("id")
    assert iid, f"no integrator_id in response {data}"
    CREATED_IDS.append(iid)
    return data


# ---------------- P0 BUG FIX ----------------

class TestLifecycleGuard:
    def test_edit_field_does_not_close_project(self, h):
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        # PUT changing only a plain field (phone). Full ficha payload — the API
        # accepts IntegratorCreate so we resend all required fields.
        body = {
            "name": intg["name"],
            "integrator_type": intg["integrator_type"],
            "app_name": intg["app_name"],
            "integration_modality": intg.get("integration_modality"),
            "integrator_status": "En proceso",
            "principal_contact_phone": "0412-1234567",
            "certifications": intg.get("certifications") or {},
        }
        r = requests.put(f"{API}/integrators/{iid}", json=body, headers=h, timeout=30)
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text}"
        upd = r.json()
        assert upd.get("project_scope") == "new", f"scope was altered: {upd.get('project_scope')}"
        assert upd.get("integrator_status") == "En proceso"
        assert upd.get("principal_contact_phone") == "0412-1234567"

    def test_put_cerrado_status_rejected_422(self, h):
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        body = {
            "name": intg["name"],
            "integrator_type": intg["integrator_type"],
            "app_name": intg["app_name"],
            "integrator_status": "Cerrado",  # not in Literal
        }
        r = requests.put(f"{API}/integrators/{iid}", json=body, headers=h, timeout=30)
        assert r.status_code == 422, f"Expected 422 literal_error, got {r.status_code} {r.text}"
        # Sanity: pydantic literal_error mention
        txt = r.text.lower()
        assert "literal" in txt or "input should be" in txt

    def test_edit_on_cerrado_stays_cerrado(self, h):
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        # Close it via the official endpoint
        rc = requests.post(f"{API}/integrators/{iid}/close", headers=h, timeout=30)
        assert rc.status_code == 200, rc.text
        # Now edit a plain field (with a valid status) — must NOT reactivate
        body = {
            "name": intg["name"],
            "integrator_type": intg["integrator_type"],
            "app_name": intg["app_name"],
            "integrator_status": "En proceso",  # attempted reactivation via edit
            "principal_contact_name": "QATEST Contacto",
        }
        r = requests.put(f"{API}/integrators/{iid}", json=body, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        upd = r.json()
        assert upd.get("integrator_status") == "Cerrado", f"was reactivated: {upd.get('integrator_status')}"
        # scope must remain None after close
        assert upd.get("project_scope") in (None, ""), f"scope reappeared: {upd.get('project_scope')}"


# ---------------- Close flow ----------------

class TestCloseFlow:
    def test_close_sets_cerrado_and_returns_notification_key(self, h):
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        r = requests.post(f"{API}/integrators/{iid}/close", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "ok"
        assert "notification" in data, f"missing 'notification' key: {data}"
        upd = data.get("integrator") or {}
        assert upd.get("integrator_status") == "Cerrado"
        assert upd.get("project_scope") in (None, "")


# ---------------- Matrix read-only guard ----------------

class TestMatrixReadOnly:
    def test_cert_change_blocked_when_not_active(self, h):
        # Create Active, then close → scope=None + Cerrado.
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        requests.post(f"{API}/integrators/{iid}/close", headers=h, timeout=30)
        # Try to change certifications
        body = {
            "name": intg["name"],
            "integrator_type": intg["integrator_type"],
            "app_name": intg["app_name"],
            "integrator_status": "En proceso",  # will be preserved as Cerrado
            "certifications": {"c2p": "C"},  # different from stored {}
        }
        r = requests.put(f"{API}/integrators/{iid}", json=body, headers=h, timeout=30)
        assert r.status_code == 403, f"Expected 403 read-only, got {r.status_code} {r.text}"

    def test_cert_change_allowed_when_active_project(self, h):
        intg = _make_integrator(h, scope="new", status="En proceso")
        iid = intg["integrator_id"]
        body = {
            "name": intg["name"],
            "integrator_type": intg["integrator_type"],
            "app_name": intg["app_name"],
            "integrator_status": "En proceso",
            "certifications": {"c2p": "C"},
        }
        r = requests.put(f"{API}/integrators/{iid}", json=body, headers=h, timeout=30)
        assert r.status_code == 200, f"Expected 200 for active project, got {r.status_code} {r.text}"
        assert (r.json().get("certifications") or {}).get("c2p") == "C"


# ---------------- Assign Test Environment ----------------

class TestAssignTestEnvironment:
    def test_assign_success_and_days_left(self, h):
        intg = _make_integrator(h, scope=None, status="En proceso")
        iid = intg["integrator_id"]
        today = date.today()
        end = today + timedelta(days=10)  # ~ business days depends on calendar
        r = requests.post(
            f"{API}/integrators/{iid}/assign-test-environment",
            json={"start_date": today.isoformat(), "end_date": end.isoformat()},
            headers=h, timeout=30,
        )
        assert r.status_code == 200, r.text
        upd = r.json().get("integrator") or {}
        assert upd.get("project_scope") == "test_environment"
        assert upd.get("integrator_status") == "En proceso"
        assert upd.get("test_env_start_date") == today.isoformat()
        assert upd.get("test_env_end_date") == end.isoformat()

        # GET list and find our record; must have integer test_env_days_left
        rg = requests.get(f"{API}/integrators", headers=h, timeout=30)
        assert rg.status_code == 200
        items = rg.json()
        rec = next((x for x in items if x.get("integrator_id") == iid), None)
        assert rec is not None, "created test-env integrator not returned by GET /integrators"
        dl = rec.get("test_env_days_left")
        assert isinstance(dl, int), f"test_env_days_left not int: {dl!r}"
        assert 0 <= dl <= 15, f"unexpected days_left value {dl}"

    def test_end_before_start_returns_400(self, h):
        intg = _make_integrator(h, scope=None, status="En proceso")
        iid = intg["integrator_id"]
        today = date.today()
        r = requests.post(
            f"{API}/integrators/{iid}/assign-test-environment",
            json={"start_date": today.isoformat(), "end_date": (today - timedelta(days=3)).isoformat()},
            headers=h, timeout=30,
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code} {r.text}"

    def test_nonexistent_integrator_returns_404(self, h):
        r = requests.post(
            f"{API}/integrators/int_doesnotexist_zzz/assign-test-environment",
            json={"start_date": "2026-01-01", "end_date": "2026-01-10"},
            headers=h, timeout=30,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code} {r.text}"


# ---------------- Otras Acciones catalog ----------------

class TestOtherActionsCatalog:
    def test_catalog_contains_new_actions(self, h):
        r = requests.get(f"{API}/other-actions/catalog", headers=h, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        actions = data.get("actions") or data.get("catalog") or data
        # Try common shapes
        if isinstance(actions, dict):
            actions = actions.get("actions") or list(actions.values())
        ids = {a.get("id") for a in actions if isinstance(a, dict)}
        assert "integration_project_closed" in ids, f"missing integration_project_closed. IDs: {ids}"
        assert "test_environment_expired" in ids, f"missing test_environment_expired. IDs: {ids}"
        for a in actions:
            if a.get("id") == "integration_project_closed":
                assert a.get("label")
                assert isinstance(a.get("variables"), list) and a["variables"]
            if a.get("id") == "test_environment_expired":
                assert a.get("label")
                assert isinstance(a.get("variables"), list) and a["variables"]

    def test_actions_configurable_via_post_config(self, h):
        # Configure both actions (enabled with empty recipients) — must accept 200
        for aid in ("integration_project_closed", "test_environment_expired"):
            payload = {"action_id": aid, "enabled": True, "recipients": []}
            r = requests.put(f"{API}/other-actions/configs", json=payload, headers=h, timeout=30)
            assert r.status_code in (200, 201), f"config {aid} failed: {r.status_code} {r.text}"


# ---------------- Cleanup ----------------

def test_zzz_cleanup_qatest_records(h):
    """Delete all QATEST_ integrators (both by tracked IDs and by name prefix).
    Then assert 0 QATEST_ remain in GET /integrators."""
    # Delete by tracked ids first
    for iid in list(CREATED_IDS):
        try:
            requests.delete(f"{API}/integrators/{iid}", headers=h, timeout=30)
        except Exception:
            pass
    # Then fetch all and delete anything QATEST_
    r = requests.get(f"{API}/integrators?include_closed=1", headers=h, timeout=30)
    if r.status_code != 200:
        r = requests.get(f"{API}/integrators", headers=h, timeout=30)
    if r.status_code == 200:
        for x in r.json():
            if (x.get("name") or "").startswith("QATEST_"):
                requests.delete(f"{API}/integrators/{x['integrator_id']}", headers=h, timeout=30)
    # Verify 0 remain
    r2 = requests.get(f"{API}/integrators?include_closed=1", headers=h, timeout=30)
    if r2.status_code != 200:
        r2 = requests.get(f"{API}/integrators", headers=h, timeout=30)
    remaining = [x for x in r2.json() if (x.get("name") or "").startswith("QATEST_")]
    assert not remaining, f"QATEST_ records still present after cleanup: {[x['name'] for x in remaining]}"
    # Safety: ensure Saint de Venezuela still exists
    saint = [x for x in r2.json() if x.get("name") == "Saint de Venezuela"]
    assert saint, "Saint de Venezuela was accidentally removed — CRITICAL"
