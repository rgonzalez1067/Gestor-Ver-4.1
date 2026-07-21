"""Endpoints del módulo "Taller" y catálogo de insumos para reparaciones.

Extraído de `quote_actions.py` para separar la gestión de equipos físicos en taller
y exports relacionados.
"""
from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import io
import uuid
import base64
import logging

from config import db, get_current_user
from services.other_actions_engine import dispatch_other_action


router = APIRouter()
logger = logging.getLogger(__name__)


class RecepcionModelo(BaseModel):
    model_id: str = ""
    model_name: str
    serials: List[str] = []


class RecepcionRequest(BaseModel):
    client_id: str
    client_name: str = ""
    client_rif: str = ""
    models: List[RecepcionModelo] = []


@router.post("/taller/recepcion")
async def recepcion_equipos(payload: RecepcionRequest, authorization: Optional[str] = Header(None)):
    """Registra la recepción física de equipos en el Taller con estatus 'Recibido'
    y dispara la notificación configurable 'taller_recepcion_equipos'.
    """
    user = await get_current_user(authorization)
    client = await db.clients.find_one({"client_id": payload.client_id}, {"_id": 0}) or {}
    client_name = (payload.client_name or client.get("fantasy_name")
                   or client.get("legal_name") or client.get("commercial_name") or "").strip()
    client_rif = (payload.client_rif or client.get("rif") or "").strip()
    client_email = (client.get("email") or "").strip()
    if not client_email:
        for c in (client.get("contacts") or []):
            if (c.get("email") or "").strip():
                client_email = c["email"].strip()
                break

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    created_ids = []
    equipos_desc = []
    equipos_pairs = []
    for m in payload.models:
        serials = [s.strip() for s in (m.serials or []) if s and s.strip()]
        for s in serials:
            doc = {
                "taller_equipo_id": f"te_{uuid.uuid4().hex[:12]}",
                "serial": s,
                "modelo": m.model_name,
                "modelo_id": m.model_id,
                "client_id": payload.client_id,
                "client_name": client_name,
                "quote_id": None,
                "quote_number": None,
                "estatus": "Recibido",
                "fecha_ingreso": now_iso,
                "fecha_entrega": None,
                "fecha_recepcion": now_iso,
                "recibido_por": user.get("email"),
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            await db.taller_equipos.insert_one(doc)
            created_ids.append(doc["taller_equipo_id"])
            equipos_desc.append(f"{m.model_name} · Serial {s}")
            equipos_pairs.append((m.model_name, s))

    if not created_ids:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un equipo con serial")

    fecha_str = now.strftime("%d/%m/%Y %H:%M")
    tpl_vars = {
        "Nombre_Cliente": client_name, "nombre_cliente": client_name,
        "Rif_Cliente": client_rif, "rif_cliente": client_rif,
        "Cantidad_Equipos": str(len(created_ids)),
        "Equipos_Recibidos": "\n".join(f"- {e}" for e in equipos_desc),
        "Equipos_Recibidos_HTML": "<br>".join(equipos_desc),
        "Fecha_Recepcion": fecha_str, "fecha_sistema": fecha_str,
        "usuario_ejecutor": user.get("email", ""),
    }
    try:
        pdf_bytes = _generate_reception_pdf(client_name, client_rif, equipos_pairs, fecha_str, user.get("email", ""))
        pdf_att = [{
            "filename": f"Comprobante_Recepcion_{(client_name or 'Cliente').replace(' ', '_')[:40]}.pdf",
            "content": base64.b64encode(pdf_bytes).decode("utf-8"),
        }]
    except Exception as e:  # noqa: BLE001
        logger.error(f"[taller-recepcion] fallo al generar PDF comprobante: {e}")
        pdf_att = None

    try:
        await dispatch_other_action(
            "taller_recepcion_equipos", tpl_vars, current_user=user,
            fallback_subject=f"Recepción de equipos en taller — {client_name}",
            extra_cc=[client_email] if client_email else None,
            extra_attachments=pdf_att,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[taller-recepcion] fallo al notificar: {e}")

    return {"success": True, "created": len(created_ids), "estatus": "Recibido"}


def _generate_reception_pdf(client_name, client_rif, equipos, fecha_str, user_email):
    """Genera el PDF 'Comprobante de Recepción de Equipos' (bytes)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as rl_canvas

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter)
    w, h = letter

    def header(y0):
        c.setFillColorRGB(0.08, 0.16, 0.28)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(2.5 * cm, y0, "Comprobante de Recepción de Equipos")
        c.setFont("Helvetica", 9); c.setFillGray(0.45)
        c.drawString(2.5 * cm, y0 - 0.55 * cm, "Gestión de Taller · Mega Soft")
        c.setFillGray(0)
        return y0 - 1.4 * cm

    y = header(h - 2.6 * cm)
    c.setFont("Helvetica", 11)
    for line in [f"Cliente: {client_name}", f"RIF: {client_rif}",
                 f"Fecha de recepción: {fecha_str}", f"Recibido por: {user_email}"]:
        c.drawString(2.5 * cm, y, line); y -= 0.55 * cm

    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2.5 * cm, y, f"Equipos recibidos ({len(equipos)})")
    y -= 0.6 * cm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(2.5 * cm, y, "#"); c.drawString(3.4 * cm, y, "Modelo"); c.drawString(12 * cm, y, "Serial")
    c.line(2.5 * cm, y - 0.15 * cm, w - 2.5 * cm, y - 0.15 * cm)
    c.setFont("Helvetica", 9)
    for i, (modelo, serial) in enumerate(equipos, 1):
        y -= 0.5 * cm
        if y < 2.6 * cm:
            c.showPage(); y = header(h - 2.6 * cm); c.setFont("Helvetica", 9)
        c.drawString(2.5 * cm, y, str(i))
        c.drawString(3.4 * cm, y, str(modelo)[:60])
        c.drawString(12 * cm, y, str(serial)[:28])

    c.setFont("Helvetica", 8); c.setFillGray(0.5)
    c.drawString(2.5 * cm, 1.8 * cm,
                 "Documento generado automáticamente. Estatus asignado a los equipos: \"Recibido\".")
    c.showPage(); c.save(); buf.seek(0)
    return buf.getvalue()


@router.get("/taller/pending-count")
async def get_taller_pending_count(authorization: Optional[str] = Header(None)):
    """Contador de equipos en taller con estatus 'Recibido' (pendientes por cotizar).
    Usado por el badge del menú de Gestión de Taller."""
    await get_current_user(authorization)
    count = await db.taller_equipos.count_documents({"estatus": "Recibido"})
    return {"pending": count}


@router.get("/taller/equipos-disponibles")
async def get_equipos_disponibles(client_id: str, authorization: Optional[str] = Header(None)):
    """Lista los equipos con estatus 'Recibido' de un cliente para vincularlos a una
    cotización de reparación (Fase 2 - Trazabilidad de Taller)."""
    await get_current_user(authorization)
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id es requerido")
    equipos = await db.taller_equipos.find(
        {"client_id": client_id, "estatus": "Recibido"},
        {"_id": 0, "taller_equipo_id": 1, "serial": 1, "modelo": 1, "modelo_id": 1,
         "fecha_ingreso": 1, "fecha_recepcion": 1},
    ).sort("fecha_ingreso", 1).to_list(1000)
    return {"equipos": equipos, "total": len(equipos)}


@router.post("/taller/parse-serials")
async def parse_serials_excel(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Extrae la lista de seriales (única, en orden) de un Excel para la Recepción."""
    await get_current_user(authorization)
    import openpyxl
    if not (file.filename or "").endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="El archivo debe ser formato Excel (.xlsx)")
    try:
        contents = await file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True)
        ws = wb.active
        seen, serials = set(), []
        skip = ('serial', 'seriales', 'numero de serie', 'número de serie', 'serial number', 'nro', 'n/s')
        for row in ws.iter_rows(min_row=1, values_only=True):
            for cell in row:
                if cell is None:
                    continue
                val = str(cell).strip()
                if val and val.lower() not in skip and val not in seen:
                    seen.add(val); serials.append(val)
        wb.close()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Error al leer el Excel: {str(e)}")
    if not serials:
        raise HTTPException(status_code=400, detail="No se encontraron seriales en el archivo")
    return {"serials": serials, "count": len(serials)}


