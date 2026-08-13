"""
baseline_models.py

Purpose (in simple language):
------------------------------
Before trying any advanced ML (Random Forest, XGBoost - later phases), we
must first establish simple BASELINE models. If a complex model can't beat
these simple ones, the complex model isn't actually adding value. This file
trains and evaluates four baselines for every eligible (Crop, Market) pair:

1. Naive baseline       - "tomorrow's price = today's price" (lag_1)
2. 3-day moving average - "tomorrow's price = average of last 3 records"
3. 7-day moving average - "tomorrow's price = average of last 7 records"
4. Linear Regression    - a simple model using all engineered features

Design decision - one variety per (Crop, Market) pair:
Phase 1's data-quality report and eligibility list operate at the
(Crop, Market) level, not (Crop, Market, Variety). Since a single clean
price series is needed for a fair time-based evaluation, we pick the
DOMINANT variety (the one with the most historical records) for each
eligible (Crop, Market) pair and model that series. This choice is logged
transparently in the output files. Full multi-variety modeling can be
revisited in a later phase if needed.

Time-based split (never random):
- Sort the series by date.
- The LAST 20% of records (by date) become the test set.
- Everything before that is the training set.
- This mirrors how the system will actually be used: train on the past,
  predict the near future - never let the model "see" test-period data
  during training.

Evaluation metrics: MAE, RMSE, MAPE (MAPE skips/flags rows where the
actual price is at or near zero, since dividing by ~0 produces meaningless
or infinite error values).
"""

import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

BASE_DIR = os.path.dirname(__file__)
FEATURES_FILE = os.path.join(BASE_DIR, "data", "features", "engineered_features.csv")
QUALITY_REPORT_FILE = os.path.join(BASE_DIR, "data", "processed", "data_quality_report.csv")

MODEL_OUTPUTS_DIR = os.path.join(BASE_DIR, "data", "model_outputs")
METRICS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "baseline_metrics.csv")
PREDICTIONS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "baseline_predictions.csv")
SKIPPED_PAIRS_FILE = os.path.join(MODEL_OUTPUTS_DIR, "skipped_pairs.csv")
SUMMARY_FILE = os.path.join(MODEL_OUTPUTS_DIR, "phase2_summary.txt")

TEST_FRACTION = 0.20

# Rows where the actual price is below this are excluded from MAPE
# specifically (MAE/RMSE still use them) - dividing by a near-zero price
# produces a meaningless, often huge percentage error.
MAPE_SAFE_MIN_PRICE = 1.0

# Minimum usable (non-NaN-feature) rows required before we'll even attempt
# a time-based split and model fit for a pair.
MIN_USABLE_ROWS = 20

# Feature columns used by Linear Regression. Deliberately excludes any
# identifier/text columns (Commodity/Market/Variety are constant within a
# single pair's series anyway and carry no signal there) and excludes the
# target itself.
LINEAR_REGRESSION_FEATURES = [
    "Year", "Month", "Day", "Day_Of_Week", "Day_Of_Year", "Quarter",
    "lag_1", "lag_3", "lag_7", "lag_14",
    "rolling_mean_3", "rolling_mean_7", "rolling_mean_14", "rolling_std_7",
    "price_change_1d", "price_change_7d",
]


def time_based_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION):
    """
    Splits an already-sorted-by-date dataframe into train/test using the
    LAST `test_fraction` of rows (by date order) as the test set. This is
    never a random shuffle - row order in equals row order out.
    Returns (train_df, test_df, meta_dict).
    """
    df = df.sort_values("Arrival_Date").reset_index(drop=True)
    n = len(df)
    n_test = max(1, int(round(n * test_fraction)))
    n_train = n - n_test

    train_df = df.iloc[:n_train].copy()
    test_df = df.iloc[n_train:].copy()

    meta = {
        "n_train": len(train_df),
        "n_test": len(test_df),
        "train_start": str(train_df["Arrival_Date"].min().date()) if len(train_df) else None,
        "train_end": str(train_df["Arrival_Date"].max().date()) if len(train_df) else None,
        "test_start": str(test_df["Arrival_Date"].min().date()) if len(test_df) else None,
        "test_end": str(test_df["Arrival_Date"].max().date()) if len(test_df) else None,
    }
    return train_df, test_df, meta


def safe_mape(actual: pd.Series, predicted: pd.Series, min_price: float = MAPE_SAFE_MIN_PRICE):
    """
    Standard MAPE divides by the actual value, which explodes or becomes
    meaningless near zero. This version excludes rows where actual < min_price
    from the MAPE calculation specifically, and reports how many rows were
    excluded so nothing is silently hidden.
    """
    actual = actual.reset_index(drop=True)
    predicted = predicted.reset_index(drop=True)

    valid_mask = actual.abs() >= min_price
    excluded_count = int((~valid_mask).sum())

    if valid_mask.sum() == 0:
        return np.nan, excluded_count

    pct_errors = ((actual[valid_mask] - predicted[valid_mask]).abs() / actual[valid_mask].abs()) * 100
    return float(pct_errors.mean()), excluded_count


