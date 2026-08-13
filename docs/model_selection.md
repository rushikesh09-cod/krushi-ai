# Model Selection — How and Why (Phase 3)

## ⚠️ Synthetic Data Notice

**Every number in this document and in Phase 3's output files (advanced_metrics.csv,
model_comparison.csv, model_registry.csv, etc.) comes from the project's
synthetic/sample dataset** (`data/raw/sample_multicrop_prices.csv`), generated
purely to build and test the pipeline. These are **development/testing
results**, not real-world forecasting accuracy. Once real AGMARKNET/e-NAM
data is loaded (see `docs/data_sources.md`), Phase 3 must be re-run, and
only those results should be treated as meaningful.

---

## Combined vs Crop-Specific Models

- **Crop-specific models** (Random Forest, XGBoost) are trained using ONLY
  one (Crop, Market) pair's own history. They can capture that pair's own
  idiosyncratic patterns, but have less data to learn from.
- **Combined models** (one shared Random Forest, one shared XGBoost) are
  trained on ALL eligible pairs' data at once, with Crop, Market, Variety,
  District, and Season included as one-hot encoded features. They have more
  total training data and can potentially "borrow strength" from patterns
  shared across crops/markets, but may blur pair-specific quirks.

Neither approach is assumed superior. Both are trained, evaluated per pair
on identical test data, and the winner is decided purely by measured
performance (see selection rule below).

**Why one-hot encoding, not numeric IDs:** turning "Onion"→1, "Tomato"→2,
"Wheat"→3 and feeding that into a model would falsely imply an ordering or
magnitude relationship between crops (as if Wheat > Tomato > Onion in some
numeric sense). One-hot encoding avoids this entirely — every category is
its own independent 0/1 flag.

---

## Time-Based Testing (Why Random Splitting Is Never Used)

All data is sorted chronologically per (Crop, Market, Variety) group. The
**latest 20%** of each series' records become the test set; everything
earlier is the training set. This mirrors how the system will actually be
used in production: trained on the past, asked to predict the near future.

A random shuffle-based split would let the model train on data from
*after* the test period — for example, training on Tuesday's price to
predict Monday's. That is data leakage and would make every metric
meaningless. This is why:
- Every group is explicitly sorted by date before any split.
- `time_based_split()` always takes the last N rows by date — never a
  random sample.
- For the **combined model**, each pair's own train/test date boundary is
  preserved and then all pairs' train portions are concatenated together
  (and likewise for test) — so the combined model never trains on any
  pair's future test-period data either.

---

## Model Selection Rule

For every eligible (Crop, Market) pair, all 7 candidates are evaluated on
the exact same test rows:

1. Naive previous-price baseline (Phase 2)
2. Best of Moving-Average-3-day / Moving-Average-7-day (Phase 2)
3. Linear Regression (Phase 2, retrained here to obtain a saveable model object)
4. Random Forest (crop-specific)
5. XGBoost (crop-specific)
6. Random Forest (combined)
7. XGBoost (combined)

**Step 1 — Rank:** all 7 are ranked by MAE (lower is better); RMSE breaks
any tie.

**Step 2 — Naive guard:** if the top-ranked candidate is NOT the naive
baseline, it must still improve on naive's MAE by at least the
**minimum-improvement threshold (currently 2%)** before it is allowed to
replace naive. If it doesn't clear that bar, naive is selected instead.

```
improvement_pct = (naive_MAE - candidate_MAE) / naive_MAE * 100
if best_candidate is naive:
    select naive
elif improvement_pct >= MIN_IMPROVEMENT_PCT (2.0):
    select best_candidate
else:
    select naive anyway
```

**Why this matters / why naive may legitimately win:** commodity prices
often behave close to a random walk day-to-day — tomorrow's price is
usually closest to today's price. A complex model can appear to "win" by
a tiny margin that's really just noise in a particular test window. The
2% threshold protects against swapping in a more complex, harder-to-
maintain model for a gain that isn't actually reliable. **In this Phase 3
run, naive won 15 of 18 pairs** — this is an expected, honest outcome for
this kind of data, not a pipeline failure.

The threshold (`MIN_IMPROVEMENT_PCT` in `advanced_models.py`) is a single
constant and can be tuned later as more real data becomes available.

---

## Prediction Range Method ("Estimated Price Range")

We do **not** call this a "confidence interval" — a true statistical
confidence interval requires assumptions (e.g. normally distributed,
independent errors) that haven't been verified for this data.

Instead, for the selected model of each pair:
1. Take that model's own prediction errors (residuals = actual − predicted)
   on its time-based validation/test set.
2. Compute the 10th and 90th percentile of those residuals.
3. Add those percentile offsets to the current point prediction to get the
   lower and upper bounds.

This means: "in roughly 80% of past validation cases, the real price
landed within this band relative to the prediction" — an empirical,
plainly explainable statement, not a guaranteed probability claim. If a
pair has fewer than 5 validation residuals (too few for a reliable
percentile), the code falls back to a simple ±1 MAE band instead of
fabricating false precision.

---

## Confidence Score Formula

Overall score (0–100) = weighted average of five components, each scored
0–100 individually:

| Component | Weight | What it measures |
|---|---|---|
| Model validation accuracy | 35% | Derived from MAPE — lower MAPE scores higher |
| Data quality score | 20% | From Phase 1's per-(Crop, Market) quality report |
| Data freshness | 15% | From Phase 1's per-(Crop, Market) freshness score |
| Historical record count | 15% | More training rows → higher score, capped at 180 records |
| Recent price volatility | 15% | Calmer recent prices (lower coefficient of variation) → higher score |

**Confidence levels:** High ≥ 75, Medium 50–74, Low < 50.

If the level is Low, the system attaches the message:
`"Low-confidence forecast - use with caution."`

If a (Crop, Market) pair was never eligible per Phase 1 (or lacked enough
usable rows in Phase 2/3), **no forecast, range, or confidence score is
generated for it at all** — it appears only in `phase3_skipped_pairs.csv`
with a reason.

---

## Limitations of the Current (Synthetic) Data

- All current metrics reflect a synthetic dataset generated to exercise
  the pipeline's logic (duplicates, outliers, stale data, thin records,
  etc. were deliberately injected in Phase 1). They say nothing about how
  well any model will actually forecast real Maharashtra crop prices.
- Arrivals-based features are entirely absent in this run because the
  synthetic dataset has no `Arrivals_in_Quintal` column — the code
  supports them and will use them automatically once reliable arrivals
  data is present (see `_is_arrivals_reliable()` / `_arrivals_available_for()`).
- Hyperparameters for Random Forest and XGBoost (e.g. `n_estimators=200`,
  `max_depth`) are reasonable defaults, not tuned — hyperparameter tuning
  was explicitly out of scope for Phase 3 and can be revisited once real
  data is available and there's a genuine signal worth tuning for.
- The "dominant variety" simplification (Phase 2 and Phase 3 both model
  only the most-recorded variety per Crop-Market pair) means minority
  varieties' price behavior isn't separately modeled yet.
