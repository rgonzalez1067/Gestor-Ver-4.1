# ruff: noqa
"""Iter264 — Fix: en el modal Aprobación de cotización, los archivos
`approval_files` (Orden de Compra / Soporte de Aprobación) ahora también se
adjuntan al correo de Administración (además de persistirse en quote.attachments
vía /attachments). Se agregó observabilidad en email_logs: attachment_count y
attachment_names.

Este test:
  1. Siembra una cotización desechable en estado 'Enviada' (implementation VPOS).
  2. Aprueba vía POST /api/quotes/{id}/approve con multipart:
     - `payload` (billing_instruction mínimo)
     - 2 archivos en `payment_files` (pago_1.pdf, pago_2.pdf)
     - 2 archivos en `approval_files` (orden_compra_1.pdf, orden_compra_2.pdf)
  3. Verifica en Mongo email_logs (action='approve', quote_id=...) que
     attachment_names contenga los 4 archivos cargados y los PDFs auto-generados
     (Cotización y Cálculos Definitivos) sin duplicaciones.
  4. Regresión: el endpoint separado /attachments sigue persistiendo
     approval_files en quote.attachments.
"""
import asyncio
import io
import json as _json
import os
import sys
import time

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')

API = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

# --------------- Utilidades ---------------

QUOTE_ID = "qid_iter264_multiatt"
CLIENT_ID = "cli_iter264_multiatt"


