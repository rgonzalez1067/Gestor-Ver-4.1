"""Cálculo de PVV (Puntos de Venta Virtuales) — métrica oficial de la operación
técnica que refleja el peso real del procesamiento configurado.

Fórmula homologada con el cotizador comercial:
    PVV = Nro de Cajas × (Bancos × Productos)

donde (Bancos × Productos) es el conteo de combinaciones banco/producto activas
en la `implementation_matrix` del proyecto. Si la matriz está vacía (proyecto
sin medios de pago configurados todavía), PVV = Nro de Cajas para no penalizar
proyectos recién creados.

Este es el MISMO valor que se renderiza en el "Resumen Ejecutivo" del PDF de
cotización bajo la etiqueta "Total de Terminales Virtuales" (ver
`routes/quotes.py:1488-1495`).
"""
from typing import Any


def compute_project_pvv(project: dict[str, Any]) -> int:
    """Calcula el Nro de PVV para un proyecto.

    Parámetros:
      project: documento del proyecto (puede ser parcial; se leen `cantidad_cajas`,
               `box_count`, `implementation_matrix`).

    Retorna:
      int >= 0. Cuando la matriz no contiene combinaciones banco/producto válidas
      se retorna la cantidad de cajas (proyecto en estado inicial).
    """
    matrix = project.get("implementation_matrix") or {}
    n_combos = 0
    for bank, prods in matrix.items():
        if isinstance(prods, dict):
            # Cada llave dentro del banco es un producto distinto.
            n_combos += len(prods)
    try:
        cajas = int(project.get("cantidad_cajas") or project.get("box_count") or 0)
    except (TypeError, ValueError):
        cajas = 0
    if n_combos <= 0:
        return cajas
    return cajas * n_combos
