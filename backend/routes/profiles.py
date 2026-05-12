"""
profiles.py — Maestro de Perfiles de Usuario.

Un perfil es una plantilla reutilizable de permisos que se asigna a usuarios.
El perfil define el "techo" (ceiling) — los usuarios solo pueden tener permisos
iguales o inferiores a los del perfil.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from config import db
from routes.auth import get_current_user
from permissions_catalog import (
    MODULE_IDS, MENU_GROUPS, SPECIAL_FLAG_IDS, PERMISSION_LEVELS,
    enforce_permissions_ceiling, enforce_groups_ceiling, enforce_specials_ceiling,
)

router = APIRouter(tags=["profiles"])


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    permissions: Optional[dict] = None        # {module_id: "none"|"read"|"edit"}
    menu_groups: Optional[dict] = None        # {group_id: bool}
    special_permissions: Optional[List[str]] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[dict] = None
    menu_groups: Optional[dict] = None
    special_permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


def _sanitize_profile_input(data: dict) -> dict:
    """Filtra permisos/grupos/flags inválidos."""
    out = {}
    if "permissions" in data and data["permissions"] is not None:
        out["permissions"] = {
            m: lv for m, lv in data["permissions"].items()
            if m in MODULE_IDS and lv in PERMISSION_LEVELS
        }
    if "menu_groups" in data and data["menu_groups"] is not None:
        valid_gids = {g["id"] for g in MENU_GROUPS}
        out["menu_groups"] = {g: bool(v) for g, v in data["menu_groups"].items() if g in valid_gids}
    if "special_permissions" in data and data["special_permissions"] is not None:
        out["special_permissions"] = [
            f for f in data["special_permissions"]
            if isinstance(f, str) and f in SPECIAL_FLAG_IDS
        ]
    return out


async def _require_admin(authorization: Optional[str]):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden gestionar perfiles")
    return user


# ============================================================
# CRUD
# ============================================================
@router.get("/admin/profiles")
async def list_profiles(authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    profiles = await db.profiles.find({}, {"_id": 0}).sort("name", 1).to_list(length=None)
    # Adjuntar user_count
    for p in profiles:
        p["user_count"] = await db.users.count_documents({"profile_id": p["profile_id"]})
    return profiles


@router.get("/admin/profiles/{profile_id}")
async def get_profile(profile_id: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    profile = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    profile["user_count"] = await db.users.count_documents({"profile_id": profile_id})
    return profile


@router.get("/admin/profiles/{profile_id}/users")
async def list_profile_users(profile_id: str, authorization: Optional[str] = Header(None)):
    """Auditoría: usuarios asignados a un perfil de seguridad.
    Devuelve datos mínimos para validación cruzada del Administrador
    (nombre, login, sede/departamento, estatus, role)."""
    await _require_admin(authorization)
    profile = await db.profiles.find_one(
        {"profile_id": profile_id}, {"_id": 0, "profile_id": 1, "name": 1}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    cursor = db.users.find(
        {"profile_id": profile_id},
        {
            "_id": 0,
            "user_id": 1,
            "email": 1,
            "first_name": 1,
            "last_name": 1,
            "name": 1,
            "cargo": 1,
            "sede": 1,
            "departamento": 1,
            "is_active": 1,
            "role": 1,
        },
    )
    users = [u async for u in cursor]

    def _full_name(u):
        if u.get("first_name") or u.get("last_name"):
            return f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        return u.get("name") or u.get("email") or ""

    users.sort(key=lambda u: _full_name(u).lower())
    return {
        "profile_id": profile["profile_id"],
        "profile_name": profile.get("name"),
        "total": len(users),
        "users": users,
    }


@router.post("/admin/profiles")
async def create_profile(data: ProfileCreate, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="El nombre del perfil es obligatorio")
    existing = await db.profiles.find_one({"name": data.name.strip()})
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe un perfil con ese nombre")

    now = datetime.now(timezone.utc).isoformat()
    clean = _sanitize_profile_input(data.model_dump())
    profile = {
        "profile_id": f"prof_{uuid.uuid4().hex[:10]}",
        "name": data.name.strip(),
        "description": (data.description or "").strip(),
        "permissions": clean.get("permissions", {m: "edit" for m in MODULE_IDS}),
        "menu_groups": clean.get("menu_groups", {g["id"]: True for g in MENU_GROUPS}),
        "special_permissions": clean.get("special_permissions", []),
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.profiles.insert_one(profile)
    profile["user_count"] = 0
    profile.pop("_id", None)
    return profile


@router.put("/admin/profiles/{profile_id}")
async def update_profile(profile_id: str, data: ProfileUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar un perfil. Al BAJAR un nivel, los usuarios vinculados se
    re-sincronizan automáticamente hacia abajo (comportamiento elegido: 1a)."""
    await _require_admin(authorization)
    profile = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    updates = {}
    raw = data.model_dump(exclude_unset=True)
    if "name" in raw and raw["name"]:
        other = await db.profiles.find_one({"name": raw["name"].strip(), "profile_id": {"$ne": profile_id}})
        if other:
            raise HTTPException(status_code=409, detail="Ya existe un perfil con ese nombre")
        updates["name"] = raw["name"].strip()
    if "description" in raw:
        updates["description"] = (raw["description"] or "").strip()
    if "is_active" in raw:
        updates["is_active"] = bool(raw["is_active"])

    sanitized = _sanitize_profile_input(raw)
    # Merge con los existentes
    new_perms = {**profile.get("permissions", {}), **sanitized.get("permissions", {})}
    new_groups = {**profile.get("menu_groups", {}), **sanitized.get("menu_groups", {})}
    new_specials = sanitized.get("special_permissions", profile.get("special_permissions", []))

    if "permissions" in sanitized:
        updates["permissions"] = new_perms
    if "menu_groups" in sanitized:
        updates["menu_groups"] = new_groups
    if "special_permissions" in sanitized:
        updates["special_permissions"] = new_specials

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.profiles.update_one({"profile_id": profile_id}, {"$set": updates})

    # Re-sincronización: recortar usuarios vinculados si exceden el nuevo techo.
    linked_users = await db.users.find({"profile_id": profile_id}, {"_id": 0}).to_list(length=None)
    for u in linked_users:
        new_u_perms = enforce_permissions_ceiling(u.get("permissions", {}), new_perms)
        new_u_groups = enforce_groups_ceiling(u.get("menu_groups", {}), new_groups)
        new_u_specials = enforce_specials_ceiling(u.get("special_permissions", []), new_specials)
        await db.users.update_one(
            {"user_id": u["user_id"]},
            {"$set": {
                "permissions": new_u_perms,
                "menu_groups": new_u_groups,
                "special_permissions": new_u_specials,
            }},
        )

    updated = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
    updated["user_count"] = await db.users.count_documents({"profile_id": profile_id})
    return updated


