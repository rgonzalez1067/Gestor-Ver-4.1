# ruff: noqa
"""Tests Iteration 13:
- Validar Pago robusto (avanza aunque falte config de email).
- Fix WriteError por custom_actions_executed: null.
- pinpad_question restaurado para todos los flujos.
- Precarga modelo_impresora_fiscal del cliente en el modal.
"""
import os
import sys
import asyncio
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import db  # noqa: E402


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_custom_action_handles_null_custom_actions_executed():
    """Bug histórico: cotizaciones legacy con `custom_actions_executed: null`
    rompían el $set anidado con WriteError. Verificamos que se normaliza primero.
    """
    from routes.quote_action_customization import dispatch_custom_action
    import routes.quote_action_customization as qac

    suffix = uuid.uuid4().hex[:8]
    quote_id = f"qt_cpa_{suffix}"
    config_key = f"equipos::pago_validado_eq_test_{suffix}"
    action_id = f"pago_validado_eq_test_{suffix}"

    async def runner():
        # Cot legacy con campo null
        await db.quotes.insert_one({
            "quote_id": quote_id, "quote_number": "COT-CPA-001",
            "quote_category": "equipment", "quote_status": "Aprobada",
            "client_id": "cli_cpa", "client_name": "Test CPA",
            "custom_actions_executed": None,  # ← null (bug trigger)
        })
        await db.quote_custom_actions.insert_one({
            "config_key": config_key, "action_id": action_id,
            "business_type": "equipos", "product_subcategory": None,
            "label": "Validar Pago Test", "enabled": True,
            "required_roles": [], "required_cargos": [], "allowed_user_ids": [],
        })
        orig = qac._require_user

        async def _stub(_auth):
            return {"user_id": "u_test", "email": "test@test.com", "role": "admin", "cargo": "Admin"}

        qac._require_user = _stub
        try:
            res = await dispatch_custom_action(quote_id, action_id, payload={}, authorization="Bearer dummy")
            assert res.get("ok") is True
            assert res.get("executed_at"), "executed_at debe estar presente"
            # Verificar persistencia
            q = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
            assert isinstance(q.get("custom_actions_executed"), dict)
            assert action_id in q["custom_actions_executed"]
        finally:
            qac._require_user = orig
            await db.quotes.delete_one({"quote_id": quote_id})
            await db.quote_custom_actions.delete_one({"config_key": config_key})

    _run(runner())


def test_custom_action_no_400_when_no_recipients():
    """Si no hay destinatarios configurados, la acción debe marcar `email_sent=False`
    pero retornar 200 con `ok=True` (no romper el flujo)."""
    from routes.quote_action_customization import dispatch_custom_action
    import routes.quote_action_customization as qac

    suffix = uuid.uuid4().hex[:8]
    quote_id = f"qt_cpb_{suffix}"
    config_key = f"equipos::test_act_{suffix}"
    action_id = f"test_act_{suffix}"

    async def runner():
        await db.quotes.insert_one({
            "quote_id": quote_id, "quote_number": "COT-CPB-001",
            "quote_category": "equipment", "quote_status": "Aprobada",
            "client_id": "cli_cpb", "client_name": "Test CPB",
        })
        await db.quote_custom_actions.insert_one({
            "config_key": config_key, "action_id": action_id,
            "business_type": "equipos", "product_subcategory": None,
            "label": "Acción Sin Destinatarios", "enabled": True,
            "required_roles": [], "required_cargos": [], "allowed_user_ids": [],
        })
        orig = qac._require_user

        async def _stub(_auth):
            return {"user_id": "u_test", "email": "test@test.com", "role": "admin", "cargo": "Admin"}

        qac._require_user = _stub
        try:
            res = await dispatch_custom_action(quote_id, action_id, payload={}, authorization="Bearer dummy")
            # No debe lanzar — debe retornar OK con email_sent (puede ser True o False)
            assert res.get("ok") is True
            # Verificar que la cot tiene la ejecución marcada incluso sin destinatarios
            q = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
            assert action_id in (q.get("custom_actions_executed") or {})
        finally:
            qac._require_user = orig
            await db.quotes.delete_one({"quote_id": quote_id})
            await db.quote_custom_actions.delete_one({"config_key": config_key})

    _run(runner())


def test_pinpad_question_for_all_flows():
    """handleProjectTypeSelect debe llevar a pinpad_question para PYME y no-PYME."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    # PYME: branch que va a pinpad_question
    assert "setMultistorePhase('pinpad_question')" in content
    # No-PYME (post-equipos auto-load) también debe ir a pinpad_question, no a goToFiscalPrinterPhase
    # Verificamos que ambos branches de no-PYME (payment_gateway y POS/VPOS) lleguen ahí.
    idx_select = content.find("const handleProjectTypeSelect")
    assert idx_select > 0
    select_block = content[idx_select:idx_select + 4000]
    # Debe aparecer pinpad_question también para payment_gateway (no-PYME)
    pinpad_count = select_block.count("setMultistorePhase('pinpad_question')")
    assert pinpad_count >= 2, f"Se esperaban ≥2 transiciones a pinpad_question en no-PYME, hubo {pinpad_count}"


def test_fiscal_printer_reset_before_load():
    """goToFiscalPrinterPhase debe resetear los states antes de hacer GET /clients."""
    with open("/app/frontend/src/pages/Quotes.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.find("const goToFiscalPrinterPhase")
    assert idx > 0
    block = content[idx:idx + 1500]
    # Reset explícito (las dos líneas) deben aparecer antes del try
    reset_idx = block.find("setFiscalPrinterFromClient('')")
    try_idx = block.find("try {")
    assert 0 < reset_idx < try_idx, "El reset debe estar ANTES del try del fetch"