def compute_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    """Computes MAE, RMSE, and safe MAPE for one model's predictions."""
    actual = actual.reset_index(drop=True)
    predicted = predicted.reset_index(drop=True)

    valid = actual.notna() & predicted.notna()
    actual_v, predicted_v = actual[valid], predicted[valid]

    if len(actual_v) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "MAPE": np.nan, "MAPE_Excluded_Rows": 0}

    mae = float((actual_v - predicted_v).abs().mean())
    rmse = float(np.sqrt(((actual_v - predicted_v) ** 2).mean()))
    mape, excluded = safe_mape(actual_v, predicted_v)

    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "MAPE": round(mape, 3) if not np.isnan(mape) else np.nan,
            "MAPE_Excluded_Rows": excluded}


def select_dominant_variety(pair_df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """
    Given all rows for one (Commodity, Market) pair (possibly spanning
    several varieties), picks the variety with the most records and
    returns (chosen_variety_name, filtered_dataframe).
    """
    counts = pair_df["Variety"].value_counts()
    dominant_variety = counts.index[0]
    filtered = pair_df[pair_df["Variety"] == dominant_variety].copy()
    return dominant_variety, filtered


def run_models_for_pair(crop: str, market: str, series_df: pd.DataFrame):
    """
    Trains and evaluates all four baseline models for one (Crop, Market)
    pair's chosen variety series. Returns (metrics_rows, prediction_rows).
    """
    df = series_df.sort_values("Arrival_Date").reset_index(drop=True)

    # Rows missing any required feature (e.g. the first 14 rows of a group,
    # before enough history exists for lag_14/rolling_mean_14) cannot be
    # used for model fitting or a fair like-for-like comparison across
    # models - we drop them here, openly, rather than silently letting
    # sklearn error out or coerce NaNs.
    required_cols = LINEAR_REGRESSION_FEATURES + ["Modal_Price", "Arrival_Date"]
    usable_df = df.dropna(subset=required_cols).reset_index(drop=True)

    if len(usable_df) < MIN_USABLE_ROWS:
        return None, None, f"Only {len(usable_df)} usable rows after removing NaN feature rows (minimum required: {MIN_USABLE_ROWS})"

    train_df, test_df, meta = time_based_split(usable_df, TEST_FRACTION)

    if len(train_df) < 5 or len(test_df) < 1:
        return None, None, f"Train/test split too small (train={len(train_df)}, test={len(test_df)})"

    metrics_rows = []
    prediction_rows = []

    actual_test = test_df["Modal_Price"]

    # --- 1. Naive baseline: predicted = lag_1 (yesterday's actual price) ---
    naive_pred = test_df["lag_1"]
    metrics_rows.append({"Model": "Naive_Previous_Price", **compute_metrics(actual_test, naive_pred)})

    # --- 2. 3-day moving average baseline ---
    ma3_pred = test_df["rolling_mean_3"]
    metrics_rows.append({"Model": "Moving_Average_3Day", **compute_metrics(actual_test, ma3_pred)})

    # --- 3. 7-day moving average baseline ---
    ma7_pred = test_df["rolling_mean_7"]
    metrics_rows.append({"Model": "Moving_Average_7Day", **compute_metrics(actual_test, ma7_pred)})

    # --- 4. Linear Regression ---
    X_train = train_df[LINEAR_REGRESSION_FEATURES]
    y_train = train_df["Modal_Price"]
    X_test = test_df[LINEAR_REGRESSION_FEATURES]

    lr_model = LinearRegression()
    lr_model.fit(X_train, y_train)
    lr_pred = pd.Series(lr_model.predict(X_test), index=test_df.index)
    metrics_rows.append({"Model": "Linear_Regression", **compute_metrics(actual_test, lr_pred)})

    # attach common run metadata to every metric row
    for row in metrics_rows:
        row.update({
            "Crop": crop, "Market": market,
            "N_Train": meta["n_train"], "N_Test": meta["n_test"],
            "Train_Start": meta["train_start"], "Train_End": meta["train_end"],
            "Test_Start": meta["test_start"], "Test_End": meta["test_end"],
        })

    # per-row predictions for every model, for transparency/auditing
    for idx in test_df.index:
        prediction_rows.append({
            "Crop": crop, "Market": market,
            "Arrival_Date": test_df.loc[idx, "Arrival_Date"].date(),
            "Actual_Modal_Price": test_df.loc[idx, "Modal_Price"],
            "Pred_Naive": naive_pred.loc[idx],
            "Pred_MA3": ma3_pred.loc[idx],
            "Pred_MA7": ma7_pred.loc[idx],
            "Pred_Linear_Regression": lr_pred.loc[idx],
        })

    return metrics_rows, prediction_rows, None


def run_baseline_pipeline():
    os.makedirs(MODEL_OUTPUTS_DIR, exist_ok=True)

    print(f"Loading engineered features from {FEATURES_FILE}")
    features_df = pd.read_csv(FEATURES_FILE)
    features_df["Arrival_Date"] = pd.to_datetime(features_df["Arrival_Date"], errors="coerce")

    print(f"Loading Phase 1 data quality report from {QUALITY_REPORT_FILE}")
    quality_df = pd.read_csv(QUALITY_REPORT_FILE)

    all_metrics = []
    all_predictions = []
    skipped_rows = []

    for _, q_row in quality_df.iterrows():
        crop, market = q_row["Crop"], q_row["Market"]

        if not bool(q_row["Is_Eligible"]):
            reason = q_row["Reasons_If_Ineligible"] or "Marked not eligible in Phase 1 data quality report"
            skipped_rows.append({"Crop": crop, "Market": market, "Reason": reason})
            print(f"SKIPPING {crop} @ {market}: {reason}")
            continue

        pair_df = features_df[(features_df["Commodity"] == crop) & (features_df["Market"] == market)]
        if len(pair_df) == 0:
            reason = "No engineered feature rows found for this pair (unexpected - check upstream pipeline)"
            skipped_rows.append({"Crop": crop, "Market": market, "Reason": reason})
            print(f"SKIPPING {crop} @ {market}: {reason}")
            continue

        dominant_variety, variety_df = select_dominant_variety(pair_df)

        metrics_rows, prediction_rows, skip_reason = run_models_for_pair(crop, market, variety_df)

        if skip_reason:
            skipped_rows.append({"Crop": crop, "Market": market, "Reason": skip_reason})
            print(f"SKIPPING {crop} @ {market}: {skip_reason}")
            continue

        for row in metrics_rows:
            row["Variety_Used"] = dominant_variety
        for row in prediction_rows:
            row["Variety_Used"] = dominant_variety

        all_metrics.extend(metrics_rows)
        all_predictions.extend(prediction_rows)
        print(f"Modeled {crop} @ {market} (variety: {dominant_variety}) - "
              f"{metrics_rows[0]['N_Train']} train / {metrics_rows[0]['N_Test']} test rows")

    metrics_df = pd.DataFrame(all_metrics)
    predictions_df = pd.DataFrame(all_predictions)
    skipped_df = pd.DataFrame(skipped_rows, columns=["Crop", "Market", "Reason"])

    metrics_df.to_csv(METRICS_FILE, index=False)
    predictions_df.to_csv(PREDICTIONS_FILE, index=False)
    skipped_df.to_csv(SKIPPED_PAIRS_FILE, index=False)

    # --- Build a readable summary ---
    total_pairs = len(quality_df)
    modeled_pairs = metrics_df[["Crop", "Market"]].drop_duplicates().shape[0] if len(metrics_df) else 0
    skipped_count = len(skipped_df)

    summary_lines = [
        "KrushiMitra AI - Phase 2 Baseline Model Summary",
        f"Generated: {pd.Timestamp.now()}",
        "",
        f"Total (Crop, Market) pairs in Phase 1 quality report: {total_pairs}",
        f"Pairs successfully modeled:                           {modeled_pairs}",
        f"Pairs skipped:                                         {skipped_count}",
        "",
        "Skipped pairs and reasons:",
    ]
    for _, row in skipped_df.iterrows():
        summary_lines.append(f"  {row['Crop']} @ {row['Market']}: {row['Reason']}")

    summary_lines.append("")
    summary_lines.append("Average metrics per model (across all modeled pairs):")
    if len(metrics_df):
        avg_metrics = metrics_df.groupby("Model")[["MAE", "RMSE", "MAPE"]].mean().round(3)
        for model_name, row in avg_metrics.iterrows():
            summary_lines.append(f"  {model_name}: MAE={row['MAE']}, RMSE={row['RMSE']}, MAPE={row['MAPE']}%")

    summary_text = "\n".join(summary_lines)
    with open(SUMMARY_FILE, "w") as f:
        f.write(summary_text)

    print("\n" + "=" * 70)
    print(summary_text)
    print("=" * 70)
    print(f"\nSaved: {METRICS_FILE}")
    print(f"Saved: {PREDICTIONS_FILE}")
    print(f"Saved: {SKIPPED_PAIRS_FILE}")
    print(f"Saved: {SUMMARY_FILE}")

    return metrics_df, predictions_df, skipped_df


if __name__ == "__main__":
    run_baseline_pipeline()
