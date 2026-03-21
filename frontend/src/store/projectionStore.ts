/**
 * Zustand store for ML projections and Monte Carlo results.
 */

import { create } from 'zustand';
import type { PredictionResult, MonteCarloResult } from '@/types/projection';

interface ProjectionState {
  prediction: PredictionResult | null;
  monteCarlo: MonteCarloResult | null;
  isLoadingPrediction: boolean;
  isLoadingMonteCarlo: boolean;
  predictionError: string | null;
  monteCarloError: string | null;

  setPrediction: (prediction: PredictionResult | null) => void;
  setMonteCarlo: (mc: MonteCarloResult | null) => void;
  setLoadingPrediction: (loading: boolean) => void;
  setLoadingMonteCarlo: (loading: boolean) => void;
  setPredictionError: (error: string | null) => void;
  setMonteCarloError: (error: string | null) => void;
}

export const useProjectionStore = create<ProjectionState>((set) => ({
  prediction: null,
  monteCarlo: null,
  isLoadingPrediction: false,
  isLoadingMonteCarlo: false,
  predictionError: null,
  monteCarloError: null,

  setPrediction: (prediction) => set({ prediction }),
  setMonteCarlo: (monteCarlo) => set({ monteCarlo }),
  setLoadingPrediction: (isLoadingPrediction) => set({ isLoadingPrediction }),
  setLoadingMonteCarlo: (isLoadingMonteCarlo) => set({ isLoadingMonteCarlo }),
  setPredictionError: (predictionError) => set({ predictionError }),
  setMonteCarloError: (monteCarloError) => set({ monteCarloError }),
}));
