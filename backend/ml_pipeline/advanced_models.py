"""
advanced_models.py

Purpose (in simple language):
------------------------------
This is the Phase 3 centerpiece. For every eligible (Crop, Market) pair it:

1. Trains TWO crop-specific models (Random Forest, XGBoost) using only
   that pair's own history.
2. Trains TWO combined models (Random Forest, XGBoost) using ALL eligible
   pairs' history together, with Crop/Market/Variety/Season properly
   one-hot encoded (never as arbitrary ordered numeric IDs).
3. Re-evaluates the Phase 2 baselines (Naive, best Moving Average, Linear
   Regression) on the EXACT SAME test rows, so every candidate is judged
   on identical, unseen, time-based test data.
4. Applies a documented, conservative selection rule - a complex model
   only replaces the naive baseline if it improves MAE by at least
   MIN_IMPROVEMENT_PCT.
5. Builds a prediction range and a documented confidence score for the
   winning model of every pair.
6. Saves the winning model to disk (only if it's a genuinely trained
   model) and records everything in the model registry.

IMPORTANT: this project currently runs on SYNTHETIC / SAMPLE data (see
docs/data_sources.md and docs/csv_format.md). Every metric, prediction,
and "winning model" in this phase is a DEVELOPMENT/TESTING result used to
validate that the pipeline works correctly - none of it should be read as
real-world forecasting accuracy. This is also stamped directly into
model_registry.csv via the Development_Data_Flag column.
"""

import os
import pandas as pd
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from baseline_models import (
    select_dominant_variety, time_based_split, compute_metrics,
    LINEAR_REGRESSION_FEATURES, MIN_USABLE_ROWS, TEST_FRACTION,
)
from forecast_utils import build_prediction_range, determine_trend, calculate_confidence_score
import model_registry as registry

BASE_DIR = os.path.dirname(__file__)
FEATURES_FILE = os.path.join(BASE_DIR, "data", "features", "engineered_features.csv")
QUALITY_REPORT_FILE = os.path.join(BASE_DIR, "data", "processed", "data_quality_report.csv")
BASELINE_METRICS_FILE = os.path.join(BASE_DIR, "data", "model_outputs", "baseline_metrics.csv")

MODEL_OUTPUTS_DIR = os.path.join(BASE_DIR, "data", "model_outputs")
SAVED_MODELS_DIR = os.path.join(BASE_DIR, "saved_models")

ADVANCED_METRICS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "advanced_metrics.csv")
MODEL_COMPARISON_FILE = os.path.join(MODEL_OUTPUTS_DIR, "model_comparison.csv")
REGISTRY_FILE = os.path.join(MODEL_OUTPUTS_DIR, "model_registry.csv")
ADVANCED_PREDICTIONS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "advanced_predictions.csv")
PREDICTION_RANGES_FILE = os.path.join(MODEL_OUTPUTS_DIR, "prediction_ranges.csv")
CONFIDENCE_SCORES_FILE = os.path.join(MODEL_OUTPUTS_DIR, "confidence_scores.csv")
SKIPPED_PAIRS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "phase3_skipped_pairs.csv")
SUMMARY_FILE = os.path.join(MODEL_OUTPUTS_DIR, "phase3_summary.txt")

# --- Selection rule configuration (documented in docs/model_selection.md) ---
MIN_IMPROVEMENT_PCT = 2.0  # a non-naive model must beat naive's MAE by at least this % to be selected

# --- Feature sets ---
NUMERIC_FEATURES = [
    "Year", "Month", "Day", "Day_Of_Week", "Day_Of_Year", "Quarter",
    "lag_1", "lag_3", "lag_7", "lag_14",
    "rolling_mean_3", "rolling_mean_7", "rolling_mean_14", "rolling_std_7",
    "price_change_1d", "price_change_7d",
]
ARRIVALS_FEATURES = ["arrivals_lag_1", "arrivals_rolling_mean_7"]
CROP_SPECIFIC_CATEGORICAL = ["Season"]
COMBINED_CATEGORICAL = ["Commodity", "Market", "Variety", "District", "Season"]

