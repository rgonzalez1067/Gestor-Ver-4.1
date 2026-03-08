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
    
    # Resize to 100x100 using PIL
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGBA" if ext == "png" else "RGB")
        img.thumbnail((100, 100), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG" if ext == "png" else "JPEG", quality=90)
        content = buf.getvalue()
    except Exception:
        pass  # If PIL fails, save original
    
    with open(filepath, "wb") as f:
        f.write(content)
    
    logo_url = f"/api/uploads/bank_logos/{filename}"
    return {"logo_url": logo_url}

# ==================== BANKS ENDPOINTS ====================

@router.post("/banks", response_model=Bank)
async def create_bank(bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    bank = Bank(**bank_data.model_dump())
    doc = bank.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.banks.insert_one(doc)
    return bank

@router.get("/banks", response_model=List[Bank])
async def get_banks(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    banks = await db.banks.find({}, {"_id": 0}).to_list(1000)
    for bank in banks:
        if isinstance(bank['created_at'], str):
            bank['created_at'] = datetime.fromisoformat(bank['created_at'])
    return banks

@router.put("/banks/{bank_id}", response_model=Bank)
async def update_bank(bank_id: str, bank_data: BankCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.banks.update_one(
        {"bank_id": bank_id},
        {"$set": bank_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Bank not found")
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if isinstance(bank['created_at'], str):
        bank['created_at'] = datetime.fromisoformat(bank['created_at'])
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
    """Obtiene el detalle completo de un banco incluyendo sus medios de pago activos."""
    await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    if isinstance(bank.get('created_at'), str):
        bank['created_at'] = datetime.fromisoformat(bank['created_at'])
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
    """Actualiza el estatus o datos de una integración."""
    await get_current_user(authorization)
    bank = await db.banks.find_one({"bank_id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="Banco no encontrado")
    
    integrations = bank.get("integrations", [])
    found = False
    for i, intg in enumerate(integrations):
        if intg.get("integration_id") == integration_id:
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
    return integrations[i]

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

