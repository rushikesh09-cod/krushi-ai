import os
import pandas as pd


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RAW_DATA_FILE = os.path.join(
    BASE_DIR,
    "ml_pipeline",
    "data",
    "raw",
    "sample_multicrop_prices.csv",
)


REQUIRED_COLUMNS = [
    "State",
    "District",
    "Market",
    "Commodity",
    "Variety",
    "Grade",
    "Arrival_Date",
    "Min_Price",
    "Max_Price",
    "Modal_Price",
]


def load_market_data() -> pd.DataFrame:
    """Load the current market-price CSV."""

    if not os.path.exists(RAW_DATA_FILE):
        raise FileNotFoundError(
            f"Market data file not found: {RAW_DATA_FILE}"
        )

    df = pd.read_csv(RAW_DATA_FILE)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    df["Arrival_Date"] = pd.to_datetime(
        df["Arrival_Date"],
        errors="coerce",
        dayfirst=True,
    )

    # Normalize text fields
    df["Market"] = df["Market"].astype(str).str.strip()
    df["Commodity"] = df["Commodity"].astype(str).str.strip()
    df["Variety"] = df["Variety"].astype(str).str.strip()

    # Normalize market names
    df["Market"] = df["Market"].str.title()

    # Normalize commodity names
    df["Commodity"] = df["Commodity"].str.title()

    # Convert prices to numbers
    for column in [
        "Min_Price",
        "Max_Price",
        "Modal_Price",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "Arrival_Date",
            "Modal_Price",
        ]
    )

    return df


def get_latest_prices() -> pd.DataFrame:
    """
    Return the latest available market-price record
    for each Commodity + Market + Variety combination.
    """

    df = load_market_data()

    df = df.sort_values("Arrival_Date")

    latest = (
        df.groupby(
            ["Commodity", "Market", "Variety"],
            as_index=False,
        )
        .tail(1)
        .reset_index(drop=True)
    )

    return latest