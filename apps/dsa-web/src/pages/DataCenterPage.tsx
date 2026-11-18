import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Database, RefreshCw, Settings2, TriangleAlert, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { Link } from 'react-router-dom';
import { dataCapabilityApi } from '../api/dataCapability';
import { getParsedApiError } from '../api/error';
import { systemConfigApi } from '../api/systemConfig';
import { AppPage, Badge, Button, Card, EmptyState, InlineAlert, Loading, PageHeader } from '../components/common';
import { SettingsField } from '../components/settings/SettingsField';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { DataCapabilityOverview, DatasetQualityStatus, ProviderCapabilityStatus } from '../types/dataCapability';
import type { SystemConfigItem, SystemConfigResponse, SystemConfigUpdateItem } from '../types/systemConfig';
import { cn } from '../utils/cn';
import { formatDateTime } from '../utils/format';
import { formatMarketReviewRegionLabel, resolveServerMarketReviewRegions } from '../utils/marketReviewRegion';

type Status = DatasetQualityStatus | ProviderCapabilityStatus;

/** Web-editable settings that turn a provider on (mirrors DataCapabilityService._is_provider_configured). */
const PROVIDER_CONFIG_KEYS: Record<string, string[]> = {
  tushare: ['TUSHARE_TOKEN'],
  tickplus: ['TICKPLUS_API_KEY'],
  tickflow: ['TICKFLOW_API_KEY'],
  futu: ['FUTU_OPEND_HOST', 'FUTU_OPEND_PORT'],
  longbridge: ['LONGBRIDGE_OAUTH_CLIENT_ID', 'LONGBRIDGE_APP_KEY', 'LONGBRIDGE_APP_SECRET', 'LONGBRIDGE_ACCESS_TOKEN'],
  finnhub: ['FINNHUB_API_KEY'],
  alphavantage: ['ALPHAVANTAGE_API_KEY'],
  tavily: ['TAVILY_API_KEYS'],
  serpapi: ['SERPAPI_API_KEYS'],
  brave: ['BRAVE_API_KEYS'],
  bocha: ['BOCHA_API_KEYS'],
  minimax: ['MINIMAX_API_KEYS'],
  anspire: ['ANSPIRE_API_KEYS'],
  searxng: ['SEARXNG_BASE_URLS'],
};

function ProviderConfigModal({
  title,
  items,
  saving,
  error,
  onSave,
  onClose,
}: {
  title: string;
  items: SystemConfigItem[];
  saving: boolean;
  error: string;
  onSave: (changed: SystemConfigUpdateItem[]) => void;
  onClose: () => void;
}) {
  const { t } = useUiLanguage();
  const [draft, setDraft] = useState<Record<string, string>>(
    () => Object.fromEntries(items.map((item) => [item.key, item.value])),
  );
  const changed = items
    .filter((item) => (draft[item.key] ?? '') !== item.value)
    .map((item) => ({ key: item.key, value: draft[item.key] ?? '' }));
  const close = () => {
    if (!saving) onClose();
  };
  const dialogRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={close}>
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border/70 bg-elevated shadow-2xl outline-none"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          // Help popups are portaled outside this node; let them handle their own Escape.
          if (event.key === 'Escape' && event.currentTarget.contains(event.target as Node)) close();
        }}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border/60 px-5 py-4">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <button
            type="button"
            aria-label={t('common.close')}
            disabled={saving}
            onClick={close}
            className="rounded-lg p-1 text-secondary-text transition-colors hover:bg-hover hover:text-foreground disabled:opacity-50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 divide-y divide-border/40 overflow-y-auto">
          {items.map((item) => (
            <SettingsField
              key={item.key}
              item={item}
              value={draft[item.key] ?? ''}
              disabled={saving}
              onChange={(key, value) => setDraft((current) => ({ ...current, [key]: value }))}
            />
          ))}
        </div>
        {error ? <div className="px-5 pt-3"><InlineAlert variant="danger" message={error} /></div> : null}
        <div className="flex justify-end gap-2 px-5 py-4">
          <Button size="sm" variant="ghost" disabled={saving} onClick={close}>{t('common.cancel')}</Button>
          <Button
            size="sm"
            disabled={changed.length === 0}
            isLoading={saving}
            loadingText={t('dataCenter.saveAndApply')}
            onClick={() => onSave(changed)}
          >
            {t('dataCenter.saveAndApply')}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function statusVariant(status: Status): 'success' | 'warning' | 'danger' | 'default' {
  if (status === 'ok') return 'success';
  if (status === 'partial' || status === 'degraded' || status === 'stale' || status === 'unknown') return 'warning';
  if (status === 'unavailable') return 'danger';
  return 'default';
}

