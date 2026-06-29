"""Route module: services.py"""
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
        ca = srv.get('created_at')
        if ca is None:
            srv['created_at'] = datetime.now(timezone.utc)
        elif isinstance(ca, str):
            srv['created_at'] = datetime.fromisoformat(ca)
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
    ca = service.get('created_at')
    if ca is None:
        service['created_at'] = datetime.now(timezone.utc)
    elif isinstance(ca, str):
        service['created_at'] = datetime.fromisoformat(ca)
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

    from services.pdf_report import build_corporate_pdf

    services = await db.services.find({}, {"_id": 0}).to_list(1000)
    services.sort(key=lambda s: (s.get("name") or "").strip().casefold())

    headers = ['Servicio', 'Tipo Corp', 'Setup Conv.', 'Mensual Conv.', 'Setup Out.', 'Mensual Out.']
    rows = []
    for s in services:
        rows.append([
            s.get('name', ''),
            s.get('tipo_corp', ''),
            f"${s.get('setup_cost_conventional', 0):.2f}",
            f"${s.get('monthly_cost_conventional', 0):.2f}",
            f"${s.get('setup_cost_outsourcing', 0):.2f}",
            f"${s.get('monthly_cost_outsourcing', 0):.2f}",
        ])

    buffer = build_corporate_pdf(
        title="Medios de Pago y Servicios",
        headers=headers, rows=rows,
        col_ratios=[2.6, 1.4, 1, 1, 1, 1],
    )
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



# ==================== BANKS POR PRODUCTO ====================

def _normalize(s: str) -> str:
    """Normaliza string: lowercase, sin acentos, espacios colapsados, trim. Espejo de findServicePrice() del frontend."""
    if not s:
        return ""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = " ".join(s.split())
    return s.lower().strip()


async def _bancos_para_servicio(service_id: str, service_name: str) -> list:
    """Devuelve la lista de bancos asociados al servicio dado.
    Cruza por products.service_id (match exacto) y por products.product_name normalizado."""
    target = _normalize(service_name)
    banks = await db.banks.find({}, {"_id": 0}).to_list(None)
    matched = []
    for b in banks:
        for p in (b.get("products") or []):
            if (p.get("service_id") and p["service_id"] == service_id) or (
                _normalize(p.get("product_name", "")) == target
            ):
                matched.append({
                    "bank_id": b.get("bank_id"),
                    "bank_name": b.get("name"),
                    "bank_logo_url": b.get("bank_logo_url") or "",
                    "bank_code": b.get("bank_code") or "",
                    "product_name": p.get("product_name", ""),
                    "vpos_available": bool(p.get("vpos_available")),
                    "gateway_available": bool(p.get("gateway_available")),
                    "mpos_available": bool(p.get("mpos_available")),
                    "link_available": bool(p.get("link_available")),
                })
                break  # un banco se cuenta una vez
    matched.sort(key=lambda x: (x["bank_name"] or "").lower())
    return matched


