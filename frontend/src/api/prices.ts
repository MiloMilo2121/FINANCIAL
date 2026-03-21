import { api } from './client';
import type { OHLCVBar } from '@/types/market';

export async function getBars(params: {
  asset: string;
  resolution: string;
  from: number;
  to: number;
}): Promise<{ s: string; t: number[]; o: number[]; h: number[]; l: number[]; c: number[]; v: number[] }> {
  return api.get(
    `/prices/${params.asset}/bars?resolution=${params.resolution}&from=${params.from}&to=${params.to}`
  );
}

export async function getLatestPrice(asset: string): Promise<{
  asset: string;
  price_usd: number | null;
  timestamp: string | null;
  sources: string[];
}> {
  return api.get(`/prices/${asset}/latest`);
}
