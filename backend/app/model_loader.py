"""
model_loader.py

Purpose (in simple language):
------------------------------
This is the ONLY place that touches disk for model-related data. It:

1. Loads the Phase 3 model registry, prediction ranges, confidence scores,
   and data-quality report ONCE, when the app starts (see main.py's
   startup event) - not on every request.
2. Loads each trained model FILE (.joblib) lazily - only the first time
   it's actually needed for a prediction - and then keeps it in memory
   for every later request that needs it (a cache), so a busy endpoint
   doesn't re-read the same file from disk repeatedly.
3. Since the combined Random Forest/XGBoost artifact is shared by
   multiple (Crop, Market) pairs, the cache is keyed by FILE PATH, not by
   pair - so it's only ever loaded into memory once no matter how many
   pairs use it.

This module does not modify anything in ml_pipeline/ - it only reads the
CSV/joblib outputs Phase 1-3 already produced.
"""

import os, sys
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

import os
import logging
import joblib
import pandas as pd
import json

import config

logger = logging.getLogger("krushimitra.model_loader")


class ModelRegistryManager:
    def __init__(self):
        self.registry_df: pd.DataFrame = pd.DataFrame()
        self.ranges_df: pd.DataFrame = pd.DataFrame()
        self.confidence_df: pd.DataFrame = pd.DataFrame()
        self.quality_df: pd.DataFrame = pd.DataFrame()
        self.features_df: pd.DataFrame = pd.DataFrame()
        self.canonical_crops: list = []
        self.canonical_markets: list = []
        self._model_cache: dict = {}
        self._loaded = False

    def load(self):
        """Reads every Phase 1-3 output file exactly once. Call this at app startup."""
        logger.info("Loading model registry and supporting data files...")

        self.registry_df = pd.read_csv(config.MODEL_REGISTRY_FILE)
        self.ranges_df = pd.read_csv(config.PREDICTION_RANGES_FILE)
        self.confidence_df = pd.read_csv(config.CONFIDENCE_SCORES_FILE)
        self.quality_df = pd.read_csv(config.DATA_QUALITY_REPORT_FILE)
        self.features_df = pd.read_csv(config.ENGINEERED_FEATURES_FILE)
        self.features_df["Arrival_Date"] = pd.to_datetime(self.features_df["Arrival_Date"], errors="coerce")

        with open(config.CROPS_CONFIG_FILE) as f:
            self.canonical_crops = [c["canonical_name"] for c in json.load(f)["crops"]]
        with open(config.MARKETS_CONFIG_FILE) as f:
            self.canonical_markets = [m["canonical_name"] for m in json.load(f)["markets"]]

        self._loaded = True
        logger.info(
            f"Loaded model registry: {len(self.registry_df)} pairs, "
            f"{len(self.canonical_crops)} crops, {len(self.canonical_markets)} markets"
        )

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def models_loaded_count(self) -> int:
        """How many DISTINCT model artifact files are currently cached in memory."""
        return len(self._model_cache)

    def get_registry_row(self, crop: str, market: str):
        subset = self.registry_df[(self.registry_df["Crop"] == crop) & (self.registry_df["Market"] == market)]
        if len(subset) == 0:
            return None
        return subset.iloc[0]

    def get_range_row(self, crop: str, market: str):
        subset = self.ranges_df[(self.ranges_df["Crop"] == crop) & (self.ranges_df["Market"] == market)]
        return subset.iloc[0] if len(subset) else None

    def get_confidence_row(self, crop: str, market: str):
        subset = self.confidence_df[(self.confidence_df["Crop"] == crop) & (self.confidence_df["Market"] == market)]
        return subset.iloc[0] if len(subset) else None

    def get_quality_row(self, crop: str, market: str):
        subset = self.quality_df[(self.quality_df["Crop"] == crop) & (self.quality_df["Market"] == market)]
        return subset.iloc[0] if len(subset) else None

    def is_eligible(self, crop: str, market: str) -> bool:
        row = self.get_quality_row(crop, market)
        return bool(row["Is_Eligible"]) if row is not None else False

    def get_known_varieties(self, crop: str, market: str) -> list:
        subset = self.features_df[(self.features_df["Commodity"] == crop) & (self.features_df["Market"] == market)]
        return sorted(subset["Variety"].unique().tolist())

    def get_latest_feature_row(self, crop: str, market: str, variety: str):
        subset = self.features_df[
            (self.features_df["Commodity"] == crop)
            & (self.features_df["Market"] == market)
            & (self.features_df["Variety"] == variety)
        ].sort_values("Arrival_Date")
        if len(subset) == 0:
            return None
        return subset.iloc[-1]

    def get_model(self, file_path: str):
        """
        Lazily loads a .joblib model the FIRST time it's requested, then
        reuses the in-memory object on every subsequent call - this is
        what satisfies "load lazily, reuse loaded models, avoid loading
        on every request".
        """
        if file_path in self._model_cache:
            return self._model_cache[file_path]

        full_path = os.path.join(config.SAVED_MODELS_DIR, file_path)
        logger.info(f"Loading model artifact from disk (first use): {file_path}")
        model = joblib.load(full_path)
        self._model_cache[file_path] = model
        return model

    def list_models_summary(self) -> list:
        """Used by GET /models - deliberately excludes Model_File_Path (internal detail)."""
        rows = []
        for _, row in self.registry_df.iterrows():
            rows.append({
                "crop": row["Crop"],
                "market": row["Market"],
                "variety_used": row["Variety_Used"],
                "selected_model": row["Selected_Model_Name"],
                "model_type": row["Model_Scope"],
                "mae": float(row["MAE"]) if pd.notna(row["MAE"]) else None,
                "rmse": float(row["RMSE"]) if pd.notna(row["RMSE"]) else None,
                "mape": float(row["MAPE"]) if pd.notna(row["MAPE"]) else None,
                "development_data": True,  # Development_Data_Flag is always TRUE in the current registry
            })
        return rows


# Single shared instance for the whole app's lifetime (populated at startup in main.py)
registry_manager = ModelRegistryManager()
