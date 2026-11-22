import type { SystemConfigItem } from '../types/systemConfig';

const STORAGE_KEY = 'priceColorScheme';

// Mirrors MARKET_REVIEW_COLOR_SCHEME onto <html data-price-colors>, which
// index.css uses to map --home-price-up/down. Cached so index.html can apply
// it before the first paint.
export function applyPriceColorScheme(items: SystemConfigItem[]): void {
  const value = items.find((item) => item.key === 'MARKET_REVIEW_COLOR_SCHEME')?.value;
  const scheme = value === 'red_up' ? 'red_up' : 'green_up';
  document.documentElement.dataset.priceColors = scheme;
  try {
    localStorage.setItem(STORAGE_KEY, scheme);
  } catch {
    // Storage may be unavailable; the attribute alone still applies.
  }
}
