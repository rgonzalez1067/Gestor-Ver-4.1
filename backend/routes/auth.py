"""Route module: auth.py"""
# ruff: noqa: F403, F405
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


# ==================== HELPER: Merge runtime profile + user perms ====================

async def _effective_special_permissions(user: dict) -> list:
    """Devuelve los special_permissions efectivos: union(profile.special_permissions, user.special_permissions).
    Esto permite que cambios en el perfil se reflejen automáticamente en todos los usuarios vinculados,
    sin necesidad de reasignarlos manualmente."""
    user_sp = list(user.get("special_permissions") or [])
    profile_id = user.get("profile_id")
    if not profile_id:
        return user_sp
    profile = await db.profiles.find_one({"profile_id": profile_id}, {"_id": 0, "special_permissions": 1})
    if not profile:
        return user_sp
    profile_sp = list(profile.get("special_permissions") or [])
    # Union preservando orden (perfil primero, luego user-only)
    seen = set()
    merged = []
    for sp in profile_sp + user_sp:
        if sp not in seen:
            seen.add(sp)
            merged.append(sp)
    return merged


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
    from permissions_catalog import get_default_menu_groups
    user = await get_current_user(authorization)
    # Auto-migración: si no tiene menu_groups, se asumen todos activos (legacy).
    menu_groups = user.get("menu_groups") or get_default_menu_groups(True)
    # Runtime merge: perfil ∪ usuario (cambios al perfil se propagan automáticamente)
    effective_sp = await _effective_special_permissions(user)
    # Retornar usuario sin password_hash
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "first_name": user.get("first_name", user.get("name", "").split()[0] if user.get("name") else ""),
        "last_name": user.get("last_name", " ".join(user.get("name", "").split()[1:]) if user.get("name") else ""),
        "name": user.get("name", f"{user.get('first_name', '')} {user.get('last_name', '')}"),
        "cedula": user.get("cedula", ""),
        "role": user.get("role", "user"),
        "cargo": user.get("cargo", ""),
        "departamento": user.get("departamento", ""),
        "sede": user.get("sede", "PYME"),  # Sede del usuario
        "is_active": user.get("is_active", True),
        "is_verified": user.get("is_verified", False),
        "permissions": user.get("permissions", {}),
        "special_permissions": effective_sp,
        "menu_groups": menu_groups,
        "profile_id": user.get("profile_id"),
        "almacen_asignado": user.get("almacen_asignado", None),
        "supervisor_id": user.get("supervisor_id", None),
        "supervisor_name": user.get("supervisor_name", None),
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
    
    # Enviar email de verificación
    try:
        verify_token = secrets.token_urlsafe(32)
        verify_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        await db.email_verification_tokens.delete_many({"user_id": user_id})
        await db.email_verification_tokens.insert_one({
            "user_id": user_id,
            "token": verify_token,
            "expires_at": verify_expires.isoformat(),
            "used": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")
        verify_link = f"{frontend_url}/verify-email?token={verify_token}"
        verify_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
          <div style="background:#003366;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;font-size:22px;">Gestor MegaNexus</h1>
          </div>
          <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
            <h2 style="color:#1e293b;margin-top:0;">Bienvenido a Gestor</h2>
            <p style="color:#475569;">Hola <strong>{user_data.first_name}</strong>,</p>
            <p style="color:#475569;">Tu cuenta ha sido creada. Verifica tu correo electrónico:</p>
            <div style="text-align:center;margin:25px 0;">
              <a href="{verify_link}" style="background:#16a34a;color:white;padding:12px 30px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">
                Verificar Correo
              </a>
            </div>
            <p style="color:#94a3b8;font-size:13px;">Este enlace expira en 24 horas.</p>
          </div>
        </div>
        """
        from services.email_service import send_email
        await send_email(
            to=[user_data.email],
            subject="Verifica tu Correo - Gestor MegaNexus",
            html=verify_html,
            action="email_verification"
        )
    except Exception as e:
        logging.error(f"[AUTH] Error enviando verificacion en registro: {e}")
    
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
    
    # Auto-migración menu_groups: si no existen, se marcan TODOS como activos (legacy).
    if not user.get("menu_groups"):
        from permissions_catalog import get_default_menu_groups
        default_groups = get_default_menu_groups(True)
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"menu_groups": default_groups}})
        user["menu_groups"] = default_groups
    
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

    # Runtime merge: perfil ∪ usuario para special_permissions
    effective_sp = await _effective_special_permissions(user)

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
        "special_permissions": effective_sp,
        "menu_groups": user.get("menu_groups") or {},
        "profile_id": user.get("profile_id"),
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
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1, "departamento": 1, "is_active": 1}
    ).to_list(1000)
    for u in users:
        u["full_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return users


@router.get("/auth/ejecutivos")
async def get_ejecutivos(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios con cargo de Ejecutivo para asignación de clientes."""
    await get_current_user(authorization)
    ventas_deptos = ["Ventas Pyme", "Ventas Corporativas"]
    users = await db.users.find(
        {"is_active": True, "departamento": {"$in": ventas_deptos}},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1, "departamento": 1}
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


@router.get("/auth/coordinadores")
async def get_coordinadores(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios con cargo de Coordinador en el departamento de Implementación."""
    await get_current_user(authorization)
    users = await db.users.find(
        {"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1, "departamento": 1}
    ).to_list(1000)
    for u in users:
        u["full_name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
    return users


# ==================== FORGOT / RESET PASSWORD (PUBLIC) ====================

@router.post("/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """Solicitar restablecimiento de contraseña. Envía email con enlace."""
    user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    # Siempre retornar éxito para no revelar si el email existe
    if not user:
        return {"message": "Si el correo existe, recibirás un enlace de recuperación."}

    user_id = user["user_id"]
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await db.password_reset_tokens.delete_many({"user_id": user_id})
    await db.password_reset_tokens.insert_one({
        "user_id": user_id,
        "token": reset_token,
        "expires_at": expires_at.isoformat(),
        "used": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    # Construir enlace de reset
    frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <div style="background:#003366;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="color:white;margin:0;font-size:22px;">Gestor MegaNexus</h1>
      </div>
      <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <h2 style="color:#1e293b;margin-top:0;">Recuperación de Contraseña</h2>
        <p style="color:#475569;">Hola <strong>{user.get('first_name', user.get('name', ''))}</strong>,</p>
        <p style="color:#475569;">Recibimos una solicitud para restablecer tu contraseña. Haz clic en el botón:</p>
        <div style="text-align:center;margin:25px 0;">
          <a href="{reset_link}" style="background:#003366;color:white;padding:12px 30px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">
            Restablecer Contraseña
          </a>
        </div>
        <p style="color:#94a3b8;font-size:13px;">Este enlace expira en 1 hora. Si no solicitaste este cambio, ignora este correo.</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
        <p style="color:#94a3b8;font-size:12px;text-align:center;">Gestor — Work Flow de Procesos Integrales</p>
      </div>
    </div>
    """

    try:
        from services.email_service import send_email
        await send_email(
            to=[data.email],
            subject="Recuperación de Contraseña — Gestor MegaNexus",
            html=html,
            action="password_reset"
        )
        logging.info(f"[AUTH] Email de reset enviado a {data.email}")
    except Exception as e:
        logging.error(f"[AUTH] Error enviando email de reset: {e}")
        # Log link for debugging when email fails
        logging.info(f"[AUTH] Reset link (email falló): {reset_link}")

    return {"message": "Si el correo existe, recibirás un enlace de recuperación."}


@router.post("/auth/reset-password")
async def reset_password(data: ResetPasswordRequest):
    """Restablecer contraseña usando token válido."""
    token_doc = await db.password_reset_tokens.find_one(
        {"token": data.token, "used": {"$ne": True}}, {"_id": 0}
    )
    if not token_doc:
        raise HTTPException(status_code=400, detail="Token inválido o ya utilizado")

    # Verificar expiración
    expires_at = datetime.fromisoformat(token_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="El token ha expirado. Solicita uno nuevo.")

    user_id = token_doc["user_id"]
    new_hash = hash_password(data.new_password)

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"password_hash": new_hash}}
    )

    # Marcar token como usado
    await db.password_reset_tokens.update_one(
        {"token": data.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Invalidar sesiones previas
    await db.user_sessions.delete_many({"user_id": user_id})

    logging.info(f"[AUTH] Contraseña restablecida para user_id={user_id}")
    return {"message": "Contraseña restablecida exitosamente. Ya puedes iniciar sesión."}


# ==================== EMAIL VERIFICATION ====================

@router.post("/auth/verify-email")
async def verify_email(data: VerifyEmailRequest):
    """Verificar email usando token."""
    token_doc = await db.email_verification_tokens.find_one(
        {"token": data.token, "used": {"$ne": True}}, {"_id": 0}
    )
    if not token_doc:
        raise HTTPException(status_code=400, detail="Token de verificación inválido o ya utilizado")

    expires_at = datetime.fromisoformat(token_doc["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="El token ha expirado. Solicita uno nuevo.")

    user_id = token_doc["user_id"]
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"is_verified": True}}
    )

    await db.email_verification_tokens.update_one(
        {"token": data.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}}
    )

    logging.info(f"[AUTH] Email verificado para user_id={user_id}")
    return {"message": "Correo electrónico verificado exitosamente."}


