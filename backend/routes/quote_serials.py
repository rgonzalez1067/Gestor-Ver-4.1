"""Endpoints de inventario/seriales vinculados a cotizaciones.

Incluye:
 - Catálogo de modelos Pinpad/POS físicos.
 - Búsqueda de seriales por cliente/RIF (historial).
 - Búsqueda de equipos para implementación (Fast Track / VPOS-MPOS).
 - Prerregistro (preasignación) de seriales Fast Track.

Extraído de `quote_actions.py` para separar la lógica de hardware de la de workflow
de la cotización.
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging

from config import db, get_current_user, render_email_template
from services.email_service import send_email
from services.notification_engine import try_dispatch as _ne_try_dispatch
from routes.quote_helpers import get_email_template


router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== PYME EXTENDED FLOW: PINPAD MODELS & INVENTORY SERIALS ====================

@router.get("/quotes/{quote_id}/pinpad-models")
async def get_pinpad_models(quote_id: str, authorization: Optional[str] = Header(None)):
    """Retorna modelos de POS/Pinpad físicos (excluyendo servicios como licencias/garantías) para selección en flujo PYME."""
    await get_current_user(authorization)
    models = []
    async for hw in db.hardware.find(
        {"type": {"$in": ["POS", "Pinpad"]}, "asset_type": {"$ne": "Servicio"}},
        {"_id": 0}
    ):
        models.append({
            "hardware_id": hw.get("hardware_id", ""),
            "name": hw.get("name", ""),
            "type": hw.get("type", ""),
        })
    return {"models": models}


@router.get("/quotes/{quote_id}/inventory-serials")
async def get_inventory_serials(quote_id: str, model_id: str, authorization: Optional[str] = Header(None)):
    """Busca seriales de salidas de inventario por RIF del cliente, modelo y últimos 15 días."""
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    if not client:
        return {"serials": [], "client_rif": ""}

    client_rif = (client.get("rif", "") or "").replace("-", "").replace(" ", "").upper().strip()
    if not client_rif:
        return {"serials": [], "client_rif": ""}

    # Buscar todos los client_id con el mismo RIF normalizado
    all_client_ids = []
    async for cl in db.clients.find({}, {"_id": 0, "client_id": 1, "rif": 1}):
        cl_rif = (cl.get("rif", "") or "").replace("-", "").replace(" ", "").upper().strip()
        if cl_rif == client_rif:
            all_client_ids.append(cl["client_id"])

    # Fecha límite: últimos 15 días
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()

    # Buscar salidas de inventario que coincidan
    serials_found = []
    query = {
        "movement_type": "salida",
        "item_id": model_id,
        "created_at": {"$gte": cutoff_date},
        "$or": [
            {"client_id": {"$in": all_client_ids}},
        ],
        "serials": {"$exists": True, "$ne": []},
    }
    # También buscar por nombre de cliente si no hay client_id en el movimiento
    client_names = set()
    async for cl in db.clients.find({"client_id": {"$in": all_client_ids}}, {"_id": 0, "legal_name": 1, "fantasy_name": 1}):
        if cl.get("legal_name"):
            client_names.add(cl["legal_name"])
        if cl.get("fantasy_name"):
            client_names.add(cl["fantasy_name"])

    if client_names:
        query["$or"].append({"client_name": {"$in": list(client_names)}})

    async for mov in db.inventory_movements.find(query, {"_id": 0}):
        for serial in mov.get("serials", []):
            serials_found.append({
                "serial": serial,
                "modelo": mov.get("item_name", ""),
                "movement_id": mov.get("movement_id", ""),
                "warehouse": mov.get("warehouse_id", ""),
                "date": mov.get("created_at", ""),
                "reference": mov.get("reference", ""),
            })

    return {"serials": serials_found, "client_rif": client_rif}


# ==================== EQUIPMENT SEARCH FOR IMPLEMENTATION ====================

@router.get("/quotes/{quote_id}/equipment-for-implementation")
async def get_equipment_for_implementation(quote_id: str, project_type: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Busca equipos para vincular al proyecto de implementación.

    Lógica de búsqueda según tipo de proyecto:
    - POS Fast Track: Busca seriales en taller_equipos por quote_id (sin filtro de estatus)
    - VPOS/MPOS: Busca equipos entregados al cliente por RIF normalizado con estatus 'Entregado'
    - Sin tipo / otro: Combinación de ambas búsquedas
    """
    await get_current_user(authorization)

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")

    client_id = quote.get("client_id")
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) if client_id else None
    client_rif = client.get("rif", "") if client else ""

    quote_equipment = []
    rif_equipment = []

    if project_type == "pos_fast_track":
        cursor = db.taller_equipos.find({"quote_id": quote_id}, {"_id": 0})
        async for eq in cursor:
            quote_equipment.append({
                "equipo_id": eq.get("equipo_id", eq.get("taller_equipo_id", "")),
                "modelo": eq.get("modelo", ""),
                "serial": eq.get("serial", ""),
                "marca": eq.get("marca", ""),
                "estatus": eq.get("estatus", ""),
                "source": "cotizacion",
            })

    elif project_type == "vpos_mpos":
        if client_rif:
            normalized_rif = client_rif.replace("-", "").replace(" ", "").upper().strip()
            all_client_ids = []
            async for cl in db.clients.find({}, {"_id": 0, "client_id": 1, "rif": 1}):
                cl_rif = (cl.get("rif", "") or "").replace("-", "").replace(" ", "").upper().strip()
                if cl_rif == normalized_rif:
                    all_client_ids.append(cl["client_id"])

            if all_client_ids:
                cursor = db.taller_equipos.find({
                    "client_id": {"$in": all_client_ids},
                    "estatus": "Entregado",
                }, {"_id": 0})
                async for eq in cursor:
                    rif_equipment.append({
                        "equipo_id": eq.get("equipo_id", eq.get("taller_equipo_id", "")),
                        "modelo": eq.get("modelo", ""),
                        "serial": eq.get("serial", ""),
                        "marca": eq.get("marca", ""),
                        "estatus": eq.get("estatus", ""),
                        "quote_number": eq.get("quote_number", ""),
                        "source": "cliente_rif",
                    })

                try:
                    ne_cursor = db.notas_entrega.find({
                        "client_id": {"$in": all_client_ids},
                        "estatus": "Entregado",
                    }, {"_id": 0})
                    async for ne in ne_cursor:
                        for eq in ne.get("equipos", []):
                            eq_id = eq.get("equipo_id", eq.get("taller_equipo_id", ""))
                            if not any(r["equipo_id"] == eq_id for r in rif_equipment if eq_id):
                                rif_equipment.append({
                                    "equipo_id": eq_id,
                                    "modelo": eq.get("modelo", ""),
                                    "serial": eq.get("serial", ""),
                                    "marca": eq.get("marca", ""),
                                    "estatus": "Entregado",
                                    "quote_number": ne.get("quote_number", ""),
                                    "source": "nota_entrega",
                                })
                except Exception:
                    pass

    else:
        # Fallback genérico: buscar ambos tipos
        cursor = db.taller_equipos.find({"quote_id": quote_id}, {"_id": 0})
        async for eq in cursor:
            quote_equipment.append({
                "equipo_id": eq.get("equipo_id", eq.get("taller_equipo_id", "")),
                "modelo": eq.get("modelo", ""),
                "serial": eq.get("serial", ""),
                "marca": eq.get("marca", ""),
                "estatus": eq.get("estatus", ""),
                "source": "cotizacion",
            })

        if client_rif:
            client_ids = []
            async for cl in db.clients.find({"rif": client_rif}, {"_id": 0, "client_id": 1}):
                client_ids.append(cl["client_id"])

            if client_ids:
                cursor2 = db.taller_equipos.find({
                    "client_id": {"$in": client_ids},
                    "estatus": "Entregado",
                    "quote_id": {"$ne": quote_id},
                }, {"_id": 0})
                async for eq in cursor2:
                    rif_equipment.append({
                        "equipo_id": eq.get("equipo_id", eq.get("taller_equipo_id", "")),
                        "modelo": eq.get("modelo", ""),
                        "serial": eq.get("serial", ""),
                        "marca": eq.get("marca", ""),
                        "estatus": eq.get("estatus", ""),
                        "quote_number": eq.get("quote_number", ""),
                        "source": "cliente_rif",
                    })

    return {
        "quote_equipment": quote_equipment,
        "rif_equipment": rif_equipment,
        "client_rif": client_rif,
        "total": len(quote_equipment) + len(rif_equipment),
    }


