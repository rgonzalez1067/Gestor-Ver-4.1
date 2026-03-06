"""Route module: clients.py"""
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os
import re
import shutil

from config import db, get_current_user, UPLOADS_DIR
from models import *

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

router = APIRouter()
logger = logging.getLogger(__name__)

# Directorio para documentos RIF
RIF_DOCS_DIR = UPLOADS_DIR / "rif_documents"
RIF_DOCS_DIR.mkdir(exist_ok=True)

ALLOWED_RIF_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}


def extract_text_from_pdf(content: bytes) -> str:
    if not PdfReader:
        raise HTTPException(status_code=500, detail="PyPDF2 no disponible")
    pdf_reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in pdf_reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text


def extract_text_from_image(content: bytes) -> str:
    if not TESSERACT_AVAILABLE:
        raise HTTPException(status_code=500, detail="pytesseract no disponible para OCR de imágenes")
    image = Image.open(io.BytesIO(content))
    text = pytesseract.image_to_string(image, lang='spa')
    return text


def parse_rif_data(text: str) -> dict:
    """Extrae RIF, razón social y dirección fiscal del texto"""
    if not text.strip():
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del documento. Verifique que sea un RIF válido.")

    # Extraer RIF: patrón [JGVEP] seguido de 9 dígitos
    rif_match = re.search(r'([JGVEP]\d{9})', text)
    rif = rif_match.group(1) if rif_match else None
    if not rif:
        raise HTTPException(status_code=400, detail="No se encontró un código RIF válido en el documento")

    # Formatear RIF: J-12345678-9
    rif_formatted = f"{rif[0]}-{rif[1:9]}-{rif[9]}" if len(rif) == 10 else rif

    # Extraer Razón Social
    legal_name = ""
    for line in text.split('\n'):
        if rif in line:
            after_rif = line.split(rif, 1)[1].strip()
            if after_rif:
                legal_name = after_rif.strip()
            break

    # Extraer Dirección Fiscal
    address = ""
    domicilio_match = re.search(r'DOMICILIO\s+FISCAL\s+(.*?)(?=FECHA\s+DE)', text, re.DOTALL | re.IGNORECASE)
    if domicilio_match:
        addr_raw = domicilio_match.group(1).strip()
        address = re.sub(r'\s+', ' ', addr_raw).strip()

    return {"rif": rif_formatted, "legal_name": legal_name, "address": address}


@router.post("/clients/parse-rif")
async def parse_rif_document(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Extrae datos del RIF (PDF o imagen) y verifica duplicados"""
    await get_current_user(authorization)

    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ALLOWED_RIF_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Formato no soportado. Use: {', '.join(ALLOWED_RIF_EXTENSIONS)}")

    content = await file.read()

    try:
        if ext == '.pdf':
            text = extract_text_from_pdf(content)
        else:
            text = extract_text_from_image(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el documento: {str(e)}")

    data = parse_rif_data(text)

    # Verificar duplicados
    rif_digits = re.sub(r'[^0-9]', '', data["rif"])
    existing_clients = []
    cursor = db.clients.find({"rif": {"$regex": rif_digits[-8:], "$options": "i"}}, {"_id": 0, "client_id": 1, "rif": 1, "legal_name": 1, "fantasy_name": 1, "sucursal": 1})
    async for doc in cursor:
        existing_clients.append(doc)

    return {
        **data,
        "is_duplicate": len(existing_clients) > 0,
        "existing_clients": existing_clients,
        "source_format": ext.replace('.', '').upper()
    }


@router.post("/clients/{client_id}/update-from-rif")
async def update_client_from_rif(client_id: str, file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Escanea RIF, extrae datos, actualiza cliente y archiva documento"""
    current_user = await get_current_user(authorization)

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ALLOWED_RIF_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Formato no soportado. Use: {', '.join(ALLOWED_RIF_EXTENSIONS)}")

    content = await file.read()

    # Extraer texto
    try:
        if ext == '.pdf':
            text = extract_text_from_pdf(content)
        else:
            text = extract_text_from_image(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el documento: {str(e)}")

    scanned = parse_rif_data(text)

    # Datos actuales para comparación
    current_data = {
        "rif": client.get("rif", ""),
        "legal_name": client.get("legal_name", ""),
        "address": client.get("address", client.get("fiscal_address", ""))
    }

    # Guardar documento RIF
    safe_rif = re.sub(r'[^a-zA-Z0-9]', '', scanned["rif"])
    rif_filename = f"{client_id}_{safe_rif}_rif{ext}"
    rif_path = RIF_DOCS_DIR / rif_filename
    with open(rif_path, "wb") as f:
        f.write(content)

    rif_url = f"/uploads/rif_documents/{rif_filename}"

    # Actualizar cliente en BD
    update_fields = {
        "rif": scanned["rif"],
        "legal_name": scanned["legal_name"],
        "fiscal_address": scanned["address"],
        "rif_document_url": rif_url,
        "rif_document_filename": file.filename,
        "rif_updated_at": datetime.now(timezone.utc).isoformat(),
        "rif_updated_by": current_user.get("email", "unknown"),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    # También actualizar 'address' si estaba vacío
    if not client.get("address"):
        update_fields["address"] = scanned["address"]

    await db.clients.update_one({"client_id": client_id}, {"$set": update_fields})

    return {
        "message": "Cliente actualizado exitosamente desde RIF",
        "previous_data": current_data,
        "updated_data": scanned,
        "rif_document_url": rif_url,
        "source_format": ext.replace('.', '').upper()
    }


@router.get("/clients/{client_id}/rif-document")
async def download_rif_document(client_id: str, authorization: Optional[str] = Header(None)):
    """Descarga el documento RIF archivado del cliente"""
    await get_current_user(authorization)

    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rif_url = client.get("rif_document_url")
    if not rif_url:
        raise HTTPException(status_code=404, detail="Este cliente no tiene un documento RIF archivado")

    file_path = UPLOADS_DIR / rif_url.replace("/uploads/", "")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo RIF no encontrado en el servidor")

    ext = file_path.suffix.lower()
    content_types = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
    content_type = content_types.get(ext, 'application/octet-stream')

    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=client.get("rif_document_filename", f"RIF_{client.get('rif', 'unknown')}{ext}")
    )

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

