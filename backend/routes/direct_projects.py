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
    """Una fila del reel de cajas: [Cantidad] + [Banco] + [Producto]."""
    quantity: int = Field(ge=1)
    bank_name: str
    product_name: str
    store_name: Optional[str] = None  # solo para multitienda


class DirectProjectStore(BaseModel):
    name: str
    box_count: int


class DirectProjectSerial(BaseModel):
    """Serial de Pinpad. El `modelo` es opcional (Iter38, feb 2026): el operador
    solo está obligado a capturar el número de serial; la asociación con un
    modelo de hardware se hace a nivel global (`pinpad_model` de la cabecera)."""
    modelo: Optional[str] = ""
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
    # Patrocinio relacional (homologado con Cotizaciones): si el Banco Patrocinante
    # elegido es un Procesador, se designa el banco final vinculado.
    sponsor_processor_id: Optional[str] = None
    sponsor_processor_name: Optional[str] = None

    # Integrador (cascada Integrador → App)
    integrator_id: Optional[str] = None
    integrator_name: Optional[str] = None
    integrator_app_name: Optional[str] = None

    # Hardware (solo VPOS / MPOS) — pinpad_model ahora viene del catálogo de hardware
    pinpad_model: Optional[str] = None
    # Patrocinador de Pinpads: 'client' | 'infrastructure' | 'bank' (None = legacy → 'bank').
    pinpad_provider: Optional[str] = None
    pinpad_bank: Optional[str] = None
    # Patrocinio relacional del Pinpad: si el Banco del Pinpad seleccionado es un
    # Procesador, se designa el banco final vinculado (Procesador → Banco).
    pinpad_processor_id: Optional[str] = None
    pinpad_processor_name: Optional[str] = None
    fiscal_printer_model: Optional[str] = None
    pinpad_serials: list[DirectProjectSerial] = Field(default_factory=list)

    # Configuración Técnica (homologado con "Enviar a Implementación")
    # server_name: "Multicomercio MSC" | "Multicomercio MSC2" | <texto libre si "Propio">
    server_name: Optional[str] = None
    communication_type: Optional[str] = "SSL"  # "SSL" | "VPN"

    # Multitienda
    is_multistore: bool = False
    stores: list[DirectProjectStore] = Field(default_factory=list)

    # Grilla (Caja -> Banco + Producto)
    boxes_grid: list[DirectProjectBox] = Field(default_factory=list)

    # Instrucciones para el implementador
    implementation_instructions: Optional[str] = None


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
    # Modelo de Pinpad: OPCIONAL (puede no estar disponible en la etapa inicial del despliegue).

    if payload.is_multistore:
        if not payload.stores:
            raise HTTPException(status_code=400, detail="Multitienda activado: debe cargar al menos una sucursal")
        total_boxes = sum(int(s.box_count or 0) for s in payload.stores)
        if total_boxes != payload.cantidad_cajas:
            raise HTTPException(
                status_code=400,
                detail=f"La suma de cajas por sucursal ({total_boxes}) debe coincidir con Cantidad de Cajas ({payload.cantidad_cajas}).",
            )

    # Seriales de Pinpad: OPCIONALES. Si NO se cargan, se permite guardar el proyecto.
    # Solo cuando el operador SÍ carga seriales se valida la consistencia con Cantidad de Cajas.
    if requires_hw:
        n_serials = len(payload.pinpad_serials or [])
        if n_serials > 0 and n_serials != payload.cantidad_cajas:
            raise HTTPException(
                status_code=400,
                detail=f"La cantidad de seriales Pinpad cargados ({n_serials}) debe coincidir con Cantidad de Cajas ({payload.cantidad_cajas}).",
            )

    if len(payload.boxes_grid) == 0:
        raise HTTPException(
            status_code=400,
            detail="La grilla debe contener al menos una fila (cantidad + banco + producto).",
        )
    # Iter38: la grilla es INDEPENDIENTE de cantidad_cajas (la matriz banco/producto
    # se construye con la información comercial; ya no se compara con la cabecera).
    for i, box in enumerate(payload.boxes_grid):
        if not (box.bank_name or "").strip():
            raise HTTPException(status_code=400, detail=f"Fila #{i+1}: banco requerido")
        if not (box.product_name or "").strip():
            raise HTTPException(status_code=400, detail=f"Fila #{i+1}: producto requerido")

    # Segmento del cliente: se conserva desde la ficha del cliente (PYME/CORP).
    client_segment = (client.get("client_segment") or "PYME").upper()
    if client_segment not in {"PYME", "CORP"}:
        client_segment = "PYME"
    # Sede del proyecto: se hereda de la ficha del USUARIO en sesión (no editable
    # por el operador) para evitar asignaciones a una sede que no le corresponde.
    # La sede es el identificador de sucursal del usuario (ej. "TBP"), NO PYME/CORP.
    sede = (user.get("sede") or "").strip()

    # ---- Construir "cotización fantasma" en memoria ----
    # Agrupar la grilla por (bank, product) → cantidad. Esto alimenta
    # `services` para que `_create_project_from_quote` arme la implementation_matrix.
    grid_pairs: dict[tuple[str, str], int] = {}
    for box in payload.boxes_grid:
        key = (box.bank_name.strip(), box.product_name.strip())
        grid_pairs[key] = grid_pairs.get(key, 0) + int(box.quantity)

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

    # Patrocinador de Pinpads (3 opciones excluyentes). La fila "Patrocinador de
    # Pinpads" de la Ficha Técnica usa sponsor_bank_name/sponsor_processor_name.
    _pp_provider = (payload.pinpad_provider or "").strip().lower()
    if not _pp_provider:
        # Compatibilidad: si no llega 'pinpad_provider' pero hay banco, es 'bank'.
        _pp_provider = "bank" if (payload.pinpad_bank or "").strip() else ""
    if _pp_provider == "client":
        _pp_bank_name = "Los Pinpads son suministrados por el Cliente"
        _pp_processor_name = None
    elif _pp_provider == "infrastructure":
        _pp_bank_name = "Los Pinpads son suministrados por Infraestructura"
        _pp_processor_name = None
    else:  # 'bank' o vacío → comportamiento estándar (banco/procesador)
        _pp_bank_name = (payload.pinpad_bank or "").strip() or None
        _pp_processor_name = (payload.pinpad_processor_name or "").strip() or None

    synthetic_quote = {
        "quote_id": pseudo_quote_id,
        "quote_number": pseudo_quote_number,
        "client_id": payload.client_id,
        "client_segment": client_segment,
        "sede": sede,
        "quote_category": "direct_project",  # mapeado por notification_engine._quote_to_biz_sub
        "quote_type": qtype,
        "services": services,
        "pg_setup_items": pg_setup_items,
        "hardware": [],
        "equipment_items": [],
        "branch_details": branch_details,
        # Patrocinador de Pinpads (homologado con Cotizaciones = sponsor_bank): en
        # Proyectos Directos proviene del campo "Banco del Pinpad" (pinpad_bank).
        # Es independiente del Patrocinador de la Implementación.
        "sponsor_bank_id": None,
        "sponsor_bank_name": _pp_bank_name,
        # Procesador asociado al Patrocinador de Pinpads (Procesador → Banco).
        "sponsor_processor_id": payload.pinpad_processor_id if _pp_provider == "bank" else None,
        "sponsor_processor_name": _pp_processor_name,
        # Patrocinador de la Implementación = "Banco Patrocinante" (Sección Definición
        # Comercial). Alimenta patrocinador_label ("Procesador — Banco" o solo "Banco")
        # y la columna de patrocinio del grid.
        "sponsored_implementation": bool(payload.sponsor_bank_id or payload.sponsor_processor_id),
        "sponsoring_bank_id": payload.sponsor_bank_id,
        "sponsoring_bank_name": payload.sponsor_bank_name,
        "sponsoring_processor_id": payload.sponsor_processor_id,
        "sponsoring_processor_name": payload.sponsor_processor_name,
        "integrator_name": payload.integrator_name,
        "integrator_app_name": payload.integrator_app_name,
        "pinpad_model": payload.pinpad_model,
        "fiscal_printer_model": payload.fiscal_printer_model,
        "server_name": (payload.server_name or "").strip() or None,
        "communication_type": (payload.communication_type or "SSL").strip().upper(),
        "requires_vpn": (payload.communication_type or "SSL").strip().upper() == "VPN",
        "cantidad_cajas": payload.cantidad_cajas,
        "economic_group": payload.economic_group or "Sin Grupo Económico",
        "fantasy_name": payload.fantasy_name or client.get("fantasy_name") or client.get("legal_name") or "",
        "total_usd": 0,
        "total_bs": 0,
        "iva_exempt": bool(client.get("iva_exempt", False)),
        "implementation_instructions": payload.implementation_instructions or None,
        "created_at": now_iso,
        "sent_to_implementation_at": now_iso,
        "created_by_user_id": user.get("user_id"),
        "is_irregular": False,
        "irregular_exceptions": [],
        "attachments": [],
        "preassigned_serials": [],
        "pinpad_serials": [pp.model_dump() for pp in payload.pinpad_serials],
        "equipments": [],
    }

    # Llamar al builder existente (deja proyecto creado con número PRY-).
    multistore_data = None
    if payload.is_multistore:
        multistore_data = {
            "is_multistore": True,
            "stores": [{"name": s.name, "box_count": int(s.box_count)} for s in payload.stores],
        }

    equipment_data = None
    pp_serials = [pp.model_dump() for pp in payload.pinpad_serials] or None

    try:
        await _create_project_from_quote(
            synthetic_quote,
            pseudo_quote_id,
            multistore_data,
            equipment_data,
            "vpos_mpos" if qtype in {"VPOS", "MPOS"} else ("payment_gateway" if qtype == "GATEWAY" else "link_pago"),
            (payload.server_name or "").strip() or None,   # server_name (Configuración Técnica)
            pp_serials,
            payload.economic_group or "Sin Grupo Económico",
            payload.fantasy_name or None,
            payload.implementation_instructions or None,
            keep_quote_active=False,
            fiscal_printer_model=payload.fiscal_printer_model,
            communication_type=(payload.communication_type or "SSL").strip().upper(),
        )
    except Exception as e:
        logger.exception(f"Error creando proyecto directo: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando proyecto: {e}")

    # ---- Localizar el proyecto recién creado por quote_id ----
    # Iter38: el usuario solicitó usar la nomenclatura ESTÁNDAR (PRY-XXXX) —
    # ya no sobrescribimos a PRD-. _create_project_from_quote asigna PRY-
    # internamente y compartimos la misma secuencia con el resto de proyectos
    # del sistema.
    project = await db.projects.find_one({"quote_id": pseudo_quote_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=500, detail="Proyecto creado pero no se pudo recuperar")

    prd_number = project["project_number"]
    await db.projects.update_one(
        {"project_id": project["project_id"]},
        {"$set": {
            "origin": "direct",
            "direct_project": True,
            # Sede heredada de la ficha del usuario en sesión (seguridad de perfiles).
            "sede": sede,
            "pinpad_provider": _pp_provider or None,
            "pinpad_bank": payload.pinpad_bank,
            # Persistir la grilla original para auditoría / re-emisión
            "boxes_grid": [b.model_dump() for b in payload.boxes_grid],
            # quote_number cosmético (el quote_id es pseudo, no apunta a quote real)
            "quote_number": prd_number,
        }},
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

        # Escenario B (Patrocinador de Pinpads = Infraestructura): aviso automático
        # al equipo de Infraestructura, replicando el motor de notificaciones
        # (acción configurable 'notify_infrastructure_pinpads') con la Ficha adjunta.
        if _pp_provider == "infrastructure":
            try:
                infra_dispatched = await engine_try_dispatch(
                    "notify_infrastructure_pinpads",
                    notif_quote,
                    user,
                    implementation_pdf_bytes=pdf_bytes,
                )
                notification_result["infrastructure"] = {
                    "dispatched": bool(infra_dispatched),
                    "reason": "ok" if infra_dispatched else "no_config",
                }
            except Exception as e:
                logger.warning(f"[direct-projects] Infra notification dispatch failed: {e}")
                notification_result["infrastructure"] = {"dispatched": False, "reason": str(e)}
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
    """Plantilla descargable para cargar seriales en masa.

    Iter38: el modelo es opcional. Plantilla simplificada a una sola columna
    'Serial' — el operador puede agregar opcionalmente la columna 'Modelo'
    si la necesita para auditoría.
    """
    await _require_direct_projects_access(authorization)
    content = _build_excel(
        rows=[
            ["ABC123456"],
            ["XYZ987654"],
            ["1100A2B3C4"],
        ],
        headers=["Serial"],
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
    """Parsea un Excel con columnas Modelo + Serial. Retorna lista JSON.

    Robusto frente a:
      - Cabecera opcional (auto-detectada).
      - Filas vacías intercaladas.
      - Espacios y tipos numéricos en serial (ej. seriales 100% numéricos).
      - Archivos .xlsx (LibreOffice/Excel/Google Sheets).
    """
    await _require_direct_projects_access(authorization)
    from openpyxl import load_workbook
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    try:
        wb = load_workbook(BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel inválido o corrupto: {e}")

    if ws is None:
        return {"items": [], "errors": ["El archivo no tiene hojas activas"], "total": 0}

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"items": [], "errors": ["El archivo está vacío"], "total": 0}

    # Detectar cabecera: si la fila 1 tiene "modelo"/"serial" (case insensitive) en alguna columna.
    first = rows[0]
    header_tokens = {"modelo", "serial", "model", "serie", "número"}
    has_header = False
    if first:
        for cell in first:
            if cell is None:
                continue
            s = str(cell).strip().lower()
            if any(tok in s for tok in header_tokens):
                has_header = True
                break
    data_rows = rows[1:] if has_header else rows

    out, errors = [], []
    for idx, row in enumerate(data_rows, start=(2 if has_header else 1)):
        if not row or all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue
        # Iter38: el SERIAL es lo único obligatorio. El modelo es opcional.
        # Soporte para dos layouts:
        #   (a) [Modelo, Serial]  ← layout legacy (2 cols)
        #   (b) [Serial]          ← layout simplificado (1 col)
        # Detección automática: si la fila tiene una sola columna con datos o la
        # primera columna parece un serial (alfa-num típico) la usamos como serial.
        col0 = row[0] if len(row) > 0 else None
        col1 = row[1] if len(row) > 1 else None

        if col1 is None or (isinstance(col1, str) and not col1.strip()):
            # Layout (b): única columna con el serial.
            serial_raw = col0
            modelo = ""
        else:
            # Layout (a): Modelo en col0, Serial en col1.
            modelo = str(col0).strip() if col0 is not None else ""
            serial_raw = col1

        if isinstance(serial_raw, float) and serial_raw.is_integer():
            serial = str(int(serial_raw))
        else:
            serial = str(serial_raw).strip() if serial_raw is not None else ""

        if not serial:
            errors.append(f"Fila {idx}: Serial es obligatorio")
            continue
        out.append({"modelo": modelo, "serial": serial})

    if not out and not errors:
        errors.append("No se detectaron filas con datos válidos")

    return {"items": out, "errors": errors, "total": len(out)}


@router.post("/direct-projects/excel-parse/branches")
async def excel_parse_branches(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
):
    """Parsea un Excel con columnas Nombre + Cantidad Cajas. Retorna lista JSON.

    Robusto frente a:
      - Filas vacías intercaladas
      - Cabeceras con texto distinto al estándar (acepta cualquier valor en la fila 1
        siempre que no se confunda con un dato real: si la primera fila contiene un
        número entero > 0 en la columna B, se asume que NO hay cabecera y se procesa
        desde la fila 1).
      - Hojas vacías
      - Tipos numéricos float (ej. 3.0) o string ("3") en cantidad_cajas
      - Espacios y mayúsculas/minúsculas en el header
      - Archivos .xlsx generados por LibreOffice / Excel / Google Sheets
    """
    await _require_direct_projects_access(authorization)
    from openpyxl import load_workbook
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    try:
        wb = load_workbook(BytesIO(raw), data_only=True, read_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel inválido o corrupto: {e}")

    if ws is None:
        return {"items": [], "errors": ["El archivo no tiene hojas activas"], "total": 0}

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {"items": [], "errors": ["El archivo está vacío"], "total": 0}

    # Detectar si la primera fila es cabecera: si la columna B contiene un entero válido
    # asumimos que es data desde la fila 1 (sin cabecera).
    first = rows[0]
    def _is_header(r):
        if not r or len(r) < 2:
            return True
        b = r[1]
        if b is None:
            return True
        try:
            v = int(float(str(b).strip()))
            return v <= 0  # si es un número válido > 0, no es cabecera
        except (TypeError, ValueError):
            return True
    skip_first = _is_header(first)
    data_rows = rows[1:] if skip_first else rows

    out, errors = [], []
    for idx, row in enumerate(data_rows, start=(2 if skip_first else 1)):
        if not row or all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            continue
        name = ""
        box_count = 0
        try:
            if len(row) > 0 and row[0] is not None:
                name = str(row[0]).strip()
            if len(row) > 1 and row[1] is not None:
                # Acepta "3", 3, 3.0, " 3 "
                raw_v = row[1]
                if isinstance(raw_v, (int, float)):
                    box_count = int(raw_v)
                else:
                    box_count = int(float(str(raw_v).strip().replace(",", ".")))
        except (TypeError, ValueError):
            errors.append(f"Fila {idx}: Cantidad de Cajas no es un número válido ({row[1] if len(row) > 1 else 'vacío'})")
            continue
        if not name:
            errors.append(f"Fila {idx}: Nombre de sucursal vacío")
            continue
        if box_count <= 0:
            errors.append(f"Fila {idx} ({name}): Cantidad de Cajas debe ser >= 1")
            continue
        out.append({"name": name, "box_count": box_count})

    if not out and not errors:
        errors.append("No se detectaron filas con datos válidos")

    return {"items": out, "errors": errors, "total": len(out)}
