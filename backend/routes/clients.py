"""Route module: clients.py"""
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
import re

router = APIRouter()

# ==================== CLIENTS ENDPOINTS ====================

@router.post("/clients/parse-rif")
async def parse_rif_pdf(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Extrae datos del RIF Digital (PDF SENIAT) y verifica duplicados"""
    await get_current_user(authorization)
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    
    content = await file.read()
    
    try:
        pdf_reader = PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += (page.extract_text() or "") + "\n"
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer el PDF: {str(e)}")
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del PDF. Verifique que sea un RIF Digital válido.")
    
    # Extraer RIF: patrón [JGVEP] seguido de 9 dígitos
    rif_match = re.search(r'([JGVEP]\d{9})', text)
    rif = rif_match.group(1) if rif_match else None
    
    if not rif:
        raise HTTPException(status_code=400, detail="No se encontró un código RIF válido en el documento")
    
    # Formatear RIF: J-XXXXXXXXX-X → J-12345678-9
    rif_formatted = f"{rif[0]}-{rif[1:9]}-{rif[9]}" if len(rif) == 10 else rif
    
    # Extraer Razón Social: texto en la misma línea después del RIF
    legal_name = ""
    for line in text.split('\n'):
        if rif in line:
            after_rif = line.split(rif, 1)[1].strip()
            if after_rif:
                legal_name = after_rif.strip()
            break
    
    # Extraer Dirección Fiscal: todo después de "DOMICILIO FISCAL" hasta "FECHA DE"
    address = ""
    domicilio_match = re.search(r'DOMICILIO\s+FISCAL\s+(.*?)(?=FECHA\s+DE)', text, re.DOTALL | re.IGNORECASE)
    if domicilio_match:
        addr_raw = domicilio_match.group(1).strip()
        # Limpiar saltos de línea y espacios múltiples
        address = re.sub(r'\s+', ' ', addr_raw).strip()
    
    # Verificar duplicados en BD
    existing_clients = []
    cursor = db.clients.find({"rif": {"$regex": rif[1:9], "$options": "i"}}, {"_id": 0, "client_id": 1, "rif": 1, "legal_name": 1, "fantasy_name": 1, "sucursal": 1})
    async for doc in cursor:
        existing_clients.append(doc)
    
    return {
        "rif": rif_formatted,
        "legal_name": legal_name,
        "address": address,
        "is_duplicate": len(existing_clients) > 0,
        "existing_clients": existing_clients
    }

@router.post("/clients")
async def create_client(client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    # Validar unicidad RIF + Sucursal
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal"},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    # Generate contacts IDs if not present
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    client = Client(**data)
    doc = client.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/clients")
async def get_clients(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    clients = await db.clients.find({}, {"_id": 0}).to_list(5000)
    return clients

@router.get("/clients/search")
async def search_clients(q: str = "", authorization: Optional[str] = Header(None)):
    """Búsqueda server-side de clientes por nombre o RIF"""
    await get_current_user(authorization)
    if not q or len(q) < 2:
        clients = await db.clients.find({}, {"_id": 0}).to_list(50)
        return clients
    query = {
        "$or": [
            {"fantasy_name": {"$regex": q, "$options": "i"}},
            {"legal_name": {"$regex": q, "$options": "i"}},
            {"rif": {"$regex": q, "$options": "i"}}
        ]
    }
    clients = await db.clients.find(query, {"_id": 0}).to_list(100)
    return clients

@router.get("/clients/template")
async def get_clients_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación para clientes"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    data = {
        'RIF': ['J-12345678-9', 'J-98765432-1', 'J-11223344-5'],
        'Sucursal': ['Principal', 'Sede Norte', 'Principal'],
        'Nombre Jurídico': ['Empresa Demo CA', 'Empresa Demo CA', 'Otra Empresa SRL'],
        'Nombre Fantasía': ['DemoCorp', 'DemoCorp Norte', 'OtraCorp'],
        'Segmento': ['Corporativo', 'Corporativo', 'Pymes'],
        'Dirección': ['Av. Libertador, Edif. Torre X, Caracas', 'CC San Ignacio, Valencia', ''],
        'Contacto Nombre': ['Carlos', 'Ana', 'Pedro'],
        'Contacto Apellido': ['Pérez', 'Ruiz', 'Gómez'],
        'Contacto Teléfono': ['0412-1234567', '0416-9876543', '0414-1112233'],
        'Contacto Email': ['carlos@demo.com', 'ana@demo.com', 'pedro@otra.com'],
        'Contacto Rol': ['Administrativo', 'Técnico', 'Financiero']
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        info_data = {
            'Campo': ['RIF *', 'Sucursal', 'Nombre Jurídico *', 'Nombre Fantasía', 'Segmento',
                       'Dirección', 'Contacto Nombre', 'Contacto Apellido', 'Contacto Teléfono',
                       'Contacto Email', 'Contacto Rol'],
            'Descripción': [
                'RIF del cliente (obligatorio)', 'Nombre de la sucursal (def: Principal)',
                'Razón social (obligatorio)', 'Nombre comercial',
                'Pymes, Corporativo o Mixto (def: Pymes)',
                'Dirección fiscal', 'Nombre del contacto principal',
                'Apellido del contacto', 'Teléfono del contacto',
                'Email del contacto', 'Administrativo, Financiero, Técnico, Cuentas por Pagar, Operativo'
            ],
            'Obligatorio': ['Sí', 'No', 'Sí', 'No', 'No', 'No', 'No', 'No', 'No', 'No', 'No'],
            'Ejemplo': ['J-12345678-9', 'Principal', 'Empresa Demo CA', 'DemoCorp', 'Corporativo',
                        'Av. Libertador...', 'Carlos', 'Pérez', '0412-1234567', 'carlos@demo.com', 'Administrativo']
        }
        pd.DataFrame(info_data).to_excel(writer, index=False, sheet_name='Instrucciones')
        
        roles_data = {
            'Roles Válidos': ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo'],
            'Segmentos Válidos': ['Pymes', 'Corporativo', 'Mixto', '', ''],
            'Nota': [
                'RIF + Sucursal deben ser únicos',
                'Se permite el mismo RIF con diferente Sucursal',
                'Los campos marcados con * son obligatorios',
                'Si no indica segmento, se asigna "Pymes"',
                'Si no indica rol, se asigna "Administrativo"'
            ]
        }
        pd.DataFrame(roles_data).to_excel(writer, index=False, sheet_name='Valores Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_clientes.xlsx"}
    )

@router.get("/clients/{client_id}")
async def get_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put("/clients/{client_id}")
async def update_client(client_id: str, client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    # Validar unicidad RIF + Sucursal (excluyendo el propio registro)
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal", "client_id": {"$ne": client_id}},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe otro cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    result = await db.clients.update_one(
        {"client_id": client_id},
        {"$set": data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_client(client_id, authorization)

@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones vinculadas
    quotes_count = await db.quotes.count_documents({"client_id": client_id})
    if quotes_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el cliente porque tiene {quotes_count} cotización(es) vinculada(s). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.clients.delete_one({"client_id": client_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    # También eliminar los logs de bitácora del cliente
    await db.client_logs.delete_many({"client_id": client_id})
    return {"message": "Cliente eliminado exitosamente"}

# ==================== BITÁCORA DE CLIENTES ====================

@router.get("/clients/{client_id}/logs")
async def get_client_logs(client_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene la bitácora de eventos de un cliente (ordenada por fecha desc)"""
    await get_current_user(authorization)
    logs = await db.client_logs.find({"client_id": client_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return logs

@router.post("/clients/{client_id}/logs")
async def create_client_log(client_id: str, log_data: ClientLogCreate, authorization: Optional[str] = Header(None)):
    """Crea una entrada en la bitácora de un cliente (no editable)"""
    current_user = await get_current_user(authorization)
    
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    log_entry = {
        "log_id": f"log_{uuid.uuid4().hex[:12]}",
        "client_id": client_id,
        "contact_date": log_data.contact_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "detail": log_data.detail,
        "action": log_data.action,
        "follow_up_date": log_data.follow_up_date,
        "is_completed": False,
        "created_by": current_user.get("email", "unknown"),
        "created_by_name": current_user.get("full_name", current_user.get("email", "")),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.client_logs.insert_one(log_entry)
    log_entry.pop("_id", None)
    return log_entry

@router.patch("/clients/logs/{log_id}/complete")
async def toggle_log_complete(log_id: str, authorization: Optional[str] = Header(None)):
    """Marca/desmarca un log como completado"""
    await get_current_user(authorization)
    log = await db.client_logs.find_one({"log_id": log_id}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Entrada de bitácora no encontrada")
    new_status = not log.get("is_completed", False)
    await db.client_logs.update_one({"log_id": log_id}, {"$set": {"is_completed": new_status}})
    return {"log_id": log_id, "is_completed": new_status}

