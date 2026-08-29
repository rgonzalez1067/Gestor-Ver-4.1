"""Route module: clients.py"""
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
import shutil

from config import db, get_current_user, require_permission, UPLOADS_DIR
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

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

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
    # Si PyPDF2 no extrajo texto útil, intentar OCR sobre las imágenes del PDF
    if not text.strip() and TESSERACT_AVAILABLE and PDF2IMAGE_AVAILABLE:
        try:
            images = convert_from_bytes(content, dpi=300)
            for img in images:
                text += pytesseract.image_to_string(img, lang='spa') + "\n"
        except Exception as e:
            logger.warning(f"OCR fallback para PDF falló: {e}")
    return text


def extract_text_from_image(content: bytes) -> str:
    if not TESSERACT_AVAILABLE:
        raise HTTPException(status_code=500, detail="pytesseract no disponible para OCR de imágenes")
    image = Image.open(io.BytesIO(content))
    text = pytesseract.image_to_string(image, lang='spa')
    return text


def sanitize_rif(rif_raw: str) -> str:
    """Limpia el RIF removiendo guiones, espacios y caracteres especiales. J-00000000-0 → J000000000"""
    if not rif_raw:
        return rif_raw
    return re.sub(r'[^A-Za-z0-9]', '', rif_raw).upper()


# ==================== JERARQUÍA RIF (Principal / Sucursales) ====================

# Campos que una sucursal HIJA hereda (snapshot) del Principal al crearse.
# Tras el snapshot, cada campo es editable localmente sin afectar al Principal.
INHERITED_BRANCH_FIELDS = [
    # Estatus y Definición Legal
    "condicion", "legal_name", "fantasy_name", "segment",
    # Capacidad Operativa
    "cantidad_tiendas", "cantidad_cajas",
    # Gestión y Soluciones
    "tipo_servicio", "integrador_id", "integrador_name", "aplicativo",
    "implementer_user_id", "implementer_name",
    "coordinator_user_id", "coordinator_name", "modelo_impresora_fiscal",
    # Dirección
    "address", "branch_address",
    # Información Adicional
    "categoria_comercial", "grupo_economico",
    "referidor", "referidor_tipo", "referidor_id", "referidor_nombre",
    "ejecutivo_propietario", "ejecutivo_user_id",
    "fecha_primer_contacto", "tipo_contacto",
]


def _is_principal_sucursal(sucursal: Optional[str]) -> bool:
    return (sucursal or "Principal").strip().lower() == "principal"


async def _find_principal_for_rif(rif: str, exclude_id: Optional[str] = None):
    """Devuelve el documento Principal (matriz) para un RIF, o None si no existe."""
    query = {"rif": rif, "$or": [{"is_branch": {"$ne": True}}, {"sucursal": {"$regex": r"^\s*principal\s*$", "$options": "i"}}]}
    if exclude_id:
        query["client_id"] = {"$ne": exclude_id}
    return await db.clients.find_one(query, {"_id": 0})


async def _derive_hierarchy(rif: str, sucursal: Optional[str], self_client_id: Optional[str] = None):
    """Determina (parent_client_id, is_branch) para un registro según su RIF+sucursal.
    - sucursal 'Principal' → (None, False)
    - sucursal con nombre y existe Principal del RIF → (principal_id, True)
    - sucursal con nombre pero aún no hay Principal → (None, False) (registro independiente)
    """
    if _is_principal_sucursal(sucursal):
        return None, False
    principal = await _find_principal_for_rif(rif, exclude_id=self_client_id)
    if principal:
        return principal["client_id"], True
    return None, False


async def _consolidated_contacts_for_client(client: dict):
    """Contactos consolidados de un cliente: los del Principal (globales) + los
    locales de la sucursal (si el cliente es una hija). Cada contacto lleva 'scope'
    ('principal' | 'local') y 'sucursal'. No muta los documentos originales."""
    principal = client
    if client.get("is_branch") and client.get("parent_client_id"):
        p = await db.clients.find_one({"client_id": client["parent_client_id"]}, {"_id": 0})
        if p:
            principal = p

    out = []

    def _emit(src_doc, scope):
        for c in (src_doc.get("contacts") or []):
            if not (c.get("email") or "").strip():
                continue
            item = dict(c)
            item["scope"] = scope
            item["sucursal"] = src_doc.get("sucursal") or "Principal"
            out.append(item)

    _emit(principal, "principal")
    if client.get("client_id") != principal.get("client_id"):
        _emit(client, "local")

    # Nivel 1 (herencia): contactos del Grupo Económico vinculado al Principal.
    # Se marcan como scope='grupo' y no editables desde la ficha del cliente/sucursal.
    gid = principal.get("grupo_economico_id")
    if gid:
        grp = await db.economic_groups.find_one(
            {"group_id": gid}, {"_id": 0, "name": 1, "contacts": 1}
        )
        if grp:
            for c in (grp.get("contacts") or []):
                if not (c.get("email") or "").strip():
                    continue
                item = dict(c)
                item["scope"] = "grupo"
                item["sucursal"] = "Grupo Económico"
                item["grupo_economico_name"] = grp.get("name")
                item["source_group_id"] = gid
                out.append(item)
    return out, principal


