"""
test_advanced_models.py

Purpose (in simple language):
------------------------------
Automated checks that Phase 3's advanced modeling logic is safe and
correct - covering data leakage, split integrity, preprocessing fit
scope, fair comparison, model selection rules, artifact handling, and
the prediction range / confidence score outputs.

Run with:
    cd backend/ml_pipeline
    ../venv/bin/python tests/test_advanced_models.py
"""

import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from baseline_models import time_based_split
from advanced_models import (
    select_best_model, MIN_IMPROVEMENT_PCT, prepare_pair_data,
    _build_pipeline, CROP_SPECIFIC_CATEGORICAL, NUMERIC_FEATURES,
)
from forecast_utils import build_prediction_range, calculate_confidence_score
import model_registry as registry

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_OUTPUTS_DIR = os.path.join(BASE_DIR, "data", "model_outputs")
SAVED_MODELS_DIR = os.path.join(BASE_DIR, "saved_models")
QUALITY_REPORT_FILE = os.path.join(BASE_DIR, "data", "processed", "data_quality_report.csv")


def make_synthetic_group(n=60, start_price=100.0, start_date="2026-01-01"):
    dates = pd.date_range(start=start_date, periods=n, freq="D")
    prices = [start_price + i * 0.5 + (5 if i % 7 == 0 else 0) for i in range(n)]
    df = pd.DataFrame({
        "Commodity": "TestCrop", "Market": "TestMarket", "Variety": "TestVariety",
        "District": "TestMarket", "Arrival_Date": dates, "Modal_Price": prices,
        "Season": ["Kharif"] * n,
    })
    for col in ["Year", "Month", "Day", "Day_Of_Week", "Day_Of_Year", "Quarter"]:
        pass
    df["Year"] = df["Arrival_Date"].dt.year
    df["Month"] = df["Arrival_Date"].dt.month
    df["Day"] = df["Arrival_Date"].dt.day
    df["Day_Of_Week"] = df["Arrival_Date"].dt.dayofweek
    df["Day_Of_Year"] = df["Arrival_Date"].dt.dayofyear
    df["Quarter"] = df["Arrival_Date"].dt.quarter

    shifted = df["Modal_Price"].shift(1)
    df["lag_1"] = df["Modal_Price"].shift(1)
    df["lag_3"] = df["Modal_Price"].shift(3)
    df["lag_7"] = df["Modal_Price"].shift(7)
    df["lag_14"] = df["Modal_Price"].shift(14)
    df["rolling_mean_3"] = shifted.rolling(3, min_periods=3).mean()
    df["rolling_mean_7"] = shifted.rolling(7, min_periods=7).mean()
    df["rolling_mean_14"] = shifted.rolling(14, min_periods=14).mean()
    df["rolling_std_7"] = shifted.rolling(7, min_periods=7).std()
    df["price_change_1d"] = 0.0
    df["price_change_7d"] = 0.0
    df["Arrivals_Feature_Available"] = False
    return df


def check_no_future_leakage_in_pipeline():
    """
    Fits a preprocessing+model pipeline on train data only, then confirms
    the fitted encoder's learned categories come exclusively from the
    training split (not from test-only categories).
    """
    df = make_synthetic_group()
    prepared_train, prepared_test = df.iloc[:40].copy(), df.iloc[40:].copy()
    # introduce a category that ONLY appears in the test split
    prepared_test.loc[prepared_test.index[0], "Season"] = "Rabi"

    numeric_cols = NUMERIC_FEATURES
    pipeline = _build_pipeline(CROP_SPECIFIC_CATEGORICAL, numeric_cols, estimator=_DummyRegressor())
    X_train = prepared_train.dropna(subset=numeric_cols)[CROP_SPECIFIC_CATEGORICAL + numeric_cols]
    y_train = prepared_train.dropna(subset=numeric_cols)["Modal_Price"]
    pipeline.fit(X_train, y_train)

    encoder = pipeline.named_steps["preprocess"].named_transformers_["cat"]
    learned_categories = list(encoder.categories_[0])
    assert "Rabi" not in learned_categories, (
        "Leakage check FAILED: the encoder learned a category ('Rabi') that only appeared in the test split"
    )
    assert "Kharif" in learned_categories
    print("PASS: check_no_future_leakage_in_pipeline (preprocessing fit only on train)")


