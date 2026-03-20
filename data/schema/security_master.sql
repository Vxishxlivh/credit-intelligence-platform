-- ================================
-- Credit Intelligence Platform
-- Security Master Schema
-- ================================

-- Core security master table
CREATE TABLE IF NOT EXISTS security_master (
    id                  SERIAL PRIMARY KEY,
    cusip               VARCHAR(9) UNIQUE,
    isin                VARCHAR(12),
    ticker              VARCHAR(20),
    issuer_name         VARCHAR(255) NOT NULL,
    asset_class         VARCHAR(50),  -- BOND, BANK_LOAN, ABS, CLO
    instrument_type     VARCHAR(50),  -- SR_SECURED, SR_UNSECURED, SUB, MEZZ
    coupon_rate         DECIMAL(8,4),
    coupon_type         VARCHAR(20),  -- FIXED, FLOATING, ZERO
    maturity_date       DATE,
    issue_date          DATE,
    currency            VARCHAR(3) DEFAULT 'USD',
    country             VARCHAR(3) DEFAULT 'USA',
    rating_sp           VARCHAR(10),  -- S&P rating
    rating_moody        VARCHAR(10),  -- Moody's rating
    industry_sector     VARCHAR(100),
    face_value          DECIMAL(18,2),
    outstanding_amount  DECIMAL(18,2),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily pricing table
CREATE TABLE IF NOT EXISTS daily_prices (
    id              SERIAL PRIMARY KEY,
    cusip           VARCHAR(9) REFERENCES security_master(cusip),
    price_date      DATE NOT NULL,
    bid_price       DECIMAL(12,6),
    ask_price       DECIMAL(12,6),
    mid_price       DECIMAL(12,6),
    last_price      DECIMAL(12,6),
    price_source    VARCHAR(50),  -- TRACE, BLOOMBERG, MANUAL
    is_stale        BOOLEAN DEFAULT FALSE,
    is_outlier      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(cusip, price_date)
);

-- Pricing exceptions table
CREATE TABLE IF NOT EXISTS pricing_exceptions (
    id              SERIAL PRIMARY KEY,
    cusip           VARCHAR(9) REFERENCES security_master(cusip),
    exception_date  DATE NOT NULL,
    exception_type  VARCHAR(50),  -- STALE, OUTLIER, MISSING, GAP
    exception_desc  TEXT,
    price_expected  DECIMAL(12,6),
    price_actual    DECIMAL(12,6),
    deviation_pct   DECIMAL(8,4),
    is_resolved     BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Issuer financials table
CREATE TABLE IF NOT EXISTS issuer_financials (
    id              SERIAL PRIMARY KEY,
    issuer_name     VARCHAR(255),
    fiscal_year     INTEGER,
    fiscal_quarter  INTEGER,
    total_debt      DECIMAL(18,2),
    ebitda          DECIMAL(18,2),
    interest_expense DECIMAL(18,2),
    net_income      DECIMAL(18,2),
    total_assets    DECIMAL(18,2),
    debt_ebitda     DECIMAL(8,4),  -- calculated
    interest_coverage DECIMAL(8,4), -- calculated
    data_source     VARCHAR(50),   -- EDGAR, MANUAL
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Covenant tracking table
CREATE TABLE IF NOT EXISTS covenant_tracking (
    id                  SERIAL PRIMARY KEY,
    cusip               VARCHAR(9) REFERENCES security_master(cusip),
    covenant_type       VARCHAR(100), -- MAX_LEVERAGE, MIN_COVERAGE, MIN_LIQUIDITY
    threshold_value     DECIMAL(12,4),
    current_value       DECIMAL(12,4),
    check_date          DATE,
    status              VARCHAR(10),  -- GREEN, AMBER, RED
    breach_flag         BOOLEAN DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================================
-- Indexes for performance
-- ================================
CREATE INDEX IF NOT EXISTS idx_prices_cusip_date 
    ON daily_prices(cusip, price_date);

CREATE INDEX IF NOT EXISTS idx_exceptions_date 
    ON pricing_exceptions(exception_date);

CREATE INDEX IF NOT EXISTS idx_covenants_status 
    ON covenant_tracking(status, check_date);

CREATE INDEX IF NOT EXISTS idx_security_asset_class 
    ON security_master(asset_class, is_active);