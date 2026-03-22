"""Feature Registry — 334 IndicatorMeta definitions.

Every indicator in the system is registered here with full metadata.
INDICATOR_REGISTRY is the single source of truth for feature ordering,
sourcing, and documentation. The FeaturePipeline uses this registry to
build its output vector (always in registration order).

Breakdown (334 total):
  Technical (75) + Macro (49) + Precious Metal (24) + Alternative (17)
  + Correlations (10) + ML Features (16) + Calendar (18) + Factor (8)
  + New Macro FRED (20) + COT Disagg (8) + De-dollarization (8)
  + Physical Microstructure (12) + ETF Flows (9) + WGC Demand (13)
  + GPR Sub-indexes (6) + Crypto & Digital (10) + Options/Derivatives (6)
  + Extra Technical (25)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IndicatorMeta:
    name: str
    category: str
    description: str
    source: str
    is_computed: bool
    freq: str
    tags: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tech(name, desc, requires=None):
    return IndicatorMeta(
        name=name, category="technical", description=desc, source="ohlcv",
        is_computed=True, freq="1d",
        tags=["technical"],
        requires=requires or ["close"],
    )


def _macro(name, desc, source, freq="1d"):
    return IndicatorMeta(
        name=name, category="macro", description=desc, source=source,
        is_computed=False, freq=freq, tags=["macro"],
        requires=[],
    )


def _pm(name, desc, source, freq="1d"):
    return IndicatorMeta(
        name=name, category="precious_metal", description=desc, source=source,
        is_computed=False, freq=freq, tags=["precious_metal", "gold"],
        requires=[],
    )


def _alt(name, desc, source, freq="1d"):
    return IndicatorMeta(
        name=name, category="alternative", description=desc, source=source,
        is_computed=False, freq=freq, tags=["alternative"],
        requires=[],
    )


def _corr(name, desc):
    return IndicatorMeta(
        name=name, category="correlation", description=desc, source="ohlcv",
        is_computed=True, freq="1d", tags=["correlation"],
        requires=["close"],
    )


def _ml(name, desc, requires=None):
    return IndicatorMeta(
        name=name, category="ml_feature", description=desc, source="computed",
        is_computed=True, freq="1d", tags=["ml", "statistical"],
        requires=requires or ["close"],
    )


def _cal(name, desc):
    return IndicatorMeta(
        name=name, category="calendar", description=desc, source="computed",
        is_computed=True, freq="1d", tags=["calendar", "seasonality"],
        requires=["date"],
    )


def _fac(name, desc, requires=None):
    return IndicatorMeta(
        name=name, category="factor", description=desc, source="computed",
        is_computed=True, freq="1d", tags=["factor", "risk_premium"],
        requires=requires or ["close"],
    )


def _phy(name, desc, source, freq="1d"):
    return IndicatorMeta(
        name=name, category="physical_microstructure", description=desc,
        source=source, is_computed=False, freq=freq,
        tags=["physical", "microstructure"], requires=[],
    )


def _etf(name, desc, freq="1d"):
    return IndicatorMeta(
        name=name, category="etf_flows", description=desc, source="etf",
        is_computed=False, freq=freq, tags=["etf", "flows"], requires=[],
    )


def _tic(name, desc):
    return IndicatorMeta(
        name=name, category="dedollarization", description=desc,
        source="treasury_tic", is_computed=False, freq="1m",
        tags=["dedollarization", "tic"], requires=[],
    )


def _opt(name, desc):
    return IndicatorMeta(
        name=name, category="options", description=desc, source="cme_cvol",
        is_computed=False, freq="1d", tags=["options", "derivatives"],
        requires=[],
    )


def _gpr_sub(name, desc):
    return IndicatorMeta(
        name=name, category="alternative", description=desc, source="gpr_index",
        is_computed=False, freq="1m", tags=["alternative", "geopolitical"],
        requires=[],
    )


def _crypto(name, desc, freq="1d"):
    return IndicatorMeta(
        name=name, category="crypto", description=desc, source="crypto_sentiment",
        is_computed=False, freq=freq, tags=["crypto", "digital"],
        requires=[],
    )


def _cot_d(name, desc):
    return IndicatorMeta(
        name=name, category="cot_disagg", description=desc, source="cftc_disagg",
        is_computed=False, freq="1w", tags=["cot", "positioning"], requires=[],
    )


def _wgc(name, desc, freq="1q"):
    return IndicatorMeta(
        name=name, category="wgc_demand", description=desc, source="wgc_demand",
        is_computed=False, freq=freq, tags=["wgc", "supply_demand"], requires=[],
    )


# ── INDICATOR_REGISTRY (175 total) ────────────────────────────────────────────

INDICATOR_REGISTRY: dict[str, IndicatorMeta] = {

    # ── Moving Averages (17) ─────────────────────────────────────────────────
    "SMA_5":    _tech("SMA_5",    "5-day Simple Moving Average"),
    "SMA_10":   _tech("SMA_10",   "10-day Simple Moving Average"),
    "SMA_20":   _tech("SMA_20",   "20-day Simple Moving Average"),
    "SMA_50":   _tech("SMA_50",   "50-day Simple Moving Average"),
    "SMA_100":  _tech("SMA_100",  "100-day Simple Moving Average"),
    "SMA_200":  _tech("SMA_200",  "200-day Simple Moving Average"),
    "EMA_5":    _tech("EMA_5",    "5-day Exponential Moving Average"),
    "EMA_10":   _tech("EMA_10",   "10-day Exponential Moving Average"),
    "EMA_20":   _tech("EMA_20",   "20-day Exponential Moving Average"),
    "EMA_50":   _tech("EMA_50",   "50-day Exponential Moving Average"),
    "EMA_100":  _tech("EMA_100",  "100-day Exponential Moving Average"),
    "EMA_200":  _tech("EMA_200",  "200-day Exponential Moving Average"),
    "WMA_20":   _tech("WMA_20",   "20-day Weighted Moving Average"),
    "DEMA_20":  _tech("DEMA_20",  "20-day Double Exponential Moving Average"),
    "TEMA_20":  _tech("TEMA_20",  "20-day Triple Exponential Moving Average"),
    "KAMA_20":  _tech("KAMA_20",  "Kaufman Adaptive Moving Average (20-day)"),
    "HullMA_20":_tech("HullMA_20","Hull Moving Average (20-day)"),

    # ── Momentum (22) ─────────────────────────────────────────────────────────
    "MACD_line":   _tech("MACD_line",   "MACD Line (EMA12 - EMA26)"),
    "MACD_signal": _tech("MACD_signal", "MACD Signal (EMA9 of MACD line)"),
    "MACD_hist":   _tech("MACD_hist",   "MACD Histogram (MACD - Signal)"),
    "RSI_7":       _tech("RSI_7",       "7-day Relative Strength Index"),
    "RSI_14":      _tech("RSI_14",      "14-day Relative Strength Index"),
    "RSI_21":      _tech("RSI_21",      "21-day Relative Strength Index"),
    "Stoch_K":     _tech("Stoch_K",     "Stochastic %K (14-period)", ["high","low","close"]),
    "Stoch_D":     _tech("Stoch_D",     "Stochastic %D (3-period SMA of %K)", ["high","low","close"]),
    "StochRSI_14": _tech("StochRSI_14", "Stochastic RSI (14-day)"),
    "ROC_5":       _tech("ROC_5",       "5-day Rate of Change (%)"),
    "ROC_10":      _tech("ROC_10",      "10-day Rate of Change (%)"),
    "ROC_20":      _tech("ROC_20",      "20-day Rate of Change (%)"),
    "ROC_60":      _tech("ROC_60",      "60-day Rate of Change (%)"),
    "MOM_10":      _tech("MOM_10",      "10-day Momentum (price difference)"),
    "Williams_R":  _tech("Williams_R",  "14-day Williams %R", ["high","low","close"]),
    "CCI_14":      _tech("CCI_14",      "14-day Commodity Channel Index", ["high","low","close"]),
    "CMO_14":      _tech("CMO_14",      "14-day Chande Momentum Oscillator"),
    "DPO_20":      _tech("DPO_20",      "20-day Detrended Price Oscillator"),
    "ADX_14":      _tech("ADX_14",      "14-day Average Directional Index", ["high","low","close"]),
    "DI_plus":     _tech("DI_plus",     "+DI (14-day directional indicator)", ["high","low","close"]),
    "DI_minus":    _tech("DI_minus",    "-DI (14-day directional indicator)", ["high","low","close"]),
    "AROON_up":    _tech("AROON_up",    "Aroon Up (25-period)", ["high","low"]),
    "AROON_down":  _tech("AROON_down",  "Aroon Down (25-period)", ["high","low"]),
    "AROON_osc":   _tech("AROON_osc",   "Aroon Oscillator (up - down)", ["high","low"]),
    "PSAR":        _tech("PSAR",        "Parabolic SAR value", ["high","low"]),

    # ── Volatility (15) ──────────────────────────────────────────────────────
    "ATR_7":    _tech("ATR_7",    "7-day Average True Range", ["high","low","close"]),
    "ATR_14":   _tech("ATR_14",   "14-day Average True Range", ["high","low","close"]),
    "ATR_21":   _tech("ATR_21",   "21-day Average True Range", ["high","low","close"]),
    "NATR_14":  _tech("NATR_14",  "14-day Normalized ATR (%)", ["high","low","close"]),
    "BB_upper": _tech("BB_upper", "Bollinger Band Upper (20, 2σ)"),
    "BB_lower": _tech("BB_lower", "Bollinger Band Lower (20, 2σ)"),
    "BB_width": _tech("BB_width", "Bollinger Band Width ((upper-lower)/middle)"),
    "BB_pct":   _tech("BB_pct",   "Bollinger %B ((close-lower)/(upper-lower))"),
    "KC_upper": _tech("KC_upper", "Keltner Channel Upper", ["high","low","close"]),
    "KC_lower": _tech("KC_lower", "Keltner Channel Lower", ["high","low","close"]),
    "Donchian_high_20": _tech("Donchian_high_20", "20-day Donchian High", ["high"]),
    "Donchian_low_20":  _tech("Donchian_low_20",  "20-day Donchian Low", ["low"]),
    "HV_10":    _tech("HV_10",    "10-day Historical Volatility (annualized)"),
    "HV_20":    _tech("HV_20",    "20-day Historical Volatility (annualized)"),
    "HV_60":    _tech("HV_60",    "60-day Historical Volatility (annualized)"),

    # ── Volume (8) ────────────────────────────────────────────────────────────
    "OBV":           _tech("OBV",           "On Balance Volume", ["close","volume"]),
    "CMF_20":        _tech("CMF_20",        "20-day Chaikin Money Flow", ["high","low","close","volume"]),
    "MFI_14":        _tech("MFI_14",        "14-day Money Flow Index", ["high","low","close","volume"]),
    "AD_line":       _tech("AD_line",       "Accumulation/Distribution Line", ["high","low","close","volume"]),
    "Volume_SMA_20": _tech("Volume_SMA_20", "20-day Volume Simple Moving Average", ["volume"]),
    "Volume_ratio":  _tech("Volume_ratio",  "Volume / 20-day Volume SMA", ["volume"]),
    "Volume_zscore": _tech("Volume_zscore", "Volume z-score (20-day)", ["volume"]),
    "VWAP_20":       _tech("VWAP_20",       "20-day Volume Weighted Average Price", ["high","low","close","volume"]),

    # ── Price Position (10) ───────────────────────────────────────────────────
    "Price_SMA20_ratio":  _tech("Price_SMA20_ratio",  "Close / SMA20 ratio"),
    "Price_SMA50_ratio":  _tech("Price_SMA50_ratio",  "Close / SMA50 ratio"),
    "Price_SMA200_ratio": _tech("Price_SMA200_ratio", "Close / SMA200 ratio"),
    "Return_1d":  _tech("Return_1d",  "1-day log return"),
    "Return_5d":  _tech("Return_5d",  "5-day cumulative log return"),
    "Return_10d": _tech("Return_10d", "10-day cumulative log return"),
    "Return_20d": _tech("Return_20d", "20-day cumulative log return"),
    "Return_60d": _tech("Return_60d", "60-day cumulative log return"),
    "High_52w_pct": _tech("High_52w_pct", "Position within 52-week high/low range (0-1)"),
    "Low_52w_pct":  _tech("Low_52w_pct",  "Distance from 52-week low as fraction of range"),

    # ── Interest Rates (10) — FRED ────────────────────────────────────────────
    "Fed_Funds_Rate":    _macro("Fed_Funds_Rate",    "Federal Funds Effective Rate (%)", "fred"),
    "Treasury_2Y":       _macro("Treasury_2Y",       "2-Year Treasury Constant Maturity Rate (%)", "fred"),
    "Treasury_5Y":       _macro("Treasury_5Y",       "5-Year Treasury Constant Maturity Rate (%)", "fred"),
    "Treasury_10Y":      _macro("Treasury_10Y",      "10-Year Treasury Constant Maturity Rate (%)", "fred"),
    "Treasury_30Y":      _macro("Treasury_30Y",      "30-Year Treasury Constant Maturity Rate (%)", "fred"),
    "TIPS_10Y":          _macro("TIPS_10Y",          "10-Year TIPS Real Yield (%)", "fred"),
    "Yield_curve_10_2":  _macro("Yield_curve_10_2",  "10Y-2Y Treasury Yield Spread (bps)", "fred"),
    "Yield_curve_10_3m": _macro("Yield_curve_10_3m", "10Y-3M Treasury Yield Spread (bps)", "fred"),
    "Breakeven_5Y":      _macro("Breakeven_5Y",      "5-Year Breakeven Inflation Rate (%)", "fred"),
    "Breakeven_10Y":     _macro("Breakeven_10Y",     "10-Year Breakeven Inflation Rate (%)", "fred"),

    # ── Inflation (5) — FRED ──────────────────────────────────────────────────
    "CPI_YoY":      _macro("CPI_YoY",      "CPI All Items YoY change (%)", "fred", "1m"),
    "CPI_Core_YoY": _macro("CPI_Core_YoY", "Core CPI (ex food&energy) YoY (%)", "fred", "1m"),
    "PPI_YoY":      _macro("PPI_YoY",      "Producer Price Index YoY change (%)", "fred", "1m"),
    "PCE_YoY":      _macro("PCE_YoY",      "PCE Price Index YoY change (%)", "fred", "1m"),
    "PCE_Core_YoY": _macro("PCE_Core_YoY", "Core PCE Price Index YoY change (%)", "fred", "1m"),

    # ── Money Supply (3) — FRED ───────────────────────────────────────────────
    "M2_YoY":             _macro("M2_YoY",             "M2 Money Supply YoY growth (%)", "fred", "1m"),
    "Real_M2_growth":     _macro("Real_M2_growth",     "Real M2 growth (M2 growth - CPI)", "fred", "1m"),
    "Monetary_base_growth":_macro("Monetary_base_growth","Monetary Base YoY growth (%)", "fred", "1m"),

    # ── Currency (8) — FRED ───────────────────────────────────────────────────
    "DXY_index":          _macro("DXY_index",          "US Dollar Index (DXY)", "fred"),
    "EUR_USD":            _macro("EUR_USD",             "EUR/USD Exchange Rate", "fred"),
    "USD_JPY":            _macro("USD_JPY",             "USD/JPY Exchange Rate", "fred"),
    "USD_CNY":            _macro("USD_CNY",             "USD/CNY Exchange Rate", "fred"),
    "GBP_USD":            _macro("GBP_USD",             "GBP/USD Exchange Rate", "fred"),
    "CHF_USD":            _macro("CHF_USD",             "CHF/USD Exchange Rate", "fred"),
    "Trade_weighted_dollar": _macro("Trade_weighted_dollar", "Trade Weighted US Dollar Index", "fred"),
    "DXY_change_20d":     _macro("DXY_change_20d",     "20-day DXY % change", "fred"),

    # ── Economic Activity (5) — FRED / World Bank ────────────────────────────
    "GDP_growth_US":    _macro("GDP_growth_US",    "US GDP Growth Rate (annual %)", "world_bank", "1q"),
    "GDP_growth_China": _macro("GDP_growth_China", "China GDP Growth Rate (annual %)", "world_bank", "1q"),
    "ISM_PMI":          _macro("ISM_PMI",          "ISM Manufacturing PMI", "fred", "1m"),
    "Retail_sales_YoY": _macro("Retail_sales_YoY", "US Retail Sales YoY change (%)", "fred", "1m"),
    "Industrial_production_YoY": _macro("Industrial_production_YoY", "Industrial Production YoY (%)", "fred", "1m"),

    # ── Employment (3) — FRED ─────────────────────────────────────────────────
    "Unemployment_rate":     _macro("Unemployment_rate",     "US Unemployment Rate (%)", "fred", "1m"),
    "NFP_change":            _macro("NFP_change",            "Non-Farm Payrolls monthly change (K)", "fred", "1m"),
    "Initial_jobless_claims":_macro("Initial_jobless_claims","Initial Jobless Claims (weekly, K)", "fred", "1w"),

    # ── Energy & Commodities (7) — EIA / Alpha Vantage ───────────────────────
    "WTI_crude":     _macro("WTI_crude",     "WTI Crude Oil Spot Price (USD/bbl)", "eia"),
    "Brent_crude":   _macro("Brent_crude",   "Brent Crude Oil Spot Price (USD/bbl)", "eia"),
    "Natural_gas":   _macro("Natural_gas",   "Henry Hub Natural Gas Price (USD/MMBtu)", "eia"),
    "Copper_price":  _macro("Copper_price",  "Copper Spot Price (USD/lb)", "alpha_vantage"),
    "Silver_price":  _macro("Silver_price",  "Silver Spot Price (USD/oz)", "alpha_vantage"),
    "Platinum_price":_macro("Platinum_price","Platinum Spot Price (USD/oz)", "alpha_vantage"),
    "Palladium_price":_macro("Palladium_price","Palladium Spot Price (USD/oz)", "alpha_vantage"),

    # ── Market Risk (6) — CBOE / FRED ─────────────────────────────────────────
    "VIX_index":       _macro("VIX_index",       "CBOE Volatility Index (VIX)", "cboe"),
    "VVIX_index":      _macro("VVIX_index",       "Volatility of VIX (VVIX)", "cboe"),
    "Put_call_ratio":  _macro("Put_call_ratio",   "Equity Put/Call Ratio", "cboe"),
    "TED_spread":      _macro("TED_spread",       "TED Spread (3M LIBOR - 3M T-bill, bps)", "fred"),
    "IG_credit_spread":_macro("IG_credit_spread", "IG Corporate Bond Spread (OAS, bps)", "fred"),
    "HY_credit_spread":_macro("HY_credit_spread", "HY Corporate Bond Spread (OAS, bps)", "fred"),

    # ── Precious Metal Specific (24) ─────────────────────────────────────────
    "Gold_silver_ratio":   _pm("Gold_silver_ratio",   "Gold/Silver Ratio (oz gold per oz silver)", "computed"),
    "Gold_copper_ratio":   _pm("Gold_copper_ratio",   "Gold/Copper Ratio", "computed"),
    "Gold_oil_ratio":      _pm("Gold_oil_ratio",      "Gold/WTI Oil Ratio (oz gold per bbl)", "computed"),
    "Gold_platinum_ratio": _pm("Gold_platinum_ratio", "Gold/Platinum Ratio", "computed"),
    "GDX_price":           _pm("GDX_price",           "VanEck Gold Miners ETF (GDX) Price", "marketstack"),
    "GDX_gold_ratio":      _pm("GDX_gold_ratio",      "GDX / Gold Price Ratio", "computed"),
    "GDXJ_gold_ratio":     _pm("GDXJ_gold_ratio",     "GDXJ Junior Miners / Gold Price Ratio", "marketstack"),
    "Gold_lease_rate_1m":  _pm("Gold_lease_rate_1m",  "1-month Gold Lease Rate (%)", "lbma", "1m"),
    "Gold_lease_rate_3m":  _pm("Gold_lease_rate_3m",  "3-month Gold Lease Rate (%)", "lbma", "1m"),
    "Gold_lease_rate_6m":  _pm("Gold_lease_rate_6m",  "6-month Gold Lease Rate (%)", "lbma", "1m"),
    "GOFO_1m":             _pm("GOFO_1m",             "1-month Gold Forward Offered Rate (%)", "lbma", "1m"),
    "GOFO_3m":             _pm("GOFO_3m",             "3-month Gold Forward Offered Rate (%)", "lbma", "1m"),
    "COMEX_open_interest": _pm("COMEX_open_interest", "COMEX Gold Futures Open Interest (lots)", "comex"),
    "COMEX_net_longs":     _pm("COMEX_net_longs",     "COMEX Gold Net Long Positions (lots)", "comex"),
    "COT_commercials_net": _pm("COT_commercials_net", "CFTC COT Gold Commercials Net Positions", "cftc", "1w"),
    "COT_speculators_net": _pm("COT_speculators_net", "CFTC COT Gold Non-Commercials Net Positions", "cftc", "1w"),
    "GLD_ETF_holdings":    _pm("GLD_ETF_holdings",    "SPDR Gold Trust (GLD) Holdings (tonnes)", "marketstack"),
    "IAU_ETF_holdings":    _pm("IAU_ETF_holdings",    "iShares Gold Trust (IAU) Holdings (tonnes)", "marketstack"),
    "CB_gold_purchases":   _pm("CB_gold_purchases",   "Central Bank Gold Purchases (tonnes, quarterly)", "wgc", "1q"),
    "LBMA_AM_fix":         _pm("LBMA_AM_fix",         "LBMA Gold AM Fix (USD/oz)", "lbma"),
    "LBMA_PM_fix":         _pm("LBMA_PM_fix",         "LBMA Gold PM Fix (USD/oz)", "lbma"),
    "Mining_AISC":         _pm("Mining_AISC",         "All-In Sustaining Cost (industry avg, USD/oz)", "wgc", "1q"),
    "WGC_jewelry_demand":  _pm("WGC_jewelry_demand",  "WGC Global Jewelry Demand (tonnes, quarterly)", "wgc", "1q"),
    "WGC_investment_demand":_pm("WGC_investment_demand","WGC Global Investment Demand (tonnes, quarterly)", "wgc", "1q"),

    # ── Alternative & Sentiment (17) ─────────────────────────────────────────
    "GPR_index":      _alt("GPR_index",      "Geopolitical Risk Index (Caldara & Iacoviello)", "gpr_index"),
    "GPR_acts":       _alt("GPR_acts",       "GPR Acts sub-index (realized geopolitical acts)", "gpr_index"),
    "GPR_threats":    _alt("GPR_threats",    "GPR Threats sub-index (media geopolitical threats)", "gpr_index"),
    "Ship_London":    _alt("Ship_London",    "Maritime Congestion — Thames (London)", "shipsdna"),
    "Ship_Dubai":     _alt("Ship_Dubai",     "Maritime Congestion — Dubai Port Rashid", "shipsdna"),
    "Ship_HK":        _alt("Ship_HK",        "Maritime Congestion — Hong Kong", "shipsdna"),
    "Ship_Mumbai":    _alt("Ship_Mumbai",    "Maritime Congestion — Mumbai", "shipsdna"),
    "Ship_Shanghai":  _alt("Ship_Shanghai",  "Maritime Congestion — Shanghai", "shipsdna"),
    "Cargo_LHR":      _alt("Cargo_LHR",      "Cargo Flights — London Heathrow (count)", "opensky"),
    "Cargo_ZRH":      _alt("Cargo_ZRH",      "Cargo Flights — Zurich (count)", "opensky"),
    "Cargo_DXB":      _alt("Cargo_DXB",      "Cargo Flights — Dubai (count)", "opensky"),
    "Cargo_HKG":      _alt("Cargo_HKG",      "Cargo Flights — Hong Kong (count)", "opensky"),
    "Satellite_NDVI_Nevada":      _alt("Satellite_NDVI_Nevada",      "Satellite NDVI — Nevada Carlin Mine", "eosda"),
    "Satellite_anomaly_Wits":     _alt("Satellite_anomaly_Wits",     "Satellite Anomaly Score — Witwatersrand SA", "eosda"),
    "Gold_sentiment_score":       _alt("Gold_sentiment_score",       "Gold Sentiment Score [-1,1] (Perplexity)", "sentiment"),
    "Gold_sentiment_confidence":  _alt("Gold_sentiment_confidence",  "Gold Sentiment Confidence [0,1]", "sentiment"),
    "Geo_threat_level":           _alt("Geo_threat_level",           "Geopolitical Threat Level [0-4]", "sentiment"),

    # ── Cross-Asset Rolling Correlations (10) ────────────────────────────────
    "Gold_DXY_corr_30d":    _corr("Gold_DXY_corr_30d",    "Gold vs DXY 30-day rolling correlation"),
    "Gold_DXY_corr_60d":    _corr("Gold_DXY_corr_60d",    "Gold vs DXY 60-day rolling correlation"),
    "Gold_10Y_corr_30d":    _corr("Gold_10Y_corr_30d",    "Gold vs 10Y yield 30-day rolling correlation"),
    "Gold_10Y_corr_60d":    _corr("Gold_10Y_corr_60d",    "Gold vs 10Y yield 60-day rolling correlation"),
    "Gold_SPX_corr_30d":    _corr("Gold_SPX_corr_30d",    "Gold vs S&P500 30-day rolling correlation"),
    "Gold_SPX_corr_60d":    _corr("Gold_SPX_corr_60d",    "Gold vs S&P500 60-day rolling correlation"),
    "Gold_oil_corr_30d":    _corr("Gold_oil_corr_30d",    "Gold vs WTI Oil 30-day rolling correlation"),
    "Gold_copper_corr_30d": _corr("Gold_copper_corr_30d", "Gold vs Copper 30-day rolling correlation"),
    "Gold_silver_corr_30d": _corr("Gold_silver_corr_30d", "Gold vs Silver 30-day rolling correlation"),
    "Gold_BTC_corr_30d":    _corr("Gold_BTC_corr_30d",    "Gold vs Bitcoin 30-day rolling correlation"),

    # ═══════════════════════════════════════════════════════════════════════════
    # ── NEW INDICATORS (175 → 334) ────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    # ── ML Feature Engineering (16) ──────────────────────────────────────────
    "Hurst_120d":           _ml("Hurst_120d",           "Hurst exponent via R/S analysis (120-day window)"),
    "HMM_bull_prob":        _ml("HMM_bull_prob",        "Hidden Markov Model bull state probability"),
    "HMM_bear_prob":        _ml("HMM_bear_prob",        "Hidden Markov Model bear state probability"),
    "HMM_volatile_prob":    _ml("HMM_volatile_prob",    "Hidden Markov Model volatile/sideways state probability"),
    "Fourier_annual_sin":   _ml("Fourier_annual_sin",   "Annual Fourier sin term (365-day cycle)", ["date"]),
    "Fourier_annual_cos":   _ml("Fourier_annual_cos",   "Annual Fourier cos term (365-day cycle)", ["date"]),
    "Fourier_semiannual_sin":_ml("Fourier_semiannual_sin","Semi-annual Fourier sin term (183-day cycle)", ["date"]),
    "Fourier_semiannual_cos":_ml("Fourier_semiannual_cos","Semi-annual Fourier cos term (183-day cycle)", ["date"]),
    "Fourier_quarterly_sin":_ml("Fourier_quarterly_sin","Quarterly Fourier sin term (91-day cycle)", ["date"]),
    "Fourier_quarterly_cos":_ml("Fourier_quarterly_cos","Quarterly Fourier cos term (91-day cycle)", ["date"]),
    "Wavelet_DWT_scale2":   _ml("Wavelet_DWT_scale2",   "Discrete Wavelet Transform detail coeff. scale~4d"),
    "Wavelet_DWT_scale8":   _ml("Wavelet_DWT_scale8",   "Discrete Wavelet Transform detail coeff. scale~16d"),
    "Realized_skewness_30d":_ml("Realized_skewness_30d","30-day realized return skewness"),
    "Realized_kurtosis_30d":_ml("Realized_kurtosis_30d","30-day realized return kurtosis"),
    "Kalman_beta_SPX":      _ml("Kalman_beta_SPX",      "Time-varying Kalman filter beta to S&P500", ["close","benchmark"]),
    "Sample_entropy_30d":   _ml("Sample_entropy_30d",   "30-day sample entropy of log-returns (complexity)"),

    # ── Calendar / Seasonality Features (18) ────────────────────────────────
    "Month_sin":                _cal("Month_sin",                "Month of year cyclical encoding — sin"),
    "Month_cos":                _cal("Month_cos",                "Month of year cyclical encoding — cos"),
    "CNY_proximity":            _cal("CNY_proximity",            "Proximity to Chinese New Year (0-1 triangular)"),
    "Diwali_proximity":         _cal("Diwali_proximity",         "Proximity to Diwali festival (0-1 triangular)"),
    "Indian_wedding_season":    _cal("Indian_wedding_season",    "Indian wedding season flag (Oct–Dec = 1)"),
    "Indian_harvest_season":    _cal("Indian_harvest_season",    "Indian harvest/Akshaya Tritiya season (Apr–May = 1)"),
    "Ramadan_proximity":        _cal("Ramadan_proximity",        "Proximity to Ramadan start (Turkish/ME demand)"),
    "FOMC_meeting_flag":        _cal("FOMC_meeting_flag",        "FOMC meeting day binary flag"),
    "Days_to_FOMC":             _cal("Days_to_FOMC",             "Normalized days to next FOMC meeting (0-1)"),
    "FOMC_blackout_flag":       _cal("FOMC_blackout_flag",       "FOMC blackout period flag (10 days pre-meeting)"),
    "COMEX_FND_flag":           _cal("COMEX_FND_flag",           "COMEX gold futures First Notice Day flag"),
    "COMEX_options_expiry":     _cal("COMEX_options_expiry",     "COMEX gold options expiry day flag"),
    "COMEX_quarterly_delivery": _cal("COMEX_quarterly_delivery", "COMEX active delivery month flag (Feb/Apr/Jun/Aug/Oct/Dec)"),
    "Quarter_end_flag":         _cal("Quarter_end_flag",         "Quarter-end flag (last 5 days of Mar/Jun/Sep/Dec)"),
    "Year_end_flag":            _cal("Year_end_flag",            "Year-end flag (last 10 days of Dec)"),
    "Day_of_week_sin":          _cal("Day_of_week_sin",          "Day of week cyclical encoding — sin"),
    "Day_of_week_cos":          _cal("Day_of_week_cos",          "Day of week cyclical encoding — cos"),
    "NFP_release_flag":         _cal("NFP_release_flag",         "Non-Farm Payrolls release day flag (first Friday of month)"),

    # ── Factor Model Features (8) ────────────────────────────────────────────
    "Gold_carry_factor":              _fac("Gold_carry_factor",              "Gold carry factor = GOFO_1m − SOFR (Erb & Harvey 2013)"),
    "Gold_momentum_12_1":             _fac("Gold_momentum_12_1",             "Gold 12-1 month price momentum"),
    "Gold_cross_sectional_momentum":  _fac("Gold_cross_sectional_momentum",  "Gold cross-sectional momentum vs commodities"),
    "Gold_value_factor":              _fac("Gold_value_factor",              "Gold real price / 10Y moving average (value ratio)"),
    "Gold_commodity_ratio":           _fac("Gold_commodity_ratio",           "Gold price / commodity basket proxy (BCOM proxy)"),
    "GDX_GDXJ_ratio":                 _fac("GDX_GDXJ_ratio",                "GDX senior miners / GDXJ junior miners price ratio"),
    "Gold_VRP":                       _fac("Gold_VRP",                       "Gold Variance Risk Premium = HV20 − GVZ implied vol"),
    "Gold_contango_backwardation":     _fac("Gold_contango_backwardation",    "Gold forward curve slope (GOFO_3m − GOFO_1m)"),

    # ── New Macro — FRED Free (20) ───────────────────────────────────────────
    "TIPS_5Y":                _macro("TIPS_5Y",                "5-Year TIPS Real Yield (%)", "fred"),
    "TIPS_30Y":               _macro("TIPS_30Y",               "30-Year TIPS Real Yield (%)", "fred"),
    "Real_Fed_Funds_Rate":    _macro("Real_Fed_Funds_Rate",    "Real Federal Funds Rate (FFR - CPI YoY)", "fred"),
    "Fed_balance_sheet_bn":   _macro("Fed_balance_sheet_bn",   "Fed Balance Sheet total assets ($ billions, WALCL)", "fred"),
    "Fed_balance_sheet_yoy":  _macro("Fed_balance_sheet_yoy",  "Fed Balance Sheet YoY change (%)", "fred"),
    "US_debt_gdp":            _macro("US_debt_gdp",            "US Federal Debt as % of GDP", "fred", "1q"),
    "US_current_account_gdp": _macro("US_current_account_gdp","US Current Account Balance as % of GDP", "fred", "1q"),
    "EPU_US_daily":           _macro("EPU_US_daily",           "US Economic Policy Uncertainty Index (Baker et al.)", "fred"),
    "EPU_global":             _macro("EPU_global",             "Global Economic Policy Uncertainty Index", "fred"),
    "EPU_trade":              _macro("EPU_trade",              "US Trade Policy Uncertainty Index", "fred"),
    "NY_Fed_recession_prob":  _macro("NY_Fed_recession_prob",  "NY Fed 12-month US Recession Probability (%)", "fred", "1m"),
    "OECD_CLI_USA":           _macro("OECD_CLI_USA",           "OECD Composite Leading Indicator — US", "fred", "1m"),
    "OECD_CLI_G7":            _macro("OECD_CLI_G7",            "OECD Composite Leading Indicator — G7", "fred", "1m"),
    "GVZ_index":              _macro("GVZ_index",              "CBOE Gold Volatility Index (GVZ)", "cboe"),
    "NFCI":                   _macro("NFCI",                   "Chicago Fed National Financial Conditions Index", "fred"),
    "ANFCI":                  _macro("ANFCI",                  "Chicago Fed Adjusted NFCI", "fred"),
    "BDI":                    _macro("BDI",                    "Baltic Dry Index (global shipping cost proxy)", "quandl"),
    "ISM_New_Orders":         _macro("ISM_New_Orders",         "ISM Manufacturing New Orders Index", "fred", "1m"),
    "SOFR":                   _macro("SOFR",                   "Secured Overnight Financing Rate (%)", "fred"),
    "OIS_10Y_spread":         _macro("OIS_10Y_spread",         "OIS-Treasury 10Y spread (systemic risk proxy)", "fred"),

    # ── COT Disaggregated — CFTC PRE API (8) ────────────────────────────────
    "COT_MM_net_gold":       _cot_d("COT_MM_net_gold",       "CFTC Disagg: Managed Money net positions — COMEX Gold"),
    "COT_MM_net_silver":     _cot_d("COT_MM_net_silver",     "CFTC Disagg: Managed Money net positions — COMEX Silver"),
    "COT_MM_net_platinum":   _cot_d("COT_MM_net_platinum",   "CFTC Disagg: Managed Money net positions — COMEX Platinum"),
    "COT_MM_net_palladium":  _cot_d("COT_MM_net_palladium",  "CFTC Disagg: Managed Money net positions — COMEX Palladium"),
    "COT_SD_net_gold":       _cot_d("COT_SD_net_gold",       "CFTC Disagg: Swap Dealers net positions — COMEX Gold"),
    "COT_SD_net_silver":     _cot_d("COT_SD_net_silver",     "CFTC Disagg: Swap Dealers net positions — COMEX Silver"),
    "COT_PM_net_gold":       _cot_d("COT_PM_net_gold",       "CFTC Disagg: Producer/Merchant net positions — COMEX Gold"),
    "COT_MM_pct_OI_gold":    _cot_d("COT_MM_pct_OI_gold",    "CFTC Disagg: Managed Money % of Open Interest — Gold"),

    # ── De-dollarization & TIC — US Treasury Free (8) ───────────────────────
    "TIC_foreign_official_total": _tic("TIC_foreign_official_total", "Foreign official holdings of US Treasuries ($ bn)"),
    "TIC_china_holdings":         _tic("TIC_china_holdings",         "China holdings of US Treasuries ($ bn)"),
    "TIC_japan_holdings":         _tic("TIC_japan_holdings",         "Japan holdings of US Treasuries ($ bn)"),
    "TIC_opec_holdings":          _tic("TIC_opec_holdings",          "OPEC countries holdings of US Treasuries ($ bn)"),
    "TIC_grand_total":            _tic("TIC_grand_total",            "Grand total foreign holdings of US Treasuries ($ bn)"),
    "TIC_china_share":            _tic("TIC_china_share",            "China share of total foreign Treasury holdings (0-1)"),
    "TIC_japan_share":            _tic("TIC_japan_share",            "Japan share of total foreign Treasury holdings (0-1)"),
    "IMF_USD_reserve_share": IndicatorMeta(
        name="IMF_USD_reserve_share", category="dedollarization",
        description="IMF COFER: USD share of allocated global FX reserves (%)",
        source="imf_cofer", is_computed=False, freq="1q",
        tags=["dedollarization", "imf"], requires=[],
    ),

    # ── Physical Market Microstructure (12) ──────────────────────────────────
    "SGE_volume":               _phy("SGE_volume",               "Shanghai Gold Exchange daily trading volume (kg)", "sge"),
    "SGE_gold_premium":         _phy("SGE_gold_premium",         "SGE gold premium vs LBMA (USD/oz)", "sge"),
    "COMEX_registered_gold":    _phy("COMEX_registered_gold",    "COMEX registered gold vault stocks (000 oz)", "comex"),
    "COMEX_eligible_gold":      _phy("COMEX_eligible_gold",      "COMEX eligible gold vault stocks (000 oz)", "comex"),
    "COMEX_stocks_OI_ratio":    _phy("COMEX_stocks_OI_ratio",    "COMEX registered stocks / open interest ratio", "comex"),
    "LBMA_clearing_volume":     _phy("LBMA_clearing_volume",     "LBMA daily gold clearing volume (000 oz)", "lbma"),
    "Swiss_gold_exports":       _phy("Swiss_gold_exports",       "Switzerland gold exports (tonnes, monthly)", "swiss_customs", "1m"),
    "Swiss_gold_imports":       _phy("Swiss_gold_imports",       "Switzerland gold imports (tonnes, monthly)", "swiss_customs", "1m"),
    "India_gold_imports":       _phy("India_gold_imports",       "India official gold imports (tonnes, monthly)", "india_customs", "1m"),
    "HK_china_gold_flow":       _phy("HK_china_gold_flow",       "Hong Kong → Mainland China net gold flow (kg, monthly)", "hk_census", "1m"),
    "COMEX_vault_coverage":     _phy("COMEX_vault_coverage",     "COMEX vault coverage ratio (registered/eligible)", "comex"),
    "LBMA_gold_price_am":       _phy("LBMA_gold_price_am",       "LBMA Gold AM auction price (USD/oz)", "lbma"),

    # ── ETF Flows Granular (9) ───────────────────────────────────────────────
    "GLD_weekly_flow_t":        _etf("GLD_weekly_flow_t",        "SPDR GLD weekly net inflow/outflow (tonnes)"),
    "IAU_weekly_flow_t":        _etf("IAU_weekly_flow_t",        "iShares IAU weekly net inflow/outflow (tonnes)"),
    "SGOL_weekly_flow_t":       _etf("SGOL_weekly_flow_t",       "Aberdeen SGOL weekly net inflow/outflow (tonnes)"),
    "PHYS_weekly_flow_t":       _etf("PHYS_weekly_flow_t",       "Sprott PHYS weekly net inflow/outflow (tonnes)"),
    "Global_ETF_aum_t":         _etf("Global_ETF_aum_t",         "Global gold-backed ETF total AUM (tonnes)", "1d"),
    "Asia_ETF_flow_t":          _etf("Asia_ETF_flow_t",          "Asia region gold ETF net weekly flow (tonnes)", "1w"),
    "NorthAmerica_ETF_flow_t":  _etf("NorthAmerica_ETF_flow_t",  "North America gold ETF net weekly flow (tonnes)", "1w"),
    "Europe_ETF_flow_t":        _etf("Europe_ETF_flow_t",        "Europe gold ETF net weekly flow (tonnes)", "1w"),
    "WGC_etf_total_tonnes":     _etf("WGC_etf_total_tonnes",     "WGC total global gold ETF holdings (tonnes)", "1d"),

    # ── WGC Supply & Demand Granular (13) ────────────────────────────────────
    "WGC_tech_demand_t":         _wgc("WGC_tech_demand_t",         "WGC technology demand (tonnes, quarterly)"),
    "WGC_bar_coin_demand_t":     _wgc("WGC_bar_coin_demand_t",     "WGC bar & coin investment demand (tonnes, quarterly)"),
    "WGC_otc_demand_t":          _wgc("WGC_otc_demand_t",          "WGC OTC & other investment demand (tonnes, quarterly)"),
    "WGC_india_jewelry_t":       _wgc("WGC_india_jewelry_t",       "WGC India jewelry demand (tonnes, quarterly)"),
    "WGC_china_jewelry_t":       _wgc("WGC_china_jewelry_t",       "WGC China jewelry demand (tonnes, quarterly)"),
    "WGC_china_bar_coin_t":      _wgc("WGC_china_bar_coin_t",      "WGC China bar & coin demand (tonnes, quarterly)"),
    "WGC_mine_production_t":     _wgc("WGC_mine_production_t",     "WGC global mine production (tonnes, quarterly)"),
    "WGC_aisc_spread":           _wgc("WGC_aisc_spread",           "Gold price minus mining AISC (USD/oz, profitability)"),
    "WGC_scrap_supply_t":        _wgc("WGC_scrap_supply_t",        "WGC gold scrap/recycling supply (tonnes, quarterly)"),
    "WGC_producer_hedging_t":    _wgc("WGC_producer_hedging_t",    "WGC producer net hedging (tonnes, quarterly)"),
    "WGC_total_demand_t":        _wgc("WGC_total_demand_t",        "WGC total identified demand (tonnes, quarterly)"),
    "WGC_total_supply_t":        _wgc("WGC_total_supply_t",        "WGC total supply (tonnes, quarterly)"),
    "WGC_demand_supply_balance": _wgc("WGC_demand_supply_balance", "WGC demand − supply balance (tonnes, quarterly)"),

    # ── GPR Sub-indexes (6) ──────────────────────────────────────────────────
    "GPR_nuclear_threats":     _gpr_sub("GPR_nuclear_threats",     "GPR sub-index: nuclear threats (Caldara & Iacoviello)"),
    "GPR_terror_acts":         _gpr_sub("GPR_terror_acts",         "GPR sub-index: terrorist acts"),
    "GPR_war_escalation":      _gpr_sub("GPR_war_escalation",      "GPR sub-index: war escalation index"),
    "GPR_russia":              _gpr_sub("GPR_russia",              "GPR sub-index: Russia-specific geopolitical risk"),
    "GPR_china":               _gpr_sub("GPR_china",               "GPR sub-index: China-specific geopolitical risk"),
    "GPR_middle_east":         _gpr_sub("GPR_middle_east",         "GPR sub-index: Middle East geopolitical risk"),

    # ── Crypto & Digital (10) ────────────────────────────────────────────────
    "Crypto_fear_greed_index":   _crypto("Crypto_fear_greed_index",   "Crypto Fear & Greed Index (0=fear, 100=greed)"),
    "Crypto_fear_greed_class":   _crypto("Crypto_fear_greed_class",   "Crypto Fear & Greed classification (0-1 encoded)"),
    "BTC_price_usd":             _crypto("BTC_price_usd",             "Bitcoin spot price (USD)"),
    "BTC_gold_ratio":            _crypto("BTC_gold_ratio",            "Bitcoin / Gold price ratio"),
    "PAXG_price_usd":            _crypto("PAXG_price_usd",            "PAX Gold token price (1 oz gold-backed, USD)"),
    "PAXG_premium":              _crypto("PAXG_premium",              "PAXG price premium vs LBMA PM fix (%)"),
    "XAUt_price_usd":            _crypto("XAUt_price_usd",            "Tether Gold (XAUt) token price (USD)"),
    "Stablecoin_total_mcap_bn":  _crypto("Stablecoin_total_mcap_bn",  "Total stablecoin market cap ($ bn)"),
    "USDT_mcap_bn":              _crypto("USDT_mcap_bn",              "Tether (USDT) market cap ($ bn)"),
    "Gold_crypto_flow_7d":       _crypto("Gold_crypto_flow_7d",       "7-day net flow into gold-backed crypto (PAXG+XAUt)", "1w"),

    # ── Options / Derivatives (6) ────────────────────────────────────────────
    "CME_CVOL_gold_atm_iv":    _opt("CME_CVOL_gold_atm_iv",    "CME CVOL Gold ATM implied volatility (%)"),
    "CME_CVOL_gold_skew":      _opt("CME_CVOL_gold_skew",      "CME CVOL Gold 25-delta risk reversal skew"),
    "CME_CVOL_term_slope":     _opt("CME_CVOL_term_slope",     "CME CVOL Gold IV term structure slope (3m-1m)"),
    "GLD_put_call_oi":         _opt("GLD_put_call_oi",         "GLD ETF put/call open interest ratio"),
    "COMEX_options_max_pain":  _opt("COMEX_options_max_pain",  "COMEX gold options max pain strike (USD/oz)"),
    "Gold_IV_term_slope":      _opt("Gold_IV_term_slope",      "Gold implied vol term structure slope (6m-1m ATM)"),

    # ── Extra Technical Indicators (25) ──────────────────────────────────────
    "ROC_1":            _tech("ROC_1",            "1-day Rate of Change (%)"),
    "ROC_3":            _tech("ROC_3",            "3-day Rate of Change (%)"),
    "RSI_2":            _tech("RSI_2",            "2-day Relative Strength Index (overbought/oversold)"),
    "EMA_3":            _tech("EMA_3",            "3-day Exponential Moving Average"),
    "SMA_252":          _tech("SMA_252",          "252-day (1-year) Simple Moving Average"),
    "Return_120d":      _tech("Return_120d",      "120-day cumulative log return"),
    "Return_252d":      _tech("Return_252d",      "252-day cumulative log return"),
    "HV_120":           _tech("HV_120",           "120-day Historical Volatility (annualized)"),
    "HV_252":           _tech("HV_252",           "252-day Historical Volatility (annualized)"),
    "Vol_regime":       _tech("Vol_regime",       "Volatility regime: HV20/HV60 ratio"),
    "Skewness_60d":     _tech("Skewness_60d",     "60-day return skewness"),
    "Kurtosis_60d":     _tech("Kurtosis_60d",     "60-day return kurtosis"),
    "Price_EMA200_ratio": _tech("Price_EMA200_ratio", "Close / EMA200 ratio"),
    "Price_SMA100_ratio": _tech("Price_SMA100_ratio", "Close / SMA100 ratio"),
    "EMA20_SMA50_cross":  _tech("EMA20_SMA50_cross",  "EMA20 / SMA50 crossover signal"),
    "MACD_hist_slope":    _tech("MACD_hist_slope",    "MACD histogram slope (current - previous)"),
    "RSI_divergence":     _tech("RSI_divergence",     "RSI vs price divergence signal"),
    "BB_squeeze":         _tech("BB_squeeze",         "Bollinger Band squeeze flag (BB_width < 20th percentile)"),
    "OBV_slope_20d":      _tech("OBV_slope_20d",      "OBV 20-day linear regression slope", ["close","volume"]),
    "CMF_20_zscore":      _tech("CMF_20_zscore",      "CMF z-score vs 60-day history", ["high","low","close","volume"]),
    "Price_open_gap":     _tech("Price_open_gap",     "Open gap: (open - prev_close) / prev_close"),
    "High_low_spread":    _tech("High_low_spread",    "Daily high-low spread as % of close", ["high","low","close"]),
    "Upper_shadow":       _tech("Upper_shadow",       "Candlestick upper shadow ratio", ["high","low","close"]),
    "Lower_shadow":       _tech("Lower_shadow",       "Candlestick lower shadow ratio", ["high","low","close"]),
    "Body_ratio":         _tech("Body_ratio",         "Candlestick body ratio (abs(close-open)/ATR)", ["high","low","close"]),
    "Overnight_gap_20d":  _tech("Overnight_gap_20d",  "20-day average overnight gap magnitude"),
    "Intraday_range_avg": _tech("Intraday_range_avg",  "20-day average intraday high-low range / close", ["high","low","close"]),
}

assert len(INDICATOR_REGISTRY) == 334, f"Expected 334 indicators, got {len(INDICATOR_REGISTRY)}"
