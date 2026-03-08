"""Route module: integrators.py"""
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
import shutil
import csv
import base64

router = APIRouter()

# ==================== INTEGRATORS ENDPOINTS ====================

@router.get("/integrators", response_model=List[Integrator])
async def get_integrators(
    authorization: Optional[str] = Header(None),
    integrator_status: Optional[str] = None,
    integrator_type: Optional[str] = None
):
    await get_current_user(authorization)
    
    query = {}
    if integrator_status:
        query['integrator_status'] = integrator_status
    if integrator_type:
        query['integrator_type'] = integrator_type
    
    integrators = await db.integrators.find(query, {"_id": 0}).to_list(1000)
    for intg in integrators:
        if isinstance(intg.get('created_at'), str):
            intg['created_at'] = datetime.fromisoformat(intg['created_at'])
    return integrators

@router.post("/integrators", response_model=Integrator)
async def create_integrator(integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    new_integrator = Integrator(**integrator.model_dump())
    doc = new_integrator.model_dump()
    
    # Auto-initialize certifications to N/A for all products if not provided
    if not doc.get('certifications'):
        cert_products = await db.services.find(
            {"service_type": "Producto", "application_type": {"$in": ["setup", "both"]}},
            {"_id": 0, "service_id": 1}
        ).to_list(1000)
        doc['certifications'] = {p["service_id"]: "N/A" for p in cert_products}
    
    doc['created_at'] = doc['created_at'].isoformat()
    await db.integrators.insert_one(doc)
    doc.pop('_id', None)
    return doc

@router.get("/integrators/{integrator_id}", response_model=Integrator)
async def get_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return integrator

@router.put("/integrators/{integrator_id}", response_model=Integrator)
async def update_integrator(integrator_id: str, integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    
    update_data = integrator.model_dump()
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": update_data}
    )
    
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return updated

@router.delete("/integrators/{integrator_id}")
async def delete_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este integrador
    quotes_with_integrator = await db.quotes.count_documents({
        "integrator_id": integrator_id
    })
    if quotes_with_integrator > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el integrador porque está asociado a {quotes_with_integrator} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.integrators.delete_one({"integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return {"message": "Integrador eliminado exitosamente"}

# Export integrators to Excel
@router.get("/integrators/export/excel")
async def export_integrators_excel(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    import pandas as pd
    
    df = pd.DataFrame(integrators)
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Reorder columns
    columns_order = ['integrator_id', 'name', 'integrator_type', 'app_name', 'integration_modality', 'integrator_status', 'created_at']
    df = df[[c for c in columns_order if c in df.columns]]
    
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Integradores')
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=integradores.xlsx"}
    )

# Export integrators to PDF
@router.get("/integrators/export/pdf")
async def export_integrators_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("<b>Listado de Integradores</b>", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Table data
    table_data = [["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus"]]
    for intg in integrators:
        table_data.append([
            intg.get('name', ''),
            intg.get('integrator_type', ''),
            intg.get('app_name', ''),
            intg.get('integration_modality', ''),
            intg.get('integrator_status', '')
        ])
    
    table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1.3*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.3, 0.5)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=integradores.pdf"}
    )

# Import integrators from Excel/CSV with Upsert logic and detailed validation
@router.post("/integrators/import", response_model=ImportResult)
async def import_integrators(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    updated_count = 0
    skipped_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename,
                    error_type='format', message='El archivo está vacío',
                    suggested_action='Agregue registros al archivo antes de importar')],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        column_mapping = {
            'nombre': 'name', 'nombre_del_integrador': 'name',
            'tipo': 'integrator_type', 'tipo_de_integrador': 'integrator_type',
            'tipo_de_integración': 'integration_type', 'tipo_de_integracion': 'integration_type',
            'tipo_integración': 'integration_type', 'tipo_integracion': 'integration_type',
            'aplicativo': 'app_name', 'nombre_del_aplicativo': 'app_name',
            'modalidad': 'integration_modality', 'modalidad_de_integración': 'integration_modality',
            'modalidad_de_integracion': 'integration_modality',
            'estatus': 'integrator_status', 'estado': 'integrator_status',
            'gestor': 'gestor', 'gestor_asignado': 'gestor',
            'categoría': 'categoria', 'categoria': 'categoria'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        required_columns = ['name', 'integrator_type', 'app_name', 'integration_modality']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None,
                    error_type='missing',
                    message=f'Columnas requeridas no encontradas: {", ".join(missing_columns)}',
                    suggested_action='Asegúrese de que el archivo tenga las columnas: Nombre, Tipo, Aplicativo, Modalidad')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        # Pre-load users and products for validation and cert initialization
        all_users = await db.users.find({"is_active": True}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}).to_list(1000)
        user_names = set()
        for u in all_users:
            full = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            user_names.add(full.lower())
            user_names.add(u.get('email', '').lower())
        
        cert_products = await db.services.find(
            {"service_type": "Producto", "application_type": {"$in": ["setup", "both"]}},
            {"_id": 0, "service_id": 1}
        ).to_list(1000)
        default_certs = {p["service_id"]: "N/A" for p in cert_products}
        
        valid_integration_types = ['CR', 'LP', 'PG', 'MP', 'TK']
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                integrator_type = str(row.get('integrator_type', '')).strip() if pd.notna(row.get('integrator_type')) else ''
                app_name = str(row.get('app_name', '')).strip() if pd.notna(row.get('app_name')) else ''
                integration_modality = str(row.get('integration_modality', '')).strip() if pd.notna(row.get('integration_modality')) else ''
                integrator_status = str(row.get('integrator_status', 'En proceso')).strip() if pd.notna(row.get('integrator_status')) else 'En proceso'
                integration_type = str(row.get('integration_type', '')).strip() if pd.notna(row.get('integration_type')) else ''
                gestor = str(row.get('gestor', '')).strip() if pd.notna(row.get('gestor')) else ''
                categoria = str(row.get('categoria', '')).strip() if pd.notna(row.get('categoria')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del integrador es obligatorio',
                        suggested_action='Ingrese un nombre válido para el integrador'))
                
                if not app_name:
                    row_errors.append(ImportError(row=row_num, column='Aplicativo', value='(vacío)',
                        error_type='missing', message='El nombre del aplicativo es obligatorio',
                        suggested_action='Ingrese el nombre del aplicativo'))
                
                if integrator_type not in INTEGRATOR_TYPES:
                    row_errors.append(ImportError(row=row_num, column='Tipo', value=integrator_type or '(vacío)',
                        error_type='invalid', message='Tipo de integrador no válido',
                        suggested_action=f'Use uno de: {", ".join(INTEGRATOR_TYPES)}'))
                
                if integration_modality not in INTEGRATION_MODALITIES:
                    row_errors.append(ImportError(row=row_num, column='Modalidad', value=integration_modality or '(vacío)',
                        error_type='invalid', message='Modalidad de integración no válida',
                        suggested_action=f'Use una de: {", ".join(INTEGRATION_MODALITIES)}'))
                
                if integration_type and integration_type not in valid_integration_types:
                    row_errors.append(ImportError(row=row_num, column='Tipo Integración',
                        value=integration_type, error_type='invalid',
                        message=f'Tipo de integración "{integration_type}" no válido',
                        suggested_action=f'Use uno de: {", ".join(valid_integration_types)}'))
                
                if gestor and gestor.lower() not in user_names:
                    row_errors.append(ImportError(row=row_num, column='Gestor', value=gestor,
                        error_type='invalid',
                        message=f'El gestor "{gestor}" no existe en la base de datos de usuarios',
                        suggested_action='Verifique el nombre o email del gestor'))
                
                if integrator_status not in INTEGRATOR_STATUSES:
                    integrator_status = "En proceso"
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Composite key for upsert: name + integration_type
                composite_query = {"name": name}
                if integration_type:
                    composite_query["integration_type"] = integration_type
                else:
                    composite_query["$or"] = [{"integration_type": None}, {"integration_type": ""}, {"integration_type": {"$exists": False}}]
                
                existing = await db.integrators.find_one(composite_query, {"_id": 0})
                
                if existing:
                    # UPDATE existing record, preserve certifications
                    update_data = {
                        "integrator_type": integrator_type,
                        "app_name": app_name,
                        "integration_modality": integration_modality,
                        "integrator_status": integrator_status,
                    }
                    if integration_type:
                        update_data["integration_type"] = integration_type
                    if gestor:
                        update_data["gestor"] = gestor
                    if categoria:
                        update_data["categoria"] = categoria
                    
                    await db.integrators.update_one(
                        {"integrator_id": existing["integrator_id"]},
                        {"$set": update_data}
                    )
                    updated_count += 1
                else:
                    # CREATE new integrator with default certifications
                    new_integrator = Integrator(
                        name=name,
                        integrator_type=integrator_type,
                        integration_type=integration_type or None,
                        app_name=app_name,
                        integration_modality=integration_modality,
                        integrator_status=integrator_status,
                        gestor=gestor or None,
                        categoria=categoria or None,
                        certifications=dict(default_certs)
                    )
                    doc = new_integrator.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.integrators.insert_one(doc)
                    success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='General', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos en esta fila'))
                skipped_count += 1
        
        # Determine status
        total_ok = success_count + updated_count
        if total_ok == total_rows:
            result_status = 'success'
            parts = []
            if success_count > 0:
                parts.append(f'{success_count} creados')
            if updated_count > 0:
                parts.append(f'{updated_count} actualizados')
            message = f'Importación exitosa: {", ".join(parts)}'
        elif total_ok > 0:
            result_status = 'partial'
            parts = []
            if success_count > 0:
                parts.append(f'{success_count} creados')
            if updated_count > 0:
                parts.append(f'{updated_count} actualizados')
            message = f'Importación parcial: {", ".join(parts)}, {skipped_count} con errores'
        else:
            result_status = 'error'
            message = f'Importación fallida: {skipped_count} registros con errores'
        
        return ImportResult(
            status=result_status,
            total_processed=total_rows,
            success_count=success_count,
            updated_count=updated_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors[:50],
            message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté dañado y tenga el formato correcto')],
            message='Error crítico: No se pudo procesar el archivo'
        )