RF_PARAMS = dict(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
XGB_PARAMS = dict(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42,
                   objective="reg:squarederror", verbosity=0)


def _arrivals_available_for(df: pd.DataFrame) -> bool:
    """Only trust arrivals features if EVERY row in this training slice has them."""
    return "Arrivals_Feature_Available" in df.columns and bool(df["Arrivals_Feature_Available"].all())


def _build_pipeline(categorical_cols, numeric_cols, estimator):
    """
    Builds a preprocessing + model pipeline. Categorical columns (crop,
    market, variety, season, district) are one-hot encoded - NEVER turned
    into arbitrary ordered integers, which would falsely imply e.g.
    "Wheat > Soybean" as a magnitude relationship. handle_unknown='ignore'
    means a category never seen during training (e.g. a new market) is
    safely encoded as all-zeros at prediction time instead of crashing.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
        ],
        remainder="passthrough",
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", estimator)])


def _usable_rows(df: pd.DataFrame, categorical_cols, numeric_cols) -> pd.DataFrame:
    required = numeric_cols + categorical_cols + ["Modal_Price", "Arrival_Date"]
    return df.dropna(subset=required).reset_index(drop=True)


def prepare_pair_data(pair_df: pd.DataFrame):
    """
    Mirrors Phase 2's exact split logic (same dominant variety, same
    time_based_split function) so every model in this phase is compared
    on IDENTICAL test rows to the Phase 2 baselines.
    """
    dominant_variety, variety_df = select_dominant_variety(pair_df)
    numeric_cols = NUMERIC_FEATURES + (ARRIVALS_FEATURES if _arrivals_available_for(variety_df) else [])
    usable_df = _usable_rows(variety_df, CROP_SPECIFIC_CATEGORICAL, numeric_cols)

    if len(usable_df) < MIN_USABLE_ROWS:
        return None

    train_df, test_df, meta = time_based_split(usable_df, TEST_FRACTION)
    if len(train_df) < 5 or len(test_df) < 1:
        return None

    return {
        "dominant_variety": dominant_variety,
        "numeric_cols": numeric_cols,
        "train_df": train_df,
        "test_df": test_df,
        "meta": meta,
    }


def train_crop_specific_models(train_df, test_df, numeric_cols):
    """Fits Linear Regression, Random Forest, and XGBoost on ONE pair's own data."""
    results = {}

    X_train_lr = train_df[LINEAR_REGRESSION_FEATURES]
    y_train = train_df["Modal_Price"]
    X_test_lr = test_df[LINEAR_REGRESSION_FEATURES]

    lr = LinearRegression()
    lr.fit(X_train_lr, y_train)
    results["Linear_Regression"] = (lr, pd.Series(lr.predict(X_test_lr), index=test_df.index))

    for name, estimator in [
        ("Random_Forest_Crop_Specific", RandomForestRegressor(**RF_PARAMS)),
        ("XGBoost_Crop_Specific", XGBRegressor(**XGB_PARAMS)),
    ]:
        pipeline = _build_pipeline(CROP_SPECIFIC_CATEGORICAL, numeric_cols, estimator)
        X_train = train_df[CROP_SPECIFIC_CATEGORICAL + numeric_cols]
        X_test = test_df[CROP_SPECIFIC_CATEGORICAL + numeric_cols]
        pipeline.fit(X_train, y_train)
        preds = pd.Series(pipeline.predict(X_test), index=test_df.index)
        results[name] = (pipeline, preds)

    return results


def train_combined_models(combined_train_df, numeric_cols):
    """Fits ONE combined Random Forest and ONE combined XGBoost across ALL eligible pairs' training data."""
    y_train = combined_train_df["Modal_Price"]
    models = {}
    for name, estimator in [
        ("Random_Forest_Combined", RandomForestRegressor(**RF_PARAMS)),
        ("XGBoost_Combined", XGBRegressor(**XGB_PARAMS)),
    ]:
        pipeline = _build_pipeline(COMBINED_CATEGORICAL, numeric_cols, estimator)
        X_train = combined_train_df[COMBINED_CATEGORICAL + numeric_cols]
        pipeline.fit(X_train, y_train)
        models[name] = pipeline
    return models


