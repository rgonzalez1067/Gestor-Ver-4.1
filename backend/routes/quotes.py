"""Route module: quotes.py"""
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, append_corporate_static_pages, append_equipment_conditions, render_email_template
from models import *
from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator
import traceback

router = APIRouter()

# ==================== QUOTES ENDPOINTS ====================

@router.post("/quotes", response_model=Quote)
async def create_quote(quote_data: QuoteCreate, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    
    exchange_rate_doc = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
    
    # Si no hay tasa de cambio, usar valor por defecto
    if not exchange_rate_doc:
        exchange_rate = 40.0  # Valor por defecto
    else:
        exchange_rate = exchange_rate_doc["rate"]
    
    # Calcular totales según el tipo de cotización
    if quote_data.quote_category == "equipment":
        # Cotización de equipos/accesorios
        subtotal_usd = sum(item.total_usd for item in quote_data.equipment_items)
        total_usd = subtotal_usd
    elif quote_data.quote_type == "GATEWAY" and quote_data.pg_setup_items:
        # Cotización Payment Gateway - total es suma de setup items
        subtotal_usd = sum(item.get("costo", 0) for item in quote_data.pg_setup_items)
        total_usd = subtotal_usd
    else:
        # Cotización de implementación (flujo original)
        subtotal_usd = sum(item.total_usd for item in quote_data.services) + sum(item.total_usd for item in quote_data.hardware)
        total_usd = subtotal_usd
    
    total_bs = total_usd * exchange_rate
    
    # Obtener la sede del usuario actual
    user_sede = current_user.get("sede", "PYME")
    
    quote_number = await generate_quote_number(user_sede)
    
    quote = Quote(
        quote_number=quote_number,
        client_id=quote_data.client_id,
        quote_category=quote_data.quote_category or "implementation",
        quote_type=quote_data.quote_type or "VPOS",
        equipment_type=quote_data.equipment_type,
        pricing_model=quote_data.pricing_model or "conventional",
        services=quote_data.services,
        hardware=quote_data.hardware,
        equipment_items=quote_data.equipment_items,
        subtotal_usd=subtotal_usd,
        total_usd=total_usd,
        exchange_rate=exchange_rate,
        total_bs=total_bs,
        notes=quote_data.notes,
        integrator_id=quote_data.integrator_id,
        integrator_name=quote_data.integrator_name,
        integrator_app_name=quote_data.integrator_app_name,
        pinpad_id=quote_data.pinpad_id,
        pinpad_model=quote_data.pinpad_model,
        sponsor_bank_id=quote_data.sponsor_bank_id,
        sponsor_bank_name=quote_data.sponsor_bank_name,
        cantidad_cajas=quote_data.cantidad_cajas,
        cantidad_bancos=quote_data.cantidad_bancos,
        pg_setup_items=quote_data.pg_setup_items,
        pg_recurring_cost=quote_data.pg_recurring_cost,
        pg_transaction_range=quote_data.pg_transaction_range,
        sede=user_sede,  # Sede del usuario
        created_by_user_id=current_user.get("user_id")  # ID del usuario que crea
    )
    
    doc = quote.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.quotes.insert_one(doc)
    
    return quote

# Modelo para crear cotización con PDF
class QuoteCreateWithPDF(BaseModel):
    """Modelo combinado para crear cotización y generar PDF"""
    # Datos básicos de la cotización
    client_id: str
    quote_category: str = "implementation"
    quote_type: str = "VPOS"
    equipment_type: Optional[str] = None
    pricing_model: str = "conventional"
    services: List[QuoteItem] = []
    hardware: List[QuoteItem] = []
    equipment_items: List[EquipmentQuoteItem] = []
    ft_equipment_items: List[dict] = []  # Fast Track equipment items for Mega Soft sponsor
    notes: Optional[str] = None
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Datos para el PDF (diccionario flexible)
    pdf_data: Optional[dict] = None
    # Campos específicos para Payment Gateway
    pg_setup_items: List[dict] = []
    pg_recurring_cost: Optional[dict] = None
    pg_transaction_range: Optional[int] = None
    # Descuentos independientes
    descuento_setup: float = 0
    descuento_recurrente: float = 0
    # Cliente en producción
    is_production_client: bool = False
    production_items: List[dict] = []
    # Parámetros dinámicos VPOS
    requires_pinpad_config: bool = True
    requires_vpn: bool = True
    # Segmento de cliente
    client_segment: str = "PYME"
    # Detalle de sucursales (opcional, para VPOS/MPOS/Fast Track)
    branch_details: List[dict] = []  # [{store_name: str, quantity: int}]

@router.post("/quotes/create-with-pdf")
async def create_quote_with_pdf(data: QuoteCreateWithPDF, authorization: Optional[str] = Header(None)):
    """
    Crea una cotización y genera el PDF automáticamente.
    El PDF se almacena en el servidor y se guarda la URL en la cotización.
    """
    current_user = await get_current_user(authorization)
    
    try:
        exchange_rate_doc = await db.exchange_rates.find_one({}, {"_id": 0}, sort=[("date", -1)])
        
        if not exchange_rate_doc:
            exchange_rate = 40.0
        else:
            exchange_rate = exchange_rate_doc["rate"]
        
        # Calcular totales
        if data.quote_category == "equipment":
            subtotal_usd = sum(item.total_usd for item in data.equipment_items)
            total_usd = subtotal_usd
        elif data.quote_type == "GATEWAY" and data.pg_setup_items:
            subtotal_usd = sum(item.get("costo", 0) for item in data.pg_setup_items)
            total_usd = subtotal_usd
        else:
            subtotal_usd = sum(item.total_usd for item in data.services) + sum(item.total_usd for item in data.hardware)
            total_usd = subtotal_usd
        
        total_bs = total_usd * exchange_rate
        
        # Obtener la sede del usuario actual
        user_sede = current_user.get("sede", "PYME")
        
        quote_number = await generate_quote_number(user_sede)
        quote_id = f"quo_{uuid.uuid4().hex[:12]}"
        
        # Generar PDF si se proporcionaron los datos
        quote_pdf_url = None
        pdf_buffer = None
        if data.pdf_data:
            try:
                # Convertir dict a TemplateQuotePDFRequest
                pdf_request = TemplateQuotePDFRequest(**data.pdf_data)
                pdf_request.quote_number = quote_number
                
                # Obtener logo si existe
                logo_path = None
                logo_file = UPLOADS_DIR / "logo.png"
                if logo_file.exists():
                    logo_path = str(logo_file)
                
                # Crear generador
                generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
                
                # Generar PDF
                pdf_buffer = generator.generate()
                
                # Agregar páginas estáticas según tipo
                if data.quote_type == 'GATEWAY':
                    pdf_buffer = append_pg_static_pages(pdf_buffer)
                elif pdf_request.client_segment == 'CORP':
                    pdf_buffer = append_corporate_static_pages(pdf_buffer)
                else:
                    pdf_buffer = append_vpos_static_pages(pdf_buffer)
                
                # Guardar PDF en el servidor
                pdf_filename = f"{quote_number}_Cotizacion.pdf"
                pdf_path = UPLOADS_DIR / pdf_filename
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_buffer.getvalue())
                
                quote_pdf_url = f"/uploads/{pdf_filename}"
                logging.info(f"PDF generado y almacenado: {quote_pdf_url}")
                
            except Exception as e:
                logging.error(f"Error generando PDF: {str(e)}")
                # Continuar sin PDF si falla la generación
        elif data.quote_type == "GATEWAY" and data.pg_setup_items:
            # Generar PDF para Payment Gateway usando DynamicQuotePDFGenerator
            try:
                client = await db.clients.find_one({"client_id": data.client_id}, {"_id": 0})
                if client:
                    # Construir TemplateQuotePDFRequest desde los datos disponibles
                    pg_setup_list = [item if isinstance(item, dict) else item.dict() for item in data.pg_setup_items]
                    
                    # Construir items recurrentes
                    rec_basic = []
                    rec_other = []
                    if data.pg_recurring_cost:
                        rc = data.pg_recurring_cost if isinstance(data.pg_recurring_cost, dict) else data.pg_recurring_cost.dict()
                        if rc.get('rangos'):
                            for rango in rc['rangos']:
                                rec_basic.append(QuotePDFItem(
                                    concepto=f"Rango {rango.get('rango_label', 'N/A')} - Precio tope: ${rango.get('precio_tope', 0):.2f}",
                                    cantidad_cajas=1,
                                    cantidad_bancos=1,
                                    tarifa=rango.get('costo_base_total', 0),
                                    bank_name=""
                                ))
                    
                    # Preparar pg_recurring_cost para el generador
                    pg_rc_data = None
                    if data.pg_recurring_cost:
                        rc = data.pg_recurring_cost if isinstance(data.pg_recurring_cost, dict) else data.pg_recurring_cost.dict()
                        pg_rc_data = rc
                    
                    pdf_request = TemplateQuotePDFRequest(
                        quote_type="GATEWAY",
                        quote_number=quote_number,
                        cliente_nombre=client.get('legal_name', client.get('fantasy_name', '')),
                        cliente_rif=client.get('rif', ''),
                        cliente_contacto=client.get('contacts', [{}])[0].get('name', '') if client.get('contacts') else '',
                        integrator_name=data.integrator_name or '',
                        integrator_app_name=data.integrator_app_name or '',
                        pg_setup_items=pg_setup_list,
                        pg_recurring_cost=pg_rc_data,
                        recurring_basic_items=rec_basic,
                        recurring_other_items=rec_other,
                        production_items=[],
                        notes=data.notes or '',
                    )
                    
                    logo_path = None
                    logo_file = UPLOADS_DIR / "logo.png"
                    if logo_file.exists():
                        logo_path = str(logo_file)
                    
                    generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
                    pdf_buffer = generator.generate()
                    pdf_buffer = append_pg_static_pages(pdf_buffer)
                    
                    pdf_filename = f"{quote_number}_Cotizacion.pdf"
                    pdf_path = UPLOADS_DIR / pdf_filename
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_buffer.getvalue())
                    quote_pdf_url = f"/uploads/{pdf_filename}"
                    logging.info(f"PDF PG generado con DynamicGenerator: {quote_pdf_url}")
            except Exception as e:
                logging.error(f"Error generando PDF PG: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Crear anexo automático para el PDF generado
        initial_attachments = []
        if quote_pdf_url:
            initial_attachments.append({
                "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
                "category": "Cotización",
                "filename": pdf_filename,
                "url": quote_pdf_url,
                "uploaded_by": current_user.get("email", "system"),
                "uploaded_by_name": current_user.get("full_name", "Sistema"),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": len(pdf_buffer.getvalue()) if pdf_buffer else 0,
                "content_type": "application/pdf"
            })
        
        # Obtener nombre del cliente
        client_doc = await db.clients.find_one({"client_id": data.client_id}, {"_id": 0, "legal_name": 1, "fantasy_name": 1})
        client_display_name = (client_doc.get("fantasy_name") or client_doc.get("legal_name", "")) if client_doc else ""
        
        # Crear la cotización
        quote = Quote(
            quote_id=quote_id,
            quote_number=quote_number,
            client_id=data.client_id,
            client_name=client_display_name,
            quote_category=data.quote_category or "implementation",
            quote_type=data.quote_type or "VPOS",
            equipment_type=data.equipment_type,
            pricing_model=data.pricing_model or "conventional",
            services=data.services,
            hardware=data.hardware,
            equipment_items=data.equipment_items,
            ft_equipment_items=data.ft_equipment_items,  # Fast Track equipment items
            subtotal_usd=subtotal_usd,
            total_usd=total_usd,
            exchange_rate=exchange_rate,
            total_bs=total_bs,
            notes=data.notes,
            integrator_id=data.integrator_id,
            integrator_name=data.integrator_name,
            integrator_app_name=data.integrator_app_name,
            pinpad_id=data.pinpad_id,
            pinpad_model=data.pinpad_model,
            sponsor_bank_id=data.sponsor_bank_id,
            sponsor_bank_name=data.sponsor_bank_name,
            cantidad_cajas=data.cantidad_cajas,
            cantidad_bancos=data.cantidad_bancos,
            pg_setup_items=data.pg_setup_items,
            pg_recurring_cost=data.pg_recurring_cost,
            pg_transaction_range=data.pg_transaction_range,
            descuento_setup=data.descuento_setup,
            descuento_recurrente=data.descuento_recurrente,
            is_production_client=data.is_production_client,
            production_items=data.production_items,
            branch_details=data.branch_details,
            requires_pinpad_config=data.requires_pinpad_config,
            requires_vpn=data.requires_vpn,
            sede=user_sede,
            client_segment=data.client_segment or user_sede,
            created_by_user_id=current_user.get("user_id"),
            quote_pdf_url=quote_pdf_url,
            attachments=initial_attachments
        )
        
        doc = quote.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.quotes.insert_one(doc)
        
        return {
            "quote": quote,
            "pdf_url": quote_pdf_url,
            "message": "Cotización creada exitosamente" + (" con PDF" if quote_pdf_url else "")
        }
        
    except Exception as e:
        logging.error(f"Error creando cotización con PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear cotización: {str(e)}")


@router.get("/pg-recurring-costs")
async def get_pg_recurring_costs(authorization: Optional[str] = Header(None)):
    """Devuelve la tabla de costos recurrentes para Payment Gateway"""
    await get_current_user(authorization)
    return PG_RECURRING_COSTS_TABLE

@router.get("/pg-defaults")
async def get_pg_defaults(authorization: Optional[str] = Header(None)):
    """Devuelve la configuración por defecto de Payment Gateway (Persona Jurídica)"""
    await get_current_user(authorization)
    # Buscar "Persona Jurídica" en los productos de bancos
    pg_default = await db.config.find_one({"type": "pg_persona_juridica"}, {"_id": 0})
    if pg_default:
        return pg_default
    # Si no existe en config, crear valor por defecto
    default = {
        "type": "pg_persona_juridica",
        "concepto": "Persona Jurídica",
        "costo": 240.00,
        "descripcion": "Costo base de configuración para Persona Jurídica"
    }
    await db.config.insert_one(default)
    return {k: v for k, v in default.items() if k != "_id"}

@router.put("/pg-defaults")
async def update_pg_defaults(data: dict, authorization: Optional[str] = Header(None)):
    """Actualiza el costo de Persona Jurídica para PG"""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden modificar esta configuración")
    costo = data.get("costo", 240.00)
    await db.config.update_one(
        {"type": "pg_persona_juridica"},
        {"$set": {"costo": costo}},
        upsert=True
    )
    return {"message": "Configuración actualizada", "costo": costo}


@router.get("/quotes", response_model=List[Quote])
async def get_quotes(authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    
    # Construir filtro jerárquico basado en cargo del usuario
    query = {}
    if current_user.get("role") != "admin":
        cargo = (current_user.get("cargo") or "").lower()
        user_id = current_user.get("user_id")
        user_depto = current_user.get("departamento", "")
        
        if "director" in cargo:
            # Director: ve todo (sin filtro adicional)
            pass
        elif "gerente" in cargo:
            # Gerente de Ventas: ve todo su departamento
            # Buscar todos los user_ids del mismo departamento
            if user_depto:
                dept_users = await db.users.find(
                    {"departamento": user_depto, "is_active": {"$ne": False}},
                    {"_id": 0, "user_id": 1}
                ).to_list(500)
                dept_user_ids = [u["user_id"] for u in dept_users]
                query["created_by_user_id"] = {"$in": dept_user_ids}
            else:
                query["created_by_user_id"] = user_id
        elif "coordinador" in cargo:
            # Coordinador: ve sus cotizaciones + las de Ejecutivos de su departamento
            if user_depto:
                team_users = await db.users.find(
                    {"departamento": user_depto, "is_active": {"$ne": False},
                     "$or": [
                         {"cargo": {"$regex": "ejecutivo", "$options": "i"}},
                         {"user_id": user_id}
                     ]},
                    {"_id": 0, "user_id": 1}
                ).to_list(500)
                team_user_ids = [u["user_id"] for u in team_users]
                query["created_by_user_id"] = {"$in": team_user_ids}
            else:
                query["created_by_user_id"] = user_id
        else:
            # Ejecutivo u otro cargo: solo ve sus propias cotizaciones
            query["created_by_user_id"] = user_id
    
    quotes = await db.quotes.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Cache de clientes para resolver nombres
    client_ids_missing = set()
    for quote in quotes:
        if quote.get('created_at') and isinstance(quote['created_at'], str):
            quote['created_at'] = datetime.fromisoformat(quote['created_at'])
        if 'sede' not in quote:
            quote['sede'] = 'PYME'
        if not quote.get('client_name') and quote.get('client_id'):
            client_ids_missing.add(quote['client_id'])
    
    # Resolver nombres de clientes faltantes
    if client_ids_missing:
        client_docs = {}
        async for c in db.clients.find({"client_id": {"$in": list(client_ids_missing)}}, {"_id": 0, "client_id": 1, "legal_name": 1, "fantasy_name": 1}):
            client_docs[c['client_id']] = c.get('fantasy_name') or c.get('legal_name', '')
        for quote in quotes:
            if not quote.get('client_name') and quote.get('client_id'):
                quote['client_name'] = client_docs.get(quote['client_id'], 'N/A')
    
    return quotes

@router.get("/quotes/{quote_id}", response_model=Quote)
async def get_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if isinstance(quote['created_at'], str):
        quote['created_at'] = datetime.fromisoformat(quote['created_at'])
    return quote

@router.get("/quotes/{quote_id}/pdf")
async def generate_quote_pdf(quote_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    client = await db.clients.find_one({"client_id": quote["client_id"]}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("<b>COTIZACIÓN</b>", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    info_data = [
        ["Cotización #:", quote["quote_number"]],
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", client["legal_name"]],
        ["RIF:", client["rif"]],
    ]
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    if quote["services"]:
        elements.append(Paragraph("<b>Servicios</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        service_data = [["Descripción", "Cantidad", "Precio Unit.", "Total"]]
        for item in quote["services"]:
            service_data.append([
                item["item_name"],
                str(item["quantity"]),
                f"${item['unit_price_usd']:.2f}",
                f"${item['total_usd']:.2f}"
            ])
        
        service_table = Table(service_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
        service_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(service_table)
        elements.append(Spacer(1, 0.3*inch))
    
    if quote["hardware"]:
        elements.append(Paragraph("<b>Hardware</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        hardware_data = [["Descripción", "Cantidad", "Precio Unit.", "Total"]]
        for item in quote["hardware"]:
            hardware_data.append([
                item["item_name"],
                str(item["quantity"]),
                f"${item['unit_price_usd']:.2f}",
                f"${item['total_usd']:.2f}"
            ])
        
        hardware_table = Table(hardware_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
        hardware_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(hardware_table)
        elements.append(Spacer(1, 0.3*inch))
    
    totals_data = [
        ["Subtotal (USD):", f"${quote['subtotal_usd']:.2f}"],
        ["Total (USD):", f"${quote['total_usd']:.2f}"],
        ["Tasa de Cambio:", f"{quote['exchange_rate']:.2f} Bs/USD"],
        ["Total (Bs):", f"{quote['total_bs']:.2f} Bs"]
    ]
    totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.black),
    ]))
    elements.append(totals_table)
    
    if quote.get("notes"):
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph("<b>Notas:</b>", styles['Heading3']))
        elements.append(Paragraph(quote["notes"], styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=quote_{quote['quote_number']}.pdf"}
    )

class QuoteUpdate(BaseModel):
    """Modelo para actualizar cotización existente"""
    quote_type: Optional[str] = None
    client_id: Optional[str] = None
    pricing_model: Optional[str] = None
    services: Optional[List[QuoteItem]] = None
    hardware: Optional[List[QuoteItem]] = None
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None
    pinpad_id: Optional[str] = None
    pinpad_model: Optional[str] = None
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    subtotal_usd: Optional[float] = None
    total_usd: Optional[float] = None
    descuento: Optional[float] = None
    descuento_setup: Optional[float] = None
    descuento_recurrente: Optional[float] = None
    exchange_rate: Optional[float] = None
    total_bs: Optional[float] = None
    notes: Optional[str] = None
    # Campos de cantidades a nivel de cotización
    cantidad_cajas: Optional[int] = None
    cantidad_bancos: Optional[int] = None
    # Cliente en producción
    is_production_client: Optional[bool] = None
    production_items: Optional[List[dict]] = None

@router.put("/quotes/{quote_id}")
async def update_quote(quote_id: str, quote_update: QuoteUpdate, authorization: Optional[str] = Header(None)):
    """Actualiza una cotización existente (solo en estado Borrador)"""
    await get_current_user(authorization)
    
    # Verificar que la cotización existe
    existing_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing_quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Solo permitir actualizar cotizaciones en estado Borrador
    if existing_quote.get("quote_status", "Borrador") != "Borrador":
        raise HTTPException(status_code=400, detail="Solo se pueden modificar cotizaciones en estado Borrador")
    
    # Preparar datos de actualización (solo campos proporcionados)
    update_data = {}
    update_fields = quote_update.model_dump(exclude_unset=True)
    
    for field, value in update_fields.items():
        if value is not None:
            update_data[field] = value
    
    # Calcular total_bs si se actualizó total_usd
    if "total_usd" in update_data:
        exchange_rate = update_data.get("exchange_rate", existing_quote.get("exchange_rate", 36.5))
        update_data["total_bs"] = update_data["total_usd"] * exchange_rate
    
    if update_data:
        result = await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Retornar cotización actualizada
    updated_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    return updated_quote

@router.delete("/quotes/{quote_id}")
async def delete_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    """Elimina una cotización (función de mantenimiento - disponible en cualquier estado)"""
    print(f"[DELETE QUOTE] Recibida solicitud para eliminar quote_id: {quote_id}")
    
    await get_current_user(authorization)
    print("[DELETE QUOTE] Usuario autenticado correctamente")
    
    # Verificar que la cotización existe
    existing_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing_quote:
        print(f"[DELETE QUOTE] ERROR: Cotización no encontrada: {quote_id}")
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    quote_number = existing_quote.get("quote_number", quote_id)
    print(f"[DELETE QUOTE] Cotización encontrada: {quote_number}, procediendo a eliminar...")
    
    # Eliminar la cotización (sin restricción de estado - función de mantenimiento)
    result = await db.quotes.delete_one({"quote_id": quote_id})
    print(f"[DELETE QUOTE] Resultado de delete_one: deleted_count={result.deleted_count}")
    
    if result.deleted_count == 0:
        print("[DELETE QUOTE] ERROR: delete_one retornó 0")
        raise HTTPException(status_code=404, detail="Error al eliminar la cotización")
    
    print(f"[DELETE QUOTE] ÉXITO: Cotización {quote_number} eliminada")
    return {"message": f"Cotización {quote_number} eliminada exitosamente", "quote_id": quote_id}

@router.post("/quotes/generate-pdf")
async def generate_quote_pdf_from_data(data: QuotePDFRequest, authorization: Optional[str] = Header(None)):
    """Genera un PDF de cotización desde los datos del frontend sin guardar en BD"""
    await get_current_user(authorization)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título
    title_style = styles['Title']
    title_style.fontSize = 16
    elements.append(Paragraph("<b>COTIZACIÓN - Merchant Server</b>", title_style))
    elements.append(Spacer(1, 0.15*inch))
    
    # Información del cliente
    quote_type_names = {
        'VPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'VPOS': 'VPOS (Cajas)',
        'MPOS': 'MPOS (Tablet/Móvil)',
        'FAST_TRACK': 'POS Stand Alone (Fast Track)',
        'VPOS_MPOS': 'VPOS/MPOS',
        'GATEWAY': 'Payment Gateway',
        'MPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'LINK': 'Link de Pago'
    }
    pricing_model_names = {
        'conventional': 'Modelo Convencional',
        'outsourcing': 'Modelo Outsourcing'
    }
    
    info_data = [
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", data.cliente_nombre],
        ["RIF:", data.cliente_rif or "N/A"],
        ["Tipo de Servicio:", quote_type_names.get(data.quote_type, data.quote_type)],
        ["Modelo de Precios:", pricing_model_names.get(data.pricing_model, data.pricing_model)],
    ]
    
    # Agregar información de integración y hardware si está disponible
    if data.integrator_name:
        info_data.append(["Integrador:", f"{data.integrator_name} ({data.integrator_app_name})"])
    if data.pinpad_model:
        info_data.append(["Modelo de Pinpad:", data.pinpad_model])
    if data.sponsor_bank_name:
        info_data.append(["Entidad Patrocinadora:", data.sponsor_bank_name])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # PG Setup Items (for Payment Gateway quotes)
    if data.pg_setup_items:
        elements.append(Paragraph("<b>Payment Gateway - Inversión en Setup / Arranque</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.05*inch))
        pg_data = [["Concepto", "Costo ($)", "Banco", "Observación"]]
        pg_total = 0
        for item in data.pg_setup_items:
            costo = item.get('costo', 0)
            pg_total += costo
            pg_data.append([
                item.get('concepto', ''),
                f"${costo:.2f}",
                item.get('banco', 'N/A'),
                item.get('observacion', '')
            ])
        pg_data.append(["Total Setup:", f"${pg_total:.2f}", "", ""])
        pg_table = Table(pg_data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
        pg_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.05, 0.55, 0.35)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.9, 0.95, 0.9)),
        ]))
        elements.append(pg_table)
        elements.append(Spacer(1, 0.15*inch))
    
    # PG Recurring Costs - Full table
    if data.pg_recurring_cost:
        rc = data.pg_recurring_cost if isinstance(data.pg_recurring_cost, dict) else {}
        elements.append(Paragraph("<b>Costos Recurrentes Mensuales</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.05*inch))
        num_products = rc.get('num_products', 0)
        if num_products:
            elements.append(Paragraph(f"Calculado para <b>{num_products}</b> medio(s) de pago", styles['Normal']))
            elements.append(Spacer(1, 0.05*inch))
        rc_data = [["Rango", "Transacciones", "Total $ Base", "Precio Tope por Rango"]]
        table_rows = rc.get('table', [])
        if table_rows:
            for row in table_rows:
                rc_data.append([
                    str(row.get('rango', '')),
                    row.get('label', 'N/A'),
                    f"${row['base']:.2f}" if row.get('base') is not None else "Negociable",
                    f"${row['tope']:.6f}" if row.get('tope') is not None else "N/A"
                ])
        else:
            # Fallback for old format (single row)
            rc_data.append([
                "1",
                rc.get('rango_label', 'N/A'),
                f"${rc.get('base', 0):.2f}" if rc.get('base') is not None else "Negociable",
                f"${rc.get('tope', 0):.6f}" if rc.get('tope') else "N/A"
            ])
        rc_table = Table(rc_data, colWidths=[0.6*inch, 1.8*inch, 1.5*inch, 1.8*inch])
        rc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.15, 0.35, 0.7)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 1)]),
        ]))
        elements.append(rc_table)
        elements.append(Spacer(1, 0.15*inch))
    
    # Función para crear tabla de items
    def create_items_table(items, header_color, title):
        if not items:
            return None
        
        elements.append(Paragraph(f"<b>{title}</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.05*inch))
        
        table_data = [["N°", "Concepto", "Cajas", "Bancos", "Tarifa USD", "Total USD"]]
        subtotal = 0
        for i, item in enumerate(items, 1):
            total = item.cantidad_cajas * item.cantidad_bancos * item.tarifa
            subtotal += total
            table_data.append([
                str(i),
                item.concepto,
                str(item.cantidad_cajas),
                str(item.cantidad_bancos),
                f"${item.tarifa:.2f}",
                f"${total:.2f}"
            ])
        
        # Fila de subtotal
        table_data.append(["", "", "", "", "Subtotal:", f"${subtotal:.2f}"])
        
        item_table = Table(table_data, colWidths=[0.4*inch, 3*inch, 0.6*inch, 0.6*inch, 0.9*inch, 0.9*inch])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), header_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            # Estilo del subtotal
            ('FONTNAME', (4, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (4, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(item_table)
        elements.append(Spacer(1, 0.15*inch))
        return subtotal
    
    # Sección SETUP (azul)
    subtotal_setup = create_items_table(data.setup_items, colors.Color(0.1, 0.4, 0.7), "INVERSIÓN INICIAL (SETUP)")
    if subtotal_setup is None:
        subtotal_setup = 0
    
    # Sección RECURRENTES BÁSICOS (verde)
    subtotal_rec_basic = create_items_table(data.recurring_basic_items, colors.Color(0.2, 0.6, 0.3), "COSTOS RECURRENTES - BÁSICOS")
    if subtotal_rec_basic is None:
        subtotal_rec_basic = 0
    
    # Sección OTROS RECURRENTES (teal)
    subtotal_rec_other = create_items_table(data.recurring_other_items, colors.Color(0.1, 0.5, 0.5), "OTROS RECURRENTES")
    if subtotal_rec_other is None:
        subtotal_rec_other = 0
    
    # Sección PRODUCCIÓN (naranja) - si hay items de producción
    subtotal_production = 0
    if data.production_items:
        subtotal_production = create_items_table(data.production_items, colors.Color(0.9, 0.5, 0.1), "CLIENTE EN PRODUCCIÓN - RECURRENTES ADICIONALES")
        if subtotal_production is None:
            subtotal_production = 0
    
    # Calcular totales con descuentos independientes
    subtotal_recurrente = subtotal_rec_basic + subtotal_rec_other + subtotal_production
    desc_setup_pct = getattr(data, 'descuento_setup', 0) or getattr(data, 'descuento', 0)
    desc_recurrente_pct = getattr(data, 'descuento_recurrente', 0) or getattr(data, 'descuento', 0)
    descuento_setup = subtotal_setup * (desc_setup_pct / 100)
    descuento_recurrente = subtotal_recurrente * (desc_recurrente_pct / 100)
    total_setup = subtotal_setup - descuento_setup
    total_recurrente = subtotal_recurrente - descuento_recurrente
    total_general = total_setup + total_recurrente
    
    # Tabla de resumen final
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("<b>RESUMEN DE LA COTIZACIÓN</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.05*inch))
    
    summary_data = [
        ["Concepto", "Subtotal", "Descuento", "Total Neto"],
        ["Inversión Inicial (Setup)", f"${subtotal_setup:.2f}", f"-${descuento_setup:.2f} ({desc_setup_pct}%)", f"${total_setup:.2f}"],
        ["Costos Recurrentes (Mensual)", f"${subtotal_recurrente:.2f}", f"-${descuento_recurrente:.2f} ({desc_recurrente_pct}%)", f"${total_recurrente:.2f}"],
        ["", "", "TOTAL GENERAL:", f"${total_general:.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.3*inch, 1.3*inch, 1.3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        # Total general
        ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (2, -1), (-1, -1), 11),
        ('BACKGROUND', (2, -1), (-1, -1), colors.Color(0.1, 0.4, 0.7)),
        ('TEXTCOLOR', (2, -1), (-1, -1), colors.whitesmoke),
    ]))
    elements.append(summary_table)
    
    # ==================== RESUMEN EJECUTIVO ====================
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("<b>RESUMEN EJECUTIVO</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Colores para la matriz
    color_amarillo = colors.Color(0.98, 0.75, 0.18)  # Amber/Amarillo
    color_azul = colors.Color(0.74, 0.85, 0.95)      # Azul claro
    color_verde = colors.Color(0.74, 0.93, 0.74)    # Verde claro
    
    # Cabecera del Resumen (Cliente, Cajas, Dirección)
    header_data = [
        ["Cliente", data.cliente_nombre],
        ["Cantidad de Cajas", str(data.cantidad_cajas)],
        ["Dirección Fiscal", data.cliente_address or "No especificada"],
    ]
    
    header_table = Table(header_data, colWidths=[1.5*inch, 5*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), color_amarillo),
        ('BACKGROUND', (0, 1), (0, 1), color_azul),
        ('BACKGROUND', (0, 2), (0, 2), color_verde),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.15*inch))
    
    # Matriz de Distribución (Bancos, Productos, Cajas)
    # Consolidar solo items con banco asociado (excluir conceptos base)
    bank_product_map = {}
    all_items = data.setup_items + data.recurring_basic_items + data.recurring_other_items
    
    for item in all_items:
        # Solo incluir items que tienen banco asociado (excluir conceptos base)
        if not item.bank_name:
            continue
            
        bank_name = item.bank_name
        product_name = item.concepto
        key = f"{bank_name}-{product_name}"
        
        if key not in bank_product_map:
            bank_product_map[key] = {
                "banco": bank_name,
                "producto": product_name,
                "cajas": 0
            }
        bank_product_map[key]["cajas"] += item.cantidad_cajas
    
    # Crear tabla de matriz
    matriz_data = [["Bancos", "Productos", "Cantidad de Cajas"]]
    total_terminales = 0
    
    for row in bank_product_map.values():
        matriz_data.append([row["banco"], row["producto"], str(row["cajas"])])
        total_terminales += row["cajas"]
    
    # Si no hay items, mostrar mensaje
    if len(matriz_data) == 1:
        matriz_data.append(["Sin medios de pago", "", "0"])
    
    matriz_table = Table(matriz_data, colWidths=[2.5*inch, 2.5*inch, 1.5*inch])
    matriz_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (0, 0), color_verde),
        ('BACKGROUND', (1, 0), (1, 0), color_azul),
        ('BACKGROUND', (2, 0), (2, 0), color_amarillo),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(matriz_table)
    
    # Total de Terminales Virtuales
    elements.append(Spacer(1, 0.05*inch))
    total_data = [["Total de Terminales Virtuales", str(total_terminales or data.cantidad_cajas)]]
    total_table = Table(total_data, colWidths=[5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(total_table)
    
    # Notas
    if data.notes:
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph("<b>Notas:</b>", styles['Heading3']))
        elements.append(Paragraph(data.notes, styles['Normal']))
    
    # Pie de página
    elements.append(Spacer(1, 0.3*inch))
    footer_style = styles['Normal']
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    elements.append(Paragraph("Este documento es una cotización y no representa un compromiso contractual.", footer_style))
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} - Cotizador Merchant Server", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"cotizacion_{data.cliente_nombre.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==================== GENERADOR DE PDF CON PLANTILLA ====================

async def _enrich_tipo_corp_from_db(data: TemplateQuotePDFRequest):
    """Enriquece items con tipo_corp desde la BD para clientes CORP.
    Busca en la colección services el tipo_corp autoritativo por nombre de concepto."""
    if data.client_segment != 'CORP':
        return
    services_cursor = db.services.find(
        {"tipo_corp": {"$exists": True, "$ne": ""}},
        {"_id": 0, "name": 1, "tipo_corp": 1}
    )
    services_list = await services_cursor.to_list(200)
    tipo_corp_map = {s["name"].lower().strip(): s["tipo_corp"] for s in services_list if s.get("tipo_corp")}
    
    for item_list in [data.setup_items, data.recurring_basic_items, data.recurring_other_items, data.production_items]:
        for item in item_list:
            if not item.tipo_corp:
                # Buscar por nombre exacto
                lookup = tipo_corp_map.get(item.concepto.lower().strip(), "")
                if not lookup:
                    # Buscar parcial: nombre del concepto contenido en un servicio
                    concepto_lc = item.concepto.lower().strip()
                    for sname, tcorp in tipo_corp_map.items():
                        if sname in concepto_lc or concepto_lc in sname:
                            lookup = tcorp
                            break
                if lookup:
                    item.tipo_corp = lookup


@router.post("/quotes/generate-pdf-with-template")
async def generate_quote_pdf_with_template(data: TemplateQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """
    Genera un PDF de cotización profesional con flujo dinámico.
    Ya no depende de plantilla base - genera el documento completo desde cero con diseño profesional.
    Características:
    - Flujo dinámico con salto de página automático
    - Sin placeholders amarillos
    - Posicionamiento exacto
    - Diseño profesional
    """
    await get_current_user(authorization)
    
    try:
        # Enriquecer items con tipo_corp desde la BD para clientes CORP
        await _enrich_tipo_corp_from_db(data)
        
        # Obtener logo si existe
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)
        
        # Crear generador
        generator = DynamicQuotePDFGenerator(data, logo_path)
        
        # Generar PDF
        pdf_buffer = generator.generate()
        
        # Agregar páginas estáticas según tipo
        if data.quote_type == 'GATEWAY':
            pdf_buffer = append_pg_static_pages(pdf_buffer)
        elif data.client_segment == 'CORP':
            pdf_buffer = append_corporate_static_pages(pdf_buffer)
        else:
            pdf_buffer = append_vpos_static_pages(pdf_buffer)
        
        # Nombre del archivo
        filename = f"cotizacion_{data.cliente_nombre.replace(' ', '_').replace('.', '')}_{data.quote_number or datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Generation-Method": "dynamic-flow"
            }
        )
        
    except Exception as e:
        logging.error(f"Error generando PDF dinámico: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")


