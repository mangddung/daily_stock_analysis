import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RuntimeAlertIndicator } from '../RuntimeAlertIndicator';

const { getRuntimeAlerts } = vi.hoisted(() => ({ getRuntimeAlerts: vi.fn() }));

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: { getRuntimeAlerts },
}));

function renderIndicator() {
  return render(
    <MemoryRouter>
      <RuntimeAlertIndicator />
    </MemoryRouter>,
  );
}

describe('RuntimeAlertIndicator', () => {
  beforeEach(() => {
    getRuntimeAlerts.mockReset();
  });

  it('stays hidden when no source is rate-limited', async () => {
    getRuntimeAlerts.mockResolvedValue({ alerts: [], ttlMinutes: 15 });
    renderIndicator();

    await vi.waitFor(() => expect(getRuntimeAlerts).toHaveBeenCalled());
    expect(screen.queryByTestId('runtime-alert-indicator')).toBeNull();
  });

  it('shows the alert count and lists each source', async () => {
    getRuntimeAlerts.mockResolvedValue({
      alerts: [
        { kind: 'llm', source: 'anthropic/claude-haiku', lastAt: '2026-11-18T17:00:00+09:00', count: 2, message: 'RateLimitError' },
        { kind: 'news', source: 'tavily', lastAt: '2026-11-18T16:58:00+09:00', count: 1, message: null },
        { kind: 'disclosure', source: 'KIND', lastAt: '2026-11-18T16:57:00+09:00', count: 1, message: '0 rows parsed' },
      ],
      ttlMinutes: 15,
    });
    renderIndicator();

    const badge = await screen.findByTestId('runtime-alert-indicator');
    expect(badge).toHaveTextContent('3');
    fireEvent.click(badge);
    expect(screen.getByText(/anthropic\/claude-haiku/)).toBeInTheDocument();
    expect(screen.getByText(/tavily/)).toBeInTheDocument();
    expect(screen.getByText(/KIND/)).toBeInTheDocument();
  });
});