# ==================== PRERREGISTRO DE SERIALES (Fast Track) ====================

@router.get("/inventory/{warehouse_id}/available-serials/{item_id}")
async def get_available_serials(warehouse_id: str, item_id: str, authorization: Optional[str] = Header(None)):
    """Retorna seriales disponibles para un ítem, excluyendo preasignados/asignados."""
    await get_current_user(authorization)

    movements = await db.inventory_movements.find(
        {"warehouse_id": warehouse_id, "item_id": item_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(2000)

    serials_in_stock = []
    serial_dates = {}
    for m in movements:
        if m.get("certification_status") == "precarga":
            continue
        sign = 1 if m["movement_type"] in ("entrada", "transferencia_entrada") else -1
        acq_date = m.get("acquisition_date") or m.get("created_at", "")
        if m.get("serials"):
            if sign > 0:
                serials_in_stock.extend(m["serials"])
                for s in m["serials"]:
                    serial_dates[s] = acq_date
            else:
                for s in m["serials"]:
                    if s in serials_in_stock:
                        serials_in_stock.remove(s)
                    serial_dates.pop(s, None)

    # Excluir seriales ya preasignados o asignados
    blocked = await db.serial_assignments.find(
        {"status": {"$in": ["preasignado", "asignado"]}},
        {"_id": 0, "serial": 1}
    ).to_list(2000)
    blocked_set = {b["serial"] for b in blocked}

    available = [s for s in serials_in_stock if s not in blocked_set]
    # Ordenar FIFO
    available.sort(key=lambda s: serial_dates.get(s, "9999"))

    return {
        "available": [{"serial": s, "acquisition_date": serial_dates.get(s, "")} for s in available],
        "total_available": len(available),
    }


@router.get("/quotes/{quote_id}/preassigned-serials")
async def get_preassigned_serials(quote_id: str, authorization: Optional[str] = Header(None)):
    """Retorna seriales preasignados para una cotización."""
    await get_current_user(authorization)
    assignments = await db.serial_assignments.find(
        {"quote_id": quote_id}, {"_id": 0}
    ).to_list(500)
    return {"assignments": assignments}


@router.post("/quotes/{quote_id}/preassign-serials")
async def preassign_serials(quote_id: str, request: dict, authorization: Optional[str] = Header(None)):
    """Prerregistro de seriales: reserva equipos para una cotización Fast Track."""
    current_user = await get_current_user(authorization)
    user_name = f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip()
    user_email = current_user.get("email", "")

    quote = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0})
    if not quote:
        raise HTTPException(status_code=404, detail="Cotización no encontrada")
    if quote.get("quote_category") != "fast_track":
        raise HTTPException(status_code=400, detail="Solo cotizaciones Fast Track soportan prerregistro de seriales")

    selected_serials = request.get("serials", [])
    warehouse_id = request.get("warehouse_id", "")
    item_id = request.get("item_id", "")
    item_name = request.get("item_name", "")
    custom_message = (request.get("custom_message") or "").strip() or None
    cc_emails = request.get("cc_emails") or []

    if not selected_serials or not warehouse_id or not item_id:
        raise HTTPException(status_code=400, detail="Faltan datos: serials, warehouse_id, item_id")

    # Validar que cantidad coincide con demanda de la cotización
    ft_items = quote.get("ft_equipment_items", [])
    required_qty = 0
    model_name = ""
    for fi in ft_items:
        if fi.get("hardware_id") == item_id or fi.get("name") == item_name:
            required_qty = fi.get("quantity", 0)
            model_name = fi.get("name", item_name)
            break

    if required_qty == 0:
        required_qty = sum(fi.get("quantity", 0) for fi in ft_items)
        model_name = ft_items[0].get("name", item_name) if ft_items else item_name

    if len(selected_serials) != required_qty:
        raise HTTPException(
            status_code=400,
            detail=f"Debe seleccionar exactamente {required_qty} seriales. Seleccionados: {len(selected_serials)}"
        )

    # Validar que los seriales no están ya preasignados/asignados
    existing = await db.serial_assignments.find(
        {"serial": {"$in": selected_serials}, "status": {"$in": ["preasignado", "asignado"]}},
        {"_id": 0, "serial": 1, "quote_id": 1}
    ).to_list(500)
    if existing:
        conflicting = [e["serial"] for e in existing]
        raise HTTPException(status_code=409, detail=f"Seriales ya reservados: {', '.join(conflicting)}")

    # Limpiar preasignaciones anteriores de esta cotización (permite re-prerregistrar)
    await db.serial_assignments.delete_many({"quote_id": quote_id, "status": "preasignado"})

    # Obtener datos del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = (client.get("fantasy_name") or client.get("legal_name")) if client else "Cliente"
    client_rif = client.get("rif", "N/A") if client else "N/A"

    # Crear asignaciones
    now = datetime.now(timezone.utc).isoformat()
    assignments = []
    for serial in selected_serials:
        doc = {
            "assignment_id": f"sa_{uuid.uuid4().hex[:12]}",
            "serial": serial,
            "item_id": item_id,
            "item_name": model_name,
            "warehouse_id": warehouse_id,
            "quote_id": quote_id,
            "quote_number": quote.get("quote_number", ""),
            "client_id": quote.get("client_id", ""),
            "client_name": client_name,
            "client_rif": client_rif,
            "status": "preasignado",
            "preassigned_at": now,
            "preassigned_by": current_user.get("user_id", ""),
            "preassigned_by_name": user_name,
            "assigned_at": None,
        }
        assignments.append(doc)

    if assignments:
        await db.serial_assignments.insert_many(assignments)

    # Guardar referencia en la cotización
    await db.quotes.update_one({"quote_id": quote_id}, {"$set": {
        "preassigned_serials": selected_serials,
        "preassigned_at": now,
        "preassigned_warehouse_id": warehouse_id,
    }})

    # === NOTIFICACIÓN: motor dinámico (config catálogo) → fallback legacy ===
    # Si en "Configuración de Notificaciones" se asignó plantilla y destinatarios
    # para `preassign_serials` en (biz_type, sub_cat), se respeta esa config
    # (incluyendo destinatario tipo Cliente). Si no hay config: legacy a Operaciones.
    email_sent = False
    email_error = None
    email_recipients = []
    email_results = []

    # Refrescar la cotización para que el motor lea preassigned_serials/at recién persistidos
    quote_refreshed = await db.quotes.find_one({"quote_id": quote_id}, {"_id": 0}) or quote
    serials_html = "<br>".join([f"&bull; {s}" for s in selected_serials])
    extra_vars = {
        "Cotizacion_Nro": quote_refreshed.get("quote_number", ""),
        "Nombre_Cliente": client_name,
        "Modelo_Equipo": model_name,
        "Lista_Seriales": serials_html,
        "Lista_Seriales_Texto": ", ".join(selected_serials),
        "Cantidad_Seriales": str(len(selected_serials)),
        "Nombre_Ejecutivo": user_name,
        "Email_Ejecutivo": user_email,
    }

    try:
        dispatched = await _ne_try_dispatch(
            action_id="preassign_serials",
            quote=quote_refreshed,
            current_user=current_user,
            custom_message=custom_message,
            cc_emails=cc_emails,
            extra_template_vars=extra_vars,
        )
    except Exception as e:
        dispatched = False
        logger.exception(f"[Preassign] Excepción en motor dinámico: {e}")

    if dispatched:
        email_sent = True
        email_recipients = ["(según Configuración de Notificaciones)"]
        logger.info(f"[Preassign] Notificación despachada por motor dinámico (quote={quote_id})")
    else:
        # === FALLBACK LEGACY: a Operaciones de la sede ===
        try:
            config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
            raw_sede = quote.get("sede", "PYME")
            norm_sede = "PYME" if raw_sede in ("TBP", "PYME", "Pymes", "pyme") else "CORP"
            sede_emails = (config.get("emails_by_sede", {}) if config else {}).get(norm_sede, {})

            # Cadena de fallback robusta:
            # 1. operations sede → 2. admin sede → 3. creador → 4. ejecutante.
            candidates = []
            if sede_emails.get("operations"):
                candidates.append(sede_emails["operations"])
            if sede_emails.get("admin") and sede_emails["admin"] not in candidates:
                candidates.append(sede_emails["admin"])
            creator_id = quote.get("created_by_user_id")
            if creator_id:
                creator_doc = await db.users.find_one({"user_id": creator_id}, {"_id": 0, "email": 1})
                ce = (creator_doc or {}).get("email")
                if ce and ce not in candidates:
                    candidates.append(ce)
            if user_email and user_email not in candidates:
                candidates.append(user_email)

            if not candidates:
                email_error = "No hay destinatario configurado para Preasignación. Configure el correo de Operaciones/Administración en Configuración › Sede, o asigne una plantilla con destinatario en Configuración de Notificaciones."
                logger.warning(f"[Preassign] {email_error} (quote={quote_id})")
            else:
                ops_email = candidates[0]
                email_recipients = [ops_email]
                logger.info(f"[Preassign/legacy] Destinatario resuelto: {ops_email} (de {candidates})")

                template = await get_email_template(f"serial_preassignment_{norm_sede}")
                if not template:
                    template = await get_email_template("serial_preassignment_PYME")
                    if template:
                        logger.warning(f"[Preassign/legacy] Plantilla por sede '{norm_sede}' no encontrada, usando 'PYME'")

                if template:
                    subject = render_email_template(template["subject"], extra_vars)
                    html = render_email_template(template["body_html"], extra_vars)
                else:
                    logger.warning("[Preassign/legacy] Sin plantilla en BD, usando fallback inline")
                    subject = f"PREASIGNACIÓN DE SERIALES: {quote.get('quote_number', '')} - {client_name}"
                    html = (f"<h2>Preasignación de Seriales</h2>"
                            f"<p>Cotización: {quote.get('quote_number')}</p>"
                            f"<p>Cliente: {client_name}</p><p>Modelo: {model_name}</p>"
                            f"<p>Seriales: {', '.join(selected_serials)}</p>")

                r = await send_email(
                    to=[ops_email], subject=subject, html=html,
                    action="preassign_serials", quote_id=quote_id,
                    quote_number=quote.get("quote_number"),
                )
                email_results.append(r)
                email_sent = bool((r or {}).get("status") in ("sent", "queued") or (r or {}).get("id"))
                if email_sent:
                    logger.info(f"[Preassign/legacy] Notificación enviada a Operaciones: {ops_email}")
                else:
                    email_error = (r or {}).get("error") or "El servicio de correo no confirmó el envío"
                    logger.error(f"[Preassign/legacy] Envío no confirmado: {email_error} (response={r})")
        except Exception as e:
            email_error = str(e)
            logger.exception(f"[Preassign/legacy] Error enviando notificación: {e}")

    return {
        "message": f"Prerregistro exitoso: {len(selected_serials)} seriales reservados",
        "serials": selected_serials,
        "status": "preasignado",
        "emails": email_results,
        "email_sent": email_sent,
        "email_error": email_error,
        "email_recipients": email_recipients,
        "dispatched_by": "engine" if dispatched else "legacy",
    }
