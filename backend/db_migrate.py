"""
Script de Exportación/Importación de datos MongoDB para MegaNexus.
Uso:
  Exportar:  python3 db_migrate.py export
  Importar:  python3 db_migrate.py import

Después del deploy limpio, ejecutar:
  cd /app/backend && python3 db_migrate.py import
"""
import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient

# Colecciones a migrar — TODAS las operativas
COLLECTIONS = [
    # Usuarios y config
    "users",
    "config",
    "counters",
    # Maestros
    "warehouses",
    "banks",
    "services",
    "hardware",
    "fiscal_printer_models",
    "email_templates",
    "min_stock_config",
    # Datos operativos
    "clients",
    "client_logs",
    "integrators",
    "inventory_movements",
    "serial_assignments",
    "projects",
    "taller_equipos",
    "new_products",
    "quotes",
    "initial_contacts",
    # Tasas y contadores
    "exchange_rates",
    "historico_tasas_cambio",
    "nota_entrega_counter",
    "transfer_note_counter",
    # Pipeline nuevos productos
    "new_product_evolution",
    "np_responsable_assignments",
    "np_status_transitions",
    # Bancos
    "bank_evolution_log",
    # Media
    "uploaded_images",
    # Auditoría
    "audit_logs",
    "audit_exceptions",
    "email_logs",
]

EXPORT_DIR = Path("/app/db_export")


def serialize(doc):
    """Convierte ObjectId y otros tipos no serializables."""
    clean = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if hasattr(v, 'isoformat'):
            clean[k] = v.isoformat()
        elif isinstance(v, bytes):
            clean[k] = v.hex()
        else:
            clean[k] = v
    return clean


async def export_data():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {"exported_at": datetime.utcnow().isoformat(), "db": db_name, "collections": {}}
    total = 0

    for coll_name in COLLECTIONS:
        docs = []
        try:
            cursor = db[coll_name].find({})
            async for doc in cursor:
                docs.append(serialize(doc))
        except Exception:
            pass

        if not docs:
            print(f"  SKIP {coll_name}: vacia")
            continue

        filepath = EXPORT_DIR / f"{coll_name}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(docs, f, ensure_ascii=False, default=str)

        manifest["collections"][coll_name] = len(docs)
        total += len(docs)
        print(f"  OK   {coll_name}: {len(docs)} documentos")

    with open(EXPORT_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nExportacion completada: {total} documentos en {len(manifest['collections'])} colecciones")
    print(f"Archivos en: {EXPORT_DIR}")


async def import_data():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    manifest_path = EXPORT_DIR / "manifest.json"
    if not manifest_path.exists():
        print("ERROR: No se encontro manifest.json. Ejecute 'export' primero.")
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    print(f"Importando datos exportados el {manifest['exported_at']}")
    total = 0

    for coll_name, expected_count in manifest["collections"].items():
        filepath = EXPORT_DIR / f"{coll_name}.json"
        if not filepath.exists():
            print(f"  SKIP {coll_name}: archivo no encontrado")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            docs = json.load(f)

        if not docs:
            continue

        existing = await db[coll_name].count_documents({})
        if existing > 0:
            print(f"  WARN {coll_name}: ya tiene {existing} docs. Limpiando...")
            await db[coll_name].delete_many({})

        batch_size = 500
        for i in range(0, len(docs), batch_size):
            batch = docs[i:i+batch_size]
            await db[coll_name].insert_many(batch)

        total += len(docs)
        print(f"  OK   {coll_name}: {len(docs)} documentos importados")

    print(f"\nImportacion completada: {total} documentos en {len(manifest['collections'])} colecciones")
    print("Reinicie el backend: sudo supervisorctl restart backend")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("export", "import"):
        print("Uso: python3 db_migrate.py [export|import]")
        sys.exit(1)

    if sys.argv[1] == "export":
        asyncio.run(export_data())
    else:
        asyncio.run(import_data())
