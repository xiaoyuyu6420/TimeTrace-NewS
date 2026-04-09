import { useEffect, useState } from 'react';
import api from '../../api/client';
import { Trash2, ExternalLink, CheckCircle, Circle } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Event, PageResponse } from '../../types';

export function AdminEvents() {
  const [data, setData] = useState<PageResponse<Event>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  const [page, setPage] = useState(1);

  const fetch = () => {
    api.get<PageResponse<Event>>('/events', { params: { page, page_size: 20 } }).then((r) => setData(r.data)).catch((e) => console.error('Failed to load events:', e));
  };

  useEffect(() => { fetch(); }, [page]);

  const toggleStatus = async (event: Event) => {
    const newStatus = event.status === 'active' ? 'resolved' : 'active';
    try {
      await api.put(`/events/${event.id}/status?status=${newStatus}`);
      fetch();
    } catch (e) {
      console.error('Failed to toggle event status:', e);
    }
  };

  const deleteEvent = async (id: number) => {
    if (!confirm('确定删除此事件？相关文章关联也会被删除。')) return;
    try {
      await api.delete(`/events/${id}`);
      fetch();
    } catch (e) {
      console.error('Failed to delete event:', e);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">事件管理</h1>
        <span className="text-sm text-slate-400">共 {data.total} 个事件</span>
      </div>

      <div className="bg-white rounded-xl border border-slate-200/80 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80 text-slate-500 text-xs">
            <tr>
              <th className="text-left px-4 py-3 font-medium">标题</th>
              <th className="text-left px-4 py-3 font-medium">状态</th>
              <th className="text-left px-4 py-3 font-medium">重要度</th>
              <th className="text-left px-4 py-3 font-medium">文章/关注</th>
              <th className="text-left px-4 py-3 font-medium">开始时间</th>
              <th className="text-right px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 max-w-[280px]">
                  <div className="font-medium text-slate-800 line-clamp-1">{e.title}</div>
                  {e.summary && <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{e.summary}</div>}
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => toggleStatus(e)} className="inline-flex items-center gap-1">
                    {e.status === 'active'
                      ? <><Circle className="w-3.5 h-3.5 text-cyan-500" /><span className="text-xs text-cyan-600">进行中</span></>
                      : <><CheckCircle className="w-3.5 h-3.5 text-emerald-500" /><span className="text-xs text-emerald-600">已完结</span></>
                    }
                  </button>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className={`w-1.5 h-1.5 rounded-full ${i <= e.importance ? 'bg-amber-400' : 'bg-slate-200'}`} />
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">{e.article_count} / {e.follow_count}</td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {e.start_date ? new Date(e.start_date).toLocaleDateString('zh-CN') : '-'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Link to={`/event/${e.id}`} className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-500 hover:bg-cyan-50 transition-colors">
                      <ExternalLink className="w-4 h-4" />
                    </Link>
                    <button onClick={() => deleteEvent(e.id)} className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">上一页</button>
          <span className="px-3 py-1.5 text-sm text-slate-400">{page} / {data.total_pages}</span>
          <button onClick={() => setPage(Math.min(data.total_pages, page + 1))} disabled={page === data.total_pages}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm disabled:opacity-30 hover:bg-slate-50">下一页</button>
        </div>
      )}
    </div>
  );
}
