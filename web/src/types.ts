/** 共享类型定义 — 与后端 schemas 对齐。 */

export interface Article {
  id: number;
  title: string;
  content?: string;
  summary: string;
  source_url: string;
  keywords: string[];
  entities: unknown[];
  rss_source_id: number | null;
  rss_source_name: string;
  credibility_score: number;
  pipeline_state: string;
  published_at: string | null;
  created_at: string | null;
  /** 管线阶段数据（仅管线查询时返回） */
  distillation?: Distillation | null;
  reasoning?: Reasoning | null;
}

export interface Distillation {
  id: number;
  article_id: number;
  facts: { content: string; fact_type: string; entities: string[]; numbers: string[]; confidence: number }[];
  core_entities: string[];
  key_numbers: string[];
  primary_action: string;
  summary_line: string;
  confidence: number;
  model_used: string;
  is_llm_generated: boolean;
  processing_time_ms: number;
  created_at: string | null;
}

export interface Reasoning {
  id: number;
  article_id: number;
  action: string;
  target_event_id: number | null;
  target_event_title: string;
  phase: string;
  suggested_category: string;
  suggested_importance: number;
  event_title: string;
  event_summary: string;
  has_conflict: boolean;
  conflict_details: string;
  confidence: number;
  needs_review: boolean;
  safe_mode: boolean;
  model_used: string;
  processing_time_ms: number;
  created_at: string | null;
}

export interface Event {
  id: number;
  title: string;
  summary: string;
  category: string;
  importance: number;
  status: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string | null;
  updated_at: string | null;
  article_count: number;
  follow_count: number;
  is_followed: boolean;
}

export interface TimelinePhase {
  phase: 'trigger' | 'development' | 'outcome' | 'followup';
  phase_label: string;
  date: string | null;
  articles: Article[];
}

export interface EventDetail extends Event {
  articles: Article[];
  timeline: TimelinePhase[];
}

export interface CategoryItem {
  name: string;
  count: number;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** 时间范围筛选值 */
export type TimeRange = 'today' | 'week' | 'month' | 'all';

/** 阶段标签映射 */
export const PHASE_LABELS: Record<string, string> = {
  trigger: '起因',
  development: '经过',
  outcome: '结果',
  followup: '后续',
};

/** 阶段颜色映射 */
export const PHASE_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  trigger:      { bg: 'bg-amber-50',  border: 'border-amber-300',  text: 'text-amber-700',  dot: 'bg-amber-400' },
  development:  { bg: 'bg-cyan-50',   border: 'border-cyan-300',   text: 'text-cyan-700',   dot: 'bg-cyan-400' },
  outcome:      { bg: 'bg-emerald-50', border: 'border-emerald-300', text: 'text-emerald-700', dot: 'bg-emerald-400' },
  followup:     { bg: 'bg-slate-50',  border: 'border-slate-300',  text: 'text-slate-600',  dot: 'bg-slate-400' },
};

/** 重要程度配置 */
export const IMPORTANCE_CONFIG: Record<number, { color: string; label: string; bar: string }> = {
  1: { color: 'bg-slate-100 text-slate-500', label: '', bar: 'bg-slate-300' },
  2: { color: 'bg-blue-50 text-blue-500',    label: '', bar: 'bg-blue-400' },
  3: { color: 'bg-cyan-50 text-cyan-600',    label: '重要', bar: 'bg-cyan-500' },
  4: { color: 'bg-orange-50 text-orange-600', label: '热点', bar: 'bg-orange-500' },
  5: { color: 'bg-red-50 text-red-600',       label: '头条', bar: 'bg-red-500' },
};

/** 时间范围选项 */
export const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: 'week',  label: '本周' },
  { value: 'month', label: '本月' },
  { value: 'all',   label: '全部' },
];
