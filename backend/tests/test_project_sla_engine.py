"""Regresión del motor SLA de proyectos (semáforo de tiempos).

Cubre el cálculo de color por umbrales y el mapeo etapa↔estado.
"""
from datetime import datetime, timezone, timedelta

from services.project_sla_engine import (
    compute_color, STATUS_TO_STAGE, ACTIVE_STATUSES, stage_entered_at, SLA_ACTION_IDS,
)


def test_compute_color_thresholds():
    th = {"warning_days": 2, "delay_days": 4}
    assert compute_color(0, th) == "green"
    assert compute_color(1, th) == "green"
    assert compute_color(2, th) == "yellow"   # alcanza advertencia
    assert compute_color(3, th) == "yellow"
    assert compute_color(4, th) == "red"      # alcanza retraso
    assert compute_color(10, th) == "red"


def test_compute_color_warning_zero():
    th = {"warning_days": 0, "delay_days": 9999}
    assert compute_color(0, th) == "yellow"
    assert compute_color(50, th) == "yellow"


def test_status_to_stage_mapping():
    assert STATUS_TO_STAGE["Por asignar"] == "por_asignar"
    assert STATUS_TO_STAGE["Asignado"] == "asignado"
    assert STATUS_TO_STAGE["En Gestión"] == "en_gestion"
    # Estados terminales/pausados no son etapas activas
    assert "Suspendido" not in ACTIVE_STATUSES
    assert "Culminado" not in ACTIVE_STATUSES


def test_six_action_ids_exist():
    expected = {
        f"sla_{kind}_{stage}"
        for kind in ("warning", "delay")
        for stage in ("por_asignar", "asignado", "en_gestion")
    }
    assert SLA_ACTION_IDS == expected
    assert len(SLA_ACTION_IDS) == 6


def test_stage_entered_at_prefers_status_changed_at():
    now = datetime.now(timezone.utc)
    changed = (now - timedelta(days=3)).isoformat()
    created = (now - timedelta(days=30)).isoformat()
    proj = {"status": "En Gestión", "status_changed_at": changed, "created_at": created}
    ea = stage_entered_at(proj)
    assert ea is not None
    assert (now - ea).days == 3  # cuenta desde que entró al estado actual
