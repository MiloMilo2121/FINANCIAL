"""FeaturePipeline — orchestrates all 334 indicators into a flat feature vector.

Design principles:
  - transform(ohlcv, external, date) → (334,) for single-bar inference (XGBoost)
  - fit_transform(ohlcv, external_series, dates) → (N-lookback, 334) for training
  - NaN → 0.0 for missing external data (forward-fill then zero-fill)
  - Feature order is always INDICATOR_REGISTRY insertion order (deterministic)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any

import numpy as np

from .feature_registry import INDICATOR_REGISTRY, IndicatorMeta
from .ml_features import compute_all_ml_features
from .calendar_features import compute_calendar_features
from .factor_features import compute_factor_features
from .indicators import (
    compute_sma, compute_ema, compute_wma, compute_dema, compute_tema,
    compute_kama, compute_hull, compute_macd, compute_rsi, compute_stochastic,
    compute_stoch_rsi, compute_roc, compute_mom, compute_williams_r,
    compute_cci, compute_cmo, compute_dpo, compute_adx_di, compute_aroon,
    compute_psar, compute_atr, compute_natr, compute_bollinger, compute_keltner,
    compute_donchian, compute_hv, compute_obv, compute_cmf, compute_mfi,
    compute_ad, compute_vwap, compute_volume_features, compute_returns,
    compute_price_ratios, compute_52w_position, compute_rolling_correlations,
)

logger = logging.getLogger(__name__)

# Minimum bars needed to compute any technical indicator
_MIN_BARS = 62  # 60-bar window + 2 extra for lagged features


class FeaturePipeline:
    """Transforms raw OHLCV + external macro data into the 334-feature vector.

    Parameters
    ----------
    registry : dict[str, IndicatorMeta]
        The global INDICATOR_REGISTRY (or a subset for testing).
    enabled : list[str] | None
        If provided, only compute these named indicators. Useful for ablation
        studies or faster inference when not all externals are available.
    """

    def __init__(
        self,
        registry: dict[str, IndicatorMeta] = INDICATOR_REGISTRY,
        enabled: list[str] | None = None,
    ) -> None:
        self._registry = registry
        self._enabled: set[str] | None = set(enabled) if enabled else None
        self._names: list[str] = [
            name for name in registry
            if (self._enabled is None or name in self._enabled)
        ]

    # ── Public API ────────────────────────────────────────────────────────────

    def get_feature_names(self) -> list[str]:
        """Ordered feature name list (matches output vector columns)."""
        return list(self._names)

    def transform(
        self,
        ohlcv: np.ndarray,
        external: dict[str, float] | None = None,
        corr_series: dict[str, np.ndarray] | None = None,
        date: datetime | None = None,
        benchmark_spx: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute the feature vector for the LAST bar in ohlcv.

        Args:
            ohlcv: (N, 5) array [open, high, low, close, volume]. N >= 60.
            external: Latest values of external indicators (macro, alt, precious metal).
                      Keys must match indicator names in INDICATOR_REGISTRY.
                      Missing keys → 0.0.
            corr_series: Optional aligned price series for rolling correlation.
                         Keys: "DXY", "10Y_yield", "SPX", "oil", "copper", "silver", "BTC"
            date: Date of the last bar (for calendar/seasonality features).
                  Defaults to datetime.now() if None.
            benchmark_spx: Optional S&P500 price series aligned with ohlcv for
                           Kalman beta computation.
        Returns:
            (len(names),) float32 feature vector.
        """
        if external is None:
            external = {}
        if corr_series is None:
            corr_series = {}
        if date is None:
            date = datetime.now()

        feats = self._compute_technical(ohlcv)
        feats.update(self._compute_correlations(ohlcv[:, 3], corr_series))

        # Merge external (external values override computed fallbacks)
        for k, v in external.items():
            feats[k] = v

        # Compute derived precious metal ratios from available data
        feats.update(self._compute_pm_ratios(feats))

        # ML-derived features (Hurst, HMM, Fourier, Wavelet, entropy, etc.)
        feats.update(self._compute_ml_features(ohlcv[:, 3], date, benchmark_spx))

        # Calendar / seasonality features
        feats.update(compute_calendar_features(date))

        # Factor model features (carry, momentum, value, VRP)
        feats.update(compute_factor_features(feats, ohlcv[:, 3]))

        # Derived extra technical indicators
        feats.update(self._compute_extra_technical(ohlcv))

        return self._to_vector(feats)

    def fit_transform(
        self,
        ohlcv: np.ndarray,
        external_series: dict[str, Any] | None = None,
        lookback: int = 60,
        dates: list[datetime] | None = None,
        benchmark_spx: np.ndarray | None = None,
    ) -> np.ndarray:
        """Build (N-lookback, 334) feature matrix for training.

        Args:
            ohlcv: (N, 5) full historical OHLCV data.
            external_series: Dict of {indicator_name: list/array of length N}.
                             If a series is shorter than N, it is forward-filled.
            lookback: Minimum window for technical indicators.
            dates: List of N datetimes corresponding to each OHLCV bar.
                   If None, calendar features are computed from datetime.now().
            benchmark_spx: Optional S&P500 price series (length N) for Kalman beta.
        Returns:
            (N - lookback, 334) float32 feature matrix.
        """
        if external_series is None:
            external_series = {}

        N = len(ohlcv)
        n_features = len(self._names)
        X = np.zeros((N - lookback, n_features), dtype=np.float32)

        for i in range(lookback, N):
            window = ohlcv[: i + 1]
            ext = self._extract_external_at(external_series, i, N)
            bar_date = dates[i] if dates and i < len(dates) else datetime.now()
            bench_window = benchmark_spx[: i + 1] if benchmark_spx is not None else None

            feats = self._compute_technical(window)
            feats.update(ext)
            feats.update(self._compute_pm_ratios(feats))
            feats.update(self._compute_ml_features(window[:, 3], bar_date, bench_window))
            feats.update(compute_calendar_features(bar_date))
            feats.update(compute_factor_features(feats, window[:, 3]))
            feats.update(self._compute_extra_technical(window))
            X[i - lookback] = self._to_vector(feats)

        return X

    # ── Internal ──────────────────────────────────────────────────────────────

    def _compute_technical(self, ohlcv: np.ndarray) -> dict[str, float]:
        """Compute all 75 technical indicators from the OHLCV window."""
        close  = ohlcv[:, 3].astype(np.float64)
        high   = ohlcv[:, 1].astype(np.float64)
        low    = ohlcv[:, 2].astype(np.float64)
        volume = ohlcv[:, 4].astype(np.float64)

        feats: dict[str, float] = {}
        feats.update(compute_sma(close))
        feats.update(compute_ema(close))
        feats.update(compute_wma(close))
        feats.update(compute_dema(close))
        feats.update(compute_tema(close))
        feats.update(compute_kama(close))
        feats.update(compute_hull(close))
        feats.update(compute_macd(close))
        feats.update(compute_rsi(close))
        feats.update(compute_stochastic(high, low, close))
        feats.update(compute_stoch_rsi(close))
        feats.update(compute_roc(close))
        feats.update(compute_mom(close))
        feats.update(compute_williams_r(high, low, close))
        feats.update(compute_cci(high, low, close))
        feats.update(compute_cmo(close))
        feats.update(compute_dpo(close))
        feats.update(compute_adx_di(high, low, close))
        feats.update(compute_aroon(high, low))
        feats.update(compute_psar(high, low))
        feats.update(compute_atr(high, low, close))
        feats.update(compute_natr(high, low, close))
        feats.update(compute_bollinger(close))
        feats.update(compute_keltner(high, low, close))
        feats.update(compute_donchian(high, low))
        feats.update(compute_hv(close))
        feats.update(compute_obv(close, volume))
        feats.update(compute_cmf(high, low, close, volume))
        feats.update(compute_mfi(high, low, close, volume))
        feats.update(compute_ad(high, low, close, volume))
        feats.update(compute_vwap(high, low, close, volume))
        feats.update(compute_volume_features(close, volume))
        feats.update(compute_returns(close))
        feats.update(compute_price_ratios(close))
        feats.update(compute_52w_position(close, high, low))
        return feats

    def _compute_correlations(
        self,
        gold_close: np.ndarray,
        corr_series: dict[str, np.ndarray],
    ) -> dict[str, float]:
        """Compute rolling cross-asset correlations."""
        try:
            return compute_rolling_correlations(gold_close, corr_series)
        except Exception as exc:
            logger.debug("correlation_compute_failed: %s", exc)
            return {k: 0.0 for k in [
                "Gold_DXY_corr_30d", "Gold_DXY_corr_60d",
                "Gold_10Y_corr_30d", "Gold_10Y_corr_60d",
                "Gold_SPX_corr_30d", "Gold_SPX_corr_60d",
                "Gold_oil_corr_30d", "Gold_copper_corr_30d",
                "Gold_silver_corr_30d", "Gold_BTC_corr_30d",
            ]}

    def _compute_ml_features(
        self,
        close: np.ndarray,
        date: datetime,
        benchmark_spx: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Compute 16 ML-derived statistical features."""
        try:
            return compute_all_ml_features(close, date, benchmark_spx)
        except Exception as exc:
            logger.debug("ml_features_compute_failed: %s", exc)
            return {}

    def _compute_extra_technical(self, ohlcv: np.ndarray) -> dict[str, float]:
        """Compute 25 extra technical indicators not in the base set."""
        feats: dict[str, float] = {}
        close  = ohlcv[:, 3].astype(np.float64)
        high   = ohlcv[:, 1].astype(np.float64)
        low    = ohlcv[:, 2].astype(np.float64)
        open_  = ohlcv[:, 0].astype(np.float64)

        n = len(close)
        if n < 2:
            return feats

        # Extra ROC
        if n > 1:
            feats["ROC_1"] = float((close[-1] - close[-2]) / (close[-2] + 1e-12) * 100)
        if n > 3:
            feats["ROC_3"] = float((close[-1] - close[-4]) / (close[-4] + 1e-12) * 100)

        # RSI_2 (ultra-short-term oscillator)
        if n >= 3:
            gains = np.maximum(np.diff(close[-3:]), 0)
            losses = np.maximum(-np.diff(close[-3:]), 0)
            ag, al = gains.mean(), losses.mean()
            feats["RSI_2"] = float(100 - 100 / (1 + ag / (al + 1e-12)))

        # EMA_3
        if n >= 3:
            k = 2 / (3 + 1)
            ema = close[0]
            for c in close[1:]:
                ema = c * k + ema * (1 - k)
            feats["EMA_3"] = float(ema)

        # SMA_252
        feats["SMA_252"] = float(np.mean(close[-min(252, n):]))

        # Returns
        if n > 120:
            feats["Return_120d"] = float(np.log(close[-1] / (close[-121] + 1e-12)))
        if n > 252:
            feats["Return_252d"] = float(np.log(close[-1] / (close[-253] + 1e-12)))

        # Extended HV
        if n > 121:
            r = np.diff(np.log(np.maximum(close[-121:], 1e-12)))
            feats["HV_120"] = float(r.std(ddof=1) * np.sqrt(252) * 100)
        if n > 253:
            r = np.diff(np.log(np.maximum(close[-253:], 1e-12)))
            feats["HV_252"] = float(r.std(ddof=1) * np.sqrt(252) * 100)

        # Volatility regime
        hv20 = feats.get("HV_20", 0.0) if "HV_20" in feats else 0.0
        hv60 = feats.get("HV_60", 0.0) if "HV_60" in feats else 0.0
        if not hv20:
            if n > 21:
                r = np.diff(np.log(np.maximum(close[-21:], 1e-12)))
                hv20 = float(r.std(ddof=1) * np.sqrt(252) * 100)
        if not hv60:
            if n > 61:
                r = np.diff(np.log(np.maximum(close[-61:], 1e-12)))
                hv60 = float(r.std(ddof=1) * np.sqrt(252) * 100)
        feats["Vol_regime"] = float(hv20 / (hv60 + 1e-12)) if hv60 > 0 else 1.0

        # Return moments
        if n > 61:
            rets = np.diff(np.log(np.maximum(close[-61:], 1e-12)))
            mu, sigma = rets.mean(), rets.std(ddof=1)
            if sigma > 1e-12:
                feats["Skewness_60d"] = float(np.clip(np.mean(((rets - mu) / sigma) ** 3), -5, 5))
                feats["Kurtosis_60d"] = float(np.clip(np.mean(((rets - mu) / sigma) ** 4), 0, 20))

        # EMA200 and SMA100 price ratios
        if n >= 200:
            k = 2 / 201
            ema200 = close[0]
            for c in close[1:]:
                ema200 = c * k + ema200 * (1 - k)
            feats["Price_EMA200_ratio"] = float(close[-1] / (ema200 + 1e-12))

        if n >= 100:
            feats["Price_SMA100_ratio"] = float(close[-1] / (np.mean(close[-100:]) + 1e-12))

        # EMA20 / SMA50 cross signal
        if n >= 50:
            k20 = 2 / 21
            ema20 = close[0]
            for c in close[1:]:
                ema20 = c * k20 + ema20 * (1 - k20)
            sma50 = np.mean(close[-50:])
            feats["EMA20_SMA50_cross"] = float(ema20 / (sma50 + 1e-12))

        # MACD histogram slope
        if n >= 28:
            k12, k26 = 2/13, 2/27
            e12, e26 = close[0], close[0]
            for c in close:
                e12 = c * k12 + e12 * (1 - k12)
                e26 = c * k26 + e26 * (1 - k26)
            macd_now = e12 - e26
            # Previous bar
            e12p, e26p = close[0], close[0]
            for c in close[:-1]:
                e12p = c * k12 + e12p * (1 - k12)
                e26p = c * k26 + e26p * (1 - k26)
            macd_prev = e12p - e26p
            feats["MACD_hist_slope"] = float(macd_now - macd_prev)

        # RSI divergence (price up but RSI down, or vice versa)
        if n >= 15:
            r5 = np.diff(np.log(np.maximum(close[-6:], 1e-12)))
            gains5 = np.maximum(r5, 0).mean()
            losses5 = np.maximum(-r5, 0).mean()
            rsi5 = 100 - 100 / (1 + gains5 / (losses5 + 1e-12))
            r15 = np.diff(np.log(np.maximum(close[-16:], 1e-12)))
            gains15 = np.maximum(r15, 0).mean()
            losses15 = np.maximum(-r15, 0).mean()
            rsi15 = 100 - 100 / (1 + gains15 / (losses15 + 1e-12))
            price_dir = 1.0 if close[-1] > close[-6] else -1.0
            rsi_dir = 1.0 if rsi5 > rsi15 else -1.0
            feats["RSI_divergence"] = float(price_dir * -rsi_dir)  # 1=divergence

        # BB squeeze
        if n >= 20:
            ma = np.mean(close[-20:])
            sd = np.std(close[-20:], ddof=1)
            bb_width = 2 * sd / (ma + 1e-12)
            # Use 20th percentile of recent bb widths as threshold
            if n >= 40:
                widths = [2 * np.std(close[j-20:j], ddof=1) / (np.mean(close[j-20:j]) + 1e-12)
                          for j in range(20, min(n+1, 60))]
                threshold = float(np.percentile(widths, 20)) if widths else 0.02
                feats["BB_squeeze"] = 1.0 if bb_width < threshold else 0.0
            else:
                feats["BB_squeeze"] = 0.0

        # OBV slope
        volume = ohlcv[:, 4].astype(np.float64)
        if n >= 21:
            returns_20 = np.diff(close[-21:])
            signs = np.sign(returns_20)
            obv_series = np.cumsum(signs * volume[-20:])
            if n >= 3:
                feats["OBV_slope_20d"] = float(np.polyfit(np.arange(len(obv_series)), obv_series, 1)[0])

        # CMF z-score
        if n >= 60:
            def _cmf(c, h, l, v, p):
                mfm = ((c - l) - (h - c)) / (h - l + 1e-12)
                return np.sum(mfm * v) / (np.sum(v) + 1e-12)
            cmf_vals = [_cmf(close[j-20:j], high[j-20:j], low[j-20:j], volume[j-20:j], 20)
                        for j in range(20, n+1)]
            if cmf_vals:
                mu_cmf, sd_cmf = np.mean(cmf_vals), np.std(cmf_vals, ddof=1)
                feats["CMF_20_zscore"] = float((cmf_vals[-1] - mu_cmf) / (sd_cmf + 1e-12))

        # Open gap
        if n >= 2:
            feats["Price_open_gap"] = float((open_[-1] - close[-2]) / (close[-2] + 1e-12))

        # High-low spread
        feats["High_low_spread"] = float((high[-1] - low[-1]) / (close[-1] + 1e-12))

        # Candlestick patterns
        if n >= 14:
            atr_window = np.maximum(high[-15:] - low[-15:], 1e-12)
            atr = np.mean(atr_window)
            body = abs(close[-1] - open_[-1])
            total = high[-1] - low[-1] + 1e-12
            feats["Upper_shadow"] = float((high[-1] - max(close[-1], open_[-1])) / total)
            feats["Lower_shadow"] = float((min(close[-1], open_[-1]) - low[-1]) / total)
            feats["Body_ratio"]   = float(body / (atr + 1e-12))

        # Overnight gap average
        if n >= 20:
            gaps = np.abs(open_[-20:] - np.roll(close[-20:], 1))
            gaps[0] = 0
            feats["Overnight_gap_20d"] = float(np.mean(gaps[1:]) / (close[-1] + 1e-12))

        # Intraday range average
        if n >= 20:
            ranges = (high[-20:] - low[-20:]) / (close[-20:] + 1e-12)
            feats["Intraday_range_avg"] = float(np.mean(ranges))

        return feats

    def _compute_pm_ratios(self, feats: dict[str, float]) -> dict[str, float]:
        """Derive precious metal ratios from available spot prices."""
        gold = feats.get("LBMA_PM_fix") or feats.get("LBMA_AM_fix", 0.0)
        if not gold or math.isnan(gold):
            gold = 0.0

        def ratio(a: float, b: float) -> float:
            return float(a / b) if b and not math.isnan(b) and b > 0 else float("nan")

        derived: dict[str, float] = {}
        silver = feats.get("Silver_price", 0.0) or 0.0
        copper = feats.get("Copper_price", 0.0) or 0.0
        wti    = feats.get("WTI_crude", 0.0) or 0.0
        plat   = feats.get("Platinum_price", 0.0) or 0.0
        gdx    = feats.get("GDX_price", 0.0) or 0.0

        if gold:
            derived["Gold_silver_ratio"]   = ratio(gold, silver)
            derived["Gold_copper_ratio"]   = ratio(gold, copper)
            derived["Gold_oil_ratio"]      = ratio(gold, wti)
            derived["Gold_platinum_ratio"] = ratio(gold, plat)
            derived["GDX_gold_ratio"]      = ratio(gdx, gold)
        return derived

    def _extract_external_at(
        self,
        external_series: dict[str, Any],
        idx: int,
        total: int,
    ) -> dict[str, float]:
        """Extract external data point at index idx, with forward-fill."""
        ext: dict[str, float] = {}
        for key, series in external_series.items():
            if series is None:
                ext[key] = 0.0
                continue
            arr = np.asarray(series, dtype=np.float64)
            if len(arr) == 0:
                ext[key] = 0.0
            elif idx < len(arr):
                v = arr[idx]
                ext[key] = float(v) if not math.isnan(v) else 0.0
            else:
                # Forward-fill: use last known value
                valid = arr[~np.isnan(arr)]
                ext[key] = float(valid[-1]) if len(valid) > 0 else 0.0
        return ext

    def _to_vector(self, feats: dict[str, float]) -> np.ndarray:
        """Build ordered float32 vector from feature dict, NaN → 0.0."""
        vec = np.zeros(len(self._names), dtype=np.float32)
        for i, name in enumerate(self._names):
            v = feats.get(name, 0.0)
            if v is None or (isinstance(v, float) and math.isnan(v)):
                vec[i] = 0.0
            else:
                vec[i] = float(v)
        return vec
