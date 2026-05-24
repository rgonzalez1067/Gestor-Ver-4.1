"""Servicio de notificaciones de asignación (Feb 2026).

Provee:
- notify_initial_contact_assigned: alerta a un ejecutivo cuando se le asigna un
  Contacto Inicial (con sus datos clave: nombre, teléfono, email, origen,
  interés, SLA).
- notify_project_assigned: alerta a un implementador cuando se le asigna un
  Proyecto (con datos del encabezado: ID, cliente, sede, fecha, ejecutivo).

Diseño:
- Templates HTML con identidad MegaNexus (azul corporativo #00447C).
- Envío asíncrono via `asyncio.create_task(...)` — el handler que asigna NO
  espera a que el correo se envíe. La interfaz responde de inmediato.
- Bitácora: cada envío (éxito o fallo) se registra en `db.bitacora` para
  auditoría con `action="assignment_email_sent" | "assignment_email_failed"`.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from config import db
from services.email_service import send_email

logger = logging.getLogger(__name__)

# Identidad MegaNexus
BRAND_COLOR = "#00447C"
BRAND_COLOR_LIGHT = "#E8F0F8"
BRAND_NAME = "MegaNexus"
SYSTEM_URL_FALLBACK = "https://admin-control-center-21.emergent.host"


def _esc(s) -> str:
    """HTML-escape simple para evitar inyección de markup en variables dinámicas."""
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _wrap_html(title: str, intro: str, rows: list, footer_cta: str = "") -> str:
    """Envuelve filas {label, value} en el layout corporativo MegaNexus."""
    rows_html = ""
    for r in rows:
        rows_html += (
            f'<tr>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;'
            f'color:#64748B;font-size:12px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.04em;width:38%;background:#F8FAFC;">'
            f'{_esc(r["label"])}</td>'
            f'<td style="padding:10px 14px;border-bottom:1px solid #E2E8F0;'
            f'color:#0F172A;font-size:14px;">{_esc(r["value"]) or "&mdash;"}</td>'
            f'</tr>'
        )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"/>
<title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#F1F5F9;padding:30px 16px;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;background:#FFFFFF;border-radius:10px;overflow:hidden;box-shadow:0 4px 24px rgba(15,23,42,0.08);">
      <!-- Header banner -->
      <tr><td style="background:{BRAND_COLOR};padding:18px 24px;color:#FFFFFF;">
        <p style="margin:0;font-size:11px;letter-spacing:0.14em;font-weight:700;opacity:0.85;text-transform:uppercase;">{BRAND_NAME} CRM</p>
        <h1 style="margin:4px 0 0 0;font-size:20px;font-weight:600;line-height:1.3;">{_esc(title)}</h1>
      </td></tr>
      <!-- Intro -->
      <tr><td style="padding:22px 24px 8px 24px;color:#334155;font-size:14px;line-height:1.55;">
        {intro}
      </td></tr>
      <!-- Data table -->
      <tr><td style="padding:8px 24px 24px 24px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;">
          {rows_html}
        </table>
      </td></tr>
      {('<tr><td style="padding:0 24px 22px 24px;">' + footer_cta + '</td></tr>') if footer_cta else ''}
      <!-- Footer -->
      <tr><td style="background:#F8FAFC;padding:14px 24px;color:#94A3B8;font-size:11px;border-top:1px solid #E2E8F0;">
        Notificación automática de {BRAND_NAME}. No respondas a este correo &mdash; ingresa al sistema para gestionar.
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


async def _send_in_background(*, to: list, subject: str, html: str, action: str, reference_id: str):
    """Tarea asíncrona que envía el correo y registra el resultado en bitácora.

    Esta función se llama vía `asyncio.create_task` para que NUNCA bloquee el
    request HTTP del handler que disparó la asignación.
    """
    ok = False
    error_msg = None
    try:
        result = await send_email(to=to, subject=subject, html=html, action=action)
        # send_email returns a dict with status='sent'|'simulated'|'failed'.
        if isinstance(result, dict):
            ok = result.get("status") in ("sent", "simulated")
            if not ok:
                error_msg = result.get("error") or result.get("message")
        else:
            ok = bool(result)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.warning(f"[assignment_email] {action} → {to} fallido: {e}")

    try:
        await db.bitacora.insert_one({
            "action": "assignment_email_sent" if ok else "assignment_email_failed",
            "sub_action": action,
            "to": to,
            "subject": subject,
            "reference_id": reference_id,
            "error": error_msg,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        # No queremos que la bitácora rompa el flujo
        pass


# ============================================================
# 1) Asignación de Contacto Inicial → Ejecutivo
# ============================================================
async def notify_initial_contact_assigned(
    contact: dict,
    target_user: dict,
    assigner_name: str = "",
) -> None:
    """Dispara (asíncrono) la alerta al ejecutivo recién asignado.

    El handler NO espera al envío: usamos asyncio.create_task para liberar el
    request inmediatamente. La interfaz de asignación sigue siendo instantánea.

    Args:
        contact: documento del contacto inicial (dict completo).
        target_user: documento del usuario ejecutivo asignado (debe tener email).
        assigner_name: nombre del usuario que ejecutó la asignación (informativo).
    """
    to_email = (target_user or {}).get("email", "").strip()
    if not to_email:
        return  # Sin email destino, no enviamos (pero el resto del flujo continúa)

    # ── Variables dinámicas del contacto ──
    # Nombre del Contacto: campo `contact_name` (persona) — con fallback a legal_name
    contact_name = (contact.get("contact_name") or contact.get("legal_name") or "").strip()
    phone = (contact.get("phone") or "").strip()
    email_contact = (contact.get("email") or "").strip()
    # Origen del Contacto: campo `referred_by` (Web/Alianza/Referido/etc.)
    origen = (contact.get("referred_by") or "Sin especificar").strip()
    # Interés del Cliente: campo `interest_notes` (servicio/producto)
    interes = (contact.get("interest_notes") or "Sin especificar").strip()
    # Fecha Máxima de Atención: campo `due_date` (calculado por SLA)
    fecha_max = (contact.get("due_date") or "Sin definir").strip() if isinstance(contact.get("due_date"), str) else "Sin definir"

    target_display = (f"{target_user.get('first_name','')} {target_user.get('last_name','')}").strip() or to_email

    subject = "Asignación de una nueva tarea de Contacto Inicial"
    intro = (
        f"Hola <b>{_esc(target_display)}</b>,<br><br>"
        f"Has sido designado como responsable de un nuevo <b>Contacto Inicial</b>. "
        f"A continuación encontrarás los datos clave para iniciar la gestión."
    )
    rows = [
        {"label": "Nombre del Contacto", "value": contact_name},
        {"label": "Teléfono", "value": phone},
        {"label": "Email", "value": email_contact},
        {"label": "Origen del Contacto", "value": origen},
        {"label": "Interés del Cliente", "value": interes},
        {"label": "Fecha Máxima de Atención", "value": fecha_max},
    ]
    footer_cta = (
        f'<div style="background:{BRAND_COLOR_LIGHT};border-left:3px solid {BRAND_COLOR};'
        f'padding:10px 14px;border-radius:4px;color:#1E293B;font-size:12px;">'
        f'<b>Acción recomendada:</b> ingresa al CRM al módulo <i>Contactos Iniciales</i> '
        f'para registrar la primera gestión antes de la fecha máxima.'
        f'</div>'
    )
    if assigner_name:
        footer_cta = (
            f'<p style="color:#64748B;font-size:11px;margin:0 0 10px 0;">'
            f'Asignado por: <b>{_esc(assigner_name)}</b></p>'
        ) + footer_cta

    html = _wrap_html(subject, intro, rows, footer_cta)

    asyncio.create_task(_send_in_background(
        to=[to_email],
        subject=subject,
        html=html,
        action="initial_contact_assigned",
        reference_id=contact.get("contact_id", ""),
    ))


# ============================================================
# 2) Asignación de Proyecto → Implementador
# ============================================================
async def notify_project_assigned(
    project: dict,
    target_user: dict,
    assigner_name: str = "",
    executive_name: Optional[str] = None,
) -> None:
    """Dispara (asíncrono) la alerta al implementador recién asignado.

    Args:
        project: documento del proyecto.
        target_user: documento del implementador (debe tener email).
        assigner_name: quien ejecutó la asignación (informativo).
        executive_name: nombre del ejecutivo comercial de origen (resuelve si None).
    """
    to_email = (target_user or {}).get("email", "").strip()
    if not to_email:
        return

    # Razón Social del cliente (no fantasy_name)
    client_id = project.get("client_id")
    legal_name = project.get("client_name") or ""
    if client_id:
        c = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "legal_name": 1, "fantasy_name": 1})
        if c:
            legal_name = (c.get("legal_name") or c.get("fantasy_name") or legal_name).strip()

    # Datos del encabezado
    project_number = project.get("project_number") or project.get("project_id") or ""
    sede = project.get("client_sede") or project.get("sede") or ""
    quote_type = project.get("quote_type") or ""
    sede_categoria = " · ".join([s for s in [sede, quote_type] if s]) or "Sin especificar"
    fecha_creacion = (project.get("created_at") or project.get("assigned_at") or "")[:19].replace("T", " ")
    fecha_asignacion = (project.get("assigned_at") or project.get("fecha_asignacion") or "")[:19].replace("T", " ")

    # Ejecutivo comercial de origen: resolver desde la cotización
    if executive_name is None:
        executive_name = ""
        quote_id = project.get("quote_id")
        if quote_id:
            q = await db.quotes.find_one(
                {"quote_id": quote_id},
                {"_id": 0, "created_by_name": 1, "executive_name": 1, "created_by_user_id": 1},
            )
            if q:
                executive_name = q.get("executive_name") or q.get("created_by_name") or ""
                if not executive_name and q.get("created_by_user_id"):
                    u = await db.users.find_one(
                        {"user_id": q["created_by_user_id"]},
                        {"_id": 0, "first_name": 1, "last_name": 1},
                    )
                    if u:
                        executive_name = f"{u.get('first_name','')} {u.get('last_name','')}".strip()

    target_display = (f"{target_user.get('first_name','')} {target_user.get('last_name','')}").strip() or to_email

    subject = f"Asignación de nuevo Proyecto de Implementación Cliente : {legal_name}"
    intro = (
        f"Hola <b>{_esc(target_display)}</b>,<br><br>"
        f"Se te ha asignado un nuevo <b>Proyecto de Implementación</b>. "
        f"A continuación encontrarás los datos del encabezado del proyecto."
    )
    rows = [
        {"label": "ID / Número de Proyecto", "value": project_number},
        {"label": "Razón Social del Cliente", "value": legal_name},
        {"label": "Sede / Categoría", "value": sede_categoria},
        {"label": "Fecha de Creación", "value": fecha_creacion or "Sin registrar"},
        {"label": "Fecha de Asignación", "value": fecha_asignacion or "Sin registrar"},
        {"label": "Ejecutivo Comercial de Origen", "value": executive_name or "Sin especificar"},
    ]
    footer_cta = (
        f'<div style="background:{BRAND_COLOR_LIGHT};border-left:3px solid {BRAND_COLOR};'
        f'padding:10px 14px;border-radius:4px;color:#1E293B;font-size:12px;">'
        f'<b>Próximo paso:</b> ingresa al CRM al módulo <i>Implementaciones</i> para '
        f'consultar la Ficha Técnica completa, anexos y comenzar la ejecución.'
        f'</div>'
    )
    if assigner_name:
        footer_cta = (
            f'<p style="color:#64748B;font-size:11px;margin:0 0 10px 0;">'
            f'Asignado por: <b>{_esc(assigner_name)}</b></p>'
        ) + footer_cta

    html = _wrap_html(subject, intro, rows, footer_cta)

    asyncio.create_task(_send_in_background(
        to=[to_email],
        subject=subject,
        html=html,
        action="project_assigned",
        reference_id=project.get("project_id", ""),
    ))
