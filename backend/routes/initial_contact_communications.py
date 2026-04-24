"""Rutas para envío de comunicaciones a Contactos Iniciales (leads).
Reutiliza la infraestructura de email templates con context='INITIAL_CONTACTS'
y registra cada envío en la bitácora del contacto inicial."""
from fastapi import APIRouter, HTTPException, Header, Form, File, UploadFile
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json
import os
import logging

from config import db, get_current_user
from services.email_service import send_email

router = APIRouter()


def _render_contact_vars(text: str, contact: dict) -> str:
    """Reemplaza variables dinámicas del contacto inicial en el texto."""
    replacements = {
        "nombre": contact.get("contact_name", ""),
        "contacto": contact.get("contact_name", ""),
        "razon_social": contact.get("legal_name", ""),
        "empresa": contact.get("legal_name", ""),
        "email": contact.get("email", ""),
        "telefono": contact.get("phone", ""),
        "referido_por": contact.get("referred_by", ""),
        "asignado_a": contact.get("assigned_to_name", ""),
        "aspectos_interes": contact.get("interest_notes", ""),
    }
    result = text or ""
    for key, val in replacements.items():
        result = result.replace(f"{{{{{key}}}}}", str(val))
        result = result.replace(f"{{{key}}}", str(val))
    return result


@router.post("/initial-contacts/{contact_id}/send-email")
async def send_initial_contact_email(
    contact_id: str,
    recipients: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    internal_doc_ids: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None),
):
    """Envía email a un contacto inicial con adjuntos y registra en bitácora."""
    current_user = await get_current_user(authorization)

    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto inicial no encontrado")

    try:
        to_list = json.loads(recipients)
        if not isinstance(to_list, list) or not to_list:
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Destinatarios inválidos")

    if not subject.strip():
        raise HTTPException(status_code=400, detail="El asunto es obligatorio")

    now = datetime.now(timezone.utc).isoformat()
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    contact_label = contact.get("legal_name") or contact.get("contact_name") or ""

    subject = _render_contact_vars(subject, contact)
    message_html = _render_contact_vars(message.replace("\n", "<br>"), contact)

    html = f"""
    <div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        <p>{message_html}</p>
        <hr>
        <p style="color: #666; font-size: 11px;">Comunicación enviada desde Gestor MegaNexus | Contacto: {contact_label}</p>
    </div>
    """

    # Adjuntos externos (reutiliza carpeta de client_emails por simplicidad operativa)
    upload_dir = f"/app/backend/uploads/initial_contact_emails/{contact_id}"
    os.makedirs(upload_dir, exist_ok=True)
    saved_files = []
    for f in files:
        if f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            with open(file_path, "wb") as fp:
                fp.write(content)
            saved_files.append({
                "filename": f.filename,
                "url": f"/uploads/initial_contact_emails/{contact_id}/{safe_name}",
                "size": len(content),
                "content_type": f.content_type,
            })

    # Documentos internos de comunicaciones de clientes (biblioteca compartida)
    try:
        doc_ids = json.loads(internal_doc_ids)
    except Exception:
        doc_ids = []
    internal_attachments = []
    for doc_id in doc_ids:
        doc = await db.client_documents.find_one({"document_id": doc_id}, {"_id": 0})
        if doc:
            file_path = f"/app/backend{doc['url']}"
            if os.path.exists(file_path):
                internal_attachments.append({
                    "filename": doc["filename"],
                    "path": file_path,
                })

    email_attachments = []
    for f_info in saved_files:
        fpath = f"/app/backend{f_info['url']}"
        if os.path.exists(fpath):
            with open(fpath, "rb") as fh:
                email_attachments.append({"filename": f_info["filename"], "content": fh.read()})
    for att in internal_attachments:
        if os.path.exists(att["path"]):
            with open(att["path"], "rb") as fh:
                email_attachments.append({"filename": att["filename"], "content": fh.read()})

    email_result = await send_email(
        to=to_list,
        subject=subject,
        html=html,
        action="initial_contact_communication",
        attachments=email_attachments if email_attachments else None,
    )

    # Registrar en bitácora del contacto
    total_attachments = len(saved_files) + len(internal_attachments)
    attachments_text = f" ({total_attachments} adjunto(s))" if total_attachments else ""

    entry = {
        "entry_id": f"bic_{uuid.uuid4().hex[:12]}",
        "action": "notification",
        "detail": f"[Email] {subject}{attachments_text} → {', '.join(to_list)}",
        "comment": message[:300],
        "user_name": user_name,
        "user_email": current_user.get("email", ""),
        "created_at": now,
        "email_data": {
            "subject": subject,
            "recipients": to_list,
            "message_preview": message[:200],
            "attachments": [f["filename"] for f in saved_files] + [a["filename"] for a in internal_attachments],
            "sent_at": now,
            "sent_by": user_name,
        },
    }
    await db.initial_contacts.update_one(
        {"contact_id": contact_id},
        {"$push": {"bitacora": entry}, "$set": {"updated_at": now}},
    )

    logging.info(f"Email contacto inicial {contact_id} enviado a {to_list} por {user_name}")

    return {
        "status": "sent",
        "message": f"Comunicación enviada a {', '.join(to_list)} y registrada en bitácora",
        "email_result": email_result,
        "attachments_count": total_attachments,
    }


@router.post("/initial-contacts/{contact_id}/preview-email")
async def preview_initial_contact_email(contact_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Vista previa con variables resueltas."""
    await get_current_user(authorization)
    contact = await db.initial_contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto inicial no encontrado")
    return {
        "subject": _render_contact_vars(body.get("subject", ""), contact),
        "message": _render_contact_vars(body.get("message", ""), contact),
    }
