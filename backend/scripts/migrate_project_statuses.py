"""Migración única: mapea los estados antiguos de proyectos al nuevo catálogo.

Catálogo nuevo: Por asignar · Asignado · En Gestión · Suspendido ·
                Implementado parcial · Culminado

Reglas de mapeo (aprobadas por el usuario):
  - "Pendiente por Asignar"            -> "Por asignar"
  - "Asignado / En Proceso"            -> "Asignado" (o "En Gestión" si ya tiene ticket)
  - "En proceso/reasignado"            -> "Asignado" (o "En Gestión" si ya tiene ticket)
  - "Suspendido por Cliente"/"...Banco"-> "Suspendido"
  - "Finalizado / Producción"          -> "Culminado"
  - Legacy: "En Implementación"        -> "En Gestión"
  - Legacy: "Completado"/"Finalizado"  -> "Culminado"
  - Legacy: "Cancelado"                -> "Suspendido"

Idempotente: los proyectos que ya tengan un estado del nuevo catálogo se omiten.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import db  # noqa: E402

NEW_STATUSES = {"Por asignar", "Asignado", "En Gestión", "Suspendido", "Implementado parcial", "Culminado"}

DIRECT_MAP = {
    "Pendiente por Asignar": "Por asignar",
    "Suspendido por Cliente": "Suspendido",
    "Suspendido por Banco": "Suspendido",
    "Finalizado / Producción": "Culminado",
    "En Implementación": "En Gestión",
    "Completado": "Culminado",
    "Finalizado": "Culminado",
    "Cancelado": "Suspendido",
}
# Estos dependen de si el proyecto ya tiene Nro de Ticket cargado.
TICKET_DEPENDENT = {"Asignado / En Proceso", "En proceso/reasignado"}


async def main():
    cursor = db.projects.find({}, {"_id": 0, "project_id": 1, "status": 1, "ticket_number": 1})
    total = 0
    migrated = 0
    skipped_ok = 0
    per_status = {}
    async for p in cursor:
        total += 1
        old = (p.get("status") or "").strip()
        if old in NEW_STATUSES:
            skipped_ok += 1
            continue
        if old in TICKET_DEPENDENT:
            new = "En Gestión" if (p.get("ticket_number") or "").strip() else "Asignado"
        else:
            new = DIRECT_MAP.get(old, "Por asignar")  # fallback seguro
        await db.projects.update_one(
            {"project_id": p["project_id"]},
            {"$set": {"status": new}},
        )
        migrated += 1
        per_status[f"{old or '(vacío)'} -> {new}"] = per_status.get(f"{old or '(vacío)'} -> {new}", 0) + 1

    print(f"Total proyectos: {total}")
    print(f"Ya en catálogo nuevo (omitidos): {skipped_ok}")
    print(f"Migrados: {migrated}")
    for k, v in sorted(per_status.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())
