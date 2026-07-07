"""Motor de cálculo de días hábiles + caché de días festivos.

Centraliza el conteo de tiempos de proyectos para que excluya automáticamente
los fines de semana (sábado/domingo) y los días festivos parametrizados por la
empresa (colección `holidays`). Reemplaza el conteo de días naturales.

Convención de conteo (decidida con el usuario):
- `business_days_between(start, end)` cuenta los días hábiles en el intervalo
  (start, end] — es decir, EXCLUYE el día de inicio e INCLUYE los días hábiles
  posteriores hasta `end`. Esto refleja los "días hábiles transcurridos".
- `add_business_days(start, n)` devuelve la fecha del n-ésimo día hábil contando
  `start` como día 1 (inclusivo) — para fechas límite de hitos.
"""
import time
import logging
from datetime import date, timedelta

from config import db

logger = logging.getLogger("business_calendar")

_CACHE = {"specific": None, "recurring": None, "at": 0.0}
_TTL_SECONDS = 30

# Snapshot sincrónico de los últimos sets cargados (para usarlos desde código
# síncrono como el generador de PDF, que no puede hacer await).
_SNAPSHOT = {"specific": set(), "recurring": set()}


def invalidate_holidays_cache() -> None:
    """Limpia el caché en memoria de festivos (llamar al crear/eliminar)."""
    _CACHE["specific"] = None
    _CACHE["recurring"] = None
    _CACHE["at"] = 0.0


def get_cached_holiday_sets() -> tuple:
    """Acceso SÍNCRONO al último snapshot de festivos (puede estar vacío si aún
    no se ha hecho ninguna carga async). Uso: generador de PDF."""
    return _SNAPSHOT["specific"], _SNAPSHOT["recurring"]


async def get_holiday_sets() -> tuple:
    """Devuelve (specific, recurring): set de fechas 'YYYY-MM-DD' y set de 'MM-DD'."""
    now = time.time()
    if _CACHE["specific"] is not None and (now - _CACHE["at"]) < _TTL_SECONDS:
        return _CACHE["specific"], _CACHE["recurring"]
    specific, recurring = set(), set()
    docs = await db.holidays.find({}, {"_id": 0}).to_list(2000)
    for d in docs:
        hd = (d.get("holiday_date") or "")[:10]
        if not hd:
            continue
        if d.get("recurring"):
            recurring.add(hd[5:10])  # MM-DD
        else:
            specific.add(hd)
    _CACHE["specific"], _CACHE["recurring"], _CACHE["at"] = specific, recurring, now
    _SNAPSHOT["specific"], _SNAPSHOT["recurring"] = specific, recurring
    return specific, recurring


def is_business_day(d: date, specific: set, recurring: set) -> bool:
    """True si `d` es día hábil (no fin de semana ni festivo)."""
    if d.weekday() >= 5:  # 5=sábado, 6=domingo
        return False
    if d.isoformat() in specific:
        return False
    if d.strftime("%m-%d") in recurring:
        return False
    return True


def business_days_between(start: date, end: date, specific: set, recurring: set) -> int:
    """Días hábiles transcurridos en (start, end] (excluye el día de inicio)."""
    if not start or not end or end <= start:
        return 0
    count = 0
    cur = start + timedelta(days=1)
    while cur <= end:
        if is_business_day(cur, specific, recurring):
            count += 1
        cur += timedelta(days=1)
    return count


def add_business_days(start: date, n: int, specific: set, recurring: set) -> date:
    """Fecha del n-ésimo día hábil contando `start` como día 1 (inclusivo).

    Ej.: start=Lunes, n=3, con Martes festivo → Lunes(1), Miércoles(2), Jueves(3) → Jueves.
    """
    if n <= 0:
        return start
    counted = 0
    cur = start
    # El día de inicio cuenta como día 1 si es hábil.
    while True:
        if is_business_day(cur, specific, recurring):
            counted += 1
            if counted >= n:
                return cur
        cur += timedelta(days=1)


def add_business_days_after(start: date, n: int, specific: set, recurring: set) -> date:
    """Fecha del n-ésimo día hábil DESPUÉS de `start` (start NO cuenta, exclusivo).

    Ej. (regla de vencimiento de cotizaciones): emisión Lunes 01 + 15 días hábiles
    → Lunes 22 (se saltan sábados, domingos y feriados intermedios).
    """
    if n <= 0:
        return start
    counted = 0
    cur = start
    while counted < n:
        cur += timedelta(days=1)
        if is_business_day(cur, specific, recurring):
            counted += 1
    return cur


async def compute_expiry_date(start: date, n: int = 15) -> date:
    """Calcula la fecha de vencimiento = `start` + `n` días hábiles (exclusivo),
    excluyendo fines de semana y feriados de la BD."""
    specific, recurring = await get_holiday_sets()
    return add_business_days_after(start, n, specific, recurring)
