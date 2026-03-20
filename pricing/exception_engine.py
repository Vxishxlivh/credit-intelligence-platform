# ================================
# Credit Intelligence Platform
# Pricing Exception Engine
# ================================

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime, timedelta
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
# Exception Type Definitions
# ================================
EXCEPTION_RULES = {
    "STALE": {
        "description": "Price unchanged for 3+ consecutive days",
        "severity":    "HIGH"
    },
    "OUTLIER": {
        "description": "Price deviates >2 standard deviations from 30-day average",
        "severity":    "HIGH"
    },
    "MISSING": {
        "description": "No price available for security on pricing date",
        "severity":    "CRITICAL"
    },
    "GAP": {
        "description": "Bid-ask spread wider than 2% — illiquid instrument",
        "severity":    "MEDIUM"
    },
    "VENDOR": {
        "description": "Price source changed unexpectedly",
        "severity":    "MEDIUM"
    }
}


# ================================
# Check for Stale Prices
# ================================
def check_stale_prices(engine, date: str) -> pd.DataFrame:
    """
    Flag securities where price has not changed for 3+ days.
    Stale prices are a key operational risk in illiquid markets.
    """
    query = text("""
        WITH price_changes AS (
            SELECT
                cusip,
                price_date,
                mid_price,
                LAG(mid_price, 1) OVER (PARTITION BY cusip ORDER BY price_date) AS prev_price_1,
                LAG(mid_price, 2) OVER (PARTITION BY cusip ORDER BY price_date) AS prev_price_2
            FROM daily_prices
            WHERE price_date >= :start_date
        )
        SELECT
            cusip,
            price_date,
            mid_price,
            prev_price_1,
            prev_price_2
        FROM price_changes
        WHERE
            price_date = :date
            AND mid_price = prev_price_1
            AND mid_price = prev_price_2
    """)

    start_date = (
        datetime.strptime(date, "%Y-%m-%d") - timedelta(days=10)
    ).strftime("%Y-%m-%d")

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": date, "start_date": start_date}).fetchall(),
            columns=["cusip", "price_date", "mid_price", "prev_price_1", "prev_price_2"]
        )

    df["exception_type"] = "STALE"
    df["severity"]       = "HIGH"
    df["description"]    = EXCEPTION_RULES["STALE"]["description"]

    logger.info(f"🔍 Stale check: {len(df)} exceptions found")
    return df


# ================================
# Check for Outlier Prices
# ================================
def check_outlier_prices(engine, date: str) -> pd.DataFrame:
    """
    Flag securities where today's price deviates more than
    2 standard deviations from the 30-day rolling average.
    """
    query = text("""
        WITH stats AS (
            SELECT
                cusip,
                AVG(mid_price)    AS avg_price,
                STDDEV(mid_price) AS std_price
            FROM daily_prices
            WHERE price_date BETWEEN :start_date AND :date
            GROUP BY cusip
        ),
        today AS (
            SELECT cusip, mid_price
            FROM daily_prices
            WHERE price_date = :date
        )
        SELECT
            t.cusip,
            t.mid_price,
            s.avg_price,
            s.std_price,
            ABS(t.mid_price - s.avg_price) / NULLIF(s.avg_price, 0) * 100 AS deviation_pct
        FROM today t
        JOIN stats s ON t.cusip = s.cusip
        WHERE
            s.std_price > 0
            AND ABS(t.mid_price - s.avg_price) > (2 * s.std_price)
    """)

    start_date = (
        datetime.strptime(date, "%Y-%m-%d") - timedelta(days=30)
    ).strftime("%Y-%m-%d")

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": date, "start_date": start_date}).fetchall(),
            columns=["cusip", "mid_price", "avg_price", "std_price", "deviation_pct"]
        )

    df["price_date"]    = date
    df["exception_type"] = "OUTLIER"
    df["severity"]       = "HIGH"
    df["description"]    = EXCEPTION_RULES["OUTLIER"]["description"]

    logger.info(f"🔍 Outlier check: {len(df)} exceptions found")
    return df