async def _seed():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    client = {
        "client_id": CLIENT_ID,
        "rif": "J888888888",
        "legal_name": "ITER264 CLIENTE TEST, C.A.",
        "fantasy_name": "ITER264 TEST",
        "address": "Av Test Piso 1 Caracas",
        "segment": "Pymes",
        "contacts": [{
            "full_name": "Ana Prueba",
            "email": "ana@iter264test.com",
            "phone": "+58 414 0000000",
        }],
    }
    await db.clients.update_one({"client_id": CLIENT_ID}, {"$set": client}, upsert=True)
    quote = {
        "quote_id": QUOTE_ID,
        "quote_number": "COT-ITER264-MULTIATT",
        "client_segment": "PYME",
        "sede": "PYME",
        "client_id": CLIENT_ID,
        "client_name": client["fantasy_name"],
        "client_rif": client["rif"],
        "quote_status": "Enviada",
        "quote_type": "VPOS",
        "quote_category": "implementation",
        "total_usd": 10, "total_bs": 400, "subtotal_usd": 10, "exchange_rate": 40.0,
        "services": [], "hardware": [],
        "archived": False,
        "attachments": [],
        "created_by_user_id": "test_creator_iter264",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    await db.quotes.update_one({"quote_id": QUOTE_ID}, {"$set": quote}, upsert=True)
    # limpiar email_logs previos de este quote
    await db.email_logs.delete_many({"quote_id": QUOTE_ID})


async def _cleanup():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    await db.clients.delete_many({"client_id": CLIENT_ID})
    await db.quotes.delete_many({"quote_id": QUOTE_ID})
    await db.email_logs.delete_many({"quote_id": QUOTE_ID})


async def _find_approve_email_log_admin():
    """Encuentra el email_log del correo enviado a Administración para approve.

    Filtra por action='approve' y quote_id, y devuelve el más reciente.
    Nota: existen múltiples email_logs por aprobación (Admin, Ventas, CC);
    todos comparten action='approve' y los mismos attachments; para efectos del
    test verificamos AL MENOS uno que contenga los 4 archivos + PDFs.
    """
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    cursor = db.email_logs.find(
        {"quote_id": QUOTE_ID, "action": {"$regex": "^approve"}},
        {"_id": 0},
    ).sort("created_at", -1).limit(20)
    return [d async for d in cursor]


def _login(email, pw):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return r.json()["session_token"]


def _payload_min():
    return {
        "consolidated_items": [
            {"name": "X", "quantity": 1, "unit_price_usd": 10, "total_usd": 10}
        ],
        "exchange_rate": 40,
        "grand_total_usd": 10,
        "grand_total_bs": 400,
        "iva_usd": 1.6, "iva_bs": 64,
        "grand_total_con_iva_usd": 11.6, "grand_total_con_iva_bs": 464,
    }


# --------------- Fixtures ---------------

@pytest.fixture(scope="module")
def token():
    asyncio.run(_seed())
    tok = _login("rgonzalez@megasoft.com.ve", "admin123")
    yield tok
    asyncio.run(_cleanup())


# --------------- Tests ---------------

def test_approve_multipart_with_4_files_reaches_email_log(token):
    """Aprueba con 2 payment_files + 2 approval_files. Verifica que TODOS los
    nombres (los 4 cargados) aparezcan en email_log.attachment_names de al menos
    un correo, y que se registre attachment_count > 0."""
    files = [
        ("payload", (None, _json.dumps(_payload_min()))),
        ("payment_files", ("pago_1.pdf", b"%PDF-1.4 fake pago 1", "application/pdf")),
        ("payment_files", ("pago_2.pdf", b"%PDF-1.4 fake pago 2", "application/pdf")),
        ("approval_files", ("orden_compra_1.pdf", b"%PDF-1.4 fake OC 1", "application/pdf")),
        ("approval_files", ("orden_compra_2.pdf", b"%PDF-1.4 fake OC 2", "application/pdf")),
    ]
    r = requests.post(
        f"{API}/api/quotes/{QUOTE_ID}/approve",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"approve debe ser 200 → got {r.status_code}: {r.text[:500]}"
    body = r.json()
    assert body.get("new_status") == "Aprobada"

    # Dar un poquito de tiempo por si el motor SMTP demora el logging
    time.sleep(1.0)

    logs = asyncio.run(_find_approve_email_log_admin())
    assert logs, f"No se encontraron email_logs para quote_id={QUOTE_ID}"

    # Buscar el log de Admin que contenga los 4 archivos cargados.
    expected_uploaded = {"pago_1.pdf", "pago_2.pdf", "orden_compra_1.pdf", "orden_compra_2.pdf"}
    matching = None
    for lg in logs:
        names = set(lg.get("attachment_names") or [])
        if expected_uploaded.issubset(names):
            matching = lg
            break

    # Diagnóstico si falla
    if not matching:
        dump = [{"action": lg.get("action"), "to": lg.get("to"),
                 "attachment_count": lg.get("attachment_count"),
                 "attachment_names": lg.get("attachment_names")} for lg in logs]
        pytest.fail(f"Ningún email_log incluyó los 4 archivos cargados. Vistos: {dump}")

    names = matching.get("attachment_names") or []
    count = matching.get("attachment_count") or 0

    # 1) Los 4 nombres cargados están presentes
    for n in ("pago_1.pdf", "pago_2.pdf", "orden_compra_1.pdf", "orden_compra_2.pdf"):
        assert n in names, f"attachment_names debe contener {n}, actual={names}"

    # 2) Al menos el PDF de "Cálculos Definitivos" está también adjunto
    calc = [n for n in names if "Calculos_Definitivos" in n or "Cálculos_Definitivos" in n]
    assert calc, f"Se esperaba al menos un PDF 'Calculos_Definitivos_*.pdf' auto-generado; names={names}"

    # 3) attachment_count coincide con len(attachment_names)
    assert count == len(names), f"attachment_count ({count}) != len(names) ({len(names)})"

    # 4) SIN duplicados (fix de la ruta legacy)
    from collections import Counter
    dupes = [n for n, c in Counter(names).items() if c > 1]
    # El logo inline "firma_logo" puede o no repetirse. Chequeamos los uploaded/PDF gen.
    tracked = [n for n in names if n in expected_uploaded or "Calculos_Definitivos" in n or "Cotizacion" in n or "Cálculos" in n]
    tracked_dupes = [n for n, c in Counter(tracked).items() if c > 1]
    assert not tracked_dupes, f"Hay adjuntos duplicados en attachment_names: {tracked_dupes} (all={names})"


def test_regression_approval_persistence_via_attachments_endpoint(token):
    """Regresión: /quotes/{id}/attachments sigue persistiendo el archivo de
    Orden de Compra (categoría 'Soporte de Aprobación') dentro de quote.attachments.
    """
    # Resetear la cotización a Enviada por si el test previo la cambió
    async def _reset():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        await db.quotes.update_one(
            {"quote_id": QUOTE_ID},
            {"$set": {"quote_status": "Enviada", "attachments": []}},
        )
    asyncio.run(_reset())

    files = {
        "file": ("orden_compra_reg.pdf", io.BytesIO(b"%PDF-1.4 OC persist"), "application/pdf"),
    }
    data = {"category": "Orden de Compra"}
    r = requests.post(
        f"{API}/api/quotes/{QUOTE_ID}/attachments",
        files=files,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (200, 201), f"upload attachment status={r.status_code} body={r.text[:400]}"

    async def _fetch():
        c = AsyncIOMotorClient(MONGO_URL)
        db = c[DB_NAME]
        return await db.quotes.find_one({"quote_id": QUOTE_ID}, {"_id": 0, "attachments": 1})
    q = asyncio.run(_fetch())
    atts = (q or {}).get("attachments") or []
    cats = [a.get("category") for a in atts]
    fnames = [a.get("filename") or a.get("name") for a in atts]
    assert "Orden de Compra" in cats, f"No persistió Orden de Compra; cats={cats}, atts={atts}"
    # El backend renombra archivos usando la plantilla {quote_number}_{Category}.{ext};
    # basta con validar que el nombre canonicalizado esté presente y no vacío.
    assert atts and any(fnames), f"No hay filename persistido en attachments; atts={atts}"
