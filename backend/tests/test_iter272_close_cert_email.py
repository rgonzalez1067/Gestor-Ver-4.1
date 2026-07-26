"""Iter272 — Cierre de Proyecto de Integración: el Certificado PDF se adjunta
y el envío ocurre incluso sin plantilla (fallback body).

Cubre:
  (A) Con acción activa + destinatario integrator_user (email) + PDF en depósito
      → email_logs registra sent_count>=1 y attachment_names incluye 'Certificado_QA_CERT.pdf'.
  (B) FALLBACK sin plantilla (template_id vacío): el envío ocurre igualmente con
      cuerpo genérico y adjunto (sent_count>=1, skipped vacío en el bitácora entry).
"""
import os
import io
import time
import pytest
import requests
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://perfilado-contactos.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"


def _login():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def token():
    return _login()


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# Helpers async
async def _mongo():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME], client


async def _reseed_qa_cert():
    db, client = await _mongo()
    try:
        # Reseed qa_cert as 'new', 2 productos 'C', integrator_type set, En proceso
        await db.integrators.update_one(
            {"integrator_id": "qa_cert"},
            {"$set": {
                "integrator_id": "qa_cert",
                "name": "QA_CERT",
                "app_name": "Plugin QA",
                "integrator_type": "Comercio",
                "integration_modality": "Directa",
                "integration_type": "e-commerce",
                "integrator_status": "En proceso",
                "project_scope": "new",
                "principal_contact_email": "qa_cert_dest@test.com",
                "certifications": {"prod_c2p": "C", "prod_biopago": "C"},
            }},
            upsert=True,
        )
    finally:
        client.close()


async def _get_last_email_log(action_contains: str):
    db, client = await _mongo()
    try:
        doc = await db.email_logs.find(
            {"action": {"$regex": action_contains}},
            {"_id": 0}
        ).sort("created_at", -1).limit(1).to_list(1)
        return doc[0] if doc else None
    finally:
        client.close()


async def _cleanup():
    db, client = await _mongo()
    try:
        await db.other_action_configs.delete_one({"action_id": "integration_project_closed"})
        await db.email_logs.delete_many({"action": {"$regex": "integration_project_closed"}})
    finally:
        client.close()


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Ensure seed exists
    asyncio.run(_reseed_qa_cert())
    yield
    asyncio.run(_cleanup())


# ============ (0) Upload PDF Certificado al depósito ============
def test_00_upload_certificate_pdf(headers):
    # Genera un PDF mínimo válido con reportlab
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica", 20)
    c.drawString(100, 750, "Certificado Base QA")
    c.showPage()
    c.save()
    buf.seek(0)
    files = {"file": ("cert_base.pdf", buf.getvalue(), "application/pdf")}
    r = requests.post(f"{API}/integrators/config/certificate", files=files, headers=headers, timeout=30)
    assert r.status_code == 200, r.text

    # Verificar que existe en la config
    r2 = requests.get(f"{API}/integrators/config/certificate", headers=headers, timeout=20)
    assert r2.status_code == 200
    assert r2.json().get("exists") is True


# ============ (A) Configurar acción activa con destinatario integrator_user + template  ============
def _get_any_template_id():
    """Toma cualquier email_template existente en la DB para asociar al destinatario."""
    async def _q():
        db, client = await _mongo()
        try:
            t = await db.email_templates.find_one({}, {"_id": 0, "template_id": 1})
            return (t or {}).get("template_id")
        finally:
            client.close()
    return asyncio.run(_q())


def test_10_configure_action_with_template(headers):
    tpl_id = _get_any_template_id() or ""
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


# ============ (B) Cerrar proyecto qa_cert y verificar sent_count + adjunto ============
def test_20_close_project_sends_certificate(headers):
    # Verificar que seed vigente
    r = requests.get(f"{API}/integrators/qa_cert", headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    intg = r.json()
    assert intg["integrator_status"] == "En proceso"
    assert intg["project_scope"] == "new"

    # POST /close (multipart)
    files = [("componente", (None, "Plugin QA")), ("version_componente", (None, "v1.0"))]
    r = requests.post(f"{API}/integrators/qa_cert/close", files=files, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("certificate_generated") is True, f"cert PDF no generado: {data}"

    notif = data.get("notification") or {}
    assert notif.get("dispatched") is True, f"dispatch no ocurrió: {notif}"
    assert notif.get("sent_count", 0) >= 1, f"sent_count debe ser >=1: {notif}"

    # Verificar email_log
    time.sleep(2)
    log = asyncio.run(_get_last_email_log("integration_project_closed"))
    assert log is not None, "No hay email_log de integration_project_closed"
    attach_names = log.get("attachment_names") or log.get("attachments") or []
    if isinstance(attach_names, list):
        joined = " ".join([str(x) for x in attach_names])
    else:
        joined = str(attach_names)
    assert "Certificado_" in joined, f"attachment_names no incluye Certificado_: {log}"


# ============ (C) FALLBACK sin plantilla — se envía con body genérico y adjunto ============
def test_30_fallback_without_template(headers):
    # Re-seed qa_cert (fue cerrado en test_20)
    asyncio.run(_reseed_qa_cert())

    # Configurar destinatario SIN template_id
    body = {
        "action_id": "integration_project_closed",
        "enabled": True,
        "recipients": [
            {
                "row_id": "r1",
                "type": "integrator_user",
                "template_id": "",
                "delivery_channel": "email",
            }
        ],
    }
    r = requests.put(f"{API}/other-actions/configs", json=body, headers=headers, timeout=20)
    assert r.status_code in (200, 201), r.text

    # Cerrar de nuevo
    files = [("componente", (None, "Plugin QA")), ("version_componente", (None, "v1.0"))]
    r = requests.post(f"{API}/integrators/qa_cert/close", files=files, headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("certificate_generated") is True

    notif = data.get("notification") or {}
    assert notif.get("dispatched") is True
    assert notif.get("sent_count", 0) >= 1, f"FALLBACK sin plantilla debería enviar. notif={notif}"
    # skipped debe ser vacío (o al menos NO contener 'Plantilla no encontrada')
    skipped = notif.get("skipped") or []
    reasons = " ".join([str(s.get("reason", "")) for s in skipped])
    assert "Plantilla" not in reasons, f"Aún hay skip por plantilla: {skipped}"

    time.sleep(2)
    log = asyncio.run(_get_last_email_log("integration_project_closed"))
    assert log is not None
    attach_names = log.get("attachment_names") or log.get("attachments") or []
    joined = " ".join([str(x) for x in attach_names]) if isinstance(attach_names, list) else str(attach_names)
    assert "Certificado_" in joined, f"Adjunto ausente en FALLBACK: {log}"


# ============ (D) Cleanup: eliminar depósito ============
def test_99_delete_certificate_deposit(headers):
    r = requests.delete(f"{API}/integrators/config/certificate", headers=headers, timeout=20)
    assert r.status_code == 200