@router.post("/auth/resend-verification")
async def resend_verification(authorization: Optional[str] = Header(None)):
    """Reenviar email de verificación al usuario autenticado."""
    current_user = await get_current_user(authorization)

    if current_user.get("is_verified"):
        return {"message": "Tu correo ya está verificado."}

    user_id = current_user["user_id"]
    email = current_user["email"]
    name = current_user.get("first_name", current_user.get("name", ""))

    verify_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    await db.email_verification_tokens.delete_many({"user_id": user_id})
    await db.email_verification_tokens.insert_one({
        "user_id": user_id,
        "token": verify_token,
        "expires_at": expires_at.isoformat(),
        "used": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")
    verify_link = f"{frontend_url}/verify-email?token={verify_token}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
      <div style="background:#003366;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="color:white;margin:0;font-size:22px;">Gestor MegaNexus</h1>
      </div>
      <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
        <h2 style="color:#1e293b;margin-top:0;">Verificación de Correo</h2>
        <p style="color:#475569;">Hola <strong>{name}</strong>,</p>
        <p style="color:#475569;">Confirma tu correo electrónico haciendo clic en el botón:</p>
        <div style="text-align:center;margin:25px 0;">
          <a href="{verify_link}" style="background:#16a34a;color:white;padding:12px 30px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">
            Verificar Correo
          </a>
        </div>
        <p style="color:#94a3b8;font-size:13px;">Este enlace expira en 24 horas.</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
        <p style="color:#94a3b8;font-size:12px;text-align:center;">Gestor — Work Flow de Procesos Integrales</p>
      </div>
    </div>
    """

    try:
        from services.email_service import send_email
        await send_email(
            to=[email],
            subject="Verifica tu Correo — Gestor MegaNexus",
            html=html,
            action="email_verification"
        )
    except Exception as e:
        logging.error(f"[AUTH] Error enviando verificación: {e}")
        logging.info(f"[AUTH] Verify link (email falló): {verify_link}")

    return {"message": "Email de verificación enviado."}


# ==================== ADMIN ENDPOINTS ====================

@router.get("/admin/users")
async def get_all_users(authorization: Optional[str] = Header(None)):
    """Obtener lista de usuarios (solo admin)"""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver la lista de usuarios")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users

@router.get("/admin/permission-catalog")
async def get_permission_catalog(authorization: Optional[str] = Header(None)):
    """Devuelve la estructura completa del sistema de permisos para renderizado dinámico.
    Admin-only. Incluye grupos de menú, módulos, funciones especiales y acciones admin-only."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden consultar el catálogo")
    from permissions_catalog import build_catalog
    return build_catalog()


@router.put("/admin/users/{user_id}/menu-groups")
async def update_user_menu_groups(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar menu_groups de un usuario (Nivel 1 activo/inactivo). Solo admin.
    Ceiling: si el usuario tiene perfil, no puede activar un grupo que el perfil tenga inactivo."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar menu_groups")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    from permissions_catalog import MENU_GROUPS
    valid_group_ids = {g["id"] for g in MENU_GROUPS}
    incoming = body.get("menu_groups") or {}

    # Validar contra el perfil si el usuario tiene uno (ceiling).
    profile_groups = None
    if user.get("profile_id") and user.get("role") != "admin":
        profile = await db.profiles.find_one({"profile_id": user["profile_id"]}, {"_id": 0})
        if profile:
            profile_groups = profile.get("menu_groups") or {}
            for gid, active in incoming.items():
                if active and gid in valid_group_ids and not profile_groups.get(gid, True):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Acceso restringido: el perfil '{profile.get('name')}' no tiene activo el grupo '{gid}'.",
                    )

    current_groups = user.get("menu_groups") or {g["id"]: True for g in MENU_GROUPS}
    for gid, active in incoming.items():
        if gid in valid_group_ids:
            current_groups[gid] = bool(active)

    await db.users.update_one({"user_id": user_id}, {"$set": {"menu_groups": current_groups}})
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Menu groups actualizados", "user": updated_user}


