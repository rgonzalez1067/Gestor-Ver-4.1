"""
Workflow Notification Helper - Motor centralizado de notificaciones por email.
Resuelve dinámicamente: buzón + plantilla + adjuntos según acción y segmento.
"""
import logging
import base64
from config import db
from services.email_service import send_email

logger = logging.getLogger(__name__)

# Matriz de disparadores: action → { recipient_key, template_base, attach_pdf }
WORKFLOW_MATRIX = {
    "send-to-client": {
        "recipient_key": "client",          # Correos del cliente
        "template_base": "quote_sent",
        "attach_pdf": True,
    },
    "approve": {
        "recipient_key": "admin",           # Buzón Administración (sede)
        "template_base": "quote_approved",
        "attach_pdf": True,
    },
    "configure": {                          # Factura / Proforma
        "recipient_key": "admin",           # Buzón Administración (sede)
        "template_base": "invoice",
        "attach_pdf": False,
    },
    "collect": {                            # Cobranza
        "recipient_key": "sales",           # Buzón Ventas (sede)
        "template_base": "comprobante_pago",
        "attach_pdf": False,                # Comprobante va aparte si aplica
    },
    "send-to-implementation": {
        "recipient_key": "implementation",  # Buzón Implementación (General)
        "template_base": "implementation",
        "attach_pdf": True,
    },
}


def render_template(template_str: str, variables: dict) -> str:
    """Renderiza variables {key} y {{key}} en una plantilla."""
    result = template_str
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value or ""))
        result = result.replace(f"{{{key}}}", str(value or ""))
    return result


async def _load_config():
    """Carga configuración de app_settings."""
    return await db.config.find_one({"type": "app_settings"}, {"_id": 0})


async def _resolve_recipients(action: str, quote: dict, config: dict) -> list:
    """Resuelve los destinatarios principales según la matriz y config."""
    matrix = WORKFLOW_MATRIX.get(action)
    if not matrix:
        return []

    recipient_key = matrix["recipient_key"]
    # Normalizar sede: TBP → PYME (legacy)
    raw_sede = quote.get("sede", quote.get("client_segment", "PYME"))
    sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
    emails_by_sede = config.get("emails_by_sede", {}) if config else {}
    sede_emails = emails_by_sede.get(sede, {})

    recipients = []

    if recipient_key == "client":
        # Correos del cliente se manejan en el caller (vienen del modal)
        pass
    elif recipient_key == "admin":
        admin = sede_emails.get("admin") or (config.get("admin_email") if config else None)
        if admin:
            recipients.append(admin)
    elif recipient_key == "sales":
        sales = sede_emails.get("sales")
        if sales:
            recipients.append(sales)
    elif recipient_key == "implementation":
        impl = config.get("implementation_email") if config else None
        if impl:
            recipients.append(impl)

    return recipients


async def _resolve_template(action: str, segment: str) -> dict:
    """Carga la plantilla correcta según acción y segmento."""
    matrix = WORKFLOW_MATRIX.get(action, {})
    template_base = matrix.get("template_base", action)

    # Normalizar segmento
    norm_segment = "PYME" if segment in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if segment in ("CORP", "Corp", "Corporativo") else segment

    # Intentar plantilla segmentada primero (ej: quote_approved_PYME)
    template_id = f"{template_base}_{norm_segment}"
    template = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})

    if not template:
        # Fallback a plantilla genérica (ej: quote_approved)
        template = await db.email_templates.find_one({"template_id": template_base}, {"_id": 0})

    if not template:
        # Fallback mínimo
        template = {
            "subject": "Notificación: {{quote_number}}",
            "body_html": f"<p>Acción <strong>{action}</strong> ejecutada para la cotización <strong>{{{{quote_number}}}}</strong>.</p>"
        }

    return template