def parse_rif_data(text: str) -> dict:
    """Extrae RIF, razón social y dirección fiscal del texto.

    Soporta DOS diseños del RIF (SENIAT):
    - ANTIGUO: el RIF y la razón social van en la MISMA línea, y la dirección
      viene tras 'DOMICILIO FISCAL' (sin dos puntos).
    - NUEVO (RIF Digital v2.0): etiqueta 'RIF:' + código en una línea, la razón
      social en la línea SIGUIENTE, y 'DOMICILIO FISCAL:' (con dos puntos) con la
      dirección en líneas posteriores hasta 'DATOS DE REGISTRO Y VIGENCIA'."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="No se pudo extraer texto del documento. Verifique que sea un RIF válido.")

    # Correcciones comunes de OCR para la letra del RIF
    OCR_CORRECTIONS = {'3': 'J', '1': 'J', 'I': 'J', '0': 'G', '6': 'G'}

    def _fix_letter(ch: str) -> str:
        ch = (ch or '').upper()
        if ch not in 'JGVEP' and ch in OCR_CORRECTIONS:
            ch = OCR_CORRECTIONS[ch]
        return ch

    rif = None
    legal_name = ""
    rif_line_idx = None

    lines = text.split('\n')

    # Estrategia NUEVA (RIF Digital v2.0): etiqueta 'RIF:' seguida del código.
    for i, line in enumerate(lines):
        m = re.search(r'RIF\s*:\s*(\S)\s*(\d{9})', line, re.IGNORECASE)
        if m:
            first_char = _fix_letter(m.group(1))
            if first_char in 'JGVEP':
                rif = first_char + m.group(2)
                rif_line_idx = i
                after = line[m.end():].strip()
                if after:
                    legal_name = after  # (diseño antiguo con etiqueta: nombre en misma línea)
                break

    # Estrategia 1 (diseño antiguo): RIF en la línea posterior a "REGISTRO ÚNICO..."
    if not rif:
        for i, line in enumerate(lines):
            if re.search(r'REGISTRO\s+.{0,10}NICO.*FISCAL', line, re.IGNORECASE):
                for j, next_line in enumerate(lines[i+1:i+4], start=i+1):
                    m = re.match(r'\s*([JGVEP]\d{9})\s+(.*)', next_line)
                    if m:
                        rif = m.group(1)
                        legal_name = m.group(2).strip()
                        rif_line_idx = j
                        break
                    m = re.match(r'\s*(\S)(\d{9})\s+(.*)', next_line)
                    if m:
                        first_char = _fix_letter(m.group(1))
                        if first_char in 'JGVEP':
                            rif = first_char + m.group(2)
                            legal_name = m.group(3).strip()
                            rif_line_idx = j
                            break
                break

    # Estrategia 2 (fallback): línea que EMPIECE con el patrón RIF
    if not rif:
        for i, line in enumerate(lines):
            m = re.match(r'\s*([JGVEP]\d{9})\s+(.*)', line)
            if m:
                rif = m.group(1)
                legal_name = m.group(2).strip()
                rif_line_idx = i
                break

    # Estrategia 3 (último recurso): patrón en cualquier parte, excluyendo comprobante
    if not rif:
        for i, line in enumerate(lines):
            if re.search(r'COMPROBANTE', line, re.IGNORECASE):
                continue
            rif_match = re.search(r'([JGVEP]\d{9})', line)
            if rif_match:
                rif = rif_match.group(1)
                rif_line_idx = i
                after_rif = line.split(rif, 1)[1].strip()
                if after_rif:
                    legal_name = after_rif
                break

    if not rif:
        raise HTTPException(status_code=400, detail="No se encontró un código RIF válido en el documento")

    # Razón social (diseño NUEVO): si quedó vacía, tomar la línea siguiente a la
    # del RIF, saltando etiquetas/encabezados de sección.
    if not legal_name and rif_line_idx is not None:
        for cand_line in lines[rif_line_idx + 1: rif_line_idx + 4]:
            cand = cand_line.strip()
            if not cand:
                continue
            if re.search(r'DOMICILIO|FISCAL|IDENTIFICACI|DATOS\s+DE|FECHA\s+DE|COMPROBANTE|DIVISI[ÓO]N|REGISTRO', cand, re.IGNORECASE):
                continue
            legal_name = cand
            break

    # Formatear RIF: sin guiones ni caracteres especiales
    rif_clean = sanitize_rif(rif)

    # Limpiar razón social: remover etiquetas que puedan quedar pegadas
    legal_name = re.split(r'\s*FECHA\s+DE', legal_name, flags=re.IGNORECASE)[0].strip()
    legal_name = re.split(r'\s*DOMICILIO\s+FISCAL', legal_name, flags=re.IGNORECASE)[0].strip()

    # Extraer Dirección Fiscal (tolerante a ':' del nuevo diseño y a múltiples
    # terminadores para no arrastrar la sección 'DATOS DE REGISTRO Y VIGENCIA').
    address = ""
    domicilio_match = re.search(
        r'DOMICILIO\s+FISCAL\s*:?\s*(.*?)(?=DATOS\s+DE\s+REGISTRO|FECHA\s+DE|N[°ºo]\s*COMPROBANTE|DIVISI[ÓO]N\s+DE|$)',
        text, re.DOTALL | re.IGNORECASE,
    )
    if domicilio_match:
        addr_raw = domicilio_match.group(1).strip()
        address = re.sub(r'\s+', ' ', addr_raw).strip()

    return {"rif": rif_clean, "legal_name": legal_name, "address": address}


@router.post("/clients/parse-rif")
async def parse_rif_document(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Extrae datos del RIF (PDF o imagen) y verifica duplicados"""
    await require_permission(authorization, "clientes", "edit")

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
    cursor = db.clients.find({"rif": {"$regex": rif_digits[-8:], "$options": "i"}}, {"_id": 0, "client_id": 1, "rif": 1, "legal_name": 1, "fantasy_name": 1, "sucursal": 1}).limit(100)
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
    current_user = await require_permission(authorization, "clientes", "edit")

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
    from services.pdf_storage import save_pdf_dual
    save_pdf_dual(rif_path, content, f"rif_documents/{rif_filename}")

    rif_url = f"/uploads/rif_documents/{rif_filename}"

    # Actualizar cliente en BD
    update_fields = {
        "rif": scanned["rif"],
        "legal_name": scanned["legal_name"],
        "address": scanned["address"],
        "fiscal_address": scanned["address"],
        "rif_document_url": rif_url,
        "rif_document_filename": file.filename,
        "rif_updated_at": datetime.now(timezone.utc).isoformat(),
        "rif_updated_by": current_user.get("email", "unknown"),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

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

    rel = rif_url.replace("/api/uploads/", "").replace("/uploads/", "")
    ext = os.path.splitext(rel)[1].lower()
    content_types = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
    content_type = content_types.get(ext, 'application/octet-stream')
    dl_name = client.get("rif_document_filename", f"RIF_{client.get('rif', 'unknown')}{ext}")

    # 1) Object Storage (persistente cross-deploy)
    from services.pdf_storage import get_pdf_from_storage
    res = get_pdf_from_storage(rel)
    if res is not None:
        data_bytes, ctype = res
        return Response(
            content=data_bytes,
            media_type=ctype or content_type,
            headers={"Content-Disposition": f'inline; filename="{dl_name}"'},
        )

    # 2) Fallback a disco local (legacy)
    file_path = UPLOADS_DIR / rel
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo RIF no encontrado en el servidor")
    return FileResponse(path=str(file_path), media_type=content_type, filename=dl_name)

async def _sync_group_name(data: dict):
    """Normaliza grupo_economico_id y sincroniza el nombre visible (grupo_economico)
    desde la tabla maestra de Grupos Económicos."""
    gid = (data.get("grupo_economico_id") or "").strip() or None
    data["grupo_economico_id"] = gid
    if gid:
        g = await db.economic_groups.find_one({"group_id": gid}, {"_id": 0, "name": 1})
        if g:
            data["grupo_economico"] = g["name"]
        else:
            data["grupo_economico_id"] = None


@router.post("/clients")
async def create_client(client_data: ClientCreate, authorization: Optional[str] = Header(None)):
    await require_permission(authorization, "clientes", "edit")
    # Sanitizar RIF
    client_data.rif = sanitize_rif(client_data.rif)
    # Validar unicidad RIF + Sucursal
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal"},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    await _sync_group_name(data)
    # Generate contacts IDs if not present
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    # Derivar jerarquía Principal/Sucursal por RIF
    data["parent_client_id"], data["is_branch"] = await _derive_hierarchy(
        client_data.rif, client_data.sucursal
    )
    client = Client(**data)
    doc = client.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/clients")
async def get_clients(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    clients = await db.clients.find({}, {"_id": 0}).to_list(2000)
    return clients


# ==================== ENDPOINTS DE JERARQUÍA (Principal / Sucursales) ====================

def _client_brief(c: dict) -> dict:
    return {
        "client_id": c.get("client_id"),
        "rif": c.get("rif"),
        "sucursal": c.get("sucursal") or "Principal",
        "legal_name": c.get("legal_name"),
        "fantasy_name": c.get("fantasy_name"),
        "condicion": c.get("condicion"),
        "is_branch": bool(c.get("is_branch")),
        "parent_client_id": c.get("parent_client_id"),
        "contacts_count": len([x for x in (c.get("contacts") or []) if (x.get("email") or "").strip()]),
    }


@router.get("/clients/by-rif")
async def get_clients_by_rif(rif: str = "", authorization: Optional[str] = Header(None)):
    """Devuelve el árbol {principal, branches[]} de un RIF. Usado por el Cotizador
    para desplegar el selector de sucursal cuando existen sucursales adscritas."""
    await get_current_user(authorization)
    rif_s = sanitize_rif(rif)
    if not rif_s:
        return {"rif": rif_s, "principal": None, "branches": [], "has_branches": False}
    docs = await db.clients.find({"rif": rif_s}, {"_id": 0}).to_list(1000)
    if not docs:
        return {"rif": rif_s, "principal": None, "branches": [], "has_branches": False}
    principal = None
    for d in docs:
        if not d.get("is_branch") and not d.get("parent_client_id"):
            principal = d
            break
    if principal is None:
        # Fallback: sucursal 'Principal' o el más antiguo
        principal = next((d for d in docs if _is_principal_sucursal(d.get("sucursal"))), None)
        if principal is None:
            principal = sorted(docs, key=lambda x: x.get("created_at") or "")[0]
    branches = [d for d in docs if d.get("client_id") != principal.get("client_id")]
    branches.sort(key=lambda x: (x.get("sucursal") or "").lower())
    return {
        "rif": rif_s,
        "principal": _client_brief(principal),
        "branches": [_client_brief(b) for b in branches],
        "has_branches": len(branches) > 0,
    }


@router.get("/clients/{client_id}/branches")
async def get_client_branches(client_id: str, authorization: Optional[str] = Header(None)):
    """Sucursales del grupo de un cliente (resuelve el Principal por RIF)."""
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "rif": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return await get_clients_by_rif(rif=client.get("rif", ""), authorization=authorization)


@router.get("/clients/{client_id}/consolidated-contacts")
async def get_consolidated_contacts(client_id: str, authorization: Optional[str] = Header(None)):
    """Contactos elegibles para envíos: contactos del Principal (globales) +
    contactos locales de la sucursal seleccionada (si el cliente es una hija)."""
    await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    contacts, principal = await _consolidated_contacts_for_client(client)
    return {
        "client_id": client_id,
        "principal_client_id": principal.get("client_id"),
        "is_branch": bool(client.get("is_branch")),
        "contacts": contacts,
    }


@router.post("/clients/{parent_id}/branches")
async def create_branch(parent_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Crea una sucursal hija adscrita a un Principal. Hereda (snapshot) los campos
    operativos del Principal como valores por defecto; luego es 100% editable local.
    Los contactos del Principal NO se copian (son globales); la sucursal parte con
    sus propios contactos locales (los que vengan en el payload, o ninguno).
    Acepta payload PARCIAL: los campos no provistos (incl. legal_name/fantasy_name)
    se heredan del Principal."""
    await require_permission(authorization, "clientes", "edit")

    principal = await db.clients.find_one({"client_id": parent_id}, {"_id": 0})
    if not principal:
        raise HTTPException(status_code=404, detail="Cliente Principal no encontrado")

    # Resolver el verdadero Principal (si se pasó el id de una hija)
    if principal.get("is_branch") and principal.get("parent_client_id"):
        real = await db.clients.find_one({"client_id": principal["parent_client_id"]}, {"_id": 0})
        if real:
            principal = real

    body = body or {}
    sucursal = (body.get("sucursal") or "").strip()
    if not sucursal or _is_principal_sucursal(sucursal):
        raise HTTPException(status_code=400, detail="Debe indicar un nombre de sucursal distinto de 'Principal'.")

    rif = principal.get("rif")
    existing = await db.clients.find_one({"rif": rif, "sucursal": sucursal}, {"_id": 0, "client_id": 1})
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe la sucursal '{sucursal}' para el RIF {rif}")

    # Snapshot de herencia: campos NO provistos (o vacíos) en el body se heredan del Principal
    def _empty(v):
        return v is None or v == "" or (isinstance(v, list) and len(v) == 0)

    data = dict(body)
    for f in INHERITED_BRANCH_FIELDS:
        if f not in data or _empty(data.get(f)):
            data[f] = principal.get(f)
    # legal_name/fantasy_name son obligatorios en el modelo → heredar si faltan
    for req_f in ("legal_name", "fantasy_name"):
        if _empty(data.get(req_f)):
            data[req_f] = principal.get(req_f) or ""
    data["rif"] = rif
    data["sucursal"] = sucursal
    data["parent_client_id"] = principal["client_id"]
    data["is_branch"] = True
    # Construir vía ClientCreate para validar/normalizar, luego promover a Client
    branch_in = ClientCreate(**{k: v for k, v in data.items() if k in ClientCreate.model_fields})
    branch_dict = branch_in.model_dump()
    branch_dict["parent_client_id"] = principal["client_id"]
    branch_dict["is_branch"] = True
    for c in branch_dict.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"

    branch = Client(**branch_dict)
    doc = branch.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.clients.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/admin/clients/migrate-hierarchy")
async def migrate_client_hierarchy(authorization: Optional[str] = Header(None)):
    """Migración idempotente: agrupa clientes por RIF y establece el vínculo
    Principal/Sucursal (parent_client_id + is_branch). Si un grupo no tiene
    'Principal', promueve el registro más antiguo."""
    await require_permission(authorization, "clientes", "edit")
    return await run_client_hierarchy_migration()


async def run_client_hierarchy_migration():
    """Lógica de migración jerárquica (reutilizable en startup y endpoint)."""
    all_clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "rif": 1, "sucursal": 1, "created_at": 1}).to_list(5000)
    groups = {}
    for c in all_clients:
        groups.setdefault(c.get("rif") or "", []).append(c)

    promoted = 0
    branches_linked = 0
    principals = 0
    for rif, docs in groups.items():
        if not rif:
            continue
        principal = next((d for d in docs if _is_principal_sucursal(d.get("sucursal"))), None)
        if principal is None:
            principal = sorted(docs, key=lambda x: x.get("created_at") or "")[0]
            await db.clients.update_one(
                {"client_id": principal["client_id"]},
                {"$set": {"sucursal": "Principal", "is_branch": False, "parent_client_id": None}}
            )
            promoted += 1
        else:
            await db.clients.update_one(
                {"client_id": principal["client_id"]},
                {"$set": {"is_branch": False, "parent_client_id": None}}
            )
        principals += 1
        for d in docs:
            if d["client_id"] == principal["client_id"]:
                continue
            await db.clients.update_one(
                {"client_id": d["client_id"]},
                {"$set": {"is_branch": True, "parent_client_id": principal["client_id"]}}
            )
            branches_linked += 1

    return {
        "message": "Migración de jerarquía completada",
        "groups": len(groups),
        "principals": principals,
        "promoted_to_principal": promoted,
        "branches_linked": branches_linked,
    }


async def restore_client_hierarchy():
    """Ejecuta la migración jerárquica UNA vez (guardada por flag en `config`).
    Se llama en el startup en background para que Producción quede migrada
    automáticamente tras un redeploy, sin bloquear el readiness probe."""
    flag = await db.config.find_one({"type": "client_hierarchy_migrated"}, {"_id": 0})
    if flag and flag.get("value") is True:
        return
    result = await run_client_hierarchy_migration()
    await db.config.update_one(
        {"type": "client_hierarchy_migrated"},
        {"$set": {"type": "client_hierarchy_migrated", "value": True, "result": result}},
        upsert=True,
    )
    logger.info(f"[startup] client hierarchy migrated: {result}")




# ==================== DATOS DE IMPLE (edición rápida + cascada multisucursal) ====================

@router.get("/implementation/default-coordinator")
async def get_default_coordinator(authorization: Optional[str] = Header(None)):
    """Coordinador por defecto para 'Datos de Imple': usuario ACTIVO cuyo PERFIL
    de seguridad es 'Coordinador de Administración'. Se resuelve dinámicamente,
    de modo que si cambia la persona asignada al perfil, la precarga se actualiza."""
    await get_current_user(authorization)
    profile = await db.profiles.find_one(
        {"name": {"$regex": r"coordinad.*administraci", "$options": "i"}},
        {"_id": 0, "profile_id": 1, "name": 1}
    )
    if not profile:
        return {"user_id": "", "name": "", "profile_found": False}
    user = await db.users.find_one(
        {"profile_id": profile["profile_id"], "is_active": True},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1}
    )
    if not user:
        return {"user_id": "", "name": "", "profile_found": True, "profile_name": profile.get("name")}
    name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    return {"user_id": user["user_id"], "name": name, "profile_found": True, "profile_name": profile.get("name")}


@router.put("/clients/{client_id}/imple-data")
async def update_client_imple_data(client_id: str, payload: ImpleDataUpdate, authorization: Optional[str] = Header(None)):
    """Edición rápida de datos de implementación. Aplica los 5 campos al cliente
    seleccionado y los replica EN CASCADA a TODAS las sucursales del mismo RIF,
    en una sola operación de actualización (update_many). Flujo unidireccional."""
    await require_permission(authorization, "datos_imple", "edit")

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "rif": 1, "legal_name": 1, "fantasy_name": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    rif = client.get("rif")
    if not rif:
        raise HTTPException(status_code=400, detail="El cliente no tiene RIF; no se puede aplicar la actualización multisucursal.")

    update_fields = {
        "tipo_servicio": payload.tipo_servicio or [],
        "integrador_id": payload.integrador_id,
        "integrador_name": payload.integrador_name,
        "aplicativo": payload.aplicativo,
        "implementer_user_id": payload.implementer_user_id,
        "implementer_name": payload.implementer_name,
        "coordinator_user_id": payload.coordinator_user_id,
        "coordinator_name": payload.coordinator_name,
        "imple_data_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Cascada: todos los registros con el mismo RIF (todas las sucursales)
    result = await db.clients.update_many({"rif": rif}, {"$set": update_fields})

    branches = await db.clients.find(
        {"rif": rif}, {"_id": 0, "client_id": 1, "sucursal": 1}
    ).to_list(1000)

    return {
        "message": f"Datos de implementación actualizados en {result.modified_count} sucursal(es) del mismo RIF.",
        "rif": rif,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "branches_count": len(branches),
        "branches": branches,
    }



@router.get("/clients/search")
async def search_clients(q: str = "", authorization: Optional[str] = Header(None)):
    """Búsqueda server-side de clientes por nombre o RIF"""
    await get_current_user(authorization)
    if not q or len(q) < 2:
        clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1}).to_list(50)
        return clients
    import re
    # Limpiar caracteres especiales para búsqueda de RIF (J-12345678-9 → J12345679)
    q_clean = re.sub(r'[.\-\s]', '', q)
    # Construir regex flexible para RIF: insertar .? entre cada carácter para ignorar puntos/guiones
    rif_pattern = '.?'.join(re.escape(c) for c in q_clean) if q_clean else q
    query = {
        "$or": [
            {"fantasy_name": {"$regex": q, "$options": "i"}},
            {"legal_name": {"$regex": q, "$options": "i"}},
            {"rif": {"$regex": rif_pattern, "$options": "i"}}
        ]
    }
    clients = await db.clients.find(query, {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1, "contact_name": 1, "address": 1, "commercial_name": 1}).to_list(50)
    return clients


@router.get("/clients/referidor-options")
async def get_referidor_options(authorization: Optional[str] = Header(None)):
    """Opciones para el selector de referidores: bancos y clientes existentes"""
    await get_current_user(authorization)
    banks = await db.banks.find({}, {"_id": 0, "bank_id": 1, "name": 1}).sort("name", 1).to_list(100)
    clients = await db.clients.find(
        {}, {"_id": 0, "client_id": 1, "fantasy_name": 1, "legal_name": 1, "rif": 1}
    ).sort("fantasy_name", 1).to_list(2000)
    return {
        "banks": [{"id": b["bank_id"], "name": b["name"]} for b in banks],
        "clients": [{"id": c["client_id"], "name": c.get("fantasy_name") or c.get("legal_name", ""), "rif": c.get("rif", "")} for c in clients]
    }

@router.get("/clients/template")
async def get_clients_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación para clientes con todos los campos del modelo"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    # Obtener ejecutivos e integradores para referencia
    ejecutivos = await db.users.find(
        {"is_active": True, "cargo": {"$in": ["Ejecutivo de Ventas Pyme", "Ejecutivo de Ventas Corporativas"]}},
        {"_id": 0, "first_name": 1, "last_name": 1}
    ).to_list(100)
    ejecutivo_names = [f"{e.get('first_name','')} {e.get('last_name','')}".strip() for e in ejecutivos]
    
    integradores = await db.integrators.find({}, {"_id": 0, "name": 1}).to_list(500)
    integrador_names = [i["name"] for i in integradores]

    # Coordinadores e Implementadores para referencia (responsables de implementación)
    coordinadores = await db.users.find(
        {"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"},
        {"_id": 0, "first_name": 1, "last_name": 1}
    ).to_list(100)
    coordinador_names = [f"{u.get('first_name','')} {u.get('last_name','')}".strip() for u in coordinadores]

    implementadores = await db.users.find(
        {"is_active": True, "cargo": "Implementador"},
        {"_id": 0, "first_name": 1, "last_name": 1}
    ).to_list(100)
    implementador_names = [f"{u.get('first_name','')} {u.get('last_name','')}".strip() for u in implementadores]

    data = {
        'RIF': ['J-12345678-9', 'J-98765432-1', 'J-11223344-5'],
        'Sucursal': ['Principal', 'Sede Norte', 'Principal'],
        'Nombre Jurídico': ['Empresa Demo CA', 'Empresa Demo CA', 'Otra Empresa SRL'],
        'Nombre Fantasía': ['DemoCorp', 'DemoCorp Norte', 'OtraCorp'],
        'Segmento': ['Corporativo', 'Corporativo', 'Pymes'],
        'Condición': ['Cliente', 'Prospecto', 'Prospecto'],
        'Origen Tipo': ['Banco', 'Cliente Referidor', 'Correo de Ventas'],
        'Referidor Nombre': ['Banco Mercantil', 'MEGA SOFT COMPUTACION C.A.', ''],
        'Referidor ID': ['', 'J-00334455-6', ''],
        'Dirección Fiscal': ['Av. Libertador, Edif. Torre X, Caracas', 'CC San Ignacio, Valencia', ''],
        'Dirección Sucursal': ['', 'Av. Bolívar Norte, Local 5', ''],
        'Categoría Comercial': ['Retail', 'Restaurante', 'Tecnología'],
        'Grupo Económico': ['Grupo Demo', 'Grupo Demo', ''],
        'Ejecutivo Propietario': [ejecutivo_names[0] if ejecutivo_names else 'Rafael González', '', ''],
        'Cantidad Tiendas': [5, 1, ''],
        'Cantidad Cajas': [12, 2, ''],
        'Coordinador': [coordinador_names[0] if coordinador_names else '', '', ''],
        'Implementador': [implementador_names[0] if implementador_names else '', '', ''],
        'Fecha Primer Contacto': ['15/01/2026', '28/02/2026', ''],
        'Tipo Contacto': ['Llamada', 'Correo', ''],
        'Tipo Servicio': ['VPOS, MPOS', 'Payment Gateway', 'Link de Pago'],
        'Integrador': [integrador_names[0] if integrador_names else '', '', ''],
        'Aplicativo': ['PaymentHub v3', '', ''],
        'Contacto Nombre Completo': ['Carlos Perez', 'Ana Ruiz', 'Pedro Gomez'],
        'Contacto Teléfono': ['0412-1234567', '0416-9876543', '0414-1112233'],
        'Contacto Email': ['carlos@demo.com', 'ana@demo.com', 'pedro@otra.com'],
        'Contacto Rol': ['Administrativo', 'Técnico', 'Financiero'],
    }
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')
        
        # Instrucciones detalladas
        fields = [
            {'Campo': 'RIF *', 'Columna': 'A', 'Descripción': 'RIF del cliente. Formato: J-12345678-9, V-12345678-9, G-12345678-9 o E-12345678-9. Obligatorio.', 'Obligatorio': 'Sí', 'Ejemplo': 'J-12345678-9'},
            {'Campo': 'Sucursal', 'Columna': 'B', 'Descripción': 'Nombre de la sucursal. Si se omite, se asigna "Principal". Permite el mismo RIF con diferentes sucursales.', 'Obligatorio': 'No', 'Ejemplo': 'Principal'},
            {'Campo': 'Nombre Jurídico *', 'Columna': 'C', 'Descripción': 'Razón social del cliente. Obligatorio.', 'Obligatorio': 'Sí', 'Ejemplo': 'Empresa Demo CA'},
            {'Campo': 'Nombre Fantasía', 'Columna': 'D', 'Descripción': 'Nombre comercial o marca. Si se omite, se usa el Nombre Jurídico.', 'Obligatorio': 'No', 'Ejemplo': 'DemoCorp'},
            {'Campo': 'Segmento', 'Columna': 'E', 'Descripción': 'Segmento comercial. Valores: Pymes, Corporativo, Emprendedor, Mixto. Default: Pymes.', 'Obligatorio': 'No', 'Ejemplo': 'Corporativo'},
            {'Campo': 'Condición', 'Columna': 'F', 'Descripción': 'Estado del cliente. Valores: Prospecto, Cliente. Default: Prospecto.', 'Obligatorio': 'No', 'Ejemplo': 'Prospecto'},
            {'Campo': 'Origen Tipo', 'Columna': 'G', 'Descripción': 'Origen del cliente. Valores de la lista maestra: Correo de Ventas, Integrador, Directores, Corporativo, Ventas Directas (Ejecutivo), Página Web / Landing Page, Redes Sociales, Alianzas Externas, Banco, Cliente Referidor, o nombres propios.', 'Obligatorio': 'No', 'Ejemplo': 'Banco'},
            {'Campo': 'Referidor Nombre', 'Columna': 'H', 'Descripción': 'Si Origen=Banco: nombre del banco. Si Origen=Cliente Referidor: nombre o RIF del cliente referidor. Vacío para los demás orígenes.', 'Obligatorio': 'No', 'Ejemplo': 'Banco Mercantil'},
            {'Campo': 'Referidor ID', 'Columna': 'I', 'Descripción': 'RIF del cliente referidor o código del banco (opcional, usado para validación cruzada).', 'Obligatorio': 'No', 'Ejemplo': 'J-00334455-6'},
            {'Campo': 'Dirección Fiscal', 'Columna': 'J', 'Descripción': 'Dirección fiscal o principal del cliente.', 'Obligatorio': 'No', 'Ejemplo': 'Av. Libertador, Caracas'},
            {'Campo': 'Dirección Sucursal', 'Columna': 'K', 'Descripción': 'Dirección de la sucursal (si difiere de la fiscal).', 'Obligatorio': 'No', 'Ejemplo': 'CC San Ignacio, Local 5'},
            {'Campo': 'Categoría Comercial', 'Columna': 'L', 'Descripción': 'Tipo de negocio. Ver hoja "Valores Válidos" para la lista completa.', 'Obligatorio': 'No', 'Ejemplo': 'Retail'},
            {'Campo': 'Grupo Económico', 'Columna': 'M', 'Descripción': 'Nombre del grupo económico al que pertenece.', 'Obligatorio': 'No', 'Ejemplo': 'Grupo Demo'},
            {'Campo': 'Ejecutivo Propietario', 'Columna': 'N', 'Descripción': 'Nombre del ejecutivo de ventas asignado. Debe existir en el sistema.', 'Obligatorio': 'No', 'Ejemplo': ejecutivo_names[0] if ejecutivo_names else 'Rafael González'},
            {'Campo': 'Cantidad Tiendas', 'Columna': 'O', 'Descripción': 'Número de tiendas o locales del cliente. Solo números enteros.', 'Obligatorio': 'No', 'Ejemplo': '5'},
            {'Campo': 'Cantidad Cajas', 'Columna': 'P', 'Descripción': 'Número de cajas registradoras del cliente. Solo números enteros.', 'Obligatorio': 'No', 'Ejemplo': '12'},
            {'Campo': 'Coordinador', 'Columna': 'Q', 'Descripción': 'Nombre del Coordinador de Implementación asignado. Debe existir en el sistema con cargo "Coordinador" y departamento "Implementación".', 'Obligatorio': 'No', 'Ejemplo': coordinador_names[0] if coordinador_names else ''},
            {'Campo': 'Implementador', 'Columna': 'R', 'Descripción': 'Nombre del Implementador asignado. Debe existir en el sistema con cargo "Implementador".', 'Obligatorio': 'No', 'Ejemplo': implementador_names[0] if implementador_names else ''},
            {'Campo': 'Fecha Primer Contacto', 'Columna': 'S', 'Descripción': 'Fecha del primer contacto. Formatos: DD/MM/AAAA o AAAA-MM-DD. No puede ser futura.', 'Obligatorio': 'No', 'Ejemplo': '15/01/2026'},
            {'Campo': 'Tipo Contacto', 'Columna': 'T', 'Descripción': 'Medio de contacto inicial: Llamada, Correo, Presencial, Referido, Otro.', 'Obligatorio': 'No', 'Ejemplo': 'Llamada'},
            {'Campo': 'Tipo Servicio', 'Columna': 'U', 'Descripción': 'Servicios de interés separados por coma. Valores: VPOS, MPOS, Payment Gateway, Link de Pago.', 'Obligatorio': 'No', 'Ejemplo': 'VPOS, MPOS'},
            {'Campo': 'Integrador', 'Columna': 'V', 'Descripción': 'Nombre del integrador asociado. Debe existir en el sistema.', 'Obligatorio': 'No', 'Ejemplo': integrador_names[0] if integrador_names else ''},
            {'Campo': 'Aplicativo', 'Columna': 'W', 'Descripción': 'Nombre del aplicativo del integrador.', 'Obligatorio': 'No', 'Ejemplo': 'PaymentHub v3'},
            {'Campo': 'Contacto Nombre Completo', 'Columna': 'X', 'Descripcion': 'Nombre completo del contacto principal del cliente.', 'Obligatorio': 'No', 'Ejemplo': 'Carlos Perez'},
            {'Campo': 'Contacto Telefono', 'Columna': 'Y', 'Descripcion': 'Telefono del contacto. Formato libre.', 'Obligatorio': 'No', 'Ejemplo': '0412-1234567'},
            {'Campo': 'Contacto Email', 'Columna': 'Z', 'Descripcion': 'Email del contacto principal.', 'Obligatorio': 'No', 'Ejemplo': 'carlos@demo.com'},
            {'Campo': 'Contacto Rol', 'Columna': 'AA', 'Descripcion': 'Rol del contacto: Administrativo, Financiero, Tecnico, Cuentas por Pagar, Operativo. Default: Administrativo.', 'Obligatorio': 'No', 'Ejemplo': 'Administrativo'},
        ]
        pd.DataFrame(fields).to_excel(writer, index=False, sheet_name='Instrucciones')
        
        # Valores Válidos — referencia completa
        categorias = [
            'Retail', 'Farmacia', 'Restaurante', 'Supermercado', 'Abasto', 'Panadería',
            'Bar / Discoteca', 'Comida Rápida', 'Cafetería', 'Tienda de Ropa', 'Boutique',
            'Salón de Belleza', 'Barbería', 'Spa / Salud', 'Gimnasio', 'Cosmética',
            'Calzados', 'Mueblería', 'Ferretería', 'Electrodomésticos', 'Joyería',
            'Electrónica', 'Software', 'Juguetería', 'Librería', 'Tienda por Departamento',
            'Educación', 'Inmobiliaria', 'Clínica', 'Alimentos', 'Tecnología', 'Servicios',
        ]
        referidores_origenes = [
            'Correo de Ventas', 'Integrador', 'Directores', 'Corporativo',
            'Jose Dolande', 'Melissa Garcia', 'Katherine Quailey', 'Rafael Gonzalez',
            'Ventas Directas (Ejecutivo)', 'Página Web / Landing Page', 'Redes Sociales',
            'Alianzas Externas', 'Banco', 'Cliente Referidor',
        ]
        # Get bank names for reference
        bank_docs = await db.banks.find({}, {"_id": 0, "name": 1}).sort("name", 1).to_list(100)
        bank_names = [b["name"] for b in bank_docs]
        tipos_contacto = ['Llamada', 'Correo', 'Presencial', 'Referido', 'Otro']
        tipos_servicio = ['VPOS', 'MPOS', 'Payment Gateway', 'Link de Pago']
        roles = ['Administrativo', 'Financiero', 'Técnico', 'Cuentas por Pagar', 'Operativo']
        segmentos = ['Pymes', 'Corporativo', 'Emprendedor', 'Mixto']
        condiciones = ['Prospecto', 'Cliente']
        
        max_len = max(len(categorias), len(referidores_origenes), len(ejecutivo_names), len(integrador_names), len(roles), len(bank_names), 15)
        def pad(lst):
            return lst + [''] * (max_len - len(lst))
        
        values_data = {
            'Segmentos (Col E)': pad(segmentos),
            'Condiciones (Col F)': pad(condiciones),
            'Orígenes del Cliente (Col G)': pad(referidores_origenes),
            'Bancos Registrados (Col H si Origen=Banco)': pad(bank_names),
            'Categorías Comerciales (Col K)': pad(categorias),
            'Tipos de Contacto (Col Q)': pad(tipos_contacto),
            'Tipos de Servicio (Col R)': pad(tipos_servicio),
            'Roles de Contacto (Col Y)': pad(roles),
            'Ejecutivos Registrados (Col M)': pad(ejecutivo_names),
            'Integradores Registrados (Col S)': pad(integrador_names[:max_len]),
            'Reglas de Importación': pad([
                '1. La clave única es: RIF + Sucursal',
                '2. Si un registro ya existe (mismo RIF + Sucursal) se OMITE',
                '3. Los campos marcados con * son OBLIGATORIOS',
                '4. El RIF debe tener formato: J-12345678-9 (letra-números-dígito)',
                '5. Si no indica Segmento, se asigna "Pymes"',
                '6. Si no indica Condición, se asigna "Prospecto"',
                '7. Si no indica Sucursal, se asigna "Principal"',
                '8. Tipo Servicio acepta valores separados por coma',
                '9. El Ejecutivo debe estar registrado en el sistema',
                '10. El Integrador debe estar registrado en el sistema',
                '11. La Fecha Primer Contacto no puede ser futura',
                '12. Cantidad Tiendas y Cajas deben ser números enteros positivos',
                '13. Los valores deben coincidir exactamente con esta hoja',
                '14. Se aceptan archivos .xlsx, .xls y .csv',
                '15. Referidor Tipo: BANCO, CLIENTE u OTRO',
                '16. Si Tipo=CLIENTE, el RIF en Col H debe existir en el sistema',
                '17. Si Tipo=BANCO, el nombre debe coincidir con la lista de bancos',
            ]),
        }
        pd.DataFrame(values_data).to_excel(writer, index=False, sheet_name='Valores Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_clientes.xlsx"}
    )

@router.get("/clients/bulk-update-template")
async def get_bulk_update_template(authorization: Optional[str] = Header(None)):
    """Plantilla Excel (.xlsx) para la Actualización Masiva de clientes por RIF."""
    await get_current_user(authorization)
    import pandas as pd

    integradores = await db.integrators.find({}, {"_id": 0, "name": 1, "app_name": 1}).to_list(500)
    integrador_names = sorted({i["name"] for i in integradores if i.get("name")})
    integ_apps = sorted({i["app_name"].strip() for i in integradores if (i.get("app_name") or "").strip()})
    ejecutivos = await db.users.find(
        {"is_active": True, "departamento": {"$in": ["Ventas Pyme", "Ventas Corporativas"]}},
        {"_id": 0, "first_name": 1, "last_name": 1}).to_list(200)
    ejecutivo_names = sorted({f"{e.get('first_name','')} {e.get('last_name','')}".strip() for e in ejecutivos})
    coords = await db.users.find(
        {"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"},
        {"_id": 0, "first_name": 1, "last_name": 1}).to_list(200)
    coord_names = sorted({f"{u.get('first_name','')} {u.get('last_name','')}".strip() for u in coords})
    impls = await db.users.find(
        {"is_active": True, "cargo": "Implementador"}, {"_id": 0, "first_name": 1, "last_name": 1}).to_list(200)
    impl_names = sorted({f"{u.get('first_name','')} {u.get('last_name','')}".strip() for u in impls})

    example = {
        'RIF': ['J-12345678-9', 'J-98765432-1'],
        'Nombre Jurídico': ['Empresa Demo CA', ''],
        'Nombre de Fantasía': ['DemoCorp', ''],
        'Segmento': ['Corporativo', 'Pymes'],
        'Cantidad de Tiendas': [5, ''],
        'Nro de Cajas': [15, ''],
        'Tipo de Servicio': ['VPOS;MPOS', ''],
        'Integrador': [integrador_names[0] if integrador_names else 'Nombre del Integrador', ''],
        'Aplicativo': [integ_apps[0] if integ_apps else 'Nombre del Aplicativo', ''],
        'Coordinador': [coord_names[0] if coord_names else 'correo.coordinador@empresa.com', ''],
        'Implementador': [impl_names[0] if impl_names else 'correo.implementador@empresa.com', ''],
        'Ejecutivo Propietario': [ejecutivo_names[0] if ejecutivo_names else 'correo.ejecutivo@empresa.com', ''],
    }

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(example).to_excel(writer, index=False, sheet_name='Plantilla')

        instrucciones = [
            {'Campo': 'RIF *', 'Descripción': 'RIF del cliente a actualizar. OBLIGATORIO. La coincidencia es por RIF (aplica a todas las sucursales con ese RIF).', 'Ejemplo': 'J-12345678-9'},
            {'Campo': 'Nombre Jurídico', 'Descripción': 'Razón social. Se actualiza solo si la celda tiene valor.', 'Ejemplo': 'Empresa Demo CA'},
            {'Campo': 'Nombre de Fantasía', 'Descripción': 'Nombre comercial / marca. Se actualiza solo si tiene valor.', 'Ejemplo': 'DemoCorp'},
            {'Campo': 'Segmento', 'Descripción': 'Valores: Pymes, Corporativo, Emprendedor, Mixto.', 'Ejemplo': 'Corporativo'},
            {'Campo': 'Cantidad de Tiendas', 'Descripción': 'Número entero.', 'Ejemplo': '5'},
            {'Campo': 'Nro de Cajas', 'Descripción': 'Número entero.', 'Ejemplo': '15'},
            {'Campo': 'Tipo de Servicio', 'Descripción': 'Se AGREGAN a los existentes. Separe con ; (VPOS;MPOS;Payment Gateway;Link de Pago).', 'Ejemplo': 'VPOS;MPOS'},
            {'Campo': 'Integrador', 'Descripción': 'Debe existir en el catálogo. Nombre exacto.', 'Ejemplo': integrador_names[0] if integrador_names else 'Integrador X'},
            {'Campo': 'Aplicativo', 'Descripción': 'Aplicativo del integrador. Si indica también el Integrador, se valida contra sus aplicativos.', 'Ejemplo': integ_apps[0] if integ_apps else 'App Y'},
            {'Campo': 'Coordinador', 'Descripción': 'Correo o nombre exacto (cargo Coordinador, depto Implementación).', 'Ejemplo': coord_names[0] if coord_names else '—'},
            {'Campo': 'Implementador', 'Descripción': 'Correo o nombre exacto (cargo Implementador).', 'Ejemplo': impl_names[0] if impl_names else '—'},
            {'Campo': 'Ejecutivo Propietario', 'Descripción': 'Correo o nombre exacto (depto Ventas).', 'Ejemplo': ejecutivo_names[0] if ejecutivo_names else '—'},
            {'Campo': '— REGLAS —', 'Descripción': '1) Solo se actualizan clientes EXISTENTES (match por RIF). 2) Las celdas VACÍAS se ignoran (actualización parcial). 3) Use el botón "Previsualizar" antes de aplicar.', 'Ejemplo': ''},
        ]
        pd.DataFrame(instrucciones).to_excel(writer, index=False, sheet_name='Instrucciones')

        max_len = max(len(integrador_names), len(integ_apps), len(coord_names), len(impl_names), len(ejecutivo_names), 4, 1)
        def _pad(lst):
            return list(lst) + [''] * (max_len - len(lst))
        valores = {
            'Segmentos': _pad(['Pymes', 'Corporativo', 'Emprendedor', 'Mixto']),
            'Tipos de Servicio': _pad(['VPOS', 'MPOS', 'Payment Gateway', 'Link de Pago']),
            'Integradores': _pad(integrador_names),
            'Aplicativos': _pad(integ_apps),
            'Coordinadores': _pad(coord_names),
            'Implementadores': _pad(impl_names),
            'Ejecutivos': _pad(ejecutivo_names),
        }
        pd.DataFrame(valores).to_excel(writer, index=False, sheet_name='Valores Válidos')

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_actualizacion_clientes.xlsx"},
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
    await require_permission(authorization, "clientes", "edit")
    # Sanitizar RIF
    client_data.rif = sanitize_rif(client_data.rif)
    # Validar unicidad RIF + Sucursal (excluyendo el propio registro)
    existing = await db.clients.find_one(
        {"rif": client_data.rif, "sucursal": client_data.sucursal or "Principal", "client_id": {"$ne": client_id}},
        {"_id": 0, "client_id": 1}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe otro cliente con RIF {client_data.rif} y sucursal '{client_data.sucursal or 'Principal'}'")
    
    data = client_data.model_dump()
    await _sync_group_name(data)
    for c in data.get("contacts", []):
        if not c.get("contact_id"):
            c["contact_id"] = f"cnt_{uuid.uuid4().hex[:8]}"
    # Re-derivar jerarquía (evita que un PUT sin estos campos rompa el vínculo padre/hija)
    data["parent_client_id"], data["is_branch"] = await _derive_hierarchy(
        client_data.rif, client_data.sucursal, self_client_id=client_id
    )
    result = await db.clients.update_one(
        {"client_id": client_id},
        {"$set": data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return await get_client(client_id, authorization)

@router.patch("/clients/{client_id}")
async def patch_client(client_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualización parcial de campos del cliente.
    Útil cuando solo se quiere modificar un campo (ej: modelo_impresora_fiscal
    desde el wizard de envío a implementación) sin requerir el payload completo
    del modelo ClientCreate. Solo permite campos seguros editables.
    """
    await require_permission(authorization, "clientes", "edit")
    # Whitelist de campos permitidos para PATCH parcial
    allowed_fields = {
        "modelo_impresora_fiscal", "aplicativo", "integrador_id", "integrador_name",
        "coordinator_user_id", "coordinator_name", "implementer_user_id", "implementer_name",
        "fantasy_name", "address", "branch_address", "categoria_comercial",
        "grupo_economico", "cantidad_tiendas", "cantidad_cajas",
    }
    payload = {k: v for k, v in (body or {}).items() if k in allowed_fields}
    if not payload:
        raise HTTPException(status_code=400, detail="No se enviaron campos editables")
    result = await db.clients.update_one({"client_id": client_id}, {"$set": payload})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True, "updated": list(payload.keys())}



@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, authorization: Optional[str] = Header(None)):
    await require_permission(authorization, "clientes", "edit")
    
    # Validar integridad referencial - verificar si hay cotizaciones vinculadas
    quotes_count = await db.quotes.count_documents({"client_id": client_id})
    if quotes_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el cliente porque tiene {quotes_count} cotización(es) vinculada(s). Elimine primero las cotizaciones asociadas."
        )

    # No permitir eliminar un Principal que tiene sucursales adscritas
    branches_count = await db.clients.count_documents({"parent_client_id": client_id})
    if branches_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede eliminar el Principal porque tiene {branches_count} sucursal(es) adscrita(s). Elimine o reasigne primero las sucursales."
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
        "contacted_person": log_data.contacted_person,
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


