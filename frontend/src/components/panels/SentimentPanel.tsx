/**
 * SentimentPanel — displays Perplexity Sonar RAG sentiment analysis.
 *
 * Implements Progressive Disclosure UX:
 * - Top level: sentiment score + direction + key drivers (3 lines)
 * - Expanded: full analysis including geopolitical risk, citations, macro context
 *
 * The cognitive load reduction principle: always-visible summary,
 * details on demand via toggle.
 */

import React, { useState } from 'react';
import type { SentimentResult } from '@/types/sentiment';
import {
  DIRECTION_CONFIG,
  THREAT_LABELS,
} from '@/types/sentiment';

interface SentimentPanelProps {
  sentiment: SentimentResult | null;
  isLoading?: boolean;
}

export const SentimentPanel: React.FC<SentimentPanelProps> = ({
  sentiment,
  isLoading = false,
}) => {
  const [expanded, setExpanded] = useState(false);

  if (isLoading) {
    return (
      <div className="p-3 border border-terminal-border rounded bg-terminal-panel">
        <div className="text-terminal-muted text-xs animate-pulse">
          ANALYZING SENTIMENT VIA PERPLEXITY SONAR...
        </div>
      </div>
    );
  }

  if (!sentiment) {
    return (
      <div className="p-3 border border-terminal-border rounded bg-terminal-panel">
        <div className="text-terminal-muted text-xs">SENTIMENT — NO DATA</div>
      </div>
    );
  }

  const { asset_sentiment, geopolitical_risk, market_positioning, macro_context, citations } = sentiment;
  const dirConfig = DIRECTION_CONFIG[asset_sentiment.direction];
  const threatConfig = THREAT_LABELS[geopolitical_risk.threat_level];

  // Sentiment score bar width as percentage
  const scoreBarWidth = Math.round((asset_sentiment.sentiment_score + 1) / 2 * 100);

  return (
    <div className="border border-terminal-border rounded bg-terminal-panel font-mono text-xs">
      {/* Header — always visible */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-terminal-border">
        <span className="text-terminal-muted uppercase tracking-wider">SENTIMENT</span>
        <div className="flex items-center gap-2">
          <span className={`font-semibold ${dirConfig.color}`}>
            {dirConfig.icon} {dirConfig.label}
          </span>
          <span className="text-terminal-muted">
            {asset_sentiment.asset} / {asset_sentiment.time_horizon.toUpperCase()}
          </span>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-terminal-muted hover:text-terminal-text ml-2"
            title={expanded ? 'Collapse' : 'Expand details'}
          >
            {expanded ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {/* Score bar + primary stats — always visible */}
      <div className="px-3 py-2 space-y-1">
        {/* Sentiment score gradient bar */}
        <div className="flex items-center gap-2">
          <span className="text-terminal-muted w-16">SCORE</span>
          <div className="flex-1 bg-terminal-border rounded-full h-1.5 relative">
            <div
              className={`absolute top-0 h-1.5 rounded-full transition-all duration-500 ${
                asset_sentiment.sentiment_score > 0 ? 'bg-terminal-positive' :
                asset_sentiment.sentiment_score < 0 ? 'bg-terminal-negative' :
                'bg-terminal-neutral'
              }`}
              style={{ left: '50%', width: `${Math.abs(asset_sentiment.sentiment_score) * 50}%`,
                       transform: asset_sentiment.sentiment_score < 0 ? 'translateX(-100%)' : 'none' }}
            />
            <div className="absolute top-0 left-1/2 w-px h-1.5 bg-terminal-muted" />
          </div>
          <span className={`w-12 text-right ${dirConfig.color}`}>
            {asset_sentiment.sentiment_score.toFixed(2)}
          </span>
        </div>

        {/* Confidence */}
        <div className="flex items-center gap-2">
          <span className="text-terminal-muted w-16">CONF</span>
          <div className="flex-1 bg-terminal-border rounded-full h-1">
            <div
              className="bg-terminal-neutral h-1 rounded-full"
              style={{ width: `${asset_sentiment.confidence * 100}%` }}
            />
          </div>
          <span className="text-terminal-text w-12 text-right">
            {(asset_sentiment.confidence * 100).toFixed(0)}%
          </span>
        </div>

        {/* Geopolitical threat — compact */}
        <div className="flex items-center gap-2">
          <span className="text-terminal-muted w-16">GPR RISK</span>
          <span className={`font-semibold ${threatConfig.color}`}>
            {threatConfig.label}
          </span>
          <span className="text-terminal-muted">
            {geopolitical_risk.gold_impact_direction.toUpperCase()} impact
          </span>
        </div>

        {/* Key drivers — top 3 always visible */}
        {asset_sentiment.key_drivers.slice(0, 3).map((driver, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-terminal-muted">•</span>
            <span className="text-terminal-text truncate">{driver}</span>
          </div>
        ))}
      </div>

      {/* Progressive disclosure: expanded details */}
      {expanded && (
        <div className="px-3 py-2 border-t border-terminal-border space-y-3">
          {/* Macro context */}
          <div>
            <div className="text-terminal-muted uppercase mb-1">MACRO CONTEXT</div>
            <p className="text-terminal-text leading-relaxed">{macro_context}</p>
          </div>

          {/* Market positioning */}
          <div>
            <div className="text-terminal-muted uppercase mb-1">POSITIONING</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {market_positioning.put_call_ratio && (
                <>
                  <span className="text-terminal-muted">PUT/CALL</span>
                  <span>{market_positioning.put_call_ratio.toFixed(2)}</span>
                </>
              )}
              {market_positioning.etf_flow_usd_billions && (
                <>
                  <span className="text-terminal-muted">ETF FLOW</span>
                  <span className={market_positioning.etf_flow_usd_billions > 0
                    ? 'text-terminal-positive' : 'text-terminal-negative'}>
                    {market_positioning.etf_flow_usd_billions > 0 ? '+' : ''}
                    {market_positioning.etf_flow_usd_billions.toFixed(1)}B USD
                  </span>
                </>
              )}
            </div>
          </div>

          {/* GPR details */}
          <div>
            <div className="text-terminal-muted uppercase mb-1">GEOPOLITICAL FACTORS</div>
            {geopolitical_risk.primary_risk_factors.map((factor, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-terminal-warning">⚠</span>
                <span>{factor}</span>
              </div>
            ))}
          </div>

          {/* Citations */}
          <div>
            <div className="text-terminal-muted uppercase mb-1">
              SOURCES ({citations.length}) — FACT-CHECK: {(sentiment.fact_check_confidence * 100).toFixed(0)}%
            </div>
            {citations.map((cite, i) => (
              <div key={i} className="text-terminal-neutral truncate">
                {cite}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
