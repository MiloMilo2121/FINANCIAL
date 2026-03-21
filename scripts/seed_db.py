#!/usr/bin/env python3
"""
seed_db.py — Load historical gold price seed data into PostgreSQL.

Reads data/seeds/gold_prices_sample.csv and bulk-inserts into price_bars.
Idempotent via ON CONFLICT DO NOTHING.

Usage:
    python scripts/seed_db.py
    # Uses POSTGRES_* env vars or falls back to dev defaults
"""

import csv
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not found — install with: pip install psycopg2-binary")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = REPO_ROOT / "data" / "seeds" / "gold_prices_sample.csv"

PG_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname":   os.environ.get("POSTGRES_DB", "financial_dev"),
    "user":     os.environ.get("POSTGRES_USER", "financial"),
    "password": os.environ.get("POSTGRES_PASSWORD", "financial_dev_password"),
}


def load_csv() -> list[dict]:
    rows = []
    with open(SEED_FILE, newline="") as f:
        reader = csv.DictReader(f)
        prev_close = None
        for row in reader:
            close = float(row["close"])
            log_price = math.log(close)
            log_return = (math.log(close) - math.log(prev_close)) if prev_close else 0.0
            prev_close = close

            ts = datetime.fromisoformat(row["date"]).replace(
                hour=21, minute=0, second=0, tzinfo=timezone.utc
            )
            rows.append({
                "timestamp":   ts,
                "asset":       row["asset"],
                "source":      row["source"],
                "asset_class": "precious_metal",
                "open":        float(row["open"]),
                "high":        float(row["high"]),
                "low":         float(row["low"]),
                "close":       close,
                "volume":      float(row["volume"]),
                "resolution":  "1D",
                "log_price":   log_price,
                "log_return":  log_return,
                "is_outlier":  False,
                "ingested_at": datetime.now(timezone.utc),
            })
    return rows


def main() -> None:
    if not SEED_FILE.exists():
        print(f"Seed file not found: {SEED_FILE}")
        sys.exit(1)

    print(f"Loading {SEED_FILE} ...")
    rows = load_csv()
    print(f"  {len(rows)} rows read")

    conn = psycopg2.connect(**PG_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO price_bars
            (timestamp, asset, source, asset_class, open, high, low, close, volume,
             resolution, log_price, log_return, is_outlier, ingested_at)
        VALUES
            (%(timestamp)s, %(asset)s, %(source)s, %(asset_class)s,
             %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s,
             %(resolution)s, %(log_price)s, %(log_return)s, %(is_outlier)s, %(ingested_at)s)
        ON CONFLICT (timestamp, asset, source, resolution) DO NOTHING
    """

    psycopg2.extras.execute_batch(cur, insert_sql, rows, page_size=500)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM price_bars WHERE source = 'seed'")
    count = cur.fetchone()[0]
    print(f"  {count} rows now in price_bars (source=seed)")

    # Update latest_prices from the last row
    last = rows[-1]
    cur.execute("""
        INSERT INTO latest_prices (asset, price, change_pct, source, updated_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (asset) DO UPDATE
        SET price = EXCLUDED.price,
            source = EXCLUDED.source,
            updated_at = NOW()
    """, (last["asset"], last["close"], last["log_return"] * 100, "seed"))
    conn.commit()

    cur.close()
    conn.close()
    print("Seed complete.")


if __name__ == "__main__":
    main()
