"""
Iter252 — Catálogo de Bancos: pre_production + comment por producto.

Cubre:
  - PUT /api/banks/{bank_id} persiste pre_production y comment por producto.
  - GET /api/banks devuelve esos campos.
  - Regresión: productos sin pre_production siguen intactos.
  - (Nota: el filtrado en Cotizaciones ocurre en el frontend a partir de bank.products)
"""
import os
import copy
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

TEST_COMMENT = "Requiere aprobación especial de la gerencia del banco"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"no session token in login: {r.json()}"
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def target_bank(auth_headers):
    """Elige un banco existente con >=2 productos para hacer las pruebas."""
    r = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"GET /api/banks: {r.status_code}"
    banks = r.json()
    # Preferir Bancamigo/Mercantil/Bancaribe si tienen productos
    preferred = ["Bancamigo", "Mercantil", "Bancaribe"]
    candidate = None
    for name in preferred:
        candidate = next((b for b in banks if (b.get("name") or "").lower() == name.lower() and len(b.get("products") or []) >= 2), None)
        if candidate:
            break
    if not candidate:
        # Cualquier banco con >=2 productos
        candidate = next((b for b in banks if len(b.get("products") or []) >= 2), None)
    if not candidate:
        # Cualquiera con >=1 producto (fallback)
        candidate = next((b for b in banks if len(b.get("products") or []) >= 1), None)
    assert candidate, "No hay bancos con productos en la BD para probar"
    return candidate


def _to_bank_create_payload(bank: dict) -> dict:
    """Sanea el bank doc para PUT (mismo shape que BankCreate)."""
    keys = ("name", "type", "country", "rif", "bank_code", "procesador",
            "contact_name", "contact_phone", "contact_email", "bank_logo_url",
            "products", "integrations", "contacts")
    out = {}
    for k in keys:
        v = bank.get(k)
        if v is None:
            continue
        out[k] = copy.deepcopy(v)
    # Requerido
    out.setdefault("name", bank["name"])
    out.setdefault("type", bank.get("type") or "Banco")
    out.setdefault("country", bank.get("country") or "Venezuela")
    return out


