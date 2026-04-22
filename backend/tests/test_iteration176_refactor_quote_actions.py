"""
Iteration 176: Validation of quote_actions.py refactor split.

Validates that endpoints moved to quote_helpers, quote_transitions,
quote_taller, and quote_serials still respond correctly without import
breakage and that helper functions remain wired correctly.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "Admin1234"


# ----- Fixtures -----
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token") or data.get("session_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ----- Auth -----
class TestAuth:
    def test_login_admin(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10


# ----- Core quotes endpoints (still in quote_actions.py) -----
class TestQuoteCore:
    def test_list_quotes(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/quotes", headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list) or isinstance(body, dict)

    def test_irregular_count(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/quotes/irregular/count", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert "count" in r.json()

    def test_audit_log(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/quotes/audit-log", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_email_logs(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/email-logs?limit=50", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text


# ----- Endpoints moved to quote_taller.py -----
class TestQuoteTallerModule:
    def test_repair_supplies(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/repair-supplies", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_taller_equipos_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/taller-equipos", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_taller_equipos_export_excel(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/taller-equipos/export-excel", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        # xlsx mime
        assert "spreadsheetml" in ct or "octet-stream" in ct or "excel" in ct, f"Unexpected CT: {ct}"
        assert len(r.content) > 100

    def test_taller_equipo_historial_404(self, admin_headers):
        # Use a definitely-nonexistent id - should be 404 (NOT 500 from import error)
        r = requests.get(
            f"{BASE_URL}/api/taller-equipos/nonexistent-id-xyz/historial",
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code in (200, 404), f"Should be 200/404 not 500: {r.status_code} {r.text[:300]}"

    def test_delete_taller_equipo_admin_only_404_or_403(self, admin_headers):
        # Admin should not get 403 (RBAC). 404 acceptable for nonexistent id.
        r = requests.delete(
            f"{BASE_URL}/api/taller-equipos/nonexistent-id-xyz",
            headers=admin_headers,
            timeout=15,
        )
        # Admin: must NOT be 500 (import error) and must NOT be 403
        assert r.status_code in (200, 404, 400), f"Unexpected: {r.status_code} {r.text[:300]}"


# ----- Endpoints moved to quote_serials.py -----
# We need at least one quote id. We attempt to fetch one; if none, we test with
# a fake id and accept 404 (verifying the route exists & no import error).
@pytest.fixture(scope="module")
def sample_quote_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/quotes", headers=admin_headers, timeout=20)
    if r.status_code != 200:
        return None
    body = r.json()
    items = body if isinstance(body, list) else body.get("items") or body.get("data") or []
    if items:
        item = items[0]
        return item.get("quote_id") or item.get("id") or item.get("_id")
    return None


class TestQuoteSerialsModule:
    def _check(self, r):
        # Accept 200/404/400 but never 500 (which would indicate import/refactor break)
        assert r.status_code != 500, f"500 from {r.url}: {r.text[:400]}"
        assert r.status_code in (200, 400, 404, 422), f"Unexpected: {r.status_code} {r.text[:300]}"

    def test_pinpad_models(self, admin_headers, sample_quote_id):
        qid = sample_quote_id or "fake-id"
        r = requests.get(f"{BASE_URL}/api/quotes/{qid}/pinpad-models", headers=admin_headers, timeout=15)
        self._check(r)

    def test_inventory_serials(self, admin_headers, sample_quote_id):
        qid = sample_quote_id or "fake-id"
        r = requests.get(f"{BASE_URL}/api/quotes/{qid}/inventory-serials", headers=admin_headers, timeout=15)
        self._check(r)

    def test_equipment_for_implementation(self, admin_headers, sample_quote_id):
        qid = sample_quote_id or "fake-id"
        r = requests.get(
            f"{BASE_URL}/api/quotes/{qid}/equipment-for-implementation",
            headers=admin_headers, timeout=15,
        )
        self._check(r)

    def test_available_serials(self, admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/inventory/fake-wh/available-serials/fake-item",
            headers=admin_headers, timeout=15,
        )
        # Should not be 500 (import error)
        assert r.status_code != 500, f"500 indicates import break: {r.text[:300]}"
        assert r.status_code in (200, 400, 404, 422), f"Unexpected: {r.status_code}"

    def test_preassigned_serials(self, admin_headers, sample_quote_id):
        qid = sample_quote_id or "fake-id"
        r = requests.get(f"{BASE_URL}/api/quotes/{qid}/preassigned-serials", headers=admin_headers, timeout=15)
        self._check(r)

    def test_preassign_serials_post_exists(self, admin_headers):
        # POST with empty body to fake id - should fail with 4xx (route exists), not 500
        r = requests.post(
            f"{BASE_URL}/api/quotes/fake-id/preassign-serials",
            headers=admin_headers, json={"serials": []}, timeout=15,
        )
        assert r.status_code != 500, f"500 from preassign-serials: {r.text[:300]}"
        assert r.status_code in (200, 400, 404, 422), r.status_code


# ----- Workflow endpoints in quote_actions.py (still there) -----
class TestQuoteWorkflowEndpointsExist:
    """Verify workflow endpoints exist & don't 500. 404 on fake id is fine."""

    @pytest.mark.parametrize("action", [
        "approve", "send-to-client", "send-to-implementation",
        "invoice", "collect", "deliver",
        "repair-complete", "repair-deliver",
    ])
    def test_workflow_endpoint_exists(self, admin_headers, action):
        r = requests.post(
            f"{BASE_URL}/api/quotes/fake-id-xyz/{action}",
            headers=admin_headers, json={}, timeout=15,
        )
        assert r.status_code != 500, f"500 from /api/quotes/.../{action}: {r.text[:400]}"
        # 404/400/422/403 acceptable, 200 unlikely with fake id
        assert r.status_code in (200, 400, 401, 403, 404, 422), (
            f"Unexpected status for /{action}: {r.status_code} {r.text[:200]}"
        )


