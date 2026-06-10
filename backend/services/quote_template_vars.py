"""Variables dinámicas a nivel de COTIZACIÓN para plantillas de correo.

Reutiliza los constructores HTML del entorno de Proyectos para que las
plantillas de Cotizaciones dispongan de las mismas tablas/variables que
dependen de la cotización: Matriz de Bancos/Productos, Matriz de Sucursales
y el Patrocinador.

Estas variables faltaban en los motores de correo de cotizaciones
(`notification_engine` y `workflow_notifications`), por lo que tokens como
{Matriz_Bancos_Productos} no se resolvían.
"""
from typing import Optional

from services.project_template_vars import _build_matrix_html, _build_stores_matrix_html


def _additional_items(quote: dict) -> list:
    """Items 'additional' (medios de pago con banco) de la cotización."""
    items = quote.get("additional_items") or []
    if not items:
        # Fallback: derivar desde services con item_type 'additional'
        items = [s for s in (quote.get("services") or []) if s.get("item_type") == "additional"]
    return items


def _matrix_from_additional_items(additional: list) -> dict:
    """Construye un dict {banco: {producto: {}}} a partir de additional_items."""
    matrix: dict = {}
    for it in additional:
        bank = (it.get("bank_name") or "").strip()
        name = (it.get("item_name") or it.get("name") or "").strip()
        if not bank or not name:
            continue
        matrix.setdefault(bank, {})[name] = {}
    return matrix


def build_quote_dynamic_vars(
    quote: dict,
    client_fantasy: str = "",
    client_legal: str = "",
) -> dict:
    """Devuelve las variables dinámicas de cotización para plantillas:
    Matriz_Bancos_Productos, Matriz_Sucursales y Patrocinador.
    """
    additional = _additional_items(quote)
    matrix = _matrix_from_additional_items(additional)
    matriz_bancos = _build_matrix_html(matrix, services=additional)

    # === Matriz de Sucursales — desde branch_details [{store_name, quantity}] ===
    branches = quote.get("branch_details") or []
    stores = [
        {
            "name": (b.get("store_name") or b.get("name") or "Sucursal"),
            "box_count": b.get("quantity") or b.get("box_count") or 0,
        }
        for b in branches
    ]
    matriz_sucursales = _build_stores_matrix_html(
        stores,
        fallback_name=client_fantasy or "Sede Principal",
        fallback_cajas=quote.get("cantidad_cajas"),
    )

    # === Patrocinador — banco/procesador si es patrocinada; si no, nombre de fantasía ===
    sponsored = quote.get("sponsored_implementation")
    sponsoring_bank = (quote.get("sponsoring_bank_name") or "").strip()
    sponsoring_processor = (quote.get("sponsoring_processor_name") or "").strip()
    if sponsored and sponsoring_bank:
        patrocinador = (
            f"{sponsoring_bank} - {sponsoring_processor}" if sponsoring_processor else sponsoring_bank
        )
    else:
        patrocinador = client_fantasy or client_legal or ""

    return {
        "Matriz_Bancos_Productos": matriz_bancos,
        "Matriz_Sucursales": matriz_sucursales,
        "Patrocinador": patrocinador,
    }
