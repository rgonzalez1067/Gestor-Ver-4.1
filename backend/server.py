"""
Cotizador Merchant Server - Punto de entrada principal.
Monta todos los routers modulares sobre la aplicación FastAPI.
"""
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
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
api_router.include_router(seed_templates_router)
api_router.include_router(projects_router)
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
