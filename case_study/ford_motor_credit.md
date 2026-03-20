# 📁 Case Study: Ford Motor Credit Company LLC
**Platform:** Credit Intelligence Platform  
**Date:** March 2026  
**Analyst:** Vaishali Hirereaddi  

---

## 1. SECURITY SETUP

**Issuer:** Ford Motor Credit Company LLC  
**Parent:** Ford Motor Company (NYSE: F)  
**Industry:** Auto Manufacturing / Captive Finance  
**CIK:** 0000037996  

### Securities on Book

| CUSIP | Instrument | Coupon | Maturity | Rating (S&P) | Asset Class |
|-------|-----------|--------|----------|--------------|-------------|
| 345397YH4 | Sr. Unsecured Bond | 4.125% | Aug 2025 | BB+ | BOND |
| 345397WN3 | Sr. Unsecured Bond | 5.584% | Mar 2026 | BB+ | BOND |
| 345397XQ5 | Sr. Unsecured Bond | 3.375% | Nov 2026 | BB+ | BOND |

### Security Master Setup Notes
- All 3 securities loaded into PostgreSQL security master
- Asset class: BOND, Instrument type: SR_UNSECURED
- Pricing source: FINRA TRACE
- Currency: USD, Country: USA

---

## 2. PRICING VALIDATION

### Daily Price Run — Sample Output
```
Date: 2026-03-01
Securities priced: 3
Exceptions flagged: 1

EXCEPTION DETECTED:
  CUSIP:          345397YH4
  Type:           STALE
  Description:    Price unchanged for 3 consecutive days (99.12)
  Action:         Flagged for vendor follow-up — approaching maturity,
                  reduced trading activity expected
  Resolution:     Confirmed with TRACE — illiquid near maturity, price valid
```

### Pricing Observations
- Near-maturity bond (Aug 2025) shows reduced price movement — expected
- Spreads on 2026 maturity widened ~15bps in Q1 2026 vs Q4 2025
- All prices within 2σ of 30-day average except stale flag above

---

## 3. FINANCIAL ANALYSIS

### Key Financials (USD Billions)

| Metric | FY2021 | FY2022 | FY2023 |
|--------|--------|--------|--------|
| Revenue | $136.3B | $158.1B | $176.2B |
| EBITDA | $10.2B | $7.8B | $11.4B |
| Total Debt | $47.3B | $48.1B | $46.9B |
| Interest Expense | $2.1B | $2.8B | $3.2B |
| Net Income | $1.8B | $1.9B | $4.3B |

### Credit Ratios

| Ratio | FY2021 | FY2022 | FY2023 | Threshold |
|-------|--------|--------|--------|-----------|
| Debt / EBITDA | 4.6x | 6.2x | 4.1x | < 6.5x |
| Interest Coverage | 4.9x | 2.8x | 3.6x | > 1.5x |
| Debt / Assets | 0.61 | 0.64 | 0.59 | < 0.75 |

### Credit Score Output
```
Running credit scoring model...
Scoring Ford Motor...

  Debt/EBITDA Score:        6/10  (4.1x — Fair)
  Interest Coverage Score:  8/10  (3.6x — Good)
  Debt/Assets Score:        6/10  (0.59 — Fair)

  Weighted Final Score:     6.7 / 10
  Credit Rating:            BB — High Yield
  Trend:                    📈 IMPROVING (Debt/EBITDA: 6.2x → 4.1x)
```

---

## 4. COVENANT MONITORING

### Covenant Check Results

| Covenant | Threshold | Current | Status | Notes |
|----------|-----------|---------|--------|-------|
| MAX_LEVERAGE (Debt/EBITDA) | ≤ 6.5x | 4.1x | 🟢 GREEN | Comfortable buffer |
| MIN_COVERAGE (Int. Coverage) | ≥ 1.5x | 3.6x | 🟢 GREEN | Well above floor |
| MAX_DEBT_ASSETS | ≤ 0.75 | 0.59 | 🟢 GREEN | Within limit |

### Key Observation
FY2022 was the stress year — Debt/EBITDA spiked to 6.2x (approaching
the 6.5x covenant threshold, only 0.3x buffer). Would have triggered
AMBER warning in the covenant monitor. FY2023 recovery brought it back
to 4.1x — significant deleveraging driven by EBITDA improvement.

---

## 5. RAG Q&A — Filing Queries

