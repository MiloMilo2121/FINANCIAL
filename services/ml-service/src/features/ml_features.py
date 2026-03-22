"""ML Feature Engineering — advanced statistical & ML-derived features.

Computes 16 indicators purely from OHLCV price history:
  Hurst_120d, HMM_bull/bear/volatile_prob, Fourier_* (6),
  Wavelet_DWT_scale2/8, Realized_skewness_30d, Realized_kurtosis_30d,
  Kalman_beta_SPX, Sample_entropy_30d.

All functions are pure-numpy when possible; optional libraries (hmmlearn,
PyWavelets) fall back gracefully to 0.0 if not installed.
"""

from __future__ import annotations

import math
import logging
from datetime import datetime
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ── Hurst Exponent ────────────────────────────────────────────────────────────

def _hurst_rs(ts: np.ndarray, min_n: int = 10) -> float:
    """Compute Hurst exponent via R/S analysis."""
    n = len(ts)
    if n < min_n:
        return float("nan")

    lags = np.unique(np.logspace(1, np.log10(n // 2), num=20).astype(int))
    rs_vals = []

    for lag in lags:
        if lag < 2:
            continue
        rs_chunk = []
        for start in range(0, n - lag + 1, lag):
            chunk = ts[start : start + lag]
            mean_adj = chunk - chunk.mean()
            cumdev = np.cumsum(mean_adj)
            R = cumdev.max() - cumdev.min()
            S = chunk.std(ddof=1)
            if S > 0:
                rs_chunk.append(R / S)
        if rs_chunk:
            rs_vals.append((lag, np.mean(rs_chunk)))

    if len(rs_vals) < 4:
        return float("nan")

    lags_log = np.log(np.array([x[0] for x in rs_vals]))
    rs_log   = np.log(np.array([x[1] for x in rs_vals]))
    try:
        h, _ = np.polyfit(lags_log, rs_log, 1)
        return float(np.clip(h, 0.0, 1.0))
    except Exception:
        return float("nan")


def compute_hurst(close: np.ndarray, window: int = 120) -> dict[str, float]:
    """Hurst exponent over `window` bars of log-returns."""
    if len(close) < window + 1:
        return {"Hurst_120d": 0.5}
    returns = np.diff(np.log(np.maximum(close[-window - 1:], 1e-12)))
    h = _hurst_rs(returns)
    return {"Hurst_120d": h if not math.isnan(h) else 0.5}


# ── Hidden Markov Model — 3 States ────────────────────────────────────────────

def compute_hmm_states(close: np.ndarray, window: int = 252) -> dict[str, float]:
    """3-state HMM probabilities: bull / bear / volatile.

    Falls back to equal probabilities if hmmlearn is not installed.
    """
    default = {"HMM_bull_prob": 1/3, "HMM_bear_prob": 1/3, "HMM_volatile_prob": 1/3}
    if len(close) < 62:
        return default

    returns = np.diff(np.log(np.maximum(close[-min(window, len(close)):], 1e-12)))

    try:
        from hmmlearn.hmm import GaussianHMM  # type: ignore
        obs = returns.reshape(-1, 1)
        model = GaussianHMM(n_components=3, covariance_type="full",
                            n_iter=100, random_state=42)
        model.fit(obs)
        # Classify states by mean return: highest=bull, lowest=bear, mid=volatile
        means = model.means_.flatten()
        states = np.argsort(means)  # ascending: bear=0, volatile=1, bull=2
        probs = model.predict_proba(obs[-1:]).flatten()
        bull_p     = float(probs[states[2]])
        bear_p     = float(probs[states[0]])
        volatile_p = float(probs[states[1]])
        return {"HMM_bull_prob": bull_p, "HMM_bear_prob": bear_p,
                "HMM_volatile_prob": volatile_p}
    except Exception as e:
        logger.debug("hmm_compute_failed: %s", e)
        # Simple regime based on rolling z-score of returns
        recent = returns[-20:]
        mu, sigma = returns.mean(), returns.std()
        if sigma < 1e-10:
            return default
        z = (recent.mean() - mu) / sigma
        if z > 0.5:
            return {"HMM_bull_prob": 0.6, "HMM_bear_prob": 0.2, "HMM_volatile_prob": 0.2}
        elif z < -0.5:
            return {"HMM_bull_prob": 0.2, "HMM_bear_prob": 0.6, "HMM_volatile_prob": 0.2}
        else:
            return {"HMM_bull_prob": 0.2, "HMM_bear_prob": 0.2, "HMM_volatile_prob": 0.6}


# ── Fourier Seasonality Terms ─────────────────────────────────────────────────

def compute_fourier(date: datetime) -> dict[str, float]:
    """Fourier sin/cos terms for annual, semi-annual, quarterly cycles."""
    day_of_year = date.timetuple().tm_yday
    year_days = 366 if (date.year % 4 == 0 and
                        (date.year % 100 != 0 or date.year % 400 == 0)) else 365
    t = day_of_year / year_days  # 0..1

    return {
        "Fourier_annual_sin":      float(math.sin(2 * math.pi * t)),
        "Fourier_annual_cos":      float(math.cos(2 * math.pi * t)),
        "Fourier_semiannual_sin":  float(math.sin(4 * math.pi * t)),
        "Fourier_semiannual_cos":  float(math.cos(4 * math.pi * t)),
        "Fourier_quarterly_sin":   float(math.sin(8 * math.pi * t)),
        "Fourier_quarterly_cos":   float(math.cos(8 * math.pi * t)),
    }


# ── Wavelet DWT ───────────────────────────────────────────────────────────────

def compute_wavelet_features(close: np.ndarray) -> dict[str, float]:
    """Discrete Wavelet Transform detail coefficients at scale 2 and 8.

    Falls back to 0.0 if PyWavelets is not installed.
    """
    default = {"Wavelet_DWT_scale2": 0.0, "Wavelet_DWT_scale8": 0.0}
    if len(close) < 16:
        return default

    try:
        import pywt  # type: ignore
        data = np.log(np.maximum(close, 1e-12))
        # 4-level DWT; detail coefficients at level 2 (scale ~4d) and 4 (scale ~16d)
        coeffs = pywt.wavedec(data, "db4", level=4)
        # coeffs[0]=approx, coeffs[1]=detail lv1, ..., coeffs[4]=detail lv4
        d2 = coeffs[2][-1] if len(coeffs) > 2 and len(coeffs[2]) else 0.0
        d4 = coeffs[4][-1] if len(coeffs) > 4 and len(coeffs[4]) else 0.0
        return {"Wavelet_DWT_scale2": float(d2), "Wavelet_DWT_scale8": float(d4)}
    except Exception as e:
        logger.debug("wavelet_compute_failed: %s", e)
        # Fallback: simple band-pass approximation using moving averages
        if len(close) < 9:
            return default
        short_ma = np.mean(close[-4:])
        long_ma  = np.mean(close[-8:])
        mid_ma   = np.mean(close[-16:]) if len(close) >= 16 else np.mean(close)
        d2 = float((short_ma - long_ma) / (long_ma + 1e-12))
        d4 = float((long_ma - mid_ma) / (mid_ma + 1e-12))
        return {"Wavelet_DWT_scale2": d2, "Wavelet_DWT_scale8": d4}


# ── Realized Higher Moments ───────────────────────────────────────────────────

def compute_realized_moments(close: np.ndarray, window: int = 30) -> dict[str, float]:
    """Realized skewness and kurtosis of returns over `window` bars."""
    default = {"Realized_skewness_30d": 0.0, "Realized_kurtosis_30d": 3.0}
    if len(close) < window + 1:
        return default

    returns = np.diff(np.log(np.maximum(close[-(window + 1):], 1e-12)))
    n = len(returns)
    if n < 4:
        return default

    mu = returns.mean()
    sigma = returns.std(ddof=1)
    if sigma < 1e-12:
        return default

    skew = float(np.mean(((returns - mu) / sigma) ** 3))
    kurt = float(np.mean(((returns - mu) / sigma) ** 4))  # excess: subtract 3 below
    return {
        "Realized_skewness_30d": np.clip(skew, -5.0, 5.0).item(),
        "Realized_kurtosis_30d": np.clip(kurt, 0.0, 20.0).item(),
    }


# ── Kalman Filter Beta ────────────────────────────────────────────────────────

def compute_kalman_beta(
    close: np.ndarray,
    benchmark: np.ndarray | None,
) -> dict[str, float]:
    """Time-varying beta to SPX via scalar Kalman filter.

    If benchmark is None or misaligned, returns 0.0.
    """
    default = {"Kalman_beta_SPX": 0.0}
    if benchmark is None or len(benchmark) < 2:
        return default
    n = min(len(close), len(benchmark))
    if n < 10:
        return default

    gold_ret = np.diff(np.log(np.maximum(close[-n:], 1e-12)))
    spx_ret  = np.diff(np.log(np.maximum(benchmark[-n:], 1e-12)))
    n -= 1

    # Scalar Kalman: state = beta, R=measurement noise, Q=process noise
    beta = 0.0
    P = 1.0
    Q = 1e-5   # process noise
    R = 0.01   # measurement noise

    for i in range(n):
        if abs(spx_ret[i]) < 1e-12:
            continue
        # Predict
        P = P + Q
        # Update
        K = P * spx_ret[i] / (spx_ret[i] ** 2 * P + R)
        beta = beta + K * (gold_ret[i] - beta * spx_ret[i])
        P = (1 - K * spx_ret[i]) * P

    return {"Kalman_beta_SPX": float(np.clip(beta, -3.0, 3.0))}


# ── Sample Entropy ────────────────────────────────────────────────────────────

def compute_sample_entropy(close: np.ndarray, window: int = 30, m: int = 2,
                           r_factor: float = 0.2) -> dict[str, float]:
    """Sample entropy of log-returns over `window` bars.

    Lower values → more predictable; higher → more random/complex.
    """
    default = {"Sample_entropy_30d": 0.0}
    if len(close) < window + 1:
        return default

    returns = np.diff(np.log(np.maximum(close[-(window + 1):], 1e-12)))
    n = len(returns)
    if n < 2 * m + 2:
        return default

    r = r_factor * float(np.std(returns, ddof=1))
    if r < 1e-12:
        return default

    def _count_matches(ts: np.ndarray, m_: int, threshold: float) -> int:
        count = 0
        for i in range(len(ts) - m_):
            for j in range(i + 1, len(ts) - m_):
                if np.max(np.abs(ts[i:i+m_] - ts[j:j+m_])) < threshold:
                    count += 1
        return count

    try:
        A = _count_matches(returns, m + 1, r)
        B = _count_matches(returns, m, r)
        if B == 0:
            return default
        se = float(-math.log(A / B)) if A > 0 else 2.0
        return {"Sample_entropy_30d": float(np.clip(se, 0.0, 5.0))}
    except Exception:
        return default


# ── Public batch function ─────────────────────────────────────────────────────

def compute_all_ml_features(
    close: np.ndarray,
    date: datetime,
    benchmark_spx: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute all 16 ML-derived features in one call."""
    feats: dict[str, float] = {}
    feats.update(compute_hurst(close))
    feats.update(compute_hmm_states(close))
    feats.update(compute_fourier(date))
    feats.update(compute_wavelet_features(close))
    feats.update(compute_realized_moments(close))
    feats.update(compute_kalman_beta(close, benchmark_spx))
    feats.update(compute_sample_entropy(close))
    return feats
