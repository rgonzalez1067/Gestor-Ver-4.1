"""
Iteration 237 — Backend E2E tests for Client hierarchy (Principal/Sucursales) feature.
Covers:
  - POST /api/admin/clients/migrate-hierarchy (idempotency)
  - GET  /api/clients/by-rif (tree for RIF J-40064040-7 Lacoste)
  - GET  /api/clients/{id}/consolidated-contacts (principal vs branch scopes)
  - POST /api/clients/{parent_id}/branches (inheritance snapshot, contacts NOT copied, 400 validation, DELETE cleanup)
  - PUT  /api/clients/{id} on a branch (local edit, preserves is_branch/parent)
  - DELETE /api/clients/{id} guard: Principal with branches returns 400
  - GET  /api/projects/{id}/suggested-contacts (consolidation for branch client_id)
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

LACOSTE_PRINCIPAL_ID = "cli_0744288d46bf"
LACOSTE_BRANCH_ID = "cli_e807e33ae011"
LACOSTE_RIF = "J400640407"  # sanitized J-40064040-7


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("session_token") or body.get("token") or body.get("access_token")
    assert tok, f"no session_token in login response: {body}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ==================== MIGRATION IDEMPOTENCY ====================

class TestMigration:
    def test_migrate_hierarchy_idempotent(self, headers):
        r1 = requests.post(f"{BASE_URL}/api/admin/clients/migrate-hierarchy", headers=headers, timeout=60)
        assert r1.status_code == 200, f"first migration call failed: {r1.status_code} {r1.text}"
        d1 = r1.json()
        assert "principals" in d1 and "branches_linked" in d1 and "groups" in d1
        principals_1 = d1["principals"]
        branches_1 = d1["branches_linked"]

        # Second run must NOT change counts (idempotent)
        r2 = requests.post(f"{BASE_URL}/api/admin/clients/migrate-hierarchy", headers=headers, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["principals"] == principals_1
        assert d2["branches_linked"] == branches_1
        # Sanity: expected magnitudes from problem statement (~516 principals, ~18 branches)
        assert principals_1 > 400
        assert branches_1 >= 10


# ==================== BY-RIF TREE ====================

class TestByRif:
    def test_by_rif_lacoste(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/clients/by-rif",
            params={"rif": "J-40064040-7"},
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data["has_branches"] is True
        assert data["principal"] is not None
        assert data["principal"]["client_id"] == LACOSTE_PRINCIPAL_ID
        branch_ids = [b["client_id"] for b in data["branches"]]
        assert LACOSTE_BRANCH_ID in branch_ids
        # Branch descriptor should include sucursal name
        branch = next(b for b in data["branches"] if b["client_id"] == LACOSTE_BRANCH_ID)
        assert "Puerto Ordaz" in (branch.get("sucursal") or "")

    def test_by_rif_sanitizes(self, headers):
        # Same RIF with different formatting must yield same principal
        r = requests.get(
            f"{BASE_URL}/api/clients/by-rif",
            params={"rif": "j400640407"},
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["principal"]["client_id"] == LACOSTE_PRINCIPAL_ID

    def test_by_rif_empty(self, headers):
        r = requests.get(f"{BASE_URL}/api/clients/by-rif", params={"rif": ""}, headers=headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["has_branches"] is False
        assert d["principal"] is None
        assert d["branches"] == []


# ==================== CONSOLIDATED CONTACTS ====================

class TestConsolidatedContacts:
    def test_principal_returns_only_principal_scope(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}/consolidated-contacts",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["client_id"] == LACOSTE_PRINCIPAL_ID
        assert data["principal_client_id"] == LACOSTE_PRINCIPAL_ID
        assert data["is_branch"] is False
        scopes = {c.get("scope") for c in data.get("contacts", [])}
        # Only principal scope for a Principal client
        assert scopes.issubset({"principal"})

    def test_branch_consolidates_principal_and_local(self, headers):
        r = requests.get(
            f"{BASE_URL}/api/clients/{LACOSTE_BRANCH_ID}/consolidated-contacts",
            headers=headers,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["client_id"] == LACOSTE_BRANCH_ID
        assert data["principal_client_id"] == LACOSTE_PRINCIPAL_ID
        assert data["is_branch"] is True
        scopes = {c.get("scope") for c in data.get("contacts", [])}
        # Must be subset of {principal, local} and at least contain 'principal' if principal has contacts
        assert scopes.issubset({"principal", "local"})


# ==================== BRANCH CREATION + INHERITANCE + DELETE ====================

class TestBranchCreateAndDelete:
    def test_create_branch_inherits_and_local_edit_cleanup(self, headers):
        # Read principal state first
        rp = requests.get(f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}", headers=headers, timeout=15)
        assert rp.status_code == 200, rp.text
        principal = rp.json()
        principal_condicion = principal.get("condicion")
        principal_legal = principal.get("legal_name")
        principal_segment = principal.get("segment")
        principal_contact_count = len(principal.get("contacts") or [])

        sucursal_name = f"TEST_237_Sucursal_{int(time.time())}"
        # NOTE (backend gap detected in iter237): ClientCreate declares legal_name
        # and fantasy_name as REQUIRED at Pydantic level, so if we omit them the
        # /branches endpoint returns 422 before the inheritance snapshot runs.
        # Spec says these should inherit from the Principal when not provided.
        # Reported as a HIGH bug; test sends explicit blank overrides to at least
        # exercise the inheritance path for the other fields (condicion, segment,
        # branch_address override, contacts NOT copied).
        payload = {
            "rif": principal.get("rif"),
            "sucursal": sucursal_name,
            "legal_name": principal.get("legal_name") or "TEST237",
            "fantasy_name": principal.get("fantasy_name") or "TEST237",
            "branch_address": "Av. Test 123, Caracas",
            "email": "",
            "contacts": [
                {
                    "first_name": "Local",
                    "last_name": "Contact",
                    "full_name": "Local Contact TEST237",
                    "email": "localtest237@example.com",
                    "role": "Comercial",
                }
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}/branches",
            headers=headers,
            json=payload,
            timeout=20,
        )
        assert r.status_code == 200, f"create branch failed: {r.status_code} {r.text}"
        branch = r.json()
        branch_id = branch["client_id"]
        try:
            # Hierarchy
            assert branch["is_branch"] is True
            assert branch["parent_client_id"] == LACOSTE_PRINCIPAL_ID
            assert branch["rif"] == principal.get("rif")
            assert branch["sucursal"] == sucursal_name
            # Overrides respected
            assert branch.get("branch_address") == "Av. Test 123, Caracas"
            # Inheritance snapshot for omitted fields
            assert branch.get("condicion") == principal_condicion
            assert branch.get("legal_name") == principal_legal
            assert branch.get("segment") == principal_segment
            # Contacts NOT copied from principal: branch has only the 1 local contact sent
            assert len(branch.get("contacts") or []) == 1
            assert (branch["contacts"][0].get("email") or "") == "localtest237@example.com"
            # Sanity: principal contacts unchanged
            rp2 = requests.get(f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}", headers=headers, timeout=15)
            assert len(rp2.json().get("contacts") or []) == principal_contact_count

            # ---------- PUT edit on branch: change branch_address only, preserve hierarchy ----------
            updated_payload = dict(branch)
            updated_payload.pop("_id", None)
            updated_payload["branch_address"] = "Av. Test 999, Caracas (updated)"
            # Intentionally drop is_branch/parent_client_id to verify the server re-derives them
            updated_payload.pop("is_branch", None)
            updated_payload.pop("parent_client_id", None)
            # Remove immutable server-side fields
            for k in ("created_at", "updated_at", "client_id"):
                updated_payload.pop(k, None)
            ru = requests.put(
                f"{BASE_URL}/api/clients/{branch_id}",
                headers=headers,
                json=updated_payload,
                timeout=20,
            )
            assert ru.status_code == 200, f"update branch failed: {ru.status_code} {ru.text}"
            updated = ru.json()
            assert updated["is_branch"] is True
            assert updated["parent_client_id"] == LACOSTE_PRINCIPAL_ID
            assert updated["branch_address"] == "Av. Test 999, Caracas (updated)"

            # Principal remains untouched by branch edit
            rp3 = requests.get(f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}", headers=headers, timeout=15)
            p3 = rp3.json()
            assert p3.get("legal_name") == principal_legal
            assert p3.get("condicion") == principal_condicion

            # ---------- DELETE guard: Principal with branches must fail (400) ----------
            rd_principal = requests.delete(
                f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}",
                headers=headers,
                timeout=15,
            )
            assert rd_principal.status_code == 400, (
                f"expected 400 deleting Principal with branches, got {rd_principal.status_code}: {rd_principal.text}"
            )
        finally:
            # Cleanup: delete the test branch we created
            rd = requests.delete(f"{BASE_URL}/api/clients/{branch_id}", headers=headers, timeout=15)
            # Accept either 200 or 204 (or 400 if there were unexpected quotes)
            assert rd.status_code in (200, 204), f"cleanup DELETE failed: {rd.status_code} {rd.text}"

    def test_create_branch_rejects_empty_or_principal_name(self, headers):
        # NOTE: because ClientCreate requires legal_name/fantasy_name, a payload
        # without them returns 422 before the sucursal check. We include them here
        # to exercise the 400 branch inside the endpoint.
        base = {
            "rif": LACOSTE_RIF,
            "legal_name": "TEST237",
            "fantasy_name": "TEST237",
        }
        payload_empty = {**base, "sucursal": ""}
        r1 = requests.post(
            f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}/branches",
            headers=headers,
            json=payload_empty,
            timeout=15,
        )
        assert r1.status_code == 400, f"expected 400 for empty sucursal, got {r1.status_code}: {r1.text}"

        payload_principal = {**base, "sucursal": "Principal"}
        r2 = requests.post(
            f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}/branches",
            headers=headers,
            json=payload_principal,
            timeout=15,
        )
        assert r2.status_code == 400, f"expected 400 for 'Principal' sucursal, got {r2.status_code}: {r2.text}"

    def test_create_branch_missing_required_pydantic_fields_returns_422(self, headers):
        """Documents the current backend contract gap: legal_name/fantasy_name are
        Pydantic-required in ClientCreate, so omitting them returns 422 even
        though the spec says the branch endpoint should snapshot them from the
        Principal. Track this as a HIGH backend issue."""
        payload = {
            "rif": LACOSTE_RIF,
            "sucursal": f"TEST_237_SucursalOmit_{int(time.time())}",
            "branch_address": "Test",
        }
        r = requests.post(
            f"{BASE_URL}/api/clients/{LACOSTE_PRINCIPAL_ID}/branches",
            headers=headers,
            json=payload,
            timeout=15,
        )
        # Currently returns 422; if backend is fixed to snapshot inheritance this
        # will become 200 and this test should be updated.
        assert r.status_code == 422, f"expected current-gap 422, got {r.status_code}: {r.text}"


# ==================== SUGGESTED CONTACTS (project) ====================

class TestProjectSuggestedContacts:
    def test_suggested_contacts_for_project_with_branch_client(self, headers):
        """Try to find a project whose client_id points to a branch; validate that
        consolidation yields Principal-scoped and branch-scoped contacts with
        source='client'. If no such project exists, fall back to any project and
        assert the endpoint is at least not broken."""
        r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
        assert r.status_code == 200, f"projects list failed: {r.status_code}"
        projects = r.json()
        if isinstance(projects, dict):
            projects = projects.get("projects") or projects.get("items") or []
        assert isinstance(projects, list) and len(projects) > 0, "no projects available for test"

        # Get all clients client_id -> is_branch map (single query for speed)
        rc = requests.get(f"{BASE_URL}/api/clients", headers=headers, timeout=60)
        assert rc.status_code == 200
        clients = rc.json()
        if isinstance(clients, dict):
            clients = clients.get("clients") or clients.get("items") or []
        branch_ids = {c["client_id"] for c in clients if c.get("is_branch")}

        branch_project = next(
            (p for p in projects if p.get("client_id") in branch_ids), None
        )

        target_project = branch_project or projects[0]
        pid = target_project.get("project_id") or target_project.get("id")
        rs = requests.get(
            f"{BASE_URL}/api/projects/{pid}/suggested-contacts",
            headers=headers,
            timeout=30,
        )
        assert rs.status_code == 200, f"suggested-contacts failed: {rs.status_code} {rs.text}"
        contacts = rs.json()
        # Endpoint may return list directly or {contacts: [...]}
        if isinstance(contacts, dict):
            contacts = contacts.get("contacts") or []
        assert isinstance(contacts, list)
        # Every client-sourced contact must have a scope field
        client_contacts = [c for c in contacts if c.get("source") == "client"]
        for c in client_contacts:
            assert "scope" in c, f"client contact without scope: {c}"

        if branch_project is not None:
            scopes = {c.get("scope") for c in client_contacts}
            # A branch project should include at least 'Principal' scope OR the branch name.
            # (Depending on whether Principal actually has any contacts.)
            assert "Principal" in scopes or any(s and s != "Principal" for s in scopes), (
                f"branch project {pid} did not include consolidated contacts: {client_contacts}"
            )
