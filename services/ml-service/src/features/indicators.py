"""Technical Indicator Library — pure NumPy, zero Pandas.

All public functions accept raw NumPy arrays (close, high, low, volume)
and return a dict[str, float] with values for the LAST bar in the series.
NaN is returned whenever the window is too short or computation fails.

Usage:
    close = ohlcv[:, 3].astype(np.float64)
    high  = ohlcv[:, 1].astype(np.float64)
    low   = ohlcv[:, 2].astype(np.float64)
    vol   = ohlcv[:, 4].astype(np.float64)

    features: dict[str, float] = {}
    features.update(compute_sma(close))
    features.update(compute_rsi(close))
    # ...
"""

from __future__ import annotations

import math

import numpy as np

_NAN = float("nan")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ema_series(x: np.ndarray, n: int) -> np.ndarray:
    """Full EMA series (length = len(x))."""
    alpha = 2.0 / (n + 1)
    out = np.empty_like(x, dtype=np.float64)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1.0 - alpha) * out[i - 1]
    return out


def _wma_series(x: np.ndarray, n: int) -> np.ndarray:
    """Weighted Moving Average series."""
    weights = np.arange(1, n + 1, dtype=np.float64)
    w_sum = weights.sum()
    out = np.full(len(x), _NAN)
    for i in range(n - 1, len(x)):
        out[i] = np.dot(weights, x[i - n + 1: i + 1]) / w_sum
    return out


def _sma_series(x: np.ndarray, n: int) -> np.ndarray:
    """Simple Moving Average series."""
    out = np.full(len(x), _NAN)
    cs = np.cumsum(x)
    out[n - 1:] = (cs[n - 1:] - np.concatenate([[0], cs[:-n]])) / n
    return out


def _wilder_smooth(x: np.ndarray, n: int) -> np.ndarray:
    """Wilder's Smoothing (RMA). Returns series of same length."""
    out = np.full(len(x), _NAN)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def _safe_last(arr: np.ndarray) -> float:
    v = arr[-1]
    return _NAN if (isinstance(v, float) and math.isnan(v)) else float(v)


# ── Moving Averages ───────────────────────────────────────────────────────────

def compute_sma(close: np.ndarray) -> dict[str, float]:
    """SMA for periods [5, 10, 20, 50, 100, 200]."""
    out: dict[str, float] = {}
    for n in [5, 10, 20, 50, 100, 200]:
        if len(close) >= n:
            out[f"SMA_{n}"] = float(close[-n:].mean())
        else:
            out[f"SMA_{n}"] = _NAN
    return out


def compute_ema(close: np.ndarray) -> dict[str, float]:
    """EMA for periods [5, 10, 20, 50, 100, 200]."""
    out: dict[str, float] = {}
    for n in [5, 10, 20, 50, 100, 200]:
        if len(close) >= n:
            out[f"EMA_{n}"] = _safe_last(_ema_series(close, n))
        else:
            out[f"EMA_{n}"] = _NAN
    return out


def compute_wma(close: np.ndarray, n: int = 20) -> dict[str, float]:
    """Weighted Moving Average."""
    if len(close) < n:
        return {"WMA_20": _NAN}
    return {"WMA_20": _safe_last(_wma_series(close, n))}


def compute_dema(close: np.ndarray, n: int = 20) -> dict[str, float]:
    """Double Exponential Moving Average: DEMA = 2*EMA1 - EMA(EMA1)."""
    if len(close) < n * 2:
        return {"DEMA_20": _NAN}
    ema1 = _ema_series(close, n)
    ema2 = _ema_series(ema1, n)
    return {"DEMA_20": float(2.0 * ema1[-1] - ema2[-1])}


def compute_tema(close: np.ndarray, n: int = 20) -> dict[str, float]:
    """Triple Exponential Moving Average: TEMA = 3*EMA1 - 3*EMA2 + EMA3."""
    if len(close) < n * 3:
        return {"TEMA_20": _NAN}
    ema1 = _ema_series(close, n)
    ema2 = _ema_series(ema1, n)
    ema3 = _ema_series(ema2, n)
    return {"TEMA_20": float(3.0 * ema1[-1] - 3.0 * ema2[-1] + ema3[-1])}


