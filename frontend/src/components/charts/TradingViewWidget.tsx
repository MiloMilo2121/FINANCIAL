/**
 * TradingView chart widget using lightweight-charts (open-source).
 *
 * For the full TradingView Advanced Charts with custom Datafeed API
 * (geopolitical marks, custom indicators, etc.), the commercial
 * charting_library package is required. This component uses the
 * open-source lightweight-charts as a development fallback.
 *
 * In production with charting_library:
 * - Replace createChart with new TradingView.widget({ ... datafeed: FinancialDatafeed })
 * - Enable getMarks(), getTimescaleMarks() via FinancialDatafeed
 * - Use custom_indicators_getter for LSTM/Monte Carlo overlays
 */

import React, { useEffect, useRef, useState } from 'react';
import { createChart, type IChartApi, type ISeriesApi, ColorType } from 'lightweight-charts';
import { usePriceStore } from '@/store/priceStore';
import { useUIStore } from '@/store/uiStore';
import { useProjectionStore } from '@/store/projectionStore';
import type { MonteCarloPercentileBand } from '@/types/projection';

interface TradingViewWidgetProps {
  asset?: string;
  className?: string;
}

export const TradingViewWidget: React.FC<TradingViewWidgetProps> = ({
  asset = 'XAU',
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const mcBandsRef = useRef<ISeriesApi<'Line'>[]>([]);

  const { bars } = usePriceStore();
  const { showMonteCarloBands, showLSTMOverlay, chartResolution } = useUIStore();
  const { monteCarlo } = useProjectionStore();

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a0a0a' },
        textColor: '#666666',
      },
      grid: {
        vertLines: { color: '#1e1e1e' },
        horzLines: { color: '#1e1e1e' },
      },
      crosshair: {
        vertLine: { color: '#f0a500', labelBackgroundColor: '#f0a500' },
        horzLine: { color: '#f0a500', labelBackgroundColor: '#f0a500' },
      },
      rightPriceScale: {
        borderColor: '#1e1e1e',
      },
      timeScale: {
        borderColor: '#1e1e1e',
        timeVisible: true,
      },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00c851',
      downColor: '#ff3547',
      borderUpColor: '#00c851',
      borderDownColor: '#ff3547',
      wickUpColor: '#00c851',
      wickDownColor: '#ff3547',
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;

    // Handle resize
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Update bars
  useEffect(() => {
    if (!candleSeriesRef.current || !bars.length) return;
    candleSeriesRef.current.setData(bars);
  }, [bars]);

  // Render Monte Carlo probability bands
  useEffect(() => {
    if (!chartRef.current) return;

    // Remove existing MC band series
    for (const series of mcBandsRef.current) {
      chartRef.current.removeSeries(series);
    }
    mcBandsRef.current = [];

    if (!showMonteCarloBands || !monteCarlo?.probability_bands.length) return;

    const bands = monteCarlo.probability_bands;

    // Render 5 percentile bands with decreasing opacity
    const bandConfigs = [
      { key: 'p50' as keyof MonteCarloPercentileBand, color: '#f0a500', lineWidth: 2, opacity: 0.9 },  // Median — gold
      { key: 'p25' as keyof MonteCarloPercentileBand, color: '#4a90d9', lineWidth: 1, opacity: 0.6 },  // 25th
      { key: 'p75' as keyof MonteCarloPercentileBand, color: '#4a90d9', lineWidth: 1, opacity: 0.6 },  // 75th
      { key: 'p5' as keyof MonteCarloPercentileBand, color: '#666666', lineWidth: 1, opacity: 0.3 },   // 5th
      { key: 'p95' as keyof MonteCarloPercentileBand, color: '#666666', lineWidth: 1, opacity: 0.3 },  // 95th
    ];

    for (const config of bandConfigs) {
      const series = chartRef.current.addLineSeries({
        color: config.color,
        lineWidth: config.lineWidth as 1 | 2 | 3 | 4,
        lineStyle: config.key === 'p50' ? 0 : 1,  // 0=solid, 1=dotted
        priceLineVisible: false,
        lastValueVisible: config.key === 'p50',
      });

      const data = bands.map((b) => ({
        time: b.timestamp as number,
        value: b[config.key] as number,
      }));

      series.setData(data);
      mcBandsRef.current.push(series);
    }
  }, [showMonteCarloBands, monteCarlo]);

  return (
    <div className={`relative ${className}`}>
      <div ref={containerRef} className="w-full h-full" />

      {/* Chart legend overlay */}
      <div className="absolute top-2 left-2 flex gap-3 text-xs font-mono">
        <span className="text-terminal-text font-semibold">{asset}/USD</span>
        <span className="text-terminal-muted">{chartResolution}</span>
        {showMonteCarloBands && monteCarlo && (
          <span className="text-gold-500">MC {monteCarlo.n_paths.toLocaleString()} paths</span>
        )}
        {showLSTMOverlay && (
          <span className="text-terminal-neutral">LSTM</span>
        )}
      </div>
    </div>
  );
};