# ==================== FISCAL PRINTER MODELS ====================

@router.get("/fiscal-printers")
async def get_fiscal_printers(authorization: Optional[str] = Header(None)):
    """Obtener modelos de impresora fiscal registrados"""
    await get_current_user(authorization)
    models = await db.fiscal_printer_models.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    if not models:
        # Seed inicial
        seed = [
            {"model_id": f"fpm_{uuid.uuid4().hex[:8]}", "name": "Bematech", "created_at": datetime.now(timezone.utc).isoformat()},
            {"model_id": f"fpm_{uuid.uuid4().hex[:8]}", "name": "Bixolon", "created_at": datetime.now(timezone.utc).isoformat()},
            {"model_id": f"fpm_{uuid.uuid4().hex[:8]}", "name": "HKA", "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        await db.fiscal_printer_models.insert_many(seed)
        models = seed
    return models


@router.post("/fiscal-printers")
async def create_fiscal_printer(data: dict, authorization: Optional[str] = Header(None)):
    """Registrar nuevo modelo de impresora fiscal en la tabla maestra"""
    await get_current_user(authorization)
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="El nombre del modelo es obligatorio")
    existing = await db.fiscal_printer_models.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"El modelo '{name}' ya existe")
    model = {
        "model_id": f"fpm_{uuid.uuid4().hex[:8]}",
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.fiscal_printer_models.insert_one(model)
    return {"model_id": model["model_id"], "name": model["name"], "created_at": model["created_at"]}




# ==================== ACTUALIZACIÓN MASIVA DE CLIENTES POR RIF ====================
# Permite actualizar en bloque (vía CSV/Excel, coincidencia por RIF en cascada a
# todas las sucursales del mismo RIF) los campos: Cantidad de Tiendas, Nro de Cajas,
# Tipo de Servicio (se AGREGA a la lista existente), Integrador, Coordinador,
# Implementador y Ejecutivo Propietario. Actualización parcial: las celdas vacías
# se ignoran. Referencias validadas contra catálogos/usuarios existentes.

def _strip_accents(s: str) -> str:
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')


def _norm_text(s) -> str:
    return _strip_accents(str(s or '').strip().lower())


_BULK_HEADER_MAP = {
    'rif': 'rif',
    'nombre juridico': 'legal_name', 'nombre_juridico': 'legal_name', 'legal_name': 'legal_name',
    'razon social': 'legal_name', 'nombre legal': 'legal_name',
    'nombre de fantasia': 'fantasy_name', 'nombre fantasia': 'fantasy_name', 'nombre_fantasia': 'fantasy_name',
    'fantasia': 'fantasy_name', 'nombre comercial': 'fantasy_name', 'fantasy_name': 'fantasy_name',
    'segmento': 'segment', 'segment': 'segment',
    'aplicativo': 'aplicativo', 'app': 'aplicativo', 'aplicacion': 'aplicativo',
    'cantidad de tiendas': 'cantidad_tiendas', 'cantidad_tiendas': 'cantidad_tiendas', 'tiendas': 'cantidad_tiendas',
    'nro de tiendas': 'cantidad_tiendas', 'numero de tiendas': 'cantidad_tiendas',
    'nro de cajas': 'cantidad_cajas', 'numero de cajas': 'cantidad_cajas', 'cantidad de cajas': 'cantidad_cajas',
    'cantidad_cajas': 'cantidad_cajas', 'cajas': 'cantidad_cajas', 'nro cajas': 'cantidad_cajas',
    'cajas activas': 'cantidad_cajas', 'cajas_activas': 'cantidad_cajas', 'nro de cajas activas': 'cantidad_cajas',
    'tipo de servicio': 'tipo_servicio', 'tipo_servicio': 'tipo_servicio',
    'integrador': 'integrador',
    'coordinador': 'coordinador',
    'implementador': 'implementador',
    'ejecutivo propietario': 'ejecutivo', 'ejecutivo': 'ejecutivo', 'ejecutivo_propietario': 'ejecutivo',
    'gerencia': 'ejecutivo', 'gerente': 'ejecutivo',
}


def _parse_bulk_file(filename: str, content: bytes):
    """Parsea CSV o XLSX a (filas [{canonical_key: value}], columnas_ignoradas)."""
    name = (filename or '').lower()
    rows_raw = []
    if name.endswith('.xlsx') or name.endswith('.xlsm'):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        headers = None
        for r in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip() if c is not None else '' for c in r]
                continue
            if r is None or all(c is None or str(c).strip() == '' for c in r):
                continue
            rows_raw.append({headers[i] if i < len(headers) else f'col{i}': (r[i] if i < len(r) else None) for i in range(len(r))})
    else:
        import csv
        text = content.decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        for r in reader:
            rows_raw.append(r)

    rows = []
    ignored = set()
    for raw in rows_raw:
        canon = {}
        for k, v in raw.items():
            if k is None or str(k).strip() == '':
                continue
            key = _BULK_HEADER_MAP.get(_norm_text(k))
            if key:
                canon[key] = '' if v is None else str(v).strip()
            else:
                ignored.add(str(k).strip())
        if any(str(val).strip() for val in canon.values()):
            rows.append(canon)
    return rows, sorted(ignored)


