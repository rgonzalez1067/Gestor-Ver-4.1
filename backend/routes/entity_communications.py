"""Rutas genéricas de comunicaciones para Integradores y Nuevos Productos.
Reutiliza la misma arquitectura de Clientes, parametrizada por `context`.
"""
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

VALID_CONTEXTS = {"CLIENTES", "INTEGRADORES", "NUEVOS_PRODUCTOS"}


# ==================== USUARIOS INTERNOS (Autocomplete) ====================

@router.get("/users/internal-emails")
async def list_internal_emails(authorization: Optional[str] = Header(None)):
    """Devuelve lista de usuarios activos para autocompletar destinatarios."""
    await get_current_user(authorization)
    users = await db.users.find(
        {"is_active": {"$ne": False}},
        {"_id": 0, "user_id": 1, "email": 1, "first_name": 1, "last_name": 1, "role": 1, "cargo": 1}
    ).to_list(500)
    result = []
    for u in users:
        email = (u.get("email") or "").strip()
        if not email or "@" not in email:
            continue
        full_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or email
        result.append({
            "user_id": u.get("user_id", ""),
            "email": email,
            "full_name": full_name,
            "role": u.get("role", ""),
            "cargo": u.get("cargo", ""),
            "label": f"{full_name} ({email})",
        })
    result.sort(key=lambda x: x["full_name"].lower())
    return result


# ==================== DOCUMENTOS DE COMUNICACIÓN ====================

@router.get("/entity-documents")
async def list_entity_documents(context: str, authorization: Optional[str] = Header(None)):
    """Lista documentos internos por contexto (INTEGRADORES, NUEVOS_PRODUCTOS)."""
    await get_current_user(authorization)
    if context not in VALID_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Contexto inválido. Válidos: {VALID_CONTEXTS}")
    docs = await db.entity_documents.find({"context": context}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@router.post("/entity-documents/upload")
async def upload_entity_document(
    context: str = Form(...),
    name: str = Form(...),
    description: str = Form(default=""),
    category: str = Form(default="General"),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None)
):
    """Sube un documento reutilizable para comunicaciones del contexto indicado."""
    current_user = await get_current_user(authorization)
    if context not in VALID_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Contexto inválido. Válidos: {VALID_CONTEXTS}")

    upload_dir = f"/app/backend/uploads/entity_documents/{context.lower()}"
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_name)
    content = await file.read()
    save_pdf_dual(file_path, content, f"entity_documents/{context.lower()}/{safe_name}")

    doc = {
        "document_id": f"edoc_{uuid.uuid4().hex[:12]}",
        "context": context,
        "name": name.strip(),
        "description": description.strip(),
        "category": category.strip(),
        "filename": file.filename,
        "url": f"/uploads/entity_documents/{context.lower()}/{safe_name}",
        "file_size": len(content),
        "content_type": file.content_type,
        "uploaded_by": current_user.get("email", ""),
        "uploaded_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.entity_documents.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/entity-documents/{document_id}")
