"""
Iter 276: Tests para nuevas categorías combinadas PinPad/Accesorio y PinPad/Licencia
en el catálogo de Bienes y Servicios (Hardware).

Cobertura:
- Creación de hardware con type='PinPad/Accesorio' y type='PinPad/Licencia'
- Verificación de que ambos tipos NO son serializados (is_serialized == False)
- Entrada de inventario para PinPad/Licencia SIN seriales (quantity=100)
- Entrada de inventario para PinPad/Accesorio SIN seriales
- Entrada de inventario para Pinpad SÍ exige seriales (comportamiento no roto)
- Cleanup de todos los ítems y movimientos creados en el test
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://quote-overhaul.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def api(admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="module")
def warehouse_id(api):
    r = api.get(f"{BASE_URL}/api/inventory/warehouses")
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) > 0, "No hay almacenes disponibles"
    # Usar el primer almacén (Los Chaguaramos)
    return lst[0]["warehouse_id"]


@pytest.fixture(scope="module")
def created_hardware_ids():
    """Registro de hardware_id creados para teardown."""
    ids = []
    yield ids


@pytest.fixture(scope="module")
def created_movement_ids():
    """Registro de movement_id creados para teardown."""
    ids = []
    yield ids


@pytest.fixture(scope="module", autouse=True)
def cleanup(api, created_hardware_ids, created_movement_ids):
    """Al final del módulo: borrar movimientos de inventario y hardware TEST_ creados."""
    yield
    # Borrar movimientos primero (para no impactar stock)
    for mv_id in created_movement_ids:
        try:
            api.delete(f"{BASE_URL}/api/inventory/movements/{mv_id}")
        except Exception as e:
            print(f"[cleanup] movement {mv_id}: {e}")
    for hw_id in created_hardware_ids:
        try:
            api.delete(f"{BASE_URL}/api/hardware/{hw_id}")
        except Exception as e:
            print(f"[cleanup] hardware {hw_id}: {e}")


# =========================================================
# 1. Hardware con nuevas categorías
# =========================================================
class TestHardwareNewCategories:

    def test_create_pinpad_accesorio(self, api, created_hardware_ids):
        payload = {
            "name": "TEST_ITER276_Cable Conector PinPad",
            "type": "PinPad/Accesorio",
            "asset_type": "Bien",
            "price_usd": 15.0,
            "price_bs_usd": 15.0,
            "description": "Cable de prueba iter276",
        }
        r = api.post(f"{BASE_URL}/api/hardware", json=payload)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert data["type"] == "PinPad/Accesorio"
        assert data["asset_type"] == "Bien"
        assert data["name"] == payload["name"]
        assert "hardware_id" in data and data["hardware_id"].startswith("hwr_")
        created_hardware_ids.append(data["hardware_id"])

        # Verificar persistencia
        r2 = api.get(f"{BASE_URL}/api/hardware")
        assert r2.status_code == 200
        items = r2.json()
        found = [h for h in items if h["hardware_id"] == data["hardware_id"]]
        assert len(found) == 1
        assert found[0]["type"] == "PinPad/Accesorio"

    def test_create_pinpad_licencia(self, api, created_hardware_ids):
        payload = {
            "name": "TEST_ITER276_Licencia Encriptacion Estandar",
            "type": "PinPad/Licencia",
            "asset_type": "Bien",
            "price_usd": 50.0,
            "price_bs_usd": 50.0,
            "description": "Licencia de prueba iter276",
        }
        r = api.post(f"{BASE_URL}/api/hardware", json=payload)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert data["type"] == "PinPad/Licencia"
        assert data["asset_type"] == "Bien"
        created_hardware_ids.append(data["hardware_id"])

    def test_create_pinpad_serialized(self, api, created_hardware_ids):
        """Item Pinpad estándar (serializado) para probar que el comportamiento no se rompe."""
        payload = {
            "name": "TEST_ITER276_Pinpad Serializado",
            "type": "Pinpad",
            "asset_type": "Bien",
            "price_usd": 100.0,
            "price_bs_usd": 100.0,
            "description": "Pinpad serializado prueba iter276",
        }
        r = api.post(f"{BASE_URL}/api/hardware", json=payload)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert data["type"] == "Pinpad"
        created_hardware_ids.append(data["hardware_id"])


# =========================================================
# 2. Entrada de inventario — exención de seriales
# =========================================================
class TestInventorySerialExemption:

    def _get_id_by_name(self, api, name):
        r = api.get(f"{BASE_URL}/api/hardware")
        assert r.status_code == 200
        for h in r.json():
            if h["name"] == name:
                return h["hardware_id"]
        pytest.fail(f"No se encontró hardware: {name}")

    def test_entry_pinpad_licencia_no_seriales(self, api, warehouse_id, created_movement_ids):
        """Debe permitir entrada quantity=100 SIN seriales (no serializado)."""
        item_id = self._get_id_by_name(api, "TEST_ITER276_Licencia Encriptacion Estandar")
        body = {
            "item_id": item_id,
            "quantity": 100,
            "unit_cost": 50.0,
            "serials": [],
            "notes": "TEST_ITER276 entrada licencia sin seriales",
        }
        r = api.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json=body)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert data["quantity"] == 100
        assert data["item_type"] == "PinPad/Licencia"
        assert data["serials"] == []
        assert "movement_id" in data
        created_movement_ids.append(data["movement_id"])

    def test_entry_pinpad_accesorio_no_seriales(self, api, warehouse_id, created_movement_ids):
        """PinPad/Accesorio tampoco requiere seriales."""
        item_id = self._get_id_by_name(api, "TEST_ITER276_Cable Conector PinPad")
        body = {
            "item_id": item_id,
            "quantity": 25,
            "unit_cost": 15.0,
            "serials": [],
            "notes": "TEST_ITER276 entrada accesorio sin seriales",
        }
        r = api.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json=body)
        assert r.status_code == 200, f"expected 200 got {r.status_code}: {r.text}"
        data = r.json()
        assert data["quantity"] == 25
        assert data["item_type"] == "PinPad/Accesorio"
        assert data["serials"] == []
        created_movement_ids.append(data["movement_id"])

    def test_entry_pinpad_serializado_requiere_seriales(self, api, warehouse_id, created_movement_ids):
        """Pinpad clásico SÍ debe exigir seriales — no romper comportamiento existente."""
        item_id = self._get_id_by_name(api, "TEST_ITER276_Pinpad Serializado")
        # Entrada SIN seriales suficientes => 400
        body_bad = {
            "item_id": item_id,
            "quantity": 3,
            "unit_cost": 100.0,
            "serials": [],
            "notes": "TEST_ITER276 pinpad sin seriales (debe fallar)",
        }
        r_bad = api.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json=body_bad)
        assert r_bad.status_code == 400, f"expected 400 got {r_bad.status_code}: {r_bad.text}"
        assert "serial" in r_bad.text.lower()

        # Entrada CON seriales => 200
        body_ok = {
            "item_id": item_id,
            "quantity": 3,
            "unit_cost": 100.0,
            "serials": ["TEST_ITER276_SN_A1", "TEST_ITER276_SN_A2", "TEST_ITER276_SN_A3"],
            "notes": "TEST_ITER276 pinpad con seriales",
        }
        r_ok = api.post(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/entry", json=body_ok)
        assert r_ok.status_code == 200, f"expected 200 got {r_ok.status_code}: {r_ok.text}"
        data = r_ok.json()
        assert data["quantity"] == 3
        assert len(data["serials"]) == 3
        assert data["item_type"] == "Pinpad"
        created_movement_ids.append(data["movement_id"])

    def test_stock_registrado_correctamente(self, api, warehouse_id):
        """Verifica que la entrada de PinPad/Licencia impactó el stock del almacén."""
        r = api.get(f"{BASE_URL}/api/inventory/warehouses/{warehouse_id}/stock")
        assert r.status_code == 200
        stock = r.json()
        # Buscar el item de licencia
        licencia_stock = [
            s for s in stock
            if s.get("item_name") == "TEST_ITER276_Licencia Encriptacion Estandar"
        ]
        assert len(licencia_stock) >= 1, "Stock de PinPad/Licencia no encontrado"
        assert licencia_stock[0]["quantity"] >= 100, f"Stock esperado >=100, obtenido {licencia_stock[0]['quantity']}"
        # requires_serial debe ser False
        assert licencia_stock[0].get("requires_serial") is False
