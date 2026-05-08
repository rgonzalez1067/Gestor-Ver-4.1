"""
Cotizador Merchant Server - Punto de entrada principal.
Monta todos los routers modulares sobre la aplicación FastAPI.
"""
from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
import logging

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

from config import db, client, UPLOADS_DIR

# Importar routers
from routes.auth import router as auth_router
from routes.clients import router as clients_router
from routes.dashboard import router as dashboard_router
from routes.banks import router as banks_router
from routes.hardware import router as hardware_router
from routes.services import router as services_router
from routes.quotes import router as quotes_router
from routes.quote_actions import router as quote_actions_router
from routes.quote_taller import router as quote_taller_router
from routes.quote_serials import router as quote_serials_router
from routes.commercial_categories import router as commercial_categories_router
from routes.attachments import router as attachments_router
from routes.integrators import router as integrators_router
from routes.settings import router as settings_router
from routes.seed_and_templates import router as seed_templates_router
from routes.projects import router as projects_router
from routes.new_products import router as new_products_router
from routes.inventory import router as inventory_router
from routes.initial_contacts import router as initial_contacts_router
from routes.initial_contact_communications import router as initial_contact_comms_router
from routes.client_communications import router as client_comms_router
from routes.sales_reports import router as sales_reports_router
from routes.entity_communications import router as entity_comms_router
from routes.quote_history import router as quote_history_router
from routes.external_api import router as external_api_router
from routes.notifications import router as notifications_router
from routes.action_notifications import router as action_notifications_router
from routes.quote_action_customization import router as quote_action_customization_router
from routes.profiles import router as profiles_router
from routes.data_migration import router as data_migration_router
from routes.project_reports import router as project_reports_router
from services.notification_scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Cotizador Merchant Server API")

@app.on_event("startup")
async def _on_startup():
    try:
        start_scheduler()
    except Exception as e:
        logging.warning(f"[startup] scheduler failed: {e}")

@app.on_event("shutdown")
async def _on_shutdown():
    try:
        stop_scheduler()
    except Exception as e:
        logging.warning(f"[shutdown] scheduler failed: {e}")

# Mount uploads — primero intenta Object Storage (persistente entre deploys),
# fallback a filesystem local para archivos legacy/temporales.
from fastapi import Path as FPath
from fastapi.responses import Response, FileResponse
from services.pdf_storage import get_pdf_from_storage

uploads_router = APIRouter()


@uploads_router.get("/api/uploads/{file_path:path}")
async def serve_upload(file_path: str = FPath(...)):
    """Sirve archivos del directorio uploads.

    Orden de búsqueda:
      1. Emergent Object Storage (namespace por ambiente: preview/production).
      2. Filesystem local (compatibilidad con archivos legacy / generados sin storage).
    """
    # 1) Object Storage
    result = get_pdf_from_storage(file_path)
    if result is not None:
        content, content_type = result
        return Response(content=content, media_type=content_type or "application/octet-stream")

    # 2) Filesystem fallback
    fs_path = UPLOADS_DIR / file_path
    if fs_path.exists() and fs_path.is_file():
        return FileResponse(str(fs_path))

    return Response(status_code=404, content="File not found")


