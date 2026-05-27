"""Direct Projects — Creación de proyectos de implementación SIN cotización previa.

Este módulo expone el flujo del requerimiento "Proyectos Directos":
  - El usuario captura cliente + definición comercial + grilla de cajas/banco/producto
    en una sola pantalla.
  - El backend genera un proyecto `PRD-YYYY-MM-NNN` reutilizando
    `_create_project_from_quote` con una "cotización fantasma" en memoria
    (que NO se persiste en la colección `quotes`).
  - Se genera la Ficha Técnica PDF y se dispara la notificación vía el motor
    dinámico (`action_notification_configs` con biz_type="proyectos_directos").

Endpoints:
  - POST /api/direct-projects                          → crear proyecto directo
  - GET  /api/direct-projects/excel-templates/serials  → plantilla seriales
  - GET  /api/direct-projects/excel-templates/branches → plantilla sucursales
  - POST /api/direct-projects/excel-parse/serials      → parsear Excel de seriales
  - POST /api/direct-projects/excel-parse/branches     → parsear Excel de sucursales
"""
from datetime import datetime, timezone
from io import BytesIO
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import db, get_current_user
from routes.quote_transitions import _create_project_from_quote
from services.implementation_pdf import generate_implementation_pdf
from services.notification_engine import try_dispatch as engine_try_dispatch

router = APIRouter(tags=["direct-projects"])
logger = logging.getLogger("direct-projects")


# =================== Helpers de permisos ===================
async def _require_direct_projects_access(authorization: Optional[str], write: bool = False):
    """Valida que el usuario tenga acceso al módulo `proyectos_directos`.

    El middleware RBAC global cubre /api/projects (módulo `proyectos`); este
    módulo nuevo requiere validación manual del nivel `proyectos_directos`.
    """
    user = await get_current_user(authorization)
    if user.get("role") == "admin":
        return user
    perms = user.get("permissions", {}) or {}
    level = perms.get("proyectos_directos", "none")
    if level == "none":
        raise HTTPException(status_code=403, detail="No tiene acceso al módulo Proyectos Directos")
    if write and level != "edit":
        raise HTTPException(status_code=403, detail="No tiene permisos de escritura en Proyectos Directos")
    return user


# =================== Models ===================
class DirectProjectBox(BaseModel):
    """Una fila de la grilla: [Nro Caja] + [Banco] + [Producto]."""
    caja_nro: int
    bank_name: str
    product_name: str
    store_name: Optional[str] = None  # solo para multitienda


class DirectProjectStore(BaseModel):
    name: str
    box_count: int


class DirectProjectSerial(BaseModel):
    modelo: str
    serial: str


class DirectProjectCreate(BaseModel):
    # Cliente
    client_id: str
    economic_group: Optional[str] = ""    # editable
    fantasy_name: Optional[str] = ""      # editable

    # Definición comercial
    quote_type: str  # "VPOS" | "MPOS" | "GATEWAY" | "LINK_PAGO"
    sede: Optional[str] = "PYME"          # "PYME" | "CORP"
    cantidad_cajas: int = Field(ge=1)
    sponsor_bank_id: Optional[str] = None
    sponsor_bank_name: Optional[str] = None
    payment_gateway_link: Optional[str] = None

    # Integrador
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None

    # Hardware (solo VPOS / MPOS)
    pinpad_model: Optional[str] = None
    pinpad_bank: Optional[str] = None
    fiscal_printer_model: Optional[str] = None
    equipment_serials: list[DirectProjectSerial] = Field(default_factory=list)
    pinpad_serials: list[DirectProjectSerial] = Field(default_factory=list)

    # Multitienda
    is_multistore: bool = False
    stores: list[DirectProjectStore] = Field(default_factory=list)

    # Grilla (Caja -> Banco + Producto)
    boxes_grid: list[DirectProjectBox] = Field(default_factory=list)

    # Instrucciones para el implementador
    implementation_instructions: Optional[str] = None


# =================== Helpers de numeración ===================
async def _next_direct_project_number(sede_code: str) -> str:
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")
    prefix = f"PRD-{year}-{month}-"
    last = await db.projects.find_one(
        {"project_number": {"$regex": f"^{prefix}"}},
        sort=[("project_number", -1)],
    )
    if last:
        try:
            n = int(last["project_number"].split("-")[3])
        except (IndexError, ValueError):
            n = 0
    else:
        n = 0
    return f"{prefix}{str(n + 1).zfill(3)}-{sede_code}"