async def delete_entity_document(document_id: str, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar documentos")

    doc = await db.entity_documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    file_path = f"/app/backend{doc.get('url', '')}"
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    await db.entity_documents.delete_one({"document_id": document_id})
    return {"message": "Documento eliminado"}


# ==================== VARIABLES DE RENDERIZADO ====================

def _build_integrator_vars(integrator: dict) -> dict:
    contacts = integrator.get("contacts") or []
    primary = contacts[0] if contacts else {}
    contact_name = primary.get("name") or primary.get("full_name") or primary.get("first_name", "")
    contact_email = primary.get("email", "") or integrator.get("email", "")
    contact_phone = primary.get("phone", "")
    return {
        "nombre_integrador": integrator.get("name", ""),
        "razon_social": integrator.get("name", ""),
        "rif": integrator.get("rif", ""),
        "email": contact_email,
        "telefono": contact_phone,
        "contacto": contact_name,
        "estado": integrator.get("integrator_status", ""),
        "aplicativo": integrator.get("app_name", ""),
        "fase": integrator.get("integration_phase", ""),
    }


def _build_new_product_vars(product: dict) -> dict:
    # Obtener nombres de responsables desde equipo_fase si existe
    equipo = product.get("equipo_fase") or []
    desarrollador = ""
    sqa = ""
    for m in equipo:
        role = (m.get("role") or "").lower()
        if "desarroll" in role or "líder" in role or "lider" in role:
            desarrollador = m.get("name", "")
        if "sqa" in role or "analista" in role:
            sqa = m.get("name", "")
    if not desarrollador and (product.get("responsable_role") or "").lower().startswith("líder"):
        desarrollador = product.get("responsable_nombre", "")
    if not sqa and "sqa" in (product.get("responsable_role") or "").lower():
        sqa = product.get("responsable_nombre", "")
    return {
        "producto": product.get("service_name", ""),
        "categoria": product.get("component_type", ""),
        "estado": product.get("status", ""),
        "desarrollador": desarrollador,
        "sqa": sqa,
        "fecha_entrega": product.get("fecha_entrega", ""),
        "banco": product.get("bank_name", ""),
    }


def _render_vars(text: str, variables: dict) -> str:
    if not text:
        return ""
    result = text
    for key, val in variables.items():
        val_str = str(val) if val is not None else ""
        result = result.replace(f"{{{{{key}}}}}", val_str)
        result = result.replace(f"{{{key}}}", val_str)
    return result


# ==================== ENVÍO DE EMAIL GENÉRICO ====================

async def _send_and_log(
    to_list: List[str],
    subject: str,
    message: str,
    variables: dict,
    external_files: List[UploadFile],
    internal_doc_ids_json: str,
    current_user: dict,
    folder: str,
    action_key: str,
):
    """Core de envío: renderiza variables, guarda adjuntos, envía y devuelve metadatos de bitácora."""
    if not to_list:
        raise HTTPException(status_code=400, detail="Debe indicar al menos un destinatario")
    if not subject.strip():
        raise HTTPException(status_code=400, detail="El asunto es obligatorio")

    rendered_subject = _render_vars(subject, variables)
    rendered_message_html = _render_vars(message.replace("\n", "<br>"), variables)

    html = f"""
    <div style=\"font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;\">
        <p>{rendered_message_html}</p>
        <hr>
        <p style=\"color: #666; font-size: 11px;\">Comunicación enviada desde Gestor MegaNexus</p>
    </div>
    """

    # Guardar adjuntos externos
    upload_dir = f"/app/backend/uploads/entity_emails/{folder}"
    os.makedirs(upload_dir, exist_ok=True)
    saved_files = []
    for f in external_files:
        if f and f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            # Subir también a Object Storage usando el path relativo dentro de uploads
            rel = os.path.relpath(file_path, "/app/backend/uploads")
            save_pdf_dual(file_path, content, rel)
            saved_files.append({"filename": f.filename, "path": file_path})

    # Cargar documentos internos
    try:
        doc_ids = json.loads(internal_doc_ids_json or "[]")
    except (json.JSONDecodeError, ValueError):
        doc_ids = []
    internal_files_info = []
    for did in doc_ids:
        doc = await db.entity_documents.find_one({"document_id": did}, {"_id": 0})
        if doc:
            path = f"/app/backend{doc['url']}"
            if os.path.exists(path):
                internal_files_info.append({"filename": doc["filename"], "path": path})

    # Construir adjuntos para SMTP
    email_attachments = []
    for info in saved_files + internal_files_info:
        if os.path.exists(info["path"]):
            with open(info["path"], "rb") as fh:
                email_attachments.append({"filename": info["filename"], "content": fh.read()})

    email_result = await send_email(
        to=to_list,
        subject=rendered_subject,
        html=html,
        action=action_key,
        attachments=email_attachments if email_attachments else None,
    )

    attachments_names = [f["filename"] for f in saved_files + internal_files_info]
    return {
        "subject": rendered_subject,
        "message_preview": rendered_message_html[:200],
        "attachments": attachments_names,
        "email_status": email_result.get("status"),
        "email_result": email_result,
    }


# ==================== INTEGRADORES ====================

@router.post("/integrators/{integrator_id}/send-email")
async def send_integrator_email(
    integrator_id: str,
    recipients: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    internal_doc_ids: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None)
):
    current_user = await get_current_user(authorization)
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")

    # Permisología: implementador asignado, gestor, supervisor jerárquico o admin
    user_id = current_user.get("user_id", "")
    user_role = current_user.get("role", "")
    impl_id = integrator.get("implementador_user_id")
    gestor_id = integrator.get("gestor_user_id")
    is_owner = user_id in (impl_id, gestor_id) if (impl_id or gestor_id) else False
    is_admin = user_role == "admin"
    is_supervisor = current_user.get("cargo") in ("Gerente", "Director", "Supervisor")
    if not (is_owner or is_admin or is_supervisor):
        raise HTTPException(status_code=403, detail="Solo el implementador/gestor asignado o su supervisor puede notificar")

    try:
        to_list = json.loads(recipients)
        if not isinstance(to_list, list):
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Destinatarios inválidos")
    to_list = [t for t in to_list if t and "@" in t]

    variables = _build_integrator_vars(integrator)
    meta = await _send_and_log(
        to_list, subject, message, variables, files, internal_doc_ids,
        current_user, folder=f"integrators/{integrator_id}", action_key="integrator_notification",
    )

    # Registrar en bitácora del integrador
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    now = datetime.now(timezone.utc).isoformat()
    attachments_text = f" ({len(meta['attachments'])} adjunto(s))" if meta["attachments"] else ""
    bitacora_entry = {
        "entry_id": f"bit_{uuid.uuid4().hex[:12]}",
        "integrator_id": integrator_id,
        "description": f"[Notificación enviada] {meta['subject']}{attachments_text} → {', '.join(to_list)}",
        "date": now[:10],
        "created_at": now,
        "created_by": current_user.get("email", ""),
        "created_by_name": user_name,
        "entry_type": "notification",
        "email_data": {
            "subject": meta["subject"],
            "recipients": to_list,
            "attachments": meta["attachments"],
            "sent_at": now,
            "sent_by": user_name,
            "email_status": meta["email_status"],
        },
    }
    await db.bitacora.insert_one(bitacora_entry)
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {"last_contact_date": bitacora_entry["date"]}}
    )

    logging.info(f"Email integrador {integrator_id} enviado a {to_list} por {user_name}")
    return {
        "status": "sent",
        "message": f"Comunicación enviada a {', '.join(to_list)} y registrada en bitácora",
        "attachments_count": len(meta["attachments"]),
    }


