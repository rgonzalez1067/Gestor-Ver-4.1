"""Route module: quotes.py"""
# ruff: noqa: F403, F405
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os
import re

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, append_corporate_static_pages, append_quote_static_pages, append_equipment_conditions, stamp_header_footer_on_all_pages, render_email_template
from services.pdf_storage import save_pdf_dual
from services.rif_formatter import format_rif
from models import *
from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import traceback

router = APIRouter()

# ==================== QUOTES ENDPOINTS ====================

async def _resolve_client_segment(client_id: Optional[str], quote_type: str, fallback: str) -> str:
    """El segmento (PyME/Corporativo) lo determina la OPCIÓN DEL MENÚ que elige el
    operador al emitir la cotización (Clientes PyME vs Clientes Corporativos), NO la
    clasificación de la ficha del cliente. Se normaliza estrictamente a 'CORP' o 'PYME'."""
    seg = (fallback or "").strip().upper()
    if seg in ("CORP", "CORPORATIVO", "CORPORATE"):
        return "CORP"
    return "PYME"

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
    elif quote_data.quote_type in ("GATEWAY", "LINK_PAGO") and quote_data.pg_setup_items:
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
    
    # El segmento PyME/Corporativo lo define la opción del menú elegida por el operador.
    qtype = quote_data.quote_type or "VPOS"
    resolved_segment = await _resolve_client_segment(quote_data.client_id, qtype, quote_data.client_segment or user_sede)
    
    quote = Quote(
        quote_number=quote_number,
        client_id=quote_data.client_id,
        quote_category=quote_data.quote_category or "implementation",
        quote_type=quote_data.quote_type or "VPOS",
        link_pago_variant=quote_data.link_pago_variant or "link_pago",
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
        sponsor_processor_id=quote_data.sponsor_processor_id,
        sponsor_processor_name=quote_data.sponsor_processor_name,
        cantidad_cajas=quote_data.cantidad_cajas,
        cantidad_bancos=quote_data.cantidad_bancos,
        pg_setup_items=quote_data.pg_setup_items,
        pg_recurring_cost=quote_data.pg_recurring_cost,
        pg_transaction_range=quote_data.pg_transaction_range,
        sede=user_sede,  # Sede del usuario
        client_segment=resolved_segment,
        created_by_user_id=current_user.get("user_id")  # ID del usuario que crea
    )
    
    doc = quote.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    # Origen inmutable: departamento/cargo del creador AL MOMENTO de crear.
    # La visibilidad por equipo se basa en esto (no en el depto ACTUAL del creador),
    # blindando el histórico ante transferencias de departamento.
    doc['creator_departamento'] = current_user.get('departamento')
    doc['creator_cargo'] = current_user.get('cargo')
    # Token dinámico: abreviaturas concatenadas de medios de pago.
    try:
        from services.medios_pago_abrev import compute_abreviaturas_medios_pago
        doc['abreviaturas_medios_pago'] = await compute_abreviaturas_medios_pago(doc)
    except Exception:
        doc['abreviaturas_medios_pago'] = ""
    await db.quotes.insert_one(doc)
    
    return quote

# Modelo para crear cotización con PDF
class QuoteCreateWithPDF(BaseModel):
    """Modelo combinado para crear cotización y generar PDF"""
    # Datos básicos de la cotización
    client_id: Optional[str] = None
    quote_category: str = "implementation"
    quote_type: str = "VPOS"
    link_pago_variant: str = "link_pago"  # link_pago | tokenizador | ambos (solo LINK_PAGO)
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
    # Patrocinio relacional del Pinpad vía Procesador (Procesador → Banco final)
    sponsor_processor_id: Optional[str] = None
    sponsor_processor_name: Optional[str] = None
    # Implementación Patrocinada (banco que asume el costo de implementación)
    sponsored_implementation: Optional[bool] = False
    sponsoring_bank_id: Optional[str] = None
    sponsoring_bank_name: Optional[str] = None
    # Patrocinio relacional vía Procesador (Procesador → Banco final)
    sponsoring_processor_id: Optional[str] = None
    sponsoring_processor_name: Optional[str] = None
    # Cliente exento de IVA — suprime impuesto en cálculos y facturación
    iva_exempt: Optional[bool] = False
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
    requires_vpn: bool = False
    # Tipo de Comunicación (conectividad): "VPN" | "SSL" | "NO_APLICA".
    communication_type: Optional[str] = None
    # Segmento de cliente. None por defecto: si el consumidor NO lo envía, el
    # backend cae al fallback user_sede (ver L447). Un default 'PYME' truthy
    # rompería ese fallback (era la trampa latente del bug PG/Link de Pago).
    client_segment: Optional[str] = None
    # Detalle de sucursales (opcional, para VPOS/MPOS/Fast Track)
    branch_details: List[dict] = []  # [{store_name: str, quantity: int}]
    # VPOS Multi-RIF
    is_multirif: Optional[bool] = False
    multirif_distribution: Optional[List[dict]] = None
    # Override del total calculado por el wizard del frontend
    override_total_usd: Optional[float] = None

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
        
        # Calcular totales — total_usd = Total Setup Neto + Equipment (excluye recurrentes)
        if data.quote_category == "equipment":
            subtotal_usd = sum(item.total_usd for item in data.equipment_items)
            total_usd = subtotal_usd
        elif data.quote_type in ("GATEWAY", "LINK_PAGO") and data.pg_setup_items:
            subtotal_usd = sum(item.get("costo", 0) for item in data.pg_setup_items)
            total_usd = subtotal_usd
        else:
            all_services_total = sum(item.total_usd for item in data.services) + sum(item.total_usd for item in data.hardware)
            setup_only_total = sum(item.total_usd for item in data.services if item.item_type in ('setup', 'additional')) + sum(item.total_usd for item in data.hardware)
            desc_setup_pct = data.descuento_setup or 0
            monto_desc_setup = setup_only_total * (desc_setup_pct / 100)
            subtotal_usd = all_services_total
            total_usd = setup_only_total - monto_desc_setup
        
        # Sumar hardware Fast Track sincronizado desde Integración
        ft_hw_subtotal = 0
        if data.ft_equipment_items:
            ft_hw_subtotal = sum((it.get("quantity", 1) * it.get("unit_price_usd", 0)) for it in data.ft_equipment_items)
            total_usd += ft_hw_subtotal
        
        # Usar override del frontend si viene (Total Setup Neto + Equipment del wizard)
        if data.override_total_usd is not None:
            total_usd = data.override_total_usd
        
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
                # Asegurar herencia del flag iva_exempt desde la cotización
                pdf_request.iva_exempt = bool(data.iva_exempt)
                # Aislamiento RBAC: garantizar IDs y hidratar nombres desde la BD,
                # de modo que el PDF guardado sea idéntico a Previsualizar/Exportar.
                pdf_request.client_id = pdf_request.client_id or data.client_id
                pdf_request.integrator_id = pdf_request.integrator_id or data.integrator_id
                pdf_request.pinpad_id = pdf_request.pinpad_id or data.pinpad_id
                pdf_request.sponsor_bank_id = pdf_request.sponsor_bank_id or data.sponsor_bank_id
                pdf_request.sponsor_processor_id = pdf_request.sponsor_processor_id or data.sponsor_processor_id
                # VPOS Multi-RIF: propagar flags y distribución para portada/cliente=Banco y página 5.
                pdf_request.is_multirif = bool(getattr(pdf_request, "is_multirif", False) or data.is_multirif)
                if not getattr(pdf_request, "multirif_distribution", None):
                    pdf_request.multirif_distribution = data.multirif_distribution or []
                pdf_request.sponsoring_bank_id = pdf_request.sponsoring_bank_id or data.sponsoring_bank_id
                pdf_request.sponsoring_bank_name = pdf_request.sponsoring_bank_name or data.sponsoring_bank_name
                await hydrate_pdf_request(pdf_request)
                await _enrich_tipo_corp_from_db(pdf_request)
                
                # Obtener logo si existe
                logo_path = None
                logo_file = UPLOADS_DIR / "logo.png"
                if logo_file.exists():
                    logo_path = str(logo_file)
                
                # Crear generador
                generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
                
                # Generar PDF
                pdf_buffer = generator.generate()
                
                # Agregar páginas estáticas/anexos según producto y segmento (PyME/Corporativo).
                # Segmento autoritativo: PG/LP heredan del cliente (no confiar en lo que envíe el
                # frontend, que al "Modificar" puede perder el segmento y degradar a PYME).
                resolved_seg = await _resolve_client_segment(
                    pdf_request.client_id or data.client_id,
                    data.quote_type,
                    pdf_request.client_segment or data.client_segment or "PYME",
                )
                pdf_buffer = append_quote_static_pages(pdf_buffer, data.quote_type, resolved_seg)
                
                # Estampar header/footer en TODAS las páginas (incluyendo anexos inyectados)
                pdf_buffer = stamp_header_footer_on_all_pages(pdf_buffer, quote_number, logo_path)
                
                # Guardar PDF en el servidor + Object Storage (persistente entre deploys)
                pdf_filename = f"{quote_number}_Cotizacion.pdf"
                pdf_path = UPLOADS_DIR / pdf_filename
                final_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer.read()
                save_pdf_dual(pdf_path, final_bytes, pdf_filename)
                
                quote_pdf_url = f"/uploads/{pdf_filename}"
                logging.info(f"PDF generado y almacenado: {quote_pdf_url}")
                
            except Exception as e:
                logging.error(f"Error generando PDF: {str(e)}")
                # Continuar sin PDF si falla la generación
        elif data.quote_type in ("GATEWAY", "LINK_PAGO") and data.pg_setup_items:
            # Generar PDF para Payment Gateway / Link de Pago usando DynamicQuotePDFGenerator
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
                        quote_type=data.quote_type or "GATEWAY",
                        link_pago_variant=data.link_pago_variant or "link_pago",
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
                        iva_exempt=bool(data.iva_exempt),
                    )
                    
                    logo_path = None
                    logo_file = UPLOADS_DIR / "logo.png"
                    if logo_file.exists():
                        logo_path = str(logo_file)
                    
                    generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
                    pdf_buffer = generator.generate()
                    # Segmento PyME/Corporativo: resolver y aplicar el anexo correspondiente
                    resolved_seg = await _resolve_client_segment(data.client_id, data.quote_type or "GATEWAY", data.client_segment or "PYME")
                    pdf_buffer = append_quote_static_pages(pdf_buffer, data.quote_type or "GATEWAY", resolved_seg)
                    
                    # Estampar header/footer en TODAS las páginas
                    pdf_buffer = stamp_header_footer_on_all_pages(pdf_buffer, quote_number, logo_path)
                    
                    pdf_filename = f"{quote_number}_Cotizacion.pdf"
                    pdf_path = UPLOADS_DIR / pdf_filename
                    final_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer.read()
                    save_pdf_dual(pdf_path, final_bytes, pdf_filename)
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
        client_doc = await db.clients.find_one({"client_id": data.client_id}, {"_id": 0, "legal_name": 1, "fantasy_name": 1}) if data.client_id else None
        client_display_name = (client_doc.get("fantasy_name") or client_doc.get("legal_name", "")) if client_doc else ""
        # VPOS Multi-RIF: no hay un cliente único; el sujeto es el lote del banco.
        if data.is_multirif and not client_display_name:
            client_display_name = f"Lote {data.sponsoring_bank_name or data.sponsor_bank_name or 'Banco'} (Multi-RIF)"
        
        # Crear la cotización
        quote = Quote(
            quote_id=quote_id,
            quote_number=quote_number,
            client_id=data.client_id or "",
            client_name=client_display_name,
            quote_category=data.quote_category or "implementation",
            quote_type=data.quote_type or "VPOS",
            link_pago_variant=data.link_pago_variant or "link_pago",
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
            sponsor_processor_id=data.sponsor_processor_id,
            sponsor_processor_name=data.sponsor_processor_name,
            sponsored_implementation=bool(data.sponsored_implementation),
            sponsoring_bank_id=data.sponsoring_bank_id if data.sponsored_implementation else None,
            sponsoring_bank_name=data.sponsoring_bank_name if data.sponsored_implementation else None,
            sponsoring_processor_id=data.sponsoring_processor_id if data.sponsored_implementation else None,
            sponsoring_processor_name=data.sponsoring_processor_name if data.sponsored_implementation else None,
            iva_exempt=bool(data.iva_exempt),
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
            is_multirif=bool(data.is_multirif),
            multirif_distribution=data.multirif_distribution,
            requires_pinpad_config=data.requires_pinpad_config,
            requires_vpn=data.requires_vpn,
            communication_type=data.communication_type,
            sede=user_sede,
            client_segment=await _resolve_client_segment(data.client_id, data.quote_type or "VPOS", data.client_segment or user_sede),
            created_by_user_id=current_user.get("user_id"),
            quote_pdf_url=quote_pdf_url,
            attachments=initial_attachments
        )
        
        doc = quote.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        # Origen inmutable del creador (ver create_quote)
        doc['creator_departamento'] = current_user.get('departamento')
        doc['creator_cargo'] = current_user.get('cargo')
        try:
            from services.medios_pago_abrev import compute_abreviaturas_medios_pago
            doc['abreviaturas_medios_pago'] = await compute_abreviaturas_medios_pago(doc)
        except Exception:
            doc['abreviaturas_medios_pago'] = ""
        await db.quotes.insert_one(doc)
        
        return {
            "quote": quote,
            "pdf_url": quote_pdf_url,
            "message": "Cotización creada exitosamente" + (" con PDF" if quote_pdf_url else "")
        }
        
    except Exception as e:
        import traceback
        logging.error(f"Error creando cotización con PDF: {str(e)}\n{traceback.format_exc()}")
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


