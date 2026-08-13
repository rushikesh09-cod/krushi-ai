"""
config.py

Purpose (in simple language):
------------------------------
Central place for two things:
1. App metadata (name, version) used by the root endpoint and Swagger docs.
2. File paths pointing INTO the existing, unchanged ml_pipeline/ folder -
   this API is a thin serving layer on top of Phase 1-3's outputs, not a
   replacement for them. Nothing in ml_pipeline/ is modified by this file.

It also wires up sys.path so this app can import a few small, stable
constants directly from ml_pipeline (e.g. the feature-column lists used
when building Random Forest / XGBoost inputs) - this guarantees the API
always uses the EXACT SAME feature definitions the models were trained
with, rather than a second, potentially-drifting copy of that list.
"""

import os
import sys

APP_NAME = "KrushiMitra AI"
APP_VERSION = "1.0"

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_PIPELINE_DIR = os.path.join(BACKEND_DIR, "ml_pipeline")

# Make ml_pipeline's modules importable (advanced_models, baseline_models,
# standardization, forecast_utils, model_registry) without copying any code.
if ML_PIPELINE_DIR not in sys.path:
    sys.path.insert(0, ML_PIPELINE_DIR)

# --- Phase 1-3 output files this API reads from (read-only) ---
MODEL_REGISTRY_FILE = os.path.join(ML_PIPELINE_DIR, "data", "model_outputs", "model_registry.csv")
PREDICTION_RANGES_FILE = os.path.join(ML_PIPELINE_DIR, "data", "model_outputs", "prediction_ranges.csv")
CONFIDENCE_SCORES_FILE = os.path.join(ML_PIPELINE_DIR, "data", "model_outputs", "confidence_scores.csv")
DATA_QUALITY_REPORT_FILE = os.path.join(ML_PIPELINE_DIR, "data", "processed", "data_quality_report.csv")
ENGINEERED_FEATURES_FILE = os.path.join(ML_PIPELINE_DIR, "data", "features", "engineered_features.csv")
SAVED_MODELS_DIR = os.path.join(ML_PIPELINE_DIR, "saved_models")

CROPS_CONFIG_FILE = os.path.join(BACKEND_DIR, "..", "config", "crops.json")
MARKETS_CONFIG_FILE = os.path.join(BACKEND_DIR, "..", "config", "markets.json")

LOG_LEVEL = "INFO"
