"""
permissions_catalog.py — Fuente única de verdad del sistema de permisos.

Define:
- MENU_GROUPS: grupos principales (Nivel 1) con toggle Activo/Inactivo.
- MODULES: submódulos (Nivel 2) con nivel Inactivo/Consulta/Edición Total.
- SPECIAL_PERMISSIONS: funciones especiales (checkbox) que rompen la restricción "Consulta".
- ADMIN_ONLY_ACTIONS: acciones restringidas por código únicamente al rol admin.
- Helpers: get_default_menu_groups, module_to_group, is_module_enabled.
"""
from typing import Optional

# ============================================================
# NIVEL 1 — Grupos de menú
# ============================================================
MENU_GROUPS = [
    {"id": "dashboard", "name": "Dashboard"},
    {"id": "gestion_comercial", "name": "Gestión Comercial"},
    {"id": "catalogos", "name": "Catálogos"},
    {"id": "gestion_implementacion", "name": "Gestión de Implementación"},
    {"id": "nuevos_productos", "name": "Nuevos Productos"},
    {"id": "gestion_administrativa", "name": "Gestión Administrativa"},
    {"id": "gestion_taller", "name": "Gestión de Taller"},
]

# ============================================================
# NIVEL 2 — Módulos/pantallas con nivel Inactivo / Consulta / Edición Total
# Los valores internos siguen siendo `none|read|edit` por retro-compat.
# ============================================================
PERMISSION_LEVELS = ["none", "read", "edit"]
LEVEL_LABELS = {
    "none": "Inactivo",
    "read": "Consulta",
    "edit": "Edición Total",
}

MODULES = [
    # Gestión Comercial
    {"id": "initial_contacts", "name": "Contacto Inicial", "group": "gestion_comercial"},
    {"id": "clientes",          "name": "Clientes",          "group": "gestion_comercial"},
    {"id": "cotizaciones",      "name": "Cotizaciones",      "group": "gestion_comercial"},
    {"id": "reportes_ventas",   "name": "Reportes de Ventas", "group": "gestion_comercial"},
    {"id": "quote_history",     "name": "Histórico de Cotizaciones", "group": "gestion_comercial"},
    # Catálogos
    {"id": "bancos",                "name": "Bancos",               "group": "catalogos"},
    {"id": "medios_pago",           "name": "Medios de Pago",       "group": "catalogos"},
    {"id": "dispositivos",          "name": "Bienes y Servicios",   "group": "catalogos"},
    {"id": "commercial_categories", "name": "Categoría Comercial",  "group": "catalogos"},
    {"id": "exchange_rate",         "name": "Tasa de Cambio",       "group": "catalogos"},
    # Implementación
    {"id": "proyectos",         "name": "Proyectos",          "group": "gestion_implementacion"},
    {"id": "proyectos_directos","name": "Proyectos Directos", "group": "gestion_implementacion"},
    {"id": "integradores",      "name": "Integradores",       "group": "gestion_implementacion"},
    # Nuevos Productos
    {"id": "nuevos_productos", "name": "Nuevos Productos", "group": "nuevos_productos"},
    # Administrativa
    {"id": "inventarios",        "name": "Inventarios",         "group": "gestion_administrativa"},
    {"id": "reportes_contables", "name": "Reportes Contables",  "group": "gestion_administrativa"},
    # Taller
    {"id": "taller_equipos", "name": "Gestión de Taller", "group": "gestion_taller"},
    # Configuración (legacy, sin grupo visible)
    {"id": "configuracion", "name": "Configuración", "group": "gestion_administrativa"},
    {"id": "config_otras_acciones", "name": "Configuración de Otras Acciones", "group": "gestion_administrativa"},
]

MODULE_IDS = [m["id"] for m in MODULES]
MODULE_TO_GROUP = {m["id"]: m["group"] for m in MODULES}

# ============================================================
# Funciones Especiales (checkbox). Formato flag: "modulo:accion"
# ============================================================
SPECIAL_PERMISSIONS = [
    # Proyectos
    {"id": "proyectos:create", "module": "proyectos",
     "label": "Crear Proyecto de Integración",
     "description": "Permite crear nuevos proyectos aunque tenga nivel Consulta."},
    # Cotizaciones (segmentación funcional)
    {"id": "cotizaciones:impl_pyme", "module": "cotizaciones",
     "label": "Generar Implementaciones Pyme",
     "description": "Habilita generación de cotizaciones de implementación Pyme."},
    {"id": "cotizaciones:impl_corp", "module": "cotizaciones",
     "label": "Generar Implementaciones Corporativas",
     "description": "Habilita generación de cotizaciones de implementación Corporativa."},
    {"id": "cotizaciones:equipos", "module": "cotizaciones",
     "label": "Generar Equipos y Accesorios",
     "description": "Habilita generación de cotizaciones de venta de equipos."},
    {"id": "cotizaciones:reparaciones", "module": "cotizaciones",
     "label": "Generar Reparaciones",
     "description": "Habilita generación de cotizaciones de reparación."},
    # Inventarios
    {"id": "inventarios:create_warehouse", "module": "inventarios",
     "label": "Nuevo Almacén",
     "description": "Permite crear y parametrizar nuevas sedes/ubicaciones."},
    # Integradores (legacy)
    {"id": "integradores:create", "module": "integradores",
     "label": "Crear Integrador",
     "description": "Permite crear nuevos integradores con nivel Consulta."},
    # Reportes de Ventas
    {"id": "reportes_ventas:executive_summary", "module": "reportes_ventas",
     "label": "Generar Resumen Ejecutivo PDF",
     "description": "Habilita la descarga del Resumen Ejecutivo (PDF consolidado de los 8 reportes). Útil para gerencia."},
]

