"""Iteration 205 — Bug fix: imágenes del cuerpo de correo deben llegar embebidas
como Content-ID (cid:) inline para clientes Gmail/Outlook.

Verifica que el backend, antes de despachar el correo, convierte:
  (a) ruta relativa  /api/projects/images/<id>.png
  (b) URL absoluta   https://<host>/api/projects/images/<id>.png  (incluso otro dominio)
  (c) data URI       data:image/png;base64,...

... a referencias 'cid:bodyimg_XXXX' con sus respectivos adjuntos inline.
Adicionalmente, una imagen con src autenticado de Gmail (mail.google.com/...)
NO debe romper el envío; el correo se envía sin esa imagen embebida.
"""
import asyncio
import base64
import os
import sys
import uuid

import pytest
from dotenv import load_dotenv

# Cargar .env del backend antes de importar config
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from services.email_service import _embed_body_images, send_email  # noqa: E402
from config import db  # noqa: E402

# image_id real existente en uploaded_images (confirmado por consulta directa).
EXISTING_IMAGE_ID = "d9a6f6f6ae5d"

# 1x1 PNG transparente (válido para data URI test).
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    """Ejecuta coroutine en el loop compartido del módulo. Necesario porque
    motor enlaza su pool de IO al loop activo al primer await; crear un loop
    nuevo por test rompe la conexión a Mongo (Event loop is closed)."""
    return _LOOP.run_until_complete(coro)


# ============================================================
# UNIT: _embed_body_images con los 4 escenarios en un mismo HTML
# ============================================================
def test_embed_body_images_unit_relative_absolute_datauri_and_gmail():
    """Las 3 imágenes incrustables → cid:bodyimg_*; el src de mail.google.com
    no rompe pero queda sin embebido (no se descarga)."""
    base_url = (os.environ.get("REACT_APP_BACKEND_URL", "") or "").rstrip("/")
    assert base_url, "REACT_APP_BACKEND_URL debe estar configurado"

    rel = f"/api/projects/images/{EXISTING_IMAGE_ID}.png"
    # Dominio distinto a propósito (validar que se sirve por storage_path, no por URL)
    abs_url = f"https://other-domain.example.com/api/projects/images/{EXISTING_IMAGE_ID}.png"
    data_uri = f"data:image/png;base64,{TINY_PNG_B64}"
    gmail_src = (
        "https://mail.google.com/mail/u/1?ui=2&view=fimg&attid=fake&fakeparam=1"
    )

    html = (
        f'<p>img1 <img src="{rel}"/></p>'
        f'<p>img2 <img src="{abs_url}"/></p>'
        f'<p>img3 <img src="{data_uri}"/></p>'
        f'<p>img4 <img src="{gmail_src}"/></p>'
    )

    new_html, atts = _run(_embed_body_images(html, []))

    # Deben crearse 3 adjuntos inline cid (no se cuenta el de gmail.com)
    cid_atts = [a for a in atts if a.get("inline") and a.get("content_id", "").startswith("bodyimg_")]
    assert len(cid_atts) == 3, f"Se esperaban 3 adjuntos inline cid, hay {len(cid_atts)}"

    # Los 3 src originales (rel/abs/data) no deben quedar en el HTML resultante.
    assert rel not in new_html, "La ruta relativa NO fue reemplazada por cid"
    assert abs_url not in new_html, "La URL absoluta NO fue reemplazada por cid"
    assert data_uri not in new_html, "El data URI NO fue reemplazado por cid"

    # Y el HTML debe contener al menos 3 referencias cid:bodyimg_
    assert new_html.count("cid:bodyimg_") == 3

    # El src de gmail debe permanecer intacto (no se rompe el envío)
    assert gmail_src in new_html

    # Los content_id de las 3 imágenes embebidas deben ser únicos
    cids = {a["content_id"] for a in cid_atts}
    assert len(cids) == 3


