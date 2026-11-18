import type React from 'react';
import type { ReportStrategy as ReportStrategyType } from '../../types/analysis';
import { Card } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import { getReportText } from '../../utils/reportLanguage';
import { useUiLanguage } from '../../contexts/UiLanguageContext';

interface ReportStrategyProps {
  strategy?: ReportStrategyType;
}

interface StrategyItemProps {
  label: string;
  value?: string;
  tone: string;
}

// Big mono suits a bare price ("97.61", "95.2-97.6"); LLM output is often a full sentence,
// which wrapped to 4-5 lines in that style, so longer values use regular body text.
const SHORT_VALUE_MAX_LENGTH = 16;

const StrategyItem: React.FC<StrategyItemProps> = ({
  label,
  value,
  tone,
}) => {
  const isShort = !value || value.trim().length <= SHORT_VALUE_MAX_LENGTH;
  return (
    <div className="home-subpanel home-strategy-card p-3" style={{ ['--home-strategy-tone' as string]: `var(${tone})` }}>
      <div className="flex flex-col">
        <span className="home-strategy-label mb-0.5 text-xs">{label}</span>
        <span
          className={isShort
            ? 'home-strategy-value text-lg font-bold font-mono'
            : 'home-strategy-value text-sm font-medium leading-relaxed'}
          style={!value ? { color: 'var(--text-muted-text)' } : undefined}
        >
          {value || '—'}
        </span>
      </div>
      <div
        className="absolute bottom-0 left-0 right-0 h-0.5"
        style={{ background: `linear-gradient(90deg, transparent, var(${tone}), transparent)` }}
      />
    </div>
  );
};

/**
 * 策略点位区组件 - 终端风格
 */
export const ReportStrategy: React.FC<ReportStrategyProps> = ({ strategy }) => {
  const { language } = useUiLanguage();
  if (!strategy) {
    return null;
  }

  const text = getReportText(language);

  const strategyItems = [
    {
      label: text.idealBuy,
      value: strategy.idealBuy,
      tone: '--home-strategy-buy',
    },
    {
      label: text.secondaryBuy,
      value: strategy.secondaryBuy,
      tone: '--home-strategy-secondary',
    },
    {
      label: text.stopLoss,
      value: strategy.stopLoss,
      tone: '--home-strategy-stop',
    },
    {
      label: text.takeProfit,
      value: strategy.takeProfit,
      tone: '--home-strategy-take',
    },
  ];

  return (
    <Card variant="bordered" padding="md" className="home-panel-card">
      <DashboardPanelHeader
        eyebrow={text.strategyPoints}
        title={text.sniperLevels}
        className="mb-3"
      />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {strategyItems.map((item) => (
          <StrategyItem key={item.label} {...item} />
        ))}
      </div>
    </Card>
  );
};
