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


def _total_cajas(project: dict[str, Any]) -> int:
    """Total de cajas robusto (homologado con el Reporte de Carga,
    `routes/projects.py::_project_total_cajas`). En Multi-RIF las cajas viven en
    `rifs`, por lo que `cantidad_cajas`/`box_count` pueden venir vacíos."""
    try:
        c = int(project.get("cantidad_cajas") or project.get("box_count") or 0)
    except (TypeError, ValueError):
        c = 0
    if c <= 0 and project.get("rifs"):
        c = sum(int(r.get("box_count") or 0) for r in (project.get("rifs") or []))
    return c


def compute_project_pvv(project: dict[str, Any]) -> int:
    """Calcula el Nro de PVV para un proyecto.

    Parámetros:
      project: documento del proyecto (puede ser parcial; se leen `cantidad_cajas`,
               `box_count`, `rifs`, `implementation_matrix`).

    Retorna:
      int >= 0. Cuando la matriz no contiene combinaciones banco/producto válidas
      se retorna la cantidad de cajas (proyecto en estado inicial). El total de
      cajas es robusto a Multi-RIF para coincidir 100% con el Reporte de Carga.
    """
    matrix = project.get("implementation_matrix") or {}
    n_combos = 0
    for bank, prods in matrix.items():
        if isinstance(prods, dict):
            # Cada llave dentro del banco es un producto distinto.
            n_combos += len(prods)
    cajas = _total_cajas(project)
    if n_combos <= 0:
        return cajas
    return cajas * n_combos


# Tipos de cotización "digitales" (ecosistema PVV puro, sin hardware físico).
DIGITAL_QUOTE_TYPES = {"GATEWAY", "LINK_PAGO"}

# Fase final de la matriz que marca un combo Banco/Producto como "Activo/Certificado".
PRODUCTION_PHASE = "En Producción"

# Estados de proyecto que cuentan sus cajas como "Configuradas" (regla de negocio).
CONFIGURED_STATUSES = {"culminado", "implementado parcial"}


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

    Reglas de negocio (confirmadas por el usuario):
      - PVV Asignados = Cajas × (Bancos × Productos) [teórico, = compute_project_pvv,
        robusto a Multi-RIF para coincidir con el Reporte de Carga].
      - Cajas Asignadas = total de cajas del proyecto.
      - Cajas Configuradas = total de cajas SOLO si el estado del proyecto es
        'Culminado' o 'Implementado parcial' (no depende del avance interno).
      - PVV Configurados = Σ terminales en 'En Producción' por combo Banco/Producto.
        En multitienda/Multi-RIF se baja al nivel de tienda (suma por tienda).
      - Proyectos digitales (GATEWAY/LINK_PAGO): bloque físico = 0/0 (no hay cajas).
    """
    is_digital = (project.get("quote_type") or "") in DIGITAL_QUOTE_TYPES
    cajas = _total_cajas(project)
    pvv_asignados = compute_project_pvv(project)

    # PVV Configurados — granular por fase de producción.
    # En multitienda/Multi-RIF el avance vive en las tiendas → se suma por tienda
    # (evita doble conteo con la matriz plantilla del proyecto).
    stores = project.get("stores") or []
    if stores:
        pvv_configurados = sum(_production_processed(s.get("implementation_matrix")) for s in stores)
    else:
        pvv_configurados = _production_processed(project.get("implementation_matrix"))
    if pvv_asignados > 0:
        pvv_configurados = min(pvv_configurados, pvv_asignados)

    # Cajas Configuradas — atado estrictamente al estado global del proyecto.
    status_norm = (project.get("status") or "").strip().lower()
    is_configured = status_norm in CONFIGURED_STATUSES

    if is_digital:
        cajas_asignadas = 0
        cajas_configuradas = 0
    else:
        cajas_asignadas = cajas
        cajas_configuradas = cajas if is_configured else 0

    return {
        "cajas_asignadas": cajas_asignadas,
        "cajas_configuradas": cajas_configuradas,
        "pvv_asignados": pvv_asignados,
        "pvv_configurados": pvv_configurados,
    }