# ============================================================
# INTEGRACIÓN: send_email persiste html_preview con 'cid:bodyimg_'
# ============================================================
def test_send_email_persists_cid_in_email_logs():
    """End-to-end: invocar send_email con las 3 imágenes incrustables al principio
    del HTML (para que entren en los primeros 500 chars del html_preview) y
    verificar que email_logs.html_preview contiene 'cid:bodyimg_'."""
    rel = f"/api/projects/images/{EXISTING_IMAGE_ID}.png"
    abs_url = f"https://other-domain.example.com/api/projects/images/{EXISTING_IMAGE_ID}.png"
    data_uri = f"data:image/png;base64,{TINY_PNG_B64}"
    gmail_src = "https://mail.google.com/mail/u/1?ui=2&view=fimg&attid=fake"

    # Imagenes al inicio para asegurar que el truncado a 500 chars las incluya.
    html = (
        f'<img src="{rel}"/>'
        f'<img src="{abs_url}"/>'
        f'<img src="{data_uri}"/>'
        f'<img src="{gmail_src}"/>'
        f"<p>Prueba CID iter205</p>"
    )

    subject = f"[TEST_iter205] CID body images {uuid.uuid4().hex[:6]}"
    # Recipient ficticio que no es deliverable (no debe afectar el log).
    result = _run(send_email(
        to=["test_iter205@invalid.local"],
        subject=subject,
        html=html,
        action="test_iter205_cid",
    ))

    assert isinstance(result, dict) and result.get("email_log_id"), result

    # Buscar el log persistido y validar html_preview
    log = _run(db.email_logs.find_one(
        {"email_log_id": result["email_log_id"]}, {"_id": 0}
    ))
    assert log is not None, "El email_log no se persistió"

    preview = log.get("html_preview", "") or ""
    assert "cid:bodyimg_" in preview, (
        f"html_preview NO contiene 'cid:bodyimg_'. preview={preview[:300]!r}"
    )

    # No deben quedar rutas relativas /api/projects/images/ ni data:image/ en el preview.
    # (Si quedaran, llegarían rotas al cliente.)
    assert "/api/projects/images/" not in preview, (
        f"Aún quedan rutas /api/projects/images/ en html_preview: {preview[:300]!r}"
    )
    assert "data:image/" not in preview, (
        f"Aún quedan data URIs en html_preview: {preview[:300]!r}"
    )

    # El src de mail.google.com NO se incrusta — su URL puede aparecer en el body,
    # pero el log de preview solo guarda 500 chars; aceptamos que sí aparezca (no rompe).
    # Lo crítico es que el envío NO haya lanzado excepción y se haya persistido el log.
    assert log.get("status") in ("sent", "simulated"), log.get("status")

    # has_attachment debe ser True porque embebimos 3 imágenes
    assert log.get("has_attachment") is True

    # Limpieza
    _run(db.email_logs.delete_one({"email_log_id": result["email_log_id"]}))


# ============================================================
# RESILIENCIA: solo gmail.com → no rompe, no embebe
# ============================================================
def test_embed_body_images_gmail_only_does_not_raise():
    """Imagen con src autenticado de Gmail no debe lanzar excepción; el HTML queda
    sin cambios significativos (no se crea cid)."""
    gmail_src = "https://mail.google.com/mail/u/1?ui=2&view=fimg&attid=fake"
    html = f'<p>solo gmail <img src="{gmail_src}"/></p>'
    new_html, atts = _run(_embed_body_images(html, []))
    cid_atts = [a for a in atts if a.get("inline") and a.get("content_id", "").startswith("bodyimg_")]
    assert len(cid_atts) == 0
    assert gmail_src in new_html



# ============================================================
# INTEGRACIÓN HTTP: /api/projects/upload-image devuelve URL ABSOLUTA
# que contiene '/api/projects/images/' (lo que el editor incrusta).
# ============================================================
def test_upload_image_returns_absolute_url():
    import io
    import requests

    base_url = (os.environ.get("REACT_APP_BACKEND_URL", "") or "").rstrip("/")
    assert base_url, "REACT_APP_BACKEND_URL debe estar configurado"

    # Login admin
    r = requests.post(
        f"{base_url}/api/auth/login",
        json={"email": "rgonzalez@megasoft.com.ve", "password": "admin123"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    token = r.json().get("session_token") or r.json().get("token")
    assert token, r.json()

    # PNG 1x1 transparente
    png_bytes = base64.b64decode(TINY_PNG_B64)
    files = {"file": ("test_iter205.png", io.BytesIO(png_bytes), "image/png")}
    r2 = requests.post(
        f"{base_url}/api/projects/upload-image",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    url = data.get("url", "")
    # Debe ser ABSOLUTA (http/https) y contener '/api/projects/images/'
    assert url.startswith("http://") or url.startswith("https://"), f"URL no absoluta: {url}"
    assert "/api/projects/images/" in url, f"URL no contiene path esperado: {url}"
    assert base_url in url, f"URL no usa el dominio configurado: {url}"

    # Y debe servirse PÚBLICAMENTE (sin auth) y devolver una imagen.
    r3 = requests.get(url, timeout=15)
    assert r3.status_code == 200, f"serve_image fallo: {r3.status_code} {r3.text[:200]}"
    assert r3.headers.get("content-type", "").startswith("image/"), r3.headers