async def send_workflow_notification(
    action: str,
    quote: dict,
    current_user: dict = None,
    custom_message: str = None,
    cc_emails: list = None,
    pdf_buffer=None,
    extra_attachments: list = None,
    override_recipients: list = None,
    extra_template_vars: dict = None,
) -> list:
    """
    Motor centralizado de notificaciones del workflow.
    
    Args:
        action: Acción del workflow (send-to-client, approve, configure, collect, send-to-implementation)
        quote: Documento de la cotización
        current_user: Usuario que ejecuta la acción
        custom_message: Mensaje personalizado del modal "Personalizar Comunicación"
        cc_emails: Lista de emails CC del modal
        pdf_buffer: BytesIO del PDF para adjuntar (si aplica)
        extra_attachments: Adjuntos adicionales [{filename, content}]
        override_recipients: Lista de recipients que reemplaza la resolución automática
        extra_template_vars: Variables adicionales para la plantilla
    
    Returns:
        Lista de resultados de envío
    """
    config = await _load_config()
    segment = quote.get("sede", quote.get("client_segment", "PYME"))
    matrix = WORKFLOW_MATRIX.get(action, {})
    quote_id = quote.get("quote_id", "")
    quote_number = quote.get("quote_number", "")

    # 1. Resolver destinatarios
    if override_recipients:
        recipients = override_recipients
    else:
        recipients = await _resolve_recipients(action, quote, config)

    # 2. Cargar y renderizar plantilla
    template = await _resolve_template(action, segment)
    
    # Resolver datos del ejecutivo creador
    creator_name, creator_email = "", ""
    creator_user_id = quote.get("created_by_user_id")
    if creator_user_id:
        creator = await db.users.find_one({"user_id": creator_user_id}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1})
        if creator:
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            creator_email = creator.get("email", "")

    template_vars = {
        "quote_number": quote_number,
        "Cotizacion_Nro": quote_number,
        "nro_cotizacion": quote_number,
        "client_name": quote.get("client_name", ""),
        "Nombre_Cliente": quote.get("client_name", ""),
        "client_rif": quote.get("client_rif", ""),
        "Rif_Cliente": quote.get("client_rif", ""),
        "quote_type": quote.get("quote_type", "N/A"),
        "total_usd": f"{quote.get('total_usd', 0):.2f}",
        "Monto_Total": f"{quote.get('total_usd', 0):.2f}",
        "integrator_name": quote.get("integrator_name", ""),
        "pinpad_model": quote.get("pinpad_model", ""),
        "sede_name": segment,
        "company_name": quote.get("company_name", "Merchant Server"),
        "Nombre_Ejecutivo": creator_name,
        "Email_Ejecutivo": creator_email,
        "Contacto_Principal": quote.get("client_contact", ""),
        "Telefono_Contacto": quote.get("client_phone", ""),
        "Email_Contacto": quote.get("client_email", ""),
        "Datos_Contacto": quote.get("client_contact", ""),
    }
    if extra_template_vars:
        template_vars.update(extra_template_vars)

    subject = render_template(template.get("subject", ""), template_vars)
    html_content = render_template(template.get("body_html", ""), template_vars)

    # 3. Agregar mensaje personalizado si existe
    if custom_message and custom_message.strip():
        user_name = ""
        if current_user:
            user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
        html_content += (
            f'<div style="margin-top:16px;padding:12px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:4px">'
            f'<p style="font-size:13px;color:#1e40af;margin:0"><strong>Mensaje de {user_name}:</strong></p>'
            f'<p style="font-size:13px;color:#334155;margin:6px 0 0">{custom_message.strip()[:500]}</p></div>'
        )

    # 4. Preparar adjuntos
    attachments = list(extra_attachments or [])
    if matrix.get("attach_pdf") and pdf_buffer:
        pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, "getvalue") else pdf_buffer
        # Nombre descriptivo según la acción
        if action == "send-to-implementation":
            filename = f"Ficha_Implementacion_{quote_number}.pdf"
        else:
            filename = f"Cotizacion_{quote_number}.pdf"
        attachments.append({
            "filename": filename,
            "content": base64.b64encode(pdf_bytes).decode("utf-8"),
        })

    # 5. Enviar a destinatarios principales
    email_results = []
    for recipient in recipients:
        if not recipient or "@" not in recipient:
            continue
        r = await send_email(
            to=[recipient],
            subject=subject,
            html=html_content,
            action=f"workflow_{action}",
            quote_id=quote_id,
            quote_number=quote_number,
            attachments=attachments if attachments else None,
        )
        email_results.append(r)
        logger.info(f"[Workflow] {action} -> {recipient} | {r.get('status')}")

    # 6. Notificar también a Ventas en aprobación (copia informativa)
    if action == "approve":
        raw_sede = quote.get("sede", quote.get("client_segment", "PYME"))
        norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP" if raw_sede in ("CORP", "Corp", "Corporativo") else raw_sede
        sede_emails = (config.get("emails_by_sede", {}) if config else {}).get(norm_sede, {})
        sales_email = sede_emails.get("sales")
        if sales_email and sales_email not in recipients:
            r = await send_email(
                to=[sales_email],
                subject=f"[VENTAS] {subject}",
                html=html_content,
                action=f"workflow_{action}_sales",
                quote_id=quote_id,
                quote_number=quote_number,
            )
            email_results.append(r)

    # 7. Enviar a CC (Personalizar Comunicación)
    for cc in (cc_emails or []):
        if not cc or "@" not in cc:
            continue
        r = await send_email(
            to=[cc],
            subject=f"[CC] {subject}",
            html=html_content,
            action=f"workflow_{action}_cc",
            quote_id=quote_id,
            quote_number=quote_number,
            attachments=attachments if attachments else None,
        )
        email_results.append(r)

    if not email_results:
        # Sin destinatarios configurados — log simulado
        r = await send_email(
            to=["no-config@placeholder.local"],
            subject=subject,
            html=html_content,
            action=f"workflow_{action}_no_config",
            quote_id=quote_id,
            quote_number=quote_number,
        )
        email_results.append(r)
        logger.warning(f"[Workflow] {action}: Sin destinatarios configurados para sede {segment}")

    return email_results
