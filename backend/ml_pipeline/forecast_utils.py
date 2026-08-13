"""
forecast_utils.py

Purpose (in simple language):
------------------------------
This file answers two questions for every forecast:
  1. "How wide should the price range be, and is it trending up or down?"
  2. "How much should a farmer trust this particular forecast?"

Neither answer is guessed or randomized - both come from actual numbers
produced during model training and evaluation.

PREDICTION RANGE METHOD (see build_prediction_range):
We use the SELECTED model's own validation-set residuals (its prediction
errors on the held-out time-based test set) to build the range. Concretely:
  residual = actual_price - predicted_price   (for every test-set row)
  lower_offset = 10th percentile of residuals
  upper_offset = 90th percentile of residuals
  Estimated_Lower_Price = predicted_price + lower_offset
  Estimated_Upper_Price = predicted_price + upper_offset

This is called an "Estimated Price Range", NOT a "confidence interval" -
a true statistical confidence interval requires assumptions (e.g. normally
distributed, i.i.d. errors) that we have not verified for this data. Using
the empirical 10th/90th percentile of actual past errors is a defensible,
plainly-explainable approximation: "in roughly 80% of past test cases, the
real price landed within this band of the prediction" - nothing stronger
is claimed.

CONFIDENCE SCORE METHOD (see calculate_confidence_score):
A single weighted average (0-100) of five components, each also scored
0-100 first:
  1. Model validation accuracy (from MAPE - lower MAPE = higher score)
  2. Data quality score          (from Phase 1's per-crop-market report)
  3. Data freshness score        (from Phase 1's per-crop-market report)
  4. Historical record count     (more training rows = higher score, capped)
  5. Recent price volatility     (calmer recent prices = higher score)

Weights (documented here and in docs/model_selection.md):
  Model accuracy   : 35%
  Data quality      : 20%
  Data freshness    : 15%
  Record count      : 15%
  Price volatility  : 15%

Confidence levels: High >= 75, Medium 50-74, Low < 50.
"""

import numpy as np
import pandas as pd

CONFIDENCE_WEIGHTS = {
    "model_accuracy": 0.35,
    "data_quality": 0.20,
    "data_freshness": 0.15,
    "record_count": 0.15,
    "price_volatility": 0.15,
}

CONFIDENCE_HIGH_THRESHOLD = 75
CONFIDENCE_MEDIUM_THRESHOLD = 50

RECORD_COUNT_TARGET = 180  # same target used in Phase 1's data-quality scoring, for consistency


def build_prediction_range(predicted_price: float, test_actuals: pd.Series, test_predictions: pd.Series):
    """
    Builds an "Estimated Price Range" (never called a confidence interval)
    around a single predicted price, using the empirical distribution of
    the selected model's own validation residuals.
    """
    residuals = (test_actuals.reset_index(drop=True) - test_predictions.reset_index(drop=True)).dropna()

    if len(residuals) < 5:
        # Too few validation points for a meaningful percentile spread -
        # fall back to a simple +/- 1 MAE band so we never fabricate precision.
        mae_fallback = residuals.abs().mean() if len(residuals) > 0 else predicted_price * 0.05
        lower = predicted_price - mae_fallback
        upper = predicted_price + mae_fallback
    else:
        lower_offset = np.percentile(residuals, 10)
        upper_offset = np.percentile(residuals, 90)
        lower = predicted_price + lower_offset
        upper = predicted_price + upper_offset

    # A price range can never sensibly go negative or invert.
    lower = max(0.0, min(lower, predicted_price))
    upper = max(upper, predicted_price)

    return round(lower, 2), round(upper, 2)


def determine_trend(predicted_price: float, last_known_price: float, threshold_pct: float = 1.0) -> str:
    """
    Compares the predicted price to the last known actual price.
    threshold_pct: the minimum % change required to call it a trend rather
    than "Stable" - avoids labelling normal noise as a trend.
    """
    if last_known_price is None or last_known_price == 0 or pd.isna(last_known_price):
        return "Stable"

    pct_change = (predicted_price - last_known_price) / last_known_price * 100
    if pct_change > threshold_pct:
        return "Increasing"
    if pct_change < -threshold_pct:
        return "Decreasing"
    return "Stable"


def _score_model_accuracy(mape: float) -> float:
    """Lower MAPE -> higher score. A MAPE of 0% scores 100, 50%+ scores 0."""
    if mape is None or pd.isna(mape):
        return 0.0
    return float(max(0, 100 - mape * 2))


def _score_record_count(n_train: int) -> float:
    return float(min(100, (n_train / RECORD_COUNT_TARGET) * 100))


def _score_volatility(recent_prices: pd.Series) -> float:
    """
    Uses the coefficient of variation (std / mean) of the most recent
    prices available. Calmer (less volatile) recent prices score higher,
    since the model has an easier, more stable pattern to predict from.
    """
    recent_prices = recent_prices.dropna()
    if len(recent_prices) < 3 or recent_prices.mean() == 0:
        return 50.0  # neutral score when volatility can't be judged

    cv = recent_prices.std() / recent_prices.mean()
    # a CV of 0 (perfectly flat) scores 100; a CV of 0.5+ (very volatile) scores near 0
    return float(max(0, 100 - cv * 200))


def calculate_confidence_score(mape: float, data_quality_score: float, freshness_score: float,
                                n_train: int, recent_prices: pd.Series) -> dict:
    """
    Combines five component scores into one overall confidence score
    (0-100) using the documented weights above. Returns a dict with the
    overall score, level, and every individual component for transparency.
    """
    accuracy_score = _score_model_accuracy(mape)
    quality_score = float(data_quality_score) if pd.notna(data_quality_score) else 0.0
    freshness = float(freshness_score) if pd.notna(freshness_score) else 0.0
    record_score = _score_record_count(n_train)
    volatility_score = _score_volatility(recent_prices)

    overall = (
        accuracy_score * CONFIDENCE_WEIGHTS["model_accuracy"]
        + quality_score * CONFIDENCE_WEIGHTS["data_quality"]
        + freshness * CONFIDENCE_WEIGHTS["data_freshness"]
        + record_score * CONFIDENCE_WEIGHTS["record_count"]
        + volatility_score * CONFIDENCE_WEIGHTS["price_volatility"]
    )
    overall = round(float(overall), 1)

    if overall >= CONFIDENCE_HIGH_THRESHOLD:
        level = "High"
    elif overall >= CONFIDENCE_MEDIUM_THRESHOLD:
        level = "Medium"
    else:
        level = "Low"

    return {
        "Overall_Confidence_Score": overall,
        "Confidence_Level": level,
        "Component_Model_Accuracy_Score": round(accuracy_score, 1),
        "Component_Data_Quality_Score": round(quality_score, 1),
        "Component_Data_Freshness_Score": round(freshness, 1),
        "Component_Record_Count_Score": round(record_score, 1),
        "Component_Price_Volatility_Score": round(volatility_score, 1),
        "Low_Confidence_Warning": "Low-confidence forecast - use with caution." if level == "Low" else "",
    }