### Q: What is the leverage trend over the last 3 years?
> *Answer (from 10-K RAG pipeline):*  
> Ford's leverage improved materially in FY2023, with Debt/EBITDA declining  
> from 6.2x in FY2022 to 4.1x in FY2023, driven by a 46% increase in EBITDA  
> to $11.4B. The company cited strong pricing power and cost discipline  
> in its automotive segment as key drivers. Long-term debt declined slightly  
> to $46.9B from $48.1B.

### Q: What are the main risk factors mentioned in the filing?
> *Answer (from 10-K RAG pipeline):*  
> Key risks include: (1) EV transition costs — Ford is investing $50B+ through  
> 2026 in electrification with near-term margin pressure on Model e segment,  
> (2) Supply chain concentration in semiconductors, (3) Pension obligations  
> of ~$8B, and (4) Interest rate sensitivity given floating rate debt exposure  
> at Ford Credit.

### Q: Has the company breached any debt covenants?
> *Answer (from 10-K RAG pipeline):*  
> No covenant breaches reported in FY2023 10-K. The filing notes maintenance  
> covenants on Ford Credit's credit facilities require minimum liquidity of  
> $4B — Ford Credit reported $25B+ in liquidity as of year-end.

---

## 6. AI-GENERATED CREDIT MEMO

---

## CREDIT MEMO — Ford Motor Credit Company LLC
**Date:** March 1, 2026  
**Analyst:** Credit Intelligence Platform  

---

### 1. BUSINESS OVERVIEW
Ford Motor Credit Company LLC is the captive finance subsidiary of Ford Motor
Company, one of the world's largest automakers. The company provides retail
and commercial financing, leasing, and insurance products to Ford dealers and
customers globally. Ford Credit's performance is closely tied to Ford's vehicle
sales volumes, interest rate movements, and used vehicle residual values.

### 2. FINANCIAL SUMMARY
Ford demonstrated meaningful credit improvement in FY2023, with EBITDA
recovering to $11.4B (+46% YoY) after a challenging FY2022. Leverage declined
from 6.2x to 4.1x Debt/EBITDA, while interest coverage improved to 3.6x from
2.8x. Total debt was modestly reduced to $46.9B. The improvement was driven
by strong pricing in the Pro (commercial) segment and ongoing cost discipline,
partially offset by EV segment losses of ~$4.7B.

### 3. CREDIT STRENGTHS
- **Deleveraging trajectory:** Debt/EBITDA improved 210bps YoY to 4.1x —
  well within the 6.5x covenant threshold with meaningful headroom
- **Diversified funding:** Ford Credit maintains $25B+ liquidity with
  diversified funding across ABS, unsecured bonds, and committed credit lines
- **Pro segment strength:** Commercial vehicle segment generates stable,
  high-margin revenue providing a reliable earnings floor

### 4. KEY RISKS
- **EV losses:** Model e segment burning ~$4.7B/year — drag on consolidated
  EBITDA until scale is achieved; timeline uncertain
- **Interest rate sensitivity:** Rising rates increase Ford Credit's funding
  costs and pressure net interest margins on retail loan portfolio
- **Residual value risk:** Softening used vehicle prices could trigger
  higher-than-expected lease losses at Ford Credit

### 5. COVENANT STATUS
All covenants GREEN as of FY2023. Closest to threshold was FY2022 leverage
at 6.2x vs 6.5x limit (5% buffer) — would have triggered AMBER alert.
FY2023 deleveraging has restored comfortable headroom across all metrics.

### 6. CREDIT ASSESSMENT
Ford Motor Credit presents a stabilizing credit profile after the FY2022
stress period. The FY2023 recovery demonstrates earnings resilience and
management's ability to deleverage under pressure. Key watch items are
EV segment losses and interest rate exposure. We assign a credit score of
**6.7 / 10**, consistent with a **BB — High Yield** rating, with a
positive trend outlook given the improving leverage trajectory.

---

## 7. PLATFORM NOTES

### What This Case Study Demonstrates
- **Security master setup** — 3 real Ford bonds loaded with full reference data
- **Pricing pipeline** — TRACE prices validated, stale exception detected and resolved
- **Credit scoring** — Full ratio model applied with 3-year trend analysis
- **Covenant monitoring** — All 3 covenants checked, FY2022 stress scenario highlighted
- **RAG queries** — 3 real credit questions answered from 10-K filing
- **AI memo** — Full 1-page credit memo auto-generated from database + filing data

### Data Sources Used
- FINRA TRACE — bond pricing
- SEC EDGAR CIK 0000037996 — 10-K filings FY2021–2023
- Calculated ratios from EDGAR XBRL financial data