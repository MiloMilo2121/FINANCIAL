#!/usr/bin/env python3
"""
smoke_test.py — Post-deployment smoke tests for the Financial Projection Platform.

Validates that all critical endpoints are reachable and return expected responses.
Exits 0 on success, 1 on failure. Designed for Cloud Build CI/CD pipeline.

Usage:
    python scripts/smoke_test.py --base-url http://api-gateway:8000
    python scripts/smoke_test.py  # defaults to localhost:8000
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    latency_ms: float


def http_get(url: str, timeout: int = 10) -> tuple[int, Any, float]:
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            latency = (time.monotonic() - start) * 1000
            return resp.status, body, latency
    except urllib.error.HTTPError as e:
        latency = (time.monotonic() - start) * 1000
        return e.code, {}, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return 0, {"error": str(e)}, latency


def http_post(url: str, payload: dict, timeout: int = 30) -> tuple[int, Any, float]:
    start = time.monotonic()
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
            latency = (time.monotonic() - start) * 1000
            return resp.status, body, latency
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except Exception:
            body = {}
        latency = (time.monotonic() - start) * 1000
        return e.code, body, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return 0, {"error": str(e)}, latency


def run_tests(base_url: str) -> list[TestResult]:
    results: list[TestResult] = []

    def check(name: str, status: int, body: Any, latency: float,
               expected_status: int = 200, required_keys: list[str] | None = None) -> None:
        if status != expected_status:
            results.append(TestResult(name, False,
                                      f"HTTP {status} (expected {expected_status})", latency))
            return
        if required_keys:
            missing = [k for k in required_keys if k not in body]
            if missing:
                results.append(TestResult(name, False,
                                          f"Missing keys: {missing}", latency))
                return
        results.append(TestResult(name, True, f"HTTP {status} in {latency:.0f}ms", latency))

    # ── API Gateway health ────────────────────────────────────
    status, body, latency = http_get(f"{base_url}/health")
    check("API Gateway /health", status, body, latency, required_keys=["status"])

    status, body, latency = http_get(f"{base_url}/ready")
    check("API Gateway /ready", status, body, latency)

    # ── Price endpoints ───────────────────────────────────────
    status, body, latency = http_get(f"{base_url}/prices/XAU/latest")
    check("Prices /XAU/latest", status, body, latency, required_keys=["asset", "price"])

    status, body, latency = http_get(f"{base_url}/prices/XAG/latest")
    check("Prices /XAG/latest", status, body, latency, required_keys=["asset", "price"])

    status, body, latency = http_get(f"{base_url}/prices/XAU/bars?resolution=1D&limit=10")
    check("Prices /XAU/bars (1D)", status, body, latency, required_keys=["s", "t", "c"])

    # ── Projection endpoints ──────────────────────────────────
    status, body, latency = http_post(
        f"{base_url}/projections/predict",
        {"asset": "XAU", "horizon_days": 5},
        timeout=30,
    )
    check("Projections /predict (XAU, 5D)", status, body, latency,
          required_keys=["asset", "model_type", "predicted_price"])

    status, body, latency = http_post(
        f"{base_url}/projections/simulate",
        {"asset": "XAU", "n_paths": 1000, "horizon_days": 30},
        timeout=60,
    )
    check("Projections /simulate (XAU, 1k paths, 30D)", status, body, latency,
          required_keys=["asset", "percentile_bands"])

    # ── Sentiment endpoints ───────────────────────────────────
    status, body, latency = http_post(
        f"{base_url}/sentiment/analyze",
        {"text": "Gold prices rise amid geopolitical tensions", "asset": "XAU"},
        timeout=30,
    )
    check("Sentiment /analyze", status, body, latency,
          required_keys=["overall"])

    status, body, latency = http_get(f"{base_url}/sentiment/marks/XAU")
    check("Sentiment /marks/XAU", status, body, latency)

    # ── ML Service direct (if accessible) ────────────────────
    ml_url = base_url.replace(":8000", ":8001")
    status, body, latency = http_get(f"{ml_url}/health")
    if status == 200:
        check("ML Service /health", status, body, latency, required_keys=["status"])
        status, body, latency = http_get(f"{ml_url}/router/stats")
        check("ML Service /router/stats", status, body, latency)
    else:
        results.append(TestResult("ML Service /health",
                                  True, "Not directly accessible (behind gateway)", 0))

    # ── Latency SLOs ─────────────────────────────────────────
    for result in results:
        if result.passed and result.latency_ms > 5000:
            result.passed = False
            result.message += f" — LATENCY SLO BREACH (>{result.latency_ms:.0f}ms > 5000ms)"

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke tests for Financial Projection Platform")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="API gateway base URL")
    parser.add_argument("--retries", type=int, default=3,
                        help="Retry count for the full test suite (for cold-start)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Smoke testing: {base_url}")
    print("=" * 60)

    for attempt in range(1, args.retries + 1):
        results = run_tests(base_url)
        passed = sum(1 for r in results if r.passed)
        total = len(results)

        for r in results:
            status_icon = "✓" if r.passed else "✗"
            print(f"  {status_icon} {r.name}: {r.message}")

        print("=" * 60)
        print(f"  {passed}/{total} tests passed")

        if passed == total:
            print("  ALL SMOKE TESTS PASSED")
            return 0

        if attempt < args.retries:
            wait = 2 ** attempt
            print(f"  Attempt {attempt}/{args.retries} failed — retrying in {wait}s...")
            time.sleep(wait)

    print("  SMOKE TESTS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
