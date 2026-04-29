"""Rutas para comunicaciones de clientes: documentos internos y envío de emails."""
from fastapi import APIRouter, HTTPException, Header, Form, File, UploadFile
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import json
import os
import logging

from config import db, get_current_user
from services.pdf_storage import save_pdf_dual
from services.email_service import send_email

router = APIRouter()


# ==================== DOCUMENTOS DE COMUNICACIÓN ====================

class ClientDocumentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = "General"


@router.get("/client-documents")
async def list_client_documents(authorization: Optional[str] = Header(None)):
    """Lista documentos internos de comunicación para clientes."""
    await get_current_user(authorization)
    docs = await db.client_documents.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@router.post("/client-documents/upload")
async def upload_client_document(
    name: str = Form(...),
    description: str = Form(default=""),
    category: str = Form(default="General"),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Sube un documento de comunicación para clientes."""
    current_user = await get_current_user(authorization)

    upload_dir = "/app/backend/uploads/client_documents"
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_name)
    content = await file.read()
    save_pdf_dual(file_path, content, f"client_documents/{safe_name}")

    doc = {
        "document_id": f"cdoc_{uuid.uuid4().hex[:12]}",
        "name": name.strip(),
        "description": description.strip(),
        "category": category.strip(),
        "filename": file.filename,
        "url": f"/uploads/client_documents/{safe_name}",
        "file_size": len(content),
        "content_type": file.content_type,
        "uploaded_by": current_user.get("email", ""),
        "uploaded_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.client_documents.insert_one(doc)
    del doc["_id"]
    return doc


@router.delete("/client-documents/{document_id}")
async def delete_client_document(document_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un documento de comunicación."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar documentos")

    doc = await db.client_documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Delete file from disk
    file_path = f"/app/backend{doc.get('url', '')}"
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.client_documents.delete_one({"document_id": document_id})
    return {"message": "Documento eliminado"}


# ==================== PLANTILLAS DE CLIENTES ====================
# Usa el mismo CRUD de email-templates existente, con context = "CLIENTES"
# No se necesitan endpoints nuevos — se filtran por context=CLIENTES


# ==================== ENVÍO DE EMAIL A CLIENTES ====================

def _render_client_vars(text: str, client: dict) -> str:
    """Reemplaza variables dinámicas del cliente en el texto."""
    contacts = client.get("contacts", [])
    contact_name = ""
    if contacts:
        c = contacts[0]
        contact_name = c.get("full_name") or c.get("name") or c.get("first_name", "")
    contact_email = contacts[0].get("email", "") if contacts else client.get("email", "")
    contact_phone = contacts[0].get("phone", "") if contacts else ""

    replacements = {
        "nombre": client.get("legal_name") or client.get("fantasy_name", ""),
        "razon_social": client.get("legal_name", ""),
        "rif": client.get("rif", ""),
        "email": contact_email,
        "contacto": contact_name,
        "direccion": client.get("address", ""),
        "telefono": contacts[0].get("phone", "") if contacts else "",
        "nombre_comercial": client.get("fantasy_name", ""),
    }

    result = text
    for key, val in replacements.items():
        result = result.replace(f"{{{{{key}}}}}", str(val))
        result = result.replace(f"{{{key}}}", str(val))
    return result


@router.post("/clients/{client_id}/send-email")
async def send_client_email(
    client_id: str,
    recipients: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    internal_doc_ids: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None)
):
    """Envía email a un cliente con adjuntos. Auto-registra en bitácora."""
    current_user = await get_current_user(authorization)

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Parse recipients
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
    client_name = client.get("legal_name") or client.get("fantasy_name", "")

    # Resolver variables en subject y message
    subject = _render_client_vars(subject, client)
    message_html = _render_client_vars(message.replace("\n", "<br>"), client)

    html = f"""
    <div style="font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;">
        <p>{message_html}</p>
        <hr>
        <p style="color: #666; font-size: 11px;">Comunicación enviada desde Gestor MegaNexus | Cliente: {client_name}</p>
    </div>
    """

    # Guardar adjuntos externos
    upload_dir = f"/app/backend/uploads/client_emails/{client_id}"
    os.makedirs(upload_dir, exist_ok=True)
    saved_files = []
    for f in files:
        if f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            save_pdf_dual(file_path, content, f"client_emails/{client_id}/{safe_name}")
            saved_files.append({
                "filename": f.filename,
                "url": f"/uploads/client_emails/{client_id}/{safe_name}",
                "size": len(content),
                "content_type": f.content_type,
            })

    # Cargar documentos internos seleccionados como adjuntos
    try:
        doc_ids = json.loads(internal_doc_ids)
    except:
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
                    "content_type": doc.get("content_type", "application/octet-stream"),
                })

    # Preparar adjuntos para el motor de email (formato: {filename, content} en bytes)
    email_attachments = []
    for f_info in saved_files:
        fpath = f"/app/backend{f_info['url']}"
        if os.path.exists(fpath):
            with open(fpath, "rb") as fh:
                email_attachments.append({
                    "filename": f_info["filename"],
                    "content": fh.read(),
                })
    for att in internal_attachments:
        if os.path.exists(att["path"]):
            with open(att["path"], "rb") as fh:
                email_attachments.append({
                    "filename": att["filename"],
                    "content": fh.read(),
                })

    # Enviar email CON adjuntos
    email_result = await send_email(
        to=to_list,
        subject=subject,
        html=html,
        action="client_communication",
        attachments=email_attachments if email_attachments else None,
    )

    # Registrar en bitácora del cliente
    attachments_text = ""
    total_attachments = len(saved_files) + len(internal_attachments)
    if total_attachments:
        attachments_text = f" ({total_attachments} adjunto(s))"

    log_entry = {
        "log_id": f"log_{uuid.uuid4().hex[:12]}",
        "client_id": client_id,
        "action": "Comunicación enviada",
        "detail": f"[Email] {subject}{attachments_text} → {', '.join(to_list)}",
        "contact_date": now[:10],
        "is_completed": True,
        "created_by": current_user.get("email", ""),
        "created_by_name": user_name,
        "created_at": now,
        "email_data": {
            "subject": subject,
            "recipients": to_list,
            "message_preview": message[:200],
            "attachments": [f["filename"] for f in saved_files] + [a["filename"] for a in internal_attachments],
            "sent_at": now,
            "sent_by": user_name,
        }
    }
    await db.client_logs.insert_one(log_entry)

    logging.info(f"Email cliente {client_id} enviado a {to_list} por {user_name}")

    return {
        "status": "sent",
        "message": f"Comunicación enviada a {', '.join(to_list)} y registrada en bitácora",
        "email_result": email_result,
        "attachments_count": total_attachments,
    }


@router.post("/clients/{client_id}/preview-email")
async def preview_client_email(client_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Vista previa de un email con variables resueltas."""
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    subject = _render_client_vars(body.get("subject", ""), client)
    message = _render_client_vars(body.get("message", ""), client)

    return {"subject": subject, "message": message}
