import { describe, expect, test } from 'vitest';
import { formatStockPrice } from '../format';

describe('formatStockPrice', () => {
  test('KR/JP codes quote in whole units with thousands separators', () => {
    expect(formatStockPrice(1183000, '000660.KS')).toBe('1,183,000');
    expect(formatStockPrice(48750.4, '247540.KQ')).toBe('48,750');
    expect(formatStockPrice(3456, '7203.T')).toBe('3,456');
  });

  test('other markets keep two decimals with thousands separators', () => {
    expect(formatStockPrice(1523.6, '600519')).toBe('1,523.60');
    expect(formatStockPrice(211.5, 'AAPL')).toBe('211.50');
    expect(formatStockPrice(12.3)).toBe('12.30');
  });
});