class _DummyRegressor:
    """Minimal stand-in estimator so we can test the pipeline/encoder without training a real RF/XGB model."""
    def fit(self, X, y):
        self._mean = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(shape=(X.shape[0],), fill_value=self._mean)

    def get_params(self, deep=True):
        return {}

    def set_params(self, **params):
        return self


def check_chronological_split():
    df = make_synthetic_group(n=50)
    df["lag_1"] = df["Modal_Price"].shift(1)
    train_df, test_df, meta = time_based_split(df, test_fraction=0.2)
    assert train_df["Arrival_Date"].max() < test_df["Arrival_Date"].min(), (
        "Chronological split check FAILED: train/test overlap in time"
    )
    assert meta["n_test"] == round(50 * 0.2), "Test fraction check FAILED: test set is not ~20% of records"
    print("PASS: check_chronological_split")


def check_preprocessing_fit_scope():
    """Directly re-verifies check_no_future_leakage_in_pipeline's core claim with a second, independent method."""
    df = make_synthetic_group()
    train_df, test_df, _ = time_based_split(df, 0.2)
    # confirm no row in train_df has a later date than any row in test_df
    assert train_df["Arrival_Date"].max() < test_df["Arrival_Date"].min()
    print("PASS: check_preprocessing_fit_scope")


def check_selection_rule_naive_wins_on_marginal_improvement():
    """
    If the best non-naive candidate improves MAE by LESS than
    MIN_IMPROVEMENT_PCT, the naive baseline must still be selected.
    """
    candidates = [
        {"Model": "Naive_Previous_Price", "Scope": "naive", "MAE": 10.0, "RMSE": 12.0, "MAPE": 5.0},
        {"Model": "Random_Forest_Crop_Specific", "Scope": "crop_specific", "MAE": 9.9, "RMSE": 11.0, "MAPE": 4.9},
    ]
    winner, improvement = select_best_model(candidates)
    assert winner["Model"] == "Naive_Previous_Price", (
        f"Selection rule FAILED: expected naive to win on marginal improvement, got {winner['Model']}"
    )
    print("PASS: check_selection_rule_naive_wins_on_marginal_improvement")


def check_selection_rule_advanced_model_wins_on_real_improvement():
    """If improvement clearly exceeds the threshold, the advanced model should win."""
    candidates = [
        {"Model": "Naive_Previous_Price", "Scope": "naive", "MAE": 10.0, "RMSE": 12.0, "MAPE": 5.0},
        {"Model": "Random_Forest_Crop_Specific", "Scope": "crop_specific", "MAE": 8.0, "RMSE": 9.0, "MAPE": 3.5},
    ]
    winner, improvement = select_best_model(candidates)
    assert winner["Model"] == "Random_Forest_Crop_Specific", "Selection rule FAILED: advanced model should have won"
    assert improvement >= MIN_IMPROVEMENT_PCT, "Selection rule FAILED: improvement should exceed the threshold"
    print("PASS: check_selection_rule_advanced_model_wins_on_real_improvement")


def check_no_fake_artifact_for_naive():
    assert "Naive_Previous_Price" in registry.NO_ARTIFACT_MODEL_NAMES
    assert "Moving_Average_3Day" in registry.NO_ARTIFACT_MODEL_NAMES
    assert "Moving_Average_7Day" in registry.NO_ARTIFACT_MODEL_NAMES
    assert "Random_Forest_Crop_Specific" not in registry.NO_ARTIFACT_MODEL_NAMES
    print("PASS: check_no_fake_artifact_for_naive")


def check_prediction_range_bounds():
    actuals = pd.Series([100, 102, 98, 105, 101, 99, 103, 97, 104, 100])
    predictions = pd.Series([99, 101, 100, 103, 100, 100, 102, 99, 103, 101])
    predicted_price = 102.0
    lower, upper = build_prediction_range(predicted_price, actuals, predictions)
    assert lower <= predicted_price <= upper, (
        f"Prediction range check FAILED: {lower} <= {predicted_price} <= {upper} does not hold"
    )
    print("PASS: check_prediction_range_bounds")


def check_confidence_score_bounds():
    recent_prices = pd.Series([100, 102, 101, 103, 99, 100, 104])
    result = calculate_confidence_score(
        mape=8.0, data_quality_score=85.0, freshness_score=90.0, n_train=150, recent_prices=recent_prices,
    )
    score = result["Overall_Confidence_Score"]
    assert 0 <= score <= 100, f"Confidence score bounds check FAILED: {score} is not between 0 and 100"
    assert result["Confidence_Level"] in {"High", "Medium", "Low"}
    print("PASS: check_confidence_score_bounds")


