"""Route module: banks.py"""
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


router = APIRouter()

# ==================== BANK LOGO UPLOAD ====================

@router.post("/banks/upload-logo")
async def upload_bank_logo(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen (PNG, JPG, WEBP)")
    
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        ext = "png"
    
    filename = f"bank_logo_{uuid.uuid4().hex[:8]}.{ext}"
    logo_dir = os.path.join(UPLOADS_DIR, "bank_logos")
    os.makedirs(logo_dir, exist_ok=True)
    filepath = os.path.join(logo_dir, filename)
    
    content = await file.read()
    
    # Resize to 150x150 using PIL
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGBA" if ext == "png" else "RGB")
        img.thumbnail((150, 150), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG" if ext == "png" else "JPEG", quality=90)
        content = buf.getvalue()
    except Exception:
        pass  # If PIL fails, save original
    
    with open(filepath, "wb") as f:
        f.write(content)
    
    logo_url = f"/api/uploads/bank_logos/{filename}"
    return {"logo_url": logo_url}

# ==================== INTEGRATION REPORT ====================

@router.get("/banks/integrations/report")
async def get_integrations_report(group_by: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Reporte global consolidado de todas las integraciones en curso de todos los bancos.
    Soporta agrupación dinámica: group_by=bank|product|phase (o None para lista plana)."""
    await get_current_user(authorization)
    
    PHASE_ORDER = {"Masificación": 0, "Primer Prod": 1, "PreProd": 2}
    PHASE_LABELS = {"PreProd": "Pre-Producción", "Primer Prod": "Primera Producción", "Masificación": "Masificación"}
    
    banks = await db.banks.find(
        {"integrations": {"$exists": True, "$ne": []}},
        {"_id": 0, "bank_id": 1, "name": 1, "bank_logo_url": 1, "integrations": 1}
    ).to_list(500)
    
    report = []
    for bank in banks:
        for intg in bank.get("integrations", []):
            # Migrate old status to new 3-state model
            migrated_intg = migrate_integration_status(intg.copy())
            report.append({
                "bank_id": bank["bank_id"],
                "bank_name": bank["name"],
                "bank_logo_url": bank.get("bank_logo_url"),
                "integration_id": migrated_intg.get("integration_id"),
                "service_name": migrated_intg.get("service_name"),
                "component_type": migrated_intg.get("component_type"),
                "status": migrated_intg.get("status"),
                "notes": migrated_intg.get("notes"),
                "created_at": migrated_intg.get("created_at")
            })
    
    report.sort(key=lambda x: PHASE_ORDER.get(x["status"], 99))
    
    if not group_by:
        return report
    
    groups = {}
    for item in report:
        if group_by == "bank":
            key = item["bank_name"]
            label = item["bank_name"]
        elif group_by == "product":
            key = item["service_name"]
            label = item["service_name"]
        elif group_by == "phase":
            key = item["status"]
            label = PHASE_LABELS.get(item["status"], item["status"])
        else:
            return report
        
        if key not in groups:
            groups[key] = {"label": label, "count": 0, "items": []}
        groups[key]["count"] += 1
        groups[key]["items"].append(item)
    
    return {"group_by": group_by, "total": len(report), "groups": groups}

# ==================== PRODUCT EVOLUTION LOG ====================

@router.get("/banks/{bank_id}/integrations/{integration_id}/evolution")
async def get_product_evolution(bank_id: str, integration_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene el historial de evolución de una integración de producto."""
    await get_current_user(authorization)
    entries = await db.bank_evolution_log.find(
        {"bank_id": bank_id, "integration_id": integration_id}, {"_id": 0}
    ).sort("date", -1).to_list(500)
    return entries

@router.post("/banks/{bank_id}/integrations/{integration_id}/evolution")
async def add_product_evolution(bank_id: str, integration_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Agrega una entrada de evolución a una integración de producto."""
    await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    
    intg = next((i for i in bank.get("integrations", []) if i.get("integration_id") == integration_id), None)
    if not intg:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    entry = ProductEvolutionEntry(
        bank_id=bank_id,
        integration_id=integration_id,
        comment=body.get("comment", ""),
        phase=body.get("phase", intg.get("status", "PreProd")),
        date=body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    doc = entry.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bank_evolution_log.insert_one(doc)
    doc.pop('_id', None)
    return doc

@router.patch("/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}")
async def update_product_evolution(bank_id: str, integration_id: str, entry_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualiza una entrada de evolución de producto."""
    await get_current_user(authorization)
    update_fields = {}
    for field in ["comment", "phase", "date"]:
        if field in body:
            update_fields[field] = body[field]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.bank_evolution_log.update_one(
        {"entry_id": entry_id, "bank_id": bank_id, "integration_id": integration_id}, {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    updated = await db.bank_evolution_log.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated

@router.delete("/banks/{bank_id}/integrations/{integration_id}/evolution/{entry_id}")
async def delete_product_evolution(bank_id: str, integration_id: str, entry_id: str, authorization: Optional[str] = Header(None)):
    """Elimina una entrada de evolución de producto."""
    await get_current_user(authorization)
    result = await db.bank_evolution_log.delete_one({"entry_id": entry_id, "bank_id": bank_id, "integration_id": integration_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return {"message": "Entrada eliminada"}

# ==================== BANKS ENDPOINTS ====================

@router.post("/banks", response_model=Bank)
async def create_bank(bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    bank = Bank(**bank_data.model_dump())
    doc = bank.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    # Asegurar contact_ids en cada contacto
    for c in doc.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"bcn_{uuid.uuid4().hex[:8]}"
    # Sincronizar campos legacy con primer contacto Principal (o el primero disponible)
    if doc.get("contacts"):
        primary = next((c for c in doc["contacts"] if c.get("contact_type") == "Principal"), doc["contacts"][0])
        full = (primary.get("full_name") or f"{primary.get('first_name','')} {primary.get('last_name','')}").strip()
        if full and not doc.get("contact_name"):
            doc["contact_name"] = full
        if primary.get("email") and not doc.get("contact_email"):
            doc["contact_email"] = primary.get("email")
        if primary.get("phone") and not doc.get("contact_phone"):
            doc["contact_phone"] = primary.get("phone")
    await db.banks.insert_one(doc)
    # Convertir created_at de vuelta para Pydantic
    doc['created_at'] = bank.created_at
    return Bank(**{k: v for k, v in doc.items() if k != '_id'})

# Status migration map: old states -> new states
STATUS_MIGRATION = {
    "Negoc.": "PreProd",
    "DESA": "PreProd", 
    "SQA": "Primer Prod",
    "Imple.": "Primer Prod",
    "PreProd": "PreProd",
    "Completado": "Masificación",
    "Primer Prod": "Primer Prod",
    "Masificación": "Masificación"
}

def migrate_integration_status(integration):
    """Migrate old integration status to new 3-state model"""
    old_status = integration.get("status", "PreProd")
    integration["status"] = STATUS_MIGRATION.get(old_status, "PreProd")
    return integration


def ensure_bank_contacts(bank: dict) -> dict:
    """Si el banco no tiene `contacts` pero sí tiene contact_name/email/phone legacy,
    genera un primer contacto en el array para que la UI pueda mostrarlo.
    No persiste — solo enriquece el documento devuelto al cliente.
    """
    contacts = bank.get("contacts") or []
    if not contacts and (bank.get("contact_name") or bank.get("contact_email") or bank.get("contact_phone")):
        full = (bank.get("contact_name") or "").strip()
        # split simple: primer token = first_name, resto = last_name
        parts = full.split(" ", 1) if full else ["", ""]
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
        bank["contacts"] = [{
            "contact_id": f"bcn_legacy_{uuid.uuid4().hex[:6]}",
            "first_name": first,
            "last_name": last,
            "full_name": full,
            "position": "",
            "email": bank.get("contact_email") or "",
            "phone": bank.get("contact_phone") or "",
            "contact_type": "Principal"
        }]
    return bank

@router.get("/banks", response_model=List[Bank])
async def get_banks(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    banks = await db.banks.find({}, {"_id": 0}).to_list(1000)
    for bank in banks:
        ca = bank.get('created_at')
        if ca is None:
            bank['created_at'] = datetime.now(timezone.utc)
        elif isinstance(ca, str):
            bank['created_at'] = datetime.fromisoformat(ca)
        # Migrate old integration statuses to new 3-state model
        if bank.get("integrations"):
            bank["integrations"] = [migrate_integration_status(i) for i in bank["integrations"]]
        # Migrate legacy contact fields → contacts[] (in-memory only)
        ensure_bank_contacts(bank)
    return banks

@router.put("/banks/{bank_id}", response_model=Bank)
async def update_bank(bank_id: str, bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    payload = bank_data.model_dump()
    # Asegurar contact_ids
    for c in payload.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"bcn_{uuid.uuid4().hex[:8]}"
    # Sincronizar campos legacy con primer contacto si está presente
    if payload.get("contacts"):
        primary = next((c for c in payload["contacts"] if c.get("contact_type") == "Principal"), payload["contacts"][0])
        full = (primary.get("full_name") or f"{primary.get('first_name','')} {primary.get('last_name','')}").strip()
        if full and not payload.get("contact_name"):
            payload["contact_name"] = full
        if primary.get("email") and not payload.get("contact_email"):
            payload["contact_email"] = primary.get("email")
        if primary.get("phone") and not payload.get("contact_phone"):
            payload["contact_phone"] = primary.get("phone")
    result = await db.banks.update_one(
        {"bank_id": bank_id},
        {"$set": payload}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    ca = bank.get('created_at')
    if ca is None:
        bank['created_at'] = datetime.now(timezone.utc)
    elif isinstance(ca, str):
        bank['created_at'] = datetime.fromisoformat(ca)
    # Migrate old integration statuses to new 3-state model
    if bank.get("integrations"):
        bank["integrations"] = [migrate_integration_status(i) for i in bank["integrations"]]
    ensure_bank_contacts(bank)
    return bank

@router.delete("/banks/{bank_id}")
async def delete_bank(bank_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este banco
    quotes_with_bank = await db.quotes.count_documents({
        "$or": [
            {"sponsor_bank_id": bank_id},
            {"services.bank_id": bank_id}
        ]
    })
    if quotes_with_bank > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el banco porque está asociado a {quotes_with_bank} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.banks.delete_one({"bank_id": bank_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    return {"message": "Banco eliminado exitosamente"}

# ==================== BANK INTEGRATIONS ====================

@router.get("/banks/{bank_id}/detail")
async def get_bank_detail(bank_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene el detalle completo de un banco incluyendo sus medios de pago activos y pipeline I+D."""
    await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    if isinstance(bank.get('created_at'), str):
        bank['created_at'] = datetime.fromisoformat(bank['created_at'])
    # Migrate old integration statuses to new 3-state model
    if bank.get("integrations"):
        bank["integrations"] = [migrate_integration_status(i) for i in bank["integrations"]]

    # Mirroring: Include pipeline products (Negociación/DESA/SQA) from Nuevos Productos
    pipeline_products = await db.new_products.find(
        {"bank_id": bank_id, "status": {"$in": ["Negociación", "DESA", "SQA"]}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    bank["pipeline_products"] = pipeline_products

    return bank

@router.post("/banks/{bank_id}/integrations")
async def add_bank_integration(bank_id: str, integration: BankIntegration, authorization: Optional[str] = Header(None)):
    """Agrega una nueva integración en curso a un banco."""
    await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    
    doc = integration.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.banks.update_one(
        {"bank_id": bank_id},
        {"$push": {"integrations": doc}}
    )
    return doc

@router.put("/banks/{bank_id}/integrations/{integration_id}")
async def update_bank_integration(bank_id: str, integration_id: str, update_data: dict, authorization: Optional[str] = Header(None)):
    """Actualiza el estatus o datos de una integración. Valida permisos de fase y sincroniza bidireccionalmente."""
    user = await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    
    integrations = bank.get("integrations", [])
    found = False
    old_status = None
    target_idx = -1
    source_product_id = None
    for i, intg in enumerate(integrations):
        if intg.get("integration_id") == integration_id:
            old_status = intg.get("status")
            source_product_id = intg.get("source_product_id")
            target_idx = i

            # Validación de Fase A: si el producto fuente está en Negociación/DESA/SQA, rechazar
            if source_product_id:
                source_product = await db.new_products.find_one(
                    {"product_id": source_product_id},
                    {"_id": 0, "status": 1}
                )
                if source_product and source_product.get("status") in ("Negociación", "DESA", "SQA"):
                    raise HTTPException(
                        status_code=403,
                        detail="Este producto está siendo gestionado desde el módulo de Nuevos Productos. No se permite modificar su estado desde Gestión de Bancos en esta fase."
                    )

            for key, val in update_data.items():
                if key in ("status", "notes", "service_name", "component_type"):
                    integrations[i][key] = val
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    
    await db.banks.update_one(
        {"bank_id": bank_id},
        {"$set": {"integrations": integrations}}
    )
    
    # Sync bidireccional: actualizar el new_product vinculado
    new_status = update_data.get("status")
    if new_status and new_status != old_status and source_product_id:
        # Map bank status back to a descriptive status in new_products
        bank_to_np_status = {
            "PreProd": "Promovido",
            "Primer Prod": "Promovido",
            "Masificación": "Promovido",
        }
        np_status = bank_to_np_status.get(new_status)
        if np_status:
            await db.new_products.update_one(
                {"product_id": source_product_id},
                {"$set": {"bank_integration_status": new_status}}
            )
    
    # Notificación simulada al equipo de ventas cuando cambia el estatus
    if new_status and new_status != old_status:
        try:
            sales_roles = ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]
            sales_users = await db.users.find(
                {"cargo": {"$in": sales_roles}},
                {"_id": 0, "email": 1, "first_name": 1, "last_name": 1}
            ).to_list(100)
            
            service_name = integrations[target_idx].get("service_name", "N/A")
            bank_name = bank.get("name", "N/A")
            recipients = [u["email"] for u in sales_users if u.get("email")]
            
            logging.info(
                f"[EMAIL SIMULADO] Notificación de cambio de estatus de integración: "
                f"Banco={bank_name}, Servicio={service_name}, "
                f"De={old_status} -> A={new_status}, "
                f"Destinatarios={recipients if recipients else 'Sin ejecutivos de ventas registrados'}"
            )
        except Exception as e:
            logging.error(f"Error al preparar notificación de integración: {e}")
    
    return integrations[target_idx]

@router.delete("/banks/{bank_id}/integrations/{integration_id}")
async def delete_bank_integration(bank_id: str, integration_id: str, authorization: Optional[str] = Header(None)):
    """Elimina una integración de un banco."""
    await get_current_user(authorization)
    
    result = await db.banks.update_one(
        {"bank_id": bank_id},
        {"$pull": {"integrations": {"integration_id": integration_id}}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return {"message": "Integración eliminada"}

@router.post("/banks/import", response_model=ImportResult)
async def import_banks(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Validar formato de archivo
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Leer archivo
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalizar nombres de columnas
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Mapeo de columnas
        column_mapping = {
            'nombre': 'name', 'tipo': 'type', 'país': 'country', 'pais': 'country'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columnas requeridas
        if 'name' not in df.columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='name', value=None, error_type='missing',
                    message='Columna "Nombre" no encontrada',
                    suggested_action='Asegúrese de que el archivo tenga la columna: Nombre')],
                message='Error: Falta columna requerida (Nombre)'
            )
        
        valid_types = ['Banco', 'Fintech']
        valid_countries = ['Venezuela', 'Estados Unidos']
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                bank_type = str(row.get('type', 'Banco')).strip() if pd.notna(row.get('type')) else 'Banco'
                country = str(row.get('country', 'Venezuela')).strip() if pd.notna(row.get('country')) else 'Venezuela'
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del banco es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Validar tipo (usar default si no es válido)
                if bank_type not in valid_types:
                    bank_type = 'Banco'
                
                # Validar país (usar default si no es válido)
                if country not in valid_countries:
                    country = 'Venezuela'
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.banks.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un banco con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear banco
                bank = Bank(name=name, type=bank_type, country=country, products=[])
                doc = bank.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.banks.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        # Determinar estado final
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} bancos importados correctamente.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors, message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=None, error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté corrupto')],
            message=f'Error: {str(e)}'
        )

@router.get("/banks/export/pdf")
async def export_banks_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    banks = await db.banks.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Bancos y Entidades - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Banco', 'Tipo', 'País', 'Productos']]
    for b in banks:
        products_str = ', '.join([p['product_name'] for p in b.get('products', [])][:3])
        if len(b.get('products', [])) > 3:
            products_str += f" (+{len(b['products']) - 3} más)"
        data.append([
            b['name'][:30],
            b['type'],
            b['country'],
            products_str[:40] if products_str else 'Sin productos'
        ])
    
    table = Table(data, colWidths=[2*inch, 1*inch, 1.2*inch, 2.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B7D4E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bancos.pdf"}
    )



# ==================== REPORTE: PRODUCTOS POR BANCO ====================

@router.get("/banks/report/products-by-bank/pdf")
async def report_products_by_bank_pdf(authorization: Optional[str] = Header(None)):
    """Reporte 'Productos por Banco': PDF elegante con cada banco y sus productos asociados.
    Mismo look & feel que /services/report/banks-by-product/pdf."""
    user = await get_current_user(authorization)
    import weasyprint

    banks = await db.banks.find({}, {"_id": 0}).sort("name", 1).to_list(None)

    # KPIs
    banks_with_products = 0
    banks_without_products = 0
    total_links = 0

    sections_html = []
    for b in banks:
        products = b.get("products") or []
        # Ordenar productos alfabéticamente
        products = sorted(products, key=lambda p: (p.get("product_name") or "").strip().lower())
        if products:
            banks_with_products += 1
            total_links += len(products)
        else:
            banks_without_products += 1

        rows = ""
        if products:
            for i, p in enumerate(products, 1):
                comps = []
                if p.get("vpos_available"):
                    comps.append("VPOS")
                if p.get("gateway_available"):
                    comps.append("Gateway")
                if p.get("mpos_available"):
                    comps.append("mPOS")
                if p.get("link_available"):
                    comps.append("Link")
                comps_html = " ".join(f'<span class="chip">{c}</span>' for c in comps) if comps else '<span class="chip-muted">—</span>'
                rows += (
                    f'<tr>'
                    f'<td class="num">{i}</td>'
                    f'<td class="bank">{(p.get("product_name") or "—").strip()}</td>'
                    f'<td class="comps">{comps_html}</td>'
                    f'</tr>'
                )
        else:
            rows = '<tr><td colspan="3" class="empty">— Sin productos asociados —</td></tr>'

        bank_type = b.get("type") or "—"
        bank_code = b.get("bank_code") or "—"
        country = b.get("country") or "—"

        sections_html.append(f"""
        <div class="product">
          <div class="prod-head">
            <div class="prod-title">{b.get('name', '—')}</div>
            <div class="prod-meta"><span>Tipo: <b>{bank_type}</b></span><span>Código: <b>{bank_code}</b></span><span>País: <b>{country}</b></span><span>Productos: <b>{len(products)}</b></span></div>
          </div>
          <table>
            <thead><tr><th class="num">#</th><th>Producto</th><th>Componentes habilitados</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """)

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    user_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Productos por Banco</title>
<style>
  @page {{ size: A4; margin: 18mm 14mm; @bottom-right {{ content: "Pág. " counter(page) " / " counter(pages); font-size: 9px; color: #64748b; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #0f172a; font-size: 10.5px; margin:0; }}
  .cover {{ border-left: 5px solid #0ea5e9; padding: 10px 0 14px 16px; margin-bottom: 18px; }}
  .cover h1 {{ font-size: 22px; margin: 0 0 4px 0; color: #0f172a; letter-spacing: -0.3px; }}
  .cover p {{ margin: 2px 0; color: #475569; font-size: 10px; }}
  .summary {{ display: flex; gap: 8px; margin: 0 0 16px 0; }}
  .stat {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; }}
  .stat .lbl {{ font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: .4px; }}
  .stat .val {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 2px; }}
  .stat.green {{ border-left: 4px solid #10b981; }}
  .stat.amber {{ border-left: 4px solid #f59e0b; }}
  .stat.blue  {{ border-left: 4px solid #0ea5e9; }}
  .stat.slate {{ border-left: 4px solid #64748b; }}
  .product {{ margin-bottom: 12px; page-break-inside: avoid; }}
  .prod-head {{ background: #f1f5f9; border-left: 3px solid #0ea5e9; padding: 6px 10px; border-radius: 4px 4px 0 0; }}
  .prod-title {{ font-size: 12px; font-weight: 700; color: #0c4a6e; }}
  .prod-meta {{ font-size: 9px; color: #475569; margin-top: 2px; display: flex; gap: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0; }}
  thead th {{ background: #0c4a6e; color: white; font-size: 9.5px; padding: 5px 8px; text-align: left; font-weight: 600; }}
  thead th.num {{ text-align: center; }}
  tbody td {{ padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; vertical-align: middle; }}
  td.num {{ text-align: center; color: #64748b; width: 28px; }}
  td.bank {{ font-weight: 600; color: #0f172a; }}
  td.empty {{ text-align: center; color: #94a3b8; font-style: italic; padding: 10px; }}
  .chip {{ display: inline-block; padding: 1px 6px; margin-right: 3px; border-radius: 10px; background: #ecfeff; color: #0e7490; font-size: 8.5px; border: 1px solid #a5f3fc; }}
  .chip-muted {{ display: inline-block; color: #94a3b8; font-size: 9px; font-style: italic; }}
  .footer {{ margin-top: 18px; padding-top: 8px; border-top: 1px solid #e2e8f0; font-size: 8.5px; color: #94a3b8; text-align: center; }}
</style></head>
<body>
  <div class="cover">
    <h1>Productos por Banco</h1>
    <p>Reporte de productos configurados por cada entidad bancaria, con sus componentes habilitados.</p>
    <p>Generado el <b>{now_str}</b> · Por <b>{user_name}</b></p>
  </div>

  <div class="summary">
    <div class="stat slate"><div class="lbl">Bancos totales</div><div class="val">{len(banks)}</div></div>
    <div class="stat green"><div class="lbl">Con productos</div><div class="val">{banks_with_products}</div></div>
    <div class="stat amber"><div class="lbl">Sin productos</div><div class="val">{banks_without_products}</div></div>
    <div class="stat blue"><div class="lbl">Asociaciones totales</div><div class="val">{total_links}</div></div>
  </div>

  {''.join(sections_html)}

  <div class="footer">MegaNexus · Reporte generado automáticamente · Documento confidencial</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"productos_por_banco_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
