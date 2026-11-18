import apiClient from './index';
import { errorText } from '../locales/errors';
import { toCamelCase } from './utils';
import type {
  AnalysisRequest,
  AnalysisResult,
  AnalyzeResponse,
  AnalyzeAsyncResponse,
  AnalysisReport,
  MarketReviewAccepted,
  MarketReviewRequest,
  TaskInfo,
  TaskStatus,
  TaskListResponse,
} from '../types/analysis';
import type { RunFlowSnapshot } from '../types/runFlow';
import { serializeMarketReviewRegions } from '../utils/marketReviewRegion';
import type { UiLanguage } from '../i18n/uiText';

// ============ API Interfaces ============

export const analysisApi = {
  /**
   * Trigger stock analysis.
   * @param data Analysis request payload
   * @returns Sync mode returns AnalysisResult; async mode returns accepted task payloads
   */
  analyze: async (data: AnalysisRequest): Promise<AnalyzeResponse> => {
    const requestData = {
      stock_code: data.stockCode,
      stock_codes: data.stockCodes,
      report_type: data.reportType || 'detailed',
      force_refresh: data.forceRefresh || false,
      async_mode: data.asyncMode || false,
      analysis_phase: data.analysisPhase || 'auto',
      stock_name: data.stockName,
      original_query: data.originalQuery,
      selection_source: data.selectionSource,
      skills: data.skills,
      report_language: data.reportLanguage,
      ...(data.notify !== undefined && { notify: data.notify }),
    };

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/analysis/analyze',
      requestData
    );

    const result = toCamelCase<AnalyzeResponse>(response.data);

    // Ensure the sync analysis report payload is converted recursively.
    if ('report' in result && result.report) {
      result.report = toCamelCase<AnalysisReport>(result.report);
    }

    return result;
  },

  /**
   * Trigger analysis in async mode.
   * @param data Analysis request payload
   * @returns Accepted task payloads; throws DuplicateTaskError on 409
   */
  analyzeAsync: async (data: AnalysisRequest): Promise<AnalyzeAsyncResponse> => {
    const requestData = {
      stock_code: data.stockCode,
      stock_codes: data.stockCodes,
      report_type: data.reportType || 'detailed',
      force_refresh: data.forceRefresh || false,
      async_mode: true,
      analysis_phase: data.analysisPhase || 'auto',
      stock_name: data.stockName,
      original_query: data.originalQuery,
      selection_source: data.selectionSource,
      skills: data.skills,
      report_language: data.reportLanguage,
      ...(data.notify !== undefined && { notify: data.notify }),
    };

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/analysis/analyze',
      requestData,
      {
        // Allow 202 accepted responses in addition to standard success codes.
        validateStatus: (status) => status === 200 || status === 202 || status === 409,
      }
    );

    // Handle duplicate submission compatibility.
    if (response.status === 409) {
      const errorData = toCamelCase<{
        error: string;
        message: string;
        stockCode: string;
        existingTaskId: string;
      }>(response.data);
      throw new DuplicateTaskError(errorData.stockCode, errorData.existingTaskId, errorData.message);
    }

    return toCamelCase<AnalyzeAsyncResponse>(response.data);
  },

  /**
   * Trigger market review in background mode.
   */
  triggerMarketReview: async (data: MarketReviewRequest = {}): Promise<MarketReviewAccepted> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/analysis/market-review',
      {
        send_notification: data.sendNotification ?? true,
        report_language: data.reportLanguage,
        ...(data.regions !== undefined && { region: serializeMarketReviewRegions(data.regions) }),
      },
      {
        validateStatus: (status) => status === 202 || status === 409,
      }
    );

    if (response.status === 409) {
      const detail = response.data?.detail;
      const message = detail && typeof detail === 'object' && 'message' in detail
        ? String((detail as { message?: unknown }).message || '')
        : String(response.data?.message || '');
      throw new Error(message || errorText('marketReviewRunning'));
    }

    return toCamelCase<MarketReviewAccepted>(response.data);
  },

  /**
   * Get async task status.
   * @param taskId Task ID
   */
  getStatus: async (taskId: string): Promise<TaskStatus> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/analysis/status/${taskId}`
    );

    const data = toCamelCase<TaskStatus>(response.data);

    // Ensure nested result payloads are converted recursively.
    if (data.result) {
      data.result = toCamelCase<AnalysisResult>(data.result);
      if (data.result.report) {
        data.result.report = toCamelCase<AnalysisReport>(data.result.report);
      }
    }

    return data;
  },

  /**
   * Get task list.
   * @param params Filter parameters
   */
  getTasks: async (params?: {
    status?: string;
    limit?: number;
  }): Promise<TaskListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/analysis/tasks',
      { params }
    );

    const data = toCamelCase<TaskListResponse>(response.data);

    return data;
  },

  /**
   * Get a run-flow snapshot for an active analysis task.
   * @param taskId Task ID
   */
  getTaskFlow: async (taskId: string): Promise<RunFlowSnapshot> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/analysis/tasks/${encodeURIComponent(taskId)}/flow`
    );

    return toCamelCase<RunFlowSnapshot>(response.data);
  },

  /**
   * Get the SSE stream URL.
   */
  /**
   * Cancel a task: pending ones stop at once, running stock analysis stops at its
   * next checkpoint (status becomes cancel_requested until then).
   */
  cancelTask: async (taskId: string): Promise<TaskInfo> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/analysis/tasks/${encodeURIComponent(taskId)}/cancel`,
    );
    return toCamelCase<TaskInfo>(response.data);
  },

  getTaskStreamUrl: (language: UiLanguage): string => {
    // Read API base URL from the shared client.
    const baseUrl = apiClient.defaults.baseURL || '';
    // EventSource cannot send the UI language header, so pass it as a query param.
    return `${baseUrl}/api/v1/analysis/tasks/stream?ui_language=${encodeURIComponent(language)}`;
  },
};

// ============ Custom Error Classes ============

/**
 * Duplicate task error.
 */
export class DuplicateTaskError extends Error {
  stockCode: string;
  existingTaskId: string;

  constructor(stockCode: string, existingTaskId: string, message?: string) {
    super(message || errorText('duplicateAnalysis', { code: stockCode }));
    this.name = 'DuplicateTaskError';
    this.stockCode = stockCode;
    this.existingTaskId = existingTaskId;
  }
}
