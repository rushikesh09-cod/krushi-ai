"""
test_feature_engineering.py

Purpose (in simple language):
------------------------------
These are automated checks that verify the feature engineering pipeline is
actually safe and correct - not just "runs without crashing". Every check
below either PASSES or raises a clear assertion error explaining exactly
what went wrong.

Checks performed:
1. No future-data leakage        - a row's lag_1 never equals its own price;
                                     it must equal the PREVIOUS row's price
2. Correct chronological ordering - every group is sorted ascending by date
3. No random train-test split     - verified in baseline_models.py's own
                                     split function directly (see check 3 below)
4. No missing target values       - Modal_Price must never be null in the
                                     engineered output
5. Correct lag calculations       - manually recompute lag_1/lag_7 on a
                                     small synthetic series and compare
6. Correct rolling calculations   - manually recompute rolling_mean_3 on a
                                     small synthetic series and compare

Run with:
    cd backend/ml_pipeline
    ../venv/bin/python tests/test_feature_engineering.py
"""

import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from feature_engineering import engineer_features_for_group
from baseline_models import time_based_split


def make_synthetic_group(n=20, start_price=100.0, start_date="2026-01-01"):
    """A single clean, gap-free synthetic crop-market-variety series with a
    known, predictable price pattern (100, 101, 102, ... ) so we can hand-
    verify every lag/rolling calculation exactly."""
    dates = pd.date_range(start=start_date, periods=n, freq="D")
    prices = [start_price + i for i in range(n)]
    return pd.DataFrame({
        "Commodity": "TestCrop",
        "Market": "TestMarket",
        "Variety": "TestVariety",
        "Arrival_Date": dates,
        "Modal_Price": prices,
        "Min_Price": [p - 10 for p in prices],
        "Max_Price": [p + 10 for p in prices],
    })


def check_no_future_leakage():
    df = make_synthetic_group()
    result = engineer_features_for_group(df)

    # Row i's lag_1 must equal row (i-1)'s Modal_Price, and must NOT equal
    # row i's own Modal_Price (that would be the definition of leakage).
    for i in range(1, len(result)):
        expected_lag1 = result.loc[i - 1, "Modal_Price"]
        actual_lag1 = result.loc[i, "lag_1"]
        assert actual_lag1 == expected_lag1, (
            f"Leakage check FAILED at row {i}: lag_1={actual_lag1}, expected {expected_lag1}"
        )
        assert actual_lag1 != result.loc[i, "Modal_Price"], (
            f"Leakage check FAILED at row {i}: lag_1 equals the row's OWN price - future data leaked in"
        )
    print("PASS: check_no_future_leakage")


def check_chronological_ordering():
    # Feed in a deliberately SHUFFLED input and confirm the function still
    # returns a chronologically sorted result.
    df = make_synthetic_group().sample(frac=1, random_state=1).reset_index(drop=True)
    result = engineer_features_for_group(df)
    dates = result["Arrival_Date"].tolist()
    assert dates == sorted(dates), "Chronological ordering check FAILED: output is not sorted ascending by date"
    print("PASS: check_chronological_ordering")


def check_no_random_split():
    df = make_synthetic_group(n=30)
    df["lag_1"] = df["Modal_Price"].shift(1)  # minimal stand-in feature for split testing
    train_df, test_df, meta = time_based_split(df, test_fraction=0.2)

    # Every train date must be earlier than every test date - this is only
    # true for a time-based split, never for a random shuffle-based split.
    assert train_df["Arrival_Date"].max() < test_df["Arrival_Date"].min(), (
        "Train/test split check FAILED: train and test sets overlap in time - split may be random, not chronological"
    )
    print("PASS: check_no_random_split")


def check_no_missing_target_values():
    df = make_synthetic_group()
    result = engineer_features_for_group(df)
    assert result["Modal_Price"].isna().sum() == 0, "Missing target check FAILED: Modal_Price contains nulls"
    print("PASS: check_no_missing_target_values")


def check_lag_calculations():
    df = make_synthetic_group(n=20, start_price=100.0)
    result = engineer_features_for_group(df)

    # Prices are 100,101,102,...,119 in row order.
    # Row 10 (0-indexed) has Modal_Price = 110.
    # lag_1 should be row 9's price = 109
    # lag_7 should be row 3's price = 103
    row = result.iloc[10]
    assert row["lag_1"] == 109, f"lag_1 calculation FAILED: got {row['lag_1']}, expected 109"
    assert row["lag_7"] == 103, f"lag_7 calculation FAILED: got {row['lag_7']}, expected 103"
    print("PASS: check_lag_calculations")


def check_rolling_calculations():
    df = make_synthetic_group(n=20, start_price=100.0)
    result = engineer_features_for_group(df)

    # Row 10 has Modal_Price = 110. rolling_mean_3 uses the shifted series
    # (so it looks at rows 7,8,9 -> prices 107,108,109) -> mean = 108
    row = result.iloc[10]
    expected_rolling_mean_3 = (107 + 108 + 109) / 3
    assert row["rolling_mean_3"] == expected_rolling_mean_3, (
        f"rolling_mean_3 calculation FAILED: got {row['rolling_mean_3']}, expected {expected_rolling_mean_3}"
    )
    print("PASS: check_rolling_calculations")


def run_all_checks():
    checks = [
        check_no_future_leakage,
        check_chronological_ordering,
        check_no_random_split,
        check_no_missing_target_values,
        check_lag_calculations,
        check_rolling_calculations,
    ]
    print("Running Phase 2 automated correctness checks...\n")
    for check in checks:
        check()
    print("\nAll Phase 2 automated checks PASSED.")


if __name__ == "__main__":
    run_all_checks()
