"""
routers/models.py

GET /models - returns a summary of every registered model (one per
eligible Crop-Market pair): which model won, its scope, its accuracy
metrics, and the development-data flag. Deliberately does NOT include
Model_File_Path - that's an internal server detail, not something an API
consumer needs or should be able to probe.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from fastapi import APIRouter

from model_loader import registry_manager
from schemas import ModelsResponse, ModelSummaryItem

logger = logging.getLogger("krushimitra.models")
router = APIRouter()


@router.get("/models", response_model=ModelsResponse, tags=["Reference Data"])
def get_models():
    summary = registry_manager.list_models_summary()
    return ModelsResponse(
        total_registered=len(summary),
        models=[ModelSummaryItem(**row) for row in summary],
    )