@router.get("/repair-supplies")
async def get_repair_supplies(authorization: Optional[str] = Header(None)):
    """Lista bienes tipo Accesorio y Componente para carga de insumos en reparaciones."""
    await get_current_user(authorization)
    items = await db.hardware.find(
        {"type": {"$in": ["Accesorio", "Componente", "Pieza"]}},
        {"_id": 0, "hardware_id": 1, "name": 1, "type": 1, "category": 1, "price_usd": 1}
    ).sort("name", 1).to_list(500)
    return items


@router.get("/taller-equipos")
async def get_taller_equipos(
    authorization: Optional[str] = Header(None),
    client_id: Optional[str] = None,
    estatus: Optional[str] = None,
    search: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
):
    """Consultar equipos en taller con filtros y cálculo de días en servidor."""
    await get_current_user(authorization)
    query = {}
    if client_id:
        query["client_id"] = client_id
    if estatus:
        query["estatus"] = estatus
    if search:
        search_re = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"serial": search_re},
            {"client_name": search_re},
            {"modelo": search_re},
            {"quote_number": search_re},
        ]
    if fecha_desde or fecha_hasta:
        date_filter = {}
        if fecha_desde:
            date_filter["$gte"] = fecha_desde
        if fecha_hasta:
            date_filter["$lte"] = fecha_hasta + "T23:59:59"
        query["fecha_ingreso"] = date_filter

    equipos = await db.taller_equipos.find(query, {"_id": 0}).to_list(2000)

    # Enriquecer con client_legal_name (Razón Social) para tooltip en grilla
    client_ids = list({e.get("client_id") for e in equipos if e.get("client_id")})
    legal_map = {}
    if client_ids:
        async for c in db.clients.find(
            {"client_id": {"$in": client_ids}},
            {"_id": 0, "client_id": 1, "legal_name": 1, "fantasy_name": 1},
        ):
            legal_map[c["client_id"]] = {
                "legal_name": c.get("legal_name", ""),
                "fantasy_name": c.get("fantasy_name", ""),
            }
    for eq in equipos:
        info = legal_map.get(eq.get("client_id"), {})
        eq["client_legal_name"] = info.get("legal_name", "")
        eq["client_fantasy_name"] = info.get("fantasy_name", "")

    # Calcular dias_en_taller en el servidor
    now = datetime.now(timezone.utc)
    for eq in equipos:
        fecha_ingreso_str = eq.get("fecha_ingreso", "")
        if fecha_ingreso_str:
            try:
                fi = datetime.fromisoformat(fecha_ingreso_str.replace("Z", "+00:00"))
                if fi.tzinfo is None:
                    fi = fi.replace(tzinfo=timezone.utc)
                delta = now - fi
                eq["dias_en_taller"] = max(delta.days, 0)
            except Exception:
                eq["dias_en_taller"] = 0
        else:
            eq["dias_en_taller"] = 0
        eq["alerta_retraso"] = eq["estatus"] == "En reparación" and eq["dias_en_taller"] > 15

    # Estadísticas
    total_en_reparacion = sum(1 for e in equipos if e.get("estatus") == "En reparación")
    total_entregados = sum(1 for e in equipos if e.get("estatus") == "Entregado")
    total_alerta = sum(1 for e in equipos if e.get("alerta_retraso"))

    return {
        "equipos": equipos,
        "total": len(equipos),
        "total_en_reparacion": total_en_reparacion,
        "total_entregados": total_entregados,
        "total_alerta": total_alerta,
    }


