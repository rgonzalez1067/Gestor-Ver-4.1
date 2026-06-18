"""Resolución de destinatarios dinámicos basados en la ficha del Proyecto.

Replica la lógica del destinatario "Generador del Proyecto" (UsuarioCreador.Email)
para el nuevo token "Usuario Implementador" (Proyecto.UsuarioImplementador.Email).

Resolución en runtime:
  - Toma el `assigned_to_user_id` del proyecto que detona el evento y extrae su
    correo principal.

Política de contingencia (Fallback) cuando el proyecto NO tiene implementador
asignado (estado "Por asignar"):
  1) Coordinador de Implementación (cargo 'Coordinador' + depto 'Implementación').
  2) Administrador del sistema (role='admin').
  3) Si nada existe → vacío (el caller registra la advertencia).
El `fallback_note` (no None) indica que se usó contingencia y debe registrarse
una advertencia en la bitácora de errores / logs.
"""
from __future__ import annotations

from typing import Optional

from config import db
from services.notification_engine import _resolve_user_email


def _user_label(u: dict) -> str:
    return f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email", "")


async def resolve_project_implementer(
    project: Optional[dict],
) -> tuple[str, str, Optional[str], Optional[str]]:
    """Resuelve el destinatario 'Usuario Implementador'.

    Retorna (email, name, user_id, fallback_note). `fallback_note` es None cuando
    se resolvió el implementador real; en caso contrario describe la contingencia.
    """
    # 1) Implementador asignado al proyecto (caso normal).
    if project:
        impl_uid = project.get("assigned_to_user_id")
        if impl_uid:
            resolved = await _resolve_user_email(impl_uid)
            if resolved:
                return resolved[0], resolved[1], impl_uid, None

    # 2) Fallback: Coordinador de Implementación.
    coord = await db.users.find_one(
        {
            "is_active": True,
            "cargo": {"$regex": "coordinador", "$options": "i"},
            "departamento": {"$regex": "implement", "$options": "i"},
            "email": {"$regex": ".+@.+"},
        },
        {"_id": 0},
    )
    if coord and coord.get("email"):
        return (
            coord["email"],
            _user_label(coord),
            coord.get("user_id"),
            "Proyecto sin Implementador asignado → notificación desviada al Coordinador de Implementación",
        )

    # 3) Fallback final: Administrador del sistema.
    admin = await db.users.find_one(
        {"is_active": True, "role": "admin", "email": {"$regex": ".+@.+"}},
        {"_id": 0},
    )
    if admin and admin.get("email"):
        return (
            admin["email"],
            _user_label(admin),
            admin.get("user_id"),
            "Proyecto sin Implementador ni Coordinador → notificación desviada al Administrador",
        )

    return "", "", None, "Sin Implementador, Coordinador ni Administrador disponibles para resolver el destinatario"
