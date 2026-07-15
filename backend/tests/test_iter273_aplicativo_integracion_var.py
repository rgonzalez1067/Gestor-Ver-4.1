"""Iter273 — Verificar que la variable {Aplicativo_Integracion} SE RENDERIZA en el
correo enviado al cerrar un Proyecto de Integración.

Escenario:
  - Se crea/upserta un integrador de prueba con app_name distintivo ("QA-APP-VERIFY-273").
  - Se configura la acción 'integration_project_closed' con destinatario integrator_user
    y plantilla 'cierre_Proy_int' (subject usa {Aplicativo_Integracion} y {Integrador}).
  - POST /api/integrators/{id}/close con componente y version_componente.
  - Se lee email_logs (MongoDB) y se valida:
      * subject contiene el app_name literal (no '{Aplicativo_Integracion}').
      * html_preview NO contiene el literal '{Aplicativo_Integracion}'.
      * (best-effort) html_preview contiene '<ul' si el truncado a 500 chars lo permite
        — si no, se omite el assert (documentado en el brief).
  - Cleanup: elimina el integrador de prueba y limpia email_logs/config generados.
"""
import os
import asyncio
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"

TEST_INTG_ID = "qa_verify_273"
TEST_APP_NAME = "QA-APP-VERIFY-273"
TEST_INTG_NAME = "QA Verify 273 Integrator"


def _login():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def headers():
    return {"Authorization": f"Bearer {_login()}"}


async def _mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME], client


async def _seed_integrator():
    db, client = await _mongo()
    try:
        await db.integrators.update_one(
            {"integrator_id": TEST_INTG_ID},
            {"$set": {
                "integrator_id": TEST_INTG_ID,
                "name": TEST_INTG_NAME,
                "app_name": TEST_APP_NAME,
                "integrator_type": "Comercio",
                "integration_modality": "Directa",
                "integration_type": "e-commerce",
                "integrator_status": "En proceso",
                "project_scope": "new",
                "principal_contact_email": "qa_verify_273@test.com",
                "certifications": {"prod_c2p": "C", "prod_biopago": "C"},
            }},
            upsert=True,
        )
    finally:
        client.close()


async def _cleanup():
    db, client = await _mongo()
    try:
        await db.integrators.delete_one({"integrator_id": TEST_INTG_ID})
        await db.email_logs.delete_many({
            "action": {"$regex": "integration_project_closed"},
            "$or": [
                {"subject": {"$regex": TEST_APP_NAME}},
                {"html_preview": {"$regex": TEST_APP_NAME}},
            ]
        })
        # No borramos other_action_configs global — solo restauramos el estado a lo previo si fuese único.
        # En su lugar dejamos la config; el próximo test la sobreescribirá si es necesario.
    finally:
        client.close()


async def _get_template_id_for_close():
    """Retorna 'cierre_Proy_int' si existe, si no, cualquier template."""
    db, client = await _mongo()
    try:
        t = await db.email_templates.find_one({"template_id": "cierre_Proy_int"}, {"_id": 0, "template_id": 1, "subject": 1})
        if t:
            return t.get("template_id"), t.get("subject", "")
        t = await db.email_templates.find_one({}, {"_id": 0, "template_id": 1, "subject": 1})
        return (t or {}).get("template_id"), (t or {}).get("subject", "")
    finally:
        client.close()


async def _get_last_email_log():
    db, client = await _mongo()
    try:
        doc = await db.email_logs.find(
            {"action": {"$regex": "integration_project_closed"}},
            {"_id": 0}
        ).sort("created_at", -1).limit(1).to_list(1)
        return doc[0] if doc else None
    finally:
        client.close()


@pytest.fixture(scope="module", autouse=True)
def _setup_teardown():
    asyncio.run(_seed_integrator())
    yield
    asyncio.run(_cleanup())


def test_01_configure_action_with_close_template(headers):
    tpl_id, tpl_subject = asyncio.run(_get_template_id_for_close())
    assert tpl_id, "No hay email_templates para asociar"
    print(f"Usando template_id={tpl_id} subject='{tpl_subject}'")

    body = {
        "action_id": "integration_project_closed",
        "enabled": True,
        "recipients": [
            {
                "row_id": "r1",
                "type": "integrator_user",
                "template_id": tpl_id,
                "delivery_channel": "email",
            }
        ],
    }
    r = requests.put(f"{API}/other-actions/configs", json=body, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text


def test_02_close_and_verify_variable_rendered(headers):
    # Sanity: integrador vigente
    r = requests.get(f"{API}/integrators/{TEST_INTG_ID}", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    intg = r.json()
    assert intg["app_name"] == TEST_APP_NAME
    assert intg["integrator_status"] == "En proceso"
    assert intg["project_scope"] == "new"

    # POST /close (multipart form-data)
    files = [("componente", (None, "Plugin QA")), ("version_componente", (None, "v1.0"))]
    r = requests.post(f"{API}/integrators/{TEST_INTG_ID}/close",
                      files=files, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("certificate_generated") is True, f"cert no generado: {data}"

    notif = data.get("notification") or {}
    assert notif.get("dispatched") is True, f"dispatch no ocurrió: {notif}"
    assert notif.get("sent_count", 0) >= 1, f"sent_count debe ser >=1: {notif}"

    # Leer último email_log
    time.sleep(2)
    log = asyncio.run(_get_last_email_log())
    assert log is not None, "No hay email_log de integration_project_closed"

    subject = log.get("subject", "") or ""
    html_preview = log.get("html_preview", "") or ""
    print(f"[EMAIL LOG] subject={subject!r}")
    print(f"[EMAIL LOG] html_preview={html_preview!r}")

    # (1) NO debe quedar el literal '{Aplicativo_Integracion}' NI '{Aplicativo_Integración}'
    assert "{Aplicativo_Integracion}" not in subject, (
        f"Variable NO renderizada en subject: {subject!r}"
    )
    assert "{Aplicativo_Integración}" not in subject, (
        f"Variable con tilde NO renderizada en subject: {subject!r}"
    )
    assert "{Aplicativo_Integracion}" not in html_preview, (
        f"Variable NO renderizada en html_preview: {html_preview!r}"
    )
    assert "{Aplicativo_Integración}" not in html_preview, (
        f"Variable con tilde NO renderizada en html_preview: {html_preview!r}"
    )

    # (2) El subject DEBE contener el app_name literal
    assert TEST_APP_NAME in subject, (
        f"El subject debería contener '{TEST_APP_NAME}': {subject!r}"
    )


def test_03_medios_certificados_bullets_best_effort():
    """Best-effort: si html_preview no está truncado antes de <ul>, verificar que
    hay una lista de viñetas para {Medios_Certificados}. Si el truncado a 500 chars
    corta antes, se documenta y no falla el test (según el brief)."""
    log = asyncio.run(_get_last_email_log())
    assert log is not None
    html_preview = log.get("html_preview", "") or ""
    # No debe quedar el literal
    assert "{Medios_Certificados}" not in html_preview, (
        f"Variable {{Medios_Certificados}} NO renderizada: {html_preview!r}"
    )
    if "<ul" in html_preview:
        # Debe contener al menos un <li>
        assert "<li" in html_preview, f"<ul sin <li en html_preview: {html_preview!r}"
        print("OK: <ul><li> presente en html_preview (Medios_Certificados renderizado como lista).")
    else:
        print("NOTE: html_preview truncado antes de <ul>. Se verificó únicamente que "
              "no queda el literal {Medios_Certificados}. (Aceptable según brief.)")
