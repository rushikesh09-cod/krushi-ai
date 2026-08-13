# How to Obtain Official Maharashtra Multi-Crop Price Data

Real government data sources only — no invented API endpoints are used
anywhere in this project.

## Option 1: data.gov.in (Recommended — easiest for multiple crops at once)

1. Go to https://www.data.gov.in
2. Search: **"Variety-wise Daily Market Prices Data of Commodity"**
   (published under Department of Agriculture & Farmers Welfare / Agmarknet)
3. This single dataset covers ALL commodities, not just one crop — so you
   can filter it for each of our five starting crops one at a time:
   - State: Maharashtra
   - Commodity: Onion → download → repeat for Tomato, Potato, Wheat, Soybean
4. Each download becomes one file in `backend/ml_pipeline/data/raw/`
   (e.g. `onion_maharashtra.csv`, `tomato_maharashtra.csv`, etc.) — the
   pipeline will combine them automatically, no manual merging needed.
5. data.gov.in also offers this dataset via API (needs a free account API
   key) — useful later for live/automatic updates once the prototype works.

## Option 2: Agmarknet portal directly

1. Go to https://agmarknet.gov.in → "Price and Arrival Report"
2. For each crop (Onion, Tomato, Potato, Wheat, Soybean):
   - Commodity: select the crop
   - State: Maharashtra
   - Market: Sangli / Kolhapur / Satara / Pune / Nashik (select one at a
     time if multi-select isn't available)
   - Date range: as much history as available
3. Export each report and place it in `data/raw/`.

## Option 3: e-NAM

e-NAM (https://www.enam.gov.in) traded-commodity data is normally accessed
through data.gov.in's e-NAM dataset listings (search "e-NAM" on data.gov.in)
rather than a public direct API.

## Important: not every crop trades in every market

Wheat and Soybean, for example, may not have significant trade volume in
all five of our target markets. This is expected and fine — download
whatever data genuinely exists per crop-market combination. The pipeline's
data-quality module (Step 8 below) will correctly mark thin or missing
crop-market pairs as "not eligible for forecasting" rather than guessing.

## Where files go

All downloaded files (any number, any naming) go into:
```
backend/ml_pipeline/data/raw/
```

## About today's sample data

Until real files are downloaded, this Phase 1 delivery includes a
**synthetic/sample CSV** (`sample_multicrop_prices.csv`) purely to test the
pipeline logic right now — including deliberately messy rows (duplicates,
missing prices, price inconsistencies, a few crop-market pairs with very
thin data) so we can verify every quality check actually works. This sample
file must be replaced with real downloaded data before the hackathon
submission.
