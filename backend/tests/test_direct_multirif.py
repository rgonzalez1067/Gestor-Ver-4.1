"""Backend tests — Proyectos Directos Multi-RIF.

Cobertura:
- Login (precondición).
- Crear un Proyecto Directo Multi-RIF con matriz POR RIF (shared_matrix=False):
  cada RIF aporta su propia grilla banco/producto y sus sucursales cuadran
  exactamente con las cajas del RIF.
- Verificar la estructura del proyecto resultante:
    * project_type == 'multirif'
    * rifs con box_count correcto
    * stores planas etiquetadas por rif, con implementation_matrix por RIF
    * direct_project == True
- Crear un Proyecto Directo Multi-RIF con matriz COMPARTIDA (shared_matrix=True).
- Regresión de cuadre estricto (400):
    * Σ cajas de sucursales != cajas del RIF
    * Σ cajas de RIFs != Cantidad de Cajas global
- Limpieza: eliminar los proyectos de prueba creados.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://email-templates-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

_created_project_ids = []


@pytest.fixture(scope="session")
def client():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["session_token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def two_clients(client):
    r = client.get(f"{API}/clients", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("clients", [])
    assert len(items) >= 2, "Se necesitan al menos 2 clientes"
    return items[0], items[1]


@pytest.fixture(scope="session")
def vpos_banks(client):
    """Devuelve 2 bancos distintos con al menos un producto VPOS disponible."""
    r = client.get(f"{API}/banks", timeout=30)
    assert r.status_code == 200
    out = []
    for b in r.json():
        prods = [p for p in (b.get("products") or []) if p.get("vpos_available")]
        if prods:
            out.append((b["name"], prods[0]["product_name"]))
        if len(out) >= 2:
            break
    assert len(out) >= 2, "Se necesitan 2 bancos con productos VPOS"
    return out


def teardown_module(module):
    """Elimina los proyectos de prueba creados (no destructivo)."""
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        return
    token = r.json()["session_token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    for pid in _created_project_ids:
        s.delete(f"{API}/projects/{pid}", timeout=30)


def test_create_multirif_per_rif_matrix(client, two_clients, vpos_banks):
    c1, c2 = two_clients
    (bank1, prod1), (bank2, prod2) = vpos_banks
    payload = {
        "client_id": c1["client_id"],
        "quote_type": "VPOS",
        "cantidad_cajas": 5,
        "project_type": "multirif",
        "multirif_sponsorship": "client",
        "shared_matrix": False,
        "server_name": "Multicomercio MSC",
        "communication_type": "SSL",
        "multirif_distribution": [
            {
                "client_id": c1["client_id"], "rif": c1.get("rif", "J1"), "client_name": c1.get("legal_name", "C1"),
                "boxes": 3,
                "stores": [{"name": "Sucursal A", "boxes": 2}, {"name": "Sucursal B", "boxes": 1}],
                "boxes_grid": [{"quantity": 1, "bank_name": bank1, "product_name": prod1}],
            },
            {
                "client_id": c2["client_id"], "rif": c2.get("rif", "J2"), "client_name": c2.get("legal_name", "C2"),
                "boxes": 2,
                "stores": [{"name": "Sucursal C", "boxes": 2}],
                "boxes_grid": [{"quantity": 1, "bank_name": bank2, "product_name": prod2}],
            },
        ],
        "boxes_grid": [],
    }
    r = client.post(f"{API}/direct-projects", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    _created_project_ids.append(pid)

    pr = client.get(f"{API}/projects/{pid}", timeout=30)
    assert pr.status_code == 200
    p = pr.json()
    assert p["project_type"] == "multirif"
    assert p.get("direct_project") is True
    assert len(p.get("rifs", [])) == 2
    rif_boxes = {r["rif"]: r["box_count"] for r in p["rifs"]}
    assert rif_boxes.get(c1.get("rif", "J1")) == 3
    assert rif_boxes.get(c2.get("rif", "J2")) == 2
    # 3 sucursales planas
    assert len(p.get("stores", [])) == 3
    # Matriz por RIF: las tiendas del RIF1 usan bank1, las del RIF2 usan bank2
    by_rif = {}
    for s in p["stores"]:
        by_rif.setdefault(s.get("rif"), set()).update((s.get("implementation_matrix") or {}).keys())
    assert by_rif.get(c1.get("rif", "J1")) == {bank1}
    assert by_rif.get(c2.get("rif", "J2")) == {bank2}


def test_create_multirif_shared_matrix(client, two_clients, vpos_banks):
    c1, _ = two_clients
    (bank1, prod1), _ = vpos_banks
    payload = {
        "client_id": c1["client_id"],
        "quote_type": "VPOS",
        "cantidad_cajas": 4,
        "project_type": "multirif",
        "multirif_sponsorship": "client",
        "shared_matrix": True,
        "server_name": "Multicomercio MSC",
        "communication_type": "VPN",
        "multirif_distribution": [
            {
                "client_id": c1["client_id"], "rif": c1.get("rif", "J1"), "client_name": c1.get("legal_name", "C1"),
                "boxes": 4,
                "stores": [{"name": "S1", "boxes": 2}, {"name": "S2", "boxes": 2}],
            },
        ],
        "boxes_grid": [{"quantity": 4, "bank_name": bank1, "product_name": prod1}],
    }
    r = client.post(f"{API}/direct-projects", json=payload, timeout=60)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    _created_project_ids.append(pid)
    p = client.get(f"{API}/projects/{pid}", timeout=30).json()
    assert p["project_type"] == "multirif"
    # Matriz compartida: ambas tiendas usan el mismo banco
    for s in p["stores"]:
        assert set((s.get("implementation_matrix") or {}).keys()) == {bank1}


def test_strict_cuadre_stores_vs_rif(client, two_clients, vpos_banks):
    """Σ cajas de sucursales != cajas del RIF → 400."""
    c1, _ = two_clients
    (bank1, prod1), _ = vpos_banks
    payload = {
        "client_id": c1["client_id"], "quote_type": "VPOS", "cantidad_cajas": 4,
        "project_type": "multirif", "shared_matrix": True,
        "server_name": "Multicomercio MSC", "communication_type": "SSL",
        "multirif_distribution": [
            {"client_id": c1["client_id"], "rif": "J1", "client_name": "C1", "boxes": 4,
             "stores": [{"name": "S1", "boxes": 3}]},
        ],
        "boxes_grid": [{"quantity": 1, "bank_name": bank1, "product_name": prod1}],
    }
    r = client.post(f"{API}/direct-projects", json=payload, timeout=60)
    assert r.status_code == 400, r.text


def test_strict_cuadre_rifs_vs_global(client, two_clients, vpos_banks):
    """Σ cajas de RIFs != Cantidad de Cajas global → 400."""
    c1, _ = two_clients
    (bank1, prod1), _ = vpos_banks
    payload = {
        "client_id": c1["client_id"], "quote_type": "VPOS", "cantidad_cajas": 5,
        "project_type": "multirif", "shared_matrix": True,
        "server_name": "Multicomercio MSC", "communication_type": "SSL",
        "multirif_distribution": [
            {"client_id": c1["client_id"], "rif": "J1", "client_name": "C1", "boxes": 3,
             "stores": [{"name": "S1", "boxes": 3}]},
        ],
        "boxes_grid": [{"quantity": 1, "bank_name": bank1, "product_name": prod1}],
    }
    r = client.post(f"{API}/direct-projects", json=payload, timeout=60)
    assert r.status_code == 400, r.text