def compute_kama(close: np.ndarray, n: int = 20, fast: int = 2, slow: int = 30) -> dict[str, float]:
    """Kaufman Adaptive Moving Average."""
    if len(close) < n + 1:
        return {"KAMA_20": _NAN}
    fast_sc = 2.0 / (fast + 1)
    slow_sc = 2.0 / (slow + 1)
    kama = np.empty_like(close, dtype=np.float64)
    kama[:n] = close[:n]
    for i in range(n, len(close)):
        direction = abs(close[i] - close[i - n])
        volatility = np.sum(np.abs(np.diff(close[i - n: i + 1])))
        er = direction / (volatility + 1e-12)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (close[i] - kama[i - 1])
    return {"KAMA_20": float(kama[-1])}


def compute_hull(close: np.ndarray, n: int = 20) -> dict[str, float]:
    """Hull Moving Average: HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))."""
    half_n = max(1, n // 2)
    sqrt_n = max(1, int(math.sqrt(n)))
    if len(close) < n + sqrt_n:
        return {"HullMA_20": _NAN}
    wma_half = _wma_series(close, half_n)
    wma_full = _wma_series(close, n)
    diff = 2.0 * wma_half - wma_full
    hull_series = _wma_series(diff, sqrt_n)
    return {"HullMA_20": _safe_last(hull_series)}


# ── Momentum ──────────────────────────────────────────────────────────────────

def compute_macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float]:
    """MACD line, Signal, and Histogram."""
    if len(close) < slow + signal:
        return {"MACD_line": _NAN, "MACD_signal": _NAN, "MACD_hist": _NAN}
    ema_fast = _ema_series(close, fast)
    ema_slow = _ema_series(close, slow)
    macd_line = ema_fast - ema_slow
    sig = _ema_series(macd_line, signal)
    return {
        "MACD_line":   float(macd_line[-1]),
        "MACD_signal": float(sig[-1]),
        "MACD_hist":   float(macd_line[-1] - sig[-1]),
    }


def compute_rsi(close: np.ndarray) -> dict[str, float]:
    """RSI for periods [7, 14, 21] using Wilder's smoothing."""
    out: dict[str, float] = {}
    for n in [7, 14, 21]:
        if len(close) < n + 1:
            out[f"RSI_{n}"] = _NAN
            continue
        deltas = np.diff(close.astype(np.float64))
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = _wilder_smooth(gains, n)
        avg_loss = _wilder_smooth(losses, n)
        rs = avg_gain[-1] / (avg_loss[-1] + 1e-12)
        out[f"RSI_{n}"] = float(100.0 - 100.0 / (1.0 + rs))
    return out


def compute_stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       k: int = 14, d: int = 3) -> dict[str, float]:
    """Stochastic Oscillator %K and %D."""
    if len(close) < k + d - 1:
        return {"Stoch_K": _NAN, "Stoch_D": _NAN}
    k_vals = np.full(len(close), _NAN)
    for i in range(k - 1, len(close)):
        h_max = high[i - k + 1: i + 1].max()
        l_min = low[i - k + 1: i + 1].min()
        rng = h_max - l_min
        k_vals[i] = 100.0 * (close[i] - l_min) / (rng + 1e-12)
    # %D = SMA(3) of %K
    valid = k_vals[~np.isnan(k_vals)]
    d_val = float(valid[-d:].mean()) if len(valid) >= d else _NAN
    return {"Stoch_K": float(k_vals[-1]), "Stoch_D": d_val}


