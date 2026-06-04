"""Tests for Equipment PDF generation with serials field (iter 182)

Covers:
- POST /api/quotes/generate-equipment-pdf accepts items[].serials (0, 2, 3 serials)
- EquipmentPDFItem defaults serials=[] when not sent
- Response is application/pdf with reasonable bytesize (>10KB)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://audit-proyectos-v2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "ragg1008@gmail.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("session_token") or data.get("access_token") or data.get("token")
    assert tok, f"No token in login response: {list(data.keys())}"
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def _pdf_payload(items, equipment_type="Reparación", repair_models=None):
    return {
        "client_id": "",
        "cliente_nombre": "TEST_Cliente_Serials",
        "cliente_rif": "J-00000000-0",
        "cliente_address": "Test Address",
        "equipment_type": equipment_type,
        "items": items,
        "notes": "Prueba de seriales",
        "repair_description": "Reparación de POS múltiples unidades",
        "equipment_serial_number": "",
        "estimated_delivery_date": "",
        "bulk_serials": [],
        "repair_models": repair_models or [],
    }


# --- Item with 0 serials (absence / empty) ---
def test_pdf_item_without_serials_field_defaults_empty(headers):
    items = [{
        "hardware_id": "",
        "name": "Servicio Reparación",
        "hardware_type": "Servicio",
        "quantity": 1,
        "unit_price_usd": 50.0,
        "total_usd": 50.0,
        # no serials key at all -> should default to []
    }]
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items), headers=headers, timeout=60)
    assert r.status_code == 200, f"PDF gen failed: {r.status_code} {r.text[:400]}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), f"Wrong content-type: {r.headers.get('content-type')}"
    assert len(r.content) > 10_000, f"PDF too small: {len(r.content)} bytes"
    assert r.content[:4] == b"%PDF", "PDF signature missing"


def test_pdf_item_with_explicit_empty_serials_list(headers):
    items = [{
        "hardware_id": "",
        "name": "Servicio Diagnóstico",
        "hardware_type": "Servicio",
        "quantity": 1,
        "unit_price_usd": 20.0,
        "total_usd": 20.0,
        "serials": [],
    }]
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items), headers=headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 10_000


# --- Item with 2 serials ---
def test_pdf_item_with_2_serials(headers):
    items = [{
        "hardware_id": "",
        "name": "Reparación Tarjeta POS",
        "hardware_type": "Servicio",
        "quantity": 2,
        "unit_price_usd": 75.0,
        "total_usd": 150.0,
        "serials": ["SN001TEST", "SN002TEST"],
    }]
    repair_models = [{
        "model_name": "TEST_POS_Model_A",
        "model_id": "",
        "quantity": 2,
        "serials": ["SN001TEST", "SN002TEST"],
    }]
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items, repair_models=repair_models),
                      headers=headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 10_000


# --- Item with 3 serials ---
def test_pdf_item_with_3_serials(headers):
    items = [{
        "hardware_id": "",
        "name": "Reparación Pantalla",
        "hardware_type": "Servicio",
        "quantity": 3,
        "unit_price_usd": 40.0,
        "total_usd": 120.0,
        "serials": ["SN010TEST", "SN011TEST", "SN012TEST"],
    }]
    repair_models = [{
        "model_name": "TEST_POS_Model_B",
        "model_id": "",
        "quantity": 3,
        "serials": ["SN010TEST", "SN011TEST", "SN012TEST"],
    }]
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items, repair_models=repair_models),
                      headers=headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 10_000


# --- N:N: same serial in multiple items (shouldn't fail backend) ---
def test_pdf_multiple_items_sharing_same_serial_n_to_n(headers):
    shared = "SN_SHARED_001"
    items = [
        {
            "hardware_id": "",
            "name": "Concepto A - Diagnóstico",
            "hardware_type": "Servicio",
            "quantity": 2,
            "unit_price_usd": 10.0,
            "total_usd": 20.0,
            "serials": [shared, "SN_B"],
        },
        {
            "hardware_id": "",
            "name": "Concepto B - Reparación",
            "hardware_type": "Servicio",
            "quantity": 3,
            "unit_price_usd": 30.0,
            "total_usd": 90.0,
            "serials": [shared, "SN_B", "SN_C"],  # shared serial also here
        },
    ]
    repair_models = [{
        "model_name": "TEST_Shared_Model",
        "model_id": "",
        "quantity": 3,
        "serials": [shared, "SN_B", "SN_C"],
    }]
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items, repair_models=repair_models),
                      headers=headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 10_000


# --- Payload without repair_models at all (should still pass) ---
def test_pdf_serials_without_repair_models_section(headers):
    items = [{
        "hardware_id": "",
        "name": "Reparación Simple",
        "hardware_type": "Servicio",
        "quantity": 2,
        "unit_price_usd": 15.0,
        "total_usd": 30.0,
        "serials": ["XA01", "XA02"],
    }]
    # equipment_type distinto, sin repair_models
    r = requests.post(f"{BASE_URL}/api/quotes/generate-equipment-pdf",
                      json=_pdf_payload(items, equipment_type="Accesorio"),
                      headers=headers, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert len(r.content) > 10_000
