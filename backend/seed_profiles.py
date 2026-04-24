"""Seed de perfiles base — idempotente. Se ejecuta al startup del backend."""
from datetime import datetime, timezone
import uuid
from config import db
from permissions_catalog import MODULE_IDS, MENU_GROUPS

ALL_GROUPS_ON = {g["id"]: True for g in MENU_GROUPS}


def _perms(overrides: dict = None) -> dict:
    """Devuelve todos los módulos en 'edit' salvo los overrides especificados."""
    base = {m: "edit" for m in MODULE_IDS}
    if overrides:
        base.update(overrides)
    return base


SEED_PROFILES = [
    {
        "name": "Vendedor Pyme",
        "description": "Ejecutivo comercial de segmento Pyme. Gestiona contactos, clientes y cotizaciones Pyme. Acceso de consulta a catálogos y proyectos.",
        "permissions": _perms({
            "bancos": "read", "medios_pago": "read", "dispositivos": "read",
            "commercial_categories": "read", "exchange_rate": "read",
            "proyectos": "read", "integradores": "read",
            "inventarios": "read", "reportes_contables": "read",
            "nuevos_productos": "none", "taller_equipos": "none", "configuracion": "none",
        }),
        "menu_groups": {**ALL_GROUPS_ON, "gestion_taller": False},
        "special_permissions": ["cotizaciones:impl_pyme", "cotizaciones:equipos"],
    },
    {
        "name": "Vendedor Corp",
        "description": "Ejecutivo comercial de segmento Corporativo. Similar a Pyme pero habilitado para cotizaciones Corp.",
        "permissions": _perms({
            "bancos": "read", "medios_pago": "read", "dispositivos": "read",
            "commercial_categories": "read", "exchange_rate": "read",
            "proyectos": "read", "integradores": "read",
            "inventarios": "read", "reportes_contables": "read",
            "nuevos_productos": "none", "taller_equipos": "none", "configuracion": "none",
        }),
        "menu_groups": {**ALL_GROUPS_ON, "gestion_taller": False},
        "special_permissions": ["cotizaciones:impl_corp", "cotizaciones:equipos"],
    },
    {
        "name": "Gerente Operativo",
        "description": "Supervisa equipos comerciales. Acceso amplio a módulos comerciales y de implementación.",
        "permissions": _perms({
            "configuracion": "read",
            "nuevos_productos": "read",
            "taller_equipos": "read",
        }),
        "menu_groups": ALL_GROUPS_ON.copy(),
        "special_permissions": [
            "cotizaciones:impl_pyme", "cotizaciones:impl_corp",
            "cotizaciones:equipos", "cotizaciones:reparaciones",
            "proyectos:create",
        ],
    },
    {
        "name": "Operador Taller",
        "description": "Opera exclusivamente la gestión de equipos en taller. Consulta mínima al resto del sistema.",
        "permissions": _perms({
            "initial_contacts": "none", "clientes": "none",
            "cotizaciones": "none", "quote_history": "none",
            "bancos": "none", "medios_pago": "none", "dispositivos": "read",
            "commercial_categories": "none", "exchange_rate": "none",
            "proyectos": "read", "integradores": "none",
            "inventarios": "read", "reportes_contables": "none",
            "nuevos_productos": "none", "configuracion": "none",
            "taller_equipos": "edit",
        }),
        "menu_groups": {
            **{g["id"]: False for g in MENU_GROUPS},
            "dashboard": True, "gestion_implementacion": True,
            "gestion_administrativa": True, "gestion_taller": True,
        },
        "special_permissions": ["cotizaciones:reparaciones"],
    },
]


async def seed_profiles_if_needed():
    """Crea los perfiles semilla solo si la colección está vacía."""
    count = await db.profiles.count_documents({})
    if count > 0:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    docs = []
    for p in SEED_PROFILES:
        docs.append({
            "profile_id": f"prof_{uuid.uuid4().hex[:10]}",
            "name": p["name"],
            "description": p["description"],
            "permissions": p["permissions"],
            "menu_groups": p["menu_groups"],
            "special_permissions": p["special_permissions"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    if docs:
        await db.profiles.insert_many(docs)
    return len(docs)