def compute_stoch_rsi(close: np.ndarray, n: int = 14) -> dict[str, float]:
    """Stochastic RSI."""
    if len(close) < n * 2 + 1:
        return {"StochRSI_14": _NAN}
    # Compute RSI series
    deltas = np.diff(close.astype(np.float64))
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_g = _wilder_smooth(gains, n)
    avg_l = _wilder_smooth(losses, n)
    rs = avg_g / (avg_l + 1e-12)
    rsi_series = 100.0 - 100.0 / (1.0 + rs)
    # Stochastic of RSI
    rsi_valid = rsi_series[~np.isnan(rsi_series)]
    if len(rsi_valid) < n:
        return {"StochRSI_14": _NAN}
    rsi_window = rsi_valid[-n:]
    rsi_min, rsi_max = rsi_window.min(), rsi_window.max()
    val = (rsi_valid[-1] - rsi_min) / (rsi_max - rsi_min + 1e-12)
    return {"StochRSI_14": float(val)}


def compute_roc(close: np.ndarray) -> dict[str, float]:
    """Rate of Change for windows [5, 10, 20, 60]."""
    out: dict[str, float] = {}
    for n in [5, 10, 20, 60]:
        if len(close) > n:
            out[f"ROC_{n}"] = float((close[-1] / close[-n - 1] - 1.0) * 100.0)
        else:
            out[f"ROC_{n}"] = _NAN
    return out


def compute_mom(close: np.ndarray, n: int = 10) -> dict[str, float]:
    """Momentum (simple price difference)."""
    if len(close) > n:
        return {"MOM_10": float(close[-1] - close[-n - 1])}
    return {"MOM_10": _NAN}


def compute_williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       n: int = 14) -> dict[str, float]:
    """Williams %R."""
    if len(close) < n:
        return {"Williams_R": _NAN}
    h_max = high[-n:].max()
    l_min = low[-n:].min()
    return {"Williams_R": float(-100.0 * (h_max - close[-1]) / (h_max - l_min + 1e-12))}


def compute_cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> dict[str, float]:
    """Commodity Channel Index."""
    if len(close) < n:
        return {"CCI_14": _NAN}
    tp = (high[-n:] + low[-n:] + close[-n:]) / 3.0
    mean_tp = tp.mean()
    mean_dev = np.mean(np.abs(tp - mean_tp))
    return {"CCI_14": float((tp[-1] - mean_tp) / (0.015 * mean_dev + 1e-12))}


def compute_cmo(close: np.ndarray, n: int = 14) -> dict[str, float]:
    """Chande Momentum Oscillator."""
    if len(close) < n + 1:
        return {"CMO_14": _NAN}
    deltas = np.diff(close[-n - 1:].astype(np.float64))
    gains = np.where(deltas > 0, deltas, 0.0).sum()
    losses = np.where(deltas < 0, -deltas, 0.0).sum()
    denom = gains + losses
    return {"CMO_14": float(100.0 * (gains - losses) / (denom + 1e-12))}


def compute_dpo(close: np.ndarray, n: int = 20) -> dict[str, float]:
    """Detrended Price Oscillator."""
    offset = n // 2 + 1
    if len(close) < n + offset:
        return {"DPO_20": _NAN}
    sma = float(close[-(n + offset): -offset].mean())
    return {"DPO_20": float(close[-offset] - sma)}


def compute_adx_di(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   n: int = 14) -> dict[str, float]:
    """ADX, +DI, -DI using Wilder's smoothing."""
    if len(close) < n * 2:
        return {"ADX_14": _NAN, "DI_plus": _NAN, "DI_minus": _NAN}
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    up_move   = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move,   0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    atr_s    = _wilder_smooth(tr, n)
    plus_s   = _wilder_smooth(plus_dm, n)
    minus_s  = _wilder_smooth(minus_dm, n)

    di_plus  = 100.0 * plus_s[-1]  / (atr_s[-1] + 1e-12)
    di_minus = 100.0 * minus_s[-1] / (atr_s[-1] + 1e-12)
    dx = 100.0 * abs(di_plus - di_minus) / (di_plus + di_minus + 1e-12)
    dx_series = np.where(atr_s > 0, 100.0 * np.abs(plus_s - minus_s) / (plus_s + minus_s + 1e-12), 0.0)
    adx = _wilder_smooth(dx_series, n)[-1]
    return {"ADX_14": float(adx), "DI_plus": float(di_plus), "DI_minus": float(di_minus)}


