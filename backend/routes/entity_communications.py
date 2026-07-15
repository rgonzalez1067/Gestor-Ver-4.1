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
from services.pdf_storage import save_pdf_dual, load_attachment_bytes, storage_name_from_upload_url
from services.email_service import send_email
from services.signature import build_signature_html

router = APIRouter()

VALID_CONTEXTS = {"CLIENTES", "INTEGRADORES", "NUEVOS_PRODUCTOS"}


# ==================== USUARIOS INTERNOS (Autocomplete) ====================

# Perfiles estratégicos para el modal de Notificaciones de Proyectos.
# Equipo de Ventas (cualquier subárea: Pyme/Corporativas/...), Equipo de
# Implementación (cualquier cargo) y Dirección/Directores.


def _is_strategic_profile(u: dict) -> bool:
    """Incluye TODO el Equipo de Ventas (cualquier subárea), TODO el Equipo de
    Implementación (cualquier cargo) y Dirección/Directores."""
    cargo = (u.get("cargo") or "").strip().lower()
    dept = (u.get("departamento") or "").strip().lower()
    # Dirección / Directores
    if cargo == "director" or dept in ("dirección", "direccion"):
        return True
    # Equipo de Ventas (Ventas Pyme, Ventas Corporativas, u otra subárea "Ventas ...")
    if dept.startswith("ventas"):
        return True
    # Equipo de Implementación (cualquier cargo)
    if dept in ("implementación", "implementacion"):
        return True
    return False


