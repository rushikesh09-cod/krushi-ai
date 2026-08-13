"""
routers/crops.py

GET /crops - returns every crop currently configured in config/crops.json
(the same file the ml_pipeline uses), regardless of whether every
crop-market combination is eligible for forecasting - eligibility is a
per-pair concern, checked separately at /predict time.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from fastapi import APIRouter

from model_loader import registry_manager
from schemas import CropsResponse

logger = logging.getLogger("krushimitra.crops")
router = APIRouter()


@router.get("/crops", response_model=CropsResponse, tags=["Reference Data"])
def get_crops():
    return CropsResponse(crops=registry_manager.canonical_crops)
