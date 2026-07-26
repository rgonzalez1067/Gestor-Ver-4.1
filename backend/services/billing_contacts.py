"""Matriz_Contactos_Facturacion (V6).

Compila una estructura ligera [{"nombre", "email"}] consolidando los contactos
de facturación en los TRES niveles jerárquicos del cliente:
  1) Grupo Económico (vinculado al Principal)
  2) RIF Principal
  3) Sucursal (contactos locales)

Filtro estricto: solo contactos con el propósito 'facturacion' explícitamente
marcado en su perfilamiento de procesos (`purposes`). Deduplica por email
(case-insensitive) conservando la primera aparición según jerarquía
(Grupo → Principal → Sucursal).
"""
from __future__ import annotations

from html import escape
from typing import List, Dict, Optional

from config import db

FACTURACION_PURPOSE = "facturacion"


def _contact_name(c: dict) -> str:
    return (
        (c.get("full_name") or c.get("name") or "").strip()
        or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
    )


def _has_facturacion(c: dict) -> bool:
    """Estricto: el contacto debe tener 'facturacion' en su lista de propósitos."""
    p = c.get("purposes")
    return isinstance(p, list) and FACTURACION_PURPOSE in p


def _collect(src_doc: Optional[dict], out: list) -> None:
    if not src_doc:
        return
    for c in (src_doc.get("contacts") or []):
        email = (c.get("email") or "").strip()
        if not email or not _has_facturacion(c):
            continue
        out.append({"nombre": _contact_name(c) or "—", "email": email})


async def compute_billing_matrix(client_id: Optional[str]) -> List[Dict[str, str]]:
    """Devuelve [{"nombre","email"}] de contactos de facturación (3 niveles),
    deduplicados por email en orden jerárquico Grupo → Principal → Sucursal."""
    if not client_id:
        return []
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return []

    # Resolver Principal (si el cliente es una sucursal, su Principal es el padre).
    principal = client
    if client.get("is_branch") and client.get("parent_client_id"):
        p = await db.clients.find_one({"client_id": client["parent_client_id"]}, {"_id": 0})
        if p:
            principal = p

    ordered: list = []

    # Nivel 1: Grupo Económico vinculado al Principal.
    gid = principal.get("grupo_economico_id")
    if gid:
        grp = await db.economic_groups.find_one({"group_id": gid}, {"_id": 0, "contacts": 1})
        _collect(grp, ordered)

    # Nivel 2: RIF Principal.
    _collect(principal, ordered)

    # Nivel 3: Sucursal (contactos locales), solo si el cliente NO es el Principal.
    if client.get("client_id") != principal.get("client_id"):
        _collect(client, ordered)

    # Dedup por email (case-insensitive), preservando el primero (jerarquía).
    seen = set()
    result: List[Dict[str, str]] = []
    for item in ordered:
        key = item["email"].lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def render_billing_matrix_html(matrix: List[Dict[str, str]]) -> str:
    """Renderiza la matriz como 'Nombre <email>' por línea (HTML, escapado)."""
    if not matrix:
        return ""
    lines = [f"{escape(m.get('nombre') or '')} &lt;{escape(m.get('email') or '')}&gt;" for m in matrix]
    return "<br>".join(lines)


async def build_billing_matrix_var(quote: dict) -> str:
    """Helper para el motor de plantillas: usa la matriz almacenada en la
    cotización si existe; si no, la recalcula en vivo desde el client_id."""
    matrix = quote.get("Matriz_Contactos_Facturacion")
    if not isinstance(matrix, list):
        matrix = await compute_billing_matrix(quote.get("client_id"))
    return render_billing_matrix_html(matrix)
