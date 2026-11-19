import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UiLanguageProvider, useUiLanguage } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import { useTaskStream } from '../useTaskStream';

const { getTaskStreamUrl } = vi.hoisted(() => ({
  getTaskStreamUrl: vi.fn(() => 'http://localhost/api/v1/analysis/tasks/stream'),
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    getTaskStreamUrl,
  },
}));

type MockEventSourceInstance = {
  listeners: Record<string, ((event: MessageEvent<string>) => void) | undefined>;
  addEventListener: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  onerror: ((event: Event) => void) | null;
};

describe('useTaskStream', () => {
  let eventSourceInstance: MockEventSourceInstance;
  let eventSourceInstances: MockEventSourceInstance[];

  beforeEach(() => {
    vi.clearAllMocks();
    eventSourceInstances = [];
    eventSourceInstance = createEventSourceInstance();

    function createEventSourceInstance(): MockEventSourceInstance {
      const instance: MockEventSourceInstance = {
        listeners: {},
        addEventListener: vi.fn((type: string, listener: (event: MessageEvent<string>) => void) => {
          const previous = instance.listeners[type];
          instance.listeners[type] = previous
            ? (event) => {
                previous(event);
                listener(event);
              }
            : listener;
        }),
        close: vi.fn(),
        onerror: null,
      };
      return instance;
    }

    class MockEventSource {
      addEventListener: MockEventSourceInstance['addEventListener'];
      close: MockEventSourceInstance['close'];

      constructor(...args: unknown[]) {
        void args;
        const instance = createEventSourceInstance();
        eventSourceInstance = instance;
        eventSourceInstances.push(instance);
        this.addEventListener = instance.addEventListener;
        this.close = instance.close;
        Object.defineProperty(this, 'onerror', {
          configurable: true,
          get: () => instance.onerror,
          set: (handler: ((event: Event) => void) | null) => {
            instance.onerror = handler;
          },
        });
      }
    }

    Object.defineProperty(window, 'EventSource', {
      writable: true,
      configurable: true,
      value: MockEventSource,
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('closes the SSE connection when the hook unmounts', async () => {
    const { unmount } = renderHook(() => useTaskStream({ enabled: true }));

    await waitFor(() => expect(getTaskStreamUrl).toHaveBeenCalledTimes(1));

    unmount();

    expect(eventSourceInstance.close).toHaveBeenCalled();
  });

  it('parses task_progress events and forwards the updated task payload', async () => {
    const onTaskProgress = vi.fn();
    const onTaskFlowEvent = vi.fn();

    renderHook(() => useTaskStream({ enabled: true, onTaskProgress, onTaskFlowEvent }));
    await waitFor(() => expect(eventSourceInstance.listeners.task_progress).toBeDefined());

    eventSourceInstance.listeners.task_progress?.(
      new MessageEvent('task_progress', {
        data: JSON.stringify({
          task_id: 'task-1',
          trace_id: 'trace-task-1',
          stock_code: 'sh000016',
          stock_name: '上证50',
          asset_type: 'index',
          status: 'processing',
          progress: 72,
          message: 'LLM 正在生成分析结果',
          report_type: 'detailed',
          analysis_phase: 'intraday',
          created_at: '2026-03-29T08:00:00Z',
          skills: ['growth_quality'],
          region: 'jp,kr',
          cancellable: true,
          flow_event: {
            id: 'flow-1',
            timestamp: '2026-03-29T08:00:01Z',
            severity: 'success',
            type: 'provider_run',
            node_id: 'provider_daily_1',
            title: '日线K线成功',
            metadata: {
              node: {
                id: 'provider_daily_1',
                lane: 'data_source',
                kind: 'data_source',
                label: '日线K线',
                status: 'success',
              },
            },
          },
        }),
      }),
    );

    expect(onTaskProgress).toHaveBeenCalledWith({
      taskId: 'task-1',
      traceId: 'trace-task-1',
      stockCode: 'sh000016',
      stockName: '上证50',
      status: 'processing',
      progress: 72,
      message: 'LLM 正在生成分析结果',
      reportType: 'detailed',
      createdAt: '2026-03-29T08:00:00Z',
      startedAt: undefined,
      completedAt: undefined,
      error: undefined,
      originalQuery: undefined,
      selectionSource: undefined,
      analysisPhase: 'intraday',
      skills: ['growth_quality'],
      region: 'jp,kr',
      assetType: 'index',
      cancellable: true,
    });
    expect(onTaskFlowEvent).toHaveBeenCalledWith(
      expect.objectContaining({ taskId: 'task-1' }),
      expect.objectContaining({
        id: 'flow-1',
        nodeId: 'provider_daily_1',
        metadata: expect.objectContaining({
          node: expect.objectContaining({ lane: 'data_source' }),
        }),
      }),
    );
  });

  it('shares one SSE connection across multiple hook instances', async () => {
    const firstConnected = vi.fn();
    const secondConnected = vi.fn();
    const firstProgress = vi.fn();
    const secondProgress = vi.fn();

    const first = renderHook(() => useTaskStream({
      enabled: true,
      onConnected: firstConnected,
      onTaskProgress: firstProgress,
    }));
    const second = renderHook(() => useTaskStream({
      enabled: true,
      onConnected: secondConnected,
      onTaskProgress: secondProgress,
    }));

    await waitFor(() => expect(eventSourceInstances).toHaveLength(1));
    expect(getTaskStreamUrl).toHaveBeenCalledTimes(1);

    eventSourceInstance.listeners.connected?.(new MessageEvent('connected'));

    await waitFor(() => expect(first.result.current.isConnected).toBe(true));
    expect(second.result.current.isConnected).toBe(true);
    expect(firstConnected).toHaveBeenCalledTimes(1);
    expect(secondConnected).toHaveBeenCalledTimes(1);

    eventSourceInstance.listeners.task_progress?.(
      new MessageEvent('task_progress', {
        data: JSON.stringify({
          task_id: 'task-1',
          stock_code: '600519',
          status: 'processing',
          progress: 50,
          report_type: 'detailed',
          created_at: '2026-03-29T08:00:00Z',
        }),
      }),
    );

    expect(firstProgress).toHaveBeenCalledTimes(1);
    expect(secondProgress).toHaveBeenCalledTimes(1);

    first.unmount();
    expect(eventSourceInstance.close).not.toHaveBeenCalled();

    second.unmount();
    expect(eventSourceInstance.close).toHaveBeenCalledTimes(1);
  });

  it('reconnects the shared stream once after errors', async () => {
    vi.useFakeTimers();
    const firstError = vi.fn();
    const secondError = vi.fn();

    renderHook(() => useTaskStream({ enabled: true, onError: firstError }));
    renderHook(() => useTaskStream({ enabled: true, onError: secondError }));

    await vi.runOnlyPendingTimersAsync();
    expect(eventSourceInstances).toHaveLength(1);

    eventSourceInstance.onerror?.(new Event('error'));

    expect(firstError).toHaveBeenCalledTimes(1);
    expect(secondError).toHaveBeenCalledTimes(1);
    expect(eventSourceInstances[0].close).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1000);

    expect(eventSourceInstances).toHaveLength(2);
    expect(getTaskStreamUrl).toHaveBeenCalledTimes(2);
  });

  it('backs off exponentially between failed reconnects and resets after connecting', async () => {
    vi.useFakeTimers();
    renderHook(() => useTaskStream({ enabled: true }));
    await vi.runOnlyPendingTimersAsync();

    eventSourceInstances[0].onerror?.(new Event('error'));
    await vi.advanceTimersByTimeAsync(1000);
    expect(eventSourceInstances).toHaveLength(2);

    eventSourceInstances[1].onerror?.(new Event('error'));
    await vi.advanceTimersByTimeAsync(1999);
    expect(eventSourceInstances).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(eventSourceInstances).toHaveLength(3);

    act(() => eventSourceInstances[2].listeners.connected?.(new MessageEvent('connected')));
    act(() => eventSourceInstances[2].onerror?.(new Event('error')));
    await vi.advanceTimersByTimeAsync(1000);
    expect(eventSourceInstances).toHaveLength(4);
  });

  it('caps the reconnect delay at 30 seconds', async () => {
    vi.useFakeTimers();
    renderHook(() => useTaskStream({ enabled: true, reconnectDelay: 20_000 }));
    await vi.runOnlyPendingTimersAsync();

    eventSourceInstances[0].onerror?.(new Event('error'));
    await vi.advanceTimersByTimeAsync(20_000);
    expect(eventSourceInstances).toHaveLength(2);

    eventSourceInstances[1].onerror?.(new Event('error'));
    await vi.advanceTimersByTimeAsync(30_000);
    expect(eventSourceInstances).toHaveLength(3);
  });

  it('reconnects when the stream goes silent past the heartbeat window', async () => {
    vi.useFakeTimers();
    const onError = vi.fn();
    renderHook(() => useTaskStream({ enabled: true, onError }));
    await vi.runOnlyPendingTimersAsync();
    act(() => eventSourceInstances[0].listeners.connected?.(new MessageEvent('connected')));

    await vi.advanceTimersByTimeAsync(40_000);
    eventSourceInstances[0].listeners.heartbeat?.(new MessageEvent('heartbeat'));
    await vi.advanceTimersByTimeAsync(40_000);
    expect(eventSourceInstances[0].close).not.toHaveBeenCalled();

    await act(() => vi.advanceTimersByTimeAsync(5_000));
    expect(eventSourceInstances[0].close).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1000);
    expect(eventSourceInstances).toHaveLength(2);
  });

  it('does not reconnect after the hook unmounts', async () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useTaskStream({ enabled: true }));
    await vi.runOnlyPendingTimersAsync();

    eventSourceInstances[0].onerror?.(new Event('error'));
    unmount();
    await vi.advanceTimersByTimeAsync(120_000);

    expect(eventSourceInstances).toHaveLength(1);
  });

  it('reopens the shared stream with the new UI language when it changes', async () => {
    window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'ko');
    const { result } = renderHook(() => {
      useTaskStream({ enabled: true });
      return useUiLanguage();
    }, { wrapper: UiLanguageProvider });

    await waitFor(() => expect(eventSourceInstances).toHaveLength(1));
    expect(getTaskStreamUrl).toHaveBeenLastCalledWith('ko');

    act(() => result.current.setLanguage('en'));

    await waitFor(() => expect(eventSourceInstances).toHaveLength(2));
    expect(eventSourceInstances[0].close).toHaveBeenCalledTimes(1);
    expect(getTaskStreamUrl).toHaveBeenLastCalledWith('en');
    window.localStorage.removeItem(UI_LANGUAGE_STORAGE_KEY);
  });
});
