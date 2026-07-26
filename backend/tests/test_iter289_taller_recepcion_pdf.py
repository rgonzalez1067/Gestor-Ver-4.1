"""Iter 289 — Ajuste del PDF 'Comprobante de Recepción de Equipos'.

Objetivo del bug fix (main agent):
- El PDF ahora agrupa por modelo: una CABECERA por modelo (una sola vez) y
  debajo la lista de seriales con numeración GLOBAL. Antes se repetía el
  nombre del modelo por cada serial en una tabla plana y las descripciones
  largas se solapaban con la columna Serial.
- Los nombres de modelo largos deben envolverse (wrap) con simpleSplit, no
  solaparse.

Tests:
  1) Unit: llamar directamente a _generate_reception_pdf con una lista de
     (modelo, serial) donde:
       - "Morefun MP63" x 10 seriales
       - "PinPad Verifone P200 Engage Lector Smart Card y Pinpad con Software de Seguridad" x 14 seriales
     Extraer el texto con PyMuPDF (fitz) y validar:
       - "Morefun MP63" aparece EXACTAMENTE 1 vez (cabecera única).
       - La descripción larga del PinPad, tomada como una sub-cadena
         distintiva ("Software de Seguridad"), aparece a lo sumo 2 veces
         (por si hay wrap en dos líneas), y NUNCA 14 veces.
       - Los 24 seriales aparecen todos.
       - La cabecera "Equipos recibidos (24)" está presente.

  2) E2E: POST /api/taller/recepcion con dos modelos y varios seriales cada
     uno; verificar 201/200 con created==N, luego GET
     /api/taller-equipos?client_id=... y comprobar que los seriales creados
     por este test tienen estatus 'Recibido'. Cleanup: DELETE por cada
     taller_equipo_id creado.
"""

import os
import re
import sys
import uuid
from typing import List, Tuple

import pytest
import requests

# Aseguramos que se pueda importar el módulo del backend
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from routes.quote_taller import _generate_reception_pdf  # noqa: E402

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://perfilado-contactos.preview.emergentagent.com",
).rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
TEST_CLIENT_ID = "cli_00bbd8a3c108"  # 'Prueba' RIF J0009273

MODEL_SHORT = "Morefun MP63"
MODEL_LONG = (
    "PinPad Verifone P200 Engage Lector Smart Card y Pinpad con Software de Seguridad"
)


# ---------- Fixtures ----------

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
    assert tok, f"No session_token en respuesta: {r.text[:200]}"
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ---------- Utilidades ----------

def _pdf_text(pdf_bytes: bytes) -> str:
    """Extrae el texto completo del PDF con PyMuPDF."""
    import fitz  # PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()


def _build_pairs() -> Tuple[List[Tuple[str, str]], List[str], List[str]]:
    """10 seriales del modelo corto + 14 del largo (24 total)."""
    short_serials = [f"QATEST-MP63-{i:03d}" for i in range(1, 11)]
    long_serials = [f"QATEST-PIN-{i:03d}" for i in range(1, 15)]
    pairs: List[Tuple[str, str]] = []
    for s in short_serials:
        pairs.append((MODEL_SHORT, s))
    for s in long_serials:
        pairs.append((MODEL_LONG, s))
    return pairs, short_serials, long_serials


# ---------- 1) Unit test del PDF ----------

class TestReceptionPDFGrouping:
    """Valida el nuevo layout: cabecera por modelo (una vez) + seriales con
    numeración global; no repetición del nombre por cada serial."""

    def test_pdf_bytes_are_generated(self):
        pairs, _, _ = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            client_name="Prueba",
            client_rif="J0009273",
            equipos=pairs,
            fecha_str="20/01/2026 10:00",
            user_email=ADMIN_EMAIL,
        )
        assert isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 500
        assert pdf_bytes[:4] == b"%PDF", "El buffer no empieza con la firma %PDF"

    def test_short_model_name_appears_exactly_once(self):
        pairs, _, _ = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            "Prueba", "J0009273", pairs, "20/01/2026 10:00", ADMIN_EMAIL
        )
        text = _pdf_text(bytes(pdf_bytes))
        # Contamos ocurrencias exactas
        count = len(re.findall(re.escape(MODEL_SHORT), text))
        assert count == 1, (
            f"'Morefun MP63' debe aparecer 1 vez como cabecera, apareció {count} veces.\n"
            f"---TEXT---\n{text[:2000]}"
        )

    def test_long_model_name_not_repeated_per_serial(self):
        pairs, _, _ = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            "Prueba", "J0009273", pairs, "20/01/2026 10:00", ADMIN_EMAIL
        )
        text = _pdf_text(bytes(pdf_bytes))
        # Sub-cadena distintiva del modelo largo. Debe aparecer 1 vez (o a lo
        # sumo 2 si el wrap la parte, pero NUNCA 14 veces como antes).
        marker = "Software de Seguridad"
        count = len(re.findall(re.escape(marker), text))
        assert 1 <= count <= 2, (
            f"'{marker}' debe aparecer 1-2 veces (cabecera con posible wrap), "
            f"apareció {count} veces (indicaría repetición por serial).\n"
            f"---TEXT---\n{text[:2500]}"
        )
        # Además, la palabra 'PinPad' que abre el modelo largo tampoco debe
        # aparecer 14 veces.
        pinpad_count = len(re.findall(r"\bPinPad\b", text))
        assert pinpad_count <= 3, (
            f"'PinPad' aparece {pinpad_count} veces; indica repetición por serial. "
            f"Se esperaba <= 3 (una vez como cabecera, tal vez con wrap)."
        )

    def test_all_serials_present_with_global_numbering(self):
        pairs, short_serials, long_serials = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            "Prueba", "J0009273", pairs, "20/01/2026 10:00", ADMIN_EMAIL
        )
        text = _pdf_text(bytes(pdf_bytes))

        missing = [s for s in short_serials + long_serials if s not in text]
        assert not missing, f"Seriales faltantes en el PDF: {missing[:5]} ..."

        # Numeración global: debe haber marcadores "1.", "10.", "24."
        for n in (1, 10, 24):
            assert re.search(rf"(?<!\d){n}\.", text), (
                f"No se encontró la numeración global '{n}.' en el PDF.\n"
                f"---TEXT---\n{text[:2500]}"
            )

    def test_header_shows_total_count(self):
        pairs, _, _ = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            "Prueba", "J0009273", pairs, "20/01/2026 10:00", ADMIN_EMAIL
        )
        text = _pdf_text(bytes(pdf_bytes))
        assert "Equipos recibidos (24)" in text, (
            f"No se encontró 'Equipos recibidos (24)' en el PDF.\n---TEXT---\n{text[:1500]}"
        )

    def test_grouping_order_short_then_long(self):
        """La cabecera de 'Morefun MP63' debe aparecer ANTES que la del PinPad
        (preservación del orden de aparición del payload)."""
        pairs, _, _ = _build_pairs()
        pdf_bytes = _generate_reception_pdf(
            "Prueba", "J0009273", pairs, "20/01/2026 10:00", ADMIN_EMAIL
        )
        text = _pdf_text(bytes(pdf_bytes))
        idx_short = text.find(MODEL_SHORT)
        idx_long = text.find("PinPad Verifone")
        assert idx_short != -1 and idx_long != -1, "Faltan las cabeceras."
        assert idx_short < idx_long, (
            f"Se esperaba 'Morefun MP63' antes de 'PinPad Verifone'. "
            f"idx_short={idx_short}, idx_long={idx_long}"
        )