@router.put("/admin/users/{user_id}/permissions")
async def update_user_permissions(user_id: str, permissions: dict, authorization: Optional[str] = Header(None)):
    """Actualizar permisos de un usuario (solo admin). Ceiling vs perfil."""
    current_user = await get_current_user(authorization)
    
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar permisos")
    
    # Verificar que el usuario existe
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Validar permisos — aceptar tanto módulos legacy (AVAILABLE_MODULES) como del catálogo nuevo (MODULE_IDS).
    from permissions_catalog import MODULE_IDS, LEVEL_RANK, LEVEL_LABELS

    # Si el usuario tiene perfil, aplicar ceiling: no aceptar niveles superiores al del perfil.
    profile_perms = None
    profile_name = None
    if user.get("profile_id") and user.get("role") != "admin":
        profile = await db.profiles.find_one({"profile_id": user["profile_id"]}, {"_id": 0})
        if profile:
            profile_perms = profile.get("permissions") or {}
            profile_name = profile.get("name")
            for module_id, new_lv in permissions.items():
                if module_id not in MODULE_IDS:
                    continue
                prof_lv = profile_perms.get(module_id, "edit")
                if LEVEL_RANK.get(new_lv, 0) > LEVEL_RANK.get(prof_lv, 2):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Acceso restringido: el nivel máximo para el perfil '{profile_name}' en '{module_id}' es '{LEVEL_LABELS.get(prof_lv, prof_lv)}'.",
                    )

    all_modules = list(set(list(AVAILABLE_MODULES) + list(MODULE_IDS)))
    valid_permissions = dict(user.get("permissions", {}))  # preservar existentes
    for module in all_modules:
        if module in permissions:
            level = permissions[module]
            if level in PERMISSION_LEVELS:
                valid_permissions[module] = level
            else:
                valid_permissions[module] = valid_permissions.get(module, "read")
    
    # Actualizar permisos
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"permissions": valid_permissions}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Permisos actualizados", "user": updated_user}

