"""Route module: dashboard.py"""
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template
from models import *
from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator


router = APIRouter()

# ==================== DASHBOARD ALERTS ====================

@router.get("/dashboard/stats")
async def get_dashboard_stats(authorization: Optional[str] = Header(None)):
    """Retorna los contadores del dashboard en una sola llamada"""
    current_user = await get_current_user(authorization)
    
    # Para cotizaciones: filtrar por sede si no es admin
    quotes_query = {}
    if current_user.get("role") != "admin":
        user_sede = current_user.get("sede", "PYME")
        quotes_query["sede"] = user_sede
    
    quotes_count = await db.quotes.count_documents(quotes_query)
    clients_count = await db.clients.count_documents({})
    banks_count = await db.banks.count_documents({})
    services_count = await db.services.count_documents({})
    hardware_count = await db.hardware.count_documents({})
    
    # Tasa de cambio
    rate_doc = await db.exchange_rates.find_one({"active": True}, {"_id": 0})
    exchange_rate = rate_doc.get("rate", 0) if rate_doc else 0
    
    return {
        "totalQuotes": quotes_count,
        "totalClients": clients_count,
        "totalBanks": banks_count,
        "totalMediosPago": services_count,
        "totalHardware": hardware_count,
        "exchangeRate": exchange_rate
    }

@router.get("/dashboard/alerts")
async def get_dashboard_alerts(authorization: Optional[str] = Header(None)):
    """Obtiene alertas de seguimiento para el dashboard"""
    await get_current_user(authorization)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_later = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Obtener logs con fecha de seguimiento pendiente (no completados)
    logs = await db.client_logs.find(
        {"follow_up_date": {"$ne": None}, "is_completed": {"$ne": True}},
        {"_id": 0}
    ).sort("follow_up_date", 1).to_list(200)
    
    # Clasificar por semáforo
    overdue = []  # Rojo
    today_list = []  # Amarillo
    upcoming = []  # Verde
    
    # Obtener info de clientes para enriquecer las alertas
    client_ids = list(set(log["client_id"] for log in logs))
    clients_map = {}
    if client_ids:
        clients = await db.clients.find({"client_id": {"$in": client_ids}}, {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1, "sucursal": 1}).to_list(200)
        clients_map = {c["client_id"]: c for c in clients}
    
    for log in logs:
        fd = log.get("follow_up_date", "")
        if not fd:
            continue
        client_info = clients_map.get(log["client_id"], {})
        enriched = {
            **log,
            "client_name": client_info.get("fantasy_name") or client_info.get("legal_name", "—"),
            "client_rif": client_info.get("rif", ""),
            "client_sucursal": client_info.get("sucursal", "")
        }
        if fd < today:
            enriched["priority"] = "overdue"
            overdue.append(enriched)
        elif fd == today:
            enriched["priority"] = "today"
            today_list.append(enriched)
        elif fd <= week_later:
            enriched["priority"] = "upcoming"
            upcoming.append(enriched)
    
    return {
        "overdue": overdue,
        "today": today_list,
        "upcoming": upcoming,
        "total": len(overdue) + len(today_list) + len(upcoming)
    }

@router.get("/dashboard/missing-pdfs")
async def get_missing_pdfs(authorization: Optional[str] = Header(None)):
    """Retorna cotizaciones que no tienen PDF generado"""
    current_user = await get_current_user(authorization)
    
    query = {
        "$or": [
            {"quote_pdf_url": None},
            {"quote_pdf_url": ""},
            {"attachments": {"$size": 0}},
            {"attachments": {"$exists": False}}
        ],
        "quote_category": {"$ne": "equipment"}
    }
    if current_user.get("role") != "admin":
        query["sede"] = current_user.get("sede", "PYME")
    
    quotes = await db.quotes.find(query, {"_id": 0, "quote_id": 1, "quote_number": 1, "quote_type": 1, "client_name": 1, "created_at": 1, "quote_status": 1}).sort("created_at", -1).to_list(100)
    
    return {"missing_pdfs": quotes, "count": len(quotes)}

