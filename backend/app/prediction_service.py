"""
prediction_service.py

Purpose (in simple language):
------------------------------
This is where a /predict request actually gets turned into an answer.

IMPORTANT, HONEST LIMITATION (documented here and in the API response):
This service performs LIVE model inference using the most recent
engineered feature row already computed by Phase 2/3 for the requested
crop-market-variety (i.e. the latest date currently present in the
pipeline's data). It does NOT yet compute fresh lag/rolling features for
an arbitrary future forecast_date on the fly - that requires a live daily
data-ingestion pipeline, which is out of scope for Phase 4 (FastAPI only).
The requested forecast_date is validated for format and echoed back, but
the forecast itself reflects the latest data available to the trained
pipeline. This is clearly stated in every response's "explanation" field.

Steps:
1. Confirm the (crop, market) pair is eligible (Phase 1 data-quality gate)
   - if not, raise a 404 AppError immediately. No forecast is ever
     fabricated for an ineligible pair.
2. Resolve which variety to use (requested variety if it matches the
   modeled Variety_Used, otherwise fall back to Variety_Used with a note -
   since only one variety per pair has a trained model, per Phase 2/3's
   documented "dominant variety" design).
3. Look up the selected model for this pair from the registry.
4. If naive/moving-average (no trained artifact) -> compute the
   prediction directly from the latest feature row's lag/rolling values.
   Otherwise -> lazily load the joblib model and call .predict() on the
   latest feature row, built with the exact same feature columns used
   during training (imported directly from ml_pipeline, never redefined).
5. Build the estimated price range by shifting the Phase 3 validation-time
   range by the (small, usually zero) difference between this live
   prediction and the value already stored in prediction_ranges.csv -
   keeping the range internally consistent with the point prediction.
6. Reuse the Phase 3 confidence score and trend info as-is.
7. Assemble the final response, including a plain-language explanation
   and (if applicable) a low-confidence warning.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
import pandas as pd

from exception_handlers import AppError
from fastapi import status
from model_loader import ModelRegistryManager
from validators import validate_variety

from baseline_models import LINEAR_REGRESSION_FEATURES
from advanced_models import NUMERIC_FEATURES, CROP_SPECIFIC_CATEGORICAL, COMBINED_CATEGORICAL
from forecast_utils import determine_trend

logger = logging.getLogger("krushimitra.prediction_service")

NAIVE_MODEL_NAMES = {"Naive_Previous_Price", "Moving_Average_3Day", "Moving_Average_7Day"}


def _naive_prediction(model_name: str, latest_row: pd.Series) -> float:
    if model_name == "Naive_Previous_Price":
        return float(latest_row["lag_1"])
    if model_name == "Moving_Average_3Day":
        return float(latest_row["rolling_mean_3"])
    if model_name == "Moving_Average_7Day":
        return float(latest_row["rolling_mean_7"])
    raise ValueError(f"Unrecognized naive model name: {model_name}")


def _model_prediction(model_scope: str, model_name: str, model_obj, latest_row: pd.Series) -> float:
    if model_name == "Linear_Regression":
        X = pd.DataFrame([latest_row[LINEAR_REGRESSION_FEATURES]])
        return float(model_obj.predict(X)[0])

    if model_scope == "crop_specific":
        cols = CROP_SPECIFIC_CATEGORICAL + NUMERIC_FEATURES
    elif model_scope == "combined":
        cols = COMBINED_CATEGORICAL + NUMERIC_FEATURES
    else:
        raise ValueError(f"Unrecognized model scope for live inference: {model_scope}")

    X = pd.DataFrame([latest_row[cols]])
    return float(model_obj.predict(X)[0])


def predict(registry_manager: ModelRegistryManager, crop: str, market: str, variety: str, forecast_date: str) -> dict:
    if not registry_manager.is_eligible(crop, market):
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            f"No eligible model available for {crop} at {market}. "
            f"This crop-market pair did not pass Phase 1 data-quality checks.",
        )

    registry_row = registry_manager.get_registry_row(crop, market)
    if registry_row is None:
        # Should not happen if is_eligible() is true, but guarded defensively.
        raise AppError(status.HTTP_404_NOT_FOUND, f"No registered model found for {crop} at {market}.")

    variety_used = registry_row["Variety_Used"]
    variety_note = ""
    if variety is not None:
        known_varieties = registry_manager.get_known_varieties(crop, market)
        matched_variety = validate_variety(variety, known_varieties)
        if matched_variety != variety_used:
            variety_note = (
                f" Note: a separate model for variety '{matched_variety}' is not available; "
                f"this forecast uses variety '{variety_used}', which has sufficient historical data."
            )

    latest_row = registry_manager.get_latest_feature_row(crop, market, variety_used)
    if latest_row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, f"No historical feature data found for {crop} at {market} ({variety_used}).")

    model_name = registry_row["Selected_Model_Name"]
    model_scope = registry_row["Model_Scope"]

    try:
        if model_name in NAIVE_MODEL_NAMES:
            live_predicted_price = _naive_prediction(model_name, latest_row)
        else:
            model_obj = registry_manager.get_model(registry_row["Model_File_Path"])
            live_predicted_price = _model_prediction(model_scope, model_name, model_obj, latest_row)
    except Exception as e:
        logger.error(f"Prediction failure for {crop} @ {market}: {e}", exc_info=True)
        raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, "Prediction failed due to an internal model error.")

    # --- Build range consistently around the live prediction, using Phase 3's validation-time range as reference ---
    range_row = registry_manager.get_range_row(crop, market)
    if range_row is not None:
        stored_predicted = float(range_row["Predicted_Modal_Price"])
        offset_lower = float(range_row["Estimated_Lower_Price"]) - stored_predicted
        offset_upper = float(range_row["Estimated_Upper_Price"]) - stored_predicted
        lower = round(live_predicted_price + offset_lower, 2)
        upper = round(live_predicted_price + offset_upper, 2)
        stored_trend = range_row["Trend"]
    else:
        lower, upper = round(live_predicted_price * 0.95, 2), round(live_predicted_price * 1.05, 2)
        stored_trend = None

    last_known_price = float(latest_row["lag_1"]) if pd.notna(latest_row["lag_1"]) else live_predicted_price
    trend = determine_trend(live_predicted_price, last_known_price) if stored_trend is None else stored_trend

    # --- Confidence, reused directly from Phase 3's evaluation ---
    confidence_row = registry_manager.get_confidence_row(crop, market)
    if confidence_row is not None:
        confidence_score = float(confidence_row["Overall_Confidence_Score"])
        confidence_level = confidence_row["Confidence_Level"]
        low_confidence_warning = confidence_row["Low_Confidence_Warning"] or None
        if pd.isna(low_confidence_warning):
            low_confidence_warning = None
    else:
        confidence_score, confidence_level, low_confidence_warning = 0.0, "Low", "Low-confidence forecast - use with caution."

    as_of_date = latest_row["Arrival_Date"].date().isoformat()
    explanation = (
        f"Based on data available through {as_of_date} for {crop} at {market} ({variety_used}), "
        f"the {model_name.replace('_', ' ')} model ({model_scope.replace('_', ' ')} scope) estimates a modal price "
        f"of Rs.{live_predicted_price:.0f} per quintal, with a {trend.lower()} trend versus the last known price of "
        f"Rs.{last_known_price:.0f}.{variety_note} "
        f"This forecast reflects the most recent data currently loaded in the system rather than a live "
        f"recomputation for the requested forecast_date ({forecast_date}); live daily data ingestion is planned "
        f"for a later phase. Prices are estimates only - actual prices may vary due to supply, demand, weather, "
        f"government policy, or unforeseen market conditions."
    )

    return {
        "crop": crop,
        "market": market,
        "variety_used": variety_used,
        "forecast_date": forecast_date,
        "predicted_price": round(live_predicted_price, 2),
        "estimated_price_range": {"lower": lower, "upper": upper},
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "selected_model": model_name,
        "model_scope": model_scope,
        "trend": trend,
        "explanation": explanation,
        "warning_if_low_confidence": low_confidence_warning,
    }
