import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import { ReportMarkdown } from '../ReportMarkdown';
import type { ReactElement } from 'react';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import type { UiLanguage } from '../../../i18n/uiText';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';

const renderInUiLanguage = (ui: ReactElement, language: UiLanguage) => {
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  return render(<UiLanguageProvider>{ui}</UiLanguageProvider>);
};

vi.mock('../../../api/history', () => ({
  historyApi: {
    getMarkdown: vi.fn(),
  },
}));

describe('ReportMarkdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses localized copy labels for English reports', async () => {
    vi.mocked(historyApi.getMarkdown).mockResolvedValue('# Full report');

    renderInUiLanguage(
      <ReportMarkdown
        recordId={1}
        stockName="Apple"
        stockCode="AAPL"
        onClose={() => {}}
      />,
      'en',
    );

    expect(await screen.findByRole('button', { name: 'Copy Markdown Source' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy Plain Text' })).toBeInTheDocument();
  });
});