def _user_lookup(users: List[dict]) -> dict:
    """Mapa de email y nombre completo (normalizados) → {user_id, name}."""
    m = {}
    for u in users:
        name = f"{u.get('first_name','')} {u.get('last_name','')}".strip()
        entry = {"user_id": u.get("user_id"), "name": name}
        if u.get("email"):
            m[_norm_text(u["email"])] = entry
        if name:
            m[_norm_text(name)] = entry
    return m


@router.post("/clients/bulk-update-by-rif")
async def bulk_update_clients_by_rif(
    file: UploadFile = File(...),
    dry_run: str = Form("true"),
    authorization: Optional[str] = Header(None),
):
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo un Administrador puede ejecutar la actualización masiva")

    is_dry = str(dry_run).lower() in ("true", "1", "yes", "si", "sí")
    content = await file.read()
    try:
        rows, ignored_columns = _parse_bulk_file(file.filename, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {e}")
    if not rows:
        raise HTTPException(status_code=400, detail="El archivo no contiene filas válidas (¿encabezados correctos?)")

    # Catálogos / usuarios de referencia
    integ_docs = await db.integrators.find({}, {"_id": 0, "integrator_id": 1, "name": 1, "app_name": 1}).to_list(2000)
    integ_by_name: dict = {}
    for d in integ_docs:
        nm = d.get("name")
        if not nm:
            continue
        integ_by_name.setdefault(_norm_text(nm), []).append({
            "id": d.get("integrator_id"), "name": nm, "app_name": (d.get("app_name") or "").strip(),
        })
    valid_segments = ['Pymes', 'Corporativo', 'Emprendedor', 'Mixto']

    ventas_deptos = ["Ventas Pyme", "Ventas Corporativas"]
    ejec_users = await db.users.find({"is_active": True, "departamento": {"$in": ventas_deptos}}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}).to_list(2000)
    impl_users = await db.users.find({"is_active": True, "cargo": "Implementador"}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}).to_list(2000)
    coord_users = await db.users.find({"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1}).to_list(2000)
    ejec_map, impl_map, coord_map = _user_lookup(ejec_users), _user_lookup(impl_users), _user_lookup(coord_users)

    # Mapa de clientes por RIF normalizado → [client_id]
    clients_by_rif: dict = {}
    async for c in db.clients.find({}, {"_id": 0, "client_id": 1, "rif": 1}):
        clients_by_rif.setdefault(sanitize_rif(c.get("rif", "")), []).append(c.get("client_id"))

    report = []
    total_clients_updated = 0
    rows_ok = 0

    for i, row in enumerate(rows, start=2):
        rif_norm = sanitize_rif(row.get("rif", ""))
        rec = {"row": i, "rif": row.get("rif", ""), "matched_clients": 0, "applied": [], "warnings": [], "status": "ok"}
        if not rif_norm:
            rec.update(status="error", warnings=["RIF vacío"])
            report.append(rec); continue
        client_ids = clients_by_rif.get(rif_norm, [])
        rec["matched_clients"] = len(client_ids)
        if not client_ids:
            rec.update(status="not_found", warnings=["RIF no encontrado en la base de clientes"])
            report.append(rec); continue

        set_fields = {}
        # Nombre Jurídico
        v = str(row.get("legal_name", "")).strip()
        if v:
            set_fields["legal_name"] = v; rec["applied"].append("Nombre Jurídico")
        # Nombre de Fantasía
        v = str(row.get("fantasy_name", "")).strip()
        if v:
            set_fields["fantasy_name"] = v; rec["applied"].append("Nombre de Fantasía")
        # Segmento
        v = str(row.get("segment", "")).strip()
        if v:
            if v in valid_segments:
                set_fields["segment"] = v; rec["applied"].append("Segmento")
            else:
                rec["warnings"].append(f"Segmento inválido: '{v}' (use: {', '.join(valid_segments)})")
        # Cantidad de Tiendas
        v = row.get("cantidad_tiendas", "")
        if str(v).strip():
            try:
                set_fields["cantidad_tiendas"] = int(float(str(v).strip())); rec["applied"].append("Cantidad de Tiendas")
            except ValueError:
                rec["warnings"].append(f"Cantidad de Tiendas inválida: '{v}'")
        # Nro de Cajas
        v = row.get("cantidad_cajas", "")
        if str(v).strip():
            try:
                set_fields["cantidad_cajas"] = int(float(str(v).strip())); rec["applied"].append("Nro de Cajas")
            except ValueError:
                rec["warnings"].append(f"Nro de Cajas inválido: '{v}'")
        # Integrador + Aplicativo (cascada)
        v_integ = str(row.get("integrador", "")).strip()
        v_app = str(row.get("aplicativo", "")).strip()
        if v_integ:
            recs = integ_by_name.get(_norm_text(v_integ))
            if recs:
                set_fields["integrador_name"] = recs[0]["name"]
                apps = [r["app_name"] for r in recs if r["app_name"]]
                if v_app:
                    match = next((r for r in recs if r["app_name"] and _norm_text(r["app_name"]) == _norm_text(v_app)), None)
                    if match:
                        set_fields["integrador_id"] = match["id"]; set_fields["aplicativo"] = match["app_name"]
                        rec["applied"] += ["Integrador", "Aplicativo"]
                    elif apps:
                        set_fields["integrador_id"] = recs[0]["id"]; rec["applied"].append("Integrador")
                        rec["warnings"].append(f"Aplicativo '{v_app}' no válido para '{recs[0]['name']}'. Válidos: {', '.join(apps)}")
                    else:
                        set_fields["integrador_id"] = recs[0]["id"]; set_fields["aplicativo"] = v_app
                        rec["applied"] += ["Integrador", "Aplicativo"]
                else:
                    set_fields["integrador_id"] = recs[0]["id"]; rec["applied"].append("Integrador")
                    if len(apps) == 1:
                        set_fields["aplicativo"] = apps[0]; rec["applied"].append("Aplicativo (auto)")
            else:
                rec["warnings"].append(f"Integrador no existe en el catálogo: '{v_integ}'")
        elif v_app:
            # Aplicativo sin Integrador en la fila: se aplica como texto (sin validación de catálogo)
            set_fields["aplicativo"] = v_app; rec["applied"].append("Aplicativo")
        # Coordinador
        v = str(row.get("coordinador", "")).strip()
        if v:
            hit = coord_map.get(_norm_text(v))
            if hit:
                set_fields["coordinator_user_id"] = hit["user_id"]; set_fields["coordinator_name"] = hit["name"]; rec["applied"].append("Coordinador")
            else:
                rec["warnings"].append(f"Coordinador no está en la lista de Coordinadores de Implementación: '{v}'")
        # Implementador
        v = str(row.get("implementador", "")).strip()
        if v:
            hit = impl_map.get(_norm_text(v))
            if hit:
                set_fields["implementer_user_id"] = hit["user_id"]; set_fields["implementer_name"] = hit["name"]; rec["applied"].append("Implementador")
            else:
                rec["warnings"].append(f"Implementador no está en la lista de Implementadores: '{v}'")
        # Ejecutivo Propietario
        v = str(row.get("ejecutivo", "")).strip()
        if v:
            hit = ejec_map.get(_norm_text(v))
            if hit:
                set_fields["ejecutivo_propietario"] = hit["name"]; set_fields["ejecutivo_user_id"] = hit["user_id"]; rec["applied"].append("Ejecutivo Propietario")
            else:
                rec["warnings"].append(f"Ejecutivo no está en la lista de usuarios de Ventas: '{v}'")
        # Tipo de Servicio (se AGREGA a la lista existente; separador ';')
        new_ts = [t.strip() for t in str(row.get("tipo_servicio", "")).replace("|", ";").split(";") if t.strip()]

        if not set_fields and not new_ts:
            rec["status"] = "sin_cambios"
            report.append(rec); continue

        if not is_dry:
            if set_fields:
                await db.clients.update_many({"client_id": {"$in": client_ids}}, {"$set": set_fields})
            if new_ts:
                for cid in client_ids:
                    doc = await db.clients.find_one({"client_id": cid}, {"_id": 0, "tipo_servicio": 1})
                    existing = doc.get("tipo_servicio") or []
                    merged = list(existing) + [t for t in new_ts if t not in existing]
                    if merged != existing:
                        await db.clients.update_one({"client_id": cid}, {"$set": {"tipo_servicio": merged}})
        if new_ts:
            rec["applied"].append("Tipo de Servicio (+" + ", ".join(new_ts) + ")")

        total_clients_updated += len(client_ids)
        rows_ok += 1
        report.append(rec)

    if not is_dry:
        await db.bitacora.insert_one({
            "action": "clients_bulk_update_by_rif",
            "filename": file.filename,
            "rows_processed": len(rows),
            "rows_applied": rows_ok,
            "clients_updated": total_clients_updated,
            "executed_by": current_user.get("email"),
            "executed_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "dry_run": is_dry,
        "rows_processed": len(rows),
        "rows_ok": rows_ok,
        "rows_not_found": sum(1 for r in report if r["status"] == "not_found"),
        "rows_error": sum(1 for r in report if r["status"] == "error"),
        "clients_updated": total_clients_updated,
        "ignored_columns": ignored_columns,
        "report": report,
    }
# --- END bulk-update ---
