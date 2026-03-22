"""Feature Registry — 175 IndicatorMeta definitions.

Every indicator in the system is registered here with full metadata.
INDICATOR_REGISTRY is the single source of truth for feature ordering,
sourcing, and documentation. The FeaturePipeline uses this registry to
build its output vector (always in registration order).
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
}

assert len(INDICATOR_REGISTRY) == 175, f"Expected 175 indicators, got {len(INDICATOR_REGISTRY)}"
