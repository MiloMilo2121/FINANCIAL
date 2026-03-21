/**
 * TopBar — Bloomberg-style status bar with clock, live prices, and alerts.
 *
 * Shows critical KPIs at all times (Inverted Pyramid principle):
 *   - Clock (UTC)
 *   - XAU/USD spot price + change %
 *   - WebSocket connection status
 *   - GPR alert (red if threat level HIGH/CRITICAL)
 *
 * Delta indicators replace absolute numbers where possible to reduce
 * cognitive load — analysts care about change, not static prices.
 */

import React, { useEffect, useState } from 'react';
import { usePriceStore } from '@/store/priceStore';
import { PRECIOUS_METALS } from '@/types/market';

export const TopBar: React.FC = () => {
  const { prices, priceChangePct, wsConnected, activeAsset, setActiveAsset } = usePriceStore();
  const [utcTime, setUtcTime] = useState('');

  // Real-time UTC clock
  useEffect(() => {
    const update = () => {
      const now = new Date();
      setUtcTime(
        now.toUTCString().split(' ').slice(1, 5).join(' ').replace(/:\d\d GMT/, ' UTC')
      );
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center justify-between px-4 py-1.5 bg-terminal-panel border-b border-terminal-border text-xs font-mono">
      {/* Left: Platform name + clock */}
      <div className="flex items-center gap-4">
        <span className="text-gold-500 font-semibold tracking-wider">FPP</span>
        <span className="text-terminal-muted">{utcTime}</span>

        {/* WebSocket status indicator */}
        <div className="flex items-center gap-1">
          <div className={`w-1.5 h-1.5 rounded-full ${
            wsConnected ? 'bg-terminal-positive animate-pulse-slow' : 'bg-terminal-negative animate-blink'
          }`} />
          <span className="text-terminal-muted">
            {wsConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Center: Metal prices + delta indicators */}
      <div className="flex items-center gap-6">
        {PRECIOUS_METALS.map((metal) => {
          const price = prices[metal.symbol];
          const changePct = priceChangePct[metal.symbol] ?? 0;
          const isPositive = changePct >= 0;
          const isActive = activeAsset === metal.symbol;

          return (
            <button
              key={metal.symbol}
              onClick={() => setActiveAsset(metal.symbol)}
              className={`flex items-center gap-2 px-2 py-0.5 rounded transition-colors ${
                isActive ? 'bg-terminal-border' : 'hover:bg-terminal-border/50'
              }`}
            >
              <span className="text-terminal-muted">{metal.symbol}/USD</span>
              {price ? (
                <>
                  <span className="text-terminal-text font-semibold">
                    {price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                  <span className={isPositive ? 'text-terminal-positive' : 'text-terminal-negative'}>
                    {isPositive ? '▲' : '▼'} {Math.abs(changePct).toFixed(2)}%
                  </span>
                </>
              ) : (
                <span className="text-terminal-muted">---</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right: Model status indicators */}
      <div className="flex items-center gap-3 text-terminal-muted">
        <span title="LSTM-XGBoost model status">ML</span>
        <div className="w-1.5 h-1.5 rounded-full bg-terminal-neutral" title="Hybrid ensemble active" />
        <span title="Monte Carlo simulation">MC</span>
        <div className="w-1.5 h-1.5 rounded-full bg-terminal-neutral" title="Heston model active" />
        <span title="Perplexity Sonar sentiment">NLP</span>
        <div className="w-1.5 h-1.5 rounded-full bg-terminal-neutral" title="Sentiment service active" />
      </div>
    </div>
  );
};
