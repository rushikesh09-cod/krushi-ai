"""
feature_engineering.py

Purpose (in simple language):
------------------------------
Machine learning models can't understand raw dates and prices directly -
they need "features": numeric signals extracted from the data that hint at
what the price might do next. This file turns our cleaned price data into
those signals.

CRITICAL RULE - NO DATA LEAKAGE:
Every lag and rolling feature for a given day must be built ONLY from days
BEFORE it. We never let a model "see the future" by accident. To guarantee
this, we ALWAYS sort each crop-market-variety group by date first, and every
rolling/lag calculation is explicitly shifted so "today's row" never
includes today's own price in its own rolling window.

Why per (Crop, Market, Variety) group, not per (Crop, Market)?
A market can trade several varieties of the same crop (e.g. Onion: Local vs
Nashik Red) at meaningfully different price levels. Computing "yesterday's
price" across mixed varieties would blend two different price series
together and produce misleading lag/rolling features. So every group is
processed completely independently, then all groups are combined into one
final feature table at the end.

Features generated:
- Calendar features:     Year, Month, Day, Day_Of_Week, Day_Of_Year, Quarter, Season
- Lag features:          lag_1, lag_3, lag_7, lag_14        (previous N records' Modal_Price)
- Rolling averages:      rolling_mean_3, rolling_mean_7, rolling_mean_14
- Rolling volatility:    rolling_std_7
- Price-change features: price_change_1d, price_change_7d   (computed from lag terms only - see below)
- Arrivals features:     only added if Arrivals_in_Quintal exists and is reliable (see is_arrivals_reliable)

Important note on "lag_N": since a market doesn't necessarily trade every
single calendar day, lag_N here means "N trading records back" for that
crop-market-variety series, not strictly "N calendar days back". This is
noted clearly so nobody misinterprets it later.

Important note on price_change features (leakage prevention):
price_change_1d and price_change_7d must NOT be computed as
(today's actual price - past price), because "today's actual price" is
exactly the value we're trying to forecast - using it as an input feature
would leak the answer into the model. Instead:
  price_change_1d = % change between lag_2 and lag_1   (momentum as of yesterday)
  price_change_7d = % change between lag_14 and lag_7  (momentum over the last week, as of a week ago)
Both are built entirely from already-past values.
"""

import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(__file__)
CLEANED_INPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "cleaned_multicrop_prices.csv")
FEATURES_DIR = os.path.join(BASE_DIR, "data", "features")
FEATURES_OUTPUT_FILE = os.path.join(FEATURES_DIR, "engineered_features.csv")

GROUP_COLUMNS = ["Commodity", "Market", "Variety"]

# An arrivals column is only trusted if it exists AND is missing in fewer
# than this fraction of rows for that specific group. Otherwise we skip
# arrivals-based features for that group rather than fabricate signal from
# mostly-empty data.
MAX_ARRIVALS_MISSING_FRACTION = 0.3


def _assign_season(month: int) -> str:
    """
    Simplified Maharashtra agricultural season mapping:
      Kharif : June - October   (monsoon-sown crops)
      Rabi   : November - March (winter-sown crops)
      Zaid   : April - May      (short summer season)
    This is an approximation used as a model feature, not an agronomic claim.
    """
    if month in (6, 7, 8, 9, 10):
        return "Kharif"
    if month in (11, 12, 1, 2, 3):
        return "Rabi"
    return "Zaid"  # April, May


def _add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    df["Year"] = df["Arrival_Date"].dt.year
    df["Month"] = df["Arrival_Date"].dt.month
    df["Day"] = df["Arrival_Date"].dt.day
    df["Day_Of_Week"] = df["Arrival_Date"].dt.dayofweek  # 0=Monday
    df["Day_Of_Year"] = df["Arrival_Date"].dt.dayofyear
    df["Quarter"] = df["Arrival_Date"].dt.quarter
    df["Season"] = df["Month"].apply(_assign_season)
    return df


def _add_lag_features(df: pd.DataFrame, price_col: str = "Modal_Price") -> pd.DataFrame:
    """
    df must already be sorted by date for this single group.
    Each lag_N uses .shift(N), which by definition only looks backwards -
    row i's lag_1 is row (i-1)'s price, never row i's own price.
    """
    df["lag_1"] = df[price_col].shift(1)
    df["lag_2"] = df[price_col].shift(2)   # intermediate only, used for price_change_1d
    df["lag_3"] = df[price_col].shift(3)
    df["lag_7"] = df[price_col].shift(7)
    df["lag_14"] = df[price_col].shift(14)
    return df