@router.delete("/admin/profiles/{profile_id}")
async def delete_profile(profile_id: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    profile = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    user_count = await db.users.count_documents({"profile_id": profile_id})
    if user_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar: {user_count} usuario(s) tiene(n) este perfil asignado",
        )
    await db.profiles.delete_one({"profile_id": profile_id})
    return {"message": "Perfil eliminado exitosamente"}


@router.post("/admin/profiles/{profile_id}/duplicate")
async def duplicate_profile(profile_id: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    source = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Perfil origen no encontrado")
    now = datetime.now(timezone.utc).isoformat()
    # Buscar nombre disponible
    base = f"{source['name']} (copia)"
    candidate = base
    n = 2
    while await db.profiles.find_one({"name": candidate}):
        candidate = f"{base} {n}"
        n += 1
    new_profile = {
        **source,
        "profile_id": f"prof_{uuid.uuid4().hex[:10]}",
        "name": candidate,
        "created_at": now,
        "updated_at": now,
    }
    await db.profiles.insert_one(new_profile)
    new_profile["user_count"] = 0
    new_profile.pop("_id", None)
    return new_profile


# ============================================================
# Asignar perfil a usuario
# ============================================================
@router.put("/admin/users/{user_id}/profile")
async def assign_profile_to_user(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asigna (o desasigna con profile_id=null) un perfil a un usuario.
    Al asignar, los permisos del perfil se COPIAN al usuario como línea base."""
    await _require_admin(authorization)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    profile_id = body.get("profile_id")
    if profile_id is None:
        # Desasignar
        await db.users.update_one({"user_id": user_id}, {"$set": {"profile_id": None}})
    else:
        profile = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0})
        if not profile:
            raise HTTPException(status_code=404, detail="Perfil no encontrado")
        # Copiar permisos del perfil como baseline del usuario
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "profile_id": profile_id,
                "permissions": profile.get("permissions", {}),
                "menu_groups": profile.get("menu_groups", {}),
                "special_permissions": list(profile.get("special_permissions", [])),
            }},
        )

    updated_user = await db.users.find_one(
        {"user_id": user_id}, {"_id": 0, "password_hash": 0}
    )
    return {"message": "Perfil asignado", "user": updated_user}