def compute_aroon(high: np.ndarray, low: np.ndarray, n: int = 25) -> dict[str, float]:
    """Aroon Up, Down, and Oscillator."""
    if len(high) < n + 1:
        return {"AROON_up": _NAN, "AROON_down": _NAN, "AROON_osc": _NAN}
    window_h = high[-(n + 1):]
    window_l = low[-(n + 1):]
    periods_since_high = n - int(np.argmax(window_h))
    periods_since_low  = n - int(np.argmin(window_l))
    aroon_up   = 100.0 * (n - periods_since_high) / n
    aroon_down = 100.0 * (n - periods_since_low)  / n
    return {"AROON_up": float(aroon_up), "AROON_down": float(aroon_down),
            "AROON_osc": float(aroon_up - aroon_down)}


def compute_psar(high: np.ndarray, low: np.ndarray,
                 step: float = 0.02, max_step: float = 0.2) -> dict[str, float]:
    """Parabolic SAR (last value)."""
    if len(high) < 3:
        return {"PSAR": _NAN}
    bull  = True
    iaf   = step
    sar   = float(low[0])
    hp    = float(high[0])
    lp    = float(low[0])

    for i in range(1, len(high)):
        if bull:
            sar = sar + iaf * (hp - sar)
            sar = min(sar, float(low[i - 1]), float(low[max(0, i - 2)]))
            if float(low[i]) < sar:
                bull = False
                sar  = hp
                lp   = float(low[i])
                iaf  = step
            else:
                if float(high[i]) > hp:
                    hp  = float(high[i])
                    iaf = min(iaf + step, max_step)
        else:
            sar = sar + iaf * (lp - sar)
            sar = max(sar, float(high[i - 1]), float(high[max(0, i - 2)]))
            if float(high[i]) > sar:
                bull = True
                sar  = lp
                hp   = float(high[i])
                iaf  = step
            else:
                if float(low[i]) < lp:
                    lp  = float(low[i])
                    iaf = min(iaf + step, max_step)
    return {"PSAR": float(sar)}


# ── Volatility ────────────────────────────────────────────────────────────────

def _atr_series(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """Full ATR series using Wilder's smoothing."""
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1]))
    )
    return _wilder_smooth(tr, n)


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, float]:
    """ATR for periods [7, 14, 21]."""
    out: dict[str, float] = {}
    for n in [7, 14, 21]:
        if len(close) > n:
            out[f"ATR_{n}"] = _safe_last(_atr_series(high, low, close, n))
        else:
            out[f"ATR_{n}"] = _NAN
    return out


def compute_natr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> dict[str, float]:
    """Normalized ATR = ATR / close * 100."""
    if len(close) <= n:
        return {"NATR_14": _NAN}
    atr = _safe_last(_atr_series(high, low, close, n))
    return {"NATR_14": float(atr / (close[-1] + 1e-12) * 100.0)}


def compute_bollinger(close: np.ndarray, n: int = 20, num_std: float = 2.0) -> dict[str, float]:
    """Bollinger Bands: upper, lower, width, %B."""
    if len(close) < n:
        return {"BB_upper": _NAN, "BB_lower": _NAN, "BB_width": _NAN, "BB_pct": _NAN}
    window = close[-n:].astype(np.float64)
    mid   = window.mean()
    std   = window.std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / (mid + 1e-12)
    pct_b = (close[-1] - lower) / (upper - lower + 1e-12)
    return {"BB_upper": float(upper), "BB_lower": float(lower),
            "BB_width": float(width), "BB_pct": float(pct_b)}


def compute_keltner(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                    n: int = 20, atr_mult: float = 2.0) -> dict[str, float]:
    """Keltner Channels."""
    if len(close) <= n:
        return {"KC_upper": _NAN, "KC_lower": _NAN}
    mid   = float(_ema_series(close, n)[-1])
    atr   = _safe_last(_atr_series(high, low, close, n))
    return {"KC_upper": float(mid + atr_mult * atr), "KC_lower": float(mid - atr_mult * atr)}


