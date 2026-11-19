import type React from 'react';
import { Card } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import type { ReportDetails } from '../../types/analysis';
import { useUiLanguage } from '../../contexts/UiLanguageContext';

interface DisclosureItem {
  date?: string;
  title?: string;
  summary?: string | null;
  source?: string;
}

const DISCLOSURE_TEXT = {
  zh: {
    eyebrow: 'FILINGS',
    title: '官方公告',
    upcoming: '预定披露',
    recent: '近期公告',
    hint: '来自官方披露源，原样展示；预定日期可能由公司变更。',
  },
  en: {
    eyebrow: 'FILINGS',
    title: 'Official disclosures',
    upcoming: 'Upcoming',
    recent: 'Recent filings',
    hint: 'Shown as published by the official sources; scheduled dates may be changed by the issuer.',
  },
  ko: {
    eyebrow: 'FILINGS',
    title: '공시',
    upcoming: '공시 예정',
    recent: '최근 공시',
    hint: '공식 공시 출처의 내용을 그대로 표시합니다. 예정일은 회사 사정으로 바뀔 수 있습니다.',
  },
} as const;

function asItems(value: unknown): DisclosureItem[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === 'object') as DisclosureItem[]) : [];
}

/** Recent filings and scheduled disclosure dates, verbatim from the disclosure service (raw_result). */
export const ReportDisclosures: React.FC<{ details?: ReportDetails }> = ({ details }) => {
  const { language } = useUiLanguage();
  const text = DISCLOSURE_TEXT[language];
  const upcoming = asItems(details?.rawResult?.upcomingDisclosures);
  const recent = asItems(details?.rawResult?.disclosures);

  if (upcoming.length === 0 && recent.length === 0) {
    return null;
  }

  return (
    <Card variant="bordered" padding="md" className="home-panel-card">
      <DashboardPanelHeader eyebrow={text.eyebrow} title={text.title} />
      <p className="mb-3 text-xs leading-5 text-muted-text">{text.hint}</p>

      {upcoming.length > 0 && (
        <section className="mb-4 text-left">
          <h4 className="mb-2 text-xs font-medium text-secondary-text">{text.upcoming}</h4>
          <ul className="space-y-2" data-testid="report-upcoming-disclosures">
            {upcoming.map((item, index) => (
              <li key={`${item.date}-${item.title}-${index}`} className="home-subpanel flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5 text-sm">
                <span className="shrink-0 font-medium tabular-nums text-foreground">{item.date}</span>
                <span className="min-w-0 flex-1 text-secondary-text">{item.title}</span>
                {item.source ? <span className="shrink-0 text-xs text-muted-text">{item.source}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      )}

      {recent.length > 0 && (
        <section className="text-left">
          <h4 className="mb-2 text-xs font-medium text-secondary-text">{text.recent}</h4>
          <ul className="space-y-2" data-testid="report-recent-disclosures">
            {recent.map((item, index) => (
              <li key={`${item.date}-${item.title}-${index}`} className="home-subpanel px-4 py-2.5">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                  <span className="shrink-0 font-medium tabular-nums text-foreground">{item.date}</span>
                  <span className="min-w-0 flex-1 text-foreground">{item.title}</span>
                  {item.source ? <span className="shrink-0 text-xs text-muted-text">{item.source}</span> : null}
                </div>
                {item.summary ? (
                  <p className="mt-1 text-sm leading-6 text-secondary-text">{item.summary}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      )}
    </Card>
  );
};