@router.get("/users/internal-emails")
async def list_internal_emails(
    profile: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Devuelve lista de usuarios activos para autocompletar destinatarios.

    Si `profile=strategic`, aplica el filtro forzado por roles estratégicos
    (Ventas Pyme/Corp, Directores e Implementación) usado en el modal de
    Notificaciones de Proyectos.
    """
    await get_current_user(authorization)
    users = await db.users.find(
        {"is_active": {"$ne": False}},
        {"_id": 0, "user_id": 1, "email": 1, "first_name": 1, "last_name": 1, "role": 1, "cargo": 1, "departamento": 1}
    ).to_list(500)
    strategic = (profile or "").strip().lower() == "strategic"
    result = []
    for u in users:
        email = (u.get("email") or "").strip()
        if not email or "@" not in email:
            continue
        if strategic and not _is_strategic_profile(u):
            continue
        full_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or email
        result.append({
            "user_id": u.get("user_id", ""),
            "email": email,
            "full_name": full_name,
            "role": u.get("role", ""),
            "cargo": u.get("cargo", ""),
            "departamento": u.get("departamento", ""),
            "label": f"{full_name} ({email})",
        })
    result.sort(key=lambda x: x["full_name"].lower())
    return result


# ==================== GRUPOS DE DESTINATARIOS CC (reutilizables) ====================

class CcGroupCreate(BaseModel):
    name: str
    emails: List[str] = []


@router.get("/cc-groups")
async def list_cc_groups(authorization: Optional[str] = Header(None)):
    """Lista los grupos de destinatarios CC guardados (compartidos por el equipo)."""
    await get_current_user(authorization)
    groups = await db.cc_groups.find({}, {"_id": 0, "name_lower": 0}).to_list(500)
    groups.sort(key=lambda g: (g.get("name") or "").lower())
    return groups


@router.post("/cc-groups")
async def create_cc_group(body: CcGroupCreate, authorization: Optional[str] = Header(None)):
    """Crea (o actualiza por nombre) un grupo reutilizable de destinatarios CC."""
    user = await get_current_user(authorization)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del grupo es obligatorio")
    emails, seen = [], set()
    for e in (body.emails or []):
        e = (e or "").strip()
        if e and "@" in e and e.lower() not in seen:
            seen.add(e.lower())
            emails.append(e)
    if not emails:
        raise HTTPException(status_code=400, detail="El grupo debe tener al menos un correo válido")
    now = datetime.now(timezone.utc).isoformat()
    creator = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    existing = await db.cc_groups.find_one({"name_lower": name.lower()})
    if existing:
        await db.cc_groups.update_one(
            {"group_id": existing["group_id"]},
            {"$set": {"name": name, "emails": emails, "updated_at": now}},
        )
        existing.update({"name": name, "emails": emails, "updated_at": now})
        existing.pop("_id", None)
        existing.pop("name_lower", None)
        return existing
    group = {
        "group_id": str(uuid.uuid4()),
        "name": name,
        "name_lower": name.lower(),
        "emails": emails,
        "created_by_user_id": user.get("user_id"),
        "created_by_name": creator,
        "created_at": now,
    }
    await db.cc_groups.insert_one({**group})
    group.pop("name_lower", None)
    return group


@router.delete("/cc-groups/{group_id}")
async def delete_cc_group(group_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un grupo de destinatarios CC."""
    await get_current_user(authorization)
    res = await db.cc_groups.delete_one({"group_id": group_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    return {"success": True}


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

    # Firma institucional global: datos dinámicos del usuario que detona el envío
    variables = {**variables, "Firma_Notificacion_Global": await build_signature_html(current_user)}

    rendered_subject = _render_vars(subject, variables)
    rendered_message_html = _render_vars(message.replace("\n", "<br>"), variables)

    html = f"""
    <div style=\"font-family: Arial, sans-serif; width: 95%; max-width: 900px; margin: 0 auto;\">
        <p>{rendered_message_html}</p>
        <hr>
        <p style=\"color: #666; font-size: 11px;\">Comunicación enviada desde Gestor MegaNexus</p>
    </div>
    """

    # Guardar adjuntos externos (persistencia) y conservar bytes en memoria.
    upload_dir = f"/app/backend/uploads/entity_emails/{folder}"
    os.makedirs(upload_dir, exist_ok=True)
    saved_files = []
    email_attachments = []
    for f in external_files:
        if f and f.filename:
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            file_path = os.path.join(upload_dir, safe_name)
            content = await f.read()
            # Subir también a Object Storage usando el path relativo dentro de uploads
            rel = os.path.relpath(file_path, "/app/backend/uploads")
            save_pdf_dual(file_path, content, rel)
            saved_files.append({"filename": f.filename, "path": file_path})
            # Bytes recién leídos: se adjuntan directamente (no se re-leen de disco).
            email_attachments.append({"filename": f.filename, "content": content})

    # Cargar documentos internos desde el mismo origen seguro (Object Storage + fallback disco)
    try:
        doc_ids = json.loads(internal_doc_ids_json or "[]")
    except (json.JSONDecodeError, ValueError):
        doc_ids = []
    internal_files_info = []
    missing_docs = []
    for did in doc_ids:
        doc = await db.entity_documents.find_one({"document_id": did}, {"_id": 0})
        if not doc:
            missing_docs.append(did)
            logging.error(f"[entity-email] Documento interno inexistente: doc_id={did} folder={folder}")
            continue
        content_bytes = load_attachment_bytes(doc.get("url", ""))
        if content_bytes is None:
            missing_docs.append(doc.get("filename") or did)
            logging.error(
                f"[entity-email] Adjunto NO localizable: doc_id={did} url={doc.get('url')} "
                f"storage_key={storage_name_from_upload_url(doc.get('url',''))} folder={folder}"
            )
            continue
        internal_files_info.append({"filename": doc["filename"], "path": f"/app/backend{doc['url']}"})
        email_attachments.append({"filename": doc["filename"], "content": content_bytes})

    # Fallback de seguridad: abortar si algún adjunto seleccionado no se localizó.
    if missing_docs:
        raise HTTPException(
            status_code=422,
            detail=(
                "No se pudo adjuntar el/los documento(s): "
                + ", ".join(str(m) for m in missing_docs)
                + ". El envío fue abortado para evitar un correo sin anexos. "
                "Verifique que el documento exista en el repositorio e intente nuevamente."
            ),
        )

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


# ==================== COMUNICACIÓN MASIVA A INTEGRADORES (BCC) ====================

INTEGRATION_TYPE_LABELS = {
    "CR": "CR — Caja Registradora",
    "LP": "LP — Link de Pago",
    "PG": "PG — Payment Gateway",
    "MP": "MP — Android (Mobile POS)",
    "TK": "TK — Tokenizador",
}


def _integrator_contact_name(intg: dict) -> str:
    contacts = intg.get("contacts") or []
    if isinstance(contacts, list) and contacts:
        return (contacts[0].get("name") or "").strip()
    return ""


async def _require_mass_comm(current_user: dict):
    """Función especial: solo admin o quien tenga el flag 'integradores:mass_comm'."""
    if current_user.get("role") == "admin":
        return
    if "integradores:mass_comm" in (current_user.get("special_permissions") or []):
        return
    raise HTTPException(status_code=403, detail="No tiene habilitada la función de Comunicación Masiva a Integradores")


@router.get("/integrators/mass/recipients")
async def list_mass_recipients(integration_type: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Lista los integradores para la grilla de selección de la Comunicación Masiva.
    Filtra opcionalmente por tipo de integración (CR/LP/PG/MP/TK)."""
    current_user = await get_current_user(authorization)
    await _require_mass_comm(current_user)
    q = {}
    if integration_type and integration_type not in ("ALL", "", "TODOS"):
        q["integration_type"] = integration_type
    items = []
    cursor = db.integrators.find(
        q, {"_id": 0, "integrator_id": 1, "name": 1, "email": 1, "contacts": 1, "integration_type": 1}
    ).sort("name", 1)
    async for intg in cursor:
        email = (intg.get("email") or "").strip()
        it = intg.get("integration_type") or ""
        items.append({
            "integrator_id": intg.get("integrator_id"),
            "name": intg.get("name", ""),
            "contact": _integrator_contact_name(intg),
            "email": email,
            "has_email": bool(email and "@" in email),
            "integration_type": it,
            "integration_type_label": INTEGRATION_TYPE_LABELS.get(it, it or "—"),
        })
    return {
        "recipients": items,
        "total": len(items),
        "with_email": sum(1 for i in items if i["has_email"]),
        "integration_types": [{"code": k, "label": v} for k, v in INTEGRATION_TYPE_LABELS.items()],
    }


@router.post("/integrators/mass/communication")
async def send_mass_communication(
    template_id: str = Form(...),
    integrator_ids: str = Form(...),
    internal_doc_ids: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None),
):
    """Envía una comunicación masiva a los integradores seleccionados usando una
    plantilla de la biblioteca (context=INTEGRADORES). Todos los correos viajan en
    BCC (copia oculta) para preservar la privacidad; los adjuntos (repositorio +
    archivos locales) son idénticos para todo el lote."""
    current_user = await get_current_user(authorization)
    await _require_mass_comm(current_user)

    try:
        ids = json.loads(integrator_ids)
        assert isinstance(ids, list)
    except (json.JSONDecodeError, ValueError, AssertionError):
        raise HTTPException(status_code=400, detail="Lista de integradores inválida")
    if not ids:
        raise HTTPException(status_code=400, detail="Debe seleccionar al menos un integrador")

    # Destinatarios (correos únicos y válidos) de los integradores seleccionados.
    recipients, seen = [], set()
    cursor = db.integrators.find({"integrator_id": {"$in": ids}}, {"_id": 0, "email": 1})
    async for intg in cursor:
        e = (intg.get("email") or "").strip()
        if e and "@" in e and e.lower() not in seen:
            recipients.append(e); seen.add(e.lower())
    if not recipients:
        raise HTTPException(status_code=400, detail="Ninguno de los integradores seleccionados tiene un correo válido")

    tpl = await db.email_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    variables = {
        "fecha_sistema": now_str, "Fecha_Sistema": now_str,
        "Firma_Notificacion_Global": await build_signature_html(current_user),
    }
    subject = _render_vars(tpl.get("subject", "") or "Comunicación", variables)
    html = _render_vars(tpl.get("body_html", "") or tpl.get("body", "") or "", variables)

    # Adjuntos: archivos locales + documentos del repositorio (entity_documents).
    upload_dir = "/app/backend/uploads/entity_emails/integradores_masivo"
    os.makedirs(upload_dir, exist_ok=True)
    email_attachments, attachment_names = [], []
    for f in files:
        if f and f.filename:
            content = await f.read()
            safe_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
            path = os.path.join(upload_dir, safe_name)
            save_pdf_dual(path, content, os.path.relpath(path, "/app/backend/uploads"))
            email_attachments.append({"filename": f.filename, "content": content})
            attachment_names.append(f.filename)

    try:
        doc_ids = json.loads(internal_doc_ids or "[]")
    except (json.JSONDecodeError, ValueError):
        doc_ids = []
    missing = []
    for did in doc_ids:
        doc = await db.entity_documents.find_one({"document_id": did}, {"_id": 0})
        if not doc:
            missing.append(did); continue
        content_bytes = load_attachment_bytes(doc.get("url", ""))
        if content_bytes is None:
            missing.append(doc.get("filename") or did); continue
        email_attachments.append({"filename": doc["filename"], "content": content_bytes})
        attachment_names.append(doc["filename"])
    if missing:
        raise HTTPException(
            status_code=422,
            detail="No se pudo adjuntar el/los documento(s): " + ", ".join(str(m) for m in missing)
                   + ". El envío fue abortado para evitar un correo sin anexos.",
        )

    from config import SENDER_EMAIL
    result = await send_email(
        to=[SENDER_EMAIL],
        subject=subject,
        html=html,
        action="integrator_mass_communication",
        attachments=email_attachments or None,
        bcc=recipients,
    )

    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get("email", "")
    now = datetime.now(timezone.utc).isoformat()
    await db.bitacora.insert_one({
        "entry_id": f"bit_{uuid.uuid4().hex[:12]}",
        "action": "integrator_mass_communication",
        "description": f"[Comunicación masiva] '{subject}' → {len(recipients)} integrador(es) en BCC"
                       + (f" ({len(attachment_names)} adjunto(s))" if attachment_names else ""),
        "date": now[:10], "created_at": now,
        "created_by": current_user.get("email", ""), "created_by_name": user_name,
        "recipients_count": len(recipients), "template_id": template_id,
        "attachments": attachment_names, "email_status": result.get("status"),
    })

    return {
        "status": result.get("status"),
        "recipients_count": len(recipients),
        "attachments_count": len(attachment_names),
        "subject": subject,
        "message": f"Comunicación masiva enviada en BCC a {len(recipients)} integrador(es).",
    }



@router.post("/integrators/{integrator_id}/preview-email")
async def preview_integrator_email(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")
    variables = _build_integrator_vars(integrator)
    variables["Firma_Notificacion_Global"] = await build_signature_html(current_user)
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
    current_user = await get_current_user(authorization)
    product = await db.new_products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    variables = _build_new_product_vars(product)
    variables["Firma_Notificacion_Global"] = await build_signature_html(current_user)
    return {
        "subject": _render_vars(body.get("subject", ""), variables),
        "message": _render_vars(body.get("message", ""), variables),
    }
