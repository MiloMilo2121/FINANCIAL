/**
 * App root — initializes WebSocket, periodic projections refresh,
 * and renders the Bloomberg Terminal-inspired layout.
 */

import React, { useEffect } from 'react';
import { TerminalLayout } from '@/components/layout/TerminalLayout';
import { useWebSocket } from '@/hooks/useWebSocket';
import { usePriceStore } from '@/store/priceStore';
import { useProjectionStore } from '@/store/projectionStore';
import { runMonteCarlo, getPrediction } from '@/api/projections';

export const App: React.FC = () => {
  const { activeAsset, prices, bars } = usePriceStore();
  const {
    setMonteCarlo,
    setPrediction,
    setLoadingMonteCarlo,
    setLoadingPrediction,
    setMonteCarloError,
    setPredictionError,
  } = useProjectionStore();

  // Connect WebSocket for real-time price ticks
  useWebSocket(activeAsset);

  // Run ML projections when price history is available
  useEffect(() => {
    if (bars.length < 60) return;

    const priceHistory = bars.map((b) => b.close);
    const currentPrice = priceHistory[priceHistory.length - 1];

    // Run Monte Carlo simulation
    setLoadingMonteCarlo(true);
    runMonteCarlo({
      asset: activeAsset,
      currentPrice,
      historicalPrices: priceHistory,
      nPaths: 10000,
      horizonDays: 30,
    })
      .then(setMonteCarlo)
      .catch((err) => setMonteCarloError(String(err)))
      .finally(() => setLoadingMonteCarlo(false));

    // Run LSTM-XGBoost prediction
    setLoadingPrediction(true);
    getPrediction({
      asset: activeAsset,
      priceHistory,
      forecastDays: 5,
    })
      .then(setPrediction)
      .catch((err) => setPredictionError(String(err)))
      .finally(() => setLoadingPrediction(false));
  }, [activeAsset, bars.length]);  // Re-run when asset changes or new bars arrive

  return <TerminalLayout />;
};

export default App;
