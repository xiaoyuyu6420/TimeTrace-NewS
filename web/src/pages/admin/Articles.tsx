import { useEffect, useState } from 'react';
import api from '../../api/client';
import { Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import type { Article, PageResponse } from '../../types';

export function AdminArticles() {
  const [data, setData] = useState<PageResponse<Article>>({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');

  const fetch = () => {
    const params: Record<string, number | string> = { page, page_size: 20 };
    if (keyword) params.keyword = keyword;
    api.get<PageResponse<Article>>('/articles', { params }).then((r) => setData(r.data)).catch((e) => console.error('Failed to load articles:', e));
  };

  useEffect(fetch, [page]);

  const deleteArticle = async (id: number) => {
    if (!confirm('确定删除此文章？')) return;
    try {
      await api.delete(`/articles/${id}`);
      fetch();
    } catch (e) {
      console.error('Failed to delete article:', e);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800">文章管理</h1>
        <span className="text-sm text-slate-400">共 {data.total} 篇</span>
      </div>

      <div className="mb-4 flex gap-2">
        <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && fetch()}
          placeholder="搜索文章标题..."
          className="flex-1 px-4 py-2 rounded-xl border border-slate-200/80 text-sm focus:border-cyan-400 outline-none" />
        <button onClick={fetch} className="px-4 py-2 rounded-xl gradient-brand text-white text-sm shadow-sm">搜索</button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200/80 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50/80 text-slate-500 text-xs">
            <tr>
              <th className="text-left px-4 py-3 font-medium">标题</th>
              <th className="text-left px-4 py-3 font-medium">关键词</th>
              <th className="text-left px-4 py-3 font-medium">时间</th>
              <th className="text-right px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((a) => (
              <tr key={a.id} className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 max-w-[300px]">
                  <div className="font-medium text-slate-800 line-clamp-1">{a.title}</div>
                  {a.summary && <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">{a.summary}</div>}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {(a.keywords || []).slice(0, 3).map((kw) => (
                      <span key={kw} className="px-1.5 py-0.5 rounded bg-cyan-50 text-cyan-600 text-[10px]">{kw}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {a.published_at ? new Date(a.published_at).toLocaleDateString('zh-CN') : '-'}
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => deleteArticle(a.id)} className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.total_pages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="p-2 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50"><ChevronLeft className="w-4 h-4" /></button>
          <span className="px-3 py-2 text-sm text-slate-400">{page} / {data.total_pages}</span>
          <button onClick={() => setPage(Math.min(data.total_pages, page + 1))} disabled={page === data.total_pages}
            className="p-2 rounded-lg border border-slate-200 disabled:opacity-30 hover:bg-slate-50"><ChevronRight className="w-4 h-4" /></button>
        </div>
      )}
    </div>
  );
}
