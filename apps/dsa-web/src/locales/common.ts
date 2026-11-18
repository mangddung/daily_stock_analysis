import type { UiLanguage } from '../i18n/uiText';

export const COMMON_TEXT = {
  zh: {
    notFoundDocumentTitle: '页面未找到 - DSA',
    notFoundTitle: '页面未找到',
    notFoundDescription: '抱歉，您访问的页面不存在或已被移动',
    notFoundBackHome: '返回首页',
    stockSearchPlaceholder: '输入股票代码或名称',
    marketCN: 'A股',
    marketHK: '港股',
    marketUS: '美股',
    marketJP: '日股',
    marketKR: '韩股',
    marketINDEX: '指数',
    marketETF: 'ETF',
    marketBSE: '北交所',
    matchExact: '精确',
    matchPrefix: '前缀',
    matchContains: '包含',
    matchFuzzy: '模糊',
  },
  en: {
    notFoundDocumentTitle: 'Page Not Found - DSA',
    notFoundTitle: 'Page not found',
    notFoundDescription: "Sorry, the page you're looking for doesn't exist or has been moved.",
    notFoundBackHome: 'Back to home',
    stockSearchPlaceholder: 'Enter stock code or name',
    marketCN: 'CN',
    marketHK: 'HK',
    marketUS: 'US',
    marketJP: 'JP',
    marketKR: 'KR',
    marketINDEX: 'Index',
    marketETF: 'ETF',
    marketBSE: 'BSE',
    matchExact: 'Exact',
    matchPrefix: 'Prefix',
    matchContains: 'Contains',
    matchFuzzy: 'Fuzzy',
  },
  ko: {
    notFoundDocumentTitle: '페이지를 찾을 수 없음 - DSA',
    notFoundTitle: '페이지를 찾을 수 없습니다',
    notFoundDescription: '요청하신 페이지가 존재하지 않거나 이동되었습니다.',
    notFoundBackHome: '홈으로 돌아가기',
    stockSearchPlaceholder: '종목 코드 또는 종목명 입력',
    marketCN: 'A주',
    marketHK: '홍콩',
    marketUS: '미국',
    marketJP: '일본',
    marketKR: '한국',
    marketINDEX: '지수',
    marketETF: 'ETF',
    marketBSE: 'BSE',
    matchExact: '정확',
    matchPrefix: '접두사',
    matchContains: '포함',
    matchFuzzy: '유사',
  },
} as const;

// Run-flow edge labels are produced in Chinese by useRunFlowSnapshot; map them at display time.
const RUN_FLOW_EDGE_LABEL_EN: Record<string, string> = {
  降级: 'Fallback',
  重试: 'Retry',
  生成: 'Generate',
  保存: 'Save',
  通知: 'Notify',
};

const RUN_FLOW_EDGE_LABEL_KO: Record<string, string> = {
  降级: '폴백',
  重试: '재시도',
  生成: '생성',
  保存: '저장',
  通知: '알림',
};

export const getRunFlowEdgeLabel = (label: string, language: UiLanguage): string =>
  (language === 'ko' && (RUN_FLOW_EDGE_LABEL_KO[label] || RUN_FLOW_EDGE_LABEL_EN[label]))
  || (language === 'en' && RUN_FLOW_EDGE_LABEL_EN[label])
  || label;
