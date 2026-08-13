# Official Multi-Crop Price CSV Format

This is the exact column format the cleaning pipeline expects. It matches
the standard AGMARKNET / data.gov.in "Variety-wise Daily Market Prices"
format, so official downloaded files can be used directly without renaming
columns.

## Required columns

```
State, District, Market, Commodity, Variety, Grade, Arrival_Date, Min_Price, Max_Price, Modal_Price
```

## Optional column (include if the source provides it — improves quality checks and later trend explanations)

```
Arrivals_in_Quintal
```

## Column meanings

| Column | Type | Example | Notes |
|---|---|---|---|
| State | text | Maharashtra | |
| District | text | Sangli | |
| Market | text | Sangli | The specific market/mandi (APMC) |
| Commodity | text | Onion | This is now a MULTI-VALUE column — Onion, Tomato, Potato, Wheat, Soybean, etc. |
| Variety | text | Local, Nashik Red, Lokwan | Same crop can have several varieties with different price bands |
| Grade | text | FAQ | Fair Average Quality — usually present, sometimes blank |
| Arrival_Date | date | 15/06/2024 | day/month/year format (as AGMARKNET exports it) |
| Min_Price | number | 1800 | ₹ per quintal |
| Max_Price | number | 2400 | ₹ per quintal |
| Modal_Price | number | 2250 | ₹ per quintal — this is our main target variable for forecasting |
| Arrivals_in_Quintal | number | 450 | optional, quantity that arrived at market that day |

## One combined file per download, or many — both work

You can save one CSV per crop, one per market, or one big combined export —
the pipeline reads **every** CSV file inside `data/raw/` and combines them
automatically. You do not need to pre-merge files yourself.

## Starting crop set for Phase 1

```
Onion, Tomato, Potato, Wheat, Soybean
```

These five are defined in `config/crops.json` — this is the single place
that controls which crops the pipeline currently supports. To add a new
crop later (e.g. Maize), you only edit that JSON file (add its canonical
name and any spelling variants) — no Python code needs to change.

Any commodity found in the raw data that is NOT listed in `config/crops.json`
is not deleted — it's set aside and saved to
`backend/ml_pipeline/data/rejected/unsupported_crops.csv` so you can review
it and decide when to officially add that crop.
