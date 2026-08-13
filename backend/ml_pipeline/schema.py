"""
schema.py

Purpose (in simple language):
------------------------------
Different official sources (AGMARKNET exports, data.gov.in downloads, e-NAM
reports) sometimes use slightly different column header spellings for the
exact same field:
  "Arrival Date"    vs  "Arrival_Date"
  "Min Price"       vs  "Min_Price"        vs  "Minimum Price"
  "Commodity Name"  vs  "Commodity"

This file does two jobs, BEFORE any cleaning logic runs:

1. normalize_headers()      -> renames whatever headers the file has into
                                our one standard set of column names
2. validate_required_columns() -> stops the pipeline with a clear, specific
                                error message if a required column is still
                                missing after normalization (instead of
                                silently crashing later with a confusing
                                KeyError deep inside the pipeline)
"""

import pandas as pd


REQUIRED_COLUMNS = [
    "State", "District", "Market", "Commodity", "Variety",
    "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price",
]

OPTIONAL_COLUMNS = ["Grade", "Arrivals_in_Quintal"]

# Maps a cleaned-up (lowercased, space-normalized) header variant to our
# one standard column name. Add more variants here as you encounter them
# in real downloaded files - no other code needs to change.
HEADER_ALIASES = {
    "state": "State",
    "state name": "State",
    "district": "District",
    "district name": "District",
    "market": "Market",
    "market name": "Market",
    "commodity": "Commodity",
    "commodity name": "Commodity",
    "variety": "Variety",
    "grade": "Grade",
    "arrival date": "Arrival_Date",
    "arrival_date": "Arrival_Date",
    "date": "Arrival_Date",
    "min price": "Min_Price",
    "minimum price": "Min_Price",
    "min_price": "Min_Price",
    "max price": "Max_Price",
    "maximum price": "Max_Price",
    "max_price": "Max_Price",
    "modal price": "Modal_Price",
    "modal_price": "Modal_Price",
    "arrivals in quintal": "Arrivals_in_Quintal",
    "arrivals (quintal)": "Arrivals_in_Quintal",
    "arrivals_in_quintal": "Arrivals_in_Quintal",
}


def _clean_header_key(header: str) -> str:
    """Lowercase, strip, collapse spaces/underscores for reliable lookup."""
    text = str(header).strip().lower()
    text = text.replace("_", " ")
    text = " ".join(text.split())
    return text


def normalize_headers(df: pd.DataFrame, source_name: str = "") -> pd.DataFrame:
    """
    Renames columns to our standard names wherever a known alias is found.
    Columns that don't match any known alias are left as-is (they might be
    harmless extra columns from the source file).
    """
    df = df.copy()
    rename_map = {}
    for col in df.columns:
        key = _clean_header_key(col)
        if key in HEADER_ALIASES:
            standard_name = HEADER_ALIASES[key]
            if standard_name != col:
                rename_map[col] = standard_name

    if rename_map:
        print(f"  Normalizing headers in {source_name or 'file'}: {rename_map}")
        df = df.rename(columns=rename_map)

    return df


def validate_required_columns(df: pd.DataFrame, source_name: str = "") -> None:
    """
    Checks that every REQUIRED_COLUMNS entry is present after normalization.
    Raises a clear, specific error naming exactly which columns are missing
    and which file they're missing from, instead of letting the pipeline
    fail later with a confusing KeyError.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Required column(s) missing in '{source_name or 'input file'}': {missing}. "
            f"Found columns were: {list(df.columns)}. "
            f"Check docs/csv_format.md for the expected format, or add a new "
            f"header alias in backend/ml_pipeline/schema.py if this is just "
            f"a naming variation."
        )