# ---------- 2) E2E POST /api/taller/recepcion ----------

class TestReceptionEndpoint:
    """Regresión: la recepción sigue creando registros con estatus 'Recibido'.
    Cleanup: elimina todos los taller_equipos creados en el test."""

    # Estado compartido para cleanup
    created_ids: List[str] = []
    created_serials: List[str] = []

    @classmethod
    def teardown_class(cls):
        # Borrar por API con admin
        try:
            r = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                timeout=30,
            )
            tok = r.json().get("session_token")
            if not tok:
                print("[cleanup] no token, skip")
                return
            headers = {"Authorization": f"Bearer {tok}"}
            for tid in cls.created_ids:
                try:
                    requests.delete(
                        f"{BASE_URL}/api/taller-equipos/{tid}",
                        headers=headers, timeout=15,
                    )
                except Exception as e:
                    print(f"[cleanup] error borrando {tid}: {e}")
            print(f"[cleanup] intentado borrar {len(cls.created_ids)} taller_equipos")
        except Exception as e:
            print(f"[cleanup] fallo global: {e}")

    def test_recepcion_creates_equipos_recibido(self, api_client):
        # Prefijo único para no colisionar con corridas anteriores
        stamp = uuid.uuid4().hex[:6].upper()
        short_serials = [f"QATEST-{stamp}-MP63-{i:02d}" for i in range(1, 4)]  # 3
        long_serials = [f"QATEST-{stamp}-PIN-{i:02d}" for i in range(1, 5)]     # 4
        payload = {
            "client_id": TEST_CLIENT_ID,
            "client_name": "Prueba",
            "client_rif": "J0009273",
            "models": [
                {"model_id": "mdl_qa_short", "model_name": MODEL_SHORT, "serials": short_serials},
                {"model_id": "mdl_qa_long", "model_name": MODEL_LONG, "serials": long_serials},
            ],
        }
        r = api_client.post(f"{BASE_URL}/api/taller/recepcion", json=payload, timeout=60)
        assert r.status_code in (200, 201), (
            f"POST /taller/recepcion falló: {r.status_code} {r.text[:400]}"
        )
        data = r.json()
        assert data.get("success") is True
        assert data.get("created") == 7, f"created esperado 7, obtenido {data.get('created')}"
        assert data.get("estatus") == "Recibido"

        TestReceptionEndpoint.created_serials.extend(short_serials + long_serials)

        # Verificar persistencia por GET
        g = api_client.get(
            f"{BASE_URL}/api/taller-equipos",
            params={"client_id": TEST_CLIENT_ID},
            timeout=30,
        )
        assert g.status_code == 200
        equipos = g.json().get("equipos", [])
        by_serial = {e.get("serial"): e for e in equipos}
        for s in short_serials + long_serials:
            assert s in by_serial, f"Serial {s} no persistido"
            assert by_serial[s].get("estatus") == "Recibido"
            TestReceptionEndpoint.created_ids.append(by_serial[s]["taller_equipo_id"])
        # Validar modelo persistido correctamente
        assert by_serial[short_serials[0]].get("modelo") == MODEL_SHORT
        assert by_serial[long_serials[0]].get("modelo") == MODEL_LONG

    def test_recepcion_empty_returns_400(self, api_client):
        payload = {
            "client_id": TEST_CLIENT_ID,
            "client_name": "Prueba",
            "client_rif": "J0009273",
            "models": [{"model_id": "x", "model_name": "X", "serials": []}],
        }
        r = api_client.post(f"{BASE_URL}/api/taller/recepcion", json=payload, timeout=30)
        assert r.status_code == 400, f"esperado 400, obtenido {r.status_code}: {r.text[:200]}"
