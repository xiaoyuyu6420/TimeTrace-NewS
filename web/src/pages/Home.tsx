import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../stores/auth';
import { EventCard } from '../components/EventCard';
import { Search, Newspaper, Clock, TrendingUp, Rss } from 'lucide-react';
import api from '../api/client';

interface EventItem {
  id: number;
  title: string;
  summary: string;
  importance: number;
  article_count: number;
  follow_count: number;
  start_date: string | null;
  status: string;
  is_followed: boolean;
}

interface PageData {
  items: EventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface Stats {
  total_articles: number;
  total_events: number;
  active_events: number;
  total_sources: number;
}

const FILTERS = [
  { value: 'active' as const, label: '进行中' },
  { value: 'resolved' as const, label: '已完结' },
  { value: '' as const, label: '全部' },
];

export function Home() {
  const auth = useAuth();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'active' | 'resolved' | ''>('active');
  const [stats, setStats] = useState<Stats | null>(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const endpoint = auth.token ? '/events' : '/events/public';
      const params: Record<string, string | number> = { page, page_size: 12 };
      if (filter) params.status = filter;
      const res = await api.get<PageData>(endpoint, { params });
      setEvents(res.data.items);
      setTotalPages(res.data.total_pages);
    } catch { /* */ } finally { setLoading(false); }
  }, [page, filter, auth.token]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  useEffect(() => {
    api.get<PageData>('/events/public', { params: { page: 1, page_size: 1 } }).then(r => {
      setStats({
        total_articles: 0,
        total_events: r.data.total,
        active_events: 0,
        total_sources: 0,
      });
    }).catch(() => {});
  }, []);

  const handleSearch = async () => {
    if (!search.trim()) { fetchEvents(); return; }
    setLoading(true);
    try {
      const res = await api.get<PageData>(`/events/search/${encodeURIComponent(search)}`, { params: { page: 1, page_size: 12 } });
      setEvents(res.data.items);
      setTotalPages(res.data.total_pages);
      setPage(1);
    } catch { /* */ } finally { setLoading(false); }
  };

  return (
    <div>
      {/* ===== Hero Section ===== */}
      <div className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-cyan-900">
        {/* Decorative circles */}
        <div className="absolute -top-24 -right-24 w-64 h-64 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 w-72 h-72 rounded-full bg-emerald-500/10 blur-3xl" />

        <div className="relative max-w-4xl mx-auto px-4 pt-16 pb-20">
          <div className="text-center animate-fade-in-up">
            {/* Badge */}
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-cyan-300 text-xs font-medium mb-6 backdrop-blur-sm">
              <Newspaper className="w-3.5 h-3.5" />
              新闻事件追踪平台
            </div>

            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight leading-tight">
              碎片新闻
              <span className="gradient-brand-text">，完整叙事</span>
            </h1>
            <p className="text-slate-400 text-lg max-w-lg mx-auto leading-relaxed">
              将碎片化的新闻聚合为有时间线的完整事件<br className="hidden sm:block" />
              像追剧一样追踪世界
            </p>
          </div>

          {/* Search bar inside hero */}
          <div className="mt-8 max-w-xl mx-auto animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
            <div className="flex items-center bg-white/10 backdrop-blur-md rounded-xl border border-white/10 p-1.5">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="搜索事件..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="w-full pl-9 pr-4 py-2.5 bg-transparent text-white placeholder:text-slate-500 outline-none text-sm"
                />
              </div>
              <div className="flex items-center gap-0.5 pl-2">
                {FILTERS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => { setFilter(f.value); setPage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      filter === f.value
                        ? 'gradient-brand text-white shadow-md'
                        : 'text-slate-400 hover:text-white hover:bg-white/10'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Stats row */}
          <div className="mt-10 flex justify-center gap-8 md:gap-12 animate-fade-in-up" style={{ animationDelay: '0.15s' }}>
            {[
              { icon: TrendingUp, label: '活跃事件', value: stats?.active_events ?? 0 },
              { icon: Newspaper, label: '文章总数', value: stats?.total_articles ?? 0 },
              { icon: Rss, label: '数据源', value: stats?.total_sources ?? 0 },
            ].map(({ icon: Icon, label, value }) => (
              <div key={label} className="text-center">
                <Icon className="w-5 h-5 text-cyan-400 mx-auto mb-1.5" />
                <div className="text-xl font-bold text-white">{value}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ===== Events Section ===== */}
      <div className="max-w-4xl mx-auto px-4 -mt-6">
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
            <p className="text-sm text-slate-400 mb-4">在管理后台添加 RSS 源后，系统将自动采集并聚合新闻事件</p>
            {auth.role === 'admin' && (
              <a href="/admin/sources" className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg gradient-brand text-white text-sm font-medium shadow-md shadow-cyan-200/30">
                <Rss className="w-4 h-4" /> 添加数据源
              </a>
            )}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 stagger">
              {events.map((event, i) => (
                <EventCard
                  key={event.id}
                  id={event.id}
                  title={event.title}
                  summary={event.summary}
                  importance={event.importance}
                  articleCount={event.article_count}
                  followCount={event.follow_count}
                  startDate={event.start_date}
                  status={event.status}
                  index={i}
                />
              ))}
            </div>

            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-8 pb-8">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="px-4 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-600 disabled:opacity-30 hover:bg-slate-50 transition-colors">
                  上一页
                </button>
                <span className="px-4 py-2 text-sm text-slate-400">{page} / {totalPages}</span>
                <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
                  className="px-4 py-2 rounded-lg text-sm bg-white border border-slate-200 text-slate-600 disabled:opacity-30 hover:bg-slate-50 transition-colors">
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
