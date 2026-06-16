"""Route module: attachments.py"""
# ruff: noqa: F403, F405
from fastapi import APIRouter, HTTPException, Header, Response, status, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta
import uuid
import logging
import io
import os

from config import db, get_current_user, require_permission, get_resend_api_key, hash_password, verify_password, UPLOADS_DIR, SENDER_EMAIL, RESEND_AVAILABLE, generate_quote_number, append_vpos_static_pages, append_pg_static_pages, render_email_template
from services.pdf_storage import save_pdf_dual, get_pdf_from_storage
from models import *
from services.pdf_generator import TemplateQuotePDFRequest, DynamicQuotePDFGenerator

router = APIRouter()

# ==================== ANEXOS (ATTACHMENTS) ENDPOINTS ====================

async def _require_quote_attachment_access(authorization: Optional[str], level: str = "read"):
    """RBAC para anexos de COTIZACIONES VIGENTES (menú Cotizaciones).

    Estos anexos pertenecen a cotizaciones aún activas y son INDEPENDIENTES de la
    funcionalidad de Anexos del Histórico de Cotizaciones (que se gobierna por el
    módulo `quote_history` en los endpoints /quote-history/...). El acceso aquí
    sigue el acceso del usuario a Cotizaciones:
      - read:  Admin, o `cotizaciones` >= Consulta, o permiso especial cotizaciones:* (Equipos/Reparaciones/Impl).
      - edit:  Admin, o `cotizaciones` = Edición, o permiso especial cotizaciones:*.
    """
    user = await get_current_user(authorization)
    if user.get("role") == "admin":
        return user
    perms = user.get("permissions", {}) or {}
    cot = perms.get("cotizaciones", "none")
    specials = user.get("special_permissions", []) or []
    has_cot_special = any(str(s).startswith("cotizaciones:") for s in specials)
    if level == "edit":
        if cot == "edit" or has_cot_special:
            return user
    else:
        if cot in ("read", "edit") or has_cot_special:
            return user
    raise HTTPException(status_code=403, detail="No tiene acceso a los anexos de esta cotización")


@router.get("/quotes/{quote_id}/attachments")
async def get_quote_attachments(quote_id: str, authorization: Optional[str] = Header(None)):
    """Obtiene todos los anexos de una cotización.

    RBAC: anexos de Cotizaciones vigentes (independiente del Histórico). Exige
    acceso de Consulta a `cotizaciones` (o especial Equipos/Reparaciones, o Admin)."""
    await _require_quote_attachment_access(authorization, "read")
    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0, "attachments": 1, "quote_number": 1})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    return {
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "attachments": quote.get("attachments", [])
    }

@router.post("/quotes/{quote_id}/attachments")
async def upload_quote_attachment(
    quote_id: str,
    file: UploadFile = File(...),
    category: str = Form(...),
    context: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None)
):
    """Sube un anexo a una cotización.

    RBAC: anexos de Cotizaciones vigentes (independiente del Histórico).
      - La carga (POST) exige nivel de Edición en `cotizaciones` (o especial
        Equipos/Reparaciones, o Admin). Se valida en backend (no solo UI).
      - Excepción: el flujo de Taller → "Reparación completada" envía
        context='taller_repair'; ese caso mantiene su comportamiento previo
        (cualquier usuario autenticado) para no bloquear la operación de taller.
    """
    if context == "taller_repair":
        current_user = await get_current_user(authorization)
    else:
        current_user = await _require_quote_attachment_access(authorization, "edit")

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoría inválida. Opciones: {', '.join(ATTACHMENT_CATEGORIES)}")
    
    # Crear directorio de anexos si no existe
    attachments_dir = UPLOADS_DIR / "attachments" / quote_id
    attachments_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre con nomenclatura: COT-AAAA-MM-NNN-SEDE_Categoria.ext
    attachment_id = f"att_{uuid.uuid4().hex[:12]}"
    file_ext = Path(file.filename).suffix if file.filename else ".pdf"
    quote_num = quote.get("quote_number", quote_id)
    # Map category to short name for filename
    category_filename_map = {
        "Cotización": "Cotizacion",
        "Orden de Compra": "OrdenCompra",
        "Factura": "Factura",
        "Pagos": "Pago",
        "Otros": "Otros"
    }
    cat_short = category_filename_map.get(category, category.replace(" ", ""))
    # Count existing in this category to add suffix if multiple
    existing_in_cat = len([a for a in quote.get("attachments", []) if a.get("category") == category])
    suffix = f"_{existing_in_cat + 1}" if existing_in_cat > 0 or category in ("Pagos", "Otros") else ""
    display_filename = f"{quote_num}_{cat_short}{suffix}{file_ext}"
    safe_filename = f"{attachment_id}{file_ext}"
    file_path = attachments_dir / safe_filename
    
    # Guardar archivo (FS + Object Storage)
    content = await file.read()
    relative_key = f"attachments/{quote_id}/{safe_filename}"
    save_pdf_dual(file_path, content, relative_key)
    
    attachment = {
        "attachment_id": attachment_id,
        "category": category,
        "filename": display_filename,
        "url": f"/uploads/attachments/{quote_id}/{safe_filename}",
        "uploaded_by": current_user.get("email", "unknown"),
        "uploaded_by_name": current_user.get("full_name", current_user.get("email", "unknown")),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream"
    }
    
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$push": {"attachments": attachment}}
    )
    
    return {"message": "Anexo subido exitosamente", "attachment": attachment}

