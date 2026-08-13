"""
routers/prediction.py

POST /predict - the main forecasting endpoint. Validates input, then
delegates to prediction_service.predict() for the actual logic.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from fastapi import APIRouter

from model_loader import registry_manager
from schemas import PredictRequest, PredictResponse
from validators import validate_and_normalize_crop, validate_and_normalize_market, validate_date_format
import prediction_service

logger = logging.getLogger("krushimitra.prediction")
router = APIRouter()


@router.post("/predict", response_model=PredictResponse, tags=["Prediction"])
def predict(request: PredictRequest):
    logger.info(f"Prediction request received: crop={request.crop}, market={request.market}, "
                f"variety={request.variety}, forecast_date={request.forecast_date}")

    crop = validate_and_normalize_crop(request.crop, registry_manager.canonical_crops)
    market = validate_and_normalize_market(request.market, registry_manager.canonical_markets)
    forecast_date = validate_date_format(request.forecast_date)

    result = prediction_service.predict(
        registry_manager=registry_manager,
        crop=crop, market=market, variety=request.variety, forecast_date=forecast_date,
    )

    logger.info(f"Prediction served: {crop} @ {market} -> {result['predicted_price']} "
                f"(model={result['selected_model']}, confidence={result['confidence_level']})")

    return PredictResponse(**result)
