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
from routes.attachments import router as attachments_router
from routes.integrators import router as integrators_router
from routes.settings import router as settings_router
from routes.seed_and_templates import router as seed_templates_router
from routes.projects import router as projects_router
from routes.new_products import router as new_products_router
from routes.inventory import router as inventory_router

app = FastAPI(title="Cotizador Merchant Server API")

# Mount uploads
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

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

    # Validar: Ninguno → 403
    if user_level == "none":
        return JSONResponse(
            status_code=403,
            content={"detail": f"No tiene acceso al módulo '{target_module}'"}
        )

    # Validar: Leer + método de escritura → 403
    if user_level == "read" and method in WRITE_METHODS:
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
api_router.include_router(quotes_router)
api_router.include_router(attachments_router)
api_router.include_router(integrators_router)
api_router.include_router(settings_router)
api_router.include_router(projects_router)  # Projects router before seed_templates to allow new email-templates CRUD routes
api_router.include_router(seed_templates_router)
api_router.include_router(new_products_router)
api_router.include_router(inventory_router)

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
        logging.info("MongoDB indexes created successfully")
    except Exception as e:
        logging.warning(f"Error creating indexes: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