function formatDatasetMarkets(datasetMarkets: Record<string, string[]>): string {
  return Object.entries(datasetMarkets)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([dataset, markets]) => `${dataset} [${markets.join(', ') || '--'}]`)
    .join(' · ');
}

function formatDatasetSources(dataset: DataCapabilityOverview['datasets'][number]): string {
  const markets = dataset.coverage?.markets;
  if (markets && typeof markets === 'object' && !Array.isArray(markets)) {
    const sources = Object.entries(markets)
      .sort(([left], [right]) => left.localeCompare(right))
      .flatMap(([market, value]) => {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
        const source = (value as Record<string, unknown>).source;
        return typeof source === 'string' && source.trim() ? [`${market}: ${source.trim()}`] : [];
      });
    if (sources.length) return sources.join(' / ');
  }
  return dataset.source || '--';
}

function SummaryTile({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <div className="rounded-xl border border-border/75 bg-card/85 px-4 py-3">
      <div className="text-xs text-secondary-text">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-text">{note}</div>
    </div>
  );
}

const DataCenterPage: React.FC = () => {
  const { t } = useUiLanguage();
  const [overview, setOverview] = useState<DataCapabilityOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const requestGeneration = useRef(0);

  useEffect(() => {
    document.title = `${t('dataCenter.title')} - DSA`;
  }, [t]);

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setError('');
    try {
      const nextOverview = await dataCapabilityApi.getOverview();
      if (generation !== requestGeneration.current) return;
      setOverview(nextOverview);
    } catch {
      if (generation !== requestGeneration.current) return;
      setOverview(null);
      setError(t('dataCenter.loadError'));
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
    return () => {
      requestGeneration.current += 1;
    };
  }, [load]);

  const [config, setConfig] = useState<SystemConfigResponse | null>(null);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configSaveError, setConfigSaveError] = useState('');

  const loadConfig = useCallback(async () => {
    try {
      setConfig(await systemConfigApi.getConfig(true));
    } catch {
      setConfig(null);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const reviewRegions = useMemo(() => {
    if (!config) return null;
    return resolveServerMarketReviewRegions(config.items.find((item) => item.key === 'MARKET_REVIEW_REGION')?.value);
  }, [config]);

  const saveProviderConfig = async (items: SystemConfigUpdateItem[]) => {
    if (!config) return;
    setSavingConfig(true);
    setConfigSaveError('');
    try {
      await systemConfigApi.update({
        configVersion: config.configVersion,
        maskToken: config.maskToken,
        reloadNow: true,
        items,
      });
      setEditingProvider(null);
      await Promise.all([loadConfig(), load()]);
    } catch (saveError) {
      setConfigSaveError(getParsedApiError(saveError).message || t('dataCenter.configSaveError'));
    } finally {
      setSavingConfig(false);
    }
  };

  const summary = useMemo(() => {
    const providers = overview?.providers ?? [];
    const datasets = overview?.datasets ?? [];
    return {
      configured: providers.filter((item) => item.configured).length,
      healthy: datasets.filter((item) => item.status === 'ok').length,
      attention: datasets.filter((item) => item.status !== 'ok').length,
    };
  }, [overview]);

  return (
    <AppPage className="space-y-5">
      <PageHeader eyebrow="Data Center" title={t('dataCenter.title')} description={t('dataCenter.description')} />

      <div className="flex justify-end gap-2">
        <Link
          to="/settings"
          className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-transparent px-3 text-sm font-medium text-secondary-text transition-all hover:bg-hover hover:text-foreground"
        >
          <Settings2 className="h-4 w-4" />{t('dataCenter.openSettings')}
        </Link>
        <Button size="sm" variant="secondary" isLoading={loading} loadingText={t('dataCenter.refreshing')} onClick={() => void load()}>
          <RefreshCw className="h-4 w-4" />{t('dataCenter.refresh')}
        </Button>
      </div>

      {error ? (
        <InlineAlert
          variant="danger"
          title={t('dataCenter.loadErrorTitle')}
          message={error}
          action={<Button size="sm" variant="secondary" onClick={() => void load()}>{t('common.retry')}</Button>}
        />
      ) : null}

      {loading && !overview ? <Loading label={t('dataCenter.loading')} /> : null}

      {!loading && !error && overview && overview.providers.length === 0 && overview.datasets.length === 0 ? (
        <EmptyState icon={<Database className="h-6 w-6" />} title={t('dataCenter.emptyTitle')} description={t('dataCenter.emptyDescription')} />
      ) : null}

      {overview ? (
        <>
          {overview.warnings.length > 0 ? (
            <InlineAlert variant="warning" title={t('dataCenter.partialTitle')} message={overview.warnings.join(' · ')} />
          ) : null}

          <div className="grid gap-3 md:grid-cols-3">
            <SummaryTile label={t('dataCenter.configuredProviders')} value={summary.configured} note={`${overview.providers.length} ${t('dataCenter.totalProviders')}`} />
            <SummaryTile label={t('dataCenter.healthyDatasets')} value={summary.healthy} note={`${overview.datasets.length} ${t('dataCenter.totalDatasets')}`} />
            <SummaryTile label={t('dataCenter.attentionDatasets')} value={summary.attention} note={t('dataCenter.attentionNote')} />
          </div>

          <Card title={t('dataCenter.providers')} subtitle={formatDateTime(overview.asOf)} variant="bordered" padding="md">
            {reviewRegions ? (
              <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-secondary-text">
                <span className="font-medium text-foreground">{t('dataCenter.reviewMarkets')}:</span>
                <span className="rounded-md bg-primary/15 px-1.5 py-0.5 font-medium text-primary ring-1 ring-primary/40">
                  {formatMarketReviewRegionLabel(reviewRegions.join(','), t)}
                </span>
                <span className="text-muted-text">{t('dataCenter.reviewMarketsHint')}</span>
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {overview.providers.map((provider) => {
                const configKeys = PROVIDER_CONFIG_KEYS[provider.name];
                return (
                  <div key={provider.name} className="rounded-xl border border-border/70 bg-surface/60 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-semibold text-foreground">{provider.label || provider.name}</div>
                        <div className="mt-1 flex items-center gap-1.5 text-xs">
                          <span className="font-mono text-muted-text">{provider.name}</span>
                          <span className="rounded bg-surface px-1.5 text-[11px] text-secondary-text ring-1 ring-border/70">
                            {provider.datasets.includes('news.events') ? t('dataCenter.categoryNews') : t('dataCenter.categoryMarket')}
                          </span>
                        </div>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-2">
                        {!provider.configured && configKeys && config ? (
                          <Button
                            size="xsm"
                            variant="secondary"
                            onClick={() => {
                              setConfigSaveError('');
                              setEditingProvider(provider.name);
                            }}
                          >
                            <Settings2 className="h-3.5 w-3.5" />{t('dataCenter.configure')}
                          </Button>
                        ) : null}
                        <Badge variant={statusVariant(provider.status)}>{provider.status}</Badge>
                      </div>
                    </div>
                    <div className="mt-3 text-xs leading-5 text-secondary-text">
                      <div className="flex flex-wrap items-center gap-1">
                        <span>{t('dataCenter.markets')}:</span>
                        {provider.markets.length ? provider.markets.map((market) => {
                          const highlighted = (reviewRegions as readonly string[] | null)?.includes(market.toLowerCase()) ?? false;
                          return (
                            <span
                              key={market}
                              className={cn(
                                'rounded px-1.5 font-mono text-[11px] uppercase',
                                highlighted ? 'bg-primary/15 font-semibold text-primary ring-1 ring-primary/40' : 'text-muted-text',
                              )}
                            >
                              {market}
                            </span>
                          );
                        }) : '--'}
                      </div>
                      <div>{t('dataCenter.datasets')}: {formatDatasetMarkets(provider.datasetMarkets) || '--'}</div>
                      <div>{t('dataCenter.lastSuccess')}: {provider.lastSuccessAt ? formatDateTime(provider.lastSuccessAt) : '--'}</div>
                    </div>
                    {provider.warnings.length > 0 ? <div className="mt-2 text-xs text-warning">{provider.warnings.join(' · ')}</div> : null}
                    {!provider.configured && configKeys && !config ? (
                      <div className="mt-2 text-xs text-muted-text">{t('dataCenter.configLoadError')}</div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>

          {editingProvider && config ? (
            <ProviderConfigModal
              title={`${overview.providers.find((item) => item.name === editingProvider)?.label || editingProvider} · ${t('dataCenter.configure')}`}
              items={(PROVIDER_CONFIG_KEYS[editingProvider] ?? []).flatMap((key) => config.items.filter((item) => item.key === key))}
              saving={savingConfig}
              error={configSaveError}
              onSave={(items) => void saveProviderConfig(items)}
              onClose={() => setEditingProvider(null)}
            />
          ) : null}

          <Card title={t('dataCenter.datasetQuality')} subtitle="Quality" variant="bordered" padding="md">
            {overview.datasets.length === 0 ? (
              <EmptyState title={t('dataCenter.noDatasetQuality')} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-border/60 text-xs uppercase text-muted-text">
                    <tr>
                      <th className="px-3 py-2 font-medium">{t('dataCenter.dataset')}</th>
                      <th className="px-3 py-2 font-medium">{t('dataCenter.status')}</th>
                      <th className="px-3 py-2 font-medium">{t('dataCenter.source')}</th>
                      <th className="whitespace-nowrap px-3 py-2 font-medium">{t('dataCenter.lastSuccess')}</th>
                      <th className="px-3 py-2 font-medium">{t('dataCenter.notes')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {overview.datasets.map((dataset) => (
                      <tr key={dataset.dataset}>
                        <td className="px-3 py-3 font-mono text-foreground">{dataset.dataset}</td>
                        <td className="px-3 py-3"><Badge variant={statusVariant(dataset.status)}>{dataset.status}</Badge></td>
                        <td className="px-3 py-3 text-secondary-text">{formatDatasetSources(dataset)}</td>
                        <td className="px-3 py-3 text-secondary-text">{dataset.lastSuccess ? formatDateTime(dataset.lastSuccess) : '--'}</td>
                        <td className="px-3 py-3 text-secondary-text">{[dataset.lastError, ...dataset.warnings].filter(Boolean).join(' · ') || '--'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={t('dataCenter.priorities')} subtitle="Routing" variant="bordered" padding="md">
            {overview.priorities.length === 0 ? (
              <EmptyState icon={<TriangleAlert className="h-6 w-6" />} title={t('dataCenter.noPriorities')} />
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {overview.priorities.map((priority) => (
                  <div key={priority.scenario} className="rounded-xl border border-border/70 bg-surface/60 p-3">
                    <div className="font-mono text-sm font-semibold text-foreground">{priority.scenario}</div>
                    <div className="mt-2 text-sm text-secondary-text">{priority.providers.join(' → ') || '--'}</div>
                    <div className="mt-1 text-xs text-muted-text">{priority.source}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      ) : null}
    </AppPage>
  );
};

export default DataCenterPage;
