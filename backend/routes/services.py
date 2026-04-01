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
            'tipo_corp': 'tipo_corp', 'tipo corp': 'tipo_corp',
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
                tipo_corp = str(row.get('tipo_corp', '')).strip() if pd.notna(row.get('tipo_corp')) else ''
                
                row_errors = []
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre', value='(vacío)',
                        error_type='missing', message='El nombre del servicio es obligatorio',
                        suggested_action='Ingrese un nombre válido'))

                valid_tipo_corp = ["Derecho de Uso", "Apoyo Técnico", "Soporte y Monitoreo"]
                if tipo_corp and tipo_corp not in valid_tipo_corp:
                    row_errors.append(ImportError(row=row_num, column='Tipo Corp', value=tipo_corp,
                        error_type='format', message=f'Valor inválido. Permitidos: {", ".join(valid_tipo_corp)}',
                        suggested_action='Use uno de los valores permitidos'))
                
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
                    tipo_corp=tipo_corp,
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
    
    data = [['Servicio', 'Tipo Corp', 'Setup Conv.', 'Mensual Conv.', 'Setup Out.', 'Mensual Out.']]
    for s in services:
        data.append([
            s['name'][:40],
            s.get('tipo_corp', '')[:20],
            f"${s.get('setup_cost_conventional', 0):.2f}",
            f"${s.get('monthly_cost_conventional', 0):.2f}",
            f"${s.get('setup_cost_outsourcing', 0):.2f}",
            f"${s.get('monthly_cost_outsourcing', 0):.2f}"
        ])
    
    table = Table(data, colWidths=[2.0*inch, 1.2*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
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
        return latest_rate
    
    return {"rate": 0, "source": "Sin datos", "date": datetime.now(timezone.utc).isoformat()}

@router.post("/exchange-rate/update")
async def update_exchange_rate(authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    
    rate_value = None
    source_name = ""
    
    # Fuente 1: exchangedyn (datos directos del BCV)
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get("https://api.exchangedyn.com/markets/quotes/usdves/bcv")
            response.raise_for_status()
            data = response.json()
            bcv_src = data.get("sources", {}).get("BCV", {})
            rate_value = float(bcv_src["quote"])
            source_name = "BCV Oficial (exchangedyn)"
    except Exception as e:
        logging.warning(f"exchangedyn falló: {e}")
    
    # Fuente 2: dolarapi.com (fallback)
    if not rate_value:
        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                response = await http_client.get("https://ve.dolarapi.com/v1/dolares/oficial")
                response.raise_for_status()
                data = response.json()
                rate_value = float(data.get("promedio") or data.get("venta") or data.get("compra") or 0)
                source_name = "BCV Oficial (dolarapi)"
        except Exception as e:
            logging.warning(f"dolarapi falló: {e}")
    
    if not rate_value:
        raise HTTPException(status_code=502, detail="No se pudo obtener la tasa de ninguna fuente BCV")
    
    now = datetime.now(timezone.utc)
    date_str = now.strftime('%Y-%m-%d')
    new_rate = {
        "rate": rate_value,
        "source": source_name,
        "date": now.isoformat(),
        "updated_by": current_user.get("email", "system"),
        "active": True,
    }
    
    await db.exchange_rates.update_many({"active": True}, {"$set": {"active": False}})
    await db.exchange_rates.insert_one(new_rate)
    new_rate.pop("_id", None)

    # Guardar en histórico automáticamente
    existing_hist = await db.historico_tasas_cambio.find_one({"fecha": date_str})
    if not existing_hist:
        await db.historico_tasas_cambio.insert_one({
            "fecha": date_str,
            "valor_tasa": rate_value,
            "moneda": "USD/BS",
            "fuente": source_name,
            "usuario_registro": current_user.get("email", "system"),
            "created_at": now.isoformat()
        })
    else:
        await db.historico_tasas_cambio.update_one(
            {"fecha": date_str},
            {"$set": {"valor_tasa": rate_value, "fuente": source_name, "usuario_registro": current_user.get("email", "system"), "updated_at": now.isoformat()}}
        )
    
    return new_rate


# ==================== HISTÓRICO DE TASAS DE CAMBIO ====================

@router.get("/exchange-rate/history")
async def get_exchange_rate_history(authorization: Optional[str] = Header(None)):
    """Obtiene el historial completo de tasas de cambio, ordenado por fecha descendente."""
    await get_current_user(authorization)
    rates = await db.historico_tasas_cambio.find({}, {"_id": 0}).sort("fecha", -1).to_list(365)
    return rates


@router.get("/exchange-rate/by-date/{fecha}")
async def get_exchange_rate_by_date(fecha: str, authorization: Optional[str] = Header(None)):
    """Obtiene la tasa de cambio para una fecha específica (formato YYYY-MM-DD)."""
    await get_current_user(authorization)
    
    rate = await db.historico_tasas_cambio.find_one({"fecha": fecha}, {"_id": 0})
    if rate:
        return {"found": True, **rate}
    
    return {"found": False, "fecha": fecha, "message": "No hay tasa registrada para esta fecha"}


@router.post("/exchange-rate/manual")
async def set_manual_exchange_rate(body: dict, authorization: Optional[str] = Header(None)):
    """Registra manualmente una tasa de cambio para una fecha específica."""
    current_user = await get_current_user(authorization)
    
    fecha = body.get("fecha")
    valor_tasa = body.get("valor_tasa")
    
    if not fecha or not valor_tasa:
        raise HTTPException(status_code=400, detail="Se requiere 'fecha' (YYYY-MM-DD) y 'valor_tasa'")
    
    try:
        valor_tasa = float(valor_tasa)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="'valor_tasa' debe ser un número válido")
    
    if valor_tasa <= 0:
        raise HTTPException(status_code=400, detail="La tasa debe ser mayor a 0")
    
    now = datetime.now(timezone.utc)
    
    existing = await db.historico_tasas_cambio.find_one({"fecha": fecha})
    if existing:
        await db.historico_tasas_cambio.update_one(
            {"fecha": fecha},
            {"$set": {
                "valor_tasa": valor_tasa,
                "fuente": "Manual",
                "usuario_registro": current_user.get("email", "system"),
                "updated_at": now.isoformat()
            }}
        )
    else:
        await db.historico_tasas_cambio.insert_one({
            "fecha": fecha,
            "valor_tasa": valor_tasa,
            "moneda": "USD/BS",
            "fuente": "Manual",
            "usuario_registro": current_user.get("email", "system"),
            "created_at": now.isoformat()
        })

    # También actualizar la tasa activa si es la fecha de hoy
    today_str = now.strftime('%Y-%m-%d')
    if fecha == today_str:
        await db.exchange_rates.update_many({"active": True}, {"$set": {"active": False}})
        new_active = {
            "rate": valor_tasa,
            "source": "Manual",
            "date": now.isoformat(),
            "updated_by": current_user.get("email", "system"),
            "active": True,
        }
        await db.exchange_rates.insert_one(new_active)
    
    return {"message": f"Tasa de {valor_tasa:.2f} registrada para {fecha}", "fecha": fecha, "valor_tasa": valor_tasa, "fuente": "Manual"}