def _dept_visibility_or(dept_name, member_ids, self_id):
    """Ramas $or para visibilidad colaborativa por departamento.
    Se basa en el ORIGEN INMUTABLE `creator_departamento` (blindado ante
    transferencias del creador), con fallback a los miembros ACTUALES del
    depto para históricos sin el campo, y siempre las propias del usuario."""
    branches = [
        {"creator_departamento": {"$regex": f"^{re.escape(dept_name)}$", "$options": "i"}},
    ]
    if member_ids:
        branches.append({"created_by_user_id": {"$in": member_ids}})
    if self_id:
        branches.append({"created_by_user_id": self_id})
    return branches


async def backfill_quote_origin():
    """Snapshot inmutable del departamento/cargo del creador para cotizaciones
    que aún no lo tienen (`creator_departamento`). Idempotente y guardado por
    flag en `config`. Se ejecuta en el startup para blindar el histórico ante
    futuras transferencias de departamento."""
    flag = await db.config.find_one({"type": "quote_origin_backfilled"}, {"_id": 0})
    if flag and flag.get("value") is True:
        return
    users = await db.users.find({}, {"_id": 0, "user_id": 1, "departamento": 1, "cargo": 1}).to_list(5000)
    umap = {u["user_id"]: u for u in users if u.get("user_id")}
    updated = 0
    cursor = db.quotes.find(
        {"creator_departamento": {"$exists": False}},
        {"_id": 0, "quote_id": 1, "created_by_user_id": 1}
    )
    async for q in cursor:
        u = umap.get(q.get("created_by_user_id"))
        if not u:
            continue
        await db.quotes.update_one(
            {"quote_id": q["quote_id"]},
            {"$set": {"creator_departamento": u.get("departamento"), "creator_cargo": u.get("cargo")}}
        )
        updated += 1
    await db.config.update_one(
        {"type": "quote_origin_backfilled"},
        {"$set": {"type": "quote_origin_backfilled", "value": True, "updated": updated}},
        upsert=True,
    )
    logging.info(f"[startup] quote origin backfilled: {updated}")


