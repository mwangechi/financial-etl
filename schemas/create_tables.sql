-- ============================================================
-- Financial ETL — Database Schema
-- ============================================================

-- Daily stock prices
CREATE TABLE IF NOT EXISTS daily_stock_prices (
    date          DATE NOT NULL,
    symbol        VARCHAR(10) NOT NULL,
    open_price    NUMERIC(12,4),
    high_price    NUMERIC(12,4),
    low_price     NUMERIC(12,4),
    close_price   NUMERIC(12,4),
    volume        BIGINT,
    daily_return   NUMERIC(10,6),
    price_range    NUMERIC(12,4),
    volatility_pct NUMERIC(8,4),
    loaded_at     TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_stock_symbol ON daily_stock_prices (symbol);
CREATE INDEX IF NOT EXISTS idx_stock_date   ON daily_stock_prices (date);

-- Daily forex rates
CREATE TABLE IF NOT EXISTS forex_daily_rates (
    date       DATE NOT NULL,
    pair       VARCHAR(10) NOT NULL,
    open_rate  NUMERIC(14,6),
    high_rate  NUMERIC(14,6),
    low_rate   NUMERIC(14,6),
    close_rate NUMERIC(14,6),
    loaded_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (date, pair)
);

CREATE INDEX IF NOT EXISTS idx_forex_pair ON forex_daily_rates (pair);
CREATE INDEX IF NOT EXISTS idx_forex_date ON forex_daily_rates (date);

-- ETL run log
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id       VARCHAR(20) PRIMARY KEY,
    started_at   TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status       VARCHAR(20) DEFAULT 'running',
    rows_extracted   INTEGER DEFAULT 0,
    rows_transformed INTEGER DEFAULT 0,
    rows_loaded      INTEGER DEFAULT 0,
    errors       TEXT
);
