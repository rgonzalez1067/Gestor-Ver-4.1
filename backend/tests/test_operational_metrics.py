# ruff: noqa
"""Regresión del Motor de Cálculo de PVV y métricas del Mini Tablero de Avance Operativo.

Reglas de negocio vigentes (confirmadas por el usuario):
  - PVV Asignados = Cajas × (Bancos × Productos), robusto a Multi-RIF (coincide con Reporte de Carga).
  - Cajas Asignadas = total de cajas del proyecto.
  - Cajas Configuradas = total de cajas SOLO si estado ∈ {'Culminado','Implementado parcial'}.
  - PVV Configurados = Σ terminales en 'En Producción' por combo Banco/Producto;
    en multitienda se baja al nivel de tienda.
  - Proyectos digitales (GATEWAY/LINK_PAGO): bloque físico = 0/0.
"""
from services.project_pvv import compute_project_metrics, compute_project_pvv


def _phase(processed=0, expected=2):
    return {"En Producción": {"processed": processed, "expected": expected, "completed": processed >= expected}}


def test_qa_pvv_asignados_2x2x2():
    """QA: 2 cajas × 2 productos × 2 bancos = 8 PVV Asignados."""
    proj = {
        "quote_type": "VPOS",
        "status": "En Gestión",
        "box_count": 2,
        "implementation_matrix": {
            "Banco A": {"Crédito": _phase(2), "Débito": _phase(0)},
            "Banco B": {"Crédito": _phase(0), "Débito": _phase(0)},
        },
    }
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 8
    assert compute_project_pvv(proj) == 8


def test_qa_cajas_configuradas_by_status():
    """QA: 10 cajas 'En Gestión' → 0 cajas config. Pasa a 'Implementado parcial' → 10."""
    base = {
        "quote_type": "VPOS",
        "box_count": 10,
        "implementation_matrix": {"Banco A": {"Débito": _phase(0, 10)}},
    }
    en_gestion = compute_project_metrics({**base, "status": "En Gestión"})
    assert en_gestion["cajas_asignadas"] == 10
    assert en_gestion["cajas_configuradas"] == 0

    parcial = compute_project_metrics({**base, "status": "Implementado parcial"})
    assert parcial["cajas_configuradas"] == 10

    culminado = compute_project_metrics({**base, "status": "Culminado"})
    assert culminado["cajas_configuradas"] == 10

    suspendido = compute_project_metrics({**base, "status": "Suspendido"})
    assert suspendido["cajas_configuradas"] == 0


def test_qa_pvv_configurados_standard_production_phase():
    """QA: 1 Banco, 2 Productos, 5 cajas. Solo 2 cajas de 1 producto en Producción → 2 PVV config."""
    proj = {
        "quote_type": "VPOS",
        "status": "En Gestión",
        "box_count": 5,
        "implementation_matrix": {
            "Banco A": {"Crédito": _phase(2, 5), "Débito": _phase(0, 5)},
        },
    }
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 10  # 5 cajas × 2 combos
    assert m["pvv_configurados"] == 2  # solo Crédito con 2 en producción


def test_qa_multistore_granularity():
    """QA: Multitienda 2 sucursales (2 cajas c/u). Solo 1 caja de Tienda A para Banco Z en Producción → 1 PVV config."""
    proj = {
        "quote_type": "VPOS",
        "project_type": "multistore",
        "status": "En Gestión",
        "box_count": 4,
        "implementation_matrix": {"Banco Z": {"Débito": _phase(0, 4)}},  # plantilla, no se cuenta
        "stores": [
            {"name": "Tienda A", "implementation_matrix": {"Banco Z": {"Débito": _phase(1, 2)}}},
            {"name": "Tienda B", "implementation_matrix": {"Banco Z": {"Débito": _phase(0, 2)}}},
        ],
    }
    m = compute_project_metrics(proj)
    assert m["pvv_configurados"] == 1  # solo 1 caja en Tienda A llegó a producción


def test_digital_project_zero_physical():
    proj = {
        "quote_type": "GATEWAY",
        "status": "Culminado",
        "box_count": 1,
        "implementation_matrix": {"Banco A": {"PG": _phase(1, 1)}, "Banco B": {"PG": _phase(0, 1)}},
    }
    m = compute_project_metrics(proj)
    assert m["cajas_asignadas"] == 0
    assert m["cajas_configuradas"] == 0   # físico siempre 0 aunque esté Culminado
    assert m["pvv_asignados"] == 2
    assert m["pvv_configurados"] == 1


def test_multirif_cajas_from_rifs_fallback():
    """Multi-RIF: cajas viven en `rifs` (box_count/cantidad_cajas vacíos)."""
    proj = {
        "quote_type": "VPOS_MULTIRIF",
        "project_type": "multirif",
        "status": "En Gestión",
        "box_count": 0,
        "cantidad_cajas": 0,
        "rifs": [{"box_count": 10}, {"box_count": 18}],
        "implementation_matrix": {"Banco A": {"Débito": _phase(0)}},
    }
    assert compute_project_pvv(proj) == 28  # 28 cajas × 1 combo
    m = compute_project_metrics(proj)
    assert m["pvv_asignados"] == 28
    assert m["cajas_asignadas"] == 28


def test_configured_never_exceeds_assigned():
    proj = {
        "quote_type": "VPOS",
        "status": "Culminado",
        "box_count": 1,
        "implementation_matrix": {"Banco A": {"Débito": _phase(99, 1)}},
    }
    m = compute_project_metrics(proj)
    assert m["pvv_configurados"] <= m["pvv_asignados"]
    assert m["cajas_configuradas"] <= m["cajas_asignadas"]
