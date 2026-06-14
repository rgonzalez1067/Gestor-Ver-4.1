"""
Regresión: variable {Matriz_Avance_Proyecto}.
Reglas por celda de fase: Cumplida -> '100%', En proceso -> '{pct}%',
No iniciada -> '—'. KPI Global = rollup_progress.global_progress (dashboard).
Jerarquía: single = Banco->Producto->Fases ; multitienda/Multi-RIF añade
nivel Tienda/Sucursal.
"""
from services.project_template_vars import _build_avance_matrix_html, _phase_cell_value, _fmt_short_date


def test_fmt_short_date():
    assert _fmt_short_date("2026-06-11T17:36:30.923180+00:00") == "11/06/2026"
    assert _fmt_short_date("") == ""
    assert _fmt_short_date(None) == ""
    assert _fmt_short_date("no-fecha") == ""


def test_matriz_con_fecha():
    """La variante con_fecha muestra la fecha (updated_at) bajo cada % alcanzado;
    la base NO la muestra."""
    single = {
        "project_type": "single",
        "rollup_progress": {"global_progress": 62},
        "implementation_matrix": {
            "Bancamiga": {
                "Tarjeta": {
                    "Recibido": {"completed": True, "expected": 5, "processed": 5, "updated_at": "2026-06-10T12:00:00+00:00"},
                    "Configurado": {"completed": False, "expected": 4, "processed": 2, "updated_at": "2026-06-11T12:00:00+00:00"},
                    "Testeado": {"completed": False, "expected": 0, "processed": 0},
                    "En Producción": {"completed": False, "expected": 0, "processed": 0},
                }
            }
        },
    }
    base = _build_avance_matrix_html(single, with_dates=False)
    con_fecha = _build_avance_matrix_html(single, with_dates=True)
    assert "10/06/2026" not in base and "11/06/2026" not in base
    assert "100%" in con_fecha and "10/06/2026" in con_fecha
    assert "50%" in con_fecha and "11/06/2026" in con_fecha



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
