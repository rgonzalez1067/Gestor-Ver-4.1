"""Utility: Normalización fiscal de RIF (Venezuela).

Regla de negocio (Feb 2026):
- El RIF venezolano oficialmente tiene 10 caracteres: 1 letra (J/V/E/G/P/C) +
  9 dígitos numéricos.
- Cuando un cliente tiene RIF con ceros a la izquierda (ej. V-00012345-0),
  el origen de los datos suele almacenarlo abreviado (V12345). Esto produce
  errores legales y visuales en PDFs, reportes y notas de entrega.
- Esta utilidad rellena con ceros a la izquierda hasta alcanzar **9 dígitos
  numéricos**, preservando la letra inicial y el dígito verificador final
  si está separado por guión.

Comportamiento:
- "V12345"         → "V-000012345"
- "V-12345"        → "V-000012345"
- "V123456789"     → "V-123456789"   (ya tiene 9 dígitos, sólo formatea)
- "V-1234567-8"    → "V-001234567-8" (preserva guión + verificador)
- "12345"          → "000012345"     (sin letra, sólo padding)
- ""               → ""              (vacío se respeta)
- None             → ""
- "N/A"            → "N/A"           (placeholders se conservan)

Esta función debe ser la ÚNICA forma de presentar un RIF al usuario final
(PDFs, exports, pantallas). No debe usarse para almacenamiento o búsqueda
en MongoDB — la BD conserva el valor original.
"""
from __future__ import annotations
import re

_PLACEHOLDERS = {"N/A", "NA", "-", "—", "SIN RIF", "SIN_RIF"}
_RIF_LETTERS = set("JVEGPCjvegpc")


def format_rif(rif) -> str:
    """Normaliza RIF aplicando padding a 9 dígitos. Ver módulo docstring."""
    if rif is None:
        return ""
    s = str(rif).strip()
    if not s:
        return ""
    if s.upper() in _PLACEHOLDERS:
        return s

    # Detecta letra inicial (J/V/E/G/P/C). Si no hay, se asume puramente
    # numérico (caso raro pero válido en imports masivos).
    letter = ""
    rest = s
    if s[0] in _RIF_LETTERS:
        letter = s[0].upper()
        rest = s[1:].lstrip("-")  # quita guión opcional tras la letra

    # Detecta y separa el dígito verificador (último dígito tras un guión).
    verifier = ""
    if "-" in rest:
        # El último segmento es el verificador si es un solo dígito.
        parts = rest.split("-")
        if parts[-1].isdigit() and len(parts[-1]) == 1:
            verifier = parts[-1]
            rest = "-".join(parts[:-1])

    # Extrae sólo los dígitos del cuerpo (descarta cualquier separador interno)
    digits = re.sub(r"\D", "", rest)
    if not digits:
        # No hay dígitos para formatear — devolvemos el input original limpio
        return s

    # Padding a 9 dígitos exactos. Si tiene más, los respetamos (no truncamos).
    if len(digits) < 9:
        digits = digits.zfill(9)

    if letter and verifier:
        return f"{letter}-{digits}-{verifier}"
    if letter:
        return f"{letter}-{digits}"
    if verifier:
        return f"{digits}-{verifier}"
    return digits
