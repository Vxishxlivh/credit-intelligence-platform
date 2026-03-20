# ================================
# Credit Intelligence Platform
# Covenant Breach Monitor
# ================================

import pandas as pd
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
# Covenant Definitions
# Standard thresholds used in leveraged credit
# ================================
COVENANTS = [
    {
        "covenant_type": "MAX_LEVERAGE",
        "description":   "Maximum Debt/EBITDA",
        "threshold":      6.5,
        "metric":         "debt_ebitda",
        "breach_when":    "above"   # breach if current > threshold
    },
    {
        "covenant_type": "MIN_COVERAGE",
        "description":   "Minimum Interest Coverage",
        "threshold":      1.5,
        "metric":         "interest_coverage",
        "breach_when":    "below"   # breach if current < threshold
    },
    {
        "covenant_type": "MAX_DEBT_ASSETS",
        "description":   "Maximum Debt/Assets",
        "threshold":      0.75,
        "metric":         "debt_assets",
        "breach_when":    "above"
    }
]


# ================================
# Determine Covenant Status
# ================================
def get_status(current_value: float, threshold: float, breach_when: str) -> str:
    """
    Returns GREEN, AMBER, or RED based on proximity to threshold.

    GREEN  → comfortable (>20% buffer from threshold)
    AMBER  → approaching (within 20% of threshold)
    RED    → breached or at threshold
    """
    if current_value is None:
        return "UNKNOWN"

    if breach_when == "above":
        buffer = (threshold - current_value) / threshold
        if current_value >= threshold:     return "RED"
        elif buffer <= 0.20:               return "AMBER"
        else:                              return "GREEN"

    elif breach_when == "below":
        buffer = (current_value - threshold) / threshold
        if current_value <= threshold:     return "RED"
        elif buffer <= 0.20:               return "AMBER"
        else:                              return "GREEN"

    return "UNKNOWN"


# ================================
# Run Covenant Check for All Issuers
# ================================
def run_covenant_monitor() -> pd.DataFrame:
    """
    Runs all covenant checks across all issuers.
    Saves results to covenant_tracking table.

    Returns:
        DataFrame with covenant status per issuer per covenant
    """
    logger.info("🚀 Running covenant monitor...")

    engine = get_db_engine()

    # Pull most recent financials per issuer
    query = text("""
        SELECT DISTINCT ON (issuer_name)
            issuer_name,
            fiscal_year,
            debt_ebitda,
            interest_coverage,
            total_debt,
            total_assets
        FROM issuer_financials
        ORDER BY issuer_name, fiscal_year DESC
    """)

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query).fetchall(),
            columns=[
                "issuer_name", "fiscal_year",
                "debt_ebitda", "interest_coverage",
                "total_debt", "total_assets"
            ]
        )

    if df.empty:
        logger.warning("No financial data found. Run fetch_edgar.py first.")
        return pd.DataFrame()

    # Calculate debt/assets ratio
    df["debt_assets"] = df.apply(
        lambda r: round(r["total_debt"] / r["total_assets"], 4)
        if r["total_assets"] and r["total_assets"] != 0 else None,
        axis=1
    )

    results = []

    for _, row in df.iterrows():
        for covenant in COVENANTS:
            metric     = covenant["metric"]
            threshold  = covenant["threshold"]
            breach_when = covenant["breach_when"]
            current    = row.get(metric)

            status = get_status(current, threshold, breach_when)
            breach = status == "RED"

            result = {
                "issuer_name":    row["issuer_name"],
                "fiscal_year":    row["fiscal_year"],
                "covenant_type":  covenant["covenant_type"],
                "description":    covenant["description"],
                "threshold":      threshold,
                "current_value":  current,
                "status":         status,
                "breach_flag":    breach
            }

            results.append(result)

            # Save to DB
            save_covenant_check(
                issuer=row["issuer_name"],
                covenant_type=covenant["covenant_type"],
                threshold=threshold,
                current=current,
                status=status,
                breach=breach,
                engine=engine
            )

    results_df = pd.DataFrame(results)

    # Print summary
    breaches = results_df[results_df["breach_flag"] == True]
    amber    = results_df[results_df["status"] == "AMBER"]

    logger.info(f"✅ Covenant check complete")
    logger.info(f"🔴 Breaches: {len(breaches)}")
    logger.info(f"🟡 Amber warnings: {len(amber)}")

    if not breaches.empty:
        logger.warning("\n⚠️  COVENANT BREACHES DETECTED:")
        logger.warning(breaches[["issuer_name", "covenant_type", "threshold", "current_value"]].to_string())

    return results_df


# ================================
# Save Covenant Check to DB
# ================================
def save_covenant_check(
    issuer, covenant_type, threshold,
    current, status, breach, engine
):
    query = text("""
        INSERT INTO covenant_tracking
            (cusip, covenant_type, threshold_value, current_value,
             check_date, status, breach_flag)
        SELECT
            sm.cusip,
            :covenant_type,
            :threshold,
            :current,
            CURRENT_DATE,
            :status,
            :breach
        FROM security_master sm
        WHERE sm.issuer_name = :issuer
        LIMIT 1
        ON CONFLICT DO NOTHING
    """)

    with engine.begin() as conn:
        conn.execute(query, {
            "issuer":        issuer,
            "covenant_type": covenant_type,
            "threshold":     threshold,
            "current":       current,
            "status":        status,
            "breach":        breach
        })


# ================================
# Get Breach Summary (for dashboard)
# ================================
def get_breach_summary(engine) -> pd.DataFrame:
    """
    Returns all current RED and AMBER covenants.
    Used by the Streamlit dashboard.
    """
    query = text("""
        SELECT
            sm.issuer_name,
            ct.covenant_type,
            ct.threshold_value,
            ct.current_value,
            ct.status,
            ct.breach_flag,
            ct.check_date
        FROM covenant_tracking ct
        JOIN security_master sm ON ct.cusip = sm.cusip
        WHERE ct.status IN ('RED', 'AMBER')
        ORDER BY ct.breach_flag DESC, ct.check_date DESC
    """)

    with engine.connect() as conn:
        return pd.DataFrame(conn.execute(query).fetchall())


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    results = run_covenant_monitor()
    if not results.empty:
        results.to_csv("analysis/covenant_monitor_output.csv", index=False)
        logger.info("📁 Saved to analysis/covenant_monitor_output.csv")