"""
routers/health.py

GET /health - reports whether the model registry loaded successfully and
how many distinct model artifacts are currently cached in memory.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from datetime import datetime
from fastapi import APIRouter

from model_loader import registry_manager
from schemas import HealthResponse

logger = logging.getLogger("krushimitra.health")
router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    return HealthResponse(
        status="healthy" if registry_manager.is_loaded else "degraded",
        model_registry_loaded=registry_manager.is_loaded,
        models_loaded=registry_manager.models_loaded_count,
        timestamp=datetime.now().isoformat(),
    )
