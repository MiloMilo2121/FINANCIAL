/**
 * useWebSocket — manages WebSocket connection for real-time price feeds.
 * Reconnects automatically on disconnect with exponential backoff.
 */

import { useEffect, useRef, useCallback } from 'react';
import { usePriceStore } from '@/store/priceStore';

const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;

export function useWebSocket(asset: string): void {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const { setPrice, setWsConnected } = usePriceStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_BASE}/prices/${asset}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      reconnectDelay.current = 1000; // Reset backoff on success
    };

    ws.onmessage = (event) => {
      try {
        const tick = JSON.parse(event.data as string);
        if (tick.type === 'tick' && tick.price && tick.asset) {
          setPrice(tick.asset, tick.price);
        }
      } catch {
        // Ignore parse errors
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
      const delay = Math.min(reconnectDelay.current, 30000);
      reconnectDelay.current = delay * 2;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [asset, setPrice, setWsConnected]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      setWsConnected(false);
    };
  }, [connect, setWsConnected]);
}
