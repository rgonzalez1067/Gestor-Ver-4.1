"""Route module: dashboard.py"""
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

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template, require_permission
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

# regenerate-pdf endpoint moved to quotes.py for proper field mapping

@router.post("/clients/import")
async def import_clients(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    await require_permission(authorization, "clientes", "edit")
    
    import pandas as pd
    
    content = await file.read()
    errors: List[ImportError] = []
    success_count = 0
    skipped_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='Archivo', value=file.filename, error_type='format',
                message=f'Formato de archivo no soportado: ".{file_ext}". Solo se aceptan archivos .xlsx, .xls o .csv.',
                suggested_action='Descargue la plantilla modelo (.xlsx) y utilice ese formato para su carga.')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        if file_ext == 'csv':
            for sep in [',', ';', '\t']:
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='utf-8')
                    if len(df.columns) >= 3:
                        break
                except Exception:
                    continue
            else:
                for sep in [',', ';', '\t']:
                    try:
                        df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='latin-1')
                        if len(df.columns) >= 3:
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
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='Archivo', value=file.filename, error_type='format',
                    message='El archivo está vacío. No se encontraron filas de datos.',
                    suggested_action='Agregue al menos una fila de datos debajo de los encabezados. Descargue la plantilla como referencia.')],
                message='Error: El archivo no contiene datos'
            )
        
        df.columns = [c.strip() for c in df.columns]
        
        column_mapping = {
            # Base fields
            'Nombre Jurídico': 'legal_name', 'nombre_jurídico': 'legal_name', 'nombre_juridico': 'legal_name',
            'Nombre Fantasía': 'fantasy_name', 'nombre_fantasía': 'fantasy_name', 'nombre_fantasia': 'fantasy_name',
            'Segmento': 'segment', 'segmento': 'segment',
            'Condición': 'condicion', 'condicion': 'condicion', 'Condicion': 'condicion',
            'Referidor': 'referidor', 'referidor': 'referidor',
            'Origen Tipo': 'origen_tipo', 'origen_tipo': 'origen_tipo', 'Origen_Tipo': 'origen_tipo',
            'Referidor Nombre': 'referidor_nombre_col', 'referidor_nombre': 'referidor_nombre_col', 'Referidor_Nombre': 'referidor_nombre_col',
            'Referidor ID': 'referidor_id_col', 'referidor_id': 'referidor_id_col', 'Referidor_ID': 'referidor_id_col',
            'Dirección Fiscal': 'address', 'Dirección': 'address', 'dirección': 'address',
            'direccion': 'address', 'dirección_fiscal': 'address', 'direccion_fiscal': 'address',
            'Dirección Sucursal': 'branch_address', 'dirección_sucursal': 'branch_address',
            'direccion_sucursal': 'branch_address',
            'Categoría Comercial': 'categoria_comercial', 'categoría_comercial': 'categoria_comercial',
            'categoria_comercial': 'categoria_comercial', 'Categoria Comercial': 'categoria_comercial',
            'Grupo Económico': 'grupo_economico', 'grupo_económico': 'grupo_economico',
            'grupo_economico': 'grupo_economico', 'Grupo Economico': 'grupo_economico',
            'Ejecutivo Propietario': 'ejecutivo_propietario', 'ejecutivo_propietario': 'ejecutivo_propietario',
            'Cantidad Tiendas': 'cantidad_tiendas', 'cantidad_tiendas': 'cantidad_tiendas',
            'Cantidad Cajas': 'cantidad_cajas', 'cantidad_cajas': 'cantidad_cajas',
            'Coordinador': 'coordinator_name', 'coordinador': 'coordinator_name',
            'Implementador': 'implementer_name', 'implementador': 'implementer_name',
            'Fecha Primer Contacto': 'fecha_primer_contacto', 'fecha_primer_contacto': 'fecha_primer_contacto',
            'Tipo Contacto': 'tipo_contacto', 'tipo_contacto': 'tipo_contacto',
            'Tipo Servicio': 'tipo_servicio', 'tipo_servicio': 'tipo_servicio',
            'Integrador': 'integrador_name', 'integrador': 'integrador_name',
            'Aplicativo': 'aplicativo', 'aplicativo': 'aplicativo',
            # Contacts
            'Contacto Nombre Completo': 'contact_name', 'contacto_nombre_completo': 'contact_name',
            'Contacto Nombre': 'contact_name', 'contacto_nombre': 'contact_name',
            'Contacto Teléfono': 'contact_phone', 'contacto_teléfono': 'contact_phone',
            'contacto_telefono': 'contact_phone',
            'Contacto Email': 'contact_email', 'contacto_email': 'contact_email',
            'Contacto Rol': 'contact_role', 'contacto_rol': 'contact_role',
            # Legacy support
            'contacto1_nombre': 'contact_name', 'contacto1_teléfono': 'contact_phone',
            'contacto1_telefono': 'contact_phone', 'contacto1_email': 'contact_email',
        }
        
        # Normalize columns: strip but keep case for mapping
        rename_map = {}
        for col in df.columns:
            stripped = col.strip()
            if stripped in column_mapping:
                rename_map[col] = column_mapping[stripped]
            elif stripped.lower() in {k.lower(): v for k, v in column_mapping.items()}:
                for k, v in column_mapping.items():
                    if k.lower() == stripped.lower():
                        rename_map[col] = v
                        break
        
        # Preserve rif and sucursal
        for col in df.columns:
            cl = col.strip().lower()
            if cl == 'rif' and col not in rename_map:
                rename_map[col] = 'rif'
            elif cl == 'sucursal' and col not in rename_map:
                rename_map[col] = 'sucursal'
        
        df.rename(columns=rename_map, inplace=True)
        df = df.loc[:, ~df.columns.duplicated()]
        
        required_columns = ['rif', 'legal_name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            friendly = {'rif': 'RIF', 'legal_name': 'Nombre Jurídico'}
            missing_friendly = [friendly.get(c, c) for c in missing_columns]
            return ImportResult(
                status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_friendly), value=None, error_type='missing',
                    message=f'Columnas obligatorias no encontradas en el archivo: {", ".join(missing_friendly)}. Verifique que los encabezados coincidan exactamente con la plantilla.',
                    suggested_action=f'Descargue la plantilla modelo y asegúrese de incluir las columnas: {", ".join(missing_friendly)}. Los nombres deben coincidir exactamente.')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_friendly)})'
            )
        
        valid_segments = ['Pymes', 'Corporativo', 'Emprendedor', 'Mixto']
        valid_condiciones = ['Prospecto', 'Cliente']
        valid_roles = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo']
        valid_tipos_servicio = ['VPOS', 'MPOS', 'Payment Gateway', 'Link de Pago']
        valid_categorias = [
            'Retail', 'Farmacia', 'Restaurante', 'Supermercado', 'Abasto', 'Panadería',
            'Bar / Discoteca', 'Comida Rápida', 'Cafetería', 'Tienda de Ropa', 'Boutique',
            'Salón de Belleza', 'Barbería', 'Spa / Salud', 'Gimnasio', 'Cosmética',
            'Calzados', 'Mueblería', 'Ferretería', 'Electrodomésticos', 'Joyería',
            'Electrónica', 'Software', 'Juguetería', 'Librería', 'Tienda por Departamento',
            'Educación', 'Inmobiliaria', 'Clínica', 'Alimentos', 'Tecnología', 'Servicios',
        ]
        
        # Pre-load ejecutivos and integradores for validation
        ejecutivos_db = await db.users.find(
            {"is_active": True, "cargo": {"$in": ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]}},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
        ).to_list(1000)
        ejecutivo_lookup = {}
        for ej in ejecutivos_db:
            full = f"{ej.get('first_name', '')} {ej.get('last_name', '')}".strip()
            ejecutivo_lookup[full.lower()] = {"name": full, "user_id": ej["user_id"]}
            ejecutivo_lookup[ej.get("email", "").lower()] = {"name": full, "user_id": ej["user_id"]}

        # Lookup de Coordinadores e Implementadores (Responsables de Implementación)
        coords_db = await db.users.find(
            {"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
        ).to_list(500)
        coordinador_lookup = {}
        for u in coords_db:
            full = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            coordinador_lookup[full.lower()] = {"name": full, "user_id": u["user_id"]}
            if u.get("email"):
                coordinador_lookup[u["email"].lower()] = {"name": full, "user_id": u["user_id"]}

        impls_db = await db.users.find(
            {"is_active": True, "cargo": "Implementador"},
            {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}
        ).to_list(500)
        implementador_lookup = {}
        for u in impls_db:
            full = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            implementador_lookup[full.lower()] = {"name": full, "user_id": u["user_id"]}
            if u.get("email"):
                implementador_lookup[u["email"].lower()] = {"name": full, "user_id": u["user_id"]}
        
        integradores_db = await db.integrators.find({}, {"_id": 0, "integrator_id": 1, "name": 1, "app_name": 1}).to_list(1000)
        integrador_by_name = {}
        for intg in integradores_db:
            key = intg["name"].strip().lower()
            integrador_by_name.setdefault(key, []).append({
                "name": intg["name"],
                "id": intg["integrator_id"],
                "app_name": (intg.get("app_name") or "").strip(),
            })
        
        import re as re_mod
        rif_pattern = re_mod.compile(r'^[JVGEP]-?\d{5,9}-?\d$', re_mod.IGNORECASE)
        
        def _safe(row, col, default=''):
            val = row.get(col, default)
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            if pd.isna(val):
                return default
            return str(val).strip()
        
        def _safe_int(row, col):
            val = row.get(col, None)
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            if pd.isna(val) or val == '' or val is None:
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return 'INVALID'
        
        col_letters = {
            'rif': 'A', 'sucursal': 'B', 'legal_name': 'C', 'fantasy_name': 'D',
            'segment': 'E', 'condicion': 'F', 'origen_tipo': 'G', 'referidor_nombre': 'H',
            'referidor_id_col': 'I', 'address': 'J', 'branch_address': 'K',
            'categoria_comercial': 'L', 'grupo_economico': 'M',
            'ejecutivo_propietario': 'N', 'cantidad_tiendas': 'O', 'cantidad_cajas': 'P',
            'fecha_primer_contacto': 'Q', 'tipo_contacto': 'R', 'tipo_servicio': 'S',
            'integrador_name': 'T', 'aplicativo': 'U',
            'contact_name': 'V', 'contact_phone': 'W',
            'contact_email': 'X', 'contact_role': 'Y',
        }
        col_friendly = {
            'rif': 'RIF', 'sucursal': 'Sucursal', 'legal_name': 'Nombre Jurídico',
            'fantasy_name': 'Nombre Fantasía', 'segment': 'Segmento', 'condicion': 'Condición',
            'origen_tipo': 'Origen Tipo', 'referidor_nombre': 'Referidor Nombre',
            'referidor_id_col': 'Referidor ID',
            'address': 'Dirección Fiscal',
            'branch_address': 'Dirección Sucursal', 'categoria_comercial': 'Categoría Comercial',
            'grupo_economico': 'Grupo Económico', 'ejecutivo_propietario': 'Ejecutivo Propietario',
            'cantidad_tiendas': 'Cantidad Tiendas', 'cantidad_cajas': 'Cantidad Cajas',
            'fecha_primer_contacto': 'Fecha Primer Contacto', 'tipo_contacto': 'Tipo Contacto',
            'tipo_servicio': 'Tipo Servicio', 'integrador_name': 'Integrador',
            'aplicativo': 'Aplicativo', 'contact_name': 'Contacto Nombre Completo',
            'contact_phone': 'Contacto Teléfono',
            'contact_email': 'Contacto Email', 'contact_role': 'Contacto Rol',
        }
        
        def _col_ref(field):
            letter = col_letters.get(field, '?')
            name = col_friendly.get(field, field)
            return f"{name} (Col {letter})"
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                rif = _safe(row, 'rif')
                legal_name = _safe(row, 'legal_name')
                fantasy_name = _safe(row, 'fantasy_name') or legal_name
                segment = _safe(row, 'segment', 'Pymes')
                condicion = _safe(row, 'condicion', 'Prospecto')
                referidor = _safe(row, 'referidor')
                origen_tipo = _safe(row, 'origen_tipo')
                referidor_nombre_raw = _safe(row, 'referidor_nombre_col')
                referidor_id_raw = _safe(row, 'referidor_id_col')
                sucursal = _safe(row, 'sucursal', 'Principal')
                address = _safe(row, 'address')
                branch_address = _safe(row, 'branch_address')
                categoria_comercial = _safe(row, 'categoria_comercial')
                grupo_economico = _safe(row, 'grupo_economico')
                ejecutivo_propietario = _safe(row, 'ejecutivo_propietario')
                cantidad_tiendas = _safe_int(row, 'cantidad_tiendas')
                cantidad_cajas = _safe_int(row, 'cantidad_cajas')
                coordinator_raw = _safe(row, 'coordinator_name')
                implementer_raw = _safe(row, 'implementer_name')
                fecha_primer_contacto_raw = _safe(row, 'fecha_primer_contacto')
                tipo_contacto = _safe(row, 'tipo_contacto')
                tipo_servicio_raw = _safe(row, 'tipo_servicio')
                integrador_name = _safe(row, 'integrador_name')
                aplicativo = _safe(row, 'aplicativo')
                
                row_errors = []
                has_critical = False
                
                # === RIF validation ===
                if not rif:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('rif'), value='(vacío)',
                        error_type='missing',
                        message=f'Fila {row_num}, Col A (RIF): El campo está vacío. Cada cliente debe tener un RIF que lo identifique de forma única.',
                        suggested_action=f'Complete la celda A{row_num} con el RIF del cliente. Formato esperado: J-12345678-9. Este campo es obligatorio (*).'))
                    has_critical = True
                elif not rif_pattern.match(rif):
                    row_errors.append(ImportError(row=row_num, column=_col_ref('rif'), value=rif,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col A (RIF): El valor "{rif}" no tiene un formato de RIF válido. Se esperaba una letra (J, V, G, E, P) seguida de un guión, 5-9 dígitos, guión y un dígito verificador.',
                        suggested_action=f'Corrija la celda A{row_num}. Ejemplos válidos: J-12345678-9, V-98765432-1, G-11223344-5.'))
                    has_critical = True
                
                # === Legal Name validation ===
                if not legal_name:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('legal_name'), value='(vacío)',
                        error_type='missing',
                        message=f'Fila {row_num}, Col C (Nombre Jurídico): El campo está vacío. La razón social es un dato obligatorio para registrar un cliente.',
                        suggested_action=f'Complete la celda C{row_num} con la razón social del cliente. Este campo es obligatorio (*).'))
                    has_critical = True
                
                # === Segment validation ===
                if segment and segment not in valid_segments:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('segment'), value=segment,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col E (Segmento): Se recibió "{segment}" pero solo se aceptan: {", ".join(valid_segments)}. Se asignará "Pymes" por defecto.',
                        suggested_action=f'Corrija la celda E{row_num}. Use exactamente uno de: {", ".join(valid_segments)}. Consulte la hoja "Valores Válidos".'))
                    segment = 'Pymes'
                
                # === Condición validation ===
                if condicion and condicion not in valid_condiciones:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('condicion'), value=condicion,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col F (Condición): Se recibió "{condicion}" pero solo se aceptan: {", ".join(valid_condiciones)}. Se asignará "Prospecto" por defecto.',
                        suggested_action=f'Corrija la celda F{row_num}. Use exactamente: Prospecto o Cliente.'))
                    condicion = 'Prospecto'
                
                # === Referidor validation (lista maestra + cascada Banco/Cliente) ===
                _valid_origenes = [
                    'Correo de Ventas', 'Integrador', 'Directores', 'Corporativo',
                    'Jose Dolande', 'Melissa Garcia', 'Katherine Quailey', 'Rafael Gonzalez',
                    'Ventas Directas (Ejecutivo)', 'Página Web / Landing Page', 'Redes Sociales',
                    'Alianzas Externas', 'Banco', 'Cliente Referidor',
                ]
                referidor_tipo = None
                referidor_id = None
                referidor_nombre = None

                # Si viene origen_tipo (nuevo formato), usarlo como referidor
                effective_referidor = origen_tipo or referidor
                if effective_referidor:
                    referidor = effective_referidor

                if referidor:
                    if referidor == 'Banco':
                        referidor_tipo = 'BANCO'
                        if referidor_nombre_raw:
                            bank_match = await db.banks.find_one(
                                {"name": {"$regex": f"^{re.escape(referidor_nombre_raw.strip())}$", "$options": "i"}},
                                {"_id": 0, "bank_id": 1, "name": 1}
                            )
                            if bank_match:
                                referidor_id = bank_match["bank_id"]
                                referidor_nombre = bank_match["name"]
                            else:
                                row_errors.append(ImportError(row=row_num, column=_col_ref('referidor_nombre'), value=referidor_nombre_raw,
                                    error_type='invalid',
                                    message=f'Fila {row_num}, Col H (Referidor Nombre): El banco "{referidor_nombre_raw}" no está registrado.',
                                    suggested_action=f'Corrija la celda H{row_num}. Consulte la hoja "Valores Válidos" para los bancos disponibles.'))
                    elif referidor == 'Cliente Referidor':
                        referidor_tipo = 'CLIENTE'
                        search_term = referidor_id_raw or referidor_nombre_raw
                        if search_term:
                            ref_client = await db.clients.find_one(
                                {"$or": [
                                    {"rif": {"$regex": re.escape(search_term.strip()), "$options": "i"}},
                                    {"fantasy_name": {"$regex": re.escape(search_term.strip()), "$options": "i"}},
                                    {"legal_name": {"$regex": re.escape(search_term.strip()), "$options": "i"}},
                                ]},
                                {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1}
                            )
                            if ref_client:
                                referidor_id = ref_client["client_id"]
                                referidor_nombre = ref_client.get("fantasy_name") or ref_client.get("legal_name", "")
                            else:
                                row_errors.append(ImportError(row=row_num, column=_col_ref('referidor_nombre'), value=search_term,
                                    error_type='invalid',
                                    message=f'Fila {row_num}, Col H/I (Referidor): No se encontró cliente "{search_term}" en el sistema.',
                                    suggested_action='Corrija la celda. Si Origen=Cliente Referidor, el nombre o RIF debe pertenecer a un comercio ya registrado.'))
                    else:
                        referidor_tipo = 'OTRO'
                        referidor_nombre = referidor_nombre_raw or None                
                # === Categoría Comercial validation ===
                if categoria_comercial and categoria_comercial not in valid_categorias:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('categoria_comercial'), value=categoria_comercial,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col J (Categoría Comercial): Se recibió "{categoria_comercial}" pero no coincide con ninguna categoría registrada ({len(valid_categorias)} opciones disponibles).',
                        suggested_action=f'Corrija la celda J{row_num}. Consulte la hoja "Valores Válidos", columna "Categorías Comerciales" para ver todas las opciones.'))
                    categoria_comercial = None
                
                # === Ejecutivo validation ===
                ejecutivo_user_id = None
                if ejecutivo_propietario:
                    ej_match = ejecutivo_lookup.get(ejecutivo_propietario.lower())
                    if ej_match:
                        ejecutivo_propietario = ej_match["name"]
                        ejecutivo_user_id = ej_match["user_id"]
                    else:
                        ej_names = [v["name"] for v in ejecutivo_lookup.values()]
                        unique_names = list(dict.fromkeys(ej_names))
                        row_errors.append(ImportError(row=row_num, column=_col_ref('ejecutivo_propietario'), value=ejecutivo_propietario,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col L (Ejecutivo Propietario): El usuario "{ejecutivo_propietario}" no está registrado como ejecutivo de ventas en el sistema.',
                            suggested_action=f'Corrija la celda L{row_num}. Ejecutivos disponibles: {", ".join(unique_names[:10])}. El nombre debe coincidir exactamente.'))
                        ejecutivo_propietario = None

                # === Coordinador validation (Responsables de Implementación) ===
                coordinator_user_id = None
                coordinator_name = None
                if coordinator_raw:
                    m = coordinador_lookup.get(coordinator_raw.lower())
                    if m:
                        coordinator_name = m["name"]
                        coordinator_user_id = m["user_id"]
                    else:
                        available = list({v["name"] for v in coordinador_lookup.values()})
                        row_errors.append(ImportError(row=row_num, column=_col_ref('coordinator_name'), value=coordinator_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col Q (Coordinador): "{coordinator_raw}" no es un Coordinador válido (cargo "Coordinador", departamento "Implementación").',
                            suggested_action=f'Corrija la celda Q{row_num}. Coordinadores disponibles: {", ".join(available[:8]) if available else "(ninguno registrado — crear en Usuarios)"}.'))

                # === Implementador validation (Responsables de Implementación) ===
                implementer_user_id = None
                implementer_name = None
                if implementer_raw:
                    m = implementador_lookup.get(implementer_raw.lower())
                    if m:
                        implementer_name = m["name"]
                        implementer_user_id = m["user_id"]
                    else:
                        available = list({v["name"] for v in implementador_lookup.values()})
                        row_errors.append(ImportError(row=row_num, column=_col_ref('implementer_name'), value=implementer_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col R (Implementador): "{implementer_raw}" no es un Implementador válido (cargo "Implementador").',
                            suggested_action=f'Corrija la celda R{row_num}. Implementadores disponibles: {", ".join(available[:8]) if available else "(ninguno registrado — crear en Usuarios)"}.'))
                
                # === Cantidad Tiendas/Cajas validation ===
                if cantidad_tiendas == 'INVALID':
                    raw_val = _safe(row, 'cantidad_tiendas')
                    row_errors.append(ImportError(row=row_num, column=_col_ref('cantidad_tiendas'), value=raw_val,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col M (Cantidad Tiendas): Se recibió "{raw_val}" pero se esperaba un número entero positivo.',
                        suggested_action=f'Corrija la celda M{row_num}. Ingrese solo un número entero (ej: 5, 10, 25). No use letras ni símbolos.'))
                    cantidad_tiendas = None
                
                if cantidad_cajas == 'INVALID':
                    raw_val = _safe(row, 'cantidad_cajas')
                    row_errors.append(ImportError(row=row_num, column=_col_ref('cantidad_cajas'), value=raw_val,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col N (Cantidad Cajas): Se recibió "{raw_val}" pero se esperaba un número entero positivo.',
                        suggested_action=f'Corrija la celda N{row_num}. Ingrese solo un número entero (ej: 2, 12, 50). No use letras ni símbolos.'))
                    cantidad_cajas = None
                
                # === Fecha Primer Contacto validation ===
                fecha_primer_contacto = None
                if fecha_primer_contacto_raw:
                    from datetime import date as date_type
                    parsed_date = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
                        try:
                            parsed_date = datetime.strptime(fecha_primer_contacto_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                    if parsed_date is None:
                        row_errors.append(ImportError(row=row_num, column=_col_ref('fecha_primer_contacto'), value=fecha_primer_contacto_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col O (Fecha Primer Contacto): El formato "{fecha_primer_contacto_raw}" no es reconocido. Formatos aceptados: DD/MM/AAAA (15/01/2026) o AAAA-MM-DD (2026-01-15).',
                            suggested_action=f'Corrija la celda O{row_num}. Use un formato de fecha estándar: 15/01/2026 o 2026-01-15.'))
                    elif parsed_date > date_type.today():
                        row_errors.append(ImportError(row=row_num, column=_col_ref('fecha_primer_contacto'), value=fecha_primer_contacto_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col O (Fecha Primer Contacto): La fecha {fecha_primer_contacto_raw} es posterior a hoy ({date_type.today().strftime("%d/%m/%Y")}). No se permiten fechas futuras.',
                            suggested_action=f'Corrija la celda O{row_num}. Ingrese una fecha igual o anterior a hoy.'))
                    else:
                        fecha_primer_contacto = parsed_date.isoformat()
                
                # === Tipo Servicio validation ===
                tipo_servicio_list = []
                if tipo_servicio_raw:
                    parts = [s.strip() for s in tipo_servicio_raw.replace(';', ',').split(',') if s.strip()]
                    invalid_services = [s for s in parts if s not in valid_tipos_servicio]
                    if invalid_services:
                        row_errors.append(ImportError(row=row_num, column=_col_ref('tipo_servicio'), value=tipo_servicio_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col Q (Tipo Servicio): Los valores "{", ".join(invalid_services)}" no son válidos. Valores aceptados: {", ".join(valid_tipos_servicio)}.',
                            suggested_action=f'Corrija la celda Q{row_num}. Separe múltiples servicios con comas: "VPOS, MPOS". Solo se aceptan: {", ".join(valid_tipos_servicio)}.'))
                    tipo_servicio_list = [s for s in parts if s in valid_tipos_servicio]
                
                # === Integrador + Aplicativo validation (cascade) ===
                integrador_id = None
                if integrador_name:
                    intg_records = integrador_by_name.get(integrador_name.strip().lower())
                    if intg_records:
                        integrador_name = intg_records[0]["name"]
                        apps = [r["app_name"] for r in intg_records if r["app_name"]]
                        if aplicativo:
                            match = next((r for r in intg_records if r["app_name"] and r["app_name"].lower() == aplicativo.strip().lower()), None)
                            if match:
                                aplicativo = match["app_name"]
                                integrador_id = match["id"]
                            elif apps:
                                has_critical = True
                                row_errors.append(ImportError(row=row_num, column=_col_ref('aplicativo'), value=aplicativo,
                                    error_type='invalid',
                                    message=f'Fila {row_num}, Col U (Aplicativo): "{aplicativo}" no es un aplicativo válido para el integrador "{integrador_name}".',
                                    suggested_action=f'Corrija la celda U{row_num}. Aplicativos válidos para "{integrador_name}": {", ".join(apps)}.'))
                            else:
                                integrador_id = intg_records[0]["id"]
                        else:
                            if len(apps) == 1:
                                aplicativo = apps[0]
                                integrador_id = intg_records[0]["id"]
                            elif len(apps) > 1:
                                has_critical = True
                                row_errors.append(ImportError(row=row_num, column=_col_ref('aplicativo'), value='(vacío)',
                                    error_type='missing',
                                    message=f'Fila {row_num}, Col U (Aplicativo): El integrador "{integrador_name}" tiene varios aplicativos; debe indicar cuál corresponde.',
                                    suggested_action=f'Complete la celda U{row_num} con uno de los aplicativos válidos: {", ".join(apps)}.'))
                            else:
                                integrador_id = intg_records[0]["id"]
                    else:
                        row_errors.append(ImportError(row=row_num, column=_col_ref('integrador_name'), value=integrador_name,
                            error_type='invalid',
                            message=f'Fila {row_num}, Col T (Integrador): El integrador "{integrador_name}" no está registrado en el sistema.',
                            suggested_action=f'Corrija la celda T{row_num}. Consulte la hoja "Valores Válidos" para ver los integradores disponibles. El nombre debe coincidir exactamente.'))
                        integrador_name = None
                
                # === Contact Role validation ===
                contact_name = _safe(row, 'contact_name')
                contact_phone = _safe(row, 'contact_phone')
                contact_email = _safe(row, 'contact_email')
                contact_role = _safe(row, 'contact_role', 'Administrativo')
                if contact_role and contact_role not in valid_roles:
                    row_errors.append(ImportError(row=row_num, column=_col_ref('contact_role'), value=contact_role,
                        error_type='invalid',
                        message=f'Fila {row_num}, Col X (Contacto Rol): Se recibió "{contact_role}" pero solo se aceptan: {", ".join(valid_roles)}. Se asignará "Administrativo" por defecto.',
                        suggested_action=f'Corrija la celda X{row_num}. Use exactamente uno de: {", ".join(valid_roles)}.'))
                    contact_role = 'Administrativo'
                
                # === Skip if critical errors ===
                if has_critical:
                    errors.extend(row_errors)
                    skipped_count += 1
                    continue
                
                # === Check duplicates ===
                existing = await db.clients.find_one({"rif": rif, "sucursal": sucursal})
                if existing:
                    errors.append(ImportError(row=row_num, column=f'{_col_ref("rif")} + {_col_ref("sucursal")}', value=f'{rif} / {sucursal}',
                        error_type='duplicate',
                        message=f'Fila {row_num}: Ya existe un cliente con RIF "{rif}" y sucursal "{sucursal}" en el sistema. No se permiten registros duplicados con la misma combinación.',
                        suggested_action='Verifique si desea importar este registro con una sucursal distinta (ej: "Sede Norte"), o elimine esta fila si ya existe en el sistema.'))
                    skipped_count += 1
                    # Still log non-critical errors
                    if row_errors:
                        errors.extend(row_errors)
                    continue
                
                # Register non-critical warnings
                if row_errors:
                    errors.extend(row_errors)
                
                # Build contacts CRM
                contacts_crm = []
                if contact_name:
                    contacts_crm.append({
                        "contact_id": f"cnt_{uuid.uuid4().hex[:8]}",
                        "first_name": contact_name,
                        "last_name": "",
                        "full_name": contact_name,
                        "phone": contact_phone,
                        "email": contact_email,
                        "role": contact_role
                    })
                
                client = Client(
                    rif=rif,
                    legal_name=legal_name,
                    fantasy_name=fantasy_name,
                    segment=segment,
                    condicion=condicion,
                    referidor=referidor or None,
                    referidor_tipo=referidor_tipo or None,
                    referidor_id=referidor_id or None,
                    referidor_nombre=referidor_nombre or None,
                    sucursal=sucursal,
                    address=address or None,
                    branch_address=branch_address or None,
                    categoria_comercial=categoria_comercial or None,
                    grupo_economico=grupo_economico or None,
                    ejecutivo_propietario=ejecutivo_propietario or None,
                    ejecutivo_user_id=ejecutivo_user_id,
                    cantidad_tiendas=cantidad_tiendas,
                    cantidad_cajas=cantidad_cajas,
                    coordinator_user_id=coordinator_user_id,
                    coordinator_name=coordinator_name,
                    implementer_user_id=implementer_user_id,
                    implementer_name=implementer_name,
                    fecha_primer_contacto=fecha_primer_contacto,
                    tipo_contacto=tipo_contacto or None,
                    tipo_servicio=tipo_servicio_list,
                    integrador_id=integrador_id,
                    integrador_name=integrador_name or None,
                    aplicativo=aplicativo or None,
                    contacts=contacts_crm,
                    contact1=Contact(name=contact_name or 'N/A', phone=contact_phone or 'N/A', email=contact_email or 'sin@email.com'),
                    contact2=Contact(name='N/A', phone='N/A', email='sin@email.com')
                )
                
                doc = client.model_dump()
                doc['created_at'] = doc['created_at'].isoformat()
                await db.clients.insert_one(doc)
                success_count += 1
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='General', value=None,
                    error_type='format',
                    message=f'Fila {row_num}: Error inesperado al procesar esta fila: {str(e)}. Esto puede deberse a datos con formato incorrecto o caracteres especiales no soportados.',
                    suggested_action=f'Revise todos los datos de la fila {row_num}. Asegúrese de que los campos numéricos solo contengan números y que las fechas tengan formato válido.'))
                skipped_count += 1
        
        _total_errors = len([e for e in errors if e.error_type in ('missing', 'duplicate', 'format') or 'crítico' in e.message.lower()])
        
        if success_count == 0 and errors:
            status = 'error'
            message = f'Importación fallida: No se pudo importar ningún registro. Se encontraron {len(errors)} errores en {total_rows} filas procesadas.'
        elif errors:
            status = 'partial'
            warning_count = len([e for e in errors if e.error_type == 'invalid'])
            skip_msg = f', {skipped_count} omitidos por errores' if skipped_count > 0 else ''
            warn_msg = f', {warning_count} advertencias' if warning_count > 0 else ''
            message = f'Importación parcial: {success_count} de {total_rows} registros importados{skip_msg}{warn_msg}.'
        else:
            status = 'success'
            message = f'Importación exitosa: {success_count} clientes importados correctamente de {total_rows} filas procesadas.'
        
        return ImportResult(
            status=status, total_processed=total_rows, success_count=success_count,
            error_count=len(errors), skipped_count=skipped_count, errors=errors[:100], message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='Archivo', value=file.filename, error_type='format',
                message=f'Error crítico al procesar el archivo: {str(e)}. El archivo puede estar corrupto o tener un formato no soportado.',
                suggested_action='Verifique que el archivo no esté dañado. Descargue la plantilla modelo y copie sus datos respetando el formato de cada columna.')],
            message='Error crítico: No se pudo procesar el archivo'
        )


@router.get("/clients/export/pdf")
async def export_clients_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)

    from services.pdf_report import build_corporate_pdf

    clients = await db.clients.find({}, {"_id": 0}).to_list(1000)
    clients.sort(key=lambda c: (c.get("legal_name") or c.get("rif") or "").strip().casefold())

    headers = ['RIF', 'Nombre Jurídico', 'Nombre Fantasía', 'Segmento', 'Contacto']
    rows = []
    for c in clients:
        contact_name = c.get('contact1', {}).get('name', '') if isinstance(c.get('contact1'), dict) else ''
        rows.append([
            c.get('rif', ''),
            c.get('legal_name', ''),
            c.get('fantasy_name', ''),
            c.get('segment', ''),
            contact_name,
        ])

    buffer = build_corporate_pdf(
        title="Clientes",
        headers=headers, rows=rows,
        col_ratios=[1.4, 2.6, 2, 1.2, 2],
    )
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=clientes.pdf"}
    )

