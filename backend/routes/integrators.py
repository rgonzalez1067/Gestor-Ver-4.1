"""Route module: integrators.py"""
# ruff: noqa: F403, F405
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os
import re

from config import db, get_current_user, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template
from models import *
import shutil
import csv

logger = logging.getLogger("integrators")
import base64

router = APIRouter()

# ============================================================
# Lista maestra de 19 productos de Integradores (M-AE en plantilla).
# Hardcoded (NO usa db.services para no acoplar con Medios de Pago).
# ============================================================
INTEGRATOR_PRODUCTS = [
    {"id": "prod_tdd_tdc",                      "name": "TDD/TDC"},
    {"id": "prod_tdc_tdd_excepto_maestro",      "name": "TDC/TDD (excepto maestro)"},
    {"id": "prod_verificacion_p2c",             "name": "Verificación P2C"},
    {"id": "prod_c2p",                          "name": "C2P"},
    {"id": "prod_cryptobuyer_criptomoneda",     "name": "Cryptobuyer/Criptomoneda"},
    {"id": "prod_biopago",                      "name": "Biopago"},
    {"id": "prod_cambio_p2c",                   "name": "Cambio P2C"},
    {"id": "prod_verificacion_pago_zelle",      "name": "Verificación Pago Zelle"},
    {"id": "prod_credito_inm_verif_transf",     "name": "Credito Inmediato/Verificación Transferencia"},
    {"id": "prod_debito_inmediato",             "name": "Debito Inmediato"},
    {"id": "prod_cambio_credito_inm_transf",    "name": "Cambio Credito Inmediato / Cambio Transferencia"},
    {"id": "prod_deposito_verif_deposito",      "name": "Deposito/Verificación Depósito"},
    {"id": "prod_cambio_cards",                 "name": "Cambio Cards"},
    {"id": "prod_consulta_cards",               "name": "Consulta Cards"},
    {"id": "prod_cambio_de_pin",                "name": "Cambio de Pin"},
    {"id": "prod_banplus_pay",                  "name": "Banplus Pay"},
    {"id": "prod_cashea",                       "name": "CASHEA"},
    {"id": "prod_xcapit",                       "name": "Xcapit"},
    {"id": "prod_crixto",                       "name": "Crixto"},
    {"id": "prod_lysto",                        "name": "Lysto"},
]
INTEGRATOR_PRODUCT_IDS = [p["id"] for p in INTEGRATOR_PRODUCTS]
INTEGRATOR_PRODUCT_NAME_TO_ID = {p["name"].lower().strip(): p["id"] for p in INTEGRATOR_PRODUCTS}


async def migrate_integrator_certifications_if_needed():
    """One-shot: resetea las certifications de todos los integradores a N/A con las
    nuevas keys (drop & reset). Idempotente mediante flag en `_migrations`."""
    flag = await db["_migrations"].find_one({"_id": "integrator_cert_reset_v1"})
    if flag:
        return 0
    default_certs = {pid: "N/A" for pid in INTEGRATOR_PRODUCT_IDS}
    result = await db.integrators.update_many({}, {"$set": {"certifications": default_certs}})
    await db["_migrations"].insert_one({
        "_id": "integrator_cert_reset_v1",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "affected": result.modified_count,
    })
    return result.modified_count


# ==================== INTEGRATORS ENDPOINTS ====================


@router.get("/integrators/products")
async def list_integrator_products(authorization: Optional[str] = Header(None)):
    """Devuelve la lista maestra de 19 productos de Integradores (iter 183d).
    Formato compatible con el consumidor legacy (`service_id`/`name`/flags) para
    que el frontend lo use como drop-in replacement de `/services`."""
    await get_current_user(authorization)
    return [
        {
            "service_id": p["id"],
            "name": p["name"],
            "service_type": "Producto",
            "application_type": "setup",
            "order": idx,
        }
        for idx, p in enumerate(INTEGRATOR_PRODUCTS)
    ]


@router.get("/integrators", response_model=List[Integrator])
async def get_integrators(
    authorization: Optional[str] = Header(None),
    integrator_status: Optional[str] = None,
    integrator_type: Optional[str] = None,
    show_all: bool = False,
):
    await get_current_user(authorization)
    
    query = {}
    if integrator_status:
        query['integrator_status'] = integrator_status
    elif not show_all:
        # Vista por defecto: solo proyectos activos (oculta los Cerrados).
        query['integrator_status'] = {"$ne": "Cerrado"}
    if integrator_type:
        query['integrator_type'] = integrator_type
    
    integrators = await db.integrators.find(query, {"_id": 0}).to_list(1000)
    
    # Check for overdue commitments per integrator
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    integrator_ids = [i['integrator_id'] for i in integrators]
    overdue_map = {}
    if integrator_ids:
        overdue_entries = await db.bitacora.find({
            "integrator_id": {"$in": integrator_ids},
            "commitment_completed": False,
            "commitment_deadline": {"$lt": today, "$nin": [None, ""]}
        }, {"_id": 0, "integrator_id": 1}).to_list(1000)
        for e in overdue_entries:
            overdue_map[e['integrator_id']] = True
    
    for intg in integrators:
        if isinstance(intg.get('created_at'), str):
            intg['created_at'] = datetime.fromisoformat(intg['created_at'])
        intg['has_overdue_commitments'] = overdue_map.get(intg['integrator_id'], False)

    # Contador de días hábiles restantes para "Asignación de Ambiente de Prueba".
    test_envs = [i for i in integrators if i.get('project_scope') == 'test_environment' and i.get('test_env_end_date')]
    if test_envs:
        from services.business_calendar import get_holiday_sets, business_days_between
        from datetime import date as _date
        _specific, _recurring = await get_holiday_sets()
        _today = _date.today()
        for intg in test_envs:
            try:
                _end = datetime.strptime(intg['test_env_end_date'][:10], "%Y-%m-%d").date()
                intg['test_env_days_left'] = business_days_between(_today, _end, _specific, _recurring)
            except Exception as _e:
                intg['test_env_days_left'] = None
    return integrators

@router.post("/integrators", response_model=Integrator)
async def create_integrator(integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)

    new_integrator = Integrator(**integrator.model_dump())
    doc = new_integrator.model_dump()

    # ===== Clasificación automática del Proyecto de Integración =====
    # Compara contra los registros existentes del mismo Integrador (por nombre):
    #  - Sin registros previos        -> "new"       (Proyecto Nuevo / Azul)
    #  - Existe pero tipo NUEVO        -> "component" (Nuevo Componente / Verde)
    #  - Existe y tipo YA presente     -> "expansion" (Proyecto Ampliado / Naranja)
    norm_name = (doc.get("name") or "").strip().lower()
    new_type = (doc.get("integration_type") or "").strip().upper()
    same_name_rows = []
    if norm_name:
        async for r in db.integrators.find(
            {"name": {"$regex": f"^{re.escape(doc.get('name','').strip())}$", "$options": "i"}},
            {"_id": 0, "integration_type": 1, "contacts": 1, "integrator_id": 1},
        ):
            same_name_rows.append(r)

    if not same_name_rows:
        scope = "new"
    else:
        existing_types = {(r.get("integration_type") or "").strip().upper() for r in same_name_rows}
        scope = "expansion" if new_type and new_type in existing_types else "component"
    doc["project_scope"] = scope

    # Matriz de Productos: en "new" y "component" TODOS los productos nacen "P"
    # (Pendiente). En "expansion" se respeta lo enviado o se inicializa N/A.
    if scope in ("new", "component"):
        doc["certifications"] = {pid: "P" for pid in INTEGRATOR_PRODUCT_IDS}
    elif not doc.get("certifications"):
        doc["certifications"] = {pid: "N/A" for pid in INTEGRATOR_PRODUCT_IDS}

    # Propagar el contacto capturado al maestro: se suma a la lista de contactos
    # de todos los registros del mismo Integrador (dedupe por email).
    incoming_contacts = doc.get("contacts") or []
    if incoming_contacts and same_name_rows:
        for row in same_name_rows:
            merged = list(row.get("contacts") or [])
            existing_emails = {(c.get("email") or "").strip().lower() for c in merged}
            for c in incoming_contacts:
                if (c.get("email") or "").strip().lower() not in existing_emails:
                    merged.append(c)
            await db.integrators.update_one(
                {"integrator_id": row["integrator_id"]}, {"$set": {"contacts": merged}}
            )

    # Automatización: el usuario que da de alta queda como "Gestor del Proyecto".
    if current_user and not doc.get('gestor_user_id'):
        creator_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get('email', '')
        doc['gestor'] = creator_name
        doc['gestor_user_id'] = current_user.get('user_id')
        doc['assigned_at'] = datetime.now(timezone.utc).isoformat()
        doc['assigned_by'] = current_user.get('user_id')

    doc['created_at'] = doc['created_at'].isoformat()
    await db.integrators.insert_one(doc)
    doc.pop('_id', None)
    return doc


