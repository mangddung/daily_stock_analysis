import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import {
  MARKET_REVIEW_REGION_ORDER,
  formatMarketReviewRegionLabel,
  parseMarketReviewRegions,
  serializeMarketReviewRegions,
  type MarketReviewRegion,
} from '../../utils/marketReviewRegion';

type MarketReviewRegionFieldProps = {
  id: string;
  value: string;
  defaultValue?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
};

/** Multi-select dropdown for the MARKET_REVIEW_REGION setting ("cn,us" / "both"). */
export const MarketReviewRegionField: React.FC<MarketReviewRegionFieldProps> = ({
  id,
  value,
  defaultValue,
  disabled = false,
  onChange,
}) => {
  const { t } = useUiLanguage();
  const [open, setOpen] = useState(false);
  const menuOpen = open && !disabled;
  const containerRef = useRef<HTMLDivElement | null>(null);

  const effectiveValue = value.trim() ? value : (defaultValue ?? '');
  const selected = parseMarketReviewRegions(effectiveValue) ?? [];
  const allSelected = selected.length === MARKET_REVIEW_REGION_ORDER.length;
  const triggerLabel = formatMarketReviewRegionLabel(effectiveValue, t) ?? t('common.selectPlaceholder');

  const regionLabels: Record<MarketReviewRegion, string> = {
    cn: t('home.marketRegionCn'),
    hk: t('home.marketRegionHk'),
    us: t('home.marketRegionUs'),
    jp: t('home.marketRegionJp'),
    kr: t('home.marketRegionKr'),
    tw: t('home.marketRegionTw'),
  };

  useEffect(() => {
    if (!menuOpen) {
      return undefined;
    }
    const handlePointerDown = (event: MouseEvent) => {
      if (event.target instanceof Node && containerRef.current?.contains(event.target)) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [menuOpen]);

  const toggleRegion = (region: MarketReviewRegion) => {
    const next = new Set<MarketReviewRegion>(selected);
    if (next.has(region)) {
      // At least one market must stay selected; an empty value falls back to cn on the server.
      if (next.size === 1) {
        return;
      }
      next.delete(region);
    } else {
      next.add(region);
    }
    onChange(serializeMarketReviewRegions([...next]));
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        id={id}
        type="button"
        disabled={disabled}
        aria-haspopup="true"
        aria-expanded={menuOpen}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false);
          }
        }}
        className={cn(
          'input-surface input-focus-glow flex h-11 w-full items-center gap-2 rounded-xl border bg-transparent px-4 text-left text-sm text-foreground transition-all focus:outline-none',
          'disabled:cursor-not-allowed disabled:opacity-60',
        )}
      >
        <span className="min-w-0 flex-1 truncate">{triggerLabel}</span>
        <ChevronDown
          className={cn('h-4 w-4 flex-shrink-0 text-secondary-text transition-transform', menuOpen && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {menuOpen ? (
        <div
          role="group"
          aria-labelledby={id}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              setOpen(false);
              document.getElementById(id)?.focus();
            }
          }}
          // Rendered in flow (not absolute): settings cards clip overflow, so a floating menu would be cut off.
          className="mt-2 overflow-hidden rounded-2xl border border-subtle bg-surface/95 p-2"
        >
          <button
            type="button"
            aria-pressed={allSelected}
            onClick={() => onChange(serializeMarketReviewRegions(MARKET_REVIEW_REGION_ORDER))}
            className="flex min-h-10 w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left text-sm text-secondary-text transition-colors hover:bg-surface-hover hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:outline-none"
          >
            <span className="flex h-4 w-4 items-center justify-center rounded border border-primary/60 bg-primary/10">
              <Check className={cn('h-3 w-3 text-primary', allSelected ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
            </span>
            <span className="font-medium">{t('home.marketRegionAll')}</span>
          </button>

          <div className="grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-1 pt-1">
            {MARKET_REVIEW_REGION_ORDER.map((region) => (
              <label
                key={region}
                className="flex min-h-10 cursor-pointer items-center gap-3 rounded-xl px-2.5 py-2 text-sm text-secondary-text transition-colors hover:bg-surface-hover hover:text-foreground"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(region)}
                  onChange={() => toggleRegion(region)}
                  className="h-4 w-4 rounded border-border accent-primary"
                />
                <span className="whitespace-nowrap">{regionLabels[region]}</span>
                <span className="ml-auto text-[11px] uppercase text-muted-text">{region}</span>
              </label>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
};
