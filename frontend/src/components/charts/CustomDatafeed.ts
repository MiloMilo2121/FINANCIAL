/**
 * TradingView Advanced Charts — Custom Datafeed API implementation.
 *
 * Implements the full IDatafeedChartApi interface, connecting TradingView
 * to the Financial Projection Platform backend:
 *   - getBars()        → REST /api/prices/{asset}/bars
 *   - subscribeBars()  → WebSocket /ws/prices/{asset}
 *   - getMarks()       → REST /api/sentiment/marks/{asset} (geopolitical events)
 *
 * This is the critical integration point: if this file is incorrect,
 * no chart feature will work. TypeScript strict mode enforces the
 * TradingView contract at compile time.
 *
 * Note: TradingView Charting Library (not Lightweight Charts) is required
 * for the full Datafeed API. This implementation targets the charting_library
 * package (requires TradingView commercial license).
 *
 * For the open-source lightweight-charts package: a simplified version
 * without the full Datafeed API is used in TradingViewWidget.tsx.
 */

import { getBars as apiBars } from '@/api/prices';
import { getGeopoliticalMarks } from '@/api/sentiment';
import type { OHLCVBar, ChartMark, SymbolInfo } from '@/types/market';

// Supported resolutions mapped to API interval strings
const RESOLUTION_MAP: Record<string, string> = {
  '1': '1min',
  '5': '5min',
  '15': '15min',
  '60': '1h',
  '240': '4h',
  'D': '1d',
  'W': '1w',
  'M': '1M',
};

const SUPPORTED_RESOLUTIONS = Object.keys(RESOLUTION_MAP);

function buildSymbolInfo(ticker: string): SymbolInfo {
  return {
    name: ticker,
    ticker,
    description: `${ticker}/USD Spot Price`,
    type: 'commodity',
    session: '24x7',
    exchange: 'LBMA',
    listed_exchange: 'LBMA',
    timezone: 'Etc/UTC',
    format: 'price',
    pricescale: 100,
    minmov: 1,
    has_intraday: true,
    has_daily: true,
    supported_resolutions: SUPPORTED_RESOLUTIONS,
    data_status: 'streaming',
  };
}

type BarsCallback = (bars: OHLCVBar[], meta: { noData: boolean }) => void;
type ResolveCallback = (symbolInfo: SymbolInfo) => void;
type ErrorCallback = (error: string) => void;

interface Subscription {
  asset: string;
  ws: WebSocket;
  callback: (bar: OHLCVBar) => void;
}

const activeSubscriptions = new Map<string, Subscription>();

export const FinancialDatafeed = {
  /**
   * Called by TradingView on initialization.
   * Must call callback(configuration) within a few seconds.
   */
  onReady(callback: (config: unknown) => void): void {
    setTimeout(() =>
      callback({
        supported_resolutions: SUPPORTED_RESOLUTIONS,
        supports_marks: true,
        supports_timescale_marks: true,
        supports_time: true,
      })
    , 0);
  },

  /**
   * Symbol search — called when user types in the symbol search box.
   */
  searchSymbols(
    userInput: string,
    _exchange: string,
    _symbolType: string,
    onResult: (results: unknown[]) => void,
  ): void {
    const metals = ['XAU', 'XAG', 'XPT', 'XPD'];
    const filtered = metals.filter((m) =>
      m.includes(userInput.toUpperCase())
    );
    onResult(
      filtered.map((symbol) => ({
        symbol,
        full_name: `${symbol}/USD`,
        description: buildSymbolInfo(symbol).description,
        type: 'commodity',
      }))
    );
  },

  /**
   * Resolve symbol info for a given ticker.
   * Called before getBars() to get the symbol's configuration.
   */
  resolveSymbol(
    symbolName: string,
    onResolve: ResolveCallback,
    onError: ErrorCallback,
  ): void {
    const ticker = symbolName.replace('/USD', '').toUpperCase();
    const validMetals = ['XAU', 'XAG', 'XPT', 'XPD'];
    if (!validMetals.includes(ticker)) {
      onError(`Unknown symbol: ${symbolName}`);
      return;
    }
    setTimeout(() => onResolve(buildSymbolInfo(ticker)), 0);
  },

  /**
   * Fetch historical OHLCV bars for the given symbol and time range.
   * Called for initial chart load and when user scrolls back in history.
   */
  async getBars(
    symbolInfo: SymbolInfo,
    resolution: string,
    periodParams: { from: number; to: number; firstDataRequest: boolean },
    onResult: BarsCallback,
    onError: ErrorCallback,
  ): Promise<void> {
    try {
      const asset = symbolInfo.ticker.replace('/USD', '');
      const data = await apiBars({
        asset,
        resolution,
        from: periodParams.from,
        to: periodParams.to,
      });

      if (data.s !== 'ok' || !data.t.length) {
        onResult([], { noData: true });
        return;
      }

      const bars: OHLCVBar[] = data.t.map((time, i) => ({
        time,
        open: data.o[i],
        high: data.h[i],
        low: data.l[i],
        close: data.c[i],
        volume: data.v[i],
      }));

      onResult(bars, { noData: false });
    } catch (err) {
      onError(String(err));
    }
  },

  /**
   * Subscribe to real-time bar updates via WebSocket.
   * TradingView calls this after getBars() completes.
   */
  subscribeBars(
    symbolInfo: SymbolInfo,
    _resolution: string,
    onTick: (bar: OHLCVBar) => void,
    subscriberUID: string,
  ): void {
    const asset = symbolInfo.ticker.replace('/USD', '');
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/prices/${asset}`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const tick = JSON.parse(event.data as string);
        if (tick.type === 'tick' && tick.price) {
          const now = Math.floor(Date.now() / 1000);
          onTick({
            time: now,
            open: tick.price,
            high: tick.price,
            low: tick.price,
            close: tick.price,
          });
        }
      } catch {
        // Ignore parse errors
      }
    };

    ws.onerror = () => {
      console.warn(`WebSocket error for ${asset}`);
    };

    activeSubscriptions.set(subscriberUID, { asset, ws, callback: onTick });
  },

  /**
   * Unsubscribe from real-time updates (called when chart resolution changes
   * or symbol changes).
   */
  unsubscribeBars(subscriberUID: string): void {
    const sub = activeSubscriptions.get(subscriberUID);
    if (sub) {
      sub.ws.close();
      activeSubscriptions.delete(subscriberUID);
    }
  },

  /**
   * TradingView Marks API — returns geopolitical event markers.
   * Each mark is displayed as an icon on the chart at the event's timestamp.
   * Hovering shows the Perplexity-generated tooltip text.
   */
  async getMarks(
    symbolInfo: SymbolInfo,
    startDate: number,
    endDate: number,
    onDataCallback: (marks: ChartMark[]) => void,
    _resolution: string,
  ): Promise<void> {
    try {
      const asset = symbolInfo.ticker.replace('/USD', '');
      const { marks } = await getGeopoliticalMarks(asset, startDate, endDate);
      onDataCallback(marks);
    } catch {
      onDataCallback([]);
    }
  },

  /**
   * Server-time sync for TradingView real-time mode.
   */
  getServerTime(callback: (time: number) => void): void {
    callback(Math.floor(Date.now() / 1000));
  },
};