@router.get("/quotes", response_model=List[Quote])
async def get_quotes(authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)

    # Construir filtro jerárquico basado en cargo del usuario
    query = {"archived": {"$ne": True}}  # Excluir cotizaciones archivadas en Histórico
    user_sede = current_user.get("sede", "PYME")
    cargo = (current_user.get("cargo") or "").lower()
    user_depto = current_user.get("departamento", "")
    depto_norm = (user_depto or "").strip().lower()
    # Detectado a nivel raíz para que la unión de alcance Operaciones (más
    # abajo, post-construcción del query) tenga acceso a la flag incluso
    # cuando el usuario sea admin (no aplica) o pase por otras ramas.
    is_ops_dept = "operaciones" in depto_norm

    if current_user.get("role") != "admin":
        user_id = current_user.get("user_id")
        # Special permissions efectivos: union(perfil, usuario)
        sp = list(current_user.get("special_permissions") or [])
        if current_user.get("profile_id"):
            prof = await db.profiles.find_one({"profile_id": current_user["profile_id"]}, {"_id": 0, "special_permissions": 1})
            for p in (prof or {}).get("special_permissions") or []:
                if p not in sp:
                    sp.append(p)
        # Si el usuario tiene perfil con permisos de cotizaciones, el alcance de lectura
        # lo define el perfil — ignoramos el filtro jerárquico legacy por cargo.
        # El frontend (useQuoteRbac) ya filtra por categoría según los special_permissions.
        has_profile_quote_perms = bool(current_user.get("profile_id")) and any(
            (p or "").startswith("cotizaciones:") for p in sp
        )

        # Normalizar departamento para detectar "Administración"
        is_admin_dept = "administración" in depto_norm or "administracion" in depto_norm

        if "director" in cargo:
            # Director (cualquier sede/depto): visibilidad total, sin filtros.
            pass
        elif "ventas corporativ" in depto_norm:
            # ===== REGLA DE EQUIPO: Ventas Corporativas (colaborativa) =====
            # Visibilidad por ORIGEN INMUTABLE: toda cotización cuyo creador
            # pertenecía a Ventas Corporativas AL CREARLA sigue visible para el
            # equipo, aunque el creador haya sido transferido después. Fallback a
            # miembros actuales para históricos sin `creator_departamento`.
            team = await db.users.find(
                {"departamento": {"$regex": "ventas corporativ", "$options": "i"},
                 "is_active": {"$ne": False}},
                {"_id": 0, "user_id": 1}
            ).to_list(500)
            team_ids = [u["user_id"] for u in team] or [user_id]
            if user_id and user_id not in team_ids:
                team_ids.append(user_id)
            query["$or"] = [
                {"creator_departamento": {"$regex": "ventas corporativ", "$options": "i"}},
                {"created_by_user_id": {"$in": team_ids}},
            ]
        elif is_admin_dept:
            # Administración: visibilidad por SEDE (PYME/CORP/TBP) sin importar
            # qué usuario creó la cotización. Permite que todo el equipo de
            # Administración de una misma sede vea las cotizaciones de esa sede
            # para procesos de facturación, cobranza y auditoría.
            query["client_segment"] = user_sede
        elif has_profile_quote_perms:
            # Perfiles RBAC custom: visibilidad departamental (colaborativa).
            query["client_segment"] = user_sede
            if user_depto:
                dept_users = await db.users.find(
                    {"departamento": user_depto, "is_active": {"$ne": False}},
                    {"_id": 0, "user_id": 1}
                ).to_list(500)
                dept_user_ids = [u["user_id"] for u in dept_users] or [user_id]
                if user_id and user_id not in dept_user_ids:
                    dept_user_ids.append(user_id)
                query["$or"] = _dept_visibility_or(user_depto, dept_user_ids, user_id)
            else:
                query["created_by_user_id"] = user_id
        elif "gerente" in cargo:
            # Gerente de Ventas: ve todo su departamento (por origen inmutable) + filtro por segmento
            query["client_segment"] = user_sede
            if user_depto:
                dept_users = await db.users.find(
                    {"departamento": user_depto, "is_active": {"$ne": False}},
                    {"_id": 0, "user_id": 1}
                ).to_list(500)
                dept_user_ids = [u["user_id"] for u in dept_users]
                query["$or"] = _dept_visibility_or(user_depto, dept_user_ids, user_id)
            else:
                query["created_by_user_id"] = user_id
        elif "coordinador" in cargo:
            # Coordinador: ve sus cotizaciones + las de Ejecutivos de su departamento
            # (por origen inmutable creator_departamento + creator_cargo), filtrado por segmento.
            query["client_segment"] = user_sede
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
                query["$or"] = [
                    {"creator_departamento": {"$regex": f"^{re.escape(user_depto)}$", "$options": "i"},
                     "creator_cargo": {"$regex": "ejecutivo", "$options": "i"}},
                    {"created_by_user_id": {"$in": team_user_ids}},
                    {"created_by_user_id": user_id},
                ]
            else:
                query["created_by_user_id"] = user_id
        else:
            # Ejecutivo u otro cargo sin jerarquía: cotizaciones de su mismo
            # departamento de ORIGEN (privacidad colaborativa por unidad de negocio).
            query["client_segment"] = user_sede
            if user_depto:
                dept_users = await db.users.find(
                    {"departamento": user_depto, "is_active": {"$ne": False}},
                    {"_id": 0, "user_id": 1}
                ).to_list(500)
                dept_user_ids = [u["user_id"] for u in dept_users] or [user_id]
                if user_id and user_id not in dept_user_ids:
                    dept_user_ids.append(user_id)
                query["$or"] = _dept_visibility_or(user_depto, dept_user_ids, user_id)
            else:
                # Usuario sin departamento asignado → solo ve sus propias cotizaciones
                query["created_by_user_id"] = user_id

    # ========= AMPLIACIÓN DE ALCANCE: Departamento OPERACIONES =========
    # Feb 2026 — Operaciones es un departamento de SOPORTE TRANSVERSAL:
    # coordina Reparaciones, Ventas de Equipos/Accesorios y la fase técnica
    # de MPOS (Imple+POS) sin generar ventas propiamente. Por eso necesita
    # LECTURA UNIVERSAL sobre estas categorías independientemente del
    # creador de la cotización (clave porque mucho del histórico fue
    # importado y tiene `created_by_user_id` sintéticos que no matchean con
    # usuarios actuales — orphan IDs).
    #
    # Categorías con acceso ABIERTO para Operaciones (lectura):
    #   - `repair` (Reparaciones) — coordinación de servicio técnico.
    #   - `equipment` (Equipos / Accesorios) — entregas y configuración.
    #   - `fast_track` (MPOS Imple + POS) — fase técnica, sólo PYME.
    #
    # El frontend restringe acciones (solo Configuración para MPOS, etc.).
    if is_ops_dept and "director" not in cargo:
        # Capturamos el scope departamental previo (created_by + sede).
        scope_keys = ("created_by_user_id", "client_segment")
        ops_dept_scope = {k: query.pop(k) for k in scope_keys if k in query}

        # Lectura universal por categoría
        ops_repair_scope = {"quote_category": "repair"}
        ops_equipment_scope = {"quote_category": "equipment"}
        ops_mpos_scope = {
            "client_segment": "PYME",
            "$or": [
                {"quote_category": "fast_track"},
                {"quote_type": "FAST_TRACK"},
            ],
        }

        or_branches = []
        if ops_dept_scope:
            # Conserva acceso a sus propias cotizaciones (incluido implementation
            # PYME/CORP creadas por algún Ops user, si las hubiera).
            if "$or" in query:
                ops_dept_scope["$or"] = query.pop("$or")
            or_branches.append(ops_dept_scope)
        or_branches.extend([ops_repair_scope, ops_equipment_scope, ops_mpos_scope])
        query["$or"] = or_branches

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
    
    # Resolver nombres de creadores
    creator_ids = set(q.get('created_by_user_id') for q in quotes if q.get('created_by_user_id'))
    if creator_ids:
        creator_map = {}
        async for u in db.users.find({"user_id": {"$in": list(creator_ids)}}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1}):
            fn = u.get("first_name", "")
            ln = u.get("last_name", "")
            full = f"{fn} {ln}".strip()
            initials = (fn[:1] + ln[:1]).upper() if fn and ln else (fn[:2] or ln[:2] or "??").upper()
            creator_map[u["user_id"]] = {"name": full, "initials": initials}
        for quote in quotes:
            uid = quote.get("created_by_user_id")
            info = creator_map.get(uid, {})
            quote["creator_name"] = info.get("name", "")
            quote["creator_initials"] = info.get("initials", "")
    
    return quotes

@router.get("/quotes/{quote_id}", response_model=Quote)
async def get_quote(quote_id: str, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    # Validación de privacidad (consistente con GET /quotes lista).
    # - Admin y Director: bypass total.
    # - Administración (depto): solo cotizaciones cuyo client_segment coincida con su sede.
    # - Resto: solo si created_by_user_id pertenece al mismo departamento (o es el propio creador).
    role = (current_user.get("role") or "").lower()
    cargo = (current_user.get("cargo") or "").lower()
    user_depto = (current_user.get("departamento") or "")
    depto_norm = user_depto.strip().lower()
    is_admin_dept = "administración" in depto_norm or "administracion" in depto_norm
    user_sede = (current_user.get("sede") or "").upper()

    if role != "admin" and "director" not in cargo:
        if is_admin_dept:
            # Administración: bloqueo por sede
            if (quote.get("client_segment") or "").upper() != user_sede:
                raise HTTPException(status_code=403, detail="No tiene acceso a esta cotización (restricción de sede para Administración)")
        elif "ventas corporativ" in depto_norm:
            # Equipo de Ventas Corporativas: acceso por ORIGEN INMUTABLE del
            # creador (consistente con la lista). Fallback al depto actual del
            # creador solo si la cotización no tiene `creator_departamento`.
            creator_id = quote.get("created_by_user_id")
            if creator_id and creator_id != current_user.get("user_id"):
                origin = (quote.get("creator_departamento") or "")
                if not origin:
                    creator = await db.users.find_one({"user_id": creator_id}, {"_id": 0, "departamento": 1})
                    origin = ((creator or {}).get("departamento") or "")
                if "ventas corporativ" not in origin.lower():
                    raise HTTPException(status_code=403, detail="No tiene acceso a esta cotización (privacidad por departamento)")
        else:
            creator_id = quote.get("created_by_user_id")
            if creator_id and creator_id != current_user.get("user_id"):
                origin = quote.get("creator_departamento")
                if not origin:
                    creator = await db.users.find_one({"user_id": creator_id}, {"_id": 0, "departamento": 1})
                    origin = (creator or {}).get("departamento") or ""
                if not user_depto or user_depto.strip().lower() != (origin or "").strip().lower():
                    raise HTTPException(status_code=403, detail="No tiene acceso a esta cotización (privacidad por departamento)")
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
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=90, bottomMargin=60)
    elements = []
    styles = getSampleStyleSheet()
    
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "logo.png")
    
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
    
    # Estampar header/footer en todas las páginas
    stamped = stamp_header_footer_on_all_pages(buffer, quote['quote_number'], logo_path)
    
    return Response(
        content=stamped.getvalue() if hasattr(stamped, 'getvalue') else stamped.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=quote_{quote['quote_number']}.pdf"}
    )

