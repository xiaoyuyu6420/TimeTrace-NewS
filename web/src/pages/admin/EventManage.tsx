import { useEffect, useState } from 'react';
import api from '../../api/client';
import {
  Merge, ArrowRight, Plus, Trash2, RefreshCw, Zap,
  ChevronDown, ChevronUp, X, Check, Search,
} from 'lucide-react';

// ─── Types ─────────────────────────────────────────────

interface Article {
  id: number;
  title: string;
  summary: string;
  keywords: string[];
  published_at: string | null;
}

interface EventItem {
  id: number;
  title: string;
  summary: string;
  status: string;
  importance: number;
  article_count: number;
  category: string;
}

interface PageData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── Component ─────────────────────────────────────────

export function AdminEventManage() {
  const [activeTab, setActiveTab] = useState<'merge' | 'assign' | 'tools'>('merge');

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">事件整理</h1>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-xl w-fit">
        {[
          { key: 'merge' as const, label: '合并事件', icon: Merge },
          { key: 'assign' as const, label: '分配文章', icon: ArrowRight },
          { key: 'tools' as const, label: '工具', icon: Zap },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === key
                ? 'gradient-brand text-white shadow-sm'
                : 'text-slate-500 hover:text-slate-700 hover:bg-white'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'merge' && <MergePanel />}
      {activeTab === 'assign' && <AssignPanel />}
      {activeTab === 'tools' && <ToolsPanel />}
    </div>
  );
}

// ─── Merge Events Panel ────────────────────────────────