def get_phase2_baseline_metrics(baseline_metrics_df, crop, market):
    """Pulls Naive and best-of-MA3/MA7 rows straight from Phase 2's own output file."""
    subset = baseline_metrics_df[(baseline_metrics_df["Crop"] == crop) & (baseline_metrics_df["Market"] == market)]
    naive_row = subset[subset["Model"] == "Naive_Previous_Price"].iloc[0]
    ma3_row = subset[subset["Model"] == "Moving_Average_3Day"].iloc[0]
    ma7_row = subset[subset["Model"] == "Moving_Average_7Day"].iloc[0]
    best_ma_row = ma3_row if ma3_row["MAE"] <= ma7_row["MAE"] else ma7_row
    best_ma_name = "Moving_Average_3Day" if ma3_row["MAE"] <= ma7_row["MAE"] else "Moving_Average_7Day"
    return naive_row, (best_ma_name, best_ma_row)


def select_best_model(candidates: list):
    """
    candidates: list of dicts with keys Model, Scope, MAE, RMSE, MAPE, ...
    Selection rule (see docs/model_selection.md):
      1. Rank all candidates by MAE (lower is better), RMSE as tie-breaker.
      2. Find the naive baseline's MAE.
      3. If the top-ranked candidate IS the naive baseline -> select naive.
      4. If the top-ranked candidate is NOT naive, only accept it if its
         MAE improves on naive's MAE by at least MIN_IMPROVEMENT_PCT.
         Otherwise, fall back to naive - added complexity isn't "free" and
         shouldn't win on a marginal, possibly noise-driven improvement.
    """
    ranked = sorted(candidates, key=lambda c: (c["MAE"], c["RMSE"]))
    best = ranked[0]

    naive_candidate = next(c for c in candidates if c["Model"] == "Naive_Previous_Price")
    naive_mae = naive_candidate["MAE"]

    if best["Model"] == "Naive_Previous_Price":
        improvement_pct = 0.0
        return best, improvement_pct

    improvement_pct = (naive_mae - best["MAE"]) / naive_mae * 100 if naive_mae else 0.0

    if improvement_pct >= MIN_IMPROVEMENT_PCT:
        return best, round(improvement_pct, 2)
    else:
        # Not enough improvement to justify the extra complexity - keep naive.
        return naive_candidate, 0.0


