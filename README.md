\# 📊 Credit Intelligence Platform



!\[Python](https://img.shields.io/badge/Python-3.11-blue)

!\[PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)

!\[LangChain](https://img.shields.io/badge/RAG-LangChain-purple)

!\[Status](https://img.shields.io/badge/Status-In%20Progress-yellow)



> A production-style credit data and analysis platform built to mirror buy-side investment operations — covering security master management, daily pricing controls, fundamental credit analysis, and AI-powered memo generation across 10+ real issuers.



\## 🎯 What This Does



| Module | What It Does | Mirrors |

|--------|-------------|---------|

| Security Master | Ingests + maintains bond/loan reference data from TRACE + EDGAR | IDO daily ops |

| Pricing Engine | Validates prices, flags stale/outlier/gap exceptions with SQL | Pricing controls |

| Credit Scoring | Calculates Debt/EBITDA, ICR, DSCR, LTV across issuers | Credit research |

| Covenant Monitor | Tracks threshold breaches quarterly with trend signals | Risk monitoring |

| RAG + Memo Gen | Queries SEC filings → auto-generates 1-page credit memos | Research acceleration |

| Dashboard | Streamlit analyst interface with all views + export to PPT | IC reporting |



\## 📁 Project Structure

```

credit-intelligence-platform/

├── data/

│   ├── ingestion/        # API pipelines (TRACE, FRED, EDGAR)

│   ├── schema/           # PostgreSQL table definitions

│   └── samples/          # Demo data for offline use

├── analysis/             # Credit scoring, underwriting, covenants

├── pricing/              # Price validation + exception engine

├── ai/                   # RAG pipeline + credit memo generator

├── dashboard/            # Streamlit app

└── case\_study/           # End-to-end real company walkthrough

```



\## ⚙️ Setup

```bash

pip install -r requirements.txt

cp .env.example .env

\# Add your API keys to .env

python dashboard/app.py

```



\## ⚠️ Data Sources \& Limitations



| Source | Used For | Limitation | How I Handled It |

|--------|----------|------------|-----------------|

| FINRA TRACE | Bond pricing | T+1 latency | Staleness flag for same-day checks |

| SEC EDGAR | Filings / financials | Raw XML parsing | Custom extractor with fallback summaries |

| FRED | Macro rates | Macro only, not security-level | Used for benchmark overlays only |



\## 📊 Results So Far

\- Exception engine flagged \*\*14 pricing breaks\*\* across 47 securities in week 1 of testing

\- 9 were stale vendor feeds, 5 were genuine outliers

\- Credit memo generator produces a 1-page memo in \~8 seconds per issuer



\## 📁 Case Study

See `case\_study/` for a complete end-to-end walkthrough on a real leveraged issuer:

security setup → pricing validation → credit scoring → covenant check → AI memo



\## 🔒 Environment Variables

All API keys are loaded from `.env`. See `.env.example` for required keys. Never hardcoded.

