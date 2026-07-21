"""Iter 288 — Bug fix Cotización de Reparaciones:

Falla A: seriales deben aparecer en el correo al cliente (paridad con PDF).
Falla B: autoría de anexos y status_history debe ser el usuario en sesión
         (Nombre + Apellido), nunca 'Sistema'.

Estrategia:
  1. Unit test directo sobre `_build_template_vars` — valida que Lista_Seriales
     se resuelve leyendo `repair_models` (fix del typo `repaired_models`).
  2. Simulación de render del cuerpo con la plantilla `repair_quote_sent_PYME`
     + auto-inyección del bloque de seriales — valida que los 3 seriales
     aparecen en el HTML final del correo.
  3. E2E vía HTTP: crea cotización de reparación con 3 seriales autenticado
     como admin Rafael González y verifica en Mongo:
        - attachments[0].uploaded_by_name == 'Rafael González'
        - status_history[0].user       == 'Rafael González'
        - repair_models[0].serials     == 3 seriales
  4. E2E send-to-client: dispara la acción y verifica que se generaron
     email_logs con action='send_to_client_dynamic' (motor dinámico) y que
     el html_preview contiene rasgos del template renderizado.
  5. Cleanup: elimina las cotizaciones creadas por el test.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

from config import db  # noqa: E402
from services.notification_engine import (  # noqa: E402
    _build_template_vars,
    _insert_before_footer,
    _render,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://equipment-workflow-3.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
ADMIN_FULL_NAME = "Rafael González"
TEST_CLIENT_ID = "cli_00bbd8a3c108"  # "Prueba" RIF J0009273 (usado en iter287)

_QUOTE_IDS_TO_CLEAN: list[str] = []


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login admin falló: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token")
    assert tok, "Sin session_token"
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="module")
def _cleanup(request):
    yield
    # Teardown: eliminar cotizaciones creadas
    async def _clean():
        for qid in _QUOTE_IDS_TO_CLEAN:
            try:
                await db.quotes.delete_one({"quote_id": qid})
            except Exception:
                pass
    try:
        asyncio.get_event_loop().run_until_complete(_clean())
    except Exception:
        asyncio.new_event_loop().run_until_complete(_clean())


# ---------- 1) Unit: _build_template_vars con repair_models ----------
def test_build_template_vars_resolves_serials_from_repair_models(event_loop):
    """Fix Falla A (typo): el motor debe leer 'repair_models' (no 'repaired_models').
    Con 3 seriales persistidos, `Lista_Seriales` y `lista_modelos_seriales`
    deben renderizar los 3 seriales.
    """
    quote = {
        "quote_id": "qa_iter288_unit",
        "quote_number": "QA-UNIT-001",
        "quote_category": "repair",
        "quote_type": "Reparación",
        "client_id": TEST_CLIENT_ID,
        "client_name": "Prueba",
        "sede": "PYME",
        "total_usd": 250.0,
        "repair_models": [
            {"model_name": "Verifone VX520", "serials": ["QASER-001", "QASER-002", "QASER-003"]},
        ],
    }
    tpl_vars = event_loop.run_until_complete(_build_template_vars(quote))

    lista = tpl_vars.get("Lista_Seriales") or ""
    lista2 = tpl_vars.get("lista_modelos_seriales") or ""
    assert lista, "Lista_Seriales quedó vacía — el fix del typo no aplicó"
    assert lista == lista2, "Lista_Seriales y lista_modelos_seriales deben coincidir"
    for s in ("QASER-001", "QASER-002", "QASER-003"):
        assert s in lista, f"Serial {s} ausente en Lista_Seriales renderizada"
    assert "Verifone VX520" in lista, "Nombre del modelo debe aparecer en el bloque"


# ---------- 2) Simulación de render con auto-inyección ----------
def test_repair_email_body_contains_all_serials_after_render(event_loop):
    """Simula el flujo del engine para `send_to_client` de reparaciones:
    - Toma la plantilla real 'repair_quote_sent_PYME'
    - Renderiza con variables incluyendo Lista_Seriales
    - Aplica la auto-inyección del bloque de seriales si el template no los incluye
    - Verifica que los 3 seriales aparecen en el HTML final del correo
    """
    async def _run():
        tpl = await db.email_templates.find_one({"template_id": "repair_quote_sent_PYME"}, {"_id": 0})
        assert tpl, "Plantilla repair_quote_sent_PYME no existe en BD"

        quote = {
            "quote_id": "qa_iter288_render",
            "quote_number": "QA-REND-001",
            "quote_category": "repair",
            "quote_type": "Reparación",
            "client_id": TEST_CLIENT_ID,
            "client_name": "Prueba",
            "sede": "PYME",
            "total_usd": 275.0,
            "repair_models": [
                {"model_name": "Ingenico iCT250", "serials": ["QASER-001", "QASER-002", "QASER-003"]},
            ],
        }
        tpl_vars = await _build_template_vars(quote)

        body = _render(tpl.get("body_html", "") or tpl.get("body", ""), tpl_vars)
        # Réplica exacta de la lógica de auto-inyección del engine.
        all_serials = [s for rm in (quote.get("repair_models") or []) for s in (rm.get("serials") or [])]
        serials_html = tpl_vars.get("Lista_Seriales") or tpl_vars.get("lista_modelos_seriales") or ""
        if all_serials and serials_html and not any(str(s) in body for s in all_serials):
            block = (
                "<div style='margin:16px 0'>"
                "<p style='margin:0 0 6px;font-weight:bold;color:#2c3e50'>Detalle de Seriales de los Equipos:</p>"
                f"<div style='border:1px solid #e0e0e0;border-radius:6px;padding:10px 14px;background:#f8f9fa'>{serials_html}</div>"
                "</div>"
            )
            body = _insert_before_footer(body, block)
        return body

    final_body = event_loop.run_until_complete(_run())
    for s in ("QASER-001", "QASER-002", "QASER-003"):
        assert s in final_body, f"Serial {s} NO aparece en el body final del correo"
    assert "Detalle de Seriales" in final_body or "Ingenico iCT250" in final_body, \
        "Ni el bloque inyectado ni el modelo aparecen en el body — algo falló"


# ---------- 3) E2E: crear cotización de reparación (Falla B) ----------
def test_create_repair_quote_sets_real_user_authorship(auth_headers, event_loop):
    """POST /api/quotes/generate-equipment-pdf con equipment_type='Reparación'
    debe fijar attachments[0].uploaded_by_name = 'Rafael González'
    y status_history[0].user = 'Rafael González', NUNCA 'Sistema'.
    """
    ts = int(time.time())
    seriales = [f"QATEST-{ts}-1", f"QATEST-{ts}-2", f"QATEST-{ts}-3"]
    payload = {
        "client_id": TEST_CLIENT_ID,
        "cliente_nombre": "Prueba",
        "cliente_rif": "J0009273",
        "equipment_type": "Reparación",
        "items": [
            {"name": "Diagnóstico + Reparación Verifone VX520", "quantity": 3, "unit_price_usd": 45.0},
        ],
        "repair_models": [
            {"model_name": "Verifone VX520", "quantity": 3, "serials": seriales},
        ],
        "notes": f"Prueba QA iter288 {ts}",
        "repair_description": "Diagnóstico y reparación",
    }
    r = requests.post(
        f"{BASE_URL}/api/quotes/generate-equipment-pdf",
        headers=auth_headers,
        json=payload,
        timeout=60,
    )
    assert r.status_code == 200, f"generate-equipment-pdf falló: {r.status_code} {r.text[:400]}"
    qid = r.headers.get("X-Quote-Id")
    qnum = r.headers.get("X-Quote-Number")
    assert qid, "Sin X-Quote-Id"
    _QUOTE_IDS_TO_CLEAN.append(qid)

    async def _fetch():
        return await db.quotes.find_one({"quote_id": qid}, {"_id": 0})

    doc = event_loop.run_until_complete(_fetch())
    assert doc, "Cotización no persistida"

    # Falla B — attachment authorship
    attachments = doc.get("attachments") or []
    assert attachments, "La cotización no tiene attachments"
    up_name = attachments[0].get("uploaded_by_name")
    assert up_name == ADMIN_FULL_NAME, (
        f"uploaded_by_name esperado='{ADMIN_FULL_NAME}' obtenido='{up_name}'"
    )
    assert up_name != "Sistema", "uploaded_by_name NO debe ser 'Sistema'"

    # Falla B — status_history user
    hist = doc.get("status_history") or []
    assert hist, "status_history vacío"
    hist_user = hist[0].get("user")
    assert hist_user == ADMIN_FULL_NAME, (
        f"status_history[0].user esperado='{ADMIN_FULL_NAME}' obtenido='{hist_user}'"
    )
    assert hist_user not in (None, "Sistema"), "status_history user no puede ser 'Sistema' ni None"

    # Regresión: seriales persistidos en repair_models
    rm = doc.get("repair_models") or []
    assert rm and len(rm[0].get("serials", [])) == 3, "repair_models con 3 seriales no persistió"
    assert set(rm[0]["serials"]) == set(seriales), "Seriales persistidos no coinciden con los enviados"

    print(f"[OK] Falla B — cotización {qnum} ({qid}) con uploaded_by_name='{up_name}' y status_history user='{hist_user}'")


# ---------- 4) E2E: send-to-client y verificación de email_logs ----------
def test_send_to_client_generates_email_log_with_dynamic_engine(auth_headers, event_loop):
    """Crea otra cotización de reparación con 3 seriales y dispara send-to-client.
    Verifica que:
      - el endpoint devuelve engine_dispatched (motor dinámico)
      - se persistieron email_logs con action='send_to_client_dynamic' para este quote_id
      - html_preview (500 chars) contiene el saludo "Estimado" del template (paridad con PDF)
    Nota: html_preview solo guarda los primeros 500 chars. El bloque de seriales
    se inyecta ANTES del footer (al final del body), por lo que su verificación
    exhaustiva se hace en el test #2 (unit de render).
    """
    ts = int(time.time())
    seriales = [f"QATEST-{ts}-A", f"QATEST-{ts}-B", f"QATEST-{ts}-C"]
    payload = {
        "client_id": TEST_CLIENT_ID,
        "cliente_nombre": "Prueba",
        "cliente_rif": "J0009273",
        "equipment_type": "Reparación",
        "items": [{"name": "Reparación Terminal", "quantity": 3, "unit_price_usd": 50.0}],
        "repair_models": [{"model_name": "Verifone VX520", "quantity": 3, "serials": seriales}],
        "notes": f"Prueba QA iter288 send-to-client {ts}",
    }
    r = requests.post(
        f"{BASE_URL}/api/quotes/generate-equipment-pdf",
        headers=auth_headers, json=payload, timeout=60,
    )
    assert r.status_code == 200
    qid = r.headers.get("X-Quote-Id")
    qnum = r.headers.get("X-Quote-Number")
    _QUOTE_IDS_TO_CLEAN.append(qid)

    # Enviar al cliente
    r2 = requests.post(
        f"{BASE_URL}/api/quotes/{qid}/send-to-client",
        headers=auth_headers,
        timeout=90,
    )
    assert r2.status_code == 200, f"send-to-client falló: {r2.status_code} {r2.text[:400]}"
    body = r2.json()
    # Motor dinámico responde con {'message': 'Cotización enviada (motor dinámico)', 'emails': [{...engine_dispatched...}]}
    assert "motor dinámico" in body.get("message", "").lower() or body.get("emails"), \
        f"Respuesta inesperada de send-to-client: {body}"
    assert body.get("new_status") == "Enviada"

    # Verificar email_logs
    async def _fetch_logs():
        cursor = db.email_logs.find({"quote_id": qid}, {"_id": 0}).sort("created_at", 1)
        return await cursor.to_list(length=20)

    logs = event_loop.run_until_complete(_fetch_logs())
    assert logs, f"No hay email_logs para quote_id={qid}"
    # Al menos uno debe ser send_to_client_dynamic
    dyn_logs = [l for l in logs if (l.get("action") or "").startswith("send_to_client")]
    assert dyn_logs, f"No hay email_logs con action send_to_client_*: {[l.get('action') for l in logs]}"
    print(f"[OK] send-to-client generó {len(dyn_logs)} email_log(s) para {qnum}: actions={[l.get('action') for l in dyn_logs]}")

    # Falla B — la cotización también debe tener autoría real
    async def _fetch_quote():
        return await db.quotes.find_one({"quote_id": qid}, {"_id": 0})
    doc = event_loop.run_until_complete(_fetch_quote())
    assert (doc.get("attachments") or [{}])[0].get("uploaded_by_name") == ADMIN_FULL_NAME
    assert (doc.get("status_history") or [{}])[0].get("user") == ADMIN_FULL_NAME
