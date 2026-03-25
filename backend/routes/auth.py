"""Route module: auth.py"""
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template
from models import *
import secrets
import hashlib
import re
import httpx

router = APIRouter()

# ==================== AUTH ENDPOINTS ====================

@router.post("/auth/session")
async def create_session(x_session_id: str = Header(...)):
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": x_session_id}
            )
            response.raise_for_status()
            session_data = response.json()
        
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        existing_user = await db.users.find_one({"email": session_data["email"]}, {"_id": 0})
        
        if existing_user:
            user_id = existing_user["user_id"]
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": session_data["name"],
                    "picture": session_data.get("picture")
                }}
            )
        else:
            user_doc = {
                "user_id": user_id,
                "email": session_data["email"],
                "name": session_data["name"],
                "picture": session_data.get("picture"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(user_doc)
        
        session_token = session_data["session_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        
        return {
            "session_token": session_token,
            "user": user
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")

@router.get("/auth/me")
async def get_me(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    # Retornar usuario sin password_hash
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "first_name": user.get("first_name", user.get("name", "").split()[0] if user.get("name") else ""),
        "last_name": user.get("last_name", " ".join(user.get("name", "").split()[1:]) if user.get("name") else ""),
        "name": user.get("name", f"{user.get('first_name', '')} {user.get('last_name', '')}"),
        "cedula": user.get("cedula", ""),
        "role": user.get("role", "user"),
        "sede": user.get("sede", "PYME"),  # Sede del usuario
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
        "permissions": user.get("permissions", {}),
        "picture": user.get("picture")
    }

@router.post("/auth/logout")
async def logout(authorization: Optional[str] = Header(None)):
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.replace("Bearer ", "")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    return {"message": "Logged out successfully"}

# ==================== NEW AUTH ENDPOINTS (Email/Password) ====================

@router.post("/auth/register")
async def register_user(user_data: UserRegister):
    """Registrar nuevo usuario con email y contraseña"""
    
    # Verificar si el email ya existe
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado")
    
    # Verificar si la cédula ya existe (solo si se proporcionó)
    if user_data.cedula:
        existing_cedula = await db.users.find_one({"cedula": user_data.cedula}, {"_id": 0})
        if existing_cedula:
            raise HTTPException(status_code=400, detail="La cédula ya está registrada")
    
    # Crear usuario
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(user_data.password)
    
    # Validar sede
    valid_sedes = ["PYME", "CORP"]
    sede = user_data.sede.upper() if user_data.sede else "PYME"
    if sede not in valid_sedes:
        raise HTTPException(status_code=400, detail="Sede inválida. Debe ser 'PYME' o 'CORP'")
    
    # Verificar si es el primer usuario (será admin)
    user_count = await db.users.count_documents({})
    is_first_user = user_count == 0
    
    # Permisos por defecto (admin tiene todo, usuario tiene lectura)
    default_permissions = {}
    for module in AVAILABLE_MODULES:
        default_permissions[module] = "edit" if is_first_user else "read"
    
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "password_hash": password_hash,
        "role": "admin" if is_first_user else "user",
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions,
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Crear sesión automáticamente
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Retornar usuario sin password
    user_response = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "role": user_doc["role"],
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions
    }
    
    return {
        "message": "Usuario registrado exitosamente",
        "session_token": session_token,
        "user": user_response
    }

@router.post("/auth/login")
async def login_user(credentials: UserLogin):
    """Login con email y contraseña"""
    
    # Buscar usuario
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Verificar si es un usuario de Google OAuth (sin password_hash)
    if "password_hash" not in user:
        raise HTTPException(
            status_code=400, 
            detail="Esta cuenta fue creada con Google. Por favor, use el inicio de sesión con Google."
        )
    
    # Verificar contraseña
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # Verificar si la cuenta está activa
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada. Contacte al administrador.")
    
    # Crear nueva sesión
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Retornar usuario sin password
    user_response = {
        "user_id": user["user_id"],
        "email": user["email"],
        "first_name": user.get("first_name", user.get("name", "").split()[0] if user.get("name") else ""),
        "last_name": user.get("last_name", " ".join(user.get("name", "").split()[1:]) if user.get("name") else ""),
        "name": user.get("name", f"{user.get('first_name', '')} {user.get('last_name', '')}"),
        "cedula": user.get("cedula", ""),
        "role": user.get("role", "user"),
        "cargo": user.get("cargo", ""),
        "departamento": user.get("departamento", ""),
        "sede": user.get("sede", "PYME"),
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
        "permissions": user.get("permissions", {}),
        "special_permissions": user.get("special_permissions", []),
        "almacen_asignado": user.get("almacen_asignado", None),
        "supervisor_id": user.get("supervisor_id", None),
        "supervisor_name": user.get("supervisor_name", None),
        "picture": user.get("picture")
    }
    
    return {
        "message": "Login exitoso",
        "session_token": session_token,
        "user": user_response
    }

# ==================== USERS LIST (para dropdowns) ====================

@router.get("/auth/users")
async def get_users_list(authorization: Optional[str] = Header(None)):
    """Obtener lista ligera de usuarios para selectores (gestor, asignación, etc.)"""
    await get_current_user(authorization)
    users = await db.users.find(
        {"is_active": True},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
    ).to_list(1000)
    for u in users:
        u["full_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return users


@router.get("/auth/ejecutivos")
async def get_ejecutivos(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios con cargo de Ejecutivo para asignación de clientes."""
    await get_current_user(authorization)
    ejecutivo_cargos = ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]
    users = await db.users.find(
        {"is_active": True, "cargo": {"$in": ejecutivo_cargos}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
    ).to_list(1000)
    for u in users:
        u["full_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return users


@router.get("/auth/implementadores")
async def get_implementadores(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios con cargo de Implementador para asignación de proyectos."""
    await get_current_user(authorization)
    users = await db.users.find(
        {"is_active": True, "cargo": "Implementador"},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1}
    ).to_list(1000)
    for u in users:
        u["full_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return users


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/users")
async def get_all_users(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver la lista de usuarios")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users

@router.put("/admin/users/{user_id}/permissions")
async def update_user_permissions(user_id: str, permissions: dict, authorization: Optional[str] = Header(None)):
    """Actualizar permisos de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar permisos")
    
    # Verificar que el usuario existe
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar permisos
    valid_permissions = {}
    for module in AVAILABLE_MODULES:
        if module in permissions:
            level = permissions[module]
            if level in PERMISSION_LEVELS:
                valid_permissions[module] = level
            else:
                valid_permissions[module] = "read"
        else:
            valid_permissions[module] = user.get("permissions", {}).get(module, "read")
    
    # Actualizar permisos
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"permissions": valid_permissions}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Permisos actualizados", "user": updated_user}

@router.put("/admin/users/{user_id}/special-permissions")
async def update_special_permissions(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar permisos especiales de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar permisos especiales")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    special_permissions = body.get("special_permissions", [])
    # Validar formato: cada elemento debe ser "modulo:accion"
    valid_flags = []
    for flag in special_permissions:
        if isinstance(flag, str) and ":" in flag:
            valid_flags.append(flag)
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"special_permissions": valid_flags}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Permisos especiales actualizados", "user": updated_user}

@router.put("/admin/users/{user_id}/almacen")
async def update_almacen_asignado(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asignar almacén a un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden asignar almacenes")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    almacen_id = body.get("almacen_asignado")
    
    # Validar que el almacén existe (si se proporciona uno)
    if almacen_id:
        wh = await db.warehouses.find_one({"warehouse_id": almacen_id}, {"_id": 0})
        if not wh:
            raise HTTPException(status_code=404, detail="Almacén no encontrado")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"almacen_asignado": almacen_id}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Almacén asignado actualizado", "user": updated_user}


@router.put("/admin/users/{user_id}/supervisor")
async def update_supervisor(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asignar supervisor a un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden asignar supervisores")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    supervisor_id = body.get("supervisor_id")
    supervisor_name = None
    
    if supervisor_id:
        # No puede ser su propio supervisor
        if supervisor_id == user_id:
            raise HTTPException(status_code=400, detail="Un usuario no puede ser su propio supervisor")
        supervisor = await db.users.find_one({"user_id": supervisor_id, "is_active": {"$ne": False}}, {"_id": 0})
        if not supervisor:
            raise HTTPException(status_code=404, detail="Supervisor no encontrado o inactivo")
        supervisor_name = f"{supervisor.get('first_name', '')} {supervisor.get('last_name', '')}".strip() or supervisor.get("email", "")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"supervisor_id": supervisor_id, "supervisor_name": supervisor_name}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Supervisor actualizado", "user": updated_user}



@router.put("/admin/users/{user_id}/role")
async def update_user_role(user_id: str, role: str, authorization: Optional[str] = Header(None)):
    """Actualizar rol de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar roles")
    
    # No permitir que el admin se quite el rol a sí mismo
    if current_user["user_id"] == user_id and role != "admin":
        raise HTTPException(status_code=400, detail="No puede quitarse el rol de administrador a sí mismo")
    
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Use 'admin' o 'user'")
    
    # Verificar que el usuario existe
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"role": role}}
    )
    
    return {"message": f"Rol actualizado a '{role}'"}

@router.put("/admin/users/{user_id}/status")
async def update_user_status(user_id: str, is_active: bool, authorization: Optional[str] = Header(None)):
    """Activar/desactivar un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar el estado de usuarios")
    
    # No permitir que el admin se desactive a sí mismo
    if current_user["user_id"] == user_id and not is_active:
        raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_active": is_active}}
    )
    
    # Si se desactiva, eliminar todas sus sesiones
    if not is_active:
        await db.user_sessions.delete_many({"user_id": user_id})
    
    return {"message": f"Usuario {'activado' if is_active else 'desactivado'}"}

@router.put("/admin/users/{user_id}")
async def update_user(user_id: str, user_data: UserUpdate, authorization: Optional[str] = Header(None)):
    """Actualizar datos de un usuario (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar usuarios")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Construir datos de actualización
    update_data = {}
    if user_data.first_name is not None:
        update_data["first_name"] = user_data.first_name
    if user_data.last_name is not None:
        update_data["last_name"] = user_data.last_name
    if user_data.first_name or user_data.last_name:
        fn = user_data.first_name or user.get("first_name", "")
        ln = user_data.last_name or user.get("last_name", "")
        update_data["name"] = f"{fn} {ln}"
    if user_data.cedula is not None:
        # Verificar que no exista otro usuario con esa cédula
        existing = await db.users.find_one({"cedula": user_data.cedula, "user_id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cédula")
        update_data["cedula"] = user_data.cedula
    if user_data.phone is not None:
        update_data["phone"] = user_data.phone
    if user_data.cargo is not None:
        update_data["cargo"] = user_data.cargo
    if user_data.departamento is not None:
        if user_data.departamento not in DEPARTAMENTOS and user_data.departamento != "":
            raise HTTPException(status_code=400, detail=f"Departamento inválido. Opciones: {DEPARTAMENTOS}")
        update_data["departamento"] = user_data.departamento
    if user_data.sede is not None:
        if user_data.sede not in ["PYME", "CORP"]:
            raise HTTPException(status_code=400, detail="Sede inválida. Use 'PYME' o 'CORP'")
        update_data["sede"] = user_data.sede
    if user_data.role is not None:
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Rol inválido. Use 'admin' o 'user'")
        # No permitir quitarse rol de admin a sí mismo
        if current_user["user_id"] == user_id and user_data.role != "admin":
            raise HTTPException(status_code=400, detail="No puede quitarse el rol de administrador")
        update_data["role"] = user_data.role
    if user_data.is_active is not None:
        if current_user["user_id"] == user_id and not user_data.is_active:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta")
        update_data["is_active"] = user_data.is_active
        if not user_data.is_active:
            await db.user_sessions.delete_many({"user_id": user_id})
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user["user_id"]
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": update_data}
    )
    
    # Registrar auditoría
    audit_log = {
        "action": "user_updated",
        "user_id": user_id,
        "changes": list(update_data.keys()),
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Usuario actualizado", "user": updated_user}

@router.post("/admin/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, authorization: Optional[str] = Header(None)):
    """Enviar token de restablecimiento de contraseña (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden restablecer contraseñas")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Generar token de un solo uso
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Guardar token en la base de datos
    await db.password_reset_tokens.delete_many({"user_id": user_id})  # Eliminar tokens anteriores
    await db.password_reset_tokens.insert_one({
        "user_id": user_id,
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["user_id"]
    })
    
    # Registrar auditoría
    audit_log = {
        "action": "password_reset_requested",
        "user_id": user_id,
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    # TODO: Enviar email con el token cuando Resend esté configurado
    # Por ahora, devolver el token para pruebas
    return {
        "message": "Token de restablecimiento generado",
        "email": user.get("email"),
        "reset_token": reset_token,  # En producción, esto NO se devuelve
        "expires_at": expires_at.isoformat(),
        "note": "El token debe ser enviado por correo electrónico al usuario"
    }

@router.post("/admin/users/create")
async def admin_create_user(user_data: UserRegister, authorization: Optional[str] = Header(None)):
    """Crear un nuevo usuario desde el panel de administración"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear usuarios")
    
    # Verificar si el email ya existe
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo electrónico")
    
    # Verificar si la cédula ya existe (solo si se proporcionó)
    if user_data.cedula:
        existing_cedula = await db.users.find_one({"cedula": user_data.cedula}, {"_id": 0})
        if existing_cedula:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cédula")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = hash_password(user_data.password)
    
    valid_sedes = ["PYME", "CORP"]
    sede = user_data.sede.upper() if user_data.sede else "PYME"
    if sede not in valid_sedes:
        raise HTTPException(status_code=400, detail="Sede inválida")
    
    default_permissions = {}
    for module in AVAILABLE_MODULES:
        default_permissions[module] = "read"
    
    user_doc = {
        "user_id": user_id,
        "email": user_data.email,
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "name": f"{user_data.first_name} {user_data.last_name}",
        "cedula": user_data.cedula,
        "phone": user_data.phone,
        "cargo": user_data.cargo,
        "departamento": user_data.departamento,
        "password_hash": password_hash,
        "role": "user",
        "sede": sede,
        "is_active": True,
        "is_verified": False,
        "permissions": default_permissions,
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user["user_id"]
    }
    
    await db.users.insert_one(user_doc)
    user_doc.pop('_id', None)
    
    # Registrar auditoría
    audit_log = {
        "action": "user_created",
        "user_id": user_id,
        "performed_by": current_user["user_id"],
        "performed_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await db.audit_logs.insert_one(audit_log)
    
    # Respuesta sin password
    user_response = {k: v for k, v in user_doc.items() if k != "password_hash"}
    return {"message": "Usuario creado exitosamente", "user": user_response}

@router.get("/admin/users/{user_id}/audit")
async def get_user_audit_log(user_id: str, authorization: Optional[str] = Header(None)):
    """Obtener historial de auditoría de un usuario"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver auditorías")
    
    logs = await db.audit_logs.find(
        {"user_id": user_id}, 
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    
    return logs

@router.get("/admin/departamentos")
async def get_departamentos(authorization: Optional[str] = Header(None)):
    """Obtener lista de departamentos disponibles"""
    await get_current_user(authorization)
    return DEPARTAMENTOS

@router.get("/admin/cargos")
async def get_cargos(authorization: Optional[str] = Header(None)):
    """Obtener lista de cargos disponibles"""
    await get_current_user(authorization)
    return CARGOS

