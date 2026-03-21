import { api } from './client';
import type { SentimentResponse } from '@/types/sentiment';
import type { ChartMark } from '@/types/market';

export async function analyzeSentiment(params: {
  asset: string;
  context?: string;
  timeHorizon?: 'short' | 'medium' | 'long';
  currentPrice?: number;
}): Promise<SentimentResponse> {
  return api.post<SentimentResponse>('/sentiment/analyze', {
    asset: params.asset,
    context: params.context ?? '',
    time_horizon: params.timeHorizon ?? 'medium',
    current_price: params.currentPrice,
  });
}

export async function getGeopoliticalMarks(
  asset: string,
  fromTs?: number,
  toTs?: number,
): Promise<{ marks: ChartMark[] }> {
  const params = new URLSearchParams();
  if (fromTs) params.set('from_ts', String(fromTs));
  if (toTs) params.set('to_ts', String(toTs));
  const query = params.toString() ? `?${params}` : '';
  return api.get<{ marks: ChartMark[] }>(`/sentiment/marks/${asset}${query}`);
}