class QuoteUpdate(BaseModel):
    """Modelo para actualizar cotización existente"""
    quote_type: Optional[str] = None
    link_pago_variant: Optional[str] = None
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
    # Patrocinio relacional del Pinpad vía Procesador (Procesador → Banco final)
    sponsor_processor_id: Optional[str] = None
    sponsor_processor_name: Optional[str] = None
    # Implementación Patrocinada
    sponsored_implementation: Optional[bool] = None
    sponsoring_bank_id: Optional[str] = None
    sponsoring_bank_name: Optional[str] = None
    sponsoring_processor_id: Optional[str] = None
    sponsoring_processor_name: Optional[str] = None
    # Cliente exento de IVA
    iva_exempt: Optional[bool] = None
    subtotal_usd: Optional[float] = None
    total_usd: Optional[float] = None
    recurring_total_usd: Optional[float] = None
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
    # Fast Track hardware
    ft_equipment_items: Optional[List[dict]] = None
    ft_hardware_subtotal: Optional[float] = None
    requires_pinpad_config: Optional[bool] = None
    requires_vpn: Optional[bool] = None
    communication_type: Optional[str] = None
    # Equipment/Repair items
    equipment_items: Optional[List[dict]] = None
    repair_description: Optional[str] = None
    equipment_serial_number: Optional[str] = None
    # Segmento PyME/Corporativo — debe transportarse en el flujo "Modificar"
    # (duplicar+PUT) para que una cotización CORP no se degrade a PYME.
    client_segment: Optional[str] = None

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

    # Normalizar segmento si viene en el update (evita degradación a PYME por
    # variantes 'Corporativo'/'Corp' y garantiza que CORP se conserve).
    if update_data.get("client_segment"):
        seg = str(update_data["client_segment"]).strip().upper()
        update_data["client_segment"] = "CORP" if seg in ("CORP", "CORPORATIVO", "CORPORATE") else "PYME"
    else:
        # Nunca escribir un client_segment vacío: preservar el existente.
        update_data.pop("client_segment", None)
    
    # Calcular total_bs si se actualizó total_usd
    if "total_usd" in update_data:
        exchange_rate = update_data.get("exchange_rate", existing_quote.get("exchange_rate", 36.5))
        update_data["total_bs"] = update_data["total_usd"] * exchange_rate
    
    if update_data:
        # Recalcular abreviaturas_medios_pago si cambian los services/additional
        try:
            services_changed = any(k in update_data for k in ("services", "additional_items"))
            if services_changed:
                from services.medios_pago_abrev import compute_abreviaturas_medios_pago
                merged = {**existing_quote, **update_data}
                update_data["abreviaturas_medios_pago"] = await compute_abreviaturas_medios_pago(merged)
        except Exception:
            pass
        result = await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Retornar cotización actualizada
    updated_quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    return updated_quote


@router.post("/quotes/{quote_id}/regenerate-pdf")
async def regenerate_quote_pdf(quote_id: str, data: dict = {}, authorization: Optional[str] = Header(None)):
    """Regenera el PDF de una cotización desde sus datos almacenados, lo guarda en disco y lo registra en los anexos."""
    current_user = await get_current_user(authorization)
    
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    try:
        # Obtener datos del cliente
        client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
        quote_number = quote["quote_number"]
        quote_type = quote.get("quote_type", "VPOS")
        # Segmento autoritativo: usar el almacenado; si falta, derivar de la sede
        # de la cotización (evita degradar CORP→PYME al regenerar el PDF).
        _seg_raw = (quote.get("client_segment") or quote.get("sede") or "").strip().upper()
        client_segment = "CORP" if _seg_raw in ("CORP", "CORPORATIVO", "CORPORATE") else "PYME"
        services = quote.get("services", [])
        
        # Reconstruir items por tipo desde los servicios almacenados
        setup_items = []
        recurring_basic_items = []
        recurring_other_items = []
        additional_items = []
        production_items = []
        
        for svc in services:
            item_type = svc.get("item_type", "setup")
            pdf_item = {
                "concepto": svc.get("item_name", ""),
                "cantidad_cajas": svc.get("cantidad_cajas", 1),
                "cantidad_bancos": svc.get("cantidad_bancos", 1),
                "tarifa": svc.get("unit_price_usd", 0),
                "bank_name": svc.get("bank_name") or None,
                "tipo_corp": svc.get("tipo_corp", "")
            }
            if item_type == "setup":
                setup_items.append(pdf_item)
            elif item_type == "recurring_basic":
                recurring_basic_items.append(pdf_item)
            elif item_type == "recurring_other":
                recurring_other_items.append(pdf_item)
            elif item_type == "additional":
                # Additional items go to BOTH setup_items (for cost table) AND additional_items (for bank/product matrix)
                setup_items.append({
                    "concepto": f"{svc.get('item_name', '')} - {svc.get('bank_name', '')}".strip(' -'),
                    "cantidad_cajas": svc.get("cantidad_cajas", 1),
                    "cantidad_bancos": svc.get("cantidad_bancos", 1),
                    "tarifa": svc.get("tarifa_setup") or svc.get("unit_price_usd", 0),
                    "bank_name": svc.get("bank_name") or None,
                    "tipo_corp": svc.get("tipo_corp", "")
                })
                # Also add to additional_items for the Resumen Ejecutivo bank/product table
                additional_items.append({
                    "concepto": svc.get("item_name", ""),
                    "cantidad_cajas": svc.get("cantidad_cajas", 1),
                    "cantidad_bancos": svc.get("cantidad_bancos", 1),
                    "tarifa": svc.get("tarifa_setup") or svc.get("unit_price_usd", 0),
                    "bank_name": svc.get("bank_name") or None,
                    "tipo_corp": svc.get("tipo_corp", "")
                })
            elif item_type == "production_recurring":
                production_items.append(pdf_item)
        
        # Obtener contacto del cliente
        contacts = client.get("contacts", [])
        contact_name = contacts[0].get("name", "") if contacts else ""
        
        # Construir TemplateQuotePDFRequest desde datos almacenados
        pdf_request = TemplateQuotePDFRequest(
            cliente_nombre=client.get("legal_name") or client.get("fantasy_name") or "",
            cliente_rif=client.get("rif") or "",
            cliente_contacto=contact_name or "",
            cliente_address=client.get("address") or "",
            quote_type=quote_type,
            link_pago_variant=quote.get("link_pago_variant") or "link_pago",
            pricing_model=quote.get("pricing_model") or "conventional",
            cantidad_cajas=quote.get("cantidad_cajas") or 1,
            quote_number=quote_number,
            integrator_name=quote.get("integrator_name") or "",
            integrator_app_name=quote.get("integrator_app_name") or "",
            pinpad_model=quote.get("pinpad_model") or "",
            sponsor_bank_name=quote.get("sponsor_bank_name") or "",
            template_type="payment_gateway" if quote_type in ("GATEWAY", "LINK_PAGO") else "vpos_pyme",
            client_segment=client_segment,
            setup_items=setup_items,
            recurring_basic_items=recurring_basic_items,
            recurring_other_items=recurring_other_items,
            additional_items=additional_items,
            production_items=production_items,
            descuento=quote.get("descuento", 0),
            descuento_setup=quote.get("descuento_setup", 0),
            descuento_recurrente=quote.get("descuento_recurrente", 0),
            requires_pinpad_config=quote.get("requires_pinpad_config", True),
            requires_vpn=quote.get("requires_vpn", False),
            notes=quote.get("notes") or "",
            is_production_client=quote.get("is_production_client", False),
            pg_setup_items=quote.get("pg_setup_items") or [],
            pg_recurring_cost=quote.get("pg_recurring_cost"),
            ft_equipment_items=[
                {"name": it.get("name", ""), "hardware_type": it.get("hardware_type", "POS"),
                 "quantity": it.get("quantity", 1), "unit_price_usd": it.get("unit_price_usd", 0)}
                for it in (quote.get("ft_equipment_items") or [])
            ],
            branch_details=quote.get("branch_details") or [],
            include_recurring=quote.get("include_recurring", True),
            iva_exempt=bool(quote.get("iva_exempt", False)),
        )
        
        # Enriquecer tipo_corp
        await _enrich_tipo_corp_from_db(pdf_request)
        
        logo_path = None
        logo_file = UPLOADS_DIR / "logo.png"
        if logo_file.exists():
            logo_path = str(logo_file)
        
        generator = DynamicQuotePDFGenerator(pdf_request, logo_path)
        pdf_buffer = generator.generate()
        
        # Agregar páginas estáticas/anexos según producto y segmento (PyME/Corporativo)
        pdf_buffer = append_quote_static_pages(pdf_buffer, quote_type, client_segment)
        
        # Estampar header/footer
        pdf_buffer = stamp_header_footer_on_all_pages(pdf_buffer, quote_number, logo_path)
        
        # Guardar PDF en disco + Object Storage
        pdf_filename = f"{quote_number}_Cotizacion.pdf"
        pdf_path = UPLOADS_DIR / pdf_filename
        pdf_bytes = pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer.read()
        save_pdf_dual(pdf_path, pdf_bytes, pdf_filename)
        
        quote_pdf_url = f"/uploads/{pdf_filename}"
        
        # Crear registro de anexo
        new_attachment = {
            "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
            "category": "Cotización",
            "filename": pdf_filename,
            "url": quote_pdf_url,
            "uploaded_by": current_user.get("email", "system"),
            "uploaded_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "file_size": len(pdf_bytes),
            "content_type": "application/pdf"
        }
        
        # Actualizar cotización: remover attachment de Cotización viejo, agregar nuevo
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$pull": {"attachments": {"category": "Cotización"}}}
        )
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {
                "$set": {"quote_pdf_url": quote_pdf_url},
                "$push": {"attachments": new_attachment}
            }
        )
        
        logging.info(f"PDF regenerado para {quote_number}: {quote_pdf_url}")
        return {"pdf_url": quote_pdf_url, "attachment": new_attachment}
        
    except Exception as e:
        logging.error(f"Error regenerando PDF: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al regenerar PDF: {str(e)}")



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
        'VPOS': 'VPOS (Cajas)',
        'FAST_TRACK': 'POS Stand Alone (Fast Track)',
        'VPOS_MPOS': 'VPOS/MPOS',
        'GATEWAY': 'Payment Gateway',
        'MPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'LINK': 'Link de Pago',
        'LINK_PAGO': 'Link de Pago'
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
        _pp_proc = (getattr(data, "sponsor_processor_name", "") or "").strip()
        _pp_label = f"{_pp_proc} - {data.sponsor_bank_name}" if _pp_proc else data.sponsor_bank_name
        info_data.append(["Entidad Patrocinadora:", _pp_label])
    
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
    
    # Incluir costo de equipos Fast Track en resumen
    ft_equip_total = 0
    if data.quote_type == 'FAST_TRACK' and data.ft_equipment_items:
        ft_equip_total = sum(
            (item.get("quantity", 1) * item.get("unit_price_usd", 0))
            for item in data.ft_equipment_items
        )
    
    total_general = total_setup + total_recurrente + ft_equip_total
    
    summary_rows = [
        ["Concepto", "Subtotal", "Descuento", "Total Neto"],
        ["Inversión Inicial (Setup)", f"${subtotal_setup:.2f}", f"-${descuento_setup:.2f} ({desc_setup_pct}%)", f"${total_setup:.2f}"],
        ["Costos Recurrentes (Mensual)", f"${subtotal_recurrente:.2f}", f"-${descuento_recurrente:.2f} ({desc_recurrente_pct}%)", f"${total_recurrente:.2f}"],
    ]
    if ft_equip_total > 0:
        summary_rows.append(["Equipos (Hardware)", f"${ft_equip_total:.2f}", "-$0.00 (0%)", f"${ft_equip_total:.2f}"])
    summary_rows.append(["", "", "TOTAL GENERAL:", f"${total_general:.2f}"])
    
    summary_data = summary_rows
    
    summary_table = Table(summary_data, colWidths=[2.5*inch, 1.3*inch, 1.3*inch, 1.3*inch])
    total_row_idx = len(summary_data) - 1
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
        ('FONTNAME', (2, total_row_idx), (-1, total_row_idx), 'Helvetica-Bold'),
        ('FONTSIZE', (2, total_row_idx), (-1, total_row_idx), 11),
        ('BACKGROUND', (2, total_row_idx), (-1, total_row_idx), colors.Color(0.1, 0.4, 0.7)),
        ('TEXTCOLOR', (2, total_row_idx), (-1, total_row_idx), colors.whitesmoke),
    ]))
    elements.append(summary_table)
    
    # ==================== PÁGINA DE COTIZACIÓN DE EQUIPOS (Fast Track) ====================
    if data.quote_type == 'FAST_TRACK' and data.ft_equipment_items:
        elements.append(PageBreak())
        elements.append(Paragraph("<b>COTIZACIÓN DE EQUIPOS</b>", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(
            f"Detalle de hardware incluido en la cotización <b>{data.quote_number or ''}</b> para <b>{data.cliente_nombre}</b>.",
            styles['Normal']
        ))
        elements.append(Spacer(1, 0.15*inch))
        
        # Tabla de equipos
        equip_header = ["N°", "Equipo", "Tipo", "Cantidad", "P. Unit. (USD)", "Total (USD)"]
        equip_rows = [equip_header]
        equip_subtotal = 0
        for idx, item in enumerate(data.ft_equipment_items, 1):
            qty = item.get("quantity", 1)
            price = item.get("unit_price_usd", 0)
            total_item = qty * price
            equip_subtotal += total_item
            equip_rows.append([
                str(idx),
                item.get("name", "N/A"),
                item.get("hardware_type", "POS"),
                str(qty),
                f"${price:,.2f}",
                f"${total_item:,.2f}"
            ])
        
        # IVA y Total (cero si cliente exento)
        _ft_iva_rate = 0.0 if getattr(data, "iva_exempt", False) else 0.16
        iva_amount = equip_subtotal * _ft_iva_rate
        equip_total_con_iva = equip_subtotal + iva_amount
        _ft_iva_label = "IVA (Exento):" if getattr(data, "iva_exempt", False) else f"IVA ({int(_ft_iva_rate*100)}%):"
        
        equip_rows.append(["", "", "", "", "Subtotal:", f"${equip_subtotal:,.2f}"])
        equip_rows.append(["", "", "", "", _ft_iva_label, f"${iva_amount:,.2f}"])
        equip_rows.append(["", "", "", "", "TOTAL:", f"${equip_total_con_iva:,.2f}"])
        
        equip_table = Table(equip_rows, colWidths=[0.4*inch, 2.2*inch, 0.9*inch, 0.8*inch, 1.2*inch, 1.2*inch])
        num_items = len(data.ft_equipment_items)
        equip_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#00447C")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, num_items), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, num_items), [colors.white, colors.Color(0.95, 0.95, 0.97)]),
            # Subtotal row
            ('FONTNAME', (4, num_items+1), (-1, num_items+1), 'Helvetica-Bold'),
            ('LINEABOVE', (4, num_items+1), (-1, num_items+1), 1, colors.grey),
            # IVA row
            ('FONTNAME', (4, num_items+2), (-1, num_items+2), 'Helvetica'),
            # Total row
            ('FONTNAME', (4, num_items+3), (-1, num_items+3), 'Helvetica-Bold'),
            ('FONTSIZE', (4, num_items+3), (-1, num_items+3), 11),
            ('BACKGROUND', (4, num_items+3), (-1, num_items+3), colors.HexColor("#00447C")),
            ('TEXTCOLOR', (4, num_items+3), (-1, num_items+3), colors.whitesmoke),
        ]))
        elements.append(equip_table)
        
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(
            "<i>Los precios de equipos están sujetos a disponibilidad de inventario. "
            "IVA calculado según la normativa fiscal vigente.</i>",
            ParagraphStyle('EquipNote', fontSize=8, textColor=colors.grey)
        ))
    
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

