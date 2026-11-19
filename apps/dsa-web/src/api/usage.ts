import apiClient from './index';
import { toCamelCase } from './utils';

export type UsagePeriod = 'today' | 'month' | 'all';

export type UsageCallTypeBreakdown = {
  callType: string;
  calls: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
};

export type UsageModelBreakdown = {
  model: string;
  calls: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  maxTotalTokens: number;
};

export type UsageCallRecord = {
  id: number;
  calledAt: string;
  callType: string;
  model: string;
  stockCode?: string | null;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
};

export type UsageDashboard = {
  period: UsagePeriod;
  fromDate: string;
  toDate: string;
  totalCalls: number;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  totalTokens: number;
  byCallType: UsageCallTypeBreakdown[];
  byModel: UsageModelBreakdown[];
  recentCalls: UsageCallRecord[];
};

export type UsageCallGroup = {
  groupId: string;
  requestId?: string | null;
  calledAt: string;
  callType: string;
  models: string[];
  stockCode?: string | null;
  calls: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  items: UsageCallRecord[];
};

export type UsageCallGroupPage = {
  period: UsagePeriod;
  page: number;
  pageSize: number;
  total: number;
  items: UsageCallGroup[];
};

export const usageApi = {
  getCallGroups: async (params: { period?: UsagePeriod; page?: number; pageSize?: number } = {}): Promise<UsageCallGroupPage> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/usage/calls', {
      params: {
        period: params.period ?? 'month',
        page: params.page ?? 1,
        page_size: params.pageSize ?? 50,
      },
    });

    return toCamelCase<UsageCallGroupPage>(response.data);
  },

  getDashboard: async (params: { period?: UsagePeriod; limit?: number } = {}): Promise<UsageDashboard> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/usage/dashboard', {
      params: {
        period: params.period ?? 'month',
        limit: params.limit ?? 50,
      },
    });

    return toCamelCase<UsageDashboard>(response.data);
  },
};