# =================== Endpoint principal ===================
@router.post("/direct-projects")
async def create_direct_project(
    payload: DirectProjectCreate,
    authorization: Optional[str] = Header(None),
):
    """Crea un proyecto de implementación directo (sin cotización).

    1. Valida cliente y campos obligatorios según `quote_type`.
    2. Construye un objeto "cotización fantasma" en memoria (NO se persiste en
       `quotes`).
    3. Llama a `_create_project_from_quote` reutilizando toda la lógica de
       creación de matriz, herencia de banco patrocinador, multitienda, etc.
    4. Genera la Ficha Técnica PDF.
    5. Dispara la notificación vía el motor dinámico (biz_type=`proyectos_directos`).
    6. Retorna el `project_id` + `project_number`.
    """
    user = await _require_direct_projects_access(authorization, write=True)

    # ---- Validaciones ----
    client = await db.clients.find_one({"client_id": payload.client_id}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    qtype = (payload.quote_type or "").upper()
    if qtype not in {"VPOS", "MPOS", "GATEWAY", "LINK_PAGO"}:
        raise HTTPException(status_code=400, detail=f"quote_type inválido: {qtype}")

    requires_hw = qtype in {"VPOS", "MPOS"}
    if requires_hw and not payload.pinpad_model:
        raise HTTPException(status_code=400, detail="VPOS/MPOS requiere modelo de Pinpad")

    if payload.is_multistore:
        if not payload.stores:
            raise HTTPException(status_code=400, detail="Multitienda activado: debe cargar al menos una sucursal")
        total_boxes = sum(int(s.box_count or 0) for s in payload.stores)
        if total_boxes != payload.cantidad_cajas:
            raise HTTPException(
                status_code=400,
                detail=f"La suma de cajas por sucursal ({total_boxes}) debe coincidir con Cantidad de Cajas ({payload.cantidad_cajas}).",
            )

    if len(payload.boxes_grid) != payload.cantidad_cajas:
        raise HTTPException(
            status_code=400,
            detail=f"La grilla debe tener exactamente {payload.cantidad_cajas} fila(s); recibidas {len(payload.boxes_grid)}.",
        )
    for i, box in enumerate(payload.boxes_grid):
        if not (box.bank_name or "").strip():
            raise HTTPException(status_code=400, detail=f"Caja #{i+1}: banco requerido")
        if not (box.product_name or "").strip():
            raise HTTPException(status_code=400, detail=f"Caja #{i+1}: producto requerido")

    sede = (payload.sede or client.get("client_segment") or "PYME").upper()
    if sede not in {"PYME", "CORP"}:
        sede = "PYME"

    # ---- Construir "cotización fantasma" en memoria ----
    # Agrupar la grilla por (bank, product) → cantidad. Esto alimenta
    # `services` para que `_create_project_from_quote` arme la implementation_matrix.
    grid_pairs: dict[tuple[str, str], int] = {}
    for box in payload.boxes_grid:
        key = (box.bank_name.strip(), box.product_name.strip())
        grid_pairs[key] = grid_pairs.get(key, 0) + 1

    services = []
    for (bank, product), qty in grid_pairs.items():
        services.append({
            "item_id": f"svc_{uuid.uuid4().hex[:8]}",
            "item_type": "additional",
            "item_name": product,
            "bank_name": bank,
            "quantity": qty,
            "price_usd": 0,
            "total_usd": 0,
        })

    # Para GATEWAY: armar pg_setup_items (banco + concepto).
    pg_setup_items = []
    if qtype == "GATEWAY":
        for (bank, product), _qty in grid_pairs.items():
            pg_setup_items.append({
                "concepto": product,
                "banco": bank,
                "costo": 0,
                "observacion": "",
            })

    # branch_details para multitienda
    branch_details = []
    if payload.is_multistore:
        for s in payload.stores:
            branch_details.append({"store_name": s.name, "quantity": int(s.box_count)})

    now_iso = datetime.now(timezone.utc).isoformat()
    # Pseudo quote_number — usado solo en logs/notificaciones; NO se persiste en `quotes`.
    pseudo_quote_number = f"DIRECT-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    pseudo_quote_id = f"dq_{uuid.uuid4().hex[:12]}"

    synthetic_quote = {
        "quote_id": pseudo_quote_id,
        "quote_number": pseudo_quote_number,
        "client_id": payload.client_id,
        "client_segment": sede,
        "sede": sede,
        "quote_category": "direct_project",  # mapeado por notification_engine._quote_to_biz_sub
        "quote_type": qtype,
        "services": services,
        "pg_setup_items": pg_setup_items,
        "hardware": [],
        "equipment_items": [],
        "branch_details": branch_details,
        "sponsor_bank_id": payload.sponsor_bank_id,
        "sponsor_bank_name": payload.sponsor_bank_name,
        "integrator_name": payload.integrator_name,
        "integrator_app_name": payload.integrator_app_name,
        "pinpad_model": payload.pinpad_model,
        "fiscal_printer_model": payload.fiscal_printer_model,
        "cantidad_cajas": payload.cantidad_cajas,
        "economic_group": payload.economic_group or "Sin Grupo Económico",
        "fantasy_name": payload.fantasy_name or client.get("fantasy_name") or client.get("legal_name") or "",
        "payment_gateway_link": payload.payment_gateway_link,
        "total_usd": 0,
        "total_bs": 0,
        "iva_exempt": bool(client.get("iva_exempt", False)),
        "implementation_instructions": payload.implementation_instructions or None,
        "created_at": now_iso,
        "created_by_user_id": user.get("user_id"),
        "is_irregular": False,
        "irregular_exceptions": [],
        "attachments": [],
        "preassigned_serials": [],
        "pinpad_serials": [pp.model_dump() for pp in payload.pinpad_serials],
        "equipments": [eq.model_dump() for eq in payload.equipment_serials],
    }

    # ---- Reservar número PRD-XXXX antes de crear el proyecto ----
    # _create_project_from_quote usa la secuencia PRY-; sobreescribimos
    # post-creación para usar el prefijo PRD- propio del flujo directo.
    sede_code = sede[:3].upper()

    # Llamar al builder existente (deja proyecto creado con número PRY-).
    multistore_data = None
    if payload.is_multistore:
        multistore_data = {
            "is_multistore": True,
            "stores": [{"name": s.name, "box_count": int(s.box_count)} for s in payload.stores],
        }

    equipment_data = [eq.model_dump() for eq in payload.equipment_serials] or None
    pp_serials = [pp.model_dump() for pp in payload.pinpad_serials] or None

    try:
        await _create_project_from_quote(
            synthetic_quote,
            pseudo_quote_id,
            multistore_data,
            equipment_data,
            "vpos_mpos" if qtype in {"VPOS", "MPOS"} else ("payment_gateway" if qtype == "GATEWAY" else "link_pago"),
            None,           # server_name no aplica
            pp_serials,
            payload.economic_group or "Sin Grupo Económico",
            payload.fantasy_name or None,
            payload.implementation_instructions or None,
            keep_quote_active=False,
            fiscal_printer_model=payload.fiscal_printer_model,
        )
    except Exception as e:
        logger.exception(f"Error creando proyecto directo: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando proyecto: {e}")

    # Localizar el proyecto recién creado por quote_id y reasignar número PRD-XXXX.
    project = await db.projects.find_one({"quote_id": pseudo_quote_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=500, detail="Proyecto creado pero no se pudo recuperar")

    prd_number = await _next_direct_project_number(sede_code)
    await db.projects.update_one(
        {"project_id": project["project_id"]},
        {"$set": {
            "project_number": prd_number,
            "origin": "direct",
            "direct_project": True,
            "payment_gateway_link": payload.payment_gateway_link,
            "pinpad_bank": payload.pinpad_bank,
            # Persistir la grilla original para auditoría / re-emisión
            "boxes_grid": [b.model_dump() for b in payload.boxes_grid],
        }},
    )
    project["project_number"] = prd_number

    # Limpiar quote_id pseudo (no apunta a ningún documento real) — opcional;
    # lo dejamos por trazabilidad pero marcamos `quote_number` con sentido.
    await db.projects.update_one(
        {"project_id": project["project_id"]},
        {"$set": {"quote_number": prd_number}},
    )

    # ---- Generar Ficha Técnica PDF ----
    # generate_implementation_pdf espera (quote, client, contacts, branches).
    # Le pasamos la synthetic_quote enriquecida con el quote_number final
    # para que el PDF use PRD-XXXX en el encabezado.
    synthetic_quote_for_pdf = dict(synthetic_quote)
    synthetic_quote_for_pdf["quote_number"] = prd_number
    contacts = client.get("contacts") or []
    try:
        pdf_bytes = generate_implementation_pdf(
            synthetic_quote_for_pdf, client, contacts, branch_details,
        )
    except Exception as e:
        logger.warning(f"[direct-projects] PDF generation failed (project ya creado): {e}")
        pdf_bytes = None

    # ---- Notificación automática vía motor dinámico ----
    notification_result = {"dispatched": False, "reason": "no_config"}
    try:
        # Re-fetch quote-equivalent payload con datos del proyecto creado para
        # alimentar las variables del template engine.
        notif_quote = dict(synthetic_quote_for_pdf)
        notif_quote["project_id"] = project["project_id"]
        notif_quote["project_number"] = prd_number
        notif_quote["client_email"] = (contacts[0].get("email") if contacts else "") or ""

        dispatched = await engine_try_dispatch(
            "send_to_implementation",
            notif_quote,
            user,
            implementation_pdf_bytes=pdf_bytes,
        )
        notification_result = {"dispatched": bool(dispatched), "reason": "ok" if dispatched else "no_config"}
    except Exception as e:
        logger.warning(f"[direct-projects] Notification dispatch failed: {e}")
        notification_result = {"dispatched": False, "reason": str(e)}

    # ---- Bitácora ----
    await db.bitacora.insert_one({
        "action": "direct_project_created",
        "project_id": project["project_id"],
        "project_number": prd_number,
        "client_id": payload.client_id,
        "executed_by": user.get("email"),
        "executed_by_name": f"{user.get('first_name','')} {user.get('last_name','')}".strip() or user.get("email"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "quote_type": qtype,
        "cantidad_cajas": payload.cantidad_cajas,
        "notification": notification_result,
    })

    return {
        "message": "Proyecto directo creado",
        "project_id": project["project_id"],
        "project_number": prd_number,
        "notification": notification_result,
    }


# =================== Excel: plantillas + parser ===================
def _build_excel(rows: list[list], headers: list[str], sheet_name: str = "Plantilla") -> bytes:
    """Construye un .xlsx en memoria. Usa openpyxl (ya disponible en el stack)."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@router.get("/direct-projects/excel-templates/serials")
async def excel_template_serials(authorization: Optional[str] = Header(None)):
    """Plantilla descargable para cargar seriales en masa: Modelo + Serial."""
    await _require_direct_projects_access(authorization)
    content = _build_excel(
        rows=[
            ["Verifone Vx520", "ABC123456"],
            ["Ingenico iCT220", "XYZ987654"],
        ],
        headers=["Modelo", "Serial"],
        sheet_name="Seriales",
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_seriales.xlsx"'},
    )


@router.get("/direct-projects/excel-templates/branches")
async def excel_template_branches(authorization: Optional[str] = Header(None)):
    """Plantilla descargable para cargar sucursales: Nombre + Cantidad Cajas."""
    await _require_direct_projects_access(authorization)
    content = _build_excel(
        rows=[
            ["Sucursal Centro", 3],
            ["Sucursal Norte", 2],
        ],
        headers=["Nombre Sucursal", "Cantidad Cajas"],
        sheet_name="Sucursales",
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_sucursales.xlsx"'},
    )


@router.post("/direct-projects/excel-parse/serials")
async def excel_parse_serials(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Parsea un Excel con columnas Modelo + Serial. Retorna lista JSON."""
    await _require_direct_projects_access(authorization)
    from openpyxl import load_workbook
    raw = await file.read()
    try:
        wb = load_workbook(BytesIO(raw), data_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel inválido: {e}")

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {"items": [], "errors": ["El archivo está vacío o solo contiene cabecera"]}

    out, errors = [], []
    for idx, row in enumerate(rows[1:], start=2):  # saltar cabecera
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        modelo = str(row[0] or "").strip() if len(row) > 0 else ""
        serial = str(row[1] or "").strip() if len(row) > 1 else ""
        if not modelo or not serial:
            errors.append(f"Fila {idx}: Modelo y Serial son obligatorios")
            continue
        out.append({"modelo": modelo, "serial": serial})
    return {"items": out, "errors": errors, "total": len(out)}


@router.post("/direct-projects/excel-parse/branches")
async def excel_parse_branches(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Parsea un Excel con columnas Nombre + Cantidad Cajas. Retorna lista JSON."""
    await _require_direct_projects_access(authorization)
    from openpyxl import load_workbook
    raw = await file.read()
    try:
        wb = load_workbook(BytesIO(raw), data_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel inválido: {e}")

    rows = list(ws.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        return {"items": [], "errors": ["El archivo está vacío o solo contiene cabecera"]}

    out, errors = [], []
    for idx, row in enumerate(rows[1:], start=2):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        name = str(row[0] or "").strip() if len(row) > 0 else ""
        try:
            box_count = int(row[1]) if len(row) > 1 and row[1] is not None else 0
        except (TypeError, ValueError):
            errors.append(f"Fila {idx}: Cantidad de Cajas no es un número entero")
            continue
        if not name or box_count <= 0:
            errors.append(f"Fila {idx}: Nombre y Cantidad Cajas (>0) son obligatorios")
            continue
        out.append({"name": name, "box_count": box_count})
    return {"items": out, "errors": errors, "total": len(out)}