app.include_router(uploads_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MIDDLEWARE RBAC ====================
# Mapeo de prefijos de ruta a módulos de permisos
ROUTE_MODULE_MAP = {
    "/api/quotes": "cotizaciones",
    "/api/clients": "clientes",
    "/api/banks": "bancos",
    "/api/services": "medios_pago",
    "/api/exchange-rate": "medios_pago",
    "/api/hardware": "dispositivos",
    "/api/component-types": "dispositivos",
    "/api/integrators": "integradores",
    "/api/config": "configuracion",
    "/api/projects": "proyectos",
    "/api/inventory": "inventarios",
    "/api/taller-equipos": "taller_equipos",
    "/api/new-products": "nuevos_productos",
}

# Rutas exentas de validación RBAC (auth, dashboard, uploads, etc.)
RBAC_EXEMPT_PREFIXES = [
    "/api/auth",
    "/api/dashboard",
    "/api/uploads",
    "/api/seed",
    "/api/attachments",
    "/api/external",
    "/api/notifications",
    "/api/ws/",
]

# Métodos HTTP que requieren nivel "edit"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def rbac_middleware(request: Request, call_next):
    """Middleware RBAC centralizado.
    Intercepta todas las peticiones y valida permisos por módulo.
    - Ninguno: 403 en cualquier método
    - Leer: Solo GET permitido
    - Editar: Acceso completo
    - Admin: Bypass total
    """
    path = request.url.path
    method = request.method
    logging.info(f"RBAC middleware: {method} {path}")

    # Rutas exentas
    if method == "OPTIONS":
        return await call_next(request)
    for exempt in RBAC_EXEMPT_PREFIXES:
        if path.startswith(exempt):
            return await call_next(request)

    # Buscar módulo correspondiente
    target_module = None
    for prefix, module in ROUTE_MODULE_MAP.items():
        if path.startswith(prefix):
            target_module = module
            break

    # Si no hay módulo mapeado, permitir (rutas internas/desconocidas)
    if not target_module:
        return await call_next(request)

    # Extraer token del header Authorization
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header

    if not token:
        return await call_next(request)  # Sin token → lo maneja get_current_user en el endpoint

    # Buscar sesión y usuario
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return await call_next(request)  # Sesión inválida → lo maneja el endpoint

    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        return await call_next(request)

    # Admin bypass
    if user.get("role") == "admin":
        return await call_next(request)

    # Obtener nivel de permiso del usuario para este módulo
    permissions = user.get("permissions", {})
    user_level = permissions.get(target_module, "none")
    logging.info(f"RBAC check: user={user.get('email')} module={target_module} level={user_level} method={method}")

    # Validar: Ninguno → 403 (pero verificar special_permissions primero)
    special_perms = user.get("special_permissions", [])

    if user_level == "none":
        # Verificar si tiene un override especial para esta acción
        if method == "POST" and f"{target_module}:create" in special_perms:
            logging.info(f"RBAC override: user={user.get('email')} special_permission={target_module}:create")
            return await call_next(request)
        return JSONResponse(
            status_code=403,
            content={"detail": f"No tiene acceso al módulo '{target_module}'"}
        )

    # Validar: Leer + método de escritura → 403 (pero verificar special_permissions primero)
    if user_level == "read" and method in WRITE_METHODS:
        if method == "POST" and f"{target_module}:create" in special_perms:
            logging.info(f"RBAC override: user={user.get('email')} special_permission={target_module}:create")
            return await call_next(request)
        return JSONResponse(
            status_code=403,
            content={"detail": f"No tiene permisos de escritura en '{target_module}'"}
        )

    return await call_next(request)

# Router principal con prefijo /api
api_router = APIRouter(prefix="/api")

# Montar todos los sub-routers
api_router.include_router(auth_router)
api_router.include_router(clients_router)
api_router.include_router(dashboard_router)
api_router.include_router(banks_router)
api_router.include_router(hardware_router)
api_router.include_router(services_router)
api_router.include_router(quote_actions_router)
api_router.include_router(quote_taller_router)
api_router.include_router(quote_serials_router)
api_router.include_router(commercial_categories_router)
api_router.include_router(quotes_router)
api_router.include_router(attachments_router)
api_router.include_router(integrators_router)
api_router.include_router(settings_router)
api_router.include_router(projects_router)  # Projects router before seed_templates to allow new email-templates CRUD routes
api_router.include_router(seed_templates_router)
api_router.include_router(action_notifications_router)
api_router.include_router(quote_action_customization_router)
api_router.include_router(new_products_router)
api_router.include_router(inventory_router)
api_router.include_router(initial_contacts_router)
api_router.include_router(initial_contact_comms_router)
api_router.include_router(client_comms_router)
api_router.include_router(sales_reports_router)
api_router.include_router(entity_comms_router)
api_router.include_router(quote_history_router)
api_router.include_router(external_api_router)
api_router.include_router(notifications_router)
api_router.include_router(profiles_router)
api_router.include_router(data_migration_router)
api_router.include_router(project_reports_router)

app.include_router(api_router)


@app.on_event("startup")
async def create_indexes():
    try:
        await db.clients.create_index([("fantasy_name", 1)])
        await db.clients.create_index([("legal_name", 1)])
        await db.clients.create_index([("rif", 1)])
        await db.clients.create_index([("client_id", 1)], unique=True)
        await db.quotes.create_index([("quote_id", 1)], unique=True)
        await db.quotes.create_index([("client_id", 1)])
        await db.quotes.create_index([("quote_number", 1)])
        await db.projects.create_index([("project_id", 1)], unique=True)
        await db.projects.create_index([("quote_id", 1)])
        await db.projects.create_index([("status", 1)])
        await db.uploaded_images.create_index([("image_id", 1)], unique=True)
        logging.info("MongoDB indexes created successfully")
    except Exception as e:
        logging.warning(f"Error creating indexes: {e}")

    # Initialize object storage
    try:
        from services.object_storage import init_storage
        init_storage()
    except Exception as e:
        logging.warning(f"Object storage init failed (images will not work): {e}")

    # Sincronizar plantillas de correo por defecto a MongoDB (sin sobreescribir las editadas)
    try:
        from routes.seed_and_templates import generate_email_templates_by_sede
        defaults = generate_email_templates_by_sede()
        synced = 0
        for tpl_id, tpl_data in defaults.items():
            exists = await db.email_templates.find_one({"template_id": tpl_id})
            if not exists:
                doc = {"template_id": tpl_id, **tpl_data, "is_active": True}
                await db.email_templates.insert_one(doc)
                synced += 1
        if synced > 0:
            logging.info(f"Synced {synced} default email templates to MongoDB")
    except Exception as e:
        logging.warning(f"Template sync failed: {e}")

    # Seed de perfiles base (idempotente)
    try:
        from seed_profiles import seed_profiles_if_needed
        created = await seed_profiles_if_needed()
        if created:
            logging.info(f"Seeded {created} default user profiles")
    except Exception as e:
        logging.warning(f"Profile seed failed: {e}")

    # Migración one-shot: resetear certifications de integradores al nuevo schema (19 productos).
    try:
        from routes.integrators import migrate_integrator_certifications_if_needed
        affected = await migrate_integrator_certifications_if_needed()
        if affected:
            logging.info(f"Integrator certifications reset for {affected} records")
    except Exception as e:
        logging.warning(f"Integrator cert migration failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
