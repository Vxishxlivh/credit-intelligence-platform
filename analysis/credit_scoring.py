# ================================
# Credit Intelligence Platform
# Credit Scoring Model
# ================================

import pandas as pd
import numpy as np
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
# Scoring Thresholds
# Based on typical buy-side credit criteria
# ================================
SCORING_THRESHOLDS = {
    "debt_ebitda": {
        # Lower is better
        "excellent": 2.0,   # <= 2x  → 10 points
        "good":      3.5,   # <= 3.5x → 8 points
        "fair":      5.0,   # <= 5x  → 6 points
        "weak":      6.5,   # <= 6.5x → 4 points
        "poor":      8.0,   # <= 8x  → 2 points
                            # > 8x   → 0 points
    },
    "interest_coverage": {
        # Higher is better
        "excellent": 5.0,   # >= 5x  → 10 points
        "good":      3.5,   # >= 3.5x → 8 points
        "fair":      2.5,   # >= 2.5x → 6 points
        "weak":      1.5,   # >= 1.5x → 4 points
        "poor":      1.0,   # >= 1x  → 2 points
                            # < 1x   → 0 points
    },
    "debt_assets": {
        # Lower is better
        "excellent": 0.30,  # <= 30% → 10 points
        "good":      0.45,  # <= 45% → 8 points
        "fair":      0.60,  # <= 60% → 6 points
        "weak":      0.75,  # <= 75% → 4 points
        "poor":      0.85,  # <= 85% → 2 points
                            # > 85%  → 0 points
    }
}

# Metric weights in final score
WEIGHTS = {
    "debt_ebitda_score":      0.40,  # Most important for leveraged credit
    "interest_coverage_score": 0.35,  # Key solvency indicator
    "debt_assets_score":       0.25,  # Balance sheet leverage
}


# ================================
# Individual Metric Scorers
# ================================
def score_debt_ebitda(ratio: float) -> int:
    """Score Debt/EBITDA — lower is better."""
    if ratio is None:
        return 0
    t = SCORING_THRESHOLDS["debt_ebitda"]
    if ratio <= t["excellent"]:  return 10
    elif ratio <= t["good"]:     return 8
    elif ratio <= t["fair"]:     return 6
    elif ratio <= t["weak"]:     return 4
    elif ratio <= t["poor"]:     return 2
    else:                        return 0


def score_interest_coverage(ratio: float) -> int:
    """Score Interest Coverage Ratio — higher is better."""
    if ratio is None:
        return 0
    t = SCORING_THRESHOLDS["interest_coverage"]
    if ratio >= t["excellent"]:  return 10
    elif ratio >= t["good"]:     return 8
    elif ratio >= t["fair"]:     return 6
    elif ratio >= t["weak"]:     return 4
    elif ratio >= t["poor"]:     return 2
    else:                        return 0


def score_debt_assets(ratio: float) -> int:
    """Score Debt/Assets — lower is better."""
    if ratio is None:
        return 0
    t = SCORING_THRESHOLDS["debt_assets"]
    if ratio <= t["excellent"]:  return 10
    elif ratio <= t["good"]:     return 8
    elif ratio <= t["fair"]:     return 6
    elif ratio <= t["weak"]:     return 4
    elif ratio <= t["poor"]:     return 2
    else:                        return 0


