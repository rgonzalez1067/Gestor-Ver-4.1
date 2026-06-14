"""Regresión del Módulo de Consulta de Ventas Avanzada (embudo excluyente + origen)."""
from routes.sales_reports import _adv_stage_of, _adv_origin, _adv_counts


def test_adv_counts_by_category():
    # Implementación → cajas
    c = _adv_counts({"quote_category": "implementation", "cantidad_cajas": 8})
    assert c == {"boxes": 8, "repair_units": None, "sold_units": None}
    # Reparación → suma de quantity de equipment_items
    c = _adv_counts({"quote_category": "repair", "equipment_items": [{"quantity": 5}, {"quantity": 1}, {"quantity": 1}]})
    assert c == {"boxes": None, "repair_units": 7, "sold_units": None}
    # Equipos → equipos vendidos
    c = _adv_counts({"quote_category": "equipment", "equipment_items": [{"quantity": 30}]})
    assert c == {"boxes": None, "repair_units": None, "sold_units": 30}
    # Fast Track híbrido → cajas + vendidos (de ft_equipment_items)
    c = _adv_counts({"quote_category": "fast_track", "cantidad_cajas": 1, "ft_equipment_items": [{"quantity": 1}]})
    assert c == {"boxes": 1, "repair_units": None, "sold_units": 1}


def test_funnel_exclusive_stages():
    # Borrador: sin ningún hito
    assert _adv_stage_of({"quote_status": "Borrador"}) is None
    # Emitida y solo enviada
    assert _adv_stage_of({"sent_to_client_at": "2026-04-01T00:00:00"}) == "enviada"
    # Aprobada (no facturada)
    assert _adv_stage_of({"sent_to_client_at": "x", "approved_at": "y"}) == "aprobada"
    # Facturada pero NO pagada -> Hito 3 (no debe contar en 4 ni 5)
    q = {"approved_at": "a", "invoice_number": "F-001", "paid_at": None, "sent_to_implementation_at": None}
    assert _adv_stage_of(q) == "facturada"
    # Pagada pero no entregada -> Hito 4
    q2 = {"invoice_number": "F-1", "paid_at": "p", "sent_to_implementation_at": None}
    assert _adv_stage_of(q2) == "pagada"
    # Entregada (implementación) -> Hito 5
    q3 = {"paid_at": "p", "sent_to_implementation_at": "i"}
    assert _adv_stage_of(q3) == "entregada"


def test_funnel_priority_is_max_stage():
    # Una cotización con todos los hitos cuenta solo como entregada (el más avanzado)
    full = {
        "sent_to_client_at": "a", "approved_at": "b", "invoice_number": "F",
        "paid_at": "p", "sent_to_implementation_at": "i",
    }
    assert _adv_stage_of(full) == "entregada"


def test_origin_derivation():
    assert _adv_origin({"parent_quote_id": "q_123"}) == "Renovación"
    assert _adv_origin({"parent_quote_id": None}) == "Generado por Ejecutivo"
    assert _adv_origin({}) == "Generado por Ejecutivo"
