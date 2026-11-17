import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import NotFoundPage from '../NotFoundPage';

describe('NotFoundPage', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('renders English copy when the UI language is English', () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'en');
    render(
      <UiLanguageProvider>
        <MemoryRouter>
          <NotFoundPage />
        </MemoryRouter>
      </UiLanguageProvider>,
    );

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to home' })).toBeInTheDocument();
    expect(document.title).toBe('Page Not Found - DSA');
    expect(document.body.textContent).not.toMatch(/[一-龥]/);
  });
});