@router.post("/quotes/preview-pdf-with-template")
async def preview_quote_pdf_with_template(data: TemplateQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """
    Genera una previsualización del PDF con flujo dinámico.
    Retorna el PDF inline para visualización en el navegador.
    """
    await get_current_user(authorization)
    
    try:
        # Enriquecer items con tipo_corp desde la BD para clientes CORP
        await _enrich_tipo_corp_from_db(data)
        
        # Obtener logo si existe
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)
        
        # Crear generador
        generator = DynamicQuotePDFGenerator(data, logo_path)
        
        # Generar PDF
        pdf_buffer = generator.generate()
        
        # Agregar páginas estáticas según tipo
        if data.quote_type == 'GATEWAY':
            pdf_buffer = append_pg_static_pages(pdf_buffer)
        elif data.client_segment == 'CORP':
            pdf_buffer = append_corporate_static_pages(pdf_buffer)
        else:
            pdf_buffer = append_vpos_static_pages(pdf_buffer)
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"}  # Inline para preview
        )
        
    except Exception as e:
        logging.error(f"Error en preview PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/quotes/check-template/{template_type}")
async def check_template_availability(template_type: str, authorization: Optional[str] = Header(None)):
    """Verifica si existe una plantilla configurada para el tipo especificado"""
    await get_current_user(authorization)
    
    templates_dir = UPLOADS_DIR / "templates"
    template_path = templates_dir / f"{template_type}.pdf"
    
    return {
        "template_type": template_type,
        "available": template_path.exists(),
        "message": "Plantilla disponible" if template_path.exists() else "No hay plantilla configurada"
    }

