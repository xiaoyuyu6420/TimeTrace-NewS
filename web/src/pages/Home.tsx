import { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../stores/auth';
import { TimelineEventCard } from '../components/TimelineEventCard';
import { TimelineSection } from '../components/TimelineSection';
import { fetchPublicEvents, fetchEvents, searchEvents, fetchCategories } from '../api/events';
import { Clock, Rss, TrendingUp, Newspaper, ChevronDown } from 'lucide-react';
import type { Event, CategoryItem, TimeRange } from '../types';
import { TIME_RANGE_OPTIONS } from '../types';

const STATUS_FILTERS = [
  { value: 'active' as const, label: '进行中' },
  { value: 'resolved' as const, label: '已完结' },
  { value: '' as const, label: '全部' },
];

/** 按 updated_at 将事件分组为时间区间 */
function groupByTime(events: Event[]): { label: string; events: Event[] }[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, Event[]> = {};

  for (const event of events) {
    const d = event.updated_at ? new Date(event.updated_at) : new Date();
    let label: string;
    if (d >= today) label = '今天';
    else if (d >= yesterday) label = '昨天';
    else if (d >= weekAgo) label = '本周';
    else label = '更早';

    if (!groups[label]) groups[label] = [];
    groups[label].push(event);
  }

  // 保持顺序
  const order = ['今天', '昨天', '本周', '更早'];
  return order
    .filter((l) => groups[l]?.length)
    .map((label) => ({ label, events: groups[label] }));
}

export function Home() {
  const auth = useAuth();
  const [searchParams] = useSearchParams();
  const searchQuery = searchParams.get('q') || '';

  const [events, setEvents] = useState<Event[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);

  const [timeRange, setTimeRange] = useState<TimeRange>('all');
  const [statusFilter, setStatusFilter] = useState<'active' | 'resolved' | ''>('active');
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [categoryOpen, setCategoryOpen] = useState(false);

  // 加载分类
  useEffect(() => {
    fetchCategories().then((r) => setCategories(r.data)).catch((e) => console.error('Failed to load categories:', e));
  }, []);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      if (searchQuery) {
        const res = await searchEvents(searchQuery, page);
        setEvents(res.data.items);
        setTotalPages(res.data.total_pages);
      } else {
        const fn = auth.token ? fetchEvents : fetchPublicEvents;
        const params: Record<string, string | number> = { page, page_size: 20 };
        if (statusFilter) params.status = statusFilter;
        if (selectedCategory) params.category = selectedCategory;
        if (timeRange !== 'all') params.time_range = timeRange;
        const res = await fn(params);
        setEvents(res.data.items);
        setTotalPages(res.data.total_pages);
      }
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  }, [page, auth.token, statusFilter, selectedCategory, timeRange, searchQuery]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 搜索时重置页码
  useEffect(() => {
    setPage(1);
  }, [searchQuery, timeRange, statusFilter, selectedCategory]);

  const groups = groupByTime(events);

  return (
    <div>
      {/* Hero — 紧凑版 */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-cyan-900">
        <div className="absolute -top-24 -right-24 w-64 h-64 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 w-72 h-72 rounded-full bg-emerald-500/10 blur-3xl" />

        <div className="relative max-w-5xl mx-auto px-4 pt-12 pb-10">
          <div className="text-center animate-fade-in-up">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-cyan-300 text-xs font-medium mb-4 backdrop-blur-sm">
              <Newspaper className="w-3.5 h-3.5" />
              事件时间线
            </div>
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-2 tracking-tight">
              碎片新闻<span className="gradient-brand-text">，完整叙事</span>
            </h1>
            <p className="text-slate-400 text-sm max-w-md mx-auto">
              追踪事件的起因、经过、结果
            </p>
          </div>

          {/* 筛选条 */}
          <div className="mt-6 max-w-2xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
            <div className="flex items-center justify-center gap-2 flex-wrap">
              {/* 时间范围 */}
              {TIME_RANGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setTimeRange(opt.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    timeRange === opt.value
                      ? 'gradient-brand text-white shadow-md'
                      : 'text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {opt.label}
                </button>
              ))}

              <div className="w-px h-5 bg-white/10 mx-1" />

              {/* 状态 */}
              {STATUS_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setStatusFilter(f.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    statusFilter === f.value
                      ? 'gradient-brand text-white shadow-md'
                      : 'text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {f.label}
                </button>
              ))}

              {/* 分类下拉 */}
              {categories.length > 0 && (
                <>
                  <div className="w-px h-5 bg-white/10 mx-1" />
                  <div className="relative">
                    <button
                      onClick={() => setCategoryOpen(!categoryOpen)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-white/10 transition-all"
                    >
                      {selectedCategory || '分类'}
                      <ChevronDown className="w-3 h-3" />
                    </button>
                    {categoryOpen && (
                      <div className="absolute top-full mt-1 right-0 bg-white rounded-lg shadow-xl border border-slate-200 py-1 min-w-[120px] z-10 animate-fade-in">
                        <button
                          onClick={() => { setSelectedCategory(''); setCategoryOpen(false); }}
                          className={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-50 ${!selectedCategory ? 'text-cyan-600 font-medium' : 'text-slate-600'}`}
                        >
                          全部分类
                        </button>
                        {categories.map((c) => (
                          <button
                            key={c.name}
                            onClick={() => { setSelectedCategory(c.name); setCategoryOpen(false); }}
                            className={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-50 flex justify-between ${selectedCategory === c.name ? 'text-cyan-600 font-medium' : 'text-slate-600'}`}
                          >
                            <span>{c.name}</span>
                            <span className="text-slate-400">{c.count}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 事件内容 */}
      <div className="max-w-5xl mx-auto px-4 mt-6 pb-8">
        {/* 搜索结果标题 */}
        {searchQuery && (
          <div className="mb-4 text-sm text-slate-500">
            搜索 "<span className="text-slate-700 font-medium">{searchQuery}</span>" 的结果
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-6 h-6 border-2 border-slate-200 border-t-cyan-500 rounded-full animate-spin" />
          </div>
        ) : events.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-12 text-center animate-fade-in-up">
            <div className="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-cyan-50 to-emerald-50 flex items-center justify-center">
              <Clock className="w-9 h-9 text-cyan-300 animate-float" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-1">暂无事件</h3>
            <p className="text-sm text-slate-400 mb-4">系统将自动采集并聚合新闻事件</p>
            {auth.role === 'admin' && (
              <a href="/admin/sources" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30">
                <Rss className="w-4 h-4" /> 添加数据源
              </a>
            )}
          </div>
        ) : (
          <>
            {/* 按时间分组展示 */}
            {groups.map(({ label, events: groupEvents }) => (
              <TimelineSection key={label} title={label} count={groupEvents.length}>
                {groupEvents.map((event, i) => (
                  <TimelineEventCard
                    key={event.id}
                    event={event}
                    index={i}
                    isLast={i === groupEvents.length - 1}
                  />
                ))}
              </TimelineSection>
            ))}

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-8">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-600 disabled:opacity-30 hover:bg-slate-50 transition-colors"
                >
                  上一页
                </button>
                <span className="px-4 py-2 text-sm text-slate-400">{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-600 disabled:opacity-30 hover:bg-slate-50 transition-colors"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
