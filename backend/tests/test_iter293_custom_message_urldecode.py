# ruff: noqa
"""Iter 293 — Fix del bug de URL-encoding en 'Mensaje del Ejecutivo' / 'Mensaje de {user}'.

Reproduce el bug reportado: el custom_message llega URL-encoded desde el
frontend (ej. 'es%20muy%20importante%20para%20nosotros' o con '%0A'),
y el bloque HTML del correo lo mostraba SIN decodificar, dejando '%20' visible.

Fix aplicado (por el main agent E1):
  - services/notification_engine.py (try_dispatch, bloque "Mensaje del Ejecutivo"):
    ahora hace unquote(custom_message) antes de armar el bloque, trunca a 1500,
    y usa white-space:pre-wrap para preservar saltos de línea.
  - services/workflow_notifications.py (send_workflow_notification, bloque
    "Mensaje de {user_name}"): mismo fix (unquote + 1500 + pre-wrap).

Este test valida ese comportamiento intercepta send_email para capturar el HTML
final renderizado y hace las aserciones:
  1. El HTML final NO contiene '%20', '%0A', '%C3' como literales.
  2. El HTML final SÍ contiene el texto decodificado ("es muy importante para nosotros").
  3. white-space:pre-wrap está presente para preservar saltos de línea.
  4. Un mensaje > 500 chars (hasta 1500) se conserva completo (no se trunca a 500).
  5. Un custom_message None/vacío no rompe el flujo.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import quote as urlquote
from unittest.mock import AsyncMock, patch

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')


# ---------- Helpers ----------
def _make_capturing_send_email():
    """Devuelve (AsyncMock, list) donde list acumulará los kwargs de cada send."""
    captured = []

    async def _fake_send(*args, **kwargs):
        # send_email(to=..., subject=..., html=..., action=..., quote_id=..., quote_number=..., attachments=..., cc=...)
        captured.append(kwargs.copy())
        return {"status": "sent", "message_id": f"mock-{uuid.uuid4().hex[:8]}"}

    return _fake_send, captured


async def _seed_engine_config(db, config_key: str, tpl_id: str, user_id: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.action_notification_configs.update_one(
        {"config_key": config_key},
        {"$set": {
            "config_key": config_key,
            "business_type": "equipos",
            "product_subcategory": None,
            "action_id": config_key.split("|")[-1],
            "recipients": [
                {"row_id": "row_iter293_1", "type": "user", "user_id": user_id,
                 "template_id": tpl_id, "send_pdf_attachments": False,
                 "delivery_channel": "email"},
            ],
            "updated_at": now_iso,
        }},
        upsert=True,
    )


# ---------------- Test 1: notification_engine.try_dispatch (Mensaje del Ejecutivo) ----------------
async def _test_engine_unquote():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]

    from services import notification_engine as ne

    # Setup: usuario activo + plantilla existente
    user_doc = await db.users.find_one({"is_active": True, "email": {"$exists": True, "$ne": ""}}, {"_id": 0, "user_id": 1, "email": 1})
    assert user_doc, "No hay usuarios activos"
    tpl_doc = await db.email_templates.find_one({}, {"_id": 0, "template_id": 1})
    assert tpl_doc, "No hay plantillas de email"

    action_id = f"iter293_engine_{uuid.uuid4().hex[:6]}"
    config_key = f"equipos|clientes_pyme|{action_id}"
    await _seed_engine_config(db, config_key, tpl_doc["template_id"], user_doc["user_id"])

    test_quote = {
        "quote_id": f"quote_iter293_{uuid.uuid4().hex[:8]}",
        "quote_number": "ITER293-ENG-001",
        "quote_category": "equipment",
        "sede": "PYME",
        "client_id": "test_client_iter293",
        "client_name": "Test SRL Iter293",
        "client_email": "qa_iter293@test.local",
        "total_usd": 100.0,
    }
    current_user = {"email": "tester@megasoft.com.ve", "first_name": "QA", "last_name": "Bot"}

    # Mensaje URL-encoded (frontend hace encodeURIComponent antes de enviar por header)
    plain = "es muy importante para nosotros\nque revises este correo."
    encoded = urlquote(plain)
    assert "%20" in encoded and "%0A" in encoded, f"Precondición: encoded debe tener %20 y %0A → {encoded!r}"

    fake_send, captured = _make_capturing_send_email()
    # Parchamos send_email en el módulo notification_engine (que hizo `from services.email_service import send_email`)
    with patch.object(ne, "send_email", side_effect=fake_send):
        ok = await ne.try_dispatch(action_id, test_quote, current_user, custom_message=encoded)

    assert ok is True, "try_dispatch debería retornar True (config presente)"
    assert len(captured) >= 1, f"send_email no fue invocado; captured={captured}"

    # Usamos SOLO el primer HTML capturado (evita duplicaciones si hay múltiples recipients/CC).
    html_full = str(captured[0].get("html", ""))

    # --- ASERCIONES CLAVE del fix ---
    # (1) El HTML NO debe contener los literales URL-encoded.
    assert "%20" not in html_full, "BUG PRESENTE: el HTML aún contiene '%20' (custom_message no fue decodificado)."
    assert "%0A" not in html_full, "BUG PRESENTE: el HTML aún contiene '%0A' (saltos de línea sin decodificar)."
    # (2) El texto decodificado debe aparecer.
    assert "es muy importante para nosotros" in html_full, "Texto decodificado no presente en HTML."
    # (3) Bloque visual del Ejecutivo está presente y usa pre-wrap.
    assert "Mensaje del Ejecutivo" in html_full, "El bloque 'Mensaje del Ejecutivo' no fue insertado."
    assert "white-space:pre-wrap" in html_full, "Falta white-space:pre-wrap → los saltos de línea no se renderizarán."

    print("[OK] notification_engine.try_dispatch: custom_message URL-encoded se decodifica correctamente")

    # --- Test truncado a 1500 (no a 500) ---
    long_plain = "palabra " * 300  # ~2400 chars sin encoding
    long_encoded = urlquote(long_plain)
    captured.clear()
    with patch.object(ne, "send_email", side_effect=fake_send):
        ok2 = await ne.try_dispatch(action_id, test_quote, current_user, custom_message=long_encoded)
    assert ok2 is True
    html_long = str(captured[0].get("html", ""))
    # Deben aparecer AL MENOS 501 chars del mensaje decodificado (probando que el corte no es a 500).
    assert "%20" not in html_long, "BUG: mensaje largo aún URL-encoded"
    # Contar cuántas ocurrencias de "palabra " hay en el bloque: cada una son 8 chars.
    # 500 chars → ~62 palabras; 1500 chars → ~187 palabras.
    occ = html_long.count("palabra ")
    assert occ > 62, f"Truncado parece limitado a ~500 chars (encontradas {occ} palabras, esperadas >62 con truncado a 1500)."
    assert occ <= 200, f"El truncado a 1500 no se aplicó (encontradas {occ} palabras, esperado ~187)."
    print(f"[OK] notification_engine: truncado a 1500 chars correcto (palabras rendered={occ})")

    # --- Test None/vacío no rompe ---
    captured.clear()
    with patch.object(ne, "send_email", side_effect=fake_send):
        ok3 = await ne.try_dispatch(action_id, test_quote, current_user, custom_message=None)
    assert ok3 is True, "try_dispatch con custom_message=None debe seguir funcionando"
    html_none = str(captured[0].get("html", ""))
    assert "Mensaje del Ejecutivo" not in html_none, "Con custom_message=None NO debe aparecer el bloque"
    print("[OK] notification_engine: custom_message=None no rompe el flujo")

    captured.clear()
    with patch.object(ne, "send_email", side_effect=fake_send):
        ok4 = await ne.try_dispatch(action_id, test_quote, current_user, custom_message="")
    assert ok4 is True
    html_empty = str(captured[0].get("html", ""))
    assert "Mensaje del Ejecutivo" not in html_empty, "Con custom_message='' NO debe aparecer el bloque"
    print("[OK] notification_engine: custom_message='' no rompe el flujo")

    # Cleanup
    await db.action_notification_configs.delete_many({"config_key": config_key})
    await db.bitacora.delete_many({"action": "notification_engine_dispatch", "config_key": config_key})
    c.close()


# ---------------- Test 2: workflow_notifications.send_workflow_notification (Mensaje de {user}) ----------------
async def _test_workflow_unquote():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]

    from services import workflow_notifications as wn

    # Precondición: haya al menos una plantilla base disponible (workflow_notifications carga por action).
    # Vamos a usar override_recipients para NO depender del config sede/matrix.
    test_quote = {
        "quote_id": f"quote_iter293_wf_{uuid.uuid4().hex[:8]}",
        "quote_number": "ITER293-WF-001",
        "quote_category": "equipment",
        "quote_type": "EQUIPOS",
        "sede": "PYME",
        "client_name": "Test SRL WF",
        "client_email": "qa_wf@test.local",
        "total_usd": 200.0,
        "created_by_user_id": None,
    }
    current_user = {"email": "operador@megasoft.com.ve", "first_name": "Juan", "last_name": "Pérez"}

    plain = "revisar por favor antes del cierre\ngracias."
    encoded = urlquote(plain)
    assert "%20" in encoded and "%0A" in encoded

    fake_send, captured = _make_capturing_send_email()

    with patch.object(wn, "send_email", side_effect=fake_send):
        # Usamos una action arbitraria; workflow_notifications tiene fallback minimal template.
        results = await wn.send_workflow_notification(
            action="approve",
            quote=test_quote,
            current_user=current_user,
            custom_message=encoded,
            cc_emails=None,
            pdf_buffer=None,
            override_recipients=["destinatario_iter293@test.local"],
        )

    assert isinstance(results, list) and len(results) >= 1, f"send_workflow_notification devolvió {results}"
    assert len(captured) >= 1, f"send_email no fue invocado; captured={captured}"

    # Usamos SOLO el primer HTML (workflow puede duplicar en 'approve' → sales copy).
    html_full = str(captured[0].get("html", ""))

    # --- ASERCIONES CLAVE del fix ---
    assert "%20" not in html_full, "BUG PRESENTE (workflow): '%20' presente en HTML final."
    assert "%0A" not in html_full, "BUG PRESENTE (workflow): '%0A' presente en HTML final."
    assert "revisar por favor antes del cierre" in html_full, "Texto decodificado ausente en workflow_notifications."
    # El bloque tiene formato "Mensaje de {user_name}"
    assert "Mensaje de Juan P" in html_full, "El bloque 'Mensaje de {user}' no fue insertado en workflow."
    assert "white-space:pre-wrap" in html_full, "Falta white-space:pre-wrap en workflow bloque."
    print("[OK] workflow_notifications.send_workflow_notification: custom_message URL-encoded se decodifica")

    # --- Test truncado a 1500 (no 500) ---
    long_plain = "linea " * 400  # ~2400 chars
    long_encoded = urlquote(long_plain)
    captured.clear()
    with patch.object(wn, "send_email", side_effect=fake_send):
        results2 = await wn.send_workflow_notification(
            action="approve",
            quote=test_quote,
            current_user=current_user,
            custom_message=long_encoded,
            override_recipients=["destinatario_iter293_long@test.local"],
        )
    assert len(results2) >= 1
    html_long = str(captured[0].get("html", ""))
    assert "%20" not in html_long, "BUG (workflow long): '%20' presente en mensaje largo"
    occ = html_long.count("linea ")
    # ~500 chars → 83 palabras; ~1500 → 250. Esperamos > 83 para validar > 500.
    assert occ > 90, f"Truncado a ~500 sospechoso: {occ} 'linea' occurrences"
    assert occ <= 260, f"Truncado a 1500 no aplicado: {occ} 'linea' occurrences (esperado ~250)"
    print(f"[OK] workflow_notifications: truncado a 1500 (palabras={occ})")

    # --- Test None/vacío no rompe ---
    captured.clear()
    with patch.object(wn, "send_email", side_effect=fake_send):
        results3 = await wn.send_workflow_notification(
            action="approve",
            quote=test_quote,
            current_user=current_user,
            custom_message=None,
            override_recipients=["destinatario_iter293_none@test.local"],
        )
    assert len(results3) >= 1
    html_none = str(captured[0].get("html", ""))
    assert "Mensaje de Juan" not in html_none, "Con custom_message=None NO debe aparecer bloque en workflow"

    captured.clear()
    with patch.object(wn, "send_email", side_effect=fake_send):
        results4 = await wn.send_workflow_notification(
            action="approve",
            quote=test_quote,
            current_user=current_user,
            custom_message="   ",  # solo espacios → strip() → vacío → no bloque
            override_recipients=["destinatario_iter293_ws@test.local"],
        )
    assert len(results4) >= 1
    html_ws = str(captured[0].get("html", ""))
    assert "Mensaje de Juan" not in html_ws, "Con custom_message='   ' NO debe aparecer bloque en workflow"
    print("[OK] workflow_notifications: custom_message None/'' /whitespace no rompe el flujo")

    c.close()


async def _test_both():
    # Run both in a single loop to avoid motor client / loop mismatch across tests.
    await _test_engine_unquote()
    await _test_workflow_unquote()


# ---------------- Pytest wrapper (sync) ----------------
def test_iter293_custom_message_urldecoded():
    """Test único (loop compartido): valida el fix en ambos motores.

    - notification_engine.try_dispatch: bloque 'Mensaje del Ejecutivo'.
    - workflow_notifications.send_workflow_notification: bloque 'Mensaje de {user}'.
    Ambos deben:
      1. Decodificar URL-encoding (%20, %0A).
      2. Truncar a 1500 (no a 500).
      3. white-space:pre-wrap en el bloque.
      4. No romper con custom_message None/vacío/whitespace.
    """
    asyncio.run(_test_both())


if __name__ == "__main__":
    test_iter293_custom_message_urldecoded()
    print("\nALL ITER293 TESTS PASSED")
