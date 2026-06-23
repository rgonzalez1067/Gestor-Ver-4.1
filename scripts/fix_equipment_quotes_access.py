#!/usr/bin/env python3
"""
Diagnóstico + reparación de acceso a "Cotizaciones de Equipos".

Caso: un usuario (ej. Anderson Godoy) no ve en el menú las acciones de
Cotizaciones de Equipos, aunque el Override de Acciones esté liberado.

POR QUÉ: la visibilidad NO depende del Override de Acciones, sino del permiso
especial `cotizaciones:equipos`. Para ver el botón/menú el usuario necesita:
  1) permissions['cotizaciones'] == 'edit'  (canEdit)
  2) grupo de menú 'gestion_comercial' activo (o sin menu_groups = legacy activo)
  3) `cotizaciones:equipos` en sus permisos especiales EFECTIVOS
     (efectivo = union(perfil.special_permissions, usuario.special_permissions))
     con REGLA DE TECHO: el usuario solo puede tenerlo si su PERFIL también lo tiene.

USO (en el entorno de Deploy/producción, desde /app):
  # Solo diagnóstico (no escribe nada):
  python scripts/fix_equipment_quotes_access.py "Anderson Godoy"
  python scripts/fix_equipment_quotes_access.py anderson@empresa.com

  # Aplicar la reparación:
  python scripts/fix_equipment_quotes_access.py "Anderson Godoy" --apply

El script lee MONGO_URL y DB_NAME del entorno (o de backend/.env).
Es IDEMPOTENTE y seguro: por defecto NO escribe (dry-run); requiere --apply.
"""
import os
import sys

FLAG = "cotizaciones:equipos"
MODULE = "cotizaciones"
GROUP = "gestion_comercial"