@router.post("/quotes/{quote_id}/regenerate-pdf")
async def regenerate_quote_pdf(quote_id: str, authorization: Optional[str] = Header(None)):
    """Regenera el PDF de una cotización existente"""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    client_nombre = ""
    client_rif = ""
    client_contacto = ""
    if client:
        client_nombre = client.get("legal_name", client.get("fantasy_name", ""))
        client_rif = client.get("rif", "")
        contacts = client.get("contacts", [])
        client_contacto = contacts[0].get("name", "") if contacts else ""
    
    quote_number = quote.get("quote_number", "SIN-NUMERO")
    quote_type = quote.get("quote_type", "VPOS_MPOS")
    
    logo_path = None
    logo_file = UPLOADS_DIR / "logo.png"
    if logo_file.exists():
        logo_path = str(logo_file)
    
    try:
        if quote_type == "GATEWAY":
            pg_setup_list = quote.get("pg_setup_items", [])
            rec_basic = []
            pg_rc_data = quote.get("pg_recurring_cost")
            if pg_rc_data and pg_rc_data.get("rangos"):
                for rango in pg_rc_data["rangos"]:
                    rec_basic.append(QuotePDFItem(
                        concepto=f"Rango {rango.get('rango_label', 'N/A')} - Precio tope: ${rango.get('precio_tope', 0):.2f}",
                        cantidad_cajas=1, cantidad_bancos=1,
                        tarifa=rango.get("costo_base_total", 0), bank_name=""
                    ))
            
            pdf_request = TemplateQuotePDFRequest(
                quote_type="GATEWAY",
                quote_number=quote_number,
                cliente_nombre=client_nombre,
                cliente_rif=client_rif,
                cliente_contacto=client_contacto,
                integrator_name=quote.get("integrator_name", ""),
                integrator_app_name=quote.get("integrator_app_name", ""),
                pg_setup_items=pg_setup_list,
                pg_recurring_cost=pg_rc_data,
                recurring_basic_items=rec_basic,
                notes=quote.get("notes", ""),
            )
            generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
            pdf_buffer = generator.generate()
            pdf_buffer = append_pg_static_pages(pdf_buffer)
        else:
            # VPOS/MPOS - reconstruir desde servicios guardados
            setup_items = []
            for svc in quote.get("services", []):
                setup_items.append(QuotePDFItem(
                    concepto=svc.get("name", svc.get("concepto", "")),
                    cantidad_cajas=svc.get("cantidad_cajas", quote.get("cantidad_cajas", 1)),
                    cantidad_bancos=svc.get("cantidad_bancos", 1),
                    tarifa=svc.get("unit_price", svc.get("tarifa", 0)),
                    bank_name=svc.get("bank_name", "")
                ))
            
            recurring_basic = []
            additional = []
            for svc in quote.get("services", []):
                svc_type = svc.get("type", "")
                if svc_type == "recurring_basic":
                    recurring_basic.append(QuotePDFItem(
                        concepto=svc.get("name", ""), cantidad_cajas=svc.get("cantidad_cajas", 1),
                        cantidad_bancos=svc.get("cantidad_bancos", 1),
                        tarifa=svc.get("unit_price", 0), bank_name=svc.get("bank_name", "")
                    ))
                elif svc_type == "additional":
                    additional.append(QuotePDFItem(
                        concepto=svc.get("name", ""), cantidad_cajas=svc.get("cantidad_cajas", 1),
                        cantidad_bancos=svc.get("cantidad_bancos", 1),
                        tarifa=svc.get("unit_price", 0), bank_name=svc.get("bank_name", "")
                    ))
            
            pdf_request = TemplateQuotePDFRequest(
                template_type="vpos_pyme",
                quote_type=quote_type,
                quote_number=quote_number,
                cliente_nombre=client_nombre,
                cliente_rif=client_rif,
                cliente_contacto=client_contacto,
                integrator_name=quote.get("integrator_name", ""),
                integrator_app_name=quote.get("integrator_app_name", ""),
                pinpad_model=quote.get("pinpad_model", ""),
                sponsor_bank_name=quote.get("sponsor_bank_name", ""),
                cantidad_cajas=quote.get("cantidad_cajas", 1),
                setup_items=setup_items,
                recurring_basic_items=recurring_basic,
                additional_items=additional,
                production_items=[QuotePDFItem(**p) for p in quote.get("production_items", []) if isinstance(p, dict)],
                descuento=quote.get("descuento", 0),
                descuento_setup=quote.get("descuento_setup", 0),
                descuento_recurrente=quote.get("descuento_recurrente", 0),
                notes=quote.get("notes", ""),
                pricing_model=quote.get("pricing_model", "conventional"),
                is_production_client=quote.get("is_production_client", False),
            )
            generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
            pdf_buffer = generator.generate()
            pdf_buffer = append_vpos_static_pages(pdf_buffer)
        
        # Guardar PDF
        pdf_filename = f"{quote_number}_Cotizacion.pdf"
        pdf_path = UPLOADS_DIR / pdf_filename
        with open(pdf_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
        quote_pdf_url = f"/uploads/{pdf_filename}"
        
        # Reemplazar o agregar el attachment de Cotización
        new_attachment = {
            "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
            "category": "Cotización",
            "filename": pdf_filename,
            "url": quote_pdf_url,
            "uploaded_by": current_user.get("email", "system"),
            "uploaded_by_name": current_user.get("full_name", "Sistema"),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "file_size": len(pdf_buffer.getvalue()),
            "content_type": "application/pdf"
        }
        
        # Remover attachment anterior de categoría "Cotización" si existe
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$pull": {"attachments": {"category": "Cotización"}}}
        )
        # Agregar nuevo attachment y actualizar URL
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$push": {"attachments": new_attachment}, "$set": {"quote_pdf_url": quote_pdf_url}}
        )
        
        logging.info(f"PDF regenerado para {quote_number}: {quote_pdf_url}")
        return {"message": "PDF regenerado exitosamente", "pdf_url": quote_pdf_url, "quote_number": quote_number}
        
    except Exception as e:
        logging.error(f"Error regenerando PDF para {quote_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error regenerando PDF: {str(e)}")