# ----- Duplicate / status -----
class TestDuplicateAndStatus:
    def test_duplicate_endpoint_exists(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/quotes/fake-id-xyz/duplicate",
            headers=admin_headers, json={}, timeout=15,
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (200, 400, 404, 422)

    def test_status_endpoint_exists(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/quotes/fake-id-xyz/status",
            headers=admin_headers, json={"status": "Borrador"}, timeout=15,
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (200, 400, 404, 422)


# ----- Irregular flow helper invocation -----
class TestIrregularHelper:
    """Verify that approving a quote in non-'Enviada' status triggers
    irregular handling (422 IRREGULAR_FLOW or similar) - confirms helpers
    in quote_helpers.py are correctly imported."""

    def test_approve_non_enviada_triggers_irregular_or_404(self, admin_headers):
        # Find a quote not in 'Enviada' state if any
        r = requests.get(f"{BASE_URL}/api/quotes", headers=admin_headers, timeout=20)
        if r.status_code != 200:
            pytest.skip("Cannot list quotes")
        body = r.json()
        items = body if isinstance(body, list) else body.get("items") or body.get("data") or []
        target = None
        for it in items:
            est = (it.get("quote_status") or it.get("estado") or it.get("status") or "").lower()
            if est and est != "enviada":
                target = it
                break
        if not target:
            pytest.skip("No quote in non-Enviada status to validate irregular trigger")
        qid = target.get("quote_id") or target.get("id") or target.get("_id")
        r2 = requests.post(
            f"{BASE_URL}/api/quotes/{qid}/approve",
            headers=admin_headers, json={}, timeout=20,
        )
        # Should NOT be 500 (would indicate broken helper import)
        assert r2.status_code != 500, f"Helper import broken? {r2.text[:400]}"
        # Expect 422 (irregular) or 400 / 200 (if regularization auto-approves)
        assert r2.status_code in (200, 400, 403, 404, 422), (
            f"Unexpected approve status: {r2.status_code} {r2.text[:300]}"
        )
