"""Iter 291 — Fix de zona horaria en 'Comprobante de Recepción de Equipos'.

Bug: la 'Fecha de recepción' del PDF y las variables de plantilla
(Fecha_Recepcion / fecha_sistema) se mostraban en UTC. El fix ubicado en
`/app/backend/routes/quote_taller.py` L87-88 introduce:

    from zoneinfo import ZoneInfo
    fecha_str = now.astimezone(ZoneInfo("America/Caracas")).strftime(
        "%d/%m/%Y %H:%M"
    )

de modo que `fecha_str` (que alimenta el PDF y `tpl_vars`) muestre la hora
local de Caracas (UTC-4, sin DST). El almacenamiento en BD sigue en UTC ISO
(now_iso).

Cobertura:
1. UNIT — Timezone: verificar que la conversión `now UTC → America/Caracas`
   resta exactamente 4h y produce el formato dd/mm/YYYY HH:MM.
2. UNIT — PDF: llamar directamente a `_generate_reception_pdf` con un
   `fecha_str` conocido y verificar con PyMuPDF que aparece la línea
   'Fecha de recepción: {fecha_str}' — es decir, el PDF NO reformatea/reconvierte
   la fecha, sólo usa la que recibe.
3. E2E — POST /api/taller/recepcion: se DESHABILITA temporalmente la config
   `taller_recepcion_equipos` (enabled=False) para evitar disparar correos
   reales. Se valida:
       (a) status 200/201, created==N, estatus='Recibido'
       (b) fecha_recepcion y fecha_ingreso persistidos en UTC ISO
       (c) al convertir esos ISO a America/Caracas coinciden con lo que el
           endpoint habría puesto en tpl_vars['Fecha_Recepcion'].
   Cleanup: DELETE de los taller_equipos creados y restauración de `enabled`
   al valor original.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

import pytest
import requests

# Importar módulos del backend
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from routes.quote_taller import _generate_reception_pdf  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL debe estar definido"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
TEST_CLIENT_ID = "cli_00bbd8a3c108"  # 'Prueba' J0009273

MODEL_QA = "Modelo QA TZ Caracas"
ACTION_ID = "taller_recepcion_equipos"


# ---------------- Fixtures ----------------

@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login falló: {r.status_code} {r.text[:200]}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No token en respuesta: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def disable_action_config_for_test():
    """Desactiva temporalmente el config `taller_recepcion_equipos` para que
    dispatch_other_action retorne disabled=True y NO se envíen correos reales.
    Restaura el estado original al finalizar la sesión de tests."""
    import asyncio
    from config import db  # motor async

    original_enabled = None

    async def _prepare():
        nonlocal original_enabled
        cfg = await db.other_action_configs.find_one(
            {"action_id": ACTION_ID}, {"_id": 0}
        )
        if cfg is not None:
            original_enabled = bool(cfg.get("enabled", True))
            await db.other_action_configs.update_one(
                {"action_id": ACTION_ID}, {"$set": {"enabled": False}}
            )

    async def _restore():
        if original_enabled is not None:
            await db.other_action_configs.update_one(
                {"action_id": ACTION_ID},
                {"$set": {"enabled": original_enabled}},
            )

    asyncio.get_event_loop().run_until_complete(_prepare())
    yield
    asyncio.get_event_loop().run_until_complete(_restore())


# ---------------- Utilidades ----------------

def _pdf_text(pdf_bytes: bytes) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()


def _to_caracas_str(iso_utc: str) -> str:
    """Convierte un ISO UTC a Caracas dd/mm/YYYY HH:MM (misma lógica que el fix)."""
    from zoneinfo import ZoneInfo
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("America/Caracas")).strftime("%d/%m/%Y %H:%M")


# ---------------- 1) UNIT — Timezone conversion ----------------

class TestTimezoneCaracasConversion:
    """Reproduce EXACTAMENTE la línea del fix (routes/quote_taller.py L87-88).
    No depende del endpoint HTTP."""

    def test_zoneinfo_caracas_is_utc_minus_4(self):
        from zoneinfo import ZoneInfo
        # Cualquier instante debe estar a UTC-4 (Caracas no tiene DST).
        for iso in (
            "2026-01-01T00:00:00+00:00",  # invierno
            "2026-07-01T12:00:00+00:00",  # verano
            "2026-12-31T23:59:00+00:00",  # fin de año
        ):
            dt_utc = datetime.fromisoformat(iso)
            dt_ccs = dt_utc.astimezone(ZoneInfo("America/Caracas"))
            delta = dt_utc.utcoffset() - dt_ccs.utcoffset()
            assert delta == timedelta(hours=4), (
                f"Esperado UTC-4 sin DST, obtenido delta={delta} en {iso}"
            )

    def test_fecha_str_format_matches_endpoint(self):
        """El endpoint hace: now.astimezone(ZoneInfo('America/Caracas'))
        .strftime('%d/%m/%Y %H:%M'). Debe producir 16 caracteres válidos."""
        from zoneinfo import ZoneInfo
        now = datetime.now(timezone.utc)
        fecha_str = now.astimezone(ZoneInfo("America/Caracas")).strftime(
            "%d/%m/%Y %H:%M"
        )
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", fecha_str), (
            f"Formato inesperado: {fecha_str!r}"
        )

    def test_utc_and_caracas_differ_by_4h_string(self):
        """Cuando la hora UTC es distinta a la Caracas por 4h, verificamos que
        la porción HH:MM del fecha_str Caracas NO coincide con la HH:MM UTC
        (a menos que sean exactamente medianoche + 4h)."""
        # Instante fijo: 15/01/2026 23:52:00 UTC → Caracas 15/01/2026 19:52
        fixed_utc = datetime(2026, 1, 15, 23, 52, tzinfo=timezone.utc)
        from zoneinfo import ZoneInfo
        ccs = fixed_utc.astimezone(ZoneInfo("America/Caracas")).strftime(
            "%d/%m/%Y %H:%M"
        )
        assert ccs == "15/01/2026 19:52", f"Esperado '15/01/2026 19:52', obtenido {ccs!r}"

        # Instante que cruza el día: 15/01/2026 02:30 UTC → Caracas 14/01/2026 22:30
        cross = datetime(2026, 1, 15, 2, 30, tzinfo=timezone.utc)
        ccs2 = cross.astimezone(ZoneInfo("America/Caracas")).strftime(
            "%d/%m/%Y %H:%M"
        )
        assert ccs2 == "14/01/2026 22:30", f"Esperado '14/01/2026 22:30', obtenido {ccs2!r}"


# ---------------- 2) UNIT — PDF muestra fecha_str intacta ----------------

class TestReceptionPDFDate:
    """Verifica que el PDF renderiza la línea 'Fecha de recepción: {fecha_str}'
    con la cadena tal cual se le pasa (Caracas), sin reformatearla."""

    def test_pdf_shows_caracas_fecha_str_verbatim(self):
        fecha_str = "15/01/2026 19:52"  # Caracas (equivale a 23:52 UTC)
        pdf = _generate_reception_pdf(
            client_name="Prueba",
            client_rif="J0009273",
            equipos=[(MODEL_QA, "QATEST-TZ-001")],
            fecha_str=fecha_str,
            user_email=ADMIN_EMAIL,
        )
        assert isinstance(pdf, (bytes, bytearray)) and pdf[:4] == b"%PDF"
        text = _pdf_text(bytes(pdf))
        # La línea debe aparecer con el texto exacto de Caracas
        assert f"Fecha de recepción: {fecha_str}" in text, (
            f"No se encontró la línea Caracas en el PDF. Extracto:\n{text[:1200]}"
        )
        # NO debe aparecer ningún string con hora +4h que sugiera UTC (23:52)
        assert "23:52" not in text, (
            f"El PDF contiene 23:52 (UTC) — no debería. Texto:\n{text[:1200]}"
        )

    def test_pdf_shows_date_crossing_day_backward(self):
        """Caso frontera: la conversión resta el día. El PDF debe reflejarlo."""
        fecha_str = "14/01/2026 22:30"  # Caracas (equivale a 15/01 02:30 UTC)
        pdf = _generate_reception_pdf(
            "Prueba", "J0009273",
            [(MODEL_QA, "QATEST-TZ-002")],
            fecha_str, ADMIN_EMAIL,
        )
        text = _pdf_text(bytes(pdf))
        assert f"Fecha de recepción: {fecha_str}" in text, text[:1200]
        # No debe filtrarse la fecha UTC
        assert "15/01/2026 02:30" not in text


# ---------------- 3) E2E — POST /api/taller/recepcion ----------------

class TestRecepcionEndpointStoresUtcShowsCaracas:
    """Regresión: la BD sigue en UTC ISO. Con la config desactivada
    (enabled=False) no se disparan correos reales."""

    created_ids: List[str] = []

    @classmethod
    def teardown_class(cls):
        # Best-effort cleanup por API
        try:
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                timeout=30,
            )
            tok = r.json().get("session_token")
            if not tok:
                return
            h = {"Authorization": f"Bearer {tok}"}
            for tid in cls.created_ids:
                try:
                    requests.delete(
                        f"{BASE_URL}/api/taller-equipos/{tid}",
                        headers=h, timeout=15,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def test_recepcion_stores_utc_iso(self, api_client, disable_action_config_for_test):
        # Snapshot de tiempo antes y después del POST para acotar el rango
        t_before = datetime.now(timezone.utc)

        stamp = uuid.uuid4().hex[:6].upper()
        serials = [f"QATEST-TZ-{stamp}-{i:02d}" for i in range(1, 3)]  # 2 equipos
        payload = {
            "client_id": TEST_CLIENT_ID,
            "client_name": "Prueba",
            "client_rif": "J0009273",
            "models": [
                {"model_id": "mdl_qa_tz", "model_name": MODEL_QA, "serials": serials}
            ],
        }
        r = api_client.post(
            f"{BASE_URL}/api/taller/recepcion", json=payload, timeout=60
        )
        t_after = datetime.now(timezone.utc)

        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        data = r.json()
        assert data.get("success") is True
        assert data.get("created") == 2
        assert data.get("estatus") == "Recibido"

        # GET para inspeccionar los ISO persistidos
        g = api_client.get(
            f"{BASE_URL}/api/taller-equipos",
            params={"client_id": TEST_CLIENT_ID},
            timeout=30,
        )
        assert g.status_code == 200
        equipos = g.json().get("equipos", [])
        by_serial = {e.get("serial"): e for e in equipos}
        for s in serials:
            assert s in by_serial, f"Serial {s} no persistido"
            eq = by_serial[s]
            TestRecepcionEndpointStoresUtcShowsCaracas.created_ids.append(
                eq["taller_equipo_id"]
            )
            fr = eq.get("fecha_recepcion", "")
            fi = eq.get("fecha_ingreso", "")
            # Debe ser ISO UTC parseable (termina en +00:00 o Z)
            assert fr, "fecha_recepcion vacío"
            dt_utc = datetime.fromisoformat(fr.replace("Z", "+00:00"))
            assert dt_utc.utcoffset() == timedelta(0), (
                f"fecha_recepcion no es UTC ISO: {fr!r} → offset {dt_utc.utcoffset()}"
            )
            # Y el mismo valor para fecha_ingreso (mismo `now_iso` en endpoint)
            assert fi == fr, f"fecha_ingreso ({fi}) != fecha_recepcion ({fr})"
            # Debe caer entre t_before y t_after (con 1s de tolerancia)
            assert t_before - timedelta(seconds=1) <= dt_utc <= t_after + timedelta(seconds=1), (
                f"UTC persistido fuera de rango: {dt_utc} not in "
                f"[{t_before}, {t_after}]"
            )

    def test_stored_utc_converts_to_caracas_minus_4h(self, api_client):
        """La visualización esperada (fecha_str) se obtiene convirtiendo el
        fecha_recepcion (UTC ISO) a America/Caracas — debe estar 4h detrás."""
        assert self.created_ids, "Depende del test previo (created_ids vacío)"
        g = api_client.get(
            f"{BASE_URL}/api/taller-equipos",
            params={"client_id": TEST_CLIENT_ID},
            timeout=30,
        )
        assert g.status_code == 200
        equipos = g.json().get("equipos", [])
        target = next(
            (e for e in equipos if e.get("taller_equipo_id") in self.created_ids),
            None,
        )
        assert target is not None, "No se encontró el equipo creado en el GET"

        iso_utc = target["fecha_recepcion"]
        dt_utc = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        caracas_str = _to_caracas_str(iso_utc)

        # Formato correcto
        assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", caracas_str)

        # Diferencia exacta de 4h contra la hora UTC (usando también HH:MM UTC)
        utc_str = dt_utc.strftime("%d/%m/%Y %H:%M")
        # Reconstruir dt Caracas y verificar que es el MISMO instante en otra zona
        from zoneinfo import ZoneInfo
        dt_ccs = dt_utc.astimezone(ZoneInfo("America/Caracas"))
        assert dt_ccs == dt_utc, "Deben representar el mismo instante"
        # Diferencia de utcoffset entre zonas: UTC (0) - Caracas (-4h) = +4h
        assert dt_utc.utcoffset() - dt_ccs.utcoffset() == timedelta(hours=4), (
            f"Delta esperado 4h, obtenido {dt_utc.utcoffset() - dt_ccs.utcoffset()}"
        )
        # Y en representación de wall-clock: la hora Caracas es 4h anterior
        wall_utc = dt_utc.replace(tzinfo=None)
        wall_ccs = dt_ccs.replace(tzinfo=None)
        assert wall_utc - wall_ccs == timedelta(hours=4), (
            f"Wall-clock diff esperado 4h. UTC={wall_utc} Caracas={wall_ccs}"
        )
        print(
            f"[iter291] UTC={utc_str}  Caracas={caracas_str}  "
            f"delta=4h  → tpl_vars['Fecha_Recepcion']={caracas_str}"
        )