def compute_donchian(high: np.ndarray, low: np.ndarray, n: int = 20) -> dict[str, float]:
    """Donchian Channel High/Low."""
    if len(high) < n:
        return {"Donchian_high_20": _NAN, "Donchian_low_20": _NAN}
    return {
        "Donchian_high_20": float(high[-n:].max()),
        "Donchian_low_20":  float(low[-n:].min()),
    }


def compute_hv(close: np.ndarray) -> dict[str, float]:
    """Historical Volatility (annualized) for windows [10, 20, 60]."""
    out: dict[str, float] = {}
    log_returns = np.log(close[1:] / close[:-1])
    for n in [10, 20, 60]:
        if len(log_returns) >= n:
            out[f"HV_{n}"] = float(log_returns[-n:].std(ddof=1) * math.sqrt(252))
        else:
            out[f"HV_{n}"] = _NAN
    return out


# ── Volume ────────────────────────────────────────────────────────────────────

def compute_obv(close: np.ndarray, volume: np.ndarray) -> dict[str, float]:
    """On Balance Volume (last value, normalized by initial volume)."""
    if len(close) < 2:
        return {"OBV": _NAN}
    signs = np.sign(np.diff(close.astype(np.float64)))
    obv_last = float(np.sum(signs * volume[1:]))
    return {"OBV": obv_last}


def compute_cmf(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                volume: np.ndarray, n: int = 20) -> dict[str, float]:
    """Chaikin Money Flow."""
    if len(close) < n:
        return {"CMF_20": _NAN}
    h, l, c, v = high[-n:], low[-n:], close[-n:], volume[-n:]
    clv = np.where(h != l, (c - l - h + c) / (h - l + 1e-12), 0.0)
    return {"CMF_20": float(np.sum(clv * v) / (v.sum() + 1e-12))}


def compute_mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                volume: np.ndarray, n: int = 14) -> dict[str, float]:
    """Money Flow Index."""
    if len(close) < n + 1:
        return {"MFI_14": _NAN}
    tp = (high + low + close) / 3.0
    raw_mf = tp * volume
    pos_mf = np.where(tp[1:] > tp[:-1], raw_mf[1:], 0.0)[-n:]
    neg_mf = np.where(tp[1:] < tp[:-1], raw_mf[1:], 0.0)[-n:]
    mfr = pos_mf.sum() / (neg_mf.sum() + 1e-12)
    return {"MFI_14": float(100.0 - 100.0 / (1.0 + mfr))}


def compute_ad(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               volume: np.ndarray) -> dict[str, float]:
    """Accumulation/Distribution Line (last value, normalized)."""
    if len(close) < 2:
        return {"AD_line": _NAN}
    h, l, c, v = high.astype(np.float64), low.astype(np.float64), \
                 close.astype(np.float64), volume.astype(np.float64)
    clv = np.where(h != l, (c - l - h + c) / (h - l + 1e-12), 0.0)
    ad  = float(np.cumsum(clv * v)[-1])
    return {"AD_line": ad}


def compute_vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                 volume: np.ndarray, n: int = 20) -> dict[str, float]:
    """Volume Weighted Average Price over n bars."""
    if len(close) < n:
        return {"VWAP_20": _NAN}
    tp = (high[-n:] + low[-n:] + close[-n:]) / 3.0
    v  = volume[-n:].astype(np.float64)
    return {"VWAP_20": float(np.sum(tp * v) / (v.sum() + 1e-12))}


def compute_volume_features(close: np.ndarray, volume: np.ndarray, n: int = 20) -> dict[str, float]:
    """Volume SMA, ratio, and z-score."""
    if len(volume) < n:
        return {"Volume_SMA_20": _NAN, "Volume_ratio": _NAN, "Volume_zscore": _NAN}
    v_window = volume[-n:].astype(np.float64)
    v_sma    = v_window.mean()
    v_std    = v_window.std(ddof=0)
    v_cur    = float(volume[-1])
    return {
        "Volume_SMA_20": float(v_sma),
        "Volume_ratio":  float(v_cur / (v_sma + 1e-12)),
        "Volume_zscore": float((v_cur - v_sma) / (v_std + 1e-12)),
    }


