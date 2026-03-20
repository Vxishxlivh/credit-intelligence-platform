# ================================
# Credit Intelligence Platform
# FINRA TRACE Bond Pricing Pipeline
# ================================

import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# Database Connection
# ================================
def get_db_engine():
    db_url = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    return create_engine(db_url)


# ================================
# Fetch Prices from FINRA TRACE
# ================================
def fetch_trace_prices(cusip: str, date: str) -> dict:
    """
    Fetch bond price from FINRA TRACE API for a given CUSIP and date.
    TRACE provides post-trade transparency for US bond markets.
    
    Args:
        cusip: 9-character bond identifier
        date: price date in YYYY-MM-DD format
    
    Returns:
        dict with bid, ask, mid prices or None if not found
    """
    url = "https://www.finra.org/finra-data/browse-catalog/bond-data"
    
    params = {
        "cusip": cusip,
        "startdate": date,
        "enddate": date,
    }

    headers = {
        "User-Agent": os.getenv("EDGAR_USER_AGENT", "credit-platform research@example.com")
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or len(data) == 0:
            logger.warning(f"No TRACE data found for CUSIP {cusip} on {date}")
            return None

        # Extract most recent trade as proxy for end-of-day price
        trades = pd.DataFrame(data)
        trades["price"] = pd.to_numeric(trades["lastSalePrice"], errors="coerce")
        trades = trades.dropna(subset=["price"])

        if trades.empty:
            return None

        mid = trades["price"].median()
        bid = mid * 0.9975   # approximate bid/ask spread for investment grade
        ask = mid * 1.0025

        return {
            "cusip": cusip,
            "price_date": date,
            "bid_price": round(bid, 6),
            "ask_price": round(ask, 6),
            "mid_price": round(mid, 6),
            "last_price": round(trades["price"].iloc[-1], 6),
            "price_source": "TRACE"
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"TRACE API error for {cusip}: {e}")
        return None


# ================================
# Price Validation Logic
# ================================
def validate_price(cusip: str, new_price: float, engine) -> dict:
    """
    Validate incoming price against historical data.
    Flags stale prices and statistical outliers.

    Returns:
        dict with is_stale, is_outlier flags and deviation_pct
    """
    query = text("""
        SELECT mid_price, price_date
        FROM daily_prices
        WHERE cusip = :cusip
        ORDER BY price_date DESC
        LIMIT 30
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"cusip": cusip})
        history = pd.DataFrame(result.fetchall(), columns=["mid_price", "price_date"])

    if history.empty:
        # No history — first time seeing this security
        return {"is_stale": False, "is_outlier": False, "deviation_pct": None}

    last_price = history["mid_price"].iloc[0]
    last_date = history["price_date"].iloc[0]
    avg_price = history["mid_price"].mean()
    std_price = history["mid_price"].std()

    # Stale check — same price as yesterday
    is_stale = (new_price == last_price)

    # Outlier check — more than 2 standard deviations from 30-day average
    deviation_pct = abs(new_price - avg_price) / avg_price * 100
    is_outlier = (deviation_pct > (2 * std_price / avg_price * 100)) if std_price > 0 else False

    return {
        "is_stale": is_stale,
        "is_outlier": is_outlier,
        "deviation_pct": round(deviation_pct, 4)
    }


# ================================
# Save Price to Database
# ================================
def save_price(price_data: dict, validation: dict, engine):
    """
    Insert validated price record into daily_prices table.
    Logs exception if stale or outlier detected.
    """
    price_data["is_stale"] = validation["is_stale"]
    price_data["is_outlier"] = validation["is_outlier"]

    insert_query = text("""
        INSERT INTO daily_prices 
            (cusip, price_date, bid_price, ask_price, mid_price, 
             last_price, price_source, is_stale, is_outlier)
        VALUES 
            (:cusip, :price_date, :bid_price, :ask_price, :mid_price,
             :last_price, :price_source, :is_stale, :is_outlier)
        ON CONFLICT (cusip, price_date) DO UPDATE SET
            mid_price = EXCLUDED.mid_price,
            is_stale = EXCLUDED.is_stale,
            is_outlier = EXCLUDED.is_outlier,
            created_at = CURRENT_TIMESTAMP
    """)

    with engine.begin() as conn:
        conn.execute(insert_query, price_data)

    # Log exception if flagged
    if validation["is_stale"] or validation["is_outlier"]:
        exception_type = "STALE" if validation["is_stale"] else "OUTLIER"
        log_exception(
            cusip=price_data["cusip"],
            date=price_data["price_date"],
            exception_type=exception_type,
            deviation_pct=validation["deviation_pct"],
            engine=engine
        )
        logger.warning(
            f"⚠️  Exception flagged for {price_data['cusip']} "
            f"— Type: {exception_type}, Deviation: {validation['deviation_pct']}%"
        )


# ================================
# Log Exception
# ================================
def log_exception(cusip, date, exception_type, deviation_pct, engine):
    """
    Insert pricing exception into pricing_exceptions table.
    """
    query = text("""
        INSERT INTO pricing_exceptions
            (cusip, exception_date, exception_type, deviation_pct)
        VALUES
            (:cusip, :date, :type, :deviation)
        ON CONFLICT DO NOTHING
    """)

    with engine.begin() as conn:
        conn.execute(query, {
            "cusip": cusip,
            "date": date,
            "type": exception_type,
            "deviation": deviation_pct
        })


# ================================
# Main Pipeline — Run Daily
# ================================
def run_daily_pricing_pipeline(date: str = None):
    """
    Main entry point for daily pricing run.
    Fetches prices for all active securities and validates them.
    """
    if not date:
        date = datetime.today().strftime("%Y-%m-%d")

    logger.info(f"🚀 Starting daily pricing pipeline for {date}")

    engine = get_db_engine()

    # Get all active securities from security master
    query = text("""
        SELECT cusip, issuer_name, asset_class 
        FROM security_master 
        WHERE is_active = TRUE AND cusip IS NOT NULL
    """)

    with engine.connect() as conn:
        securities = pd.DataFrame(
            conn.execute(query).fetchall(),
            columns=["cusip", "issuer_name", "asset_class"]
        )

    logger.info(f"📋 Found {len(securities)} active securities")

    results = {"success": 0, "missing": 0, "exceptions": 0}

    for _, row in securities.iterrows():
        cusip = row["cusip"]

        # Fetch price
        price_data = fetch_trace_prices(cusip, date)

        if not price_data:
            logger.warning(f"❌ No price found for {cusip} ({row['issuer_name']})")
            results["missing"] += 1
            continue

        # Validate price
        validation = validate_price(cusip, price_data["mid_price"], engine)

        # Save to DB
        save_price(price_data, validation, engine)

        if validation["is_stale"] or validation["is_outlier"]:
            results["exceptions"] += 1
        else:
            results["success"] += 1

    logger.info(
        f"✅ Pipeline complete — "
        f"Success: {results['success']} | "
        f"Missing: {results['missing']} | "
        f"Exceptions: {results['exceptions']}"
    )

    return results


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    run_daily_pricing_pipeline()