/**
 * Core market data types for the Financial Projection Platform.
 * Mirrors the Pydantic schemas from the backend services.
 */

export interface OHLCVBar {
  time: number;   // Unix timestamp (seconds)
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface TickData {
  asset: string;
  price: number;
  timestamp: number;
  bid?: number;
  ask?: number;
  source: string;
}

export type AssetClass = 'metal' | 'fx' | 'equity' | 'macro' | 'alternative' | 'news';

export interface MarketEvent {
  event_id: string;
  timestamp: string;
  source: string;
  asset: string;
  asset_class: AssetClass;
  price_usd?: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  currency: string;
  metadata: Record<string, unknown>;
}

/** TradingView Datafeed API - Symbol info */
export interface SymbolInfo {
  name: string;
  ticker: string;
  description: string;
  type: string;
  session: string;
  exchange: string;
  listed_exchange: string;
  timezone: string;
  format: 'price' | 'volume';
  pricescale: number;
  minmov: number;
  has_intraday: boolean;
  has_daily: boolean;
  supported_resolutions: string[];
  data_status: 'streaming' | 'endofday' | 'pulsed' | 'delayed_streaming';
}

/** TradingView Marks API - Geopolitical event marks */
export interface ChartMark {
  id: string;
  time: number;           // Unix timestamp
  color: 'red' | 'green' | 'blue' | 'yellow';
  text: string;           // Tooltip content
  label: string;          // Short label on chart
  labelFontColor: string;
  minSize: number;
}

/** Asset metadata for display */
export interface AssetMetadata {
  symbol: string;
  name: string;
  unit: string;           // e.g. "USD/troy oz"
  icon: string;
}

export const PRECIOUS_METALS: AssetMetadata[] = [
  { symbol: 'XAU', name: 'Gold', unit: 'USD/troy oz', icon: '🏅' },
  { symbol: 'XAG', name: 'Silver', unit: 'USD/troy oz', icon: '⬜' },
  { symbol: 'XPT', name: 'Platinum', unit: 'USD/troy oz', icon: '🔷' },
  { symbol: 'XPD', name: 'Palladium', unit: 'USD/troy oz', icon: '⬡' },
];