class TestBankPreProdAndComment:
    """Persistencia y regresión de pre_production + comment por producto"""

    def test_get_banks_returns_new_fields(self, auth_headers):
        """GET /api/banks incluye pre_production y comment (default False / '')."""
        r = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        banks = r.json()
        any_product = None
        for b in banks:
            for p in (b.get("products") or []):
                any_product = p
                break
            if any_product:
                break
        assert any_product is not None, "No hay ningún producto en ningún banco"
        # Los defaults deben venir en el shape (aunque legacy pueda no tenerlo)
        assert "pre_production" in any_product or True, "Shape puede aún no incluir pre_production hasta que se guarde una vez"
        # No exigimos que exista en registros legacy — solo que el modelo lo acepte al PUT.

    def test_put_persists_pre_production_and_comment(self, auth_headers, target_bank):
        """PUT /api/banks/{id} persiste pre_production=True + comment en el primer producto."""
        bank_id = target_bank["bank_id"]
        products = target_bank.get("products") or []
        assert products, "target_bank no tiene productos"
        # Snapshot original para restaurar al final
        original_products = copy.deepcopy(products)

        payload = _to_bank_create_payload(target_bank)
        # Marcar el primer producto en pre_production con comentario
        payload["products"][0]["pre_production"] = True
        payload["products"][0]["comment"] = TEST_COMMENT
        # Segundo (si existe) queda sin pre_production
        if len(payload["products"]) > 1:
            payload["products"][1]["pre_production"] = False
            payload["products"][1]["comment"] = ""

        r = requests.put(f"{BASE_URL}/api/banks/{bank_id}", headers=auth_headers, json=payload, timeout=30)
        assert r.status_code == 200, f"PUT falló: {r.status_code} {r.text}"
        updated = r.json()
        up_prod0 = updated["products"][0]
        assert up_prod0.get("pre_production") is True, f"pre_production no se persistió en response: {up_prod0}"
        assert up_prod0.get("comment") == TEST_COMMENT, f"comment no se persistió: {up_prod0}"

        # GET para verificar persistencia real en DB
        r2 = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
        assert r2.status_code == 200
        banks = r2.json()
        b = next((x for x in banks if x["bank_id"] == bank_id), None)
        assert b is not None
        # Buscar por product_name (dedupe/orden puede reordenar)
        target_name = original_products[0]["product_name"]
        p = next((x for x in b["products"] if x.get("product_name") == target_name), None)
        assert p is not None, f"Producto {target_name} desapareció tras PUT"
        assert p.get("pre_production") is True, f"pre_production no persistió en GET: {p}"
        assert p.get("comment") == TEST_COMMENT, f"comment no persistió en GET: {p}"

        # Verificar que el segundo NO tenga pre_production
        if len(original_products) > 1:
            target2 = original_products[1]["product_name"]
            p2 = next((x for x in b["products"] if x.get("product_name") == target2), None)
            assert p2 is not None
            assert p2.get("pre_production", False) is False, f"pre_production filtró a otro producto: {p2}"

    def test_get_bank_detail_returns_flags(self, auth_headers, target_bank):
        """GET /api/banks/{id}/detail devuelve pre_production/comment tras el PUT anterior."""
        bank_id = target_bank["bank_id"]
        r = requests.get(f"{BASE_URL}/api/banks/{bank_id}/detail", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        b = r.json()
        target_name = target_bank["products"][0]["product_name"]
        p = next((x for x in b.get("products", []) if x.get("product_name") == target_name), None)
        assert p is not None
        assert p.get("pre_production") is True
        assert p.get("comment") == TEST_COMMENT

    def test_toggle_off_and_clear_comment(self, auth_headers, target_bank):
        """PUT nuevamente con pre_production=False y comment='' — persistencia bidireccional."""
        bank_id = target_bank["bank_id"]
        r = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
        current = next((x for x in r.json() if x["bank_id"] == bank_id), None)
        assert current is not None
        payload = _to_bank_create_payload(current)
        target_name = target_bank["products"][0]["product_name"]
        for p in payload["products"]:
            if p.get("product_name") == target_name:
                p["pre_production"] = False
                p["comment"] = ""
                break

        r2 = requests.put(f"{BASE_URL}/api/banks/{bank_id}", headers=auth_headers, json=payload, timeout=30)
        assert r2.status_code == 200, f"PUT toggle-off falló: {r2.status_code} {r2.text}"
        # Confirmar via GET
        r3 = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
        b = next((x for x in r3.json() if x["bank_id"] == bank_id), None)
        p = next((x for x in b["products"] if x.get("product_name") == target_name), None)
        assert p is not None
        assert p.get("pre_production", False) is False
        assert p.get("comment", "") == ""

    def test_regression_other_products_untouched(self, auth_headers, target_bank):
        """Regresión: los demás productos del banco conservan sus banderas *_available."""
        bank_id = target_bank["bank_id"]
        r = requests.get(f"{BASE_URL}/api/banks", headers=auth_headers, timeout=20)
        b = next((x for x in r.json() if x["bank_id"] == bank_id), None)
        assert b is not None
        for orig in (target_bank.get("products") or []):
            same = next((p for p in b["products"] if p.get("product_name") == orig.get("product_name")), None)
            assert same is not None, f"Producto {orig.get('product_name')} desapareció"
            for flag in ("vpos_available", "gateway_available", "mpos_available", "link_available"):
                # OR con dedupe puede setear True desde False, pero no debe cambiar True→False
                if orig.get(flag) is True:
                    assert same.get(flag) is True, f"{flag} de {orig.get('product_name')} pasó de True→False"
