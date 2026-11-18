import { describe, expect, it } from 'vitest';
import type { SystemConfigItem } from '../../types/systemConfig';
import { searchSettings, type SettingsSearchGroup } from '../settingsSearch';

const item = (key: string): SystemConfigItem => ({ key, value: '', rawValueExists: false, isMasked: false });

const groups: SettingsSearchGroup[] = [
  { category: 'base', categoryTitle: '기본 설정', items: [item('STOCK_LIST'), item('REPORT_LANGUAGE')] },
  { category: 'notification', categoryTitle: '알림 채널', items: [item('WECHAT_WEBHOOK_URL'), item('FEISHU_WEBHOOK_URL')] },
];

const keysOf = (result: SettingsSearchGroup[]) => result.map((group) => [group.category, group.items.map((i) => i.key)]);

describe('searchSettings', () => {
  it('returns every group unchanged for an empty query', () => {
    expect(searchSettings(groups, '   ')).toBe(groups);
  });

  it('finds a field by its translated title and keeps its parent category', () => {
    expect(keysOf(searchSettings(groups, 'WeCom Webhook'))).toEqual([['notification', ['WECHAT_WEBHOOK_URL']]]);
    expect(keysOf(searchSettings(groups, '企业微信'))).toEqual([['notification', ['WECHAT_WEBHOOK_URL']]]);
  });

  it('matches config keys case-insensitively', () => {
    expect(keysOf(searchSettings(groups, 'stock_list'))).toEqual([['base', ['STOCK_LIST']]]);
  });

  it('returns the whole category when the query names it, and narrows with extra tokens', () => {
    expect(keysOf(searchSettings(groups, '알림'))).toEqual([['notification', ['WECHAT_WEBHOOK_URL', 'FEISHU_WEBHOOK_URL']]]);
    expect(keysOf(searchSettings(groups, '알림 feishu'))).toEqual([['notification', ['FEISHU_WEBHOOK_URL']]]);
  });

  it('drops groups without matches', () => {
    expect(searchSettings(groups, 'no-such-setting')).toEqual([]);
  });
});