@router.post("/integrators/{integrator_id}/preview-email")
async def preview_integrator_email(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")
    variables = _build_integrator_vars(integrator)
    return {
        "subject": _render_vars(body.get("subject", ""), variables),
        "message": _render_vars(body.get("message", ""), variables),
    }


# ==================== NUEVOS PRODUCTOS ====================

@router.post("/new-products/{product_id}/send-email")
async def send_new_product_email(
    product_id: str,
    recipients: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    internal_doc_ids: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None)
):
    current_user = await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    # Permisología: desarrollador/SQA asignado o admin
    user_id = current_user.get("user_id", "")
    user_role = current_user.get("role", "")
    responsable_id = product.get("usuario_responsable_fase")
    equipo_ids = [e.get("user_id") for e in (product.get("equipo_fase") or [])]
    is_owner = user_id == responsable_id or user_id in equipo_ids
    is_admin = user_role == "admin"
    is_supervisor = current_user.get("cargo") in ("Gerente", "Director", "Supervisor")
    if not (is_owner or is_admin or is_supervisor):
        raise HTTPException(status_code=403, detail="Solo el equipo asignado o su supervisor puede notificar")

    try:
        to_list = json.loads(recipients)
        if not isinstance(to_list, list):
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Destinatarios inválidos")
    to_list = [t for t in to_list if t and "@" in t]

    variables = _build_new_product_vars(product)
    meta = await _send_and_log(
        to_list, subject, message, variables, files, internal_doc_ids,
        current_user, folder=f"new_products/{product_id}", action_key="new_product_notification",
    )

    # Registrar en bitácora de evolución
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    now = datetime.now(timezone.utc)
    attachments_text = f" ({len(meta['attachments'])} adjunto(s))" if meta["attachments"] else ""
    evo_doc = {
        "entry_id": f"npe_{uuid.uuid4().hex[:8]}",
        "product_id": product_id,
        "comment": f"[Notificación enviada] {meta['subject']}{attachments_text} → {', '.join(to_list)}",
        "phase": product.get("status", "Negociación"),
        "date": now.strftime("%Y-%m-%d"),
        "created_at": now.isoformat(),
        "author_user_id": current_user.get("user_id", ""),
        "author_name": user_name,
        "entry_type": "notification",
        "email_data": {
            "subject": meta["subject"],
            "recipients": to_list,
            "attachments": meta["attachments"],
            "sent_at": now.isoformat(),
            "sent_by": user_name,
            "email_status": meta["email_status"],
        },
    }
    await db.new_product_evolution.insert_one(evo_doc)

    logging.info(f"Email nuevo producto {product_id} enviado a {to_list} por {user_name}")
    return {
        "status": "sent",
        "message": f"Comunicación enviada a {', '.join(to_list)} y registrada en bitácora",
        "attachments_count": len(meta["attachments"]),
    }


@router.post("/new-products/{product_id}/preview-email")
async def preview_new_product_email(product_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    variables = _build_new_product_vars(product)
    return {
        "subject": _render_vars(body.get("subject", ""), variables),
        "message": _render_vars(body.get("message", ""), variables),
    }
