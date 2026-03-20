# ================================
# Credit Intelligence Platform
# SEC EDGAR Financial Data Pipeline
# ================================

import requests
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import logging
import time

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# EDGAR requires a user agent header identifying yourself
HEADERS = {
    "User-Agent": os.getenv("EDGAR_USER_AGENT", "credit-platform research@example.com"),
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

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
# Get Company CIK from EDGAR
# ================================
def get_cik(company_name: str) -> str:
    """
    Look up a company's CIK (Central Index Key) from EDGAR.
    CIK is required to fetch any company's filings.

    Args:
        company_name: company name to search (e.g. 'Ford Motor')

    Returns:
        CIK string (zero-padded to 10 digits) or None
    """
    url = "https://efts.sec.gov/LATEST/search-index?q={}&dateRange=custom&startdt=2020-01-01&enddt=2024-01-01&forms=10-K"
    search_url = f"https://efts.sec.gov/LATEST/search-index?q={company_name}&forms=10-K"

    try:
        # Use the company search endpoint
        ticker_url = "https://www.sec.gov/cgi-bin/browse-edgar?company={}&CIK=&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany"
        
        # Simpler: use the known CIK lookup
        cik_url = f"https://data.sec.gov/submissions/CIK{{}}.json"
        
        # Search via EDGAR full-text search
        response = requests.get(
            "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&forms=10-K".format(
                company_name.replace(" ", "+")
            ),
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("hits", {}).get("hits"):
            cik = data["hits"]["hits"][0]["_source"]["period_of_report"]
            entity_id = data["hits"]["hits"][0]["_id"].split(":")[0]
            return entity_id.zfill(10)

        logger.warning(f"CIK not found for {company_name}")
        return None

    except Exception as e:
        logger.error(f"Error fetching CIK for {company_name}: {e}")
        return None


# ================================
# Fetch Company Facts from EDGAR
# ================================
def fetch_company_facts(cik: str) -> dict:
    """
    Fetch all reported financial facts for a company from EDGAR.
    This includes income statement, balance sheet, and cash flow items.

    Args:
        cik: 10-digit CIK string

    Returns:
        dict of financial facts by concept
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        # Respect EDGAR rate limits — 10 requests per second max
        time.sleep(0.15)
        
        return response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching facts for CIK {cik}: {e}")
        return None


# ================================
# Extract Key Financial Metrics
# ================================
def extract_financials(facts: dict, issuer_name: str) -> list:
    """
    Extract key credit metrics from raw EDGAR facts.
    Pulls most recent 4 quarters of data.

    Returns:
        list of dicts with standardized financial metrics
    """
    if not facts:
        return []

    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    records = []

    # Map EDGAR concepts to our metrics
    concept_map = {
        "LongTermDebt": "long_term_debt",
        "ShortTermBorrowings": "short_term_debt",
        "OperatingIncomeLoss": "ebit",
        "InterestExpense": "interest_expense",
        "NetIncomeLoss": "net_income",
        "Assets": "total_assets",
        "EarningsPerShareBasic": "eps",
        "Revenues": "revenue",
        "DepreciationDepletionAndAmortization": "dna"
    }

    # Build a flat dict of most recent annual values
    annual_data = {}

    for concept, field in concept_map.items():
        if concept not in us_gaap:
            continue

        units = us_gaap[concept].get("units", {})
        usd_data = units.get("USD", [])

        if not usd_data:
            continue

        # Filter to annual 10-K filings only
        annual = [
            x for x in usd_data
            if x.get("form") == "10-K" and x.get("fp") == "FY"
        ]

        if not annual:
            continue

        # Sort by end date, take most recent 4 years
        annual_sorted = sorted(annual, key=lambda x: x["end"], reverse=True)[:4]

        for entry in annual_sorted:
            year = entry["end"][:4]
            if year not in annual_data:
                annual_data[year] = {"fiscal_year": int(year)}
            annual_data[year][field] = entry["val"]

    # Calculate credit ratios for each year
    for year, data in annual_data.items():
        total_debt = data.get("long_term_debt", 0) + data.get("short_term_debt", 0)
        ebit = data.get("ebit", 0)
        dna = data.get("dna", 0)
        ebitda = ebit + dna if ebit and dna else None
        interest = data.get("interest_expense", 0)

        record = {
            "issuer_name": issuer_name,
            "fiscal_year": int(year),
            "fiscal_quarter": 4,
            "total_debt": total_debt,
            "ebitda": ebitda,
            "interest_expense": interest,
            "net_income": data.get("net_income"),
            "total_assets": data.get("total_assets"),
            # Calculate key credit ratios
            "debt_ebitda": round(total_debt / ebitda, 2) if ebitda and ebitda != 0 else None,
            "interest_coverage": round(ebitda / interest, 2) if interest and interest != 0 else None,
            "data_source": "EDGAR"
        }

        records.append(record)

    return records


# ================================
# Save Financials to Database
# ================================
def save_financials(records: list, engine):
    """
    Insert extracted financials into issuer_financials table.
    """
    if not records:
        return

    df = pd.DataFrame(records)

    df.to_sql(
        "issuer_financials",
        engine,
        if_exists="append",
        index=False,
        method="multi"
    )

    logger.info(f"✅ Saved {len(records)} financial records")


# ================================
# Main Pipeline
# ================================
def run_financials_pipeline(issuers: list):
    """
    Main entry point — fetch and store financials for a list of issuers.

    Args:
        issuers: list of company names matching security_master.issuer_name

    Example:
        run_financials_pipeline(["Ford Motor", "General Motors", "Tesla"])
    """
    logger.info(f"🚀 Starting EDGAR financials pipeline for {len(issuers)} issuers")

    engine = get_db_engine()
    total_saved = 0

    for issuer in issuers:
        logger.info(f"📄 Fetching data for: {issuer}")

        # Step 1 — Get CIK
        cik = get_cik(issuer)
        if not cik:
            logger.warning(f"⚠️  Skipping {issuer} — CIK not found")
            continue

        # Step 2 — Fetch facts
        facts = fetch_company_facts(cik)
        if not facts:
            logger.warning(f"⚠️  Skipping {issuer} — No facts returned")
            continue

        # Step 3 — Extract metrics
        records = extract_financials(facts, issuer)
        if not records:
            logger.warning(f"⚠️  No financials extracted for {issuer}")
            continue

        # Step 4 — Save to DB
        save_financials(records, engine)
        total_saved += len(records)

        logger.info(f"✅ {issuer} — saved {len(records)} years of data")

        # Respect EDGAR rate limits
        time.sleep(0.5)

    logger.info(f"🏁 Pipeline complete — {total_saved} total records saved")


# ================================
# Entry Point
# ================================
if __name__ == "__main__":
    # Sample issuers — update with your security master issuers
    sample_issuers = [
        "Ford Motor",
        "General Motors",
        "Tesla",
        "Marriott International",
        "Hilton Worldwide"
    ]
    run_financials_pipeline(sample_issuers)