@router.put("/admin/users/{user_id}/special-permissions")
async def update_special_permissions(user_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar permisos especiales de un usuario (solo admin). Ceiling vs perfil."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar permisos especiales")
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    special_permissions = body.get("special_permissions", [])
    # Validar contra catálogo: solo aceptar flags conocidos
    from permissions_catalog import SPECIAL_FLAG_IDS
    valid_flags = [f for f in special_permissions if isinstance(f, str) and f in SPECIAL_FLAG_IDS]

    # Ceiling: el user solo puede tener flags que el perfil también tenga.
    if user.get("profile_id") and user.get("role") != "admin":
        profile = await db.profiles.find_one({"profile_id": user["profile_id"]}, {"_id": 0})
        if profile:
            allowed = set(profile.get("special_permissions") or [])
            forbidden = [f for f in valid_flags if f not in allowed]
            if forbidden:
                raise HTTPException(
                    status_code=403,
                    detail=f"Acceso restringido: el perfil '{profile.get('name')}' no incluye: {', '.join(forbidden)}",
                )
    
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"special_permissions": valid_flags}}
    )
    
    updated_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {"message": "Permisos especiales actualizados", "user": updated_user}

@router.post("/admin/users/equipment-quotes-access")
async def diagnose_fix_equipment_quotes_access(body: dict, authorization: Optional[str] = Header(None)):
    """Diagnostica (y opcionalmente repara) el acceso de un usuario al menú de
    Cotizaciones de Equipos. Solo Admin. Ejecutable en producción desde la app.

    Body: {"identifier": "<nombre o email>", "apply": false}
    Condiciones para ver el menú:
      1) permissions['cotizaciones'] == 'edit'
      2) grupo de menú 'gestion_comercial' activo
      3) 'cotizaciones:equipos' en special_permissions efectivos (perfil ∪ usuario)
    """
    current_user = await get_current_user(authorization)
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    FLAG = "cotizaciones:equipos"
    MODULE = "cotizaciones"
    GROUP = "gestion_comercial"

    identifier = (body.get("identifier") or "").strip()
    apply = bool(body.get("apply"))
    if not identifier:
        raise HTTPException(status_code=400, detail="Falta 'identifier' (nombre o email)")

    rx = {"$regex": re.escape(identifier), "$options": "i"}
    user = await db.users.find_one({"$or": [{"email": rx}, {"name": rx}, {"full_name": rx}]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail=f"No se encontró usuario para '{identifier}'")

    role = user.get("role")
    is_admin = role == "admin"
    perms = user.get("permissions") or {}
    cot_level = perms.get(MODULE, "none")
    menu_groups = user.get("menu_groups") or {}
    group_active = (len(menu_groups) == 0) or bool(menu_groups.get(GROUP))
    user_sp = list(user.get("special_permissions") or [])
    profile = None
    profile_sp = []
    if user.get("profile_id"):
        profile = await db.profiles.find_one({"profile_id": user["profile_id"]}, {"_id": 0})
        profile_sp = list((profile or {}).get("special_permissions") or [])
    effective_sp = sorted(set(user_sp) | set(profile_sp))
    has_equipos = is_admin or (FLAG in effective_sp)
    can_edit = is_admin or (cot_level == "edit" and group_active)
    visible = is_admin or (can_edit and has_equipos)

    diagnosis = {
        "user": {"user_id": user.get("user_id"), "name": user.get("name") or user.get("full_name"),
                 "email": user.get("email"), "role": role,
                 "profile_id": user.get("profile_id"), "profile_name": (profile or {}).get("name")},
        "checks": {
            "cotizaciones_level": cot_level, "needs_edit_ok": is_admin or cot_level == "edit",
            "group_gestion_comercial_active": group_active,
            "special_user": user_sp, "special_profile": profile_sp, "special_effective": effective_sp,
            "has_cotizaciones_equipos": has_equipos,
        },
        "would_see_menu": visible,
    }

    if visible:
        return {"status": "ok", "fixed": False,
                "message": "El usuario ya cumple las condiciones. Pídele cerrar sesión y volver a entrar.",
                "diagnosis": diagnosis}

    planned = []
    if not is_admin:
        if profile and FLAG not in profile_sp:
            planned.append("profile_add_flag")
        if FLAG not in user_sp:
            planned.append("user_add_flag")
        if cot_level != "edit":
            planned.append("set_cotizaciones_edit")
        if menu_groups and not menu_groups.get(GROUP):
            planned.append("activate_group")

    if not apply:
        return {"status": "needs_fix", "fixed": False, "planned_actions": planned,
                "message": "DRY-RUN. Reenvía con apply=true para aplicar.", "diagnosis": diagnosis}

    applied = []
    if "profile_add_flag" in planned and profile:
        await db.profiles.update_one({"profile_id": user["profile_id"]}, {"$addToSet": {"special_permissions": FLAG}})
        applied.append("profile_add_flag")
    if "user_add_flag" in planned:
        await db.users.update_one({"user_id": user["user_id"]}, {"$addToSet": {"special_permissions": FLAG}})
        applied.append("user_add_flag")
    if "set_cotizaciones_edit" in planned:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {f"permissions.{MODULE}": "edit"}})
        applied.append("set_cotizaciones_edit")
    if "activate_group" in planned:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {f"menu_groups.{GROUP}": True}})
        applied.append("activate_group")

    return {"status": "fixed", "fixed": True, "applied_actions": applied,
            "message": "Reparación aplicada. El usuario debe cerrar sesión y volver a entrar.",
            "diagnosis": diagnosis}



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


