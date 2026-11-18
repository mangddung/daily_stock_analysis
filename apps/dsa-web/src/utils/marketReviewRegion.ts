import type { MarketReviewRegion } from '../types/analysis';
import type { UiTextKey } from '../i18n/uiText';

export type { MarketReviewRegion };

export const MARKET_REVIEW_REGION_ORDER: readonly MarketReviewRegion[] = ['cn', 'hk', 'us', 'jp', 'kr', 'tw'];

export function serializeMarketReviewRegions(regions: readonly MarketReviewRegion[]): string {
  const ordered = MARKET_REVIEW_REGION_ORDER.filter((region) => regions.includes(region));
  return ordered.length === MARKET_REVIEW_REGION_ORDER.length ? 'both' : ordered.join(',');
}

const REGION_LABEL_KEYS: Record<MarketReviewRegion, UiTextKey> = {
  cn: 'home.marketRegionCn',
  hk: 'home.marketRegionHk',
  us: 'home.marketRegionUs',
  jp: 'home.marketRegionJp',
  kr: 'home.marketRegionKr',
  tw: 'home.marketRegionTw',
};

/** UI label for a stored review region such as "cn", "cn,us" or "both"; null when unknown/empty. */
export function formatMarketReviewRegionLabel(
  region: string | null | undefined,
  t: (key: UiTextKey) => string,
): string | null {
  const value = (region || '').trim().toLowerCase();
  if (!value) {
    return null;
  }
  const codes = value.split(',').map((code) => code.trim()).filter(Boolean);
  if (value === 'both' || MARKET_REVIEW_REGION_ORDER.every((code) => codes.includes(code))) {
    return t('home.marketRegionAll');
  }
  return codes
    .map((code) => (code in REGION_LABEL_KEYS ? t(REGION_LABEL_KEYS[code as MarketReviewRegion]) : code.toUpperCase()))
    .join(' · ');
}

/** Stored region string ("cn,us", "both") back to a region list; undefined when nothing usable. */
export function parseMarketReviewRegions(region: string | null | undefined): MarketReviewRegion[] | undefined {
  const value = (region || '').trim().toLowerCase();
  if (value === 'both') {
    return [...MARKET_REVIEW_REGION_ORDER];
  }
  const codes = value.split(',').map((code) => code.trim());
  const regions = MARKET_REVIEW_REGION_ORDER.filter((code) => codes.includes(code));
  return regions.length ? regions : undefined;
}

/** Regions the server reviews for a saved MARKET_REVIEW_REGION value; the backend falls back to cn. */
export function resolveServerMarketReviewRegions(region: string | null | undefined): MarketReviewRegion[] {
  return parseMarketReviewRegions(region) ?? ['cn'];
}
