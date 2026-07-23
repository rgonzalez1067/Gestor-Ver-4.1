"""
Iter294 - Contact Profiling (Perfilamiento) tests.

Cubre:
  1) Persistencia de ContactCRM.purposes al POST /api/clients
  2) Persistencia al PUT /api/clients/{id}
  3) GET /api/clients/{id}/consolidated-contacts devuelve purposes (o [] legacy)
  4) GET /api/projects/{id}/suggested-contacts incluye purposes para source=client
  5) Cliente sembrado ASTROCEL (cli_d7a6037a7cf7) tiene ISMAEL PITA con ['taller','facturacion']
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def created_client_id(client):
    """Cliente TEST_ con 3 contactos con distintos purposes."""
    suffix = uuid.uuid4().hex[:6].upper()
    payload = {
        "rif": f"J{suffix}12345",
        "legal_name": f"TEST_ITER294_{suffix}",
        "fantasy_name": f"TEST_ITER294_{suffix}",
        "segment": "Pymes",
        "condicion": "Prospecto",
        "contacts": [
            {"full_name": "TEST Contact Taller", "email": f"taller_{suffix}@test.com",
             "phone": "0", "role": "Administrativo", "purposes": ["taller"]},
            {"full_name": "TEST Contact Fact+Impl", "email": f"factimpl_{suffix}@test.com",
             "phone": "0", "role": "Integrador", "purposes": ["facturacion", "implementacion"]},
            {"full_name": "TEST Contact Legacy", "email": f"legacy_{suffix}@test.com",
             "phone": "0", "role": "Administrativo", "purposes": []},
        ],
    }
    r = client.post(f"{BASE_URL}/api/clients", json=payload, timeout=30)
    assert r.status_code == 200, f"create failed {r.status_code} {r.text}"
    data = r.json()
    cid = data.get("client_id")
    assert cid, f"no client_id: {data}"
    yield cid
    # cleanup
    try:
        client.delete(f"{BASE_URL}/api/clients/{cid}", timeout=15)
    except Exception:
        pass


class TestContactPurposesCRUD:

    def test_create_persists_purposes(self, client, created_client_id):
        r = client.get(f"{BASE_URL}/api/clients/{created_client_id}", timeout=15)
        assert r.status_code == 200
        data = r.json()
        contacts = data.get("contacts") or []
        assert len(contacts) == 3, f"expected 3 contacts, got {len(contacts)}"
        by_email = {c.get("email"): c for c in contacts}
        taller = next(c for c in contacts if "taller_" in (c.get("email") or ""))
        factimpl = next(c for c in contacts if "factimpl_" in (c.get("email") or ""))
        legacy = next(c for c in contacts if "legacy_" in (c.get("email") or ""))
        assert taller.get("purposes") == ["taller"]
        assert set(factimpl.get("purposes") or []) == {"facturacion", "implementacion"}
        assert legacy.get("purposes") == []
        # Integrador rol persistido
        assert factimpl.get("role") == "Integrador"

    def test_update_persists_purposes(self, client, created_client_id):
        # Fetch, mutate, PUT
        r = client.get(f"{BASE_URL}/api/clients/{created_client_id}", timeout=15)
        assert r.status_code == 200
        cli = r.json()
        # Añadir 'imple_equipos' al contacto legacy
        for c in cli["contacts"]:
            if "legacy_" in (c.get("email") or ""):
                c["purposes"] = ["imple_equipos"]
        # PUT (usa ClientCreate schema — quitar campos generados)
        put_body = {k: v for k, v in cli.items()
                    if k in {"rif", "legal_name", "fantasy_name", "segment", "condicion",
                             "address", "sucursal", "contacts", "tipo_servicio",
                             "referidor_tipo", "referidor_id", "referidor_nombre"}}
        put_body["tipo_servicio"] = put_body.get("tipo_servicio") or []
        r2 = client.put(f"{BASE_URL}/api/clients/{created_client_id}", json=put_body, timeout=30)
        assert r2.status_code == 200, f"put failed {r2.status_code} {r2.text}"
        # Re-fetch
        r3 = client.get(f"{BASE_URL}/api/clients/{created_client_id}", timeout=15)
        assert r3.status_code == 200
        contacts = r3.json().get("contacts") or []
        legacy = next(c for c in contacts if "legacy_" in (c.get("email") or ""))
        assert legacy.get("purposes") == ["imple_equipos"]

    def test_consolidated_contacts_includes_purposes(self, client, created_client_id):
        r = client.get(f"{BASE_URL}/api/clients/{created_client_id}/consolidated-contacts",
                       timeout=15)
        assert r.status_code == 200
        data = r.json()
        contacts = data.get("contacts") or []
        assert len(contacts) >= 3
        # taller contact
        taller = next(c for c in contacts if "taller_" in (c.get("email") or ""))
        assert taller.get("purposes") == ["taller"], f"purposes missing/wrong: {taller}"
        factimpl = next(c for c in contacts if "factimpl_" in (c.get("email") or ""))
        assert set(factimpl.get("purposes") or []) == {"facturacion", "implementacion"}


class TestAstrocelSeed:
    """Validación del dato semilla ISMAEL PITA en cli_d7a6037a7cf7."""

    ASTROCEL_ID = "cli_d7a6037a7cf7"

    def test_astrocel_ismael_pita_purposes(self, client):
        r = client.get(f"{BASE_URL}/api/clients/{self.ASTROCEL_ID}", timeout=15)
        if r.status_code == 404:
            pytest.skip("Astrocel client not present in this env")
        assert r.status_code == 200
        contacts = r.json().get("contacts") or []
        ismael = None
        for c in contacts:
            name = (c.get("full_name") or "").upper()
            if "ISMAEL" in name and "PITA" in name:
                ismael = c
                break
        assert ismael is not None, f"ISMAEL PITA no encontrado. Contactos: {[c.get('full_name') for c in contacts]}"
        purposes = set(ismael.get("purposes") or [])
        assert "taller" in purposes and "facturacion" in purposes, f"purposes={purposes}"
        assert "imple_equipos" not in purposes
        assert "implementacion" not in purposes


class TestProjectSuggestedContacts:
    """Verifica que suggested-contacts del proyecto propague purposes en source=client."""

    def test_suggested_contacts_has_purposes_for_client_source(self, client):
        # Buscar un proyecto de ASTROCEL para minimizar deps
        r = client.get(f"{BASE_URL}/api/projects", timeout=30)
        assert r.status_code == 200
        projects = r.json() if isinstance(r.json(), list) else r.json().get("projects", [])
        target = None
        for p in projects:
            if p.get("client_id") == "cli_d7a6037a7cf7":
                target = p
                break
        if not target:
            # fallback: primer proyecto disponible
            if projects:
                target = projects[0]
        if not target:
            pytest.skip("No projects available")
        pid = target.get("project_id") or target.get("id")
        assert pid
        r2 = client.get(f"{BASE_URL}/api/projects/{pid}/suggested-contacts", timeout=30)
        assert r2.status_code == 200, f"{r2.status_code} {r2.text}"
        payload = r2.json()
        contacts = payload if isinstance(payload, list) else payload.get("contacts", [])
        # Aserciones: al menos uno source=client con purposes clave presente (aunque [])
        client_contacts = [c for c in contacts if c.get("source") == "client"]
        # Excluir el Principal (que no lleva purposes)
        crm_client = [c for c in client_contacts if c.get("contact_type") != "Principal"]
        if crm_client:
            # Al menos un contacto CRM debe tener el campo 'purposes' presente
            assert any("purposes" in c for c in crm_client), \
                f"ningún contacto CRM tiene campo purposes: {crm_client}"
        # Bank contacts: no requieren purposes
        bank_contacts = [c for c in contacts if c.get("source") == "bank"]
        for bc in bank_contacts:
            # No debe romper: pueden o no tener 'purposes', pero el flujo trabaja igual
            pass