@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, reassign_to: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Eliminar permanentemente un usuario (solo admin — super poder).

    BLINDAJE (evita cotizaciones/proyectos huérfanos): si el usuario tiene
    cotizaciones o proyectos asociados, el borrado se BLOQUEA (409) salvo que se
    indique `reassign_to=<user_id>` para reasignar primero esas referencias a otro
    ejecutivo. Alternativa recomendada: desactivar el usuario (is_active=false) en
    lugar de borrarlo.
    """
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar usuarios")

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "name": 1, "user_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_id == current_user.get("user_id"):
        raise HTTPException(status_code=400, detail="No puede eliminarse a sí mismo")

    # Conteo de referencias para blindaje.
    q_count = await db.quotes.count_documents({"created_by_user_id": user_id})
    qh_count = await db.quote_history.count_documents({"created_by_user_id": user_id})
    p_count = await db.projects.count_documents(
        {"$or": [{"created_by_user_id": user_id}, {"assigned_to_user_id": user_id}]}
    )
    total_refs = q_count + qh_count + p_count

    if total_refs and not reassign_to:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El usuario tiene referencias asociadas: {q_count} cotización(es), "
                f"{qh_count} histórica(s) y {p_count} proyecto(s). Para evitar registros "
                f"huérfanos, reasigne primero esas referencias a otro ejecutivo "
                f"(elimine con ?reassign_to=<user_id>) o desactive el usuario en lugar de borrarlo."
            ),
        )

    if reassign_to:
        target = await db.users.find_one({"user_id": reassign_to}, {"_id": 0, "user_id": 1, "email": 1, "name": 1})
        if not target:
            raise HTTPException(status_code=404, detail=f"Usuario destino de reasignación no encontrado: {reassign_to}")
        await _reassign_executive_references(user_id, reassign_to)

    # Eliminar sesiones, tokens y el usuario
    await db.user_sessions.delete_many({"user_id": user_id})
    await db.password_reset_tokens.delete_many({"user_id": user_id})
    await db.email_verification_tokens.delete_many({"user_id": user_id})
    await db.users.delete_one({"user_id": user_id})

    logging.info(f"[ADMIN] Usuario eliminado permanentemente: {user.get('email')} ({user_id}) por {current_user.get('email')}")
    return {"message": f"Usuario {user.get('name', user.get('email'))} eliminado permanentemente"}


async def _reassign_executive_references(from_user_id: str, to_user_id: str) -> dict:
    """Reasigna todas las referencias de `from_user_id` → `to_user_id`:
    cotizaciones, históricas, proyectos (creador y asignado) y las listas
    `allowed_user_ids` de overrides/acciones custom (re-denormalizando emails).

    Sirve tanto para reasignar antes de borrar como para SANAR registros que ya
    quedaron huérfanos (cuando el usuario viejo ya fue borrado)."""
    out = {"quotes": 0, "quote_history": 0, "projects_created": 0, "projects_assigned": 0,
           "overrides": 0, "custom_actions": 0}

    r = await db.quotes.update_many({"created_by_user_id": from_user_id},
                                    {"$set": {"created_by_user_id": to_user_id}})
    out["quotes"] = r.modified_count
    r = await db.quote_history.update_many({"created_by_user_id": from_user_id},
                                           {"$set": {"created_by_user_id": to_user_id}})
    out["quote_history"] = r.modified_count
    r = await db.projects.update_many({"created_by_user_id": from_user_id},
                                      {"$set": {"created_by_user_id": to_user_id}})
    out["projects_created"] = r.modified_count
    r = await db.projects.update_many({"assigned_to_user_id": from_user_id},
                                      {"$set": {"assigned_to_user_id": to_user_id}})
    out["projects_assigned"] = r.modified_count

    # Remapear allowed_user_ids en overrides y acciones custom + re-denormalizar emails.
    from routes.quote_action_customization import _resolve_emails_for_ids
    for coll_name, key in (("quote_action_overrides", "overrides"), ("quote_custom_actions", "custom_actions")):
        coll = db[coll_name]
        async for it in coll.find({"allowed_user_ids": from_user_id}, {"_id": 0}):
            ids = [to_user_id if x == from_user_id else x for x in (it.get("allowed_user_ids") or [])]
            ids = sorted(set(ids))
            emails = await _resolve_emails_for_ids(ids)
            await coll.update_one(
                {"config_key": it.get("config_key")},
                {"$set": {"allowed_user_ids": ids, "allowed_user_emails": emails}},
            )
            out[key] += 1
    return out


@router.get("/admin/executives/orphaned")
async def list_orphaned_executive_references(authorization: Optional[str] = Header(None)):
    """Lista los `user_id` referenciados en cotizaciones/proyectos/overrides que YA
    NO existen en la tabla de usuarios (registros huérfanos), con conteos y el
    nombre congelado si está disponible. Solo admin."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")

    existing = {u["user_id"] async for u in db.users.find({}, {"_id": 0, "user_id": 1})}

    counts: dict = {}
    def _bump(uid, field):
        if not uid or uid in existing:
            return
        counts.setdefault(uid, {"user_id": uid, "quotes": 0, "quote_history": 0,
                                "projects": 0, "overrides": 0, "sample_name": None})
        counts[uid][field] += 1

    async for q in db.quotes.find({}, {"_id": 0, "created_by_user_id": 1, "created_by_name": 1}):
        uid = q.get("created_by_user_id")
        _bump(uid, "quotes")
        if uid in counts and not counts[uid]["sample_name"] and q.get("created_by_name"):
            counts[uid]["sample_name"] = q.get("created_by_name")
    async for h in db.quote_history.find({}, {"_id": 0, "created_by_user_id": 1}):
        _bump(h.get("created_by_user_id"), "quote_history")
    async for p in db.projects.find({}, {"_id": 0, "created_by_user_id": 1, "assigned_to_user_id": 1}):
        _bump(p.get("created_by_user_id"), "projects")
        _bump(p.get("assigned_to_user_id"), "projects")
    for coll_name in ("quote_action_overrides", "quote_custom_actions"):
        async for it in db[coll_name].find({}, {"_id": 0, "allowed_user_ids": 1}):
            for uid in (it.get("allowed_user_ids") or []):
                _bump(uid, "overrides")

    return {"orphaned": sorted(counts.values(), key=lambda x: -(x["quotes"] + x["projects"]))}