@router.delete("/quotes/{quote_id}/attachments/{attachment_id}")
async def delete_quote_attachment(quote_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Elimina un anexo de una cotización.

    RBAC (Matriz estricta de Anexos): la eliminación queda restringida
    EXCLUSIVAMENTE al rol Administrador (control crítico, no asignable por
    perfil). Se valida en backend además de ocultar el ícono en la UI.
    """
    user = await get_current_user(authorization)
    if (user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo el Administrador puede eliminar anexos")

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    
    # Buscar el anexo
    attachment = next((a for a in quote.get("attachments", []) if a["attachment_id"] == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")
    
    # Eliminar archivo físico
    url_path = attachment["url"].replace("/uploads/", "")
    file_path = UPLOADS_DIR / url_path
    if file_path.exists():
        file_path.unlink()
    
    # Eliminar de la BD
    await db.quotes.update_one(
        {"quote_id": quote_id},
        {"$pull": {"attachments": {"attachment_id": attachment_id}}}
    )
    
    return {"message": "Anexo eliminado exitosamente"}

@router.get("/quotes/{quote_id}/attachments/{attachment_id}/download")
async def download_quote_attachment(quote_id: str, attachment_id: str, authorization: Optional[str] = Header(None)):
    """Descarga un anexo de una cotización.

    Estrategia optimizada para minimizar latencia:
      1) Filesystem local primero (~10ms, sirve la mayoría de casos en
         Preview y los recientes en Producción).
      2) Object Storage solo como fallback (~500-2000ms de red) para los
         anexos viejos que ya no están en el FS efímero del pod tras un deploy.

    RBAC: anexos de Cotizaciones vigentes (independiente del Histórico). Exige
    acceso de Consulta a `cotizaciones` (o especial Equipos/Reparaciones, o Admin).
    """
    await _require_quote_attachment_access(authorization, "read")

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    attachment = next((a for a in quote.get("attachments", []) if a["attachment_id"] == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Anexo no encontrado")

    url_path = (attachment.get("url") or "").replace("/uploads/", "")
    ctype = attachment.get("content_type", "application/octet-stream")
    filename = attachment.get("filename", attachment_id)

    # 1) FS local primero — instantáneo cuando está disponible.
    file_path = UPLOADS_DIR / url_path
    if file_path.exists():
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type=ctype,
        )

    # 2) Fallback: Object Storage (persistente cross-deploy).
    obj = get_pdf_from_storage(url_path)
    if obj:
        content, stored_ctype = obj
        return StreamingResponse(
            io.BytesIO(content),
            media_type=stored_ctype or ctype,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

async def generate_quote_pdf_buffer(quote: dict, client: dict) -> io.BytesIO:
    """Genera un PDF de cotización y lo retorna como buffer"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    title_style = styles['Title']
    title_style.fontSize = 16
    elements.append(Paragraph("<b>COTIZACIÓN - Merchant Server</b>", title_style))
    elements.append(Spacer(1, 0.15*inch))
    
    quote_type_names = {
        'VPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'VPOS_MPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'GATEWAY': 'Payment Gateway',
        'MPOS': 'VPOS/MPOS (Cajas y Tablet)',
        'LINK': 'Link de Pago'
    }
    
    client_name = client.get('fantasy_name') or client.get('legal_name') or 'Cliente'
    
    info_data = [
        ["Cotización #:", quote.get('quote_number', 'N/A')],
        ["Fecha:", datetime.now().strftime("%d/%m/%Y")],
        ["Cliente:", client_name],
        ["RIF:", client.get('rif', 'N/A')],
        ["Tipo de Servicio:", quote_type_names.get(quote.get('quote_type'), quote.get('quote_type', 'N/A'))],
    ]
    
    if quote.get('integrator_name'):
        info_data.append(["Integrador:", f"{quote.get('integrator_name')} ({quote.get('integrator_app_name', '')})"])
    if quote.get('pinpad_model'):
        info_data.append(["Modelo Pinpad:", quote.get('pinpad_model')])
    if quote.get('sponsor_bank_name'):
        info_data.append(["Patrocinador:", quote.get('sponsor_bank_name')])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Servicios
    if quote.get('services'):
        elements.append(Paragraph("<b>Servicios</b>", styles['Heading2']))
        svc_data = [["Concepto", "Cantidad", "Precio USD", "Total USD"]]
        for svc in quote['services']:
            total = svc.get('quantity', 1) * svc.get('price_usd', 0)
            svc_data.append([
                svc.get('item_name', ''),
                str(svc.get('quantity', 1)),
                f"${svc.get('price_usd', 0):.2f}",
                f"${total:.2f}"
            ])
        svc_table = Table(svc_data, colWidths=[3.5*inch, 1*inch, 1*inch, 1*inch])
        svc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.4, 0.7)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(svc_table)
        elements.append(Spacer(1, 0.15*inch))
    
    # PG Setup Items
    if quote.get('pg_setup_items'):
        elements.append(Paragraph("<b>Payment Gateway - Inversión en Setup / Arranque</b>", styles['Heading2']))
        pg_data = [["Concepto", "Costo ($)", "Banco", "Observación"]]
        pg_total = 0
        for item in quote['pg_setup_items']:
            costo = item.get('costo', 0)
            pg_total += costo
            pg_data.append([
                item.get('concepto', ''),
                f"${costo:.2f}",
                item.get('banco', 'N/A'),
                item.get('observacion', '')
            ])
        pg_data.append(["Total Setup:", f"${pg_total:.2f}", "", ""])
        pg_table = Table(pg_data, colWidths=[2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
        pg_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.05, 0.55, 0.35)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.9, 0.95, 0.9)),
        ]))
        elements.append(pg_table)
        elements.append(Spacer(1, 0.15*inch))
    
    # PG Recurring Costs - Full table
    if quote.get('pg_recurring_cost'):
        rc = quote['pg_recurring_cost']
        elements.append(Paragraph("<b>Costos Recurrentes Mensuales</b>", styles['Heading2']))
        num_products = rc.get('num_products', 0)
        if num_products:
            elements.append(Paragraph(f"Calculado para <b>{num_products}</b> medio(s) de pago", styles['Normal']))
            elements.append(Spacer(1, 0.05*inch))
        rc_data = [["Rango", "Transacciones", "Total $ Base", "Precio Tope por Rango"]]
        table_rows = rc.get('table', [])
        if table_rows:
            for row in table_rows:
                rc_data.append([
                    str(row.get('rango', '')),
                    row.get('label', 'N/A'),
                    f"${row['base']:.2f}" if row.get('base') is not None else "Negociable",
                    f"${row['tope']:.6f}" if row.get('tope') is not None else "N/A"
                ])
        else:
            # Fallback for old single-row format
            rc_data.append([
                "1",
                rc.get('rango_label', 'N/A'),
                f"${rc.get('base', 0):.2f}" if rc.get('base') is not None else "Negociable",
                f"${rc.get('tope', 0):.6f}" if rc.get('tope') else "N/A"
            ])
        rc_table = Table(rc_data, colWidths=[0.6*inch, 1.8*inch, 1.5*inch, 1.8*inch])
        rc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.15, 0.35, 0.7)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 1)]),
        ]))
        elements.append(rc_table)
        elements.append(Spacer(1, 0.15*inch))

    # Total
    elements.append(Spacer(1, 0.2*inch))
    total_data = [
        ["Total USD:", f"${quote.get('total_usd', 0):.2f}"]
    ]
    total_table = Table(total_data, colWidths=[5*inch, 1.5*inch])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
    ]))
    elements.append(total_table)
    
    # Footer
    elements.append(Spacer(1, 0.3*inch))
    footer_style = styles['Normal']
    footer_style.fontSize = 8
    footer_style.textColor = colors.grey
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    
    # Agregar páginas estáticas según tipo de cotización
    quote_type = quote.get('quote_type', '')
    if quote_type == 'GATEWAY':
        buffer = append_pg_static_pages(buffer)
    elif quote_type not in ('GATEWAY',):
        buffer = append_vpos_static_pages(buffer)
    
    return buffer