def _add_rolling_features(df: pd.DataFrame, price_col: str = "Modal_Price") -> pd.DataFrame:
    """
    Leakage prevention detail: we call .shift(1) BEFORE .rolling(...), so the
    rolling window for row i only ever includes rows up to (i-1). Without
    the shift(1), pandas' rolling() would include row i's own price in its
    own "rolling average" - that would be leakage.
    """
    shifted = df[price_col].shift(1)
    df["rolling_mean_3"] = shifted.rolling(window=3, min_periods=3).mean()
    df["rolling_mean_7"] = shifted.rolling(window=7, min_periods=7).mean()
    df["rolling_mean_14"] = shifted.rolling(window=14, min_periods=14).mean()
    df["rolling_std_7"] = shifted.rolling(window=7, min_periods=7).std()
    return df


def _add_price_change_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Built entirely from lag terms (already-past values) - see module
    docstring for why this avoids leakage.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        df["price_change_1d"] = np.where(
            (df["lag_2"].notna()) & (df["lag_2"] != 0),
            (df["lag_1"] - df["lag_2"]) / df["lag_2"] * 100,
            np.nan,
        )
        df["price_change_7d"] = np.where(
            (df["lag_14"].notna()) & (df["lag_14"] != 0),
            (df["lag_7"] - df["lag_14"]) / df["lag_14"] * 100,
            np.nan,
        )
    return df


def _is_arrivals_reliable(df: pd.DataFrame) -> bool:
    if "Arrivals_in_Quintal" not in df.columns:
        return False
    missing_frac = df["Arrivals_in_Quintal"].isna().mean()
    return missing_frac < MAX_ARRIVALS_MISSING_FRACTION


def _add_arrivals_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Only called when _is_arrivals_reliable() is True for this group.
    Same leakage-prevention pattern: shift(1) before any rolling/lag use.
    """
    shifted = df["Arrivals_in_Quintal"].shift(1)
    df["arrivals_lag_1"] = shifted
    df["arrivals_rolling_mean_7"] = shifted.rolling(window=7, min_periods=7).mean()
    return df


def engineer_features_for_group(group_df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs the full feature pipeline for ONE (Commodity, Market, Variety)
    group. The caller is responsible for splitting the full dataset into
    groups before calling this.
    """
    df = group_df.copy()

    # Leakage prevention step 1: always sort chronologically before
    # computing anything lag/rolling related.
    df = df.sort_values("Arrival_Date").reset_index(drop=True)

    df = _add_calendar_features(df)
    df = _add_lag_features(df)
    df = _add_rolling_features(df)
    df = _add_price_change_features(df)

    if _is_arrivals_reliable(df):
        df = _add_arrivals_features(df)
        df["Arrivals_Feature_Available"] = True
    else:
        df["Arrivals_Feature_Available"] = False

    # lag_2 was only an intermediate needed for price_change_1d - drop it
    # from the final output since it wasn't in the requested feature list.
    df = df.drop(columns=["lag_2"])

    return df


def run_feature_engineering() -> pd.DataFrame:
    os.makedirs(FEATURES_DIR, exist_ok=True)

    print(f"Loading cleaned dataset from {CLEANED_INPUT_FILE}")
    df = pd.read_csv(CLEANED_INPUT_FILE)
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"], errors="coerce")

    print(f"Loaded {len(df)} cleaned rows")
    print(f"Processing {df.groupby(GROUP_COLUMNS).ngroups} (Commodity, Market, Variety) groups independently...")

    engineered_groups = []
    for group_keys, group_df in df.groupby(GROUP_COLUMNS):
        engineered = engineer_features_for_group(group_df)
        engineered_groups.append(engineered)

    result = pd.concat(engineered_groups, ignore_index=True)
    result = result.sort_values(GROUP_COLUMNS + ["Arrival_Date"]).reset_index(drop=True)

    print(f"Feature engineering complete. Output has {len(result)} rows and {len(result.columns)} columns.")
    result.to_csv(FEATURES_OUTPUT_FILE, index=False)
    print(f"Saved to {FEATURES_OUTPUT_FILE}")

    return result


if __name__ == "__main__":
    run_feature_engineering()
