import { afterEach, describe, expect, it } from 'vitest';
import { formatParsedApiError, parseApiError } from '../error';
import { validateStockCode } from '../../utils/validation';
import { setActiveUiLanguage } from '../../utils/uiLanguage';

describe('api error UI language', () => {
  afterEach(() => setActiveUiLanguage('zh'));

  it('keeps Chinese copy by default', () => {
    const parsed = parseApiError({ code: 'ERR_NETWORK', message: 'Network Error' });
    expect(parsed.title).toBe('无法连接到本地服务');
  });

  it('returns English copy when the UI language is English', () => {
    setActiveUiLanguage('en');

    const network = parseApiError({ code: 'ERR_NETWORK', message: 'Network Error' });
    expect(network.title).toBe('Cannot connect to the local service');

    const validation = parseApiError({
      response: { status: 422, data: { detail: { error: 'validation_failed', issues: [{ key: 'LLM_KEY', code: 'missing_api_key' }] } } },
    });
    expect(validation.title).toBe('Configuration needs attention');
    expect(validation.message).toBe('Fix the following settings and try again:\nLLM_KEY: Enter the API key for this channel.');

    const http = parseApiError({ response: { status: 500 } });
    expect(formatParsedApiError(http)).toBe('Request failed: The request did not complete (HTTP 500).');

    expect(validateStockCode('').message).toBe('Enter a stock code');
  });
});
