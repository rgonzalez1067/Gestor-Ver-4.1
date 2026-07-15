"""
Backend tests for VPOS Multi-RIF Phase 1 (Comercial Entry + Data Foundation).

Coverage:
- Login (precondition)
- Create a quote with quote_type='VPOS_MULTIRIF' WITHOUT client_id but with
  sponsoring_bank_id + sponsored_implementation=True.
- Verify persistence (GET /quotes/{id}):
    * quote_type == 'VPOS_MULTIRIF'
    * is_multirif == True
    * sponsored_implementation == True
    * sponsoring_bank_id populated
    * sponsoring_bank_name populated
    * client_name synthetic 'Lote <Banco> (Multi-RIF)'
    * client_id empty (since multirif)
- Regression: Create a standard VPOS quote with client_id and verify is_multirif=False.
- Cleanup: delete created TEST_ quotes at end.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://integrator-hub-6.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def session_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="session")
def client(session_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {session_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def acquiring_bank(client):
    """Pick a known bank (Banco de Venezuela preferred)."""
    r = client.get(f"{API}/banks", timeout=30)
    assert r.status_code == 200
    banks = r.json()
    target = next((b for b in banks if b.get("name") == "Banco de Venezuela"), None) or banks[0]
    return target


@pytest.fixture(scope="session")
def integrator(client):
    r = client.get(f"{API}/integrators/dropdown", timeout=30)
    assert r.status_code == 200
    items = r.json()
    assert len(items) > 0
    return items[0]


@pytest.fixture(scope="session")
def any_client(client):
    """Pick any client for regression VPOS test."""
    r = client.get(f"{API}/clients?limit=1", timeout=30)
    if r.status_code != 200:
        r = client.get(f"{API}/clients", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("clients", data.get("items", []))
    assert items, "Need at least one client in DB for regression test"
    return items[0]


# ---------- Helpers ----------
def _build_service_item(bank_id, bank_name, marker):
    """A minimal QuoteItem (service) for /quotes/create-with-pdf."""
    return {
        "item_type": "service",
        "item_id": f"svc_{uuid.uuid4().hex[:8]}",
        "item_name": f"TEST_MP_{marker} - Suscripción PDV/Banco",
        "quantity": 5,
        "unit_price_usd": 12.0,
        "total_usd": 60.0,
        "cantidad_cajas": 5,
        "cantidad_bancos": 1,
        "bank_id": bank_id,
        "bank_name": bank_name,
    }


def _common_payload(integrator):
    return {
        "client_segment": "PYME",
        "quote_category": "implementation",
        "pricing_model": "conventional",
        "integrator_id": integrator["integrator_id"],
        "integrator_name": integrator["name"],
        "integrator_app_name": integrator.get("app_name", ""),
        "cantidad_cajas": 5,
        "cantidad_bancos": 1,
        "is_production_client": False,
        "requires_pinpad_config": True,
        "requires_vpn": False,
        "communication_type": "NO_APLICA",
        "production_items": [],
        "branch_details": [],
        "iva_exempt": False,
        "descuento_setup": 0,
        "descuento_recurrente": 0,
        "hardware": [],
        "ft_equipment_items": [],
        "pdf_data": {},
    }


# ---------- Tests ----------
class TestMultiRifPhase1:
    created_ids = []  # class-level for teardown

    def test_login_works(self, session_token):
        assert isinstance(session_token, str) and len(session_token) > 10

    def test_create_multirif_quote_persists_correctly(self, client, acquiring_bank, integrator):
        # Build payload matching what the frontend wizard posts for VPOS_MULTIRIF
        bank_id = acquiring_bank["bank_id"]
        bank_name = acquiring_bank["name"]
        services = [_build_service_item(bank_id, bank_name, marker="MULTIRIF")]

        payload = _common_payload(integrator)
        payload.update({
            "client_id": None,             # NO client for multirif
            "is_multirif": True,
            "quote_type": "VPOS_MULTIRIF",
            "services": services,
            "sponsored_implementation": True,
            "sponsoring_bank_id": bank_id,
            "sponsoring_bank_name": bank_name,
            "sponsor_bank_id": "",
            "sponsor_bank_name": "",
            "notes": "TEST_MULTIRIF_PHASE1",
            "override_total_usd": 60.0,
        })

        r = client.post(f"{API}/quotes/create-with-pdf", json=payload, timeout=60)
        assert r.status_code == 200, f"create-with-pdf failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        assert "quote" in body, body
        q = body["quote"]
        quote_id = q.get("quote_id")
        assert quote_id, "Missing quote_id in response"
        TestMultiRifPhase1.created_ids.append(quote_id)

        # Assertions on the response payload
        assert q.get("quote_type") == "VPOS_MULTIRIF"
        assert q.get("is_multirif") is True
        assert q.get("sponsored_implementation") is True
        assert q.get("sponsoring_bank_id") == bank_id
        assert q.get("sponsoring_bank_name") == bank_name
        assert (q.get("client_name") or "").startswith("Lote ")
        assert bank_name in q.get("client_name", "")
        assert "(Multi-RIF)" in q.get("client_name", "")

        # Verify persistence via GET
        rg = client.get(f"{API}/quotes/{quote_id}", timeout=30)
        assert rg.status_code == 200, rg.text
        qg = rg.json()
        assert qg.get("quote_type") == "VPOS_MULTIRIF"
        assert qg.get("is_multirif") is True
        assert qg.get("sponsored_implementation") is True
        assert qg.get("sponsoring_bank_id") == bank_id
        assert qg.get("sponsoring_bank_name") == bank_name
        assert (qg.get("client_name") or "").startswith("Lote ")
        # client_id should be empty or falsy for multirif
        assert not qg.get("client_id"), f"client_id should be empty for multirif but got {qg.get('client_id')}"

    def test_regression_vpos_quote_with_client(self, client, any_client, integrator, acquiring_bank):
        """Standard VPOS still works with client_id and without is_multirif flag."""
        client_id = any_client.get("client_id") or any_client.get("id")
        assert client_id, f"Could not extract client_id from {any_client}"

        services = [_build_service_item(acquiring_bank["bank_id"], acquiring_bank["name"], marker="VPOS")]
        payload = _common_payload(integrator)
        payload.update({
            "client_id": client_id,
            "is_multirif": False,
            "quote_type": "VPOS",
            "services": services,
            "sponsored_implementation": False,
            "sponsoring_bank_id": "",
            "sponsoring_bank_name": "",
            "sponsor_bank_id": "",
            "sponsor_bank_name": "",
            "notes": "TEST_VPOS_REGRESSION_PHASE1",
            "override_total_usd": 60.0,
        })

        r = client.post(f"{API}/quotes/create-with-pdf", json=payload, timeout=60)
        assert r.status_code == 200, f"VPOS create failed: {r.status_code} {r.text[:500]}"
        q = r.json()["quote"]
        quote_id = q.get("quote_id")
        assert quote_id
        TestMultiRifPhase1.created_ids.append(quote_id)

        assert q.get("quote_type") == "VPOS"
        assert bool(q.get("is_multirif")) is False
        assert q.get("client_id") == client_id
        # client_name should be the client's name, not a "Lote ..." synthetic
        assert not (q.get("client_name") or "").startswith("Lote ")

        # GET persistence
        rg = client.get(f"{API}/quotes/{quote_id}", timeout=30)
        assert rg.status_code == 200
        qg = rg.json()
        assert qg.get("client_id") == client_id
        assert bool(qg.get("is_multirif")) is False

    def test_multirif_without_sponsoring_bank_creates_lote_banco_fallback(self, client, integrator):
        """
        Edge: if multirif is true but sponsoring_bank_name is empty, backend should still
        generate a synthetic client_name with fallback 'Banco'. Not the expected UI path,
        but validates backend defensive default.
        """
        payload = _common_payload(integrator)
        payload.update({
            "client_id": None,
            "is_multirif": True,
            "quote_type": "VPOS_MULTIRIF",
            "services": [],
            "sponsored_implementation": True,
            "sponsoring_bank_id": "",
            "sponsoring_bank_name": "",
            "notes": "TEST_MULTIRIF_NOBANK_PHASE1",
            "override_total_usd": 0.0,
        })
        r = client.post(f"{API}/quotes/create-with-pdf", json=payload, timeout=60)
        # Backend may or may not allow empty services. Accept 200 (created) or 4xx.
        if r.status_code == 200:
            q = r.json()["quote"]
            TestMultiRifPhase1.created_ids.append(q["quote_id"])
            assert q.get("is_multirif") is True
            assert (q.get("client_name") or "").startswith("Lote ")
        else:
            # Acceptable if backend rejects empty services
            assert r.status_code in (400, 422), f"Unexpected status: {r.status_code} {r.text[:200]}"

    @classmethod
    def teardown_class(cls):
        """Cleanup created TEST_ quotes."""
        try:
            r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
            tok = r.json()["session_token"]
            h = {"Authorization": f"Bearer {tok}"}
            for qid in cls.created_ids:
                try:
                    requests.delete(f"{API}/quotes/{qid}", headers=h, timeout=20)
                except Exception:
                    pass
        except Exception:
            pass
