import apiClient from './index';
import { toCamelCase } from './utils';

/** Quotes take this from Yahoo's market state; market clocks from the exchange calendar ('break' = lunch break). */
export type MarketSession = 'pre' | 'regular' | 'break' | 'post' | 'closed' | 'unknown';

export type SessionWindow = {
  phase: 'pre' | 'regular' | 'break' | 'post';
  /** Epoch seconds. */
  start: number;
  end: number;
};

export type MarketClock = {
  market: string;
  timezone: string;
  session: MarketSession;
  /** Epoch seconds; null while closed. */
  sessionEndsAt: number | null;
  nextSession: SessionWindow['phase'] | null;
  nextSessionStartsAt: number | null;
  nextRegularOpen: number | null;
  /** Phases of the running session, or of the next one while closed. */
  schedule: SessionWindow[];
};

export type ExtendedQuote = {
  session: 'pre' | 'post';
  price: number;
  change: number | null;
  changePercent: number | null;
  asOf: number | null;
};

export type MarketQuote = {
  symbol: string;
  code: string;
  name: string;
  currency: string | null;
  session: MarketSession;
  delayMinutes: number | null;
  price: number | null;
  change: number | null;
  changePercent: number | null;
  /** Epoch seconds of the quoted price. */
  asOf: number | null;
  extended: ExtendedQuote | null;
  source: 'stream' | 'snapshot' | 'none';
  /** Set on indices only (us, kr, jp, hk, cn). */
  market?: string;
};

export type MarketOverview = {
  serverTime: number;
  streamConnected: boolean;
  markets: MarketClock[];
  indices: MarketQuote[];
  fx: MarketQuote[];
  watchlist: MarketQuote[];
};

export const marketApi = {
  async getOverview(): Promise<MarketOverview> {
    const response = await apiClient.get('/api/v1/market/overview');
    return toCamelCase<MarketOverview>(response.data);
  },
};
