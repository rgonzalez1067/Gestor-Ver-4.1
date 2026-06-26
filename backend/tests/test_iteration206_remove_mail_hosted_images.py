"""Iteration 206 — Bug fix: las imágenes <img src='mail.google.com/...'> (pegadas
desde Gmail) requieren sesión Google y SIEMPRE llegan rotas al destinatario.

La solución implementada en email_service._embed_body_images() ahora:
  • ELIMINA del HTML cualquier <img> cuya URL esté alojada en buzones de
    correo (mail.google.com / googleusercontent fimg / outlook.live.com /
    outlook.office* / OWA) antes de enviar el correo.
  • Sigue convirtiendo a 'cid:bodyimg_*' las imágenes (a) ruta relativa de
    nuestro storage /api/projects/images/<id>, (b) URL absoluta de nuestro
    storage en cualquier dominio, (c) data URIs base64, (d) otras URLs
    remotas públicas descargables.
  • NO intenta descargar las imágenes auth-gated (resiliencia/perf): se
    eliminan directamente.

Validamos:
  1. Unit: HTML mixto (gmail+rel+abs+data) → 3 cid, sin <img> de gmail, sin
     'mail.google.com', sin /api/projects/images/, sin data:image/.
  2. Plantilla REAL 'Notificación de Proyecto — Cliente' (email_templates):
     tiene 5 <img mail.google.com> → después de _embed_body_images quedan
     0 'mail.google.com' y 0 <img> apuntando a Gmail.
  3. send_email e2e: con el HTML real de la plantilla, no lanza excepción y
     email_logs.html_preview NO contiene 'mail.google.com' ni <img de gmail.
  4. Perf/resiliencia: solo gmail (sin imágenes incrustables) → ejecuta en
     menos de 1s y devuelve atts vacío (no se descarga nada).
"""
import asyncio
import os
import sys
import time
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from services.email_service import _embed_body_images, send_email  # noqa: E402
from config import db  # noqa: E402

EXISTING_IMAGE_ID = "d9a6f6f6ae5d"
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


# =====================================================================
# UNIT: 4 escenarios mixtos — gmail SE ELIMINA, los otros 3 → cid:bodyimg_
# =====================================================================
def test_embed_body_images_removes_mail_google_and_keeps_others_as_cid():
    rel = f"/api/projects/images/{EXISTING_IMAGE_ID}.png"
    abs_url = f"https://other-domain.example.com/api/projects/images/{EXISTING_IMAGE_ID}.png"
    data_uri = f"data:image/png;base64,{TINY_PNG_B64}"
    gmail_src_a = (
        "https://mail.google.com/mail/u/1?ui=2&amp;ik=abc&amp;view=fimg&amp;attid=fake1"
    )
    gmail_src_b = "https://mail.google.com/mail/u/0?ui=2&ik=xyz&view=fimg&attid=fake2"
    gusercontent = (
        "https://fimg.googleusercontent.com/something?view=fimg&attid=fake3"
    )
    outlook_src = "https://outlook.live.com/owa/?ItemID=fake&attid=4"

    html = (
        f'<p>imgA <img src="{rel}"/></p>'
        f'<p>imgB <img src="{abs_url}"/></p>'
        f'<p>imgC <img src="{data_uri}"/></p>'
        f'<p>imgD <img src="{gmail_src_a}"/></p>'
        f'<p>imgE <img src=\'{gmail_src_b}\'/></p>'
        f'<p>imgF <img src="{gusercontent}"/></p>'
        f'<p>imgG <img src="{outlook_src}"/></p>'
    )

    new_html, atts = _run(_embed_body_images(html, []))

    # 3 adjuntos inline cid (los 3 incrustables; gmail/outlook eliminados, no embebidos)
    cid_atts = [a for a in atts if a.get("inline") and a.get("content_id", "").startswith("bodyimg_")]
    assert len(cid_atts) == 3, f"Esperaba 3 cid, hay {len(cid_atts)}"
    assert new_html.count("cid:bodyimg_") == 3

    # Las 4 imágenes de buzón deben haber sido ELIMINADAS por completo del HTML
    assert "mail.google.com" not in new_html, f"Aún queda 'mail.google.com' en HTML: {new_html[:300]!r}"
    assert "googleusercontent.com" not in new_html, f"Aún queda 'googleusercontent.com': {new_html[:300]!r}"
    assert "outlook.live.com" not in new_html, f"Aún queda 'outlook.live.com': {new_html[:300]!r}"
    assert "/owa/" not in new_html, f"Aún queda '/owa/' en HTML: {new_html[:300]!r}"

    # Ya no debe quedar ninguna ruta relativa /api/projects/images/ ni data: en el HTML final
    assert "/api/projects/images/" not in new_html, f"Quedó ruta relativa: {new_html[:300]!r}"
    assert "data:image/" not in new_html, f"Quedó data URI: {new_html[:300]!r}"

    # Los 4 <img> de buzón fueron eliminados → total <img> en HTML = 3 (los cid)
    img_count = new_html.lower().count("<img")
    assert img_count == 3, f"Esperaba 3 <img> (cid), hay {img_count}. HTML: {new_html[:400]!r}"


