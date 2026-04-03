# ================================
# Credit Intelligence Platform
# AI Credit Memo Generator
# ================================

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from sqlalchemy import create_engine, text
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
# Fetch Issuer Data from DB
# ================================
def fetch_issuer_data(issuer_name: str, engine) -> dict:
    """
    Pull all available data for an issuer from the database.
    Combines financials, credit score, pricing, and covenant status.
    """

    # Financials — last 3 years
    fin_query = text("""
        SELECT
            fiscal_year,
            total_debt,
            ebitda,
            interest_expense,
            net_income,
            total_assets,
            debt_ebitda,
            interest_coverage
        FROM issuer_financials
        WHERE issuer_name = :issuer
        ORDER BY fiscal_year DESC
        LIMIT 3
    """)

    # Covenant status
    cov_query = text("""
        SELECT
            ct.covenant_type,
            ct.threshold_value,
            ct.current_value,
            ct.status,
            ct.breach_flag
        FROM covenant_tracking ct
        JOIN security_master sm ON ct.cusip = sm.cusip
        WHERE sm.issuer_name = :issuer
        ORDER BY ct.check_date DESC
        LIMIT 5
    """)

    # Securities
    sec_query = text("""
        SELECT
            cusip,
            asset_class,
            instrument_type,
            coupon_rate,
            maturity_date,
            rating_sp,
            rating_moody
        FROM security_master
        WHERE issuer_name = :issuer
        AND is_active = TRUE
    """)

    with engine.connect() as conn:
        financials = conn.execute(fin_query, {"issuer": issuer_name}).fetchall()
        covenants  = conn.execute(cov_query, {"issuer": issuer_name}).fetchall()
        securities = conn.execute(sec_query, {"issuer": issuer_name}).fetchall()

    return {
        "issuer_name": issuer_name,
        "financials":  [dict(r._mapping) for r in financials],
        "covenants":   [dict(r._mapping) for r in covenants],
        "securities":  [dict(r._mapping) for r in securities]
    }


# ================================
# Credit Memo Prompt Template
# ================================
MEMO_PROMPT = PromptTemplate(
    input_variables=["issuer_name", "financials", "covenants", "securities", "date"],
    template="""
You are a senior credit analyst at a leading alternative asset manager.
Write a concise, professional 1-page credit memo for the following issuer.

ISSUER: {issuer_name}
DATE: {date}

FINANCIAL DATA (most recent 3 years):
{financials}

COVENANT STATUS:
{covenants}

SECURITIES ON BOOK:
{securities}

Write the memo in the following structure:

## CREDIT MEMO — {issuer_name}
**Date:** {date}
**Analyst:** Credit Intelligence Platform

---

### 1. BUSINESS OVERVIEW
2-3 sentences describing the company, industry, and business model.

### 2. FINANCIAL SUMMARY
Summarize key metrics: revenue trend, EBITDA margin, leverage (Debt/EBITDA),
interest coverage. Note any significant year-over-year changes.
Be specific with numbers.

### 3. CREDIT STRENGTHS
3 bullet points — specific strengths based on the data provided.

### 4. KEY RISKS
3 bullet points — specific risks or concerns based on the data provided.

### 5. COVENANT STATUS
Summarize current covenant compliance. Flag any RED or AMBER items clearly.

### 6. CREDIT ASSESSMENT
One paragraph with overall credit view.
End with a credit score out of 10 and a rating label
(e.g. BB — High Yield, B — Speculative).

Keep the memo factual, data-driven, and professional.
Do not invent data not provided. If data is missing, note it as unavailable.
"""
)


# ================================
# Generate Credit Memo
# ================================
def generate_credit_memo(issuer_name: str) -> str:
    """
    Generate a 1-page AI credit memo for a given issuer.

    Args:
        issuer_name: must match issuer_name in security_master table

    Returns:
        Formatted credit memo as a string
    """
    logger.info(f"📝 Generating credit memo for {issuer_name}...")

    engine = get_db_engine()

    # Fetch all issuer data
    data = fetch_issuer_data(issuer_name, engine)

    if not data["financials"]:
        logger.warning(f"No financial data found for {issuer_name}")
        return f"Error: No financial data available for {issuer_name}"

    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,         # Low temp for factual, consistent output
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Format data for prompt
    financials_str = json.dumps(data["financials"], indent=2, default=str)
    covenants_str  = json.dumps(data["covenants"],  indent=2, default=str)
    securities_str = json.dumps(data["securities"], indent=2, default=str)

    # Build prompt
    prompt = MEMO_PROMPT.format(
        issuer_name  = issuer_name,
        financials   = financials_str,
        covenants    = covenants_str,
        securities   = securities_str,
        date         = datetime.today().strftime("%B %d, %Y")
    )

    # Generate memo
    response = llm.invoke(prompt)
    memo_text = response.content

    logger.info(f"✅ Memo generated for {issuer_name} ({len(memo_text)} chars)")

    return memo_text


# ================================
# Save Memo to File
# ================================
def save_memo(issuer_name: str, memo_text: str) -> str:
    """
    Save generated memo to case_study folder.
    Returns the file path.
    """
    safe_name = issuer_name.lower().replace(" ", "_")
    date_str  = datetime.today().strftime("%Y%m%d")
    filename  = f"case_study/{safe_name}_credit_memo_{date_str}.md"

    with open(filename, "w") as f:
        f.write(memo_text)

    logger.info(f"📁 Memo saved to {filename}")
    return filename


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    # Test with a sample issuer
    # Make sure this issuer exists in your security_master table
    issuer = "Ford Motor"

    memo = generate_credit_memo(issuer)
    print(memo)

    # Save to file
    save_memo(issuer, memo)