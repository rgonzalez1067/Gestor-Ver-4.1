# ruff: noqa
"""Backend tests — Iter68: Patrocinador de Pinpads en Proyectos Directos.

Cubre los 3 escenarios excluyentes del nuevo campo `pinpad_provider`:
  A) 'client'         → Ficha Sección B: 'Los Pinpads son suministrados por el Cliente'.
  B) 'infrastructure' → Ficha Sección B: 'Los Pinpads son suministrados por Infraestructura'
                        + notification.infrastructure.dispatched == True.
  C) 'bank'           → Ficha muestra banco/procesador (estándar) y NO glosa.
  + Independencia: client/bank NO disparan notify_infrastructure_pinpads.
  + CONFIG: catálogo expone la acción y la permite bajo 'proyectos_directos'.
"""
import io
import os
import pytest
import requests

_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not _BACKEND_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                _BACKEND_URL = line.split("=", 1)[1].strip()
                break
assert _BACKEND_URL, "REACT_APP_BACKEND_URL not set"
BASE_URL = _BACKEND_URL.rstrip("/")

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json().get("session_token") or r.json().get("token")


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def client_id(H):
    r = requests.get(f"{BASE_URL}/api/clients", headers=H, timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items") or data.get("clients") or []
    assert items, "No clients available"
    return items[0].get("client_id") or items[0].get("id")


def _payload(client_id, pinpad_provider, pinpad_bank=None, pinpad_processor_id=None,
             pinpad_processor_name=None):
    return {
        "client_id": client_id,
        "economic_group": "Grupo TEST",
        "fantasy_name": "Fantasy TEST Iter68",
        "quote_type": "VPOS",
        "sede": "PYME",
        "cantidad_cajas": 2,
        "sponsor_bank_name": "Banesco",
        "integrator_name": "TEST Integrator",
        "integrator_app_name": "TEST App",
        "pinpad_model": "Verifone Vx520",
        "pinpad_provider": pinpad_provider,
        "pinpad_bank": pinpad_bank,
        "pinpad_processor_id": pinpad_processor_id,
        "pinpad_processor_name": pinpad_processor_name,
        "fiscal_printer_model": None,
        "pinpad_serials": [],
        "is_multistore": True,
        "stores": [{"name": "Sucursal A", "box_count": 1}, {"name": "Sucursal B", "box_count": 1}],
        "boxes_grid": [{"quantity": 2, "bank_name": "Banesco", "product_name": "POS Banesco"}],
        "implementation_instructions": "Test Iter68 pinpad_provider",
    }


def _ficha_text(project_id, H):
    """Descarga la Ficha Técnica PDF y extrae el texto."""
    r = requests.get(f"{BASE_URL}/api/projects/{project_id}/ficha-tecnica",
                     headers=H, timeout=60)
    assert r.status_code == 200, f"Ficha HTTP {r.status_code}: {r.text[:200]}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
    # Extract text
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(r.content))
        return "\n".join((p.extract_text() or "") for p in reader.pages)


# ====================== CONFIG ======================
class TestCatalogConfig:
    def test_catalog_has_notify_infra_action(self, H):
        r = requests.get(f"{BASE_URL}/api/action-notifications/catalog",
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        actions = data.get("actions") or []
        ids = [a.get("id") for a in actions]
        assert "notify_infrastructure_pinpads" in ids, f"Missing action. Got: {ids}"
        allowed = data.get("allowed_actions_by_biz_sub") or {}
        key = "proyectos_directos|_"
        assert key in allowed, f"Missing key {key} in allowed_actions_by_biz_sub"
        assert "notify_infrastructure_pinpads" in allowed[key], \
            f"Action not allowed under proyectos_directos: {allowed[key]}"

    def test_config_seeded_for_notify_infra(self, H):
        key = "proyectos_directos|_|notify_infrastructure_pinpads"
        r = requests.get(f"{BASE_URL}/api/action-notifications/configs/{key}",
                         headers=H, timeout=30)
        assert r.status_code == 200, r.text
        cfg = r.json()
        recipients = cfg.get("recipients") or []
        assert len(recipients) >= 1, f"Config '{key}' has no recipients: {cfg}"
        # Channel inbox per requirement
        channels = {r.get("delivery_channel") for r in recipients}
        assert "inbox" in channels, f"No inbox delivery channel in config: {recipients}"


# ====================== ESCENARIO A: client ======================
class TestScenarioClient:
    def test_create_with_client_provider(self, H, client_id):
        p = _payload(client_id, pinpad_provider="client")
        r = requests.post(f"{BASE_URL}/api/direct-projects", json=p, headers=H, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        proj_id = data.get("project_id")
        assert proj_id
        # Independencia: no se debe disparar infra
        infra = (data.get("notification") or {}).get("infrastructure")
        assert infra is None or infra.get("dispatched") is False, \
            f"Client provider should NOT trigger infra notification: {infra}"

        # Ficha contiene la glosa cliente
        text = _ficha_text(proj_id, H)
        assert "Los Pinpads son suministrados por el Cliente" in text, \
            f"Glosa cliente missing in ficha. Sample: {text[:500]}"


# ====================== ESCENARIO B: infrastructure ======================
class TestScenarioInfrastructure:
    def test_create_with_infrastructure_provider(self, H, client_id):
        p = _payload(client_id, pinpad_provider="infrastructure")
        r = requests.post(f"{BASE_URL}/api/direct-projects", json=p, headers=H, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        proj_id = data.get("project_id")
        assert proj_id

        # Infra notification dispatched
        notif = data.get("notification") or {}
        infra = notif.get("infrastructure")
        assert infra is not None, f"Missing 'infrastructure' in notification: {notif}"
        assert infra.get("dispatched") is True, \
            f"Infra notification not dispatched: {infra}"

        # Ficha contiene glosa Infraestructura
        text = _ficha_text(proj_id, H)
        assert "Los Pinpads son suministrados por Infraestructura" in text, \
            f"Glosa infra missing in ficha. Sample: {text[:500]}"


# ====================== ESCENARIO C: bank ======================
class TestScenarioBank:
    def test_create_with_bank_provider(self, H, client_id):
        p = _payload(client_id, pinpad_provider="bank", pinpad_bank="Banesco")
        r = requests.post(f"{BASE_URL}/api/direct-projects", json=p, headers=H, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        proj_id = data.get("project_id")
        assert proj_id

        # Independencia: no se debe disparar infra
        infra = (data.get("notification") or {}).get("infrastructure")
        assert infra is None or infra.get("dispatched") is False, \
            f"Bank provider should NOT trigger infra notification: {infra}"

        # Ficha NO debe contener las glosas, pero SÍ el nombre del banco
        text = _ficha_text(proj_id, H)
        assert "Los Pinpads son suministrados por el Cliente" not in text
        assert "Los Pinpads son suministrados por Infraestructura" not in text
        assert "Banesco" in text, f"Bank name missing in ficha. Sample: {text[:500]}"
