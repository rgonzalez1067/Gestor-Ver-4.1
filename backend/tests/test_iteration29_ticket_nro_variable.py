# ruff: noqa
"""Iteration 29 — Validar que {Ticket_Nro} se resuelve correctamente desde project.ticket_number."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ticket_nro_resolves_from_project():
    from services.project_template_vars import resolve_project_template_vars

    fake_project = {
        "project_id": "prj_test_iter29",
        "project_number": "PRY-2026-05-999-TST",
        "quote_number": "COT-2026-05-999-PYME",
        "ticket_number": "55512",  # ticket asignado al desbloquear el proyecto
        "client_id": None,
        "client_name": "ACME C.A.",
        "client_rif": "J123456789",
        "client_segment": "PYME",
        "quote_type": "VPOS",
        "assigned_at": "2026-05-22T10:30:00Z",
        "unblocked_at": "2026-05-23T14:45:00Z",
        "assigned_to_name": "Implementador Demo",
        "services": [],
        "stores": [],
        "implementation_matrix": {},
    }

    vars_resolved = asyncio.run(resolve_project_template_vars(fake_project))

    # Confirmar alias PascalCase Spanish presentes
    assert vars_resolved["Ticket_Nro"] == "55512", f"Ticket_Nro mal resuelto: {vars_resolved.get('Ticket_Nro')!r}"
    assert vars_resolved["Nro_Ticket"] == "55512", "Alias Nro_Ticket faltante"
    assert vars_resolved["Nro_Proyecto"] == "PRY-2026-05-999-TST"
    assert vars_resolved["Tipo_Proyecto"] == "VPOS"
    assert vars_resolved["Fecha_Asignacion"] == "22/05/2026"
    assert vars_resolved["Fecha_Desbloqueo_Ticket"] == "23/05/2026"
    # snake_case sigue funcionando (back-compat)
    assert vars_resolved["ticket_number"] == "55512"
    assert vars_resolved["project_number"] == "PRY-2026-05-999-TST"


def test_ticket_nro_empty_when_not_unblocked():
    from services.project_template_vars import resolve_project_template_vars

    fake_project = {
        "project_id": "prj_locked",
        "project_number": "PRY-2026-05-001-PRI",
        "quote_number": "COT-2026-05-001-PYME",
        # ticket_number ausente → proyecto bloqueado
        "client_name": "Locked Client",
        "client_rif": "J987654321",
        "client_segment": "PYME",
        "quote_type": "VPOS",
        "services": [],
        "stores": [],
        "implementation_matrix": {},
    }

    vars_resolved = asyncio.run(resolve_project_template_vars(fake_project))
    assert vars_resolved["Ticket_Nro"] == "", "Ticket_Nro debe estar vacío si el proyecto no se ha desbloqueado"
    assert vars_resolved["Fecha_Desbloqueo_Ticket"] == "", "Fecha_Desbloqueo_Ticket debe estar vacía"


if __name__ == "__main__":
    test_ticket_nro_resolves_from_project()
    test_ticket_nro_empty_when_not_unblocked()
    print("OK — both tests passed")
