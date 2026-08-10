"""Backend tests for iteration 295 - Economic Groups (Grupo Económico) V4.
Covers CRUD, validations, associated clients grid ordering, contact
inheritance to clients/projects, permissions catalog, and PDF export.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-overhaul.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="session")
def client_session(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def created_group(client_session):
    """Create a fresh group for tests; clean up at end."""
    import uuid
    name = f"TEST_QA_Iter295_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": name,
        "description": "Grupo QA iter295",
        "representantes": [
            {"nombre": "Juan Pérez", "cedula": "V-12345678", "cargo": "CEO", "telefono": "0212-1234567", "email": "juan@qa.com"}
        ],
        "contacts": [
            {
                "name": "Contacto QA",
                "email": "qa295@grupo.com",
                "role": "Integrador",
                "phone": "0212-9999999",
                "purposes": ["facturacion", "implementacion"],
            }
        ],
    }
    r = client_session.post(f"{API}/grupos-economicos", json=payload)
    assert r.status_code == 200, r.text
    g = r.json()
    yield g
    # cleanup
    client_session.delete(f"{API}/grupos-economicos/{g['group_id']}")


# ---------- CRUD ----------
class TestEconomicGroupsCRUD:
    def test_list(self, client_session):
        r = client_session.get(f"{API}/grupos-economicos")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            g = data[0]
            assert "group_id" in g and "name" in g
            assert "rif_count" in g
            assert "contacts_count" in g

    def test_create_and_get_detail(self, client_session, created_group):
        gid = created_group["group_id"]
        r = client_session.get(f"{API}/grupos-economicos/{gid}")
        assert r.status_code == 200
        g = r.json()
        assert g["name"] == created_group["name"]
        assert "clients" in g and isinstance(g["clients"], list)
        assert "rif_count" in g
        # representantes / contacts preserved
        assert len(g.get("representantes", [])) == 1
        assert len(g.get("contacts", [])) == 1
        c = g["contacts"][0]
        assert c["role"] == "Integrador"
        assert set(["facturacion", "implementacion"]).issubset(set(c.get("purposes") or []))
        # contact_id auto-assigned
        assert c.get("contact_id", "").startswith("cnt_")

    def test_duplicate_name_rejected(self, client_session, created_group):
        r = client_session.post(f"{API}/grupos-economicos", json={"name": created_group["name"].upper()})
        assert r.status_code == 400

    def test_empty_name_rejected(self, client_session):
        r = client_session.post(f"{API}/grupos-economicos", json={"name": "  "})
        assert r.status_code == 400

    def test_update_group(self, client_session, created_group):
        gid = created_group["group_id"]
        new_desc = "Descripción actualizada QA"
        payload = {
            "name": created_group["name"],
            "description": new_desc,
            "representantes": created_group.get("representantes", []),
            "contacts": created_group.get("contacts", []),
        }
        r = client_session.put(f"{API}/grupos-economicos/{gid}", json=payload)
        assert r.status_code == 200, r.text
        # verify persistence
        r2 = client_session.get(f"{API}/grupos-economicos/{gid}")
        assert r2.json()["description"] == new_desc

    def test_update_duplicate_name_rejected(self, client_session, created_group):
        # get another group's name (if exists)
        r = client_session.get(f"{API}/grupos-economicos")
        others = [g for g in r.json() if g["group_id"] != created_group["group_id"]]
        if not others:
            pytest.skip("No other group to test duplicate against")
        other_name = others[0]["name"]
        payload = {"name": other_name, "description": "x"}
        r = client_session.put(f"{API}/grupos-economicos/{created_group['group_id']}", json=payload)
        assert r.status_code == 400


# ---------- Associated clients (grid + link) ----------
class TestAssociatedClientsGrid:
    def test_link_client_and_grid_shape(self, client_session, created_group):
        gid = created_group["group_id"]
        # Find any client to link
        clients_list = client_session.get(f"{API}/clients").json()
        assert isinstance(clients_list, list) and clients_list
        # pick a principal client (no parent)
        target = None
        for c in clients_list:
            if not c.get("parent_client_id") and not c.get("is_branch"):
                target = c
                break
        assert target, "No principal client found"
        client_id = target["client_id"]
        original_group_id = target.get("grupo_economico_id")

        try:
            # PUT link
            put_payload = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": gid}
            r = client_session.put(f"{API}/clients/{client_id}", json=put_payload)
            assert r.status_code == 200, r.text
            # group nombre auto-sync in client doc
            refreshed = client_session.get(f"{API}/clients/{client_id}").json()
            assert refreshed["grupo_economico_id"] == gid
            assert refreshed["grupo_economico"] == created_group["name"]

            # grid via GET /grupos-economicos/{id}
            g = client_session.get(f"{API}/grupos-economicos/{gid}").json()
            assert g["rif_count"] >= 1
            rows = g["clients"]
            assert rows, "No associated rows returned"
            row = rows[0]
            # Field order in dict (Python 3.7+ preserves insert order) — verify keys exist
            keys = list(row.keys())
            # Required columns in strict order: fantasy_name, rif, legal_name
            required_order = ["fantasy_name", "rif", "legal_name"]
            positions = [keys.index(k) for k in required_order if k in keys]
            assert positions == sorted(positions), f"Column order broken: {keys}"

            # /clients endpoint
            r2 = client_session.get(f"{API}/grupos-economicos/{gid}/clients")
            assert r2.status_code == 200
            rows2 = r2.json()
            assert any(r["client_id"] == client_id for r in rows2)
        finally:
            # restore
            restore = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": original_group_id}
            client_session.put(f"{API}/clients/{client_id}", json=restore)


# ---------- Contact inheritance ----------
class TestContactInheritance:
    def test_consolidated_contacts_include_group(self, client_session, created_group):
        gid = created_group["group_id"]
        # link a client
        clients_list = client_session.get(f"{API}/clients").json()
        target = next((c for c in clients_list if not c.get("parent_client_id") and not c.get("is_branch")), None)
        assert target
        client_id = target["client_id"]
        original_group_id = target.get("grupo_economico_id")
        try:
            put_payload = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": gid}
            r = client_session.put(f"{API}/clients/{client_id}", json=put_payload)
            assert r.status_code == 200

            r = client_session.get(f"{API}/clients/{client_id}/consolidated-contacts")
            assert r.status_code == 200, r.text
            data = r.json()
            contacts = data.get("contacts", data) if isinstance(data, dict) else data
            # Expect grupo-scoped entry with our email
            grupo_items = [c for c in contacts if isinstance(c, dict) and (c.get("scope") == "grupo")]
            assert grupo_items, f"No grupo-scope contacts returned: {contacts}"
            emails = {c.get("email") for c in grupo_items}
            assert "qa295@grupo.com" in emails
            # verify group name attached
            it = next(c for c in grupo_items if c.get("email") == "qa295@grupo.com")
            assert it.get("grupo_economico_name") == created_group["name"]
        finally:
            restore = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": original_group_id}
            client_session.put(f"{API}/clients/{client_id}", json=restore)

    def test_project_suggested_contacts_include_group(self, client_session, created_group):
        gid = created_group["group_id"]
        clients_list = client_session.get(f"{API}/clients").json()
        target = next((c for c in clients_list if not c.get("parent_client_id") and not c.get("is_branch")), None)
        assert target
        client_id = target["client_id"]
        original_group_id = target.get("grupo_economico_id")

        # find a project belonging to this client
        proj_list = client_session.get(f"{API}/projects").json()
        proj = next((p for p in proj_list if p.get("client_id") == client_id), None)
        if not proj:
            pytest.skip("No project associated to any principal client")

        try:
            put_payload = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": gid}
            client_session.put(f"{API}/clients/{client_id}", json=put_payload)

            r = client_session.get(f"{API}/projects/{proj['project_id']}/suggested-contacts")
            assert r.status_code == 200, r.text
            contacts = r.json()
            grupo_items = [c for c in contacts if c.get("scope") == "grupo"]
            # inheritance may include client's group contact
            assert any(c.get("email") == "qa295@grupo.com" for c in grupo_items), (
                f"Group contact not inherited to project: {contacts}"
            )
        finally:
            restore = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": original_group_id}
            client_session.put(f"{API}/clients/{client_id}", json=restore)


# ---------- Permissions catalog ----------
class TestPermissionsCatalog:
    def test_module_registered(self, client_session):
        r = client_session.get(f"{API}/admin/permission-catalog")
        assert r.status_code == 200, r.text
        data = r.json()
        # Structure: dict of groups OR list of modules
        found = False
        gestion_pos = -1
        clients_pos = -1
        groups_pos = -1
        # Try both shapes
        if isinstance(data, dict):
            for group_key, modules in data.items():
                if isinstance(modules, list):
                    for i, m in enumerate(modules):
                        mid = m.get("id") if isinstance(m, dict) else m
                        if mid == "grupos_economicos":
                            found = True
                            groups_pos = i
                            if group_key.lower() == "gestion_comercial":
                                pass
                        if mid == "clients":
                            clients_pos = i
                    if found and clients_pos >= 0 and group_key.lower() == "gestion_comercial":
                        assert groups_pos < clients_pos, f"grupos_economicos should be before clients in gestion_comercial"
        elif isinstance(data, list):
            for i, m in enumerate(data):
                if m.get("id") == "grupos_economicos":
                    found = True
                    groups_pos = i
                if m.get("id") == "clients":
                    clients_pos = i
            if found and clients_pos > 0:
                assert groups_pos < clients_pos
        assert found, f"grupos_economicos module not present in permission-catalog: {data}"


# ---------- PDF export ----------
class TestPdfExport:
    def test_export_pdf(self, client_session, created_group):
        gid = created_group["group_id"]
        r = client_session.get(f"{API}/grupos-economicos/{gid}/export-pdf")
        assert r.status_code == 200, r.text
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF", f"Not a PDF file: {r.content[:20]}"


# ---------- Delete unlinks clients ----------
class TestDeleteUnlinks:
    def test_delete_group_unlinks_clients(self, client_session):
        import uuid
        # Create ephemeral group
        name = f"TEST_QA_delete_{uuid.uuid4().hex[:6]}"
        r = client_session.post(f"{API}/grupos-economicos", json={"name": name})
        assert r.status_code == 200
        gid = r.json()["group_id"]

        clients_list = client_session.get(f"{API}/clients").json()
        target = next((c for c in clients_list if not c.get("parent_client_id") and not c.get("is_branch")), None)
        assert target
        client_id = target["client_id"]
        original_group_id = target.get("grupo_economico_id")

        try:
            put_payload = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": gid}
            client_session.put(f"{API}/clients/{client_id}", json=put_payload)
            # Verify linked
            assert client_session.get(f"{API}/clients/{client_id}").json()["grupo_economico_id"] == gid

            # Delete group
            r = client_session.delete(f"{API}/grupos-economicos/{gid}")
            assert r.status_code == 200

            # Verify client still exists but unlinked
            c = client_session.get(f"{API}/clients/{client_id}")
            assert c.status_code == 200
            data = c.json()
            assert data["client_id"] == client_id
            assert not data.get("grupo_economico_id")
            assert not data.get("grupo_economico")
        finally:
            # restore
            restore = {**{k: v for k, v in target.items() if k != "_id"}, "grupo_economico_id": original_group_id}
            client_session.put(f"{API}/clients/{client_id}", json=restore)