@router.get("/integrators/summary")
async def get_integrations_summary(group_by: str = "phase", authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    service_map = {p['id']: p['name'] for p in INTEGRATOR_PRODUCTS}
    groups = {}
    if group_by == "phase":
        for intg in integrators:
            key = intg.get('integration_phase') or 'Sin fase'
            groups.setdefault(key, {"label": key, "count": 0, "items": []})
            groups[key]["count"] += 1
            groups[key]["items"].append({"integrator_id": intg['integrator_id'], "name": intg['name'], "app_name": intg.get('app_name', ''), "integration_modality": intg.get('integration_modality', ''), "integrator_status": intg.get('integrator_status', ''), "integration_phase": intg.get('integration_phase', ''), "gestor": intg.get('gestor', '')})
    elif group_by == "product":
        for intg in integrators:
            for sid, status in (intg.get('certifications') or {}).items():
                if status in ('C', 'P'):
                    pname = service_map.get(sid, sid)
                    groups.setdefault(pname, {"label": pname, "count": 0, "certified": 0, "pending": 0, "items": []})
                    groups[pname]["count"] += 1
                    groups[pname]["certified" if status == 'C' else "pending"] += 1
                    groups[pname]["items"].append({"integrator_id": intg['integrator_id'], "name": intg['name'], "status": status, "integration_phase": intg.get('integration_phase', '')})
    elif group_by == "modality":
        for intg in integrators:
            key = intg.get('integration_modality') or 'Sin modalidad'
            groups.setdefault(key, {"label": key, "count": 0, "items": []})
            groups[key]["count"] += 1
            groups[key]["items"].append({"integrator_id": intg['integrator_id'], "name": intg['name'], "app_name": intg.get('app_name', ''), "integrator_status": intg.get('integrator_status', ''), "integration_phase": intg.get('integration_phase', '')})
    return {"group_by": group_by, "total": len(integrators), "groups": groups}



@router.get("/integrators/dropdown")
async def get_integrators_dropdown(authorization: Optional[str] = Header(None)):
    """Retorna lista ligera de integradores para dropdowns con sus aplicativos."""
    await get_current_user(authorization)
    integrators = await db.integrators.find({}, {"_id": 0, "integrator_id": 1, "name": 1, "app_name": 1}).to_list(1000)
    return [{"integrator_id": i["integrator_id"], "name": i["name"], "app_name": i.get("app_name", "")} for i in integrators]


@router.get("/integrators/coordinators")
async def list_implementation_coordinators(authorization: Optional[str] = Header(None)):
    """Usuarios con cargo 'Coordinador' del departamento 'Implementación' (activos).
    Alimenta el dropdown dinámico 'Coordinador' de la ficha de integrador. Solo
    estos perfiles deben poder asignarse como Coordinador del proyecto."""
    await get_current_user(authorization)
    cur = db.users.find(
        {"is_active": True, "cargo": "Coordinador", "departamento": "Implementación"},
        {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1},
    )
    out = []
    async for u in cur:
        name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        out.append({"user_id": u.get("user_id"), "name": name or u.get("email", ""), "email": u.get("email", "")})
    out.sort(key=lambda x: (x["name"] or "").lower())
    return out




@router.get("/integrators/{integrator_id}", response_model=Integrator)
async def get_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return integrator

@router.put("/integrators/{integrator_id}", response_model=Integrator)
async def update_integrator(integrator_id: str, integrator: IntegratorCreate, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    
    update_data = integrator.model_dump()
    # BLINDAJE DEL CICLO DE VIDA DEL PROYECTO:
    # La edición de la ficha NUNCA debe alterar el estatus del proyecto ni su
    # clasificación de alcance. El cierre ocurre EXCLUSIVAMENTE por el botón
    # "Cerrar Proyecto" (endpoint /close). Preservamos siempre estos campos.
    update_data["project_scope"] = existing.get("project_scope")
    update_data.pop("closed_at", None)
    update_data.pop("closed_by", None)
    incoming_status = update_data.get("integrator_status")
    if existing.get("integrator_status") == "Cerrado" or incoming_status == "Cerrado":
        # Ni se cierra por edición, ni se reactiva un proyecto ya cerrado editando la ficha.
        update_data["integrator_status"] = existing.get("integrator_status")
    # RESTRICCIÓN DE SEGURIDAD — MATRIZ DE PRODUCTOS SOLO-LECTURA:
    # No se permite modificar la matriz de certificaciones si el integrador NO está
    # en fase de Proyecto Activo (scope clasificado y estatus != Cerrado).
    incoming_certs = update_data.get("certifications")
    if incoming_certs is not None and incoming_certs != (existing.get("certifications") or {}):
        _scope = existing.get("project_scope")
        _is_active = _scope in ("new", "component", "expansion", "test_environment") and existing.get("integrator_status") != "Cerrado"
        if not _is_active:
            raise HTTPException(status_code=403, detail="La Matriz de Productos es de solo lectura: el integrador no se encuentra en fase de Proyecto Activo.")
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": update_data}
    )
    
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return updated


def _certified_products_names(intg: dict) -> list:
    """Lista de nombres de Medios de Pago / Productos con certificación 'C' (Certificado),
    en el orden de la lista maestra. (Regla del Valor 'C')."""
    certs = intg.get("certifications") or {}
    return [p["name"] for p in INTEGRATOR_PRODUCTS if str(certs.get(p["id"], "")).strip().upper() == "C"]


def _certified_products_string(intg: dict) -> str:
    """Nombres de los Medios/Productos certificados unidos por ' / '."""
    return " / ".join(_certified_products_names(intg))


def _certified_products_bullets_html(intg: dict) -> str:
    """Lista enumerada con viñetas (HTML) de los Medios/Productos certificados,
    para la variable {Medios_Certificados} de la plantilla de Cierre."""
    names = _certified_products_names(intg)
    if not names:
        return ""
    items = "".join(f'<li style="margin:3px 0;">{n}</li>' for n in names)
    return f'<ul style="margin:8px 0 8px 20px; padding:0; list-style-type:disc;">{items}</ul>'


def _wrap_text_lines(text: str, font: str, size: float, max_width: float) -> list:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = (text or "").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if stringWidth(test, font, size) <= max_width or not cur:
            cur = test
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _build_standalone_certificate_pdf(intg: dict, componente: str, version: str, productos_str: str) -> bytes:
    """Construye un Certificado de Integración corporativo COMPLETO desde cero
    (sin depender de un PDF base en el depósito). Garantiza que siempre exista un
    certificado que adjuntar al cierre del proyecto."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader

    name = intg.get("name", "")
    app_name = intg.get("app_name", "")
    fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    W, H = landscape(A4)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    cx = W / 2

    # Marco corporativo (doble borde)
    c.setStrokeColorRGB(0.12, 0.23, 0.37)
    c.setLineWidth(3); c.rect(1.2 * cm, 1.2 * cm, W - 2.4 * cm, H - 2.4 * cm)
    c.setLineWidth(1); c.rect(1.5 * cm, 1.5 * cm, W - 3.0 * cm, H - 3.0 * cm)

    # Logo institucional
    logo = UPLOADS_DIR / "notif_logo.jpg"
    top = H - 2.6 * cm
    try:
        if logo.exists():
            img = ImageReader(str(logo))
            iw, ih = img.getSize()
            disp_w = 4.5 * cm
            disp_h = disp_w * ih / iw
            c.drawImage(img, cx - disp_w / 2, top - disp_h, disp_w, disp_h,
                        mask='auto', preserveAspectRatio=True)
            top = top - disp_h - 0.4 * cm
    except Exception:
        pass

    y = top - 0.6 * cm
    c.setFillColorRGB(0.12, 0.16, 0.22)
    c.setFont("Helvetica-Bold", 28); c.drawCentredString(cx, y, "CERTIFICADO DE INTEGRACIÓN")
    y -= 0.5 * cm
    c.setStrokeColorRGB(0.12, 0.23, 0.37); c.setLineWidth(1.5)
    c.line(cx - 6 * cm, y, cx + 6 * cm, y)
    y -= 1.1 * cm

    c.setFont("Helvetica", 14); c.drawCentredString(cx, y, "Se certifica a:")
    y -= 0.95 * cm
    c.setFont("Helvetica-Bold", 24); c.drawCentredString(cx, y, name)
    y -= 1.05 * cm

    max_w = W * 0.74
    body = (f"Por haber cumplido a cabalidad la integración y pruebas de la interfaz "
            f"{componente} - Versión {version}")
    c.setFont("Helvetica", 13)
    for ln in _wrap_text_lines(body, "Helvetica", 13, max_w):
        c.drawCentredString(cx, y, ln); y -= 0.6 * cm
    if productos_str:
        y -= 0.15 * cm
        for ln in _wrap_text_lines(f"para los Productos: {productos_str}", "Helvetica-Oblique", 13, max_w):
            c.setFont("Helvetica-Oblique", 13); c.drawCentredString(cx, y, ln); y -= 0.6 * cm
    y -= 0.1 * cm
    c.setFont("Helvetica", 13)
    for ln in _wrap_text_lines(f"con el Aplicativo {app_name}", "Helvetica", 13, max_w):
        c.drawCentredString(cx, y, ln); y -= 0.6 * cm

    y -= 0.7 * cm
    c.setFont("Helvetica", 12); c.drawCentredString(cx, y, "Desarrollado por:")
    y -= 0.65 * cm
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(cx, y, name)

    c.setFont("Helvetica", 11); c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(cx, 2.05 * cm, f"Emitido el {fecha}")
    c.save(); buf.seek(0)
    return buf.read()


async def _generate_integration_certificate_pdf(intg: dict, componente: str, version: str, productos_str: str):
    """Genera el Certificado de Integración para adjuntar al cierre.

    - Si existe un PDF base en el depósito 'Certificado' (db.config
      type=integration_certificate), estampa el texto dinámico sobre él.
    - Si NO existe un PDF base (o es una imagen / archivo no-PDF), construye un
      Certificado corporativo COMPLETO desde cero, de modo que SIEMPRE haya un
      certificado que adjuntar (nunca retorna None por falta de depósito)."""
    base_path = None
    doc = await db.config.find_one({"type": "integration_certificate"}, {"_id": 0})
    if doc and doc.get("filename") and str(doc["filename"]).lower().endswith(".pdf"):
        fpath = UPLOADS_DIR / doc["filename"]
        # Si el archivo no está en disco (FS efímero tras redeploy) pero sí en Mongo,
        # lo restauramos para poder estampar sobre TU PDF cargado.
        if not fpath.exists() and doc.get("content_b64"):
            try:
                fpath.write_bytes(base64.b64decode(doc["content_b64"]))
            except Exception as e:
                logger.warning(f"[cert] no se pudo restaurar el PDF base desde Mongo: {e}")
        if fpath.exists():
            base_path = fpath
    try:
        if base_path is None:
            # Sin PDF base válido → certificado autónomo corporativo.
            return _build_standalone_certificate_pdf(intg, componente, version, productos_str)

        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.pdfbase.pdfmetrics import stringWidth
        base = PdfReader(str(base_path))
        page = base.pages[0]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        name = intg.get("name", "")
        app_name = intg.get("app_name", "")

        # Anclas del template: posición de cada etiqueta fija impresa.
        anchors: dict = {}
        try:
            import pdfplumber
            with pdfplumber.open(str(base_path)) as _pdf:
                for _wd in _pdf.pages[0].extract_words():
                    anchors.setdefault(_wd["text"], _wd)
        except Exception as _e:
            logger.warning(f"[cert] no se pudieron leer anclas del template: {_e}")

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w, h))
        c.setFillColorRGB(0.12, 0.16, 0.22)
        R_MARGIN = w - 45

        def _yb(word, dy=3.0):
            return h - float(word["bottom"]) + dy

        def _fit_font(text, base_size, avail, font="Helvetica-Bold", floor=8):
            fs = base_size
            while fs > floor and stringWidth(text, font, fs) > avail:
                fs -= 1
            return fs

        if anchors.get("Certifica") or anchors.get("Productos:"):
            # Template MegaSoft con etiquetas fijas → rellenar SOLO valores dinámicos.
            a_cert = anchors.get("Certifica"); a_ca = anchors.get("a:")
            if a_cert:
                cx = (float(a_cert["x0"]) + float((a_ca or a_cert)["x1"])) / 2
                fs = _fit_font(name, 30, w - 160)
                c.setFont("Helvetica-Bold", fs)
                c.drawCentredString(cx, h - float(a_cert["bottom"]) - 44, name)
            a_intf = anchors.get("interfaz,")
            comp_txt = f"{componente} - Versión {version}".strip(" -")
            if a_intf and comp_txt:
                x = float(a_intf["x1"]) + 8
                a_para = anchors.get("para")
                limit = (float(a_para["x0"]) - 6) if a_para else R_MARGIN
                fs = _fit_font(comp_txt, 20, limit - x)
                c.setFont("Helvetica-Bold", fs); c.drawString(x, _yb(a_intf), comp_txt)
            a_prod = anchors.get("Productos:")
            if a_prod and productos_str:
                # Productos en la LÍNEA SIGUIENTE, CENTRADOS en la página.
                cxp = w / 2
                avail = w - 200
                yb = _yb(a_prod) - 24
                lines = []; cur = ""
                for wd in productos_str.split():
                    test = (cur + " " + wd).strip()
                    if stringWidth(test, "Helvetica-Bold", 18) <= avail or not cur:
                        cur = test
                    else:
                        lines.append(cur); cur = wd
                if cur:
                    lines.append(cur)
                c.setFont("Helvetica-Bold", 18)
                for i, ln in enumerate(lines):
                    c.drawCentredString(cxp, yb - i * 22, ln)
            a_app = anchors.get("Aplicativo")
            if a_app and app_name:
                x = float(a_app["x1"]) + 8
                a_des = anchors.get("desarrollado")
                limit = (float(a_des["x0"]) - 6) if a_des else R_MARGIN
                fs = _fit_font(app_name, 20, limit - x)
                c.setFont("Helvetica-Bold", fs); c.drawString(x, _yb(a_app), app_name)
            a_por = anchors.get("por")
            if a_por and name:
                # Nombre del integrador (desarrollador) en la LÍNEA SIGUIENTE, CENTRADO en la página.
                fs = _fit_font(name, 20, w - 160)
                c.setFont("Helvetica-Bold", fs)
                c.drawCentredString(w / 2, _yb(a_por) - 24, name)
            a_car = anchors.get("Caracas,")
            if a_car:
                fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
                c.setFont("Helvetica", 12); c.drawString(float(a_car["x1"]) + 6, _yb(a_car), fecha)
        else:
            # Fallback: template sin etiquetas → overlay centrado completo.
            cx = w / 2; y = h * 0.60
            c.setFont("Helvetica", 14); c.drawCentredString(cx, y, "Certifica a:")
            y -= 30; c.setFont("Helvetica-Bold", 22); c.drawCentredString(cx, y, name)
            y -= 40; max_w = w * 0.78
            body = (f"Por haber cumplido a cabalidad la integración y pruebas de la interfaz "
                    f"{componente} - Versión {version}")
            for ln in _wrap_text_lines(body, "Helvetica", 13, max_w):
                c.setFont("Helvetica", 13); c.drawCentredString(cx, y, ln); y -= 20
            y -= 6
            for ln in _wrap_text_lines(f"para los Productos: {productos_str}", "Helvetica-Oblique", 13, max_w):
                c.setFont("Helvetica-Oblique", 13); c.drawCentredString(cx, y, ln); y -= 20
            y -= 6
            for ln in _wrap_text_lines(f"con el Aplicativo {app_name}", "Helvetica", 13, max_w):
                c.setFont("Helvetica", 13); c.drawCentredString(cx, y, ln); y -= 20
            y -= 24; c.setFont("Helvetica", 12); c.drawCentredString(cx, y, "Desarrollado por:")
            y -= 24; c.setFont("Helvetica-Bold", 16); c.drawCentredString(cx, y, name)
        c.save(); buf.seek(0)
        overlay = PdfReader(buf)
        writer = PdfWriter()
        page.merge_page(overlay.pages[0])
        writer.add_page(page)
        for extra in base.pages[1:]:
            writer.add_page(extra)
        out = io.BytesIO(); writer.write(out); out.seek(0)
        return out.read()
    except Exception as e:
        logger.warning(f"[cert] fallo estampando sobre depósito, se genera certificado autónomo: {e}")
        try:
            return _build_standalone_certificate_pdf(intg, componente, version, productos_str)
        except Exception as e2:
            logger.error(f"[cert] no se pudo generar el certificado autónomo: {e2}")
            return None


@router.post("/integrators/{integrator_id}/close")
async def close_integrator_project(
    integrator_id: str,
    componente: Optional[str] = Form(None),
    version_componente: Optional[str] = Form(None),
    extra_recipients: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    authorization: Optional[str] = Header(None),
):
    """Cierre de Proyecto de Integración con generación automatizada de Certificado.

    - Ambiente de Prueba (project_scope='test_environment'): BYPASS total — solo se
      borra de la Vista de Proyectos (estatus 'Cerrado'). Sin modales/cert/correo/grilla.
    - Estándar (new/component): el registro pasa a 'Certificado' (Vista de Integradores).
    - Ampliación (expansion): reemplaza el registro certificado del mismo binomio
      (nombre + integration_type) y consume el registro de ampliación.
    """
    current_user = await get_current_user(authorization)
    role = (current_user or {}).get("role", "")
    if role not in ("admin", "implementador", "coordinador", "gestor"):
        raise HTTPException(status_code=403, detail="No tiene permisos para cerrar proyectos")

    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    closed_by = current_user.get("email") if current_user else ""
    scope = existing.get("project_scope")

    # ---------- EXCEPCIÓN: Ambiente de Prueba (bypass total) ----------
    if scope == "test_environment":
        await db.integrators.update_one(
            {"integrator_id": integrator_id},
            {"$set": {"integrator_status": "Cerrado", "project_scope": None,
                      "closed_at": now_iso, "closed_by": closed_by}},
        )
        updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
        return {"status": "ok", "bypass": True, "integrator": updated, "notification": None}

    # ---------- ESTÁNDAR: requiere datos técnicos del Modal 1 ----------
    componente = (componente or "").strip()
    version_componente = (version_componente or "").strip()
    if not componente or not version_componente:
        raise HTTPException(status_code=400, detail="Componente y Versión del Componente son obligatorios")

    productos_str = _certified_products_string(existing)
    medios_bullets = _certified_products_bullets_html(existing)

    # Certificado PDF (estampado sobre el depósito) + anexos del Modal 2
    attachments = []
    cert_bytes = await _generate_integration_certificate_pdf(existing, componente, version_componente, productos_str)
    if cert_bytes:
        attachments.append({"filename": f"Certificado_{existing.get('name', 'Integracion')}.pdf", "content": cert_bytes})
    for f in (files or []):
        try:
            content = await f.read()
            if content:
                attachments.append({"filename": f.filename, "content": content})
        except Exception:
            pass

    extra_cc = [e.strip() for e in re.split(r"[,;\s]+", extra_recipients or "") if e.strip() and "@" in e]

    # ---------- Persistencia / grillas ----------
    cert_set = {
        "cert_component": componente, "cert_version": version_componente,
        "cert_products": productos_str, "certified_at": now_iso, "certified_by": closed_by,
        "closed_at": now_iso, "closed_by": closed_by,
        "integrator_status": "Certificado", "project_scope": None,
    }

    replaced = False
    if scope == "expansion":
        base = await db.integrators.find_one({
            "name": existing.get("name"),
            "integration_type": existing.get("integration_type"),
            "integrator_status": "Certificado",
            "integrator_id": {"$ne": integrator_id},
        })
        if base:
            # Reemplazar el registro certificado existente con la info del cierre
            await db.integrators.update_one(
                {"integrator_id": base["integrator_id"]},
                {"$set": {**cert_set, "app_name": existing.get("app_name", base.get("app_name", "")),
                          "certifications": existing.get("certifications", base.get("certifications", {})),
                          "updated_at": now_iso}},
            )
            await db.integrators.delete_one({"integrator_id": integrator_id})
            target_id = base["integrator_id"]
            replaced = True

    if not replaced:
        await db.integrators.update_one({"integrator_id": integrator_id}, {"$set": cert_set})
        target_id = integrator_id

    updated = await db.integrators.find_one({"integrator_id": target_id}, {"_id": 0})

    # ---------- Notificación (Otras Acciones) con cert + anexos ----------
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    tpl_vars = {
        "nombre_integrador": existing.get("name", ""), "Integrador": existing.get("name", ""),
        "integrator_name": existing.get("name", ""),
        "nombre_aplicativo": existing.get("app_name", ""), "app_name": existing.get("app_name", ""),
        "Aplicativo_Integracion": existing.get("app_name", ""), "Aplicativo_Integración": existing.get("app_name", ""),
        "tipo_integracion": existing.get("integration_type", ""), "tipo_integrador": existing.get("integrator_type", ""),
        "modalidad_integracion": existing.get("integration_modality", ""),
        "nombre_implementador": existing.get("implementador", ""), "Nombre_Implementador": existing.get("implementador", ""),
        "componente": componente, "Componente": componente,
        "version_componente": version_componente, "Version_Componente": version_componente,
        "productos_certificados": productos_str, "Productos_Certificados": productos_str, "Productos": productos_str,
        "medios_certificados": medios_bullets, "Medios_Certificados": medios_bullets,
        "cerrado_por": closed_by, "Cerrado_Por": closed_by,
        "usuario_ejecutor": closed_by, "fecha_sistema": now_str, "Fecha_Sistema": now_str,
    }
    dispatch_result = None
    try:
        from services.other_actions_engine import dispatch_other_action
        dispatch_result = await dispatch_other_action(
            "integration_project_closed", tpl_vars, current_user=current_user,
            fallback_subject=f"Cierre de Proyecto de Integración: {existing.get('name', '')} — {existing.get('app_name', '')}",
            integrator=existing,
            extra_attachments=attachments or None,
            extra_cc=extra_cc or None,
        )
    except Exception as e:
        logger.warning(f"[close] dispatch integration_project_closed falló: {e}")
    return {"status": "ok", "bypass": False, "replaced": replaced,
            "productos_certificados": productos_str,
            "certificate_generated": bool(cert_bytes),
            "integrator": updated, "notification": dispatch_result}



def _build_integrator_tpl_vars(intg: dict, actor_email: str) -> dict:
    """Variables de plantilla para acciones de ciclo de vida de Integración."""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    email_intg = (intg.get("principal_contact_email") or "").strip()
    return {
        "nombre_integrador": intg.get("name", ""), "Integrador": intg.get("name", ""),
        "integrator_name": intg.get("name", ""),
        "nombre_aplicativo": intg.get("app_name", ""), "app_name": intg.get("app_name", ""),
        "tipo_integracion": intg.get("integration_type", ""), "tipo_integrador": intg.get("integrator_type", ""),
        "modalidad_integracion": intg.get("integration_modality", ""),
        "nombre_implementador": intg.get("implementador", ""), "Nombre_Implementador": intg.get("implementador", ""),
        "email_integrador": email_intg, "Correo_Integrador": email_intg,
        "usuario_ejecutor": actor_email, "fecha_sistema": now_str, "Fecha_Sistema": now_str,
    }


# ============================================================
# CICLO DE VIDA: Suspensión / Reactivación de Proyecto de Integración
# ============================================================
@router.post("/integrators/{integrator_id}/suspend")
async def suspend_integrator_project(integrator_id: str, authorization: Optional[str] = Header(None)):
    """Suspende un Proyecto de Integración activo → estatus 'Suspendido'.
    Conserva toda la información histórica (incluido project_scope) y dispara la
    'Otra Acción' de suspensión."""
    current_user = await get_current_user(authorization)
    role = (current_user or {}).get("role", "")
    if role not in ("admin", "implementador", "coordinador", "gestor"):
        raise HTTPException(status_code=403, detail="No tiene permisos para suspender proyectos")

    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    if existing.get("integrator_status") == "Cerrado":
        raise HTTPException(status_code=400, detail="Un proyecto cerrado no puede suspenderse")
    if existing.get("integrator_status") == "Suspendido":
        raise HTTPException(status_code=400, detail="El proyecto ya está suspendido")

    actor = current_user.get("email") if current_user else ""
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {
            "integrator_status": "Suspendido",
            "suspended_at": datetime.now(timezone.utc).isoformat(),
            "suspended_by": actor,
            "status_before_suspension": existing.get("integrator_status", "En proceso"),
        }},
    )
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})

    dispatch_result = None
    try:
        from services.other_actions_engine import dispatch_other_action
        dispatch_result = await dispatch_other_action(
            "integration_project_suspended",
            _build_integrator_tpl_vars(existing, actor),
            current_user=current_user,
            fallback_subject=f"Suspensión de Proyecto de Integración: {existing.get('name', '')} — {existing.get('app_name', '')}",
            integrator=existing,
        )
    except Exception as e:
        logger.warning(f"[suspend] dispatch integration_project_suspended falló: {e}")
    return {"status": "ok", "integrator": updated, "notification": dispatch_result}


@router.post("/integrators/{integrator_id}/reactivate")
async def reactivate_integrator_project(integrator_id: str, authorization: Optional[str] = Header(None)):
    """Reactiva un Proyecto de Integración suspendido → estatus 'En proceso'.
    Lo devuelve a la vista de proyectos activos y dispara la 'Otra Acción' de
    reactivación."""
    current_user = await get_current_user(authorization)
    role = (current_user or {}).get("role", "")
    if role not in ("admin", "implementador", "coordinador", "gestor"):
        raise HTTPException(status_code=403, detail="No tiene permisos para reactivar proyectos")

    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    if existing.get("integrator_status") != "Suspendido":
        raise HTTPException(status_code=400, detail="Solo se pueden reactivar proyectos suspendidos")

    actor = current_user.get("email") if current_user else ""
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {
            "integrator_status": "En proceso",
            "reactivated_at": datetime.now(timezone.utc).isoformat(),
            "reactivated_by": actor,
        }},
    )
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})

    dispatch_result = None
    try:
        from services.other_actions_engine import dispatch_other_action
        dispatch_result = await dispatch_other_action(
            "integration_project_reactivated",
            _build_integrator_tpl_vars(existing, actor),
            current_user=current_user,
            fallback_subject=f"Reactivación de Proyecto de Integración: {existing.get('name', '')} — {existing.get('app_name', '')}",
            integrator=existing,
        )
    except Exception as e:
        logger.warning(f"[reactivate] dispatch integration_project_reactivated falló: {e}")
    return {"status": "ok", "integrator": updated, "notification": dispatch_result}


# ============================================================
# REPOSITORIO DE CERTIFICADOS DE INTEGRACIÓN (Configuración)
# ============================================================
_CERT_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".pdf"}
_CERT_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}


async def _get_integration_certificate_attachment() -> Optional[list]:
    """Devuelve [{filename, content}] del certificado institucional guardado, o None."""
    try:
        doc = await db.config.find_one({"type": "integration_certificate"}, {"_id": 0})
        if not doc or not doc.get("filename"):
            return None
        fpath = UPLOADS_DIR / doc["filename"]
        if not fpath.exists():
            return None
        return [{"filename": doc.get("original_name") or doc["filename"], "content": fpath.read_bytes()}]
    except Exception as e:
        logger.warning(f"[cert] no se pudo leer el certificado: {e}")
        return None


@router.get("/integrators/config/certificate")
async def get_integration_certificate_info(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    doc = await db.config.find_one({"type": "integration_certificate"}, {"_id": 0})
    if not doc or not doc.get("filename"):
        return {"exists": False}
    return {
        "exists": True,
        "original_name": doc.get("original_name", doc["filename"]),
        "content_type": doc.get("content_type", ""),
        "uploaded_at": doc.get("uploaded_at", ""),
        "uploaded_by": doc.get("uploaded_by", ""),
    }


@router.post("/integrators/config/certificate")
async def upload_integration_certificate(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Carga/reemplaza el Certificado de Integración institucional.
    Formatos permitidos ESTRICTAMENTE: .jpg, .png, .pdf."""
    current_user = await get_current_user(authorization)
    role = (current_user or {}).get("role", "")
    if role not in ("admin", "coordinador", "gestor"):
        raise HTTPException(status_code=403, detail="No tiene permisos para gestionar el certificado")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _CERT_ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Formato no permitido. Solo se aceptan .jpg, .png y .pdf")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="El archivo está vacío")

    # Eliminar cualquier certificado previo (cualquier extensión).
    for old in UPLOADS_DIR.glob("integration_certificate.*"):
        try:
            old.unlink()
        except Exception:
            pass

    stored_name = f"integration_certificate{ext}"
    (UPLOADS_DIR / stored_name).write_bytes(content)

    now = datetime.now(timezone.utc).isoformat()
    await db.config.update_one(
        {"type": "integration_certificate"},
        {"$set": {
            "type": "integration_certificate",
            "filename": stored_name,
            "original_name": file.filename,
            "content_type": _CERT_MIME.get(ext, file.content_type or ""),
            # Persistencia en Mongo: el FS del contenedor es efímero (se pierde en
            # cada redeploy). Guardamos el contenido para restaurarlo al arranque.
            "content_b64": base64.b64encode(content).decode("ascii"),
            "uploaded_at": now,
            "uploaded_by": current_user.get("email"),
        }},
        upsert=True,
    )
    return {"status": "ok", "original_name": file.filename, "content_type": _CERT_MIME.get(ext, "")}


async def restore_integration_certificate():
    """Restaura el PDF/imagen del depósito 'Certificado' desde Mongo hacia el disco
    al arrancar el servidor (el FS del contenedor es efímero → sobrevive redeploys)."""
    try:
        doc = await db.config.find_one({"type": "integration_certificate"}, {"_id": 0})
        if not doc or not doc.get("filename") or not doc.get("content_b64"):
            return
        fpath = UPLOADS_DIR / doc["filename"]
        if not fpath.exists():
            fpath.write_bytes(base64.b64decode(doc["content_b64"]))
            logger.info(f"[cert] certificado restaurado a disco: {doc['filename']}")
    except Exception as e:
        logger.warning(f"[cert] restore_integration_certificate falló: {e}")


@router.get("/integrators/config/certificate/download")
async def download_integration_certificate(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    doc = await db.config.find_one({"type": "integration_certificate"}, {"_id": 0})
    if not doc or not doc.get("filename"):
        raise HTTPException(status_code=404, detail="No hay certificado cargado")
    fpath = UPLOADS_DIR / doc["filename"]
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
    return FileResponse(str(fpath), media_type=doc.get("content_type") or "application/octet-stream",
                        filename=doc.get("original_name") or doc["filename"])


@router.delete("/integrators/config/certificate")
async def delete_integration_certificate(authorization: Optional[str] = Header(None)):
    current_user = await get_current_user(authorization)
    role = (current_user or {}).get("role", "")
    if role not in ("admin", "coordinador", "gestor"):
        raise HTTPException(status_code=403, detail="No tiene permisos para eliminar el certificado")
    for old in UPLOADS_DIR.glob("integration_certificate.*"):
        try:
            old.unlink()
        except Exception:
            pass
    await db.config.delete_one({"type": "integration_certificate"})
    return {"status": "ok"}


class TestEnvironmentPayload(BaseModel):
    start_date: str
    end_date: str


@router.post("/integrators/{integrator_id}/assign-test-environment")
async def assign_test_environment(integrator_id: str, payload: TestEnvironmentPayload, authorization: Optional[str] = Header(None)):
    """Asigna una 'Asignación de Ambiente de Prueba' a un Integrador EXISTENTE.
    Marca project_scope='test_environment' con vigencia (Fecha Inicio/Fin) y lo deja
    'En proceso' para que sea un Proyecto Activo (badge morado + contador de días hábiles)."""
    await get_current_user(authorization)
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="El Integrador no existe. El Ambiente de Prueba solo puede asignarse a un Integrador registrado.")
    try:
        start = datetime.strptime(payload.start_date[:10], "%Y-%m-%d").date()
        end = datetime.strptime(payload.end_date[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido (use YYYY-MM-DD)")
    if end < start:
        raise HTTPException(status_code=400, detail="La Fecha Final no puede ser anterior a la Fecha de Inicio")
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {
            "project_scope": "test_environment",
            "integrator_status": "En proceso",
            "test_env_start_date": start.isoformat(),
            "test_env_end_date": end.isoformat(),
            "test_env_expiry_notified": False,
            "test_env_assigned_at": datetime.now(timezone.utc).isoformat(),
        }, "$unset": {"closed_at": "", "closed_by": ""}},
    )
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return {"status": "ok", "integrator": updated}


class ExpandPayload(BaseModel):
    productos_certificar: Optional[str] = None
    correo_eventual: Optional[str] = None
    contacts: Optional[List[dict]] = None


@router.post("/integrators/{integrator_id}/expand")
async def expand_integrator_type(integrator_id: str, payload: Optional[ExpandPayload] = None, authorization: Optional[str] = Header(None)):
    """Marca un Proyecto de Integración existente como 'Ampliación' de un tipo
    vigente. No crea una fila nueva (anti-duplicidad): actualiza la fila del tipo
    seleccionado a project_scope='expansion' y la deja 'En proceso' (en curso),
    para que se resalte en la grilla y aparezca en el filtro 'Proyectos Ampliados'.

    Al ser un proyecto de complemento, persiste los campos del complemento
    (productos a certificar y correo adicional eventual) usados luego en la
    notificación al Integrador."""
    await get_current_user(authorization)
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrator not found")
    set_data = {
        "project_scope": "expansion",
        "integrator_status": "En proceso",
        "expanded_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload is not None:
        if payload.productos_certificar is not None:
            set_data["productos_certificar"] = payload.productos_certificar
        if payload.correo_eventual is not None:
            set_data["correo_eventual"] = payload.correo_eventual
        # Fusionar el Responsable capturado (dedupe por email) en los contactos del integrador.
        if payload.contacts:
            merged = list(existing.get("contacts") or [])
            existing_emails = {(c.get("email") or "").strip().lower() for c in merged}
            for c in payload.contacts:
                email_key = (c.get("email") or "").strip().lower()
                if not email_key or email_key not in existing_emails:
                    merged.append(c)
                    if email_key:
                        existing_emails.add(email_key)
            set_data["contacts"] = merged
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": set_data},
    )
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return updated


@router.delete("/integrators/{integrator_id}")
async def delete_integrator(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    # Validar integridad referencial - verificar si hay cotizaciones que usen este integrador
    quotes_with_integrator = await db.quotes.count_documents({
        "integrator_id": integrator_id
    })
    if quotes_with_integrator > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"No se puede eliminar el integrador porque está asociado a {quotes_with_integrator} cotización(es). Elimine primero las cotizaciones asociadas."
        )
    
    result = await db.integrators.delete_one({"integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Integrator not found")
    return {"message": "Integrador eliminado exitosamente"}


@router.delete("/integrators/bulk/all")
async def delete_all_integrators(force_cascade: bool = False, authorization: Optional[str] = Header(None)):
    """Elimina integradores.
    - force_cascade=False (default): borra sólo los integradores SIN cotizaciones/proyectos asociados.
      Devuelve la lista de protegidos para que el frontend pregunte si desea forzar cascada.
    - force_cascade=True: borra integradores + todas sus cotizaciones + proyectos asociados.
    Solo admin."""
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden ejecutar esta acción")

    # Construir set de integrator_ids referenciados
    referenced_ids = set()
    q_refs = await db.quotes.distinct("integrator_id")
    referenced_ids.update([r for r in q_refs if r])
    p_refs = await db.projects.distinct("integrator_id")
    referenced_ids.update([r for r in p_refs if r])

    now = datetime.now(timezone.utc).isoformat()

    if force_cascade:
        # Borrar cotizaciones y proyectos asociados primero, luego TODOS los integradores.
        quotes_del = await db.quotes.delete_many({"integrator_id": {"$in": list(referenced_ids)}}) if referenced_ids else None
        projects_del = await db.projects.delete_many({"integrator_id": {"$in": list(referenced_ids)}}) if referenced_ids else None
        result = await db.integrators.delete_many({})

        await db.integrators_bulk_deletions.insert_one({
            "mode": "cascade",
            "deleted_count": result.deleted_count,
            "quotes_deleted": quotes_del.deleted_count if quotes_del else 0,
            "projects_deleted": projects_del.deleted_count if projects_del else 0,
            "deleted_by": current_user.get("email"),
            "deleted_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "deleted_at": now,
        })
        return {
            "message": (
                f"Se eliminaron {result.deleted_count} integrador(es) en cascada "
                f"(junto con {quotes_del.deleted_count if quotes_del else 0} cotización(es) y "
                f"{projects_del.deleted_count if projects_del else 0} proyecto(s))."
            ),
            "deleted_count": result.deleted_count,
            "quotes_deleted": quotes_del.deleted_count if quotes_del else 0,
            "projects_deleted": projects_del.deleted_count if projects_del else 0,
            "skipped_count": 0,
            "protected": [],
        }

    # Modo seguro: borra sólo los no referenciados
    result = await db.integrators.delete_many({"integrator_id": {"$nin": list(referenced_ids)}})

    # Detalle de los protegidos (para que el frontend pregunte si desea forzar cascada)
    protected_docs = await db.integrators.find(
        {}, {"_id": 0, "integrator_id": 1, "name": 1}
    ).to_list(None)
    protected = []
    for d in protected_docs:
        iid = d.get("integrator_id")
        qc = await db.quotes.count_documents({"integrator_id": iid})
        pc = await db.projects.count_documents({"integrator_id": iid})
        protected.append({
            "integrator_id": iid,
            "name": d.get("name"),
            "quotes_count": qc,
            "projects_count": pc,
        })

    await db.integrators_bulk_deletions.insert_one({
        "mode": "safe",
        "deleted_count": result.deleted_count,
        "skipped_count": len(protected),
        "protected_ids": [p["integrator_id"] for p in protected],
        "deleted_by": current_user.get("email"),
        "deleted_by_name": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "deleted_at": now,
    })

    if result.deleted_count == 0 and protected:
        msg = f"Ningún integrador eliminado. {len(protected)} conservado(s) por tener cotizaciones/proyectos asociados."
    else:
        parts = [f"Se eliminaron {result.deleted_count} integrador(es)"]
        if protected:
            parts.append(f"{len(protected)} conservado(s) por tener cotizaciones/proyectos asociados")
        msg = ". ".join(parts)

    return {
        "message": msg,
        "deleted_count": result.deleted_count,
        "skipped_count": len(protected),
        "protected": protected,
    }

@router.put("/integrators/{integrator_id}/assign")
async def assign_integrator_manager(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asignar un gestor/implementador a un proyecto de integración y notificar por email."""
    current_user = await get_current_user(authorization)
    
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Se requiere user_id")
    
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Proyecto de integración no encontrado")
    
    assignee = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not assignee:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    assignee_name = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip() or assignee.get('email', '')
    assignee_email = assignee.get('email', '')
    
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {
            "gestor": assignee_name,
            "gestor_user_id": user_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "assigned_by": current_user.get("user_id")
        }}
    )
    
    # Notificación por email al implementador asignado
    from services.email_service import send_email, resolve_sender_for_area
    assigner_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get('email', '')
    subject = f"Nuevo proyecto asignado: {integrator.get('name', '')} — {integrator.get('app_name', '')}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e40af; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Proyecto de Integración Asignado</h2>
        </div>
        <div style="padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
            <p>Hola <strong>{assignee_name}</strong>,</p>
            <p><strong>{assigner_name}</strong> te ha asignado un nuevo proyecto de integración:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-weight: bold; color: #475569;">Integrador</td>
                    <td style="padding: 8px;">{integrator.get('name', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-weight: bold; color: #475569;">Aplicativo</td>
                    <td style="padding: 8px;">{integrator.get('app_name', '')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-weight: bold; color: #475569;">Tipo</td>
                    <td style="padding: 8px;">{integrator.get('integration_type', 'N/A')}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px; font-weight: bold; color: #475569;">Modalidad</td>
                    <td style="padding: 8px;">{integrator.get('integration_modality', '')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold; color: #475569;">Categoría</td>
                    <td style="padding: 8px;">{integrator.get('categoria', 'N/A')}</td>
                </tr>
            </table>
            <p style="color: #64748b; font-size: 13px;">Ingresa al sistema para ver los detalles completos del proyecto.</p>
        </div>
    </div>
    """
    
    email_result = await send_email(
        to=[assignee_email] if assignee_email else [],
        subject=subject,
        html=html,
        action="integrator_assignment",
        sender=await resolve_sender_for_area("integradores"),
    )
    
    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return {
        "status": "ok",
        "integrator": updated,
        "email": email_result,
        "message": f"Proyecto asignado a {assignee_name}"
    }


@router.put("/integrators/{integrator_id}/assign-implementador")
async def assign_integrator_implementador(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Asignar un implementador a un proyecto de integración y notificar por email."""
    current_user = await get_current_user(authorization)
    
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Se requiere user_id")
    
    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Proyecto de integración no encontrado")
    
    assignee = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not assignee:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    assignee_name = f"{assignee.get('first_name', '')} {assignee.get('last_name', '')}".strip() or assignee.get('email', '')
    assignee_email = assignee.get('email', '')
    
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {
            "implementador": assignee_name,
            "implementador_user_id": user_id,
        }}
    )
    
    assigner_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get('email', '')

    # Tabla de contactos técnicos del integrador (disponible como variable {contactos_tecnicos})
    contacts_html = ""
    contacts = integrator.get("contacts") or []
    if contacts:
        contacts_rows = ""
        for c in contacts:
            contacts_rows += f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 6px 8px; font-size: 13px;">{c.get('name', '')}</td>
                    <td style="padding: 6px 8px; font-size: 13px;">{c.get('email', '') or '—'}</td>
                    <td style="padding: 6px 8px; font-size: 13px;">{c.get('phone', '') or '—'}</td>
                </tr>"""
        contacts_html = f"""
            <p style="margin-top: 16px; font-weight: bold; color: #334155;">Responsables Técnicos del Integrador:</p>
            <table style="width: 100%; border-collapse: collapse; margin: 8px 0;">
                <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
                    <th style="padding: 6px 8px; text-align: left; font-size: 12px; color: #475569;">Nombre</th>
                    <th style="padding: 6px 8px; text-align: left; font-size: 12px; color: #475569;">Email</th>
                    <th style="padding: 6px 8px; text-align: left; font-size: 12px; color: #475569;">Teléfono</th>
                </tr>
                {contacts_rows}
            </table>"""

    # Notificación 100% dinámica vía "Configuración de otras Acciones" (mismas reglas:
    # receptor, plantilla y canal definidos por el admin). El correo/destinatario/mensaje
    # hardcodeado fue removido por requerimiento.
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    tpl_vars = {
        "nombre_implementador": assignee_name, "Nombre_Implementador": assignee_name,
        "email_implementador": assignee_email, "Correo_Implementador": assignee_email,
        "nombre_integrador": integrator.get("name", ""), "Integrador": integrator.get("name", ""),
        "integrator_name": integrator.get("name", ""),
        "nombre_aplicativo": integrator.get("app_name", ""), "app_name": integrator.get("app_name", ""),
        "tipo_integracion": integrator.get("integration_type", ""), "tipo_integrador": integrator.get("integrator_type", ""),
        "asignado_por": assigner_name, "Asignado_Por": assigner_name,
        "contactos_tecnicos": contacts_html, "Contactos_Tecnicos": contacts_html,
        "fecha_sistema": now_str, "Fecha_Sistema": now_str,
    }
    from services.other_actions_engine import dispatch_other_action
    dispatch_result = await dispatch_other_action(
        "implementer_assignment", tpl_vars, current_user=current_user,
        fallback_subject=f"Asignación de proyecto: {integrator.get('name', '')} — {integrator.get('app_name', '')}",
    )

    updated = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    return {
        "status": "ok",
        "integrator": updated,
        "notification": dispatch_result,
        "message": f"Implementador asignado: {assignee_name}"
    }


@router.patch("/integrators/{integrator_id}/contact-date")
async def update_contact_date(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    """Actualizar solo la fecha de último contacto (inline edit)"""
    await get_current_user(authorization)
    date_val = body.get("last_contact_date")
    if date_val:
        from datetime import date as date_type
        try:
            parsed = datetime.strptime(date_val, "%Y-%m-%d").date()
            if parsed > date_type.today():
                raise HTTPException(status_code=400, detail="La fecha no puede ser futura")
            date_val = parsed.isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (use YYYY-MM-DD)")
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {"last_contact_date": date_val}}
    )
    return {"status": "ok", "last_contact_date": date_val}

# ==================== BITACORA ENDPOINTS ====================

@router.get("/integrators/{integrator_id}/bitacora")
async def get_bitacora(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    entries = await db.bitacora.find(
        {"integrator_id": integrator_id}, {"_id": 0}
    ).sort("date", -1).to_list(500)
    for e in entries:
        if isinstance(e.get('created_at'), str):
            e['created_at'] = datetime.fromisoformat(e['created_at'])
    return entries

@router.post("/integrators/{integrator_id}/bitacora")
async def add_bitacora_entry(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")
    
    entry = BitacoraEntry(
        integrator_id=integrator_id,
        description=body.get("description", ""),
        contact_id=body.get("contact_id"),
        contact_name=body.get("contact_name"),
        date=body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        commitment=body.get("commitment"),
        commitment_deadline=body.get("commitment_deadline"),
        commitment_completed=body.get("commitment_completed", False),
    )
    doc = entry.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.bitacora.insert_one(doc)
    doc.pop('_id', None)
    
    # Auto-update last_contact_date
    await db.integrators.update_one(
        {"integrator_id": integrator_id},
        {"$set": {"last_contact_date": entry.date}}
    )
    
    return doc

@router.patch("/integrators/{integrator_id}/bitacora/{entry_id}")
async def update_bitacora_entry(integrator_id: str, entry_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    update_fields = {}
    for field in ["description", "contact_id", "contact_name", "date", "commitment", "commitment_deadline", "commitment_completed"]:
        if field in body:
            update_fields[field] = body[field]
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    
    result = await db.bitacora.update_one(
        {"entry_id": entry_id, "integrator_id": integrator_id},
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    
    updated = await db.bitacora.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated

@router.delete("/integrators/{integrator_id}/bitacora/{entry_id}")
async def delete_bitacora_entry(integrator_id: str, entry_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.bitacora.delete_one({"entry_id": entry_id, "integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return {"message": "Entrada eliminada"}


# ==================== EVOLUTION LOG ENDPOINTS ====================

@router.get("/integrators/{integrator_id}/evolution")
async def get_evolution_log(integrator_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    entries = await db.evolution_log.find(
        {"integrator_id": integrator_id}, {"_id": 0}
    ).sort("date", -1).to_list(500)
    return entries

@router.post("/integrators/{integrator_id}/evolution")
async def add_evolution_entry(integrator_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    existing = await db.integrators.find_one({"integrator_id": integrator_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")
    
    entry = EvolutionEntry(
        integrator_id=integrator_id,
        comment=body.get("comment", ""),
        phase=body.get("phase", ""),
        contact_person=body.get("contact_person", ""),
        date=body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    )
    doc = entry.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.evolution_log.insert_one(doc)
    doc.pop('_id', None)
    return doc

@router.patch("/integrators/{integrator_id}/evolution/{entry_id}")
async def update_evolution_entry(integrator_id: str, entry_id: str, body: dict, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    update_fields = {}
    for field in ["comment", "phase", "date", "contact_person"]:
        if field in body:
            update_fields[field] = body[field]
    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.evolution_log.update_one(
        {"entry_id": entry_id, "integrator_id": integrator_id}, {"$set": update_fields}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    updated = await db.evolution_log.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated

@router.delete("/integrators/{integrator_id}/evolution/{entry_id}")
async def delete_evolution_entry(integrator_id: str, entry_id: str, authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    result = await db.evolution_log.delete_one({"entry_id": entry_id, "integrator_id": integrator_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return {"message": "Entrada eliminada"}



# Export integrators to Excel (with certification matrix)
@router.get("/integrators/export/excel")
async def export_integrators_excel(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    import pandas as pd

    def _fmt_ddmmyyyy(iso_str):
        """ISO (aaaa-mm-dd) → dd/mm/aaaa para la plantilla. Tolera vacío."""
        if not iso_str:
            return ''
        try:
            return datetime.strptime(str(iso_str)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            return str(iso_str)

    # Cabecera exacta de la plantilla: Coordinador junto a Implementador,
    # Fecha de Inicio antes de Último Contacto, y los campos de texto nuevos al final.
    BASE_HEADERS = [
        'Nombre', 'Tipo', 'Aplicativo', 'Modalidad de Integración', 'Estatus',
        'Tipo de Integracion', 'Gestor Administrativo', 'Implementador', 'Coordinador',
        'Nro Ticket', 'Categoría', 'Fecha de Inicio del Proyecto',
        'Último contacto con el Cliente', 'Correo',
    ]
    TAIL_HEADERS = ['Nombre del Proyecto', 'Observaciones',
                    'Nombre del Contacto Principal', 'Teléfono Contacto Principal',
                    'Email Contacto Principal', 'Negociación de Interfaz']

    rows = []
    for intg in integrators:
        row = {
            'Nombre': intg.get('name', ''),
            'Tipo': intg.get('integrator_type', ''),
            'Aplicativo': intg.get('app_name', ''),
            'Modalidad de Integración': intg.get('integration_modality', ''),
            'Estatus': intg.get('integrator_status', ''),
            'Tipo de Integracion': intg.get('integration_type', ''),
            'Gestor Administrativo': intg.get('gestor', ''),
            'Implementador': intg.get('implementador', ''),
            'Coordinador': intg.get('coordinador', ''),
            'Nro Ticket': intg.get('ticket_number', ''),
            'Categoría': intg.get('categoria', ''),
            'Fecha de Inicio del Proyecto': _fmt_ddmmyyyy(intg.get('project_start_date')),
            'Último contacto con el Cliente': intg.get('last_contact_date', ''),
            'Correo': intg.get('email', ''),
            'Nombre del Proyecto': intg.get('project_name', ''),
            'Observaciones': intg.get('observations', ''),
            'Nombre del Contacto Principal': intg.get('principal_contact_name', ''),
            'Teléfono Contacto Principal': intg.get('principal_contact_phone', ''),
            'Email Contacto Principal': intg.get('principal_contact_email', ''),
            'Negociación de Interfaz': intg.get('interface_negotiation', ''),
        }
        certs = intg.get('certifications') or {}
        for prod in INTEGRATOR_PRODUCTS:
            row[prod['name']] = certs.get(prod['id'], 'N/A')
        rows.append(row)

    column_order = BASE_HEADERS + [p['name'] for p in INTEGRATOR_PRODUCTS] + TAIL_HEADERS
    df = pd.DataFrame(rows, columns=column_order)
    
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, sheet_name='Integradores')
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=integradores.xlsx"}
    )

# Export integrators to PDF
@router.get("/integrators/export/pdf")
async def export_integrators_pdf(authorization: Optional[str] = Header(None)):
    await get_current_user(authorization)
    
    integrators = await db.integrators.find({}, {"_id": 0}).to_list(1000)
    
    if not integrators:
        raise HTTPException(status_code=404, detail="No integrators to export")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("<b>Listado de Integradores</b>", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Table data
    table_data = [["Nombre", "Tipo", "Aplicativo", "Modalidad", "Estatus"]]
    for intg in integrators:
        table_data.append([
            intg.get('name', ''),
            intg.get('integrator_type', ''),
            intg.get('app_name', ''),
            intg.get('integration_modality', ''),
            intg.get('integrator_status', '')
        ])
    
    table = Table(table_data, colWidths=[1.5*inch, 1*inch, 1.5*inch, 1.3*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.2, 0.3, 0.5)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=integradores.pdf"}
    )

async def _installed_clients_for_integrator(integrator_id: str):
    """Devuelve (integrador, clientes) de los comercios que tengan asignados EXACTAMENTE
    ese integrador (por id o por nombre) y esa misma Aplicación (app_name)."""
    intg = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not intg:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")

    name = (intg.get("name") or "").strip()
    app_name = (intg.get("app_name") or "").strip()

    def _rx(s):
        return {"$regex": f"^{re.escape(s)}$", "$options": "i"}

    or_integrador = [{"integrador_id": integrator_id}]
    if name:
        or_integrador.append({"integrador_name": _rx(name)})

    query = {"$and": [{"$or": or_integrador}]}
    if app_name:
        query["$and"].append({"aplicativo": _rx(app_name)})

    clients = await db.clients.find(
        query, {"_id": 0, "rif": 1, "legal_name": 1, "fantasy_name": 1, "condicion": 1}
    ).to_list(2000)
    clients.sort(key=lambda c: (c.get("legal_name") or "").strip().casefold())
    return intg, clients


@router.get("/integrators/{integrator_id}/installed-clients")
async def get_installed_clients(integrator_id: str, authorization: Optional[str] = Header(None)):
    """Listado dinámico de clientes instalados con este Integrador + Aplicación."""
    await get_current_user(authorization)
    intg, clients = await _installed_clients_for_integrator(integrator_id)
    return {
        "integrator_id": integrator_id,
        "integrator_name": intg.get("name", ""),
        "app_name": intg.get("app_name", ""),
        "count": len(clients),
        "clients": [
            {
                "rif": c.get("rif", ""),
                "legal_name": c.get("legal_name", ""),
                "fantasy_name": c.get("fantasy_name", ""),
                "condicion": c.get("condicion", ""),
            }
            for c in clients
        ],
    }


@router.get("/integrators/{integrator_id}/installed-clients/pdf")
async def export_installed_clients_pdf(integrator_id: str, authorization: Optional[str] = Header(None)):
    """PDF corporativo del listado de clientes instalados (Integrador + Aplicación)."""
    await get_current_user(authorization)
    from services.pdf_report import build_corporate_pdf

    intg, clients = await _installed_clients_for_integrator(integrator_id)
    name = intg.get("name", "")
    app_name = intg.get("app_name", "")

    headers = ['RIF', 'Razón Social', 'Nombre de Fantasía', 'Estatus']
    rows = [[c.get('rif', ''), c.get('legal_name', ''), c.get('fantasy_name', ''), c.get('condicion', '')] for c in clients]

    buffer = build_corporate_pdf(
        title=f"Clientes Instalados — Integrador: {name} | Aplicación: {app_name}",
        headers=headers, rows=rows,
        col_ratios=[1.4, 3, 3, 1.4],
    )
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', f"{name}_{app_name}").strip('_') or "integrador"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=clientes_instalados_{safe}.pdf"}
    )


# Import template for integrators (dynamic product columns)
@router.get("/integrators/import/template")
async def get_integrators_import_template(authorization: Optional[str] = Header(None)):
    """Descargar plantilla de importación con columnas dinámicas de productos"""
    await get_current_user(authorization)
    
    import pandas as pd
    
    # Plantilla oficial: campos base + 19 productos + campos de seguimiento al final.
    # Coordinador junto a Implementador; Fecha de Inicio antes de Último Contacto.
    sample_vals = ['C', 'P', 'N/A']
    data = {
        'Nombre': ['TechPay Solutions', 'ComercioApp', 'GatewayVe'],
        'Tipo': ['Integrador', 'Comercio', 'Integrador'],
        'Aplicativo': ['PaymentHub v3', 'MiTienda App', 'GW-Connect'],
        'Modalidad de Integración': ['PG Universal', 'MPOS', 'REST'],
        'Estatus': ['En proceso', 'Certificado', 'En proceso'],
        'Tipo de Integracion': ['PG', 'MP', 'CR'],
        'Gestor Administrativo': ['', '', ''],
        'Implementador': ['', '', ''],
        'Coordinador': ['', '', ''],
        'Nro Ticket': ['TKT-00145', '', 'TKT-00203'],
        'Categoría': ['Cliente/Integrador nuevo PG', '', 'Cliente/Integrador actual de VPOS'],
        'Fecha de Inicio del Proyecto': ['10/01/2026', '', '05/02/2026'],
        'Último contacto con el Cliente': ['15/01/2026', '28/02/2026', ''],
        'Correo': ['contacto@techpay.com', 'info@comercioapp.com', 'soporte@gw.ve'],
    }
    # Productos (matriz de certificación)
    for i, prod in enumerate(INTEGRATOR_PRODUCTS):
        data[prod['name']] = [sample_vals[i % 3], sample_vals[(i + 1) % 3], sample_vals[(i + 2) % 3]]
    # Campos de seguimiento de texto libre — AL FINAL
    data['Nombre del Proyecto'] = ['Migración PG Fase 1', '', 'Integración VPOS Retail']
    data['Observaciones'] = ['Pendiente kickoff', '', 'Requiere ambiente de pruebas']
    # Contacto Principal — 4 columnas nuevas al final
    data['Nombre del Contacto Principal'] = ['Ana Pérez', 'Luis Díaz', '']
    data['Teléfono Contacto Principal'] = ['+58 412-5551234', '0212-7654321', '']
    data['Email Contacto Principal'] = ['ana.perez@techpay.com', 'luis@comercioapp.com', '']
    data['Negociación de Interfaz'] = ['Sí', 'No', '']

    column_order = list(data.keys())  # garantiza el orden de columnas solicitado
    df = pd.DataFrame(data, columns=column_order)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla')

        # Hoja Instrucciones — campos base + matriz de productos
        base_fields = [
            {'Campo': 'Nombre *',                       'Descripcion': 'Nombre del integrador (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'TechPay Solutions'},
            {'Campo': 'Tipo *',                         'Descripcion': 'Integrador o Comercio (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'Integrador'},
            {'Campo': 'Aplicativo *',                   'Descripcion': 'Nombre del aplicativo (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'PaymentHub v3'},
            {'Campo': 'Modalidad de Integración *',     'Descripcion': 'Modalidad de integración (obligatorio)', 'Obligatorio': 'Sí', 'Ejemplo': 'PG Universal'},
            {'Campo': 'Estatus',                        'Descripcion': 'Estado actual (def: En proceso)', 'Obligatorio': 'No', 'Ejemplo': 'En proceso'},
            {'Campo': 'Tipo de Integracion',            'Descripcion': 'CR, LP, PG, MP, TK', 'Obligatorio': 'No', 'Ejemplo': 'PG'},
            {'Campo': 'Gestor Administrativo',          'Descripcion': 'Nombre del gestor (debe existir en el sistema)', 'Obligatorio': 'No', 'Ejemplo': 'Juan Perez'},
            {'Campo': 'Implementador',                  'Descripcion': 'Nombre EXACTO del implementador en BD (o email). Vacío = por asignar.', 'Obligatorio': 'No', 'Ejemplo': 'Maria Gonzalez'},
            {'Campo': 'Coordinador',                    'Descripcion': 'Nombre EXACTO de un usuario con cargo "Coordinador" del departamento "Implementación". Si no existe o el cargo es inválido, la fila se rechaza.', 'Obligatorio': 'No', 'Ejemplo': 'Kevin Malaguera'},
            {'Campo': 'Nro Ticket',                     'Descripcion': 'Número de ticket (texto libre). Editable en UI.', 'Obligatorio': 'No', 'Ejemplo': 'TKT-00145'},
            {'Campo': 'Categoría',                      'Descripcion': 'Categoria del integrador', 'Obligatorio': 'No', 'Ejemplo': 'Cliente/Integrador nuevo PG'},
            {'Campo': 'Fecha de Inicio del Proyecto',   'Descripcion': 'Fecha de inicio (DD/MM/AAAA estricto).', 'Obligatorio': 'No', 'Ejemplo': '10/01/2026'},
            {'Campo': 'Último contacto con el Cliente', 'Descripcion': 'Fecha (DD/MM/AAAA). No futura.', 'Obligatorio': 'No', 'Ejemplo': '15/01/2026'},
            {'Campo': 'Correo',                         'Descripcion': 'Email de contacto del integrador', 'Obligatorio': 'No', 'Ejemplo': 'contacto@empresa.com'},
            {'Campo': 'Nombre del Proyecto',            'Descripcion': 'Nombre del proyecto (texto libre).', 'Obligatorio': 'No', 'Ejemplo': 'Migración PG Fase 1'},
            {'Campo': 'Observaciones',                  'Descripcion': 'Notas/observaciones (texto libre).', 'Obligatorio': 'No', 'Ejemplo': 'Pendiente kickoff'},
            {'Campo': 'Nombre del Contacto Principal',  'Descripcion': 'Nombre del contacto principal del integrador (texto libre).', 'Obligatorio': 'No', 'Ejemplo': 'Ana Pérez'},
            {'Campo': 'Teléfono Contacto Principal',    'Descripcion': 'Teléfono del contacto principal (texto libre).', 'Obligatorio': 'No', 'Ejemplo': '+58 412-5551234'},
            {'Campo': 'Email Contacto Principal',       'Descripcion': 'Email del contacto principal. Si se indica, debe tener formato válido (usuario@dominio.com), si no la fila se rechaza.', 'Obligatorio': 'No', 'Ejemplo': 'ana.perez@empresa.com'},
            {'Campo': 'Negociación de Interfaz',        'Descripcion': '¿Estaría de acuerdo en negociar su interfaz? Solo acepta "Sí" o "No" (vacío permitido).', 'Obligatorio': 'No', 'Ejemplo': 'Sí'},
            {'Campo': '--- MATRIZ DE PRODUCTOS (19) ---', 'Descripcion': 'Columnas M a AE — estado de certificación por producto. Valores C / P / N/A.', 'Obligatorio': '---', 'Ejemplo': '---'},
        ]
        for prod in INTEGRATOR_PRODUCTS:
            base_fields.append({
                'Campo': prod['name'],
                'Descripcion': f'Estado de certificación para {prod["name"]}. Valores: C, P, N/A',
                'Obligatorio': 'No',
                'Ejemplo': 'C / P / N/A',
            })
        pd.DataFrame(base_fields).to_excel(writer, index=False, sheet_name='Instrucciones')
        
        # Valid values sheet — COMPLETE reference
        all_modalities = ['Bridge PG', 'MPOS', 'PG Universal', 'PG No universal', 'REST',
                          'Stand Alone', 'TKN No Universal', 'TKN Universal',
                          'Web Link de Pago Modalidad No Universal', 'Web Link de Pago Modalidad Universal', 'Wrapper']
        all_categories = [
            'Cliente/Integrador actual de PG', 'Cliente/Integrador actual de VPOS',
            'Cliente/Integrador actual Tokenizador', 'Cliente/Integrador nuevo Link de Pago',
            'Cliente/Integrador nuevo Mpos', 'Cliente/Integrador nuevo PG',
            'Cliente/Integrador nuevo VPOS', 'Cliente/Integrador MobilePOS'
        ]
        max_len = max(len(all_modalities), len(all_categories), len(INTEGRATOR_PRODUCTS), 12)
        def pad(lst):
            return lst + [''] * (max_len - len(lst))
        values_data = {
            'Tipos de Integrador (Col B)': pad(['Integrador', 'Comercio']),
            'Modalidades (Col D)': pad(all_modalities),
            'Tipos de Integración (Col F)': pad(['CR — Caja Registradora', 'LP — Link de Pago',
                'PG — Payment Gateway', 'MP — Android (Mobile POS)', 'TK — Tokenizador']),
            'Estatus (Col E)': pad(['Certificado', 'En proceso', 'Suspendido']),
            'Categorías (Col J)': pad(all_categories),
            'Valores de Certificación': pad(['C — Certificado', 'P — Pendiente', 'N/A — No Aplica',
                '(vacío) — Se asigna N/A automáticamente', 'Se aceptan mayúsculas y minúsculas (c, p, n/a)']),
            'Formato de Fechas (Col K)': pad(['DD/MM/AAAA (ej: 15/01/2026)', 'AAAA-MM-DD (ej: 2026-01-15)',
                'DD-MM-AAAA (ej: 15-01-2026)', 'No se permiten fechas futuras']),
            'Reglas de Importación': pad([
                '1. La clave única es: Nombre + Tipo Integración',
                '2. Si un registro ya existe (misma clave), se ACTUALIZAN sus datos',
                '3. La Matriz de Certificación existente se preserva al actualizar',
                '4. Los campos marcados con * son OBLIGATORIOS',
                '5. Si no indica Estatus, se asigna "En proceso" por defecto',
                '6. El Gestor e Implementador deben estar registrados en el sistema (nombre o email)',
                '7. Las columnas de productos (M a AE) son opcionales',
                '8. Celdas vacías en productos se asignan como N/A',
                '9. Se aceptan archivos .xlsx, .xls y .csv (separador: coma, punto y coma o tab)',
                '10. Los valores deben coincidir EXACTAMENTE con los de esta hoja (respetar mayúsculas)',
            ])
        }
        pd.DataFrame(values_data).to_excel(writer, index=False, sheet_name='Valores Válidos')
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_integradores.xlsx"}
    )

# Import integrators from Excel/CSV with Upsert logic, certification matrix, and detailed validation
@router.post("/integrators/import", response_model=ImportResult)
async def import_integrators(
    file: UploadFile = File(...),
    mode: str = Form("upsert"),
    authorization: Optional[str] = Header(None)
):
    current_user = await get_current_user(authorization)
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden importar data de integradores")
    
    import pandas as pd
    import unicodedata

    def _norm_name(s):
        """Normaliza nombres/emails para comparar: minúsculas, sin acentos/diacríticos
        y espacios internos colapsados. Evita falsos 'usuario no existe' por tildes
        (María vs Maria), dobles espacios o mayúsculas."""
        s = (s or "").strip().lower()
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(c for c in s if not unicodedata.combining(c))
        s = re.sub(r'\s+', ' ', s)
        return s

    content = await file.read()
    errors: List[ImportError] = []
    # Dedup en-archivo: una fila solo es duplicado real si coincide en su totalidad
    # (Nombre + Tipo + Tipo de Integración + Aplicativo + Modalidad). Si difiere en
    # Aplicativo/Modalidad/Tipo de Integración, es un registro distinto y se inserta.
    seen_row_keys = set()
    success_count = 0
    updated_count = 0
    skipped_count = 0
    cert_updates_count = 0
    
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['csv', 'xlsx', 'xls']:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            cert_updates_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message='Formato de archivo no soportado',
                suggested_action='Utilice archivos .xlsx, .xls o .csv')],
            message='Error: Formato de archivo no válido'
        )
    
    try:
        if file_ext == 'csv':
            # Auto-detect separator: try comma, semicolon, tab
            for sep in [',', ';', '\t']:
                try:
                    df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='utf-8')
                    if len(df.columns) >= 4:
                        break
                except Exception:
                    continue
            else:
                # Fallback: try latin-1 encoding
                for sep in [',', ';', '\t']:
                    try:
                        df = pd.read_csv(io.BytesIO(content), sep=sep, encoding='latin-1')
                        if len(df.columns) >= 4:
                            break
                    except Exception:
                        continue
                else:
                    df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        
        total_rows = len(df)
        
        if total_rows == 0:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                cert_updates_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column='archivo', value=file.filename,
                    error_type='format', message='El archivo está vacío',
                    suggested_action='Agregue registros al archivo antes de importar')],
                message='Error: El archivo no contiene datos'
            )
        
        # Keep original column names for product matching before normalizing
        _original_columns = list(df.columns.str.strip())
        df.columns = [c.strip() for c in df.columns]
        
        # Normalize base column names
        column_mapping = {
            'Nombre': 'name', 'nombre': 'name', 'nombre_del_integrador': 'name',
            'Tipo': 'integrator_type', 'tipo': 'integrator_type', 'tipo_de_integrador': 'integrator_type',
            'Tipo Integración': 'integration_type', 'tipo_integración': 'integration_type',
            'Tipo de Integración': 'integration_type', 'tipo de integración': 'integration_type',
            'tipo_de_integración': 'integration_type', 'tipo_de_integracion': 'integration_type',
            'tipo_integracion': 'integration_type',
            'Aplicativo': 'app_name', 'aplicativo': 'app_name', 'nombre_del_aplicativo': 'app_name',
            'Modalidad': 'integration_modality', 'modalidad': 'integration_modality',
            'modalidad_de_integración': 'integration_modality', 'modalidad_de_integracion': 'integration_modality',
            'Modalidad de Integración': 'integration_modality',
            'Estatus': 'integrator_status', 'estatus': 'integrator_status', 'estado': 'integrator_status',
            'Gestor': 'gestor', 'gestor_asignado': 'gestor',
            'Gestor Administrativo': 'gestor', 'gestor_administrativo': 'gestor',
            'Gestor Adminisitrativo': 'gestor',  # typo en archivos legados
            'Implementador': 'implementador', 'implementador': 'implementador',
            'implementador_asignado': 'implementador', 'implementer': 'implementador',
            'Nro de Ticket': 'ticket_number', 'nro_de_ticket': 'ticket_number',
            'nro_ticket': 'ticket_number', 'ticket': 'ticket_number',
            'Ticket': 'ticket_number', 'Numero de Ticket': 'ticket_number',
            'Nro Ticket': 'ticket_number', 'nro ticket': 'ticket_number',
            'Categoría': 'categoria', 'categoría': 'categoria', 'categoria': 'categoria', 'Categoria': 'categoria',
            'Último Contacto': 'last_contact_date', 'último_contacto': 'last_contact_date',
            'ultimo_contacto': 'last_contact_date', 'Ultimo Contacto': 'last_contact_date',
            'Último contacto con el Cliente': 'last_contact_date',
            'ultimo contacto con el cliente': 'last_contact_date',
            'Correo': 'email', 'correo': 'email', 'email_contacto': 'email',
            'Tipo Integracion': 'integration_type', 'tipo integracion': 'integration_type',
            'Tipo de Integracion': 'integration_type',
            'Coordinador': 'coordinador', 'coordinador': 'coordinador',
            'Fecha de Inicio del Proyecto': 'project_start_date', 'fecha de inicio del proyecto': 'project_start_date',
            'Fecha de Inicio': 'project_start_date', 'fecha_inicio_proyecto': 'project_start_date',
            'Nombre del Proyecto': 'project_name', 'nombre del proyecto': 'project_name', 'nombre_proyecto': 'project_name',
            'Observaciones': 'observations', 'observaciones': 'observations',
            'Nombre del Contacto Principal': 'principal_contact_name', 'nombre del contacto principal': 'principal_contact_name',
            'nombre_del_contacto_principal': 'principal_contact_name',
            'Teléfono Contacto Principal': 'principal_contact_phone', 'teléfono contacto principal': 'principal_contact_phone',
            'Telefono Contacto Principal': 'principal_contact_phone', 'telefono contacto principal': 'principal_contact_phone',
            'telefono_contacto_principal': 'principal_contact_phone',
            'Email Contacto Principal': 'principal_contact_email', 'email contacto principal': 'principal_contact_email',
            'Correo Contacto Principal': 'principal_contact_email', 'email_contacto_principal': 'principal_contact_email',
            'Negociación de Interfaz': 'interface_negotiation', 'negociación de interfaz': 'interface_negotiation',
            'Negociacion de Interfaz': 'interface_negotiation', 'negociacion de interfaz': 'interface_negotiation',
            'negociacion_de_interfaz': 'interface_negotiation',
        }
        
        # Pre-load users and products
        all_users = await db.users.find({"is_active": True}, {"_id": 0, "user_id": 1, "first_name": 1, "last_name": 1, "email": 1, "cargo": 1, "departamento": 1}).to_list(1000)
        user_names = set()
        # user_lookup maps lowercased fullname/email -> {user_id, display_name}
        user_lookup = {}
        # coordinator_lookup: SOLO usuarios cargo 'Coordinador' del depto 'Implementación'
        coordinator_lookup = {}
        for u in all_users:
            full = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
            email = u.get('email', '')
            display = full if full else email
            full_key = _norm_name(full)
            email_key = _norm_name(email)
            if full_key:
                user_names.add(full_key)
                user_lookup[full_key] = {"user_id": u.get("user_id"), "display": display}
            if email_key:
                user_names.add(email_key)
                user_lookup[email_key] = {"user_id": u.get("user_id"), "display": display}
            if u.get("cargo") == "Coordinador" and u.get("departamento") == "Implementación":
                entry = {"user_id": u.get("user_id"), "display": display}
                if full_key:
                    coordinator_lookup[full_key] = entry
                if email_key:
                    coordinator_lookup[email_key] = entry
        
        default_certs = {pid: "N/A" for pid in INTEGRATOR_PRODUCT_IDS}

        # Build product name -> id mapping (case-insensitive)
        product_name_to_id = {name.strip(): pid for name, pid in INTEGRATOR_PRODUCT_NAME_TO_ID.items()}
        
        # Identify which columns in the file are product columns
        base_column_names = set(column_mapping.keys())
        product_columns = {}  # original_col_name -> service_id
        for col in df.columns:
            col_stripped = col.strip()
            if col_stripped.lower() in [k.lower() for k in base_column_names]:
                continue
            # Check if this column matches a product name
            if col_stripped.lower() in product_name_to_id:
                product_columns[col] = product_name_to_id[col_stripped.lower()]
        
        # Rename base columns
        rename_map = {}
        for col in df.columns:
            if col in column_mapping:
                rename_map[col] = column_mapping[col]
        df.rename(columns=rename_map, inplace=True)
        
        # Deduplicate columns after renaming (keep first occurrence)
        # This prevents "truth value of a Series is ambiguous" errors
        df = df.loc[:, ~df.columns.duplicated()]
        
        required_columns = ['name', 'integrator_type', 'app_name', 'integration_modality']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return ImportResult(
                status='error', total_processed=0, success_count=0, updated_count=0,
                cert_updates_count=0, error_count=1, skipped_count=0,
                errors=[ImportError(row=0, column=', '.join(missing_columns), value=None,
                    error_type='missing',
                    message=f'Columnas requeridas no encontradas: {", ".join(missing_columns)}',
                    suggested_action='Asegúrese de que el archivo tenga las columnas: Nombre, Tipo, Aplicativo, Modalidad')],
                message=f'Error: Faltan columnas requeridas ({", ".join(missing_columns)})'
            )
        
        valid_integration_types = ['CR', 'LP', 'PG', 'MP', 'TK']
        valid_cert_values = {'c': 'C', 'p': 'P', 'n/a': 'N/A', 'na': 'N/A', '': 'N/A'}
        
        def _safe_val(row, col, default=''):
            """Safely extract a scalar value from a row, handling duplicate columns."""
            val = row.get(col, default)
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            if pd.isna(val):
                return default
            return str(val).strip()
        
        for idx, row in df.iterrows():
            row_num = idx + 2
            
            try:
                name = _safe_val(row, 'name')
                integrator_type = _safe_val(row, 'integrator_type')
                app_name = _safe_val(row, 'app_name')
                integration_modality = _safe_val(row, 'integration_modality')
                integrator_status = _safe_val(row, 'integrator_status', 'En proceso')
                integration_type = _safe_val(row, 'integration_type')
                gestor = _safe_val(row, 'gestor')
                implementador_raw = _safe_val(row, 'implementador')
                ticket_number = _safe_val(row, 'ticket_number')
                categoria = _safe_val(row, 'categoria')
                last_contact_raw = _safe_val(row, 'last_contact_date')
                email = _safe_val(row, 'email')
                
                row_errors = []
                
                # Parse last_contact_date - handle datetime objects from Excel AND strings
                last_contact_date = None
                raw_val_contact = row.get('last_contact_date', None)
                if isinstance(raw_val_contact, pd.Series):
                    raw_val_contact = raw_val_contact.iloc[0]
                
                from datetime import date as date_type
                
                if isinstance(raw_val_contact, datetime):
                    # pandas read Excel dates as datetime objects
                    parsed_date = raw_val_contact.date()
                    if parsed_date > date_type.today():
                        row_errors.append(ImportError(row=row_num, column='Último Contacto (Col I)',
                            value=str(parsed_date), error_type='invalid',
                            message=f'Fila {row_num}, Columna I (Último Contacto): La fecha es posterior a hoy. No se permiten fechas futuras.',
                            suggested_action=f'Corrija la celda I{row_num}. Ingrese una fecha igual o anterior a hoy'))
                    else:
                        last_contact_date = parsed_date.isoformat()
                elif last_contact_raw and last_contact_raw.lower() not in ('n/a', 'na', '', 'nan', 'none'):
                    parsed_date = None
                    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S'):
                        try:
                            parsed_date = datetime.strptime(last_contact_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                    if parsed_date is None:
                        row_errors.append(ImportError(row=row_num, column='Último Contacto (Col I)',
                            value=last_contact_raw, error_type='invalid',
                            message=f'Fila {row_num}, Columna I (Último Contacto): El formato "{last_contact_raw}" no es reconocido. Formatos aceptados: DD/MM/AAAA (ej: 15/01/2026) o AAAA-MM-DD (ej: 2026-01-15).',
                            suggested_action=f'Corrija la celda I{row_num}. Use formato de fecha estándar: 15/01/2026'))
                    elif parsed_date > date_type.today():
                        row_errors.append(ImportError(row=row_num, column='Último Contacto (Col I)',
                            value=last_contact_raw, error_type='invalid',
                            message=f'Fila {row_num}, Columna I (Último Contacto): La fecha {last_contact_raw} es posterior a hoy ({date_type.today().strftime("%d/%m/%Y")}). No se permiten fechas futuras.',
                            suggested_action=f'Corrija la celda I{row_num}. Ingrese una fecha igual o anterior a hoy'))
                    else:
                        last_contact_date = parsed_date.isoformat()
                
                if not name:
                    row_errors.append(ImportError(row=row_num, column='Nombre (Col A)', value='(vacío)',
                        error_type='missing', message=f'Fila {row_num}, Columna A (Nombre): El campo está vacío. Cada integrador debe tener un nombre único que lo identifique.',
                        suggested_action='Complete la celda A{0} con el nombre del integrador. Este campo es obligatorio (*).'.format(row_num)))
                
                if not app_name:
                    row_errors.append(ImportError(row=row_num, column='Aplicativo (Col C)', value='(vacío)',
                        error_type='missing', message=f'Fila {row_num}, Columna C (Aplicativo): El campo está vacío. Es obligatorio indicar el nombre del sistema o aplicación del integrador.',
                        suggested_action='Complete la celda C{0} con el nombre del aplicativo. Este campo es obligatorio (*).'.format(row_num)))
                
                if integrator_type not in INTEGRATOR_TYPES:
                    row_errors.append(ImportError(row=row_num, column='Tipo (Col B)', value=integrator_type or '(vacío)',
                        error_type='invalid', message=f'Fila {row_num}, Columna B (Tipo): Se recibió "{integrator_type or "(vacío)"}" pero solo se aceptan: {", ".join(INTEGRATOR_TYPES)}. El valor debe coincidir exactamente.',
                        suggested_action='Corrija la celda B{0}. Copie el valor exacto de la hoja "Valores Válidos", columna "Tipos de Integrador".'.format(row_num)))
                
                if integration_modality not in INTEGRATION_MODALITIES:
                    row_errors.append(ImportError(row=row_num, column='Modalidad (Col D)', value=integration_modality or '(vacío)',
                        error_type='invalid', message=f'Fila {row_num}, Columna D (Modalidad): Se recibió "{integration_modality or "(vacío)"}" pero no coincide con ninguna modalidad válida. Verifique mayúsculas y espacios.',
                        suggested_action='Corrija la celda D{0}. Consulte la hoja "Valores Válidos", columna "Modalidades" para ver las {1} opciones disponibles.'.format(row_num, len(INTEGRATION_MODALITIES))))
                
                if integration_type and integration_type not in valid_integration_types:
                    row_errors.append(ImportError(row=row_num, column='Tipo Integración (Col F)', value=integration_type,
                        error_type='invalid', message=f'Fila {row_num}, Columna F (Tipo Integración): Se recibió "{integration_type}" pero solo se aceptan: {", ".join(valid_integration_types)}.',
                        suggested_action='Corrija la celda F{0}. Use exactamente: {1}.'.format(row_num, ", ".join(valid_integration_types))))
                
                if gestor and _norm_name(gestor) not in user_names:
                    row_errors.append(ImportError(row=row_num, column='Gestor (Col G)', value=gestor,
                        error_type='invalid', message=f'Fila {row_num}, Columna G (Gestor): El usuario "{gestor}" no está registrado en el sistema. No se puede asignar como gestor.',
                        suggested_action='Corrija la celda G{0}. El gestor debe ser un usuario activo del sistema (nombre completo o email). Verifique en el módulo de Usuarios.'.format(row_num)))
                
                # Implementador (Col H): si viene, debe coincidir EXACTO con un usuario activo.
                # Si viene vacío, queda por asignar y se setea luego desde UI.
                implementador_name = None
                implementador_user_id = None
                if implementador_raw:
                    found = user_lookup.get(_norm_name(implementador_raw))
                    if found:
                        implementador_name = found["display"]
                        implementador_user_id = found["user_id"]
                    else:
                        row_errors.append(ImportError(row=row_num, column='Implementador (Col H)', value=implementador_raw,
                            error_type='invalid',
                            message=f'Fila {row_num}, Columna H (Implementador): El usuario "{implementador_raw}" no coincide exactamente con ningún usuario activo. El nombre debe ser IDÉNTICO al registrado en la BD (o usar el email).',
                            suggested_action='Corrija la celda H{0}. Copie el nombre completo (ej: "Maria Gonzalez") o el email exacto del implementador desde el módulo de Usuarios. Deje vacío para asignar luego.'.format(row_num)))


                if integrator_status not in INTEGRATOR_STATUSES:
                    integrator_status = "En proceso"

                # Coordinador (opcional): si viene, debe ser un usuario con cargo
                # 'Coordinador' del departamento 'Implementación'. Si no, se rechaza la fila.
                coordinador_raw = _safe_val(row, 'coordinador')
                coordinador_name = None
                coordinador_user_id = None
                coordinador_invalid = False
                if coordinador_raw:
                    cfound = coordinator_lookup.get(_norm_name(coordinador_raw))
                    if cfound:
                        coordinador_name = cfound["display"]
                        coordinador_user_id = cfound["user_id"]
                    else:
                        coordinador_invalid = True
                        row_errors.append(ImportError(row=row_num, column='Coordinador',
                            value=coordinador_raw, error_type='invalid',
                            message=f'Error en fila {row_num}: Coordinador no encontrado o cargo inválido',
                            suggested_action='El Coordinador debe ser un usuario con cargo "Coordinador" del departamento "Implementación".'))

                # Fecha de Inicio del Proyecto (opcional): formato estricto DD/MM/AAAA
                # para texto; se aceptan fechas nativas de Excel.
                project_start_date = None
                psd_invalid = False
                raw_psd = row.get('project_start_date', None)
                if isinstance(raw_psd, pd.Series):
                    raw_psd = raw_psd.iloc[0]
                psd_raw = _safe_val(row, 'project_start_date')
                if isinstance(raw_psd, datetime):
                    project_start_date = raw_psd.date().isoformat()
                elif psd_raw and psd_raw.lower() not in ('n/a', 'na', '', 'nan', 'none'):
                    try:
                        project_start_date = datetime.strptime(psd_raw, '%d/%m/%Y').date().isoformat()
                    except ValueError:
                        psd_invalid = True
                        row_errors.append(ImportError(row=row_num, column='Fecha de Inicio del Proyecto',
                            value=psd_raw, error_type='invalid',
                            message=f'Fila {row_num}, Fecha de Inicio del Proyecto: El formato "{psd_raw}" no es válido. Use estrictamente DD/MM/AAAA (ej: 10/01/2026).',
                            suggested_action=f'Corrija la fecha de inicio en la fila {row_num}. Formato obligatorio: DD/MM/AAAA.'))

                project_name = _safe_val(row, 'project_name')
                observations = _safe_val(row, 'observations')

                # Contacto Principal (4 campos nuevos)
                principal_contact_name = _safe_val(row, 'principal_contact_name')
                principal_contact_phone = _safe_val(row, 'principal_contact_phone')
                principal_contact_email = _safe_val(row, 'principal_contact_email')
                pce_invalid = False
                if principal_contact_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", principal_contact_email):
                    pce_invalid = True
                    row_errors.append(ImportError(row=row_num, column='Email Contacto Principal',
                        value=principal_contact_email, error_type='invalid',
                        message=f'Fila {row_num}, Email Contacto Principal: "{principal_contact_email}" no tiene un formato de correo válido.',
                        suggested_action='Corrija el correo en la fila {0}. Use el formato usuario@dominio.com o deje la celda vacía.'.format(row_num)))
                interface_negotiation = None
                neg_raw = _safe_val(row, 'interface_negotiation')
                neg_invalid = False
                if neg_raw:
                    low = neg_raw.strip().lower()
                    if low in ('sí', 'si', 's', 'yes', 'true', '1'):
                        interface_negotiation = 'Sí'
                    elif low in ('no', 'n', 'false', '0'):
                        interface_negotiation = 'No'
                    else:
                        neg_invalid = True
                        row_errors.append(ImportError(row=row_num, column='Negociación de Interfaz',
                            value=neg_raw, error_type='invalid',
                            message=f'Fila {row_num}, Negociación de Interfaz: Se recibió "{neg_raw}" pero solo se acepta "Sí" o "No".',
                            suggested_action='Corrija la celda en la fila {0}. Use exactamente "Sí" o "No", o déjela vacía.'.format(row_num)))
                # Parse certification columns
                row_certs = {}
                cert_has_errors = False
                for col_name, service_id in product_columns.items():
                    raw_val = _safe_val(row, col_name)
                    normalized = valid_cert_values.get(raw_val.lower(), None)
                    if normalized is None:
                        col_letter = chr(ord('J') + list(product_columns.keys()).index(col_name)) if list(product_columns.keys()).index(col_name) < 16 else f'Col {10 + list(product_columns.keys()).index(col_name)}'
                        row_errors.append(ImportError(row=row_num, column=f'{col_name} ({col_letter})',
                            value=raw_val, error_type='invalid',
                            message=f'Fila {row_num}, {col_letter} ({col_name}): Se recibió "{raw_val}" pero solo se aceptan valores de certificación: C (Certificado), P (Pendiente) o N/A (No Aplica). Las celdas vacías se asignan como N/A.',
                            suggested_action=f'Corrija la celda en la fila {row_num}, columna "{col_name}". Use exactamente: C, P o N/A'))
                        cert_has_errors = True
                    else:
                        row_certs[service_id] = normalized
                
                if row_errors:
                    errors.extend(row_errors)
                    if cert_has_errors or coordinador_invalid or psd_invalid or pce_invalid or neg_invalid or not name or not app_name or integrator_type not in INTEGRATOR_TYPES or integration_modality not in INTEGRATION_MODALITIES:
                        skipped_count += 1
                        continue
                
                # Build full certifications: start with defaults, overlay with file data
                full_certs = dict(default_certs)
                for sid, val in row_certs.items():
                    full_certs[sid] = val

                # Dedup en-archivo: clave = TODAS las columnas críticas (A,B,C,D + Tipo Int.).
                # Filas con A/B iguales pero C/D distintas son registros diferentes (NO se omiten);
                # solo se omite una fila 100% idéntica a otra ya procesada del mismo archivo.
                row_key = (
                    name.strip().lower(),
                    (integrator_type or '').strip().lower(),
                    (integration_type or '').strip().lower(),
                    (app_name or '').strip().lower(),
                    (integration_modality or '').strip().lower(),
                )
                if row_key in seen_row_keys:
                    errors.append(ImportError(row=row_num, column='Fila duplicada',
                        value=name, error_type='duplicate',
                        message=f'Fila {row_num}: Registro 100% idéntico a una fila anterior del archivo (Nombre, Tipo, Tipo de Integración, Aplicativo y Modalidad coinciden). Se omitió para evitar duplicados.',
                        suggested_action='Si las filas deben ser distintas, modifique al menos el Aplicativo (Col C) o la Modalidad (Col D).'))
                    skipped_count += 1
                    continue
                seen_row_keys.add(row_key)

                # Composite key for upsert: Nombre + Tipo + Tipo de Integración + Aplicativo + Modalidad.
                # Permite que un mismo integrador con distinto Aplicativo/Modalidad/Tipo de Integración
                # genere registros independientes (en vez de sobrescribir uno con otro).
                composite_query = {
                    "name": name,
                    "integrator_type": integrator_type,
                    "app_name": app_name,
                    "integration_modality": integration_modality,
                }
                if integration_type:
                    composite_query["integration_type"] = integration_type
                else:
                    composite_query["$or"] = [{"integration_type": None}, {"integration_type": ""}, {"integration_type": {"$exists": False}}]
                
                existing = await db.integrators.find_one(composite_query, {"_id": 0})
                
                if existing and mode == "insert_only":
                    errors.append(ImportError(row=row_num, column='Nombre/Tipo Int.',
                        value=f'{name} / {integration_type or "N/A"}',
                        error_type='duplicate',
                        message='Ya existe un integrador con este nombre y tipo de integración',
                        suggested_action='Use el modo "Upsert" para actualizar registros existentes'))
                    skipped_count += 1
                elif existing:
                    # UPSERT: update basic data + overwrite certifications from file
                    update_data = {
                        "integrator_type": integrator_type,
                        "app_name": app_name,
                        "integration_modality": integration_modality,
                        "integrator_status": integrator_status,
                    }
                    if integration_type:
                        update_data["integration_type"] = integration_type
                    if gestor:
                        update_data["gestor"] = gestor
                    if implementador_name:
                        update_data["implementador"] = implementador_name
                        update_data["implementador_user_id"] = implementador_user_id
                    if ticket_number:
                        update_data["ticket_number"] = ticket_number
                    if categoria:
                        update_data["categoria"] = categoria
                    if last_contact_date:
                        update_data["last_contact_date"] = last_contact_date
                    if email:
                        update_data["email"] = email
                    if coordinador_name:
                        update_data["coordinador"] = coordinador_name
                        update_data["coordinador_user_id"] = coordinador_user_id
                    if project_start_date:
                        update_data["project_start_date"] = project_start_date
                    if project_name:
                        update_data["project_name"] = project_name
                    if observations:
                        update_data["observations"] = observations
                    if principal_contact_name:
                        update_data["principal_contact_name"] = principal_contact_name
                    if principal_contact_phone:
                        update_data["principal_contact_phone"] = principal_contact_phone
                    if principal_contact_email:
                        update_data["principal_contact_email"] = principal_contact_email
                    if interface_negotiation:
                        update_data["interface_negotiation"] = interface_negotiation
                    
                    # Merge certs: existing certs as base, overlay with file data
                    if product_columns:
                        existing_certs = existing.get("certifications", {})
                        merged_certs = {**existing_certs, **row_certs}
                        update_data["certifications"] = merged_certs
                        cert_updates_count += len(row_certs)
                    
                    await db.integrators.update_one(
                        {"integrator_id": existing["integrator_id"]},
                        {"$set": update_data}
                    )
                    updated_count += 1
                else:
                    # CREATE new integrator with full certifications
                    new_integrator = Integrator(
                        name=name,
                        integrator_type=integrator_type,
                        integration_type=integration_type or None,
                        app_name=app_name,
                        integration_modality=integration_modality,
                        integrator_status=integrator_status,
                        gestor=gestor or None,
                        categoria=categoria or None,
                        implementador=implementador_name,
                        implementador_user_id=implementador_user_id,
                        ticket_number=ticket_number or None,
                        last_contact_date=last_contact_date,
                        email=email or None,
                        coordinador=coordinador_name,
                        coordinador_user_id=coordinador_user_id,
                        project_start_date=project_start_date,
                        project_name=project_name or None,
                        observations=observations or None,
                        principal_contact_name=principal_contact_name or None,
                        principal_contact_phone=principal_contact_phone or None,
                        principal_contact_email=principal_contact_email or None,
                        interface_negotiation=interface_negotiation,
                        certifications=full_certs
                    )
                    doc = new_integrator.model_dump()
                    doc['created_at'] = doc['created_at'].isoformat()
                    await db.integrators.insert_one(doc)
                    success_count += 1
                    cert_updates_count += len(full_certs)
                
            except Exception as e:
                errors.append(ImportError(row=row_num, column='General', value=None,
                    error_type='format', message=f'Error al procesar fila: {str(e)}',
                    suggested_action='Verifique el formato de los datos en esta fila'))
                skipped_count += 1
        
        # Determine status
        total_ok = success_count + updated_count
        if total_ok == total_rows:
            result_status = 'success'
            parts = []
            if success_count > 0:
                parts.append(f'{success_count} creados')
            if updated_count > 0:
                parts.append(f'{updated_count} actualizados')
            if cert_updates_count > 0:
                parts.append(f'{cert_updates_count} certificaciones procesadas')
            message = f'Importación exitosa: {", ".join(parts)}'
        elif total_ok > 0:
            result_status = 'partial'
            parts = []
            if success_count > 0:
                parts.append(f'{success_count} creados')
            if updated_count > 0:
                parts.append(f'{updated_count} actualizados')
            if cert_updates_count > 0:
                parts.append(f'{cert_updates_count} certificaciones')
            message = f'Importación parcial: {", ".join(parts)}, {skipped_count} con errores'
        else:
            result_status = 'error'
            message = f'Importación fallida: {skipped_count} registros con errores'
        
        return ImportResult(
            status=result_status,
            total_processed=total_rows,
            success_count=success_count,
            updated_count=updated_count,
            cert_updates_count=cert_updates_count,
            error_count=len(errors),
            skipped_count=skipped_count,
            errors=errors,
            message=message
        )
        
    except Exception as e:
        return ImportResult(
            status='error', total_processed=0, success_count=0, updated_count=0,
            cert_updates_count=0, error_count=1, skipped_count=0,
            errors=[ImportError(row=0, column='archivo', value=file.filename,
                error_type='format', message=f'Error al procesar archivo: {str(e)}',
                suggested_action='Verifique que el archivo no esté dañado y tenga el formato correcto')],
            message='Error crítico: No se pudo procesar el archivo'
        )



class NotifyProjectPayload(BaseModel):
    custom_message: Optional[str] = None
    additional_recipients: Optional[str] = None


@router.post("/integrators/{integrator_id}/notify-new-project")
async def notify_new_integration_project(
    integrator_id: str,
    payload: Optional[NotifyProjectPayload] = None,
    authorization: Optional[str] = Header(None),
    x_custom_message: Optional[str] = Header(None),
    x_additional_recipients: Optional[str] = Header(None)
):
    """Envía notificación de nuevo proyecto de integración al Gerente de Implementación"""
    current_user = await get_current_user(authorization)

    # El mensaje personalizado y los CC ahora viajan en el BODY (los headers HTTP
    # rompían con saltos de línea/acentos y truncaban el texto). Se mantiene
    # compatibilidad con los headers legacy por si algún cliente antiguo los usa.
    payload = payload or NotifyProjectPayload()
    custom_message = (payload.custom_message if payload.custom_message is not None else x_custom_message) or ""
    custom_message = custom_message.strip()
    if len(custom_message) > 300:
        raise HTTPException(status_code=400, detail="El mensaje no puede exceder los 300 caracteres")
    additional_recipients = (payload.additional_recipients if payload.additional_recipients is not None else x_additional_recipients) or ""

    integrator = await db.integrators.find_one({"integrator_id": integrator_id}, {"_id": 0})
    if not integrator:
        raise HTTPException(status_code=404, detail="Integrador no encontrado")
    
    # Obtener email del Gerente de Implementación desde configuración
    config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
    impl_manager_email = config.get("implementation_manager_email") if config else None
    if not impl_manager_email:
        raise HTTPException(status_code=400, detail="No hay correo de Gerente de Implementación configurado en Configuración > Correos de Notificación")
    
    # Obtener primer contacto técnico como responsable
    contacts = integrator.get("contacts", [])
    first_contact = contacts[0] if contacts else {}
    
    INTEGRATION_TYPE_MAP = {
        'CR': 'CR — Caja Registradora', 'LP': 'LP — Link de Pago',
        'PG': 'PG — Payment Gateway', 'MP': 'MP — Android (Mobile POS)', 'TK': 'TK — Tokenizador'
    }
    
    # Bloque "Información adicional:" — se inyecta SIEMPRE justo encima de la firma
    # institucional (ver prepend_signature_html), independientemente de si la
    # plantilla referencia o no la variable {comentarios_personalizados}.
    import html as _html
    info_block = ""
    if custom_message:
        safe_msg = _html.escape(custom_message)
        info_block = (
            '<div style="margin:18px 0 8px 0;padding-top:12px;border-top:1px solid #e2e8f0;">'
            '<p style="font-weight:bold;color:#1e293b;margin:0 0 4px 0;">Información adicional:</p>'
            f'<p style="color:#334155;margin:0;white-space:pre-wrap;">{safe_msg}</p>'
            '</div>'
        )
    
    # Variables de la plantilla (incluye aliases para compatibilidad con plantillas editadas)
    variables = {
        "nombre_integrador": integrator.get("name", ""),
        "Integrador": integrator.get("name", ""),
        "tipo_integracion": INTEGRATION_TYPE_MAP.get(integrator.get("integration_type", ""), integrator.get("integration_type", "")),
        "Tipo_Integración": INTEGRATION_TYPE_MAP.get(integrator.get("integration_type", ""), integrator.get("integration_type", "")),
        "Tipo_integrador": INTEGRATION_TYPE_MAP.get(integrator.get("integration_type", ""), integrator.get("integration_type", "")),
        "nombre_aplicativo": integrator.get("app_name", ""),
        "Aplicativo_Integracion": integrator.get("app_name", ""),
        "nombre_responsable": first_contact.get("name", "No asignado"),
        "email_responsable": first_contact.get("email", "No asignado"),
        "telefono_responsable": first_contact.get("phone", "No asignado"),
        "comentarios_personalizados": info_block,
        "usuario_creador": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "Nombre_Ejecutivo": f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
        "fecha_sistema": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"),
        # Productos a Certificar (texto libre del Proyecto de Integración).
        "Productos_Certificar_Integrador": integrator.get("productos_certificar", "") or "",
        "productos_certificar_integrador": integrator.get("productos_certificar", "") or "",
        # Productos del nuevo proyecto (para la plantilla de creación de Nuevos Proyectos).
        "Productos_nuevos": integrator.get("productos_certificar", "") or "",
    }

    # Correo Adicional Eventual: CC volátil para este envío específico. Se toma
    # del campo del proyecto (correo_eventual) y de los destinatarios ad-hoc del
    # modal (body). No altera el correo maestro del integrador.
    extra_cc: list = []
    ev = (integrator.get("correo_eventual") or "").strip()
    if ev and "@" in ev:
        extra_cc.append(ev)
    if additional_recipients:
        extra_cc += [e.strip() for e in additional_recipients.split(",") if e.strip() and "@" in e.strip()]
    # Dedupe preservando orden.
    extra_cc = list(dict.fromkeys(extra_cc))

    # Motor dinámico "Configuración de otras Acciones" (con fallback legacy)
    try:
        from services.other_actions_engine import dispatch_other_action
        _dyn = await dispatch_other_action(
            "new_integration_project", variables, current_user=current_user,
            fallback_subject=f"Nuevo Proyecto de Integracion — {integrator.get('name','')}",
            extra_cc=extra_cc,
            prepend_signature_html=info_block or None,
        )
        if _dyn.get("dispatched"):
            # Auditoría en la bitácora del proyecto (correo eventual incluido).
            try:
                await db.bitacora.insert_one({
                    "entry_id": f"bit_{datetime.now(timezone.utc).timestamp()}",
                    "integrator_id": integrator_id,
                    "action": "new_integration_project_notify",
                    "sent_to": _dyn.get("recipients", []),
                    "cc": extra_cc,
                    "productos_certificar": integrator.get("productos_certificar", "") or "",
                    "executed_by": current_user.get("email"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass
            if _dyn.get("disabled"):
                return {"message": "Notificación desactivada en Configuración de otras Acciones", "sent_to": []}
            return {
                "message": f"Notificación enviada a {_dyn.get('sent_count', 0)} destinatario(s) (Configuración de otras Acciones)"
                + (f" + {len(extra_cc)} en copia" if extra_cc else ""),
                "sent_to": _dyn.get("recipients", []),
                "cc": extra_cc,
            }
    except Exception as e:
        logging.error(f"[Integradores] motor dinámico de otras acciones falló: {e}")

    # Obtener plantilla (puede estar personalizada en DB o usar la default)
    template = await db.email_templates.find_one({"template_id": "new_integration_project"}, {"_id": 0})
    if not template:
        from routes.seed_and_templates import PROJECT_EMAIL_TEMPLATES
        template = PROJECT_EMAIL_TEMPLATES.get("new_integration_project")
    
    if not template:
        raise HTTPException(status_code=500, detail="Plantilla 'new_integration_project' no encontrada")
    
    # Renderizar - soportar tanto {var} como {{var}}
    subject = template["subject"]
    body = template["body_html"]
    for key, value in variables.items():
        val = str(value)
        body = body.replace(f"{{{{{key}}}}}", val)  # {{var}} primero
        body = body.replace(f"{{{key}}}", val)       # {var} después
        subject = subject.replace(f"{{{{{key}}}}}", val)
        subject = subject.replace(f"{{{key}}}", val)
    
    # Destinatarios (fallback legacy)
    recipients = [impl_manager_email]
    cc_list = list(extra_cc)
    
    try:
        from services.email_service import send_email, resolve_sender_for_area
        await send_email(
            to=recipients,
            subject=subject,
            html=body,
            action="new_integration_project",
            quote_id=integrator_id,
            sender=await resolve_sender_for_area("integradores"),
            cc=cc_list or None,
        )
        return {"message": f"Notificacion enviada a {impl_manager_email}" + (f" y {len(cc_list)} destinatario(s) en copia" if cc_list else ""), "sent_to": recipients, "cc": cc_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")
