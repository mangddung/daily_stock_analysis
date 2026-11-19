import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ReportDisclosures } from '../ReportDisclosures';

describe('ReportDisclosures', () => {
  it('renders nothing without disclosure data', () => {
    const { container } = render(<ReportDisclosures details={{ rawResult: { disclosures: null } }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('lists scheduled dates and recent filings verbatim', () => {
    render(
      <ReportDisclosures
        details={{
          rawResult: {
            upcomingDisclosures: [{ date: '2026-11-26', title: 'Earnings announcement, Third quarter', source: 'JPX' }],
            disclosures: [{ date: '2026-11-19', title: 'Rights offering decision', summary: 'KRW 100bn', source: 'OpenDART' }],
          },
        }}
      />,
    );
    expect(screen.getByTestId('report-upcoming-disclosures')).toHaveTextContent('2026-11-26');
    expect(screen.getByText('Earnings announcement, Third quarter')).toBeInTheDocument();
    expect(screen.getByTestId('report-recent-disclosures')).toHaveTextContent('Rights offering decision');
    expect(screen.getByText('KRW 100bn')).toBeInTheDocument();
  });
});
