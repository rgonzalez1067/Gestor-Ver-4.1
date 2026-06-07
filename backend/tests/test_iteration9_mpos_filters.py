# ruff: noqa
"""Tests para Iteration 9: Flujo MPOS estabilizado + filtros Validar Pago/Preasign.

Cubre:
1. _build_template_vars retorna `client_name` con legal_name primero (no fantasy_name).
2. inventory-serials antepone seriales preasignados para el mismo cliente.
3. PDF de Implementación usa banner 'SERIALES DE LOS EQUIPOS'.
4. send_to_implementation no marca irregular para fast_track en estados naturales.
"""
import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import db  # noqa: E402
from services.notification_engine import _build_template_vars  # noqa: E402


def _run(coro):
    """Helper para ejecutar coroutines reutilizando el event loop activo si existe."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def test_build_template_vars_client_name_uses_legal_name():
    """client_name debe priorizar legal_name (Razón Social) sobre fantasy_name."""
    client_id = f"cli_test_{uuid.uuid4().hex[:8]}"

    async def setup_and_test():
        await db.clients.insert_one({
            "client_id": client_id,
            "legal_name": "INVERSIONES PAGO AQUI 24/7, C.A.",
            "fantasy_name": "Astrocel Tienda Centro",
            "rif": "J-12345678-9",
            "address": "Av. Principal",
            "contacts": [{"full_name": "María Pérez", "email": "m@cli.com", "phone": "0212-555"}],
        })
        try:
            quote = {
                "quote_id": "qt_dummy",
                "quote_number": "COT-TEST-001",
                "client_id": client_id,
                "client_name": "",
                "client_rif": "",
                "total_usd": 100,
            }
            return await _build_template_vars(quote)
        finally:
            await db.clients.delete_one({"client_id": client_id})

    vars_ = _run(setup_and_test())
    assert vars_["client_name"] == "INVERSIONES PAGO AQUI 24/7, C.A."
    assert vars_["Nombre_Cliente"] == "INVERSIONES PAGO AQUI 24/7, C.A."
    assert vars_["Datos_Contacto"] == "María Pérez"
    assert vars_["Contacto_Principal"] == "María Pérez"


def test_inventory_serials_prioritizes_preassigned():
    """El endpoint inventory-serials debe retornar primero los seriales preasignados."""
    from routes.quote_serials import get_inventory_serials
    import routes.quote_serials as qs

    client_id = f"cli_inv_{uuid.uuid4().hex[:8]}"
    quote_id = f"qt_inv_{uuid.uuid4().hex[:8]}"
    item_id = f"hw_test_{uuid.uuid4().hex[:8]}"
    rif = "J-99887766-5"

    async def runner():
        await db.clients.insert_one({
            "client_id": client_id, "legal_name": "TEST INV CA", "fantasy_name": "TEST INV", "rif": rif,
        })
        await db.quotes.insert_one({
            "quote_id": quote_id, "quote_number": "COT-INV-TEST", "client_id": client_id,
            "quote_category": "fast_track",
        })
        for s in ["PRE-001", "PRE-002"]:
            await db.serial_assignments.insert_one({
                "assignment_id": f"sa_{uuid.uuid4().hex[:8]}",
                "serial": s, "item_id": item_id, "item_name": "Modelo X",
                "warehouse_id": "wh_test", "quote_id": quote_id, "client_id": client_id,
                "status": "preasignado", "preassigned_at": datetime.now(timezone.utc).isoformat(),
            })
        await db.inventory_movements.insert_one({
            "movement_id": f"mov_{uuid.uuid4().hex[:8]}", "movement_type": "salida",
            "item_id": item_id, "item_name": "Modelo X",
            "warehouse_id": "wh_test", "client_id": client_id,
            "serials": ["OLD-001"], "created_at": datetime.now(timezone.utc).isoformat(),
        })

        orig = qs.get_current_user

        async def _stub(_auth):
            return {"user_id": "u_test", "email": "t@t.com"}

        qs.get_current_user = _stub
        try:
            return await get_inventory_serials(quote_id, item_id, authorization="Bearer dummy")
        finally:
            qs.get_current_user = orig
            await db.clients.delete_one({"client_id": client_id})
            await db.quotes.delete_one({"quote_id": quote_id})
            await db.serial_assignments.delete_many({"quote_id": quote_id})
            await db.inventory_movements.delete_many({"item_id": item_id})

    res = _run(runner())
    serials = res["serials"]
    assert len(serials) >= 3, f"Esperados >=3 seriales, recibidos {len(serials)}"
    # Los 2 primeros deben ser preasignados (from_preassign=True)
    assert serials[0].get("from_preassign") is True, f"Primer serial debe ser preasignado: {serials[0]}"
    assert serials[1].get("from_preassign") is True
    # El histórico va después con flag False
    assert any(s["serial"] == "OLD-001" and s.get("from_preassign") is False for s in serials)


def test_implementation_pdf_banner_seriales():
    """La sección C debe titularse 'SERIALES DE LOS EQUIPOS'."""
    with open("/app/backend/services/implementation_pdf.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "C. SERIALES DE LOS EQUIPOS" in content, "Banner actualizado faltante"
    assert "C. MODELO Y SERIALES DE EQUIPOS" not in content, "Banner viejo no removido"


def test_send_to_implementation_fast_track_regular_flow():
    """Verifica que el código de send_to_implementation considere regular el flujo MPOS."""
    with open("/app/backend/routes/quote_actions.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "is_fast_track" in content
    assert '"Aprobada", "Configurada", "Facturada", "Pagada"' in content


def test_filter_status_includes_validar_pago_and_preasign():
    """QuoteFilters debe incluir las nuevas opciones Validar Pago y Preasign."""
    with open("/app/frontend/src/components/quotes/QuoteFilters.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert '"Validar Pago"' in content, "Falta opción Validar Pago"
    assert '"Preasign"' in content, "Falta opción Preasign"


def test_quotes_table_preasign_status_helper():
    """getEffectiveStatus debe retornar 'Preasign' cuando hay preassigned_at sin configured_at."""
    with open("/app/frontend/src/components/quotes/QuotesTable.jsx", "r", encoding="utf-8") as f:
        content = f.read()
    assert "return 'Preasign'" in content, "Falta lógica de Preasign en getEffectiveStatus"
