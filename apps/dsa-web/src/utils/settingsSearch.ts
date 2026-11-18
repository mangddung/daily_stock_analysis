import type { SystemConfigItem } from '../types/systemConfig';
import {
  getFieldDescriptionKo,
  getFieldDescriptionZh,
  getFieldTitleKo,
  getFieldTitleZh,
} from './systemConfigI18n';

export interface SettingsSearchGroup {
  category: string;
  categoryTitle: string;
  items: SystemConfigItem[];
}

function splitQuery(query: string): string[] {
  return query.trim().toLowerCase().split(/\s+/).filter(Boolean);
}

/** Every name a field can be found by: key, zh/en/ko titles and descriptions, regardless of UI language. */
function getSearchableText(item: SystemConfigItem): string {
  const key = item.schema?.key ?? item.key;
  return [
    key,
    item.schema?.title,
    item.schema?.description,
    getFieldTitleZh(key, ''),
    getFieldTitleKo(key, ''),
    getFieldDescriptionZh(key, ''),
    getFieldDescriptionKo(key, ''),
  ].filter(Boolean).join('\n').toLowerCase();
}

/**
 * Filters settings groups by a whitespace-separated query. A field matches when every
 * token appears in its own text or its category title, so a category-name query returns
 * the whole category and "알림 webhook" narrows to webhook fields under 알림 채널.
 * Groups without matches are dropped; group and item order are preserved.
 */
export function searchSettings(groups: SettingsSearchGroup[], query: string): SettingsSearchGroup[] {
  const tokens = splitQuery(query);
  if (!tokens.length) {
    return groups;
  }
  return groups
    .map((group) => {
      const categoryText = group.categoryTitle.toLowerCase();
      const items = group.items.filter((item) => {
        const text = `${categoryText}\n${getSearchableText(item)}`;
        return tokens.every((token) => text.includes(token));
      });
      return { ...group, items };
    })
    .filter((group) => group.items.length > 0);
}
