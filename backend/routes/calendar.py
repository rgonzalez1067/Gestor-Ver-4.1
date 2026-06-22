"""Rutas del Calendario Laboral (Días Festivos).

  - GET    /api/calendar/holidays         → lista de festivos (cualquier usuario autenticado)
  - POST   /api/calendar/holidays         → alta de festivo (solo Admin)
  - DELETE /api/calendar/holidays/{id}    → elimina festivo (solo Admin)

La gestión es solo-Admin; la lectura es abierta a usuarios autenticados para que
el panel de Proyectos y el motor SLA puedan calcular días hábiles.
"""
import logging
import uuid
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from config import db, get_current_user
from services.business_calendar import invalidate_holidays_cache

router = APIRouter(tags=["calendar"])
logger = logging.getLogger("calendar")


class HolidayCreate(BaseModel):
    holiday_date: str = Field(..., description="Fecha 'YYYY-MM-DD'")
    description: str = Field(..., min_length=1, max_length=150)
    recurring: bool = False


async def _require_admin(authorization: Optional[str]) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo el Administrador puede gestionar el Calendario Laboral")
    return user


@router.get("/calendar/holidays")
async def list_holidays(authorization: Optional[str] = Header(None)):
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="No autorizado")
    docs = await db.holidays.find({}, {"_id": 0}).to_list(2000)
    # Orden cronológico: recurrentes por MM-DD, específicos por fecha completa.
    docs.sort(key=lambda d: (d.get("holiday_date") or ""))
    return docs


@router.post("/calendar/holidays")
async def create_holiday(payload: HolidayCreate, authorization: Optional[str] = Header(None)):
    user = await _require_admin(authorization)

    raw = (payload.holiday_date or "").strip()[:10]
    try:
        parsed = date.fromisoformat(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Fecha inválida. Use formato YYYY-MM-DD.")
    iso = parsed.isoformat()
    desc = payload.description.strip()
    if not desc:
        raise HTTPException(status_code=400, detail="La descripción es obligatoria.")

    # Unicidad: para recurrentes, no permitir otra recurrente con el mismo MM-DD;
    # para específicos, no permitir otra con la misma fecha completa.
    if payload.recurring:
        md = iso[5:10]
        if await db.holidays.find_one({"recurring": True, "month_day": md}):
            raise HTTPException(status_code=409, detail=f"Ya existe un festivo recurrente para el {md[3:5]}/{md[0:2]}.")
    else:
        if await db.holidays.find_one({"recurring": {"$ne": True}, "holiday_date": iso}):
            raise HTTPException(status_code=409, detail="Ya existe un festivo registrado para esa fecha.")

    doc = {
        "holiday_id": f"hol_{uuid.uuid4().hex[:12]}",
        "holiday_date": iso,
        "month_day": iso[5:10],
        "description": desc,
        "recurring": bool(payload.recurring),
        "created_by": user.get("user_id"),
        "created_by_name": user.get("name") or user.get("email"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.holidays.insert_one(doc)
    invalidate_holidays_cache()
    doc.pop("_id", None)
    return doc


@router.delete("/calendar/holidays/{holiday_id}")
async def delete_holiday(holiday_id: str, authorization: Optional[str] = Header(None)):
    await _require_admin(authorization)
    res = await db.holidays.delete_one({"holiday_id": holiday_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Festivo no encontrado")
    invalidate_holidays_cache()
    return {"message": "Festivo eliminado", "holiday_id": holiday_id}
