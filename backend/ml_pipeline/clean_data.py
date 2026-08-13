"""
clean_data.py

Purpose (in simple language):
------------------------------
This is the main script that ties everything together. It reads every raw
CSV in data/raw/, cleans it, checks its quality per (Crop, Market) pair, and
produces several output files - and crucially, every row that gets removed
along the way is saved to an audit file explaining why, so nothing vanishes
silently.

Steps performed, in order:
1. Load every raw CSV file found in data/raw/
2. Normalize column headers (e.g. "Arrival Date" -> "Arrival_Date")
3. Validate that all required columns are present (stops with a clear
   error if not - see schema.py)
4. Standardize crop names and market names (using config/crops.json and
   config/markets.json)
5. Separate SUPPORTED crops (Phase 1 set) from UNSUPPORTED crops - the
   unsupported ones are saved to data/rejected/unsupported_crops.csv,
   not silently dropped
6. Run hard validation (validation.py) -> split into valid rows and
   rejected rows (data/rejected/rejected_records.csv)
7. Parse and sort dates
8. Remove duplicate records using an improved key that includes Grade
   (State, District, Market, Commodity, Variety, Grade, Arrival_Date) so
   valid records from different districts/grades are never wrongly merged
   - removed duplicates are saved to data/rejected/duplicate_records.csv
9. Flag outliers separately per (Crop, Market, Variety) group - flagged
   rows are KEPT (for transparency) but marked, so model training can
   exclude them later
10. Run the per-(Crop, Market) data-quality assessment
11. Save cleaned dataset + print a full run summary with every count

Run it with:
    cd backend/ml_pipeline
    ../venv/bin/python clean_data.py
"""

import os
import glob
import pandas as pd
import numpy as np

from schema import normalize_headers, validate_required_columns, REQUIRED_COLUMNS
from standardization import standardize_dataframe, CANONICAL_CROPS, CANONICAL_MARKETS
from validation import validate_records
from data_quality import run_quality_checks

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
REJECTED_DIR = os.path.join(BASE_DIR, "data", "rejected")

CLEANED_OUTPUT_FILE = os.path.join(PROCESSED_DIR, "cleaned_multicrop_prices.csv")
QUALITY_REPORT_FILE = os.path.join(PROCESSED_DIR, "data_quality_report.csv")
QUALITY_SUMMARY_TEXT_FILE = os.path.join(PROCESSED_DIR, "data_quality_summary.txt")
RUN_SUMMARY_FILE = os.path.join(PROCESSED_DIR, "run_summary.txt")

REJECTED_OUTPUT_FILE = os.path.join(REJECTED_DIR, "rejected_records.csv")
UNSUPPORTED_CROPS_FILE = os.path.join(REJECTED_DIR, "unsupported_crops.csv")
DUPLICATE_RECORDS_FILE = os.path.join(REJECTED_DIR, "duplicate_records.csv")

# Improved duplicate key - includes Grade so records that legitimately
# differ by grade (or come from a different district under the same
# market name) are never wrongly treated as duplicates.
DUPLICATE_KEY_COLUMNS = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date"]


