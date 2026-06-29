"""Route module: hardware.py"""
# ruff: noqa: F403, F405
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

# ==================== COMPONENT TYPES ENDPOINTS ====================

@router.post("/component-types", response_model=ComponentType)
async def create_component_type(component_data: ComponentTypeCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    component = ComponentType(**component_data.model_dump())
    doc = component.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.component_types.insert_one(doc)
    return component

@router.get("/component-types", response_model=List[ComponentType])
async def get_component_types(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    components = await db.component_types.find({}, {"_id": 0}).to_list(1000)
    for comp in components:
        if isinstance(comp['created_at'], str):
            comp['created_at'] = datetime.fromisoformat(comp['created_at'])
    return components

@router.delete("/component-types/{component_id}")
async def delete_component_type(component_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.component_types.delete_one({"component_id": component_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Component type not found")
    return {"message": "Component type deleted successfully"}

# ==================== HARDWARE ENDPOINTS ====================

@router.post("/hardware", response_model=Hardware)
async def create_hardware(hardware_data: HardwareCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    hardware = Hardware(**hardware_data.model_dump())
    doc = hardware.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.hardware.insert_one(doc)
    return hardware

@router.get("/hardware", response_model=List[Hardware])
async def get_hardware(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    for hw in hardware_list:
        if isinstance(hw['created_at'], str):
            hw['created_at'] = datetime.fromisoformat(hw['created_at'])
    return hardware_list

@router.put("/hardware/{hardware_id}", response_model=Hardware)
async def update_hardware(hardware_id: str, hardware_data: HardwareCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.hardware.update_one(
        {"hardware_id": hardware_id},
        {"$set": hardware_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Hardware not found")
    hardware = await db.hardware.find_one({"hardware_id": hardware_id}, {"_id": 0})
    if isinstance(hardware['created_at'], str):
        hardware['created_at'] = datetime.fromisoformat(hardware['created_at'])
    return hardware

@router.delete("/hardware/{hardware_id}")
async def delete_hardware(hardware_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este dispositivo
    quotes_with_hardware = await db.quotes.count_documents({
        "$or": [
            {"pinpad_id": hardware_id},
            {"hardware.hardware_id": hardware_id}
        ]
    })
    if quotes_with_hardware > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el dispositivo porque está asociado a {quotes_with_hardware} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.hardware.delete_one({"hardware_id": hardware_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Hardware not found")
    return {"message": "Dispositivo eliminado exitosamente"}

# ==================== HARDWARE IMPORT/EXPORT ====================

@router.post("/hardware/import", response_model=ImportResult)
async def import_hardware(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Importar bienes y servicios desde archivo Excel/CSV"""
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
            'nombre': 'name', 'tipo': 'type', 'categoría': 'category', 'categoria': 'category',
            'precio_usd': 'price_usd', 'precio_efectivo': 'price_usd',
            'precio_bs_usd': 'price_bs_usd', 'precio_transferencia': 'price_bs_usd',
            'descripción': 'description', 'descripcion': 'description'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Verificar columna requerida
        if 'name' not in df.columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='name', value=None, error_type='missing',
                    message='Columna "Nombre" no encontrada',
                    suggested_action='Asegúrese de que el archivo tenga la columna: Nombre')],
                message='Error: Falta columna requerida (Nombre)'
            )
        
        # Tipos válidos
        valid_types = ['Pinpad', 'POS', 'Cable', 'Base', 'Accesorio', 'Mantenimiento', 'Licencia', 'Consultoria', 'Componente', 'Pieza']
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                hw_type = str(row.get('type', 'Accesorio')).strip() if pd.notna(row.get('type')) else 'Accesorio'
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Validar tipo (usar default si no es válido)
                if hw_type not in valid_types:
                    hw_type = 'Accesorio'
                
                # Parsear precios
                try:
                    price_usd = float(row.get('price_usd', 0)) if pd.notna(row.get('price_usd')) else 0.0
                except (ValueError, TypeError):
                    price_usd = 0.0
                
                try:
                    price_bs_usd = float(row.get('price_bs_usd', 0)) if pd.notna(row.get('price_bs_usd')) else 0.0
                except (ValueError, TypeError):
                    price_bs_usd = 0.0
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.hardware.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un registro con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear hardware
                hardware = Hardware(
                    name=name, 
                    type=hw_type, 
                    price_usd=price_usd, 
                    price_bs_usd=price_bs_usd,
                    description=description
                )
                doc = hardware.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.hardware.insert_one(doc)
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
            message = f'Importación exitosa: {success_count} registros importados correctamente.'
        
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

@router.get("/hardware/export/excel")
async def export_hardware_excel(authorization: Optional[str] = Header(None)):
    """Exportar bienes y servicios a Excel"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    
    # Crear DataFrame
    data = []
    for h in hardware_list:
        data.append({
            'Nombre': h.get('name', ''),
            'Tipo': h.get('type', ''),
            'Precio Efectivo (USD)': h.get('price_usd', 0),
            'Precio Bs/USD': h.get('price_bs_usd', 0),
            'Descripción': h.get('description', '')
        })
    
    df = pd.DataFrame(data)
    
    # Crear archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Bienes y Servicios')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=bienes_servicios.xlsx"}
    )

@router.get("/hardware/export/pdf")
async def export_hardware_pdf(authorization: Optional[str] = Header(None)):
    """Exportar bienes y servicios a PDF"""
    await get_current_user(authorization)

    from services.pdf_report import build_corporate_pdf

    hardware_list = await db.hardware.find({}, {"_id": 0}).to_list(1000)
    hardware_list.sort(key=lambda h: (h.get("name") or "").strip().casefold())

    headers = ['Nombre', 'Tipo', 'Precio USD', 'Precio Bs/USD', 'Descripción']
    rows = []
    for h in hardware_list:
        rows.append([
            h.get('name', ''),
            h.get('type', ''),
            f"${h.get('price_usd', 0):.2f}",
            f"${h.get('price_bs_usd', 0):.2f}",
            h.get('description', '') or '',
        ])

    buffer = build_corporate_pdf(
        title="Bienes y Servicios",
        headers=headers, rows=rows,
        col_ratios=[2.4, 1.2, 1, 1, 3.4],
    )
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=bienes_servicios.pdf"}
    )

@router.get("/hardware/template")
async def get_hardware_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación para bienes y servicios"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    # Crear plantilla con datos de ejemplo
    data = {
        'Nombre': ['Pinpad V240m', 'Cable USB', 'Servicio Mantenimiento'],
        'Tipo': ['Pinpad', 'Cable', 'Mantenimiento'],
        'Precio Efectivo (USD)': [150.00, 5.00, 50.00],
        'Precio Bs/USD': [165.00, 5.50, 55.00],
        'Descripción': ['Terminal de pago Verifone', 'Cable USB tipo A-B', 'Mantenimiento preventivo mensual']
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        # Añadir hoja con tipos válidos
        tipos_data = {
            'Tipos Válidos': ['Pinpad', 'POS', 'Cable', 'Base', 'Accesorio', 'Mantenimiento', 'Licencia', 'Consultoria', 'Componente', 'Pieza'],
            'Descripción': [
                'Dispositivos Pinpad',
                'Terminales POS',
                'Cables de conexión',
                'Bases y soportes',
                'Accesorios varios',
                'Servicios de mantenimiento',
                'Licencias de software',
                'Servicios de consultoría',
                'Componentes electrónicos',
                'Piezas mecánicas'
            ]
        }
        pd.DataFrame(tipos_data).to_excel(writer, index=False, sheet_name='Tipos Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_bienes_servicios.xlsx"}
    )