def _load_env():
    """Carga MONGO_URL/DB_NAME del entorno o de backend/.env."""
    mongo = os.environ.get("MONGO_URL")
    dbname = os.environ.get("DB_NAME")
    if mongo and dbname:
        return mongo, dbname
    # Fallback: parsear backend/.env
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, "..", "backend", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "MONGO_URL" and not mongo:
                    mongo = v
                if k == "DB_NAME" and not dbname:
                    dbname = v
    return mongo, dbname


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if not args:
        print("Uso: python scripts/fix_equipment_quotes_access.py \"<Nombre o email>\" [--apply]")
        sys.exit(1)
    query_str = args[0].strip()

    mongo_url, db_name = _load_env()
    if not mongo_url or not db_name:
        print("ERROR: No se encontró MONGO_URL/DB_NAME en el entorno ni en backend/.env")
        sys.exit(2)

    try:
        from pymongo import MongoClient
    except ImportError:
        print("ERROR: pymongo no disponible. Ejecuta dentro del entorno del backend.")
        sys.exit(2)

    client = MongoClient(mongo_url)
    db = client[db_name]

    # --- Localizar usuario (por nombre contiene, o email exacto) ---
    import re
    rx = re.compile(re.escape(query_str), re.IGNORECASE)
    user = db.users.find_one({"$or": [
        {"email": rx},
        {"name": rx},
        {"full_name": rx},
    ]})
    if not user:
        print(f"❌ No se encontró ningún usuario que coincida con: '{query_str}'")
        # Sugerencias
        sims = list(db.users.find({"name": re.compile(query_str.split()[0], re.IGNORECASE)},
                                  {"_id": 0, "name": 1, "email": 1}).limit(10))
        if sims:
            print("   Coincidencias parciales:")
            for s in sims:
                print(f"     - {s.get('name')}  <{s.get('email')}>")
        sys.exit(3)

    name = user.get("name") or user.get("full_name") or user.get("email")
    role = user.get("role")
    perms = user.get("permissions") or {}
    cot_level = perms.get(MODULE, "none")
    menu_groups = user.get("menu_groups") or {}
    group_active = (len(menu_groups) == 0) or bool(menu_groups.get(GROUP))
    user_sp = list(user.get("special_permissions") or [])

    profile = None
    profile_sp = []
    if user.get("profile_id"):
        profile = db.profiles.find_one({"profile_id": user["profile_id"]})
        profile_sp = list((profile or {}).get("special_permissions") or [])

    effective_sp = sorted(set(user_sp) | set(profile_sp))
    is_admin = role == "admin"
    has_equipos = is_admin or (FLAG in effective_sp)
    can_edit = is_admin or (cot_level == "edit" and group_active)

    print("=" * 70)
    print(f"DIAGNÓSTICO — Acceso a Cotizaciones de Equipos")
    print("=" * 70)
    print(f"Usuario           : {name}  <{user.get('email')}>")
    print(f"user_id           : {user.get('user_id')}")
    print(f"role              : {role}")
    print(f"perfil            : {(profile or {}).get('name')}  (profile_id={user.get('profile_id')})")
    print("-" * 70)
    print(f"[1] permissions['{MODULE}'] : {cot_level}   -> canEdit requiere 'edit'  {'✅' if (is_admin or cot_level=='edit') else '❌'}")
    print(f"[2] grupo '{GROUP}' activo  : {group_active}  {'✅' if group_active else '❌'}")
    print(f"[3] special perms (usuario) : {user_sp}")
    print(f"    special perms (perfil)  : {profile_sp}")
    print(f"    EFECTIVOS               : {effective_sp}")
    print(f"    ¿incluye '{FLAG}'?       : {has_equipos}  {'✅' if has_equipos else '❌'}")
    print("-" * 70)
    visible = is_admin or (can_edit and has_equipos)
    print(f"RESULTADO: ¿Vería el menú de Cotizaciones de Equipos? -> {'✅ SÍ' if visible else '❌ NO'}")

    if visible:
        print("\nEl usuario YA cumple las condiciones. Si aún no lo ve:")
        print("  - Pídele que cierre sesión y vuelva a entrar (refrescar token/permisos).")
        print("  - Verifica que el grupo 'Gestión Comercial' esté activo en su perfil.")
        client.close()
        return

    # --- Plan de reparación ---
    fixes = []
    if not is_admin:
        if FLAG not in profile_sp:
            fixes.append(("profile_add_flag", f"Agregar '{FLAG}' a special_permissions del perfil '{(profile or {}).get('name')}'"))
        if FLAG not in user_sp:
            fixes.append(("user_add_flag", f"Agregar '{FLAG}' a special_permissions del usuario"))
        if cot_level != "edit":
            fixes.append(("user_set_edit", f"Set permissions['{MODULE}'] = 'edit' (estaba '{cot_level}')"))
        if menu_groups and not menu_groups.get(GROUP):
            fixes.append(("user_group_active", f"Activar grupo de menú '{GROUP}'"))

    print("\nPLAN DE REPARACIÓN:")
    for _, desc in fixes:
        print(f"   • {desc}")

    if not fixes:
        print("   (No hay cambios automáticos aplicables; revisar manualmente.)")
        client.close()
        return

    if not apply:
        print("\n⚠️  DRY-RUN: no se escribió nada. Para aplicar, repite el comando con  --apply")
        client.close()
        return

    # --- Aplicar ---
    print("\nAPLICANDO CAMBIOS...")
    for key, desc in fixes:
        if key == "profile_add_flag" and profile:
            db.profiles.update_one({"profile_id": user["profile_id"]},
                                   {"$addToSet": {"special_permissions": FLAG}})
            print(f"   ✅ {desc}")
        elif key == "user_add_flag":
            db.users.update_one({"user_id": user["user_id"]},
                                {"$addToSet": {"special_permissions": FLAG}})
            print(f"   ✅ {desc}")
        elif key == "user_set_edit":
            db.users.update_one({"user_id": user["user_id"]},
                                {"$set": {f"permissions.{MODULE}": "edit"}})
            print(f"   ✅ {desc}")
        elif key == "user_group_active":
            db.users.update_one({"user_id": user["user_id"]},
                                {"$set": {f"menu_groups.{GROUP}": True}})
            print(f"   ✅ {desc}")

    print("\n✅ Reparación aplicada. El usuario debe CERRAR SESIÓN y volver a entrar.")
    client.close()


if __name__ == "__main__":
    main()