@router.get("/taller-equipos/{taller_equipo_id}/historial")
async def get_taller_equipo_historial(taller_equipo_id: str, authorization: Optional[str] = Header(None)):
    """Obtener historial/detalle de un equipo en taller."""
    await get_current_user(authorization)

    equipo = await db.taller_equipos.find_one({"taller_equipo_id": taller_equipo_id}, {"_id": 0})
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado en taller")

    # Calcular dias_en_taller
    now = datetime.now(timezone.utc)
    fecha_ingreso_str = equipo.get("fecha_ingreso", "")
    if fecha_ingreso_str:
        try:
            fi = datetime.fromisoformat(fecha_ingreso_str.replace("Z", "+00:00"))
            if fi.tzinfo is None:
                fi = fi.replace(tzinfo=timezone.utc)
            equipo["dias_en_taller"] = max((now - fi).days, 0)
        except Exception:
            equipo["dias_en_taller"] = 0

    # Obtener datos de la cotización
    quote = await db.quotes.find_one(
        {"quote_id": equipo.get("quote_id")},
        {"_id": 0, "status_history": 1, "quote_number": 1, "quote_status": 1, "created_by_user_id": 1, "approved_at": 1}
    )

    # Obtener usuario que creó/aprobó
    user_info = None
    if quote and quote.get("created_by_user_id"):
        user_info = await db.users.find_one(
            {"user_id": quote["created_by_user_id"]},
            {"_id": 0, "first_name": 1, "last_name": 1, "email": 1},
        )

    return {
        "equipo": equipo,
        "cotizacion": {
            "quote_number": quote.get("quote_number", "") if quote else "",
            "quote_status": quote.get("quote_status", "") if quote else "",
            "approved_at": quote.get("approved_at", "") if quote else "",
            "status_history": quote.get("status_history", []) if quote else [],
        },
        "recibido_por": {
            "nombre": f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip() if user_info else "Sistema",
            "email": user_info.get("email", "") if user_info else "",
        },
    }


