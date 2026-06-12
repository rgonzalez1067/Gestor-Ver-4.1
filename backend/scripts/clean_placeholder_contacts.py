"""
Limpieza de contactos placeholder heredados de importaciones masivas.

Contexto: muchos clientes tienen un campo legacy `contact2` con valores
placeholder ({name:'N/A', phone:'N/A', email:'na@na.com' | 'sin@email.com'})
que NO existen en la ficha real del cliente pero aparecían en la ventana de
"Destinatarios del Proyecto" (suggested-contacts).

Este script elimina (unset) únicamente los contactos legacy contact1/contact2
que coincidan con el patrón placeholder, y filtra arrays `contacts` de
clientes/bancos por si existieran. NO toca contactos reales.

Uso:  python -m scripts.clean_placeholder_contacts          (aplica cambios)
      python -m scripts.clean_placeholder_contacts --dry-run (solo reporta)
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_EMAILS = {"na@na.com", "sin@email.com", "n/a", "noemail@noemail.com"}
PLACEHOLDER_NAMES = {"n/a", "na", "sin nombre"}


def _is_placeholder(email: str, name: str) -> bool:
    em = (email or "").strip().lower()
    nm = (name or "").strip().lower()
    if em in PLACEHOLDER_EMAILS:
        return True
    # Nombre placeholder y sin email válido
    if nm in PLACEHOLDER_NAMES and ("@" not in em or em in PLACEHOLDER_EMAILS):
        return True
    return False


async def main(dry_run: bool):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    legacy_unset = 0
    clients_arr_cleaned = 0
    banks_arr_cleaned = 0

    # 1) Clientes: legacy contact1/contact2 placeholder -> $unset
    async for cl in db.clients.find({}, {"_id": 0, "client_id": 1, "contact1": 1, "contact2": 1, "contacts": 1}):
        unset = {}
        for k in ("contact1", "contact2"):
            lg = cl.get(k)
            if isinstance(lg, dict) and _is_placeholder(lg.get("email"), lg.get("name")):
                unset[k] = ""
        # 1b) Filtrar array contacts (defensivo)
        arr = cl.get("contacts") or []
        new_arr = [c for c in arr if not _is_placeholder(c.get("email"), c.get("full_name") or f"{c.get('first_name','')} {c.get('last_name','')}")]
        arr_changed = len(new_arr) != len(arr)

        update = {}
        if unset:
            update["$unset"] = unset
            legacy_unset += len(unset)
        if arr_changed:
            update.setdefault("$set", {})["contacts"] = new_arr
            clients_arr_cleaned += (len(arr) - len(new_arr))

        if update and not dry_run:
            await db.clients.update_one({"client_id": cl["client_id"]}, update)

    # 2) Bancos: filtrar array contacts (defensivo)
    async for bk in db.banks.find({}, {"_id": 0, "bank_id": 1, "name": 1, "contacts": 1}):
        arr = bk.get("contacts") or []
        new_arr = [c for c in arr if not _is_placeholder(c.get("email"), c.get("full_name") or f"{c.get('first_name','')} {c.get('last_name','')}")]
        if len(new_arr) != len(arr):
            banks_arr_cleaned += (len(arr) - len(new_arr))
            if not dry_run:
                await db.banks.update_one({"bank_id": bk.get("bank_id"), "name": bk.get("name")}, {"$set": {"contacts": new_arr}})

    mode = "[DRY-RUN] " if dry_run else ""
    print(f"{mode}Legacy contact1/contact2 placeholder eliminados (unset): {legacy_unset}")
    print(f"{mode}Contactos placeholder removidos de clients.contacts[]: {clients_arr_cleaned}")
    print(f"{mode}Contactos placeholder removidos de banks.contacts[]: {banks_arr_cleaned}")
    client.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    asyncio.run(main(dry))
