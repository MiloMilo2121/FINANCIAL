/**
 * Projection and Monte Carlo types.
 */

export interface PredictionResult {
  asset: string;
  predictions: number[];       // Mean price forecasts per day
  uncertainty_std: number[];   // Standard deviation per day
  model_tier: 'cache' | 'lightweight' | 'hybrid_ensemble' | 'full_multimodal';
  cache_hit: boolean;
  forecast_days: number;
}

export interface MonteCarloPercentileBand {
  timestamp: number;           // Unix timestamp (seconds)
  date: string;                // YYYY-MM-DD
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
}

export interface MonteCarloResult {
  asset: string;
  current_price: number;
  probability_bands: MonteCarloPercentileBand[];
  var_95: {
    var_pct: number;
    var_usd: number;
    expected_shortfall_pct: number;
    expected_shortfall_usd: number;
    confidence_level: number;
  };
  heston_params: {
    S0: number;
    v0: number;
    mu: number;
    kappa: number;
    theta: number;
    sigma_v: number;
    rho: number;
    feller_satisfied: boolean;
  };
  computation_time_ms: number;
  n_paths: number;
}

/** Data for TradingView custom indicator series */
export interface LSTMOverlayData {
  time: number;
  value: number;
  upper: number;   // +1 std dev
  lower: number;   // -1 std dev
}
