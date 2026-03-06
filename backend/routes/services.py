"""Route module: services.py"""
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
import httpx

router = APIRouter()

# ==================== SERVICES ENDPOINTS ====================

@router.post("/services", response_model=Service)
async def create_service(service_data: ServiceCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    service = Service(**service_data.model_dump())
    doc = service.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.services.insert_one(doc)
    return service

@router.get("/services", response_model=List[Service])
async def get_services(
    authorization: Optional[str] = Header(None),
    compatibility: Optional[str] = None,
    application_type: Optional[str] = None
):
    await get_current_user(authorization)
    
    query = {}
    if compatibility:
        compatibility_lower = compatibility.lower()
        if compatibility_lower == 'vpos':
            query['vpos_enabled'] = True
        elif compatibility_lower == 'gateway':
            query['gateway_enabled'] = True
        elif compatibility_lower == 'mpos':
            query['mpos_enabled'] = True
        elif compatibility_lower == 'link':
            query['link_enabled'] = True
    
    # Filtrar por tipo de aplicación (setup, recurring, both)
    if application_type:
        if application_type == 'recurring_available':
            # Servicios que pueden ser recurrentes (recurring o both)
            query['application_type'] = {'$in': ['recurring', 'both']}
        else:
            query['application_type'] = application_type
    
    services = await db.services.find(query, {"_id": 0}).to_list(1000)
    for srv in services:
        if isinstance(srv['created_at'], str):
            srv['created_at'] = datetime.fromisoformat(srv['created_at'])
    return services

@router.put("/services/{service_id}", response_model=Service)
async def update_service(service_id: str, service_data: ServiceCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.services.update_one(
        {"service_id": service_id},
        {"$set": service_data.model_dump()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    service = await db.services.find_one({"service_id": service_id}, {"_id": 0})
    if isinstance(service['created_at'], str):
        service['created_at'] = datetime.fromisoformat(service['created_at'])
    return service

@router.delete("/services/{service_id}")
async def delete_service(service_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este servicio
    quotes_with_service = await db.quotes.count_documents({
        "services.item_id": service_id
    })
    if quotes_with_service > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el medio de pago porque está asociado a {quotes_with_service} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    # Verificar si está vinculado a algún banco
    banks_with_service = await db.banks.count_documents({
        "products.service_id": service_id
    })
    if banks_with_service > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el medio de pago porque está configurado en {banks_with_service} banco(s). Elimine primero la asociación con los bancos."
        )
    
    result = await db.services.delete_one({"service_id": service_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Medio de pago eliminado exitosamente"}

@router.post("/services/import", response_model=ImportResult)
async def import_services(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
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
            'nombre': 'name', 'categoría': 'category', 'categoria': 'category',
            'descripción': 'description', 'descripcion': 'description',
            'setup_convencional': 'setup_cost_conventional',
            'mensual_convencional': 'monthly_cost_conventional',
            'setup_outsourcing': 'setup_cost_outsourcing',
            'mensual_outsourcing': 'monthly_cost_outsourcing'
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
        
        # Procesar cada fila
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
                category = str(row.get('category', 'General')).strip() if pd.notna(row.get('category')) else 'General'
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del servicio es obligatorio',
                        suggested_action='Ingrese un nombre válido'))
                
                # Parsear costos con validación
                def parse_cost(value, field_name):
                    if pd.isna(value) or value == '':
                        return 0.0
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        row_errors.append(ImportError(row=row_num, column=field_name, value=str(value),
                            error_type='format', message='Valor numérico inválido',
                            suggested_action='Ingrese un número válido (ej: 100.50)'))
                        return 0.0
                
                setup_conv = parse_cost(row.get('setup_cost_conventional'), 'Setup Convencional')
                monthly_conv = parse_cost(row.get('monthly_cost_conventional'), 'Mensual Convencional')
                setup_outs = parse_cost(row.get('setup_cost_outsourcing'), 'Setup Outsourcing')
                monthly_outs = parse_cost(row.get('monthly_cost_outsourcing'), 'Mensual Outsourcing')
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados
                existing = await db.services.find_one({"name": name})
                if existing:
                    errors.append(ImportError(row=row_num, column='Nombre', value=name,
                        error_type='duplicate', message='Ya existe un servicio con este nombre',
                        suggested_action='Verifique si desea actualizar el registro existente'))
                    skipped_count += 1
                    continue
                
                # Crear servicio
                service = Service(
                    category=category, name=name, description=description,
                    setup_cost_conventional=setup_conv, monthly_cost_conventional=monthly_conv,
                    setup_cost_outsourcing=setup_outs, monthly_cost_outsourcing=monthly_outs
                )
                doc = service.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.services.insert_one(doc)
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
            message = f'Importación exitosa: {success_count} servicios importados correctamente.'
        
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

@router.get("/services/export/pdf")
async def export_services_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    services = await db.services.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Catálogo de Servicios - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Servicio', 'Setup Conv.', 'Mensual Conv.', 'Setup Out.', 'Mensual Out.']]
    for s in services:
        data.append([
            s['name'][:40],
            f"${s.get('setup_cost_conventional', 0):.2f}",
            f"${s.get('monthly_cost_conventional', 0):.2f}",
            f"${s.get('setup_cost_outsourcing', 0):.2f}",
            f"${s.get('monthly_cost_outsourcing', 0):.2f}"
        ])
    
    table = Table(data, colWidths=[2.5*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
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
        headers={"Content-Disposition": "attachment; filename=servicios.pdf"}
    )

# ==================== EXCHANGE RATE ENDPOINTS ====================

@router.get("/exchange-rate/current")
async def get_current_exchange_rate(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    latest_rate = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
    
    if latest_rate:
        if isinstance(latest_rate['date'], str):
            latest_rate['date'] = datetime.fromisoformat(latest_rate['date'])
        
        rate_age = datetime.now(timezone.utc) - latest_rate['date'].replace(tzinfo=timezone.utc)
        if rate_age.total_seconds() < 86400:
            return latest_rate
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get("https://pydolarve.org/api/v1/dollar?page=bcv")
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                bcv_rate = float(data[0].get("price", 0))
                
                new_rate = {
                    "rate": bcv_rate,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source": "BCV"
                }
                
                await db.exchange_rates.insert_one(new_rate)
                
                new_rate['date'] = datetime.fromisoformat(new_rate['date'])
                return new_rate
    except Exception as e:
        if latest_rate:
            return latest_rate
        raise HTTPException(status_code=503, detail=f"Unable to fetch exchange rate: {str(e)}")

@router.post("/exchange-rate/update")
async def update_exchange_rate(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get("https://pydolarve.org/api/v1/dollar?page=bcv")
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                bcv_rate = float(data[0].get("price", 0))
                
                new_rate = {
                    "rate": bcv_rate,
                    "date": datetime.now(timezone.utc).isoformat(),
                    "source": "BCV"
                }
                
                await db.exchange_rates.insert_one(new_rate)
                new_rate['date'] = datetime.fromisoformat(new_rate['date'])
                
                return new_rate
            else:
                raise HTTPException(status_code=503, detail="No data received from BCV API")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch exchange rate: {str(e)}")

