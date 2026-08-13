"""
validation.py

Purpose (in simple language):
------------------------------
Some rows in raw government data are not just "unusual" — they are flat-out
broken (e.g. Min Price higher than Max Price, negative prices, or a Modal
Price that doesn't even fall between Min and Max). These rows would confuse
any model, so they must be REMOVED, not just flagged.

But instead of silently deleting them, every rejected row is written to a
separate file (`data/rejected/rejected_records.csv`) together with the
reason it was rejected — so nothing disappears without a trace and you can
always double-check the pipeline's decisions.

This is different from `data_quality.py`, which measures overall dataset
health (freshness, missing %, etc.) and from the IQR outlier check in
`clean_data.py`, which flags statistically unusual (but not necessarily
wrong) prices and KEEPS them in the dataset.
"""

import pandas as pd
import numpy as np

from schema import REQUIRED_COLUMNS  # single source of truth, see schema.py


def validate_records(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataframe into (valid_rows, rejected_rows).
    `rejected_rows` has an extra "Rejection_Reason" column explaining why
    each row was removed. A row can only have ONE reason recorded (the
    first rule it fails), keeping the log easy to read.
    """
    df = df.copy()
    df["Rejection_Reason"] = ""

    # Rule 1: required fields must not be blank
    for col in ["Market", "Commodity", "Arrival_Date"]:
        mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
        df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = f"Missing required field: {col}"

    # Rule 2: prices must be present and numeric
    for col in ["Min_Price", "Max_Price", "Modal_Price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        mask = df[col].isna()
        df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = f"Missing or non-numeric {col}"

    # Rule 3: prices must be positive
    for col in ["Min_Price", "Max_Price", "Modal_Price"]:
        mask = df[col] <= 0
        df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = f"{col} is zero or negative"

    # Rule 4: Min_Price must not exceed Max_Price
    mask = df["Min_Price"] > df["Max_Price"]
    df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = "Min_Price greater than Max_Price"

    # Rule 5: Modal_Price must fall within [Min_Price, Max_Price], small tolerance allowed
    tolerance = 0.02  # 2% tolerance for rounding differences in source data
    lower_ok = df["Modal_Price"] >= df["Min_Price"] * (1 - tolerance)
    upper_ok = df["Modal_Price"] <= df["Max_Price"] * (1 + tolerance)
    mask = ~(lower_ok & upper_ok)
    df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = "Modal_Price outside Min/Max range"

    # Rule 6: date must be parseable
    parsed_dates = pd.to_datetime(df["Arrival_Date"], dayfirst=True, errors="coerce")
    mask = parsed_dates.isna()
    df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = "Unparseable Arrival_Date"
    df["Arrival_Date"] = parsed_dates

    # Rule 7: date must not be in the future
    mask = df["Arrival_Date"] > pd.Timestamp.now()
    df.loc[mask & (df["Rejection_Reason"] == ""), "Rejection_Reason"] = "Arrival_Date is in the future"

    is_rejected = df["Rejection_Reason"] != ""
    rejected_rows = df[is_rejected].copy()
    valid_rows = df[~is_rejected].drop(columns=["Rejection_Reason"]).copy()

    return valid_rows, rejected_rows