# Modelo para PDF de cotización de equipos
class EquipmentPDFItem(BaseModel):
    hardware_id: str = ""
    name: str
    hardware_type: str = ""
    quantity: int = 1
    unit_price_usd: float = 0
    total_usd: float = 0

class RepairModelEntry(BaseModel):
    model_name: str
    model_id: str = ""
    quantity: int = 0
    serials: List[str] = []

class EquipmentQuotePDFRequest(BaseModel):
    client_id: str = ""
    cliente_nombre: str
    cliente_rif: str = ""
    cliente_address: str = ""
    equipment_type: str = "Dispositivo"
    items: List[EquipmentPDFItem] = []
    notes: str = ""
    repair_description: str = ""
    equipment_serial_number: str = ""
    estimated_delivery_date: str = ""
    bulk_serials: List[str] = []
    repair_models: List[RepairModelEntry] = []

@router.post("/quotes/generate-equipment-pdf")
async def generate_equipment_quote_pdf(data: EquipmentQuotePDFRequest, authorization: Optional[str] = Header(None)):
    """Genera PDF, lo guarda en el servidor, crea la cotización y devuelve el PDF."""
    current_user = await get_current_user(authorization)
    import weasyprint
    import base64 as b64mod

    now = datetime.now(timezone.utc)
    # Obtener sede del usuario
    user_sede = current_user.get("sede", "PYME")
    quote_number = await generate_quote_number(user_sede)
    fecha = now.strftime("%d/%m/%Y")
    from datetime import timedelta
    vence = (now + timedelta(days=15)).strftime("%d/%m/%Y")

    # Cargar logo de la empresa si existe
    logo_html = '<div class="brand">Gestor - Work Flow</div><div class="brand-sub">Procesos Integrales</div>'
    logo_file = UPLOADS_DIR / "logo.png"
    if logo_file.exists():
        logo_b64 = b64mod.b64encode(logo_file.read_bytes()).decode()
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-height:60px;max-width:200px;object-fit:contain" />'

    type_labels = {"Verifone": "Equipos Verifone", "Morefun": "Equipos Morefun", "Accesorio": "Accesorios", "Reparación": "Reparaciones"}
    type_title = type_labels.get(data.equipment_type, data.equipment_type)

    subtotal = sum(item.quantity * item.unit_price_usd for item in data.items)
    iva = round(subtotal * 0.16, 2)
    total = round(subtotal + iva, 2)

    items_html = ""
    for item in data.items:
        line_total = item.quantity * item.unit_price_usd
        items_html += f"""<tr>
            <td><span class="item-name">{item.name}</span><span class="item-desc">{item.hardware_type}</span></td>
            <td style="text-align:center">{item.quantity}</td>
            <td style="text-align:right">${item.unit_price_usd:,.2f}</td>
            <td style="text-align:right">${line_total:,.2f}</td>
        </tr>"""

    repair_section = ""
    if data.equipment_type == "Reparación" and data.repair_description:
        # Resumen por modelo si hay repair_models
        models_summary = ""
        if data.repair_models:
            total_units = sum(m.quantity for m in data.repair_models)
            models_rows = "".join(
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px">{m.model_name}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px;text-align:center">{m.quantity}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px;text-align:center">{len(m.serials)}</td></tr>'
                for m in data.repair_models
            )
            models_summary = f"""<br>
                <table style="width:100%;border-collapse:collapse;margin-top:8px;border:1px solid #fed7aa;border-radius:4px">
                    <thead><tr style="background:#fef3c7">
                        <th style="padding:6px 10px;text-align:left;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Modelo</th>
                        <th style="padding:6px 10px;text-align:center;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Cantidad</th>
                        <th style="padding:6px 10px;text-align:center;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Seriales</th>
                    </tr></thead>
                    <tbody>{models_rows}</tbody>
                    <tfoot><tr style="background:#fef3c7">
                        <td style="padding:6px 10px;font-weight:bold;font-size:12px;color:#92400e">Total</td>
                        <td style="padding:6px 10px;font-weight:bold;font-size:12px;color:#92400e;text-align:center">{total_units}</td>
                        <td style="padding:6px 10px;font-weight:bold;font-size:12px;color:#92400e;text-align:center">{sum(len(m.serials) for m in data.repair_models)}</td>
                    </tr></tfoot>
                </table>"""
        else:
            # Legacy: serial individual o bulk
            serial_html = ""
            if data.bulk_serials:
                serial_list = "".join(f"<li style='font-size:11px;color:#475569'>{s}</li>" for s in data.bulk_serials)
                serial_html = f"""<br><strong style="font-size:12px;color:#9a3412">Seriales ({len(data.bulk_serials)}):</strong>
                    <ul style="margin:4px 0 0 16px;padding:0;columns:2;column-gap:24px">{serial_list}</ul>"""
            elif data.equipment_serial_number:
                serial_html = f'<br><span style="font-size:12px;color:#64748b">Serial: {data.equipment_serial_number}</span>'
            models_summary = serial_html

        repair_section = f"""<div style="margin:20px 0;padding:15px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px">
            <strong style="color:#9a3412">Detalle de Reparación</strong><br>
            <span style="font-size:13px;color:#475569">{data.repair_description}</span>
            {models_summary}
            {'<br><span style="font-size:12px;color:#64748b">Entrega Est.: ' + data.estimated_delivery_date + '</span>' if data.estimated_delivery_date else ''}
        </div>"""

    notes_section = ""
    if data.notes:
        notes_section = f'<br><strong>Observaciones:</strong><br><span style="font-size:12px">{data.notes}</span>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{ size: letter; margin: 40px; }}
        body {{ font-family: Helvetica, Arial, sans-serif; color: #475569; margin: 0; padding: 0; font-size: 13px; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #f8fafc; padding-bottom: 20px; margin-bottom: 30px; }}
        .brand {{ font-size: 22px; font-weight: bold; color: #1e293b; }}
        .brand-sub {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
        .quote-meta {{ text-align: right; }}
        .quote-id {{ font-size: 18px; color: #3b82f6; font-weight: 800; }}
        .quote-type {{ font-size: 12px; color: #64748b; background: #f1f5f9; padding: 3px 10px; border-radius: 4px; display: inline-block; margin-top: 6px; }}
        .info-grid {{ display: flex; justify-content: space-between; gap: 40px; margin: 30px 0; }}
        .info-block {{ flex: 1; }}
        .info-block h3 {{ font-size: 10px; text-transform: uppercase; color: #94a3b8; letter-spacing: 1px; margin: 0 0 6px 0; }}
        .info-block strong {{ color: #1e293b; font-size: 14px; }}
        .info-block span {{ font-size: 12px; color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th {{ background: #f8fafc; text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; border-bottom: 2px solid #e2e8f0; }}
        td {{ padding: 14px 12px; border-bottom: 1px solid #f1f5f9; }}
        .item-name {{ font-weight: 600; color: #1e293b; display: block; }}
        .item-desc {{ font-size: 11px; color: #94a3b8; }}
        .footer {{ margin-top: 40px; display: flex; justify-content: space-between; gap: 40px; }}
        .totals {{ background: #1e293b; color: white; padding: 20px; border-radius: 8px; min-width: 250px; }}
        .total-row {{ display: flex; justify-content: space-between; margin: 6px 0; font-size: 13px; }}
        .grand-total {{ font-size: 20px; font-weight: bold; border-top: 1px solid #334155; padding-top: 10px; margin-top: 10px; }}
        .terms {{ font-size: 10px; line-height: 1.6; color: #94a3b8; flex: 1; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            {logo_html}
        </div>
        <div class="quote-meta">
            <div class="quote-id">COTIZACIÓN #{quote_number}</div>
            <div style="font-size:12px;color:#64748b">Fecha: {fecha}</div>
            <div style="font-size:12px;color:#64748b">Vence: {vence}</div>
            <div class="quote-type">{type_title}</div>
        </div>
    </div>
    <div class="info-grid">
        <div class="info-block">
            <h3>Preparado para:</h3>
            <strong>{data.cliente_nombre}</strong><br>
            <span>RIF: {data.cliente_rif or 'N/A'}</span><br>
            <span>{data.cliente_address or ''}</span>
        </div>
        <div class="info-block" style="text-align:right">
            <h3>Emitido por:</h3>
            <strong>Mega Soft, C.A.</strong><br>
            <span>Sistema de Cotizaciones</span>
        </div>
    </div>
    {repair_section}
    <table>
        <thead>
            <tr>
                <th>Descripción del Equipo/Servicio</th>
                <th style="text-align:center">Cant.</th>
                <th style="text-align:right">P. Unitario</th>
                <th style="text-align:right">Total</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>
    <div class="footer">
        <div class="terms">
            <strong>Términos y Condiciones:</strong><br>
            Los precios están sujetos a cambio sin previo aviso según mercado.
            La garantía cubre defectos de fábrica por 12 meses. No incluye daños por mal uso.
            Los equipos se entregan configurados y listos para operar tras la validación del pago.
            {notes_section}
        </div>
        <div class="totals">
            <div class="total-row"><span>Subtotal:</span><span>${subtotal:,.2f}</span></div>
            <div class="total-row"><span>IVA (16%):</span><span>${iva:,.2f}</span></div>
            <div class="total-row grand-total"><span>TOTAL:</span><span>${total:,.2f}</span></div>
        </div>
    </div>
</body>
</html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    # Generar Anexo de Seriales por Modelo (si hay repair_models con seriales)
    if data.repair_models and any(m.serials for m in data.repair_models):
        model_blocks = ""
        for m in data.repair_models:
            if not m.serials:
                continue
            serial_items = "".join(
                f'<span style="display:inline-block;width:48%;padding:3px 0;font-size:11px;font-family:monospace;color:#334155">{s}</span>'
                for s in m.serials
            )
            model_blocks += f"""
                <div style="margin-bottom:20px">
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 14px;margin-bottom:8px">
                        <strong style="font-size:14px;color:#1e293b">{m.model_name}</strong>
                        <span style="float:right;font-size:12px;color:#64748b">{len(m.serials)} equipo(s)</span>
                    </div>
                    <div style="padding:0 8px;display:flex;flex-wrap:wrap">
                        {serial_items}
                    </div>
                </div>"""

        annexe_html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<style>
    @page {{ size: letter; margin: 40px; }}
    body {{ font-family: Helvetica, Arial, sans-serif; color: #475569; margin: 0; padding: 0; }}
</style></head><body>
    <div style="border-bottom:2px solid #e2e8f0;padding-bottom:14px;margin-bottom:24px">
        <h2 style="font-size:18px;color:#1e293b;margin:0">Anexo de Seriales por Modelo</h2>
        <p style="font-size:12px;color:#94a3b8;margin:4px 0 0 0">Cotización #{quote_number} — {data.cliente_nombre}</p>
    </div>
    {model_blocks}
    <div style="margin-top:30px;padding:16px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px">
        <p style="font-size:12px;color:#92400e;margin:0;line-height:1.6">
            <strong>Nota importante:</strong> Estimado cliente, al momento de aprobar esta Cotización asegúrese de los modelos
            y la cantidad de equipos de cada modelo que está enviando a reparación.
        </p>
    </div>
</body></html>"""

        annexe_bytes = weasyprint.HTML(string=annexe_html).write_pdf()

        # Combinar cotización + anexo con PyPDF2
        from PyPDF2 import PdfReader, PdfWriter
        writer = PdfWriter()
        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
            writer.add_page(page)
        for page in PdfReader(io.BytesIO(annexe_bytes)).pages:
            writer.add_page(page)
        combined = io.BytesIO()
        writer.write(combined)
        pdf_bytes = combined.getvalue()

    # Anexar condiciones legales según el tipo de cotización
    pdf_bytes = append_equipment_conditions(pdf_bytes, data.equipment_type, user_sede)

    # Guardar PDF en el servidor
    pdf_filename = f"{quote_number}_Cotizacion_Equipo.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename
    with open(pdf_path, 'wb') as f:
        f.write(pdf_bytes)
    quote_pdf_url = f"/uploads/{pdf_filename}"
    logging.info(f"PDF equipos generado y almacenado: {quote_pdf_url}")

    # Crear anexo automático
    attachment_entry = {
        "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
        "category": "Cotización",
        "filename": pdf_filename,
        "url": quote_pdf_url,
        "uploaded_by": current_user.get("email", "system"),
        "uploaded_by_name": current_user.get("full_name", "Sistema"),
        "uploaded_at": now.isoformat(),
        "file_size": len(pdf_bytes),
        "content_type": "application/pdf"
    }

    # Crear cotización en BD
    quote_id = f"quo_{uuid.uuid4().hex[:12]}"
    quote_category = "repair" if data.equipment_type == "Reparación" else "equipment"

    # Obtener nombre de cliente si hay client_id
    client_display_name = data.cliente_nombre
    if data.client_id:
        client_doc = await db.clients.find_one({"client_id": data.client_id}, {"_id": 0, "legal_name": 1, "fantasy_name": 1})
        if client_doc:
            client_display_name = client_doc.get("fantasy_name") or client_doc.get("legal_name", data.cliente_nombre)

    equipment_items_list = [item.model_dump() for item in data.items]

    quote_doc = {
        "quote_id": quote_id,
        "quote_number": quote_number,
        "client_id": data.client_id,
        "client_name": client_display_name,
        "quote_category": quote_category,
        "quote_type": data.equipment_type,
        "equipment_type": data.equipment_type,
        "equipment_items": equipment_items_list,
        "subtotal_usd": subtotal,
        "total_usd": total,
        "total_bs": 0,
        "exchange_rate": 0,
        "notes": data.notes or "",
        "repair_description": data.repair_description or None,
        "equipment_serial_number": data.equipment_serial_number or None,
        "estimated_delivery_date": data.estimated_delivery_date or None,
        "repair_models": [m.dict() for m in data.repair_models] if data.repair_models else [],
        "quote_status": "Borrador",
        "quote_pdf_url": quote_pdf_url,
        "attachments": [attachment_entry],
        "sede": user_sede,
        "created_by_user_id": current_user.get("user_id"),
        "created_at": now.isoformat(),
        "status_history": [{
            "status": "Borrador",
            "timestamp": now.isoformat(),
            "user": current_user.get("full_name", current_user.get("email", "Sistema"))
        }]
    }
    await db.quotes.insert_one(quote_doc)
    logging.info(f"Cotización de equipo creada: {quote_id} ({quote_number})")

    filename = f"cotizacion_{data.equipment_type.lower().replace(' ', '_')}_{data.cliente_rif or 'cliente'}_{now.strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Quote-Id": quote_id,
            "X-Quote-Number": quote_number
        }
    )



# ==================== CARGA MASIVA DE SERIALES PARA REPARACIONES ====================

@router.post("/quotes/validate-repair-serials")
async def validate_repair_serials(
    file: UploadFile = File(...),
    client_id: str = Form(""),
    authorization: Optional[str] = Header(None)
):
    """Recibe un archivo Excel con seriales, los valida contra el inventario y retorna resultados."""
    await get_current_user(authorization)
    import openpyxl

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato Excel (.xlsx)")

    try:
        contents = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True)
        ws = wb.active

        serials = []
        for row in ws.iter_rows(min_row=1, values_only=True):
            for cell in row:
                if cell is not None:
                    val = str(cell).strip()
                    if val and val.lower() not in ('serial', 'seriales', 'numero de serie', 'número de serie', 'serial number', 'nro', 'n/s'):
                        serials.append(val)

        wb.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer el archivo Excel: {str(e)}")

    if not serials:
        raise HTTPException(status_code=400, detail="No se encontraron seriales en el archivo")

    # Deduplicar preservando orden
    seen = set()
    unique_serials = []
    for s in serials:
        if s not in seen:
            seen.add(s)
            unique_serials.append(s)

    # Buscar en inventory_movements
    all_movements = await db.inventory_movements.find(
        {"serials": {"$in": unique_serials}},
        {"_id": 0, "item_name": 1, "item_type": 1, "warehouse_id": 1, "serials": 1}
    ).to_list(10000)

    # Construir mapa serial -> info
    serial_info = {}
    for m in all_movements:
        for s in m.get("serials", []):
            if s in seen and s not in serial_info:
                serial_info[s] = {
                    "item_name": m.get("item_name", ""),
                    "item_type": m.get("item_type", ""),
                    "warehouse_id": m.get("warehouse_id", "")
                }

    # Enriquecer con nombre del almacén
    wh_ids = list(set(v["warehouse_id"] for v in serial_info.values() if v["warehouse_id"]))
    wh_map = {}
    if wh_ids:
        warehouses = await db.warehouses.find(
            {"warehouse_id": {"$in": wh_ids}}, {"_id": 0, "warehouse_id": 1, "name": 1}
        ).to_list(100)
        wh_map = {w["warehouse_id"]: w["name"] for w in warehouses}

    found = []
    not_found = []
    for s in unique_serials:
        if s in serial_info:
            info = serial_info[s]
            found.append({
                "serial": s,
                "item_name": info["item_name"],
                "item_type": info["item_type"],
                "warehouse": wh_map.get(info["warehouse_id"], info["warehouse_id"])
            })
        else:
            not_found.append({"serial": s})

    return {
        "total_uploaded": len(unique_serials),
        "found": found,
        "not_found": not_found,
        "found_count": len(found),
        "not_found_count": len(not_found)
    }
