import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { marketApi, type MarketClock, type MarketOverview, type MarketQuote, type MarketSession } from '../api/market';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, AppPage, Badge, Card, EmptyState, Loading, PageHeader } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { UiLanguage, UiTextKey, UiTextParams } from '../i18n/uiText';
import { getUiLocale } from '../utils/uiLanguage';
import { cn } from '../utils/cn';

type Translate = (key: UiTextKey, params?: UiTextParams) => string;

const POLL_MS = 3000;

const SESSION_VARIANT: Record<MarketSession, 'success' | 'warning' | 'info' | 'default'> = {
  regular: 'success',
  pre: 'warning',
  post: 'warning',
  break: 'info',
  closed: 'default',
  unknown: 'default',
};

// Index group width by card count; capped at 2 columns below lg so phones keep a 2-column grid.
const INDEX_GROUP_SPAN = {
  1: { outer: 'col-span-1', inner: 'grid-cols-1' },
  2: { outer: 'col-span-2', inner: 'grid-cols-2' },
  3: { outer: 'col-span-2 lg:col-span-3', inner: 'grid-cols-2 lg:grid-cols-3' },
} as const;

function formatDuration(seconds: number, t: Translate): string {
  if (seconds < 60) return t('dashboard.duration.soon');
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? t('dashboard.duration.hm', { hours, minutes }) : t('dashboard.duration.m', { minutes });
}

