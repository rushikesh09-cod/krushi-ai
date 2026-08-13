"""
validators.py

Purpose (in simple language):
------------------------------
Checks user input BEFORE any prediction logic runs, and raises a clear,
specific AppError (with the right HTTP status code) the moment something
is wrong - unknown crop, unknown market, unknown variety, or a badly
formatted date. This keeps prediction_service.py focused purely on the
"happy path" prediction logic.

Crop/market names are normalized using the SAME standardization functions
the ml_pipeline uses (imported directly, not re-implemented) so "onion",
"Onion", and "ONION" are all treated identically here too.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from datetime import datetime
from fastapi import status

from exception_handlers import AppError
from standardization import standardize_crop_name, standardize_market_name  # from ml_pipeline, reused as-is


def validate_and_normalize_crop(crop: str, known_crops: list) -> str:
    if not crop or not str(crop).strip():
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "Field 'crop' must not be empty.")

    normalized = standardize_crop_name(crop)
    if normalized not in known_crops:
        raise AppError(status.HTTP_404_NOT_FOUND, f"Unknown crop: '{crop}'. Supported crops: {known_crops}")
    return normalized


def validate_and_normalize_market(market: str, known_markets: list) -> str:
    if not market or not str(market).strip():
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "Field 'market' must not be empty.")

    normalized = standardize_market_name(market)
    if normalized not in known_markets:
        raise AppError(status.HTTP_404_NOT_FOUND, f"Unknown market: '{market}'. Supported markets: {known_markets}")
    return normalized


def validate_variety(variety: str, known_varieties: list) -> str:
    """
    Returns the matched known variety name (case-insensitive match), or
    raises a 404 if the requested variety has never been seen for this
    crop-market pair at all.
    """
    match = next((v for v in known_varieties if v.strip().lower() == variety.strip().lower()), None)
    if match is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            f"Unknown variety: '{variety}'. Known varieties for this crop-market pair: {known_varieties}",
        )
    return match


def validate_date_format(date_str: str) -> str:
    if not date_str or not str(date_str).strip():
        raise AppError(status.HTTP_422_UNPROCESSABLE_ENTITY, "Field 'forecast_date' must not be empty.")
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Invalid forecast_date '{date_str}'. Expected format: YYYY-MM-DD (e.g. 2026-08-01).",
        )
    return date_str.strip()