# ================================
# Final Credit Score Calculator
# ================================
def calculate_credit_score(row: pd.Series) -> dict:
    """
    Calculate weighted credit score for a single issuer.
    Score ranges from 0 (worst) to 10 (best).

    Returns:
        dict with individual scores, weighted total, and rating label
    """
    debt_ebitda = row.get("debt_ebitda")
    interest_coverage = row.get("interest_coverage")
    debt_assets = (
        row.get("total_debt") / row.get("total_assets")
        if row.get("total_assets") and row.get("total_assets") != 0
        else None
    )

    # Individual scores
    de_score  = score_debt_ebitda(debt_ebitda)
    ic_score  = score_interest_coverage(interest_coverage)
    da_score  = score_debt_assets(debt_assets)

    # Weighted final score
    final_score = (
        de_score  * WEIGHTS["debt_ebitda_score"] +
        ic_score  * WEIGHTS["interest_coverage_score"] +
        da_score  * WEIGHTS["debt_assets_score"]
    )

    # Map score to rating label
    if final_score >= 8.5:   rating = "AAA/AA — Very Strong"
    elif final_score >= 7.0: rating = "A/BBB — Investment Grade"
    elif final_score >= 5.5: rating = "BB — High Yield"
    elif final_score >= 4.0: rating = "B — Speculative"
    elif final_score >= 2.5: rating = "CCC — Distressed"
    else:                    rating = "D — Default Risk"

    return {
        "debt_ebitda":          round(debt_ebitda, 2) if debt_ebitda else None,
        "interest_coverage":    round(interest_coverage, 2) if interest_coverage else None,
        "debt_assets":          round(debt_assets, 2) if debt_assets else None,
        "debt_ebitda_score":    de_score,
        "interest_coverage_score": ic_score,
        "debt_assets_score":    da_score,
        "final_score":          round(final_score, 2),
        "credit_rating":        rating
    }


# ================================
# Trend Analysis
# ================================
def analyze_trend(issuer_name: str, engine) -> str:
    """
    Compare most recent year vs prior year Debt/EBITDA.
    Returns trend signal: IMPROVING, STABLE, DETERIORATING
    """
    query = text("""
        SELECT fiscal_year, debt_ebitda
        FROM issuer_financials
        WHERE issuer_name = :issuer
        ORDER BY fiscal_year DESC
        LIMIT 2
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"issuer": issuer_name})
        rows = result.fetchall()

    if len(rows) < 2:
        return "INSUFFICIENT DATA"

    current = rows[0][1]
    prior   = rows[1][1]

    if current is None or prior is None:
        return "INSUFFICIENT DATA"

    change = current - prior

    if change < -0.5:   return "📈 IMPROVING"
    elif change > 0.5:  return "📉 DETERIORATING"
    else:               return "➡️  STABLE"


# ================================
# Run Scoring for All Issuers
# ================================
def run_credit_scoring() -> pd.DataFrame:
    """
    Main function — scores all issuers in the database
    using their most recent annual financials.

    Returns:
        DataFrame with scores ranked best to worst
    """
    logger.info("🚀 Running credit scoring model...")

    engine = get_db_engine()

    # Pull most recent financials per issuer
    query = text("""
        SELECT DISTINCT ON (issuer_name)
            issuer_name,
            fiscal_year,
            total_debt,
            ebitda,
            interest_expense,
            net_income,
            total_assets,
            debt_ebitda,
            interest_coverage
        FROM issuer_financials
        ORDER BY issuer_name, fiscal_year DESC
    """)

    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query).fetchall(),
            columns=[
                "issuer_name", "fiscal_year", "total_debt",
                "ebitda", "interest_expense", "net_income",
                "total_assets", "debt_ebitda", "interest_coverage"
            ]
        )

    if df.empty:
        logger.warning("No financial data found. Run fetch_edgar.py first.")
        return pd.DataFrame()

    logger.info(f"📋 Scoring {len(df)} issuers...")

    # Apply scoring model to each issuer
    scores = df.apply(calculate_credit_score, axis=1, result_type="expand")
    df = pd.concat([df[["issuer_name", "fiscal_year"]], scores], axis=1)

    # Add trend signal
    df["trend"] = df["issuer_name"].apply(
        lambda x: analyze_trend(x, engine)
    )

    # Rank by final score
    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    df.index += 1  # Start ranking from 1

    logger.info("✅ Credit scoring complete")
    logger.info("\n" + df[["issuer_name", "final_score", "credit_rating", "trend"]].to_string())

    return df


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    results = run_credit_scoring()
    if not results.empty:
        results.to_csv("analysis/credit_scores_output.csv", index=True)
        logger.info("📁 Results saved to analysis/credit_scores_output.csv")