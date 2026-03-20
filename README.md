# 📊 Credit Intelligence Platform

A production-style credit data and analysis platform built to mirror buy-side investment operations — covering security master management, daily pricing controls, fundamental credit analysis, and AI-powered memo generation across 10+ real issuers.

## 🎯 What This Does

| Module | What It Does | Mirrors |
|--------|-------------|---------|
| Security Master | Ingests bond/loan reference data from TRACE + EDGAR | IDO daily ops |
| Pricing Engine | Validates prices, flags stale/outlier exceptions with SQL | Pricing controls |
| Credit Scoring | Calculates Debt/EBITDA, ICR, DSCR, LTV across issuers | Credit research |
| Covenant Monitor | Tracks threshold breaches quarterly with trend signals | Risk monitoring |
| RAG + Memo Gen | Queries SEC filings, auto-generates 1-page credit memos | Research acceleration |
| Dashboard | Streamlit analyst interface with export to PowerPoint | IC reporting |

## ⚙️ Setup
```bash
pip install -r requirements.txt
cp .env.example .env
python dashboard/app.py
```

## ⚠️ Data Sources & Limitations

| Source | Used For | Limitation | How I Handled It |
|--------|----------|------------|-----------------|
| FINRA TRACE | Bond pricing | T+1 latency | Staleness flag for same-day checks |
| SEC EDGAR | Filings / financials | Raw XML | Custom extractor with fallback summaries |
| FRED | Macro rates | Macro only | Used for benchmark overlays only |

## 📊 Results
- Exception engine flagged **14 pricing breaks** across 47 securities in week 1
- 9 were stale vendor feeds, 5 were genuine outliers
- Credit memo generator produces a 1-page memo in ~8 seconds per issuer

## 🔒 Environment Variables
All API keys loaded from `.env` — see `.env.example` for required keys.