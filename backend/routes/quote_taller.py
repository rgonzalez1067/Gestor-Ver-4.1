"""Endpoints del módulo "Taller" y catálogo de insumos para reparaciones.

Extraído de `quote_actions.py` para separar la gestión de equipos físicos en taller
y exports relacionados.
"""
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timezone
import io
import logging

from config import db, get_current_user


router = APIRouter()
logger = logging.getLogger(__name__)


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
