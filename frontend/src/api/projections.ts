import { api } from './client';
import type { PredictionResult, MonteCarloResult } from '@/types/projection';

export async function getPrediction(params: {
  asset: string;
  priceHistory: number[];
  macroFeatures?: Record<string, number>;
  forecastDays?: number;
  newsSummary?: string;
}): Promise<PredictionResult> {
  return api.post<PredictionResult>('/projections/predict', {
    asset: params.asset,
    price_history: params.priceHistory,
    macro_features: params.macroFeatures ?? {},
    forecast_days: params.forecastDays ?? 5,
    news_summary: params.newsSummary,
  });
}

export async function runMonteCarlo(params: {
  asset: string;
  currentPrice: number;
  historicalPrices: number[];
  nPaths?: number;
  horizonDays?: number;
}): Promise<MonteCarloResult> {
  return api.post<MonteCarloResult>('/projections/simulate', {
    asset: params.asset,
    current_price: params.currentPrice,
    historical_prices: params.historicalPrices,
    n_paths: params.nPaths ?? 10000,
    horizon_days: params.horizonDays ?? 30,
  });
}