@router.post("/clients/import")
async def import_clients(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                message='Formato de archivo no soportado', suggested_action='Utilice archivos .xlsx, .xls o .csv')],
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
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío', suggested_action='Agregue registros al archivo')],
                message='Error: El archivo no contiene datos'
            )
        
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        column_mapping = {
            'nombre_jurídico': 'legal_name', 'nombre_juridico': 'legal_name',
            'nombre_fantasía': 'fantasy_name', 'nombre_fantasia': 'fantasy_name',
            'segmento': 'segment', 'dirección': 'address', 'direccion': 'address',
            'contacto_nombre': 'contact_name', 'contacto_apellido': 'contact_lastname',
            'contacto_teléfono': 'contact_phone', 'contacto_telefono': 'contact_phone',
            'contacto_email': 'contact_email', 'contacto_rol': 'contact_role',
            # Legacy support
            'contacto1_nombre': 'contact_name', 'contacto1_teléfono': 'contact_phone',
            'contacto1_telefono': 'contact_phone', 'contacto1_email': 'contact_email'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        required_columns = ['rif', 'legal_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None, error_type='missing',
                    message='Columnas requeridas no encontradas',
                    suggested_action='Descargue la plantilla y use las columnas: RIF, Nombre Jurídico')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        valid_segments = ['Pymes', 'Corporativo', 'Mixto']
        valid_roles = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo']
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                rif = str(row.get('rif', '')).strip() if pd.notna(row.get('rif')) else ''
                legal_name = str(row.get('legal_name', '')).strip() if pd.notna(row.get('legal_name')) else ''
                fantasy_name = str(row.get('fantasy_name', '')).strip() if pd.notna(row.get('fantasy_name')) else ''
                segment = str(row.get('segment', 'Pymes')).strip() if pd.notna(row.get('segment')) else 'Pymes'
                sucursal = str(row.get('sucursal', 'Principal')).strip() if pd.notna(row.get('sucursal')) else 'Principal'
                address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else ''
                
                row_errors = []
                
                if not rif:
                    row_errors.append(ImportError(row=row_num, column='RIF', value='(vacío)',
                        error_type='missing', message='El RIF es obligatorio',
                        suggested_action='Ingrese un RIF válido'))
                
                if not legal_name:
                    row_errors.append(ImportError(row=row_num, column='Nombre Jurídico', value='(vacío)',
                        error_type='missing', message='El nombre jurídico es obligatorio',
                        suggested_action='Ingrese el nombre jurídico del cliente'))
                
                if segment not in valid_segments:
                    segment = 'Pymes'
                
                if row_errors:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # Verificar duplicados con llave compuesta RIF + Sucursal
                existing = await db.clients.find_one({"rif": rif, "sucursal": sucursal})
                if existing:
                    errors.append(ImportError(row=row_num, column='RIF + Sucursal', value=f'{rif} / {sucursal}',
                        error_type='duplicate', message=f'Ya existe un cliente con RIF {rif} y sucursal "{sucursal}"',
                        suggested_action='Cambie la sucursal o verifique si desea actualizar el registro'))
                    skipped_count += 1
                    continue
                
                # Construir contactos CRM
                contacts_crm = []
                contact_name = str(row.get('contact_name', '')).strip() if pd.notna(row.get('contact_name')) else ''
                contact_lastname = str(row.get('contact_lastname', '')).strip() if pd.notna(row.get('contact_lastname')) else ''
                contact_phone = str(row.get('contact_phone', '')).strip() if pd.notna(row.get('contact_phone')) else ''
                contact_email = str(row.get('contact_email', '')).strip() if pd.notna(row.get('contact_email')) else ''
                contact_role = str(row.get('contact_role', 'Administrativo')).strip() if pd.notna(row.get('contact_role')) else 'Administrativo'
                if contact_role not in valid_roles:
                    contact_role = 'Administrativo'
                
                if contact_name:
                    contacts_crm.append({
                        "contact_id": f"cnt_{uuid.uuid4().hex[:8]}",
                        "first_name": contact_name,
                        "last_name": contact_lastname,
                        "phone": contact_phone,
                        "email": contact_email,
                        "role": contact_role
                    })
                
                client = Client(
                    rif=rif,
                    legal_name=legal_name,
                    fantasy_name=fantasy_name,
                    segment=segment,
                    sucursal=sucursal,
                    address=address,
                    contacts=contacts_crm,
                    contact1=Contact(name=f'{contact_name} {contact_lastname}'.strip() or 'N/A', phone=contact_phone or 'N/A', email=contact_email or 'sin@email.com'),
                    contact2=Contact(name='N/A', phone='N/A', email='sin@email.com')
                )
                
                doc = client.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.clients.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='general', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos'))
                skipped_count += 1
        
        if success_count == 0 and errors:
            status = 'error'
            message = f'Error: No se pudo importar ningún registro. {len(errors)} errores encontrados.'
        elif errors:
            status = 'partial'
            message = f'Importación parcial: {success_count} registros importados, {skipped_count} omitidos.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} clientes importados correctamente.'
        
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


@router.get("/clients/export/pdf")
async def export_clients_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    clients = await db.clients.find({}, {"_id": 0}).to_list(1000)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Clientes - Cotizador Merchant Server", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['RIF', 'Nombre Jurídico', 'Nombre Fantasía', 'Segmento', 'Contacto']]
    for c in clients:
        contact_name = c.get('contact1', {}).get('name', 'N/A') if isinstance(c.get('contact1'), dict) else 'N/A'
        data.append([
            c['rif'][:15],
            c['legal_name'][:25],
            c['fantasy_name'][:20],
            c.get('segment', 'N/A'),
            contact_name[:20]
        ])
    
    table = Table(data, colWidths=[1.2*inch, 2*inch, 1.5*inch, 1*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00447C')),
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
        headers={"Content-Disposition": "attachment; filename=clientes.pdf"}
    )

