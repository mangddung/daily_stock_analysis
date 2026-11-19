import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { TriangleAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { systemConfigApi, type RuntimeAlertsResponse } from '../../api/systemConfig';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { UiTextKey } from '../../i18n/uiText';
import { cn } from '../../utils/cn';
import { formatDateTime } from '../../utils/format';

const POLL_INTERVAL_MS = 60_000;

const KIND_LABEL_KEYS: Record<string, UiTextKey> = {
  llm: 'layout.rateLimitKindLlm',
  market: 'layout.rateLimitKindMarket',
  news: 'layout.rateLimitKindNews',
  disclosure: 'layout.rateLimitKindDisclosure',
};

type RuntimeAlertIndicatorProps = {
  /** floating: mobile top bar; rail: desktop sidebar (panel opens to the side); drawer: mobile nav drawer. */
  variant?: 'floating' | 'rail' | 'drawer';
  collapsed?: boolean;
};

const PANEL_PLACEMENT = {
  floating: 'right-0 top-full mt-2',
  rail: 'left-full bottom-0 ml-3',
  drawer: 'left-0 bottom-full mb-2',
} as const;

/** Shell-wide badge for upstream rate limits (LLM / market data / news) and disclosure-source failures; hidden when healthy. */
export const RuntimeAlertIndicator: React.FC<RuntimeAlertIndicatorProps> = ({ variant = 'floating', collapsed = false }) => {
  const { t } = useUiLanguage();
  const navigate = useNavigate();
  const [data, setData] = useState<RuntimeAlertsResponse | null>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      systemConfigApi.getRuntimeAlerts()
        .then((response) => {
          if (!cancelled) setData(response);
        })
        // An unreachable alert feed must never surface as its own error.
        .catch(() => undefined);
    };
    load();
    const timer = window.setInterval(load, POLL_INTERVAL_MS);
    window.addEventListener('focus', load);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener('focus', load);
    };
  }, []);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  const alerts = data?.alerts ?? [];
  if (alerts.length === 0) {
    return null;
  }

  return (
    <div className={cn('relative', variant === 'floating' ? '' : 'w-full')} ref={containerRef}>
      <button
        type="button"
        className={cn(
          'inline-flex items-center justify-center gap-1.5 rounded-xl border border-warning/40 bg-warning/10 font-medium text-warning transition-colors hover:bg-warning/15',
          variant === 'floating'
            ? 'h-10 px-3 text-sm shadow-soft-card backdrop-blur-md'
            : 'h-9 w-full px-2 text-xs',
          open ? 'border-warning/70' : '',
        )}
        aria-label={t('layout.rateLimitEntry')}
        aria-expanded={open}
        aria-haspopup="dialog"
        data-testid="runtime-alert-indicator"
        onClick={() => setOpen((current) => !current)}
      >
        <TriangleAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span className="truncate">
          {collapsed ? alerts.length : t('layout.rateLimitBadge', { count: alerts.length })}
        </span>
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t('layout.rateLimitEntry')}
          className={cn(
            'absolute z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-2xl border border-border/70 bg-card/95 p-3 shadow-soft-card backdrop-blur-xl',
            PANEL_PLACEMENT[variant],
          )}
        >
          <p className="text-sm font-semibold text-foreground">{t('layout.rateLimitEntry')}</p>
          <p className="mt-1 text-xs leading-5 text-secondary-text">
            {t('layout.rateLimitHint', { minutes: data?.ttlMinutes ?? 15 })}
          </p>
          <ul className="mt-3 space-y-2">
            {alerts.map((alert) => (
              <li key={`${alert.kind}:${alert.source}`} className="rounded-xl border border-border/60 bg-background/40 px-3 py-2">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="min-w-0 truncate font-medium text-foreground">
                    {KIND_LABEL_KEYS[alert.kind] ? t(KIND_LABEL_KEYS[alert.kind]) : alert.kind} · {alert.source}
                  </span>
                  <span className="shrink-0 text-muted-text">
                    {formatDateTime(alert.lastAt)} · {t('layout.rateLimitCount', { count: alert.count })}
                  </span>
                </div>
                {alert.message ? (
                  <p className="mt-1 line-clamp-2 break-all text-[11px] leading-4 text-secondary-text" title={alert.message}>
                    {alert.message}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-3 text-xs text-secondary-text underline-offset-2 transition-colors hover:text-foreground hover:underline"
            onClick={() => {
              setOpen(false);
              navigate('/data');
            }}
          >
            {t('layout.rateLimitOpenDataCenter')}
          </button>
        </div>
      ) : null}
    </div>
  );
};
