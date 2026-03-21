/**
 * Sentiment analysis types matching the Pydantic SentimentResult schema.
 */

export type SentimentDirection = 'bullish' | 'bearish' | 'neutral';
export type ThreatLevel = 0 | 1 | 2 | 3 | 4;

export interface AssetSentiment {
  asset: string;
  sentiment_score: number;      // -1.0 to 1.0
  direction: SentimentDirection;
  confidence: number;           // 0.0 to 1.0
  key_drivers: string[];
  time_horizon: 'short' | 'medium' | 'long';
}

export interface GeopoliticalRisk {
  threat_level: ThreatLevel;
  primary_risk_factors: string[];
  affected_regions: string[];
  gold_impact_direction: SentimentDirection;
  gold_impact_magnitude: number;
}

export interface MarketPositioning {
  put_call_ratio: number | null;
  institutional_flow_direction: SentimentDirection | null;
  etf_flow_usd_billions: number | null;
  comex_net_long_change: number | null;
}

export interface SentimentResult {
  asset_sentiment: AssetSentiment;
  geopolitical_risk: GeopoliticalRisk;
  market_positioning: MarketPositioning;
  macro_context: string;
  citations: string[];
  fact_check_confidence: number;
  analysis_timestamp: string;
}

export interface MLFeatures {
  sentiment_score: number;
  sentiment_confidence: number;
  geopolitical_threat_level: number;
  gold_impact_magnitude: number;
  fact_check_confidence: number;
  institutional_flow_bullish: number;   // 1.0=bullish, -1.0=bearish, 0.0=neutral
}

export interface SentimentResponse {
  sentiment: SentimentResult;
  ml_features: MLFeatures;
}

/** Direction display helpers */
export const DIRECTION_CONFIG: Record<SentimentDirection, {
  color: string;
  label: string;
  icon: string;
}> = {
  bullish: { color: 'text-terminal-positive', label: 'BULLISH', icon: '▲' },
  bearish: { color: 'text-terminal-negative', label: 'BEARISH', icon: '▼' },
  neutral: { color: 'text-terminal-neutral', label: 'NEUTRAL', icon: '◆' },
};

export const THREAT_LABELS: Record<ThreatLevel, { label: string; color: string }> = {
  0: { label: 'NONE', color: 'text-terminal-muted' },
  1: { label: 'LOW', color: 'text-terminal-neutral' },
  2: { label: 'MEDIUM', color: 'text-terminal-warning' },
  3: { label: 'HIGH', color: 'text-terminal-negative' },
  4: { label: 'CRITICAL', color: 'text-terminal-critical' },
};
