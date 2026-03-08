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

@router.patch("/integrators/{integrator_id}/contact-date")
async def update_contact_date(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar solo la fecha de último contacto (inline edit)"""
    await get_current_user(authorization)
    date_val = body.get("last_contact_date")
    if date_val:
        from datetime import date as date_type
        try:
            parsed = datetime.strptime(date_val, "%Y-%m-%d").date()
            if parsed > date_type.today():
                raise HTTPException(status_code=400, detail="La fecha no puede ser futura")
            date_val = parsed.isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (use YYYY-MM-DD)")
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {"last_contact_date": date_val}}
    )
    return {"status": "ok", "last_contact_date": date_val}

# Export integrators to Excel (with certification matrix)
@router.get("/integrators/export/excel")
async def export_integrators_excel(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(5000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    import pandas as pd
    
    # Fetch products for cert columns
    cert_products = await db.services.find(
        {"service_type": "Producto", "application_type": {"$in": ["setup", "both"]}},
        {"_id": 0, "service_id": 1, "name": 1}
    ).sort("name", 1).to_list(1000)
    
    rows = []
    for intg in integrators:
        row = {
            'Nombre': intg.get('name', ''),
            'Tipo': intg.get('integrator_type', ''),
            'Aplicativo': intg.get('app_name', ''),
            'Modalidad': intg.get('integration_modality', ''),
            'Estatus': intg.get('integrator_status', ''),
            'Tipo Integración': intg.get('integration_type', ''),
            'Gestor': intg.get('gestor', ''),
            'Categoría': intg.get('categoria', ''),
            'Último Contacto': intg.get('last_contact_date', ''),
        }
        certs = intg.get('certifications') or {}
        for prod in cert_products:
            row[prod['name']] = certs.get(prod['service_id'], 'N/A')
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
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

# Import template for integrators (dynamic product columns)
@router.get("/integrators/import/template")
async def get_integrators_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación con columnas dinámicas de productos"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    # Fetch all cert products for dynamic columns
    cert_products = await db.services.find(
        {"service_type": "Producto", "application_type": {"$in": ["setup", "both"]}},
        {"_id": 0, "service_id": 1, "name": 1}
    ).sort("name", 1).to_list(1000)
    
    # Base data with 3 example rows
    data = {
        'Nombre': ['TechPay Solutions', 'ComercioApp', 'GatewayVe'],
        'Tipo': ['Integrador', 'Comercio', 'Integrador'],
        'Aplicativo': ['PaymentHub v3', 'MiTienda App', 'GW-Connect'],
        'Modalidad': ['PG Universal', 'MPOS', 'REST'],
        'Estatus': ['En proceso', 'Certificado', 'En proceso'],
        'Tipo Integración': ['PG', 'MP', 'CR'],
        'Gestor': ['', '', ''],
        'Categoría': ['Cliente/Integrador nuevo PG', '', 'Cliente/Integrador actual de VPOS'],
        'Último Contacto': ['15/01/2026', '28/02/2026', '']
    }
    
    # Add dynamic product columns with sample cert values
    sample_vals = ['C', 'P', 'N/A']
    for i, prod in enumerate(cert_products):
        data[prod['name']] = [sample_vals[i % 3], sample_vals[(i + 1) % 3], sample_vals[(i + 2) % 3]]
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        # Instructions sheet - base fields + product columns info
        base_fields = [
            {'Campo': 'Nombre *', 'Descripción': 'Nombre del integrador (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'TechPay Solutions'},
            {'Campo': 'Tipo *', 'Descripción': 'Integrador o Comercio (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'Integrador'},
            {'Campo': 'Aplicativo *', 'Descripción': 'Nombre del aplicativo (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'PaymentHub v3'},
            {'Campo': 'Modalidad *', 'Descripción': 'Modalidad de integración (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'PG Universal'},
            {'Campo': 'Estatus', 'Descripción': 'Estado actual (def: En proceso)', 'Obligatorio': 'No', 'Ejemplo': 'En proceso'},
            {'Campo': 'Tipo Integración', 'Descripción': 'CR, LP, PG, MP, TK', 'Obligatorio': 'No', 'Ejemplo': 'PG'},
            {'Campo': 'Gestor', 'Descripción': 'Nombre del gestor (debe existir en el sistema)', 'Obligatorio': 'No', 'Ejemplo': 'Juan Pérez'},
            {'Campo': 'Categoría', 'Descripción': 'Categoría del integrador', 'Obligatorio': 'No', 'Ejemplo': 'Cliente/Integrador nuevo PG'},
            {'Campo': 'Último Contacto', 'Descripción': 'Fecha del último contacto (DD/MM/AAAA). No puede ser futura.', 'Obligatorio': 'No', 'Ejemplo': '15/01/2026'},
            {'Campo': '--- COLUMNAS DE PRODUCTOS ---', 'Descripción': 'Las siguientes columnas corresponden a la Matriz de Certificación', 'Obligatorio': '---', 'Ejemplo': '---'},
        ]
        for prod in cert_products:
            base_fields.append({
                'Campo': prod['name'],
                'Descripción': f'Estado de certificación para {prod["name"]}. Valores: C, P, N/A',
                'Obligatorio': 'No',
                'Ejemplo': 'C / P / N/A'
            })
        pd.DataFrame(base_fields).to_excel(writer, index=False, sheet_name='Instrucciones')
        
        # Valid values sheet — COMPLETE reference
        all_modalities = ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST',
                          'Stand Alone', 'TKN No Universal', 'TKN Universal',
                          'Web Link de Pago Modalidad No Universal', 'Web Link de Pago Modalidad Universal', 'Wrapper']
        all_categories = [
            'Cliente/Integrador actual de PG', 'Cliente/Integrador actual de VPOS',
            'Cliente/Integrador actual Tokenizador', 'Cliente/Integrador nuevo Link de Pago',
            'Cliente/Integrador nuevo Mpos', 'Cliente/Integrador nuevo PG',
            'Cliente/Integrador nuevo VPOS', 'Cliente/Integrador MobilePOS'
        ]
        max_len = max(len(all_modalities), len(all_categories), len(cert_products), 12)
        pad = lambda lst: lst + [''] * (max_len - len(lst))
        values_data = {
            'Tipos de Integrador (Col B)': pad(['Integrador', 'Comercio']),
            'Modalidades (Col D)': pad(all_modalities),
            'Tipos de Integración (Col F)': pad(['CR — Caja Registradora', 'LP — Link de Pago',
                'PG — Payment Gateway', 'MP — Android (Mobile POS)', 'TK — Tokenizador']),
            'Estatus (Col E)': pad(['Certificado', 'En proceso', 'Suspendido']),
            'Categorías (Col H)': pad(all_categories),
            'Valores de Certificación': pad(['C — Certificado', 'P — Pendiente', 'N/A — No Aplica',
                '(vacío) — Se asigna N/A automáticamente', 'Se aceptan mayúsculas y minúsculas (c, p, n/a)']),
            'Formato de Fechas (Col I)': pad(['DD/MM/AAAA (ej: 15/01/2026)', 'AAAA-MM-DD (ej: 2026-01-15)',
                'DD-MM-AAAA (ej: 15-01-2026)', 'No se permiten fechas futuras']),
            'Reglas de Importación': pad([
                '1. La clave única es: Nombre + Tipo Integración',
                '2. Si un registro ya existe (misma clave), se ACTUALIZAN sus datos',
                '3. La Matriz de Certificación existente se preserva al actualizar',
                '4. Los campos marcados con * son OBLIGATORIOS',
                '5. Si no indica Estatus, se asigna "En proceso" por defecto',
                '6. El Gestor debe estar registrado en el sistema (Nombre completo o Email)',
                '7. Las columnas de productos (J en adelante) son opcionales',
                '8. Celdas vacías en productos se asignan como N/A',
                '9. Se aceptan archivos .xlsx, .xls y .csv (separador: coma, punto y coma o tab)',
                '10. Los valores deben coincidir EXACTAMENTE con los de esta hoja (respetar mayúsculas)',
            ])
        }
        pd.DataFrame(values_data).to_excel(writer, index=False, sheet_name='Valores Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_integradores.xlsx"}
    )

# Import integrators from Excel/CSV with Upsert logic, certification matrix, and detailed validation
@router.post("/integrators/import", response_model=ImportResult)
async def import_integrators(
    file: UploadFile = File(...),
    mode: str = Form("upsert"),
    authorization: Optional[str] = Header(None)
):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    updated_count = 0
    skipped_count = 0
    cert_updates_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            cert_updates_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        if file_ext == 'csv':
            # Auto-detect separator: try comma, semicolon, tab
            for sep in [',', ';', '\t']:
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='utf-8')
                    if len(df.columns) >= 4:
                        break
                except Exception:
                    continue
            else:
                # Fallback: try latin-1 encoding
                for sep in [',', ';', '\t']:
                    try:
                        df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='latin-1')
                        if len(df.columns) >= 4:
                            break
                    except Exception:
                        continue
                else:
                    df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                cert_updates_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename,
                    error_type='format', message='El archivo está vacío',
                    suggested_action='Agregue registros al archivo antes de importar')],
                message='Error: El archivo no contiene datos'
            )
        
        # Keep original column names for product matching before normalizing
        original_columns = list(df.columns.str.strip())
        df.columns = [c.strip() for c in df.columns]
        
        # Normalize base column names
        column_mapping = {
            'Nombre': 'name', 'nombre': 'name', 'nombre_del_integrador': 'name',
            'Tipo': 'integrator_type', 'tipo': 'integrator_type', 'tipo_de_integrador': 'integrator_type',
            'Tipo Integración': 'integration_type', 'tipo_integración': 'integration_type',
            'tipo_de_integración': 'integration_type', 'tipo_de_integracion': 'integration_type',
            'tipo_integracion': 'integration_type',
            'Aplicativo': 'app_name', 'aplicativo': 'app_name', 'nombre_del_aplicativo': 'app_name',
            'Modalidad': 'integration_modality', 'modalidad': 'integration_modality',
            'modalidad_de_integración': 'integration_modality', 'modalidad_de_integracion': 'integration_modality',
            'Estatus': 'integrator_status', 'estatus': 'integrator_status', 'estado': 'integrator_status',
            'Gestor': 'gestor', 'gestor_asignado': 'gestor',
            'Categoría': 'categoria', 'categoría': 'categoria', 'categoria': 'categoria',
            'Último Contacto': 'last_contact_date', 'último_contacto': 'last_contact_date',
            'ultimo_contacto': 'last_contact_date', 'Ultimo Contacto': 'last_contact_date'
        }
        
        # Pre-load users and products
        all_users = await db.users.find({"is_active": True}, {"_id": 0, "first_name": 1, "last_name": 1, "email": 1}).to_list(1000)
        user_names = set()
        for u in all_users:
            full = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            user_names.add(full.lower())
            user_names.add(u.get('email', '').lower())
        
        cert_products = await db.services.find(
            {"service_type": "Producto", "application_type": {"$in": ["setup", "both"]}},
            {"_id": 0, "service_id": 1, "name": 1}
        ).to_list(1000)
        default_certs = {p["service_id"]: "N/A" for p in cert_products}
        
        # Build product name -> service_id mapping (case-insensitive)
        product_name_to_id = {}
        for p in cert_products:
            product_name_to_id[p["name"].strip().lower()] = p["service_id"]
        
        # Identify which columns in the file are product columns
        base_column_names = set(column_mapping.keys())
        product_columns = {}  # original_col_name -> service_id
        for col in df.columns:
            col_stripped = col.strip()
            if col_stripped.lower() in [k.lower() for k in base_column_names]:
                continue
            # Check if this column matches a product name
            if col_stripped.lower() in product_name_to_id:
                product_columns[col] = product_name_to_id[col_stripped.lower()]
        
        # Rename base columns
        rename_map = {}
        for col in df.columns:
            if col in column_mapping:
                rename_map[col] = column_mapping[col]
        df.rename(columns=rename_map, inplace=True)
        
        required_columns = ['name', 'integrator_type', 'app_name', 'integration_modality']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                cert_updates_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None,
                    error_type='missing',
                    message=f'Columnas requeridas no encontradas: {", ".join(missing_columns)}',
                    suggested_action='Asegúrese de que el archivo tenga las columnas: Nombre, Tipo, Aplicativo, Modalidad')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        valid_integration_types = ['CR', 'LP', 'PG', 'MP', 'TK']
        valid_cert_values = {'c': 'C', 'p': 'P', 'n/a': 'N/A', 'na': 'N/A', '': 'N/A'}
        
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
                last_contact_raw = str(row.get('last_contact_date', '')).strip() if pd.notna(row.get('last_contact_date')) else ''
                
                row_errors = []
                
                # Parse last_contact_date
                last_contact_date = None
                if last_contact_raw:
                    from datetime import date as date_type
                    parsed_date = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
                        try:
                            parsed_date = datetime.strptime(last_contact_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                    if parsed_date is None:
                        row_errors.append(ImportError(row=row_num, column='Último Contacto (Col I)',
                            value=last_contact_raw, error_type='invalid',
                            message=f'Fila {row_num}, Columna I (Último Contacto): El formato "{last_contact_raw}" no es reconocido. Formatos aceptados: DD/MM/AAAA (ej: 15/01/2026) o AAAA-MM-DD (ej: 2026-01-15).',
                            suggested_action=f'Corrija la celda I{row_num}. Use formato de fecha estándar: 15/01/2026'))
                    elif parsed_date > date_type.today():
                        row_errors.append(ImportError(row=row_num, column='Último Contacto (Col I)',
                            value=last_contact_raw, error_type='invalid',
                            message=f'Fila {row_num}, Columna I (Último Contacto): La fecha {last_contact_raw} es posterior a hoy ({date_type.today().strftime("%d/%m/%Y")}). No se permiten fechas futuras.',
                            suggested_action=f'Corrija la celda I{row_num}. Ingrese una fecha igual o anterior a hoy'))
                    else:
                        last_contact_date = parsed_date.isoformat()
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre (Col A)', value='(vacío)',
                        error_type='missing', message=f'Fila {row_num}, Columna A (Nombre): El campo está vacío. Cada integrador debe tener un nombre único que lo identifique.',
                        suggested_action='Complete la celda A{0} con el nombre del integrador. Este campo es obligatorio (*).'.format(row_num)))
                
                if not app_name:
                    row_errors.append(ImportError(row=row_num, column='Aplicativo (Col C)', value='(vacío)',
                        error_type='missing', message=f'Fila {row_num}, Columna C (Aplicativo): El campo está vacío. Es obligatorio indicar el nombre del sistema o aplicación del integrador.',
                        suggested_action='Complete la celda C{0} con el nombre del aplicativo. Este campo es obligatorio (*).'.format(row_num)))
                
                if integrator_type not in INTEGRATOR_TYPES:
                    row_errors.append(ImportError(row=row_num, column='Tipo (Col B)', value=integrator_type or '(vacío)',
                        error_type='invalid', message=f'Fila {row_num}, Columna B (Tipo): Se recibió "{integrator_type or "(vacío)"}" pero solo se aceptan: {", ".join(INTEGRATOR_TYPES)}. El valor debe coincidir exactamente.',
                        suggested_action='Corrija la celda B{0}. Copie el valor exacto de la hoja "Valores Válidos", columna "Tipos de Integrador".'.format(row_num)))
                
                if integration_modality not in INTEGRATION_MODALITIES:
                    row_errors.append(ImportError(row=row_num, column='Modalidad (Col D)', value=integration_modality or '(vacío)',
                        error_type='invalid', message=f'Fila {row_num}, Columna D (Modalidad): Se recibió "{integration_modality or "(vacío)"}" pero no coincide con ninguna modalidad válida. Verifique mayúsculas y espacios.',
                        suggested_action='Corrija la celda D{0}. Consulte la hoja "Valores Válidos", columna "Modalidades" para ver las {1} opciones disponibles.'.format(row_num, len(INTEGRATION_MODALITIES))))
                
                if integration_type and integration_type not in valid_integration_types:
                    row_errors.append(ImportError(row=row_num, column='Tipo Integración (Col F)', value=integration_type,
                        error_type='invalid', message=f'Fila {row_num}, Columna F (Tipo Integración): Se recibió "{integration_type}" pero solo se aceptan: {", ".join(valid_integration_types)}.',
                        suggested_action='Corrija la celda F{0}. Use exactamente: {1}.'.format(row_num, ", ".join(valid_integration_types))))
                
                if gestor and gestor.lower() not in user_names:
                    row_errors.append(ImportError(row=row_num, column='Gestor (Col G)', value=gestor,
                        error_type='invalid', message=f'Fila {row_num}, Columna G (Gestor): El usuario "{gestor}" no está registrado en el sistema. No se puede asignar como gestor.',
                        suggested_action='Corrija la celda G{0}. El gestor debe ser un usuario activo del sistema (nombre completo o email). Verifique en el módulo de Usuarios.'.format(row_num)))
                
                if integrator_status not in INTEGRATOR_STATUSES:
                    integrator_status = "En proceso"
                
                # Parse certification columns
                row_certs = {}
                cert_has_errors = False
                for col_name, service_id in product_columns.items():
                    raw_val = str(row.get(col_name, '')).strip() if pd.notna(row.get(col_name)) else ''
                    normalized = valid_cert_values.get(raw_val.lower(), None)
                    if normalized is None:
                        col_letter = chr(ord('J') + list(product_columns.keys()).index(col_name)) if list(product_columns.keys()).index(col_name) < 16 else f'Col {10 + list(product_columns.keys()).index(col_name)}'
                        row_errors.append(ImportError(row=row_num, column=f'{col_name} ({col_letter})',
                            value=raw_val, error_type='invalid',
                            message=f'Fila {row_num}, {col_letter} ({col_name}): Se recibió "{raw_val}" pero solo se aceptan valores de certificación: C (Certificado), P (Pendiente) o N/A (No Aplica). Las celdas vacías se asignan como N/A.',
                            suggested_action=f'Corrija la celda en la fila {row_num}, columna "{col_name}". Use exactamente: C, P o N/A'))
                        cert_has_errors = True
                    else:
                        row_certs[service_id] = normalized
                
                if row_errors:
                    errors.extend(row_errors)
                    if cert_has_errors or not name or not app_name or integrator_type not in INTEGRATOR_TYPES or integration_modality not in INTEGRATION_MODALITIES:
                        skipped_count += 1
                        continue
                
                # Build full certifications: start with defaults, overlay with file data
                full_certs = dict(default_certs)
                for sid, val in row_certs.items():
                    full_certs[sid] = val
                
                # Composite key for upsert: name + integration_type
                composite_query = {"name": name}
                if integration_type:
                    composite_query["integration_type"] = integration_type
                else:
                    composite_query["$or"] = [{"integration_type": None}, {"integration_type": ""}, {"integration_type": {"$exists": False}}]
                
                existing = await db.integrators.find_one(composite_query, {"_id": 0})
                
                if existing and mode == "insert_only":
                    errors.append(ImportError(row=row_num, column='Nombre/Tipo Int.',
                        value=f'{name} / {integration_type or "N/A"}',
                        error_type='duplicate',
                        message='Ya existe un integrador con este nombre y tipo de integración',
                        suggested_action='Use el modo "Upsert" para actualizar registros existentes'))
                    skipped_count += 1
                elif existing:
                    # UPSERT: update basic data + overwrite certifications from file
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
                    if last_contact_date:
                        update_data["last_contact_date"] = last_contact_date
                    
                    # Merge certs: existing certs as base, overlay with file data
                    if product_columns:
                        existing_certs = existing.get("certifications", {})
                        merged_certs = {**existing_certs, **row_certs}
                        update_data["certifications"] = merged_certs
                        cert_updates_count += len(row_certs)
                    
                    await db.integrators.update_one(
                        {"integrator_id": existing["integrator_id"]},
                        {"$set": update_data}
                    )
                    updated_count += 1
                else:
                    # CREATE new integrator with full certifications
                    new_integrator = Integrator(
                        name=name,
                        integrator_type=integrator_type,
                        integration_type=integration_type or None,
                        app_name=app_name,
                        integration_modality=integration_modality,
                        integrator_status=integrator_status,
                        gestor=gestor or None,
                        categoria=categoria or None,
                        last_contact_date=last_contact_date,
                        certifications=full_certs
                    )
                    doc = new_integrator.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.integrators.insert_one(doc)
                    success_count += 1
                    cert_updates_count += len(full_certs)
                
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
            if cert_updates_count > 0:
                parts.append(f'{cert_updates_count} certificaciones procesadas')
            message = f'Importación exitosa: {", ".join(parts)}'
        elif total_ok > 0:
            result_status = 'partial'
            parts = []
            if success_count > 0:
                parts.append(f'{success_count} creados')
            if updated_count > 0:
                parts.append(f'{updated_count} actualizados')
            if cert_updates_count > 0:
                parts.append(f'{cert_updates_count} certificaciones')
            message = f'Importación parcial: {", ".join(parts)}, {skipped_count} con errores'
        else:
            result_status = 'error'
            message = f'Importación fallida: {skipped_count} registros con errores'
        
        return ImportResult(
            status=result_status,
            total_processed=total_rows,
            success_count=success_count,
            updated_count=updated_count,
            cert_updates_count=cert_updates_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors[:50],
            message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            cert_updates_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté dañado y tenga el formato correcto')],
            message='Error crítico: No se pudo procesar el archivo'
        )