function MergePanel() {
  const [events, setEvents] = useState<PageData<EventItem>>({ items: [], total: 0, page: 1, page_size: 50, total_pages: 0 });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [merging, setMerging] = useState(false);
  const [msg, setMsg] = useState('');

  const fetchEvents = () => {
    api.get<PageData<EventItem>>('/events', { params: { page, page_size: 50, status: 'active' } })
      .then(r => setEvents(r.data))
      .catch(() => {});
  };

  useEffect(() => { fetchEvents(); }, [page]);

  const toggleSelect = (id: number) => {
    setSelected(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleMerge = async () => {
    if (selected.length < 2) return;
    setMerging(true);
    setMsg('');
    try {
      // Merge all into the first selected
      const targetId = selected[0];
      for (let i = 1; i < selected.length; i++) {
        await api.post('/admin/events/merge', {
          source_id: selected[i],
          target_id: targetId,
        });
      }
      setMsg(`成功合并 ${selected.length} 个事件`);
      setSelected([]);
      fetchEvents();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || '合并失败');
    }
    setMerging(false);
  };

  return (
    <div>
      {msg && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${msg.includes('成功') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      <div className="flex items-center gap-3 mb-4">
        <span className="text-sm text-slate-500">已选 {selected.length} 个事件</span>
        <button
          onClick={handleMerge}
          disabled={selected.length < 2 || merging}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl gradient-brand text-white text-sm shadow-sm disabled:opacity-40"
        >
          <Merge className="w-3.5 h-3.5" />
          {merging ? '合并中...' : '合并选中'}
        </button>
        {selected.length >= 2 && (
          <span className="text-xs text-slate-400">
            将合并到: {events.items.find(e => e.id === selected[0])?.title || '第一个'}
          </span>
        )}
      </div>

      <div className="bg-white rounded-xl border border-slate-200/80 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80 text-slate-500 text-xs">
            <tr>
              <th className="w-10 px-3 py-3"></th>
              <th className="text-left px-3 py-3 font-medium">标题</th>
              <th className="text-left px-3 py-3 font-medium">文章数</th>
              <th className="text-left px-3 py-3 font-medium">类别</th>
            </tr>
          </thead>
          <tbody>
            {events.items.map(e => (
              <tr
                key={e.id}
                className={`border-t border-slate-100 transition-colors cursor-pointer ${
                  selected.includes(e.id) ? 'bg-cyan-50/50' : 'hover:bg-slate-50/50'
                }`}
                onClick={() => toggleSelect(e.id)}
              >
                <td className="px-3 py-3">
                  <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                    selected.includes(e.id) ? 'border-cyan-500 bg-cyan-500' : 'border-slate-300'
                  }`}>
                    {selected.includes(e.id) && <Check className="w-3 h-3 text-white" />}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <div className="font-medium text-slate-800 line-clamp-1">{e.title}</div>
                  {e.summary && <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{e.summary}</div>}
                </td>
                <td className="px-3 py-3 text-slate-500">{e.article_count}</td>
                <td className="px-3 py-3">
                  {e.category && <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-500 text-xs">{e.category}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {events.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">上一页</button>
          <span className="px-3 py-1.5 text-sm text-slate-400">{page} / {events.total_pages}</span>
          <button onClick={() => setPage(Math.min(events.total_pages, page + 1))} disabled={page === events.total_pages}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">下一页</button>
        </div>
      )}
    </div>
  );
}

// ─── Assign Articles Panel ─────────────────────────────

function AssignPanel() {
  const [unassigned, setUnassigned] = useState<PageData<Article>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  const [events, setEvents] = useState<EventItem[]>([]);
  const [page, setPage] = useState(1);
  const [assigning, setAssigning] = useState<Record<number, number>>({}); // articleId -> eventId
  const [msg, setMsg] = useState('');

  const fetchData = () => {
    api.get<PageData<Article>>('/admin/articles/unassigned', { params: { page, page_size: 20 } })
      .then(r => setUnassigned(r.data))
      .catch(() => {});
    api.get<PageData<EventItem>>('/events', { params: { page: 1, page_size: 100, status: 'active' } })
      .then(r => setEvents(r.data.items))
      .catch(() => {});
  };

  useEffect(() => { fetchData(); }, [page]);

  const handleAssign = async (articleId: number, eventId: number) => {
    setMsg('');
    try {
      await api.post(`/admin/articles/${articleId}/assign`, { event_id: eventId });
      setMsg('分配成功');
      setAssigning(prev => {
        const next = { ...prev };
        delete next[articleId];
        return next;
      });
      fetchData();
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || '分配失败');
    }
  };

  return (
    <div>
      {msg && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm ${msg.includes('成功') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
          {msg}
        </div>
      )}

      <div className="mb-4 text-sm text-slate-500">
        未分组文章: {unassigned.total} 篇
      </div>

      <div className="space-y-2">
        {unassigned.items.map(a => (
          <div key={a.id} className="bg-white rounded-xl border border-slate-200/80 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-slate-800 line-clamp-2">{a.title}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(a.keywords || []).slice(0, 5).map(kw => (
                    <span key={kw} className="px-1.5 py-0.5 rounded bg-cyan-50 text-cyan-600 text-[10px]">{kw}</span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <select
                  value={assigning[a.id] || ''}
                  onChange={e => setAssigning(prev => ({ ...prev, [a.id]: Number(e.target.value) }))}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm outline-none focus:border-cyan-400 max-w-[200px]"
                >
                  <option value="">选择事件...</option>
                  {events.map(ev => (
                    <option key={ev.id} value={ev.id}>{ev.title}</option>
                  ))}
                </select>
                <button
                  onClick={() => assigning[a.id] && handleAssign(a.id, assigning[a.id])}
                  disabled={!assigning[a.id]}
                  className="p-2 rounded-lg gradient-brand text-white disabled:opacity-30"
                >
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {unassigned.items.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <Check className="w-8 h-8 mx-auto mb-2 text-emerald-400" />
            所有文章都已分组
          </div>
        )}
      </div>

      {unassigned.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">上一页</button>
          <span className="px-3 py-1.5 text-sm text-slate-400">{page} / {unassigned.total_pages}</span>
          <button onClick={() => setPage(Math.min(unassigned.total_pages, page + 1))} disabled={page === unassigned.total_pages}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">下一页</button>
        </div>
      )}
    </div>
  );
}

// ─── Tools Panel ───────────────────────────────────────

function ToolsPanel() {
  const [running, setRunning] = useState('');
  const [msg, setMsg] = useState('');

  const triggerAction = async (action: string, endpoint: string) => {
    setRunning(action);
    setMsg('');
    try {
      const res = await api.post(endpoint);
      setMsg(res.data.message || `${action}已启动`);
    } catch {
      setMsg(`${action}失败`);
    }
    setRunning('');
  };

  return (
    <div className="space-y-4">
      {msg && (
        <div className="px-4 py-2 rounded-lg text-sm bg-cyan-50 text-cyan-700">{msg}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Re-aggregate */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg gradient-brand flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-medium text-slate-800">重新聚合</div>
              <div className="text-xs text-slate-400">重新处理所有未分组文章</div>
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            使用 Embedding 语义相似度 + 时间窗口重新匹配文章到事件。适合调整阈值后重新运行。
          </p>
          <button
            onClick={() => triggerAction('聚合', '/admin/aggregate')}
            disabled={!!running}
            className="px-4 py-2 rounded-xl gradient-brand text-white text-sm disabled:opacity-40"
          >
            {running === '聚合' ? '运行中...' : '开始聚合'}
          </button>
        </div>

        {/* Re-embed */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-medium text-slate-800">重新向量化</div>
              <div className="text-xs text-slate-400">为文章生成 Embedding 向量</div>
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            调用智谱 Embedding API 为缺少向量的文章生成语义向量。需要配置 LLM_API_KEY。
          </p>
          <button
            onClick={() => triggerAction('向量化', '/admin/reembed')}
            disabled={!!running}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white text-sm disabled:opacity-40"
          >
            {running === '向量化' ? '运行中...' : '开始向量化'}
          </button>
        </div>

        {/* Crawl */}
        <div className="bg-white rounded-xl border border-slate-200/80 p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
              <Search className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-medium text-slate-800">抓取 RSS</div>
              <div className="text-xs text-slate-400">手动触发 RSS 源抓取</div>
            </div>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            抓取后自动执行关键词提取、Embedding 生成和事件聚合完整流程。
          </p>
          <button
            onClick={() => triggerAction('抓取', '/rss/crawl')}
            disabled={!!running}
            className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-400 to-orange-500 text-white text-sm disabled:opacity-40"
          >
            {running === '抓取' ? '运行中...' : '开始抓取'}
          </button>
        </div>
      </div>
    </div>
  );
}
