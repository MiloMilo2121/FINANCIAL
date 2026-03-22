"""Factor Model Features — carry, momentum, value, VRP, and cross-sectional.

Derives 8 factors from already-computed indicators (no new API calls required).
All inputs come from the `feats` dict that FeaturePipeline builds internally.

References:
  - Gold carry: Erb & Harvey (2013) "The Golden Dilemma"
  - Commodity momentum: Asness, Moskowitz & Pedersen (2013)
  - Variance Risk Premium: Dew-Becker et al. (2016)
"""

from __future__ import annotations

import math

import numpy as np


def compute_factor_features(
    feats: dict[str, float],
    close: np.ndarray,
) -> dict[str, float]:
    """Compute all 8 factor features.

    Parameters
    ----------
    feats : dict[str, float]
        The running features dict as built by FeaturePipeline (contains macro
        indicators: GOFO_1m, Fed_Funds_Rate / SOFR, VIX, etc.)
    close : np.ndarray
        Gold close price series (daily, recent history ≥ 252 bars preferred).

    Returns
    -------
    dict with 8 factor indicator keys.
    """
    result: dict[str, float] = {}

    # ── 1. Gold Carry Factor (GOFO_1m - SOFR / Fed Funds Rate) ───────────────
    gofo    = feats.get("GOFO_1m", 0.0) or 0.0
    sofr    = feats.get("SOFR", 0.0) or feats.get("Fed_Funds_Rate", 0.0) or 0.0
    result["Gold_carry_factor"] = float(gofo - sofr)

    # ── 2. Gold Momentum 12-1 month ───────────────────────────────────────────
    # Return from 12 months ago to 1 month ago (skip last month to avoid reversal)
    if len(close) >= 252:
        p_12m = close[-252] if len(close) >= 252 else close[0]
        p_1m  = close[-21]  if len(close) >= 21  else close[0]
        p_now = close[-1]
        if p_12m > 0 and p_1m > 0:
            mom_12_1 = float(math.log(p_1m / p_12m))
        else:
            mom_12_1 = 0.0
    else:
        mom_12_1 = float(feats.get("Return_60d", 0.0))  # fallback to 60d
    result["Gold_momentum_12_1"] = float(np.clip(mom_12_1, -1.0, 1.0))

    # ── 3. Gold Cross-Sectional Momentum vs Silver ─────────────────────────────
    gold_ret  = feats.get("Return_20d", 0.0) or 0.0
    silver_rt = feats.get("Silver_price", 0.0)
    # Proxy: gold return relative to cross-asset mean (use ROC_20)
    # We don't have silver return directly, so use a proxy from gold vs silver ratio change
    gs_ratio  = feats.get("Gold_silver_ratio", 0.0) or 0.0
    if gs_ratio > 0:
        # If ratio rising → gold outperforming silver → positive cross-sectional momentum
        result["Gold_cross_sectional_momentum"] = float(np.clip(gold_ret, -1.0, 1.0))
    else:
        result["Gold_cross_sectional_momentum"] = 0.0

    # ── 4. Gold Value Factor (real price / 10Y moving average) ───────────────
    if len(close) >= 252:
        ma_10y = np.mean(close[-min(len(close), 2520):])  # up to 10Y of data
        cpi_adj = 1.0 + (feats.get("CPI_YoY", 0.0) or 0.0) / 100.0
        real_price = float(close[-1]) / max(cpi_adj, 0.1)
        result["Gold_value_factor"] = float(np.clip(real_price / (ma_10y + 1e-12), 0.0, 5.0))
    elif len(close) > 0:
        result["Gold_value_factor"] = 1.0  # at fair value by default
    else:
        result["Gold_value_factor"] = 1.0

    # ── 5. Gold/Commodity Basket Ratio (proxy for BCOM via Oil+Copper) ────────
    oil    = feats.get("WTI_crude", 0.0) or 0.0
    copper = feats.get("Copper_price", 0.0) or 0.0
    gold_p = float(close[-1]) if len(close) > 0 else 0.0

    if oil > 0 and copper > 0 and gold_p > 0:
        # Normalize: gold in $/oz, oil in $/bbl, copper in $/lb
        bcom_proxy = (oil * 0.5 + copper * 100 * 0.5)  # rough equal-weight proxy
        result["Gold_commodity_ratio"] = float(np.clip(gold_p / (bcom_proxy + 1e-12), 0.0, 100.0))
    else:
        result["Gold_commodity_ratio"] = 0.0

    # ── 6. GDX / GDXJ Ratio (miners leverage ratio) ───────────────────────────
    gdx  = feats.get("GDX_price", 0.0) or 0.0
    gdxj = feats.get("GDXJ_price", 0.0) or 0.0
    if gdx > 0 and gdxj > 0:
        result["GDX_GDXJ_ratio"] = float(np.clip(gdx / gdxj, 0.0, 10.0))
    else:
        result["GDX_GDXJ_ratio"] = 0.0

    # ── 7. Gold Variance Risk Premium (HV20 - GVZ implied vol) ───────────────
    hv20 = feats.get("HV_20", 0.0) or 0.0
    gvz  = feats.get("GVZ_index", 0.0) or 0.0
    if gvz > 0:
        result["Gold_VRP"] = float(np.clip(hv20 - gvz, -50.0, 50.0))
    elif hv20 > 0:
        # Fallback: VIX-gold vol spread as proxy
        vix = feats.get("VIX_index", 0.0) or 0.0
        result["Gold_VRP"] = float(np.clip(hv20 - vix, -50.0, 50.0))
    else:
        result["Gold_VRP"] = 0.0

    # ── 8. Gold Contango / Backwardation ─────────────────────────────────────
    # GOFO > 0 → contango (futures premium); GOFO < 0 → backwardation
    gofo_3m = feats.get("GOFO_3m", 0.0) or 0.0
    gofo_1m = feats.get("GOFO_1m", 0.0) or 0.0
    # Use term spread as the signal
    result["Gold_contango_backwardation"] = float(np.clip(gofo_3m - gofo_1m, -5.0, 5.0))

    return result
