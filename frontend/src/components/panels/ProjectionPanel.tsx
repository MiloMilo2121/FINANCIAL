/**
 * ProjectionPanel — displays Monte Carlo probability bands and VaR metrics.
 *
 * Implements Progressive Disclosure: summary stats always visible,
 * Heston parameters hidden behind toggle (for quant researchers only).
 */

import React, { useState } from 'react';
import type { MonteCarloResult } from '@/types/projection';

interface ProjectionPanelProps {
  monteCarlo: MonteCarloResult | null;
  prediction?: { predictions: number[]; uncertainty_std: number[] } | null;
  isLoading?: boolean;
}

export const ProjectionPanel: React.FC<ProjectionPanelProps> = ({
  monteCarlo,
  prediction,
  isLoading = false,
}) => {
  const [showHeston, setShowHeston] = useState(false);

  if (isLoading) {
    return (
      <div className="p-3 border border-terminal-border rounded bg-terminal-panel">
        <div className="text-terminal-muted text-xs animate-pulse">
          RUNNING MONTE CARLO SIMULATION ({(10000).toLocaleString()} PATHS)...
        </div>
      </div>
    );
  }

  if (!monteCarlo) {
    return (
      <div className="p-3 border border-terminal-border rounded bg-terminal-panel">
        <div className="text-terminal-muted text-xs">PROJECTIONS — NO DATA</div>
      </div>
    );
  }

  const { var_95, heston_params, probability_bands, n_paths, computation_time_ms } = monteCarlo;

  // Terminal distribution (last band = 30-day horizon)
  const terminal = probability_bands[probability_bands.length - 1];
  const currentPrice = monteCarlo.current_price;

  const formatPct = (val: number) => `${(val * 100).toFixed(2)}%`;
  const formatDelta = (val: number) => {
    const pct = ((val - currentPrice) / currentPrice) * 100;
    const color = pct >= 0 ? 'text-terminal-positive' : 'text-terminal-negative';
    const sign = pct >= 0 ? '+' : '';
    return <span className={color}>{sign}{pct.toFixed(1)}%</span>;
  };

  return (
    <div className="border border-terminal-border rounded bg-terminal-panel font-mono text-xs">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-terminal-border">
        <span className="text-terminal-muted uppercase tracking-wider">PROJECTIONS</span>
        <div className="flex items-center gap-2 text-terminal-muted">
          <span>{n_paths.toLocaleString()} paths</span>
          <span>{computation_time_ms.toFixed(0)}ms</span>
        </div>
      </div>

      {/* 30-day MC distribution summary */}
      <div className="px-3 py-2 space-y-1">
        <div className="text-terminal-muted uppercase mb-2">30D PROBABILITY DISTRIBUTION</div>

        {terminal && (
          <>
            {[
              { label: 'P95 BULL', val: terminal.p95 },
              { label: 'P75', val: terminal.p75 },
              { label: 'P50 MED', val: terminal.p50 },
              { label: 'P25', val: terminal.p25 },
              { label: 'P05 BEAR', val: terminal.p5 },
            ].map(({ label, val }) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-terminal-muted w-20">{label}</span>
                <span className="text-terminal-text w-20">
                  ${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span className="text-terminal-muted">{formatDelta(val)}</span>
              </div>
            ))}
          </>
        )}

        {/* VaR metrics */}
        <div className="border-t border-terminal-border mt-2 pt-2 space-y-1">
          <div className="text-terminal-muted uppercase mb-1">RISK METRICS (95% CONF.)</div>
          <div className="flex gap-4">
            <div>
              <div className="text-terminal-muted">VaR</div>
              <div className="text-terminal-negative font-semibold">
                -{formatPct(var_95.var_pct)}
              </div>
              <div className="text-terminal-muted">
                -${var_95.var_usd.toFixed(0)}/oz
              </div>
            </div>
            <div>
              <div className="text-terminal-muted">CVaR (ES)</div>
              <div className="text-terminal-negative font-semibold">
                -{formatPct(var_95.expected_shortfall_pct)}
              </div>
              <div className="text-terminal-muted">
                -${var_95.expected_shortfall_usd.toFixed(0)}/oz
              </div>
            </div>
          </div>
        </div>

        {/* LSTM 5-day prediction */}
        {prediction && (
          <div className="border-t border-terminal-border mt-2 pt-2">
            <div className="text-terminal-muted uppercase mb-1">LSTM 5D FORECAST</div>
            <div className="flex gap-2">
              {prediction.predictions.slice(0, 5).map((price, i) => (
                <div key={i} className="text-center">
                  <div className="text-terminal-muted">D+{i + 1}</div>
                  <div className={price >= currentPrice ? 'text-terminal-positive' : 'text-terminal-negative'}>
                    ${price.toFixed(0)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Progressive disclosure: Heston parameters (quant detail) */}
        <button
          onClick={() => setShowHeston(!showHeston)}
          className="w-full text-left text-terminal-muted hover:text-terminal-text mt-2 pt-2 border-t border-terminal-border uppercase"
        >
          HESTON MODEL PARAMS {showHeston ? '▲' : '▼'}
        </button>

        {showHeston && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-1">
            {Object.entries(heston_params).map(([key, val]) => (
              key !== 'feller_satisfied' && (
                <React.Fragment key={key}>
                  <span className="text-terminal-muted uppercase">{key}</span>
                  <span className="text-terminal-text">
                    {typeof val === 'number' ? val.toFixed(4) : String(val)}
                  </span>
                </React.Fragment>
              )
            ))}
            <span className="text-terminal-muted">FELLER</span>
            <span className={heston_params.feller_satisfied ? 'text-terminal-positive' : 'text-terminal-negative'}>
              {heston_params.feller_satisfied ? 'SATISFIED ✓' : 'VIOLATED ✗'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