@router.post("/admin/executives/reassign")
async def reassign_executive_references(from_user_id: str, to_user_id: str, authorization: Optional[str] = Header(None)):
    """Reasigna TODAS las referencias de un ejecutivo (incluso si ya fue borrado)
    a otro usuario existente. Útil para sanar cotizaciones/proyectos huérfanos y
    remapear los overrides de acciones. Solo admin."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    if from_user_id == to_user_id:
        raise HTTPException(status_code=400, detail="from_user_id y to_user_id no pueden ser iguales")
    target = await db.users.find_one({"user_id": to_user_id}, {"_id": 0, "user_id": 1, "email": 1, "name": 1})
    if not target:
        raise HTTPException(status_code=404, detail=f"Usuario destino no encontrado: {to_user_id}")
    result = await _reassign_executive_references(from_user_id, to_user_id)
    logging.info(f"[ADMIN] Reasignación {from_user_id} → {to_user_id} por {current_user.get('email')}: {result}")
    return {
        "ok": True,
        "from_user_id": from_user_id,
        "to_user_id": to_user_id,
        "to_user_email": target.get("email"),
        "reassigned": result,
    }


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
    frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    try:
        from services.email_service import send_email
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
          <div style="background:#003366;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;font-size:22px;">Gestor MegaNexus</h1>
          </div>
          <div style="background:#f8fafc;padding:30px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
            <h2 style="color:#1e293b;margin-top:0;">Restablecimiento de Contraseña</h2>
            <p style="color:#475569;">Hola <strong>{user.get('first_name', user.get('name', ''))}</strong>,</p>
            <p style="color:#475569;">Un administrador ha solicitado restablecer tu contraseña:</p>
            <div style="text-align:center;margin:25px 0;">
              <a href="{reset_link}" style="background:#003366;color:white;padding:12px 30px;text-decoration:none;border-radius:6px;font-weight:bold;display:inline-block;">
                Restablecer Contraseña
              </a>
            </div>
            <p style="color:#94a3b8;font-size:13px;">Este enlace expira en 24 horas.</p>
          </div>
        </div>
        """
        await send_email(
            to=[user.get("email")],
            subject="Restablecimiento de Contraseña - Gestor MegaNexus",
            html=html,
            action="admin_password_reset"
        )
    except Exception as e:
        logging.error(f"[AUTH] Error enviando email de reset admin: {e}")

    return {
        "message": "Token de restablecimiento generado y enviado por correo",
        "email": user.get("email"),
        "reset_link": reset_link,
        "expires_at": expires_at.isoformat()
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