function formatClock(epochSec: number, locale: string, withDate = false): string {
  return new Intl.DateTimeFormat(locale, {
    ...(withDate ? { month: '2-digit', day: '2-digit', weekday: 'short' } : {}),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(epochSec * 1000);
}

/** "Opens in 3h 12m" style line; a day or more away shows the next open date instead. */
function sessionCountdown(market: MarketClock, nowSec: number, locale: string, t: Translate): string | null {
  if (market.session === 'regular' && market.sessionEndsAt) {
    const key = market.nextSession === 'break' ? 'dashboard.until.break' : 'dashboard.until.close';
    return t(key, { time: formatDuration(market.sessionEndsAt - nowSec, t) });
  }
  if (market.session === 'post' && market.sessionEndsAt) {
    return t('dashboard.until.postEnd', { time: formatDuration(market.sessionEndsAt - nowSec, t) });
  }
  if (!market.nextRegularOpen) return null;
  const wait = market.nextRegularOpen - nowSec;
  return wait >= 86400
    ? t('dashboard.nextOpen', { date: formatClock(market.nextRegularOpen, locale, true) })
    : t('dashboard.until.open', { time: formatDuration(wait, t) });
}

function formatPrice(value: number | null | undefined, language: UiLanguage): string {
  if (value === null || value === undefined) return '-';
  const digits = Math.abs(value) < 10 ? 4 : 2;
  return new Intl.NumberFormat(getUiLocale(language), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

// Korean convention: up is red, down is blue.
function changeClass(value: number | null | undefined): string {
  if (!value) return 'text-secondary-text';
  return value > 0 ? 'text-danger' : 'text-cyan';
}

function formatAge(asOf: number | null | undefined, nowSec: number, language: UiLanguage, t: Translate): string {
  if (!asOf) return '-';
  const age = Math.max(0, nowSec - asOf);
  if (age < 60) return t('dashboard.justNow');
  if (age < 3600) return t('dashboard.minutesAgo', { minutes: Math.floor(age / 60) });
  if (age < 86400) return t('dashboard.hoursAgo', { hours: Math.floor(age / 3600) });
  return new Intl.DateTimeFormat(getUiLocale(language), {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(asOf * 1000));
}

function toParsedError(error: unknown, t: Translate): ParsedApiError {
  const parsed = (error as { parsedError?: ParsedApiError } | null)?.parsedError;
  if (parsed) return parsed;
  const message = error instanceof Error ? error.message : String(error);
  return { title: t('dashboard.error.title'), message, rawMessage: message, category: 'http_error' };
}

const Freshness: React.FC<{ quote: MarketQuote; nowSec: number; language: UiLanguage; t: Translate }> = ({
  quote,
  nowSec,
  language,
  t,
}) => (
  <span className="inline-flex flex-wrap items-center gap-1.5 text-xs text-secondary-text">
    {formatAge(quote.asOf, nowSec, language, t)}
    {/* A closed market's last price is final, so the exchange delay no longer matters. */}
    {quote.delayMinutes && quote.session !== 'closed' ? <Badge variant="warning">{t('dashboard.delayed', { minutes: quote.delayMinutes })}</Badge> : null}
  </span>
);

const QuoteCard: React.FC<{ quote: MarketQuote; nowSec: number; language: UiLanguage; t: Translate }> = ({
  quote,
  nowSec,
  language,
  t,
}) => (
  <Card padding="sm" className="rounded-2xl">
    <p className="truncate text-xs text-secondary-text">{quote.name}</p>
    {quote.price === null ? (
      <p className="mt-2 text-sm text-secondary-text">{t('dashboard.waiting')}</p>
    ) : (
      <>
        <div className="mt-1 flex items-baseline justify-between gap-2">
          <span className="text-xl font-semibold tabular-nums text-foreground">{formatPrice(quote.price, language)}</span>
          <span className={cn('text-sm font-medium tabular-nums', changeClass(quote.changePercent))}>
            {formatPercent(quote.changePercent)}
          </span>
        </div>
        <div className="mt-2">
          <Freshness quote={quote} nowSec={nowSec} language={language} t={t} />
        </div>
      </>
    )}
  </Card>
);

const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h2 className="mb-3 text-sm font-semibold text-foreground">{children}</h2>
);

const DashboardPage: React.FC = () => {
  const { language, t } = useUiLanguage();
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      marketApi.getOverview().then(
        (data) => {
          if (cancelled) return;
          setOverview(data);
          setError(null);
        },
        (err: unknown) => {
          if (!cancelled) setError(toParsedError(err, t));
        },
      );
    void load();
    const poll = window.setInterval(() => {
      if (!document.hidden) void load();
    }, POLL_MS);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      cancelled = true;
      window.clearInterval(poll);
      window.clearInterval(clock);
    };
  }, [t]);

  const nowSec = now / 1000;
  const locale = getUiLocale(language);

  return (
    <AppPage>
      <PageHeader
        title={t('dashboard.title')}
        description={t('dashboard.description')}
        actions={
          overview ? (
            <Badge
              variant={overview.streamConnected ? 'success' : 'default'}
              title={t(overview.streamConnected ? 'dashboard.liveHint' : 'dashboard.snapshotHint')}
            >
              {t(overview.streamConnected ? 'dashboard.live' : 'dashboard.snapshot')}
            </Badge>
          ) : null
        }
      />

      {error ? <ApiErrorAlert error={error} className="mt-4" /> : null}

      {!overview ? (
        error ? null : <Loading className="mt-6" />
      ) : (
        <div className="mt-4 space-y-6">
          <section>
            <SectionTitle>{t('dashboard.markets')}</SectionTitle>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
              {overview.markets.map((market) => {
                const countdown = sessionCountdown(market, nowSec, locale, t);
                return (
                <Card key={market.market} padding="sm" className="rounded-2xl">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-foreground">
                      {t(`dashboard.market.${market.market}` as UiTextKey)}
                    </span>
                    <Badge variant={SESSION_VARIANT[market.session]}>
                      {t(`dashboard.session.${market.session}` as UiTextKey)}
                    </Badge>
                  </div>
                  <p className="mt-2 text-lg font-semibold tabular-nums text-foreground">
                    {new Intl.DateTimeFormat(locale, {
                      timeZone: market.timezone,
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                      hour12: false,
                    }).format(now)}
                  </p>
                  {countdown ? <p className="mt-1 text-xs font-medium text-cyan">{countdown}</p> : null}
                  {market.schedule.length > 0 ? (
                    // Shown in the viewer's own timezone, e.g. US pre-market 18:00 in Korea (17:00 during US DST).
                    <ul className="mt-2 space-y-0.5 border-t border-border/40 pt-2 text-[11px] text-secondary-text">
                      {market.schedule.map((window) => (
                        <li
                          key={`${window.phase}-${window.start}`}
                          className={cn(
                            'flex justify-between gap-2 tabular-nums',
                            nowSec >= window.start && nowSec < window.end ? 'font-medium text-foreground' : '',
                          )}
                        >
                          <span>{t(`dashboard.session.${window.phase}` as UiTextKey)}</span>
                          <span>
                            {formatClock(window.start, locale)}–{formatClock(window.end, locale)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </Card>
                );
              })}
            </div>
          </section>

          <section>
            <SectionTitle>{t('dashboard.indices')}</SectionTitle>
            {/* 4 columns x 2 rows on wide screens; dense flow tucks 1-card markets into gaps (US+JP / KR+HK+CN). */}
            <div className="grid grid-flow-row-dense grid-cols-2 gap-3 lg:grid-cols-4">
              {overview.markets.map((market) => {
                const quotes = overview.indices.filter((quote) => quote.market === market.market);
                if (quotes.length === 0) return null;
                const span = INDEX_GROUP_SPAN[Math.min(quotes.length, 3) as 1 | 2 | 3];
                return (
                  <div key={market.market} className={cn('rounded-2xl border border-border/50 p-2', span.outer)}>
                    <div className="mb-2 flex items-center gap-2 px-1">
                      <span className="text-xs font-medium text-foreground">
                        {t(`dashboard.market.${market.market}` as UiTextKey)}
                      </span>
                      <Badge variant={SESSION_VARIANT[market.session]}>
                        {t(`dashboard.session.${market.session}` as UiTextKey)}
                      </Badge>
                    </div>
                    <div className={cn('grid gap-2', span.inner)}>
                      {quotes.map((quote) => (
                        <QuoteCard key={quote.symbol} quote={quote} nowSec={nowSec} language={language} t={t} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section>
            <SectionTitle>{t('dashboard.fx')}</SectionTitle>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {overview.fx.map((quote) => (
                <QuoteCard key={quote.symbol} quote={quote} nowSec={nowSec} language={language} t={t} />
              ))}
            </div>
          </section>

          <section>
            <SectionTitle>{t('dashboard.watchlist')}</SectionTitle>
            {overview.watchlist.length === 0 ? (
              <EmptyState
                title={t('dashboard.watchlistEmpty')}
                description={t('dashboard.watchlistEmptyHint')}
                action={
                  <Link to="/analysis" className="btn-primary">
                    {t('dashboard.goAnalysis')}
                  </Link>
                }
              />
            ) : (
              <Card padding="none" className="overflow-x-auto rounded-2xl">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-border/50 text-left text-xs text-secondary-text">
                      <th className="px-4 py-3 font-medium">{t('dashboard.col.name')}</th>
                      <th className="px-4 py-3 text-right font-medium">{t('dashboard.col.price')}</th>
                      <th className="px-4 py-3 text-right font-medium">{t('dashboard.col.change')}</th>
                      <th className="px-4 py-3 text-right font-medium">{t('dashboard.col.extended')}</th>
                      <th className="px-4 py-3 font-medium">{t('dashboard.col.asOf')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.watchlist.map((quote) => (
                      <tr key={quote.code} className="border-b border-border/30 last:border-0">
                        <td className="px-4 py-3">
                          <p className="truncate font-medium text-foreground">{quote.name}</p>
                          <p className="text-xs text-secondary-text">{quote.code}</p>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-foreground">
                          {quote.price === null ? t('dashboard.waiting') : formatPrice(quote.price, language)}
                        </td>
                        <td className={cn('px-4 py-3 text-right tabular-nums', changeClass(quote.changePercent))}>
                          {formatPercent(quote.changePercent)}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          {quote.extended ? (
                            <span className="inline-flex items-center gap-1.5">
                              <Badge variant="warning">{t(`dashboard.session.${quote.extended.session}` as UiTextKey)}</Badge>
                              <span className="text-foreground">{formatPrice(quote.extended.price, language)}</span>
                              <span className={changeClass(quote.extended.changePercent)}>
                                {formatPercent(quote.extended.changePercent)}
                              </span>
                            </span>
                          ) : (
                            <span className="text-secondary-text">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <Freshness quote={quote} nowSec={nowSec} language={language} t={t} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </section>
        </div>
      )}
    </AppPage>
  );
};

export default DashboardPage;
