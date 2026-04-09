/** Event API 封装。 */

import api from './client';
import type { Event, EventDetail, CategoryItem, PageResponse, TimeRange } from '../types';

interface EventListParams {
  page?: number;
  page_size?: number;
  status?: string;
  category?: string;
  time_range?: TimeRange;
  keyword?: string;
}

/** 获取公开事件列表 */
export function fetchPublicEvents(params: EventListParams = {}) {
  return api.get<PageResponse<Event>>('/events/public', {
    params: { page_size: 20, ...params },
  });
}

/** 获取认证用户事件列表 */
export function fetchEvents(params: EventListParams = {}) {
  return api.get<PageResponse<Event>>('/events', {
    params: { page_size: 20, ...params },
  });
}

/** 获取公开事件详情（含时间线） */
export function fetchPublicEventDetail(id: number) {
  return api.get<EventDetail>(`/events/${id}/public`);
}

/** 获取认证用户事件详情 */
export function fetchEventDetail(id: number) {
  return api.get<EventDetail>(`/events/${id}`);
}

/** 搜索事件 */
export function searchEvents(query: string, page = 1) {
  return api.get<PageResponse<Event>>(`/events/search/${encodeURIComponent(query)}`, {
    params: { page, page_size: 20 },
  });
}

/** 获取事件分类列表 */
export function fetchCategories() {
  return api.get<CategoryItem[]>('/events/categories');
}
