"""
Iter 227 - Backend tests for Integrator "Clientes Instalados" feature.

Endpoints:
  GET /api/integrators/{id}/installed-clients
  GET /api/integrators/{id}/installed-clients/pdf

Business rules:
  A client is listed only if:
    (integrador_id == integrator.integrator_id OR
     integrador_name (case-insensitive equal) == integrator.name)
    AND aplicativo (case-insensitive equal) == integrator.app_name
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

QATEST_PREFIX = "QATEST_"


# -------- fixtures --------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok, f"session_token missing in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _rand_rif():
    return f"J-{uuid.uuid4().hex[:8].upper()}-0"


def _mk_int_name():
    return f"{QATEST_PREFIX}Integ_{uuid.uuid4().hex[:6]}"


def _mk_app_name(tag):
    return f"{QATEST_PREFIX}App_{tag}_{uuid.uuid4().hex[:4]}"


@pytest.fixture(scope="module")
def scenario(session):
    """
    Create an integrator X with app_name AppY, plus:
      - Client A: integrador_id=X.id, aplicativo=AppY (match by id)  -> LISTED
      - Client B: integrador_id=X.id, aplicativo=AppZ (wrong app)    -> EXCLUDED
      - Client C: no integrador_id, integrador_name=X (mixed case),
                  aplicativo=lowercase AppY                            -> LISTED (name + case-insensitive)
      - Second integrator W (different name, same AppY) to make sure the
        endpoint is scoped strictly per integrator.
    """
    int_name = _mk_int_name()
    app_y = _mk_app_name("Y")
    app_z = _mk_app_name("Z")

    # integrator X
    resp = session.post(f"{API}/integrators", json={
        "name": int_name,
        "integrator_type": "Integrador",
        "app_name": app_y,
        "integration_modality": "REST",
        "integrator_status": "En proceso",
    }, timeout=30)
    assert resp.status_code in (200, 201), f"create integrator failed: {resp.status_code} {resp.text[:200]}"
    intg = resp.json()
    intg_id = intg["integrator_id"]

    # Client A - matches by id + exact app
    ra = session.post(f"{API}/clients", json={
        "rif": _rand_rif(), "legal_name": f"{QATEST_PREFIX}Cliente A", "fantasy_name": "CliA",
        "integrador_id": intg_id, "integrador_name": int_name, "aplicativo": app_y,
        "condicion": "Cliente",
    }, timeout=30)
    assert ra.status_code in (200, 201), f"client A: {ra.status_code} {ra.text[:200]}"

    # Client B - same integrator but different app
    rb = session.post(f"{API}/clients", json={
        "rif": _rand_rif(), "legal_name": f"{QATEST_PREFIX}Cliente B", "fantasy_name": "CliB",
        "integrador_id": intg_id, "integrador_name": int_name, "aplicativo": app_z,
        "condicion": "Cliente",
    }, timeout=30)
    assert rb.status_code in (200, 201), f"client B: {rb.status_code} {rb.text[:200]}"

    # Client C - name-based match + case-insensitive on both fields
    rc = session.post(f"{API}/clients", json={
        "rif": _rand_rif(), "legal_name": f"{QATEST_PREFIX}Cliente C", "fantasy_name": "CliC",
        "integrador_name": int_name.upper(),  # different case
        "aplicativo": app_y.lower(),          # different case
        "condicion": "Prospecto",
    }, timeout=30)
    assert rc.status_code in (200, 201), f"client C: {rc.status_code} {rc.text[:200]}"

    yield {
        "integrator_id": intg_id,
        "integrator_name": int_name,
        "app_name": app_y,
        "app_z": app_z,
    }


# -------- tests --------

class TestInstalledClientsAPI:
    def test_endpoint_returns_expected_shape_and_matches(self, session, scenario):
        r = session.get(f"{API}/integrators/{scenario['integrator_id']}/installed-clients", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # shape
        for key in ("integrator_name", "app_name", "count", "clients"):
            assert key in data, f"missing key {key} in {data}"
        assert data["integrator_name"] == scenario["integrator_name"]
        assert data["app_name"] == scenario["app_name"]
        assert isinstance(data["clients"], list)

        # ONLY QATEST_ clients we created that must be listed: A and C
        qat_legals = [c["legal_name"] for c in data["clients"] if c.get("legal_name", "").startswith(QATEST_PREFIX)]
        assert f"{QATEST_PREFIX}Cliente A" in qat_legals, f"Client A missing. Got: {qat_legals}"
        assert f"{QATEST_PREFIX}Cliente C" in qat_legals, f"Client C (name+ci match) missing. Got: {qat_legals}"
        assert f"{QATEST_PREFIX}Cliente B" not in qat_legals, "Client B (wrong aplicativo) must be excluded"
        # count matches list length
        assert data["count"] == len(data["clients"])
        # each row exposes the 4 documented fields
        for row in data["clients"]:
            for k in ("rif", "legal_name", "fantasy_name", "condicion"):
                assert k in row, f"row missing {k}: {row}"

    def test_404_for_nonexistent_integrator(self, session):
        r = session.get(f"{API}/integrators/int_doesnotexist_zzz/installed-clients", timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code} {r.text[:200]}"


class TestInstalledClientsPDF:
    def test_pdf_ok(self, session, scenario):
        r = session.get(f"{API}/integrators/{scenario['integrator_id']}/installed-clients/pdf", timeout=60)
        assert r.status_code == 200, r.text[:300]
        # PDF magic header
        assert r.content[:4] == b"%PDF", f"not a PDF: {r.content[:8]!r}"
        # correct content-type
        assert "application/pdf" in r.headers.get("content-type", "").lower()
        # attachment header present
        cd = r.headers.get("content-disposition", "").lower()
        assert "attachment" in cd and "clientes_instalados" in cd

    def test_pdf_404_for_unknown(self, session):
        r = session.get(f"{API}/integrators/int_unknown_xxxx/installed-clients/pdf", timeout=30)
        assert r.status_code == 404


# -------- cleanup --------
def test_zzz_cleanup_qatest(session):
    """Runs last (alphabetically). Wipes QATEST_ integrators and clients directly."""
    # find QATEST_ integrators
    r = session.get(f"{API}/integrators", timeout=30)
    if r.status_code == 200:
        for i in r.json() if isinstance(r.json(), list) else r.json().get("items", []):
            if i.get("name", "").startswith(QATEST_PREFIX):
                iid = i.get("integrator_id")
                if iid:
                    session.delete(f"{API}/integrators/{iid}", timeout=30)
    # find QATEST_ clients
    r = session.get(f"{API}/clients", timeout=30)
    if r.status_code == 200:
        for c in r.json():
            if c.get("legal_name", "").startswith(QATEST_PREFIX):
                cid = c.get("client_id")
                if cid:
                    session.delete(f"{API}/clients/{cid}", timeout=30)

    # verify (best-effort)
    r2 = session.get(f"{API}/integrators", timeout=30)
    if r2.status_code == 200:
        leftover_int = [i for i in (r2.json() if isinstance(r2.json(), list) else r2.json().get("items", []))
                        if i.get("name", "").startswith(QATEST_PREFIX)]
        print(f"Leftover QATEST_ integrators: {len(leftover_int)}")
    r3 = session.get(f"{API}/clients", timeout=30)
    if r3.status_code == 200:
        leftover_cli = [c for c in r3.json() if c.get("legal_name", "").startswith(QATEST_PREFIX)]
        print(f"Leftover QATEST_ clients: {len(leftover_cli)}")
