"""
main.py

Purpose (in simple language):
------------------------------
The entrypoint that assembles the whole API: configures logging, loads
the model registry once at startup, registers every router and every
exception handler, and exposes the root ("/") status endpoint.

Run with (from backend/app/):
    uvicorn main:app --reload --port 8000

Then visit:
    http://127.0.0.1:8000/docs   (Swagger UI)
    http://127.0.0.1:8000/redoc  (ReDoc)
"""

import os
import sys

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from model_loader import registry_manager
from exception_handlers import AppError, app_error_handler, validation_error_handler, not_found_handler, generic_exception_handler
from schemas import RootResponse
from routers import health, crops, markets, models, prediction

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("krushimitra.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {config.APP_NAME} v{config.APP_VERSION}...")
    try:
        registry_manager.load()
        logger.info("Model registry loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model registry at startup: {e}", exc_info=True)
        # Do not crash the process - /health will correctly report "degraded"
        # and /predict will fail with a clear error, rather than the whole
        # app failing to even start.
    yield
    logger.info("Shutting down KrushiMitra AI API.")


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="Serves crop price forecasts from the Phase 3 model registry. "
                 "All current models are trained on synthetic/sample development data.",
    lifespan=lifespan,
)


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, not_found_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.include_router(health.router)
app.include_router(crops.router)
app.include_router(markets.router)
app.include_router(models.router)
app.include_router(prediction.router)


@app.get("/", response_model=RootResponse, tags=["Root"])
def root():
    return RootResponse(project=config.APP_NAME, version=config.APP_VERSION, status="running")
