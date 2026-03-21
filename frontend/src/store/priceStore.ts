/**
 * Zustand store for real-time price state.
 * Updated by WebSocket ticks from the API Gateway.
 */

import { create } from 'zustand';
import type { OHLCVBar, TickData } from '@/types/market';

interface PriceState {
  // Current prices by asset
  prices: Record<string, number>;
  // Price change % since last close
  priceChangePct: Record<string, number>;
  // Recent OHLCV bars for the active asset
  bars: OHLCVBar[];
  // WebSocket connection status
  wsConnected: boolean;
  // Active asset being displayed
  activeAsset: string;

  // Actions
  setPrice: (asset: string, price: number, prevClose?: number) => void;
  setBars: (bars: OHLCVBar[]) => void;
  setWsConnected: (connected: boolean) => void;
  setActiveAsset: (asset: string) => void;
  appendBar: (bar: OHLCVBar) => void;
}

export const usePriceStore = create<PriceState>((set) => ({
  prices: {},
  priceChangePct: {},
  bars: [],
  wsConnected: false,
  activeAsset: 'XAU',

  setPrice: (asset, price, prevClose) =>
    set((state) => ({
      prices: { ...state.prices, [asset]: price },
      priceChangePct: {
        ...state.priceChangePct,
        [asset]: prevClose ? ((price - prevClose) / prevClose) * 100 : 0,
      },
    })),

  setBars: (bars) => set({ bars }),

  setWsConnected: (wsConnected) => set({ wsConnected }),

  setActiveAsset: (activeAsset) => set({ activeAsset, bars: [] }),

  appendBar: (bar) =>
    set((state) => {
      const bars = [...state.bars];
      const last = bars[bars.length - 1];
      if (last && last.time === bar.time) {
        // Update current bar
        bars[bars.length - 1] = bar;
      } else {
        bars.push(bar);
      }
      return { bars };
    }),
}));
