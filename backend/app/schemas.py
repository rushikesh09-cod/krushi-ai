"""
schemas.py

Purpose (in simple language):
------------------------------
Defines the exact shape of every request and response this API accepts or
returns. FastAPI uses these to auto-generate Swagger docs (/docs, /redoc),
validate incoming JSON automatically (missing/wrong-type fields become a
422 error before our own code even runs), and keep responses consistent.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class RootResponse(BaseModel):
    project: str
    version: str
    status: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    model_registry_loaded: bool
    models_loaded: int
    timestamp: str


class CropsResponse(BaseModel):
    crops: List[str]


class MarketsResponse(BaseModel):
    markets: List[str]
    filtered_by_crop: Optional[str] = None


class ModelSummaryItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    crop: str
    market: str
    variety_used: str
    selected_model: str
    model_type: str  # Model_Scope: naive / crop_specific / combined
    mae: float
    rmse: float
    mape: Optional[float] = None
    development_data: bool


class ModelsResponse(BaseModel):
    total_registered: int
    models: List[ModelSummaryItem]


class PredictRequest(BaseModel):
    crop: str = Field(..., description="Crop name, e.g. 'Onion'")
    market: str = Field(..., description="Market name, e.g. 'Sangli'")
    variety: Optional[str] = Field(None, description="Optional variety name. If omitted, the modeled variety is used.")
    forecast_date: str = Field(..., description="Forecast date in YYYY-MM-DD format, e.g. '2026-08-01'")


class EstimatedPriceRange(BaseModel):
    lower: float
    upper: float


class PredictResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    crop: str
    market: str
    variety_used: str
    forecast_date: str
    predicted_price: float
    estimated_price_range: EstimatedPriceRange
    confidence_score: float
    confidence_level: str
    selected_model: str
    model_scope: str
    trend: str
    explanation: str
    warning_if_low_confidence: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
