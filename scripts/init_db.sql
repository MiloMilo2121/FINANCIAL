-- Financial Projection Platform — PostgreSQL initialization
-- Run by setup_dev.sh after docker-compose brings up the DB

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- OHLCV price bars (normalized, cleaned by ETL)
-- ============================================================
CREATE TABLE IF NOT EXISTS price_bars (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp   TIMESTAMPTZ NOT NULL,
    asset       VARCHAR(16) NOT NULL,
    source      VARCHAR(64) NOT NULL,
    asset_class VARCHAR(32) NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    resolution  VARCHAR(8) NOT NULL DEFAULT '1D',
    log_price   DOUBLE PRECISION,
    log_return  DOUBLE PRECISION,
    is_outlier  BOOLEAN DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_price_bars_unique
    ON price_bars (timestamp, asset, source, resolution);

CREATE INDEX IF NOT EXISTS idx_price_bars_asset_ts
    ON price_bars (asset, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_price_bars_asset_resolution
    ON price_bars (asset, resolution, timestamp DESC);

-- ============================================================
-- Latest tick prices (upserted by ingestion service)
-- ============================================================
CREATE TABLE IF NOT EXISTS latest_prices (
    asset       VARCHAR(16) PRIMARY KEY,
    price       DOUBLE PRECISION NOT NULL,
    change_pct  DOUBLE PRECISION DEFAULT 0,
    source      VARCHAR(64),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- ML projections (logged per request for backtesting)
-- ============================================================
CREATE TABLE IF NOT EXISTS projections (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset                   VARCHAR(16) NOT NULL,
    model_type              VARCHAR(32) NOT NULL,
    horizon_days            INT NOT NULL,
    predicted_price         DOUBLE PRECISION NOT NULL,
    confidence              DOUBLE PRECISION,
    ensemble_weight_lstm    DOUBLE PRECISION,
    ensemble_weight_xgb     DOUBLE PRECISION,
    mc_p5                   DOUBLE PRECISION,
    mc_p25                  DOUBLE PRECISION,
    mc_p50                  DOUBLE PRECISION,
    mc_p75                  DOUBLE PRECISION,
    mc_p95                  DOUBLE PRECISION,
    var_95                  DOUBLE PRECISION,
    cvar_95                 DOUBLE PRECISION,
    sentiment_score         DOUBLE PRECISION,
    gpr_level               INT,
    cache_hit               BOOLEAN DEFAULT FALSE,
    latency_ms              INT
);

CREATE INDEX IF NOT EXISTS idx_projections_asset_ts
    ON projections (asset, created_at DESC);

-- ============================================================
-- Sentiment events
-- ============================================================
CREATE TABLE IF NOT EXISTS sentiment_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    asset               VARCHAR(16) NOT NULL,
    headline            TEXT,
    source_url          TEXT,
    overall_score       DOUBLE PRECISION NOT NULL,
    overall_direction   VARCHAR(16) NOT NULL,
    overall_confidence  DOUBLE PRECISION NOT NULL,
    supply_demand_score DOUBLE PRECISION,
    macro_score         DOUBLE PRECISION,
    geopolitical_score  DOUBLE PRECISION,
    institutional_score DOUBLE PRECISION,
    threat_level        INT,
    threat_regions      JSONB,
    net_positioning     VARCHAR(16),
    citations           JSONB,
    perplexity_model    VARCHAR(64),
    processing_ms       INT
);

CREATE INDEX IF NOT EXISTS idx_sentiment_asset_ts
    ON sentiment_events (asset, created_at DESC);

-- ============================================================
-- Geopolitical events (for chart marks)
-- ============================================================
CREATE TABLE IF NOT EXISTS geopolitical_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_date  DATE NOT NULL,
    asset       VARCHAR(16) NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    impact      VARCHAR(16) NOT NULL DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
    source_url  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_geo_events_asset_date
    ON geopolitical_events (asset, event_date DESC);

-- ============================================================
-- Initial seed for latest_prices (dev only)
-- ============================================================
INSERT INTO latest_prices (asset, price, change_pct, source) VALUES
    ('XAU', 2350.00, 0.0, 'seed'),
    ('XAG', 28.50,   0.0, 'seed'),
    ('XPT', 960.00,  0.0, 'seed'),
    ('XPD', 1050.00, 0.0, 'seed')
ON CONFLICT (asset) DO NOTHING;