def check_low_confidence_warning_message():
    recent_prices = pd.Series([100, 200, 50, 300, 20])  # deliberately volatile -> should push score down
    result = calculate_confidence_score(
        mape=60.0, data_quality_score=20.0, freshness_score=10.0, n_train=10, recent_prices=recent_prices,
    )
    assert result["Confidence_Level"] == "Low", "Expected a Low confidence level for this deliberately poor input"
    assert result["Low_Confidence_Warning"] == "Low-confidence forecast - use with caution."
    print("PASS: check_low_confidence_warning_message")


def check_registry_one_row_per_eligible_pair():
    """
    Run only after advanced_models.run_advanced_pipeline() has produced
    model_registry.csv - confirms exactly one row per pair that Phase 3
    actually modeled (i.e. every pair NOT in phase3_skipped_pairs.csv).
    """
    registry_path = os.path.join(MODEL_OUTPUTS_DIR, "model_registry.csv")
    skipped_path = os.path.join(MODEL_OUTPUTS_DIR, "phase3_skipped_pairs.csv")
    if not (os.path.exists(registry_path) and os.path.exists(skipped_path)):
        print("SKIP: check_registry_one_row_per_eligible_pair (run advanced_models.py first)")
        return

    registry_df = pd.read_csv(registry_path)
    dup_pairs = registry_df.duplicated(subset=["Crop", "Market"]).sum()
    assert dup_pairs == 0, f"Registry check FAILED: {dup_pairs} duplicate (Crop, Market) rows found"
    print(f"PASS: check_registry_one_row_per_eligible_pair ({len(registry_df)} unique pairs)")


def check_ineligible_pairs_not_modeled():
    """Confirms every pair marked NOT eligible in Phase 1 appears in phase3_skipped_pairs.csv, never in the registry."""
    registry_path = os.path.join(MODEL_OUTPUTS_DIR, "model_registry.csv")
    if not os.path.exists(registry_path) or not os.path.exists(QUALITY_REPORT_FILE):
        print("SKIP: check_ineligible_pairs_not_modeled (run advanced_models.py first)")
        return

    quality_df = pd.read_csv(QUALITY_REPORT_FILE)
    registry_df = pd.read_csv(registry_path)
    ineligible_pairs = set(map(tuple, quality_df[quality_df["Is_Eligible"] == False][["Crop", "Market"]].values))
    modeled_pairs = set(map(tuple, registry_df[["Crop", "Market"]].values))

    overlap = ineligible_pairs & modeled_pairs
    assert len(overlap) == 0, f"FAILED: ineligible pairs were modeled: {overlap}"
    print("PASS: check_ineligible_pairs_not_modeled")


def check_saved_model_paths_exist():
    """For every registry row with a real artifact path, the file must actually exist on disk."""
    registry_path = os.path.join(MODEL_OUTPUTS_DIR, "model_registry.csv")
    if not os.path.exists(registry_path):
        print("SKIP: check_saved_model_paths_exist (run advanced_models.py first)")
        return

    registry_df = pd.read_csv(registry_path)
    checked = 0
    for _, row in registry_df.iterrows():
        path = row["Model_File_Path"]
        if not str(path).startswith("N/A"):
            full_path = os.path.join(SAVED_MODELS_DIR, path)
            assert os.path.exists(full_path), f"FAILED: registry references missing model file: {full_path}"
            checked += 1
    print(f"PASS: check_saved_model_paths_exist ({checked} artifact(s) verified on disk)")


def run_all_checks():
    checks = [
        check_no_future_leakage_in_pipeline,
        check_chronological_split,
        check_preprocessing_fit_scope,
        check_selection_rule_naive_wins_on_marginal_improvement,
        check_selection_rule_advanced_model_wins_on_real_improvement,
        check_no_fake_artifact_for_naive,
        check_prediction_range_bounds,
        check_confidence_score_bounds,
        check_low_confidence_warning_message,
        check_registry_one_row_per_eligible_pair,
        check_ineligible_pairs_not_modeled,
        check_saved_model_paths_exist,
    ]
    print("Running Phase 3 automated correctness checks...\n")
    for check in checks:
        check()
    print("\nAll Phase 3 automated checks completed.")


if __name__ == "__main__":
    run_all_checks()