@router.get("/taller-equipos/export-excel")
async def export_taller_equipos_excel(
    authorization: Optional[str] = Header(None),
    estatus: Optional[str] = None,
    search: Optional[str] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
):
    """Exportar equipos en taller a Excel."""
    await get_current_user(authorization)

    query = {}
    if estatus:
        query["estatus"] = estatus
    if search:
        search_re = {"$regex": search, "$options": "i"}
        query["$or"] = [{"serial": search_re}, {"client_name": search_re}, {"modelo": search_re}, {"quote_number": search_re}]
    if fecha_desde or fecha_hasta:
        date_filter = {}
        if fecha_desde:
            date_filter["$gte"] = fecha_desde
        if fecha_hasta:
            date_filter["$lte"] = fecha_hasta + "T23:59:59"
        query["fecha_ingreso"] = date_filter

    equipos = await db.taller_equipos.find(query, {"_id": 0}).to_list(2000)

    now = datetime.now(timezone.utc)
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Equipos en Taller"

    # Header styles
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="00447C", end_color="00447C", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )
    red_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    red_font = Font(color="991B1B", bold=True)

    headers = ["Serial", "Modelo", "Cliente", "Cotizacion Origen", "Estatus", "Fecha Ingreso", "Fecha Entrega", "Dias en Taller"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    for row_idx, eq in enumerate(equipos, 2):
        fecha_ingreso_str = eq.get("fecha_ingreso", "")
        dias = 0
        if fecha_ingreso_str:
            try:
                fi = datetime.fromisoformat(fecha_ingreso_str.replace("Z", "+00:00"))
                if fi.tzinfo is None:
                    fi = fi.replace(tzinfo=timezone.utc)
                dias = max((now - fi).days, 0)
            except Exception:
                pass

        fecha_entrega_str = eq.get("fecha_entrega") or ""
        is_alert = eq.get("estatus") == "En reparación" and dias > 15

        values = [
            eq.get("serial", ""),
            eq.get("modelo", ""),
            eq.get("client_name", ""),
            eq.get("quote_number", ""),
            eq.get("estatus", ""),
            fecha_ingreso_str[:10] if fecha_ingreso_str else "",
            fecha_entrega_str[:10] if fecha_entrega_str else "",
            dias,
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.border = thin_border
            if is_alert:
                cell.fill = red_fill
                if col == 8:
                    cell.font = red_font

    # Adjust column widths
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 18

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"equipos_taller_{now.strftime('%Y%m%d')}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.delete("/taller-equipos/{taller_equipo_id}")
async def delete_taller_equipo(taller_equipo_id: str, authorization: Optional[str] = Header(None)):
    """Eliminar un equipo del taller de reparaciones. Solo administradores."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar registros del taller")

    equipo = await db.taller_equipos.find_one({"taller_equipo_id": taller_equipo_id}, {"_id": 0})
    if not equipo:
        raise HTTPException(status_code=404, detail="Equipo no encontrado en taller")

    await db.taller_equipos.delete_one({"taller_equipo_id": taller_equipo_id})
    logger.info(f"Equipo taller {taller_equipo_id} eliminado por {current_user.get('email')}")
    return {"message": "Registro de taller eliminado exitosamente"}
