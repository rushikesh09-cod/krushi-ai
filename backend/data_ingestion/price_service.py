from .csv_loader import get_latest_prices


def get_latest_market_prices() -> list:
    """Return latest market prices in API-friendly format."""

    df = get_latest_prices()

    results = []

    for _, row in df.iterrows():
        results.append(
            {
                "crop": row["Commodity"],
                "market": row["Market"],
                "variety": row["Variety"],
                "arrival_date": row["Arrival_Date"].date().isoformat(),
                "min_price": float(row["Min_Price"]),
                "max_price": float(row["Max_Price"]),
                "modal_price": float(row["Modal_Price"]),
            }
        )

    return results