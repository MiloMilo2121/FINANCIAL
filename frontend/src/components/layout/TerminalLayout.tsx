/**
 * TerminalLayout — Bloomberg Terminal-inspired shell.
 *
 * Layout structure (Inverted Pyramid information hierarchy):
 *   ┌─────────────────────────────────────────────┐
 *   │ TopBar: Clock │ Prices │ Alert indicators    │ ← Strategic (always visible)
 *   ├────────────────────────┬────────────────────┤
 *   │                        │ SentimentPanel      │
 *   │   TradingView Chart    │ ProjectionPanel     │ ← Analytical
 *   │   (LSTM + MC overlays) │ MetalsHeatmap       │
 *   │                        │                     │
 *   └────────────────────────┴────────────────────┘
 *
 * The left panel occupies ~70% of screen width for the chart.
 * Right panel (~30%) contains the intelligence panels.
 * All non-essential information is behind progressive disclosure toggles.
 */

import React from 'react';
import { TopBar } from './TopBar';
import { TradingViewWidget } from '@/components/charts/TradingViewWidget';
import { SentimentPanel } from '@/components/panels/SentimentPanel';
import { ProjectionPanel } from '@/components/panels/ProjectionPanel';
import { MetalsHeatmap } from '@/components/heatmap/MetalsHeatmap';
import { usePriceStore } from '@/store/priceStore';
import { useProjectionStore } from '@/store/projectionStore';

export const TerminalLayout: React.FC = () => {
  const { activeAsset } = usePriceStore();
  const { prediction, monteCarlo, isLoadingPrediction, isLoadingMonteCarlo } = useProjectionStore();

  return (
    <div className="flex flex-col h-screen bg-terminal-bg text-terminal-text font-mono overflow-hidden">
      {/* Top bar: clock, live prices, alert indicators */}
      <TopBar />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chart panel — 70% width */}
        <div className="flex-1 min-w-0 p-2">
          <TradingViewWidget
            asset={activeAsset}
            className="w-full h-full"
          />
        </div>

        {/* Intelligence sidebar — 30% width */}
        <div className="w-80 flex-shrink-0 flex flex-col gap-2 p-2 overflow-y-auto">
          <SentimentPanel
            sentiment={null}  // Populated by useSentiment hook in App.tsx
            isLoading={false}
          />
          <ProjectionPanel
            monteCarlo={monteCarlo}
            prediction={prediction}
            isLoading={isLoadingMonteCarlo}
          />
          <MetalsHeatmap />
        </div>
      </div>
    </div>
  );
};
