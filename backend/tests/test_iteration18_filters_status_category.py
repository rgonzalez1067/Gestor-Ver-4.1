# ruff: noqa
"""Tests Iteration 18 — Filtros estrictos de estado y categoría en Cotizaciones.

Valida:
1. `getEffectiveStatus` (replicada en backend) clasifica "Validar Pago" DESPUÉS
   de "Pagada" — un quote con paid_at + pago_validado debe ser 'Validar Pago',
   no 'Pagada'.
2. Filtro de Categoría "Implementación (todas)" debe incluir fast_track
   (MPOS Imple+POS), no excluirlos.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def get_effective_status(q):
    """Espejo Python del helper en frontend QuotesTable.jsx (Feb 2026)."""
    if q.get('delivered_at'): return 'Entregada'
    if q.get('repaired_at'): return 'Reparada'
    if q.get('implementation_completed_at'): return 'Implementada'
    ex = q.get('custom_actions_executed') or {}
    if ex.get('pago_validado') or ex.get('pago_validado_eq') or ex.get('pago_validado_rep'):
        return 'Validar Pago'
    if q.get('paid_at'): return 'Pagada'
    if q.get('invoice_number') or q.get('invoiced_at'): return 'Facturada'
    if q.get('configured_at'): return 'Configurada'
    if q.get('preassigned_at') or (q.get('preassigned_serials') and len(q['preassigned_serials']) > 0):
        return 'Preasign'
    if q.get('approved_at'): return 'Aprobada'
    if q.get('sent_at'): return 'Enviada'
    return q.get('quote_status') or 'Borrador'


def matches_category(quote, filter_category):
    """Espejo Python del filtro de categoría en QuotesTable.jsx (Feb 2026)."""
    if not filter_category or filter_category == 'all':
        return True
    cat = quote.get('quote_category') or 'implementation'
    parts = filter_category.split(':', 1)
    base_cat = parts[0]
    sub_type = parts[1] if len(parts) > 1 else None
    qt = (quote.get('quote_type') or '').upper()

    if sub_type == 'FAST_TRACK':
        return cat == 'fast_track' or (cat == 'implementation' and qt == 'FAST_TRACK')
    if base_cat == 'implementation' and not sub_type:
        # "Implementación (todas)" — incluye fast_track también
        return cat in ('implementation', 'fast_track')
    if base_cat != cat:
        return False
    if sub_type:
        return qt == sub_type.upper()
    return True


# ============ getEffectiveStatus ============
def test_validar_pago_takes_precedence_over_pagada():
    """Si un quote tiene paid_at Y pago_validado, el estado es 'Validar Pago'
    (más reciente operativamente que cobrar)."""
    q = {
        "paid_at": "2026-05-07T13:57:21",
        "invoiced_at": "2026-05-07T13:39:17",
        "custom_actions_executed": {"pago_validado_eq": "2026-05-13T20:53:36"},
    }
    assert get_effective_status(q) == 'Validar Pago'


def test_only_paid_no_validation_is_pagada():
    """Sin pago_validado, paid_at => Pagada."""
    q = {"paid_at": "2026-05-07T13:57:21", "invoiced_at": "2026-05-07T13:39:17"}
    assert get_effective_status(q) == 'Pagada'


def test_delivered_overrides_validar_pago():
    """delivered_at sigue siendo más avanzado que Validar Pago."""
    q = {
        "delivered_at": "2026-05-25T10:00:00",
        "paid_at": "2026-05-07T13:57:21",
        "custom_actions_executed": {"pago_validado_eq": "2026-05-13T20:53:36"},
    }
    assert get_effective_status(q) == 'Entregada'


def test_pago_validado_alone_returns_validar_pago():
    """pago_validado sin paid_at → Validar Pago (edge case raro)."""
    q = {"invoiced_at": "2026-05-07T13:39:17",
         "custom_actions_executed": {"pago_validado": "2026-05-13T20:53:36"}}
    assert get_effective_status(q) == 'Validar Pago'


def test_status_filter_excludes_pagada_from_validar_pago_bucket():
    """Filtro 'Pagada' no debe mostrar quotes con pago_validado."""
    quotes = [
        {"paid_at": "x"},
        {"paid_at": "x", "custom_actions_executed": {"pago_validado_eq": "y"}},
    ]
    pagada = [q for q in quotes if get_effective_status(q) == 'Pagada']
    validar = [q for q in quotes if get_effective_status(q) == 'Validar Pago']
    assert len(pagada) == 1
    assert len(validar) == 1


# ============ matches_category ============
def test_implementation_all_includes_fast_track():
    """Filtro 'implementation' (Implementación todas) DEBE incluir fast_track."""
    q_fast_track = {"quote_category": "fast_track", "quote_type": "FAST_TRACK"}
    q_legacy_mpos = {"quote_category": "implementation", "quote_type": "FAST_TRACK"}
    q_vpos = {"quote_category": "implementation", "quote_type": "VPOS"}
    assert matches_category(q_fast_track, 'implementation') is True
    assert matches_category(q_legacy_mpos, 'implementation') is True
    assert matches_category(q_vpos, 'implementation') is True


def test_implementation_all_excludes_equipment_and_repair():
    q_eq = {"quote_category": "equipment"}
    q_rep = {"quote_category": "repair"}
    assert matches_category(q_eq, 'implementation') is False
    assert matches_category(q_rep, 'implementation') is False


def test_implementation_subtype_strict():
    """implementation:VPOS NO debe traer FAST_TRACK ni GATEWAY."""
    q_vpos = {"quote_category": "implementation", "quote_type": "VPOS"}
    q_mpos = {"quote_category": "fast_track", "quote_type": "FAST_TRACK"}
    assert matches_category(q_vpos, 'implementation:VPOS') is True
    assert matches_category(q_mpos, 'implementation:VPOS') is False


def test_implementation_fast_track_filter_matches_both_legacy_and_new():
    q_new = {"quote_category": "fast_track", "quote_type": "FAST_TRACK"}
    q_legacy = {"quote_category": "implementation", "quote_type": "FAST_TRACK"}
    q_vpos = {"quote_category": "implementation", "quote_type": "VPOS"}
    assert matches_category(q_new, 'implementation:FAST_TRACK') is True
    assert matches_category(q_legacy, 'implementation:FAST_TRACK') is True
    assert matches_category(q_vpos, 'implementation:FAST_TRACK') is False


def test_equipment_filter_strict():
    q_eq = {"quote_category": "equipment"}
    q_impl = {"quote_category": "implementation", "quote_type": "VPOS"}
    assert matches_category(q_eq, 'equipment') is True
    assert matches_category(q_impl, 'equipment') is False


def test_repair_filter_strict():
    q_rep = {"quote_category": "repair"}
    q_eq = {"quote_category": "equipment"}
    assert matches_category(q_rep, 'repair') is True
    assert matches_category(q_eq, 'repair') is False