def run_advanced_pipeline():
    os.makedirs(MODEL_OUTPUTS_DIR, exist_ok=True)
    os.makedirs(SAVED_MODELS_DIR, exist_ok=True)

    print(f"Loading engineered features from {FEATURES_FILE}")
    features_df = pd.read_csv(FEATURES_FILE)
    features_df["Arrival_Date"] = pd.to_datetime(features_df["Arrival_Date"], errors="coerce")

    print(f"Loading Phase 1 data quality report from {QUALITY_REPORT_FILE}")
    quality_df = pd.read_csv(QUALITY_REPORT_FILE)

    print(f"Loading Phase 2 baseline metrics from {BASELINE_METRICS_FILE}")
    baseline_metrics_df = pd.read_csv(BASELINE_METRICS_FILE)

    eligible_pairs = quality_df[quality_df["Is_Eligible"] == True][["Crop", "Market"]].values.tolist()
    print(f"{len(eligible_pairs)} eligible (Crop, Market) pairs found in Phase 1 report")

    # --- Pass 1: prepare per-pair train/test splits (needed before combined training) ---
    pair_data = {}
    skipped_rows = []

    for crop, market in eligible_pairs:
        pair_df = features_df[(features_df["Commodity"] == crop) & (features_df["Market"] == market)]
        if len(pair_df) == 0:
            skipped_rows.append({"Crop": crop, "Market": market, "Reason": "No engineered feature rows found"})
            continue

        prepared = prepare_pair_data(pair_df)
        if prepared is None:
            skipped_rows.append({"Crop": crop, "Market": market, "Reason": "Insufficient usable rows after dropping NaN feature rows"})
            continue

        pair_data[(crop, market)] = prepared

    # Also log any pairs the Phase 1 report marked NOT eligible, for completeness.
    ineligible = quality_df[quality_df["Is_Eligible"] == False]
    for _, row in ineligible.iterrows():
        skipped_rows.append({"Crop": row["Crop"], "Market": row["Market"], "Reason": f"Not eligible per Phase 1 report: {row['Reasons_If_Ineligible']}"})

    print(f"{len(pair_data)} pairs have sufficient data for Phase 3 modeling")

    # --- Determine combined feature set: arrivals only if reliable for EVERY pair being combined ---
    combined_arrivals_ok = all(_arrivals_available_for(p["train_df"]) for p in pair_data.values()) if pair_data else False
    combined_numeric_cols = NUMERIC_FEATURES + (ARRIVALS_FEATURES if combined_arrivals_ok else [])
    if not combined_arrivals_ok:
        print("Note: arrivals data not reliably available across all pairs - combined model excludes arrivals features.")

    # --- Build combined train/test sets from each pair's OWN split boundary ---
    combined_train_parts, combined_test_parts = [], []
    for (crop, market), prepared in pair_data.items():
        combined_train_parts.append(prepared["train_df"])
        combined_test_parts.append(prepared["test_df"])
    combined_train_df = pd.concat(combined_train_parts, ignore_index=False) if combined_train_parts else pd.DataFrame()
    combined_test_df = pd.concat(combined_test_parts, ignore_index=False) if combined_test_parts else pd.DataFrame()

    print(f"Combined training set: {len(combined_train_df)} rows across {len(pair_data)} pairs")
    combined_models = {}
    if len(combined_train_df) > 0:
        combined_models = train_combined_models(combined_train_df, combined_numeric_cols)
        for name, pipeline in combined_models.items():
            X_test = combined_test_df[COMBINED_CATEGORICAL + combined_numeric_cols]
            combined_test_df[f"__pred__{name}"] = pipeline.predict(X_test)

    # --- Pass 2: per-pair crop-specific models, fair comparison, selection, registry ---
    advanced_metrics_rows = []
    comparison_rows = []
    prediction_rows = []
    range_rows = []
    confidence_rows = []
    registry_rows = []
    combined_artifact_cache = {}

    quality_lookup = quality_df.set_index(["Crop", "Market"])

    for (crop, market), prepared in pair_data.items():
        train_df, test_df = prepared["train_df"], prepared["test_df"]
        meta = prepared["meta"]
        numeric_cols = prepared["numeric_cols"]
        dominant_variety = prepared["dominant_variety"]
        actual_test = test_df["Modal_Price"]

        # --- Phase 2 baselines, re-evaluated on these exact same test rows ---
        naive_row, (best_ma_name, ma_row) = get_phase2_baseline_metrics(baseline_metrics_df, crop, market)

        candidates = [
            {"Model": "Naive_Previous_Price", "Scope": "naive",
             "MAE": naive_row["MAE"], "RMSE": naive_row["RMSE"], "MAPE": naive_row["MAPE"]},
            {"Model": best_ma_name, "Scope": "naive",
             "MAE": ma_row["MAE"], "RMSE": ma_row["RMSE"], "MAPE": ma_row["MAPE"]},
        ]

        # --- Crop-specific models (Linear Regression, Random Forest, XGBoost) ---
        crop_specific = train_crop_specific_models(train_df, test_df, numeric_cols)
        crop_specific_scopes = {
            "Linear_Regression": "crop_specific",
            "Random_Forest_Crop_Specific": "crop_specific",
            "XGBoost_Crop_Specific": "crop_specific",
        }
        for name, (model_obj, preds) in crop_specific.items():
            m = compute_metrics(actual_test, preds)
            candidates.append({"Model": name, "Scope": crop_specific_scopes[name], "MAE": m["MAE"], "RMSE": m["RMSE"], "MAPE": m["MAPE"],
                                "_model_obj": model_obj, "_preds": preds})

        # --- Combined models, filtered back to this pair's own test rows ---
        pair_test_mask = (combined_test_df["Commodity"] == crop) & (combined_test_df["Market"] == market)
        for name in ["Random_Forest_Combined", "XGBoost_Combined"]:
            pair_combined_preds = combined_test_df.loc[pair_test_mask, f"__pred__{name}"]
            pair_combined_preds.index = test_df.index  # align index for compute_metrics
            m = compute_metrics(actual_test, pair_combined_preds)
            candidates.append({"Model": name, "Scope": "combined", "MAE": m["MAE"], "RMSE": m["RMSE"], "MAPE": m["MAPE"],
                                "_model_obj": combined_models.get(name), "_preds": pair_combined_preds})

        # record every candidate's metrics for full transparency
        for c in candidates:
            advanced_metrics_rows.append({
                "Crop": crop, "Market": market, "Variety_Used": dominant_variety,
                "Model": c["Model"], "Scope": c["Scope"],
                "MAE": c["MAE"], "RMSE": c["RMSE"], "MAPE": c["MAPE"],
                "N_Train": meta["n_train"], "N_Test": meta["n_test"],
                "Test_Start": meta["test_start"], "Test_End": meta["test_end"],
            })

        # --- Selection ---
        winner, improvement_pct = select_best_model(candidates)
        comparison_rows.append({
            "Crop": crop, "Market": market,
            "Naive_MAE": naive_row["MAE"], "Best_MA_Model": best_ma_name, "Best_MA_MAE": ma_row["MAE"],
            "Selected_Model": winner["Model"], "Selected_Scope": winner["Scope"],
            "Selected_MAE": winner["MAE"], "Selected_RMSE": winner["RMSE"], "Selected_MAPE": winner["MAPE"],
            "Improvement_Over_Naive_Pct": improvement_pct,
            "Min_Improvement_Threshold_Pct": MIN_IMPROVEMENT_PCT,
        })

        # --- Save artifact + registry row ---
        requires_artifact = winner["Model"] not in registry.NO_ARTIFACT_MODEL_NAMES
        model_file_path = None
        if requires_artifact:
            model_file_path = registry.save_model_artifact(
                winner["_model_obj"], crop, market, winner["Model"], winner["Scope"],
                SAVED_MODELS_DIR, _combined_cache=combined_artifact_cache,
            )

        feature_list = (LINEAR_REGRESSION_FEATURES if winner["Model"] == "Linear_Regression"
                         else (CROP_SPECIFIC_CATEGORICAL + numeric_cols if winner["Scope"] == "crop_specific"
                         else (COMBINED_CATEGORICAL + combined_numeric_cols if winner["Scope"] == "combined" else [])))

        data_quality_score = quality_lookup.loc[(crop, market), "Overall_Score"]
        freshness_score = quality_lookup.loc[(crop, market), "Freshness_Score"]

        registry_rows.append(registry.build_registry_row(
            crop=crop, market=market, variety_used=dominant_variety,
            selected_model_name=winner["Model"], model_scope=winner["Scope"],
            model_file_path=model_file_path,
            mae=winner["MAE"], rmse=winner["RMSE"], mape=winner["MAPE"],
            improvement_pct=improvement_pct,
            n_train=meta["n_train"], n_test=meta["n_test"],
            train_start=meta["train_start"], train_end=meta["train_end"],
            test_start=meta["test_start"], test_end=meta["test_end"],
            feature_list=feature_list, data_quality_score=data_quality_score,
        ))

        # --- Predictions for every test row using the WINNING model ---
        winner_preds = winner.get("_preds")
        if winner_preds is None:
            # naive / MA winner - recompute its formula-based predictions directly
            winner_preds = test_df["lag_1"] if winner["Model"] == "Naive_Previous_Price" else (
                test_df["rolling_mean_3"] if winner["Model"] == "Moving_Average_3Day" else test_df["rolling_mean_7"])

        for idx in test_df.index:
            prediction_rows.append({
                "Crop": crop, "Market": market, "Variety_Used": dominant_variety,
                "Arrival_Date": test_df.loc[idx, "Arrival_Date"].date(),
                "Actual_Modal_Price": test_df.loc[idx, "Modal_Price"],
                "Predicted_Modal_Price": round(float(winner_preds.loc[idx]), 2) if pd.notna(winner_preds.loc[idx]) else None,
                "Selected_Model": winner["Model"], "Selected_Scope": winner["Scope"],
            })

        # --- Prediction range + trend, using the LATEST test row as "current" forecast ---
        latest_idx = test_df.index[-1]
        latest_predicted_price = float(winner_preds.loc[latest_idx]) if pd.notna(winner_preds.loc[latest_idx]) else float(actual_test.loc[latest_idx])
        last_known_price = float(test_df.loc[latest_idx, "lag_1"]) if pd.notna(test_df.loc[latest_idx, "lag_1"]) else float(actual_test.iloc[-2]) if len(actual_test) > 1 else latest_predicted_price

        lower, upper = build_prediction_range(latest_predicted_price, actual_test, winner_preds)
        trend = determine_trend(latest_predicted_price, last_known_price)

        range_rows.append({
            "Crop": crop, "Market": market, "Variety_Used": dominant_variety,
            "As_Of_Date": test_df.loc[latest_idx, "Arrival_Date"].date(),
            "Predicted_Modal_Price": round(latest_predicted_price, 2),
            "Estimated_Lower_Price": lower, "Estimated_Upper_Price": upper,
            "Trend": trend, "Selected_Model": winner["Model"],
            "Method_Note": "Range built from 10th-90th percentile of the selected model's own test-set residuals. Not a guaranteed statistical confidence interval.",
        })

        # --- Confidence score ---
        recent_prices = test_df["Modal_Price"].tail(14)
        confidence = calculate_confidence_score(
            mape=winner["MAPE"], data_quality_score=data_quality_score, freshness_score=freshness_score,
            n_train=meta["n_train"], recent_prices=recent_prices,
        )
        confidence_rows.append({"Crop": crop, "Market": market, **confidence})

        print(f"{crop} @ {market}: selected {winner['Model']} ({winner['Scope']}), "
              f"MAE={winner['MAE']}, improvement over naive={improvement_pct}%, "
              f"confidence={confidence['Overall_Confidence_Score']} ({confidence['Confidence_Level']})")

    # --- Save all output files ---
    pd.DataFrame(advanced_metrics_rows).to_csv(ADVANCED_METRICS_FILE, index=False)
    pd.DataFrame(comparison_rows).to_csv(MODEL_COMPARISON_FILE, index=False)
    registry.write_registry(registry_rows, REGISTRY_FILE)
    pd.DataFrame(prediction_rows).to_csv(ADVANCED_PREDICTIONS_FILE, index=False)
    pd.DataFrame(range_rows).to_csv(PREDICTION_RANGES_FILE, index=False)
    pd.DataFrame(confidence_rows).to_csv(CONFIDENCE_SCORES_FILE, index=False)
    pd.DataFrame(skipped_rows, columns=["Crop", "Market", "Reason"]).to_csv(SKIPPED_PAIRS_FILE, index=False)

    # --- Summary ---
    comparison_df = pd.DataFrame(comparison_rows)
    scope_counts = comparison_df["Selected_Scope"].value_counts().to_dict() if len(comparison_df) else {}
    summary_lines = [
        "KrushiMitra AI - Phase 3 Advanced Model Summary",
        "*** RESULTS ARE FROM SYNTHETIC / SAMPLE DEVELOPMENT DATA - NOT REAL-WORLD ACCURACY ***",
        f"Generated: {pd.Timestamp.now()}",
        "",
        f"Total (Crop, Market) pairs in Phase 1 report: {len(quality_df)}",
        f"Pairs modeled in Phase 3: {len(pair_data)}",
        f"Pairs skipped: {len(skipped_rows)}",
        "",
        f"Selection rule: MAE primary, RMSE tie-breaker, minimum {MIN_IMPROVEMENT_PCT}% MAE "
        f"improvement over naive baseline required before a complex model replaces it.",
        "",
        "Selected model scope breakdown:",
    ]
    for scope, count in scope_counts.items():
        summary_lines.append(f"  {scope}: {count} pair(s)")

    summary_lines.append("")
    summary_lines.append("Per-pair selection:")
    for _, row in comparison_df.iterrows():
        summary_lines.append(
            f"  {row['Crop']} @ {row['Market']}: {row['Selected_Model']} "
            f"(MAE={row['Selected_MAE']}, improvement over naive={row['Improvement_Over_Naive_Pct']}%)"
        )

    summary_text = "\n".join(summary_lines)
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary_text)

    print("\n" + "=" * 70)
    print(summary_text)
    print("=" * 70)

    return {
        "advanced_metrics": advanced_metrics_rows,
        "comparison": comparison_rows,
        "registry": registry_rows,
        "predictions": prediction_rows,
        "ranges": range_rows,
        "confidence": confidence_rows,
        "skipped": skipped_rows,
    }


if __name__ == "__main__":
    run_advanced_pipeline()
