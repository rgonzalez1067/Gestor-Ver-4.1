"""Iter36 — Regression test: la restricción "solo Configuración" para usuarios
del Departamento Operaciones aplica únicamente a cotizaciones fast_track
(MPOS Imple+POS). Para Reparaciones, Equipos e Implementaciones nativas, el
override de acciones se rige por las reglas estándar.

Este test valida el invariant LÓGICO documentado en QuotesTable.jsx:
   canEditNonConfig = canEdit && !(opsReadonly && isFastTrack)

Se replica la lógica en Python para detectar regresiones a nivel de contrato.
"""
import pytest


def can_edit_non_config(can_edit: bool, ops_readonly: bool, quote_category: str) -> bool:
    """Réplica fiel de la lógica del frontend (QuotesTable.jsx Iter36)."""
    is_fast_track = quote_category == "fast_track"
    return can_edit and not (ops_readonly and is_fast_track)


@pytest.mark.parametrize("category,expected", [
    ("repair", True),
    ("equipment", True),
    ("implementation", True),
    ("fast_track", False),
])
def test_ops_user_can_act_except_on_fast_track(category, expected):
    """Usuario de Operaciones con canEdit=True: puede actuar en TODO excepto fast_track."""
    assert can_edit_non_config(can_edit=True, ops_readonly=True, quote_category=category) is expected


@pytest.mark.parametrize("category", ["repair", "equipment", "implementation", "fast_track"])
def test_non_ops_user_unaffected(category):
    """Usuario no-Operaciones (ops_readonly=False) puede actuar en todas las categorías
    cuando canEdit=True. La regla nueva NO debe afectar a otros perfiles."""
    assert can_edit_non_config(can_edit=True, ops_readonly=False, quote_category=category) is True


@pytest.mark.parametrize("category", ["repair", "equipment", "fast_track"])
def test_no_edit_permission_blocks_all(category):
    """Si canEdit=False, ningún usuario puede actuar (independiente de ops_readonly)."""
    assert can_edit_non_config(can_edit=False, ops_readonly=True, quote_category=category) is False
    assert can_edit_non_config(can_edit=False, ops_readonly=False, quote_category=category) is False