@router.get("/services/{service_id}/banks")
async def get_banks_for_service(service_id: str, authorization: Optional[str] = Header(None)):
    """Lista de bancos que tienen este producto asociado."""
    await get_current_user(authorization)
    svc = await db.services.find_one({"service_id": service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    banks = await _bancos_para_servicio(service_id, svc.get("name", ""))
    return {
        "service_id": service_id,
        "service_name": svc.get("name", ""),
        "count": len(banks),
        "banks": banks,
    }


@router.get("/services/report/banks-by-product/pdf")
async def report_banks_by_product_pdf(authorization: Optional[str] = Header(None)):
    """Reporte 'Bancos por Producto': PDF elegante con cada producto y los bancos asociados."""
    user = await get_current_user(authorization)
    import weasyprint

    services = await db.services.find(
        {"service_type": "Producto", "application_type": "setup"},
        {"_id": 0},
    ).sort("name", 1).to_list(None)

    # Pre-construir mapa de bancos para todos los productos (1 sola lectura de banks)
    all_banks = await db.banks.find({}, {"_id": 0}).to_list(None)

    def banks_for(svc):
        target = _normalize(svc.get("name", ""))
        sid = svc.get("service_id")
        out = []
        for b in all_banks:
            for p in (b.get("products") or []):
                if (p.get("service_id") and p["service_id"] == sid) or (
                    _normalize(p.get("product_name", "")) == target
                ):
                    comps = []
                    if p.get("vpos_available"):
                        comps.append("VPOS")
                    if p.get("gateway_available"):
                        comps.append("Gateway")
                    if p.get("mpos_available"):
                        comps.append("mPOS")
                    if p.get("link_available"):
                        comps.append("Link")
                    out.append({
                        "name": b.get("name", "—"),
                        "code": b.get("bank_code", "") or "—",
                        "components": comps or ["—"],
                    })
                    break
        out.sort(key=lambda x: x["name"].lower())
        return out

    # Construir bloques HTML
    sections_html = []
    products_with_banks = 0
    products_without_banks = 0
    total_links = 0

    for svc in services:
        banks = banks_for(svc)
        if banks:
            products_with_banks += 1
            total_links += len(banks)
        else:
            products_without_banks += 1

        rows = ""
        if banks:
            for i, b in enumerate(banks, 1):
                comps = " ".join(
                    f'<span class="chip">{c}</span>' for c in b["components"]
                )
                rows += (
                    f'<tr>'
                    f'<td class="num">{i}</td>'
                    f'<td class="bank">{b["name"]}</td>'
                    f'<td class="code">{b["code"]}</td>'
                    f'<td class="comps">{comps}</td>'
                    f'</tr>'
                )
        else:
            rows = '<tr><td colspan="4" class="empty">— Sin bancos asociados —</td></tr>'

        category = svc.get("category", "") or "—"
        app_type_map = {"setup": "Setup", "recurring": "Recurrente", "both": "Setup + Recurrente"}
        app_type = app_type_map.get(svc.get("application_type", ""), "—")

        sections_html.append(f"""
        <div class="product">
          <div class="prod-head">
            <div class="prod-title">{svc.get('name', '—')}</div>
            <div class="prod-meta"><span>Categoría: <b>{category}</b></span><span>Tipo: <b>{app_type}</b></span><span>Bancos: <b>{len(banks)}</b></span></div>
          </div>
          <table>
            <thead><tr><th class="num">#</th><th>Banco</th><th class="code">Código</th><th>Componentes habilitados</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """)

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    user_name = f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email", "")

    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Bancos por Producto</title>
<style>
  @page {{ size: A4; margin: 18mm 14mm; @bottom-right {{ content: "Pág. " counter(page) " / " counter(pages); font-size: 9px; color: #64748b; }} }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #0f172a; font-size: 10.5px; margin:0; }}
  .cover {{ border-left: 5px solid #0ea5e9; padding: 10px 0 14px 16px; margin-bottom: 18px; }}
  .cover h1 {{ font-size: 22px; margin: 0 0 4px 0; color: #0f172a; letter-spacing: -0.3px; }}
  .cover p {{ margin: 2px 0; color: #475569; font-size: 10px; }}
  .summary {{ display: flex; gap: 8px; margin: 0 0 16px 0; }}
  .stat {{ flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; }}
  .stat .lbl {{ font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: .4px; }}
  .stat .val {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-top: 2px; }}
  .stat.green {{ border-left: 4px solid #10b981; }}
  .stat.amber {{ border-left: 4px solid #f59e0b; }}
  .stat.blue  {{ border-left: 4px solid #0ea5e9; }}
  .stat.slate {{ border-left: 4px solid #64748b; }}
  .product {{ margin-bottom: 12px; page-break-inside: avoid; }}
  .prod-head {{ background: #f1f5f9; border-left: 3px solid #0ea5e9; padding: 6px 10px; border-radius: 4px 4px 0 0; }}
  .prod-title {{ font-size: 12px; font-weight: 700; color: #0c4a6e; }}
  .prod-meta {{ font-size: 9px; color: #475569; margin-top: 2px; display: flex; gap: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 0; }}
  thead th {{ background: #0c4a6e; color: white; font-size: 9.5px; padding: 5px 8px; text-align: left; font-weight: 600; }}
  thead th.num, thead th.code {{ text-align: center; }}
  tbody td {{ padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 10px; vertical-align: middle; }}
  td.num {{ text-align: center; color: #64748b; width: 28px; }}
  td.bank {{ font-weight: 600; color: #0f172a; }}
  td.code {{ text-align: center; color: #475569; width: 70px; font-family: monospace; }}
  td.empty {{ text-align: center; color: #94a3b8; font-style: italic; padding: 10px; }}
  .chip {{ display: inline-block; padding: 1px 6px; margin-right: 3px; border-radius: 10px; background: #ecfeff; color: #0e7490; font-size: 8.5px; border: 1px solid #a5f3fc; }}
  .footer {{ margin-top: 18px; padding-top: 8px; border-top: 1px solid #e2e8f0; font-size: 8.5px; color: #94a3b8; text-align: center; }}
</style></head>
<body>
  <div class="cover">
    <h1>Bancos por Producto</h1>
    <p>Reporte de asociaciones entre productos del catálogo (categoría Producto · tipo Setup) y las entidades bancarias.</p>
    <p>Generado el <b>{now_str}</b> · Por <b>{user_name}</b></p>
  </div>

  <div class="summary">
    <div class="stat slate"><div class="lbl">Productos totales</div><div class="val">{len(services)}</div></div>
    <div class="stat green"><div class="lbl">Con bancos asociados</div><div class="val">{products_with_banks}</div></div>
    <div class="stat amber"><div class="lbl">Sin asociar</div><div class="val">{products_without_banks}</div></div>
    <div class="stat blue"><div class="lbl">Asociaciones totales</div><div class="val">{total_links}</div></div>
  </div>

  {''.join(sections_html)}

  <div class="footer">MegaNexus · Reporte generado automáticamente · Documento confidencial</div>
</body></html>"""

    pdf_bytes = weasyprint.HTML(string=html).write_pdf()
    filename = f"bancos_por_producto_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
