"""Helper para concatenar abreviaturas de Medios de Pago de una cotización.

Construye el token `cotizacion.abreviaturas_medios_pago` que se expone en
plantillas de email y PDF. Recorre los items `additional` de la cotización
(que representan los medios de pago seleccionados por el ejecutivo),
identifica el service maestro de cada uno y concatena las abreviaturas
separadas por "/", omitiendo barras huérfanas y duplicados.
"""
from typing import Iterable, Optional
from config import db


def _normalize_separators(value: Optional[str]) -> str:
    """Elimina barras huérfanas al inicio/final y colapsa múltiples seguidas."""
    if not value:
        return ""
    parts = [p.strip() for p in value.split("/")]
    parts = [p for p in parts if p]
    return "/".join(parts)


def _extract_medio_pago_names(quote: dict) -> list[str]:
    """Devuelve la lista (en orden, sin duplicados) de nombres de medios de pago
    seleccionados en la cotización. Hoy un medio de pago vive como item
    `additional` con `medio_pago_name` (o `item_name` si no lo tiene).
    """
    seen: set[str] = set()
    out: list[str] = []
    services_list: Iterable[dict] = quote.get("services") or []
    additional_list: Iterable[dict] = quote.get("additional_items") or []
    for src in (services_list, additional_list):
        for it in src:
            if (it.get("item_type") or "") != "additional":
                # additional_items legacy (sin item_type) también cuentan
                if src is services_list:
                    continue
            name = (it.get("medio_pago_name") or it.get("item_name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
    return out


async def compute_abreviaturas_medios_pago(quote: dict) -> str:
    """Construye la cadena concatenada de abreviaturas para una cotización.

    Lee el catálogo `db.services` y resuelve la `abreviatura` de cada medio
    de pago. Si un service no tiene `abreviatura` setteada, cae al nombre
    completo del medio de pago (mejor algo legible que vacío).
    """
    names = _extract_medio_pago_names(quote)
    if not names:
        return ""

    # Buscar abreviaturas en el catálogo en un solo round-trip
    docs = await db.services.find(
        {"name": {"$in": names}},
        {"_id": 0, "name": 1, "abreviatura": 1},
    ).to_list(200)
    abrev_by_name = {
        d["name"]: (d.get("abreviatura") or "").strip() or d["name"]
        for d in docs
    }
    abreviaturas = []
    for n in names:
        abrev = abrev_by_name.get(n) or n  # fallback al nombre
        abrev = (abrev or "").strip()
        if abrev:
            abreviaturas.append(abrev)
    return _normalize_separators("/".join(abreviaturas))


def compute_abreviaturas_from_services_map(
    quote: dict, services_map: dict[str, str]
) -> str:
    """Variante síncrona que recibe un mapa precargado {service_name: abreviatura}.
    Útil cuando el caller ya tiene el catálogo en memoria.
    """
    names = _extract_medio_pago_names(quote)
    if not names:
        return ""
    abreviaturas = []
    for n in names:
        abrev = (services_map.get(n) or n).strip()
        if abrev:
            abreviaturas.append(abrev)
    return _normalize_separators("/".join(abreviaturas))