# ---------------------------------------------------------------------------
# Step 1-3: Load, normalize headers, validate required columns, combine
# ---------------------------------------------------------------------------
def load_and_combine_raw_files(raw_dir: str) -> pd.DataFrame:
    csv_files = glob.glob(os.path.join(raw_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. "
            "Place downloaded AGMARKNET/e-NAM/data.gov.in files there first "
            "(see docs/data_sources.md)."
        )

    frames = []
    for path in csv_files:
        name = os.path.basename(path)
        df = pd.read_csv(path)
        df = normalize_headers(df, source_name=name)
        validate_required_columns(df, source_name=name)

        # Grade is optional in REQUIRED_COLUMNS' spirit but used in our
        # duplicate key - if a source file genuinely lacks it, fill blank
        # rather than crash, since Grade is in OPTIONAL_COLUMNS.
        if "Grade" not in df.columns:
            df["Grade"] = ""

        frames.append(df)
        print(f"Loaded {len(df)} rows from {name}")

    combined = pd.concat(frames, ignore_index=True)
    print(f"Combined dataset has {len(combined)} rows total from {len(csv_files)} file(s)")
    return combined


# ---------------------------------------------------------------------------
# Step 8: Remove duplicates (improved key) - with audit log
# ---------------------------------------------------------------------------
def remove_duplicates(df: pd.DataFrame):
    before = len(df)
    is_dup = df.duplicated(subset=DUPLICATE_KEY_COLUMNS, keep="first")
    duplicate_rows = df[is_dup].copy()
    deduped = df[~is_dup].reset_index(drop=True)
    print(f"Removed {len(duplicate_rows)} duplicate records (key: {DUPLICATE_KEY_COLUMNS})")
    return deduped, duplicate_rows


# ---------------------------------------------------------------------------
# Step 9: Flag outliers per (Crop, Market, Variety) group - keep, don't delete
# ---------------------------------------------------------------------------
def flag_outliers_iqr(df: pd.DataFrame, price_col: str = "Modal_Price") -> pd.DataFrame:
    df = df.copy()
    df["Is_Outlier"] = False

    group_cols = ["Commodity", "Market", "Variety"]
    for _, group_idx in df.groupby(group_cols).groups.items():
        group = df.loc[group_idx, price_col]
        if len(group) < 4:
            continue
        q1, q3 = group.quantile(0.25), group.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_idx = group[(group < lower) | (group > upper)].index
        df.loc[outlier_idx, "Is_Outlier"] = True

    flagged = int(df["Is_Outlier"].sum())
    print(f"Flagged {flagged} rows as price outliers (kept in file, excluded from training later)")
    return df


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(REJECTED_DIR, exist_ok=True)

    counts = {}

    print("Step 1-3: Loading raw files, normalizing headers, validating required columns...")
    df = load_and_combine_raw_files(RAW_DIR)
    counts["input_rows"] = len(df)

    print("\nStep 4: Standardizing crop and market names...")
    df = standardize_dataframe(df)

    print("\nStep 5: Separating supported vs unsupported crops...")
    known_crop_mask = df["Commodity"].isin(CANONICAL_CROPS)
    unsupported_df = df[~known_crop_mask].copy()
    df = df[known_crop_mask].reset_index(drop=True)
    counts["unsupported_crop_rows"] = len(unsupported_df)
    print(f"Kept {len(df)} supported-crop rows; set aside {len(unsupported_df)} unsupported-crop rows")

    if len(unsupported_df) > 0:
        unsupported_df.to_csv(UNSUPPORTED_CROPS_FILE, index=False)
        unknown_names = sorted(unsupported_df["Commodity"].unique())
        print(f"Unsupported crop names found: {unknown_names}")
        print(f"Saved to {UNSUPPORTED_CROPS_FILE}")
    else:
        # still write an (empty-with-headers) file so the audit trail is consistent
        pd.DataFrame(columns=list(df.columns)).to_csv(UNSUPPORTED_CROPS_FILE, index=False)

    print("\nStep 6: Running hard validation (splitting valid vs rejected records)...")
    valid_df, rejected_df = validate_records(df)
    counts["valid_rows_after_hard_validation"] = len(valid_df)
    counts["rejected_rows"] = len(rejected_df)
    print(f"Valid: {len(valid_df)} rows | Rejected: {len(rejected_df)} rows")
    rejected_df.to_csv(REJECTED_OUTPUT_FILE, index=False)
    print(f"Rejected records saved to {REJECTED_OUTPUT_FILE}")

    df = valid_df

    print("\nStep 7: Parsing and sorting dates...")
    df["Arrival_Date"] = pd.to_datetime(df["Arrival_Date"], errors="coerce")
    df = df.sort_values(["Commodity", "Market", "Arrival_Date"]).reset_index(drop=True)

    print("\nStep 8: Removing duplicates (improved key incl. Grade)...")
    df, duplicate_rows = remove_duplicates(df)
    counts["duplicate_rows_removed"] = len(duplicate_rows)
    duplicate_rows.to_csv(DUPLICATE_RECORDS_FILE, index=False)
    print(f"Duplicate records saved to {DUPLICATE_RECORDS_FILE}")

    print("\nStep 9: Flagging outliers (IQR method, per Crop+Market+Variety)...")
    df = flag_outliers_iqr(df)
    counts["outlier_rows_flagged"] = int(df["Is_Outlier"].sum())

    print("\nStep 10: Running per-(Crop, Market) data quality assessment...")
    quality_report = run_quality_checks(df)
    quality_report.to_csv(QUALITY_REPORT_FILE, index=False)

    eligible_count = int(quality_report["Is_Eligible"].sum())
    total_pairs = len(quality_report)
    quality_lines = [
        f"Data Quality Summary - generated {pd.Timestamp.now()}",
        f"Total (Crop, Market) pairs assessed: {total_pairs}",
        f"Eligible for forecasting: {eligible_count}",
        f"NOT eligible (insufficient/poor data): {total_pairs - eligible_count}",
        "",
        "Per-pair detail:",
    ]
    for _, row in quality_report.iterrows():
        status = "ELIGIBLE" if row["Is_Eligible"] else "NOT ELIGIBLE"
        line = f"  [{status}] {row['Crop']} @ {row['Market']}: score={row['Overall_Score']}, records={row['Record_Count']}"
        if row["Reasons_If_Ineligible"]:
            line += f" -- {row['Reasons_If_Ineligible']}"
        if row["Warnings"]:
            line += f" | Warnings: {row['Warnings']}"
        quality_lines.append(line)

    quality_summary_text = "\n".join(quality_lines)
    with open(QUALITY_SUMMARY_TEXT_FILE, "w") as f:
        f.write(quality_summary_text)
    print("\n" + quality_summary_text)

    counts["final_cleaned_rows"] = len(df)

    print(f"\nStep 11: Saving cleaned dataset to {CLEANED_OUTPUT_FILE}")
    df.to_csv(CLEANED_OUTPUT_FILE, index=False)

    # -----------------------------------------------------------------
    # Full run summary with every requested count
    # -----------------------------------------------------------------
    summary_lines = [
        f"KrushiMitra AI - Phase 1 Pipeline Run Summary",
        f"Generated: {pd.Timestamp.now()}",
        "",
        f"Input row count (combined raw files):     {counts['input_rows']}",
        f"Unsupported-crop row count (set aside):    {counts['unsupported_crop_rows']}",
        f"Rows after hard validation (valid):        {counts['valid_rows_after_hard_validation']}",
        f"Rejected row count (hard validation fail): {counts['rejected_rows']}",
        f"Duplicate row count (removed):              {counts['duplicate_rows_removed']}",
        f"Outlier row count (flagged, kept):          {counts['outlier_rows_flagged']}",
        f"Final cleaned row count:                    {counts['final_cleaned_rows']}",
        "",
        f"(Crop, Market) pairs assessed: {total_pairs}",
        f"  Eligible for forecasting:     {eligible_count}",
        f"  NOT eligible:                 {total_pairs - eligible_count}",
        "",
        "Output files:",
        f"  Cleaned dataset:      {CLEANED_OUTPUT_FILE}",
        f"  Quality report (CSV): {QUALITY_REPORT_FILE}",
        f"  Quality summary:      {QUALITY_SUMMARY_TEXT_FILE}",
        f"  Rejected records:     {REJECTED_OUTPUT_FILE}",
        f"  Unsupported crops:    {UNSUPPORTED_CROPS_FILE}",
        f"  Duplicate records:    {DUPLICATE_RECORDS_FILE}",
    ]
    summary_text = "\n".join(summary_lines)
    with open(RUN_SUMMARY_FILE, "w") as f:
        f.write(summary_text)

    print("\n" + "=" * 70)
    print(summary_text)
    print("=" * 70)

    return df, quality_report, counts


if __name__ == "__main__":
    run_pipeline()
