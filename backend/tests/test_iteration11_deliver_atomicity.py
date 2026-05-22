"""Test atomicidad de /quotes/{id}/deliver:
Cuando un item del payload falla validación, NINGÚN movimiento debe haberse insertado.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone

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


def test_deliver_atomic_pre_validation():
    """Si el item 2 falla validación de seriales, el item 1 NO debe quedar descontado."""
    from routes.quote_actions import deliver_quote
    import routes.quote_actions as qa
    from fastapi import HTTPException

    suffix = uuid.uuid4().hex[:8]
    quote_id = f"qt_atom_{suffix}"
    wh_id = f"wh_atom_{suffix}"
    item1_id = f"hw1_atom_{suffix}"
    item2_id = f"hw2_atom_{suffix}"

    async def runner():
        # Setup almacén
        await db.warehouses.insert_one({"warehouse_id": wh_id, "name": "Test WH Atomic", "sede": "PYME"})
        # Setup hardware (item1 = no serializado, item2 = serializado)
        await db.hardware.insert_one({"hardware_id": item1_id, "name": "Cable USB", "type": "Accesorio"})
        await db.hardware.insert_one({"hardware_id": item2_id, "name": "Pinpad X1000", "type": "Pinpad"})
        # Entradas iniciales: 5 de item1, 3 de item2 con seriales
        now = datetime.now(timezone.utc).isoformat()
        await db.inventory_movements.insert_one({
            "movement_id": f"mov_e1_{suffix}", "warehouse_id": wh_id, "item_id": item1_id,
            "item_name": "Cable USB", "item_type": "Accesorio",
            "movement_type": "entrada", "quantity": 5, "unit_cost": 1.0, "serials": [],
            "created_at": now, "created_by": "test",
        })
        await db.inventory_movements.insert_one({
            "movement_id": f"mov_e2_{suffix}", "warehouse_id": wh_id, "item_id": item2_id,
            "item_name": "Pinpad X1000", "item_type": "Pinpad",
            "movement_type": "entrada", "quantity": 3, "unit_cost": 100.0,
            "serials": ["SER-A001", "SER-A002", "SER-A003"],
            "created_at": now, "created_by": "test",
        })
        # Cotización equipment Pagada (regular flow)
        await db.quotes.insert_one({
            "quote_id": quote_id, "quote_number": "COT-ATOM-001",
            "quote_category": "equipment", "quote_status": "Pagada",
            "client_id": "cli_atom", "client_name": "Test Atom",
            "equipment_items": [
                {"hardware_id": item1_id, "name": "Cable USB", "hardware_type": "Accesorio", "quantity": 2},
                {"hardware_id": item2_id, "name": "Pinpad X1000", "hardware_type": "Pinpad", "quantity": 2},
            ],
        })

        # Mock get_current_user
        orig = qa.get_current_user

        async def _stub(_auth):
            return {"user_id": "u_test", "email": "test@test.com", "first_name": "Test", "last_name": "User"}

        qa.get_current_user = _stub

        try:
            # Payload con item 1 válido y item 2 con seriales INVÁLIDOS
            body = {
                "warehouse_id": wh_id,
                "delivery_items": [
                    {"hardware_id": item1_id, "quantity": 2, "serials": []},
                    {"hardware_id": item2_id, "quantity": 2, "serials": ["SER-FAKE-999", "SER-FAKE-998"]},
                ],
                "delivery_method": "personalizada",
                "receiver_name": "Juan Test",
                "invoice_number": "FAC-001",
                "notes": "",
            }
            raised = False
            try:
                await deliver_quote(quote_id, body, authorization="Bearer dummy")
            except HTTPException as e:
                raised = True
                assert e.status_code == 400, f"Esperado 400, got {e.status_code}"
                assert "no disponible" in (e.detail or "").lower() or "serial" in (e.detail or "").lower()

            assert raised, "Se esperaba HTTPException por seriales inválidos"

            # CRÍTICO: verificar que NINGÚN movimiento de salida se haya creado
            salidas = await db.inventory_movements.count_documents({
                "warehouse_id": wh_id, "movement_type": "salida",
            })
            assert salidas == 0, f"Se esperaba 0 salidas tras validación fallida, hay {salidas}"

            # Quote no debe haber cambiado a Entregada
            q = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
            assert q.get("quote_status") == "Pagada", f"Quote no debe avanzar: {q.get('quote_status')}"
            assert not q.get("delivered_at"), "delivered_at debe estar vacío"
        finally:
            qa.get_current_user = orig
            await db.warehouses.delete_one({"warehouse_id": wh_id})
            await db.hardware.delete_many({"hardware_id": {"$in": [item1_id, item2_id]}})
            await db.inventory_movements.delete_many({"warehouse_id": wh_id})
            await db.quotes.delete_one({"quote_id": quote_id})

    _run(runner())


def test_delivery_prep_requires_serial_uses_catalog():
    """delivery-prep debe leer requires_serial del catálogo, no del snapshot."""
    from routes.quote_actions import delivery_preparation
    import routes.quote_actions as qa

    suffix = uuid.uuid4().hex[:8]
    quote_id = f"qt_dp_{suffix}"
    item_id = f"hw_dp_{suffix}"

    async def runner():
        # Catálogo: tipo Pinpad (serializado)
        await db.hardware.insert_one({"hardware_id": item_id, "name": "Pinpad Y", "type": "Pinpad"})
        # Cotización con snapshot ERRÓNEO (hardware_type vacío)
        await db.quotes.insert_one({
            "quote_id": quote_id, "quote_number": "COT-DP-001",
            "quote_category": "equipment", "quote_status": "Aprobada",
            "client_id": "cli_dp", "client_name": "Test DP",
            "equipment_items": [
                {"hardware_id": item_id, "name": "Pinpad Y", "hardware_type": "", "quantity": 1},
            ],
        })

        orig = qa.get_current_user

        async def _stub(_auth):
            return {"user_id": "u_test", "email": "test@test.com"}

        qa.get_current_user = _stub
        try:
            res = await delivery_preparation(quote_id, warehouse_id=None, authorization="Bearer dummy")
            items = res.get("items", [])
            assert len(items) == 1
            # A pesar del snapshot vacío, debe detectar requires_serial=True del catálogo
            assert items[0]["requires_serial"] is True, f"requires_serial mal: {items[0]}"
            assert items[0]["hardware_type"] == "Pinpad"
        finally:
            qa.get_current_user = orig
            await db.hardware.delete_one({"hardware_id": item_id})
            await db.quotes.delete_one({"quote_id": quote_id})

    _run(runner())
