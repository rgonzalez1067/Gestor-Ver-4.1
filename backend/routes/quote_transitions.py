"""Transiciones post-cotización: creación de proyectos al enviar a implementación.

Extraído de `quote_actions.py` para aislar la lógica que convierte una cotización
finalizada en un proyecto de implementación (single/multitienda) y notifica al
gerente responsable.
"""
from datetime import datetime, timezone
import logging
import uuid

from config import db
from services.email_service import send_email


logger = logging.getLogger(__name__)


async def _create_project_from_quote(
    quote: dict,
    quote_id: str,
    multistore_data: dict = None,
    equipment_data: list = None,
    project_type_impl: str = None,
    server_name: str = None,
    pinpad_serials: list = None,
    economic_group: str = None,
    fantasy_name: str = None,
    implementation_instructions: str = None,
    keep_quote_active: bool = False,
):
    """Crea un proyecto a partir de una cotización enviada a implementación.

    Args:
        keep_quote_active: Si True (caso MPOS Imple+POS / fast_track), la
            cotización origen NO se elimina; permanece activa con
            quote_status="Enviada a Imple" para ser cerrada posteriormente vía
            "Marcar como Entregada". Default False (comportamiento legacy).
    """
    existing = await db.projects.find_one({"quote_id": quote_id})
    if existing:
        logger.info(f"Proyecto ya existe para cotización {quote_id}")
        return

    # Obtener datos del cliente
    client = await db.clients.find_one({"client_id": quote.get("client_id")}, {"_id": 0})
    client_name = client.get("legal_name", "") if client else quote.get("client_name", "")
    client_rif = client.get("rif", "") if client else ""
    client_sede = client.get("sucursal", "Principal") if client else "Principal"

    # Código de sede para nomenclatura
    sede_code = client_sede[:3].upper() if client_sede else "PRI"
    now = datetime.now(timezone.utc)
    year = now.strftime('%Y')
    month = now.strftime('%m')

    # Consecutivo mensual
    month_prefix = f"PRY-{year}-{month}-"
    last_project = await db.projects.find_one(
        {"project_number": {"$regex": f"^{month_prefix}"}},
        sort=[("project_number", -1)]
    )
    if last_project:
        try:
            last_num = int(last_project["project_number"].split("-")[3])
            next_num = last_num + 1
        except (IndexError, ValueError):
            next_num = 1
    else:
        next_num = 1

    project_number = f"PRY-{year}-{month}-{str(next_num).zfill(3)}-{sede_code}"

    # Extraer bancos de la cotización
    banks = []
    for item in quote.get("services", []):
        bn = item.get("bank_name")
        if bn and bn not in [b.get("bank_name") for b in banks]:
            banks.append({"bank_name": bn})
    if quote.get("sponsor_bank_name"):
        if quote["sponsor_bank_name"] not in [b.get("bank_name") for b in banks]:
            banks.append({"bank_name": quote["sponsor_bank_name"]})

    # Para Payment Gateway (GATEWAY): los bancos provienen de pg_setup_items
    # (cada item lleva {concepto, banco, costo, observacion}). Se ignora 'N/A'
    # que corresponde a items conceptuales fijos (ej. Persona Jurídica).
    is_gateway = (quote.get("quote_type") or "").upper() == "GATEWAY"
    if is_gateway:
        for it in quote.get("pg_setup_items", []) or []:
            bn = (it.get("banco") or "").strip()
            if not bn or bn.upper() == "N/A":
                continue
            if bn not in [b.get("bank_name") for b in banks]:
                banks.append({"bank_name": bn})

    # Construir matriz de implementación.
    # - VPOS/MPOS/Fast Track: items 'additional' de `services` agrupados por banco/producto.
    # - Payment Gateway: pg_setup_items agrupados por banco/concepto, pre-poblados
    #   con `expected: 1` para que el implementador pueda editar y propagar a las
    #   fases siguientes desde "Recibido" (igual UX que hardware).
    implementation_matrix = {}
    if is_gateway:
        for it in quote.get("pg_setup_items", []) or []:
            bn = (it.get("banco") or "").strip()
            name = (it.get("concepto") or "").strip()
            if not bn or not name or bn.upper() == "N/A":
                continue
            if bn not in implementation_matrix:
                implementation_matrix[bn] = {}
            if name not in implementation_matrix[bn]:
                implementation_matrix[bn][name] = {
                    "Recibido":      {"expected": 1, "processed": 0, "completed": False},
                    "Configurado":   {"expected": 1, "processed": 0, "completed": False},
                    "Testeado":      {"expected": 1, "processed": 0, "completed": False},
                    "En Producción": {"expected": 1, "processed": 0, "completed": False},
                }
    else:
        for item in quote.get("services", []):
            if item.get("item_type") != "additional":
                continue
            bn = item.get("bank_name", "")
            name = item.get("item_name", "")
            if not bn or not name:
                continue
            if bn not in implementation_matrix:
                implementation_matrix[bn] = {}
            if name not in implementation_matrix[bn]:
                implementation_matrix[bn][name] = {}

    # Heredar anexos de la cotización
    attachments = []
    for att in quote.get("attachments", []):
        attachments.append({
            "attachment_id": att.get("attachment_id", f"att_{uuid.uuid4().hex[:12]}"),
            "filename": att.get("filename", ""),
            "url": att.get("url", ""),
            "category": att.get("category", "Cotización"),
            "uploaded_by": att.get("uploaded_by", "system"),
            "uploaded_by_name": att.get("uploaded_by_name", "Sistema"),
            "uploaded_at": att.get("uploaded_at", now.isoformat()),
            "inherited_from": "cotización",
        })

    project = {
        "project_id": f"prj_{uuid.uuid4().hex[:12]}",
        "project_number": project_number,
        "quote_id": quote_id,
        "quote_number": quote.get("quote_number", ""),
        "quote_pdf_url": quote.get("quote_pdf_url"),
        "client_id": quote.get("client_id", ""),
        "client_name": client_name,
        "client_rif": client_rif,
        "client_sede": client_sede,
        "client_segment": quote.get("client_segment", "PYME"),
        "quote_category": quote.get("quote_category", "implementation"),
        "quote_type": quote.get("quote_type", "VPOS"),
        "services": quote.get("services", []),
        "hardware": quote.get("hardware", []),
        "equipment_items": quote.get("equipment_items", []),
        "pg_setup_items": quote.get("pg_setup_items", []),
        "banks": banks,
        "integrator_name": quote.get("integrator_name"),
        "integrator_app_name": quote.get("integrator_app_name"),
        "pinpad_model": quote.get("pinpad_model"),
        "sponsor_bank_name": quote.get("sponsor_bank_name"),
        # Implementación Patrocinada (heredado desde la cotización para reportabilidad)
        "sponsored_implementation": bool(quote.get("sponsored_implementation", False)),
        "sponsoring_bank_id": quote.get("sponsoring_bank_id") or None,
        "sponsoring_bank_name": quote.get("sponsoring_bank_name") or None,
        "total_usd": quote.get("total_usd", 0),
        "total_bs": quote.get("total_bs", 0),
        "status": "Pendiente por Asignar",
        "priority": "Normal",
        "is_irregular": quote.get("is_irregular", False),
        "irregular_exceptions": quote.get("irregular_exceptions", []) or [],
        "implementation_matrix": implementation_matrix,
        "attachments": attachments,
        "bitacora": [],
        "notes": [{
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Proyecto creado desde cotización {quote.get('quote_number', quote_id)}",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        }],
        "created_at": now.isoformat(),
        "project_type": "single",
        "client_notified": False,
        "client_notified_at": None,
        "client_notified_by": None,
        "bank_notifications": {},
        "rollup_progress": None,
        "box_count": int(quote.get("cantidad_cajas", 0) or 0),
    }

    # === Auto-asignación desde la ficha del cliente ===
    # Si el cliente tiene un Implementador fijado en su ficha, heredamos
    # la asignación y dejamos el proyecto listo "Asignado / En Proceso".
    # Si no tiene, mantenemos el estatus "Pendiente por Asignar".
    client_impl_user_id = (client or {}).get("implementer_user_id")
    client_impl_name = (client or {}).get("implementer_name")
    if client_impl_user_id and client_impl_name:
        project["assigned_to_user_id"] = client_impl_user_id
        project["assigned_to_name"] = client_impl_name
        project["assigned_at"] = now.isoformat()
        project["status"] = "Asignado / En Proceso"
        project["auto_assigned_from_client"] = True
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Asignado automáticamente a {client_impl_name} desde la ficha del cliente.",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

    # Soporte Multitienda (heredado de branch_details de la cotización o enviado manualmente)
    branch_details = quote.get("branch_details", [])
    if not multistore_data and branch_details:
        multistore_data = {
            "is_multistore": True,
            "stores": [{"name": b.get("store_name", ""), "box_count": int(b.get("quantity", 0))} for b in branch_details]
        }

    if multistore_data and multistore_data.get("is_multistore"):
        stores_raw = multistore_data.get("stores", [])
        project["project_type"] = "multistore"
        project["stores"] = []
        for store in stores_raw:
            store_entry = {
                "store_id": f"st_{uuid.uuid4().hex[:8]}",
                "name": store.get("name", ""),
                "box_count": store.get("box_count", 0),
                "implementation_matrix": dict(implementation_matrix),
                "status": "Pendiente",
                "notes": [],
            }
            project["stores"].append(store_entry)
        # Nota especial para multitienda
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Proyecto Multitienda con {len(stores_raw)} tienda(s): {', '.join(s.get('name', '') for s in stores_raw)}",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

    # Tipo de Proyecto de Implementación (POS Fast Track / VPOS-MPOS / Payment Gateway)
    if project_type_impl:
        project["project_type_impl"] = project_type_impl

    # Servidor de instalación (flujo PYME)
    if server_name:
        project["server_name"] = server_name
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Servidor de instalación: {server_name}",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

    # Grupo Económico y Nombre de Fantasía (defaults aplicados aguas arriba)
    if economic_group is not None:
        project["economic_group"] = economic_group
    if fantasy_name is not None:
        project["fantasy_name"] = fantasy_name

    # Instrucciones adicionales para el Implementador (HTML rich-text).
    # Se persiste en la tabla de proyectos. Si viene vacío/None, se fuerza a None
    # para limpiar cualquier contenido previo (importante en re-envíos/regeneraciones).
    project["implementation_instructions"] = implementation_instructions if implementation_instructions else None

    # Pinpad seriales seleccionados (flujo PYME)
    if pinpad_serials and isinstance(pinpad_serials, list):
        project["pinpad_serials"] = pinpad_serials
        pp_models = {}
        for pp in pinpad_serials:
            m = pp.get("modelo", "Desconocido")
            if m not in pp_models:
                pp_models[m] = 0
            pp_models[m] += 1
        pp_summary = ", ".join(f"{m} x{c}" for m, c in pp_models.items())
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Pinpads vinculados desde inventario: {pp_summary} ({len(pinpad_serials)} serial(es))",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

    # Equipos vinculados (seriales y modelos)
    if equipment_data and isinstance(equipment_data, list):
        project["equipments"] = equipment_data
        models_summary = {}
        for eq in equipment_data:
            modelo = eq.get("modelo", "Desconocido")
            if modelo not in models_summary:
                models_summary[modelo] = 0
            models_summary[modelo] += 1
        summary_text = ", ".join(f"{m} x{c}" for m, c in models_summary.items())
        project["notes"].append({
            "note_id": f"pn_{uuid.uuid4().hex[:8]}",
            "text": f"Equipos vinculados: {summary_text} ({len(equipment_data)} serial(es))",
            "created_by": "system",
            "created_by_name": "Sistema",
            "created_at": now.isoformat(),
        })

    await db.projects.insert_one(project)
    project.pop("_id", None)
    logger.info(f"Proyecto {project_number} creado desde cotización {quote_id}")

    # Push notification (evento #6 Proyecto creado desde cotización)
    try:
        from services.notification_service import notify as _push_notify
        await _push_notify(
            event_type="project_created",
            title=f"Nuevo proyecto {project_number}",
            message=f"Cliente {client_name} · Cotización {quote.get('quote_number','')} · Total USD ${quote.get('total_usd',0):,.2f}",
            context={
                "creator_user_id": quote.get("created_by_user_id"),
                "sede": quote.get("sede") or client_sede,
            },
            link=f"/projects/{project['project_id']}",
            project_id=project["project_id"],
            quote_id=quote_id,
        )
    except Exception as e:
        logger.warning(f"[notify] project_created failed: {e}")

    # Eliminar la cotización origen — EXCEPTO si `keep_quote_active=True`
    # (caso MPOS Imple+POS / fast_track), donde la cotización se preserva
    # activa para que el cierre operativo lo haga "Marcar como Entregada".
    if keep_quote_active:
        await db.quotes.update_one(
            {"quote_id": quote_id},
            {"$set": {
                "quote_status": "Enviada a Imple",
                "sent_to_implementation_at": datetime.now(timezone.utc).isoformat(),
                "project_id": project["project_id"],
                "project_number": project_number,
            }},
        )
        logger.info(f"Cotización {quote_id} preservada activa (keep_quote_active=True), proyecto {project_number} vinculado.")
    else:
        await db.quotes.delete_one({"quote_id": quote_id})
        logger.info(f"Cotización {quote_id} eliminada tras conversión a proyecto {project_number}")

    # Notificar al Gerente de Implementación
    try:
        config = await db.config.find_one({"type": "app_settings"}, {"_id": 0})
        impl_manager_email = config.get("implementation_manager_email") if config else None
        if impl_manager_email:
            notif_subject = f"Nuevo Proyecto: {project_number} - {client_name}"
            notif_html = f"""
            <h2>Nuevo Proyecto Pendiente de Asignación</h2>
            <p><strong>Proyecto:</strong> {project_number}</p>
            <p><strong>Cliente:</strong> {client_name} ({client_rif})</p>
            <p><strong>Sede:</strong> {client_sede}</p>
            <p><strong>Cotización origen:</strong> {quote.get('quote_number', '')}</p>
            <p><strong>Tipo:</strong> {quote.get('quote_type', 'VPOS')}</p>
            <p><strong>Total USD:</strong> ${quote.get('total_usd', 0):,.2f}</p>
            <hr>
            <p>Ingrese al sistema para asignar este proyecto a un implementador.</p>
            """
            await send_email(
                to=[impl_manager_email],
                subject=notif_subject,
                html=notif_html,
                action="new_project_notification",
                quote_id=quote_id,
            )
    except Exception as e:
        logger.warning(f"Error notificando gerente de implementación: {e}")
