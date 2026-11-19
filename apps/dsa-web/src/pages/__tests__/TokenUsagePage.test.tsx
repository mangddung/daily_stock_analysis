import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import TokenUsagePage from '../TokenUsagePage';

const { get } = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('../../api/index', () => ({
  default: { get },
}));

const dashboardResponse = {
  period: 'month',
  from_date: '2026-06-01',
  to_date: '2026-06-11',
  total_calls: 3,
  total_prompt_tokens: 120,
  total_completion_tokens: 280,
  total_tokens: 400,
  by_call_type: [
    {
      call_type: 'analysis',
      calls: 2,
      prompt_tokens: 100,
      completion_tokens: 200,
      total_tokens: 300,
    },
    {
      call_type: 'agent',
      calls: 1,
      prompt_tokens: 20,
      completion_tokens: 80,
      total_tokens: 100,
    },
  ],
  by_model: [
    {
      model: 'openai/gpt-test',
      calls: 2,
      prompt_tokens: 100,
      completion_tokens: 200,
      total_tokens: 300,
      max_total_tokens: 240,
    },
    {
      model: 'custom-router',
      calls: 1,
      prompt_tokens: 20,
      completion_tokens: 80,
      total_tokens: 100,
      max_total_tokens: 100,
    },
  ],
  recent_calls: [
    {
      id: 1,
      called_at: '2026-06-11T09:30:00',
      call_type: 'analysis',
      model: 'openai/gpt-test',
      stock_code: '600519',
      prompt_tokens: 40,
      completion_tokens: 200,
      total_tokens: 240,
    },
  ],
};

const callRecord = {
  id: 1,
  called_at: '2026-06-11T09:30:00',
  call_type: 'analysis',
  model: 'openai/gpt-test',
  stock_code: '600519',
  prompt_tokens: 40,
  completion_tokens: 200,
  total_tokens: 240,
};

const callGroupsResponse = {
  period: 'month',
  page: 1,
  page_size: 50,
  total: 1,
  items: [
    {
      group_id: 'i:1',
      request_id: null,
      called_at: callRecord.called_at,
      call_type: 'analysis',
      models: ['openai/gpt-test'],
      stock_code: '600519',
      calls: 1,
      prompt_tokens: 40,
      completion_tokens: 200,
      total_tokens: 240,
      items: [callRecord],
    },
  ],
};

const agentCall = { ...callRecord, call_type: 'agent', model: 'claude-x', stock_code: null, total_tokens: 11 };

const groupedCallsResponse = {
  ...callGroupsResponse,
  total: 120,
  items: [
    {
      group_id: 'r:req-1',
      request_id: 'req-1',
      called_at: callRecord.called_at,
      call_type: 'agent',
      models: ['claude-x'],
      stock_code: null,
      calls: 2,
      prompt_tokens: 80,
      completion_tokens: 400,
      total_tokens: 22,
      items: [
        { ...agentCall, id: 2 },
        { ...agentCall, id: 3 },
      ],
    },
  ],
};

function respond(url: string, dashboard: unknown = dashboardResponse, calls: unknown = callGroupsResponse) {
  return Promise.resolve({ data: url === '/api/v1/usage/calls' ? calls : dashboard });
}

function makeDashboardResponse(overrides: Partial<typeof dashboardResponse> = {}) {
  return {
    ...dashboardResponse,
    ...overrides,
  };
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function renderPage() {
  return render(
    <UiLanguageProvider>
      <TokenUsagePage />
    </UiLanguageProvider>
  );
}

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem('dsa.uiLanguage', 'zh');
  vi.clearAllMocks();
  get.mockImplementation((url: string) => respond(url));
});