# ================================
# Check for Missing Prices
# ================================
def check_missing_prices(engine, date: str) -> pd.DataFrame:
    """
    Flag active securities with no price record for today.
    Missing prices are CRITICAL — they block NAV calculation.
    """
    query = text("""
        SELECT
            sm.cusip,
            sm.issuer_name,
            sm.asset_class
        FROM security_master sm
        LEFT JOIN daily_prices dp
            ON sm.cusip = dp.cusip
            AND dp.price_date = :date
        WHERE
            sm.is_active = TRUE
            AND dp.cusip IS NULL
    """)

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": date}).fetchall(),
            columns=["cusip", "issuer_name", "asset_class"]
        )

    df["price_date"]     = date
    df["exception_type"] = "MISSING"
    df["severity"]       = "CRITICAL"
    df["description"]    = EXCEPTION_RULES["MISSING"]["description"]

    logger.info(f"🔍 Missing check: {len(df)} exceptions found")
    return df


# ================================
# Check for Wide Bid-Ask Spreads
# ================================
def check_wide_spreads(engine, date: str) -> pd.DataFrame:
    """
    Flag securities where bid-ask spread > 2%.
    Wide spreads indicate illiquid instruments — pricing risk.
    """
    query = text("""
        SELECT
            cusip,
            price_date,
            bid_price,
            ask_price,
            mid_price,
            (ask_price - bid_price) / NULLIF(mid_price, 0) * 100 AS spread_pct
        FROM daily_prices
        WHERE
            price_date = :date
            AND bid_price IS NOT NULL
            AND ask_price IS NOT NULL
            AND (ask_price - bid_price) / NULLIF(mid_price, 0) * 100 > 2.0
    """)

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": date}).fetchall(),
            columns=["cusip", "price_date", "bid_price", "ask_price", "mid_price", "spread_pct"]
        )

    df["exception_type"] = "GAP"
    df["severity"]       = "MEDIUM"
    df["description"]    = EXCEPTION_RULES["GAP"]["description"]

    logger.info(f"🔍 Spread check: {len(df)} exceptions found")
    return df


# ================================
# Save Exceptions to Database
# ================================
def save_exceptions(exceptions_df: pd.DataFrame, engine):
    """
    Persist all detected exceptions to pricing_exceptions table.
    """
    if exceptions_df.empty:
        return

    for _, row in exceptions_df.iterrows():
        query = text("""
            INSERT INTO pricing_exceptions
                (cusip, exception_date, exception_type,
                 exception_desc, deviation_pct, is_resolved)
            VALUES
                (:cusip, :date, :type, :desc, :deviation, FALSE)
            ON CONFLICT DO NOTHING
        """)

        with engine.begin() as conn:
            conn.execute(query, {
                "cusip":     row.get("cusip"),
                "date":      row.get("price_date"),
                "type":      row.get("exception_type"),
                "desc":      row.get("description"),
                "deviation": row.get("deviation_pct")
            })


# ================================
# Main Exception Engine
# ================================
def run_exception_engine(date: str = None) -> dict:
    """
    Runs all exception checks for a given date.
    Returns summary dict with counts by exception type.
    """
    if not date:
        date = datetime.today().strftime("%Y-%m-%d")

    logger.info(f"🚀 Running exception engine for {date}")

    engine = get_db_engine()

    # Run all checks
    stale   = check_stale_prices(engine, date)
    outlier = check_outlier_prices(engine, date)
    missing = check_missing_prices(engine, date)
    gaps    = check_wide_spreads(engine, date)

    # Combine all exceptions
    all_exceptions = pd.concat(
        [stale, outlier, missing, gaps],
        ignore_index=True
    )

    # Save to database
    save_exceptions(all_exceptions, engine)

    # Build summary
    summary = {
        "date":          date,
        "total":         len(all_exceptions),
        "stale":         len(stale),
        "outlier":       len(outlier),
        "missing":       len(missing),
        "gaps":          len(gaps),
        "critical":      len(all_exceptions[all_exceptions["severity"] == "CRITICAL"]),
        "high":          len(all_exceptions[all_exceptions["severity"] == "HIGH"]),
        "medium":        len(all_exceptions[all_exceptions["severity"] == "MEDIUM"])
    }

    logger.info(
        f"✅ Exception engine complete\n"
        f"   Total:    {summary['total']}\n"
        f"   Critical: {summary['critical']}\n"
        f"   High:     {summary['high']}\n"
        f"   Medium:   {summary['medium']}"
    )

    return summary


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    summary = run_exception_engine()
    print(summary)