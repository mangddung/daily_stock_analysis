import type { UiLanguage } from '../i18n/uiText';

export const UI_LANGUAGE_STORAGE_KEY = 'dsa.uiLanguage';
/** Request header read by the backend (src/ui_language.py) to localize generated text. */
export const UI_LANGUAGE_HEADER = 'X-DSA-UI-Language';

export function normalizeUiLanguage(value?: string | null): UiLanguage | null {
  if (value === 'zh' || value === 'en' || value === 'ko') {
    return value;
  }
  return null;
}

function getStoredUiLanguage(storage?: Storage | null): UiLanguage | null {
  if (!storage) {
    return null;
  }

  try {
    return normalizeUiLanguage(storage.getItem(UI_LANGUAGE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function getUiLanguageStorage(): Storage | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function persistUiLanguage(storage: Storage | null, language: UiLanguage): void {
  if (!storage) {
    return;
  }

  try {
    storage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Ignore storage failures; in-memory language still updates.
  }
}

function getBrowserUiLanguage(navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null): UiLanguage {
  const languageCandidates = [
    ...(Array.isArray(navigatorLike?.languages) ? navigatorLike?.languages ?? [] : []),
    navigatorLike?.language,
  ].filter((language): language is string => Boolean(language));

  for (const candidate of languageCandidates) {
    const normalized = candidate.toLowerCase();
    if (normalized.startsWith('zh')) {
      return 'zh';
    }
    if (normalized.startsWith('en')) {
      return 'en';
    }
    if (normalized.startsWith('ko')) {
      return 'ko';
    }
  }

  return 'zh';
}

export function resolveInitialUiLanguage({
  storage,
  navigatorLike,
}: {
  storage?: Storage | null;
  navigatorLike?: Pick<Navigator, 'language' | 'languages'> | null;
} = {}): UiLanguage {
  const stored = getStoredUiLanguage(storage);
  if (stored) {
    return stored;
  }

  return getBrowserUiLanguage(navigatorLike);
}

export function getRuntimeInitialLanguage(): UiLanguage {
  if (typeof window === 'undefined') {
    return 'zh';
  }

  return resolveInitialUiLanguage({
    storage: getUiLanguageStorage(),
    navigatorLike: window.navigator,
  });
}

let activeUiLanguage: UiLanguage | null = null;

/** Called by UiLanguageProvider so code outside React (API error parsing, stores) follows the toggle. */
export function setActiveUiLanguage(language: UiLanguage): void {
  activeUiLanguage = language;
}

export function getActiveUiLanguage(): UiLanguage {
  return activeUiLanguage ?? getStoredUiLanguage(getUiLanguageStorage()) ?? 'zh';
}

const UI_LOCALES: Record<UiLanguage, string> = { zh: 'zh-CN', en: 'en-US', ko: 'ko-KR' };

/** BCP 47 locale for Intl/toLocale* date and number formatting in the given UI language. */
export function getUiLocale(language: UiLanguage): string {
  return UI_LOCALES[language];
}