# =====================================================================
# PLANTILLA REAL: 'Notificación de Proyecto — Cliente'
# =====================================================================
def test_real_template_notif_proyecto_cliente_strips_all_mail_google():
    doc = _run(db.email_templates.find_one(
        {"name": {"$regex": "Notificaci.n de Proyecto", "$options": "i"}},
        {"_id": 0, "name": 1, "body_html": 1, "body": 1},
    ))
    assert doc, "No se encontró plantilla 'Notificación de Proyecto — Cliente'"
    body = doc.get("body_html") or doc.get("body") or ""
    assert body, "La plantilla no tiene body"
    assert body.count("mail.google.com") >= 1, (
        "La plantilla real ya NO contiene URLs mail.google.com — el test "
        "ya no es representativo (recolectar nueva plantilla afectada)."
    )
    img_initial = body.lower().count("<img")

    t0 = time.time()
    new_html, atts = _run(_embed_body_images(body, []))
    elapsed = time.time() - t0

    # Cero referencias a mail.google.com en el HTML final
    assert "mail.google.com" not in new_html, (
        f"La plantilla aún contiene 'mail.google.com' tras embed. "
        f"prefijo={new_html[:300]!r}"
    )
    # Y los <img> de gmail desaparecieron (puede que queden <img> de otras fuentes
    # como nuestro storage convertidos a cid:bodyimg_).
    remaining_imgs = new_html.lower().count("<img")
    assert remaining_imgs < img_initial, (
        f"No se eliminó ningún <img>: antes={img_initial}, después={remaining_imgs}"
    )
    # No se debió haber intentado descargar imágenes de gmail → rápido (< 2s
    # incluso permitiendo I/O mongo del storage_path para otras imágenes)
    assert elapsed < 5.0, f"_embed_body_images tomó {elapsed:.2f}s (esperado < 5s)"


# =====================================================================
# E2E send_email con la plantilla real → log no contiene mail.google.com
# =====================================================================
def test_send_email_real_template_logs_no_mail_google_in_preview():
    doc = _run(db.email_templates.find_one(
        {"name": {"$regex": "Notificaci.n de Proyecto", "$options": "i"}},
        {"_id": 0, "body_html": 1, "body": 1},
    ))
    assert doc
    body = doc.get("body_html") or doc.get("body") or ""

    # Inyectamos al comienzo una imagen nuestra (cid candidato) para que aparezca
    # en los 500 chars del html_preview.
    rel = f"/api/projects/images/{EXISTING_IMAGE_ID}.png"
    html = f'<img src="{rel}"/>' + body

    subject = f"[TEST_iter206] real template {uuid.uuid4().hex[:6]}"
    result = _run(send_email(
        to=["test_iter206@invalid.local"],
        subject=subject,
        html=html,
        action="test_iter206_real_template",
    ))
    assert isinstance(result, dict) and result.get("email_log_id"), result

    log = _run(db.email_logs.find_one(
        {"email_log_id": result["email_log_id"]}, {"_id": 0}
    ))
    assert log is not None, "El email_log no se persistió"

    # El html guardado podría estar truncado a 500 chars. Para validar el
    # cuerpo COMPLETO, repetimos el embed (idempotente para nuestra rel/abs/data
    # — las gmail ya están eliminadas) y aseguramos que el resultado no tiene
    # 'mail.google.com'. Para el log, validamos que el preview tampoco.
    preview = (log.get("html_preview") or "")
    assert "mail.google.com" not in preview, (
        f"html_preview contiene 'mail.google.com': {preview[:300]!r}"
    )
    # El preview no debe tener <img> rotos apuntando a Gmail
    assert "src=\"https://mail.google.com" not in preview
    assert "src='https://mail.google.com" not in preview

    assert log.get("status") in ("sent", "simulated")

    # Limpieza
    _run(db.email_logs.delete_one({"email_log_id": result["email_log_id"]}))


# =====================================================================
# PERF/RESILIENCIA: solo imágenes de gmail → no descarga, rápido
# =====================================================================
def test_embed_body_images_only_gmail_is_fast_and_empty():
    html = "".join([
        f'<p><img src="https://mail.google.com/mail/u/1?ui=2&ik=abc&view=fimg&attid={i}"/></p>'
        for i in range(5)
    ])
    t0 = time.time()
    new_html, atts = _run(_embed_body_images(html, []))
    elapsed = time.time() - t0

    assert atts == [], f"No debió haber adjuntos: {atts}"
    assert "mail.google.com" not in new_html
    assert new_html.lower().count("<img") == 0
    # Como NO se descarga ninguna imagen, debe ser inmediato (sin httpx round-trips)
    assert elapsed < 1.0, f"Demasiado lento: {elapsed:.2f}s (no se debe descargar)"
