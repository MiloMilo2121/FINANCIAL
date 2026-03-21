/**
 * MetalsHeatmap — sector rotation visualization for precious metals.
 *
 * Displays all tracked metals and gold-correlated equities as color-coded
 * cells, allowing instant identification of capital flow direction.
 *
 * Color encoding (accessibility-safe, no red/green):
 *   - Strong gains: terminal-positive (green, #00c851)
 *   - Strong losses: terminal-negative (red, #ff3547)
 *   - Neutral: terminal-muted (gray, #666666)
 *
 * Layout follows the "Visual Hierarchy" UX principle:
 * larger cells = more significant assets (gold > silver > mining equities).
 */

import React from 'react';
import { usePriceStore } from '@/store/priceStore';

interface HeatmapCell {
  symbol: string;
  name: string;
  category: 'metal' | 'etf' | 'miner';
  size: 'large' | 'medium' | 'small';
}

const HEATMAP_CELLS: HeatmapCell[] = [
  { symbol: 'XAU', name: 'GOLD', category: 'metal', size: 'large' },
  { symbol: 'XAG', name: 'SILVER', category: 'metal', size: 'medium' },
  { symbol: 'XPT', name: 'PLATINUM', category: 'metal', size: 'medium' },
  { symbol: 'XPD', name: 'PALLADIUM', category: 'metal', size: 'medium' },
  { symbol: 'GLD', name: 'SPDR GLD', category: 'etf', size: 'small' },
  { symbol: 'GOLD', name: 'BARRICK', category: 'miner', size: 'small' },
  { symbol: 'NEM', name: 'NEWMONT', category: 'miner', size: 'small' },
  { symbol: 'AEM', name: 'AGNICO', category: 'miner', size: 'small' },
  { symbol: 'WPM', name: 'WHEATON', category: 'miner', size: 'small' },
  { symbol: 'FNV', name: 'FRANCO-NEV', category: 'miner', size: 'small' },
];

const SIZE_CLASSES = {
  large: 'col-span-2 row-span-2 h-24',
  medium: 'col-span-1 row-span-1 h-12',
  small: 'col-span-1 h-10',
};

function getColorClass(changePct: number): string {
  if (changePct > 2) return 'bg-green-900 text-terminal-positive';
  if (changePct > 0.5) return 'bg-green-950 text-terminal-positive';
  if (changePct > -0.5) return 'bg-terminal-panel text-terminal-muted';
  if (changePct > -2) return 'bg-red-950 text-terminal-negative';
  return 'bg-red-900 text-terminal-negative';
}

export const MetalsHeatmap: React.FC = () => {
  const { prices, priceChangePct } = usePriceStore();

  return (
    <div className="border border-terminal-border rounded bg-terminal-panel font-mono text-xs">
      <div className="px-3 py-2 border-b border-terminal-border text-terminal-muted uppercase tracking-wider">
        MARKET HEATMAP
      </div>
      <div className="p-2 grid grid-cols-4 gap-1 auto-rows-auto">
        {HEATMAP_CELLS.map((cell) => {
          const changePct = priceChangePct[cell.symbol] ?? 0;
          const price = prices[cell.symbol];
          const colorClass = getColorClass(changePct);

          return (
            <div
              key={cell.symbol}
              className={`
                ${SIZE_CLASSES[cell.size]}
                ${colorClass}
                flex flex-col items-center justify-center
                border border-terminal-border rounded cursor-pointer
                hover:opacity-80 transition-opacity duration-150
                p-1
              `}
              title={`${cell.name} — ${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`}
            >
              <div className="font-semibold">{cell.symbol}</div>
              <div className="opacity-70">{cell.name}</div>
              {cell.size !== 'small' && price && (
                <div className="opacity-90">${price.toLocaleString()}</div>
              )}
              <div className="font-bold">
                {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