async def hydrate_pdf_request(data: TemplateQuotePDFRequest):
    """Aísla la generación de PDF de la sesión/RBAC del usuario.

    Si el request trae IDs, resuelve los nombres AUTORITATIVOS desde Mongo
    (clients, integrators, hardware, banks) y los sobrescribe. Esto garantiza que
    Previsualizar / Exportar / Guardar produzcan EXACTAMENTE el mismo documento
    sin importar qué catálogos tenga cargados el frontend del usuario (un usuario
    con permisos limitados antes generaba PDFs con campos en blanco).

    Se aplica a TODOS los modelos (VPOS, MPOS, Payment Gateway, Link de Pago).
    """
    # --- Cliente ---
    if getattr(data, "client_id", None):
        client = await db.clients.find_one({"client_id": data.client_id}, {"_id": 0})
        if client:
            data.cliente_nombre = client.get("legal_name") or client.get("fantasy_name") or data.cliente_nombre
            data.cliente_rif = client.get("rif") or data.cliente_rif
            data.cliente_address = client.get("address") or data.cliente_address
            contacts = client.get("contacts") or []
            if contacts:
                c0 = contacts[0] or {}
                contact_name = c0.get("full_name") or c0.get("name") or ""
                if contact_name:
                    data.cliente_contacto = contact_name

    # --- VPOS Multi-RIF: el "cliente" es el Banco de adquirencia ---
    if getattr(data, "is_multirif", False):
        bank = None
        if getattr(data, "sponsoring_bank_id", None):
            bank = await db.banks.find_one({"bank_id": data.sponsoring_bank_id}, {"_id": 0, "name": 1, "rif": 1})
        bank_name = (bank.get("name") if bank else None) or data.sponsoring_bank_name or data.cliente_nombre or "Banco"
        data.cliente_nombre = bank_name
        data.cliente_rif = (bank.get("rif") if bank else None) or ""
        data.cliente_contacto = ""
        data.cliente_address = ""

    # --- Integrador ---
    if getattr(data, "integrator_id", None):
        if data.integrator_id == "sin_integrador":
            data.integrator_name = data.integrator_name or "Sin integrador por el momento"
        else:
            integ = await db.integrators.find_one(
                {"integrator_id": data.integrator_id}, {"_id": 0, "name": 1}
            )
            if integ and integ.get("name"):
                data.integrator_name = integ["name"]

    # --- Pinpad / Hardware (VPOS/MPOS y POS de Fast Track viven en `hardware`) ---
    if getattr(data, "pinpad_id", None) and data.pinpad_id not in ("none", ""):
        hw = await db.hardware.find_one({"hardware_id": data.pinpad_id}, {"_id": 0, "name": 1})
        if hw and hw.get("name"):
            data.pinpad_model = hw["name"]

    # --- Banco patrocinante ---
    if getattr(data, "sponsor_bank_id", None):
        bank = await db.banks.find_one({"bank_id": data.sponsor_bank_id}, {"_id": 0, "name": 1})
        if bank and bank.get("name"):
            data.sponsor_bank_name = bank["name"]

    return data



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
        # Aislamiento RBAC: hidratar nombres desde la BD usando los IDs
        await hydrate_pdf_request(data)
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
        
        # Agregar páginas estáticas/anexos según producto y segmento (PyME/Corporativo).
        # Segmento autoritativo desde la selección del operador (igual que Previsualizar/Guardar).
        resolved_seg = await _resolve_client_segment(data.client_id, data.quote_type, data.client_segment or "PYME")
        pdf_buffer = append_quote_static_pages(pdf_buffer, data.quote_type, resolved_seg)
        
        # Estampar header/footer en TODAS las páginas
        pdf_buffer = stamp_header_footer_on_all_pages(pdf_buffer, data.quote_number or '', logo_path)
        
        # Nombre del archivo
        filename = f"cotizacion_{data.cliente_nombre.replace(' ', '_').replace('.', '')}_{data.quote_number or datetime.now().strftime('%Y%m%d')}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer.read(),
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
        # Aislamiento RBAC: hidratar nombres desde la BD usando los IDs
        await hydrate_pdf_request(data)
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
        
        # Agregar páginas estáticas/anexos según producto y segmento (PyME/Corporativo).
        # Segmento autoritativo desde la ficha del cliente para PG/LP.
        resolved_seg = await _resolve_client_segment(data.client_id, data.quote_type, data.client_segment or "PYME")
        pdf_buffer = append_quote_static_pages(pdf_buffer, data.quote_type, resolved_seg)
        
        # Estampar header/footer en TODAS las páginas
        pdf_buffer = stamp_header_footer_on_all_pages(pdf_buffer, data.quote_number or '', logo_path)
        
        return Response(
            content=pdf_buffer.getvalue() if hasattr(pdf_buffer, 'getvalue') else pdf_buffer.read(),
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
    # Seriales asociados a este concepto (solo cotizaciones de Reparación).
    # Relación N:N con el pool de repair_models: un serial puede aparecer en varios conceptos.
    serials: List[str] = []
    # Concepto sin serial: ítems administrativos/logísticos (Casillero, Envío, Seguro, etc.)
    # Cuando True se omite la lista de seriales en el PDF y la validación de obligatoriedad.
    no_serial: bool = False

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
    iva_exempt: Optional[bool] = False
    # Iter50: descuento aplicable a cotizaciones de Equipos.
    discount_type: Optional[str] = None  # 'percent' | 'amount' | None
    discount_value: Optional[float] = 0  # valor crudo introducido por el usuario
    discount_amount_usd: Optional[float] = 0  # monto absoluto ya calculado en el cliente

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
    # Iter50: aplicar descuento ANTES de calcular el IVA (afecta la base imponible).
    discount_amount = 0.0
    discount_label = ""
    if data.discount_type and (data.discount_value or 0) > 0:
        if data.discount_type == "percent":
            pct = max(0.0, min(100.0, float(data.discount_value or 0)))
            discount_amount = round(subtotal * pct / 100.0, 2)
            discount_label = f"Descuento ({pct:g}%):"
        elif data.discount_type == "amount":
            discount_amount = max(0.0, min(subtotal, float(data.discount_value or 0)))
            discount_label = "Descuento:"
    # Si el frontend ya envió `discount_amount_usd` (ya calculado), preferirlo
    # para evitar discrepancias por redondeo entre cliente y servidor.
    if data.discount_amount_usd and abs(float(data.discount_amount_usd) - discount_amount) > 0.01:
        discount_amount = round(max(0.0, min(subtotal, float(data.discount_amount_usd))), 2)
    base_after_discount = max(0.0, subtotal - discount_amount)
    iva_rate = 0.0 if getattr(data, "iva_exempt", False) else 0.16
    iva = round(base_after_discount * iva_rate, 2)
    total = round(base_after_discount + iva, 2)
    iva_label = "IVA (Exento)" if getattr(data, "iva_exempt", False) else "IVA (16%)"

    items_html = ""
    for item in data.items:
        line_total = item.quantity * item.unit_price_usd
        serials_block = ""
        if getattr(item, "no_serial", False):
            # Concepto administrativo/logístico — no se desglosan seriales en el PDF.
            serials_block = (
                '<div style="margin-top:4px;font-size:10px;font-style:italic;color:#94a3b8">'
                '<span style="font-weight:600;color:#64748b">Sin serial</span> · concepto administrativo/logístico'
                '</div>'
            )
        elif item.serials:
            # Chips de seriales en columnas, fuente menor, itálica.
            serial_spans = "".join(
                f'<span style="display:inline-block;margin:1px 4px 1px 0;padding:1px 6px;background:#fff7ed;border:1px solid #fed7aa;border-radius:3px;font-family:monospace;font-size:9.5px;color:#9a3412">{s}</span>'
                for s in item.serials
            )
            serials_block = (
                f'<div style="margin-top:4px;font-size:10px;font-style:italic;color:#6b7280">'
                f'<span style="font-weight:600;color:#9a3412">Seriales ({len(item.serials)}):</span> {serial_spans}'
                f'</div>'
            )
        items_html += f"""<tr>
            <td><span class="item-name">{item.name}</span><span class="item-desc">{item.hardware_type}</span>{serials_block}</td>
            <td style="text-align:center">{item.quantity}</td>
            <td style="text-align:right">${item.unit_price_usd:,.2f}</td>
            <td style="text-align:right">${line_total:,.2f}</td>
        </tr>"""

    repair_section = ""
    if data.equipment_type == "Reparación" and data.repair_description:
        # Resumen por modelo si hay repair_models
        models_summary = ""
        if data.repair_models:
            _total_units = sum(m.quantity for m in data.repair_models)
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
                        <td style="padding:6px 10px;font-weight:bold;font-size:12px;color:#92400e;text-align:center">{_total_units}</td>
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
        @page {{
            size: letter;
            margin: 200px 40px 40px 40px;
            @top-left {{ content: element(page-header); width: 100%; }}
        }}
        body {{ font-family: Helvetica, Arial, sans-serif; color: #475569; margin: 0; padding: 0; font-size: 13px; }}
        .running-header {{ position: running(page-header); width: 100%; padding-top: 10px; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #f8fafc; padding-bottom: 16px; }}
        .brand {{ font-size: 22px; font-weight: bold; color: #1e293b; }}
        .brand-sub {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
        .quote-meta {{ text-align: right; }}
        .quote-id {{ font-size: 18px; color: #3b82f6; font-weight: 800; }}
        .quote-type {{ font-size: 12px; color: #64748b; background: #f1f5f9; padding: 3px 10px; border-radius: 4px; display: inline-block; margin-top: 6px; }}
        .info-grid {{ display: flex; justify-content: space-between; gap: 40px; margin: 14px 0 0 0; }}
        .info-block {{ flex: 1; }}
        .info-block h3 {{ font-size: 10px; text-transform: uppercase; color: #94a3b8; letter-spacing: 1px; margin: 0 0 4px 0; }}
        .info-block strong {{ color: #1e293b; font-size: 13px; }}
        .info-block span {{ font-size: 11px; color: #64748b; }}
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
    <!-- Encabezado fijo: se renderiza en TODAS las páginas de la cotización vía @top-left -->
    <div class="running-header">
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
                <span>RIF: {format_rif(data.cliente_rif) or 'N/A'}</span><br>
                <span>{data.cliente_address or ''}</span>
            </div>
            <div class="info-block" style="text-align:right">
                <h3>Emitido por:</h3>
                <strong>Mega Soft Computación, C.A.</strong><br>
                <span>Sistema de Cotizaciones</span>
            </div>
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
            {('<div class="total-row" style="color:#c2410c"><span>' + discount_label + '</span><span>-$' + format(discount_amount, ',.2f') + '</span></div>') if discount_amount > 0 else ''}
            <div class="total-row"><span>{iva_label}:</span><span>${iva:,.2f}</span></div>
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

    # Guardar PDF en el servidor + Object Storage
    pdf_filename = f"{quote_number}_Cotizacion_Equipo.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename
    save_pdf_dual(pdf_path, pdf_bytes, pdf_filename)
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

    # Determinar segmento basado en la sede del usuario
    client_segment = "CORP" if user_sede in ("CORP", "Corp", "Corporativo") else "PYME"

    quote_doc = {
        "quote_id": quote_id,
        "quote_number": quote_number,
        "client_id": data.client_id,
        "client_name": client_display_name,
        "client_segment": client_segment,
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
        "iva_exempt": bool(getattr(data, "iva_exempt", False)),
        # Iter50: descuento aplicado.
        "discount_type": data.discount_type or None,
        "discount_value": float(data.discount_value or 0),
        "discount_amount_usd": float(discount_amount),
        "quote_status": "Borrador",
        "quote_pdf_url": quote_pdf_url,
        "attachments": [attachment_entry],
        "sede": user_sede,
        "created_by_user_id": current_user.get("user_id"),
        "creator_departamento": current_user.get("departamento"),
        "creator_cargo": current_user.get("cargo"),
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



@router.post("/quotes/{quote_id}/regenerate-equipment-pdf")
async def regenerate_equipment_pdf(quote_id: str, data: dict = {}, authorization: Optional[str] = Header(None)):
    """Regenera PDF de cotización de equipos/reparaciones desde datos almacenados."""
    current_user = await get_current_user(authorization)
    import weasyprint
    import base64 as b64mod

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    # Obtener datos del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    cliente_nombre = quote.get("client_name", "")
    cliente_rif = ""
    cliente_address = ""
    if client:
        cliente_nombre = client.get("legal_name") or client.get("fantasy_name", cliente_nombre)
        cliente_rif = client.get("rif", "")
        cliente_address = client.get("address", "")

    quote_number = quote["quote_number"]
    equipment_type = quote.get("equipment_type", "Equipo")
    items = quote.get("equipment_items", [])
    notes = quote.get("notes", "")
    repair_description = quote.get("repair_description", "")
    equipment_serial_number = quote.get("equipment_serial_number", "")
    repair_models = quote.get("repair_models", [])

    now = datetime.now(timezone.utc)
    fecha = now.strftime("%d/%m/%Y")
    vence = (now + timedelta(days=15)).strftime("%d/%m/%Y")

    logo_html = '<div style="font-size:22px;font-weight:bold;color:#1e293b">Gestor - Work Flow</div>'
    logo_file = UPLOADS_DIR / "logo.png"
    if logo_file.exists():
        logo_b64 = b64mod.b64encode(logo_file.read_bytes()).decode()
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-height:60px;max-width:200px;object-fit:contain" />'

    type_labels = {"Verifone": "Equipos Verifone", "Morefun": "Equipos Morefun", "Accesorio": "Accesorios", "Reparación": "Reparaciones"}
    type_title = type_labels.get(equipment_type, equipment_type)

    subtotal = sum((i.get("quantity", 1) * i.get("unit_price_usd", 0)) for i in items)
    iva_rate = 0.0 if quote.get("iva_exempt") else 0.16
    iva = round(subtotal * iva_rate, 2)
    total = round(subtotal + iva, 2)
    iva_label = "IVA (Exento)" if quote.get("iva_exempt") else "IVA (16%)"

    items_html = ""
    for item in items:
        line_total = (item.get("quantity", 1)) * (item.get("unit_price_usd", 0))
        items_html += f"""<tr>
            <td><span style="font-weight:600;color:#1e293b;display:block">{item.get('name', '')}</span>
            <span style="font-size:11px;color:#94a3b8">{item.get('hardware_type', '')}</span></td>
            <td style="text-align:center">{item.get('quantity', 1)}</td>
            <td style="text-align:right">${item.get('unit_price_usd', 0):,.2f}</td>
            <td style="text-align:right">${line_total:,.2f}</td>
        </tr>"""

    repair_section = ""
    if equipment_type == "Reparación" and repair_description:
        models_summary = ""
        if repair_models:
            _total_units = sum(m.get("quantity", 0) for m in repair_models)
            models_rows = "".join(
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px">{m.get("model_name", "")}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px;text-align:center">{m.get("quantity", 0)}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #fed7aa;font-size:12px;text-align:center">{len(m.get("serials", []))}</td></tr>'
                for m in repair_models
            )
            models_summary = f"""<br><table style="width:100%;border-collapse:collapse;margin-top:8px;border:1px solid #fed7aa;border-radius:4px">
                <thead><tr style="background:#fef3c7">
                    <th style="padding:6px 10px;text-align:left;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Modelo</th>
                    <th style="padding:6px 10px;text-align:center;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Cantidad</th>
                    <th style="padding:6px 10px;text-align:center;font-size:11px;color:#92400e;border-bottom:1px solid #fed7aa">Seriales</th>
                </tr></thead><tbody>{models_rows}</tbody></table>"""
        elif equipment_serial_number:
            models_summary = f'<br><span style="font-size:12px;color:#64748b">Serial: {equipment_serial_number}</span>'

        repair_section = f"""<div style="margin:20px 0;padding:15px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px">
            <strong style="color:#9a3412">Detalle de Reparación</strong><br>
            <span style="font-size:13px;color:#475569">{repair_description}</span>
            {models_summary}
        </div>"""

    notes_section = ""
    if notes:
        notes_section = f'<br><strong>Observaciones:</strong><br><span style="font-size:12px">{notes}</span>'

    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
    <style>
        @page {{ size: letter; margin: 40px; }}
        body {{ font-family: Helvetica, Arial, sans-serif; color: #475569; margin: 0; padding: 0; font-size: 13px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th {{ background: #f8fafc; text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; color: #64748b; letter-spacing: 0.5px; border-bottom: 2px solid #e2e8f0; }}
        td {{ padding: 14px 12px; border-bottom: 1px solid #f1f5f9; }}
    </style></head><body>
    <div style="display:flex;justify-content:space-between;border-bottom:2px solid #f8fafc;padding-bottom:20px;margin-bottom:30px">
        <div>{logo_html}</div>
        <div style="text-align:right">
            <div style="font-size:18px;color:#3b82f6;font-weight:800">COTIZACIÓN #{quote_number}</div>
            <div style="font-size:12px;color:#64748b">Fecha: {fecha}</div>
            <div style="font-size:12px;color:#64748b">Vence: {vence}</div>
            <div style="font-size:12px;color:#64748b;background:#f1f5f9;padding:3px 10px;border-radius:4px;display:inline-block;margin-top:6px">{type_title}</div>
        </div>
    </div>
    <div style="display:flex;justify-content:space-between;gap:40px;margin:30px 0">
        <div style="flex:1"><h3 style="font-size:10px;text-transform:uppercase;color:#94a3b8;letter-spacing:1px;margin:0 0 6px 0">Preparado para:</h3>
        <strong style="color:#1e293b;font-size:14px">{cliente_nombre}</strong><br>
        <span style="font-size:12px;color:#64748b">RIF: {format_rif(cliente_rif) or 'N/A'}</span><br>
        <span style="font-size:12px;color:#64748b">{cliente_address or ''}</span></div>
        <div style="flex:1;text-align:right"><h3 style="font-size:10px;text-transform:uppercase;color:#94a3b8;letter-spacing:1px;margin:0 0 6px 0">Emitido por:</h3>
        <strong style="color:#1e293b;font-size:14px">Mega Soft Computación, C.A.</strong></div>
    </div>
    {repair_section}
    <table><thead><tr>
        <th>Descripción del Equipo/Servicio</th>
        <th style="text-align:center">Cant.</th>
        <th style="text-align:right">P. Unitario</th>
        <th style="text-align:right">Total</th>
    </tr></thead><tbody>{items_html}</tbody></table>
    <div style="margin-top:40px;display:flex;justify-content:space-between;gap:40px">
        <div style="font-size:10px;line-height:1.6;color:#94a3b8;flex:1">
            <strong>Términos y Condiciones:</strong><br>
            Los precios están sujetos a cambio sin previo aviso según mercado.
            La garantía cubre defectos de fábrica por 12 meses.
            {notes_section}
        </div>
        <div style="background:#1e293b;color:white;padding:20px;border-radius:8px;min-width:250px">
            <div style="display:flex;justify-content:space-between;margin:6px 0;font-size:13px"><span>Subtotal:</span><span>${subtotal:,.2f}</span></div>
            <div style="display:flex;justify-content:space-between;margin:6px 0;font-size:13px"><span>{iva_label}:</span><span>${iva:,.2f}</span></div>
            <div style="display:flex;justify-content:space-between;font-size:20px;font-weight:bold;border-top:1px solid #334155;padding-top:10px;margin-top:10px"><span>TOTAL:</span><span>${total:,.2f}</span></div>
        </div>
    </div></body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()

    # Guardar PDF + Object Storage
    pdf_filename = f"{quote_number}_Cotizacion_Equipo.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename
    save_pdf_dual(pdf_path, pdf_bytes, pdf_filename)
    quote_pdf_url = f"/uploads/{pdf_filename}"

    # Reemplazar attachment de Cotización
    new_attachment = {
        "attachment_id": f"att_{uuid.uuid4().hex[:12]}",
        "category": "Cotización",
        "filename": pdf_filename,
        "url": quote_pdf_url,
        "uploaded_by": current_user.get("email", "system"),
        "uploaded_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "uploaded_at": now.isoformat(),
        "file_size": len(pdf_bytes),
        "content_type": "application/pdf"
    }

    await db.quotes.update_one({"quote_id": quote_id}, {"$pull": {"attachments": {"category": "Cotización"}}})
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {"quote_pdf_url": quote_pdf_url}, "$push": {"attachments": new_attachment}})

    logging.info(f"PDF equipo regenerado para {quote_number}: {quote_pdf_url}")
    return {"pdf_url": quote_pdf_url, "quote_number": quote_number}



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
    ).to_list(2000)

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


# ============================================================================
# VPOS Multi-RIF: Carga de la matriz de Tiendas/Sucursales vía Excel
# ----------------------------------------------------------------------------
# Estructura objetivo (multirif_distribution):
#   [{ client_id, rif, client_name, boxes, stores: [{ name, boxes }] }]
#
# Formato del Excel (hoja "Distribucion", una fila por Sucursal):
#   | RIF Cliente | Nombre Sucursal | Cajas |
# Reglas:
#   - El RIF agrupa las sucursales por Cliente. Las "Cajas del RIF" se calculan
#     como la suma de las cajas de sus sucursales.
#   - El RIF debe corresponder a un Cliente registrado (se busca por RIF).
#   - "Cajas" debe ser un entero > 0.
#   - Sucursal no puede repetirse dentro del mismo RIF.
# El endpoint NO persiste nada: devuelve la distribución parseada + un reporte
# de errores/advertencias detallado (fila por fila) para que el frontend la
# muestre y, si no hay errores, reemplace la distribución del panel.
# ============================================================================

def _mr_norm_rif(s) -> str:
    """Normaliza un RIF para comparación: deja sólo alfanuméricos en mayúscula."""
    import re as _re
    return _re.sub(r'[^A-Za-z0-9]', '', str(s or '')).upper()


def _mr_norm_header(h) -> str:
    """Normaliza un encabezado de columna: minúsculas, sólo alfanumérico."""
    import re as _re
    return _re.sub(r'[^a-z0-9]', '', str(h or '').strip().lower())


@router.get("/quotes/multirif/excel-template")
async def multirif_excel_template(authorization: Optional[str] = Header(None)):
    """Descarga la plantilla .xlsx para cargar la distribución Multi-RIF
    (hoja de datos + hoja de Instrucciones)."""
    await get_current_user(authorization)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Distribucion"
    headers = ["RIF Cliente", "Nombre Sucursal", "Cajas"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2C3E50")
        cell.alignment = Alignment(horizontal="center")
    ws.column_dimensions['A'].width = 22
    ws.column_dimensions['B'].width = 36
    ws.column_dimensions['C'].width = 10
    # Filas de ejemplo
    ws.append(["J-12345678-9", "Sucursal Centro", 4])
    ws.append(["J-12345678-9", "Sucursal Este", 2])
    ws.append(["J-98765432-1", "Sede Norte", 4])

    ins = wb.create_sheet("Instrucciones")
    lines = [
        "INSTRUCCIONES — Carga de Distribución Multi-RIF (Tiendas/Sucursales)",
        "",
        "1) Complete la hoja 'Distribucion' con UNA FILA POR SUCURSAL.",
        "2) Columnas obligatorias (no cambie los encabezados de la fila 1):",
        "     • RIF Cliente: RIF del cliente al que pertenece la sucursal (ej. J-12345678-9).",
        "       El cliente debe estar registrado en el sistema; se busca por RIF.",
        "     • Nombre Sucursal: nombre de la tienda/sucursal (no puede repetirse dentro del mismo RIF).",
        "     • Cajas: cantidad de cajas (PDV) de esa sucursal. Entero mayor a 0.",
        "3) Las 'Cajas del RIF' se calculan automáticamente como la suma de sus sucursales.",
        "4) Al cargar, la distribución del Excel REEMPLAZA la del panel.",
        "5) Si el total de cajas del Excel no coincide con las Cajas Globales del lote, se mostrará",
        "   una ADVERTENCIA (no bloquea); podrá ajustar manualmente.",
        "",
        "ERRORES QUE SE REPORTAN (con número de fila):",
        "   • RIF vacío, Nombre de sucursal vacío o Cajas inválidas (no numérico / ≤ 0).",
        "   • RIF que no corresponde a ningún Cliente registrado.",
        "   • Sucursal duplicada dentro del mismo RIF.",
        "   • Faltan columnas obligatorias / archivo vacío o ilegible.",
        "",
        "Sugerencia: borre las filas de ejemplo antes de cargar su archivo real.",
    ]
    for i, t in enumerate(lines, 1):
        ins.cell(row=i, column=1, value=t)
    ins.column_dimensions['A'].width = 110

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_distribucion_multirif.xlsx"},
    )


@router.post("/quotes/multirif/parse-excel")
async def multirif_parse_excel(
    file: UploadFile = File(...),
    global_boxes: Optional[int] = Form(None),
    validate_rif: Optional[bool] = Form(True),
    authorization: Optional[str] = Header(None),
):
    """Parsea el Excel de distribución Multi-RIF y devuelve la distribución +
    reporte detallado de errores/advertencias. No persiste nada.
    Si validate_rif es False, NO valida la existencia del RIF en clientes
    (flujo flexible para prospección): acepta cualquier RIF con máscara básica,
    deja client_id y client_name vacíos (Nombre Jurídico 'No Validado')."""
    await get_current_user(authorization)
    import re

    fname = (file.filename or "").lower()
    if not fname.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx). Use la plantilla.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True, read_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Asegúrese de que sea un .xlsx válido (no .xls ni .csv).")

    ws = wb["Distribucion"] if "Distribucion" in wb.sheetnames else wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 1:
        raise HTTPException(status_code=400, detail="La hoja de datos está vacía.")

    header = [_mr_norm_header(h) for h in rows[0]]

    def _find_col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return None

    ci_rif = _find_col("rif", "rifcliente")
    ci_suc = _find_col("nombresucursal", "sucursal", "tienda", "nombretienda")
    ci_caj = _find_col("cajas", "cantidad", "cajassucursal", "cantidadcajas", "pdv")

    missing = []
    if ci_rif is None:
        missing.append("RIF Cliente")
    if ci_suc is None:
        missing.append("Nombre Sucursal")
    if ci_caj is None:
        missing.append("Cajas")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Faltan columnas obligatorias en la fila 1: {', '.join(missing)}. Descargue y use la plantilla.",
        )

    # Índice de clientes por RIF normalizado (solo si se exige validación).
    clients_by_rif = {}
    if validate_rif:
        async for c in db.clients.find({}, {"_id": 0, "client_id": 1, "rif": 1, "legal_name": 1, "fantasy_name": 1}):
            for k in {_mr_norm_rif(c.get("rif")), _mr_norm_rif(format_rif(c.get("rif")))}:
                if k:
                    clients_by_rif[k] = c

    errors = []
    warnings = []
    groups = {}   # norm_rif -> {client_id, rif, client_name, stores, seen}
    order = []
    total_boxes = 0

    for ridx, row in enumerate(rows[1:], start=2):
        if row is None or all((v is None or str(v).strip() == "") for v in row):
            continue  # fila completamente vacía → se ignora

        rif_raw = row[ci_rif] if ci_rif < len(row) else None
        suc_raw = row[ci_suc] if ci_suc < len(row) else None
        caj_raw = row[ci_caj] if ci_caj < len(row) else None
        rif_s = str(rif_raw).strip() if rif_raw is not None else ""
        suc_s = str(suc_raw).strip() if suc_raw is not None else ""

        row_errs = []
        if not rif_s:
            row_errs.append("RIF Cliente vacío.")
        if not suc_s:
            row_errs.append("Nombre Sucursal vacío.")

        boxes = None
        try:
            boxes = int(float(caj_raw))
        except (TypeError, ValueError):
            boxes = None
        if boxes is None or boxes <= 0:
            row_errs.append(f"Cajas inválidas ('{caj_raw}'): debe ser un número entero mayor a 0.")

        client = None
        if validate_rif:
            # Escenario A (SÍ): el RIF debe existir en la tabla de clientes.
            if rif_s:
                client = clients_by_rif.get(_mr_norm_rif(rif_s)) or clients_by_rif.get(_mr_norm_rif(format_rif(rif_s)))
                if not client:
                    row_errs.append(f"El RIF '{rif_s}' no corresponde a ningún Cliente registrado en el sistema.")
        else:
            # Escenario B (NO): solo máscara básica alfanumérica (sin consultar BD).
            if rif_s and not re.match(r'^[A-Za-z0-9][A-Za-z0-9\-\.\s]*$', rif_s):
                row_errs.append(f"El RIF '{rif_s}' tiene un formato inválido (use solo letras, números, guiones o puntos).")

        if row_errs:
            errors.append({"row": ridx, "rif": rif_s, "sucursal": suc_s, "messages": row_errs})
            continue

        if validate_rif:
            nk = _mr_norm_rif(client.get("rif"))
            cid = client["client_id"]
            disp_rif = client.get("rif", "")
            cname = client.get("fantasy_name") or client.get("legal_name") or ""
        else:
            nk = _mr_norm_rif(rif_s)
            cid = ""
            disp_rif = rif_s
            cname = ""

        if nk not in groups:
            groups[nk] = {"client_id": cid, "rif": disp_rif, "client_name": cname, "stores": [], "seen": {}}
            order.append(nk)
        g = groups[nk]
        skey = suc_s.lower()
        if skey in g["seen"]:
            errors.append({
                "row": ridx, "rif": rif_s, "sucursal": suc_s,
                "messages": [f"Sucursal duplicada para el RIF '{rif_s}' (ya aparece en la fila {g['seen'][skey]})."],
            })
            continue
        g["seen"][skey] = ridx
        g["stores"].append({"name": suc_s, "boxes": boxes})
        total_boxes += boxes

    distribution = []
    for nk in order:
        g = groups[nk]
        distribution.append({
            "client_id": g["client_id"],
            "rif": g["rif"],
            "client_name": g["client_name"],
            "validated": bool(validate_rif),
            "boxes": sum(s["boxes"] for s in g["stores"]),
            "stores": g["stores"],
        })

    if global_boxes is not None and total_boxes != int(global_boxes):
        diff = total_boxes - int(global_boxes)
        warnings.append(
            f"El total de cajas del Excel ({total_boxes}) no coincide con las Cajas Globales del lote "
            f"({int(global_boxes)}); diferencia de {abs(diff)} caja(s). Puede ajustar manualmente."
        )

    summary = {
        "total_rifs": len(distribution),
        "total_stores": sum(len(d["stores"]) for d in distribution),
        "total_boxes": total_boxes,
        "rows_with_errors": len(errors),
    }

    return {
        "ok": len(errors) == 0,
        "distribution": distribution,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }
