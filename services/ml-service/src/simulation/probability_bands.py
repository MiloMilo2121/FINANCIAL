"""Extract probability bands from Monte Carlo results for TradingView display.

Converts MCResult percentile arrays into the format expected by the
TradingView frontend (timestamp-indexed arrays for each percentile).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from financial_ml.simulation.monte_carlo import MCResult


def extract_bands_for_frontend(
    result: MCResult,
    start_date: datetime,
) -> list[dict]:
    """Convert MC percentile bands to frontend-ready format.

    Args:
        result: Monte Carlo simulation result.
        start_date: The date from which simulation starts (today).

    Returns:
        List of dicts, one per future trading day:
        [{
            "timestamp": unix_seconds,
            "date": "YYYY-MM-DD",
            "p5": float,
            "p25": float,
            "p50": float,
            "p75": float,
            "p95": float,
        }]
    """
    bands = []
    current = start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)

    for step in range(result.n_steps):
        # Advance by business days (skip weekends for daily simulation)
        current += timedelta(days=1)
        while current.weekday() >= 5:  # 5=Saturday, 6=Sunday
            current += timedelta(days=1)

        entry = {
            "timestamp": int(current.timestamp()),
            "date": current.strftime("%Y-%m-%d"),
        }
        for percentile, values in result.percentiles.items():
            entry[f"p{percentile}"] = round(float(values[step]), 4)
        bands.append(entry)

    return bands


def extract_tradingview_series(result: MCResult, start_date: datetime) -> dict:
    """Format bands as separate TradingView line series data.

    Returns:
        Dict mapping percentile label to list of {time: unix_sec, value: float}
    """
    bands = extract_bands_for_frontend(result, start_date)

    series = {}
    for p in [5, 25, 50, 75, 95]:
        series[f"p{p}"] = [
            {"time": b["timestamp"], "value": b[f"p{p}"]}
            for b in bands
        ]

    return series
