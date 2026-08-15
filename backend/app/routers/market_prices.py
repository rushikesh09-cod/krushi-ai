from fastapi import APIRouter, HTTPException

from data_ingestion.price_service import get_latest_market_prices


router = APIRouter(
    prefix="/market-prices",
    tags=["Market Prices"],
)


@router.get("")
def get_market_prices():
    """
    Return the latest available market price for
    each crop-market-variety combination.
    """

    try:
        prices = get_latest_market_prices()

        return {
            "count": len(prices),
            "source": "CSV development data",
            "prices": prices,
        }

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load market prices: {str(e)}",
        )