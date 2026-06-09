"""
Regresión — {Matriz_Bancos_Productos} (edición/estilos) + variable {Patrocinador}.

Cubre:
- `_clean_html_in_braces`: colapsa variables fragmentadas por el editor PERO no
  consume etiquetas adyacentes (no corrompe tablas que siguen a una variable).
- `_render_vars`: renderiza {Patrocinador} y preserva la tabla siguiente.
- `_style_email_tables`: re-aplica bordes a tablas sin estilo (salida de TipTap).
- `resolve_project_template_vars`: {Patrocinador} condicional (patrocinado vs no).
"""
import asyncio
import pytest

from config import db
from routes.projects import _clean_html_in_braces, _render_vars, _style_email_tables
from services.project_template_vars import resolve_project_template_vars

loop = asyncio.get_event_loop()


def test_clean_braces_collapses_split_variable():
    html = "<p>{<span>Nombre</span>_Cliente}</p>"
    assert _clean_html_in_braces(html) == "<p>{Nombre_Cliente}</p>"


def test_clean_braces_does_not_eat_adjacent_table():
    """La tabla que sigue a una variable NO debe ser consumida (bug fix)."""
    html = "<strong>{Patrocinador}</strong><table><tbody><tr><td>x</td></tr></tbody></table>"
    out = _clean_html_in_braces(html)
    assert "<table>" in out
    assert "<td>x</td>" in out
    assert "{Patrocinador}" in out


def test_render_vars_keeps_table_after_variable():
    html = "<p>{Patrocinador}</p><table><tbody><tr><td>Banco</td></tr></tbody></table>"
    out = _render_vars(html, {"Patrocinador": "Banco Mercantil"})
    assert "Banco Mercantil" in out
    assert "<table>" in out and "<td>Banco</td>" in out


def test_style_email_tables_adds_borders():
    bare = "<table><tbody><tr><td><p>A</p></td><th>H</th></tr></tbody></table>"
    out = _style_email_tables(bare)
    assert "border-collapse:collapse" in out
    assert "border:1px solid" in out


def test_style_email_tables_preserves_existing_style():
    styled = '<table style="width:50%"><tbody><tr><td style="color:red">A</td></tr></tbody></table>'
    out = _style_email_tables(styled)
    assert out == styled  # no se altera lo que ya trae estilo


def test_patrocinador_sponsored_uses_bank():
    project = loop.run_until_complete(
        db.projects.find_one(
            {"sponsored_implementation": True, "sponsoring_bank_name": {"$ne": None}},
            {"_id": 0},
        )
    )
    assert project, "Se requiere un proyecto patrocinado para la prueba"
    v = loop.run_until_complete(resolve_project_template_vars(project))
    expected = project.get("sponsoring_bank_name")
    if project.get("sponsoring_processor_name"):
        expected = f"{expected} - {project['sponsoring_processor_name']}"
    assert v["Patrocinador"] == expected


def test_patrocinador_unsponsored_uses_client_name():
    project = loop.run_until_complete(
        db.projects.find_one(
            {"$or": [{"sponsored_implementation": {"$ne": True}}, {"sponsoring_bank_name": None}]},
            {"_id": 0},
        )
    )
    assert project, "Se requiere un proyecto no patrocinado para la prueba"
    v = loop.run_until_complete(resolve_project_template_vars(project))
    # No es el banco patrocinador; corresponde a la fantasía/nombre del cliente
    assert v["Patrocinador"]
    assert v["Patrocinador"] != project.get("sponsoring_bank_name")