describe('TokenUsagePage', () => {
  it('renders token summary, model breakdowns, and recent calls from the dashboard API shape', async () => {
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Token 用量监控' })).toBeInTheDocument();
    expect(await screen.findByText('400')).toBeInTheDocument();
    expect(screen.getAllByText('openai/gpt-test')).toHaveLength(2);
    expect(screen.getAllByText('个股分析')).toHaveLength(2);
    expect(screen.getByText(/600519/)).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('/api/v1/usage/dashboard', {
      params: { period: 'month', limit: 50 },
    });
  });

  it('renders English copy when the UI language is English', async () => {
    window.localStorage.setItem('dsa.uiLanguage', 'en');

    renderPage();

    expect(await screen.findByRole('heading', { name: 'Token usage' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Today' })).toBeInTheDocument();
    expect(screen.getAllByText('Stock analysis')).toHaveLength(2);
    expect(screen.getByText(/Calls from one chat turn are grouped into one row/)).toBeInTheDocument();
    expect(screen.queryByText('Token 用量监控')).not.toBeInTheDocument();
  });

  it('keeps the newest period data when dashboard requests resolve out of order', async () => {
    const monthRequest = createDeferred<{ data: typeof dashboardResponse }>();
    const todayRequest = createDeferred<{ data: typeof dashboardResponse }>();
    const todayResponse = makeDashboardResponse({
      period: 'today',
      from_date: '2026-06-15',
      to_date: '2026-06-15',
      total_calls: 9,
      total_prompt_tokens: 700,
      total_completion_tokens: 200,
      total_tokens: 900,
      by_call_type: [
        {
          call_type: 'analysis',
          calls: 9,
          prompt_tokens: 700,
          completion_tokens: 200,
          total_tokens: 900,
        },
      ],
      by_model: [
        {
          model: 'openai/gpt-test',
          calls: 9,
          prompt_tokens: 700,
          completion_tokens: 200,
          total_tokens: 900,
          max_total_tokens: 300,
        },
      ],
      recent_calls: [],
    });

    get.mockImplementation((url, config) => {
      if (url === '/api/v1/usage/calls') {
        return respond(url);
      }
      const period = config?.params?.period;
      if (period === 'month') {
        return monthRequest.promise;
      }
      if (period === 'today') {
        return todayRequest.promise;
      }
      return Promise.resolve({ data: dashboardResponse });
    });

    renderPage();

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/api/v1/usage/dashboard', {
        params: { period: 'month', limit: 50 },
      });
    });

    fireEvent.click(screen.getByRole('button', { name: '今日' }));

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/api/v1/usage/dashboard', {
        params: { period: 'today', limit: 50 },
      });
    });

    await act(async () => {
      todayRequest.resolve({ data: todayResponse });
    });

    expect(await screen.findByText('900')).toBeInTheDocument();

    await act(async () => {
      monthRequest.resolve({ data: dashboardResponse });
    });

    await waitFor(() => {
      expect(screen.getByText('900')).toBeInTheDocument();
    });
    expect(screen.queryByText('400')).not.toBeInTheDocument();
  });

  it('reloads dashboard when period changes', async () => {
    renderPage();

    await screen.findByRole('heading', { name: 'Token 用量监控' });
    fireEvent.click(screen.getByRole('button', { name: '今日' }));

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/api/v1/usage/dashboard', {
        params: { period: 'today', limit: 50 },
      });
    });
  });

  it('collapses one chat turn into a single row and expands its calls', async () => {
    get.mockImplementation((url: string) => respond(url, dashboardResponse, groupedCallsResponse));
    renderPage();

    const toggle = await screen.findByRole('button', { name: /2 次调用/ });
    expect(screen.getByText('22')).toBeInTheDocument();
    expect(screen.queryAllByText('11')).toHaveLength(0);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByText('11')).toHaveLength(2);
  });

  it('requests the next page of call groups', async () => {
    get.mockImplementation((url: string) => respond(url, dashboardResponse, groupedCallsResponse));
    renderPage();

    await screen.findByRole('button', { name: /2 次调用/ });
    fireEvent.click(screen.getByRole('button', { name: '2' }));

    await waitFor(() => {
      expect(get).toHaveBeenLastCalledWith('/api/v1/usage/calls', {
        params: { period: 'month', page: 2, page_size: 50 },
      });
    });
  });
});
