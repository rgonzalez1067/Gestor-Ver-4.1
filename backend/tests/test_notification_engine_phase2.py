# ruff: noqa
"""Phase 2 — Motor Dinámico de Notificaciones.

Tests para validar:
  1. Sin config → engine.try_dispatch retorna False (caller debe usar legacy).
  2. Con config válida → engine despacha emails y retorna True.
  3. Config con `client_field` y cliente sin email → validate retorna warning.
  4. _quote_to_biz_sub mapea correctamente las cotizaciones.
  5. Bitácora se registra al despachar.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')


async def _run():
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]

    from services.notification_engine import (
        try_dispatch,
        validate_client_email_required,
        has_config,
        _quote_to_biz_sub,
    )

    # -------- 1. Mapping helper --------
    q_eq = {"quote_category": "equipment"}
    assert _quote_to_biz_sub(q_eq) == ("equipos", None), "equipos sin sub"

    q_rep = {"quote_category": "repair"}
    assert _quote_to_biz_sub(q_rep) == ("reparaciones", None), "reparaciones sin sub"

    q_pyme_vpos = {"quote_category": "implementation", "quote_type": "VPOS", "sede": "PYME"}
    assert _quote_to_biz_sub(q_pyme_vpos) == ("implementacion_pyme", "vpos")

    q_corp_pg = {"quote_category": "implementation", "quote_type": "GATEWAY", "sede": "CORP"}
    assert _quote_to_biz_sub(q_corp_pg) == ("implementacion_corp", "payment_gateway")

    q_pyme_mpos_pos = {"quote_category": "implementation", "quote_type": "MPOS", "sub_quote_type": "IMPLE_POS", "sede": "PYME"}
    assert _quote_to_biz_sub(q_pyme_mpos_pos) == ("implementacion_pyme", "mpos_imple_pos")

    q_pyme_mpos_tablet = {"quote_category": "implementation", "quote_type": "MPOS", "sede": "PYME"}
    assert _quote_to_biz_sub(q_pyme_mpos_tablet) == ("implementacion_pyme", "mpos_tablet")

    print("[OK] _quote_to_biz_sub mapping → 5/5 passed")

    # -------- 2. Sin config → try_dispatch False (fallback legacy) --------
    test_quote = {
        "quote_id": f"quote_test_{uuid.uuid4().hex[:8]}",
        "quote_number": "TEST-PHASE2-001",
        "quote_category": "equipment",
        "client_id": "non_existent",
        "client_name": "Test SRL",
        "client_email": "qa@test.local",
        "total_usd": 100.0,
    }
    user = {"email": "tester@megasoft.com.ve", "first_name": "QA", "last_name": "Bot"}

    # Asegurarnos de que NO existe config para esta acción
    await db.action_notification_configs.delete_many({"config_key": "equipos|_|approve"})
    await db.action_notification_configs.delete_many({"config_key": "equipos|_|test_action"})

    dispatched = await try_dispatch("test_action", test_quote, user)
    assert dispatched is False, "Sin config debe retornar False"
    print("[OK] Sin config → try_dispatch False (fallback legacy)")

    # -------- 3. has_config con/sin --------
    assert (await has_config("test_action", test_quote)) is False
    print("[OK] has_config sin config → False")

    # -------- 4. Crear config con user válido + plantilla → despacho exitoso --------
    # Buscar 1 user activo con email
    user_doc = await db.users.find_one({"is_active": True, "email": {"$exists": True, "$ne": ""}}, {"_id": 0, "user_id": 1, "email": 1})
    assert user_doc, "No hay usuarios activos para testear"
    user_id = user_doc["user_id"]

    # Buscar 1 plantilla
    tpl_doc = await db.email_templates.find_one({}, {"_id": 0, "template_id": 1})
    assert tpl_doc, "No hay plantillas para testear"
    tpl_id = tpl_doc["template_id"]

    config_key = "equipos|_|test_action"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.action_notification_configs.update_one(
        {"config_key": config_key},
        {"$set": {
            "config_key": config_key,
            "business_type": "equipos",
            "product_subcategory": None,
            "action_id": "test_action",
            "recipients": [
                {"row_id": "row_test1", "type": "user", "user_id": user_id,
                 "template_id": tpl_id, "send_pdf_attachments": False},
            ],
            "updated_at": now_iso,
        }},
        upsert=True,
    )

    # Limpiar bitácora previa para este test
    await db.bitacora.delete_many({"action": "notification_engine_dispatch", "config_key": config_key})

    dispatched = await try_dispatch("test_action", test_quote, user, custom_message="Test mensaje")
    assert dispatched is True, "Con config válida debe retornar True"
    print("[OK] Con config válida → try_dispatch True")

    # has_config tras crear
    assert (await has_config("test_action", test_quote)) is True
    print("[OK] has_config con config → True")

    # Bitácora: debe haber 1 entrada
    bita_count = await db.bitacora.count_documents({
        "action": "notification_engine_dispatch",
        "config_key": config_key,
    })
    assert bita_count == 1, f"Bitácora esperada=1, obtenida={bita_count}"
    print("[OK] Bitácora registrada (1 entrada)")

    # -------- 5. validate_client_email_required --------
    # Crear config con client_field
    cfg_key2 = "equipos|_|test_action_client"
    await db.action_notification_configs.update_one(
        {"config_key": cfg_key2},
        {"$set": {
            "config_key": cfg_key2,
            "business_type": "equipos",
            "product_subcategory": None,
            "action_id": "test_action_client",
            "recipients": [
                {"row_id": "row_cf", "type": "client_field", "user_id": None,
                 "template_id": tpl_id, "send_pdf_attachments": True},
            ],
            "updated_at": now_iso,
        }},
        upsert=True,
    )

    # Quote SIN client_email
    quote_no_email = {
        "quote_id": "qne_test",
        "quote_number": "QNE-001",
        "quote_category": "equipment",
        "client_id": "missing_client_xyz",
        "client_name": "Client Sin Email",
        "total_usd": 50.0,
    }
    warn = await validate_client_email_required("test_action_client", quote_no_email)
    assert warn is not None and "email" in warn.lower(), f"Esperado warning, got: {warn}"
    print("[OK] validate_client_email_required (cliente sin email) → warning generado")

    # Quote CON client_email
    quote_with_email = {**quote_no_email, "client_email": "qa@test.local"}
    warn2 = await validate_client_email_required("test_action_client", quote_with_email)
    assert warn2 is None, f"Esperado None, got: {warn2}"
    print("[OK] validate_client_email_required (cliente con email) → None")

    # -------- Cleanup --------
    await db.action_notification_configs.delete_many({"config_key": {"$in": [config_key, cfg_key2]}})
    await db.bitacora.delete_many({"action": "notification_engine_dispatch", "config_key": {"$in": [config_key, cfg_key2]}})

    c.close()


def test_notification_engine_phase2():
    asyncio.run(_run())


if __name__ == "__main__":
    test_notification_engine_phase2()
    print("\nALL PHASE 2 TESTS PASSED")