# ── Price Position ─────────────────────────────────────────────────────────────

def compute_returns(close: np.ndarray) -> dict[str, float]:
    """Log returns for windows [1, 5, 10, 20, 60]."""
    out: dict[str, float] = {}
    for n in [1, 5, 10, 20, 60]:
        key = f"Return_{n}d"
        if len(close) > n:
            out[key] = float(math.log(close[-1] / (close[-n - 1] + 1e-12)))
        else:
            out[key] = _NAN
    return out


def compute_price_ratios(close: np.ndarray) -> dict[str, float]:
    """Close / SMA20, SMA50, SMA200 ratios."""
    out: dict[str, float] = {}
    sma_vals = compute_sma(close)
    cur = float(close[-1])
    for n in [20, 50, 200]:
        sma = sma_vals.get(f"SMA_{n}", _NAN)
        if sma and not math.isnan(sma):
            out[f"Price_SMA{n}_ratio"] = float(cur / (sma + 1e-12))
        else:
            out[f"Price_SMA{n}_ratio"] = _NAN
    return out


def compute_52w_position(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> dict[str, float]:
    """Position within 52-week (252-bar) high/low range."""
    n = min(252, len(close))
    if n < 5:
        return {"High_52w_pct": _NAN, "Low_52w_pct": _NAN}
    h_max = high[-n:].max()
    l_min = low[-n:].min()
    rng   = h_max - l_min + 1e-12
    cur   = float(close[-1])
    return {
        "High_52w_pct": float((cur - l_min) / rng),
        "Low_52w_pct":  float((h_max - cur) / rng),
    }


# ── Cross-Asset Correlations ──────────────────────────────────────────────────

def compute_rolling_correlations(
    gold_close: np.ndarray,
    external_series: dict[str, np.ndarray],
) -> dict[str, float]:
    """Rolling correlations: gold vs DXY, 10Y yield, SPX, oil, copper, silver, BTC.

    Args:
        gold_close: Gold closing prices (length N).
        external_series: Mapping of corr key → aligned price series (same length).
            Keys: "DXY", "10Y_yield", "SPX", "oil", "copper", "silver", "BTC"
    """
    out: dict[str, float] = {}
    gold_lr = np.log(gold_close[1:] / gold_close[:-1])

    corr_map = {
        "Gold_DXY_corr_30d":    ("DXY",       30),
        "Gold_DXY_corr_60d":    ("DXY",       60),
        "Gold_10Y_corr_30d":    ("10Y_yield",  30),
        "Gold_10Y_corr_60d":    ("10Y_yield",  60),
        "Gold_SPX_corr_30d":    ("SPX",        30),
        "Gold_SPX_corr_60d":    ("SPX",        60),
        "Gold_oil_corr_30d":    ("oil",        30),
        "Gold_copper_corr_30d": ("copper",     30),
        "Gold_silver_corr_30d": ("silver",     30),
        "Gold_BTC_corr_30d":    ("BTC",        30),
    }

    for feat_name, (series_key, window) in corr_map.items():
        other = external_series.get(series_key)
        if other is None or len(other) < window + 1:
            out[feat_name] = _NAN
            continue
        other = np.asarray(other, dtype=np.float64)
        other_lr = np.log(other[1:] / (other[:-1] + 1e-12))
        n_common = min(len(gold_lr), len(other_lr), window)
        if n_common < 5:
            out[feat_name] = _NAN
            continue
        g = gold_lr[-n_common:]
        o = other_lr[-n_common:]
        # Pearson correlation
        g_dev = g - g.mean()
        o_dev = o - o.mean()
        denom = math.sqrt((g_dev**2).sum() * (o_dev**2).sum()) + 1e-12
        out[feat_name] = float(np.dot(g_dev, o_dev) / denom)
    return out
