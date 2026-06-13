"""
Backend tests for VPOS Multi-RIF Phase 2 (nested distribution Global->RIF->Store).

Validates that the backend persists:
  * is_multirif = True
  * quote_type = 'VPOS_MULTIRIF'
  * multirif_distribution = [{client_id, rif, client_name, boxes, stores:[{name,boxes}]}]

Cleanup: DELETE TEST_ quotes at end.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


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
def two_clients(client):
    r = client.get(f"{API}/clients", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("clients", data.get("items", []))
    assert len(items) >= 2, "Need at least 2 clients in DB"
    return items[:2]


def _service(bank_id, bank_name):
    return {
        "item_type": "service",
        "item_id": f"svc_{uuid.uuid4().hex[:8]}",
        "item_name": "TEST_MP_MULTIRIF_P2 - Suscripción",
        "quantity": 10,
        "unit_price_usd": 12.0,
        "total_usd": 120.0,
        "cantidad_cajas": 10,
        "cantidad_bancos": 1,
        "bank_id": bank_id,
        "bank_name": bank_name,
    }


class TestMultiRifPhase2:
    created_ids = []

    def test_login(self, session_token):
        assert isinstance(session_token, str) and len(session_token) > 10

    def test_create_multirif_with_distribution_persists(self, client, acquiring_bank, integrator, two_clients):
        bank_id = acquiring_bank["bank_id"]
        bank_name = acquiring_bank["name"]

        c1 = two_clients[0]
        c2 = two_clients[1]
        c1_id = c1.get("client_id") or c1.get("id")
        c2_id = c2.get("client_id") or c2.get("id")

        distribution = [
            {
                "client_id": c1_id,
                "rif": c1.get("rif", "J-00000000-0"),
                "client_name": c1.get("fantasy_name") or c1.get("legal_name") or "Cliente A",
                "boxes": 5,
                "stores": [
                    {"name": "Sucursal Centro", "boxes": 3},
                    {"name": "Sucursal Este", "boxes": 2},
                ],
            },
            {
                "client_id": c2_id,
                "rif": c2.get("rif", "J-11111111-1"),
                "client_name": c2.get("fantasy_name") or c2.get("legal_name") or "Cliente B",
                "boxes": 5,
                "stores": [
                    {"name": "Sucursal Oeste", "boxes": 5},
                ],
            },
        ]

        payload = {
            "client_id": None,
            "client_segment": "PYME",
            "quote_category": "implementation",
            "pricing_model": "conventional",
            "integrator_id": integrator["integrator_id"],
            "integrator_name": integrator["name"],
            "integrator_app_name": integrator.get("app_name", ""),
            "cantidad_cajas": 10,
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
            "is_multirif": True,
            "quote_type": "VPOS_MULTIRIF",
            "services": [_service(bank_id, bank_name)],
            "sponsored_implementation": True,
            "sponsoring_bank_id": bank_id,
            "sponsoring_bank_name": bank_name,
            "notes": "TEST_MULTIRIF_PHASE2",
            "override_total_usd": 120.0,
            "multirif_distribution": distribution,
        }

        r = client.post(f"{API}/quotes/create-with-pdf", json=payload, timeout=60)
        assert r.status_code == 200, f"create failed: {r.status_code} {r.text[:600]}"
        body = r.json()
        q = body.get("quote") or {}
        quote_id = q.get("quote_id")
        assert quote_id
        TestMultiRifPhase2.created_ids.append(quote_id)

        # Persistence verification
        rg = client.get(f"{API}/quotes/{quote_id}", timeout=30)
        assert rg.status_code == 200
        qg = rg.json()
        assert qg.get("quote_type") == "VPOS_MULTIRIF"
        assert qg.get("is_multirif") is True
        dist = qg.get("multirif_distribution")
        assert isinstance(dist, list), f"multirif_distribution missing/not list: {dist}"
        assert len(dist) == 2, f"Expected 2 RIFs, got {len(dist)}"

        # Validate first RIF
        r0 = dist[0]
        assert r0["client_id"] == c1_id
        assert r0["boxes"] == 5
        assert isinstance(r0["stores"], list) and len(r0["stores"]) == 2
        store_boxes_sum = sum(s["boxes"] for s in r0["stores"])
        assert store_boxes_sum == 5

        # Validate second RIF
        r1 = dist[1]
        assert r1["client_id"] == c2_id
        assert r1["boxes"] == 5
        assert len(r1["stores"]) == 1
        assert r1["stores"][0]["name"] == "Sucursal Oeste"
        assert r1["stores"][0]["boxes"] == 5

        # Total assigned matches global boxes
        total_assigned = sum(r["boxes"] for r in dist)
        assert total_assigned == 10

    @classmethod
    def teardown_class(cls):
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
