"""
Regresión: variable {Matriz_Avance_Proyecto}.
Reglas por celda de fase: Cumplida -> '100%', En proceso -> '{pct}%',
No iniciada -> '—'. KPI Global = rollup_progress.global_progress (dashboard).
Jerarquía: single = Banco->Producto->Fases ; multitienda/Multi-RIF añade
nivel Tienda/Sucursal.
"""
from services.project_template_vars import _build_avance_matrix_html, _phase_cell_value


def test_phase_cell_rules():
    assert _phase_cell_value({"completed": True, "expected": 5, "processed": 5}) == ("100%", "done")
    assert _phase_cell_value({"completed": False, "expected": 4, "processed": 2}) == ("50%", "progress")
    assert _phase_cell_value({"completed": False, "expected": 4, "processed": 4}) == ("100%", "done")
    assert _phase_cell_value({"completed": False, "expected": 0, "processed": 0}) == ("—", "none")
    assert _phase_cell_value({}) == ("—", "none")


def test_single_project_matrix():
    single = {
        "project_type": "single",
        "rollup_progress": {"global_progress": 62},
        "implementation_matrix": {
            "Bancamiga": {
                "Tarjeta": {
                    "Recibido": {"completed": True, "expected": 5, "processed": 5},
                    "Configurado": {"completed": False, "expected": 4, "processed": 2},
                    "Testeado": {"completed": False, "expected": 0, "processed": 0},
                    "En Producción": {"completed": False, "expected": 0, "processed": 0},
                }
            }
        },
    }
    h = _build_avance_matrix_html(single)
    assert "Avance Global del Proyecto" in h and "62%" in h
    assert "Banco: Bancamiga" in h
    assert "100%" in h and "50%" in h and "—" in h


def test_multirif_project_matrix():
    multi = {
        "project_type": "multirif",
        "rollup_progress": {"global_progress": 40},
        "rifs": [{"rif_id": "r1", "client_name": "Comercio A", "rif": "J-1"}],
        "stores": [{
            "name": "Centro", "box_count": 3, "rif_id": "r1",
            "implementation_matrix": {
                "Banesco": {
                    "C2P": {
                        "Recibido": {"completed": True, "expected": 3, "processed": 3},
                        "Configurado": {"completed": False, "expected": 3, "processed": 1},
                    }
                }
            },
        }],
    }
    h = _build_avance_matrix_html(multi)
    assert "Sucursal: Centro" in h
    assert "Comercio A" in h and "J-1" in h
    assert "40%" in h
