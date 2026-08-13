"""
routers/markets.py

GET /markets - returns every configured market.
GET /markets?crop=Onion - returns only markets where that crop has an
ELIGIBLE (Crop, Market) pair per the Phase 1 data-quality report - this is
deliberately stricter than "any market that ever had a row for this crop",
since an ineligible pair can't actually be forecasted anyway.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import logging
from typing import Optional
from fastapi import APIRouter, Query, status

from model_loader import registry_manager
from schemas import MarketsResponse
from exception_handlers import AppError
from validators import validate_and_normalize_crop

logger = logging.getLogger("krushimitra.markets")
router = APIRouter()


@router.get("/markets", response_model=MarketsResponse, tags=["Reference Data"])
def get_markets(crop: Optional[str] = Query(None, description="Optional crop name to filter markets by, e.g. 'Onion'")):
    if crop is None:
        return MarketsResponse(markets=registry_manager.canonical_markets, filtered_by_crop=None)

    normalized_crop = validate_and_normalize_crop(crop, registry_manager.canonical_crops)
    eligible_markets = sorted(
        registry_manager.quality_df[
            (registry_manager.quality_df["Crop"] == normalized_crop) & (registry_manager.quality_df["Is_Eligible"] == True)
        ]["Market"].unique().tolist()
    )
    return MarketsResponse(markets=eligible_markets, filtered_by_crop=normalized_crop)
