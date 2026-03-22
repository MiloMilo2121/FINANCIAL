"""FeaturePipeline — orchestrates all 175 indicators into a flat feature vector.

Design principles:
  - transform(ohlcv, external) → (175,) for single-bar inference (XGBoost)
  - fit_transform(ohlcv, external_series) → (N-lookback, 175) for training
  - NaN → 0.0 for missing external data (forward-fill then zero-fill)
  - Feature order is always INDICATOR_REGISTRY insertion order (deterministic)
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from .feature_registry import INDICATOR_REGISTRY, IndicatorMeta
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
    """Transforms raw OHLCV + external macro data into the 175-feature vector.

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
    ) -> np.ndarray:
        """Compute the feature vector for the LAST bar in ohlcv.

        Args:
            ohlcv: (N, 5) array [open, high, low, close, volume]. N >= 60.
            external: Latest values of external indicators (macro, alt, precious metal).
                      Keys must match indicator names in INDICATOR_REGISTRY.
                      Missing keys → 0.0.
            corr_series: Optional aligned price series for rolling correlation.
                         Keys: "DXY", "10Y_yield", "SPX", "oil", "copper", "silver", "BTC"
        Returns:
            (len(names),) float32 feature vector.
        """
        if external is None:
            external = {}
        if corr_series is None:
            corr_series = {}

        feats = self._compute_technical(ohlcv)
        feats.update(self._compute_correlations(ohlcv[:, 3], corr_series))

        # Merge external (external values override computed fallbacks)
        for k, v in external.items():
            feats[k] = v

        # Compute derived precious metal ratios from available data
        feats.update(self._compute_pm_ratios(feats))

        return self._to_vector(feats)

    def fit_transform(
        self,
        ohlcv: np.ndarray,
        external_series: dict[str, Any] | None = None,
        lookback: int = 60,
    ) -> np.ndarray:
        """Build (N-lookback, 175) feature matrix for training.

        Args:
            ohlcv: (N, 5) full historical OHLCV data.
            external_series: Dict of {indicator_name: list/array of length N}.
                             If a series is shorter than N, it is forward-filled.
            lookback: Minimum window for technical indicators.
        Returns:
            (N - lookback, 175) float32 feature matrix.
        """
        if external_series is None:
            external_series = {}

        N = len(ohlcv)
        n_features = len(self._names)
        X = np.zeros((N - lookback, n_features), dtype=np.float32)

        for i in range(lookback, N):
            window = ohlcv[: i + 1]
            ext = self._extract_external_at(external_series, i, N)
            feats = self._compute_technical(window)
            feats.update(ext)
            feats.update(self._compute_pm_ratios(feats))
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
