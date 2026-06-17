# ruff: noqa
"""Regresión del Motor de Cálculo de PVV y métricas del Mini Tablero de Avance Operativo.

Reglas confirmadas con el usuario:
  - "Configurado" = terminales en la fase final 'En Producción'.
  - PVV Asignados = Cajas × (Bancos × Productos).
  - PVV Configurados = Σ processed en 'En Producción' (single + tiendas).
  - Cajas Configuradas = PVV Configurados ÷ (Bancos × Productos).
  - Proyectos digitales (GATEWAY/LINK_PAGO): bloque físico = 0/0.
"""
from services.project_pvv import compute_project_metrics, compute_project_pvv


def _phase(processed=0, expected=2):
    return {"En Producción": {"processed": processed, "expected": expected, "completed": processed >= expected}}


def test_qa_criterion_2x2x2_equals_8_pvv():
    """QA: 2 cajas × 2 productos × 2 bancos = 8 PVV Asignados."""
    proj = {
        "quote_type": "VPOS",
        "box_count": 2,
        "implementation_matrix": {
            "Banco A": {"Crédito": _phase(2), "Débito": _phase(0)},
            "Banco B": {"Crédito": _phase(0), "Débito": _phase(0)},
        },
    }
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 8
    assert compute_project_pvv(proj) == 8
    # Solo Banco A/Crédito llegó a producción (processed=2) -> 2 PVV configurados.
    assert m["pvv_configurados"] == 2
    assert m["cajas_asignadas"] == 2


def test_fully_configured_single():
    proj = {
        "quote_type": "VPOS",
        "box_count": 3,
        "implementation_matrix": {"Banco A": {"Débito": _phase(3, 3)}},
    }
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 3            # 3 cajas × 1 combo
    assert m["pvv_configurados"] == 3
    assert m["cajas_asignadas"] == 3
    assert m["cajas_configuradas"] == 3       # 3 / 1 combo


def test_digital_project_has_zero_physical():
    proj = {
        "quote_type": "GATEWAY",
        "box_count": 1,
        "implementation_matrix": {"Banco A": {"PG": _phase(1, 1)}, "Banco B": {"PG": _phase(0, 1)}},
    }
    m = compute_project_metrics(proj)
    assert m["cajas_asignadas"] == 0
    assert m["cajas_configuradas"] == 0
    assert m["pvv_asignados"] == 2            # 1 caja × 2 combos
    assert m["pvv_configurados"] == 1


def test_empty_matrix_is_resilient():
    proj = {"quote_type": "VPOS", "box_count": 4, "implementation_matrix": {}}
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 4            # fallback a cajas cuando no hay combos
    assert m["pvv_configurados"] == 0
    assert m["cajas_asignadas"] == 4
    assert m["cajas_configuradas"] == 0


def test_multistore_aggregates_stores():
    """En multitienda el avance vive en las tiendas; se suma su producción."""
    store_matrix = {"Banco A": {"Débito": _phase(2, 2)}}
    proj = {
        "quote_type": "VPOS",
        "project_type": "multistore",
        "box_count": 4,
        "implementation_matrix": {"Banco A": {"Débito": _phase(0, 4)}},
        "stores": [
            {"name": "T1", "implementation_matrix": store_matrix},
            {"name": "T2", "implementation_matrix": {"Banco A": {"Débito": _phase(1, 2)}}},
        ],
    }
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 4            # 4 cajas × 1 combo
    assert m["pvv_configurados"] == 3         # 2 (T1) + 1 (T2)
    assert m["cajas_configuradas"] == 3       # 3 / 1 combo


def test_configured_never_exceeds_assigned():
    proj = {
        "quote_type": "VPOS",
        "box_count": 1,
        "implementation_matrix": {"Banco A": {"Débito": _phase(99, 1)}},
    }
    m = compute_project_metrics(proj)
    assert m["pvv_configurados"] <= m["pvv_asignados"]
    assert m["cajas_configuradas"] <= m["cajas_asignadas"]
