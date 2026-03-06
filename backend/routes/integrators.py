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
    doc['created_at'] = doc['created_at'].isoformat()
    await db.integrators.insert_one(doc)
    return new_integrator

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

# Import integrators from Excel/CSV with detailed validation
@router.post("/integrators/import", response_model=ImportResult)
async def import_integrators(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    # Determine file format
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error',
            total_processed=0,
            success_count=0,
            error_count=1,
            skipped_count=0,
            errors=[ImportError(
                row=0,
                column='archivo',
                value=file.filename,
                error_type='format',
                message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv'
            )],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        # Read file
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error',
                total_processed=0,
                success_count=0,
                error_count=1,
                skipped_count=0,
                errors=[ImportError(
                    row=0,
                    column='archivo',
                    value=file.filename,
                    error_type='format',
                    message='El archivo está vacío',
                    suggested_action='Agregue registros al archivo antes de importar'
                )],
                message='Error: El archivo no contiene datos'
            )
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        # Map common column names
        column_mapping = {
            'nombre': 'name',
            'nombre_del_integrador': 'name',
            'tipo': 'integrator_type',
            'tipo_de_integrador': 'integrator_type',
            'aplicativo': 'app_name',
            'nombre_del_aplicativo': 'app_name',
            'modalidad': 'integration_modality',
            'modalidad_de_integración': 'integration_modality',
            'modalidad_de_integracion': 'integration_modality',
            'estatus': 'integrator_status',
            'estado': 'integrator_status'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Required columns check
        required_columns = ['name', 'integrator_type', 'app_name', 'integration_modality']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error',
                total_processed=0,
                success_count=0,
                error_count=1,
                skipped_count=0,
                errors=[ImportError(
                    row=0,
                    column=', '.join(missing_columns),
                    value=None,
                    error_type='missing',
                    message=f'Columnas requeridas no encontradas: {", ".join(missing_columns)}',
                    suggested_action='Asegúrese de que el archivo tenga las columnas: Nombre, Tipo, Aplicativo, Modalidad'
                )],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (header is row 1)
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                integrator_type = str(row.get('integrator_type', '')).strip() if pd.notna(row.get('integrator_type')) else ''
                app_name = str(row.get('app_name', '')).strip() if pd.notna(row.get('app_name')) else ''
                integration_modality = str(row.get('integration_modality', '')).strip() if pd.notna(row.get('integration_modality')) else ''
                integrator_status = str(row.get('integrator_status', 'En proceso')).strip() if pd.notna(row.get('integrator_status')) else 'En proceso'
                
                row_errors = []
                
                # Validate required fields
                if not name:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Nombre',
                        value='(vacío)',
                        error_type='missing',
                        message='El nombre del integrador es obligatorio',
                        suggested_action='Ingrese un nombre válido para el integrador'
                    ))
                
                if not app_name:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Aplicativo',
                        value='(vacío)',
                        error_type='missing',
                        message='El nombre del aplicativo es obligatorio',
                        suggested_action='Ingrese el nombre del aplicativo'
                    ))
                
                # Validate integrator_type
                if integrator_type not in INTEGRATOR_TYPES:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Tipo',
                        value=integrator_type or '(vacío)',
                        error_type='invalid',
                        message='Tipo de integrador no válido',
                        suggested_action=f'Use uno de: {", ".join(INTEGRATOR_TYPES)}'
                    ))
                
                # Validate integration_modality
                if integration_modality not in INTEGRATION_MODALITIES:
                    row_errors.append(ImportError(
                        row=row_num,
                        column='Modalidad',
                        value=integration_modality or '(vacío)',
                        error_type='invalid',
                        message='Modalidad de integración no válida',
                        suggested_action=f'Use una de: {", ".join(INTEGRATION_MODALITIES)}'
                    ))
                
                # Validate status (non-blocking, use default)
                if integrator_status not in INTEGRATOR_STATUSES:
                    integrator_status = "En proceso"
                
                # If there are errors, skip this row
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Check for duplicates
                existing = await db.integrators.find_one({
                    "name": name,
                    "app_name": app_name
                })
                
                if existing:
                    errors.append(ImportError(
                        row=row_num,
                        column='Nombre/Aplicativo',
                        value=f'{name} / {app_name}',
                        error_type='duplicate',
                        message='Ya existe un integrador con este nombre y aplicativo',
                        suggested_action='Verifique si desea actualizar el registro existente'
                    ))
                    skipped_count += 1
                    continue
                
                # Create integrator
                new_integrator = Integrator(
                    name=name,
                    integrator_type=integrator_type,
                    app_name=app_name,
                    integration_modality=integration_modality,
                    integrator_status=integrator_status
                )
                
                doc = new_integrator.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.integrators.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(
                    row=row_num,
                    column='General',
                    value=None,
                    error_type='format',
                    message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos en esta fila'
                ))
                skipped_count += 1
        
        # Determine status
        if success_count == total_rows:
            result_status = 'success'
            message = f'Importación exitosa: {success_count} registros procesados correctamente'
        elif success_count > 0:
            result_status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} con errores'
        else:
            result_status = 'error'
            message = f'Importación fallida: {skipped_count} registros con errores'
        
        return ImportResult(
            status=result_status,
            total_processed=total_rows,
            success_count=success_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors[:50],  # Limit to first 50 errors
            message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error',
            total_processed=0,
            success_count=0,
            error_count=1,
            skipped_count=0,
            errors=[ImportError(
                row=0,
                column='archivo',
                value=file.filename,
                error_type='format',
                message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté dañado y tenga el formato correcto'
            )],
            message='Error crítico: No se pudo procesar el archivo'
        )

