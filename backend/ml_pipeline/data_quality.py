"""
data_quality.py

Purpose (in simple language):
------------------------------
A crop can have excellent data in one market and almost no data in
another (e.g. Wheat might be well-recorded in Pune but barely traded in
Sangli). So instead of scoring "Onion" as one single thing, we score every
(Crop, Market) COMBINATION separately. Each combination gets its own
Data Quality Score (0-100) and its own eligibility decision.

Eligibility is NOT based on one fixed rule like "needs 90 days of data".
Instead we look at seven different signals together:

1. Number of valid records        - do we have enough rows at all?
2. Data freshness                 - how recent is the latest record?
3. Missing-date percentage        - within the date range we DO have,
                                     how many days have no record at all
                                     (gaps in the trading calendar)?
4. Missing-value percentage       - within records we DO have, how many
                                     price cells are blank?
5. Price continuity               - do day-to-day prices jump wildly in a
                                     way that suggests bad data entry
                                     (rather than a real market swing)?
6. Outlier percentage             - IQR-based, computed separately for
                                     every (Crop, Market, Variety) group,
                                     since normal price ranges differ by
                                     crop, market, and variety.
7. Historical coverage            - how long is the overall time span of
                                     data we have (a few weeks vs many
                                     months)?

These seven scores are combined into one overall score. A (Crop, Market)
pair is only marked "eligible for forecasting" if it clears both:
  (a) an absolute minimum record-count floor (a very basic sanity check,
      not the ONLY criterion), AND
  (b) a minimum overall combined score.

This means a crop-market pair with 200 records but very stale, gap-filled,
inconsistent data can still correctly be marked NOT eligible - and a pair
with a shorter but clean, fresh, continuous history can pass.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Thresholds (documented and adjustable in one place)
# ---------------------------------------------------------------------------
MIN_RECORDS_ABSOLUTE_FLOOR = 30          # below this, always ineligible no matter what
MIN_OVERALL_SCORE_FOR_ELIGIBILITY = 60   # combined score must reach this
FRESHNESS_TARGET_DAYS = 14               # data newer than this scores 100 on freshness
FRESHNESS_STALE_CUTOFF_DAYS = 180        # data older than this scores 0
COVERAGE_TARGET_DAYS = 180               # span of history considered "good" coverage
LARGE_JUMP_THRESHOLD_PCT = 40            # day-to-day % change considered a suspicious jump


@dataclass
class CropMarketQuality:
    crop: str
    market: str
    record_count: int
    overall_score: float
    is_eligible: bool
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # individual factor scores, kept for transparency in the report
    record_count_score: float = 0.0
    freshness_score: float = 0.0
    missing_date_score: float = 0.0
    missing_value_score: float = 0.0
    continuity_score: float = 0.0
    outlier_score: float = 0.0
    coverage_score: float = 0.0

    latest_date: str = ""
    date_range_days: int = 0
    missing_date_pct: float = 0.0
    missing_value_pct: float = 0.0
    outlier_pct: float = 0.0


def _score_record_count(count: int) -> float:
    """More records = higher score, capped at 100 around 180+ records."""
    return float(min(100, (count / 180) * 100))


def _score_freshness(latest_date: pd.Timestamp) -> float:
    if pd.isna(latest_date):
        return 0.0
    gap_days = (datetime.now() - latest_date.to_pydatetime()).days
    if gap_days <= FRESHNESS_TARGET_DAYS:
        return 100.0
    if gap_days >= FRESHNESS_STALE_CUTOFF_DAYS:
        return 0.0
    # linear decay between target and stale cutoff
    span = FRESHNESS_STALE_CUTOFF_DAYS - FRESHNESS_TARGET_DAYS
    return float(max(0, 100 - ((gap_days - FRESHNESS_TARGET_DAYS) / span) * 100))


def _score_missing_dates(dates: pd.Series) -> tuple[float, float]:
    """
    Looks at the full date span (first to last record) and checks what
    fraction of calendar days within that span have NO record at all.
    Returns (score, missing_date_pct).
    """
    dates = dates.dropna().sort_values()
    if len(dates) < 2:
        return 0.0, 100.0

    full_span_days = (dates.max() - dates.min()).days + 1
    unique_days_with_data = dates.dt.normalize().nunique()
    missing_pct = max(0.0, 100 * (1 - unique_days_with_data / full_span_days))
    score = max(0.0, 100 - missing_pct)  # 1% missing date coverage costs 1 point
    return score, missing_pct


def _score_missing_values(df: pd.DataFrame, price_cols: List[str]) -> tuple[float, float]:
    total_cells = len(df) * len(price_cols)
    missing_cells = df[price_cols].isna().sum().sum()
    missing_pct = (missing_cells / total_cells * 100) if total_cells > 0 else 100.0
    score = max(0.0, 100 - missing_pct * 4)  # every 1% missing costs 4 points
    return score, missing_pct


def _score_price_continuity(df: pd.DataFrame, price_col: str = "Modal_Price") -> float:
    """
    Sorts by date and checks the % day-to-day change in price. A market
    that jumps up/down by more than LARGE_JUMP_THRESHOLD_PCT frequently is
    either genuinely volatile or has data-entry problems - either way it
    lowers confidence, so we penalize a high frequency of large jumps.
    """
    series = df.sort_values("Arrival_Date")[price_col].dropna()
    if len(series) < 3:
        return 50.0  # not enough points to judge continuity, neutral score

    pct_change = series.pct_change().abs() * 100
    pct_change = pct_change.dropna()
    if len(pct_change) == 0:
        return 50.0

    large_jump_pct = float((pct_change > LARGE_JUMP_THRESHOLD_PCT).mean() * 100)
    score = max(0.0, 100 - large_jump_pct * 3)  # every 1% of large-jump days costs 3 points
    return score


def _score_outliers(df: pd.DataFrame, price_col: str = "Modal_Price") -> tuple[float, float]:
    """
    IQR outlier detection, computed within this (Crop, Market) group only.
    Variety-level splitting happens one level up, in run_quality_checks(),
    so that outlier ranges reflect a single crop+market+variety's normal
    price behavior.
    """
    series = df[price_col].dropna()
    if len(series) == 0:
        return 0.0, 100.0

    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outlier_pct = float(((series < lower) | (series > upper)).mean() * 100)
    score = max(0.0, 100 - outlier_pct * 6)  # every 1% outliers costs 6 points
    return score, outlier_pct


def _score_coverage(date_range_days: int) -> float:
    return float(min(100, (date_range_days / COVERAGE_TARGET_DAYS) * 100))


def assess_crop_market(df_group: pd.DataFrame, crop: str, market: str) -> CropMarketQuality:
    """Runs all seven checks for one (Crop, Market) group and combines them."""
    record_count = len(df_group)
    dates = pd.to_datetime(df_group["Arrival_Date"], errors="coerce")
    latest_date = dates.max() if dates.notna().any() else pd.NaT
    date_range_days = int((dates.max() - dates.min()).days) if dates.notna().sum() >= 2 else 0

    record_count_score = _score_record_count(record_count)
    freshness_score = _score_freshness(latest_date)
    missing_date_score, missing_date_pct = _score_missing_dates(dates)
    missing_value_score, missing_value_pct = _score_missing_values(df_group, ["Min_Price", "Max_Price", "Modal_Price"])
    continuity_score = _score_price_continuity(df_group)
    outlier_score, outlier_pct = _score_outliers(df_group)
    coverage_score = _score_coverage(date_range_days)

    factor_scores = [
        record_count_score, freshness_score, missing_date_score,
        missing_value_score, continuity_score, outlier_score, coverage_score,
    ]
    overall_score = float(np.mean(factor_scores))

    is_eligible = (record_count >= MIN_RECORDS_ABSOLUTE_FLOOR) and (overall_score >= MIN_OVERALL_SCORE_FOR_ELIGIBILITY)

    # "reasons" explains why a pair is NOT eligible (only populated when it's actually ineligible).
    reasons = []
    if not is_eligible:
        if record_count < MIN_RECORDS_ABSOLUTE_FLOOR:
            reasons.append(f"Only {record_count} records (minimum floor is {MIN_RECORDS_ABSOLUTE_FLOOR})")
        if overall_score < MIN_OVERALL_SCORE_FOR_ELIGIBILITY:
            reasons.append(f"Overall quality score {overall_score:.1f} is below required {MIN_OVERALL_SCORE_FOR_ELIGIBILITY}")

    # "warnings" flags a weak individual factor even when the pair is still eligible overall -
    # e.g. Wheat data might be old but otherwise clean/complete enough to still clear the bar.
    # This is surfaced separately so a strong overall score doesn't silently hide a real weak spot.
    warnings = []
    if freshness_score < 30:
        warnings.append("Data is fairly stale - forecast confidence should be reduced accordingly")
    if missing_date_score < 30:
        warnings.append("Noticeable gaps in the trading date calendar")
    if continuity_score < 40:
        warnings.append("Frequent large day-to-day price jumps detected")

    return CropMarketQuality(
        crop=crop, market=market, record_count=record_count,
        overall_score=overall_score, is_eligible=is_eligible, reasons=reasons,
        warnings=warnings,
        record_count_score=record_count_score, freshness_score=freshness_score,
        missing_date_score=missing_date_score, missing_value_score=missing_value_score,
        continuity_score=continuity_score, outlier_score=outlier_score,
        coverage_score=coverage_score,
        latest_date=str(latest_date.date()) if pd.notna(latest_date) else "N/A",
        date_range_days=date_range_days,
        missing_date_pct=missing_date_pct, missing_value_pct=missing_value_pct,
        outlier_pct=outlier_pct,
    )


def run_quality_checks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Runs the full per-(Crop, Market) assessment across the entire dataset
    and returns one summary row per combination, ready to save as a report.
    """
    results = []
    for (crop, market), group in df.groupby(["Commodity", "Market"]):
        result = assess_crop_market(group, crop, market)
        results.append(result)

    report_df = pd.DataFrame([{
        "Crop": r.crop,
        "Market": r.market,
        "Record_Count": r.record_count,
        "Overall_Score": round(r.overall_score, 1),
        "Is_Eligible": r.is_eligible,
        "Record_Count_Score": round(r.record_count_score, 1),
        "Freshness_Score": round(r.freshness_score, 1),
        "Missing_Date_Score": round(r.missing_date_score, 1),
        "Missing_Value_Score": round(r.missing_value_score, 1),
        "Continuity_Score": round(r.continuity_score, 1),
        "Outlier_Score": round(r.outlier_score, 1),
        "Coverage_Score": round(r.coverage_score, 1),
        "Latest_Date": r.latest_date,
        "Date_Range_Days": r.date_range_days,
        "Missing_Date_Pct": round(r.missing_date_pct, 2),
        "Missing_Value_Pct": round(r.missing_value_pct, 2),
        "Outlier_Pct": round(r.outlier_pct, 2),
        "Reasons_If_Ineligible": "; ".join(r.reasons) if r.reasons else "",
        "Warnings": "; ".join(r.warnings) if r.warnings else "",
    } for r in results])

    return report_df.sort_values(["Crop", "Market"]).reset_index(drop=True)
