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


# Tipos de cotización "digitales" (ecosistema PVV puro, sin hardware físico).
DIGITAL_QUOTE_TYPES = {"GATEWAY", "LINK_PAGO"}

# Fase final de la matriz que marca un combo Banco/Producto como "Activo/Certificado".
PRODUCTION_PHASE = "En Producción"


def _matrix_combos(matrix: dict | None) -> int:
    """Conteo de combinaciones Banco×Producto en una matriz de implementación."""
    n = 0
    for _bank, prods in (matrix or {}).items():
        if isinstance(prods, dict):
            n += len(prods)
    return n


def _production_processed(matrix: dict | None) -> int:
    """Suma de terminales `processed` en la fase final 'En Producción' de cada
    combo Banco/Producto. Representa los PVV ya activos/certificados."""
    total = 0
    for _bank, prods in (matrix or {}).items():
        if not isinstance(prods, dict):
            continue
        for _prod, phases in prods.items():
            ep = (phases or {}).get(PRODUCTION_PHASE) or {}
            try:
                total += int(ep.get("processed") or 0)
            except (TypeError, ValueError):
                pass
    return total


def compute_project_metrics(project: dict[str, Any]) -> dict[str, int]:
    """Métricas del Mini Tablero de Avance Operativo para un proyecto.

    Devuelve 4 contadores enteros:
      - cajas_asignadas / cajas_configuradas (ecosistema físico)
      - pvv_asignados / pvv_configurados (ecosistema digital)

    Reglas (confirmadas con el usuario):
      - "Configurado" = terminales que alcanzaron la fase final 'En Producción'.
      - PVV Asignados = Cajas × (Bancos × Productos) [teórico, = compute_project_pvv].
      - PVV Configurados = Σ `processed` en 'En Producción' (proyecto single + tiendas).
      - Cajas Configuradas = PVV Configurados ÷ (Bancos × Productos) [congruencia con la fórmula].
      - Proyectos digitales (GATEWAY/LINK_PAGO): el bloque físico es 0/0 (no hay cajas).
    """
    is_digital = (project.get("quote_type") or "") in DIGITAL_QUOTE_TYPES
    try:
        box_count = int(project.get("box_count") or project.get("cantidad_cajas") or 0)
    except (TypeError, ValueError):
        box_count = 0

    n_combos = _matrix_combos(project.get("implementation_matrix"))
    pvv_asignados = compute_project_pvv(project)

    pvv_configurados = _production_processed(project.get("implementation_matrix"))
    for store in (project.get("stores") or []):
        pvv_configurados += _production_processed(store.get("implementation_matrix"))
    # Robustez: nunca exceder el teórico asignado.
    if pvv_asignados > 0:
        pvv_configurados = min(pvv_configurados, pvv_asignados)

    if is_digital:
        cajas_asignadas = 0
        cajas_configuradas = 0
    else:
        cajas_asignadas = box_count
        cajas_configuradas = round(pvv_configurados / n_combos) if n_combos > 0 else 0
        cajas_configuradas = min(cajas_configuradas, cajas_asignadas)

    return {
        "cajas_asignadas": cajas_asignadas,
        "cajas_configuradas": cajas_configuradas,
        "pvv_asignados": pvv_asignados,
        "pvv_configurados": pvv_configurados,
    }