SPECIAL_FLAG_IDS = [s["id"] for s in SPECIAL_PERMISSIONS]

# ============================================================
# Acciones RESTRINGIDAS AL ADMIN (hardcoded, nunca asignables)
# ============================================================
ADMIN_ONLY_ACTIONS = [
    {"id": "integradores:bulk_delete", "label": "Vaciar Base de Datos de Integradores"},
    {"id": "integradores:import",      "label": "Importar Data de Integradores"},
    {"id": "proyectos:delete",         "label": "Eliminar Proyecto"},
    {"id": "taller_equipos:delete",    "label": "Eliminar Equipo de Taller"},
]

# ============================================================
# Helpers
# ============================================================
def get_default_menu_groups(active: bool = True) -> dict:
    """Devuelve dict {group_id: bool} con todos los grupos en el estado dado."""
    return {g["id"]: active for g in MENU_GROUPS}


def get_default_permissions(level: str = "read") -> dict:
    """Devuelve dict {module_id: level} con el nivel por default para todos los módulos."""
    return {m["id"]: level for m in MODULES}


def module_to_group(module_id: str) -> Optional[str]:
    return MODULE_TO_GROUP.get(module_id)


def is_module_enabled(user: dict, module_id: str) -> bool:
    """Verifica que el grupo padre del módulo esté activo para el usuario.
    Si el usuario no tiene menu_groups (legacy), se considera activo por compatibilidad."""
    if user.get("role") == "admin":
        return True
    groups = user.get("menu_groups") or {}
    if not groups:
        return True  # legacy user — backward compatible
    group_id = module_to_group(module_id)
    if not group_id:
        return True
    return bool(groups.get(group_id, True))


def build_catalog() -> dict:
    """Payload para el frontend: estructura completa de permisos."""
    return {
        "menu_groups": MENU_GROUPS,
        "modules": MODULES,
        "levels": [{"value": lv, "label": LEVEL_LABELS[lv]} for lv in PERMISSION_LEVELS],
        "special_permissions": SPECIAL_PERMISSIONS,
        "admin_only_actions": ADMIN_ONLY_ACTIONS,
    }


# ============================================================
# CEILING HELPERS — Jerarquía Perfil → Usuario
# ============================================================
LEVEL_RANK = {"none": 0, "read": 1, "edit": 2}


def level_within_ceiling(user_level: str, profile_level: str) -> bool:
    """True si user_level <= profile_level en la jerarquía de permisos."""
    ul = LEVEL_RANK.get(user_level or "none", 0)
    pl = LEVEL_RANK.get(profile_level or "none", 0)
    return ul <= pl


def enforce_permissions_ceiling(user_perms: dict, profile_perms: dict) -> dict:
    """Ajusta user_perms para que ningún módulo exceda el nivel del perfil.
    Retorna un nuevo dict con los ajustes aplicados (recorta hacia abajo)."""
    out = {}
    for module_id, user_lv in (user_perms or {}).items():
        profile_lv = (profile_perms or {}).get(module_id, "edit")
        out[module_id] = user_lv if level_within_ceiling(user_lv, profile_lv) else profile_lv
    return out


def enforce_groups_ceiling(user_groups: dict, profile_groups: dict) -> dict:
    """Si el perfil tiene un grupo Inactivo, el user también lo tendrá inactivo."""
    out = {}
    for gid, user_active in (user_groups or {}).items():
        profile_active = (profile_groups or {}).get(gid, True)
        out[gid] = bool(user_active) and bool(profile_active)
    # Copiar los del perfil que no están en user
    for gid, profile_active in (profile_groups or {}).items():
        if gid not in out:
            out[gid] = bool(profile_active)
    return out


def enforce_specials_ceiling(user_flags: list, profile_flags: list) -> list:
    """El user solo puede tener flags que su perfil también tenga."""
    profile_set = set(profile_flags or [])
    return [f for f in (user_flags or []) if f in profile_set]
