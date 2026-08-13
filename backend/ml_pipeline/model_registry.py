"""
model_registry.py

Purpose (in simple language):
------------------------------
Once advanced_models.py has decided which model "wins" for each
(Crop, Market) pair, this file is responsible for two things:

1. Saving the actual trained model file to disk (only when the winning
   model is genuinely a trained ML model - Random Forest, XGBoost, or
   Linear Regression). If the winner is the naive baseline or a moving
   average, there is no model object to save (it's just arithmetic on the
   existing price series) - this is recorded honestly in the registry
   instead of creating a meaningless placeholder file.

2. Writing model_registry.csv - one row per eligible (Crop, Market) pair,
   documenting exactly which model was chosen, how it performed, what
   data it was trained on, and a clear flag that this is all still
   DEVELOPMENT / SYNTHETIC DATA, not a production forecasting result.
"""

import os
import re
import joblib
import pandas as pd

REGISTRY_COLUMNS = [
    "Crop", "Market", "Variety_Used",
    "Selected_Model_Name", "Model_Scope",
    "Model_File_Path",
    "MAE", "RMSE", "MAPE",
    "Improvement_Over_Naive_Pct",
    "N_Train", "N_Test",
    "Train_Start", "Train_End", "Test_Start", "Test_End",
    "Date_Trained",
    "Feature_List",
    "Data_Quality_Score",
    "Development_Data_Flag",
]

# Model scopes are intentionally restricted to these three values only.
VALID_MODEL_SCOPES = {"naive", "crop_specific", "combined"}

# Models in this set are pure arithmetic (no trained object exists) - the
# registry must record "N/A - no trained artifact" for these, never a fake path.
NO_ARTIFACT_MODEL_NAMES = {"Naive_Previous_Price", "Moving_Average_3Day", "Moving_Average_7Day"}


def _sanitize_filename_part(text: str) -> str:
    """Lowercases and strips anything that isn't a safe filename character."""
    text = text.strip().lower().replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def build_model_filename(crop: str, market: str, model_type: str, scope: str) -> str:
    """
    Builds a clean, collision-safe filename.
    Crop-specific example:  onion_sangli_random_forest.joblib
    Combined example:       combined_random_forest.joblib   (one shared file,
                            reused across every pair that selects it - never
                            duplicated per pair, per Phase 3 requirement 7)
    """
    # model_type may already carry a "_Crop_Specific" / "_Combined" suffix
    # (e.g. "Random_Forest_Combined") - strip it here since the filename
    # pattern below adds the scope prefix/context itself, avoiding a
    # redundant name like "combined_random_forest_combined.joblib".
    for suffix in ("_Crop_Specific", "_Combined"):
        if model_type.endswith(suffix):
            model_type = model_type[: -len(suffix)]

    model_type_clean = _sanitize_filename_part(model_type)
    if scope == "combined":
        return f"combined_{model_type_clean}.joblib"
    crop_clean = _sanitize_filename_part(crop)
    market_clean = _sanitize_filename_part(market)
    return f"{crop_clean}_{market_clean}_{model_type_clean}.joblib"


def save_model_artifact(model_object, crop: str, market: str, model_type: str, scope: str,
                          saved_models_dir: str, _combined_cache: dict = None) -> str:
    """
    Saves a trained model object with joblib and returns the path relative
    to saved_models_dir (used in the registry, not an absolute path, so the
    project stays portable).

    For combined models, `_combined_cache` (a dict passed in by the caller)
    ensures the SAME combined model is only written to disk ONCE even
    though many pairs will reference it - preventing duplicate saves.
    """
    filename = build_model_filename(crop, market, model_type, scope)
    full_path = os.path.join(saved_models_dir, filename)

    if scope == "combined" and _combined_cache is not None:
        if filename in _combined_cache:
            return filename  # already saved earlier in this run
        joblib.dump(model_object, full_path)
        _combined_cache[filename] = True
        return filename

    joblib.dump(model_object, full_path)
    return filename


def build_registry_row(crop, market, variety_used, selected_model_name, model_scope,
                        model_file_path, mae, rmse, mape, improvement_pct,
                        n_train, n_test, train_start, train_end, test_start, test_end,
                        feature_list, data_quality_score) -> dict:
    assert model_scope in VALID_MODEL_SCOPES, f"Invalid model scope: {model_scope}"

    return {
        "Crop": crop,
        "Market": market,
        "Variety_Used": variety_used,
        "Selected_Model_Name": selected_model_name,
        "Model_Scope": model_scope,
        "Model_File_Path": model_file_path if model_file_path else "N/A - no trained artifact (formula-based model)",
        "MAE": mae,
        "RMSE": rmse,
        "MAPE": mape,
        "Improvement_Over_Naive_Pct": improvement_pct,
        "N_Train": n_train,
        "N_Test": n_test,
        "Train_Start": train_start,
        "Train_End": train_end,
        "Test_Start": test_start,
        "Test_End": test_end,
        "Date_Trained": str(pd.Timestamp.now()),
        "Feature_List": ";".join(feature_list),
        "Data_Quality_Score": data_quality_score,
        "Development_Data_Flag": "TRUE - trained on synthetic/sample development data, NOT real-world AGMARKNET data",
    }


def write_registry(rows: list, output_path: str) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=REGISTRY_COLUMNS)
    df.to_csv(output_path, index=False)
    return df
